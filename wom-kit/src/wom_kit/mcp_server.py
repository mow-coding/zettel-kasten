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


def configure_stdio_utf8() -> None:
    for stream in (sys.stdin, sys.stdout):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except (TypeError, ValueError):
                pass


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
        "name": "provider_setup_status",
        "description": "Check local provider setup metadata and receipts. Read-only; never calls providers, creates repos or buckets, uploads, syncs, pushes, hashes, OAuth, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "object_storage_adapter_readiness_plan",
        "description": "Check readiness for a future object-storage adapter. Read-only; never calls providers, retrieves secrets, uploads, downloads, creates presigned URLs, reads object bytes, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "operation": {
                    "type": "string",
                    "enum": sorted(archive_services.OBJECT_STORAGE_ADAPTER_OPERATIONS),
                    "default": "presigned_download",
                },
                "provider_ref": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "object_storage_operation_request_plan",
        "description": "Compose a read-only approval request package before a future object-storage operation. Never calls providers, retrieves secrets, uploads, downloads, creates presigned URLs, reads object bytes, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "operation": {
                    "type": "string",
                    "enum": sorted(archive_services.OBJECT_STORAGE_ADAPTER_OPERATIONS),
                    "default": "presigned_download",
                },
                "object_id": {"type": "string"},
                "store_ref": {"type": "string"},
                "ttl_seconds": {"type": "integer", "default": archive_services.PRESIGNED_URL_DEFAULT_TTL_SECONDS},
                "provider_ref": {"type": "string"},
                "credential_id": {"type": "string", "default": "cred:object-storage"},
                "credential_ref": {"type": "string"},
                "credential_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS)},
                "provider": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS)},
                "store_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS), "default": "password_manager"},
                "adapter_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_ADAPTER_KINDS)},
                "approval_decision": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS), "default": "needs_review"},
                "approval_receipt": {"type": "string"},
                "consumer": {"type": "string", "default": "wom:adapter:object-storage"},
                "reviewed_by": {"type": "string", "default": "human:pending-review"},
                "platform": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS), "default": "windows"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "human_artifact_store_plan",
        "description": "Plan a user-facing human artifact surface. Read-only; never creates notes, publishes posts, uploads files, starts OAuth, calls providers, mints, or runs ZET transport.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "surface_kind": {"type": "string", "enum": sorted(archive_services.HUMAN_ARTIFACT_SURFACE_KINDS)},
                "surface_ref": {"type": "string"},
                "role": {
                    "type": "string",
                    "enum": sorted(archive_services.HUMAN_ARTIFACT_ROLES),
                    "default": archive_services.HUMAN_ARTIFACT_DEFAULT_ROLE,
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "surface_kind"],
        },
    },
    {
        "name": "imap_mailbox_plan",
        "description": "Plan a read-only Gmail, Naver, or generic IMAP mailbox source. Dry-run only; never connects, logs in, reads headers/bodies/attachments, sends mail, changes flags, stores secrets, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "source_id": {"type": "string"},
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
                    "default": "generic_imap",
                },
                "imap_host": {"type": "string"},
                "imap_port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 993},
                "account_ref": {"type": "string"},
                "username_ref": {"type": "string"},
                "auth_mode": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
                    "default": "app_password_ref",
                },
                "app_password_ref": {"type": "string"},
                "oauth_token_ref": {"type": "string"},
                "mailbox_ref": {"type": "string", "default": "imap:mailbox:inbox"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "source_id", "account_ref", "username_ref"],
        },
    },
    {
        "name": "imap_mailbox_operation_request_plan",
        "description": "Compose a read-only approval request package before a future IMAP mailbox operation. Dry-run only; never connects, logs in, reads headers/bodies/attachments, opens keyrings, starts OAuth, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "source_id": {"type": "string"},
                "adapter_id": {
                    "type": "string",
                    "description": "Optional safe adapter manifest id to check under config/imap-adapters/.",
                },
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
                    "default": "generic_imap",
                },
                "imap_host": {"type": "string"},
                "imap_port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 993},
                "account_ref": {"type": "string"},
                "username_ref": {"type": "string"},
                "auth_mode": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
                    "default": "app_password_ref",
                },
                "app_password_ref": {"type": "string"},
                "oauth_token_ref": {"type": "string"},
                "mailbox_ref": {"type": "string", "default": "imap:mailbox:inbox"},
                "operation": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
                    "default": "header_metadata_scan",
                },
                "max_messages": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_LIMIT,
                    "default": archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
                },
                "since_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": archive_services.IMAP_MAILBOX_OPERATION_SINCE_DAYS_LIMIT,
                },
                "credential_id": {"type": "string", "default": "cred:mail-source-access"},
                "credential_ref": {"type": "string"},
                "credential_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS)},
                "credential_provider": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS)},
                "store_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
                    "default": "password_manager",
                },
                "adapter_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_ADAPTER_KINDS)},
                "approval_decision": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
                    "default": "needs_review",
                },
                "approval_receipt": {"type": "string"},
                "consumer": {"type": "string", "default": "wom:adapter:imap-mailbox"},
                "reviewed_by": {"type": "string", "default": "human:pending-review"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "source_id", "account_ref", "username_ref"],
        },
    },
    {
        "name": "imap_mailbox_adapter_readiness_plan",
        "description": "Check readiness for a future IMAP mailbox adapter. Dry-run only; never connects, logs in, reads headers/bodies/attachments, opens keyrings, starts OAuth, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "source_id": {"type": "string"},
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
                    "default": "generic_imap",
                },
                "imap_host": {"type": "string"},
                "imap_port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 993},
                "account_ref": {"type": "string"},
                "username_ref": {"type": "string"},
                "auth_mode": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
                    "default": "app_password_ref",
                },
                "app_password_ref": {"type": "string"},
                "oauth_token_ref": {"type": "string"},
                "mailbox_ref": {"type": "string", "default": "imap:mailbox:inbox"},
                "operation": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
                    "default": "header_metadata_scan",
                },
                "max_messages": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_LIMIT,
                    "default": archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
                },
                "since_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": archive_services.IMAP_MAILBOX_OPERATION_SINCE_DAYS_LIMIT,
                },
                "credential_id": {"type": "string", "default": "cred:mail-source-access"},
                "credential_ref": {"type": "string"},
                "credential_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS)},
                "credential_provider": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS)},
                "store_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
                    "default": "password_manager",
                },
                "adapter_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_ADAPTER_KINDS)},
                "approval_decision": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
                    "default": "needs_review",
                },
                "approval_receipt": {"type": "string"},
                "consumer": {"type": "string", "default": "wom:adapter:imap-mailbox"},
                "reviewed_by": {"type": "string", "default": "human:pending-review"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "source_id", "account_ref", "username_ref"],
        },
    },
    {
        "name": "imap_mailbox_selection_plan",
        "description": "Plan future read-only mailbox message selection. Dry-run only; never connects, logs in, selects/searches a mailbox, lists message ids, reads headers/bodies/attachments, opens keyrings, starts OAuth, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "source_id": {"type": "string"},
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
                    "default": "generic_imap",
                },
                "imap_host": {"type": "string"},
                "imap_port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 993},
                "account_ref": {"type": "string"},
                "username_ref": {"type": "string"},
                "auth_mode": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
                    "default": "app_password_ref",
                },
                "app_password_ref": {"type": "string"},
                "oauth_token_ref": {"type": "string"},
                "mailbox_ref": {"type": "string", "default": "imap:mailbox:inbox"},
                "operation": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
                    "default": "header_metadata_scan",
                },
                "selection_rule": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_SELECTION_RULES),
                    "default": "newest_first",
                },
                "selector_id": {"type": "string", "default": "mail-selection:recent-inbox"},
                "max_messages": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_LIMIT,
                    "default": archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
                },
                "since_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": archive_services.IMAP_MAILBOX_OPERATION_SINCE_DAYS_LIMIT,
                },
                "credential_id": {"type": "string", "default": "cred:mail-source-access"},
                "credential_ref": {"type": "string"},
                "credential_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS)},
                "credential_provider": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS)},
                "store_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
                    "default": "password_manager",
                },
                "adapter_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_ADAPTER_KINDS)},
                "approval_decision": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
                    "default": "needs_review",
                },
                "approval_receipt": {"type": "string"},
                "consumer": {"type": "string", "default": "wom:adapter:imap-mailbox"},
                "reviewed_by": {"type": "string", "default": "human:pending-review"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "source_id", "account_ref", "username_ref"],
        },
    },
    {
        "name": "imap_mailbox_adapter_audit_plan",
        "description": "Preview a non-secret future IMAP adapter audit receipt. Dry-run only; never connects, logs in, selects/searches a mailbox, lists messages, reads headers/bodies/attachments, opens keyrings, starts OAuth, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "adapter_id": {"type": "string"},
                "source_id": {"type": "string"},
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
                    "default": "generic_imap",
                },
                "imap_host": {"type": "string"},
                "imap_port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 993},
                "account_ref": {"type": "string"},
                "username_ref": {"type": "string"},
                "auth_mode": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
                    "default": "app_password_ref",
                },
                "app_password_ref": {"type": "string"},
                "oauth_token_ref": {"type": "string"},
                "mailbox_ref": {"type": "string", "default": "imap:mailbox:inbox"},
                "operation": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
                    "default": "header_metadata_scan",
                },
                "selection_rule": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_SELECTION_RULES),
                    "default": "newest_first",
                },
                "selector_id": {"type": "string", "default": "mail-selection:recent-inbox"},
                "max_messages": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_LIMIT,
                    "default": archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
                },
                "since_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": archive_services.IMAP_MAILBOX_OPERATION_SINCE_DAYS_LIMIT,
                },
                "credential_id": {"type": "string", "default": "cred:mail-source-access"},
                "credential_ref": {"type": "string"},
                "credential_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS)},
                "credential_provider": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS)},
                "store_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
                    "default": "password_manager",
                },
                "adapter_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_ADAPTER_KINDS)},
                "approval_decision": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
                    "default": "needs_review",
                },
                "approval_receipt": {"type": "string"},
                "result_status": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ADAPTER_AUDIT_RESULT_STATUSES),
                    "default": "not_run",
                },
                "consumer": {"type": "string", "default": "wom:adapter:imap-mailbox"},
                "reviewed_by": {"type": "string", "default": "human:pending-review"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "adapter_id", "source_id", "account_ref", "username_ref"],
        },
    },
    {
        "name": "imap_mailbox_adapter_manifest_plan",
        "description": "Preview a non-secret future IMAP adapter manifest. Dry-run only; never writes manifests, connects, logs in, selects/searches a mailbox, lists messages, reads headers/bodies/attachments, opens keyrings, starts OAuth, or calls providers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "adapter_id": {"type": "string"},
                "providers": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS)},
                },
                "operations": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS)},
                },
                "selection_rules": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(archive_services.IMAP_MAILBOX_SELECTION_RULES)},
                },
                "consumer": {"type": "string", "default": "wom:adapter:imap-mailbox"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "adapter_id"],
        },
    },
    {
        "name": "imap_mailbox_adapter_preflight_plan",
        "description": "Run a read-only preflight before any future IMAP adapter execution. Dry-run only; never connects, logs in, selects/searches a mailbox, lists messages, reads headers/bodies/attachments, opens keyrings, starts OAuth, calls providers, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "adapter_id": {"type": "string"},
                "source_id": {"type": "string"},
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_PROVIDERS),
                    "default": "generic_imap",
                },
                "imap_host": {"type": "string"},
                "imap_port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 993},
                "account_ref": {"type": "string"},
                "username_ref": {"type": "string"},
                "auth_mode": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_ALLOWED_AUTH_MODES),
                    "default": "app_password_ref",
                },
                "app_password_ref": {"type": "string"},
                "oauth_token_ref": {"type": "string"},
                "mailbox_ref": {"type": "string", "default": "imap:mailbox:inbox"},
                "operation": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_OPERATION_REQUEST_OPERATIONS),
                    "default": "header_metadata_scan",
                },
                "selection_rule": {
                    "type": "string",
                    "enum": sorted(archive_services.IMAP_MAILBOX_SELECTION_RULES),
                    "default": "newest_first",
                },
                "selector_id": {"type": "string", "default": "mail-selection:recent-inbox"},
                "max_messages": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_LIMIT,
                    "default": archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT,
                },
                "since_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": archive_services.IMAP_MAILBOX_OPERATION_SINCE_DAYS_LIMIT,
                },
                "credential_id": {"type": "string", "default": "cred:mail-source-access"},
                "credential_ref": {"type": "string"},
                "credential_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS)},
                "credential_provider": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS)},
                "store_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
                    "default": "password_manager",
                },
                "adapter_kind": {"type": "string", "enum": sorted(archive_services.CREDENTIAL_ADAPTER_KINDS)},
                "approval_decision": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
                    "default": "needs_review",
                },
                "approval_receipt": {"type": "string"},
                "consumer": {"type": "string", "default": "wom:adapter:imap-mailbox"},
                "reviewed_by": {"type": "string", "default": "human:pending-review"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "adapter_id", "source_id", "account_ref", "username_ref"],
        },
    },
    {
        "name": "credential_ref_plan",
        "description": "Plan a local credential reference for mail, model APIs, OCR APIs, storage, or backups. Dry-run only; never reads, writes, prompts for, or echoes secret values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "credential_id": {"type": "string"},
                "credential_ref": {"type": "string"},
                "credential_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
                    "default": "generic_secret",
                },
                "purpose": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PURPOSES),
                },
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "credential_id", "credential_ref"],
        },
    },
    {
        "name": "credential_ref_inventory",
        "description": "List known credential refs without echoing ref values or secrets. Read-only; never reads environment variables, opens keyrings, calls providers, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "credential_store_recommendation",
        "description": "Recommend a password manager, OS keyring, or secret manager class for a human scenario. Read-only; never reads, writes, prompts for, or echoes secrets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "scenario": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_SCENARIOS),
                },
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "scenario"],
        },
    },
    {
        "name": "credential_vault_onboarding_plan",
        "description": "Plan safe human vault/keyring onboarding without opening password managers, browser stores, keyrings, files, environment variables, or providers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "scenario": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_SCENARIOS),
                },
                "store_id": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_VAULT_ONBOARDING_STORE_IDS),
                    "default": "recommended",
                },
                "credential_id": {"type": "string"},
                "credential_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
                },
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
                },
                "action_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
                },
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "scenario"],
        },
    },
    {
        "name": "credential_plaintext_migration_plan",
        "description": "Plan safe migration from a human-selected plaintext secret note into a real vault/keyring without reading files, returning secrets, writing vaults, or deleting plaintext.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "source_label": {"type": "string", "description": "Safe non-secret source label; not a path."},
                "credential_id": {"type": "string"},
                "target_store_id": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_VAULT_ONBOARDING_STORE_IDS),
                    "default": "recommended",
                },
                "scenario": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_SCENARIOS),
                    "default": "personal_local_first",
                },
                "credential_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
                },
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
                },
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "source_label", "credential_id"],
        },
    },
    {
        "name": "credential_policy_check",
        "description": "Check a credential request against the approval policy gate before any future adapter can run. Read-only; never opens stores, reads secrets, writes receipts, or executes adapters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "credential_id": {"type": "string"},
                "credential_ref": {"type": "string"},
                "credential_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
                },
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
                },
                "action_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
                },
                "approval_decision": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
                    "default": "needs_review",
                },
                "store_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
                    "default": "password_manager",
                },
                "adapter_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
                },
                "operation": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ADAPTER_OPERATIONS),
                },
                "consumer": {"type": "string", "default": "wom_local_adapter"},
                "reviewed_by": {"type": "string", "default": "human:pending-review"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "approval_receipt": {
                    "type": "string",
                    "description": "Optional archive-relative credential access approval receipt to verify.",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "credential_id", "action_kind"],
        },
    },
    {
        "name": "credential_keepassxc_command_plan",
        "description": "Plan a KeePassXC CLI add command after verifying an approval receipt. Read-only; never executes keepassxc-cli, opens vaults, reads paths, prompts for, writes, or echoes secrets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "credential_id": {"type": "string"},
                "credential_ref": {"type": "string"},
                "credential_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
                },
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
                },
                "action_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
                    "default": "plaintext_secret_migration",
                },
                "operation": {
                    "type": "string",
                    "enum": ["plaintext_secret_migration", "write_new_secret"],
                    "default": "plaintext_secret_migration",
                },
                "approval_receipt": {
                    "type": "string",
                    "description": "Archive-relative credential access approval receipt to verify.",
                },
                "entry_label": {"type": "string", "description": "Safe non-secret KeePassXC entry label."},
                "group_label": {"type": "string", "description": "Optional safe non-secret KeePassXC group label."},
                "database_ref": {
                    "type": "string",
                    "description": "Safe label for the human-selected database; not a local path.",
                    "default": "keepassxc:human-selected-database",
                },
                "consumer": {"type": "string", "default": "wom:adapter:keepassxc"},
                "reviewed_by": {"type": "string", "default": "human:pending-review"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "credential_id", "approval_receipt", "entry_label"],
        },
    },
    {
        "name": "credential_access_broker_plan",
        "description": "Plan a future approved credential broker request without retrieving secrets. Read-only; never opens password managers, browser stores, keyrings, files, or environment variables.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "credential_id": {"type": "string"},
                "credential_ref": {"type": "string"},
                "credential_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
                },
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
                },
                "action_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
                },
                "store_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
                    "default": "password_manager",
                },
                "consumer": {"type": "string", "default": "wom_local_adapter"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "credential_id", "action_kind"],
        },
    },
    {
        "name": "credential_access_approval_plan",
        "description": "Preview a future credential access approval receipt without writing or retrieving secrets. Read-only; never opens vaults, keyrings, browser stores, files, or environment variables.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "credential_id": {"type": "string"},
                "credential_ref": {"type": "string"},
                "credential_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
                },
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
                },
                "action_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
                },
                "decision": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_APPROVAL_DECISIONS),
                    "default": "needs_review",
                },
                "store_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
                    "default": "password_manager",
                },
                "consumer": {"type": "string", "default": "wom_local_adapter"},
                "reviewed_by": {"type": "string", "default": "human:pending-review"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "credential_id", "action_kind"],
        },
    },
    {
        "name": "credential_adapter_readiness_plan",
        "description": "Preview a future credential adapter contract without opening keyrings, vaults, browser stores, files, or environment variables. Read-only; never retrieves, writes, or echoes secrets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "adapter_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
                },
                "operation": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ADAPTER_OPERATIONS),
                },
                "credential_id": {"type": "string"},
                "credential_ref": {"type": "string"},
                "credential_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
                },
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
                },
                "action_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
                },
                "store_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
                },
                "consumer": {"type": "string"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "adapter_kind", "operation", "credential_id", "action_kind"],
        },
    },
    {
        "name": "credential_adapter_manifest_plan",
        "description": "Preview a non-secret future credential adapter manifest without writing it. Read-only; never opens keyrings, vaults, browser stores, files, or environment variables.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "adapter_id": {"type": "string"},
                "adapter_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
                },
                "operations": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": sorted(archive_services.CREDENTIAL_ADAPTER_OPERATIONS),
                    },
                },
                "store_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
                },
                "consumer": {"type": "string"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "adapter_id", "adapter_kind"],
        },
    },
    {
        "name": "credential_adapter_audit_plan",
        "description": "Preview a non-secret future credential adapter audit receipt without writing it. Read-only; never executes adapters, opens stores, reads secrets, or calls providers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "adapter_id": {"type": "string"},
                "adapter_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ADAPTER_KINDS),
                },
                "operation": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ADAPTER_OPERATIONS),
                },
                "credential_id": {"type": "string"},
                "credential_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_KINDS),
                },
                "provider": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_REF_ALLOWED_PROVIDERS),
                },
                "action_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_ACTIONS),
                },
                "result_status": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ADAPTER_AUDIT_RESULT_STATUSES),
                    "default": "not_run",
                },
                "store_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_ACCESS_BROKER_STORE_KINDS),
                },
                "consumer": {"type": "string"},
                "platform": {
                    "type": "string",
                    "enum": sorted(archive_services.CREDENTIAL_STORE_RECOMMENDATION_PLATFORMS),
                    "default": "windows",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "adapter_id", "adapter_kind", "operation", "credential_id", "action_kind"],
        },
    },
    {
        "name": "zet_surface_prototype_plan",
        "description": "Plan a user-selected ZET surface prototype for WordPress, Joplin, Notion, or Obsidian. Read-only; never calls providers, requests tokens, writes notes, publishes, syncs, mints, or transports.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "surface_kind": {"type": "string", "enum": sorted(archive_services.ZET_SURFACE_PROTOTYPE_KINDS)},
                "surface_ref": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "surface_kind"],
        },
    },
    {
        "name": "prehashed_objet_ledger_preview",
        "description": "Preview an already-hashed external content-addressed objet ledger. Read-only; never echoes row values, reads blob bytes, registers manifests, writes, uploads, or calls providers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "ledger": {"type": "string", "description": "UTF-8 JSONL ledger path."},
                "store_kind": {
                    "type": "string",
                    "enum": sorted(archive_services.PREHASHED_OBJET_LEDGER_STORE_KINDS),
                    "default": "generic_content_addressed_store",
                },
                "sha256_field": {"type": "string", "default": "sha256"},
                "size_field": {"type": "string", "default": "bytes"},
                "mime_field": {"type": "string", "default": "mime"},
                "max_rows": {"type": "integer", "default": 100000},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "ledger"],
        },
    },
    {
        "name": "resolve_objet_ref",
        "description": "Resolve one sha256 objet reference to safe manifest, local, and external candidates. Read-only; never echoes absolute paths, calls providers, creates URLs, downloads, hashes bytes, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "object_id": {"type": "string", "description": "sha256:<64 lowercase hex> or bare 64 lowercase hex."},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "object_id"],
        },
    },
    {
        "name": "presigned_url_plan",
        "description": "Plan a future provider presigned URL request for an objet. Read-only; never creates URLs, calls providers, reads object bytes, downloads, uploads, retrieves secrets, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "object_id": {"type": "string", "description": "sha256:<64 lowercase hex> or bare 64 lowercase hex."},
                "store_ref": {"type": "string", "description": "Safe external store label/ref, not a URL, path, token, or secret."},
                "operation": {
                    "type": "string",
                    "enum": sorted(archive_services.PRESIGNED_URL_OPERATIONS),
                    "default": "download",
                },
                "ttl_seconds": {
                    "type": "integer",
                    "default": archive_services.PRESIGNED_URL_DEFAULT_TTL_SECONDS,
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "object_id"],
        },
    },
    {
        "name": "project_intake_plan",
        "description": "Plan one staged project folder intake session. Read-only; returns human review questions and never reads bodies, recurses, writes, uploads, drafts, mints, or cleans.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "staged_folder": {"type": "string", "description": "Path to one staged project folder."},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "staged_folder"],
        },
    },
    {
        "name": "project_intake_unpack_queue",
        "description": "Queue top-level staged items for human-guided unpacking. Read-only; returns opaque item refs and never exposes names, reads bodies, hashes, writes, captures, drafts, mints, uploads, or cleans.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "staged_folder": {"type": "string", "description": "Path to one staged project folder."},
                "receipt": {"type": "string", "description": "Optional archive-relative project-intake decisions receipt."},
                "max_items": {"type": "integer", "default": 25},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "staged_folder"],
        },
    },
    {
        "name": "project_intake_unpack_choice",
        "description": "Record one human-confirmed unpack choice. Approval-gated; validates a choice file, completed project-intake receipt, and current opaque queue without exposing staged entry names or local paths.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "choice": {"type": "string", "description": "Path to one reviewed unpack-choice JSON file."},
                "receipt": {"type": "string", "description": "Archive-relative project-intake decisions receipt."},
                "staged_folder": {"type": "string", "description": "Path to one staged project folder."},
                "dry_run": {"type": "boolean", "default": True},
                "approve": {"type": "boolean", "default": False},
                "reviewed_by": {"type": "string", "description": "Reviewer id required when approve is true."},
            },
            "required": ["archive_root", "choice", "receipt", "staged_folder"],
        },
    },
    {
        "name": "project_intake_staging_guide",
        "description": "Show where to stage one project folder before a project intake session. Read-only; never creates folders, moves files, uploads, captures, drafts, mints, or cleans.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "project_slug": {"type": "string", "description": "Lowercase ASCII project slug for the staged folder."},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "project_slug"],
        },
    },
    {
        "name": "project_intake_session_guide",
        "description": "Show the next safe human-guided project intake step. Read-only; never writes decisions, captures, drafts, mints, uploads, cleans, or runs automatically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "project_slug": {"type": "string", "description": "Lowercase ASCII project slug for staging guidance."},
                "staged_folder": {"type": "string", "description": "One staged project folder for a new intake session."},
                "receipt": {"type": "string", "description": "Archive-relative project-intake decisions receipt for a continuing session."},
                "session_id": {"type": "string", "description": "Optional safe session id for a new decision template."},
                "staged_folder_ref": {"type": "string", "description": "Optional non-secret staged folder reference for a new decision template."},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "project_intake_status",
        "description": "Review one project-intake decisions receipt. Read-only; returns checklist coverage and next human-review prompts without echoing answer values.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "receipt": {"type": "string", "description": "Archive-relative project-intake decisions receipt."},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "receipt"],
        },
    },
    {
        "name": "project_intake_next_question",
        "description": "Return the next human-review question for one project intake session. Read-only; never writes decisions, echoes answer values, reads bodies, captures, drafts, mints, uploads, or cleans.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "staged_folder": {"type": "string", "description": "One staged project folder for a new intake session."},
                "receipt": {"type": "string", "description": "Archive-relative project-intake decisions receipt for a continuing session."},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "project_intake_decision_template",
        "description": "Build a next-question project-intake decisions JSON template. Read-only; never fills answers, echoes previous answer values, writes decisions, captures, drafts, mints, uploads, or cleans.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "staged_folder": {"type": "string", "description": "One staged project folder for a new intake session."},
                "receipt": {"type": "string", "description": "Archive-relative project-intake decisions receipt for a continuing session."},
                "session_id": {"type": "string", "description": "Optional safe session id for the template."},
                "staged_folder_ref": {"type": "string", "description": "Optional non-secret staged folder reference for the template."},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "project_intake_item_plan",
        "description": "Preview the source-intake dry-run route for one human-selected project-intake item. Read-only; redacts local paths and never writes, captures, drafts, mints, uploads, or cleans.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string", "description": "Path to the archive root."},
                "receipt": {"type": "string", "description": "Archive-relative project-intake decisions receipt."},
                "local_path": {"type": "string", "description": "One local file selected by the human for item planning."},
                "source_role": {"type": "string", "description": "Optional source role for later draft provenance."},
                "title": {"type": "string", "description": "Optional non-secret human-reviewed title."},
                "mime": {"type": "string", "description": "Optional MIME type."},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "receipt", "local_path"],
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
                "project_intake_receipt": {"type": "string"},
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
        "name": "zettel_objet_links",
        "description": "Preview safe local-client objet link candidates referenced by one zettel. Read-only; never echoes body text, frontmatter values, absolute paths, provider URLs, presigned URLs, object bytes, or writes files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "zettel_id": {"type": "string"},
                "path": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
                "max_refs": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
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
        "name": "zet_projection_plan_check",
        "description": "Read-only dry-run ZET publication/projection plan preview for one local zet. Never publishes, writes receipts, calls providers, or transports.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "zet": {"type": "string"},
                "surface": {"type": "string", "enum": sorted(archive_services.ZET_PROJECTION_SURFACE_KINDS)},
                "visibility": {
                    "type": "string",
                    "enum": sorted(archive_services.ZET_PROJECTION_VISIBILITIES),
                    "default": "unknown",
                },
                "projection_format": {
                    "type": "string",
                    "enum": sorted(archive_services.ZET_PROJECTION_FORMATS),
                    "default": "metadata_only",
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "zet", "surface"],
        },
    },
    {
        "name": "zet_shared_update_record_review_preview",
        "description": "Read-only dry-run review preview for one local ZET shared update record before any renewal action.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "record": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "record"],
        },
    },
    {
        "name": "zet_shared_update_record_review_index",
        "description": "Read-only dry-run index over local archive-contained ZET shared update records before any renewal action.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "records_dir": {"type": "string"},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": archive_services.ZET_SHARED_UPDATE_REVIEW_INDEX_MAX_LIMIT,
                    "default": archive_services.ZET_SHARED_UPDATE_REVIEW_INDEX_MAX_LIMIT,
                },
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "records_dir"],
        },
    },
    {
        "name": "zet_transport_would_plan",
        "description": "Read-only dry-run ZET would-transport plan for one local shared update record. This never transports, creates keys, writes receipts, calls providers, or starts workers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "record": {"type": "string"},
                "method": {"type": "string", "enum": sorted(archive_services.ZET_TRANSPORT_METHODS)},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "record", "method"],
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
        "name": "foreign_block_attestation_review_candidate_plan",
        "description": "Read-only candidate planner for human attestation review from an eligible foreign block quarantine decision.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "case_id": {"type": "string"},
                "expected_decision": {
                    "type": "string",
                    "enum": [archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_DECISION],
                },
                "expected_outcome": {
                    "type": "string",
                    "enum": [archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_OUTCOME],
                },
                "prospective_attestor": {"type": "string"},
                "review_scope": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_SCOPES),
                    "default": "full_human_review",
                },
                "review_note": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "case_id"],
        },
    },
    {
        "name": "record_attestation_review_candidate_check",
        "description": "Read-only dry-run check for a CLI-only foreign block attestation review candidate record write.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "path": {"type": "string"},
                "candidate_plan": {"type": "object"},
                "expected_case_id": {"type": "string"},
                "expected_review_scope": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_SCOPES),
                },
                "expected_attestor": {"type": "string"},
                "review_note": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "foreign_block_attestation_review_candidate_index",
        "description": "Read-only index and consistency check for recorded foreign block attestation review candidates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "case_id": {"type": "string"},
                "review_scope": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_SCOPES | {"all"}),
                    "default": "all",
                },
                "include_receipts": {"type": "boolean", "default": False},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "foreign_block_attestation_statement_draft_preview",
        "description": "Read-only non-binding attestation statement draft preview for one recorded foreign block candidate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "case_id": {"type": "string"},
                "expected_review_scope": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_SCOPES),
                },
                "prospective_attestor": {"type": "string"},
                "statement_style": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_STATEMENT_STYLES),
                    "default": "minimal",
                },
                "review_note": {"type": "string"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root", "case_id"],
        },
    },
    {
        "name": "record_attestation_statement_draft_check",
        "description": "Read-only dry-run check for a CLI-only local attestation statement draft record write.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "path": {"type": "string"},
                "draft_preview": {"type": "object"},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "foreign_block_attestation_statement_draft_review_index",
        "description": "Read-only index and consistency check for recorded foreign block attestation statement drafts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "case_id": {"type": "string"},
                "statement_style": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_STATEMENT_STYLES | {"all"}),
                    "default": "all",
                },
                "review_scope": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_SCOPES | {"all"}),
                    "default": "all",
                },
                "include_receipts": {"type": "boolean", "default": False},
                "dry_run": {"type": "boolean", "default": True},
            },
            "required": ["archive_root"],
        },
    },
    {
        "name": "foreign_block_attestation_statement_draft_decision_preview",
        "description": "Read-only decision-route preview for one recorded foreign block attestation statement draft.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archive_root": {"type": "string"},
                "case_id": {"type": "string"},
                "decision_intent": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_STATEMENT_DRAFT_DECISION_INTENTS),
                    "default": "needs_more_review",
                },
                "reviewer": {"type": "string"},
                "expected_review_scope": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_REVIEW_CANDIDATE_SCOPES),
                },
                "expected_statement_style": {
                    "type": "string",
                    "enum": sorted(archive_services.FOREIGN_BLOCK_ATTESTATION_STATEMENT_STYLES),
                },
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
    configure_stdio_utf8()
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
    if name == "provider_setup_status":
        return tool_provider_setup_status(arguments)
    if name == "object_storage_adapter_readiness_plan":
        return tool_object_storage_adapter_readiness_plan(arguments)
    if name == "object_storage_operation_request_plan":
        return tool_object_storage_operation_request_plan(arguments)
    if name == "human_artifact_store_plan":
        return tool_human_artifact_store_plan(arguments)
    if name == "imap_mailbox_plan":
        return tool_imap_mailbox_plan(arguments)
    if name == "imap_mailbox_operation_request_plan":
        return tool_imap_mailbox_operation_request_plan(arguments)
    if name == "imap_mailbox_adapter_readiness_plan":
        return tool_imap_mailbox_adapter_readiness_plan(arguments)
    if name == "imap_mailbox_selection_plan":
        return tool_imap_mailbox_selection_plan(arguments)
    if name == "imap_mailbox_adapter_audit_plan":
        return tool_imap_mailbox_adapter_audit_plan(arguments)
    if name == "imap_mailbox_adapter_manifest_plan":
        return tool_imap_mailbox_adapter_manifest_plan(arguments)
    if name == "imap_mailbox_adapter_preflight_plan":
        return tool_imap_mailbox_adapter_preflight_plan(arguments)
    if name == "credential_ref_plan":
        return tool_credential_ref_plan(arguments)
    if name == "credential_ref_inventory":
        return tool_credential_ref_inventory(arguments)
    if name == "credential_store_recommendation":
        return tool_credential_store_recommendation(arguments)
    if name == "credential_vault_onboarding_plan":
        return tool_credential_vault_onboarding_plan(arguments)
    if name == "credential_plaintext_migration_plan":
        return tool_credential_plaintext_migration_plan(arguments)
    if name == "credential_policy_check":
        return tool_credential_policy_check(arguments)
    if name == "credential_keepassxc_command_plan":
        return tool_credential_keepassxc_command_plan(arguments)
    if name == "credential_access_broker_plan":
        return tool_credential_access_broker_plan(arguments)
    if name == "credential_access_approval_plan":
        return tool_credential_access_approval_plan(arguments)
    if name == "credential_adapter_readiness_plan":
        return tool_credential_adapter_readiness_plan(arguments)
    if name == "credential_adapter_manifest_plan":
        return tool_credential_adapter_manifest_plan(arguments)
    if name == "credential_adapter_audit_plan":
        return tool_credential_adapter_audit_plan(arguments)
    if name == "zet_surface_prototype_plan":
        return tool_zet_surface_prototype_plan(arguments)
    if name == "prehashed_objet_ledger_preview":
        return tool_prehashed_objet_ledger_preview(arguments)
    if name == "resolve_objet_ref":
        return tool_resolve_objet_ref(arguments)
    if name == "presigned_url_plan":
        return tool_presigned_url_plan(arguments)
    if name == "project_intake_plan":
        return tool_project_intake_plan(arguments)
    if name == "project_intake_unpack_queue":
        return tool_project_intake_unpack_queue(arguments)
    if name == "project_intake_unpack_choice":
        return tool_project_intake_unpack_choice(arguments)
    if name == "project_intake_staging_guide":
        return tool_project_intake_staging_guide(arguments)
    if name == "project_intake_session_guide":
        return tool_project_intake_session_guide(arguments)
    if name == "project_intake_status":
        return tool_project_intake_status(arguments)
    if name == "project_intake_next_question":
        return tool_project_intake_next_question(arguments)
    if name == "project_intake_decision_template":
        return tool_project_intake_decision_template(arguments)
    if name == "project_intake_item_plan":
        return tool_project_intake_item_plan(arguments)
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
    if name == "zettel_objet_links":
        return tool_zettel_objet_links(arguments)
    if name == "block_header_check":
        return tool_block_header_check(arguments)
    if name == "zet_projection_plan_check":
        return tool_zet_projection_plan_check(arguments)
    if name == "zet_shared_update_record_review_preview":
        return tool_zet_shared_update_record_review_preview(arguments)
    if name == "zet_shared_update_record_review_index":
        return tool_zet_shared_update_record_review_index(arguments)
    if name == "zet_transport_would_plan":
        return tool_zet_transport_would_plan(arguments)
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
    if name == "foreign_block_attestation_review_candidate_plan":
        return tool_foreign_block_attestation_review_candidate_plan(arguments)
    if name == "record_attestation_review_candidate_check":
        return tool_record_attestation_review_candidate_check(arguments)
    if name == "foreign_block_attestation_review_candidate_index":
        return tool_foreign_block_attestation_review_candidate_index(arguments)
    if name == "foreign_block_attestation_statement_draft_preview":
        return tool_foreign_block_attestation_statement_draft_preview(arguments)
    if name == "record_attestation_statement_draft_check":
        return tool_record_attestation_statement_draft_check(arguments)
    if name == "foreign_block_attestation_statement_draft_review_index":
        return tool_foreign_block_attestation_statement_draft_review_index(arguments)
    if name == "foreign_block_attestation_statement_draft_decision_preview":
        return tool_foreign_block_attestation_statement_draft_decision_preview(arguments)
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


def tool_provider_setup_status(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("provider_setup_status is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(archive_services.provider_setup_status, archive_root)
    state = str(result.get("status") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"provider_setup_status: {state}.", result)


def tool_object_storage_adapter_readiness_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("object_storage_adapter_readiness_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.object_storage_adapter_readiness_plan,
        archive_root,
        operation=optional_string_arg(arguments, "operation") or "presigned_download",
        provider_ref=optional_string_arg(arguments, "provider_ref"),
        dry_run=True,
    )
    state = str(result.get("readiness_state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"object_storage_adapter_readiness_plan: {state}.", result)


def tool_object_storage_operation_request_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("object_storage_operation_request_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    try:
        ttl_seconds = int(arguments.get("ttl_seconds", archive_services.PRESIGNED_URL_DEFAULT_TTL_SECONDS))
    except (TypeError, ValueError):
        raise ToolError("ttl_seconds must be an integer.")
    result = call_service(
        archive_services.object_storage_operation_request_plan,
        archive_root,
        operation=optional_string_arg(arguments, "operation") or "presigned_download",
        object_id=optional_string_arg(arguments, "object_id"),
        store_ref=optional_string_arg(arguments, "store_ref"),
        ttl_seconds=ttl_seconds,
        provider_ref=optional_string_arg(arguments, "provider_ref"),
        credential_id=optional_string_arg(arguments, "credential_id") or "cred:object-storage",
        credential_ref=optional_string_arg(arguments, "credential_ref"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        provider=optional_string_arg(arguments, "provider"),
        store_kind=optional_string_arg(arguments, "store_kind") or "password_manager",
        adapter_kind=optional_string_arg(arguments, "adapter_kind"),
        approval_decision=optional_string_arg(arguments, "approval_decision") or "needs_review",
        approval_receipt=optional_string_arg(arguments, "approval_receipt"),
        consumer=optional_string_arg(arguments, "consumer") or "wom:adapter:object-storage",
        reviewed_by=optional_string_arg(arguments, "reviewed_by") or "human:pending-review",
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = str(result.get("request_state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"object_storage_operation_request_plan: {state}.", result)


def tool_human_artifact_store_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is False:
        raise ToolError("human_artifact_store_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.human_artifact_store_plan,
        archive_root,
        surface_kind=require_string_arg(arguments, "surface_kind"),
        surface_ref=optional_string_arg(arguments, "surface_ref"),
        role=optional_string_arg(arguments, "role") or archive_services.HUMAN_ARTIFACT_DEFAULT_ROLE,
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"human_artifact_store_plan: {state}.", result)


def tool_imap_mailbox_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("imap_mailbox_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.imap_mailbox_plan,
        archive_root,
        source_id=require_string_arg(arguments, "source_id"),
        provider=optional_string_arg(arguments, "provider") or "generic_imap",
        imap_host=optional_string_arg(arguments, "imap_host"),
        imap_port=arguments.get("imap_port", 993),
        account_ref=require_string_arg(arguments, "account_ref"),
        username_ref=require_string_arg(arguments, "username_ref"),
        auth_mode=optional_string_arg(arguments, "auth_mode") or "app_password_ref",
        app_password_ref=optional_string_arg(arguments, "app_password_ref"),
        oauth_token_ref=optional_string_arg(arguments, "oauth_token_ref"),
        mailbox_ref=optional_string_arg(arguments, "mailbox_ref") or "imap:mailbox:inbox",
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"imap_mailbox_plan: {state}.", result)


def tool_imap_mailbox_operation_request_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("imap_mailbox_operation_request_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    try:
        imap_port = int(arguments.get("imap_port", 993))
    except (TypeError, ValueError):
        raise ToolError("imap_port must be an integer.")
    try:
        max_messages = int(arguments.get("max_messages", archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT))
    except (TypeError, ValueError):
        raise ToolError("max_messages must be an integer.")
    since_days_arg = arguments.get("since_days")
    since_days: int | None = None
    if since_days_arg is not None:
        try:
            since_days = int(since_days_arg)
        except (TypeError, ValueError):
            raise ToolError("since_days must be an integer.")
    result = call_service(
        archive_services.imap_mailbox_operation_request_plan,
        archive_root,
        source_id=require_string_arg(arguments, "source_id"),
        provider=optional_string_arg(arguments, "provider") or "generic_imap",
        imap_host=optional_string_arg(arguments, "imap_host"),
        imap_port=imap_port,
        account_ref=require_string_arg(arguments, "account_ref"),
        username_ref=require_string_arg(arguments, "username_ref"),
        auth_mode=optional_string_arg(arguments, "auth_mode") or "app_password_ref",
        app_password_ref=optional_string_arg(arguments, "app_password_ref"),
        oauth_token_ref=optional_string_arg(arguments, "oauth_token_ref"),
        mailbox_ref=optional_string_arg(arguments, "mailbox_ref") or "imap:mailbox:inbox",
        operation=optional_string_arg(arguments, "operation") or "header_metadata_scan",
        max_messages=max_messages,
        since_days=since_days,
        credential_id=optional_string_arg(arguments, "credential_id") or "cred:mail-source-access",
        credential_ref=optional_string_arg(arguments, "credential_ref"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        credential_provider=optional_string_arg(arguments, "credential_provider"),
        store_kind=optional_string_arg(arguments, "store_kind") or "password_manager",
        adapter_kind=optional_string_arg(arguments, "adapter_kind"),
        approval_decision=optional_string_arg(arguments, "approval_decision") or "needs_review",
        approval_receipt=optional_string_arg(arguments, "approval_receipt"),
        consumer=optional_string_arg(arguments, "consumer") or "wom:adapter:imap-mailbox",
        reviewed_by=optional_string_arg(arguments, "reviewed_by") or "human:pending-review",
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = str(result.get("request_state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"imap_mailbox_operation_request_plan: {state}.", result)


def tool_imap_mailbox_adapter_readiness_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("imap_mailbox_adapter_readiness_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    try:
        imap_port = int(arguments.get("imap_port", 993))
    except (TypeError, ValueError):
        raise ToolError("imap_port must be an integer.")
    try:
        max_messages = int(arguments.get("max_messages", archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT))
    except (TypeError, ValueError):
        raise ToolError("max_messages must be an integer.")
    since_days_arg = arguments.get("since_days")
    since_days: int | None = None
    if since_days_arg is not None:
        try:
            since_days = int(since_days_arg)
        except (TypeError, ValueError):
            raise ToolError("since_days must be an integer.")
    result = call_service(
        archive_services.imap_mailbox_adapter_readiness_plan,
        archive_root,
        source_id=require_string_arg(arguments, "source_id"),
        adapter_id=optional_string_arg(arguments, "adapter_id"),
        provider=optional_string_arg(arguments, "provider") or "generic_imap",
        imap_host=optional_string_arg(arguments, "imap_host"),
        imap_port=imap_port,
        account_ref=require_string_arg(arguments, "account_ref"),
        username_ref=require_string_arg(arguments, "username_ref"),
        auth_mode=optional_string_arg(arguments, "auth_mode") or "app_password_ref",
        app_password_ref=optional_string_arg(arguments, "app_password_ref"),
        oauth_token_ref=optional_string_arg(arguments, "oauth_token_ref"),
        mailbox_ref=optional_string_arg(arguments, "mailbox_ref") or "imap:mailbox:inbox",
        operation=optional_string_arg(arguments, "operation") or "header_metadata_scan",
        max_messages=max_messages,
        since_days=since_days,
        credential_id=optional_string_arg(arguments, "credential_id") or "cred:mail-source-access",
        credential_ref=optional_string_arg(arguments, "credential_ref"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        credential_provider=optional_string_arg(arguments, "credential_provider"),
        store_kind=optional_string_arg(arguments, "store_kind") or "password_manager",
        adapter_kind=optional_string_arg(arguments, "adapter_kind"),
        approval_decision=optional_string_arg(arguments, "approval_decision") or "needs_review",
        approval_receipt=optional_string_arg(arguments, "approval_receipt"),
        consumer=optional_string_arg(arguments, "consumer") or "wom:adapter:imap-mailbox",
        reviewed_by=optional_string_arg(arguments, "reviewed_by") or "human:pending-review",
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = str(result.get("readiness_state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"imap_mailbox_adapter_readiness_plan: {state}.", result)


def tool_imap_mailbox_selection_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("imap_mailbox_selection_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    try:
        imap_port = int(arguments.get("imap_port", 993))
    except (TypeError, ValueError):
        raise ToolError("imap_port must be an integer.")
    try:
        max_messages = int(arguments.get("max_messages", archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT))
    except (TypeError, ValueError):
        raise ToolError("max_messages must be an integer.")
    since_days_arg = arguments.get("since_days")
    since_days: int | None = None
    if since_days_arg is not None:
        try:
            since_days = int(since_days_arg)
        except (TypeError, ValueError):
            raise ToolError("since_days must be an integer.")
    result = call_service(
        archive_services.imap_mailbox_selection_plan,
        archive_root,
        source_id=require_string_arg(arguments, "source_id"),
        provider=optional_string_arg(arguments, "provider") or "generic_imap",
        imap_host=optional_string_arg(arguments, "imap_host"),
        imap_port=imap_port,
        account_ref=require_string_arg(arguments, "account_ref"),
        username_ref=require_string_arg(arguments, "username_ref"),
        auth_mode=optional_string_arg(arguments, "auth_mode") or "app_password_ref",
        app_password_ref=optional_string_arg(arguments, "app_password_ref"),
        oauth_token_ref=optional_string_arg(arguments, "oauth_token_ref"),
        mailbox_ref=optional_string_arg(arguments, "mailbox_ref") or "imap:mailbox:inbox",
        operation=optional_string_arg(arguments, "operation") or "header_metadata_scan",
        selection_rule=optional_string_arg(arguments, "selection_rule") or "newest_first",
        selector_id=optional_string_arg(arguments, "selector_id") or "mail-selection:recent-inbox",
        max_messages=max_messages,
        since_days=since_days,
        credential_id=optional_string_arg(arguments, "credential_id") or "cred:mail-source-access",
        credential_ref=optional_string_arg(arguments, "credential_ref"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        credential_provider=optional_string_arg(arguments, "credential_provider"),
        store_kind=optional_string_arg(arguments, "store_kind") or "password_manager",
        adapter_kind=optional_string_arg(arguments, "adapter_kind"),
        approval_decision=optional_string_arg(arguments, "approval_decision") or "needs_review",
        approval_receipt=optional_string_arg(arguments, "approval_receipt"),
        consumer=optional_string_arg(arguments, "consumer") or "wom:adapter:imap-mailbox",
        reviewed_by=optional_string_arg(arguments, "reviewed_by") or "human:pending-review",
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = str(result.get("selection_state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"imap_mailbox_selection_plan: {state}.", result)


def tool_imap_mailbox_adapter_audit_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("imap_mailbox_adapter_audit_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    try:
        imap_port = int(arguments.get("imap_port", 993))
    except (TypeError, ValueError):
        raise ToolError("imap_port must be an integer.")
    try:
        max_messages = int(arguments.get("max_messages", archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT))
    except (TypeError, ValueError):
        raise ToolError("max_messages must be an integer.")
    since_days_arg = arguments.get("since_days")
    since_days: int | None = None
    if since_days_arg is not None:
        try:
            since_days = int(since_days_arg)
        except (TypeError, ValueError):
            raise ToolError("since_days must be an integer.")
    result = call_service(
        archive_services.imap_mailbox_adapter_audit_plan,
        archive_root,
        adapter_id=require_string_arg(arguments, "adapter_id"),
        source_id=require_string_arg(arguments, "source_id"),
        provider=optional_string_arg(arguments, "provider") or "generic_imap",
        imap_host=optional_string_arg(arguments, "imap_host"),
        imap_port=imap_port,
        account_ref=require_string_arg(arguments, "account_ref"),
        username_ref=require_string_arg(arguments, "username_ref"),
        auth_mode=optional_string_arg(arguments, "auth_mode") or "app_password_ref",
        app_password_ref=optional_string_arg(arguments, "app_password_ref"),
        oauth_token_ref=optional_string_arg(arguments, "oauth_token_ref"),
        mailbox_ref=optional_string_arg(arguments, "mailbox_ref") or "imap:mailbox:inbox",
        operation=optional_string_arg(arguments, "operation") or "header_metadata_scan",
        selection_rule=optional_string_arg(arguments, "selection_rule") or "newest_first",
        selector_id=optional_string_arg(arguments, "selector_id") or "mail-selection:recent-inbox",
        max_messages=max_messages,
        since_days=since_days,
        credential_id=optional_string_arg(arguments, "credential_id") or "cred:mail-source-access",
        credential_ref=optional_string_arg(arguments, "credential_ref"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        credential_provider=optional_string_arg(arguments, "credential_provider"),
        store_kind=optional_string_arg(arguments, "store_kind") or "password_manager",
        adapter_kind=optional_string_arg(arguments, "adapter_kind"),
        approval_decision=optional_string_arg(arguments, "approval_decision") or "needs_review",
        approval_receipt=optional_string_arg(arguments, "approval_receipt"),
        consumer=optional_string_arg(arguments, "consumer") or "wom:adapter:imap-mailbox",
        reviewed_by=optional_string_arg(arguments, "reviewed_by") or "human:pending-review",
        platform=optional_string_arg(arguments, "platform") or "windows",
        result_status=optional_string_arg(arguments, "result_status") or "not_run",
        dry_run=True,
    )
    state = str(result.get("audit_state") or ("passed" if result["ok"] else "blocked"))
    receipt = result.get("receipt_preview") if isinstance(result.get("receipt_preview"), dict) else {}
    return tool_success_result(
        f"imap_mailbox_adapter_audit_plan: {state}, result={receipt.get('result_status') or '-'}.",
        result,
    )


def tool_imap_mailbox_adapter_preflight_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("imap_mailbox_adapter_preflight_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    try:
        imap_port = int(arguments.get("imap_port", 993))
    except (TypeError, ValueError):
        raise ToolError("imap_port must be an integer.")
    try:
        max_messages = int(arguments.get("max_messages", archive_services.IMAP_MAILBOX_OPERATION_MAX_MESSAGES_DEFAULT))
    except (TypeError, ValueError):
        raise ToolError("max_messages must be an integer.")
    since_days_arg = arguments.get("since_days")
    since_days: int | None = None
    if since_days_arg is not None:
        try:
            since_days = int(since_days_arg)
        except (TypeError, ValueError):
            raise ToolError("since_days must be an integer.")
    result = call_service(
        archive_services.imap_mailbox_adapter_preflight_plan,
        archive_root,
        adapter_id=require_string_arg(arguments, "adapter_id"),
        source_id=require_string_arg(arguments, "source_id"),
        provider=optional_string_arg(arguments, "provider") or "generic_imap",
        imap_host=optional_string_arg(arguments, "imap_host"),
        imap_port=imap_port,
        account_ref=require_string_arg(arguments, "account_ref"),
        username_ref=require_string_arg(arguments, "username_ref"),
        auth_mode=optional_string_arg(arguments, "auth_mode") or "app_password_ref",
        app_password_ref=optional_string_arg(arguments, "app_password_ref"),
        oauth_token_ref=optional_string_arg(arguments, "oauth_token_ref"),
        mailbox_ref=optional_string_arg(arguments, "mailbox_ref") or "imap:mailbox:inbox",
        operation=optional_string_arg(arguments, "operation") or "header_metadata_scan",
        selection_rule=optional_string_arg(arguments, "selection_rule") or "newest_first",
        selector_id=optional_string_arg(arguments, "selector_id") or "mail-selection:recent-inbox",
        max_messages=max_messages,
        since_days=since_days,
        credential_id=optional_string_arg(arguments, "credential_id") or "cred:mail-source-access",
        credential_ref=optional_string_arg(arguments, "credential_ref"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        credential_provider=optional_string_arg(arguments, "credential_provider"),
        store_kind=optional_string_arg(arguments, "store_kind") or "password_manager",
        adapter_kind=optional_string_arg(arguments, "adapter_kind"),
        approval_decision=optional_string_arg(arguments, "approval_decision") or "needs_review",
        approval_receipt=optional_string_arg(arguments, "approval_receipt"),
        consumer=optional_string_arg(arguments, "consumer") or "wom:adapter:imap-mailbox",
        reviewed_by=optional_string_arg(arguments, "reviewed_by") or "human:pending-review",
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = str(result.get("preflight_state") or ("passed" if result["ok"] else "blocked"))
    gate = result.get("gate_summary") if isinstance(result.get("gate_summary"), dict) else {}
    return tool_success_result(
        f"imap_mailbox_adapter_preflight_plan: {state}, request={gate.get('request_state') or '-'}.",
        result,
    )


def tool_imap_mailbox_adapter_manifest_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("imap_mailbox_adapter_manifest_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    providers_arg = arguments.get("providers")
    operations_arg = arguments.get("operations")
    selection_rules_arg = arguments.get("selection_rules")
    result = call_service(
        archive_services.imap_mailbox_adapter_manifest_plan,
        archive_root,
        adapter_id=require_string_arg(arguments, "adapter_id"),
        providers=[str(item) for item in providers_arg] if isinstance(providers_arg, list) else None,
        operations=[str(item) for item in operations_arg] if isinstance(operations_arg, list) else None,
        selection_rules=[str(item) for item in selection_rules_arg] if isinstance(selection_rules_arg, list) else None,
        consumer=optional_string_arg(arguments, "consumer") or "wom:adapter:imap-mailbox",
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    manifest = result.get("manifest_preview") if isinstance(result.get("manifest_preview"), dict) else {}
    return tool_success_result(
        f"imap_mailbox_adapter_manifest_plan: {state}, adapter={manifest.get('adapter_id') or '-'}.",
        result,
    )


def tool_credential_ref_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("credential_ref_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.credential_ref_plan,
        archive_root,
        credential_id=require_string_arg(arguments, "credential_id"),
        credential_ref=require_string_arg(arguments, "credential_ref"),
        credential_kind=optional_string_arg(arguments, "credential_kind") or "generic_secret",
        purpose=optional_string_arg(arguments, "purpose"),
        provider=optional_string_arg(arguments, "provider"),
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"credential_ref_plan: {state}.", result)


def tool_credential_ref_inventory(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("credential_ref_inventory is read-only and requires dry-run.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.credential_ref_inventory,
        archive_root,
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"credential_ref_inventory: {state}, {result['credential_count']} ref(s).", result)


def tool_credential_store_recommendation(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("credential_store_recommendation is read-only and requires dry-run.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.credential_store_recommendation,
        archive_root,
        scenario=require_string_arg(arguments, "scenario"),
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    primary = result.get("primary_recommendation") if isinstance(result.get("primary_recommendation"), dict) else {}
    return tool_success_result(
        f"credential_store_recommendation: {state}, primary={primary.get('store_id') or '-'}.",
        result,
    )


def tool_credential_vault_onboarding_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("credential_vault_onboarding_plan is read-only and requires dry-run.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.credential_vault_onboarding_plan,
        archive_root,
        scenario=require_string_arg(arguments, "scenario"),
        store_id=optional_string_arg(arguments, "store_id") or "recommended",
        credential_id=optional_string_arg(arguments, "credential_id"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        provider=optional_string_arg(arguments, "provider"),
        action_kind=optional_string_arg(arguments, "action_kind"),
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    store = result.get("selected_store") if isinstance(result.get("selected_store"), dict) else {}
    return tool_success_result(
        f"credential_vault_onboarding_plan: {state}, store={store.get('store_id') or '-'}.",
        result,
    )


def tool_credential_plaintext_migration_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("credential_plaintext_migration_plan is read-only and requires dry-run.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.credential_plaintext_migration_plan,
        archive_root,
        source_label=require_string_arg(arguments, "source_label"),
        credential_id=require_string_arg(arguments, "credential_id"),
        target_store_id=optional_string_arg(arguments, "target_store_id") or "recommended",
        scenario=optional_string_arg(arguments, "scenario") or "personal_local_first",
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        provider=optional_string_arg(arguments, "provider"),
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    target = result.get("target") if isinstance(result.get("target"), dict) else {}
    return tool_success_result(
        f"credential_plaintext_migration_plan: {state}, target={target.get('selected_store_id') or '-'}.",
        result,
    )


def tool_credential_policy_check(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("credential_policy_check is read-only and requires dry-run.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.credential_policy_check,
        archive_root,
        credential_id=require_string_arg(arguments, "credential_id"),
        credential_ref=optional_string_arg(arguments, "credential_ref"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        provider=optional_string_arg(arguments, "provider"),
        action_kind=require_string_arg(arguments, "action_kind"),
        approval_decision=optional_string_arg(arguments, "approval_decision") or "needs_review",
        store_kind=optional_string_arg(arguments, "store_kind") or "password_manager",
        adapter_kind=optional_string_arg(arguments, "adapter_kind"),
        operation=optional_string_arg(arguments, "operation"),
        consumer=optional_string_arg(arguments, "consumer"),
        reviewed_by=optional_string_arg(arguments, "reviewed_by"),
        platform=optional_string_arg(arguments, "platform") or "windows",
        approval_receipt=optional_string_arg(arguments, "approval_receipt"),
        dry_run=True,
    )
    return tool_success_result(
        f"credential_policy_check: {result.get('policy_result') or '-'}.",
        result,
    )


def tool_credential_keepassxc_command_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("credential_keepassxc_command_plan is read-only and requires dry-run.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.credential_keepassxc_command_plan,
        archive_root,
        credential_id=require_string_arg(arguments, "credential_id"),
        credential_ref=optional_string_arg(arguments, "credential_ref"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        provider=optional_string_arg(arguments, "provider"),
        action_kind=optional_string_arg(arguments, "action_kind") or "plaintext_secret_migration",
        operation=optional_string_arg(arguments, "operation") or "plaintext_secret_migration",
        approval_receipt=require_string_arg(arguments, "approval_receipt"),
        entry_label=require_string_arg(arguments, "entry_label"),
        group_label=optional_string_arg(arguments, "group_label"),
        database_ref=optional_string_arg(arguments, "database_ref") or "keepassxc:human-selected-database",
        consumer=optional_string_arg(arguments, "consumer") or "wom:adapter:keepassxc",
        reviewed_by=optional_string_arg(arguments, "reviewed_by"),
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    summary = result.get("policy_check_summary") if isinstance(result.get("policy_check_summary"), dict) else {}
    return tool_success_result(
        f"credential_keepassxc_command_plan: {state}, policy={summary.get('policy_result') or '-'}.",
        result,
    )


def tool_credential_access_broker_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("credential_access_broker_plan is read-only and requires dry-run.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.credential_access_broker_plan,
        archive_root,
        credential_id=require_string_arg(arguments, "credential_id"),
        credential_ref=optional_string_arg(arguments, "credential_ref"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        provider=optional_string_arg(arguments, "provider"),
        action_kind=require_string_arg(arguments, "action_kind"),
        store_kind=optional_string_arg(arguments, "store_kind") or "password_manager",
        consumer=optional_string_arg(arguments, "consumer") or "wom_local_adapter",
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    request = result.get("broker_request") if isinstance(result.get("broker_request"), dict) else {}
    return tool_success_result(
        f"credential_access_broker_plan: {state}, action={request.get('action_kind') or '-'}.",
        result,
    )


def tool_credential_access_approval_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("credential_access_approval_plan is read-only and requires dry-run.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.credential_access_approval_plan,
        archive_root,
        credential_id=require_string_arg(arguments, "credential_id"),
        credential_ref=optional_string_arg(arguments, "credential_ref"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        provider=optional_string_arg(arguments, "provider"),
        action_kind=require_string_arg(arguments, "action_kind"),
        decision=optional_string_arg(arguments, "decision") or "needs_review",
        store_kind=optional_string_arg(arguments, "store_kind") or "password_manager",
        consumer=optional_string_arg(arguments, "consumer") or "wom_local_adapter",
        reviewed_by=optional_string_arg(arguments, "reviewed_by") or "human:pending-review",
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(
        f"credential_access_approval_plan: {state}, decision={result.get('decision') or '-'}.",
        result,
    )


def tool_credential_adapter_readiness_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("credential_adapter_readiness_plan is read-only and requires dry-run.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.credential_adapter_readiness_plan,
        archive_root,
        adapter_kind=require_string_arg(arguments, "adapter_kind"),
        operation=require_string_arg(arguments, "operation"),
        credential_id=require_string_arg(arguments, "credential_id"),
        credential_ref=optional_string_arg(arguments, "credential_ref"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        provider=optional_string_arg(arguments, "provider"),
        action_kind=require_string_arg(arguments, "action_kind"),
        store_kind=optional_string_arg(arguments, "store_kind"),
        consumer=optional_string_arg(arguments, "consumer"),
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    adapter = result.get("adapter") if isinstance(result.get("adapter"), dict) else {}
    return tool_success_result(
        f"credential_adapter_readiness_plan: {state}, adapter={adapter.get('adapter_kind') or '-'}.",
        result,
    )


def tool_credential_adapter_manifest_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("credential_adapter_manifest_plan is read-only and requires dry-run.")
    archive_root = require_path_arg(arguments, "archive_root")
    operations = arguments.get("operations")
    if operations is not None and not isinstance(operations, list):
        raise ToolError("operations must be an array when provided.")
    result = call_service(
        archive_services.credential_adapter_manifest_plan,
        archive_root,
        adapter_id=require_string_arg(arguments, "adapter_id"),
        adapter_kind=require_string_arg(arguments, "adapter_kind"),
        operations=[str(item) for item in operations] if isinstance(operations, list) else None,
        store_kind=optional_string_arg(arguments, "store_kind"),
        consumer=optional_string_arg(arguments, "consumer"),
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    manifest = result.get("manifest_preview") if isinstance(result.get("manifest_preview"), dict) else {}
    return tool_success_result(
        f"credential_adapter_manifest_plan: {state}, adapter={manifest.get('adapter_id') or '-'}.",
        result,
    )


def tool_credential_adapter_audit_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("credential_adapter_audit_plan is read-only and requires dry-run.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.credential_adapter_audit_plan,
        archive_root,
        adapter_id=require_string_arg(arguments, "adapter_id"),
        adapter_kind=require_string_arg(arguments, "adapter_kind"),
        operation=require_string_arg(arguments, "operation"),
        credential_id=require_string_arg(arguments, "credential_id"),
        credential_kind=optional_string_arg(arguments, "credential_kind"),
        provider=optional_string_arg(arguments, "provider"),
        action_kind=require_string_arg(arguments, "action_kind"),
        result_status=optional_string_arg(arguments, "result_status") or "not_run",
        store_kind=optional_string_arg(arguments, "store_kind"),
        consumer=optional_string_arg(arguments, "consumer"),
        platform=optional_string_arg(arguments, "platform") or "windows",
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    receipt = result.get("receipt_preview") if isinstance(result.get("receipt_preview"), dict) else {}
    return tool_success_result(
        f"credential_adapter_audit_plan: {state}, result={receipt.get('result_status') or '-'}.",
        result,
    )


def tool_zet_surface_prototype_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("zet_surface_prototype_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.zet_surface_prototype_plan,
        archive_root,
        surface_kind=require_string_arg(arguments, "surface_kind"),
        surface_ref=optional_string_arg(arguments, "surface_ref"),
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"zet_surface_prototype_plan: {state}.", result)


def tool_prehashed_objet_ledger_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("prehashed_objet_ledger_preview is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    ledger = require_path_arg(arguments, "ledger")
    result = call_service(
        archive_services.prehashed_objet_ledger_preview,
        archive_root,
        ledger,
        store_kind=optional_string_arg(arguments, "store_kind") or "generic_content_addressed_store",
        sha256_field=optional_string_arg(arguments, "sha256_field") or "sha256",
        size_field=optional_string_arg(arguments, "size_field") or "bytes",
        mime_field=optional_string_arg(arguments, "mime_field") or "mime",
        dry_run=True,
        max_rows=int(arguments.get("max_rows", 100000)),
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"prehashed_objet_ledger_preview: {state}.", result)


def tool_resolve_objet_ref(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("resolve_objet_ref is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.resolve_objet_ref,
        archive_root,
        object_id=require_string_arg(arguments, "object_id"),
        dry_run=True,
    )
    state = str(result.get("resolution_state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"resolve_objet_ref: {state}.", result)


def tool_presigned_url_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("presigned_url_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    try:
        ttl_seconds = int(arguments.get("ttl_seconds", archive_services.PRESIGNED_URL_DEFAULT_TTL_SECONDS))
    except (TypeError, ValueError):
        raise ToolError("ttl_seconds must be an integer.")
    result = call_service(
        archive_services.presigned_url_plan,
        archive_root,
        object_id=require_string_arg(arguments, "object_id"),
        store_ref=optional_string_arg(arguments, "store_ref"),
        operation=optional_string_arg(arguments, "operation") or "download",
        ttl_seconds=ttl_seconds,
        dry_run=True,
    )
    state = str(result.get("plan_state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"presigned_url_plan: {state}.", result)


def tool_project_intake_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("project_intake_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    staged_folder = require_path_arg(arguments, "staged_folder")
    result = call_service(archive_services.project_intake_plan, archive_root, staged_folder)
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"project_intake_plan: {state}.", result)


def tool_project_intake_unpack_queue(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("project_intake_unpack_queue is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    staged_folder = require_path_arg(arguments, "staged_folder")
    result = call_service(
        archive_services.project_intake_unpack_queue,
        archive_root,
        staged_folder,
        receipt=optional_string_arg(arguments, "receipt"),
        max_items=int(arguments.get("max_items", 25)),
        dry_run=True,
    )
    state = str(result.get("state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"project_intake_unpack_queue: {state}.", result)


def tool_project_intake_unpack_choice(arguments: dict[str, Any]) -> dict[str, Any]:
    dry_run = bool(arguments.get("dry_run", True))
    approve = bool(arguments.get("approve", False))
    archive_root = require_path_arg(arguments, "archive_root")
    choice = require_path_arg(arguments, "choice")
    staged_folder = require_path_arg(arguments, "staged_folder")
    result = call_service(
        archive_services.project_intake_unpack_choice,
        archive_root,
        choice,
        receipt=require_string_arg(arguments, "receipt"),
        staged_folder=staged_folder,
        dry_run=dry_run,
        approve=approve,
        reviewed_by=optional_string_arg(arguments, "reviewed_by"),
    )
    state = "recorded" if result.get("ok") and not result.get("dry_run") else ("ready" if result.get("ok") else "blocked")
    return tool_success_result(f"project_intake_unpack_choice: {state}.", result)


def tool_project_intake_staging_guide(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("project_intake_staging_guide is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.project_intake_staging_guide,
        archive_root,
        project_slug=require_string_arg(arguments, "project_slug"),
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"project_intake_staging_guide: {state}.", result)


def tool_project_intake_session_guide(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("project_intake_session_guide is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    staged_folder_value = optional_string_arg(arguments, "staged_folder")
    staged_folder = require_path_arg({"staged_folder": staged_folder_value}, "staged_folder") if staged_folder_value else None
    result = call_service(
        archive_services.project_intake_session_guide,
        archive_root,
        project_slug=optional_string_arg(arguments, "project_slug"),
        staged_folder=staged_folder,
        receipt=optional_string_arg(arguments, "receipt"),
        session_id=optional_string_arg(arguments, "session_id"),
        staged_folder_ref=optional_string_arg(arguments, "staged_folder_ref"),
        dry_run=True,
    )
    state = str(result.get("state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"project_intake_session_guide: {state}.", result)


def tool_project_intake_status(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("project_intake_status is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    result = call_service(
        archive_services.project_intake_status,
        archive_root,
        require_string_arg(arguments, "receipt"),
        dry_run=True,
    )
    state = str(result.get("readiness", {}).get("status") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"project_intake_status: {state}.", result)


def tool_project_intake_next_question(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("project_intake_next_question is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    staged_folder_value = optional_string_arg(arguments, "staged_folder")
    receipt = optional_string_arg(arguments, "receipt")
    staged_folder = require_path_arg({"staged_folder": staged_folder_value}, "staged_folder") if staged_folder_value else None
    result = call_service(
        archive_services.project_intake_next_question,
        archive_root,
        staged_folder=staged_folder,
        receipt=receipt,
        dry_run=True,
    )
    state = str(result.get("state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"project_intake_next_question: {state}.", result)


def tool_project_intake_decision_template(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("project_intake_decision_template is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    staged_folder_value = optional_string_arg(arguments, "staged_folder")
    receipt = optional_string_arg(arguments, "receipt")
    staged_folder = require_path_arg({"staged_folder": staged_folder_value}, "staged_folder") if staged_folder_value else None
    result = call_service(
        archive_services.project_intake_decision_template,
        archive_root,
        staged_folder=staged_folder,
        receipt=receipt,
        session_id=optional_string_arg(arguments, "session_id"),
        staged_folder_ref=optional_string_arg(arguments, "staged_folder_ref"),
        dry_run=True,
    )
    state = str(result.get("state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"project_intake_decision_template: {state}.", result)


def tool_project_intake_item_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("project_intake_item_plan is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    local_path = require_path_arg(arguments, "local_path")
    result = call_service(
        archive_services.project_intake_item_plan,
        archive_root,
        receipt=require_string_arg(arguments, "receipt"),
        local_path=local_path,
        source_role=optional_string_arg(arguments, "source_role") or archive_services.SOURCE_INTAKE_DEFAULT_ROLE,
        title=optional_string_arg(arguments, "title"),
        mime=optional_string_arg(arguments, "mime"),
        dry_run=True,
    )
    state = str(result.get("state") or ("passed" if result["ok"] else "blocked"))
    return tool_success_result(f"project_intake_item_plan: {state}.", result)


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
        project_intake_receipt=optional_string_arg(arguments, "project_intake_receipt"),
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


def tool_zettel_objet_links(arguments: dict[str, Any]) -> dict[str, Any]:
    if arguments.get("dry_run", True) is not True:
        raise ToolError("zettel_objet_links is dry-run only.")
    archive_root = require_path_arg(arguments, "archive_root")
    zettel_id = optional_string_arg(arguments, "zettel_id")
    relative_path = optional_string_arg(arguments, "path")
    result = call_service(
        archive_services.zettel_objet_links,
        archive_root,
        zettel_id=zettel_id,
        relative_path=relative_path,
        dry_run=True,
        max_refs=int(arguments.get("max_refs", 100)),
    )
    state = "passed" if result.get("ok") else "blocked"
    return tool_success_result(f"zettel_objet_links: {state}, {result['count']} link(s).", result)


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


def tool_zet_projection_plan_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("zet_projection_plan_check is dry-run only.")
    result = call_service(
        archive_services.zet_projection_plan_preview,
        archive_root,
        zet_ref=require_string_arg(arguments, "zet"),
        surface=require_string_arg(arguments, "surface"),
        dry_run=True,
        visibility=optional_string_arg(arguments, "visibility") or "unknown",
        projection_format=optional_string_arg(arguments, "projection_format") or "metadata_only",
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"zet_projection_plan_check: {state}.", result)


def tool_zet_shared_update_record_review_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("zet_shared_update_record_review_preview is dry-run only.")
    result = call_service(
        archive_services.zet_shared_update_record_review_preview,
        archive_root,
        record=require_string_arg(arguments, "record"),
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"zet_shared_update_record_review_preview: {state}.", result)


def tool_zet_shared_update_record_review_index(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("zet_shared_update_record_review_index is dry-run only.")
    limit = arguments.get("limit", archive_services.ZET_SHARED_UPDATE_REVIEW_INDEX_MAX_LIMIT)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ToolError("limit must be an integer between 1 and 100.")
    result = call_service(
        archive_services.zet_shared_update_record_review_index,
        archive_root,
        records_dir=require_string_arg(arguments, "records_dir"),
        dry_run=True,
        limit=limit,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"zet_shared_update_record_review_index: {state}.", result)


def tool_zet_transport_would_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("zet_transport_would_plan is dry-run only.")
    result = call_service(
        archive_services.zet_transport_would_plan,
        archive_root,
        record=require_string_arg(arguments, "record"),
        method=require_string_arg(arguments, "method"),
        dry_run=True,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"zet_transport_would_plan: {state}.", result)


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


def tool_foreign_block_attestation_review_candidate_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_attestation_review_candidate_plan is dry-run only.")
    case_id = require_string_arg(arguments, "case_id")
    expected_decision = optional_string_arg(arguments, "expected_decision")
    expected_outcome = optional_string_arg(arguments, "expected_outcome")
    prospective_attestor = optional_string_arg(arguments, "prospective_attestor")
    review_scope = optional_string_arg(arguments, "review_scope") or "full_human_review"
    review_note = optional_string_arg(arguments, "review_note")
    result = call_service(
        archive_services.foreign_block_attestation_review_candidate_plan,
        archive_root,
        case_id=case_id,
        dry_run=True,
        expected_decision=expected_decision,
        expected_outcome=expected_outcome,
        prospective_attestor=prospective_attestor,
        review_scope=review_scope,
        review_note=review_note,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_attestation_review_candidate_plan: {state}.", result)


def tool_record_attestation_review_candidate_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("record_attestation_review_candidate_check is dry-run only.")
    if arguments.get("approve") is not None:
        raise ToolError("record_attestation_review_candidate_check does not approve or write.")
    candidate_plan = arguments.get("candidate_plan")
    if candidate_plan is not None and not isinstance(candidate_plan, dict):
        raise ToolError("candidate_plan must be a structured object.")
    path = optional_string_arg(arguments, "path")
    expected_case_id = optional_string_arg(arguments, "expected_case_id")
    expected_review_scope = optional_string_arg(arguments, "expected_review_scope")
    expected_attestor = optional_string_arg(arguments, "expected_attestor")
    review_note = optional_string_arg(arguments, "review_note")
    result = call_service(
        archive_services.record_attestation_review_candidate,
        archive_root,
        candidate_plan_path=path,
        candidate_plan=candidate_plan,
        dry_run=True,
        approve=False,
        reviewed_by=None,
        expected_case_id=expected_case_id,
        expected_review_scope=expected_review_scope,
        expected_attestor=expected_attestor,
        review_note=review_note,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"record_attestation_review_candidate_check: {state}.", result)


def tool_foreign_block_attestation_review_candidate_index(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_attestation_review_candidate_index is dry-run only.")
    case_id = optional_string_arg(arguments, "case_id")
    review_scope = optional_string_arg(arguments, "review_scope") or "all"
    include_receipts = bool(arguments.get("include_receipts", False))
    result = call_service(
        archive_services.foreign_block_attestation_review_candidate_index,
        archive_root,
        case_id=case_id,
        review_scope=review_scope,
        include_receipts=include_receipts,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_attestation_review_candidate_index: {state}.", result)


def tool_foreign_block_attestation_statement_draft_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_attestation_statement_draft_preview is dry-run only.")
    case_id = require_string_arg(arguments, "case_id")
    expected_review_scope = optional_string_arg(arguments, "expected_review_scope")
    prospective_attestor = optional_string_arg(arguments, "prospective_attestor")
    statement_style = optional_string_arg(arguments, "statement_style") or "minimal"
    review_note = optional_string_arg(arguments, "review_note")
    result = call_service(
        archive_services.foreign_block_attestation_statement_draft_preview,
        archive_root,
        case_id=case_id,
        dry_run=True,
        expected_review_scope=expected_review_scope,
        prospective_attestor=prospective_attestor,
        statement_style=statement_style,
        review_note=review_note,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_attestation_statement_draft_preview: {state}.", result)


def tool_record_attestation_statement_draft_check(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("record_attestation_statement_draft_check is dry-run only.")
    if arguments.get("approve") is not None:
        raise ToolError("record_attestation_statement_draft_check does not approve or write.")
    draft_preview = arguments.get("draft_preview")
    if draft_preview is not None and not isinstance(draft_preview, dict):
        raise ToolError("draft_preview must be a structured object.")
    path = optional_string_arg(arguments, "path")
    result = call_service(
        archive_services.record_attestation_statement_draft,
        archive_root,
        draft_preview_path=path,
        draft_preview=draft_preview,
        dry_run=True,
        approve=False,
        reviewed_by=None,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"record_attestation_statement_draft_check: {state}.", result)


def tool_foreign_block_attestation_statement_draft_review_index(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_attestation_statement_draft_review_index is dry-run only.")
    case_id = optional_string_arg(arguments, "case_id")
    statement_style = optional_string_arg(arguments, "statement_style") or "all"
    review_scope = optional_string_arg(arguments, "review_scope") or "all"
    include_receipts = bool(arguments.get("include_receipts", False))
    result = call_service(
        archive_services.foreign_block_attestation_statement_draft_review_index,
        archive_root,
        case_id=case_id,
        statement_style=statement_style,
        review_scope=review_scope,
        include_receipts=include_receipts,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_attestation_statement_draft_review_index: {state}.", result)


def tool_foreign_block_attestation_statement_draft_decision_preview(arguments: dict[str, Any]) -> dict[str, Any]:
    archive_root = require_path_arg(arguments, "archive_root")
    if arguments.get("dry_run", True) is not True:
        raise ToolError("foreign_block_attestation_statement_draft_decision_preview is dry-run only.")
    case_id = require_string_arg(arguments, "case_id")
    decision_intent = optional_string_arg(arguments, "decision_intent") or "needs_more_review"
    reviewer = optional_string_arg(arguments, "reviewer")
    expected_review_scope = optional_string_arg(arguments, "expected_review_scope")
    expected_statement_style = optional_string_arg(arguments, "expected_statement_style")
    review_note = optional_string_arg(arguments, "review_note")
    result = call_service(
        archive_services.foreign_block_attestation_statement_draft_decision_preview,
        archive_root,
        case_id=case_id,
        dry_run=True,
        decision_intent=decision_intent,
        reviewer=reviewer,
        expected_review_scope=expected_review_scope,
        expected_statement_style=expected_statement_style,
        review_note=review_note,
    )
    state = "passed" if result["ok"] else "blocked"
    return tool_success_result(f"foreign_block_attestation_statement_draft_decision_preview: {state}.", result)


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
