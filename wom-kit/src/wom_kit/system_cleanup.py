"""v0.4.55 (owner request 2026-10-01): WOM's own byproducts are deleted, not left to pile up.

WOM itself, not the person or their AI, leaves files on the operator's PC:
a runtime per version updated to, a bootstrap environment per install, an
update result, a terminal handoff capsule and an operation journal per run,
abandoned download pieces and temporary files after a crash. Nothing deleted
them, so they grew with every release (about 40-55 MB per runtime and per
bootstrap environment), and more than 4096 journals block the update's
delivery scan outright.

Two paths share one planner:

* ``auto_prune_after_update(project_root)`` runs after a successful update
  whose result delivery was acknowledged. It deletes project-internal junk
  only: runtimes other than the pinned one and the one before it, and finished
  update results, handoff capsules and journals older than seven days (the
  newest few of each kind always stay).
* ``system-cleanup <archive-root> --dry-run`` / ``--approve`` covers the same
  plus bootstrap environments under ``%LOCALAPPDATA%\\WOM``, WOM temporary
  files and abandoned restore downloads, under one exact approval.

Never deleted: the pinned and previous runtime, the running interpreter,
anything while a project update holds its lock or an update transaction is
open, an update result or capsule whose delivery is pending, receipts,
approval claims, credential records, manifests, ledgers and locks. Only
WOM-named regular files or validated WOM trees are touched; a file another
program holds open is skipped and retried next time. Paths are never echoed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import sys
import tempfile
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OPERATION = "system_cleanup"
LIFECYCLE_ACTION = "system_cleanup"
SCHEMA_PLAN = "wom-kit/system-cleanup-plan/v0.1"
SCHEMA_RESULT = "wom-kit/system-cleanup-result/v0.1"
SCHEMA_RECEIPT = "wom-kit/system-cleanup-receipt/v0.1"
RECEIPT_PREFIX = "receipts/system-cleanup"
REVIEW_BINDING_CODES = ("plan_digest_reviewed", "cleanup_items_reviewed")

FINISHED_RECORD_MIN_AGE_SECONDS = 7 * 86400
PARTIAL_MIN_AGE_SECONDS = 86400
KEEP_NEWEST_RECORDS = 5
KEEP_NEWEST_JOURNALS = 20
MAX_ITEMS_PER_CATEGORY = 10000

PROJECT_CATEGORIES = ("old_runtimes", "update_results", "update_handoff_capsules", "operation_journals")
APPROVAL_ONLY_CATEGORIES = ("bootstrap_environments", "temporary_files", "restore_partials", "archive_results")
CATEGORIES = PROJECT_CATEGORIES + APPROVAL_ONLY_CATEGORIES

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_DIR_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
# The documented name is bootstrap-v<NNNN>-<32 hex>; older docs used bootstrap-v<NNN> and helper
# AIs added their own labels (bootstrap-v0446-camp-<hex>). All live in WOM's own LOCALAPPDATA\WOM
# folder and are recognised only together with a pyvenv.cfg.
_BOOTSTRAP_RE = re.compile(r"^bootstrap-v(\d)(\d)(\d{1,3})(?:-[A-Za-z0-9._-]{1,80})?$")
_UPDATE_RESULT_RE = re.compile(r"^project-version-update-[0-9a-f]{32}\.json(?:\.partial)?$")
_CAPSULE_RE = re.compile(r"^[0-9a-f]{64}\.json$")
_JOURNAL_RE = re.compile(r"^[0-9a-f]{64}\.jsonl$")
_ARCHIVE_RESULT_RE = re.compile(r"^(?:[0-9a-f]{32}|capture-[0-9a-f]{8,64})\.json$")
_TEMP_FILE_RE = re.compile(r"^wom-(?:git-backup-.+\.(?:index|msg)|comctl32-v6-.+\.manifest)$")
_TEMP_DIR_RE = re.compile(r"^wom-project-runtime-(?:bundle|reference)-.+$")
_REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

_ERRORS = frozenset({
    "system_cleanup_plan_changed",
    "system_cleanup_nothing_to_delete",
    "system_cleanup_approval_claim_invalid",
    "system_cleanup_root_invalid",
})


class SystemCleanupError(RuntimeError):
    """Fixed-code failure; never carries a path."""

    def __init__(self, code: str) -> None:
        self.code = code if code in _ERRORS else "system_cleanup_plan_changed"
        self.effects: str | None = None
        self.cause_code: str | None = None
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"SystemCleanupError({self.code!r})"


def _fail(code: str, *, effects: str | None = None) -> SystemCleanupError:
    error = SystemCleanupError(code)
    error.effects = effects
    return error


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _lstat(path: Path) -> os.stat_result | None:
    try:
        return os.lstat(path)
    except OSError:
        return None


def _is_link_or_reparse(info: os.stat_result) -> bool:
    return bool(stat.S_ISLNK(info.st_mode) or (_REPARSE_FLAG and getattr(info, "st_file_attributes", 0) & _REPARSE_FLAG))


def _plain_dir(path: Path) -> bool:
    info = _lstat(path)
    return info is not None and stat.S_ISDIR(info.st_mode) and not _is_link_or_reparse(info)


def _plain_file(info: os.stat_result | None) -> bool:
    return info is not None and stat.S_ISREG(info.st_mode) and not _is_link_or_reparse(info)


def _tree_bytes(path: Path) -> int:
    total = 0
    for current, dirs, files in os.walk(path, followlinks=False):
        kept = []
        for name in dirs:
            info = _lstat(Path(current) / name)
            if info is not None and not _is_link_or_reparse(info):
                kept.append(name)
        dirs[:] = kept
        for name in files:
            info = _lstat(Path(current) / name)
            if _plain_file(info):
                total += info.st_size
    return total


def _version_tuple(text: str | None) -> tuple[int, int, int] | None:
    if not isinstance(text, str):
        return None
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", text.strip())
    return tuple(int(part) for part in match.groups()) if match else None  # type: ignore[return-value]


def _running_prefixes() -> list[Path]:
    prefixes = []
    for value in {sys.prefix, sys.base_prefix, os.path.dirname(sys.executable)}:
        try:
            prefixes.append(Path(value).resolve())
        except OSError:
            continue
    return prefixes


def _contains_running(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return True
    return any(prefix == resolved or resolved in prefix.parents for prefix in _running_prefixes())


def _pinned_version(project_root: Path) -> tuple[int, int, int] | None:
    pin = project_root / ".zettel-kasten" / "installed-version.txt"
    info = _lstat(pin)
    if not _plain_file(info) or info.st_size > 64:
        return None
    try:
        return _version_tuple(pin.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return None


def _update_in_progress(project_root: Path) -> bool:
    base = project_root / ".zettel-kasten"
    if _lstat(base / "version-update.lock") is not None:
        return True
    updates = base / "private" / "version-updates"
    try:
        return any(entry.name.startswith("update_") for entry in os.scandir(updates))
    except OSError:
        return False


def _delivery_pending(project_root: Path) -> bool:
    terminal = project_root / ".zettel-kasten" / "private" / "version-update-terminal"
    return any(_lstat(terminal / name) is not None for name in ("active.json", "display-pending.json"))


def _item(category: str, path: Path, *, size: int, mtime: float, scope: str, kind: str) -> dict[str, Any]:
    return {
        "category": category,
        "scope": scope,
        "kind": kind,
        "id": _sha256(f"{category}\0{path.name}".encode("utf-8"))[:32],
        "bytes": int(size),
        "mtime": int(mtime),
        "_path": path,
    }


def _old_files(folder: Path, pattern: re.Pattern[str], *, category: str, scope: str, min_age: float,
               keep_newest: int, now: float, eligible=None) -> list[dict[str, Any]]:
    if not _plain_dir(folder):
        return []
    entries = []
    try:
        listing = list(os.scandir(folder))
    except OSError:
        return []
    for entry in listing:
        if not pattern.fullmatch(entry.name):
            continue
        info = _lstat(Path(entry.path))
        if not _plain_file(info):
            continue
        entries.append((info.st_mtime, Path(entry.path), info))
    entries.sort(key=lambda row: (row[0], row[1].name), reverse=True)
    items = []
    for index, (mtime, path, info) in enumerate(entries):
        if index < keep_newest or now - mtime <= min_age:
            continue
        if eligible is not None and not eligible(path):
            continue
        items.append(_item(category, path, size=info.st_size, mtime=mtime, scope=scope, kind="file"))
        if len(items) >= MAX_ITEMS_PER_CATEGORY:
            break
    return items


def _journal_finished(path: Path) -> bool:
    """A journal whose last record is a completed, delivered operation; an unreadable one is junk."""

    try:
        info = os.lstat(path)
        if info.st_size > 2 * 1024 * 1024:
            return False
        lines = [line for line in path.read_bytes().splitlines() if line.strip()]
        first = json.loads(lines[0])
        last = json.loads(lines[-1])
    except (OSError, ValueError, IndexError):
        return True
    if not isinstance(first, dict) or not isinstance(last, dict):
        return True
    if last.get("event") != "completed" or last.get("terminal") is not True:
        return False
    if first.get("operation_kind") == "project_version_update":
        return last.get("terminal_delivery_acknowledged") is True or last.get("result_available") is False
    return True


def _project_items(project_root: Path, now: float) -> tuple[list[dict[str, Any]], list[str]]:
    notes: list[str] = []
    items: list[dict[str, Any]] = []
    base = project_root / ".zettel-kasten"
    if not _plain_dir(base):
        return items, notes
    if _update_in_progress(project_root):
        notes.append("project_update_in_progress_project_items_kept")
        return items, notes
    pinned = _pinned_version(project_root)
    runtimes = base / "runtimes"
    if pinned is None:
        notes.append("project_pin_unreadable_runtimes_kept")
    elif _plain_dir(runtimes):
        versions = []
        for entry in os.scandir(runtimes):
            match = _VERSION_DIR_RE.fullmatch(entry.name)
            path = Path(entry.path)
            if match is None or not _plain_dir(path):
                continue
            versions.append((tuple(int(part) for part in match.groups()), path))
        older = sorted((row for row in versions if row[0] < pinned), reverse=True)
        keep = {pinned}
        if older:
            keep.add(older[0][0])
        for version, path in sorted(versions):
            if version in keep or _contains_running(path):
                continue
            receipt = path / "runtime-receipt.json"
            try:
                document = json.loads(receipt.read_text(encoding="utf-8")) if _plain_file(_lstat(receipt)) else None
            except (OSError, ValueError, UnicodeError):
                document = None
            if (not isinstance(document, dict)
                    or document.get("schema") != "wom-kit/project-runtime-receipt/v0.1"
                    or _version_tuple(document.get("target_version")) != version):
                notes.append("unrecognised_runtime_kept")
                continue
            info = _lstat(path)
            items.append(_item("old_runtimes", path, size=_tree_bytes(path), mtime=info.st_mtime if info else now,
                               scope="project", kind="tree"))
    pending = _delivery_pending(project_root)
    if pending:
        notes.append("update_result_delivery_pending_results_kept")
    else:
        items += _old_files(base / "diagnostics", _UPDATE_RESULT_RE, category="update_results", scope="project",
                            min_age=FINISHED_RECORD_MIN_AGE_SECONDS, keep_newest=KEEP_NEWEST_RECORDS, now=now)
        items += _old_files(base / "private" / "version-update-terminal", _CAPSULE_RE,
                            category="update_handoff_capsules", scope="project",
                            min_age=FINISHED_RECORD_MIN_AGE_SECONDS, keep_newest=KEEP_NEWEST_RECORDS, now=now)
    items += _old_files(base / "operations", _JOURNAL_RE, category="operation_journals", scope="project",
                        min_age=FINISHED_RECORD_MIN_AGE_SECONDS, keep_newest=KEEP_NEWEST_JOURNALS, now=now,
                        eligible=_journal_finished)
    return items, notes


def _archive_items(archive_root: Path, now: float) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    diagnostics = archive_root / ".wom-scratch" / "diagnostics"
    items += _old_files(diagnostics, _ARCHIVE_RESULT_RE, category="archive_results", scope="archive",
                        min_age=FINISHED_RECORD_MIN_AGE_SECONDS, keep_newest=KEEP_NEWEST_RECORDS, now=now)
    items += _old_files(diagnostics / ".operations", _JOURNAL_RE, category="operation_journals", scope="archive",
                        min_age=FINISHED_RECORD_MIN_AGE_SECONDS, keep_newest=KEEP_NEWEST_JOURNALS, now=now,
                        eligible=_journal_finished)
    sinks = archive_root / "profiles" / "local" / "exact-operations" / "restore-sinks"
    if _plain_dir(sinks):
        for current, dirs, files in os.walk(sinks, followlinks=False):
            dirs[:] = [name for name in dirs if _plain_dir(Path(current) / name)]
            for name in files:
                path = Path(current) / name
                info = _lstat(path)
                if name.endswith(".part") and _plain_file(info) and now - info.st_mtime > PARTIAL_MIN_AGE_SECONDS:
                    items.append(_item("restore_partials", path, size=info.st_size, mtime=info.st_mtime,
                                       scope="archive", kind="file"))
    return items


def _user_items(project_root: Path, now: float) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    notes: list[str] = []
    pinned = _pinned_version(project_root)
    local = os.environ.get("LOCALAPPDATA")
    wom_folder = Path(local) / "WOM" if local else None
    if wom_folder is not None and _plain_dir(wom_folder):
        if pinned is None:
            notes.append("project_pin_unreadable_bootstrap_environments_kept")
        else:
            for entry in os.scandir(wom_folder):
                match = _BOOTSTRAP_RE.fullmatch(entry.name)
                path = Path(entry.path)
                if match is None or not _plain_dir(path) or not _plain_file(_lstat(path / "pyvenv.cfg")):
                    continue
                version = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
                info = _lstat(path)
                if (version > pinned or info is None or now - info.st_mtime <= PARTIAL_MIN_AGE_SECONDS
                        or _contains_running(path)):
                    continue
                items.append(_item("bootstrap_environments", path, size=_tree_bytes(path), mtime=info.st_mtime,
                                   scope="user_local_app_data", kind="tree"))
    temp = Path(tempfile.gettempdir())
    if _plain_dir(temp):
        try:
            listing = list(os.scandir(temp))
        except OSError:
            listing = []
        for entry in listing:
            path = Path(entry.path)
            info = _lstat(path)
            if info is None or now - info.st_mtime <= PARTIAL_MIN_AGE_SECONDS:
                continue
            if _TEMP_FILE_RE.fullmatch(entry.name) and _plain_file(info):
                items.append(_item("temporary_files", path, size=info.st_size, mtime=info.st_mtime,
                                   scope="user_temp", kind="file"))
            elif _TEMP_DIR_RE.fullmatch(entry.name) and _plain_dir(path) and not _contains_running(path):
                items.append(_item("temporary_files", path, size=_tree_bytes(path), mtime=info.st_mtime,
                                   scope="user_temp", kind="tree"))
    return items, notes


def _summary(items: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {category: {"count": sum(1 for item in items if item["category"] == category),
                       "bytes": sum(item["bytes"] for item in items if item["category"] == category)}
            for category in CATEGORIES}


def _project_root(archive_root: Path) -> Path:
    from . import archive_services

    return archive_services._project_update_resume_project_root_read_only(archive_root)


def _collect(archive_root: Path, *, now: float, project_only: bool = False) -> tuple[list[dict[str, Any]], list[str]]:
    project_root = _project_root(archive_root) if not project_only else archive_root
    items, notes = _project_items(project_root, now)
    if not project_only:
        items += _archive_items(archive_root, now)
        user_items, user_notes = _user_items(project_root, now)
        items += user_items
        notes += user_notes
    items.sort(key=lambda item: (item["category"], item["id"]))
    return items, sorted(set(notes))


def _plan_digest(items: list[dict[str, Any]]) -> str:
    return _sha256(_canonical({
        "schema": SCHEMA_PLAN,
        "items": [[item["category"], item["id"], item["bytes"], item["mtime"]] for item in items],
    }))


def plan_system_cleanup(archive_root: Path | str, *, now: float | None = None) -> dict[str, Any]:
    """Read-only plan: which WOM byproducts would be deleted, by kind, with byte counts."""

    from . import archive_services

    root = archive_services.require_existing_archive_root(archive_root)
    moment = time.time() if now is None else now
    items, notes = _collect(root, now=moment)
    blockers = [] if items else ["system_cleanup_nothing_to_delete"]
    summary = _summary(items)
    return {
        "schema": SCHEMA_PLAN,
        "ok": not blockers,
        "state": "ready_for_exact_human_approval" if not blockers else "blocked",
        "dry_run": True,
        "lifecycle_action": LIFECYCLE_ACTION,
        "plan_sha256": _plan_digest(items),
        "items_sha256": _sha256(_canonical(sorted(item["id"] for item in items))),
        "item_count": len(items),
        "bytes_freed_total": sum(item["bytes"] for item in items),
        "categories": summary,
        "kept_notes": notes,
        "policy": {
            "runtimes_kept": "the pinned version and the one before it",
            "finished_records_min_age_days": FINISHED_RECORD_MIN_AGE_SECONDS // 86400,
            "partials_min_age_hours": PARTIAL_MIN_AGE_SECONDS // 3600,
            "newest_records_kept": KEEP_NEWEST_RECORDS,
            "newest_journals_kept": KEEP_NEWEST_JOURNALS,
            "never_deleted": ["receipts", "approval claims", "credential records", "manifests", "ledgers",
                              "locks", "open update transactions", "pending update results"],
        },
        "recoverable": False,
        "blockers": blockers,
        "reason_codes": blockers or ["system_cleanup_ready"],
        "next_safe_actions": (
            ["Rerun with --approve --reviewed-by <person:...> --expected-plan-sha256 <plan_sha256>; one dialog (or the session grant) deletes the whole plan. Deleted items cannot be recovered and are all rebuildable or finished WOM byproducts."]
            if not blockers else
            ["Nothing to delete: no finished WOM byproduct is old enough or outside what is always kept."]
        ),
        "private_values_echoed": False,
        "local_paths_echoed": False,
    }


def _delete(item: dict[str, Any]) -> bool:
    path: Path = item["_path"]
    info = _lstat(path)
    if info is None:
        return True
    if _is_link_or_reparse(info):
        return False
    try:
        if item["kind"] == "tree":
            if not stat.S_ISDIR(info.st_mode):
                return False
            failed: list[bool] = []

            def _onexc(_function, _path, _error):
                failed.append(True)

            if sys.version_info >= (3, 12):
                shutil.rmtree(path, onexc=_onexc)
            else:  # pragma: no cover - Python 3.10/3.11
                shutil.rmtree(path, onerror=lambda *args: failed.append(True))
            return not failed and _lstat(path) is None
        if not stat.S_ISREG(info.st_mode):
            return False
        os.unlink(path)
        return True
    except OSError:
        return False


def _remove_empty_restore_folders(archive_root: Path) -> None:
    sinks = archive_root / "profiles" / "local" / "exact-operations" / "restore-sinks"
    if not _plain_dir(sinks):
        return
    for current, dirs, files in sorted(os.walk(sinks, followlinks=False), key=lambda row: -len(row[0])):
        if Path(current) != sinks and not dirs and not files:
            try:
                os.rmdir(current)
            except OSError:
                pass


def _run_deletions(items: list[dict[str, Any]]) -> tuple[dict[str, dict[str, int]], int, int]:
    deleted = {category: {"count": 0, "bytes": 0} for category in CATEGORIES}
    skipped = 0
    freed = 0
    for item in items:
        if _delete(item):
            deleted[item["category"]]["count"] += 1
            deleted[item["category"]]["bytes"] += item["bytes"]
            freed += item["bytes"]
        else:
            skipped += 1
    return deleted, skipped, freed


def approve_system_cleanup(
    archive_root: Path | str,
    *,
    expected_plan_sha256: str,
    reviewed_by: str,
    exact_human_approval_claim: Any = None,
    now: float | None = None,
) -> dict[str, Any]:
    """The approved deletion of the exact reviewed plan, then one content-free receipt."""

    from . import archive_services

    root = archive_services.require_existing_archive_root(archive_root)
    moment = time.time() if now is None else now
    items, notes = _collect(root, now=moment)
    if not items:
        raise _fail("system_cleanup_nothing_to_delete", effects="none")
    plan_sha = _plan_digest(items)
    expected = str(expected_plan_sha256 or "").strip().lower()
    if _SHA_RE.fullmatch(expected) is None or not secrets.compare_digest(plan_sha, expected):
        raise _fail("system_cleanup_plan_changed", effects="none")
    envelope: dict[str, Any] | None = None
    if exact_human_approval_claim is not None:
        reference = exact_human_approval_claim.public_reference()
        if not isinstance(reference, Mapping):
            raise _fail("system_cleanup_approval_claim_invalid", effects="none")
        envelope = {**dict(reference), "operation": OPERATION}
    deleted, skipped, freed = _run_deletions(items)
    _remove_empty_restore_folders(root)
    cleaned_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt_relative = f"{RECEIPT_PREFIX}/{plan_sha[:16]}.json"
    receipt: dict[str, Any] = {
        "schema": SCHEMA_RECEIPT, "lifecycle_action": LIFECYCLE_ACTION, "plan_sha256": plan_sha,
        "cleaned_at": cleaned_at, "reviewed_by": reviewed_by, "deleted": deleted,
        "skipped_count": skipped, "bytes_freed": freed, "automatic": False,
    }
    if envelope is not None:
        receipt["exact_human_approval"] = envelope
    try:
        archive_services._atomic_write_json(archive_services.archive_internal_path(root, receipt_relative), receipt)
        receipt_written = True
    except OSError:
        receipt_written = False
    complete = skipped == 0 and receipt_written
    return {
        "schema": SCHEMA_RESULT,
        "ok": complete,
        "state": "cleaned" if complete else "partially_cleaned",
        "dry_run": False,
        "approved": True,
        "lifecycle_action": LIFECYCLE_ACTION,
        "plan_sha256": plan_sha,
        "deleted": deleted,
        "deleted_count": sum(row["count"] for row in deleted.values()),
        "skipped_count": skipped,
        "bytes_freed": freed,
        "kept_notes": notes,
        "receipt_relative_path": receipt_relative if receipt_written else None,
        "recoverable": False,
        "blockers": [] if complete else ["system_cleanup_items_in_use_skipped"],
        "next_safe_actions": (
            [] if complete else
            ["Some items were in use (for example a program still had a file open) and were left; rerun --dry-run later to delete them."]
        ),
        "private_values_echoed": False,
        "local_paths_echoed": False,
    }


def auto_prune_after_update(project_root: Path | str, *, now: float | None = None) -> dict[str, Any]:
    """Project-internal pruning after a successful, delivered update; never raises.

    The person approved the update; these items are WOM's own finished or
    superseded byproducts inside the project (old runtimes beyond the previous
    one, update results, handoff capsules and journals older than seven days),
    deleted under the same rules as ``system-cleanup``.
    """

    try:
        root = Path(project_root)
        moment = time.time() if now is None else now
        items, notes = _project_items(root, moment)
        deleted, skipped, freed = _run_deletions(items)
        return {
            "schema": "wom-kit/system-cleanup-auto-prune/v0.1",
            "deleted": {category: deleted[category] for category in PROJECT_CATEGORIES},
            "deleted_count": sum(row["count"] for row in deleted.values()),
            "skipped_count": skipped,
            "bytes_freed": freed,
            "kept_notes": notes,
            "local_paths_echoed": False,
        }
    except Exception:  # noqa: BLE001 - pruning never changes the update outcome
        return {"schema": "wom-kit/system-cleanup-auto-prune/v0.1", "deleted_count": 0,
                "unavailable": True, "local_paths_echoed": False}


__all__ = [
    "CATEGORIES",
    "OPERATION",
    "REVIEW_BINDING_CODES",
    "SystemCleanupError",
    "approve_system_cleanup",
    "auto_prune_after_update",
    "plan_system_cleanup",
]
