"""Content-free Git backup attention for session-start and evidence results.

v0.4.32 (beta letter 164 ⑥): an archive whose contract names GitHub as an
external backup lane went three weeks with hundreds of changes only on the
local disk, and nothing WOM printed said so. This module answers exactly one
question at every session start, every backup-evidence read and every
work-session create/claim: *is there local work that Git does not yet hold,
and how old is the newest commit the remote is known to have?*

Boundaries, all deliberate:

- **Counts and ages only.** No path, branch name, remote URL, commit subject,
  author or hash ever leaves this module. A count is a count of records;
  an age is whole days.
- **Local Git only, never the network.** ``@{upstream}`` is the cached
  remote-tracking ref. "Remote tip is n days old" means the newest commit
  the local clone *knows* the remote has; it is not proof the remote still
  holds it, which is why the backup-evidence GitHub lane stays unverified.
- **Bounded and fail-quiet.** One shared time budget covers every probe; an
  unavailable probe degrades to ``None`` with its fixed failure kind, and a
  missing or unsafe Git executable degrades to ``state: git_unavailable``.
  The host command's own result is never turned into a failure by this block.
- **Read-only.** ``--no-optional-locks`` and the pinned-executable safety
  flags from :mod:`git_backup_plan` are reused verbatim; no hook, attribute
  file or exclude file is consulted, nothing is written.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from . import archive_services
from . import git_backup_plan

GIT_BACKUP_ATTENTION_SCHEMA = "wom-kit/git-backup-attention/v1"
GIT_BACKUP_ATTENTION_BUDGET_SECONDS = 8.0
GIT_BACKUP_ATTENTION_PROBE_SECONDS = 3.0
GIT_BACKUP_ATTENTION_STATUS_SECONDS = 6.0
GIT_BACKUP_ATTENTION_MAX_STATUS_BYTES = 64 * 1024 * 1024
GIT_BACKUP_ATTENTION_STALE_DAYS = 7
GIT_BACKUP_ATTENTION_NEXT_COMMAND = (
    "archive git-backup-plan <archive-root> --dry-run --format json"
)
GIT_BACKUP_ATTENTION_STATES = (
    "observed",
    "not_a_repository",
    "git_unavailable",
    "unavailable",
)
GIT_BACKUP_ATTENTION_CODES = (
    "uncommitted_changes_present",
    "uncommitted_change_count_unavailable",
    "commits_not_pushed",
    "upstream_missing",
    "remote_tip_older_than_7_days",
    "last_commit_older_than_7_days",
    "head_unborn",
)
GIT_BACKUP_ATTENTION_UNAVAILABLE_SUMMARY = (
    "Git backup attention could not be observed; run the read-only git-backup-plan dry-run before assuming anything is backed up."
)
GIT_BACKUP_ATTENTION_KEYS = frozenset(
    {
        "schema",
        "state",
        "reason_code",
        "repository_inspected",
        "repository_scope",
        "head_state",
        "uncommitted_change_count",
        "uncommitted_change_count_state",
        "untracked_count",
        "tracked_change_count",
        "last_commit_age_days",
        "upstream_state",
        "ahead_count",
        "behind_count",
        "remote_tip_age_days",
        "attention",
        "review_recommended",
        "human_summary",
        "next_command",
        "probes",
        "probe_budget_seconds",
        "network_checked",
        "remote_state_is_proof",
        "paths_branches_or_messages_echoed",
    }
)


def _days_since(unix_seconds: int, *, now: float) -> int:
    return max(0, int((now - float(unix_seconds)) // 86400))


def _count_status_records(raw: bytes) -> tuple[int, int, int] | None:
    """Count porcelain v1 ``-z`` records: (all, untracked, tracked changes).

    A rename or copy record carries a second NUL-terminated field (the old
    path); it is consumed with its record so the count is of changes, not of
    fields. Nothing about the fields is retained.
    """

    if not raw:
        return 0, 0, 0
    fields = raw.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    total = untracked = tracked = 0
    index = 0
    while index < len(fields):
        field = fields[index]
        if len(field) < 3 or field[2:3] != b" ":
            return None
        status = field[:2]
        if b"R" in status or b"C" in status:
            index += 1
            if index >= len(fields):
                return None
        total += 1
        if status == b"??":
            untracked += 1
        else:
            tracked += 1
        index += 1
    return total, untracked, tracked


def _same_directory(left: str, right: Path) -> bool:
    try:
        left_resolved = Path(left).resolve()
        right_resolved = right.resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    return os.path.normcase(str(left_resolved)) == os.path.normcase(str(right_resolved))


def git_backup_attention(archive_root: Path | str) -> dict[str, Any]:
    """Observe the local Git backup gap of ``archive_root`` without echoing anything private.

    Never raises for an observation failure; the returned block always has
    :data:`GIT_BACKUP_ATTENTION_KEYS` and a fixed ``state``.
    """

    now = time.time()
    deadline = time.monotonic() + GIT_BACKUP_ATTENTION_BUDGET_SECONDS
    probes: list[dict[str, Any]] = []
    block: dict[str, Any] = {
        "schema": GIT_BACKUP_ATTENTION_SCHEMA,
        "state": "unavailable",
        "reason_code": "git_backup_attention_unavailable",
        "repository_inspected": False,
        "repository_scope": None,
        "head_state": None,
        "uncommitted_change_count": None,
        "uncommitted_change_count_state": "unavailable",
        "untracked_count": None,
        "tracked_change_count": None,
        "last_commit_age_days": None,
        "upstream_state": None,
        "ahead_count": None,
        "behind_count": None,
        "remote_tip_age_days": None,
        "attention": [],
        "review_recommended": True,
        "human_summary": GIT_BACKUP_ATTENTION_UNAVAILABLE_SUMMARY,
        "next_command": GIT_BACKUP_ATTENTION_NEXT_COMMAND,
        "probes": probes,
        "probe_budget_seconds": GIT_BACKUP_ATTENTION_BUDGET_SECONDS,
        "network_checked": False,
        "remote_state_is_proof": False,
        "paths_branches_or_messages_echoed": False,
    }

    try:
        root = archive_services.require_existing_archive_root(Path(archive_root))
    except (archive_services.ArchiveServiceError, OSError, ValueError, TypeError):
        block["reason_code"] = "archive_root_invalid"
        return block

    pinned = git_backup_plan._pin_git_executable()
    if pinned is None:
        block["state"] = "git_unavailable"
        block["reason_code"] = "git_executable_unavailable_or_unsafe"
        block["review_recommended"] = False
        block["human_summary"] = (
            "Git is not available to this process, so the local backup gap was not observed."
        )
        return block
    token = git_backup_plan._PINNED_GIT_EXECUTABLE.set(pinned)
    try:
        environment = git_backup_plan._local_git_environment()

        def probe(
            name: str,
            arguments: list[str],
            *,
            max_output_bytes: int = 64 * 1024,
            max_seconds: float = GIT_BACKUP_ATTENTION_PROBE_SECONDS,
        ) -> tuple[int, bytes] | None:
            remaining = deadline - time.monotonic()
            record: dict[str, Any] = {
                "probe": name,
                "available": False,
                "return_code": None,
                "failure_kind": None,
            }
            probes.append(record)
            if remaining <= 0:
                record["failure_kind"] = "probe_budget_exhausted"
                return None
            archive_services._wom_kit_git_take_failure()
            completed = archive_services._wom_kit_project_update_run_capped(
                git_backup_plan._git_command(root, arguments),
                environment=environment,
                timeout_seconds=max(0.05, min(max_seconds, remaining)),
                max_output_bytes=max_output_bytes,
            )
            if completed is None:
                record["failure_kind"] = (
                    archive_services._wom_kit_git_take_failure() or "launch_failed"
                )
                return None
            record["available"] = True
            record["return_code"] = int(completed[0])
            return completed

        def text_of(completed: tuple[int, bytes] | None) -> str | None:
            if completed is None or completed[0] != 0:
                return None
            try:
                return completed[1].decode("utf-8").strip()
            except UnicodeError:
                return None

        toplevel = probe("rev-parse", ["rev-parse", "--show-toplevel"])
        if toplevel is None:
            block["reason_code"] = "git_repository_probe_unavailable"
            return block
        block["repository_inspected"] = True
        if toplevel[0] != 0:
            block["state"] = "not_a_repository"
            block["reason_code"] = "git_repository_missing"
            block["review_recommended"] = False
            block["human_summary"] = (
                "This archive is not inside a Git repository; no Git backup lane is active."
            )
            return block
        toplevel_text = text_of(toplevel)
        block["repository_scope"] = (
            "archive_root"
            if toplevel_text is not None and _same_directory(toplevel_text, root)
            else "enclosing_repository"
        )

        attention: list[str] = []

        head = probe("log", ["log", "-1", "--format=%ct", "HEAD", "--"])
        head_text = text_of(head)
        if head is not None and head[0] != 0:
            block["head_state"] = "unborn"
            attention.append("head_unborn")
        elif head_text is not None and head_text.isdigit():
            block["head_state"] = "commit"
            block["last_commit_age_days"] = _days_since(int(head_text), now=now)
            if block["last_commit_age_days"] >= GIT_BACKUP_ATTENTION_STALE_DAYS:
                attention.append("last_commit_older_than_7_days")
        else:
            block["head_state"] = "unavailable"

        status = probe(
            "status",
            ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--", "."],
            max_output_bytes=GIT_BACKUP_ATTENTION_MAX_STATUS_BYTES,
            max_seconds=GIT_BACKUP_ATTENTION_STATUS_SECONDS,
        )
        counts = (
            _count_status_records(status[1])
            if status is not None and status[0] == 0
            else None
        )
        if counts is None:
            attention.append("uncommitted_change_count_unavailable")
        else:
            total, untracked, tracked = counts
            block["uncommitted_change_count"] = total
            block["uncommitted_change_count_state"] = "exact"
            block["untracked_count"] = untracked
            block["tracked_change_count"] = tracked
            if total > 0:
                attention.append("uncommitted_changes_present")

        if block["head_state"] == "commit":
            upstream = probe(
                "rev-parse-upstream",
                ["rev-parse", "--verify", "--quiet", "@{upstream}"],
            )
            if upstream is None:
                block["upstream_state"] = "unavailable"
            elif upstream[0] != 0:
                block["upstream_state"] = "missing"
                attention.append("upstream_missing")
            else:
                block["upstream_state"] = "tracked"
                counts_text = text_of(
                    probe(
                        "rev-list",
                        ["rev-list", "--count", "--left-right", "@{upstream}...HEAD", "--"],
                    )
                )
                parts = counts_text.split() if counts_text else []
                if len(parts) == 2 and all(part.isdigit() for part in parts):
                    block["behind_count"] = int(parts[0])
                    block["ahead_count"] = int(parts[1])
                    if block["ahead_count"] > 0:
                        attention.append("commits_not_pushed")
                tip_text = text_of(
                    probe("log-upstream", ["log", "-1", "--format=%ct", "@{upstream}", "--"])
                )
                if tip_text is not None and tip_text.isdigit():
                    block["remote_tip_age_days"] = _days_since(int(tip_text), now=now)
                    if block["remote_tip_age_days"] >= GIT_BACKUP_ATTENTION_STALE_DAYS:
                        attention.append("remote_tip_older_than_7_days")

        block["state"] = "observed"
        block["reason_code"] = "observed"
        block["attention"] = sorted(set(attention))
        block["review_recommended"] = bool(block["attention"])
        block["human_summary"] = _human_summary(block)
        return block
    finally:
        git_backup_plan._PINNED_GIT_EXECUTABLE.reset(token)


def _human_summary(block: dict[str, Any]) -> str:
    parts: list[str] = []
    count = block.get("uncommitted_change_count")
    if count is None:
        parts.append("the uncommitted change count could not be observed")
    elif count == 0:
        parts.append("no uncommitted changes")
    else:
        parts.append(f"{count} uncommitted change(s)")
    last_commit = block.get("last_commit_age_days")
    if block.get("head_state") == "unborn":
        parts.append("no commit yet")
    elif last_commit is not None:
        parts.append(f"last commit {last_commit} day(s) ago")
    upstream_state = block.get("upstream_state")
    if upstream_state == "missing":
        parts.append("no upstream branch is configured, so nothing here has a push target")
    elif upstream_state == "tracked":
        ahead = block.get("ahead_count")
        if ahead:
            parts.append(f"{ahead} commit(s) not pushed")
        elif ahead == 0:
            parts.append("every local commit is on the cached remote-tracking ref")
        tip = block.get("remote_tip_age_days")
        if tip is not None:
            parts.append(f"the newest commit the remote is known to have is {tip} day(s) old")
    summary = "Git backup attention: " + "; ".join(parts) + "."
    if not block.get("attention"):
        summary = "Git backup attention: " + "; ".join(parts) + " (nothing waiting)."
    return summary


def attach_git_backup_attention(
    result: dict[str, Any], archive_root: Path | str
) -> dict[str, Any]:
    """Return a copy of ``result`` carrying ``git_backup_attention``."""

    attached = dict(result)
    attached["git_backup_attention"] = git_backup_attention(archive_root)
    return attached
