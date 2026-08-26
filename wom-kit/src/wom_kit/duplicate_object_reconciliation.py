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
from typing import Any, Mapping

import yaml

from .exact_human_approval import (
    _ClaimedExactHumanApproval,
    ExactHumanApprovalError,
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
_CORE_FIELDS = ("object_id", "sha256", "logical_key", "mime", "size_bytes")
_WINDOWS_REPARSE_ATTRIBUTE = 0x400


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
) -> _DuplicateObjectReconciliationPlan:
    root, archive_id = _safe_root(archive_root)
    manifest = _read_manifest(root)
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
    return _DuplicateObjectReconciliationPlan(
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
    )


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


@dataclass(frozen=True, repr=False)
class _DuplicateObjectReconciliationRevertPlan:
    archive_root: Path
    archive_id: str
    plan_sha256: str
    manifest_current_sha256: str
    manifest_restore_sha256: str
    source_receipt_sha256: str
    removed_exact_duplicate_row_count: int
    reconciled_canonical_external_pair_count: int
    _manifest_current_bytes: bytes
    _manifest_restore_bytes: bytes
    _source_reconciliation_id: str
    _source_receipt_bytes: bytes
    _source_journal_bytes: bytes

    def public_document(self) -> dict[str, Any]:
        return {
            "schema_version": REVERT_PLAN_SCHEMA_VERSION,
            "ok": True,
            "reason_code": "duplicate_object_exact_revert_ready",
            "plan_sha256": self.plan_sha256,
            "manifest_current_sha256": self.manifest_current_sha256,
            "manifest_restore_sha256": self.manifest_restore_sha256,
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


def _safe_receipt_paths(root: Path) -> list[Path]:
    directory = root.joinpath(*RECEIPT_ROOT.parts)
    try:
        _assert_internal_parents(root, directory / "candidate", create=False)
        directory_stat = os.lstat(directory)
    except FileNotFoundError:
        return []
    except (OSError, DuplicateObjectReconciliationError):
        raise _fail("duplicate_object_revert_evidence_invalid") from None
    if (
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


def _validated_revert_candidate(
    root: Path,
    *,
    receipt_path: Path,
    current_manifest: bytes,
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
        or type(reconcile_id) is not str
        or _RECONCILIATION_ID_RE.fullmatch(reconcile_id) is None
        or type(plan_sha) is not str
        or _SHA256_RE.fullmatch(plan_sha) is None
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
    if (
        _sha256(snapshot_raw) != before_sha
        or journal.get("schema_version") != JOURNAL_SCHEMA_VERSION
        or journal.get("reconciliation_id") != reconcile_id
        or journal.get("plan_sha256") != plan_sha
        or journal.get("manifest_before_sha256") != before_sha
        or journal.get("manifest_after_sha256") != after_sha
        or journal.get("status") != "succeeded"
        or journal.get("receipt_created") is not True
        or journal.get("receipt_sha256") != _sha256(receipt_raw)
    ):
        raise _fail("duplicate_object_revert_evidence_invalid")
    if _sha256(current_manifest) != after_sha:
        return None
    archive_id = _safe_root(root)[1]
    source_receipt_sha = _sha256(receipt_raw)
    plan_basis = {
        "schema_version": REVERT_PLAN_SCHEMA_VERSION,
        "archive_identity_sha256": exact_human_approval_archive_identity_sha256(
            archive_id
        ),
        "manifest_current_sha256": after_sha,
        "manifest_restore_sha256": before_sha,
        "source_receipt_sha256": source_receipt_sha,
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
        source_receipt_sha256=source_receipt_sha,
        removed_exact_duplicate_row_count=exact_removed,
        reconciled_canonical_external_pair_count=pair_count,
        _manifest_current_bytes=current_manifest,
        _manifest_restore_bytes=snapshot_raw,
        _source_reconciliation_id=reconcile_id,
        _source_receipt_bytes=receipt_raw,
        _source_journal_bytes=journal_raw,
    )


def _plan_duplicate_object_reconciliation_revert_core(
    archive_root: Path | str,
) -> _DuplicateObjectReconciliationRevertPlan:
    root, _archive_id = _safe_root(archive_root)
    current = _read_manifest(root)
    candidates: list[_DuplicateObjectReconciliationRevertPlan] = []
    for receipt_path in _safe_receipt_paths(root):
        candidate = _validated_revert_candidate(
            root,
            receipt_path=receipt_path,
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
    return _plan_duplicate_object_reconciliation_revert_core(
        archive_root
    ).public_document()


def _duplicate_object_reconciliation_revert_context(
    plan: _DuplicateObjectReconciliationRevertPlan,
    *,
    reviewer_claim: str,
) -> ExactHumanApprovalContext:
    if type(plan) is not _DuplicateObjectReconciliationRevertPlan:
        raise _fail("duplicate_object_revert_plan_invalid")
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
            "successful_reconciliation_receipt_digest",
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
        and left.source_receipt_sha256 == right.source_receipt_sha256
        and left._manifest_current_bytes == right._manifest_current_bytes
        and left._manifest_restore_bytes == right._manifest_restore_bytes
        and left._source_receipt_bytes == right._source_receipt_bytes
        and left._source_journal_bytes == right._source_journal_bytes
    )


def _apply_duplicate_object_reconciliation_revert_core(
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
    if _read_manifest(root) != plan._manifest_current_bytes:
        raise _fail("duplicate_object_manifest_changed")
    try:
        approval_reference = _ClaimedExactHumanApproval.assert_ready_for_context(
            approval_claim, context
        )
    except ExactHumanApprovalError:
        raise _fail("duplicate_object_revert_approval_required") from None

    # This rediscovery verifies there is still exactly one applicable receipt,
    # rereads the create-only snapshot and journal, and proves current==post
    # immediately before the first mutation.
    fresh = _plan_duplicate_object_reconciliation_revert_core(root)
    if not _same_revert_plan(plan, fresh):
        raise _fail("duplicate_object_revert_evidence_invalid")

    revert_id = plan.plan_sha256.removeprefix("sha256:")[:24]
    lock_path = root.joinpath(*REVERT_LOCK_ROOT.parts, f"{revert_id}.lock")
    post_snapshot_path = root.joinpath(
        *REVERT_SNAPSHOT_ROOT.parts, f"{revert_id}.post.manifest.bin"
    )
    journal_path = root.joinpath(*REVERT_JOURNAL_ROOT.parts, f"{revert_id}.json")
    receipt_path = root.joinpath(*REVERT_RECEIPT_ROOT.parts, f"{revert_id}.json")
    lock_descriptor = -1
    lock_created = False
    manifest_replaced = False
    try:
        _assert_internal_parents(root, lock_path, create=True)
        lock_descriptor = os.open(
            lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        lock_created = True
        os.write(lock_descriptor, plan.plan_sha256.encode("ascii") + b"\n")
        os.fsync(lock_descriptor)
        _create_only(root, post_snapshot_path, plan._manifest_current_bytes)
        journal = {
            "schema_version": REVERT_JOURNAL_SCHEMA_VERSION,
            "revert_id": revert_id,
            "plan_sha256": plan.plan_sha256,
            "source_receipt_sha256": plan.source_receipt_sha256,
            "manifest_before_revert_sha256": plan.manifest_current_sha256,
            "manifest_after_revert_sha256": plan.manifest_restore_sha256,
            "approval_reference": dict(approval_reference),
            "status": "started",
            "post_state_snapshot_created": True,
            "manifest_restored": False,
            "receipt_created": False,
        }
        _create_only(root, journal_path, _canonical_bytes(journal))
        _atomic_replace(root, _manifest_path(root), plan._manifest_restore_bytes)
        manifest_replaced = True
        if _read_manifest(root) != plan._manifest_restore_bytes:
            raise OSError("manifest_revert_verification_failed")
        receipt = {
            "schema_version": REVERT_RECEIPT_SCHEMA_VERSION,
            "revert_id": revert_id,
            "plan_sha256": plan.plan_sha256,
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
        receipt_raw = _canonical_bytes(receipt)
        _create_only(root, receipt_path, receipt_raw)
        finalized = dict(journal)
        finalized.update(
            {
                "status": "succeeded",
                "manifest_restored": True,
                "receipt_created": True,
                "receipt_sha256": _sha256(receipt_raw),
            }
        )
        _atomic_replace(root, journal_path, _canonical_bytes(finalized))
        return {
            "schema_version": REVERT_RESULT_SCHEMA_VERSION,
            "ok": True,
            "reason_code": "duplicate_object_exact_revert_succeeded",
            "plan_sha256": plan.plan_sha256,
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
            "object_ids_echoed": False,
            "paths_echoed": False,
            "row_content_echoed": False,
        }
    except FileExistsError:
        raise _fail("duplicate_object_revert_conflict") from None
    except DuplicateObjectReconciliationError:
        raise
    except BaseException:
        raise _fail(
            "duplicate_object_revert_state_unknown"
            if manifest_replaced
            else "duplicate_object_revert_conflict"
        ) from None
    finally:
        if lock_descriptor >= 0:
            os.close(lock_descriptor)
        if lock_created and not manifest_replaced:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


def _apply_duplicate_object_reconciliation_core(
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
        fresh_plan = _plan_duplicate_object_reconciliation_core(root)
        if (
            fresh_plan.manifest_sha256 != plan.manifest_sha256
            or fresh_plan.plan_sha256 != plan.plan_sha256
            or fresh_plan._replacement_bytes != plan._replacement_bytes
        ):
            raise _fail("duplicate_object_local_evidence_changed")

        # This is the first mutation boundary.  The authenticated started
        # claim above is deliberately rechecked after every read-only preflight.
        _assert_internal_parents(root, lock_path, create=True)
        lock_descriptor = os.open(
            lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        lock_created = True
        os.write(lock_descriptor, plan.plan_sha256.encode("ascii") + b"\n")
        os.fsync(lock_descriptor)

        _create_only(root, snapshot_path, plan._manifest_bytes)
        journal = {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "reconciliation_id": reconcile_id,
            "plan_sha256": plan.plan_sha256,
            "manifest_before_sha256": plan.manifest_sha256,
            "manifest_after_sha256": _sha256(plan._replacement_bytes),
            "unresolved_inventory_sha256": plan.unresolved_inventory_sha256,
            "approval_reference": dict(approval_reference),
            "status": "started",
            "snapshot_created": True,
            "manifest_replaced": False,
            "receipt_created": False,
        }
        _create_only(root, journal_path, _canonical_bytes(journal))
        _atomic_replace(root, _manifest_path(root), plan._replacement_bytes)
        manifest_replaced = True
        if _read_manifest(root) != plan._replacement_bytes:
            raise OSError("manifest_verification_failed")
        receipt = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "reconciliation_id": reconcile_id,
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
        _create_only(root, receipt_path, _canonical_bytes(receipt))
        finalized = dict(journal)
        finalized.update(
            {
                "status": "succeeded",
                "manifest_replaced": True,
                "receipt_created": True,
                "receipt_sha256": _sha256(_canonical_bytes(receipt)),
            }
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
        }
    except FileExistsError:
        raise _fail("duplicate_object_reconciliation_conflict") from None
    except DuplicateObjectReconciliationError:
        raise
    except BaseException:
        code = (
            "duplicate_object_reconciliation_state_unknown"
            if manifest_replaced
            else "duplicate_object_reconciliation_conflict"
        )
        raise _fail(code) from None
    finally:
        if lock_descriptor >= 0:
            os.close(lock_descriptor)
        # Keep a lock after an ambiguous/applied mutation as durable evidence.
        if lock_created and not manifest_replaced:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


__all__ = [
    "DuplicateObjectReconciliationError",
    "plan_duplicate_object_reconciliation",
    "plan_duplicate_object_reconciliation_revert",
]
