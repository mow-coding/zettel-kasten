"""Read-only host guidance readiness inspection for WOM archives."""

from __future__ import annotations

import os
from pathlib import Path
import re
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
AGENTS_ROUTING_BLOCK_BEGIN = (
    "<!-- WOM-RUNTIME-GUIDANCE-ROUTING v0.3.293 BEGIN -->"
)
AGENTS_ROUTING_BLOCK_END = (
    "<!-- WOM-RUNTIME-GUIDANCE-ROUTING v0.3.293 END -->"
)
AGENTS_ROUTING_AUTHORITY_LINE = (
    "This is the current authoritative WOM runtime guidance routing contract. "
    "Follow every directive in this block."
)
AGENTS_ROUTING_BLOCK = "\n".join(
    (
        AGENTS_ROUTING_BLOCK_BEGIN,
        AGENTS_ROUTING_AUTHORITY_LINE,
        (
            "Run `archive ai-start-here <archive-root> --dry-run --progress "
            "--format json` before choosing an archive action."
        ),
        "Read and follow the returned `action_routing`.",
        "Read `inbox_attention` and surface every unpublished-draft count before broad work.",
        (
            "Use `archive search <archive-root> <query> --count-total "
            "--format json` for official WOM search."
        ),
        "Raw grep and raw SQL are not authoritative WOM search results.",
        (
            "For operator feedback, run `archive operator-feedback-plan "
            "<archive-root> --dry-run --format json`, inspect `archive "
            "operator-feedback-ledger <archive-root> --dry-run --format json`, "
            "compose and approve the six-section body through "
            "`operator-feedback-compose`, verify it with "
            "`operator-feedback-body-check --dry-run`, "
            "require human review, preview `archive operator-feedback-record "
            "<archive-root> ... --feedback-ref feedback-body-sha256:<digest> "
            "--intent create|update --dry-run --format "
            "json`, and only then use the reviewed `--approve` replay; create "
            "never overwrites, while update also requires the fresh "
            "`--expected-record-sha256`."
        ),
        AGENTS_ROUTING_BLOCK_END,
    )
)
AGENTS_ROUTING_REQUIRED_ROUTES = (
    "ai_start_here",
    "action_routing",
    "unpublished_draft_attention",
    "official_archive_search",
    "raw_search_not_authoritative",
    "operator_feedback_review_route",
)
AGENTS_ROUTING_MARKERS = (
    (
        "ai_start_here",
        "archive ai-start-here <archive-root> --dry-run --progress --format json",
    ),
    ("action_routing", "action_routing"),
    ("unpublished_draft_attention", "inbox_attention"),
    (
        "official_archive_search",
        "archive search <archive-root> <query> --count-total --format json",
    ),
    (
        "raw_search_not_authoritative",
        "raw grep and raw sql are not authoritative",
    ),
    (
        "operator_feedback_review_route",
        "operator-feedback-plan",
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
    *,
    host: str,
    scope: str,
    diagnostic_code: str,
    blocker: str,
    archive_id: str | None = None,
    inspection_reads: dict[str, bool] | None = None,
    observation_status: str = "observed",
) -> dict[str, Any]:
    reads = {
        "archive_configuration_read": False,
        "agents_body_read": False,
        "credential_or_secret_store_read": False,
    }
    if inspection_reads is not None:
        reads.update(
            {
                key: bool(inspection_reads.get(key))
                for key in reads
            }
        )
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
        "inspection_reads": reads,
        "observation_status": observation_status,
        "closed_actions": {
            "files_written": False,
            "agents_file_modified": False,
            "runtime_skill_installation_changed": False,
            "provider_api_called": False,
            "network_checked": False,
        },
        "privacy": {
            "local_paths_redacted": True,
            "archive_identity_exposed": archive_id is not None,
            "agents_body_exposed": False,
            "secret_values_exposed": False,
        },
        "blockers": [blocker],
        "warnings": [],
    }


def blocked_runtime_guidance_result(
    *,
    host: str,
    scope: str,
    diagnostic_code: str,
    blocker: str,
    inspection_reads: dict[str, bool] | None = None,
    observation_status: str = "conservative_after_failure",
) -> dict[str, Any]:
    """Build one pure content-free CLI/service failure result without I/O."""

    return _blocked_result(
        host=host,
        scope=scope,
        diagnostic_code=diagnostic_code,
        blocker=blocker,
        inspection_reads=(
            inspection_reads
            if inspection_reads is not None
            else {
                "archive_configuration_read": True,
                "agents_body_read": True,
                "credential_or_secret_store_read": False,
            }
        ),
        observation_status=observation_status,
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


def _agents_routing_result(
    status: str,
    *,
    checked: bool,
    body_read: bool,
    legacy_present: list[str] | None = None,
) -> tuple[dict[str, Any], bool]:
    current = status == "current"
    legacy_routes = legacy_present or []
    return (
        {
            "status": status,
            "checked": checked,
            "path_hint": "repo/AGENTS.md",
            "contract_version": "v0.3.293",
            "required_routes": list(AGENTS_ROUTING_REQUIRED_ROUTES),
            "present_routes": (
                list(AGENTS_ROUTING_REQUIRED_ROUTES) if current else []
            ),
            "missing_routes": (
                [] if current else list(AGENTS_ROUTING_REQUIRED_ROUTES)
            ),
            "canonical_block_present": current,
            "legacy_anchors_present_unverified": (
                bool(legacy_routes) and not current
            ),
            "legacy_present_routes": (
                [] if current else legacy_routes
            ),
            "body_echoed": False,
        },
        body_read,
    )


def _inside_markdown_fence(text: str, block_start: int) -> bool:
    """Return whether an exact routing block starts inside a Markdown fence."""

    opened: tuple[str, int] | None = None
    for line in text[:block_start].splitlines():
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if match is None:
            continue
        marker = match.group(1)
        trailing = match.group(2)
        if opened is None:
            opened = (marker[0], len(marker))
            continue
        if (
            marker[0] == opened[0]
            and len(marker) >= opened[1]
            and not trailing.strip()
        ):
            opened = None
    return opened is not None


def _canonical_agents_routing_block_present(text: str) -> bool:
    """Recognize exactly one positive, non-quoted canonical contract block."""

    normalized = text.replace("\r\n", "\n")
    if (
        normalized.count(AGENTS_ROUTING_BLOCK_BEGIN) != 1
        or normalized.count(AGENTS_ROUTING_BLOCK_END) != 1
    ):
        return False
    start = normalized.find(AGENTS_ROUTING_BLOCK_BEGIN)
    end_start = normalized.find(AGENTS_ROUTING_BLOCK_END)
    if start < 0 or end_start < start:
        return False
    end = end_start + len(AGENTS_ROUTING_BLOCK_END)
    if (start and normalized[start - 1] != "\n") or (
        end < len(normalized) and normalized[end] != "\n"
    ):
        return False
    if normalized[start:end] != AGENTS_ROUTING_BLOCK:
        return False
    return not _inside_markdown_fence(normalized, start)


def _inspect_agents_routing(
    repo_root: Path,
) -> tuple[dict[str, Any], bool]:
    agents_path = repo_root / "AGENTS.md"
    kind = archive_services.wom_kit_real_path_kind(repo_root, agents_path)
    if kind == "missing":
        return _agents_routing_result(
            "absent",
            checked=True,
            body_read=False,
        )
    if kind != "file":
        return _agents_routing_result(
            "unsafe",
            checked=True,
            body_read=False,
        )

    text = archive_services.wom_kit_read_bounded_real_text(
        repo_root,
        agents_path,
        max_bytes=MAX_AGENTS_BYTES,
    )
    if text is None:
        return _agents_routing_result(
            "unreadable",
            checked=True,
            body_read=True,
        )

    normalized = " ".join(text.casefold().split())
    legacy_present = [
        name
        for name, marker in AGENTS_ROUTING_MARKERS
        if marker.casefold() in normalized
    ]
    return _agents_routing_result(
        (
            "current"
            if _canonical_agents_routing_block_present(text)
            else "incomplete"
        ),
        checked=True,
        body_read=True,
        legacy_present=legacy_present,
    )


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
            host=host,
            scope=scope,
            diagnostic_code="repo_root_required",
            blocker=(
                "runtime-guidance-readiness with --host codex --scope repo "
                "requires an explicit --repo-root."
            ),
        )

    inspection_reads = {
        "archive_configuration_read": False,
        "agents_body_read": False,
        "credential_or_secret_store_read": False,
    }
    try:
        root = archive_services.require_existing_archive_root(archive_root)
    except EXPECTED_ARCHIVE_IDENTITY_ERRORS:
        return _blocked_result(
            host=host,
            scope=scope,
            diagnostic_code="invalid_archive",
            blocker=(
                "Runtime guidance readiness requires a readable WOM archive "
                "with a valid archive identity."
            ),
            inspection_reads=inspection_reads,
        )

    inspection_reads["archive_configuration_read"] = True
    try:
        archive_id = _read_valid_archive_id(root)
    except EXPECTED_ARCHIVE_IDENTITY_ERRORS:
        return _blocked_result(
            host=host,
            scope=scope,
            diagnostic_code="invalid_archive",
            blocker=(
                "Runtime guidance readiness requires a readable WOM archive "
                "with a valid archive identity."
            ),
            inspection_reads=inspection_reads,
        )
    projected_archive_id = archive_services.safe_projection_scalar(archive_id)
    if projected_archive_id != archive_id:
        return _blocked_result(
            host=host,
            scope=scope,
            diagnostic_code="archive_identity_unshareable",
            blocker=(
                "Runtime guidance readiness requires an archive identity that "
                "can be projected exactly without exposing private or unsafe "
                "content."
            ),
            inspection_reads=inspection_reads,
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
            host=host,
            scope=scope,
            diagnostic_code="unsafe_or_unreadable_target",
            blocker=(
                "Runtime guidance readiness could not resolve a safe archive "
                "and explicit host repository target."
            ),
            archive_id=projected_archive_id,
            inspection_reads=inspection_reads,
        )

    skill_result = runtime_skill_install.runtime_skill_status(
        host=normalized_host,
        scope=normalized_scope,
        repo_root=resolved_repo,
        redact_local_paths=True,
        package_version=__version__,
    )
    agents_routing, agents_body_read = _inspect_agents_routing(resolved_repo)
    inspection_reads["agents_body_read"] = agents_body_read
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
    if agents_status == "absent":
        diagnostic_codes.append("agents_routing_contract_absent")
    elif agents_status == "incomplete":
        diagnostic_codes.append("agents_routing_contract_not_current")
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
        "archive_id": projected_archive_id,
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
        "inspection_reads": inspection_reads,
        "observation_status": "observed",
        "closed_actions": {
            "files_written": False,
            "agents_file_modified": False,
            "runtime_skill_installation_changed": False,
            "provider_api_called": False,
            "network_checked": False,
        },
        "privacy": {
            "local_paths_redacted": True,
            "archive_identity_exposed": True,
            "agents_body_exposed": False,
            "secret_values_exposed": False,
            "untrusted_manifest_values_exposed": False,
        },
        "blockers": blockers,
        "warnings": warnings,
    }
