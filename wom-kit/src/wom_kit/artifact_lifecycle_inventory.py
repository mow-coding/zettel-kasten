"""Bounded, content-free archive artifact lifecycle inventory.

The inventory is deliberately read-only.  It never follows filesystem links,
reads ordinary artifact bodies, hashes object bytes, calls providers, or makes
cleanup decisions.  The only file bodies it may read are bounded control
metadata: the canonical object manifest and top-level workpack package files.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat as stat_module
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


INVENTORY_SCHEMA = "wom-kit/artifact-lifecycle-inventory/v0.1"
DEFAULT_MAX_ENTRIES_PER_ROOT = 10_000
MAX_ENTRIES_PER_ROOT = 100_000
DEFAULT_MAX_ITEMS = 200
MAX_ITEMS = 2_000
MAX_CONTROL_FILE_BYTES = 1 * 1024 * 1024
MAX_OBJECT_MANIFEST_BYTES = 64 * 1024 * 1024
OBJECT_ID_RE = re.compile(r"^sha256:(?P<digest>[0-9a-f]{64})$")
LOCAL_OBJECT_PATH_RE = re.compile(
    r"^objects/sha256/(?P<prefix>[0-9a-f]{2})/(?P<digest>[0-9a-f]{64})$"
)
INDEX_RELATIVE_PATHS = (
    "db/archive-index.sqlite",
    "db/archive-index.sqlite-wal",
    "db/archive-index.sqlite-shm",
    "db/archive-index.sqlite-journal",
)


@dataclass(frozen=True)
class ScopeSpec:
    root_id: str
    relative_root: str
    artifact_class: str
    review_state: str
    list_files: bool


RECURSIVE_SCOPES = (
    ScopeSpec(
        "private_scratch",
        ".wom-scratch",
        "DISPOSABLE_AFTER_REVIEW",
        "preservation_or_operation_review_required",
        True,
    ),
    ScopeSpec(
        "ai_workbench_scratch",
        "workbench/ai-scratch",
        "DISPOSABLE_AFTER_REVIEW",
        "preservation_review_required",
        True,
    ),
    ScopeSpec(
        "ai_staging_inbox",
        "staging/ai/inbox",
        "DURABLE_UNTIL_RESOLVED",
        "intake_fate_review_required",
        True,
    ),
    ScopeSpec(
        "ai_staging_reviewed",
        "staging/ai/reviewed",
        "DURABLE_UNTIL_RESOLVED",
        "reviewed_but_lifecycle_open",
        True,
    ),
    ScopeSpec(
        "temporary_files",
        "tmp",
        "DISPOSABLE_AFTER_REVIEW",
        "cleanup_review_required",
        True,
    ),
    ScopeSpec(
        "capture_staging",
        "staging/incoming",
        "DURABLE_UNTIL_RESOLVED",
        "preservation_verification_required",
        True,
    ),
    ScopeSpec(
        "draft_inbox",
        "inbox",
        "DURABLE_UNTIL_RESOLVED",
        "draft_lifecycle_open",
        True,
    ),
    ScopeSpec(
        "workpacks",
        "workpacks",
        "DURABLE_WITH_EXPIRY",
        "expiry_or_retention_review_required",
        True,
    ),
    ScopeSpec(
        "local_object_store",
        "objects/sha256",
        "DURABLE_ARCHIVE_RECORD",
        "keep",
        False,
    ),
    ScopeSpec(
        "local_derived_text_store",
        "objects/derived-text/sha256",
        "DURABLE_ARCHIVE_RECORD",
        "keep",
        False,
    ),
)

NEVER_TOUCH_PRESENCE_SCOPE = ScopeSpec(
    "noncanonical_in_root_objets",
    "objets",
    "EXTERNAL_LIVE_NEVER_TOUCH",
    "manual_migration_hold",
    False,
)


@dataclass(frozen=True)
class _Entry:
    root_id: str
    relative_path: str
    is_directory: bool
    size: int
    mtime_ns: int
    device: int
    inode: int


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _artifact_ref(archive_id: str, relative_path: str) -> str:
    digest = _sha256_text(f"{archive_id}\x00{relative_path}")
    return f"artifact:{digest[:24]}"


def _identity(
    stat_result: os.stat_result,
    *,
    directory: bool,
) -> tuple[int, int, int, int, int, int]:
    return (
        int(stat_result.st_mode),
        int(getattr(stat_result, "st_dev", 0)),
        int(getattr(stat_result, "st_ino", 0)),
        int(stat_result.st_mtime_ns),
        int(
            getattr(
                stat_result,
                "st_ctime_ns",
                int(float(getattr(stat_result, "st_ctime", 0.0)) * 1_000_000_000),
            )
        ),
        0 if directory else int(stat_result.st_size),
    )


def _descriptor_comparable_identity(
    value: tuple[int, int, int, int, int, int],
) -> tuple[int, int, int, int, int]:
    # On Windows, fstat() can expose a different ctime representation from
    # lstat() for the same handle/path.  Compare every stable cross-API field
    # here, then compare the two path lstat snapshots with full ctime below.
    return (value[0], value[1], value[2], value[3], value[5])


def _is_reparse_point(stat_result: os.stat_result) -> bool:
    attributes = int(getattr(stat_result, "st_file_attributes", 0))
    marker = int(getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(attributes & marker)


def _iso_from_ns(value: int) -> str:
    return datetime.fromtimestamp(value / 1_000_000_000, tz=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def _age_bucket(value: int, *, now: datetime) -> str:
    age_seconds = max(0.0, now.timestamp() - (value / 1_000_000_000))
    age_days = age_seconds / 86_400
    if age_days < 7:
        return "under_7_days"
    if age_days < 31:
        return "7_to_30_days"
    if age_days < 91:
        return "31_to_90_days"
    return "over_90_days"


def _normalize_limit(value: Any, *, default: int, maximum: int, field: str) -> tuple[int, list[str]]:
    blockers: list[str] = []
    if isinstance(value, bool):
        blockers.append(f"{field}_invalid")
        return default, blockers
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        blockers.append(f"{field}_invalid")
        return default, blockers
    if parsed < 1:
        blockers.append(f"{field}_below_minimum")
        return 1, blockers
    if parsed > maximum:
        blockers.append(f"{field}_above_maximum")
        return maximum, blockers
    return parsed, blockers


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _scan_recursive_scope(
    root: Path,
    spec: ScopeSpec,
    *,
    max_entries: int,
) -> tuple[dict[str, Any], list[_Entry], list[str]]:
    scope_path = root.joinpath(*PurePosixPath(spec.relative_root).parts)
    blockers: list[str] = []
    entries: list[_Entry] = []
    summary: dict[str, Any] = {
        "root_id": spec.root_id,
        "relative_root": spec.relative_root,
        "artifact_class": spec.artifact_class,
        "scan_mode": "recursive_metadata",
        "present": False,
        "coverage_complete": True,
        "entries_seen": 0,
        "file_count": 0,
        "directory_count": 0,
        "byte_count": 0,
        "symlink_or_reparse_count": 0,
        "special_file_count": 0,
        "unreadable_count": 0,
        "changed_during_scan_count": 0,
        "truncated": False,
    }
    try:
        root_stat = os.lstat(scope_path)
    except FileNotFoundError:
        return summary, entries, blockers
    except OSError:
        summary["coverage_complete"] = False
        summary["unreadable_count"] = 1
        return summary, entries, [f"{spec.root_id}_root_unreadable"]

    summary["present"] = True
    if stat_module.S_ISLNK(root_stat.st_mode) or _is_reparse_point(root_stat):
        summary["coverage_complete"] = False
        summary["symlink_or_reparse_count"] = 1
        return summary, entries, [f"{spec.root_id}_root_link_or_reparse"]
    if not stat_module.S_ISDIR(root_stat.st_mode):
        summary["coverage_complete"] = False
        summary["special_file_count"] = 1
        return summary, entries, [f"{spec.root_id}_root_not_directory"]

    directory_snapshots: list[tuple[Path, tuple[int, int, int, int, int, int]]] = [
        (scope_path, _identity(root_stat, directory=True))
    ]
    file_snapshots: list[tuple[Path, tuple[int, int, int, int, int, int]]] = []
    stack: list[tuple[Path, tuple[int, int, int, int, int, int]]] = [
        directory_snapshots[0]
    ]
    truncated = False
    while stack and not truncated:
        directory, expected_directory_identity = stack.pop()
        try:
            current_directory_stat = os.lstat(directory)
            if (
                stat_module.S_ISLNK(current_directory_stat.st_mode)
                or _is_reparse_point(current_directory_stat)
                or not stat_module.S_ISDIR(current_directory_stat.st_mode)
                or _identity(current_directory_stat, directory=True)
                != expected_directory_identity
            ):
                summary["changed_during_scan_count"] += 1
                blockers.append(f"{spec.root_id}_changed_during_scan")
                continue
            iterator = os.scandir(directory)
        except OSError:
            summary["unreadable_count"] += 1
            blockers.append(f"{spec.root_id}_entry_unreadable")
            continue
        with iterator:
            for directory_entry in iterator:
                if summary["entries_seen"] >= max_entries:
                    truncated = True
                    break
                summary["entries_seen"] += 1
                path = Path(directory_entry.path)
                try:
                    # Use lstat for both snapshot passes.  On Windows,
                    # DirEntry.stat() may report zero device/inode values while
                    # os.lstat() reports the real file identity, which would
                    # otherwise create a false changed-during-scan result.
                    item_stat = os.lstat(path)
                except OSError:
                    summary["unreadable_count"] += 1
                    blockers.append(f"{spec.root_id}_entry_unreadable")
                    continue
                if directory_entry.is_symlink() or _is_reparse_point(item_stat):
                    summary["symlink_or_reparse_count"] += 1
                    blockers.append(f"{spec.root_id}_link_or_reparse_skipped")
                    continue
                if stat_module.S_ISDIR(item_stat.st_mode):
                    summary["directory_count"] += 1
                    identity = _identity(item_stat, directory=True)
                    directory_snapshots.append((path, identity))
                    entries.append(
                        _Entry(
                            root_id=spec.root_id,
                            relative_path=_relative(path, root),
                            is_directory=True,
                            size=0,
                            mtime_ns=item_stat.st_mtime_ns,
                            device=identity[1],
                            inode=identity[2],
                        )
                    )
                    stack.append((path, identity))
                    continue
                if stat_module.S_ISREG(item_stat.st_mode):
                    summary["file_count"] += 1
                    summary["byte_count"] += int(item_stat.st_size)
                    identity = _identity(item_stat, directory=False)
                    file_snapshots.append((path, identity))
                    entries.append(
                        _Entry(
                            root_id=spec.root_id,
                            relative_path=_relative(path, root),
                            is_directory=False,
                            size=int(item_stat.st_size),
                            mtime_ns=item_stat.st_mtime_ns,
                            device=identity[1],
                            inode=identity[2],
                        )
                    )
                    continue
                summary["special_file_count"] += 1
                blockers.append(f"{spec.root_id}_special_file_skipped")

    if truncated:
        summary["truncated"] = True
        blockers.append(f"{spec.root_id}_entry_limit_reached")

    for path, before in [*directory_snapshots, *file_snapshots]:
        try:
            after_stat = os.lstat(path)
            after = _identity(
                after_stat,
                directory=stat_module.S_ISDIR(after_stat.st_mode),
            )
        except (FileNotFoundError, OSError):
            summary["changed_during_scan_count"] += 1
            continue
        if after != before:
            summary["changed_during_scan_count"] += 1

    if summary["changed_during_scan_count"]:
        blockers.append(f"{spec.root_id}_changed_during_scan")
        # A directory replacement can make a path-based scandir observe a
        # different tree.  Never emit candidate rows or aggregate sizes from
        # a scope whose snapshot identity changed.
        entries.clear()
        summary["file_count"] = 0
        summary["directory_count"] = 0
        summary["byte_count"] = 0
    summary["coverage_complete"] = not any(
        (
            summary["truncated"],
            summary["symlink_or_reparse_count"],
            summary["special_file_count"],
            summary["unreadable_count"],
            summary["changed_during_scan_count"],
        )
    )
    return summary, entries, sorted(set(blockers))


def _scan_index_files(root: Path) -> tuple[dict[str, Any], list[_Entry], list[str]]:
    summary = {
        "root_id": "generated_index",
        "relative_root": "db",
        "artifact_class": "REBUILDABLE_GENERATED",
        "scan_mode": "exact_known_files",
        "present": False,
        "coverage_complete": True,
        "entries_seen": len(INDEX_RELATIVE_PATHS),
        "file_count": 0,
        "directory_count": 0,
        "byte_count": 0,
        "symlink_or_reparse_count": 0,
        "special_file_count": 0,
        "unreadable_count": 0,
        "changed_during_scan_count": 0,
        "truncated": False,
    }
    entries: list[_Entry] = []
    blockers: list[str] = []
    for relative in INDEX_RELATIVE_PATHS:
        path = root.joinpath(*PurePosixPath(relative).parts)
        try:
            before_stat = os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError:
            summary["unreadable_count"] += 1
            blockers.append("generated_index_entry_unreadable")
            continue
        summary["present"] = True
        if stat_module.S_ISLNK(before_stat.st_mode) or _is_reparse_point(before_stat):
            summary["symlink_or_reparse_count"] += 1
            blockers.append("generated_index_link_or_reparse_skipped")
            continue
        if not stat_module.S_ISREG(before_stat.st_mode):
            summary["special_file_count"] += 1
            blockers.append("generated_index_special_file_skipped")
            continue
        identity = _identity(before_stat, directory=False)
        try:
            after_stat = os.lstat(path)
        except OSError:
            summary["changed_during_scan_count"] += 1
            blockers.append("generated_index_changed_during_scan")
            continue
        if _identity(after_stat, directory=False) != identity:
            summary["changed_during_scan_count"] += 1
            blockers.append("generated_index_changed_during_scan")
        summary["file_count"] += 1
        summary["byte_count"] += int(before_stat.st_size)
        entries.append(
            _Entry(
                root_id="generated_index",
                relative_path=relative,
                is_directory=False,
                size=int(before_stat.st_size),
                mtime_ns=before_stat.st_mtime_ns,
                device=identity[1],
                inode=identity[2],
            )
        )
    summary["coverage_complete"] = not any(
        (
            summary["symlink_or_reparse_count"],
            summary["special_file_count"],
            summary["unreadable_count"],
            summary["changed_during_scan_count"],
        )
    )
    return summary, entries, sorted(set(blockers))


def _scan_never_touch_presence(
    root: Path,
    spec: ScopeSpec,
) -> tuple[dict[str, Any], list[_Entry], list[str]]:
    """Classify only the root marker; never enumerate possible original bytes."""

    path = root.joinpath(*PurePosixPath(spec.relative_root).parts)
    summary: dict[str, Any] = {
        "root_id": spec.root_id,
        "relative_root": spec.relative_root,
        "artifact_class": spec.artifact_class,
        "scan_mode": "root_presence_only_never_touch",
        "present": False,
        "coverage_complete": True,
        "entries_seen": 0,
        "file_count": 0,
        "directory_count": 0,
        "byte_count": 0,
        "symlink_or_reparse_count": 0,
        "special_file_count": 0,
        "unreadable_count": 0,
        "changed_during_scan_count": 0,
        "truncated": False,
    }
    try:
        before_stat = os.lstat(path)
    except FileNotFoundError:
        return summary, [], []
    except OSError:
        summary.update(
            {
                "present": True,
                "coverage_complete": False,
                "unreadable_count": 1,
            }
        )
        return summary, [], [f"{spec.root_id}_root_unreadable"]
    summary["present"] = True
    if stat_module.S_ISLNK(before_stat.st_mode) or _is_reparse_point(before_stat):
        summary.update(
            {
                "coverage_complete": False,
                "symlink_or_reparse_count": 1,
            }
        )
        return summary, [], [f"{spec.root_id}_root_link_or_reparse"]
    if not stat_module.S_ISDIR(before_stat.st_mode):
        summary.update(
            {
                "coverage_complete": False,
                "special_file_count": 1,
            }
        )
        return summary, [], [f"{spec.root_id}_root_not_directory"]
    identity = _identity(before_stat, directory=True)
    try:
        after_stat = os.lstat(path)
    except OSError:
        summary["changed_during_scan_count"] = 1
    else:
        if _identity(after_stat, directory=True) != identity:
            summary["changed_during_scan_count"] = 1
    if summary["changed_during_scan_count"]:
        summary["coverage_complete"] = False
        return summary, [], [f"{spec.root_id}_changed_during_scan"]
    summary["directory_count"] = 1
    return (
        summary,
        [
            _Entry(
                root_id=spec.root_id,
                relative_path=spec.relative_root,
                is_directory=True,
                size=0,
                mtime_ns=before_stat.st_mtime_ns,
                device=identity[1],
                inode=identity[2],
            )
        ],
        [],
    )


def _reject_duplicate_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


class _ControlFileChangedError(OSError):
    pass


class _ControlFileTooLargeError(ValueError):
    pass


def _read_verified_control_bytes(
    path: Path,
    before_stat: os.stat_result,
    *,
    max_bytes: int,
) -> bytes:
    """Open a bounded control file, verify the opened inode, then read it.

    The descriptor check closes the lstat/open replacement window before any
    bytes are consumed.  The descriptor and path are checked again after the
    read so a concurrent replacement cannot be reported as a stable snapshot.
    """

    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(path, flags)
    try:
        opened_stat = os.fstat(descriptor)
        if (
            stat_module.S_ISLNK(opened_stat.st_mode)
            or _is_reparse_point(opened_stat)
            or not stat_module.S_ISREG(opened_stat.st_mode)
            or _descriptor_comparable_identity(
                _identity(opened_stat, directory=False)
            )
            != _descriptor_comparable_identity(
                _identity(before_stat, directory=False)
            )
        ):
            raise _ControlFileChangedError("control file changed before read")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            payload = handle.read(max_bytes + 1)
        after_descriptor_stat = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    try:
        after_path_stat = os.lstat(path)
    except OSError as exc:
        raise _ControlFileChangedError("control file path changed after read") from exc
    expected = _identity(before_stat, directory=False)
    if (
        _descriptor_comparable_identity(
            _identity(after_descriptor_stat, directory=False)
        )
        != _descriptor_comparable_identity(expected)
        or _identity(after_path_stat, directory=False) != expected
        or stat_module.S_ISLNK(after_path_stat.st_mode)
        or _is_reparse_point(after_path_stat)
        or not stat_module.S_ISREG(after_path_stat.st_mode)
    ):
        raise _ControlFileChangedError("control file changed during read")
    if len(payload) > max_bytes:
        raise _ControlFileTooLargeError("control file size limit reached")
    return payload


def _scan_object_manifest(
    root: Path,
    *,
    max_records: int,
) -> tuple[dict[str, Any], set[str], list[str]]:
    path = root / "objects" / "manifests" / "files.jsonl"
    result: dict[str, Any] = {
        "present": False,
        "valid": True,
        "complete": True,
        "record_count": 0,
        "unique_object_id_count": 0,
        "duplicate_object_id_count": 0,
        "invalid_record_count": 0,
        "bytes_read": 0,
        "changed_during_read": False,
    }
    object_ids: set[str] = set()
    blockers: list[str] = []
    try:
        before_stat = os.lstat(path)
    except FileNotFoundError:
        return result, object_ids, blockers
    except OSError:
        result.update({"present": True, "valid": False, "complete": False})
        return result, object_ids, ["object_manifest_unreadable"]
    result["present"] = True
    if (
        stat_module.S_ISLNK(before_stat.st_mode)
        or _is_reparse_point(before_stat)
        or not stat_module.S_ISREG(before_stat.st_mode)
    ):
        result.update({"valid": False, "complete": False})
        return result, object_ids, ["object_manifest_unsafe"]
    if before_stat.st_size > MAX_OBJECT_MANIFEST_BYTES:
        result.update({"valid": False, "complete": False})
        return result, object_ids, ["object_manifest_size_limit_reached"]

    try:
        payload = _read_verified_control_bytes(
            path,
            before_stat,
            max_bytes=MAX_OBJECT_MANIFEST_BYTES,
        )
    except _ControlFileTooLargeError:
        result.update({"valid": False, "complete": False})
        blockers.append("object_manifest_size_limit_reached")
        payload = b""
    except _ControlFileChangedError:
        result.update(
            {"valid": False, "complete": False, "changed_during_read": True}
        )
        blockers.append("object_manifest_changed_during_read")
        payload = b""
    except OSError:
        result.update({"valid": False, "complete": False})
        blockers.append("object_manifest_unreadable")
        payload = b""

    result["bytes_read"] = len(payload)
    for raw_line in payload.splitlines(keepends=True):
        if not raw_line.strip():
            continue
        if result["record_count"] >= max_records:
            result["complete"] = False
            blockers.append("object_manifest_record_limit_reached")
            break
        result["record_count"] += 1
        if len(raw_line) > MAX_CONTROL_FILE_BYTES:
            result["invalid_record_count"] += 1
            blockers.append("object_manifest_record_too_large")
            continue
        try:
            record = json.loads(
                raw_line.decode("utf-8"),
                object_pairs_hook=_reject_duplicate_json_pairs,
            )
        except (UnicodeError, json.JSONDecodeError, ValueError):
            result["invalid_record_count"] += 1
            blockers.append("object_manifest_record_invalid")
            continue
        object_id = record.get("object_id") if isinstance(record, dict) else None
        match = OBJECT_ID_RE.fullmatch(str(object_id or ""))
        if match is None:
            result["invalid_record_count"] += 1
            blockers.append("object_manifest_object_id_invalid")
            continue
        normalized = f"sha256:{match.group('digest')}"
        if normalized in object_ids:
            result["duplicate_object_id_count"] += 1
            blockers.append("object_manifest_duplicate_object_id")
        object_ids.add(normalized)
    result["unique_object_id_count"] = len(object_ids)
    result["valid"] = bool(
        result["valid"]
        and result["invalid_record_count"] == 0
        and result["duplicate_object_id_count"] == 0
        and not result["changed_during_read"]
    )
    if not result["valid"]:
        result["complete"] = False
    return result, object_ids, sorted(set(blockers))


class _NoDuplicateSafeLoader(yaml.SafeLoader):
    def compose_node(
        self,
        parent: yaml.nodes.Node | None,
        index: int | None,
    ) -> yaml.nodes.Node:
        if self.check_event(yaml.AliasEvent):
            raise ValueError("yaml_alias_not_allowed")
        return super().compose_node(parent, index)


def _construct_unique_mapping(
    loader: _NoDuplicateSafeLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError("duplicate_yaml_key")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_NoDuplicateSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _parse_expiry(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    elif isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _workpack_summary(
    root: Path,
    workpack_entries: list[_Entry],
    *,
    now: datetime,
) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    top_level_directories = {
        PurePosixPath(entry.relative_path).parts[1]
        for entry in workpack_entries
        if entry.is_directory
        and len(PurePosixPath(entry.relative_path).parts) == 2
    }
    package_rows = {
        PurePosixPath(entry.relative_path).parts[1]: entry
        for entry in workpack_entries
        if not entry.is_directory
        and len(PurePosixPath(entry.relative_path).parts) == 3
        and PurePosixPath(entry.relative_path).name == "package.yml"
    }
    states: dict[str, str] = {}
    blockers: list[str] = []
    counts = {
        "package_directory_count": len(top_level_directories),
        "package_metadata_count": len(package_rows),
        "active_count": 0,
        "expired_count": 0,
        "unknown_expiry_count": 0,
        "missing_package_metadata_count": 0,
        "invalid_package_metadata_count": 0,
    }
    for package_name in sorted(top_level_directories):
        row = package_rows.get(package_name)
        if row is None:
            counts["missing_package_metadata_count"] += 1
            blockers.append("workpack_package_metadata_missing")
            states[f"workpacks/{package_name}"] = "workpack_metadata_missing"
            continue
        package_path = root.joinpath(*PurePosixPath(row.relative_path).parts)
        if row.size > MAX_CONTROL_FILE_BYTES:
            counts["invalid_package_metadata_count"] += 1
            blockers.append("workpack_package_metadata_too_large")
            states[row.relative_path] = "workpack_metadata_invalid"
            continue
        try:
            before_stat = os.lstat(package_path)
            expected_identity = _identity(before_stat, directory=False)
            if (
                stat_module.S_ISLNK(before_stat.st_mode)
                or _is_reparse_point(before_stat)
                or not stat_module.S_ISREG(before_stat.st_mode)
                or expected_identity[1] != row.device
                or expected_identity[2] != row.inode
                or expected_identity[3] != row.mtime_ns
                or expected_identity[5] != row.size
            ):
                raise OSError("workpack metadata identity changed")
            payload = _read_verified_control_bytes(
                package_path,
                before_stat,
                max_bytes=MAX_CONTROL_FILE_BYTES,
            )
            data = yaml.load(
                payload.decode("utf-8"),
                Loader=_NoDuplicateSafeLoader,
            )
        except (
            OSError,
            UnicodeError,
            yaml.YAMLError,
            ValueError,
            TypeError,
            RecursionError,
        ):
            counts["invalid_package_metadata_count"] += 1
            blockers.append("workpack_package_metadata_invalid")
            states[row.relative_path] = "workpack_metadata_invalid"
            continue
        if not isinstance(data, dict):
            counts["invalid_package_metadata_count"] += 1
            blockers.append("workpack_package_metadata_invalid")
            states[row.relative_path] = "workpack_metadata_invalid"
            continue
        expires_at = _parse_expiry(data.get("expires_at"))
        if expires_at is None:
            counts["unknown_expiry_count"] += 1
            states[row.relative_path] = "workpack_expiry_unknown"
        elif expires_at <= now:
            counts["expired_count"] += 1
            states[row.relative_path] = "workpack_expired_review_required"
        else:
            counts["active_count"] += 1
            states[row.relative_path] = "workpack_active"
    return counts, states, sorted(set(blockers))


def _class_counts(
    scope_summaries: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for summary in scope_summaries:
        artifact_class = str(summary["artifact_class"])
        counts = result.setdefault(
            artifact_class,
            {"file_count": 0, "directory_count": 0, "byte_count": 0},
        )
        counts["file_count"] += int(summary["file_count"])
        counts["directory_count"] += int(summary["directory_count"])
        counts["byte_count"] += int(summary["byte_count"])
    return {key: result[key] for key in sorted(result)}


def artifact_lifecycle_inventory(
    archive_root: Path | str,
    *,
    max_entries_per_root: int = DEFAULT_MAX_ENTRIES_PER_ROOT,
    max_items: int = DEFAULT_MAX_ITEMS,
    show_relative_paths: bool = False,
    dry_run: bool = True,
    _now: datetime | None = None,
) -> dict[str, Any]:
    # Lazy import avoids turning this focused module into a second authority for
    # archive-root and archive-id validation.
    from . import archive_services

    root = archive_services.require_existing_archive_root(archive_root)
    archive_id = archive_services.read_archive_id(root)
    blockers: list[str] = []
    warnings: list[str] = []
    if dry_run is not True:
        blockers.append("artifact_lifecycle_inventory_requires_dry_run")
    entry_limit, limit_blockers = _normalize_limit(
        max_entries_per_root,
        default=DEFAULT_MAX_ENTRIES_PER_ROOT,
        maximum=MAX_ENTRIES_PER_ROOT,
        field="max_entries_per_root",
    )
    item_limit, item_blockers = _normalize_limit(
        max_items,
        default=DEFAULT_MAX_ITEMS,
        maximum=MAX_ITEMS,
        field="max_items",
    )
    blockers.extend(limit_blockers)
    blockers.extend(item_blockers)
    now = (_now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    scope_summaries: list[dict[str, Any]] = []
    all_entries: list[_Entry] = []
    entries_by_root: dict[str, list[_Entry]] = {}
    for spec in RECURSIVE_SCOPES:
        summary, entries, scope_blockers = _scan_recursive_scope(
            root,
            spec,
            max_entries=entry_limit,
        )
        scope_summaries.append(summary)
        all_entries.extend(entries)
        entries_by_root[spec.root_id] = entries
        blockers.extend(scope_blockers)

    index_summary, index_entries, index_blockers = _scan_index_files(root)
    scope_summaries.append(index_summary)
    all_entries.extend(index_entries)
    entries_by_root["generated_index"] = index_entries
    blockers.extend(index_blockers)

    never_touch_summary, never_touch_entries, never_touch_blockers = (
        _scan_never_touch_presence(root, NEVER_TOUCH_PRESENCE_SCOPE)
    )
    scope_summaries.append(never_touch_summary)
    all_entries.extend(never_touch_entries)
    entries_by_root[NEVER_TOUCH_PRESENCE_SCOPE.root_id] = never_touch_entries
    blockers.extend(never_touch_blockers)

    manifest, manifest_object_ids, manifest_blockers = _scan_object_manifest(
        root,
        max_records=entry_limit,
    )
    blockers.extend(manifest_blockers)
    if manifest["duplicate_object_id_count"]:
        warnings.append("object_manifest_duplicate_object_ids_present")

    local_object_entries = [
        entry
        for entry in entries_by_root.get("local_object_store", [])
        if not entry.is_directory
    ]
    local_store_summary = next(
        item for item in scope_summaries if item["root_id"] == "local_object_store"
    )
    valid_local_objects: list[tuple[_Entry, str]] = []
    invalid_local_layout_count = 0
    for entry in local_object_entries:
        match = LOCAL_OBJECT_PATH_RE.fullmatch(entry.relative_path)
        if match is None or match.group("prefix") != match.group("digest")[:2]:
            invalid_local_layout_count += 1
            continue
        valid_local_objects.append((entry, f"sha256:{match.group('digest')}"))
    if invalid_local_layout_count:
        blockers.append("local_object_store_layout_invalid")

    object_reconciliation_complete = bool(
        local_store_summary["coverage_complete"]
        and manifest["valid"]
        and manifest["complete"]
        and (manifest["present"] or not valid_local_objects)
    )
    if valid_local_objects and not manifest["present"]:
        blockers.append("object_manifest_missing_for_local_store")
    unmanifested_entries: list[_Entry] = []
    if object_reconciliation_complete:
        unmanifested_entries = [
            entry
            for entry, object_id in valid_local_objects
            if object_id not in manifest_object_ids
        ]
    local_object_reconciliation = {
        "complete": object_reconciliation_complete,
        "valid_layout_file_count": len(valid_local_objects),
        "invalid_layout_file_count": invalid_local_layout_count,
        "unmanifested_local_object_candidate_count": (
            len(unmanifested_entries) if object_reconciliation_complete else None
        ),
        "object_bytes_hashed": False,
        "orphan_claimed": False,
    }

    workpack_summary, workpack_states, workpack_blockers = _workpack_summary(
        root,
        entries_by_root.get("workpacks", []),
        now=now,
    )
    blockers.extend(workpack_blockers)

    spec_by_root = {
        spec.root_id: spec
        for spec in (*RECURSIVE_SCOPES, NEVER_TOUCH_PRESENCE_SCOPE)
    }
    candidates: list[tuple[_Entry, str, str]] = []
    for entry in all_entries:
        if entry.is_directory and entry.root_id != NEVER_TOUCH_PRESENCE_SCOPE.root_id:
            continue
        if entry.root_id == "generated_index":
            candidates.append((entry, "REBUILDABLE_GENERATED", "rebuildable_keep_until_requested"))
            continue
        spec = spec_by_root[entry.root_id]
        if entry.root_id == NEVER_TOUCH_PRESENCE_SCOPE.root_id:
            candidates.append((entry, spec.artifact_class, spec.review_state))
            continue
        if not spec.list_files:
            continue
        review_state = workpack_states.get(entry.relative_path, spec.review_state)
        candidates.append((entry, spec.artifact_class, review_state))
    for entry in unmanifested_entries:
        candidates.append(
            (
                entry,
                "DURABLE_ARCHIVE_RECORD",
                "unmanifested_local_object_candidate",
            )
        )

    # A missing package.yml is represented once at package-directory granularity.
    for relative_path, state in workpack_states.items():
        if state != "workpack_metadata_missing":
            continue
        matching = next(
            (
                entry
                for entry in entries_by_root.get("workpacks", [])
                if entry.is_directory and entry.relative_path == relative_path
            ),
            None,
        )
        if matching is not None:
            candidates.append((matching, "DURABLE_WITH_EXPIRY", state))

    candidates.sort(key=lambda row: (row[0].relative_path, row[2]))
    item_rows: list[dict[str, Any]] = []
    for entry, artifact_class, review_state in candidates[:item_limit]:
        item = {
            "artifact_ref": _artifact_ref(archive_id, entry.relative_path),
            "root_id": entry.root_id,
            "artifact_class": artifact_class,
            "review_state": review_state,
            "entry_kind": "directory" if entry.is_directory else "file",
            "bytes": entry.size,
            "modified_at": _iso_from_ns(entry.mtime_ns),
            "age_bucket": _age_bucket(entry.mtime_ns, now=now),
        }
        if show_relative_paths:
            item["relative_path"] = entry.relative_path
        item_rows.append(item)
    if len(candidates) > len(item_rows):
        warnings.append("review_item_listing_truncated")

    blockers = sorted(set(blockers))
    warnings = sorted(set(warnings))
    coverage_complete = bool(
        all(summary["coverage_complete"] for summary in scope_summaries)
        and manifest["complete"]
        and not any(code.endswith("_invalid") for code in blockers)
    )
    if not coverage_complete:
        blockers = sorted(set([*blockers, "declared_lifecycle_coverage_incomplete"]))
    inventory_state = (
        "blocked"
        if blockers
        else ("attention_required" if candidates else "clear")
    )

    next_safe_actions: list[str] = []
    if any(entry.root_id in {"private_scratch", "ai_workbench_scratch", "ai_staging_inbox", "ai_staging_reviewed"} for entry, _, _ in candidates):
        next_safe_actions.append(
            "Run ai-artifact-inventory for the narrower AI fate review; do not delete from this inventory."
        )
    if entries_by_root.get("capture_staging"):
        next_safe_actions.append(
            "Run staged-cleanup-check on one human-selected staged folder before any manual removal."
        )
    if workpack_summary["expired_count"] or workpack_summary["unknown_expiry_count"]:
        next_safe_actions.append(
            "Review workpack purpose, retention obligations, and receipt lineage; expiry alone is not deletion approval."
        )
    if unmanifested_entries:
        next_safe_actions.append(
            "Hold unmanifested local object candidates and repair or prove manifest lineage; never infer that they are disposable or orphaned."
        )
    if entries_by_root.get("noncanonical_in_root_objets"):
        next_safe_actions.append(
            "Use Doctor and the artifact-hygiene in-root objets migration guide; this inventory never reads or moves original bytes."
        )
    if blockers:
        next_safe_actions.append(
            "Resolve coverage blockers or rerun with a safe higher per-root limit before relying on absence or count claims."
        )
    if not next_safe_actions:
        next_safe_actions.append(
            "No review candidates were found in the declared local lifecycle roots."
        )
    next_safe_actions.append(
        "No inventory result grants permission to delete; cleanup remains a separate human-reviewed workflow."
    )

    digest_basis = {
        "schema": INVENTORY_SCHEMA,
        "archive_id": archive_id,
        "coverage_complete": coverage_complete,
        "scope_summaries": scope_summaries,
        "class_counts": _class_counts(scope_summaries),
        "object_manifest": manifest,
        "local_object_reconciliation": local_object_reconciliation,
        "workpacks": workpack_summary,
        "review_candidate_count": len(candidates),
        "items": [
            {key: value for key, value in item.items() if key != "relative_path"}
            for item in item_rows
        ],
        "blockers": blockers,
        "warnings": warnings,
    }
    return {
        "schema": INVENTORY_SCHEMA,
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "artifact_lifecycle_inventory",
        "archive_id": archive_id,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "inventory_state": inventory_state,
        "inventory_digest": _sha256_text(_canonical_json(digest_basis)),
        "scope_policy": {
            "fixed_archive_owned_roots_only": True,
            "archive_wide_scan_performed": False,
            "arbitrary_operator_roots_accepted": False,
            "max_entries_per_root": entry_limit,
            "root_count": len(scope_summaries),
            "unknown_archive_locations_may_exist": True,
        },
        "coverage": {
            "complete": coverage_complete,
            "scope_count": len(scope_summaries),
            "complete_scope_count": sum(
                1 for summary in scope_summaries if summary["coverage_complete"]
            ),
            "scopes": scope_summaries,
            "snapshot_consistency": "bounded_metadata_scan_with_entry_and_directory_recheck",
        },
        "class_counts": _class_counts(scope_summaries),
        "object_manifest": manifest,
        "local_object_reconciliation": local_object_reconciliation,
        "workpacks": workpack_summary,
        "review_candidate_count": len(candidates),
        "item_count": len(item_rows),
        "items_truncated": len(candidates) > len(item_rows),
        "items": item_rows,
        "external_boundaries": {
            "sibling_objet_stores_scanned": False,
            "provider_inventory_requested": False,
            "provider_api_called": False,
            "remote_cleanup_state_known": False,
        },
        "closed_actions": {
            "ordinary_artifact_bodies_read": False,
            "bounded_control_metadata_read": True,
            "content_hashes_calculated": False,
            "object_bytes_read": False,
            "files_written": False,
            "files_deleted": False,
            "zets_written": False,
            "provider_api_called": False,
        },
        "privacy_guards": {
            "relative_paths_echoed": bool(show_relative_paths),
            "absolute_paths_echoed": False,
            "artifact_body_text_echoed": False,
            "object_ids_echoed": False,
            "workpack_ids_echoed": False,
            "provider_values_echoed": False,
            "secrets_read": False,
        },
        "next_safe_actions": next_safe_actions,
        "would_change": [],
        "blockers": blockers,
        "warnings": warnings,
    }
