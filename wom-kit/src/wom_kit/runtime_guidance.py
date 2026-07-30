"""Read-only host guidance readiness inspection for WOM archives."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import __version__
from . import archive_services
from . import runtime_skill_install

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only when dependency is absent.
    yaml = None


READINESS_SCHEMA = "wom-kit/runtime-guidance-readiness/v0.1"
MAX_AGENTS_BYTES = 512 * 1024
SUPPORTED_HOST = "codex"
SUPPORTED_SCOPE = "repo"
AGENTS_ROUTING_MARKERS = (
    (
        "ai_start_here",
        "archive ai-start-here <archive-root> --dry-run --progress --format json",
    ),
    ("action_routing", "action_routing"),
    (
        "official_archive_search",
        "archive search <archive-root> <query> --count-total --format json",
    ),
    (
        "raw_search_not_authoritative",
        "raw grep and raw sql are not authoritative",
    ),
)
SAFE_SKILL_STATES = {
    "absent",
    "managed_current",
    "managed_outdated",
    "managed_invalid",
    "managed_drift",
    "unmanaged_conflict",
    "blocked_symlink",
    "blocked_not_directory",
}
EXPECTED_LOCAL_INSPECTION_ERRORS: tuple[type[BaseException], ...] = (
    archive_services.ArchiveServiceError,
    OSError,
    UnicodeError,
    ValueError,
)
if yaml is not None:
    EXPECTED_LOCAL_INSPECTION_ERRORS += (yaml.YAMLError,)  # type: ignore[union-attr]
EXPECTED_ARCHIVE_IDENTITY_ERRORS = EXPECTED_LOCAL_INSPECTION_ERRORS + (
    RuntimeError,
)


def _safe_target(host: str, scope: str) -> dict[str, str]:
    normalized_host = host.strip().lower() if isinstance(host, str) else ""
    normalized_scope = scope.strip().lower() if isinstance(scope, str) else ""
    return {
        "host": normalized_host if normalized_host in {"codex", "custom"} else "unsupported",
        "scope": normalized_scope
        if normalized_scope in {"user", "repo", "custom"}
        else "unsupported",
    }


def _read_valid_archive_id(root: Path) -> str:
    archive_id = archive_services.read_archive_id(root)
    if not archive_id.strip():
        raise archive_services.ArchiveServiceError(
            "archive.yml archive_id must not be empty."
        )
    return archive_id


def _blocked_result(
    archive_root: Path | str,
    *,
    host: str,
    scope: str,
    diagnostic_code: str,
    blocker: str,
) -> dict[str, Any]:
    archive_id: str | None = None
    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = _read_valid_archive_id(root)
    except EXPECTED_ARCHIVE_IDENTITY_ERRORS:
        pass
    return {
        "ok": False,
        "ready": False,
        "dry_run": True,
        "schema": READINESS_SCHEMA,
        "lifecycle_action": "runtime_guidance_readiness",
        "status": "blocked",
        "archive_id": archive_id,
        "target": _safe_target(host, scope),
        "runtime_skill": {
            "status": "not_checked",
            "checked": False,
        },
        "agents_routing": {
            "status": "not_checked",
            "checked": False,
            "path_hint": "repo/AGENTS.md",
            "body_echoed": False,
        },
        "host_guidance_consumption": {
            "status": "not_proven",
            "claim_supported": False,
        },
        "diagnostic_codes": [diagnostic_code],
        "next_safe_commands": [],
        "closed_actions": {
            "files_written": False,
            "agents_file_modified": False,
            "runtime_skill_installation_changed": False,
            "provider_api_called": False,
            "network_checked": False,
            "secrets_read": False,
        },
        "privacy": {
            "local_paths_redacted": True,
            "agents_body_exposed": False,
            "secret_values_exposed": False,
        },
        "blockers": [blocker],
        "warnings": [],
    }


def blocked_runtime_guidance_result(
    archive_root: Path | str,
    *,
    host: str,
    scope: str,
    diagnostic_code: str,
    blocker: str,
) -> dict[str, Any]:
    """Build one content-free CLI/service failure result."""

    return _blocked_result(
        archive_root,
        host=host,
        scope=scope,
        diagnostic_code=diagnostic_code,
        blocker=blocker,
    )


def _safe_runtime_skill_projection(
    skill_result: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any], bool]:
    raw_target = (
        skill_result.get("target")
        if isinstance(skill_result.get("target"), dict)
        else {}
    )
    raw_installation = (
        skill_result.get("installation")
        if isinstance(skill_result.get("installation"), dict)
        else {}
    )
    raw_state = skill_result.get("status")
    state = (
        raw_state
        if isinstance(raw_state, str) and raw_state in SAFE_SKILL_STATES
        else "managed_invalid"
    )
    raw_version = raw_installation.get("installed_version")
    installed_version = archive_services.stable_version_value(
        raw_version if isinstance(raw_version, str) else None
    )
    version_invalid = bool(
        raw_version is not None and installed_version is None
    )
    raw_source_sha256 = raw_installation.get(
        "installed_source_package_sha256"
    )
    installed_source_sha256 = (
        raw_source_sha256
        if isinstance(raw_source_sha256, str)
        and runtime_skill_install.SHA256_RE.fullmatch(raw_source_sha256)
        is not None
        else None
    )
    raw_manifest_sha256 = raw_installation.get("install_manifest_sha256")
    manifest_sha256 = (
        raw_manifest_sha256
        if isinstance(raw_manifest_sha256, str)
        and runtime_skill_install.SHA256_RE.fullmatch(raw_manifest_sha256)
        is not None
        else None
    )
    if version_invalid:
        state = "managed_invalid"
    target = {
        "host": "codex",
        "scope": "repo",
        "skill_name": runtime_skill_install.SKILL_NAME,
        "path": None,
        "path_redacted": True,
        "path_hint": "repo/.agents/skills/wom-archive",
        "target_path_sha256": (
            raw_target.get("target_path_sha256")
            if isinstance(raw_target.get("target_path_sha256"), str)
            and runtime_skill_install.SHA256_RE.fullmatch(
                raw_target["target_path_sha256"]
            )
            is not None
            else None
        ),
    }
    installation = {
        "state": state,
        "managed": state.startswith("managed_"),
        "installed_version": installed_version,
        "installed_version_status": (
            "invalid_or_untrusted"
            if version_invalid
            or raw_installation.get("installed_version_status")
            == "invalid_or_untrusted"
            else "valid"
            if installed_version is not None
            else "not_available"
        ),
        "installed_source_package_sha256": installed_source_sha256,
        "install_manifest_sha256": manifest_sha256,
        "file_bodies_exposed": False,
        "untrusted_manifest_values_exposed": False,
    }
    return state, target, installation, version_invalid


def _inspect_agents_routing(repo_root: Path) -> dict[str, Any]:
    agents_path = repo_root / "AGENTS.md"
    kind = archive_services.wom_kit_real_path_kind(repo_root, agents_path)
    if kind == "missing":
        return {
            "status": "absent",
            "checked": True,
            "path_hint": "repo/AGENTS.md",
            "required_routes": [name for name, _marker in AGENTS_ROUTING_MARKERS],
            "present_routes": [],
            "missing_routes": [name for name, _marker in AGENTS_ROUTING_MARKERS],
            "body_echoed": False,
        }
    if kind != "file":
        return {
            "status": "unsafe",
            "checked": True,
            "path_hint": "repo/AGENTS.md",
            "required_routes": [name for name, _marker in AGENTS_ROUTING_MARKERS],
            "present_routes": [],
            "missing_routes": [],
            "body_echoed": False,
        }

    text = archive_services.wom_kit_read_bounded_real_text(
        repo_root,
        agents_path,
        max_bytes=MAX_AGENTS_BYTES,
    )
    if text is None:
        return {
            "status": "unreadable",
            "checked": True,
            "path_hint": "repo/AGENTS.md",
            "required_routes": [name for name, _marker in AGENTS_ROUTING_MARKERS],
            "present_routes": [],
            "missing_routes": [],
            "body_echoed": False,
        }

    normalized = " ".join(text.casefold().split())
    present = [
        name
        for name, marker in AGENTS_ROUTING_MARKERS
        if marker.casefold() in normalized
    ]
    missing = [
        name
        for name, _marker in AGENTS_ROUTING_MARKERS
        if name not in present
    ]
    return {
        "status": "current" if not missing else "incomplete",
        "checked": True,
        "path_hint": "repo/AGENTS.md",
        "required_routes": [name for name, _marker in AGENTS_ROUTING_MARKERS],
        "present_routes": present,
        "missing_routes": missing,
        "body_echoed": False,
    }


def runtime_guidance_readiness(
    archive_root: Path | str,
    *,
    host: str,
    scope: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Inspect one explicit host/repo target without modifying host or archive files."""

    normalized_host = host.strip().lower() if isinstance(host, str) else ""
    normalized_scope = scope.strip().lower() if isinstance(scope, str) else ""
    if normalized_host != SUPPORTED_HOST or normalized_scope != SUPPORTED_SCOPE:
        return _blocked_result(
            archive_root,
            host=host,
            scope=scope,
            diagnostic_code="unsupported_host_scope",
            blocker=(
                "runtime-guidance-readiness v0.1 supports only the explicit "
                "--host codex --scope repo inspection contract."
            ),
        )
    if repo_root is None:
        return _blocked_result(
            archive_root,
            host=host,
            scope=scope,
            diagnostic_code="repo_root_required",
            blocker=(
                "runtime-guidance-readiness with --host codex --scope repo "
                "requires an explicit --repo-root."
            ),
        )

    try:
        root = archive_services.require_existing_archive_root(archive_root)
        archive_id = _read_valid_archive_id(root)
    except EXPECTED_ARCHIVE_IDENTITY_ERRORS:
        return _blocked_result(
            archive_root,
            host=host,
            scope=scope,
            diagnostic_code="invalid_archive",
            blocker=(
                "Runtime guidance readiness requires a readable WOM archive "
                "with a valid archive identity."
            ),
        )

    try:
        resolved_repo = Path(os.path.abspath(os.fspath(repo_root.expanduser())))
        runtime_skill_install.resolve_target_location(
            host=normalized_host,
            scope=normalized_scope,
            repo_root=resolved_repo,
        )
    except (archive_services.ArchiveServiceError, OSError, ValueError):
        return _blocked_result(
            archive_root,
            host=host,
            scope=scope,
            diagnostic_code="unsafe_or_unreadable_target",
            blocker=(
                "Runtime guidance readiness could not resolve a safe archive "
                "and explicit host repository target."
            ),
        )

    skill_result = runtime_skill_install.runtime_skill_status(
        host=normalized_host,
        scope=normalized_scope,
        repo_root=resolved_repo,
        redact_local_paths=True,
        package_version=__version__,
    )
    agents_routing = _inspect_agents_routing(resolved_repo)
    (
        skill_status,
        skill_target,
        skill_installation,
        installed_version_invalid,
    ) = _safe_runtime_skill_projection(skill_result)
    diagnostic_codes: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    if installed_version_invalid or (
        skill_installation["installed_version_status"]
        == "invalid_or_untrusted"
    ):
        diagnostic_codes.append("runtime_skill_manifest_version_invalid")
        blockers.append(
            "Runtime Skill ownership manifest version is invalid or untrusted."
        )
    elif not skill_result.get("ok"):
        diagnostic_codes.append("runtime_skill_inspection_blocked")
        blockers.append("Runtime Skill state could not be inspected safely.")
    elif skill_status == "absent":
        diagnostic_codes.append("runtime_skill_absent")
    elif skill_status == "managed_outdated":
        diagnostic_codes.append("runtime_skill_outdated")
    elif skill_status != "managed_current":
        diagnostic_codes.append("runtime_skill_unmanaged_or_drifted")
        blockers.append("Runtime Skill state is not safely managed by this WOM-kit contract.")

    agents_status = str(agents_routing.get("status") or "unreadable")
    if agents_status in {"absent", "incomplete"}:
        diagnostic_codes.append("legacy_agents_routing_absent")
    elif agents_status in {"unsafe", "unreadable"}:
        diagnostic_codes.append(f"agents_routing_{agents_status}")
        blockers.append("Repository AGENTS.md routing could not be inspected safely.")

    ready = (
        not blockers
        and skill_status == "managed_current"
        and agents_status == "current"
    )
    status = "ready" if ready else "blocked" if blockers else "attention_required"
    next_safe_commands: list[str] = []
    if skill_status in {"absent", "managed_outdated"}:
        next_safe_commands.append(
            "archive runtime-skill-install --host codex --scope repo "
            "--repo-root <repo-root> --dry-run --format json"
        )
    if agents_status in {"absent", "incomplete"}:
        warnings.append(
            "Repository AGENTS.md needs human review against current WOM routing; "
            "this command does not create or modify it."
        )

    return {
        "ok": not blockers,
        "ready": ready,
        "dry_run": True,
        "schema": READINESS_SCHEMA,
        "lifecycle_action": "runtime_guidance_readiness",
        "status": status,
        "archive_id": archive_id,
        "target": {
            "host": normalized_host,
            "scope": normalized_scope,
        },
        "runtime_skill": {
            "status": skill_status,
            "checked": True,
            "target": skill_target,
            "installation": skill_installation,
        },
        "agents_routing": agents_routing,
        "host_guidance_consumption": {
            "status": "not_proven",
            "claim_supported": False,
        },
        "diagnostic_codes": diagnostic_codes,
        "next_safe_commands": next_safe_commands,
        "closed_actions": {
            "files_written": False,
            "agents_file_modified": False,
            "runtime_skill_installation_changed": False,
            "provider_api_called": False,
            "network_checked": False,
            "secrets_read": False,
        },
        "privacy": {
            "local_paths_redacted": True,
            "agents_body_exposed": False,
            "secret_values_exposed": False,
            "untrusted_manifest_values_exposed": False,
        },
        "blockers": blockers,
        "warnings": warnings,
    }
