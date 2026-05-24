"""Shared archive operations used by CLI and MCP tools."""

from __future__ import annotations

import json
import hashlib
import fnmatch
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .paths import (
    ArchivePathError,
    archive_relative_path,
    contains_forbidden_location_reference,
    is_path_within_root,
    normalize_archive_relative_path,
    resolve_archive_relative_path,
)
from .schema_validator import validate_schema

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only when dependency is absent.
    yaml = None


FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.DOTALL)
VALID_ZETTEL_FOLDERS = ("zettels/", "inbox/")
INDEX_RELATIVE_PATH = "db/archive-index.sqlite"
KIT_ROOT = Path(__file__).resolve().parents[2]
WORKPACK_MODES = {"reference", "copy", "mount", "derive", "handover", "return"}
ARCHIVE_SCOPES = {"personal", "relationship", "family", "child", "project", "company", "business_unit"}
OWNER_KINDS = {
    "person",
    "relationship",
    "family",
    "household",
    "child",
    "project",
    "company",
    "business_unit",
    "team",
    "role",
    "client",
    "server",
}
SENSITIVE_SHARE_CATEGORIES = {"medical", "psychological", "journal", "relationship-private"}
SENSITIVE_CATEGORY_ALIASES = {"diary": "journal", "therapy": "psychological", "mental-health": "psychological"}
EXTERNAL_IMPORT_SOURCES = {"notion", "google_drive"}
EXTERNAL_IMPORT_EXTENSIONS = {".md", ".markdown", ".txt"}
SOURCE_TYPES = {"local_folder", "external_ssd", "notion_export", "google_drive_export", "object_manifest"}
PROFILE_REGISTRY_VERSION = "wom-profile-registry/v0.1"
PROFILE_REGISTRY_ARCHIVE_TYPES = {"personal", "company", "family", "project", "relationship", "child", "business_unit"}
PROFILE_RESOLUTION_STATES = {"resolved", "ambiguous", "not_found", "token_missing"}
PROFILE_NEXT_ACTIONS = {
    "run_runtime_context",
    "ask_user_to_choose_profile",
    "register_profile_token",
    "suggest_delegate_flow",
}
PROFILE_ALLOWED_TOKEN_KEYS = {"state", "token_ref"}
PROFILE_RAW_TOKEN_KEYS = {
    "access_token",
    "api_key",
    "client_secret",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
    "value",
}
PROFILE_IGNORABLE_QUERY_CHARS = dict.fromkeys(map(ord, "\ufeff\u200b\u200c\u200d\u2060"), None)
RUNTIME_CONTEXT_ARCHIVE_TYPES = {"personal", "company", "family", "project", "relationship", "child", "business_unit"}
RUNTIME_CONTEXT_SAFE_ACTIONS = [
    "create draft in inbox",
    "run mint dry-run",
    "run check-safe-html dry-run",
    "run doctor",
    "mint only through CLI approve path",
]
SOURCE_MAPS_DIR = "source-maps"
SOURCE_SCAN_RECEIPTS_DIR = "receipts/sources"
RESTORE_DRILL_RECEIPTS_DIR = "receipts/recovery"
MINT_RECEIPTS_DIR = "receipts/mint"
MINT_DRAFT_SNAPSHOTS_DIR = "receipts/mint/drafts"
DELEGATE_RECEIPTS_DIR = "receipts/delegate"
ATTESTATION_RECEIPTS_DIR = "receipts/attest"
ANCHOR_METADATA_DIR = "anchors"
DELEGATE_TARGET_POLICY_COUNTERPARTY_BOUND = "counterparty_bound"
DELEGATE_TARGET_POLICY_CLAIMABLE_ONCE = "claimable_once"
DELEGATE_TARGET_POLICIES = {
    DELEGATE_TARGET_POLICY_COUNTERPARTY_BOUND,
    DELEGATE_TARGET_POLICY_CLAIMABLE_ONCE,
}
DELEGATE_DEFAULT_TARGET_POLICY = DELEGATE_TARGET_POLICY_COUNTERPARTY_BOUND
MINT_AUTHORITY_MODE = "basic"
MINT_CHECKLIST_VERSION = "zet-mint/v0.2"
SOURCE_SCAN_MODE = "metadata_only"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
OBJECT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
DRAFT_CREATION_MODES = {"human_written", "ai_assisted", "ai_generated", "imported", "derived"}
SOURCE_INTAKE_ROLES = {"primary_source", "context", "attachment", "derived_context"}
SOURCE_INTAKE_DEFAULT_ROLE = "primary_source"
SOURCE_INTAKE_RUNTIMES = {"codex", "claude_code", "other"}
SOURCE_INTAKE_SAFE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._+-]{0,199}$")
SOURCE_INTAKE_ARTIFACT_KIND_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
SOURCE_INTAKE_OBJECT_STORAGE_PROVIDERS = {
    "object_storage",
    "cloudflare_r2",
    "cloudflare-r2",
    "backblaze_b2",
    "backblaze-b2",
    "aws_s3",
    "aws-s3",
    "google_cloud_storage",
    "google-cloud-storage",
    "generic_s3",
    "generic-s3",
}
DRAFT_SECRET_VALUE_RE = re.compile(
    r"(?i)(?:api[_-]?key|secret|token|password|credential|aws_secret_access_key)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=:-]{12,}"
    r"|-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|\bAKIA[0-9A-Z]{16}\b"
    r"|\bghp_[A-Za-z0-9_]{20,}\b"
)
SOURCE_ROOTS_LOCAL_PROFILE = "profiles/local/source-roots.local.yml"
RESTORE_DRILL_EXCLUDED_PATHS = [
    ".git/",
    ".env",
    ".env.*",
    "db/archive-index.sqlite",
    "profiles/local/",
    "keyrings/local/",
    ".archive-local/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
]
PROVIDER_TYPES = {
    "github",
    "object_storage",
    "cloudflare_r2",
    "backblaze_b2",
    "neon",
    "external_ssd",
    "rclone",
    "restic",
    "keepassxc",
}
PROVIDER_REFERENCE_URLS = {
    "github": "https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization",
    "object_storage": "object-storage-provider-manual",
    "cloudflare_r2": "https://developers.cloudflare.com/r2/api/tokens/",
    "backblaze_b2": "https://www.backblaze.com/docs/cloud-storage-application-key-capabilities",
    "neon": "https://neon.com/docs/get-started-with-neon/connect-neon",
    "external_ssd": "local-operations-manual",
    "rclone": "https://rclone.org/docs/",
    "restic": "https://restic.readthedocs.io/",
    "keepassxc": "https://keepassxc.org/docs/",
}
GITHUB_REPOSITORY_SETUP_RECEIPTS_DIR = "receipts/providers"
GITHUB_REPOSITORY_DEFAULT_VISIBILITY = "private"
GITHUB_REPOSITORY_DEFAULT_REMOTE_PROTOCOL = "ssh"
GITHUB_REPOSITORY_NAME_PREFIX = "zettel-kasten-"
GITHUB_REPOSITORY_ALLOWED_VISIBILITIES = {"private"}
GITHUB_REPOSITORY_REMOTE_PROTOCOLS = {"ssh", "https"}
GITHUB_REPOSITORY_NAME_RE = re.compile(r"^[A-Za-z0-9-]{1,80}$")
GITHUB_PROFILE_SLUG_RE = re.compile(r"^[A-Za-z0-9-]+$")
GITHUB_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
GITHUB_SECRET_LIKE_RE = re.compile(
    r"(?i)\b(?:ghp_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9]{20,}|"
    r"token|secret|password|oauth|cookie|credential)\b"
)
OBJECT_STORAGE_SETUP_RECEIPTS_DIR = "receipts/providers"
OBJECT_STORAGE_ALLOWED_PROVIDERS = {
    "cloudflare-r2",
    "aws-s3",
    "backblaze-b2",
    "google-cloud-storage",
    "generic-s3",
}
OBJECT_STORAGE_DEFAULT_VISIBILITY = "private"
OBJECT_STORAGE_ALLOWED_VISIBILITIES = {"private"}
OBJECT_STORAGE_BUCKET_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$")
OBJECT_STORAGE_REGION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$")
OBJECT_STORAGE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,119}$")
OBJECT_STORAGE_PROVIDER_TOKEN_ENVS = {
    "cloudflare-r2": "R2_TOKEN",
    "aws-s3": "AWS_OBJECT_STORAGE_TOKEN",
    "backblaze-b2": "B2_OBJECT_STORAGE_TOKEN",
    "google-cloud-storage": "GCS_OBJECT_STORAGE_TOKEN",
    "generic-s3": "OBJECT_STORAGE_TOKEN",
}
ONBOARDING_PROVIDER_PROFILES = {
    "local_only": {
        "description": "Local archive plus physical/local backup and external secret vault guidance.",
        "enabled_providers": ["external_ssd", "keepassxc"],
    },
    "object_storage_planned": {
        "description": "Plan replaceable object storage and backup tooling without enabling GitHub or Neon by default.",
        "enabled_providers": ["cloudflare_r2", "backblaze_b2", "external_ssd", "rclone", "restic", "keepassxc"],
    },
    "full_provider_plan": {
        "description": "Plan GitHub, object storage, optional Neon coordination, backup tooling, and keyring references.",
        "enabled_providers": [
            "github",
            "cloudflare_r2",
            "backblaze_b2",
            "neon",
            "external_ssd",
            "rclone",
            "restic",
            "keepassxc",
        ],
    },
}
PILOT_SOURCE_PLANS = {
    "personal_life": [
        {
            "source_id": "local:personal-documents",
            "source_type": "local_folder",
            "description": "Personal documents folder, selected explicitly by the archive owner.",
            "root_ref": "ARCHIVE_SOURCE_PERSONAL_DOCUMENTS_ROOT",
        },
        {
            "source_id": "ssd:personal-originals",
            "source_type": "external_ssd",
            "description": "Personal external SSD originals and backups.",
            "root_ref": "ARCHIVE_SOURCE_PERSONAL_SSD_ROOT",
        },
        {
            "source_id": "notion:personal-export",
            "source_type": "notion_export",
            "description": "Personal Notion export folder.",
            "root_ref": "ARCHIVE_SOURCE_NOTION_PERSONAL_EXPORT_ROOT",
        },
        {
            "source_id": "google_drive:personal-export",
            "source_type": "google_drive_export",
            "description": "Personal Google Drive export or manifest folder.",
            "root_ref": "ARCHIVE_SOURCE_GOOGLE_DRIVE_PERSONAL_EXPORT_ROOT",
        },
        {
            "source_id": "object:personal-media-manifest",
            "source_type": "object_manifest",
            "description": "Versioned manifest for large personal media stored elsewhere.",
            "root_ref": "archive:objects/manifests/files.jsonl",
        },
    ],
    "team": [
        {
            "source_id": "local:team-workspace",
            "source_type": "local_folder",
            "description": "Team working folder selected explicitly by the team operator.",
            "root_ref": "ARCHIVE_SOURCE_TEAM_WORKSPACE_ROOT",
        },
        {
            "source_id": "notion:team-export",
            "source_type": "notion_export",
            "description": "Team Notion export folder.",
            "root_ref": "ARCHIVE_SOURCE_NOTION_TEAM_EXPORT_ROOT",
        },
        {
            "source_id": "google_drive:team-export",
            "source_type": "google_drive_export",
            "description": "Team Google Drive export or manifest folder.",
            "root_ref": "ARCHIVE_SOURCE_GOOGLE_DRIVE_TEAM_EXPORT_ROOT",
        },
        {
            "source_id": "object:team-media-manifest",
            "source_type": "object_manifest",
            "description": "Versioned manifest for team large objects stored elsewhere.",
            "root_ref": "archive:objects/manifests/files.jsonl",
        },
    ],
}
PROMOTION_CHECKLIST_PASS_VALUES = {"pass", "passed", "true", "yes", "done", "complete", "completed"}
PROMOTION_CHECKLIST_FAIL_VALUES = {"fail", "failed", "false", "no", "blocked", "missing"}
REQUIRED_ZETTEL_FIELDS = [
    "id",
    "title",
    "created_at",
    "updated_at",
    "archive_id",
    "status",
    "facets",
    "assets",
    "edges",
    "provenance",
    "visibility",
]


class ArchiveServiceError(Exception):
    pass


def require_yaml() -> None:
    if yaml is None:
        raise ArchiveServiceError("PyYAML is required. Install it with: python -m pip install PyYAML")


def load_yaml(text: str) -> Any:
    require_yaml()
    return yaml.safe_load(text)  # type: ignore[union-attr]


def dump_yaml(data: Any) -> str:
    require_yaml()
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)  # type: ignore[union-attr]


def parse_frontmatter(text: str) -> str | None:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    return match.group(1)


def split_zettel_text(text: str) -> tuple[dict[str, Any], str]:
    frontmatter_text = parse_frontmatter(text)
    frontmatter = load_yaml(frontmatter_text) if frontmatter_text else {}
    if not isinstance(frontmatter, dict):
        frontmatter = {}
    body = text[FRONTMATTER_RE.match(text).end() :].lstrip() if frontmatter_text and FRONTMATTER_RE.match(text) else text
    return frontmatter, body


def require_existing_archive_root(archive_root: Path | str) -> Path:
    root = Path(archive_root).resolve()
    if not root.is_dir():
        raise ArchiveServiceError(f"Archive root does not exist or is not a directory: {root}")
    return root


def archive_internal_path(archive_root: Path, relative_path: str) -> Path:
    try:
        return resolve_archive_relative_path(archive_root, relative_path)
    except ArchivePathError as exc:
        raise ArchiveServiceError(f"Archive path is unsafe: {relative_path} ({exc})") from exc


def read_archive_text(archive_root: Path, relative_path: str) -> str:
    path = archive_internal_path(archive_root, relative_path)
    if not path.is_file():
        raise ArchiveServiceError(f"Archive file is missing: {relative_path}")
    return path.read_text(encoding="utf-8")


def list_zettels(archive_root: Path | str, status: str = "canonical", limit: int = 100) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    if status not in {"all", "draft", "canonical"}:
        raise ArchiveServiceError("status must be one of: all, draft, canonical")
    limit = max(1, min(int(limit), 500))

    if status == "all":
        folders = [("zettels", "canonical"), ("inbox", "draft")]
    elif status == "draft":
        folders = [("inbox", "draft")]
    else:
        folders = [("zettels", "canonical")]

    zettels: list[dict[str, Any]] = []
    for folder, expected_status in folders:
        folder_root = root / folder
        if not folder_root.is_dir():
            continue
        for path in safe_archive_glob(folder_root, "*.md", root, recursive=True):
            zettels.append(zettel_summary(path, root, expected_status))
            if len(zettels) >= limit:
                break
        if len(zettels) >= limit:
            break

    return {"zettels": zettels, "count": len(zettels)}


def zettel_summary(path: Path, archive_root: Path, expected_status: str) -> dict[str, Any]:
    frontmatter, _body = split_zettel_text(path.read_text(encoding="utf-8"))
    frontmatter = json_safe(frontmatter)
    return {
        "path": archive_relative_path(path, archive_root),
        "id": frontmatter.get("id"),
        "title": frontmatter.get("title"),
        "status": frontmatter.get("status", expected_status),
        "kind": frontmatter.get("kind"),
        "created_at": frontmatter.get("created_at"),
        "updated_at": frontmatter.get("updated_at"),
        "facets": frontmatter.get("facets", {}),
        "visibility": frontmatter.get("visibility", {}),
    }


def read_zettel(
    archive_root: Path | str,
    *,
    zettel_id: str | None = None,
    relative_path: str | None = None,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    if not zettel_id and not relative_path:
        raise ArchiveServiceError("Provide zettel_id or path.")

    path = resolve_zettel_path(root, zettel_id=zettel_id, relative_path=relative_path)
    frontmatter, body = split_zettel_text(path.read_text(encoding="utf-8"))
    frontmatter = json_safe(frontmatter)
    return {
        "path": archive_relative_path(path, root),
        "frontmatter": frontmatter,
        "body": body,
    }


def resolve_zettel_path(archive_root: Path, zettel_id: str | None, relative_path: str | None) -> Path:
    if relative_path:
        try:
            candidate = resolve_archive_relative_path(archive_root, relative_path)
        except ArchivePathError as exc:
            raise ArchiveServiceError(f"Zettel path is unsafe: {exc}") from exc
        relative = archive_relative_path(candidate, archive_root)
        if not relative.startswith(VALID_ZETTEL_FOLDERS) or candidate.suffix.lower() != ".md":
            raise ArchiveServiceError("Zettel path must point to a Markdown file inside inbox/ or zettels/.")
        if not candidate.is_file():
            raise ArchiveServiceError(f"Zettel path not found: {relative_path}")
        return candidate

    assert zettel_id is not None
    for path in iter_zettel_paths(archive_root):
        frontmatter, _body = split_zettel_text(path.read_text(encoding="utf-8"))
        if frontmatter.get("id") == zettel_id:
            return path
    raise ArchiveServiceError(f"Zettel id not found: {zettel_id}")


def valid_draft_zettel_id(value: str) -> bool:
    return bool(value and re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]*$", value))


def normalize_draft_body(body: str) -> str:
    normalized = body.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.rstrip() + "\n"


def valid_iso_timestamp(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_optional_string_list(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            result.append(text)
    return result


def normalize_source_refs(items: list[dict[str, Any]], blockers: list[str]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            blockers.append(f"source_refs[{index}] must be an object.")
            continue
        ref_type = str(item.get("type") or "").strip()
        value = str(item.get("value") or "").strip()
        if not ref_type or not value:
            blockers.append(f"source_refs[{index}] requires type and value.")
            continue
        ref = {"type": ref_type, "value": value}
        role = str(item.get("role") or "").strip()
        if role:
            ref["role"] = role
        refs.append(ref)
    return refs


def normalize_local_ai_sessions(items: list[dict[str, Any]], blockers: list[str]) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if isinstance(item, str):
            item = {"session_ref": item}
        if not isinstance(item, dict):
            blockers.append(f"local_ai_sessions[{index}] must be an object or safe string ref.")
            continue
        session_ref = str(item.get("session_ref") or item.get("value") or "").strip()
        if not session_ref:
            blockers.append(f"local_ai_sessions[{index}] requires session_ref.")
            continue
        session: dict[str, Any] = {"session_ref": session_ref}
        for key in ["runtime", "profile_id", "archive_id", "authority_mode"]:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                session[key] = value.strip()
        sessions.append(session)
    return sessions


def validate_safe_draft_values(value: Any, blockers: list[str], field_path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            validate_safe_draft_values(child, blockers, f"{field_path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            validate_safe_draft_values(child, blockers, f"{field_path}[{index}]")
        return
    if value is None:
        return
    text = str(value)
    if contains_forbidden_location_reference(text):
        blockers.append(f"Unsafe local path or provider locator in {field_path}.")
    if DRAFT_SECRET_VALUE_RE.search(text):
        blockers.append(f"Secret-like value in {field_path}.")


def create_draft_zettel(
    archive_root: Path | str,
    *,
    title: str,
    body: str,
    archive_id: str | None = None,
    kind: str = "fleeting_capture",
    facets: dict[str, Any] | None = None,
    visibility: dict[str, Any] | None = None,
    created_by: str = "cli:archive",
    source: str = "cli_command",
    dry_run: bool = False,
    expected_archive_id: str | None = None,
    expected_type: str | None = None,
    profile_id: str | None = None,
    profile_operator_id: str | None = None,
    profile_authority_mode: str | None = None,
    creation_mode: str | None = None,
    assisted_by: list[str] | None = None,
    supervised_by: list[str] | None = None,
    derived_from: list[str] | None = None,
    source_refs: list[dict[str, Any]] | None = None,
    local_ai_sessions: list[dict[str, Any]] | None = None,
    draft_id: str | None = None,
    created_at: str | None = None,
    expected_body_sha256: str | None = None,
    draft_approved_by: str | None = None,
) -> dict[str, Any]:
    require_yaml()
    root = require_existing_archive_root(archive_root)
    archive_config = read_archive_config(root)
    if not title:
        raise ArchiveServiceError("title is required.")
    if body is None:
        body = ""
    blockers: list[str] = []
    warnings: list[str] = []
    if not body.strip():
        blockers.append("body is required and must contain non-whitespace text.")

    resolved_archive_id = archive_id or str(archive_config.get("archive_id") or "")
    archive_type = archive_config.get("type") if isinstance(archive_config.get("type"), str) else None
    if not resolved_archive_id:
        blockers.append("archive.yml does not contain archive_id and archive_id was not provided.")
    if expected_archive_id and expected_archive_id != resolved_archive_id:
        blockers.append(f"Expected archive id mismatch: expected {expected_archive_id}, found {resolved_archive_id}.")
    if expected_type and expected_type != archive_type:
        blockers.append(f"Expected archive type mismatch: expected {expected_type}, found {archive_type or 'unknown'}.")

    now = (created_at or datetime.now().astimezone().replace(microsecond=0).isoformat()).strip()
    if not now:
        blockers.append("created_at must not be empty.")
        now = datetime.now().astimezone().replace(microsecond=0).isoformat()
    elif created_at and not valid_iso_timestamp(now):
        blockers.append("created_at must be an ISO 8601 timestamp.")

    if draft_id is not None:
        zettel_id = draft_id.strip()
        if not valid_draft_zettel_id(zettel_id):
            blockers.append("draft_id must be a safe zet id without path separators.")
    else:
        zettel_id = make_zettel_id(title, now)

    normalized_body = normalize_draft_body(body)
    body_sha256 = sha256_text(normalized_body)
    if expected_body_sha256:
        expected_hash = expected_body_sha256.strip().lower()
        if not SHA256_RE.match(expected_hash):
            blockers.append("expected_body_sha256 must be a 64-character lowercase hex SHA-256 value.")
        elif expected_hash != body_sha256:
            blockers.append("Expected body SHA-256 does not match the draft body.")

    if contains_forbidden_location_reference(body):
        blockers.append("Draft body appears to contain a provider URL or local absolute path.")
    if DRAFT_SECRET_VALUE_RE.search(body):
        blockers.append("Draft body appears to contain a secret-like value.")

    if creation_mode:
        if creation_mode not in DRAFT_CREATION_MODES:
            blockers.append("creation_mode must be one of: " + ", ".join(sorted(DRAFT_CREATION_MODES)) + ".")

    assisted = clean_optional_string_list(assisted_by)
    supervised = clean_optional_string_list(supervised_by)
    derived = clean_optional_string_list(derived_from)
    refs = normalize_source_refs(source_refs or [], blockers)
    sessions = normalize_local_ai_sessions(local_ai_sessions or [], blockers)
    validate_safe_draft_values(
        {
            "created_by": created_by,
            "source": source,
            "profile_id": profile_id,
            "profile_operator_id": profile_operator_id,
            "profile_authority_mode": profile_authority_mode,
            "assisted_by": assisted,
            "supervised_by": supervised,
            "derived_from": derived,
            "source_refs": refs,
            "local_ai_sessions": sessions,
            "draft_approved_by": draft_approved_by,
        },
        blockers,
    )

    profile_bound = any(
        value
        for value in [
            profile_id,
            profile_operator_id,
            profile_authority_mode,
            sessions,
        ]
    )
    if profile_bound and not dry_run:
        if not draft_approved_by:
            blockers.append("Profile-bound draft creation requires draft_approved_by.")
        if not expected_body_sha256:
            blockers.append("Profile-bound draft creation requires expected_body_sha256.")
    elif profile_bound and dry_run:
        if not draft_approved_by:
            warnings.append("Profile-bound write replay will require draft_approved_by.")
        if not expected_body_sha256:
            warnings.append("Profile-bound write replay will require expected_body_sha256.")

    if creation_mode in {"ai_assisted", "ai_generated"}:
        if not assisted:
            blockers.append("AI-assisted or AI-generated drafts must identify the assisting AI runtime.")

    frontmatter = {
        "id": zettel_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
        "archive_id": resolved_archive_id,
        "status": "draft",
        "kind": kind or "fleeting_capture",
        "facets": facets or {},
        "assets": [],
        "edges": [],
        "provenance": {
            "created_by": created_by,
            "created_in": resolved_archive_id,
            "source": source,
            "derived_from": derived,
        },
        "visibility": visibility or default_private_visibility(),
        "promotion": {
            "stage": "captured",
            "ready_for_promotion": False,
        },
    }
    if creation_mode:
        frontmatter["provenance"]["creation_mode"] = creation_mode
    if assisted:
        frontmatter["provenance"]["assisted_by"] = assisted
    if supervised:
        frontmatter["provenance"]["supervised_by"] = supervised
    if refs:
        frontmatter["source_refs"] = refs
    if sessions:
        frontmatter["local_ai_sessions"] = sessions
    if draft_approved_by or expected_body_sha256:
        frontmatter["draft_creation"] = {
            "approved_by": draft_approved_by,
            "approval_scope": "inbox_draft_only",
            "approved_body_sha256": expected_body_sha256.strip().lower() if expected_body_sha256 else None,
        }

    inbox = archive_internal_path(root, "inbox")
    path = inbox / f"{zettel_id}.md"
    if draft_id is None and not dry_run:
        suffix = 2
        base_zettel_id = zettel_id
        while path.exists():
            zettel_id = f"{base_zettel_id}_{suffix}"
            frontmatter["id"] = zettel_id
            path = inbox / f"{zettel_id}.md"
            suffix += 1
    elif path.exists():
        blockers.append(f"Proposed draft path already exists: inbox/{zettel_id}.md.")

    proposed_path = f"inbox/{zettel_id}.md"
    approval_replay = {
        "draft_id": zettel_id,
        "created_at": now,
        "expected_body_sha256": body_sha256,
        "expected_archive_id": expected_archive_id or resolved_archive_id,
        "expected_type": expected_type or archive_type,
        "profile_id": profile_id,
    }
    target_archive = {
        "archive_id": resolved_archive_id,
        "archive_type": archive_type,
        "profile_id": profile_id,
        "profile_operator_id": profile_operator_id,
        "profile_authority_mode": profile_authority_mode,
    }
    preview = {
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "create_draft",
        "target_archive": target_archive,
        "proposed_path": proposed_path,
        "frontmatter_preview": json_safe(frontmatter),
        "body_sha256": body_sha256,
        "blockers": unique_preserve_order(blockers),
        "warnings": unique_preserve_order(warnings),
        "would_change": [f"write {proposed_path}"],
        "approval_replay": approval_replay,
    }
    if dry_run:
        return preview
    if blockers:
        raise ArchiveServiceError("Draft creation blocked: " + "; ".join(unique_preserve_order(blockers)))

    inbox.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + dump_yaml(frontmatter) + "---\n\n" + normalized_body, encoding="utf-8")
    return {
        "ok": True,
        "dry_run": False,
        "lifecycle_action": "create_draft",
        "zettel_id": zettel_id,
        "path": archive_relative_path(path, root),
        "status": "draft",
        "target_archive": target_archive,
        "frontmatter": json_safe(frontmatter),
        "body_sha256": body_sha256,
        "warnings": unique_preserve_order(warnings),
        "created_paths": [archive_relative_path(path, root)],
        "approval_replay": approval_replay,
    }


def promote_zettel_dry_run(
    archive_root: Path | str,
    *,
    zettel_id: str | None = None,
    relative_path: str | None = None,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    path = resolve_zettel_path(root, zettel_id=zettel_id, relative_path=relative_path)
    draft_relative = archive_relative_path(path, root)
    frontmatter, body = split_zettel_text(path.read_text(encoding="utf-8"))
    frontmatter = json_safe(frontmatter)
    rules = load_zettel_rules(root)
    minting_rules = lifecycle_minting_rules(rules)
    paths = rules.get("paths") if isinstance(rules.get("paths"), dict) else {}
    note_kinds = note_kind_rules(rules)
    allowed_link_types = load_allowed_link_types(root)

    blockers: list[str] = []
    warnings: list[str] = []
    target_folder = normalize_rule_folder(
        root,
        minting_rules.get("default_target_path"),
        "zettels/",
        blockers,
        "Minting target",
    )
    receipt_folder = normalize_rule_folder(
        root,
        paths.get("receipts") if isinstance(paths, dict) else None,
        "receipts/",
        warnings,
        "Receipt",
    )

    if not draft_relative.startswith("inbox/"):
        blockers.append("Only drafts inside inbox/ can be promoted.")
    if frontmatter.get("status") != "draft":
        blockers.append("Draft status must be draft.")
    for field in REQUIRED_ZETTEL_FIELDS:
        if field not in frontmatter:
            blockers.append(f"Missing required frontmatter field: {field}.")

    kind = frontmatter.get("kind")
    if not kind:
        warnings.append("Recommended frontmatter field is missing: kind.")
    elif isinstance(kind, str):
        kind_rule = note_kinds.get(kind)
        if isinstance(kind_rule, dict) and kind_rule.get("canonical_allowed") is False:
            blockers.append(f"Note kind cannot be promoted to canonical memory: {kind}.")
        elif kind_rule is None:
            warnings.append(f"Unknown note kind in zettel-rules.yml: {kind}.")

    if "promotion" not in frontmatter:
        warnings.append("Recommended frontmatter field is missing: promotion.")
    if not str(frontmatter.get("title") or "").strip():
        blockers.append("Title must be present.")
    if not body.strip():
        blockers.append("Body must be present.")
    if contains_forbidden_location_reference(body):
        blockers.append("Body appears to contain a provider URL or local absolute path.")

    provenance = frontmatter.get("provenance")
    if not isinstance(provenance, dict):
        blockers.append("Provenance must be an object.")
    else:
        for field in ["created_by", "created_in", "source", "derived_from"]:
            if field not in provenance:
                blockers.append(f"Provenance is missing required field: {field}.")

    visibility = frontmatter.get("visibility")
    if not isinstance(visibility, dict):
        blockers.append("Visibility must be an object.")
    else:
        for field in ["scope", "source_visibility"]:
            if not visibility.get(field):
                blockers.append(f"Visibility is missing required field: {field}.")

    proposed_path = f"{target_folder}{path.name}"
    proposed_file = resolve_archive_relative_path(root, proposed_path)
    if proposed_file.exists():
        blockers.append(f"Proposed canonical path already exists: {proposed_path}.")

    checklist = build_minting_checklist(frontmatter, body, minting_rules, allowed_link_types)
    requires_checklist = bool(minting_rules.get("requires_checklist", True))
    if requires_checklist:
        for item in checklist:
            if item["required"] and item["status"] != "passed":
                blockers.append(
                    f"Required minting checklist item is not passed: {item['id']} ({item['status']})."
                )

    near_duplicates = find_promotion_duplicates(root, path, frontmatter, body, proposed_path)
    for duplicate in near_duplicates:
        message = (
            f"Possible duplicate canonical zettel: {duplicate['path']} "
            f"({duplicate['reason']})."
        )
        if duplicate["severity"] == "blocker":
            blockers.append(message)
        else:
            warnings.append(message)

    zettel_id_value = str(frontmatter.get("id") or path.stem)
    proposed_receipt_path = f"{receipt_folder}promotion/{zettel_id_value}.promotion.json"
    receipt_preview = build_promotion_receipt_preview(
        zettel_id=zettel_id_value,
        title=frontmatter.get("title"),
        draft_path=draft_relative,
        proposed_canonical_path=proposed_path,
        proposed_receipt_path=proposed_receipt_path,
        checklist=checklist,
        near_duplicates=near_duplicates,
        blockers=blockers,
        warnings=warnings,
        requires_human_approval=bool(minting_rules.get("requires_human_approval", True)),
    )
    return {
        "ok": not blockers,
        "dry_run": True,
        "draft_path": draft_relative,
        "zettel_id": frontmatter.get("id"),
        "title": frontmatter.get("title"),
        "proposed_canonical_path": proposed_path,
        "proposed_receipt_path": proposed_receipt_path,
        "blockers": blockers,
        "warnings": warnings,
        "checklist": checklist,
        "near_duplicates": near_duplicates,
        "receipt_preview": receipt_preview,
        "would_change": [
            "status -> canonical",
            "promotion.stage -> promoted",
            "updated_at -> current time",
            f"write {proposed_path}",
            f"write {proposed_receipt_path}",
        ],
    }


def promote_zettel(
    archive_root: Path | str,
    *,
    zettel_id: str | None = None,
    relative_path: str | None = None,
    reviewed_by: str,
    allow_warnings: bool = False,
) -> dict[str, Any]:
    reviewer = reviewed_by.strip()
    if not reviewer:
        raise ArchiveServiceError("Real promotion requires --reviewed-by.")

    root = require_existing_archive_root(archive_root)
    dry_run = promote_zettel_dry_run(root, zettel_id=zettel_id, relative_path=relative_path)
    if dry_run["blockers"]:
        raise ArchiveServiceError("Promotion blocked by dry-run: " + "; ".join(dry_run["blockers"]))
    if dry_run["warnings"] and not allow_warnings:
        raise ArchiveServiceError(
            "Promotion has warnings; rerun with --allow-warnings to approve them: "
            + "; ".join(dry_run["warnings"])
        )

    source_path = resolve_zettel_path(root, zettel_id=zettel_id, relative_path=relative_path)
    source_frontmatter, body = split_zettel_text(source_path.read_text(encoding="utf-8"))
    source_frontmatter = json_safe(source_frontmatter)

    canonical_relative = dry_run["proposed_canonical_path"]
    receipt_relative = dry_run["proposed_receipt_path"]
    canonical_path = resolve_archive_relative_path(root, canonical_relative)
    receipt_path = resolve_archive_relative_path(root, receipt_relative)
    if canonical_path.exists():
        raise ArchiveServiceError(f"Target canonical path already exists: {canonical_relative}.")
    if receipt_path.exists():
        raise ArchiveServiceError(f"Promotion receipt path already exists: {receipt_relative}.")

    now = datetime.now().astimezone().replace(microsecond=0).isoformat()
    promotion = source_frontmatter.get("promotion")
    if not isinstance(promotion, dict):
        promotion = {}
    promotion.update(
        {
            "stage": "promoted",
            "reviewed_by": reviewer,
            "reviewed_at": now,
            "checklist_version": "zettel-promotion/v0.2",
        }
    )
    canonical_frontmatter = dict(source_frontmatter)
    canonical_frontmatter["status"] = "canonical"
    canonical_frontmatter["updated_at"] = now
    canonical_frontmatter["promotion"] = promotion
    canonical_text = "---\n" + dump_yaml(canonical_frontmatter) + "---\n\n" + body.rstrip() + "\n"

    zettel_id_value = str(source_frontmatter.get("id") or source_path.stem)
    title = source_frontmatter.get("title")
    created_paths = [canonical_relative, receipt_relative]
    receipt = {
        "receipt_id": f"receipt:promotion:{zettel_id_value}",
        "action": "promote_zettel",
        "dry_run": False,
        "timestamp": now,
        "reviewed_by": reviewer,
        "source": {
            "path": dry_run["draft_path"],
        },
        "target": {
            "path": canonical_relative,
        },
        "zettel": {
            "id": zettel_id_value,
            "title": title,
        },
        "checklist": dry_run["checklist"],
        "near_duplicates": dry_run["near_duplicates"],
        "warnings": dry_run["warnings"],
        "result": {
            "created_paths": created_paths,
        },
    }

    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    created_canonical = False
    created_receipt = False
    try:
        with canonical_path.open("x", encoding="utf-8") as handle:
            created_canonical = True
            handle.write(canonical_text)
        with receipt_path.open("x", encoding="utf-8") as handle:
            created_receipt = True
            handle.write(json.dumps(json_safe(receipt), indent=2, ensure_ascii=False, default=str) + "\n")
    except OSError:
        if created_canonical and canonical_path.exists():
            canonical_path.unlink()
        if created_receipt and receipt_path.exists():
            receipt_path.unlink()
        raise

    return {
        "ok": True,
        "dry_run": False,
        "draft_path": dry_run["draft_path"],
        "zettel_id": zettel_id_value,
        "title": title,
        "canonical_path": canonical_relative,
        "receipt_path": receipt_relative,
        "reviewed_by": reviewer,
        "warnings": dry_run["warnings"],
        "near_duplicates": dry_run["near_duplicates"],
        "checklist": dry_run["checklist"],
        "created_paths": created_paths,
        "receipt": json_safe(receipt),
    }


def mint_zettel_dry_run(
    archive_root: Path | str,
    *,
    zettel_id: str | None = None,
    relative_path: str | None = None,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    promotion_dry_run = promote_zettel_dry_run(root, zettel_id=zettel_id, relative_path=relative_path)
    source_path = resolve_zettel_path(root, zettel_id=zettel_id, relative_path=relative_path)
    source_frontmatter, _body = split_zettel_text(source_path.read_text(encoding="utf-8"))
    source_frontmatter = json_safe(source_frontmatter)

    zettel_id_value = str(source_frontmatter.get("id") or source_path.stem)
    receipt_relative = f"{MINT_RECEIPTS_DIR}/{zettel_id_value}.mint.json"
    snapshot_relative = f"{MINT_DRAFT_SNAPSHOTS_DIR}/{zettel_id_value}.draft.md"
    blockers = list(promotion_dry_run["blockers"])
    warnings = list(promotion_dry_run["warnings"])

    receipt_path = resolve_archive_relative_path(root, receipt_relative)
    snapshot_path = resolve_archive_relative_path(root, snapshot_relative)
    if receipt_path.exists():
        blockers.append(f"Mint receipt path already exists: {receipt_relative}.")
    if snapshot_path.exists():
        blockers.append(f"Draft snapshot path already exists: {snapshot_relative}.")

    receipt_preview = build_mint_receipt_preview(
        archive_root=root,
        source_path=source_path,
        frontmatter=source_frontmatter,
        zettel_id=zettel_id_value,
        title=source_frontmatter.get("title"),
        draft_path=promotion_dry_run["draft_path"],
        proposed_canonical_path=promotion_dry_run["proposed_canonical_path"],
        proposed_receipt_path=receipt_relative,
        proposed_snapshot_path=snapshot_relative,
        checklist=promotion_dry_run["checklist"],
        near_duplicates=promotion_dry_run["near_duplicates"],
        blockers=blockers,
        warnings=warnings,
    )
    return {
        "ok": not blockers,
        "dry_run": True,
        "draft_path": promotion_dry_run["draft_path"],
        "zettel_id": zettel_id_value,
        "title": source_frontmatter.get("title"),
        "authority_mode": MINT_AUTHORITY_MODE,
        "proposed_canonical_path": promotion_dry_run["proposed_canonical_path"],
        "proposed_mint_receipt_path": receipt_relative,
        "proposed_draft_snapshot_path": snapshot_relative,
        "blockers": blockers,
        "warnings": warnings,
        "checklist": promotion_dry_run["checklist"],
        "near_duplicates": promotion_dry_run["near_duplicates"],
        "receipt_preview": receipt_preview,
        "would_change": [
            "status -> canonical",
            "mint.stage -> minted",
            "mint.authority_mode -> basic",
            "promotion.stage -> promoted",
            "updated_at -> current time",
            f"write {promotion_dry_run['proposed_canonical_path']}",
            f"write {receipt_relative}",
            f"write {snapshot_relative}",
        ],
    }


def mint_zettel(
    archive_root: Path | str,
    *,
    zettel_id: str | None = None,
    relative_path: str | None = None,
    reviewed_by: str,
    allow_warnings: bool = False,
) -> dict[str, Any]:
    reviewer = reviewed_by.strip()
    if not reviewer:
        raise ArchiveServiceError("Real minting requires --reviewed-by.")

    root = require_existing_archive_root(archive_root)
    dry_run = mint_zettel_dry_run(root, zettel_id=zettel_id, relative_path=relative_path)
    if dry_run["blockers"]:
        raise ArchiveServiceError("Minting blocked by dry-run: " + "; ".join(dry_run["blockers"]))
    if dry_run["warnings"] and not allow_warnings:
        raise ArchiveServiceError(
            "Minting has warnings; rerun with --allow-warnings to approve them: "
            + "; ".join(dry_run["warnings"])
        )

    source_path = resolve_zettel_path(root, zettel_id=zettel_id, relative_path=relative_path)
    source_text = source_path.read_text(encoding="utf-8")
    source_frontmatter, body = split_zettel_text(source_text)
    source_frontmatter = json_safe(source_frontmatter)

    canonical_relative = dry_run["proposed_canonical_path"]
    receipt_relative = dry_run["proposed_mint_receipt_path"]
    snapshot_relative = dry_run["proposed_draft_snapshot_path"]
    canonical_path = resolve_archive_relative_path(root, canonical_relative)
    receipt_path = resolve_archive_relative_path(root, receipt_relative)
    snapshot_path = resolve_archive_relative_path(root, snapshot_relative)
    if canonical_path.exists():
        raise ArchiveServiceError(f"Target canonical path already exists: {canonical_relative}.")
    if receipt_path.exists():
        raise ArchiveServiceError(f"Mint receipt path already exists: {receipt_relative}.")
    if snapshot_path.exists():
        raise ArchiveServiceError(f"Draft snapshot path already exists: {snapshot_relative}.")

    now = datetime.now().astimezone().replace(microsecond=0).isoformat()
    promotion = source_frontmatter.get("promotion")
    if not isinstance(promotion, dict):
        promotion = {}
    promotion.update(
        {
            "stage": "promoted",
            "reviewed_by": reviewer,
            "reviewed_at": now,
            "checklist_version": "zettel-promotion/v0.2",
        }
    )
    mint = {
        "stage": "minted",
        "minted_at": now,
        "reviewed_by": reviewer,
        "authority_mode": MINT_AUTHORITY_MODE,
        "receipt_path": receipt_relative,
        "draft_snapshot_path": snapshot_relative,
        "checklist_version": MINT_CHECKLIST_VERSION,
    }
    canonical_frontmatter = dict(source_frontmatter)
    canonical_frontmatter["status"] = "canonical"
    canonical_frontmatter["updated_at"] = now
    canonical_frontmatter["mint"] = mint
    canonical_frontmatter["promotion"] = promotion
    canonical_text = "---\n" + dump_yaml(canonical_frontmatter) + "---\n\n" + body.rstrip() + "\n"

    zettel_id_value = str(source_frontmatter.get("id") or source_path.stem)
    title = source_frontmatter.get("title")
    created_paths = [canonical_relative, receipt_relative, snapshot_relative]

    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    created_files: list[Path] = []
    try:
        with canonical_path.open("x", encoding="utf-8") as handle:
            created_files.append(canonical_path)
            handle.write(canonical_text)
        with snapshot_path.open("x", encoding="utf-8") as handle:
            created_files.append(snapshot_path)
            handle.write(source_text)

        source_sha = sha256_path(source_path)
        canonical_sha = sha256_path(canonical_path)
        snapshot_sha = sha256_path(snapshot_path)
        receipt = {
            "receipt_id": f"receipt:mint:{zettel_id_value}",
            "receipt_path": receipt_relative,
            "action": "mint_zettel",
            "dry_run": False,
            "timestamp": now,
            "archive_id": read_archive_id(root),
            "authority_mode": MINT_AUTHORITY_MODE,
            "reviewed_by": reviewer,
            "reviewed_at": now,
            "source": {
                "path": dry_run["draft_path"],
                "status": "draft",
                "sha256": source_sha,
            },
            "target": {
                "path": canonical_relative,
                "status": "canonical",
                "sha256": canonical_sha,
            },
            "snapshot": {
                "path": snapshot_relative,
                "sha256": snapshot_sha,
            },
            "zettel": {
                "id": zettel_id_value,
                "title": title,
            },
            "source_refs": extract_mint_source_refs(source_frontmatter),
            "edges": source_frontmatter.get("edges") if isinstance(source_frontmatter.get("edges"), list) else [],
            "local_ai_sessions": extract_mint_local_ai_sessions(source_frontmatter),
            "checklist": dry_run["checklist"],
            "near_duplicates": dry_run["near_duplicates"],
            "warnings": dry_run["warnings"],
            "result": {
                "created_paths": created_paths,
            },
        }
        with receipt_path.open("x", encoding="utf-8") as handle:
            created_files.append(receipt_path)
            handle.write(json.dumps(json_safe(receipt), indent=2, ensure_ascii=False, default=str) + "\n")
    except OSError:
        for created_path in reversed(created_files):
            if created_path.exists():
                created_path.unlink()
        raise

    return {
        "ok": True,
        "dry_run": False,
        "draft_path": dry_run["draft_path"],
        "zettel_id": zettel_id_value,
        "title": title,
        "authority_mode": MINT_AUTHORITY_MODE,
        "canonical_path": canonical_relative,
        "mint_receipt_path": receipt_relative,
        "draft_snapshot_path": snapshot_relative,
        "reviewed_by": reviewer,
        "warnings": dry_run["warnings"],
        "near_duplicates": dry_run["near_duplicates"],
        "checklist": dry_run["checklist"],
        "created_paths": created_paths,
        "receipt": json_safe(receipt),
    }


def load_zettel_rules(archive_root: Path) -> dict[str, Any]:
    for path in [
        archive_internal_path(archive_root, "zettel-kasten/zettel-rules.yml"),
        KIT_ROOT / "zettel-kasten" / "zettel-rules.yml",
    ]:
        if path.is_file():
            data = load_yaml(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    return {}


def load_allowed_link_types(archive_root: Path) -> set[str]:
    for path in [
        archive_internal_path(archive_root, "zettel-kasten/types.yml"),
        KIT_ROOT / "zettel-kasten" / "types.yml",
    ]:
        if not path.is_file():
            continue
        data = load_yaml(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        link_types = data.get("link_types") or []
        if isinstance(link_types, list):
            return {item.get("id") for item in link_types if isinstance(item, dict) and item.get("id")}
    return set()


def note_kind_rules(rules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    note_kinds = rules.get("note_kinds") or []
    if not isinstance(note_kinds, list):
        return {}
    return {
        item["id"]: item
        for item in note_kinds
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def lifecycle_minting_rules(rules: dict[str, Any]) -> dict[str, Any]:
    minting_rules = rules.get("minting_rules")
    if isinstance(minting_rules, dict):
        return minting_rules
    promotion_rules = rules.get("promotion_rules")
    if isinstance(promotion_rules, dict):
        return promotion_rules
    return {}


def normalize_rule_folder(
    archive_root: Path,
    raw_path: Any,
    fallback: str,
    issues: list[str],
    label: str,
) -> str:
    candidate = raw_path if isinstance(raw_path, str) and raw_path.strip() else fallback
    try:
        resolved = resolve_archive_relative_path(archive_root, candidate)
        relative = archive_relative_path(resolved, archive_root)
    except ArchivePathError as exc:
        issues.append(f"{label} path in zettel-rules.yml is unsafe: {candidate} ({exc}).")
        relative = fallback.strip("/")
    return relative.rstrip("/") + "/"


def build_promotion_checklist(
    frontmatter: dict[str, Any],
    body: str,
    promotion_rules: dict[str, Any],
    allowed_link_types: set[str],
) -> list[dict[str, Any]]:
    raw_items = promotion_rules.get("checklist") if isinstance(promotion_rules, dict) else []
    if not isinstance(raw_items, list):
        return []

    promotion = frontmatter.get("promotion") if isinstance(frontmatter.get("promotion"), dict) else {}
    results: list[dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict) or not isinstance(raw_item.get("id"), str):
            continue
        item_id = raw_item["id"]
        required = bool(raw_item.get("required", False))
        explicit = promotion_checklist_decision(promotion, item_id)
        if explicit is True:
            status = "passed"
            message = "Marked as passed in frontmatter."
            source = "frontmatter"
        elif explicit is False:
            status = "blocked"
            message = "Marked as not passed in frontmatter."
            source = "frontmatter"
        else:
            status, message = infer_promotion_checklist_item(item_id, frontmatter, body, allowed_link_types)
            source = "machine"
        results.append(
            {
                "id": item_id,
                "question": raw_item.get("question"),
                "required": required,
                "status": status,
                "source": source,
                "message": message,
            }
        )
    return results


def build_minting_checklist(
    frontmatter: dict[str, Any],
    body: str,
    minting_rules: dict[str, Any],
    allowed_link_types: set[str],
) -> list[dict[str, Any]]:
    return build_lifecycle_checklist(frontmatter, body, minting_rules, allowed_link_types)


def build_lifecycle_checklist(
    frontmatter: dict[str, Any],
    body: str,
    rules: dict[str, Any],
    allowed_link_types: set[str],
) -> list[dict[str, Any]]:
    raw_items = rules.get("checklist") if isinstance(rules, dict) else []
    if not isinstance(raw_items, list):
        return []

    mint = frontmatter.get("mint") if isinstance(frontmatter.get("mint"), dict) else {}
    promotion = frontmatter.get("promotion") if isinstance(frontmatter.get("promotion"), dict) else {}
    results: list[dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict) or not isinstance(raw_item.get("id"), str):
            continue
        item_id = raw_item["id"]
        required = bool(raw_item.get("required", False))
        explicit = lifecycle_checklist_decision(mint, item_id)
        source_label = "mint_frontmatter"
        if explicit is None:
            explicit = promotion_checklist_decision(promotion, item_id)
            source_label = "legacy_promotion_frontmatter"
        if explicit is True:
            status = "passed"
            message = "Marked as passed in frontmatter."
            source = source_label
        elif explicit is False:
            status = "blocked"
            message = "Marked as not passed in frontmatter."
            source = source_label
        else:
            status, message = infer_promotion_checklist_item(item_id, frontmatter, body, allowed_link_types)
            source = "machine"
        results.append(
            {
                "id": item_id,
                "question": raw_item.get("question"),
                "required": required,
                "status": status,
                "source": source,
                "message": message,
            }
        )
    return results


def lifecycle_checklist_decision(lifecycle: dict[str, Any], item_id: str) -> bool | None:
    checklist = lifecycle.get("checklist")
    if isinstance(checklist, dict):
        return interpret_promotion_checklist_value(checklist.get(item_id))
    if isinstance(checklist, list):
        for entry in checklist:
            if isinstance(entry, dict) and entry.get("id") == item_id:
                if "passed" in entry:
                    return interpret_promotion_checklist_value(entry.get("passed"))
                return interpret_promotion_checklist_value(entry.get("status"))
    return None


def promotion_checklist_decision(promotion: dict[str, Any], item_id: str) -> bool | None:
    checklist = promotion.get("checklist")
    if isinstance(checklist, dict):
        return interpret_promotion_checklist_value(checklist.get(item_id))
    if isinstance(checklist, list):
        for entry in checklist:
            if isinstance(entry, dict) and entry.get("id") == item_id:
                if "passed" in entry:
                    return interpret_promotion_checklist_value(entry.get("passed"))
                return interpret_promotion_checklist_value(entry.get("status"))
    return None


def interpret_promotion_checklist_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in PROMOTION_CHECKLIST_PASS_VALUES:
            return True
        if normalized in PROMOTION_CHECKLIST_FAIL_VALUES:
            return False
    if isinstance(value, dict):
        if "passed" in value:
            return interpret_promotion_checklist_value(value.get("passed"))
        if "status" in value:
            return interpret_promotion_checklist_value(value.get("status"))
    return None


def infer_promotion_checklist_item(
    item_id: str,
    frontmatter: dict[str, Any],
    body: str,
    allowed_link_types: set[str],
) -> tuple[str, str]:
    title = str(frontmatter.get("title") or "").strip()
    facets = frontmatter.get("facets")
    provenance = frontmatter.get("provenance")
    visibility = frontmatter.get("visibility")
    edges = frontmatter.get("edges")

    if item_id == "understandable_title":
        if len(title) >= 5 and title.lower() not in {"draft", "untitled", "note"}:
            return "passed", "Title is present and specific enough for a machine check."
        return "blocked", "Title is missing or too vague."
    if item_id == "future_self_contained":
        if len(body.strip()) >= 40:
            return "passed", "Body has enough content for a first self-contained check."
        return "blocked", "Body is too short to stand alone."
    if item_id == "source_clarity":
        if isinstance(provenance, dict) and provenance.get("source"):
            return "passed", "Provenance includes a source."
        return "blocked", "Provenance source is missing."
    if item_id == "object_id_only":
        if contains_forbidden_location_reference(body):
            return "blocked", "Body contains a provider URL or local absolute path."
        return "passed", "No provider URL or local absolute path was detected."
    if item_id == "stable_facets":
        if isinstance(facets, dict) and bool(facets):
            return "passed", "Facets are present."
        return "blocked", "Facets are missing or empty."
    if item_id == "allowed_edges":
        if not isinstance(edges, list):
            return "blocked", "Edges must be a list."
        unknown_edges = [
            edge.get("type")
            for edge in edges
            if isinstance(edge, dict)
            and edge.get("type")
            and allowed_link_types
            and edge.get("type") not in allowed_link_types
        ]
        if unknown_edges:
            return "blocked", "Unknown edge type(s): " + ", ".join(str(item) for item in unknown_edges)
        return "passed", "Edges are empty or use allowed types."
    if item_id == "explicit_visibility":
        if isinstance(visibility, dict) and visibility.get("scope") and visibility.get("source_visibility"):
            return "passed", "Visibility fields are explicit."
        return "blocked", "Visibility scope or source visibility is missing."
    if item_id == "provenance_present":
        if isinstance(provenance, dict) and provenance.get("created_by") and provenance.get("created_in") and provenance.get("source"):
            return "passed", "Provenance has creator, archive, and source."
        return "blocked", "Provenance is incomplete."
    if item_id in {"one_clear_purpose", "sensitive_content_reviewed"}:
        return "needs_human_review", "This checklist item needs explicit human review."
    return "needs_human_review", "No machine check exists for this checklist item yet."


def find_promotion_duplicates(
    archive_root: Path,
    draft_path: Path,
    frontmatter: dict[str, Any],
    body: str,
    proposed_path: str,
) -> list[dict[str, Any]]:
    canonical_root = archive_root / "zettels"
    if not canonical_root.is_dir():
        return []

    zettel_id = str(frontmatter.get("id") or "")
    title_key = normalize_compare_text(str(frontmatter.get("title") or ""))
    body_key = normalize_compare_text(body)[:500]
    duplicates: list[dict[str, Any]] = []
    for candidate in safe_archive_glob(canonical_root, "*.md", archive_root, recursive=True):
        if candidate.resolve() == draft_path.resolve():
            continue
        candidate_relative = archive_relative_path(candidate, archive_root)
        candidate_frontmatter, candidate_body = split_zettel_text(candidate.read_text(encoding="utf-8"))
        candidate_frontmatter = json_safe(candidate_frontmatter)

        if candidate_relative == proposed_path:
            duplicates.append(
                {
                    "path": candidate_relative,
                    "reason": "target_path_exists",
                    "severity": "blocker",
                }
            )
            continue
        if zettel_id and candidate_frontmatter.get("id") == zettel_id:
            duplicates.append(
                {
                    "path": candidate_relative,
                    "reason": "same_zettel_id",
                    "severity": "blocker",
                }
            )
            continue
        if title_key and normalize_compare_text(str(candidate_frontmatter.get("title") or "")) == title_key:
            duplicates.append(
                {
                    "path": candidate_relative,
                    "reason": "same_title",
                    "severity": "warning",
                }
            )
            continue
        if len(body_key) >= 120 and normalize_compare_text(candidate_body)[:500] == body_key:
            duplicates.append(
                {
                    "path": candidate_relative,
                    "reason": "very_similar_body_start",
                    "severity": "warning",
                }
            )
    return duplicates


def normalize_compare_text(text: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]+", " ", text.lower()).strip()


def build_promotion_receipt_preview(
    *,
    zettel_id: str,
    title: Any,
    draft_path: str,
    proposed_canonical_path: str,
    proposed_receipt_path: str,
    checklist: list[dict[str, Any]],
    near_duplicates: list[dict[str, Any]],
    blockers: list[str],
    warnings: list[str],
    requires_human_approval: bool,
) -> dict[str, Any]:
    return {
        "receipt_id": f"receipt:promotion:{zettel_id}",
        "receipt_path": proposed_receipt_path,
        "action": "promote_zettel",
        "dry_run": True,
        "timestamp": "<execution-time>",
        "requires_human_approval": requires_human_approval,
        "source": {
            "path": draft_path,
            "status": "draft",
        },
        "target": {
            "path": proposed_canonical_path,
            "status": "canonical",
        },
        "zettel": {
            "id": zettel_id,
            "title": title,
        },
        "checklist": checklist,
        "near_duplicates": near_duplicates,
        "blockers": blockers,
        "warnings": warnings,
    }


def build_mint_receipt_preview(
    *,
    archive_root: Path,
    source_path: Path,
    frontmatter: dict[str, Any],
    zettel_id: str,
    title: Any,
    draft_path: str,
    proposed_canonical_path: str,
    proposed_receipt_path: str,
    proposed_snapshot_path: str,
    checklist: list[dict[str, Any]],
    near_duplicates: list[dict[str, Any]],
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    source_sha = sha256_path(source_path)
    return {
        "receipt_id": f"receipt:mint:{zettel_id}",
        "receipt_path": proposed_receipt_path,
        "action": "mint_zettel",
        "dry_run": True,
        "timestamp": "<execution-time>",
        "archive_id": read_archive_id(archive_root),
        "authority_mode": MINT_AUTHORITY_MODE,
        "reviewed_by": "<required-on-approve>",
        "source": {
            "path": draft_path,
            "status": "draft",
            "sha256": source_sha,
        },
        "target": {
            "path": proposed_canonical_path,
            "status": "canonical",
            "sha256": "<after-write>",
        },
        "snapshot": {
            "path": proposed_snapshot_path,
            "sha256": source_sha,
        },
        "zettel": {
            "id": zettel_id,
            "title": title,
        },
        "source_refs": extract_mint_source_refs(frontmatter),
        "edges": frontmatter.get("edges") if isinstance(frontmatter.get("edges"), list) else [],
        "local_ai_sessions": extract_mint_local_ai_sessions(frontmatter),
        "checklist": checklist,
        "near_duplicates": near_duplicates,
        "blockers": blockers,
        "warnings": warnings,
    }


def extract_mint_source_refs(frontmatter: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    explicit_refs = frontmatter.get("source_refs")
    if isinstance(explicit_refs, list):
        for item in explicit_refs:
            if isinstance(item, dict):
                refs.append(json_safe(item))
            elif item is not None:
                refs.append({"type": "source_ref", "value": str(item)})

    provenance = frontmatter.get("provenance")
    if isinstance(provenance, dict):
        source = provenance.get("source")
        if source:
            refs.append({"type": "provenance_source", "value": str(source)})
        derived_from = provenance.get("derived_from")
        if isinstance(derived_from, list):
            for item in derived_from:
                if isinstance(item, dict):
                    refs.append(json_safe(item))
                elif item is not None:
                    refs.append({"type": "derived_from", "value": str(item)})
    return refs


def extract_mint_local_ai_sessions(frontmatter: dict[str, Any]) -> list[dict[str, Any]]:
    sessions = frontmatter.get("local_ai_sessions")
    if isinstance(sessions, list):
        return [json_safe(item) if isinstance(item, dict) else {"value": str(item)} for item in sessions if item is not None]
    session = frontmatter.get("local_ai_session")
    if isinstance(session, dict):
        return [json_safe(session)]
    return []


def list_views(archive_root: Path | str) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    views_root = root / "views"
    views: list[dict[str, Any]] = []
    if views_root.is_dir():
        for path in safe_archive_glob(views_root, "*.yml", root):
            data = load_yaml(path.read_text(encoding="utf-8"))
            views.append(
                {
                    "path": archive_relative_path(path, root),
                    "id": data.get("id") if isinstance(data, dict) else None,
                    "name": data.get("name") if isinstance(data, dict) else None,
                    "for": data.get("for") if isinstance(data, dict) else None,
                }
            )
    return {"views": views, "count": len(views)}


def pack_work_context(
    archive_root: Path | str,
    *,
    view_id: str,
    purpose: str,
    mode: str = "reference",
    target_archive: str | None = None,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    if mode not in WORKPACK_MODES:
        raise ArchiveServiceError("mode must be one of: " + ", ".join(sorted(WORKPACK_MODES)))
    if not view_id:
        raise ArchiveServiceError("view_id is required.")
    if not purpose.strip():
        raise ArchiveServiceError("purpose is required.")

    view = resolve_view(root, view_id)
    selected = select_zettels_for_view(root, view)
    source_archive = read_archive_id(root)
    identity_doc = load_archive_identity(root)
    ownership = identity_doc.get("ownership") if isinstance(identity_doc.get("ownership"), dict) else {}
    now = datetime.now().astimezone().replace(microsecond=0).isoformat()
    package_id = unique_workpack_id(root, view_id, now)
    package_root = archive_internal_path(root, f"workpacks/{package_id}")
    zettels_root = package_root / "zettels"
    manifests_root = package_root / "manifests"
    views_root = package_root / "views"
    for folder in [zettels_root, manifests_root, views_root]:
        folder.mkdir(parents=True, exist_ok=False)

    zettel_entries: list[dict[str, Any]] = []
    object_ids: set[str] = set()
    for zettel in selected:
        source_path = zettel["path"]
        destination = zettels_root / source_path.name
        shutil.copy2(source_path, destination)
        frontmatter = zettel["frontmatter"]
        zettel_entries.append(
            {
                "id": frontmatter.get("id"),
                "title": frontmatter.get("title"),
                "source_path": archive_relative_path(source_path, root),
                "package_path": archive_relative_path(destination, package_root),
            }
        )
        for object_id in zettel_object_ids(frontmatter):
            object_ids.add(object_id)

    manifest_records = load_manifest_records(root)
    selected_manifest_records = [record for record in manifest_records if record.get("object_id") in object_ids]
    manifest_path = manifests_root / "files.jsonl"
    manifest_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, default=str, separators=(",", ":")) + "\n" for record in selected_manifest_records),
        encoding="utf-8",
    )

    view_path = views_root / f"{safe_slug(view_id)}.yml"
    view_snapshot = {
        "id": view["id"],
        "name": view.get("name"),
        "for": "workpack",
        "filters": view.get("filters") or {},
        "include": view.get("include") or {},
        "context_policy": view.get("context_policy") or {},
        "source_view_path": view.get("source_path"),
    }
    view_path.write_text(dump_yaml(view_snapshot), encoding="utf-8")

    package = {
        "package_id": package_id,
        "source_archive": source_archive,
        "target_archive": target_archive,
        "mode": mode,
        "purpose": purpose,
        "contents": {
            "view_id": view_id,
            "view_path": archive_relative_path(view_path, package_root),
            "zettels": zettel_entries,
            "objects": {
                "include_originals": False,
                "include_metadata_only": True,
                "manifest_path": archive_relative_path(manifest_path, package_root),
                "object_ids": sorted(object_ids),
            },
            "receipts": [],
        },
        "permissions": {
            "can_read": True,
            "can_modify": False,
            "can_import_as_derivative": mode in {"derive", "handover", "return", "copy", "reference"},
            "can_reshare": False,
        },
        "provenance": {
            "created_by": "cli:archive",
            "created_at": now,
            "source_view": view_id,
            "source_paths": [entry["source_path"] for entry in zettel_entries],
        },
        "scope_gate": {
            "unit": "view",
            "view_id": view_id,
            "source_view_path": view.get("source_path"),
            "included_zettels": [entry["source_path"] for entry in zettel_entries],
            "included_objects": sorted(object_ids),
            "excluded": [],
            "sensitive_categories_blocked_by_default": sorted(SENSITIVE_SHARE_CATEGORIES),
        },
        "trust_gate": {
            "counterparty_identity_required": bool(target_archive),
            "counterparty_fingerprint_required": bool(target_archive),
            "verification_method": "archive_identity_fingerprint",
            "signatures": "optional_v1",
        },
        "ownership_gate": {
            "ownership_transfer": False,
            "current_owner": ownership.get("owner_id"),
            "current_owner_kind": ownership.get("owner_kind"),
            "operators": ownership.get("operators") if isinstance(ownership.get("operators"), list) else [],
            "receipt_required_for_transfer": True,
        },
        "lineage": {
            "event": "share_scope",
            "source_archive": source_archive,
            "target_archive": target_archive,
            "source_view": view_id,
        },
    }
    if target_archive is None:
        del package["target_archive"]

    package_path = package_root / "package.yml"
    package_path.write_text(dump_yaml(package), encoding="utf-8")

    return {
        "ok": True,
        "package_id": package_id,
        "package_path": archive_relative_path(package_root, root),
        "package_file": archive_relative_path(package_path, root),
        "source_archive": source_archive,
        "target_archive": target_archive,
        "mode": mode,
        "view_id": view_id,
        "zettels": len(zettel_entries),
        "objects": len(selected_manifest_records),
        "receipts": 0,
        "contents": package["contents"],
    }


def import_workpack_dry_run(archive_root: Path | str, workpack_path: Path | str) -> dict[str, Any]:
    return import_workpack_dry_run_with_trust(archive_root, workpack_path)


def import_workpack_dry_run_with_trust(
    archive_root: Path | str,
    workpack_path: Path | str,
    *,
    counterparty_id: str | None = None,
    counterparty_fingerprint: str | None = None,
) -> dict[str, Any]:
    target_root = require_existing_archive_root(archive_root)
    package_root, package_file = resolve_workpack_package_path(workpack_path)
    package = load_yaml(package_file.read_text(encoding="utf-8"))
    if not isinstance(package, dict):
        raise ArchiveServiceError("Workpack package.yml must be a YAML object.")

    blockers: list[str] = []
    warnings: list[str] = []
    for issue in validate_schema(package, "workpack.schema.json"):
        blockers.append(f"{issue.code}: {issue.message}")

    package_id = str(package.get("package_id") or package_root.name)
    mode = package.get("mode")
    if mode not in WORKPACK_MODES:
        blockers.append(f"Invalid workpack mode: {mode}.")

    permissions = package.get("permissions") if isinstance(package.get("permissions"), dict) else {}
    if permissions.get("can_read") is not True:
        blockers.append("Workpack permissions.can_read must be true for import dry-run.")
    if mode == "derive" and permissions.get("can_import_as_derivative") is not True:
        blockers.append("Derived workpack import requires permissions.can_import_as_derivative: true.")

    target_archive_id = read_archive_id(target_root)
    declared_target = package.get("target_archive")
    if isinstance(declared_target, str) and declared_target and declared_target != target_archive_id:
        warnings.append(f"Workpack target_archive is {declared_target}, but target archive is {target_archive_id}.")

    zettel_previews = inspect_workpack_zettels(target_root, package_root, package, blockers, warnings)
    object_previews = inspect_workpack_manifest(target_root, package_root, package, blockers, warnings)
    scope_gate = build_import_scope_gate(package, zettel_previews, object_previews)
    ownership_gate = package.get("ownership_gate") if isinstance(package.get("ownership_gate"), dict) else {"ownership_transfer": False}
    trust_gate = build_import_trust_gate(
        target_root,
        package,
        counterparty_id=counterparty_id,
        counterparty_fingerprint=counterparty_fingerprint,
        blockers=blockers,
    )

    proposed_receipt_path = f"receipts/import/{package_id}.import.json"
    receipt_preview = {
        "receipt_id": f"receipt:import:{package_id}",
        "receipt_path": proposed_receipt_path,
        "action": "import_workpack",
        "dry_run": True,
        "timestamp": "<execution-time>",
        "package": {
            "package_id": package_id,
            "package_path": str(package_root),
            "mode": mode,
        },
        "target_archive": target_archive_id,
        "scope_gate": scope_gate,
        "trust_gate": trust_gate,
        "ownership_gate": ownership_gate,
        "proposed": {
            "zettels_to_inbox": [item["target_path"] for item in zettel_previews if item["action"] == "create_inbox_draft"],
            "objects_to_merge": [item["object_id"] for item in object_previews if item["action"] == "append_manifest_record"],
            "receipt_path": proposed_receipt_path,
        },
        "blockers": blockers,
        "warnings": warnings,
    }

    return {
        "ok": not blockers,
        "dry_run": True,
        "package_id": package_id,
        "package_file": str(package_file),
        "target_archive": target_archive_id,
        "blockers": blockers,
        "warnings": warnings,
        "zettels": zettel_previews,
        "objects": object_previews,
        "scope_gate": scope_gate,
        "trust_gate": trust_gate,
        "ownership_gate": ownership_gate,
        "proposed_receipt_path": proposed_receipt_path,
        "receipt_preview": receipt_preview,
        "would_change": [
            "write selected zettels to target inbox/",
            "append new object metadata to target objects/manifests/files.jsonl",
            f"write {proposed_receipt_path}",
        ],
    }


def external_import_dry_run(
    archive_root: Path | str,
    export_path: Path | str,
    *,
    source_system: str,
    limit: int = 200,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    source = normalize_external_import_source(source_system)
    export_root = Path(export_path).expanduser().resolve()
    if not export_root.exists():
        raise ArchiveServiceError(f"External import export path does not exist: {export_root}")
    limit = max(1, min(int(limit), 1000))

    blockers: list[str] = []
    warnings: list[str] = []
    target_archive = read_archive_id(root)
    discovered = discover_external_import_items(export_root, source, limit=limit, warnings=warnings)
    if not discovered:
        blockers.append("No importable Markdown or text items were found.")

    target_ids = collect_target_zettel_ids(root)
    previews: list[dict[str, Any]] = []
    for item in discovered:
        zettel_id = external_import_zettel_id(source, item)
        target_path = f"inbox/{zettel_id}.md"
        conflicts: list[str] = []
        if zettel_id in target_ids:
            conflicts.append("zettel_id_exists")
            blockers.append(f"Target archive already has imported zettel id: {zettel_id}.")
        if archive_internal_path(root, target_path).exists():
            conflicts.append("target_path_exists")
            blockers.append(f"Target inbox path already exists: {target_path}.")
        if contains_forbidden_location_reference(item["body"]):
            conflicts.append("forbidden_location_reference")
            blockers.append(f"External item contains a forbidden provider/local path reference: {item['source_path']}.")
        previews.append(
            {
                "external_id": item["external_id"],
                "title": item["title"],
                "source_path": item["source_path"],
                "source_url": item.get("source_url"),
                "sha256": item["sha256"],
                "zettel_id": zettel_id,
                "target_path": target_path,
                "action": "create_inbox_draft",
                "conflicts": conflicts,
            }
        )

    export_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "source": source,
                "export_path": str(export_root),
                "items": [item["sha256"] for item in discovered],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    proposed_receipt_path = f"receipts/import/{source}_{export_fingerprint}.external-import.json"
    if archive_internal_path(root, proposed_receipt_path).exists():
        blockers.append(f"Proposed external import receipt already exists: {proposed_receipt_path}.")

    scope_gate = {
        "unit": "external_export",
        "source_system": source,
        "source_export_path": str(export_root),
        "item_count": len(previews),
        "included": [item["source_path"] for item in previews],
        "excluded": [],
        "sensitive_categories_blocked_by_default": sorted(SENSITIVE_SHARE_CATEGORIES),
    }
    trust_gate = {
        "required": False,
        "ok": True,
        "status": "local_export_input",
        "external_api_called": False,
        "secret_values_required": False,
    }
    lineage = {
        "event": "external_import",
        "source_system": source,
        "target_archive": target_archive,
        "source_export_path": str(export_root),
    }
    receipt_preview = {
        "receipt_id": f"receipt:external-import:{source}:{export_fingerprint}",
        "receipt_path": proposed_receipt_path,
        "action": "import_external_archive",
        "dry_run": True,
        "timestamp": "<execution-time>",
        "source_system": source,
        "source_export": {
            "path": str(export_root),
            "fingerprint": export_fingerprint,
            "mode": "manifest_or_export_folder",
            "external_api_called": False,
        },
        "target_archive": target_archive,
        "items": previews,
        "scope_gate": scope_gate,
        "trust_gate": trust_gate,
        "lineage": lineage,
        "blockers": blockers,
        "warnings": warnings,
    }
    return {
        "ok": not blockers,
        "dry_run": True,
        "source_system": source,
        "source_export": str(export_root),
        "target_archive": target_archive,
        "items": previews,
        "item_count": len(previews),
        "blockers": blockers,
        "warnings": warnings,
        "scope_gate": scope_gate,
        "trust_gate": trust_gate,
        "lineage": lineage,
        "proposed_receipt_path": proposed_receipt_path,
        "receipt_preview": receipt_preview,
        "would_change": [
            "write imported records as draft zettels under inbox/",
            f"write {proposed_receipt_path}",
        ],
    }


def import_external_archive(
    archive_root: Path | str,
    export_path: Path | str,
    *,
    source_system: str,
    reviewed_by: str,
    limit: int = 200,
) -> dict[str, Any]:
    reviewer = reviewed_by.strip()
    if not reviewer:
        raise ArchiveServiceError("External import requires --reviewed-by.")

    root = require_existing_archive_root(archive_root)
    dry_run = external_import_dry_run(root, export_path, source_system=source_system, limit=limit)
    if dry_run["blockers"]:
        raise ArchiveServiceError("External import blocked by dry-run: " + "; ".join(dry_run["blockers"]))

    now = datetime.now().astimezone().replace(microsecond=0).isoformat()
    source = dry_run["source_system"]
    discovered_by_id = {
        external_import_zettel_id(source, item): item
        for item in discover_external_import_items(
            Path(export_path).expanduser().resolve(),
            source,
            limit=limit,
            warnings=[],
        )
    }
    receipt_relative = dry_run["proposed_receipt_path"]
    receipt_path = archive_internal_path(root, receipt_relative)
    if receipt_path.exists():
        raise ArchiveServiceError(f"Proposed external import receipt already exists: {receipt_relative}.")

    created_paths: list[Path] = []
    created_relative_paths: list[str] = []
    receipt = dict(dry_run["receipt_preview"])
    receipt["dry_run"] = False
    receipt["timestamp"] = now
    receipt["reviewed_by"] = reviewer
    receipt["reviewed_at"] = now
    receipt["result"] = {
        "created_paths": [],
        "imported_count": len(dry_run["items"]),
        "external_api_called": False,
    }

    try:
        for preview in dry_run["items"]:
            item = discovered_by_id.get(preview["zettel_id"])
            if item is None:
                raise ArchiveServiceError(f"External import item disappeared before apply: {preview['source_path']}")
            target_path = archive_internal_path(root, preview["target_path"])
            target_path.parent.mkdir(parents=True, exist_ok=True)
            text = build_external_import_zettel_text(
                target_archive=dry_run["target_archive"],
                source_system=source,
                item=item,
                zettel_id=preview["zettel_id"],
                now=now,
                reviewed_by=reviewer,
            )
            with target_path.open("x", encoding="utf-8") as handle:
                handle.write(text)
            created_paths.append(target_path)
            created_relative_paths.append(preview["target_path"])

        receipt["result"]["created_paths"] = created_relative_paths + [receipt_relative]
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with receipt_path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(json_safe(receipt), indent=2, ensure_ascii=False, default=str) + "\n")
        created_paths.append(receipt_path)
    except Exception:
        for path in reversed(created_paths):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
        raise

    return {
        "ok": True,
        "dry_run": False,
        "source_system": source,
        "source_export": dry_run["source_export"],
        "target_archive": dry_run["target_archive"],
        "imported_count": len(dry_run["items"]),
        "reviewed_by": reviewer,
        "created_paths": created_relative_paths + [receipt_relative],
        "receipt_path": receipt_relative,
        "receipt": json_safe(receipt),
    }


def normalize_external_import_source(source_system: str) -> str:
    source = (source_system or "").strip().lower().replace("-", "_")
    aliases = {"gdrive": "google_drive", "google": "google_drive"}
    source = aliases.get(source, source)
    if source not in EXTERNAL_IMPORT_SOURCES:
        raise ArchiveServiceError("source_system must be one of: " + ", ".join(sorted(EXTERNAL_IMPORT_SOURCES)))
    return source


def discover_external_import_items(
    export_path: Path,
    source_system: str,
    *,
    limit: int,
    warnings: list[str],
) -> list[dict[str, Any]]:
    if export_path.is_file() and export_path.suffix.lower() in {".json", ".yml", ".yaml"}:
        return discover_external_import_manifest_items(export_path, source_system, limit=limit, warnings=warnings)
    if export_path.is_file():
        return external_import_item_from_file(export_path.parent, export_path, source_system, metadata=None, warnings=warnings)[:limit]
    items: list[dict[str, Any]] = []
    for path in sorted(export_path.rglob("*")):
        if len(items) >= limit:
            warnings.append(f"Import item limit reached: {limit}.")
            break
        if not path.is_file() or not is_path_within_root(path, export_path):
            continue
        if path.suffix.lower() not in EXTERNAL_IMPORT_EXTENSIONS:
            continue
        items.extend(external_import_item_from_file(export_path, path, source_system, metadata=None, warnings=warnings))
    return items


def discover_external_import_manifest_items(
    manifest_path: Path,
    source_system: str,
    *,
    limit: int,
    warnings: list[str],
) -> list[dict[str, Any]]:
    data = load_external_import_manifest_data(manifest_path)
    if not isinstance(data, dict):
        raise ArchiveServiceError("External import manifest must be a JSON/YAML object.")
    declared_source = data.get("source_system") or data.get("source")
    if declared_source and normalize_external_import_source(str(declared_source)) != source_system:
        raise ArchiveServiceError(f"External import manifest source does not match --source: {declared_source}")
    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        raise ArchiveServiceError("External import manifest must contain an items list.")

    root = manifest_path.parent
    items: list[dict[str, Any]] = []
    for raw_item in raw_items[:limit]:
        if not isinstance(raw_item, dict):
            warnings.append("Skipping manifest item that is not an object.")
            continue
        content = raw_item.get("content")
        if isinstance(content, str) and content.strip():
            items.append(external_import_item_from_content(root, source_system, raw_item, warnings))
            continue
        raw_path = raw_item.get("path") or raw_item.get("file")
        if not isinstance(raw_path, str):
            warnings.append("Skipping manifest item without path or content.")
            continue
        item_path = resolve_external_export_path(root, raw_path)
        items.extend(external_import_item_from_file(root, item_path, source_system, metadata=raw_item, warnings=warnings))
    if len(raw_items) > limit:
        warnings.append(f"Import item limit reached: {limit}.")
    return items


def load_external_import_manifest_data(manifest_path: Path) -> Any:
    if manifest_path.suffix.lower() == ".json":
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return load_yaml(manifest_path.read_text(encoding="utf-8"))


def resolve_external_export_path(root: Path, raw_path: str) -> Path:
    try:
        normalized = raw_path.replace("\\", "/").strip()
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ArchivePathError("External export item path must stay inside the export folder.")
        candidate = root.joinpath(*normalized.split("/")).resolve()
    except (OSError, ValueError) as exc:
        raise ArchiveServiceError(f"External export path is unsafe: {raw_path} ({exc})") from exc
    if not candidate.is_relative_to(root.resolve()):
        raise ArchiveServiceError(f"External export path escapes export folder: {raw_path}")
    return candidate


def external_import_item_from_file(
    export_root: Path,
    path: Path,
    source_system: str,
    *,
    metadata: dict[str, Any] | None,
    warnings: list[str],
) -> list[dict[str, Any]]:
    if path.suffix.lower() not in EXTERNAL_IMPORT_EXTENSIONS:
        warnings.append(f"Skipping unsupported external import file type: {path.name}.")
        return []
    if not path.is_file() or not is_path_within_root(path, export_root):
        warnings.append(f"Skipping unsafe external import path: {path}.")
        return []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        warnings.append(f"Skipping empty external import file: {path.name}.")
        return []
    relative = archive_relative_path(path, export_root)
    meta = metadata or {}
    title = str(meta.get("title") or extract_external_import_title(text, path))
    external_id = str(meta.get("external_id") or meta.get("id") or f"{source_system}:{relative}")
    return [
        {
            "external_id": external_id,
            "title": title,
            "body": text.rstrip() + "\n",
            "source_path": relative,
            "source_url": meta.get("url") or meta.get("source_url"),
            "created_at": meta.get("created_at"),
            "updated_at": meta.get("updated_at"),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
    ]


def external_import_item_from_content(
    export_root: Path,
    source_system: str,
    metadata: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    text = str(metadata.get("content") or "")
    title = str(metadata.get("title") or "Untitled external import")
    external_id = str(metadata.get("external_id") or metadata.get("id") or f"{source_system}:{safe_slug(title)}")
    if not text.strip():
        warnings.append(f"Manifest item has empty content: {external_id}.")
    return {
        "external_id": external_id,
        "title": title,
        "body": text.rstrip() + "\n",
        "source_path": str(metadata.get("path") or f"manifest:{external_id}"),
        "source_url": metadata.get("url") or metadata.get("source_url"),
        "created_at": metadata.get("created_at"),
        "updated_at": metadata.get("updated_at"),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def extract_external_import_title(text: str, path: Path) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or path.stem
        if stripped:
            return stripped[:80]
    return path.stem


def external_import_zettel_id(source_system: str, item: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        f"{source_system}\n{item.get('external_id')}\n{item.get('source_path')}\n{item.get('sha256')}".encode("utf-8")
    ).hexdigest()[:16]
    return f"zet_import_{source_system}_{digest}"


def build_external_import_zettel_text(
    *,
    target_archive: str,
    source_system: str,
    item: dict[str, Any],
    zettel_id: str,
    now: str,
    reviewed_by: str,
) -> str:
    frontmatter = {
        "id": zettel_id,
        "title": item["title"],
        "created_at": now,
        "updated_at": now,
        "archive_id": target_archive,
        "status": "draft",
        "kind": "imported_external_record",
        "facets": {
            "source_system": source_system,
            "external_id": item["external_id"],
        },
        "assets": [],
        "edges": [],
        "provenance": {
            "created_by": "cli:archive",
            "created_in": target_archive,
            "source": f"external_import:{source_system}",
            "derived_from": [
                {
                    "source_system": source_system,
                    "external_id": item["external_id"],
                    "source_path": item["source_path"],
                    "source_url": item.get("source_url"),
                    "sha256": item["sha256"],
                }
            ],
        },
        "visibility": default_private_visibility(),
        "promotion": {
            "stage": "imported_to_inbox",
            "ready_for_promotion": False,
            "reviewed_by": reviewed_by,
        },
        "external_import": {
            "source_system": source_system,
            "external_id": item["external_id"],
            "source_path": item["source_path"],
            "source_url": item.get("source_url"),
            "source_created_at": item.get("created_at"),
            "source_updated_at": item.get("updated_at"),
            "sha256": item["sha256"],
        },
    }
    return "---\n" + dump_yaml(frontmatter) + "---\n\n" + item["body"].rstrip() + "\n"


def build_zettel_scope_preview(
    root: Path,
    *,
    view_id: str,
    target_archive: str | None,
    allow_sensitive: bool,
    blockers: list[str],
    warnings: list[str],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    source_archive = read_archive_id(root)
    identity_doc = load_archive_identity(root)
    ownership = identity_doc.get("ownership") if isinstance(identity_doc.get("ownership"), dict) else {}
    view = resolve_view(root, view_id)
    selected = select_zettels_for_view(root, view)
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for zettel in selected:
        path = zettel["path"]
        frontmatter = zettel["frontmatter"]
        relative = archive_relative_path(path, root)
        sensitive_categories = sensitive_categories_for_frontmatter(frontmatter)
        item = {
            "path": relative,
            "zettel_id": frontmatter.get("id"),
            "title": frontmatter.get("title"),
            "sha256": sha256_path(path),
            "sensitive_categories": sensitive_categories,
        }
        if sensitive_categories and not allow_sensitive:
            item["reason"] = "sensitive_category_blocked_by_default"
            excluded.append(item)
            blockers.append(
                f"Sensitive zettel is excluded by default: {relative} ({', '.join(sensitive_categories)})."
            )
        else:
            if sensitive_categories:
                warnings.append(f"Sensitive zettel allowed by explicit flag: {relative}.")
            included.append(item)

    if not selected:
        warnings.append(f"View selected no canonical zettels: {view_id}.")

    scope_gate = {
        "unit": "view",
        "view_id": view_id,
        "source_view_path": view.get("source_path"),
        "target_archive": target_archive,
        "sensitive_categories_blocked_by_default": sorted(SENSITIVE_SHARE_CATEGORIES),
        "allow_sensitive": allow_sensitive,
        "included": included,
        "excluded": excluded,
    }
    ownership_gate = {
        "ownership_transfer": False,
        "current_owner": ownership.get("owner_id"),
        "current_owner_kind": ownership.get("owner_kind"),
        "operators": ownership.get("operators") if isinstance(ownership.get("operators"), list) else [],
        "receipt_required_for_transfer": True,
    }
    return source_archive, scope_gate, ownership_gate


def deferred_claimable_once_trust_gate(
    *,
    counterparty_id: str | None,
    counterparty_fingerprint: str | None,
) -> dict[str, Any]:
    return {
        "required": False,
        "ok": True,
        "status": "deferred_until_attestation",
        "counterparty_id": counterparty_id or None,
        "provided_fingerprint": counterparty_fingerprint or None,
        "matched": None,
        "verification_method": "archive_identity_fingerprint_at_attestation",
    }


def blocked_counterparty_bound_trust_gate() -> dict[str, Any]:
    return {
        "required": True,
        "ok": False,
        "status": "blocked",
        "counterparty_id": None,
        "provided_fingerprint": None,
        "matched": None,
        "verification_method": "archive_identity_fingerprint",
    }


def normalize_delegate_target_policy(target_policy: str | None) -> str:
    policy = (target_policy or DELEGATE_DEFAULT_TARGET_POLICY).strip() or DELEGATE_DEFAULT_TARGET_POLICY
    if policy not in DELEGATE_TARGET_POLICIES:
        raise ArchiveServiceError("target_policy must be one of: " + ", ".join(sorted(DELEGATE_TARGET_POLICIES)))
    return policy


def build_delegation_capability(
    *,
    source_archive: str,
    target_archive: str | None,
    view_id: str,
    target_policy: str,
) -> dict[str, Any]:
    target_slug = safe_slug(target_archive) if target_archive else "claimable-once"
    capability = {
        "capability_id": f"capability:delegate:{safe_slug(source_archive)}:{target_slug}:{safe_slug(view_id)}",
        "target_policy": target_policy,
        "claim_state": "unclaimed_preview",
        "spent_state": "not_spent_preview",
        "nonce": "<generated-on-real-delegate>",
        "binding_method": "attestation_claim_binding",
        "settlement_condition": {"mode": "none"},
    }
    if target_archive:
        capability["target_archive"] = target_archive
    if target_policy == DELEGATE_TARGET_POLICY_CLAIMABLE_ONCE:
        capability["claim_limit"] = 1
        capability["claimant"] = "attesting_archive_at_claim_time"
    return capability


def normalized_delegate_capability(
    delegate_receipt: dict[str, Any],
    *,
    source_archive: str,
    target_archive: str | None,
    blockers: list[str],
) -> dict[str, Any]:
    raw_capability = delegate_receipt.get("delegation_capability")
    capability = dict(raw_capability) if isinstance(raw_capability, dict) else {}
    target_policy = string_or_empty(capability.get("target_policy")) or DELEGATE_TARGET_POLICY_COUNTERPARTY_BOUND
    if target_policy not in DELEGATE_TARGET_POLICIES:
        blockers.append(f"Delegate receipt target_policy is unsupported: {target_policy}.")
        target_policy = DELEGATE_TARGET_POLICY_COUNTERPARTY_BOUND
    capability.setdefault(
        "capability_id",
        f"capability:delegate:{safe_slug(source_archive)}:{safe_slug(target_archive) if target_archive else 'legacy'}",
    )
    capability["target_policy"] = target_policy
    capability.setdefault("claim_state", "legacy_untracked")
    capability.setdefault("spent_state", "legacy_untracked")
    capability.setdefault("binding_method", "attestation_claim_binding")
    capability.setdefault("settlement_condition", {"mode": "none"})
    return capability


def build_claim_binding(
    *,
    archive_id: str,
    source_archive: str,
    target_archive: str | None,
    delegation_capability: dict[str, Any],
    target_archive_match: bool,
) -> dict[str, Any]:
    target_policy = delegation_capability.get("target_policy") or DELEGATE_TARGET_POLICY_COUNTERPARTY_BOUND
    binding = {
        "binding_method": "attestation_claim_binding",
        "capability_id": delegation_capability.get("capability_id"),
        "target_policy": target_policy,
        "claimed_by_archive": archive_id,
        "source_archive": source_archive,
        "target_archive": target_archive,
        "target_archive_match": target_archive_match,
        "settlement_condition": delegation_capability.get("settlement_condition", {"mode": "none"}),
    }
    if target_policy == DELEGATE_TARGET_POLICY_CLAIMABLE_ONCE:
        binding["claim_state_after_attestation"] = "claimed_preview"
        binding["spent_state_after_attestation"] = "spent_preview"
        binding["claim_limit"] = delegation_capability.get("claim_limit", 1)
    else:
        binding["claim_state_after_attestation"] = "bound_preview"
        binding["spent_state_after_attestation"] = "not_applicable"
    return binding


def share_archive_scope_dry_run(
    archive_root: Path | str,
    *,
    view_id: str,
    target_archive: str,
    counterparty_id: str | None = None,
    counterparty_fingerprint: str | None = None,
    allow_sensitive: bool = False,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    if not view_id:
        raise ArchiveServiceError("view_id is required.")
    if not target_archive.strip():
        raise ArchiveServiceError("target_archive is required.")

    blockers: list[str] = []
    warnings: list[str] = []
    source_archive, scope_gate, ownership_gate = build_zettel_scope_preview(
        root,
        view_id=view_id,
        target_archive=target_archive,
        allow_sensitive=allow_sensitive,
        blockers=blockers,
        warnings=warnings,
    )
    trust_gate = validate_counterparty_trust(
        root,
        counterparty_id=counterparty_id or target_archive,
        counterparty_fingerprint=counterparty_fingerprint,
        blockers=blockers,
    )

    proposed_receipt_path = (
        f"receipts/share/{safe_slug(source_archive)}__{safe_slug(target_archive)}__{safe_slug(view_id)}.share.json"
    )
    receipt_preview = {
        "receipt_id": f"receipt:share:{safe_slug(source_archive)}:{safe_slug(target_archive)}:{safe_slug(view_id)}",
        "receipt_path": proposed_receipt_path,
        "action": "share_archive_scope",
        "dry_run": True,
        "timestamp": "<execution-time>",
        "source_archive": source_archive,
        "target_archive": target_archive,
        "scope_gate": scope_gate,
        "trust_gate": trust_gate,
        "ownership_gate": ownership_gate,
        "blockers": blockers,
        "warnings": warnings,
    }

    return {
        "ok": not blockers,
        "dry_run": True,
        "source_archive": source_archive,
        "target_archive": target_archive,
        "view_id": view_id,
        "blockers": blockers,
        "warnings": warnings,
        "scope_gate": scope_gate,
        "trust_gate": trust_gate,
        "ownership_gate": ownership_gate,
        "proposed_receipt_path": proposed_receipt_path,
        "receipt_preview": receipt_preview,
        "would_change": [
            "create share workpack from selected view",
            f"write {proposed_receipt_path}",
        ],
    }


def delegate_zets_dry_run(
    archive_root: Path | str,
    *,
    view_id: str,
    target_archive: str | None = None,
    counterparty_id: str | None = None,
    counterparty_fingerprint: str | None = None,
    allow_sensitive: bool = False,
    target_policy: str | None = None,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    if not view_id:
        raise ArchiveServiceError("view_id is required.")
    resolved_target_policy = normalize_delegate_target_policy(target_policy)
    resolved_target_archive = (target_archive or "").strip() or None
    blockers: list[str] = []
    warnings: list[str] = []
    source_archive, scope_gate, ownership_gate = build_zettel_scope_preview(
        root,
        view_id=view_id,
        target_archive=resolved_target_archive,
        allow_sensitive=allow_sensitive,
        blockers=blockers,
        warnings=warnings,
    )

    if resolved_target_policy == DELEGATE_TARGET_POLICY_COUNTERPARTY_BOUND:
        if resolved_target_archive is None:
            blockers.append("target_archive is required for counterparty_bound delegation.")
            trust_gate = blocked_counterparty_bound_trust_gate()
        else:
            trust_gate = validate_counterparty_trust(
                root,
                counterparty_id=counterparty_id or resolved_target_archive,
                counterparty_fingerprint=counterparty_fingerprint,
                blockers=blockers,
            )
    else:
        trust_gate = deferred_claimable_once_trust_gate(
            counterparty_id=counterparty_id,
            counterparty_fingerprint=counterparty_fingerprint,
        )

    target_slug = safe_slug(resolved_target_archive) if resolved_target_archive else "claimable-once"
    proposed_receipt_path = (
        f"{DELEGATE_RECEIPTS_DIR}/"
        f"{safe_slug(source_archive)}__{target_slug}__{safe_slug(view_id)}.delegate.json"
    )
    receipt_path = archive_internal_path(root, proposed_receipt_path)
    if receipt_path.exists():
        blockers.append(f"Proposed delegate receipt already exists: {proposed_receipt_path}.")
    delegated_zets = [
        {
            "path": item.get("path"),
            "zettel_id": item.get("zettel_id"),
            "title": item.get("title"),
            "sha256": item.get("sha256"),
            "sensitive_categories": item.get("sensitive_categories", []),
        }
        for item in scope_gate["included"]
    ]
    scope_gate = dict(scope_gate)
    scope_gate["delegated_zets"] = delegated_zets
    scope_gate["target_policy"] = resolved_target_policy
    delegation_capability = build_delegation_capability(
        source_archive=source_archive,
        target_archive=resolved_target_archive,
        view_id=view_id,
        target_policy=resolved_target_policy,
    )
    delegate_receipt = {
        "receipt_id": f"receipt:delegate:{safe_slug(source_archive)}:{target_slug}:{safe_slug(view_id)}",
        "receipt_path": proposed_receipt_path,
        "action": "delegate_zet",
        "lifecycle_action": "delegate",
        "dry_run": True,
        "timestamp": "<execution-time>",
        "source_archive": source_archive,
        "target_archive": resolved_target_archive,
        "target_policy": resolved_target_policy,
        "view_id": view_id,
        "delegation_capability": delegation_capability,
        "settlement_condition": delegation_capability["settlement_condition"],
        "scope_gate": scope_gate,
        "trust_gate": trust_gate,
        "ownership_gate": ownership_gate,
        "delegated_zets": delegated_zets,
        "compatibility": {
            "protocol": "zet-sharing-dry-run/v0.2",
            "schema": "delegate-receipt/v0.2",
            "trust_profile": trust_gate.get("status"),
            "capability": f"delegate:{resolved_target_policy}",
        },
        "blockers": blockers,
        "warnings": warnings,
    }
    if resolved_target_policy == DELEGATE_TARGET_POLICY_COUNTERPARTY_BOUND and resolved_target_archive is not None:
        delegate_receipt["legacy_share_receipt_preview"] = {
            "receipt_id": f"receipt:share:{safe_slug(source_archive)}:{safe_slug(resolved_target_archive)}:{safe_slug(view_id)}",
            "receipt_path": f"receipts/share/{safe_slug(source_archive)}__{safe_slug(resolved_target_archive)}__{safe_slug(view_id)}.share.json",
            "action": "share_archive_scope",
            "dry_run": True,
            "timestamp": "<execution-time>",
            "source_archive": source_archive,
            "target_archive": resolved_target_archive,
            "scope_gate": scope_gate,
            "trust_gate": trust_gate,
            "ownership_gate": ownership_gate,
            "blockers": blockers,
            "warnings": warnings,
        }
    return {
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "delegate",
        "source_archive": source_archive,
        "target_archive": resolved_target_archive,
        "target_policy": resolved_target_policy,
        "view_id": view_id,
        "blockers": blockers,
        "warnings": warnings,
        "scope_gate": scope_gate,
        "trust_gate": trust_gate,
        "ownership_gate": ownership_gate,
        "delegated_zets": delegated_zets,
        "delegation_capability": delegation_capability,
        "settlement_condition": delegation_capability["settlement_condition"],
        "proposed_delegate_receipt_path": proposed_receipt_path,
        "delegate_receipt_preview": delegate_receipt,
        "proposed_receipt_path": proposed_receipt_path,
        "receipt_preview": delegate_receipt,
        "would_change": [
            "create delegate receipt for selected zets",
            f"write {proposed_receipt_path}",
        ],
    }


def issued_delegation_capability(capability: dict[str, Any]) -> dict[str, Any]:
    issued = json_safe(capability)
    target_policy = issued.get("target_policy") or DELEGATE_TARGET_POLICY_COUNTERPARTY_BOUND
    issued["nonce"] = f"nonce:{secrets.token_hex(16)}"
    issued["issue_state"] = "issued"
    issued["registry_state"] = {
        "claim_registry": "not_implemented",
        "spent_registry": "not_implemented",
        "revocation_registry": "not_implemented",
    }
    if target_policy == DELEGATE_TARGET_POLICY_CLAIMABLE_ONCE:
        issued["claim_state"] = "unclaimed_receipt_only"
        issued["spent_state"] = "not_spent_receipt_only"
    else:
        issued["claim_state"] = "counterparty_bound"
        issued["spent_state"] = "not_applicable"
    return issued


def delegate_zets(
    archive_root: Path | str,
    *,
    view_id: str,
    target_archive: str | None = None,
    counterparty_id: str | None = None,
    counterparty_fingerprint: str | None = None,
    allow_sensitive: bool = False,
    target_policy: str | None = None,
    reviewed_by: str,
) -> dict[str, Any]:
    reviewer = reviewed_by.strip()
    if not reviewer:
        raise ArchiveServiceError("Real zet delegation requires --reviewed-by.")

    root = require_existing_archive_root(archive_root)
    dry_run = delegate_zets_dry_run(
        root,
        view_id=view_id,
        target_archive=target_archive,
        counterparty_id=counterparty_id,
        counterparty_fingerprint=counterparty_fingerprint,
        allow_sensitive=allow_sensitive,
        target_policy=target_policy,
    )
    if dry_run["blockers"]:
        raise ArchiveServiceError("zet delegation blocked by dry-run: " + "; ".join(dry_run["blockers"]))

    receipt_relative = dry_run["proposed_delegate_receipt_path"]
    receipt_path = archive_internal_path(root, receipt_relative)
    if receipt_path.exists():
        raise ArchiveServiceError(f"Delegate receipt path already exists: {receipt_relative}.")

    now = datetime.now().astimezone().replace(microsecond=0).isoformat()
    receipt = json_safe(dry_run["delegate_receipt_preview"])
    capability = issued_delegation_capability(dry_run["delegation_capability"])
    receipt.update(
        {
            "dry_run": False,
            "timestamp": now,
            "reviewed_by": reviewer,
            "reviewed_at": now,
            "delegation_capability": capability,
            "settlement_condition": capability.get("settlement_condition", {"mode": "none"}),
            "result": {
                "created_paths": [receipt_relative],
                "status": "delegate_receipt_written",
            },
        }
    )
    if isinstance(receipt.get("compatibility"), dict):
        receipt["compatibility"]["protocol"] = "zet-sharing/v0.2"

    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(json_safe(receipt), indent=2, ensure_ascii=False, default=str) + "\n")

    return {
        "ok": True,
        "dry_run": False,
        "lifecycle_action": "delegate",
        "source_archive": dry_run["source_archive"],
        "target_archive": dry_run["target_archive"],
        "target_policy": dry_run["target_policy"],
        "view_id": dry_run["view_id"],
        "receipt_path": receipt_relative,
        "delegate_receipt_path": receipt_relative,
        "reviewed_by": reviewer,
        "blockers": [],
        "warnings": dry_run["warnings"],
        "scope_gate": dry_run["scope_gate"],
        "trust_gate": dry_run["trust_gate"],
        "ownership_gate": dry_run["ownership_gate"],
        "created_paths": [receipt_relative],
        "delegated_zets": dry_run["delegated_zets"],
        "delegation_capability": capability,
        "settlement_condition": capability.get("settlement_condition", {"mode": "none"}),
        "receipt": json_safe(receipt),
    }


def attest_zets_dry_run(
    archive_root: Path | str,
    *,
    delegate_receipt_path: str,
    counterparty_id: str | None = None,
    counterparty_fingerprint: str | None = None,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_id = read_archive_id(root)
    blockers: list[str] = []
    warnings: list[str] = []
    receipt_path = resolve_receipt_input_path(root, delegate_receipt_path)
    delegate_receipt = load_json_file(receipt_path)
    schema_issues = validate_schema(delegate_receipt, "delegate-receipt.schema.json")
    if schema_issues:
        blockers.extend(f"Delegate receipt schema issue: {issue.message}" for issue in schema_issues)

    source_archive = string_or_empty(delegate_receipt.get("source_archive"))
    target_archive = string_or_empty(delegate_receipt.get("target_archive")) or None
    delegation_capability = normalized_delegate_capability(
        delegate_receipt,
        source_archive=source_archive,
        target_archive=target_archive,
        blockers=blockers,
    )
    target_policy = delegation_capability.get("target_policy")
    target_archive_match = target_policy == DELEGATE_TARGET_POLICY_CLAIMABLE_ONCE or target_archive == archive_id
    if target_policy != DELEGATE_TARGET_POLICY_CLAIMABLE_ONCE and target_archive != archive_id:
        blockers.append(f"Delegate receipt target_archive does not match this archive: {target_archive} != {archive_id}.")
    trust_gate = validate_counterparty_trust(
        root,
        counterparty_id=counterparty_id or source_archive,
        counterparty_fingerprint=counterparty_fingerprint,
        blockers=blockers,
    )
    delegated_zets = normalized_delegated_zets(delegate_receipt.get("delegated_zets"), blockers)
    delegate_receipt_sha = sha256_path(receipt_path)
    delegate_receipt_id = string_or_empty(delegate_receipt.get("receipt_id")) or "unknown"
    proposed_receipt_path = (
        f"{ATTESTATION_RECEIPTS_DIR}/"
        f"{safe_slug(archive_id)}__{safe_slug(source_archive)}__{safe_slug(delegate_receipt_id)}.attestation.json"
    )
    claim_binding = build_claim_binding(
        archive_id=archive_id,
        source_archive=source_archive,
        target_archive=target_archive,
        delegation_capability=delegation_capability,
        target_archive_match=target_archive_match,
    )
    verification = {
        "delegate_receipt_schema": "passed" if not schema_issues else "blocked",
        "target_archive_match": target_archive_match,
        "target_policy": target_policy,
        "delegated_zets_count": len(delegated_zets),
        "hashes_valid": all(SHA256_RE.match(str(item.get("sha256") or "")) for item in delegated_zets),
    }
    attestation_receipt = {
        "receipt_id": f"receipt:attestation:{safe_slug(archive_id)}:{safe_slug(source_archive)}:{safe_slug(delegate_receipt_id)}",
        "receipt_path": proposed_receipt_path,
        "action": "attest_zet",
        "lifecycle_action": "attest",
        "dry_run": True,
        "timestamp": "<execution-time>",
        "attesting_archive": archive_id,
        "source_archive": source_archive,
        "target_archive": target_archive,
        "delegate_receipt": {
            "receipt_id": delegate_receipt.get("receipt_id"),
            "path": display_receipt_input_path(root, receipt_path),
            "sha256": delegate_receipt_sha,
            "action": delegate_receipt.get("action"),
            "lifecycle_action": delegate_receipt.get("lifecycle_action"),
        },
        "delegated_zets": delegated_zets,
        "delegation_capability": delegation_capability,
        "claim_binding": claim_binding,
        "settlement_condition": delegation_capability.get("settlement_condition", {"mode": "none"}),
        "trust_gate": trust_gate,
        "verification": verification,
        "blockers": blockers,
        "warnings": warnings,
    }
    return {
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "attest",
        "archive_id": archive_id,
        "source_archive": source_archive,
        "target_archive": target_archive,
        "blockers": blockers,
        "warnings": warnings,
        "trust_gate": trust_gate,
        "verification": verification,
        "delegated_zets": delegated_zets,
        "delegation_capability": delegation_capability,
        "claim_binding": claim_binding,
        "settlement_condition": delegation_capability.get("settlement_condition", {"mode": "none"}),
        "proposed_attestation_receipt_path": proposed_receipt_path,
        "attestation_receipt_preview": attestation_receipt,
        "would_change": [
            "record attestation receipt for delegated zets",
            f"write {proposed_receipt_path}",
        ],
    }


def anchor_zets_dry_run(
    archive_root: Path | str,
    *,
    attestation_receipt_path: str,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_id = read_archive_id(root)
    blockers: list[str] = []
    warnings: list[str] = []
    receipt_path = resolve_receipt_input_path(root, attestation_receipt_path)
    attestation_receipt = load_json_file(receipt_path)
    schema_issues = validate_schema(attestation_receipt, "attestation-receipt.schema.json")
    if schema_issues:
        blockers.extend(f"Attestation receipt schema issue: {issue.message}" for issue in schema_issues)

    attesting_archive = string_or_empty(attestation_receipt.get("attesting_archive"))
    target_archive = string_or_empty(attestation_receipt.get("target_archive"))
    source_archive = string_or_empty(attestation_receipt.get("source_archive"))
    claim_binding = attestation_receipt.get("claim_binding") if isinstance(attestation_receipt.get("claim_binding"), dict) else {}
    settlement_condition = (
        attestation_receipt.get("settlement_condition")
        if isinstance(attestation_receipt.get("settlement_condition"), dict)
        else {"mode": "none"}
    )
    if attesting_archive != archive_id:
        blockers.append(f"Attestation receipt attesting_archive does not match this archive: {attesting_archive} != {archive_id}.")
    if target_archive and target_archive != archive_id:
        blockers.append(f"Attestation receipt target_archive does not match this archive: {target_archive} != {archive_id}.")

    delegated_zets = normalized_delegated_zets(attestation_receipt.get("delegated_zets"), blockers)
    attestation_sha = sha256_path(receipt_path)
    attestation_receipt_id = string_or_empty(attestation_receipt.get("receipt_id")) or "unknown"
    proposed_anchor_path = (
        f"{ANCHOR_METADATA_DIR}/"
        f"{safe_slug(archive_id)}__{safe_slug(source_archive)}__{safe_slug(attestation_receipt_id)}.anchor.json"
    )
    anchored_zets = [
        {
            "foreign_zettel_id": item.get("zettel_id"),
            "foreign_path": item.get("path"),
            "title": item.get("title"),
            "sha256": item.get("sha256"),
            "local_status": "foreign_attested",
            "provenance": {
                "source_archive": source_archive,
                "attestation_receipt_id": attestation_receipt.get("receipt_id"),
                "claim_binding": claim_binding,
                "preserve_foreign_authorship": True,
            },
        }
        for item in delegated_zets
    ]
    anchor_metadata = {
        "anchor_id": f"anchor:{safe_slug(archive_id)}:{safe_slug(source_archive)}:{safe_slug(attestation_receipt_id)}",
        "path": proposed_anchor_path,
        "action": "anchor_zet",
        "lifecycle_action": "anchor",
        "dry_run": True,
        "timestamp": "<execution-time>",
        "archive_id": archive_id,
        "source_archive": source_archive,
        "attestation_receipt": {
            "receipt_id": attestation_receipt.get("receipt_id"),
            "path": display_receipt_input_path(root, receipt_path),
            "sha256": attestation_sha,
        },
        "claim_binding": claim_binding,
        "settlement_condition": settlement_condition,
        "anchored_zets": anchored_zets,
        "foreign_provenance_policy": {
            "preserve_source_archive": True,
            "preserve_foreign_zettel_ids": True,
            "do_not_claim_authorship": True,
            "requires_human_review_before_canonical_memory": True,
        },
        "local_meaning": {
            "status": "preview",
            "suggested_scope": "foreign_attested",
            "requires_anchor_review": True,
        },
        "status": "preview",
        "blockers": blockers,
        "warnings": warnings,
    }
    return {
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "anchor",
        "archive_id": archive_id,
        "source_archive": source_archive,
        "blockers": blockers,
        "warnings": warnings,
        "anchored_zets": anchored_zets,
        "claim_binding": claim_binding,
        "settlement_condition": settlement_condition,
        "proposed_anchor_metadata_path": proposed_anchor_path,
        "anchor_metadata_preview": anchor_metadata,
        "would_change": [
            "record anchor metadata for attested foreign zets",
            f"write {proposed_anchor_path}",
        ],
    }


SAFE_HTML_PROFILE_ID = "wom-safe-html/v0.1-draft"
SAFE_HTML_BLOCKED_TAGS = ("script", "iframe", "object", "embed")
SAFE_HTML_BLOCK_TAG_PATTERNS = {
    name: re.compile(rf"<\s*{name}\b", re.IGNORECASE) for name in SAFE_HTML_BLOCKED_TAGS
}
SAFE_HTML_JS_URL_PATTERN = re.compile(r"\bjavascript\s*:", re.IGNORECASE)
SAFE_HTML_INLINE_EVENT_PATTERN = re.compile(r"<\s*\w+[^>]*\son[a-z]+\s*=", re.IGNORECASE)


def check_safe_html_dry_run(
    archive_root: Path | str,
    *,
    zettel_id: str | None = None,
    relative_path: str | None = None,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_id = read_archive_id(root)
    if not zettel_id and not relative_path:
        raise ArchiveServiceError("Provide --zettel-id or --path.")

    path = resolve_zettel_path(root, zettel_id=zettel_id, relative_path=relative_path)
    source_path = archive_relative_path(path, root)
    text = path.read_text(encoding="utf-8")
    frontmatter, body = split_zettel_text(text)
    frontmatter = json_safe(frontmatter) if isinstance(frontmatter, dict) else {}

    blockers: list[str] = []
    warnings: list[str] = []
    detected_unsafe: list[str] = []

    for tag, pattern in SAFE_HTML_BLOCK_TAG_PATTERNS.items():
        if pattern.search(body):
            detected_unsafe.append(tag)
            blockers.append(
                f"Unsafe raw HTML element <{tag}> detected in zet body. "
                f"WOM Safe HTML Profile will not allow <{tag}> in canonical zets."
            )
    if SAFE_HTML_JS_URL_PATTERN.search(body):
        detected_unsafe.append("javascript_url")
        blockers.append(
            "Unsafe javascript: URL detected in zet body. "
            "WOM Safe HTML Profile will not allow the javascript: protocol in links."
        )
    if SAFE_HTML_INLINE_EVENT_PATTERN.search(body):
        detected_unsafe.append("inline_event_handler")
        blockers.append(
            "Inline event handler attribute detected in zet body (for example onclick=). "
            "WOM Safe HTML Profile will not allow inline event handlers."
        )

    if not body.strip():
        warnings.append("zet body is empty; future Safe HTML migration still expects structured content.")

    assets = frontmatter.get("assets") if isinstance(frontmatter.get("assets"), list) else []
    edges = frontmatter.get("edges") if isinstance(frontmatter.get("edges"), list) else []
    provenance = frontmatter.get("provenance") if isinstance(frontmatter.get("provenance"), dict) else {}
    derived_from = provenance.get("derived_from") if isinstance(provenance.get("derived_from"), list) else []
    object_id_references = [
        item.get("object_id")
        for item in assets
        if isinstance(item, dict) and isinstance(item.get("object_id"), str)
    ]

    html_profile_preview = {
        "profile_id": SAFE_HTML_PROFILE_ID,
        "status": "draft",
        "blocked_elements": list(SAFE_HTML_BLOCKED_TAGS),
        "blocked_attribute_pattern": "on*",
        "blocked_url_schemes": ["javascript:"],
        "allowlist_status": (
            "not yet defined; future WOM Safe HTML Profile will publish an explicit "
            "element/attribute allowlist before any real migration."
        ),
        "detected_unsafe_categories": detected_unsafe,
    }
    text_extraction_preview = {
        "method": "markdown_plain_text",
        "char_count": len(body),
        "line_count": body.count("\n") + 1 if body else 0,
        "word_count": len(body.split()),
        "has_yaml_frontmatter": bool(frontmatter),
    }
    source_reference_preview = {
        "method": "frontmatter_envelope_v0_2",
        "assets_count": len(assets),
        "edges_count": len(edges),
        "derived_from_count": len(derived_from),
        "object_id_references": object_id_references,
        "notes": (
            "WOM Safe HTML Profile prefers object_id, content hash, or manifest ref over raw provider URLs "
            "for canonical source identity."
        ),
    }

    return {
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "check_safe_html",
        "archive_id": archive_id,
        "source_path": source_path,
        "detected_format": "markdown_compatible",
        "proposed_profile": SAFE_HTML_PROFILE_ID,
        "blockers": blockers,
        "warnings": warnings,
        "html_profile_preview": html_profile_preview,
        "text_extraction_preview": text_extraction_preview,
        "source_reference_preview": source_reference_preview,
        "would_change": [],
    }


def onboarding_plan(
    target_root: Path | str,
    *,
    archive_type: str,
    archive_id: str,
    principal_id: str,
    principal_name: str | None = None,
    principal_kind: str | None = None,
    name: str | None = None,
    provider_profile: str | None = None,
) -> dict[str, Any]:
    resolved_type = (archive_type or "").strip()
    resolved_archive_id = (archive_id or "").strip()
    resolved_principal_id = (principal_id or "").strip()
    resolved_profile = provider_profile or "local_only"
    resolved_principal_kind = principal_kind or default_principal_kind_for_archive_type(resolved_type)
    resolved_target = Path(target_root).expanduser().resolve()
    blockers: list[str] = []
    warnings: list[str] = []

    if resolved_type not in {"personal", "family", "company"}:
        blockers.append("archive_type must be one of: personal, family, company.")
    if not resolved_archive_id:
        blockers.append("archive_id is required.")
    if not resolved_principal_id:
        blockers.append("principal_id is required.")
    if resolved_profile not in ONBOARDING_PROVIDER_PROFILES:
        blockers.append(
            "provider_profile must be one of: "
            + ", ".join(sorted(ONBOARDING_PROVIDER_PROFILES))
            + "."
        )
    if resolved_target.exists():
        if not resolved_target.is_dir():
            blockers.append(f"Target archive root must be a folder or absent: {resolved_target}.")
        elif any(resolved_target.iterdir()):
            blockers.append(f"Target archive folder must be empty or absent: {resolved_target}.")

    enabled_providers = provider_profile_enabled_providers(resolved_profile)
    disabled_providers = sorted(PROVIDER_TYPES - set(enabled_providers))
    return {
        "ok": not blockers,
        "dry_run": True,
        "action": "onboard_archive",
        "target_root": str(resolved_target),
        "archive_type": resolved_type,
        "archive_id": resolved_archive_id,
        "principal_id": resolved_principal_id,
        "principal_kind": resolved_principal_kind,
        "principal_name": principal_name or resolved_principal_id,
        "name": name or default_archive_name(resolved_type, principal_name, resolved_principal_id),
        "provider_profile": resolved_profile,
        "provider_profile_description": ONBOARDING_PROVIDER_PROFILES.get(resolved_profile, {}).get("description"),
        "provider_bindings": {
            "path": "provider-bindings.yml",
            "enabled_providers": enabled_providers,
            "disabled_providers": disabled_providers,
            "secret_values_allowed": False,
            "secret_refs_only": True,
        },
        "docker_runtime": {
            "strategy": "docker_first_hybrid",
            "container_os": "linux",
            "compose_file": "compose.yaml",
            "archive_mount": "/archives",
            "cli_service": "archive-cli",
            "mcp_service": "archive-mcp",
        },
        "keyring_guidance": [
            "Store long-lived provider secrets in KeePassXC, an OS keychain, or another external secret store.",
            "Keep archive files limited to env var names, role names, bucket names, repository names, and keyring entry references.",
            "Use provider-bindings.yml to describe external services without storing token, password, or database URL values.",
        ],
        "doctor_plan": {
            "command": f"archive doctor {resolved_target} --strict",
            "strict": True,
            "runs_after_approve": True,
        },
        "would_create": [
            "archive.yml",
            "archive-identity.yml",
            "provider-bindings.yml",
            "source-bindings.yml",
            "AGENTS.md",
            "zettel-kasten/",
            "inbox/",
            "zettels/",
            "views/",
            "source-maps/",
            "objects/manifests/files.jsonl",
            "db/schema.sql",
            "receipts/",
            ".gitignore",
        ],
        "blockers": blockers,
        "warnings": warnings,
    }


def real_pilot_plan(
    *,
    personal_root: Path | str,
    team_root: Path | str,
    personal_archive_id: str = "archive:personal:life",
    personal_principal_id: str = "person:me",
    personal_principal_name: str | None = None,
    team_archive_id: str = "archive:company:founding-team",
    team_principal_id: str = "team:founding-team",
    team_principal_name: str | None = None,
    personal_provider_profile: str = "object_storage_planned",
    team_provider_profile: str = "full_provider_plan",
) -> dict[str, Any]:
    personal_target = Path(personal_root).expanduser().resolve()
    team_target = Path(team_root).expanduser().resolve()
    blockers: list[str] = []
    warnings: list[str] = []

    separation_checks = archive_separation_checks(
        personal_target,
        team_target,
        personal_archive_id=personal_archive_id,
        team_archive_id=team_archive_id,
        personal_principal_id=personal_principal_id,
        team_principal_id=team_principal_id,
    )
    blockers.extend(separation_checks["blockers"])
    warnings.extend(separation_checks["warnings"])

    personal_onboarding = onboarding_plan(
        personal_target,
        archive_type="personal",
        archive_id=personal_archive_id,
        principal_id=personal_principal_id,
        principal_name=personal_principal_name,
        principal_kind="person",
        name=default_archive_name("personal", personal_principal_name, personal_principal_id),
        provider_profile=personal_provider_profile,
    )
    team_onboarding = onboarding_plan(
        team_target,
        archive_type="company",
        archive_id=team_archive_id,
        principal_id=team_principal_id,
        principal_name=team_principal_name,
        principal_kind="team",
        name=team_principal_name or "Founding Team Archive",
        provider_profile=team_provider_profile,
    )
    for plan in [personal_onboarding, team_onboarding]:
        blockers.extend(plan.get("blockers", []))
        warnings.extend(plan.get("warnings", []))

    archives = [
        pilot_archive_plan(
            role="personal_life",
            label="Personal life archive",
            onboarding=personal_onboarding,
        ),
        pilot_archive_plan(
            role="team",
            label="Team/company archive",
            onboarding=team_onboarding,
        ),
    ]
    return {
        "ok": not blockers,
        "dry_run": True,
        "action": "plan_real_archive_pilot",
        "safety_model": {
            "metadata_first": True,
            "content_read_default": False,
            "full_hash_default": False,
            "live_provider_api_default": False,
            "mcp_apply_tools": False,
            "secrets_in_versioned_files": False,
        },
        "archives": archives,
        "separation_gate": {
            "ok": not separation_checks["blockers"],
            "checks": separation_checks["checks"],
            "blockers": separation_checks["blockers"],
            "warnings": separation_checks["warnings"],
        },
        "first_30_minute_loop": [
            "Run pilot-plan and read the blockers/warnings.",
            "Create the personal archive with onboard --approve only if the plan is clean.",
            "Create the team archive separately; do not nest it inside the personal archive.",
            "Run preflight on each archive before registering real sources.",
            "Register one narrow source at a time with add-source --dry-run first.",
            "Run scan-source --dry-run and review the item count before any approved scan.",
            "Run doctor --strict, index, then search to confirm the map is useful.",
        ],
        "do_not_do_yet": [
            "Do not mount or scan an entire drive as the first source.",
            "Do not store tokens, database URLs, or passwords in archive files.",
            "Do not mix private personal sources into the team archive.",
            "Do not call live provider APIs from the default Docker runtime.",
        ],
        "blockers": unique_preserve_order(blockers),
        "warnings": unique_preserve_order(warnings),
    }


def pilot_archive_plan(*, role: str, label: str, onboarding: dict[str, Any]) -> dict[str, Any]:
    archive_root = onboarding["target_root"]
    suggestions = [pilot_source_suggestion(archive_root, item) for item in PILOT_SOURCE_PLANS[role]]
    return {
        "role": role,
        "label": label,
        "archive_type": onboarding["archive_type"],
        "archive_id": onboarding["archive_id"],
        "principal_id": onboarding["principal_id"],
        "target_root": archive_root,
        "provider_profile": onboarding["provider_profile"],
        "enabled_providers": onboarding["provider_bindings"]["enabled_providers"],
        "onboarding": onboarding,
        "suggested_sources": suggestions,
        "commands": {
            "onboard_dry_run": (
                "archive onboard "
                f"--target-root {archive_root} "
                f"--type {onboarding['archive_type']} "
                f"--archive-id {onboarding['archive_id']} "
                f"--principal-id {onboarding['principal_id']} "
                f"--provider-profile {onboarding['provider_profile']} "
                "--dry-run"
            ),
            "preflight": f"archive preflight {archive_root} --strict",
            "doctor": f"archive doctor {archive_root} --strict",
            "index": f"archive index {archive_root}",
        },
    }


def pilot_source_suggestion(archive_root: str, item: dict[str, str]) -> dict[str, Any]:
    source_id = item["source_id"]
    source_type = item["source_type"]
    root_ref = item["root_ref"]
    register_command = (
        f"archive add-source {archive_root} "
        f"--source-id {source_id} "
        f"--type {source_type} "
        f"--root-ref {root_ref} "
        "--dry-run"
    )
    scan_command = f"archive scan-source {archive_root} --source {source_id} --dry-run"
    if not root_ref.startswith("archive:"):
        scan_command += " --source-root <real-local-or-export-path>"
    return {
        "source_id": source_id,
        "source_type": source_type,
        "description": item["description"],
        "root_ref": root_ref,
        "metadata_only": True,
        "content_read": False,
        "full_hash_calculated": False,
        "live_provider_api_called": False,
        "register_command": register_command,
        "scan_command": scan_command,
    }


def archive_separation_checks(
    personal_root: Path,
    team_root: Path,
    *,
    personal_archive_id: str,
    team_archive_id: str,
    personal_principal_id: str,
    team_principal_id: str,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    roots_distinct = personal_root != team_root
    checks.append({"check": "archive_roots_distinct", "ok": roots_distinct})
    if not roots_distinct:
        blockers.append("Personal and team archive roots must be different folders.")

    roots_non_overlapping = not paths_overlap(personal_root, team_root)
    checks.append({"check": "archive_roots_not_nested", "ok": roots_non_overlapping})
    if not roots_non_overlapping:
        blockers.append("Personal and team archive roots must not be nested inside each other.")

    ids_distinct = personal_archive_id != team_archive_id
    checks.append({"check": "archive_ids_distinct", "ok": ids_distinct})
    if not ids_distinct:
        blockers.append("Personal and team archive ids must be different.")

    principals_distinct = personal_principal_id != team_principal_id
    checks.append({"check": "principal_ids_distinct", "ok": principals_distinct})
    if not principals_distinct:
        blockers.append("Personal owner/principal id and team principal id should be different.")

    if personal_root.name.lower() in {"team", "company", "work"}:
        warnings.append("Personal archive folder name looks like a team/work folder; double-check separation.")
    if team_root.name.lower() in {"personal", "life", "private"}:
        warnings.append("Team archive folder name looks personal/private; double-check separation.")

    return {"checks": checks, "blockers": blockers, "warnings": warnings}


def paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def default_principal_kind_for_archive_type(archive_type: str) -> str:
    if archive_type == "family":
        return "family"
    if archive_type == "company":
        return "company"
    return "person"


def default_archive_name(archive_type: str, principal_name: str | None, principal_id: str) -> str:
    display = principal_name or principal_id or archive_type.title()
    if archive_type == "family":
        return f"{display} Family Archive"
    if archive_type == "company":
        return f"{display} Company Archive"
    return f"{display} Personal Archive"


def provider_profile_enabled_providers(provider_profile: str | None) -> list[str]:
    profile = provider_profile or "local_only"
    config = ONBOARDING_PROVIDER_PROFILES.get(profile)
    if not isinstance(config, dict):
        return []
    return [provider for provider in config.get("enabled_providers", []) if provider in PROVIDER_TYPES]


def provider_bindings_summary(archive_root: Path | str) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_id = read_archive_id(root)
    bindings_doc = load_provider_bindings(root)
    bindings = provider_bindings_list(bindings_doc)
    providers = [summarize_provider_binding(binding) for binding in bindings]
    change_plan = build_provider_change_plan(
        root,
        source_archive=archive_id,
        previous_owner=None,
        new_owner=None,
        new_owner_archive=None,
        operators_after=[],
        reason=None,
    )
    return {
        "ok": True,
        "archive_id": archive_id,
        "bindings_present": archive_internal_path(root, "provider-bindings.yml").is_file(),
        "provider_bindings_path": "provider-bindings.yml",
        "binding_count": len(bindings),
        "providers": providers,
        "provider_change_plan": change_plan,
    }


def load_provider_bindings(archive_root: Path) -> dict[str, Any]:
    path = archive_internal_path(archive_root, "provider-bindings.yml")
    if not path.is_file():
        return {
            "version": "provider-bindings/v0.1",
            "archive_id": read_archive_id(archive_root),
            "bindings": [],
        }
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ArchiveServiceError("provider-bindings.yml must be a YAML object.")
    return json_safe(data)


def provider_bindings_list(bindings_doc: dict[str, Any]) -> list[dict[str, Any]]:
    bindings = bindings_doc.get("bindings") or []
    if not isinstance(bindings, list):
        return []
    return [item for item in bindings if isinstance(item, dict)]


def summarize_provider_binding(binding: dict[str, Any]) -> dict[str, Any]:
    provider = str(binding.get("provider") or "unknown")
    resource = binding.get("resource") if isinstance(binding.get("resource"), dict) else {}
    auth = binding.get("auth") if isinstance(binding.get("auth"), dict) else {}
    owner_mapping = binding.get("owner_mapping") if isinstance(binding.get("owner_mapping"), dict) else {}
    return {
        "binding_id": binding.get("binding_id"),
        "provider": provider,
        "enabled": binding.get("enabled") is not False,
        "purpose": binding.get("purpose"),
        "resource": resource,
        "auth_refs": auth,
        "owner_mapping": owner_mapping,
        "manual_required": True,
        "reference": PROVIDER_REFERENCE_URLS.get(provider),
    }


def build_provider_change_plan(
    archive_root: Path,
    *,
    source_archive: str,
    previous_owner: Any,
    new_owner: str | None,
    new_owner_archive: str | None,
    operators_after: list[str],
    reason: str | None,
) -> dict[str, Any]:
    bindings_doc = load_provider_bindings(archive_root)
    bindings = provider_bindings_list(bindings_doc)
    warnings: list[str] = []
    if not archive_internal_path(archive_root, "provider-bindings.yml").is_file():
        warnings.append("provider-bindings.yml is missing; external provider changes cannot be planned.")

    provider_steps = [
        provider_change_step(
            binding,
            source_archive=source_archive,
            previous_owner=previous_owner,
            new_owner=new_owner,
            new_owner_archive=new_owner_archive,
            operators_after=operators_after,
            reason=reason,
        )
        for binding in bindings
        if binding.get("enabled") is not False
    ]
    status = "manual_required" if provider_steps else "not_configured"
    return {
        "action": "provider_access_change_plan",
        "status": status,
        "external_changes_are_manual": True,
        "source_archive": source_archive,
        "previous_owner": previous_owner,
        "new_owner": new_owner,
        "new_owner_archive": new_owner_archive,
        "operators_after": operators_after,
        "binding_count": len(provider_steps),
        "providers": provider_steps,
        "warnings": warnings,
    }


def provider_change_step(
    binding: dict[str, Any],
    *,
    source_archive: str,
    previous_owner: Any,
    new_owner: str | None,
    new_owner_archive: str | None,
    operators_after: list[str],
    reason: str | None,
) -> dict[str, Any]:
    provider = str(binding.get("provider") or "unknown")
    resource = binding.get("resource") if isinstance(binding.get("resource"), dict) else {}
    auth = binding.get("auth") if isinstance(binding.get("auth"), dict) else {}
    owner_mapping = binding.get("owner_mapping") if isinstance(binding.get("owner_mapping"), dict) else {}
    return {
        "binding_id": binding.get("binding_id"),
        "provider": provider,
        "status": "manual_required",
        "automated": False,
        "source_archive": source_archive,
        "previous_owner": previous_owner,
        "new_owner": new_owner,
        "new_owner_archive": new_owner_archive,
        "operators_after": operators_after,
        "reason": reason,
        "resource": resource,
        "auth_refs": auth,
        "owner_mapping": owner_mapping,
        "required_actions": provider_required_actions(provider, owner_mapping),
        "reference": PROVIDER_REFERENCE_URLS.get(provider),
    }


def provider_required_actions(provider: str, owner_mapping: dict[str, Any]) -> list[str]:
    if provider == "github":
        return [
            "Review GitHub organization, repository, team, and collaborator roles for the archive repository.",
            "Grant the new owner/operator team the intended repository role before relying on the transfer.",
            "Remove or reduce previous owner/operator access after the transfer receipt is verified.",
            "Rotate deploy keys or tokens that were tied to the previous owner.",
        ]
    if provider == "object_storage":
        return [
            "Review the external object storage bucket/container, IAM policy, lifecycle policy, and billing owner.",
            "Create or rotate scoped credentials outside the archive and keep only env/token refs in provider-bindings.yml.",
            "Run a provider-native dry-run/list check before uploading any objet files.",
            "Do not upload, sync, copy, or hash source/original files from this provider binding step.",
        ]
    if provider == "cloudflare_r2":
        return [
            "Review the Cloudflare account, R2 bucket, and API token access policy.",
            "Create or rotate scoped R2 credentials for the new owner/operator.",
            "Update the external secret store entry referenced by the configured env vars.",
            "Revoke previous credentials only after object sync and restore checks pass.",
        ]
    if provider == "backblaze_b2":
        return [
            "Review Backblaze B2 bucket access and application key capabilities.",
            "Create or rotate a bucket-scoped application key for the new owner/operator.",
            "Update rclone/restic or app env refs outside the archive.",
            "Revoke previous application keys after verification.",
        ]
    if provider == "neon":
        return [
            "Review Neon project, branch, database, and role ownership outside the archive.",
            "Create or rotate the Postgres role or connection string for shared coordination use.",
            "Use a branch for rehearsal or spin-out verification before production changes.",
            "Update the external secret store entry referenced by the database URL env var.",
        ]
    if provider == "external_ssd":
        return [
            "Confirm the physical drive label and backup set to hand over.",
            "Record custody transfer outside the archive receipt if the drive changes hands.",
            "Verify checksums after copying or receiving the physical backup.",
        ]
    if provider == "rclone":
        return [
            "Review the rclone remote name and config location outside the archive.",
            "Create or update the remote credentials in the external secret store.",
            "Run a dry-run sync before enabling writes for the new owner/operator.",
        ]
    if provider == "restic":
        return [
            "Review the restic repository and password env refs outside the archive.",
            "Rotate repository credentials if they were tied to the previous owner.",
            "Run restic check after handover.",
        ]
    if provider == "keepassxc":
        entries = owner_mapping.get("entry_refs") if isinstance(owner_mapping.get("entry_refs"), list) else []
        suffix = f" Entries: {', '.join(map(str, entries))}." if entries else ""
        return [
            "Review KeePassXC entries referenced by this archive binding." + suffix,
            "Move, share, or rotate secrets in KeePassXC outside the archive.",
            "Never write copied secret values into archive files or receipts.",
        ]
    return ["Review this provider manually because WOM-kit does not automate external account changes."]


def github_repository_setup_plan(
    archive_root: Path | str,
    *,
    profile_id: str | None = None,
    profile_slug: str | None = None,
    github_owner: str | None = None,
    github_account_ref: str | None = None,
    repo_name: str | None = None,
    visibility: str = GITHUB_REPOSITORY_DEFAULT_VISIBILITY,
    remote_protocol: str = GITHUB_REPOSITORY_DEFAULT_REMOTE_PROTOCOL,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_config = read_archive_config(root)
    archive_id = str(archive_config.get("archive_id") or "")
    blockers: list[str] = []
    warnings: list[str] = []

    resolved_profile_id = (profile_id or "").strip()
    if not resolved_profile_id:
        blockers.append("profile_id is required.")

    resolved_slug = resolve_github_profile_slug(resolved_profile_id, profile_slug, blockers, warnings)
    resolved_repo_name = resolve_github_repo_name(repo_name, resolved_slug, blockers)
    resolved_visibility = (visibility or GITHUB_REPOSITORY_DEFAULT_VISIBILITY).strip().lower()
    resolved_remote_protocol = (remote_protocol or GITHUB_REPOSITORY_DEFAULT_REMOTE_PROTOCOL).strip().lower()
    resolved_owner = (github_owner or "").strip()
    resolved_account_ref = (github_account_ref or "").strip()

    if not archive_id:
        blockers.append("archive.yml does not contain archive_id.")
    if resolved_visibility not in GITHUB_REPOSITORY_ALLOWED_VISIBILITIES:
        blockers.append("visibility must be private.")
    if resolved_remote_protocol not in GITHUB_REPOSITORY_REMOTE_PROTOCOLS:
        blockers.append("remote_protocol must be ssh or https.")
    if not resolved_owner:
        blockers.append("github_owner is required.")
    elif not safe_github_owner(resolved_owner):
        blockers.append("github_owner must be a GitHub user or org name using ASCII letters, numbers, and hyphens only.")
    if not resolved_account_ref:
        blockers.append("github_account_ref is required.")
    elif not safe_github_account_ref(resolved_account_ref):
        blockers.append("github_account_ref must be a safe account reference, not an email, URL, token, or path.")

    provider_binding = build_github_provider_binding(
        archive_id=archive_id,
        profile_id=resolved_profile_id,
        profile_slug=resolved_slug,
        github_owner=resolved_owner,
        github_account_ref=resolved_account_ref,
        repo_name=resolved_repo_name,
        visibility=resolved_visibility,
        remote_protocol=resolved_remote_protocol,
    )
    local_profile_preview = build_github_local_profile_preview(
        profile_id=resolved_profile_id,
        profile_slug=resolved_slug,
        github_owner=resolved_owner,
        github_account_ref=resolved_account_ref,
        repo_name=resolved_repo_name,
        visibility=resolved_visibility,
        remote_protocol=resolved_remote_protocol,
    )
    receipt_path = github_provider_setup_receipt_path(resolved_repo_name)
    manual_steps = github_repository_manual_steps(resolved_owner, resolved_repo_name, resolved_visibility, resolved_remote_protocol)
    receipt_preview = build_github_provider_setup_receipt(
        archive_id=archive_id,
        profile_id=resolved_profile_id,
        profile_slug=resolved_slug,
        github_owner=resolved_owner,
        github_account_ref=resolved_account_ref,
        repo_name=resolved_repo_name,
        visibility=resolved_visibility,
        remote_protocol=resolved_remote_protocol,
        receipt_path=receipt_path,
        reviewed_by="<required-on-approve>",
        timestamp="<execution-time>",
        dry_run=True,
        manual_steps=manual_steps,
    )
    provider_doc = load_provider_bindings(root)
    if provider_doc.get("archive_id") and provider_doc.get("archive_id") != archive_id:
        blockers.append("provider-bindings.yml archive_id must match archive.yml archive_id.")
    if archive_internal_path(root, receipt_path).exists():
        blockers.append(f"Proposed provider setup receipt already exists: {receipt_path}.")

    provider_action = "update provider-bindings.yml" if archive_internal_path(root, "provider-bindings.yml").exists() else "create provider-bindings.yml"
    would_change = [provider_action, f"write {receipt_path}"]
    return {
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "github_repository_setup_plan",
        "archive_id": archive_id,
        "profile_id": resolved_profile_id or None,
        "profile_slug": resolved_slug or None,
        "proposed_repo_name": resolved_repo_name or None,
        "proposed_visibility": resolved_visibility,
        "proposed_remote_protocol": resolved_remote_protocol,
        "github_owner": resolved_owner or None,
        "github_account_ref": resolved_account_ref or None,
        "provider_binding_preview": json_safe(provider_binding),
        "local_profile_preview": json_safe(local_profile_preview),
        "provider_setup_receipt_preview": json_safe(receipt_preview),
        "manual_steps": manual_steps,
        "blockers": unique_preserve_order(blockers),
        "warnings": unique_preserve_order(warnings),
        "would_change": would_change,
    }


def approve_github_repository_setup_plan(
    archive_root: Path | str,
    *,
    reviewed_by: str,
    write_local_profile: bool = False,
    profile_id: str | None = None,
    profile_slug: str | None = None,
    github_owner: str | None = None,
    github_account_ref: str | None = None,
    repo_name: str | None = None,
    visibility: str = GITHUB_REPOSITORY_DEFAULT_VISIBILITY,
    remote_protocol: str = GITHUB_REPOSITORY_DEFAULT_REMOTE_PROTOCOL,
) -> dict[str, Any]:
    reviewer = (reviewed_by or "").strip()
    if not reviewer:
        raise ArchiveServiceError("GitHub repository setup approval requires reviewed_by.")
    validate_github_safe_metadata(reviewer, "reviewed_by")

    root = require_existing_archive_root(archive_root)
    plan = github_repository_setup_plan(
        root,
        profile_id=profile_id,
        profile_slug=profile_slug,
        github_owner=github_owner,
        github_account_ref=github_account_ref,
        repo_name=repo_name,
        visibility=visibility,
        remote_protocol=remote_protocol,
    )
    if plan["blockers"]:
        raise ArchiveServiceError("GitHub repository setup blocked by dry-run: " + "; ".join(plan["blockers"]))

    now = datetime.now().astimezone().replace(microsecond=0).isoformat()
    provider_path = archive_internal_path(root, "provider-bindings.yml")
    receipt_relative = plan["provider_setup_receipt_preview"]["receipt_path"]
    receipt_path = archive_internal_path(root, receipt_relative)
    if receipt_path.exists():
        raise ArchiveServiceError(f"Proposed provider setup receipt already exists: {receipt_relative}.")

    provider_doc = load_provider_bindings(root)
    if provider_doc.get("archive_id") and provider_doc.get("archive_id") != plan["archive_id"]:
        raise ArchiveServiceError("provider-bindings.yml archive_id must match archive.yml archive_id.")
    provider_doc["version"] = "provider-bindings/v0.1"
    provider_doc["archive_id"] = plan["archive_id"]
    provider_doc["bindings"] = upsert_github_provider_binding(
        provider_bindings_list(provider_doc),
        plan["provider_binding_preview"],
    )

    receipt = build_github_provider_setup_receipt(
        archive_id=plan["archive_id"],
        profile_id=plan["profile_id"],
        profile_slug=plan["profile_slug"],
        github_owner=plan["github_owner"],
        github_account_ref=plan["github_account_ref"],
        repo_name=plan["proposed_repo_name"],
        visibility=plan["proposed_visibility"],
        remote_protocol=plan["proposed_remote_protocol"],
        receipt_path=receipt_relative,
        reviewed_by=reviewer,
        timestamp=now,
        dry_run=False,
        manual_steps=plan["manual_steps"],
    )
    receipt["result"] = {
        "changed_paths": ["provider-bindings.yml", receipt_relative],
        "github_api_called": False,
        "github_repository_created": False,
        "git_remote_configured": False,
        "git_push_performed": False,
    }

    changed_paths = ["provider-bindings.yml", receipt_relative]
    local_profile: dict[str, Any] | None = None
    local_profile_path: Path | None = None
    local_profile_relative = "profiles/local/github-accounts.local.yml"
    if write_local_profile:
        ensure_local_profile_gitignore(root)
        local_profile_path = archive_internal_path(root, local_profile_relative)
        local_profile = merge_github_local_profile(
            load_local_github_profile(local_profile_path),
            plan["local_profile_preview"]["entry"],
        )
        changed_paths.append(local_profile_relative)
        receipt["result"]["changed_paths"] = changed_paths

    provider_original_text = provider_path.read_text(encoding="utf-8") if provider_path.exists() else None
    local_profile_original_text = (
        local_profile_path.read_text(encoding="utf-8")
        if write_local_profile and local_profile_path is not None and local_profile_path.exists()
        else None
    )
    created_receipt = False

    def restore_text(path: Path, original_text: str | None) -> None:
        if original_text is None:
            if path.exists():
                path.unlink()
            return
        write_text_atomic(path, original_text)

    try:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with receipt_path.open("x", encoding="utf-8") as handle:
            created_receipt = True
            handle.write(json.dumps(json_safe(receipt), indent=2, ensure_ascii=False, default=str) + "\n")
        provider_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(provider_path, dump_yaml(json_safe(provider_doc)))
        if write_local_profile and local_profile_path is not None and local_profile is not None:
            local_profile_path.parent.mkdir(parents=True, exist_ok=True)
            write_text_atomic(local_profile_path, dump_yaml(json_safe(local_profile)))
    except Exception:
        if created_receipt and receipt_path.exists():
            try:
                receipt_path.unlink()
            except OSError:
                pass
        try:
            restore_text(provider_path, provider_original_text)
        except OSError:
            pass
        if write_local_profile and local_profile_path is not None:
            try:
                restore_text(local_profile_path, local_profile_original_text)
            except OSError:
                pass
        raise

    return {
        "ok": True,
        "dry_run": False,
        "lifecycle_action": "github_repository_setup_plan",
        "archive_id": plan["archive_id"],
        "profile_id": plan["profile_id"],
        "profile_slug": plan["profile_slug"],
        "proposed_repo_name": plan["proposed_repo_name"],
        "proposed_visibility": plan["proposed_visibility"],
        "proposed_remote_protocol": plan["proposed_remote_protocol"],
        "github_owner": plan["github_owner"],
        "github_account_ref": plan["github_account_ref"],
        "provider_binding": json_safe(plan["provider_binding_preview"]),
        "receipt_path": receipt_relative,
        "provider_setup_receipt": json_safe(receipt),
        "local_profile_path": local_profile_relative if write_local_profile else None,
        "manual_steps": plan["manual_steps"],
        "changed_paths": changed_paths,
        "github_api_called": False,
        "github_repository_created": False,
        "git_remote_configured": False,
        "git_push_performed": False,
        "warnings": plan["warnings"],
    }


def resolve_github_profile_slug(
    profile_id: str,
    explicit_slug: str | None,
    blockers: list[str],
    warnings: list[str],
) -> str:
    raw = (explicit_slug or "").strip()
    if not raw:
        candidate = profile_id.rsplit(":", 1)[-1].strip() if profile_id else ""
        if not candidate:
            blockers.append("profile_slug is required when profile_id cannot provide an ASCII slug.")
            return ""
        if not candidate.isascii():
            blockers.append("Non-ASCII profile labels or ids require explicit --profile-slug.")
            return ""
        raw = candidate
        warnings.append("profile_slug was derived from profile_id; pass --profile-slug for replayable setup.")
    if not safe_github_profile_slug_input(raw):
        blockers.append("profile_slug must use ASCII letters, numbers, and hyphens only, and must not look like a path, URL, email, or secret.")
        return ""
    normalized = re.sub(r"-{2,}", "-", raw).strip("-")
    if not normalized:
        blockers.append("profile_slug must not be empty after normalization.")
        return ""
    return normalized


def safe_github_profile_slug_input(value: str) -> bool:
    text = value.strip()
    if not text or not text.isascii():
        return False
    if any(item in text for item in ["@", "/", "\\", ":", "#", "?", "&", "="]):
        return False
    if text.lower().startswith(("http-", "https-", "www-")):
        return False
    if GITHUB_SECRET_LIKE_RE.search(text):
        return False
    return bool(GITHUB_PROFILE_SLUG_RE.match(text))


def resolve_github_repo_name(repo_name: str | None, profile_slug: str, blockers: list[str]) -> str:
    proposed = (repo_name or "").strip()
    if not proposed and profile_slug:
        proposed = f"{GITHUB_REPOSITORY_NAME_PREFIX}{profile_slug}"
    if not safe_github_repo_name(proposed):
        blockers.append(
            "repo_name must start with zettel-kasten-, use only ASCII letters, numbers, and hyphens, "
            "avoid spaces/slashes/URL fragments, and be at most 80 characters."
        )
        return proposed
    return proposed


def safe_github_repo_name(value: str) -> bool:
    text = value.strip()
    if not text or not text.isascii():
        return False
    if len(text) > 80:
        return False
    if not text.lower().startswith(GITHUB_REPOSITORY_NAME_PREFIX):
        return False
    if any(item in text for item in [" ", "/", "\\", ":", "#", "?", "&", "=", "@"]):
        return False
    if GITHUB_SECRET_LIKE_RE.search(text):
        return False
    return bool(GITHUB_REPOSITORY_NAME_RE.match(text))


def safe_github_owner(value: str) -> bool:
    text = value.strip()
    if not text or not text.isascii():
        return False
    if any(item in text for item in ["@", "/", "\\", ":", "#", "?", "&", "="]):
        return False
    if GITHUB_SECRET_LIKE_RE.search(text):
        return False
    return bool(GITHUB_OWNER_RE.match(text)) and "--" not in text


def safe_github_account_ref(value: str) -> bool:
    text = value.strip()
    if not text or not text.isascii():
        return False
    if "@" in text or "://" in text or "\\" in text or "/" in text or "#" in text or "?" in text:
        return False
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", text) and not text.lower().startswith("github:account:"):
        return False
    if "." in text and not text.lower().startswith("github:account:"):
        return False
    if GITHUB_SECRET_LIKE_RE.search(text):
        return False
    return bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,119}$", text))


def validate_github_safe_metadata(value: str, field_name: str) -> None:
    text = value.strip()
    if contains_forbidden_location_reference(text) or "@" in text or "://" in text or GITHUB_SECRET_LIKE_RE.search(text):
        raise ArchiveServiceError(f"{field_name} must be a safe actor/reference, not a path, URL, email, token, or secret.")


def build_github_provider_binding(
    *,
    archive_id: str,
    profile_id: str,
    profile_slug: str,
    github_owner: str,
    github_account_ref: str,
    repo_name: str,
    visibility: str,
    remote_protocol: str,
) -> dict[str, Any]:
    return {
        "binding_id": f"github:{repo_name}",
        "provider": "github",
        "enabled": True,
        "purpose": "archive_repository_metadata_and_manual_setup_plan",
        "resource": {
            "owner": github_owner,
            "repo": repo_name,
            "visibility": visibility,
            "remote_protocol": remote_protocol,
        },
        "auth": {
            "method": "gh_cli_or_token_ref",
            "token_env": "GITHUB_TOKEN",
            "account_ref": github_account_ref,
        },
        "owner_mapping": {
            "archive_id": archive_id,
            "profile_id": profile_id,
            "profile_slug": profile_slug,
        },
        "notes": "Manual GitHub repository setup plan only; WOM-kit does not create repositories or configure remotes.",
    }


def build_github_local_profile_preview(
    *,
    profile_id: str,
    profile_slug: str,
    github_owner: str,
    github_account_ref: str,
    repo_name: str,
    visibility: str,
    remote_protocol: str,
) -> dict[str, Any]:
    entry = {
        "profile_id": profile_id,
        "profile_slug": profile_slug,
        "github_owner": github_owner,
        "github_account_ref": github_account_ref,
        "repo_name": repo_name,
        "visibility": visibility,
        "remote_protocol": remote_protocol,
        "token_env": "GITHUB_TOKEN",
    }
    return {
        "path": "profiles/local/github-accounts.local.yml",
        "ignored_by_default": True,
        "entry": entry,
    }


def github_repository_manual_steps(
    github_owner: str,
    repo_name: str,
    visibility: str,
    remote_protocol: str,
) -> list[str]:
    remote_hint = "SSH" if remote_protocol == "ssh" else "HTTPS"
    return [
        f"Manually create a {visibility} GitHub repository named {repo_name} under {github_owner}.",
        f"Configure repository access and branch protection in GitHub before connecting this archive.",
        f"Only after human review, configure the local git remote outside this planner using {remote_hint}.",
        "Run doctor --strict after local metadata approval.",
    ]


def github_provider_setup_receipt_path(repo_name: str) -> str:
    safe_repo = safe_slug(repo_name or "github-repository")
    return f"{GITHUB_REPOSITORY_SETUP_RECEIPTS_DIR}/{safe_repo}.github-repository-setup.json"


def build_github_provider_setup_receipt(
    *,
    archive_id: str,
    profile_id: str,
    profile_slug: str,
    github_owner: str,
    github_account_ref: str,
    repo_name: str,
    visibility: str,
    remote_protocol: str,
    receipt_path: str,
    reviewed_by: str,
    timestamp: str,
    dry_run: bool,
    manual_steps: list[str],
) -> dict[str, Any]:
    return {
        "receipt_id": f"receipt:provider-setup:github:{repo_name}",
        "receipt_path": receipt_path,
        "lifecycle_action": "github_repository_setup_plan",
        "provider": "github",
        "dry_run": dry_run,
        "timestamp": timestamp,
        "archive_id": archive_id,
        "profile_id": profile_id,
        "profile_slug": profile_slug,
        "resource": {
            "owner": github_owner,
            "repo": repo_name,
            "visibility": visibility,
            "remote_protocol": remote_protocol,
        },
        "auth": {
            "method": "gh_cli_or_token_ref",
            "token_env": "GITHUB_TOKEN",
            "account_ref": github_account_ref,
        },
        "reviewed_by": reviewed_by,
        "external_actions": {
            "github_api_called": False,
            "github_repository_created": False,
            "oauth_started": False,
            "gh_cli_called": False,
            "git_remote_configured": False,
            "git_push_performed": False,
        },
        "manual_steps": manual_steps,
    }


def upsert_github_provider_binding(bindings: list[dict[str, Any]], new_binding: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    replaced = False
    new_key = github_binding_compare_key(new_binding)
    for binding in bindings:
        if github_binding_compare_key(binding) == new_key:
            result.append(json_safe(new_binding))
            replaced = True
        else:
            result.append(json_safe(binding))
    if not replaced:
        result.append(json_safe(new_binding))
    return result


def github_binding_compare_key(binding: dict[str, Any]) -> tuple[str, str, str]:
    resource = binding.get("resource") if isinstance(binding.get("resource"), dict) else {}
    owner = str(resource.get("owner") or resource.get("org") or "").lower()
    repo = str(resource.get("repo") or "").lower()
    binding_id = str(binding.get("binding_id") or "").lower()
    return (str(binding.get("provider") or "").lower(), owner, repo or binding_id)


def ensure_local_profile_gitignore(root: Path) -> None:
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        raise ArchiveServiceError("Archive .gitignore must protect profiles/local/ before writing a local profile hint.")
    text = gitignore.read_text(encoding="utf-8")
    if "profiles/local/" not in text:
        raise ArchiveServiceError("Archive .gitignore must include profiles/local/ before writing a local profile hint.")


def load_local_github_profile(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "version": "wom-local-github-profile/v0.1",
            "github_accounts": [],
        }
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ArchiveServiceError("Local GitHub profile hint must be a YAML object.")
    if not isinstance(data.get("github_accounts"), list):
        data["github_accounts"] = []
    data["version"] = str(data.get("version") or "wom-local-github-profile/v0.1")
    return json_safe(data)


def merge_github_local_profile(data: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    accounts = data.get("github_accounts") if isinstance(data.get("github_accounts"), list) else []
    result: list[dict[str, Any]] = []
    replaced = False
    for item in accounts:
        if not isinstance(item, dict):
            continue
        same_profile = str(item.get("profile_id") or "").lower() == str(entry.get("profile_id") or "").lower()
        same_account = str(item.get("github_account_ref") or "").lower() == str(entry.get("github_account_ref") or "").lower()
        if same_profile or same_account:
            result.append(json_safe(entry))
            replaced = True
        else:
            result.append(json_safe(item))
    if not replaced:
        result.append(json_safe(entry))
    data["github_accounts"] = result
    return data


def object_storage_setup_plan(
    archive_root: Path | str,
    *,
    provider: str | None = None,
    profile_id: str | None = None,
    profile_slug: str | None = None,
    storage_account_ref: str | None = None,
    bucket_name: str | None = None,
    region: str | None = None,
    endpoint_ref: str | None = None,
    objet_prefix: str | None = None,
    visibility: str = OBJECT_STORAGE_DEFAULT_VISIBILITY,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_config = read_archive_config(root)
    archive_id = str(archive_config.get("archive_id") or "")
    blockers: list[str] = []
    warnings: list[str] = []

    resolved_provider = normalize_object_storage_provider(provider)
    if not resolved_provider:
        blockers.append("provider is required.")
    elif resolved_provider not in OBJECT_STORAGE_ALLOWED_PROVIDERS:
        blockers.append("provider must be one of: " + ", ".join(sorted(OBJECT_STORAGE_ALLOWED_PROVIDERS)) + ".")

    resolved_profile_id = (profile_id or "").strip()
    if not resolved_profile_id:
        blockers.append("profile_id is required.")
    resolved_slug = resolve_github_profile_slug(resolved_profile_id, profile_slug, blockers, warnings)
    bucket_slug = object_storage_bucket_slug(resolved_slug)
    resolved_bucket = resolve_object_storage_bucket_name(bucket_name, bucket_slug, blockers)
    resolved_visibility = (visibility or OBJECT_STORAGE_DEFAULT_VISIBILITY).strip().lower()
    resolved_account_ref = (storage_account_ref or "").strip()
    resolved_region = (region or "auto").strip()
    resolved_endpoint_ref = (endpoint_ref or default_object_storage_endpoint_ref(resolved_provider)).strip()
    resolved_prefix = resolve_objet_prefix(objet_prefix, archive_id, blockers)

    if not archive_id:
        blockers.append("archive.yml does not contain archive_id.")
    if resolved_visibility not in OBJECT_STORAGE_ALLOWED_VISIBILITIES:
        blockers.append("visibility must be private.")
    if not safe_object_storage_account_ref(resolved_account_ref):
        blockers.append("storage_account_ref must be a safe account reference, not an email, URL, token, secret, or path.")
    if not safe_object_storage_region(resolved_region):
        blockers.append("region must be a safe region label.")
    if resolved_endpoint_ref and not safe_object_storage_ref(resolved_endpoint_ref):
        blockers.append("endpoint_ref must be a safe endpoint reference, not a URL, token, secret, or path.")

    warnings.append("Bucket/container global availability is not checked by this dry-run.")

    provider_binding = build_object_storage_provider_binding(
        archive_id=archive_id,
        profile_id=resolved_profile_id,
        profile_slug=resolved_slug,
        provider_kind=resolved_provider,
        storage_account_ref=resolved_account_ref,
        bucket_name=resolved_bucket,
        region=resolved_region,
        endpoint_ref=resolved_endpoint_ref,
        objet_prefix=resolved_prefix,
        visibility=resolved_visibility,
    )
    local_profile_preview = build_object_storage_local_profile_preview(
        profile_id=resolved_profile_id,
        profile_slug=resolved_slug,
        provider_kind=resolved_provider,
        storage_account_ref=resolved_account_ref,
        bucket_name=resolved_bucket,
        region=resolved_region,
        endpoint_ref=resolved_endpoint_ref,
        objet_prefix=resolved_prefix,
        visibility=resolved_visibility,
    )
    policy_preview = build_objet_storage_policy_preview(
        archive_id=archive_id,
        provider_kind=resolved_provider,
        bucket_name=resolved_bucket,
        objet_prefix=resolved_prefix,
        visibility=resolved_visibility,
    )
    receipt_path = object_storage_provider_setup_receipt_path(resolved_bucket)
    manual_steps = object_storage_manual_steps(resolved_provider, resolved_bucket, resolved_region, resolved_prefix)
    receipt_preview = build_object_storage_provider_setup_receipt(
        archive_id=archive_id,
        profile_id=resolved_profile_id,
        profile_slug=resolved_slug,
        provider_kind=resolved_provider,
        storage_account_ref=resolved_account_ref,
        bucket_name=resolved_bucket,
        region=resolved_region,
        endpoint_ref=resolved_endpoint_ref,
        objet_prefix=resolved_prefix,
        visibility=resolved_visibility,
        receipt_path=receipt_path,
        reviewed_by="<required-on-approve>",
        timestamp="<execution-time>",
        dry_run=True,
        manual_steps=manual_steps,
    )

    provider_doc = load_provider_bindings(root)
    if provider_doc.get("archive_id") and provider_doc.get("archive_id") != archive_id:
        blockers.append("provider-bindings.yml archive_id must match archive.yml archive_id.")
    if archive_internal_path(root, receipt_path).exists():
        blockers.append(f"Proposed provider setup receipt already exists: {receipt_path}.")

    provider_action = "update provider-bindings.yml" if archive_internal_path(root, "provider-bindings.yml").exists() else "create provider-bindings.yml"
    return {
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "object_storage_setup_plan",
        "archive_id": archive_id,
        "profile_id": resolved_profile_id or None,
        "profile_slug": resolved_slug or None,
        "provider": resolved_provider or None,
        "proposed_bucket_name": resolved_bucket or None,
        "proposed_objet_prefix": resolved_prefix or None,
        "proposed_visibility": resolved_visibility,
        "storage_account_ref": resolved_account_ref or None,
        "region": resolved_region or None,
        "endpoint_ref": resolved_endpoint_ref or None,
        "provider_binding_preview": json_safe(provider_binding),
        "local_profile_preview": json_safe(local_profile_preview),
        "provider_setup_receipt_preview": json_safe(receipt_preview),
        "objet_storage_policy_preview": json_safe(policy_preview),
        "manual_steps": manual_steps,
        "blockers": unique_preserve_order(blockers),
        "warnings": unique_preserve_order(warnings),
        "would_change": [provider_action, f"write {receipt_path}"],
    }


def approve_object_storage_setup_plan(
    archive_root: Path | str,
    *,
    reviewed_by: str,
    write_local_profile: bool = False,
    provider: str | None = None,
    profile_id: str | None = None,
    profile_slug: str | None = None,
    storage_account_ref: str | None = None,
    bucket_name: str | None = None,
    region: str | None = None,
    endpoint_ref: str | None = None,
    objet_prefix: str | None = None,
    visibility: str = OBJECT_STORAGE_DEFAULT_VISIBILITY,
) -> dict[str, Any]:
    reviewer = (reviewed_by or "").strip()
    if not reviewer:
        raise ArchiveServiceError("Object storage setup approval requires reviewed_by.")
    validate_github_safe_metadata(reviewer, "reviewed_by")

    root = require_existing_archive_root(archive_root)
    plan = object_storage_setup_plan(
        root,
        provider=provider,
        profile_id=profile_id,
        profile_slug=profile_slug,
        storage_account_ref=storage_account_ref,
        bucket_name=bucket_name,
        region=region,
        endpoint_ref=endpoint_ref,
        objet_prefix=objet_prefix,
        visibility=visibility,
    )
    if plan["blockers"]:
        raise ArchiveServiceError("Object storage setup blocked by dry-run: " + "; ".join(plan["blockers"]))

    now = datetime.now().astimezone().replace(microsecond=0).isoformat()
    provider_path = archive_internal_path(root, "provider-bindings.yml")
    receipt_relative = plan["provider_setup_receipt_preview"]["receipt_path"]
    receipt_path = archive_internal_path(root, receipt_relative)
    if receipt_path.exists():
        raise ArchiveServiceError(f"Proposed provider setup receipt already exists: {receipt_relative}.")

    provider_doc = load_provider_bindings(root)
    if provider_doc.get("archive_id") and provider_doc.get("archive_id") != plan["archive_id"]:
        raise ArchiveServiceError("provider-bindings.yml archive_id must match archive.yml archive_id.")
    provider_doc["version"] = "provider-bindings/v0.1"
    provider_doc["archive_id"] = plan["archive_id"]
    provider_doc["bindings"] = upsert_object_storage_provider_binding(
        provider_bindings_list(provider_doc),
        plan["provider_binding_preview"],
    )

    receipt = build_object_storage_provider_setup_receipt(
        archive_id=plan["archive_id"],
        profile_id=plan["profile_id"],
        profile_slug=plan["profile_slug"],
        provider_kind=plan["provider"],
        storage_account_ref=plan["storage_account_ref"],
        bucket_name=plan["proposed_bucket_name"],
        region=plan["region"],
        endpoint_ref=plan["endpoint_ref"],
        objet_prefix=plan["proposed_objet_prefix"],
        visibility=plan["proposed_visibility"],
        receipt_path=receipt_relative,
        reviewed_by=reviewer,
        timestamp=now,
        dry_run=False,
        manual_steps=plan["manual_steps"],
    )
    receipt["result"] = {
        "changed_paths": ["provider-bindings.yml", receipt_relative],
        "provider_api_called": False,
        "bucket_created": False,
        "files_uploaded": False,
        "sync_started": False,
        "files_hashed": False,
    }

    changed_paths = ["provider-bindings.yml", receipt_relative]
    local_profile: dict[str, Any] | None = None
    local_profile_path: Path | None = None
    local_profile_relative = "profiles/local/object-storage-accounts.local.yml"
    if write_local_profile:
        ensure_local_profile_gitignore(root)
        local_profile_path = archive_internal_path(root, local_profile_relative)
        local_profile = merge_object_storage_local_profile(
            load_local_object_storage_profile(local_profile_path),
            plan["local_profile_preview"]["entry"],
        )
        changed_paths.append(local_profile_relative)
        receipt["result"]["changed_paths"] = changed_paths

    provider_original_text = provider_path.read_text(encoding="utf-8") if provider_path.exists() else None
    local_profile_original_text = (
        local_profile_path.read_text(encoding="utf-8")
        if write_local_profile and local_profile_path is not None and local_profile_path.exists()
        else None
    )
    created_receipt = False

    def restore_text(path: Path, original_text: str | None) -> None:
        if original_text is None:
            if path.exists():
                path.unlink()
            return
        write_text_atomic(path, original_text)

    try:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with receipt_path.open("x", encoding="utf-8") as handle:
            created_receipt = True
            handle.write(json.dumps(json_safe(receipt), indent=2, ensure_ascii=False, default=str) + "\n")
        provider_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(provider_path, dump_yaml(json_safe(provider_doc)))
        if write_local_profile and local_profile_path is not None and local_profile is not None:
            local_profile_path.parent.mkdir(parents=True, exist_ok=True)
            write_text_atomic(local_profile_path, dump_yaml(json_safe(local_profile)))
    except Exception:
        if created_receipt and receipt_path.exists():
            try:
                receipt_path.unlink()
            except OSError:
                pass
        try:
            restore_text(provider_path, provider_original_text)
        except OSError:
            pass
        if write_local_profile and local_profile_path is not None:
            try:
                restore_text(local_profile_path, local_profile_original_text)
            except OSError:
                pass
        raise

    return {
        "ok": True,
        "dry_run": False,
        "lifecycle_action": "object_storage_setup_plan",
        "archive_id": plan["archive_id"],
        "profile_id": plan["profile_id"],
        "profile_slug": plan["profile_slug"],
        "provider": plan["provider"],
        "proposed_bucket_name": plan["proposed_bucket_name"],
        "proposed_objet_prefix": plan["proposed_objet_prefix"],
        "proposed_visibility": plan["proposed_visibility"],
        "storage_account_ref": plan["storage_account_ref"],
        "region": plan["region"],
        "endpoint_ref": plan["endpoint_ref"],
        "provider_binding": json_safe(plan["provider_binding_preview"]),
        "receipt_path": receipt_relative,
        "provider_setup_receipt": json_safe(receipt),
        "local_profile_path": local_profile_relative if write_local_profile else None,
        "manual_steps": plan["manual_steps"],
        "changed_paths": changed_paths,
        "provider_api_called": False,
        "bucket_created": False,
        "files_uploaded": False,
        "sync_started": False,
        "files_hashed": False,
        "warnings": plan["warnings"],
    }


def normalize_object_storage_provider(provider: str | None) -> str:
    value = (provider or "").strip().lower().replace("_", "-")
    aliases = {
        "r2": "cloudflare-r2",
        "cloudflare": "cloudflare-r2",
        "s3": "aws-s3",
        "b2": "backblaze-b2",
        "gcs": "google-cloud-storage",
        "google": "google-cloud-storage",
    }
    return aliases.get(value, value)


def object_storage_bucket_slug(profile_slug: str) -> str:
    value = re.sub(r"[^a-z0-9-]+", "-", (profile_slug or "").lower())
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value


def resolve_object_storage_bucket_name(bucket_name: str | None, bucket_slug: str, blockers: list[str]) -> str:
    proposed = (bucket_name or "").strip()
    if not proposed and bucket_slug:
        proposed = f"zettel-kasten-{bucket_slug}-objets"
    if not safe_object_storage_bucket_name(proposed):
        blockers.append(
            "bucket_name must use lowercase ASCII letters, numbers, and hyphens only; "
            "start and end with an alphanumeric character; avoid dots, underscores, slashes, spaces, and URL fragments; "
            "and be at most 63 characters."
        )
    return proposed


def safe_object_storage_bucket_name(value: str) -> bool:
    text = value.strip()
    if not text or not text.isascii():
        return False
    if any(item in text for item in [".", "_", " ", "/", "\\", ":", "#", "?", "&", "=", "@"]):
        return False
    if GITHUB_SECRET_LIKE_RE.search(text):
        return False
    return bool(OBJECT_STORAGE_BUCKET_RE.match(text))


def default_object_storage_endpoint_ref(provider_kind: str) -> str:
    return f"provider:endpoint:{provider_kind or 'object-storage'}"


def resolve_objet_prefix(objet_prefix: str | None, archive_id: str, blockers: list[str]) -> str:
    prefix = (objet_prefix or "").strip()
    if not prefix and archive_id:
        prefix = f"archives/{archive_id}/objets/"
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    if not safe_objet_prefix(prefix):
        blockers.append("objet_prefix must be a safe relative provider prefix, not a local path, URL, traversal path, token, or secret.")
    return prefix


def safe_objet_prefix(value: str) -> bool:
    text = value.strip()
    if not text or not text.isascii():
        return False
    normalized = text.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("./") or "//" in normalized:
        return False
    if any(part == ".." for part in normalized.split("/")):
        return False
    if "://" in normalized or "#" in normalized or "?" in normalized:
        return False
    if GITHUB_SECRET_LIKE_RE.search(normalized):
        return False
    if contains_forbidden_location_reference(normalized):
        return False
    return True


def safe_object_storage_region(value: str) -> bool:
    text = value.strip()
    if not text or not text.isascii():
        return False
    if "@" in text or "://" in text or "/" in text or "\\" in text or "#" in text or "?" in text:
        return False
    if GITHUB_SECRET_LIKE_RE.search(text):
        return False
    return bool(OBJECT_STORAGE_REGION_RE.match(text))


def safe_object_storage_account_ref(value: str) -> bool:
    if not value:
        return False
    return safe_object_storage_ref(value)


def safe_object_storage_ref(value: str) -> bool:
    text = value.strip()
    if not text or not text.isascii():
        return False
    if "@" in text or "://" in text or "\\" in text or "/" in text or "#" in text or "?" in text:
        return False
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", text) and not (
        text.lower().startswith("storage:account:")
        or text.lower().startswith("provider:endpoint:")
        or text.lower().startswith("keyring:")
    ):
        return False
    if "." in text and not text.lower().startswith("provider:endpoint:"):
        return False
    if GITHUB_SECRET_LIKE_RE.search(text):
        return False
    return bool(OBJECT_STORAGE_REF_RE.match(text))


def build_object_storage_provider_binding(
    *,
    archive_id: str,
    profile_id: str,
    profile_slug: str,
    provider_kind: str,
    storage_account_ref: str,
    bucket_name: str,
    region: str,
    endpoint_ref: str,
    objet_prefix: str,
    visibility: str,
) -> dict[str, Any]:
    return {
        "binding_id": f"object_storage:{provider_kind}:{bucket_name}",
        "provider": "object_storage",
        "provider_kind": provider_kind,
        "enabled": True,
        "purpose": "objet_storage_metadata_and_manual_setup_plan",
        "resource": {
            "bucket": bucket_name,
            "prefix": objet_prefix,
            "visibility": visibility,
            "region": region,
            "endpoint_ref": endpoint_ref,
        },
        "auth": {
            "method": "token_ref_or_env",
            "token_env": OBJECT_STORAGE_PROVIDER_TOKEN_ENVS.get(provider_kind, "OBJECT_STORAGE_TOKEN"),
            "account_ref": storage_account_ref,
        },
        "owner_mapping": {
            "archive_id": archive_id,
            "profile_id": profile_id,
            "profile_slug": profile_slug,
        },
        "notes": "Manual object storage setup plan only; WOM-kit does not create buckets, upload objets, sync, copy, or hash files.",
    }


def build_object_storage_local_profile_preview(
    *,
    profile_id: str,
    profile_slug: str,
    provider_kind: str,
    storage_account_ref: str,
    bucket_name: str,
    region: str,
    endpoint_ref: str,
    objet_prefix: str,
    visibility: str,
) -> dict[str, Any]:
    entry = {
        "profile_id": profile_id,
        "profile_slug": profile_slug,
        "provider_kind": provider_kind,
        "storage_account_ref": storage_account_ref,
        "bucket_name": bucket_name,
        "region": region,
        "endpoint_ref": endpoint_ref,
        "objet_prefix": objet_prefix,
        "visibility": visibility,
        "token_env": OBJECT_STORAGE_PROVIDER_TOKEN_ENVS.get(provider_kind, "OBJECT_STORAGE_TOKEN"),
    }
    return {
        "path": "profiles/local/object-storage-accounts.local.yml",
        "ignored_by_default": True,
        "entry": entry,
    }


def build_objet_storage_policy_preview(
    *,
    archive_id: str,
    provider_kind: str,
    bucket_name: str,
    objet_prefix: str,
    visibility: str,
) -> dict[str, Any]:
    return {
        "archive_id": archive_id,
        "term": "objet",
        "technical_layer": "object_storage",
        "provider_kind": provider_kind,
        "bucket": bucket_name,
        "prefix": objet_prefix,
        "visibility": visibility,
        "stores": [
            "source/original files",
            "images",
            "audio",
            "video",
            "PDFs",
            "PPTX/DOCX/HWPX/spreadsheets",
            "large artifacts that should not live directly in Git",
        ],
        "git_storage": False,
        "content_uploaded": False,
        "content_hashed": False,
        "source_imported": False,
    }


def object_storage_manual_steps(provider_kind: str, bucket_name: str, region: str, objet_prefix: str) -> list[str]:
    return [
        f"Manually create a private {provider_kind} bucket/container named {bucket_name}.",
        f"Reserve the prefix {objet_prefix} for this archive's objets.",
        f"Configure scoped credentials outside the archive and expose only an env/token ref such as {OBJECT_STORAGE_PROVIDER_TOKEN_ENVS.get(provider_kind, 'OBJECT_STORAGE_TOKEN')}.",
        "Check provider bucket-name availability manually; WOM-kit does not call provider APIs.",
        "Run doctor --strict after local metadata approval.",
    ]


def object_storage_provider_setup_receipt_path(bucket_name: str) -> str:
    safe_bucket = safe_slug(bucket_name or "object-storage")
    return f"{OBJECT_STORAGE_SETUP_RECEIPTS_DIR}/{safe_bucket}.object-storage-setup.json"


def build_object_storage_provider_setup_receipt(
    *,
    archive_id: str,
    profile_id: str,
    profile_slug: str,
    provider_kind: str,
    storage_account_ref: str,
    bucket_name: str,
    region: str,
    endpoint_ref: str,
    objet_prefix: str,
    visibility: str,
    receipt_path: str,
    reviewed_by: str,
    timestamp: str,
    dry_run: bool,
    manual_steps: list[str],
) -> dict[str, Any]:
    return {
        "receipt_id": f"receipt:provider-setup:object-storage:{provider_kind}:{bucket_name}",
        "receipt_path": receipt_path,
        "lifecycle_action": "object_storage_setup_plan",
        "provider": "object_storage",
        "provider_kind": provider_kind,
        "dry_run": dry_run,
        "timestamp": timestamp,
        "archive_id": archive_id,
        "profile_id": profile_id,
        "profile_slug": profile_slug,
        "resource": {
            "bucket": bucket_name,
            "prefix": objet_prefix,
            "visibility": visibility,
            "region": region,
            "endpoint_ref": endpoint_ref,
        },
        "auth": {
            "method": "token_ref_or_env",
            "token_env": OBJECT_STORAGE_PROVIDER_TOKEN_ENVS.get(provider_kind, "OBJECT_STORAGE_TOKEN"),
            "account_ref": storage_account_ref,
        },
        "reviewed_by": reviewed_by,
        "external_actions": {
            "provider_api_called": False,
            "bucket_created": False,
            "oauth_started": False,
            "files_uploaded": False,
            "sync_started": False,
            "files_copied": False,
            "files_hashed": False,
            "source_content_imported": False,
        },
        "manual_steps": manual_steps,
    }


def upsert_object_storage_provider_binding(bindings: list[dict[str, Any]], new_binding: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    replaced = False
    new_key = object_storage_binding_compare_key(new_binding)
    for binding in bindings:
        if object_storage_binding_compare_key(binding) == new_key:
            result.append(json_safe(new_binding))
            replaced = True
        else:
            result.append(json_safe(binding))
    if not replaced:
        result.append(json_safe(new_binding))
    return result


def object_storage_binding_compare_key(binding: dict[str, Any]) -> tuple[str, str, str]:
    resource = binding.get("resource") if isinstance(binding.get("resource"), dict) else {}
    return (
        str(binding.get("provider") or "").lower(),
        str(binding.get("provider_kind") or "").lower(),
        str(resource.get("bucket") or binding.get("binding_id") or "").lower(),
    )


def load_local_object_storage_profile(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "version": "wom-local-object-storage-profile/v0.1",
            "object_storage_accounts": [],
        }
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ArchiveServiceError("Local object storage profile hint must be a YAML object.")
    if not isinstance(data.get("object_storage_accounts"), list):
        data["object_storage_accounts"] = []
    data["version"] = str(data.get("version") or "wom-local-object-storage-profile/v0.1")
    return json_safe(data)


def merge_object_storage_local_profile(data: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    accounts = data.get("object_storage_accounts") if isinstance(data.get("object_storage_accounts"), list) else []
    result: list[dict[str, Any]] = []
    replaced = False
    for item in accounts:
        if not isinstance(item, dict):
            continue
        same_provider_kind = str(item.get("provider_kind") or "").lower() == str(entry.get("provider_kind") or "").lower()
        same_bucket = str(item.get("bucket_name") or "").lower() == str(entry.get("bucket_name") or "").lower()
        if same_provider_kind and same_bucket:
            result.append(json_safe(entry))
            replaced = True
        else:
            result.append(json_safe(item))
    if not replaced:
        result.append(json_safe(entry))
    data["object_storage_accounts"] = result
    return data


def ownership_transfer_dry_run(
    archive_root: Path | str,
    *,
    new_owner: str,
    new_owner_kind: str | None = None,
    new_owner_archive: str | None = None,
    operators_after: list[str] | None = None,
    approved_by: list[str] | None = None,
    subject: str | None = None,
    counterparty_id: str | None = None,
    counterparty_fingerprint: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    resolved_new_owner = new_owner.strip()
    if not resolved_new_owner:
        raise ArchiveServiceError("new_owner is required.")

    blockers: list[str] = []
    warnings: list[str] = []
    source_archive = read_archive_id(root)
    identity_doc = load_archive_identity(root)
    ownership = identity_doc.get("ownership") if isinstance(identity_doc.get("ownership"), dict) else {}
    transfer_policy = ownership.get("transfer_policy") if isinstance(ownership.get("transfer_policy"), dict) else {}
    operators_before = ownership.get("operators") if isinstance(ownership.get("operators"), list) else []
    subjects = ownership.get("subjects") if isinstance(ownership.get("subjects"), list) else []
    previous_owner = ownership.get("owner_id")
    previous_owner_kind = ownership.get("owner_kind")
    resolved_new_owner_kind = new_owner_kind or infer_owner_kind(resolved_new_owner)
    resolved_operators_after = normalize_unique_strings(operators_after)
    approval_actors = normalize_unique_strings(approved_by)
    resolved_subject = subject or default_transfer_subject(subjects, transfer_policy, resolved_new_owner)

    if resolved_new_owner_kind not in OWNER_KINDS:
        blockers.append(
            "new_owner_kind is required or must be one of: "
            + ", ".join(sorted(OWNER_KINDS))
            + "."
        )
    if previous_owner == resolved_new_owner:
        blockers.append("New owner is already the current owner.")
    if transfer_policy.get("ownership_transfer_allowed") is not True:
        blockers.append("archive-identity.yml transfer_policy does not allow ownership transfer.")
    if transfer_policy.get("requires_receipt") is not True:
        blockers.append("Ownership transfer must require a receipt.")
    if not resolved_operators_after:
        blockers.append("At least one --operator-after value is required for the post-transfer operator list.")
    if transfer_policy.get("requires_human_approval", True) and not approval_actors:
        blockers.append("At least one --approved-by value is required by the transfer policy.")

    approval_checks = build_approval_actor_checks(approval_actors, previous_owner, operators_before, blockers, warnings)
    trust_gate = validate_counterparty_trust(
        root,
        counterparty_id=counterparty_id or new_owner_archive or resolved_new_owner,
        counterparty_fingerprint=counterparty_fingerprint,
        blockers=blockers,
    )

    proposed_receipt_path = (
        "receipts/lineage/"
        f"{safe_slug(source_archive)}__to__{safe_slug(resolved_new_owner)}.ownership-transfer.json"
    )
    if (root / proposed_receipt_path).exists():
        blockers.append(f"Proposed ownership transfer receipt already exists: {proposed_receipt_path}.")

    scope_gate = {
        "unit": "archive_ownership",
        "archive_id": source_archive,
        "manifest": "archive-identity.yml",
        "record_transfer": False,
        "included": [
            "archive-identity.yml ownership block",
            "archive-identity.yml lineage hints",
            proposed_receipt_path,
        ],
        "excluded": [
            "zettels/",
            "inbox/",
            "objects/",
            "workpacks/",
        ],
        "sensitive_categories_blocked_by_default": sorted(SENSITIVE_SHARE_CATEGORIES),
    }
    ownership_gate = {
        "ownership_transfer": True,
        "status": "passed" if not blockers else "blocked",
        "current_owner": previous_owner,
        "current_owner_kind": previous_owner_kind,
        "new_owner": resolved_new_owner,
        "new_owner_kind": resolved_new_owner_kind,
        "new_owner_archive": new_owner_archive,
        "operators_before": operator_ids(operators_before),
        "operators_after": resolved_operators_after,
        "subjects": subjects,
        "subject": resolved_subject,
        "approval_actors": approval_actors,
        "approval_checks": approval_checks,
        "transfer_policy": transfer_policy,
        "receipt_required_for_transfer": True,
    }
    lineage = {
        "event": "ownership_transfer",
        "source_archive": source_archive,
        "previous_owner": previous_owner,
        "new_owner": resolved_new_owner,
        "subject": resolved_subject,
        "new_owner_archive": new_owner_archive,
        "reason": reason,
    }
    provider_change_plan = build_provider_change_plan(
        root,
        source_archive=source_archive,
        previous_owner=previous_owner,
        new_owner=resolved_new_owner,
        new_owner_archive=new_owner_archive,
        operators_after=resolved_operators_after,
        reason=reason,
    )
    receipt_preview = {
        "receipt_id": f"receipt:ownership-transfer:{safe_slug(source_archive)}:{safe_slug(resolved_new_owner)}",
        "receipt_path": proposed_receipt_path,
        "action": transfer_policy.get("receipt_action") or "transfer_archive_ownership",
        "dry_run": True,
        "timestamp": "<execution-time>",
        "source_archive": source_archive,
        "previous_owner": {
            "owner_id": previous_owner,
            "owner_kind": previous_owner_kind,
            "owner_archive_id": ownership.get("owner_archive_id"),
        },
        "new_owner": {
            "owner_id": resolved_new_owner,
            "owner_kind": resolved_new_owner_kind,
            "owner_archive_id": new_owner_archive,
        },
        "operators_before": operator_ids(operators_before),
        "operators_after": resolved_operators_after,
        "subject": resolved_subject,
        "scope_manifest": scope_gate,
        "approval_actors": approval_actors,
        "trust_gate": trust_gate,
        "ownership_gate": ownership_gate,
        "lineage": lineage,
        "provider_change_plan": provider_change_plan,
        "blockers": blockers,
        "warnings": warnings,
    }

    return {
        "ok": not blockers,
        "dry_run": True,
        "source_archive": source_archive,
        "previous_owner": previous_owner,
        "previous_owner_kind": previous_owner_kind,
        "new_owner": resolved_new_owner,
        "new_owner_kind": resolved_new_owner_kind,
        "new_owner_archive": new_owner_archive,
        "subject": resolved_subject,
        "blockers": blockers,
        "warnings": warnings,
        "scope_gate": scope_gate,
        "trust_gate": trust_gate,
        "ownership_gate": ownership_gate,
        "lineage": lineage,
        "provider_change_plan": provider_change_plan,
        "proposed_receipt_path": proposed_receipt_path,
        "receipt_preview": receipt_preview,
        "would_change": [
            "update archive-identity.yml ownership.owner_id",
            "update archive-identity.yml ownership.owner_kind",
            "replace archive-identity.yml ownership.operators",
            "append ownership transfer lineage metadata",
            "record provider_change_plan without calling external provider APIs",
            f"write {proposed_receipt_path}",
        ],
    }


def transfer_archive_ownership(
    archive_root: Path | str,
    *,
    new_owner: str,
    new_owner_kind: str | None = None,
    new_owner_archive: str | None = None,
    operators_after: list[str] | None = None,
    approved_by: list[str] | None = None,
    subject: str | None = None,
    counterparty_id: str | None = None,
    counterparty_fingerprint: str | None = None,
    reason: str | None = None,
    reviewed_by: str,
) -> dict[str, Any]:
    reviewer = reviewed_by.strip()
    if not reviewer:
        raise ArchiveServiceError("Real ownership transfer requires --reviewed-by.")

    root = require_existing_archive_root(archive_root)
    dry_run = ownership_transfer_dry_run(
        root,
        new_owner=new_owner,
        new_owner_kind=new_owner_kind,
        new_owner_archive=new_owner_archive,
        operators_after=operators_after,
        approved_by=approved_by,
        subject=subject,
        counterparty_id=counterparty_id,
        counterparty_fingerprint=counterparty_fingerprint,
        reason=reason,
    )
    if dry_run["blockers"]:
        raise ArchiveServiceError("Ownership transfer blocked by dry-run: " + "; ".join(dry_run["blockers"]))

    ownership_gate = dry_run["ownership_gate"]
    if not actor_can_approve_transfer(reviewer, ownership_gate):
        raise ArchiveServiceError("Real ownership transfer reviewer must be the current owner, an operator, or an approved actor.")

    identity_path = archive_internal_path(root, "archive-identity.yml")
    original_identity_text = identity_path.read_text(encoding="utf-8")
    identity_doc = load_archive_identity(root)
    ownership = identity_doc.get("ownership") if isinstance(identity_doc.get("ownership"), dict) else {}
    if not isinstance(ownership, dict):
        ownership = {}
    lineage_doc = identity_doc.get("lineage") if isinstance(identity_doc.get("lineage"), dict) else {}
    if not isinstance(lineage_doc, dict):
        lineage_doc = {}

    now = datetime.now().astimezone().replace(microsecond=0).isoformat()
    receipt_relative = dry_run["proposed_receipt_path"]
    receipt_path = resolve_archive_relative_path(root, receipt_relative)
    if receipt_path.exists():
        raise ArchiveServiceError(f"Proposed ownership transfer receipt already exists: {receipt_relative}.")

    previous_owner_display_name = ownership.get("owner_display_name")
    operators_after_records = build_operator_records(dry_run["ownership_gate"]["operators_after"], dry_run["new_owner"], now)
    ownership["owner_id"] = dry_run["new_owner"]
    ownership["owner_kind"] = dry_run["new_owner_kind"]
    ownership["owner_display_name"] = dry_run["new_owner"]
    if dry_run.get("new_owner_archive"):
        ownership["owner_archive_id"] = dry_run["new_owner_archive"]
    else:
        ownership.pop("owner_archive_id", None)
    ownership["operators"] = operators_after_records
    identity_doc["ownership"] = ownership

    ownership_transfers = lineage_doc.get("ownership_transfers")
    if not isinstance(ownership_transfers, list):
        ownership_transfers = []
    transfer_event = {
        "event": "ownership_transfer",
        "receipt_id": dry_run["receipt_preview"]["receipt_id"],
        "receipt_path": receipt_relative,
        "timestamp": now,
        "source_archive": dry_run["source_archive"],
        "previous_owner": dry_run["previous_owner"],
        "new_owner": dry_run["new_owner"],
        "new_owner_archive": dry_run["new_owner_archive"],
        "subject": dry_run["subject"],
        "reviewed_by": reviewer,
        "reason": reason,
    }
    ownership_transfers.append(transfer_event)
    lineage_doc["ownership_transfers"] = ownership_transfers
    identity_doc["lineage"] = lineage_doc

    receipt = dict(dry_run["receipt_preview"])
    receipt["dry_run"] = False
    receipt["timestamp"] = now
    receipt["reviewed_by"] = reviewer
    receipt["reviewed_at"] = now
    receipt["scope_manifest"] = dict(receipt["scope_manifest"])
    receipt["scope_manifest"]["record_transfer"] = True
    receipt["ownership_gate"] = dict(receipt["ownership_gate"])
    receipt["ownership_gate"]["status"] = "passed"
    receipt["lineage"] = dict(receipt["lineage"])
    receipt["lineage"]["timestamp"] = now
    receipt["result"] = {
        "changed_paths": ["archive-identity.yml", receipt_relative],
        "previous_owner_display_name": previous_owner_display_name,
        "operators_after_records": operators_after_records,
        "provider_changes_applied": False,
        "provider_changes_status": receipt["provider_change_plan"]["status"],
    }

    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    created_receipt = False
    try:
        with receipt_path.open("x", encoding="utf-8") as handle:
            created_receipt = True
            handle.write(json.dumps(json_safe(receipt), indent=2, ensure_ascii=False, default=str) + "\n")
        write_text_atomic(identity_path, dump_yaml(identity_doc))
    except OSError:
        if created_receipt and receipt_path.exists():
            receipt_path.unlink()
        if identity_path.read_text(encoding="utf-8") != original_identity_text:
            write_text_atomic(identity_path, original_identity_text)
        raise

    return {
        "ok": True,
        "dry_run": False,
        "source_archive": dry_run["source_archive"],
        "previous_owner": dry_run["previous_owner"],
        "new_owner": dry_run["new_owner"],
        "new_owner_kind": dry_run["new_owner_kind"],
        "new_owner_archive": dry_run["new_owner_archive"],
        "subject": dry_run["subject"],
        "reviewed_by": reviewer,
        "receipt_path": receipt_relative,
        "changed_paths": ["archive-identity.yml", receipt_relative],
        "provider_change_plan": dry_run["provider_change_plan"],
        "receipt": json_safe(receipt),
    }


def actor_can_approve_transfer(actor: str, ownership_gate: dict[str, Any]) -> bool:
    allowed = {str(value) for value in ownership_gate.get("approval_actors") or []}
    allowed.update(str(value) for value in ownership_gate.get("operators_before") or [])
    current_owner = ownership_gate.get("current_owner")
    if current_owner:
        allowed.add(str(current_owner))
    return actor in allowed


def build_operator_records(operator_ids_after: list[str], new_owner: str, iso_now: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for operator_id in operator_ids_after:
        role = "owner_operator" if operator_id == new_owner else "delegated_operator"
        records.append(
            {
                "operator_id": operator_id,
                "role": role,
                "permissions": ["capture", "curate", "approve", "transfer_request"],
                "starts_at": iso_now,
                "ends_at": None,
            }
        )
    return records


def write_text_atomic(path: Path, text: str) -> None:
    temporary_path = path.with_name(path.name + ".tmp")
    try:
        temporary_path.write_text(text, encoding="utf-8")
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def normalize_unique_strings(values: list[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        item = str(value).strip()
        if item and item not in result:
            result.append(item)
    return result


def infer_owner_kind(owner_id: str) -> str | None:
    prefix = owner_id.split(":", 1)[0].strip()
    return prefix if prefix in OWNER_KINDS else None


def default_transfer_subject(
    subjects: list[Any],
    transfer_policy: dict[str, Any],
    new_owner: str,
) -> str | None:
    policy_target = transfer_policy.get("default_transfer_target")
    if isinstance(policy_target, str) and policy_target:
        return policy_target
    subject_ids = [
        item.get("subject_id")
        for item in subjects
        if isinstance(item, dict) and isinstance(item.get("subject_id"), str)
    ]
    if new_owner in subject_ids:
        return new_owner
    if len(subject_ids) == 1:
        return subject_ids[0]
    return None


def operator_ids(operators: list[Any]) -> list[str]:
    return [
        item["operator_id"]
        for item in operators
        if isinstance(item, dict) and isinstance(item.get("operator_id"), str)
    ]


def build_approval_actor_checks(
    approval_actors: list[str],
    previous_owner: Any,
    operators_before: list[Any],
    blockers: list[str],
    warnings: list[str],
) -> list[dict[str, Any]]:
    operators_by_id = {
        item.get("operator_id"): item
        for item in operators_before
        if isinstance(item, dict) and isinstance(item.get("operator_id"), str)
    }
    checks: list[dict[str, Any]] = []
    for actor in approval_actors:
        check = {
            "actor": actor,
            "recognized": False,
            "role": None,
            "permissions": [],
            "status": "blocked",
        }
        if actor == previous_owner:
            check.update({"recognized": True, "role": "owner", "status": "recognized_owner"})
            checks.append(check)
            continue

        operator = operators_by_id.get(actor)
        if operator is None:
            blockers.append(f"Approval actor is not the current owner or an operator: {actor}.")
            checks.append(check)
            continue

        permissions = operator.get("permissions") if isinstance(operator.get("permissions"), list) else []
        check["recognized"] = True
        check["role"] = operator.get("role")
        check["permissions"] = permissions
        if not permissions:
            warnings.append(f"Approval actor has no explicit permissions list: {actor}.")
            check["status"] = "recognized_operator_without_permissions"
        elif "approve" in permissions or "transfer_request" in permissions:
            check["status"] = "recognized_operator"
        else:
            blockers.append(f"Approval actor lacks approve or transfer_request permission: {actor}.")
        checks.append(check)
    return checks


def resolve_view(archive_root: Path, view_id: str) -> dict[str, Any]:
    views_root = archive_root / "views"
    if not views_root.is_dir():
        raise ArchiveServiceError("views/ directory is missing.")
    for path in safe_archive_glob(views_root, "*.yml", archive_root):
        data = load_yaml(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        if data.get("id") == view_id:
            result = json_safe(data)
            result["source_path"] = archive_relative_path(path, archive_root)
            return result
        saved_views = data.get("saved_views") or []
        if isinstance(saved_views, list):
            for saved_view in saved_views:
                if isinstance(saved_view, dict) and saved_view.get("id") == view_id:
                    result = json_safe(saved_view)
                    result.setdefault("include", data.get("include") or {})
                    result.setdefault("context_policy", data.get("context_policy") or {})
                    result["source_path"] = archive_relative_path(path, archive_root)
                    return result
    raise ArchiveServiceError(f"View id not found: {view_id}")


def select_zettels_for_view(archive_root: Path, view: dict[str, Any]) -> list[dict[str, Any]]:
    filters = view.get("filters") or {}
    if not isinstance(filters, dict):
        raise ArchiveServiceError("View filters must be an object.")
    max_zettels = 50
    context_policy = view.get("context_policy") or {}
    if isinstance(context_policy, dict) and isinstance(context_policy.get("max_zettels"), int):
        max_zettels = max(1, min(context_policy["max_zettels"], 500))

    selected: list[dict[str, Any]] = []
    for path in iter_zettel_paths(archive_root):
        relative = archive_relative_path(path, archive_root)
        if not relative.startswith("zettels/"):
            continue
        frontmatter, body = split_zettel_text(path.read_text(encoding="utf-8"))
        frontmatter = json_safe(frontmatter)
        if frontmatter.get("status") != "canonical":
            continue
        if not zettel_matches_filters(frontmatter, filters):
            continue
        selected.append({"path": path, "frontmatter": frontmatter, "body": body})
        if len(selected) >= max_zettels:
            break
    return selected


def zettel_matches_filters(frontmatter: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, expected in filters.items():
        actual = nested_value(frontmatter, str(key).split("."))
        if isinstance(actual, list):
            if expected not in actual:
                return False
        elif actual != expected:
            return False
    return True


def nested_value(data: Any, parts: list[str]) -> Any:
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def zettel_object_ids(frontmatter: dict[str, Any]) -> set[str]:
    object_ids: set[str] = set()
    assets = frontmatter.get("assets") or []
    if isinstance(assets, list):
        for asset in assets:
            if isinstance(asset, dict) and isinstance(asset.get("object_id"), str):
                object_ids.add(asset["object_id"])
    return object_ids


def load_manifest_records(archive_root: Path) -> list[dict[str, Any]]:
    manifest_path = archive_internal_path(archive_root, "objects/manifests/files.jsonl")
    if not manifest_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def load_source_bindings(archive_root: Path) -> dict[str, Any]:
    path = archive_internal_path(archive_root, "source-bindings.yml")
    if not path.is_file():
        return {
            "version": "source-bindings/v0.1",
            "archive_id": read_archive_id(archive_root),
            "sources": [],
        }
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ArchiveServiceError("source-bindings.yml must be a YAML object.")
    return json_safe(data)


def source_bindings_list(bindings_doc: dict[str, Any]) -> list[dict[str, Any]]:
    sources = bindings_doc.get("sources") or []
    if not isinstance(sources, list):
        return []
    return [item for item in sources if isinstance(item, dict)]


def source_binding_by_id(archive_root: Path, source_id: str) -> dict[str, Any]:
    normalized = (source_id or "").strip()
    if not normalized:
        raise ArchiveServiceError("source id is required.")
    bindings = source_bindings_list(load_source_bindings(archive_root))
    for binding in bindings:
        if binding.get("source_id") == normalized:
            return binding
    raise ArchiveServiceError(f"Source id not found in source-bindings.yml: {normalized}")


def source_map_relative_path(source_id: str) -> str:
    return f"{SOURCE_MAPS_DIR}/{safe_slug(source_id)}.jsonl"


def source_scan_receipt_relative_path(source_id: str, fingerprint: str) -> str:
    return f"{SOURCE_SCAN_RECEIPTS_DIR}/{safe_slug(source_id)}_{fingerprint}.source-scan.json"


def list_sources(archive_root: Path | str) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_id = read_archive_id(root)
    bindings_doc = load_source_bindings(root)
    local_roots = load_local_source_roots(root)
    sources = []
    for binding in source_bindings_list(bindings_doc):
        source_id = str(binding.get("source_id") or "")
        map_relative = source_map_relative_path(source_id)
        entries = load_source_map_entries(root, map_relative)
        sources.append(
            {
                "source_id": source_id,
                "source_type": binding.get("source_type"),
                "enabled": binding.get("enabled") is not False,
                "description": binding.get("description"),
                "root_ref": binding.get("root_ref"),
                "scope_policy": binding.get("scope_policy") if isinstance(binding.get("scope_policy"), dict) else {},
                "visibility": binding.get("visibility") if isinstance(binding.get("visibility"), dict) else default_private_visibility(),
                "source_map_path": map_relative,
                "source_map_present": archive_internal_path(root, map_relative).is_file(),
                "mapped_items": len(entries),
                "local_root_profile_present": source_id in local_roots,
            }
        )
    return {
        "ok": True,
        "archive_id": archive_id,
        "source_bindings_present": archive_internal_path(root, "source-bindings.yml").is_file(),
        "source_bindings_path": "source-bindings.yml",
        "source_count": len(sources),
        "sources": sources,
    }


def add_source_dry_run(
    archive_root: Path | str,
    *,
    source_id: str,
    source_type: str,
    description: str | None = None,
    root_ref: str | None = None,
    local_root: Path | str | None = None,
    write_local_profile: bool = False,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    max_items: int = 2000,
    visibility_scope: str = "private",
    source_visibility: str = "private",
    replace: bool = False,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_id = read_archive_id(root)
    resolved_source_id = (source_id or "").strip()
    resolved_type = (source_type or "").strip()
    blockers: list[str] = []
    warnings: list[str] = []
    if not resolved_source_id:
        blockers.append("source_id is required.")
    if resolved_type not in SOURCE_TYPES:
        blockers.append("source_type must be one of: " + ", ".join(sorted(SOURCE_TYPES)) + ".")

    bindings_doc = load_source_bindings(root)
    existing = {item.get("source_id"): item for item in source_bindings_list(bindings_doc)}
    exists = resolved_source_id in existing
    if exists and not replace:
        blockers.append(f"Source already exists. Use --replace to update it: {resolved_source_id}.")

    resolved_root_ref = normalize_source_root_ref(resolved_source_id, resolved_type, root_ref)
    validate_source_root_ref(root, resolved_root_ref, blockers)
    if local_root is not None:
        local_root_path = Path(local_root).expanduser().resolve()
        if not local_root_path.exists():
            warnings.append("Provided local root does not exist yet; registration can still be planned.")
    else:
        local_root_path = None
        if write_local_profile:
            blockers.append("--write-local-profile requires --local-root.")

    source_binding = build_source_binding(
        source_id=resolved_source_id,
        source_type=resolved_type,
        description=description,
        root_ref=resolved_root_ref,
        include=include,
        exclude=exclude,
        max_items=max_items,
        visibility_scope=visibility_scope,
        source_visibility=source_visibility,
    )
    local_profile_plan = {
        "write": bool(write_local_profile and local_root_path is not None),
        "path": SOURCE_ROOTS_LOCAL_PROFILE,
        "path_recorded": bool(write_local_profile and local_root_path is not None),
        "local_root_provided": local_root_path is not None,
    }
    would_change = ["source-bindings.yml"]
    if local_profile_plan["write"]:
        would_change.append(SOURCE_ROOTS_LOCAL_PROFILE)
    return {
        "ok": not blockers,
        "dry_run": True,
        "action": "add_archive_source",
        "archive_id": archive_id,
        "source_id": resolved_source_id,
        "source_type": resolved_type,
        "replace": replace,
        "already_exists": exists,
        "source_binding": source_binding,
        "local_profile": local_profile_plan,
        "mount_plan": source_mount_step(source_binding, local_profile_present=local_profile_plan["write"]),
        "would_change": would_change,
        "blockers": blockers,
        "warnings": warnings,
    }


def add_source_binding(
    archive_root: Path | str,
    *,
    source_id: str,
    source_type: str,
    reviewed_by: str,
    description: str | None = None,
    root_ref: str | None = None,
    local_root: Path | str | None = None,
    write_local_profile: bool = False,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    max_items: int = 2000,
    visibility_scope: str = "private",
    source_visibility: str = "private",
    replace: bool = False,
) -> dict[str, Any]:
    reviewer = reviewed_by.strip()
    if not reviewer:
        raise ArchiveServiceError("Source registration requires --reviewed-by.")
    root = require_existing_archive_root(archive_root)
    plan = add_source_dry_run(
        root,
        source_id=source_id,
        source_type=source_type,
        description=description,
        root_ref=root_ref,
        local_root=local_root,
        write_local_profile=write_local_profile,
        include=include,
        exclude=exclude,
        max_items=max_items,
        visibility_scope=visibility_scope,
        source_visibility=source_visibility,
        replace=replace,
    )
    if plan["blockers"]:
        raise ArchiveServiceError("Source registration blocked by dry-run: " + "; ".join(plan["blockers"]))

    source_bindings_path = archive_internal_path(root, "source-bindings.yml")
    bindings_doc = load_source_bindings(root)
    bindings_doc["archive_id"] = plan["archive_id"]
    sources = source_bindings_list(bindings_doc)
    source_binding = dict(plan["source_binding"])
    replaced = False
    for index, existing in enumerate(sources):
        if existing.get("source_id") == source_binding["source_id"]:
            sources[index] = source_binding
            replaced = True
            break
    if not replaced:
        sources.append(source_binding)
    bindings_doc["sources"] = sources
    source_bindings_path.write_text(dump_yaml(bindings_doc), encoding="utf-8")

    changed_paths = ["source-bindings.yml"]
    local_profile_path: str | None = None
    if plan["local_profile"]["write"] and local_root is not None:
        local_profile_path = write_local_source_root_profile(
            root,
            source_id=source_binding["source_id"],
            root_ref=source_binding["root_ref"],
            local_root=Path(local_root).expanduser().resolve(),
            reviewed_by=reviewer,
        )
        changed_paths.append(local_profile_path)

    return {
        "ok": True,
        "dry_run": False,
        "action": "add_archive_source",
        "archive_id": plan["archive_id"],
        "source_id": source_binding["source_id"],
        "source_type": source_binding["source_type"],
        "reviewed_by": reviewer,
        "changed_paths": changed_paths,
        "source_binding": source_binding,
        "local_profile_path": local_profile_path,
        "mount_plan": source_mount_step(source_binding, local_profile_present=local_profile_path is not None),
    }


def build_source_binding(
    *,
    source_id: str,
    source_type: str,
    description: str | None,
    root_ref: str,
    include: list[str] | None,
    exclude: list[str] | None,
    max_items: int,
    visibility_scope: str,
    source_visibility: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_type": source_type,
        "enabled": True,
        "description": description or f"{source_type} source {source_id}",
        "root_ref": root_ref,
        "scope_policy": {
            "mode": SOURCE_SCAN_MODE,
            "include": include or ["**/*"],
            "exclude": exclude if exclude is not None else [".git/**", "__pycache__/**"],
            "max_items": max(1, min(int(max_items), 10000)),
        },
        "visibility": {
            "scope": visibility_scope or "private",
            "allowed_archives": [],
            "source_visibility": source_visibility or "private",
        },
        "provenance": {
            "registered_by": "archive:add-source",
        },
    }


def normalize_source_root_ref(source_id: str, source_type: str, root_ref: str | None) -> str:
    if root_ref:
        return root_ref.strip()
    if source_type == "object_manifest":
        return "archive:objects/manifests/files.jsonl"
    return f"ARCHIVE_SOURCE_{safe_slug(source_id).upper()}_ROOT"


def validate_source_root_ref(archive_root: Path, root_ref: str, blockers: list[str]) -> None:
    if not root_ref:
        blockers.append("root_ref is required.")
        return
    if root_ref.startswith("archive:"):
        try:
            archive_internal_path(archive_root, root_ref.removeprefix("archive:"))
        except ArchiveServiceError as exc:
            blockers.append(str(exc))
        return
    normalized = root_ref.replace("\\", "/").strip()
    if contains_forbidden_location_reference(root_ref) or normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        blockers.append("root_ref must be an env/root ref or archive:relative ref, not an absolute path or provider URL.")


def load_local_source_roots(archive_root: Path) -> dict[str, dict[str, Any]]:
    path = archive_internal_path(archive_root, SOURCE_ROOTS_LOCAL_PROFILE)
    if not path.is_file():
        return {}
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    sources = data.get("sources")
    if not isinstance(sources, dict):
        return {}
    return {str(key): value for key, value in sources.items() if isinstance(value, dict)}


def local_source_root_path(archive_root: Path, source_id: str) -> Path | None:
    entry = load_local_source_roots(archive_root).get(source_id)
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        return None
    return Path(entry["path"]).expanduser().resolve()


def write_local_source_root_profile(
    archive_root: Path,
    *,
    source_id: str,
    root_ref: str,
    local_root: Path,
    reviewed_by: str,
) -> str:
    path = archive_internal_path(archive_root, SOURCE_ROOTS_LOCAL_PROFILE)
    data: dict[str, Any]
    if path.is_file():
        loaded = load_yaml(path.read_text(encoding="utf-8"))
        data = loaded if isinstance(loaded, dict) else {}
    else:
        data = {"version": "source-roots-local/v0.1", "sources": {}}
    data.setdefault("version", "source-roots-local/v0.1")
    sources = data.get("sources") if isinstance(data.get("sources"), dict) else {}
    sources[source_id] = {
        "root_ref": root_ref,
        "path": str(local_root),
        "path_is_local_only": True,
        "reviewed_by": reviewed_by,
        "updated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
    }
    data["sources"] = sources
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(data), encoding="utf-8")
    return SOURCE_ROOTS_LOCAL_PROFILE


def source_mount_plan(archive_root: Path | str) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_id = read_archive_id(root)
    local_roots = load_local_source_roots(root)
    sources = []
    for binding in source_bindings_list(load_source_bindings(root)):
        sources.append(source_mount_step(binding, local_profile_present=str(binding.get("source_id") or "") in local_roots))
    return {
        "ok": True,
        "archive_id": archive_id,
        "strategy": "docker_compose_override_or_host_native_cli",
        "local_profile_path": SOURCE_ROOTS_LOCAL_PROFILE,
        "secrets_required": False,
        "sources": sources,
        "notes": [
            "Host-native CLI can use ignored local profile paths or --source-root directly.",
            "Docker scans need each source mounted read-only under the suggested container_source_root.",
            "Do not mount your whole drive unless you intentionally choose a trusted broad discovery mode.",
        ],
    }


def recovery_plan(archive_root: Path | str) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_id = read_archive_id(root)
    sources = list_sources(root)
    providers = provider_bindings_summary(root)
    latest_receipt = latest_successful_restore_drill_receipt(root)
    return {
        "ok": True,
        "action": "archive_recovery_plan",
        "archive_root": str(root),
        "archive_id": archive_id,
        "local_only": True,
        "external_api_called": False,
        "secret_values_required": False,
        "control_plane_units": [
            "archive.yml",
            "archive-identity.yml",
            "provider-bindings.yml",
            "source-bindings.yml",
            "zettels/",
            "inbox/",
            "views/",
            "source-maps/",
            "objects/manifests/files.jsonl",
            "receipts/",
            "zettel-kasten/",
            "AGENTS.md",
        ],
        "excluded_from_restore_copy": RESTORE_DRILL_EXCLUDED_PATHS,
        "does_not_copy": [
            "external PC/SSD/SaaS/object-storage originals",
            "local-only profiles and keyrings",
            "generated SQLite search indexes",
            "provider secrets",
            "git history",
        ],
        "source_summary": {
            "source_count": sources["source_count"],
            "mapped_sources": [
                source["source_id"]
                for source in sources["sources"]
                if source.get("source_map_present")
            ],
            "unmapped_sources": [
                source["source_id"]
                for source in sources["sources"]
                if not source.get("source_map_present")
            ],
        },
        "provider_summary": {
            "binding_count": providers["binding_count"],
            "manual_required": True,
            "providers": [
                provider["provider"]
                for provider in providers["providers"]
                if provider.get("enabled") is not False
            ],
        },
        "latest_successful_restore_drill": latest_receipt,
        "next_steps": [
            "Run restore-drill --dry-run against an empty target folder.",
            "Run restore-drill --approve --reviewed-by <actor> before first real source scan.",
            "Keep external originals in their current systems; restore drill verifies the archive control plane.",
        ],
    }


def restore_drill_dry_run(archive_root: Path | str, target: Path | str) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    target_path = Path(target).expanduser().resolve()
    archive_id = read_archive_id(root)
    blockers: list[str] = []
    warnings: list[str] = []
    validate_restore_drill_target(root, target_path, blockers)
    copy_plan = restore_drill_copy_plan(root)
    receipt_preview = {
        "receipt_id": f"receipt:restore-drill:{safe_slug(archive_id)}:<execution-time>",
        "action": "restore_drill",
        "dry_run": True,
        "timestamp": "<execution-time>",
        "source_archive": archive_id,
        "source_archive_root": str(root),
        "target_root": str(target_path),
        "copy_plan": copy_plan,
        "validation": {
            "doctor_strict": "planned",
            "index": "planned",
            "search_smoke": "planned",
        },
        "result": {
            "status": "planned",
            "changed_paths": [],
        },
        "blockers": blockers,
        "warnings": warnings,
    }
    return {
        "ok": not blockers,
        "dry_run": True,
        "action": "restore_drill",
        "archive_id": archive_id,
        "archive_root": str(root),
        "target_root": str(target_path),
        "target_exists": target_path.exists(),
        "copy_plan": copy_plan,
        "receipt_preview": receipt_preview,
        "proposed_receipt_path": f"{RESTORE_DRILL_RECEIPTS_DIR}/<timestamp>.restore-drill.json",
        "would_change": [
            str(target_path),
            f"{RESTORE_DRILL_RECEIPTS_DIR}/<timestamp>.restore-drill.json",
        ],
        "blockers": blockers,
        "warnings": warnings,
    }


def validate_restore_drill_target(archive_root: Path, target: Path, blockers: list[str]) -> None:
    if target.exists() and not target.is_dir():
        blockers.append(f"Restore target must be a folder or absent: {target}.")
        return
    if target.exists() and any(target.iterdir()):
        blockers.append(f"Restore target must be empty or absent: {target}.")

    anchor = Path(target.anchor) if target.anchor else None
    if anchor is not None and target == anchor:
        blockers.append(f"Restore target must not be a filesystem or drive root: {target}.")

    kit_root = KIT_ROOT.resolve()
    if target == kit_root or target.is_relative_to(kit_root):
        blockers.append(f"Restore target must not be inside the WOM-kit repository: {target}.")

    if target == archive_root or target.is_relative_to(archive_root):
        blockers.append(f"Restore target must not be inside the source archive: {target}.")

    if archive_root.is_relative_to(target):
        blockers.append(f"Restore target must not contain the source archive: {target}.")

    system_reason = local_source_system_path_reason(target)
    if system_reason:
        blockers.append(f"Restore target must not be inside a system directory: {target} ({system_reason}).")


def restore_drill_copy_plan(archive_root: Path) -> dict[str, Any]:
    included_files = 0
    included_bytes = 0
    excluded_files = 0
    for path in sorted(archive_root.rglob("*")):
        if not path.is_file() or not is_path_within_root(path, archive_root):
            continue
        relative = archive_relative_path(path, archive_root)
        if restore_drill_should_exclude(relative):
            excluded_files += 1
            continue
        included_files += 1
        try:
            included_bytes += path.stat().st_size
        except OSError:
            pass
    return {
        "mode": "control_plane_copy",
        "metadata_only": True,
        "copies_external_originals": False,
        "included_files": included_files,
        "included_bytes": included_bytes,
        "excluded_files": excluded_files,
        "excluded_paths": RESTORE_DRILL_EXCLUDED_PATHS,
    }


def restore_drill_should_exclude(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    for pattern in RESTORE_DRILL_EXCLUDED_PATHS:
        if pattern.endswith("/"):
            prefix = pattern.rstrip("/")
            if normalized == prefix or normalized.startswith(prefix + "/"):
                return True
            continue
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def copy_restore_drill_tree(archive_root: Path, target: Path) -> list[str]:
    changed_paths: list[str] = []
    target.mkdir(parents=True, exist_ok=True)
    for path in sorted(archive_root.rglob("*")):
        if not path.is_file() or not is_path_within_root(path, archive_root):
            continue
        relative = archive_relative_path(path, archive_root)
        if restore_drill_should_exclude(relative):
            continue
        destination = target / Path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        changed_paths.append(relative)
    return changed_paths


def latest_successful_restore_drill_receipt(archive_root: Path | str) -> dict[str, Any] | None:
    root = require_existing_archive_root(archive_root)
    receipts_root = archive_internal_path(root, RESTORE_DRILL_RECEIPTS_DIR)
    if not receipts_root.is_dir():
        return None
    latest: dict[str, Any] | None = None
    for path in sorted(receipts_root.glob("*.restore-drill.json")):
        if not is_path_within_root(path, root):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        result = data.get("result") if isinstance(data.get("result"), dict) else {}
        if data.get("dry_run") is False and result.get("status") == "passed":
            latest = {
                "receipt_path": archive_relative_path(path, root),
                "receipt_id": data.get("receipt_id"),
                "reviewed_by": data.get("reviewed_by"),
                "reviewed_at": data.get("reviewed_at"),
                "target_root": data.get("target_root"),
                "status": result.get("status"),
            }
    return latest


def preflight_check(
    archive_root: Path | str,
    *,
    diagnostics: list[dict[str, Any]] | None = None,
    peer_archive_root: Path | str | None = None,
    require_source_maps: bool = False,
    require_restore_drill: bool = False,
    strict: bool = False,
    docker_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_id = read_archive_id(root)
    blockers: list[str] = []
    warnings: list[str] = []
    findings: list[dict[str, Any]] = []

    def add_finding(severity: str, code: str, message: str, path: str | None = None) -> None:
        finding = {"severity": severity, "code": code, "message": message}
        if path:
            finding["path"] = path
        findings.append(finding)
        if severity == "BLOCKER":
            blockers.append(message)
        elif severity == "WARN":
            warnings.append(message)

    doctor_diagnostics = diagnostics or []
    doctor_errors = [item for item in doctor_diagnostics if item.get("severity") == "ERROR"]
    doctor_warnings = [item for item in doctor_diagnostics if item.get("severity") == "WARN"]
    if doctor_errors:
        add_finding("BLOCKER", "doctor_errors", f"archive doctor reported {len(doctor_errors)} error(s).")
    if doctor_warnings:
        add_finding("WARN", "doctor_warnings", f"archive doctor reported {len(doctor_warnings)} warning(s).")

    sources = list_sources(root)
    source_by_id = {source["source_id"]: source for source in sources["sources"]}
    for source in sources["sources"]:
        if source.get("enabled") and require_source_maps and not source.get("source_map_present"):
            add_finding(
                "BLOCKER",
                "source_map_missing",
                f"Required source map is missing for source: {source['source_id']}.",
                str(source.get("source_map_path") or ""),
            )

    local_profile_checks = []
    for source_id, entry in load_local_source_roots(root).items():
        path_value = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(path_value, str) or not path_value.strip():
            add_finding("BLOCKER", "local_source_root_missing", f"Local profile path is missing for source: {source_id}.")
            continue
        path = Path(path_value).expanduser().resolve()
        source_type = str(source_by_id.get(source_id, {}).get("source_type") or "")
        check = classify_local_source_root(path, archive_root=root, source_id=source_id, source_type=source_type)
        local_profile_checks.append(check)
        if check["severity"] == "BLOCKER":
            add_finding("BLOCKER", check["code"], check["message"], check.get("path"))
        elif check["severity"] == "WARN":
            add_finding("WARN", check["code"], check["message"], check.get("path"))
        if not path.exists():
            add_finding("WARN", "local_source_root_not_found", f"Local source root does not exist yet: {source_id}.", str(path))

    peer_summary = None
    if peer_archive_root is not None:
        peer = Path(peer_archive_root).expanduser().resolve()
        peer_summary = {"path": str(peer), "exists": peer.exists()}
        if paths_overlap(root, peer):
            add_finding("BLOCKER", "peer_archive_root_overlaps", "Peer archive root overlaps this archive root.", str(peer))
        if not peer.exists():
            add_finding("WARN", "peer_archive_missing", "Peer archive root does not exist yet; create it before team/personal separation testing.", str(peer))
        elif not peer.is_dir():
            add_finding("BLOCKER", "peer_archive_not_directory", "Peer archive root is not a directory.", str(peer))
        else:
            try:
                peer_id = read_archive_id(peer)
                peer_summary["archive_id"] = peer_id
                if peer_id == archive_id:
                    add_finding("BLOCKER", "peer_archive_id_duplicate", "Peer archive id must not match this archive id.", str(peer))
            except ArchiveServiceError as exc:
                add_finding("BLOCKER", "peer_archive_unreadable", f"Peer archive could not be read: {exc}", str(peer))

    provider_summary: dict[str, Any] | None = None
    try:
        provider_summary = provider_bindings_summary(root)
    except ArchiveServiceError as exc:
        add_finding("BLOCKER", "provider_bindings_unreadable", f"Provider bindings could not be read: {exc}")

    mounts = source_mount_plan(root)
    docker = docker_runtime or {"checked": False, "ok": None, "status": "not_checked"}
    if docker.get("checked") and not docker.get("ok"):
        add_finding("BLOCKER", "docker_runtime_unavailable", str(docker.get("message") or "Docker runtime is not available."))

    latest_restore = latest_successful_restore_drill_receipt(root)
    if require_restore_drill and latest_restore is None:
        add_finding(
            "BLOCKER",
            "restore_drill_required",
            "A successful restore drill receipt is required before real source pilot.",
            RESTORE_DRILL_RECEIPTS_DIR,
        )

    ok = not blockers and not (strict and warnings)
    return {
        "ok": ok,
        "action": "archive_preflight_check",
        "archive_root": str(root),
        "archive_id": archive_id,
        "strict": strict,
        "require_source_maps": require_source_maps,
        "require_restore_drill": require_restore_drill,
        "doctor": {
            "checked": bool(diagnostics is not None),
            "errors": len(doctor_errors),
            "warnings": len(doctor_warnings),
            "diagnostics": doctor_diagnostics,
        },
        "sources": {
            "source_count": sources["source_count"],
            "missing_source_maps": [
                source["source_id"]
                for source in sources["sources"]
                if source.get("enabled") and not source.get("source_map_present")
            ],
            "local_profile_checks": local_profile_checks,
            "mount_plan": mounts,
        },
        "providers": provider_summary,
        "peer_archive": peer_summary,
        "restore_drill": {
            "required": require_restore_drill,
            "latest_successful": latest_restore,
        },
        "docker_runtime": docker,
        "findings": findings,
        "blockers": unique_preserve_order(blockers),
        "warnings": unique_preserve_order(warnings),
        "next_safe_actions": preflight_next_actions(blockers, warnings),
    }


def classify_local_source_root(
    path: Path,
    *,
    archive_root: Path,
    source_id: str,
    source_type: str,
) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    severity = "OK"
    code = "local_source_root_ok"
    message = f"Local source root looks narrow enough for first pilot: {source_id}."

    def result(new_severity: str, new_code: str, new_message: str) -> dict[str, Any]:
        return {
            "source_id": source_id,
            "source_type": source_type,
            "path": str(resolved),
            "exists": resolved.exists(),
            "severity": new_severity,
            "code": new_code,
            "message": new_message,
        }

    anchor = Path(resolved.anchor) if resolved.anchor else None
    if anchor is not None and resolved == anchor:
        return result("BLOCKER", "local_source_root_too_broad", f"Local source root is a filesystem or drive root: {source_id}.")

    home = Path.home().resolve()
    if resolved == home:
        return result("BLOCKER", "local_source_root_home", f"Local source root is the whole home folder: {source_id}.")

    system_reason = local_source_system_path_reason(resolved)
    if system_reason:
        return result("BLOCKER", "local_source_root_system_path", f"Local source root points into a system directory: {source_id} ({system_reason}).")

    kit_root = KIT_ROOT.resolve()
    if resolved == kit_root or kit_root.is_relative_to(resolved):
        return result("BLOCKER", "local_source_root_contains_repo", f"Local source root contains the WOM-kit repository: {source_id}.")

    if resolved == archive_root or archive_root.is_relative_to(resolved):
        return result("BLOCKER", "local_source_root_contains_archive", f"Local source root contains the archive itself: {source_id}.")

    broad_home_children = [
        home / "Documents",
        home / "Desktop",
        home / "Downloads",
        home / "OneDrive",
        home / "Google Drive",
    ]
    if any(resolved == item.resolve() for item in broad_home_children if item.exists()):
        return result("WARN", "local_source_root_broad_user_folder", f"Local source root is a broad user folder; first pilot should prefer a narrower subfolder: {source_id}.")

    if resolved.is_relative_to(kit_root):
        return result("WARN", "local_source_root_inside_repo", f"Local source root is inside the WOM-kit repository checkout: {source_id}.")

    if resolved.is_relative_to(archive_root):
        return result("WARN", "local_source_root_inside_archive", f"Local source root is inside the archive; prefer archive: refs for internal folders: {source_id}.")

    return result(severity, code, message)


def local_source_system_path_reason(path: Path) -> str | None:
    windows_roots = [
        os.environ.get("SystemRoot"),
        os.environ.get("WINDIR"),
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
    ]
    for raw in windows_roots:
        if not raw:
            continue
        root = Path(raw).resolve()
        if path == root or path.is_relative_to(root):
            return str(root)

    posix_blocked = [Path(item) for item in ["/etc", "/usr", "/bin", "/sbin", "/var", "/opt", "/root"]]
    for root in posix_blocked:
        try:
            resolved = root.resolve()
        except OSError:
            resolved = root
        if path == resolved or path.is_relative_to(resolved):
            return str(resolved)
    return None


def preflight_next_actions(blockers: list[str], warnings: list[str]) -> list[str]:
    if blockers:
        return [
            "Fix blockers before touching real personal or team data.",
            "Run archive doctor --strict after fixing structural or secret-safety problems.",
            "Use add-source --dry-run before registering any real source.",
        ]
    if warnings:
        return [
            "Review warnings with the human owner/operator.",
            "Prefer one narrow source for the first scan.",
            "Run scan-source --dry-run and check item_count before approving a scan.",
        ]
    return [
        "Start with one narrow source registration dry-run.",
        "Run metadata-only scan-source --dry-run.",
        "Approve only after reviewing item_count, source root, and receipt preview.",
    ]


def profile_list(
    registry_path: Path | str,
    *,
    current_profile: str | None = None,
    strict: bool = False,
    redact_local_paths: bool = True,
) -> dict[str, Any]:
    registry_file, registry, blockers, warnings = load_profile_registry(registry_path)
    profiles = profile_registry_entries(registry, blockers, warnings)
    if strict and warnings:
        blockers.extend(warnings)
        warnings = []

    return {
        "ok": not blockers,
        "lifecycle_action": "profile_list",
        "registry_path": redacted_path_value(registry_file, redact_local_paths=redact_local_paths),
        "default_profile": registry.get("default_profile"),
        "current_profile": current_profile,
        "profiles": [profile_public_summary(profile, redact_local_paths=redact_local_paths) for profile in profiles],
        "warnings": unique_preserve_order(warnings),
        "blockers": unique_preserve_order(blockers),
        "redaction": {"local_paths_redacted": bool(redact_local_paths)},
    }


def profile_resolve(
    registry_path: Path | str,
    *,
    target: str,
    current_profile: str | None = None,
    strict: bool = False,
    redact_local_paths: bool = True,
) -> dict[str, Any]:
    registry_file, registry, blockers, warnings = load_profile_registry(registry_path)
    profiles = profile_registry_entries(registry, blockers, warnings)
    query = normalize_profile_lookup_text(target or "")
    if not query:
        blockers.append("target query is required.")

    matches = resolve_profile_matches(profiles, query) if query else []
    selected_profile = matches[0]["profile"] if len(matches) == 1 else None
    resolution_state = profile_resolution_state(matches, selected_profile)
    direct_write_available = False
    suggested_next_action = "suggest_delegate_flow"
    delegate_fallback_preview: dict[str, Any] | None = None
    target_archive_context_preview = None
    runtime_context_args_preview = None

    if len(matches) > 1:
        resolution_state = "ambiguous"
        suggested_next_action = "ask_user_to_choose_profile"
        warnings.append("Multiple profiles matched the target query; ask the user to choose one.")
    elif not matches:
        resolution_state = "not_found"
        suggested_next_action = "suggest_delegate_flow"
        warnings.append("No profile matched the target query; register the profile or use a delegate flow.")
        delegate_fallback_preview = {
            "available": True,
            "reason": "target_profile_not_found",
            "suggestion": "Ask the user to choose/register a profile, or prepare a delegate flow instead of direct archive writing.",
        }
    elif selected_profile is not None:
        token_state = profile_token_state(selected_profile)
        archive_root = profile_archive_root(selected_profile)
        if token_state == "missing":
            resolution_state = "token_missing"
            suggested_next_action = "register_profile_token"
            warnings.append("Matched profile has no usable token; direct write is not available.")
            delegate_fallback_preview = {
                "available": True,
                "reason": "profile_token_missing",
                "suggestion": "Register the profile token, or use a delegate flow if this AI should not write to the target archive.",
            }
        else:
            resolution_state = "resolved"
            suggested_next_action = "run_runtime_context"

        if not archive_root:
            direct_write_available = False
            warnings.append("Matched profile is missing archive_root; direct write is not available.")
        else:
            direct_write_available = token_state != "missing"

        target_archive_context_preview = profile_context_preview(selected_profile, redact_local_paths=redact_local_paths)
        runtime_context_args_preview = {
            "archive_root": redact_profile_archive_root(archive_root, redact_local_paths=redact_local_paths),
            "expected_archive_id": selected_profile.get("archive_id"),
            "expected_type": selected_profile.get("archive_type"),
            "format": "json",
        }

    if strict and warnings and resolution_state not in {"token_missing", "not_found"}:
        blockers.extend(warnings)
        warnings = []

    return {
        "ok": not blockers and resolution_state not in {"ambiguous", "not_found"},
        "lifecycle_action": "profile_resolve",
        "target_query": query,
        "current_profile": current_profile,
        "default_profile": registry.get("default_profile"),
        "matches": [profile_match_summary(match, redact_local_paths=redact_local_paths) for match in matches],
        "selected_profile": profile_public_summary(selected_profile, redact_local_paths=redact_local_paths)
        if selected_profile is not None and len(matches) == 1
        else None,
        "resolution_state": resolution_state,
        "direct_write_available": direct_write_available,
        "suggested_next_action": suggested_next_action,
        "target_archive_context_preview": target_archive_context_preview,
        "runtime_context_args_preview": runtime_context_args_preview,
        "delegate_fallback_preview": delegate_fallback_preview,
        "warnings": unique_preserve_order(warnings),
        "blockers": unique_preserve_order(blockers),
        "redaction": {"local_paths_redacted": bool(redact_local_paths)},
        "registry_path": redacted_path_value(registry_file, redact_local_paths=redact_local_paths),
    }


def load_profile_registry(registry_path: Path | str) -> tuple[Path, dict[str, Any], list[str], list[str]]:
    registry_file = Path(registry_path).expanduser().resolve()
    blockers: list[str] = []
    warnings: list[str] = []
    if not registry_file.is_file():
        return registry_file, {}, ["Profile registry does not exist or is not a file."], warnings
    try:
        data = load_yaml(registry_file.read_text(encoding="utf-8"))
    except Exception as exc:
        return registry_file, {}, [f"Profile registry could not be read as YAML: {exc}"], warnings
    if not isinstance(data, dict):
        return registry_file, {}, ["Profile registry must be a YAML object."], warnings
    registry = json_safe(data)
    if registry.get("version") != PROFILE_REGISTRY_VERSION:
        blockers.append(f"Profile registry version must be {PROFILE_REGISTRY_VERSION}.")
    if not isinstance(registry.get("profiles"), list):
        blockers.append("Profile registry must contain a profiles list.")
    return registry_file, registry, blockers, warnings


def profile_registry_entries(registry: dict[str, Any], blockers: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    raw_profiles = registry.get("profiles") if isinstance(registry.get("profiles"), list) else []
    profiles: list[dict[str, Any]] = []
    seen_profile_ids: set[str] = set()
    for index, item in enumerate(raw_profiles):
        if not isinstance(item, dict):
            warnings.append(f"Profile registry item {index} is not an object.")
            continue
        profile = json_safe(item)
        profile_id = profile.get("profile_id")
        if not isinstance(profile_id, str) or not profile_id.strip():
            warnings.append(f"Profile registry item {index} is missing profile_id.")
            continue
        if profile_id in seen_profile_ids:
            blockers.append(f"Profile registry contains duplicate profile_id: {profile_id}.")
        seen_profile_ids.add(profile_id)
        validate_profile_token_contract(profile, blockers)
        if profile.get("archive_type") and profile.get("archive_type") not in PROFILE_REGISTRY_ARCHIVE_TYPES:
            warnings.append(f"Profile {profile_id} has an unknown archive_type.")
        profiles.append(profile)
    return profiles


def validate_profile_token_contract(profile: dict[str, Any], blockers: list[str]) -> None:
    token = profile.get("token")
    if token is None:
        return
    profile_id = str(profile.get("profile_id") or "<unknown-profile>")
    if not isinstance(token, dict):
        blockers.append(f"Profile {profile_id} token must be an object with state/token_ref metadata only.")
        return
    token_keys = {str(key) for key in token.keys()}
    raw_keys = sorted(key for key in token_keys if key.casefold() in PROFILE_RAW_TOKEN_KEYS)
    if raw_keys:
        blockers.append(
            f"Profile {profile_id} token contains raw secret-like field(s): {', '.join(raw_keys)}. "
            "Use token_ref instead of storing token values."
        )
    unknown_keys = sorted(token_keys - PROFILE_ALLOWED_TOKEN_KEYS)
    if unknown_keys:
        blockers.append(
            f"Profile {profile_id} token contains unsupported field(s): {', '.join(unknown_keys)}. "
            "Only state and token_ref are allowed."
        )


def resolve_profile_matches(profiles: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    ranked_matches: list[dict[str, Any]] = []
    for profile in profiles:
        match = profile_match(profile, query)
        if match is not None:
            ranked_matches.append(match)
    if not ranked_matches:
        return []
    best_rank = min(match["rank"] for match in ranked_matches)
    return [match for match in ranked_matches if match["rank"] == best_rank]


def profile_match(profile: dict[str, Any], query: str) -> dict[str, Any] | None:
    checks = [
        ("profile_id", profile.get("profile_id"), 0),
        ("label", profile.get("label"), 1),
    ]
    aliases = profile.get("aliases") if isinstance(profile.get("aliases"), list) else []
    for alias in aliases:
        checks.append(("alias", alias, 2))
    for field, value, rank in checks:
        if isinstance(value, str) and exact_profile_query_match(value, query):
            return {
                "profile": profile,
                "profile_id": profile.get("profile_id"),
                "match_type": field,
                "matched_value": value,
                "strength": "strong",
                "rank": rank,
            }
    return None


def exact_profile_query_match(value: str, query: str) -> bool:
    left = normalize_profile_lookup_text(value)
    right = normalize_profile_lookup_text(query)
    return left.casefold() == right.casefold()


def normalize_profile_lookup_text(value: str) -> str:
    return unicodedata.normalize("NFC", value).translate(PROFILE_IGNORABLE_QUERY_CHARS).strip()


def profile_resolution_state(matches: list[dict[str, Any]], selected_profile: dict[str, Any] | None) -> str:
    if len(matches) > 1:
        return "ambiguous"
    if not matches:
        return "not_found"
    if selected_profile is not None and profile_token_state(selected_profile) == "missing":
        return "token_missing"
    return "resolved"


def profile_public_summary(profile: dict[str, Any] | None, *, redact_local_paths: bool) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "profile_id": profile.get("profile_id"),
        "label": profile.get("label"),
        "aliases": profile_aliases(profile),
        "node_id": profile.get("node_id"),
        "archive_id": profile.get("archive_id"),
        "archive_type": profile.get("archive_type"),
        "operator_id": profile.get("operator_id"),
        "authority_mode": profile.get("authority_mode"),
        "token_state": profile_token_state(profile),
        "archive_root": redact_profile_archive_root(profile_archive_root(profile), redact_local_paths=redact_local_paths),
    }


def profile_match_summary(match: dict[str, Any], *, redact_local_paths: bool) -> dict[str, Any]:
    profile = match["profile"]
    return {
        "profile_id": profile.get("profile_id"),
        "label": profile.get("label"),
        "match_type": match.get("match_type"),
        "matched_value": match.get("matched_value"),
        "strength": match.get("strength"),
        "archive_id": profile.get("archive_id"),
        "archive_type": profile.get("archive_type"),
        "token_state": profile_token_state(profile),
        "authority_mode": profile.get("authority_mode"),
        "archive_root": redact_profile_archive_root(profile_archive_root(profile), redact_local_paths=redact_local_paths),
    }


def profile_context_preview(profile: dict[str, Any], *, redact_local_paths: bool) -> dict[str, Any]:
    return {
        "profile_id": profile.get("profile_id"),
        "archive_id": profile.get("archive_id"),
        "archive_type": profile.get("archive_type"),
        "node_id": profile.get("node_id"),
        "operator_id": profile.get("operator_id"),
        "authority_mode": profile.get("authority_mode"),
        "archive_root": redact_profile_archive_root(profile_archive_root(profile), redact_local_paths=redact_local_paths),
    }


def profile_aliases(profile: dict[str, Any]) -> list[str]:
    aliases = profile.get("aliases") if isinstance(profile.get("aliases"), list) else []
    return [alias for alias in aliases if isinstance(alias, str)]


def profile_archive_root(profile: dict[str, Any]) -> str | None:
    archive_root = profile.get("archive_root")
    if isinstance(archive_root, str) and archive_root.strip():
        return archive_root.strip()
    return None


def profile_token_state(profile: dict[str, Any]) -> str:
    token = profile.get("token") if isinstance(profile.get("token"), dict) else {}
    state = token.get("state")
    if isinstance(state, str) and state.strip():
        return state.strip()
    return "missing"


def redact_profile_archive_root(archive_root: str | None, *, redact_local_paths: bool) -> str | None:
    if not archive_root:
        return None
    return "<local-path-redacted>" if redact_local_paths else archive_root


def redacted_path_value(path: Path, *, redact_local_paths: bool) -> str:
    return "<local-path-redacted>" if redact_local_paths else str(path)


def runtime_context(
    archive_root: Path | str,
    *,
    expected_archive_id: str | None = None,
    expected_type: str | None = None,
    strict: bool = False,
    redact_local_paths: bool = True,
    diagnostics: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    blockers: list[str] = []
    warnings: list[str] = []

    if expected_type is not None and expected_type not in RUNTIME_CONTEXT_ARCHIVE_TYPES:
        raise ArchiveServiceError("expected archive type must be one of: " + ", ".join(sorted(RUNTIME_CONTEXT_ARCHIVE_TYPES)))

    archive_config = load_runtime_context_yaml(root, "archive.yml", blockers, required=True)
    identity_doc = load_runtime_context_yaml(root, "archive-identity.yml", warnings, required=False)

    archive_id = archive_config.get("archive_id") if isinstance(archive_config.get("archive_id"), str) else None
    archive_type = archive_config.get("type") if isinstance(archive_config.get("type"), str) else None
    identity = identity_doc.get("identity") if isinstance(identity_doc.get("identity"), dict) else {}
    scope = identity.get("scope") if isinstance(identity.get("scope"), str) else None

    if archive_id is None:
        blockers.append("archive.yml does not contain a readable archive_id.")
    elif expected_archive_id and archive_id != expected_archive_id:
        blockers.append(f"Expected archive id {expected_archive_id}, found {archive_id}.")

    if expected_type:
        found_types = {item for item in [archive_type, scope] if item}
        if expected_type not in found_types:
            message = runtime_type_mismatch_message(expected_type, archive_type, scope)
            if strict:
                blockers.append(message)
            else:
                warnings.append(message)

    doctor_summary = runtime_context_doctor_summary(diagnostics, strict=strict, blockers=blockers, warnings=warnings)
    paths = runtime_context_paths(root, archive_config, warnings)
    if strict and warnings:
        blockers.extend(warnings)
        warnings = []

    result: dict[str, Any] = {
        "ok": not blockers,
        "lifecycle_action": "runtime_context",
        "archive_id": archive_id,
        "archive_type": archive_type,
        "scope": scope,
        "principal": runtime_context_principal_summary(archive_config, identity_doc),
        "owner": runtime_context_owner_summary(identity_doc),
        "ai_write_policy": runtime_context_ai_write_policy_summary(archive_config),
        "paths": paths,
        "available_safe_actions": list(RUNTIME_CONTEXT_SAFE_ACTIONS),
        "doctor_summary": doctor_summary,
        "blockers": unique_preserve_order(blockers),
        "warnings": unique_preserve_order(warnings),
        "redaction": {
            "local_paths_redacted": bool(redact_local_paths),
        },
    }
    if not redact_local_paths:
        result["local_archive_root"] = str(root)
        result["local_paths"] = runtime_context_local_paths(root, paths)
    return result


def load_runtime_context_yaml(root: Path, relative_path: str, messages: list[str], *, required: bool) -> dict[str, Any]:
    try:
        data = load_yaml(read_archive_text(root, relative_path))
    except ArchiveServiceError as exc:
        if required:
            messages.append(f"{relative_path} could not be read: {exc}")
        return {}
    except Exception as exc:
        if required:
            messages.append(f"{relative_path} could not be parsed as YAML: {exc}")
        else:
            messages.append(f"{relative_path} could not be parsed as YAML.")
        return {}
    if not isinstance(data, dict):
        messages.append(f"{relative_path} must be a YAML object.")
        return {}
    return json_safe(data)


def runtime_type_mismatch_message(expected_type: str, archive_type: str | None, scope: str | None) -> str:
    found_values = unique_preserve_order([item for item in [archive_type, scope] if item])
    found = ", ".join(found_values) or "unknown"
    return f"Expected archive type {expected_type}, found {found}."


def runtime_context_doctor_summary(
    diagnostics: list[dict[str, Any]] | None,
    *,
    strict: bool,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    if diagnostics is None:
        return {"checked": False, "errors": 0, "warnings": 0, "infos": 0}
    errors = sum(1 for item in diagnostics if item.get("severity") == "ERROR")
    warning_count = sum(1 for item in diagnostics if item.get("severity") == "WARN")
    infos = sum(1 for item in diagnostics if item.get("severity") == "INFO")
    if errors:
        blockers.append(f"archive doctor reported {errors} error(s).")
    if warning_count:
        message = f"archive doctor reported {warning_count} warning(s)."
        if strict:
            blockers.append(message)
        else:
            warnings.append(message)
    return {"checked": True, "errors": errors, "warnings": warning_count, "infos": infos}


def runtime_context_paths(root: Path, archive_config: dict[str, Any], warnings: list[str]) -> dict[str, str | None]:
    root_policy = archive_config.get("root_policy") if isinstance(archive_config.get("root_policy"), dict) else {}
    return {
        "inbox": runtime_context_relative_path(root, root_policy.get("ai_inbox"), "inbox/", warnings, "inbox", directory=True),
        "zettels": runtime_context_relative_path(root, root_policy.get("canonical_zettels"), "zettels/", warnings, "zettels", directory=True),
        "receipts": runtime_context_relative_path(root, None, "receipts/", warnings, "receipts", directory=True),
        "object_manifest": runtime_context_relative_path(
            root,
            root_policy.get("object_manifest"),
            "objects/manifests/files.jsonl",
            warnings,
            "object manifest",
            directory=False,
            only_if_exists=True,
        ),
    }


def runtime_context_relative_path(
    root: Path,
    raw_path: Any,
    fallback: str,
    warnings: list[str],
    label: str,
    *,
    directory: bool,
    only_if_exists: bool = False,
) -> str | None:
    relative = str(raw_path or fallback)
    try:
        path = resolve_archive_relative_path(root, relative)
    except ArchivePathError:
        warnings.append(f"{label} path is unsafe in archive.yml; using {fallback}.")
        path = resolve_archive_relative_path(root, fallback)
    if only_if_exists and not path.exists():
        return None
    display = archive_relative_path(path, root)
    if directory and not display.endswith("/"):
        display += "/"
    return display


def runtime_context_local_paths(root: Path, paths: dict[str, str | None]) -> dict[str, str | None]:
    local_paths: dict[str, str | None] = {}
    for key, relative in paths.items():
        if relative is None:
            local_paths[key] = None
            continue
        normalized = relative.rstrip("/")
        local_paths[key] = str(resolve_archive_relative_path(root, normalized))
    return local_paths


def runtime_context_principal_summary(archive_config: dict[str, Any], identity_doc: dict[str, Any]) -> dict[str, Any]:
    principal = archive_config.get("principal") if isinstance(archive_config.get("principal"), dict) else {}
    identity = identity_doc.get("identity") if isinstance(identity_doc.get("identity"), dict) else {}
    return {
        "principal_id": identity.get("principal_id") or principal.get("principal_id"),
        "display_name": identity.get("display_name") or principal.get("display_name"),
        "kind": principal.get("kind"),
        "identity_id": identity.get("identity_id"),
    }


def runtime_context_owner_summary(identity_doc: dict[str, Any]) -> dict[str, Any]:
    ownership = identity_doc.get("ownership") if isinstance(identity_doc.get("ownership"), dict) else {}
    operators = ownership.get("operators") if isinstance(ownership.get("operators"), list) else []
    subjects = ownership.get("subjects") if isinstance(ownership.get("subjects"), list) else []
    return {
        "owner_id": ownership.get("owner_id"),
        "owner_kind": ownership.get("owner_kind"),
        "owner_display_name": ownership.get("owner_display_name"),
        "owner_archive_id": ownership.get("owner_archive_id"),
        "operator_count": len(operators),
        "subject_count": len(subjects),
    }


def runtime_context_ai_write_policy_summary(archive_config: dict[str, Any]) -> dict[str, Any]:
    policy = archive_config.get("ai_write_policy") if isinstance(archive_config.get("ai_write_policy"), dict) else {}
    default = policy.get("default")
    canonical_requires = policy.get("canonical_requires")
    summary = "unavailable"
    if default or canonical_requires:
        summary = f"default={default or 'unknown'}; canonical_requires={canonical_requires or 'unknown'}"
    return {
        "default": default,
        "canonical_requires": canonical_requires,
        "summary": summary,
    }


def source_mount_step(binding: dict[str, Any], *, local_profile_present: bool) -> dict[str, Any]:
    source_id = str(binding.get("source_id") or "")
    source_type = str(binding.get("source_type") or "")
    root_ref = str(binding.get("root_ref") or "")
    container_root = f"/sources/{safe_slug(source_id)}"
    archive_relative = root_ref.startswith("archive:") or source_type == "object_manifest"
    if archive_relative:
        container_root = root_ref.removeprefix("archive:") if root_ref.startswith("archive:") else "objects/manifests/files.jsonl"
    docker_command = f"docker compose run --rm archive-cli scan-source /archives/<archive-folder> --source {source_id} --dry-run"
    if not archive_relative:
        docker_command = f"docker compose run --rm archive-cli scan-source /archives/<archive-folder> --source {source_id} --source-root {container_root} --dry-run"
    return {
        "source_id": source_id,
        "source_type": source_type,
        "root_ref": root_ref,
        "enabled": binding.get("enabled") is not False,
        "needs_host_mount": not archive_relative,
        "local_profile_present": local_profile_present,
        "container_source_root": container_root,
        "compose_volume_hint": None
        if archive_relative
        else f"${{{root_ref}}}:{container_root}:ro",
        "host_native_scan_command": f"archive scan-source <archive> --source {source_id} --dry-run",
        "docker_scan_command": docker_command,
        "manual_required": not archive_relative,
    }


def load_source_map_entries(archive_root: Path, relative_path: str) -> list[dict[str, Any]]:
    path = archive_internal_path(archive_root, relative_path)
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            entries.append(record)
    return entries


def source_intake_plan(
    archive_root: Path | str,
    *,
    local_path: Path | str | None = None,
    source_id: str | None = None,
    item_id: str | None = None,
    relative_path: str | None = None,
    objet_ref: str | None = None,
    object_id: str | None = None,
    provider: str | None = None,
    provider_object_id: str | None = None,
    provider_kind: str | None = None,
    ai_artifact_ref: str | None = None,
    runtime: str | None = None,
    artifact_kind: str | None = None,
    expected_archive_id: str | None = None,
    expected_type: str | None = None,
    profile_id: str | None = None,
    source_role: str = SOURCE_INTAKE_DEFAULT_ROLE,
    title: str | None = None,
    mime: str | None = None,
    redact_local_paths: bool = True,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_config = read_archive_config(root)
    archive_id = str(archive_config.get("archive_id") or "")
    archive_type = archive_config.get("type") if isinstance(archive_config.get("type"), str) else None
    blockers: list[str] = []
    warnings: list[str] = []

    if expected_archive_id and expected_archive_id != archive_id:
        blockers.append(f"Expected archive id mismatch: expected {expected_archive_id}, found {archive_id or 'unknown'}.")
    if expected_type and expected_type != archive_type:
        blockers.append(f"Expected archive type mismatch: expected {expected_type}, found {archive_type or 'unknown'}.")

    role = (source_role or SOURCE_INTAKE_DEFAULT_ROLE).strip()
    if role not in SOURCE_INTAKE_ROLES:
        blockers.append("source_role must be one of: " + ", ".join(sorted(SOURCE_INTAKE_ROLES)) + ".")
        role = SOURCE_INTAKE_DEFAULT_ROLE

    for field_name, field_value in {
        "profile_id": profile_id,
        "title": title,
        "mime": mime,
    }.items():
        if field_value and not safe_source_intake_text(str(field_value)):
            blockers.append(f"{field_name} must not contain local paths, provider URLs, tokens, or secrets.")

    locator_kinds = source_intake_locator_kinds(
        local_path=local_path,
        source_id=source_id,
        item_id=item_id,
        relative_path=relative_path,
        objet_ref=objet_ref,
        object_id=object_id,
        provider=provider,
        provider_object_id=provider_object_id,
        provider_kind=provider_kind,
        ai_artifact_ref=ai_artifact_ref,
        runtime=runtime,
        artifact_kind=artifact_kind,
        blockers=blockers,
    )
    input_kind = locator_kinds[0] if len(locator_kinds) == 1 else None
    if len(locator_kinds) != 1:
        blockers.append("Exactly one source locator mode is required.")

    result_body = source_intake_empty_body(
        archive_id=archive_id,
        profile_id=profile_id,
        input_kind=input_kind,
        source_role=role,
        object_storage_context=object_storage_context(root),
    )

    if input_kind == "local_path":
        apply_local_path_source_intake(
            root,
            result_body,
            Path(str(local_path)),
            title=title,
            mime=mime,
            source_role=role,
            redact_local_paths=redact_local_paths,
            blockers=blockers,
            warnings=warnings,
        )
    elif input_kind == "source_map_item":
        apply_source_map_item_source_intake(
            root,
            result_body,
            source_id=str(source_id or ""),
            item_id=str(item_id or ""),
            relative_path=None,
            title=title,
            mime=mime,
            source_role=role,
            blockers=blockers,
            warnings=warnings,
        )
    elif input_kind == "source_map_relative_path":
        apply_source_map_item_source_intake(
            root,
            result_body,
            source_id=str(source_id or ""),
            item_id=None,
            relative_path=str(relative_path or ""),
            title=title,
            mime=mime,
            source_role=role,
            blockers=blockers,
            warnings=warnings,
        )
    elif input_kind == "objet_ref":
        resolved_object_id = object_id_from_objet_ref(str(objet_ref or ""), blockers)
        apply_manifest_object_source_intake(
            root,
            result_body,
            resolved_object_id,
            title=title,
            mime=mime,
            source_role=role,
            direct_lookup=True,
            blockers=blockers,
            warnings=warnings,
        )
    elif input_kind == "object_id":
        normalized_object_id = normalize_object_id(str(object_id or ""), blockers)
        apply_manifest_object_source_intake(
            root,
            result_body,
            normalized_object_id,
            title=title,
            mime=mime,
            source_role=role,
            direct_lookup=True,
            blockers=blockers,
            warnings=warnings,
        )
    elif input_kind == "provider_object":
        apply_provider_object_source_intake(
            result_body,
            provider=str(provider or ""),
            provider_object_id=str(provider_object_id or ""),
            provider_kind=str(provider_kind or ""),
            title=title,
            mime=mime,
            source_role=role,
            blockers=blockers,
        )
    elif input_kind == "ai_artifact":
        apply_ai_artifact_source_intake(
            result_body,
            ai_artifact_ref=str(ai_artifact_ref or ""),
            runtime=str(runtime or ""),
            artifact_kind=str(artifact_kind or ""),
            title=title,
            mime=mime,
            source_role=role,
            blockers=blockers,
        )

    if not result_body["object_storage_context"]["object_storage_configured"]:
        warnings.append("Run the object storage / objet setup planner before real objet capture.")

    if blockers:
        result_body["objet_status"] = "blocked"
    result_body["ok"] = not blockers
    result_body["blockers"] = unique_preserve_order(blockers)
    result_body["warnings"] = unique_preserve_order(warnings)
    result_body["next_safe_actions"] = source_intake_next_safe_actions(result_body)
    return json_safe(result_body)


def source_intake_empty_body(
    *,
    archive_id: str,
    profile_id: str | None,
    input_kind: str | None,
    source_role: str,
    object_storage_context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": True,
        "dry_run": True,
        "lifecycle_action": "source_intake_plan",
        "archive_id": archive_id,
        "profile_id": profile_id,
        "input_kind": input_kind,
        "source_kind": None,
        "source_role": source_role,
        "objet_status": None,
        "source_refs_for_draft": [],
        "objet_ref": {},
        "provider_object_ref": {},
        "object_storage_context": object_storage_context,
        "content_access": {
            "metadata_only": True,
            "content_read": False,
            "copied": False,
            "uploaded": False,
            "imported": False,
            "ocr_performed": False,
            "transcription_performed": False,
            "external_api_called": False,
            "full_hash_calculated": False,
        },
        "draft_provenance_suggestions": {},
        "source_metadata": {},
        "blockers": [],
        "warnings": [],
        "next_safe_actions": [],
        "would_change": [],
    }


def source_intake_locator_kinds(
    *,
    local_path: Path | str | None,
    source_id: str | None,
    item_id: str | None,
    relative_path: str | None,
    objet_ref: str | None,
    object_id: str | None,
    provider: str | None,
    provider_object_id: str | None,
    provider_kind: str | None,
    ai_artifact_ref: str | None,
    runtime: str | None,
    artifact_kind: str | None,
    blockers: list[str],
) -> list[str]:
    kinds: list[str] = []
    if local_path is not None:
        kinds.append("local_path")
    if source_id and item_id:
        kinds.append("source_map_item")
    if source_id and relative_path:
        kinds.append("source_map_relative_path")
    if objet_ref:
        kinds.append("objet_ref")
    if object_id:
        kinds.append("object_id")
    if provider or provider_object_id or provider_kind:
        kinds.append("provider_object")
        if not (provider and provider_object_id and provider_kind):
            blockers.append("Provider locator requires --provider, --provider-object-id, and --provider-kind.")
    if ai_artifact_ref or runtime or artifact_kind:
        kinds.append("ai_artifact")
        if not (ai_artifact_ref and runtime and artifact_kind):
            blockers.append("AI artifact locator requires --ai-artifact-ref, --runtime, and --artifact-kind.")
    if source_id and not (item_id or relative_path):
        blockers.append("Source locator requires --item-id or --relative-path.")
    if (item_id or relative_path) and not source_id:
        blockers.append("Source locator requires --source.")
    return kinds


def apply_local_path_source_intake(
    root: Path,
    result: dict[str, Any],
    local_path: Path,
    *,
    title: str | None,
    mime: str | None,
    source_role: str,
    redact_local_paths: bool,
    blockers: list[str],
    warnings: list[str],
) -> None:
    raw_path = str(local_path)
    if "\x00" in raw_path or source_intake_has_provider_url(raw_path) or source_intake_secret_like(raw_path):
        blockers.append("local_path must be a local file path, not a provider URL, token, or secret.")
        result["objet_status"] = "blocked"
        return
    candidate = local_path.expanduser().resolve()
    if not candidate.exists():
        blockers.append("local_path does not exist.")
        result["objet_status"] = "blocked"
        return
    if not candidate.is_file():
        blockers.append("local_path must point to a file for source intake planning.")
        result["objet_status"] = "blocked"
        return

    stat = candidate.stat()
    guessed_mime = safe_mime(mime or mimetypes.guess_type(candidate.name)[0])
    label = safe_source_label(title, candidate.name, redact_local_paths)
    result["source_kind"] = classify_source_kind(guessed_mime, candidate.suffix)
    result["source_metadata"] = {
        "label": label,
        "extension": candidate.suffix.lower(),
        "mime": guessed_mime,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone().replace(microsecond=0).isoformat(),
        "local_path": "<redacted-local-path>" if redact_local_paths else str(candidate),
        "body_read": False,
        "full_hash_calculated": False,
    }

    manifest_record = manifest_record_for_local_path(root, candidate)
    if manifest_record:
        set_manifest_object_intake_result(result, manifest_record, source_role=source_role, title=title, mime=mime)
    else:
        result["objet_status"] = "candidate_unmanifested"
        result["source_refs_for_draft"] = [
            {"type": "source_intake_candidate", "value": f"candidate:{safe_slug(label)}", "role": source_role}
        ]
        result["draft_provenance_suggestions"] = {
            "source": "source_intake_candidate",
            "derived_from": [f"candidate:{safe_slug(label)}"],
        }

    if not local_path_inside_registered_source_root(root, candidate):
        warnings.append("Local file is outside registered source roots; register or scan the source before real objet capture.")
    if candidate.suffix.lower() in {".md", ".markdown", ".txt"}:
        warnings.append(".md/.txt files may already be zets or text notes; confirm whether this is an objet before capture.")


def apply_source_map_item_source_intake(
    root: Path,
    result: dict[str, Any],
    *,
    source_id: str,
    item_id: str | None,
    relative_path: str | None,
    title: str | None,
    mime: str | None,
    source_role: str,
    blockers: list[str],
    warnings: list[str],
) -> None:
    if source_intake_secret_like(source_id) or contains_forbidden_location_reference(source_id):
        blockers.append("source must not contain local paths, provider URLs, tokens, or secrets.")
        return
    if relative_path:
        try:
            normalized_relative = normalize_source_intake_relative_path(relative_path)
        except ArchivePathError as exc:
            blockers.append(f"relative_path is unsafe: {exc}.")
            return
    else:
        normalized_relative = None
    try:
        binding = source_binding_by_id(root, source_id)
    except ArchiveServiceError as exc:
        blockers.append(str(exc))
        return
    map_relative = source_map_relative_path(source_id)
    entries = load_source_map_entries(root, map_relative)
    match: dict[str, Any] | None = None
    for entry in entries:
        if item_id and str(entry.get("item_id") or "") == item_id:
            match = entry
            break
        if normalized_relative and str(entry.get("relative_path") or "").replace("\\", "/") == normalized_relative:
            match = entry
            break
    if match is None:
        blockers.append("Source map item was not found.")
        return

    source_mime = safe_mime(mime or str(match.get("mime") or ""))
    label = safe_source_map_label(title, match)
    result["source_kind"] = classify_source_kind(source_mime, str(match.get("relative_path") or ""))
    result["source_metadata"] = {
        "label": label,
        "source_id": source_id,
        "source_type": binding.get("source_type"),
        "source_map_path": map_relative,
        "item_id": match.get("item_id"),
        "item_kind": match.get("item_kind"),
        "relative_path": match.get("relative_path"),
        "mime": source_mime,
        "size_bytes": match.get("size_bytes"),
        "modified_at": match.get("modified_at"),
        "scan_status": match.get("scan_status"),
    }
    object_id_value = str(match.get("object_id") or "").strip()
    if object_id_value:
        normalized = normalize_object_id(object_id_value, blockers)
        record = find_manifest_record(root, normalized)
        if record:
            set_manifest_object_intake_result(result, record, source_role=source_role, title=title, mime=mime)
        else:
            result["objet_status"] = "candidate_unmanifested"
            warnings.append("Source map item has an object_id, but the object manifest record was not found.")
            result["objet_ref"] = {"ref": f"objet:{normalized}", "object_id": normalized, "manifested": False}
            result["source_refs_for_draft"] = [{"type": "object_id", "value": normalized, "role": source_role}]
        result["source_refs_for_draft"].append(
            {"type": "source_map_item", "value": str(match.get("item_id") or item_id or normalized_relative), "role": "supporting_context"}
        )
    else:
        result["objet_status"] = "candidate_unmanifested"
        source_item_value = str(match.get("item_id") or normalized_relative or "")
        result["source_refs_for_draft"] = [{"type": "source_map_item", "value": source_item_value, "role": source_role}]
        result["draft_provenance_suggestions"] = {
            "source": "source_map_item",
            "derived_from": [source_item_value],
        }

    if str(match.get("relative_path") or "").lower().endswith((".md", ".markdown", ".txt")):
        warnings.append(".md/.txt files may already be zets or text notes; confirm whether this is an objet before capture.")


def apply_manifest_object_source_intake(
    root: Path,
    result: dict[str, Any],
    object_id_value: str,
    *,
    title: str | None,
    mime: str | None,
    source_role: str,
    direct_lookup: bool,
    blockers: list[str],
    warnings: list[str],
) -> None:
    if not object_id_value:
        return
    record = find_manifest_record(root, object_id_value)
    if record is None:
        if direct_lookup:
            blockers.append("object_id or objet_ref does not resolve to objects/manifests/files.jsonl.")
        result["objet_status"] = "blocked"
        return
    set_manifest_object_intake_result(result, record, source_role=source_role, title=title, mime=mime)
    if str(record.get("logical_key") or "").lower().endswith((".md", ".markdown", ".txt")):
        warnings.append(".md/.txt manifest records may already be zets or text notes; confirm whether this is an objet.")


def apply_provider_object_source_intake(
    result: dict[str, Any],
    *,
    provider: str,
    provider_object_id: str,
    provider_kind: str,
    title: str | None,
    mime: str | None,
    source_role: str,
    blockers: list[str],
) -> None:
    if not safe_source_intake_ref(provider) or not safe_source_intake_ref(provider_object_id) or not safe_source_intake_artifact_kind(provider_kind):
        blockers.append("provider, provider_object_id, and provider_kind must be safe refs, not URLs, paths, tokens, or secrets.")
        return
    source_mime = safe_mime(mime)
    label = title.strip() if isinstance(title, str) and title.strip() else provider_object_id
    value = f"{provider}:{provider_kind}:{provider_object_id}"
    result["source_kind"] = "provider_item"
    result["objet_status"] = "provider_reference"
    result["provider_object_ref"] = {
        "provider": provider,
        "provider_kind": provider_kind,
        "provider_object_id": provider_object_id,
        "manifested": False,
    }
    result["source_metadata"] = {
        "label": label,
        "mime": source_mime,
        "provider": provider,
        "provider_kind": provider_kind,
    }
    result["source_refs_for_draft"] = [{"type": "provider_object_ref", "value": value, "role": source_role}]
    result["draft_provenance_suggestions"] = {
        "source": "provider_object_ref",
        "derived_from": [value],
    }


def apply_ai_artifact_source_intake(
    result: dict[str, Any],
    *,
    ai_artifact_ref: str,
    runtime: str,
    artifact_kind: str,
    title: str | None,
    mime: str | None,
    source_role: str,
    blockers: list[str],
) -> None:
    normalized_runtime = runtime.strip()
    if normalized_runtime not in SOURCE_INTAKE_RUNTIMES:
        blockers.append("runtime must be one of: " + ", ".join(sorted(SOURCE_INTAKE_RUNTIMES)) + ".")
    if not safe_source_intake_ref(ai_artifact_ref):
        blockers.append("ai_artifact_ref must be a safe ref, not a URL, path, token, or secret.")
    if not safe_source_intake_artifact_kind(artifact_kind):
        blockers.append("artifact_kind must be a safe label.")
    if blockers:
        return
    source_mime = safe_mime(mime)
    label = title.strip() if isinstance(title, str) and title.strip() else ai_artifact_ref
    result["source_kind"] = "ai_artifact"
    result["objet_status"] = "ai_artifact"
    result["source_metadata"] = {
        "label": label,
        "runtime": normalized_runtime,
        "artifact_kind": artifact_kind,
        "mime": source_mime,
    }
    result["source_refs_for_draft"] = [{"type": "ai_artifact", "value": ai_artifact_ref, "role": source_role}]
    result["draft_provenance_suggestions"] = {
        "source": "ai_artifact",
        "assisted_by": [f"ai_runtime:{normalized_runtime}"],
        "derived_from": [ai_artifact_ref],
    }


def set_manifest_object_intake_result(
    result: dict[str, Any],
    record: dict[str, Any],
    *,
    source_role: str,
    title: str | None,
    mime: str | None,
) -> None:
    object_id_value = str(record.get("object_id") or "")
    source_mime = safe_mime(mime or str(record.get("mime") or ""))
    logical_key = str(record.get("logical_key") or "")
    result["source_kind"] = classify_source_kind(source_mime, logical_key)
    result["objet_status"] = "manifested"
    result["objet_ref"] = {
        "ref": f"objet:{object_id_value}",
        "object_id": object_id_value,
        "manifested": True,
        "manifest_path": "objects/manifests/files.jsonl",
        "logical_key": logical_key or None,
        "mime": source_mime,
        "size_bytes": record.get("size_bytes") if isinstance(record.get("size_bytes"), int) else None,
    }
    existing_metadata = result["source_metadata"] if isinstance(result.get("source_metadata"), dict) else {}
    existing_label = existing_metadata.get("label") if isinstance(existing_metadata.get("label"), str) else None
    label = title.strip() if isinstance(title, str) and title.strip() else existing_label or logical_key or object_id_value
    result["source_metadata"] = {
        **existing_metadata,
        "label": label,
        "logical_key": logical_key or None,
        "mime": source_mime,
        "size_bytes": record.get("size_bytes") if isinstance(record.get("size_bytes"), int) else None,
    }
    result["source_refs_for_draft"] = [{"type": "object_id", "value": object_id_value, "role": source_role}]
    result["draft_provenance_suggestions"] = {
        "source": "object_manifest",
        "derived_from": [object_id_value],
    }


def source_intake_next_safe_actions(result: dict[str, Any]) -> list[str]:
    status = result.get("objet_status")
    actions = ["create-draft --dry-run with source_refs_for_draft", "mint only through separate human approval"]
    if status == "manifested":
        return actions
    if status == "candidate_unmanifested":
        return [
            "register or scan the source in metadata-only mode if needed",
            "run the object storage / objet setup planner before real objet capture",
            "wait for a future explicit objet capture/import flow before canonical object_id citation",
            *actions,
        ]
    if status == "provider_reference":
        return [
            "export or register provider metadata without storing raw provider URLs",
            "wait for a future provider capture/import flow before canonical object_id citation",
            *actions,
        ]
    if status == "ai_artifact":
        return [
            "keep the AI artifact ref as provenance context",
            *actions,
        ]
    return []


def object_storage_context(root: Path) -> dict[str, Any]:
    provider_doc = load_provider_bindings(root)
    candidates: list[dict[str, Any]] = []
    for binding in provider_bindings_list(provider_doc):
        provider = str(binding.get("provider") or "")
        provider_kind = str(binding.get("provider_kind") or "")
        resource = binding.get("resource") if isinstance(binding.get("resource"), dict) else {}
        if provider.lower() not in SOURCE_INTAKE_OBJECT_STORAGE_PROVIDERS and provider_kind.lower() not in SOURCE_INTAKE_OBJECT_STORAGE_PROVIDERS:
            continue
        candidates.append(
            drop_none_values(
                {
                    "binding_id": binding.get("binding_id"),
                    "provider": provider,
                    "provider_kind": provider_kind or None,
                    "bucket": resource.get("bucket"),
                    "prefix": resource.get("prefix"),
                    "visibility": resource.get("visibility"),
                    "enabled": binding.get("enabled") is not False,
                }
            )
        )
    configured = any(item.get("enabled") for item in candidates)
    return {
        "object_storage_configured": configured,
        "candidate_storage_providers": candidates,
        "manual_setup_required": not configured,
        "upload_performed": False,
        "provider_api_called": False,
    }


def normalize_object_id(value: str, blockers: list[str]) -> str:
    text = value.strip().lower()
    if SHA256_RE.match(text):
        text = f"sha256:{text}"
    if not OBJECT_ID_RE.match(text):
        blockers.append("object_id must be formatted as sha256:<64 lowercase hex characters>.")
        return ""
    return text


def object_id_from_objet_ref(value: str, blockers: list[str]) -> str:
    text = value.strip().lower()
    if not text.startswith("objet:"):
        blockers.append("objet_ref must be formatted as objet:sha256:<64 lowercase hex characters>.")
        return ""
    return normalize_object_id(text.removeprefix("objet:"), blockers)


def find_manifest_record(root: Path, object_id_value: str) -> dict[str, Any] | None:
    if not object_id_value:
        return None
    for record in load_manifest_records(root):
        if str(record.get("object_id") or "").lower() == object_id_value.lower():
            return record
    return None


def manifest_record_for_local_path(root: Path, candidate: Path) -> dict[str, Any] | None:
    relative: str | None = None
    try:
        if candidate.resolve().is_relative_to(root.resolve()):
            relative = archive_relative_path(candidate, root)
    except (OSError, RuntimeError, ValueError, ArchivePathError):
        relative = None
    if not relative:
        return None
    for record in load_manifest_records(root):
        if record.get("logical_key") == relative:
            return record
        locations = record.get("locations")
        if isinstance(locations, list):
            for location in locations:
                if isinstance(location, dict) and location.get("path") == relative:
                    return record
    return None


def local_path_inside_registered_source_root(root: Path, candidate: Path) -> bool:
    for binding in source_bindings_list(load_source_bindings(root)):
        source_id = str(binding.get("source_id") or "")
        root_ref = str(binding.get("root_ref") or "")
        roots: list[Path] = []
        if root_ref.startswith("archive:"):
            try:
                roots.append(archive_internal_path(root, root_ref.removeprefix("archive:")))
            except ArchiveServiceError:
                pass
        elif root_ref and os.environ.get(root_ref):
            roots.append(Path(os.environ[root_ref]).expanduser().resolve())
        local_profile_root = local_source_root_path(root, source_id)
        if local_profile_root is not None:
            roots.append(local_profile_root)
        for source_root in roots:
            try:
                if candidate.resolve().is_relative_to(source_root.resolve()):
                    return True
            except (OSError, RuntimeError, ValueError):
                continue
    return False


def normalize_source_intake_relative_path(value: str) -> str:
    normalized = normalize_archive_relative_path(value)
    if contains_forbidden_location_reference(normalized) or source_intake_secret_like(normalized):
        raise ArchivePathError("relative path must not contain provider URLs, local paths, tokens, or secrets")
    return normalized


def safe_source_label(title: str | None, filename: str, redact_local_paths: bool) -> str:
    if isinstance(title, str) and title.strip():
        return title.strip()
    suffix = Path(filename).suffix.lower()
    if redact_local_paths:
        return f"local-file{suffix}" if suffix else "local-file"
    return filename


def safe_source_map_label(title: str | None, item: dict[str, Any]) -> str:
    if isinstance(title, str) and title.strip():
        return title.strip()
    item_title = item.get("title")
    if isinstance(item_title, str) and item_title.strip():
        return item_title.strip()
    relative = item.get("relative_path")
    if isinstance(relative, str) and relative.strip():
        return Path(relative.replace("\\", "/")).name
    item_id = item.get("item_id")
    return str(item_id or "source-map-item")


def safe_mime(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9.+-]{0,99}/[A-Za-z0-9][A-Za-z0-9.+-]{0,99}$", text):
        return None
    if source_intake_secret_like(text) or contains_forbidden_location_reference(text):
        return None
    return text


def classify_source_kind(mime: str | None, path_or_ext: str | None = None) -> str:
    suffix = Path(path_or_ext or "").suffix.lower()
    if mime:
        if mime.startswith("image/"):
            return "image"
        if mime.startswith("audio/"):
            return "audio"
        if mime.startswith("video/"):
            return "video"
        if mime in {"application/pdf"}:
            return "document"
        if mime.startswith("text/"):
            return "text"
    if suffix in {".ppt", ".pptx"}:
        return "presentation"
    if suffix in {".xls", ".xlsx", ".csv"}:
        return "spreadsheet"
    if suffix in {".pdf", ".doc", ".docx", ".hwp", ".hwpx", ".odt", ".rtf"}:
        return "document"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic"}:
        return "image"
    if suffix in {".mp3", ".wav", ".m4a", ".flac", ".ogg"}:
        return "audio"
    if suffix in {".mp4", ".mov", ".mkv", ".webm"}:
        return "video"
    if suffix in {".md", ".markdown", ".txt"}:
        return "text"
    return "file"


def safe_source_intake_text(value: str) -> bool:
    return not (contains_forbidden_location_reference(value) or DRAFT_SECRET_VALUE_RE.search(value) or source_intake_secret_like(value))


def safe_source_intake_ref(value: str) -> bool:
    text = value.strip()
    if not text or not text.isascii():
        return False
    if "@" in text or "://" in text or "\\" in text or "/" in text or "#" in text or "?" in text or "\x00" in text:
        return False
    if contains_forbidden_location_reference(text) or source_intake_secret_like(text):
        return False
    return bool(SOURCE_INTAKE_SAFE_REF_RE.match(text))


def safe_source_intake_artifact_kind(value: str) -> bool:
    text = value.strip()
    if not text or not text.isascii():
        return False
    if contains_forbidden_location_reference(text) or source_intake_secret_like(text):
        return False
    return bool(SOURCE_INTAKE_ARTIFACT_KIND_RE.match(text))


def source_intake_has_provider_url(value: str) -> bool:
    return bool(re.search(r"(?i)\b(?:s3|b2|r2|gs)://|://", value))


def source_intake_secret_like(value: str) -> bool:
    return bool(DRAFT_SECRET_VALUE_RE.search(value) or GITHUB_SECRET_LIKE_RE.search(value))


def source_scan_dry_run(
    archive_root: Path | str,
    *,
    source_id: str,
    source_root: Path | str | None = None,
    limit: int = 2000,
) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    archive_id = read_archive_id(root)
    binding = source_binding_by_id(root, source_id)
    source_type = str(binding.get("source_type") or "")
    if source_type not in SOURCE_TYPES:
        raise ArchiveServiceError("source_type must be one of: " + ", ".join(sorted(SOURCE_TYPES)))
    limit = max(1, min(int(limit), 10000))
    scope_policy = binding.get("scope_policy") if isinstance(binding.get("scope_policy"), dict) else {}
    policy_max = scope_policy.get("max_items")
    if isinstance(policy_max, int):
        limit = min(limit, max(1, min(policy_max, 10000)))

    blockers: list[str] = []
    warnings: list[str] = []
    if binding.get("enabled") is False:
        blockers.append(f"Source is disabled in source-bindings.yml: {source_id}.")

    resolved_root, root_resolution = resolve_source_scan_root(root, binding, source_root, blockers, warnings)
    scan_now = datetime.now().astimezone().replace(microsecond=0).isoformat()
    items: list[dict[str, Any]] = []
    if not blockers:
        items = discover_source_map_items(
            archive_root=root,
            binding=binding,
            resolved_root=resolved_root,
            scanned_at=scan_now,
            limit=limit,
            warnings=warnings,
        )
        items = [drop_none_values(item) for item in items]
        if not items:
            warnings.append(f"Source scan found no metadata items: {source_id}.")

    source_map_path = source_map_relative_path(source_id)
    fingerprint = source_scan_fingerprint(source_id, source_type, items)
    proposed_receipt_path = source_scan_receipt_relative_path(source_id, fingerprint)
    if archive_internal_path(root, proposed_receipt_path).exists():
        blockers.append(f"Proposed source scan receipt already exists: {proposed_receipt_path}.")

    scope_gate = {
        "unit": "source",
        "source_id": source_id,
        "source_type": source_type,
        "scan_mode": SOURCE_SCAN_MODE,
        "metadata_only": True,
        "content_read": False,
        "full_hash_calculated": False,
        "root_ref": binding.get("root_ref"),
        "item_count": len(items),
        "limit": limit,
    }
    trust_gate = {
        "required": False,
        "ok": True,
        "status": "local_or_export_metadata_only",
        "external_api_called": False,
        "secret_values_required": False,
    }
    lineage = {
        "event": "source_scan",
        "source_archive": archive_id,
        "source_id": source_id,
        "source_type": source_type,
        "scan_mode": SOURCE_SCAN_MODE,
    }
    receipt_preview = {
        "receipt_id": f"receipt:source-scan:{safe_slug(archive_id)}:{safe_slug(source_id)}:{fingerprint}",
        "receipt_path": proposed_receipt_path,
        "action": "scan_archive_source",
        "dry_run": True,
        "timestamp": "<execution-time>",
        "source_archive": archive_id,
        "source_id": source_id,
        "source_type": source_type,
        "scan_mode": SOURCE_SCAN_MODE,
        "source_root_resolution": root_resolution,
        "item_count": len(items),
        "source_map_path": source_map_path,
        "scope_gate": scope_gate,
        "trust_gate": trust_gate,
        "lineage": lineage,
        "blockers": blockers,
        "warnings": warnings,
    }
    return {
        "ok": not blockers,
        "dry_run": True,
        "action": "scan_archive_source",
        "source_archive": archive_id,
        "source_id": source_id,
        "source_type": source_type,
        "scan_mode": SOURCE_SCAN_MODE,
        "source_root_resolution": root_resolution,
        "source_map_path": source_map_path,
        "proposed_source_map_path": source_map_path,
        "proposed_receipt_path": proposed_receipt_path,
        "item_count": len(items),
        "items": items,
        "scope_gate": scope_gate,
        "trust_gate": trust_gate,
        "lineage": lineage,
        "receipt_preview": receipt_preview,
        "would_change": [source_map_path, proposed_receipt_path],
        "blockers": blockers,
        "warnings": warnings,
    }


def scan_source(
    archive_root: Path | str,
    *,
    source_id: str,
    reviewed_by: str,
    source_root: Path | str | None = None,
    limit: int = 2000,
) -> dict[str, Any]:
    reviewer = reviewed_by.strip()
    if not reviewer:
        raise ArchiveServiceError("Source scan requires --reviewed-by.")
    root = require_existing_archive_root(archive_root)
    dry_run = source_scan_dry_run(root, source_id=source_id, source_root=source_root, limit=limit)
    if dry_run["blockers"]:
        raise ArchiveServiceError("Source scan blocked by dry-run: " + "; ".join(dry_run["blockers"]))

    now = datetime.now().astimezone().replace(microsecond=0).isoformat()
    source_map_relative = dry_run["source_map_path"]
    source_map_path = archive_internal_path(root, source_map_relative)
    receipt_relative = dry_run["proposed_receipt_path"]
    receipt_path = archive_internal_path(root, receipt_relative)
    if receipt_path.exists():
        raise ArchiveServiceError(f"Proposed source scan receipt already exists: {receipt_relative}.")

    old_source_map_text = source_map_path.read_text(encoding="utf-8") if source_map_path.is_file() else None
    receipt = dict(dry_run["receipt_preview"])
    receipt["dry_run"] = False
    receipt["timestamp"] = now
    receipt["reviewed_by"] = reviewer
    receipt["reviewed_at"] = now
    receipt["result"] = {
        "changed_paths": [source_map_relative, receipt_relative],
        "source_map_written": True,
        "external_api_called": False,
    }
    try:
        source_map_path.parent.mkdir(parents=True, exist_ok=True)
        source_map_text = "".join(
            json.dumps(json_safe(item), ensure_ascii=False, sort_keys=True, default=str) + "\n"
            for item in dry_run["items"]
        )
        source_map_path.write_text(source_map_text, encoding="utf-8")
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        with receipt_path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(json_safe(receipt), indent=2, ensure_ascii=False, default=str) + "\n")
    except Exception:
        if old_source_map_text is None:
            try:
                if source_map_path.exists():
                    source_map_path.unlink()
            except OSError:
                pass
        else:
            try:
                source_map_path.write_text(old_source_map_text, encoding="utf-8")
            except OSError:
                pass
        try:
            if receipt_path.exists():
                receipt_path.unlink()
        except OSError:
            pass
        raise

    return {
        "ok": True,
        "dry_run": False,
        "action": "scan_archive_source",
        "source_archive": dry_run["source_archive"],
        "source_id": dry_run["source_id"],
        "source_type": dry_run["source_type"],
        "scan_mode": dry_run["scan_mode"],
        "item_count": dry_run["item_count"],
        "source_map_path": source_map_relative,
        "receipt_path": receipt_relative,
        "reviewed_by": reviewer,
        "changed_paths": [source_map_relative, receipt_relative],
        "receipt": json_safe(receipt),
    }


def resolve_source_scan_root(
    archive_root: Path,
    binding: dict[str, Any],
    source_root: Path | str | None,
    blockers: list[str],
    warnings: list[str],
) -> tuple[Path | None, dict[str, Any]]:
    source_type = str(binding.get("source_type") or "")
    source_id = str(binding.get("source_id") or "")
    root_ref = str(binding.get("root_ref") or "")
    resolution: dict[str, Any] = {
        "method": None,
        "root_ref": root_ref,
        "path_recorded": False,
        "exists": False,
    }
    if source_type == "object_manifest":
        manifest_path = archive_internal_path(archive_root, "objects/manifests/files.jsonl")
        resolution.update({"method": "archive_object_manifest", "exists": manifest_path.is_file()})
        if not manifest_path.is_file():
            blockers.append("Object manifest source requires objects/manifests/files.jsonl.")
        return manifest_path, resolution

    candidate: Path | None = None
    if source_root is not None:
        candidate = Path(source_root).expanduser().resolve()
        resolution["method"] = "cli_argument"
    elif root_ref.startswith("archive:"):
        try:
            candidate = archive_internal_path(archive_root, root_ref.removeprefix("archive:"))
            resolution["method"] = "archive_relative_root_ref"
        except ArchiveServiceError as exc:
            blockers.append(str(exc))
    elif root_ref and os.environ.get(root_ref):
        candidate = Path(os.environ[root_ref]).expanduser().resolve()
        resolution["method"] = f"env:{root_ref}"
    elif source_id and local_source_root_path(archive_root, source_id) is not None:
        candidate = local_source_root_path(archive_root, source_id)
        resolution["method"] = "ignored_local_profile"
    else:
        blockers.append(f"Source requires --source-root or an environment variable named by root_ref: {root_ref}.")
        resolution["method"] = "unresolved"

    if candidate is None:
        return None, resolution
    resolution["exists"] = candidate.exists()
    if not candidate.exists():
        blockers.append("Resolved source root does not exist.")
        return candidate, resolution
    if source_type in {"local_folder", "external_ssd", "notion_export"} and not candidate.is_dir():
        blockers.append(f"Source type {source_type} requires a directory root.")
    if source_type == "google_drive_export" and not (candidate.is_dir() or candidate.is_file()):
        blockers.append("Google Drive export source requires a directory or manifest file.")
    if candidate == archive_root:
        warnings.append("Source root is the archive root; this is allowed for examples but should be explicit for real archives.")
    return candidate, resolution


def discover_source_map_items(
    *,
    archive_root: Path,
    binding: dict[str, Any],
    resolved_root: Path | None,
    scanned_at: str,
    limit: int,
    warnings: list[str],
) -> list[dict[str, Any]]:
    source_type = str(binding.get("source_type") or "")
    if source_type == "object_manifest":
        return object_manifest_source_map_items(archive_root, binding, scanned_at, limit, warnings)
    if resolved_root is None:
        return []
    if source_type == "google_drive_export" and resolved_root.is_file():
        return google_drive_manifest_source_map_items(resolved_root, binding, scanned_at, limit, warnings)
    return filesystem_source_map_items(resolved_root, binding, scanned_at, limit, warnings)


def object_manifest_source_map_items(
    archive_root: Path,
    binding: dict[str, Any],
    scanned_at: str,
    limit: int,
    warnings: list[str],
) -> list[dict[str, Any]]:
    source_id = str(binding.get("source_id") or "")
    visibility = source_visibility(binding)
    entries: list[dict[str, Any]] = []
    for record in load_manifest_records(archive_root)[:limit]:
        object_id = str(record.get("object_id") or "")
        logical_key = record.get("logical_key") if isinstance(record.get("logical_key"), str) else None
        entries.append(
            {
                "source_id": source_id,
                "item_id": object_id or stable_source_item_id(source_id, logical_key or "object"),
                "item_kind": "object",
                "relative_path": logical_key,
                "object_id": object_id or None,
                "size_bytes": record.get("size_bytes") if isinstance(record.get("size_bytes"), int) else None,
                "mime": record.get("mime"),
                "visibility": visibility,
                "scan_status": "seen",
                "provenance": {
                    "source_type": "object_manifest",
                    "scan_mode": SOURCE_SCAN_MODE,
                    "scanned_at": scanned_at,
                    "content_read": False,
                    "full_hash_calculated": False,
                    "external_api_called": False,
                },
            }
        )
    if len(load_manifest_records(archive_root)) > limit:
        warnings.append(f"Object manifest source scan was limited to {limit} item(s).")
    return entries


def google_drive_manifest_source_map_items(
    manifest_path: Path,
    binding: dict[str, Any],
    scanned_at: str,
    limit: int,
    warnings: list[str],
) -> list[dict[str, Any]]:
    data = load_external_import_manifest_data(manifest_path)
    raw_items = data.get("items") if isinstance(data, dict) else []
    if not isinstance(raw_items, list):
        warnings.append("Google Drive source manifest has no items list.")
        return []
    source_id = str(binding.get("source_id") or "")
    visibility = source_visibility(binding)
    entries: list[dict[str, Any]] = []
    for raw_item in raw_items[:limit]:
        if not isinstance(raw_item, dict):
            continue
        external_id = str(raw_item.get("external_id") or raw_item.get("id") or raw_item.get("url") or raw_item.get("path") or "")
        relative_path = str(raw_item.get("path") or "") or None
        entries.append(
            {
                "source_id": source_id,
                "item_id": stable_source_item_id(source_id, external_id or relative_path or str(len(entries))),
                "item_kind": str(raw_item.get("kind") or "file"),
                "relative_path": relative_path,
                "external_url": raw_item.get("url") or raw_item.get("source_url"),
                "provider_id": external_id or None,
                "size_bytes": raw_item.get("size_bytes") if isinstance(raw_item.get("size_bytes"), int) else None,
                "modified_at": raw_item.get("modified_at") or raw_item.get("updated_at"),
                "mime": raw_item.get("mime"),
                "title": raw_item.get("title") or raw_item.get("name"),
                "visibility": visibility,
                "scan_status": "seen",
                "provenance": {
                    "source_type": "google_drive_export",
                    "scan_mode": SOURCE_SCAN_MODE,
                    "scanned_at": scanned_at,
                    "content_read": False,
                    "full_hash_calculated": False,
                    "external_api_called": False,
                },
            }
        )
    if len(raw_items) > limit:
        warnings.append(f"Google Drive source scan was limited to {limit} item(s).")
    return entries


def filesystem_source_map_items(
    root: Path,
    binding: dict[str, Any],
    scanned_at: str,
    limit: int,
    warnings: list[str],
) -> list[dict[str, Any]]:
    source_id = str(binding.get("source_id") or "")
    source_type = str(binding.get("source_type") or "")
    visibility = source_visibility(binding)
    scope_policy = binding.get("scope_policy") if isinstance(binding.get("scope_policy"), dict) else {}
    include_patterns = scope_patterns(scope_policy.get("include"), ["**/*"])
    exclude_patterns = scope_patterns(scope_policy.get("exclude"), [".git/**", "__pycache__/**"])
    entries: list[dict[str, Any]] = []
    skipped = 0
    for path in sorted(root.rglob("*")):
        if len(entries) >= limit:
            skipped += 1
            continue
        if not path.is_file():
            continue
        if not is_path_within_root(path, root):
            skipped += 1
            continue
        relative = path.relative_to(root).as_posix()
        if not matches_any_pattern(relative, include_patterns):
            skipped += 1
            continue
        if matches_any_pattern(relative, exclude_patterns):
            skipped += 1
            continue
        try:
            stat = path.stat()
        except OSError:
            skipped += 1
            continue
        entries.append(
            {
                "source_id": source_id,
                "item_id": stable_source_item_id(source_id, relative),
                "item_kind": "file",
                "relative_path": relative,
                "size_bytes": int(stat.st_size),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).astimezone().replace(microsecond=0).isoformat(),
                "mime": mimetypes.guess_type(path.name)[0],
                "title": path.stem,
                "visibility": visibility,
                "scan_status": "seen",
                "provenance": {
                    "source_type": source_type,
                    "scan_mode": SOURCE_SCAN_MODE,
                    "scanned_at": scanned_at,
                    "content_read": False,
                    "full_hash_calculated": False,
                    "external_api_called": False,
                },
            }
        )
    if skipped:
        warnings.append(f"Source scan skipped or deferred {skipped} item(s) because of limits, filters, or path safety.")
    return entries


def source_visibility(binding: dict[str, Any]) -> dict[str, Any]:
    visibility = binding.get("visibility")
    if isinstance(visibility, dict):
        return json_safe(visibility)
    return default_private_visibility()


def scope_patterns(value: Any, default: list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str) and item]
    if isinstance(value, str) and value:
        return [value]
    return default


def matches_any_pattern(relative_path: str, patterns: list[str]) -> bool:
    normalized = relative_path.replace("\\", "/")
    for pattern in patterns:
        normalized_pattern = pattern.replace("\\", "/")
        if normalized_pattern in {"*", "**", "**/*"}:
            return True
        if fnmatch.fnmatch(normalized, normalized_pattern):
            return True
        if normalized_pattern.endswith("/**") and normalized.startswith(normalized_pattern[:-3]):
            return True
    return False


def stable_source_item_id(source_id: str, key: str) -> str:
    digest = hashlib.sha256(f"{source_id}\n{key}".encode("utf-8")).hexdigest()[:16]
    return f"sourceitem:{safe_slug(source_id)}:{digest}"


def source_scan_fingerprint(source_id: str, source_type: str, items: list[dict[str, Any]]) -> str:
    payload = {
        "source_id": source_id,
        "source_type": source_type,
        "items": [
            {
                "item_id": item.get("item_id"),
                "relative_path": item.get("relative_path"),
                "external_url": item.get("external_url"),
                "object_id": item.get("object_id"),
                "size_bytes": item.get("size_bytes"),
                "modified_at": item.get("modified_at"),
            }
            for item in items
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def unique_workpack_id(archive_root: Path, view_id: str, iso_now: str) -> str:
    base = f"workpack_{iso_now[:10].replace('-', '')}_{safe_slug(view_id)}"
    candidate = base
    suffix = 2
    while (archive_root / "workpacks" / candidate).exists():
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def safe_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:64] or "item"


def resolve_workpack_package_path(workpack_path: Path | str) -> tuple[Path, Path]:
    candidate = Path(workpack_path).resolve()
    package_file = candidate / "package.yml" if candidate.is_dir() else candidate
    if package_file.name != "package.yml":
        raise ArchiveServiceError("Workpack path must be a workpack directory or package.yml file.")
    if not package_file.is_file():
        raise ArchiveServiceError(f"Workpack package.yml not found: {package_file}")
    return package_file.parent, package_file


def inspect_workpack_zettels(
    target_root: Path,
    package_root: Path,
    package: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
) -> list[dict[str, Any]]:
    entries = extract_workpack_zettel_entries(package, package_root, blockers)
    target_ids = collect_target_zettel_ids(target_root)
    previews: list[dict[str, Any]] = []
    for entry in entries:
        package_path = entry["package_path"]
        try:
            zettel_path = resolve_archive_relative_path(package_root, package_path)
        except ArchivePathError as exc:
            blockers.append(f"Workpack zettel path is unsafe: {package_path} ({exc}).")
            continue
        if not zettel_path.is_file():
            blockers.append(f"Workpack zettel file is missing: {package_path}.")
            continue
        frontmatter, _body = split_zettel_text(zettel_path.read_text(encoding="utf-8"))
        frontmatter = json_safe(frontmatter)
        zettel_id = frontmatter.get("id")
        filename = zettel_path.name
        target_path = f"inbox/{filename}"
        preview = {
            "id": zettel_id,
            "title": frontmatter.get("title"),
            "package_path": archive_relative_path(zettel_path, package_root),
            "target_path": target_path,
            "action": "create_inbox_draft",
            "conflicts": [],
        }
        if zettel_id in target_ids:
            preview["conflicts"].append("zettel_id_exists")
            blockers.append(f"Target archive already has zettel id: {zettel_id}.")
        if (target_root / target_path).exists():
            preview["conflicts"].append("target_path_exists")
            blockers.append(f"Target inbox path already exists: {target_path}.")
        if contains_forbidden_location_reference(zettel_path.read_text(encoding="utf-8")):
            warnings.append(f"Workpack zettel may contain a provider URL or local absolute path: {package_path}.")
        previews.append(preview)
    return previews


def extract_workpack_zettel_entries(
    package: dict[str, Any],
    package_root: Path,
    blockers: list[str],
) -> list[dict[str, str]]:
    contents = package.get("contents") if isinstance(package.get("contents"), dict) else {}
    raw_entries = contents.get("zettels") if isinstance(contents, dict) else None
    entries: list[dict[str, str]] = []
    if isinstance(raw_entries, list):
        for item in raw_entries:
            if isinstance(item, dict) and isinstance(item.get("package_path"), str):
                entries.append({"package_path": item["package_path"]})
            elif isinstance(item, str):
                entries.append({"package_path": item})
            else:
                blockers.append("Workpack contents.zettels contains an unsupported entry.")
    if entries:
        return entries

    zettels_root = package_root / "zettels"
    if zettels_root.is_dir():
        for path in safe_archive_glob(zettels_root, "*.md", package_root):
            entries.append({"package_path": archive_relative_path(path, package_root)})
    return entries


def collect_target_zettel_ids(target_root: Path) -> set[Any]:
    zettel_ids: set[Any] = set()
    for path in iter_zettel_paths(target_root):
        frontmatter, _body = split_zettel_text(path.read_text(encoding="utf-8"))
        if frontmatter.get("id"):
            zettel_ids.add(frontmatter.get("id"))
    return zettel_ids


def inspect_workpack_manifest(
    target_root: Path,
    package_root: Path,
    package: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
) -> list[dict[str, Any]]:
    contents = package.get("contents") if isinstance(package.get("contents"), dict) else {}
    objects = contents.get("objects") if isinstance(contents.get("objects"), dict) else {}
    manifest_relative = objects.get("manifest_path") if isinstance(objects.get("manifest_path"), str) else "manifests/files.jsonl"
    try:
        manifest_path = resolve_archive_relative_path(package_root, manifest_relative)
    except ArchivePathError as exc:
        blockers.append(f"Workpack manifest path is unsafe: {manifest_relative} ({exc}).")
        return []
    if not manifest_path.is_file():
        if objects.get("object_ids"):
            blockers.append(f"Workpack object manifest is missing: {manifest_relative}.")
        return []

    target_objects = {record.get("object_id"): record for record in load_manifest_records(target_root)}
    previews: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            blockers.append(f"Workpack manifest invalid JSON on line {line_number}: {exc}.")
            continue
        object_id = record.get("object_id") if isinstance(record, dict) else None
        if not object_id:
            blockers.append(f"Workpack manifest entry missing object_id on line {line_number}.")
            continue
        action = "already_present" if object_id in target_objects else "append_manifest_record"
        preview = {
            "object_id": object_id,
            "logical_key": record.get("logical_key") if isinstance(record, dict) else None,
            "action": action,
            "include_original": False,
        }
        if action == "already_present":
            warnings.append(f"Target manifest already has object_id: {object_id}.")
        previews.append(preview)
    return previews


def build_import_scope_gate(
    package: dict[str, Any],
    zettel_previews: list[dict[str, Any]],
    object_previews: list[dict[str, Any]],
) -> dict[str, Any]:
    package_scope = package.get("scope_gate") if isinstance(package.get("scope_gate"), dict) else {}
    included_paths = [item["package_path"] for item in zettel_previews if item.get("action") == "create_inbox_draft"]
    return {
        "unit": package_scope.get("unit") or "workpack",
        "view_id": package_scope.get("view_id") or nested_value(package, ["contents", "view_id"]),
        "included_zettels": included_paths,
        "included_objects": [item["object_id"] for item in object_previews if item.get("action") == "append_manifest_record"],
        "excluded": package_scope.get("excluded") or [],
        "sensitive_categories_blocked_by_default": package_scope.get("sensitive_categories_blocked_by_default")
        or sorted(SENSITIVE_SHARE_CATEGORIES),
    }


def build_import_trust_gate(
    target_root: Path,
    package: dict[str, Any],
    *,
    counterparty_id: str | None,
    counterparty_fingerprint: str | None,
    blockers: list[str],
) -> dict[str, Any]:
    trust_policy = package.get("trust_gate") if isinstance(package.get("trust_gate"), dict) else {}
    if not trust_policy.get("counterparty_identity_required"):
        return {"required": False, "ok": True, "status": "not_required"}
    return validate_counterparty_trust(
        target_root,
        counterparty_id=counterparty_id or str(package.get("source_archive") or ""),
        counterparty_fingerprint=counterparty_fingerprint,
        blockers=blockers,
    )


def load_archive_identity(archive_root: Path) -> dict[str, Any]:
    data = load_yaml(read_archive_text(archive_root, "archive-identity.yml"))
    if not isinstance(data, dict):
        raise ArchiveServiceError("archive-identity.yml must be a YAML object.")
    return json_safe(data)


def load_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArchiveServiceError(f"JSON file is invalid: {path}") from exc
    if not isinstance(data, dict):
        raise ArchiveServiceError(f"JSON file must contain an object: {path}")
    return json_safe(data)


def resolve_receipt_input_path(archive_root: Path, raw_path: str) -> Path:
    value = (raw_path or "").strip()
    if not value:
        raise ArchiveServiceError("Receipt path is required.")
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        path = candidate.resolve()
    else:
        path = archive_internal_path(archive_root, value)
    if not path.is_file():
        raise ArchiveServiceError(f"Receipt file is missing: {value}")
    return path


def display_receipt_input_path(archive_root: Path, path: Path) -> str:
    if is_path_within_root(path, archive_root):
        return archive_relative_path(path, archive_root)
    return str(path)


def string_or_empty(value: Any) -> str:
    return value if isinstance(value, str) else ""


def normalized_delegated_zets(raw_items: Any, blockers: list[str]) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        blockers.append("Delegated zets must be a list.")
        return []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            blockers.append(f"Delegated zets entry must be an object: index {index}.")
            continue
        path = item.get("path")
        zettel_id = item.get("zettel_id")
        sha256 = item.get("sha256")
        if not isinstance(path, str) or not path:
            blockers.append(f"Delegated zets entry missing path: index {index}.")
        if not isinstance(zettel_id, str) or not zettel_id:
            blockers.append(f"Delegated zets entry missing zettel_id: index {index}.")
        if not isinstance(sha256, str) or not SHA256_RE.match(sha256):
            blockers.append(f"Delegated zets entry has invalid sha256: index {index}.")
        normalized.append(
            {
                "path": path,
                "zettel_id": zettel_id,
                "title": item.get("title"),
                "sha256": sha256,
                "sensitive_categories": item.get("sensitive_categories") if isinstance(item.get("sensitive_categories"), list) else [],
            }
        )
    if not normalized:
        blockers.append("Delegated zets list is empty.")
    return normalized


def validate_counterparty_trust(
    archive_root: Path,
    *,
    counterparty_id: str | None,
    counterparty_fingerprint: str | None,
    blockers: list[str],
) -> dict[str, Any]:
    identity_doc = load_archive_identity(archive_root)
    counterparty = (counterparty_id or "").strip()
    fingerprint = (counterparty_fingerprint or "").strip()
    result = {
        "required": True,
        "ok": False,
        "counterparty_id": counterparty or None,
        "provided_fingerprint": fingerprint or None,
        "matched": None,
        "status": "blocked",
    }
    if not counterparty:
        blockers.append("Counterparty identity is required for archive sharing.")
        return result
    if not fingerprint:
        blockers.append("Counterparty fingerprint is required for trust gate verification.")
        return result

    trusted = identity_doc.get("trusted_counterparties") or []
    if not isinstance(trusted, list):
        blockers.append("archive-identity.yml trusted_counterparties must be a list.")
        return result
    for item in trusted:
        if not isinstance(item, dict):
            continue
        identifiers = {
            str(value)
            for value in [item.get("identity_id"), item.get("archive_id"), item.get("principal_id")]
            if value
        }
        if counterparty not in identifiers:
            continue
        expected = str(item.get("expected_fingerprint") or "")
        result["matched"] = {
            "identity_id": item.get("identity_id"),
            "archive_id": item.get("archive_id"),
            "principal_id": item.get("principal_id"),
            "trust_level": item.get("trust_level"),
            "expected_fingerprint": expected or None,
        }
        if expected != fingerprint:
            blockers.append("Counterparty fingerprint does not match trusted identity.")
            return result
        result["ok"] = True
        result["status"] = "verified"
        return result

    blockers.append(f"Counterparty identity is not trusted by this archive: {counterparty}.")
    return result


def sensitive_categories_for_frontmatter(frontmatter: dict[str, Any]) -> list[str]:
    raw_values: list[Any] = [frontmatter.get("kind")]
    facets = frontmatter.get("facets")
    if isinstance(facets, dict):
        for key in ["domain", "record_type", "category", "sensitivity", "privacy", "tags"]:
            raw_values.append(facets.get(key))
    visibility = frontmatter.get("visibility")
    if isinstance(visibility, dict):
        raw_values.append(visibility.get("scope"))

    found: set[str] = set()
    for value in raw_values:
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, str):
                continue
            normalized = re.sub(r"[^a-z0-9]+", "-", item.lower()).strip("-")
            normalized = SENSITIVE_CATEGORY_ALIASES.get(normalized, normalized)
            if normalized in SENSITIVE_SHARE_CATEGORIES:
                found.add(normalized)
    return sorted(found)


def index_archive(archive_root: Path | str) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    db_path = archive_internal_path(root, INDEX_RELATIVE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    zettel_count = 0
    object_count = 0
    view_count = 0
    source_map_count = 0
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS zettels (
              path TEXT PRIMARY KEY,
              zettel_id TEXT,
              title TEXT,
              status TEXT,
              kind TEXT,
              body TEXT,
              frontmatter_json TEXT
            );
            CREATE TABLE IF NOT EXISTS objects (
              object_id TEXT PRIMARY KEY,
              logical_key TEXT,
              mime TEXT,
              manifest_json TEXT
            );
            CREATE TABLE IF NOT EXISTS views (
              path TEXT PRIMARY KEY,
              view_id TEXT,
              name TEXT,
              view_for TEXT,
              view_json TEXT
            );
            CREATE TABLE IF NOT EXISTS source_map_entries (
              item_id TEXT PRIMARY KEY,
              source_id TEXT,
              item_kind TEXT,
              relative_path TEXT,
              external_url TEXT,
              scan_status TEXT,
              source_json TEXT
            );
            DELETE FROM zettels;
            DELETE FROM objects;
            DELETE FROM views;
            DELETE FROM source_map_entries;
            """
        )

        for path in iter_zettel_paths(root):
            frontmatter, body = split_zettel_text(path.read_text(encoding="utf-8"))
            frontmatter = json_safe(frontmatter)
            conn.execute(
                """
                INSERT OR REPLACE INTO zettels(path, zettel_id, title, status, kind, body, frontmatter_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    archive_relative_path(path, root),
                    frontmatter.get("id"),
                    frontmatter.get("title"),
                    frontmatter.get("status"),
                    frontmatter.get("kind"),
                    body,
                    json.dumps(frontmatter, ensure_ascii=False, default=str),
                ),
            )
            zettel_count += 1

        manifest_path = root / "objects" / "manifests" / "files.jsonl"
        if manifest_path.is_file():
            for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO objects(object_id, logical_key, mime, manifest_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        record.get("object_id"),
                        record.get("logical_key"),
                        record.get("mime"),
                        json.dumps(record, ensure_ascii=False, default=str),
                    ),
                )
                object_count += 1

        views_root = root / "views"
        if views_root.is_dir():
            for path in safe_archive_glob(views_root, "*.yml", root):
                data = load_yaml(path.read_text(encoding="utf-8"))
                safe_data = json_safe(data)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO views(path, view_id, name, view_for, view_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        archive_relative_path(path, root),
                        safe_data.get("id") if isinstance(safe_data, dict) else None,
                        safe_data.get("name") if isinstance(safe_data, dict) else None,
                        safe_data.get("for") if isinstance(safe_data, dict) else None,
                        json.dumps(safe_data, ensure_ascii=False, default=str),
                    ),
                )
                view_count += 1

        source_maps_root = root / SOURCE_MAPS_DIR
        if source_maps_root.is_dir():
            for path in safe_archive_glob(source_maps_root, "*.jsonl", root):
                for raw_line in path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(record, dict):
                        continue
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO source_map_entries(
                          item_id, source_id, item_kind, relative_path, external_url, scan_status, source_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.get("item_id"),
                            record.get("source_id"),
                            record.get("item_kind"),
                            record.get("relative_path"),
                            record.get("external_url"),
                            record.get("scan_status"),
                            json.dumps(record, ensure_ascii=False, default=str),
                        ),
                    )
                    source_map_count += 1

        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "index_path": archive_relative_path(db_path, root),
        "zettels": zettel_count,
        "objects": object_count,
        "views": view_count,
        "source_map_entries": source_map_count,
    }


def search_archive(archive_root: Path | str, query: str, limit: int = 20) -> dict[str, Any]:
    root = require_existing_archive_root(archive_root)
    if not query.strip():
        raise ArchiveServiceError("query is required.")
    db_path = root / INDEX_RELATIVE_PATH
    if not db_path.is_file():
        raise ArchiveServiceError("Archive index is missing. Run archive index first.")

    like = f"%{query.lower()}%"
    limit = max(1, min(int(limit), 100))
    results: list[dict[str, Any]] = []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        for row in conn.execute(
            """
            SELECT path, zettel_id, title, status, kind, body, frontmatter_json
            FROM zettels
            WHERE lower(coalesce(zettel_id, '') || ' ' || coalesce(title, '') || ' ' || coalesce(status, '') || ' ' ||
                        coalesce(kind, '') || ' ' || coalesce(body, '') || ' ' || coalesce(frontmatter_json, '')) LIKE ?
            ORDER BY path
            LIMIT ?
            """,
            (like, limit),
        ):
            results.append(
                {
                    "type": "zettel",
                    "path": row["path"],
                    "id": row["zettel_id"],
                    "title": row["title"],
                    "status": row["status"],
                    "kind": row["kind"],
                    "snippet": make_snippet(row["body"] or row["frontmatter_json"] or "", query),
                }
            )

        remaining = limit - len(results)
        if remaining > 0:
            for row in conn.execute(
                """
                SELECT object_id, logical_key, mime, manifest_json
                FROM objects
                WHERE lower(coalesce(object_id, '') || ' ' || coalesce(logical_key, '') || ' ' ||
                            coalesce(mime, '') || ' ' || coalesce(manifest_json, '')) LIKE ?
                ORDER BY logical_key
                LIMIT ?
                """,
                (like, remaining),
            ):
                results.append(
                    {
                        "type": "object",
                        "path": row["logical_key"],
                        "id": row["object_id"],
                        "title": row["logical_key"],
                        "mime": row["mime"],
                        "snippet": make_snippet(row["manifest_json"] or "", query),
                    }
                )

        remaining = limit - len(results)
        if remaining > 0:
            for row in conn.execute(
                """
                SELECT path, view_id, name, view_for, view_json
                FROM views
                WHERE lower(coalesce(view_id, '') || ' ' || coalesce(name, '') || ' ' ||
                            coalesce(view_for, '') || ' ' || coalesce(view_json, '')) LIKE ?
                ORDER BY path
                LIMIT ?
                """,
                (like, remaining),
            ):
                results.append(
                    {
                        "type": "view",
                        "path": row["path"],
                        "id": row["view_id"],
                        "title": row["name"],
                        "for": row["view_for"],
                        "snippet": make_snippet(row["view_json"] or "", query),
                    }
                )

        remaining = limit - len(results)
        if remaining > 0:
            for row in conn.execute(
                """
                SELECT item_id, source_id, item_kind, relative_path, external_url, scan_status, source_json
                FROM source_map_entries
                WHERE lower(coalesce(item_id, '') || ' ' || coalesce(source_id, '') || ' ' ||
                            coalesce(item_kind, '') || ' ' || coalesce(relative_path, '') || ' ' ||
                            coalesce(external_url, '') || ' ' || coalesce(scan_status, '') || ' ' ||
                            coalesce(source_json, '')) LIKE ?
                ORDER BY source_id, relative_path, external_url
                LIMIT ?
                """,
                (like, remaining),
            ):
                title = row["relative_path"] or row["external_url"] or row["item_id"]
                results.append(
                    {
                        "type": "source_map",
                        "path": row["relative_path"] or row["external_url"],
                        "id": row["item_id"],
                        "title": title,
                        "source_id": row["source_id"],
                        "item_kind": row["item_kind"],
                        "scan_status": row["scan_status"],
                        "snippet": make_snippet(row["source_json"] or "", query),
                    }
                )
    finally:
        conn.close()

    return {"query": query, "count": len(results), "results": results}


def iter_zettel_paths(archive_root: Path) -> list[Path]:
    archive_root = archive_root.resolve()
    paths: list[Path] = []
    for folder in ["zettels", "inbox"]:
        root = archive_root / folder
        if root.is_dir():
            paths.extend(safe_archive_glob(root, "*.md", archive_root, recursive=True))
    return paths


def safe_archive_glob(root: Path, pattern: str, archive_root: Path, *, recursive: bool = False) -> list[Path]:
    """Return matching files whose resolved target stays inside the archive root."""

    iterator = root.rglob(pattern) if recursive else root.glob(pattern)
    return sorted(path for path in iterator if path.is_file() and is_path_within_root(path, archive_root))


def make_snippet(text: str, query: str, size: int = 160) -> str:
    compact = " ".join(text.split())
    index = compact.lower().find(query.lower())
    if index < 0:
        return compact[:size]
    start = max(0, index - size // 3)
    end = min(len(compact), start + size)
    return compact[start:end]


def read_archive_id(archive_root: Path) -> str:
    data = read_archive_config(archive_root)
    if not isinstance(data.get("archive_id"), str):
        raise ArchiveServiceError("archive.yml does not contain archive_id and archive_id was not provided.")
    return data["archive_id"]


def read_archive_config(archive_root: Path) -> dict[str, Any]:
    data = load_yaml(read_archive_text(archive_root, "archive.yml"))
    if not isinstance(data, dict):
        raise ArchiveServiceError("archive.yml is not a readable object.")
    return data


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_private_visibility() -> dict[str, Any]:
    return {"scope": "private", "allowed_archives": [], "source_visibility": "private"}


def make_zettel_id(title: str, iso_now: str) -> str:
    day = iso_now[:10].replace("-", "")
    time_part = iso_now[11:19].replace(":", "")
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:32] or "draft"
    return f"zet_{day}_{time_part}_{slug}"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def drop_none_values(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}
