#!/usr/bin/env python3
"""Minimal AI Archive Kit CLI.

Commands:
  doctor  Inspect an archive for structural and policy issues.
  init    Create a new archive from a built-in template.
  index   Build a generated local SQLite search index.
  pack    Create a portable workpack from a view.
  import  Preview a workpack import without mutating the target archive.
  import-external
          Import Notion or Google Drive exports as governed inbox drafts.
  providers
          Inspect provider bindings and external account change plans.
  sources
          Inspect source bindings and mapped source items.
  scan-source
          Metadata-only scan of a registered source into source-maps/.
  add-source
          Register a source without hand-editing source-bindings.yml.
  mint-zettel
          Mint an inbox draft zet into canonical private archive memory.
  source-mounts
          Show host-native and Docker mount guidance for registered sources.
  recovery-plan
          Show backup/restore readiness without writing files.
  restore-drill
          Plan or run a local restore drill before real data pilot.
  pilot-plan
          Plan a first real personal/team pilot without writing files.
  preflight
          Check an archive before connecting real personal or team data.
  transfer-ownership
          Preview or apply an archive ownership transfer.
  search  Search the generated local SQLite index.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import archive_services
from .paths import (
    ArchivePathError,
    archive_relative_path,
    contains_forbidden_location_reference,
    is_path_within_root,
    resolve_archive_relative_path,
)
from .schema_validator import validate_schema

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only when dependency is absent.
    yaml = None


KIT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_ROOT = KIT_ROOT / "templates"
KIT_ZETTEL_KASTEN_ROOT = KIT_ROOT / "zettel-kasten"

REQUIRED_ARCHIVE_FILES = [
    "AGENTS.md",
    "archive.yml",
    "archive-identity.yml",
    "provider-bindings.yml",
    "source-bindings.yml",
    "views/homebase.yml",
    "objects/manifests/files.jsonl",
    "db/schema.sql",
]

REQUIRED_ARCHIVE_DIRS = [
    "inbox",
    "zettels",
    "views",
    "source-maps",
    "objects",
    "objects/manifests",
    "db",
]

RECOMMENDED_V02_FILES = [
    "zettel-kasten/types.yml",
    "zettel-kasten/actions.yml",
    "zettel-kasten/policies.yml",
    "zettel-kasten/zettel-rules.yml",
]

ZETTEL_KASTEN_SCHEMA_FILES = {
    "types.yml": "zettel-kasten-types.schema.json",
    "actions.yml": "zettel-kasten-actions.schema.json",
    "policies.yml": "zettel-kasten-policies.schema.json",
    "zettel-rules.yml": "zettel-rules.schema.json",
}

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

ALLOWED_ZETTEL_STATUS = {"draft", "canonical", "archived", "redacted"}
CANONICAL_REQUIRES_VALUES = {"human_minting", "human_promotion"}
OBJECT_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.DOTALL)
SECRET_VALUE_RE = re.compile(
    r"(?i)(?:api[_-]?key|secret|token|password|credential|aws_secret_access_key)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=:-]{12,}"
    r"|-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|\bAKIA[0-9A-Z]{16}\b"
)
SECRET_SCAN_EXTENSIONS = {
    ".conf",
    ".env",
    ".ini",
    ".json",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
RECOMMENDED_GITIGNORE_PATTERNS = [
    ".env",
    ".env.*",
    "!.env.example",
    "secrets/",
    "profiles/local/",
    "profiles/*.local.yml",
    "keyrings/local/",
    "keyrings/*.local.yml",
    ".archive-local/",
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.kdbx",
    "rclone.conf",
    "credentials.json",
    "token.json",
]
SECRET_FILENAME_EXACT = {
    ".env",
    "credentials.json",
    "token.json",
    "rclone.conf",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}
SECRET_FILENAME_SUFFIXES = (
    ".key",
    ".pem",
    ".p12",
    ".pfx",
    ".kdbx",
    ".secret.yml",
    ".secrets.yml",
    ".secret.yaml",
    ".secrets.yaml",
)
LOCAL_PROFILE_ROOTS = (
    "profiles/local/",
    "keyrings/local/",
    ".archive-local/",
)


@dataclass
class Diagnostic:
    severity: str
    code: str
    message: str
    path: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
        }


class Doctor:
    def __init__(self, archive_root: Path) -> None:
        self.archive_root = archive_root.resolve()
        self.diagnostics: list[Diagnostic] = []
        self.archive_config: dict[str, Any] = {}
        self.manifest_objects: dict[str, dict[str, Any]] = {}
        self.allowed_link_types = self._load_allowed_link_types()

    def run(self) -> list[Diagnostic]:
        if not self.archive_root.exists():
            self.error("archive_root_missing", "Archive root does not exist.", self.archive_root)
            return self.diagnostics
        if not self.archive_root.is_dir():
            self.error("archive_root_not_directory", "Archive root is not a directory.", self.archive_root)
            return self.diagnostics

        self.info("archive_root", f"Inspecting archive root: {self.archive_root}", self.archive_root)
        self._check_symlink_boundaries()
        self._check_required_structure()
        self._check_v02_recommendations()
        self._check_archive_yml()
        self._check_archive_identity_yml()
        self._check_provider_bindings_yml()
        self._check_source_bindings_yml()
        self._check_sqlite_schema()
        self._check_object_manifest()
        self._check_source_maps()
        self._check_zettels()
        self._check_views()
        self._check_workpacks()
        self._check_external_import_receipts()
        self._check_source_scan_receipts()
        self._check_recovery_receipts()
        self._check_lineage_receipts()
        self._check_mint_receipts()
        self._check_zettel_kasten_layer()
        self._check_local_profile_and_secret_safety()
        return self.diagnostics

    def error(self, code: str, message: str, path: Path | str | None = None) -> None:
        self.diagnostics.append(Diagnostic("ERROR", code, message, self._display_path(path)))

    def warn(self, code: str, message: str, path: Path | str | None = None) -> None:
        self.diagnostics.append(Diagnostic("WARN", code, message, self._display_path(path)))

    def info(self, code: str, message: str, path: Path | str | None = None) -> None:
        self.diagnostics.append(Diagnostic("INFO", code, message, self._display_path(path)))

    def _display_path(self, path: Path | str | None) -> str | None:
        if path is None:
            return None
        path_obj = Path(path)
        try:
            return archive_relative_path(path_obj, self.archive_root)
        except (ArchivePathError, OSError, ValueError):
            return str(path)

    def _check_required_structure(self) -> None:
        for relative in REQUIRED_ARCHIVE_DIRS:
            path = self.archive_root / relative
            if not path.is_dir():
                self.error("required_directory_missing", f"Required directory is missing: {relative}", path)

        for relative in REQUIRED_ARCHIVE_FILES:
            path = self.archive_root / relative
            if not path.is_file():
                self.error("required_file_missing", f"Required file is missing: {relative}", path)

    def _check_v02_recommendations(self) -> None:
        for relative in RECOMMENDED_V02_FILES:
            path = self.archive_root / relative
            if not path.is_file():
                self.warn("v02_file_missing", f"Recommended v0.2 file is missing: {relative}", path)

    def _check_archive_yml(self) -> None:
        path = self.archive_root / "archive.yml"
        data = self._load_yaml_file(path)
        if not isinstance(data, dict):
            return
        self.archive_config = data
        self._check_schema(data, "archive.schema.json", path)

        for field in [
            "archive_id",
            "name",
            "type",
            "principal",
            "root_policy",
            "ai_write_policy",
            "storage_policy",
        ]:
            if field not in data:
                self.error("archive_field_missing", f"archive.yml missing required field: {field}", path)

        root_policy = data.get("root_policy") or {}
        if isinstance(root_policy, dict):
            for key, default_relative in [
                ("canonical_zettels", "zettels/"),
                ("ai_inbox", "inbox/"),
                ("views", "views/"),
                ("object_manifest", "objects/manifests/files.jsonl"),
                ("sqlite_schema", "db/schema.sql"),
            ]:
                relative = root_policy.get(key, default_relative)
                try:
                    policy_path = resolve_archive_relative_path(self.archive_root, str(relative))
                except ArchivePathError as exc:
                    self.error("root_policy_path_unsafe", f"root_policy.{key} has an unsafe path: {relative} ({exc})", path)
                    continue
                if not policy_path.exists():
                    self.error("root_policy_path_missing", f"root_policy.{key} points to a missing path: {relative}", path)

        ai_policy = data.get("ai_write_policy") or {}
        if isinstance(ai_policy, dict):
            if ai_policy.get("default") != "inbox_only":
                self.warn("unsafe_ai_write_default", "ai_write_policy.default should be inbox_only.", path)
            if ai_policy.get("canonical_requires") not in CANONICAL_REQUIRES_VALUES:
                self.warn(
                    "unsafe_minting_policy",
                    "ai_write_policy.canonical_requires should be human_minting. Legacy human_promotion is also accepted.",
                    path,
                )

        storage_policy = data.get("storage_policy") or {}
        if isinstance(storage_policy, dict):
            if storage_policy.get("object_identity") != "sha256":
                self.error("object_identity_policy", "storage_policy.object_identity must be sha256.", path)
            if storage_policy.get("provider_urls_in_zettels") != "forbidden":
                self.error("provider_url_policy", "storage_policy.provider_urls_in_zettels must be forbidden.", path)

    def _check_archive_identity_yml(self) -> None:
        path = self.archive_root / "archive-identity.yml"
        data = self._load_yaml_file(path)
        if not isinstance(data, dict):
            return
        self._check_schema(data, "archive-identity.schema.json", path)
        identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
        archive_id = identity.get("archive_id")
        if self.archive_config and archive_id != self.archive_config.get("archive_id"):
            self.error("archive_identity_mismatch", "archive-identity.yml identity.archive_id must match archive.yml archive_id.", path)
        scope = identity.get("scope")
        if scope and scope != self.archive_config.get("type"):
            self.warn("archive_identity_scope_mismatch", "archive-identity.yml identity.scope should match archive.yml type.", path)

    def _check_provider_bindings_yml(self) -> None:
        path = self.archive_root / "provider-bindings.yml"
        data = self._load_yaml_file(path)
        if not isinstance(data, dict):
            return
        self._check_schema(data, "provider-bindings.schema.json", path)
        archive_id = data.get("archive_id")
        if self.archive_config and archive_id != self.archive_config.get("archive_id"):
            self.error("provider_bindings_archive_mismatch", "provider-bindings.yml archive_id must match archive.yml archive_id.", path)
        self._check_provider_binding_secret_refs(data, path)

    def _check_provider_binding_secret_refs(self, value: Any, path: Path, field_path: str = "$") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{field_path}.{key}"
                if self._is_provider_secret_field(str(key)) and not str(key).endswith("_env"):
                    if isinstance(child, str) and child.strip():
                        self.error(
                            "provider_bindings_secret_field",
                            f"Provider binding field should reference an env var or keyring entry, not store a secret-like value: {child_path}",
                            path,
                        )
                self._check_provider_binding_secret_refs(child, path, child_path)
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                self._check_provider_binding_secret_refs(child, path, f"{field_path}[{index}]")
            return
        if isinstance(value, str) and SECRET_VALUE_RE.search(f"value: {value}"):
            self.error(
                "provider_bindings_secret_value",
                f"Provider binding appears to contain a secret-like value at {field_path}. Use an *_env or keyring reference instead.",
                path,
            )

    def _check_source_bindings_yml(self) -> None:
        path = self.archive_root / "source-bindings.yml"
        data = self._load_yaml_file(path)
        if not isinstance(data, dict):
            return
        self._check_schema(data, "source-bindings.schema.json", path)
        archive_id = data.get("archive_id")
        if self.archive_config and archive_id != self.archive_config.get("archive_id"):
            self.error("source_bindings_archive_mismatch", "source-bindings.yml archive_id must match archive.yml archive_id.", path)
        sources = data.get("sources") if isinstance(data.get("sources"), list) else []
        seen: set[str] = set()
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                self.error("source_binding_invalid", f"source-bindings.yml sources[{index}] must be an object.", path)
                continue
            source_id = source.get("source_id")
            if not isinstance(source_id, str) or not source_id.strip():
                self.error("source_binding_id_missing", f"source-bindings.yml sources[{index}] missing source_id.", path)
            elif source_id in seen:
                self.error("source_binding_id_duplicate", f"Duplicate source_id in source-bindings.yml: {source_id}", path)
            else:
                seen.add(source_id)
            source_type = source.get("source_type")
            if source_type not in archive_services.SOURCE_TYPES:
                self.error("source_binding_type_invalid", f"Invalid source_type in source-bindings.yml: {source_type}", path)
            root_ref = source.get("root_ref")
            if not isinstance(root_ref, str) or not root_ref.strip():
                self.error("source_binding_root_ref_missing", f"Source binding missing root_ref: {source_id}", path)
            else:
                self._check_source_ref_is_portable(root_ref, path, f"sources[{index}].root_ref")
            self._check_source_binding_secret_refs(source, path, f"$.sources[{index}]")

    def _check_source_ref_is_portable(self, value: str, path: Path, field_path: str) -> None:
        if value.startswith("archive:"):
            try:
                resolve_archive_relative_path(self.archive_root, value.removeprefix("archive:"))
            except ArchivePathError as exc:
                self.error("source_binding_archive_ref_unsafe", f"{field_path} has an unsafe archive ref: {value} ({exc})", path)
            return
        if contains_forbidden_location_reference(value) or self._looks_like_absolute_path(value):
            self.error(
                "source_binding_sensitive_path",
                f"{field_path} should store an env/keyring/root ref, not an absolute path or provider URL.",
                path,
            )

    def _check_source_binding_secret_refs(self, value: Any, path: Path, field_path: str = "$") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{field_path}.{key}"
                if self._is_source_secret_field(str(key)) and not str(key).endswith("_ref") and not str(key).endswith("_env"):
                    if isinstance(child, str) and child.strip():
                        self.error(
                            "source_bindings_secret_field",
                            f"Source binding field should reference an env var or keyring entry, not store a secret-like value: {child_path}",
                            path,
                        )
                self._check_source_binding_secret_refs(child, path, child_path)
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                self._check_source_binding_secret_refs(child, path, f"{field_path}[{index}]")
            return
        if isinstance(value, str) and SECRET_VALUE_RE.search(f"value: {value}"):
            self.error(
                "source_bindings_secret_value",
                f"Source binding appears to contain a secret-like value at {field_path}. Use an env/keyring reference instead.",
                path,
            )

    def _is_source_secret_field(self, key: str) -> bool:
        normalized = key.lower()
        return normalized in {"token", "api_token", "secret", "password", "credential", "credentials", "database_url"}

    def _looks_like_absolute_path(self, value: str) -> bool:
        normalized = value.strip().replace("\\", "/")
        return bool(re.match(r"^[A-Za-z]:/", normalized)) or normalized.startswith("/") or normalized.startswith("//")

    def _is_provider_secret_field(self, key: str) -> bool:
        normalized = key.lower()
        return normalized in {
            "token",
            "api_token",
            "secret",
            "password",
            "credential",
            "credentials",
            "access_key_id",
            "secret_access_key",
            "application_key",
            "database_url",
        }

    def _check_sqlite_schema(self) -> None:
        path = self.archive_root / "db" / "schema.sql"
        if not path.is_file():
            return
        try:
            sql = path.read_text(encoding="utf-8")
            conn = sqlite3.connect(":memory:")
            try:
                conn.executescript(sql)
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self.error("sqlite_schema_invalid", f"SQLite schema failed to parse: {exc}", path)

    def _check_object_manifest(self) -> None:
        path = self.archive_root / "objects" / "manifests" / "files.jsonl"
        if not path.is_file():
            return

        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                self.error("object_manifest_json_invalid", f"Invalid JSON on line {line_number}: {exc}", path)
                continue
            self._check_schema(record, "object-manifest-entry.schema.json", path)

            object_id = record.get("object_id")
            sha256 = record.get("sha256")
            if not isinstance(object_id, str) or not OBJECT_ID_RE.match(object_id):
                self.error("object_id_invalid", f"Invalid object_id on line {line_number}: {object_id}", path)
                continue
            if not isinstance(sha256, str) or not SHA256_RE.match(sha256):
                self.error("sha256_invalid", f"Invalid sha256 on line {line_number}: {sha256}", path)
            if isinstance(sha256, str) and object_id != f"sha256:{sha256}":
                self.error("object_id_sha_mismatch", f"object_id and sha256 mismatch on line {line_number}.", path)
            if object_id in self.manifest_objects:
                self.error("object_id_duplicate", f"Duplicate object_id in manifest: {object_id}", path)
            self.manifest_objects[object_id] = record

            if "logical_key" not in record:
                self.error("object_logical_key_missing", f"Object missing logical_key: {object_id}", path)
            if "locations" not in record or not isinstance(record.get("locations"), list):
                self.warn("object_locations_missing", f"Object has no locations list: {object_id}", path)

            self._check_local_object_locations(record, path)

    def _check_local_object_locations(self, record: dict[str, Any], manifest_path: Path) -> None:
        object_id = record.get("object_id")
        expected_sha = record.get("sha256")
        expected_size = record.get("size_bytes")
        locations = record.get("locations") or []
        if not isinstance(locations, list):
            return

        for location in locations:
            if not isinstance(location, dict):
                self.warn("object_location_invalid", f"Object location is not an object: {object_id}", manifest_path)
                continue
            if location.get("provider") != "local":
                continue
            relative_path = location.get("path")
            if not isinstance(relative_path, str):
                self.warn("local_object_path_missing", f"Local object location missing path: {object_id}", manifest_path)
                continue
            try:
                local_path = resolve_archive_relative_path(self.archive_root, relative_path)
            except ArchivePathError as exc:
                self.error("local_object_path_unsafe", f"Local object location has an unsafe path: {relative_path} ({exc})", manifest_path)
                continue
            if not local_path.is_file():
                self.warn("local_object_missing", f"Local object file is missing: {relative_path}", local_path)
                continue
            if isinstance(expected_size, int) and local_path.stat().st_size != expected_size:
                self.error("local_object_size_mismatch", f"Local object size mismatch: {relative_path}", local_path)
            if isinstance(expected_sha, str):
                actual_sha = sha256_file(local_path)
                if actual_sha != expected_sha:
                    self.error("local_object_sha_mismatch", f"Local object SHA-256 mismatch: {relative_path}", local_path)

    def _check_source_maps(self) -> None:
        root = self.archive_root / "source-maps"
        if not root.is_dir():
            return
        known_sources = self._known_source_ids()
        seen_items: set[str] = set()
        for path in sorted(root.glob("*.jsonl")):
            if not self._path_stays_inside_archive(path):
                continue
            for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    self.error("source_map_json_invalid", f"Invalid JSON on line {line_number}: {exc}", path)
                    continue
                if not isinstance(record, dict):
                    self.error("source_map_entry_invalid", f"Source map line {line_number} must be a JSON object.", path)
                    continue
                self._check_schema(record, "source-map-entry.schema.json", path)
                source_id = record.get("source_id")
                if known_sources and source_id not in known_sources:
                    self.error("source_map_unknown_source", f"Source map references unknown source_id: {source_id}", path)
                item_id = record.get("item_id")
                if isinstance(item_id, str):
                    if item_id in seen_items:
                        self.error("source_map_item_duplicate", f"Duplicate source map item_id: {item_id}", path)
                    seen_items.add(item_id)
                relative_path = record.get("relative_path")
                if isinstance(relative_path, str) and self._relative_source_path_is_unsafe(relative_path):
                    self.error("source_map_relative_path_unsafe", f"Source map relative_path is unsafe: {relative_path}", path)
                if not relative_path and not record.get("external_url") and not record.get("object_id"):
                    self.error("source_map_location_missing", "Source map entry needs relative_path, external_url, or object_id.", path)

    def _known_source_ids(self) -> set[str]:
        path = self.archive_root / "source-bindings.yml"
        data = self._load_yaml_file(path, missing_ok=True)
        if not isinstance(data, dict):
            return set()
        sources = data.get("sources") if isinstance(data.get("sources"), list) else []
        return {item.get("source_id") for item in sources if isinstance(item, dict) and isinstance(item.get("source_id"), str)}

    def _relative_source_path_is_unsafe(self, value: str) -> bool:
        normalized = value.replace("\\", "/").strip()
        return (
            not normalized
            or normalized.startswith("/")
            or normalized.startswith("//")
            or bool(re.match(r"^[A-Za-z]:/", normalized))
            or ".." in normalized.split("/")
        )

    def _check_zettels(self) -> None:
        for folder, expected_status in [("zettels", "canonical"), ("inbox", "draft")]:
            root = self.archive_root / folder
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*.md")):
                if not self._path_stays_inside_archive(path):
                    continue
                self._check_zettel_file(path, expected_status)

    def _check_zettel_file(self, path: Path, expected_status: str) -> None:
        text = path.read_text(encoding="utf-8")
        if contains_forbidden_location_reference(text):
            self.error("provider_url_in_zettel", "Zettel appears to contain a provider URL or local absolute path.", path)

        frontmatter = parse_frontmatter(text)
        if frontmatter is None:
            self.error("zettel_frontmatter_missing", "Zettel is missing YAML frontmatter.", path)
            return

        data = self._load_yaml_text(frontmatter, path)
        if not isinstance(data, dict):
            self.error("zettel_frontmatter_invalid", "Zettel frontmatter must be a YAML object.", path)
            return
        self._check_schema(data, "zettel-frontmatter.schema.json", path)

        for field in REQUIRED_ZETTEL_FIELDS:
            if field not in data:
                self.error("zettel_field_missing", f"Zettel missing required frontmatter field: {field}", path)

        status = data.get("status")
        if status not in ALLOWED_ZETTEL_STATUS:
            self.error("zettel_status_invalid", f"Invalid zettel status: {status}", path)
        elif status != expected_status:
            self.warn("zettel_status_path_mismatch", f"Zettel in {path.parent.name}/ has status {status}, expected {expected_status}.", path)

        if expected_status == "canonical" and "mint" not in data and "promotion" not in data:
            self.warn("canonical_lifecycle_metadata_missing", "Canonical zettel has no mint or v0.2 promotion metadata.", path)
        if "mint" in data:
            self._check_zettel_mint_metadata(data, path)
        if "kind" not in data:
            self.warn("zettel_kind_missing", "Zettel has no v0.2 kind field.", path)

        self._check_zettel_assets(data, path)
        self._check_zettel_edges(data, path)

    def _check_zettel_mint_metadata(self, data: dict[str, Any], path: Path) -> None:
        mint = data.get("mint")
        if not isinstance(mint, dict):
            self.error("mint_metadata_invalid", "Zettel mint metadata must be an object.", path)
            return
        if mint.get("stage") != "minted":
            self.error("mint_stage_invalid", "Zettel mint.stage must be minted.", path)
        if mint.get("authority_mode") != archive_services.MINT_AUTHORITY_MODE:
            self.error("mint_authority_mode_invalid", "Zettel mint.authority_mode must be basic in the current v0.2 line.", path)
        for field in ["minted_at", "reviewed_by", "receipt_path", "draft_snapshot_path", "checklist_version"]:
            if not mint.get(field):
                self.error("mint_metadata_field_missing", f"Zettel mint metadata missing field: {field}.", path)

        receipt_path = self._resolve_archive_file_ref(
            mint.get("receipt_path"),
            path,
            code_prefix="mint_receipt",
            label="Zettel mint.receipt_path",
            required=True,
        )
        if receipt_path and receipt_path.suffix != ".json":
            self.error("mint_receipt_path_invalid", "Zettel mint.receipt_path must point to a JSON receipt.", path)
        if receipt_path and receipt_path.is_file():
            receipt = self._load_json_file(receipt_path)
            if isinstance(receipt, dict):
                expected_target = self._display_path(path)
                actual_target = receipt.get("target", {}).get("path") if isinstance(receipt.get("target"), dict) else None
                if actual_target != expected_target:
                    self.error(
                        "mint_receipt_target_mismatch",
                        "Zettel mint receipt target.path does not point back to this zettel.",
                        path,
                    )
                receipt_zettel = receipt.get("zettel") if isinstance(receipt.get("zettel"), dict) else {}
                if receipt_zettel.get("id") != data.get("id"):
                    self.error("mint_receipt_zettel_mismatch", "Zettel mint receipt zettel.id does not match this zettel id.", path)

        self._resolve_archive_file_ref(
            mint.get("draft_snapshot_path"),
            path,
            code_prefix="mint_snapshot",
            label="Zettel mint.draft_snapshot_path",
            required=True,
        )

    def _check_zettel_assets(self, data: dict[str, Any], path: Path) -> None:
        assets = data.get("assets") or []
        if not isinstance(assets, list):
            self.error("zettel_assets_invalid", "Zettel assets must be a list.", path)
            return
        for asset in assets:
            if not isinstance(asset, dict):
                self.error("zettel_asset_invalid", "Zettel asset must be an object.", path)
                continue
            object_id = asset.get("object_id")
            if not isinstance(object_id, str) or not OBJECT_ID_RE.match(object_id):
                self.error("zettel_asset_object_id_invalid", f"Invalid asset object_id: {object_id}", path)
                continue
            if self.manifest_objects and object_id not in self.manifest_objects:
                self.warn("zettel_asset_missing_manifest_record", f"Asset object_id not found in manifest: {object_id}", path)

    def _check_zettel_edges(self, data: dict[str, Any], path: Path) -> None:
        edges = data.get("edges") or []
        if not isinstance(edges, list):
            self.error("zettel_edges_invalid", "Zettel edges must be a list.", path)
            return
        for edge in edges:
            if not isinstance(edge, dict):
                self.error("zettel_edge_invalid", "Zettel edge must be an object.", path)
                continue
            edge_type = edge.get("type")
            if edge_type and self.allowed_link_types and edge_type not in self.allowed_link_types:
                self.warn("zettel_edge_type_unknown", f"Edge type is not defined in zettel-kasten/types.yml: {edge_type}", path)

    def _check_views(self) -> None:
        root = self.archive_root / "views"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*.yml")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_yaml_file(path)
            if isinstance(data, dict):
                self._check_schema(data, "view.schema.json", path)

    def _check_workpacks(self) -> None:
        root = self.archive_root / "workpacks"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*/package.yml")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_yaml_file(path)
            if isinstance(data, dict):
                self._check_schema(data, "workpack.schema.json", path)

    def _check_external_import_receipts(self) -> None:
        root = self.archive_root / "receipts" / "import"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*.external-import.json")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "external-import-receipt.schema.json", path)
            if data.get("action") != "import_external_archive":
                self.error(
                    "external_import_receipt_action_invalid",
                    "External import receipt action must be import_external_archive.",
                    path,
                )
            for field in ["source_export", "scope_gate", "trust_gate", "lineage"]:
                if not isinstance(data.get(field), dict):
                    self.error(
                        "external_import_receipt_field_missing",
                        f"External import receipt must contain object field: {field}.",
                        path,
                    )

    def _check_source_scan_receipts(self) -> None:
        root = self.archive_root / "receipts" / "sources"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*.source-scan.json")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "source-scan-receipt.schema.json", path)
            if data.get("action") != "scan_archive_source":
                self.error(
                    "source_scan_receipt_action_invalid",
                    "Source scan receipt action must be scan_archive_source.",
                    path,
                )
            for field in ["scope_gate", "trust_gate", "lineage", "source_root_resolution"]:
                if not isinstance(data.get(field), dict):
                    self.error(
                        "source_scan_receipt_field_missing",
                        f"Source scan receipt must contain object field: {field}.",
                        path,
                    )

    def _check_recovery_receipts(self) -> None:
        root = self.archive_root / "receipts" / "recovery"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*.restore-drill.json")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "restore-drill-receipt.schema.json", path)
            if data.get("action") != "restore_drill":
                self.error(
                    "restore_drill_receipt_action_invalid",
                    "Restore drill receipt action must be restore_drill.",
                    path,
                )
            for field in ["copy_plan", "validation", "result"]:
                if not isinstance(data.get(field), dict):
                    self.error(
                        "restore_drill_receipt_field_missing",
                        f"Restore drill receipt must contain object field: {field}.",
                        path,
                    )

    def _check_lineage_receipts(self) -> None:
        root = self.archive_root / "receipts" / "lineage"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*.ownership-transfer.json")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "ownership-transfer-receipt.schema.json", path)
            if data.get("action") != "transfer_archive_ownership":
                self.error(
                    "ownership_transfer_receipt_action_invalid",
                    "Ownership transfer receipt action must be transfer_archive_ownership.",
                    path,
                )
            for field in ["scope_manifest", "trust_gate", "ownership_gate"]:
                if not isinstance(data.get(field), dict):
                    self.error(
                        "ownership_transfer_receipt_gate_missing",
                        f"Ownership transfer receipt must contain object field: {field}.",
                        path,
                    )

    def _check_mint_receipts(self) -> None:
        root = self.archive_root / "receipts" / "mint"
        if not root.is_dir():
            return
        for path in sorted(root.glob("*.mint.json")):
            if not self._path_stays_inside_archive(path):
                continue
            data = self._load_json_file(path)
            if not isinstance(data, dict):
                continue
            self._check_schema(data, "mint-receipt.schema.json", path)
            if data.get("action") != "mint_zettel":
                self.error("mint_receipt_action_invalid", "Mint receipt action must be mint_zettel.", path)
            if data.get("authority_mode") != archive_services.MINT_AUTHORITY_MODE:
                self.error("mint_receipt_authority_mode_invalid", "Mint receipt authority_mode must be basic in the current v0.2 line.", path)
            if data.get("dry_run") is False and not data.get("reviewed_by"):
                self.error("mint_receipt_reviewer_missing", "Applied mint receipt must include reviewed_by.", path)
            for field in ["source", "target", "snapshot", "zettel", "result"]:
                if not isinstance(data.get(field), dict):
                    self.error("mint_receipt_field_missing", f"Mint receipt must contain object field: {field}.", path)

            self._check_mint_receipt_status(data, path, "source", "draft")
            self._check_mint_receipt_status(data, path, "target", "canonical")
            self._check_mint_receipt_file_ref(data, path, "source")
            target_path = self._check_mint_receipt_file_ref(data, path, "target")
            self._check_mint_receipt_file_ref(data, path, "snapshot")

            if target_path is not None:
                frontmatter = parse_frontmatter(target_path.read_text(encoding="utf-8"))
                if frontmatter is None:
                    self.error("mint_receipt_target_frontmatter_missing", "Mint receipt target has no zettel frontmatter.", path)
                    continue
                target_data = self._load_yaml_text(frontmatter, target_path)
                if not isinstance(target_data, dict):
                    continue
                mint = target_data.get("mint") if isinstance(target_data.get("mint"), dict) else {}
                receipt_relative = self._display_path(path)
                if mint.get("receipt_path") != receipt_relative:
                    self.error(
                        "mint_receipt_canonical_link_missing",
                        "Mint receipt target zettel does not link back through mint.receipt_path.",
                        path,
                    )

    def _check_mint_receipt_status(self, data: dict[str, Any], path: Path, section: str, expected_status: str) -> None:
        section_data = data.get(section)
        if not isinstance(section_data, dict):
            return
        status = section_data.get("status")
        if status != expected_status:
            self.error(
                "mint_receipt_status_invalid",
                f"Mint receipt {section}.status must be {expected_status}.",
                path,
            )

    def _check_mint_receipt_file_ref(self, data: dict[str, Any], path: Path, section: str) -> Path | None:
        section_data = data.get(section)
        if not isinstance(section_data, dict):
            return None
        resolved = self._resolve_archive_file_ref(
            section_data.get("path"),
            path,
            code_prefix=f"mint_receipt_{section}",
            label=f"Mint receipt {section}.path",
            required=True,
        )
        if resolved is None:
            return None
        expected_sha = section_data.get("sha256")
        if not isinstance(expected_sha, str) or not SHA256_RE.match(expected_sha):
            self.error("mint_receipt_sha_invalid", f"Mint receipt {section}.sha256 must be a lowercase SHA-256 hex digest.", path)
            return resolved
        actual_sha = sha256_file(resolved)
        if actual_sha != expected_sha:
            self.error("mint_receipt_sha_mismatch", f"Mint receipt {section}.sha256 does not match the referenced file.", path)
        return resolved

    def _resolve_archive_file_ref(
        self,
        value: Any,
        path: Path,
        *,
        code_prefix: str,
        label: str,
        required: bool,
    ) -> Path | None:
        if not isinstance(value, str) or not value.strip():
            if required:
                self.error(f"{code_prefix}_path_missing", f"{label} is missing.", path)
            return None
        try:
            resolved = resolve_archive_relative_path(self.archive_root, value)
        except ArchivePathError as exc:
            self.error(f"{code_prefix}_path_unsafe", f"{label} is unsafe: {value} ({exc})", path)
            return None
        if not resolved.is_file():
            self.error(f"{code_prefix}_path_missing", f"{label} points to a missing file: {value}", path)
            return None
        return resolved

    def _check_zettel_kasten_layer(self) -> None:
        root = self.archive_root / "zettel-kasten"
        if not root.is_dir():
            return
        for filename, schema_name in ZETTEL_KASTEN_SCHEMA_FILES.items():
            path = root / filename
            data = self._load_yaml_file(path, missing_ok=True)
            if isinstance(data, dict):
                self._check_schema(data, schema_name, path)

    def _check_schema(self, data: Any, schema_name: str, path: Path) -> None:
        for issue in validate_schema(data, schema_name):
            self.error(issue.code, f"{schema_name}: {issue.message}", path)

    def _check_local_profile_and_secret_safety(self) -> None:
        self._check_gitignore_secret_patterns()
        for path in sorted(self.archive_root.rglob("*")):
            if not path.is_file() or not self._path_stays_inside_archive(path) or self._is_ignored_scan_path(path):
                continue
            relative = self._display_path(path) or str(path)
            name = path.name.lower()
            if self._is_secret_filename(path):
                self.error("secret_file_detected", f"Secret-like local file should not live in the archive: {relative}", path)
                continue
            if self._should_scan_secret_content(path):
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                if SECRET_VALUE_RE.search(text):
                    self.error("secret_value_detected", f"Secret-like value found in archive file: {relative}", path)
            if self._is_local_profile_path(path):
                self._check_local_profile_file(path)

    def _check_gitignore_secret_patterns(self) -> None:
        path = self.archive_root / ".gitignore"
        if not path.is_file():
            self.warn("local_profile_gitignore_missing", "Archive has no .gitignore protecting local profiles and secrets.", path)
            return
        lines = {
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        missing = [pattern for pattern in RECOMMENDED_GITIGNORE_PATTERNS if pattern not in lines]
        if missing:
            self.warn(
                "local_profile_gitignore_incomplete",
                "Archive .gitignore is missing local profile/secret pattern(s): " + ", ".join(missing),
                path,
            )

    def _is_ignored_scan_path(self, path: Path) -> bool:
        relative_parts = path.resolve().relative_to(self.archive_root).parts
        ignored_dirs = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv"}
        return any(part in ignored_dirs for part in relative_parts)

    def _is_secret_filename(self, path: Path) -> bool:
        relative = self._display_path(path) or path.name
        normalized = relative.replace("\\", "/")
        name = path.name.lower()
        if name == ".env.example":
            return False
        if name in SECRET_FILENAME_EXACT:
            return True
        if name.startswith(".env."):
            return True
        if name.endswith(SECRET_FILENAME_SUFFIXES):
            return True
        return "/secrets/" in f"/{normalized.lower()}"

    def _should_scan_secret_content(self, path: Path) -> bool:
        return path.suffix.lower() in SECRET_SCAN_EXTENSIONS or path.name.lower().startswith(".env")

    def _is_local_profile_path(self, path: Path) -> bool:
        relative = (self._display_path(path) or "").replace("\\", "/")
        return relative.endswith(".local.yml") or relative.endswith(".local.yaml") or relative.startswith(LOCAL_PROFILE_ROOTS)

    def _check_local_profile_file(self, path: Path) -> None:
        data = self._load_yaml_file(path, missing_ok=True) if path.suffix.lower() in {".yml", ".yaml"} else None
        if not isinstance(data, dict):
            return
        env = data.get("env")
        if isinstance(env, dict):
            forbidden_env_keys = [key for key in env if key not in {"required", "optional"}]
            if forbidden_env_keys:
                self.warn(
                    "local_profile_env_values",
                    "Local profiles should list required/optional env var names, not env values: " + ", ".join(forbidden_env_keys),
                    path,
                )
        if any(key in data for key in ["password", "token", "secret", "api_key", "credential"]):
            self.error("local_profile_secret_value", "Local profile appears to contain a secret value.", path)

    def _check_symlink_boundaries(self) -> None:
        for path in sorted(self.archive_root.rglob("*")):
            if path.is_symlink() and not is_path_within_root(path, self.archive_root):
                self.error(
                    "archive_symlink_escapes_root",
                    "Archive symlink resolves outside the archive root.",
                    path,
                )

    def _path_stays_inside_archive(self, path: Path) -> bool:
        if is_path_within_root(path, self.archive_root):
            return True
        self.error(
            "archive_path_escapes_root",
            "Archive file resolves outside the archive root, usually through a symlink.",
            path,
        )
        return False

    def _load_allowed_link_types(self) -> set[str]:
        candidates = [
            self.archive_root / "zettel-kasten" / "types.yml",
            KIT_ZETTEL_KASTEN_ROOT / "types.yml",
        ]
        for path in candidates:
            data = self._load_yaml_file(path, missing_ok=True)
            if not isinstance(data, dict):
                continue
            link_types = data.get("link_types") or []
            if isinstance(link_types, list):
                return {item.get("id") for item in link_types if isinstance(item, dict) and item.get("id")}
        return set()

    def _load_yaml_file(self, path: Path, missing_ok: bool = False) -> Any:
        if not path.is_file():
            if not missing_ok:
                self.error("yaml_file_missing", "YAML file is missing.", path)
            return None
        if self._path_lexically_inside_archive(path) and not self._path_stays_inside_archive(path):
            return None
        try:
            return load_yaml(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.error("yaml_parse_error", f"YAML failed to parse: {exc}", path)
            return None

    def _load_yaml_text(self, text: str, path: Path) -> Any:
        try:
            return load_yaml(text)
        except Exception as exc:
            self.error("yaml_parse_error", f"YAML failed to parse: {exc}", path)
            return None

    def _load_json_file(self, path: Path) -> Any:
        if self._path_lexically_inside_archive(path) and not self._path_stays_inside_archive(path):
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self.error("json_parse_error", f"JSON failed to parse: {exc}", path)
            return None
        except OSError as exc:
            self.error("json_read_error", f"JSON file could not be read: {exc}", path)
            return None

    def _path_lexically_inside_archive(self, path: Path) -> bool:
        try:
            return path.absolute().is_relative_to(self.archive_root)
        except (OSError, RuntimeError, ValueError):
            return False


def require_yaml() -> None:
    if yaml is None:
        raise SystemExit("PyYAML is required. Install it with: python -m pip install PyYAML")


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_doctor(args: argparse.Namespace) -> int:
    doctor = Doctor(Path(args.archive_root))
    diagnostics = doctor.run()
    errors = [item for item in diagnostics if item.severity == "ERROR"]
    warnings = [item for item in diagnostics if item.severity == "WARN"]

    if args.json or getattr(args, "format", "text") == "json":
        print_json([item.as_dict() for item in diagnostics])
    else:
        print_diagnostics(diagnostics, errors, warnings)

    if errors or (args.strict and warnings):
        return 1
    return 0


def command_validate(args: argparse.Namespace) -> int:
    doctor = Doctor(Path(args.archive_root))
    diagnostics = doctor.run()
    errors = [item for item in diagnostics if item.severity == "ERROR"]
    warnings = [item for item in diagnostics if item.severity == "WARN"]
    ok = not errors and (args.allow_warnings or not warnings)

    if args.format == "json":
        print_json(
            {
                "ok": ok,
                "errors": len(errors),
                "warnings": len(warnings),
                "diagnostics": [item.as_dict() for item in diagnostics],
            }
        )
    else:
        print_diagnostics(diagnostics, errors, warnings)
        print("Validation passed." if ok else "Validation failed.")

    return 0 if ok else 1


def command_list_zettels(args: argparse.Namespace) -> int:
    try:
        result = archive_services.list_zettels(Path(args.archive_root), status=args.status, limit=args.limit)
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Found {result['count']} zettel(s).")
        for zettel in result["zettels"]:
            print(
                "\t".join(
                    [
                        str(zettel.get("status") or "-"),
                        str(zettel.get("id") or "-"),
                        str(zettel.get("title") or "(untitled)"),
                        str(zettel.get("path") or "-"),
                    ]
                )
            )
    return 0


def command_read_zettel(args: argparse.Namespace) -> int:
    try:
        result = archive_services.read_zettel(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
        )
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        frontmatter = result["frontmatter"]
        print(f"Path: {result['path']}")
        if isinstance(frontmatter, dict):
            print(f"ID: {frontmatter.get('id', '-')}")
            print(f"Title: {frontmatter.get('title', '-')}")
            print(f"Status: {frontmatter.get('status', '-')}")
        print()
        print(result["body"].rstrip())
    return 0


def command_create_draft(args: argparse.Namespace) -> int:
    try:
        body = read_body_arg(args)
        result = archive_services.create_draft_zettel(
            Path(args.archive_root),
            title=args.title,
            body=body,
            archive_id=args.archive_id,
            kind=args.kind,
            facets=parse_key_value_pairs(args.facet or []),
            created_by="cli:archive",
            source="cli_command",
        )
    except (archive_services.ArchiveServiceError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Created draft zettel {result['zettel_id']} at {result['path']}")
    return 0


def command_promote(args: argparse.Namespace) -> int:
    if args.dry_run:
        try:
            result = archive_services.promote_zettel_dry_run(
                Path(args.archive_root),
                zettel_id=args.zettel_id,
                relative_path=args.path,
            )
        except archive_services.ArchiveServiceError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if args.format == "json":
            print_json(result)
        else:
            print(f"Dry-run promotion for {result.get('zettel_id') or result['draft_path']}")
            print(f"Draft path: {result['draft_path']}")
            print(f"Proposed canonical path: {result['proposed_canonical_path']}")
            print(f"Proposed receipt path: {result['proposed_receipt_path']}")
            if result.get("checklist"):
                print("Checklist:")
                for item in result["checklist"]:
                    print(f"- {item['id']}: {item['status']} ({item['source']})")
            if result.get("near_duplicates"):
                print("Near duplicates:")
                for item in result["near_duplicates"]:
                    print(f"- {item['path']}: {item['reason']}")
            if result["blockers"]:
                print("Blockers:")
                for blocker in result["blockers"]:
                    print(f"- {blocker}")
            if result["warnings"]:
                print("Warnings:")
                for warning in result["warnings"]:
                    print(f"- {warning}")
            print("Promotion dry-run passed." if result["ok"] else "Promotion dry-run blocked.")
        return 0 if result["ok"] else 1

    if not args.approve:
        print("Real promotion requires --approve.", file=sys.stderr)
        return 1
    if not args.reviewed_by:
        print("Real promotion requires --reviewed-by.", file=sys.stderr)
        return 1

    try:
        result = archive_services.promote_zettel(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            reviewed_by=args.reviewed_by,
            allow_warnings=args.allow_warnings,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Promoted {result['zettel_id']} to canonical memory.")
        print(f"Canonical path: {result['canonical_path']}")
        print(f"Receipt path: {result['receipt_path']}")
        if result["warnings"]:
            print("Warnings approved:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0


def command_mint_zettel(args: argparse.Namespace) -> int:
    if args.dry_run:
        try:
            result = archive_services.mint_zettel_dry_run(
                Path(args.archive_root),
                zettel_id=args.zettel_id,
                relative_path=args.path,
            )
        except archive_services.ArchiveServiceError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if args.format == "json":
            print_json(result)
        else:
            print(f"Dry-run mint for {result.get('zettel_id') or result['draft_path']}")
            print(f"Draft path: {result['draft_path']}")
            print(f"Proposed canonical path: {result['proposed_canonical_path']}")
            print(f"Proposed mint receipt path: {result['proposed_mint_receipt_path']}")
            print(f"Proposed draft snapshot path: {result['proposed_draft_snapshot_path']}")
            if result.get("checklist"):
                print("Checklist:")
                for item in result["checklist"]:
                    print(f"- {item['id']}: {item['status']} ({item['source']})")
            if result.get("near_duplicates"):
                print("Near duplicates:")
                for item in result["near_duplicates"]:
                    print(f"- {item['path']}: {item['reason']}")
            if result["blockers"]:
                print("Blockers:")
                for blocker in result["blockers"]:
                    print(f"- {blocker}")
            if result["warnings"]:
                print("Warnings:")
                for warning in result["warnings"]:
                    print(f"- {warning}")
            print("Mint dry-run passed." if result["ok"] else "Mint dry-run blocked.")
        return 0 if result["ok"] else 1

    if not args.approve:
        print("Real minting requires --approve.", file=sys.stderr)
        return 1
    if not args.reviewed_by:
        print("Real minting requires --reviewed-by.", file=sys.stderr)
        return 1

    try:
        result = archive_services.mint_zettel(
            Path(args.archive_root),
            zettel_id=args.zettel_id,
            relative_path=args.path,
            reviewed_by=args.reviewed_by,
            allow_warnings=args.allow_warnings,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Minted {result['zettel_id']} into canonical private archive memory.")
        print(f"Canonical path: {result['canonical_path']}")
        print(f"Mint receipt path: {result['mint_receipt_path']}")
        print(f"Draft snapshot path: {result['draft_snapshot_path']}")
        if result["warnings"]:
            print("Warnings approved:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0


def command_index(args: argparse.Namespace) -> int:
    try:
        result = archive_services.index_archive(Path(args.archive_root))
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(
            "Indexed "
            f"{result['zettels']} zettel(s), "
            f"{result['objects']} object(s), "
            f"{result['views']} view(s), "
            f"{result['source_map_entries']} source map item(s) "
            f"at {result['index_path']}"
        )
    return 0


def command_search(args: argparse.Namespace) -> int:
    try:
        result = archive_services.search_archive(Path(args.archive_root), args.query, limit=args.limit)
    except archive_services.ArchiveServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Found {result['count']} result(s).")
        for item in result["results"]:
            print(
                "\t".join(
                    [
                        str(item.get("type") or "-"),
                        str(item.get("id") or "-"),
                        str(item.get("title") or "(untitled)"),
                        str(item.get("path") or "-"),
                        str(item.get("snippet") or ""),
                    ]
                )
            )
    return 0


def command_pack(args: argparse.Namespace) -> int:
    try:
        result = archive_services.pack_work_context(
            Path(args.archive_root),
            view_id=args.view,
            purpose=args.purpose,
            mode=args.mode,
            target_archive=args.target_archive,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Created workpack {result['package_id']} at {result['package_path']}")
        print(f"View: {result['view_id']}")
        print(f"Mode: {result['mode']}")
        print(f"Zettels: {result['zettels']}")
        print(f"Objects: {result['objects']} metadata record(s)")
    return 0


def command_import_workpack(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Only --dry-run workpack import is implemented. Real import is intentionally unavailable.", file=sys.stderr)
        return 1
    try:
        result = archive_services.import_workpack_dry_run_with_trust(
            Path(args.archive_root),
            Path(args.workpack),
            counterparty_id=args.counterparty_id,
            counterparty_fingerprint=args.counterparty_fingerprint,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result["ok"] else "blocked"
        print(f"Workpack import dry-run {state}: {result['package_id']}")
        print(f"Target archive: {result['target_archive']}")
        print(f"Proposed receipt path: {result['proposed_receipt_path']}")
        print(f"Zettels: {len(result['zettels'])}")
        print(f"Objects: {len(result['objects'])}")
        print(f"Scope gate included zettels: {len(result['scope_gate']['included_zettels'])}")
        print(f"Trust gate: {result['trust_gate']['status']}")
        if result["blockers"]:
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result["warnings"]:
            print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_import_external(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("External import requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("External import requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        if args.dry_run:
            result = archive_services.external_import_dry_run(
                Path(args.archive_root),
                Path(args.export),
                source_system=args.source,
                limit=args.limit,
            )
        else:
            result = archive_services.import_external_archive(
                Path(args.archive_root),
                Path(args.export),
                source_system=args.source,
                reviewed_by=args.reviewed_by,
                limit=args.limit,
            )
    except (archive_services.ArchiveServiceError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
        return 0 if result["ok"] else 1

    mode = "dry-run" if result["dry_run"] else "applied"
    state = "passed" if result["ok"] else "blocked"
    print(f"External import {mode} {state}.")
    print(f"Source: {result['source_system']}")
    print(f"Target archive: {result['target_archive']}")
    if result["dry_run"]:
        print(f"Items: {result['item_count']}")
        print(f"Proposed receipt path: {result['proposed_receipt_path']}")
    else:
        print(f"Imported: {result['imported_count']}")
        print(f"Receipt path: {result['receipt_path']}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_share(args: argparse.Namespace) -> int:
    if not args.dry_run:
        print("Only --dry-run archive sharing is implemented. Real share/merge/fork is intentionally unavailable.", file=sys.stderr)
        return 1
    try:
        result = archive_services.share_archive_scope_dry_run(
            Path(args.archive_root),
            view_id=args.view,
            target_archive=args.target_archive,
            counterparty_id=args.counterparty_id,
            counterparty_fingerprint=args.counterparty_fingerprint,
            allow_sensitive=args.allow_sensitive,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        state = "passed" if result["ok"] else "blocked"
        print(f"Archive share dry-run {state}.")
        print(f"Source archive: {result['source_archive']}")
        print(f"Target archive: {result['target_archive']}")
        print(f"View: {result['view_id']}")
        print(f"Included zettels: {len(result['scope_gate']['included'])}")
        print(f"Excluded zettels: {len(result['scope_gate']['excluded'])}")
        print(f"Trust gate: {result['trust_gate']['status']}")
        print(f"Proposed receipt path: {result['proposed_receipt_path']}")
        if result["blockers"]:
            print("Blockers:")
            for blocker in result["blockers"]:
                print(f"- {blocker}")
        if result["warnings"]:
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_providers(args: argparse.Namespace) -> int:
    try:
        result = archive_services.provider_bindings_summary(Path(args.archive_root))
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Provider bindings for {result['archive_id']}: {result['binding_count']} configured.")
        print(f"Path: {result['provider_bindings_path']}")
        print(f"External changes: {result['provider_change_plan']['status']}")
        for provider in result["providers"]:
            state = "enabled" if provider["enabled"] else "disabled"
            print(f"- {provider['provider']} ({state}): {provider['binding_id']}")
    return 0


def command_sources(args: argparse.Namespace) -> int:
    try:
        result = archive_services.list_sources(Path(args.archive_root))
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Sources for {result['archive_id']}: {result['source_count']} configured.")
        print(f"Path: {result['source_bindings_path']}")
        for source in result["sources"]:
            state = "enabled" if source["enabled"] else "disabled"
            mapped = source["mapped_items"]
            print(f"- {source['source_id']} ({source['source_type']}, {state}): {mapped} mapped item(s)")
    return 0


def command_scan_source(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("Source scan requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("Source scan requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        if args.dry_run:
            result = archive_services.source_scan_dry_run(
                Path(args.archive_root),
                source_id=args.source,
                source_root=args.source_root,
                limit=args.limit,
            )
        else:
            result = archive_services.scan_source(
                Path(args.archive_root),
                source_id=args.source,
                source_root=args.source_root,
                reviewed_by=args.reviewed_by,
                limit=args.limit,
            )
    except (archive_services.ArchiveServiceError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
        return 0 if result["ok"] else 1

    mode = "dry-run" if result["dry_run"] else "applied"
    state = "passed" if result["ok"] else "blocked"
    print(f"Source scan {mode} {state}.")
    print(f"Archive: {result['source_archive']}")
    print(f"Source: {result['source_id']} ({result['source_type']})")
    print(f"Scan mode: {result['scan_mode']}")
    print(f"Items: {result['item_count']}")
    if result["dry_run"]:
        print(f"Proposed source map path: {result['proposed_source_map_path']}")
        print(f"Proposed receipt path: {result['proposed_receipt_path']}")
    else:
        print(f"Source map path: {result['source_map_path']}")
        print(f"Receipt path: {result['receipt_path']}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_add_source(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("Source registration requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("Source registration requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        if args.dry_run:
            result = archive_services.add_source_dry_run(
                Path(args.archive_root),
                source_id=args.source_id,
                source_type=args.source_type,
                description=args.description,
                root_ref=args.root_ref,
                local_root=args.local_root,
                write_local_profile=args.write_local_profile,
                include=args.include,
                exclude=args.exclude,
                max_items=args.max_items,
                visibility_scope=args.visibility_scope,
                source_visibility=args.source_visibility,
                replace=args.replace,
            )
        else:
            result = archive_services.add_source_binding(
                Path(args.archive_root),
                source_id=args.source_id,
                source_type=args.source_type,
                description=args.description,
                root_ref=args.root_ref,
                local_root=args.local_root,
                write_local_profile=args.write_local_profile,
                include=args.include,
                exclude=args.exclude,
                max_items=args.max_items,
                visibility_scope=args.visibility_scope,
                source_visibility=args.source_visibility,
                replace=args.replace,
                reviewed_by=args.reviewed_by,
            )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
        return 0 if result["ok"] else 1

    mode = "dry-run" if result["dry_run"] else "applied"
    state = "passed" if result["ok"] else "blocked"
    print(f"Source registration {mode} {state}.")
    print(f"Archive: {result['archive_id']}")
    print(f"Source: {result['source_id']} ({result['source_type']})")
    print(f"Root ref: {result['source_binding']['root_ref']}")
    if result["dry_run"]:
        print("Would change: " + ", ".join(result["would_change"]))
    else:
        print("Changed: " + ", ".join(result["changed_paths"]))
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_source_mounts(args: argparse.Namespace) -> int:
    try:
        result = archive_services.source_mount_plan(Path(args.archive_root))
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Source mount plan for {result['archive_id']}.")
        print(f"Strategy: {result['strategy']}")
        for source in result["sources"]:
            if source["needs_host_mount"]:
                print(f"- {source['source_id']}: mount {source['compose_volume_hint']}")
                print(f"  Docker scan: {source['docker_scan_command']}")
            else:
                print(f"- {source['source_id']}: no extra host mount needed")
    return 0


def command_recovery_plan(args: argparse.Namespace) -> int:
    try:
        result = archive_services.recovery_plan(Path(args.archive_root))
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print(f"Recovery plan for {result['archive_id']}.")
        print("Mode: local control-plane recovery; external originals are not copied.")
        print(f"Sources: {result['source_summary']['source_count']} configured")
        print(f"Providers: {result['provider_summary']['binding_count']} configured, manual verification required")
        if result["latest_successful_restore_drill"]:
            latest = result["latest_successful_restore_drill"]
            print(f"Latest restore drill: {latest['receipt_path']}")
        else:
            print("Latest restore drill: none")
    return 0


def command_restore_drill(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if not args.dry_run and not args.approve:
        print("Restore drill requires --dry-run or --approve.", file=sys.stderr)
        return 1
    if args.approve and not args.reviewed_by:
        print("Restore drill requires --reviewed-by when --approve is used.", file=sys.stderr)
        return 1

    try:
        plan = archive_services.restore_drill_dry_run(Path(args.archive_root), Path(args.target))
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.dry_run or not plan["ok"]:
        print_restore_drill_result(plan, args.format)
        return 0 if plan["ok"] else 1

    archive_root = Path(args.archive_root).resolve()
    target = Path(args.target).expanduser().resolve()
    reviewed_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    timestamp_slug = reviewed_at.replace(":", "").replace("+", "_").replace("-", "").replace("T", "_")
    receipt_relative = f"{archive_services.RESTORE_DRILL_RECEIPTS_DIR}/{timestamp_slug}.restore-drill.json"

    try:
        changed_archive_paths = archive_services.copy_restore_drill_tree(archive_root, target)
        diagnostics = Doctor(target).run()
        errors = [item for item in diagnostics if item.severity == "ERROR"]
        warnings = [item for item in diagnostics if item.severity == "WARN"]
        index_result = archive_services.index_archive(target)
        search_result = archive_services.search_archive(target, "archive", limit=3)
    except (archive_services.ArchiveServiceError, OSError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    validation_ok = not errors and not warnings
    result_status = "passed" if validation_ok else "failed"
    blockers = [] if validation_ok else [f"Restored copy doctor reported {len(errors)} error(s), {len(warnings)} warning(s)."]
    receipt = dict(plan["receipt_preview"])
    receipt.update(
        {
            "receipt_id": f"receipt:restore-drill:{archive_services.safe_slug(plan['archive_id'])}:{timestamp_slug}",
            "dry_run": False,
            "timestamp": reviewed_at,
            "reviewed_by": args.reviewed_by,
            "reviewed_at": reviewed_at,
            "validation": {
                "doctor_strict": {
                    "ok": validation_ok,
                    "errors": len(errors),
                    "warnings": len(warnings),
                    "diagnostics": [item.as_dict() for item in diagnostics],
                },
                "index": index_result,
                "search_smoke": {
                    "ok": True,
                    "query": search_result["query"],
                    "count": search_result["count"],
                },
            },
            "result": {
                "status": result_status,
                "changed_paths": [str(target), receipt_relative],
                "restored_archive_file_count": len(changed_archive_paths),
            },
            "blockers": blockers,
            "warnings": [],
        }
    )
    receipt_path = archive_services.archive_internal_path(archive_root, receipt_relative)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    final = {
        "ok": validation_ok,
        "dry_run": False,
        "action": "restore_drill",
        "archive_id": plan["archive_id"],
        "archive_root": str(archive_root),
        "target_root": str(target),
        "receipt_path": receipt_relative,
        "copy_plan": plan["copy_plan"],
        "validation": receipt["validation"],
        "result": receipt["result"],
        "blockers": blockers,
        "warnings": [],
    }
    print_restore_drill_result(final, args.format)
    return 0 if validation_ok else 1


def print_restore_drill_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    mode = "dry-run" if result["dry_run"] else "applied"
    state = "passed" if result["ok"] else "blocked"
    print(f"Restore drill {mode} {state}.")
    print(f"Archive: {result['archive_id']}")
    print(f"Target: {result['target_root']}")
    print(f"Files planned: {result['copy_plan']['included_files']}")
    if result.get("receipt_path"):
        print(f"Receipt: {result['receipt_path']}")
    elif result.get("proposed_receipt_path"):
        print(f"Proposed receipt: {result['proposed_receipt_path']}")
    if result.get("blockers"):
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result.get("warnings"):
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def command_pilot_plan(args: argparse.Namespace) -> int:
    try:
        result = archive_services.real_pilot_plan(
            personal_root=Path(args.personal_root),
            team_root=Path(args.team_root),
            personal_archive_id=args.personal_archive_id,
            personal_principal_id=args.personal_principal_id,
            personal_principal_name=args.personal_principal_name,
            team_archive_id=args.team_archive_id,
            team_principal_id=args.team_principal_id,
            team_principal_name=args.team_principal_name,
            personal_provider_profile=args.personal_provider_profile,
            team_provider_profile=args.team_provider_profile,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
        return 0 if result["ok"] else 1

    state = "passed" if result["ok"] else "blocked"
    print(f"Real archive pilot plan {state}.")
    print("Safety model: metadata-first, no content reads, no live provider API calls.")
    for archive in result["archives"]:
        print(f"- {archive['label']}: {archive['target_root']}")
        print(f"  Archive id: {archive['archive_id']}")
        print(f"  Provider profile: {archive['provider_profile']}")
        print(f"  Suggested sources: {len(archive['suggested_sources'])}")
    if result["blockers"]:
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    return 0 if result["ok"] else 1


def command_preflight(args: argparse.Namespace) -> int:
    try:
        archive_root = Path(args.archive_root)
        diagnostics = [item.as_dict() for item in Doctor(archive_root).run()]
        docker_runtime = docker_runtime_check() if args.check_docker else {"checked": False, "ok": None, "status": "not_checked"}
        result = archive_services.preflight_check(
            archive_root,
            diagnostics=diagnostics,
            peer_archive_root=Path(args.peer_archive) if args.peer_archive else None,
            require_source_maps=args.require_source_maps,
            require_restore_drill=args.require_restore_drill,
            strict=args.strict,
            docker_runtime=docker_runtime,
        )
    except (archive_services.ArchiveServiceError, OSError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
        return 0 if result["ok"] else 1

    state = "passed" if result["ok"] else "blocked"
    print(f"Archive preflight {state}.")
    print(f"Archive: {result['archive_id']}")
    print(f"Doctor: {result['doctor']['errors']} error(s), {result['doctor']['warnings']} warning(s)")
    print(f"Sources: {result['sources']['source_count']} configured")
    print(f"Docker: {result['docker_runtime']['status']}")
    if result["blockers"]:
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")
    print("Next safe actions:")
    for action in result["next_safe_actions"]:
        print(f"- {action}")
    return 0 if result["ok"] else 1


def docker_runtime_check() -> dict[str, Any]:
    override = os.environ.get("AI_ARCHIVE_TEST_DOCKER_STATE")
    if override:
        return docker_runtime_check_from_state(override)

    docker = shutil.which("docker")
    if docker is None:
        return {
            "checked": True,
            "ok": False,
            "status": "missing",
            "message": "Docker CLI is not installed or not on PATH.",
        }

    compose = subprocess.run(
        [docker, "compose", "version"],
        cwd=KIT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    if compose.returncode != 0:
        return {
            "checked": True,
            "ok": False,
            "status": "compose_missing",
            "message": "Docker Compose is not available through docker compose.",
        }

    info = subprocess.run(
        [docker, "info", "--format", "{{.ServerVersion}}"],
        cwd=KIT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    if info.returncode != 0:
        return {
            "checked": True,
            "ok": False,
            "status": "daemon_down",
            "message": "Docker daemon is not reachable. Start Docker Desktop and rerun preflight.",
        }

    config = subprocess.run(
        [docker, "compose", "config"],
        cwd=KIT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    if config.returncode != 0:
        return {
            "checked": True,
            "ok": False,
            "status": "compose_config_failed",
            "message": "docker compose config failed for the Archive Kit runtime.",
        }

    return {
        "checked": True,
        "ok": True,
        "status": "ready",
        "server_version": info.stdout.strip(),
        "message": "Docker CLI, Compose, daemon, and compose config are available.",
    }


def docker_runtime_check_from_state(state: str) -> dict[str, Any]:
    mapping = {
        "missing": ("missing", False, "Docker CLI is not installed or not on PATH."),
        "compose_missing": ("compose_missing", False, "Docker Compose is not available through docker compose."),
        "daemon_down": ("daemon_down", False, "Docker daemon is not reachable. Start Docker Desktop and rerun preflight."),
        "ready": ("ready", True, "Docker CLI, Compose, daemon, and compose config are available."),
    }
    status, ok, message = mapping.get(state, ("unknown", False, f"Unknown Docker test state: {state}."))
    return {"checked": True, "ok": ok, "status": status, "message": message}


def command_onboard(args: argparse.Namespace) -> int:
    require_yaml()
    if args.guided:
        fill_guided_onboarding_args(args)
    missing = [
        name
        for name in ["target_root", "archive_type", "archive_id", "principal_id"]
        if not getattr(args, name, None)
    ]
    if missing:
        print("Missing onboarding argument(s): " + ", ".join(f"--{name.replace('_', '-')}" for name in missing), file=sys.stderr)
        return 2
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1

    principal_kind = args.principal_kind or archive_services.default_principal_kind_for_archive_type(args.archive_type)
    try:
        plan = archive_services.onboarding_plan(
            Path(args.target_root),
            archive_type=args.archive_type,
            archive_id=args.archive_id,
            principal_id=args.principal_id,
            principal_name=args.principal_name,
            principal_kind=principal_kind,
            name=args.name,
            provider_profile=args.provider_profile,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not args.approve:
        print_onboarding_result(plan, args.format)
        return 0 if plan["ok"] else 1
    if not plan["ok"]:
        print_onboarding_result(plan, args.format)
        return 1

    target = Path(args.target_root).resolve()
    if target.exists() and not target.is_dir():
        print(f"Target archive root must be a folder or absent: {target}.", file=sys.stderr)
        return 1
    if target.exists() and any(target.iterdir()):
        print(f"Target archive folder must be empty or absent: {target}.", file=sys.stderr)
        return 1
    template = TEMPLATES_ROOT / args.archive_type
    if not template.is_dir():
        print(f"Unknown archive type: {args.archive_type}", file=sys.stderr)
        return 2

    namespace = argparse.Namespace(
        archive_root=str(target),
        type=args.archive_type,
        archive_id=args.archive_id,
        principal_id=args.principal_id,
        principal_name=args.principal_name,
        principal_kind=principal_kind,
        name=args.name or plan["name"],
        dry_run=False,
    )
    target.mkdir(parents=True, exist_ok=True)
    copy_template(template, target)
    copy_zettel_kasten_layer(target)
    create_recommended_dirs(target)
    write_safe_gitignore(target)
    update_archive_yml(target, namespace)
    update_archive_identity_yml(target, namespace)
    update_provider_bindings_yml(target, namespace)
    update_source_bindings_yml(target, namespace)
    apply_provider_profile(target, args.provider_profile)

    doctor = Doctor(target)
    diagnostics = doctor.run()
    errors = [item for item in diagnostics if item.severity == "ERROR"]
    warnings = [item for item in diagnostics if item.severity == "WARN"]
    result = dict(plan)
    result.update(
        {
            "ok": not errors and not warnings,
            "dry_run": False,
            "created_paths": plan["would_create"],
            "doctor": {
                "strict": True,
                "errors": len(errors),
                "warnings": len(warnings),
                "diagnostics": [item.as_dict() for item in diagnostics],
            },
        }
    )
    print_onboarding_result(result, args.format)
    return 0 if result["ok"] else 1


def fill_guided_onboarding_args(args: argparse.Namespace) -> None:
    def ask(attr: str, prompt: str, default: str | None = None) -> None:
        if getattr(args, attr, None):
            return
        suffix = f" [{default}]" if default else ""
        answer = input(f"{prompt}{suffix}: ").strip()
        setattr(args, attr, answer or default)

    ask("archive_type", "Archive type (personal, family, company)", "personal")
    ask("target_root", "Archive folder to create", "archives/personal")
    ask("principal_id", "Owner/principal id", "person:me")
    ask("archive_id", "Archive id", "archive:personal:me")
    ask("principal_name", "Display name", "Me")


def print_onboarding_result(result: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print_json(result)
        return
    state = "passed" if result["ok"] else "blocked"
    mode = "dry-run" if result["dry_run"] else "applied"
    print(f"Archive onboarding {mode} {state}.")
    print(f"Target: {result['target_root']}")
    print(f"Archive: {result['archive_id']} ({result['archive_type']})")
    print(f"Principal: {result['principal_id']}")
    print(f"Provider profile: {result['provider_profile']}")
    print("Enabled providers: " + ", ".join(result["provider_bindings"]["enabled_providers"]))
    if not result["dry_run"] and "doctor" in result:
        doctor = result["doctor"]
        print(f"Doctor: {doctor['errors']} error(s), {doctor['warnings']} warning(s)")
    if result["blockers"]:
        print("Blockers:")
        for blocker in result["blockers"]:
            print(f"- {blocker}")
    if result["warnings"]:
        print("Warnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")


def command_transfer_ownership(args: argparse.Namespace) -> int:
    if args.dry_run and args.approve:
        print("Use either --dry-run or --approve, not both.", file=sys.stderr)
        return 1
    if args.dry_run:
        try:
            result = archive_services.ownership_transfer_dry_run(
                Path(args.archive_root),
                new_owner=args.new_owner,
                new_owner_kind=args.new_owner_kind,
                new_owner_archive=args.new_owner_archive,
                operators_after=args.operator_after,
                approved_by=args.approved_by,
                subject=args.subject,
                counterparty_id=args.counterparty_id,
                counterparty_fingerprint=args.counterparty_fingerprint,
                reason=args.reason,
            )
        except (archive_services.ArchiveServiceError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if args.format == "json":
            print_json(result)
        else:
            state = "passed" if result["ok"] else "blocked"
            print(f"Ownership transfer dry-run {state}.")
            print(f"Archive: {result['source_archive']}")
            print(f"Previous owner: {result['previous_owner']}")
            print(f"New owner: {result['new_owner']}")
            print(f"Operators after: {', '.join(result['ownership_gate']['operators_after']) or '(none)'}")
            print(f"Trust gate: {result['trust_gate']['status']}")
            print(f"Provider changes: {result['provider_change_plan']['status']}")
            print(f"Proposed receipt path: {result['proposed_receipt_path']}")
            if result["blockers"]:
                print("Blockers:")
                for blocker in result["blockers"]:
                    print(f"- {blocker}")
            if result["warnings"]:
                print("Warnings:")
                for warning in result["warnings"]:
                    print(f"- {warning}")
        return 0 if result["ok"] else 1

    if not args.approve:
        print("Real ownership transfer requires --approve. Use --dry-run to preview.", file=sys.stderr)
        return 1
    if not args.reviewed_by:
        print("Real ownership transfer requires --reviewed-by.", file=sys.stderr)
        return 1

    try:
        result = archive_services.transfer_archive_ownership(
            Path(args.archive_root),
            new_owner=args.new_owner,
            new_owner_kind=args.new_owner_kind,
            new_owner_archive=args.new_owner_archive,
            operators_after=args.operator_after,
            approved_by=args.approved_by,
            subject=args.subject,
            counterparty_id=args.counterparty_id,
            counterparty_fingerprint=args.counterparty_fingerprint,
            reason=args.reason,
            reviewed_by=args.reviewed_by,
        )
    except (archive_services.ArchiveServiceError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.format == "json":
        print_json(result)
    else:
        print("Ownership transfer applied.")
        print(f"Archive: {result['source_archive']}")
        print(f"Previous owner: {result['previous_owner']}")
        print(f"New owner: {result['new_owner']}")
        print(f"Reviewed by: {result['reviewed_by']}")
        print(f"Receipt path: {result['receipt_path']}")
        print(f"Provider changes: {result['provider_change_plan']['status']} (manual)")
    return 0


def command_init(args: argparse.Namespace) -> int:
    require_yaml()

    target = Path(args.archive_root).resolve()
    template = TEMPLATES_ROOT / args.type
    if not template.is_dir():
        print(f"Unknown archive type: {args.type}", file=sys.stderr)
        return 2

    if target.exists() and any(target.iterdir()):
        print(f"Target must be empty or absent: {target}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"Would initialize {args.type} archive at {target}")
        return 0

    target.mkdir(parents=True, exist_ok=True)
    copy_template(template, target)
    copy_zettel_kasten_layer(target)
    create_recommended_dirs(target)
    write_safe_gitignore(target)
    update_archive_yml(target, args)
    update_archive_identity_yml(target, args)
    update_provider_bindings_yml(target, args)
    update_source_bindings_yml(target, args)

    print(f"Initialized {args.type} archive at {target}")
    print(f"archive_id: {args.archive_id}")
    print(f"principal_id: {args.principal_id}")
    return 0


def copy_template(template: Path, target: Path) -> None:
    for child in template.iterdir():
        destination = target / child.name
        if child.is_dir():
            shutil.copytree(child, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(child, destination)


def copy_zettel_kasten_layer(target: Path) -> None:
    destination = target / "zettel-kasten"
    shutil.copytree(KIT_ZETTEL_KASTEN_ROOT, destination, dirs_exist_ok=True)


def create_recommended_dirs(target: Path) -> None:
    for relative in [
        "inbox",
        "zettels",
        "views",
        "source-maps",
        "objects/manifests",
        "db",
        "workbench",
        "receipts",
        "receipts/import",
        "receipts/lineage",
        "receipts/mint",
        "receipts/mint/drafts",
        "receipts/recovery",
        "receipts/share",
        "receipts/sources",
    ]:
        (target / relative).mkdir(parents=True, exist_ok=True)


def write_safe_gitignore(target: Path) -> None:
    gitignore = target / ".gitignore"
    if gitignore.exists():
        return
    gitignore.write_text(
        "\n".join(
            [
                "# AI Archive Kit safe defaults",
                ".env",
                ".env.*",
                "!.env.example",
                "*.key",
                "*.pem",
                "*.p12",
                "*.pfx",
                "*.kdbx",
                "secrets/",
                "profiles/local/",
                "profiles/*.local.yml",
                "keyrings/local/",
                "keyrings/*.local.yml",
                ".archive-local/",
                "rclone.conf",
                "credentials.json",
                "token.json",
                "tmp/",
                "",
                "# Generated archive search indexes",
                "**/db/archive-index.sqlite",
                "",
            ]
        ),
        encoding="utf-8",
    )


def update_archive_yml(target: Path, args: argparse.Namespace) -> None:
    path = target / "archive.yml"
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"archive.yml is not a YAML object: {path}")

    data["archive_id"] = args.archive_id
    data["name"] = args.name or f"{args.type.title()} Archive"
    data["type"] = args.type
    data["principal"] = {
        "principal_id": args.principal_id,
        "display_name": args.principal_name or args.principal_id,
        "kind": args.principal_kind,
    }
    data.setdefault("root_policy", {})
    data["root_policy"].setdefault("canonical_zettels", "zettels/")
    data["root_policy"].setdefault("ai_inbox", "inbox/")
    data["root_policy"].setdefault("views", "views/")
    data["root_policy"].setdefault("object_manifest", "objects/manifests/files.jsonl")
    data["root_policy"].setdefault("source_bindings", "source-bindings.yml")
    data["root_policy"].setdefault("source_maps", "source-maps/")
    data["root_policy"].setdefault("sqlite_schema", "db/schema.sql")
    data.setdefault("ai_write_policy", {})
    data["ai_write_policy"]["default"] = "inbox_only"
    data["ai_write_policy"]["canonical_requires"] = "human_minting"
    data.setdefault("storage_policy", {})
    data["storage_policy"]["object_identity"] = "sha256"
    data["storage_policy"]["provider_urls_in_zettels"] = "forbidden"
    data["storage_policy"]["locations_live_in_manifest"] = True
    data.setdefault("mounted_archives", [])

    path.write_text(dump_yaml(data), encoding="utf-8")


def update_archive_identity_yml(target: Path, args: argparse.Namespace) -> None:
    path = target / "archive-identity.yml"
    data: dict[str, Any] = {}
    if path.is_file():
        loaded = load_yaml(path.read_text(encoding="utf-8"))
        data = loaded if isinstance(loaded, dict) else {}

    identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    identity["archive_id"] = args.archive_id
    identity.setdefault("identity_id", f"identity:{args.archive_id}")
    identity["scope"] = args.type
    identity["principal_id"] = args.principal_id
    identity.setdefault("display_name", args.principal_name or args.principal_id)
    identity.setdefault("public_keys", [])
    data["identity"] = identity

    ownership = data.get("ownership") if isinstance(data.get("ownership"), dict) else {}
    ownership["owner_id"] = args.principal_id
    ownership["owner_kind"] = args.principal_kind
    ownership["owner_display_name"] = args.principal_name or args.principal_id
    ownership["owner_archive_id"] = args.archive_id
    default_operator = {
        "operator_id": args.principal_id,
        "role": "owner_operator",
        "permissions": ["capture", "curate", "approve", "transfer_request"],
    }
    if args.type == "personal" or not isinstance(ownership.get("operators"), list) or not ownership.get("operators"):
        ownership["operators"] = [default_operator]
    ownership.setdefault("subjects", [])
    ownership.setdefault(
        "transfer_policy",
        {
            "ownership_transfer_allowed": True,
            "requires_human_approval": True,
            "requires_receipt": True,
            "receipt_action": "transfer_archive_ownership",
            "default_transfer_target": None,
        },
    )
    data["ownership"] = ownership
    data.setdefault("trusted_counterparties", [])
    data.setdefault(
        "lineage",
        {
            "parents": [],
            "children": [],
            "forked_from": None,
            "merged_from": [],
            "exited_from": None,
        },
    )

    path.write_text(dump_yaml(data), encoding="utf-8")


def update_provider_bindings_yml(target: Path, args: argparse.Namespace) -> None:
    path = target / "provider-bindings.yml"
    if not path.is_file():
        return
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"provider-bindings.yml is not a YAML object: {path}")
    data["archive_id"] = args.archive_id
    path.write_text(dump_yaml(data), encoding="utf-8")


def update_source_bindings_yml(target: Path, args: argparse.Namespace) -> None:
    path = target / "source-bindings.yml"
    if not path.is_file():
        return
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"source-bindings.yml is not a YAML object: {path}")
    data["archive_id"] = args.archive_id
    path.write_text(dump_yaml(data), encoding="utf-8")


def apply_provider_profile(target: Path, provider_profile: str | None) -> None:
    path = target / "provider-bindings.yml"
    if not path.is_file():
        return
    data = load_yaml(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"provider-bindings.yml is not a YAML object: {path}")
    enabled = set(archive_services.provider_profile_enabled_providers(provider_profile))
    bindings = data.get("bindings") if isinstance(data.get("bindings"), list) else []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        binding["enabled"] = binding.get("provider") in enabled
    data["onboarding"] = {
        "provider_profile": provider_profile or "local_only",
        "secret_values_allowed": False,
        "external_provider_mutation": "manual_required",
    }
    path.write_text(dump_yaml(data), encoding="utf-8")


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def print_diagnostics(diagnostics: list[Diagnostic], errors: list[Diagnostic], warnings: list[Diagnostic]) -> None:
    for item in diagnostics:
        location = f" [{item.path}]" if item.path else ""
        print(f"{item.severity}: {item.code}: {item.message}{location}")
    print(f"\nSummary: {len(errors)} error(s), {len(warnings)} warning(s).")


def parse_key_value_pairs(items: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Facet must be KEY=VALUE: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Facet key must not be empty: {item}")
        result[key] = value.strip()
    return result


def read_body_arg(args: argparse.Namespace) -> str:
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    return args.body


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="archive",
        description="Minimal CLI for AI Archive Kit / zettel-kasten archives.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    doctor = subcommands.add_parser("doctor", help="Inspect an archive for structural and policy issues.")
    doctor.add_argument("archive_root", nargs="?", default=".", help="Archive root to inspect.")
    doctor.add_argument("--strict", action="store_true", help="Treat warnings as a failing result.")
    doctor.add_argument("--json", action="store_true", help="Print diagnostics as JSON.")
    doctor.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    doctor.set_defaults(func=command_doctor)

    validate = subcommands.add_parser("validate", help="Run strict archive validation.")
    validate.add_argument("archive_root", nargs="?", default=".", help="Archive root to validate.")
    validate.add_argument("--allow-warnings", action="store_true", help="Do not fail when only warnings are present.")
    validate.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    validate.set_defaults(func=command_validate)

    list_zettels = subcommands.add_parser("list-zettels", help="List draft and/or canonical zettels.")
    list_zettels.add_argument("archive_root", help="Archive root to inspect.")
    list_zettels.add_argument("--status", choices=["all", "draft", "canonical"], default="canonical", help="Zettel status to list.")
    list_zettels.add_argument("--limit", type=int, default=100, help="Maximum number of zettels to return.")
    list_zettels.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    list_zettels.set_defaults(func=command_list_zettels)

    read_zettel = subcommands.add_parser("read-zettel", help="Read one zettel by id or archive-relative path.")
    read_zettel.add_argument("archive_root", help="Archive root to inspect.")
    read_target = read_zettel.add_mutually_exclusive_group(required=True)
    read_target.add_argument("--zettel-id", help="Zettel id to read.")
    read_target.add_argument("--path", help="Archive-relative zettel path to read.")
    read_zettel.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    read_zettel.set_defaults(func=command_read_zettel)

    create_draft = subcommands.add_parser("create-draft", help="Create a draft zettel in inbox/.")
    create_draft.add_argument("archive_root", help="Archive root to write to.")
    create_draft.add_argument("--title", required=True, help="Draft title.")
    body = create_draft.add_mutually_exclusive_group(required=True)
    body.add_argument("--body", help="Draft body text.")
    body.add_argument("--body-file", help="Path to a UTF-8 text file containing the draft body.")
    create_draft.add_argument("--archive-id", help="Archive id. Defaults to archive.yml archive_id.")
    create_draft.add_argument("--kind", default="fleeting_capture", help="Zettel kind.")
    create_draft.add_argument("--facet", action="append", help="Facet in KEY=VALUE form. May be repeated.")
    create_draft.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    create_draft.set_defaults(func=command_create_draft)

    promote = subcommands.add_parser("promote", help="Check whether a draft zettel can be promoted.")
    promote.add_argument("archive_root", help="Archive root to inspect.")
    promote_target = promote.add_mutually_exclusive_group(required=True)
    promote_target.add_argument("--zettel-id", help="Draft zettel id to check.")
    promote_target.add_argument("--path", help="Archive-relative draft path to check.")
    promote.add_argument("--dry-run", action="store_true", help="Preview promotion without writing canonical memory.")
    promote.add_argument("--approve", action="store_true", help="Actually write canonical memory after dry-run gates pass.")
    promote.add_argument("--reviewed-by", help="Reviewer id required for real promotion, e.g. person:me.")
    promote.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Allow real promotion when dry-run warnings are present.",
    )
    promote.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    promote.set_defaults(func=command_promote)

    mint = subcommands.add_parser("mint-zettel", help="Mint an inbox draft zet into canonical private archive memory.")
    mint.add_argument("archive_root", help="Archive root to inspect.")
    mint_target = mint.add_mutually_exclusive_group(required=True)
    mint_target.add_argument("--zettel-id", help="Draft zettel id to mint.")
    mint_target.add_argument("--path", help="Archive-relative draft path to mint.")
    mint.add_argument("--dry-run", action="store_true", help="Preview minting without writing canonical memory.")
    mint.add_argument("--approve", action="store_true", help="Actually mint after dry-run gates pass.")
    mint.add_argument("--reviewed-by", help="Reviewer id required for real minting, e.g. person:me.")
    mint.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Allow real minting when dry-run warnings are present.",
    )
    mint.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    mint.set_defaults(func=command_mint_zettel)

    index = subcommands.add_parser("index", help="Build a generated local SQLite search index.")
    index.add_argument("archive_root", help="Archive root to index.")
    index.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    index.set_defaults(func=command_index)

    search = subcommands.add_parser("search", help="Search the generated local SQLite search index.")
    search.add_argument("archive_root", help="Archive root to search.")
    search.add_argument("query", help="Search query.")
    search.add_argument("--limit", type=int, default=20, help="Maximum number of results to return.")
    search.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    search.set_defaults(func=command_search)

    pack = subcommands.add_parser("pack", help="Create a portable workpack from a saved view.")
    pack.add_argument("archive_root", help="Source archive root.")
    pack.add_argument("--view", required=True, help="View id to pack.")
    pack.add_argument("--purpose", required=True, help="Reason this workpack exists.")
    pack.add_argument(
        "--mode",
        choices=["reference", "copy", "mount", "derive", "handover", "return"],
        default="reference",
        help="Workpack mode.",
    )
    pack.add_argument("--target-archive", help="Optional target archive id.")
    pack.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    pack.set_defaults(func=command_pack)

    import_workpack = subcommands.add_parser("import", help="Preview a workpack import without mutating the target archive.")
    import_workpack.add_argument("archive_root", help="Target archive root.")
    import_workpack.add_argument("workpack", help="Workpack directory or package.yml file.")
    import_workpack.add_argument("--dry-run", action="store_true", help="Preview import without writing target archive files.")
    import_workpack.add_argument("--counterparty-id", help="Expected sender identity/archive/principal id for trust-gated workpacks.")
    import_workpack.add_argument("--counterparty-fingerprint", help="Expected sender public key fingerprint for trust-gated workpacks.")
    import_workpack.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    import_workpack.set_defaults(func=command_import_workpack)

    import_external = subcommands.add_parser("import-external", help="Import Notion or Google Drive exports as inbox drafts.")
    import_external.add_argument("archive_root", help="Target archive root.")
    import_external.add_argument("--source", required=True, choices=sorted(archive_services.EXTERNAL_IMPORT_SOURCES), help="External source system.")
    import_external.add_argument("--export", required=True, help="Export folder or JSON/YAML manifest to import.")
    import_external.add_argument("--dry-run", action="store_true", help="Preview import without writing archive files.")
    import_external.add_argument("--approve", action="store_true", help="Write imported items to inbox and record a receipt.")
    import_external.add_argument("--reviewed-by", help="Reviewer id required for approved import.")
    import_external.add_argument("--limit", type=int, default=200, help="Maximum number of external items to import.")
    import_external.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    import_external.set_defaults(func=command_import_external)

    share = subcommands.add_parser("share", help="Dry-run a governed archive share from a saved view.")
    share.add_argument("archive_root", help="Source archive root.")
    share.add_argument("--view", required=True, help="View id to share.")
    share.add_argument("--target-archive", required=True, help="Target archive id.")
    share.add_argument("--counterparty-id", help="Expected counterparty identity/archive/principal id.")
    share.add_argument("--counterparty-fingerprint", help="Expected counterparty public key fingerprint.")
    share.add_argument("--allow-sensitive", action="store_true", help="Allow sensitive categories in the dry-run manifest.")
    share.add_argument("--dry-run", action="store_true", help="Preview sharing without writing or sending files.")
    share.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    share.set_defaults(func=command_share)

    providers = subcommands.add_parser("providers", help="Inspect external provider bindings and manual change plans.")
    providers.add_argument("archive_root", help="Archive root to inspect.")
    providers.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    providers.set_defaults(func=command_providers)

    sources = subcommands.add_parser("sources", help="Inspect source bindings and source map status.")
    sources.add_argument("archive_root", help="Archive root to inspect.")
    sources.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    sources.set_defaults(func=command_sources)

    scan_source = subcommands.add_parser("scan-source", help="Metadata-only scan of a registered source into a source map.")
    scan_source.add_argument("archive_root", help="Archive root to inspect.")
    scan_source.add_argument("--source", required=True, help="source_id from source-bindings.yml.")
    scan_source.add_argument(
        "--source-root",
        help="Real local/export folder or manifest path for this run. It is used at runtime and not written to source maps.",
    )
    scan_source.add_argument("--dry-run", action="store_true", help="Preview source scan without writing archive files.")
    scan_source.add_argument("--approve", action="store_true", help="Write source map and receipt after dry-run gates pass.")
    scan_source.add_argument("--reviewed-by", help="Reviewer id required for approved source scan.")
    scan_source.add_argument("--limit", type=int, default=2000, help="Maximum metadata items to map.")
    scan_source.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    scan_source.set_defaults(func=command_scan_source)

    add_source = subcommands.add_parser("add-source", help="Register a source without hand-editing source-bindings.yml.")
    add_source.add_argument("archive_root", help="Archive root to update.")
    add_source.add_argument("--source-id", required=True, help="Stable source id, e.g. local:documents or ssd:archive-drive.")
    add_source.add_argument(
        "--type",
        dest="source_type",
        required=True,
        choices=sorted(archive_services.SOURCE_TYPES),
        help="Source type.",
    )
    add_source.add_argument("--description", help="Human-readable source description.")
    add_source.add_argument(
        "--root-ref",
        help="Safe root ref to store, e.g. ARCHIVE_SOURCE_DOCUMENTS_ROOT or archive:objects/manifests/files.jsonl.",
    )
    add_source.add_argument(
        "--local-root",
        help="Actual local path used only for ignored local profile guidance when --write-local-profile is set.",
    )
    add_source.add_argument(
        "--write-local-profile",
        action="store_true",
        help="Write the actual local root to ignored profiles/local/source-roots.local.yml.",
    )
    add_source.add_argument("--include", action="append", help="Include glob. Repeatable. Defaults to **/*.")
    add_source.add_argument("--exclude", action="append", help="Exclude glob. Repeatable.")
    add_source.add_argument("--max-items", type=int, default=2000, help="Maximum metadata items for default scans.")
    add_source.add_argument("--visibility-scope", default="private", help="Visibility scope recorded for mapped items.")
    add_source.add_argument("--source-visibility", default="private", help="Source visibility recorded for mapped items.")
    add_source.add_argument("--replace", action="store_true", help="Replace an existing source with the same source id.")
    add_source.add_argument("--dry-run", action="store_true", help="Preview source registration without writing files.")
    add_source.add_argument("--approve", action="store_true", help="Write source-bindings.yml after review.")
    add_source.add_argument("--reviewed-by", help="Reviewer id required for approved registration.")
    add_source.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    add_source.set_defaults(func=command_add_source)

    source_mounts = subcommands.add_parser("source-mounts", help="Show host-native and Docker mount guidance for registered sources.")
    source_mounts.add_argument("archive_root", help="Archive root to inspect.")
    source_mounts.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    source_mounts.set_defaults(func=command_source_mounts)

    recovery_plan = subcommands.add_parser("recovery-plan", help="Show local backup and restore readiness without writing files.")
    recovery_plan.add_argument("archive_root", help="Archive root to inspect.")
    recovery_plan.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    recovery_plan.set_defaults(func=command_recovery_plan)

    restore_drill = subcommands.add_parser("restore-drill", help="Plan or run a local restore drill for the archive control plane.")
    restore_drill.add_argument("archive_root", help="Archive root to copy from.")
    restore_drill.add_argument("--target", required=True, help="Empty or absent folder where the restored copy will be created.")
    restore_drill.add_argument("--dry-run", action="store_true", help="Preview restore drill without creating the target folder.")
    restore_drill.add_argument("--approve", action="store_true", help="Copy the archive control plane and write a restore drill receipt.")
    restore_drill.add_argument("--reviewed-by", help="Reviewer id required for approved restore drill.")
    restore_drill.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    restore_drill.set_defaults(func=command_restore_drill)

    pilot_plan = subcommands.add_parser("pilot-plan", help="Plan a safe first real personal/team archive pilot without writing files.")
    pilot_plan.add_argument("--personal-root", required=True, help="Target folder for the private personal life archive.")
    pilot_plan.add_argument("--team-root", required=True, help="Target folder for the team/company archive.")
    pilot_plan.add_argument("--personal-archive-id", default="archive:personal:life", help="Personal archive id.")
    pilot_plan.add_argument("--personal-principal-id", default="person:me", help="Personal owner/principal id.")
    pilot_plan.add_argument("--personal-principal-name", help="Personal owner display name.")
    pilot_plan.add_argument("--team-archive-id", default="archive:company:founding-team", help="Team/company archive id.")
    pilot_plan.add_argument("--team-principal-id", default="team:founding-team", help="Team owner/principal id.")
    pilot_plan.add_argument("--team-principal-name", help="Team display name.")
    pilot_plan.add_argument(
        "--personal-provider-profile",
        choices=sorted(archive_services.ONBOARDING_PROVIDER_PROFILES),
        default="object_storage_planned",
        help="Provider planning profile for the personal archive.",
    )
    pilot_plan.add_argument(
        "--team-provider-profile",
        choices=sorted(archive_services.ONBOARDING_PROVIDER_PROFILES),
        default="full_provider_plan",
        help="Provider planning profile for the team/company archive.",
    )
    pilot_plan.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    pilot_plan.set_defaults(func=command_pilot_plan)

    preflight = subcommands.add_parser("preflight", help="Check an archive before connecting real personal or team data.")
    preflight.add_argument("archive_root", help="Archive root to inspect.")
    preflight.add_argument("--peer-archive", help="Optional peer archive root to check personal/team separation.")
    preflight.add_argument("--require-source-maps", action="store_true", help="Block if any enabled source has not been mapped yet.")
    preflight.add_argument("--require-restore-drill", action="store_true", help="Block if no successful restore drill receipt is present.")
    preflight.add_argument("--check-docker", action="store_true", help="Check Docker CLI, Compose, daemon, and compose config.")
    preflight.add_argument("--strict", action="store_true", help="Treat warnings as a failing preflight.")
    preflight.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    preflight.set_defaults(func=command_preflight)

    onboard = subcommands.add_parser("onboard", help="Plan or apply beginner-friendly archive onboarding.")
    onboard.add_argument("--target-root", help="Archive folder to create, e.g. /archives/personal or .\\archives\\personal.")
    onboard.add_argument("--type", dest="archive_type", choices=["personal", "company", "family"], help="Archive template type.")
    onboard.add_argument("--archive-id", help="Archive id, e.g. archive:personal:me.")
    onboard.add_argument("--principal-id", help="Owner/principal id, e.g. person:me.")
    onboard.add_argument("--principal-name", help="Human-readable owner/principal display name.")
    onboard.add_argument(
        "--principal-kind",
        choices=["person", "family", "household", "child", "company", "team", "project", "role", "client"],
        help="Principal kind. Defaults from --type.",
    )
    onboard.add_argument("--name", help="Human-readable archive name.")
    onboard.add_argument(
        "--provider-profile",
        choices=sorted(archive_services.ONBOARDING_PROVIDER_PROFILES),
        default="local_only",
        help="External provider planning profile.",
    )
    onboard.add_argument("--guided", action="store_true", help="Ask beginner-friendly questions for missing values.")
    onboard.add_argument("--dry-run", action="store_true", help="Preview onboarding without writing files.")
    onboard.add_argument("--approve", action="store_true", help="Create the archive after the onboarding plan passes.")
    onboard.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    onboard.set_defaults(func=command_onboard)

    transfer_ownership = subcommands.add_parser(
        "transfer-ownership",
        help="Preview or apply an archive ownership transfer.",
    )
    transfer_ownership.add_argument("archive_root", help="Archive root to inspect.")
    transfer_ownership.add_argument("--new-owner", required=True, help="New owner id, e.g. person:child or company:spinout.")
    transfer_ownership.add_argument(
        "--new-owner-kind",
        choices=sorted(archive_services.OWNER_KINDS),
        help="New owner kind. Defaults to the id prefix when possible.",
    )
    transfer_ownership.add_argument("--new-owner-archive", help="Optional archive id for the new owner.")
    transfer_ownership.add_argument(
        "--operator-after",
        action="append",
        help="Operator id after transfer. Repeat for each post-transfer operator.",
    )
    transfer_ownership.add_argument(
        "--approved-by",
        action="append",
        help="Current owner/operator id that approved the proposed transfer. Repeat as needed.",
    )
    transfer_ownership.add_argument("--subject", help="Subject of the transfer, e.g. person:child.")
    transfer_ownership.add_argument("--counterparty-id", help="Trusted counterparty id to verify. Defaults to the new owner.")
    transfer_ownership.add_argument("--counterparty-fingerprint", help="Expected public key fingerprint for the new owner.")
    transfer_ownership.add_argument("--reason", help="Human-readable reason for the proposed transfer.")
    transfer_ownership.add_argument("--dry-run", action="store_true", help="Preview transfer without writing archive files.")
    transfer_ownership.add_argument("--approve", action="store_true", help="Apply the transfer after dry-run gates pass.")
    transfer_ownership.add_argument("--reviewed-by", help="Reviewer id required for real transfer, e.g. person:me.")
    transfer_ownership.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    transfer_ownership.set_defaults(func=command_transfer_ownership)

    init = subcommands.add_parser("init", help="Initialize a new archive from a template.")
    init.add_argument("archive_root", help="Target archive root. Must be absent or empty.")
    init.add_argument("--type", choices=["personal", "company", "family"], required=True, help="Archive template type.")
    init.add_argument("--archive-id", required=True, help="Archive id, e.g. archive:personal:me.")
    init.add_argument("--principal-id", required=True, help="Principal id, e.g. person:me.")
    init.add_argument("--principal-name", help="Human-readable principal display name.")
    init.add_argument(
        "--principal-kind",
        default="person",
        choices=["person", "family", "household", "child", "company", "team", "project", "role", "client"],
        help="Principal kind.",
    )
    init.add_argument("--name", help="Human-readable archive name.")
    init.add_argument("--dry-run", action="store_true", help="Show what would happen without writing files.")
    init.set_defaults(func=command_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
