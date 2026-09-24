"""Build one reviewed Notion page recovery request from a simple page list.

Letters 142, 148 and 156 could not produce a single recovery request: the
request needs a scope binding per group (credential id, workspace fingerprint,
authenticated scope receipt digest, revision) that no command produced. The
operator now writes only a private JSONL list of `{"page_id", "group"}` rows
and names which adopted credential serves each group; the builder takes the
scope bindings from the authenticated credential listing and writes the
request under the ignored `profiles/local/notion-page-recovery/` folder.

The builder reads no Notion data and calls no provider. Page ids, paths and
credential values are never echoed. The request it writes is a planning
file; running it still needs `notion-page-recovery --approve`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from .notion_page_recovery import MAX_REQUEST_ITEMS, REQUEST_SCHEMA

BUILD_SCHEMA = "wom-kit/notion-page-recovery-request-build/v0.1"
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}$")
_GROUP_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
_UUID_HEX_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def _page_uuid(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    compact = value.strip().replace("-", "")
    if not _UUID_HEX_RE.fullmatch(compact):
        return None
    return str(uuid.UUID(hex=compact.lower()))


def _blocked(codes: list[str], **extra: Any) -> dict[str, Any]:
    return {
        "schema": BUILD_SCHEMA,
        "ok": False,
        "state": "blocked",
        "blockers": sorted(set(codes)),
        "writes": 0,
        "provider_calls": 0,
        "privacy_guards": {"page_ids_echoed": False, "paths_echoed": False, "secret_values_echoed": False},
        **extra,
    }


def build_request(
    archive_id: str,
    pages_text: str,
    group_credentials: Mapping[str, str],
    credentials: list[Mapping[str, Any]],
    *,
    batch_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return (request, public summary). The request is None when blocked."""

    blockers: list[str] = []
    if not _SAFE_ID_RE.fullmatch(batch_id or ""):
        blockers.append("notion_request_batch_id_invalid")
    if not group_credentials:
        blockers.append("notion_request_group_mapping_required")
    for group in group_credentials:
        if not _GROUP_RE.fullmatch(group):
            blockers.append("notion_request_group_name_invalid")
    by_credential = {
        str(row.get("credential_id")): row
        for row in credentials
        if isinstance(row, Mapping) and row.get("provider") == "notion"
    }
    groups: list[dict[str, Any]] = []
    credential_state: dict[str, str] = {}
    for group, credential_id in sorted(group_credentials.items()):
        row = by_credential.get(credential_id)
        scope = row.get("scope_binding") if isinstance(row, Mapping) else None
        if row is None or not isinstance(scope, Mapping):
            credential_state[group] = "credential_not_found"
            blockers.append("notion_request_credential_not_found")
            continue
        if scope.get("persisted") is not True or scope.get("workspace_evidence_verified") is not True:
            credential_state[group] = "credential_not_ready"
            blockers.append("notion_request_credential_not_ready")
            continue
        credential_state[group] = "ready"
        groups.append({"group_id": group, "expected_count": 0, "scope_binding": dict(scope)})

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    counts = {group: 0 for group in group_credentials}
    for number, line in enumerate(pages_text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            blockers.append("notion_request_page_line_invalid")
            continue
        if not isinstance(row, dict) or set(row) - {"page_id", "group"}:
            blockers.append("notion_request_page_line_invalid")
            continue
        page_id = _page_uuid(row.get("page_id"))
        group = row.get("group")
        if page_id is None:
            blockers.append("notion_request_page_id_invalid")
            continue
        if group not in counts:
            blockers.append("notion_request_page_group_unmapped")
            continue
        if page_id in seen:
            continue  # the same page listed twice is recovered once
        seen.add(page_id)
        counts[group] += 1
        items.append({"item_id": f"page-{len(items) + 1:04d}", "group_id": group, "page_id": page_id})
    if not items:
        blockers.append("notion_request_no_pages")
    if len(items) > MAX_REQUEST_ITEMS:
        blockers.append("notion_request_too_many_pages")
    for group_entry in groups:
        group_entry["expected_count"] = counts[group_entry["group_id"]]
    groups = [entry for entry in groups if entry["expected_count"] > 0]
    if any(counts[group] == 0 for group in counts):
        blockers.append("notion_request_group_without_pages")

    summary = {
        "schema": BUILD_SCHEMA,
        "page_count": len(items),
        "group_counts": dict(sorted(counts.items())),
        "credential_state": dict(sorted(credential_state.items())),
        "provider_calls": 0,
        "privacy_guards": {"page_ids_echoed": False, "paths_echoed": False, "secret_values_echoed": False},
    }
    if "notion_request_credential_not_ready" in blockers:
        # v0.4.41: the adopted credential becomes ready once its workspace
        # default is recorded (one exact approval; labels only).
        summary["next_safe_actions"] = [
            "archive credential-lifecycle <archive-root> --workspace-fingerprint <sha256> "
            "--default-credential-id <credential-id> --dry-run",
            "then the same command with --approve --reviewed-by <you>",
        ]
    if blockers:
        return None, {**_blocked(blockers), **summary}
    request = {
        "schema": REQUEST_SCHEMA,
        "batch_id": batch_id,
        "archive_id": archive_id,
        "expected_item_count": len(items),
        "groups": groups,
        "items": items,
    }
    raw = json.dumps(request, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return request, {
        **summary,
        "ok": True,
        "state": "ready",
        "request_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "blockers": [],
    }


def write_request(target: Path, request: Mapping[str, Any]) -> None:
    """Create the request file; never overwrite an existing one."""

    raw = (json.dumps(request, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    try:
        os.write(descriptor, raw)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
