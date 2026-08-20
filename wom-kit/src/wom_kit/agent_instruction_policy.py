"""Bounded, content-free conflict detection for local AI instruction files.

WOM cannot safely infer policy semantics from arbitrary prose.  This module
therefore reads only known local entrypoints and trusts only an exact
machine-readable HTML-comment header.  Explicit active conflicts block write
work; unmarked prose is reported as unverified and never silently treated as a
resolved policy.

Precedence is fixed, not caller-controlled:

``WOM runtime policy > current project policy > archive-local policy``.

No instruction is executed, rewritten, copied into output, or reflected with a
local path.  Historical/retired policy remains readable evidence but has no
active authority.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Any, Mapping

import yaml


POLICY_SCHEMA_VERSION = "wom-kit/agent-instruction-policy/v0.1"
RESULT_SCHEMA_VERSION = "wom-kit/agent-instruction-policy-inspection/v0.1"
MARKER_START = "<!-- wom-agent-policy\n"
MARKER_END = "\n-->"
MAX_INSTRUCTION_BYTES = 256 * 1024
MAX_MARKER_BYTES = 16 * 1024
MAX_DIRECTIVES = 64

_POLICY_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{0,95}$")
_DIRECTIVE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_VALUES = {
    "required",
    "forbidden",
    "enabled",
    "disabled",
    "read_only",
    "retired",
    "advisory",
}
_STATUSES = {"active", "retired", "historical"}
_ROLES = {"project_current", "archive_local"}

_RUNTIME_DIRECTIVES = {
    "direct_archive_write": "forbidden",
    "exact_human_approval": "required",
    "external_root_gc": "forbidden",
    "instruction_auto_rewrite": "forbidden",
}


class AgentInstructionPolicyError(RuntimeError):
    _CODES = {
        "agent_instruction_archive_invalid",
        "agent_instruction_project_root_not_bound",
        "agent_instruction_entry_unsafe",
        "agent_instruction_entry_unavailable",
        "agent_instruction_policy_invalid",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "agent_instruction_policy_invalid"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"AgentInstructionPolicyError({self.code!r})"


def _fail(code: str) -> AgentInstructionPolicyError:
    return AgentInstructionPolicyError(code)


def _is_reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _safe_root(path: Path, *, archive: bool) -> Path:
    try:
        resolved = path.resolve(strict=True)
        info = os.lstat(resolved)
    except (OSError, RuntimeError, ValueError):
        raise _fail(
            "agent_instruction_archive_invalid"
            if archive
            else "agent_instruction_project_root_not_bound"
        ) from None
    if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise _fail(
            "agent_instruction_archive_invalid"
            if archive
            else "agent_instruction_project_root_not_bound"
        )
    if archive:
        marker = resolved / "archive.yml"
        try:
            marker_info = os.lstat(marker)
        except OSError:
            raise _fail("agent_instruction_archive_invalid") from None
        if _is_reparse(marker_info) or not stat.S_ISREG(marker_info.st_mode):
            raise _fail("agent_instruction_archive_invalid")
    return resolved


def _bound_project_root(archive_root: Path, project_root: Path | str | None) -> Path:
    expected = archive_root.parent
    if project_root is None:
        return _safe_root(expected, archive=False)
    candidate = _safe_root(Path(project_root), archive=False)
    try:
        if not os.path.samefile(candidate, expected):
            raise _fail("agent_instruction_project_root_not_bound")
    except OSError:
        raise _fail("agent_instruction_project_root_not_bound") from None
    return candidate


def _read_known_entry(path: Path) -> tuple[bytes | None, str]:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None, "missing"
    except OSError:
        return None, "unavailable"
    if _is_reparse(info) or not stat.S_ISREG(info.st_mode):
        return None, "unsafe"
    if info.st_size > MAX_INSTRUCTION_BYTES:
        return None, "oversized"
    try:
        raw = path.read_bytes()
    except OSError:
        return None, "unavailable"
    if len(raw) != info.st_size or len(raw) > MAX_INSTRUCTION_BYTES:
        return None, "unstable"
    return raw, "read"


def _parse_policy(raw: bytes, *, role: str) -> tuple[dict[str, Any] | None, str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        return None, "invalid_utf8"
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith(MARKER_START):
        return None, "marker_missing"
    end = text.find(MARKER_END, len(MARKER_START))
    if end < 0 or end > MAX_MARKER_BYTES:
        return None, "marker_invalid"
    marker = text[len(MARKER_START) : end]
    try:
        parsed = yaml.safe_load(marker)
    except yaml.YAMLError:
        return None, "marker_invalid"
    if not isinstance(parsed, Mapping):
        return None, "marker_invalid"
    document = dict(parsed)
    if set(document) != {
        "schema_version",
        "policy_id",
        "policy_version",
        "status",
        "scope_role",
        "directives",
    }:
        return None, "marker_invalid"
    if document.get("schema_version") != POLICY_SCHEMA_VERSION:
        return None, "marker_invalid"
    if (
        type(document.get("policy_id")) is not str
        or _POLICY_ID_RE.fullmatch(document["policy_id"]) is None
        or type(document.get("policy_version")) is not int
        or document["policy_version"] < 1
        or document["policy_version"] > 1_000_000
        or document.get("status") not in _STATUSES
        or document.get("scope_role") != role
    ):
        return None, "marker_invalid"
    directives = document.get("directives")
    if not isinstance(directives, Mapping) or len(directives) > MAX_DIRECTIVES:
        return None, "marker_invalid"
    normalized: dict[str, str] = {}
    for key, value in directives.items():
        if (
            type(key) is not str
            or _DIRECTIVE_RE.fullmatch(key) is None
            or type(value) is not str
            or value not in _VALUES
        ):
            return None, "marker_invalid"
        normalized[key] = value
    document["directives"] = dict(sorted(normalized.items()))
    return document, "valid"


def inspect_agent_instruction_policies(
    archive_root: Path | str,
    *,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Inspect two exact entrypoints without echoing paths or instruction text."""

    archive = _safe_root(Path(archive_root), archive=True)
    project = _bound_project_root(archive, project_root)
    candidates = (
        ("project_current", project / "AGENTS.md", 200),
        ("archive_local", archive / "AGENTS.md", 100),
    )
    sources: list[dict[str, Any]] = [
        {
            "role": "wom_runtime",
            "status": "active",
            "marker_status": "built_in",
            "policy_id": "wom_runtime_v0400",
            "policy_version": 1,
            "content_sha256": None,
            "directive_count": len(_RUNTIME_DIRECTIVES),
            "path_echoed": False,
            "instruction_text_echoed": False,
        }
    ]
    active: list[tuple[str, int, Mapping[str, str]]] = [
        ("wom_runtime", 300, _RUNTIME_DIRECTIVES)
    ]
    warnings: list[str] = []
    blockers: list[str] = []
    unverified_present = 0

    for role, path, priority in candidates:
        raw, read_status = _read_known_entry(path)
        if raw is None:
            sources.append(
                {
                    "role": role,
                    "status": "missing" if read_status == "missing" else "unreadable",
                    "marker_status": "not_checked",
                    "policy_id": None,
                    "policy_version": None,
                    "content_sha256": None,
                    "directive_count": 0,
                    "path_echoed": False,
                    "instruction_text_echoed": False,
                }
            )
            if read_status != "missing":
                blockers.append("agent_instruction_entry_unsafe")
            continue
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        policy, marker_status = _parse_policy(raw, role=role)
        if policy is None:
            unverified_present += 1
            sources.append(
                {
                    "role": role,
                    "status": "unverified",
                    "marker_status": marker_status,
                    "policy_id": None,
                    "policy_version": None,
                    "content_sha256": digest,
                    "directive_count": 0,
                    "path_echoed": False,
                    "instruction_text_echoed": False,
                }
            )
            warnings.append("agent_instruction_policy_unverified")
            continue
        sources.append(
            {
                "role": role,
                "status": policy["status"],
                "marker_status": "valid",
                "policy_id": policy["policy_id"],
                "policy_version": policy["policy_version"],
                "content_sha256": digest,
                "directive_count": len(policy["directives"]),
                "path_echoed": False,
                "instruction_text_echoed": False,
            }
        )
        if policy["status"] == "active":
            active.append((role, priority, policy["directives"]))
        else:
            warnings.append("retired_or_historical_instruction_policy_present")

    directive_rows: list[dict[str, Any]] = []
    conflict_keys: list[str] = []
    all_keys = sorted({key for _role, _priority, directives in active for key in directives})
    for key in all_keys:
        declarations = [
            (priority, role, directives[key])
            for role, priority, directives in active
            if key in directives
        ]
        declarations.sort(reverse=True)
        selected_priority, selected_role, selected_value = declarations[0]
        values = {value for _priority, _role, value in declarations}
        conflict = len(values) > 1
        if conflict:
            conflict_keys.append(key)
        directive_rows.append(
            {
                "directive": key,
                "selected_value": selected_value,
                "selected_source_role": selected_role,
                "selected_priority": selected_priority,
                "active_declaration_count": len(declarations),
                "conflict": conflict,
            }
        )
    if conflict_keys:
        blockers.append("active_agent_instruction_policy_conflict")
    if unverified_present > 1:
        blockers.append("multiple_unverified_agent_instruction_sources")

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    safe_to_continue_reads = "agent_instruction_entry_unsafe" not in blockers
    write_actions_blocked = bool(blockers)
    status = "conflict" if conflict_keys else ("unverified" if unverified_present else "resolved")
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "ok": not blockers,
        "lifecycle_action": "agent_instruction_policy_inspection",
        "status": status,
        "precedence": ["wom_runtime", "project_current", "archive_local"],
        "sources": sources,
        "resolved_directives": directive_rows,
        "conflict_directive_count": len(conflict_keys),
        "unverified_source_count": unverified_present,
        "safe_to_continue_reads": safe_to_continue_reads,
        "write_actions_blocked": write_actions_blocked,
        "auto_rewrite_performed": False,
        "instruction_text_executed": False,
        "instruction_text_echoed": False,
        "local_paths_echoed": False,
        "next_safe_actions": [
            "mark current instruction files with wom-agent-policy metadata",
            "retire obsolete policy explicitly instead of deleting history",
            "resolve every active directive conflict before archive writes",
        ],
        "blockers": blockers,
        "warnings": warnings,
    }


__all__ = [
    "AgentInstructionPolicyError",
    "MARKER_END",
    "MARKER_START",
    "POLICY_SCHEMA_VERSION",
    "RESULT_SCHEMA_VERSION",
    "inspect_agent_instruction_policies",
]
