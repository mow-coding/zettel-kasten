"""Read-only observed source-reference coverage and storage-evidence audit.

The command deliberately distinguishes the current canonical population WOM
can enumerate from an archive-wide source population that does not yet have a
complete public authority.  Private identities remain internal and are
replaced by output-local ordinals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Iterable, Mapping, Sequence, TextIO


RESULT_SCHEMA_ID = "wom-kit/source-reference-coverage-audit-result/v0.1"
LIFECYCLE_ACTION = "source_reference_coverage_audit"
DEFAULT_MAX_ITEMS = 50
MAX_ITEMS = 500
MAX_ZETTEL_BYTES = 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_RECORDS = 1_000_000
OBJECT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
OBJET_REF_RE = re.compile(r"^objet:(sha256:[0-9a-f]{64})$")
FORMATS = frozenset({"json", "text"})
COVERAGE_STATES = (
    "recovered_durable_reference",
    "recoverable_candidate_only",
    "unrecovered_reference",
    "retry_residue",
    "not_applicable",
    "blocked_or_unknown",
)
STORAGE_STATES = (
    "recorded_time_evidence",
    "manifest_identity_only",
    "contradictory",
    "no_evidence",
    "not_applicable",
    "indeterminate",
)
AUTHORITY_FAMILIES = (
    "canonical_zettel_source_refs",
    "canonical_notion_omission_markers",
)
ISSUE_CODES = (
    "interpreter_no_bytecode_mode_required",
    "request_invalid",
    "archive_boundary_unsafe",
    "population_authority_unreadable",
    "population_authority_invalid",
    "population_authority_changed",
    "population_identity_conflict",
    "archive_wide_population_authority_unavailable",
    "storage_manifest_unreadable",
    "storage_manifest_invalid",
    "storage_evidence_contradictory",
    "storage_evidence_unreadable",
    "result_semantic_validation_failed",
    "result_serialization_blocked",
)
REASON_CODES = (
    "exact_durable_reference",
    "explicit_unrecovered_marker",
    "authority_unreadable",
    "authority_changed",
    "authority_invalid",
    "duplicate_identity_conflict",
    "exact_linked_provider_receipt",
    "exact_manifest_identity",
    "no_recorded_storage_evidence",
    "storage_evidence_unreadable",
    "storage_evidence_contradictory",
    "object_binding_absent",
    "reviewed_not_applicable",
)
EVIDENCE_KIND_CODES = (
    "population_authority",
    "durable_source_reference",
    "explicit_omission_marker",
    "object_manifest",
    "linked_provider_receipt",
    "none",
)
HELP_TEXT = (
    "usage: python -B -m wom_kit.archive_cli "
    "source-reference-coverage-audit <archive-root> --dry-run "
    "[--max-items <1..500>] [--progress] [--format json|text]\n"
    "options:\n"
    "  -h, --help\n"
    "  --dry-run\n"
    "  --max-items <1..500>\n"
    "  --progress\n"
    "  --format json|text"
)
_UNREADABLE_RECEIPT_CODES = frozenset(
    {
        "execution_receipt_missing_or_unsafe",
        "execution_receipt_too_large",
        "execution_receipt_invalid_json",
        "execution_receipt_unreadable",
    }
)
_WINDOWS_REPARSE_ATTRIBUTE = 0x00000400


@dataclass
class AuditRequest:
    archive_root: str | None = None
    dry_run: bool = False
    max_items: int = DEFAULT_MAX_ITEMS
    progress: bool = False
    output_format: str = "text"
    help_requested: bool = False
    invalid: bool = False


@dataclass
class Occurrence:
    """Private internal occurrence; identity and object id are never emitted."""

    private_sort_key: tuple[str, int, int]
    zettel_identity: str
    authority_family: str
    coverage_state: str
    reason_codes: list[str]
    evidence_kind_codes: list[str]
    applicable: bool = True
    durable_reference_present: bool = False
    exact_object_binding: str | None = field(default=None, repr=False)
    identity_conflict: bool = False
    storage_state: str = "no_evidence"


@dataclass
class ManifestInventory:
    records_by_object: dict[str, list[dict[str, Any]]] = field(
        default_factory=dict
    )
    present: bool = False
    scan_complete: bool = True
    before_after_identity_equal: bool = True
    records_scanned: int = 0
    invalid_record_count: int = 0
    issue_codes: list[str] = field(default_factory=list)


class DuplicateJSONKeyError(ValueError):
    """Raised for duplicate JSON object keys."""


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values))


def _issue_counts(codes: Iterable[str]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for code in codes:
        normalized = str(code)
        if normalized not in ISSUE_CODES:
            normalized = "result_semantic_validation_failed"
        counts[normalized] = counts.get(normalized, 0) + 1
    return [
        {
            "severity": (
                "info"
                if code == "archive_wide_population_authority_unavailable"
                else "error"
            ),
            "code": code,
            "count": count,
        }
        for code, count in sorted(counts.items())
    ]


def _parse_request(argv: Sequence[str]) -> AuditRequest:
    request = AuditRequest()
    seen: set[str] = set()
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"-h", "--help"}:
            request.help_requested = True
            index += 1
            continue
        if token == "--dry-run":
            if token in seen:
                request.invalid = True
            seen.add(token)
            request.dry_run = True
            index += 1
            continue
        if token == "--progress":
            if token in seen:
                request.invalid = True
            seen.add(token)
            request.progress = True
            index += 1
            continue
        if token in {"--max-items", "--format"}:
            if token in seen or index + 1 >= len(argv):
                request.invalid = True
                index += 1
                continue
            seen.add(token)
            value = argv[index + 1]
            if token == "--max-items":
                if not re.fullmatch(r"[0-9]+", value):
                    request.invalid = True
                else:
                    parsed = int(value)
                    if not 1 <= parsed <= MAX_ITEMS:
                        request.invalid = True
                    else:
                        request.max_items = parsed
            else:
                if value not in FORMATS:
                    request.invalid = True
                else:
                    request.output_format = value
            index += 2
            continue
        if token.startswith("-"):
            request.invalid = True
            index += 1
            continue
        if request.archive_root is None:
            request.archive_root = token
        else:
            request.invalid = True
        index += 1
    if not request.help_requested and (
        request.archive_root is None or not request.dry_run
    ):
        request.invalid = True
    return request


def _progress(enabled: bool, stream: TextIO, phase: str) -> None:
    if enabled:
        print(f"SOURCE_REFERENCE_COVERAGE_AUDIT_PHASE={phase}", file=stream)


def _interpreter_started_with_no_bytecode_mode() -> bool:
    """Require an explicit Python ``-B`` option, not only an environment flag."""

    explicit_no_bytecode = any(
        argument == "-B"
        or (
            argument.startswith("-")
            and not argument.startswith("--")
            and "B" in argument[1:]
        )
        for argument in getattr(sys, "orig_argv", ())
    )
    return bool(sys.flags.dont_write_bytecode == 1 and explicit_no_bytecode)


def _is_reparse(value: os.stat_result) -> bool:
    return bool(
        getattr(value, "st_file_attributes", 0)
        & _WINDOWS_REPARSE_ATTRIBUTE
    )


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _read_stable_regular_file(
    path: Path,
    *,
    max_bytes: int,
    services: Any,
    root: Path,
) -> tuple[bytes | None, str | None]:
    """Read one owned regular file with a same-handle before/after identity."""

    try:
        if services.zet_revision_path_has_symlink_component(root, path):
            return None, "unsafe"
        before = os.lstat(path)
        if (
            stat.S_ISLNK(before.st_mode)
            or _is_reparse(before)
            or not stat.S_ISREG(before.st_mode)
        ):
            return None, "unsafe"
        if before.st_size > max_bytes:
            return None, "oversized"
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or _stat_identity(opened) != _stat_identity(before)
            ):
                return None, "changed"
            raw = handle.read(max_bytes + 1)
            opened_after = os.fstat(handle.fileno())
        after = os.lstat(path)
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "unreadable"
    if (
        len(raw) > max_bytes
        or len(raw) != before.st_size
        or _stat_identity(before) != _stat_identity(opened_after)
        or _stat_identity(opened_after) != _stat_identity(after)
    ):
        return None, "changed"
    return raw, None


def _normalize_object_binding(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if OBJECT_ID_RE.fullmatch(normalized):
        return normalized
    match = OBJET_REF_RE.fullmatch(normalized)
    return match.group(1) if match is not None else None


def _source_ref_binding(item: Mapping[str, Any]) -> str | None:
    for key in ("object_id", "objet_ref", "value"):
        binding = _normalize_object_binding(item.get(key))
        if binding is not None:
            return binding
    return None


def _valid_source_ref(item: Any) -> bool:
    if not isinstance(item, Mapping) or not item:
        return False
    if not all(isinstance(key, str) and key for key in item):
        return False
    return all(
        isinstance(item.get(key), str)
        and bool(item[key])
        and item[key] == item[key].strip()
        for key in ("type", "value")
    )


def _enumerate_canonical_zettel_paths(
    root: Path,
    services: Any,
) -> tuple[list[Path], bool, list[str]]:
    """Enumerate only ``zettels/`` and fail closed on unsafe/changing dirs."""

    zettels_root = root / "zettels"
    directory_generations: dict[Path, tuple[int, int, int, int]] = {}
    paths: list[Path] = []
    complete = True
    issues: list[str] = []
    try:
        root_stat = os.lstat(zettels_root)
        if (
            not stat.S_ISDIR(root_stat.st_mode)
            or stat.S_ISLNK(root_stat.st_mode)
            or _is_reparse(root_stat)
            or services.zet_revision_path_has_symlink_component(
                root,
                zettels_root,
            )
        ):
            return [], False, ["population_authority_unreadable"]
        for current_raw, directory_names, file_names in os.walk(
            zettels_root,
            topdown=True,
            followlinks=False,
        ):
            current = Path(current_raw)
            current_stat = os.lstat(current)
            if (
                not stat.S_ISDIR(current_stat.st_mode)
                or stat.S_ISLNK(current_stat.st_mode)
                or _is_reparse(current_stat)
            ):
                complete = False
                issues.append("population_authority_unreadable")
                directory_names[:] = []
                continue
            directory_generations[current] = _stat_identity(current_stat)

            safe_directory_names: list[str] = []
            for name in sorted(directory_names):
                child = current / name
                child_stat = os.lstat(child)
                if (
                    not stat.S_ISDIR(child_stat.st_mode)
                    or stat.S_ISLNK(child_stat.st_mode)
                    or _is_reparse(child_stat)
                ):
                    complete = False
                    issues.append("population_authority_unreadable")
                    continue
                safe_directory_names.append(name)
            directory_names[:] = safe_directory_names

            for name in sorted(file_names):
                if not name.endswith(".md"):
                    continue
                child = current / name
                child_stat = os.lstat(child)
                if (
                    not stat.S_ISREG(child_stat.st_mode)
                    or stat.S_ISLNK(child_stat.st_mode)
                    or _is_reparse(child_stat)
                ):
                    complete = False
                    issues.append("population_authority_unreadable")
                    continue
                paths.append(child)
    except (OSError, RuntimeError, ValueError):
        return [], False, ["population_authority_unreadable"]

    for directory, before in directory_generations.items():
        try:
            after = os.lstat(directory)
        except OSError:
            complete = False
            issues.append("population_authority_changed")
            continue
        if _stat_identity(after) != before:
            complete = False
            issues.append("population_authority_changed")
    return (
        sorted(paths, key=lambda path: path.relative_to(root).as_posix()),
        complete,
        _unique(issues),
    )


def _scan_observed_population(
    root: Path,
    archive_id: str,
    services: Any,
) -> tuple[list[Occurrence], bool, list[str], int]:
    occurrences: list[Occurrence] = []
    complete = True
    issue_codes: list[str] = []
    authority_files_scanned = 0
    identity_to_occurrence_indexes: dict[str, list[int]] = {}
    identity_to_paths: dict[str, set[str]] = {}
    path_to_occurrence_indexes: dict[Path, list[int]] = {}
    path_generations: dict[Path, tuple[int, int, int, int]] = {}
    (
        zettel_paths,
        enumeration_complete,
        enumeration_issues,
    ) = _enumerate_canonical_zettel_paths(root, services)
    complete = enumeration_complete
    issue_codes.extend(enumeration_issues)

    for path in zettel_paths:
        try:
            outer_before = os.lstat(path)
        except OSError:
            complete = False
            issue_codes.append("population_authority_changed")
            continue
        snapshot = services.validated_approval_zettel_snapshot(
            path,
            max_bytes=MAX_ZETTEL_BYTES,
            expected_zettel_id=None,
            expected_archive_id=archive_id,
            expected_status="canonical",
        )
        try:
            outer_after = os.lstat(path)
        except OSError:
            complete = False
            issue_codes.append("population_authority_changed")
            continue
        if _stat_identity(outer_before) != _stat_identity(outer_after):
            complete = False
            issue_codes.append("population_authority_changed")
            continue
        path_generations[path] = _stat_identity(outer_after)
        if snapshot.get("ok") is not True or not isinstance(
            snapshot.get("bytes"), bytes
        ):
            snapshot_issues = {
                str(code) for code in snapshot.get("issue_codes") or []
            }
            complete = False
            issue_codes.append(
                "population_authority_changed"
                if "zettel_snapshot_changed" in snapshot_issues
                else "population_authority_invalid"
            )
            continue
        raw = snapshot["bytes"]
        try:
            text = raw.decode("utf-8-sig")
            boundary = services.parse_approval_zettel_content_boundary(text)
            relative = path.relative_to(root).as_posix()
        except (UnicodeError, ValueError):
            complete = False
            issue_codes.append("population_authority_invalid")
            continue
        if boundary.get("state") == "blocked":
            complete = False
            issue_codes.append("population_authority_invalid")
            continue
        frontmatter = boundary.get("frontmatter")
        if not isinstance(frontmatter, dict):
            complete = False
            issue_codes.append("population_authority_invalid")
            continue
        if frontmatter.get("status") != "canonical":
            continue
        zettel_id = frontmatter.get("id")
        if (
            not isinstance(zettel_id, str)
            or not zettel_id
            or zettel_id != zettel_id.strip()
        ):
            complete = False
            issue_codes.append("population_authority_invalid")
            continue
        authority_files_scanned += 1
        identity_to_occurrence_indexes.setdefault(zettel_id, [])
        identity_to_paths.setdefault(zettel_id, set()).add(relative)
        path_to_occurrence_indexes.setdefault(path, [])

        raw_source_refs = frontmatter.get("source_refs")
        if raw_source_refs is None:
            source_refs: list[Any] = []
        elif isinstance(raw_source_refs, list):
            source_refs = raw_source_refs
        else:
            source_refs = []
            complete = False
            issue_codes.append("population_authority_invalid")
        for ordinal, item in enumerate(source_refs, start=1):
            valid = _valid_source_ref(item)
            occurrence = Occurrence(
                private_sort_key=(relative, 0, ordinal),
                zettel_identity=zettel_id,
                authority_family="canonical_zettel_source_refs",
                coverage_state=(
                    "recovered_durable_reference"
                    if valid
                    else "blocked_or_unknown"
                ),
                reason_codes=[
                    "exact_durable_reference"
                    if valid
                    else "authority_invalid"
                ],
                evidence_kind_codes=[
                    "population_authority",
                    (
                        "durable_source_reference"
                        if valid
                        else "none"
                    ),
                ],
                durable_reference_present=valid,
                exact_object_binding=(
                    (
                        _source_ref_binding(item)
                        if valid and isinstance(item, Mapping)
                        else _normalize_object_binding(item)
                    )
                    if valid
                    else None
                ),
            )
            identity_to_occurrence_indexes[zettel_id].append(
                len(occurrences)
            )
            path_to_occurrence_indexes[path].append(len(occurrences))
            occurrences.append(occurrence)
            if not valid:
                complete = False
                issue_codes.append("population_authority_invalid")

        body = str(boundary.get("body") or "")
        if services.notion_import_frontmatter_is_notion(frontmatter):
            marker_count = body.count(
                services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
            )
            declared_count = services._notion_locator_strict_omitted_count(
                frontmatter
            )
            count_valid = (
                isinstance(declared_count, int)
                and declared_count == marker_count
            )
            if not count_valid:
                complete = False
                issue_codes.append("population_authority_invalid")
            for ordinal in range(1, marker_count + 1):
                occurrence = Occurrence(
                    private_sort_key=(relative, 1, ordinal),
                    zettel_identity=zettel_id,
                    authority_family=(
                        "canonical_notion_omission_markers"
                    ),
                    coverage_state=(
                        "unrecovered_reference"
                        if count_valid
                        else "blocked_or_unknown"
                    ),
                    reason_codes=[
                        (
                            "explicit_unrecovered_marker"
                            if count_valid
                            else "authority_invalid"
                        )
                    ],
                    evidence_kind_codes=[
                        "population_authority",
                        "explicit_omission_marker",
                    ],
                )
                identity_to_occurrence_indexes[zettel_id].append(
                    len(occurrences)
                )
                path_to_occurrence_indexes[path].append(len(occurrences))
                occurrences.append(occurrence)

    for zettel_id, paths in identity_to_paths.items():
        if len(paths) <= 1:
            continue
        complete = False
        issue_codes.append("population_identity_conflict")
        indexes = identity_to_occurrence_indexes[zettel_id]
        for index in indexes:
            occurrence = occurrences[index]
            occurrence.identity_conflict = True
            occurrence.coverage_state = "blocked_or_unknown"
            occurrence.reason_codes = ["duplicate_identity_conflict"]
            occurrence.durable_reference_present = False
            occurrence.exact_object_binding = None

    (
        final_paths,
        final_enumeration_complete,
        final_enumeration_issues,
    ) = _enumerate_canonical_zettel_paths(root, services)
    if not final_enumeration_complete:
        complete = False
    issue_codes.extend(final_enumeration_issues)
    if final_paths != zettel_paths:
        complete = False
        issue_codes.append("population_authority_changed")
    final_changed_paths: set[Path] = set(zettel_paths) - set(final_paths)
    for path, generation in path_generations.items():
        try:
            final_generation = _stat_identity(os.lstat(path))
        except OSError:
            complete = False
            issue_codes.append("population_authority_changed")
            final_changed_paths.add(path)
            continue
        if final_generation != generation:
            complete = False
            issue_codes.append("population_authority_changed")
            final_changed_paths.add(path)
    for path in final_changed_paths:
        for index in path_to_occurrence_indexes.get(path, []):
            occurrence = occurrences[index]
            occurrence.coverage_state = "blocked_or_unknown"
            occurrence.reason_codes = ["authority_changed"]
            occurrence.durable_reference_present = False
            occurrence.exact_object_binding = None

    occurrences.sort(key=lambda item: item.private_sort_key)
    return (
        occurrences,
        complete,
        _unique(issue_codes),
        authority_files_scanned,
    )


def _strict_json_object(raw: bytes) -> dict[str, Any] | None:
    def reject_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise DuplicateJSONKeyError(key)
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ValueError("non-finite")
            ),
        )
    except (
        DuplicateJSONKeyError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
        RecursionError,
    ):
        return None
    return value if isinstance(value, dict) else None


def _scan_manifest(
    root: Path,
    services: Any,
) -> ManifestInventory:
    inventory = ManifestInventory()
    path = root / "objects" / "manifests" / "files.jsonl"
    raw, error = _read_stable_regular_file(
        path,
        max_bytes=MAX_MANIFEST_BYTES,
        services=services,
        root=root,
    )
    if error == "missing":
        return inventory
    inventory.present = True
    if error is not None or raw is None:
        inventory.scan_complete = False
        inventory.before_after_identity_equal = error != "changed"
        inventory.issue_codes.append("storage_manifest_unreadable")
        return inventory

    lines = raw.splitlines()
    if len(lines) > MAX_MANIFEST_RECORDS:
        inventory.scan_complete = False
        inventory.issue_codes.append("storage_manifest_invalid")
        lines = lines[:MAX_MANIFEST_RECORDS]
    for raw_line in lines:
        if not raw_line.strip():
            continue
        inventory.records_scanned += 1
        record = _strict_json_object(raw_line)
        if record is None:
            inventory.invalid_record_count += 1
            inventory.scan_complete = False
            inventory.issue_codes.append("storage_manifest_invalid")
            continue
        object_id = str(record.get("object_id") or "").lower()
        digest = str(record.get("sha256") or "").lower()
        if (
            not OBJECT_ID_RE.fullmatch(object_id)
            or digest != object_id.removeprefix("sha256:")
        ):
            inventory.invalid_record_count += 1
            inventory.scan_complete = False
            inventory.issue_codes.append("storage_manifest_invalid")
            continue
        inventory.records_by_object.setdefault(object_id, []).append(record)
    return inventory


def _classify_storage_for_occurrence(
    occurrence: Occurrence,
    *,
    root: Path,
    archive_id: str,
    inventory: ManifestInventory,
    services: Any,
    receipt_cache: dict[str, tuple[dict[str, Any] | None, str | None]],
) -> tuple[str, list[str], list[str], list[str]]:
    if not occurrence.applicable:
        return (
            "not_applicable",
            ["reviewed_not_applicable"],
            ["none"],
            [],
        )
    object_id = occurrence.exact_object_binding
    if object_id is None:
        return (
            "no_evidence",
            ["object_binding_absent", "no_recorded_storage_evidence"],
            ["none"],
            [],
        )
    records = inventory.records_by_object.get(object_id, [])
    if not records:
        if not inventory.scan_complete:
            return (
                "indeterminate",
                ["storage_evidence_unreadable"],
                ["none"],
                ["storage_evidence_unreadable"],
            )
        return (
            "no_evidence",
            ["no_recorded_storage_evidence"],
            ["none"],
            [],
        )
    if len(records) != 1:
        return (
            "contradictory",
            ["storage_evidence_contradictory"],
            ["object_manifest"],
            ["storage_evidence_contradictory"],
        )
    record = records[0]
    locations = record.get("locations")
    if not isinstance(locations, list):
        return (
            "contradictory",
            ["storage_evidence_contradictory"],
            ["object_manifest"],
            ["storage_evidence_contradictory"],
        )

    valid_receipt = False
    contradictory = False
    indeterminate = False
    for location in locations:
        if not isinstance(location, dict):
            contradictory = True
            continue
        if (
            location.get("provider") != "object_storage"
            or location.get("availability") != "wom_uploaded"
        ):
            continue
        codes, _receipt_read = (
            services.backup_evidence_receipt_validation_codes(
                root,
                archive_id=archive_id,
                object_id=object_id,
                location=location,
                receipt_cache=receipt_cache,
            )
        )
        if not codes:
            valid_receipt = True
        elif set(codes) & _UNREADABLE_RECEIPT_CODES:
            indeterminate = True
        else:
            contradictory = True
    if contradictory:
        return (
            "contradictory",
            ["storage_evidence_contradictory"],
            ["object_manifest"],
            ["storage_evidence_contradictory"],
        )
    if indeterminate:
        return (
            "indeterminate",
            ["storage_evidence_unreadable"],
            ["object_manifest"],
            ["storage_evidence_unreadable"],
        )
    if valid_receipt:
        return (
            "recorded_time_evidence",
            ["exact_linked_provider_receipt"],
            ["object_manifest", "linked_provider_receipt"],
            [],
        )
    return (
        "manifest_identity_only",
        ["exact_manifest_identity"],
        ["object_manifest"],
        [],
    )


def _coverage_aggregate(
    occurrences: Sequence[Occurrence],
    *,
    population_complete: bool,
) -> dict[str, Any]:
    counts = {
        state: sum(
            1 for occurrence in occurrences if occurrence.coverage_state == state
        )
        for state in COVERAGE_STATES
    }
    population_count = len(occurrences)
    applicable_count = population_count - counts["not_applicable"]
    if not population_complete or counts["blocked_or_unknown"]:
        state = "indeterminate"
    elif applicable_count == 0:
        state = "not_applicable"
    elif counts["recovered_durable_reference"] == applicable_count:
        state = "complete"
    elif counts["recovered_durable_reference"] == 0:
        state = "none"
    else:
        state = "partial"
    return {
        "population_complete": population_complete,
        "archive_wide_population_authority_available": False,
        "state": state,
        "population_count": population_count,
        "applicable_count": applicable_count,
        "recovered_count": counts["recovered_durable_reference"],
        "candidate_only_count": counts["recoverable_candidate_only"],
        "unrecovered_count": counts["unrecovered_reference"],
        "retry_residue_count": counts["retry_residue"],
        "not_applicable_count": counts["not_applicable"],
        "blocked_or_unknown_count": counts["blocked_or_unknown"],
        "archive_wide_coverage_claim_supported": False,
    }


def _storage_aggregate(
    occurrences: Sequence[Occurrence],
    *,
    assessment_complete: bool,
) -> dict[str, Any]:
    counts = {
        state: sum(
            1 for occurrence in occurrences if occurrence.storage_state == state
        )
        for state in STORAGE_STATES
    }
    assessment_count = len(occurrences)
    applicable_count = assessment_count - counts["not_applicable"]
    if not assessment_complete or counts["indeterminate"]:
        state = "indeterminate"
    elif counts["contradictory"]:
        state = "contradictory"
    elif applicable_count == 0:
        state = "not_applicable"
    elif counts["recorded_time_evidence"] == applicable_count:
        state = "recorded_time_full"
    elif counts["recorded_time_evidence"] > 0:
        state = "recorded_time_partial"
    elif counts["manifest_identity_only"] == applicable_count:
        state = "manifest_identity_only"
    elif counts["no_evidence"] == applicable_count:
        state = "no_evidence"
    else:
        state = "mixed_nonrecorded_evidence"
    distinct_objects = {
        occurrence.exact_object_binding
        for occurrence in occurrences
        if occurrence.exact_object_binding is not None
    }
    return {
        "assessment_scope": "local_recorded_evidence_only",
        "assessment_complete": assessment_complete,
        "state": state,
        "assessment_count": assessment_count,
        "applicable_assessment_count": applicable_count,
        "recorded_time_evidence_count": counts["recorded_time_evidence"],
        "manifest_identity_only_count": counts["manifest_identity_only"],
        "contradictory_count": counts["contradictory"],
        "no_evidence_count": counts["no_evidence"],
        "not_applicable_count": counts["not_applicable"],
        "indeterminate_count": counts["indeterminate"],
        "distinct_bound_object_count_known": True,
        "distinct_bound_object_count": len(distinct_objects),
        "current_bytes_checked": False,
        "live_local_availability_claim_supported": False,
        "live_remote_availability_claim_supported": False,
        "live_storage_integrity_claim_supported": False,
    }


def _details(
    occurrences: Sequence[Occurrence],
    *,
    max_items: int,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for ordinal, occurrence in enumerate(occurrences[:max_items], start=1):
        result.append(
            {
                "reference_ordinal": ordinal,
                "authority_family": occurrence.authority_family,
                "coverage_state": occurrence.coverage_state,
                "storage_evidence_state": occurrence.storage_state,
                "reason_codes": _unique(occurrence.reason_codes),
                "evidence_kind_codes": _unique(
                    occurrence.evidence_kind_codes
                ),
                "applicable": occurrence.applicable,
                "durable_reference_present": (
                    occurrence.durable_reference_present
                ),
                "exact_object_binding_present": (
                    occurrence.exact_object_binding is not None
                ),
            }
        )
    return result


def _empty_result(
    *,
    status: str,
    exit_code: int,
    issue_codes: Sequence[str],
    startup_mode: bool,
    max_items: int,
) -> dict[str, Any]:
    coverage = _coverage_aggregate([], population_complete=False)
    storage = _storage_aggregate([], assessment_complete=False)
    return {
        "schema": RESULT_SCHEMA_ID,
        "ok": False,
        "dry_run": True,
        "lifecycle_action": LIFECYCLE_ACTION,
        "status": status,
        "exit_code": exit_code,
        "execution_guard": {
            "interpreter_no_bytecode_mode": startup_mode,
            "wom_command_body_writes_prohibited": True,
            "self_reexec_used": False,
            "environment_mutated": False,
        },
        "assessment_scope": (
            "observed_current_canonical_source_occurrences_and_"
            "local_recorded_storage_evidence"
        ),
        "issues": _issue_counts(issue_codes),
        "authority_summary": {
            "population_authority_family_count": 2,
            "population_authority_files_scanned": 0,
            "population_traversal_complete": False,
            "archive_wide_population_authority_available": False,
            "storage_manifest_present": False,
            "storage_manifest_records_scanned": 0,
            "storage_traversal_complete": False,
            "before_after_identity_equal": False,
        },
        "index_observation": {
            "state": "not_used",
            "index_rows_consumed": 0,
        },
        "source_reference_coverage": coverage,
        "recorded_storage_evidence": storage,
        "claim_separation": {
            "source_coverage_implies_storage_integrity": False,
            "storage_integrity_implies_source_coverage": False,
            "source_state_changes_storage_state": False,
            "storage_state_changes_source_state": False,
        },
        "details_returned": 0,
        "details_truncated": False,
        "details": [],
        "resource_limits": {
            "max_items": max_items,
            "zettel_file_bytes": MAX_ZETTEL_BYTES,
            "object_manifest_bytes": MAX_MANIFEST_BYTES,
            "object_manifest_records": MAX_MANIFEST_RECORDS,
        },
        "privacy_guards": {
            "source_identifier_exposed": False,
            "object_identifier_exposed": False,
            "local_path_exposed": False,
            "provider_locator_exposed": False,
            "secret_value_exposed": False,
            "object_bytes_read": False,
            "provider_api_called": False,
            "network_used": False,
            "files_written": False,
        },
    }


def validate_result_semantics(value: Mapping[str, Any]) -> None:
    """Pure cross-field validation that JSON Schema cannot express."""

    coverage = value["source_reference_coverage"]
    storage = value["recorded_storage_evidence"]
    details = value["details"]
    population_sum = sum(
        int(coverage[key])
        for key in (
            "recovered_count",
            "candidate_only_count",
            "unrecovered_count",
            "retry_residue_count",
            "not_applicable_count",
            "blocked_or_unknown_count",
        )
    )
    if population_sum != coverage["population_count"]:
        raise ValueError("coverage count invariant failed")
    if (
        coverage["applicable_count"]
        != coverage["population_count"] - coverage["not_applicable_count"]
    ):
        raise ValueError("coverage applicability invariant failed")
    storage_sum = sum(
        int(storage[key])
        for key in (
            "recorded_time_evidence_count",
            "manifest_identity_only_count",
            "contradictory_count",
            "no_evidence_count",
            "not_applicable_count",
            "indeterminate_count",
        )
    )
    if storage_sum != storage["assessment_count"]:
        raise ValueError("storage count invariant failed")
    if storage["assessment_count"] != coverage["population_count"]:
        raise ValueError("axis denominator invariant failed")
    if (
        storage["applicable_assessment_count"]
        != storage["assessment_count"] - storage["not_applicable_count"]
    ):
        raise ValueError("storage applicability invariant failed")
    if value["details_returned"] != len(details):
        raise ValueError("details count invariant failed")
    if value["details_returned"] > coverage["population_count"]:
        raise ValueError("details population bound invariant failed")
    expected_truncation = (
        value["details_returned"] < coverage["population_count"]
    )
    if value["details_truncated"] is not expected_truncation:
        raise ValueError("details truncation invariant failed")
    if [detail["reference_ordinal"] for detail in details] != list(
        range(1, len(details) + 1)
    ):
        raise ValueError("detail ordinal invariant failed")
    for detail in details:
        if (
            detail["durable_reference_present"]
            != (
                detail["coverage_state"]
                == "recovered_durable_reference"
            )
        ):
            raise ValueError("detail durable-reference invariant failed")
        if (
            detail["exact_object_binding_present"]
            and not detail["durable_reference_present"]
        ):
            raise ValueError("detail object-binding invariant failed")
    if value["index_observation"] != {
        "state": "not_used",
        "index_rows_consumed": 0,
    }:
        raise ValueError("index non-use invariant failed")
    if coverage["archive_wide_coverage_claim_supported"] is not False:
        raise ValueError("archive-wide claim invariant failed")
    for key in (
        "current_bytes_checked",
        "live_local_availability_claim_supported",
        "live_remote_availability_claim_supported",
        "live_storage_integrity_claim_supported",
    ):
        if storage[key] is not False:
            raise ValueError("live storage claim invariant failed")
    if any(value["claim_separation"].values()):
        raise ValueError("axis independence invariant failed")
    authority = value["authority_summary"]
    if (
        authority["population_traversal_complete"]
        is not coverage["population_complete"]
    ):
        raise ValueError("population traversal invariant failed")
    expected_storage_complete = bool(
        coverage["population_complete"]
        and authority["storage_traversal_complete"]
    )
    if storage["assessment_complete"] is not expected_storage_complete:
        raise ValueError("storage traversal invariant failed")
    if storage["distinct_bound_object_count"] > coverage["population_count"]:
        raise ValueError("distinct object bound invariant failed")
    status_contract = {
        "audit_complete": (True, 0),
        "audit_incomplete": (False, 1),
        "blocked": (False, 2),
    }
    if status_contract.get(value["status"]) != (
        value["ok"],
        value["exit_code"],
    ):
        raise ValueError("status invariant failed")


def _execute(
    request: AuditRequest,
    *,
    progress_stream: TextIO,
) -> tuple[dict[str, Any], int]:
    from . import archive_services as services

    _progress(request.progress, progress_stream, "archive_boundary")
    try:
        root = services.require_existing_archive_root(request.archive_root)
        archive_id = services.read_archive_id(root)
    except Exception:
        result = _empty_result(
            status="blocked",
            exit_code=2,
            issue_codes=["archive_boundary_unsafe"],
            startup_mode=True,
            max_items=request.max_items,
        )
        return result, 2

    _progress(request.progress, progress_stream, "canonical_population")
    (
        occurrences,
        population_complete,
        population_issues,
        authority_files_scanned,
    ) = _scan_observed_population(root, archive_id, services)

    _progress(request.progress, progress_stream, "recorded_storage_evidence")
    manifest = _scan_manifest(root, services)
    receipt_cache: dict[
        str, tuple[dict[str, Any] | None, str | None]
    ] = {}
    storage_issues: list[str] = list(manifest.issue_codes)
    for occurrence in occurrences:
        (
            storage_state,
            storage_reasons,
            storage_evidence,
            item_issues,
        ) = _classify_storage_for_occurrence(
            occurrence,
            root=root,
            archive_id=archive_id,
            inventory=manifest,
            services=services,
            receipt_cache=receipt_cache,
        )
        occurrence.storage_state = storage_state
        occurrence.reason_codes = _unique(
            [*occurrence.reason_codes, *storage_reasons]
        )
        occurrence.evidence_kind_codes = _unique(
            [*occurrence.evidence_kind_codes, *storage_evidence]
        )
        storage_issues.extend(item_issues)

    coverage = _coverage_aggregate(
        occurrences,
        population_complete=population_complete,
    )
    assessment_complete = bool(
        population_complete and manifest.scan_complete
    )
    storage = _storage_aggregate(
        occurrences,
        assessment_complete=assessment_complete,
    )
    details = _details(occurrences, max_items=request.max_items)
    issue_codes = _unique(
        [
            "archive_wide_population_authority_unavailable",
            *population_issues,
            *storage_issues,
        ]
    )
    population_identity_equal = not bool(
        {
            "population_authority_unreadable",
            "population_authority_changed",
        }
        & set(population_issues)
    )
    execution_complete = bool(
        population_complete and manifest.scan_complete
    )
    status = "audit_complete" if execution_complete else "audit_incomplete"
    exit_code = 0 if execution_complete else 1
    result = {
        "schema": RESULT_SCHEMA_ID,
        "ok": execution_complete,
        "dry_run": True,
        "lifecycle_action": LIFECYCLE_ACTION,
        "status": status,
        "exit_code": exit_code,
        "execution_guard": {
            "interpreter_no_bytecode_mode": True,
            "wom_command_body_writes_prohibited": True,
            "self_reexec_used": False,
            "environment_mutated": False,
        },
        "assessment_scope": (
            "observed_current_canonical_source_occurrences_and_"
            "local_recorded_storage_evidence"
        ),
        "issues": _issue_counts(issue_codes),
        "authority_summary": {
            "population_authority_family_count": len(AUTHORITY_FAMILIES),
            "population_authority_files_scanned": authority_files_scanned,
            "population_traversal_complete": population_complete,
            "archive_wide_population_authority_available": False,
            "storage_manifest_present": manifest.present,
            "storage_manifest_records_scanned": manifest.records_scanned,
            "storage_traversal_complete": manifest.scan_complete,
            "before_after_identity_equal": bool(
                population_identity_equal
                and manifest.before_after_identity_equal
            ),
        },
        "index_observation": {
            "state": "not_used",
            "index_rows_consumed": 0,
        },
        "source_reference_coverage": coverage,
        "recorded_storage_evidence": storage,
        "claim_separation": {
            "source_coverage_implies_storage_integrity": False,
            "storage_integrity_implies_source_coverage": False,
            "source_state_changes_storage_state": False,
            "storage_state_changes_source_state": False,
        },
        "details_returned": len(details),
        "details_truncated": len(occurrences) > len(details),
        "details": details,
        "resource_limits": {
            "max_items": request.max_items,
            "zettel_file_bytes": MAX_ZETTEL_BYTES,
            "object_manifest_bytes": MAX_MANIFEST_BYTES,
            "object_manifest_records": MAX_MANIFEST_RECORDS,
        },
        "privacy_guards": {
            "source_identifier_exposed": False,
            "object_identifier_exposed": False,
            "local_path_exposed": False,
            "provider_locator_exposed": False,
            "secret_value_exposed": False,
            "object_bytes_read": False,
            "provider_api_called": False,
            "network_used": False,
            "files_written": False,
        },
    }
    try:
        validate_result_semantics(result)
    except (KeyError, TypeError, ValueError):
        blocked = _empty_result(
            status="blocked",
            exit_code=2,
            issue_codes=["result_semantic_validation_failed"],
            startup_mode=True,
            max_items=request.max_items,
        )
        return blocked, 2
    _progress(request.progress, progress_stream, "result")
    return result, exit_code


def _render_text(result: Mapping[str, Any]) -> str:
    coverage = result["source_reference_coverage"]
    storage = result["recorded_storage_evidence"]
    return "\n".join(
        (
            f"SOURCE REFERENCE COVERAGE: {str(coverage['state']).upper()}",
            (
                "RECORDED STORAGE EVIDENCE: "
                f"{str(storage['state']).replace('_', ' ').upper()}"
            ),
            "ARCHIVE-WIDE POPULATION AUTHORITY: UNAVAILABLE",
            "ARCHIVE-WIDE COVERAGE CLAIM SUPPORTED: NO",
            "CURRENT BYTES CHECKED: NO",
            f"STATUS: {str(result['status']).upper()}",
        )
    )


def command_source_reference_coverage_audit_argv(
    argv: Sequence[str],
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Raw CLI route with content-free failures and no silent re-execution."""

    output = sys.stdout if stdout is None else stdout
    error = sys.stderr if stderr is None else stderr
    request = _parse_request(argv)
    startup_mode = _interpreter_started_with_no_bytecode_mode()
    if request.help_requested and not request.invalid:
        print(HELP_TEXT, file=output)
        return 0
    if request.invalid:
        result = _empty_result(
            status="blocked",
            exit_code=2,
            issue_codes=["request_invalid"],
            startup_mode=startup_mode,
            max_items=request.max_items,
        )
        print(
            json.dumps(result, ensure_ascii=True, separators=(",", ":")),
            file=output,
        )
        return 2
    if not startup_mode:
        result = _empty_result(
            status="blocked",
            exit_code=2,
            issue_codes=["interpreter_no_bytecode_mode_required"],
            startup_mode=False,
            max_items=request.max_items,
        )
        print(
            json.dumps(result, ensure_ascii=True, separators=(",", ":")),
            file=output,
        )
        return 2
    result, exit_code = _execute(request, progress_stream=error)
    try:
        rendered = (
            json.dumps(
                result,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            if request.output_format == "json"
            else _render_text(result)
        )
    except (TypeError, ValueError):
        fallback = _empty_result(
            status="blocked",
            exit_code=2,
            issue_codes=["result_serialization_blocked"],
            startup_mode=True,
            max_items=request.max_items,
        )
        rendered = json.dumps(
            fallback,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        exit_code = 2
    try:
        print(rendered, file=output)
    except (BrokenPipeError, OSError):
        return exit_code
    return exit_code
