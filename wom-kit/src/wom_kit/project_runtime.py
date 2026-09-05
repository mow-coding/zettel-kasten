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
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator, Mapping

from .schema_validator import validate_schema
from .process_launch import noninteractive_creationflags


PROJECT_RUNTIME_POLICY_SCHEMA = "wom-kit/project-runtime-policy/v0.1"
PROJECT_RUNTIME_RECEIPT_SCHEMA = "wom-kit/project-runtime-receipt/v0.1"
PROJECT_RUNTIME_REPAIR_RECEIPT_SCHEMA = "wom-kit/project-runtime-receipt/v0.2"
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
PROJECT_RUNTIME_CLEANUP_CAPSULE_SCHEMA = (
    "wom-kit/project-runtime-candidate-cleanup/v0.4.19"
)
PROJECT_RUNTIME_CLEANUP_TERMINAL_EVIDENCE_SCHEMA = (
    "wom-kit/project-update-runtime-cleanup-terminal-evidence/v0.4.19"
)
PROJECT_RUNTIME_CLEANUP_SIDECAR_INVENTORY_SCHEMA = (
    "wom-kit/project-runtime-candidate-cleanup-sidecars/v0.4.19"
)
PROJECT_RUNTIME_CLEANUP_CAPSULE_PREFIX = ".runtime-candidate-cleanup_"
PROJECT_RUNTIME_CLEANUP_CAPSULE_SUFFIX = ".json"
PROJECT_RUNTIME_CLEANUP_CAPSULE_MAX_BYTES = 64 * 1024 * 1024
PROJECT_RUNTIME_CLEANUP_CAPSULE_KEYS = frozenset(
    {
        "schema",
        "status",
        "target_tag",
        "target_version",
        "target_commit",
        "transaction_ref",
        "candidate_locator",
        "seal_locator",
        "quarantine_locator",
        "project_root_identity",
        "transaction_root_identity",
        "candidate_root_identity",
        "runtime_parent_identity",
        "runtime_parent_existed_before",
        "runtime_parent_created_identity",
        "existing_runtime_root_identity",
        "capsule_parent_identity",
        "capsule_identity",
        "inventory",
        "inventory_sha256",
        "inventory_count",
        "inventory_bytes",
        "candidate_sha256",
        "seal_identity",
        "seal_mtime_ns",
        "seal_size_bytes",
        "seal_sha256",
        "outer_transaction_ack_required_before_retire",
        "absolute_paths_echoed",
    }
)
PROJECT_RUNTIME_REPAIR_BACKUP_NAME = "runtime-repair-preimage"
PROJECT_RUNTIME_ROLLBACK_CANDIDATE_NAME = "runtime-rollback-candidate"
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
PROJECT_RUNTIME_TRANSIENT_TREE_SCAN_ATTEMPTS = 3
PROJECT_RUNTIME_TRANSIENT_TREE_SCAN_BACKOFF_SECONDS = 0.025
PROJECT_RUNTIME_TRANSIENT_WINDOWS_ERRORS = frozenset({5, 32, 33})


class ProjectRuntimeError(RuntimeError):
    """A content-free project runtime failure."""


_LIVE_PAYLOAD_INTEGRITY_FAILURE_CODES = frozenset(
    {
        "project_runtime_required_python_missing",
        "project_runtime_required_python_unsafe",
        "project_runtime_tree_unsafe",
        "project_runtime_tree_case_collision",
        "project_runtime_tree_too_large",
    }
)


def _live_payload_observation_error(
    error: BaseException,
) -> tuple[str, str]:
    code = str(error.args[0]) if error.args else ""
    if code in _LIVE_PAYLOAD_INTEGRITY_FAILURE_CODES:
        return "failed", code
    return "unavailable", "project_runtime_live_payload_unavailable"


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
    existing_runtime_repair_required: bool
    existing_runtime_root_identity: tuple[int, int] | None
    existing_runtime_inventory: tuple[RuntimeCandidateInventoryEntry, ...] = field(
        repr=False
    )
    existing_runtime_inventory_sha256: str | None
    existing_runtime_inventory_count: int
    existing_runtime_inventory_bytes: int
    # v0.4.15 private recovery records and public approval summaries predate
    # repair-only fields.  This bit is private reconstruction state only; it
    # keeps those already-authenticated bytes and digests unchanged.
    legacy_resume_shape: bool = field(
        default=False,
        repr=False,
        compare=False,
    )

    def public_summary(self) -> dict[str, Any]:
        summary = {
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
        if self.legacy_resume_shape:
            return summary
        summary.update(
            {
                "runtime_receipt_schema": _candidate_receipt_document(
                    self.receipt_bytes
                )["schema"],
                "existing_runtime_repair_required": (
                    self.existing_runtime_repair_required
                ),
                "existing_runtime_preimage_sha256": (
                    None
                    if self.existing_runtime_inventory_sha256 is None
                    else f"sha256:{self.existing_runtime_inventory_sha256}"
                ),
                "existing_runtime_preimage_count": (
                    self.existing_runtime_inventory_count
                ),
                "existing_runtime_preimage_bytes": (
                    self.existing_runtime_inventory_bytes
                ),
                # Preview truth describes the exact future lifecycle.  The
                # old runtime is bound now, but it is not moved into the
                # private transaction until approved promotion.
                "repair_preimage_exactly_bound": (
                    self.existing_runtime_repair_required
                ),
                "will_preserve_during_active_transaction": (
                    self.existing_runtime_repair_required
                ),
            }
        )
        return summary


@dataclass(frozen=True)
class RuntimeCandidateCleanupCapsule:
    """Private, self-contained authority for crash-safe candidate cleanup."""

    target_tag: str
    target_version: str
    target_commit: str
    transaction_ref: str
    project_root: Path = field(repr=False)
    transaction_root: Path = field(repr=False)
    candidate_root: Path = field(repr=False)
    quarantine_root: Path = field(repr=False)
    seal_path: Path = field(repr=False)
    capsule_path: Path = field(repr=False)
    capsule_parent_identity: tuple[int, int]
    capsule_identity: tuple[int, int]
    capsule_mtime_ns: int
    capsule_size_bytes: int
    project_root_identity: tuple[int, int]
    transaction_root_identity: tuple[int, int]
    candidate_root_identity: tuple[int, int]
    runtime_parent_identity: tuple[int, int]
    runtime_parent_existed_before: bool
    runtime_parent_created_identity: tuple[int, int] | None
    existing_runtime_root_identity: tuple[int, int] | None
    inventory: tuple[RuntimeCandidateInventoryEntry, ...] = field(repr=False)
    inventory_sha256: str
    inventory_count: int
    inventory_bytes: int
    candidate_sha256: str
    seal_identity: tuple[int, int]
    seal_mtime_ns: int
    seal_size_bytes: int
    seal_sha256: str
    capsule_bytes: bytes = field(repr=False)
    capsule_sha256: str

    def public_evidence(self) -> dict[str, Any]:
        """Return content-free evidence for the outer transaction checkpoint."""

        return {
            "schema": PROJECT_RUNTIME_CLEANUP_TERMINAL_EVIDENCE_SCHEMA,
            "status": "terminal_cleanup_evidence",
            "target_tag": self.target_tag,
            "transaction_ref": self.transaction_ref,
            "candidate_sha256": f"sha256:{self.candidate_sha256}",
            "provider_inventory_sha256": (
                f"sha256:{self.inventory_sha256}"
            ),
            "provider_inventory_count": self.inventory_count,
            "provider_inventory_bytes": self.inventory_bytes,
            "runtime_cleanup_capsule_sha256": (
                f"sha256:{self.capsule_sha256}"
            ),
            "runtime_cleanup_capsule_identity_sha256": (
                "sha256:"
                + _sha256_bytes(
                    (
                        json.dumps(
                            list(self.capsule_identity),
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("ascii")
                )
            ),
            "outer_transaction_ack_required_before_retire": True,
            "sidecar_must_retire_before_transaction_cleanup": True,
            "private_paths_echoed": False,
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
    inventory: tuple[RuntimeCandidateInventoryEntry, ...] = field(
        default=(), repr=False
    )
    runtime_root_identity: tuple[int, int] | None = field(
        default=None, repr=False
    )
    runtime_parent_identity: tuple[int, int] | None = field(
        default=None, repr=False
    )
    repaired: bool = False
    replaced_runtime_path: Path | None = field(default=None, repr=False)
    replaced_runtime_identity: tuple[int, int] | None = field(
        default=None, repr=False
    )
    replaced_runtime_inventory: tuple[RuntimeCandidateInventoryEntry, ...] = field(
        default=(), repr=False
    )
    transaction_root: Path | None = field(default=None, repr=False)
    transaction_root_identity: tuple[int, int] | None = field(
        default=None, repr=False
    )
    runtime_parent_existed_before: bool = True
    runtime_parent_created_identity: tuple[int, int] | None = field(
        default=None, repr=False
    )

    def public_summary(self) -> dict[str, Any]:
        return {
            "status": "verified",
            "target_tag": self.target_tag,
            "target_version": self.target_version,
            "target_commit": self.target_commit,
            "path": self.logical_path,
            "created": self.created,
            "repaired": self.repaired,
            # This summary is built while the authenticated transaction is
            # still active.  Terminal projection replaces this live-state
            # truth after exact cleanup has run.
            "rollback_preimage_present": bool(
                self.repaired and self.replaced_runtime_path is not None
            ),
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
    device/inode identity plus type, file size, mtime and Windows attributes is
    the portable observation used here. Directory allocation
    size is not a content generation: Windows can report it as zero before a
    later metadata observation without any member or byte change. Tree scans
    bind exact members separately. Directory size/ARCHIVE are bookkeeping.
    NTFS may also return redundant 0x10000000 (CPython #126253): normalize it
    only with directory mode AND Win32 DIRECTORY (0x10). Retain all other bits.
    Descriptors remain byte authority; paths prove stable names and ancestors.
    """
    attributes = int(getattr(stat_result, "st_file_attributes", 0))
    return (
        int(stat_result.st_dev),
        int(stat_result.st_ino),
        int(stat_module.S_IFMT(stat_result.st_mode)),
        0 if stat_module.S_ISDIR(stat_result.st_mode) else int(stat_result.st_size),
        int(stat_result.st_mtime_ns),
        attributes & (~(0x20 | (0x10000000 if attributes & 0x10 else 0)) if stat_module.S_ISDIR(stat_result.st_mode) else -1),
    )


def _real_component_snapshot(
    root: Path,
    target: Path,
    *,
    target_must_exist: bool,
) -> tuple[tuple[str, tuple[int, int, int, int, int, int]], ...] | None:
    """Observe one non-reparse path chain without resolving through links."""

    observation = _real_component_snapshot_observation(
        root,
        target,
        target_must_exist=target_must_exist,
    )
    snapshot = observation.get("snapshot")
    return snapshot if isinstance(snapshot, tuple) else None


def _real_component_snapshot_observation(
    root: Path,
    target: Path,
    *,
    target_must_exist: bool,
) -> dict[str, Any]:
    """Observe a path chain while preserving failed vs unavailable truth."""

    try:
        root_absolute = Path(os.path.abspath(str(root)))
        target_absolute = Path(os.path.abspath(str(target)))
        relative = target_absolute.relative_to(root_absolute)
    except ValueError:
        return {
            "state": "failed",
            "reason_code": "path_outside_root",
            "snapshot": None,
        }
    except (OSError, RuntimeError):
        return {
            "state": "unavailable",
            "reason_code": "path_observation_unavailable",
            "snapshot": None,
        }
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
            return {
                "state": "failed",
                "reason_code": "path_component_missing",
                "snapshot": None,
            }
        except OSError:
            return {
                "state": "unavailable",
                "reason_code": "path_observation_unavailable",
                "snapshot": None,
            }
        if _is_reparse_stat(component_stat) or stat_module.S_ISLNK(
            component_stat.st_mode
        ):
            return {
                "state": "failed",
                "reason_code": "path_component_reparse",
                "snapshot": None,
            }
        is_target = index == len(paths) - 1
        if not is_target and not stat_module.S_ISDIR(component_stat.st_mode):
            return {
                "state": "failed",
                "reason_code": "path_component_not_directory",
                "snapshot": None,
            }
        if is_target and target_must_exist and not (
            stat_module.S_ISREG(component_stat.st_mode)
            or stat_module.S_ISDIR(component_stat.st_mode)
        ):
            return {
                "state": "failed",
                "reason_code": "path_target_kind_invalid",
                "snapshot": None,
            }
        observations.append((str(component), _stat_identity(component_stat)))
    if target_must_exist and len(observations) != len(paths):
        return {
            "state": "failed",
            "reason_code": "path_component_missing",
            "snapshot": None,
        }
    return {
        "state": "passed",
        "reason_code": "verified",
        "snapshot": tuple(observations),
    }


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
        "supply_lock": "wom-kit/project-runtime-supply-lock-v0.4.19.json",
        "supply_lock_sha256": "sha256:8714250cab5fd639ef00c99d054f7b33b7a8b45fce63f68702e4138fec83b70e",
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
    *,
    expected_created_identity: tuple[int, int] | None = None,
) -> None:
    """Remove only the exact empty runtime parent created by this operation.

    A before-snapshot that says the name was absent is not deletion authority:
    another process may have created that name since the snapshot.  Legacy
    callers that do not carry the created identity therefore fail closed.
    """

    before = tracker.before
    if (
        before is None
        or before.root_existed
        or expected_created_identity is None
    ):
        return
    _restore_exact_owned_runtime_parent(
        project_root,
        expected_identity=expected_created_identity,
        existed_before=False,
        created_identity=expected_created_identity,
        promoted_final_present=False,
    )


def launcher_bytes(target: str) -> bytes:
    version = _version(target)
    if version is None:
        raise ProjectRuntimeError("project_runtime_target_version_invalid")
    # The lightweight bootstrap first ships in v0.4.19. A newer updater must
    # not rewrite an older target launcher to import a module its wheel lacks.
    entry_module = (
        "wom_kit.cli_entry"
        if tuple(int(part) for part in version.split(".")) >= (0, 4, 19)
        else "wom_kit.archive_cli"
    )
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        'set "PYTHONDONTWRITEBYTECODE=1"\r\n'
        'set "PYTHONNOUSERSITE=1"\r\n'
        'set "PYTHONSAFEPATH=1"\r\n'
        f'"%~dp0..\\runtimes\\v{version}\\Scripts\\python.exe" '
        f'-I -B -X utf8 -m {entry_module} %*\r\n'
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
    main_loaded = sys.modules.get("__main__")
    package_loaded = sys.modules.get("wom_kit")

    # New launchers use cli_entry, which imports archive_cli canonically.
    # Historical launchers use ``python -m wom_kit.archive_cli``: there the
    # executing module is ``__main__`` and need not also have its canonical
    # import name. Accept that old alias only for the exact WOM import spec;
    # the expected runtime path, real-component checks, receipt inventory,
    # size, and digest are still verified below.
    archive_cli_module_candidate: str | Path | None = (
        running_archive_cli_module_path
    )
    if archive_cli_module_candidate is None:
        archive_cli_module_candidate = getattr(
            archive_cli_loaded,
            "__file__",
            None,
        )
    if archive_cli_module_candidate is None:
        main_spec = getattr(main_loaded, "__spec__", None)
        main_spec_name = getattr(main_spec, "name", None)
        main_file = getattr(main_loaded, "__file__", None)
        main_origin = getattr(main_spec, "origin", None)
        if (
            main_spec_name == "wom_kit.archive_cli"
            and isinstance(main_file, (str, Path))
            and str(main_file)
            and isinstance(main_origin, (str, Path))
            and str(main_origin)
            and _same_absolute_path(Path(main_file), Path(main_origin))
        ):
            archive_cli_module_candidate = main_file
    archive_cli_module_path = (
        Path(os.path.abspath(str(archive_cli_module_candidate)))
        if archive_cli_module_candidate is not None
        and str(archive_cli_module_candidate)
        else None
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
    launcher_observation_state = str(
        launcher.get("observation_state") or "passed"
    )
    inspection_truth = runtime_inspection_truth(inspection)
    static_receipt_aligned = bool(
        inspection.get("static_receipt_valid")
        and inspection.get("target_version") == version
        and inspection.get("path") == runtime_logical_path(version)
    )
    inspection_static_receipt_aligned = static_receipt_aligned
    live_payload_aligned = bool(
        static_receipt_aligned and inspection.get("live_payload_aligned") is True
    )
    reported_live_payload_state = inspection.get("live_payload_state")
    live_payload_state = str(
        reported_live_payload_state
        if reported_live_payload_state is not None
        else "passed"
        if live_payload_aligned
        else "failed"
        if static_receipt_aligned
        else "not_reached"
    )
    if live_payload_state not in {
        "passed",
        "failed",
        "not_reached",
        "unavailable",
    }:
        live_payload_state = "unavailable"
    reported_live_payload_reason = inspection.get("live_payload_reason_code")
    live_payload_reason_code = str(
        reported_live_payload_reason
        if reported_live_payload_reason is not None
        else "project_runtime_live_payload_verified"
        if live_payload_aligned
        else "project_runtime_live_payload_mismatch"
        if static_receipt_aligned
        else "project_runtime_static_receipt_invalid"
    )
    receipt_path = final / PROJECT_RUNTIME_RECEIPT_NAME
    live_receipt_bytes: bytes | None = None
    if inspection_truth["state"] != "passed":
        receipt_generation_aligned = False
        receipt_generation_state = "not_reached"
        receipt_generation_reason_code = str(inspection_truth["reason_code"])
    else:
        try:
            receipt_path.lstat()
        except FileNotFoundError:
            receipt_generation_aligned = False
            receipt_generation_state = "failed"
            receipt_generation_reason_code = (
                "project_runtime_receipt_generation_changed"
            )
        except OSError:
            receipt_generation_aligned = False
            receipt_generation_state = "unavailable"
            receipt_generation_reason_code = (
                "project_runtime_receipt_generation_unavailable"
            )
        else:
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
            receipt_generation_state = (
                "passed"
                if receipt_generation_aligned
                else "unavailable"
                if live_receipt_bytes is None
                else "failed"
            )
            receipt_generation_reason_code = (
                "project_runtime_receipt_generation_verified"
                if receipt_generation_aligned
                else "project_runtime_receipt_generation_unavailable"
                if live_receipt_bytes is None
                else "project_runtime_receipt_generation_changed"
            )
    if not receipt_generation_aligned:
        static_receipt_aligned = False
        live_payload_aligned = False
        live_payload_state = receipt_generation_state
        live_payload_reason_code = receipt_generation_reason_code
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
    executable_observation = _real_component_snapshot_observation(
        root,
        executable,
        target_must_exist=True,
    )
    module_observation = _real_component_snapshot_observation(
        root,
        module_path,
        target_must_exist=True,
    )
    prefix_observation = _real_component_snapshot_observation(
        root,
        prefix,
        target_must_exist=True,
    )
    executable_identity_aligned = _same_absolute_path(
        executable,
        expected_python,
    )
    module_identity_aligned = bool(
        _path_is_within(module_path, final) and wom_module_layout
    )
    prefix_identity_aligned = _same_absolute_path(prefix, final)
    executable_aligned = bool(
        executable_identity_aligned
        and executable_observation["state"] == "passed"
    )
    module_aligned = bool(
        module_identity_aligned
        and module_observation["state"] == "passed"
    )
    prefix_aligned = bool(
        prefix_identity_aligned
        and prefix_observation["state"] == "passed"
    )
    executable_receipt_bound = False
    module_receipt_bound = False
    executable_receipt_observation_unavailable = False
    module_receipt_observation_unavailable = False
    core_modules_receipt_bound = False
    binding_read_unavailable = False
    core_binding_deterministic_failure = False
    core_module_bindings: dict[str, dict[str, Any]] = {
        label: {
            "observed": False,
            "expected_identity": False,
            "inventory_entry_present": False,
            "bytes_receipt_bound": False,
            "reason_code": f"project_runtime_core_{label}_not_checked",
            "absolute_paths_echoed": False,
            "hashes_echoed": False,
        }
        for label in ("archive_cli", "project_runtime", "package_origin")
    }
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
            live_payload_state = (
                "passed" if live_payload_aligned else "failed"
            )
            live_payload_reason_code = (
                "project_runtime_live_payload_verified"
                if live_payload_aligned
                else "project_runtime_live_payload_mismatch"
            )

            def receipt_bound_file(
                candidate: Path | None,
            ) -> tuple[bool, bool]:
                if candidate is None:
                    return False, False
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
                    return False, True
                return (
                    bool(
                        live_payload_aligned
                        and expected is not None
                        and expected == (actual_size, actual_digest)
                    ),
                    False,
                )

            (
                executable_receipt_bound,
                executable_receipt_observation_unavailable,
            ) = receipt_bound_file(executable)
            (
                module_receipt_bound,
                module_receipt_observation_unavailable,
            ) = receipt_bound_file(module_path)
            binding_read_unavailable = bool(
                executable_receipt_observation_unavailable
                or module_receipt_observation_unavailable
            )
            expected_core_paths = (
                (
                    "archive_cli",
                    archive_cli_module_path,
                    final
                    / "Lib"
                    / "site-packages"
                    / "wom_kit"
                    / "archive_cli.py",
                ),
                (
                    "project_runtime",
                    project_runtime_module_path,
                    final
                    / "Lib"
                    / "site-packages"
                    / "wom_kit"
                    / "project_runtime.py",
                ),
                (
                    "package_origin",
                    package_origin_path,
                    final / "Lib" / "site-packages" / "wom_kit" / "__init__.py",
                ),
            )
            core_module_bindings = {}
            for label, observed, expected in expected_core_paths:
                observed_available = observed is not None
                expected_identity = bool(
                    observed_available
                    and _same_absolute_path(observed, expected)
                )
                try:
                    observed_logical = (
                        Path(os.path.abspath(str(observed)))
                        .relative_to(Path(os.path.abspath(str(final))))
                        .as_posix()
                        if observed is not None
                        else None
                    )
                except (OSError, RuntimeError, ValueError):
                    observed_logical = None
                inventory_entry_present = bool(
                    observed_logical is not None
                    and observed_logical in inventory_by_path
                )
                if expected_identity:
                    (
                        bytes_receipt_bound,
                        bytes_observation_unavailable,
                    ) = receipt_bound_file(observed)
                else:
                    bytes_receipt_bound = False
                    bytes_observation_unavailable = False
                binding_read_unavailable = bool(
                    binding_read_unavailable
                    or bytes_observation_unavailable
                )
                if (
                    not observed_available
                    or not expected_identity
                    or not inventory_entry_present
                    or (
                        not bytes_receipt_bound
                        and not bytes_observation_unavailable
                    )
                ):
                    core_binding_deterministic_failure = True
                if not observed_available:
                    detail_reason = (
                        f"project_runtime_core_{label}_unobserved"
                    )
                elif not expected_identity:
                    detail_reason = (
                        f"project_runtime_core_{label}_identity_mismatch"
                    )
                elif not inventory_entry_present:
                    detail_reason = (
                        f"project_runtime_core_{label}_inventory_missing"
                    )
                elif bytes_observation_unavailable:
                    detail_reason = (
                        f"project_runtime_core_{label}_observation_unavailable"
                    )
                elif not bytes_receipt_bound:
                    detail_reason = (
                        f"project_runtime_core_{label}_bytes_not_receipt_bound"
                    )
                else:
                    detail_reason = (
                        f"project_runtime_core_{label}_receipt_bound"
                    )
                core_module_bindings[label] = {
                    "observed": observed_available,
                    "expected_identity": expected_identity,
                    "inventory_entry_present": inventory_entry_present,
                    "bytes_receipt_bound": bytes_receipt_bound,
                    "reason_code": detail_reason,
                    "absolute_paths_echoed": False,
                    "hashes_echoed": False,
                }
            core_modules_receipt_bound = all(
                item["bytes_receipt_bound"]
                for item in core_module_bindings.values()
            )
        except ProjectRuntimeError as error:
            live_payload_aligned = False
            (
                live_payload_state,
                live_payload_reason_code,
            ) = _live_payload_observation_error(error)
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
    process_observation_states = (
        str(executable_observation["state"]),
        str(module_observation["state"]),
        str(prefix_observation["state"]),
    )
    failure_reason_code: str | None = None
    if launcher_observation_state == "failed" or (
        launcher_observation_state == "passed" and not launcher_aligned
    ):
        failure_reason_code = "project_runtime_launcher_mismatch"
    elif inspection_truth["state"] == "failed":
        failure_reason_code = str(inspection_truth["reason_code"])
    elif receipt_generation_state == "failed":
        failure_reason_code = receipt_generation_reason_code
    elif live_payload_state == "failed":
        failure_reason_code = live_payload_reason_code
    elif (
        not executable_identity_aligned
        or not module_identity_aligned
        or not prefix_identity_aligned
        or "failed" in process_observation_states
    ):
        failure_reason_code = "project_runtime_process_binding_mismatch"
    elif (
        live_payload_aligned
        and executable_aligned
        and module_aligned
        and (
            (
                not executable_receipt_bound
                and not executable_receipt_observation_unavailable
            )
            or (
                not module_receipt_bound
                and not module_receipt_observation_unavailable
            )
        )
    ):
        failure_reason_code = (
            "project_runtime_process_bytes_not_receipt_bound"
        )
    elif (
        live_payload_aligned
        and executable_aligned
        and module_aligned
        and core_binding_deterministic_failure
    ):
        failure_reason_code = (
            "project_runtime_core_modules_not_receipt_bound"
        )
    elif not isolated or not no_bytecode:
        failure_reason_code = (
            "project_runtime_canonical_launcher_flags_missing"
        )

    observation_unavailable = bool(
        launcher_observation_state == "unavailable"
        or inspection_truth["state"] == "unavailable"
        or receipt_generation_state == "unavailable"
        or live_payload_state == "unavailable"
        or "unavailable" in process_observation_states
        or binding_read_unavailable
    )
    if bound:
        reason_code = "current_project_runtime_bound"
        observation_state = "passed"
    elif failure_reason_code is not None:
        reason_code = failure_reason_code
        observation_state = "failed"
    elif launcher_observation_state == "unavailable":
        reason_code = "project_runtime_launcher_observation_unavailable"
        observation_state = "unavailable"
    elif inspection_truth["state"] == "unavailable":
        reason_code = str(inspection_truth["reason_code"])
        observation_state = "unavailable"
    elif receipt_generation_state == "unavailable":
        reason_code = receipt_generation_reason_code
        observation_state = "unavailable"
    elif live_payload_state == "unavailable":
        reason_code = live_payload_reason_code
        observation_state = "unavailable"
    elif observation_unavailable:
        reason_code = "project_runtime_process_binding_observation_unavailable"
        observation_state = "unavailable"
    else:
        # Every known deterministic mismatch is selected above.  Keep this
        # closed fallback deterministic rather than misreporting an
        # unclassified contradiction as an observation outage.
        reason_code = "project_runtime_process_binding_mismatch"
        observation_state = "failed"
    return {
        "bound": bound,
        "reason_code": reason_code,
        "observation_state": observation_state,
        "launcher_aligned": launcher_aligned,
        "static_receipt_aligned": static_receipt_aligned,
        "receipt_generation_aligned": receipt_generation_aligned,
        "receipt_generation_state": receipt_generation_state,
        "receipt_generation_reason_code": receipt_generation_reason_code,
        "live_payload_aligned": live_payload_aligned,
        "live_payload_state": live_payload_state,
        "live_payload_reason_code": live_payload_reason_code,
        "running_executable_aligned": executable_aligned,
        "running_module_aligned": module_aligned,
        "running_prefix_aligned": prefix_aligned,
        "running_executable_receipt_bound": executable_receipt_bound,
        "running_module_receipt_bound": module_receipt_bound,
        "core_modules_receipt_bound": core_modules_receipt_bound,
        "core_module_bindings": core_module_bindings,
        "isolated_mode": isolated,
        "dont_write_bytecode": no_bytecode,
        "verification_scope": "current_process_operational_binding",
        "project_runtime_argv": project_runtime_argv(),
        "private_values_echoed": False,
        "absolute_paths_echoed": False,
    }


def runtime_inspection_truth(
    inspection: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize one runtime inspection without collapsing four-state truth."""

    status = str(inspection.get("status") or "")
    static_state = str(
        inspection.get("static_receipt_state") or ""
    )
    if status == "unavailable" or static_state == "unavailable":
        return {
            "state": "unavailable",
            "reason_code": str(
                inspection.get("static_receipt_reason_code")
                or "project_runtime_static_receipt_unavailable"
            ),
            "private_values_echoed": False,
        }
    if inspection.get("receipt_candidate_valid") is True:
        reported_state = inspection.get("live_payload_state")
        state = str(reported_state) if reported_state is not None else "passed"
        if state not in {"passed", "failed", "not_reached", "unavailable"}:
            state = "unavailable"
        reason_code = str(
            inspection.get("live_payload_reason_code")
            or (
                "project_runtime_live_payload_verified"
                if state == "passed"
                else "project_runtime_live_payload_unavailable"
            )
        )
        if state == "passed":
            return {
                "state": "passed",
                "reason_code": "project_runtime_live_payload_verified",
                "private_values_echoed": False,
            }
        return {
            "state": state,
            "reason_code": reason_code,
            "private_values_echoed": False,
        }
    if status == "missing":
        return {
            "state": "failed",
            "reason_code": "project_runtime_missing",
            "private_values_echoed": False,
        }
    if status == "unsafe":
        return {
            "state": "failed",
            "reason_code": "project_runtime_target_directory_invalid",
            "private_values_echoed": False,
        }
    if status == "invalid_target":
        return {
            "state": "failed",
            "reason_code": "project_runtime_target_version_invalid",
            "private_values_echoed": False,
        }
    if inspection.get("static_receipt_valid") is not True:
        return {
            "state": "failed",
            "reason_code": "project_runtime_static_receipt_invalid",
            "private_values_echoed": False,
        }
    reported_state = str(
        inspection.get("live_payload_state") or "unavailable"
    )
    state = (
        reported_state
        if reported_state in {"failed", "not_reached", "unavailable"}
        else "failed"
    )
    reason_code = str(
        inspection.get("live_payload_reason_code")
        or (
            "project_runtime_live_payload_mismatch"
            if state == "failed"
            else "project_runtime_live_payload_unavailable"
        )
    )
    return {
        "state": state,
        "reason_code": reason_code,
        "private_values_echoed": False,
    }


_RUNNING_ARCHIVE_CLI_MODULE_UNSET = object()


def project_write_guard(
    inspection_root: Path,
    *,
    running_version: str,
    running_module_path: str | Path | None = None,
    running_archive_cli_module_path: str | Path | None | object = _RUNNING_ARCHIVE_CLI_MODULE_UNSET,
) -> dict[str, Any]:
    """Return a content-free blocker when a project pin and runtime differ.

    Existing callers bind their running module as the CLI, unchanged. A
    non-CLI caller may pass an explicit None CLI origin to observe the real
    loaded canonical/legacy CLI instead; this does not waive any core check.
    """

    root = Path(os.path.abspath(str(inspection_root)))
    search_roots = [root]
    archive_config = root / "archive.yml"
    try:
        archive_config_stat = archive_config.lstat()
    except FileNotFoundError:
        archive_config_stat = None
    except OSError:
        return {
            "blocked": True,
            "reason_code": "project_runtime_unavailable",
            "detail_reason_code": "project_root_observation_unavailable",
            "runtime_inspection_state": "unavailable",
            "project_runtime_argv": project_runtime_argv(),
            "private_values_echoed": False,
            "absolute_paths_echoed": False,
        }
    if archive_config_stat is not None:
        archive_config_observation = _real_component_snapshot_observation(
            root,
            archive_config,
            target_must_exist=True,
        )
        if archive_config_observation["state"] != "passed" or not (
            stat_module.S_ISREG(archive_config_stat.st_mode)
            and not stat_module.S_ISLNK(archive_config_stat.st_mode)
            and not _is_reparse_stat(archive_config_stat)
        ):
            return {
                "blocked": True,
                "reason_code": (
                    "project_runtime_unavailable"
                    if archive_config_observation["state"] == "unavailable"
                    else "project_runtime_mismatch"
                ),
                "detail_reason_code": (
                    "project_root_observation_unavailable"
                    if archive_config_observation["state"] == "unavailable"
                    else "project_archive_root_binding_unsafe"
                ),
                "runtime_inspection_state": (
                    "unavailable"
                    if archive_config_observation["state"] == "unavailable"
                    else "failed"
                ),
                "project_runtime_argv": project_runtime_argv(),
                "private_values_echoed": False,
                "absolute_paths_echoed": False,
            }
        if root.parent != root:
            search_roots.append(root.parent)
    for project_root in search_roots:
        update_lock_path = (
            project_root / ".zettel-kasten" / "version-update.lock"
        )
        try:
            update_lock_path.lstat()
            update_lock_present = True
        except FileNotFoundError:
            update_lock_present = False
        except OSError:
            return {
                "blocked": True,
                "reason_code": "project_runtime_unavailable",
                "detail_reason_code": "project_update_lock_observation_unavailable",
                "runtime_inspection_state": "unavailable",
                "project_runtime_argv": project_runtime_argv(),
                "private_values_echoed": False,
                "absolute_paths_echoed": False,
            }
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
            pin_stat = pin_path.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return {
                "blocked": True,
                "reason_code": "project_runtime_unavailable",
                "detail_reason_code": "project_runtime_pin_observation_unavailable",
                "runtime_inspection_state": "unavailable",
                "project_runtime_argv": project_runtime_argv(),
                "private_values_echoed": False,
                "absolute_paths_echoed": False,
            }
        pin_observation = _real_component_snapshot_observation(
            project_root,
            pin_path,
            target_must_exist=True,
        )
        if (
            pin_observation["state"] == "unavailable"
        ):
            return {
                "blocked": True,
                "reason_code": "project_runtime_unavailable",
                "detail_reason_code": "project_runtime_pin_observation_unavailable",
                "runtime_inspection_state": "unavailable",
                "project_runtime_argv": project_runtime_argv(),
                "private_values_echoed": False,
                "absolute_paths_echoed": False,
            }
        if (
            pin_observation["state"] != "passed"
            or not stat_module.S_ISREG(pin_stat.st_mode)
            or stat_module.S_ISLNK(pin_stat.st_mode)
            or _is_reparse_stat(pin_stat)
        ):
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
        if pin_bytes is None:
            return {
                "blocked": True,
                "reason_code": "project_runtime_unavailable",
                "detail_reason_code": "project_runtime_pin_observation_unavailable",
                "runtime_inspection_state": "unavailable",
                "project_runtime_argv": project_runtime_argv(),
                "private_values_echoed": False,
                "absolute_paths_echoed": False,
            }
        try:
            pinned_version = _version((pin_bytes or b"").decode("utf-8-sig").strip())
        except UnicodeError:
            pinned_version = None
        running = _version(running_version)
        runtime_inspection_state = "not_reached"
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
            core_module_bindings: dict[str, Any] | None = None
        else:
            minimum = _version("0.4.3")
            runtime_required = bool(
                minimum is not None
                and tuple(int(part) for part in pinned_version.split("."))
                >= tuple(int(part) for part in minimum.split("."))
            )
            if runtime_required:
                installed = inspect_runtime(project_root, pinned_version)
                inspection_truth = runtime_inspection_truth(installed)
                runtime_inspection_state = str(
                    inspection_truth["state"]
                )
                binding = current_project_runtime_binding(
                    project_root,
                    pinned_version,
                    running_module_path=running_module_path,
                    running_archive_cli_module_path=(
                        running_module_path
                        if running_archive_cli_module_path is _RUNNING_ARCHIVE_CLI_MODULE_UNSET
                        else running_archive_cli_module_path
                    ),
                    runtime_inspection=installed,
                )
                binding_observation_state = str(
                    binding.get("observation_state")
                    or (
                        "passed"
                        if binding.get("bound") is True
                        else runtime_inspection_state
                        if runtime_inspection_state
                        in {"failed", "not_reached", "unavailable"}
                        else "failed"
                    )
                )
                combined_states = {
                    runtime_inspection_state,
                    binding_observation_state,
                }
                runtime_inspection_state = (
                    "failed"
                    if "failed" in combined_states
                    else "unavailable"
                    if "unavailable" in combined_states
                    else "not_reached"
                    if "not_reached" in combined_states
                    else "passed"
                )
                blocked = bool(
                    inspection_truth["state"] != "passed"
                    or not binding.get("bound")
                )
                detail_reason_code = (
                    str(inspection_truth["reason_code"])
                    if inspection_truth["state"] == "failed"
                    else str(binding.get("reason_code"))
                    if binding_observation_state == "failed"
                    else str(inspection_truth["reason_code"])
                    if inspection_truth["state"] != "passed"
                    else str(binding.get("reason_code"))
                )
                binding_details = binding.get("core_module_bindings")
                core_module_bindings = (
                    dict(binding_details)
                    if isinstance(binding_details, dict)
                    else None
                )
            else:
                blocked = False
                detail_reason_code = "project_runtime_version_aligned"
                core_module_bindings = None
        return {
            "blocked": blocked,
            "reason_code": (
                "project_runtime_unavailable"
                if blocked and runtime_inspection_state == "unavailable"
                else "project_runtime_mismatch"
                if blocked
                else "project_runtime_version_aligned"
            ),
            "detail_reason_code": detail_reason_code,
            "runtime_inspection_state": runtime_inspection_state,
            "project_pin": f"v{pinned_version}",
            "running_version": f"v{running}" if running else None,
            "project_runtime_argv": project_runtime_argv(),
            "core_module_bindings": core_module_bindings,
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
    observation_state = "passed"
    observation_reason_code = "verified"
    try:
        path_stat = path.lstat()
        present = True
    except FileNotFoundError:
        path_stat = None
        present = False
    except OSError:
        path_stat = None
        present = True
        observation_state = "unavailable"
        observation_reason_code = "project_runtime_launcher_observation_unavailable"
    component_observation = _real_component_snapshot_observation(
        project_root,
        path,
        target_must_exist=present,
    )
    if component_observation["state"] == "unavailable":
        observation_state = "unavailable"
        observation_reason_code = "project_runtime_launcher_observation_unavailable"
    known_unsafe = bool(
        present
        and path_stat is not None
        and (
            not stat_module.S_ISREG(path_stat.st_mode)
            or stat_module.S_ISLNK(path_stat.st_mode)
            or _is_reparse_stat(path_stat)
            or component_observation["state"] == "failed"
        )
    )
    if known_unsafe:
        observation_state = "failed"
        observation_reason_code = "project_runtime_launcher_path_unsafe"
    previous = (
        _read_limited(
            path,
            limit=64 * 1024,
            ancestor_root=project_root,
        )
        if present and observation_state == "passed"
        else None
    )
    if present and observation_state == "passed" and previous is None:
        observation_state = "unavailable"
        observation_reason_code = "project_runtime_launcher_observation_unavailable"
    target_bytes = launcher_bytes(target)
    return {
        "path": path,
        "logical": PROJECT_RUNTIME_LAUNCHER_RELATIVE.as_posix(),
        "existed": present and previous is not None,
        "previous_bytes": previous,
        "target_bytes": target_bytes,
        "already_target": previous == target_bytes,
        "unsafe": known_unsafe,
        "observation_state": observation_state,
        "observation_reason_code": observation_reason_code,
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
            "static_receipt_state": "not_reached",
            "static_receipt_reason_code": (
                "project_runtime_target_version_invalid"
            ),
            "live_payload_aligned": False,
            "live_payload_state": "not_reached",
            "live_payload_reason_code": "project_runtime_target_version_invalid",
            "absolute_paths_echoed": False,
        }
    root = Path(os.path.abspath(str(project_root)))
    final = runtime_path(root, version)
    logical = runtime_logical_path(version)
    receipt_path = final / PROJECT_RUNTIME_RECEIPT_NAME
    try:
        final_stat = final.lstat()
    except FileNotFoundError:
        return {
            "status": "missing",
            "verified": False,
            "receipt_candidate_valid": False,
            "static_receipt_valid": False,
            "static_receipt_state": "failed",
            "static_receipt_reason_code": "project_runtime_missing",
            "live_payload_aligned": False,
            "live_payload_state": "not_reached",
            "live_payload_reason_code": "project_runtime_missing",
            "path": logical,
            "receipt_sha256": None,
            "absolute_paths_echoed": False,
        }
    except OSError:
        return {
            "status": "unavailable",
            "verified": False,
            "receipt_candidate_valid": False,
            "static_receipt_valid": False,
            "static_receipt_state": "unavailable",
            "static_receipt_reason_code": (
                "project_runtime_target_observation_unavailable"
            ),
            "live_payload_aligned": False,
            "live_payload_state": "not_reached",
            "live_payload_reason_code": (
                "project_runtime_target_observation_unavailable"
            ),
            "path": logical,
            "receipt_sha256": None,
            "absolute_paths_echoed": False,
        }
    final_observation = _real_component_snapshot_observation(
        root,
        final,
        target_must_exist=True,
    )
    if (
        not stat_module.S_ISDIR(final_stat.st_mode)
        or _is_reparse_stat(final_stat)
        or final_observation["state"] == "failed"
    ):
        return {
            "status": "unsafe",
            "verified": False,
            "receipt_candidate_valid": False,
            "static_receipt_valid": False,
            "static_receipt_state": "failed",
            "static_receipt_reason_code": (
                "project_runtime_target_directory_invalid"
            ),
            "live_payload_aligned": False,
            "live_payload_state": "not_reached",
            "live_payload_reason_code": "project_runtime_target_directory_invalid",
            "path": logical,
            "receipt_sha256": None,
            "absolute_paths_echoed": False,
        }
    if final_observation["state"] == "unavailable":
        return {
            "status": "unavailable",
            "verified": False,
            "receipt_candidate_valid": False,
            "static_receipt_valid": False,
            "static_receipt_state": "unavailable",
            "static_receipt_reason_code": (
                "project_runtime_target_observation_unavailable"
            ),
            "live_payload_aligned": False,
            "live_payload_state": "not_reached",
            "live_payload_reason_code": (
                "project_runtime_target_observation_unavailable"
            ),
            "path": logical,
            "receipt_sha256": None,
            "absolute_paths_echoed": False,
        }
    try:
        receipt_stat = receipt_path.lstat()
    except FileNotFoundError:
        receipt_stat = None
    except OSError:
        return {
            "status": "unavailable",
            "verified": False,
            "receipt_candidate_valid": False,
            "static_receipt_valid": False,
            "static_receipt_state": "unavailable",
            "static_receipt_reason_code": (
                "project_runtime_static_receipt_unavailable"
            ),
            "live_payload_aligned": False,
            "live_payload_state": "not_reached",
            "live_payload_reason_code": (
                "project_runtime_static_receipt_unavailable"
            ),
            "path": logical,
            "receipt_sha256": None,
            "absolute_paths_echoed": False,
        }
    receipt_observation = _real_component_snapshot_observation(
        root,
        receipt_path,
        target_must_exist=True,
    )
    if receipt_observation["state"] == "unavailable":
        return {
            "status": "unavailable",
            "verified": False,
            "receipt_candidate_valid": False,
            "static_receipt_valid": False,
            "static_receipt_state": "unavailable",
            "static_receipt_reason_code": (
                "project_runtime_static_receipt_unavailable"
            ),
            "live_payload_aligned": False,
            "live_payload_state": "not_reached",
            "live_payload_reason_code": (
                "project_runtime_static_receipt_unavailable"
            ),
            "path": logical,
            "receipt_sha256": None,
            "absolute_paths_echoed": False,
        }
    if (
        receipt_stat is not None
        and (
            not stat_module.S_ISREG(receipt_stat.st_mode)
            or stat_module.S_ISLNK(receipt_stat.st_mode)
            or _is_reparse_stat(receipt_stat)
        )
    ):
        return {
            "status": "unsafe",
            "verified": False,
            "receipt_candidate_valid": False,
            "static_receipt_valid": False,
            "static_receipt_state": "failed",
            "static_receipt_reason_code": (
                "project_runtime_static_receipt_unsafe"
            ),
            "live_payload_aligned": False,
            "live_payload_state": "not_reached",
            "live_payload_reason_code": (
                "project_runtime_static_receipt_unsafe"
            ),
            "path": logical,
            "receipt_sha256": None,
            "absolute_paths_echoed": False,
        }
    if (
        receipt_stat is None
        or receipt_observation["state"] == "failed"
        or receipt_stat.st_size < 0
        or receipt_stat.st_size > 2 * 1024 * 1024
    ):
        receipt_bytes = None
        static_receipt_state = "failed"
        static_receipt_reason_code = "project_runtime_static_receipt_invalid"
    else:
        receipt_bytes = _read_limited(
            receipt_path,
            limit=2 * 1024 * 1024,
            ancestor_root=root,
        )
        if receipt_bytes is None:
            return {
                "status": "unavailable",
                "verified": False,
                "receipt_candidate_valid": False,
                "static_receipt_valid": False,
                "static_receipt_state": "unavailable",
                "static_receipt_reason_code": (
                    "project_runtime_static_receipt_unavailable"
                ),
                "live_payload_aligned": False,
                "live_payload_state": "not_reached",
                "live_payload_reason_code": (
                    "project_runtime_static_receipt_unavailable"
                ),
                "path": logical,
                "receipt_sha256": None,
                "absolute_paths_echoed": False,
            }
        static_receipt_state = "failed"
        static_receipt_reason_code = "project_runtime_static_receipt_invalid"
    try:
        receipt = _json_without_duplicate_keys(receipt_bytes or b"")
    except (UnicodeError, json.JSONDecodeError, ValueError):
        receipt = None
    expected_sha = str(expected_wheel_sha256 or "").removeprefix("sha256:") or None
    expected_lock_sha = (
        str(expected_supply_lock_sha256 or "").removeprefix("sha256:") or None
    )
    verification = receipt.get("verification") if isinstance(receipt, dict) else None
    receipt_schema_name = (
        "project-runtime-receipt-v0.2.schema.json"
        if isinstance(receipt, dict)
        and receipt.get("schema") == PROJECT_RUNTIME_REPAIR_RECEIPT_SCHEMA
        else "project-runtime-receipt-v0.1.schema.json"
        if isinstance(receipt, dict)
        and receipt.get("schema") == PROJECT_RUNTIME_RECEIPT_SCHEMA
        else None
    )
    receipt_schema_valid = bool(
        isinstance(receipt, dict)
        and receipt_schema_name is not None
        and not validate_schema(receipt, receipt_schema_name)
    )
    python_executable = final / "Scripts" / "python.exe"
    static_receipt_valid = bool(
        receipt_schema_valid
        and receipt.get("schema")
        in {
            PROJECT_RUNTIME_RECEIPT_SCHEMA,
            PROJECT_RUNTIME_REPAIR_RECEIPT_SCHEMA,
        }
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
    if static_receipt_valid:
        static_receipt_state = "passed"
        static_receipt_reason_code = "project_runtime_static_receipt_verified"
    required_python_safe = False
    live_payload_sha256: str | None = None
    live_payload_aligned = False
    live_payload_state = "not_reached"
    live_payload_reason_code = "project_runtime_static_receipt_invalid"
    if static_receipt_valid:
        try:
            try:
                python_stat = python_executable.lstat()
            except FileNotFoundError as error:
                raise ProjectRuntimeError(
                    "project_runtime_required_python_missing"
                ) from error
            except OSError as error:
                raise ProjectRuntimeError(
                    "project_runtime_required_python_unavailable"
                ) from error
            python_observation = _real_component_snapshot_observation(
                root,
                python_executable,
                target_must_exist=True,
            )
            if python_observation["state"] == "unavailable":
                raise ProjectRuntimeError(
                    "project_runtime_required_python_unavailable"
                )
            if (
                python_observation["state"] != "passed"
                or not stat_module.S_ISREG(python_stat.st_mode)
                or stat_module.S_ISLNK(python_stat.st_mode)
                or _is_reparse_stat(python_stat)
            ):
                raise ProjectRuntimeError(
                    "project_runtime_required_python_unsafe"
                )
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
            live_payload_state = (
                "passed" if live_payload_aligned else "failed"
            )
            live_payload_reason_code = (
                "project_runtime_live_payload_verified"
                if live_payload_aligned
                else "project_runtime_live_payload_mismatch"
            )
        except ProjectRuntimeError as error:
            required_python_safe = False
            live_payload_aligned = False
            (
                live_payload_state,
                live_payload_reason_code,
            ) = _live_payload_observation_error(error)
        except (OSError, RuntimeError, ValueError):
            required_python_safe = False
            live_payload_aligned = False
            live_payload_state = "unavailable"
            live_payload_reason_code = "project_runtime_live_payload_unavailable"
    valid = bool(static_receipt_valid and required_python_safe and live_payload_aligned)
    return {
        "status": "receipt_candidate" if valid else "invalid",
        "verified": False,
        "receipt_candidate_valid": valid,
        "static_receipt_valid": static_receipt_valid,
        "static_receipt_state": static_receipt_state,
        "static_receipt_reason_code": static_receipt_reason_code,
        "live_payload_aligned": live_payload_aligned,
        "live_payload_state": live_payload_state,
        "live_payload_reason_code": live_payload_reason_code,
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


def _verify_existing_runtime_support_files(
    final: Path,
    inventory: tuple[RuntimeCandidateInventoryEntry, ...],
) -> None:
    """Authenticate startup bytes before invoking an existing interpreter.

    Wheel verification covers site-packages, not the venv redirectors or its
    configuration. The already trusted bootstrap CPython supplies those
    redirectors; no candidate venv or network request is needed. An unknown
    layout is not eligible for the early no-op path.
    """

    excluded_roots = {PROJECT_RUNTIME_ARTIFACTS_NAME, PROJECT_RUNTIME_RECEIPT_NAME}
    support_files = {
        item.relative_path
        for item in inventory
        if item.entry_type == "file"
        and PurePosixPath(item.relative_path).parts[0] not in excluded_roots
        and not item.relative_path.startswith("Lib/site-packages/")
    }
    if support_files != {"pyvenv.cfg", "Scripts/python.exe", "Scripts/pythonw.exe"}:
        raise ProjectRuntimeError("project_runtime_existing_support_inventory_mismatch")
    base = Path(sys.base_prefix)
    for name in ("python.exe", "pythonw.exe"):
        trusted = base / "Lib" / "venv" / "scripts" / "nt" / name
        if not _existing_components_are_real(base, trusted):
            raise ProjectRuntimeError("project_runtime_trusted_redirector_unavailable")
        try:
            trusted_digest = _sha256_file(trusted, ancestor_root=base)
        except ProjectRuntimeError as error:
            raise ProjectRuntimeError("project_runtime_trusted_redirector_unavailable") from error
        if _sha256_file(final / "Scripts" / name, ancestor_root=final) != trusted_digest:
            raise ProjectRuntimeError("project_runtime_existing_redirector_mismatch")
    cfg = _read_limited(final / "pyvenv.cfg", limit=64 * 1024, ancestor_root=final)
    if cfg is None:
        raise ProjectRuntimeError("project_runtime_existing_pyvenv_unavailable")
    try:
        lines = cfg.decode("utf-8").splitlines()
    except UnicodeError as error:
        raise ProjectRuntimeError("project_runtime_existing_pyvenv_mismatch") from error
    # 'executable' records the original bootstrap path, which can legitimately
    # differ on a later invocation. CPython's startup home must still be the
    # trusted base and must not redirect imports to a historical user path.
    if (
        len(lines) != 4
        or lines[:3] != [
            f"home = {base}",
            "include-system-site-packages = false",
            f"version = {platform.python_version()}",
        ]
        or not lines[3].startswith("executable = ")
        or not Path(lines[3].removeprefix("executable = ")).is_absolute()
    ):
        raise ProjectRuntimeError("project_runtime_existing_pyvenv_mismatch")


def verify_existing_runtime_for_noop(
    project_root: Path,
    *,
    target: str,
    target_commit: str,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
    progress_callback: Callable[[str, str, int | None, int | None], None] | None = None,
) -> dict[str, Any]:
    """Read-only retained-supply proof before preparing a runtime candidate.

    The caller owns the project lock and the Git/ref/pin/source/launcher
    preconditions. Only ``repair_required`` authorizes replacement; observed
    generation drift stays ``failed`` without repair authority. ``unavailable``
    never authorizes replacing an unreadable runtime. Success
    performs real fresh-process checks after authenticating executable and
    package bytes, then re-observes the whole retained tree. No receipt boolean
    alone, download, candidate directory, or new approval is involved.
    """

    drift_failure_codes = {
        "project_runtime_existing_receipt_changed",
        "project_runtime_existing_payload_changed",
        "project_runtime_tree_changed",
        "project_runtime_candidate_concurrent_drift",
    }

    def result(state: str, reason: str, installed: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return {
            "state": state,
            "reason_code": reason,
            "reusable": state == "passed",
            # Observed generation drift is a failed comparison, but not
            # authority to silently prepare a replacement for a moving target.
            "repair_required": state == "failed" and reason not in drift_failure_codes,
            "installed": dict(installed or {}),
            "private_values_echoed": False,
            "absolute_paths_echoed": False,
        }

    version = _version(target)
    if (
        version is None
        or bootstrap.version != version
        or bootstrap.tag != f"v{version}"
        or COMMIT_RE.fullmatch(target_commit) is None
        or project_runtime_supply_lock(supply.raw_bytes, expected_target=target) != supply
    ):
        return result("not_reached", "project_runtime_noop_binding_invalid")
    if not runtime_supply_matches_current_interpreter(supply):
        return result("not_reached", "project_runtime_interpreter_not_locked")
    if progress_callback is not None:
        progress_callback("project-runtime-noop-static", "start", None, None)
    inspection = inspect_runtime(
        project_root,
        target,
        expected_commit=target_commit,
        expected_wheel_sha256=bootstrap.sha256,
        expected_supply_lock_sha256=supply.sha256,
    )
    if inspection.get("receipt_candidate_valid") is not True:
        truth = runtime_inspection_truth(inspection)
        return result(str(truth["state"]), str(truth["reason_code"]), inspection)
    final = runtime_path(project_root, version)
    inventory_before: tuple[RuntimeCandidateInventoryEntry, ...] | None = None
    try:
        root_before = _real_component_snapshot(project_root, final, target_must_exist=True)
        if root_before is None:
            raise ProjectRuntimeError("project_runtime_existing_observation_unavailable")
        inventory_before = _candidate_inventory_snapshot(final)
        if any(item.relative_path == PROJECT_RUNTIME_INSTALLING_NAME for item in inventory_before):
            raise ProjectRuntimeError("project_runtime_existing_install_incomplete")
        receipt_bytes = _read_limited(final / PROJECT_RUNTIME_RECEIPT_NAME, limit=2 * 1024 * 1024, ancestor_root=project_root)
        if receipt_bytes is None:
            raise ProjectRuntimeError("project_runtime_existing_receipt_unavailable")
        if inspection.get("receipt_sha256") != f"sha256:{_sha256_bytes(receipt_bytes)}":
            raise ProjectRuntimeError("project_runtime_existing_receipt_changed")
        receipt = _candidate_receipt_document(receipt_bytes)
        if receipt.get("wheel_file_name") != bootstrap.file_name:
            raise ProjectRuntimeError("project_runtime_existing_receipt_mismatch")
        _inventory, retained_wheels, _top = _verify_retained_artifacts(
            final,
            bootstrap=bootstrap,
            supply=supply,
            receipt_inventory=receipt.get("artifact_inventory"),
        )
        _verify_existing_runtime_support_files(final, inventory_before)
        if _candidate_inventory_snapshot(final) != inventory_before:
            raise ProjectRuntimeError("project_runtime_existing_payload_changed")
        if progress_callback is not None:
            progress_callback("project-runtime-noop-static", "done", None, None)
        # The process verifier authenticates pip and every importable package
        # against trusted wheels before starting its first target subprocess.
        verification, packages, python_version = _runtime_process_verification(
            final,
            version=version,
            stage_prefix="project-runtime-noop",
            progress_callback=progress_callback,
            bootstrap=bootstrap,
            supply=supply,
            retained_wheels=retained_wheels,
            expected_receipt_packages=receipt.get("installed_distributions"),
            expected_python_version=receipt.get("python_version"),
        )
        if (
            _candidate_inventory_snapshot(final) != inventory_before
            or _real_component_snapshot(project_root, final, target_must_exist=True) != root_before
            or f"sha256:{_runtime_payload_sha256(final)}" != receipt.get("installed_payload_sha256")
        ):
            raise ProjectRuntimeError("project_runtime_existing_payload_changed")
        installed = dict(inspection)
        installed.update({
            "status": "verified",
            "verified": True,
            "verification": verification,
            "python_version": python_version,
            "installed_distributions": packages,
            "verification_basis": "trusted_retained_supply_and_fresh_process",
            "verification_scope": "retained_artifacts_startup_and_live_payload",
            "live_reverification_required_before_reuse": False,
        })
        return result("passed", "project_runtime_existing_verified", installed)
    except ProjectRuntimeError as error:
        reason = str(error)
        # A timeout or unsuccessful probe is not evidence that authenticated
        # installed bytes are corrupt. In particular it must not authorize a
        # replacement candidate after this observational no-op attempt.
        unavailable = _runtime_error_is_observation_unavailable(error) or (
            reason.startswith("project-runtime-noop-")
            and reason.endswith(("_timeout", "_failed"))
        )
        if not unavailable and reason not in drift_failure_codes and inventory_before is not None:
            # A mismatch halfway through static verification may itself have
            # been caused by a concurrent change. Compare the already captured
            # generation before granting repair authority; do not skip this
            # proof merely because the later success-only comparison was not
            # reached. Stable pre-existing corruption still permits repair.
            try:
                inventory_after_error = _candidate_inventory_snapshot(final)
            except ProjectRuntimeError as observation_error:
                if _runtime_error_is_observation_unavailable(observation_error):
                    return result("unavailable", "project_runtime_existing_observation_unavailable")
                return result("failed", "project_runtime_existing_payload_changed")
            except (OSError, UnicodeError, subprocess.SubprocessError):
                return result("unavailable", "project_runtime_existing_observation_unavailable")
            if inventory_after_error != inventory_before:
                return result("failed", "project_runtime_existing_payload_changed")
        return result("unavailable" if unavailable else "failed", reason)
    except (OSError, UnicodeError, subprocess.SubprocessError):
        return result("unavailable", "project_runtime_existing_observation_unavailable")


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
    inspection_truth = runtime_inspection_truth(installed)
    launcher = launcher_snapshot(project_root, target)
    blockers: list[str] = []
    warnings: list[str] = []
    if policy_state == "unavailable":
        blockers.append("project_runtime_policy_unavailable")
    if required and installed["status"] == "unsafe":
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
    if required and launcher.get("observation_state") == "unavailable":
        blockers.append(
            str(
                launcher.get("observation_reason_code")
                or "project_runtime_launcher_observation_unavailable"
            )
        )
    elif required and launcher.get("unsafe"):
        blockers.append("project_runtime_launcher_path_unsafe")
    if required and inspection_truth["state"] == "unavailable":
        blockers.append(str(inspection_truth["reason_code"]))
    if deferred and bootstrap is None:
        warnings.append(
            "Project-runtime policy is deferred until the exact target tag is fetched; approval will fail closed if that tag requires a project runtime and this process is not the exact public release wheel."
        )
    runtime_creation_required = bool(
        required
        and inspection_truth["state"] != "unavailable"
        and not installed.get("receipt_candidate_valid")
    )
    runtime_repair_required = bool(
        required
        and inspection_truth["state"] == "failed"
        and installed.get("status") == "invalid"
    )
    if runtime_repair_required:
        warnings.append(
            "The target project runtime exists but does not match its bound receipt. The approved update will build and fully verify a private replacement, preserve the existing runtime as an exact private recovery preimage, and then repair the target atomically. After durable promotion, later component failures preserve that recovery state for authenticated forward resume instead of automatically rolling the runtime back."
        )
    materialization_required = bool(
        required and inspection_truth["state"] != "unavailable"
    )
    activation_required = bool(required and not launcher.get("already_target"))
    summary = {
        "policy_state": policy_state,
        "required": required,
        "target_path": runtime_logical_path(target),
        "launcher_path": PROJECT_RUNTIME_LAUNCHER_RELATIVE.as_posix(),
        "project_runtime_argv": project_runtime_argv(),
        "installed": installed,
        "inspection_truth": inspection_truth,
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
        "runtime_repair_required": runtime_repair_required,
        # Read-only planning has not yet snapshotted the exact repair tree.
        # It describes what approval preparation must bind and what the active
        # transaction will preserve, without claiming that either already
        # happened.
        "repair_preimage_exactly_bound": False,
        "will_bind_repair_preimage_exactly_before_approval": (
            runtime_repair_required
        ),
        "will_preserve_during_active_transaction": runtime_repair_required,
        "live_reverification_required": required,
        "activation_required": activation_required,
        "active_version_pin": ".zettel-kasten/installed-version.txt",
        "global_path_mutation": False,
        "old_invalid_runtime_deletion_stage": (
            "terminal_cleanup_after_authenticated_success"
            if runtime_repair_required
            else "not_applicable"
        ),
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
        creationflags=noninteractive_creationflags(),
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
                *_stat_identity(root_stat),
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
                        *_stat_identity(entry_stat),
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
    files: list[tuple[str, Path, int, str]] | None = None
    for attempt in range(PROJECT_RUNTIME_TRANSIENT_TREE_SCAN_ATTEMPTS):
        try:
            files = _walk_regular_files(
                runtime,
                require_stable_tree_generation=True,
            )
            break
        except ProjectRuntimeError as error:
            if (
                error.args != ("project_runtime_tree_changed",)
                or attempt == PROJECT_RUNTIME_TRANSIENT_TREE_SCAN_ATTEMPTS - 1
            ):
                raise
            time.sleep(
                PROJECT_RUNTIME_TRANSIENT_TREE_SCAN_BACKOFF_SECONDS
                * (attempt + 1)
            )
    if files is None:
        raise ProjectRuntimeError("project_runtime_tree_changed")
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
            raise ProjectRuntimeError(
                str(runtime_inspection_truth(verified)["reason_code"])
            )
        (final / PROJECT_RUNTIME_INSTALLING_NAME).unlink()
        verified_without_marker = inspect_runtime(
            project_root,
            version,
            expected_commit=target_commit,
            expected_wheel_sha256=bootstrap.sha256,
            expected_supply_lock_sha256=supply.sha256,
        )
        if not verified_without_marker.get("receipt_candidate_valid"):
            raise ProjectRuntimeError(
                str(
                    runtime_inspection_truth(verified_without_marker)[
                        "reason_code"
                    ]
                )
            )
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


# ---------------------------------------------------------------------------
# v0.4.3 complete pre-approval runtime candidate
# ---------------------------------------------------------------------------


def _runtime_path_presence_observation(path: Path) -> dict[str, Any]:
    """Observe one name without collapsing access failure into absence."""

    try:
        path.lstat()
    except FileNotFoundError:
        return {"state": "passed", "present": False}
    except OSError:
        return {"state": "unavailable", "present": None}
    return {"state": "passed", "present": True}


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
            stat_module.S_ISLNK(root_stat.st_mode)
            or _is_reparse(root_stat)
            or not stat_module.S_ISDIR(root_stat.st_mode)
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
                or stat_module.S_ISLNK(stat_result.st_mode)
                or _is_reparse(stat_result)
            ):
                raise ProjectRuntimeError("project_runtime_candidate_unsafe")
            seen.add(folded)
            if stat_module.S_ISDIR(stat_result.st_mode):
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
            elif stat_module.S_ISREG(stat_result.st_mode):
                try:
                    link_count = _file_link_count(Path(entry.path), stat_result)
                except OSError as error:
                    raise ProjectRuntimeError(
                        "project_runtime_candidate_unreadable"
                    ) from error
                if link_count != 1:
                    raise ProjectRuntimeError("project_runtime_candidate_hardlink_unsafe")
                try:
                    digest, size = _sha256_file(
                        Path(entry.path),
                        limit=1024 * 1024 * 1024,
                    )
                    # Re-observe metadata after hashing so a concurrent
                    # replacement cannot be silently sealed.  An inability to
                    # observe is not evidence of drift and must remain an
                    # unavailable, content-free failure.
                    after = Path(entry.path).lstat()
                    after_link_count = _file_link_count(Path(entry.path), after)
                except OSError as error:
                    raise ProjectRuntimeError(
                        "project_runtime_candidate_unreadable"
                    ) from error
                if (
                    stat_module.S_ISLNK(after.st_mode)
                    or _is_reparse(after)
                    or not stat_module.S_ISREG(after.st_mode)
                    or int(after.st_dev) != int(stat_result.st_dev)
                    or int(after.st_ino) != int(stat_result.st_ino)
                    or after_link_count != 1
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
            temporary_presence = _runtime_path_presence_observation(temporary)
            if temporary_presence["state"] == "unavailable":
                raise ProjectRuntimeError(
                    "project_runtime_candidate_detach_observation_unavailable"
                )
            if temporary_presence["present"] is True:
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
    existing_runtime_repair_required: bool,
    existing_runtime_inventory_sha256: str | None,
    runtime_parent_existed_before: bool,
    inventory: tuple[RuntimeCandidateInventoryEntry, ...],
    legacy_shape: bool = False,
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
    if not legacy_shape:
        binding.update(
            {
                "existing_runtime_repair_required": (
                    existing_runtime_repair_required
                ),
                "existing_runtime_inventory_sha256": (
                    None
                    if existing_runtime_inventory_sha256 is None
                    else f"sha256:{existing_runtime_inventory_sha256}"
                ),
            }
        )
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
    schema_name = (
        "project-runtime-receipt-v0.2.schema.json"
        if isinstance(document, dict)
        and document.get("schema") == PROJECT_RUNTIME_REPAIR_RECEIPT_SCHEMA
        else "project-runtime-receipt-v0.1.schema.json"
        if isinstance(document, dict)
        and document.get("schema") == PROJECT_RUNTIME_RECEIPT_SCHEMA
        else None
    )
    if (
        not isinstance(document, dict)
        or schema_name is None
        or validate_schema(document, schema_name)
    ):
        raise ProjectRuntimeError("project_runtime_candidate_receipt_invalid")
    return document


def _existing_runtime_matches_candidate(
    project_root: Path,
    candidate: PreparedRuntimeCandidate,
) -> bool:
    """Static-only exact comparison used both before and after approval."""

    return bool(
        _existing_runtime_candidate_observation(
            project_root,
            candidate,
        )["matches"]
    )


def _runtime_error_is_observation_unavailable(error: BaseException) -> bool:
    """Classify only explicit I/O uncertainty as observation unavailable."""

    reason_code = str(error)
    return any(
        marker in reason_code
        for marker in (
            "_unavailable",
            "_unreadable",
            "unreadable_or_changed",
        )
    )


def _existing_runtime_candidate_observation(
    project_root: Path,
    candidate: PreparedRuntimeCandidate,
) -> dict[str, Any]:
    """Compare an existing runtime without authorizing repair on read errors."""

    final = runtime_path(project_root, candidate.target_version)
    try:
        final_stat = final.lstat()
    except FileNotFoundError:
        return {
            "state": "failed",
            "reason_code": "project_runtime_existing_missing",
            "matches": False,
        }
    except OSError:
        return {
            "state": "unavailable",
            "reason_code": "project_runtime_existing_observation_unavailable",
            "matches": False,
        }
    final_components = _real_component_snapshot_observation(
        project_root,
        final,
        target_must_exist=True,
    )
    if final_components["state"] == "unavailable":
        return {
            "state": "unavailable",
            "reason_code": "project_runtime_existing_observation_unavailable",
            "matches": False,
        }
    if (
        not stat_module.S_ISDIR(final_stat.st_mode)
        or stat_module.S_ISLNK(final_stat.st_mode)
        or _is_reparse_stat(final_stat)
        or final_components["state"] != "passed"
    ):
        return {
            "state": "failed",
            "reason_code": "project_runtime_existing_unsafe",
            "matches": False,
        }
    installing = final / PROJECT_RUNTIME_INSTALLING_NAME
    try:
        installing.lstat()
    except FileNotFoundError:
        pass
    except OSError:
        return {
            "state": "unavailable",
            "reason_code": "project_runtime_existing_observation_unavailable",
            "matches": False,
        }
    else:
        return {
            "state": "failed",
            "reason_code": "project_runtime_existing_install_incomplete",
            "matches": False,
        }
    receipt_path = final / PROJECT_RUNTIME_RECEIPT_NAME
    try:
        receipt_stat = receipt_path.lstat()
    except FileNotFoundError:
        return {
            "state": "failed",
            "reason_code": "project_runtime_existing_receipt_missing",
            "matches": False,
        }
    except OSError:
        return {
            "state": "unavailable",
            "reason_code": "project_runtime_existing_observation_unavailable",
            "matches": False,
        }
    receipt_components = _real_component_snapshot_observation(
        project_root,
        receipt_path,
        target_must_exist=True,
    )
    if receipt_components["state"] == "unavailable":
        return {
            "state": "unavailable",
            "reason_code": "project_runtime_existing_observation_unavailable",
            "matches": False,
        }
    if (
        not stat_module.S_ISREG(receipt_stat.st_mode)
        or stat_module.S_ISLNK(receipt_stat.st_mode)
        or _is_reparse_stat(receipt_stat)
        or receipt_components["state"] != "passed"
        or receipt_stat.st_size < 0
        or receipt_stat.st_size > 2 * 1024 * 1024
    ):
        return {
            "state": "failed",
            "reason_code": "project_runtime_existing_receipt_invalid",
            "matches": False,
        }
    try:
        receipt_bytes = _read_limited(
            receipt_path,
            limit=2 * 1024 * 1024,
            ancestor_root=project_root,
        )
    except OSError:
        return {
            "state": "unavailable",
            "reason_code": "project_runtime_existing_observation_unavailable",
            "matches": False,
        }
    if receipt_bytes is None:
        return {
            "state": "unavailable",
            "reason_code": "project_runtime_existing_observation_unavailable",
            "matches": False,
        }
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
            return {
                "state": "failed",
                "reason_code": "project_runtime_existing_receipt_mismatch",
                "matches": False,
            }
        parsed_supply = project_runtime_supply_lock(
            candidate.supply_lock_bytes,
            expected_target=candidate.target_tag,
        )
        if parsed_supply is None or parsed_supply.sha256 != candidate.supply_lock_sha256:
            return {
                "state": "failed",
                "reason_code": "project_runtime_existing_supply_mismatch",
                "matches": False,
            }
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
    except TypeError:
        return {
            "state": "failed",
            "reason_code": "project_runtime_existing_receipt_invalid",
            "matches": False,
        }
    except ProjectRuntimeError as error:
        unavailable = _runtime_error_is_observation_unavailable(error)
        return {
            "state": "unavailable" if unavailable else "failed",
            "reason_code": (
                "project_runtime_existing_observation_unavailable"
                if unavailable
                else "project_runtime_existing_integrity_mismatch"
            ),
            "matches": False,
        }
    except OSError:
        return {
            "state": "unavailable",
            "reason_code": "project_runtime_existing_observation_unavailable",
            "matches": False,
        }
    # The parsed supply must exist; the helper above intentionally accepts no
    # receipt as authority for artifact bytes.
    if tuple(dict(item) for item in artifact_inventory) != tuple(
        dict(item) for item in candidate.artifact_inventory
    ):
        return {
            "state": "failed",
            "reason_code": "project_runtime_existing_artifact_mismatch",
            "matches": False,
        }
    try:
        matches = bool(
            _runtime_payload_sha256(final) == candidate.installed_payload_sha256
            and _normalized_runtime_payload_inventory(final)
            == candidate.normalized_payload_inventory
        )
    except ProjectRuntimeError as error:
        unavailable = _runtime_error_is_observation_unavailable(error)
        return {
            "state": "unavailable" if unavailable else "failed",
            "reason_code": (
                "project_runtime_existing_observation_unavailable"
                if unavailable
                else "project_runtime_existing_payload_mismatch"
            ),
            "matches": False,
        }
    except OSError:
        return {
            "state": "unavailable",
            "reason_code": "project_runtime_existing_observation_unavailable",
            "matches": False,
        }
    return {
        "state": "passed" if matches else "failed",
        "reason_code": (
            "project_runtime_existing_verified"
            if matches
            else "project_runtime_existing_payload_mismatch"
        ),
        "matches": matches,
    }


def _runtime_inventory_observation(
    path: Path,
    *,
    identity: tuple[int, int],
    inventory: tuple[RuntimeCandidateInventoryEntry, ...],
) -> dict[str, Any]:
    presence = _runtime_path_presence_observation(path)
    if presence["state"] == "unavailable":
        return {"state": "unavailable", "matches": False}
    if presence["present"] is not True:
        return {"state": "failed", "matches": False}
    try:
        live_identity = _path_identity(path)
        live_inventory = _candidate_inventory_snapshot(path)
    except ProjectRuntimeError as error:
        reason_code = str(error)
        unavailable = any(
            marker in reason_code
            for marker in ("_unavailable", "_unreadable")
        )
        return {
            "state": "unavailable" if unavailable else "failed",
            "matches": False,
        }
    except OSError:
        return {"state": "unavailable", "matches": False}
    matches = live_identity == identity and live_inventory == inventory
    return {"state": "passed" if matches else "failed", "matches": matches}


def runtime_repair_state_observation(
    candidate: PreparedRuntimeCandidate,
) -> dict[str, str]:
    """Classify repair topology without turning an unreadable path into drift."""

    if (
        not isinstance(candidate, PreparedRuntimeCandidate)
        or not candidate.existing_runtime_repair_required
        or candidate.existing_runtime_root_identity is None
        or candidate.existing_runtime_inventory_sha256 is None
    ):
        return {
            "state": "passed",
            "reason_code": "not_applicable",
            "repair_state": "not_applicable",
        }
    final = runtime_path(candidate.project_root, candidate.target_version)
    backup = _runtime_repair_backup_path(candidate)
    candidate_presence = _runtime_path_presence_observation(
        candidate.candidate_root
    )
    final_presence = _runtime_path_presence_observation(final)
    backup_presence = _runtime_path_presence_observation(backup)
    candidate_at_staging = _runtime_inventory_observation(
        candidate.candidate_root,
        identity=candidate.candidate_root_identity,
        inventory=candidate.inventory,
    )
    candidate_at_final = _runtime_inventory_observation(
        final,
        identity=candidate.candidate_root_identity,
        inventory=candidate.inventory,
    )
    old_at_final = _runtime_inventory_observation(
        final,
        identity=candidate.existing_runtime_root_identity,
        inventory=candidate.existing_runtime_inventory,
    )
    old_at_backup = _runtime_inventory_observation(
        backup,
        identity=candidate.existing_runtime_root_identity,
        inventory=candidate.existing_runtime_inventory,
    )
    if (
        candidate_at_staging["matches"]
        and old_at_final["matches"]
        and backup_presence == {"state": "passed", "present": False}
    ):
        repair_state = "preimage_final"
    elif (
        candidate_at_staging["matches"]
        and final_presence == {"state": "passed", "present": False}
        and old_at_backup["matches"]
    ):
        repair_state = "backup_only"
    elif (
        candidate_presence == {"state": "passed", "present": False}
        and candidate_at_final["matches"]
        and old_at_backup["matches"]
    ):
        repair_state = "candidate_final_plus_backup"
    else:
        observations = (
            candidate_presence,
            final_presence,
            backup_presence,
            candidate_at_staging,
            candidate_at_final,
            old_at_final,
            old_at_backup,
        )
        if any(item["state"] == "unavailable" for item in observations):
            return {
                "state": "unavailable",
                "reason_code": "project_runtime_repair_observation_unavailable",
                "repair_state": "unknown",
            }
        return {
            "state": "failed",
            "reason_code": "project_runtime_repair_state_invalid",
            "repair_state": "invalid",
        }
    return {
        "state": "passed",
        "reason_code": "verified",
        "repair_state": repair_state,
    }


def runtime_repair_state(candidate: PreparedRuntimeCandidate) -> str:
    """Compatibility scalar for callers that do not need four-state truth."""

    observation = runtime_repair_state_observation(candidate)
    return (
        observation["repair_state"]
        if observation["state"] == "passed"
        else "invalid"
    )


def existing_runtime_repair_preimage_matches(
    candidate: PreparedRuntimeCandidate,
) -> bool:
    """Prove the sealed preimage is available at either exact repair name."""

    return runtime_repair_state(candidate) in {
        "preimage_final",
        "backup_only",
    }


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
    candidate_presence = _runtime_path_presence_observation(candidate_root)
    seal_presence = _runtime_path_presence_observation(seal_path)
    runtime_parent_presence = _runtime_path_presence_observation(
        project / PROJECT_RUNTIME_RELATIVE_ROOT
    )
    if any(
        observation["state"] == "unavailable"
        for observation in (
            candidate_presence,
            seal_presence,
            runtime_parent_presence,
        )
    ):
        raise ProjectRuntimeError(
            "project_runtime_candidate_preimage_observation_unavailable"
        )
    if (
        candidate_presence["present"] is True
        or seal_presence["present"] is True
    ):
        raise ProjectRuntimeError("project_runtime_candidate_already_exists")

    runtimes_root = project / PROJECT_RUNTIME_RELATIVE_ROOT
    runtime_parent_existed_before = runtime_parent_presence["present"] is True
    mutated = False
    created_runtime_parent_identity: tuple[int, int] | None = None
    try:
        if not runtime_parent_existed_before:
            try:
                # The transaction root proves .zettel-kasten already exists.
                # CREATE_NEW semantics prevent a concurrent parent from being
                # mistaken for one created by this candidate.
                runtimes_root.mkdir()
            except FileExistsError as error:
                raise ProjectRuntimeError(
                    "project_runtime_parent_concurrent_creation"
                ) from error
            except OSError as error:
                raise ProjectRuntimeError(
                    "project_runtime_parent_creation_unavailable"
                ) from error
            mutated = True
            created_runtime_parent_identity = _path_identity(runtimes_root)
            if not _existing_components_are_real(project, runtimes_root):
                raise ProjectRuntimeError("project_runtime_root_unsafe")
            try:
                # Make both the new empty directory and its parent name
                # durable before any candidate bytes, network, or child
                # process can exist.  A crash before these barriers is an
                # incomplete private transaction, never an absent preimage.
                _flush_directory_durable(runtimes_root)
                _flush_directory_durable(runtimes_root.parent)
            except ProjectRuntimeError as error:
                raise ProjectRuntimeError(
                    "project_runtime_parent_creation_durability_failed"
                ) from error
            if (
                _runtime_path_presence_observation(runtimes_root)
                != {"state": "passed", "present": True}
                or _path_identity(runtimes_root)
                != created_runtime_parent_identity
                or not _existing_components_are_real(project, runtimes_root)
            ):
                raise ProjectRuntimeError(
                    "project_runtime_parent_identity_drift"
                )
        if not _existing_components_are_real(project, runtimes_root):
            raise ProjectRuntimeError("project_runtime_root_unsafe")
        try:
            candidate_root.mkdir()
        except OSError as error:
            raise ProjectRuntimeError(
                "project_runtime_candidate_creation_failed"
            ) from error
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
            created_runtime_parent_identity is not None
            and runtime_parent_identity != created_runtime_parent_identity
        ):
            raise ProjectRuntimeError(
                "project_runtime_parent_identity_drift"
            )
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
                created_runtime_parent_identity
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
            existing_runtime_repair_required=False,
            existing_runtime_root_identity=None,
            existing_runtime_inventory=(),
            existing_runtime_inventory_sha256=None,
            existing_runtime_inventory_count=0,
            existing_runtime_inventory_bytes=0,
        )
        final = runtime_path(project, version)
        existing_runtime_reusable = False
        existing_runtime_repair_required = False
        existing_runtime_root_identity: tuple[int, int] | None = None
        existing_runtime_inventory: tuple[RuntimeCandidateInventoryEntry, ...] = ()
        existing_runtime_inventory_sha256: str | None = None
        existing_runtime_inventory_bytes = 0
        existing_observation = _existing_runtime_candidate_observation(
            project,
            provisional,
        )
        if existing_observation["state"] == "unavailable":
            raise ProjectRuntimeError(
                "project_runtime_existing_observation_unavailable"
            )
        if (
            existing_observation["reason_code"]
            != "project_runtime_existing_missing"
        ):
            existing_runtime_reusable = bool(
                existing_observation["matches"]
            )
            if not existing_runtime_reusable:
                existing_runtime_repair_required = True
                existing_runtime_root_identity = _path_identity(final)
                existing_runtime_inventory = _candidate_inventory_snapshot(final)
                existing_runtime_inventory_sha256 = (
                    _recursive_candidate_inventory_digest(
                        existing_runtime_inventory
                    )
                )
                existing_runtime_inventory_bytes = sum(
                    item.size_bytes
                    for item in existing_runtime_inventory
                    if item.entry_type == "file"
                )
        if existing_runtime_repair_required:
            # The ordinary receipt remains v0.1.  Only a candidate that has
            # now proven an exact invalid-runtime preimage is rewritten to the
            # repair-aware v0.2 receipt before the candidate is sealed.
            repair_receipt = {
                **receipt,
                "schema": PROJECT_RUNTIME_REPAIR_RECEIPT_SCHEMA,
                "previous_runtime_deleted_during_materialization": False,
                "terminal_cleanup_required_to_remove_private_repair_preimage": True,
            }
            repair_receipt.pop("previous_runtime_deleted", None)
            if validate_schema(
                repair_receipt,
                "project-runtime-receipt-v0.2.schema.json",
            ):
                raise ProjectRuntimeError(
                    "project_runtime_receipt_schema_invalid"
                )
            repair_receipt_bytes = (
                json.dumps(
                    repair_receipt,
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8")
            receipt_path = candidate_root / PROJECT_RUNTIME_RECEIPT_NAME
            temporary_receipt = candidate_root / (
                PROJECT_RUNTIME_RECEIPT_NAME + ".repair.tmp"
            )
            _write_exact_new_file(temporary_receipt, repair_receipt_bytes)
            os.replace(temporary_receipt, receipt_path)
            _flush_directory_durable(candidate_root)
            receipt = repair_receipt
            receipt_bytes = repair_receipt_bytes
            _detach_candidate_hardlinks(candidate_root)
            inventory = _candidate_inventory_snapshot(candidate_root)
            provisional = PreparedRuntimeCandidate(
                **{
                    **provisional.__dict__,
                    "inventory": inventory,
                    "inventory_count": len(inventory),
                    "inventory_bytes": sum(
                        item.size_bytes
                        for item in inventory
                        if item.entry_type == "file"
                    ),
                    "receipt_bytes": receipt_bytes,
                    "receipt_sha256": _sha256_bytes(receipt_bytes),
                }
            )
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
            existing_runtime_repair_required=(
                existing_runtime_repair_required
            ),
            existing_runtime_inventory_sha256=(
                existing_runtime_inventory_sha256
            ),
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
            "existing_runtime_repair_required": (
                existing_runtime_repair_required
            ),
            "existing_runtime_inventory_sha256": (
                None
                if existing_runtime_inventory_sha256 is None
                else f"sha256:{existing_runtime_inventory_sha256}"
            ),
            "existing_runtime_inventory_count": len(
                existing_runtime_inventory
            ),
            "existing_runtime_inventory_bytes": (
                existing_runtime_inventory_bytes
            ),
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
                "existing_runtime_root": (
                    None
                    if existing_runtime_root_identity is None
                    else list(existing_runtime_root_identity)
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
                "existing_runtime_repair_required": (
                    existing_runtime_repair_required
                ),
                "existing_runtime_root_identity": (
                    existing_runtime_root_identity
                ),
                "existing_runtime_inventory": existing_runtime_inventory,
                "existing_runtime_inventory_sha256": (
                    existing_runtime_inventory_sha256
                ),
                "existing_runtime_inventory_count": len(
                    existing_runtime_inventory
                ),
                "existing_runtime_inventory_bytes": (
                    existing_runtime_inventory_bytes
                ),
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
    legacy_seal_keys = {
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
    current_seal_keys = legacy_seal_keys | {
        "existing_runtime_repair_required",
        "existing_runtime_inventory_sha256",
        "existing_runtime_inventory_count",
        "existing_runtime_inventory_bytes",
    }
    legacy_resume_shape = set(seal) == legacy_seal_keys
    if not legacy_resume_shape and set(seal) != current_seal_keys:
        raise ProjectRuntimeError("project_runtime_candidate_seal_invalid")
    identities = seal.get("path_identities")
    legacy_identity_keys = {
        "project_root",
        "transaction_root",
        "candidate_root",
        "runtime_parent",
        "runtime_parent_created",
    }
    current_identity_keys = legacy_identity_keys | {"existing_runtime_root"}
    if (
        not isinstance(identities, dict)
        or set(identities)
        != (
            legacy_identity_keys
            if legacy_resume_shape
            else current_identity_keys
        )
    ):
        raise ProjectRuntimeError("project_runtime_candidate_seal_invalid")
    project_identity = _sealed_identity(identities.get("project_root"))
    transaction_identity = _sealed_identity(identities.get("transaction_root"))
    candidate_identity = _sealed_identity(identities.get("candidate_root"))
    runtime_parent_identity = _sealed_identity(identities.get("runtime_parent"))
    created_value = identities.get("runtime_parent_created")
    runtime_parent_created_identity = (
        None if created_value is None else _sealed_identity(created_value)
    )
    existing_runtime_value = identities.get("existing_runtime_root")
    existing_runtime_root_identity = (
        None
        if existing_runtime_value is None
        else _sealed_identity(existing_runtime_value)
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
        or (
            not legacy_resume_shape
            and (
                not isinstance(
                    seal.get("existing_runtime_repair_required"), bool
                )
                or not isinstance(
                    seal.get("existing_runtime_inventory_count"), int
                )
                or isinstance(
                    seal.get("existing_runtime_inventory_count"), bool
                )
                or not isinstance(
                    seal.get("existing_runtime_inventory_bytes"), int
                )
                or isinstance(
                    seal.get("existing_runtime_inventory_bytes"), bool
                )
            )
        )
    ):
        raise ProjectRuntimeError("project_runtime_candidate_seal_invalid")
    repair_required = (
        False
        if legacy_resume_shape
        else seal["existing_runtime_repair_required"]
    )
    repair_inventory_sha = seal.get("existing_runtime_inventory_sha256")
    if repair_required:
        if (
            not isinstance(repair_inventory_sha, str)
            or not repair_inventory_sha.startswith("sha256:")
            or SHA256_RE.fullmatch(
                repair_inventory_sha.removeprefix("sha256:")
            )
            is None
            or existing_runtime_root_identity is None
        ):
            raise ProjectRuntimeError("project_runtime_candidate_seal_invalid")
        final_runtime = runtime_path(project, target)
        repair_backup = transaction / PROJECT_RUNTIME_REPAIR_BACKUP_NAME
        final_presence = _runtime_path_presence_observation(final_runtime)
        backup_presence = _runtime_path_presence_observation(repair_backup)
        if (
            final_presence["state"] == "unavailable"
            or backup_presence["state"] == "unavailable"
        ):
            raise ProjectRuntimeError(
                "project_runtime_existing_repair_preimage_unavailable"
            )
        if (
            final_presence["present"] is True
            and _path_identity(final_runtime) == existing_runtime_root_identity
        ):
            existing_runtime_location = final_runtime
        elif (
            backup_presence["present"] is True
            and _path_identity(repair_backup) == existing_runtime_root_identity
        ):
            existing_runtime_location = repair_backup
        else:
            raise ProjectRuntimeError(
                "project_runtime_candidate_seal_invalid"
            )
        existing_runtime_inventory = _candidate_inventory_snapshot(
            existing_runtime_location
        )
    else:
        if (
            repair_inventory_sha is not None
            or existing_runtime_root_identity is not None
            or (
                not legacy_resume_shape
                and (
                    seal["existing_runtime_inventory_count"] != 0
                    or seal["existing_runtime_inventory_bytes"] != 0
                )
            )
        ):
            raise ProjectRuntimeError("project_runtime_candidate_seal_invalid")
        existing_runtime_inventory = ()
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
        existing_runtime_repair_required=repair_required,
        existing_runtime_root_identity=existing_runtime_root_identity,
        existing_runtime_inventory=existing_runtime_inventory,
        existing_runtime_inventory_sha256=(
            None
            if repair_inventory_sha is None
            else repair_inventory_sha.removeprefix("sha256:")
        ),
        existing_runtime_inventory_count=seal[
            "existing_runtime_inventory_count"
        ] if not legacy_resume_shape else 0,
        existing_runtime_inventory_bytes=seal[
            "existing_runtime_inventory_bytes"
        ] if not legacy_resume_shape else 0,
        legacy_resume_shape=legacy_resume_shape,
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
        or type(candidate.legacy_resume_shape) is not bool
        or (
            candidate.legacy_resume_shape
            and candidate.existing_runtime_repair_required
        )
        or (
            candidate.runtime_parent_existed_before
            and candidate.runtime_parent_created_identity is not None
        )
        or (
            not candidate.runtime_parent_existed_before
            and candidate.runtime_parent_created_identity
            != candidate.runtime_parent_identity
        )
        or (
            candidate.existing_runtime_reusable
            and candidate.existing_runtime_repair_required
        )
        or (
            candidate.existing_runtime_repair_required
            and (
                candidate.existing_runtime_root_identity is None
                or candidate.existing_runtime_inventory_sha256 is None
                or candidate.existing_runtime_inventory_count
                != len(candidate.existing_runtime_inventory)
                or candidate.existing_runtime_inventory_bytes
                != sum(
                    item.size_bytes
                    for item in candidate.existing_runtime_inventory
                    if item.entry_type == "file"
                )
            )
        )
        or (
            not candidate.existing_runtime_repair_required
            and (
                candidate.existing_runtime_root_identity is not None
                or candidate.existing_runtime_inventory
                or candidate.existing_runtime_inventory_sha256 is not None
                or candidate.existing_runtime_inventory_count != 0
                or candidate.existing_runtime_inventory_bytes != 0
            )
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
    final = runtime_path(project, candidate.target_version)
    if candidate.existing_runtime_repair_required:
        repair_observation = runtime_repair_state_observation(candidate)
        if repair_observation["state"] == "unavailable":
            raise ProjectRuntimeError(
                "project_runtime_existing_repair_preimage_unavailable"
            )
        if repair_observation["repair_state"] not in {
            "preimage_final",
            "backup_only",
        }:
            raise ProjectRuntimeError(
                "project_runtime_existing_repair_preimage_drift"
            )
    elif candidate.existing_runtime_reusable:
        existing_observation = _existing_runtime_candidate_observation(
            project,
            candidate,
        )
        if existing_observation["state"] == "unavailable":
            raise ProjectRuntimeError(
                "project_runtime_existing_observation_unavailable"
            )
        if not existing_observation["matches"]:
            raise ProjectRuntimeError("project_runtime_existing_runtime_drift")
    else:
        final_presence = _runtime_path_presence_observation(final)
        if final_presence["state"] == "unavailable":
            raise ProjectRuntimeError(
                "project_runtime_target_observation_unavailable"
            )
        if final_presence["present"] is True:
            raise ProjectRuntimeError(
                "project_runtime_target_directory_concurrent"
            )
    try:
        seal_stat = candidate.seal_path.lstat()
    except OSError as error:
        raise ProjectRuntimeError(
            "project_runtime_candidate_seal_unavailable"
        ) from error
    try:
        seal_link_count = _file_link_count(candidate.seal_path, seal_stat)
    except ProjectRuntimeError as error:
        raise ProjectRuntimeError(
            "project_runtime_candidate_seal_unavailable"
        ) from error
    seal_observation = _stable_regular_file_observation(
        candidate.seal_path,
        limit=256 * 1024,
        ancestor_root=candidate.transaction_root,
        collect_bytes=True,
    )
    if seal_observation is None:
        raise ProjectRuntimeError(
            "project_runtime_candidate_seal_unavailable"
        )
    live_seal_bytes = seal_observation[0]
    if (
        stat_module.S_ISLNK(seal_stat.st_mode)
        or _is_reparse(seal_stat)
        or not stat_module.S_ISREG(seal_stat.st_mode)
        or seal_link_count != 1
        or live_seal_bytes != candidate.seal_bytes
        or _sha256_bytes(candidate.seal_bytes) != candidate.seal_sha256
    ):
        raise ProjectRuntimeError("project_runtime_candidate_seal_drift")
    try:
        seal_document = _json_without_duplicate_keys(candidate.seal_bytes)
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise ProjectRuntimeError("project_runtime_candidate_seal_drift") from error
    legacy_expected_seal_keys = {
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
    expected_seal_keys = (
        legacy_expected_seal_keys
        if candidate.legacy_resume_shape
        else legacy_expected_seal_keys
        | {
            "existing_runtime_repair_required",
            "existing_runtime_inventory_sha256",
            "existing_runtime_inventory_count",
            "existing_runtime_inventory_bytes",
        }
    )
    expected_path_identities = {
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
    if not candidate.legacy_resume_shape:
        expected_path_identities["existing_runtime_root"] = (
            None
            if candidate.existing_runtime_root_identity is None
            else list(candidate.existing_runtime_root_identity)
        )
    repair_seal_matches = bool(
        candidate.legacy_resume_shape
        or (
            seal_document.get("existing_runtime_repair_required")
            is candidate.existing_runtime_repair_required
            and seal_document.get("existing_runtime_inventory_sha256")
            == (
                None
                if candidate.existing_runtime_inventory_sha256 is None
                else f"sha256:{candidate.existing_runtime_inventory_sha256}"
            )
            and seal_document.get("existing_runtime_inventory_count")
            == candidate.existing_runtime_inventory_count
            and seal_document.get("existing_runtime_inventory_bytes")
            == candidate.existing_runtime_inventory_bytes
        )
    )
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
        or not repair_seal_matches
        or seal_document.get("runtime_parent_existed_before")
        is not candidate.runtime_parent_existed_before
        or seal_document.get("path_identities") != expected_path_identities
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
        existing_runtime_repair_required=(
            candidate.existing_runtime_repair_required
        ),
        existing_runtime_inventory_sha256=(
            candidate.existing_runtime_inventory_sha256
        ),
        runtime_parent_existed_before=candidate.runtime_parent_existed_before,
        inventory=inventory,
        legacy_shape=candidate.legacy_resume_shape,
    )
    if digest != candidate.candidate_sha256:
        raise ProjectRuntimeError("project_runtime_candidate_drift")
    receipt_observation = _stable_regular_file_observation(
        candidate.candidate_root / PROJECT_RUNTIME_RECEIPT_NAME,
        limit=2 * 1024 * 1024,
        ancestor_root=candidate.candidate_root,
        collect_bytes=True,
        tree_shape_bound=True,
    )
    if receipt_observation is None:
        raise ProjectRuntimeError(
            "project_runtime_candidate_receipt_unavailable"
        )
    receipt_bytes = receipt_observation[0]
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
        or (
            candidate.existing_runtime_repair_required
            and (
                receipt.get("schema")
                != PROJECT_RUNTIME_REPAIR_RECEIPT_SCHEMA
                or receipt.get(
                    "previous_runtime_deleted_during_materialization"
                ) is not False
                or receipt.get(
                    "terminal_cleanup_required_to_remove_private_repair_preimage"
                ) is not True
            )
        )
        or (
            not candidate.existing_runtime_repair_required
            and receipt.get("schema") != PROJECT_RUNTIME_RECEIPT_SCHEMA
        )
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


def verify_prepared_runtime_candidate_observation(
    candidate: PreparedRuntimeCandidate,
    *,
    project_root: Path,
    target: str,
    target_commit: str,
    bootstrap: BootstrapWheel,
    supply: RuntimeSupplyLock,
) -> tuple[str, str, dict[str, Any] | None]:
    """Revalidate a candidate without confusing confirmed drift with I/O loss."""

    try:
        summary = verify_prepared_runtime_candidate(
            candidate,
            project_root=project_root,
            target=target,
            target_commit=target_commit,
            bootstrap=bootstrap,
            supply=supply,
        )
    except ProjectRuntimeError as error:
        reason_code = str(error) or "project_runtime_candidate_unavailable"
        if (
            not reason_code.startswith("project_runtime_")
            or re.fullmatch(r"[a-z][a-z0-9_]*", reason_code) is None
        ):
            return (
                "unavailable",
                "project_runtime_candidate_observation_unavailable",
                None,
            )
        unavailable = _runtime_error_is_observation_unavailable(error)
        return (
            "unavailable" if unavailable else "failed",
            reason_code,
            None,
        )
    except OSError:
        return (
            "unavailable",
            "project_runtime_candidate_observation_unavailable",
            None,
        )
    return "passed", "verified", summary


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
    candidate_presence = _runtime_path_presence_observation(
        candidate.candidate_root
    )
    final_presence = _runtime_path_presence_observation(final)
    if (
        candidate_presence["state"] == "unavailable"
        or final_presence["state"] == "unavailable"
    ):
        raise ProjectRuntimeError(
            "project_runtime_candidate_promotion_observation_unavailable"
        )
    if (
        candidate_presence["present"] is True
        or final_presence["present"] is not True
        or not _existing_components_are_real(candidate.project_root, final)
        or _path_identity(final) != candidate.candidate_root_identity
        or _candidate_inventory_snapshot(final) != candidate.inventory
        or _read_limited(final / PROJECT_RUNTIME_RECEIPT_NAME, limit=2 * 1024 * 1024)
        != candidate.receipt_bytes
    ):
        raise ProjectRuntimeError("project_runtime_candidate_promotion_ambiguous")


def _runtime_repair_backup_path(
    candidate: PreparedRuntimeCandidate,
) -> Path:
    return candidate.transaction_root / PROJECT_RUNTIME_REPAIR_BACKUP_NAME


def _runtime_inventory_matches(
    path: Path,
    *,
    identity: tuple[int, int],
    inventory: tuple[RuntimeCandidateInventoryEntry, ...],
) -> bool:
    try:
        return bool(
            _path_identity(path) == identity
            and _candidate_inventory_snapshot(path) == inventory
        )
    except (OSError, ProjectRuntimeError):
        return False


def _restore_failed_runtime_repair_promotion(
    candidate: PreparedRuntimeCandidate,
    *,
    final: Path,
    backup: Path,
    tracker: RuntimeMutationTracker | None,
) -> bool:
    """Restore both names after any caught two-rename repair failure."""

    old_identity = candidate.existing_runtime_root_identity
    if old_identity is None:
        return False
    try:
        candidate_at_final = _runtime_inventory_matches(
            final,
            identity=candidate.candidate_root_identity,
            inventory=candidate.inventory,
        )
        if candidate_at_final:
            candidate_presence = _runtime_path_presence_observation(
                candidate.candidate_root
            )
            if (
                candidate_presence["state"] == "unavailable"
                or candidate_presence["present"] is True
            ):
                return False
            _atomic_promote_directory_no_replace(
                final,
                candidate.candidate_root,
            )
            _flush_directory_durable(candidate.transaction_root)
        else:
            final_presence = _runtime_path_presence_observation(final)
            if final_presence["state"] == "unavailable":
                return False
            if (
                final_presence["present"] is True
                and not _runtime_inventory_matches(
                    final,
                    identity=old_identity,
                    inventory=candidate.existing_runtime_inventory,
                )
            ):
                return False

        backup_presence = _runtime_path_presence_observation(backup)
        if backup_presence["state"] == "unavailable":
            return False
        if backup_presence["present"] is True:
            final_presence = _runtime_path_presence_observation(final)
            if not _runtime_inventory_matches(
                backup,
                identity=old_identity,
                inventory=candidate.existing_runtime_inventory,
            ) or final_presence != {"state": "passed", "present": False}:
                return False
            _atomic_promote_directory_no_replace(backup, final)

        _flush_directory_durable(
            candidate.project_root / PROJECT_RUNTIME_RELATIVE_ROOT
        )
        _flush_directory_durable(candidate.transaction_root)
        backup_presence = _runtime_path_presence_observation(backup)
        restored = bool(
            backup_presence == {"state": "passed", "present": False}
            and _runtime_inventory_matches(
                final,
                identity=old_identity,
                inventory=candidate.existing_runtime_inventory,
            )
            and _runtime_inventory_matches(
                candidate.candidate_root,
                identity=candidate.candidate_root_identity,
                inventory=candidate.inventory,
            )
        )
        if tracker is not None:
            restored = runtime_mutation_restored(
                candidate.project_root,
                tracker,
            ) and restored
        return restored
    except (OSError, ProjectRuntimeError):
        return False


def reopen_promoted_runtime_materialization(
    candidate: PreparedRuntimeCandidate,
) -> RuntimeMaterialization:
    """Rebuild exact rollback authority after promotion survived a process exit."""

    if not isinstance(candidate, PreparedRuntimeCandidate):
        raise ProjectRuntimeError("project_runtime_candidate_binding_invalid")
    final = runtime_path(candidate.project_root, candidate.target_version)
    repair_backup: Path | None = None
    if candidate.existing_runtime_repair_required:
        repair_backup = _runtime_repair_backup_path(candidate)

    def exact_promoted_state_observation() -> dict[str, Any]:
        existing_observation = _existing_runtime_candidate_observation(
            candidate.project_root,
            candidate,
        )
        if existing_observation["state"] == "unavailable":
            return {
                "state": "unavailable",
                "reason_code": (
                    "project_runtime_candidate_promotion_observation_unavailable"
                ),
                "matches": False,
            }
        if not existing_observation["matches"]:
            return {
                "state": "failed",
                "reason_code": "project_runtime_candidate_promotion_ambiguous",
                "matches": False,
            }
        if candidate.existing_runtime_repair_required:
            repair_observation = runtime_repair_state_observation(candidate)
            if repair_observation["state"] == "unavailable":
                return {
                    "state": "unavailable",
                    "reason_code": (
                        "project_runtime_candidate_promotion_observation_unavailable"
                    ),
                    "matches": False,
                }
            if (
                repair_backup is None
                or candidate.existing_runtime_root_identity is None
                or repair_observation["repair_state"]
                != "candidate_final_plus_backup"
            ):
                return {
                    "state": "failed",
                    "reason_code": (
                        "project_runtime_candidate_promotion_ambiguous"
                    ),
                    "matches": False,
                }
            backup_observation = _runtime_inventory_observation(
                repair_backup,
                identity=candidate.existing_runtime_root_identity,
                inventory=candidate.existing_runtime_inventory,
            )
            if backup_observation["state"] == "unavailable":
                return {
                    "state": "unavailable",
                    "reason_code": (
                        "project_runtime_candidate_promotion_observation_unavailable"
                    ),
                    "matches": False,
                }
            return {
                "state": (
                    "passed" if backup_observation["matches"] else "failed"
                ),
                "reason_code": (
                    "verified"
                    if backup_observation["matches"]
                    else "project_runtime_candidate_promotion_ambiguous"
                ),
                "matches": bool(backup_observation["matches"]),
            }
        if candidate.existing_runtime_reusable:
            return {
                "state": "passed",
                "reason_code": "verified",
                "matches": True,
            }
        candidate_presence = _runtime_path_presence_observation(
            candidate.candidate_root
        )
        if candidate_presence["state"] == "unavailable":
            return {
                "state": "unavailable",
                "reason_code": (
                    "project_runtime_candidate_promotion_observation_unavailable"
                ),
                "matches": False,
            }
        matches = candidate_presence["present"] is False
        return {
            "state": "passed" if matches else "failed",
            "reason_code": (
                "verified"
                if matches
                else "project_runtime_candidate_promotion_ambiguous"
            ),
            "matches": matches,
        }

    promoted_observation = exact_promoted_state_observation()
    if promoted_observation["state"] == "unavailable":
        raise ProjectRuntimeError(
            "project_runtime_candidate_promotion_observation_unavailable"
        )
    if not promoted_observation["matches"]:
        raise ProjectRuntimeError("project_runtime_candidate_promotion_ambiguous")
    # A hard exit can occur after the candidate-to-final rename but before the
    # original process flushes either directory.  Reopened execution must make
    # both rename halves durable and then re-prove the exact identities/bytes
    # before a runtime-verified checkpoint may be appended.
    _flush_directory_durable(
        candidate.project_root / PROJECT_RUNTIME_RELATIVE_ROOT
    )
    _flush_directory_durable(candidate.transaction_root)
    promoted_observation = exact_promoted_state_observation()
    if promoted_observation["state"] == "unavailable":
        raise ProjectRuntimeError(
            "project_runtime_candidate_promotion_observation_unavailable"
        )
    if not promoted_observation["matches"]:
        raise ProjectRuntimeError("project_runtime_candidate_promotion_ambiguous")
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
        created=not candidate.existing_runtime_reusable,
        verification=candidate.verification,
        inventory=candidate.inventory,
        runtime_root_identity=candidate.candidate_root_identity,
        runtime_parent_identity=candidate.runtime_parent_identity,
        repaired=candidate.existing_runtime_repair_required,
        replaced_runtime_path=repair_backup,
        replaced_runtime_identity=(
            candidate.existing_runtime_root_identity
        ),
        replaced_runtime_inventory=(
            candidate.existing_runtime_inventory
        ),
        transaction_root=candidate.transaction_root,
        transaction_root_identity=candidate.transaction_root_identity,
        runtime_parent_existed_before=candidate.runtime_parent_existed_before,
        runtime_parent_created_identity=candidate.runtime_parent_created_identity,
    )


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
        existing_observation = _existing_runtime_candidate_observation(
            project,
            candidate,
        )
        if existing_observation["state"] == "unavailable":
            raise ProjectRuntimeError(
                "project_runtime_existing_observation_unavailable"
            )
        if not existing_observation["matches"]:
            raise ProjectRuntimeError("project_runtime_existing_runtime_drift")
        receipt_bytes = _read_limited(
            final / PROJECT_RUNTIME_RECEIPT_NAME,
            limit=2 * 1024 * 1024,
        )
        if receipt_bytes is None:
            raise ProjectRuntimeError(
                "project_runtime_existing_observation_unavailable"
            )
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
            inventory=candidate.inventory,
            runtime_root_identity=_path_identity(final),
            runtime_parent_identity=candidate.runtime_parent_identity,
            transaction_root=candidate.transaction_root,
            transaction_root_identity=candidate.transaction_root_identity,
            runtime_parent_existed_before=candidate.runtime_parent_existed_before,
            runtime_parent_created_identity=(
                candidate.runtime_parent_created_identity
            ),
        )
    if not candidate.existing_runtime_repair_required:
        final_presence = _runtime_path_presence_observation(final)
        if final_presence["state"] == "unavailable":
            raise ProjectRuntimeError(
                "project_runtime_target_observation_unavailable"
            )
        if final_presence["present"] is True:
            raise ProjectRuntimeError(
                "project_runtime_target_directory_concurrent"
            )
    repair_backup: Path | None = None
    repair_observation: dict[str, str] | None = None
    if candidate.existing_runtime_repair_required:
        repair_observation = runtime_repair_state_observation(candidate)
        if repair_observation["state"] == "unavailable":
            raise ProjectRuntimeError(
                "project_runtime_existing_repair_preimage_unavailable"
            )
        if repair_observation["repair_state"] not in {
            "preimage_final",
            "backup_only",
        }:
            raise ProjectRuntimeError(
                "project_runtime_existing_repair_preimage_drift"
            )
        repair_backup = _runtime_repair_backup_path(candidate)
        if repair_observation["repair_state"] == "preimage_final":
            backup_presence = _runtime_path_presence_observation(
                repair_backup
            )
            if backup_presence["state"] == "unavailable":
                raise ProjectRuntimeError(
                    "project_runtime_repair_backup_observation_unavailable"
                )
            if backup_presence["present"] is True:
                raise ProjectRuntimeError(
                    "project_runtime_repair_backup_collision"
                )
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
        if candidate.existing_runtime_repair_required:
            if repair_observation is None or repair_backup is None:
                raise ProjectRuntimeError(
                    "project_runtime_existing_repair_preimage_unavailable"
                )
            repair_state = repair_observation["repair_state"]
            if repair_state == "preimage_final":
                _atomic_promote_directory_no_replace(final, repair_backup)
                _flush_directory_durable(runtimes_root)
                _flush_directory_durable(candidate.transaction_root)
            elif repair_state != "backup_only":
                raise ProjectRuntimeError(
                    "project_runtime_existing_repair_preimage_drift"
                )
            backup_observation = _runtime_inventory_observation(
                repair_backup,
                identity=candidate.existing_runtime_root_identity,
                inventory=candidate.existing_runtime_inventory,
            )
            if backup_observation["state"] == "unavailable":
                raise ProjectRuntimeError(
                    "project_runtime_repair_backup_observation_unavailable"
                )
            if not backup_observation["matches"]:
                raise ProjectRuntimeError(
                    "project_runtime_repair_backup_drift"
                )
        _atomic_promote_directory_no_replace(candidate.candidate_root, final)
        _verify_promoted_candidate_image(candidate, final)
        # Persist both halves of each rename.  The old invalid runtime remains
        # as an exact private rollback preimage after a successful repair.
        _flush_directory_durable(runtimes_root)
        _flush_directory_durable(candidate.transaction_root)
        _verify_promoted_candidate_image(candidate, final)
    except BaseException as error:
        if (
            candidate.existing_runtime_repair_required
            and repair_backup is not None
            and _restore_failed_runtime_repair_promotion(
                candidate,
                final=final,
                backup=repair_backup,
                tracker=tracker,
            )
        ):
            raise ProjectRuntimeError(
                "project_runtime_repair_promotion_rolled_back"
            ) from error
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
        inventory=candidate.inventory,
        runtime_root_identity=candidate.candidate_root_identity,
        runtime_parent_identity=candidate.runtime_parent_identity,
        repaired=candidate.existing_runtime_repair_required,
        replaced_runtime_path=repair_backup,
        replaced_runtime_identity=candidate.existing_runtime_root_identity,
        replaced_runtime_inventory=candidate.existing_runtime_inventory,
        transaction_root=candidate.transaction_root,
        transaction_root_identity=candidate.transaction_root_identity,
        runtime_parent_existed_before=candidate.runtime_parent_existed_before,
        runtime_parent_created_identity=candidate.runtime_parent_created_identity,
    )


def _cleanup_inventory_private_value(
    inventory: tuple[RuntimeCandidateInventoryEntry, ...],
) -> list[dict[str, Any]]:
    return [
        {
            "relative_path": item.relative_path,
            "entry_type": item.entry_type,
            "device": item.device,
            "inode": item.inode,
            "nlink": item.nlink,
            "size_bytes": item.size_bytes,
            "mtime_ns": item.mtime_ns,
            "sha256": item.sha256,
        }
        for item in inventory
    ]


def _cleanup_inventory_from_private_value(
    value: Any,
) -> tuple[RuntimeCandidateInventoryEntry, ...]:
    if not isinstance(value, list) or len(value) > 1_000_000:
        raise ProjectRuntimeError("project_runtime_cleanup_capsule_invalid")
    expected_keys = {
        "relative_path",
        "entry_type",
        "device",
        "inode",
        "nlink",
        "size_bytes",
        "mtime_ns",
        "sha256",
    }
    result: list[RuntimeCandidateInventoryEntry] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict) or set(raw) != expected_keys:
            raise ProjectRuntimeError("project_runtime_cleanup_capsule_invalid")
        relative = raw.get("relative_path")
        entry_type = raw.get("entry_type")
        numeric = (
            raw.get("device"),
            raw.get("inode"),
            raw.get("nlink"),
            raw.get("size_bytes"),
            raw.get("mtime_ns"),
        )
        if (
            not isinstance(relative, str)
            or not relative
            or len(relative) > 4096
            or "\\" in relative
            or PurePosixPath(relative).is_absolute()
            or not PurePosixPath(relative).parts
            or any(
                part in {"", ".", ".."}
                for part in PurePosixPath(relative).parts
            )
            or PurePosixPath(relative).as_posix() != relative
            or relative.casefold() in seen
            or entry_type not in {"file", "directory"}
            or any(
                not isinstance(item, int)
                or isinstance(item, bool)
                or item < 0
                for item in numeric
            )
        ):
            raise ProjectRuntimeError("project_runtime_cleanup_capsule_invalid")
        digest = raw.get("sha256")
        if (
            entry_type == "file"
            and (
                raw["nlink"] != 1
                or not isinstance(digest, str)
                or SHA256_RE.fullmatch(digest) is None
            )
        ) or (
            entry_type == "directory"
            and (
                digest is not None
                or raw["size_bytes"] != 0
                or raw["mtime_ns"] != 0
            )
        ):
            raise ProjectRuntimeError("project_runtime_cleanup_capsule_invalid")
        seen.add(relative.casefold())
        result.append(
            RuntimeCandidateInventoryEntry(
                relative_path=relative,
                entry_type=entry_type,
                device=raw["device"],
                inode=raw["inode"],
                nlink=raw["nlink"],
                size_bytes=raw["size_bytes"],
                mtime_ns=raw["mtime_ns"],
                sha256=digest,
            )
        )
    return tuple(result)


def _runtime_candidate_cleanup_capsule_path(transaction_root: Path) -> Path:
    return transaction_root.parent / (
        PROJECT_RUNTIME_CLEANUP_CAPSULE_PREFIX
        + transaction_root.name
        + PROJECT_RUNTIME_CLEANUP_CAPSULE_SUFFIX
    )


@contextmanager
def _retained_default_stream_cleanup_file(
    path: Path,
    *,
    identity: tuple[int, int],
    mtime_ns: int,
    size_bytes: int,
    sha256: str,
) -> Iterator[None]:
    """Hold one exact default-stream-only file across cleanup decisions."""

    if os.name != "nt":
        before = _stable_regular_file_observation(
            path,
            limit=max(size_bytes, 1),
            ancestor_root=path.parent,
            collect_bytes=False,
        )
        try:
            before_stat = path.lstat()
        except OSError as error:
            raise ProjectRuntimeError(
                "project_runtime_cleanup_file_unavailable"
            ) from error
        if (
            before is None
            or (int(before_stat.st_dev), int(before_stat.st_ino)) != identity
            or int(before_stat.st_mtime_ns) != mtime_ns
            or int(before_stat.st_size) != size_bytes
            or before[1] != sha256
            or before[2] != size_bytes
        ):
            raise ProjectRuntimeError(
                "project_runtime_cleanup_file_state_invalid"
            )
        try:
            yield
        except BaseException:
            raise
        after = _stable_regular_file_observation(
            path,
            limit=max(size_bytes, 1),
            ancestor_root=path.parent,
            collect_bytes=False,
        )
        try:
            after_stat = path.lstat()
        except OSError as error:
            raise ProjectRuntimeError(
                "project_runtime_cleanup_file_unavailable"
            ) from error
        if (
            after is None
            or (int(after_stat.st_dev), int(after_stat.st_ino)) != identity
            or int(after_stat.st_mtime_ns) != mtime_ns
            or int(after_stat.st_size) != size_bytes
            or after[1] != sha256
            or after[2] != size_bytes
        ):
            raise ProjectRuntimeError(
                "project_runtime_cleanup_file_state_invalid"
            )
        return

    from . import legacy_cleanup_bound_delete as bound_delete

    approved = bound_delete._ApprovedFile(
        device=identity[0],
        inode=identity[1],
        size=size_bytes,
        mtime_ns=mtime_ns,
        sha256=sha256,
    )

    def validate(handle: int) -> None:
        bound_delete._validate_windows_named_file(path, approved)
        bound_delete._reject_windows_alternate_streams(
            handle,
            directory=False,
        )
        bound_delete._windows_digest_handle(
            handle,
            approved,
            expected_link_count=1,
        )

    handle: int | None = None
    try:
        handle = bound_delete._windows_open(path, directory=False)
        validate(handle)
    except BaseException as error:
        if handle is not None:
            try:
                bound_delete._windows_close(handle)
            except BaseException:
                pass
        raise ProjectRuntimeError(
            "project_runtime_cleanup_file_state_invalid"
        ) from error
    try:
        yield
    except BaseException:
        try:
            bound_delete._windows_close(handle)
        except BaseException:
            pass
        raise
    validation_error: BaseException | None = None
    try:
        validate(handle)
    except BaseException as error:
        validation_error = error
    try:
        bound_delete._windows_close(handle)
    except BaseException as error:
        validation_error = error
    if validation_error is not None:
        raise ProjectRuntimeError(
            "project_runtime_cleanup_file_state_invalid"
        ) from validation_error


def _runtime_candidate_cleanup_sidecar_shape(
    project_root: Path,
    capsule_path: Path,
    *,
    expected_transaction_ref: str,
) -> str:
    """Classify a sidecar without using it as cleanup authority.

    This bounded header check exists only for restart discovery.  Full cleanup
    authority still requires :func:`load_runtime_candidate_cleanup_capsule`,
    including the live transaction-root identity and complete inventory.
    """

    try:
        before = capsule_path.lstat()
        if (
            capsule_path.is_symlink()
            or _is_reparse(before)
            or not stat_module.S_ISREG(before.st_mode)
            or _file_link_count(capsule_path, before) != 1
            or int(before.st_size) <= 0
            or int(before.st_size) > PROJECT_RUNTIME_CLEANUP_CAPSULE_MAX_BYTES
            or not _existing_components_are_real(project_root, capsule_path)
        ):
            return "review_required"
        raw = _read_limited(
            capsule_path,
            limit=PROJECT_RUNTIME_CLEANUP_CAPSULE_MAX_BYTES,
            ancestor_root=project_root,
        )
        after = capsule_path.lstat()
    except (OSError, ProjectRuntimeError):
        return "unavailable"
    if (
        raw is None
        or int(before.st_dev) != int(after.st_dev)
        or int(before.st_ino) != int(after.st_ino)
        or int(before.st_size) != int(after.st_size)
        or int(before.st_mtime_ns) != int(after.st_mtime_ns)
    ):
        return "unavailable"
    try:
        document = _json_without_duplicate_keys(raw)
    except (UnicodeError, ValueError, json.JSONDecodeError):
        return "review_required"
    if (
        not isinstance(document, dict)
        or set(document) != PROJECT_RUNTIME_CLEANUP_CAPSULE_KEYS
        or document.get("schema") != PROJECT_RUNTIME_CLEANUP_CAPSULE_SCHEMA
        or document.get("status") != "cleanup_intent"
        or document.get("transaction_ref") != expected_transaction_ref
        or document.get("outer_transaction_ack_required_before_retire")
        is not True
        or document.get("absolute_paths_echoed") is not False
        or (
            json.dumps(document, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        != raw
    ):
        return "review_required"
    try:
        capsule_identity = _sealed_identity(
            document.get("capsule_identity")
        )
    except ProjectRuntimeError:
        return "review_required"
    if capsule_identity != (int(before.st_dev), int(before.st_ino)):
        return "review_required"
    try:
        with _retained_default_stream_cleanup_file(
            capsule_path,
            identity=capsule_identity,
            mtime_ns=int(before.st_mtime_ns),
            size_bytes=int(before.st_size),
            sha256=_sha256_bytes(raw),
        ):
            pass
    except ProjectRuntimeError:
        return "review_required"
    return "shape_valid"


def runtime_candidate_cleanup_sidecar_inventory(
    project_root: Path,
) -> dict[str, Any]:
    """Discover private cleanup sidecars without deleting or exposing paths.

    ``recoverable_transaction_refs`` can be passed to the dedicated capsule
    loader.  ``orphaned_transaction_refs`` have lost their exact transaction
    root and are therefore review-only: this module never guesses that the
    sidecar, runtime parent, or outer transaction evidence may be deleted.
    """

    empty = {
        "schema": PROJECT_RUNTIME_CLEANUP_SIDECAR_INVENTORY_SCHEMA,
        "state": "passed",
        "recoverable_transaction_refs": (),
        "orphaned_transaction_refs": (),
        "review_required_transaction_refs": (),
        "unavailable_transaction_refs": (),
        "unattributed_sidecar_count": 0,
        "sidecar_count": 0,
        "automatic_orphan_deletion_allowed": False,
        "orphan_recovery": "review_only_preserve_sidecar",
        "sidecar_must_retire_before_transaction_cleanup": True,
        "private_paths_echoed": False,
        "absolute_paths_echoed": False,
    }
    project = Path(os.path.abspath(str(project_root)))
    project_presence = _runtime_path_presence_observation(project)
    if project_presence != {"state": "passed", "present": True}:
        result = dict(empty)
        result["state"] = (
            "unavailable"
            if project_presence["state"] == "unavailable"
            else "failed"
        )
        return result
    parent = project / PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
    parent_presence = _runtime_path_presence_observation(parent)
    if parent_presence == {"state": "passed", "present": False}:
        return empty
    if parent_presence != {"state": "passed", "present": True}:
        result = dict(empty)
        result["state"] = "unavailable"
        return result
    try:
        project_stat = project.lstat()
        parent_stat = parent.lstat()
        parent_identity = (int(parent_stat.st_dev), int(parent_stat.st_ino))
        if (
            project.is_symlink()
            or parent.is_symlink()
            or _is_reparse(project_stat)
            or _is_reparse(parent_stat)
            or not stat_module.S_ISDIR(project_stat.st_mode)
            or not stat_module.S_ISDIR(parent_stat.st_mode)
            or not _existing_components_are_real(project, parent)
        ):
            result = dict(empty)
            result["state"] = "failed"
            return result
        entries = tuple(os.scandir(parent))
    except OSError:
        result = dict(empty)
        result["state"] = "unavailable"
        return result

    refs_by_folded: dict[str, list[str]] = {}
    unattributed = 0
    for entry in entries:
        name = entry.name
        if not (
            name.startswith(PROJECT_RUNTIME_CLEANUP_CAPSULE_PREFIX)
            and name.endswith(PROJECT_RUNTIME_CLEANUP_CAPSULE_SUFFIX)
        ):
            continue
        transaction_ref = name[
            len(PROJECT_RUNTIME_CLEANUP_CAPSULE_PREFIX) :
            -len(PROJECT_RUNTIME_CLEANUP_CAPSULE_SUFFIX)
        ]
        if (
            PROJECT_RUNTIME_TRANSACTION_REF_RE.fullmatch(transaction_ref)
            is None
            or name
            != (
                PROJECT_RUNTIME_CLEANUP_CAPSULE_PREFIX
                + transaction_ref
                + PROJECT_RUNTIME_CLEANUP_CAPSULE_SUFFIX
            )
        ):
            unattributed += 1
            continue
        refs_by_folded.setdefault(transaction_ref.casefold(), []).append(
            transaction_ref
        )

    recoverable: list[str] = []
    orphaned: list[str] = []
    review_required: list[str] = []
    unavailable: list[str] = []
    for folded in sorted(refs_by_folded):
        values = refs_by_folded[folded]
        if len(values) != 1:
            review_required.extend(sorted(values))
            continue
        transaction_ref = values[0]
        transaction = parent / transaction_ref
        capsule_path = _runtime_candidate_cleanup_capsule_path(transaction)
        shape = _runtime_candidate_cleanup_sidecar_shape(
            project,
            capsule_path,
            expected_transaction_ref=transaction_ref,
        )
        if shape == "unavailable":
            unavailable.append(transaction_ref)
            continue
        if shape != "shape_valid":
            review_required.append(transaction_ref)
            continue
        transaction_presence = _runtime_path_presence_observation(transaction)
        if transaction_presence["state"] == "unavailable":
            unavailable.append(transaction_ref)
        elif transaction_presence["present"] is False:
            orphaned.append(transaction_ref)
        else:
            try:
                load_runtime_candidate_cleanup_capsule(project, transaction)
            except ProjectRuntimeError as error:
                if str(error) == "project_runtime_cleanup_capsule_unavailable":
                    unavailable.append(transaction_ref)
                else:
                    review_required.append(transaction_ref)
            else:
                recoverable.append(transaction_ref)

    try:
        if (
            _path_identity(parent) != parent_identity
            or not _existing_components_are_real(project, parent)
        ):
            result = dict(empty)
            result["state"] = "unavailable"
            return result
    except (OSError, ProjectRuntimeError):
        result = dict(empty)
        result["state"] = "unavailable"
        return result

    result = dict(empty)
    result.update(
        {
            "state": "unavailable" if unavailable else "passed",
            "recoverable_transaction_refs": tuple(recoverable),
            "orphaned_transaction_refs": tuple(orphaned),
            "review_required_transaction_refs": tuple(review_required),
            "unavailable_transaction_refs": tuple(unavailable),
            "unattributed_sidecar_count": unattributed,
            "sidecar_count": (
                len(recoverable)
                + len(orphaned)
                + len(review_required)
                + len(unavailable)
                + unattributed
            ),
        }
    )
    return result


def _runtime_candidate_cleanup_quarantine_path(
    transaction_root: Path,
    inventory_sha256: str,
) -> Path:
    return transaction_root / (
        f"runtime-candidate-cleanup-{inventory_sha256[:16]}"
    )


def _runtime_candidate_cleanup_capsule_bytes(
    candidate: PreparedRuntimeCandidate,
    *,
    capsule_parent_identity: tuple[int, int],
    capsule_identity: tuple[int, int],
    seal_identity: tuple[int, int],
    seal_mtime_ns: int,
    seal_size_bytes: int,
) -> bytes:
    quarantine = _runtime_candidate_cleanup_quarantine_path(
        candidate.transaction_root,
        candidate.inventory_sha256,
    )
    document = {
        "schema": PROJECT_RUNTIME_CLEANUP_CAPSULE_SCHEMA,
        "status": "cleanup_intent",
        "target_tag": candidate.target_tag,
        "target_version": candidate.target_version,
        "target_commit": candidate.target_commit,
        "transaction_ref": candidate.transaction_ref,
        "candidate_locator": candidate.logical_candidate_path,
        "seal_locator": candidate.logical_seal_path,
        "quarantine_locator": quarantine.relative_to(
            candidate.project_root
        ).as_posix(),
        "project_root_identity": list(candidate.project_root_identity),
        "transaction_root_identity": list(candidate.transaction_root_identity),
        "candidate_root_identity": list(candidate.candidate_root_identity),
        "runtime_parent_identity": list(candidate.runtime_parent_identity),
        "runtime_parent_existed_before": (
            candidate.runtime_parent_existed_before
        ),
        "runtime_parent_created_identity": (
            None
            if candidate.runtime_parent_created_identity is None
            else list(candidate.runtime_parent_created_identity)
        ),
        "existing_runtime_root_identity": (
            None
            if candidate.existing_runtime_root_identity is None
            else list(candidate.existing_runtime_root_identity)
        ),
        "capsule_parent_identity": list(capsule_parent_identity),
        "capsule_identity": list(capsule_identity),
        "inventory": _cleanup_inventory_private_value(candidate.inventory),
        "inventory_sha256": f"sha256:{candidate.inventory_sha256}",
        "inventory_count": candidate.inventory_count,
        "inventory_bytes": candidate.inventory_bytes,
        "candidate_sha256": f"sha256:{candidate.candidate_sha256}",
        "seal_identity": list(seal_identity),
        "seal_mtime_ns": seal_mtime_ns,
        "seal_size_bytes": seal_size_bytes,
        "seal_sha256": f"sha256:{candidate.seal_sha256}",
        "outer_transaction_ack_required_before_retire": True,
        "absolute_paths_echoed": False,
    }
    return (
        json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _write_runtime_candidate_cleanup_capsule_exact_new(
    capsule_path: Path,
    candidate: PreparedRuntimeCandidate,
    *,
    capsule_parent_identity: tuple[int, int],
    seal_identity: tuple[int, int],
    seal_mtime_ns: int,
    seal_size_bytes: int,
) -> tuple[bytes, tuple[int, int], int, int]:
    """Create a self-identity-bound sidecar without replacing any name.

    Opening the empty file first is intentional: only the descriptor identity
    can be embedded in the document without a circular content digest.  A
    hard exit before the final fsync leaves an empty or partial sidecar, which
    discovery classifies as review-only and never uses as cleanup authority.
    """

    try:
        with capsule_path.open("x+b") as handle:
            opened = os.fstat(handle.fileno())
            if (
                not stat_module.S_ISREG(opened.st_mode)
                or stat_module.S_ISLNK(opened.st_mode)
                or _is_reparse(opened)
            ):
                raise ProjectRuntimeError(
                    "project_runtime_cleanup_capsule_write_unavailable"
                )
            capsule_identity = (
                int(opened.st_dev),
                int(opened.st_ino),
            )
            raw = _runtime_candidate_cleanup_capsule_bytes(
                candidate,
                capsule_parent_identity=capsule_parent_identity,
                capsule_identity=capsule_identity,
                seal_identity=seal_identity,
                seal_mtime_ns=seal_mtime_ns,
                seal_size_bytes=seal_size_bytes,
            )
            written = handle.write(raw)
            if written != len(raw):
                raise ProjectRuntimeError(
                    "project_runtime_cleanup_capsule_write_unavailable"
                )
            handle.flush()
            os.fsync(handle.fileno())
            completed = os.fstat(handle.fileno())
            if (
                (int(completed.st_dev), int(completed.st_ino))
                != capsule_identity
                or not stat_module.S_ISREG(completed.st_mode)
                or _is_reparse(completed)
                or int(completed.st_size) != len(raw)
            ):
                raise ProjectRuntimeError(
                    "project_runtime_cleanup_capsule_write_unavailable"
                )
            capsule_mtime_ns = int(completed.st_mtime_ns)
            capsule_size_bytes = int(completed.st_size)
    except ProjectRuntimeError:
        raise
    except OSError as error:
        raise ProjectRuntimeError(
            "project_runtime_cleanup_capsule_write_unavailable"
        ) from error
    return (
        raw,
        capsule_identity,
        capsule_mtime_ns,
        capsule_size_bytes,
    )


def _validate_runtime_cleanup_seal_or_terminal_topology(
    capsule: RuntimeCandidateCleanupCapsule,
) -> bool:
    """Cross-bind a surviving seal, or prove the seal is terminally absent."""

    seal_presence = _runtime_path_presence_observation(capsule.seal_path)
    if seal_presence["state"] == "unavailable":
        raise ProjectRuntimeError(
            "project_runtime_cleanup_seal_unavailable"
        )
    if seal_presence["present"] is False:
        candidate_presence = _runtime_path_presence_observation(
            capsule.candidate_root
        )
        quarantine_presence = _runtime_path_presence_observation(
            capsule.quarantine_root
        )
        if (
            candidate_presence["state"] == "unavailable"
            or quarantine_presence["state"] == "unavailable"
        ):
            raise ProjectRuntimeError(
                "project_runtime_cleanup_topology_unavailable"
            )
        if (
            candidate_presence["present"] is not False
            or quarantine_presence["present"] is not False
        ):
            raise ProjectRuntimeError(
                "project_runtime_cleanup_topology_invalid"
            )
        return False

    seal_bytes = _read_limited(
        capsule.seal_path,
        limit=256 * 1024,
        ancestor_root=capsule.transaction_root,
    )
    if seal_bytes is None:
        raise ProjectRuntimeError(
            "project_runtime_cleanup_seal_unavailable"
        )
    try:
        with _retained_default_stream_cleanup_file(
            capsule.seal_path,
            identity=capsule.seal_identity,
            mtime_ns=capsule.seal_mtime_ns,
            size_bytes=capsule.seal_size_bytes,
            sha256=capsule.seal_sha256,
        ):
            pass
        seal = _json_without_duplicate_keys(seal_bytes)
    except ProjectRuntimeError:
        raise
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise ProjectRuntimeError(
            "project_runtime_cleanup_seal_invalid"
        ) from error
    if not isinstance(seal, dict):
        raise ProjectRuntimeError("project_runtime_cleanup_seal_invalid")

    legacy_keys = {
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
    current_keys = legacy_keys | {
        "existing_runtime_repair_required",
        "existing_runtime_inventory_sha256",
        "existing_runtime_inventory_count",
        "existing_runtime_inventory_bytes",
    }
    legacy_shape = set(seal) == legacy_keys
    if not legacy_shape and set(seal) != current_keys:
        raise ProjectRuntimeError("project_runtime_cleanup_seal_invalid")
    identities = seal.get("path_identities")
    expected_identities = {
        "project_root": list(capsule.project_root_identity),
        "transaction_root": list(capsule.transaction_root_identity),
        "candidate_root": list(capsule.candidate_root_identity),
        "runtime_parent": list(capsule.runtime_parent_identity),
        "runtime_parent_created": (
            None
            if capsule.runtime_parent_created_identity is None
            else list(capsule.runtime_parent_created_identity)
        ),
    }
    if not legacy_shape:
        expected_identities["existing_runtime_root"] = (
            None
            if capsule.existing_runtime_root_identity is None
            else list(capsule.existing_runtime_root_identity)
        )
    numeric_values = (
        seal.get("inventory_count"),
        seal.get("inventory_bytes"),
    )
    if (
        seal.get("schema") != PROJECT_RUNTIME_CANDIDATE_SCHEMA
        or seal.get("status") != "sealed"
        or seal.get("target_tag") != capsule.target_tag
        or _version(seal.get("target_tag")) != capsule.target_version
        or seal.get("target_commit") != capsule.target_commit
        or seal.get("transaction_ref") != capsule.transaction_ref
        or seal.get("candidate_locator")
        != capsule.candidate_root.relative_to(
            capsule.project_root
        ).as_posix()
        or seal.get("inventory_sha256")
        != f"sha256:{capsule.inventory_sha256}"
        or seal.get("candidate_sha256")
        != f"sha256:{capsule.candidate_sha256}"
        or any(type(value) is not int or value < 0 for value in numeric_values)
        or seal.get("inventory_count") != capsule.inventory_count
        or seal.get("inventory_bytes") != capsule.inventory_bytes
        or identities != expected_identities
        or seal.get("runtime_parent_existed_before")
        is not capsule.runtime_parent_existed_before
        or seal.get("same_volume_verified") is not True
        or seal.get("recursive_directory_durability_verified") is not True
        or seal.get("seal_parent_durability_required") is not True
        or seal.get("marker_free_final_postimage") is not True
        or seal.get("post_approval_child_process_allowed") is not False
        or seal.get("post_approval_network_allowed") is not False
        or seal.get("post_approval_copy_allowed") is not False
        or seal.get("absolute_paths_echoed") is not False
        or (legacy_shape and capsule.existing_runtime_root_identity is not None)
    ):
        raise ProjectRuntimeError("project_runtime_cleanup_seal_invalid")
    return True


def load_runtime_candidate_cleanup_capsule(
    project_root: Path,
    transaction_root: Path,
) -> RuntimeCandidateCleanupCapsule:
    """Load only an exact private cleanup record; never inspect PATH or code."""

    project, transaction, transaction_ref, logical_candidate, logical_seal = (
        _candidate_paths(project_root, transaction_root)
    )
    capsule_path = _runtime_candidate_cleanup_capsule_path(transaction)
    try:
        before = capsule_path.lstat()
        if (
            capsule_path.is_symlink()
            or _is_reparse(before)
            or not stat_module.S_ISREG(before.st_mode)
            or _file_link_count(capsule_path, before) != 1
            or int(before.st_size) <= 0
            or int(before.st_size) > PROJECT_RUNTIME_CLEANUP_CAPSULE_MAX_BYTES
            or not _existing_components_are_real(project, capsule_path)
        ):
            raise ProjectRuntimeError("project_runtime_cleanup_capsule_invalid")
        raw = _read_limited(
            capsule_path,
            limit=PROJECT_RUNTIME_CLEANUP_CAPSULE_MAX_BYTES,
        )
        after = capsule_path.lstat()
    except ProjectRuntimeError as error:
        if str(error) == "project_runtime_cleanup_capsule_invalid":
            raise
        raise ProjectRuntimeError(
            "project_runtime_cleanup_capsule_unavailable"
        ) from error
    except OSError as error:
        raise ProjectRuntimeError(
            "project_runtime_cleanup_capsule_unavailable"
        ) from error
    if (
        raw is None
        or int(before.st_dev) != int(after.st_dev)
        or int(before.st_ino) != int(after.st_ino)
        or int(before.st_size) != int(after.st_size)
        or int(before.st_mtime_ns) != int(after.st_mtime_ns)
    ):
        raise ProjectRuntimeError("project_runtime_cleanup_capsule_unavailable")
    try:
        document = _json_without_duplicate_keys(raw)
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise ProjectRuntimeError("project_runtime_cleanup_capsule_invalid") from error
    if (
        not isinstance(document, dict)
        or set(document) != PROJECT_RUNTIME_CLEANUP_CAPSULE_KEYS
        or document.get("schema") != PROJECT_RUNTIME_CLEANUP_CAPSULE_SCHEMA
        or document.get("status") != "cleanup_intent"
        or document.get("transaction_ref") != transaction_ref
        or document.get("candidate_locator") != logical_candidate
        or document.get("seal_locator") != logical_seal
        or document.get("outer_transaction_ack_required_before_retire")
        is not True
        or document.get("absolute_paths_echoed") is not False
        or (
            json.dumps(document, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        != raw
    ):
        raise ProjectRuntimeError("project_runtime_cleanup_capsule_invalid")
    target_tag = document.get("target_tag")
    target_version = document.get("target_version")
    target_commit = document.get("target_commit")
    inventory_sha = document.get("inventory_sha256")
    candidate_sha = document.get("candidate_sha256")
    seal_sha = document.get("seal_sha256")
    numeric = (
        document.get("inventory_count"),
        document.get("inventory_bytes"),
        document.get("seal_mtime_ns"),
        document.get("seal_size_bytes"),
    )
    if (
        not isinstance(target_tag, str)
        or not isinstance(target_version, str)
        or _version(target_tag) != target_version
        or not isinstance(target_commit, str)
        or COMMIT_RE.fullmatch(target_commit) is None
        or any(
            not isinstance(item, int)
            or isinstance(item, bool)
            or item < 0
            for item in numeric
        )
        or not isinstance(inventory_sha, str)
        or not inventory_sha.startswith("sha256:")
        or SHA256_RE.fullmatch(inventory_sha.removeprefix("sha256:")) is None
        or not isinstance(candidate_sha, str)
        or not candidate_sha.startswith("sha256:")
        or SHA256_RE.fullmatch(candidate_sha.removeprefix("sha256:")) is None
        or not isinstance(seal_sha, str)
        or not seal_sha.startswith("sha256:")
        or SHA256_RE.fullmatch(seal_sha.removeprefix("sha256:")) is None
    ):
        raise ProjectRuntimeError("project_runtime_cleanup_capsule_invalid")
    try:
        project_identity = _sealed_identity(
            document.get("project_root_identity")
        )
        transaction_identity = _sealed_identity(
            document.get("transaction_root_identity")
        )
        candidate_identity = _sealed_identity(
            document.get("candidate_root_identity")
        )
        runtime_parent_identity = _sealed_identity(
            document.get("runtime_parent_identity")
        )
        capsule_parent_identity = _sealed_identity(
            document.get("capsule_parent_identity")
        )
        capsule_identity = _sealed_identity(
            document.get("capsule_identity")
        )
        seal_identity = _sealed_identity(document.get("seal_identity"))
        created_value = document.get("runtime_parent_created_identity")
        created_identity = (
            None if created_value is None else _sealed_identity(created_value)
        )
        existing_runtime_value = document.get(
            "existing_runtime_root_identity"
        )
        existing_runtime_identity = (
            None
            if existing_runtime_value is None
            else _sealed_identity(existing_runtime_value)
        )
    except ProjectRuntimeError as error:
        raise ProjectRuntimeError(
            "project_runtime_cleanup_capsule_invalid"
        ) from error
    existed_before = document.get("runtime_parent_existed_before")
    if (
        not isinstance(existed_before, bool)
        or (existed_before and created_identity is not None)
        or (not existed_before and created_identity != runtime_parent_identity)
        or _path_identity(project) != project_identity
        or _path_identity(transaction) != transaction_identity
        or _path_identity(transaction.parent) != capsule_parent_identity
        or capsule_identity
        != (int(before.st_dev), int(before.st_ino))
        or capsule_identity
        != (int(after.st_dev), int(after.st_ino))
        or not _existing_components_are_real(project, transaction.parent)
        or len(
            {
                project_identity[0],
                transaction_identity[0],
                candidate_identity[0],
                runtime_parent_identity[0],
                seal_identity[0],
                capsule_parent_identity[0],
                capsule_identity[0],
                *(
                    ()
                    if existing_runtime_identity is None
                    else (existing_runtime_identity[0],)
                ),
            }
        )
        != 1
    ):
        raise ProjectRuntimeError("project_runtime_cleanup_capsule_invalid")
    inventory = _cleanup_inventory_from_private_value(document.get("inventory"))
    inventory_digest = _recursive_candidate_inventory_digest(inventory)
    inventory_bytes = sum(
        item.size_bytes for item in inventory if item.entry_type == "file"
    )
    inventory_digest_value = inventory_sha.removeprefix("sha256:")
    quarantine = _runtime_candidate_cleanup_quarantine_path(
        transaction,
        inventory_digest_value,
    )
    try:
        expected_quarantine_locator = quarantine.relative_to(project).as_posix()
    except ValueError as error:
        raise ProjectRuntimeError("project_runtime_cleanup_capsule_invalid") from error
    if (
        inventory_digest != inventory_digest_value
        or document["inventory_count"] != len(inventory)
        or document["inventory_bytes"] != inventory_bytes
        or document.get("quarantine_locator") != expected_quarantine_locator
    ):
        raise ProjectRuntimeError("project_runtime_cleanup_capsule_invalid")
    capsule_sha256 = _sha256_bytes(raw)
    try:
        with _retained_default_stream_cleanup_file(
            capsule_path,
            identity=capsule_identity,
            mtime_ns=int(before.st_mtime_ns),
            size_bytes=int(before.st_size),
            sha256=capsule_sha256,
        ):
            pass
    except ProjectRuntimeError as error:
        raise ProjectRuntimeError(
            "project_runtime_cleanup_capsule_invalid"
        ) from error
    loaded = RuntimeCandidateCleanupCapsule(
        target_tag=target_tag,
        target_version=target_version,
        target_commit=target_commit,
        transaction_ref=transaction_ref,
        project_root=project,
        transaction_root=transaction,
        candidate_root=transaction / PROJECT_RUNTIME_CANDIDATE_NAME,
        quarantine_root=quarantine,
        seal_path=transaction / PROJECT_RUNTIME_CANDIDATE_SEAL_NAME,
        capsule_path=capsule_path,
        capsule_parent_identity=capsule_parent_identity,
        capsule_identity=capsule_identity,
        capsule_mtime_ns=int(before.st_mtime_ns),
        capsule_size_bytes=int(before.st_size),
        project_root_identity=project_identity,
        transaction_root_identity=transaction_identity,
        candidate_root_identity=candidate_identity,
        runtime_parent_identity=runtime_parent_identity,
        runtime_parent_existed_before=existed_before,
        runtime_parent_created_identity=created_identity,
        existing_runtime_root_identity=existing_runtime_identity,
        inventory=inventory,
        inventory_sha256=inventory_digest_value,
        inventory_count=document["inventory_count"],
        inventory_bytes=document["inventory_bytes"],
        candidate_sha256=candidate_sha.removeprefix("sha256:"),
        seal_identity=seal_identity,
        seal_mtime_ns=document["seal_mtime_ns"],
        seal_size_bytes=document["seal_size_bytes"],
        seal_sha256=seal_sha.removeprefix("sha256:"),
        capsule_bytes=raw,
        capsule_sha256=capsule_sha256,
    )
    _validate_runtime_cleanup_seal_or_terminal_topology(loaded)
    return loaded


def _runtime_cleanup_creation_observation_guard_held(
    candidate: PreparedRuntimeCandidate,
    *,
    capsule_present: bool,
) -> tuple[tuple[int, int], tuple[int, int], int, int] | None:
    """Re-prove the exact runtime namespace while the tx guard is held."""

    if not isinstance(candidate, PreparedRuntimeCandidate):
        return None
    try:
        project, transaction, transaction_ref, logical_candidate, logical_seal = (
            _candidate_paths(
                candidate.project_root,
                candidate.transaction_root,
            )
        )
        capsule_path = _runtime_candidate_cleanup_capsule_path(transaction)
        capsule_observation = _runtime_path_presence_observation(capsule_path)
        quarantine = _runtime_candidate_cleanup_quarantine_path(
            transaction,
            candidate.inventory_sha256,
        )
        quarantine_observation = _runtime_path_presence_observation(
            quarantine
        )
        runtime_parent = project / PROJECT_RUNTIME_RELATIVE_ROOT
        parent_observation = _runtime_path_presence_observation(runtime_parent)
        if (
            candidate.project_root != project
            or candidate.transaction_root != transaction
            or candidate.transaction_ref != transaction_ref
            or candidate.logical_candidate_path != logical_candidate
            or candidate.logical_seal_path != logical_seal
            or candidate.candidate_root
            != transaction / PROJECT_RUNTIME_CANDIDATE_NAME
            or candidate.seal_path
            != transaction / PROJECT_RUNTIME_CANDIDATE_SEAL_NAME
            or capsule_observation
            != {"state": "passed", "present": capsule_present}
            or quarantine_observation
            != {"state": "passed", "present": False}
            or parent_observation
            != {"state": "passed", "present": True}
            or _path_identity(project) != candidate.project_root_identity
            or _path_identity(transaction)
            != candidate.transaction_root_identity
            or _path_identity(runtime_parent)
            != candidate.runtime_parent_identity
            or not _existing_components_are_real(project, runtime_parent)
        ):
            return None

        candidate_observation = _runtime_inventory_observation(
            candidate.candidate_root,
            identity=candidate.candidate_root_identity,
            inventory=candidate.inventory,
        )
        final_observation = _runtime_inventory_observation(
            runtime_path(project, candidate.target_version),
            identity=candidate.candidate_root_identity,
            inventory=candidate.inventory,
        )
        if (
            candidate_observation["state"] == "unavailable"
            or final_observation["state"] == "unavailable"
            or (
                bool(candidate_observation["matches"])
                == bool(final_observation["matches"])
            )
        ):
            # Exactly one name owns the sealed candidate generation: its
            # private staging name before promotion, or its final runtime name
            # after promotion.  Neither and both are fixed-closed drift.
            return None

        capsule_parent = transaction.parent
        parent_stat = capsule_parent.lstat()
        if (
            capsule_parent.is_symlink()
            or _is_reparse(parent_stat)
            or not stat_module.S_ISDIR(parent_stat.st_mode)
            or not _existing_components_are_real(project, capsule_parent)
        ):
            return None
        capsule_parent_identity = (
            int(parent_stat.st_dev),
            int(parent_stat.st_ino),
        )
        seal_stat = candidate.seal_path.lstat()
        if (
            candidate.seal_path.is_symlink()
            or _is_reparse(seal_stat)
            or not stat_module.S_ISREG(seal_stat.st_mode)
            or _file_link_count(candidate.seal_path, seal_stat) != 1
        ):
            return None
        seal_bytes = _read_limited(
            candidate.seal_path,
            limit=256 * 1024,
            ancestor_root=transaction,
        )
        after = candidate.seal_path.lstat()
        seal_identity = (
            int(seal_stat.st_dev),
            int(seal_stat.st_ino),
        )
        if (
            seal_bytes != candidate.seal_bytes
            or _sha256_bytes(seal_bytes or b"") != candidate.seal_sha256
            or (int(after.st_dev), int(after.st_ino)) != seal_identity
            or int(after.st_size) != int(seal_stat.st_size)
            or int(after.st_mtime_ns) != int(seal_stat.st_mtime_ns)
            or len(
                {
                    candidate.project_root_identity[0],
                    candidate.transaction_root_identity[0],
                    candidate.candidate_root_identity[0],
                    candidate.runtime_parent_identity[0],
                    capsule_parent_identity[0],
                    seal_identity[0],
                }
            )
            != 1
        ):
            return None
    except (OSError, ProjectRuntimeError, TypeError, ValueError):
        return None
    return (
        capsule_parent_identity,
        seal_identity,
        int(seal_stat.st_mtime_ns),
        int(seal_stat.st_size),
    )


def _create_runtime_candidate_cleanup_capsule(
    candidate: PreparedRuntimeCandidate,
) -> RuntimeCandidateCleanupCapsule | None:
    """Durably bind cleanup authority before moving the candidate root."""

    if not isinstance(candidate, PreparedRuntimeCandidate):
        return None
    try:
        from .project_update_transaction import (
            runtime_cleanup_sidecar_creation_guard,
        )

        with runtime_cleanup_sidecar_creation_guard(
            candidate.project_root,
            candidate.transaction_ref,
        ) as revalidate_transaction:
            revalidate_transaction()
            observed = _runtime_cleanup_creation_observation_guard_held(
                candidate,
                capsule_present=False,
            )
            if observed is None:
                return None
            (
                capsule_parent_identity,
                seal_identity,
                seal_mtime_ns,
                seal_size_bytes,
            ) = observed
            capsule_path = _runtime_candidate_cleanup_capsule_path(
                candidate.transaction_root
            )
            capsule_parent = candidate.transaction_root.parent
            with _retained_default_stream_cleanup_file(
                candidate.seal_path,
                identity=seal_identity,
                mtime_ns=seal_mtime_ns,
                size_bytes=seal_size_bytes,
                sha256=candidate.seal_sha256,
            ):
                # This is the last cooperative abort-state check before the
                # create-only sidecar publication.
                revalidate_transaction()
                (
                    raw,
                    capsule_identity,
                    capsule_mtime_ns,
                    capsule_size_bytes,
                ) = _write_runtime_candidate_cleanup_capsule_exact_new(
                    capsule_path,
                    candidate,
                    capsule_parent_identity=capsule_parent_identity,
                    seal_identity=seal_identity,
                    seal_mtime_ns=seal_mtime_ns,
                    seal_size_bytes=seal_size_bytes,
                )
                _flush_directory_durable(capsule_parent)
                revalidate_transaction()
            after_publication = (
                _runtime_cleanup_creation_observation_guard_held(
                    candidate,
                    capsule_present=True,
                )
            )
            if after_publication != observed:
                return None
            loaded = load_runtime_candidate_cleanup_capsule(
                candidate.project_root,
                candidate.transaction_root,
            )
            revalidate_transaction()
    except Exception:
        # Namespace lock contention, an unavailable guard, transaction abort,
        # or any local observation failure must leave all existing names
        # untouched.  A partial O_EXCL sidecar is durable review-only evidence.
        return None
    if (
        loaded.capsule_bytes != raw
        or loaded.capsule_identity != capsule_identity
        or loaded.capsule_mtime_ns != capsule_mtime_ns
        or loaded.capsule_size_bytes != capsule_size_bytes
        or loaded.candidate_root_identity != candidate.candidate_root_identity
        or loaded.inventory != candidate.inventory
        or loaded.candidate_sha256 != candidate.candidate_sha256
        or loaded.seal_sha256 != candidate.seal_sha256
    ):
        return None
    return loaded


def _reload_exact_runtime_candidate_cleanup_capsule(
    capsule: RuntimeCandidateCleanupCapsule,
) -> RuntimeCandidateCleanupCapsule | None:
    if not isinstance(capsule, RuntimeCandidateCleanupCapsule):
        return None
    try:
        loaded = load_runtime_candidate_cleanup_capsule(
            capsule.project_root,
            capsule.transaction_root,
        )
    except ProjectRuntimeError:
        return None
    if (
        loaded.capsule_sha256 != capsule.capsule_sha256
        or loaded.capsule_bytes != capsule.capsule_bytes
        or loaded != capsule
    ):
        return None
    return loaded


def _delete_exact_inventory_tree_contents(
    root: Path,
    inventory: tuple[RuntimeCandidateInventoryEntry, ...],
    *,
    root_identity: tuple[int, int],
) -> bool:
    """Delete exact children while retaining the root as a resume tombstone.

    Missing children are allowed because an earlier process may have exited
    after deleting only part of the exact tree.  Every child that is still
    present must retain its sealed identity (and, for files, its exact bytes)
    before the Windows retained-handle primitive marks that object itself for
    deletion.  The exact root intentionally remains until a caller has retired
    its other recovery evidence.  POSIX remains fixed closed in the primitive.
    """

    try:
        root_presence = _runtime_path_presence_observation(root)
        if root_presence == {"state": "passed", "present": False}:
            return False
        if root_presence["state"] == "unavailable":
            return False
        if _path_identity(root) != root_identity:
            return False
        live_inventory = _candidate_inventory_snapshot(root)
        expected_by_path = {item.relative_path: item for item in inventory}
        if len(expected_by_path) != len(inventory):
            return False
        for live in live_inventory:
            expected = expected_by_path.get(live.relative_path)
            if expected is None or live.entry_type != expected.entry_type:
                return False
            if (
                live.device != expected.device
                or live.inode != expected.inode
                or (
                    live.entry_type == "file"
                    and live != expected
                )
            ):
                return False

        from .legacy_cleanup_bound_delete import (
            _delete_exact_approved_empty_directory,
            _delete_exact_approved_file,
        )

        files = [item for item in live_inventory if item.entry_type == "file"]
        directories = [
            item for item in live_inventory if item.entry_type == "directory"
        ]
        for item in sorted(
            files,
            key=lambda value: (value.relative_path.count("/"), value.relative_path),
            reverse=True,
        ):
            path = root / PurePosixPath(item.relative_path)
            try:
                _delete_exact_approved_file(
                    root,
                    path,
                    {
                        "identity": {
                            "device": item.device,
                            "inode": item.inode,
                        },
                        "mtime_ns": item.mtime_ns,
                        "sha256": item.sha256,
                        "size": item.size_bytes,
                        "type": "file",
                    },
                )
            except BaseException:
                if _runtime_path_presence_observation(path) != {
                    "state": "passed",
                    "present": False,
                }:
                    return False
            _flush_directory_durable(path.parent)
        for item in sorted(
            directories,
            key=lambda value: (value.relative_path.count("/"), value.relative_path),
            reverse=True,
        ):
            path = root / PurePosixPath(item.relative_path)
            try:
                _delete_exact_approved_empty_directory(
                    root,
                    path,
                    {
                        "identity": {
                            "birthtime_ns": None,
                            "device": item.device,
                            "inode": item.inode,
                        },
                        "type": "directory",
                    },
                )
            except BaseException:
                if _runtime_path_presence_observation(path) != {
                    "state": "passed",
                    "present": False,
                }:
                    return False
            _flush_directory_durable(path.parent)
    except BaseException:
        return False
    try:
        return bool(
            _path_identity(root) == root_identity
            and _candidate_inventory_snapshot(root) == ()
        )
    except (OSError, ProjectRuntimeError):
        return False


def _delete_exact_empty_inventory_root(
    root: Path,
    *,
    root_identity: tuple[int, int],
) -> bool:
    """Delete the exact empty tombstone root and durably prove its absence."""

    presence = _runtime_path_presence_observation(root)
    if presence["state"] == "unavailable":
        return False
    if presence["present"] is False:
        try:
            _flush_directory_durable(root.parent)
        except ProjectRuntimeError:
            return False
        return True
    try:
        if (
            _path_identity(root) != root_identity
            or _candidate_inventory_snapshot(root) != ()
        ):
            return False
        from .legacy_cleanup_bound_delete import (
            _delete_exact_approved_empty_directory,
        )

        root_stat = root.lstat()
        _delete_exact_approved_empty_directory(
            root.parent,
            root,
            {
                "identity": {
                    "birthtime_ns": getattr(
                        root_stat,
                        "st_birthtime_ns",
                        None,
                    ),
                    "device": root_identity[0],
                    "inode": root_identity[1],
                },
                "type": "directory",
            },
        )
        _flush_directory_durable(root.parent)
    except (OSError, ProjectRuntimeError):
        return False
    return _runtime_path_presence_observation(root) == {
        "state": "passed",
        "present": False,
    }


def _delete_exact_inventory_tree(
    root: Path,
    inventory: tuple[RuntimeCandidateInventoryEntry, ...],
    *,
    root_identity: tuple[int, int],
) -> bool:
    """Delete one detached exact tree, including its root, with resume safety."""

    presence = _runtime_path_presence_observation(root)
    if presence["state"] == "unavailable":
        return False
    if presence["present"] is False:
        return True
    return bool(
        _delete_exact_inventory_tree_contents(
            root,
            inventory,
            root_identity=root_identity,
        )
        and _delete_exact_empty_inventory_root(
            root,
            root_identity=root_identity,
        )
    )


def _runtime_deletion_tree_observation(
    path: Path,
    *,
    identity: tuple[int, int],
    inventory: tuple[RuntimeCandidateInventoryEntry, ...],
) -> dict[str, str]:
    """Classify one exact tree, including a safe partial-delete resume state."""

    presence = _runtime_path_presence_observation(path)
    if presence["state"] == "unavailable":
        return {"state": "unavailable", "tree_state": "unknown"}
    if presence["present"] is False:
        return {"state": "passed", "tree_state": "absent"}
    try:
        if _path_identity(path) != identity:
            return {"state": "failed", "tree_state": "drift"}
        live_inventory = _candidate_inventory_snapshot(path)
    except ProjectRuntimeError as error:
        unavailable = _runtime_error_is_observation_unavailable(error)
        return {
            "state": "unavailable" if unavailable else "failed",
            "tree_state": "unknown" if unavailable else "drift",
        }
    except OSError:
        return {"state": "unavailable", "tree_state": "unknown"}

    expected_by_path = {item.relative_path: item for item in inventory}
    if len(expected_by_path) != len(inventory):
        return {"state": "failed", "tree_state": "drift"}
    for live in live_inventory:
        expected = expected_by_path.get(live.relative_path)
        if (
            expected is None
            or live.entry_type != expected.entry_type
            or live.device != expected.device
            or live.inode != expected.inode
            or (live.entry_type == "file" and live != expected)
        ):
            return {"state": "failed", "tree_state": "drift"}
    return {
        "state": "passed",
        "tree_state": "exact" if live_inventory == inventory else "partial",
    }


def _restore_exact_owned_runtime_parent(
    project_root: Path,
    *,
    expected_identity: tuple[int, int] | None,
    existed_before: bool,
    created_identity: tuple[int, int] | None,
    promoted_final_present: bool,
) -> bool:
    """Restore an exact-created runtime parent without trusting name absence."""

    if expected_identity is None:
        return False
    runtime_parent = project_root / PROJECT_RUNTIME_RELATIVE_ROOT
    parent_presence = _runtime_path_presence_observation(runtime_parent)
    if parent_presence["state"] == "unavailable":
        return False
    if parent_presence["present"] is False:
        if existed_before or promoted_final_present:
            return False
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
            or not _existing_components_are_real(project_root, runtime_parent)
        ):
            return False
        if existed_before or promoted_final_present:
            return True
        if created_identity != expected_identity:
            return False
        with os.scandir(runtime_parent) as iterator:
            if next(iterator, None) is not None:
                return False
        from .legacy_cleanup_bound_delete import (
            _delete_exact_approved_empty_directory,
        )

        _delete_exact_approved_empty_directory(
            runtime_parent.parent,
            runtime_parent,
            {
                "identity": {
                    "birthtime_ns": getattr(
                        stat_result,
                        "st_birthtime_ns",
                        None,
                    ),
                    "device": int(stat_result.st_dev),
                    "inode": int(stat_result.st_ino),
                },
                "type": "directory",
            },
        )
        _flush_directory_durable(runtime_parent.parent)
    except (OSError, ProjectRuntimeError):
        return False
    return _runtime_path_presence_observation(runtime_parent) == {
        "state": "passed",
        "present": False,
    }


def _restore_runtime_parent_after_candidate_cleanup(
    candidate: PreparedRuntimeCandidate,
    *,
    promoted_final_present: bool,
) -> bool:
    """Restore an exact-owned empty runtime parent on sealed cancellation."""

    return _restore_exact_owned_runtime_parent(
        candidate.project_root,
        expected_identity=candidate.runtime_parent_identity,
        existed_before=candidate.runtime_parent_existed_before,
        created_identity=candidate.runtime_parent_created_identity,
        promoted_final_present=promoted_final_present,
    )


def _delete_exact_candidate_seal(candidate: PreparedRuntimeCandidate) -> bool:
    """Retire the exact seal or durably confirm a prior retirement."""

    seal_presence = _runtime_path_presence_observation(candidate.seal_path)
    if seal_presence["state"] == "unavailable":
        return False
    if seal_presence["present"] is False:
        try:
            _flush_directory_durable(candidate.transaction_root)
        except ProjectRuntimeError:
            return False
        return True
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
        from .legacy_cleanup_bound_delete import _delete_exact_approved_file

        _delete_exact_approved_file(
            candidate.transaction_root,
            candidate.seal_path,
            {
                "identity": {
                    "device": int(seal_stat.st_dev),
                    "inode": int(seal_stat.st_ino),
                },
                "mtime_ns": int(seal_stat.st_mtime_ns),
                "sha256": candidate.seal_sha256,
                "size": int(seal_stat.st_size),
                "type": "file",
            },
        )
        _flush_directory_durable(candidate.transaction_root)
    except FileNotFoundError:
        try:
            _flush_directory_durable(candidate.transaction_root)
        except ProjectRuntimeError:
            return False
    except (OSError, ProjectRuntimeError):
        return False
    return _runtime_path_presence_observation(candidate.seal_path) == {
        "state": "passed",
        "present": False,
    }


def _delete_exact_cleanup_bound_seal(
    capsule: RuntimeCandidateCleanupCapsule,
) -> bool:
    """Retire only the normal seal identity bound before cleanup began."""

    presence = _runtime_path_presence_observation(capsule.seal_path)
    if presence["state"] == "unavailable":
        return False
    if presence["present"] is False:
        try:
            _flush_directory_durable(capsule.transaction_root)
        except ProjectRuntimeError:
            return False
        return True
    try:
        before = capsule.seal_path.lstat()
        if (
            capsule.seal_path.is_symlink()
            or _is_reparse(before)
            or not stat_module.S_ISREG(before.st_mode)
            or _file_link_count(capsule.seal_path, before) != 1
            or (int(before.st_dev), int(before.st_ino))
            != capsule.seal_identity
            or int(before.st_mtime_ns) != capsule.seal_mtime_ns
            or int(before.st_size) != capsule.seal_size_bytes
            or not _existing_components_are_real(
                capsule.project_root,
                capsule.seal_path,
            )
        ):
            return False
        digest, size = _sha256_file(
            capsule.seal_path,
            limit=256 * 1024,
        )
        after = capsule.seal_path.lstat()
        if (
            digest != capsule.seal_sha256
            or size != capsule.seal_size_bytes
            or int(after.st_dev) != int(before.st_dev)
            or int(after.st_ino) != int(before.st_ino)
            or int(after.st_mtime_ns) != int(before.st_mtime_ns)
            or int(after.st_size) != int(before.st_size)
        ):
            return False
        from .legacy_cleanup_bound_delete import _delete_exact_approved_file

        _delete_exact_approved_file(
            capsule.transaction_root,
            capsule.seal_path,
            {
                "identity": {
                    "device": capsule.seal_identity[0],
                    "inode": capsule.seal_identity[1],
                },
                "mtime_ns": capsule.seal_mtime_ns,
                "sha256": capsule.seal_sha256,
                "size": capsule.seal_size_bytes,
                "type": "file",
            },
        )
        _flush_directory_durable(capsule.transaction_root)
    except (OSError, ProjectRuntimeError):
        return False
    return _runtime_path_presence_observation(capsule.seal_path) == {
        "state": "passed",
        "present": False,
    }


def runtime_candidate_cleanup_terminal_evidence(
    capsule: RuntimeCandidateCleanupCapsule,
) -> dict[str, Any] | None:
    """Return evidence only after all domain cleanup names are proven absent.

    The capsule deliberately remains present.  The outer project-update
    transaction must bind this digest in a durable terminal checkpoint before
    its existing exact transaction cleanup retires the capsule.
    """

    loaded = _reload_exact_runtime_candidate_cleanup_capsule(capsule)
    if loaded is None:
        return None
    observations = (
        _runtime_path_presence_observation(loaded.candidate_root),
        _runtime_path_presence_observation(loaded.quarantine_root),
        _runtime_path_presence_observation(loaded.seal_path),
    )
    if any(
        observation != {"state": "passed", "present": False}
        for observation in observations
    ):
        return None
    final = runtime_path(loaded.project_root, loaded.target_version)
    final_observation = _runtime_inventory_observation(
        final,
        identity=loaded.candidate_root_identity,
        inventory=loaded.inventory,
    )
    if final_observation["state"] == "unavailable":
        return None
    final_matches = bool(final_observation["matches"])
    runtime_parent = loaded.project_root / PROJECT_RUNTIME_RELATIVE_ROOT
    parent_presence = _runtime_path_presence_observation(runtime_parent)
    if parent_presence["state"] == "unavailable":
        return None
    keep_parent = loaded.runtime_parent_existed_before or final_matches
    if keep_parent:
        try:
            parent_exact = bool(
                parent_presence["present"] is True
                and _path_identity(runtime_parent)
                == loaded.runtime_parent_identity
                and _existing_components_are_real(
                    loaded.project_root,
                    runtime_parent,
                )
            )
        except (OSError, ProjectRuntimeError):
            return None
        if not parent_exact:
            return None
    elif parent_presence != {"state": "passed", "present": False}:
        return None
    evidence = loaded.public_evidence()
    evidence["cleanup_complete"] = True
    evidence["candidate_root_absent"] = True
    evidence["quarantine_root_absent"] = True
    evidence["normal_seal_absent"] = True
    evidence["runtime_parent_restored"] = True
    return evidence


def _runtime_cleanup_terminal_evidence_sha256(
    evidence: Mapping[str, Any],
) -> str | None:
    """Match the transaction journal's canonical, newline-free digest."""

    try:
        raw = json.dumps(
            dict(evidence),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        return None
    return f"sha256:{_sha256_bytes(raw)}"


def _disk_revalidated_runtime_cleanup_ack(
    project_root: Path,
    durable_ack: object,
) -> object | None:
    """Return only a fresh transaction-issued ack for this exact project.

    The lazy import avoids a module cycle.  The transaction module owns the
    unforgeable issued-instance registry and re-reads its durable authority;
    this module never accepts a digest string, mapping, or caller-built
    dataclass as a deletion capability.
    """

    try:
        from . import project_update_transaction as update_transaction

        if not update_transaction.revalidate_runtime_cleanup_durable_ack(
            durable_ack
        ):
            return None
        transaction_ref = durable_ack.transaction_ref
        current = update_transaction.load_runtime_cleanup_durable_ack(
            project_root,
            transaction_ref,
        )
        if (
            current is None
            or current != durable_ack
            or not update_transaction.revalidate_runtime_cleanup_durable_ack(
                current
            )
        ):
            return None
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    except Exception:
        # The outer module deliberately exposes only a boolean revalidator.
        # Any unexpected loader/revalidation failure is fixed closed and must
        # never become capsule-deletion authority.
        return None
    return current


def retire_runtime_candidate_cleanup_capsule(
    capsule: RuntimeCandidateCleanupCapsule | None,
    *,
    durable_ack: object,
    project_root: Path | None = None,
) -> bool:
    """Retire a capsule only with a disk-loaded durable outer authority.

    ``capsule=None`` is the fresh-process, already-retired path: the exact
    deterministic sidecar name must be absent and the caller must provide the
    project root so the transaction module can re-open its durable authority.
    """

    if capsule is not None and not isinstance(
        capsule, RuntimeCandidateCleanupCapsule
    ):
        return False
    if capsule is None and project_root is None:
        return False
    project = Path(
        os.path.abspath(
            str(capsule.project_root if capsule is not None else project_root)
        )
    )
    if project_root is not None and Path(
        os.path.abspath(str(project_root))
    ) != project:
        return False
    ack = _disk_revalidated_runtime_cleanup_ack(project, durable_ack)
    if ack is None:
        return False
    try:
        transaction_ref = ack.transaction_ref
        target_tag = ack.target_tag
        transaction = (
            project
            / PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
            / transaction_ref
        )
        _project, transaction, _ref, _candidate, _seal = _candidate_paths(
            project,
            transaction,
        )
    except (AttributeError, OSError, ProjectRuntimeError, TypeError):
        return False

    capsule_path = _runtime_candidate_cleanup_capsule_path(transaction)
    presence = _runtime_path_presence_observation(capsule_path)
    if presence["state"] == "unavailable":
        return False
    if presence["present"] is False:
        try:
            if (
                capsule is not None
                and (
                    capsule.project_root != project
                    or capsule.transaction_root != transaction
                    or capsule.transaction_ref != transaction_ref
                    or capsule.target_tag != target_tag
                    or not secrets.compare_digest(
                        ack.runtime_cleanup_capsule_sha256,
                        f"sha256:{capsule.capsule_sha256}",
                    )
                    or not secrets.compare_digest(
                        ack.runtime_cleanup_capsule_identity_sha256,
                        capsule.public_evidence()[
                            "runtime_cleanup_capsule_identity_sha256"
                        ],
                    )
                )
            ):
                return False
            _flush_directory_durable(capsule_path.parent)
            if (
                _runtime_path_presence_observation(capsule_path)
                != {"state": "passed", "present": False}
                or _disk_revalidated_runtime_cleanup_ack(
                    project,
                    ack,
                )
                is None
            ):
                return False
        except (AttributeError, OSError, ProjectRuntimeError, TypeError):
            return False
        return True
    if capsule is None:
        return False
    loaded = _reload_exact_runtime_candidate_cleanup_capsule(capsule)
    if loaded is None:
        return False
    evidence = runtime_candidate_cleanup_terminal_evidence(loaded)
    evidence_sha256 = (
        None
        if evidence is None
        else _runtime_cleanup_terminal_evidence_sha256(evidence)
    )
    identity_sha256 = loaded.public_evidence()[
        "runtime_cleanup_capsule_identity_sha256"
    ]
    try:
        ack_matches = bool(
            evidence_sha256 is not None
            and loaded.project_root == project
            and loaded.transaction_root == transaction
            and loaded.transaction_ref == transaction_ref
            and loaded.target_tag == target_tag
            and secrets.compare_digest(
                ack.runtime_cleanup_terminal_evidence_sha256,
                evidence_sha256,
            )
            and secrets.compare_digest(
                ack.runtime_cleanup_capsule_sha256,
                f"sha256:{loaded.capsule_sha256}",
            )
            and secrets.compare_digest(
                ack.runtime_cleanup_capsule_identity_sha256,
                identity_sha256,
            )
        )
    except (AttributeError, TypeError):
        return False
    if not ack_matches:
        return False
    try:
        with _retained_default_stream_cleanup_file(
            loaded.capsule_path,
            identity=loaded.capsule_identity,
            mtime_ns=loaded.capsule_mtime_ns,
            size_bytes=loaded.capsule_size_bytes,
            sha256=loaded.capsule_sha256,
        ):
            if (
                _disk_revalidated_runtime_cleanup_ack(project, ack) is None
            ):
                return False
        from .legacy_cleanup_bound_delete import _delete_exact_approved_file

        _delete_exact_approved_file(
            loaded.capsule_path.parent,
            loaded.capsule_path,
            {
                "identity": {
                    "device": loaded.capsule_identity[0],
                    "inode": loaded.capsule_identity[1],
                },
                "mtime_ns": loaded.capsule_mtime_ns,
                "sha256": loaded.capsule_sha256,
                "size": loaded.capsule_size_bytes,
                "type": "file",
            },
        )
        _flush_directory_durable(loaded.capsule_path.parent)
    except (OSError, ProjectRuntimeError):
        return False
    return _runtime_path_presence_observation(loaded.capsule_path) == {
        "state": "passed",
        "present": False,
    }


def _resume_runtime_candidate_tree_cleanup(
    loaded: RuntimeCandidateCleanupCapsule,
) -> bool:
    """Clean the candidate tree while capsule and seal handles are retained."""

    root_presence = _runtime_path_presence_observation(loaded.candidate_root)
    quarantine_presence = _runtime_path_presence_observation(
        loaded.quarantine_root
    )
    if (
        root_presence["state"] == "unavailable"
        or quarantine_presence["state"] == "unavailable"
        or (
            root_presence["present"] is True
            and quarantine_presence["present"] is True
        )
    ):
        return False
    if root_presence["present"] is True:
        root_observation = _runtime_deletion_tree_observation(
            loaded.candidate_root,
            identity=loaded.candidate_root_identity,
            inventory=loaded.inventory,
        )
        if root_observation != {"state": "passed", "tree_state": "exact"}:
            return False
        try:
            _atomic_promote_directory_no_replace(
                loaded.candidate_root,
                loaded.quarantine_root,
            )
            _flush_directory_durable(loaded.transaction_root)
        except (OSError, ProjectRuntimeError):
            return False
    quarantine_presence = _runtime_path_presence_observation(
        loaded.quarantine_root
    )
    if quarantine_presence["state"] == "unavailable":
        return False
    final = runtime_path(loaded.project_root, loaded.target_version)
    final_observation = _runtime_inventory_observation(
        final,
        identity=loaded.candidate_root_identity,
        inventory=loaded.inventory,
    )
    if final_observation["state"] == "unavailable":
        return False
    final_matches = bool(final_observation["matches"])
    if not _restore_exact_owned_runtime_parent(
        loaded.project_root,
        expected_identity=loaded.runtime_parent_identity,
        existed_before=loaded.runtime_parent_existed_before,
        created_identity=loaded.runtime_parent_created_identity,
        promoted_final_present=final_matches,
    ):
        return False
    if quarantine_presence["present"] is True:
        try:
            _flush_directory_durable(loaded.transaction_root)
        except ProjectRuntimeError:
            return False
        quarantine_observation = _runtime_deletion_tree_observation(
            loaded.quarantine_root,
            identity=loaded.candidate_root_identity,
            inventory=loaded.inventory,
        )
        if not (
            quarantine_observation["state"] == "passed"
            and quarantine_observation["tree_state"] in {"exact", "partial"}
            and _delete_exact_inventory_tree_contents(
                loaded.quarantine_root,
                loaded.inventory,
                root_identity=loaded.candidate_root_identity,
            )
            and _delete_exact_empty_inventory_root(
                loaded.quarantine_root,
                root_identity=loaded.candidate_root_identity,
            )
        ):
            return False
    return True


def resume_runtime_candidate_cleanup(
    capsule: RuntimeCandidateCleanupCapsule,
) -> RuntimeCandidateCleanupCapsule | None:
    """Resume cleanup from one disk-loaded capsule without prior Python state."""

    loaded = _reload_exact_runtime_candidate_cleanup_capsule(capsule)
    if loaded is None:
        return None
    try:
        with _retained_default_stream_cleanup_file(
            loaded.capsule_path,
            identity=loaded.capsule_identity,
            mtime_ns=loaded.capsule_mtime_ns,
            size_bytes=loaded.capsule_size_bytes,
            sha256=loaded.capsule_sha256,
        ):
            seal_presence = _runtime_path_presence_observation(
                loaded.seal_path
            )
            if seal_presence["state"] == "unavailable":
                return None
            if seal_presence["present"] is True:
                with _retained_default_stream_cleanup_file(
                    loaded.seal_path,
                    identity=loaded.seal_identity,
                    mtime_ns=loaded.seal_mtime_ns,
                    size_bytes=loaded.seal_size_bytes,
                    sha256=loaded.seal_sha256,
                ):
                    if not _resume_runtime_candidate_tree_cleanup(loaded):
                        return None
            else:
                if _validate_runtime_cleanup_seal_or_terminal_topology(
                    loaded
                ) is not False:
                    return None
                if not _resume_runtime_candidate_tree_cleanup(loaded):
                    return None
            if not _delete_exact_cleanup_bound_seal(loaded):
                return None
    except ProjectRuntimeError:
        return None
    return (
        loaded
        if runtime_candidate_cleanup_terminal_evidence(loaded) is not None
        else None
    )


def cleanup_prepared_runtime_candidate(
    candidate: PreparedRuntimeCandidate,
) -> RuntimeCandidateCleanupCapsule | None:
    """Begin or resume cleanup while retaining durable terminal evidence."""

    if not isinstance(candidate, PreparedRuntimeCandidate):
        return None
    capsule_path = _runtime_candidate_cleanup_capsule_path(
        candidate.transaction_root
    )
    capsule_presence = _runtime_path_presence_observation(capsule_path)
    root_presence = _runtime_path_presence_observation(candidate.candidate_root)
    quarantine = _runtime_candidate_cleanup_quarantine_path(
        candidate.transaction_root,
        candidate.inventory_sha256,
    )
    quarantine_presence = _runtime_path_presence_observation(quarantine)
    if (
        capsule_presence["state"] == "unavailable"
        or root_presence["state"] == "unavailable"
        or quarantine_presence["state"] == "unavailable"
    ):
        return None
    capsule: RuntimeCandidateCleanupCapsule | None
    if capsule_presence["present"] is True:
        try:
            capsule = load_runtime_candidate_cleanup_capsule(
                candidate.project_root,
                candidate.transaction_root,
            )
        except ProjectRuntimeError:
            return None
        if (
            capsule.target_tag != candidate.target_tag
            or capsule.target_version != candidate.target_version
            or capsule.target_commit != candidate.target_commit
            or capsule.candidate_root_identity
            != candidate.candidate_root_identity
            or capsule.runtime_parent_identity
            != candidate.runtime_parent_identity
            or capsule.runtime_parent_existed_before
            != candidate.runtime_parent_existed_before
            or capsule.runtime_parent_created_identity
            != candidate.runtime_parent_created_identity
            or capsule.inventory != candidate.inventory
            or capsule.inventory_sha256 != candidate.inventory_sha256
            or capsule.candidate_sha256 != candidate.candidate_sha256
            or capsule.seal_sha256 != candidate.seal_sha256
        ):
            return None
    else:
        if quarantine_presence["present"] is True:
            # A detached root without its prior durable authority is preserved.
            return None
        if root_presence["present"] is True:
            parsed_supply = project_runtime_supply_lock(
                candidate.supply_lock_bytes,
                expected_target=candidate.target_tag,
            )
            if parsed_supply is None:
                return None
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
                return None
        else:
            final_observation = _runtime_inventory_observation(
                runtime_path(candidate.project_root, candidate.target_version),
                identity=candidate.candidate_root_identity,
                inventory=candidate.inventory,
            )
            if (
                final_observation["state"] != "passed"
                or not final_observation["matches"]
            ):
                return None
        capsule = _create_runtime_candidate_cleanup_capsule(candidate)
        if capsule is None:
            return None
    return resume_runtime_candidate_cleanup(capsule)


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
    return bool(
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
    """Exact, resume-safe rollback for one materialized runtime.

    The updater calls this while holding the archive-wide mutation lock.  The
    implementation nevertheless treats a non-cooperating name race as drift:
    the public runtime name is first moved, without replacement, into the
    private transaction.  Deletion is permitted only after that detached name
    is re-bound to the sealed root identity and recursive inventory.
    """

    if not isinstance(runtime, RuntimeMaterialization):
        return False
    if not runtime.created:
        return True
    project = Path(os.path.abspath(str(project_root)))
    final = runtime_path(project, runtime.target_version)
    transaction_root = runtime.transaction_root
    transaction_identity = runtime.transaction_root_identity
    new_identity = runtime.runtime_root_identity
    runtime_parent_identity = runtime.runtime_parent_identity
    if (
        runtime.final_path != final
        or not runtime.inventory
        or new_identity is None
        or runtime_parent_identity is None
        or transaction_root is None
        or transaction_identity is None
        or _sha256_bytes(runtime.receipt_bytes) != runtime.receipt_sha256
    ):
        return False

    transaction_presence = _runtime_path_presence_observation(transaction_root)
    if transaction_presence != {"state": "passed", "present": True}:
        return False
    try:
        _project, exact_transaction, _ref, _candidate, _seal = _candidate_paths(
            project,
            transaction_root,
        )
        if (
            exact_transaction != transaction_root
            or _path_identity(transaction_root) != transaction_identity
            or transaction_identity[0] != new_identity[0]
            or runtime_parent_identity[0] != new_identity[0]
        ):
            return False
    except (OSError, ProjectRuntimeError):
        return False

    rollback_candidate = (
        transaction_root / PROJECT_RUNTIME_ROLLBACK_CANDIDATE_NAME
    )
    runtimes_root = project / PROJECT_RUNTIME_RELATIVE_ROOT

    def observe_runtime_parent() -> dict[str, str]:
        presence = _runtime_path_presence_observation(runtimes_root)
        if presence["state"] == "unavailable":
            return {"state": "unavailable", "parent_state": "unknown"}
        if presence["present"] is False:
            return {"state": "passed", "parent_state": "absent"}
        try:
            stat_result = runtimes_root.lstat()
            matches = bool(
                not runtimes_root.is_symlink()
                and not _is_reparse(stat_result)
                and runtimes_root.is_dir()
                and (
                    int(stat_result.st_dev),
                    int(stat_result.st_ino),
                )
                == runtime_parent_identity
                and _existing_components_are_real(project, runtimes_root)
            )
        except OSError:
            return {"state": "unavailable", "parent_state": "unknown"}
        return {
            "state": "passed" if matches else "failed",
            "parent_state": "exact" if matches else "drift",
        }

    def observe_new(path: Path) -> dict[str, str]:
        return _runtime_deletion_tree_observation(
            path,
            identity=new_identity,
            inventory=runtime.inventory,
        )

    def observations_are_available(*items: Mapping[str, str]) -> bool:
        return all(item["state"] != "unavailable" for item in items)

    def flush_completion_names(*, final_present: bool) -> bool:
        try:
            runtime_parent = observe_runtime_parent()
            if runtime_parent["state"] == "unavailable":
                return False
            if runtime_parent["parent_state"] == "exact":
                _flush_directory_durable(runtimes_root)
            elif (
                runtime_parent["parent_state"] != "absent"
                or final_present
                or runtime.runtime_parent_existed_before
            ):
                return False
            else:
                _flush_directory_durable(runtimes_root.parent)
            _flush_directory_durable(transaction_root)
        except ProjectRuntimeError:
            return False
        return True

    if runtime.repaired:
        backup = runtime.replaced_runtime_path
        old_identity = runtime.replaced_runtime_identity
        if (
            backup is None
            or old_identity is None
            or backup
            != transaction_root / PROJECT_RUNTIME_REPAIR_BACKUP_NAME
        ):
            return False

        def observe_old(path: Path) -> dict[str, str]:
            return _runtime_deletion_tree_observation(
                path,
                identity=old_identity,
                inventory=runtime.replaced_runtime_inventory,
            )

        final_new = observe_new(final)
        final_old = observe_old(final)
        backup_old = observe_old(backup)
        rollback_new = observe_new(rollback_candidate)
        runtime_parent = observe_runtime_parent()
        if not observations_are_available(
            final_new,
            final_old,
            backup_old,
            rollback_new,
            runtime_parent,
        ):
            return False
        if runtime_parent["parent_state"] != "exact":
            return False

        if (
            final_new["tree_state"] == "exact"
            and backup_old["tree_state"] == "exact"
            and rollback_new["tree_state"] == "absent"
        ):
            try:
                _atomic_promote_directory_no_replace(
                    final,
                    rollback_candidate,
                )
            except OSError:
                return False
            final_new = observe_new(final)
            rollback_new = observe_new(rollback_candidate)
            if not (
                final_new == {"state": "passed", "tree_state": "absent"}
                and rollback_new
                == {"state": "passed", "tree_state": "exact"}
            ):
                return False
            if not flush_completion_names(final_present=False):
                return False
            final_new = observe_new(final)
            final_old = observe_old(final)
            backup_old = observe_old(backup)
            rollback_new = observe_new(rollback_candidate)

        if (
            final_old["tree_state"] == "absent"
            and backup_old["tree_state"] == "exact"
            and rollback_new["tree_state"] in {"exact", "partial"}
        ):
            # A reopened process cannot assume the two directory-entry halves
            # of the prior detach were durable merely because they are now
            # visible.  Flush and re-prove them before restoring the preimage.
            if not flush_completion_names(final_present=False):
                return False
            final_old = observe_old(final)
            backup_old = observe_old(backup)
            rollback_new = observe_new(rollback_candidate)
            if not (
                final_old
                == {"state": "passed", "tree_state": "absent"}
                and backup_old
                == {"state": "passed", "tree_state": "exact"}
                and rollback_new["state"] == "passed"
                and rollback_new["tree_state"] in {"exact", "partial"}
            ):
                return False
            try:
                _atomic_promote_directory_no_replace(backup, final)
            except OSError:
                return False
            final_old = observe_old(final)
            backup_old = observe_old(backup)
            rollback_new = observe_new(rollback_candidate)
            if not (
                final_old == {"state": "passed", "tree_state": "exact"}
                and backup_old
                == {"state": "passed", "tree_state": "absent"}
                and rollback_new["state"] == "passed"
                and rollback_new["tree_state"] in {"exact", "partial"}
            ):
                return False
            if not flush_completion_names(final_present=True):
                return False
            final_old = observe_old(final)
            backup_old = observe_old(backup)
            rollback_new = observe_new(rollback_candidate)

        if (
            final_old["tree_state"] == "exact"
            and backup_old["tree_state"] == "absent"
            and rollback_new["tree_state"] in {"exact", "partial"}
        ):
            # The old runtime must be durably restored before the only exact
            # new-runtime copy is retired from the private transaction.
            if not flush_completion_names(final_present=True):
                return False
            final_old = observe_old(final)
            backup_old = observe_old(backup)
            rollback_new = observe_new(rollback_candidate)
            if not (
                final_old == {"state": "passed", "tree_state": "exact"}
                and backup_old
                == {"state": "passed", "tree_state": "absent"}
                and rollback_new["state"] == "passed"
                and rollback_new["tree_state"] in {"exact", "partial"}
            ):
                return False
            if not _delete_exact_inventory_tree(
                rollback_candidate,
                runtime.inventory,
                root_identity=new_identity,
            ):
                return False
            final_old = observe_old(final)
            backup_old = observe_old(backup)
            rollback_new = observe_new(rollback_candidate)

        if not (
            final_old == {"state": "passed", "tree_state": "exact"}
            and backup_old == {"state": "passed", "tree_state": "absent"}
            and rollback_new
            == {"state": "passed", "tree_state": "absent"}
            and flush_completion_names(final_present=True)
        ):
            return False
    else:
        final_new = observe_new(final)
        rollback_new = observe_new(rollback_candidate)
        runtime_parent = observe_runtime_parent()
        if not observations_are_available(
            final_new,
            rollback_new,
            runtime_parent,
        ):
            return False
        if (
            final_new["tree_state"] == "exact"
            and rollback_new["tree_state"] == "absent"
        ):
            if runtime_parent["parent_state"] != "exact":
                return False
            try:
                _atomic_promote_directory_no_replace(
                    final,
                    rollback_candidate,
                )
            except OSError:
                return False
            final_new = observe_new(final)
            rollback_new = observe_new(rollback_candidate)
            if not (
                final_new == {"state": "passed", "tree_state": "absent"}
                and rollback_new
                == {"state": "passed", "tree_state": "exact"}
            ):
                return False
            if not flush_completion_names(final_present=False):
                return False
            final_new = observe_new(final)
            rollback_new = observe_new(rollback_candidate)
        if (
            final_new["tree_state"] == "absent"
            and rollback_new["tree_state"] in {"exact", "partial"}
        ):
            if not flush_completion_names(final_present=False):
                return False
            final_new = observe_new(final)
            rollback_new = observe_new(rollback_candidate)
            if not (
                final_new
                == {"state": "passed", "tree_state": "absent"}
                and rollback_new["state"] == "passed"
                and rollback_new["tree_state"] in {"exact", "partial"}
            ):
                return False
            if not _delete_exact_inventory_tree(
                rollback_candidate,
                runtime.inventory,
                root_identity=new_identity,
            ):
                return False
            final_new = observe_new(final)
            rollback_new = observe_new(rollback_candidate)
        if not (
            final_new == {"state": "passed", "tree_state": "absent"}
            and rollback_new
            == {"state": "passed", "tree_state": "absent"}
            and flush_completion_names(final_present=False)
            and _restore_exact_owned_runtime_parent(
                project,
                expected_identity=runtime_parent_identity,
                existed_before=runtime.runtime_parent_existed_before,
                created_identity=runtime.runtime_parent_created_identity,
                promoted_final_present=False,
            )
        ):
            return False

    if mutation_tracker is not None:
        return runtime_mutation_restored(project, mutation_tracker)
    return True
