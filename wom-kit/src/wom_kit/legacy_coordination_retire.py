"""Retire one workspace-local coordination root by moving it, never deleting.

Letters 142, 148 and 156 were blocked three times by
`legacy-coordination-cleanup`, whose writer could only delete and refused
collaboration records, nested Git repositories and a Git check that could not
run. The customer asked for a narrow contract that names only the retired
structure, keeps collaboration records and nested repositories intact, and
ends the old structure. Retirement moves the whole `.mow-harness` folder in
one same-volume rename to a reviewed destination outside the workspace,
verifies the moved folder is the same one, and writes a content-free receipt
in the workspace archive. Nothing is deleted; removing the preserved copy
later is the owner's own choice.

Public results stay content-free: no names, paths, or file contents are
echoed. The exact effect set is bound by `plan_sha256`.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

from . import legacy_coordination_cleanup as cleanup

RETIRE_PLAN_SCHEMA = "wom-kit/legacy-coordination-retire-plan/v0.1"
RETIRE_RESULT_SCHEMA = "wom-kit/legacy-coordination-retire-result/v0.1"
RETIRE_RECEIPT_SCHEMA = "wom-kit/legacy-coordination-retire-receipt/v0.1"
RETIRE_RECEIPTS_DIR = "receipts/legacy-coordination-retirements"
RETIRE_POLICY_VERSION = 1
FINAL_NAME_PREFIX = "mow-harness-retired-"

# Blockers of the delete-only cleanup that describe content retirement keeps:
# a move preserves collaboration records, nested repositories and unknown
# top-level entries intact, so they become preserved classes, not blockers.
PRESERVED_CLASS_BLOCKERS = {
    "collab_present_in_target": "preserved_collab",
    "nested_git_repository_present": "preserved_nested_repository",
    "unknown_top_level_entry": "preserved_unknown_top_level",
    "top_level_name_case_mismatch": "preserved_unknown_top_level",
}


def _sha(value: Any) -> str:
    return hashlib.sha256(cleanup._canonical_bytes(value)).hexdigest()


def _git_environment() -> dict[str, str]:
    # Keep the user's global Git configuration (for example safe.directory);
    # the delete-only cleanup ignored it and failed as git_tracking_check_failed
    # on folders Git considers owned by another account. Repository-selection
    # variables are still stripped so the check cannot be redirected.
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
        or key.upper() in {"GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM"}
    }
    environment.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"})
    return environment


def _git_blockers(workspace_root: Path) -> list[str]:
    """Moving files a parent repository tracks would change that repository."""

    selector = {"GIT_COMMON_DIR", "GIT_DIR", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_WORK_TREE"}
    if any(name in os.environ for name in selector):
        return ["git_tracking_environment_unsafe"]
    roots: list[Path] = []
    current = workspace_root
    while True:
        marker = current / ".git"
        if cleanup._path_exists_no_follow(marker):
            try:
                info = os.lstat(marker)
            except OSError:
                return ["git_ancestor_marker_unsafe"]
            if cleanup._is_reparse(info) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                return ["git_ancestor_marker_unsafe"]
            roots.append(current)
        if current.parent == current:
            break
        current = current.parent
    if not roots:
        return []
    import subprocess

    environment = _git_environment()
    target = workspace_root / cleanup.TARGET_NAME
    for root in roots:
        try:
            top = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=environment, timeout=10, check=False,
                creationflags=cleanup.noninteractive_creationflags(),
            )
        except FileNotFoundError:
            return ["git_executable_unavailable"]
        except (OSError, subprocess.SubprocessError):
            return ["git_tracking_check_failed"]
        if top.returncode != 0:
            if b"safe.directory" in top.stderr or b"dubious ownership" in top.stderr:
                return ["git_safe_directory_refused"]
            return ["git_tracking_check_failed"]
        try:
            rendered = os.fsdecode(top.stdout).rstrip("\r\n")
            if not rendered or "\n" in rendered:
                raise ValueError("ambiguous top level")
            observed = Path(rendered).resolve(strict=True)
            if cleanup._normalized_path_key(observed) != cleanup._normalized_path_key(root.resolve(strict=True)):
                return ["git_toplevel_mismatch"]
            pathspec = target.relative_to(observed).as_posix()
        except (OSError, RuntimeError, ValueError):
            return ["git_toplevel_mismatch"]
        try:
            tracked = subprocess.run(
                ["git", "-C", str(observed), "--literal-pathspecs", "ls-files", "-z", "--", pathspec],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env=environment, timeout=10, check=False,
                creationflags=cleanup.noninteractive_creationflags(),
            )
        except (OSError, subprocess.SubprocessError):
            return ["git_tracking_check_failed"]
        if tracked.returncode != 0:
            return ["git_tracking_check_failed"]
        if tracked.stdout:
            return ["git_tracked_target"]
    return []


def _inside_git_worktree(path: Path) -> bool:
    current = path
    while True:
        if cleanup._path_exists_no_follow(current / ".git"):
            return True
        if current.parent == current:
            return False
        current = current.parent


def _destination_state(
    destination: Path | str | None,
    *,
    workspace_root: Path | None,
    target_identity: dict[str, int] | None,
    final_name: str,
) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    if not destination or not str(destination).strip():
        return {}, ["destination_required"]
    supplied = Path(str(destination))
    if not supplied.is_absolute():
        return {}, ["destination_must_be_absolute"]
    try:
        info = os.lstat(supplied)
    except OSError:
        return {}, ["destination_missing_or_unreadable"]
    if cleanup._is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        return {}, ["destination_not_a_plain_directory"]
    resolved = supplied.resolve(strict=True)
    if workspace_root is not None:
        workspace_key = cleanup._normalized_path_key(workspace_root.resolve(strict=True))
        destination_key = cleanup._normalized_path_key(resolved)
        if destination_key == workspace_key or destination_key.startswith(workspace_key.rstrip("\\/") + os.sep.lower()) \
                or destination_key.startswith(workspace_key.rstrip("\\/") + "/"):
            blockers.append("destination_inside_workspace")
    if target_identity is not None and int(info.st_dev) != int(target_identity["device"]):
        blockers.append("destination_cross_volume")
    if _inside_git_worktree(resolved):
        blockers.append("destination_inside_git_worktree")
    if cleanup._path_exists_no_follow(resolved / final_name):
        blockers.append("destination_final_name_exists")
    return {
        "path_key_sha256": hashlib.sha256(cleanup._normalized_path_key(resolved).encode("utf-8")).hexdigest(),
        "identity": cleanup._identity(info),
        "final_name": final_name,
    }, blockers


def _build_retire_plan(
    workspace_root: Path | str,
    destination: Path | str | None,
    *,
    max_files: int,
    max_bytes: int,
    owned_lock_record: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], Path | None]:
    supplied = Path(workspace_root)
    blockers: list[str] = []
    classes = {"preserved_collab": False, "preserved_nested_repository": False, "preserved_unknown_top_level": False}
    tree: dict[str, Any] = {"records": [], "summary": {}, "blockers": []}
    host_identity: dict[str, Any] = {}
    target_present = False
    target_identity: dict[str, int] | None = None
    normalized, root_identity, root_blockers = cleanup._validate_workspace_root_path(supplied)
    blockers.extend(root_blockers)
    if not blockers:
        host_identity, host_blockers = cleanup._host_identity(normalized)
        blockers.extend(host_blockers)
    if not blockers:
        target, name_blockers, target_present = cleanup._workspace_target_name_state(
            normalized, owned_lock_record=owned_lock_record,
        )
        blockers.extend(name_blockers)
        if target_present and not name_blockers:
            try:
                target_identity = cleanup._identity(os.lstat(target))
            except OSError:
                blockers.append("target_unreadable")
            tree = cleanup._scan_target_tree(normalized, target, max_files=max_files, max_bytes=max_bytes)
            for code in tree["blockers"]:
                preserved = PRESERVED_CLASS_BLOCKERS.get(code)
                if preserved:
                    classes[preserved] = True
                else:
                    blockers.append(code)
            blockers.extend(_git_blockers(normalized))
    scan_digest = _sha(tree["records"])
    final_name = FINAL_NAME_PREFIX + scan_digest[:8]
    destination_state: dict[str, Any] = {}
    if target_present:
        destination_state, destination_blockers = _destination_state(
            destination,
            workspace_root=normalized if not root_blockers else None,
            target_identity=target_identity,
            final_name=final_name,
        )
        blockers.extend(destination_blockers)
    private = {
        "schema": RETIRE_PLAN_SCHEMA,
        "policy_version": RETIRE_POLICY_VERSION,
        "workspace_root_identity": root_identity,
        "host_identity": host_identity,
        "target_present": target_present,
        "target_identity": target_identity,
        "target_records": tree["records"],
        "preserved_classes": classes,
        "destination": destination_state,
        "limits": {"max_files": max_files, "max_bytes": max_bytes},
        "blockers": cleanup._unique_codes(blockers),
    }
    plan_sha256 = _sha(private)
    public = {
        "schema": RETIRE_PLAN_SCHEMA,
        "ok": not private["blockers"],
        "action": "legacy_coordination_retire_plan",
        "status": "blocked" if private["blockers"] else "ready" if target_present else "target_absent",
        "dry_run": True,
        "target_present": target_present,
        "plan_sha256": plan_sha256,
        "summary": tree.get("summary", {}),
        "preserved_classes": classes,
        "destination_final_name": final_name if target_present else None,
        "would_change": (
            ["move the retired coordination folder to the reviewed destination"]
            if target_present and not private["blockers"] else []
        ),
        "deletes": False,
        "blockers": private["blockers"],
        "privacy": {"absolute_paths_echoed": False, "filenames_echoed": False, "file_contents_echoed": False},
    }
    return private, public, normalized if not root_blockers else None


def legacy_coordination_retire_plan(
    workspace_root: Path | str,
    destination: Path | str | None,
    *,
    max_files: int = cleanup.DEFAULT_LEGACY_COORDINATION_CLEANUP_MAX_FILES,
    max_bytes: int = cleanup.DEFAULT_LEGACY_COORDINATION_CLEANUP_MAX_BYTES,
) -> dict[str, Any]:
    _private, public, _root = _build_retire_plan(workspace_root, destination, max_files=max_files, max_bytes=max_bytes)
    return public


def _write_receipt(archive_root: Path, receipt: dict[str, Any]) -> str:
    directory = archive_root / RETIRE_RECEIPTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    relative = f"{RETIRE_RECEIPTS_DIR}/{receipt['plan_sha256'][:16]}.json"
    path = archive_root / relative
    raw = (json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    try:
        os.write(descriptor, raw)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return relative


def legacy_coordination_retire(
    workspace_root: Path | str,
    destination: Path | str,
    *,
    expected_plan_sha256: str,
    reviewed_by: str | None,
    exact_human_approval_claim: Any = None,
    expected_exact_approval_plan_sha256: str | None = None,
    expected_exact_approval_target_binding_sha256: str | None = None,
    max_files: int = cleanup.DEFAULT_LEGACY_COORDINATION_CLEANUP_MAX_FILES,
    max_bytes: int = cleanup.DEFAULT_LEGACY_COORDINATION_CLEANUP_MAX_BYTES,
) -> dict[str, Any]:
    """Move the reviewed coordination folder after a reauthenticated approval."""

    from . import archive_services
    from .exact_human_approval_windows import ExactHumanApprovalOperation
    from .operation_approval_binding import OperationApprovalBindingError, plan_digest_approval_binding

    if exact_human_approval_claim is None:
        return archive_services._compound_exact_human_approval_blocked(
            lifecycle_action="legacy_coordination_retire",
        )
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if reviewer is None:
        raise archive_services.ArchiveServiceError("legacy_coordination_retire_reviewer_invalid")
    workspace = Path(workspace_root)
    archive_root = archive_services.require_existing_archive_root(workspace / "archive")
    try:
        archive_services._require_exact_human_operation_approval(
            archive_root,
            plan_digest_approval_binding(ExactHumanApprovalOperation.legacy_coordination_retire, expected_plan_sha256),
            reviewer_claim=reviewer,
            expected_plan_sha256=expected_exact_approval_plan_sha256,
            expected_target_binding_sha256=expected_exact_approval_target_binding_sha256,
            claim=exact_human_approval_claim,
        )
    except OperationApprovalBindingError as exc:
        raise archive_services.ArchiveServiceError(exc.code) from None

    def result(status: str, blockers: list[str], *, moved: bool, receipt: str | None = None,
               public: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            **(public or {}),
            "schema": RETIRE_RESULT_SCHEMA,
            "ok": status == "retired" and not blockers,
            "action": "legacy_coordination_retire",
            "status": status,
            "dry_run": False,
            "moved": moved,
            "deletes": False,
            "receipt_path": receipt,
            "blockers": cleanup._unique_codes(blockers),
            "files_written": [receipt] if receipt else [],
        }

    normalized, _root_identity, root_blockers = cleanup._validate_workspace_root_path(workspace)
    if root_blockers:
        return result("blocked", root_blockers, moved=False)
    lock_path = normalized / cleanup.LOCK_NAME
    with cleanup.bind_workspace_root(normalized) as bound:
        try:
            descriptor, lock_record = cleanup._acquire_lock(bound, lock_path)
        except OSError:
            return result("blocked", ["retire_lock_occupied_or_unsafe"], moved=False)
        try:
            # Re-plan with the workspace path exactly as supplied: the reviewed
            # digest binds the supplied and the canonical path.
            private, public, root = _build_retire_plan(
                workspace, destination, max_files=max_files, max_bytes=max_bytes,
                owned_lock_record=lock_record,
            )
            if public["plan_sha256"] != expected_plan_sha256 or private["blockers"] or root is None:
                return result("blocked", [*private["blockers"], "legacy_coordination_retire_plan_changed"],
                              moved=False, public=public)
            target = root / cleanup.TARGET_NAME
            final = Path(str(destination)).resolve(strict=True) / private["destination"]["final_name"]
            before = cleanup._identity(os.lstat(target))
            try:
                os.rename(target, final)
            except OSError:
                return result("blocked", ["retire_move_failed_nothing_changed"], moved=False, public=public)
            try:
                after = cleanup._identity(os.lstat(final))
                target_gone = not cleanup._path_exists_no_follow(target)
            except OSError:
                after, target_gone = None, False
            if after != before or not target_gone:
                return result("recovery_required", ["relocated_verification_mismatch"], moved=True, public=public)
            receipt = {
                "schema": RETIRE_RECEIPT_SCHEMA,
                "plan_sha256": expected_plan_sha256,
                "reviewed_by": reviewer,
                "summary": public.get("summary", {}),
                "preserved_classes": private["preserved_classes"],
                "destination_path_key_sha256": private["destination"]["path_key_sha256"],
                "destination_final_name": private["destination"]["final_name"],
                "target_records_sha256": _sha(private["target_records"]),
                "deletes": False,
                "exact_human_approval": {
                    "operation": "legacy_coordination_retire",
                    "approval_plan_sha256": expected_exact_approval_plan_sha256,
                },
            }
            try:
                relative = _write_receipt(archive_root, receipt)
            except OSError:
                return result("retired_receipt_missing", ["retire_receipt_write_failed"], moved=True, public=public)
            return result("retired", [], moved=True, receipt=relative, public=public)
        finally:
            cleanup._release_lock(normalized, lock_path, descriptor, lock_record)
