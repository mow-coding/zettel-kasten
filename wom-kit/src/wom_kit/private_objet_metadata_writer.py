"""Approval-gated v0.3.296 private objet metadata writer.

The public service wrapper lives in :mod:`wom_kit.archive_services`.  This
module keeps the private writer isolated from search, indexes, providers, and
object-byte operations.  Dry-run is a bounded read-only snapshot on every
platform.  Approved mutation is delegated to the retained-handle Win32 helper
and never falls back to path-based POSIX or shell operations.
"""

from __future__ import annotations

from array import array
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
from typing import Any, Iterable

from . import private_objet_metadata as private_metadata
from . import private_objet_metadata_writer_contract as contract
from .schema_validator import validate_schema


RESULT_SCHEMA = "wom-kit/private-objet-source-metadata-write-result/v0.1"

OBJECT_MANIFEST_MAX_BYTES = 536_870_912
OBJECT_MANIFEST_MAX_ROWS = 1_000_000
OBJECT_MANIFEST_MAX_ROW_BYTES = 1_048_576
PRIVATE_MANIFEST_MAX_BYTES = 268_435_456
PRIVATE_MANIFEST_MAX_ROWS = 100_000
PRIVATE_MANIFEST_MAX_ROW_BYTES = 1_048_576
PRIVATE_RECEIPT_MAX_BYTES = 65_536
PRIVATE_RECEIPT_MAX_COUNT = 100_000
PRIVATE_RECEIPT_TOTAL_BYTES_MAX = 536_870_912
PRIVATE_RECEIPT_DIR_MAX_ENTRIES = 100_002
PRIVATE_RECEIPT_ANCESTOR_DIR_MAX_ENTRIES = 100_000
PRIVATE_MANIFEST_DIR_MAX_ENTRIES = 100_000
PRIVATE_JOURNAL_MAX_BYTES = 131_072

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REVIEWED_BY_RE = re.compile(
    r"^operator:[A-Za-z0-9][A-Za-z0-9._-]{0,190}$"
)
_RECEIPT_BASENAME_RE = re.compile(r"^[0-9a-f]{64}\.json$")
_OWNED_TEMP_BASENAME_RE = re.compile(
    r"^\.[0-9a-f]{64}\.receipt\.tmp$"
)
_WINDOWS_REPARSE_ATTRIBUTE = 0x400

_CURRENT_BOUND_REASONS = (
    (
        "object_manifest_bytes_limit",
        "private_metadata_object_manifest_bytes_limit_exceeded",
    ),
    (
        "object_manifest_rows_limit",
        "private_metadata_object_manifest_rows_limit_exceeded",
    ),
    (
        "object_manifest_row_bytes_limit",
        "private_metadata_object_manifest_row_bytes_limit_exceeded",
    ),
    (
        "private_manifest_bytes_limit",
        "private_metadata_manifest_bytes_limit_exceeded",
    ),
    (
        "private_manifest_rows_limit",
        "private_metadata_manifest_rows_limit_exceeded",
    ),
    (
        "private_manifest_row_bytes_limit",
        "private_metadata_manifest_row_bytes_limit_exceeded",
    ),
    (
        "receipt_bytes_limit",
        "private_metadata_receipt_bytes_limit_exceeded",
    ),
    (
        "receipt_count_limit",
        "private_metadata_receipt_count_limit_exceeded",
    ),
    (
        "receipt_total_bytes_limit",
        "private_metadata_receipt_total_bytes_limit_exceeded",
    ),
    (
        "receipt_directory_entries_limit",
        "private_metadata_receipt_directory_entries_limit_exceeded",
    ),
    (
        "receipt_ancestor_directory_entries_limit",
        "private_metadata_receipt_ancestor_directory_entries_limit_exceeded",
    ),
    (
        "manifest_directory_entries_limit",
        "private_metadata_manifest_directory_entries_limit_exceeded",
    ),
    (
        "journal_bytes_limit",
        "private_metadata_journal_bytes_limit_exceeded",
    ),
)

_PROSPECTIVE_REASONS = (
    (
        "prospective_private_manifest_bytes",
        PRIVATE_MANIFEST_MAX_BYTES,
        "private_metadata_prospective_manifest_bytes_limit_exceeded",
    ),
    (
        "prospective_private_manifest_rows",
        PRIVATE_MANIFEST_MAX_ROWS,
        "private_metadata_prospective_manifest_rows_limit_exceeded",
    ),
    (
        "canonical_stored_row_bytes",
        PRIVATE_MANIFEST_MAX_ROW_BYTES,
        "private_metadata_prospective_manifest_row_bytes_limit_exceeded",
    ),
    (
        "prospective_receipt_bytes",
        PRIVATE_RECEIPT_MAX_BYTES,
        "private_metadata_prospective_receipt_bytes_limit_exceeded",
    ),
    (
        "prospective_receipt_final_count",
        PRIVATE_RECEIPT_MAX_COUNT,
        "private_metadata_prospective_receipt_count_limit_exceeded",
    ),
    (
        "prospective_receipt_final_total_bytes",
        PRIVATE_RECEIPT_TOTAL_BYTES_MAX,
        "private_metadata_prospective_receipt_total_bytes_limit_exceeded",
    ),
    (
        "prospective_receipt_directory_peak_entries",
        PRIVATE_RECEIPT_DIR_MAX_ENTRIES,
        "private_metadata_prospective_receipt_directory_entries_limit_exceeded",
    ),
    (
        "receipt_root_entries_after_bootstrap",
        PRIVATE_RECEIPT_ANCESTOR_DIR_MAX_ENTRIES,
        "private_metadata_prospective_receipt_ancestor_directory_entries_limit_exceeded",
    ),
    (
        "receipt_objects_entries_after_bootstrap",
        PRIVATE_RECEIPT_ANCESTOR_DIR_MAX_ENTRIES,
        "private_metadata_prospective_receipt_ancestor_directory_entries_limit_exceeded",
    ),
    (
        "prospective_manifest_directory_peak_entries",
        PRIVATE_MANIFEST_DIR_MAX_ENTRIES,
        "private_metadata_prospective_manifest_directory_entries_limit_exceeded",
    ),
    (
        "prospective_journal_bytes",
        PRIVATE_JOURNAL_MAX_BYTES,
        "private_metadata_prospective_journal_bytes_limit_exceeded",
    ),
)


class _DuplicateKeyError(ValueError):
    pass


class _SnapshotError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _CurrentBoundError(_SnapshotError):
    def __init__(self, reasons: Iterable[str]) -> None:
        ordered = _ordered_current_bound_internal_reasons(reasons)
        if not ordered:
            raise ValueError("current-bound error requires a known reason")
        self.reasons = ordered
        super().__init__(ordered[0])


class _PreplanSemanticError(_SnapshotError):
    def __init__(self, reasons: Iterable[str]) -> None:
        observed = set(reasons)
        ordered = [
            reason
            for reason in (
                "journal_cross_field_mismatch",
                "receipt_semantic_mismatch",
            )
            if reason in observed
        ]
        if not ordered:
            raise ValueError("semantic error requires a known reason")
        self.reasons = ordered
        super().__init__(ordered[0])


@dataclass
class _ObjectManifestAuthorityWork:
    parsed_bytes: int = 0
    parsed_rows: int = 0
    prefix_lookups: int = 0
    prefix_lookup_units: int = 0


@dataclass(frozen=True)
class _ObjectManifestOccurrence:
    first_row_number: int
    first_sha256: str
    second_row_number: int | None


@dataclass(frozen=True)
class _ObjectManifestPrefixAuthority:
    row_count: int
    prefix_byte_counts: array
    prefix_sha256_bytes: bytearray
    object_occurrences: dict[str, _ObjectManifestOccurrence]
    parsed_byte_count: int


@dataclass(frozen=True)
class _FileSnapshot:
    path: Path
    raw: bytes | None
    state: dict[str, Any]
    identity: tuple[int, int] | None


@dataclass
class _PlanningContext:
    root: Path
    archive_id: str
    intake: dict[str, Any]
    intake_sha256: str
    row: dict[str, Any]
    row_cjson: bytes
    stored_row: bytes
    canonical_row_sha256: str
    authority_key_sha256: str
    receipt_relative_path: str
    owned_temp_relative_paths: list[str]
    object_manifest: _FileSnapshot
    object_manifest_prefix_authority: _ObjectManifestPrefixAuthority
    object_manifest_match_count: int
    private_manifest: _FileSnapshot
    private_rows: list[dict[str, Any]]
    private_row_bytes: list[bytes]
    journal: _FileSnapshot
    journal_document: dict[str, Any] | None
    receipt: _FileSnapshot
    receipt_document: dict[str, Any] | None
    temp_snapshots: dict[str, _FileSnapshot]
    receipt_directory_chain_before: dict[str, Any]
    receipt_directory_chain_after: dict[str, Any]
    receipt_inventory: list[tuple[str, int]]
    receipt_directory_entry_count: int
    manifest_directory_entry_count: int
    authority_chain: dict[str, Any] | None
    authority_chain_sha256: str | None
    authority_chain_validation: str
    action: str
    reasons: list[str]
    prior_row_state: str
    receipt_inventory_state: str
    authority_chain_scope: str
    existing_exact_row_count: int
    exact_receipt_count: int
    planned_receipt_sha256: str | None


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _ordered_current_bound_internal_reasons(
    reasons: Iterable[str],
) -> list[str]:
    observed = set(reasons)
    return [
        internal
        for internal, _ in _CURRENT_BOUND_REASONS
        if internal in observed
    ]


def _current_bound_public_reasons(
    reasons: Iterable[str],
) -> list[str]:
    observed = set(reasons)
    return [
        public
        for internal, public in _CURRENT_BOUND_REASONS
        if internal in observed
    ]


def _contains_surrogate(value: Any) -> bool:
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            if any(0xD800 <= ord(char) <= 0xDFFF for char in current):
                return True
        elif isinstance(current, dict):
            pending.extend(current.keys())
            pending.extend(current.values())
        elif isinstance(current, (list, tuple)):
            pending.extend(current)
    return False


def _duplicate_key_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError
        result[key] = value
    return result


def _reject_non_finite(_: str) -> Any:
    raise ValueError


def _strict_json(raw: bytes) -> Any:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("BOM")
    value = json.loads(
        raw.decode("utf-8", errors="strict"),
        object_pairs_hook=_duplicate_key_object,
        parse_constant=_reject_non_finite,
    )
    if _contains_surrogate(value):
        raise ValueError("surrogate")
    return value


def _is_reparse(stat_result: os.stat_result) -> bool:
    return bool(
        getattr(stat_result, "st_file_attributes", 0)
        & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _identity(stat_result: os.stat_result) -> tuple[int, int]:
    return (int(stat_result.st_dev), int(stat_result.st_ino))


def _absent_state() -> dict[str, Any]:
    return {
        "state": "absent",
        "sha256": None,
        "byte_count": 0,
        "row_count": 0,
        "link_count": 0,
    }


def _present_state(raw: bytes, row_count: int, link_count: int = 1) -> dict[str, Any]:
    return {
        "state": "present",
        "sha256": contract.sha256_digest(raw),
        "byte_count": len(raw),
        "row_count": row_count,
        "link_count": link_count,
    }


def _present_invalid_state(raw: bytes, link_count: int) -> dict[str, Any]:
    return {
        "state": "present_invalid",
        "sha256": contract.sha256_digest(raw),
        "byte_count": len(raw),
        "row_count": None,
        "link_count": link_count,
    }


def _unavailable_state(
    *,
    byte_count: int | None = None,
    link_count: int | None = None,
) -> dict[str, Any]:
    return {
        "state": "unavailable",
        "sha256": None,
        "byte_count": byte_count,
        "row_count": None,
        "link_count": link_count,
    }


def _safe_relative_parts(value: str) -> tuple[str, ...] | None:
    if (
        type(value) is not str
        or not value
        or "\\" in value
        or "\x00" in value
        or PureWindowsPath(value).is_absolute()
        or PurePosixPath(value).is_absolute()
    ):
        return None
    path = PurePosixPath(value)
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path.parts


def _path_has_safe_chain(root: Path, path: Path, *, final_may_absent: bool) -> bool:
    try:
        root_stat = os.lstat(root)
    except OSError:
        return False
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or stat.S_ISLNK(root_stat.st_mode)
        or _is_reparse(root_stat)
    ):
        return False
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    current = root
    for index, part in enumerate(relative.parts):
        current = current / part
        try:
            item_stat = os.lstat(current)
        except FileNotFoundError:
            return final_may_absent
        except OSError:
            return False
        if stat.S_ISLNK(item_stat.st_mode) or _is_reparse(item_stat):
            return False
        if index < len(relative.parts) - 1 and not stat.S_ISDIR(item_stat.st_mode):
            return False
    return True


def _safe_archive_path(
    root: Path,
    relative: str,
    *,
    final_may_absent: bool,
) -> Path | None:
    parts = _safe_relative_parts(relative)
    if parts is None:
        return None
    path = root.joinpath(*parts)
    if not _path_has_safe_chain(root, path, final_may_absent=final_may_absent):
        return None
    return path


def _read_regular_snapshot(
    root: Path,
    path: Path,
    *,
    maximum_bytes: int,
    allow_absent: bool,
    classify: Any,
    allowed_link_counts: tuple[int, ...] = (1,),
) -> _FileSnapshot:
    # Import lazily: archive_services exposes the public wrapper and imports
    # this module only after its retained read-only chain helpers are defined.
    from . import archive_services as services

    if not path.parent.exists():
        if allow_absent:
            return _FileSnapshot(path, None, _absent_state(), None)
        raise _SnapshotError("unavailable")
    try:
        with services._bound_directory_chain(root, path.parent) as parent:
            try:
                if parent.descriptor is not None:
                    before = os.stat(
                        path.name,
                        dir_fd=parent.descriptor,
                        follow_symlinks=False,
                    )
                else:
                    before = os.stat(path, follow_symlinks=False)
            except FileNotFoundError:
                if allow_absent:
                    return _FileSnapshot(
                        path,
                        None,
                        _absent_state(),
                        None,
                    )
                raise _SnapshotError("unavailable")
            if (
                not stat.S_ISREG(before.st_mode)
                or stat.S_ISLNK(before.st_mode)
                or _is_reparse(before)
            ):
                raise _SnapshotError("unsafe")
            if int(before.st_nlink) not in allowed_link_counts:
                raise _SnapshotError("unexpected_hardlink")
            if before.st_size > maximum_bytes:
                return _FileSnapshot(
                    path,
                    None,
                    _unavailable_state(
                        byte_count=int(before.st_size),
                        link_count=int(before.st_nlink),
                    ),
                    _identity(before),
                )
            with services._hold_bound_regular_file(
                parent,
                path,
                before,
            ) as binding:
                opened = os.fstat(binding.descriptor)
                if (
                    _identity(opened) != _identity(before)
                    or not stat.S_ISREG(opened.st_mode)
                    or int(opened.st_nlink) != int(before.st_nlink)
                    or int(opened.st_nlink) not in allowed_link_counts
                    or opened.st_size > maximum_bytes
                ):
                    raise _SnapshotError("unavailable")
                os.lseek(binding.descriptor, 0, os.SEEK_SET)
                remaining = int(opened.st_size)
                chunks: list[bytes] = []
                while remaining:
                    chunk = os.read(
                        binding.descriptor,
                        min(remaining, 1024 * 1024),
                    )
                    if not chunk:
                        raise _SnapshotError("unavailable")
                    chunks.append(chunk)
                    remaining -= len(chunk)
                raw = b"".join(chunks)
                if os.read(binding.descriptor, 1):
                    raise _SnapshotError("unavailable")
                after = os.fstat(binding.descriptor)
                if (
                    _identity(after) != _identity(opened)
                    or after.st_size != len(raw)
                    or int(after.st_nlink) != int(opened.st_nlink)
                    or int(after.st_nlink) not in allowed_link_counts
                ):
                    raise _SnapshotError("unavailable")
    except _SnapshotError:
        raise
    except (OSError, ValueError) as exc:
        raise _SnapshotError("unavailable") from exc
    try:
        row_count = classify(raw)
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        state = _present_invalid_state(raw, int(before.st_nlink))
    else:
        state = _present_state(raw, row_count, int(before.st_nlink))
    return _FileSnapshot(path, raw, state, _identity(before))


def _classify_stored_document(
    raw: bytes,
    validator: Any,
    semantic_validator: Any | None = None,
) -> tuple[int, dict[str, Any]]:
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise ValueError
    document = _strict_json(raw[:-1])
    if raw != contract.stored_json_bytes(document):
        raise ValueError
    if not validator(document)["accepted"]:
        raise ValueError
    if semantic_validator is not None and not semantic_validator(document)[
        "accepted"
    ]:
        raise ValueError
    return 1, document


def _classify_object_manifest(
    raw: bytes,
    *,
    work: _ObjectManifestAuthorityWork | None = None,
) -> tuple[int, _ObjectManifestPrefixAuthority]:
    prefix_byte_counts = array("Q", [0])
    prefix_sha256_bytes = bytearray(hashlib.sha256(b"").digest())
    occurrences: dict[str, _ObjectManifestOccurrence] = {}
    if not raw:
        return (
            0,
            _ObjectManifestPrefixAuthority(
                row_count=0,
                prefix_byte_counts=prefix_byte_counts,
                prefix_sha256_bytes=prefix_sha256_bytes,
                object_occurrences=occurrences,
                parsed_byte_count=0,
            ),
        )
    if not raw.endswith(b"\n"):
        raise ValueError
    manifest_hasher = hashlib.sha256()
    parsed_byte_count = 0
    row_count = 0
    row_start = 0
    while row_start < len(raw):
        row_end = raw.find(b"\n", row_start)
        if row_end < 0:
            raise ValueError
        stored_line = raw[row_start : row_end + 1]
        row_start = row_end + 1
        if len(stored_line) > OBJECT_MANIFEST_MAX_ROW_BYTES:
            raise _SnapshotError("object_manifest_row_bytes_limit")
        if not stored_line.endswith(b"\n"):
            raise ValueError
        value = _strict_json(stored_line[:-1])
        if not isinstance(value, dict):
            raise ValueError
        if validate_schema(value, "object-manifest-entry.schema.json"):
            raise ValueError
        row_count += 1
        if row_count > OBJECT_MANIFEST_MAX_ROWS:
            raise _SnapshotError("object_manifest_rows_limit")
        parsed_byte_count += len(stored_line)
        manifest_hasher.update(stored_line)
        prefix_byte_counts.append(parsed_byte_count)
        prefix_sha256_bytes.extend(manifest_hasher.digest())
        object_id = value["object_id"]
        observed = occurrences.get(object_id)
        if observed is None:
            occurrences[object_id] = _ObjectManifestOccurrence(
                first_row_number=row_count,
                first_sha256=value["sha256"],
                second_row_number=None,
            )
        elif observed.second_row_number is None:
            occurrences[object_id] = _ObjectManifestOccurrence(
                first_row_number=observed.first_row_number,
                first_sha256=observed.first_sha256,
                second_row_number=row_count,
            )
        if work is not None:
            work.parsed_rows += 1
            work.parsed_bytes += len(stored_line)
    return (
        row_count,
        _ObjectManifestPrefixAuthority(
            row_count=row_count,
            prefix_byte_counts=prefix_byte_counts,
            prefix_sha256_bytes=prefix_sha256_bytes,
            object_occurrences=occurrences,
            parsed_byte_count=parsed_byte_count,
        ),
    )


def _classify_private_manifest(
    raw: bytes,
) -> tuple[int, list[dict[str, Any]], list[bytes]]:
    if not raw or not raw.endswith(b"\n"):
        raise ValueError
    rows: list[dict[str, Any]] = []
    stored_rows: list[bytes] = []
    for stored_line in raw.splitlines(keepends=True):
        if (
            len(stored_line) > PRIVATE_MANIFEST_MAX_ROW_BYTES
        ):
            raise _SnapshotError("private_manifest_row_bytes_limit")
        if not stored_line.endswith(b"\n"):
            raise ValueError
        value = _strict_json(stored_line[:-1])
        if (
            not isinstance(value, dict)
            or not private_metadata.validate_private_metadata_record(value)[
                "accepted"
            ]
            or stored_line != contract.stored_json_bytes(value)
        ):
            raise ValueError
        rows.append(value)
        stored_rows.append(stored_line)
        if len(rows) > PRIVATE_MANIFEST_MAX_ROWS:
            raise _SnapshotError("private_manifest_rows_limit")
    return len(rows), rows, stored_rows


def _snapshot_absent_or_document(
    root: Path,
    relative: str,
    *,
    maximum_bytes: int,
    validator: Any,
    semantic_validator: Any | None = None,
    allowed_link_counts: tuple[int, ...] = (1,),
    over_limit_reason: str,
) -> tuple[_FileSnapshot, dict[str, Any] | None]:
    path = _safe_archive_path(root, relative, final_may_absent=True)
    if path is None:
        raise _SnapshotError("unsafe")
    document: dict[str, Any] | None = None

    def classify(raw: bytes) -> int:
        nonlocal document
        count, value = _classify_stored_document(
            raw,
            validator,
            semantic_validator,
        )
        document = value
        return count

    snapshot = _read_regular_snapshot(
        root,
        path,
        maximum_bytes=maximum_bytes,
        allow_absent=True,
        classify=classify,
        allowed_link_counts=allowed_link_counts,
    )
    if (
        snapshot.state["state"] == "unavailable"
        and snapshot.state["byte_count"] is not None
        and snapshot.state["byte_count"] > maximum_bytes
    ):
        raise _SnapshotError(over_limit_reason)
    return snapshot, document


def _directory_entry_count(root: Path, path: Path, maximum: int) -> int:
    from . import archive_services as services

    try:
        with services._bound_directory_chain(root, path) as binding:
            if binding.descriptor is not None:
                info = os.fstat(binding.descriptor)
            else:
                info = os.stat(path, follow_symlinks=False)
            if (
                not stat.S_ISDIR(info.st_mode)
                or stat.S_ISLNK(info.st_mode)
                or _is_reparse(info)
            ):
                raise _SnapshotError("directory_unsafe")
            count = 0
            with services._scan_bound_directory(binding) as entries:
                for _ in entries:
                    count += 1
                    if count > maximum:
                        break
            if binding.descriptor is not None:
                current = os.fstat(binding.descriptor)
            else:
                current = os.stat(path, follow_symlinks=False)
            if _identity(current) != _identity(info):
                raise _SnapshotError("directory_unavailable")
            return count
    except _SnapshotError:
        raise
    except OSError as exc:
        raise _SnapshotError("directory_unavailable") from exc


def _stored_row_bound_reasons(
    raw: bytes,
    *,
    maximum_rows: int,
    maximum_row_bytes: int,
    rows_reason: str,
    row_bytes_reason: str,
) -> list[str]:
    row_count = 0
    row_bytes_exceeded = False
    start = 0
    while True:
        end = raw.find(b"\n", start)
        if end < 0:
            break
        row_count += 1
        if end + 1 - start > maximum_row_bytes:
            row_bytes_exceeded = True
        start = end + 1
    reasons: list[str] = []
    if row_count > maximum_rows:
        reasons.append(rows_reason)
    if row_bytes_exceeded:
        reasons.append(row_bytes_reason)
    return reasons


def _safe_stat_size(
    root: Path,
    relative: str,
) -> int | None:
    path = _safe_archive_path(root, relative, final_may_absent=True)
    if path is None:
        return None
    try:
        info = os.lstat(path)
    except (FileNotFoundError, OSError):
        return None
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_ISLNK(info.st_mode)
        or _is_reparse(info)
    ):
        return None
    return int(info.st_size)


def _collect_current_bound_reasons(
    root: Path,
    *,
    receipt_relative_path: str,
    owned_temp_relative_paths: list[str],
) -> list[str]:
    """Collect independently observable current bounds in normative order.

    This is a read-only preflight.  It deliberately ignores unsafe or
    unavailable authority here; the exact authority readers below retain those
    higher-precedence classifications.  Safely observed bounds are collected
    together instead of whichever filesystem family happened to be visited
    first.
    """

    observed: list[str] = []

    manifest_profiles = (
        (
            contract.OBJECT_MANIFEST_PATH,
            OBJECT_MANIFEST_MAX_BYTES,
            OBJECT_MANIFEST_MAX_ROWS,
            OBJECT_MANIFEST_MAX_ROW_BYTES,
            False,
            "object_manifest_bytes_limit",
            "object_manifest_rows_limit",
            "object_manifest_row_bytes_limit",
        ),
        (
            contract.PRIVATE_MANIFEST_PATH,
            PRIVATE_MANIFEST_MAX_BYTES,
            PRIVATE_MANIFEST_MAX_ROWS,
            PRIVATE_MANIFEST_MAX_ROW_BYTES,
            True,
            "private_manifest_bytes_limit",
            "private_manifest_rows_limit",
            "private_manifest_row_bytes_limit",
        ),
    )
    for (
        relative,
        maximum_bytes,
        maximum_rows,
        maximum_row_bytes,
        allow_absent,
        bytes_reason,
        rows_reason,
        row_bytes_reason,
    ) in manifest_profiles:
        path = _safe_archive_path(
            root,
            relative,
            final_may_absent=allow_absent,
        )
        if path is None:
            continue
        try:
            snapshot = _read_regular_snapshot(
                root,
                path,
                maximum_bytes=maximum_bytes,
                allow_absent=allow_absent,
                classify=lambda _: 0,
            )
        except _SnapshotError:
            continue
        byte_count = snapshot.state.get("byte_count")
        if (
            snapshot.state.get("state") == "unavailable"
            and type(byte_count) is int
            and byte_count > maximum_bytes
        ):
            observed.append(bytes_reason)
            continue
        if snapshot.raw is not None:
            observed.extend(
                _stored_row_bound_reasons(
                    snapshot.raw,
                    maximum_rows=maximum_rows,
                    maximum_row_bytes=maximum_row_bytes,
                    rows_reason=rows_reason,
                    row_bytes_reason=row_bytes_reason,
                )
            )

    receipt_directory = (
        root / "receipts" / "objects" / "private-source-metadata"
    )
    receipt_count = 0
    receipt_total_bytes = 0
    receipt_entries = 0
    try:
        if receipt_directory.exists():
            from . import archive_services as services

            with services._bound_directory_chain(
                root,
                receipt_directory,
            ) as binding:
                with services._scan_bound_directory(binding) as entries:
                    for entry in entries:
                        receipt_entries += 1
                        entry_bound_exceeded = (
                            receipt_entries
                            > PRIVATE_RECEIPT_DIR_MAX_ENTRIES
                        )
                        if (
                            entry.is_symlink()
                            or not entry.is_file(follow_symlinks=False)
                            or _RECEIPT_BASENAME_RE.fullmatch(entry.name)
                            is None
                        ):
                            if entry_bound_exceeded:
                                break
                            continue
                        try:
                            item_stat = entry.stat(follow_symlinks=False)
                        except OSError:
                            if entry_bound_exceeded:
                                break
                            continue
                        if _is_reparse(item_stat):
                            if entry_bound_exceeded:
                                break
                            continue
                        item_size = int(item_stat.st_size)
                        receipt_count += 1
                        receipt_total_bytes += item_size
                        if item_size > PRIVATE_RECEIPT_MAX_BYTES:
                            observed.append("receipt_bytes_limit")
                        if entry_bound_exceeded:
                            break
    except (OSError, ValueError):
        pass
    if receipt_count > PRIVATE_RECEIPT_MAX_COUNT:
        observed.append("receipt_count_limit")
    if receipt_total_bytes > PRIVATE_RECEIPT_TOTAL_BYTES_MAX:
        observed.append("receipt_total_bytes_limit")
    if receipt_entries > PRIVATE_RECEIPT_DIR_MAX_ENTRIES:
        observed.append("receipt_directory_entries_limit")

    for relative in (receipt_relative_path, owned_temp_relative_paths[2]):
        item_size = _safe_stat_size(root, relative)
        if (
            item_size is not None
            and item_size > PRIVATE_RECEIPT_MAX_BYTES
        ):
            observed.append("receipt_bytes_limit")

    for relative in (
        "receipts",
        "receipts/objects",
    ):
        path = root.joinpath(*PurePosixPath(relative).parts)
        try:
            if path.exists() and (
                _directory_entry_count(
                    root,
                    path,
                    PRIVATE_RECEIPT_ANCESTOR_DIR_MAX_ENTRIES,
                )
                > PRIVATE_RECEIPT_ANCESTOR_DIR_MAX_ENTRIES
            ):
                observed.append(
                    "receipt_ancestor_directory_entries_limit"
                )
        except _SnapshotError:
            pass

    manifests_directory = root / "objects" / "manifests"
    try:
        if (
            _directory_entry_count(
                root,
                manifests_directory,
                PRIVATE_MANIFEST_DIR_MAX_ENTRIES,
            )
            > PRIVATE_MANIFEST_DIR_MAX_ENTRIES
        ):
            observed.append("manifest_directory_entries_limit")
    except _SnapshotError:
        pass

    for relative in (
        contract.JOURNAL_PATH,
        owned_temp_relative_paths[0],
    ):
        item_size = _safe_stat_size(root, relative)
        if (
            item_size is not None
            and item_size > PRIVATE_JOURNAL_MAX_BYTES
        ):
            observed.append("journal_bytes_limit")
    manifest_temp_size = _safe_stat_size(
        root,
        owned_temp_relative_paths[1],
    )
    if (
        manifest_temp_size is not None
        and manifest_temp_size > PRIVATE_MANIFEST_MAX_BYTES
    ):
        observed.append("private_manifest_bytes_limit")

    return _ordered_current_bound_internal_reasons(observed)


def _observe_receipt_directory_chain(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    relatives = (
        "receipts",
        "receipts/objects",
        "receipts/objects/private-source-metadata",
    )
    states: list[dict[str, Any]] = []
    absent_seen = False
    for relative in relatives:
        path = root.joinpath(*PurePosixPath(relative).parts)
        if absent_seen:
            if path.exists():
                raise _SnapshotError("directory_chain_impossible")
            states.append({"state": "absent", "entry_count": 0})
            continue
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            absent_seen = True
            states.append({"state": "absent", "entry_count": 0})
            continue
        except OSError as exc:
            raise _SnapshotError("directory_unavailable") from exc
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or _is_reparse(info)
        ):
            raise _SnapshotError("directory_unsafe")
        maximum_entries = (
            PRIVATE_RECEIPT_DIR_MAX_ENTRIES
            if relative == "receipts/objects/private-source-metadata"
            else PRIVATE_RECEIPT_ANCESTOR_DIR_MAX_ENTRIES
        )
        entry_count = _directory_entry_count(
            root,
            path,
            maximum_entries,
        )
        if entry_count > maximum_entries:
            raise _SnapshotError(
                "receipt_directory_entries_limit"
                if relative
                == "receipts/objects/private-source-metadata"
                else "receipt_ancestor_directory_entries_limit"
            )
        states.append(
            {
                "state": "present",
                "entry_count": entry_count,
            }
        )

    before = {
        "receipts_root": states[0],
        "objects_parent": states[1],
        "private_receipt_directory": states[2],
    }
    after = deepcopy(before)
    if states[0]["state"] == "absent":
        after = {
            "receipts_root": {"state": "present", "entry_count": 1},
            "objects_parent": {"state": "present", "entry_count": 1},
            "private_receipt_directory": {
                "state": "present",
                "entry_count": 0,
            },
        }
    elif states[1]["state"] == "absent":
        after["receipts_root"]["entry_count"] += 1
        after["objects_parent"] = {"state": "present", "entry_count": 1}
        after["private_receipt_directory"] = {
            "state": "present",
            "entry_count": 0,
        }
    elif states[2]["state"] == "absent":
        after["objects_parent"]["entry_count"] += 1
        after["private_receipt_directory"] = {
            "state": "present",
            "entry_count": 0,
        }
    return before, after


def _receipt_directory_chain_complete(
    chain: dict[str, Any],
) -> bool:
    return all(
        chain[key]["state"] == "present"
        for key in (
            "receipts_root",
            "objects_parent",
            "private_receipt_directory",
        )
    )


def _safe_archive_id(raw_archive_id: Any, safe_projection: Any) -> str | None:
    if (
        type(raw_archive_id) is not str
        or not 1 <= len(raw_archive_id) <= 200
        or _contains_surrogate(raw_archive_id)
        or safe_projection(raw_archive_id) != raw_archive_id
    ):
        return None
    return raw_archive_id


def _reviewed_by_valid(value: Any, safe_projection: Any) -> bool:
    if (
        type(value) is not str
        or not value.isascii()
        or not 10 <= len(value.encode("ascii")) <= 200
        or _REVIEWED_BY_RE.fullmatch(value) is None
        or safe_projection(value) != value
    ):
        return False
    return True


def _observe_object_manifest(
    root: Path,
    object_id: str,
    *,
    work: _ObjectManifestAuthorityWork | None = None,
) -> tuple[_FileSnapshot, _ObjectManifestPrefixAuthority, int]:
    path = _safe_archive_path(
        root,
        contract.OBJECT_MANIFEST_PATH,
        final_may_absent=False,
    )
    if path is None:
        raise _SnapshotError("authority_path_unsafe")
    prefix_authority: _ObjectManifestPrefixAuthority | None = None

    def classify(raw: bytes) -> int:
        nonlocal prefix_authority
        count, authority = _classify_object_manifest(raw, work=work)
        prefix_authority = authority
        return count

    snapshot = _read_regular_snapshot(
        root,
        path,
        maximum_bytes=OBJECT_MANIFEST_MAX_BYTES,
        allow_absent=False,
        classify=classify,
    )
    if (
        snapshot.state["state"] == "unavailable"
        and snapshot.state["byte_count"] is not None
        and snapshot.state["byte_count"] > OBJECT_MANIFEST_MAX_BYTES
    ):
        raise _SnapshotError("object_manifest_bytes_limit")
    if snapshot.state["state"] != "present":
        raise _SnapshotError("authority_state_invalid")
    if (
        prefix_authority is None
        or not _object_manifest_state_is_exact_historical_prefix(
            snapshot,
            snapshot.state,
            prefix_authority=prefix_authority,
            object_id=object_id,
            work=work,
        )
    ):
        raise _SnapshotError("authority_state_invalid")
    return snapshot, prefix_authority, 1


def _observe_private_manifest(
    root: Path,
) -> tuple[_FileSnapshot, list[dict[str, Any]], list[bytes]]:
    path = _safe_archive_path(
        root,
        contract.PRIVATE_MANIFEST_PATH,
        final_may_absent=True,
    )
    if path is None:
        raise _SnapshotError("authority_path_unsafe")
    rows: list[dict[str, Any]] = []
    stored_rows: list[bytes] = []

    def classify(raw: bytes) -> int:
        nonlocal rows, stored_rows
        count, values, stored = _classify_private_manifest(raw)
        rows = values
        stored_rows = stored
        return count

    snapshot = _read_regular_snapshot(
        root,
        path,
        maximum_bytes=PRIVATE_MANIFEST_MAX_BYTES,
        allow_absent=True,
        classify=classify,
    )
    if (
        snapshot.state["state"] == "unavailable"
        and snapshot.state["byte_count"] is not None
        and snapshot.state["byte_count"] > PRIVATE_MANIFEST_MAX_BYTES
    ):
        raise _SnapshotError("private_manifest_bytes_limit")
    if snapshot.state["state"] not in {"absent", "present"}:
        raise _SnapshotError("authority_state_invalid")
    return snapshot, rows, stored_rows


def _observe_journal(
    root: Path,
) -> tuple[_FileSnapshot, dict[str, Any] | None]:
    return _snapshot_absent_or_document(
        root,
        contract.JOURNAL_PATH,
        maximum_bytes=PRIVATE_JOURNAL_MAX_BYTES,
        validator=contract.validate_private_metadata_write_journal,
        allowed_link_counts=(1, 2),
        over_limit_reason="journal_bytes_limit",
    )


def _observe_receipt(
    root: Path,
    relative: str,
) -> tuple[_FileSnapshot, dict[str, Any] | None]:
    return _snapshot_absent_or_document(
        root,
        relative,
        maximum_bytes=PRIVATE_RECEIPT_MAX_BYTES,
        validator=contract.validate_private_metadata_write_receipt,
        allowed_link_counts=(1, 2),
        over_limit_reason="receipt_bytes_limit",
    )


def _observe_owned_temps(
    root: Path,
    relatives: list[str],
) -> tuple[dict[str, _FileSnapshot], dict[str, dict[str, Any] | None]]:
    snapshots: dict[str, _FileSnapshot] = {}
    documents: dict[str, dict[str, Any] | None] = {}
    keys = ("journal_temp", "manifest_temp", "receipt_temp")
    for key, relative in zip(keys, relatives):
        path = _safe_archive_path(root, relative, final_may_absent=True)
        if path is None:
            raise _SnapshotError("authority_path_unsafe")
        document: dict[str, Any] | None = None
        if key == "journal_temp":

            def classify(raw: bytes) -> int:
                nonlocal document
                count, value = _classify_stored_document(
                    raw,
                    contract.validate_private_metadata_write_journal,
                )
                document = value
                return count

            maximum = PRIVATE_JOURNAL_MAX_BYTES
        elif key == "manifest_temp":

            def classify(raw: bytes) -> int:
                count, _, _ = _classify_private_manifest(raw)
                return count

            maximum = PRIVATE_MANIFEST_MAX_BYTES
        else:

            def classify(raw: bytes) -> int:
                nonlocal document
                count, value = _classify_stored_document(
                    raw,
                    contract.validate_private_metadata_write_receipt,
                )
                document = value
                return count

            maximum = PRIVATE_RECEIPT_MAX_BYTES
        snapshot = _read_regular_snapshot(
            root,
            path,
            maximum_bytes=maximum,
            allow_absent=True,
            classify=classify,
            allowed_link_counts=(
                (1, 2)
                if key in {"journal_temp", "receipt_temp"}
                else (1,)
            ),
        )
        if (
            snapshot.state["state"] == "unavailable"
            and snapshot.state["byte_count"] is not None
            and snapshot.state["byte_count"] > maximum
        ):
            raise _SnapshotError(
                {
                    "journal_temp": "journal_bytes_limit",
                    "manifest_temp": "private_manifest_bytes_limit",
                    "receipt_temp": "receipt_bytes_limit",
                }[key]
            )
        snapshots[key] = snapshot
        documents[key] = document
    return snapshots, documents


def _inventory_receipt_directory(
    root: Path,
    chain_before: dict[str, Any],
    *,
    allowed_temp_basename: str,
) -> tuple[list[tuple[str, int]], int, list[str]]:
    from . import archive_services as services

    directory_state = chain_before["private_receipt_directory"]
    if directory_state["state"] == "absent":
        return [], 0, []
    directory = root / "receipts" / "objects" / "private-source-metadata"
    inventory: list[tuple[str, int]] = []
    unexpected: list[str] = []
    entries_seen = 0
    receipt_total_bytes = 0
    try:
        with services._bound_directory_chain(root, directory) as binding:
            with services._scan_bound_directory(binding) as entries:
                for entry in entries:
                    entries_seen += 1
                    if entries_seen > PRIVATE_RECEIPT_DIR_MAX_ENTRIES:
                        break
                    try:
                        if (
                            entry.is_symlink()
                            or not entry.is_file(follow_symlinks=False)
                        ):
                            unexpected.append(entry.name)
                            continue
                        item_stat = entry.stat(follow_symlinks=False)
                    except OSError as exc:
                        raise _SnapshotError(
                            "directory_unavailable"
                        ) from exc
                    if (
                        getattr(item_stat, "st_file_attributes", 0)
                        & _WINDOWS_REPARSE_ATTRIBUTE
                    ):
                        unexpected.append(entry.name)
                        continue
                    if _RECEIPT_BASENAME_RE.fullmatch(entry.name):
                        item_size = int(item_stat.st_size)
                        if item_size > PRIVATE_RECEIPT_MAX_BYTES:
                            raise _SnapshotError("receipt_bytes_limit")
                        inventory.append(
                            (entry.name, item_size)
                        )
                        if len(inventory) > PRIVATE_RECEIPT_MAX_COUNT:
                            raise _SnapshotError("receipt_count_limit")
                        receipt_total_bytes += item_size
                        if (
                            receipt_total_bytes
                            > PRIVATE_RECEIPT_TOTAL_BYTES_MAX
                        ):
                            raise _SnapshotError(
                                "receipt_total_bytes_limit"
                            )
                    elif entry.name != allowed_temp_basename:
                        unexpected.append(entry.name)
    except _SnapshotError:
        raise
    except OSError as exc:
        raise _SnapshotError("directory_unavailable") from exc
    return sorted(inventory), entries_seen, sorted(unexpected)


def _historical_manifest_state(
    raw: bytes,
    row_count: int,
) -> dict[str, Any]:
    if not raw:
        return _absent_state()
    return _present_state(raw, row_count, 1)


def _object_manifest_historical_state(
    prefix_authority: _ObjectManifestPrefixAuthority,
    row_count: int,
) -> dict[str, Any]:
    if not 1 <= row_count <= prefix_authority.row_count:
        raise ValueError("object manifest prefix row count out of range")
    digest_start = row_count * 32
    return {
        "state": "present",
        "sha256": (
            "sha256:"
            + prefix_authority.prefix_sha256_bytes[
                digest_start : digest_start + 32
            ].hex()
        ),
        "byte_count": prefix_authority.prefix_byte_counts[row_count],
        "row_count": row_count,
        "link_count": 1,
    }


def _object_manifest_state_is_exact_historical_prefix(
    object_manifest: _FileSnapshot,
    historical_state: Any,
    *,
    prefix_authority: _ObjectManifestPrefixAuthority,
    object_id: str,
    work: _ObjectManifestAuthorityWork | None = None,
) -> bool:
    if work is not None:
        work.prefix_lookups += 1
        work.prefix_lookup_units += 1
    raw = object_manifest.raw
    if (
        raw is None
        or object_manifest.state.get("state") != "present"
        or object_manifest.state.get("link_count") != 1
        or type(historical_state) is not dict
        or historical_state.get("state") != "present"
        or historical_state.get("link_count") != 1
    ):
        return False
    byte_count = historical_state.get("byte_count")
    row_count = historical_state.get("row_count")
    if (
        type(byte_count) is not int
        or type(row_count) is not int
        or byte_count <= 0
        or row_count <= 0
        or row_count > prefix_authority.row_count
        or len(prefix_authority.prefix_byte_counts)
        != prefix_authority.row_count + 1
        or len(prefix_authority.prefix_sha256_bytes)
        != 32 * (prefix_authority.row_count + 1)
        or prefix_authority.parsed_byte_count != len(raw)
        or prefix_authority.prefix_byte_counts[-1] != len(raw)
        or object_manifest.state.get("row_count")
        != prefix_authority.row_count
        or object_manifest.state.get("byte_count") != len(raw)
    ):
        return False
    if object_manifest.state != _object_manifest_historical_state(
        prefix_authority,
        prefix_authority.row_count,
    ):
        return False
    if historical_state != _object_manifest_historical_state(
        prefix_authority,
        row_count,
    ):
        return False
    occurrence = prefix_authority.object_occurrences.get(object_id)
    if (
        occurrence is None
        or occurrence.first_row_number > row_count
        or occurrence.first_sha256 != object_id[7:]
        or occurrence.second_row_number is not None
    ):
        return False
    return True


def _journal_private_transition_matches_current(
    private_manifest: _FileSnapshot,
    *,
    stored_row: bytes,
    expected_before: Any,
    expected_after: Any,
) -> bool:
    if type(expected_before) is not dict or type(expected_after) is not dict:
        return False
    current_raw = private_manifest.raw or b""
    current_rows = int(private_manifest.state.get("row_count") or 0)
    if private_manifest.state == expected_before:
        return expected_after == _historical_manifest_state(
            current_raw + stored_row,
            current_rows + 1,
        )
    if (
        private_manifest.state != expected_after
        or not current_raw.endswith(stored_row)
        or current_rows < 1
    ):
        return False
    before_raw = current_raw[: -len(stored_row)]
    return expected_before == _historical_manifest_state(
        before_raw,
        current_rows - 1,
    )


def _receipt_matches_current_authority(
    document: dict[str, Any],
    *,
    archive_id: str,
    row: dict[str, Any],
    object_manifest: _FileSnapshot,
    object_manifest_prefix_authority: _ObjectManifestPrefixAuthority,
    object_manifest_authority_work: (
        _ObjectManifestAuthorityWork | None
    ) = None,
) -> bool:
    historical_object_state = document.get("object_manifest_state")
    return bool(
        _object_manifest_state_is_exact_historical_prefix(
            object_manifest,
            historical_object_state,
            prefix_authority=object_manifest_prefix_authority,
            object_id=row["object_id"],
            work=object_manifest_authority_work,
        )
        and contract.validate_private_metadata_write_receipt_semantics(
            document,
            expected_archive_id=archive_id,
            expected_object_manifest_state=historical_object_state,
        )["accepted"]
    )


def _journal_matches_current_authority(
    document: dict[str, Any],
    *,
    archive_id: str,
    intake_sha256: str,
    row: dict[str, Any],
    stored_row: bytes,
    object_manifest: _FileSnapshot,
    object_manifest_prefix_authority: _ObjectManifestPrefixAuthority,
    private_manifest: _FileSnapshot,
    object_manifest_authority_work: (
        _ObjectManifestAuthorityWork | None
    ) = None,
) -> bool:
    historical_object_state = document.get("object_manifest_state")
    expected_before = document.get("private_manifest_before")
    expected_after = document.get("private_manifest_after")
    return bool(
        _object_manifest_state_is_exact_historical_prefix(
            object_manifest,
            historical_object_state,
            prefix_authority=object_manifest_prefix_authority,
            object_id=row["object_id"],
            work=object_manifest_authority_work,
        )
        and _journal_private_transition_matches_current(
            private_manifest,
            stored_row=stored_row,
            expected_before=expected_before,
            expected_after=expected_after,
        )
        and contract.validate_private_metadata_write_journal_semantics(
            document,
            canonical_row=row,
            expected_archive_id=archive_id,
            expected_intake_sha256=intake_sha256,
            expected_object_manifest_state=historical_object_state,
            expected_private_manifest_before=expected_before,
            expected_private_manifest_after=expected_after,
        )["accepted"]
    )


def _parse_receipt_at_path(
    root: Path,
    relative: str,
    row: dict[str, Any],
    *,
    allowed_publication_twin_identity: tuple[int, int] | None = None,
    archive_id: str | None = None,
    object_manifest: _FileSnapshot | None = None,
    object_manifest_prefix_authority: (
        _ObjectManifestPrefixAuthority | None
    ) = None,
    object_manifest_authority_work: (
        _ObjectManifestAuthorityWork | None
    ) = None,
    expected_private_manifest_before: dict[str, Any] | None = None,
    expected_private_manifest_after: dict[str, Any] | None = None,
) -> tuple[_FileSnapshot, dict[str, Any]]:
    try:
        observation_digest = row["source_provenance"][
            "observation_evidence_sha256"
        ]
        derived_authority_key = contract.authority_key_sha256(
            observation_digest
        )
        derived_relative = contract.receipt_relative_path(
            derived_authority_key
        )
        expected_path = _safe_archive_path(
            root,
            derived_relative,
            final_may_absent=True,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise _SnapshotError("authority_state_invalid") from exc
    if relative != derived_relative or expected_path is None:
        raise _SnapshotError("receipt_semantic_mismatch")
    snapshot, document = _observe_receipt(root, relative)
    if snapshot.state["state"] == "absent":
        raise _SnapshotError("orphan_or_missing_receipt")
    if (
        snapshot.path != expected_path
        or snapshot.state["state"] != "present"
        or (
            snapshot.state["link_count"] != 1
            and not (
                snapshot.state["link_count"] == 2
                and snapshot.identity
                == allowed_publication_twin_identity
            )
        )
        or document is None
    ):
        raise _SnapshotError("authority_state_invalid")
    if (
        document.get("authority_key_sha256") != derived_authority_key
        or document.get("observation_evidence_sha256") != observation_digest
        or document.get("plan_binding", {}).get("authority_key_sha256")
        != derived_authority_key
        or document.get("plan_binding", {}).get("receipt_relative_path")
        != derived_relative
        or (
            object_manifest is not None
            and object_manifest_prefix_authority is not None
            and not _object_manifest_state_is_exact_historical_prefix(
                object_manifest,
                document.get("object_manifest_state"),
                prefix_authority=object_manifest_prefix_authority,
                object_id=row["object_id"],
                work=object_manifest_authority_work,
            )
        )
        or contract.validate_private_metadata_write_receipt_semantics(
            document,
            canonical_row=row,
            expected_archive_id=archive_id,
            expected_object_manifest_state=(
                document.get("object_manifest_state")
                if (
                    object_manifest is not None
                    and object_manifest_prefix_authority is not None
                )
                else None
            ),
            expected_private_manifest_before=(
                expected_private_manifest_before
            ),
            expected_private_manifest_after=expected_private_manifest_after,
        )["accepted"]
        is not True
    ):
        raise _SnapshotError("receipt_semantic_mismatch")
    return snapshot, document


def _build_complete_authority_chain(
    root: Path,
    rows: list[dict[str, Any]],
    stored_rows: list[bytes],
    *,
    private_manifest_state: dict[str, Any],
    inventory: list[tuple[str, int]],
    allowed_receipt_twin_relative: str | None = None,
    allowed_receipt_twin_identity: tuple[int, int] | None = None,
    capture_receipt_relative: str | None = None,
    archive_id: str | None = None,
    object_manifest: _FileSnapshot | None = None,
    object_manifest_prefix_authority: (
        _ObjectManifestPrefixAuthority | None
    ) = None,
    object_manifest_authority_work: (
        _ObjectManifestAuthorityWork | None
    ) = None,
) -> tuple[dict[str, Any], str, dict[str, dict[str, Any]]]:
    entries: list[dict[str, Any]] = []
    captured_receipts: dict[str, dict[str, Any]] = {}
    expected_names: list[str] = []
    observed_evidence_digests: set[str] = set()
    observed_canonical_row_digests: set[str] = set()
    manifest_hasher = hashlib.sha256()
    manifest_byte_count = 0
    chain_entries_hasher = hashlib.sha256()
    chain_entries_hasher.update(b'{"entries":[')

    def historical_manifest_state(row_count: int) -> dict[str, Any]:
        if row_count == 0:
            return _absent_state()
        return {
            "state": "present",
            "sha256": "sha256:" + manifest_hasher.copy().hexdigest(),
            "byte_count": manifest_byte_count,
            "row_count": row_count,
            "link_count": 1,
        }

    def authority_chain_digest(
        state: dict[str, Any],
    ) -> str:
        digest = chain_entries_hasher.copy()
        digest.update(b'],"private_manifest_state":')
        digest.update(contract.canonical_json_bytes(state))
        digest.update(b',"schema":')
        digest.update(
            contract.canonical_json_bytes(contract.AUTHORITY_CHAIN_SCHEMA)
        )
        digest.update(b"}")
        return "sha256:" + digest.hexdigest()

    for row_number, (row, stored_row) in enumerate(
        zip(rows, stored_rows),
        start=1,
    ):
        observation_digest = row["source_provenance"][
            "observation_evidence_sha256"
        ]
        canonical_row_digest = contract.sha256_digest(
            contract.canonical_json_bytes(row)
        )
        if (
            observation_digest in observed_evidence_digests
            or canonical_row_digest in observed_canonical_row_digests
        ):
            raise _SnapshotError("duplicate_authority_identity")
        observed_evidence_digests.add(observation_digest)
        observed_canonical_row_digests.add(canonical_row_digest)
        authority_key = contract.authority_key_sha256(observation_digest)
        relative = contract.receipt_relative_path(authority_key)
        expected_names.append(PurePosixPath(relative).name)
        before = historical_manifest_state(row_number - 1)
        manifest_hasher.update(stored_row)
        manifest_byte_count += len(stored_row)
        after = historical_manifest_state(row_number)
        receipt_snapshot, receipt = _parse_receipt_at_path(
            root,
            relative,
            row,
            allowed_publication_twin_identity=(
                allowed_receipt_twin_identity
                if relative == allowed_receipt_twin_relative
                else None
            ),
            archive_id=archive_id,
            object_manifest=object_manifest,
            object_manifest_prefix_authority=(
                object_manifest_prefix_authority
            ),
            object_manifest_authority_work=(
                object_manifest_authority_work
            ),
            expected_private_manifest_before=before,
            expected_private_manifest_after=after,
        )
        prefix_chain_sha256 = authority_chain_digest(before)
        if (
            receipt["authority_chain_before_sha256"]
            != prefix_chain_sha256
            or receipt["plan_binding"]["authority_chain_sha256"]
            != prefix_chain_sha256
        ):
            raise _SnapshotError("receipt_semantic_mismatch")
        if (
            receipt["private_manifest_before"] != before
            or receipt["private_manifest_after"] != after
            or receipt["authority_chain_before_sha256"]
            != receipt["plan_binding"]["authority_chain_sha256"]
        ):
            raise _SnapshotError("receipt_semantic_mismatch")
        entry = {
            "row_number": row_number,
            "intake_sha256": receipt["intake_sha256"],
            "canonical_row_sha256": receipt["canonical_row_sha256"],
            "observation_evidence_sha256": observation_digest,
            "review_evidence_sha256": receipt["review_evidence_sha256"],
            "authority_key_sha256": authority_key,
            "receipt_relative_path": relative,
            "receipt_sha256": receipt_snapshot.state["sha256"],
            "manifest_before": before,
            "manifest_after": after,
        }
        entries.append(entry)
        if row_number > 1:
            chain_entries_hasher.update(b",")
        chain_entries_hasher.update(contract.canonical_json_bytes(entry))
        if relative == capture_receipt_relative:
            captured_receipts[relative] = receipt
    actual_names = [name for name, _ in inventory]
    if sorted(expected_names) != sorted(actual_names):
        raise _SnapshotError("orphan_or_missing_receipt")
    if historical_manifest_state(len(rows)) != private_manifest_state:
        raise _SnapshotError("authority_state_invalid")
    authority_chain = {
        "schema": contract.AUTHORITY_CHAIN_SCHEMA,
        "private_manifest_state": private_manifest_state,
        "entries": entries,
    }
    if not contract.validate_private_metadata_authority_chain_semantics(
        authority_chain
    )["accepted"]:
        raise _SnapshotError("authority_state_invalid")
    return (
        authority_chain,
        authority_chain_digest(private_manifest_state),
        captured_receipts,
    )


def _journal_matches_incoming(
    journal: dict[str, Any] | None,
    *,
    row: dict[str, Any],
    intake_sha256: str,
    canonical_row_sha256: str,
    authority_key_sha256: str,
) -> bool:
    if journal is None:
        return False
    if not contract.validate_private_metadata_write_journal_semantics(
        journal,
        canonical_row=row,
    )["accepted"]:
        return False
    receipt = journal["receipt_document"]
    return bool(
        journal["authority_key_sha256"] == authority_key_sha256
        and receipt["intake_sha256"] == intake_sha256
        and receipt["canonical_row_sha256"] == canonical_row_sha256
    )


def _classify_current_action(
    *,
    private_manifest: _FileSnapshot,
    private_rows: list[dict[str, Any]],
    row: dict[str, Any],
    canonical_row_sha256: str,
    intake_sha256: str,
    review_evidence_sha256: str,
    authority_key_sha256: str,
    receipt: _FileSnapshot,
    receipt_document: dict[str, Any] | None,
    journal: _FileSnapshot,
    journal_document: dict[str, Any] | None,
    temp_snapshots: dict[str, _FileSnapshot],
    temp_documents: dict[str, dict[str, Any] | None],
) -> tuple[str, list[str], str, str, int, int, str | None]:
    def result(
        action: str,
        reasons: list[str],
        *,
        prior_state: str,
        inventory_state: str,
        row_count: int,
        receipt_count: int,
        planned_receipt_sha256: str | None,
    ) -> tuple[str, list[str], str, str, int, int, str | None]:
        return (
            action,
            reasons,
            prior_state,
            inventory_state,
            row_count,
            receipt_count,
            planned_receipt_sha256,
        )

    def is_absent(snapshot: _FileSnapshot) -> bool:
        return bool(
            snapshot.raw is None
            and snapshot.identity is None
            and snapshot.state == _absent_state()
        )

    def has_consistent_bytes(
        snapshot: _FileSnapshot,
        *,
        link_count: int,
    ) -> bool:
        raw = snapshot.raw
        if raw is None or snapshot.identity is None:
            return False
        if snapshot.state.get("state") == "present":
            row_count = snapshot.state.get("row_count")
            if type(row_count) is not int or row_count < 1:
                return False
            expected = _present_state(raw, row_count, link_count)
        elif snapshot.state.get("state") == "present_invalid":
            expected = _present_invalid_state(raw, link_count)
        else:
            return False
        return snapshot.state == expected

    def is_exact_document(
        snapshot: _FileSnapshot,
        document: dict[str, Any] | None,
        *,
        link_count: int,
    ) -> bool:
        if document is None:
            return False
        raw = contract.stored_json_bytes(document)
        return bool(
            snapshot.raw == raw
            and snapshot.state == _present_state(raw, 1, link_count)
            and snapshot.identity is not None
        )

    def is_exact_manifest(
        snapshot: _FileSnapshot,
        expected: bytes,
        *,
        row_count: int,
    ) -> bool:
        return bool(
            snapshot.raw == expected
            and snapshot.state == _present_state(expected, row_count, 1)
            and snapshot.identity is not None
        )

    def is_strict_prefix(
        snapshot: _FileSnapshot,
        expected: bytes,
    ) -> bool:
        raw = snapshot.raw
        return bool(
            raw is not None
            and len(raw) < len(expected)
            and expected.startswith(raw)
            and has_consistent_bytes(snapshot, link_count=1)
        )

    def is_same_identity_twin(
        first: _FileSnapshot,
        first_document: dict[str, Any] | None,
        second: _FileSnapshot,
        second_document: dict[str, Any] | None,
    ) -> bool:
        return bool(
            first_document is not None
            and second_document is not None
            and first_document == second_document
            and is_exact_document(first, first_document, link_count=2)
            and is_exact_document(second, second_document, link_count=2)
            and first.identity == second.identity
        )

    def non_absent_link_count(snapshot: _FileSnapshot) -> int | None:
        if is_absent(snapshot):
            return None
        value = snapshot.state.get("link_count")
        return value if type(value) is int else -1

    observation_digest = row["source_provenance"][
        "observation_evidence_sha256"
    ]
    observation_rows = [
        existing
        for existing in private_rows
        if existing["source_provenance"]["observation_evidence_sha256"]
        == observation_digest
    ]
    exact_rows = [
        existing
        for existing in observation_rows
        if contract.sha256_digest(contract.canonical_json_bytes(existing))
        == canonical_row_sha256
    ]
    exact_count = len(exact_rows)
    if len(observation_rows) > 1:
        prior_row_state = "multiple"
    elif exact_count == 1:
        prior_row_state = "exact"
    elif observation_rows:
        prior_row_state = "collision"
    else:
        prior_row_state = "absent"

    receipt_absent = is_absent(receipt)
    receipt_present = not receipt_absent
    receipt_self_semantically_valid = bool(
        receipt.state.get("state") == "present"
        and receipt_document is not None
        and contract.validate_private_metadata_write_receipt_semantics(
            receipt_document,
        )["accepted"]
    )
    receipt_semantically_exact = bool(
        receipt_self_semantically_valid
        and receipt_document is not None
        and contract.validate_private_metadata_write_receipt_semantics(
            receipt_document,
            canonical_row=row,
        )["accepted"]
    )
    receipt_exact_link_one = bool(
        receipt_self_semantically_valid
        and is_exact_document(receipt, receipt_document, link_count=1)
    )
    receipt_exact_link_two = bool(
        receipt_self_semantically_valid
        and is_exact_document(receipt, receipt_document, link_count=2)
    )
    exact_receipt = receipt_exact_link_one or receipt_exact_link_two
    receipt_matches_incoming = bool(
        exact_receipt
        and receipt_semantically_exact
        and receipt_document is not None
        and receipt_document["intake_sha256"] == intake_sha256
        and receipt_document["review_evidence_sha256"]
        == review_evidence_sha256
    )
    if receipt_absent:
        receipt_inventory_state = "absent"
    elif exact_receipt:
        receipt_inventory_state = "exact"
    else:
        receipt_inventory_state = "conflicting"

    exact_journal = _journal_matches_incoming(
        journal_document,
        row=row,
        intake_sha256=intake_sha256,
        canonical_row_sha256=canonical_row_sha256,
        authority_key_sha256=authority_key_sha256,
    )
    if exact_journal and journal_document is not None:
        exact_journal = bool(
            journal_document["receipt_document"]["review_evidence_sha256"]
            == review_evidence_sha256
        )
    exact_journal_temp = _journal_matches_incoming(
        temp_documents["journal_temp"],
        row=row,
        intake_sha256=intake_sha256,
        canonical_row_sha256=canonical_row_sha256,
        authority_key_sha256=authority_key_sha256,
    )
    if exact_journal_temp and temp_documents["journal_temp"] is not None:
        exact_journal_temp = bool(
            temp_documents["journal_temp"]["receipt_document"][
                "review_evidence_sha256"
            ]
            == review_evidence_sha256
        )

    journal_absent = is_absent(journal)
    journal_temp_absent = is_absent(temp_snapshots["journal_temp"])
    manifest_temp_absent = is_absent(temp_snapshots["manifest_temp"])
    receipt_temp_absent = is_absent(temp_snapshots["receipt_temp"])

    fixed_journal_link_one = bool(
        exact_journal
        and is_exact_document(
            journal,
            journal_document,
            link_count=1,
        )
    )
    fixed_journal_link_two = bool(
        exact_journal
        and is_exact_document(
            journal,
            journal_document,
            link_count=2,
        )
    )
    journal_temp_link_one = bool(
        exact_journal_temp
        and is_exact_document(
            temp_snapshots["journal_temp"],
            temp_documents["journal_temp"],
            link_count=1,
        )
    )
    journal_twin = bool(
        exact_journal
        and exact_journal_temp
        and is_same_identity_twin(
            journal,
            journal_document,
            temp_snapshots["journal_temp"],
            temp_documents["journal_temp"],
        )
    )

    exact_receipt_temp_document = bool(
        temp_documents["receipt_temp"] is not None
        and contract.validate_private_metadata_write_receipt_semantics(
            temp_documents["receipt_temp"],
        )["accepted"]
    )
    receipt_twin = bool(
        receipt_self_semantically_valid
        and exact_receipt_temp_document
        and is_same_identity_twin(
            receipt,
            receipt_document,
            temp_snapshots["receipt_temp"],
            temp_documents["receipt_temp"],
        )
    )

    journal_pair_has_equal_bytes = bool(
        not journal_absent
        and not journal_temp_absent
        and journal.raw is not None
        and journal.raw == temp_snapshots["journal_temp"].raw
    )
    receipt_pair_has_equal_bytes = bool(
        not receipt_absent
        and not receipt_temp_absent
        and receipt.raw is not None
        and receipt.raw == temp_snapshots["receipt_temp"].raw
    )
    journal_pair_shares_identity = bool(
        not journal_absent
        and not journal_temp_absent
        and journal.identity is not None
        and journal.identity == temp_snapshots["journal_temp"].identity
    )
    receipt_pair_shares_identity = bool(
        not receipt_absent
        and not receipt_temp_absent
        and receipt.identity is not None
        and receipt.identity == temp_snapshots["receipt_temp"].identity
    )

    link_relationship_invalid = False
    for snapshot in (
        private_manifest,
        temp_snapshots["manifest_temp"],
    ):
        link_count = non_absent_link_count(snapshot)
        if link_count is not None and link_count != 1:
            link_relationship_invalid = True
    for snapshot in (
        journal,
        temp_snapshots["journal_temp"],
        receipt,
        temp_snapshots["receipt_temp"],
    ):
        link_count = non_absent_link_count(snapshot)
        if link_count is not None and link_count not in {1, 2}:
            link_relationship_invalid = True
    if (
        non_absent_link_count(journal) == 2
        or non_absent_link_count(temp_snapshots["journal_temp"]) == 2
    ) and not journal_twin:
        link_relationship_invalid = True
    if (
        non_absent_link_count(receipt) == 2
        or non_absent_link_count(temp_snapshots["receipt_temp"]) == 2
    ) and not receipt_twin:
        link_relationship_invalid = True
    if journal_pair_has_equal_bytes and not journal_twin:
        link_relationship_invalid = True
    if receipt_pair_has_equal_bytes and not receipt_twin:
        link_relationship_invalid = True
    if journal_pair_shares_identity and not journal_twin:
        link_relationship_invalid = True
    if receipt_pair_shares_identity and not receipt_twin:
        link_relationship_invalid = True

    planned_from_journal: str | None = None
    if exact_journal and journal_document is not None:
        planned_from_journal = journal_document["receipt_sha256"]
    elif exact_journal_temp and temp_documents["journal_temp"] is not None:
        planned_from_journal = temp_documents["journal_temp"][
            "receipt_sha256"
        ]

    if link_relationship_invalid:
        return result(
            "manual_hold",
            ["private_metadata_unexpected_hardlink"],
            prior_state=prior_row_state,
            inventory_state=receipt_inventory_state,
            row_count=exact_count,
            receipt_count=1 if exact_receipt else 0,
            planned_receipt_sha256=(
                planned_from_journal
                or (
                    receipt.state.get("sha256")
                    if exact_receipt
                    else None
                )
            ),
        )

    journal_cross_field_mismatch = any(
        snapshot.state.get("state") == "present"
        and document is not None
        and not contract.validate_private_metadata_write_journal_semantics(
            document
        )["accepted"]
        for snapshot, document in (
            (journal, journal_document),
            (
                temp_snapshots["journal_temp"],
                temp_documents["journal_temp"],
            ),
        )
    )
    if journal_cross_field_mismatch:
        return result(
            "manual_hold",
            ["private_metadata_journal_cross_field_mismatch"],
            prior_state=prior_row_state,
            inventory_state=receipt_inventory_state,
            row_count=exact_count,
            receipt_count=1 if exact_receipt else 0,
            planned_receipt_sha256=(
                receipt.state.get("sha256") if exact_receipt else None
            ),
        )
    replay_mismatch_reasons: list[str] = []
    if exact_receipt and receipt_document is not None:
        if receipt_document["intake_sha256"] != intake_sha256:
            replay_mismatch_reasons.append(
                "private_metadata_authority_intake_digest_mismatch"
            )
        if (
            receipt_document["review_evidence_sha256"]
            != review_evidence_sha256
        ):
            replay_mismatch_reasons.append(
                "private_metadata_authority_review_evidence_digest_mismatch"
            )
        if (
            receipt_document["canonical_row_sha256"]
            != canonical_row_sha256
            or prior_row_state in {"collision", "multiple"}
        ):
            replay_mismatch_reasons.append(
                "private_metadata_observation_authority_collision"
            )
    elif prior_row_state in {"collision", "multiple"}:
        replay_mismatch_reasons.append(
            "private_metadata_observation_authority_collision"
        )
    if replay_mismatch_reasons:
        return result(
            "manual_hold",
            _unique(replay_mismatch_reasons),
            prior_state=prior_row_state,
            inventory_state=receipt_inventory_state,
            row_count=exact_count,
            receipt_count=1 if exact_receipt else 0,
            planned_receipt_sha256=(
                receipt.state.get("sha256") if exact_receipt else None
            ),
        )

    stored_row = contract.stored_json_bytes(row)
    current_raw = private_manifest.raw or b""

    def transition_matches_before(document: dict[str, Any]) -> bool:
        before_rows = int(private_manifest.state.get("row_count") or 0)
        expected_after = _present_state(
            current_raw + stored_row,
            before_rows + 1,
            1,
        )
        return bool(
            document["private_manifest_before"] == private_manifest.state
            and document["private_manifest_after"] == expected_after
        )

    def transition_matches_after(document: dict[str, Any]) -> bool:
        if (
            private_manifest.state.get("state") != "present"
            or private_manifest.state.get("link_count") != 1
            or type(private_manifest.state.get("row_count")) is not int
            or private_manifest.state["row_count"] < 1
            or not current_raw.endswith(stored_row)
            or not private_rows
            or contract.sha256_digest(
                contract.canonical_json_bytes(private_rows[-1])
            )
            != canonical_row_sha256
        ):
            return False
        prefix_raw = current_raw[: -len(stored_row)]
        prefix_rows = private_manifest.state["row_count"] - 1
        expected_before = (
            _absent_state()
            if prefix_rows == 0
            else _present_state(prefix_raw, prefix_rows, 1)
        )
        return bool(
            document["private_manifest_before"] == expected_before
            and document["private_manifest_after"] == private_manifest.state
        )

    def manifest_temp_matches_rollback(
        document: dict[str, Any],
    ) -> bool:
        expected = current_raw + stored_row
        after_rows = int(
            document["private_manifest_after"]["row_count"]
        )
        return bool(
            manifest_temp_absent
            or is_exact_manifest(
                temp_snapshots["manifest_temp"],
                expected,
                row_count=after_rows,
            )
            or is_strict_prefix(
                temp_snapshots["manifest_temp"],
                expected,
            )
        )

    def receipt_temp_matches_recovery(
        document: dict[str, Any],
    ) -> bool:
        expected = contract.stored_json_bytes(document["receipt_document"])
        full = bool(
            temp_documents["receipt_temp"] == document["receipt_document"]
            and is_exact_document(
                temp_snapshots["receipt_temp"],
                temp_documents["receipt_temp"],
                link_count=1,
            )
        )
        return bool(
            receipt_temp_absent
            or full
            or is_strict_prefix(
                temp_snapshots["receipt_temp"],
                expected,
            )
        )

    journal_source: dict[str, Any] | None = None
    fixed_journal_state_allowed = fixed_journal_link_one or journal_twin
    if fixed_journal_state_allowed:
        journal_source = journal_document
    elif journal_absent and journal_temp_link_one:
        journal_source = temp_documents["journal_temp"]

    if (
        prior_row_state == "absent"
        and receipt_absent
        and journal_source is not None
        and transition_matches_before(journal_source)
    ):
        journal_cell_allowed = bool(
            (
                journal_absent
                and journal_temp_link_one
                and manifest_temp_absent
                and receipt_temp_absent
            )
            or (
                not journal_absent
                and fixed_journal_state_allowed
                and (journal_temp_absent or journal_twin)
                and receipt_temp_absent
                and manifest_temp_matches_rollback(journal_source)
            )
        )
        if journal_cell_allowed:
            return result(
                "rollback_required",
                [],
                prior_state="absent",
                inventory_state="absent",
                row_count=0,
                receipt_count=0,
                planned_receipt_sha256=journal_source["receipt_sha256"],
            )

    if (
        prior_row_state == "exact"
        and receipt_absent
        and fixed_journal_link_one
        and journal_document is not None
        and journal_temp_absent
        and manifest_temp_absent
        and transition_matches_after(journal_document)
        and receipt_temp_matches_recovery(journal_document)
    ):
        return result(
            "recovery_required",
            [],
            prior_state="exact",
            inventory_state="absent",
            row_count=1,
            receipt_count=0,
            planned_receipt_sha256=journal_document["receipt_sha256"],
        )

    if (
        prior_row_state == "exact"
        and receipt_matches_incoming
        and fixed_journal_link_one
        and journal_document is not None
        and journal_temp_absent
        and manifest_temp_absent
        and transition_matches_after(journal_document)
        and journal_document["receipt_document"] == receipt_document
        and (
            (receipt_exact_link_one and receipt_temp_absent)
            or receipt_twin
        )
    ):
        return result(
            "already_applied",
            [],
            prior_state="exact",
            inventory_state="exact",
            row_count=1,
            receipt_count=1,
            planned_receipt_sha256=receipt.state["sha256"],
        )

    all_authority_residue_absent = bool(
        journal_absent
        and journal_temp_absent
        and manifest_temp_absent
        and receipt_temp_absent
    )
    if (
        prior_row_state == "absent"
        and receipt_absent
        and all_authority_residue_absent
    ):
        return result(
            "append",
            [],
            prior_state="absent",
            inventory_state="absent",
            row_count=0,
            receipt_count=0,
            planned_receipt_sha256=None,
        )
    if prior_row_state == "absent" and receipt_present:
        return result(
            "manual_hold",
            ["private_metadata_orphan_receipt"],
            prior_state="absent",
            inventory_state=receipt_inventory_state,
            row_count=0,
            receipt_count=1 if exact_receipt else 0,
            planned_receipt_sha256=(
                receipt.state.get("sha256") if exact_receipt else None
            ),
        )
    if (
        prior_row_state == "exact"
        and receipt_matches_incoming
        and receipt_exact_link_one
        and all_authority_residue_absent
    ):
        return result(
            "already_applied",
            [],
            prior_state="exact",
            inventory_state="exact",
            row_count=1,
            receipt_count=1,
            planned_receipt_sha256=receipt.state["sha256"],
        )
    if prior_row_state == "exact" and receipt_absent:
        return result(
            "manual_hold",
            ["private_metadata_recovery_evidence_missing_or_ambiguous"],
            prior_state="exact",
            inventory_state="absent",
            row_count=1,
            receipt_count=0,
            planned_receipt_sha256=planned_from_journal,
        )
    return result(
        "manual_hold",
        ["private_metadata_recovery_evidence_missing_or_ambiguous"],
        prior_state=prior_row_state,
        inventory_state=receipt_inventory_state,
        row_count=exact_count,
        receipt_count=1 if exact_receipt else 0,
        planned_receipt_sha256=(
            planned_from_journal
            or (
                receipt.state.get("sha256")
                if exact_receipt
                else None
            )
        ),
    )


def _receipt_for_append_plan(
    plan: dict[str, Any],
    *,
    reviewed_by: str,
    privacy_class: str,
) -> dict[str, Any]:
    plan_sha256 = contract.sha256_digest(
        contract.canonical_json_bytes(plan)
    )
    return {
        "schema": contract.RECEIPT_SCHEMA,
        "writer_state_machine_version": contract.WRITER_STATE_MACHINE_VERSION,
        "lifecycle": "private_objet_source_metadata_write",
        "action": "applied",
        "artifact_class": privacy_class,
        "archive_id": plan["archive_id"],
        "record_privacy_class": privacy_class,
        "object_id": plan["object_id"],
        "authority_key_sha256": plan["authority_key_sha256"],
        "intake_sha256": plan["intake_sha256"],
        "canonical_row_sha256": plan["canonical_row_sha256"],
        "observation_evidence_sha256": plan[
            "observation_evidence_sha256"
        ],
        "review_evidence_sha256": plan["review_evidence_sha256"],
        "reviewed_by": reviewed_by,
        "external_writers_quiescent_affirmed": True,
        "mutation_platform_profile": contract.MUTATION_PLATFORM_PROFILE,
        "power_loss_durability_verified": False,
        "plan_binding": deepcopy(plan),
        "plan_sha256": plan_sha256,
        "object_manifest_state": deepcopy(plan["object_manifest_state"]),
        "authority_chain_before_sha256": plan["authority_chain_sha256"],
        "private_manifest_before": deepcopy(plan["private_manifest_before"]),
        "private_manifest_after": deepcopy(plan["private_manifest_after"]),
        "intake_schema": contract.INTAKE_SCHEMA,
        "durable_schema": contract.DURABLE_SCHEMA,
        "normalization_profile": deepcopy(
            contract.NORMALIZATION_PROFILE_VALUE
        ),
        "derived_alias_count": plan["derived_alias_count"],
        "closed_actions": {
            "source_artifact_modified": False,
            "object_bytes_opened": False,
            "provider_or_network_called": False,
            "database_or_index_written": False,
        },
    }


def _journal_for_receipt(
    receipt: dict[str, Any],
) -> dict[str, Any]:
    plan = receipt["plan_binding"]
    return {
        "schema": contract.JOURNAL_SCHEMA,
        "writer_state_machine_version": contract.WRITER_STATE_MACHINE_VERSION,
        "transition": "append",
        "plan_sha256": receipt["plan_sha256"],
        "authority_chain_before_sha256": receipt[
            "authority_chain_before_sha256"
        ],
        "authority_key_sha256": receipt["authority_key_sha256"],
        "receipt_relative_path": plan["receipt_relative_path"],
        "receipt_document": deepcopy(receipt),
        "receipt_sha256": contract.sha256_digest(
            contract.stored_json_bytes(receipt)
        ),
        "object_manifest_state": deepcopy(plan["object_manifest_state"]),
        "private_manifest_before": deepcopy(plan["private_manifest_before"]),
        "private_manifest_after": deepcopy(plan["private_manifest_after"]),
        "owned_temp_relative_paths": contract.owned_temp_relative_paths(
            receipt["authority_key_sha256"]
        ),
    }


def _manifest_after_append(
    before: _FileSnapshot,
    stored_row: bytes,
) -> dict[str, Any]:
    before_raw = before.raw or b""
    before_rows = int(before.state["row_count"] or 0)
    return _present_state(before_raw + stored_row, before_rows + 1, 1)


def _base_resource_binding(
    context: _PlanningContext,
    *,
    manifest_directory_entries_with_both_locks: int,
    receipt_chain_after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    private_bytes = int(context.private_manifest.state["byte_count"] or 0)
    private_rows = int(context.private_manifest.state["row_count"] or 0)
    receipt_count = len(context.receipt_inventory)
    receipt_total = sum(size for _, size in context.receipt_inventory)
    chain_after = (
        context.receipt_directory_chain_after
        if receipt_chain_after is None
        else receipt_chain_after
    )
    return {
        "basis": "no_write",
        "private_manifest_current_bytes": private_bytes,
        "private_manifest_current_rows": private_rows,
        "canonical_stored_row_bytes": len(context.stored_row),
        "receipt_final_count_current": receipt_count,
        "receipt_final_total_bytes_current": receipt_total,
        "receipt_directory_entries_current": (
            context.receipt_directory_entry_count
        ),
        "receipt_root_entries_after_bootstrap": chain_after[
            "receipts_root"
        ]["entry_count"],
        "receipt_objects_entries_after_bootstrap": chain_after[
            "objects_parent"
        ]["entry_count"],
        "manifest_directory_entries_with_both_locks": (
            manifest_directory_entries_with_both_locks
        ),
        "prospective_private_manifest_bytes": private_bytes,
        "prospective_private_manifest_rows": private_rows,
        "prospective_receipt_bytes": 0,
        "prospective_receipt_final_count": receipt_count,
        "prospective_receipt_final_total_bytes": receipt_total,
        "prospective_receipt_directory_peak_entries": (
            context.receipt_directory_entry_count
        ),
        "prospective_manifest_directory_peak_entries": (
            manifest_directory_entries_with_both_locks
        ),
        "prospective_journal_bytes": 0,
    }


def _make_plan(
    context: _PlanningContext,
    *,
    action: str,
    blocked_context: str | None,
    resource_binding: dict[str, Any],
    manifest_after: dict[str, Any] | None = None,
    chain_after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    authority_validation = context.authority_chain_validation
    authority_digest = (
        context.authority_chain_sha256
        if authority_validation != "manual_hold"
        else None
    )
    plan = {
        "schema": contract.PLAN_SCHEMA,
        "writer_state_machine_version": contract.WRITER_STATE_MACHINE_VERSION,
        "archive_id": context.archive_id,
        "intake_sha256": context.intake_sha256,
        "canonical_row_sha256": context.canonical_row_sha256,
        "observation_evidence_sha256": context.row["source_provenance"][
            "observation_evidence_sha256"
        ],
        "review_evidence_sha256": context.intake["review_evidence"][
            "review_evidence_sha256"
        ],
        "object_id": context.row["object_id"],
        "object_manifest_state": deepcopy(context.object_manifest.state),
        "object_manifest_match_count": context.object_manifest_match_count,
        "private_manifest_before": deepcopy(context.private_manifest.state),
        "private_manifest_after": deepcopy(
            manifest_after or context.private_manifest.state
        ),
        "receipt_directory_chain_before": deepcopy(
            context.receipt_directory_chain_before
        ),
        "receipt_directory_chain_after": deepcopy(
            chain_after or context.receipt_directory_chain_before
        ),
        "receipt_state": deepcopy(context.receipt.state),
        "journal_state": deepcopy(context.journal.state),
        "journal_sha256": (
            context.journal.state["sha256"]
            if context.journal.state["state"]
            in {"present", "present_invalid"}
            else None
        ),
        "owned_temp_states": {
            key: deepcopy(context.temp_snapshots[key].state)
            for key in ("journal_temp", "manifest_temp", "receipt_temp")
        },
        "planned_receipt_sha256": context.planned_receipt_sha256,
        "prior_row_state": context.prior_row_state,
        "receipt_inventory_state": context.receipt_inventory_state,
        "authority_chain_scope": context.authority_chain_scope,
        "authority_chain_validation": authority_validation,
        "authority_chain_sha256": authority_digest,
        "intake_schema": contract.INTAKE_SCHEMA,
        "durable_schema": contract.DURABLE_SCHEMA,
        "normalization_profile": deepcopy(
            contract.NORMALIZATION_PROFILE_VALUE
        ),
        "action": action,
        "blocked_context": blocked_context,
        "derived_alias_count": len(context.row["label_candidates"]),
        "existing_exact_row_count": context.existing_exact_row_count,
        "exact_receipt_count": context.exact_receipt_count,
        "resource_binding": deepcopy(resource_binding),
        "private_manifest_relative_path": contract.PRIVATE_MANIFEST_PATH,
        "receipt_directory_relative_path": contract.RECEIPT_DIRECTORY,
        "authority_key_sha256": context.authority_key_sha256,
        "receipt_relative_path": context.receipt_relative_path,
    }
    if not contract.validate_private_metadata_write_plan_semantics(plan)[
        "accepted"
    ]:
        raise ValueError("constructed plan violates closed contract")
    return plan


def _append_fixed_point_plan(
    context: _PlanningContext,
    *,
    manifest_directory_entries_with_both_locks: int,
) -> tuple[dict[str, Any] | None, list[str]]:
    binding = _base_resource_binding(
        context,
        manifest_directory_entries_with_both_locks=(
            manifest_directory_entries_with_both_locks
        ),
    )
    binding.update(
        {
            "basis": "append_worst_case_actor",
            "prospective_private_manifest_bytes": (
                int(context.private_manifest.state["byte_count"] or 0)
                + len(context.stored_row)
            ),
            "prospective_private_manifest_rows": (
                int(context.private_manifest.state["row_count"] or 0) + 1
            ),
            "prospective_receipt_final_count": (
                len(context.receipt_inventory) + 1
            ),
            "prospective_receipt_directory_peak_entries": (
                context.receipt_directory_entry_count + 2
            ),
            "prospective_manifest_directory_peak_entries": (
                manifest_directory_entries_with_both_locks + 2
            ),
        }
    )
    manifest_after = _manifest_after_append(
        context.private_manifest,
        context.stored_row,
    )
    p_value = 0
    j_value = 0
    candidate: dict[str, Any] | None = None
    for _ in range(16):
        binding["prospective_receipt_bytes"] = p_value
        binding["prospective_receipt_final_total_bytes"] = (
            sum(size for _, size in context.receipt_inventory) + p_value
        )
        binding["prospective_journal_bytes"] = j_value
        candidate = _make_plan(
            context,
            action="append",
            blocked_context=None,
            resource_binding=binding,
            manifest_after=manifest_after,
            chain_after=context.receipt_directory_chain_after,
        )
        receipt = _receipt_for_append_plan(
            candidate,
            reviewed_by=contract.WORST_CASE_REVIEWED_BY,
            privacy_class=context.row["privacy_class"],
        )
        journal = _journal_for_receipt(receipt)
        p_next = len(contract.stored_json_bytes(receipt))
        j_next = len(contract.stored_json_bytes(journal))
        if p_next == p_value and j_next == j_value:
            break
        p_value = p_next
        j_value = j_next
    else:
        return None, ["private_metadata_resource_size_fixed_point_failed"]

    assert candidate is not None
    prospective_reasons = _prospective_resource_reasons(
        candidate["resource_binding"],
        recovery=False,
    )
    if not prospective_reasons:
        return candidate, []
    blocked_plan = _make_plan(
        context,
        action="blocked",
        blocked_context="append",
        resource_binding=candidate["resource_binding"],
        manifest_after=context.private_manifest.state,
        chain_after=context.receipt_directory_chain_after,
    )
    return blocked_plan, prospective_reasons


def _prospective_resource_reasons(
    binding: dict[str, Any],
    *,
    recovery: bool,
) -> list[str]:
    reasons: list[str] = []
    for field, maximum, reason in _PROSPECTIVE_REASONS:
        if recovery and field in {
            "prospective_private_manifest_bytes",
            "prospective_private_manifest_rows",
            "canonical_stored_row_bytes",
            "receipt_root_entries_after_bootstrap",
            "receipt_objects_entries_after_bootstrap",
            "prospective_manifest_directory_peak_entries",
            "prospective_journal_bytes",
        }:
            continue
        if binding[field] > maximum:
            reasons.append(reason)
    return _unique(reasons)


def _recovery_plan(
    context: _PlanningContext,
    *,
    manifest_directory_entries_with_both_locks: int,
) -> tuple[dict[str, Any], list[str]]:
    binding = _base_resource_binding(
        context,
        manifest_directory_entries_with_both_locks=(
            manifest_directory_entries_with_both_locks
        ),
    )
    assert context.journal_document is not None
    receipt_bytes = len(
        contract.stored_json_bytes(
            context.journal_document["receipt_document"]
        )
    )
    receipt_temp_absent = (
        context.temp_snapshots["receipt_temp"].state["state"] == "absent"
    )
    binding.update(
        {
            "basis": "recovery_exact_journal",
            "prospective_receipt_bytes": receipt_bytes,
            "prospective_receipt_final_count": (
                len(context.receipt_inventory) + 1
            ),
            "prospective_receipt_final_total_bytes": (
                sum(size for _, size in context.receipt_inventory)
                + receipt_bytes
            ),
            "prospective_receipt_directory_peak_entries": (
                context.receipt_directory_entry_count
                + (2 if receipt_temp_absent else 1)
            ),
            "prospective_manifest_directory_peak_entries": (
                manifest_directory_entries_with_both_locks
            ),
            "prospective_journal_bytes": int(
                context.journal.state["byte_count"] or 0
            ),
        }
    )
    reasons = _prospective_resource_reasons(binding, recovery=True)
    if reasons:
        return (
            _make_plan(
                context,
                action="blocked",
                blocked_context="recovery",
                resource_binding=binding,
            ),
            reasons,
        )
    return (
        _make_plan(
            context,
            action="recovery_required",
            blocked_context=None,
            resource_binding=binding,
        ),
        [],
    )


def _validate_persistent_lock_state(
    root: Path,
) -> tuple[int, list[str], int]:
    manifests = root / "objects" / "manifests"
    if not _path_has_safe_chain(root, manifests, final_may_absent=False):
        raise _SnapshotError("lock_path_unsafe")
    entry_count = _directory_entry_count(
        root,
        manifests,
        PRIVATE_MANIFEST_DIR_MAX_ENTRIES,
    )
    missing = 0
    for relative in (
        contract.OBJECT_MANIFEST_LOCK,
        contract.PRIVATE_METADATA_LOCK,
    ):
        path = _safe_archive_path(root, relative, final_may_absent=True)
        if path is None:
            raise _SnapshotError("lock_path_unsafe")
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            missing += 1
            continue
        except OSError as exc:
            raise _SnapshotError("lock_path_unsafe") from exc
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or _is_reparse(info)
            or info.st_size != 0
            or info.st_nlink != 1
        ):
            raise _SnapshotError("lock_path_unsafe")
    normalized_count = entry_count + missing
    if normalized_count > PRIVATE_MANIFEST_DIR_MAX_ENTRIES:
        raise _SnapshotError("manifest_directory_entries_limit")
    return normalized_count, [], missing


def _unexpected_manifest_residue(
    root: Path,
    *,
    allowed_relatives: list[str],
) -> list[str]:
    from . import archive_services as services

    manifests = root / "objects" / "manifests"
    allowed_names = {
        PurePosixPath(value).name
        for value in allowed_relatives
        if PurePosixPath(value).parent
        == PurePosixPath("objects/manifests")
    }
    unexpected: list[str] = []
    try:
        with services._bound_directory_chain(root, manifests) as binding:
            with services._scan_bound_directory(binding) as entries:
                for entry in entries:
                    if not entry.name.startswith(
                        ".private-source-metadata-write."
                    ):
                        continue
                    if entry.name not in allowed_names:
                        unexpected.append(entry.name)
    except OSError as exc:
        raise _SnapshotError("authority_state_unavailable") from exc
    return sorted(unexpected)


def _build_planning_context(
    root: Path,
    *,
    archive_id: str,
    intake: dict[str, Any],
    intake_sha256: str,
    row_result: dict[str, Any],
    object_manifest_authority_work: (
        _ObjectManifestAuthorityWork | None
    ) = None,
) -> tuple[_PlanningContext, int, list[str]]:
    row = row_result["row"]
    assert isinstance(row, dict)
    row_cjson = row_result["canonical_json_bytes"]
    stored_row = row_result["stored_row_bytes"]
    canonical_row_sha256 = row_result["canonical_row_sha256"]
    assert isinstance(row_cjson, bytes)
    assert isinstance(stored_row, bytes)
    assert isinstance(canonical_row_sha256, str)
    authority_key = contract.authority_key_sha256(
        row["source_provenance"]["observation_evidence_sha256"]
    )
    receipt_relative = contract.receipt_relative_path(authority_key)
    temp_relatives = contract.owned_temp_relative_paths(authority_key)
    current_bound_reasons = _collect_current_bound_reasons(
        root,
        receipt_relative_path=receipt_relative,
        owned_temp_relative_paths=temp_relatives,
    )
    if current_bound_reasons:
        raise _CurrentBoundError(current_bound_reasons)

    (
        object_manifest,
        object_manifest_prefix_authority,
        match_count,
    ) = _observe_object_manifest(
        root,
        row["object_id"],
        work=object_manifest_authority_work,
    )
    private_manifest, private_rows, private_stored_rows = (
        _observe_private_manifest(root)
    )
    chain_before, chain_after = _observe_receipt_directory_chain(root)
    receipt_inventory, receipt_entry_count, unexpected_receipt_entries = (
        _inventory_receipt_directory(
            root,
            chain_before,
            allowed_temp_basename=PurePosixPath(temp_relatives[2]).name,
        )
    )
    receipt, receipt_document = _observe_receipt(root, receipt_relative)
    journal, journal_document = _observe_journal(root)
    temp_snapshots, temp_documents = _observe_owned_temps(
        root,
        temp_relatives,
    )
    semantic_mismatches: list[str] = []
    for snapshot, document in (
        (journal, journal_document),
        (
            temp_snapshots["journal_temp"],
            temp_documents["journal_temp"],
        ),
    ):
        if (
            snapshot.state.get("state") == "present"
            and document is not None
            and not _journal_matches_current_authority(
                document,
                archive_id=archive_id,
                intake_sha256=intake_sha256,
                row=row,
                stored_row=stored_row,
                object_manifest=object_manifest,
                object_manifest_prefix_authority=(
                    object_manifest_prefix_authority
                ),
                private_manifest=private_manifest,
                object_manifest_authority_work=(
                    object_manifest_authority_work
                ),
            )
        ):
            semantic_mismatches.append("journal_cross_field_mismatch")
    if (
        receipt.state.get("state") == "present"
        and receipt_document is not None
        and not _receipt_matches_current_authority(
            receipt_document,
            archive_id=archive_id,
            row=row,
            object_manifest=object_manifest,
            object_manifest_prefix_authority=(
                object_manifest_prefix_authority
            ),
            object_manifest_authority_work=(
                object_manifest_authority_work
            ),
        )
    ):
        semantic_mismatches.append("receipt_semantic_mismatch")
    if semantic_mismatches:
        raise _PreplanSemanticError(semantic_mismatches)
    manifest_entries_with_locks, lock_bound_reasons, missing_lock_count = (
        _validate_persistent_lock_state(root)
    )
    unexpected_manifest_entries = _unexpected_manifest_residue(
        root,
        allowed_relatives=[
            contract.JOURNAL_PATH,
            *temp_relatives,
        ],
    )

    (
        action,
        reasons,
        prior_row_state,
        receipt_inventory_state,
        existing_exact_row_count,
        exact_receipt_count,
        planned_receipt_sha256,
    ) = _classify_current_action(
        private_manifest=private_manifest,
        private_rows=private_rows,
        row=row,
        canonical_row_sha256=canonical_row_sha256,
        intake_sha256=intake_sha256,
        review_evidence_sha256=intake["review_evidence"][
            "review_evidence_sha256"
        ],
        authority_key_sha256=authority_key,
        receipt=receipt,
        receipt_document=receipt_document,
        journal=journal,
        journal_document=journal_document,
        temp_snapshots=temp_snapshots,
        temp_documents=temp_documents,
    )

    persistent_state_action = action in {
        "rollback_required",
        "recovery_required",
        "already_applied",
    }
    receipt_chain_complete = _receipt_directory_chain_complete(chain_before)
    if persistent_state_action and not receipt_chain_complete:
        action = "manual_hold"
        reasons.append(
            "private_metadata_receipt_directory_chain_impossible"
        )
    if unexpected_receipt_entries or unexpected_manifest_entries:
        action = "manual_hold"
        reasons.append("private_metadata_recovery_evidence_missing_or_ambiguous")
    if (
        missing_lock_count
        and persistent_state_action
    ):
        action = "manual_hold"
        reasons.append("private_metadata_lock_identity_changed")

    authority_chain: dict[str, Any] | None = None
    authority_chain_sha256: str | None = None
    authority_chain_validation = "valid_complete"
    authority_chain_scope = "complete_current"
    receipt_temp_snapshot = temp_snapshots["receipt_temp"]
    permitted_receipt_twin = bool(
        receipt.state.get("state") == "present"
        and receipt.state.get("link_count") == 2
        and receipt_temp_snapshot.state.get("state") == "present"
        and receipt_temp_snapshot.state.get("link_count") == 2
        and receipt.identity is not None
        and receipt.identity == receipt_temp_snapshot.identity
        and receipt.raw is not None
        and receipt.raw == receipt_temp_snapshot.raw
    )
    try:
        if action == "recovery_required":
            if (
                journal_document is None
                or journal.state["state"] != "present"
                or not private_rows
                or contract.sha256_digest(
                    contract.canonical_json_bytes(private_rows[-1])
                )
                != canonical_row_sha256
            ):
                raise _SnapshotError("recovery_ambiguous")
            prefix_rows = private_rows[:-1]
            prefix_stored = private_stored_rows[:-1]
            prefix_raw = b"".join(prefix_stored)
            before_state = journal_document["private_manifest_before"]
            if (
                _historical_manifest_state(prefix_raw, len(prefix_rows))
                != before_state
                or private_manifest.state
                != journal_document["private_manifest_after"]
            ):
                raise _SnapshotError("recovery_ambiguous")
            authority_chain, authority_chain_sha256, _ = (
                _build_complete_authority_chain(
                    root,
                    prefix_rows,
                    prefix_stored,
                    private_manifest_state=before_state,
                    inventory=receipt_inventory,
                    archive_id=archive_id,
                    object_manifest=object_manifest,
                    object_manifest_prefix_authority=(
                        object_manifest_prefix_authority
                    ),
                    object_manifest_authority_work=(
                        object_manifest_authority_work
                    ),
                )
            )
            if (
                authority_chain_sha256
                != journal_document["authority_chain_before_sha256"]
            ):
                raise _SnapshotError("journal_cross_field_mismatch")
            authority_chain_scope = "prefix_before_interrupted_append"
            authority_chain_validation = "valid_recovery_prefix"
        else:
            authority_chain, authority_chain_sha256, _ = (
                _build_complete_authority_chain(
                    root,
                    private_rows,
                    private_stored_rows,
                    private_manifest_state=private_manifest.state,
                    inventory=receipt_inventory,
                    allowed_receipt_twin_relative=(
                        receipt_relative
                        if permitted_receipt_twin
                        else None
                    ),
                    allowed_receipt_twin_identity=(
                        receipt.identity
                        if permitted_receipt_twin
                        else None
                    ),
                    archive_id=archive_id,
                    object_manifest=object_manifest,
                    object_manifest_prefix_authority=(
                        object_manifest_prefix_authority
                    ),
                    object_manifest_authority_work=(
                        object_manifest_authority_work
                    ),
                )
            )
    except _SnapshotError as exc:
        if exc.reason in {
            "journal_cross_field_mismatch",
            "receipt_semantic_mismatch",
        }:
            raise _PreplanSemanticError([exc.reason]) from exc
        if action in {"append", "already_applied", "rollback_required"}:
            action = "manual_hold"
        authority_chain = None
        authority_chain_sha256 = None
        authority_chain_validation = "manual_hold"
        if exc.reason == "receipt_semantic_mismatch":
            reasons.append(
                "private_metadata_receipt_plan_authority_chain_mismatch"
            )
        elif exc.reason == "journal_cross_field_mismatch":
            reasons.append("private_metadata_journal_cross_field_mismatch")
        elif exc.reason == "orphan_or_missing_receipt":
            reasons.append("private_metadata_orphan_receipt")
        else:
            reasons.append("private_metadata_authority_state_invalid")

    context = _PlanningContext(
        root=root,
        archive_id=archive_id,
        intake=intake,
        intake_sha256=intake_sha256,
        row=row,
        row_cjson=row_cjson,
        stored_row=stored_row,
        canonical_row_sha256=canonical_row_sha256,
        authority_key_sha256=authority_key,
        receipt_relative_path=receipt_relative,
        owned_temp_relative_paths=temp_relatives,
        object_manifest=object_manifest,
        object_manifest_prefix_authority=(
            object_manifest_prefix_authority
        ),
        object_manifest_match_count=match_count,
        private_manifest=private_manifest,
        private_rows=private_rows,
        private_row_bytes=private_stored_rows,
        journal=journal,
        journal_document=journal_document,
        receipt=receipt,
        receipt_document=receipt_document,
        temp_snapshots=temp_snapshots,
        receipt_directory_chain_before=chain_before,
        receipt_directory_chain_after=chain_after,
        receipt_inventory=receipt_inventory,
        receipt_directory_entry_count=receipt_entry_count,
        manifest_directory_entry_count=(
            manifest_entries_with_locks
        ),
        authority_chain=authority_chain,
        authority_chain_sha256=authority_chain_sha256,
        authority_chain_validation=authority_chain_validation,
        action=action,
        reasons=_unique([*reasons, *lock_bound_reasons]),
        prior_row_state=prior_row_state,
        receipt_inventory_state=receipt_inventory_state,
        authority_chain_scope=authority_chain_scope,
        existing_exact_row_count=existing_exact_row_count,
        exact_receipt_count=exact_receipt_count,
        planned_receipt_sha256=planned_receipt_sha256,
    )
    return context, manifest_entries_with_locks, lock_bound_reasons


def _plan_from_context(
    context: _PlanningContext,
    *,
    manifest_entries_with_locks: int,
) -> tuple[dict[str, Any] | None, list[str]]:
    if context.action == "append":
        return _append_fixed_point_plan(
            context,
            manifest_directory_entries_with_both_locks=(
                manifest_entries_with_locks
            ),
        )
    if context.action == "recovery_required":
        return _recovery_plan(
            context,
            manifest_directory_entries_with_both_locks=(
                manifest_entries_with_locks
            ),
        )
    binding = _base_resource_binding(
        context,
        manifest_directory_entries_with_both_locks=manifest_entries_with_locks,
        receipt_chain_after=context.receipt_directory_chain_before,
    )
    plan = _make_plan(
        context,
        action=context.action,
        blocked_context=None,
        resource_binding=binding,
    )
    return plan, context.reasons


def _result_envelope(
    *,
    action: str,
    archive_id: str | None,
    intake_sha256: str | None,
    plan: dict[str, Any] | None,
    plan_sha256: str | None,
    reasons: list[str],
    dry_run: bool,
    hold_context: dict[str, Any] | None = None,
    receipt_sha256: str | None = None,
    files_written: list[str] | None = None,
) -> dict[str, Any]:
    context = plan or {}
    is_success = not reasons and action not in {"blocked", "manual_hold"}
    if action == "append" and dry_run:
        next_safe_actions = [
            "Approve only this exact plan digest after reviewing the private intake.",
        ]
    elif action == "rollback_required":
        next_safe_actions = [
            "Approve this exact rollback plan; it removes only verified owned residue and does not append.",
        ]
    elif action == "recovery_required":
        next_safe_actions = [
            "Approve this exact recovery plan to publish the journal-bound immutable receipt.",
        ]
    elif action == "already_applied":
        next_safe_actions = []
    else:
        next_safe_actions = [
            "Preserve current evidence and run one fresh dry-run after the reported condition is resolved.",
        ]
    would_change: list[str] = []
    if dry_run and not reasons:
        if action == "append":
            would_change = [
                contract.PRIVATE_MANIFEST_PATH,
                context.get("receipt_relative_path"),
            ]
        elif action in {"rollback_required", "recovery_required"}:
            would_change = [
                value
                for value in (
                    context.get("receipt_relative_path")
                    if action == "recovery_required"
                    else contract.JOURNAL_PATH,
                )
                if isinstance(value, str)
            ]
    return {
        "schema": RESULT_SCHEMA,
        "lifecycle": "private_objet_source_metadata_write",
        "ok": is_success,
        "dry_run": dry_run,
        "status": action,
        "action": action,
        "archive_id": archive_id,
        "intake_sha256": intake_sha256,
        "canonical_row_sha256": context.get("canonical_row_sha256"),
        "plan_sha256": plan_sha256,
        "plan": plan,
        "hold_context": hold_context,
        "object_manifest_match_count": context.get(
            "object_manifest_match_count"
        ),
        "existing_exact_row_count": context.get(
            "existing_exact_row_count"
        ),
        "exact_receipt_count": context.get("exact_receipt_count"),
        "derived_alias_count": context.get("derived_alias_count"),
        "receipt_sha256": receipt_sha256,
        "planned_families": {
            "private_manifest": contract.PRIVATE_MANIFEST_PATH,
            "receipt_directory": contract.RECEIPT_DIRECTORY,
            "journal": contract.JOURNAL_PATH,
        },
        "would_change": [value for value in would_change if value],
        "files_written": files_written or [],
        "privacy": {
            "private_values_echoed": False,
            "local_paths_echoed": False,
            "object_bytes_opened": False,
            "provider_or_network_called": False,
            "database_or_index_written": False,
        },
        "closed_actions": {
            "indexed": False,
            "searchable": False,
            "object_bytes_verified": False,
            "source_coverage_proven": False,
        },
        "blockers": _unique(reasons),
        "warnings": [],
        "next_safe_actions": next_safe_actions,
    }


def _preplan_result(
    *,
    action: str,
    reason: str | list[str],
    archive_id: str | None,
    intake_sha256: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    reasons = [reason] if isinstance(reason, str) else reason
    return _result_envelope(
        action=action,
        archive_id=archive_id,
        intake_sha256=intake_sha256,
        plan=None,
        plan_sha256=None,
        reasons=reasons,
        dry_run=dry_run,
    )


def _map_planning_snapshot_error(reason: str) -> tuple[str, str]:
    mapping = {
        "authority_path_unsafe": (
            "manual_hold",
            "private_metadata_authority_path_unsafe",
        ),
        "authority_state_unavailable": (
            "manual_hold",
            "private_metadata_authority_state_unavailable",
        ),
        "authority_state_invalid": (
            "manual_hold",
            "private_metadata_authority_state_invalid",
        ),
        "journal_cross_field_mismatch": (
            "manual_hold",
            "private_metadata_journal_cross_field_mismatch",
        ),
        "receipt_semantic_mismatch": (
            "manual_hold",
            "private_metadata_receipt_plan_authority_chain_mismatch",
        ),
        "object_manifest_bytes_limit": (
            "manual_hold",
            "private_metadata_object_manifest_bytes_limit_exceeded",
        ),
        "object_manifest_rows_limit": (
            "manual_hold",
            "private_metadata_object_manifest_rows_limit_exceeded",
        ),
        "object_manifest_row_bytes_limit": (
            "manual_hold",
            "private_metadata_object_manifest_row_bytes_limit_exceeded",
        ),
        "private_manifest_bytes_limit": (
            "manual_hold",
            "private_metadata_manifest_bytes_limit_exceeded",
        ),
        "private_manifest_rows_limit": (
            "manual_hold",
            "private_metadata_manifest_rows_limit_exceeded",
        ),
        "private_manifest_row_bytes_limit": (
            "manual_hold",
            "private_metadata_manifest_row_bytes_limit_exceeded",
        ),
        "receipt_bytes_limit": (
            "manual_hold",
            "private_metadata_receipt_bytes_limit_exceeded",
        ),
        "receipt_count_limit": (
            "manual_hold",
            "private_metadata_receipt_count_limit_exceeded",
        ),
        "receipt_total_bytes_limit": (
            "manual_hold",
            "private_metadata_receipt_total_bytes_limit_exceeded",
        ),
        "receipt_directory_entries_limit": (
            "manual_hold",
            "private_metadata_receipt_directory_entries_limit_exceeded",
        ),
        "receipt_ancestor_directory_entries_limit": (
            "manual_hold",
            (
                "private_metadata_receipt_ancestor_directory_entries_"
                "limit_exceeded"
            ),
        ),
        "manifest_directory_entries_limit": (
            "manual_hold",
            "private_metadata_manifest_directory_entries_limit_exceeded",
        ),
        "journal_bytes_limit": (
            "manual_hold",
            "private_metadata_journal_bytes_limit_exceeded",
        ),
        "unexpected_hardlink": (
            "manual_hold",
            "private_metadata_unexpected_hardlink",
        ),
        "directory_unsafe": (
            "manual_hold",
            "private_metadata_receipt_directory_unsafe",
        ),
        "directory_unavailable": (
            "manual_hold",
            "private_metadata_receipt_directory_unavailable",
        ),
        "directory_chain_impossible": (
            "manual_hold",
            "private_metadata_receipt_directory_chain_impossible",
        ),
        "lock_path_unsafe": (
            "manual_hold",
            "private_metadata_lock_path_unsafe",
        ),
        "unsafe": (
            "manual_hold",
            "private_metadata_authority_path_unsafe",
        ),
        "unavailable": (
            "manual_hold",
            "private_metadata_authority_state_unavailable",
        ),
    }
    return mapping.get(
        reason,
        ("manual_hold", "private_metadata_authority_state_invalid"),
    )


def plan_private_objet_metadata_write(
    archive_root: Path,
    *,
    archive_id: Any,
    safe_projection: Any,
    intake_relative_path: str,
    expected_intake_sha256: str | None,
) -> dict[str, Any]:
    """Build one deterministic, content-free, read-only writer plan."""

    root = Path(archive_root).resolve()
    safe_archive_id = _safe_archive_id(archive_id, safe_projection)
    if safe_archive_id is None:
        return _preplan_result(
            action="blocked",
            reason="private_metadata_archive_id_not_safely_bindable",
            archive_id=None,
            intake_sha256=None,
            dry_run=True,
        )
    if expected_intake_sha256 is None:
        return _preplan_result(
            action="blocked",
            reason="private_metadata_expected_intake_sha256_required",
            archive_id=safe_archive_id,
            intake_sha256=None,
            dry_run=True,
        )
    if (
        type(expected_intake_sha256) is not str
        or _DIGEST_RE.fullmatch(expected_intake_sha256) is None
    ):
        return _preplan_result(
            action="blocked",
            reason="private_metadata_expected_intake_sha256_invalid",
            archive_id=safe_archive_id,
            intake_sha256=None,
            dry_run=True,
        )
    intake_path = _safe_archive_path(
        root,
        intake_relative_path,
        final_may_absent=False,
    )
    if intake_path is None:
        return _preplan_result(
            action="blocked",
            reason="private_metadata_intake_path_unsafe",
            archive_id=safe_archive_id,
            intake_sha256=None,
            dry_run=True,
        )
    try:
        intake_snapshot = _read_regular_snapshot(
            root,
            intake_path,
            maximum_bytes=contract.INTAKE_MAX_BYTES,
            allow_absent=False,
            classify=lambda raw: (
                1
                if contract.parse_private_metadata_intake_bytes(raw)[
                    "accepted"
                ]
                else (_ for _ in ()).throw(ValueError())
            ),
        )
    except _SnapshotError:
        return _preplan_result(
            action="blocked",
            reason="private_metadata_intake_unavailable",
            archive_id=safe_archive_id,
            intake_sha256=None,
            dry_run=True,
        )
    if (
        intake_snapshot.raw is None
        or intake_snapshot.state["state"] != "present"
    ):
        return _preplan_result(
            action="blocked",
            reason="private_metadata_intake_invalid",
            archive_id=safe_archive_id,
            intake_sha256=None,
            dry_run=True,
        )
    parsed = contract.parse_private_metadata_intake_bytes(
        intake_snapshot.raw
    )
    if not parsed["accepted"]:
        return _preplan_result(
            action="blocked",
            reason="private_metadata_intake_invalid",
            archive_id=safe_archive_id,
            intake_sha256=None,
            dry_run=True,
        )
    intake_sha256 = parsed["intake_sha256"]
    if intake_sha256 != expected_intake_sha256:
        return _preplan_result(
            action="blocked",
            reason="private_metadata_intake_digest_mismatch",
            archive_id=safe_archive_id,
            intake_sha256=intake_sha256,
            dry_run=True,
        )
    intake = parsed["intake"]
    row_result = contract.build_private_metadata_row(intake)
    if not row_result["accepted"]:
        return _preplan_result(
            action="blocked",
            reason="private_metadata_intake_invalid",
            archive_id=safe_archive_id,
            intake_sha256=intake_sha256,
            dry_run=True,
        )
    try:
        context, manifest_entries_with_locks, _ = _build_planning_context(
            root,
            archive_id=safe_archive_id,
            intake=intake,
            intake_sha256=intake_sha256,
            row_result=row_result,
        )
        plan, plan_reasons = _plan_from_context(
            context,
            manifest_entries_with_locks=manifest_entries_with_locks,
        )
    except _CurrentBoundError as exc:
        return _preplan_result(
            action="manual_hold",
            reason=_current_bound_public_reasons(exc.reasons),
            archive_id=safe_archive_id,
            intake_sha256=intake_sha256,
            dry_run=True,
        )
    except _PreplanSemanticError as exc:
        return _preplan_result(
            action="manual_hold",
            reason=[
                _map_planning_snapshot_error(reason)[1]
                for reason in exc.reasons
            ],
            archive_id=safe_archive_id,
            intake_sha256=intake_sha256,
            dry_run=True,
        )
    except _SnapshotError as exc:
        action, reason = _map_planning_snapshot_error(exc.reason)
        return _preplan_result(
            action=action,
            reason=reason,
            archive_id=safe_archive_id,
            intake_sha256=intake_sha256,
            dry_run=True,
        )
    except (KeyError, TypeError, ValueError):
        return _preplan_result(
            action="manual_hold",
            reason="private_metadata_authority_state_invalid",
            archive_id=safe_archive_id,
            intake_sha256=intake_sha256,
            dry_run=True,
        )
    if plan is None:
        return _preplan_result(
            action="blocked",
            reason=plan_reasons,
            archive_id=safe_archive_id,
            intake_sha256=intake_sha256,
            dry_run=True,
        )
    plan_sha256 = contract.sha256_digest(
        contract.canonical_json_bytes(plan)
    )
    action = plan["action"]
    reasons = _unique([*context.reasons, *plan_reasons])
    if action == "append" and reasons:
        action = "manual_hold"
    return _result_envelope(
        action=action,
        archive_id=safe_archive_id,
        intake_sha256=intake_sha256,
        plan=plan,
        plan_sha256=plan_sha256,
        reasons=reasons,
        dry_run=True,
        receipt_sha256=context.receipt.state.get("sha256"),
    )


def private_objet_metadata_write(
    archive_root: Path,
    *,
    archive_id: Any,
    safe_projection: Any,
    intake_relative_path: str,
    expected_intake_sha256: str | None,
    expected_plan_sha256: str | None,
    dry_run: bool,
    approve: bool,
    reviewed_by: str | None,
    affirm_private_metadata_reviewed: bool,
    affirm_external_writers_quiescent: bool,
) -> dict[str, Any]:
    """Plan or execute the closed v0.3.296 lifecycle."""

    if dry_run is approve:
        raise ValueError("choose exactly one of dry_run and approve")
    if dry_run:
        if (
            expected_plan_sha256 is not None
            or reviewed_by is not None
            or affirm_private_metadata_reviewed
            or affirm_external_writers_quiescent
        ):
            raise ValueError("approval-only parameters are forbidden in dry-run")
        return plan_private_objet_metadata_write(
            archive_root,
            archive_id=archive_id,
            safe_projection=safe_projection,
            intake_relative_path=intake_relative_path,
            expected_intake_sha256=expected_intake_sha256,
        )

    root = Path(archive_root).resolve()
    safe_archive_id = _safe_archive_id(archive_id, safe_projection)
    if expected_intake_sha256 is None:
        return _preplan_result(
            action="blocked",
            reason="private_metadata_expected_intake_sha256_required",
            archive_id=safe_archive_id,
            intake_sha256=None,
            dry_run=False,
        )
    if (
        type(expected_intake_sha256) is not str
        or _DIGEST_RE.fullmatch(expected_intake_sha256) is None
    ):
        return _preplan_result(
            action="blocked",
            reason="private_metadata_expected_intake_sha256_invalid",
            archive_id=safe_archive_id,
            intake_sha256=None,
            dry_run=False,
        )
    intake_preflight = _approval_intake_preflight(
        root,
        intake_relative_path=intake_relative_path,
    )
    observed_intake_sha256 = intake_preflight.get("intake_sha256")
    if (
        observed_intake_sha256 is not None
        and observed_intake_sha256 != expected_intake_sha256
    ):
        return _preplan_result(
            action="blocked",
            reason="private_metadata_intake_digest_mismatch",
            archive_id=safe_archive_id,
            intake_sha256=observed_intake_sha256,
            dry_run=False,
        )
    if expected_plan_sha256 is None:
        return _preplan_result(
            action="blocked",
            reason="private_metadata_expected_plan_sha256_required",
            archive_id=safe_archive_id,
            intake_sha256=observed_intake_sha256,
            dry_run=False,
        )
    if (
        type(expected_plan_sha256) is not str
        or _DIGEST_RE.fullmatch(expected_plan_sha256) is None
    ):
        return _preplan_result(
            action="blocked",
            reason="private_metadata_expected_plan_sha256_invalid",
            archive_id=safe_archive_id,
            intake_sha256=observed_intake_sha256,
            dry_run=False,
        )
    if not _reviewed_by_valid(reviewed_by, safe_projection):
        return _preplan_result(
            action="blocked",
            reason="private_metadata_reviewed_by_invalid",
            archive_id=safe_archive_id,
            intake_sha256=observed_intake_sha256,
            dry_run=False,
        )
    if affirm_private_metadata_reviewed is not True:
        return _preplan_result(
            action="blocked",
            reason="private_metadata_private_review_affirmation_required",
            archive_id=safe_archive_id,
            intake_sha256=observed_intake_sha256,
            dry_run=False,
        )
    if affirm_external_writers_quiescent is not True:
        return _preplan_result(
            action="blocked",
            reason=(
                "private_metadata_all_writers_quiescence_affirmation_required"
            ),
            archive_id=safe_archive_id,
            intake_sha256=observed_intake_sha256,
            dry_run=False,
        )
    if os.name != "nt":
        return _preplan_result(
            action="blocked",
            reason="private_metadata_approval_platform_not_supported",
            archive_id=safe_archive_id,
            intake_sha256=observed_intake_sha256,
            dry_run=False,
        )

    try:
        from . import private_metadata_win32 as win32
    except (ImportError, OSError):
        return _preplan_result(
            action="blocked",
            reason="private_metadata_required_win32_primitive_unavailable",
            archive_id=safe_archive_id,
            intake_sha256=observed_intake_sha256,
            dry_run=False,
        )
    support = win32.approval_support_status(root)
    if not support.supported:
        support_reason = support.reason
        if support_reason not in {
            "private_metadata_approval_platform_not_supported",
            "private_metadata_required_win32_primitive_unavailable",
        }:
            support_reason = (
                "private_metadata_required_win32_primitive_unavailable"
            )
        return _preplan_result(
            action="blocked",
            reason=support_reason,
            archive_id=safe_archive_id,
            intake_sha256=observed_intake_sha256,
            dry_run=False,
        )
    if safe_archive_id is None:
        return _preplan_result(
            action="blocked",
            reason="private_metadata_archive_id_not_safely_bindable",
            archive_id=None,
            intake_sha256=observed_intake_sha256,
            dry_run=False,
        )
    preflight_reason = intake_preflight.get("reason")
    if preflight_reason is not None:
        return _preplan_result(
            action="blocked",
            reason=preflight_reason,
            archive_id=safe_archive_id,
            intake_sha256=observed_intake_sha256,
            dry_run=False,
        )
    return _approve_private_objet_metadata_write(
        root,
        archive_id=safe_archive_id,
        safe_projection=safe_projection,
        intake_relative_path=intake_relative_path,
        expected_intake_sha256=expected_intake_sha256,
        expected_plan_sha256=expected_plan_sha256,
        reviewed_by=reviewed_by,
        win32=win32,
    )


def _approve_private_objet_metadata_write(
    archive_root: Path,
    *,
    archive_id: str | None,
    safe_projection: Any,
    intake_relative_path: str,
    expected_intake_sha256: str,
    expected_plan_sha256: str,
    reviewed_by: str,
    win32: Any,
) -> dict[str, Any]:
    """Execute one exact locked plan through retained Win32 authorities."""

    del safe_projection
    if archive_id is None:
        return _preplan_result(
            action="blocked",
            reason="private_metadata_archive_id_not_safely_bindable",
            archive_id=None,
            intake_sha256=expected_intake_sha256,
            dry_run=False,
        )

    root = Path(archive_root).resolve()
    state = _ApprovalExecutionState()
    guard: Any | None = None
    locks: Any | None = None
    intake_authority: Any | None = None
    object_authority: Any | None = None
    outcome: dict[str, Any] | None = None
    pending_failure: _ApprovalFailure | None = None
    release_failure: _ApprovalFailure | None = None

    try:
        intake_path = _safe_archive_path(
            root,
            intake_relative_path,
            final_may_absent=False,
        )
        if intake_path is None:
            return _preplan_result(
                action="blocked",
                reason="private_metadata_intake_path_unsafe",
                archive_id=archive_id,
                intake_sha256=expected_intake_sha256,
                dry_run=False,
            )
        state.stage = "guard_or_lock"
        guard = win32.PrivateMetadataMutationGuard(root)
        guard.hold_chain(intake_path.parent)
        guard.hold_chain(root / "objects" / "manifests")
        guard.validate_all()

        intake_authority = win32.open_bound_file(
            guard,
            intake_path.relative_to(root).as_posix(),
            profile=win32.FileHandleProfile.AUTHORITY_READ,
            expected_link_count=1,
            reason="private_metadata_intake_unavailable",
        )
        state.handles.append(intake_authority)
        intake_raw = intake_authority.read_all(
            max_bytes=contract.INTAKE_MAX_BYTES,
            reason="private_metadata_intake_unavailable",
        )
        locked_intake_sha256 = contract.sha256_digest(intake_raw)
        if locked_intake_sha256 != expected_intake_sha256:
            outcome = _preplan_result(
                action="blocked",
                reason="private_metadata_intake_digest_mismatch",
                archive_id=archive_id,
                intake_sha256=locked_intake_sha256,
                dry_run=False,
            )
            raise _ApprovalStop
        parsed = contract.parse_private_metadata_intake_bytes(intake_raw)
        if not parsed["accepted"]:
            outcome = _preplan_result(
                action="blocked",
                reason="private_metadata_intake_invalid",
                archive_id=archive_id,
                intake_sha256=locked_intake_sha256,
                dry_run=False,
            )
            raise _ApprovalStop
        row_result = contract.build_private_metadata_row(parsed["intake"])
        if not row_result["accepted"]:
            outcome = _preplan_result(
                action="blocked",
                reason="private_metadata_intake_invalid",
                archive_id=archive_id,
                intake_sha256=locked_intake_sha256,
                dry_run=False,
            )
            raise _ApprovalStop

        locks = win32.PrivateMetadataLockPair(guard)
        locks.acquire()
        locks.validate()
        guard.validate_all()

        chain_before, _ = _observe_receipt_directory_chain(root)
        _hold_existing_receipt_directories(
            guard,
            root=root,
            chain_before=chain_before,
        )
        try:
            _, lock_preflight_reasons, _ = (
                _validate_persistent_lock_state(root)
            )
        except _SnapshotError as exc:
            action, reason = _map_planning_snapshot_error(exc.reason)
            outcome = _preplan_result(
                action=action,
                reason=reason,
                archive_id=archive_id,
                intake_sha256=locked_intake_sha256,
                dry_run=False,
            )
            raise _ApprovalStop
        if lock_preflight_reasons:
            outcome = _preplan_result(
                action="blocked",
                reason=lock_preflight_reasons,
                archive_id=archive_id,
                intake_sha256=locked_intake_sha256,
                dry_run=False,
            )
            raise _ApprovalStop
        locks.validate()
        guard.validate_all()

        locked_row = row_result["row"]
        authority_key_sha256 = contract.authority_key_sha256(
            locked_row["source_provenance"]["observation_evidence_sha256"]
        )
        retained_authorities = _acquire_locked_authorities(
            root,
            guard=guard,
            context_receipt_relative_path=contract.receipt_relative_path(
                authority_key_sha256
            ),
            owned_temp_relative_paths=contract.owned_temp_relative_paths(
                authority_key_sha256
            ),
            state=state,
            win32=win32,
        )
        state.locked_authorities = retained_authorities
        object_authority = retained_authorities.object_manifest

        try:
            context, locked_plan, locked_plan_sha256, locked_reasons = (
                _locked_replan(
                    root,
                    archive_id=archive_id,
                    intake=parsed["intake"],
                    intake_sha256=locked_intake_sha256,
                    row_result=row_result,
                )
            )
        except _SnapshotError as exc:
            action, reason = _map_planning_snapshot_error(exc.reason)
            outcome = _preplan_result(
                action=action,
                reason=reason,
                archive_id=archive_id,
                intake_sha256=locked_intake_sha256,
                dry_run=False,
            )
            raise _ApprovalStop
        except (KeyError, TypeError, ValueError):
            outcome = _preplan_result(
                action="manual_hold",
                reason="private_metadata_authority_state_invalid",
                archive_id=archive_id,
                intake_sha256=locked_intake_sha256,
                dry_run=False,
            )
            raise _ApprovalStop
        except _ApprovalFailure as exc:
            if (
                exc.reason
                != "private_metadata_resource_size_fixed_point_failed"
            ):
                raise
            outcome = _preplan_result(
                action="blocked",
                reason=exc.reason,
                archive_id=archive_id,
                intake_sha256=locked_intake_sha256,
                dry_run=False,
            )
            raise _ApprovalStop

        _verify_locked_authorities_match_context(
            root,
            guard=guard,
            authorities=retained_authorities,
            context=context,
            win32=win32,
        )
        _verify_retained_input_authorities(
            win32,
            guard,
            intake_authority=intake_authority,
            intake_raw=intake_raw,
            object_authority=object_authority,
            context=context,
        )
        locks.validate()
        guard.validate_all()

        if locked_plan_sha256 != expected_plan_sha256:
            if _completed_append_convergence(
                context,
                current_plan=locked_plan,
                incoming_append_plan_sha256=expected_plan_sha256,
            ):
                _verify_completed_convergence_readonly(
                    root,
                    guard=guard,
                    object_authority=object_authority,
                    context=context,
                    state=state,
                    win32=win32,
                )
                outcome = _result_envelope(
                    action="already_applied",
                    archive_id=archive_id,
                    intake_sha256=locked_intake_sha256,
                    plan=locked_plan,
                    plan_sha256=locked_plan_sha256,
                    reasons=[],
                    dry_run=False,
                    receipt_sha256=context.receipt.state.get("sha256"),
                    files_written=[],
                )
            else:
                outcome = _preplan_result(
                    action="blocked",
                    reason="private_metadata_plan_changed",
                    archive_id=archive_id,
                    intake_sha256=locked_intake_sha256,
                    dry_run=False,
                )
        elif locked_plan["action"] in {"manual_hold", "blocked"}:
            outcome = _result_envelope(
                action=locked_plan["action"],
                archive_id=archive_id,
                intake_sha256=locked_intake_sha256,
                plan=locked_plan,
                plan_sha256=locked_plan_sha256,
                reasons=locked_reasons,
                dry_run=False,
                receipt_sha256=context.receipt.state.get("sha256"),
                files_written=[],
            )
        else:
            state.accepted_plan = locked_plan
            state.accepted_plan_sha256 = locked_plan_sha256
            state.context = context
            _initialize_residue_ledger(state, context)
            state.last_verified_authority_state = {
                "append": "before",
                "rollback_required": "before",
                "recovery_required": "after",
                "already_applied": "applied",
            }[locked_plan["action"]]
            state.cleanup_authority_state = (
                state.last_verified_authority_state
            )
            if locked_plan["action"] == "append":
                outcome = _execute_append_approval(
                    root,
                    guard=guard,
                    locks=locks,
                    intake_authority=intake_authority,
                    intake_raw=intake_raw,
                    object_authority=object_authority,
                    reviewed_by=reviewed_by,
                    state=state,
                    win32=win32,
                )
            elif locked_plan["action"] == "rollback_required":
                outcome = _execute_rollback_approval(
                    root,
                    guard=guard,
                    locks=locks,
                    intake_authority=intake_authority,
                    intake_raw=intake_raw,
                    object_authority=object_authority,
                    state=state,
                    win32=win32,
                )
            elif locked_plan["action"] == "recovery_required":
                outcome = _execute_recovery_approval(
                    root,
                    guard=guard,
                    locks=locks,
                    intake_authority=intake_authority,
                    intake_raw=intake_raw,
                    object_authority=object_authority,
                    state=state,
                    win32=win32,
                )
            else:
                outcome = _execute_already_applied_approval(
                    root,
                    guard=guard,
                    locks=locks,
                    intake_authority=intake_authority,
                    intake_raw=intake_raw,
                    object_authority=object_authority,
                    state=state,
                    win32=win32,
                )
    except _ApprovalStop:
        pass
    except _ApprovalFailure as exc:
        pending_failure = exc
        if state.accepted_plan is not None:
            _handle_primary_failure_cleanup(
                state,
                failure=pending_failure,
                root=root,
                guard=guard,
                locks=locks,
                win32=win32,
            )
    except getattr(win32, "Win32MutationFailure", RuntimeError) as exc:
        transferred = exc.take_authorities()
        terminal_released = _handle_terminal_release_failure(
            state,
            exc=exc,
            authorities=transferred,
            root=root,
            guard=guard,
            locks=locks,
            win32=win32,
        )
        if not terminal_released:
            _adopt_failure_authorities(state, transferred)
        pending_failure = _approval_failure_from_win32(state, exc)
        if terminal_released:
            pending_failure.authority_state = (
                state.last_verified_authority_state
            )
        if state.accepted_plan is not None:
            _handle_primary_failure_cleanup(
                state,
                failure=pending_failure,
                root=root,
                guard=guard,
                locks=locks,
                win32=win32,
            )
    except getattr(win32, "Win32SafetyError", RuntimeError) as exc:
        pending_failure = _approval_failure_from_win32(state, exc)
        if state.accepted_plan is not None:
            _handle_primary_failure_cleanup(
                state,
                failure=pending_failure,
                root=root,
                guard=guard,
                locks=locks,
                win32=win32,
            )
    except _SnapshotError as exc:
        if state.accepted_plan is None:
            action, reason = _map_planning_snapshot_error(exc.reason)
            outcome = _preplan_result(
                action=action,
                reason=reason,
                archive_id=archive_id,
                intake_sha256=expected_intake_sha256,
                dry_run=False,
            )
        else:
            pending_failure = _ApprovalFailure(
                "private_metadata_final_verification_failed",
                stage=state.stage,
                authority_state="unknown",
            )
            _attempt_failure_cleanup(
                state,
                root=root,
                guard=guard,
                locks=locks,
                win32=win32,
            )
    except (KeyError, TypeError, ValueError):
        if state.accepted_plan is None:
            outcome = _preplan_result(
                action="manual_hold",
                reason="private_metadata_authority_state_invalid",
                archive_id=archive_id,
                intake_sha256=expected_intake_sha256,
                dry_run=False,
            )
        else:
            pending_failure = _ApprovalFailure(
                "private_metadata_final_verification_failed",
                stage=state.stage,
                authority_state="unknown",
            )
            _attempt_failure_cleanup(
                state,
                root=root,
                guard=guard,
                locks=locks,
                win32=win32,
            )
    finally:
        close_error = _close_tracked_handles(state, win32)
        if close_error is not None:
            release_failure = close_error
        if locks is not None:
            try:
                locks.release()
            except getattr(win32, "Win32SafetyError", RuntimeError) as exc:
                release_authority_state = (
                    state.last_verified_authority_state
                    if not getattr(locks, "_acquired", True)
                    else _release_failure_authority_state(
                        state,
                        exc,
                        syscall_only_operations={
                            "unlock_file_ex",
                            "coordination_lock_close",
                        },
                    )
                )
                if release_failure is None:
                    release_failure = _ApprovalFailure(
                        "private_metadata_lock_identity_changed",
                        stage="guard_or_lock",
                        authority_state=release_authority_state,
                    )
                locks.terminal_release_after_failure()
        if guard is not None:
            try:
                guard.close()
            except getattr(win32, "Win32SafetyError", RuntimeError) as exc:
                release_authority_state = (
                    state.last_verified_authority_state
                    if getattr(guard, "_closed", False)
                    else _release_failure_authority_state(
                        state,
                        exc,
                        syscall_only_operations={"mutation_guard_close"},
                    )
                )
                if release_failure is None:
                    release_failure = _ApprovalFailure(
                        "private_metadata_mutation_guard_identity_changed",
                        stage="guard_or_lock",
                        authority_state=release_authority_state,
                    )
                guard.terminal_release_after_failure()

    failure = pending_failure or release_failure
    if failure is not None:
        if state.last_verified_authority_state == "unknown":
            failure.authority_state = "unknown"
        if state.accepted_plan is None:
            return _preplan_result(
                action="manual_hold",
                reason=failure.reason,
                archive_id=archive_id,
                intake_sha256=expected_intake_sha256,
                dry_run=False,
            )
        cleanup_state, cleanup_incomplete = _attempt_failure_cleanup_result(
            state,
        )
        reasons = [failure.reason]
        if cleanup_incomplete:
            reasons.append("private_metadata_owned_cleanup_incomplete")
        return _execution_hold_result(
            state,
            archive_id=archive_id,
            intake_sha256=expected_intake_sha256,
            reasons=reasons,
            stage=failure.stage,
            authority_state=failure.authority_state,
            cleanup_state=cleanup_state,
        )
    if outcome is None:
        return _preplan_result(
            action="manual_hold",
            reason="private_metadata_final_verification_failed",
            archive_id=archive_id,
            intake_sha256=expected_intake_sha256,
            dry_run=False,
        )
    return outcome


class _ApprovalStop(Exception):
    """Internal non-error control transfer to the single return boundary."""


class _ApprovalFailure(RuntimeError):
    def __init__(
        self,
        reason: str,
        *,
        stage: str,
        authority_state: str,
    ) -> None:
        self.reason = reason
        self.stage = stage
        self.authority_state = authority_state
        super().__init__(reason)


@dataclass
class _ApprovalExecutionState:
    accepted_plan: dict[str, Any] | None = None
    accepted_plan_sha256: str | None = None
    context: _PlanningContext | None = None
    stage: str = "guard_or_lock"
    last_verified_authority_state: str = "unknown"
    cleanup_authority_state: str = "unknown"
    handles: list[Any] = None  # type: ignore[assignment]
    residue_obligations: list[str] = None  # type: ignore[assignment]
    cleanup_state: str = "not_required"
    locked_authorities: "_LockedAuthoritySet | None" = None
    residue_ledger: dict[str, "_ResidueEntry"] = None  # type: ignore[assignment]
    cleanup_incomplete: bool = False
    applied_object_authority: Any | None = None
    applied_manifest_authority: Any | None = None
    applied_receipt_authority: Any | None = None
    applied_expected_receipt: dict[str, Any] | None = None
    terminal_release_occurred: bool = False

    def __post_init__(self) -> None:
        if self.handles is None:
            self.handles = []
        if self.residue_obligations is None:
            self.residue_obligations = []
        if self.residue_ledger is None:
            self.residue_ledger = {}


@dataclass
class _ResidueEntry:
    """One exact writer-owned name and the authority that proves its state."""

    role: str
    relative_path: str
    state: str = "not_arisen"
    bound: Any | None = None


def _initialize_residue_ledger(
    state: _ApprovalExecutionState,
    context: _PlanningContext,
) -> None:
    state.residue_ledger = {
        "journal_temp": _ResidueEntry(
            "journal_temp",
            context.owned_temp_relative_paths[0],
        ),
        "manifest_temp": _ResidueEntry(
            "manifest_temp",
            context.owned_temp_relative_paths[1],
        ),
        "receipt_temp": _ResidueEntry(
            "receipt_temp",
            context.owned_temp_relative_paths[2],
        ),
        "fixed_journal": _ResidueEntry(
            "fixed_journal",
            contract.JOURNAL_PATH,
        ),
    }


def _track_handle(state: _ApprovalExecutionState, bound: Any | None) -> None:
    if bound is not None and all(
        existing is not bound for existing in state.handles
    ):
        state.handles.append(bound)


def _record_residue_authority(
    state: _ApprovalExecutionState,
    role: str,
    bound: Any,
    *,
    name_state: str = "owned_present",
) -> None:
    entry = state.residue_ledger.get(role)
    if entry is None:
        return
    entry.state = name_state
    entry.bound = bound
    _track_handle(state, bound)
    if entry.relative_path not in state.residue_obligations:
        state.residue_obligations.append(entry.relative_path)


def _record_residue_absent(
    state: _ApprovalExecutionState,
    role: str,
) -> None:
    entry = state.residue_ledger.get(role)
    if entry is None:
        return
    entry.state = "absent_proved"
    entry.bound = None
    if entry.relative_path in state.residue_obligations:
        state.residue_obligations.remove(entry.relative_path)


def _adopt_failure_authorities(
    state: _ApprovalExecutionState,
    authorities: tuple[Any, ...],
) -> None:
    for transfer in authorities:
        bound = getattr(transfer, "bound", None)
        role = getattr(transfer, "role", "")
        name_state = getattr(
            transfer,
            "name_state",
            "preserved_unverified",
        )
        _track_handle(state, bound)
        if (
            state.last_verified_authority_state == "applied"
            and bound is not None
        ):
            if role == "object_manifest":
                state.applied_object_authority = bound
            elif role == "private_manifest":
                state.applied_manifest_authority = bound
            elif role == "final_receipt":
                state.applied_receipt_authority = bound
        if role == "private_manifest" and name_state == "renamed_final":
            _record_residue_absent(state, "manifest_temp")
        if role in state.residue_ledger and bound is not None:
            _record_residue_authority(
                state,
                role,
                bound,
                name_state=name_state,
            )
            if role == "journal_temp" and name_state == "twin_published":
                fixed = state.residue_ledger.get("fixed_journal")
                if fixed is not None:
                    fixed.state = "twin_published"
                    fixed.bound = None
                    if (
                        fixed.relative_path
                        not in state.residue_obligations
                    ):
                        state.residue_obligations.append(
                            fixed.relative_path
                        )


@dataclass
class _LockedAuthoritySet:
    """Approval-only Win32 authorities retained across plan acceptance."""

    object_manifest: Any
    object_manifest_raw: bytes
    private_manifest: Any | None
    private_manifest_raw: bytes | None
    journal: Any | None
    journal_raw: bytes | None
    receipt: Any | None
    receipt_raw: bytes | None
    temps: dict[str, Any | None]
    temp_raw: dict[str, bytes | None]


def _approval_intake_preflight(
    root: Path,
    *,
    intake_relative_path: str,
) -> dict[str, Any]:
    path = _safe_archive_path(
        root,
        intake_relative_path,
        final_may_absent=False,
    )
    if path is None:
        return {
            "reason": "private_metadata_intake_path_unsafe",
            "intake_sha256": None,
        }
    try:
        snapshot = _read_regular_snapshot(
            root,
            path,
            maximum_bytes=contract.INTAKE_MAX_BYTES,
            allow_absent=False,
            classify=lambda _: 1,
        )
    except _SnapshotError:
        return {
            "reason": "private_metadata_intake_unavailable",
            "intake_sha256": None,
        }
    if snapshot.raw is None:
        reason = (
            "private_metadata_intake_invalid"
            if snapshot.state.get("byte_count") is not None
            else "private_metadata_intake_unavailable"
        )
        return {"reason": reason, "intake_sha256": None}
    intake_sha256 = contract.sha256_digest(snapshot.raw)
    parsed = contract.parse_private_metadata_intake_bytes(snapshot.raw)
    return {
        "reason": (
            None if parsed["accepted"] else "private_metadata_intake_invalid"
        ),
        "intake_sha256": intake_sha256,
    }


def _hold_existing_receipt_directories(
    guard: Any,
    *,
    root: Path,
    chain_before: dict[str, Any],
) -> None:
    values = (
        ("receipts_root", root / "receipts"),
        ("objects_parent", root / "receipts" / "objects"),
        (
            "private_receipt_directory",
            root / "receipts" / "objects" / "private-source-metadata",
        ),
    )
    for key, path in values:
        if chain_before[key]["state"] == "present":
            guard.hold_directory(path)
    guard.validate_all()


def _locked_replan(
    root: Path,
    *,
    archive_id: str,
    intake: dict[str, Any],
    intake_sha256: str,
    row_result: dict[str, Any],
) -> tuple[_PlanningContext, dict[str, Any], str, list[str]]:
    context, manifest_entries_with_locks, _ = _build_planning_context(
        root,
        archive_id=archive_id,
        intake=intake,
        intake_sha256=intake_sha256,
        row_result=row_result,
    )
    plan, plan_reasons = _plan_from_context(
        context,
        manifest_entries_with_locks=manifest_entries_with_locks,
    )
    if plan is None:
        raise _ApprovalFailure(
            plan_reasons[0]
            if plan_reasons
            else "private_metadata_resource_size_fixed_point_failed",
            stage="guard_or_lock",
            authority_state="unknown",
        )
    plan_sha256 = contract.sha256_digest(
        contract.canonical_json_bytes(plan)
    )
    return context, plan, plan_sha256, _unique(
        [*context.reasons, *plan_reasons]
    )


def _open_optional_locked_authority(
    root: Path,
    *,
    guard: Any,
    relative_path: str,
    maximum_bytes: int,
    allowed_link_counts: tuple[int, ...],
    state: _ApprovalExecutionState,
    win32: Any,
) -> tuple[Any | None, bytes | None]:
    path = root / PurePosixPath(relative_path)
    if not guard.is_held(path.parent):
        return None, None
    if win32.path_is_absent(
        guard,
        path,
        reason="private_metadata_authority_state_unavailable",
        operation="locked_authority_absence",
    ):
        return None, None
    bound = win32.open_bound_file(
        guard,
        relative_path,
        profile=win32.FileHandleProfile.NARROW_READ,
        expected_link_count=None,
        reason="private_metadata_authority_state_unavailable",
    )
    state.handles.append(bound)
    information = bound.information(
        reason="private_metadata_authority_state_unavailable",
        operation="locked_authority_information",
    )
    if information.link_count not in allowed_link_counts:
        raise _SnapshotError("unexpected_hardlink")
    if information.byte_count > maximum_bytes:
        raise _SnapshotError("authority_state_unavailable")
    bound.expected_link_count = information.link_count
    raw = bound.read_all(
        max_bytes=maximum_bytes,
        reason="private_metadata_authority_state_unavailable",
    )
    win32.validate_bound_path(
        guard,
        bound,
        expected_link_count=information.link_count,
        reason="private_metadata_authority_state_unavailable",
    )
    return bound, raw


def _acquire_locked_authorities(
    root: Path,
    *,
    guard: Any,
    context_receipt_relative_path: str,
    owned_temp_relative_paths: list[str],
    state: _ApprovalExecutionState,
    win32: Any,
) -> _LockedAuthoritySet:
    """Acquire all current transaction authorities under the lock pair."""

    object_manifest = win32.open_bound_file(
        guard,
        contract.OBJECT_MANIFEST_PATH,
        profile=win32.FileHandleProfile.AUTHORITY_READ,
        expected_link_count=1,
        reason="private_metadata_authority_state_unavailable",
    )
    state.handles.append(object_manifest)
    object_raw = object_manifest.read_all(
        max_bytes=OBJECT_MANIFEST_MAX_BYTES,
        reason="private_metadata_authority_state_unavailable",
    )
    win32.validate_bound_path(
        guard,
        object_manifest,
        expected_link_count=1,
        reason="private_metadata_authority_state_unavailable",
    )

    private_manifest, private_raw = _open_optional_locked_authority(
        root,
        guard=guard,
        relative_path=contract.PRIVATE_MANIFEST_PATH,
        maximum_bytes=PRIVATE_MANIFEST_MAX_BYTES,
        allowed_link_counts=(1,),
        state=state,
        win32=win32,
    )
    journal, journal_raw = _open_optional_locked_authority(
        root,
        guard=guard,
        relative_path=contract.JOURNAL_PATH,
        maximum_bytes=PRIVATE_JOURNAL_MAX_BYTES,
        allowed_link_counts=(1, 2),
        state=state,
        win32=win32,
    )
    receipt, receipt_raw = _open_optional_locked_authority(
        root,
        guard=guard,
        relative_path=context_receipt_relative_path,
        maximum_bytes=PRIVATE_RECEIPT_MAX_BYTES,
        allowed_link_counts=(1, 2),
        state=state,
        win32=win32,
    )
    temp_authorities: dict[str, Any | None] = {}
    temp_raw: dict[str, bytes | None] = {}
    for key, relative, maximum, links in zip(
        ("journal_temp", "manifest_temp", "receipt_temp"),
        owned_temp_relative_paths,
        (
            PRIVATE_JOURNAL_MAX_BYTES,
            PRIVATE_MANIFEST_MAX_BYTES,
            PRIVATE_RECEIPT_MAX_BYTES,
        ),
        ((1, 2), (1,), (1, 2)),
    ):
        authority, raw = _open_optional_locked_authority(
            root,
            guard=guard,
            relative_path=relative,
            maximum_bytes=maximum,
            allowed_link_counts=links,
            state=state,
            win32=win32,
        )
        temp_authorities[key] = authority
        temp_raw[key] = raw
    guard.validate_all()
    return _LockedAuthoritySet(
        object_manifest=object_manifest,
        object_manifest_raw=object_raw,
        private_manifest=private_manifest,
        private_manifest_raw=private_raw,
        journal=journal,
        journal_raw=journal_raw,
        receipt=receipt,
        receipt_raw=receipt_raw,
        temps=temp_authorities,
        temp_raw=temp_raw,
    )


def _verify_locked_authorities_match_context(
    root: Path,
    *,
    guard: Any,
    authorities: _LockedAuthoritySet,
    context: _PlanningContext,
    win32: Any,
) -> None:
    pairs = (
        (
            authorities.object_manifest,
            authorities.object_manifest_raw,
            context.object_manifest,
            contract.OBJECT_MANIFEST_PATH,
        ),
        (
            authorities.private_manifest,
            authorities.private_manifest_raw,
            context.private_manifest,
            contract.PRIVATE_MANIFEST_PATH,
        ),
        (
            authorities.journal,
            authorities.journal_raw,
            context.journal,
            contract.JOURNAL_PATH,
        ),
        (
            authorities.receipt,
            authorities.receipt_raw,
            context.receipt,
            context.receipt_relative_path,
        ),
        *(
            (
                authorities.temps[key],
                authorities.temp_raw[key],
                context.temp_snapshots[key],
                relative,
            )
            for key, relative in zip(
                ("journal_temp", "manifest_temp", "receipt_temp"),
                context.owned_temp_relative_paths,
            )
        ),
    )
    for bound, raw, snapshot, relative in pairs:
        if bound is None:
            if snapshot.state["state"] != "absent":
                raise _SnapshotError("authority_state_unavailable")
            parent = root / PurePosixPath(relative).parent
            if guard.is_held(parent) and not win32.path_is_absent(
                guard,
                root / PurePosixPath(relative),
                reason="private_metadata_authority_state_unavailable",
                operation="locked_authority_absence_recheck",
            ):
                raise _SnapshotError("authority_state_unavailable")
            continue
        if snapshot.state["state"] not in {"present", "present_invalid"}:
            raise _SnapshotError("authority_state_unavailable")
        information = win32.validate_bound_path(
            guard,
            bound,
            expected_link_count=bound.expected_link_count,
            reason="private_metadata_authority_state_unavailable",
        )
        if (
            raw != snapshot.raw
            or snapshot.identity is None
            or bound.identity.file_index != snapshot.identity[1]
            or information.byte_count != snapshot.state["byte_count"]
            or information.link_count != snapshot.state["link_count"]
            or contract.sha256_digest(raw or b"")
            != snapshot.state["sha256"]
        ):
            raise _SnapshotError("authority_state_unavailable")
    guard.validate_all()


def _verify_retained_input_authorities(
    win32: Any,
    guard: Any,
    *,
    intake_authority: Any,
    intake_raw: bytes,
    object_authority: Any,
    context: _PlanningContext,
) -> None:
    win32.validate_bound_path(
        guard,
        intake_authority,
        expected_link_count=1,
        reason="private_metadata_mutation_guard_identity_changed",
    )
    if intake_authority.read_all(
        max_bytes=contract.INTAKE_MAX_BYTES,
        reason="private_metadata_mutation_guard_identity_changed",
    ) != intake_raw:
        raise _ApprovalFailure(
            "private_metadata_mutation_guard_identity_changed",
            stage="guard_or_lock",
            authority_state="unknown",
        )
    _verify_object_authority(
        win32,
        guard,
        object_authority=object_authority,
        context=context,
    )


def _verify_object_authority(
    win32: Any,
    guard: Any,
    *,
    object_authority: Any,
    context: _PlanningContext,
) -> None:
    win32.validate_bound_path(
        guard,
        object_authority,
        expected_link_count=1,
        reason="private_metadata_object_manifest_changed_before_commit",
    )
    expected = context.object_manifest.raw
    if expected is None:
        raise _ApprovalFailure(
            "private_metadata_object_manifest_changed_before_commit",
            stage="manifest_replacement",
            authority_state="unknown",
        )
    actual = object_authority.read_all(
        max_bytes=OBJECT_MANIFEST_MAX_BYTES,
        reason="private_metadata_object_manifest_changed_before_commit",
    )
    if (
        actual != expected
        or contract.sha256_digest(actual)
        != context.object_manifest.state["sha256"]
    ):
        raise _ApprovalFailure(
            "private_metadata_object_manifest_changed_before_commit",
            stage="manifest_replacement",
            authority_state="unknown",
        )


def _completed_append_convergence(
    context: _PlanningContext,
    *,
    current_plan: dict[str, Any],
    incoming_append_plan_sha256: str,
) -> bool:
    receipt = context.receipt_document
    return bool(
        current_plan["action"] == "already_applied"
        and context.authority_chain_validation == "valid_complete"
        and context.prior_row_state == "exact"
        and context.receipt_inventory_state == "exact"
        and context.existing_exact_row_count == 1
        and context.exact_receipt_count == 1
        and receipt is not None
        and receipt.get("plan_binding", {}).get("action") == "append"
        and receipt.get("plan_sha256") == incoming_append_plan_sha256
        and contract.sha256_digest(
            contract.canonical_json_bytes(receipt["plan_binding"])
        )
        == incoming_append_plan_sha256
    )


def _verify_completed_convergence_readonly(
    root: Path,
    *,
    guard: Any,
    object_authority: Any,
    context: _PlanningContext,
    state: _ApprovalExecutionState,
    win32: Any,
) -> None:
    """Retain every completed authority without cleaning converged residue."""

    if context.private_manifest.raw is None or context.receipt.raw is None:
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="final_verification",
            authority_state="unknown",
        )
    _verify_object_authority(
        win32,
        guard,
        object_authority=object_authority,
        context=context,
    )
    _open_exact_bound(
        win32,
        guard,
        relative_path=contract.PRIVATE_MANIFEST_PATH,
        expected=context.private_manifest.raw,
        profile=win32.FileHandleProfile.NARROW_READ,
        expected_link_count=1,
        reason="private_metadata_final_verification_failed",
        state=state,
    )
    receipt_link_count = int(context.receipt.state["link_count"])
    receipt_final = _open_exact_bound(
        win32,
        guard,
        relative_path=context.receipt_relative_path,
        expected=context.receipt.raw,
        profile=win32.FileHandleProfile.NARROW_READ,
        expected_link_count=receipt_link_count,
        reason="private_metadata_final_verification_failed",
        state=state,
    )
    journal_link_count = context.journal.state.get("link_count")
    if context.journal.raw is not None:
        _open_exact_bound(
            win32,
            guard,
            relative_path=contract.JOURNAL_PATH,
            expected=context.journal.raw,
            profile=win32.FileHandleProfile.NARROW_READ,
            expected_link_count=int(journal_link_count),
            reason="private_metadata_final_verification_failed",
            state=state,
        )
    elif not win32.path_is_absent(
        guard,
        root / PurePosixPath(contract.JOURNAL_PATH),
        reason="private_metadata_final_verification_failed",
        operation="convergence_journal_absence",
    ):
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="final_verification",
            authority_state="unknown",
        )
    for key, relative in zip(
        ("journal_temp", "manifest_temp", "receipt_temp"),
        context.owned_temp_relative_paths,
    ):
        snapshot = context.temp_snapshots[key]
        if snapshot.state["state"] == "absent":
            if not win32.path_is_absent(
                guard,
                root / PurePosixPath(relative),
                reason="private_metadata_final_verification_failed",
                operation="convergence_temp_absence",
            ):
                raise _ApprovalFailure(
                    "private_metadata_final_verification_failed",
                    stage="final_verification",
                    authority_state="unknown",
                )
            continue
        if (
            key != "receipt_temp"
            or snapshot.raw is None
            or snapshot.identity is None
            or receipt_link_count != 2
        ):
            raise _ApprovalFailure(
                "private_metadata_final_verification_failed",
                stage="final_verification",
                authority_state="unknown",
            )
        receipt_temp = _open_exact_bound(
            win32,
            guard,
            relative_path=relative,
            expected=snapshot.raw,
            profile=win32.FileHandleProfile.TRANSITIONAL_READ,
            expected_link_count=2,
            reason="private_metadata_unexpected_hardlink",
            state=state,
        )
        if receipt_temp.identity != receipt_final.identity:
            raise _ApprovalFailure(
                "private_metadata_unexpected_hardlink",
                stage="final_verification",
                authority_state="unknown",
            )
    guard.validate_all()


def _bootstrap_receipt_directories(
    guard: Any,
    *,
    root: Path,
    plan: dict[str, Any],
    win32: Any,
) -> list[str]:
    created: list[str] = []
    paths = (
        ("receipts_root", "receipts"),
        ("objects_parent", "receipts/objects"),
        (
            "private_receipt_directory",
            "receipts/objects/private-source-metadata",
        ),
    )
    for key, relative in paths:
        before = plan["receipt_directory_chain_before"][key]["state"]
        if before == "absent":
            win32.create_guarded_directory(guard, root / PurePosixPath(relative))
            created.append(relative)
        elif not guard.is_held(root / PurePosixPath(relative)):
            raise _ApprovalFailure(
                "private_metadata_mutation_guard_identity_changed",
                stage="receipt_directory_bootstrap",
                authority_state="before",
            )
    observed_before, observed_after = _observe_receipt_directory_chain(root)
    if (
        observed_before != plan["receipt_directory_chain_after"]
        or observed_after != plan["receipt_directory_chain_after"]
    ):
        raise _ApprovalFailure(
            "private_metadata_receipt_directory_bootstrap_failed",
            stage="receipt_directory_bootstrap",
            authority_state="before",
        )
    guard.validate_all()
    return created


def _verify_bound_bytes(
    win32: Any,
    guard: Any,
    bound: Any,
    *,
    expected: bytes,
    reason: str,
    expected_link_count: int = 1,
) -> None:
    win32.validate_bound_path(
        guard,
        bound,
        expected_link_count=expected_link_count,
        reason=reason,
    )
    if bound.read_all(
        max_bytes=len(expected),
        reason=reason,
    ) != expected:
        raise _ApprovalFailure(
            reason,
            stage="final_verification",
            authority_state="unknown",
        )
    bound.bind_proved_content(
        expected_byte_count=len(expected),
        expected_sha256=(
            "sha256:" + hashlib.sha256(expected).hexdigest()
        ),
        reason=reason,
    )


def _open_exact_bound(
    win32: Any,
    guard: Any,
    *,
    relative_path: str,
    expected: bytes,
    profile: Any,
    expected_link_count: int,
    reason: str,
    state: _ApprovalExecutionState,
) -> Any:
    bound = win32.open_bound_file(
        guard,
        relative_path,
        profile=profile,
        expected_link_count=expected_link_count,
        reason=reason,
    )
    state.handles.append(bound)
    _verify_bound_bytes(
        win32,
        guard,
        bound,
        expected=expected,
        reason=reason,
        expected_link_count=expected_link_count,
    )
    return bound


def _retained_authority_for_relative(
    state: _ApprovalExecutionState,
    context: _PlanningContext,
    relative_path: str,
) -> Any | None:
    authorities = state.locked_authorities
    if authorities is None:
        return None
    if relative_path == contract.OBJECT_MANIFEST_PATH:
        return authorities.object_manifest
    if relative_path == contract.PRIVATE_MANIFEST_PATH:
        return authorities.private_manifest
    if relative_path == contract.JOURNAL_PATH:
        return authorities.journal
    if relative_path == context.receipt_relative_path:
        return authorities.receipt
    for key, relative in zip(
        ("journal_temp", "manifest_temp", "receipt_temp"),
        context.owned_temp_relative_paths,
    ):
        if relative_path == relative:
            return authorities.temps[key]
    return None


def _require_retained_exact_bound(
    win32: Any,
    guard: Any,
    *,
    relative_path: str,
    expected: bytes,
    expected_link_count: int,
    state: _ApprovalExecutionState,
    context: _PlanningContext,
    reason: str,
) -> Any:
    bound = _retained_authority_for_relative(
        state,
        context,
        relative_path,
    )
    if bound is None:
        raise _ApprovalFailure(
            reason,
            stage=state.stage,
            authority_state="unknown",
        )
    _verify_bound_bytes(
        win32,
        guard,
        bound,
        expected=expected,
        reason=reason,
        expected_link_count=expected_link_count,
    )
    return bound


def _assert_manifest_temp_source(
    source: Any,
    *,
    root: Path,
    plan: dict[str, Any],
    win32: Any,
) -> str:
    authority_key_hex = plan["authority_key_sha256"][7:]
    expected_relative = win32.owned_temp_relative_path(
        win32.OwnedTempKind.MANIFEST,
        authority_key_hex,
    )
    actual_relative = source.path.relative_to(root).as_posix()
    if (
        actual_relative != expected_relative
        or expected_relative != contract.owned_temp_relative_paths(
            plan["authority_key_sha256"]
        )[1]
    ):
        raise _ApprovalFailure(
            "private_metadata_owned_temp_substituted",
            stage="manifest_replacement",
            authority_state="before",
        )
    return authority_key_hex


def _open_private_manifest_before_authority(
    root: Path,
    *,
    guard: Any,
    context: _PlanningContext,
    state: _ApprovalExecutionState,
    win32: Any,
) -> Any | None:
    before = context.private_manifest
    retained = (
        state.locked_authorities.private_manifest
        if state.locked_authorities is not None
        else None
    )
    if before.state["state"] == "absent":
        if retained is not None:
            raise _ApprovalFailure(
                "private_metadata_manifest_replacement_failed",
                stage="manifest_replacement",
                authority_state="unknown",
            )
        if not win32.path_is_absent(
            guard,
            root / PurePosixPath(contract.PRIVATE_MANIFEST_PATH),
            reason="private_metadata_manifest_replacement_failed",
            operation="manifest_before_absence",
        ):
            raise _ApprovalFailure(
                "private_metadata_manifest_replacement_failed",
                stage="manifest_replacement",
                authority_state="unknown",
        )
        return None
    if before.raw is None:
        raise _ApprovalFailure(
            "private_metadata_manifest_replacement_failed",
            stage="manifest_replacement",
            authority_state="unknown",
        )
    if retained is None:
        raise _ApprovalFailure(
            "private_metadata_manifest_replacement_failed",
            stage="manifest_replacement",
            authority_state="unknown",
        )
    _verify_bound_bytes(
        win32,
        guard,
        retained,
        expected=before.raw,
        reason="private_metadata_manifest_replacement_failed",
        expected_link_count=1,
    )
    return retained


def _execute_append_approval(
    root: Path,
    *,
    guard: Any,
    locks: Any,
    intake_authority: Any,
    intake_raw: bytes,
    object_authority: Any,
    reviewed_by: str,
    state: _ApprovalExecutionState,
    win32: Any,
) -> dict[str, Any]:
    del intake_authority, intake_raw
    plan = state.accepted_plan
    context = state.context
    assert plan is not None and context is not None

    state.stage = "manifest_replacement"
    _verify_object_authority(
        win32,
        guard,
        object_authority=object_authority,
        context=context,
    )
    locks.validate()
    guard.validate_all()

    state.stage = "receipt_directory_bootstrap"
    _bootstrap_receipt_directories(
        guard,
        root=root,
        plan=plan,
        win32=win32,
    )
    locks.validate()

    receipt = _receipt_for_append_plan(
        plan,
        reviewed_by=reviewed_by,
        privacy_class=context.row["privacy_class"],
    )
    if not contract.validate_private_metadata_write_receipt_semantics(
        receipt,
        canonical_row=context.row,
    )["accepted"]:
        raise _ApprovalFailure(
            "private_metadata_receipt_plan_authority_chain_mismatch",
            stage="semantic_verification",
            authority_state="before",
        )
    journal = _journal_for_receipt(receipt)
    if not contract.validate_private_metadata_write_journal_semantics(
        journal,
        canonical_row=context.row,
    )["accepted"]:
        raise _ApprovalFailure(
            "private_metadata_journal_cross_field_mismatch",
            stage="semantic_verification",
            authority_state="before",
        )
    receipt_bytes = contract.stored_json_bytes(receipt)
    journal_bytes = contract.stored_json_bytes(journal)
    resource = plan["resource_binding"]
    if (
        len(receipt_bytes) > resource["prospective_receipt_bytes"]
        or len(journal_bytes) > resource["prospective_journal_bytes"]
    ):
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="semantic_verification",
            authority_state="before",
        )

    authority_key_hex = plan["authority_key_sha256"][7:]
    state.stage = "owned_temp_materialization"
    journal_source = win32.materialize_owned_temp(
        guard,
        kind=win32.OwnedTempKind.JOURNAL,
        authority_key_hex=authority_key_hex,
        data=journal_bytes,
    )
    _record_residue_authority(state, "journal_temp", journal_source)

    state.stage = "hardlink_publication"
    journal_residue = win32.publish_hard_link(
        guard,
        journal_source,
        destination_relative_path=contract.JOURNAL_PATH,
        survivor_profile=win32.FileHandleProfile.RESIDUE_DISPOSITION,
        expected_bytes=journal_bytes,
    )
    _track_handle(state, journal_residue)
    _record_residue_absent(state, "journal_temp")
    _record_residue_authority(state, "fixed_journal", journal_residue)

    after_bytes = (context.private_manifest.raw or b"") + context.stored_row
    if (
        contract.sha256_digest(after_bytes)
        != plan["private_manifest_after"]["sha256"]
        or len(after_bytes) != plan["private_manifest_after"]["byte_count"]
    ):
        raise _ApprovalFailure(
            "private_metadata_journal_cross_field_mismatch",
            stage="semantic_verification",
            authority_state="before",
        )

    state.stage = "owned_temp_materialization"
    manifest_source = win32.materialize_owned_temp(
        guard,
        kind=win32.OwnedTempKind.MANIFEST,
        authority_key_hex=authority_key_hex,
        data=after_bytes,
    )
    _record_residue_authority(state, "manifest_temp", manifest_source)
    before_authority = _open_private_manifest_before_authority(
        root,
        guard=guard,
        context=context,
        state=state,
        win32=win32,
    )

    state.stage = "manifest_replacement"
    _verify_object_authority(
        win32,
        guard,
        object_authority=object_authority,
        context=context,
    )
    locks.validate()
    guard.validate_all()
    bound_authority_key_hex = _assert_manifest_temp_source(
        manifest_source,
        root=root,
        plan=plan,
        win32=win32,
    )
    manifest_final = win32.replace_private_manifest(
        guard,
        manifest_source,
        authority_key_hex=bound_authority_key_hex,
        replace_if_exists=(
            context.private_manifest.state["state"] == "present"
        ),
        before_authority=before_authority,
        expected_bytes=after_bytes,
    )
    _track_handle(state, manifest_final)
    _record_residue_absent(state, "manifest_temp")
    state.last_verified_authority_state = "after"
    state.cleanup_authority_state = "after"

    state.stage = "owned_temp_materialization"
    receipt_source = win32.materialize_owned_temp(
        guard,
        kind=win32.OwnedTempKind.RECEIPT,
        authority_key_hex=authority_key_hex,
        data=receipt_bytes,
    )
    _record_residue_authority(state, "receipt_temp", receipt_source)
    state.stage = "hardlink_publication"
    receipt_final = win32.publish_hard_link(
        guard,
        receipt_source,
        destination_relative_path=context.receipt_relative_path,
        survivor_profile=win32.FileHandleProfile.NARROW_READ,
        expected_bytes=receipt_bytes,
    )
    _track_handle(state, receipt_final)
    _record_residue_absent(state, "receipt_temp")

    state.stage = "final_verification"
    _verify_applied_authority(
        root,
        guard=guard,
        object_authority=object_authority,
        context=context,
        manifest_authority=manifest_final,
        receipt_authority=receipt_final,
        expected_receipt=receipt,
        journal_authority=journal_residue,
        expected_journal=journal,
        win32=win32,
    )
    state.applied_object_authority = object_authority
    state.applied_manifest_authority = manifest_final
    state.applied_receipt_authority = receipt_final
    state.applied_expected_receipt = receipt
    state.last_verified_authority_state = "applied"
    state.cleanup_authority_state = "applied"

    state.stage = "residue_disposition"
    win32.dispose_bound_residue(guard, journal_residue, locks=locks)
    _record_residue_absent(state, "fixed_journal")
    state.cleanup_state = "completed"

    state.stage = "final_verification"
    clean_context = _verify_terminal_replan(
        root,
        state=state,
        expected_action="already_applied",
    )
    locks.validate()
    guard.validate_all()
    return _result_envelope(
        action="applied",
        archive_id=plan["archive_id"],
        intake_sha256=plan["intake_sha256"],
        plan=plan,
        plan_sha256=state.accepted_plan_sha256,
        reasons=[],
        dry_run=False,
        receipt_sha256=clean_context.receipt.state["sha256"],
        files_written=[
            contract.PRIVATE_MANIFEST_PATH,
            context.receipt_relative_path,
        ],
    )


def _execute_recovery_approval(
    root: Path,
    *,
    guard: Any,
    locks: Any,
    intake_authority: Any,
    intake_raw: bytes,
    object_authority: Any,
    state: _ApprovalExecutionState,
    win32: Any,
) -> dict[str, Any]:
    del intake_authority, intake_raw
    plan = state.accepted_plan
    context = state.context
    assert plan is not None and context is not None
    journal = context.journal_document
    if journal is None or context.journal.raw is None:
        raise _ApprovalFailure(
            "private_metadata_journal_cross_field_mismatch",
            stage="semantic_verification",
            authority_state="after",
        )
    journal_bytes = context.journal.raw
    journal_narrow = _require_retained_exact_bound(
        win32,
        guard,
        relative_path=contract.JOURNAL_PATH,
        expected=journal_bytes,
        expected_link_count=1,
        reason="private_metadata_final_verification_failed",
        state=state,
        context=context,
    )
    journal_residue = win32.handoff_to_residue_authority(
        guard,
        journal_narrow,
        reason="private_metadata_final_verification_failed",
    )
    _record_residue_authority(state, "fixed_journal", journal_residue)

    receipt_bytes = contract.stored_json_bytes(journal["receipt_document"])
    receipt_temp_snapshot = context.temp_snapshots["receipt_temp"]
    if receipt_temp_snapshot.state["state"] != "absent":
        state.stage = "residue_disposition"
        residue = _open_owned_prefix_residue(
            win32,
            guard,
            relative_path=context.owned_temp_relative_paths[2],
            expected=receipt_bytes,
            state=state,
            context=context,
        )
        _record_residue_authority(state, "receipt_temp", residue)
        win32.dispose_bound_residue(guard, residue, locks=locks)
        _record_residue_absent(state, "receipt_temp")

    _verify_object_authority(
        win32,
        guard,
        object_authority=object_authority,
        context=context,
    )
    manifest_final = _require_retained_exact_bound(
        win32,
        guard,
        relative_path=contract.PRIVATE_MANIFEST_PATH,
        expected=context.private_manifest.raw or b"",
        expected_link_count=1,
        reason="private_metadata_final_verification_failed",
        state=state,
        context=context,
    )

    authority_key_hex = plan["authority_key_sha256"][7:]
    state.stage = "owned_temp_materialization"
    receipt_source = win32.materialize_owned_temp(
        guard,
        kind=win32.OwnedTempKind.RECEIPT,
        authority_key_hex=authority_key_hex,
        data=receipt_bytes,
    )
    _record_residue_authority(state, "receipt_temp", receipt_source)
    state.stage = "hardlink_publication"
    receipt_final = win32.publish_hard_link(
        guard,
        receipt_source,
        destination_relative_path=context.receipt_relative_path,
        survivor_profile=win32.FileHandleProfile.NARROW_READ,
        expected_bytes=receipt_bytes,
    )
    _track_handle(state, receipt_final)
    _record_residue_absent(state, "receipt_temp")

    state.stage = "final_verification"
    _verify_applied_authority(
        root,
        guard=guard,
        object_authority=object_authority,
        context=context,
        manifest_authority=manifest_final,
        receipt_authority=receipt_final,
        expected_receipt=journal["receipt_document"],
        journal_authority=journal_residue,
        expected_journal=journal,
        win32=win32,
    )
    state.applied_object_authority = object_authority
    state.applied_manifest_authority = manifest_final
    state.applied_receipt_authority = receipt_final
    state.applied_expected_receipt = journal["receipt_document"]
    state.last_verified_authority_state = "applied"
    state.cleanup_authority_state = "applied"

    state.stage = "residue_disposition"
    win32.dispose_bound_residue(guard, journal_residue, locks=locks)
    _record_residue_absent(state, "fixed_journal")
    state.cleanup_state = "completed"

    state.stage = "final_verification"
    clean_context = _verify_terminal_replan(
        root,
        state=state,
        expected_action="already_applied",
    )
    locks.validate()
    guard.validate_all()
    return _result_envelope(
        action="recovery_completed",
        archive_id=plan["archive_id"],
        intake_sha256=plan["intake_sha256"],
        plan=plan,
        plan_sha256=state.accepted_plan_sha256,
        reasons=[],
        dry_run=False,
        receipt_sha256=clean_context.receipt.state["sha256"],
        files_written=[context.receipt_relative_path],
    )


def _revalidate_rollback_before_journal_disposition(
    root: Path,
    *,
    guard: Any,
    locks: Any,
    object_authority: Any,
    journal_authority: Any,
    expected_journal_bytes: bytes,
    state: _ApprovalExecutionState,
    context: _PlanningContext,
    win32: Any,
) -> None:
    """Re-prove rollback authority immediately before its final delete."""

    state.stage = "final_verification"
    try:
        _verify_object_authority(
            win32,
            guard,
            object_authority=object_authority,
            context=context,
        )
        if context.private_manifest.state["state"] == "present":
            _require_retained_exact_bound(
                win32,
                guard,
                relative_path=contract.PRIVATE_MANIFEST_PATH,
                expected=context.private_manifest.raw or b"",
                expected_link_count=1,
                reason="private_metadata_final_verification_failed",
                state=state,
                context=context,
            )
        elif not win32.path_is_absent(
            guard,
            root / PurePosixPath(contract.PRIVATE_MANIFEST_PATH),
            reason="private_metadata_final_verification_failed",
            operation="rollback_commit_manifest_absence",
        ):
            raise _ApprovalFailure(
                "private_metadata_final_verification_failed",
                stage="final_verification",
                authority_state="unknown",
            )
        if not win32.path_is_absent(
            guard,
            root / PurePosixPath(context.receipt_relative_path),
            reason="private_metadata_final_verification_failed",
            operation="rollback_commit_receipt_absence",
        ):
            raise _ApprovalFailure(
                "private_metadata_final_verification_failed",
                stage="final_verification",
                authority_state="unknown",
            )
        _verify_bound_bytes(
            win32,
            guard,
            journal_authority,
            expected=expected_journal_bytes,
            reason="private_metadata_final_verification_failed",
            expected_link_count=1,
        )
        locks.validate()
        guard.validate_all()
    except (
        _ApprovalFailure,
        getattr(win32, "Win32SafetyError", RuntimeError),
    ):
        # The surviving journal is restart evidence once this checkpoint is
        # not fully proved.  Never let generic failure cleanup delete it.
        state.cleanup_authority_state = "unknown"
        raise


def _execute_rollback_approval(
    root: Path,
    *,
    guard: Any,
    locks: Any,
    intake_authority: Any,
    intake_raw: bytes,
    object_authority: Any,
    state: _ApprovalExecutionState,
    win32: Any,
) -> dict[str, Any]:
    del intake_authority, intake_raw
    plan = state.accepted_plan
    context = state.context
    assert plan is not None and context is not None
    expected_after = (context.private_manifest.raw or b"") + context.stored_row
    journal = _rollback_journal_document(context)
    journal_bytes = contract.stored_json_bytes(journal)

    _verify_object_authority(
        win32,
        guard,
        object_authority=object_authority,
        context=context,
    )
    if context.private_manifest.state["state"] == "present":
        _require_retained_exact_bound(
            win32,
            guard,
            relative_path=contract.PRIVATE_MANIFEST_PATH,
            expected=context.private_manifest.raw or b"",
            expected_link_count=1,
            reason="private_metadata_final_verification_failed",
            state=state,
            context=context,
        )
    elif not win32.path_is_absent(
        guard,
        root / PurePosixPath(contract.PRIVATE_MANIFEST_PATH),
        reason="private_metadata_final_verification_failed",
        operation="rollback_manifest_before_absence",
    ):
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="final_verification",
            authority_state="unknown",
        )

    manifest_temp = context.temp_snapshots["manifest_temp"]
    if manifest_temp.state["state"] != "absent":
        state.stage = "residue_disposition"
        residue = _open_owned_prefix_residue(
            win32,
            guard,
            relative_path=context.owned_temp_relative_paths[1],
            expected=expected_after,
            state=state,
            context=context,
        )
        _record_residue_authority(state, "manifest_temp", residue)
        win32.dispose_bound_residue(guard, residue, locks=locks)
        _record_residue_absent(state, "manifest_temp")

    fixed = context.journal
    journal_temp = context.temp_snapshots["journal_temp"]
    fixed_present = fixed.state["state"] == "present"
    temp_present = journal_temp.state["state"] == "present"
    surviving_journal: Any | None = None
    surviving_role: str | None = None
    if fixed_present and temp_present:
        state.stage = "residue_disposition"
        surviving_journal = _dispose_same_identity_twin_keep_residue(
            win32,
            guard,
            locks=locks,
            survivor_relative=contract.JOURNAL_PATH,
            residue_relative=context.owned_temp_relative_paths[0],
            expected=journal_bytes,
            state=state,
            context=context,
        )
        surviving_role = "fixed_journal"
    elif fixed_present:
        fixed_narrow = _require_retained_exact_bound(
            win32,
            guard,
            relative_path=contract.JOURNAL_PATH,
            expected=journal_bytes,
            expected_link_count=1,
            reason="private_metadata_final_verification_failed",
            state=state,
            context=context,
        )
        surviving_journal = win32.handoff_to_residue_authority(
            guard,
            fixed_narrow,
            reason="private_metadata_final_verification_failed",
        )
        surviving_role = "fixed_journal"
        _record_residue_authority(
            state,
            surviving_role,
            surviving_journal,
        )
    elif temp_present:
        temp_narrow = _require_retained_exact_bound(
            win32,
            guard,
            relative_path=context.owned_temp_relative_paths[0],
            expected=journal_bytes,
            expected_link_count=1,
            reason="private_metadata_final_verification_failed",
            state=state,
            context=context,
        )
        surviving_journal = win32.handoff_to_residue_authority(
            guard,
            temp_narrow,
            reason="private_metadata_final_verification_failed",
        )
        surviving_role = "journal_temp"
        _record_residue_authority(
            state,
            surviving_role,
            surviving_journal,
        )
    else:
        raise _ApprovalFailure(
            "private_metadata_journal_cross_field_mismatch",
            stage="semantic_verification",
            authority_state="before",
        )

    assert surviving_journal is not None and surviving_role is not None
    _revalidate_rollback_before_journal_disposition(
        root,
        guard=guard,
        locks=locks,
        object_authority=object_authority,
        journal_authority=surviving_journal,
        expected_journal_bytes=journal_bytes,
        state=state,
        context=context,
        win32=win32,
    )
    state.stage = "residue_disposition"
    win32.dispose_bound_residue(
        guard,
        surviving_journal,
        locks=locks,
    )
    _record_residue_absent(state, surviving_role)
    if surviving_role == "fixed_journal":
        # A twin cleanup already proved the temp name absent.
        if temp_present:
            _record_residue_absent(state, "journal_temp")

    state.stage = "final_verification"
    for relative in (
        contract.JOURNAL_PATH,
        *context.owned_temp_relative_paths,
    ):
        if not win32.path_is_absent(
            guard,
            root / PurePosixPath(relative),
            reason="private_metadata_final_verification_failed",
            operation="rollback_terminal_absence",
        ):
            raise _ApprovalFailure(
                "private_metadata_final_verification_failed",
                stage="final_verification",
                authority_state="unknown",
            )
    state.cleanup_state = "completed"
    clean_context = _verify_terminal_replan(
        root,
        state=state,
        expected_action="append",
    )
    locks.validate()
    guard.validate_all()
    return _result_envelope(
        action="rollback_completed",
        archive_id=plan["archive_id"],
        intake_sha256=plan["intake_sha256"],
        plan=plan,
        plan_sha256=state.accepted_plan_sha256,
        reasons=[],
        dry_run=False,
        receipt_sha256=clean_context.receipt.state.get("sha256"),
        files_written=[],
    )


def _execute_already_applied_approval(
    root: Path,
    *,
    guard: Any,
    locks: Any,
    intake_authority: Any,
    intake_raw: bytes,
    object_authority: Any,
    state: _ApprovalExecutionState,
    win32: Any,
) -> dict[str, Any]:
    del intake_authority, intake_raw
    plan = state.accepted_plan
    context = state.context
    assert plan is not None and context is not None
    if context.receipt_document is None or context.receipt.raw is None:
        raise _ApprovalFailure(
            "private_metadata_receipt_plan_authority_chain_mismatch",
            stage="semantic_verification",
            authority_state="unknown",
        )
    authorities = state.locked_authorities
    if (
        authorities is None
        or authorities.private_manifest is None
        or authorities.receipt is None
    ):
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="final_verification",
            authority_state="unknown",
        )
    # ``already_applied`` is a complete checkpoint as soon as its locked
    # replan is accepted.  Retain that checkpoint before any receipt-twin or
    # fixed-journal handoff can fail so a terminal handle release can reprove
    # the actual object/manifest/receipt authority instead of guessing.
    state.applied_object_authority = object_authority
    state.applied_manifest_authority = authorities.private_manifest
    state.applied_receipt_authority = authorities.receipt
    state.applied_expected_receipt = context.receipt_document
    receipt_bytes = context.receipt.raw
    receipt_temp = context.temp_snapshots["receipt_temp"]
    if receipt_temp.state["state"] == "present":
        state.stage = "residue_disposition"
        receipt_final = _dispose_same_identity_twin_keep_narrow(
            win32,
            guard,
            locks=locks,
            survivor_relative=context.receipt_relative_path,
            residue_relative=context.owned_temp_relative_paths[2],
            expected=receipt_bytes,
            state=state,
            context=context,
        )
    else:
        receipt_final = _require_retained_exact_bound(
            win32,
            guard,
            relative_path=context.receipt_relative_path,
            expected=receipt_bytes,
            expected_link_count=1,
            reason="private_metadata_final_verification_failed",
            state=state,
            context=context,
        )

    manifest_final = _require_retained_exact_bound(
        win32,
        guard,
        relative_path=contract.PRIVATE_MANIFEST_PATH,
        expected=context.private_manifest.raw or b"",
        expected_link_count=1,
        reason="private_metadata_final_verification_failed",
        state=state,
        context=context,
    )

    journal_residue: Any | None = None
    expected_journal: dict[str, Any] | None = None
    if context.journal.state["state"] == "present":
        if context.journal_document is None or context.journal.raw is None:
            raise _ApprovalFailure(
                "private_metadata_journal_cross_field_mismatch",
                stage="semantic_verification",
                authority_state="unknown",
            )
        expected_journal = context.journal_document
        journal_narrow = _require_retained_exact_bound(
            win32,
            guard,
            relative_path=contract.JOURNAL_PATH,
            expected=context.journal.raw,
            expected_link_count=1,
            reason="private_metadata_final_verification_failed",
            state=state,
            context=context,
        )
        journal_residue = win32.handoff_to_residue_authority(
            guard,
            journal_narrow,
            reason="private_metadata_final_verification_failed",
        )
        _record_residue_authority(
            state,
            "fixed_journal",
            journal_residue,
        )

    state.stage = "final_verification"
    _verify_applied_authority(
        root,
        guard=guard,
        object_authority=object_authority,
        context=context,
        manifest_authority=manifest_final,
        receipt_authority=receipt_final,
        expected_receipt=context.receipt_document,
        journal_authority=journal_residue,
        expected_journal=expected_journal,
        win32=win32,
    )
    state.applied_object_authority = object_authority
    state.applied_manifest_authority = manifest_final
    state.applied_receipt_authority = receipt_final
    state.applied_expected_receipt = context.receipt_document
    state.last_verified_authority_state = "applied"
    state.cleanup_authority_state = "applied"
    if journal_residue is not None:
        state.stage = "residue_disposition"
        win32.dispose_bound_residue(
            guard,
            journal_residue,
            locks=locks,
        )
        _record_residue_absent(state, "fixed_journal")
        state.cleanup_state = "completed"

    state.stage = "final_verification"
    clean_context = _verify_terminal_replan(
        root,
        state=state,
        expected_action="already_applied",
    )
    locks.validate()
    guard.validate_all()
    return _result_envelope(
        action="already_applied",
        archive_id=plan["archive_id"],
        intake_sha256=plan["intake_sha256"],
        plan=plan,
        plan_sha256=state.accepted_plan_sha256,
        reasons=[],
        dry_run=False,
        receipt_sha256=clean_context.receipt.state["sha256"],
        files_written=[],
    )


def _rollback_journal_document(
    context: _PlanningContext,
) -> dict[str, Any]:
    if context.journal_document is not None:
        return context.journal_document
    raw = context.temp_snapshots["journal_temp"].raw
    if raw is None:
        raise _ApprovalFailure(
            "private_metadata_journal_cross_field_mismatch",
            stage="semantic_verification",
            authority_state="before",
        )
    try:
        value = _strict_json(raw[:-1]) if raw.endswith(b"\n") else None
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        value = None
    if (
        type(value) is not dict
        or contract.stored_json_bytes(value) != raw
        or not contract.validate_private_metadata_write_journal_semantics(
            value,
            canonical_row=context.row,
        )["accepted"]
    ):
        raise _ApprovalFailure(
            "private_metadata_journal_cross_field_mismatch",
            stage="semantic_verification",
            authority_state="before",
        )
    return value


def _open_owned_prefix_residue(
    win32: Any,
    guard: Any,
    *,
    relative_path: str,
    expected: bytes,
    state: _ApprovalExecutionState,
    context: _PlanningContext,
) -> Any:
    narrow = _retained_authority_for_relative(
        state,
        context,
        relative_path,
    )
    if narrow is None:
        raise _ApprovalFailure(
            "private_metadata_owned_temp_substituted",
            stage="residue_disposition",
            authority_state=state.last_verified_authority_state,
        )
    observed_information = win32.validate_bound_path(
        guard,
        narrow,
        expected_link_count=1,
        reason="private_metadata_owned_temp_substituted",
    )
    observed = narrow.read_all(
        max_bytes=len(expected),
        reason="private_metadata_owned_temp_substituted",
    )
    if not (
        observed == expected
        or (
            observed_information.byte_count < len(expected)
            and expected.startswith(observed)
        )
    ):
        raise _ApprovalFailure(
            "private_metadata_owned_temp_substituted",
            stage="residue_disposition",
            authority_state=state.last_verified_authority_state,
        )
    narrow.bind_proved_content(
        expected_byte_count=len(observed),
        expected_sha256=(
            "sha256:" + hashlib.sha256(observed).hexdigest()
        ),
        reason="private_metadata_owned_temp_substituted",
    )
    residue = win32.handoff_to_residue_authority(
        guard,
        narrow,
        reason="private_metadata_owned_temp_substituted",
    )
    state.handles.append(residue)
    return residue


def _dispose_same_identity_twin_keep_residue(
    win32: Any,
    guard: Any,
    *,
    locks: Any,
    survivor_relative: str,
    residue_relative: str,
    expected: bytes,
    state: _ApprovalExecutionState,
    context: _PlanningContext,
) -> Any:
    survivor = _require_retained_exact_bound(
        win32,
        guard,
        relative_path=survivor_relative,
        expected=expected,
        expected_link_count=2,
        reason="private_metadata_unexpected_hardlink",
        state=state,
        context=context,
    )
    residue = _require_retained_exact_bound(
        win32,
        guard,
        relative_path=residue_relative,
        expected=expected,
        expected_link_count=2,
        reason="private_metadata_unexpected_hardlink",
        state=state,
        context=context,
    )
    if survivor.identity != residue.identity:
        raise _ApprovalFailure(
            "private_metadata_unexpected_hardlink",
            stage="residue_disposition",
            authority_state=state.last_verified_authority_state,
        )
    survivor_transition, residue_authority = (
        win32.handoff_same_identity_twin_to_residue(
        guard,
        survivor,
        residue,
        expected_bytes=expected,
        )
    )
    _track_handle(state, survivor_transition)
    if state.last_verified_authority_state == "applied":
        state.applied_receipt_authority = survivor_transition
    _record_residue_authority(
        state,
        "journal_temp",
        residue_authority,
        name_state="twin_published",
    )
    win32.dispose_bound_residue(
        guard,
        residue_authority,
        locks=locks,
    )
    _record_residue_absent(state, "journal_temp")
    survivor_transition.expected_link_count = 1
    _verify_bound_bytes(
        win32,
        guard,
        survivor_transition,
        expected=expected,
        reason="private_metadata_final_verification_failed",
        expected_link_count=1,
    )
    retained = win32.handoff_to_residue_authority(
        guard,
        survivor_transition,
        reason="private_metadata_final_verification_failed",
    )
    _record_residue_authority(state, "fixed_journal", retained)
    return retained


def _dispose_same_identity_twin_keep_narrow(
    win32: Any,
    guard: Any,
    *,
    locks: Any,
    survivor_relative: str,
    residue_relative: str,
    expected: bytes,
    state: _ApprovalExecutionState,
    context: _PlanningContext,
) -> Any:
    survivor = _require_retained_exact_bound(
        win32,
        guard,
        relative_path=survivor_relative,
        expected=expected,
        expected_link_count=2,
        reason="private_metadata_unexpected_hardlink",
        state=state,
        context=context,
    )
    residue = _require_retained_exact_bound(
        win32,
        guard,
        relative_path=residue_relative,
        expected=expected,
        expected_link_count=2,
        reason="private_metadata_unexpected_hardlink",
        state=state,
        context=context,
    )
    if survivor.identity != residue.identity:
        raise _ApprovalFailure(
            "private_metadata_unexpected_hardlink",
            stage="residue_disposition",
            authority_state="unknown",
        )
    survivor_transition, residue_authority = (
        win32.handoff_same_identity_twin_to_residue(
        guard,
        survivor,
        residue,
        expected_bytes=expected,
        )
    )
    _track_handle(state, survivor_transition)
    _record_residue_authority(
        state,
        "receipt_temp",
        residue_authority,
        name_state="twin_published",
    )
    win32.dispose_bound_residue(
        guard,
        residue_authority,
        locks=locks,
    )
    _record_residue_absent(state, "receipt_temp")
    survivor_transition.expected_link_count = 1
    _verify_bound_bytes(
        win32,
        guard,
        survivor_transition,
        expected=expected,
        reason="private_metadata_final_verification_failed",
        expected_link_count=1,
    )
    narrow = win32.handoff_to_narrow_authority(
        guard,
        survivor_transition,
        reason="private_metadata_final_verification_failed",
    )
    _track_handle(state, narrow)
    if state.last_verified_authority_state == "applied":
        state.applied_receipt_authority = narrow
    return narrow


def _verify_applied_authority(
    root: Path,
    *,
    guard: Any,
    object_authority: Any,
    context: _PlanningContext,
    manifest_authority: Any,
    receipt_authority: Any,
    expected_receipt: dict[str, Any],
    journal_authority: Any | None,
    expected_journal: dict[str, Any] | None,
    win32: Any,
    verify_owned_temp_absence: bool = True,
) -> None:
    expected_manifest = expected_receipt["private_manifest_after"]
    manifest_raw = manifest_authority.read_all(
        max_bytes=PRIVATE_MANIFEST_MAX_BYTES,
        reason="private_metadata_final_verification_failed",
    )
    if (
        contract.sha256_digest(manifest_raw) != expected_manifest["sha256"]
        or len(manifest_raw) != expected_manifest["byte_count"]
    ):
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="final_verification",
            authority_state="unknown",
        )
    _verify_bound_bytes(
        win32,
        guard,
        receipt_authority,
        expected=contract.stored_json_bytes(expected_receipt),
        reason="private_metadata_final_verification_failed",
        expected_link_count=1,
    )
    if not contract.validate_private_metadata_write_receipt_semantics(
        expected_receipt,
        canonical_row=context.row,
    )["accepted"]:
        raise _ApprovalFailure(
            "private_metadata_receipt_plan_authority_chain_mismatch",
            stage="semantic_verification",
            authority_state="unknown",
        )
    if expected_journal is not None:
        if journal_authority is None:
            raise _ApprovalFailure(
                "private_metadata_journal_cross_field_mismatch",
                stage="semantic_verification",
                authority_state="unknown",
            )
        _verify_bound_bytes(
            win32,
            guard,
            journal_authority,
            expected=contract.stored_json_bytes(expected_journal),
            reason="private_metadata_final_verification_failed",
            expected_link_count=1,
        )
        if (
            expected_journal["receipt_document"] != expected_receipt
            or not contract.validate_private_metadata_write_journal_semantics(
                expected_journal,
                canonical_row=context.row,
            )["accepted"]
        ):
            raise _ApprovalFailure(
                "private_metadata_journal_cross_field_mismatch",
                stage="semantic_verification",
                authority_state="unknown",
            )

    _verify_object_authority(
        win32,
        guard,
        object_authority=object_authority,
        context=context,
    )
    private_snapshot, rows, stored_rows = _observe_private_manifest(root)
    if private_snapshot.state != expected_manifest:
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="final_verification",
            authority_state="unknown",
        )
    chain_before, _ = _observe_receipt_directory_chain(root)
    inventory, _, unexpected = _inventory_receipt_directory(
        root,
        chain_before,
        allowed_temp_basename=PurePosixPath(
            context.owned_temp_relative_paths[2]
        ).name,
    )
    if unexpected:
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="final_verification",
            authority_state="unknown",
        )
    try:
        _, _, receipts = _build_complete_authority_chain(
            root,
            rows,
            stored_rows,
            private_manifest_state=private_snapshot.state,
            inventory=inventory,
            capture_receipt_relative=context.receipt_relative_path,
        )
    except _SnapshotError as exc:
        reason = (
            "private_metadata_receipt_plan_authority_chain_mismatch"
            if exc.reason == "receipt_semantic_mismatch"
            else "private_metadata_final_verification_failed"
        )
        raise _ApprovalFailure(
            reason,
            stage=(
                "semantic_verification"
                if reason.endswith("mismatch")
                else "final_verification"
            ),
            authority_state="unknown",
        ) from exc
    if receipts.get(context.receipt_relative_path) != expected_receipt:
        raise _ApprovalFailure(
            "private_metadata_receipt_plan_authority_chain_mismatch",
            stage="semantic_verification",
            authority_state="unknown",
        )
    if verify_owned_temp_absence:
        for relative in context.owned_temp_relative_paths:
            if not win32.path_is_absent(
                guard,
                root / PurePosixPath(relative),
                reason="private_metadata_final_verification_failed",
                operation="applied_owned_temp_absence",
            ):
                raise _ApprovalFailure(
                    "private_metadata_final_verification_failed",
                    stage="final_verification",
                    authority_state="unknown",
                )
    guard.validate_all()


def _reprove_applied_content_checkpoint(
    *,
    state: _ApprovalExecutionState,
    guard: Any,
    win32: Any,
) -> None:
    """Reprove only the accepted object/M1/R checkpoint after terminal release.

    RG-28 forbids planner work, receipt-directory inventory, and any inspection
    or classification of the released J/Rt residue.  The locked planning
    context already proved the complete chain, so this verifier reads only the
    three retained content authorities that make up the applied checkpoint.
    """

    context = state.context
    expected_receipt = state.applied_expected_receipt
    object_authority = state.applied_object_authority
    manifest_authority = state.applied_manifest_authority
    receipt_authority = state.applied_receipt_authority
    if (
        context is None
        or expected_receipt is None
        or object_authority is None
        or manifest_authority is None
        or receipt_authority is None
    ):
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="final_verification",
            authority_state="unknown",
        )

    expected_manifest = expected_receipt.get("private_manifest_after")
    if type(expected_manifest) is not dict:
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="final_verification",
            authority_state="unknown",
        )

    _verify_object_authority(
        win32,
        guard,
        object_authority=object_authority,
        context=context,
    )
    win32.validate_bound_path(
        guard,
        manifest_authority,
        reason="private_metadata_final_verification_failed",
        expected_link_count=1,
    )
    manifest_raw = manifest_authority.read_all(
        max_bytes=PRIVATE_MANIFEST_MAX_BYTES,
        reason="private_metadata_final_verification_failed",
    )
    if (
        contract.sha256_digest(manifest_raw)
        != expected_manifest.get("sha256")
        or len(manifest_raw) != expected_manifest.get("byte_count")
    ):
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="final_verification",
            authority_state="unknown",
        )
    manifest_authority.bind_proved_content(
        expected_byte_count=len(manifest_raw),
        expected_sha256=contract.sha256_digest(manifest_raw),
        reason="private_metadata_final_verification_failed",
    )
    receipt_link_count = getattr(
        receipt_authority,
        "expected_link_count",
        None,
    )
    if receipt_link_count not in (1, 2):
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="final_verification",
            authority_state="unknown",
        )
    _verify_bound_bytes(
        win32,
        guard,
        receipt_authority,
        expected=contract.stored_json_bytes(expected_receipt),
        reason="private_metadata_final_verification_failed",
        expected_link_count=receipt_link_count,
    )
    if not contract.validate_private_metadata_write_receipt_semantics(
        expected_receipt,
        canonical_row=context.row,
    )["accepted"]:
        raise _ApprovalFailure(
            "private_metadata_receipt_plan_authority_chain_mismatch",
            stage="semantic_verification",
            authority_state="unknown",
        )


def _verify_terminal_replan(
    root: Path,
    *,
    state: _ApprovalExecutionState,
    expected_action: str,
) -> _PlanningContext:
    context = state.context
    assert context is not None
    row_result = contract.build_private_metadata_row(context.intake)
    if not row_result["accepted"]:
        raise _ApprovalFailure(
            "private_metadata_final_verification_failed",
            stage="final_verification",
            authority_state="unknown",
        )
    current, plan, _, reasons = _locked_replan(
        root,
        archive_id=context.archive_id,
        intake=context.intake,
        intake_sha256=context.intake_sha256,
        row_result=row_result,
    )
    if (
        plan["action"] != expected_action
        or reasons
        or current.authority_chain_validation != "valid_complete"
    ):
        semantic_reason = next(
            (
                reason
                for reason in reasons
                if reason
                in {
                    "private_metadata_journal_cross_field_mismatch",
                    "private_metadata_receipt_plan_authority_chain_mismatch",
                }
            ),
            None,
        )
        raise _ApprovalFailure(
            semantic_reason or "private_metadata_final_verification_failed",
            stage=(
                "semantic_verification"
                if semantic_reason is not None
                else "final_verification"
            ),
            authority_state="unknown",
        )
    return current


def _approval_failure_from_win32(
    state: _ApprovalExecutionState,
    exc: BaseException,
) -> _ApprovalFailure:
    reason = getattr(
        exc,
        "reason",
        "private_metadata_final_verification_failed",
    )
    direct_stage = {
        "private_metadata_mutation_guard_identity_changed": "guard_or_lock",
        "private_metadata_lock_identity_changed": "guard_or_lock",
        "private_metadata_receipt_directory_bootstrap_failed": (
            "receipt_directory_bootstrap"
        ),
        "private_metadata_owned_temp_materialization_failed": (
            "owned_temp_materialization"
        ),
        "private_metadata_hardlink_publication_failed": (
            "hardlink_publication"
        ),
        "private_metadata_object_manifest_changed_before_commit": (
            "manifest_replacement"
        ),
        "private_metadata_manifest_replacement_failed": (
            "manifest_replacement"
        ),
        "private_metadata_residue_disposition_failed": (
            "residue_disposition"
        ),
        "private_metadata_final_verification_failed": "final_verification",
        "private_metadata_journal_cross_field_mismatch": (
            "semantic_verification"
        ),
        "private_metadata_receipt_plan_authority_chain_mismatch": (
            "semantic_verification"
        ),
    }
    stage = direct_stage.get(reason, state.stage)
    authority_state = state.last_verified_authority_state
    effect = getattr(getattr(exc, "effect", None), "value", None)
    checkpoint = getattr(
        getattr(exc, "checkpoint", None),
        "value",
        "",
    )
    if (
        effect == "state_change_proved"
        and checkpoint.startswith("manifest_")
    ):
        state.cleanup_authority_state = "after"
    if (
        effect in {"state_change_proved", "state_change_possible"}
        and checkpoint.startswith("hardlink_")
    ):
        state.cleanup_authority_state = "unknown"
    if (
        effect in {"state_change_proved", "state_change_possible"}
        and stage
        in {
            "hardlink_publication",
            "manifest_replacement",
            "residue_disposition",
            "final_verification",
            "semantic_verification",
        }
    ) or (
        effect is None
        and stage
        in {
            "manifest_replacement",
            "residue_disposition",
            "final_verification",
            "semantic_verification",
        }
    ):
        authority_state = "unknown"
    if reason == "private_metadata_object_manifest_changed_before_commit":
        authority_state = "unknown"
    return _ApprovalFailure(
        reason,
        stage=stage,
        authority_state=authority_state,
    )


def _close_tracked_handles(
    state: _ApprovalExecutionState,
    win32: Any,
) -> _ApprovalFailure | None:
    first: _ApprovalFailure | None = None
    accepted = state.accepted_plan is not None
    reason = (
        "private_metadata_final_verification_failed"
        if accepted
        else "private_metadata_authority_state_unavailable"
    )
    for bound in reversed(state.handles):
        if getattr(bound, "closed", True):
            continue
        try:
            bound.close(
                reason=reason,
                operation="approval_tracked_handle_close",
                )
        except getattr(win32, "Win32SafetyError", RuntimeError):
            if first is None:
                first = _ApprovalFailure(
                    reason,
                    stage=(
                        "final_verification" if accepted else "guard_or_lock"
                    ),
                    authority_state=(
                        state.last_verified_authority_state
                        if accepted
                        else "unknown"
                    ),
                )
            # The first ordinary CloseHandle failure does not surrender the
            # exact raw authority.  Finish its bounded no-path terminal release
            # before moving to any other handle, lock, or guard.
            win32.release_terminal_bound_authority(
                bound,
                reason=reason,
                operation="approval_tracked_handle_terminal_release",
            )
    state.handles.clear()
    return first


def _release_failure_authority_state(
    state: _ApprovalExecutionState,
    exc: BaseException,
    *,
    syscall_only_operations: set[str],
) -> str:
    """Keep a proved checkpoint only for a syscall-only release failure."""

    if getattr(exc, "operation", None) in syscall_only_operations:
        return state.last_verified_authority_state
    state.last_verified_authority_state = "unknown"
    return "unknown"


def _failure_cleanup_roles(
    state: _ApprovalExecutionState,
) -> tuple[str, ...]:
    if state.cleanup_authority_state == "before":
        return (
            "manifest_temp",
            "receipt_temp",
            "journal_temp",
            "fixed_journal",
        )
    if state.cleanup_authority_state == "after":
        # The fixed journal is restart authority once the manifest is after.
        return ("receipt_temp",)
    if state.cleanup_authority_state == "applied":
        return ("receipt_temp", "journal_temp", "fixed_journal")
    return ()


def _forget_terminal_authority(
    state: _ApprovalExecutionState,
    bound: Any,
) -> None:
    state.handles = [
        candidate for candidate in state.handles if candidate is not bound
    ]
    for entry in state.residue_ledger.values():
        if entry.bound is bound:
            entry.bound = None
            entry.state = "terminal_released"


def _reprove_authority_after_terminal_release(
    root: Path,
    *,
    state: _ApprovalExecutionState,
    guard: Any,
    locks: Any,
    win32: Any,
) -> None:
    """Reprove the prior complete checkpoint; never inspect/classify residue."""

    prior = state.last_verified_authority_state
    try:
        context = state.context
        plan = state.accepted_plan
        if context is None or plan is None:
            raise _ApprovalFailure(
                "private_metadata_final_verification_failed",
                stage="final_verification",
                authority_state="unknown",
            )
        if prior == "applied":
            _reprove_applied_content_checkpoint(
                state=state,
                guard=guard,
                win32=win32,
            )
        elif prior in {"before", "after"}:
            object_authority = (
                state.locked_authorities.object_manifest
                if state.locked_authorities is not None
                else None
            )
            if object_authority is None:
                raise _ApprovalFailure(
                    "private_metadata_final_verification_failed",
                    stage="final_verification",
                    authority_state="unknown",
                )
            _verify_object_authority(
                win32,
                guard,
                object_authority=object_authority,
                context=context,
            )
            private_snapshot, _, _ = _observe_private_manifest(root)
            expected_manifest = plan[
                (
                    "private_manifest_before"
                    if prior == "before"
                    else "private_manifest_after"
                )
            ]
            if private_snapshot.state != expected_manifest:
                raise _ApprovalFailure(
                    "private_metadata_final_verification_failed",
                    stage="final_verification",
                    authority_state="unknown",
                )
            if not win32.path_is_absent(
                guard,
                root / PurePosixPath(context.receipt_relative_path),
                reason="private_metadata_final_verification_failed",
                operation="terminal_checkpoint_receipt_absence",
            ):
                raise _ApprovalFailure(
                    "private_metadata_final_verification_failed",
                    stage="final_verification",
                    authority_state="unknown",
                )
        else:
            raise _ApprovalFailure(
                "private_metadata_final_verification_failed",
                stage="final_verification",
                authority_state="unknown",
            )
        guard.validate_all()
        locks.validate()
    except Exception:
        state.last_verified_authority_state = "unknown"
    else:
        state.last_verified_authority_state = prior


def _handle_terminal_release_failure(
    state: _ApprovalExecutionState,
    *,
    exc: BaseException,
    authorities: tuple[Any, ...],
    root: Path,
    guard: Any | None,
    locks: Any | None,
    win32: Any,
) -> bool:
    if not getattr(exc, "terminal_release_required", False):
        return False
    if guard is None or locks is None or not authorities:
        os._exit(74)
    live_bounds: list[Any] = []
    for transfer in authorities:
        candidate = getattr(transfer, "bound", None)
        if candidate is None or getattr(candidate, "closed", True):
            os._exit(74)
        if any(existing is candidate for existing in live_bounds):
            os._exit(74)
        live_bounds.append(candidate)
    marked = tuple(
        transfer
        for transfer in authorities
        if getattr(transfer, "terminal_release_first", False)
    )
    if marked:
        if len(marked) != 1:
            os._exit(74)
        terminal_transfer = marked[0]
    elif len(authorities) == 1:
        terminal_transfer = authorities[0]
    else:
        os._exit(74)
    bound = getattr(terminal_transfer, "bound", None)
    if bound is None:
        os._exit(74)

    # This exact residue release precedes every other handle/lock/guard close.
    # For a still-delete-pending handle it is the directive's explicit final
    # filesystem mutation-effect boundary.
    win32.release_terminal_bound_authority(bound)
    if not getattr(bound, "closed", False):
        os._exit(74)
    _forget_terminal_authority(state, bound)
    remaining = tuple(
        transfer
        for transfer in authorities
        if transfer is not terminal_transfer
    )
    for transfer in remaining:
        expected_link_count = getattr(
            transfer,
            "expected_link_count_after_terminal_release",
            None,
        )
        survivor = getattr(transfer, "bound", None)
        if expected_link_count is not None:
            if survivor is None or getattr(survivor, "closed", True):
                os._exit(74)
            survivor.expected_link_count = expected_link_count
    _adopt_failure_authorities(state, remaining)
    state.terminal_release_occurred = True
    _reprove_authority_after_terminal_release(
        root,
        state=state,
        guard=guard,
        locks=locks,
        win32=win32,
    )
    return True


def _handle_primary_failure_cleanup(
    state: _ApprovalExecutionState,
    *,
    failure: _ApprovalFailure,
    root: Path,
    guard: Any | None,
    locks: Any | None,
    win32: Any,
) -> None:
    """Honor first-unfulfilled when the primary disposition itself failed."""

    if state.terminal_release_occurred:
        # A helper-owned ordinary close has already failed and its exact raw
        # authority has entered bounded terminal release.  That release fixes
        # the first unfulfilled operation for this invocation.  Do not begin a
        # later residue handoff/disposition after the terminal unwind; preserve
        # every remaining obligation for a fresh classification instead.
        state.cleanup_state = "incomplete"
        state.cleanup_incomplete = True
        failure.authority_state = state.last_verified_authority_state
        return
    if (
        failure.reason == "private_metadata_residue_disposition_failed"
        and failure.stage == "residue_disposition"
    ):
        # This invocation has already attempted the first outstanding cleanup
        # obligation.  Retrying that same disposition here would erase the
        # durable restart authority and misreport a completed cleanup.
        state.cleanup_state = "incomplete"
        state.cleanup_incomplete = True
        return
    _attempt_failure_cleanup(
        state,
        root=root,
        guard=guard,
        locks=locks,
        win32=win32,
    )
    if state.terminal_release_occurred:
        failure.authority_state = state.last_verified_authority_state


def _attempt_failure_cleanup(
    state: _ApprovalExecutionState,
    *,
    root: Path,
    guard: Any | None,
    locks: Any | None,
    win32: Any,
) -> None:
    """Dispose proved writer-owned residue while guard/locks remain live."""

    if guard is None or locks is None:
        if state.residue_obligations:
            state.cleanup_state = "preserved_unverified"
            state.cleanup_incomplete = True
        return
    roles = _failure_cleanup_roles(state)
    if not roles and state.residue_obligations:
        state.cleanup_state = "preserved_unverified"
        state.cleanup_incomplete = True
        return
    candidates = [
        state.residue_ledger[role]
        for role in roles
        if role in state.residue_ledger
        and state.residue_ledger[role].state
        not in {"not_arisen", "absent_proved"}
    ]
    if not candidates:
        if state.cleanup_state != "completed":
            state.cleanup_state = "not_required"
        state.cleanup_incomplete = False
        return

    for entry in candidates:
        bound = entry.bound
        if bound is None or getattr(bound, "closed", True):
            entry.state = "preserved_unverified"
            state.cleanup_state = "preserved_unverified"
            state.cleanup_incomplete = True
            return
        try:
            locks.validate()
            guard.validate_all()
            if entry.state == "delete_pending":
                win32.complete_delete_pending_residue(guard, bound)
                _record_residue_absent(state, entry.role)
                locks.validate()
                guard.validate_all()
                continue
            if isinstance(
                bound,
                getattr(win32, "Win32UnverifiedCreatedFile", ()),
            ):
                win32.dispose_unverified_created_file(guard, bound)
                _record_residue_absent(state, entry.role)
                locks.validate()
                guard.validate_all()
                continue
            if bound.profile is not win32.FileHandleProfile.RESIDUE_DISPOSITION:
                bound = win32.handoff_to_residue_authority(
                    guard,
                    bound,
                    reason="private_metadata_residue_disposition_failed",
                )
                _track_handle(state, bound)
                entry.bound = bound
            win32.dispose_bound_residue(
                guard,
                bound,
                locks=locks,
            )
            _record_residue_absent(state, entry.role)
            locks.validate()
            guard.validate_all()
        except getattr(win32, "Win32MutationFailure", RuntimeError) as exc:
            transferred = exc.take_authorities()
            terminal_released = _handle_terminal_release_failure(
                state,
                exc=exc,
                authorities=transferred,
                root=root,
                guard=guard,
                locks=locks,
                win32=win32,
            )
            if not terminal_released:
                _adopt_failure_authorities(state, transferred)
            if terminal_released:
                entry.state = "terminal_released"
                entry.bound = None
                state.cleanup_state = "incomplete"
                state.cleanup_incomplete = True
                return
            entry.state = (
                "preserved_unverified"
                if (
                    getattr(getattr(exc, "effect", None), "value", None)
                    == "state_change_possible"
                    or (
                        not transferred
                        and getattr(bound, "closed", True)
                    )
                )
                else "cleanup_failed"
            )
            state.cleanup_state = (
                "preserved_unverified"
                if entry.state == "preserved_unverified"
                else "incomplete"
            )
            state.cleanup_incomplete = True
            return
        except getattr(win32, "Win32SafetyError", RuntimeError):
            entry.state = (
                "cleanup_failed"
                if not getattr(bound, "closed", True)
                else "preserved_unverified"
            )
            state.cleanup_state = (
                "incomplete"
                if entry.state == "cleanup_failed"
                else "preserved_unverified"
            )
            state.cleanup_incomplete = True
            return
    state.cleanup_state = "completed"
    state.cleanup_incomplete = False


def _attempt_failure_cleanup_result(
    state: _ApprovalExecutionState,
) -> tuple[str, bool]:
    return state.cleanup_state, state.cleanup_incomplete


def _execution_hold_result(
    state: _ApprovalExecutionState,
    *,
    archive_id: str,
    intake_sha256: str,
    reasons: list[str],
    stage: str,
    authority_state: str,
    cleanup_state: str,
) -> dict[str, Any]:
    assert state.accepted_plan is not None
    assert state.accepted_plan_sha256 is not None
    return _result_envelope(
        action="manual_hold",
        archive_id=archive_id,
        intake_sha256=intake_sha256,
        plan=state.accepted_plan,
        plan_sha256=state.accepted_plan_sha256,
        reasons=_unique(reasons),
        dry_run=False,
        hold_context={
            "failure_stage": stage,
            "last_verified_authority_state": authority_state,
            "cleanup_state": cleanup_state,
        },
        receipt_sha256=(
            state.context.receipt.state.get("sha256")
            if state.context is not None
            else None
        ),
        files_written=[],
    )
