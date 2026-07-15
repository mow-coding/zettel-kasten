"""Preview, install, verify, and remove the packaged WOM archive Agent Skill."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Any
import uuid

from . import __version__
from .resource_paths import runtime_resource_root


SKILL_NAME = "wom-archive"
INSTALL_MANIFEST_NAME = ".wom-kit-install.json"
INSTALL_MANIFEST_SCHEMA = "wom-kit/runtime-skill-install-manifest/v0.1"
STATUS_SCHEMA = "wom-kit/runtime-skill-status/v0.1"
INSTALL_SCHEMA = "wom-kit/runtime-skill-install/v0.1"
UNINSTALL_SCHEMA = "wom-kit/runtime-skill-uninstall/v0.1"
SOURCE_PACKAGE_SCHEMA = "wom-kit/runtime-skill-source-package/v0.1"
PLAN_SCHEMA = "wom-kit/runtime-skill-operation-plan/v0.1"
LOCK_NAME = f".{SKILL_NAME}.wom-kit.lock"
SAFE_REVIEWER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
MAX_SOURCE_FILE_BYTES = 2 * 1024 * 1024
MAX_SOURCE_PACKAGE_BYTES = 8 * 1024 * 1024
MAX_MANIFEST_BYTES = 512 * 1024


@dataclass(frozen=True)
class SourceFile:
    path: str
    bytes: int
    sha256: str
    source_path: Path

    def public_row(self) -> dict[str, object]:
        return {"path": self.path, "bytes": self.bytes, "sha256": self.sha256}


@dataclass(frozen=True)
class SourcePackage:
    root: Path
    files: tuple[SourceFile, ...]
    total_bytes: int
    sha256: str


@dataclass(frozen=True)
class TargetLocation:
    host: str
    scope: str
    skills_root: Path
    target: Path
    path_hint: str
    target_path_sha256: str


@dataclass(frozen=True)
class TargetInspection:
    state: str
    manifest: dict[str, Any] | None
    manifest_sha256: str | None
    installed_version: str | None
    installed_source_sha256: str | None
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_sha256(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def safe_relative_path(value: object) -> str | None:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        return None
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or pure.as_posix() != value
        or any(part in {"", ".", ".."} for part in pure.parts)
        or any(part.endswith((" ", ".")) for part in pure.parts)
        or any(part.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES for part in pure.parts)
    ):
        return None
    return value


def default_source_root() -> Path:
    return runtime_resource_root("templates") / "ai-runtime" / SKILL_NAME


def is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(os.path, "isjunction", None)
    return bool(is_junction is not None and is_junction(path))


def load_source_package(source_root: Path | None = None) -> SourcePackage:
    root = Path(os.path.abspath(os.fspath((source_root or default_source_root()).expanduser())))
    if not root.is_dir() or has_symlink_component(root):
        raise ValueError("Packaged runtime skill source is missing or unsafe.")

    files: list[SourceFile] = []
    total_bytes = 0
    for path in sorted(root.rglob("*")):
        if is_link_like(path):
            raise ValueError("Packaged runtime skill source must not contain symlinks.")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("Packaged runtime skill source contains an unsupported entry.")
        relative = path.relative_to(root).as_posix()
        if safe_relative_path(relative) != relative or relative == INSTALL_MANIFEST_NAME:
            raise ValueError("Packaged runtime skill source contains an unsafe path.")
        data = path.read_bytes()
        if len(data) > MAX_SOURCE_FILE_BYTES:
            raise ValueError("Packaged runtime skill source contains an oversized file.")
        total_bytes += len(data)
        if total_bytes > MAX_SOURCE_PACKAGE_BYTES:
            raise ValueError("Packaged runtime skill source exceeds the bounded package size.")
        files.append(SourceFile(relative, len(data), sha256_bytes(data), path))

    if not files or not any(row.path == "SKILL.md" for row in files):
        raise ValueError("Packaged runtime skill source is missing SKILL.md.")
    digest_input = {
        "schema": SOURCE_PACKAGE_SCHEMA,
        "skill_name": SKILL_NAME,
        "files": [row.public_row() for row in files],
    }
    return SourcePackage(root, tuple(files), total_bytes, canonical_sha256(digest_input))


def has_symlink_component(path: Path) -> bool:
    current = path
    while True:
        if is_link_like(current):
            return True
        if current.parent == current:
            return False
        current = current.parent


def resolve_target_location(
    *,
    host: str,
    scope: str,
    repo_root: Path | None = None,
    skills_root: Path | None = None,
) -> TargetLocation:
    normalized_host = host.strip().lower()
    normalized_scope = scope.strip().lower()
    if normalized_host not in {"codex", "custom"}:
        raise ValueError("host must be codex or custom")

    if normalized_host == "codex" and normalized_scope == "user":
        if repo_root is not None or skills_root is not None:
            raise ValueError("codex user scope does not accept repo_root or skills_root")
        resolved_skills_root = Path(
            os.path.abspath(os.fspath(Path.home() / ".agents" / "skills"))
        )
        hint = "user/.agents/skills/wom-archive"
    elif normalized_host == "codex" and normalized_scope == "repo":
        if repo_root is None or skills_root is not None:
            raise ValueError("codex repo scope requires repo_root and does not accept skills_root")
        resolved_repo = Path(os.path.abspath(os.fspath(repo_root.expanduser())))
        if not resolved_repo.is_dir() or has_symlink_component(resolved_repo):
            raise ValueError("repo_root must be an existing non-symlink directory")
        resolved_skills_root = Path(
            os.path.abspath(os.fspath(resolved_repo / ".agents" / "skills"))
        )
        if not resolved_skills_root.is_relative_to(resolved_repo):
            raise ValueError("resolved Codex skills root escapes repo_root")
        hint = "repo/.agents/skills/wom-archive"
    elif normalized_host == "custom" and normalized_scope == "custom":
        if skills_root is None or repo_root is not None:
            raise ValueError("custom scope requires skills_root and does not accept repo_root")
        resolved_skills_root = Path(os.path.abspath(os.fspath(skills_root.expanduser())))
        if resolved_skills_root.parent == resolved_skills_root:
            raise ValueError("custom skills_root must not be a filesystem root")
        hint = "custom-skills/wom-archive"
    else:
        raise ValueError("host and scope are incompatible")

    if has_symlink_component(resolved_skills_root):
        raise ValueError("skills root has an existing symlink component")
    target = Path(os.path.abspath(os.fspath(resolved_skills_root / SKILL_NAME)))
    if target.parent != resolved_skills_root or target.name != SKILL_NAME:
        raise ValueError("resolved skill target is outside the skills root")
    return TargetLocation(
        host=normalized_host,
        scope=normalized_scope,
        skills_root=resolved_skills_root,
        target=target,
        path_hint=hint,
        target_path_sha256=sha256_bytes(os.fsencode(str(target))),
    )


def validate_manifest_files(value: object) -> tuple[dict[str, object], ...] | None:
    if not isinstance(value, list) or not value:
        return None
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict):
            return None
        path = safe_relative_path(raw.get("path"))
        size = raw.get("bytes")
        digest = raw.get("sha256")
        if (
            path is None
            or path == INSTALL_MANIFEST_NAME
            or path in seen
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or size > MAX_SOURCE_FILE_BYTES
            or not isinstance(digest, str)
            or SHA256_RE.fullmatch(digest) is None
        ):
            return None
        seen.add(path)
        rows.append({"path": path, "bytes": size, "sha256": digest})
    return tuple(rows)


def inspect_target(
    location: TargetLocation,
    source: SourcePackage,
    *,
    package_version: str = __version__,
) -> TargetInspection:
    target = location.target
    if is_link_like(target):
        return TargetInspection(
            "blocked_symlink", None, None, None, None,
            ("Existing skill target is a symlink and will not be touched.",), (),
        )
    if not target.exists():
        return TargetInspection("absent", None, None, None, None, (), ())
    if not target.is_dir():
        return TargetInspection(
            "blocked_not_directory", None, None, None, None,
            ("Existing skill target is not a directory and will not be touched.",), (),
        )

    manifest_path = target / INSTALL_MANIFEST_NAME
    if not manifest_path.is_file() or is_link_like(manifest_path):
        return TargetInspection(
            "unmanaged_conflict", None, None, None, None,
            ("Existing skill directory has no valid WOM-kit ownership manifest.",), (),
        )
    try:
        raw_manifest = manifest_path.read_bytes()
    except OSError:
        return TargetInspection(
            "managed_invalid", None, None, None, None,
            ("Existing WOM-kit skill manifest could not be read safely.",), (),
        )
    if len(raw_manifest) > MAX_MANIFEST_BYTES:
        return TargetInspection(
            "managed_invalid", None, None, None, None,
            ("Existing WOM-kit skill manifest exceeds the size limit.",), (),
        )
    try:
        manifest = json.loads(raw_manifest.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        manifest = None
    if not isinstance(manifest, dict):
        return TargetInspection(
            "managed_invalid", None, sha256_bytes(raw_manifest), None, None,
            ("Existing WOM-kit skill manifest is invalid.",), (),
        )

    file_rows = validate_manifest_files(manifest.get("files"))
    installed_version = manifest.get("package_version")
    installed_source_sha256 = manifest.get("source_package_sha256")
    installed_at = manifest.get("installed_at")
    reviewed_by = manifest.get("reviewed_by")
    manifest_payload_sha256 = manifest.get("manifest_payload_sha256")
    expected_manifest_keys = {
        "schema",
        "skill_name",
        "package_version",
        "host",
        "scope",
        "source_package_sha256",
        "installed_at",
        "reviewed_by",
        "files",
        "manifest_payload_sha256",
    }
    payload = {
        key: value
        for key, value in manifest.items()
        if key != "manifest_payload_sha256"
    }
    if (
        set(manifest) != expected_manifest_keys
        or manifest.get("schema") != INSTALL_MANIFEST_SCHEMA
        or manifest.get("skill_name") != SKILL_NAME
        or manifest.get("host") != location.host
        or manifest.get("scope") != location.scope
        or not isinstance(installed_version, str)
        or not installed_version
        or not isinstance(installed_source_sha256, str)
        or SHA256_RE.fullmatch(installed_source_sha256) is None
        or not isinstance(installed_at, str)
        or UTC_TIMESTAMP_RE.fullmatch(installed_at) is None
        or safe_reviewer(
            reviewed_by if isinstance(reviewed_by, str) else None
        ) != reviewed_by
        or not isinstance(manifest_payload_sha256, str)
        or SHA256_RE.fullmatch(manifest_payload_sha256) is None
        or canonical_sha256(payload) != manifest_payload_sha256
        or file_rows is None
    ):
        return TargetInspection(
            "managed_invalid", manifest, sha256_bytes(raw_manifest),
            installed_version if isinstance(installed_version, str) else None,
            installed_source_sha256 if isinstance(installed_source_sha256, str) else None,
            ("Existing WOM-kit skill manifest does not match this installation contract.",), (),
        )

    expected_files = {str(row["path"]): row for row in file_rows}
    actual_files: set[str] = set()
    actual_dirs: set[str] = set()
    for path in target.rglob("*"):
        if is_link_like(path):
            return TargetInspection(
                "managed_drift", manifest, sha256_bytes(raw_manifest), installed_version,
                installed_source_sha256,
                ("Managed skill directory contains a symlink and will not be changed.",), (),
            )
        relative = path.relative_to(target).as_posix()
        if path.is_dir():
            actual_dirs.add(relative)
        elif path.is_file() and relative != INSTALL_MANIFEST_NAME:
            actual_files.add(relative)
        elif not path.is_file():
            return TargetInspection(
                "managed_drift", manifest, sha256_bytes(raw_manifest), installed_version,
                installed_source_sha256,
                ("Managed skill directory contains an unsupported entry.",), (),
            )

    expected_dirs = {
        PurePosixPath(path).parent.as_posix()
        for path in expected_files
        if PurePosixPath(path).parent.as_posix() != "."
    }
    expanded_expected_dirs = set(expected_dirs)
    for value in tuple(expected_dirs):
        parent = PurePosixPath(value).parent
        while parent.as_posix() != ".":
            expanded_expected_dirs.add(parent.as_posix())
            parent = parent.parent
    if actual_files != set(expected_files) or actual_dirs != expanded_expected_dirs:
        return TargetInspection(
            "managed_drift", manifest, sha256_bytes(raw_manifest), installed_version,
            installed_source_sha256,
            ("Managed skill files no longer match the ownership manifest inventory.",), (),
        )

    for relative, row in expected_files.items():
        path = target / Path(relative)
        try:
            data = path.read_bytes()
        except OSError:
            return TargetInspection(
                "managed_drift", manifest, sha256_bytes(raw_manifest), installed_version,
                installed_source_sha256,
                ("Managed skill file could not be read safely.",), (),
            )
        if len(data) != row["bytes"] or sha256_bytes(data) != row["sha256"]:
            return TargetInspection(
                "managed_drift", manifest, sha256_bytes(raw_manifest), installed_version,
                installed_source_sha256,
                ("Managed skill file bytes differ from the ownership manifest.",), (),
            )

    state = (
        "managed_current"
        if installed_version == package_version and installed_source_sha256 == source.sha256
        else "managed_outdated"
    )
    return TargetInspection(
        state, manifest, sha256_bytes(raw_manifest), installed_version,
        installed_source_sha256, (), (),
    )


def transaction_target_location(location: TargetLocation, target: Path) -> TargetLocation:
    return TargetLocation(
        host=location.host,
        scope=location.scope,
        skills_root=target.parent,
        target=target,
        path_hint="private-transaction-copy/wom-archive",
        target_path_sha256=sha256_bytes(os.fsencode(str(target))),
    )


def target_projection(location: TargetLocation, *, redact_local_paths: bool) -> dict[str, object]:
    return {
        "host": location.host,
        "scope": location.scope,
        "skill_name": SKILL_NAME,
        "path": None if redact_local_paths else str(location.target),
        "path_redacted": bool(redact_local_paths),
        "path_hint": location.path_hint,
        "target_path_sha256": location.target_path_sha256,
    }


def source_projection(source: SourcePackage, package_version: str) -> dict[str, object]:
    return {
        "package_version": package_version,
        "skill_name": SKILL_NAME,
        "file_count": len(source.files),
        "total_bytes": source.total_bytes,
        "source_package_sha256": source.sha256,
        "source_path_exposed": False,
    }


def inspection_projection(inspection: TargetInspection) -> dict[str, object]:
    return {
        "state": inspection.state,
        "managed": inspection.state.startswith("managed_"),
        "installed_version": inspection.installed_version,
        "installed_source_package_sha256": inspection.installed_source_sha256,
        "install_manifest_sha256": inspection.manifest_sha256,
        "file_bodies_exposed": False,
    }


def operation_plan_sha256(
    operation: str,
    location: TargetLocation,
    source: SourcePackage,
    inspection: TargetInspection,
    package_version: str,
) -> str:
    return canonical_sha256(
        {
            "schema": PLAN_SCHEMA,
            "operation": operation,
            "host": location.host,
            "scope": location.scope,
            "skill_name": SKILL_NAME,
            "target_path_sha256": location.target_path_sha256,
            "package_version": package_version,
            "source_package_sha256": source.sha256,
            "target_state": inspection.state,
            "install_manifest_sha256": inspection.manifest_sha256,
            "installed_version": inspection.installed_version,
            "installed_source_package_sha256": inspection.installed_source_sha256,
        }
    )


def common_closed_actions(*, wrote_host_files: bool) -> dict[str, bool]:
    return {
        "archive_read": False,
        "archive_write": False,
        "host_skill_files_written": wrote_host_files,
        "provider_api_called": False,
        "network_called": False,
        "secrets_read": False,
        "credentials_read": False,
        "generated_graph_created": False,
    }


def blocked_result(
    *,
    schema: str,
    operation: str,
    host: str,
    scope: str,
    blocker: str,
) -> dict[str, object]:
    return {
        "ok": False,
        "schema": schema,
        "lifecycle_action": operation,
        "status": "blocked",
        "target": {
            "host": host,
            "scope": scope,
            "skill_name": SKILL_NAME,
            "path": None,
            "path_redacted": True,
        },
        "would_write": False,
        "closed_actions": common_closed_actions(wrote_host_files=False),
        "next_safe_actions": ["Correct the target options, then run the read-only preview again."],
        "blockers": [blocker],
        "warnings": [],
    }


def build_operation_result(
    *,
    operation: str,
    location: TargetLocation,
    source: SourcePackage,
    inspection: TargetInspection,
    package_version: str,
    redact_local_paths: bool,
) -> dict[str, object]:
    if operation == "status":
        schema = STATUS_SCHEMA
        status = inspection.state
        ok = not inspection.blockers
        would_write = False
    elif operation == "install":
        schema = INSTALL_SCHEMA
        status_by_state = {
            "absent": "ready_to_install",
            "managed_outdated": "ready_to_update",
            "managed_current": "already_current",
        }
        status = status_by_state.get(inspection.state, "blocked")
        ok = status != "blocked"
        would_write = status in {"ready_to_install", "ready_to_update"}
    elif operation == "uninstall":
        schema = UNINSTALL_SCHEMA
        status_by_state = {
            "absent": "already_absent",
            "managed_outdated": "ready_to_uninstall",
            "managed_current": "ready_to_uninstall",
        }
        status = status_by_state.get(inspection.state, "blocked")
        ok = status != "blocked"
        would_write = status == "ready_to_uninstall"
    else:  # pragma: no cover - internal programming guard.
        raise ValueError(f"Unknown runtime skill operation: {operation}")

    plan_sha256 = operation_plan_sha256(operation, location, source, inspection, package_version)
    blockers = list(inspection.blockers)
    if status == "blocked" and not blockers:
        blockers.append("Current target state is not eligible for this operation.")

    if operation == "status":
        next_actions = {
            "absent": ["Run runtime-skill-install with --dry-run before installing."],
            "managed_current": ["No action is required. Restart Codex only if the skill is not visible."],
            "managed_outdated": ["Run runtime-skill-install with --dry-run to preview a managed update."],
        }.get(inspection.state, ["Review the blocker without editing or deleting the existing directory."])
    elif operation == "install" and would_write:
        next_actions = [
            "Review this plan, then rerun the same target options with --approve, --reviewed-by, and --expected-plan-sha256.",
            "Restart Codex only if the installed skill is not detected automatically.",
        ]
    elif operation == "install" and status == "already_current":
        next_actions = ["No write is needed. Restart Codex only if the skill is not visible."]
    elif operation == "uninstall" and would_write:
        next_actions = [
            "Review this plan, then rerun the same target options with --approve, --reviewed-by, and --expected-plan-sha256."
        ]
    elif operation == "uninstall" and status == "already_absent":
        next_actions = ["No write is needed; the managed skill is already absent."]
    else:
        next_actions = ["Review the blocker without editing or deleting the existing directory."]

    return {
        "ok": bool(ok and not blockers),
        "schema": schema,
        "lifecycle_action": f"runtime_skill_{operation}",
        "status": status,
        "dry_run": True,
        "target": target_projection(location, redact_local_paths=redact_local_paths),
        "source_package": source_projection(source, package_version),
        "installation": inspection_projection(inspection),
        "operation_plan_sha256": plan_sha256,
        "would_write": would_write,
        "approval_requirements": {
            "required_for_write": would_write,
            "reviewed_by_required": would_write,
            "expected_plan_sha256_required": would_write,
        },
        "privacy": {
            "local_paths_redacted": redact_local_paths,
            "file_bodies_exposed": False,
            "secret_values_exposed": False,
        },
        "closed_actions": common_closed_actions(wrote_host_files=False),
        "next_safe_actions": next_actions,
        "blockers": blockers,
        "warnings": list(inspection.warnings),
    }


def runtime_skill_status(
    *,
    host: str = "codex",
    scope: str = "user",
    repo_root: Path | None = None,
    skills_root: Path | None = None,
    redact_local_paths: bool = True,
    source_root: Path | None = None,
    package_version: str = __version__,
) -> dict[str, object]:
    try:
        source = load_source_package(source_root)
        location = resolve_target_location(
            host=host, scope=scope, repo_root=repo_root, skills_root=skills_root
        )
        inspection = inspect_target(location, source, package_version=package_version)
    except (OSError, ValueError):
        return blocked_result(
            schema=STATUS_SCHEMA,
            operation="runtime_skill_status",
            host=host,
            scope=scope,
            blocker="Runtime skill status could not resolve a safe source and target.",
        )
    return build_operation_result(
        operation="status",
        location=location,
        source=source,
        inspection=inspection,
        package_version=package_version,
        redact_local_paths=redact_local_paths,
    )


def build_install_manifest(
    source: SourcePackage,
    location: TargetLocation,
    *,
    package_version: str,
    reviewed_by: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": INSTALL_MANIFEST_SCHEMA,
        "skill_name": SKILL_NAME,
        "package_version": package_version,
        "host": location.host,
        "scope": location.scope,
        "source_package_sha256": source.sha256,
        "installed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reviewed_by": reviewed_by,
        "files": [row.public_row() for row in source.files],
    }
    return {**payload, "manifest_payload_sha256": canonical_sha256(payload)}


def write_staging_skill(
    staging: Path,
    source: SourcePackage,
    manifest: dict[str, object],
) -> None:
    staging.mkdir(parents=False, exist_ok=False)
    for row in source.files:
        destination = staging / Path(row.path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = row.source_path.read_bytes()
        if len(data) != row.bytes or sha256_bytes(data) != row.sha256:
            raise RuntimeError("Runtime skill source changed after approval planning.")
        destination.write_bytes(data)
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    (staging / INSTALL_MANIFEST_NAME).write_bytes(manifest_bytes)


def acquire_lock(skills_root: Path) -> Path:
    skills_root.mkdir(parents=True, exist_ok=True)
    if has_symlink_component(skills_root):
        raise RuntimeError("Skills root became unsafe before write.")
    lock_path = skills_root / LOCK_NAME
    with lock_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(
            {"schema": "wom-kit/runtime-skill-operation-lock/v0.1", "skill_name": SKILL_NAME},
            handle,
            ensure_ascii=True,
            sort_keys=True,
        )
        handle.write("\n")
    return lock_path


def safe_reviewer(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    return candidate if SAFE_REVIEWER_RE.fullmatch(candidate) else None


def runtime_skill_install(
    *,
    dry_run: bool,
    approve: bool,
    reviewed_by: str | None = None,
    expected_plan_sha256: str | None = None,
    host: str = "codex",
    scope: str = "user",
    repo_root: Path | None = None,
    skills_root: Path | None = None,
    redact_local_paths: bool = True,
    source_root: Path | None = None,
    package_version: str = __version__,
) -> dict[str, object]:
    if dry_run == approve:
        return blocked_result(
            schema=INSTALL_SCHEMA,
            operation="runtime_skill_install",
            host=host,
            scope=scope,
            blocker="Choose exactly one of dry_run or approve.",
        )
    try:
        source = load_source_package(source_root)
        location = resolve_target_location(
            host=host, scope=scope, repo_root=repo_root, skills_root=skills_root
        )
        inspection = inspect_target(location, source, package_version=package_version)
    except (OSError, ValueError):
        return blocked_result(
            schema=INSTALL_SCHEMA,
            operation="runtime_skill_install",
            host=host,
            scope=scope,
            blocker="Runtime skill install could not resolve a safe source and target.",
        )

    preview = build_operation_result(
        operation="install",
        location=location,
        source=source,
        inspection=inspection,
        package_version=package_version,
        redact_local_paths=redact_local_paths,
    )
    if dry_run or not preview.get("ok") or not preview.get("would_write"):
        return preview

    reviewer = safe_reviewer(reviewed_by)
    if reviewer is None:
        preview["ok"] = False
        preview["status"] = "blocked"
        preview["blockers"] = ["approve requires a safe non-secret reviewed_by actor id"]
        return preview
    if not isinstance(expected_plan_sha256, str) or not SHA256_RE.fullmatch(expected_plan_sha256):
        preview["ok"] = False
        preview["status"] = "blocked"
        preview["blockers"] = ["approve requires the exact expected_plan_sha256 from dry-run"]
        return preview
    if expected_plan_sha256 != preview["operation_plan_sha256"]:
        preview["ok"] = False
        preview["status"] = "blocked"
        preview["blockers"] = ["expected_plan_sha256 does not match the current install plan"]
        return preview

    lock_path: Path | None = None
    staging: Path | None = None
    backup: Path | None = None
    promoted = False
    warnings: list[str] = []
    prior_state = inspection.state
    try:
        lock_path = acquire_lock(location.skills_root)
        source = load_source_package(source_root)
        inspection = inspect_target(location, source, package_version=package_version)
        current_plan = operation_plan_sha256("install", location, source, inspection, package_version)
        if current_plan != expected_plan_sha256:
            raise RuntimeError("Runtime skill install plan changed before write.")
        if inspection.state not in {"absent", "managed_outdated"}:
            raise RuntimeError("Runtime skill target is no longer eligible for install.")

        nonce = uuid.uuid4().hex
        staging = location.skills_root.parent / f".{SKILL_NAME}.install-{nonce}"
        backup = location.skills_root.parent / f".{SKILL_NAME}.backup-{nonce}"
        if staging.exists() or backup.exists():
            raise RuntimeError("Runtime skill transaction path collision.")
        manifest = build_install_manifest(
            source, location, package_version=package_version, reviewed_by=reviewer
        )
        write_staging_skill(staging, source, manifest)
        source_after_staging = load_source_package(source_root)
        if source_after_staging.sha256 != source.sha256:
            raise RuntimeError("Runtime skill source changed while staging approved files.")

        if inspection.state == "managed_outdated":
            location.target.rename(backup)
            backup_inspection = inspect_target(
                transaction_target_location(location, backup),
                source,
                package_version=package_version,
            )
            if backup_inspection.state not in {"managed_current", "managed_outdated"}:
                backup.rename(location.target)
                backup = None
                raise RuntimeError("Managed runtime skill changed during update preparation.")
        try:
            staging.rename(location.target)
            staging = None
            promoted = True
        except BaseException:
            if backup is not None and backup.exists() and not location.target.exists():
                backup.rename(location.target)
                backup = None
            raise

        installed = inspect_target(location, source, package_version=package_version)
        if installed.state != "managed_current":
            raise RuntimeError("Installed runtime skill did not pass manifest verification.")

        if backup is not None and backup.exists():
            backup_inspection = inspect_target(
                transaction_target_location(location, backup),
                source,
                package_version=package_version,
            )
            if backup_inspection.state in {"managed_current", "managed_outdated"}:
                try:
                    shutil.rmtree(backup)
                    backup = None
                except OSError:
                    warnings.append(
                        "Old verified skill backup remains outside the active skills directory."
                    )
            else:
                warnings.append("Old verified skill backup remains outside the active skills directory.")
    except (OSError, RuntimeError):
        if (
            staging is not None
            and staging.exists()
            and staging.parent == location.skills_root.parent
        ):
            shutil.rmtree(staging, ignore_errors=True)
        if promoted and location.target.exists():
            failed_copy = location.skills_root.parent / (
                f".{SKILL_NAME}.failed-{uuid.uuid4().hex}"
            )
            try:
                location.target.rename(failed_copy)
                warnings.append(
                    "Unverified replacement was moved outside the active skills directory."
                )
            except OSError:
                pass
        if backup is not None and backup.exists() and not location.target.exists():
            try:
                backup.rename(location.target)
                backup = None
            except OSError:
                pass
        failed = build_operation_result(
            operation="install",
            location=location,
            source=source,
            inspection=inspect_target(location, source, package_version=package_version),
            package_version=package_version,
            redact_local_paths=redact_local_paths,
        )
        failed["ok"] = False
        failed["status"] = "failed_before_verified_completion"
        failed["dry_run"] = False
        failed["would_write"] = False
        failed["blockers"] = ["Runtime skill install did not reach a verified complete state."]
        failed["warnings"] = warnings
        return failed
    finally:
        if lock_path is not None:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                warnings.append("Runtime skill operation lock cleanup is still pending.")

    result = build_operation_result(
        operation="install",
        location=location,
        source=source,
        inspection=installed,
        package_version=package_version,
        redact_local_paths=redact_local_paths,
    )
    post_write_plan_sha256 = result["operation_plan_sha256"]
    result.update(
        {
            "ok": True,
            "status": "installed" if prior_state == "absent" else "updated",
            "dry_run": False,
            "would_write": False,
            "written": True,
            "reviewed_by": reviewer,
            "operation_plan_sha256": expected_plan_sha256,
            "post_write_plan_sha256": post_write_plan_sha256,
            "closed_actions": common_closed_actions(wrote_host_files=True),
            "next_safe_actions": [
                "Confirm runtime-skill-status reports managed_current.",
                "Restart Codex only if the skill is not detected automatically.",
            ],
            "blockers": [],
            "warnings": warnings,
        }
    )
    return result


def runtime_skill_uninstall(
    *,
    dry_run: bool,
    approve: bool,
    reviewed_by: str | None = None,
    expected_plan_sha256: str | None = None,
    host: str = "codex",
    scope: str = "user",
    repo_root: Path | None = None,
    skills_root: Path | None = None,
    redact_local_paths: bool = True,
    source_root: Path | None = None,
    package_version: str = __version__,
) -> dict[str, object]:
    if dry_run == approve:
        return blocked_result(
            schema=UNINSTALL_SCHEMA,
            operation="runtime_skill_uninstall",
            host=host,
            scope=scope,
            blocker="Choose exactly one of dry_run or approve.",
        )
    try:
        source = load_source_package(source_root)
        location = resolve_target_location(
            host=host, scope=scope, repo_root=repo_root, skills_root=skills_root
        )
        inspection = inspect_target(location, source, package_version=package_version)
    except (OSError, ValueError):
        return blocked_result(
            schema=UNINSTALL_SCHEMA,
            operation="runtime_skill_uninstall",
            host=host,
            scope=scope,
            blocker="Runtime skill uninstall could not resolve a safe source and target.",
        )

    preview = build_operation_result(
        operation="uninstall",
        location=location,
        source=source,
        inspection=inspection,
        package_version=package_version,
        redact_local_paths=redact_local_paths,
    )
    if dry_run or not preview.get("ok") or not preview.get("would_write"):
        return preview

    reviewer = safe_reviewer(reviewed_by)
    if reviewer is None:
        preview["ok"] = False
        preview["status"] = "blocked"
        preview["blockers"] = ["approve requires a safe non-secret reviewed_by actor id"]
        return preview
    if not isinstance(expected_plan_sha256, str) or not SHA256_RE.fullmatch(expected_plan_sha256):
        preview["ok"] = False
        preview["status"] = "blocked"
        preview["blockers"] = ["approve requires the exact expected_plan_sha256 from dry-run"]
        return preview
    if expected_plan_sha256 != preview["operation_plan_sha256"]:
        preview["ok"] = False
        preview["status"] = "blocked"
        preview["blockers"] = ["expected_plan_sha256 does not match the current uninstall plan"]
        return preview

    lock_path: Path | None = None
    tombstone: Path | None = None
    cleanup_pending = False
    warnings: list[str] = []
    try:
        lock_path = acquire_lock(location.skills_root)
        source = load_source_package(source_root)
        inspection = inspect_target(location, source, package_version=package_version)
        current_plan = operation_plan_sha256("uninstall", location, source, inspection, package_version)
        if current_plan != expected_plan_sha256:
            raise RuntimeError("Runtime skill uninstall plan changed before write.")
        if inspection.state not in {"managed_current", "managed_outdated"}:
            raise RuntimeError("Runtime skill target is no longer eligible for uninstall.")

        tombstone = location.skills_root.parent / f".{SKILL_NAME}.uninstall-{uuid.uuid4().hex}"
        if tombstone.exists():
            raise RuntimeError("Runtime skill uninstall transaction path collision.")
        location.target.rename(tombstone)
        moved_inspection = inspect_target(
            transaction_target_location(location, tombstone),
            source,
            package_version=package_version,
        )
        if moved_inspection.state not in {"managed_current", "managed_outdated"}:
            tombstone.rename(location.target)
            tombstone = None
            raise RuntimeError("Managed runtime skill changed during uninstall preparation.")
        try:
            shutil.rmtree(tombstone)
            tombstone = None
        except OSError:
            cleanup_pending = True
    except (OSError, RuntimeError):
        if tombstone is not None and tombstone.exists() and not location.target.exists():
            try:
                tombstone.rename(location.target)
                tombstone = None
            except OSError:
                pass
        failed_inspection = inspect_target(location, source, package_version=package_version)
        failed = build_operation_result(
            operation="uninstall",
            location=location,
            source=source,
            inspection=failed_inspection,
            package_version=package_version,
            redact_local_paths=redact_local_paths,
        )
        failed["ok"] = False
        failed["status"] = "failed_before_verified_removal"
        failed["dry_run"] = False
        failed["would_write"] = False
        failed["blockers"] = ["Runtime skill uninstall did not reach a verified removed state."]
        failed["warnings"] = warnings
        return failed
    finally:
        if lock_path is not None:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                warnings.append("Runtime skill operation lock cleanup is still pending.")

    result = build_operation_result(
        operation="uninstall",
        location=location,
        source=source,
        inspection=inspect_target(location, source, package_version=package_version),
        package_version=package_version,
        redact_local_paths=redact_local_paths,
    )
    post_write_plan_sha256 = result["operation_plan_sha256"]
    result.update(
        {
            "ok": True,
            "status": "uninstalled_cleanup_pending" if cleanup_pending else "uninstalled",
            "dry_run": False,
            "would_write": False,
            "written": True,
            "reviewed_by": reviewer,
            "operation_plan_sha256": expected_plan_sha256,
            "post_write_plan_sha256": post_write_plan_sha256,
            "closed_actions": common_closed_actions(wrote_host_files=True),
            "next_safe_actions": [
                "Restart Codex if it still shows the removed skill from an earlier session."
            ],
            "blockers": [],
            "warnings": warnings + (
                ["Verified removed skill files remain in a non-active cleanup location."]
                if cleanup_pending
                else []
            ),
        }
    )
    return result
