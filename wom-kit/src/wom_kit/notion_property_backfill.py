"""Lossless, receipt-bound recovery for local Notion mirror properties.

The public API deliberately exposes aggregate counts and digests only.  Raw
Notion page/property values stay in the private in-memory plan and, after an
approved write, in the canonical zettel's ``source_properties`` field.  The
module has no provider or credential dependency: its acquisition source is an
operator-selected local raw-page JSONL file or complete block-mirror directory.

This is a domain service, not a new top-level command.  The existing
``archive migrate`` family exposes it only through the fixed
``notion-source-properties`` target.
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import hmac
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import time
from typing import Any, Callable, Mapping

import yaml

from . import archive_services
from .exact_human_approval import (
    ExactHumanApprovalError,
    _ClaimedExactHumanApproval,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)
from .exact_human_approval_workflow import (
    _execute_exact_human_approved_write,
    _resume_exact_human_approved_write_core,
)
from .exact_operation_manifest import (
    ExactFieldEffect,
    FileExactOperationCheckpointStore,
    ExactOperationApprovalAuthority,
    ExactOperationManifest,
    ExactOperationManifestError,
    ExactOperationItem,
    ExactOperationProgress,
    apply_exact_operation,
    exact_operation_execution_sha256,
    exact_operation_writer_lock,
    hash_field_value,
    revert_exact_operation_fields,
    verify_exact_operation,
)
from .operation_approval_binding import (
    ExactOperationApprovalBinding,
    exact_operation_manifest_approval_binding,
)
from .zettel_index_batch_lifecycle import ZettelIndexBatchLifecycle


SOURCE_PROPERTIES_SCHEMA_VERSION = "wom-kit/notion-source-properties/v0.1"
ACCEPTANCE_SCHEMA_VERSION = (
    "wom-kit/notion-property-backfill-acceptance/v0.1"
)
PLAN_SCHEMA_VERSION = "wom-kit/notion-property-backfill-plan/v0.1"
PLANNING_PROGRESS_SCHEMA_VERSION = (
    "wom-kit/notion-property-backfill-planning-progress/v0.1"
)
RESULT_SCHEMA_VERSION = "wom-kit/notion-property-backfill-result/v0.1"
VERIFICATION_SCHEMA_VERSION = (
    "wom-kit/notion-property-backfill-verification-result/v0.1"
)
REVERT_PLAN_SCHEMA_VERSION = "wom-kit/notion-property-backfill-revert-plan/v0.1"
REVERT_RESULT_SCHEMA_VERSION = "wom-kit/notion-property-backfill-revert-result/v0.1"
EXECUTION_LOCATOR_SCHEMA_VERSION = (
    "wom-kit/notion-property-backfill-execution-locator/v0.1"
)
ACCEPTANCE_BOOTSTRAP_RESULT_SCHEMA_VERSION = (
    "wom-kit/notion-property-backfill-acceptance-bootstrap-result/v0.1"
)
NOTION_PROPERTY_BACKFILL_OPERATION = "notion_property_backfill"
NOTION_PROPERTY_BACKFILL_REVERT_OPERATION = (
    "notion_property_backfill_revert"
)
NOTION_SOURCE_PROPERTIES_MIGRATION_TARGET = "notion-source-properties"
ACCEPTANCE_PRIVATE_PREFIX = PurePosixPath(
    "profiles/local/notion-property-backfill"
)

MAX_MIRROR_BYTES = 4 * 1024 * 1024 * 1024
MAX_MIRROR_LINE_BYTES = 64 * 1024 * 1024
MAX_MIRROR_PAGES = 100_000
MAX_PROPERTIES = 2_000_000
MAX_PROPERTIES_PER_PAGE = 10_000
MAX_CANONICAL_FILE_BYTES = 64 * 1024 * 1024
MAX_ACCEPTANCE_FILE_BYTES = 64 * 1024
CANONICAL_SCAN_WORKERS = 4

_ARCHIVE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_UUID_COMPACT_RE = re.compile(r"^[0-9A-Fa-f]{32}$")
_UUID_DASHED_RE = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_START_MARKER_RE = re.compile(
    rb"^# wom-kit:notion-source-properties:start (sha256:[0-9a-f]{64})(?:\r\n|\n)$"
)
_END_MARKER_LINES = {
    b"# wom-kit:notion-source-properties:end\n",
    b"# wom-kit:notion-source-properties:end\r\n",
}

_LIST_TYPES = frozenset(
    {"files", "multi_select", "people", "relation", "rich_text", "title"}
)
_NULLABLE_STRING_TYPES = frozenset({"email", "phone_number", "url"})
_NULLABLE_OBJECT_TYPES = frozenset({"date", "select", "status", "verification"})
_SYSTEM_STRING_TYPES = frozenset({"created_time", "last_edited_time"})
_SYSTEM_OBJECT_TYPES = frozenset({"created_by", "last_edited_by"})

# Letter 138's historical counts came from this exact compatibility probe: it
# searched only the first 40,000 decoded characters of each mirror file and
# required these exact Korean property names.  These expressions are retained
# solely to explain the old 51/904/2,810 audit without mistaking those figures
# for semantic counts of every populated property of the same Notion type.
_HISTORICAL_PROBE_HEAD_CHARACTERS = 40_000
_HISTORICAL_PROBE_SPECS = {
    "email": (
        "이메일",
        re.compile(r'"이메일":\s*\{[^}]*"email":\s*"([^"]+)"'),
    ),
    "url": (
        "URL",
        re.compile(r'"URL":\s*\{[^}]*"url":\s*"([^"]+)"'),
    ),
    "date": (
        "날짜",
        re.compile(
            r'"날짜":\s*\{[^}]*"date":\s*\{"start":\s*"([^"]+)"'
        ),
    ),
}


class NotionPropertyBackfillError(RuntimeError):
    """A fixed-code error which never retains private archive values."""

    _CODES = {
        "notion_property_backfill_archive_invalid",
        "notion_property_backfill_mirror_invalid",
        "notion_property_backfill_plan_invalid",
        "notion_property_backfill_no_writes",
        "notion_property_backfill_approval_required",
        "notion_property_backfill_plan_changed",
        "notion_property_backfill_path_unsafe",
        "notion_property_backfill_acceptance_output_exists",
        "notion_property_backfill_acceptance_output_not_private",
        "notion_property_backfill_acceptance_output_outcome_unknown",
        "notion_property_backfill_acceptance_output_write_failed",
        "notion_property_backfill_revert_no_writes",
    }

    def __init__(self, code: str) -> None:
        self.code = (
            code
            if code in self._CODES
            else "notion_property_backfill_plan_invalid"
        )
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"NotionPropertyBackfillError({self.code!r})"


@dataclass
class _PlanningProgressPublisher:
    """Publish throttled, content-free acquisition/scan/join progress."""

    hook: Callable[[Mapping[str, Any]], None] | None
    clock: Callable[[], float] = time.monotonic
    current_stage: str | None = None
    stage_started_monotonic: float | None = None
    last_publish_monotonic: float | None = None
    callback_failure_count: int = 0

    def publish(
        self,
        stage: str,
        processed: int,
        total: int,
        *,
        unit: str,
        force: bool = False,
    ) -> None:
        now = self.clock()
        if self.current_stage != stage:
            self.current_stage = stage
            self.stage_started_monotonic = now
            force = True
        if (
            not force
            and processed != total
            and self.last_publish_monotonic is not None
            and now - self.last_publish_monotonic < 1.0
        ):
            return
        stage_started = self.stage_started_monotonic
        stage_elapsed = max(
            0.0,
            now - stage_started if stage_started is not None else 0.0,
        )
        eta_seconds: float | None = None
        if processed > 0 and total >= processed and stage_elapsed > 0:
            eta_seconds = stage_elapsed * (total - processed) / processed
        event = {
            "schema_version": PLANNING_PROGRESS_SCHEMA_VERSION,
            "stage": stage,
            "processed": processed,
            "total": total,
            "unit": unit,
            "stage_elapsed_seconds": round(stage_elapsed, 3),
            "eta_seconds": (
                round(eta_seconds, 3) if eta_seconds is not None else None
            ),
            "private_values_echoed": False,
            "paths_echoed": False,
            "source_page_ids_echoed": False,
            "property_values_echoed": False,
        }
        self.last_publish_monotonic = now
        if self.hook is None:
            return
        try:
            self.hook(event)
        except Exception:
            self.callback_failure_count += 1


def _fail(code: str) -> NotionPropertyBackfillError:
    return NotionPropertyBackfillError(code)


def _canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise _fail("notion_property_backfill_plan_invalid") from None


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _json_sha256(value: Any) -> str:
    return _sha256(_canonical_bytes(value))


def _is_reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _is_link_or_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or _is_reparse(info)


def _resolve_existing_without_links(path: Path | str) -> Path:
    """Resolve an existing path only after every supplied component is safe."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    anchor = Path(absolute.anchor)
    current = anchor
    parts = absolute.parts[1:] if absolute.anchor else absolute.parts
    for part in parts:
        current = current / part
        info = os.lstat(current)
        if _is_link_or_reparse(info):
            raise OSError("linked path component")
    return absolute.resolve(strict=True)


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_mode),
        int(info.st_size),
        int(info.st_mtime_ns),
    )


def _strict_json(raw: bytes | str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def reject_constant(_value: str) -> Any:
        raise ValueError("non-finite number")

    try:
        text = raw if type(raw) is str else raw.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise _fail("notion_property_backfill_mirror_invalid") from None


def _json_tree(value: Any, *, depth: int = 0, nodes: list[int] | None = None) -> Any:
    if nodes is None:
        nodes = [0]
    nodes[0] += 1
    if depth > 64 or nodes[0] > 1_000_000:
        raise ValueError("json tree limit")
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non-finite")
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if type(value) is list:
        return [_json_tree(item, depth=depth + 1, nodes=nodes) for item in value]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("non-string key")
        return {
            key: _json_tree(child, depth=depth + 1, nodes=nodes)
            for key, child in value.items()
        }
    raise ValueError("non-json value")


def _yaml_json_mapping(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        raise ValueError("yaml unicode") from None

    base_loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

    class UniqueLoader(base_loader):  # type: ignore[misc, valid-type]
        def construct_mapping(self, node: Any, deep: bool = False) -> Any:
            if not isinstance(node, yaml.MappingNode):
                return super().construct_mapping(node, deep=deep)
            self.flatten_mapping(node)
            mapping: dict[str, Any] = {}
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if type(key) is not str or key in mapping:
                    raise ValueError("ambiguous yaml mapping")
                mapping[key] = self.construct_object(value_node, deep=deep)
            return mapping

    try:
        loaded = yaml.load(text, Loader=UniqueLoader)
        normalized = _json_tree(loaded)
    except (yaml.YAMLError, ValueError, TypeError, RecursionError):
        raise ValueError("invalid yaml") from None
    if type(normalized) is not dict:
        raise ValueError("yaml root")
    return normalized


def _safe_root(archive_root: Path | str) -> tuple[Path, str]:
    try:
        root = _resolve_existing_without_links(archive_root)
        info = os.lstat(root)
        if _is_link_or_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise OSError
        marker = root / "archive.yml"
        marker_raw = _read_regular(
            _resolve_existing_without_links(marker),
            max_bytes=MAX_ACCEPTANCE_FILE_BYTES,
        )
        document = _yaml_json_mapping(marker_raw)
        archive_id = document.get("archive_id")
        if type(archive_id) is not str or _ARCHIVE_ID_RE.fullmatch(archive_id) is None:
            raise ValueError
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _fail("notion_property_backfill_archive_invalid") from None
    return root, archive_id


def _normalize_source_page_id(value: Any) -> str | None:
    if type(value) is not str or not value or value != value.strip() or len(value) > 1024:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return None
    if _UUID_COMPACT_RE.fullmatch(value):
        return value.lower()
    if _UUID_DASHED_RE.fullmatch(value):
        return value.replace("-", "").lower()
    return value


def _frontmatter_parts(raw: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    """Return newline, frontmatter, closing delimiter line, and body."""

    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("bom")
    lines = raw.splitlines(keepends=True)
    if not lines or lines[0] not in {b"---\n", b"---\r\n"}:
        raise ValueError("frontmatter boundary")
    newline = b"\r\n" if lines[0].endswith(b"\r\n") else b"\n"
    closing_index: int | None = None
    for index in range(1, len(lines)):
        line = lines[index]
        if line in {b"---\n", b"---\r\n", b"---"}:
            if line not in {b"---", b"---" + newline}:
                raise ValueError("mixed newline")
            closing_index = index
            break
    if closing_index is None:
        raise ValueError("frontmatter boundary")
    frontmatter = b"".join(lines[1:closing_index])
    closing = lines[closing_index]
    body = b"".join(lines[closing_index + 1 :])
    return newline, frontmatter, closing, body


def _read_regular(path: Path, *, max_bytes: int) -> bytes:
    try:
        before = os.lstat(path)
        if (
            _is_link_or_reparse(before)
            or not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size > max_bytes
        ):
            raise OSError
        raw = path.read_bytes()
        after = os.lstat(path)
        if _identity(before) != _identity(after) or len(raw) > max_bytes:
            raise OSError
        return raw
    except OSError:
        raise ValueError("unsafe regular file") from None


def load_notion_property_backfill_acceptance(
    path: Path | str,
) -> dict[str, Any]:
    """Read one bounded, byte-canonical local acceptance profile.

    CLI bootstrap publication uses :func:`_canonical_bytes`.  Requiring the
    exact same bytes here means the later approved plan binds the reviewed
    create-only artifact, not a hand-copied or whitespace-rewritten lookalike.
    """

    try:
        resolved = _resolve_existing_without_links(path)
        raw = _read_regular(resolved, max_bytes=MAX_ACCEPTANCE_FILE_BYTES)
        document = _strict_json(raw)
        normalized = _json_tree(document)
        if (
            type(normalized) is not dict
            or raw != _canonical_bytes(normalized)
        ):
            raise ValueError
        return normalized
    except (NotionPropertyBackfillError, OSError, TypeError, ValueError):
        raise _fail("notion_property_backfill_plan_invalid") from None


def _acceptance_private_output_path(
    root: Path,
    relative_value: str,
) -> Path:
    if (
        type(relative_value) is not str
        or not relative_value
        or "\\" in relative_value
        or any(ord(character) < 32 or ord(character) == 127 for character in relative_value)
    ):
        raise _fail("notion_property_backfill_path_unsafe")
    relative = PurePosixPath(relative_value)
    prefix_parts = ACCEPTANCE_PRIVATE_PREFIX.parts
    if (
        relative.is_absolute()
        or relative.parts[: len(prefix_parts)] != prefix_parts
        or len(relative.parts) <= len(prefix_parts)
        or any(part in {"", ".", ".."} for part in relative.parts)
        or any(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", part) is None
            for part in relative.parts[len(prefix_parts) :]
        )
        or relative.suffix != ".json"
    ):
        raise _fail("notion_property_backfill_path_unsafe")
    candidate = root.joinpath(*relative.parts)
    try:
        candidate.resolve(strict=False).relative_to(root)
    except (OSError, RuntimeError, ValueError):
        raise _fail("notion_property_backfill_path_unsafe") from None
    return candidate


def _require_profiles_local_private(root: Path) -> None:
    """Require the exact ignored-local boundary before staging evidence."""

    try:
        raw = _read_regular(root / ".gitignore", max_bytes=256 * 1024)
        text = raw.decode("utf-8-sig")
    except (OSError, UnicodeError, ValueError):
        raise _fail(
            "notion_property_backfill_acceptance_output_not_private"
        ) from None
    ignored = False
    later_negation = False
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        if line in {
            "profiles/local/",
            "/profiles/local/",
            "profiles/local",
            "/profiles/local",
        }:
            ignored = True
            later_negation = False
            continue
        if ignored and line.startswith("!"):
            # Full Git wildmatch semantics are deliberately not reimplemented.
            # Any later re-inclusion could expose the private acceptance file.
            later_negation = True
    if not ignored or later_negation:
        raise _fail("notion_property_backfill_acceptance_output_not_private")


def _write_all(descriptor: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        written = os.write(descriptor, raw[offset:])
        if written <= 0:
            raise OSError("write made no progress")
        offset += written


def _fsync_directory(path: Path) -> bool:
    """Flush one POSIX directory; Windows publication uses MoveFileExW."""

    if os.name == "nt":
        return False
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY)
        os.fsync(descriptor)
        return True
    except OSError:
        return False
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _publish_acceptance_final_no_replace(
    temporary: Path,
    path: Path,
) -> tuple[bool, bool]:
    """Publish one sibling create-only and report temp consumption/durability.

    Windows uses the documented write-through move so the final namespace
    entry, not merely the temporary file contents, is flushed before success.
    POSIX keeps the hard-link no-replace boundary and requires the caller to
    remove the temporary name and fsync the parent directory afterward.
    """

    if os.name != "nt":
        try:
            os.link(temporary, path, follow_symlinks=False)
        except TypeError:  # pragma: no cover - compatibility fallback.
            os.link(temporary, path)
        return False, False

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    move_file_ex = kernel32.MoveFileExW
    move_file_ex.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
    ]
    move_file_ex.restype = wintypes.BOOL
    movefile_write_through = 0x00000008
    if not move_file_ex(
        str(temporary),
        str(path),
        movefile_write_through,
    ):
        error = ctypes.get_last_error()
        if error in {80, 183}:  # ERROR_FILE_EXISTS / ERROR_ALREADY_EXISTS
            raise FileExistsError(error, "acceptance output exists", path)
        raise ctypes.WinError(error)
    return True, True


def _observe_exact_acceptance(path: Path, expected: bytes) -> str:
    """Classify a possibly-published final path without trusting its name."""

    descriptor = -1
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        return "not_written"
    except OSError:
        return "unknown"
    try:
        if (
            _is_link_or_reparse(before)
            or not stat.S_ISREG(before.st_mode)
            or before.st_size != len(expected)
        ):
            return "unknown"
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if _identity(opened) != _identity(before):
            return "unknown"
        chunks: list[bytes] = []
        total = 0
        while total <= len(expected):
            chunk = os.read(descriptor, min(64 * 1024, len(expected) + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.lstat(path)
        if (
            _identity(opened) != _identity(after)
            or total != len(expected)
            or b"".join(chunks) != expected
        ):
            return "unknown"
        return "verified_exact"
    except OSError:
        return "unknown"
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _publish_acceptance_create_only(
    root: Path,
    path: Path,
    raw: bytes,
) -> bool:
    """Publish complete private bytes create-only; never replace a file."""

    _ensure_internal_parents(root, path, create=True)
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    descriptor: int | None = None
    published = False
    temporary_consumed = False
    namespace_durable = False
    try:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(temporary, flags, 0o600)
        opened = os.fstat(descriptor)
        if _is_link_or_reparse(opened) or not stat.S_ISREG(opened.st_mode):
            raise OSError("unsafe temporary")
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        _ensure_internal_parents(root, path, create=False)
        temporary_consumed, namespace_durable = (
            _publish_acceptance_final_no_replace(temporary, path)
        )
        published = True
        if not temporary_consumed:
            try:
                temporary.unlink()
            except OSError:
                raise _fail(
                    "notion_property_backfill_acceptance_output_outcome_unknown"
                ) from None
            temporary_consumed = True
    except FileExistsError:
        raise _fail(
            "notion_property_backfill_acceptance_output_exists"
        ) from None
    except NotionPropertyBackfillError:
        raise
    except (OSError, ValueError):
        raise _fail(
            "notion_property_backfill_acceptance_output_write_failed"
        ) from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if not temporary_consumed:
            try:
                temporary.unlink(missing_ok=True)
                temporary_consumed = True
            except OSError:
                # A published hard link with a surviving temporary name has
                # nlink=2 and is rejected by the exact acceptance loader.  It
                # is never a usable-success result.
                raise _fail(
                    "notion_property_backfill_acceptance_output_outcome_unknown"
                ) from None
    if published and not namespace_durable:
        namespace_durable = _fsync_directory(path.parent)
    observed = _observe_exact_acceptance(path, raw)
    if (
        observed == "verified_exact"
        and namespace_durable
        and temporary_consumed
    ):
        return True
    if observed == "not_written":
        raise _fail(
            "notion_property_backfill_acceptance_output_write_failed"
        ) from None
    raise _fail(
        "notion_property_backfill_acceptance_output_outcome_unknown"
    )


def persist_notion_property_backfill_acceptance_candidate(
    plan: "_NotionPropertyBackfillPlan",
    output_relative: str,
) -> dict[str, Any]:
    """Create one private reviewed-acceptance candidate without approval.

    This is a recovery-evidence staging write only.  It never mutates a zettel
    and it cannot overwrite an existing candidate.
    """

    if type(plan) is not _NotionPropertyBackfillPlan:
        raise _fail("notion_property_backfill_plan_invalid")
    root, archive_id = _safe_root(plan.archive_root)
    if archive_id != plan.archive_id:
        raise _fail("notion_property_backfill_plan_changed")
    _require_profiles_local_private(root)
    output = _acceptance_private_output_path(root, output_relative)
    candidate = plan.public_document()["acceptance_candidate"]
    raw = _canonical_bytes(candidate)
    if len(raw) > MAX_ACCEPTANCE_FILE_BYTES:
        raise _fail("notion_property_backfill_plan_invalid")
    cleanup_complete = _publish_acceptance_create_only(root, output, raw)
    return {
        "schema_version": ACCEPTANCE_BOOTSTRAP_RESULT_SCHEMA_VERSION,
        "ok": True,
        "reason_code": "notion_property_backfill_acceptance_candidate_created",
        "acceptance_document_sha256": _sha256(raw),
        "mirror_snapshot_sha256": plan.mirror_sha256,
        "mirror_page_count": plan.mirror_page_count,
        "source_property_count": plan.source_property_count,
        "populated_property_count": plan.populated_property_count,
        "indeterminate_property_count": plan.indeterminate_property_count,
        "opaque_property_count": plan.opaque_property_count,
        "private_output_created": True,
        "create_only": True,
        "temporary_cleanup_complete": cleanup_complete,
        "namespace_durability_confirmed": True,
        "recovery_evidence_staging_write": True,
        "canonical_zettel_writes_performed": False,
        "writes_performed": True,
        "private_values_echoed": False,
        "paths_echoed": False,
        "source_page_ids_echoed": False,
        "property_values_echoed": False,
    }


def _frontmatter(raw: bytes) -> dict[str, Any]:
    _newline, frontmatter, _closing, _body = _frontmatter_parts(raw)
    return _yaml_json_mapping(frontmatter)


def _canonical_source_page_id(frontmatter: Mapping[str, Any]) -> str | None:
    facets = frontmatter.get("facets")
    if type(facets) is not dict or "source_page_id" not in facets:
        return None
    raw = facets.get("source_page_id")
    values = raw if type(raw) is list else [raw]
    normalized = {_normalize_source_page_id(value) for value in values}
    if None in normalized or len(normalized) != 1:
        raise ValueError("ambiguous source page id")
    return next(iter(normalized))


def _generic_population(value: Any) -> str:
    if value is None or value == "" or value == [] or value == {}:
        return "empty"
    return "populated"


def _typed_population(property_type: str, payload: Mapping[str, Any]) -> str:
    if payload.get("has_more") is True:
        return "review"
    if payload.get("next_cursor") is not None or payload.get("next_url") is not None:
        return "review"
    if property_type not in payload:
        return "review"
    value = payload[property_type]
    if property_type in _LIST_TYPES:
        return _generic_population(value) if type(value) is list else "review"
    if property_type in _NULLABLE_STRING_TYPES:
        return _generic_population(value) if value is None or type(value) is str else "review"
    if property_type == "date":
        if value is None:
            return "empty"
        if type(value) is not dict:
            return "review"
        start = value.get("start")
        end = value.get("end")
        time_zone = value.get("time_zone")
        if (
            type(start) is not str
            or not start
            or (end is not None and type(end) is not str)
            or (time_zone is not None and type(time_zone) is not str)
        ):
            return "review"
        return "populated"
    if property_type in _NULLABLE_OBJECT_TYPES:
        return _generic_population(value) if value is None or type(value) is dict else "review"
    if property_type == "number":
        if value is None:
            return "empty"
        if type(value) in {int, float} and not (
            type(value) is float and not math.isfinite(value)
        ):
            return "populated"
        return "review"
    if property_type == "checkbox":
        return "populated" if type(value) is bool else "review"
    if property_type in _SYSTEM_STRING_TYPES:
        return "populated" if type(value) is str and bool(value) else "review"
    if property_type in _SYSTEM_OBJECT_TYPES:
        return "populated" if type(value) is dict and bool(value) else "review"
    if property_type in {"formula", "rollup"}:
        if type(value) is not dict or type(value.get("type")) is not str:
            return "review"
        result_type = value["type"]
        if result_type not in value:
            return "review"
        return _generic_population(value[result_type])
    if property_type in {"unique_id", "button"}:
        return _generic_population(value) if value is None or type(value) is dict else "review"
    # Unknown/future Notion property types are retained losslessly.  Their
    # population state uses only JSON emptiness and never causes omission.
    return _generic_population(value)


@dataclass(frozen=True, repr=False)
class _MirrorProperty:
    property_id: str
    property_name: str
    property_type: str
    population_state: str
    raw_json_payload: dict[str, Any]

    def document(self) -> dict[str, Any]:
        return {
            "property_id": self.property_id,
            "property_name": self.property_name,
            "property_type": self.property_type,
            "population_state": self.population_state,
            "raw_json_payload": self.raw_json_payload,
        }


@dataclass(frozen=True, repr=False)
class _OpaqueMirrorProperty:
    property_id: str
    raw_json_value: Any

    def document(self) -> dict[str, Any]:
        return {
            "property_id": self.property_id,
            "raw_json_value": self.raw_json_value,
        }


@dataclass(frozen=True, repr=False)
class _MirrorPage:
    source_page_id: str
    normalized_source_page_id: str | None
    record_sha256: str
    source_format: str
    semantics_unavailable: bool
    properties: tuple[_MirrorProperty, ...]
    opaque_properties: tuple[_OpaqueMirrorProperty, ...]
    property_count: int
    populated_property_count: int
    indeterminate_property_count: int
    historical_head_match_types: tuple[str, ...]
    historical_full_match_types: tuple[str, ...]
    historical_probe_reasons: tuple[tuple[str, str], ...]
    review_codes: tuple[str, ...]
    warning_codes: tuple[str, ...]

    def source_properties(self) -> dict[str, Any]:
        return {
            "schema_version": SOURCE_PROPERTIES_SCHEMA_VERSION,
            "source_system": "notion",
            "source_format": self.source_format,
            "semantics_unavailable": self.semantics_unavailable,
            "source_page_id": self.source_page_id,
            "source_mirror_record_sha256": self.record_sha256,
            "property_count": self.property_count,
            "populated_property_count": self.populated_property_count,
            "empty_property_count": (
                self.property_count
                - self.populated_property_count
                - self.indeterminate_property_count
            ),
            "indeterminate_property_count": self.indeterminate_property_count,
            "properties": [item.document() for item in self.properties],
            "opaque_property_count": len(self.opaque_properties),
            "opaque_properties": [
                item.document() for item in self.opaque_properties
            ],
        }


def _parse_mirror_page(raw_line: bytes) -> _MirrorPage:
    try:
        raw_text = raw_line.decode("utf-8")
    except UnicodeError:
        raise _fail("notion_property_backfill_mirror_invalid") from None
    document = _strict_json(raw_text)
    if type(document) is not dict:
        raise _fail("notion_property_backfill_mirror_invalid")
    review_codes: set[str] = set()
    warning_codes: set[str] = set()
    opaque_parsed: list[_OpaqueMirrorProperty] = []
    source_property_count: int | None = None
    # Two locally preserved formats are supported.  A raw-page JSONL row has
    # ``id``/``properties`` at its root.  The complete block mirror stores one
    # page per file and wraps the same raw page as ``object_record``.
    if type(document.get("object_record")) is dict:
        source_format = "notion_api_page"
        object_record = document["object_record"]
        page_id = document.get("page_id")
        if page_id != object_record.get("id"):
            raise _fail("notion_property_backfill_mirror_invalid")
        properties = object_record.get("properties")
    elif type(document.get("recordMap")) is dict:
        source_format = "legacy_record_map"
        page_id = document.get("page_id")
        record_map = document["recordMap"]
        blocks = record_map.get("block")
        record = blocks.get(page_id) if type(blocks) is dict else None
        outer_value = record.get("value") if type(record) is dict else None
        root_block = (
            outer_value.get("value") if type(outer_value) is dict else None
        )
        internal_properties = (
            root_block.get("properties") if type(root_block) is dict else None
        )
        if type(page_id) is not str or type(root_block) is not dict:
            raise _fail("notion_property_backfill_mirror_invalid")
        # recordMap property keys are internal IDs.  Without a trustworthy
        # collection-schema/type join, interpreting them as names or Notion
        # API types would manufacture semantics.  Exact 1:1 targets may still
        # receive the untouched JSON values in an explicitly opaque envelope.
        if type(internal_properties) is dict:
            source_property_count = len(internal_properties)
            for property_id, raw_value in internal_properties.items():
                if type(property_id) is not str or not property_id:
                    review_codes.add("record_map_property_shape_invalid")
                    continue
                try:
                    normalized_raw_value = _json_tree(raw_value)
                except ValueError:
                    raise _fail("notion_property_backfill_mirror_invalid") from None
                opaque_parsed.append(
                    _OpaqueMirrorProperty(
                        property_id=property_id,
                        raw_json_value=normalized_raw_value,
                    )
                )
            opaque_parsed.sort(key=lambda item: item.property_id)
            properties = {}
            warning_codes.add("record_map_property_semantics_unavailable")
        else:
            # A root block without ``properties`` is still one acquired source
            # page.  Keep it in the review inventory instead of rejecting the
            # entire 11,585-page mirror or silently dropping the page.
            properties = {}
            source_property_count = 0
            review_codes.add("record_map_root_properties_absent")
    else:
        source_format = "notion_api_page"
        page_id = document.get("id")
        properties = document.get("properties")
    if type(page_id) is not str or type(properties) is not dict:
        raise _fail("notion_property_backfill_mirror_invalid")
    page_property_count = (
        source_property_count
        if source_property_count is not None
        else len(properties)
    )
    if page_property_count > MAX_PROPERTIES_PER_PAGE:
        # A write must never create a source_properties value rejected by the
        # shipped maxItems contract.  Preserve the page in review accounting.
        review_codes.add("property_count_exceeds_schema_limit")
    normalized = _normalize_source_page_id(page_id)
    if normalized is None:
        review_codes.add("source_page_id_invalid")
    parsed: list[_MirrorProperty] = []
    property_ids: set[str] = set()
    populated = 0
    indeterminate = len(opaque_parsed)
    for property_name, raw_payload in properties.items():
        if type(property_name) is not str or type(raw_payload) is not dict:
            review_codes.add("property_shape_invalid")
            continue
        try:
            payload = _json_tree(raw_payload)
        except ValueError:
            raise _fail("notion_property_backfill_mirror_invalid") from None
        property_id = payload.get("id")
        property_type = payload.get("type")
        if type(property_id) is not str or not property_id or type(property_type) is not str or not property_type:
            review_codes.add("property_shape_invalid")
            continue
        if property_id in property_ids:
            review_codes.add("duplicate_property_id")
        property_ids.add(property_id)
        state = _typed_population(property_type, payload)
        if state == "review":
            indeterminate += 1
            review_codes.add("property_incomplete_or_indeterminate")
        elif state == "populated":
            populated += 1
        parsed.append(
            _MirrorProperty(
                property_id=property_id,
                property_name=property_name,
                property_type=property_type,
                population_state=state,
                raw_json_payload=payload,
            )
        )
    if len(parsed) != len(properties):
        # No malformed property can disappear into a successful write.
        indeterminate += len(properties) - len(parsed)
    parsed.sort(key=lambda item: (item.property_id, item.property_name))
    historical_head_match_types: list[str] = []
    historical_full_match_types: list[str] = []
    historical_probe_reasons: list[tuple[str, str]] = []
    for property_type, (expected_name, pattern) in sorted(
        _HISTORICAL_PROBE_SPECS.items()
    ):
        expected_name_token = f'"{expected_name}"'
        head_text = raw_text[:_HISTORICAL_PROBE_HEAD_CHARACTERS]
        head_match = (
            expected_name_token in head_text and pattern.search(head_text) is not None
        )
        full_match = head_match or (
            expected_name_token in raw_text and pattern.search(raw_text) is not None
        )
        if head_match:
            historical_head_match_types.append(property_type)
        if full_match:
            historical_full_match_types.append(property_type)
        populated_of_type = tuple(
            item
            for item in parsed
            if item.property_type == property_type
            and item.population_state == "populated"
        )
        exact_name = any(
            item.property_name == expected_name for item in populated_of_type
        )
        other_name = any(
            item.property_name != expected_name for item in populated_of_type
        )
        if head_match and not populated_of_type:
            reason = "regex_without_root_semantic"
        elif populated_of_type and not head_match:
            if exact_name and full_match:
                reason = "exact_name_after_40k"
            elif exact_name:
                reason = "exact_name_format_mismatch"
            elif other_name:
                reason = "other_property_name_only"
            else:
                reason = "semantic_unclassified"
        elif populated_of_type and head_match:
            reason = "matched_same_page"
        else:
            continue
        historical_probe_reasons.append((property_type, reason))
    return _MirrorPage(
        source_page_id=page_id,
        normalized_source_page_id=normalized,
        record_sha256=_sha256(raw_line),
        source_format=source_format,
        semantics_unavailable=source_format == "legacy_record_map",
        properties=tuple(parsed),
        opaque_properties=tuple(opaque_parsed),
        property_count=page_property_count,
        populated_property_count=populated,
        indeterminate_property_count=indeterminate,
        historical_head_match_types=tuple(historical_head_match_types),
        historical_full_match_types=tuple(historical_full_match_types),
        historical_probe_reasons=tuple(historical_probe_reasons),
        review_codes=tuple(sorted(review_codes)),
        warning_codes=tuple(sorted(warning_codes)),
    )


def _safe_mirror_directory_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []

    def walk_failed(_error: OSError) -> None:
        raise OSError("mirror traversal incomplete")

    for current, directories, names in os.walk(
        root,
        followlinks=False,
        onerror=walk_failed,
    ):
        current_path = Path(current)
        safe_directories: list[str] = []
        for name in sorted(directories):
            candidate = current_path / name
            info = os.lstat(candidate)
            if _is_link_or_reparse(info) or not stat.S_ISDIR(info.st_mode):
                raise OSError("unsafe mirror directory")
            safe_directories.append(name)
        directories[:] = safe_directories
        for name in sorted(names):
            candidate = current_path / name
            if candidate.suffix.lower() == ".json":
                files.append(candidate)
    return tuple(sorted(files, key=lambda item: item.relative_to(root).as_posix()))


def _read_mirror(
    path: Path | str,
    *,
    progress: _PlanningProgressPublisher,
) -> tuple[Path, str, str, tuple[_MirrorPage, ...]]:
    try:
        resolved = _resolve_existing_without_links(path)
        before = os.lstat(resolved)
        if _is_link_or_reparse(before):
            raise OSError
        digest = hashlib.sha256()
        pages: list[_MirrorPage] = []
        total_properties = 0
        total_bytes = 0
        if stat.S_ISREG(before.st_mode):
            if before.st_nlink != 1 or before.st_size > MAX_MIRROR_BYTES:
                raise OSError
            source_kind = "raw_page_jsonl"
            processed_bytes = 0
            progress.publish(
                "acquire_mirror",
                0,
                before.st_size,
                unit="bytes",
                force=True,
            )
            with resolved.open("rb") as stream:
                while True:
                    line = stream.readline(MAX_MIRROR_LINE_BYTES + 1)
                    if not line:
                        break
                    if len(line) > MAX_MIRROR_LINE_BYTES or not line.strip():
                        raise ValueError
                    digest.update(line)
                    pages.append(_parse_mirror_page(line))
                    processed_bytes += len(line)
                    progress.publish(
                        "acquire_mirror",
                        processed_bytes,
                        before.st_size,
                        unit="bytes",
                    )
                    total_properties += pages[-1].property_count
                    if len(pages) > MAX_MIRROR_PAGES or total_properties > MAX_PROPERTIES:
                        raise ValueError
            after = os.lstat(resolved)
            if _identity(before) != _identity(after):
                raise OSError
        elif stat.S_ISDIR(before.st_mode):
            source_kind = "block_mirror_directory"
            initial_files = _safe_mirror_directory_files(resolved)
            if not initial_files:
                raise OSError
            progress.publish(
                "acquire_mirror",
                0,
                len(initial_files),
                unit="files",
                force=True,
            )
            for index, candidate in enumerate(initial_files, start=1):
                raw = _read_regular(candidate, max_bytes=MAX_MIRROR_LINE_BYTES)
                total_bytes += len(raw)
                if total_bytes > MAX_MIRROR_BYTES:
                    raise ValueError
                relative = candidate.relative_to(resolved).as_posix().encode("utf-8")
                digest.update(len(relative).to_bytes(4, "big"))
                digest.update(relative)
                digest.update(hashlib.sha256(raw).digest())
                page = _parse_mirror_page(raw)
                if _normalize_source_page_id(candidate.stem) != page.normalized_source_page_id:
                    raise ValueError
                pages.append(page)
                progress.publish(
                    "acquire_mirror",
                    index,
                    len(initial_files),
                    unit="files",
                )
                total_properties += page.property_count
                if len(pages) > MAX_MIRROR_PAGES or total_properties > MAX_PROPERTIES:
                    raise ValueError
            after = os.lstat(resolved)
            if (
                _identity(before) != _identity(after)
                or initial_files != _safe_mirror_directory_files(resolved)
            ):
                raise OSError
        else:
            raise OSError
        if not pages:
            raise OSError
    except NotionPropertyBackfillError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _fail("notion_property_backfill_mirror_invalid") from None
    return resolved, source_kind, "sha256:" + digest.hexdigest(), tuple(pages)


@dataclass(frozen=True, repr=False)
class _CanonicalTarget:
    path: Path
    target_ref: str
    raw: bytes
    frontmatter: dict[str, Any]
    normalized_source_page_id: str


def _read_canonical_candidate(
    root: Path,
    archive_id: str,
    candidate: Path,
) -> tuple[str, _CanonicalTarget | tuple[str, str] | None]:
    """Read and classify one canonical candidate without reflecting its path."""

    try:
        raw = _read_regular(candidate, max_bytes=MAX_CANONICAL_FILE_BYTES)
    except ValueError:
        return "invalid", None
    try:
        frontmatter = _frontmatter(raw)
    except ValueError:
        candidate_text = raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
        try:
            decoded = candidate_text.decode("utf-8", errors="strict")
        except UnicodeError:
            # If the bytes are unreadable, absence of a source id cannot be
            # proven.  Treat this as a global canonical-scan blocker.
            return "invalid", None
        if "source_page_id" in decoded:
            return "invalid", None
        reason = (
            "bom_non_candidate_no_source_page_id"
            if raw.startswith(b"\xef\xbb\xbf")
            else "malformed_non_candidate_no_source_page_id"
        )
        return (
            "excluded_non_candidate",
            (
                _sha256(
                    candidate.relative_to(root).as_posix().encode("utf-8")
                ),
                reason,
            ),
        )
    try:
        if frontmatter.get("status") == "redacted":
            return "non_target", None
        source_id = _canonical_source_page_id(frontmatter)
        if source_id is None:
            return "non_target", None
        zettel_id = frontmatter.get("id")
        if (
            type(zettel_id) is not str
            or not zettel_id
            or frontmatter.get("archive_id") != archive_id
        ):
            return "invalid", None
        if frontmatter.get("status") != "canonical":
            return "non_target", None
        target_ref = candidate.relative_to(root).as_posix()
        return (
            "target",
            _CanonicalTarget(
                candidate,
                target_ref,
                raw,
                frontmatter,
                source_id,
            ),
        )
    except ValueError:
        return "invalid", None


def _discover_canonical_files(
    root: Path,
    zettels: Path,
) -> tuple[tuple[Path, ...], int]:
    """Snapshot candidate names and surface every traversal failure."""

    candidates: list[Path] = []
    invalid_count = 0
    traversal_errors: list[OSError] = []

    def walk_failed(error: OSError) -> None:
        traversal_errors.append(error)

    for current, directories, files in os.walk(
        zettels,
        followlinks=False,
        onerror=walk_failed,
    ):
        current_path = Path(current)
        safe_directories: list[str] = []
        for name in sorted(directories):
            candidate = current_path / name
            try:
                info = os.lstat(candidate)
                if _is_link_or_reparse(info) or not stat.S_ISDIR(info.st_mode):
                    invalid_count += 1
                else:
                    safe_directories.append(name)
            except OSError:
                invalid_count += 1
        directories[:] = safe_directories
        for name in sorted(files):
            if name.lower().endswith(".md"):
                candidates.append(current_path / name)
    invalid_count += len(traversal_errors)
    return (
        tuple(
            sorted(
                candidates,
                key=lambda item: item.relative_to(root).as_posix(),
            )
        ),
        invalid_count,
    )


def _scan_canonical(
    root: Path,
    archive_id: str,
    *,
    progress: _PlanningProgressPublisher,
) -> tuple[
    dict[str, list[_CanonicalTarget]],
    int,
    int,
    tuple[tuple[str, str], ...],
]:
    zettels = root / "zettels"
    try:
        zettels_info = os.lstat(zettels)
    except OSError:
        progress.publish(
            "scan_canonical",
            0,
            0,
            unit="files",
            force=True,
        )
        return {}, 0, 0, ()
    try:
        resolved_zettels = zettels.resolve(strict=True)
        resolved_zettels.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        resolved_zettels = zettels
        zettels_safe = False
    else:
        zettels_safe = (
            not _is_link_or_reparse(zettels_info)
            and stat.S_ISDIR(zettels_info.st_mode)
            and resolved_zettels == zettels
        )
    if not zettels_safe:
        progress.publish(
            "scan_canonical",
            0,
            0,
            unit="files",
            force=True,
        )
        return {}, 0, 1, ()
    by_source: dict[str, list[_CanonicalTarget]] = {}
    excluded_non_candidate_malformed: list[tuple[str, str]] = []
    progress.publish(
        "discover_canonical",
        0,
        1,
        unit="scan",
        force=True,
    )
    candidates, invalid_count = _discover_canonical_files(root, zettels)
    progress.publish(
        "discover_canonical",
        1,
        1,
        unit="scan",
        force=True,
    )
    progress.publish(
        "scan_canonical",
        0,
        len(candidates),
        unit="files",
        force=True,
    )
    results: list[
        tuple[str, _CanonicalTarget | tuple[str, str] | None] | None
    ] = [None] * len(candidates)
    with ThreadPoolExecutor(
        max_workers=CANONICAL_SCAN_WORKERS,
        thread_name_prefix="wom-notion-canonical-scan",
    ) as executor:
        pending = {
            executor.submit(
                _read_canonical_candidate,
                root,
                archive_id,
                candidate,
            ): index
            for index, candidate in enumerate(candidates)
        }
        completed_count = 0
        while pending:
            completed, _not_done = wait(
                pending,
                timeout=1.0,
                return_when=FIRST_COMPLETED,
            )
            if not completed:
                progress.publish(
                    "scan_canonical",
                    completed_count,
                    len(candidates),
                    unit="files",
                    force=True,
                )
                continue
            for future in completed:
                index = pending.pop(future)
                try:
                    results[index] = future.result()
                except Exception:
                    results[index] = ("invalid", None)
                completed_count += 1
            progress.publish(
                "scan_canonical",
                completed_count,
                len(candidates),
                unit="files",
            )
    final_candidates, final_invalid_count = _discover_canonical_files(
        root,
        zettels,
    )
    if final_candidates != candidates or final_invalid_count != invalid_count:
        invalid_count += 1
    for result in results:
        if result is None or result[0] == "invalid":
            invalid_count += 1
            continue
        kind, payload = result
        if kind == "excluded_non_candidate":
            if type(payload) is tuple:
                excluded_non_candidate_malformed.append(payload)
            else:
                invalid_count += 1
        elif kind == "target":
            if type(payload) is not _CanonicalTarget:
                invalid_count += 1
                continue
            by_source.setdefault(
                payload.normalized_source_page_id, []
            ).append(payload)
    for targets in by_source.values():
        targets.sort(key=lambda item: item.target_ref)
    return (
        by_source,
        len(candidates),
        invalid_count,
        tuple(sorted(excluded_non_candidate_malformed)),
    )


def _canonical_projection_sha256(
    canonical: Mapping[str, list[_CanonicalTarget]],
    *,
    archive_id: str,
    invalid_count: int,
) -> str:
    """Bind canonical source-id/target identity without unrelated file bytes."""

    rows = []
    for source_id in sorted(canonical):
        for target in canonical[source_id]:
            rows.append(
                {
                    "normalized_source_page_id": source_id,
                    "target_ref": target.target_ref,
                    "target_identity_sha256": _target_identity_sha256(
                        archive_id,
                        target.target_ref,
                        target.frontmatter,
                    ),
                }
            )
    return _json_sha256(
        {
            "schema_version": (
                "wom-kit/notion-property-canonical-projection/v0.1"
            ),
            "invalid_canonical_count": invalid_count,
            "targets": rows,
        }
    )


def _dump_managed_field(field: Mapping[str, Any], newline: bytes) -> bytes:
    field_sha = _json_sha256(field)
    text = yaml.safe_dump(
        {"source_properties": dict(field)},
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=10_000,
    )
    dumped = text.encode("utf-8").replace(b"\n", newline)
    return (
        b"# wom-kit:notion-source-properties:start "
        + field_sha.encode("ascii")
        + newline
        + dumped
        + b"# wom-kit:notion-source-properties:end"
        + newline
    )


def _insert_managed_field(raw: bytes, field: Mapping[str, Any]) -> bytes:
    newline, frontmatter, closing, body = _frontmatter_parts(raw)
    if b"wom-kit:notion-source-properties:" in frontmatter:
        raise ValueError("managed marker already present")
    managed = _dump_managed_field(field, newline)
    return b"---" + newline + frontmatter + managed + closing + body


@dataclass(frozen=True, repr=False)
class _BackfillWrite:
    target_ref: str
    target_identity_sha256: str
    normalized_source_page_id: str
    post_value: bytes
    source_mirror_record_sha256: str


def _target_identity_sha256(
    archive_id: str,
    target_ref: str,
    frontmatter: Mapping[str, Any],
) -> str:
    zettel_id = frontmatter.get("id")
    if type(zettel_id) is not str or not zettel_id:
        raise ValueError("canonical identity")
    return _json_sha256(
        {
            "schema_version": "wom-kit/notion-property-target-identity/v0.1",
            "archive_id": archive_id,
            "zettel_id": zettel_id,
            "target_ref": target_ref,
        }
    )


@dataclass(frozen=True, repr=False)
class _NotionPropertyBackfillPlan:
    archive_root: Path
    archive_id: str
    mirror_path: Path
    mirror_source_kind: str
    mirror_sha256: str
    plan_sha256: str
    target_binding_sha256: str
    manifest: ExactOperationManifest | None
    audit_basis_sha256: str
    source_inventory_sha256: str
    canonical_projection_sha256: str
    mirror_page_count: int
    canonical_file_count: int
    invalid_canonical_count: int
    excluded_non_candidate_malformed: tuple[tuple[str, str], ...]
    source_property_count: int
    populated_property_count: int
    indeterminate_property_count: int
    opaque_source_page_count: int
    opaque_property_count: int
    source_format_page_counts: dict[str, int]
    legacy_record_map_root_page_counts: dict[str, int]
    normalized_source_id_page_counts: dict[str, int]
    populated_page_counts_by_property_type: dict[str, int]
    populated_property_counts_by_type: dict[str, int]
    historical_named_head_page_counts_by_property_type: dict[str, int]
    historical_named_full_page_counts_by_property_type: dict[str, int]
    historical_probe_reason_counts_by_property_type: dict[str, dict[str, int]]
    historical_probe_reason_counts_by_source_format: dict[
        str, dict[str, dict[str, int]]
    ]
    category_populated_property_counts_by_type: dict[str, dict[str, int]]
    unexplained_missing_populated_property_count: int
    unexplained_missing_populated_property_type_count: int
    acceptance_document_sha256: str | None
    acceptance_verified: bool
    acceptance_mismatch_codes: tuple[str, ...]
    category_counts: dict[str, int]
    category_property_counts: dict[str, int]
    category_populated_property_counts: dict[str, int]
    category_opaque_property_counts: dict[str, int]
    category_source_set_sha256: dict[str, str]
    classification_binding_sha256: str
    unresolved_source_set_sha256: str
    unresolved_reason_set_sha256: str
    unmapped_populated_page_count: int
    unmapped_populated_property_count: int
    unmapped_opaque_property_count: int
    review_reason_counts: dict[str, int]
    warning_reason_counts: dict[str, int]
    zero_silent_omission: bool
    managed_equal_effect_count: int
    writes: tuple[_BackfillWrite, ...]
    _acceptance: dict[str, Any] | None

    @property
    def approveable(self) -> bool:
        return (
            self.category_counts["mapped"] > 0
            and self.zero_silent_omission
            and self.acceptance_verified
        )

    @property
    def resumable(self) -> bool:
        return (
            bool(self.writes)
            and self.zero_silent_omission
            and self.acceptance_verified
        )

    def public_document(self) -> dict[str, Any]:
        warning_codes: list[str] = []
        if self.category_counts["review"]:
            warning_codes.append("review_pages_present")
        if self.category_counts["unmapped"]:
            warning_codes.append("unmapped_pages_present")
        if self.opaque_property_count:
            warning_codes.append("opaque_record_map_properties_present")
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "ok": self.approveable,
            "reason_code": (
                "notion_property_backfill_ready"
                if self.approveable
                else "notion_property_backfill_no_writes"
            ),
            "plan_sha256": self.plan_sha256,
            "target_binding_sha256": self.target_binding_sha256,
            "source_binding_sha256": (
                self.manifest.source_set_sha256
                if self.manifest is not None
                else _json_sha256([])
            ),
            "effect_binding_sha256": (
                self.manifest.effect_set_sha256
                if self.manifest is not None
                else _json_sha256([])
            ),
            "mirror_sha256": self.mirror_sha256,
            "acceptance_candidate": {
                "schema_version": ACCEPTANCE_SCHEMA_VERSION,
                "mirror_snapshot_sha256": self.mirror_sha256,
                "mirror_page_count": self.mirror_page_count,
                "source_property_count": self.source_property_count,
                "populated_property_count": self.populated_property_count,
                "indeterminate_property_count": self.indeterminate_property_count,
                "opaque_property_count": self.opaque_property_count,
                "source_format_page_counts": dict(
                    self.source_format_page_counts
                ),
                "legacy_record_map_root_page_counts": dict(
                    self.legacy_record_map_root_page_counts
                ),
                "normalized_source_id_page_counts": dict(
                    self.normalized_source_id_page_counts
                ),
                "populated_page_counts_by_property_type": dict(
                    self.populated_page_counts_by_property_type
                ),
            },
            "source_inventory_sha256": self.source_inventory_sha256,
            "canonical_projection_sha256": (
                self.canonical_projection_sha256
            ),
            "mirror_source_kind": self.mirror_source_kind,
            "mirror_page_count": self.mirror_page_count,
            "canonical_file_count": self.canonical_file_count,
            "invalid_canonical_count": self.invalid_canonical_count,
            "excluded_non_candidate_malformed_count": len(
                self.excluded_non_candidate_malformed
            ),
            "excluded_non_candidate_malformed": [
                {"opaque_ref_sha256": opaque_ref, "reason_code": reason}
                for opaque_ref, reason in self.excluded_non_candidate_malformed
            ],
            "source_property_count": self.source_property_count,
            "populated_property_count": self.populated_property_count,
            "indeterminate_property_count": self.indeterminate_property_count,
            "opaque_source_page_count": self.opaque_source_page_count,
            "opaque_property_count": self.opaque_property_count,
            "source_format_page_counts": dict(self.source_format_page_counts),
            "legacy_record_map_root_page_counts": dict(
                self.legacy_record_map_root_page_counts
            ),
            "normalized_source_id_page_counts": dict(
                self.normalized_source_id_page_counts
            ),
            "populated_page_counts_by_property_type": dict(
                self.populated_page_counts_by_property_type
            ),
            "populated_property_counts_by_type": dict(
                self.populated_property_counts_by_type
            ),
            "historical_named_head_page_counts_by_property_type": dict(
                self.historical_named_head_page_counts_by_property_type
            ),
            "historical_named_full_page_counts_by_property_type": dict(
                self.historical_named_full_page_counts_by_property_type
            ),
            "historical_probe_reason_counts_by_property_type": {
                property_type: dict(counts)
                for property_type, counts in (
                    self.historical_probe_reason_counts_by_property_type.items()
                )
            },
            "historical_probe_reason_counts_by_source_format": {
                source_format: {
                    property_type: dict(counts)
                    for property_type, counts in by_type.items()
                }
                for source_format, by_type in (
                    self.historical_probe_reason_counts_by_source_format.items()
                )
            },
            "category_populated_property_counts_by_type": {
                category: dict(counts)
                for category, counts in (
                    self.category_populated_property_counts_by_type.items()
                )
            },
            "unexplained_missing_populated_property_count": (
                self.unexplained_missing_populated_property_count
            ),
            "unexplained_missing_populated_property_type_count": (
                self.unexplained_missing_populated_property_type_count
            ),
            "acceptance_verified": self.acceptance_verified,
            "acceptance_document_sha256": (
                self.acceptance_document_sha256
            ),
            "acceptance_mismatch_codes": list(self.acceptance_mismatch_codes),
            "category_counts": dict(self.category_counts),
            "category_property_counts": dict(self.category_property_counts),
            "category_populated_property_counts": dict(
                self.category_populated_property_counts
            ),
            "category_opaque_property_counts": dict(
                self.category_opaque_property_counts
            ),
            "category_source_set_sha256": dict(
                self.category_source_set_sha256
            ),
            "classification_binding_sha256": (
                self.classification_binding_sha256
            ),
            "unresolved_source_set_sha256": (
                self.unresolved_source_set_sha256
            ),
            "unresolved_reason_set_sha256": (
                self.unresolved_reason_set_sha256
            ),
            "unmapped_reason_counts": {
                "unmapped_no_canonical_target": self.category_counts["unmapped"]
            },
            "unmapped_populated_page_count": (
                self.unmapped_populated_page_count
            ),
            "unmapped_populated_property_count": (
                self.unmapped_populated_property_count
            ),
            "unmapped_opaque_property_count": (
                self.unmapped_opaque_property_count
            ),
            "unresolved_source_evidence_not_modified": True,
            "unresolved_source_lifecycle_guaranteed": False,
            "unmapped_treated_as_drop": False,
            "review_reason_counts": dict(self.review_reason_counts),
            "warning_reason_counts": dict(self.warning_reason_counts),
            "planned_write_count": self.category_counts["mapped"],
            "manifest_effect_count": len(self.writes),
            "managed_equal_effect_count": self.managed_equal_effect_count,
            "zero_silent_omission": self.zero_silent_omission,
            "requires_exact_human_approval": True,
            "warning_codes": warning_codes,
            "private_values_echoed": False,
            "paths_echoed": False,
            "source_page_ids_echoed": False,
            "property_values_echoed": False,
            "provider_api_called": False,
            "writes_performed": False,
        }


def _acceptance_result(
    acceptance: Mapping[str, Any] | None,
    *,
    mirror_snapshot_sha256: str,
    mirror_page_count: int,
    source_property_count: int,
    populated_property_count: int,
    indeterminate_property_count: int,
    opaque_property_count: int,
    source_format_page_counts: Mapping[str, int],
    legacy_record_map_root_page_counts: Mapping[str, int],
    normalized_source_id_page_counts: Mapping[str, int],
    populated_page_counts_by_property_type: Mapping[str, int],
) -> tuple[bool, tuple[str, ...], str, dict[str, Any] | None]:
    """Validate an explicit, caller-owned source-completeness gate.

    The application run must bind the expected inventory independently of the
    mirror being read.  This prevents a valid but partial 3,605-page export
    from being approved as the complete 11,585-page recovery source.
    """

    if acceptance is None:
        return False, ("acceptance_profile_required",), _json_sha256({}), None
    try:
        document = _json_tree(dict(acceptance))
        expected_pages = document.get("mirror_page_count")
        expected_snapshot = document.get("mirror_snapshot_sha256")
        expected_source_properties = document.get("source_property_count")
        expected_populated = document.get("populated_property_count")
        expected_indeterminate = document.get("indeterminate_property_count")
        expected_opaque = document.get("opaque_property_count")
        expected_types = document.get(
            "populated_page_counts_by_property_type", {}
        )
        expected_formats = document.get("source_format_page_counts", {})
        expected_legacy_roots = document.get(
            "legacy_record_map_root_page_counts"
        )
        expected_source_ids = document.get("normalized_source_id_page_counts")
        if (
            document.get("schema_version") != ACCEPTANCE_SCHEMA_VERSION
            or set(document) - {
                "schema_version",
                "mirror_snapshot_sha256",
                "mirror_page_count",
                "source_property_count",
                "populated_property_count",
                "indeterminate_property_count",
                "opaque_property_count",
                "source_format_page_counts",
                "legacy_record_map_root_page_counts",
                "normalized_source_id_page_counts",
                "populated_page_counts_by_property_type",
            }
            or type(expected_pages) is not int
            or expected_pages <= 0
            or type(expected_snapshot) is not str
            or _SHA256_RE.fullmatch(expected_snapshot) is None
            or type(expected_source_properties) is not int
            or expected_source_properties < 0
            or type(expected_populated) is not int
            or expected_populated < 0
            or type(expected_indeterminate) is not int
            or expected_indeterminate < 0
            or type(expected_opaque) is not int
            or expected_opaque < 0
            or type(expected_types) is not dict
            or type(expected_formats) is not dict
            or not expected_formats
            or not set(expected_formats).issubset(
                {"notion_api_page", "legacy_record_map"}
            )
            or type(expected_legacy_roots) is not dict
            or set(expected_legacy_roots) != {
                "properties_present",
                "properties_absent",
            }
            or type(expected_source_ids) is not dict
            or set(expected_source_ids) != {"unique", "duplicate", "invalid"}
            or any(
                type(name) is not str
                or not name
                or type(count) is not int
                or count < 0
                for name, count in expected_types.items()
            )
            or any(
                type(name) is not str
                or not name
                or type(count) is not int
                or count < 0
                for name, count in expected_formats.items()
            )
            or any(
                type(count) is not int or count < 0
                for count in expected_legacy_roots.values()
            )
            or any(
                type(count) is not int or count < 0
                for count in expected_source_ids.values()
            )
            or (
                expected_formats
                and sum(expected_formats.values()) != expected_pages
            )
            or sum(expected_legacy_roots.values())
            != expected_formats.get("legacy_record_map", 0)
            or sum(expected_source_ids.values()) != expected_pages
        ):
            raise ValueError
    except (TypeError, ValueError):
        raise _fail("notion_property_backfill_plan_invalid") from None
    mismatch: list[str] = []
    if expected_snapshot != mirror_snapshot_sha256:
        mismatch.append("mirror_snapshot_mismatch")
    if expected_pages != mirror_page_count:
        mismatch.append("mirror_page_count_mismatch")
    if expected_source_properties != source_property_count:
        mismatch.append("source_property_count_mismatch")
    if expected_populated != populated_property_count:
        mismatch.append("populated_property_count_mismatch")
    if expected_indeterminate != indeterminate_property_count:
        mismatch.append("indeterminate_property_count_mismatch")
    if expected_opaque != opaque_property_count:
        mismatch.append("opaque_property_count_mismatch")
    if expected_formats and dict(sorted(expected_formats.items())) != dict(
        sorted(source_format_page_counts.items())
    ):
        mismatch.append("source_format_page_count_mismatch")
    if dict(sorted(expected_legacy_roots.items())) != dict(
        sorted(legacy_record_map_root_page_counts.items())
    ):
        mismatch.append("legacy_record_map_root_page_count_mismatch")
    if dict(sorted(expected_source_ids.items())) != dict(
        sorted(normalized_source_id_page_counts.items())
    ):
        mismatch.append("normalized_source_id_page_count_mismatch")
    for property_type, expected_count in sorted(expected_types.items()):
        if populated_page_counts_by_property_type.get(property_type, 0) != expected_count:
            mismatch.append("populated_property_type_count_mismatch")
            break
    return not mismatch, tuple(mismatch), _json_sha256(document), document


def _plan_notion_property_backfill_core(
    archive_root: Path | str,
    mirror_jsonl: Path | str,
    *,
    acceptance: Mapping[str, Any] | None = None,
    progress: Callable[[Mapping[str, Any]], None] | None = None,
) -> _NotionPropertyBackfillPlan:
    progress_publisher = _PlanningProgressPublisher(progress)
    progress_publisher.publish(
        "starting",
        0,
        1,
        unit="plan",
        force=True,
    )
    root, archive_id = _safe_root(archive_root)
    (
        canonical,
        canonical_count,
        invalid_canonical_count,
        excluded_non_candidate_malformed,
    ) = _scan_canonical(root, archive_id, progress=progress_publisher)
    canonical_projection_sha256 = _canonical_projection_sha256(
        canonical,
        archive_id=archive_id,
        invalid_count=invalid_canonical_count,
    )
    # Scan the many small canonical files before streaming the 925MB-class
    # mirror.  This preserves the same O(files + zets) algorithm while avoiding
    # the large sequential read evicting the canonical working set immediately
    # before thousands of small-file reads on Windows.
    mirror_path, mirror_source_kind, mirror_sha, pages = _read_mirror(
        mirror_jsonl,
        progress=progress_publisher,
    )
    mirror_id_counts: dict[str, int] = {}
    for page in pages:
        if page.normalized_source_page_id is not None:
            mirror_id_counts[page.normalized_source_page_id] = (
                mirror_id_counts.get(page.normalized_source_page_id, 0) + 1
            )
    duplicate_mirror_ids = {
        source_id for source_id, count in mirror_id_counts.items() if count > 1
    }
    normalized_source_id_page_counts = {
        "unique": sum(count for count in mirror_id_counts.values() if count == 1),
        "duplicate": sum(
            count for count in mirror_id_counts.values() if count > 1
        ),
        "invalid": sum(
            page.normalized_source_page_id is None for page in pages
        ),
    }
    category_counts = {name: 0 for name in ("mapped", "already_equal", "unmapped", "review")}
    category_property_counts = dict(category_counts)
    category_populated_counts = dict(category_counts)
    category_opaque_counts = dict(category_counts)
    category_populated_counts_by_type: dict[str, dict[str, int]] = {
        name: {} for name in category_counts
    }
    category_source_records: dict[str, list[dict[str, Any]]] = {
        name: [] for name in category_counts
    }
    operation_category_counts = dict(category_counts)
    operation_category_property_counts = dict(category_counts)
    operation_category_populated_counts = dict(category_counts)
    operation_category_opaque_counts = dict(category_counts)
    operation_category_source_records: dict[str, list[dict[str, Any]]] = {
        name: [] for name in category_counts
    }
    review_reason_counts: dict[str, int] = {}
    warning_reason_counts: dict[str, int] = {}
    writes: list[_BackfillWrite] = []
    managed_equal_effect_count = 0

    progress_publisher.publish(
        "join_and_classify",
        0,
        len(pages),
        unit="pages",
        force=True,
    )
    for index, page in enumerate(pages, start=1):
        managed_equal_current = False
        reasons = set(page.review_codes)
        source_id = page.normalized_source_page_id
        targets = canonical.get(source_id, []) if source_id is not None else []
        if invalid_canonical_count:
            reasons.add("canonical_scan_incomplete")
        if source_id in duplicate_mirror_ids:
            reasons.add("duplicate_mirror_page_id")
        if len(targets) > 1:
            reasons.add("duplicate_canonical_page_id")

        category: str
        if reasons:
            category = "review"
        elif not targets:
            category = "unmapped"
        else:
            target = targets[0]
            expected = page.source_properties()
            if "source_properties" not in target.frontmatter:
                try:
                    candidate = _insert_managed_field(target.raw, expected)
                except ValueError:
                    category = "review"
                    reasons.add("managed_field_boundary_invalid")
                else:
                    if len(candidate) > MAX_CANONICAL_FILE_BYTES:
                        category = "review"
                        reasons.add("canonical_size_limit_exceeded")
                    else:
                        category = "mapped"
                        writes.append(
                            _BackfillWrite(
                                target_ref=target.target_ref,
                                target_identity_sha256=_target_identity_sha256(
                                    archive_id,
                                    target.target_ref,
                                    target.frontmatter,
                                ),
                                normalized_source_page_id=(
                                    target.normalized_source_page_id
                                ),
                                post_value=_canonical_bytes(expected),
                                source_mirror_record_sha256=page.record_sha256,
                            )
                        )
            elif target.frontmatter["source_properties"] == expected:
                state, field_sha256, _candidate = _managed_field_state(target.raw)
                if state == "managed" and field_sha256 == _json_sha256(expected):
                    category = "already_equal"
                    managed_equal_current = True
                    managed_equal_effect_count += 1
                    writes.append(
                        _BackfillWrite(
                            target_ref=target.target_ref,
                            target_identity_sha256=_target_identity_sha256(
                                archive_id,
                                target.target_ref,
                                target.frontmatter,
                            ),
                            normalized_source_page_id=(
                                target.normalized_source_page_id
                            ),
                            post_value=_canonical_bytes(expected),
                            source_mirror_record_sha256=page.record_sha256,
                        )
                    )
                elif b"wom-kit:notion-source-properties:" in target.raw:
                    category = "review"
                    reasons.add("managed_field_boundary_invalid")
                else:
                    category = "already_equal"
            else:
                category = "review"
                reasons.add("existing_source_properties_conflict")

        category_counts[category] += 1
        category_property_counts[category] += page.property_count
        category_populated_counts[category] += page.populated_property_count
        category_opaque_counts[category] += len(page.opaque_properties)
        for item in page.properties:
            if item.population_state == "populated":
                type_counts = category_populated_counts_by_type[category]
                type_counts[item.property_type] = (
                    type_counts.get(item.property_type, 0) + 1
                )
        if category == "review":
            for reason in sorted(reasons):
                review_reason_counts[reason] = review_reason_counts.get(reason, 0) + 1
        if category == "unmapped":
            classification_reasons = ("unmapped_no_canonical_target",)
        elif category == "review":
            classification_reasons = tuple(sorted(reasons))
        elif category == "already_equal":
            classification_reasons = ("source_properties_already_equal",)
        else:
            classification_reasons = ("exact_source_to_canonical_target",)
        category_source_records[category].append(
            {
                "source_ordinal": index - 1,
                "source_mirror_record_sha256": page.record_sha256,
                "reason_codes": classification_reasons,
                "property_count": page.property_count,
                "populated_property_count": page.populated_property_count,
                "opaque_property_count": len(page.opaque_properties),
            }
        )
        # A field already written by this exact adapter remains one originally
        # approved ``mapped`` effect.  Normalizing only that owned state makes
        # the manifest reconstruct byte-for-byte after a write-before-receipt
        # crash while plain pre-existing equal data stays ``already_equal``.
        operation_category = "mapped" if managed_equal_current else category
        operation_category_counts[operation_category] += 1
        operation_category_property_counts[operation_category] += (
            page.property_count
        )
        operation_category_populated_counts[operation_category] += (
            page.populated_property_count
        )
        operation_category_opaque_counts[operation_category] += len(
            page.opaque_properties
        )
        if operation_category == "unmapped":
            operation_reasons = ("unmapped_no_canonical_target",)
        elif operation_category == "review":
            operation_reasons = tuple(sorted(reasons))
        elif operation_category == "already_equal":
            operation_reasons = ("source_properties_already_equal",)
        else:
            operation_reasons = ("exact_source_to_canonical_target",)
        operation_category_source_records[operation_category].append(
            {
                "source_ordinal": index - 1,
                "source_mirror_record_sha256": page.record_sha256,
                "reason_codes": operation_reasons,
                "property_count": page.property_count,
                "populated_property_count": page.populated_property_count,
                "opaque_property_count": len(page.opaque_properties),
            }
        )
        for warning in page.warning_codes:
            warning_reason_counts[warning] = warning_reason_counts.get(warning, 0) + 1
        progress_publisher.publish(
            "join_and_classify",
            index,
            len(pages),
            unit="pages",
        )

    writes.sort(key=lambda item: item.target_ref)
    finalize_total = max(1, len(writes))
    progress_publisher.publish(
        "finalize_plan",
        0,
        finalize_total,
        unit="effects",
        force=True,
    )
    source_property_count = sum(page.property_count for page in pages)
    populated_property_count = sum(page.populated_property_count for page in pages)
    indeterminate_property_count = sum(
        page.indeterminate_property_count for page in pages
    )
    opaque_source_page_count = sum(bool(page.opaque_properties) for page in pages)
    opaque_property_count = sum(len(page.opaque_properties) for page in pages)
    source_format_page_counts: dict[str, int] = {}
    historical_head_counts = {
        property_type: 0 for property_type in sorted(_HISTORICAL_PROBE_SPECS)
    }
    historical_full_counts = dict(historical_head_counts)
    historical_reason_counts: dict[str, dict[str, int]] = {}
    historical_reason_counts_by_source_format: dict[
        str, dict[str, dict[str, int]]
    ] = {}
    for page in pages:
        source_format_page_counts[page.source_format] = (
            source_format_page_counts.get(page.source_format, 0) + 1
        )
        for property_type in page.historical_head_match_types:
            historical_head_counts[property_type] += 1
        for property_type in page.historical_full_match_types:
            historical_full_counts[property_type] += 1
        for property_type, reason in page.historical_probe_reasons:
            by_reason = historical_reason_counts.setdefault(property_type, {})
            by_reason[reason] = by_reason.get(reason, 0) + 1
            by_format = historical_reason_counts_by_source_format.setdefault(
                page.source_format, {}
            ).setdefault(property_type, {})
            by_format[reason] = by_format.get(reason, 0) + 1
    source_format_page_counts = dict(sorted(source_format_page_counts.items()))
    legacy_record_map_root_page_counts = {
        "properties_present": sum(
            page.source_format == "legacy_record_map"
            and "record_map_root_properties_absent" not in page.review_codes
            for page in pages
        ),
        "properties_absent": sum(
            page.source_format == "legacy_record_map"
            and "record_map_root_properties_absent" in page.review_codes
            for page in pages
        ),
    }
    historical_reason_counts = {
        property_type: dict(sorted(counts.items()))
        for property_type, counts in sorted(historical_reason_counts.items())
    }
    historical_reason_counts_by_source_format = {
        source_format: {
            property_type: dict(sorted(counts.items()))
            for property_type, counts in sorted(by_type.items())
        }
        for source_format, by_type in sorted(
            historical_reason_counts_by_source_format.items()
        )
    }
    populated_page_counts_by_property_type: dict[str, int] = {}
    populated_property_counts_by_type: dict[str, int] = {}
    for page in pages:
        populated_types = {
            item.property_type
            for item in page.properties
            if item.population_state == "populated"
        }
        for property_type in populated_types:
            populated_page_counts_by_property_type[property_type] = (
                populated_page_counts_by_property_type.get(property_type, 0) + 1
            )
        for item in page.properties:
            if item.population_state == "populated":
                populated_property_counts_by_type[item.property_type] = (
                    populated_property_counts_by_type.get(item.property_type, 0)
                    + 1
                )
    populated_page_counts_by_property_type = dict(
        sorted(populated_page_counts_by_property_type.items())
    )
    populated_property_counts_by_type = dict(
        sorted(populated_property_counts_by_type.items())
    )
    category_populated_counts_by_type = {
        category: dict(sorted(counts.items()))
        for category, counts in category_populated_counts_by_type.items()
    }
    category_source_set_sha256 = {
        category: _json_sha256(records)
        for category, records in sorted(category_source_records.items())
    }
    operation_category_source_set_sha256 = {
        category: _json_sha256(records)
        for category, records in sorted(
            operation_category_source_records.items()
        )
    }
    unresolved_records = sorted(
        category_source_records["unmapped"]
        + category_source_records["review"],
        key=lambda item: item["source_ordinal"],
    )
    unresolved_source_set_sha256 = _json_sha256(unresolved_records)
    unresolved_reason_set_sha256 = _json_sha256(
        [
            {
                "source_ordinal": item["source_ordinal"],
                "source_mirror_record_sha256": item[
                    "source_mirror_record_sha256"
                ],
                "reason_codes": item["reason_codes"],
            }
            for item in unresolved_records
        ]
    )
    operation_unresolved_records = sorted(
        operation_category_source_records["unmapped"]
        + operation_category_source_records["review"],
        key=lambda item: item["source_ordinal"],
    )
    operation_unresolved_source_set_sha256 = _json_sha256(
        operation_unresolved_records
    )
    operation_unresolved_reason_set_sha256 = _json_sha256(
        [
            {
                "source_ordinal": item["source_ordinal"],
                "source_mirror_record_sha256": item[
                    "source_mirror_record_sha256"
                ],
                "reason_codes": item["reason_codes"],
            }
            for item in operation_unresolved_records
        ]
    )
    unmapped_populated_page_count = sum(
        item["populated_property_count"] > 0
        for item in category_source_records["unmapped"]
    )
    unmapped_populated_property_count = category_populated_counts["unmapped"]
    unmapped_opaque_property_count = category_opaque_counts["unmapped"]
    classification_binding_sha256 = _json_sha256(
        {
            "schema_version": (
                "wom-kit/notion-property-classification-binding/v0.1"
            ),
            "category_counts": category_counts,
            "category_property_counts": category_property_counts,
            "category_populated_property_counts": category_populated_counts,
            "category_opaque_property_counts": category_opaque_counts,
            "category_source_set_sha256": category_source_set_sha256,
            "unresolved_source_set_sha256": unresolved_source_set_sha256,
            "unresolved_reason_set_sha256": unresolved_reason_set_sha256,
            "unmapped_populated_page_count": unmapped_populated_page_count,
            "unmapped_populated_property_count": (
                unmapped_populated_property_count
            ),
            "unmapped_opaque_property_count": unmapped_opaque_property_count,
        }
    )
    operation_classification_binding_sha256 = _json_sha256(
        {
            "schema_version": (
                "wom-kit/notion-property-operation-classification-binding/v0.1"
            ),
            "category_counts": operation_category_counts,
            "category_property_counts": operation_category_property_counts,
            "category_populated_property_counts": (
                operation_category_populated_counts
            ),
            "category_opaque_property_counts": operation_category_opaque_counts,
            "category_source_set_sha256": (
                operation_category_source_set_sha256
            ),
            "unresolved_source_set_sha256": (
                operation_unresolved_source_set_sha256
            ),
            "unresolved_reason_set_sha256": (
                operation_unresolved_reason_set_sha256
            ),
            "unmapped_populated_page_count": unmapped_populated_page_count,
            "unmapped_populated_property_count": (
                unmapped_populated_property_count
            ),
            "unmapped_opaque_property_count": unmapped_opaque_property_count,
        }
    )
    unexplained_by_type = {
        property_type: source_count
        - sum(
            counts.get(property_type, 0)
            for counts in category_populated_counts_by_type.values()
        )
        for property_type, source_count in populated_property_counts_by_type.items()
    }
    unexplained_missing_populated_property_count = sum(
        abs(count) for count in unexplained_by_type.values()
    )
    unexplained_missing_populated_property_type_count = sum(
        count != 0 for count in unexplained_by_type.values()
    )
    (
        acceptance_verified,
        acceptance_mismatch_codes,
        acceptance_sha256,
        normalized_acceptance,
    ) = (
        _acceptance_result(
            acceptance,
            mirror_snapshot_sha256=mirror_sha,
            mirror_page_count=len(pages),
            source_property_count=source_property_count,
            populated_property_count=populated_property_count,
            indeterminate_property_count=indeterminate_property_count,
            opaque_property_count=opaque_property_count,
            source_format_page_counts=source_format_page_counts,
            legacy_record_map_root_page_counts=(
                legacy_record_map_root_page_counts
            ),
            normalized_source_id_page_counts=normalized_source_id_page_counts,
            populated_page_counts_by_property_type=(
                populated_page_counts_by_property_type
            ),
        )
    )
    zero_silent_omission = (
        sum(category_counts.values()) == len(pages)
        and sum(category_property_counts.values()) == source_property_count
        and sum(category_populated_counts.values()) == populated_property_count
        and sum(category_opaque_counts.values()) == opaque_property_count
        and sum(source_format_page_counts.values()) == len(pages)
        and sum(legacy_record_map_root_page_counts.values())
        == source_format_page_counts.get("legacy_record_map", 0)
        and sum(normalized_source_id_page_counts.values()) == len(pages)
        and unexplained_missing_populated_property_count == 0
        and unexplained_missing_populated_property_type_count == 0
        and all(
            page.review_codes
            or page.property_count
            == len(page.properties) + len(page.opaque_properties)
            for page in pages
        )
    )
    source_inventory_basis = {
        "schema_version": "wom-kit/notion-property-source-inventory/v0.1",
        "archive_identity_sha256": exact_human_approval_archive_identity_sha256(
            archive_id
        ),
        "mirror_sha256": mirror_sha,
        "mirror_source_kind": mirror_source_kind,
        "canonical_projection_sha256": canonical_projection_sha256,
        "acceptance_sha256": acceptance_sha256,
        "acceptance_verified": acceptance_verified,
        "acceptance_mismatch_codes": acceptance_mismatch_codes,
        "mirror_page_count": len(pages),
        "source_property_count": source_property_count,
        "populated_property_count": populated_property_count,
        "indeterminate_property_count": indeterminate_property_count,
        "opaque_source_page_count": opaque_source_page_count,
        "opaque_property_count": opaque_property_count,
        "source_format_page_counts": source_format_page_counts,
        "legacy_record_map_root_page_counts": (
            legacy_record_map_root_page_counts
        ),
        "normalized_source_id_page_counts": normalized_source_id_page_counts,
        "populated_page_counts_by_property_type": (
            populated_page_counts_by_property_type
        ),
        "populated_property_counts_by_type": populated_property_counts_by_type,
        "historical_named_head_page_counts_by_property_type": (
            historical_head_counts
        ),
        "historical_named_full_page_counts_by_property_type": (
            historical_full_counts
        ),
        "historical_probe_reason_counts_by_property_type": (
            historical_reason_counts
        ),
        "historical_probe_reason_counts_by_source_format": (
            historical_reason_counts_by_source_format
        ),
        "unexplained_missing_populated_property_count": (
            unexplained_missing_populated_property_count
        ),
        "unexplained_missing_populated_property_type_count": (
            unexplained_missing_populated_property_type_count
        ),
        "classification_binding_sha256": (
            operation_classification_binding_sha256
        ),
        "category_counts": operation_category_counts,
        "category_property_counts": operation_category_property_counts,
        "category_populated_property_counts": (
            operation_category_populated_counts
        ),
        "category_opaque_property_counts": operation_category_opaque_counts,
        "category_source_set_sha256": operation_category_source_set_sha256,
        "unresolved_source_set_sha256": (
            operation_unresolved_source_set_sha256
        ),
        "unresolved_reason_set_sha256": (
            operation_unresolved_reason_set_sha256
        ),
        "unmapped_populated_page_count": unmapped_populated_page_count,
        "unmapped_populated_property_count": unmapped_populated_property_count,
        "unmapped_opaque_property_count": unmapped_opaque_property_count,
    }
    source_inventory_sha = _json_sha256(source_inventory_basis)
    audit_basis = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "archive_identity_sha256": exact_human_approval_archive_identity_sha256(
            archive_id
        ),
        "mirror_sha256": mirror_sha,
        "source_inventory_sha256": source_inventory_sha,
        "mirror_source_kind": mirror_source_kind,
        "canonical_projection_sha256": canonical_projection_sha256,
        "acceptance_sha256": acceptance_sha256,
        "acceptance_verified": acceptance_verified,
        "acceptance_mismatch_codes": acceptance_mismatch_codes,
        "mirror_page_count": len(pages),
        "canonical_file_count": canonical_count,
        "invalid_canonical_count": invalid_canonical_count,
        "excluded_non_candidate_malformed": excluded_non_candidate_malformed,
        "source_property_count": source_property_count,
        "populated_property_count": populated_property_count,
        "indeterminate_property_count": indeterminate_property_count,
        "opaque_source_page_count": opaque_source_page_count,
        "opaque_property_count": opaque_property_count,
        "source_format_page_counts": source_format_page_counts,
        "legacy_record_map_root_page_counts": (
            legacy_record_map_root_page_counts
        ),
        "normalized_source_id_page_counts": normalized_source_id_page_counts,
        "populated_page_counts_by_property_type": (
            populated_page_counts_by_property_type
        ),
        "populated_property_counts_by_type": populated_property_counts_by_type,
        "historical_named_head_page_counts_by_property_type": (
            historical_head_counts
        ),
        "historical_named_full_page_counts_by_property_type": (
            historical_full_counts
        ),
        "historical_probe_reason_counts_by_property_type": (
            historical_reason_counts
        ),
        "historical_probe_reason_counts_by_source_format": (
            historical_reason_counts_by_source_format
        ),
        "category_populated_property_counts_by_type": (
            category_populated_counts_by_type
        ),
        "unexplained_missing_populated_property_count": (
            unexplained_missing_populated_property_count
        ),
        "unexplained_missing_populated_property_type_count": (
            unexplained_missing_populated_property_type_count
        ),
        "category_counts": category_counts,
        "category_property_counts": category_property_counts,
        "category_populated_property_counts": category_populated_counts,
        "category_opaque_property_counts": category_opaque_counts,
        "category_source_set_sha256": category_source_set_sha256,
        "classification_binding_sha256": classification_binding_sha256,
        "unresolved_source_set_sha256": unresolved_source_set_sha256,
        "unresolved_reason_set_sha256": unresolved_reason_set_sha256,
        "unmapped_populated_page_count": unmapped_populated_page_count,
        "unmapped_populated_property_count": unmapped_populated_property_count,
        "unmapped_opaque_property_count": unmapped_opaque_property_count,
        "review_reason_counts": dict(sorted(review_reason_counts.items())),
        "warning_reason_counts": dict(sorted(warning_reason_counts.items())),
        "zero_silent_omission": zero_silent_omission,
    }
    audit_basis_sha = _json_sha256(audit_basis)
    operation_evidence = {
        "schema": "wom-kit/notion-property-recovery/v1",
        "counts": {
            "source_page_count": len(pages),
            "canonical_file_count": canonical_count,
            "excluded_non_candidate_malformed_count": len(
                excluded_non_candidate_malformed
            ),
            "mapped_page_count": operation_category_counts["mapped"],
            "mapped_property_count": operation_category_property_counts[
                "mapped"
            ],
            "mapped_populated_property_count": (
                operation_category_populated_counts["mapped"]
            ),
            "already_equal_page_count": operation_category_counts[
                "already_equal"
            ],
            "unmapped_page_count": operation_category_counts["unmapped"],
            "review_page_count": operation_category_counts["review"],
            "effect_count": len(writes),
            "source_property_count": source_property_count,
            "populated_property_count": populated_property_count,
            "opaque_property_count": opaque_property_count,
            "unmapped_populated_page_count": unmapped_populated_page_count,
            "unmapped_populated_property_count": (
                unmapped_populated_property_count
            ),
            "unmapped_opaque_property_count": (
                unmapped_opaque_property_count
            ),
            "unexplained_missing_populated_property_count": (
                unexplained_missing_populated_property_count
            ),
            "unexplained_missing_populated_property_type_count": (
                unexplained_missing_populated_property_type_count
            ),
        },
        "digests": {
            "mirror_snapshot_sha256": mirror_sha,
            "source_inventory_sha256": source_inventory_sha,
            "canonical_projection_sha256": canonical_projection_sha256,
            "acceptance_document_sha256": (
                acceptance_sha256
                or _json_sha256(
                    {
                        "schema_version": (
                            "wom-kit/notion-property-acceptance-absent/v0.1"
                        )
                    }
                )
            ),
            "classification_binding_sha256": (
                operation_classification_binding_sha256
            ),
            "mapped_source_set_sha256": (
                operation_category_source_set_sha256["mapped"]
            ),
            "already_equal_source_set_sha256": (
                operation_category_source_set_sha256["already_equal"]
            ),
            "unmapped_source_set_sha256": (
                operation_category_source_set_sha256["unmapped"]
            ),
            "review_source_set_sha256": (
                operation_category_source_set_sha256["review"]
            ),
            "unresolved_source_set_sha256": (
                operation_unresolved_source_set_sha256
            ),
            "unresolved_reason_set_sha256": (
                operation_unresolved_reason_set_sha256
            ),
        },
        "private_values_echoed": False,
    }
    manifest_items: list[ExactOperationItem] = []
    for ordinal, write in enumerate(writes):
        source_binding = _canonical_bytes(
            {
                "schema_version": "wom-kit/notion-property-source-binding/v0.1",
                "mirror_sha256": mirror_sha,
                "source_mirror_record_sha256": (
                    write.source_mirror_record_sha256
                ),
                "source_inventory_sha256": source_inventory_sha,
            }
        )
        item_id = "item:" + hashlib.sha256(
            (write.target_ref + "\x00" + write.source_mirror_record_sha256).encode(
                "utf-8"
            )
        ).hexdigest()
        manifest_items.append(
            ExactOperationItem(
                ordinal=ordinal,
                item_id=item_id,
                target_kind="zettel",
                target_ref=write.target_ref,
                target_identity_sha256=write.target_identity_sha256,
                fields=(
                    ExactFieldEffect(
                        field_ref="source_properties",
                        pre_sha256=hash_field_value(None),
                        post_sha256=hash_field_value(write.post_value),
                        source_sha256=hash_field_value(source_binding),
                    ),
                ),
            )
        )
        progress_publisher.publish(
            "finalize_plan",
            ordinal + 1,
            finalize_total,
            unit="effects",
        )
    if not manifest_items:
        # The common manifest intentionally rejects an empty effect set.  A
        # non-approveable plan still needs deterministic public digests, so a
        # fixed content-free sentinel is used outside the manifest boundary.
        manifest = None
        plan_sha256 = _json_sha256(
            {"audit_basis_sha256": audit_basis_sha, "empty_effect_set": True}
        )
        target_binding_sha256 = _json_sha256([])
    else:
        manifest = ExactOperationManifest.build(
            operation=NOTION_PROPERTY_BACKFILL_OPERATION,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                archive_id
            ),
            items=manifest_items,
            operation_evidence=operation_evidence,
        )
        plan_sha256 = manifest.manifest_sha256
        target_binding_sha256 = manifest.target_set_sha256
    result = _NotionPropertyBackfillPlan(
        archive_root=root,
        archive_id=archive_id,
        mirror_path=mirror_path,
        mirror_source_kind=mirror_source_kind,
        mirror_sha256=mirror_sha,
        plan_sha256=plan_sha256,
        target_binding_sha256=target_binding_sha256,
        manifest=manifest,
        audit_basis_sha256=audit_basis_sha,
        source_inventory_sha256=source_inventory_sha,
        canonical_projection_sha256=canonical_projection_sha256,
        mirror_page_count=len(pages),
        canonical_file_count=canonical_count,
        invalid_canonical_count=invalid_canonical_count,
        excluded_non_candidate_malformed=excluded_non_candidate_malformed,
        source_property_count=source_property_count,
        populated_property_count=populated_property_count,
        indeterminate_property_count=indeterminate_property_count,
        opaque_source_page_count=opaque_source_page_count,
        opaque_property_count=opaque_property_count,
        source_format_page_counts=source_format_page_counts,
        legacy_record_map_root_page_counts=(
            legacy_record_map_root_page_counts
        ),
        normalized_source_id_page_counts=normalized_source_id_page_counts,
        populated_page_counts_by_property_type=(
            populated_page_counts_by_property_type
        ),
        populated_property_counts_by_type=populated_property_counts_by_type,
        historical_named_head_page_counts_by_property_type=(
            historical_head_counts
        ),
        historical_named_full_page_counts_by_property_type=(
            historical_full_counts
        ),
        historical_probe_reason_counts_by_property_type=(
            historical_reason_counts
        ),
        historical_probe_reason_counts_by_source_format=(
            historical_reason_counts_by_source_format
        ),
        category_populated_property_counts_by_type=(
            category_populated_counts_by_type
        ),
        unexplained_missing_populated_property_count=(
            unexplained_missing_populated_property_count
        ),
        unexplained_missing_populated_property_type_count=(
            unexplained_missing_populated_property_type_count
        ),
        acceptance_document_sha256=(
            acceptance_sha256 if normalized_acceptance is not None else None
        ),
        acceptance_verified=acceptance_verified,
        acceptance_mismatch_codes=acceptance_mismatch_codes,
        category_counts=category_counts,
        category_property_counts=category_property_counts,
        category_populated_property_counts=category_populated_counts,
        category_opaque_property_counts=category_opaque_counts,
        category_source_set_sha256=category_source_set_sha256,
        classification_binding_sha256=classification_binding_sha256,
        unresolved_source_set_sha256=unresolved_source_set_sha256,
        unresolved_reason_set_sha256=unresolved_reason_set_sha256,
        unmapped_populated_page_count=unmapped_populated_page_count,
        unmapped_populated_property_count=unmapped_populated_property_count,
        unmapped_opaque_property_count=unmapped_opaque_property_count,
        review_reason_counts=dict(sorted(review_reason_counts.items())),
        warning_reason_counts=dict(sorted(warning_reason_counts.items())),
        zero_silent_omission=zero_silent_omission,
        managed_equal_effect_count=managed_equal_effect_count,
        writes=tuple(writes),
        _acceptance=normalized_acceptance,
    )
    progress_publisher.publish(
        "finalize_plan",
        finalize_total,
        finalize_total,
        unit="effects",
        force=True,
    )
    return result


def plan_notion_property_backfill(
    archive_root: Path | str,
    mirror_jsonl: Path | str,
    *,
    acceptance: Mapping[str, Any] | None = None,
    progress: Callable[[Mapping[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Return a content-free projection of the private recovery plan."""

    return _plan_notion_property_backfill_core(
        archive_root, mirror_jsonl, acceptance=acceptance, progress=progress
    ).public_document()


def _notion_property_backfill_context(
    plan: _NotionPropertyBackfillPlan,
    *,
    reviewer_claim: str,
    mode: str = "apply",
) -> ExactHumanApprovalContext:
    binding = _notion_property_backfill_approval_binding(plan, mode=mode)
    return binding.context(
        archive_id=plan.archive_id,
        reviewer_claim=reviewer_claim,
    )


def _notion_property_operation_manifest(
    plan: _NotionPropertyBackfillPlan,
    *,
    mode: str,
) -> ExactOperationManifest:
    if (
        type(plan) is not _NotionPropertyBackfillPlan
        or plan.manifest is None
        or mode not in {"apply", "revert"}
    ):
        raise _fail("notion_property_backfill_plan_invalid")
    if mode == "apply":
        return plan.manifest
    return ExactOperationManifest.build(
        operation=NOTION_PROPERTY_BACKFILL_REVERT_OPERATION,
        archive_identity_sha256=plan.manifest.archive_identity_sha256,
        items=plan.manifest.items,
        operation_evidence=plan.manifest.operation_evidence,
    )


def _notion_property_backfill_approval_binding(
    plan: _NotionPropertyBackfillPlan,
    *,
    mode: str = "apply",
) -> ExactOperationApprovalBinding:
    if (
        type(plan) is not _NotionPropertyBackfillPlan
        or not plan.resumable
        or plan.manifest is None
    ):
        raise _fail("notion_property_backfill_no_writes")
    warnings: list[str] = []
    if plan.category_counts["review"]:
        warnings.append("review_pages_present")
    if plan.category_counts["unmapped"]:
        warnings.append("unmapped_pages_present")
    if plan.unmapped_populated_property_count:
        warnings.append("unmapped_populated_properties_present")
    if plan.opaque_property_count:
        warnings.append("opaque_record_map_properties_present")
    manifest = _notion_property_operation_manifest(plan, mode=mode)
    operation = (
        ExactHumanApprovalOperation.notion_property_backfill
        if mode == "apply"
        else ExactHumanApprovalOperation.notion_property_backfill_revert
    )
    return exact_operation_manifest_approval_binding(
        manifest,
        operation=operation,
        archive_id=plan.archive_id,
        warnings=tuple(sorted(warnings)),
    )


def _ensure_internal_parents(root: Path, path: Path, *, create: bool) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise _fail("notion_property_backfill_path_unsafe") from None
    current = root
    for part in relative.parts[:-1]:
        if part in {"", ".", ".."}:
            raise _fail("notion_property_backfill_path_unsafe")
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            if not create:
                raise _fail("notion_property_backfill_path_unsafe") from None
            try:
                current.mkdir()
                info = os.lstat(current)
            except (OSError, FileExistsError):
                raise _fail("notion_property_backfill_path_unsafe") from None
        except OSError:
            raise _fail("notion_property_backfill_path_unsafe") from None
        if _is_link_or_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise _fail("notion_property_backfill_path_unsafe")


def _atomic_replace(
    root: Path,
    path: Path,
    *,
    expected_bytes: bytes,
    replacement_bytes: bytes,
) -> None:
    """Commit only if the exact bytes read by the field adapter still exist."""

    _ensure_internal_parents(root, path, create=False)
    transaction_sha256 = _json_sha256(
        {
            "schema_version": "wom-kit/notion-property-field-cas/v0.1",
            "target_ref_sha256": _sha256(
                path.relative_to(root).as_posix().encode("utf-8")
            ),
            "expected_sha256": _sha256(expected_bytes),
            "replacement_sha256": _sha256(replacement_bytes),
        }
    )
    archive_services._replace_regular_file_bytes_compare_and_swap(
        root,
        path,
        expected_bytes=expected_bytes,
        replacement_bytes=replacement_bytes,
        transaction_sha256=transaction_sha256,
        swap_suffix=".notion-properties.swap",
        max_bytes=MAX_CANONICAL_FILE_BYTES,
        error_prefix="notion_property_backfill",
    )


def _safe_target_from_ref(root: Path, target_ref: Any) -> Path:
    if type(target_ref) is not str or not target_ref.startswith("zettels/"):
        raise ValueError("target ref")
    relative = Path(target_ref)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.suffix.lower() != ".md"
    ):
        raise ValueError("target ref")
    candidate = root.joinpath(*relative.parts)
    try:
        candidate.resolve(strict=False).relative_to(root)
    except (OSError, RuntimeError, ValueError):
        raise ValueError("target ref") from None
    return candidate


def _managed_field_state(raw: bytes) -> tuple[str, str | None, bytes | None]:
    """Return state, field digest, and bytes with only the managed block removed."""

    try:
        newline, frontmatter, closing, body = _frontmatter_parts(raw)
        lines = frontmatter.splitlines(keepends=True)
        starts = [
            index
            for index, line in enumerate(lines)
            if _START_MARKER_RE.fullmatch(line)
        ]
        ends = [
            index
            for index, line in enumerate(lines)
            if line in _END_MARKER_LINES
        ]
        complete = _frontmatter(raw)
    except ValueError:
        return "review", None, None
    field = complete.get("source_properties")
    if not starts and not ends and field is None:
        return "absent", None, raw
    if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
        return "review", None, None
    start_index, end_index = starts[0], ends[0]
    match = _START_MARKER_RE.fullmatch(lines[start_index])
    if match is None:
        return "review", None, None
    marker_sha = match.group(1).decode("ascii")
    try:
        managed_mapping = _yaml_json_mapping(
            b"".join(lines[start_index + 1 : end_index])
        )
    except ValueError:
        return "review", None, None
    if set(managed_mapping) != {"source_properties"}:
        return "review", None, None
    managed_field = managed_mapping["source_properties"]
    if field != managed_field or _json_sha256(field) != marker_sha:
        return "review", None, None
    remaining_frontmatter = b"".join(
        lines[:start_index] + lines[end_index + 1 :]
    )
    candidate = b"---" + newline + remaining_frontmatter + closing + body
    return "managed", marker_sha, candidate


def _source_binding_value(
    plan: _NotionPropertyBackfillPlan,
    write: _BackfillWrite,
) -> bytes:
    return _canonical_bytes(
        {
            "schema_version": "wom-kit/notion-property-source-binding/v0.1",
            "mirror_sha256": plan.mirror_sha256,
            "source_mirror_record_sha256": write.source_mirror_record_sha256,
            "source_inventory_sha256": plan.source_inventory_sha256,
        }
    )


class _NotionPropertyPayloads:
    def __init__(self, plan: _NotionPropertyBackfillPlan) -> None:
        if plan.manifest is None or len(plan.manifest.items) != len(plan.writes):
            raise _fail("notion_property_backfill_plan_invalid")
        self._values: dict[tuple[str, str, str], bytes | None] = {}
        for item, write in zip(plan.manifest.items, plan.writes):
            if item.target_ref != write.target_ref:
                raise _fail("notion_property_backfill_plan_invalid")
            self._values[(item.item_id, "source_properties", "pre")] = None
            self._values[
                (item.item_id, "source_properties", "post")
            ] = write.post_value
            self._values[
                (item.item_id, "source_properties", "source")
            ] = _source_binding_value(plan, write)

    def field_value(
        self,
        *,
        item_id: str,
        field_ref: str,
        state: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        heartbeat()
        return self._values[(item_id, field_ref, state)]


class _NotionPropertyTargetBoundary:
    def __init__(
        self,
        root: Path,
        archive_id: str,
        identities: Mapping[str, str],
        source_page_ids: Mapping[str, str],
    ) -> None:
        self.root = root
        self.archive_id = archive_id
        self.identities = dict(identities)
        self.source_page_ids = dict(source_page_ids)
        if set(self.identities) != set(self.source_page_ids):
            raise _fail("notion_property_backfill_plan_invalid")

    def _target(self, target_kind: str, target_ref: str) -> Path:
        if target_kind != "zettel" or target_ref not in self.identities:
            raise ValueError("target boundary")
        return _safe_target_from_ref(self.root, target_ref)

    def _snapshot(
        self,
        target_kind: str,
        target_ref: str,
    ) -> tuple[Path, bytes, dict[str, Any]]:
        target = self._target(target_kind, target_ref)
        raw = _read_regular(target, max_bytes=MAX_CANONICAL_FILE_BYTES)
        frontmatter = _frontmatter(raw)
        identity = _target_identity_sha256(
            self.archive_id,
            target_ref,
            frontmatter,
        )
        try:
            source_page_id = _canonical_source_page_id(frontmatter)
        except ValueError:
            raise ValueError("target source identity drift") from None
        if (
            identity != self.identities[target_ref]
            or source_page_id != self.source_page_ids[target_ref]
            or frontmatter.get("archive_id") != self.archive_id
            or frontmatter.get("status") != "canonical"
        ):
            raise ValueError("target identity drift")
        return target, raw, frontmatter


class _NotionPropertyVerifier(_NotionPropertyTargetBoundary):
    def target_identity_sha256(
        self,
        *,
        target_kind: str,
        target_ref: str,
        heartbeat: Callable[[], None],
    ) -> str:
        heartbeat()
        _target, _raw, frontmatter = self._snapshot(target_kind, target_ref)
        return _target_identity_sha256(self.archive_id, target_ref, frontmatter)

    def read_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        heartbeat: Callable[[], None],
    ) -> bytes | None:
        heartbeat()
        if field_ref != "source_properties":
            raise ValueError("field boundary")
        _target, raw, frontmatter = self._snapshot(target_kind, target_ref)
        if field_ref not in frontmatter:
            return None
        state, _field_sha, _candidate = _managed_field_state(raw)
        if state != "managed":
            raise ValueError("field is not owned by this adapter")
        return _canonical_bytes(frontmatter[field_ref])


class _NotionPropertyWriter(_NotionPropertyTargetBoundary):
    def __init__(
        self,
        root: Path,
        archive_id: str,
        identities: Mapping[str, str],
        source_page_ids: Mapping[str, str],
        index_lifecycle: ZettelIndexBatchLifecycle,
    ) -> None:
        super().__init__(root, archive_id, identities, source_page_ids)
        self.index_lifecycle = index_lifecycle

    def write_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        value: bytes | None,
        heartbeat: Callable[[], None],
    ) -> None:
        heartbeat()
        if field_ref != "source_properties":
            raise ValueError("field boundary")
        target, raw, frontmatter = self._snapshot(target_kind, target_ref)
        if value is None:
            state, _field_sha, candidate = _managed_field_state(raw)
            if state != "managed" or candidate is None:
                raise ValueError("managed field cannot be reverted")
        else:
            if field_ref in frontmatter:
                raise ValueError("field is not absent")
            try:
                decoded = _strict_json(value)
            except NotionPropertyBackfillError:
                raise ValueError("field payload") from None
            if (
                type(decoded) is not dict
                or decoded.get("schema_version")
                != SOURCE_PROPERTIES_SCHEMA_VERSION
                or value != _canonical_bytes(decoded)
            ):
                raise ValueError("field payload")
            candidate = _insert_managed_field(raw, decoded)
        heartbeat()
        self.index_lifecycle.before_canonical_write()
        _atomic_replace(
            self.root,
            target,
            expected_bytes=raw,
            replacement_bytes=candidate,
        )


def _index_mutation_owner_sha256(
    plan: _NotionPropertyBackfillPlan,
) -> str:
    if plan.manifest is None:
        raise _fail("notion_property_backfill_plan_invalid")
    return archive_services.archive_manifest_mutation_owner_sha256(
        operation="notion_property_backfill",
        operation_binding_sha256=plan.manifest.manifest_sha256,
    )


def _execution_adapters(
    plan: _NotionPropertyBackfillPlan,
    *,
    index_lifecycle: ZettelIndexBatchLifecycle | None = None,
) -> tuple[
    _NotionPropertyPayloads,
    _NotionPropertyWriter,
    _NotionPropertyVerifier,
]:
    if plan.manifest is None:
        raise _fail("notion_property_backfill_no_writes")
    identities = {
        item.target_ref: item.target_identity_sha256 for item in plan.manifest.items
    }
    source_page_ids = {
        write.target_ref: write.normalized_source_page_id
        for write in plan.writes
    }
    lifecycle = index_lifecycle or ZettelIndexBatchLifecycle.inspect(
        plan.archive_root,
        has_zettel_targets=True,
        allow_dirty_resume=False,
        operation_owner_sha256=_index_mutation_owner_sha256(plan),
    )
    return (
        _NotionPropertyPayloads(plan),
        _NotionPropertyWriter(
            plan.archive_root,
            plan.archive_id,
            identities,
            source_page_ids,
            lifecycle,
        ),
        _NotionPropertyVerifier(
            plan.archive_root,
            plan.archive_id,
            identities,
            source_page_ids,
        ),
    )


def _notion_property_index_entries(
    plan: _NotionPropertyBackfillPlan,
    writer: _NotionPropertyWriter,
) -> tuple[dict[str, Any], ...]:
    if plan.manifest is None:
        raise _fail("notion_property_backfill_plan_invalid")
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in plan.manifest.items:
        target, raw, frontmatter = writer._snapshot(
            item.target_kind,
            item.target_ref,
        )
        relative = archive_services.archive_relative_path(
            target,
            plan.archive_root,
        )
        if relative in seen:
            continue
        seen.add(relative)
        boundary = archive_services.parse_approval_zettel_content_boundary(
            raw.decode("utf-8")
        )
        if boundary.get("state") == "blocked":
            raise ValueError("target")
        entries.append(
            {
                "path": target,
                "frontmatter": frontmatter,
                "body": str(boundary.get("body") or ""),
                "expected_file_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return tuple(entries)


def _unresolved_result_projection(
    plan: _NotionPropertyBackfillPlan,
) -> dict[str, Any]:
    """Return only content-free, manifest-bound unresolved-set evidence."""

    if plan.manifest is None or plan.manifest.operation_evidence is None:
        raise _fail("notion_property_backfill_plan_invalid")
    evidence = plan.manifest.operation_evidence.document()
    counts = evidence["counts"]
    digests = evidence["digests"]
    durable_category_counts = {
        category: counts[f"{category}_page_count"]
        for category in ("mapped", "already_equal", "unmapped", "review")
    }
    durable_category_source_sets = {
        category: digests[f"{category}_source_set_sha256"]
        for category in ("mapped", "already_equal", "unmapped", "review")
    }
    return {
        "classification_binding_sha256": digests[
            "classification_binding_sha256"
        ],
        "category_counts": durable_category_counts,
        "category_source_set_sha256": durable_category_source_sets,
        "unresolved_source_set_sha256": digests[
            "unresolved_source_set_sha256"
        ],
        "unresolved_reason_set_sha256": digests[
            "unresolved_reason_set_sha256"
        ],
        "unmapped_reason_counts": {
            "unmapped_no_canonical_target": counts["unmapped_page_count"]
        },
        "unmapped_populated_page_count": counts[
            "unmapped_populated_page_count"
        ],
        "unmapped_populated_property_count": (
            counts["unmapped_populated_property_count"]
        ),
        "unmapped_opaque_property_count": counts[
            "unmapped_opaque_property_count"
        ],
        "durable_operation_evidence": evidence,
        "operation_evidence_sha256": (
            plan.manifest.operation_evidence.evidence_sha256
        ),
        "current_observed_category_counts": dict(plan.category_counts),
        "current_observed_classification_binding_sha256": (
            plan.classification_binding_sha256
        ),
        "unresolved_source_evidence_not_modified": True,
        "unresolved_source_lifecycle_guaranteed": False,
        "unmapped_treated_as_drop": False,
        "classification_bound_by_manifest": True,
    }


def _publish_execution_locator(
    plan: _NotionPropertyBackfillPlan,
    claim: _ClaimedExactHumanApproval,
    authority: ExactOperationApprovalAuthority,
    *,
    mode: str,
    hook: Callable[[Mapping[str, Any]], None] | None,
) -> str:
    """Publish the opaque resume locator before entering the common runner."""

    manifest = _notion_property_operation_manifest(plan, mode=mode)
    selected_fields = (
        tuple(
            (item.item_id, "source_properties")
            for item in manifest.items
        )
        if mode == "revert"
        else None
    )
    execution_sha256 = exact_operation_execution_sha256(
        manifest,
        mode=mode,
        selected_fields=selected_fields,
        approval_authority=authority,
    )
    if hook is not None:
        document = {
            "schema_version": EXECUTION_LOCATOR_SCHEMA_VERSION,
            "mode": mode,
            "approval_id": claim.approval_id,
            "execution_sha256": execution_sha256,
            "manifest_sha256": manifest.manifest_sha256,
            "checkpoint_required_for_resume": True,
            "private_values_echoed": False,
            "paths_echoed": False,
            "source_page_ids_echoed": False,
            "property_values_echoed": False,
        }
        try:
            hook(document)
        except Exception:
            # Observability is never mutation authority.
            pass
    return execution_sha256


def _assert_approved_manifest(
    plan: _NotionPropertyBackfillPlan,
    approval_claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
    *,
    mode: str,
) -> ExactOperationApprovalAuthority:
    if plan.manifest is None:
        raise _fail("notion_property_backfill_no_writes")
    binding = _notion_property_backfill_approval_binding(plan, mode=mode)
    expected_operation = (
        ExactHumanApprovalOperation.notion_property_backfill
        if mode == "apply"
        else ExactHumanApprovalOperation.notion_property_backfill_revert
    )
    if (
        type(approval_claim) is not _ClaimedExactHumanApproval
        or type(context) is not ExactHumanApprovalContext
        or context.operation is not expected_operation
        or context.plan_sha256 != binding.plan_sha256
        or context.target_binding_sha256 != binding.target_binding_sha256
    ):
        raise _fail("notion_property_backfill_approval_required")
    try:
        reference = _ClaimedExactHumanApproval.assert_ready_for_context(
            approval_claim,
            context,
        )
    except ExactHumanApprovalError:
        raise _fail("notion_property_backfill_approval_required") from None
    try:
        return ExactOperationApprovalAuthority.from_reference(reference)
    except ExactOperationManifestError:
        raise _fail("notion_property_backfill_approval_required") from None


def _revalidated_plan(
    plan: _NotionPropertyBackfillPlan,
    *,
    allow_managed_equal: bool = False,
    progress: Callable[[Mapping[str, Any]], None] | None = None,
) -> _NotionPropertyBackfillPlan:
    current = _plan_notion_property_backfill_core(
        plan.archive_root,
        plan.mirror_path,
        acceptance=plan._acceptance,
        progress=progress,
    )
    if current.manifest is None or plan.manifest is None:
        raise _fail("notion_property_backfill_plan_changed")
    if allow_managed_equal:
        # Apply changes the public classification from ``mapped`` to managed
        # ``already_equal``.  Resume/revert must keep using the originally
        # approved manifest while proving that every raw source, exact target,
        # payload, and unresolved set is otherwise unchanged.
        stable_after_write = (
            current.mirror_sha256 == plan.mirror_sha256
            and current.writes == plan.writes
            and current.unresolved_source_set_sha256
            == plan.unresolved_source_set_sha256
            and current.unresolved_reason_set_sha256
            == plan.unresolved_reason_set_sha256
            and current.category_counts["unmapped"]
            == plan.category_counts["unmapped"]
            and current.category_counts["review"]
            == plan.category_counts["review"]
            and (
                current.category_counts["mapped"]
                + current.category_counts["already_equal"]
            )
            == (
                plan.category_counts["mapped"]
                + plan.category_counts["already_equal"]
            )
            and current.acceptance_verified
            and current.zero_silent_omission
        )
        if not stable_after_write:
            raise _fail("notion_property_backfill_plan_changed")
        return plan
    if (
        current.manifest.document() != plan.manifest.document()
        or current.source_inventory_sha256 != plan.source_inventory_sha256
        or current.audit_basis_sha256 != plan.audit_basis_sha256
    ):
        raise _fail("notion_property_backfill_plan_changed")
    return current


def _assert_canonical_projection_unchanged(
    plan: _NotionPropertyBackfillPlan,
    *,
    progress: Callable[[Mapping[str, Any]], None] | None,
) -> None:
    """Recheck the complete canonical join projection under writer lock."""

    publisher = _PlanningProgressPublisher(progress)
    canonical, _count, invalid_count, _excluded = _scan_canonical(
        plan.archive_root,
        plan.archive_id,
        progress=publisher,
    )
    current = _canonical_projection_sha256(
        canonical,
        archive_id=plan.archive_id,
        invalid_count=invalid_count,
    )
    if not hmac.compare_digest(current, plan.canonical_projection_sha256):
        raise _fail("notion_property_backfill_plan_changed")


def _merge_index_truth(
    result: dict[str, Any],
    index_truth: Mapping[str, Any],
    *,
    failure_state: str,
) -> dict[str, Any]:
    result.update(index_truth)
    if index_truth.get("index_rebuild_required") is True:
        result.update(
            {
                "ok": False,
                "reason_code": archive_services.INDEX_REBUILD_REQUIRED,
                "state": failure_state,
                "blockers": [archive_services.INDEX_REBUILD_REQUIRED],
            }
        )
    return result


def _index_precondition_blocked_result(
    plan: _NotionPropertyBackfillPlan,
    manifest: ExactOperationManifest,
    *,
    mode: str,
    lifecycle: ZettelIndexBatchLifecycle,
) -> dict[str, Any]:
    is_revert = mode == "revert"
    return {
        "schema_version": (
            REVERT_RESULT_SCHEMA_VERSION if is_revert else RESULT_SCHEMA_VERSION
        ),
        "ok": False,
        "reason_code": archive_services.INDEX_REBUILD_REQUIRED,
        "state": (
            "notion_property_backfill_revert_index_rebuild_required"
            if is_revert
            else "notion_property_backfill_index_rebuild_required"
        ),
        "manifest_sha256": manifest.manifest_sha256,
        "blockers": [archive_services.INDEX_REBUILD_REQUIRED],
        "next_safe_actions": list(
            archive_services.INDEX_REBUILD_NEXT_SAFE_ACTIONS
        ),
        "executed_field_count": 0,
        "written_field_count": 0,
        "resumed_field_count": 0,
        "writes_performed": False,
        "applied_property_count": 0,
        "applied_populated_property_count": 0,
        "reverted_field_count": 0,
        "field_scoped_revert_supported": True,
        "field_scoped_revert": is_revert,
        "common_exact_operation_manifest_used": True,
        "parallel_receipt_created": False,
        **_unresolved_result_projection(plan),
        "private_values_echoed": False,
        "paths_echoed": False,
        "source_page_ids_echoed": False,
        "property_values_echoed": False,
        **lifecycle.precondition_truth(),
    }


def _apply_with_store(
    plan: _NotionPropertyBackfillPlan,
    authority: ExactOperationApprovalAuthority,
    checkpoints: FileExactOperationCheckpointStore,
    *,
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
    index_lifecycle: ZettelIndexBatchLifecycle | None = None,
) -> dict[str, Any]:
    if plan.manifest is None or plan.manifest.operation_evidence is None:
        raise _fail("notion_property_backfill_plan_invalid")
    operation_counts = plan.manifest.operation_evidence.document()["counts"]
    index_lifecycle = index_lifecycle or ZettelIndexBatchLifecycle.inspect(
        plan.archive_root,
        has_zettel_targets=bool(plan.manifest.items),
        allow_dirty_resume=resume,
        operation_owner_sha256=_index_mutation_owner_sha256(plan),
    )
    if index_lifecycle.precondition_blocked:
        return _index_precondition_blocked_result(
            plan,
            plan.manifest,
            mode="apply",
            lifecycle=index_lifecycle,
        )
    payloads, writer, verifier = _execution_adapters(
        plan,
        index_lifecycle=index_lifecycle,
    )
    try:
        core_result = apply_exact_operation(
            plan.manifest,
            payloads=payloads,
            writer=writer,
            verifier=verifier,
            checkpoint_store=checkpoints,
            approval_authority=authority,
            resume=resume,
            progress_hook=progress_hook,
        )
    except BaseException:
        index_lifecycle.interrupted()
        raise
    try:
        entries = (
            _notion_property_index_entries(plan, writer)
            if index_lifecycle.mutation_active
            else ()
        )
        index_truth = index_lifecycle.finalize(entries)
    except Exception:
        index_truth = index_lifecycle.delta_failed()
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "ok": core_result.get("status") == "completed",
        "reason_code": "notion_property_backfill_succeeded",
        "manifest_sha256": plan.manifest.manifest_sha256,
        "execution": core_result,
        "executed_field_count": core_result.get("field_count", 0),
        "written_field_count": core_result.get("written_field_count", 0),
        "resumed_field_count": core_result.get("resumed_field_count", 0),
        "writes_performed": core_result.get("written_field_count", 0) > 0,
        "applied_property_count": operation_counts["mapped_property_count"],
        "applied_populated_property_count": operation_counts[
            "mapped_populated_property_count"
        ],
        "field_scoped_revert_supported": True,
        "common_exact_operation_manifest_used": True,
        "parallel_receipt_created": False,
        **_unresolved_result_projection(plan),
        "private_values_echoed": False,
        "paths_echoed": False,
        "source_page_ids_echoed": False,
        "property_values_echoed": False,
    }
    return _merge_index_truth(
        result,
        index_truth,
        failure_state="notion_property_backfill_index_update_failed",
    )


def _apply_notion_property_backfill_core(
    plan: _NotionPropertyBackfillPlan,
    approval_claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
    resume: bool = False,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    planning_progress: Callable[[Mapping[str, Any]], None] | None = None,
    execution_locator_hook: (
        Callable[[Mapping[str, Any]], None] | None
    ) = None,
) -> dict[str, Any]:
    """Execute field effects only through ExactOperationManifest v1."""

    if (
        type(plan) is not _NotionPropertyBackfillPlan
        or (not plan.resumable if resume else not plan.approveable)
    ):
        raise _fail("notion_property_backfill_no_writes")
    current = _revalidated_plan(
        plan,
        allow_managed_equal=resume,
        progress=planning_progress,
    )
    authority = _assert_approved_manifest(
        current,
        approval_claim,
        context,
        mode="apply",
    )
    with exact_operation_writer_lock(current.archive_root) as writer_lock:
        index_lifecycle = ZettelIndexBatchLifecycle.inspect(
            current.archive_root,
            has_zettel_targets=bool(current.manifest.items),
            allow_dirty_resume=resume,
            operation_owner_sha256=_index_mutation_owner_sha256(current),
        )
        if index_lifecycle.precondition_blocked:
            return _index_precondition_blocked_result(
                current,
                current.manifest,
                mode="apply",
                lifecycle=index_lifecycle,
            )
        _publish_execution_locator(
            current,
            approval_claim,
            authority,
            mode="apply",
            hook=execution_locator_hook,
        )
        _assert_canonical_projection_unchanged(
            current,
            progress=planning_progress,
        )
        checkpoints = FileExactOperationCheckpointStore(
            current.archive_root,
            writer_lock=writer_lock,
        )
        return _apply_with_store(
            current,
            authority,
            checkpoints,
            resume=resume,
            progress_hook=progress_hook,
            index_lifecycle=index_lifecycle,
        )


def verify_notion_property_backfill(
    plan: _NotionPropertyBackfillPlan,
    *,
    state: str = "post",
    heartbeat: Callable[[], None] | None = None,
) -> dict[str, Any]:
    if (
        type(plan) is not _NotionPropertyBackfillPlan
        or plan.manifest is None
        or state not in {"pre", "post"}
    ):
        raise _fail("notion_property_backfill_plan_invalid")
    _payloads, _writer, verifier = _execution_adapters(plan)
    result = verify_exact_operation(
        plan.manifest,
        verifier=verifier,
        state=state,
        heartbeat=heartbeat,
    )
    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "ok": result["all_match"],
        "reason_code": (
            "notion_property_backfill_verified"
            if result["all_match"]
            else "notion_property_backfill_verification_incomplete"
        ),
        "manifest_sha256": plan.manifest.manifest_sha256,
        "verification": result,
        "field_scoped_verification": True,
        "private_values_echoed": False,
        "paths_echoed": False,
        "source_page_ids_echoed": False,
        "property_values_echoed": False,
        "writes_performed": False,
    }


def plan_notion_property_backfill_revert(
    plan: _NotionPropertyBackfillPlan,
) -> dict[str, Any]:
    verification = verify_notion_property_backfill(plan, state="post")
    manifest = _notion_property_operation_manifest(plan, mode="revert")
    return {
        "schema_version": REVERT_PLAN_SCHEMA_VERSION,
        "ok": verification["ok"],
        "reason_code": (
            "notion_property_backfill_revert_ready"
            if verification["ok"]
            else "notion_property_backfill_revert_review_required"
        ),
        "manifest_sha256": manifest.manifest_sha256,
        "selected_field_count": len(plan.writes),
        "selection_sha256": _json_sha256(
            [
                (item.item_id, "source_properties")
                for item in manifest.items
            ]
        ),
        "field_scoped_revert": True,
        "requires_exact_human_approval": True,
        "private_values_echoed": False,
        "paths_echoed": False,
        "writes_performed": False,
    }


def _revert_with_store(
    plan: _NotionPropertyBackfillPlan,
    authority: ExactOperationApprovalAuthority,
    checkpoints: FileExactOperationCheckpointStore,
    *,
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
    index_lifecycle: ZettelIndexBatchLifecycle | None = None,
) -> dict[str, Any]:
    manifest = _notion_property_operation_manifest(plan, mode="revert")
    index_lifecycle = index_lifecycle or ZettelIndexBatchLifecycle.inspect(
        plan.archive_root,
        has_zettel_targets=bool(manifest.items),
        allow_dirty_resume=True,
        operation_owner_sha256=_index_mutation_owner_sha256(plan),
    )
    if index_lifecycle.precondition_blocked:
        return _index_precondition_blocked_result(
            plan,
            manifest,
            mode="revert",
            lifecycle=index_lifecycle,
        )
    payloads, writer, verifier = _execution_adapters(
        plan,
        index_lifecycle=index_lifecycle,
    )
    selection = tuple(
        (item.item_id, "source_properties") for item in manifest.items
    )
    try:
        core_result = revert_exact_operation_fields(
            manifest,
            selected_fields=selection,
            payloads=payloads,
            writer=writer,
            verifier=verifier,
            checkpoint_store=checkpoints,
            approval_authority=authority,
            resume=resume,
            progress_hook=progress_hook,
        )
    except BaseException:
        index_lifecycle.interrupted()
        raise
    try:
        entries = (
            _notion_property_index_entries(plan, writer)
            if index_lifecycle.mutation_active
            else ()
        )
        index_truth = index_lifecycle.finalize(entries)
    except Exception:
        index_truth = index_lifecycle.delta_failed()
    result = {
        "schema_version": REVERT_RESULT_SCHEMA_VERSION,
        "ok": core_result.get("status") == "completed",
        "reason_code": "notion_property_backfill_reverted",
        "manifest_sha256": manifest.manifest_sha256,
        "execution": core_result,
        "executed_field_count": core_result.get("field_count", 0),
        "written_field_count": core_result.get("written_field_count", 0),
        "resumed_field_count": core_result.get("resumed_field_count", 0),
        "writes_performed": core_result.get("written_field_count", 0) > 0,
        "reverted_field_count": len(selection),
        "field_scoped_revert": True,
        "common_exact_operation_manifest_used": True,
        "parallel_receipt_created": False,
        **_unresolved_result_projection(plan),
        "private_values_echoed": False,
        "paths_echoed": False,
        "source_page_ids_echoed": False,
        "property_values_echoed": False,
    }
    return _merge_index_truth(
        result,
        index_truth,
        failure_state="notion_property_backfill_revert_index_update_failed",
    )


def _revert_notion_property_backfill_core(
    plan: _NotionPropertyBackfillPlan,
    approval_claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
    resume: bool = False,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    planning_progress: Callable[[Mapping[str, Any]], None] | None = None,
    execution_locator_hook: (
        Callable[[Mapping[str, Any]], None] | None
    ) = None,
) -> dict[str, Any]:
    if (
        type(plan) is not _NotionPropertyBackfillPlan
        or plan.manifest is None
        or not plan.resumable
    ):
        raise _fail("notion_property_backfill_revert_no_writes")
    current = _revalidated_plan(
        plan,
        allow_managed_equal=True,
        progress=planning_progress,
    )
    authority = _assert_approved_manifest(
        current,
        approval_claim,
        context,
        mode="revert",
    )
    with exact_operation_writer_lock(current.archive_root) as writer_lock:
        manifest = _notion_property_operation_manifest(current, mode="revert")
        index_lifecycle = ZettelIndexBatchLifecycle.inspect(
            current.archive_root,
            has_zettel_targets=bool(manifest.items),
            allow_dirty_resume=True,
            operation_owner_sha256=_index_mutation_owner_sha256(current),
        )
        if index_lifecycle.precondition_blocked:
            return _index_precondition_blocked_result(
                current,
                manifest,
                mode="revert",
                lifecycle=index_lifecycle,
            )
        _publish_execution_locator(
            current,
            approval_claim,
            authority,
            mode="revert",
            hook=execution_locator_hook,
        )
        _assert_canonical_projection_unchanged(
            current,
            progress=planning_progress,
        )
        checkpoints = FileExactOperationCheckpointStore(
            current.archive_root,
            writer_lock=writer_lock,
        )
        return _revert_with_store(
            current,
            authority,
            checkpoints,
            resume=resume,
            progress_hook=progress_hook,
            index_lifecycle=index_lifecycle,
        )


def execute_notion_property_backfill(
    plan: _NotionPropertyBackfillPlan,
    *,
    reviewer_claim: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    planning_progress: Callable[[Mapping[str, Any]], None] | None = None,
    execution_locator_hook: (
        Callable[[Mapping[str, Any]], None] | None
    ) = None,
) -> dict[str, Any]:
    """Show the native exact review once, then execute the bound backfill."""

    if type(plan) is not _NotionPropertyBackfillPlan or not plan.approveable:
        raise _fail("notion_property_backfill_no_writes")
    if plan.manifest is None:
        raise _fail("notion_property_backfill_plan_invalid")
    index_lifecycle = ZettelIndexBatchLifecycle.inspect(
        plan.archive_root,
        has_zettel_targets=bool(plan.manifest.items),
        allow_dirty_resume=False,
        operation_owner_sha256=_index_mutation_owner_sha256(plan),
    )
    if index_lifecycle.precondition_blocked:
        return _index_precondition_blocked_result(
            plan,
            plan.manifest,
            mode="apply",
            lifecycle=index_lifecycle,
        )
    context = _notion_property_backfill_context(
        plan,
        reviewer_claim=reviewer_claim,
        mode="apply",
    )
    return _execute_exact_human_approved_write(
        plan.archive_root,
        context,
        lambda claim: _apply_notion_property_backfill_core(
            plan,
            claim,
            context=context,
            progress_hook=progress_hook,
            planning_progress=planning_progress,
            execution_locator_hook=execution_locator_hook,
        ),
    )


def execute_notion_property_backfill_revert(
    plan: _NotionPropertyBackfillPlan,
    *,
    reviewer_claim: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    planning_progress: Callable[[Mapping[str, Any]], None] | None = None,
    execution_locator_hook: (
        Callable[[Mapping[str, Any]], None] | None
    ) = None,
) -> dict[str, Any]:
    """Show the native exact review once, then revert only the owned field."""

    if type(plan) is not _NotionPropertyBackfillPlan or not plan.resumable:
        raise _fail("notion_property_backfill_revert_no_writes")
    if plan_notion_property_backfill_revert(plan)["ok"] is not True:
        # Do not start a one-use native approval claim unless every selected
        # managed field is currently in the exact post-state being reverted.
        raise _fail("notion_property_backfill_revert_no_writes")
    manifest = _notion_property_operation_manifest(plan, mode="revert")
    index_lifecycle = ZettelIndexBatchLifecycle.inspect(
        plan.archive_root,
        has_zettel_targets=bool(manifest.items),
        allow_dirty_resume=True,
        operation_owner_sha256=_index_mutation_owner_sha256(plan),
    )
    if index_lifecycle.precondition_blocked:
        return _index_precondition_blocked_result(
            plan,
            manifest,
            mode="revert",
            lifecycle=index_lifecycle,
        )
    context = _notion_property_backfill_context(
        plan,
        reviewer_claim=reviewer_claim,
        mode="revert",
    )
    return _execute_exact_human_approved_write(
        plan.archive_root,
        context,
        lambda claim: _revert_notion_property_backfill_core(
            plan,
            claim,
            context=context,
            progress_hook=progress_hook,
            planning_progress=planning_progress,
            execution_locator_hook=execution_locator_hook,
        ),
    )


def _resume_notion_property_backfill_approved_core(
    plan: _NotionPropertyBackfillPlan,
    *,
    reviewer_claim: str,
    approval_id: str,
    execution_sha256: str,
    mode: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    planning_progress: Callable[[Mapping[str, Any]], None] | None = None,
    execution_locator_hook: (
        Callable[[Mapping[str, Any]], None] | None
    ) = None,
    key_provider: Any = None,
) -> dict[str, Any]:
    """Rehydrate the same started claim; never display a second approval."""

    if (
        type(plan) is not _NotionPropertyBackfillPlan
        or not plan.resumable
        or plan.manifest is None
        or mode not in {"apply", "revert"}
        or type(execution_sha256) is not str
        or _SHA256_RE.fullmatch(execution_sha256) is None
    ):
        raise _fail("notion_property_backfill_plan_invalid")
    current = _revalidated_plan(
        plan,
        allow_managed_equal=True,
        progress=planning_progress,
    )
    context = _notion_property_backfill_context(
        current,
        reviewer_claim=reviewer_claim,
        mode=mode,
    )
    operation_manifest = _notion_property_operation_manifest(
        current,
        mode=mode,
    )
    selection = tuple(
        (item.item_id, "source_properties") for item in operation_manifest.items
    )
    with exact_operation_writer_lock(current.archive_root) as writer_lock:
        checkpoints = FileExactOperationCheckpointStore(
            current.archive_root,
            writer_lock=writer_lock,
        )

        locator_published = False

        def authority_and_execution(
            claim: _ClaimedExactHumanApproval,
        ) -> tuple[ExactOperationApprovalAuthority, str]:
            nonlocal locator_published
            if not hmac.compare_digest(claim.approval_id, approval_id):
                raise _fail("notion_property_backfill_approval_required")
            authority = _assert_approved_manifest(
                current,
                claim,
                context,
                mode=mode,
            )
            actual_execution_sha256 = exact_operation_execution_sha256(
                operation_manifest,
                mode=mode,
                selected_fields=selection if mode == "revert" else None,
                approval_authority=authority,
            )
            if not hmac.compare_digest(
                actual_execution_sha256,
                execution_sha256,
            ):
                raise _fail("notion_property_backfill_plan_changed")
            if not locator_published:
                _publish_execution_locator(
                    current,
                    claim,
                    authority,
                    mode=mode,
                    hook=execution_locator_hook,
                )
                locator_published = True
            return authority, actual_execution_sha256

        def checkpoint_guard(claim: _ClaimedExactHumanApproval) -> bool:
            _authority, actual_execution_sha256 = authority_and_execution(claim)
            _assert_canonical_projection_unchanged(
                current,
                progress=planning_progress,
            )
            return checkpoints.resume_checkpoint_present(
                actual_execution_sha256
            )

        def writer(claim: _ClaimedExactHumanApproval) -> Mapping[str, Any]:
            authority, _actual_execution_sha256 = authority_and_execution(claim)
            if mode == "apply":
                return _apply_with_store(
                    current,
                    authority,
                    checkpoints,
                    resume=True,
                    progress_hook=progress_hook,
                )
            return _revert_with_store(
                current,
                authority,
                checkpoints,
                resume=True,
                progress_hook=progress_hook,
            )

        return _resume_exact_human_approved_write_core(
            current.archive_root,
            context,
            approval_id,
            checkpoint_guard,
            writer,
            key_provider=key_provider,
        )


def resume_notion_property_backfill(
    plan: _NotionPropertyBackfillPlan,
    *,
    reviewer_claim: str,
    approval_id: str,
    execution_sha256: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    planning_progress: Callable[[Mapping[str, Any]], None] | None = None,
    execution_locator_hook: (
        Callable[[Mapping[str, Any]], None] | None
    ) = None,
) -> dict[str, Any]:
    return _resume_notion_property_backfill_approved_core(
        plan,
        reviewer_claim=reviewer_claim,
        approval_id=approval_id,
        execution_sha256=execution_sha256,
        mode="apply",
        progress_hook=progress_hook,
        planning_progress=planning_progress,
        execution_locator_hook=execution_locator_hook,
    )


def resume_notion_property_backfill_revert(
    plan: _NotionPropertyBackfillPlan,
    *,
    reviewer_claim: str,
    approval_id: str,
    execution_sha256: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    planning_progress: Callable[[Mapping[str, Any]], None] | None = None,
    execution_locator_hook: (
        Callable[[Mapping[str, Any]], None] | None
    ) = None,
) -> dict[str, Any]:
    return _resume_notion_property_backfill_approved_core(
        plan,
        reviewer_claim=reviewer_claim,
        approval_id=approval_id,
        execution_sha256=execution_sha256,
        mode="revert",
        progress_hook=progress_hook,
        planning_progress=planning_progress,
        execution_locator_hook=execution_locator_hook,
    )


__all__ = [
    "NOTION_PROPERTY_BACKFILL_OPERATION",
    "NotionPropertyBackfillError",
    "SOURCE_PROPERTIES_SCHEMA_VERSION",
    "execute_notion_property_backfill",
    "execute_notion_property_backfill_revert",
    "plan_notion_property_backfill",
    "plan_notion_property_backfill_revert",
    "resume_notion_property_backfill",
    "resume_notion_property_backfill_revert",
    "verify_notion_property_backfill",
]
