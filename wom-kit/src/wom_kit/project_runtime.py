"""Project-scoped WOM runtime installation and inspection.

The project updater owns activation and rollback.  This module deliberately
does not mutate the process-wide PATH or a user-wide Python installation.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import re
import secrets
import shutil
import stat as stat_module
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

from .schema_validator import validate_schema


PROJECT_RUNTIME_POLICY_SCHEMA = "wom-kit/project-runtime-policy/v0.1"
PROJECT_RUNTIME_RECEIPT_SCHEMA = "wom-kit/project-runtime-receipt/v0.1"
PROJECT_RUNTIME_RELATIVE_ROOT = Path(".zettel-kasten") / "runtimes"
PROJECT_RUNTIME_LAUNCHER_RELATIVE = Path(".zettel-kasten") / "bin" / "archive.cmd"
PROJECT_RUNTIME_RECEIPT_NAME = "runtime-receipt.json"
PROJECT_RUNTIME_INSTALLING_NAME = ".runtime-installing.json"
PROJECT_RUNTIME_ARTIFACTS_NAME = "runtime-artifacts"
PROJECT_RUNTIME_RETAINED_LOCK_NAME = "project-runtime-supply-lock.json"
PROJECT_RUNTIME_SUPPLY_LOCK_SCHEMA = "wom-kit/project-runtime-supply-lock/v0.1"
PROJECT_RUNTIME_PREPARED_BUNDLE_SCHEMA = (
    "wom-kit/project-runtime-prepared-bundle/v0.1"
)
PROJECT_RUNTIME_PREPARED_MARKER_NAME = ".prepared-runtime-bundle.json"
PROJECT_RUNTIME_PREPARED_PREFIX = "wom-project-runtime-bundle-"
PROJECT_RUNTIME_CANDIDATE_SCHEMA = "wom-kit/project-runtime-candidate/v0.1"
PROJECT_RUNTIME_CANDIDATE_NAME = "runtime-candidate"
PROJECT_RUNTIME_CANDIDATE_SEAL_NAME = "runtime-candidate-seal.json"
PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT = (
    Path(".zettel-kasten") / "private" / "version-updates"
)
PROJECT_RUNTIME_TRANSACTION_REF_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?$"
)
STABLE_VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40,64}$")
WHEEL_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\.whl$")
DIST_NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,126}[A-Za-z0-9])?$")
PUBLIC_WHEEL_PATH_RE = re.compile(
    r"^/mow-coding/zettel-kasten/releases/download/"
    r"v(?P<version>(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))/"
    r"wom_kit-(?P=version)-py3-none-any\.whl$"
)
PROJECT_RUNTIME_TRANSIENT_UNLINK_ATTEMPTS = 8
PROJECT_RUNTIME_TRANSIENT_UNLINK_BACKOFF_SECONDS = 0.025
PROJECT_RUNTIME_TRANSIENT_WINDOWS_ERRORS = frozenset({5, 32, 33})


class ProjectRuntimeError(RuntimeError):
    """A content-free project runtime failure."""


class PreparedRuntimeBundleCleanupError(ProjectRuntimeError):
    """A bundle preparation failure whose private temp cleanup is uncertain."""

    def __init__(self, cleanup_handle: "PreparedRuntimeCleanupHandle") -> None:
        super().__init__("project_runtime_prepared_bundle_cleanup_unverified")
        self.cleanup_handle = cleanup_handle


class RuntimeReferenceCleanupError(ProjectRuntimeError):
    """A fresh shadow runtime could not be proven absent."""

    def __init__(self, reference_root: Path) -> None:
        super().__init__("project_runtime_reference_cleanup_unverified")
        self.reference_root = reference_root


class PreparedRuntimeCandidateIncompleteError(ProjectRuntimeError):
    """Preparation stopped after private state may have been created.

    Deliberately contains no path.  A durable update transaction owns any
    partial tree and must classify it; this module never guesses that a
    partially-built runtime is safe to delete.
    """

    def __init__(self) -> None:
        super().__init__("project_runtime_candidate_preparation_incomplete")


@dataclass(frozen=True)
class BootstrapWheel:
    version: str
    tag: str
    url: str
    sha256: str
    file_name: str

    def public_summary(self) -> dict[str, Any]:
        return {
            "available": True,
            "reason_code": "exact_public_release_wheel_verified",
            "source_kind": "public_github_release",
            "release_tag": self.tag,
            "wheel_file_name": self.file_name,
            "wheel_sha256": f"sha256:{self.sha256}",
            "download_url_echoed": False,
        }


@dataclass(frozen=True)
class RuntimeArtifactSpec:
    role: str
    distribution: str
    version: str
    file_name: str
    url: str
    size_bytes: int
    sha256: str

    def public_summary(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "distribution": self.distribution,
            "version": self.version,
            "file_name": self.file_name,
            "size_bytes": self.size_bytes,
            "sha256": f"sha256:{self.sha256}",
            "source_kind": "public_pypi_file",
            "download_url_echoed": False,
        }


@dataclass(frozen=True)
class RuntimeSupplyLock:
    schema: str
    target_tag: str
    implementation: str
    python_version: str
    python_tag: str
    abi_tag: str
    platform_tag: str
    artifacts: tuple[RuntimeArtifactSpec, ...]
    raw_bytes: bytes
    sha256: str

    def public_summary(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "target_tag": self.target_tag,
            "lock_sha256": f"sha256:{self.sha256}",
            "interpreter": {
                "implementation": self.implementation,
                "python_version": self.python_version,
                "python_tag": self.python_tag,
                "abi_tag": self.abi_tag,
                "platform_tag": self.platform_tag,
            },
            "artifacts": [item.public_summary() for item in self.artifacts],
            "index_resolution": False,
            "all_artifacts_hash_and_size_bound": True,
            "download_urls_echoed": False,
        }


@dataclass(frozen=True)
class RuntimeRootSnapshot:
    valid: bool
    root_existed: bool
    root_identity: tuple[int, int] | None
    entries: tuple[tuple[str, str, int, int], ...]


@dataclass
class RuntimeMutationTracker:
    before: RuntimeRootSnapshot | None = None
    started: bool = False
    completed: bool = False
    cleanup_verified: bool | None = None


@dataclass(frozen=True)
class PreparedRuntimeCleanupHandle:
    root: Path
    root_identity: tuple[int, int] | None
    marker_bytes: bytes | None


@dataclass(frozen=True)
class PreparedRuntimeBundle:
    target_tag: str
    target_version: str
    target_commit: str
    root: Path
    cleanup_handle: PreparedRuntimeCleanupHandle
    marker_bytes: bytes
    file_snapshot: tuple[tuple[str, int, int, int, int, str], ...]
    bundle_sha256: str
    wheel_sha256: str
    supply_lock_sha256: str
    artifact_inventory: tuple[Mapping[str, Any], ...]

    def public_summary(self) -> dict[str, Any]:
        return {
            "schema": PROJECT_RUNTIME_PREPARED_BUNDLE_SCHEMA,
            "status": "prepared",
            "target_tag": self.target_tag,
            "target_version": self.target_version,
            "target_commit": self.target_commit,
            "bundle_sha256": f"sha256:{self.bundle_sha256}",
            "wheel_sha256": f"sha256:{self.wheel_sha256}",
            "supply_lock_sha256": f"sha256:{self.supply_lock_sha256}",
            "artifact_inventory": [dict(item) for item in self.artifact_inventory],
            "network_complete": True,
            "post_approval_network_allowed": False,
            "cleanup_required": True,
            "cleanup_contract": "exact_owned_tree_and_absence_verified",
            "download_urls_echoed": False,
            "private_values_echoed": False,
            "absolute_paths_echoed": False,
        }


@dataclass(frozen=True)
class RuntimeCandidateInventoryEntry:
    """One exact recursive entry in a sealed runtime candidate."""

    relative_path: str
    entry_type: str
    device: int
    inode: int
    nlink: int
    size_bytes: int
    mtime_ns: int
    sha256: str | None

    def binding_summary(self) -> dict[str, Any]:
        return {
            "path": self.relative_path,
            "type": self.entry_type,
            "nlink": self.nlink,
            "size_bytes": self.size_bytes,
            "sha256": f"sha256:{self.sha256}" if self.sha256 is not None else None,
        }


@dataclass(frozen=True)
class PreparedRuntimeCandidate:
    """A complete, process-verified runtime ready for static-only promotion."""

    target_tag: str
    target_version: str
    target_commit: str
    transaction_ref: str
    logical_candidate_path: str
    logical_seal_path: str
    project_root: Path = field(repr=False)
    transaction_root: Path = field(repr=False)
    candidate_root: Path = field(repr=False)
    seal_path: Path = field(repr=False)
    project_root_identity: tuple[int, int]
    transaction_root_identity: tuple[int, int]
    candidate_root_identity: tuple[int, int]
    runtime_parent_identity: tuple[int, int]
    runtime_parent_existed_before: bool
    runtime_parent_created_identity: tuple[int, int] | None
    same_volume_identity: int
    inventory: tuple[RuntimeCandidateInventoryEntry, ...] = field(repr=False)
    inventory_sha256: str
    candidate_sha256: str
    inventory_count: int
    inventory_bytes: int
    seal_bytes: bytes = field(repr=False)
    seal_sha256: str
    receipt_bytes: bytes = field(repr=False)
    receipt_sha256: str
    wheel_file_name: str
    wheel_sha256: str
    supply_lock_sha256: str
    supply_lock_bytes: bytes = field(repr=False)
    artifact_inventory: tuple[Mapping[str, Any], ...] = field(repr=False)
    installed_payload_sha256: str
    normalized_payload_inventory: tuple[tuple[str, int, str], ...] = field(
        repr=False
    )
    python_version: str
    installed_distributions: tuple[Mapping[str, Any], ...] = field(repr=False)
    verification: Mapping[str, bool] = field(repr=False)
    existing_runtime_reusable: bool

    def public_summary(self) -> dict[str, Any]:
        return {
            "schema": PROJECT_RUNTIME_CANDIDATE_SCHEMA,
            "status": "sealed",
            "target_tag": self.target_tag,
            "target_version": self.target_version,
            "target_commit": self.target_commit,
            "transaction_ref": self.transaction_ref,
            "candidate_locator": self.logical_candidate_path,
            "seal_locator": self.logical_seal_path,
            "inventory_sha256": f"sha256:{self.inventory_sha256}",
            "candidate_sha256": f"sha256:{self.candidate_sha256}",
            "inventory_count": self.inventory_count,
            "inventory_bytes": self.inventory_bytes,
            "receipt_sha256": f"sha256:{self.receipt_sha256}",
            "wheel_file_name": self.wheel_file_name,
            "wheel_sha256": f"sha256:{self.wheel_sha256}",
            "supply_lock_sha256": f"sha256:{self.supply_lock_sha256}",
            "artifact_inventory": [dict(item) for item in self.artifact_inventory],
            "installed_payload_sha256": f"sha256:{self.installed_payload_sha256}",
            "python_version": self.python_version,
            "verification": dict(self.verification),
            "existing_runtime_reusable": self.existing_runtime_reusable,
            "complete_runtime_image": True,
            "network_complete": True,
            "toolchain_complete": True,
            "same_volume_verified": True,
            "runtime_parent_existed_before": self.runtime_parent_existed_before,
            "post_approval_child_process_allowed": False,
            "post_approval_network_allowed": False,
            "post_approval_copy_allowed": False,
            "marker_free_final_postimage": True,
            "reopenable_from_private_seal": True,
            "durability_barriers_complete": True,
            "cleanup_contract": "sealed_exact_tree_only",
            "download_urls_echoed": False,
            "private_values_echoed": False,
            "absolute_paths_echoed": False,
        }


@dataclass(frozen=True)
class RuntimeMaterialization:
    target_tag: str
    target_version: str
    target_commit: str
    final_path: Path
    logical_path: str
    receipt_bytes: bytes
    receipt_sha256: str
    wheel_sha256: str
    supply_lock_sha256: str
    artifact_inventory: tuple[Mapping[str, Any], ...]
    installed_payload_sha256: str
    python_version: str
    created: bool
    verification: Mapping[str, bool]

    def public_summary(self) -> dict[str, Any]:
        return {
            "status": "verified",
            "target_tag": self.target_tag,
            "target_version": self.target_version,
            "target_commit": self.target_commit,
            "path": self.logical_path,
            "created": self.created,
            "receipt_sha256": f"sha256:{self.receipt_sha256}",
            "wheel_sha256": f"sha256:{self.wheel_sha256}",
            "supply_lock_sha256": f"sha256:{self.supply_lock_sha256}",
            "artifact_inventory": [dict(item) for item in self.artifact_inventory],
            "installed_payload_sha256": f"sha256:{self.installed_payload_sha256}",
            "python_version": self.python_version,
            "verification": dict(self.verification),
            "absolute_paths_echoed": False,
        }


def _version(value: str | None) -> str | None:
    text = str(value or "").strip().removeprefix("v")
    return text if STABLE_VERSION_RE.fullmatch(text) else None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_reparse_stat(stat_result: os.stat_result) -> bool:
    return bool(getattr(stat_result, "st_file_attributes", 0) & 0x400)


def _stat_identity(stat_result: os.stat_result) -> tuple[int, int, int, int, int, int]:
    """Return the fields that must stay stable across a bound read.

    Windows does not expose one uniform generation counter through Python.  A
    device/inode identity plus type, size, mtime and reparse attributes is the
    strongest portable observation available here.  The open descriptor is
    still the authority for the bytes; the path observations only prove that
    the name and its ancestors did not visibly move around that read.
    """

    return (
        int(stat_result.st_dev),
        int(stat_result.st_ino),
        int(stat_module.S_IFMT(stat_result.st_mode)),
        int(stat_result.st_size),
        int(stat_result.st_mtime_ns),
        int(getattr(stat_result, "st_file_attributes", 0)),
    )


def _real_component_snapshot(
    root: Path,
    target: Path,
    *,
    target_must_exist: bool,
) -> tuple[tuple[str, tuple[int, int, int, int, int, int]], ...] | None:
    """Observe one non-reparse path chain without resolving through links."""

    try:
        root_absolute = Path(os.path.abspath(str(root)))
        target_absolute = Path(os.path.abspath(str(target)))
        relative = target_absolute.relative_to(root_absolute)
    except (OSError, RuntimeError, ValueError):
        return None
    paths = [root_absolute]
    current = root_absolute
    for part in relative.parts:
        current = current / part
        paths.append(current)
    observations: list[tuple[str, tuple[int, int, int, int, int, int]]] = []
    for index, component in enumerate(paths):
        try:
            component_stat = component.lstat()
        except FileNotFoundError:
            if not target_must_exist and index > 0:
                # Creation paths are allowed to have a missing suffix, but no
                # later component can exist once one prefix is absent.
                break
            return None
        except OSError:
            return None
        if _is_reparse_stat(component_stat) or stat_module.S_ISLNK(
            component_stat.st_mode
        ):
            return None
        is_target = index == len(paths) - 1
        if not is_target and not stat_module.S_ISDIR(component_stat.st_mode):
            return None
        if is_target and target_must_exist and not (
            stat_module.S_ISREG(component_stat.st_mode)
            or stat_module.S_ISDIR(component_stat.st_mode)
        ):
            return None
        observations.append((str(component), _stat_identity(component_stat)))
    if target_must_exist and len(observations) != len(paths):
        return None
    return tuple(observations)


def _stable_regular_file_observation(
    path: Path,
    *,
    limit: int,
    ancestor_root: Path | None = None,
    collect_bytes: bool,
    tree_shape_bound: bool = False,
) -> tuple[bytes | None, str, int] | None:
    """Read/hash a bounded regular file through one no-follow descriptor.

    The descriptor prevents a post-open pathname swap from changing the byte
    stream.  Matching before/after descriptor, pathname, and ancestor
    snapshots rejects observable file or directory generation changes.
    """

    root = Path(ancestor_root) if ancestor_root is not None else path.parent
    try:
        path_before = path.lstat()
    except OSError:
        return None
    if (
        not stat_module.S_ISREG(path_before.st_mode)
        or stat_module.S_ISLNK(path_before.st_mode)
        or _is_reparse_stat(path_before)
    ):
        return None
    before_components = None
    if not tree_shape_bound:
        before_components = _real_component_snapshot(
            root,
            path,
            target_must_exist=True,
        )
        if before_components is None:
            return None
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened_before = os.fstat(descriptor)
        if (
            not stat_module.S_ISREG(opened_before.st_mode)
            or _is_reparse_stat(opened_before)
            or opened_before.st_size < 0
            or opened_before.st_size > limit
        ):
            return None
        digest = hashlib.sha256()
        chunks: list[bytes] | None = [] if collect_bytes else None
        total = 0
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = None
            while True:
                chunk = handle.read(min(1024 * 1024, limit + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    return None
                digest.update(chunk)
                if chunks is not None:
                    chunks.append(chunk)
            opened_after = os.fstat(handle.fileno())
        try:
            path_after = path.lstat()
        except OSError:
            return None
        after_components = None
        if not tree_shape_bound:
            after_components = _real_component_snapshot(
                root,
                path,
                target_must_exist=True,
            )
        if (
            not stat_module.S_ISREG(opened_after.st_mode)
            or not stat_module.S_ISREG(path_after.st_mode)
            or _is_reparse_stat(opened_after)
            or _is_reparse_stat(path_after)
            or _stat_identity(path_before) != _stat_identity(opened_before)
            or _stat_identity(opened_before) != _stat_identity(opened_after)
            or _stat_identity(opened_after) != _stat_identity(path_after)
            or (
                not tree_shape_bound
                and before_components != after_components
            )
            or total != opened_after.st_size
        ):
            return None
        return (
            b"".join(chunks) if chunks is not None else None,
            digest.hexdigest(),
            total,
        )
    except OSError:
        return None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _read_limited(
    path: Path,
    *,
    limit: int,
    ancestor_root: Path | None = None,
) -> bytes | None:
    try:
        observed = _stable_regular_file_observation(
            path,
            limit=limit,
            ancestor_root=ancestor_root,
            collect_bytes=True,
        )
    except (OSError, RuntimeError, ValueError):
        return None
    return observed[0] if observed is not None else None


def _existing_components_are_real(root: Path, target: Path) -> bool:
    return _real_component_snapshot(
        root,
        target,
        target_must_exist=False,
    ) is not None


def project_runtime_policy_document(raw: bytes | None) -> dict[str, Any] | None:
    if raw is None or len(raw) > 64 * 1024:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    expected = {
        "schema": PROJECT_RUNTIME_POLICY_SCHEMA,
        "mode": "project_local_venv",
        "runtime_root": ".zettel-kasten/runtimes/vX.Y.Z",
        "active_version_pin": ".zettel-kasten/installed-version.txt",
        "launcher": ".zettel-kasten/bin/archive.cmd",
        "supply_lock": "wom-kit/project-runtime-supply-lock-v0.4.15.json",
        "supply_lock_sha256": "sha256:8cc4597742bab8bb4f7c1f4e4c28d90d0b8cddd1293247e680c615531d31953d",
        "global_path_mutation": False,
    }
    if value != expected:
        return None
    return value


def _json_without_duplicate_keys(raw: bytes) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    return json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs)


def project_runtime_supply_lock(
    raw: bytes | None,
    *,
    expected_target: str | None = None,
) -> RuntimeSupplyLock | None:
    """Parse one exact, content-bound public runtime artifact inventory."""

    if raw is None or not raw or len(raw) > 256 * 1024:
        return None
    try:
        value = _json_without_duplicate_keys(raw)
    except (UnicodeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(value, dict) or set(value) != {
        "schema",
        "target_tag",
        "interpreter",
        "artifacts",
    }:
        return None
    target_version = _version(value.get("target_tag"))
    expected_version = _version(expected_target) if expected_target is not None else None
    if (
        value.get("schema") != PROJECT_RUNTIME_SUPPLY_LOCK_SCHEMA
        or target_version is None
        or (expected_target is not None and target_version != expected_version)
    ):
        return None
    interpreter = value.get("interpreter")
    if not isinstance(interpreter, dict) or set(interpreter) != {
        "implementation",
        "python_version",
        "python_tag",
        "abi_tag",
        "platform_tag",
    }:
        return None
    implementation = interpreter.get("implementation")
    python_version = interpreter.get("python_version")
    python_tag = interpreter.get("python_tag")
    abi_tag = interpreter.get("abi_tag")
    platform_tag = interpreter.get("platform_tag")
    if (
        implementation != "cpython"
        or not isinstance(python_version, str)
        or re.fullmatch(r"[1-9][0-9]*\.[0-9]+", python_version) is None
        or not isinstance(python_tag, str)
        or re.fullmatch(r"cp[0-9]{2,3}", python_tag) is None
        or not isinstance(abi_tag, str)
        or re.fullmatch(r"cp[0-9]{2,3}", abi_tag) is None
        or python_tag != abi_tag
        or platform_tag != "win_amd64"
        or python_tag != "cp" + python_version.replace(".", "")
    ):
        return None
    artifacts_raw = value.get("artifacts")
    if not isinstance(artifacts_raw, list) or not (1 <= len(artifacts_raw) <= 32):
        return None
    artifacts: list[RuntimeArtifactSpec] = []
    seen_distributions: set[str] = set()
    seen_files: set[str] = set()
    previous_sort_key: tuple[str, str, str] | None = None
    for item in artifacts_raw:
        if not isinstance(item, dict) or set(item) != {
            "role",
            "distribution",
            "version",
            "file_name",
            "url",
            "size_bytes",
            "sha256",
        }:
            return None
        role = item.get("role")
        distribution = item.get("distribution")
        version = item.get("version")
        file_name = item.get("file_name")
        url = item.get("url")
        size_bytes = item.get("size_bytes")
        sha256_label = item.get("sha256")
        if (
            role != "dependency"
            or not isinstance(distribution, str)
            or DIST_NAME_RE.fullmatch(distribution) is None
            or not isinstance(version, str)
            or STABLE_VERSION_RE.fullmatch(version) is None
            or not isinstance(file_name, str)
            or WHEEL_FILE_RE.fullmatch(file_name) is None
            or not file_name.casefold().endswith(
                f"-{python_tag}-{abi_tag}-{platform_tag}.whl".casefold()
            )
            or not isinstance(url, str)
            or type(size_bytes) is not int
            or not (1 <= size_bytes <= 128 * 1024 * 1024)
            or not isinstance(sha256_label, str)
            or not sha256_label.startswith("sha256:")
            or SHA256_RE.fullmatch(sha256_label.removeprefix("sha256:")) is None
        ):
            return None
        parsed = urllib.parse.urlparse(url)
        if (
            parsed.scheme != "https"
            or (parsed.hostname or "").casefold() != "files.pythonhosted.org"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.params
            or parsed.query
            or parsed.fragment
            or PurePosixPath(parsed.path).name != file_name
        ):
            return None
        distribution_key = re.sub(r"[-_.]+", "-", distribution).casefold()
        file_key = file_name.casefold()
        sort_key = (distribution_key, version, file_key)
        if (
            distribution_key in seen_distributions
            or file_key in seen_files
            or (previous_sort_key is not None and sort_key <= previous_sort_key)
        ):
            return None
        seen_distributions.add(distribution_key)
        seen_files.add(file_key)
        previous_sort_key = sort_key
        artifacts.append(
            RuntimeArtifactSpec(
                role=role,
                distribution=distribution,
                version=version,
                file_name=file_name,
                url=url,
                size_bytes=size_bytes,
                sha256=sha256_label.removeprefix("sha256:"),
            )
        )
    return RuntimeSupplyLock(
        schema=PROJECT_RUNTIME_SUPPLY_LOCK_SCHEMA,
        target_tag=f"v{target_version}",
        implementation=implementation,
        python_version=python_version,
        python_tag=python_tag,
        abi_tag=abi_tag,
        platform_tag=platform_tag,
        artifacts=tuple(artifacts),
        raw_bytes=raw,
        sha256=_sha256_bytes(raw),
    )


def bootstrap_wheel_for_target(target: str) -> tuple[BootstrapWheel | None, dict[str, Any]]:
    target_version = _version(target)
    unavailable = {
        "available": False,
        "reason_code": "exact_public_release_wheel_unavailable",
        "source_kind": "unverified",
        "release_tag": f"v{target_version}" if target_version else None,
        "wheel_file_name": None,
        "wheel_sha256": None,
        "download_url_echoed": False,
        "next_safe_actions": [],
    }
    if target_version is None:
        return None, unavailable
    try:
        distribution = importlib.metadata.distribution("wom-kit")
        if _version(distribution.version) != target_version:
            unavailable["reason_code"] = "running_distribution_version_differs_from_target"
            return None, unavailable
        direct_url_text = distribution.read_text("direct_url.json")
        direct_url = json.loads(direct_url_text or "null")
    except (importlib.metadata.PackageNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None, unavailable
    if not isinstance(direct_url, dict):
        return None, unavailable
    url = direct_url.get("url")
    archive_info = direct_url.get("archive_info")
    if not isinstance(url, str) or not isinstance(archive_info, dict):
        return None, unavailable
    parsed = urllib.parse.urlparse(url)
    path_match = PUBLIC_WHEEL_PATH_RE.fullmatch(parsed.path)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").casefold() != "github.com"
        or path_match is None
        or path_match.group("version") != target_version
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
    ):
        unavailable["reason_code"] = "running_distribution_not_from_exact_public_release_wheel"
        return None, unavailable
    hashes = archive_info.get("hashes")
    sha256 = hashes.get("sha256") if isinstance(hashes, dict) else None
    if not isinstance(sha256, str):
        legacy_hash = archive_info.get("hash")
        if isinstance(legacy_hash, str) and legacy_hash.startswith("sha256="):
            sha256 = legacy_hash.removeprefix("sha256=")
    sha256 = str(sha256 or "").lower()
    if SHA256_RE.fullmatch(sha256) is None:
        unavailable["reason_code"] = "running_distribution_wheel_hash_unavailable"
        unavailable["next_safe_actions"] = [
            (
                "Install the exact public target wheel in a dedicated external "
                "CPython 3.12 virtual environment with python.exe -m pip; "
                "the updater requires pip's recorded wheel SHA-256."
            ),
            (
                "Do not delete an update lock, bypass SHA-256 verification, "
                "or use an installer whose installed metadata omits the "
                "archive hash."
            ),
        ]
        return None, unavailable
    file_name = Path(parsed.path).name
    wheel = BootstrapWheel(
        version=target_version,
        tag=f"v{target_version}",
        url=url,
        sha256=sha256,
        file_name=file_name,
    )
    return wheel, wheel.public_summary()


def runtime_logical_path(target: str) -> str:
    version = _version(target)
    if version is None:
        raise ProjectRuntimeError("project_runtime_target_version_invalid")
    return f".zettel-kasten/runtimes/v{version}"


def runtime_path(project_root: Path, target: str) -> Path:
    return project_root / Path(runtime_logical_path(target))


def runtime_root_snapshot(project_root: Path) -> RuntimeRootSnapshot:
    root = project_root / PROJECT_RUNTIME_RELATIVE_ROOT
    if not _existing_components_are_real(project_root, root):
        return RuntimeRootSnapshot(False, root.exists(), None, ())
    if not root.exists():
        return RuntimeRootSnapshot(True, False, None, ())
    try:
        root_stat = root.lstat()
        if (
            not root.is_dir()
            or root.is_symlink()
            or bool(getattr(root_stat, "st_file_attributes", 0) & 0x400)
        ):
            return RuntimeRootSnapshot(False, True, None, ())
        entries: list[tuple[str, str, int, int]] = []
        seen_names: set[str] = set()
        with os.scandir(root) as iterator:
            for entry in iterator:
                name_key = entry.name.casefold()
                if name_key in seen_names:
                    return RuntimeRootSnapshot(False, True, None, ())
                seen_names.add(name_key)
                stat_result = entry.stat(follow_symlinks=False)
                attributes = getattr(stat_result, "st_file_attributes", 0)
                if entry.is_symlink() or bool(attributes & 0x400):
                    return RuntimeRootSnapshot(False, True, None, ())
                kind = (
                    "directory"
                    if entry.is_dir(follow_symlinks=False)
                    else "file"
                    if entry.is_file(follow_symlinks=False)
                    else "other"
                )
                if kind == "other":
                    return RuntimeRootSnapshot(False, True, None, ())
                entries.append(
                    (
                        entry.name,
                        kind,
                        int(stat_result.st_dev),
                        int(stat_result.st_ino),
                    )
                )
    except OSError:
        return RuntimeRootSnapshot(False, True, None, ())
    entries.sort(key=lambda item: (item[0].casefold(), item[0]))
    return RuntimeRootSnapshot(
        True,
        True,
        (int(root_stat.st_dev), int(root_stat.st_ino)),
        tuple(entries),
    )


def runtime_mutation_restored(
    project_root: Path,
    tracker: RuntimeMutationTracker,
) -> bool:
    before = tracker.before
    if before is None or not before.valid:
        return False
    current = runtime_root_snapshot(project_root)
    restored = bool(current.valid and current == before)
    tracker.cleanup_verified = restored
    return restored


def _remove_new_empty_runtime_root(
    project_root: Path,
    tracker: RuntimeMutationTracker,
) -> None:
    before = tracker.before
    if before is None or before.root_existed:
        return
    root = project_root / PROJECT_RUNTIME_RELATIVE_ROOT
    if not _existing_components_are_real(project_root, root):
        return
    try:
        root.rmdir()
    except OSError:
        return


def launcher_bytes(target: str) -> bytes:
    version = _version(target)
    if version is None:
        raise ProjectRuntimeError("project_runtime_target_version_invalid")
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        'set "PYTHONDONTWRITEBYTECODE=1"\r\n'
        'set "PYTHONNOUSERSITE=1"\r\n'
        'set "PYTHONSAFEPATH=1"\r\n'
        f'"%~dp0..\\runtimes\\v{version}\\Scripts\\python.exe" '
        '-I -B -X utf8 -m wom_kit.archive_cli %*\r\n'
    ).encode("utf-8")


def project_runtime_argv() -> list[str]:
    return [r".\.zettel-kasten\bin\archive.cmd"]


def _same_absolute_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(
        os.path.abspath(str(right))
    )


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        Path(os.path.abspath(str(path))).relative_to(
            Path(os.path.abspath(str(parent)))
        )
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def current_project_runtime_binding(
    project_root: Path,
    target: str,
    *,
    running_executable: str | Path | None = None,
    running_module_path: str | Path | None = None,
    running_archive_cli_module_path: str | Path | None = None,
    running_project_runtime_module_path: str | Path | None = None,
    running_package_origin_path: str | Path | None = None,
    running_prefix: str | Path | None = None,
    isolated_mode: bool | None = None,
    dont_write_bytecode: bool | None = None,
    runtime_inspection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify that this process matches the canonical project-launcher contract.

    A static runtime receipt proves what a prior installer recorded.  It does
    not prove which Python or WOM package the current process selected, and
    process state cannot prove which batch file causally started it.  This
    content-free result therefore verifies equivalent interpreter/module/flag
    binding while keeping those evidence boundaries separate.
    """

    version = _version(target)
    if version is None:
        return {
            "bound": False,
            "reason_code": "project_runtime_target_version_invalid",
            "absolute_paths_echoed": False,
        }
    root = Path(os.path.abspath(str(project_root)))
    final = runtime_path(root, version)
    expected_python = final / "Scripts" / "python.exe"
    inspection = (
        dict(runtime_inspection)
        if isinstance(runtime_inspection, Mapping)
        else inspect_runtime(root, version)
    )
    launcher = launcher_snapshot(root, version)
    executable = Path(
        os.path.abspath(str(running_executable or sys.executable))
    )
    module_path = Path(
        os.path.abspath(str(running_module_path or __file__))
    )
    archive_cli_loaded = sys.modules.get("wom_kit.archive_cli")
    package_loaded = sys.modules.get("wom_kit")
    archive_cli_module_path = Path(
        os.path.abspath(
            str(
                running_archive_cli_module_path
                or getattr(archive_cli_loaded, "__file__", "")
            )
        )
    )
    project_runtime_module_path = Path(
        os.path.abspath(str(running_project_runtime_module_path or __file__))
    )
    package_origin_path = Path(
        os.path.abspath(
            str(
                running_package_origin_path
                or getattr(package_loaded, "__file__", "")
            )
        )
    )
    prefix = Path(os.path.abspath(str(running_prefix or sys.prefix)))
    isolated = bool(sys.flags.isolated) if isolated_mode is None else bool(isolated_mode)
    no_bytecode = (
        bool(sys.dont_write_bytecode)
        if dont_write_bytecode is None
        else bool(dont_write_bytecode)
    )
    launcher_aligned = bool(
        not launcher.get("unsafe") and launcher.get("already_target")
    )
    static_receipt_aligned = bool(
        inspection.get("static_receipt_valid")
        and inspection.get("target_version") == version
        and inspection.get("path") == runtime_logical_path(version)
    )
    live_payload_aligned = bool(
        static_receipt_aligned and inspection.get("live_payload_aligned") is True
    )
    receipt_path = final / PROJECT_RUNTIME_RECEIPT_NAME
    live_receipt_bytes = _read_limited(
        receipt_path,
        limit=2 * 1024 * 1024,
        ancestor_root=root,
    )
    receipt_generation_aligned = bool(
        live_receipt_bytes is not None
        and inspection.get("receipt_sha256")
        == f"sha256:{_sha256_bytes(live_receipt_bytes)}"
    )
    if not receipt_generation_aligned:
        static_receipt_aligned = False
        live_payload_aligned = False
    try:
        module_relative = module_path.relative_to(final)
        module_parts = tuple(part.casefold() for part in module_relative.parts)
    except (OSError, RuntimeError, ValueError):
        module_relative = None
        module_parts = ()
    wom_module_layout = bool(
        len(module_parts) >= 4
        and module_parts[:3] == ("lib", "site-packages", "wom_kit")
        and module_parts[-1].endswith((".py", ".pyc", ".pyd"))
    )
    executable_aligned = bool(
        _same_absolute_path(executable, expected_python)
        and _real_component_snapshot(root, executable, target_must_exist=True)
        is not None
    )
    module_aligned = bool(
        _path_is_within(module_path, final)
        and wom_module_layout
        and _real_component_snapshot(root, module_path, target_must_exist=True)
        is not None
    )
    prefix_aligned = bool(
        _same_absolute_path(prefix, final)
        and _real_component_snapshot(root, prefix, target_must_exist=True) is not None
    )
    executable_receipt_bound = False
    module_receipt_bound = False
    core_modules_receipt_bound = False
    if live_payload_aligned and executable_aligned and module_aligned:
        expected_payload = str(
            inspection.get("installed_payload_sha256") or ""
        ).removeprefix("sha256:")
        try:
            observed_payload, inventory = _runtime_payload_observation(final)
            inventory_by_path = {
                logical: (size, digest) for logical, size, digest in inventory
            }
            live_payload_aligned = observed_payload == expected_payload

            def receipt_bound_file(candidate: Path) -> bool:
                try:
                    logical = Path(os.path.abspath(str(candidate))).relative_to(
                        Path(os.path.abspath(str(final)))
                    ).as_posix()
                    expected = inventory_by_path.get(logical)
                    actual_digest, actual_size = _sha256_file(
                        candidate,
                        ancestor_root=root,
                    )
                except (OSError, RuntimeError, ValueError, ProjectRuntimeError):
                    return False
                return bool(
                    live_payload_aligned
                    and expected is not None
                    and expected == (actual_size, actual_digest)
                )

            executable_receipt_bound = receipt_bound_file(executable)
            module_receipt_bound = receipt_bound_file(module_path)
            expected_core_paths = (
                (
                    archive_cli_module_path,
                    final
                    / "Lib"
                    / "site-packages"
                    / "wom_kit"
                    / "archive_cli.py",
                ),
                (
                    project_runtime_module_path,
                    final
                    / "Lib"
                    / "site-packages"
                    / "wom_kit"
                    / "project_runtime.py",
                ),
                (
                    package_origin_path,
                    final / "Lib" / "site-packages" / "wom_kit" / "__init__.py",
                ),
            )
            core_modules_receipt_bound = all(
                _same_absolute_path(observed, expected)
                and receipt_bound_file(observed)
                for observed, expected in expected_core_paths
            )
        except ProjectRuntimeError:
            live_payload_aligned = False
    bound = bool(
        launcher_aligned
        and static_receipt_aligned
        and live_payload_aligned
        and executable_aligned
        and module_aligned
        and prefix_aligned
        and executable_receipt_bound
        and module_receipt_bound
        and core_modules_receipt_bound
        and isolated
        and no_bytecode
    )
    if not launcher_aligned:
        reason_code = "project_runtime_launcher_mismatch"
    elif not static_receipt_aligned:
        reason_code = "project_runtime_static_receipt_invalid"
    elif not live_payload_aligned:
        reason_code = "project_runtime_live_payload_mismatch"
    elif not executable_aligned or not module_aligned or not prefix_aligned:
        reason_code = "project_runtime_process_binding_mismatch"
    elif not executable_receipt_bound or not module_receipt_bound:
        reason_code = "project_runtime_process_bytes_not_receipt_bound"
    elif not core_modules_receipt_bound:
        reason_code = "project_runtime_core_modules_not_receipt_bound"
    elif not isolated or not no_bytecode:
        reason_code = "project_runtime_canonical_launcher_flags_missing"
    else:
        reason_code = "current_project_runtime_bound"
    return {
        "bound": bound,
        "reason_code": reason_code,
        "launcher_aligned": launcher_aligned,
        "static_receipt_aligned": static_receipt_aligned,
        "receipt_generation_aligned": receipt_generation_aligned,
        "live_payload_aligned": live_payload_aligned,
        "running_executable_aligned": executable_aligned,
        "running_module_aligned": module_aligned,
        "running_prefix_aligned": prefix_aligned,
        "running_executable_receipt_bound": executable_receipt_bound,
        "running_module_receipt_bound": module_receipt_bound,
        "core_modules_receipt_bound": core_modules_receipt_bound,
        "isolated_mode": isolated,
        "dont_write_bytecode": no_bytecode,
        "verification_scope": "current_process_operational_binding",
        "project_runtime_argv": project_runtime_argv(),
        "private_values_echoed": False,
        "absolute_paths_echoed": False,
    }


def project_write_guard(
    inspection_root: Path,
    *,
    running_version: str,
    running_module_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return a content-free blocker when a project pin and runtime differ."""

    root = Path(os.path.abspath(str(inspection_root)))
    search_roots = [root]
    try:
        if (root / "archive.yml").is_file() and root.parent != root:
            search_roots.append(root.parent)
    except OSError:
        pass
    for project_root in search_roots:
        update_lock_path = (
            project_root / ".zettel-kasten" / "version-update.lock"
        )
        try:
            update_lock_present = os.path.lexists(update_lock_path)
        except OSError:
            update_lock_present = True
        if update_lock_present:
            return {
                "blocked": True,
                "reason_code": "project_update_recovery_required",
                "project_runtime_argv": project_runtime_argv(),
                "private_values_echoed": False,
                "absolute_paths_echoed": False,
            }
        pin_path = project_root / ".zettel-kasten" / "installed-version.txt"
        try:
            pin_present = os.path.lexists(pin_path)
        except OSError:
            pin_present = True
        if not pin_present:
            continue
        if not _existing_components_are_real(project_root, pin_path):
            return {
                "blocked": True,
                "reason_code": "project_runtime_pin_unsafe",
                "project_runtime_argv": project_runtime_argv(),
                "private_values_echoed": False,
                "absolute_paths_echoed": False,
            }
        pin_bytes = _read_limited(
            pin_path,
            limit=1024,
            ancestor_root=project_root,
        )
        try:
            pinned_version = _version((pin_bytes or b"").decode("utf-8-sig").strip())
        except UnicodeError:
            pinned_version = None
        running = _version(running_version)
        if pinned_version is None:
            return {
                "blocked": True,
                "reason_code": "project_runtime_pin_invalid",
                "project_runtime_argv": project_runtime_argv(),
                "private_values_echoed": False,
                "absolute_paths_echoed": False,
            }
        if pinned_version != running:
            blocked = True
            detail_reason_code = "project_runtime_version_mismatch"
        else:
            minimum = _version("0.4.3")
            runtime_required = bool(
                minimum is not None
                and tuple(int(part) for part in pinned_version.split("."))
                >= tuple(int(part) for part in minimum.split("."))
            )
            if runtime_required:
                installed = inspect_runtime(project_root, pinned_version)
                binding = current_project_runtime_binding(
                    project_root,
                    pinned_version,
                    running_module_path=running_module_path,
                    runtime_inspection=installed,
                )
                blocked = bool(
                    not installed.get("receipt_candidate_valid")
                    or installed.get("live_payload_aligned") is not True
                    or not binding.get("bound")
                )
                detail_reason_code = (
                    "project_runtime_static_receipt_invalid"
                    if not installed.get("static_receipt_valid")
                    else "project_runtime_live_payload_mismatch"
                    if installed.get("live_payload_aligned") is not True
                    else str(binding.get("reason_code"))
                )
            else:
                blocked = False
                detail_reason_code = "project_runtime_version_aligned"
        return {
            "blocked": blocked,
            "reason_code": (
                "project_runtime_mismatch"
                if blocked
                else "project_runtime_version_aligned"
            ),
            "detail_reason_code": detail_reason_code,
            "project_pin": f"v{pinned_version}",
            "running_version": f"v{running}" if running else None,
            "project_runtime_argv": project_runtime_argv(),
            "private_values_echoed": False,
            "absolute_paths_echoed": False,
        }
    return {
        "blocked": False,
        "reason_code": "project_runtime_pin_not_found",
        "project_runtime_argv": project_runtime_argv(),
        "private_values_echoed": False,
        "absolute_paths_echoed": False,
    }


def launcher_snapshot(project_root: Path, target: str) -> dict[str, Any]:
    path = project_root / PROJECT_RUNTIME_LAUNCHER_RELATIVE
    previous = _read_limited(
        path,
        limit=64 * 1024,
        ancestor_root=project_root,
    )
    try:
        present = os.path.lexists(path)
    except OSError:
        present = True
    unsafe = present and previous is None
    if not _existing_components_are_real(project_root, path):
        unsafe = True
    target_bytes = launcher_bytes(target)
    return {
        "path": path,
        "logical": PROJECT_RUNTIME_LAUNCHER_RELATIVE.as_posix(),
        "existed": present and previous is not None,
        "previous_bytes": previous,
        "target_bytes": target_bytes,
        "already_target": previous == target_bytes,
        "unsafe": unsafe,
    }


def runtime_supply_matches_current_interpreter(supply: RuntimeSupplyLock) -> bool:
    machine = platform.machine().replace("-", "_").casefold()
    return bool(
        os.name == "nt"
        and sys.implementation.name.casefold() == supply.implementation
        and f"{sys.version_info.major}.{sys.version_info.minor}"
        == supply.python_version
        and supply.python_tag == f"cp{sys.version_info.major}{sys.version_info.minor}"
        and supply.abi_tag == supply.python_tag
        and supply.platform_tag == "win_amd64"
        and machine in {"amd64", "x86_64"}
    )


def inspect_runtime(
    project_root: Path,
    target: str,
    *,
    expected_commit: str | None = None,
    expected_wheel_sha256: str | None = None,
    expected_supply_lock_sha256: str | None = None,
) -> dict[str, Any]:
    version = _version(target)
    if version is None:
        return {
            "status": "invalid_target",
            "verified": False,
            "receipt_candidate_valid": False,
            "static_receipt_valid": False,
            "live_payload_aligned": False,
            "absolute_paths_echoed": False,
        }
    root = Path(os.path.abspath(str(project_root)))
    final = runtime_path(root, version)
    logical = runtime_logical_path(version)
    receipt_path = final / PROJECT_RUNTIME_RECEIPT_NAME
    try:
        final_present = os.path.lexists(final)
    except OSError:
        final_present = True
    if not final_present:
        return {
            "status": "missing",
            "verified": False,
            "receipt_candidate_valid": False,
            "static_receipt_valid": False,
            "live_payload_aligned": False,
            "path": logical,
            "receipt_sha256": None,
            "absolute_paths_echoed": False,
        }
    try:
        final_stat = final.lstat()
    except OSError:
        final_stat = None
    if (
        final_stat is None
        or not stat_module.S_ISDIR(final_stat.st_mode)
        or _is_reparse_stat(final_stat)
        or _real_component_snapshot(root, final, target_must_exist=True) is None
        or _real_component_snapshot(root, receipt_path, target_must_exist=True) is None
    ):
        return {
            "status": "unsafe",
            "verified": False,
            "receipt_candidate_valid": False,
            "static_receipt_valid": False,
            "live_payload_aligned": False,
            "path": logical,
            "receipt_sha256": None,
            "absolute_paths_echoed": False,
        }
    receipt_bytes = _read_limited(
        receipt_path,
        limit=2 * 1024 * 1024,
        ancestor_root=root,
    )
    try:
        receipt = _json_without_duplicate_keys(receipt_bytes or b"")
    except (UnicodeError, json.JSONDecodeError, ValueError):
        receipt = None
    expected_sha = str(expected_wheel_sha256 or "").removeprefix("sha256:") or None
    expected_lock_sha = (
        str(expected_supply_lock_sha256 or "").removeprefix("sha256:") or None
    )
    verification = receipt.get("verification") if isinstance(receipt, dict) else None
    receipt_schema_valid = bool(
        isinstance(receipt, dict)
        and not validate_schema(
            receipt,
            "project-runtime-receipt-v0.1.schema.json",
        )
    )
    python_executable = final / "Scripts" / "python.exe"
    static_receipt_valid = bool(
        receipt_schema_valid
        and receipt.get("schema") == PROJECT_RUNTIME_RECEIPT_SCHEMA
        and receipt.get("target_tag") == f"v{version}"
        and receipt.get("target_version") == version
        and (expected_commit is None or receipt.get("target_commit") == expected_commit)
        and (
            expected_sha is None
            or receipt.get("wheel_sha256") == f"sha256:{expected_sha}"
        )
        and (
            expected_lock_sha is None
            or receipt.get("supply_lock_sha256")
            == f"sha256:{expected_lock_sha}"
        )
        and isinstance(verification, dict)
        and verification.get("pip_check") is True
        and verification.get("version") is True
        and verification.get("package_resources") is True
        and verification.get("new_process") is True
        and verification.get("supply_lock") is True
        and verification.get("artifact_hashes") is True
        and verification.get("artifact_sizes") is True
        and verification.get("artifact_inventory") is True
        and verification.get("installed_payload") is True
        and verification.get("live_process") is True
    )
    required_python_safe = False
    live_payload_sha256: str | None = None
    live_payload_aligned = False
    if static_receipt_valid:
        try:
            _python_digest, _python_size = _sha256_file(
                python_executable,
                ancestor_root=root,
            )
            required_python_safe = True
            live_payload_digest, live_inventory = _runtime_payload_observation(final)
            live_payload_sha256 = f"sha256:{live_payload_digest}"
            python_logical = python_executable.relative_to(final).as_posix()
            python_in_inventory = any(
                logical_path == python_logical
                for logical_path, _size, _digest in live_inventory
            )
            live_payload_aligned = bool(
                required_python_safe
                and python_in_inventory
                and receipt.get("installed_payload_sha256")
                == live_payload_sha256
            )
        except (OSError, RuntimeError, ValueError, ProjectRuntimeError):
            required_python_safe = False
            live_payload_aligned = False
    valid = bool(static_receipt_valid and required_python_safe and live_payload_aligned)
    return {
        "status": "receipt_candidate" if valid else "invalid",
        "verified": False,
        "receipt_candidate_valid": valid,
        "static_receipt_valid": static_receipt_valid,
        "live_payload_aligned": live_payload_aligned,
        "required_python_safe": required_python_safe,
        "path": logical,
        "target_tag": f"v{version}",
        "target_version": version,
        "target_commit": receipt.get("target_commit") if isinstance(receipt, dict) else None,
        "wheel_sha256": receipt.get("wheel_sha256") if isinstance(receipt, dict) else None,
        "supply_lock_sha256": (
            receipt.get("supply_lock_sha256") if isinstance(receipt, dict) else None
        ),
        "installed_payload_sha256": (
            receipt.get("installed_payload_sha256")
            if isinstance(receipt, dict)
            else None
        ),
        "live_payload_sha256": live_payload_sha256,
        "python_version": receipt.get("python_version") if isinstance(receipt, dict) else None,
        "verification": verification if isinstance(verification, dict) else {},
        "receipt_sha256": f"sha256:{_sha256_bytes(receipt_bytes)}" if receipt_bytes else None,
        "verification_basis": "receipt_binding_and_descriptor_bound_live_payload_hash",
        "verification_scope": "static_receipt_plus_live_payload_bytes",
        "live_reverification_required_before_reuse": True,
        "absolute_paths_echoed": False,
    }


def plan_runtime(
    project_root: Path,
    target: str,
    *,
    policy_state: str,
    target_commit: str | None,
    bootstrap: BootstrapWheel | None,
    bootstrap_summary: Mapping[str, Any],
    supply: RuntimeSupplyLock | None = None,
    enforce_interpreter: bool = True,
) -> tuple[dict[str, Any], list[str], list[str]]:
    required = policy_state == "required"
    deferred = policy_state == "deferred"
    expected_sha = bootstrap.sha256 if bootstrap is not None else None
    expected_lock_sha = supply.sha256 if supply is not None else None
    installed = inspect_runtime(
        project_root,
        target,
        expected_commit=target_commit,
        expected_wheel_sha256=expected_sha,
        expected_supply_lock_sha256=expected_lock_sha,
    )
    launcher = launcher_snapshot(project_root, target)
    blockers: list[str] = []
    warnings: list[str] = []
    if required and installed["status"] in {"invalid", "unsafe"}:
        blockers.append("project_runtime_target_directory_invalid")
    if required and not installed.get("verified") and bootstrap is None:
        blockers.append("project_runtime_exact_public_wheel_required")
    if required and supply is None:
        blockers.append("project_runtime_exact_supply_lock_required")
    if required and supply is not None and supply.target_tag != f"v{_version(target)}":
        blockers.append("project_runtime_supply_lock_target_mismatch")
    interpreter_compatible = bool(
        supply is not None and runtime_supply_matches_current_interpreter(supply)
    )
    if required and supply is not None and not interpreter_compatible:
        if enforce_interpreter:
            blockers.append("project_runtime_interpreter_not_locked")
        else:
            warnings.append(
                "The exact project runtime is locked to a different interpreter or platform; a Windows lock-held approval preparation will enforce this boundary before any write."
            )
    if required and launcher.get("unsafe"):
        blockers.append("project_runtime_launcher_path_unsafe")
    if deferred and bootstrap is None:
        warnings.append(
            "Project-runtime policy is deferred until the exact target tag is fetched; approval will fail closed if that tag requires a project runtime and this process is not the exact public release wheel."
        )
    runtime_creation_required = bool(
        required and not installed.get("receipt_candidate_valid")
    )
    materialization_required = bool(required)
    activation_required = bool(required and not launcher.get("already_target"))
    summary = {
        "policy_state": policy_state,
        "required": required,
        "target_path": runtime_logical_path(target),
        "launcher_path": PROJECT_RUNTIME_LAUNCHER_RELATIVE.as_posix(),
        "project_runtime_argv": project_runtime_argv(),
        "installed": installed,
        "bootstrap": dict(bootstrap_summary),
        "supply": (
            supply.public_summary()
            if supply is not None
            else {
                "available": False,
                "lock_sha256": None,
                "index_resolution": False,
                "download_urls_echoed": False,
            }
        ),
        "interpreter_compatible": interpreter_compatible,
        "interpreter_enforced": enforce_interpreter,
        "materialization_required": materialization_required,
        "runtime_creation_required": runtime_creation_required,
        "live_reverification_required": required,
        "activation_required": activation_required,
        "active_version_pin": ".zettel-kasten/installed-version.txt",
        "global_path_mutation": False,
        "previous_runtime_deletion": False,
    }
    return summary, blockers, warnings


def _emit(
    callback: Callable[[str, str, int | None, int | None], None] | None,
    stage: str,
    event: str,
    current: int | None = None,
    total: int | None = None,
) -> None:
    if callback is not None:
        callback(stage, event, current, total)


def _isolated_python_environment() -> dict[str, str]:
    """Return a subprocess environment that cannot shadow the project runtime."""

    blocked = {
        "__PYVENV_LAUNCHER__",
        "CONDA_DEFAULT_ENV",
        "CONDA_PREFIX",
        "PYTHONCASEOK",
        "PYTHONEXECUTABLE",
        "PYTHONHOME",
        "PYTHONINSPECT",
        "PYTHONIOENCODING",
        "PYTHONNOUSERSITE",
        "PYTHONOPTIMIZE",
        "PYTHONPATH",
        "PYTHONSAFEPATH",
        "PYTHONSTARTUP",
        "PYTHONUSERBASE",
        "PYTHONWARNINGS",
        "VIRTUAL_ENV",
    }
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in blocked and not key.upper().startswith("PIP_")
    }
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONNOUSERSITE": "1",
            "PYTHONSAFEPATH": "1",
            "PYTHONUTF8": "1",
        }
    )
    return environment


def _run_bounded(
    argv: list[str],
    *,
    stage: str,
    callback: Callable[[str, str, int | None, int | None], None] | None,
    timeout_seconds: float = 240.0,
    capture: bool = False,
) -> str:
    _emit(callback, stage, "start")
    started = time.monotonic()
    last_heartbeat = started
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=False,
        env=_isolated_python_environment(),
    )
    while process.poll() is None:
        now = time.monotonic()
        if now - started > timeout_seconds:
            process.kill()
            process.wait()
            raise ProjectRuntimeError(f"{stage}_timeout")
        if now - last_heartbeat >= 9.0:
            _emit(callback, stage, "heartbeat")
            last_heartbeat = now
        time.sleep(0.2)
    output = b""
    if capture and process.stdout is not None:
        try:
            output = process.stdout.read(1024 * 1024 + 1)
        finally:
            process.stdout.close()
    if process.returncode != 0 or len(output) > 1024 * 1024:
        raise ProjectRuntimeError(f"{stage}_failed")
    _emit(callback, stage, "done")
    return output.decode("utf-8", errors="strict").strip() if capture else ""


def _release_asset_redirect_url_valid(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return bool(
        parsed.scheme == "https"
        and (parsed.hostname or "").casefold()
        in {
            "release-assets.githubusercontent.com",
            "objects.githubusercontent.com",
        }
        and parsed.username is None
        and parsed.password is None
        and not parsed.params
        and not parsed.fragment
        and bool(parsed.path)
    )


class _RuntimeArtifactRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(
        self,
        *,
        source_kind: str,
        callback: Callable[[str, str, int | None, int | None], None] | None,
        stage: str,
    ) -> None:
        super().__init__()
        self.source_kind = source_kind
        self.callback = callback
        self.stage = stage

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        if self.source_kind != "github_release" or not _release_asset_redirect_url_valid(
            newurl
        ):
            raise ProjectRuntimeError("project_runtime_artifact_redirect_unsafe")
        _emit(self.callback, self.stage, "heartbeat")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_runtime_artifact(
    request: urllib.request.Request,
    *,
    source_kind: str,
    callback: Callable[[str, str, int | None, int | None], None] | None,
    stage: str,
) -> Any:
    opener = urllib.request.build_opener(
        _RuntimeArtifactRedirectHandler(
            source_kind=source_kind,
            callback=callback,
            stage=stage,
        )
    )
    # The per-socket bound stays below the ten-second heartbeat contract.  A
    # redirect emits a heartbeat before the next allowlisted connection.
    return opener.open(request, timeout=8.0)


def _download_exact_artifact(
    *,
    url: str,
    expected_sha256: str,
    expected_size: int | None,
    destination: Path,
    callback: Callable[[str, str, int | None, int | None], None] | None,
    stage: str,
    source_kind: str,
) -> int:
    initial_url = urllib.parse.urlparse(url)
    if source_kind == "pypi_file":
        initial_valid = bool(
            initial_url.scheme == "https"
            and (initial_url.hostname or "").casefold()
            == "files.pythonhosted.org"
            and initial_url.username is None
            and initial_url.password is None
            and not initial_url.params
            and not initial_url.query
            and not initial_url.fragment
        )
    elif source_kind == "github_release":
        initial_valid = bool(
            initial_url.scheme == "https"
            and (initial_url.hostname or "").casefold() == "github.com"
            and initial_url.username is None
            and initial_url.password is None
            and not initial_url.params
            and not initial_url.query
            and not initial_url.fragment
            and PUBLIC_WHEEL_PATH_RE.fullmatch(initial_url.path) is not None
        )
    else:
        initial_valid = False
    if not initial_valid:
        raise ProjectRuntimeError("project_runtime_artifact_url_unsafe")
    _emit(callback, stage, "start")
    digest = hashlib.sha256()
    total = 0
    last_heartbeat = time.monotonic()
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "wom-kit-project-runtime/0.1"},
        method="GET",
    )
    with _open_runtime_artifact(
        request,
        source_kind=source_kind,
        callback=callback,
        stage=stage,
    ) as response, destination.open("xb") as handle:
        final_url = urllib.parse.urlparse(response.geturl())
        final_host = (final_url.hostname or "").casefold()
        final_common_valid = bool(
            final_url.scheme == "https"
            and final_url.username is None
            and final_url.password is None
            and not final_url.params
            and not final_url.fragment
        )
        pypi_final_valid = bool(
            source_kind == "pypi_file"
            and final_common_valid
            and final_host == "files.pythonhosted.org"
            and not final_url.query
            and response.geturl() == url
        )
        github_final_valid = bool(
            source_kind == "github_release"
            and final_common_valid
            and (
                (
                    final_host == "github.com"
                    and final_url.path == initial_url.path
                    and not final_url.query
                )
                or _release_asset_redirect_url_valid(response.geturl())
            )
        )
        if not pypi_final_valid and not github_final_valid:
            raise ProjectRuntimeError("project_runtime_artifact_redirect_unsafe")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > 128 * 1024 * 1024:
                raise ProjectRuntimeError("project_runtime_artifact_too_large")
            handle.write(chunk)
            digest.update(chunk)
            now = time.monotonic()
            if now - last_heartbeat >= 9.0:
                _emit(callback, stage, "heartbeat", total, expected_size)
                last_heartbeat = now
    if expected_size is not None and total != expected_size:
        raise ProjectRuntimeError("project_runtime_artifact_size_mismatch")
    if digest.hexdigest() != expected_sha256:
        raise ProjectRuntimeError("project_runtime_artifact_sha256_mismatch")
    _emit(callback, stage, "done", total, total)
    return total


def _download_exact_wheel(
    bootstrap: BootstrapWheel,
    destination: Path,
    callback: Callable[[str, str, int | None, int | None], None] | None,
) -> None:
    _download_exact_artifact(
        url=bootstrap.url,
        expected_sha256=bootstrap.sha256,
        expected_size=None,
        destination=destination,
        callback=callback,
        stage="project-runtime-wheel",
        source_kind="github_release",
    )


def _resource_check_script() -> str:
    return (
        "import hashlib,json;"
        "from wom_kit.resource_paths import PACKAGED_RESOURCES_ROOT,packaged_resource_manifest;"
        "r=PACKAGED_RESOURCES_ROOT;"
        "m=packaged_resource_manifest();"
        "assert m['version'];"
        "assert all((r/f['packaged']).is_file() and "
        "hashlib.sha256((r/f['packaged']).read_bytes()).hexdigest()==f['sha256'] "
        "for f in m['files']);"
        "print('verified')"
    )


def _sha256_file(
    path: Path,
    *,
    limit: int = 512 * 1024 * 1024,
    ancestor_root: Path | None = None,
    tree_shape_bound: bool = False,
) -> tuple[str, int]:
    observed = _stable_regular_file_observation(
        path,
        limit=limit,
        ancestor_root=ancestor_root,
        collect_bytes=False,
        tree_shape_bound=tree_shape_bound,
    )
    if observed is None:
        raise ProjectRuntimeError("project_runtime_file_unreadable_or_changed")
    return observed[1], observed[2]


def _walk_regular_files(
    root: Path,
    *,
    excluded_top_level: set[str] | None = None,
    max_files: int = 100_000,
    max_total_bytes: int = 4 * 1024 * 1024 * 1024,
    require_stable_tree_generation: bool = False,
) -> list[tuple[str, Path, int, str]]:
    def shape_snapshot() -> tuple[
        tuple[str, str, int, int, int, int, int, int], ...
    ]:
        try:
            root_stat = root.lstat()
        except OSError as error:
            raise ProjectRuntimeError("project_runtime_tree_unreadable") from error
        if (
            not stat_module.S_ISDIR(root_stat.st_mode)
            or stat_module.S_ISLNK(root_stat.st_mode)
            or _is_reparse_stat(root_stat)
        ):
            raise ProjectRuntimeError("project_runtime_tree_unsafe")
        pending: list[tuple[Path, PurePosixPath]] = [(root, PurePosixPath("."))]
        observed: list[tuple[str, str, int, int, int, int, int, int]] = [
            (
                ".",
                "directory",
                int(root_stat.st_dev),
                int(root_stat.st_ino),
                int(stat_module.S_IFMT(root_stat.st_mode)),
                int(root_stat.st_size),
                int(root_stat.st_mtime_ns),
                int(getattr(root_stat, "st_file_attributes", 0)),
            )
        ]
        file_count = 0
        byte_count = 0
        while pending:
            directory, logical_parent = pending.pop()
            try:
                directory_before = directory.lstat()
                if (
                    not stat_module.S_ISDIR(directory_before.st_mode)
                    or stat_module.S_ISLNK(directory_before.st_mode)
                    or _is_reparse_stat(directory_before)
                ):
                    raise ProjectRuntimeError("project_runtime_tree_unsafe")
                with os.scandir(directory) as iterator:
                    entries = sorted(
                        iterator,
                        key=lambda item: (item.name.casefold(), item.name),
                    )
                directory_after = directory.lstat()
            except OSError as error:
                raise ProjectRuntimeError("project_runtime_tree_unreadable") from error
            if _stat_identity(directory_before) != _stat_identity(directory_after):
                raise ProjectRuntimeError("project_runtime_tree_changed")
            seen: set[str] = set()
            for entry in entries:
                name_key = entry.name.casefold()
                if name_key in seen:
                    raise ProjectRuntimeError("project_runtime_tree_case_collision")
                seen.add(name_key)
                relative = (
                    PurePosixPath(entry.name)
                    if logical_parent == PurePosixPath(".")
                    else logical_parent / entry.name
                )
                if logical_parent == PurePosixPath(".") and name_key in excluded:
                    continue
                try:
                    entry_path = Path(entry.path)
                    entry_stat = entry_path.lstat()
                except OSError as error:
                    raise ProjectRuntimeError("project_runtime_tree_unreadable") from error
                if stat_module.S_ISLNK(entry_stat.st_mode) or _is_reparse_stat(
                    entry_stat
                ):
                    raise ProjectRuntimeError("project_runtime_tree_unsafe")
                if stat_module.S_ISDIR(entry_stat.st_mode):
                    kind = "directory"
                    pending.append((entry_path, relative))
                elif stat_module.S_ISREG(entry_stat.st_mode):
                    kind = "file"
                    file_count += 1
                    byte_count += int(entry_stat.st_size)
                    if file_count > max_files or byte_count > max_total_bytes:
                        raise ProjectRuntimeError("project_runtime_tree_too_large")
                else:
                    raise ProjectRuntimeError("project_runtime_tree_unsafe")
                observed.append(
                    (
                        relative.as_posix(),
                        kind,
                        int(entry_stat.st_dev),
                        int(entry_stat.st_ino),
                        int(stat_module.S_IFMT(entry_stat.st_mode)),
                        int(entry_stat.st_size),
                        int(entry_stat.st_mtime_ns),
                        int(getattr(entry_stat, "st_file_attributes", 0)),
                    )
                )
        observed.sort(key=lambda item: (item[0].casefold(), item[0], item[1]))
        return tuple(observed)

    files: list[tuple[str, Path, int, str]] = []
    excluded = {item.casefold() for item in (excluded_top_level or set())}
    before_shape = shape_snapshot()
    for logical, kind, _dev, _ino, _mode, expected_size, _mtime, _attrs in before_shape:
        if kind != "file":
            continue
        path = root.joinpath(*PurePosixPath(logical).parts)
        # The pre/post whole-tree shape binds every ancestor generation.  The
        # per-file descriptor observation therefore needs to repeat only its
        # immediate directory and pathname checks here.
        digest, size = _sha256_file(path, tree_shape_bound=True)
        if size != expected_size:
            raise ProjectRuntimeError("project_runtime_tree_changed")
        files.append((logical, path, size, digest))
    if require_stable_tree_generation and shape_snapshot() != before_shape:
        raise ProjectRuntimeError("project_runtime_tree_changed")
    files.sort(key=lambda item: (item[0].casefold(), item[0]))
    return files


def _runtime_payload_observation(
    final: Path,
) -> tuple[str, tuple[tuple[str, int, str], ...]]:
    files = _walk_regular_files(
        final,
        excluded_top_level={
            PROJECT_RUNTIME_ARTIFACTS_NAME,
            PROJECT_RUNTIME_RECEIPT_NAME,
            PROJECT_RUNTIME_INSTALLING_NAME,
        },
        require_stable_tree_generation=True,
    )
    digest = hashlib.sha256()
    for logical, _path, size, file_sha256 in files:
        digest.update(logical.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_sha256.encode("ascii"))
        digest.update(b"\n")
    inventory = tuple((logical, size, file_sha256) for logical, _path, size, file_sha256 in files)
    return digest.hexdigest(), inventory


def _runtime_payload_sha256(final: Path) -> str:
    return _runtime_payload_observation(final)[0]


def _wheel_payload_manifest(
    wheel_path: Path,
) -> tuple[dict[str, tuple[int, str]], set[str]]:
    expected: dict[str, tuple[int, str]] = {}
    roots: set[str] = set()
    total_uncompressed = 0
    try:
        with zipfile.ZipFile(wheel_path) as archive:
            seen: set[str] = set()
            for info in archive.infolist():
                name = info.filename
                logical = PurePosixPath(name)
                if (
                    not name
                    or "\\" in name
                    or logical.is_absolute()
                    or ".." in logical.parts
                    or name.casefold() in seen
                    or bool(info.flag_bits & 0x1)
                    or ((info.external_attr >> 16) & 0o170000) == 0o120000
                ):
                    raise ProjectRuntimeError("project_runtime_wheel_payload_unsafe")
                seen.add(name.casefold())
                if info.is_dir():
                    continue
                if ".data" in {part.casefold() for part in logical.parts}:
                    raise ProjectRuntimeError("project_runtime_wheel_data_layout_unsupported")
                total_uncompressed += info.file_size
                if (
                    info.file_size < 0
                    or info.file_size > 512 * 1024 * 1024
                    or total_uncompressed > 1024 * 1024 * 1024
                ):
                    raise ProjectRuntimeError("project_runtime_wheel_payload_too_large")
                member_digest = hashlib.sha256()
                member_size = 0
                with archive.open(info, "r") as handle:
                    while True:
                        chunk = handle.read(1024 * 1024)
                        if not chunk:
                            break
                        member_size += len(chunk)
                        if member_size > info.file_size:
                            raise ProjectRuntimeError(
                                "project_runtime_wheel_payload_size_mismatch"
                            )
                        member_digest.update(chunk)
                if member_size != info.file_size:
                    raise ProjectRuntimeError(
                        "project_runtime_wheel_payload_size_mismatch"
                    )
                roots.add(logical.parts[0])
                if name.casefold().endswith(".dist-info/record"):
                    continue
                expected[name] = (member_size, member_digest.hexdigest())
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        if isinstance(error, ProjectRuntimeError):
            raise
        raise ProjectRuntimeError("project_runtime_wheel_payload_unreadable") from error
    if not expected or not roots:
        raise ProjectRuntimeError("project_runtime_wheel_payload_empty")
    return expected, roots


def _validate_generated_dist_info_file(
    *,
    final: Path,
    site_packages: Path,
    logical: str,
    path: Path,
    expected_record_paths: set[str],
) -> bool:
    parts = PurePosixPath(logical).parts
    if len(parts) != 2 or not parts[0].casefold().endswith(".dist-info"):
        return False
    name = parts[1].casefold()
    data = _read_limited(path, limit=4 * 1024 * 1024)
    if data is None:
        return False
    if name == "installer":
        return data == b"pip\n"
    if name == "requested":
        return data == b""
    if name != "record":
        return False
    try:
        text = data.decode("utf-8")
        rows = list(csv.reader(text.splitlines()))
    except (UnicodeError, csv.Error):
        return False
    if not rows or len(rows) > 100_000:
        return False
    final_absolute = Path(os.path.abspath(str(final)))
    record_logical = logical.casefold()
    observed_record_paths: set[str] = set()
    observed_record_keys: set[str] = set()
    for row in rows:
        if len(row) != 3:
            return False
        recorded_path, recorded_hash, recorded_size = row
        pure = PurePosixPath(recorded_path)
        if (
            not recorded_path
            or "\\" in recorded_path
            or "\x00" in recorded_path
            or pure.is_absolute()
            or ":" in pure.parts[0]
        ):
            return False
        record_key = pure.as_posix().casefold()
        if record_key in observed_record_keys:
            return False
        observed_record_keys.add(record_key)
        observed_record_paths.add(pure.as_posix())
        resolved = Path(os.path.abspath(str(site_packages.joinpath(*pure.parts))))
        try:
            resolved.relative_to(final_absolute)
        except ValueError:
            return False
        if not _existing_components_are_real(final, resolved) or not resolved.is_file():
            return False
        is_record = pure.as_posix().casefold() == record_logical
        if is_record:
            if recorded_hash or recorded_size:
                return False
        else:
            digest, size = _sha256_file(resolved)
            encoded = base64.urlsafe_b64encode(bytes.fromhex(digest)).rstrip(b"=").decode(
                "ascii"
            )
            if recorded_hash != f"sha256={encoded}" or recorded_size != str(size):
                return False
    return observed_record_paths == expected_record_paths


def _verify_installed_wheel_payloads(final: Path, wheels: list[Path]) -> set[str]:
    site_packages = final / "Lib" / "site-packages"
    if not _existing_components_are_real(final, site_packages):
        raise ProjectRuntimeError("project_runtime_site_packages_unsafe")
    combined: dict[str, tuple[int, str]] = {}
    roots: set[str] = set()
    top_level: set[str] = set()
    expected_records: dict[str, set[str]] = {}
    for wheel in wheels:
        manifest, wheel_roots = _wheel_payload_manifest(wheel)
        dist_info_roots = [
            root for root in wheel_roots if root.casefold().endswith(".dist-info")
        ]
        if len(dist_info_roots) != 1:
            raise ProjectRuntimeError("project_runtime_wheel_dist_info_invalid")
        dist_info_root = dist_info_roots[0]
        expected_records[dist_info_root] = {
            *manifest,
            f"{dist_info_root}/INSTALLER",
            f"{dist_info_root}/REQUESTED",
            f"{dist_info_root}/RECORD",
        }
        for logical, binding in manifest.items():
            if logical in combined and combined[logical] != binding:
                raise ProjectRuntimeError("project_runtime_wheel_payload_collision")
            combined[logical] = binding
            top_level.add(PurePosixPath(logical).parts[0])
        overlap = {item.casefold() for item in roots} & {
            item.casefold() for item in wheel_roots
        }
        if overlap:
            raise ProjectRuntimeError("project_runtime_wheel_root_collision")
        roots.update(wheel_roots)
    for logical, (expected_size, expected_sha256) in combined.items():
        path = site_packages.joinpath(*PurePosixPath(logical).parts)
        if not _existing_components_are_real(final, path):
            raise ProjectRuntimeError("project_runtime_installed_payload_unsafe")
        actual_sha256, actual_size = _sha256_file(path)
        if actual_size != expected_size or actual_sha256 != expected_sha256:
            raise ProjectRuntimeError("project_runtime_installed_payload_mismatch")
    expected_root_files = {
        logical
        for logical in combined
        if PurePosixPath(logical).parts[0] in roots
    }
    observed_root_files: set[str] = set()
    for root_name in sorted(roots, key=str.casefold):
        root_path = site_packages / root_name
        expected_as_file = root_name in expected_root_files
        if expected_as_file:
            observed_root_files.add(root_name)
            continue
        for logical, path, _size, _sha256 in _walk_regular_files(root_path):
            observed = f"{root_name}/{logical}"
            observed_root_files.add(observed)
            if observed not in expected_root_files and not _validate_generated_dist_info_file(
                final=final,
                site_packages=site_packages,
                logical=observed,
                path=path,
                expected_record_paths=expected_records.get(root_name, set()),
            ):
                raise ProjectRuntimeError(
                    "project_runtime_installed_payload_inventory_mismatch"
                )
    missing = expected_root_files - observed_root_files
    if missing:
        raise ProjectRuntimeError("project_runtime_installed_payload_inventory_mismatch")
    return top_level


def _trusted_pip_wheel() -> Path:
    bundled = Path(sys.base_prefix) / "Lib" / "ensurepip" / "_bundled"
    try:
        candidates = sorted(bundled.glob("pip-*-py3-none-any.whl"))
    except OSError as error:
        raise ProjectRuntimeError("project_runtime_trusted_pip_unavailable") from error
    if len(candidates) != 1:
        raise ProjectRuntimeError("project_runtime_trusted_pip_unavailable")
    wheel = candidates[0]
    if not _existing_components_are_real(Path(sys.base_prefix), wheel):
        raise ProjectRuntimeError("project_runtime_trusted_pip_unavailable")
    _wheel_payload_manifest(wheel)
    return wheel


def _runtime_requirements(
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
) -> list[str]:
    return [
        f"wom-kit=={bootstrap.version}",
        *(f"{item.distribution}=={item.version}" for item in supply.artifacts),
    ]


def _run_offline_runtime_install(
    python_executable: Path,
    *,
    wheelhouse: Path,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    stage: str,
    progress_callback: Callable[[str, str, int | None, int | None], None] | None,
) -> None:
    _run_bounded(
        [
            str(python_executable),
            "-I",
            "-B",
            "-X",
            "utf8",
            "-m",
            "pip",
            "--isolated",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "--no-cache-dir",
            "--no-compile",
            "--no-index",
            "--no-deps",
            "--find-links",
            str(wheelhouse),
            *_runtime_requirements(bootstrap, supply),
        ],
        stage=stage,
        callback=progress_callback,
    )


def _prune_runtime_scripts(runtime: Path) -> None:
    scripts = runtime / "Scripts"
    if not _existing_components_are_real(runtime, scripts):
        raise ProjectRuntimeError("project_runtime_scripts_unsafe")
    allowed = {"python.exe", "pythonw.exe"}
    try:
        with os.scandir(scripts) as iterator:
            entries = list(iterator)
        for entry in entries:
            entry_path = Path(entry.path)
            # DirEntry.stat() can report zero device/inode values on Windows;
            # Path.lstat() supplies the stable identity rechecked by the retry.
            stat_result = entry_path.lstat()
            if (
                entry.name.casefold() in allowed
                and entry.is_file(follow_symlinks=False)
                and not entry.is_symlink()
                and not bool(getattr(stat_result, "st_file_attributes", 0) & 0x400)
            ):
                continue
            if (
                entry.is_symlink()
                or bool(getattr(stat_result, "st_file_attributes", 0) & 0x400)
                or not entry.is_file(follow_symlinks=False)
            ):
                raise ProjectRuntimeError("project_runtime_scripts_unsafe")
            _unlink_owned_runtime_file_with_retry(
                runtime,
                entry_path,
                expected_identity=(int(stat_result.st_dev), int(stat_result.st_ino)),
            )
    except OSError as error:
        raise ProjectRuntimeError("project_runtime_scripts_cleanup_failed") from error
    observed = {path.name.casefold() for path in scripts.iterdir()}
    if observed != allowed:
        raise ProjectRuntimeError("project_runtime_scripts_cleanup_failed")


def _unlink_owned_runtime_file_with_retry(
    runtime: Path,
    path: Path,
    *,
    expected_identity: tuple[int, int],
) -> None:
    """Remove one owned runtime file despite a short Windows scanner lock.

    Only Windows sharing/access conflicts are retried.  Windows deletion is
    performed through a retained handle bound to the exact identity, bytes,
    size, and timestamp observed before the first attempt.  A pathname swap can
    therefore never redirect deletion to a replacement file.
    """

    try:
        current = path.lstat()
    except OSError as error:
        raise ProjectRuntimeError(
            "project_runtime_scripts_cleanup_failed"
        ) from error
    if (
        not _path_is_within(path, runtime)
        or not _existing_components_are_real(runtime, path)
        or not stat_module.S_ISREG(current.st_mode)
        or path.is_symlink()
        or _is_reparse(current)
        or (int(current.st_dev), int(current.st_ino)) != expected_identity
        or int(current.st_nlink) != 1
    ):
        raise ProjectRuntimeError("project_runtime_scripts_unsafe")
    observation = _stable_regular_file_observation(
        path,
        limit=64 * 1024 * 1024,
        ancestor_root=runtime,
        collect_bytes=False,
    )
    if observation is None:
        raise ProjectRuntimeError("project_runtime_scripts_unsafe")
    _raw, digest, size = observation
    try:
        approved = path.lstat()
    except OSError as error:
        raise ProjectRuntimeError(
            "project_runtime_scripts_cleanup_failed"
        ) from error
    if (
        not stat_module.S_ISREG(approved.st_mode)
        or _is_reparse(approved)
        or (int(approved.st_dev), int(approved.st_ino)) != expected_identity
        or int(approved.st_nlink) != 1
        or int(approved.st_size) != size
    ):
        raise ProjectRuntimeError("project_runtime_scripts_unsafe")
    exact_record: dict[str, Any] = {
        "type": "file",
        "identity": {
            "device": int(approved.st_dev),
            "inode": int(approved.st_ino),
        },
        "size": size,
        "mtime_ns": int(approved.st_mtime_ns),
        "sha256": digest,
    }

    for attempt in range(PROJECT_RUNTIME_TRANSIENT_UNLINK_ATTEMPTS):
        try:
            _delete_exact_owned_runtime_file(runtime, path, exact_record)
            return
        except OSError as error:
            transient = bool(
                os.name == "nt"
                and getattr(error, "code", None)
                == "legacy_cleanup_bound_win32_open_uncertain"
                and _winerror_from_exception_chain(error)
                in PROJECT_RUNTIME_TRANSIENT_WINDOWS_ERRORS
            )
            if (
                not transient
                or attempt == PROJECT_RUNTIME_TRANSIENT_UNLINK_ATTEMPTS - 1
            ):
                if _bound_delete_error_is_unsafe(error):
                    raise ProjectRuntimeError(
                        "project_runtime_scripts_unsafe"
                    ) from error
                raise ProjectRuntimeError(
                    "project_runtime_scripts_cleanup_failed"
                ) from error
            time.sleep(
                PROJECT_RUNTIME_TRANSIENT_UNLINK_BACKOFF_SECONDS * (attempt + 1)
            )
    raise ProjectRuntimeError("project_runtime_scripts_cleanup_failed")


def _delete_exact_owned_runtime_file(
    runtime: Path,
    path: Path,
    exact_record: Mapping[str, Any],
) -> None:
    if os.name != "nt":
        # Project runtimes are a Windows product surface.  Keep the portable
        # unit boundary deterministic without pretending POSIX unlink is an
        # exact compare-and-delete primitive.
        path.unlink()
        return
    # Delayed import avoids the archive_services -> project_runtime import
    # cycle; the bound-delete helper is only needed after module initialization.
    from .legacy_cleanup_bound_delete import _delete_exact_approved_file

    _delete_exact_approved_file(runtime, path, exact_record)


def _winerror_from_exception_chain(error: BaseException) -> int | None:
    observed: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in observed:
        observed.add(id(current))
        value = getattr(current, "winerror", None)
        if isinstance(value, int):
            return value
        current = current.__cause__ or current.__context__
    return None


def _bound_delete_error_is_unsafe(error: BaseException) -> bool:
    code = getattr(error, "code", "")
    return bool(
        isinstance(code, str)
        and (
            "_drift" in code
            or "_unsafe" in code
            or "alternate_data_stream" in code
            or code
            in {
                "legacy_cleanup_bound_file_hardlink",
                "legacy_cleanup_bound_win32_file_name_uncertain",
                "legacy_cleanup_bound_path_invalid",
                "legacy_cleanup_bound_path_outside_root",
                "legacy_cleanup_bound_path_stream_syntax",
            }
        )
    )


def _remove_runtime_bytecode(runtime: Path) -> None:
    files = _walk_regular_files(runtime)
    for logical, path, _size, _digest in files:
        if path.suffix.casefold() == ".pyc" or "__pycache__" in {
            part.casefold() for part in PurePosixPath(logical).parts
        }:
            try:
                path.unlink()
            except OSError as error:
                raise ProjectRuntimeError("project_runtime_bytecode_cleanup_failed") from error
    directories = sorted(
        (
            path
            for path in runtime.rglob("__pycache__")
            if path.is_dir() and not path.is_symlink()
        ),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError as error:
            raise ProjectRuntimeError("project_runtime_bytecode_cleanup_failed") from error
    if any(path.suffix.casefold() == ".pyc" for path in runtime.rglob("*.pyc")):
        raise ProjectRuntimeError("project_runtime_bytecode_cleanup_failed")


def _canonicalize_pyvenv_cfg(runtime: Path) -> None:
    path = runtime / "pyvenv.cfg"
    if not _existing_components_are_real(runtime, path) or not path.is_file():
        raise ProjectRuntimeError("project_runtime_pyvenv_unsafe")
    data = (
        f"home = {Path(sys.base_prefix)}\n"
        "include-system-site-packages = false\n"
        f"version = {platform.python_version()}\n"
        f"executable = {Path(sys.executable)}\n"
    ).encode("utf-8")
    try:
        path.write_bytes(data)
    except OSError as error:
        raise ProjectRuntimeError("project_runtime_pyvenv_write_failed") from error


def _canonicalize_installed_records(runtime: Path, wheels: list[Path]) -> None:
    site_packages = runtime / "Lib" / "site-packages"
    for wheel in wheels:
        manifest, roots = _wheel_payload_manifest(wheel)
        dist_info_roots = sorted(
            (root for root in roots if root.casefold().endswith(".dist-info")),
            key=str.casefold,
        )
        if len(dist_info_roots) != 1:
            raise ProjectRuntimeError("project_runtime_wheel_dist_info_invalid")
        dist_info_root = dist_info_roots[0]
        dist_info = site_packages / dist_info_root
        allowed_existing = {
            logical
            for logical in manifest
            if PurePosixPath(logical).parts[0] == dist_info_root
        } | {
            f"{dist_info_root}/RECORD",
            f"{dist_info_root}/INSTALLER",
            f"{dist_info_root}/REQUESTED",
        }
        observed = {
            f"{dist_info_root}/{logical}"
            for logical, _path, _size, _digest in _walk_regular_files(dist_info)
        }
        if not observed <= allowed_existing:
            raise ProjectRuntimeError("project_runtime_dist_info_extra_file")
        installer = dist_info / "INSTALLER"
        requested = dist_info / "REQUESTED"
        installer.write_bytes(b"pip\n")
        requested.write_bytes(b"")
        record_rows: list[list[str]] = []
        record_logical = f"{dist_info_root}/RECORD"
        record_members = sorted(
            {
                *manifest,
                f"{dist_info_root}/INSTALLER",
                f"{dist_info_root}/REQUESTED",
            }
            - {record_logical},
            key=lambda value: (value.casefold(), value),
        )
        for logical in record_members:
            path = site_packages.joinpath(*PurePosixPath(logical).parts)
            digest, size = _sha256_file(path)
            encoded = base64.urlsafe_b64encode(bytes.fromhex(digest)).rstrip(b"=").decode(
                "ascii"
            )
            record_rows.append([logical, f"sha256={encoded}", str(size)])
        record_rows.append([record_logical, "", ""])
        output = io.StringIO(newline="")
        csv.writer(output, lineterminator="\n").writerows(record_rows)
        (dist_info / "RECORD").write_bytes(output.getvalue().encode("utf-8"))


def _normalized_runtime_payload_inventory(
    runtime: Path,
) -> tuple[tuple[str, int, str], ...]:
    root_text = str(Path(os.path.abspath(str(runtime))))
    variants = {
        root_text,
        root_text.replace("\\", "/"),
    }
    replacements: list[tuple[bytes, bytes]] = []
    for value in variants:
        replacements.append((value.encode("utf-8"), b"<WOM_RUNTIME_ROOT>"))
        replacements.append(
            (value.encode("utf-16le"), "<WOM_RUNTIME_ROOT>".encode("utf-16le"))
        )
    replacements.sort(key=lambda item: len(item[0]), reverse=True)
    inventory: list[tuple[str, int, str]] = []
    for logical, path, _size, _digest in _walk_regular_files(
        runtime,
        excluded_top_level={
            PROJECT_RUNTIME_ARTIFACTS_NAME,
            PROJECT_RUNTIME_RECEIPT_NAME,
            PROJECT_RUNTIME_INSTALLING_NAME,
        },
    ):
        data = _read_limited(path, limit=512 * 1024 * 1024)
        if data is None:
            raise ProjectRuntimeError("project_runtime_payload_unreadable")
        normalized = data
        for source, replacement in replacements:
            normalized = normalized.replace(source, replacement)
        inventory.append((logical, len(normalized), _sha256_bytes(normalized)))
    return tuple(inventory)


def _artifact_inventory_entry(
    *,
    role: str,
    distribution: str,
    version: str,
    file_name: str,
    size_bytes: int,
    sha256: str,
) -> dict[str, Any]:
    return {
        "role": role,
        "distribution": distribution,
        "version": version,
        "file_name": file_name,
        "size_bytes": size_bytes,
        "sha256": f"sha256:{sha256}",
    }


def _prepared_bundle_snapshot(
    root: Path,
) -> tuple[tuple[int, int], tuple[tuple[str, int, int, int, int, str], ...]]:
    try:
        root_stat = root.lstat()
        if (
            not root.is_dir()
            or root.is_symlink()
            or bool(getattr(root_stat, "st_file_attributes", 0) & 0x400)
        ):
            raise ProjectRuntimeError("project_runtime_prepared_bundle_unsafe")
        files: list[tuple[str, int, int, int, int, str]] = []
        seen: set[str] = set()
        with os.scandir(root) as iterator:
            entries = sorted(iterator, key=lambda item: (item.name.casefold(), item.name))
        for entry in entries:
            name_key = entry.name.casefold()
            stat_result = entry.stat(follow_symlinks=False)
            if (
                name_key in seen
                or entry.is_symlink()
                or bool(getattr(stat_result, "st_file_attributes", 0) & 0x400)
                or not entry.is_file(follow_symlinks=False)
            ):
                raise ProjectRuntimeError("project_runtime_prepared_bundle_unsafe")
            seen.add(name_key)
            digest, size = _sha256_file(Path(entry.path), limit=128 * 1024 * 1024)
            files.append(
                (
                    entry.name,
                    int(stat_result.st_dev),
                    int(stat_result.st_ino),
                    size,
                    int(stat_result.st_mtime_ns),
                    digest,
                )
            )
    except OSError as error:
        raise ProjectRuntimeError("project_runtime_prepared_bundle_unreadable") from error
    return (
        (int(root_stat.st_dev), int(root_stat.st_ino)),
        tuple(files),
    )


def _prepared_bundle_digest(
    *,
    target_tag: str,
    target_commit: str,
    wheel_sha256: str,
    supply_lock_sha256: str,
    snapshot: tuple[tuple[str, int, int, int, int, str], ...],
) -> str:
    public_files = [
        {"name": name, "size_bytes": size, "sha256": f"sha256:{digest}"}
        for name, _device, _inode, size, _mtime_ns, digest in snapshot
    ]
    binding = {
        "schema": PROJECT_RUNTIME_PREPARED_BUNDLE_SCHEMA,
        "target_tag": target_tag,
        "target_commit": target_commit,
        "wheel_sha256": f"sha256:{wheel_sha256}",
        "supply_lock_sha256": f"sha256:{supply_lock_sha256}",
        "files": public_files,
        "network_complete": True,
        "post_approval_network_allowed": False,
    }
    return _sha256_bytes(
        (json.dumps(binding, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
    )


def cleanup_prepared_runtime_bundle(
    bundle: PreparedRuntimeBundle | PreparedRuntimeCleanupHandle,
) -> bool:
    """Remove one exact private bundle and prove absence; repeated calls are safe."""

    handle = bundle.cleanup_handle if isinstance(bundle, PreparedRuntimeBundle) else bundle
    root = handle.root
    if not root.exists():
        return True
    try:
        temp_root = Path(os.path.abspath(tempfile.gettempdir()))
        root_absolute = Path(os.path.abspath(str(root)))
        root_absolute.relative_to(temp_root)
        root_stat = root_absolute.lstat()
        if (
            not root_absolute.name.startswith(PROJECT_RUNTIME_PREPARED_PREFIX)
            or root_absolute.is_symlink()
            or not root_absolute.is_dir()
            or bool(getattr(root_stat, "st_file_attributes", 0) & 0x400)
            or (
                handle.root_identity is not None
                and (int(root_stat.st_dev), int(root_stat.st_ino))
                != handle.root_identity
            )
        ):
            return False
        if handle.marker_bytes is not None and _read_limited(
            root_absolute / PROJECT_RUNTIME_PREPARED_MARKER_NAME,
            limit=64 * 1024,
        ) != handle.marker_bytes:
            return False
        with os.scandir(root_absolute) as iterator:
            entries = list(iterator)
        for entry in entries:
            stat_result = entry.stat(follow_symlinks=False)
            if (
                entry.is_symlink()
                or bool(getattr(stat_result, "st_file_attributes", 0) & 0x400)
                or not entry.is_file(follow_symlinks=False)
            ):
                return False
        for entry in entries:
            Path(entry.path).unlink()
        root_absolute.rmdir()
    except (OSError, RuntimeError, ValueError):
        return False
    return not root.exists()


def _expected_bundle_inventory(
    *,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    main_size: int,
) -> tuple[Mapping[str, Any], ...]:
    inventory = [
        _artifact_inventory_entry(
            role="runtime",
            distribution="wom-kit",
            version=bootstrap.version,
            file_name=bootstrap.file_name,
            size_bytes=main_size,
            sha256=bootstrap.sha256,
        ),
        *[
            _artifact_inventory_entry(
                role=item.role,
                distribution=item.distribution,
                version=item.version,
                file_name=item.file_name,
                size_bytes=item.size_bytes,
                sha256=item.sha256,
            )
            for item in supply.artifacts
        ],
    ]
    inventory.sort(key=lambda item: (str(item["file_name"]).casefold(), str(item["file_name"])))
    return tuple(inventory)


def prepare_runtime_bundle(
    *,
    target: str,
    target_commit: str,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    progress_callback: Callable[[str, str, int | None, int | None], None] | None = None,
) -> PreparedRuntimeBundle:
    """Complete all runtime network I/O before native approval."""

    version = _version(target)
    parsed_supply = project_runtime_supply_lock(supply.raw_bytes, expected_target=target)
    if (
        version is None
        or bootstrap.version != version
        or bootstrap.tag != f"v{version}"
        or COMMIT_RE.fullmatch(target_commit) is None
        or parsed_supply != supply
        or supply.target_tag != f"v{version}"
        or not runtime_supply_matches_current_interpreter(supply)
    ):
        raise ProjectRuntimeError("project_runtime_preparation_binding_invalid")
    root: Path | None = None
    cleanup_handle: PreparedRuntimeCleanupHandle | None = None
    try:
        root = Path(tempfile.mkdtemp(prefix=PROJECT_RUNTIME_PREPARED_PREFIX))
        cleanup_handle = PreparedRuntimeCleanupHandle(
            root=root,
            root_identity=None,
            marker_bytes=None,
        )
        root_stat = root.lstat()
        cleanup_handle = PreparedRuntimeCleanupHandle(
            root=root,
            root_identity=(int(root_stat.st_dev), int(root_stat.st_ino)),
            marker_bytes=None,
        )
        marker_bytes = (
            json.dumps(
                {
                    "schema": PROJECT_RUNTIME_PREPARED_BUNDLE_SCHEMA,
                    "target_tag": f"v{version}",
                    "target_commit": target_commit,
                    "wheel_sha256": f"sha256:{bootstrap.sha256}",
                    "supply_lock_sha256": f"sha256:{supply.sha256}",
                    "ownership_nonce": secrets.token_hex(16),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        (root / PROJECT_RUNTIME_PREPARED_MARKER_NAME).write_bytes(marker_bytes)
        cleanup_handle = PreparedRuntimeCleanupHandle(
            root=root,
            root_identity=cleanup_handle.root_identity,
            marker_bytes=marker_bytes,
        )
        (root / PROJECT_RUNTIME_RETAINED_LOCK_NAME).write_bytes(supply.raw_bytes)
        main_path = root / bootstrap.file_name
        main_size = _download_exact_artifact(
            url=bootstrap.url,
            expected_sha256=bootstrap.sha256,
            expected_size=None,
            destination=main_path,
            callback=progress_callback,
            stage="project-runtime-wheel",
            source_kind="github_release",
        )
        for index, artifact in enumerate(supply.artifacts, start=1):
            _download_exact_artifact(
                url=artifact.url,
                expected_sha256=artifact.sha256,
                expected_size=artifact.size_bytes,
                destination=root / artifact.file_name,
                callback=progress_callback,
                stage=f"project-runtime-dependency-{index}",
                source_kind="pypi_file",
            )
        inventory = _expected_bundle_inventory(
            bootstrap=bootstrap,
            supply=supply,
            main_size=main_size,
        )
        root_identity, snapshot = _prepared_bundle_snapshot(root)
        bundle_sha256 = _prepared_bundle_digest(
            target_tag=f"v{version}",
            target_commit=target_commit,
            wheel_sha256=bootstrap.sha256,
            supply_lock_sha256=supply.sha256,
            snapshot=snapshot,
        )
        bundle = PreparedRuntimeBundle(
            target_tag=f"v{version}",
            target_version=version,
            target_commit=target_commit,
            root=root,
            cleanup_handle=PreparedRuntimeCleanupHandle(
                root=root,
                root_identity=root_identity,
                marker_bytes=marker_bytes,
            ),
            marker_bytes=marker_bytes,
            file_snapshot=snapshot,
            bundle_sha256=bundle_sha256,
            wheel_sha256=bootstrap.sha256,
            supply_lock_sha256=supply.sha256,
            artifact_inventory=inventory,
        )
        verify_prepared_runtime_bundle(
            bundle,
            target=target,
            target_commit=target_commit,
            bootstrap=bootstrap,
            supply=supply,
        )
        return bundle
    except BaseException as error:
        if cleanup_handle is not None and not cleanup_prepared_runtime_bundle(cleanup_handle):
            raise PreparedRuntimeBundleCleanupError(cleanup_handle) from error
        if isinstance(error, ProjectRuntimeError):
            raise
        raise ProjectRuntimeError("project_runtime_preparation_failed") from error


def verify_prepared_runtime_bundle(
    bundle: PreparedRuntimeBundle,
    *,
    target: str,
    target_commit: str,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
) -> dict[str, Any]:
    version = _version(target)
    if (
        version is None
        or bundle.target_tag != f"v{version}"
        or bundle.target_version != version
        or bundle.target_commit != target_commit
        or bundle.wheel_sha256 != bootstrap.sha256
        or bundle.supply_lock_sha256 != supply.sha256
        or bundle.cleanup_handle.marker_bytes != bundle.marker_bytes
    ):
        raise ProjectRuntimeError("project_runtime_prepared_bundle_binding_invalid")
    root_identity, snapshot = _prepared_bundle_snapshot(bundle.root)
    expected_file_names = {
        PROJECT_RUNTIME_PREPARED_MARKER_NAME,
        PROJECT_RUNTIME_RETAINED_LOCK_NAME,
        bootstrap.file_name,
        *(artifact.file_name for artifact in supply.artifacts),
    }
    if (
        root_identity != bundle.cleanup_handle.root_identity
        or snapshot != bundle.file_snapshot
        or {item[0] for item in snapshot} != expected_file_names
        or _read_limited(
            bundle.root / PROJECT_RUNTIME_PREPARED_MARKER_NAME,
            limit=64 * 1024,
        )
        != bundle.marker_bytes
        or _read_limited(
            bundle.root / PROJECT_RUNTIME_RETAINED_LOCK_NAME,
            limit=256 * 1024,
        )
        != supply.raw_bytes
    ):
        raise ProjectRuntimeError("project_runtime_prepared_bundle_drift")
    digest = _prepared_bundle_digest(
        target_tag=bundle.target_tag,
        target_commit=target_commit,
        wheel_sha256=bootstrap.sha256,
        supply_lock_sha256=supply.sha256,
        snapshot=snapshot,
    )
    if digest != bundle.bundle_sha256:
        raise ProjectRuntimeError("project_runtime_prepared_bundle_drift")
    main_digest, main_size = _sha256_file(
        bundle.root / bootstrap.file_name,
        limit=128 * 1024 * 1024,
    )
    expected_inventory = _expected_bundle_inventory(
        bootstrap=bootstrap,
        supply=supply,
        main_size=main_size,
    )
    if main_digest != bootstrap.sha256 or tuple(
        dict(item) for item in bundle.artifact_inventory
    ) != tuple(dict(item) for item in expected_inventory):
        raise ProjectRuntimeError("project_runtime_prepared_bundle_drift")
    for artifact in supply.artifacts:
        digest_value, size = _sha256_file(
            bundle.root / artifact.file_name,
            limit=128 * 1024 * 1024,
        )
        if digest_value != artifact.sha256 or size != artifact.size_bytes:
            raise ProjectRuntimeError("project_runtime_prepared_bundle_drift")
    summary = bundle.public_summary()
    summary["live_reverified"] = True
    return summary


def _verify_retained_artifacts(
    final: Path,
    *,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    receipt_inventory: Any,
) -> tuple[tuple[Mapping[str, Any], ...], list[Path], set[str]]:
    artifacts_root = final / PROJECT_RUNTIME_ARTIFACTS_NAME
    if not _existing_components_are_real(final, artifacts_root):
        raise ProjectRuntimeError("project_runtime_artifact_directory_unsafe")
    lock_path = artifacts_root / PROJECT_RUNTIME_RETAINED_LOCK_NAME
    lock_bytes = _read_limited(lock_path, limit=256 * 1024)
    if lock_bytes != supply.raw_bytes or _sha256_bytes(lock_bytes or b"") != supply.sha256:
        raise ProjectRuntimeError("project_runtime_retained_supply_lock_mismatch")
    if not isinstance(receipt_inventory, list):
        raise ProjectRuntimeError("project_runtime_artifact_inventory_invalid")
    inventory_by_file: dict[str, Mapping[str, Any]] = {}
    for item in receipt_inventory:
        if not isinstance(item, dict) or set(item) != {
            "role",
            "distribution",
            "version",
            "file_name",
            "size_bytes",
            "sha256",
        }:
            raise ProjectRuntimeError("project_runtime_artifact_inventory_invalid")
        file_name = item.get("file_name")
        if (
            not isinstance(file_name, str)
            or file_name.casefold() in {key.casefold() for key in inventory_by_file}
        ):
            raise ProjectRuntimeError("project_runtime_artifact_inventory_invalid")
        inventory_by_file[file_name] = item
    expected_names = {
        PROJECT_RUNTIME_RETAINED_LOCK_NAME,
        bootstrap.file_name,
        *(item.file_name for item in supply.artifacts),
    }
    try:
        observed_names = {path.name for path in artifacts_root.iterdir()}
    except OSError as error:
        raise ProjectRuntimeError("project_runtime_artifact_inventory_unreadable") from error
    if observed_names != expected_names or set(inventory_by_file) != expected_names - {
        PROJECT_RUNTIME_RETAINED_LOCK_NAME
    }:
        raise ProjectRuntimeError("project_runtime_artifact_inventory_mismatch")
    main_item = inventory_by_file.get(bootstrap.file_name)
    if (
        main_item is None
        or main_item.get("role") != "runtime"
        or main_item.get("distribution") != "wom-kit"
        or main_item.get("version") != bootstrap.version
        or main_item.get("sha256") != f"sha256:{bootstrap.sha256}"
        or type(main_item.get("size_bytes")) is not int
        or not (1 <= int(main_item["size_bytes"]) <= 128 * 1024 * 1024)
    ):
        raise ProjectRuntimeError("project_runtime_artifact_inventory_mismatch")
    expected_dependencies = {
        item.file_name: _artifact_inventory_entry(
            role=item.role,
            distribution=item.distribution,
            version=item.version,
            file_name=item.file_name,
            size_bytes=item.size_bytes,
            sha256=item.sha256,
        )
        for item in supply.artifacts
    }
    for file_name, expected in expected_dependencies.items():
        if inventory_by_file.get(file_name) != expected:
            raise ProjectRuntimeError("project_runtime_artifact_inventory_mismatch")
    wheel_paths: list[Path] = []
    canonical_inventory: list[Mapping[str, Any]] = []
    for file_name in sorted(inventory_by_file, key=str.casefold):
        item = inventory_by_file[file_name]
        path = artifacts_root / file_name
        if not _existing_components_are_real(final, path):
            raise ProjectRuntimeError("project_runtime_artifact_path_unsafe")
        digest, size = _sha256_file(path, limit=128 * 1024 * 1024)
        if (
            size != item.get("size_bytes")
            or f"sha256:{digest}" != item.get("sha256")
        ):
            raise ProjectRuntimeError("project_runtime_retained_artifact_mismatch")
        wheel_paths.append(path)
        canonical_inventory.append(dict(item))
    artifact_top_level = _verify_installed_wheel_payloads(final, wheel_paths)
    return tuple(canonical_inventory), wheel_paths, artifact_top_level


def _normalize_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).casefold()


def _validate_distribution_inventory(
    packages: Any,
    *,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
) -> str:
    if not isinstance(packages, list):
        raise ProjectRuntimeError("project_runtime_package_inventory_mismatch")
    expected = {
        "wom-kit": bootstrap.version,
        **{
            _normalize_distribution_name(item.distribution): item.version
            for item in supply.artifacts
        },
    }
    observed: dict[str, str] = {}
    pip_version: str | None = None
    for item in packages:
        if not isinstance(item, dict) or set(item) != {"name", "version"}:
            raise ProjectRuntimeError("project_runtime_package_inventory_mismatch")
        name = item.get("name")
        version = item.get("version")
        if not isinstance(name, str) or not isinstance(version, str) or not version:
            raise ProjectRuntimeError("project_runtime_package_inventory_mismatch")
        normalized = _normalize_distribution_name(name)
        if normalized in observed:
            raise ProjectRuntimeError("project_runtime_package_inventory_mismatch")
        observed[normalized] = version
        if normalized == "pip":
            pip_version = version
    if pip_version is None or observed != {**expected, "pip": pip_version}:
        raise ProjectRuntimeError("project_runtime_package_inventory_mismatch")
    return pip_version


def _verify_site_packages_top_level(
    final: Path,
    *,
    artifact_top_level: set[str],
    pip_version: str,
) -> None:
    site_packages = final / "Lib" / "site-packages"
    expected = {
        *artifact_top_level,
        "pip",
        f"pip-{pip_version}.dist-info",
    }
    try:
        observed: set[str] = set()
        with os.scandir(site_packages) as iterator:
            for entry in iterator:
                stat_result = entry.stat(follow_symlinks=False)
                if entry.is_symlink() or bool(
                    getattr(stat_result, "st_file_attributes", 0) & 0x400
                ):
                    raise ProjectRuntimeError("project_runtime_site_packages_unsafe")
                observed.add(entry.name)
    except OSError as error:
        raise ProjectRuntimeError("project_runtime_site_packages_unreadable") from error
    if {item.casefold() for item in observed} != {
        item.casefold() for item in expected
    }:
        raise ProjectRuntimeError("project_runtime_site_packages_inventory_mismatch")


def _static_distribution_inventory(
    final: Path,
    *,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    retained_wheels: list[Path],
) -> tuple[list[dict[str, Any]], str, set[str]]:
    site_packages = final / "Lib" / "site-packages"
    pip_wheel = _trusted_pip_wheel()
    artifact_top_level = _verify_installed_wheel_payloads(
        final,
        [*retained_wheels, pip_wheel],
    )
    try:
        packages = sorted(
            [
                {"name": distribution.metadata.get("Name"), "version": distribution.version}
                for distribution in importlib.metadata.distributions(
                    path=[str(site_packages)]
                )
            ],
            key=lambda item: (
                str(item["name"]).casefold(),
                str(item["version"]),
            ),
        )
    except (OSError, UnicodeError) as error:
        raise ProjectRuntimeError("project_runtime_package_inventory_invalid") from error
    pip_version = _validate_distribution_inventory(
        packages,
        bootstrap=bootstrap,
        supply=supply,
    )
    _verify_site_packages_top_level(
        final,
        artifact_top_level=artifact_top_level,
        pip_version=pip_version,
    )
    return packages, pip_version, artifact_top_level


def _explicit_site_command(
    python_executable: Path,
    site_packages: Path,
    script: str,
) -> list[str]:
    return [
        str(python_executable),
        "-I",
        "-B",
        "-S",
        "-X",
        "utf8",
        "-c",
        "import sys;site=sys.argv.pop(1);sys.path.insert(0,site);" + script,
        str(site_packages),
    ]


def _runtime_process_verification(
    final: Path,
    *,
    version: str,
    stage_prefix: str,
    progress_callback: Callable[[str, str, int | None, int | None], None] | None,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    retained_wheels: list[Path],
    reuse_isolated: bool = False,
    pip_check_proven: bool | None = None,
    expected_receipt_packages: Any = None,
    expected_python_version: str | None = None,
) -> tuple[dict[str, bool], list[dict[str, Any]], str]:
    python_executable = final / "Scripts" / "python.exe"
    site_packages = final / "Lib" / "site-packages"
    static_stage = f"{stage_prefix}-static-inventory"
    if progress_callback is not None:
        progress_callback(static_stage, "start", None, None)
    static_packages, _pip_version, _artifact_top_level = _static_distribution_inventory(
        final,
        bootstrap=bootstrap,
        supply=supply,
        retained_wheels=retained_wheels,
    )
    if progress_callback is not None:
        progress_callback(static_stage, "done", None, None)
    if not reuse_isolated:
        _run_bounded(
            [
                str(python_executable),
                "-I",
                "-B",
                "-X",
                "utf8",
                "-m",
                "pip",
                "--isolated",
                "check",
            ],
            stage=f"{stage_prefix}-pip-check",
            callback=progress_callback,
        )
        version_argv = [
            str(python_executable),
            "-I",
            "-B",
            "-X",
            "utf8",
            "-m",
            "wom_kit.archive_cli",
            "--version",
        ]
        resource_argv = [
            str(python_executable),
            "-I",
            "-B",
            "-X",
            "utf8",
            "-c",
            _resource_check_script(),
        ]
        process_argv = [
            str(python_executable),
            "-I",
            "-B",
            "-X",
            "utf8",
            "-c",
            "import wom_kit; print(wom_kit.__version__)",
        ]
        packages_argv = [
            str(python_executable),
            "-I",
            "-B",
            "-X",
            "utf8",
            "-c",
            "import importlib.metadata,json; print(json.dumps(sorted([{'name':d.metadata.get('Name'),'version':d.version} for d in importlib.metadata.distributions()], key=lambda x:(str(x['name']).casefold(),x['version']))))",
        ]
    else:
        if pip_check_proven is not True:
            raise ProjectRuntimeError("project_runtime_reuse_pip_check_unproven")
        version_argv = _explicit_site_command(
            python_executable,
            site_packages,
            "import runpy;sys.argv=['archive','--version'];runpy.run_module('wom_kit.archive_cli',run_name='__main__')",
        )
        resource_argv = _explicit_site_command(
            python_executable,
            site_packages,
            _resource_check_script(),
        )
        process_argv = _explicit_site_command(
            python_executable,
            site_packages,
            "import wom_kit;print(wom_kit.__version__)",
        )
        packages_argv = _explicit_site_command(
            python_executable,
            site_packages,
            "import importlib.metadata,json;print(json.dumps(sorted([{'name':d.metadata.get('Name'),'version':d.version} for d in importlib.metadata.distributions(path=[site])],key=lambda x:(str(x['name']).casefold(),x['version']))))",
        )
    version_output = _run_bounded(
        version_argv,
        stage=f"{stage_prefix}-version",
        callback=progress_callback,
        capture=True,
    )
    if version_output != f"archive {version}":
        raise ProjectRuntimeError("project_runtime_version_mismatch")
    resource_output = _run_bounded(
        resource_argv,
        stage=f"{stage_prefix}-resources",
        callback=progress_callback,
        capture=True,
    )
    if resource_output != "verified":
        raise ProjectRuntimeError("project_runtime_resource_verification_failed")
    process_output = _run_bounded(
        process_argv,
        stage=f"{stage_prefix}-new-process",
        callback=progress_callback,
        capture=True,
    )
    if process_output != version:
        raise ProjectRuntimeError("project_runtime_new_process_mismatch")
    packages_output = _run_bounded(
        packages_argv,
        stage=f"{stage_prefix}-package-inventory",
        callback=progress_callback,
        capture=True,
    )
    try:
        packages = json.loads(packages_output)
    except json.JSONDecodeError as error:
        raise ProjectRuntimeError("project_runtime_package_inventory_invalid") from error
    _validate_distribution_inventory(
        packages,
        bootstrap=bootstrap,
        supply=supply,
    )
    if packages != static_packages:
        raise ProjectRuntimeError("project_runtime_package_inventory_mismatch")
    if expected_receipt_packages is not None and packages != expected_receipt_packages:
        raise ProjectRuntimeError("project_runtime_package_inventory_mismatch")
    python_argv = [str(python_executable), "-I", "-B"]
    if reuse_isolated:
        python_argv.append("-S")
    python_argv.extend(
        ["-X", "utf8", "-c", "import platform; print(platform.python_version())"]
    )
    python_version = _run_bounded(
        python_argv,
        stage=f"{stage_prefix}-python-version",
        callback=progress_callback,
        capture=True,
    )
    if expected_python_version is not None and python_version != expected_python_version:
        raise ProjectRuntimeError("project_runtime_python_version_mismatch")
    verification = {
        "wheel_sha256": True,
        "pip_check": True,
        "version": True,
        "package_resources": True,
        "new_process": True,
        "supply_lock": True,
        "artifact_hashes": True,
        "artifact_sizes": True,
        "artifact_inventory": True,
        "installed_payload": True,
        "live_process": True,
    }
    return verification, packages, python_version


def _bundle_wheel_paths(
    bundle: PreparedRuntimeBundle,
    *,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
) -> list[Path]:
    return [
        bundle.root / bootstrap.file_name,
        *(bundle.root / artifact.file_name for artifact in supply.artifacts),
    ]


def _initialize_runtime_payload(
    runtime: Path,
    *,
    wheelhouse: Path,
    wheel_paths: list[Path],
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    stage_prefix: str,
    progress_callback: Callable[[str, str, int | None, int | None], None] | None,
) -> tuple[dict[str, bool], list[dict[str, Any]], str]:
    def local_stage(name: str, action: Callable[[], None]) -> None:
        stage = f"{stage_prefix}-{name}"
        if progress_callback is not None:
            progress_callback(stage, "start", None, None)
        action()
        if progress_callback is not None:
            progress_callback(stage, "done", None, None)

    _run_bounded(
        [
            sys.executable,
            "-I",
            "-B",
            "-X",
            "utf8",
            "-m",
            "venv",
            "--copies",
            str(runtime),
        ],
        stage=f"{stage_prefix}-venv",
        callback=progress_callback,
    )
    python_executable = runtime / "Scripts" / "python.exe"
    _run_offline_runtime_install(
        python_executable,
        wheelhouse=wheelhouse,
        bootstrap=bootstrap,
        supply=supply,
        stage=f"{stage_prefix}-install",
        progress_callback=progress_callback,
    )
    local_stage("prune-scripts", lambda: _prune_runtime_scripts(runtime))
    local_stage("bytecode-cleanup", lambda: _remove_runtime_bytecode(runtime))
    local_stage("pyvenv-canonicalize", lambda: _canonicalize_pyvenv_cfg(runtime))
    trusted_pip_stage = f"{stage_prefix}-trusted-pip-discovery"
    if progress_callback is not None:
        progress_callback(trusted_pip_stage, "start", None, None)
    trusted_pip_wheel = _trusted_pip_wheel()
    if progress_callback is not None:
        progress_callback(trusted_pip_stage, "done", None, None)
    local_stage(
        "record-canonicalize",
        lambda: _canonicalize_installed_records(
            runtime,
            [*wheel_paths, trusted_pip_wheel],
        ),
    )
    local_stage(
        "installed-payload-verify",
        lambda: _verify_installed_wheel_payloads(
            runtime,
            [*wheel_paths, trusted_pip_wheel],
        ),
    )
    return _runtime_process_verification(
        runtime,
        version=bootstrap.version,
        stage_prefix=stage_prefix,
        progress_callback=progress_callback,
        bootstrap=bootstrap,
        supply=supply,
        retained_wheels=wheel_paths,
    )


def _reference_payload_inventory(
    bundle: PreparedRuntimeBundle,
    *,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    progress_callback: Callable[[str, str, int | None, int | None], None] | None,
) -> tuple[tuple[tuple[str, int, str], ...], Mapping[str, bool]]:
    shadow_parent: Path | None = None
    try:
        with tempfile.TemporaryDirectory(
            prefix="wom-project-runtime-reference-"
        ) as temporary:
            shadow_parent = Path(temporary)
            reference = shadow_parent / f"v{bootstrap.version}"
            wheel_paths = _bundle_wheel_paths(
                bundle,
                bootstrap=bootstrap,
                supply=supply,
            )
            reference_verification, _packages, _python_version = _initialize_runtime_payload(
                reference,
                wheelhouse=bundle.root,
                wheel_paths=wheel_paths,
                bootstrap=bootstrap,
                supply=supply,
                stage_prefix="project-runtime-reference",
                progress_callback=progress_callback,
            )
            inventory = _normalized_runtime_payload_inventory(reference)
        if shadow_parent.exists():
            raise ProjectRuntimeError("project_runtime_reference_cleanup_unverified")
        if reference_verification.get("pip_check") is not True:
            raise ProjectRuntimeError("project_runtime_reference_pip_check_unproven")
        return inventory, reference_verification
    except BaseException as error:
        if shadow_parent is not None and shadow_parent.exists():
            raise RuntimeReferenceCleanupError(shadow_parent) from error
        if isinstance(error, ProjectRuntimeError):
            raise
        raise ProjectRuntimeError("project_runtime_reference_failed") from error


def _remove_owned_install_tree(
    project_root: Path,
    path: Path,
    *,
    installing_marker: bytes,
    receipt_bytes: bytes | None,
) -> bool:
    if not path.exists():
        return True
    if not _existing_components_are_real(project_root, path) or not path.is_dir():
        return False
    marker_matches = (
        _read_limited(path / PROJECT_RUNTIME_INSTALLING_NAME, limit=64 * 1024)
        == installing_marker
    )
    receipt_matches = bool(
        receipt_bytes is not None
        and _read_limited(path / PROJECT_RUNTIME_RECEIPT_NAME, limit=2 * 1024 * 1024)
        == receipt_bytes
    )
    if not marker_matches and not receipt_matches:
        return False
    try:
        shutil.rmtree(path)
    except OSError:
        return False
    return not path.exists()


def _remove_exact_created_tree(
    project_root: Path,
    path: Path,
    identity: tuple[int, int] | None,
) -> bool:
    if not path.exists():
        return True
    try:
        stat_result = path.lstat()
        if (
            identity is None
            or (int(stat_result.st_dev), int(stat_result.st_ino)) != identity
            or not path.name.startswith(".v")
            or not _existing_components_are_real(project_root, path)
            or not path.is_dir()
            or path.is_symlink()
        ):
            return False
        _walk_regular_files(path)
        shutil.rmtree(path)
    except (OSError, ProjectRuntimeError):
        return False
    return not path.exists()


def materialize_runtime(
    project_root: Path,
    *,
    target: str,
    target_commit: str,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    prepared_bundle: PreparedRuntimeBundle,
    mutation_tracker: RuntimeMutationTracker,
    running_version: str,
    progress_callback: Callable[[str, str, int | None, int | None], None] | None = None,
) -> RuntimeMaterialization:
    version = _version(target)
    parsed_supply = project_runtime_supply_lock(
        supply.raw_bytes,
        expected_target=target,
    )
    if (
        version is None
        or bootstrap.version != version
        or bootstrap.tag != f"v{version}"
        or COMMIT_RE.fullmatch(target_commit) is None
        or parsed_supply != supply
        or supply.target_tag != f"v{version}"
    ):
        raise ProjectRuntimeError("project_runtime_materialization_binding_invalid")
    if not runtime_supply_matches_current_interpreter(supply):
        raise ProjectRuntimeError("project_runtime_interpreter_not_locked")
    tracker = mutation_tracker
    if not isinstance(tracker, RuntimeMutationTracker):
        raise ProjectRuntimeError("project_runtime_mutation_tracker_required")
    if (
        tracker.before is not None
        or tracker.started
        or tracker.completed
        or tracker.cleanup_verified is not None
    ):
        raise ProjectRuntimeError("project_runtime_mutation_tracker_not_pristine")
    verify_prepared_runtime_bundle(
        prepared_bundle,
        target=target,
        target_commit=target_commit,
        bootstrap=bootstrap,
        supply=supply,
    )
    final = runtime_path(project_root, version)
    logical = runtime_logical_path(version)
    existing = inspect_runtime(
        project_root,
        version,
        expected_commit=target_commit,
        expected_wheel_sha256=bootstrap.sha256,
        expected_supply_lock_sha256=supply.sha256,
    )
    if existing.get("receipt_candidate_valid"):
        receipt_bytes = _read_limited(final / PROJECT_RUNTIME_RECEIPT_NAME, limit=2 * 1024 * 1024)
        if receipt_bytes is None:
            raise ProjectRuntimeError("project_runtime_existing_receipt_unreadable")
        try:
            receipt = json.loads(receipt_bytes.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ProjectRuntimeError("project_runtime_existing_receipt_unreadable") from error
        if not isinstance(receipt, dict):
            raise ProjectRuntimeError("project_runtime_existing_receipt_unreadable")
        artifact_inventory, retained_wheels, _artifact_top_level = _verify_retained_artifacts(
            final,
            bootstrap=bootstrap,
            supply=supply,
            receipt_inventory=receipt.get("artifact_inventory"),
        )
        installed_payload_sha256 = _runtime_payload_sha256(final)
        if receipt.get("installed_payload_sha256") != (
            "sha256:" + installed_payload_sha256
        ):
            raise ProjectRuntimeError("project_runtime_existing_payload_mismatch")
        reference_inventory, reference_verification = _reference_payload_inventory(
            prepared_bundle,
            bootstrap=bootstrap,
            supply=supply,
            progress_callback=progress_callback,
        )
        verify_prepared_runtime_bundle(
            prepared_bundle,
            target=target,
            target_commit=target_commit,
            bootstrap=bootstrap,
            supply=supply,
        )
        existing_inventory = _normalized_runtime_payload_inventory(final)
        if existing_inventory != reference_inventory:
            raise ProjectRuntimeError("project_runtime_existing_shadow_mismatch")
        verification, packages, python_version = _runtime_process_verification(
            final,
            version=version,
            stage_prefix="project-runtime-reuse",
            progress_callback=progress_callback,
            bootstrap=bootstrap,
            supply=supply,
            retained_wheels=retained_wheels,
            reuse_isolated=True,
            pip_check_proven=reference_verification.get("pip_check"),
            expected_receipt_packages=receipt.get("installed_distributions"),
            expected_python_version=receipt.get("python_version"),
        )
        if packages != receipt.get("installed_distributions"):
            raise ProjectRuntimeError("project_runtime_package_inventory_mismatch")
        payload_after = _runtime_payload_sha256(final)
        if payload_after != installed_payload_sha256:
            raise ProjectRuntimeError("project_runtime_existing_payload_changed")
        return RuntimeMaterialization(
            target_tag=f"v{version}",
            target_version=version,
            target_commit=target_commit,
            final_path=final,
            logical_path=logical,
            receipt_bytes=receipt_bytes,
            receipt_sha256=_sha256_bytes(receipt_bytes),
            wheel_sha256=bootstrap.sha256,
            supply_lock_sha256=supply.sha256,
            artifact_inventory=artifact_inventory,
            installed_payload_sha256=installed_payload_sha256,
            python_version=python_version,
            created=False,
            verification=verification,
        )
    if final.exists():
        raise ProjectRuntimeError("project_runtime_target_directory_invalid")
    runtimes_root = project_root / PROJECT_RUNTIME_RELATIVE_ROOT
    before = runtime_root_snapshot(project_root)
    if not before.valid:
        raise ProjectRuntimeError("project_runtime_root_snapshot_unavailable")
    tracker.before = before
    tracker.started = True
    tracker.cleanup_verified = False
    staging: Path | None = None
    staging_identity: tuple[int, int] | None = None
    receipt_bytes: bytes | None = None
    final_created = False
    installing_marker = (
        json.dumps(
            {
                "schema": "wom-kit/project-runtime-installing/v0.1",
                "target_tag": f"v{version}",
                "target_commit": target_commit,
                "wheel_sha256": f"sha256:{bootstrap.sha256}",
                "ownership_nonce": secrets.token_hex(16),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    try:
        if not _existing_components_are_real(project_root, runtimes_root):
            raise ProjectRuntimeError("project_runtime_root_unsafe")
        runtimes_root.mkdir(parents=True, exist_ok=True)
        if not _existing_components_are_real(project_root, runtimes_root):
            raise ProjectRuntimeError("project_runtime_root_unsafe")
        staging = Path(tempfile.mkdtemp(prefix=f".v{version}-", dir=runtimes_root))
        staging_stat = staging.lstat()
        staging_identity = (int(staging_stat.st_dev), int(staging_stat.st_ino))
        (staging / PROJECT_RUNTIME_INSTALLING_NAME).write_bytes(installing_marker)
        artifacts_root = staging / PROJECT_RUNTIME_ARTIFACTS_NAME
        artifacts_root.mkdir()
        copy_names = {
            PROJECT_RUNTIME_RETAINED_LOCK_NAME,
            bootstrap.file_name,
            *(artifact.file_name for artifact in supply.artifacts),
        }
        for file_name in sorted(copy_names, key=str.casefold):
            shutil.copyfile(
                prepared_bundle.root / file_name,
                artifacts_root / file_name,
            )
        artifact_inventory = [dict(item) for item in prepared_bundle.artifact_inventory]
        wheel_paths = [
            artifacts_root / bootstrap.file_name,
            *(artifacts_root / artifact.file_name for artifact in supply.artifacts),
        ]
        for item in artifact_inventory:
            digest, size = _sha256_file(
                artifacts_root / str(item["file_name"]),
                limit=128 * 1024 * 1024,
            )
            if (
                size != item["size_bytes"]
                or f"sha256:{digest}" != item["sha256"]
            ):
                raise ProjectRuntimeError("project_runtime_local_bundle_copy_mismatch")
        verification, packages, python_version = _initialize_runtime_payload(
            staging,
            wheelhouse=artifacts_root,
            wheel_paths=wheel_paths,
            bootstrap=bootstrap,
            supply=supply,
            stage_prefix="project-runtime-stage",
            progress_callback=progress_callback,
        )
        _stage_inventory, _stage_wheels, _stage_top_level = _verify_retained_artifacts(
            staging,
            bootstrap=bootstrap,
            supply=supply,
            receipt_inventory=artifact_inventory,
        )
        os.replace(staging, final)
        final_created = True
        canonical_inventory, retained_wheels, _final_top_level = _verify_retained_artifacts(
            final,
            bootstrap=bootstrap,
            supply=supply,
            receipt_inventory=artifact_inventory,
        )
        verification, packages, python_version = _runtime_process_verification(
            final,
            version=version,
            stage_prefix="project-runtime-final",
            progress_callback=progress_callback,
            bootstrap=bootstrap,
            supply=supply,
            retained_wheels=retained_wheels,
        )
        installed_payload_sha256 = _runtime_payload_sha256(final)
        receipt = {
            "schema": PROJECT_RUNTIME_RECEIPT_SCHEMA,
            "status": "verified",
            "created_at": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "target_tag": f"v{version}",
            "target_version": version,
            "target_commit": target_commit,
            "wheel_file_name": bootstrap.file_name,
            "wheel_sha256": f"sha256:{bootstrap.sha256}",
            "supply_lock_sha256": f"sha256:{supply.sha256}",
            "artifact_inventory": [dict(item) for item in canonical_inventory],
            "installed_payload_sha256": f"sha256:{installed_payload_sha256}",
            "python_version": python_version,
            "installer_running_version": running_version,
            "installed_distributions": packages,
            "verification": verification,
            "global_path_mutation": False,
            "previous_runtime_deleted": False,
            "absolute_paths_echoed": False,
        }
        if validate_schema(receipt, "project-runtime-receipt-v0.1.schema.json"):
            raise ProjectRuntimeError("project_runtime_receipt_schema_invalid")
        receipt_bytes = (
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        receipt_temporary = final / (PROJECT_RUNTIME_RECEIPT_NAME + ".tmp")
        with receipt_temporary.open("xb") as handle:
            handle.write(receipt_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(
            receipt_temporary,
            final / PROJECT_RUNTIME_RECEIPT_NAME,
        )
        verified = inspect_runtime(
            project_root,
            version,
            expected_commit=target_commit,
            expected_wheel_sha256=bootstrap.sha256,
            expected_supply_lock_sha256=supply.sha256,
        )
        if not verified.get("receipt_candidate_valid"):
            raise ProjectRuntimeError("project_runtime_final_verification_failed")
        (final / PROJECT_RUNTIME_INSTALLING_NAME).unlink()
        verified_without_marker = inspect_runtime(
            project_root,
            version,
            expected_commit=target_commit,
            expected_wheel_sha256=bootstrap.sha256,
            expected_supply_lock_sha256=supply.sha256,
        )
        if not verified_without_marker.get("receipt_candidate_valid"):
            raise ProjectRuntimeError("project_runtime_final_verification_failed")
        tracker.completed = True
        tracker.cleanup_verified = None
        return RuntimeMaterialization(
            target_tag=f"v{version}",
            target_version=version,
            target_commit=target_commit,
            final_path=final,
            logical_path=logical,
            receipt_bytes=receipt_bytes,
            receipt_sha256=_sha256_bytes(receipt_bytes),
            wheel_sha256=bootstrap.sha256,
            supply_lock_sha256=supply.sha256,
            artifact_inventory=canonical_inventory,
            installed_payload_sha256=installed_payload_sha256,
            python_version=python_version,
            created=True,
            verification=verification,
        )
    except BaseException as error:
        cleanup_ok = True
        if staging is not None:
            if _read_limited(
                staging / PROJECT_RUNTIME_INSTALLING_NAME,
                limit=64 * 1024,
            ) == installing_marker:
                cleanup_ok = _remove_owned_install_tree(
                    project_root,
                    staging,
                    installing_marker=installing_marker,
                    receipt_bytes=receipt_bytes,
                ) and cleanup_ok
            else:
                cleanup_ok = _remove_exact_created_tree(
                    project_root,
                    staging,
                    staging_identity,
                ) and cleanup_ok
        if final_created:
            cleanup_ok = _remove_owned_install_tree(
                project_root,
                final,
                installing_marker=installing_marker,
                receipt_bytes=receipt_bytes,
            ) and cleanup_ok
        _remove_new_empty_runtime_root(project_root, tracker)
        restored = runtime_mutation_restored(project_root, tracker)
        if not cleanup_ok or not restored:
            raise ProjectRuntimeError(
                "project_runtime_materialization_cleanup_unverified"
            ) from error
        raise


def remove_materialized_runtime(
    project_root: Path,
    runtime: RuntimeMaterialization,
    *,
    mutation_tracker: RuntimeMutationTracker | None = None,
) -> bool:
    if not runtime.created:
        return True
    final = runtime.final_path
    if final != runtime_path(project_root, runtime.target_version):
        return False
    receipt_path = final / PROJECT_RUNTIME_RECEIPT_NAME
    receipt_bytes = _read_limited(receipt_path, limit=2 * 1024 * 1024)
    if (
        not _existing_components_are_real(project_root, receipt_path)
        or receipt_bytes != runtime.receipt_bytes
        or _sha256_bytes(receipt_bytes or b"") != runtime.receipt_sha256
    ):
        return False
    try:
        shutil.rmtree(final)
    except OSError:
        return False
    if final.exists():
        return False
    if mutation_tracker is not None:
        _remove_new_empty_runtime_root(project_root, mutation_tracker)
        return runtime_mutation_restored(project_root, mutation_tracker)
    return True


# ---------------------------------------------------------------------------
# v0.4.3 complete pre-approval runtime candidate
# ---------------------------------------------------------------------------


def _lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _path_identity(path: Path) -> tuple[int, int]:
    try:
        stat_result = path.lstat()
    except OSError as error:
        raise ProjectRuntimeError("project_runtime_candidate_path_unreadable") from error
    return int(stat_result.st_dev), int(stat_result.st_ino)


def _is_reparse(stat_result: os.stat_result) -> bool:
    return bool(getattr(stat_result, "st_file_attributes", 0) & 0x400)


def _file_link_count(path: Path, stat_result: os.stat_result) -> int:
    """Return the real hard-link count (Windows stat may report zero)."""

    if os.name != "nt":
        return int(stat_result.st_nlink)
    import ctypes
    from ctypes import wintypes

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel32.CreateFileW
    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create.restype = wintypes.HANDLE
    get_info = kernel32.GetFileInformationByHandle
    get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ByHandleFileInformation)]
    get_info.restype = wintypes.BOOL
    close = kernel32.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    handle = create(
        str(path),
        0,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x02000000,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ProjectRuntimeError("project_runtime_candidate_unreadable")
    try:
        information = _ByHandleFileInformation()
        if not get_info(handle, ctypes.byref(information)):
            raise ProjectRuntimeError("project_runtime_candidate_unreadable")
        return int(information.nNumberOfLinks)
    finally:
        close(handle)


def _candidate_inventory_snapshot(
    root: Path,
) -> tuple[RuntimeCandidateInventoryEntry, ...]:
    """Return an exact, non-following recursive snapshot of one candidate."""

    try:
        root_stat = root.lstat()
        if (
            root.is_symlink()
            or _is_reparse(root_stat)
            or not root.is_dir()
        ):
            raise ProjectRuntimeError("project_runtime_candidate_unsafe")
    except OSError as error:
        raise ProjectRuntimeError("project_runtime_candidate_unreadable") from error

    result: list[RuntimeCandidateInventoryEntry] = []
    seen: set[str] = set()

    def visit(directory: Path, prefix: PurePosixPath) -> None:
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(
                    iterator,
                    key=lambda item: (item.name.casefold(), item.name),
                )
        except OSError as error:
            raise ProjectRuntimeError("project_runtime_candidate_unreadable") from error
        for entry in entries:
            try:
                stat_result = Path(entry.path).lstat()
            except OSError as error:
                raise ProjectRuntimeError("project_runtime_candidate_unreadable") from error
            relative = (prefix / entry.name).as_posix()
            folded = relative.casefold()
            if (
                folded in seen
                or entry.is_symlink()
                or _is_reparse(stat_result)
            ):
                raise ProjectRuntimeError("project_runtime_candidate_unsafe")
            seen.add(folded)
            if entry.is_dir(follow_symlinks=False):
                result.append(
                    RuntimeCandidateInventoryEntry(
                        relative_path=relative,
                        entry_type="directory",
                        device=int(stat_result.st_dev),
                        inode=int(stat_result.st_ino),
                        nlink=int(stat_result.st_nlink),
                        # Directory size/mtime are filesystem bookkeeping, not
                        # runtime bytes.  Child identities and the complete
                        # recursive name set bind directory contents.
                        size_bytes=0,
                        mtime_ns=0,
                        sha256=None,
                    )
                )
                visit(Path(entry.path), prefix / entry.name)
            elif entry.is_file(follow_symlinks=False):
                link_count = _file_link_count(Path(entry.path), stat_result)
                if link_count != 1:
                    raise ProjectRuntimeError("project_runtime_candidate_hardlink_unsafe")
                digest, size = _sha256_file(
                    Path(entry.path),
                    limit=1024 * 1024 * 1024,
                )
                # Re-observe metadata after hashing so a concurrent replacement
                # cannot be silently sealed.
                after = Path(entry.path).lstat()
                if (
                    _is_reparse(after)
                    or Path(entry.path).is_symlink()
                    or not Path(entry.path).is_file()
                    or int(after.st_dev) != int(stat_result.st_dev)
                    or int(after.st_ino) != int(stat_result.st_ino)
                    or _file_link_count(Path(entry.path), after) != 1
                    or int(after.st_size) != size
                    or int(after.st_mtime_ns) != int(stat_result.st_mtime_ns)
                ):
                    raise ProjectRuntimeError("project_runtime_candidate_concurrent_drift")
                result.append(
                    RuntimeCandidateInventoryEntry(
                        relative_path=relative,
                        entry_type="file",
                        device=int(after.st_dev),
                        inode=int(after.st_ino),
                        nlink=1,
                        size_bytes=size,
                        mtime_ns=int(after.st_mtime_ns),
                        sha256=digest,
                    )
                )
            else:
                raise ProjectRuntimeError("project_runtime_candidate_unsafe")

    visit(root, PurePosixPath())
    return tuple(result)


def _detach_candidate_hardlinks(root: Path) -> None:
    """Give every candidate file a private inode before sealing it."""

    def visit(directory: Path) -> None:
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda item: (item.name.casefold(), item.name))
        except OSError as error:
            raise ProjectRuntimeError("project_runtime_candidate_unreadable") from error
        for entry in entries:
            path = Path(entry.path)
            stat_result = entry.stat(follow_symlinks=False)
            if entry.is_symlink() or _is_reparse(stat_result):
                raise ProjectRuntimeError("project_runtime_candidate_unsafe")
            if entry.is_dir(follow_symlinks=False):
                visit(path)
                continue
            if not entry.is_file(follow_symlinks=False):
                raise ProjectRuntimeError("project_runtime_candidate_unsafe")
            if _file_link_count(path, stat_result) == 1:
                continue
            temporary = path.with_name(path.name + ".wom-private-copy")
            if _lexists(temporary):
                raise ProjectRuntimeError("project_runtime_candidate_detach_collision")
            try:
                with path.open("rb") as source, temporary.open("xb") as destination:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
                    destination.flush()
                    os.fsync(destination.fileno())
                os.chmod(temporary, stat_result.st_mode)
                os.replace(temporary, path)
            except OSError as error:
                raise ProjectRuntimeError("project_runtime_candidate_detach_failed") from error
            detached = path.lstat()
            if _file_link_count(path, detached) != 1 or _is_reparse(detached):
                raise ProjectRuntimeError("project_runtime_candidate_detach_failed")

    visit(root)


def _candidate_binding_digest(
    *,
    target_tag: str,
    target_commit: str,
    transaction_ref: str,
    logical_candidate_path: str,
    wheel_file_name: str,
    wheel_sha256: str,
    supply_lock_sha256: str,
    receipt_sha256: str,
    installed_payload_sha256: str,
    normalized_payload_inventory: tuple[tuple[str, int, str], ...],
    existing_runtime_reusable: bool,
    runtime_parent_existed_before: bool,
    inventory: tuple[RuntimeCandidateInventoryEntry, ...],
) -> str:
    binding = {
        "schema": PROJECT_RUNTIME_CANDIDATE_SCHEMA,
        "target_tag": target_tag,
        "target_commit": target_commit,
        "transaction_ref": transaction_ref,
        "candidate_locator": logical_candidate_path,
        "wheel_file_name": wheel_file_name,
        "wheel_sha256": f"sha256:{wheel_sha256}",
        "supply_lock_sha256": f"sha256:{supply_lock_sha256}",
        "receipt_sha256": f"sha256:{receipt_sha256}",
        "installed_payload_sha256": f"sha256:{installed_payload_sha256}",
        "normalized_payload_inventory": [
            {"path": path, "size_bytes": size, "sha256": f"sha256:{digest}"}
            for path, size, digest in normalized_payload_inventory
        ],
        "existing_runtime_reusable": existing_runtime_reusable,
        "runtime_parent_existed_before": runtime_parent_existed_before,
        "inventory": [entry.binding_summary() for entry in inventory],
        "marker_free_final_postimage": True,
        "post_approval_child_process_allowed": False,
        "post_approval_network_allowed": False,
        "post_approval_copy_allowed": False,
    }
    return _sha256_bytes(
        (json.dumps(binding, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
    )


def _recursive_candidate_inventory_digest(
    inventory: tuple[RuntimeCandidateInventoryEntry, ...],
) -> str:
    return _sha256_bytes(
        (
            json.dumps(
                [entry.binding_summary() for entry in inventory],
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    )


def _strict_candidate_timestamp(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
        value,
    ) is None:
        raise ProjectRuntimeError("project_runtime_candidate_timestamp_invalid")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise ProjectRuntimeError("project_runtime_candidate_timestamp_invalid") from error
    if parsed.tzinfo != timezone.utc or parsed.microsecond != 0:
        raise ProjectRuntimeError("project_runtime_candidate_timestamp_invalid")
    return value


def _candidate_paths(
    project_root: Path,
    transaction_root: Path,
) -> tuple[Path, Path, str, str, str]:
    project = Path(os.path.abspath(str(project_root)))
    transaction = Path(os.path.abspath(str(transaction_root)))
    expected_parent = project / PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
    try:
        relative = transaction.relative_to(expected_parent)
    except ValueError as error:
        raise ProjectRuntimeError("project_runtime_transaction_root_invalid") from error
    if (
        len(relative.parts) != 1
        or PROJECT_RUNTIME_TRANSACTION_REF_RE.fullmatch(relative.parts[0]) is None
        or not project.is_dir()
        or not transaction.is_dir()
        or not _existing_components_are_real(project, transaction)
    ):
        raise ProjectRuntimeError("project_runtime_transaction_root_invalid")
    candidate = transaction / PROJECT_RUNTIME_CANDIDATE_NAME
    seal = transaction / PROJECT_RUNTIME_CANDIDATE_SEAL_NAME
    logical_candidate = candidate.relative_to(project).as_posix()
    logical_seal = seal.relative_to(project).as_posix()
    return project, transaction, relative.parts[0], logical_candidate, logical_seal


def _write_exact_new_file(path: Path, data: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as error:
        raise ProjectRuntimeError("project_runtime_candidate_write_failed") from error


def _flush_directory_durable(path: Path) -> None:
    """Fail-closed durability barrier for one real directory entry set."""

    try:
        stat_result = path.lstat()
        if path.is_symlink() or _is_reparse(stat_result) or not path.is_dir():
            raise ProjectRuntimeError("project_runtime_directory_durability_failed")
    except OSError as error:
        raise ProjectRuntimeError(
            "project_runtime_directory_durability_failed"
        ) from error
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create = kernel32.CreateFileW
        create.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create.restype = wintypes.HANDLE
        flush = kernel32.FlushFileBuffers
        flush.argtypes = [wintypes.HANDLE]
        flush.restype = wintypes.BOOL
        close = kernel32.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        handle = create(
            str(path),
            0x40000000,  # GENERIC_WRITE, required by FlushFileBuffers
            0x00000001 | 0x00000002 | 0x00000004,
            None,
            3,  # OPEN_EXISTING
            0x02000000 | 0x80000000,  # BACKUP_SEMANTICS | WRITE_THROUGH
            None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise ProjectRuntimeError("project_runtime_directory_durability_failed")
        flush_ok = False
        close_ok = False
        try:
            flush_ok = bool(flush(handle))
        finally:
            close_ok = bool(close(handle))
        if not flush_ok or not close_ok:
            raise ProjectRuntimeError("project_runtime_directory_durability_failed")
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise ProjectRuntimeError(
            "project_runtime_directory_durability_failed"
        ) from error


def _flush_candidate_tree_durable(
    root: Path,
    inventory: tuple[RuntimeCandidateInventoryEntry, ...],
) -> None:
    """Flush every candidate directory deepest-first and prove no drift."""

    if _candidate_inventory_snapshot(root) != inventory:
        raise ProjectRuntimeError("project_runtime_candidate_durability_drift")
    directories = [item for item in inventory if item.entry_type == "directory"]
    for item in sorted(
        directories,
        key=lambda value: (value.relative_path.count("/"), value.relative_path),
        reverse=True,
    ):
        _flush_directory_durable(root / PurePosixPath(item.relative_path))
    _flush_directory_durable(root)
    if _candidate_inventory_snapshot(root) != inventory:
        raise ProjectRuntimeError("project_runtime_candidate_durability_drift")


def _candidate_receipt_document(data: bytes) -> dict[str, Any]:
    try:
        document = _json_without_duplicate_keys(data)
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise ProjectRuntimeError("project_runtime_candidate_receipt_invalid") from error
    if (
        not isinstance(document, dict)
        or validate_schema(document, "project-runtime-receipt-v0.1.schema.json")
    ):
        raise ProjectRuntimeError("project_runtime_candidate_receipt_invalid")
    return document


def _existing_runtime_matches_candidate(
    project_root: Path,
    candidate: PreparedRuntimeCandidate,
) -> bool:
    """Static-only exact comparison used both before and after approval."""

    final = runtime_path(project_root, candidate.target_version)
    if (
        not final.is_dir()
        or not _existing_components_are_real(project_root, final)
        or _lexists(final / PROJECT_RUNTIME_INSTALLING_NAME)
    ):
        return False
    receipt_bytes = _read_limited(
        final / PROJECT_RUNTIME_RECEIPT_NAME,
        limit=2 * 1024 * 1024,
    )
    if receipt_bytes is None:
        return False
    try:
        receipt = _candidate_receipt_document(receipt_bytes)
        if (
            receipt.get("target_tag") != candidate.target_tag
            or receipt.get("target_version") != candidate.target_version
            or receipt.get("target_commit") != candidate.target_commit
            or receipt.get("wheel_sha256") != f"sha256:{candidate.wheel_sha256}"
            or receipt.get("supply_lock_sha256")
            != f"sha256:{candidate.supply_lock_sha256}"
            or receipt.get("installed_payload_sha256")
            != f"sha256:{candidate.installed_payload_sha256}"
            or receipt.get("python_version") != candidate.python_version
            or tuple(receipt.get("installed_distributions", ()))
            != candidate.installed_distributions
            or receipt.get("verification") != dict(candidate.verification)
        ):
            return False
        parsed_supply = project_runtime_supply_lock(
            candidate.supply_lock_bytes,
            expected_target=candidate.target_tag,
        )
        if parsed_supply is None or parsed_supply.sha256 != candidate.supply_lock_sha256:
            return False
        artifact_inventory, _retained, _top = _verify_retained_artifacts(
            final,
            bootstrap=BootstrapWheel(
                version=candidate.target_version,
                tag=candidate.target_tag,
                url="https://invalid.example/never-used",
                sha256=candidate.wheel_sha256,
                file_name=candidate.wheel_file_name,
            ),
            supply=parsed_supply,
            receipt_inventory=receipt.get("artifact_inventory"),
        )
    except (ProjectRuntimeError, TypeError):
        return False
    # The parsed supply must exist; the helper above intentionally accepts no
    # receipt as authority for artifact bytes.
    if tuple(dict(item) for item in artifact_inventory) != tuple(
        dict(item) for item in candidate.artifact_inventory
    ):
        return False
    try:
        return (
            _runtime_payload_sha256(final) == candidate.installed_payload_sha256
            and _normalized_runtime_payload_inventory(final)
            == candidate.normalized_payload_inventory
        )
    except ProjectRuntimeError:
        return False


def prepare_runtime_candidate(
    project_root: Path,
    transaction_root: Path,
    *,
    target: str,
    target_commit: str,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    running_version: str,
    receipt_created_at: str,
    progress_callback: Callable[[str, str, int | None, int | None], None] | None = None,
) -> PreparedRuntimeCandidate:
    """Build, execute, verify, and seal the complete runtime before approval."""

    version = _version(target)
    parsed_supply = project_runtime_supply_lock(supply.raw_bytes, expected_target=target)
    created_at = _strict_candidate_timestamp(receipt_created_at)
    if (
        version is None
        or bootstrap.version != version
        or bootstrap.tag != f"v{version}"
        or COMMIT_RE.fullmatch(target_commit) is None
        or parsed_supply != supply
        or supply.target_tag != f"v{version}"
        or not runtime_supply_matches_current_interpreter(supply)
        or _version(running_version) is None
    ):
        raise ProjectRuntimeError("project_runtime_candidate_binding_invalid")
    project, transaction, transaction_ref, logical_candidate, logical_seal = (
        _candidate_paths(project_root, transaction_root)
    )
    candidate_root = transaction / PROJECT_RUNTIME_CANDIDATE_NAME
    seal_path = transaction / PROJECT_RUNTIME_CANDIDATE_SEAL_NAME
    if _lexists(candidate_root) or _lexists(seal_path):
        raise ProjectRuntimeError("project_runtime_candidate_already_exists")

    runtimes_root = project / PROJECT_RUNTIME_RELATIVE_ROOT
    runtime_parent_existed_before = _lexists(runtimes_root)
    mutated = False
    try:
        runtimes_root.mkdir(parents=True, exist_ok=True)
        if not _existing_components_are_real(project, runtimes_root):
            raise ProjectRuntimeError("project_runtime_root_unsafe")
        candidate_root.mkdir()
        mutated = True
        artifacts_root = candidate_root / PROJECT_RUNTIME_ARTIFACTS_NAME
        artifacts_root.mkdir()
        _write_exact_new_file(
            artifacts_root / PROJECT_RUNTIME_RETAINED_LOCK_NAME,
            supply.raw_bytes,
        )
        main_path = artifacts_root / bootstrap.file_name
        main_size = _download_exact_artifact(
            url=bootstrap.url,
            expected_sha256=bootstrap.sha256,
            expected_size=None,
            destination=main_path,
            callback=progress_callback,
            stage="project-runtime-candidate-wheel",
            source_kind="github_release",
        )
        for index, artifact in enumerate(supply.artifacts, start=1):
            _download_exact_artifact(
                url=artifact.url,
                expected_sha256=artifact.sha256,
                expected_size=artifact.size_bytes,
                destination=artifacts_root / artifact.file_name,
                callback=progress_callback,
                stage=f"project-runtime-candidate-dependency-{index}",
                source_kind="pypi_file",
            )
        artifact_inventory = _expected_bundle_inventory(
            bootstrap=bootstrap,
            supply=supply,
            main_size=main_size,
        )
        wheel_paths = [
            artifacts_root / bootstrap.file_name,
            *(artifacts_root / artifact.file_name for artifact in supply.artifacts),
        ]
        verification, packages, python_version = _initialize_runtime_payload(
            candidate_root,
            wheelhouse=artifacts_root,
            wheel_paths=wheel_paths,
            bootstrap=bootstrap,
            supply=supply,
            stage_prefix="project-runtime-candidate",
            progress_callback=progress_callback,
        )
        _detach_candidate_hardlinks(candidate_root)
        canonical_inventory, _retained, _top = _verify_retained_artifacts(
            candidate_root,
            bootstrap=bootstrap,
            supply=supply,
            receipt_inventory=[dict(item) for item in artifact_inventory],
        )
        installed_payload_sha256 = _runtime_payload_sha256(candidate_root)
        normalized_payload_inventory = _normalized_runtime_payload_inventory(
            candidate_root
        )
        receipt = {
            "schema": PROJECT_RUNTIME_RECEIPT_SCHEMA,
            "status": "verified",
            "created_at": created_at,
            "target_tag": f"v{version}",
            "target_version": version,
            "target_commit": target_commit,
            "wheel_file_name": bootstrap.file_name,
            "wheel_sha256": f"sha256:{bootstrap.sha256}",
            "supply_lock_sha256": f"sha256:{supply.sha256}",
            "artifact_inventory": [dict(item) for item in canonical_inventory],
            "installed_payload_sha256": f"sha256:{installed_payload_sha256}",
            "python_version": python_version,
            "installer_running_version": running_version,
            "installed_distributions": packages,
            "verification": verification,
            "global_path_mutation": False,
            "previous_runtime_deleted": False,
            "absolute_paths_echoed": False,
        }
        if validate_schema(receipt, "project-runtime-receipt-v0.1.schema.json"):
            raise ProjectRuntimeError("project_runtime_receipt_schema_invalid")
        receipt_bytes = (
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        _write_exact_new_file(
            candidate_root / PROJECT_RUNTIME_RECEIPT_NAME,
            receipt_bytes,
        )
        # The receipt write is the final pre-seal mutation.  Re-run private
        # inode detachment at this exact boundary before recursive sealing.
        _detach_candidate_hardlinks(candidate_root)
        inventory = _candidate_inventory_snapshot(candidate_root)
        candidate_identity = _path_identity(candidate_root)
        project_identity = _path_identity(project)
        transaction_identity = _path_identity(transaction)
        runtime_parent_identity = _path_identity(runtimes_root)
        if (
            candidate_identity[0] != runtime_parent_identity[0]
            or transaction_identity[0] != runtime_parent_identity[0]
            or project_identity[0] != runtime_parent_identity[0]
        ):
            raise ProjectRuntimeError("project_runtime_candidate_cross_volume")

        # Existing runtime reuse is decided now, while child/toolchain work is
        # still permitted.  Promotion will only repeat this static comparison.
        provisional = PreparedRuntimeCandidate(
            target_tag=f"v{version}",
            target_version=version,
            target_commit=target_commit,
            transaction_ref=transaction_ref,
            logical_candidate_path=logical_candidate,
            logical_seal_path=logical_seal,
            project_root=project,
            transaction_root=transaction,
            candidate_root=candidate_root,
            seal_path=seal_path,
            project_root_identity=project_identity,
            transaction_root_identity=transaction_identity,
            candidate_root_identity=candidate_identity,
            runtime_parent_identity=runtime_parent_identity,
            runtime_parent_existed_before=runtime_parent_existed_before,
            runtime_parent_created_identity=(
                None if runtime_parent_existed_before else runtime_parent_identity
            ),
            same_volume_identity=candidate_identity[0],
            inventory=inventory,
            inventory_sha256="0" * 64,
            candidate_sha256="0" * 64,
            inventory_count=len(inventory),
            inventory_bytes=sum(
                item.size_bytes for item in inventory if item.entry_type == "file"
            ),
            seal_bytes=b"",
            seal_sha256="0" * 64,
            receipt_bytes=receipt_bytes,
            receipt_sha256=_sha256_bytes(receipt_bytes),
            wheel_file_name=bootstrap.file_name,
            wheel_sha256=bootstrap.sha256,
            supply_lock_sha256=supply.sha256,
            supply_lock_bytes=supply.raw_bytes,
            artifact_inventory=canonical_inventory,
            installed_payload_sha256=installed_payload_sha256,
            normalized_payload_inventory=normalized_payload_inventory,
            python_version=python_version,
            installed_distributions=tuple(dict(item) for item in packages),
            verification=dict(verification),
            existing_runtime_reusable=False,
        )
        final = runtime_path(project, version)
        existing_runtime_reusable = False
        if _lexists(final):
            existing_runtime_reusable = _existing_runtime_matches_candidate(
                project,
                provisional,
            )
            if not existing_runtime_reusable:
                raise ProjectRuntimeError("project_runtime_target_directory_invalid")
        inventory_sha256 = _recursive_candidate_inventory_digest(inventory)
        candidate_sha256 = _candidate_binding_digest(
            target_tag=f"v{version}",
            target_commit=target_commit,
            transaction_ref=transaction_ref,
            logical_candidate_path=logical_candidate,
            wheel_file_name=bootstrap.file_name,
            wheel_sha256=bootstrap.sha256,
            supply_lock_sha256=supply.sha256,
            receipt_sha256=_sha256_bytes(receipt_bytes),
            installed_payload_sha256=installed_payload_sha256,
            normalized_payload_inventory=normalized_payload_inventory,
            existing_runtime_reusable=existing_runtime_reusable,
            runtime_parent_existed_before=runtime_parent_existed_before,
            inventory=inventory,
        )
        # The candidate is not publishable until every subprocess-created
        # directory entry is behind a durability barrier.  The transaction
        # parent flush binds the candidate-root entry itself.
        _flush_candidate_tree_durable(candidate_root, inventory)
        _flush_directory_durable(transaction)
        seal = {
            "schema": PROJECT_RUNTIME_CANDIDATE_SCHEMA,
            "status": "sealed",
            "target_tag": f"v{version}",
            "target_commit": target_commit,
            "transaction_ref": transaction_ref,
            "candidate_locator": logical_candidate,
            "inventory_sha256": f"sha256:{inventory_sha256}",
            "candidate_sha256": f"sha256:{candidate_sha256}",
            "inventory_count": len(inventory),
            "inventory_bytes": sum(
                item.size_bytes for item in inventory if item.entry_type == "file"
            ),
            "receipt_sha256": f"sha256:{_sha256_bytes(receipt_bytes)}",
            "wheel_file_name": bootstrap.file_name,
            "wheel_sha256": f"sha256:{bootstrap.sha256}",
            "supply_lock_sha256": f"sha256:{supply.sha256}",
            "same_volume_verified": True,
            "existing_runtime_reusable": existing_runtime_reusable,
            "runtime_parent_existed_before": runtime_parent_existed_before,
            "path_identities": {
                "project_root": list(project_identity),
                "transaction_root": list(transaction_identity),
                "candidate_root": list(candidate_identity),
                "runtime_parent": list(runtime_parent_identity),
                "runtime_parent_created": (
                    None
                    if runtime_parent_existed_before
                    else list(runtime_parent_identity)
                ),
            },
            "recursive_directory_durability_verified": True,
            "seal_parent_durability_required": True,
            "marker_free_final_postimage": True,
            "post_approval_child_process_allowed": False,
            "post_approval_network_allowed": False,
            "post_approval_copy_allowed": False,
            "absolute_paths_echoed": False,
        }
        seal_bytes = (
            json.dumps(seal, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        _write_exact_new_file(seal_path, seal_bytes)
        _flush_directory_durable(transaction)
        prepared = PreparedRuntimeCandidate(
            **{
                **provisional.__dict__,
                "inventory_sha256": inventory_sha256,
                "candidate_sha256": candidate_sha256,
                "seal_bytes": seal_bytes,
                "seal_sha256": _sha256_bytes(seal_bytes),
                "existing_runtime_reusable": existing_runtime_reusable,
            }
        )
        verify_prepared_runtime_candidate(
            prepared,
            project_root=project,
            target=target,
            target_commit=target_commit,
            bootstrap=bootstrap,
            supply=supply,
        )
        return prepared
    except BaseException as error:
        # Unknown or partial candidates belong to the durable transaction.
        # Automatic recursive deletion here would destroy recovery evidence.
        if mutated and not isinstance(error, PreparedRuntimeCandidateIncompleteError):
            raise PreparedRuntimeCandidateIncompleteError() from error
        raise


def _sealed_identity(value: Any) -> tuple[int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in value)
    ):
        raise ProjectRuntimeError("project_runtime_candidate_seal_invalid")
    return int(value[0]), int(value[1])


def load_prepared_runtime_candidate(
    project_root: Path,
    transaction_root: Path,
    *,
    target: str,
    target_commit: str,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
) -> PreparedRuntimeCandidate:
    """Reopen one sealed preapproval candidate without executing any code."""

    project, transaction, transaction_ref, logical_candidate, logical_seal = (
        _candidate_paths(project_root, transaction_root)
    )
    candidate_root = transaction / PROJECT_RUNTIME_CANDIDATE_NAME
    seal_path = transaction / PROJECT_RUNTIME_CANDIDATE_SEAL_NAME
    seal_bytes = _read_limited(seal_path, limit=256 * 1024)
    receipt_bytes = _read_limited(
        candidate_root / PROJECT_RUNTIME_RECEIPT_NAME,
        limit=2 * 1024 * 1024,
    )
    if seal_bytes is None or receipt_bytes is None:
        raise ProjectRuntimeError("project_runtime_candidate_seal_invalid")
    try:
        seal = _json_without_duplicate_keys(seal_bytes)
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise ProjectRuntimeError("project_runtime_candidate_seal_invalid") from error
    if not isinstance(seal, dict):
        raise ProjectRuntimeError("project_runtime_candidate_seal_invalid")
    identities = seal.get("path_identities")
    if not isinstance(identities, dict) or set(identities) != {
        "project_root",
        "transaction_root",
        "candidate_root",
        "runtime_parent",
        "runtime_parent_created",
    }:
        raise ProjectRuntimeError("project_runtime_candidate_seal_invalid")
    project_identity = _sealed_identity(identities.get("project_root"))
    transaction_identity = _sealed_identity(identities.get("transaction_root"))
    candidate_identity = _sealed_identity(identities.get("candidate_root"))
    runtime_parent_identity = _sealed_identity(identities.get("runtime_parent"))
    created_value = identities.get("runtime_parent_created")
    runtime_parent_created_identity = (
        None if created_value is None else _sealed_identity(created_value)
    )
    inventory = _candidate_inventory_snapshot(candidate_root)
    receipt = _candidate_receipt_document(receipt_bytes)
    canonical_inventory, _retained, _top = _verify_retained_artifacts(
        candidate_root,
        bootstrap=bootstrap,
        supply=supply,
        receipt_inventory=receipt.get("artifact_inventory"),
    )
    inventory_sha = seal.get("inventory_sha256")
    candidate_sha = seal.get("candidate_sha256")
    if (
        not isinstance(inventory_sha, str)
        or not inventory_sha.startswith("sha256:")
        or SHA256_RE.fullmatch(inventory_sha.removeprefix("sha256:")) is None
        or not isinstance(candidate_sha, str)
        or not candidate_sha.startswith("sha256:")
        or SHA256_RE.fullmatch(candidate_sha.removeprefix("sha256:")) is None
        or not isinstance(seal.get("inventory_count"), int)
        or isinstance(seal.get("inventory_count"), bool)
        or not isinstance(seal.get("inventory_bytes"), int)
        or isinstance(seal.get("inventory_bytes"), bool)
        or not isinstance(seal.get("existing_runtime_reusable"), bool)
        or not isinstance(seal.get("runtime_parent_existed_before"), bool)
    ):
        raise ProjectRuntimeError("project_runtime_candidate_seal_invalid")
    distributions = receipt.get("installed_distributions")
    verification = receipt.get("verification")
    python_version = receipt.get("python_version")
    if (
        not isinstance(distributions, list)
        or not isinstance(verification, dict)
        or not isinstance(python_version, str)
    ):
        raise ProjectRuntimeError("project_runtime_candidate_receipt_invalid")
    candidate = PreparedRuntimeCandidate(
        target_tag=str(receipt.get("target_tag")),
        target_version=str(receipt.get("target_version")),
        target_commit=str(receipt.get("target_commit")),
        transaction_ref=transaction_ref,
        logical_candidate_path=logical_candidate,
        logical_seal_path=logical_seal,
        project_root=project,
        transaction_root=transaction,
        candidate_root=candidate_root,
        seal_path=seal_path,
        project_root_identity=project_identity,
        transaction_root_identity=transaction_identity,
        candidate_root_identity=candidate_identity,
        runtime_parent_identity=runtime_parent_identity,
        runtime_parent_existed_before=seal["runtime_parent_existed_before"],
        runtime_parent_created_identity=runtime_parent_created_identity,
        same_volume_identity=candidate_identity[0],
        inventory=inventory,
        inventory_sha256=inventory_sha.removeprefix("sha256:"),
        candidate_sha256=candidate_sha.removeprefix("sha256:"),
        inventory_count=seal["inventory_count"],
        inventory_bytes=seal["inventory_bytes"],
        seal_bytes=seal_bytes,
        seal_sha256=_sha256_bytes(seal_bytes),
        receipt_bytes=receipt_bytes,
        receipt_sha256=_sha256_bytes(receipt_bytes),
        wheel_file_name=str(receipt.get("wheel_file_name")),
        wheel_sha256=str(receipt.get("wheel_sha256", "")).removeprefix("sha256:"),
        supply_lock_sha256=str(
            receipt.get("supply_lock_sha256", "")
        ).removeprefix("sha256:"),
        supply_lock_bytes=supply.raw_bytes,
        artifact_inventory=canonical_inventory,
        installed_payload_sha256=str(
            receipt.get("installed_payload_sha256", "")
        ).removeprefix("sha256:"),
        normalized_payload_inventory=_normalized_runtime_payload_inventory(
            candidate_root
        ),
        python_version=python_version,
        installed_distributions=tuple(dict(item) for item in distributions),
        verification=dict(verification),
        existing_runtime_reusable=seal["existing_runtime_reusable"],
    )
    verify_prepared_runtime_candidate(
        candidate,
        project_root=project,
        target=target,
        target_commit=target_commit,
        bootstrap=bootstrap,
        supply=supply,
    )
    return candidate


def verify_prepared_runtime_candidate(
    candidate: PreparedRuntimeCandidate,
    *,
    project_root: Path,
    target: str,
    target_commit: str,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
) -> dict[str, Any]:
    """Statically revalidate a sealed candidate; executes no child or toolchain."""

    if not isinstance(candidate, PreparedRuntimeCandidate):
        raise ProjectRuntimeError("project_runtime_candidate_binding_invalid")
    version = _version(target)
    project, transaction, transaction_ref, logical_candidate, logical_seal = (
        _candidate_paths(project_root, candidate.transaction_root)
    )
    if (
        version is None
        or candidate.target_tag != f"v{version}"
        or candidate.target_version != version
        or candidate.target_commit != target_commit
        or candidate.transaction_ref != transaction_ref
        or candidate.logical_candidate_path != logical_candidate
        or candidate.logical_seal_path != logical_seal
        or candidate.project_root != project
        or candidate.transaction_root != transaction
        or candidate.candidate_root != transaction / PROJECT_RUNTIME_CANDIDATE_NAME
        or candidate.seal_path != transaction / PROJECT_RUNTIME_CANDIDATE_SEAL_NAME
        or bootstrap.version != version
        or bootstrap.tag != f"v{version}"
        or bootstrap.file_name != candidate.wheel_file_name
        or bootstrap.sha256 != candidate.wheel_sha256
        or supply.target_tag != f"v{version}"
        or supply.sha256 != candidate.supply_lock_sha256
        or _sha256_bytes(supply.raw_bytes) != supply.sha256
        or supply.raw_bytes != candidate.supply_lock_bytes
        or (
            candidate.runtime_parent_existed_before
            and candidate.runtime_parent_created_identity is not None
        )
        or (
            not candidate.runtime_parent_existed_before
            and candidate.runtime_parent_created_identity
            != candidate.runtime_parent_identity
        )
    ):
        raise ProjectRuntimeError("project_runtime_candidate_binding_invalid")
    if (
        _path_identity(project) != candidate.project_root_identity
        or _path_identity(transaction) != candidate.transaction_root_identity
        or _path_identity(candidate.candidate_root) != candidate.candidate_root_identity
        or _path_identity(project / PROJECT_RUNTIME_RELATIVE_ROOT)
        != candidate.runtime_parent_identity
        or candidate.candidate_root_identity[0] != candidate.same_volume_identity
        or candidate.runtime_parent_identity[0] != candidate.same_volume_identity
    ):
        raise ProjectRuntimeError("project_runtime_candidate_identity_drift")
    try:
        seal_stat = candidate.seal_path.lstat()
    except OSError as error:
        raise ProjectRuntimeError("project_runtime_candidate_seal_drift") from error
    if (
        candidate.seal_path.is_symlink()
        or _is_reparse(seal_stat)
        or not candidate.seal_path.is_file()
        or _file_link_count(candidate.seal_path, seal_stat) != 1
        or _read_limited(candidate.seal_path, limit=256 * 1024)
        != candidate.seal_bytes
        or _sha256_bytes(candidate.seal_bytes) != candidate.seal_sha256
    ):
        raise ProjectRuntimeError("project_runtime_candidate_seal_drift")
    try:
        seal_document = _json_without_duplicate_keys(candidate.seal_bytes)
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise ProjectRuntimeError("project_runtime_candidate_seal_drift") from error
    expected_seal_keys = {
        "schema",
        "status",
        "target_tag",
        "target_commit",
        "transaction_ref",
        "candidate_locator",
        "inventory_sha256",
        "candidate_sha256",
        "inventory_count",
        "inventory_bytes",
        "receipt_sha256",
        "wheel_file_name",
        "wheel_sha256",
        "supply_lock_sha256",
        "same_volume_verified",
        "existing_runtime_reusable",
        "runtime_parent_existed_before",
        "path_identities",
        "recursive_directory_durability_verified",
        "seal_parent_durability_required",
        "marker_free_final_postimage",
        "post_approval_child_process_allowed",
        "post_approval_network_allowed",
        "post_approval_copy_allowed",
        "absolute_paths_echoed",
    }
    if (
        not isinstance(seal_document, dict)
        or set(seal_document) != expected_seal_keys
        or seal_document.get("schema") != PROJECT_RUNTIME_CANDIDATE_SCHEMA
        or seal_document.get("status") != "sealed"
        or seal_document.get("target_tag") != candidate.target_tag
        or seal_document.get("target_commit") != candidate.target_commit
        or seal_document.get("transaction_ref") != candidate.transaction_ref
        or seal_document.get("candidate_locator")
        != candidate.logical_candidate_path
        or seal_document.get("inventory_sha256")
        != f"sha256:{candidate.inventory_sha256}"
        or seal_document.get("candidate_sha256")
        != f"sha256:{candidate.candidate_sha256}"
        or seal_document.get("inventory_count") != candidate.inventory_count
        or seal_document.get("inventory_bytes") != candidate.inventory_bytes
        or seal_document.get("receipt_sha256")
        != f"sha256:{candidate.receipt_sha256}"
        or seal_document.get("wheel_file_name") != candidate.wheel_file_name
        or seal_document.get("wheel_sha256")
        != f"sha256:{candidate.wheel_sha256}"
        or seal_document.get("supply_lock_sha256")
        != f"sha256:{candidate.supply_lock_sha256}"
        or seal_document.get("same_volume_verified") is not True
        or seal_document.get("existing_runtime_reusable")
        is not candidate.existing_runtime_reusable
        or seal_document.get("runtime_parent_existed_before")
        is not candidate.runtime_parent_existed_before
        or seal_document.get("path_identities")
        != {
            "project_root": list(candidate.project_root_identity),
            "transaction_root": list(candidate.transaction_root_identity),
            "candidate_root": list(candidate.candidate_root_identity),
            "runtime_parent": list(candidate.runtime_parent_identity),
            "runtime_parent_created": (
                None
                if candidate.runtime_parent_created_identity is None
                else list(candidate.runtime_parent_created_identity)
            ),
        }
        or seal_document.get("recursive_directory_durability_verified") is not True
        or seal_document.get("seal_parent_durability_required") is not True
        or seal_document.get("marker_free_final_postimage") is not True
        or seal_document.get("post_approval_child_process_allowed") is not False
        or seal_document.get("post_approval_network_allowed") is not False
        or seal_document.get("post_approval_copy_allowed") is not False
        or seal_document.get("absolute_paths_echoed") is not False
    ):
        raise ProjectRuntimeError("project_runtime_candidate_seal_drift")
    inventory = _candidate_inventory_snapshot(candidate.candidate_root)
    inventory_bytes = sum(
        item.size_bytes for item in inventory if item.entry_type == "file"
    )
    if (
        inventory != candidate.inventory
        or _recursive_candidate_inventory_digest(inventory)
        != candidate.inventory_sha256
        or len(inventory) != candidate.inventory_count
        or inventory_bytes != candidate.inventory_bytes
    ):
        raise ProjectRuntimeError("project_runtime_candidate_drift")
    digest = _candidate_binding_digest(
        target_tag=candidate.target_tag,
        target_commit=target_commit,
        transaction_ref=candidate.transaction_ref,
        logical_candidate_path=candidate.logical_candidate_path,
        wheel_file_name=candidate.wheel_file_name,
        wheel_sha256=candidate.wheel_sha256,
        supply_lock_sha256=candidate.supply_lock_sha256,
        receipt_sha256=candidate.receipt_sha256,
        installed_payload_sha256=candidate.installed_payload_sha256,
        normalized_payload_inventory=candidate.normalized_payload_inventory,
        existing_runtime_reusable=candidate.existing_runtime_reusable,
        runtime_parent_existed_before=candidate.runtime_parent_existed_before,
        inventory=inventory,
    )
    if digest != candidate.candidate_sha256:
        raise ProjectRuntimeError("project_runtime_candidate_drift")
    receipt_bytes = _read_limited(
        candidate.candidate_root / PROJECT_RUNTIME_RECEIPT_NAME,
        limit=2 * 1024 * 1024,
    )
    if (
        receipt_bytes != candidate.receipt_bytes
        or _sha256_bytes(receipt_bytes or b"") != candidate.receipt_sha256
    ):
        raise ProjectRuntimeError("project_runtime_candidate_receipt_drift")
    receipt = _candidate_receipt_document(receipt_bytes or b"")
    if (
        receipt.get("target_tag") != candidate.target_tag
        or receipt.get("target_version") != candidate.target_version
        or receipt.get("target_commit") != candidate.target_commit
        or receipt.get("wheel_file_name") != candidate.wheel_file_name
        or receipt.get("wheel_sha256") != f"sha256:{candidate.wheel_sha256}"
        or receipt.get("supply_lock_sha256")
        != f"sha256:{candidate.supply_lock_sha256}"
        or receipt.get("installed_payload_sha256")
        != f"sha256:{candidate.installed_payload_sha256}"
        or receipt.get("python_version") != candidate.python_version
        or tuple(receipt.get("installed_distributions", ()))
        != candidate.installed_distributions
        or receipt.get("verification") != dict(candidate.verification)
    ):
        raise ProjectRuntimeError("project_runtime_candidate_receipt_drift")
    canonical_inventory, _retained, _top = _verify_retained_artifacts(
        candidate.candidate_root,
        bootstrap=bootstrap,
        supply=supply,
        receipt_inventory=receipt.get("artifact_inventory"),
    )
    if tuple(dict(item) for item in canonical_inventory) != tuple(
        dict(item) for item in candidate.artifact_inventory
    ):
        raise ProjectRuntimeError("project_runtime_candidate_artifact_drift")
    if (
        _runtime_payload_sha256(candidate.candidate_root)
        != candidate.installed_payload_sha256
        or _normalized_runtime_payload_inventory(candidate.candidate_root)
        != candidate.normalized_payload_inventory
    ):
        raise ProjectRuntimeError("project_runtime_candidate_payload_drift")
    summary = candidate.public_summary()
    summary["static_reverified"] = True
    return summary


def _atomic_promote_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically move a directory without replacement or copy fallback."""

    import ctypes

    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move = kernel32.MoveFileExW
        move.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        move.restype = ctypes.c_int
        # MOVEFILE_WRITE_THROUGH only.  Deliberately omit REPLACE_EXISTING and
        # COPY_ALLOWED.
        if not move(str(source), str(destination), 0x00000008):
            raise OSError(ctypes.get_last_error(), "atomic no-replace move failed")
        return
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise OSError("atomic no-replace directory promotion unsupported")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    if renameat2(
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(destination),
        1,  # RENAME_NOREPLACE
    ) != 0:
        raise OSError(ctypes.get_errno(), "atomic no-replace move failed")


def _verify_promoted_candidate_image(
    candidate: PreparedRuntimeCandidate,
    final: Path,
) -> None:
    if (
        _lexists(candidate.candidate_root)
        or not final.is_dir()
        or not _existing_components_are_real(candidate.project_root, final)
        or _path_identity(final) != candidate.candidate_root_identity
        or _candidate_inventory_snapshot(final) != candidate.inventory
        or _read_limited(final / PROJECT_RUNTIME_RECEIPT_NAME, limit=2 * 1024 * 1024)
        != candidate.receipt_bytes
    ):
        raise ProjectRuntimeError("project_runtime_candidate_promotion_ambiguous")


def promote_runtime_candidate(
    project_root: Path,
    *,
    target: str,
    target_commit: str,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    prepared_candidate: PreparedRuntimeCandidate,
    mutation_tracker: RuntimeMutationTracker | None = None,
) -> RuntimeMaterialization:
    """Post-approval static CAS promotion; never executes or copies anything."""

    verify_prepared_runtime_candidate(
        prepared_candidate,
        project_root=project_root,
        target=target,
        target_commit=target_commit,
        bootstrap=bootstrap,
        supply=supply,
    )
    candidate = prepared_candidate
    project = Path(os.path.abspath(str(project_root)))
    final = runtime_path(project, candidate.target_version)
    tracker = mutation_tracker
    if tracker is not None and (
        not isinstance(tracker, RuntimeMutationTracker)
        or tracker.before is not None
        or tracker.started
        or tracker.completed
        or tracker.cleanup_verified is not None
    ):
        raise ProjectRuntimeError("project_runtime_mutation_tracker_not_pristine")
    if candidate.existing_runtime_reusable:
        if not _existing_runtime_matches_candidate(project, candidate):
            raise ProjectRuntimeError("project_runtime_existing_runtime_drift")
        receipt_bytes = _read_limited(
            final / PROJECT_RUNTIME_RECEIPT_NAME,
            limit=2 * 1024 * 1024,
        )
        if receipt_bytes is None:
            raise ProjectRuntimeError("project_runtime_existing_runtime_drift")
        return RuntimeMaterialization(
            target_tag=candidate.target_tag,
            target_version=candidate.target_version,
            target_commit=candidate.target_commit,
            final_path=final,
            logical_path=runtime_logical_path(candidate.target_version),
            receipt_bytes=receipt_bytes,
            receipt_sha256=_sha256_bytes(receipt_bytes),
            wheel_sha256=candidate.wheel_sha256,
            supply_lock_sha256=candidate.supply_lock_sha256,
            artifact_inventory=candidate.artifact_inventory,
            installed_payload_sha256=candidate.installed_payload_sha256,
            python_version=candidate.python_version,
            created=False,
            verification=candidate.verification,
        )
    if _lexists(final):
        raise ProjectRuntimeError("project_runtime_target_directory_concurrent")
    runtimes_root = project / PROJECT_RUNTIME_RELATIVE_ROOT
    if (
        _path_identity(runtimes_root) != candidate.runtime_parent_identity
        or _path_identity(candidate.candidate_root)[0] != _path_identity(runtimes_root)[0]
    ):
        raise ProjectRuntimeError("project_runtime_candidate_cross_volume")
    if tracker is not None:
        tracker.before = runtime_root_snapshot(project)
        if not tracker.before.valid:
            raise ProjectRuntimeError("project_runtime_root_snapshot_unavailable")
        tracker.started = True
        tracker.cleanup_verified = False
    try:
        _atomic_promote_directory_no_replace(candidate.candidate_root, final)
        _verify_promoted_candidate_image(candidate, final)
        # Persist both halves of the rename: destination addition and source
        # removal.  A barrier failure is ambiguous and never triggers deletion.
        _flush_directory_durable(runtimes_root)
        _flush_directory_durable(candidate.transaction_root)
        _verify_promoted_candidate_image(candidate, final)
    except BaseException as error:
        raise ProjectRuntimeError(
            "project_runtime_candidate_promotion_ambiguous"
        ) from error
    if tracker is not None:
        tracker.completed = True
        tracker.cleanup_verified = None
    return RuntimeMaterialization(
        target_tag=candidate.target_tag,
        target_version=candidate.target_version,
        target_commit=candidate.target_commit,
        final_path=final,
        logical_path=runtime_logical_path(candidate.target_version),
        receipt_bytes=candidate.receipt_bytes,
        receipt_sha256=candidate.receipt_sha256,
        wheel_sha256=candidate.wheel_sha256,
        supply_lock_sha256=candidate.supply_lock_sha256,
        artifact_inventory=candidate.artifact_inventory,
        installed_payload_sha256=candidate.installed_payload_sha256,
        python_version=candidate.python_version,
        created=True,
        verification=candidate.verification,
    )


def _delete_exact_inventory_tree(
    root: Path,
    inventory: tuple[RuntimeCandidateInventoryEntry, ...],
) -> bool:
    try:
        if _candidate_inventory_snapshot(root) != inventory:
            return False
        files = [item for item in inventory if item.entry_type == "file"]
        directories = [item for item in inventory if item.entry_type == "directory"]
        for item in sorted(
            files,
            key=lambda value: (value.relative_path.count("/"), value.relative_path),
            reverse=True,
        ):
            path = root / PurePosixPath(item.relative_path)
            stat_result = path.lstat()
            digest, size = _sha256_file(path, limit=1024 * 1024 * 1024)
            if (
                path.is_symlink()
                or _is_reparse(stat_result)
                or int(stat_result.st_dev) != item.device
                or int(stat_result.st_ino) != item.inode
                or _file_link_count(path, stat_result) != 1
                or size != item.size_bytes
                or digest != item.sha256
                or int(stat_result.st_mtime_ns) != item.mtime_ns
            ):
                return False
            path.unlink()
        for item in sorted(
            directories,
            key=lambda value: (value.relative_path.count("/"), value.relative_path),
            reverse=True,
        ):
            path = root / PurePosixPath(item.relative_path)
            stat_result = path.lstat()
            if (
                path.is_symlink()
                or _is_reparse(stat_result)
                or not path.is_dir()
                or int(stat_result.st_dev) != item.device
                or int(stat_result.st_ino) != item.inode
                or int(stat_result.st_nlink) != item.nlink
            ):
                return False
            path.rmdir()
        root.rmdir()
    except (OSError, ProjectRuntimeError):
        return False
    return not _lexists(root)


def _restore_runtime_parent_after_candidate_cleanup(
    candidate: PreparedRuntimeCandidate,
    *,
    promoted_final_present: bool,
) -> bool:
    """Restore an exact-owned empty runtime parent on sealed cancellation."""

    if candidate.runtime_parent_existed_before or promoted_final_present:
        return True
    runtime_parent = candidate.project_root / PROJECT_RUNTIME_RELATIVE_ROOT
    expected_identity = candidate.runtime_parent_created_identity
    if expected_identity is None:
        return False
    if not _lexists(runtime_parent):
        try:
            _flush_directory_durable(runtime_parent.parent)
        except ProjectRuntimeError:
            return False
        return True
    try:
        stat_result = runtime_parent.lstat()
        if (
            runtime_parent.is_symlink()
            or _is_reparse(stat_result)
            or not runtime_parent.is_dir()
            or (int(stat_result.st_dev), int(stat_result.st_ino))
            != expected_identity
            or not _existing_components_are_real(candidate.project_root, runtime_parent)
        ):
            return False
        with os.scandir(runtime_parent) as iterator:
            if next(iterator, None) is not None:
                return False
        runtime_parent.rmdir()
        _flush_directory_durable(runtime_parent.parent)
    except (OSError, ProjectRuntimeError):
        return False
    return not _lexists(runtime_parent)


def cleanup_prepared_runtime_candidate(
    candidate: PreparedRuntimeCandidate,
) -> bool:
    """Delete only a fully sealed exact candidate; unknown trees are retained."""

    if not isinstance(candidate, PreparedRuntimeCandidate):
        return False
    quarantine = candidate.transaction_root / (
        f"runtime-candidate-cleanup-{candidate.inventory_sha256[:16]}"
    )
    root = candidate.candidate_root
    final_matches = False
    if _lexists(root):
        parsed_supply = project_runtime_supply_lock(
            candidate.supply_lock_bytes,
            expected_target=candidate.target_tag,
        )
        if parsed_supply is None:
            return False
        try:
            verify_prepared_runtime_candidate(
                candidate,
                project_root=candidate.project_root,
                target=candidate.target_tag,
                target_commit=candidate.target_commit,
                bootstrap=BootstrapWheel(
                    version=candidate.target_version,
                    tag=candidate.target_tag,
                    url="https://invalid.example/never-used",
                    sha256=candidate.wheel_sha256,
                    file_name=candidate.wheel_file_name,
                ),
                supply=parsed_supply,
            )
        except (ProjectRuntimeError, TypeError, AttributeError):
            return False
        if _lexists(quarantine):
            return False
        try:
            _atomic_promote_directory_no_replace(root, quarantine)
            _flush_directory_durable(candidate.transaction_root)
        except (OSError, ProjectRuntimeError):
            return False
    elif not _lexists(quarantine):
        final = runtime_path(candidate.project_root, candidate.target_version)
        try:
            final_matches = (
                final.is_dir()
                and _candidate_inventory_snapshot(final) == candidate.inventory
            )
        except ProjectRuntimeError:
            final_matches = False
        if not final_matches and _lexists(candidate.seal_path):
            # Candidate disappeared without the exact quarantine/final image.
            # Preserve the remaining seal as recovery evidence.
            return False
    if _lexists(quarantine):
        try:
            _flush_directory_durable(candidate.transaction_root)
        except ProjectRuntimeError:
            return False
        # Keep the exact quarantine and seal as durable evidence until an
        # exact-created runtime parent can also be restored.
        if not _restore_runtime_parent_after_candidate_cleanup(
            candidate,
            promoted_final_present=final_matches,
        ):
            return False
        if (
            _path_identity(quarantine) != candidate.candidate_root_identity
            or not _delete_exact_inventory_tree(quarantine, candidate.inventory)
        ):
            return False
        try:
            _flush_directory_durable(candidate.transaction_root)
        except ProjectRuntimeError:
            return False
    else:
        # Promoted-final cleanup has no quarantine, but still observes the
        # runtime-parent contract before removing its seal.
        if not _restore_runtime_parent_after_candidate_cleanup(
            candidate,
            promoted_final_present=final_matches,
        ):
            return False
    try:
        seal_stat = candidate.seal_path.lstat()
        if (
            candidate.seal_path.is_symlink()
            or _is_reparse(seal_stat)
            or _file_link_count(candidate.seal_path, seal_stat) != 1
            or _read_limited(candidate.seal_path, limit=256 * 1024)
            != candidate.seal_bytes
        ):
            return False
        candidate.seal_path.unlink()
        _flush_directory_durable(candidate.transaction_root)
    except FileNotFoundError:
        try:
            _flush_directory_durable(candidate.transaction_root)
        except ProjectRuntimeError:
            return False
    except (OSError, ProjectRuntimeError):
        return False
    return (
        not _lexists(candidate.candidate_root)
        and not _lexists(quarantine)
        and not _lexists(candidate.seal_path)
    )


# Transitional names remain importable for service/test patching, but they no
# longer expose the old wheels-only or post-approval toolchain behavior.
def prepare_runtime_bundle(*args: Any, **kwargs: Any) -> PreparedRuntimeCandidate:
    raise ProjectRuntimeError("project_runtime_legacy_bundle_api_disabled")


def verify_prepared_runtime_bundle(
    bundle: PreparedRuntimeCandidate,
    *,
    target: str,
    target_commit: str,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    project_root: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(bundle, PreparedRuntimeCandidate) or project_root is None:
        raise ProjectRuntimeError("project_runtime_legacy_bundle_api_disabled")
    return verify_prepared_runtime_candidate(
        bundle,
        project_root=project_root,
        target=target,
        target_commit=target_commit,
        bootstrap=bootstrap,
        supply=supply,
    )


def cleanup_prepared_runtime_bundle(bundle: Any) -> bool:
    return (
        cleanup_prepared_runtime_candidate(bundle)
        if isinstance(bundle, PreparedRuntimeCandidate)
        else False
    )


def materialize_runtime(
    project_root: Path,
    *,
    target: str,
    target_commit: str,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    prepared_bundle: PreparedRuntimeCandidate,
    mutation_tracker: RuntimeMutationTracker,
    running_version: str,
    progress_callback: Callable[[str, str, int | None, int | None], None] | None = None,
) -> RuntimeMaterialization:
    if not isinstance(prepared_bundle, PreparedRuntimeCandidate):
        raise ProjectRuntimeError("project_runtime_legacy_bundle_api_disabled")
    # running_version and progress_callback are deliberately unused after the
    # candidate seal; retaining them only keeps the integration transition
    # explicit and source-compatible.
    return promote_runtime_candidate(
        project_root,
        target=target,
        target_commit=target_commit,
        bootstrap=bootstrap,
        supply=supply,
        prepared_candidate=prepared_bundle,
        mutation_tracker=mutation_tracker,
    )


def remove_materialized_runtime(
    project_root: Path,
    runtime: RuntimeMaterialization,
    *,
    mutation_tracker: RuntimeMutationTracker | None = None,
) -> bool:
    """Never auto-delete a promoted final runtime.

    Durable project-update recovery owns any approved rollback/quarantine.  A
    no-op reuse needs no deletion; a created final always remains in place.
    """

    return not runtime.created
