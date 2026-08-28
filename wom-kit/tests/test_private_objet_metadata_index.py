from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import io
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence
import unittest
from unittest import mock
import urllib.request
import zipfile


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent
SRC_ROOT = KIT_ROOT / "src"
PACKAGED_RESOURCE_ROOT = SRC_ROOT / "wom_kit" / "_resources"
RESOURCE_MANIFEST_PATH = PACKAGED_RESOURCE_ROOT / "resource-manifest.json"
PREDECESSOR_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "v0.3.297-surface-baseline.json"
)

PREDECESSOR_COMMIT = "96a37f10907951039130ea0b1cc574e2b3f80ffa"
PREDECESSOR_WHEEL_SHA256 = (
    "28ac3f6f25a0c352becdb274f3214ed34b375123c13ec1e7a5c108b13c1e4653"
)
SEALED_CORPUS_SCHEMA = (
    "wom-kit/sealed-public-private-policy-canary-corpus/v0.1"
)
SEALED_MEMBER_BYTE_COUNT = 6
SEALED_MEMBER_SHA256 = (
    "4478d5c1032499345cc1516e7f26bb30ba1d0f781d57e618de5a54a418c5fc5d"
)
SEALED_DERIVED_FORM_COUNT = 8
PREDECESSOR_GIT_RAW_COUNT = 203
PREDECESSOR_GIT_FILE_COUNT = 38
PREDECESSOR_GIT_PATH_NAME_COUNT = 0
PREDECESSOR_WHEEL_RAW_COUNT = 1
PREDECESSOR_WHEEL_MEMBER_COUNT = 1
PREDECESSOR_WHEEL_MATCHING_MEMBER = b"wom_kit/archive_services.py"
EMPTY_ALLOWLIST_BYTES = b"[]"
EMPTY_ALLOWLIST_SHA256 = (
    "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
)

CLI_COUNT = 575
CLI_CANONICAL_SHA256 = (
    "f3d12300e12dc3ab54d2b72e443f69bb4102ac2460c3d51d7f3da17108063c1f"
)
MCP_COUNT = 130
MCP_CANONICAL_SHA256 = (
    "f3f2263e28ed490efc37313036a81d9e4eb1b8da9c184fce435ded44001db1fe"
)
DB_SOURCE_COUNT = 3
DB_SOURCE_CANONICAL_SHA256 = (
    "d9a42f08ee12a6d42e40214cfb12441e4077bf50c38c25b2692ec1344328294a"
)
RESOURCE_ADDITIONS = frozenset(
    {
        "release-notes/v0.4.11.md",
        "schemas/agent-instruction-policy-v0.1.schema.json",
        "schemas/approval-handoff-v0.1.schema.json",
        "schemas/approval-integrity-audit-result-v0.1.schema.json",
        "schemas/approval-integrity-overlay-entry-v0.1.schema.json",
        "schemas/cli-error-v0.1.schema.json",
        "schemas/command-approval-status-inventory-v0.1.schema.json",
        "schemas/command-approval-status-inventory-v0.2.schema.json",
        "schemas/credential-capability-v0.1.schema.json",
        "schemas/duplicate-object-reconciliation-receipt-v0.1.schema.json",
        "schemas/exact-human-approval-link-receipt-v0.1.schema.json",
        "schemas/human-artifact-registry-v0.1.schema.json",
        "schemas/operation-exact-human-approval-v0.1.schema.json",
        "schemas/artifact-lifecycle-inventory.schema.json",
        "schemas/authoring-conventions.schema.json",
        "schemas/draft-discard-receipt.schema.json",
        "schemas/draft-discard-restore-receipt.schema.json",
        "schemas/external-locator-receipt.schema.json",
        "schemas/external-locator-record.schema.json",
        "schemas/external-locator-revert-receipt.schema.json",
        "schemas/markup-normalization-journal.schema.json",
        "schemas/markup-normalization-plan.schema.json",
        "schemas/markup-normalization-receipt.schema.json",
        "schemas/markup-normalization-recovery-receipt.schema.json",
        "schemas/markup-normalization-revert-receipt.schema.json",
        "schemas/markup-reference-binding-manifest.schema.json",
        "schemas/notion-property-backfill-acceptance-v0.1.schema.json",
        "schemas/notion-source-properties-v0.1.schema.json",
        "schemas/object-storage-bytes-preserved-receipt-v0.1.schema.json",
        "schemas/object-storage-formal-adoption-receipt-v0.1.schema.json",
        "schemas/objet-capture-batch-receipt.schema.json",
        "schemas/objet-capture-batch-request.schema.json",
        "schemas/principal-record.schema.json",
        "schemas/principal-registration-receipt.schema.json",
        "schemas/principal-unregistration-receipt.schema.json",
        "schemas/private-objet-finder-request-v0.1.schema.json",
        "schemas/private-objet-finder-result-v0.1.schema.json",
        "schemas/project-bytecode-repair-receipt.schema.json",
        "schemas/project-runtime-receipt-v0.1.schema.json",
        "schemas/project-version-update-receipt-v0.3.schema.json",
        "schemas/relation-candidate-plan.schema.json",
        "schemas/relation-judgment-receipt.schema.json",
        "schemas/relation-judgment.schema.json",
        "schemas/saved-view-revert-journal.schema.json",
        "schemas/saved-view-revert-receipt.schema.json",
        "schemas/saved-view-write-receipt.schema.json",
        "schemas/saved-view-write-request.schema.json",
        "schemas/source-reference-coverage-audit-result-v0.1.schema.json",
        "schemas/source-intake-batch-receipt.schema.json",
        "schemas/source-intake-batch-request.schema.json",
        "schemas/source-fidelity-draft-receipt.schema.json",
        "schemas/source-fidelity-draft-receipt-v0.2.schema.json",
        "schemas/source-fidelity-session-evidence-receipt-v0.1.schema.json",
        "schemas/zettel-objet-link-receipt.schema.json",
        "schemas/zettel-objet-link-revert-receipt.schema.json",
    }
)
RESOURCE_REMOVALS = frozenset({"release-notes/v0.3.297.md"})

PREDECESSOR_WHEEL_ENV = "WOM_V03298_PREDECESSOR_WHEEL"
CANDIDATE_WHEEL_ENV = "WOM_V03298_CANDIDATE_WHEEL"
PREDECESSOR_INSTALL_ENV = "WOM_V03298_PREDECESSOR_SITE_PACKAGES"
CANDIDATE_INSTALL_ENV = "WOM_V03298_CANDIDATE_SITE_PACKAGES"

ASCII_LOWER_TABLE = bytes.maketrans(
    bytes(range(256)),
    bytes(
        value + 32 if ord("A") <= value <= ord("Z") else value
        for value in range(256)
    ),
)


# Import the source checkout being tested, not an older installed WOM-kit.
src_root_text = str(SRC_ROOT)
if src_root_text in sys.path:
    sys.path.remove(src_root_text)
sys.path.insert(0, src_root_text)

from wom_kit import archive_cli, archive_services, mcp_server  # noqa: E402
from wom_kit import private_objet_metadata as private_metadata  # noqa: E402
from wom_kit import private_objet_metadata_index_health as private_health  # noqa: E402
from wom_kit import private_objet_metadata_index_session as private_session  # noqa: E402
from wom_kit.private_objet_metadata_index import (  # noqa: E402
    PRIVATE_TABLE_NAMES,
    PrivateObjetIndexInspection,
)
from wom_kit.private_objet_metadata_index_authority import (  # noqa: E402
    _PrivateObjetIndexAuthorityCapture as PrivateObjetIndexAuthorityCapture,
)


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _git_bytes(*arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError("privacy_gate_git_command_failed")
    return completed.stdout


def _git_tree_rows(commit: str) -> tuple[tuple[bytes, bytes, bytes], ...]:
    raw = _git_bytes("ls-tree", "-r", "-z", "--full-tree", commit)
    rows: list[tuple[bytes, bytes, bytes]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            header, path = record.split(b"\t", 1)
            _mode, object_type, object_id = header.split(b" ", 2)
        except ValueError:
            raise AssertionError("privacy_gate_git_tree_parse_failed") from None
        rows.append((path, object_type, object_id))
    if len({path for path, _kind, _oid in rows}) != len(rows):
        raise AssertionError("privacy_gate_git_tree_duplicate_path")
    return tuple(rows)


def _git_blob_batch(object_ids: Sequence[bytes]) -> dict[bytes, bytes]:
    unique = tuple(dict.fromkeys(object_ids))
    completed = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=REPO_ROOT,
        input=b"".join(object_id + b"\n" for object_id in unique),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError("privacy_gate_git_batch_failed")
    stream = io.BytesIO(completed.stdout)
    blobs: dict[bytes, bytes] = {}
    for expected_id in unique:
        header = stream.readline().rstrip(b"\n")
        fields = header.split(b" ")
        if len(fields) != 3:
            raise AssertionError("privacy_gate_git_batch_header_invalid")
        actual_id, object_type, raw_size = fields
        if actual_id != expected_id or object_type != b"blob":
            raise AssertionError("privacy_gate_git_batch_identity_invalid")
        try:
            size = int(raw_size)
        except ValueError:
            raise AssertionError("privacy_gate_git_batch_size_invalid") from None
        data = stream.read(size)
        terminator = stream.read(1)
        if len(data) != size or terminator != b"\n":
            raise AssertionError("privacy_gate_git_batch_payload_invalid")
        blobs[expected_id] = data
    if stream.read(1):
        raise AssertionError("privacy_gate_git_batch_trailing_output")
    return blobs


@lru_cache(maxsize=4)
def _git_object_entries(commit: str) -> Mapping[bytes, bytes]:
    rows = _git_tree_rows(commit)
    blob_ids = [object_id for _path, kind, object_id in rows if kind == b"blob"]
    blobs = _git_blob_batch(blob_ids)
    entries: dict[bytes, bytes] = {}
    for path, kind, object_id in rows:
        # A gitlink has a public path name but no blob bytes to scan.
        entries[path] = blobs[object_id] if kind == b"blob" else b""
    return entries


def _ascii_lower(value: bytes) -> bytes:
    return value.translate(ASCII_LOWER_TABLE)


def _raw_occurrences(value: bytes, member: bytes) -> int:
    if not member or len(value) < len(member):
        return 0
    lowered = _ascii_lower(value)
    count = 0
    start = 0
    while True:
        offset = lowered.find(member, start)
        if offset < 0:
            return count
        count += 1
        start = offset + 1


def _exact_occurrences(value: bytes, needle: bytes) -> int:
    if not needle or len(value) < len(needle):
        return 0
    count = 0
    start = 0
    while True:
        offset = value.find(needle, start)
        if offset < 0:
            return count
        count += 1
        start = offset + 1


@lru_cache(maxsize=1)
def _sealed_member() -> bytes:
    """Derive the fixed member without ever returning it through test output."""

    target = bytes.fromhex(SEALED_MEMBER_SHA256)
    candidates: set[bytes] = set()
    entries = _git_object_entries(PREDECESSOR_COMMIT)

    def matching_candidates(run_pattern: bytes) -> set[bytes]:
        # Count rolling integer six-grams first.  Hash only grams having the
        # directive's exact aggregate count; this avoids persisting a corpus
        # inventory and avoids millions of short-lived private byte slices.
        counts: Counter[int] = Counter()
        low_mask = (1 << (8 * (SEALED_MEMBER_BYTE_COUNT - 1))) - 1
        for data in entries.values():
            lowered = _ascii_lower(data)
            for matched in re.finditer(run_pattern, lowered):
                run = matched.group(0)
                if len(run) < SEALED_MEMBER_BYTE_COUNT:
                    continue
                code = int.from_bytes(
                    run[:SEALED_MEMBER_BYTE_COUNT],
                    "big",
                )
                counts[code] += 1
                for byte in run[SEALED_MEMBER_BYTE_COUNT:]:
                    code = ((code & low_mask) << 8) | byte
                    counts[code] += 1
        matches: set[bytes] = set()
        for code, count in counts.items():
            if count != PREDECESSOR_GIT_RAW_COUNT:
                continue
            candidate = code.to_bytes(SEALED_MEMBER_BYTE_COUNT, "big")
            if hashlib.sha256(candidate).digest() == target:
                matches.add(candidate)
        return matches

    # The expected member is an ASCII lowercase word.  The second pass is a
    # complete ASCII fallback and runs only if the expected closed fact drifts.
    candidates.update(matching_candidates(rb"[a-z]{6,}"))
    if not candidates:
        candidates.update(matching_candidates(rb"[\x00-\x7f]{6,}"))

    if len(candidates) != 1:
        raise AssertionError("sealed_member_derivation_not_unique")
    member = next(iter(candidates))
    if (
        len(member) != SEALED_MEMBER_BYTE_COUNT
        or not member.isascii()
        or member != _ascii_lower(member)
        or hashlib.sha256(member).hexdigest() != SEALED_MEMBER_SHA256
    ):
        raise AssertionError("sealed_member_verification_failed")
    return member


def _sealed_derived_forms(member: bytes) -> frozenset[bytes]:
    upper = member.upper()

    def percent(value: bytes, uppercase_hex: bool) -> bytes:
        pattern = "%02X" if uppercase_hex else "%02x"
        return "".join("%" + (pattern % byte) for byte in value).encode("ascii")

    text = member.decode("ascii")
    upper_text = upper.decode("ascii")
    forms = {
        percent(member, True),
        percent(member, False),
        percent(upper, True),
        percent(upper, False),
        text.encode("utf-16le"),
        text.encode("utf-16be"),
        upper_text.encode("utf-16le"),
        upper_text.encode("utf-16be"),
    }
    if len(forms) != SEALED_DERIVED_FORM_COUNT:
        raise AssertionError("sealed_derived_form_cardinality_invalid")
    return frozenset(forms)


@dataclass(frozen=True)
class _SurfaceScan:
    raw_total: int
    occurrence_file_count: int
    path_name_raw_total: int
    derived_total: int
    matching_binary_count: int
    path_counts: Mapping[bytes, int]
    lower_line_multisets: Mapping[bytes, Counter[bytes]]


def _scan_entries(
    entries: Mapping[bytes, bytes],
    member: bytes,
    derived_forms: Iterable[bytes],
) -> _SurfaceScan:
    path_counts: dict[bytes, int] = {}
    lower_lines: dict[bytes, Counter[bytes]] = {}
    path_name_raw_total = 0
    derived_total = 0
    matching_binary_count = 0

    forms = tuple(derived_forms)
    for path, data in entries.items():
        path_name_raw_total += _raw_occurrences(path, member)
        derived_total += sum(_exact_occurrences(path, form) for form in forms)
        derived_total += sum(_exact_occurrences(data, form) for form in forms)
        count = _raw_occurrences(data, member)
        if count == 0:
            continue
        path_counts[path] = count
        if b"\0" in data:
            matching_binary_count += 1
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            matching_binary_count += 1
            continue
        lines: Counter[bytes] = Counter()
        for line in data.splitlines():
            if _raw_occurrences(line, member):
                lines[_ascii_lower(line)] += 1
        lower_lines[path] = lines

    return _SurfaceScan(
        raw_total=sum(path_counts.values()),
        occurrence_file_count=len(path_counts),
        path_name_raw_total=path_name_raw_total,
        derived_total=derived_total,
        matching_binary_count=matching_binary_count,
        path_counts=path_counts,
        lower_line_multisets=lower_lines,
    )


def _assert_surface_subset(
    test: unittest.TestCase,
    predecessor: _SurfaceScan,
    candidate: _SurfaceScan,
    *,
    maximum_total: int,
    maximum_files: int,
) -> None:
    test.assertEqual(
        candidate.matching_binary_count,
        0,
        "sealed_surface_binary_hold",
    )
    test.assertEqual(candidate.path_name_raw_total, 0, "sealed_path_name_hold")
    test.assertEqual(candidate.derived_total, 0, "sealed_derived_variant_hold")
    test.assertLessEqual(candidate.raw_total, maximum_total, "sealed_total_hold")
    test.assertLessEqual(
        candidate.occurrence_file_count,
        maximum_files,
        "sealed_file_count_hold",
    )
    test.assertTrue(
        set(candidate.path_counts).issubset(predecessor.path_counts),
        "sealed_occurrence_path_subset_hold",
    )
    for path, count in candidate.path_counts.items():
        test.assertLessEqual(
            count,
            predecessor.path_counts[path],
            "sealed_per_path_count_hold",
        )
        extra_lines = (
            candidate.lower_line_multisets[path]
            - predecessor.lower_line_multisets[path]
        )
        test.assertFalse(extra_lines, "sealed_same_path_line_subset_hold")


def _worktree_is_clean() -> bool:
    return not _git_bytes("status", "--porcelain=v1", "-z", "--untracked-files=all")


def _candidate_entries() -> tuple[Mapping[bytes, bytes], str]:
    if _worktree_is_clean():
        head = _git_bytes("rev-parse", "HEAD").strip().decode("ascii")
        return _git_object_entries(head), "git_object"

    raw_paths = _git_bytes(
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    )
    entries: dict[bytes, bytes] = {}
    for raw_path in raw_paths.split(b"\0"):
        if not raw_path:
            continue
        candidate = REPO_ROOT / os.fsdecode(raw_path)
        try:
            before = candidate.lstat()
        except FileNotFoundError:
            # A tracked deletion is absent from the candidate approximation.
            continue
        if stat.S_ISLNK(before.st_mode):
            data = os.fsencode(os.readlink(candidate))
        elif stat.S_ISREG(before.st_mode):
            data = candidate.read_bytes()
        else:
            raise AssertionError("candidate_surface_unsupported_file_type")
        after = candidate.lstat()
        if (
            before.st_mode != after.st_mode
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
        ):
            raise AssertionError("candidate_surface_changed_during_scan")
        entries[raw_path.replace(b"\\", b"/")] = data
    return entries, "dirty_worktree_approximation"


def _runtime_canaries() -> dict[str, str]:
    prefix = "_".join(("WOMV03298", "PRIVATE")) + "_"
    plain_suffixes = {
        "filename": "FILENAME_CANARY_N1.DAT",
        "label": "LABEL_CANARY_N1",
        "path": "PATH_CANARY_N1",
        "provider": "PROVIDER_CANARY_N1",
        "source": "SOURCE_CANARY_N1",
        "reviewer": "REVIEWER_CANARY_N1",
        "exception": "EXCEPTION_CANARY_N1",
    }
    digest_cores = {
        "object_id": "OBJECT_ID_CANARY_N1",
        "receipt": "RECEIPT_CANARY_N1",
        "authority_fingerprint": "AUTHORITY_FINGERPRINT_CANARY_N1",
        "observation_rows": "OBSERVATION_ROWS_CANARY_N1",
        "alias_rows": "ALIAS_ROWS_CANARY_N1",
        "projection_rows": "PROJECTION_ROWS_CANARY_N1",
    }
    values = {
        key: prefix + suffix for key, suffix in plain_suffixes.items()
    }
    values.update(
        {
            key: "sha256:"
            + hashlib.sha256((prefix + core).encode("utf-8")).hexdigest()
            for key, core in digest_cores.items()
        }
    )
    if len(values) != len(set(values.values())):
        raise AssertionError("runtime_canary_inventory_not_unique")
    return values


def _runtime_value_bytes() -> tuple[bytes, ...]:
    values = tuple(_runtime_canaries().values())
    encoded: list[bytes] = []
    for value in values:
        encoded.append(value.encode("utf-8"))
        encoded.append(json.dumps(value, ensure_ascii=True).encode("utf-8"))
    return tuple(dict.fromkeys(encoded))


def _assert_no_runtime_values(
    test: unittest.TestCase,
    payloads: Iterable[bytes],
    *,
    code: str,
) -> None:
    values = _runtime_value_bytes()
    occurrence_total = 0
    for payload in payloads:
        occurrence_total += sum(
            _exact_occurrences(payload, value) for value in values
        )
    test.assertEqual(occurrence_total, 0, code)


def _json_scalars(value: Any) -> Iterable[Any]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield key
            yield from _json_scalars(item)
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        for item in value:
            yield from _json_scalars(item)
    else:
        yield value


def _assert_no_runtime_json_scalars(
    test: unittest.TestCase,
    value: Any,
    *,
    code: str,
) -> None:
    needles = tuple(_runtime_canaries().values())
    matches = 0
    for scalar in _json_scalars(value):
        if isinstance(scalar, str):
            matches += sum(needle in scalar for needle in needles)
    test.assertEqual(matches, 0, code)


def _current_cli_paths() -> list[list[str]]:
    discovered: set[tuple[str, ...]] = set()

    def visit(parser: argparse.ArgumentParser, prefix: tuple[str, ...]) -> None:
        for action in parser._actions:
            if not isinstance(action, argparse._SubParsersAction):
                continue
            for label, child in action.choices.items():
                path = prefix + (label,)
                discovered.add(path)
                visit(child, path)

    visit(archive_cli.build_parser(), ())
    return [list(path) for path in sorted(discovered)]


def _current_mcp_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "name": definition["name"],
            "inputSchema": definition["inputSchema"],
        }
        for definition in mcp_server.TOOL_DEFINITIONS
    ]
    return sorted(rows, key=lambda row: row["name"])


def _current_database_rows() -> list[dict[str, Any]]:
    candidates = {
        path
        for path in (KIT_ROOT / "templates").glob("*/db/schema.sql")
        if path.is_file()
    }
    for relative_root in (
        "wom-kit/migrations",
        "wom-kit/src/wom_kit/migrations",
    ):
        migration_root = REPO_ROOT / relative_root
        if migration_root.is_dir():
            candidates.update(
                path for path in migration_root.rglob("*") if path.is_file()
            )
    rows: list[dict[str, Any]] = []
    for path in sorted(
        candidates,
        key=lambda item: item.relative_to(REPO_ROOT).as_posix(),
    ):
        data = path.read_bytes()
        rows.append(
            {
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return rows


def _public_health_shape() -> dict[str, Any]:
    return {
        "ok": True,
        "dry_run": True,
        "lifecycle_action": "index_health",
        "archive_id": "synthetic-private-index",
        "index_path": "db/archive-index.sqlite",
        "index_state": "current",
        "summary": {
            "live_zettel_count": 0,
            "indexed_zettel_count": 0,
        },
        "samples": {},
        "stale_reasons": [],
        "privacy_guards": {
            "zettel_body_text_echoed": False,
            "zettel_titles_echoed": False,
            "absolute_local_paths_echoed": False,
        },
        "would_change": [],
        "next_safe_actions": [],
        "blockers": [],
        "warnings": [],
    }


def _runtime_private_health_result() -> dict[str, Any]:
    canaries = _runtime_canaries()
    private_locations = (
        canaries["filename"],
        canaries["label"],
        canaries["label"],
        canaries["path"],
        canaries["provider"],
        canaries["source"],
        canaries["reviewer"],
        canaries["object_id"],
        canaries["receipt"],
        canaries["authority_fingerprint"],
        canaries["observation_rows"],
        canaries["alias_rows"],
        canaries["projection_rows"],
    )
    inspection = PrivateObjetIndexInspection(
        observation_count=1,
        alias_count=1,
        distinct_object_count=1,
        projection_count=2,
        blocked_alias_derivation_count=0,
        blocked_label_projection_count=0,
        observation_rows_sha256=canaries["observation_rows"],
        alias_rows_sha256=canaries["alias_rows"],
        projection_rows_sha256=canaries["projection_rows"],
        authority_fingerprint_sha256=canaries["authority_fingerprint"],
        metadata_row=private_locations,
    )
    authority = PrivateObjetIndexAuthorityCapture(
        _compiler_input_bytes=(
            b'{"private_manifest_state":"present_nonempty"}'
        ),
        _fingerprint_bytes=b"{}",
        fingerprint_sha256=canaries["authority_fingerprint"],
        comparison_token=(
            "runtime-canary",
            canaries["authority_fingerprint"],
            "stable",
        ),
    )
    probe = private_health._ProjectionProbe(  # type: ignore[attr-defined]
        tuple(PRIVATE_TABLE_NAMES),
        1,
        inspection,
    )
    envelope = private_health._envelope_from_probe(  # type: ignore[attr-defined]
        probe,
        authority,
    )
    decision = private_health._decision("C11", envelope)  # type: ignore[attr-defined]
    return private_health.compose_private_objet_metadata_index_health(
        _public_health_shape(),
        decision,
    )


def _private_record_with_runtime_canaries() -> dict[str, Any]:
    canaries = _runtime_canaries()
    normalized = private_metadata.normalize_private_filename(
        canaries["filename"],
        "literal_unicode",
    )
    if normalized["issue_codes"]:
        raise AssertionError("runtime_canary_filename_fixture_invalid")
    return {
        "schema": private_metadata.PRIVATE_METADATA_SCHEMA,
        "privacy_class": "private_archive",
        # The public-generic projection contract intentionally returns its
        # object ID.  The object-ID canary is therefore exercised in the
        # private inspection metadata row above, while this supplemental
        # projection fixture uses a non-canary synthetic ID.
        "object_id": "sha256:"
        + hashlib.sha256(
            b"synthetic-public-projection-object"
        ).hexdigest(),
        "names": normalized["names"],
        "media_type": {
            "value": None,
            "basis": "unknown",
            "registered_status": "not_checked",
            "extension_agreement": "unknown",
            "extension_comparison_evidence_sha256": None,
            "registry_evidence": None,
        },
        "size_bytes": None,
        "size_bytes_basis": "unknown",
        "source_provenance": {
            "source_system": "synthetic-fixture",
            "source_record_id": (
                canaries["provider"] + "/" + canaries["path"]
            ),
            "source_attachment_id": canaries["source"],
            "source_snapshot_sha256": canaries["receipt"],
            "observation_evidence_sha256": canaries["observation_rows"],
            "evidence_kind": "source_attachment_metadata",
            "captured_at": "2026-08-02T00:00:00Z",
        },
        "label_candidates": [
            {
                "kind": "human_reviewed_label",
                "value": canaries["label"],
                "privacy_class": "private_archive",
                "evidence_sha256": canaries["alias_rows"],
                "review_status": "accepted",
                "review_evidence_sha256": canaries["projection_rows"],
            },
            {
                "kind": "extension_generic",
                "value": "document",
                "privacy_class": "private_archive",
                "evidence_sha256": canaries["alias_rows"],
                "review_status": "unreviewed",
                "review_evidence_sha256": None,
            },
        ],
        "normalization_profile": {
            "id": private_metadata.NORMALIZATION_PROFILE,
            "unicode_version": "17.0.0",
            "confusables_data_sha256": None,
            "confusable_status": "not_checked",
        },
    }


def _zip_entries(path: Path) -> Mapping[bytes, bytes]:
    try:
        with zipfile.ZipFile(path) as wheel:
            entries: dict[bytes, bytes] = {}
            for info in wheel.infolist():
                name = info.filename.encode("utf-8")
                if name in entries:
                    raise AssertionError("release_wheel_duplicate_member")
                entries[name] = b"" if info.is_dir() else wheel.read(info)
            return entries
    except AssertionError:
        raise
    except Exception:
        raise AssertionError("release_wheel_unreadable") from None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        raise AssertionError("release_artifact_unreadable") from None
    return digest.hexdigest()


def _required_env_pair(
    test: unittest.TestCase,
    first_name: str,
    second_name: str,
    *,
    kind: str,
) -> tuple[Path, Path]:
    first = os.environ.get(first_name)
    second = os.environ.get(second_name)
    if first is None and second is None:
        test.skipTest(
            f"release-only {kind} gate: set {first_name} and {second_name}"
        )
    if not first or not second:
        test.fail(f"release_{kind}_environment_pair_incomplete")
    return Path(first), Path(second)


def _installed_resource_entries(site_packages: Path) -> Mapping[bytes, bytes]:
    root = site_packages / "wom_kit" / "_resources"
    manifest_path = root / "resource-manifest.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except Exception:
        raise AssertionError("installed_resource_manifest_unreadable") from None
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema")
        != "wom-kit/package-resource-manifest/v0.1"
        or not isinstance(manifest.get("files"), list)
        or manifest.get("file_count") != len(manifest["files"])
    ):
        raise AssertionError("installed_resource_manifest_invalid")
    entries: dict[bytes, bytes] = {
        b"resource-manifest.json": manifest_bytes,
    }
    for row in manifest["files"]:
        if not isinstance(row, dict) or set(row) != {
            "source",
            "packaged",
            "bytes",
            "sha256",
        }:
            raise AssertionError("installed_resource_row_invalid")
        packaged = row["packaged"]
        if (
            not isinstance(packaged, str)
            or "\\" in packaged
            or packaged.startswith("/")
            or ".." in Path(packaged).parts
        ):
            raise AssertionError("installed_resource_path_invalid")
        target = root.joinpath(*packaged.split("/"))
        try:
            if target.is_symlink() or not target.is_file():
                raise AssertionError("installed_resource_payload_invalid")
            data = target.read_bytes()
        except AssertionError:
            raise
        except OSError:
            raise AssertionError("installed_resource_payload_unreadable") from None
        if (
            len(data) != row["bytes"]
            or hashlib.sha256(data).hexdigest() != row["sha256"]
        ):
            raise AssertionError("installed_resource_payload_mismatch")
        name = packaged.encode("utf-8")
        if name in entries:
            raise AssertionError("installed_resource_duplicate_path")
        entries[name] = data
    return entries


class PrivateObjetMetadataIndexPrivacyGateTests(unittest.TestCase):
    def test_00_sealed_member_and_derived_forms_are_exact_and_nonpublic(self) -> None:
        member = _sealed_member()
        derived = _sealed_derived_forms(member)
        self.assertEqual(SEALED_CORPUS_SCHEMA.rsplit("/", 1)[-1], "v0.1")
        self.assertEqual(len(member), SEALED_MEMBER_BYTE_COUNT)
        self.assertEqual(
            hashlib.sha256(member).hexdigest(),
            SEALED_MEMBER_SHA256,
        )
        self.assertEqual(len(derived), SEALED_DERIVED_FORM_COUNT)
        for value in _runtime_canaries().values():
            encoded = value.encode("utf-8")
            self.assertNotEqual(encoded, member, "runtime_sealed_collision")
            self.assertNotIn(encoded, derived, "runtime_derived_collision")

    def test_01_exact_predecessor_git_object_baseline(self) -> None:
        member = _sealed_member()
        scan = _scan_entries(
            _git_object_entries(PREDECESSOR_COMMIT),
            member,
            _sealed_derived_forms(member),
        )
        self.assertEqual(scan.raw_total, PREDECESSOR_GIT_RAW_COUNT)
        self.assertEqual(
            scan.occurrence_file_count,
            PREDECESSOR_GIT_FILE_COUNT,
        )
        self.assertEqual(
            scan.path_name_raw_total,
            PREDECESSOR_GIT_PATH_NAME_COUNT,
        )
        self.assertEqual(scan.derived_total, 0)
        self.assertEqual(scan.matching_binary_count, 0)

    def test_02_candidate_git_object_or_dirty_worktree_is_predecessor_subset(
        self,
    ) -> None:
        member = _sealed_member()
        derived = _sealed_derived_forms(member)
        predecessor = _scan_entries(
            _git_object_entries(PREDECESSOR_COMMIT),
            member,
            derived,
        )
        candidate_entries, mode = _candidate_entries()
        self.assertIn(
            mode,
            {"git_object", "dirty_worktree_approximation"},
        )
        candidate = _scan_entries(candidate_entries, member, derived)
        _assert_surface_subset(
            self,
            predecessor,
            candidate,
            maximum_total=PREDECESSOR_GIT_RAW_COUNT,
            maximum_files=PREDECESSOR_GIT_FILE_COUNT,
        )
        _assert_no_runtime_values(
            self,
            candidate_entries.values(),
            code="runtime_canary_present_in_candidate_source",
        )

    def test_03_empty_occurrence_allowlist_is_exact(self) -> None:
        self.assertEqual(len(EMPTY_ALLOWLIST_BYTES), 2)
        self.assertFalse(EMPTY_ALLOWLIST_BYTES.endswith(b"\n"))
        self.assertEqual(
            hashlib.sha256(EMPTY_ALLOWLIST_BYTES).hexdigest(),
            EMPTY_ALLOWLIST_SHA256,
        )
        self.assertEqual(json.loads(EMPTY_ALLOWLIST_BYTES), [])

    def test_04_runtime_canaries_are_private_but_generic_projection_is_closed(
        self,
    ) -> None:
        record = _private_record_with_runtime_canaries()
        validation = private_metadata.validate_private_metadata_record(record)
        self.assertIs(validation["accepted"], True)

        with (
            mock.patch.object(
                socket,
                "create_connection",
                side_effect=AssertionError("network_call_forbidden"),
            ) as socket_call,
            mock.patch.object(
                urllib.request,
                "urlopen",
                side_effect=AssertionError("provider_call_forbidden"),
            ) as url_call,
        ):
            result = private_metadata.project_objet_safe_label(
                [record],
                "public_generic",
                True,
            )
        socket_call.assert_not_called()
        url_call.assert_not_called()
        self.assertEqual(result["issue_codes"], [])
        payload = json.dumps(
            result,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        _assert_no_runtime_values(
            self,
            [payload],
            code="runtime_canary_present_in_generic_projection",
        )
        _assert_no_runtime_json_scalars(
            self,
            result,
            code="runtime_canary_present_in_projection_scalar",
        )

    def test_05_runtime_canaries_and_digests_do_not_escape_health_cli_or_mcp(
        self,
    ) -> None:
        result = _runtime_private_health_result()
        serialized = json.dumps(
            result,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        _assert_no_runtime_values(
            self,
            [serialized],
            code="runtime_canary_present_in_health",
        )
        _assert_no_runtime_json_scalars(
            self,
            result,
            code="runtime_canary_present_in_health_scalar",
        )

        canaries = _runtime_canaries()
        with mock.patch.object(
            private_health,
            "_with_private_objet_index_read_session",
            side_effect=RuntimeError(canaries["exception"]),
        ):
            failure = (
                private_health.evaluate_private_objet_metadata_index_health(
                    Path("runtime-canary-root-is-not-read"),
                    "synthetic-private-index",
                )
            )
        _assert_no_runtime_values(
            self,
            [_canonical_bytes(failure.envelope)],
            code="runtime_exception_canary_present_in_health",
        )

        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp)
            output_relative = (
                ".wom-scratch/diagnostics/health-result.json"
            )

            def service(
                _root: Path,
                *,
                dry_run: bool,
                max_items: int,
                progress_callback: Any,
            ) -> dict[str, Any]:
                self.assertIs(dry_run, True)
                self.assertEqual(max_items, 50)
                for stage in (
                    "index-health-live-zettels",
                    "index-health-index-rows",
                    "index-health-compare",
                ):
                    progress_callback(stage, "start", 0, 0)
                    progress_callback(stage, "done", 0, 0)
                return deepcopy(result)

            args = mcp_server.SimpleArgs(
                dry_run=True,
                archive_root=str(archive_root),
                max_items=50,
                progress=True,
                output=output_relative,
                format="json",
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.object(
                    archive_services,
                    "index_health",
                    side_effect=service,
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                exit_code = archive_cli.command_index_health(args)
            self.assertEqual(exit_code, 0)
            output_path = archive_root / output_relative
            self.assertTrue(output_path.is_file())
            output_bytes = output_path.read_bytes()
            _assert_no_runtime_values(
                self,
                [
                    stdout.getvalue().encode("utf-8"),
                    stderr.getvalue().encode("utf-8"),
                    output_bytes,
                ],
                code="runtime_canary_present_in_cli_surface",
            )
            _assert_no_runtime_json_scalars(
                self,
                json.loads(output_bytes),
                code="runtime_canary_present_in_cli_output_scalar",
            )

            with mock.patch.object(
                archive_services,
                "index_health",
                return_value=deepcopy(result),
            ):
                mcp = mcp_server.tool_index_health(
                    {
                        "archive_root": str(archive_root),
                        "dry_run": True,
                        "max_items": 50,
                    }
                )
            mcp_bytes = json.dumps(
                mcp,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            _assert_no_runtime_values(
                self,
                [mcp_bytes],
                code="runtime_canary_present_in_mcp_surface",
            )
            _assert_no_runtime_json_scalars(
                self,
                mcp,
                code="runtime_canary_present_in_mcp_scalar",
            )

        capability_payloads = [
            (KIT_ROOT / "docs" / "capability-matrix.md").read_bytes(),
            _canonical_bytes(_current_cli_paths()),
            _canonical_bytes(_current_mcp_rows()),
        ]
        _assert_no_runtime_values(
            self,
            capability_payloads,
            code="runtime_canary_present_in_capability_surface",
        )

    def test_06_cli_mcp_and_db_template_surfaces_are_exact(self) -> None:
        cli = _current_cli_paths()
        self.assertEqual(len(cli), CLI_COUNT)
        self.assertEqual(_canonical_sha256(cli), CLI_CANONICAL_SHA256)
        self.assertIn(["objet-source-metadata-write"], cli)

        mcp = _current_mcp_rows()
        self.assertEqual(len(mcp), MCP_COUNT)
        self.assertEqual(_canonical_sha256(mcp), MCP_CANONICAL_SHA256)

        database = _current_database_rows()
        self.assertEqual(len(database), DB_SOURCE_COUNT)
        self.assertEqual(
            _canonical_sha256(database),
            DB_SOURCE_CANONICAL_SHA256,
        )
        fixture = json.loads(
            PREDECESSOR_FIXTURE_PATH.read_text(encoding="utf-8")
        )
        predecessor_database = fixture["database"]["sources"]
        self.assertEqual(
            [row["path"] for row in database],
            [row["path"] for row in predecessor_database],
        )
        self.assertNotEqual(database, predecessor_database)
        self.assertTrue(
            all(
                "CREATE TABLE IF NOT EXISTS principals"
                in (REPO_ROOT / row["path"]).read_text(encoding="utf-8")
                for row in database
            )
        )

    def test_07_resource_delta_and_source_package_mirror_are_exact(self) -> None:
        fixture = json.loads(
            PREDECESSOR_FIXTURE_PATH.read_text(encoding="utf-8")
        )
        predecessor_paths = set(
            fixture["package_resources"]["packaged_paths"]
        )
        manifest_bytes = RESOURCE_MANIFEST_PATH.read_bytes()
        manifest = json.loads(manifest_bytes)
        self.assertEqual(
            manifest["schema"],
            "wom-kit/package-resource-manifest/v0.1",
        )
        self.assertEqual(manifest["version"], "0.4.11")
        self.assertEqual(manifest["file_count"], len(manifest["files"]))
        current_paths = {row["packaged"] for row in manifest["files"]}
        self.assertEqual(
            predecessor_paths - current_paths,
            set(RESOURCE_REMOVALS),
        )
        self.assertEqual(
            current_paths - predecessor_paths,
            set(RESOURCE_ADDITIONS),
        )

        for row in manifest["files"]:
            source = KIT_ROOT.joinpath(*row["source"].split("/"))
            packaged = PACKAGED_RESOURCE_ROOT.joinpath(
                *row["packaged"].split("/")
            )
            self.assertFalse(source.is_symlink())
            self.assertFalse(packaged.is_symlink())
            source_bytes = source.read_bytes()
            packaged_bytes = packaged.read_bytes()
            self.assertEqual(
                source_bytes,
                packaged_bytes,
                "source_package_resource_mirror_mismatch",
            )
            self.assertEqual(len(packaged_bytes), row["bytes"])
            self.assertEqual(
                hashlib.sha256(packaged_bytes).hexdigest(),
                row["sha256"],
            )

    def test_08_private_runtime_artifact_types_are_excluded_from_public_paths(
        self,
    ) -> None:
        typed_artifacts = {
            "db/archive-index.sqlite": "private_archive",
            "db/archive-index.sqlite-wal": "private_archive",
            "db/archive-index.sqlite-shm": "private_archive",
            "db/archive-index.sqlite-journal": "private_archive",
            "db/archive-index.sqlite.lock": "private_archive",
            "db/archive-index.sqlite.backup": "private_archive",
            "db/archive-index.sqlite.snapshot": "private_archive",
            ".wom-scratch/private-index-health.json": "private_archive",
        }
        self.assertEqual(set(typed_artifacts.values()), {"private_archive"})

        required_ignored = {
            "**/db/archive-index.sqlite",
            "**/db/archive-index.sqlite-wal",
            "**/db/archive-index.sqlite-shm",
            "**/db/archive-index.sqlite-journal",
            ".wom-scratch/",
        }
        self.assertTrue(
            required_ignored.issubset(archive_cli.RECOMMENDED_GITIGNORE_PATTERNS)
        )

        candidate_entries, _mode = _candidate_entries()
        normalized_paths = {
            path.decode("utf-8", errors="surrogateescape").lower()
            for path in candidate_entries
        }
        forbidden_exact = set(typed_artifacts)
        self.assertFalse(
            normalized_paths & forbidden_exact,
            "private_runtime_artifact_tracked",
        )
        resource_names = {
            row["packaged"].lower()
            for row in json.loads(
                RESOURCE_MANIFEST_PATH.read_text(encoding="utf-8")
            )["files"]
        }
        self.assertFalse(
            resource_names & forbidden_exact,
            "private_runtime_artifact_packaged",
        )

    def test_09_public_release_copy_keeps_the_narrow_claim_boundary(self) -> None:
        release_note = (
            KIT_ROOT / "docs" / "releases" / "v0.3.298.md"
        ).read_text(encoding="utf-8")
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        capability = (
            KIT_ROOT / "docs" / "capability-matrix.md"
        ).read_text(encoding="utf-8")
        combined = "\n".join((release_note, changelog, capability))
        release_flat = " ".join(release_note.split())
        self.assertIn("v0.3.302", combined)
        self.assertIn("not", release_note.lower())
        self.assertIn("globally privacy-clean", release_flat)
        self.assertIn("adds zero", release_flat)
        self.assertIn("enumerated public release surfaces", release_flat)
        self.assertNotIn(
            "the entire repository is privacy-clean",
            combined.lower(),
        )

    def test_10_ci_test_jobs_fetch_the_exact_predecessor_object(self) -> None:
        workflow = (
            REPO_ROOT / ".github" / "workflows" / "ci.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("\n  tests:\n", workflow)
        tests_job = workflow.split("\n  tests:\n", 1)[1]
        checkout_block = tests_job.split(
            "- uses: actions/setup-python@v5",
            1,
        )[0]
        self.assertIn("fetch-depth: 0", checkout_block)


class PrivateObjetMetadataIndexReleaseArtifactGateTests(unittest.TestCase):
    def test_release_only_predecessor_and_candidate_wheels(self) -> None:
        predecessor_path, candidate_path = _required_env_pair(
            self,
            PREDECESSOR_WHEEL_ENV,
            CANDIDATE_WHEEL_ENV,
            kind="wheel",
        )
        if not predecessor_path.is_file() or not candidate_path.is_file():
            self.fail("release_wheel_artifact_missing")
        self.assertEqual(
            _sha256_file(predecessor_path),
            PREDECESSOR_WHEEL_SHA256,
        )

        member = _sealed_member()
        derived = _sealed_derived_forms(member)
        predecessor_entries = _zip_entries(predecessor_path)
        candidate_entries = _zip_entries(candidate_path)
        predecessor = _scan_entries(predecessor_entries, member, derived)
        candidate = _scan_entries(candidate_entries, member, derived)

        self.assertEqual(
            predecessor.raw_total,
            PREDECESSOR_WHEEL_RAW_COUNT,
        )
        self.assertEqual(
            predecessor.occurrence_file_count,
            PREDECESSOR_WHEEL_MEMBER_COUNT,
        )
        self.assertEqual(
            set(predecessor.path_counts),
            {PREDECESSOR_WHEEL_MATCHING_MEMBER},
        )
        self.assertEqual(predecessor.path_name_raw_total, 0)
        self.assertEqual(predecessor.derived_total, 0)
        self.assertEqual(predecessor.matching_binary_count, 0)
        _assert_surface_subset(
            self,
            predecessor,
            candidate,
            maximum_total=PREDECESSOR_WHEEL_RAW_COUNT,
            maximum_files=PREDECESSOR_WHEEL_MEMBER_COUNT,
        )
        _assert_no_runtime_values(
            self,
            candidate_entries.values(),
            code="runtime_canary_present_in_candidate_wheel",
        )

    def test_release_only_fresh_installed_resource_pair(self) -> None:
        predecessor_root, candidate_root = _required_env_pair(
            self,
            PREDECESSOR_INSTALL_ENV,
            CANDIDATE_INSTALL_ENV,
            kind="install",
        )
        if not predecessor_root.is_dir() or not candidate_root.is_dir():
            self.fail("release_install_artifact_missing")
        predecessor_entries = _installed_resource_entries(predecessor_root)
        candidate_entries = _installed_resource_entries(candidate_root)

        member = _sealed_member()
        derived = _sealed_derived_forms(member)
        predecessor = _scan_entries(predecessor_entries, member, derived)
        candidate = _scan_entries(candidate_entries, member, derived)
        for scan in (predecessor, candidate):
            self.assertEqual(scan.raw_total, 0)
            self.assertEqual(scan.occurrence_file_count, 0)
            self.assertEqual(scan.path_name_raw_total, 0)
            self.assertEqual(scan.derived_total, 0)
            self.assertEqual(scan.matching_binary_count, 0)
        _assert_no_runtime_values(
            self,
            candidate_entries.values(),
            code="runtime_canary_present_in_candidate_install",
        )

        predecessor_names = {
            name.decode("utf-8")
            for name in predecessor_entries
            if name != b"resource-manifest.json"
        }
        candidate_names = {
            name.decode("utf-8")
            for name in candidate_entries
            if name != b"resource-manifest.json"
        }
        self.assertEqual(
            predecessor_names - candidate_names,
            set(RESOURCE_REMOVALS),
        )
        self.assertEqual(
            candidate_names - predecessor_names,
            set(RESOURCE_ADDITIONS),
        )

        checkout_entries = _installed_resource_entries(SRC_ROOT)
        self.assertEqual(
            candidate_entries,
            checkout_entries,
            "fresh_install_resource_bytes_do_not_match_checkout",
        )


if __name__ == "__main__":
    unittest.main()
