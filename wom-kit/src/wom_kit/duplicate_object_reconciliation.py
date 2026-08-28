"""Bounded duplicate object-manifest classification and exact repair.

The module deliberately separates four cases that used to collapse into one
``duplicate_object_id`` blocker:

* byte-identical repeated rows, which can be removed without merging evidence;
* compatible repeated evidence, which needs a human-designed merge policy; and
* one strictly proved canonical-local/external-prehashed pair, whose evidence
  can be folded losslessly into the canonical row after human approval; and
* all other conflicting definitions, which must remain blocked.

Both repair classes are bound to one live, one-use
:mod:`wom_kit.exact_human_approval` reference.  The original manifest bytes
are preserved in a create-only snapshot before replacement.  A separate
native-approved revert restores those exact bytes only while the manifest is
still at the recorded post-state.  Public results contain counts and digests,
never object ids, paths, location labels, provenance values, or row contents.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat as stat_module
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

import yaml

from . import archive_services
from .exact_human_approval import (
    _ClaimedExactHumanApproval,
    _audit_exact_human_approval_terminal_record_core,
    ExactHumanApprovalError,
    REFERENCE_SCHEMA_VERSION,
    TERMINAL_RECORD_AUTHENTICATION_SCHEMA_VERSION,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)


PLAN_SCHEMA_VERSION = "wom-kit/duplicate-object-reconciliation-plan/v0.1"
RESULT_SCHEMA_VERSION = "wom-kit/duplicate-object-reconciliation-result/v0.1"
JOURNAL_SCHEMA_VERSION = "wom-kit/duplicate-object-reconciliation-journal/v0.1"
RECEIPT_SCHEMA_VERSION = "wom-kit/duplicate-object-reconciliation-receipt/v0.1"
PAIR_EVIDENCE_SCHEMA_VERSION = (
    "wom-kit/private-canonical-external-object-reconciliation/v0.1"
)
PAIR_EVIDENCE_FIELD = "_wom_private_duplicate_reconciliation"
UNRESOLVED_INVENTORY_SCHEMA_VERSION = (
    "wom-kit/duplicate-object-unresolved-inventory/v0.1"
)
REVERT_PLAN_SCHEMA_VERSION = (
    "wom-kit/duplicate-object-reconciliation-revert-plan/v0.1"
)
REVERT_RESULT_SCHEMA_VERSION = (
    "wom-kit/duplicate-object-reconciliation-revert-result/v0.1"
)
REVERT_JOURNAL_SCHEMA_VERSION = (
    "wom-kit/duplicate-object-reconciliation-revert-journal/v0.1"
)
REVERT_RECEIPT_SCHEMA_VERSION = (
    "wom-kit/duplicate-object-reconciliation-revert-receipt/v0.1"
)
MANIFEST_RELATIVE_PATH = PurePosixPath("objects/manifests/files.jsonl")
SNAPSHOT_ROOT = PurePosixPath("snapshots/objects/duplicate-reconciliation")
JOURNAL_ROOT = PurePosixPath("journals/objects/duplicate-reconciliation")
RECEIPT_ROOT = PurePosixPath("receipts/objects/duplicate-reconciliation")
LOCK_ROOT = PurePosixPath("profiles/local/duplicate-object-reconciliation/locks")
REVERT_SNAPSHOT_ROOT = PurePosixPath(
    "snapshots/objects/duplicate-reconciliation-revert"
)
REVERT_JOURNAL_ROOT = PurePosixPath(
    "journals/objects/duplicate-reconciliation-revert"
)
REVERT_RECEIPT_ROOT = PurePosixPath(
    "receipts/objects/duplicate-reconciliation-revert"
)
REVERT_LOCK_ROOT = PurePosixPath(
    "profiles/local/duplicate-object-reconciliation/revert-locks"
)
TERMINAL_COMPENSATION_ROOT = PurePosixPath(
    "profiles/local/duplicate-object-reconciliation/terminal-compensations"
)
TERMINAL_COMPENSATION_SCHEMA_VERSION = (
    "wom-kit/duplicate-object-terminal-compensation/v0.1"
)
TERMINAL_AUTHENTICATION_SCHEMA_VERSION = (
    TERMINAL_RECORD_AUTHENTICATION_SCHEMA_VERSION
)
REVERT_FINALIZATION_EVIDENCE_SCHEMA_VERSION = (
    "wom-kit/duplicate-object-revert-finalization-evidence/v0.1"
)
MAX_MANIFEST_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_ROWS = 1_000_000
MAX_RECONCILIATION_RECEIPTS = 4096
MAX_RECEIPT_BYTES = 1024 * 1024

_OBJECT_ID_RE = re.compile(r"sha256:([0-9a-f]{64})\Z")
_SHA256_RE = re.compile(r"(?:sha256:)?([0-9a-f]{64})\Z")
_CANONICAL_LOGICAL_KEY_RE = re.compile(
    r"objects/sha256/([0-9a-f]{2})/([0-9a-f]{64})\Z"
)
_EXTERNAL_PREHASHED_LOGICAL_KEY_RE = re.compile(
    r"objects/external/prehashed/([a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?)/"
    r"([0-9a-f]{2})/([0-9a-f]{64})\Z"
)
_RECONCILIATION_ID_RE = re.compile(r"[0-9a-f]{24}\Z")
_APPROVAL_ID_RE = re.compile(r"approval_[0-9a-f]{32}\Z")
_MAX_APPROVAL_SUPERSESSION_DEPTH = 8
_CORE_FIELDS = ("object_id", "sha256", "logical_key", "mime", "size_bytes")
_WINDOWS_REPARSE_ATTRIBUTE = 0x400

_TerminalApprovalAuditor = Callable[
    [
        Mapping[str, Any],
        ExactHumanApprovalOperation,
        str,
        str,
        tuple[str, ...],
        Mapping[str, str] | None,
        bytes,
        str,
    ],
    bool,
]


class DuplicateObjectReconciliationError(RuntimeError):
    _CODES = {
        "duplicate_object_archive_invalid",
        "duplicate_object_manifest_missing",
        "duplicate_object_manifest_unsafe",
        "duplicate_object_manifest_too_large",
        "duplicate_object_manifest_invalid",
        "duplicate_object_manifest_changed",
        "duplicate_object_no_duplicates",
        "duplicate_object_human_resolution_required",
        "duplicate_object_plan_invalid",
        "duplicate_object_approval_required",
        "duplicate_object_reconciliation_conflict",
        "duplicate_object_reconciliation_state_unknown",
        "duplicate_object_local_evidence_changed",
        "duplicate_object_revert_candidate_missing",
        "duplicate_object_revert_candidate_ambiguous",
        "duplicate_object_revert_evidence_invalid",
        "duplicate_object_revert_plan_invalid",
        "duplicate_object_revert_approval_required",
        "duplicate_object_revert_conflict",
        "duplicate_object_revert_state_unknown",
        "archive_index_rebuild_required",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "duplicate_object_reconciliation_state_unknown"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"DuplicateObjectReconciliationError({self.code!r})"


def _fail(code: str) -> DuplicateObjectReconciliationError:
    return DuplicateObjectReconciliationError(code)


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical_bytes(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii") + b"\n"


def _is_reparse_point(value: os.stat_result) -> bool:
    return bool(
        int(getattr(value, "st_file_attributes", 0))
        & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        int(value.st_dev),
        int(value.st_ino),
        int(value.st_mode),
        int(value.st_size),
        int(value.st_mtime_ns),
        int(value.st_ctime_ns),
    )


def _open_path_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    """Identity fields comparable between Windows path and handle stat calls.

    Windows can report ``st_ctime_ns`` as creation time through a path and as
    metadata-change time through an already-open handle.  Requiring those two
    representations to match rejects an unchanged file nondeterministically.
    We still compare ctime within each observation family and use the stable
    device/inode/mode/size/mtime tuple across the path/handle boundary.
    """

    return (
        int(value.st_dev),
        int(value.st_ino),
        int(value.st_mode),
        int(value.st_size),
        int(value.st_mtime_ns),
    )


def _assert_internal_parents(root: Path, path: Path, *, create: bool) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise _fail("duplicate_object_manifest_unsafe") from None
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if create:
            try:
                current.mkdir()
            except FileExistsError:
                pass
        try:
            current_stat = os.lstat(current)
        except OSError:
            raise _fail("duplicate_object_manifest_unsafe") from None
        if (
            stat_module.S_ISLNK(current_stat.st_mode)
            or _is_reparse_point(current_stat)
            or not stat_module.S_ISDIR(current_stat.st_mode)
        ):
            raise _fail("duplicate_object_manifest_unsafe")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _safe_root(value: Path | str) -> tuple[Path, str]:
    try:
        root = Path(value).resolve(strict=True)
        root_stat = os.lstat(root)
        marker = root / "archive.yml"
        marker_stat = os.lstat(marker)
        if (
            stat_module.S_ISLNK(root_stat.st_mode)
            or _is_reparse_point(root_stat)
            or not stat_module.S_ISDIR(root_stat.st_mode)
            or stat_module.S_ISLNK(marker_stat.st_mode)
            or _is_reparse_point(marker_stat)
            or not stat_module.S_ISREG(marker_stat.st_mode)
            or marker_stat.st_size > 1024 * 1024
        ):
            raise OSError
        marker_raw = marker.read_bytes()
        if _identity(os.lstat(marker)) != _identity(marker_stat):
            raise OSError
        document = yaml.safe_load(marker_raw.decode("utf-8"))
        archive_id = document.get("archive_id") if isinstance(document, dict) else None
        if type(archive_id) is not str or not archive_id.strip():
            raise ValueError
        return root, archive_id.strip()
    except BaseException:
        raise _fail("duplicate_object_archive_invalid") from None


def _manifest_path(root: Path) -> Path:
    return root.joinpath(*MANIFEST_RELATIVE_PATH.parts)


def _read_manifest(root: Path) -> bytes:
    path = _manifest_path(root)
    _assert_internal_parents(root, path, create=False)
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        raise _fail("duplicate_object_manifest_missing") from None
    except OSError:
        raise _fail("duplicate_object_manifest_unsafe") from None
    if (
        stat_module.S_ISLNK(before.st_mode)
        or _is_reparse_point(before)
        or not stat_module.S_ISREG(before.st_mode)
        or before.st_size > MAX_MANIFEST_BYTES
    ):
        code = (
            "duplicate_object_manifest_too_large"
            if before.st_size > MAX_MANIFEST_BYTES
            else "duplicate_object_manifest_unsafe"
        )
        raise _fail(code)
    try:
        raw = path.read_bytes()
        after = os.lstat(path)
    except OSError:
        raise _fail("duplicate_object_manifest_unsafe") from None
    if _identity(before) != _identity(after):
        raise _fail("duplicate_object_manifest_changed")
    if len(raw) > MAX_MANIFEST_BYTES:
        raise _fail("duplicate_object_manifest_too_large")
    return raw


def _line_content(raw_line: bytes) -> bytes:
    if raw_line.endswith(b"\r\n"):
        return raw_line[:-2]
    if raw_line.endswith((b"\r", b"\n")):
        return raw_line[:-1]
    return raw_line


def _line_ending(raw_line: bytes) -> bytes:
    if raw_line.endswith(b"\r\n"):
        return b"\r\n"
    if raw_line.endswith(b"\n"):
        return b"\n"
    if raw_line.endswith(b"\r"):
        return b"\r"
    return b""


def _json_value_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _streamed_local_object_is_verified(
    root: Path,
    *,
    logical_key: str,
    digest: str,
    size_bytes: int,
) -> bool:
    """Prove one canonical local object without following filesystem aliases."""

    path = root.joinpath(*logical_key.split("/"))
    try:
        _assert_internal_parents(root, path, create=False)
        before = os.lstat(path)
        if (
            stat_module.S_ISLNK(before.st_mode)
            or _is_reparse_point(before)
            or not stat_module.S_ISREG(before.st_mode)
            or int(before.st_nlink) != 1
            or int(before.st_size) != size_bytes
        ):
            return False
        flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
        no_follow = int(getattr(os, "O_NOFOLLOW", 0))
        descriptor = os.open(path, flags | no_follow)
        try:
            opened_before = os.fstat(descriptor)
            if (
                _open_path_identity(opened_before) != _open_path_identity(before)
                or int(opened_before.st_nlink) != 1
            ):
                return False
            hasher = hashlib.sha256()
            observed_size = 0
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                observed_size += len(chunk)
                if observed_size > size_bytes:
                    return False
                hasher.update(chunk)
            opened_after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        after = os.lstat(path)
        return (
            _identity(before) == _identity(after)
            and _identity(opened_before) == _identity(opened_after)
            and _open_path_identity(after) == _open_path_identity(opened_after)
            and int(after.st_nlink) == 1
            and observed_size == size_bytes
            and hasher.hexdigest() == digest
        )
    except (OSError, DuplicateObjectReconciliationError):
        return False


def _strict_pair_replacement(
    root: Path,
    *,
    lines: list[bytes],
    rows: list[tuple[int, bytes, dict[str, Any]]],
    digest: str,
) -> tuple[int, int, bytes] | None:
    """Return canonical index, external index, and one lossless merged row.

    The class is intentionally narrow.  Any extra row, unsafe local file,
    malformed evidence collection, or noncanonical key keeps the group in the
    review-only inventory.
    """

    if len(rows) != 2 or lines[rows[0][0]] == lines[rows[1][0]]:
        return None
    canonical: tuple[int, bytes, dict[str, Any]] | None = None
    external: tuple[int, bytes, dict[str, Any]] | None = None
    for row in rows:
        logical_key = row[2].get("logical_key")
        if type(logical_key) is not str:
            return None
        canonical_match = _CANONICAL_LOGICAL_KEY_RE.fullmatch(logical_key)
        external_match = _EXTERNAL_PREHASHED_LOGICAL_KEY_RE.fullmatch(logical_key)
        if (
            canonical_match is not None
            and canonical_match.group(1) == digest[:2]
            and canonical_match.group(2) == digest
        ):
            if canonical is not None:
                return None
            canonical = row
        elif (
            external_match is not None
            and external_match.group(2) == digest[:2]
            and external_match.group(3) == digest
        ):
            if external is not None:
                return None
            external = row
        else:
            return None
    if canonical is None or external is None:
        return None
    canonical_document = canonical[2]
    external_document = external[2]
    canonical_locations = canonical_document.get("locations")
    external_locations = external_document.get("locations")
    if (
        canonical_document.get("size_bytes") != external_document.get("size_bytes")
        or type(canonical_locations) is not list
        or type(external_locations) is not list
        or type(canonical_document.get("provenance")) is not dict
        or type(external_document.get("provenance")) is not dict
        or PAIR_EVIDENCE_FIELD in canonical_document
        or PAIR_EVIDENCE_FIELD in external_document
        or not all(type(location) is dict for location in canonical_locations)
        or not all(type(location) is dict for location in external_locations)
    ):
        return None
    canonical_key = canonical_document["logical_key"]
    if not any(
        location.get("provider") == "local"
        and location.get("path") == canonical_key
        and location.get("availability") == "available"
        for location in canonical_locations
    ):
        return None
    size_bytes = canonical_document["size_bytes"]
    if not _streamed_local_object_is_verified(
        root,
        logical_key=canonical_key,
        digest=digest,
        size_bytes=size_bytes,
    ):
        return None

    merged_locations: list[dict[str, Any]] = []
    seen_locations: set[bytes] = set()
    for location in (*canonical_locations, *external_locations):
        encoded = _json_value_bytes(location)
        if encoded in seen_locations:
            continue
        seen_locations.add(encoded)
        merged_locations.append(dict(location))
    merged = dict(canonical_document)
    merged["locations"] = merged_locations
    merged[PAIR_EVIDENCE_FIELD] = {
        "schema_version": PAIR_EVIDENCE_SCHEMA_VERSION,
        "reconciliation_class": "canonical_local_external_prehashed_pair",
        "source_rows": [
            {
                "role": "canonical_local",
                "row_sha256": _sha256(lines[canonical[0]]),
            },
            {
                "role": "external_prehashed",
                "row_sha256": _sha256(lines[external[0]]),
            },
        ],
        "superseded_external_definition": external_document,
    }
    replacement = _json_value_bytes(merged) + _line_ending(lines[canonical[0]])
    return canonical[0], external[0], replacement


@dataclass(frozen=True, repr=False)
class _DuplicateObjectReconciliationPlan:
    archive_root: Path
    archive_id: str
    manifest_sha256: str
    plan_sha256: str
    row_count: int
    duplicate_group_count: int
    duplicate_row_count: int
    exact_group_count: int
    compatible_group_count: int
    conflicting_group_count: int
    canonical_external_pair_group_count: int
    exact_duplicate_row_group_count: int
    exact_removable_row_count: int
    removable_row_count: int
    unresolved_inventory_sha256: str
    approveable: bool
    _manifest_bytes: bytes
    _replacement_bytes: bytes
    _unresolved_inventory: Mapping[str, Any]
    _plan_basis: Mapping[str, Any]

    def public_document(self) -> dict[str, Any]:
        unresolved_group_count = (
            self.compatible_group_count + self.conflicting_group_count
        )
        if self.canonical_external_pair_group_count and unresolved_group_count:
            reason = "duplicate_object_reconciliation_ready_with_unresolved_groups"
        elif self.canonical_external_pair_group_count:
            reason = "duplicate_object_reconciliation_ready"
        elif self.approveable and unresolved_group_count:
            reason = (
                "duplicate_object_exact_reconciliation_ready_with_unresolved_groups"
            )
        elif self.approveable:
            reason = "duplicate_object_exact_reconciliation_ready"
        else:
            reason = "duplicate_object_human_resolution_required"
        next_safe_actions: list[str] = []
        if self.exact_removable_row_count:
            next_safe_actions.append("approve_exact_duplicate_row_reconciliation")
        if self.canonical_external_pair_group_count:
            next_safe_actions.append("approve_canonical_external_pair_reconciliation")
        if unresolved_group_count:
            next_safe_actions.append(
                "review_duplicate_object_evidence_without_mutation"
            )
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "ok": self.approveable,
            "reason_code": reason,
            "manifest_sha256": self.manifest_sha256,
            "plan_sha256": self.plan_sha256,
            "row_count": self.row_count,
            "duplicate_group_count": self.duplicate_group_count,
            "duplicate_row_count": self.duplicate_row_count,
            "classification_counts": {
                "exact_byte_duplicate": self.exact_group_count,
                "compatible_repeated_evidence": self.compatible_group_count,
                "conflicting_definition": self.conflicting_group_count,
                "canonical_local_external_prehashed_pair": (
                    self.canonical_external_pair_group_count
                ),
            },
            "exact_duplicate_row_group_count": (
                self.exact_duplicate_row_group_count
            ),
            "removable_row_count": self.removable_row_count,
            "exact_duplicate_row_count_removable": self.exact_removable_row_count,
            "canonical_external_pair_group_count": (
                self.canonical_external_pair_group_count
            ),
            "unresolved_group_count": unresolved_group_count,
            "human_resolution_still_required": bool(unresolved_group_count),
            "unresolved_inventory": {
                "schema_version": UNRESOLVED_INVENTORY_SCHEMA_VERSION,
                "group_count": unresolved_group_count,
                "inventory_sha256": self.unresolved_inventory_sha256,
                "object_ids_echoed": False,
                "paths_echoed": False,
                "row_content_echoed": False,
            },
            "automatic_merge_permitted": False,
            "strict_human_approved_pair_reconciliation_permitted": bool(
                self.canonical_external_pair_group_count
            ),
            "exact_row_deduplication_permitted": bool(
                self.exact_removable_row_count
            ),
            "requires_exact_human_approval": True,
            "object_ids_echoed": False,
            "paths_echoed": False,
            "row_content_echoed": False,
            "next_safe_actions": next_safe_actions,
        }


def _plan_duplicate_object_reconciliation_core(
    archive_root: Path | str,
    *,
    _manifest_override: bytes | None = None,
    terminal_auditor: _TerminalApprovalAuditor | None = None,
) -> _DuplicateObjectReconciliationPlan:
    root, archive_id = _safe_root(archive_root)
    manifest = (
        _read_manifest(root)
        if _manifest_override is None
        else _manifest_override
    )
    if type(manifest) is not bytes or len(manifest) > MAX_MANIFEST_BYTES:
        raise _fail("duplicate_object_manifest_too_large")
    lines = manifest.splitlines(keepends=True)
    if len(lines) > MAX_MANIFEST_ROWS:
        raise _fail("duplicate_object_manifest_too_large")

    groups: dict[str, list[tuple[int, bytes, dict[str, Any]]]] = {}
    nonempty_count = 0
    try:
        for index, raw_line in enumerate(lines):
            content = _line_content(raw_line)
            if not content.strip():
                continue
            nonempty_count += 1
            document = json.loads(
                content.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs
            )
            if not isinstance(document, dict):
                raise ValueError
            object_id = document.get("object_id")
            match = _OBJECT_ID_RE.fullmatch(str(object_id or ""))
            if match is None:
                raise ValueError
            sha = document.get("sha256")
            sha_match = _SHA256_RE.fullmatch(str(sha or ""))
            if sha_match is None or sha_match.group(1) != match.group(1):
                raise ValueError
            if (
                type(document.get("logical_key")) is not str
                or type(document.get("mime")) is not str
                or type(document.get("size_bytes")) is not int
                or document["size_bytes"] < 0
            ):
                raise ValueError
            row = (index, content, document)
            groups.setdefault(object_id, []).append(row)
    except (UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        raise _fail("duplicate_object_manifest_invalid") from None

    duplicate_groups = [
        (object_id, rows) for object_id, rows in groups.items() if len(rows) > 1
    ]
    if not duplicate_groups:
        raise _fail("duplicate_object_no_duplicates")

    exact = compatible = conflicting = 0
    exact_removable = canonical_external_pairs = 0
    exact_duplicate_row_groups = 0
    remove_indexes: set[int] = set()
    replace_indexes: dict[int, bytes] = {}
    duplicate_rows = 0
    unresolved_metrics: dict[str, dict[str, Any]] = {
        "compatible_repeated_evidence": {
            "group_count": 0,
            "row_count_before": 0,
            "row_count_after_exact_deduplication": 0,
            "exact_duplicate_row_count_removed": 0,
            "group_sequence_hasher": hashlib.sha256(),
        },
        "conflicting_definition": {
            "group_count": 0,
            "row_count_before": 0,
            "row_count_after_exact_deduplication": 0,
            "exact_duplicate_row_count_removed": 0,
            "group_sequence_hasher": hashlib.sha256(),
        },
    }
    for object_id, rows in duplicate_groups:
        duplicate_rows += len(rows) - 1
        unique_rows: list[tuple[int, bytes, dict[str, Any]]] = []
        seen_row_bytes: set[bytes] = set()
        removed_in_group = 0
        for row in rows:
            raw_line = lines[row[0]]
            if raw_line in seen_row_bytes:
                remove_indexes.add(row[0])
                exact_removable += 1
                removed_in_group += 1
                continue
            seen_row_bytes.add(raw_line)
            unique_rows.append(row)
        if removed_in_group:
            exact_duplicate_row_groups += 1
        if len(unique_rows) == 1:
            exact += 1
            continue
        # Never reinterpret an A,A,B group as a two-row pair.  The exact A
        # cleanup remains available, while A/B stays explicitly unresolved.
        pair = (
            _strict_pair_replacement(
                root,
                lines=lines,
                rows=unique_rows,
                digest=object_id.removeprefix("sha256:"),
            )
            if len(rows) == 2
            else None
        )
        if pair is not None:
            canonical_index, external_index, replacement_line = pair
            canonical_external_pairs += 1
            remove_indexes.add(external_index)
            replace_indexes[canonical_index] = replacement_line
            continue
        first_core = tuple(
            unique_rows[0][2].get(field) for field in _CORE_FIELDS
        )
        if all(
            tuple(row[2].get(field) for field in _CORE_FIELDS) == first_core
            for row in unique_rows[1:]
        ):
            compatible += 1
            classification = "compatible_repeated_evidence"
        else:
            conflicting += 1
            classification = "conflicting_definition"

        metrics = unresolved_metrics[classification]
        metrics["group_count"] += 1
        metrics["row_count_before"] += len(rows)
        metrics["row_count_after_exact_deduplication"] += len(unique_rows)
        metrics["exact_duplicate_row_count_removed"] += removed_in_group
        group_ref = _sha256(
            b"wom-kit/duplicate-object-unresolved-group/v0.1\0"
            + object_id.encode("ascii")
        )
        metrics["group_sequence_hasher"].update(group_ref.encode("ascii") + b"\n")

    removable = exact_removable + canonical_external_pairs
    approveable = removable > 0
    replacement = b"".join(
        replace_indexes.get(index, raw_line)
        for index, raw_line in enumerate(lines)
        if index not in remove_indexes
    )
    manifest_sha = _sha256(manifest)
    inventory_rows: list[dict[str, Any]] = []
    for classification in (
        "compatible_repeated_evidence",
        "conflicting_definition",
    ):
        metrics = unresolved_metrics[classification]
        inventory_rows.append(
            {
                "classification": classification,
                "group_count": metrics["group_count"],
                "row_count_before": metrics["row_count_before"],
                "row_count_after_exact_deduplication": metrics[
                    "row_count_after_exact_deduplication"
                ],
                "exact_duplicate_row_count_removed": metrics[
                    "exact_duplicate_row_count_removed"
                ],
                "group_sequence_sha256": (
                    "sha256:" + metrics["group_sequence_hasher"].hexdigest()
                ),
            }
        )
    unresolved_inventory_basis = {
        "schema_version": UNRESOLVED_INVENTORY_SCHEMA_VERSION,
        "unresolved_group_count": compatible + conflicting,
        "classification_groups": inventory_rows,
        "object_ids_stored": False,
        "paths_stored": False,
        "row_content_stored": False,
    }
    unresolved_inventory_sha = _sha256(
        _canonical_bytes(unresolved_inventory_basis)
    )
    unresolved_inventory = {
        **unresolved_inventory_basis,
        "inventory_sha256": unresolved_inventory_sha,
    }
    plan_basis = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "archive_identity_sha256": exact_human_approval_archive_identity_sha256(
            archive_id
        ),
        "manifest_sha256": manifest_sha,
        "replacement_sha256": _sha256(replacement),
        "row_count": nonempty_count,
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_row_count": duplicate_rows,
        "exact_group_count": exact,
        "compatible_group_count": compatible,
        "conflicting_group_count": conflicting,
        "canonical_external_pair_group_count": canonical_external_pairs,
        "exact_duplicate_row_group_count": exact_duplicate_row_groups,
        "exact_removable_row_count": exact_removable,
        "removable_row_count": removable,
        "unresolved_inventory_sha256": unresolved_inventory_sha,
    }
    plan_sha = _sha256(_canonical_bytes(plan_basis))
    plan = _DuplicateObjectReconciliationPlan(
        archive_root=root,
        archive_id=archive_id,
        manifest_sha256=manifest_sha,
        plan_sha256=plan_sha,
        row_count=nonempty_count,
        duplicate_group_count=len(duplicate_groups),
        duplicate_row_count=duplicate_rows,
        exact_group_count=exact,
        compatible_group_count=compatible,
        conflicting_group_count=conflicting,
        canonical_external_pair_group_count=canonical_external_pairs,
        exact_duplicate_row_group_count=exact_duplicate_row_groups,
        exact_removable_row_count=exact_removable,
        removable_row_count=removable,
        unresolved_inventory_sha256=unresolved_inventory_sha,
        approveable=approveable,
        _manifest_bytes=manifest,
        _replacement_bytes=replacement,
        _unresolved_inventory=unresolved_inventory,
        _plan_basis=plan_basis,
    )
    _assert_forward_not_terminal_compensated(
        root,
        plan,
        terminal_auditor=terminal_auditor,
    )
    return plan


def plan_duplicate_object_reconciliation(
    archive_root: Path | str,
) -> dict[str, Any]:
    """Return only the content-free public projection of a private plan."""

    return _plan_duplicate_object_reconciliation_core(
        archive_root
    ).public_document()


def _duplicate_object_reconciliation_context(
    plan: _DuplicateObjectReconciliationPlan,
    *,
    reviewer_claim: str,
) -> ExactHumanApprovalContext:
    if type(plan) is not _DuplicateObjectReconciliationPlan:
        raise _fail("duplicate_object_plan_invalid")
    return ExactHumanApprovalContext(
        operation=ExactHumanApprovalOperation.duplicate_object_reconcile,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(
            plan.archive_id
        ),
        plan_sha256=plan.plan_sha256,
        target_binding_sha256=plan.manifest_sha256,
        reviewer_claim=reviewer_claim,
        review_binding_codes=(
            "canonical_external_pair_local_byte_proof",
            "duplicate_classification_counts",
            "manifest_digest",
            "replacement_digest",
            "unresolved_duplicate_inventory",
        ),
    )


def _create_only(root: Path, path: Path, raw: bytes) -> None:
    _assert_internal_parents(root, path, create=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _atomic_replace(root: Path, path: Path, raw: bytes) -> None:
    _assert_internal_parents(root, path, create=False)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".duplicate-reconcile-", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _replace_manifest_compare_and_swap(
    root: Path,
    *,
    expected_bytes: bytes,
    replacement_bytes: bytes,
    transaction_sha256: str,
    swap_suffix: str,
    error_prefix: str,
) -> None:
    """Replace the object manifest through the shared index-aware CAS primitive.

    Keeping this narrow wrapper local gives interruption tests a stable seam while
    preserving the shared compare-and-swap and regular-file safety contract.
    """

    archive_services._replace_regular_file_bytes_compare_and_swap(
        root,
        _manifest_path(root),
        expected_bytes=expected_bytes,
        replacement_bytes=replacement_bytes,
        transaction_sha256=transaction_sha256,
        swap_suffix=swap_suffix,
        max_bytes=MAX_MANIFEST_BYTES,
        error_prefix=error_prefix,
    )


def _read_safe_internal_file(
    root: Path,
    path: Path,
    *,
    maximum_bytes: int,
) -> bytes:
    try:
        _assert_internal_parents(root, path, create=False)
        before = os.lstat(path)
        if (
            stat_module.S_ISLNK(before.st_mode)
            or _is_reparse_point(before)
            or not stat_module.S_ISREG(before.st_mode)
            or int(before.st_nlink) != 1
            or int(before.st_size) > maximum_bytes
        ):
            raise OSError
        raw = path.read_bytes()
        after = os.lstat(path)
        if _identity(before) != _identity(after) or len(raw) > maximum_bytes:
            raise OSError
        return raw
    except (OSError, DuplicateObjectReconciliationError):
        raise _fail("duplicate_object_revert_evidence_invalid") from None


def _strict_json_document(raw: bytes) -> dict[str, Any]:
    try:
        document = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs
        )
    except (UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        raise _fail("duplicate_object_revert_evidence_invalid") from None
    if type(document) is not dict:
        raise _fail("duplicate_object_revert_evidence_invalid")
    return document


def _approval_reference_is_exact(value: Any) -> bool:
    return bool(
        type(value) is dict
        and set(value) == {
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


def _terminal_authentication_document(mac: str) -> dict[str, Any]:
    return {
        "schema_version": TERMINAL_AUTHENTICATION_SCHEMA_VERSION,
        "algorithm": "hmac-sha256",
        "mac": mac,
    }


def _terminal_authentication_mac(value: Any) -> str | None:
    if (
        type(value) is not dict
        or set(value) != {"schema_version", "algorithm", "mac"}
        or value.get("schema_version")
        != TERMINAL_AUTHENTICATION_SCHEMA_VERSION
        or value.get("algorithm") != "hmac-sha256"
        or type(value.get("mac")) is not str
        or re.fullmatch(r"hmac-sha256:[0-9a-f]{64}", value["mac"])
        is None
    ):
        return None
    return value["mac"]


def _revert_finalization_evidence_digests(
    value: Any,
) -> dict[str, str] | None:
    digest_fields = {
        "approval_reference_sha256",
        "claim_receipt_sha256",
        "claim_mac_sha256",
    }
    if (
        type(value) is not dict
        or set(value) != {"schema_version", *digest_fields}
        or value.get("schema_version")
        != REVERT_FINALIZATION_EVIDENCE_SCHEMA_VERSION
        or any(
            type(value.get(field)) is not str
            or _SHA256_RE.fullmatch(value[field]) is None
            for field in digest_fields
        )
    ):
        return None
    return {field: value[field] for field in sorted(digest_fields)}


def _terminal_record_is_authenticated(
    document: Mapping[str, Any],
    *,
    terminal_auditor: _TerminalApprovalAuditor | None,
    reference: Mapping[str, Any],
    expected_plan_sha256: str,
    expected_target_binding_sha256: str,
    allowed_statuses: tuple[str, ...],
    succeeded_evidence: Mapping[str, str] | None,
) -> bool:
    authentication = document.get("terminal_authentication")
    mac = _terminal_authentication_mac(authentication)
    if mac is None or terminal_auditor is None:
        return False
    payload_document = dict(document)
    payload_document.pop("terminal_authentication", None)
    try:
        return terminal_auditor(
            reference,
            ExactHumanApprovalOperation.duplicate_object_reconcile,
            expected_plan_sha256,
            expected_target_binding_sha256,
            allowed_statuses,
            succeeded_evidence,
            _canonical_bytes(payload_document),
            mac,
        ) is True
    except BaseException:
        return False


def _claim_terminal_auditor(
    claim: _ClaimedExactHumanApproval,
) -> _TerminalApprovalAuditor:
    def _audit(
        reference: Mapping[str, Any],
        expected_operation: ExactHumanApprovalOperation,
        expected_plan_sha256: str,
        expected_target_binding_sha256: str,
        allowed_statuses: tuple[str, ...],
        succeeded_evidence: Mapping[str, str] | None,
        payload: bytes,
        expected_mac: str,
    ) -> bool:
        return claim.exact_terminal_record_matches(
            reference,
            expected_operation,
            expected_plan_sha256,
            expected_target_binding_sha256,
            allowed_statuses,
            succeeded_evidence,
            payload,
            expected_mac,
        )

    return _audit


def _production_terminal_auditor(root: Path) -> _TerminalApprovalAuditor:
    """Use the established archive key read-only only when evidence needs it."""

    def _audit(
        reference: Mapping[str, Any],
        expected_operation: ExactHumanApprovalOperation,
        expected_plan_sha256: str,
        expected_target_binding_sha256: str,
        allowed_statuses: tuple[str, ...],
        succeeded_evidence: Mapping[str, str] | None,
        payload: bytes,
        expected_mac: str,
    ) -> bool:
        try:
            from .credential_secure_intake_windows import (
                _CtypesWindowsNativeFacade,
            )
            from .credential_secure_registry import (
                _StableArchiveFingerprintKeyProvider,
            )

            provider = _StableArchiveFingerprintKeyProvider(
                _CtypesWindowsNativeFacade(cli_live_approved=True)
            )
            return bool(
                provider.use_key(
                    root,
                    lambda key: _audit_exact_human_approval_terminal_record_core(
                        root,
                        reference,
                        expected_operation=expected_operation,
                        expected_plan_sha256=expected_plan_sha256,
                        expected_target_binding_sha256=(
                            expected_target_binding_sha256
                        ),
                        allowed_statuses=allowed_statuses,
                        expected_succeeded_evidence_digests=(
                            succeeded_evidence
                        ),
                        payload=payload,
                        expected_mac=expected_mac,
                        receipt_authentication_key=key,
                    ),
                    create_if_missing=False,
                )
            )
        except BaseException:
            return False

    return _audit


def _forward_receipt_document(
    plan: _DuplicateObjectReconciliationPlan,
    *,
    reconciliation_id: str,
    approval_reference: Mapping[str, Any],
    approval_supersession: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    document = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "reconciliation_id": reconciliation_id,
        "plan_sha256": plan.plan_sha256,
        "manifest_before_sha256": plan.manifest_sha256,
        "manifest_after_sha256": _sha256(plan._replacement_bytes),
        "removed_exact_duplicate_row_count": plan.exact_removable_row_count,
        "reconciled_canonical_external_pair_count": (
            plan.canonical_external_pair_group_count
        ),
        "compatible_group_count": plan.compatible_group_count,
        "conflicting_group_count": plan.conflicting_group_count,
        "unresolved_group_count": (
            plan.compatible_group_count + plan.conflicting_group_count
        ),
        "human_resolution_still_required": bool(
            plan.compatible_group_count + plan.conflicting_group_count
        ),
        "unresolved_inventory": dict(plan._unresolved_inventory),
        "approval_reference": dict(approval_reference),
        "snapshot_preserved": True,
        "automatic_merge_performed": False,
        "strict_human_approved_pair_reconciliation_performed": bool(
            plan.canonical_external_pair_group_count
        ),
        "unresolved_distinct_rows_modified": False,
        "object_ids_stored_in_receipt": False,
        "paths_echoed_in_public_result": False,
    }
    if approval_supersession is not None:
        document["approval_supersession_sha256"] = _sha256(
            _canonical_bytes(approval_supersession)
        )
    return document


@dataclass(frozen=True, repr=False)
class _DuplicateObjectReconciliationRevertPlan:
    archive_root: Path
    archive_id: str
    plan_sha256: str
    manifest_current_sha256: str
    manifest_restore_sha256: str
    source_evidence_kind: str
    source_evidence_sha256: str
    source_journal_sha256: str
    source_receipt_sha256: str | None
    removed_exact_duplicate_row_count: int
    reconciled_canonical_external_pair_count: int
    _manifest_current_bytes: bytes
    _manifest_restore_bytes: bytes
    _source_reconciliation_id: str
    _source_receipt_bytes: bytes | None
    _source_journal_bytes: bytes

    def public_document(self) -> dict[str, Any]:
        return {
            "schema_version": REVERT_PLAN_SCHEMA_VERSION,
            "ok": True,
            "reason_code": "duplicate_object_exact_revert_ready",
            "plan_sha256": self.plan_sha256,
            "manifest_current_sha256": self.manifest_current_sha256,
            "manifest_restore_sha256": self.manifest_restore_sha256,
            "source_evidence_kind": self.source_evidence_kind,
            "source_evidence_sha256": self.source_evidence_sha256,
            "source_journal_sha256": self.source_journal_sha256,
            "source_receipt_sha256": self.source_receipt_sha256,
            "source_change_counts": {
                "exact_duplicate_rows_removed": (
                    self.removed_exact_duplicate_row_count
                ),
                "canonical_external_pairs_reconciled": (
                    self.reconciled_canonical_external_pair_count
                ),
            },
            "candidate_count": 1,
            "restores_whole_manifest_exact_bytes": True,
            "requires_exact_human_approval": True,
            "object_ids_echoed": False,
            "paths_echoed": False,
            "row_content_echoed": False,
        }


def _safe_json_paths(
    root: Path,
    *,
    relative_directory: PurePosixPath,
) -> list[Path]:
    directory = root.joinpath(*relative_directory.parts)
    try:
        directory_stat = os.lstat(directory)
    except FileNotFoundError:
        return []
    except OSError:
        raise _fail("duplicate_object_revert_evidence_invalid") from None
    try:
        _assert_internal_parents(root, directory / "candidate", create=False)
        directory_after = os.lstat(directory)
    except (OSError, DuplicateObjectReconciliationError):
        raise _fail("duplicate_object_revert_evidence_invalid") from None
    if (
        _identity(directory_stat) != _identity(directory_after)
        or
        stat_module.S_ISLNK(directory_stat.st_mode)
        or _is_reparse_point(directory_stat)
        or not stat_module.S_ISDIR(directory_stat.st_mode)
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    paths: list[Path] = []
    try:
        entries = sorted(os.scandir(directory), key=lambda item: item.name)
    except OSError:
        raise _fail("duplicate_object_revert_evidence_invalid") from None
    if len(entries) > MAX_RECONCILIATION_RECEIPTS:
        raise _fail("duplicate_object_revert_evidence_invalid")
    for entry in entries:
        try:
            entry_stat = entry.stat(follow_symlinks=False)
        except OSError:
            raise _fail("duplicate_object_revert_evidence_invalid") from None
        if entry.is_symlink() or _is_reparse_point(entry_stat):
            raise _fail("duplicate_object_revert_evidence_invalid")
        if not entry.name.endswith(".json"):
            continue
        if not stat_module.S_ISREG(entry_stat.st_mode):
            raise _fail("duplicate_object_revert_evidence_invalid")
        paths.append(Path(entry.path))
    return paths


def _safe_receipt_paths(root: Path) -> list[Path]:
    return _safe_json_paths(root, relative_directory=RECEIPT_ROOT)


def _safe_journal_paths(root: Path) -> list[Path]:
    return _safe_json_paths(root, relative_directory=JOURNAL_ROOT)


def _safe_revert_journal_paths(root: Path) -> list[Path]:
    return _safe_json_paths(root, relative_directory=REVERT_JOURNAL_ROOT)


def _terminal_compensation_path(
    root: Path,
    plan_sha256: str,
) -> Path:
    return root.joinpath(
        *TERMINAL_COMPENSATION_ROOT.parts,
        f"{plan_sha256.removeprefix('sha256:')[:24]}.json",
    )


def _assert_forward_not_terminal_compensated(
    root: Path,
    plan: _DuplicateObjectReconciliationPlan,
    *,
    terminal_auditor: _TerminalApprovalAuditor | None = None,
) -> None:
    try:
        marker_path = _terminal_compensation_path(root, plan.plan_sha256)
        marker_raw = _optional_safe_internal_file(
            root, marker_path, maximum_bytes=MAX_RECEIPT_BYTES
        )
        if marker_raw is None:
            _assert_no_surviving_terminal_compensation_history(
                root,
                plan,
                terminal_auditor=terminal_auditor,
            )
            return
        marker = _strict_json_document(marker_raw)
        expected_keys = {
            "schema_version",
            "source_plan_sha256",
            "source_journal_sha256",
            "source_evidence_sha256",
            "revert_plan_sha256",
            "revert_started_journal_sha256",
            "revert_receipt_sha256",
            "restored_manifest_sha256",
        }
        if (
            _canonical_bytes(marker) != marker_raw
            or set(marker) != expected_keys
            or marker.get("schema_version")
            != TERMINAL_COMPENSATION_SCHEMA_VERSION
            or marker.get("source_plan_sha256") != plan.plan_sha256
            or marker.get("restored_manifest_sha256") != plan.manifest_sha256
            or any(
                type(marker.get(field)) is not str
                or _SHA256_RE.fullmatch(marker[field]) is None
                for field in expected_keys
                - {
                    "schema_version",
                    "source_plan_sha256",
                    "restored_manifest_sha256",
                }
            )
        ):
            raise _fail("duplicate_object_reconciliation_conflict")
        source_journal_path = root.joinpath(
            *JOURNAL_ROOT.parts,
            f"{plan.plan_sha256.removeprefix('sha256:')[:24]}.json",
        )
        source_journal_raw = _read_safe_internal_file(
            root, source_journal_path, maximum_bytes=MAX_RECEIPT_BYTES
        )
        if _sha256(source_journal_raw) != marker["source_journal_sha256"]:
            raise _fail("duplicate_object_reconciliation_conflict")
    except DuplicateObjectReconciliationError:
        raise _fail("duplicate_object_reconciliation_conflict") from None
    raise _fail("duplicate_object_reconciliation_conflict")


def _assert_no_surviving_terminal_compensation_history(
    root: Path,
    plan: _DuplicateObjectReconciliationPlan,
    *,
    terminal_auditor: _TerminalApprovalAuditor | None = None,
) -> None:
    """Reject an exact replay even if its private terminal marker vanished.

    The marker is an acceleration/index record, not the sole authority.  A
    completed (or post-restore finalize-only) emergency revert still leaves a
    fully validated revert journal, receipt, snapshots, and the interrupted
    source journal.  Reconstruct and validate that durable chain before
    deciding that an absent marker means the forward operation is new.
    """

    source_reconciliation_id = plan.plan_sha256.removeprefix("sha256:")[:24]
    source_journal_path = root.joinpath(
        *JOURNAL_ROOT.parts,
        f"{source_reconciliation_id}.json",
    )
    try:
        source_journal_raw = _optional_safe_internal_file(
            root,
            source_journal_path,
            maximum_bytes=MAX_RECEIPT_BYTES,
        )
        source_journal_sha256 = (
            _sha256(source_journal_raw)
            if source_journal_raw is not None
            else None
        )
        for revert_journal_path in _safe_revert_journal_paths(root):
            journal_raw_before = _read_safe_internal_file(
                root,
                revert_journal_path,
                maximum_bytes=MAX_RECEIPT_BYTES,
            )
            journal = _strict_json_document(journal_raw_before)
            if _canonical_bytes(journal) != journal_raw_before:
                raise _fail("duplicate_object_reconciliation_conflict")

            # First select only history that names this exact source journal.
            # Fully replaying every unrelated historical snapshot would turn
            # a bounded lookup into O(history * manifest_size), and would make
            # one old terminal record prevent a distinct later operation.
            matching_source_id = (
                journal.get("source_reconciliation_id")
                == source_reconciliation_id
            )
            matching_source_digest = (
                source_journal_sha256 is not None
                and journal.get("source_journal_sha256")
                == source_journal_sha256
            )
            if not matching_source_id and not matching_source_digest:
                continue
            if journal.get("source_evidence_kind") not in {
                "interrupted_started_journal",
                "interrupted_receipt_published",
            }:
                raise _fail("duplicate_object_reconciliation_conflict")

            # This performs the complete receipt/snapshot/source/journal
            # validation.  A terminal journal returns no retry candidate, but
            # validation still has to succeed before it may block a replay.
            _revert_plan_from_execution_journal(
                root,
                journal_path=revert_journal_path,
                current_manifest=plan._manifest_bytes,
                terminal_auditor=terminal_auditor,
            )
            journal_raw_after = _read_safe_internal_file(
                root,
                revert_journal_path,
                maximum_bytes=MAX_RECEIPT_BYTES,
            )
            if journal_raw_after != journal_raw_before:
                raise _fail("duplicate_object_reconciliation_conflict")

            if source_journal_raw is None:
                raise _fail("duplicate_object_reconciliation_conflict")
            source_journal_raw_before = source_journal_raw
            source_journal = _strict_json_document(source_journal_raw_before)
            source_journal_raw_after = _read_safe_internal_file(
                root,
                source_journal_path,
                maximum_bytes=MAX_RECEIPT_BYTES,
            )
            if source_journal_raw_after != source_journal_raw_before:
                raise _fail("duplicate_object_reconciliation_conflict")
            if (
                source_journal.get("plan_sha256") == plan.plan_sha256
                and journal.get("source_journal_sha256")
                == _sha256(source_journal_raw_before)
                and journal.get("manifest_after_revert_sha256")
                == plan.manifest_sha256
            ):
                raise _fail("duplicate_object_reconciliation_conflict")
    except DuplicateObjectReconciliationError:
        raise _fail("duplicate_object_reconciliation_conflict") from None


def _build_revert_plan(
    root: Path,
    *,
    current_manifest: bytes,
    snapshot_raw: bytes,
    reconciliation_id: str,
    journal_raw: bytes,
    receipt_raw: bytes | None,
    source_evidence_kind: str,
    exact_removed: int,
    pair_count: int,
) -> _DuplicateObjectReconciliationRevertPlan:
    archive_id = _safe_root(root)[1]
    before_sha = _sha256(snapshot_raw)
    after_sha = _sha256(current_manifest)
    journal_sha = _sha256(journal_raw)
    receipt_sha = _sha256(receipt_raw) if receipt_raw is not None else None
    if source_evidence_kind == "successful_receipt":
        if receipt_sha is None:
            raise _fail("duplicate_object_revert_evidence_invalid")
        source_evidence_sha = receipt_sha
    else:
        source_evidence_sha = _sha256(
            _canonical_bytes(
                {
                    "schema_version": (
                        "wom-kit/duplicate-object-interrupted-evidence/v0.1"
                    ),
                    "journal_sha256": journal_sha,
                    "receipt_sha256": receipt_sha,
                }
            )
        )
    plan_basis = {
        "schema_version": REVERT_PLAN_SCHEMA_VERSION,
        "archive_identity_sha256": exact_human_approval_archive_identity_sha256(
            archive_id
        ),
        "manifest_current_sha256": after_sha,
        "manifest_restore_sha256": before_sha,
        "source_evidence_kind": source_evidence_kind,
        "source_evidence_sha256": source_evidence_sha,
        "source_journal_sha256": journal_sha,
        "source_receipt_sha256": receipt_sha,
        "removed_exact_duplicate_row_count": exact_removed,
        "reconciled_canonical_external_pair_count": pair_count,
    }
    revert_plan_sha = _sha256(_canonical_bytes(plan_basis))
    return _DuplicateObjectReconciliationRevertPlan(
        archive_root=root,
        archive_id=archive_id,
        plan_sha256=revert_plan_sha,
        manifest_current_sha256=after_sha,
        manifest_restore_sha256=before_sha,
        source_evidence_kind=source_evidence_kind,
        source_evidence_sha256=source_evidence_sha,
        source_journal_sha256=journal_sha,
        source_receipt_sha256=receipt_sha,
        removed_exact_duplicate_row_count=exact_removed,
        reconciled_canonical_external_pair_count=pair_count,
        _manifest_current_bytes=current_manifest,
        _manifest_restore_bytes=snapshot_raw,
        _source_reconciliation_id=reconciliation_id,
        _source_receipt_bytes=receipt_raw,
        _source_journal_bytes=journal_raw,
    )


def _validated_revert_candidate(
    root: Path,
    *,
    receipt_path: Path,
    current_manifest: bytes,
    terminal_auditor: _TerminalApprovalAuditor | None = None,
) -> _DuplicateObjectReconciliationRevertPlan | None:
    receipt_raw = _read_safe_internal_file(
        root, receipt_path, maximum_bytes=MAX_RECEIPT_BYTES
    )
    receipt = _strict_json_document(receipt_raw)
    reconcile_id = receipt.get("reconciliation_id")
    before_sha = receipt.get("manifest_before_sha256")
    after_sha = receipt.get("manifest_after_sha256")
    plan_sha = receipt.get("plan_sha256")
    exact_removed = receipt.get("removed_exact_duplicate_row_count")
    pair_count = receipt.get("reconciled_canonical_external_pair_count", 0)
    if (
        receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION
        or receipt_path.stem != reconcile_id
        or type(reconcile_id) is not str
        or _RECONCILIATION_ID_RE.fullmatch(reconcile_id) is None
        or type(plan_sha) is not str
        or _SHA256_RE.fullmatch(plan_sha) is None
        or reconcile_id
        != plan_sha.removeprefix("sha256:")[:24]
        or type(before_sha) is not str
        or _SHA256_RE.fullmatch(before_sha) is None
        or type(after_sha) is not str
        or _SHA256_RE.fullmatch(after_sha) is None
        or type(exact_removed) is not int
        or exact_removed < 0
        or type(pair_count) is not int
        or pair_count < 0
        or exact_removed + pair_count <= 0
        or receipt.get("snapshot_preserved") is not True
        or not _approval_reference_is_exact(receipt.get("approval_reference"))
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    snapshot_path = root.joinpath(
        *SNAPSHOT_ROOT.parts, f"{reconcile_id}.manifest.bin"
    )
    journal_path = root.joinpath(*JOURNAL_ROOT.parts, f"{reconcile_id}.json")
    snapshot_raw = _read_safe_internal_file(
        root, snapshot_path, maximum_bytes=MAX_MANIFEST_BYTES
    )
    journal_raw = _read_safe_internal_file(
        root, journal_path, maximum_bytes=MAX_RECEIPT_BYTES
    )
    journal = _strict_json_document(journal_raw)
    journal_base_invalid = bool(
        _sha256(snapshot_raw) != before_sha
        or journal.get("schema_version") != JOURNAL_SCHEMA_VERSION
        or journal.get("reconciliation_id") != reconcile_id
        or journal.get("plan_sha256") != plan_sha
        or journal.get("manifest_before_sha256") != before_sha
        or journal.get("manifest_after_sha256") != after_sha
        or journal.get("snapshot_created") is not True
        or not _approval_reference_is_exact(journal.get("approval_reference"))
        or journal.get("approval_reference") != receipt.get("approval_reference")
    )
    if journal_base_invalid:
        raise _fail("duplicate_object_revert_evidence_invalid")
    plan_basis = _validated_interrupted_plan_basis(root=root, journal=journal)
    if (
        not _interrupted_receipt_is_exact(
            receipt_raw,
            journal=journal,
            plan_basis=plan_basis,
        )
        or exact_removed != plan_basis.get("exact_removable_row_count")
        or pair_count
        != plan_basis.get("canonical_external_pair_group_count")
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    forward_journal_base_keys = {
        "schema_version",
        "reconciliation_id",
        "plan_sha256",
        "manifest_before_sha256",
        "manifest_after_sha256",
        "unresolved_inventory_sha256",
        "plan_basis",
        "approval_reference",
        "status",
        "snapshot_created",
        "manifest_replaced",
        "receipt_created",
    }
    if journal.get("status") == "started":
        if (
            journal.get("manifest_replaced") is not False
            or journal.get("receipt_created") is not False
            or "receipt_sha256" in journal
        ):
            raise _fail("duplicate_object_revert_evidence_invalid")
        # The interrupted-journal validator below independently reconstructs
        # and binds this receipt, snapshot, and exact replacement.
        return None
    if journal.get("status") == "rolled_back":
        if _sha256(current_manifest) == after_sha:
            raise _fail("duplicate_object_revert_evidence_invalid")
        return None
    if (
        journal.get("status") != "succeeded"
        or journal.get("manifest_replaced") is not True
        or journal.get("receipt_created") is not True
        or journal.get("receipt_sha256") != _sha256(receipt_raw)
        or _canonical_bytes(journal) != journal_raw
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    expected_succeeded_keys = forward_journal_base_keys | {
        "receipt_sha256",
        "terminal_authentication",
    }
    supersession = journal.get("approval_supersession")
    if supersession is not None:
        expected_succeeded_keys.add("approval_supersession")
    if (
        set(journal) != expected_succeeded_keys
        or (
            supersession is not None
            and not _approval_supersession_is_exact(
                supersession,
                manifest_sha256=before_sha,
                replacement_reference=journal["approval_reference"],
                require_superseded_journal_evidence=True,
                forward_journal_context=_forward_journal_binding_context(
                    journal
                ),
            )
        )
        or not _terminal_record_is_authenticated(
            journal,
            terminal_auditor=terminal_auditor,
            reference=journal["approval_reference"],
            expected_plan_sha256=plan_sha,
            expected_target_binding_sha256=before_sha,
            allowed_statuses=("started", "succeeded"),
            succeeded_evidence=None,
        )
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    if _sha256(current_manifest) != after_sha:
        return None
    return _build_revert_plan(
        root,
        current_manifest=current_manifest,
        snapshot_raw=snapshot_raw,
        reconciliation_id=reconcile_id,
        journal_raw=journal_raw,
        receipt_raw=receipt_raw,
        source_evidence_kind="successful_receipt",
        exact_removed=exact_removed,
        pair_count=pair_count,
    )


def _validated_interrupted_plan_basis(
    *,
    root: Path,
    journal: Mapping[str, Any],
) -> Mapping[str, Any]:
    basis = journal.get("plan_basis")
    expected_keys = {
        "schema_version",
        "archive_identity_sha256",
        "manifest_sha256",
        "replacement_sha256",
        "row_count",
        "duplicate_group_count",
        "duplicate_row_count",
        "exact_group_count",
        "compatible_group_count",
        "conflicting_group_count",
        "canonical_external_pair_group_count",
        "exact_duplicate_row_group_count",
        "exact_removable_row_count",
        "removable_row_count",
        "unresolved_inventory_sha256",
    }
    integer_fields = expected_keys - {
        "schema_version",
        "archive_identity_sha256",
        "manifest_sha256",
        "replacement_sha256",
        "unresolved_inventory_sha256",
    }
    if (
        type(basis) is not dict
        or set(basis) != expected_keys
        or basis.get("schema_version") != PLAN_SCHEMA_VERSION
        or basis.get("archive_identity_sha256")
        != exact_human_approval_archive_identity_sha256(_safe_root(root)[1])
        or basis.get("manifest_sha256")
        != journal.get("manifest_before_sha256")
        or basis.get("replacement_sha256")
        != journal.get("manifest_after_sha256")
        or basis.get("unresolved_inventory_sha256")
        != journal.get("unresolved_inventory_sha256")
        or any(
            type(basis.get(field)) is not int or int(basis[field]) < 0
            for field in integer_fields
        )
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    exact_removed = int(basis["exact_removable_row_count"])
    pair_count = int(basis["canonical_external_pair_group_count"])
    duplicate_group_count = int(basis["duplicate_group_count"])
    if (
        int(basis["row_count"]) <= 0
        or duplicate_group_count <= 0
        or int(basis["duplicate_row_count"]) <= 0
        or int(basis["removable_row_count"])
        != exact_removed + pair_count
        or exact_removed + pair_count <= 0
        or duplicate_group_count
        != int(basis["exact_group_count"])
        + int(basis["compatible_group_count"])
        + int(basis["conflicting_group_count"])
        + pair_count
        or int(basis["exact_duplicate_row_group_count"])
        > duplicate_group_count
        or exact_removed > int(basis["duplicate_row_count"])
        or pair_count > duplicate_group_count
        or _sha256(_canonical_bytes(basis)) != journal.get("plan_sha256")
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    return basis


def _interrupted_receipt_is_exact(
    raw: bytes,
    *,
    journal: Mapping[str, Any],
    plan_basis: Mapping[str, Any],
) -> bool:
    try:
        receipt = _strict_json_document(raw)
    except DuplicateObjectReconciliationError:
        return False
    expected_keys = {
        "schema_version",
        "reconciliation_id",
        "plan_sha256",
        "manifest_before_sha256",
        "manifest_after_sha256",
        "removed_exact_duplicate_row_count",
        "reconciled_canonical_external_pair_count",
        "compatible_group_count",
        "conflicting_group_count",
        "unresolved_group_count",
        "human_resolution_still_required",
        "unresolved_inventory",
        "approval_reference",
        "snapshot_preserved",
        "automatic_merge_performed",
        "strict_human_approved_pair_reconciliation_performed",
        "unresolved_distinct_rows_modified",
        "object_ids_stored_in_receipt",
        "paths_echoed_in_public_result",
    }
    supersession = journal.get("approval_supersession")
    if supersession is not None:
        expected_keys.add("approval_supersession_sha256")
    inventory = receipt.get("unresolved_inventory")
    if type(inventory) is not dict or "inventory_sha256" not in inventory:
        return False
    inventory_basis = dict(inventory)
    inventory_sha = inventory_basis.pop("inventory_sha256")
    unresolved_count = int(plan_basis["compatible_group_count"]) + int(
        plan_basis["conflicting_group_count"]
    )
    return bool(
        set(receipt) == expected_keys
        and receipt.get("schema_version") == RECEIPT_SCHEMA_VERSION
        and receipt.get("reconciliation_id")
        == journal.get("reconciliation_id")
        and receipt.get("plan_sha256") == journal.get("plan_sha256")
        and receipt.get("manifest_before_sha256")
        == journal.get("manifest_before_sha256")
        and receipt.get("manifest_after_sha256")
        == journal.get("manifest_after_sha256")
        and receipt.get("removed_exact_duplicate_row_count")
        == plan_basis.get("exact_removable_row_count")
        and receipt.get("reconciled_canonical_external_pair_count")
        == plan_basis.get("canonical_external_pair_group_count")
        and receipt.get("compatible_group_count")
        == plan_basis.get("compatible_group_count")
        and receipt.get("conflicting_group_count")
        == plan_basis.get("conflicting_group_count")
        and receipt.get("unresolved_group_count") == unresolved_count
        and receipt.get("human_resolution_still_required")
        is bool(unresolved_count)
        and receipt.get("approval_reference")
        == journal.get("approval_reference")
        and (
            supersession is None
            or receipt.get("approval_supersession_sha256")
            == _sha256(_canonical_bytes(supersession))
        )
        and receipt.get("snapshot_preserved") is True
        and receipt.get("automatic_merge_performed") is False
        and receipt.get(
            "strict_human_approved_pair_reconciliation_performed"
        )
        is bool(plan_basis["canonical_external_pair_group_count"])
        and receipt.get("unresolved_distinct_rows_modified") is False
        and receipt.get("object_ids_stored_in_receipt") is False
        and receipt.get("paths_echoed_in_public_result") is False
        and inventory.get("schema_version")
        == UNRESOLVED_INVENTORY_SCHEMA_VERSION
        and inventory.get("unresolved_group_count") == unresolved_count
        and inventory.get("object_ids_stored") is False
        and inventory.get("paths_stored") is False
        and inventory.get("row_content_stored") is False
        and inventory_sha == plan_basis.get("unresolved_inventory_sha256")
        and _sha256(_canonical_bytes(inventory_basis)) == inventory_sha
    )


def _validated_interrupted_revert_candidate(
    root: Path,
    *,
    journal_path: Path,
    current_manifest: bytes,
) -> _DuplicateObjectReconciliationRevertPlan | None:
    journal_raw = _read_safe_internal_file(
        root, journal_path, maximum_bytes=MAX_RECEIPT_BYTES
    )
    journal = _strict_json_document(journal_raw)
    reconciliation_id = journal.get("reconciliation_id")
    plan_sha = journal.get("plan_sha256")
    before_sha = journal.get("manifest_before_sha256")
    after_sha = journal.get("manifest_after_sha256")
    unresolved_sha = journal.get("unresolved_inventory_sha256")
    status = journal.get("status")
    if (
        journal.get("schema_version") != JOURNAL_SCHEMA_VERSION
        or type(reconciliation_id) is not str
        or _RECONCILIATION_ID_RE.fullmatch(reconciliation_id) is None
        or journal_path.stem != reconciliation_id
        or type(plan_sha) is not str
        or _SHA256_RE.fullmatch(plan_sha) is None
        or reconciliation_id
        != plan_sha.removeprefix("sha256:")[:24]
        or type(before_sha) is not str
        or _SHA256_RE.fullmatch(before_sha) is None
        or type(after_sha) is not str
        or _SHA256_RE.fullmatch(after_sha) is None
        or type(unresolved_sha) is not str
        or _SHA256_RE.fullmatch(unresolved_sha) is None
        or not _approval_reference_is_exact(journal.get("approval_reference"))
        or status not in {"started", "succeeded", "rolled_back"}
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")

    current_sha = _sha256(current_manifest)
    if status == "started" and current_sha not in {before_sha, after_sha}:
        # A preserved interrupted source journal may belong to a completed
        # terminal compensation followed by a later, independent exact
        # reconciliation.  It is not evidence for the current manifest.
        # Keep validating any journal whose before/after state does match so a
        # relevant malformed or incomplete record can never be skipped.
        return None

    receipt_path = root.joinpath(
        *RECEIPT_ROOT.parts, f"{reconciliation_id}.json"
    )
    if status == "succeeded":
        try:
            receipt_raw = _read_safe_internal_file(
                root, receipt_path, maximum_bytes=MAX_RECEIPT_BYTES
            )
        except DuplicateObjectReconciliationError:
            raise _fail("duplicate_object_revert_evidence_invalid") from None
        if (
            journal.get("snapshot_created") is not True
            or journal.get("manifest_replaced") is not True
            or journal.get("receipt_created") is not True
            or journal.get("receipt_sha256") != _sha256(receipt_raw)
        ):
            raise _fail("duplicate_object_revert_evidence_invalid")
        return None
    if status == "rolled_back":
        if _sha256(current_manifest) == after_sha:
            raise _fail("duplicate_object_revert_evidence_invalid")
        return None

    expected_started_keys = {
        "schema_version",
        "reconciliation_id",
        "plan_sha256",
        "manifest_before_sha256",
        "manifest_after_sha256",
        "unresolved_inventory_sha256",
        "plan_basis",
        "approval_reference",
        "status",
        "snapshot_created",
        "manifest_replaced",
        "receipt_created",
    }
    if (
        set(journal) != expected_started_keys
        or journal.get("snapshot_created") is not True
        or journal.get("manifest_replaced") is not False
        or journal.get("receipt_created") is not False
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")

    snapshot_path = root.joinpath(
        *SNAPSHOT_ROOT.parts, f"{reconciliation_id}.manifest.bin"
    )
    snapshot_raw = _read_safe_internal_file(
        root, snapshot_path, maximum_bytes=MAX_MANIFEST_BYTES
    )
    if _sha256(snapshot_raw) != before_sha:
        raise _fail("duplicate_object_revert_evidence_invalid")
    if current_sha == before_sha:
        # No manifest mutation occurred.  This is not a revert candidate.
        return None
    if current_sha != after_sha:
        raise _fail("duplicate_object_revert_evidence_invalid")

    lock_path = root.joinpath(*LOCK_ROOT.parts, f"{reconciliation_id}.lock")
    lock_raw = _read_safe_internal_file(root, lock_path, maximum_bytes=256)
    if lock_raw != plan_sha.encode("ascii") + b"\n":
        raise _fail("duplicate_object_revert_evidence_invalid")

    plan_basis = _validated_interrupted_plan_basis(root=root, journal=journal)

    receipt_raw: bytes | None
    try:
        receipt_stat = os.lstat(receipt_path)
    except FileNotFoundError:
        receipt_raw = None
    except OSError:
        raise _fail("duplicate_object_revert_evidence_invalid") from None
    else:
        if (
            stat_module.S_ISLNK(receipt_stat.st_mode)
            or _is_reparse_point(receipt_stat)
            or not stat_module.S_ISREG(receipt_stat.st_mode)
        ):
            raise _fail("duplicate_object_revert_evidence_invalid")
        receipt_raw = _read_safe_internal_file(
            root, receipt_path, maximum_bytes=MAX_RECEIPT_BYTES
        )
        if not _interrupted_receipt_is_exact(
            receipt_raw,
            journal=journal,
            plan_basis=plan_basis,
        ):
            raise _fail("duplicate_object_revert_evidence_invalid")

    return _build_revert_plan(
        root,
        current_manifest=current_manifest,
        snapshot_raw=snapshot_raw,
        reconciliation_id=reconciliation_id,
        journal_raw=journal_raw,
        receipt_raw=receipt_raw,
        source_evidence_kind=(
            "interrupted_receipt_published"
            if receipt_raw is not None
            else "interrupted_started_journal"
        ),
        exact_removed=int(plan_basis["exact_removable_row_count"]),
        pair_count=int(plan_basis["canonical_external_pair_group_count"]),
    )


def _source_revert_candidates_for_manifest(
    root: Path,
    current: bytes,
    *,
    terminal_auditor: _TerminalApprovalAuditor | None = None,
) -> list[_DuplicateObjectReconciliationRevertPlan]:
    candidates: list[_DuplicateObjectReconciliationRevertPlan] = []
    for receipt_path in _safe_receipt_paths(root):
        candidate = _validated_revert_candidate(
            root,
            receipt_path=receipt_path,
            current_manifest=current,
            terminal_auditor=terminal_auditor,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _plan_duplicate_object_reconciliation_revert_core(
    archive_root: Path | str,
    *,
    terminal_auditor: _TerminalApprovalAuditor | None = None,
) -> _DuplicateObjectReconciliationRevertPlan:
    root, _archive_id = _safe_root(archive_root)
    current = _read_manifest(root)
    candidates = _source_revert_candidates_for_manifest(
        root,
        current,
        terminal_auditor=terminal_auditor,
    )
    for journal_path in _safe_revert_journal_paths(root):
        candidate = _revert_plan_from_execution_journal(
            root,
            journal_path=journal_path,
            current_manifest=current,
            terminal_auditor=terminal_auditor,
        )
        if candidate is not None:
            candidates.append(candidate)
    unique: list[_DuplicateObjectReconciliationRevertPlan] = []
    for candidate in candidates:
        if any(_same_revert_plan(candidate, prior) for prior in unique):
            continue
        unique.append(candidate)
    candidates = unique
    for journal_path in _safe_journal_paths(root):
        candidate = _validated_interrupted_revert_candidate(
            root,
            journal_path=journal_path,
            current_manifest=current,
        )
        if candidate is not None:
            candidates.append(candidate)
    if not candidates:
        raise _fail("duplicate_object_revert_candidate_missing")
    if len(candidates) != 1:
        raise _fail("duplicate_object_revert_candidate_ambiguous")
    return candidates[0]


def plan_duplicate_object_reconciliation_revert(
    archive_root: Path | str,
) -> dict[str, Any]:
    root = Path(archive_root)
    return _plan_duplicate_object_reconciliation_revert_core(
        root,
        terminal_auditor=_production_terminal_auditor(root),
    ).public_document()


def _duplicate_object_reconciliation_revert_context(
    plan: _DuplicateObjectReconciliationRevertPlan,
    *,
    reviewer_claim: str,
) -> ExactHumanApprovalContext:
    if type(plan) is not _DuplicateObjectReconciliationRevertPlan:
        raise _fail("duplicate_object_revert_plan_invalid")
    evidence_binding_code = (
        "successful_reconciliation_receipt_digest"
        if plan.source_evidence_kind == "successful_receipt"
        else "interrupted_reconciliation_evidence_digest"
    )
    return ExactHumanApprovalContext(
        operation=ExactHumanApprovalOperation.duplicate_object_reconcile,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(
            plan.archive_id
        ),
        plan_sha256=plan.plan_sha256,
        target_binding_sha256=plan.manifest_current_sha256,
        reviewer_claim=reviewer_claim,
        review_binding_codes=(
            "current_post_state_manifest_digest",
            "exact_original_snapshot_digest",
            evidence_binding_code,
            "whole_manifest_revert",
        ),
    )


def _same_revert_plan(
    left: _DuplicateObjectReconciliationRevertPlan,
    right: _DuplicateObjectReconciliationRevertPlan,
) -> bool:
    return (
        left.plan_sha256 == right.plan_sha256
        and left.manifest_current_sha256 == right.manifest_current_sha256
        and left.manifest_restore_sha256 == right.manifest_restore_sha256
        and left.source_evidence_kind == right.source_evidence_kind
        and left.source_evidence_sha256 == right.source_evidence_sha256
        and left.source_journal_sha256 == right.source_journal_sha256
        and left.source_receipt_sha256 == right.source_receipt_sha256
        and left._manifest_current_bytes == right._manifest_current_bytes
        and left._manifest_restore_bytes == right._manifest_restore_bytes
        and left._source_receipt_bytes == right._source_receipt_bytes
        and left._source_journal_bytes == right._source_journal_bytes
    )


def _revert_started_journal_document(
    plan: _DuplicateObjectReconciliationRevertPlan,
    *,
    revert_id: str,
    approval_reference: Mapping[str, Any],
    approval_supersession: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    document = {
        "schema_version": REVERT_JOURNAL_SCHEMA_VERSION,
        "revert_id": revert_id,
        "plan_sha256": plan.plan_sha256,
        "source_evidence_kind": plan.source_evidence_kind,
        "source_evidence_sha256": plan.source_evidence_sha256,
        "source_journal_sha256": plan.source_journal_sha256,
        "source_receipt_sha256": plan.source_receipt_sha256,
        "source_reconciliation_id": plan._source_reconciliation_id,
        "manifest_before_revert_sha256": plan.manifest_current_sha256,
        "manifest_after_revert_sha256": plan.manifest_restore_sha256,
        "removed_exact_duplicate_row_count": (
            plan.removed_exact_duplicate_row_count
        ),
        "reconciled_canonical_external_pair_count": (
            plan.reconciled_canonical_external_pair_count
        ),
        "approval_reference": dict(approval_reference),
        "status": "started",
        "post_state_snapshot_created": True,
        "manifest_restored": False,
        "receipt_created": False,
    }
    if approval_supersession is not None:
        document["approval_supersession"] = dict(approval_supersession)
    return document


def _revert_receipt_document(
    plan: _DuplicateObjectReconciliationRevertPlan,
    *,
    revert_id: str,
    approval_reference: Mapping[str, Any],
    approval_supersession: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    document = {
        "schema_version": REVERT_RECEIPT_SCHEMA_VERSION,
        "revert_id": revert_id,
        "plan_sha256": plan.plan_sha256,
        "source_evidence_kind": plan.source_evidence_kind,
        "source_evidence_sha256": plan.source_evidence_sha256,
        "source_journal_sha256": plan.source_journal_sha256,
        "source_receipt_sha256": plan.source_receipt_sha256,
        "manifest_before_revert_sha256": plan.manifest_current_sha256,
        "manifest_after_revert_sha256": plan.manifest_restore_sha256,
        "restored_exact_original_manifest_bytes": True,
        "removed_exact_duplicate_row_count_restored": (
            plan.removed_exact_duplicate_row_count
        ),
        "reconciled_canonical_external_pair_count_restored": (
            plan.reconciled_canonical_external_pair_count
        ),
        "approval_reference": dict(approval_reference),
        "post_state_snapshot_preserved": True,
        "object_ids_stored_in_receipt": False,
        "paths_stored_in_receipt": False,
    }
    if approval_supersession is not None:
        document["approval_supersession_sha256"] = _sha256(
            _canonical_bytes(approval_supersession)
        )
    return document


def _terminal_compensation_document(
    plan: _DuplicateObjectReconciliationRevertPlan,
    *,
    source_journal_raw: bytes,
    revert_started_journal_raw: bytes,
    revert_receipt_raw: bytes,
) -> dict[str, Any]:
    return {
        "schema_version": TERMINAL_COMPENSATION_SCHEMA_VERSION,
        "source_plan_sha256": _strict_json_document(source_journal_raw)[
            "plan_sha256"
        ],
        "source_journal_sha256": _sha256(source_journal_raw),
        "source_evidence_sha256": plan.source_evidence_sha256,
        "revert_plan_sha256": plan.plan_sha256,
        "revert_started_journal_sha256": _sha256(revert_started_journal_raw),
        "revert_receipt_sha256": _sha256(revert_receipt_raw),
        "restored_manifest_sha256": plan.manifest_restore_sha256,
    }


def _revert_finalization_pending_journal_document(
    started: Mapping[str, Any],
    *,
    receipt_raw: bytes,
    pending_finalization_approval_reference: Mapping[str, Any],
) -> dict[str, Any]:
    document = dict(started)
    document.update(
        {
            "status": "finalization_pending",
            "manifest_restored": True,
            "receipt_created": True,
            "receipt_sha256": _sha256(receipt_raw),
            "pending_finalization_approval_reference": dict(
                pending_finalization_approval_reference
            ),
        }
    )
    return document


def _revert_succeeded_journal_document(
    started: Mapping[str, Any],
    *,
    receipt_raw: bytes,
    finalization_claim: _ClaimedExactHumanApproval,
    context: ExactHumanApprovalContext,
) -> dict[str, Any]:
    finalization_reference = finalization_claim.assert_succeeded_for_context(
        context
    )
    finalization_evidence = finalization_claim.succeeded_evidence_digests(
        context
    )
    document = dict(started)
    document.update(
        {
            "status": "succeeded",
            "manifest_restored": True,
            "receipt_created": True,
            "receipt_sha256": _sha256(receipt_raw),
            "finalization_approval_reference": dict(finalization_reference),
            "finalization_claim_evidence": {
                "schema_version": REVERT_FINALIZATION_EVIDENCE_SCHEMA_VERSION,
                **finalization_evidence,
            },
        }
    )
    payload = _canonical_bytes(document)
    mac = finalization_claim.exact_terminal_record_mac(payload)
    document["terminal_authentication"] = _terminal_authentication_document(mac)
    return document


def _revert_approval_supersession_is_exact(
    value: Any,
    *,
    plan: _DuplicateObjectReconciliationRevertPlan,
    revert_id: str,
    replacement_reference: Mapping[str, Any],
    supersession_depth: int = 0,
) -> bool:
    if supersession_depth >= _MAX_APPROVAL_SUPERSESSION_DEPTH:
        return False
    expected_keys = {
        "schema_version",
        "reason_code",
        "superseded_journal_sha256",
        "superseded_approval_reference_sha256",
        "replacement_approval_reference_sha256",
        "manifest_sha256",
        "mutation_had_not_started",
        "superseded_journal_evidence",
    }
    if type(value) is not dict or set(value) != expected_keys:
        return False
    evidence = value.get("superseded_journal_evidence")
    if (
        value.get("schema_version")
        != "wom-kit/duplicate-object-prewrite-approval-supersession/v0.1"
        or value.get("reason_code")
        != "interrupted_prewrite_approval_superseded"
        or type(value.get("superseded_journal_sha256")) is not str
        or _SHA256_RE.fullmatch(value["superseded_journal_sha256"])
        is None
        or type(value.get("superseded_approval_reference_sha256")) is not str
        or _SHA256_RE.fullmatch(
            value["superseded_approval_reference_sha256"]
        )
        is None
        or value.get("replacement_approval_reference_sha256")
        != _sha256(_canonical_bytes(replacement_reference))
        or value.get("manifest_sha256") != plan.manifest_current_sha256
        or value.get("mutation_had_not_started") is not True
        or type(evidence) is not dict
        or set(evidence) != {"schema_version", "journal"}
        or evidence.get("schema_version")
        != "wom-kit/duplicate-object-superseded-started-journal/v0.1"
        or type(evidence.get("journal")) is not dict
    ):
        return False
    superseded_journal = evidence["journal"]
    superseded_reference = superseded_journal.get("approval_reference")
    nested_supersession = superseded_journal.get("approval_supersession")
    expected_started = _revert_started_journal_document(
        plan,
        revert_id=revert_id,
        approval_reference=(
            superseded_reference
            if isinstance(superseded_reference, Mapping)
            else {}
        ),
        approval_supersession=(
            nested_supersession
            if isinstance(nested_supersession, Mapping)
            else None
        ),
    )
    if (
        superseded_journal != expected_started
        or not _approval_reference_is_exact(superseded_reference)
        or _sha256(_canonical_bytes(superseded_journal))
        != value["superseded_journal_sha256"]
        or _sha256(_canonical_bytes(superseded_reference))
        != value["superseded_approval_reference_sha256"]
    ):
        return False
    return bool(
        nested_supersession is None
        or _revert_approval_supersession_is_exact(
            nested_supersession,
            plan=plan,
            revert_id=revert_id,
            replacement_reference=superseded_reference,
            supersession_depth=supersession_depth + 1,
        )
    )


def _superseded_approval_references(
    supersession: Mapping[str, Any],
    *,
    maximum_depth: int = _MAX_APPROVAL_SUPERSESSION_DEPTH,
) -> list[Mapping[str, Any]]:
    references: list[Mapping[str, Any]] = []
    current: Any = supersession
    for _ in range(maximum_depth):
        if not isinstance(current, Mapping):
            raise _fail("duplicate_object_revert_evidence_invalid")
        try:
            journal = current["superseded_journal_evidence"]["journal"]
            reference = journal["approval_reference"]
        except (KeyError, TypeError):
            raise _fail("duplicate_object_revert_evidence_invalid") from None
        if not _approval_reference_is_exact(reference):
            raise _fail("duplicate_object_revert_evidence_invalid")
        references.append(reference)
        current = journal.get("approval_supersession")
        if current is None:
            return references
    raise _fail("duplicate_object_revert_evidence_invalid")


def _revert_journal_is_exact_for_plan(
    plan: _DuplicateObjectReconciliationRevertPlan,
    *,
    revert_id: str,
    raw: bytes,
    terminal_auditor: _TerminalApprovalAuditor | None = None,
) -> dict[str, Any]:
    document = _strict_json_document(raw)
    if _canonical_bytes(document) != raw:
        raise _fail("duplicate_object_revert_evidence_invalid")
    approval_reference = document.get("approval_reference")
    if not _approval_reference_is_exact(approval_reference):
        raise _fail("duplicate_object_revert_evidence_invalid")
    supersession = document.get("approval_supersession")
    if supersession is not None and not _revert_approval_supersession_is_exact(
        supersession,
        plan=plan,
        revert_id=revert_id,
        replacement_reference=approval_reference,
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    started = _revert_started_journal_document(
        plan,
        revert_id=revert_id,
        approval_reference=approval_reference,
        approval_supersession=supersession,
    )
    status = document.get("status")
    if status == "started":
        if document != started:
            raise _fail("duplicate_object_revert_evidence_invalid")
        return document
    receipt_sha = document.get("receipt_sha256")
    if (
        type(receipt_sha) is not str
        or _SHA256_RE.fullmatch(receipt_sha) is None
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    if status == "finalization_pending":
        pending_reference = document.get(
            "pending_finalization_approval_reference"
        )
        if not _approval_reference_is_exact(pending_reference):
            raise _fail("duplicate_object_revert_evidence_invalid")
        expected = _revert_finalization_pending_journal_document(
            started,
            receipt_raw=b"placeholder",
            pending_finalization_approval_reference=pending_reference,
        )
        expected["receipt_sha256"] = receipt_sha
        expected["terminal_authentication"] = document.get(
            "terminal_authentication"
        )
        if (
            document != expected
            or not _terminal_record_is_authenticated(
                document,
                terminal_auditor=terminal_auditor,
                reference=pending_reference,
                expected_plan_sha256=plan.plan_sha256,
                expected_target_binding_sha256=plan.manifest_current_sha256,
                allowed_statuses=("started", "succeeded"),
                succeeded_evidence=None,
            )
        ):
            raise _fail("duplicate_object_revert_evidence_invalid")
        return document
    if status != "succeeded":
        raise _fail("duplicate_object_revert_evidence_invalid")
    finalization_reference = document.get("finalization_approval_reference")
    evidence = _revert_finalization_evidence_digests(
        document.get("finalization_claim_evidence")
    )
    if not _approval_reference_is_exact(finalization_reference) or evidence is None:
        raise _fail("duplicate_object_revert_evidence_invalid")
    expected = dict(started)
    expected.update(
        {
            "status": "succeeded",
            "manifest_restored": True,
            "receipt_created": True,
            "receipt_sha256": receipt_sha,
            "finalization_approval_reference": dict(finalization_reference),
            "finalization_claim_evidence": {
                "schema_version": REVERT_FINALIZATION_EVIDENCE_SCHEMA_VERSION,
                **evidence,
            },
            "terminal_authentication": document.get(
                "terminal_authentication"
            ),
        }
    )
    if (
        document != expected
        or not _terminal_record_is_authenticated(
            document,
            terminal_auditor=terminal_auditor,
            reference=finalization_reference,
            expected_plan_sha256=plan.plan_sha256,
            expected_target_binding_sha256=plan.manifest_current_sha256,
            allowed_statuses=("succeeded",),
            succeeded_evidence=evidence,
        )
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    return document


def _optional_safe_revert_file(
    root: Path,
    path: Path,
    *,
    maximum_bytes: int,
) -> bytes | None:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError:
        raise _fail("duplicate_object_revert_evidence_invalid") from None
    return _read_safe_internal_file(root, path, maximum_bytes=maximum_bytes)


def _inspect_revert_execution(
    root: Path,
    plan: _DuplicateObjectReconciliationRevertPlan,
    *,
    current_manifest: bytes,
    terminal_auditor: _TerminalApprovalAuditor | None = None,
) -> dict[str, Any]:
    revert_id = plan.plan_sha256.removeprefix("sha256:")[:24]
    lock_path = root.joinpath(*REVERT_LOCK_ROOT.parts, f"{revert_id}.lock")
    snapshot_path = root.joinpath(
        *REVERT_SNAPSHOT_ROOT.parts, f"{revert_id}.post.manifest.bin"
    )
    journal_path = root.joinpath(*REVERT_JOURNAL_ROOT.parts, f"{revert_id}.json")
    receipt_path = root.joinpath(*REVERT_RECEIPT_ROOT.parts, f"{revert_id}.json")
    lock_raw = _optional_safe_revert_file(root, lock_path, maximum_bytes=256)
    snapshot_raw = _optional_safe_revert_file(
        root, snapshot_path, maximum_bytes=MAX_MANIFEST_BYTES
    )
    journal_raw = _optional_safe_revert_file(
        root, journal_path, maximum_bytes=MAX_RECEIPT_BYTES
    )
    receipt_raw = _optional_safe_revert_file(
        root, receipt_path, maximum_bytes=MAX_RECEIPT_BYTES
    )
    current_is_post = current_manifest == plan._manifest_current_bytes
    current_is_pre = current_manifest == plan._manifest_restore_bytes
    if not current_is_post and not current_is_pre:
        raise _fail("duplicate_object_revert_evidence_invalid")
    if all(
        value is None
        for value in (lock_raw, snapshot_raw, journal_raw, receipt_raw)
    ):
        if not current_is_post:
            raise _fail("duplicate_object_revert_evidence_invalid")
        return {
            "state": "absent",
            "revert_id": revert_id,
            "lock_path": lock_path,
            "snapshot_path": snapshot_path,
            "journal_path": journal_path,
            "receipt_path": receipt_path,
            "lock_raw": None,
            "snapshot_raw": None,
            "journal_raw": None,
            "journal": None,
            "receipt_raw": None,
        }
    if (
        lock_raw != plan.plan_sha256.encode("ascii") + b"\n"
        or (snapshot_raw is not None and lock_raw is None)
        or (journal_raw is not None and snapshot_raw is None)
        or (receipt_raw is not None and journal_raw is None)
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    if snapshot_raw is not None and snapshot_raw != plan._manifest_current_bytes:
        raise _fail("duplicate_object_revert_evidence_invalid")
    if journal_raw is None:
        if receipt_raw is not None or current_is_pre:
            raise _fail("duplicate_object_revert_evidence_invalid")
        journal = None
    else:
        journal = _revert_journal_is_exact_for_plan(
            plan,
            revert_id=revert_id,
            raw=journal_raw,
            terminal_auditor=terminal_auditor,
        )
    if journal is not None:
        expected_receipt = _canonical_bytes(
            _revert_receipt_document(
                plan,
                revert_id=revert_id,
                approval_reference=journal["approval_reference"],
                approval_supersession=journal.get("approval_supersession"),
            )
        )
        if receipt_raw is not None and receipt_raw != expected_receipt:
            raise _fail("duplicate_object_revert_evidence_invalid")
        if journal["status"] in {"finalization_pending", "succeeded"}:
            if (
                not current_is_pre
                or receipt_raw is None
                or journal.get("receipt_sha256") != _sha256(receipt_raw)
            ):
                raise _fail("duplicate_object_revert_evidence_invalid")
        elif current_is_post and receipt_raw is not None:
            raise _fail("duplicate_object_revert_evidence_invalid")
    state = "restore_required" if current_is_post else "finalize_only"
    return {
        "state": state,
        "revert_id": revert_id,
        "lock_path": lock_path,
        "snapshot_path": snapshot_path,
        "journal_path": journal_path,
        "receipt_path": receipt_path,
        "lock_raw": lock_raw,
        "snapshot_raw": snapshot_raw,
        "journal_raw": journal_raw,
        "journal": journal,
        "receipt_raw": receipt_raw,
    }


def _revert_plan_from_execution_journal(
    root: Path,
    *,
    journal_path: Path,
    current_manifest: bytes,
    terminal_auditor: _TerminalApprovalAuditor | None = None,
) -> _DuplicateObjectReconciliationRevertPlan | None:
    raw = _read_safe_internal_file(
        root, journal_path, maximum_bytes=MAX_RECEIPT_BYTES
    )
    document = _strict_json_document(raw)
    revert_id = document.get("revert_id")
    plan_sha = document.get("plan_sha256")
    source_reconciliation_id = document.get("source_reconciliation_id")
    if (
        type(revert_id) is not str
        or _RECONCILIATION_ID_RE.fullmatch(revert_id) is None
        or journal_path.stem != revert_id
        or type(plan_sha) is not str
        or _SHA256_RE.fullmatch(plan_sha) is None
        or revert_id != plan_sha.removeprefix("sha256:")[:24]
        or type(source_reconciliation_id) is not str
        or _RECONCILIATION_ID_RE.fullmatch(source_reconciliation_id) is None
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    snapshot_path = root.joinpath(
        *REVERT_SNAPSHOT_ROOT.parts, f"{revert_id}.post.manifest.bin"
    )
    post_manifest = _read_safe_internal_file(
        root, snapshot_path, maximum_bytes=MAX_MANIFEST_BYTES
    )
    # Reconstruct the exact source operation named by the revert journal.  A
    # successful forward operation is receipt-backed, while an interrupted
    # forward operation can only be recovered from its still-started journal.
    # Scanning receipts alone loses that second provenance once the revert has
    # already restored the manifest to the pre-state.
    source_candidates: list[_DuplicateObjectReconciliationRevertPlan] = []
    source_receipt_path = root.joinpath(
        *RECEIPT_ROOT.parts, f"{source_reconciliation_id}.json"
    )
    if _optional_safe_revert_file(
        root,
        source_receipt_path,
        maximum_bytes=MAX_RECEIPT_BYTES,
    ) is not None:
        receipt_candidate = _validated_revert_candidate(
            root,
            receipt_path=source_receipt_path,
            current_manifest=post_manifest,
            terminal_auditor=terminal_auditor,
        )
        if receipt_candidate is not None:
            source_candidates.append(receipt_candidate)
    source_journal_path = root.joinpath(
        *JOURNAL_ROOT.parts, f"{source_reconciliation_id}.json"
    )
    journal_candidate = _validated_interrupted_revert_candidate(
        root,
        journal_path=source_journal_path,
        current_manifest=post_manifest,
    )
    if journal_candidate is not None:
        source_candidates.append(journal_candidate)
    matching = [
        candidate
        for candidate in source_candidates
        if candidate.plan_sha256 == plan_sha
    ]
    if len(matching) != 1:
        raise _fail("duplicate_object_revert_evidence_invalid")
    plan = matching[0]
    if current_manifest not in {
        plan._manifest_current_bytes,
        plan._manifest_restore_bytes,
    }:
        receipt_path = root.joinpath(
            *REVERT_RECEIPT_ROOT.parts, f"{revert_id}.json"
        )
        receipt_exists = _optional_safe_revert_file(
            root,
            receipt_path,
            maximum_bytes=MAX_RECEIPT_BYTES,
        ) is not None
        validation_manifest = (
            plan._manifest_restore_bytes
            if document.get("status") == "succeeded" or receipt_exists
            else plan._manifest_current_bytes
        )
        _inspect_revert_execution(
            root,
            plan,
            current_manifest=validation_manifest,
            terminal_auditor=terminal_auditor,
        )
        return None
    _inspect_revert_execution(
        root,
        plan,
        current_manifest=current_manifest,
        terminal_auditor=terminal_auditor,
    )
    # A succeeded revert is terminal evidence, not an approveable retry.  It
    # must still be inspected above so a later independent forward candidate
    # can coexist with authenticated historical evidence.
    if document.get("status") == "succeeded":
        return None
    return plan


def _create_or_exact_revert_file(
    root: Path,
    path: Path,
    raw: bytes,
    *,
    maximum_bytes: int,
) -> None:
    existing = _optional_safe_revert_file(
        root, path, maximum_bytes=maximum_bytes
    )
    if existing is not None:
        if existing != raw:
            raise _fail("duplicate_object_revert_evidence_invalid")
        return
    try:
        _create_only(root, path, raw)
    except BaseException:
        reread = _optional_safe_revert_file(
            root, path, maximum_bytes=maximum_bytes
        )
        if reread != raw:
            raise _fail("duplicate_object_revert_state_unknown") from None


def _replace_or_exact_revert_file(
    root: Path,
    path: Path,
    raw: bytes,
    *,
    maximum_bytes: int,
) -> None:
    try:
        _atomic_replace(root, path, raw)
    except BaseException:
        reread = _optional_safe_revert_file(
            root, path, maximum_bytes=maximum_bytes
        )
        if reread != raw:
            raise _fail("duplicate_object_revert_state_unknown") from None


def _apply_duplicate_object_reconciliation_revert_core(
    plan: _DuplicateObjectReconciliationRevertPlan,
    approval_claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
) -> dict[str, Any]:
    if type(plan) is not _DuplicateObjectReconciliationRevertPlan:
        raise _fail("duplicate_object_revert_plan_invalid")
    root, archive_id = _safe_root(plan.archive_root)
    if root != plan.archive_root or archive_id != plan.archive_id:
        raise _fail("duplicate_object_revert_plan_invalid")
    current_manifest = _read_manifest(root)
    source_journal = _strict_json_document(plan._source_journal_bytes)
    manifest_mutation_owner_sha256 = (
        archive_services.archive_manifest_mutation_owner_sha256(
            operation="duplicate_object_reconcile",
            operation_binding_sha256=str(source_journal["plan_sha256"]),
        )
    )
    try:
        archive_services.require_archive_manifest_index_mutation_authority(
            root,
            operation_owner_sha256=manifest_mutation_owner_sha256,
            expected_pre_manifest_sha256=_sha256(current_manifest),
            expected_post_manifest_sha256=plan.manifest_restore_sha256,
        )
    except archive_services.ArchiveServiceError:
        raise _fail("archive_index_rebuild_required") from None
    with archive_services._ObjetCaptureManifestLock(root):
        return _apply_duplicate_object_reconciliation_revert_locked_core(
            plan,
            approval_claim,
            context=context,
        )


def _apply_duplicate_object_reconciliation_revert_locked_core(
    plan: _DuplicateObjectReconciliationRevertPlan,
    approval_claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
) -> dict[str, Any]:
    if type(plan) is not _DuplicateObjectReconciliationRevertPlan:
        raise _fail("duplicate_object_revert_plan_invalid")
    if (
        type(approval_claim) is not _ClaimedExactHumanApproval
        or type(context) is not ExactHumanApprovalContext
        or context.operation is not ExactHumanApprovalOperation.duplicate_object_reconcile
        or context.plan_sha256 != plan.plan_sha256
        or context.target_binding_sha256 != plan.manifest_current_sha256
    ):
        raise _fail("duplicate_object_revert_approval_required")
    root, archive_id = _safe_root(plan.archive_root)
    if root != plan.archive_root or archive_id != plan.archive_id:
        raise _fail("duplicate_object_revert_plan_invalid")
    current_manifest = _read_manifest(root)
    if current_manifest not in {
        plan._manifest_current_bytes,
        plan._manifest_restore_bytes,
    }:
        raise _fail("duplicate_object_manifest_changed")
    try:
        approval_reference = _ClaimedExactHumanApproval.assert_ready_for_context(
            approval_claim, context
        )
    except ExactHumanApprovalError:
        raise _fail("duplicate_object_revert_approval_required") from None

    # Rediscovery also recognizes an interrupted revert whose manifest already
    # equals the exact pre-state.  In that state the writer performs only
    # receipt/journal finalization; it never writes the manifest a second time.
    terminal_auditor = _claim_terminal_auditor(approval_claim)
    fresh = _plan_duplicate_object_reconciliation_revert_core(
        root,
        terminal_auditor=terminal_auditor,
    )
    if not _same_revert_plan(plan, fresh):
        raise _fail("duplicate_object_revert_evidence_invalid")
    execution = _inspect_revert_execution(
        root,
        plan,
        current_manifest=current_manifest,
        terminal_auditor=terminal_auditor,
    )
    source_journal = _strict_json_document(plan._source_journal_bytes)
    manifest_mutation_owner_sha256 = (
        archive_services.archive_manifest_mutation_owner_sha256(
            operation="duplicate_object_reconcile",
            operation_binding_sha256=str(source_journal["plan_sha256"]),
        )
    )
    try:
        source_claim_status = (
            approval_claim.approval_integrity_reference_status(
                source_journal["approval_reference"],
                expected_operation=(
                    ExactHumanApprovalOperation.duplicate_object_reconcile
                ),
                expected_plan_sha256=str(source_journal["plan_sha256"]),
                expected_target_binding_sha256=plan.manifest_restore_sha256,
            )
        )
    except ExactHumanApprovalError:
        raise _fail("duplicate_object_revert_evidence_invalid") from None
    allowed_source_claim_states = (
        {"started", "succeeded"}
        if plan.source_evidence_kind == "successful_receipt"
        else {"started"}
    )
    if source_claim_status not in allowed_source_claim_states:
        raise _fail("duplicate_object_revert_evidence_invalid")
    source_supersession = source_journal.get("approval_supersession")
    if (
        plan.source_evidence_kind == "successful_receipt"
        and source_supersession is not None
    ):
        try:
            superseded_references = _superseded_approval_references(
                source_supersession
            )
            for superseded_reference in superseded_references:
                superseded_status = (
                    approval_claim.approval_integrity_reference_status(
                        superseded_reference,
                        expected_operation=(
                            ExactHumanApprovalOperation
                            .duplicate_object_reconcile
                        ),
                        expected_plan_sha256=str(source_journal["plan_sha256"]),
                        expected_target_binding_sha256=(
                            plan.manifest_restore_sha256
                        ),
                    )
                )
                if superseded_status != "started":
                    raise _fail("duplicate_object_revert_evidence_invalid")
        except ExactHumanApprovalError:
            raise _fail("duplicate_object_revert_evidence_invalid") from None

    revert_supersession = (
        execution["journal"].get("approval_supersession")
        if execution["journal"] is not None
        else None
    )
    if revert_supersession is not None:
        try:
            for superseded_reference in _superseded_approval_references(
                revert_supersession
            ):
                superseded_status = (
                    approval_claim.approval_integrity_reference_status(
                        superseded_reference,
                        expected_operation=(
                            ExactHumanApprovalOperation
                            .duplicate_object_reconcile
                        ),
                        expected_plan_sha256=plan.plan_sha256,
                        expected_target_binding_sha256=(
                            plan.manifest_current_sha256
                        ),
                    )
                )
                if superseded_status != "started":
                    raise _fail("duplicate_object_revert_evidence_invalid")
        except ExactHumanApprovalError:
            raise _fail("duplicate_object_revert_evidence_invalid") from None

    if execution["state"] in {"absent", "restore_required"}:
        try:
            archive_services.require_archive_manifest_index_mutation_authority(
                root,
                operation_owner_sha256=manifest_mutation_owner_sha256,
                expected_pre_manifest_sha256=_sha256(current_manifest),
                expected_post_manifest_sha256=plan.manifest_restore_sha256,
            )
        except archive_services.ArchiveServiceError:
            raise _fail("archive_index_rebuild_required") from None
    else:
        index_evidence = archive_services.require_current_zettel_index(root)
        if "archive_index_dirty" in set(
            index_evidence.get("reason_codes") or []
        ):
            try:
                archive_services.require_archive_manifest_index_mutation_authority(
                    root,
                    operation_owner_sha256=manifest_mutation_owner_sha256,
                    expected_pre_manifest_sha256=_sha256(current_manifest),
                    expected_post_manifest_sha256=_sha256(current_manifest),
                )
            except archive_services.ArchiveServiceError:
                raise _fail("archive_index_rebuild_required") from None

    revert_id = execution["revert_id"]
    lock_path = execution["lock_path"]
    post_snapshot_path = execution["snapshot_path"]
    journal_path = execution["journal_path"]
    receipt_path = execution["receipt_path"]
    manifest_write_performed = False
    manifest_mutation_attempted = False
    manifest_projection_update_required = False
    manifest_index_generation: str | None = None
    manifest_index_lease_token: (
        archive_services.ArchiveIndexMutationLeaseToken | None
    ) = None
    manifest_index_resumed = False
    manifest_index_updated = False
    try:
        journal = execution["journal"]
        journal_raw = execution["journal_raw"]
        mutation_approval_reference = dict(approval_reference)
        if journal is not None:
            prior_reference = dict(journal["approval_reference"])
            try:
                prior_status = (
                    approval_claim.approval_integrity_reference_status(
                        prior_reference,
                        expected_operation=(
                            ExactHumanApprovalOperation.duplicate_object_reconcile
                        ),
                        expected_plan_sha256=plan.plan_sha256,
                        expected_target_binding_sha256=(
                            plan.manifest_current_sha256
                        ),
                    )
                )
            except ExactHumanApprovalError:
                raise _fail("duplicate_object_revert_evidence_invalid") from None
            allowed_prior_states = (
                {"started", "succeeded"}
                if journal["status"] == "succeeded"
                else {"started"}
            )
            if prior_status not in allowed_prior_states:
                raise _fail("duplicate_object_revert_evidence_invalid")
            existing_finalization_reference = (
                journal.get("pending_finalization_approval_reference")
                if journal["status"] == "finalization_pending"
                else journal.get("finalization_approval_reference")
            )
            if existing_finalization_reference is not None:
                try:
                    finalization_status = (
                        approval_claim.approval_integrity_reference_status(
                            existing_finalization_reference,
                            expected_operation=(
                                ExactHumanApprovalOperation
                                .duplicate_object_reconcile
                            ),
                            expected_plan_sha256=plan.plan_sha256,
                            expected_target_binding_sha256=(
                                plan.manifest_current_sha256
                            ),
                        )
                    )
                except ExactHumanApprovalError:
                    raise _fail(
                        "duplicate_object_revert_evidence_invalid"
                    ) from None
                expected_finalization_status = (
                    "started"
                    if journal["status"] == "finalization_pending"
                    else "succeeded"
                )
                if finalization_status != expected_finalization_status:
                    raise _fail("duplicate_object_revert_evidence_invalid")
                if (
                    journal["status"] == "finalization_pending"
                    and existing_finalization_reference != approval_reference
                ):
                    raise _fail("duplicate_object_revert_evidence_invalid")
            mutation_approval_reference = prior_reference
            if (
                execution["state"] == "finalize_only"
                and journal["status"] == "started"
                and prior_reference != approval_reference
            ):
                raise _fail("duplicate_object_revert_evidence_invalid")
            if (
                execution["state"] == "restore_required"
                and journal["status"] == "started"
                and prior_reference != approval_reference
            ):
                if execution["receipt_raw"] is not None:
                    raise _fail("duplicate_object_revert_evidence_invalid")
                prior_supersession = journal.get("approval_supersession")
                if (
                    prior_supersession is not None
                    and len(
                        _superseded_approval_references(prior_supersession)
                    )
                    >= _MAX_APPROVAL_SUPERSESSION_DEPTH
                ):
                    raise _fail("duplicate_object_revert_evidence_invalid")
                supersession = _approval_supersession_document(
                    superseded_journal_raw=journal_raw,
                    superseded_reference=prior_reference,
                    replacement_reference=approval_reference,
                    manifest_sha256=plan.manifest_current_sha256,
                    include_superseded_journal_evidence=True,
                )
                journal = _revert_started_journal_document(
                    plan,
                    revert_id=revert_id,
                    approval_reference=approval_reference,
                    approval_supersession=supersession,
                )
                journal_raw = _canonical_bytes(journal)
                _replace_or_exact_revert_file(
                    root,
                    journal_path,
                    journal_raw,
                    maximum_bytes=MAX_RECEIPT_BYTES,
                )
                mutation_approval_reference = dict(approval_reference)

        _create_or_exact_revert_file(
            root,
            lock_path,
            plan.plan_sha256.encode("ascii") + b"\n",
            maximum_bytes=256,
        )
        _create_or_exact_revert_file(
            root,
            post_snapshot_path,
            plan._manifest_current_bytes,
            maximum_bytes=MAX_MANIFEST_BYTES,
        )
        if journal is None:
            journal = _revert_started_journal_document(
                plan,
                revert_id=revert_id,
                approval_reference=mutation_approval_reference,
            )
            journal_raw = _canonical_bytes(journal)
            _create_or_exact_revert_file(
                root,
                journal_path,
                journal_raw,
                maximum_bytes=MAX_RECEIPT_BYTES,
            )

        if execution["state"] in {"absent", "restore_required"}:
            try:
                (
                    manifest_index_generation,
                    manifest_index_began,
                    manifest_index_lease_token,
                ) = archive_services.prepare_archive_manifest_index_mutation(
                    root,
                    operation_owner_sha256=manifest_mutation_owner_sha256,
                    expected_pre_manifest_sha256=(
                        plan.manifest_current_sha256
                    ),
                    expected_post_manifest_sha256=(
                        plan.manifest_restore_sha256
                    ),
                )
            except archive_services.ArchiveServiceError:
                raise _fail("archive_index_rebuild_required") from None
            manifest_index_resumed = not manifest_index_began
            manifest_mutation_attempted = True
            manifest_projection_update_required = True
            try:
                _replace_manifest_compare_and_swap(
                    root,
                    expected_bytes=plan._manifest_current_bytes,
                    replacement_bytes=plan._manifest_restore_bytes,
                    transaction_sha256=manifest_mutation_owner_sha256,
                    swap_suffix=".duplicate-object-revert-manifest.swap",
                    error_prefix="duplicate_object_revert",
                )
            except BaseException:
                if _read_manifest(root) != plan._manifest_restore_bytes:
                    raise _fail("duplicate_object_revert_state_unknown") from None
            else:
                manifest_write_performed = True
        if _read_manifest(root) != plan._manifest_restore_bytes:
            raise _fail("duplicate_object_revert_state_unknown")
        if manifest_projection_update_required:
            manifest_index_updated = (
                archive_services.replace_archive_index_manifest_projection(
                    root,
                    expected_generation=str(manifest_index_generation or ""),
                    expected_manifest_sha256=plan.manifest_restore_sha256,
                    expected_mutation_owner_sha256=(
                        manifest_mutation_owner_sha256
                    ),
                    lease_token=manifest_index_lease_token,
                )
            )
            if not manifest_index_updated:
                raise _fail("archive_index_rebuild_required")
        else:
            index_evidence = archive_services.require_current_zettel_index(root)
            if (
                not index_evidence.get("ok")
                and "archive_index_dirty"
                in set(index_evidence.get("reason_codes") or [])
            ):
                try:
                    (
                        manifest_index_generation,
                        manifest_index_began,
                        manifest_index_lease_token,
                    ) = archive_services.prepare_archive_manifest_index_mutation(
                        root,
                        operation_owner_sha256=(
                            manifest_mutation_owner_sha256
                        ),
                        expected_pre_manifest_sha256=(
                            plan.manifest_restore_sha256
                        ),
                        expected_post_manifest_sha256=(
                            plan.manifest_restore_sha256
                        ),
                    )
                except archive_services.ArchiveServiceError:
                    raise _fail("archive_index_rebuild_required") from None
                if manifest_index_began:
                    raise _fail("archive_index_rebuild_required")
                manifest_index_resumed = True
                manifest_index_updated = (
                    archive_services.replace_archive_index_manifest_projection(
                        root,
                        expected_generation=manifest_index_generation,
                        expected_manifest_sha256=(
                            plan.manifest_restore_sha256
                        ),
                        expected_mutation_owner_sha256=(
                            manifest_mutation_owner_sha256
                        ),
                        lease_token=manifest_index_lease_token,
                    )
                )
                if not manifest_index_updated:
                    raise _fail("archive_index_rebuild_required")

        receipt_raw = _canonical_bytes(
            _revert_receipt_document(
                plan,
                revert_id=revert_id,
                approval_reference=mutation_approval_reference,
                approval_supersession=journal.get("approval_supersession"),
            )
        )
        _create_or_exact_revert_file(
            root,
            receipt_path,
            receipt_raw,
            maximum_bytes=MAX_RECEIPT_BYTES,
        )
        if plan.source_evidence_kind != "successful_receipt":
            compensation_raw = _canonical_bytes(
                _terminal_compensation_document(
                    plan,
                    source_journal_raw=plan._source_journal_bytes,
                    revert_started_journal_raw=journal_raw,
                    revert_receipt_raw=receipt_raw,
                )
            )
            _create_or_exact_revert_file(
                root,
                _terminal_compensation_path(
                    root,
                    _strict_json_document(plan._source_journal_bytes)[
                        "plan_sha256"
                    ],
                ),
                compensation_raw,
                maximum_bytes=MAX_RECEIPT_BYTES,
            )

        started = _revert_started_journal_document(
            plan,
            revert_id=revert_id,
            approval_reference=mutation_approval_reference,
            approval_supersession=journal.get("approval_supersession"),
        )
        pending = _revert_finalization_pending_journal_document(
            started,
            receipt_raw=receipt_raw,
            pending_finalization_approval_reference=approval_reference,
        )
        pending_payload = _canonical_bytes(pending)
        pending["terminal_authentication"] = (
            _terminal_authentication_document(
                approval_claim.exact_terminal_record_mac(pending_payload)
            )
        )
        pending_raw = _canonical_bytes(pending)
        if journal_raw != pending_raw:
            _replace_or_exact_revert_file(
                root,
                journal_path,
                pending_raw,
                maximum_bytes=MAX_RECEIPT_BYTES,
            )
        return {
            "schema_version": REVERT_RESULT_SCHEMA_VERSION,
            "ok": True,
            "reason_code": "duplicate_object_exact_revert_succeeded",
            "plan_sha256": plan.plan_sha256,
            "source_evidence_kind": plan.source_evidence_kind,
            "source_evidence_sha256": plan.source_evidence_sha256,
            "source_journal_sha256": plan.source_journal_sha256,
            "source_receipt_sha256": plan.source_receipt_sha256,
            "manifest_before_revert_sha256": plan.manifest_current_sha256,
            "manifest_after_revert_sha256": plan.manifest_restore_sha256,
            "restored_exact_original_manifest_bytes": True,
            "restored_change_counts": {
                "exact_duplicate_rows": plan.removed_exact_duplicate_row_count,
                "canonical_external_pairs": (
                    plan.reconciled_canonical_external_pair_count
                ),
            },
            "post_state_snapshot_preserved": True,
            "receipt_created": True,
            "manifest_write_performed_this_run": manifest_write_performed,
            "finalize_only": not manifest_write_performed,
            "interrupted_source_journal_finalized_rolled_back": False,
            "object_ids_echoed": False,
            "paths_echoed": False,
            "row_content_echoed": False,
            "generated_index_updated": manifest_index_updated,
            "index_generation": manifest_index_generation,
            "index_mutation_resumed": manifest_index_resumed,
        }
    except DuplicateObjectReconciliationError:
        if manifest_mutation_attempted and manifest_index_generation is not None:
            archive_services.mark_archive_index_dirty(
                root,
                expected_generation=manifest_index_generation,
                expected_mutation_owner_sha256=manifest_mutation_owner_sha256,
                lease_token=manifest_index_lease_token,
            )
        raise
    except BaseException:
        if manifest_mutation_attempted and manifest_index_generation is not None:
            archive_services.mark_archive_index_dirty(
                root,
                expected_generation=manifest_index_generation,
                expected_mutation_owner_sha256=manifest_mutation_owner_sha256,
                lease_token=manifest_index_lease_token,
            )
        raise _fail("duplicate_object_revert_state_unknown") from None


def _finalize_duplicate_object_reconciliation_revert_core(
    plan: _DuplicateObjectReconciliationRevertPlan,
    finalization_claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
) -> None:
    """Seal one restored revert only after its claim is durably succeeded."""

    if (
        type(plan) is not _DuplicateObjectReconciliationRevertPlan
        or type(finalization_claim) is not _ClaimedExactHumanApproval
        or type(context) is not ExactHumanApprovalContext
        or context.operation
        is not ExactHumanApprovalOperation.duplicate_object_reconcile
        or context.plan_sha256 != plan.plan_sha256
        or context.target_binding_sha256 != plan.manifest_current_sha256
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    try:
        finalization_reference = finalization_claim.assert_succeeded_for_context(
            context
        )
    except ExactHumanApprovalError:
        raise _fail("duplicate_object_revert_evidence_invalid") from None

    root, archive_id = _safe_root(plan.archive_root)
    if root != plan.archive_root or archive_id != plan.archive_id:
        raise _fail("duplicate_object_revert_evidence_invalid")
    current_manifest = _read_manifest(root)
    if current_manifest != plan._manifest_restore_bytes:
        raise _fail("duplicate_object_revert_evidence_invalid")
    terminal_auditor = _claim_terminal_auditor(finalization_claim)
    execution = _inspect_revert_execution(
        root,
        plan,
        current_manifest=current_manifest,
        terminal_auditor=terminal_auditor,
    )
    journal = execution["journal"]
    receipt_raw = execution["receipt_raw"]
    if journal is None or receipt_raw is None:
        raise _fail("duplicate_object_revert_evidence_invalid")
    if journal["status"] == "succeeded":
        if journal.get("finalization_approval_reference") != finalization_reference:
            raise _fail("duplicate_object_revert_evidence_invalid")
        return
    if (
        journal["status"] != "finalization_pending"
        or journal.get("pending_finalization_approval_reference")
        != finalization_reference
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")

    fresh = _plan_duplicate_object_reconciliation_revert_core(
        root,
        terminal_auditor=terminal_auditor,
    )
    if not _same_revert_plan(plan, fresh):
        raise _fail("duplicate_object_revert_evidence_invalid")
    started = _revert_started_journal_document(
        plan,
        revert_id=execution["revert_id"],
        approval_reference=journal["approval_reference"],
        approval_supersession=journal.get("approval_supersession"),
    )
    finalized = _revert_succeeded_journal_document(
        started,
        receipt_raw=receipt_raw,
        finalization_claim=finalization_claim,
        context=context,
    )
    finalized_raw = _canonical_bytes(finalized)
    _replace_or_exact_revert_file(
        root,
        execution["journal_path"],
        finalized_raw,
        maximum_bytes=MAX_RECEIPT_BYTES,
    )
    reread = _read_safe_internal_file(
        root,
        execution["journal_path"],
        maximum_bytes=MAX_RECEIPT_BYTES,
    )
    _revert_journal_is_exact_for_plan(
        plan,
        revert_id=execution["revert_id"],
        raw=reread,
        terminal_auditor=terminal_auditor,
    )


def _duplicate_object_reconciliation_revert_resume_approval_id(
    plan: _DuplicateObjectReconciliationRevertPlan,
    *,
    terminal_auditor: _TerminalApprovalAuditor,
) -> str:
    """Return only the exact pending claim id needed for no-dialog resume."""

    if type(plan) is not _DuplicateObjectReconciliationRevertPlan or not callable(
        terminal_auditor
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    root, archive_id = _safe_root(plan.archive_root)
    if root != plan.archive_root or archive_id != plan.archive_id:
        raise _fail("duplicate_object_revert_evidence_invalid")
    current_manifest = _read_manifest(root)
    if current_manifest not in {
        plan._manifest_current_bytes,
        plan._manifest_restore_bytes,
    }:
        raise _fail("duplicate_object_revert_evidence_invalid")
    execution = _inspect_revert_execution(
        root,
        plan,
        current_manifest=current_manifest,
        terminal_auditor=terminal_auditor,
    )
    journal = execution["journal"]
    if journal is None or journal["status"] not in {
        "started",
        "finalization_pending",
    }:
        raise _fail("duplicate_object_revert_evidence_invalid")
    reference = (
        journal.get("pending_finalization_approval_reference")
        if journal["status"] == "finalization_pending"
        else journal.get("approval_reference")
    )
    if not _approval_reference_is_exact(reference):
        raise _fail("duplicate_object_revert_evidence_invalid")
    return str(reference["approval_id"])


def _duplicate_object_reconciliation_revert_resume_checkpoint_matches(
    plan: _DuplicateObjectReconciliationRevertPlan,
    claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
    expected_claim_status: str,
) -> bool:
    """Read-only guard for started-writer and succeeded-finalizer resume tails."""

    try:
        if (
            type(plan) is not _DuplicateObjectReconciliationRevertPlan
            or type(claim) is not _ClaimedExactHumanApproval
            or type(context) is not ExactHumanApprovalContext
            or expected_claim_status not in {"started", "succeeded"}
            or claim.status != expected_claim_status
            or context.operation
            is not ExactHumanApprovalOperation.duplicate_object_reconcile
            or context.plan_sha256 != plan.plan_sha256
            or context.target_binding_sha256 != plan.manifest_current_sha256
        ):
            return False
        reference = (
            claim.assert_ready_for_context(context)
            if expected_claim_status == "started"
            else claim.assert_succeeded_for_context(context)
        )
        root, archive_id = _safe_root(plan.archive_root)
        if root != plan.archive_root or archive_id != plan.archive_id:
            return False
        current_manifest = _read_manifest(root)
        if current_manifest not in {
            plan._manifest_current_bytes,
            plan._manifest_restore_bytes,
        }:
            return False
        execution = _inspect_revert_execution(
            root,
            plan,
            current_manifest=current_manifest,
            terminal_auditor=_claim_terminal_auditor(claim),
        )
        journal = execution["journal"]
        if journal is None:
            return False
        if journal["status"] == "started":
            return bool(
                expected_claim_status == "started"
                and journal.get("approval_reference") == reference
            )
        if journal["status"] == "finalization_pending":
            return bool(
                journal.get("pending_finalization_approval_reference")
                == reference
                and execution["receipt_raw"] is not None
                and current_manifest == plan._manifest_restore_bytes
            )
        return False
    except BaseException:
        return False


def _optional_safe_internal_file(
    root: Path,
    path: Path,
    *,
    maximum_bytes: int,
) -> bytes | None:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return None
    except OSError:
        raise _fail("duplicate_object_reconciliation_conflict") from None
    return _read_safe_internal_file(
        root,
        path,
        maximum_bytes=maximum_bytes,
    )


def _forward_started_journal_document(
    plan: _DuplicateObjectReconciliationPlan,
    *,
    reconciliation_id: str,
    approval_reference: Mapping[str, Any],
    approval_supersession: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    document = {
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "reconciliation_id": reconciliation_id,
        "plan_sha256": plan.plan_sha256,
        "manifest_before_sha256": plan.manifest_sha256,
        "manifest_after_sha256": _sha256(plan._replacement_bytes),
        "unresolved_inventory_sha256": plan.unresolved_inventory_sha256,
        "plan_basis": dict(plan._plan_basis),
        "approval_reference": dict(approval_reference),
        "status": "started",
        "snapshot_created": True,
        "manifest_replaced": False,
        "receipt_created": False,
    }
    if approval_supersession is not None:
        document["approval_supersession"] = dict(approval_supersession)
    return document


def _forward_succeeded_journal_document(
    started: Mapping[str, Any],
    *,
    receipt_raw: bytes,
    approval_claim: _ClaimedExactHumanApproval,
) -> dict[str, Any]:
    document = dict(started)
    document.update(
        {
            "status": "succeeded",
            "manifest_replaced": True,
            "receipt_created": True,
            "receipt_sha256": _sha256(receipt_raw),
        }
    )
    payload = _canonical_bytes(document)
    mac = approval_claim.exact_terminal_record_mac(payload)
    document["terminal_authentication"] = _terminal_authentication_document(mac)
    return document


def _forward_journal_binding_context(
    journal: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        key: journal.get(key)
        for key in (
            "schema_version",
            "reconciliation_id",
            "plan_sha256",
            "manifest_before_sha256",
            "manifest_after_sha256",
            "unresolved_inventory_sha256",
            "plan_basis",
        )
    }


def _approval_supersession_document(
    *,
    superseded_journal_raw: bytes,
    superseded_reference: Mapping[str, Any],
    replacement_reference: Mapping[str, Any],
    manifest_sha256: str,
    include_superseded_journal_evidence: bool = False,
) -> dict[str, Any]:
    document = {
        "schema_version": (
            "wom-kit/duplicate-object-prewrite-approval-supersession/v0.1"
        ),
        "reason_code": "interrupted_prewrite_approval_superseded",
        "superseded_journal_sha256": _sha256(superseded_journal_raw),
        "superseded_approval_reference_sha256": _sha256(
            _canonical_bytes(superseded_reference)
        ),
        "replacement_approval_reference_sha256": _sha256(
            _canonical_bytes(replacement_reference)
        ),
        "manifest_sha256": manifest_sha256,
        "mutation_had_not_started": True,
    }
    if include_superseded_journal_evidence:
        document["superseded_journal_evidence"] = {
            "schema_version": (
                "wom-kit/duplicate-object-superseded-started-journal/v0.1"
            ),
            "journal": _strict_json_document(superseded_journal_raw),
        }
    return document


def _approval_supersession_is_exact(
    value: Any,
    *,
    manifest_sha256: str,
    replacement_reference: Mapping[str, Any],
    require_superseded_journal_evidence: bool = False,
    forward_journal_context: Mapping[str, Any] | None = None,
    supersession_depth: int = 0,
) -> bool:
    if supersession_depth >= _MAX_APPROVAL_SUPERSESSION_DEPTH:
        return False
    if type(value) is not dict:
        return False
    expected_keys = {
        "schema_version",
        "reason_code",
        "superseded_journal_sha256",
        "superseded_approval_reference_sha256",
        "replacement_approval_reference_sha256",
        "manifest_sha256",
        "mutation_had_not_started",
    }
    if require_superseded_journal_evidence:
        expected_keys.add("superseded_journal_evidence")
    basic_is_exact = bool(
        set(value) == expected_keys
        and value.get("schema_version")
        == "wom-kit/duplicate-object-prewrite-approval-supersession/v0.1"
        and value.get("reason_code")
        == "interrupted_prewrite_approval_superseded"
        and type(value.get("superseded_journal_sha256")) is str
        and _SHA256_RE.fullmatch(value["superseded_journal_sha256"])
        is not None
        and type(value.get("superseded_approval_reference_sha256")) is str
        and _SHA256_RE.fullmatch(
            value["superseded_approval_reference_sha256"]
        )
        is not None
        and value.get("replacement_approval_reference_sha256")
        == _sha256(_canonical_bytes(replacement_reference))
        and value.get("manifest_sha256") == manifest_sha256
        and value.get("mutation_had_not_started") is True
    )
    if not basic_is_exact:
        return False
    if not require_superseded_journal_evidence:
        return True
    evidence = value.get("superseded_journal_evidence")
    if (
        type(evidence) is not dict
        or set(evidence) != {"schema_version", "journal"}
        or evidence.get("schema_version")
        != "wom-kit/duplicate-object-superseded-started-journal/v0.1"
        or type(evidence.get("journal")) is not dict
        or not isinstance(forward_journal_context, Mapping)
    ):
        return False
    superseded_journal = evidence["journal"]
    expected_started_keys = {
        "schema_version",
        "reconciliation_id",
        "plan_sha256",
        "manifest_before_sha256",
        "manifest_after_sha256",
        "unresolved_inventory_sha256",
        "plan_basis",
        "approval_reference",
        "status",
        "snapshot_created",
        "manifest_replaced",
        "receipt_created",
    }
    nested_supersession = superseded_journal.get("approval_supersession")
    if nested_supersession is not None:
        expected_started_keys.add("approval_supersession")
    superseded_reference = superseded_journal.get("approval_reference")
    if (
        set(superseded_journal) != expected_started_keys
        or _sha256(_canonical_bytes(superseded_journal))
        != value.get("superseded_journal_sha256")
        or not _approval_reference_is_exact(superseded_reference)
        or _sha256(_canonical_bytes(superseded_reference))
        != value.get("superseded_approval_reference_sha256")
        or superseded_journal.get("status") != "started"
        or superseded_journal.get("snapshot_created") is not True
        or superseded_journal.get("manifest_replaced") is not False
        or superseded_journal.get("receipt_created") is not False
        or any(
            superseded_journal.get(key) != forward_journal_context.get(key)
            for key in (
                "schema_version",
                "reconciliation_id",
                "plan_sha256",
                "manifest_before_sha256",
                "manifest_after_sha256",
                "unresolved_inventory_sha256",
                "plan_basis",
            )
        )
    ):
        return False
    return bool(
        nested_supersession is None
        or _approval_supersession_is_exact(
            nested_supersession,
            manifest_sha256=manifest_sha256,
            replacement_reference=superseded_reference,
            require_superseded_journal_evidence=True,
            forward_journal_context=forward_journal_context,
            supersession_depth=supersession_depth + 1,
        )
    )


def _validated_started_forward_journal(
    plan: _DuplicateObjectReconciliationPlan,
    *,
    reconciliation_id: str,
    raw: bytes,
) -> dict[str, Any]:
    document = _strict_json_document(raw)
    approval_reference = document.get("approval_reference", {})
    approval_supersession = document.get("approval_supersession")
    if (
        _canonical_bytes(document) != raw
        or document
        != _forward_started_journal_document(
            plan,
            reconciliation_id=reconciliation_id,
            approval_reference=approval_reference,
            approval_supersession=approval_supersession,
        )
        or not _approval_reference_is_exact(approval_reference)
        or (
            approval_supersession is not None
            and not _approval_supersession_is_exact(
                approval_supersession,
                manifest_sha256=plan.manifest_sha256,
                replacement_reference=approval_reference,
                require_superseded_journal_evidence=True,
                forward_journal_context=_forward_journal_binding_context(
                    document
                ),
            )
        )
    ):
        raise _fail("duplicate_object_reconciliation_conflict")
    return document


def _apply_duplicate_object_reconciliation_core(
    plan: _DuplicateObjectReconciliationPlan,
    approval_claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
) -> dict[str, Any]:
    if type(plan) is not _DuplicateObjectReconciliationPlan or not plan.approveable:
        raise _fail("duplicate_object_human_resolution_required")
    root, archive_id = _safe_root(plan.archive_root)
    if archive_id != plan.archive_id or root != plan.archive_root:
        raise _fail("duplicate_object_plan_invalid")
    manifest_mutation_owner_sha256 = (
        archive_services.archive_manifest_mutation_owner_sha256(
            operation="duplicate_object_reconcile",
            operation_binding_sha256=plan.plan_sha256,
        )
    )
    try:
        archive_services.require_archive_manifest_index_mutation_authority(
            root,
            operation_owner_sha256=manifest_mutation_owner_sha256,
            expected_pre_manifest_sha256=plan.manifest_sha256,
            expected_post_manifest_sha256=_sha256(plan._replacement_bytes),
        )
    except archive_services.ArchiveServiceError:
        raise _fail("archive_index_rebuild_required") from None
    with archive_services._ObjetCaptureManifestLock(root):
        return _apply_duplicate_object_reconciliation_locked_core(
            plan,
            approval_claim,
            context=context,
        )


def _apply_duplicate_object_reconciliation_locked_core(
    plan: _DuplicateObjectReconciliationPlan,
    approval_claim: _ClaimedExactHumanApproval,
    *,
    context: ExactHumanApprovalContext,
) -> dict[str, Any]:
    """Apply one bounded duplicate plan from a current authenticated claim.

    The shared exact-human workflow owns terminal claim finalization.  This
    writer only reauthenticates the still-started concrete claim immediately
    before its first mutation and stores the reference returned by that check.
    """

    if type(plan) is not _DuplicateObjectReconciliationPlan or not plan.approveable:
        raise _fail("duplicate_object_human_resolution_required")
    if (
        type(approval_claim) is not _ClaimedExactHumanApproval
        or type(context) is not ExactHumanApprovalContext
        or context.operation is not ExactHumanApprovalOperation.duplicate_object_reconcile
        or context.plan_sha256 != plan.plan_sha256
        or context.target_binding_sha256 != plan.manifest_sha256
    ):
        raise _fail("duplicate_object_approval_required")

    root, archive_id = _safe_root(plan.archive_root)
    if archive_id != plan.archive_id or root != plan.archive_root:
        raise _fail("duplicate_object_plan_invalid")
    manifest_mutation_owner_sha256 = (
        archive_services.archive_manifest_mutation_owner_sha256(
            operation="duplicate_object_reconcile",
            operation_binding_sha256=plan.plan_sha256,
        )
    )
    current = _read_manifest(root)
    if current != plan._manifest_bytes:
        raise _fail("duplicate_object_manifest_changed")

    reconcile_id = plan.plan_sha256.removeprefix("sha256:")[:24]
    lock_path = root.joinpath(*LOCK_ROOT.parts, f"{reconcile_id}.lock")
    snapshot_path = root.joinpath(*SNAPSHOT_ROOT.parts, f"{reconcile_id}.manifest.bin")
    journal_path = root.joinpath(*JOURNAL_ROOT.parts, f"{reconcile_id}.json")
    receipt_path = root.joinpath(*RECEIPT_ROOT.parts, f"{reconcile_id}.json")
    lock_descriptor = -1
    lock_created = False
    manifest_replaced = False
    manifest_mutation_attempted = False
    manifest_index_generation: str | None = None
    manifest_index_lease_token: (
        archive_services.ArchiveIndexMutationLeaseToken | None
    ) = None
    manifest_index_resumed = False
    manifest_index_updated = False
    try:
        try:
            approval_reference = (
                _ClaimedExactHumanApproval.assert_ready_for_context(
                    approval_claim,
                    context,
                )
            )
        except ExactHumanApprovalError:
            raise _fail("duplicate_object_approval_required") from None

        # Reparse the manifest and independently stream every eligible local
        # object again after approval, immediately before the lock that begins
        # mutation.  A path, size, identity, or byte drift invalidates the
        # approved plan without producing snapshots or receipts.
        fresh_plan = _plan_duplicate_object_reconciliation_core(
            root,
            terminal_auditor=_claim_terminal_auditor(approval_claim),
        )
        if (
            fresh_plan.manifest_sha256 != plan.manifest_sha256
            or fresh_plan.plan_sha256 != plan.plan_sha256
            or fresh_plan._replacement_bytes != plan._replacement_bytes
        ):
            raise _fail("duplicate_object_local_evidence_changed")
        try:
            archive_services.require_archive_manifest_index_mutation_authority(
                root,
                operation_owner_sha256=manifest_mutation_owner_sha256,
                expected_pre_manifest_sha256=plan.manifest_sha256,
                expected_post_manifest_sha256=_sha256(
                    plan._replacement_bytes
                ),
            )
        except archive_services.ArchiveServiceError:
            raise _fail("archive_index_rebuild_required") from None

        existing_lock = _optional_safe_internal_file(
            root,
            lock_path,
            maximum_bytes=256,
        )
        existing_snapshot = _optional_safe_internal_file(
            root,
            snapshot_path,
            maximum_bytes=MAX_MANIFEST_BYTES,
        )
        existing_journal = _optional_safe_internal_file(
            root,
            journal_path,
            maximum_bytes=MAX_RECEIPT_BYTES,
        )
        existing_receipt = _optional_safe_internal_file(
            root,
            receipt_path,
            maximum_bytes=MAX_RECEIPT_BYTES,
        )
        if (
            existing_receipt is not None
            or existing_lock
            not in {None, plan.plan_sha256.encode("ascii") + b"\n"}
            or existing_snapshot not in {None, plan._manifest_bytes}
            or (existing_journal is not None and existing_snapshot is None)
        ):
            raise _fail("duplicate_object_reconciliation_conflict")
        if existing_journal is not None:
            journal = _validated_started_forward_journal(
                plan,
                reconciliation_id=reconcile_id,
                raw=existing_journal,
            )
            try:
                prior_claim_status = (
                    approval_claim.approval_integrity_reference_status(
                        journal["approval_reference"],
                        expected_operation=(
                            ExactHumanApprovalOperation.duplicate_object_reconcile
                        ),
                        expected_plan_sha256=plan.plan_sha256,
                        expected_target_binding_sha256=plan.manifest_sha256,
                    )
                )
            except ExactHumanApprovalError:
                raise _fail("duplicate_object_reconciliation_conflict") from None
            if prior_claim_status != "started":
                raise _fail("duplicate_object_reconciliation_conflict")
            prior_supersession = journal.get("approval_supersession")
            if prior_supersession is not None:
                try:
                    for superseded_reference in _superseded_approval_references(
                        prior_supersession
                    ):
                        superseded_status = (
                            approval_claim.approval_integrity_reference_status(
                                superseded_reference,
                                expected_operation=(
                                    ExactHumanApprovalOperation
                                    .duplicate_object_reconcile
                                ),
                                expected_plan_sha256=plan.plan_sha256,
                                expected_target_binding_sha256=(
                                    plan.manifest_sha256
                                ),
                            )
                        )
                        if superseded_status != "started":
                            raise _fail(
                                "duplicate_object_reconciliation_conflict"
                            )
                except ExactHumanApprovalError:
                    raise _fail(
                        "duplicate_object_reconciliation_conflict"
                    ) from None
            prior_reference = dict(journal["approval_reference"])
            if prior_reference != approval_reference:
                if (
                    prior_supersession is not None
                    and len(
                        _superseded_approval_references(prior_supersession)
                    )
                    >= _MAX_APPROVAL_SUPERSESSION_DEPTH
                ):
                    raise _fail("duplicate_object_reconciliation_conflict")
                supersession = _approval_supersession_document(
                    superseded_journal_raw=existing_journal,
                    superseded_reference=prior_reference,
                    replacement_reference=approval_reference,
                    manifest_sha256=plan.manifest_sha256,
                    include_superseded_journal_evidence=True,
                )
                journal = _forward_started_journal_document(
                    plan,
                    reconciliation_id=reconcile_id,
                    approval_reference=approval_reference,
                    approval_supersession=supersession,
                )
                replacement_journal_raw = _canonical_bytes(journal)
                try:
                    _atomic_replace(root, journal_path, replacement_journal_raw)
                except BaseException:
                    if _read_safe_internal_file(
                        root,
                        journal_path,
                        maximum_bytes=MAX_RECEIPT_BYTES,
                    ) != replacement_journal_raw:
                        raise _fail(
                            "duplicate_object_reconciliation_conflict"
                        ) from None
                existing_journal = replacement_journal_raw
        else:
            journal = _forward_started_journal_document(
                plan,
                reconciliation_id=reconcile_id,
                approval_reference=approval_reference,
            )

        # This is the first mutation boundary.  The authenticated started
        # claim above is deliberately rechecked after every read-only preflight.
        if existing_lock is None:
            _assert_internal_parents(root, lock_path, create=True)
            lock_descriptor = os.open(
                lock_path,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | int(getattr(os, "O_BINARY", 0)),
                0o600,
            )
            lock_created = True
            os.write(lock_descriptor, plan.plan_sha256.encode("ascii") + b"\n")
            os.fsync(lock_descriptor)

        if existing_snapshot is None:
            _create_only(root, snapshot_path, plan._manifest_bytes)
        if existing_journal is None:
            _create_only(root, journal_path, _canonical_bytes(journal))
        try:
            (
                manifest_index_generation,
                manifest_index_began,
                manifest_index_lease_token,
            ) = archive_services.prepare_archive_manifest_index_mutation(
                root,
                operation_owner_sha256=manifest_mutation_owner_sha256,
                expected_pre_manifest_sha256=plan.manifest_sha256,
                expected_post_manifest_sha256=_sha256(plan._replacement_bytes),
            )
        except archive_services.ArchiveServiceError:
            raise _fail("archive_index_rebuild_required") from None
        manifest_index_resumed = not manifest_index_began
        manifest_mutation_attempted = True
        _replace_manifest_compare_and_swap(
            root,
            expected_bytes=plan._manifest_bytes,
            replacement_bytes=plan._replacement_bytes,
            transaction_sha256=manifest_mutation_owner_sha256,
            swap_suffix=".duplicate-object-reconcile-manifest.swap",
            error_prefix="duplicate_object_reconcile",
        )
        manifest_replaced = True
        if _read_manifest(root) != plan._replacement_bytes:
            raise OSError("manifest_verification_failed")
        manifest_index_updated = (
            archive_services.replace_archive_index_manifest_projection(
                root,
                expected_generation=manifest_index_generation,
                expected_manifest_sha256=_sha256(plan._replacement_bytes),
                expected_mutation_owner_sha256=(
                    manifest_mutation_owner_sha256
                ),
                lease_token=manifest_index_lease_token,
            )
        )
        if not manifest_index_updated:
            raise _fail("archive_index_rebuild_required")
        receipt = _forward_receipt_document(
            plan,
            reconciliation_id=reconcile_id,
            approval_reference=approval_reference,
            approval_supersession=journal.get("approval_supersession"),
        )
        receipt_raw = _canonical_bytes(receipt)
        _create_only(root, receipt_path, receipt_raw)
        finalized = _forward_succeeded_journal_document(
            journal,
            receipt_raw=receipt_raw,
            approval_claim=approval_claim,
        )
        _atomic_replace(root, journal_path, _canonical_bytes(finalized))
        unresolved_group_count = (
            plan.compatible_group_count + plan.conflicting_group_count
        )
        if plan.canonical_external_pair_group_count:
            reason_code = (
                "duplicate_object_reconciliation_succeeded_with_unresolved_groups"
                if unresolved_group_count
                else "duplicate_object_reconciliation_succeeded"
            )
        else:
            reason_code = (
                "duplicate_object_exact_rows_removed_with_unresolved_groups"
                if unresolved_group_count
                else "duplicate_object_exact_reconciliation_succeeded"
            )
        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "ok": True,
            "reason_code": reason_code,
            "plan_sha256": plan.plan_sha256,
            "manifest_before_sha256": plan.manifest_sha256,
            "manifest_after_sha256": _sha256(plan._replacement_bytes),
            "removed_exact_duplicate_row_count": plan.exact_removable_row_count,
            "reconciled_canonical_external_pair_count": (
                plan.canonical_external_pair_group_count
            ),
            "compatible_group_count": plan.compatible_group_count,
            "conflicting_group_count": plan.conflicting_group_count,
            "unresolved_group_count": unresolved_group_count,
            "human_resolution_still_required": bool(unresolved_group_count),
            "unresolved_inventory": {
                "schema_version": UNRESOLVED_INVENTORY_SCHEMA_VERSION,
                "group_count": unresolved_group_count,
                "inventory_sha256": plan.unresolved_inventory_sha256,
                "object_ids_echoed": False,
                "paths_echoed": False,
                "row_content_echoed": False,
            },
            "snapshot_preserved": True,
            "receipt_created": True,
            "automatic_merge_performed": False,
            "strict_human_approved_pair_reconciliation_performed": bool(
                plan.canonical_external_pair_group_count
            ),
            "unresolved_distinct_rows_modified": False,
            "object_ids_echoed": False,
            "paths_echoed": False,
            "generated_index_updated": manifest_index_updated,
            "index_generation": manifest_index_generation,
            "index_mutation_resumed": manifest_index_resumed,
        }
    except FileExistsError:
        raise _fail("duplicate_object_reconciliation_conflict") from None
    except DuplicateObjectReconciliationError:
        if manifest_mutation_attempted and manifest_index_generation is not None:
            archive_services.mark_archive_index_dirty(
                root,
                expected_generation=manifest_index_generation,
                expected_mutation_owner_sha256=manifest_mutation_owner_sha256,
                lease_token=manifest_index_lease_token,
            )
        raise
    except BaseException:
        if manifest_mutation_attempted and manifest_index_generation is not None:
            archive_services.mark_archive_index_dirty(
                root,
                expected_generation=manifest_index_generation,
                expected_mutation_owner_sha256=manifest_mutation_owner_sha256,
                lease_token=manifest_index_lease_token,
            )
        code = (
            "duplicate_object_reconciliation_state_unknown"
            if manifest_mutation_attempted
            else "duplicate_object_reconciliation_conflict"
        )
        raise _fail(code) from None
    finally:
        if lock_descriptor >= 0:
            os.close(lock_descriptor)
        # Keep a lock after an ambiguous/applied mutation as durable evidence.
        if lock_created and not manifest_mutation_attempted:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


__all__ = [
    "DuplicateObjectReconciliationError",
    "plan_duplicate_object_reconciliation",
    "plan_duplicate_object_reconciliation_revert",
]
