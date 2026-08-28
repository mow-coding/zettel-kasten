from __future__ import annotations

import argparse
import hashlib
import importlib
import io
import json
import math
import platform
import re
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator, Mapping
from unittest import mock


EXECUTING_BENCHMARK_PATH = Path(__file__).absolute()
BENCHMARK_PATH = EXECUTING_BENCHMARK_PATH
KIT_ROOT = BENCHMARK_PATH.parents[1]
SOURCE_ROOT = KIT_ROOT / "src"
PACKAGE_ROOT = SOURCE_ROOT / "wom_kit"

# Production modules are deliberately absent at module import time.  The
# benchmark captures source/HEAD/script/wheel provenance first, then imports
# these names from a private materialization of those exact captured wheel
# bytes.  A source checkout can therefore never be measured before it is
# provenance-bound.
archive_cli: ModuleType
archive_services: ModuleType
completion_workflows: ModuleType


BENCHMARK_SCHEMA = "wom-kit/v0412-link-index-benchmark/v0.2"
MIB = 1024 * 1024
ARCHIVE_ID = "archive:personal:v0412-link-index-benchmark"
ROLE = "evidence"
PRIVATE_SENTINEL = "PRIVATE_V0412_LINK_INDEX_BENCHMARK_MUST_NOT_ESCAPE"
ZETTEL_ID_PREFIX = "zet_20260828_link_index_benchmark_"
HEARTBEAT_INTERVAL_SECONDS = 9.0
COLD_P95_LIMIT_SECONDS = 20.0
WARM_P95_LIMIT_SECONDS = 5.0
FIRST_STATUS_LIMIT_SECONDS = 2.0
HEARTBEAT_GAP_LIMIT_SECONDS = 10.0
EXPECTED_DISTRIBUTION = "wom-kit"
EXPECTED_VERSION = "0.4.12"


@dataclass(frozen=True)
class BenchmarkProfile:
    name: str
    zettel_count: int
    object_count: int
    manifest_target_bytes: int
    cold_iterations: int
    warm_iterations: int


FULL_PROFILE = BenchmarkProfile(
    name="full",
    zettel_count=8_616,
    object_count=22_441,
    manifest_target_bytes=37 * MIB,
    cold_iterations=5,
    warm_iterations=10,
)
REDUCED_PROFILE = BenchmarkProfile(
    name="reduced",
    zettel_count=48,
    object_count=128,
    manifest_target_bytes=512 * 1024,
    cold_iterations=3,
    warm_iterations=5,
)
PROFILES = {
    FULL_PROFILE.name: FULL_PROFILE,
    REDUCED_PROFILE.name: REDUCED_PROFILE,
}


class BenchmarkContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class BootstrapAuthority:
    source_script_path: Path
    executing_script_path: Path
    expected_script_sha256: str
    expected_provenance_sha256: str


@dataclass(frozen=True)
class FixtureAuthority:
    root: Path
    ready_zettel_id: str
    existing_zettel_id: str
    ready_object_id: str
    existing_object_id: str
    manifest_size_bytes: int


@dataclass(frozen=True)
class PlanMeasurement:
    duration_seconds: float
    first_serialized_write_seconds: float
    first_serialized_flush_seconds: float
    max_serialized_flush_gap_seconds: float
    serialized_progress: str
    serialized_write_calls: int
    serialized_flush_calls: int
    state: str


@dataclass
class PlanInstrumentation:
    normal_plan_calls: int = 0
    authority_lookup_calls: int = 0
    target_manifest_rows_returned: int = 0
    target_manifest_json_parses: int = 0
    non_target_lookup_json_parses: int = 0
    legacy_full_zettel_resolver_calls: int = 0
    full_manifest_parser_calls: int = 0


class SerializedProgressCapture:
    """Capture the exact text and delivery calls used by ``print(..., flush=True)``.

    A callback timestamp only proves that an event reached the formatter.  This
    stream records the formatter's actual ``write`` and ``flush`` calls so the
    benchmark can measure what an operator-facing transport would receive.
    """

    encoding = "utf-8"
    errors = "strict"

    def __init__(self, *, origin: float) -> None:
        self.origin = origin
        self._lock = threading.Lock()
        self._chunks: list[str] = []
        self._write_timestamps: list[float] = []
        self._flush_timestamps: list[float] = []

    def write(self, value: str) -> int:
        if not isinstance(value, str):
            raise TypeError("serialized_progress_text_required")
        observed = time.perf_counter() - self.origin
        with self._lock:
            self._chunks.append(value)
            if value:
                self._write_timestamps.append(observed)
        return len(value)

    def flush(self) -> None:
        observed = time.perf_counter() - self.origin
        with self._lock:
            self._flush_timestamps.append(observed)

    def isatty(self) -> bool:
        return False

    def evidence(self) -> tuple[str, float, float, float, int, int]:
        with self._lock:
            serialized = "".join(self._chunks)
            writes = tuple(self._write_timestamps)
            flushes = tuple(self._flush_timestamps)
        if not serialized or not writes:
            raise BenchmarkContractError("serialized_progress_write_missing")
        if not flushes:
            raise BenchmarkContractError("serialized_progress_flush_missing")
        gaps = [
            later - earlier
            for earlier, later in zip(flushes, flushes[1:])
        ]
        return (
            serialized,
            writes[0],
            flushes[0],
            max(gaps, default=0.0),
            len(writes),
            len(flushes),
        )


def _object_digest(index: int) -> str:
    return hashlib.sha256(
        f"v0412-link-index-benchmark-object:{index}".encode("ascii")
    ).hexdigest()


def _object_id(index: int) -> str:
    return "sha256:" + _object_digest(index)


def _zettel_id(index: int) -> str:
    return f"{ZETTEL_ID_PREFIX}{index:05d}"


def _manifest_record(index: int, padding_bytes: int) -> dict[str, Any]:
    digest = _object_digest(index)
    return {
        "object_id": "sha256:" + digest,
        "sha256": digest,
        "logical_key": f"objects/sha256/{digest[:2]}/{digest}",
        "mime": "application/octet-stream",
        "size_bytes": index,
        "locations": [
            {
                "provider": "local",
                "path": f"objects/sha256/{digest[:2]}/{digest}",
                "availability": "available",
            }
        ],
        "provenance": {
            "source": "synthetic_benchmark",
            "padding": "x" * padding_bytes,
        },
    }


def _manifest_line(index: int, padding_bytes: int) -> bytes:
    return json.dumps(
        _manifest_record(index, padding_bytes),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_manifest(
    manifest_path: Path,
    *,
    object_count: int,
    target_bytes: int,
) -> int:
    base_bytes = sum(
        len(_manifest_line(index, 0)) + 1 for index in range(object_count)
    )
    padding_total = target_bytes - base_bytes
    if padding_total < 0:
        raise BenchmarkContractError("manifest_target_too_small")
    padding_each, padded_remainder = divmod(padding_total, object_count)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("wb") as handle:
        for index in range(object_count):
            padding_bytes = padding_each + int(index < padded_remainder)
            handle.write(_manifest_line(index, padding_bytes))
            handle.write(b"\n")
    actual_bytes = manifest_path.stat().st_size
    if actual_bytes != target_bytes:
        raise BenchmarkContractError("manifest_size_mismatch")
    return actual_bytes


def _zettel_text(index: int, *, existing_object_id: str) -> str:
    assets = "assets: []\n"
    if index == 1:
        assets = (
            "assets:\n"
            f"  - object_id: {existing_object_id}\n"
            f"    role: {ROLE}\n"
        )
    # Every generated body is private-marked.  A single sentinel is enough:
    # the body contains no other text, so any body echo must also echo it.
    private_body = f"\n{PRIVATE_SENTINEL}\n"
    return (
        "---\n"
        f"id: {_zettel_id(index)}\n"
        f"title: Synthetic benchmark item {index}\n"
        'created_at: "2026-08-28T00:00:00+09:00"\n'
        'updated_at: "2026-08-28T00:00:00+09:00"\n'
        f"archive_id: {ARCHIVE_ID}\n"
        "status: canonical\n"
        "kind: benchmark_fixture\n"
        "facets:\n"
        "  domain: benchmark\n"
        + assets
        + "edges: []\n"
        "provenance:\n"
        "  created_by: person:synthetic-benchmark\n"
        f"  created_in: {ARCHIVE_ID}\n"
        "  source: synthetic_benchmark\n"
        "  derived_from: []\n"
        "visibility:\n"
        "  scope: private\n"
        "  allowed_archives: []\n"
        "  source_visibility: private\n"
        "---\n"
        + private_body
    )


def create_fixture(root: Path, profile: BenchmarkProfile) -> FixtureAuthority:
    root.mkdir(parents=True)
    (root / "archive.yml").write_text(
        (
            f"archive_id: {ARCHIVE_ID}\n"
            "name: Synthetic v0.4.12 link-index benchmark\n"
            "type: personal\n"
            "root_policy:\n"
            "  canonical_zettels: zettels/\n"
            "  object_manifest: objects/manifests/files.jsonl\n"
            "storage_policy:\n"
            "  object_identity: sha256\n"
            "  provider_urls_in_zettels: forbidden\n"
            "  locations_live_in_manifest: true\n"
        ),
        encoding="utf-8",
    )
    (root / ".gitignore").write_text(
        (
            ".archive-local/\n"
            "**/db/archive-index.sqlite\n"
            "**/db/archive-index.sqlite-wal\n"
            "**/db/archive-index.sqlite-shm\n"
            "**/db/archive-index.sqlite-journal\n"
            "objects/sha256/\n"
        ),
        encoding="utf-8",
    )
    zettels_root = root / "zettels"
    zettels_root.mkdir()
    existing_object_id = _object_id(1)
    for index in range(profile.zettel_count):
        (zettels_root / f"{_zettel_id(index)}.md").write_text(
            _zettel_text(index, existing_object_id=existing_object_id),
            encoding="utf-8",
        )
    manifest_size = _write_manifest(
        root / "objects" / "manifests" / "files.jsonl",
        object_count=profile.object_count,
        target_bytes=profile.manifest_target_bytes,
    )
    return FixtureAuthority(
        root=root,
        ready_zettel_id=_zettel_id(0),
        existing_zettel_id=_zettel_id(1),
        ready_object_id=_object_id(0),
        existing_object_id=existing_object_id,
        manifest_size_bytes=manifest_size,
    )


def _nearest_rank_p95(values: list[float]) -> float:
    if not values:
        raise BenchmarkContractError("timing_samples_missing")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _environment_specification() -> dict[str, Any]:
    safe_fields = {
        "os_family": platform.system().lower() or "unknown",
        "python_version": platform.python_version(),
        "pointer_bits": struct.calcsize("P") * 8,
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            safe_fields,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        **safe_fields,
        "environment_fingerprint_sha256": "sha256:" + fingerprint,
    }


def _sha256_label(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _path_is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction) and is_junction():
        return True
    try:
        metadata = path.lstat()
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    return bool(getattr(metadata, "st_file_attributes", 0) & reparse_flag)


def _stable_regular_file_bytes(path: Path, *, reason_code: str) -> bytes:
    """Read one exact regular-file image without following a link-like entry."""

    try:
        before = path.lstat()
        if _path_is_link_like(path) or not stat.S_ISREG(before.st_mode):
            raise BenchmarkContractError(reason_code)
        first = path.read_bytes()
        middle = path.lstat()
        second = path.read_bytes()
        after = path.lstat()
    except BenchmarkContractError:
        raise
    except OSError as exc:
        raise BenchmarkContractError(reason_code) from exc
    identity_fields = (
        "st_dev",
        "st_ino",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
        "st_file_attributes",
    )
    identities = [
        tuple(getattr(snapshot, field, None) for field in identity_fields)
        for snapshot in (before, middle, after)
    ]
    if not first or first != second or len(set(identities)) != 1:
        raise BenchmarkContractError(reason_code)
    return first


def _source_package_inventory() -> dict[str, tuple[int, str]]:
    inventory: dict[str, tuple[int, str]] = {}
    if _path_is_link_like(SOURCE_ROOT) or _path_is_link_like(PACKAGE_ROOT):
        raise BenchmarkContractError("source_package_symlink_forbidden")
    for path in sorted(PACKAGE_ROOT.rglob("*")):
        # Check the directory entry before following it with is_file/read_bytes.
        # In particular, a dangling ignored symlink reports is_file() == False.
        if _path_is_link_like(path):
            raise BenchmarkContractError("source_package_symlink_forbidden")
        if path.is_dir():
            continue
        if not path.is_file():
            raise BenchmarkContractError("source_package_entry_type_forbidden")
        relative_parts = path.relative_to(SOURCE_ROOT).parts
        if (
            "__pycache__" in relative_parts
            or path.suffix.casefold() in {".pyc", ".pyo"}
        ):
            continue
        raw = path.read_bytes()
        relative = Path(*relative_parts).as_posix()
        inventory[relative] = (len(raw), hashlib.sha256(raw).hexdigest())
    if not inventory:
        raise BenchmarkContractError("source_package_inventory_empty")
    return inventory


def _inventory_sha256(inventory: Mapping[str, tuple[int, str]]) -> str:
    canonical = [
        {
            "path": path,
            "size_bytes": size_bytes,
            "sha256": digest,
        }
        for path, (size_bytes, digest) in sorted(inventory.items())
    ]
    raw = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_label(raw)


def _wheel_member_is_safe(member: zipfile.ZipInfo) -> bool:
    name = member.filename
    normalized = name[:-1] if member.is_dir() and name.endswith("/") else name
    parts = normalized.split("/")
    unix_mode = int(member.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(unix_mode)
    dos_attributes = int(member.external_attr) & 0xFFFF
    expected_types = (
        {0, stat.S_IFDIR} if member.is_dir() else {0, stat.S_IFREG}
    )
    return bool(
        normalized
        and "\x00" not in normalized
        and "\\" not in normalized
        and not normalized.startswith("/")
        and re.match(r"^[A-Za-z]:", normalized) is None
        and all(part not in {"", ".", ".."} for part in parts)
        and file_type in expected_types
        and not (dos_attributes & 0x0400)
    )


def _wheel_package_inventory_from_bytes(
    wheel_raw: bytes,
) -> tuple[dict[str, tuple[int, str]], str, str]:
    try:
        with zipfile.ZipFile(io.BytesIO(wheel_raw), "r") as wheel:
            members = wheel.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)):
                raise BenchmarkContractError("benchmark_wheel_duplicate_member")
            if any(not _wheel_member_is_safe(member) for member in members):
                raise BenchmarkContractError("benchmark_wheel_member_unsafe")
            metadata_names = [
                name
                for name in names
                if name.endswith(".dist-info/METADATA")
            ]
            wheel_metadata_names = [
                name
                for name in names
                if name.endswith(".dist-info/WHEEL")
            ]
            if len(metadata_names) != 1 or len(wheel_metadata_names) != 1:
                raise BenchmarkContractError("benchmark_wheel_metadata_invalid")
            metadata = wheel.read(metadata_names[0]).decode("utf-8", "strict")
            name_match = re.search(r"(?m)^Name:\s*(\S+)\s*$", metadata)
            version_match = re.search(r"(?m)^Version:\s*(\S+)\s*$", metadata)
            if name_match is None or version_match is None:
                raise BenchmarkContractError("benchmark_wheel_metadata_invalid")
            distribution = name_match.group(1)
            version = version_match.group(1)
            inventory: dict[str, tuple[int, str]] = {}
            for member in members:
                name = member.filename
                if member.is_dir() or not name.startswith("wom_kit/"):
                    continue
                raw = wheel.read(member)
                inventory[name] = (
                    len(raw),
                    hashlib.sha256(raw).hexdigest(),
                )
    except (OSError, UnicodeError, zipfile.BadZipFile) as exc:
        raise BenchmarkContractError("benchmark_wheel_unreadable") from exc
    if not inventory:
        raise BenchmarkContractError("benchmark_wheel_package_empty")
    return inventory, distribution, version


def _wheel_package_inventory(
    wheel_path: Path,
) -> tuple[dict[str, tuple[int, str]], str, str, bytes]:
    if not wheel_path.is_file() or wheel_path.suffix.casefold() != ".whl":
        raise BenchmarkContractError("benchmark_wheel_missing")
    try:
        wheel_raw = wheel_path.read_bytes()
    except OSError as exc:
        raise BenchmarkContractError("benchmark_wheel_unreadable") from exc
    inventory, distribution, version = _wheel_package_inventory_from_bytes(
        wheel_raw
    )
    return inventory, distribution, version, wheel_raw


def _run_git_bytes(arguments: list[str]) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(KIT_ROOT), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        raise BenchmarkContractError("benchmark_git_evidence_unavailable")
    return bytes(completed.stdout)


def _run_git_blob_batch(oids: list[str]) -> list[bytes]:
    if not oids:
        return []
    completed = subprocess.run(
        ["git", "-C", str(KIT_ROOT), "cat-file", "--batch"],
        input=("\n".join(oids) + "\n").encode("ascii"),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        raise BenchmarkContractError("benchmark_git_evidence_unavailable")
    raw = bytes(completed.stdout)
    cursor = 0
    blobs: list[bytes] = []
    for expected_oid in oids:
        header_end = raw.find(b"\n", cursor)
        if header_end < 0:
            raise BenchmarkContractError("benchmark_git_blob_batch_invalid")
        try:
            returned_oid, object_type, encoded_size = raw[
                cursor:header_end
            ].split(b" ", 2)
            size = int(encoded_size.decode("ascii", "strict"))
        except (UnicodeError, ValueError) as exc:
            raise BenchmarkContractError(
                "benchmark_git_blob_batch_invalid"
            ) from exc
        content_start = header_end + 1
        content_end = content_start + size
        if (
            returned_oid.decode("ascii", "strict") != expected_oid
            or object_type != b"blob"
            or size < 0
            or content_end >= len(raw)
            or raw[content_end : content_end + 1] != b"\n"
        ):
            raise BenchmarkContractError("benchmark_git_blob_batch_invalid")
        blobs.append(raw[content_start:content_end])
        cursor = content_end + 1
    if cursor != len(raw):
        raise BenchmarkContractError("benchmark_git_blob_batch_invalid")
    return blobs


def _git_head_blob_or_none(repo_relative: str) -> bytes | None:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(KIT_ROOT),
            "cat-file",
            "blob",
            f"HEAD:{repo_relative}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return bytes(completed.stdout)


def _git_scoped_change_count(kit_relative: str) -> int:
    raw = _run_git_bytes(
        [
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
            "--",
            kit_relative,
        ]
    )
    return len([record for record in raw.split(b"\0") if record])


def _git_head_package_inventory(
    source_repo_relative: str,
) -> dict[str, tuple[int, str]]:
    """Read the exact committed package bytes, including Git-ignore gaps."""

    package_prefix = f"{source_repo_relative}/wom_kit"
    raw = _run_git_bytes(
        [
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            "HEAD",
            "--",
            f":(top,literal){package_prefix}",
        ]
    )
    entries: list[tuple[str, str]] = []
    seen_paths: set[str] = set()
    for encoded_entry in raw.split(b"\0"):
        if not encoded_entry:
            continue
        try:
            encoded_metadata, encoded_path = encoded_entry.split(b"\t", 1)
            mode, object_type, encoded_oid = encoded_metadata.split(b" ", 2)
            repo_relative = encoded_path.decode("utf-8", "strict")
            oid = encoded_oid.decode("ascii", "strict")
        except (UnicodeError, ValueError) as exc:
            raise BenchmarkContractError(
                "benchmark_git_package_tree_invalid"
            ) from exc
        if (
            mode not in {b"100644", b"100755"}
            or object_type != b"blob"
            or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid) is None
            or not repo_relative.startswith(package_prefix + "/")
        ):
            raise BenchmarkContractError(
                "benchmark_git_package_tree_invalid"
            )
        source_relative = repo_relative.removeprefix(
            source_repo_relative + "/"
        )
        relative_parts = Path(source_relative).parts
        if (
            not source_relative
            or "__pycache__" in relative_parts
            or Path(source_relative).suffix.casefold() in {".pyc", ".pyo"}
            or source_relative in seen_paths
        ):
            raise BenchmarkContractError(
                "benchmark_git_package_tree_invalid"
            )
        seen_paths.add(source_relative)
        entries.append((source_relative, oid))
    inventory: dict[str, tuple[int, str]] = {}
    blobs = _run_git_blob_batch([oid for _relative, oid in entries])
    for (source_relative, _oid), blob in zip(entries, blobs, strict=True):
        inventory[source_relative] = (
            len(blob),
            hashlib.sha256(blob).hexdigest(),
        )
    if not inventory:
        raise BenchmarkContractError("benchmark_git_package_tree_empty")
    return inventory


def _inventory_delta_count(
    left: Mapping[str, tuple[int, str]],
    right: Mapping[str, tuple[int, str]],
) -> int:
    return sum(
        left.get(path) != right.get(path)
        for path in set(left).union(right)
    )


def _provenance_document(wheel_path: Path) -> dict[str, Any]:
    source_inventory = _source_package_inventory()
    (
        wheel_inventory,
        distribution,
        version,
        wheel_raw,
    ) = _wheel_package_inventory(wheel_path)
    source_tree_sha256 = _inventory_sha256(source_inventory)
    wheel_package_tree_sha256 = _inventory_sha256(wheel_inventory)
    benchmark_raw = _stable_regular_file_bytes(
        BENCHMARK_PATH,
        reason_code="benchmark_script_unstable",
    )

    repo_root_raw = _run_git_bytes(["rev-parse", "--show-toplevel"])
    try:
        # Canonical paths are needed only for containment/relative path math:
        # Windows may spell TEMP with a short 8.3 alias while Git returns the
        # long spelling. Link-like source/script entries were rejected above.
        repo_root = Path(repo_root_raw.decode("utf-8", "strict").strip()).resolve()
        source_repo_relative = (
            SOURCE_ROOT.resolve().relative_to(repo_root).as_posix()
        )
        source_kit_relative = (
            SOURCE_ROOT.resolve().relative_to(KIT_ROOT.resolve()).as_posix()
        )
        benchmark_kit_relative = (
            BENCHMARK_PATH.resolve().relative_to(KIT_ROOT.resolve()).as_posix()
        )
        benchmark_repo_relative = (
            BENCHMARK_PATH.resolve().relative_to(repo_root).as_posix()
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise BenchmarkContractError("benchmark_git_scope_invalid") from exc

    committed_source_inventory = _git_head_package_inventory(
        source_repo_relative
    )
    committed_benchmark_raw = _git_head_blob_or_none(
        benchmark_repo_relative
    )

    commit_oid = _run_git_bytes(["rev-parse", "HEAD"]).decode(
        "ascii", "strict"
    ).strip()
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit_oid) is None:
        raise BenchmarkContractError("benchmark_git_commit_invalid")
    commit_content = _run_git_bytes(["cat-file", "commit", "HEAD"])
    commit_object = (
        b"commit "
        + str(len(commit_content)).encode("ascii")
        + b"\0"
        + commit_content
    )
    commit_oid_recomputed = (
        hashlib.sha1(commit_object, usedforsecurity=False).hexdigest()
        if len(commit_oid) == 40
        else hashlib.sha256(commit_object).hexdigest()
    )
    if commit_oid_recomputed != commit_oid:
        raise BenchmarkContractError("benchmark_git_commit_object_mismatch")
    source_tree_oid = _run_git_bytes(
        ["rev-parse", f"HEAD:{source_repo_relative}/wom_kit"]
    ).decode("ascii", "strict").strip()
    if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", source_tree_oid) is None:
        raise BenchmarkContractError("benchmark_git_tree_invalid")

    git_status_change_count = (
        _git_scoped_change_count(source_kit_relative)
        + _git_scoped_change_count(benchmark_kit_relative)
    )
    source_inventory_delta_count = _inventory_delta_count(
        source_inventory,
        committed_source_inventory,
    )
    benchmark_matches_commit = (
        committed_benchmark_raw is not None
        and benchmark_raw == committed_benchmark_raw
    )
    wheel_matches_source = wheel_inventory == source_inventory
    wheel_distribution_exact = distribution == EXPECTED_DISTRIBUTION
    wheel_version_exact = version == EXPECTED_VERSION
    source_matches_commit = source_inventory_delta_count == 0
    exact_commit_delta_count = source_inventory_delta_count + int(
        not benchmark_matches_commit
    )
    return {
        "source_tree_sha256": source_tree_sha256,
        "source_tree_entry_count": len(source_inventory),
        "git_source_tree_oid": (
            ("sha1:" if len(source_tree_oid) == 40 else "sha256:")
            + source_tree_oid
        ),
        "git_commit_oid": (
            ("sha1:" if len(commit_oid) == 40 else "sha256:") + commit_oid
        ),
        "git_commit_sha256": _sha256_label(commit_object),
        "benchmark_script_sha256": _sha256_label(benchmark_raw),
        "wheel_sha256": _sha256_label(wheel_raw),
        "wheel_package_tree_sha256": wheel_package_tree_sha256,
        "wheel_package_entry_count": len(wheel_inventory),
        "wheel_distribution_exact": wheel_distribution_exact,
        "wheel_version_exact": wheel_version_exact,
        "wheel_matches_source_tree": wheel_matches_source,
        "source_tree_matches_git_commit": source_matches_commit,
        "benchmark_script_matches_git_commit": benchmark_matches_commit,
        "source_inventory_delta_count": source_inventory_delta_count,
        "git_status_change_count": git_status_change_count,
        "scoped_uncommitted_entry_count": exact_commit_delta_count,
        "private_paths_included": False,
    }


def _provenance_sha256(provenance: Mapping[str, Any]) -> str:
    raw = json.dumps(
        provenance,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_label(raw)


def _verify_bootstrap_authority(
    authority: BootstrapAuthority,
) -> dict[str, str]:
    if (
        authority.source_script_path != BENCHMARK_PATH
        or authority.executing_script_path != EXECUTING_BENCHMARK_PATH
        or authority.source_script_path == authority.executing_script_path
        or re.fullmatch(r"sha256:[0-9a-f]{64}", authority.expected_script_sha256)
        is None
        or re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            authority.expected_provenance_sha256,
        )
        is None
    ):
        raise BenchmarkContractError("benchmark_bootstrap_authority_invalid")
    source_raw = _stable_regular_file_bytes(
        authority.source_script_path,
        reason_code="benchmark_bootstrap_source_script_unstable",
    )
    executing_raw = _stable_regular_file_bytes(
        authority.executing_script_path,
        reason_code="benchmark_bootstrap_driver_unstable",
    )
    if (
        source_raw != executing_raw
        or _sha256_label(source_raw) != authority.expected_script_sha256
    ):
        raise BenchmarkContractError("benchmark_bootstrap_driver_mismatch")
    return {
        "executing_benchmark_script_sha256": _sha256_label(executing_raw),
        "bootstrap_supervisor_provenance_sha256": (
            authority.expected_provenance_sha256
        ),
    }


def _runtime_package_inventory(
    runtime_root: Path,
) -> dict[str, tuple[int, str]]:
    package_root = runtime_root / "wom_kit"
    if (
        not runtime_root.is_dir()
        or not package_root.is_dir()
        or _path_is_link_like(runtime_root)
        or _path_is_link_like(package_root)
    ):
        raise BenchmarkContractError("benchmark_runtime_materialization_unsafe")
    inventory: dict[str, tuple[int, str]] = {}
    for path in sorted(package_root.rglob("*")):
        if _path_is_link_like(path):
            raise BenchmarkContractError(
                "benchmark_runtime_materialization_unsafe"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise BenchmarkContractError(
                "benchmark_runtime_materialization_unsafe"
            )
        relative_parts = path.relative_to(runtime_root).parts
        if (
            "__pycache__" in relative_parts
            or path.suffix.casefold() in {".pyc", ".pyo"}
        ):
            continue
        raw = path.read_bytes()
        inventory[Path(*relative_parts).as_posix()] = (
            len(raw),
            hashlib.sha256(raw).hexdigest(),
        )
    if not inventory:
        raise BenchmarkContractError("benchmark_runtime_materialization_empty")
    return inventory


def _materialize_captured_wheel_runtime(
    wheel_raw: bytes,
    runtime_root: Path,
    *,
    expected_inventory: Mapping[str, tuple[int, str]],
) -> None:
    if runtime_root.exists() or _path_is_link_like(runtime_root.parent):
        raise BenchmarkContractError("benchmark_runtime_materialization_unsafe")
    try:
        runtime_root.mkdir()
        with zipfile.ZipFile(io.BytesIO(wheel_raw), "r") as wheel:
            for member in wheel.infolist():
                if not _wheel_member_is_safe(member):
                    raise BenchmarkContractError(
                        "benchmark_wheel_member_unsafe"
                    )
                name = member.filename
                if member.is_dir() or not name.startswith("wom_kit/"):
                    continue
                if name not in expected_inventory:
                    raise BenchmarkContractError(
                        "benchmark_runtime_materialization_mismatch"
                    )
                target = runtime_root.joinpath(*name.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                if any(
                    _path_is_link_like(parent)
                    for parent in (
                        runtime_root,
                        *target.parents,
                    )
                    if parent == runtime_root or runtime_root in parent.parents
                ):
                    raise BenchmarkContractError(
                        "benchmark_runtime_materialization_unsafe"
                    )
                raw = wheel.read(member)
                with target.open("xb") as handle:
                    handle.write(raw)
        materialized_inventory = _runtime_package_inventory(runtime_root)
    except BenchmarkContractError:
        raise
    except (OSError, UnicodeError, ValueError, zipfile.BadZipFile) as exc:
        raise BenchmarkContractError(
            "benchmark_runtime_materialization_failed"
        ) from exc
    if materialized_inventory != dict(expected_inventory):
        raise BenchmarkContractError(
            "benchmark_runtime_materialization_mismatch"
        )


def _loaded_runtime_binding(
    runtime_root: Path,
    *,
    wheel_inventory: Mapping[str, tuple[int, str]],
) -> dict[str, Any]:
    runtime_inventory = _runtime_package_inventory(runtime_root)
    if runtime_inventory != dict(wheel_inventory):
        raise BenchmarkContractError("benchmark_loaded_runtime_mismatch")
    records: list[dict[str, Any]] = []
    loaded_names = sorted(
        name
        for name in sys.modules
        if name == "wom_kit" or name.startswith("wom_kit.")
    )
    required_names = {
        "wom_kit",
        "wom_kit.archive_cli",
        "wom_kit.archive_services",
        "wom_kit.completion_workflows",
    }
    if not required_names.issubset(loaded_names):
        raise BenchmarkContractError("benchmark_loaded_runtime_incomplete")
    for module_name in loaded_names:
        module = sys.modules.get(module_name)
        module_file_value = getattr(module, "__file__", None)
        if not isinstance(module, ModuleType) or not isinstance(
            module_file_value, str
        ):
            raise BenchmarkContractError("benchmark_loaded_runtime_namespace")
        module_file = Path(module_file_value)
        try:
            resolved_file = module_file.resolve(strict=True)
            relative = resolved_file.relative_to(
                runtime_root.resolve(strict=True)
            ).as_posix()
        except (OSError, ValueError) as exc:
            raise BenchmarkContractError(
                "benchmark_loaded_runtime_origin_mismatch"
            ) from exc
        if (
            resolved_file.suffix.casefold() != ".py"
            or _path_is_link_like(resolved_file)
            or relative not in wheel_inventory
        ):
            raise BenchmarkContractError(
                "benchmark_loaded_runtime_origin_mismatch"
            )
        raw = resolved_file.read_bytes()
        observed = (len(raw), hashlib.sha256(raw).hexdigest())
        if observed != wheel_inventory[relative]:
            raise BenchmarkContractError(
                "benchmark_loaded_runtime_content_mismatch"
            )
        records.append(
            {
                "module": module_name,
                "member": relative,
                "size_bytes": observed[0],
                "sha256": observed[1],
            }
        )
    encoded = json.dumps(
        records,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "runtime_package_tree_sha256": _inventory_sha256(
            runtime_inventory
        ),
        "runtime_package_entry_count": len(runtime_inventory),
        "loaded_module_binding_sha256": _sha256_label(encoded),
        "loaded_module_count": len(records),
    }


@dataclass(frozen=True)
class LoadedRuntimeAuthority:
    runtime_root: Path
    wheel_inventory: Mapping[str, tuple[int, str]]
    initial_binding: Mapping[str, Any]

    def snapshot(self) -> dict[str, Any]:
        return _loaded_runtime_binding(
            self.runtime_root,
            wheel_inventory=self.wheel_inventory,
        )


@contextmanager
def _activated_captured_wheel_runtime(
    wheel_path: Path,
    provenance: Mapping[str, Any],
    *,
    runtime_root: Path,
) -> Iterator[LoadedRuntimeAuthority]:
    if any(
        name == "wom_kit" or name.startswith("wom_kit.")
        for name in sys.modules
    ):
        raise BenchmarkContractError("benchmark_runtime_preloaded")
    try:
        wheel_raw = wheel_path.read_bytes()
    except OSError as exc:
        raise BenchmarkContractError("benchmark_wheel_unreadable") from exc
    wheel_inventory, distribution, version = (
        _wheel_package_inventory_from_bytes(wheel_raw)
    )
    if (
        _sha256_label(wheel_raw) != provenance.get("wheel_sha256")
        or _inventory_sha256(wheel_inventory)
        != provenance.get("wheel_package_tree_sha256")
        or len(wheel_inventory)
        != int(provenance.get("wheel_package_entry_count") or -1)
        or distribution != EXPECTED_DISTRIBUTION
        or version != EXPECTED_VERSION
        or provenance.get("wheel_matches_source_tree") is not True
        or provenance.get("wheel_distribution_exact") is not True
        or provenance.get("wheel_version_exact") is not True
    ):
        raise BenchmarkContractError("benchmark_runtime_wheel_binding_mismatch")
    _materialize_captured_wheel_runtime(
        wheel_raw,
        runtime_root,
        expected_inventory=wheel_inventory,
    )

    previous_sys_path = list(sys.path)
    previous_dont_write_bytecode = sys.dont_write_bytecode
    missing = object()
    previous_globals = {
        name: globals().get(name, missing)
        for name in (
            "archive_cli",
            "archive_services",
            "completion_workflows",
        )
    }
    try:
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(runtime_root))
        importlib.invalidate_caches()
        loaded_archive_cli = importlib.import_module("wom_kit.archive_cli")
        loaded_archive_services = importlib.import_module(
            "wom_kit.archive_services"
        )
        loaded_completion_workflows = importlib.import_module(
            "wom_kit.completion_workflows"
        )
        globals().update(
            {
                "archive_cli": loaded_archive_cli,
                "archive_services": loaded_archive_services,
                "completion_workflows": loaded_completion_workflows,
            }
        )
        initial_binding = _loaded_runtime_binding(
            runtime_root,
            wheel_inventory=wheel_inventory,
        )
        yield LoadedRuntimeAuthority(
            runtime_root=runtime_root,
            wheel_inventory=wheel_inventory,
            initial_binding=initial_binding,
        )
    finally:
        for name in tuple(sys.modules):
            if name == "wom_kit" or name.startswith("wom_kit."):
                sys.modules.pop(name, None)
        importlib.invalidate_caches()
        sys.path[:] = previous_sys_path
        sys.dont_write_bytecode = previous_dont_write_bytecode
        for name, previous in previous_globals.items():
            if previous is missing:
                globals().pop(name, None)
            else:
                globals()[name] = previous


def _serialized_output_safety(
    serialized: str,
    *,
    forbidden_values: tuple[str, ...],
    zettel_ids: tuple[str, ...],
    object_ids: tuple[str, ...],
) -> dict[str, int]:
    windows_absolute_path_count = len(
        re.findall(r"[A-Za-z]:[\\/]", serialized)
    ) + len(re.findall(r"\\{2,}[^\\\s]+", serialized))
    unix_absolute_path_count = len(
        # A schema such as "wom-kit/v1" is not an absolute path because the
        # slash follows a word character. Values such as /workspace, /var,
        # and path=/private are caught without assuming a particular runner.
        re.findall(r"(?<![A-Za-z0-9_.-])/(?!/)", serialized)
    )
    known_zettel_ids = frozenset(zettel_ids)
    known_object_ids = frozenset(object_ids)
    zettel_id_occurrences = sum(
        match.group(0) in known_zettel_ids
        for match in re.finditer(
            re.escape(ZETTEL_ID_PREFIX) + r"[0-9]{5}",
            serialized,
        )
    )
    object_id_occurrences = sum(
        match.group(0) in known_object_ids
        for match in re.finditer(r"sha256:[0-9a-f]{64}", serialized)
    )
    return {
        "private_sentinel_occurrences": serialized.count(PRIVATE_SENTINEL),
        "absolute_path_occurrences": (
            windows_absolute_path_count + unix_absolute_path_count
        ),
        "zettel_id_occurrences": zettel_id_occurrences,
        "object_id_occurrences": object_id_occurrences,
        "forbidden_value_occurrences": sum(
            serialized.count(value) for value in forbidden_values if value
        ),
    }


def _profile_source_bound_to_commit(
    profile: BenchmarkProfile,
    provenance: Mapping[str, Any],
) -> bool:
    if profile.name != FULL_PROFILE.name:
        return True
    return (
        provenance["source_tree_matches_git_commit"] is True
        and provenance["benchmark_script_matches_git_commit"] is True
        and int(provenance["source_inventory_delta_count"]) == 0
        and int(provenance["git_status_change_count"]) == 0
        and int(provenance["scoped_uncommitted_entry_count"]) == 0
    )


def _safe_failure(profile: BenchmarkProfile, reason_code: str) -> dict[str, Any]:
    return {
        "ok": False,
        "schema": BENCHMARK_SCHEMA,
        "profile": profile.name,
        "reason_codes": [reason_code],
        "counts": {
            "zettels": profile.zettel_count,
            "objets": profile.object_count,
            "manifest_target_bytes": profile.manifest_target_bytes,
        },
        "environment": _environment_specification(),
        "private_values_echoed": False,
        "absolute_paths_echoed": False,
        "zettel_ids_echoed": False,
        "object_ids_echoed": False,
    }


def _measure_plan(
    fixture: FixtureAuthority,
    *,
    zettel_id: str,
    object_id: str,
    expected_state: str,
    authority_projection: Mapping[str, Any] | None,
) -> PlanMeasurement:
    started = time.perf_counter()
    capture = SerializedProgressCapture(origin=started)
    with mock.patch.object(archive_cli.sys, "stderr", capture):
        reporter = archive_cli.CommandProgressReporter(
            True,
            label="zettel-objet-link-benchmark",
            heartbeat_interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
            stage_order=("zettel-objet-link-plan",),
        )
        try:
            reporter.progress("zettel-objet-link-plan", "start", 0, 1)
            result = completion_workflows.zettel_objet_link_plan(
                fixture.root,
                zettel_id=zettel_id,
                object_id=object_id,
                role=ROLE,
                authority_projection=authority_projection,
            )
            reporter.progress("zettel-objet-link-plan", "done", 1, 1)
        finally:
            reporter.close()
    elapsed = time.perf_counter() - started
    if result.get("ok") is not True or result.get("state") != expected_state:
        raise BenchmarkContractError("plan_fixed_state_mismatch")
    (
        serialized_progress,
        first_write,
        first_flush,
        max_flush_gap,
        write_calls,
        flush_calls,
    ) = capture.evidence()
    return PlanMeasurement(
        duration_seconds=elapsed,
        first_serialized_write_seconds=first_write,
        first_serialized_flush_seconds=first_flush,
        max_serialized_flush_gap_seconds=max_flush_gap,
        serialized_progress=serialized_progress,
        serialized_write_calls=write_calls,
        serialized_flush_calls=flush_calls,
        state=str(result["state"]),
    )


def _timing_document(measurements: list[PlanMeasurement]) -> dict[str, Any]:
    durations = [item.duration_seconds for item in measurements]
    return {
        "samples": [round(value, 6) for value in durations],
        "p95": round(_nearest_rank_p95(durations), 6),
        "state": measurements[0].state,
    }


def _run_plan_measurements(
    fixture: FixtureAuthority,
    profile: BenchmarkProfile,
    projection: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], PlanInstrumentation, str]:
    instrumentation = PlanInstrumentation()
    original_lookup = (
        archive_services.lookup_zettel_objet_link_authority_projection
    )
    original_json_loads = json.loads
    lookup_depth = 0

    def forbidden_legacy_resolver(*_args: Any, **_kwargs: Any) -> Any:
        instrumentation.legacy_full_zettel_resolver_calls += 1
        raise BenchmarkContractError("legacy_full_zettel_resolver_called")

    def forbidden_full_manifest_parser(*_args: Any, **_kwargs: Any) -> Any:
        instrumentation.full_manifest_parser_calls += 1
        raise BenchmarkContractError("full_manifest_parser_called")

    def observed_lookup(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal lookup_depth
        outermost = lookup_depth == 0
        if outermost:
            instrumentation.authority_lookup_calls += 1
        lookup_depth += 1
        try:
            result = original_lookup(*args, **kwargs)
        finally:
            lookup_depth -= 1
        rows = result.get("manifest_records") if isinstance(result, dict) else None
        if outermost and isinstance(rows, list):
            instrumentation.target_manifest_rows_returned += len(rows)
        return result

    def observed_json_loads(*args: Any, **kwargs: Any) -> Any:
        value = original_json_loads(*args, **kwargs)
        if lookup_depth <= 0:
            return value
        if (
            isinstance(value, dict)
            and isinstance(value.get("object_id"), str)
            and isinstance(value.get("sha256"), str)
            and isinstance(value.get("logical_key"), str)
            and isinstance(value.get("locations"), list)
            and isinstance(value.get("provenance"), dict)
        ):
            instrumentation.target_manifest_json_parses += 1
        else:
            instrumentation.non_target_lookup_json_parses += 1
        return value

    measurements: dict[str, list[PlanMeasurement]] = {
        "cold_ready": [],
        "cold_already_present": [],
        "warm_ready": [],
        "warm_already_present": [],
    }
    with (
        mock.patch.object(
            completion_workflows,
            "_resolve_zettel_objet_link_target_bound",
            side_effect=forbidden_legacy_resolver,
        ),
        mock.patch.object(
            completion_workflows,
            "_strict_zettel_objet_manifest_records",
            side_effect=forbidden_full_manifest_parser,
        ),
        mock.patch.object(
            completion_workflows,
            "_strict_zettel_objet_manifest_records_from_bytes",
            side_effect=forbidden_full_manifest_parser,
        ),
        mock.patch.object(
            archive_services,
            "archive_index_strict_manifest_snapshot",
            side_effect=forbidden_full_manifest_parser,
        ),
        mock.patch.object(
            archive_services,
            "lookup_zettel_objet_link_authority_projection",
            side_effect=observed_lookup,
        ),
        mock.patch.object(
            archive_services.json,
            "loads",
            side_effect=observed_json_loads,
        ),
    ):
        for _index in range(profile.cold_iterations):
            measurements["cold_ready"].append(
                _measure_plan(
                    fixture,
                    zettel_id=fixture.ready_zettel_id,
                    object_id=fixture.ready_object_id,
                    expected_state="ready",
                    authority_projection=None,
                )
            )
            measurements["cold_already_present"].append(
                _measure_plan(
                    fixture,
                    zettel_id=fixture.existing_zettel_id,
                    object_id=fixture.existing_object_id,
                    expected_state="already_present",
                    authority_projection=None,
                )
            )
        for _index in range(profile.warm_iterations):
            measurements["warm_ready"].append(
                _measure_plan(
                    fixture,
                    zettel_id=fixture.ready_zettel_id,
                    object_id=fixture.ready_object_id,
                    expected_state="ready",
                    authority_projection=projection,
                )
            )
            measurements["warm_already_present"].append(
                _measure_plan(
                    fixture,
                    zettel_id=fixture.existing_zettel_id,
                    object_id=fixture.existing_object_id,
                    expected_state="already_present",
                    authority_projection=projection,
                )
            )

    all_measurements = [
        item for group in measurements.values() for item in group
    ]
    instrumentation.normal_plan_calls = len(all_measurements)
    timing = {
        key: _timing_document(value) for key, value in measurements.items()
    }
    status = {
        "first_serialized_write_seconds_max": round(
            max(
                item.first_serialized_write_seconds
                for item in all_measurements
            ),
            6,
        ),
        "first_serialized_flush_seconds_max": round(
            max(
                item.first_serialized_flush_seconds
                for item in all_measurements
            ),
            6,
        ),
        "max_serialized_flush_gap_seconds": round(
            max(
                item.max_serialized_flush_gap_seconds
                for item in all_measurements
            ),
            6,
        ),
        "heartbeat_interval_seconds": HEARTBEAT_INTERVAL_SECONDS,
        "serialized_stream_count": len(all_measurements),
        "serialized_line_count": sum(
            item.serialized_progress.count("\n") for item in all_measurements
        ),
        "serialized_utf8_bytes": sum(
            len(item.serialized_progress.encode("utf-8"))
            for item in all_measurements
        ),
        "serialized_write_calls": sum(
            item.serialized_write_calls for item in all_measurements
        ),
        "serialized_flush_calls": sum(
            item.serialized_flush_calls for item in all_measurements
        ),
    }
    framed_stream = b"".join(
        len(item.serialized_progress.encode("utf-8")).to_bytes(8, "big")
        + item.serialized_progress.encode("utf-8")
        for item in all_measurements
    )
    status["serialized_streams_sha256"] = (
        "sha256:" + hashlib.sha256(framed_stream).hexdigest()
    )
    combined_stream = "".join(
        item.serialized_progress for item in all_measurements
    )
    return timing, status, instrumentation, combined_stream


def run_benchmark(
    profile: BenchmarkProfile,
    *,
    wheel_path: Path,
    bootstrap_authority: BootstrapAuthority | None = None,
) -> dict[str, Any]:
    bootstrap_initial = (
        _verify_bootstrap_authority(bootstrap_authority)
        if bootstrap_authority is not None
        else None
    )
    source_provenance = _provenance_document(wheel_path)
    if bootstrap_authority is not None and (
        source_provenance.get("benchmark_script_sha256")
        != bootstrap_authority.expected_script_sha256
        or _provenance_sha256(source_provenance)
        != bootstrap_authority.expected_provenance_sha256
    ):
        raise BenchmarkContractError("benchmark_bootstrap_provenance_mismatch")
    with ExitStack() as benchmark_stack:
        temporary = benchmark_stack.enter_context(
            tempfile.TemporaryDirectory(
                prefix="wom-v0412-link-index-benchmark-"
            )
        )
        runtime_authority = benchmark_stack.enter_context(
            _activated_captured_wheel_runtime(
                wheel_path,
                source_provenance,
                runtime_root=Path(temporary) / "runtime",
            )
        )
        provenance = dict(source_provenance)
        root = Path(temporary) / "archive"
        fixture_started = time.perf_counter()
        fixture = create_fixture(root, profile)
        fixture_seconds = time.perf_counter() - fixture_started

        index_started = time.perf_counter()
        indexed = archive_services.index_archive(root)
        index_seconds = time.perf_counter() - index_started
        if (
            indexed.get("ok") is not True
            or int(indexed.get("zettels") or -1) != profile.zettel_count
            or int(indexed.get("objects") or -1) != profile.object_count
        ):
            raise BenchmarkContractError("index_rebuild_failed")

        projection_started = time.perf_counter()
        projection = (
            completion_workflows.build_zettel_objet_link_authority_projection(
                root
            )
        )
        projection_seconds = time.perf_counter() - projection_started
        if projection.get("ok") is not True:
            raise BenchmarkContractError("authority_projection_unavailable")

        (
            plan_timing,
            status_timing,
            instrumentation,
            serialized_progress,
        ) = (
            _run_plan_measurements(fixture, profile, projection)
        )
        expected_plan_calls = 2 * (
            profile.cold_iterations + profile.warm_iterations
        )
        final_runtime_binding = runtime_authority.snapshot()
        final_source_provenance = _provenance_document(wheel_path)
        bootstrap_final = (
            _verify_bootstrap_authority(bootstrap_authority)
            if bootstrap_authority is not None
            else None
        )
        bootstrap_verified = bool(
            bootstrap_initial is not None
            and bootstrap_final == bootstrap_initial
            and bootstrap_initial[
                "executing_benchmark_script_sha256"
            ]
            == provenance["benchmark_script_sha256"]
            and bootstrap_initial[
                "bootstrap_supervisor_provenance_sha256"
            ]
            == _provenance_sha256(source_provenance)
        )
        initial_runtime_binding = dict(runtime_authority.initial_binding)
        loaded_runtime_bound_to_captured_wheel = bool(
            initial_runtime_binding["runtime_package_tree_sha256"]
            == provenance["wheel_package_tree_sha256"]
            and final_runtime_binding["runtime_package_tree_sha256"]
            == provenance["wheel_package_tree_sha256"]
            and int(initial_runtime_binding["runtime_package_entry_count"])
            == int(provenance["wheel_package_entry_count"])
            and int(final_runtime_binding["runtime_package_entry_count"])
            == int(provenance["wheel_package_entry_count"])
            and int(final_runtime_binding["loaded_module_count"])
            >= int(initial_runtime_binding["loaded_module_count"])
        )
        provenance.update(
            {
                "loaded_runtime_package_tree_sha256": (
                    final_runtime_binding["runtime_package_tree_sha256"]
                ),
                "loaded_runtime_package_entry_count": int(
                    final_runtime_binding["runtime_package_entry_count"]
                ),
                "loaded_runtime_initial_module_binding_sha256": (
                    initial_runtime_binding["loaded_module_binding_sha256"]
                ),
                "loaded_runtime_initial_module_count": int(
                    initial_runtime_binding["loaded_module_count"]
                ),
                "loaded_runtime_final_module_binding_sha256": (
                    final_runtime_binding["loaded_module_binding_sha256"]
                ),
                "loaded_runtime_final_module_count": int(
                    final_runtime_binding["loaded_module_count"]
                ),
                "executing_benchmark_script_sha256": (
                    bootstrap_final[
                        "executing_benchmark_script_sha256"
                    ]
                    if bootstrap_final is not None
                    else ""
                ),
                "bootstrap_supervisor_provenance_sha256": (
                    bootstrap_final[
                        "bootstrap_supervisor_provenance_sha256"
                    ]
                    if bootstrap_final is not None
                    else ""
                ),
                "bootstrap_verified": bootstrap_verified,
            }
        )
        checks = {
            "profile_counts_exact": (
                int(indexed["zettels"]) == profile.zettel_count
                and int(indexed["objects"]) == profile.object_count
                and fixture.manifest_size_bytes == profile.manifest_target_bytes
            ),
            "cold_plan_p95_within_limit": max(
                float(plan_timing["cold_ready"]["p95"]),
                float(plan_timing["cold_already_present"]["p95"]),
            )
            <= COLD_P95_LIMIT_SECONDS,
            "warm_ready_p95_within_limit": (
                float(plan_timing["warm_ready"]["p95"])
                <= WARM_P95_LIMIT_SECONDS
            ),
            "warm_already_present_p95_within_limit": (
                float(plan_timing["warm_already_present"]["p95"])
                <= WARM_P95_LIMIT_SECONDS
            ),
            "first_serialized_write_within_limit": (
                float(status_timing["first_serialized_write_seconds_max"])
                <= FIRST_STATUS_LIMIT_SECONDS
            ),
            "first_serialized_flush_within_limit": (
                float(status_timing["first_serialized_flush_seconds_max"])
                <= FIRST_STATUS_LIMIT_SECONDS
            ),
            "serialized_heartbeat_gap_within_limit": (
                float(status_timing["max_serialized_flush_gap_seconds"])
                <= HEARTBEAT_GAP_LIMIT_SECONDS
                and HEARTBEAT_INTERVAL_SECONDS <= HEARTBEAT_GAP_LIMIT_SECONDS
            ),
            "serialized_progress_captured": (
                int(status_timing["serialized_stream_count"])
                == expected_plan_calls
                and int(status_timing["serialized_line_count"])
                >= expected_plan_calls * 2
                and int(status_timing["serialized_utf8_bytes"]) > 0
                and int(status_timing["serialized_write_calls"]) > 0
                and int(status_timing["serialized_flush_calls"])
                >= expected_plan_calls * 2
            ),
            "legacy_full_zettel_resolver_unused": (
                instrumentation.legacy_full_zettel_resolver_calls == 0
            ),
            "full_manifest_json_parser_unused": (
                instrumentation.full_manifest_parser_calls == 0
            ),
            "target_manifest_rows_only": (
                instrumentation.normal_plan_calls == expected_plan_calls
                and instrumentation.authority_lookup_calls
                == expected_plan_calls
                and instrumentation.target_manifest_rows_returned
                == expected_plan_calls
                and instrumentation.target_manifest_json_parses
                == expected_plan_calls * 2
                and instrumentation.non_target_lookup_json_parses == 0
            ),
            "fixed_states_exact": (
                plan_timing["cold_ready"]["state"] == "ready"
                and plan_timing["warm_ready"]["state"] == "ready"
                and plan_timing["cold_already_present"]["state"]
                == "already_present"
                and plan_timing["warm_already_present"]["state"]
                == "already_present"
            ),
            "wheel_bound_to_source_tree": (
                provenance["wheel_matches_source_tree"] is True
                and provenance["wheel_distribution_exact"] is True
                and provenance["wheel_version_exact"] is True
                and provenance["source_tree_sha256"]
                == provenance["wheel_package_tree_sha256"]
            ),
            "full_profile_source_bound_to_commit": (
                _profile_source_bound_to_commit(profile, provenance)
            ),
            "provenance_stable_during_benchmark": (
                final_source_provenance == source_provenance
            ),
            "loaded_runtime_bound_to_captured_wheel": (
                loaded_runtime_bound_to_captured_wheel
            ),
            "captured_driver_bootstrap_verified": bootstrap_verified,
        }
        report: dict[str, Any] = {
            "ok": False,
            "schema": BENCHMARK_SCHEMA,
            "profile": profile.name,
            "reason_codes": [],
            "counts": {
                "zettels": profile.zettel_count,
                "objets": profile.object_count,
                "manifest_size_bytes": fixture.manifest_size_bytes,
                "manifest_size_mib": round(
                    fixture.manifest_size_bytes / MIB,
                    6,
                ),
                "ready_targets": 1,
                "already_present_targets": 1,
                "cold_samples_per_state": profile.cold_iterations,
                "warm_samples_per_state": profile.warm_iterations,
            },
            "setup_durations_seconds": {
                "fixture_generation": round(fixture_seconds, 6),
                "index_rebuild": round(index_seconds, 6),
                "initial_projection_build": round(projection_seconds, 6),
            },
            "plan_durations_seconds": plan_timing,
            "status_delivery": status_timing,
            "thresholds_seconds": {
                "cold_plan_p95": COLD_P95_LIMIT_SECONDS,
                "warm_plan_p95": WARM_P95_LIMIT_SECONDS,
                "first_serialized_write": FIRST_STATUS_LIMIT_SECONDS,
                "first_serialized_flush": FIRST_STATUS_LIMIT_SECONDS,
                "max_serialized_flush_gap": HEARTBEAT_GAP_LIMIT_SECONDS,
            },
            "authority": {
                "index_generation": str(projection.get("generation") or ""),
                "manifest_sha256": str(
                    projection.get("manifest_sha256") or ""
                ),
                "ready_state": "ready",
                "already_present_state": "already_present",
            },
            "instrumentation": {
                "normal_plan_calls": instrumentation.normal_plan_calls,
                "authority_lookup_calls": instrumentation.authority_lookup_calls,
                "target_manifest_rows_returned": (
                    instrumentation.target_manifest_rows_returned
                ),
                "target_manifest_json_parses": (
                    instrumentation.target_manifest_json_parses
                ),
                "non_target_lookup_json_parses": (
                    instrumentation.non_target_lookup_json_parses
                ),
                "legacy_full_zettel_resolver_calls": (
                    instrumentation.legacy_full_zettel_resolver_calls
                ),
                "full_manifest_json_parser_calls": (
                    instrumentation.full_manifest_parser_calls
                ),
            },
            "environment": _environment_specification(),
            "provenance": provenance,
            "checks": checks,
        }

        forbidden_values = (
            PRIVATE_SENTINEL,
            str(root),
            root.as_posix(),
            fixture.ready_zettel_id,
            fixture.existing_zettel_id,
            fixture.ready_object_id,
            fixture.existing_object_id,
        )
        zettel_ids = tuple(
            _zettel_id(index) for index in range(profile.zettel_count)
        )
        object_ids = tuple(
            _object_id(index) for index in range(profile.object_count)
        )
        progress_safety = _serialized_output_safety(
            serialized_progress,
            forbidden_values=forbidden_values,
            zettel_ids=zettel_ids,
            object_ids=object_ids,
        )
        report["serialized_progress_safety"] = progress_safety
        checks["serialized_progress_public_safe"] = all(
            value == 0 for value in progress_safety.values()
        )
        provenance["release_evidence_eligible"] = (
            profile.name == FULL_PROFILE.name
            and checks["wheel_bound_to_source_tree"]
            and checks["full_profile_source_bound_to_commit"]
            and checks["provenance_stable_during_benchmark"]
            and checks["loaded_runtime_bound_to_captured_wheel"]
            and checks["captured_driver_bootstrap_verified"]
        )
        rendered = json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        safety = _serialized_output_safety(
            rendered + "\n" + serialized_progress,
            forbidden_values=forbidden_values,
            zettel_ids=zettel_ids,
            object_ids=object_ids,
        )
        public_output_safe = all(value == 0 for value in safety.values())
        report["output_safety"] = safety
        report["private_values_echoed"] = (
            safety["private_sentinel_occurrences"] > 0
        )
        report["absolute_paths_echoed"] = (
            safety["absolute_path_occurrences"] > 0
        )
        report["zettel_ids_echoed"] = safety["zettel_id_occurrences"] > 0
        report["object_ids_echoed"] = safety["object_id_occurrences"] > 0
        checks["public_output_safe"] = public_output_safe
        report["ok"] = all(checks.values())
        if not report["ok"]:
            report["reason_codes"] = ["benchmark_contract_failed"]
        return report


def _capture_supervisor_authority(
    wheel_path: Path,
) -> tuple[bytes, str, str]:
    script_raw = _stable_regular_file_bytes(
        BENCHMARK_PATH,
        reason_code="benchmark_bootstrap_source_script_unstable",
    )
    try:
        compile(script_raw, "benchmark_driver", "exec")
    except (SyntaxError, UnicodeError, ValueError) as exc:
        raise BenchmarkContractError(
            "benchmark_bootstrap_source_script_invalid"
        ) from exc
    script_sha256 = _sha256_label(script_raw)
    provenance = _provenance_document(wheel_path)
    if provenance.get("benchmark_script_sha256") != script_sha256:
        raise BenchmarkContractError("benchmark_bootstrap_provenance_mismatch")
    if (
        _stable_regular_file_bytes(
            BENCHMARK_PATH,
            reason_code="benchmark_bootstrap_source_script_unstable",
        )
        != script_raw
    ):
        raise BenchmarkContractError("benchmark_bootstrap_source_script_unstable")
    return script_raw, script_sha256, _provenance_sha256(provenance)


def _materialize_captured_driver(script_raw: bytes, target: Path) -> None:
    if (
        target.exists()
        or not target.parent.is_dir()
        or _path_is_link_like(target.parent)
    ):
        raise BenchmarkContractError("benchmark_bootstrap_materialization_unsafe")
    try:
        with target.open("xb") as handle:
            handle.write(script_raw)
            handle.flush()
        target.chmod(0o600)
    except OSError as exc:
        raise BenchmarkContractError(
            "benchmark_bootstrap_materialization_failed"
        ) from exc
    if (
        _stable_regular_file_bytes(
            target,
            reason_code="benchmark_bootstrap_materialization_unstable",
        )
        != script_raw
    ):
        raise BenchmarkContractError("benchmark_bootstrap_materialization_mismatch")


def _configure_worker_authority(args: argparse.Namespace) -> BootstrapAuthority:
    global BENCHMARK_PATH, KIT_ROOT, SOURCE_ROOT, PACKAGE_ROOT

    expected_script_sha256 = str(args._expected_script_sha256 or "")
    expected_provenance_sha256 = str(
        args._expected_provenance_sha256 or ""
    )
    if (
        not args._source_script
        or re.fullmatch(r"sha256:[0-9a-f]{64}", expected_script_sha256)
        is None
        or re.fullmatch(r"sha256:[0-9a-f]{64}", expected_provenance_sha256)
        is None
    ):
        raise BenchmarkContractError("benchmark_bootstrap_worker_args_invalid")
    source_script = Path(str(args._source_script)).absolute()
    if (
        source_script.name != "benchmark_v0412_link_index.py"
        or source_script.parent.name != "tools"
        or len(source_script.parents) < 2
    ):
        raise BenchmarkContractError("benchmark_bootstrap_source_scope_invalid")
    source_kit_root = source_script.parents[1]
    BENCHMARK_PATH = source_script
    KIT_ROOT = source_kit_root
    SOURCE_ROOT = source_kit_root / "src"
    PACKAGE_ROOT = SOURCE_ROOT / "wom_kit"
    authority = BootstrapAuthority(
        source_script_path=source_script,
        executing_script_path=EXECUTING_BENCHMARK_PATH,
        expected_script_sha256=expected_script_sha256,
        expected_provenance_sha256=expected_provenance_sha256,
    )
    _verify_bootstrap_authority(authority)
    return authority


def _render_report(report: Mapping[str, Any], output_format: str) -> bytes:
    if output_format == "json":
        rendered = json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n"
    else:
        lines = [
            "WOM v0.4.12 link-index synthetic benchmark",
            f"profile: {report['profile']}",
            f"ok: {str(bool(report['ok'])).lower()}",
            (
                "counts: "
                f"zettels={report['counts']['zettels']} "
                f"objets={report['counts']['objets']}"
            ),
        ]
        if report.get("plan_durations_seconds"):
            timing = report["plan_durations_seconds"]
            lines.append(
                "p95_seconds: "
                f"cold_ready={timing['cold_ready']['p95']} "
                f"cold_already_present={timing['cold_already_present']['p95']} "
                f"warm_ready={timing['warm_ready']['p95']} "
                "warm_already_present="
                f"{timing['warm_already_present']['p95']}"
            )
        if report.get("reason_codes"):
            lines.append("reason: " + str(report["reason_codes"][0]))
        rendered = "\n".join(lines) + "\n"
    return rendered.encode("utf-8", "strict")


def _safe_failed_process(args: argparse.Namespace):
    report = _safe_failure(PROFILES[args.profile], "benchmark_internal_error")
    return subprocess.CompletedProcess(
        args=(),
        returncode=1,
        stdout=_render_report(report, args.format),
        stderr=b"",
    )


def _launch_captured_worker(args: argparse.Namespace):
    wheel_path = Path(args.wheel)
    script_raw, script_sha256, provenance_sha256 = (
        _capture_supervisor_authority(wheel_path)
    )
    with tempfile.TemporaryDirectory(
        prefix="wom-v0412-benchmark-driver-"
    ) as temporary:
        temporary_root = Path(temporary)
        captured_script = temporary_root / "benchmark_driver.py"
        _materialize_captured_driver(script_raw, captured_script)
        command = [
            sys.executable,
            "-I",
            str(captured_script),
            "--_worker",
            "--_expected-script-sha256",
            script_sha256,
            "--_expected-provenance-sha256",
            provenance_sha256,
            "--_source-script",
            str(BENCHMARK_PATH),
            "--profile",
            args.profile,
            "--format",
            args.format,
            "--wheel",
            args.wheel,
        ]
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            raise BenchmarkContractError("benchmark_worker_launch_failed") from exc
        private_tokens = {
            str(temporary_root),
            temporary_root.as_posix(),
            str(captured_script),
            captured_script.as_posix(),
            str(BENCHMARK_PATH),
            BENCHMARK_PATH.as_posix(),
            str(wheel_path),
            wheel_path.as_posix(),
        }
        serialized = bytes(completed.stdout) + b"\n" + bytes(completed.stderr)
        lowered = serialized.lower()
        if any(
            token
            and token.encode("utf-8", "strict").lower() in lowered
            for token in private_tokens
        ):
            return _safe_failed_process(args)
        return completed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the public-safe synthetic v0.4.12 single-link authority-index "
            "benchmark."
        )
    )
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILES),
        default="reduced",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
    )
    parser.add_argument(
        "--wheel",
        required=True,
        help=(
            "Exact v0.4.12 wheel whose bytes and package tree are bound to "
            "this benchmark result."
        ),
    )
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--_expected-script-sha256",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--_expected-provenance-sha256",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--_source-script", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    profile = PROFILES[args.profile]
    if args._worker:
        try:
            bootstrap_authority = _configure_worker_authority(args)
            report = run_benchmark(
                profile,
                wheel_path=Path(args.wheel),
                bootstrap_authority=bootstrap_authority,
            )
        except Exception:
            # Neither a worker failure nor its hidden paths may escape into
            # public benchmark evidence.
            report = _safe_failure(profile, "benchmark_internal_error")
        sys.stdout.buffer.write(_render_report(report, args.format))
        sys.stdout.buffer.flush()
        return 0 if report.get("ok") is True else 1

    try:
        completed = _launch_captured_worker(args)
    except Exception:
        completed = _safe_failed_process(args)
    # Normal worker stdout/stderr and its exact exit status are preserved. A
    # path-bearing worker failure is replaced inside _launch_captured_worker
    # by one path-free public failure document.
    sys.stdout.buffer.write(bytes(completed.stdout))
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(bytes(completed.stderr))
    sys.stderr.buffer.flush()
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
