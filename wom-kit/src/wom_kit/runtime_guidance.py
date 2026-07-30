"""Read-only host guidance readiness inspection for WOM archives."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import __version__
from . import archive_services
from . import runtime_skill_install


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


def _safe_target(host: str, scope: str) -> dict[str, str]:
    normalized_host = host.strip().lower() if isinstance(host, str) else ""
    normalized_scope = scope.strip().lower() if isinstance(scope, str) else ""
    return {
        "host": normalized_host if normalized_host in {"codex", "custom"} else "unsupported",
        "scope": normalized_scope
        if normalized_scope in {"user", "repo", "custom"}
        else "unsupported",
    }


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
        archive_id = archive_services.read_archive_id(root)
    except (archive_services.ArchiveServiceError, OSError, ValueError):
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
    skill_status = str(skill_result.get("status") or "blocked")
    diagnostic_codes: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    if not skill_result.get("ok"):
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
        "archive_id": archive_services.read_archive_id(root),
        "target": {
            "host": normalized_host,
            "scope": normalized_scope,
        },
        "runtime_skill": {
            "status": skill_status,
            "checked": True,
            "target": skill_result.get("target"),
            "installation": skill_result.get("installation"),
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
        },
        "blockers": blockers,
        "warnings": warnings,
    }
