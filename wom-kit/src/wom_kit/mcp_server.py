"""Minimal stdio MCP server for zettel-kasten archives.

This module intentionally implements a small JSON-RPC stdio subset directly.
It can later be swapped to the official MCP Python SDK without changing the
archive-facing tool functions.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from . import archive_cli
from . import archive_services


SERVER_NAME = "zettel-kasten-archive-mcp"
SUPPORTED_PROTOCOL_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
MCP_ALLOWED_ROOTS_ENV = "AI_ARCHIVE_MCP_ALLOWED_ROOTS"
MCP_ALLOW_LOCAL_PATHS_ENV = "AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS"

JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "wom_profile_list",
        "description": "List read-only WOM profile registry entries before resolving archive runtime context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "registry": {"type": "string", "description": "Path to the WOM profile registry YAML file."},
                "current_profile": {"type": "string"},
                "strict": {"type": "boolean", "default": False},
                "redact_local_paths": {
                    "type": "boolean",
                    "default": True,
                    "description": "Local paths remain redacted unless AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1 is set on the MCP server.",
                },
            },
            "required": ["registry"],
        },
    },
    {
        "name": "wom_profile_resolve",
        "description": "Resolve a requested WOM profile by profile id, label, or alias before runtime-context or draft work.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "registry": {"type": "string", "description": "Path to the WOM profile registry YAML file."},
                "target": {"type": "string", "description": "Requested profile id, label, or alias."},
                "current_profile": {"type": "string"},
                "strict": {"type": "boolean", "default": False},
                "redact_local_paths": {
                    "type": "boolean",
                    "default": True,
                    "description": "Local paths remain redacted unless AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1 is set on the MCP server.",
                },
            },
            "required": ["registry", "target"],
        },
    },
    {
        "name": "wom_profile_wallet_check",
        "description": "Preview wallet-ready WOM profile/node identity metadata. Read-only; never generates keys, signs, registers wallets, or calls blockchain/provider APIs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root used for context."},
                "profile": {"type": "string", "description": "Requested profile id, label, or alias."},
                "registry": {
                    "type": "string",
                    "description": "Optional path to the WOM profile registry YAML file. If omitted, fixed archive-local registry paths are checked.",
                },
                "dry_run": {"type": "boolean", "default": True},
                "redact_local_paths": {
                    "type": "boolean",
                    "default": True,
                    "description": "Local paths remain redacted unless AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1 is set on the MCP server.",
                },
            },
            "required": ["archive_root", "profile"],
        },
    },
    {
        "name": "archive_doctor",
        "description": "Inspect a zettel-kasten archive for structural, metadata, object manifest, and zettel policy issues.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "strict": {"type": "boolean", "default": False},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "archive_runtime_context",
        "description": "Return read-only AI runtime context for a mounted archive before draft, dry-run, or mint approval work.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "expected_archive_id": {"type": "string"},
                "expected_type": {"type": "string", "enum": sorted(archive_services.RUNTIME_CONTEXT_ARCHIVE_TYPES)},
                "strict": {"type": "boolean", "default": False},
                "redact_local_paths": {
                    "type": "boolean",
                    "default": True,
                    "description": "Local paths remain redacted unless AI_ARCHIVE_MCP_ALLOW_LOCAL_PATHS=1 is set on the MCP server.",
                },
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "prompt_boundary_check",
        "description": "Heuristic dry-run prompt-injection boundary check. Read-only; never executes inspected text, calls LLMs, calls providers, approves, mints, or mutates files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "text": {"type": "string", "description": "Inline untrusted text to inspect."},
                "path": {"type": "string", "description": "Archive-relative zet or text path to inspect."},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "github_repository_setup_plan",
        "description": "Plan GitHub repository metadata for a WOM profile. Read-only; never creates repos, remotes, pushes, OAuth, or API calls.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "profile_id": {"type": "string"},
                "profile_slug": {"type": "string"},
                "github_owner": {"type": "string"},
                "github_account_ref": {"type": "string"},
                "repo_name": {"type": "string"},
                "visibility": {
                    "type": "string",
                    "enum": sorted(archive_services.GITHUB_REPOSITORY_ALLOWED_VISIBILITIES),
                    "default": archive_services.GITHUB_REPOSITORY_DEFAULT_VISIBILITY,
                },
                "remote_protocol": {
                    "type": "string",
                    "enum": sorted(archive_services.GITHUB_REPOSITORY_REMOTE_PROTOCOLS),
                    "default": archive_services.GITHUB_REPOSITORY_DEFAULT_REMOTE_PROTOCOL,
                },
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "object_storage_setup_plan",
        "description": "Plan object storage metadata for WOM objets. Read-only; never creates buckets, uploads, syncs, copies, hashes, OAuth, or API calls.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "provider": {"type": "string"},
                "profile_id": {"type": "string"},
                "profile_slug": {"type": "string"},
                "storage_account_ref": {"type": "string"},
                "bucket_name": {"type": "string"},
                "region": {"type": "string"},
                "endpoint_ref": {"type": "string"},
                "objet_prefix": {"type": "string"},
                "visibility": {
                    "type": "string",
                    "enum": sorted(archive_services.OBJECT_STORAGE_ALLOWED_VISIBILITIES),
                    "default": archive_services.OBJECT_STORAGE_DEFAULT_VISIBILITY,
                },
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "source_intake_plan",
        "description": "Plan safe source/objet references before draft creation. Read-only metadata-only dry-run; never reads file bodies, hashes, copies, uploads, imports, OCRs, transcribes, or calls provider APIs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "dry_run": {"type": "boolean", "default": True},
                "local_path": {"type": "string"},
                "source": {"type": "string"},
                "item_id": {"type": "string"},
                "relative_path": {"type": "string"},
                "objet_ref": {"type": "string"},
                "object_id": {"type": "string"},
                "provider": {"type": "string"},
                "provider_object_id": {"type": "string"},
                "provider_kind": {"type": "string"},
                "ai_artifact_ref": {"type": "string"},
                "runtime": {"type": "string", "enum": sorted(archive_services.SOURCE_INTAKE_RUNTIMES)},
                "artifact_kind": {"type": "string"},
                "expected_archive_id": {"type": "string"},
                "expected_type": {"type": "string"},
                "profile_id": {"type": "string"},
                "source_role": {"type": "string", "enum": sorted(archive_services.SOURCE_INTAKE_ROLES)},
                "title": {"type": "string"},
                "mime": {"type": "string"},
                "redact_local_paths": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "archive_init",
        "description": "Initialize a new personal, company, or family archive from safe defaults. Target must be absent or empty.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "archive_type": {"type": "string", "enum": ["personal", "company", "family"]},
                "archive_id": {"type": "string"},
                "principal_id": {"type": "string"},
                "principal_name": {"type": "string"},
                "principal_kind": {
                    "type": "string",
                    "enum": ["person", "family", "household", "child", "company", "team", "project", "role", "client"],
                    "default": "person",
                },
                "name": {"type": "string"},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["archive_root", "archive_type", "archive_id", "principal_id"],
        },
    },
    {
        "name": "archive_onboarding_plan",
        "description": "Plan beginner-friendly Docker-first archive onboarding. This never creates folders or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_root": {"type": "string"},
                "archive_type": {"type": "string", "enum": ["personal", "company", "family"]},
                "archive_id": {"type": "string"},
                "principal_id": {"type": "string"},
                "principal_name": {"type": "string"},
                "principal_kind": {
                    "type": "string",
                    "enum": ["person", "family", "household", "child", "company", "team", "project", "role", "client"],
                },
                "name": {"type": "string"},
                "provider_profile": {
                    "type": "string",
                    "enum": sorted(archive_services.ONBOARDING_PROVIDER_PROFILES),
                    "default": "local_only",
                },
            },
            "required": ["target_root", "archive_type", "archive_id", "principal_id"],
        },
    },
    {
        "name": "real_pilot_plan",
        "description": "Plan a safe first real personal/team archive pilot. This never creates folders, scans files, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "personal_root": {"type": "string"},
                "team_root": {"type": "string"},
                "personal_archive_id": {"type": "string", "default": "archive:personal:life"},
                "personal_principal_id": {"type": "string", "default": "person:me"},
                "personal_principal_name": {"type": "string"},
                "team_archive_id": {"type": "string", "default": "archive:company:founding-team"},
                "team_principal_id": {"type": "string", "default": "team:founding-team"},
                "team_principal_name": {"type": "string"},
                "personal_provider_profile": {
                    "type": "string",
                    "enum": sorted(archive_services.ONBOARDING_PROVIDER_PROFILES),
                    "default": "object_storage_planned",
                },
                "team_provider_profile": {
                    "type": "string",
                    "enum": sorted(archive_services.ONBOARDING_PROVIDER_PROFILES),
                    "default": "full_provider_plan",
                },
            },
            "required": ["personal_root", "team_root"],
        },
    },
    {
        "name": "archive_preflight_check",
        "description": "Check archive safety before connecting real personal or team data. This is read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "peer_archive": {"type": "string"},
                "require_source_maps": {"type": "boolean", "default": False},
                "require_restore_drill": {"type": "boolean", "default": False},
                "strict": {"type": "boolean", "default": False},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "recovery_plan",
        "description": "Show local backup and restore readiness. This never writes files or calls external APIs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"}
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "restore_drill_plan",
        "description": "Plan a local restore drill. This never creates the restore target or writes receipts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "target": {"type": "string"}
            },
            "required": ["archive_root", "target"],
        },
    },
    {
        "name": "external_import_plan",
        "description": "Plan a Notion or Google Drive export import. This never writes archive files or calls external APIs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "source": {"type": "string", "enum": sorted(archive_services.EXTERNAL_IMPORT_SOURCES)},
                "export_path": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
            },
            "required": ["archive_root", "source", "export_path"],
        },
    },
    {
        "name": "list_sources",
        "description": "List registered source bindings and current source map status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "source_scan_plan",
        "description": "Plan a metadata-only source scan. This never writes source maps or receipts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "source": {"type": "string"},
                "source_root": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10000, "default": 2000},
            },
            "required": ["archive_root", "source"],
        },
    },
    {
        "name": "source_registration_plan",
        "description": "Plan source registration. This never writes source-bindings.yml or local profiles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "source_id": {"type": "string"},
                "source_type": {"type": "string", "enum": sorted(archive_services.SOURCE_TYPES)},
                "description": {"type": "string"},
                "root_ref": {"type": "string"},
                "local_root": {"type": "string"},
                "write_local_profile": {"type": "boolean", "default": False},
                "include": {"type": "array", "items": {"type": "string"}},
                "exclude": {"type": "array", "items": {"type": "string"}},
                "max_items": {"type": "integer", "minimum": 1, "maximum": 10000, "default": 2000},
                "visibility_scope": {"type": "string", "default": "private"},
                "source_visibility": {"type": "string", "default": "private"},
                "replace": {"type": "boolean", "default": False},
            },
            "required": ["archive_root", "source_id", "source_type"],
        },
    },
    {
        "name": "source_mount_plan",
        "description": "Show host-native and Docker mount guidance for registered sources. This never changes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "list_zettels",
        "description": "List draft and/or canonical zettels with basic frontmatter metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "status": {"type": "string", "enum": ["all", "draft", "canonical"], "default": "canonical"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "read_zettel",
        "description": "Read one zettel by zettel id or archive-relative path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "zettel_id": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "block_header_check",
        "description": "Dry-run preview of the derived block header for one draft or canonical zet.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "zettel_id": {"type": "string"},
                "path": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "foreign_block_intake_check",
        "description": "Read-only dry-run intake preview for a foreign/shared block or Markdown-compatible zet before any trust/import action.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "path": {"type": "string"},
                "content": {"type": "object"},
                "text": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "foreign_block_trust_check",
        "description": "Read-only dry-run trust/attestation eligibility preview from a foreign-block intake report.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "path": {"type": "string"},
                "intake_report": {"type": "object"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "foreign_block_attestation_packet_check",
        "description": "Read-only dry-run human-review attestation packet preview from a foreign-block trust report.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "path": {"type": "string"},
                "trust_report": {"type": "object"},
                "prospective_attestor": {"type": "string"},
                "review_scope": {"type": "string", "enum": ["human_review", "policy_review", "operator_review"]},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "foreign_block_quarantine_plan",
        "description": "Read-only dry-run quarantine placement plan from a foreign-block attestation packet preview.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "path": {"type": "string"},
                "attestation_packet": {"type": "object"},
                "quarantine_case_id": {"type": "string"},
                "reviewer": {"type": "string"},
                "quarantine_policy": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_QUARANTINE_POLICIES),
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "quarantine_foreign_block_check",
        "description": "Read-only dry-run check for an approved CLI-only foreign block quarantine write.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "path": {"type": "string"},
                "quarantine_plan": {"type": "object"},
                "expected_case_id": {"type": "string"},
                "reviewed_by": {"type": "string"},
                "review_note": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "foreign_block_quarantine_review_index",
        "description": "Read-only inventory and consistency check for existing foreign block quarantine cases.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "case_id": {"type": "string"},
                "status": {"type": "string", "enum": ["written_untrusted", "all"], "default": "written_untrusted"},
                "include_receipts": {"type": "boolean", "default": False},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "foreign_block_quarantine_decision_check",
        "description": "Read-only decision-path preview for one existing foreign block quarantine case.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "case_id": {"type": "string"},
                "decision_intent": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_QUARANTINE_DECISION_INTENTS),
                    "default": "auto",
                },
                "reviewer": {"type": "string"},
                "review_note": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "case_id"],
        },
    },
    {
        "name": "record_quarantine_decision_check",
        "description": "Read-only dry-run check for a CLI-only foreign block quarantine decision record write.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "path": {"type": "string"},
                "decision_preview": {"type": "object"},
                "expected_case_id": {"type": "string"},
                "expected_decision": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_QUARANTINE_DECISIONS),
                },
                "reviewed_by": {"type": "string"},
                "review_note": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "foreign_block_quarantine_decision_review_index",
        "description": "Read-only inventory and consistency check for recorded foreign block quarantine decisions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "case_id": {"type": "string"},
                "decision": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_QUARANTINE_DECISIONS | {"all"}),
                    "default": "all",
                },
                "include_receipts": {"type": "boolean", "default": False},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "foreign_block_decision_outcome_plan",
        "description": "Read-only outcome planner for one recorded foreign block quarantine decision.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "case_id": {"type": "string"},
                "expected_decision": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_QUARANTINE_DECISIONS),
                },
                "reviewer": {"type": "string"},
                "review_note": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "case_id"],
        },
    },
    {
        "name": "create_draft_zettel",
        "description": "Create an AI draft zettel in inbox/. This does not mint to canonical memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "title": {"type": "string"},
                "body": {"type": "string"},
                "archive_id": {"type": "string"},
                "kind": {"type": "string", "default": "fleeting_capture"},
                "facets": {"type": "object"},
                "visibility": {"type": "object"},
                "dry_run": {"type": "boolean", "default": False},
                "expected_archive_id": {"type": "string"},
                "expected_type": {"type": "string", "enum": sorted(archive_services.RUNTIME_CONTEXT_ARCHIVE_TYPES)},
                "profile_context": {"type": "object"},
                "creation_mode": {"type": "string", "enum": sorted(archive_services.DRAFT_CREATION_MODES)},
                "created_by": {"type": "string"},
                "source": {"type": "string"},
                "assisted_by": {"type": "array", "items": {"type": "string"}},
                "supervised_by": {"type": "array", "items": {"type": "string"}},
                "derived_from": {"type": "array", "items": {"type": "string"}},
                "source_refs": {"type": "array", "items": {"type": "object"}},
                "source_intake_plan": {"type": "object"},
                "prompt_boundary_report": {"type": "object"},
                "local_ai_sessions": {"type": "array", "items": {"type": "object"}},
                "draft_id": {"type": "string"},
                "created_at": {"type": "string"},
                "expected_body_sha256": {"type": "string"},
                "draft_approved_by": {"type": "string"},
            },
            "required": ["archive_root", "title", "body"],
        },
    },
    {
        "name": "list_views",
        "description": "List saved AI context views from views/*.yml.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "archive_index",
        "description": "Build a generated local SQLite search index at db/archive-index.sqlite.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "archive_search",
        "description": "Search zettels, object manifest entries, and views through the generated local SQLite index.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            "required": ["archive_root", "query"],
        },
    },
    {
        "name": "promotion_check",
        "description": "Dry-run check whether an inbox draft zettel can be promoted. This never writes canonical memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "zettel_id": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "mint_zettel_check",
        "description": "Dry-run check whether an inbox draft zet can be minted. This never writes canonical memory, receipts, or snapshots.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "zettel_id": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "share_check",
        "description": "Dry-run check whether a saved view can be shared with a trusted counterparty. This never writes or sends data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "view": {"type": "string"},
                "target_archive": {"type": "string"},
                "counterparty_id": {"type": "string"},
                "counterparty_fingerprint": {"type": "string"},
                "allow_sensitive": {"type": "boolean", "default": False},
            },
            "required": ["archive_root", "view", "target_archive"],
        },
    },
    {
        "name": "delegate_zet_check",
        "description": "Dry-run check whether zets from a saved view can be delegated. This never writes receipts or sends data.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "view": {"type": "string"},
                "target_archive": {"type": "string"},
                "target_policy": {"type": "string", "enum": sorted(archive_services.DELEGATE_TARGET_POLICIES)},
                "counterparty_id": {"type": "string"},
                "counterparty_fingerprint": {"type": "string"},
                "allow_sensitive": {"type": "boolean", "default": False},
            },
            "required": ["archive_root", "view"],
        },
    },
    {
        "name": "attest_zet_check",
        "description": "Dry-run check whether a delegated foreign zet receipt can be attested. This never writes receipts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "delegate_receipt": {"type": "string"},
                "counterparty_id": {"type": "string"},
                "counterparty_fingerprint": {"type": "string"},
            },
            "required": ["archive_root", "delegate_receipt"],
        },
    },
    {
        "name": "anchor_zet_check",
        "description": "Dry-run check whether an attested foreign zet can be anchored into local meaning. This never writes metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "attestation_receipt": {"type": "string"},
            },
            "required": ["archive_root", "attestation_receipt"],
        },
    },
    {
        "name": "ownership_transfer_check",
        "description": "Dry-run check whether archive ownership can be transferred. This never changes owners or writes receipts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "new_owner": {"type": "string"},
                "new_owner_kind": {"type": "string", "enum": sorted(archive_services.OWNER_KINDS)},
                "new_owner_archive": {"type": "string"},
                "operators_after": {"type": "array", "items": {"type": "string"}},
                "approved_by": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "counterparty_id": {"type": "string"},
                "counterparty_fingerprint": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["archive_root", "new_owner"],
        },
    },
]


def main() -> int:
    server = JsonRpcMcpServer()
    return server.serve(sys.stdin, sys.stdout)


class JsonRpcMcpServer:
    def serve(self, stdin: Any, stdout: Any) -> int:
        for raw_line in stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                self._write(stdout, error_response(None, JSONRPC_PARSE_ERROR, f"Parse error: {exc}"))
                continue

            response = self.handle_message(message)
            if response is not None:
                self._write(stdout, response)
        return 0

    def handle_message(self, message: Any) -> dict[str, Any] | None:
        if not isinstance(message, dict):
            return error_response(None, JSONRPC_INVALID_REQUEST, "Request must be a JSON object.")

        request_id = message.get("id")
        method = message.get("method")
        is_notification = "id" not in message

        if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
            if is_notification:
                return None
            return error_response(request_id, JSONRPC_INVALID_REQUEST, "Invalid JSON-RPC request.")

        if is_notification:
            self._handle_notification(method)
            return None

        try:
            result = self._dispatch_request(method, message.get("params") or {})
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except ToolError as exc:
            return {"jsonrpc": "2.0", "id": request_id, "result": tool_error_result(str(exc))}
        except InvalidParamsError as exc:
            return error_response(request_id, JSONRPC_INVALID_PARAMS, str(exc))
        except MethodNotFoundError:
            return error_response(request_id, JSONRPC_METHOD_NOT_FOUND, f"Method not found: {method}")
        except Exception as exc:  # pragma: no cover - defensive protocol boundary.
            return error_response(request_id, JSONRPC_INTERNAL_ERROR, f"Internal error: {exc}")

    def _handle_notification(self, method: str) -> None:
        return None

    def _dispatch_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            return handle_initialize(params)
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": TOOL_DEFINITIONS}
        if method == "tools/call":
            return handle_tools_call(params)
        raise MethodNotFoundError()

    def _write(self, stdout: Any, response: dict[str, Any]) -> None:
        stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
        stdout.flush()


def handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    requested = params.get("protocolVersion")
    protocol_version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]
    return {
        "protocolVersion": protocol_version,
        "capabilities": {
            "tools": {"listChanged": False},
        },
        "serverInfo": {
            "name": SERVER_NAME,
            "version": __version__,
        },
    }


def handle_tools_call(params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments") or {}
    if not isinstance(name, str):
        raise InvalidParamsError("tools/call params.name must be a string.")
    if not isinstance(arguments, dict):
        raise InvalidParamsError("tools/call params.arguments must be an object.")

    if name == "wom_profile_list":
        return tool_wom_profile_list(arguments)
    if name == "wom_profile_resolve":
        return tool_wom_profile_resolve(arguments)
    if name == "wom_profile_wallet_check":
        return tool_wom_profile_wallet_check(arguments)
    if name == "archive_doctor":
        return tool_archive_doctor(arguments)
    if name == "archive_runtime_context":
        return tool_archive_runtime_context(arguments)
    if name == "prompt_boundary_check":
        return tool_prompt_boundary_check(arguments)
    if name == "github_repository_setup_plan":
        return tool_github_repository_setup_plan(arguments)
    if name == "object_storage_setup_plan":
        return tool_object_storage_setup_plan(arguments)
    if name == "source_intake_plan":
        return tool_source_intake_plan(arguments)
    if name == "archive_init":
        return tool_archive_init(arguments)
    if name == "archive_onboarding_plan":
        return tool_archive_onboarding_plan(arguments)
    if name == "real_pilot_plan":
        return tool_real_pilot_plan(arguments)
    if name == "archive_preflight_check":
        return tool_archive_preflight_check(arguments)
    if name == "recovery_plan":
        return tool_recovery_plan(arguments)
    if name == "restore_drill_plan":
        return tool_restore_drill_plan(arguments)
    if name == "external_import_plan":
        return tool_external_import_plan(arguments)
    if name == "list_sources":
        return tool_list_sources(arguments)
    if name == "source_scan_plan":
        return tool_source_scan_plan(arguments)
    if name == "source_registration_plan":
        return tool_source_registration_plan(arguments)
    if name == "source_mount_plan":
        return tool_source_mount_plan(arguments)
    if name == "list_zettels":
        return tool_list_zettels(arguments)
    if name == "read_zettel":
        return tool_read_zettel(arguments)
    if name == "block_header_check":
        return tool_block_header_check(arguments)
    if name == "foreign_block_intake_check":
        return tool_foreign_block_intake_check(arguments)
    if name == "foreign_block_trust_check":
        return tool_foreign_block_trust_check(arguments)
    if name == "foreign_block_attestation_packet_check":
        return tool_foreign_block_attestation_packet_check(arguments)
    if name == "foreign_block_quarantine_plan":
        return tool_foreign_block_quarantine_plan(arguments)
    if name == "quarantine_foreign_block_check":
        return tool_quarantine_foreign_block_check(arguments)
    if name == "foreign_block_quarantine_review_index":
        return tool_foreign_block_quarantine_review_index(arguments)
    if name == "foreign_block_quarantine_decision_check":
        return tool_foreign_block_quarantine_decision_check(arguments)
    if name == "record_quarantine_decision_check":
        return tool_record_quarantine_decision_check(arguments)
    if name == "foreign_block_quarantine_decision_review_index":
        return tool_foreign_block_quarantine_decision_review_index(arguments)
    if name == "foreign_block_decision_outcome_plan":
        return tool_foreign_block_decision_outcome_plan(arguments)
    if name == "create_draft_zettel":
        return tool_create_draft_zettel(arguments)
    if name == "list_views":
        return tool_list_views(arguments)
    if name == "archive_index":
        return tool_archive_index(arguments)
    if name == "archive_search":
        return tool_archive_search(arguments)
    if name == "promotion_check":
        return tool_promotion_check(arguments)
    if name == "mint_zettel_check":
        return tool_mint_zettel_check(arguments)
    if name == "share_check":
        return tool_share_check(arguments)
    if name == "delegate_zet_check":
        return tool_delegate_zet_check(arguments)
    if name == "attest_zet_check":
        return tool_attest_zet_check(arguments)
    if name == "anchor_zet_check":
        return tool_anchor_zet_check(arguments)
    if name == "ownership_transfer_check":
        return tool_ownership_transfer_check(arguments)

    raise ToolError(f"Unknown tool: {name}")


def tool_archive_doctor(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    strict = bool(arguments.get("strict", False))
    doctor = archive_cli.Doctor(archive_root)
    diagnostics = doctor.run()
    errors = [item for item in diagnostics if item.severity == "ERROR"]
    warnings = [item for item in diagnostics if item.severity == "WARN"]
    ok = not errors and not (strict and warnings)
    text = f"archive_doctor: {len(errors)} error(s), {len(warnings)} warning(s)."
    return tool_success_result(
        text,
        {
            "ok": ok,
            "errors": len(errors),
            "warnings": len(warnings),
            "diagnostics": [item.as_dict() for item in diagnostics],
        },
    )


def tool_wom_profile_list(arguments: dict[str, Any]) -> dict[str, Any]:
    registry = require_path_arg(arguments, "registry")
    requested_redaction = bool(arguments.get("redact_local_paths", True))
    redact_local_paths = mcp_redact_local_paths(requested_redaction)
    result = call_service(
        archive_services.profile_list,
        registry,
        current_profile=optional_string_arg(arguments, "current_profile"),
        strict=bool(arguments.get("strict", False)),
        redact_local_paths=redact_local_paths,
    )
    add_mcp_redaction_warning(result, requested_redaction, redact_local_paths)
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"wom_profile_list: {state}.", result)


def tool_wom_profile_resolve(arguments: dict[str, Any]) -> dict[str, Any]:
    registry = require_path_arg(arguments, "registry")
    target = require_string_arg(arguments, "target")
    requested_redaction = bool(arguments.get("redact_local_paths", True))
    redact_local_paths = mcp_redact_local_paths(requested_redaction)
    result = call_service(
        archive_services.profile_resolve,
        registry,
        target=target,
        current_profile=optional_string_arg(arguments, "current_profile"),
        strict=bool(arguments.get("strict", False)),
        redact_local_paths=redact_local_paths,
    )
    add_mcp_redaction_warning(result, requested_redaction, redact_local_paths)
    state = str(result.get("resolution_state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"wom_profile_resolve: {state}.", result)


def tool_wom_profile_wallet_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    profile = require_string_arg(arguments, "profile")
    registry = optional_path_arg(arguments, "registry")
    if arguments.get("dry_run", True) is False:
        raise ToolError("wom_profile_wallet_check is dry-run only.")
    requested_redaction = bool(arguments.get("redact_local_paths", True))
    redact_local_paths = mcp_redact_local_paths(requested_redaction)
    result = call_service(
        archive_services.profile_wallet_preview,
        archive_root,
        profile=profile,
        registry_path=registry,
        dry_run=bool(arguments.get("dry_run", True)),
        redact_local_paths=redact_local_paths,
    )
    add_mcp_redaction_warning(result, requested_redaction, redact_local_paths)
    state = str(result.get("resolution_state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"wom_profile_wallet_check: {state}.", result)


def tool_archive_runtime_context(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    strict = bool(arguments.get("strict", False))
    requested_redaction = bool(arguments.get("redact_local_paths", True))
    redact_local_paths = mcp_redact_local_paths(requested_redaction)
    diagnostics = [item.as_dict() for item in archive_cli.Doctor(archive_root).run()]
    result = call_service(
        archive_services.runtime_context,
        archive_root,
        expected_archive_id=optional_string_arg(arguments, "expected_archive_id"),
        expected_type=optional_string_arg(arguments, "expected_type"),
        strict=strict,
        redact_local_paths=redact_local_paths,
        diagnostics=diagnostics,
    )
    add_mcp_redaction_warning(result, requested_redaction, redact_local_paths)
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"archive_runtime_context: {state}.", result)


def tool_prompt_boundary_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("prompt_boundary_check is dry-run only.")
    result = call_service(
        archive_services.prompt_boundary_check,
        archive_root,
        text=optional_string_arg(arguments, "text"),
        relative_path=optional_string_arg(arguments, "path"),
        dry_run=True,
    )
    state = str(result.get("risk_level") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"prompt_boundary_check: {state}.", result)


def tool_github_repository_setup_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.github_repository_setup_plan,
        archive_root,
        profile_id=optional_string_arg(arguments, "profile_id"),
        profile_slug=optional_string_arg(arguments, "profile_slug"),
        github_owner=optional_string_arg(arguments, "github_owner"),
        github_account_ref=optional_string_arg(arguments, "github_account_ref"),
        repo_name=optional_string_arg(arguments, "repo_name"),
        visibility=optional_string_arg(arguments, "visibility") or archive_services.GITHUB_REPOSITORY_DEFAULT_VISIBILITY,
        remote_protocol=optional_string_arg(arguments, "remote_protocol")
        or archive_services.GITHUB_REPOSITORY_DEFAULT_REMOTE_PROTOCOL,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"github_repository_setup_plan: {state}.", result)


def tool_object_storage_setup_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.object_storage_setup_plan,
        archive_root,
        provider=optional_string_arg(arguments, "provider"),
        profile_id=optional_string_arg(arguments, "profile_id"),
        profile_slug=optional_string_arg(arguments, "profile_slug"),
        storage_account_ref=optional_string_arg(arguments, "storage_account_ref"),
        bucket_name=optional_string_arg(arguments, "bucket_name"),
        region=optional_string_arg(arguments, "region"),
        endpoint_ref=optional_string_arg(arguments, "endpoint_ref"),
        objet_prefix=optional_string_arg(arguments, "objet_prefix"),
        visibility=optional_string_arg(arguments, "visibility") or archive_services.OBJECT_STORAGE_DEFAULT_VISIBILITY,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"object_storage_setup_plan: {state}.", result)


def tool_source_intake_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is False:
        raise ToolError("source_intake_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    local_path_value = optional_string_arg(arguments, "local_path")
    local_path = require_path_arg({"local_path": local_path_value}, "local_path") if local_path_value else None
    requested_redaction = bool(arguments.get("redact_local_paths", True))
    redact_local_paths = mcp_redact_local_paths(requested_redaction)
    result = call_service(
        archive_services.source_intake_plan,
        archive_root,
        local_path=local_path,
        source_id=optional_string_arg(arguments, "source"),
        item_id=optional_string_arg(arguments, "item_id"),
        relative_path=optional_string_arg(arguments, "relative_path"),
        objet_ref=optional_string_arg(arguments, "objet_ref"),
        object_id=optional_string_arg(arguments, "object_id"),
        provider=optional_string_arg(arguments, "provider"),
        provider_object_id=optional_string_arg(arguments, "provider_object_id"),
        provider_kind=optional_string_arg(arguments, "provider_kind"),
        ai_artifact_ref=optional_string_arg(arguments, "ai_artifact_ref"),
        runtime=optional_string_arg(arguments, "runtime"),
        artifact_kind=optional_string_arg(arguments, "artifact_kind"),
        expected_archive_id=optional_string_arg(arguments, "expected_archive_id"),
        expected_type=optional_string_arg(arguments, "expected_type"),
        profile_id=optional_string_arg(arguments, "profile_id"),
        source_role=optional_string_arg(arguments, "source_role") or archive_services.SOURCE_INTAKE_DEFAULT_ROLE,
        title=optional_string_arg(arguments, "title"),
        mime=optional_string_arg(arguments, "mime"),
        redact_local_paths=redact_local_paths,
    )
    add_mcp_redaction_warning(result, requested_redaction, redact_local_paths)
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"source_intake_plan: {state}.", result)


def tool_archive_init(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_cli.require_yaml()
    archive_root = require_path_arg(arguments, "archive_root")
    archive_type = require_string_arg(arguments, "archive_type")
    archive_id = require_string_arg(arguments, "archive_id")
    principal_id = require_string_arg(arguments, "principal_id")
    principal_name = optional_string_arg(arguments, "principal_name")
    principal_kind = optional_string_arg(arguments, "principal_kind") or "person"
    name = optional_string_arg(arguments, "name")
    dry_run = bool(arguments.get("dry_run", False))

    template = archive_cli.TEMPLATES_ROOT / archive_type
    if archive_type not in {"personal", "company", "family"} or not template.is_dir():
        raise ToolError(f"Unknown archive_type: {archive_type}")
    if archive_root.exists() and any(archive_root.iterdir()):
        raise ToolError(f"Target must be empty or absent: {archive_root}")

    if dry_run:
        return tool_success_result(
            f"Would initialize {archive_type} archive at {archive_root}",
            {"archive_root": str(archive_root), "archive_type": archive_type, "dry_run": True},
        )

    namespace = SimpleArgs(
        archive_root=str(archive_root),
        type=archive_type,
        archive_id=archive_id,
        principal_id=principal_id,
        principal_name=principal_name,
        principal_kind=principal_kind,
        name=name,
        dry_run=False,
    )
    archive_root.mkdir(parents=True, exist_ok=True)
    archive_cli.copy_template(template, archive_root)
    archive_cli.copy_zettel_kasten_layer(archive_root)
    archive_cli.create_recommended_dirs(archive_root)
    archive_cli.write_safe_gitignore(archive_root)
    archive_cli.update_archive_yml(archive_root, namespace)
    archive_cli.update_archive_identity_yml(archive_root, namespace)
    archive_cli.update_provider_bindings_yml(archive_root, namespace)
    archive_cli.update_source_bindings_yml(archive_root, namespace)

    return tool_success_result(
        f"Initialized {archive_type} archive at {archive_root}",
        {
            "archive_root": str(archive_root),
            "archive_type": archive_type,
            "archive_id": archive_id,
            "principal_id": principal_id,
        },
    )


def tool_archive_onboarding_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    target_root = require_path_arg(arguments, "target_root")
    archive_type = require_string_arg(arguments, "archive_type")
    archive_id = require_string_arg(arguments, "archive_id")
    principal_id = require_string_arg(arguments, "principal_id")
    principal_name = optional_string_arg(arguments, "principal_name")
    principal_kind = optional_string_arg(arguments, "principal_kind") or archive_services.default_principal_kind_for_archive_type(archive_type)
    name = optional_string_arg(arguments, "name")
    provider_profile = optional_string_arg(arguments, "provider_profile") or "local_only"
    result = archive_services.onboarding_plan(
        target_root,
        archive_type=archive_type,
        archive_id=archive_id,
        principal_id=principal_id,
        principal_name=principal_name,
        principal_kind=principal_kind,
        name=name,
        provider_profile=provider_profile,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"archive_onboarding_plan: {state}.", result)


def tool_real_pilot_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    personal_root = require_path_arg(arguments, "personal_root")
    team_root = require_path_arg(arguments, "team_root")
    result = call_service(
        archive_services.real_pilot_plan,
        personal_root=personal_root,
        team_root=team_root,
        personal_archive_id=optional_string_arg(arguments, "personal_archive_id") or "archive:personal:life",
        personal_principal_id=optional_string_arg(arguments, "personal_principal_id") or "person:me",
        personal_principal_name=optional_string_arg(arguments, "personal_principal_name"),
        team_archive_id=optional_string_arg(arguments, "team_archive_id") or "archive:company:founding-team",
        team_principal_id=optional_string_arg(arguments, "team_principal_id") or "team:founding-team",
        team_principal_name=optional_string_arg(arguments, "team_principal_name"),
        personal_provider_profile=optional_string_arg(arguments, "personal_provider_profile") or "object_storage_planned",
        team_provider_profile=optional_string_arg(arguments, "team_provider_profile") or "full_provider_plan",
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"real_pilot_plan: {state}.", result)


def tool_archive_preflight_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    peer_value = optional_string_arg(arguments, "peer_archive")
    peer_archive = require_path_arg({"peer_archive": peer_value}, "peer_archive") if peer_value else None
    strict = bool(arguments.get("strict", False))
    diagnostics = [item.as_dict() for item in archive_cli.Doctor(archive_root).run()]
    result = call_service(
        archive_services.preflight_check,
        archive_root,
        diagnostics=diagnostics,
        peer_archive_root=peer_archive,
        require_source_maps=bool(arguments.get("require_source_maps", False)),
        require_restore_drill=bool(arguments.get("require_restore_drill", False)),
        strict=strict,
        docker_runtime={"checked": False, "ok": None, "status": "not_checked"},
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"archive_preflight_check: {state}.", result)


def tool_recovery_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(archive_services.recovery_plan, archive_root)
    return tool_success_result(f"recovery_plan: {result['archive_id']}.", result)


def tool_restore_drill_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    target = require_path_arg(arguments, "target")
    result = call_service(archive_services.restore_drill_dry_run, archive_root, target)
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"restore_drill_plan: {state}.", result)


def tool_external_import_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    export_path = require_path_arg(arguments, "export_path")
    source = require_string_arg(arguments, "source")
    limit = int(arguments.get("limit", 200))
    result = call_service(
        archive_services.external_import_dry_run,
        archive_root,
        export_path,
        source_system=source,
        limit=limit,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"external_import_plan: {state}.", result)


def tool_list_sources(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(archive_services.list_sources, archive_root)
    return tool_success_result(f"Found {result['source_count']} source(s).", result)


def tool_source_scan_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    source = require_string_arg(arguments, "source")
    source_root_value = optional_string_arg(arguments, "source_root")
    source_root = require_path_arg({"source_root": source_root_value}, "source_root") if source_root_value else None
    limit = int(arguments.get("limit", 2000))
    result = call_service(
        archive_services.source_scan_dry_run,
        archive_root,
        source_id=source,
        source_root=source_root,
        limit=limit,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"source_scan_plan: {state}.", result)


def tool_source_registration_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    local_root_value = optional_string_arg(arguments, "local_root")
    local_root = require_path_arg({"local_root": local_root_value}, "local_root") if local_root_value else None
    result = call_service(
        archive_services.add_source_dry_run,
        archive_root,
        source_id=require_string_arg(arguments, "source_id"),
        source_type=require_string_arg(arguments, "source_type"),
        description=optional_string_arg(arguments, "description"),
        root_ref=optional_string_arg(arguments, "root_ref"),
        local_root=local_root,
        write_local_profile=bool(arguments.get("write_local_profile", False)),
        include=optional_string_list_arg(arguments, "include"),
        exclude=optional_string_list_arg(arguments, "exclude"),
        max_items=int(arguments.get("max_items", 2000)),
        visibility_scope=optional_string_arg(arguments, "visibility_scope") or "private",
        source_visibility=optional_string_arg(arguments, "source_visibility") or "private",
        replace=bool(arguments.get("replace", False)),
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"source_registration_plan: {state}.", result)


def tool_source_mount_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(archive_services.source_mount_plan, archive_root)
    return tool_success_result(f"source_mount_plan: {len(result['sources'])} source(s).", result)


def tool_list_zettels(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    status = optional_string_arg(arguments, "status") or "canonical"
    limit = int(arguments.get("limit", 100))
    result = call_service(archive_services.list_zettels, archive_root, status=status, limit=limit)

    return tool_success_result(
        f"Found {result['count']} zettel(s).",
        result,
    )


def tool_read_zettel(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    zettel_id = optional_string_arg(arguments, "zettel_id")
    relative_path = optional_string_arg(arguments, "path")
    result = call_service(
        archive_services.read_zettel,
        archive_root,
        zettel_id=zettel_id,
        relative_path=relative_path,
    )
    frontmatter = result["frontmatter"]
    return tool_success_result(
        f"Read zettel {frontmatter.get('id', result['path']) if isinstance(frontmatter, dict) else result['path']}.",
        result,
    )


def tool_block_header_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    zettel_id = optional_string_arg(arguments, "zettel_id")
    relative_path = optional_string_arg(arguments, "path")
    result = call_service(
        archive_services.block_header_preview,
        archive_root,
        zettel_id=zettel_id,
        relative_path=relative_path,
        dry_run=bool(arguments.get("dry_run", True)),
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"block_header_check: {state}.", result)


def tool_foreign_block_intake_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_intake_check is dry-run only.")
    content = arguments.get("content") if isinstance(arguments.get("content"), dict) else None
    if "content" in arguments and content is None:
        raise ToolError("foreign_block_intake_check content must be a structured object.")
    text = optional_string_arg(arguments, "text")
    relative_path = optional_string_arg(arguments, "path")
    result = call_service(
        archive_services.foreign_block_intake_check,
        archive_root,
        relative_path=relative_path,
        text=text,
        content=content,
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_intake_check: {state}.", result)


def tool_foreign_block_trust_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_trust_check is dry-run only.")
    intake_report = arguments.get("intake_report") if isinstance(arguments.get("intake_report"), dict) else None
    if "intake_report" in arguments and intake_report is None:
        raise ToolError("foreign_block_trust_check intake_report must be a structured object.")
    relative_path = optional_string_arg(arguments, "path")
    result = call_service(
        archive_services.foreign_block_trust_preview,
        archive_root,
        intake_report_path=relative_path,
        intake_report=intake_report,
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_trust_check: {state}.", result)


def tool_foreign_block_attestation_packet_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_attestation_packet_check is dry-run only.")
    trust_report = arguments.get("trust_report") if isinstance(arguments.get("trust_report"), dict) else None
    if "trust_report" in arguments and trust_report is None:
        raise ToolError("foreign_block_attestation_packet_check trust_report must be a structured object.")
    relative_path = optional_string_arg(arguments, "path")
    prospective_attestor = optional_string_arg(arguments, "prospective_attestor")
    review_scope = optional_string_arg(arguments, "review_scope") or "human_review"
    result = call_service(
        archive_services.foreign_block_attestation_packet_preview,
        archive_root,
        trust_report_path=relative_path,
        trust_report=trust_report,
        dry_run=True,
        prospective_attestor=prospective_attestor,
        review_scope=review_scope,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_attestation_packet_check: {state}.", result)


def tool_foreign_block_quarantine_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_quarantine_plan is dry-run only.")
    attestation_packet = arguments.get("attestation_packet") if isinstance(arguments.get("attestation_packet"), dict) else None
    if "attestation_packet" in arguments and attestation_packet is None:
        raise ToolError("foreign_block_quarantine_plan attestation_packet must be a structured object.")
    relative_path = optional_string_arg(arguments, "path")
    quarantine_case_id = optional_string_arg(arguments, "quarantine_case_id")
    reviewer = optional_string_arg(arguments, "reviewer")
    quarantine_policy = optional_string_arg(arguments, "quarantine_policy") or archive_services.FOREIGN_BLOCK_QUARANTINE_DEFAULT_POLICY
    result = call_service(
        archive_services.foreign_block_quarantine_plan,
        archive_root,
        attestation_packet_path=relative_path,
        attestation_packet=attestation_packet,
        dry_run=True,
        quarantine_case_id=quarantine_case_id,
        reviewer=reviewer,
        quarantine_policy=quarantine_policy,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_quarantine_plan: {state}.", result)


def tool_quarantine_foreign_block_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("quarantine_foreign_block_check is dry-run only.")
    quarantine_plan = arguments.get("quarantine_plan") if isinstance(arguments.get("quarantine_plan"), dict) else None
    if "quarantine_plan" in arguments and quarantine_plan is None:
        raise ToolError("quarantine_plan must be a structured object.")
    relative_path = optional_string_arg(arguments, "path")
    expected_case_id = optional_string_arg(arguments, "expected_case_id")
    reviewed_by = optional_string_arg(arguments, "reviewed_by")
    review_note = optional_string_arg(arguments, "review_note")
    result = call_service(
        archive_services.quarantine_foreign_block,
        archive_root,
        plan_path=relative_path,
        plan=quarantine_plan,
        dry_run=True,
        approve=False,
        reviewed_by=reviewed_by,
        expected_case_id=expected_case_id,
        review_note=review_note,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"quarantine_foreign_block_check: {state}.", result)


def tool_foreign_block_quarantine_review_index(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_quarantine_review_index is dry-run only.")
    case_id = optional_string_arg(arguments, "case_id")
    status = optional_string_arg(arguments, "status") or "written_untrusted"
    include_receipts = bool(arguments.get("include_receipts", False))
    result = call_service(
        archive_services.foreign_block_quarantine_review_index,
        archive_root,
        case_id=case_id,
        status=status,
        include_receipts=include_receipts,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_quarantine_review_index: {state}.", result)


def tool_foreign_block_quarantine_decision_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_quarantine_decision_check is dry-run only.")
    case_id = require_string_arg(arguments, "case_id")
    decision_intent = optional_string_arg(arguments, "decision_intent") or "auto"
    reviewer = optional_string_arg(arguments, "reviewer")
    review_note = optional_string_arg(arguments, "review_note")
    result = call_service(
        archive_services.foreign_block_quarantine_decision_preview,
        archive_root,
        case_id=case_id,
        decision_intent=decision_intent,
        reviewer=reviewer,
        review_note=review_note,
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_quarantine_decision_check: {state}.", result)


def tool_record_quarantine_decision_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("record_quarantine_decision_check is dry-run only.")
    if arguments.get("approve") is not None:
        raise ToolError("record_quarantine_decision_check does not approve or write.")
    decision_preview = arguments.get("decision_preview")
    if decision_preview is not None and not isinstance(decision_preview, dict):
        raise ToolError("decision_preview must be a structured object.")
    path = optional_string_arg(arguments, "path")
    expected_case_id = optional_string_arg(arguments, "expected_case_id")
    expected_decision = optional_string_arg(arguments, "expected_decision")
    reviewed_by = optional_string_arg(arguments, "reviewed_by")
    review_note = optional_string_arg(arguments, "review_note")
    result = call_service(
        archive_services.record_quarantine_decision,
        archive_root,
        decision_preview_path=path,
        decision_preview=decision_preview,
        dry_run=True,
        approve=False,
        reviewed_by=reviewed_by,
        expected_case_id=expected_case_id,
        expected_decision=expected_decision,
        review_note=review_note,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"record_quarantine_decision_check: {state}.", result)


def tool_foreign_block_quarantine_decision_review_index(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_quarantine_decision_review_index is dry-run only.")
    case_id = optional_string_arg(arguments, "case_id")
    decision = optional_string_arg(arguments, "decision") or "all"
    include_receipts = bool(arguments.get("include_receipts", False))
    result = call_service(
        archive_services.foreign_block_quarantine_decision_review_index,
        archive_root,
        case_id=case_id,
        decision=decision,
        include_receipts=include_receipts,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_quarantine_decision_review_index: {state}.", result)


def tool_foreign_block_decision_outcome_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_decision_outcome_plan is dry-run only.")
    case_id = require_string_arg(arguments, "case_id")
    expected_decision = optional_string_arg(arguments, "expected_decision")
    reviewer = optional_string_arg(arguments, "reviewer")
    review_note = optional_string_arg(arguments, "review_note")
    result = call_service(
        archive_services.foreign_block_decision_outcome_plan,
        archive_root,
        case_id=case_id,
        dry_run=True,
        expected_decision=expected_decision,
        reviewer=reviewer,
        review_note=review_note,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_decision_outcome_plan: {state}.", result)


def tool_create_draft_zettel(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    title = require_string_arg(arguments, "title")
    body = require_string_arg(arguments, "body")
    archive_id = optional_string_arg(arguments, "archive_id")
    kind = optional_string_arg(arguments, "kind") or "fleeting_capture"
    facets = arguments.get("facets") if isinstance(arguments.get("facets"), dict) else {}
    visibility = arguments.get("visibility") if isinstance(arguments.get("visibility"), dict) else None
    profile_context = arguments.get("profile_context") if isinstance(arguments.get("profile_context"), dict) else {}
    source_refs = arguments.get("source_refs") if isinstance(arguments.get("source_refs"), list) else []
    if "source_intake_plan" in arguments and not isinstance(arguments.get("source_intake_plan"), dict):
        raise ToolError("source_intake_plan must be a structured object, not a local file path.")
    source_intake_plan = arguments.get("source_intake_plan") if isinstance(arguments.get("source_intake_plan"), dict) else None
    if "prompt_boundary_report" in arguments and not isinstance(arguments.get("prompt_boundary_report"), dict):
        raise ToolError("prompt_boundary_report must be a structured object, not a local file path.")
    prompt_boundary_report = (
        arguments.get("prompt_boundary_report") if isinstance(arguments.get("prompt_boundary_report"), dict) else None
    )
    local_ai_sessions = arguments.get("local_ai_sessions") if isinstance(arguments.get("local_ai_sessions"), list) else []
    created_by = optional_string_arg(arguments, "created_by") or "mcp:zettel-kasten-archive-mcp"
    source = optional_string_arg(arguments, "source") or "mcp_tool_call"
    result = call_service(
        archive_services.create_draft_zettel,
        archive_root,
        title=title,
        body=body,
        archive_id=archive_id,
        kind=kind,
        facets=facets,
        visibility=visibility,
        created_by=created_by,
        source=source,
        dry_run=bool(arguments.get("dry_run", False)),
        expected_archive_id=optional_string_arg(arguments, "expected_archive_id"),
        expected_type=optional_string_arg(arguments, "expected_type"),
        profile_id=profile_context.get("profile_id") if isinstance(profile_context.get("profile_id"), str) else None,
        profile_operator_id=(
            profile_context.get("operator_id")
            if isinstance(profile_context.get("operator_id"), str)
            else profile_context.get("profile_operator_id")
            if isinstance(profile_context.get("profile_operator_id"), str)
            else None
        ),
        profile_authority_mode=(
            profile_context.get("authority_mode")
            if isinstance(profile_context.get("authority_mode"), str)
            else profile_context.get("profile_authority_mode")
            if isinstance(profile_context.get("profile_authority_mode"), str)
            else None
        ),
        creation_mode=optional_string_arg(arguments, "creation_mode"),
        assisted_by=optional_string_list_arg(arguments, "assisted_by"),
        supervised_by=optional_string_list_arg(arguments, "supervised_by"),
        derived_from=optional_string_list_arg(arguments, "derived_from"),
        source_refs=source_refs,
        source_intake_plan=source_intake_plan,
        prompt_boundary_report=prompt_boundary_report,
        local_ai_sessions=local_ai_sessions,
        draft_id=optional_string_arg(arguments, "draft_id"),
        created_at=optional_string_arg(arguments, "created_at"),
        expected_body_sha256=optional_string_arg(arguments, "expected_body_sha256"),
        draft_approved_by=optional_string_arg(arguments, "draft_approved_by"),
    )

    if result.get("dry_run"):
        state = "passed" if result.get("ok") else "blocked"
        return tool_success_result(f"create_draft_zettel dry-run: {state}.", result)
    return tool_success_result(f"Created draft zettel {result['zettel_id']}.", result)


def tool_list_views(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(archive_services.list_views, archive_root)
    return tool_success_result(f"Found {result['count']} view(s).", result)


def tool_archive_index(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(archive_services.index_archive, archive_root)
    return tool_success_result(
        "Indexed "
        f"{result['zettels']} zettel(s), "
        f"{result['objects']} object(s), "
        f"{result['views']} view(s), "
        f"{result['source_map_entries']} source map item(s).",
        result,
    )


def tool_archive_search(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    query = require_string_arg(arguments, "query")
    limit = int(arguments.get("limit", 20))
    result = call_service(archive_services.search_archive, archive_root, query, limit=limit)
    return tool_success_result(f"Found {result['count']} result(s).", result)


def tool_promotion_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    zettel_id = optional_string_arg(arguments, "zettel_id")
    relative_path = optional_string_arg(arguments, "path")
    result = call_service(
        archive_services.promote_zettel_dry_run,
        archive_root,
        zettel_id=zettel_id,
        relative_path=relative_path,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"promotion_check: {state}.", result)


def tool_mint_zettel_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    zettel_id = optional_string_arg(arguments, "zettel_id")
    relative_path = optional_string_arg(arguments, "path")
    result = call_service(
        archive_services.mint_zettel_dry_run,
        archive_root,
        zettel_id=zettel_id,
        relative_path=relative_path,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"mint_zettel_check: {state}.", result)


def tool_share_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    view_id = require_string_arg(arguments, "view")
    target_archive = require_string_arg(arguments, "target_archive")
    counterparty_id = optional_string_arg(arguments, "counterparty_id")
    counterparty_fingerprint = optional_string_arg(arguments, "counterparty_fingerprint")
    allow_sensitive = bool(arguments.get("allow_sensitive", False))
    result = call_service(
        archive_services.share_archive_scope_dry_run,
        archive_root,
        view_id=view_id,
        target_archive=target_archive,
        counterparty_id=counterparty_id,
        counterparty_fingerprint=counterparty_fingerprint,
        allow_sensitive=allow_sensitive,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"share_check: {state}.", result)


def tool_delegate_zet_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    view_id = require_string_arg(arguments, "view")
    target_archive = optional_string_arg(arguments, "target_archive")
    target_policy = optional_string_arg(arguments, "target_policy")
    counterparty_id = optional_string_arg(arguments, "counterparty_id")
    counterparty_fingerprint = optional_string_arg(arguments, "counterparty_fingerprint")
    allow_sensitive = bool(arguments.get("allow_sensitive", False))
    result = call_service(
        archive_services.delegate_zets_dry_run,
        archive_root,
        view_id=view_id,
        target_archive=target_archive,
        counterparty_id=counterparty_id,
        counterparty_fingerprint=counterparty_fingerprint,
        allow_sensitive=allow_sensitive,
        target_policy=target_policy,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"delegate_zet_check: {state}.", result)


def tool_attest_zet_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    delegate_receipt = require_string_arg(arguments, "delegate_receipt")
    counterparty_id = optional_string_arg(arguments, "counterparty_id")
    counterparty_fingerprint = optional_string_arg(arguments, "counterparty_fingerprint")
    result = call_service(
        archive_services.attest_zets_dry_run,
        archive_root,
        delegate_receipt_path=delegate_receipt,
        counterparty_id=counterparty_id,
        counterparty_fingerprint=counterparty_fingerprint,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"attest_zet_check: {state}.", result)


def tool_anchor_zet_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    attestation_receipt = require_string_arg(arguments, "attestation_receipt")
    result = call_service(
        archive_services.anchor_zets_dry_run,
        archive_root,
        attestation_receipt_path=attestation_receipt,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"anchor_zet_check: {state}.", result)


def tool_ownership_transfer_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    new_owner = require_string_arg(arguments, "new_owner")
    new_owner_kind = optional_string_arg(arguments, "new_owner_kind")
    new_owner_archive = optional_string_arg(arguments, "new_owner_archive")
    operators_after = optional_string_list_arg(arguments, "operators_after")
    approved_by = optional_string_list_arg(arguments, "approved_by")
    subject = optional_string_arg(arguments, "subject")
    counterparty_id = optional_string_arg(arguments, "counterparty_id")
    counterparty_fingerprint = optional_string_arg(arguments, "counterparty_fingerprint")
    reason = optional_string_arg(arguments, "reason")
    result = call_service(
        archive_services.ownership_transfer_dry_run,
        archive_root,
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
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"ownership_transfer_check: {state}.", result)


class SimpleArgs:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class ToolError(Exception):
    pass


class InvalidParamsError(Exception):
    pass


class MethodNotFoundError(Exception):
    pass


def tool_success_result(text: str, structured: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": structured,
        "isError": False,
    }


def tool_error_result(text: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": {"error": text},
        "isError": True,
    }


def mcp_redact_local_paths(requested_redaction: bool) -> bool:
    return requested_redaction or os.environ.get(MCP_ALLOW_LOCAL_PATHS_ENV) != "1"


def add_mcp_redaction_warning(result: dict[str, Any], requested_redaction: bool, effective_redaction: bool) -> None:
    if requested_redaction or not effective_redaction:
        return
    warnings = result.get("warnings")
    if not isinstance(warnings, list):
        warnings = []
        result["warnings"] = warnings
    warnings.append(
        "MCP local path disclosure was requested but ignored because "
        f"{MCP_ALLOW_LOCAL_PATHS_ENV}=1 is not set."
    )


def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def require_string_arg(arguments: dict[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value:
        raise ToolError(f"Missing required string argument: {name}")
    return value


def optional_string_arg(arguments: dict[str, Any], name: str) -> str | None:
    value = arguments.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolError(f"Argument must be a string: {name}")
    return value


def optional_string_list_arg(arguments: dict[str, Any], name: str) -> list[str] | None:
    value = arguments.get(name)
    if value is None:
        return None
    if not isinstance(value, list):
        raise ToolError(f"Argument must be a list of strings: {name}")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ToolError(f"Argument must be a list of strings: {name}")
        result.append(item)
    return result


def require_path_arg(arguments: dict[str, Any], name: str) -> Path:
    path = Path(require_string_arg(arguments, name)).resolve()
    enforce_mcp_path_allowlist(path)
    return path


def optional_path_arg(arguments: dict[str, Any], name: str) -> Path | None:
    value = arguments.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ToolError(f"Argument must be a non-empty string path: {name}")
    path = Path(value).resolve()
    enforce_mcp_path_allowlist(path)
    return path


def enforce_mcp_path_allowlist(path: Path) -> None:
    raw_roots = os.environ.get(MCP_ALLOWED_ROOTS_ENV)
    if not raw_roots and os.environ.get("AI_ARCHIVE_CONTAINER") == "1":
        raw_roots = "/archives"
    if not raw_roots:
        return

    allowed_roots = [Path(item).resolve() for item in raw_roots.split(os.pathsep) if item.strip()]
    if not allowed_roots:
        return
    if any(path == root or path.is_relative_to(root) for root in allowed_roots):
        return
    allowed = ", ".join(str(root) for root in allowed_roots)
    raise ToolError(f"MCP path is outside allowed archive root(s): {path}. Allowed root(s): {allowed}")


def require_existing_archive_root(arguments: dict[str, Any]) -> Path:
    archive_root = require_path_arg(arguments, "archive_root")
    if not archive_root.is_dir():
        raise ToolError(f"Archive root does not exist or is not a directory: {archive_root}")
    return archive_root


def call_service(func: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return func(*args, **kwargs)
    except archive_services.ArchiveServiceError as exc:
        raise ToolError(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
