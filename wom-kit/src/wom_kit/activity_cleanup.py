"""Exact-file activity cleanup with immutable intent and recoverable file states.

The request and journal are private. Public output contains ordinal item numbers,
roles, byte counts and fixed codes only. Native retained-handle deletion is shared
with existing cleanup; a request is never interpreted as a recursive delete.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import uuid
import subprocess
import time
from contextlib import contextmanager

from . import archive_services as services
from .exact_human_approval_windows import ExactHumanApprovalOperation
from .exact_human_approval import PERMISSION_INTERACTIVE_INTENT_MECHANISM
from .operation_approval_binding import ExactOperationApprovalBinding
from .process_launch import noninteractive_creationflags
from . import work_timing

# The intent holds absolute external paths, reasons, a whole-root inventory and
# storage endpoints. It lives under the private, Git-ignored profile boundary so
# an archive Git backup never commits it; v0.4.38 journals are read for resume.
ROOT = "profiles/local/activity-cleanup"
LEGACY_ROOT = "receipts/activity-cleanup"
SCHEMA = "wom-kit/activity-cleanup-request/v1"
ROLES = frozenset({"deliverable", "source", "evidence", "temporary", "unknown"})
MAX_ITEMS = 100000
MAX_CONTROL_BYTES = 32 * 1024 * 1024
DOMAIN = b"wom-kit/activity-cleanup/v1\0"


def _in_archive_ai_scratch(root, path):
    """True for a path under the archive's own AI scratch roots (letter 173 D)."""
    root, path = root.resolve(), path.resolve()
    return path.is_relative_to(root) and any(
        path.is_relative_to(root / prefix.rstrip("/")) for prefix in services.AI_SCRATCH_ROOT_PREFIXES)


def _zet_referenced_scratch(root):
    """Archive-relative scratch paths any draft or zet still references explicitly."""
    referenced = set()
    for zet in services.iter_zettel_paths(root):
        try:
            frontmatter, body = services.require_readable_zettel_content(zet)
        except (services.ArchiveServiceError, OSError, UnicodeError, ValueError):
            continue
        for ref in services.zettel_ai_scratch_references(frontmatter, body):
            referenced.add(str(ref.get("path") or "").casefold())
    return referenced


class ActivityCleanupError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("ascii")


def digest(value):
    return "sha256:" + hashlib.sha256(encoded(value)).hexdigest()


def _safe_path(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 1024:
            raise ActivityCleanupError("activity_cleanup_link_or_reparse_path")
    return path


@work_timing.timed("local_hash_verify")
def file_state(path):
    path = _safe_path(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ActivityCleanupError("activity_cleanup_regular_single_link_file_required")
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
            raise ActivityCleanupError("activity_cleanup_file_changed")
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
        end = os.fstat(stream.fileno())
    latest = path.lstat()
    key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_nlink)
    if key(info) != key(end) or key(info) != key(latest):
        raise ActivityCleanupError("activity_cleanup_file_changed")
    return {"type": "file", "identity": {"device": info.st_dev, "inode": info.st_ino},
            "size": info.st_size, "mtime_ns": info.st_mtime_ns, "sha256": sha.hexdigest()}


def _directory_state(path):
    info = _safe_path(path).lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise ActivityCleanupError("activity_cleanup_directory_required")
    return {"type": "directory", "identity": {"device": info.st_dev, "inode": info.st_ino,
            "birthtime_ns": getattr(info, "st_birthtime_ns", None)}}


def _git_inventory(root):
    """Read Git facts without checkout, hooks or interpreting the output as code."""
    if not (root / ".git").exists():
        return {"repository": False}
    def git(*args):
        run = subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False,
            creationflags=noninteractive_creationflags())
        if run.returncode:
            raise ActivityCleanupError("activity_cleanup_git_inventory_unavailable")
        return run.stdout
    common = Path(os.fsdecode(git("rev-parse", "--path-format=absolute", "--git-common-dir")).strip())
    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    refs = git("for-each-ref")
    worktrees = git("worktree", "list", "--porcelain", "-z")
    return {"repository": True, "git_state_sha256": digest([status.hex(), refs.hex(), worktrees.hex()]),
        "has_uncommitted_or_untracked_files": bool(status),
        "untracked_entry_count": sum(row.startswith(b"?? ") for row in status.split(b"\0")),
        "tracked_change_entry_count": sum(len(row) > 3 and row[2:3] == b" " and not row.startswith(b"?? ") for row in status.split(b"\0")),
        # Windows temp roots may use an 8.3 alias while Git prints the long
        # spelling. Resolve both before deciding that history is external.
        "history_in_selected_root": common.resolve().is_relative_to(root.resolve()),
        "external_worktree_dependency": (not common.resolve().is_relative_to(root.resolve())
            or worktrees.count(b"worktree ") > 1)}


def _assert_no_new_git_worktree_dependency(item):
    """Check a shared-history link again immediately before a Git file changes."""
    root = Path(item["root"])
    path = Path(item["path"])
    if not path.is_relative_to(root / ".git"):
        return
    linked = root / ".git" / "worktrees"
    if os.path.lexists(linked):
        _safe_path(linked)
        if not linked.is_dir() or any(linked.iterdir()):
            raise ActivityCleanupError("activity_cleanup_shared_git_metadata_requires_worktree_detach")


def _inventory(root):
    """Bounded private metadata inventory; never follow links or infer roles."""
    result, stack = [], [Path(root)]
    while stack:
        parent = stack.pop()
        for entry in sorted(parent.iterdir()):
            info = entry.lstat()
            relative = entry.relative_to(root).as_posix()
            if len(result) >= MAX_ITEMS:
                raise ActivityCleanupError("activity_cleanup_inventory_limit_exceeded")
            linked = stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 1024)
            kind = "link" if linked else "directory" if stat.S_ISDIR(info.st_mode) else "file" if stat.S_ISREG(info.st_mode) else "other"
            # Windows reports folder sizes that change without any content change
            # (letter 173). The listing already records every child's identity,
            # size and mtime, so folder size and mtime add nothing but churn.
            content = kind != "directory"
            result.append({"relative": relative, "kind": kind, "size": info.st_size if content else None,
                "identity": [info.st_dev, info.st_ino], "mtime_ns": info.st_mtime_ns if content else None,
                "git_metadata": relative == ".git" or relative.startswith(".git/"),
                "possible_secret_config": entry.name.startswith(".env") or entry.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}})
            if kind == "directory":
                stack.append(entry)
    return result


def remaining_inventory(material):
    remaining, newly_created, unsafe = 0, 0, 0
    for scope in material["roots"]:
        root = Path(scope["path"])
        if not root.exists():
            continue
        if _directory_state(root) != scope["state"]:
            unsafe += 1
            continue
        prior = {row["relative"] for row in scope["inventory"]}
        current = _inventory(root)
        remaining += sum(row["kind"] != "directory" for row in current)
        newly_created += sum(row["kind"] != "directory" and row["relative"] not in prior for row in current)
    return {"remaining_file_or_link_count": remaining, "new_file_or_link_count": newly_created,
            "changed_root_count": unsafe, "scope_completion": "empty" if remaining == 0 and unsafe == 0 else "selected_files_only"}


def write_private_plan(candidate, destination):
    path = Path(destination)
    _safe_path(path.parent)
    if path.resolve().is_relative_to(candidate["root"].resolve()):
        raise ActivityCleanupError("activity_cleanup_private_plan_outside_archive_required")
    with path.open("xb") as stream:
        stream.write(encoded(candidate.get("restore", candidate["material"])))
        stream.flush()
        os.fsync(stream.fileno())


def _notify(progress, stage, message, current=None, total=None):
    """Observational only: content-free stage names and counts; never fails the caller."""
    if progress is not None:
        try:
            progress(stage, message, current, total)
        except Exception:
            pass


def _safe_code(value):
    return value if isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", value) else None


def _position(item):
    """v0.4.58 (letter 180): the 1-based parent position, also for an "N-streams" child (never a string count)."""
    match = re.match(r"\d+", str(item.get("number")))
    return int(match.group()) + 1 if match else None


def plan(root, request_path, *, resume=False, key_provider=None, progress=None):
    root = services.require_existing_archive_root(root)
    request_path = _safe_path(Path(request_path))
    if request_path.stat().st_size > MAX_CONTROL_BYTES:
        raise ActivityCleanupError("activity_cleanup_request_too_large")
    raw = request_path.read_bytes()
    try:
        request = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ActivityCleanupError("activity_cleanup_request_invalid") from None
    if (not isinstance(request, dict) or request.get("schema") != SCHEMA
        or set(request) - {"schema", "activity_id", "roots", "items", "remove_empty_directories", "storage"}):
        raise ActivityCleanupError("activity_cleanup_request_invalid")
    activity = request.get("activity_id")
    if not isinstance(activity, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", activity):
        raise ActivityCleanupError("activity_cleanup_activity_id_invalid")
    store = Journal(root, activity, key_provider)
    request_sha = "sha256:" + hashlib.sha256(raw).hexdigest()
    if resume:
        saved = store.read("intent")
        if saved is None or saved["request_sha256"] != request_sha:
            raise ActivityCleanupError("activity_cleanup_resume_request_changed")
        return {"root": root, "material": saved, "journal": store, "public": public_plan(saved), "progress": progress}
    roots = request.get("roots")
    items = request.get("items")
    if not isinstance(roots, list) or not roots or not isinstance(items, list) or not 0 < len(items) <= MAX_ITEMS:
        raise ActivityCleanupError("activity_cleanup_request_invalid")
    scopes = []
    _notify(progress, "activity-cleanup-inventory", "start", 0, len(roots))
    for value in roots:
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise ActivityCleanupError("activity_cleanup_absolute_root_required")
        path = _safe_path(value)
        # WOM's own mutable state is handled by its dedicated lifecycle writers;
        # the archive's AI scratch roots are activity material (letter 173 D).
        # Resolved spellings: a Windows 8.3 alias must not look external.
        real, real_root = path.resolve(), root.resolve()
        if real_root.is_relative_to(real) or (real.is_relative_to(real_root)
                                              and not real.is_relative_to(real_root / "staging")
                                              and not _in_archive_ai_scratch(root, path)):
            raise ActivityCleanupError("activity_cleanup_archive_state_not_external_source")
        if any(path.is_relative_to(scope["path"]) or Path(scope["path"]).is_relative_to(path) for scope in scopes):
            raise ActivityCleanupError("activity_cleanup_overlapping_roots")
        scopes.append({"path": str(path), "state": _directory_state(path), "git": _git_inventory(path), "inventory": _inventory(path)})
        _notify(progress, "activity-cleanup-inventory", "root", len(scopes), len(roots))
    _notify(progress, "activity-cleanup-inventory", "done", len(scopes), len(roots))
    selected, blockers, seen = [], [], set()
    _notify(progress, "activity-cleanup-hash", "start", 0, len(items))
    for number, item in enumerate(items):
        if (not isinstance(item, dict) or item.get("role") not in ROLES
            or set(item) - {"path", "role", "reason", "disposition", "discard_intent"}):
            raise ActivityCleanupError("activity_cleanup_classification_required")
        if not isinstance(item.get("path"), str) or not Path(item["path"]).is_absolute():
            raise ActivityCleanupError("activity_cleanup_absolute_file_required")
        path = _safe_path(item["path"])
        matching = [scope for scope in scopes if path != Path(scope["path"]) and path.is_relative_to(scope["path"])]
        if len(matching) != 1 or path == request_path or str(path).casefold() in seen:
            raise ActivityCleanupError("activity_cleanup_selection_invalid")
        seen.add(str(path).casefold())
        role, disposition = item["role"], item.get("disposition", "preserve")
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 4096:
            raise ActivityCleanupError("activity_cleanup_classification_reason_required")
        if role == "unknown" and disposition != "retain":
            blockers.append("activity_cleanup_unknown_classification")
        if disposition not in {"preserve", "discard", "retain"}:
            raise ActivityCleanupError("activity_cleanup_disposition_invalid")
        if role == "temporary" and disposition == "preserve":
            blockers.append("activity_cleanup_temporary_upload_requires_reclassification")
        if disposition == "discard" and (role != "temporary" or item.get("discard_intent") is not True):
            blockers.append("activity_cleanup_explicit_temporary_discard_required")
        state = file_state(path)
        from .activity_cleanup_streams import inventory as stream_inventory
        streams = stream_inventory(path, state)
        selected.append({"number": number, "path": str(path), "root": matching[0]["path"],
            "role": role, "reason": reason, "disposition": disposition, "state": state,
            "object_id": "sha256:" + state["sha256"], "alternate_streams": streams})
        _notify(progress, "activity-cleanup-hash", "file", len(selected), len(items))
    _notify(progress, "activity-cleanup-hash", "done", len(selected), len(items))
    in_archive = [item for item in selected if _in_archive_ai_scratch(root, Path(item["path"]))]
    if in_archive:
        # Deleting a file a draft or zet still points at would break that note;
        # mint-time cleanup or ai-scratch-gc owns those references.
        referenced = _zet_referenced_scratch(root)
        for item in in_archive:
            relative = Path(item["path"]).resolve().relative_to(root.resolve()).as_posix().casefold()
            if relative in referenced:
                blockers.append("activity_cleanup_scratch_still_referenced_by_zet")
    directories = []
    directory_requests = request.get("remove_empty_directories", [])
    if not isinstance(directory_requests, list) or any(not isinstance(v, str) or not Path(v).is_absolute() for v in directory_requests):
        raise ActivityCleanupError("activity_cleanup_absolute_directory_required")
    for value in directory_requests:
        path = _safe_path(value)
        if not any(path.is_relative_to(scope["path"]) for scope in scopes):
            raise ActivityCleanupError("activity_cleanup_directory_outside_selection")
        directories.append({"path": str(path), "state": _directory_state(path)})
    for scope in scopes:
        if scope["git"].get("external_worktree_dependency"):
            # Never remove shared Git metadata while another checkout depends on it.
            # Ordinary source files remain individually selectable and preservable.
            if any(Path(item["path"]).is_relative_to(Path(scope["path"]) / ".git") for item in selected):
                blockers.append("activity_cleanup_shared_git_metadata_requires_worktree_detach")
    storage = request.get("storage", {})
    allowed_storage = {"provider_kind", "store_ref", "endpoint_host", "bucket", "region", "access_key_id_ref", "secret_access_key_ref"}
    if not isinstance(storage, dict) or set(storage) - allowed_storage or any(not isinstance(v, str) for v in storage.values()):
        raise ActivityCleanupError("activity_cleanup_storage_arguments_invalid")
    material = {"schema": "wom-kit/activity-cleanup-intent/v2", "activity_id": activity,
        "archive_id": services.read_archive_id(root), "request_sha256": request_sha,
        "roots": scopes, "items": selected, "directories": directories, "storage": storage,
        "blockers": sorted(set(blockers))}
    old = store.read("intent")
    if old is not None:
        raise ActivityCleanupError("activity_cleanup_use_resume_for_existing_activity")
    return {"root": root, "material": material, "journal": store, "public": public_plan(material), "progress": progress}


def public_plan(material):
    return {"schema": "wom-kit/activity-cleanup-result/v1", "ok": not material["blockers"],
        "dry_run": True, "plan_sha256": digest(material), "item_count": len(material["items"]),
        "selected_bytes": sum(i["state"]["size"] for i in material["items"]),
        "alternate_stream_count": sum(len(i.get("alternate_streams", [])) for i in material["items"]),
        "alternate_stream_bytes": sum(s["size"] for i in material["items"] for s in i.get("alternate_streams", [])),
        "classification": {"preserve_count": sum(i["disposition"] == "preserve" for i in material["items"]),
            "discard_without_upload_count": sum(i["disposition"] == "discard" for i in material["items"]),
            "retain_without_upload_count": sum(i["disposition"] == "retain" for i in material["items"]),
            "preserve_file_bytes": sum(i["state"]["size"] for i in material["items"] if i["disposition"] == "preserve"),
            "discard_file_bytes": sum(i["state"]["size"] for i in material["items"] if i["disposition"] == "discard"),
            "retain_file_bytes": sum(i["state"]["size"] for i in material["items"] if i["disposition"] == "retain"),
            "file_bytes_are_not_deduplicated_remote_or_reclaimed_disk_bytes": True},
        "items": [{"number": i["number"], "role": i["role"], "disposition": i["disposition"],
                   "size_bytes": i["state"]["size"]} for i in material["items"]],
        "git": [s["git"] for s in material["roots"]], "blockers": material["blockers"],
        "inventory": {"file_or_link_count": sum(row["kind"] != "directory" for s in material["roots"] for row in s["inventory"]),
            "selected_file_count": len(material["items"]),
            "git_metadata_file_count": sum(row["git_metadata"] and row["kind"] != "directory" for s in material["roots"] for row in s["inventory"]),
            "possible_secret_config_count": sum(row["possible_secret_config"] for s in material["roots"] for row in s["inventory"]),
            "classification_basis": "explicit_request_reasons", "filename_based_disposal": False},
        "deletion_supported": os.name == "nt", "whole_folder_preservation_claimed": False,
        "private_values_echoed": False, "writes_performed": False}


def approval_binding(candidate):
    sha = digest(candidate["material"])
    return ExactOperationApprovalBinding(operation=ExactHumanApprovalOperation.activity_cleanup,
        plan_sha256=sha, target_binding_sha256=digest(candidate["material"]["items"]),
        warning_codes=(), review_binding_codes=("activity_cleanup_exact_files", "activity_cleanup_remote_preservation"))


class Journal:
    def __init__(self, root, activity, key_provider=None):
        self.root, self.activity, self.key_provider = root, activity, key_provider
    @contextmanager
    def writer_lock(self):
        import msvcrt
        parent = services.archive_internal_path(self.root, ROOT + "/" + self.activity)
        parent.mkdir(parents=True, exist_ok=True)
        _safe_path(parent)
        lock = parent / "writer.lock"
        with lock.open("a+b") as stream:
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ActivityCleanupError("activity_cleanup_writer_active") from None
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def _mac(self, value):
        from .operation_cancellation import ACTIVE_CLAIM
        active = ACTIVE_CLAIM.get()
        if active is not None:
            return active.activity_cleanup_mac(self.root, encoded(value))
        from .exact_human_approval_workflow import _production_key_provider
        provider = self.key_provider or _production_key_provider()
        return provider.use_key(self.root, lambda key: hmac.new(bytes(key), DOMAIN + encoded(value), hashlib.sha256).hexdigest(), create_if_missing=False)
    def relative(self, name, *, base=None):
        if not re.fullmatch(r"[a-z0-9-]+", name):
            raise ActivityCleanupError("activity_cleanup_journal_name_invalid")
        return (base or ROOT) + "/" + self.activity + "/" + name + ".json"
    def _require_private(self, relative):
        from .operator_feedback_body import _require_effective_gitignore
        try:
            _require_effective_gitignore(self.root, relative)
        except Exception:
            raise ActivityCleanupError("activity_cleanup_private_journal_not_ignored") from None
    def read(self, name):
        path = services.archive_internal_path(self.root, self.relative(name))
        legacy = services.archive_internal_path(self.root, self.relative(name, base=LEGACY_ROOT))
        documents = []
        for candidate in (path, legacy):
            if os.path.lexists(candidate):
                documents.append(self._read_signed(candidate))
        if not documents:
            return None
        if any(encoded(value) != encoded(documents[0]) for value in documents[1:]):
            raise ActivityCleanupError("activity_cleanup_journal_locations_conflict")
        return documents[0]

    def _read_signed(self, path):
        try:
            _safe_path(path)
            if path.stat().st_size > MAX_CONTROL_BYTES:
                raise ValueError()
            signed = json.loads(path.read_bytes())
            if not hmac.compare_digest(signed["mac"], self._mac(signed["document"])):
                raise ValueError()
            return signed["document"]
        except Exception:
            raise ActivityCleanupError("activity_cleanup_journal_invalid") from None
    def write(self, name, document):
        from .object_storage_offload import _create_or_match_document
        self._require_private(self.relative(name))
        raw = encoded({"document": document, "mac": self._mac(document)})
        _create_or_match_document(self.root, self.relative(name), raw,
            failure_code="object_storage_offload_receipt_conflict", max_bytes=MAX_CONTROL_BYTES)


class ReconciliationJournal:
    """Append new approval/intent without changing original item evidence."""
    def __init__(self, original, identity):
        self.original, self.identity = original, identity
        self.root, self.activity, self.key_provider = original.root, original.activity, original.key_provider

    def writer_lock(self):
        return self.original.writer_lock()

    def _name(self, name):
        if name in {"intent", "approval", "completed"} or name.startswith("attempt-"):
            return "reconcile-" + self.identity + "-" + name
        return name

    def read(self, name):
        return self.original.read(self._name(name))

    def write(self, name, document):
        return self.original.write(self._name(name), document)


def reconcile_plan(candidate, *, credential_refs=None):
    """Reconcile authenticated old intent with live unfinished files only.

    Never reinterpret a missing item as unexecuted. Completed files are neither
    opened nor imported, including when a new file now occupies the old name.
    A new parent approval explicitly includes newly observed ADS preservation.
    Original per-item and child-operation evidence remains the resume authority.
    """
    from .activity_cleanup_streams import inventory as stream_inventory
    import copy
    original, journal = candidate["material"], candidate["journal"]
    if journal.read("intent") != original:
        raise ActivityCleanupError("activity_cleanup_reconcile_original_invalid")
    material = copy.deepcopy(original)
    rebind = None
    if credential_refs is not None:
        # v0.4.53 (beta letter 177): only the two credential refs may change,
        # e.g. from env: refs bound to an ended process to OS-keychain refs.
        # Provider, store, endpoint, bucket and region stay the original's, so
        # the preserved remote identity and every child proof still match.
        storage = material.get("storage") or {}
        if (type(credential_refs) is not dict
                or set(credential_refs) != {"access_key_id_ref", "secret_access_key_ref"}
                or not storage.get("access_key_id_ref") or not storage.get("secret_access_key_ref")):
            raise ActivityCleanupError("activity_cleanup_credential_rebind_invalid")
        blockers = []
        services._object_storage_validate_credential_refs(
            access_key_id_ref=credential_refs["access_key_id_ref"],
            secret_access_key_ref=credential_refs["secret_access_key_ref"], blockers=blockers)
        if blockers:
            raise ActivityCleanupError("activity_cleanup_credential_rebind_invalid")
        rebind = {"original_refs_sha256": digest([storage["access_key_id_ref"], storage["secret_access_key_ref"]]),
                  "rebound_refs_sha256": digest([credential_refs["access_key_id_ref"],
                                                 credential_refs["secret_access_key_ref"]]),
                  "remote_identity_unchanged": True}
        storage["access_key_id_ref"] = credential_refs["access_key_id_ref"]
        storage["secret_access_key_ref"] = credential_refs["secret_access_key_ref"]
        material["storage"] = storage
    observations, held = [], []
    for item in material["items"]:
        name, path = "item-" + str(item["number"]), Path(item["path"])
        deleted = journal.read(name + "-deleted")
        if deleted:
            if deleted != {"number": item["number"], "state": "absent_after_bound_delete_intent"}:
                raise ActivityCleanupError("activity_cleanup_deleted_record_invalid")
            observations.append({"number": item["number"], "state": "completed_no_reprocessing"})
            continue
        pending = journal.read(name + "-delete-intent")
        if not os.path.lexists(path):
            state = "completion_record_pending" if (pending and pending.get("number") == item["number"]
                and pending.get("state") == item["state"]) else "missing_without_evidence"
            if state == "missing_without_evidence":
                held.append(item["number"])
            observations.append({"number": item["number"], "state": state})
            continue
        try:
            if file_state(path) != item["state"]:
                raise ActivityCleanupError("activity_cleanup_file_changed")
            current_streams = stream_inventory(path, item["state"])
            if "alternate_streams" in item and item["alternate_streams"] != current_streams:
                raise ActivityCleanupError("activity_cleanup_streams_changed")
            item["alternate_streams"] = current_streams
            observations.append({"number": item["number"], "state": "pending_recovery"})
        except (ActivityCleanupError, OSError):
            held.append(item["number"])
            observations.append({"number": item["number"], "state": "changed_or_unavailable_retained"})
    material.update(schema="wom-kit/activity-cleanup-intent/v2",
        reconciliation={"original_intent_sha256": digest(original), "observations": observations,
                        "retained_item_numbers": held, "original_item_receipts_reused": True,
                        **({"credential_rebind": rebind} if rebind is not None else {})})
    identity = digest(material)[7:]
    public = public_plan(material)
    public["reconciliation"] = material["reconciliation"]
    public["pending_recovery_count"] = sum(row["state"] in {"pending_recovery", "completion_record_pending"} for row in observations)
    public["completed_items_not_reprocessed"] = sum(row["state"] == "completed_no_reprocessing" for row in observations)
    pending_numbers = {row["number"] for row in observations if row["state"] == "pending_recovery"}
    public["pending_item_diagnosis"] = diagnose_pending_items(
        candidate["root"], journal, [item for item in original["items"] if item["number"] in pending_numbers])
    return {**candidate, "material": material, "journal": ReconciliationJournal(journal, identity), "public": public}


DIAGNOSIS_LIMIT = 200


def _upload_original_resume_check(root, journal, item):
    """Read-only: whether the saved original upload's manifest preconditions still hold."""
    from types import SimpleNamespace
    from . import object_storage_upload_exact as upload
    probe = SimpleNamespace(root=root, journal=journal)
    _label, saved, _successor = OfficialPreservationBackend._child_label(probe, item, "upload")
    if not saved:
        return "no_original_upload"
    control = services.archive_internal_path(root, upload._control_relative(saved["manifest_sha256"]))
    if not os.path.lexists(control):
        return "original_control_absent"
    try:
        plan = upload.load_object_storage_upload_plan(root, manifest_sha256=saved["manifest_sha256"])
    except Exception as error:
        return _safe_code(getattr(error, "code", None)) or "original_control_unreadable"
    try:
        upload._assert_target_preimages(plan)
    except Exception as error:
        return _safe_code(getattr(error, "code", None)) or "original_preconditions_changed"
    return "resumable_preconditions_match"


def diagnose_pending_items(root, journal, items):
    """v0.4.58 (letter 180): read-only, content-free diagnosis of unfinished items.

    Names the step each item reached, whether its child control file and
    child claims exist, and the route --reconcile takes. No remote request is
    made here; remote bytes are checked by the approved run. Never a path,
    object id or provider message. Not part of the approval binding.
    """
    from types import SimpleNamespace
    from . import object_storage_upload_exact as upload, object_storage_offload as offload
    probe = SimpleNamespace(root=root, journal=journal)
    rows, routes = [], {}
    try:
        for item in items[:DIAGNOSIS_LIMIT]:
            name = "item-" + str(item["number"])
            row = {"number": item["number"], "steps_recorded": [step for step in
                   ("chain-control", "intake", "upload-control", "preserved", "offload-control", "delete-intent")
                   if journal.read(name + "-" + step) is not None]}
            children = {}
            for operation, module in (("upload", upload), ("offload", offload)):
                _label, saved, successor = OfficialPreservationBackend._child_label(probe, item, operation)
                if not saved:
                    continue
                control = services.archive_internal_path(root, module._control_relative(saved["manifest_sha256"]))
                statuses = {}
                for claim in OfficialPreservationBackend._child_claims(probe, saved["context_sha256"]):
                    statuses[claim["status"]] = statuses.get(claim["status"], 0) + 1
                children[operation] = {"control_file": "present" if os.path.lexists(control) else "absent",
                    "claims": statuses, "attempts": int(successor.rsplit("-r", 1)[1])}
            row["child_steps"] = children
            offload_row, upload_row = children.get("offload"), children.get("upload")
            if offload_row and offload_row["control_file"] == "absent":
                if offload_row["claims"].get("succeeded"):
                    route = "offload_completed_control_absent_complete_after_remote_proof"
                elif OfficialPreservationBackend._offload_had_no_effect(probe, item):
                    route = "offload_had_no_effect_restart_offload"
                else:
                    route = "offload_effects_unproven_file_kept"
            elif offload_row:
                route = "offload_resume_original_child"
            elif upload_row:
                route = "upload_complete_after_remote_proof_or_resume_original_child"
                # v0.4.60: say up front when the original upload cannot resume
                # (its manifest preconditions changed); local check only.
                if upload_row["claims"].get("started") and not upload_row["claims"].get("succeeded"):
                    check = _upload_original_resume_check(root, journal, item)
                    upload_row["original_resume_check"] = check
                    if check != "resumable_preconditions_match":
                        route = ("upload_complete_after_remote_proof_or_upload_again_from_local_bytes"
                                 if OfficialPreservationBackend._local_object_exact(probe, item)
                                 else "upload_original_not_resumable_local_bytes_missing_file_kept")
            elif row["steps_recorded"]:
                route = "intake_resume_original_child"
            else:
                route = "not_started_process_from_start"
            row["reconcile_route"] = route
            routes[route] = routes.get(route, 0) + 1
            rows.append(row)
    except Exception as error:
        code = getattr(error, "code", None)
        return {"state": "diagnosis_unavailable",
                "code": code if isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", code)
                else "activity_cleanup_diagnosis_failed"}
    return {"state": "read_only_diagnosis", "remote_bytes_checked_now": False, "items": rows,
            "route_counts": routes, "diagnosed_count": len(rows), "not_diagnosed_count": max(0, len(items) - len(rows))}


def _restore_request_label(number, destination):
    return "restore-request-" + digest([number, str(Path(destination))])[7:]


def restore_plan(candidate, *, number, destination, resume=False):
    if type(number) is not int or number < 0 or not isinstance(destination, str) or not Path(destination).is_absolute():
        raise ActivityCleanupError("activity_cleanup_restore_arguments_invalid")
    selected = [item for item in candidate["material"]["items"] if item["number"] == number]
    if len(selected) != 1:
        raise ActivityCleanupError("activity_cleanup_restore_item_unknown")
    item = selected[0]
    preserved = candidate["journal"].read("item-" + str(number) + "-preserved")
    if not preserved or preserved.get("object_id") != item["object_id"] or preserved.get("size") != item["state"]["size"]:
        raise ActivityCleanupError("activity_cleanup_restore_preservation_missing")
    streams = candidate["journal"].read("item-" + str(number) + "-streams")
    recorded_inventory = candidate["journal"].read("item-" + str(number) + "-stream-inventory")
    if "alternate_streams" not in item and streams is None and recorded_inventory is None:
        raise ActivityCleanupError("activity_cleanup_restore_stream_inventory_unknown")
    if streams is not None and streams.get("parent_object_id") != item["object_id"]:
        raise ActivityCleanupError("activity_cleanup_stream_evidence_changed")
    if item.get("alternate_streams") and (streams is None or streams.get("streams") != item["alternate_streams"]):
        raise ActivityCleanupError("activity_cleanup_stream_preservation_missing")
    target = Path(destination)
    if not target.name or ":" in target.name:
        raise ActivityCleanupError("activity_cleanup_restore_arguments_invalid")
    _safe_path(target.parent)
    if target.resolve().is_relative_to(candidate["root"].resolve()):
        raise ActivityCleanupError("activity_cleanup_restore_external_destination_required")
    if os.path.lexists(target) and not resume:
        raise ActivityCleanupError("activity_cleanup_restore_destination_exists")
    material = {"schema": "wom-kit/activity-cleanup-restore-intent/v1",
        "activity_id": candidate["material"]["activity_id"], "number": number,
        "destination": str(target), "parent_state": _directory_state(target.parent),
        "body_object_id": item["object_id"], "body_state": item["state"],
        "streams": streams["streams"] if streams else [], "stream_item": streams["item"] if streams else None}
    saved = None
    if resume:
        saved = candidate["journal"].read(_restore_request_label(number, destination))
        if not saved or saved.get("intent") != material:
            raise ActivityCleanupError("activity_cleanup_restore_original_missing_or_changed")
    return {**candidate, "restore": material,
        "restore_approval": saved,
        "restore_public": {"ok": True, "dry_run": True, "plan_sha256": digest(material), "item_number": number,
            "body_bytes": item["state"]["size"], "alternate_stream_count": len(material["streams"]),
            "new_file_only": True, "writes_performed": False, "private_values_echoed": False}}


def restore_binding(candidate):
    material = candidate["restore"]
    return ExactOperationApprovalBinding(operation=ExactHumanApprovalOperation.activity_cleanup,
        plan_sha256=digest(material), target_binding_sha256=digest(material), warning_codes=(),
        review_binding_codes=("activity_cleanup_restore_new_file",))


def restore_item(candidate, *, reviewer, claim, backend):
    from .operation_target_leases import TargetLeases
    with TargetLeases(candidate["root"], [("file", candidate["restore"]["destination"])]):
        try:
            return _restore_item_held(candidate, reviewer=reviewer, claim=claim, backend=backend)
        except Exception as error:
            from .storage_cancellation import is_cancelled
            if not is_cancelled(error):
                raise
            journal, material = candidate["journal"], candidate["restore"]
            result = {**candidate["restore_public"], "ok": False, "dry_run": False,
                "state": "cancelled_at_checkpoint", "cause_code": "operation_cancelled_at_checkpoint",
                "cause_stage": "activity_cleanup_restore", "cancel_requested": True, "cancel_acknowledged": True,
                "writes_performed": True, "provider_request_in_flight": False, "process_killed": False,
                "publication_recorded": journal.read("restore-" + digest(material)[7:]) is not None,
                "child_operation_terminal_verified": False, "child_recovery": getattr(error, "child_recovery", None),
                "same_claim_resume_supported": True,
                "next_safe_actions": ["preserve_original_restore_request_and_child_controls", "resume_original_activity_restore"]}
            journal.write("attempt-" + uuid.uuid4().hex, result)
            return result


def _restored_state_matches(candidate, path, approved):
    from . import activity_cleanup_streams as streams
    material = candidate["restore"]
    actual = file_state(path)
    if actual != approved or streams.inventory(path, actual) != material["streams"]:
        raise ActivityCleanupError("activity_cleanup_restore_destination_changed")


def verify_restore_completion(candidate):
    material, journal = candidate["restore"], candidate["journal"]
    final = journal.read("restore-" + digest(material)[7:])
    staged = journal.read("restore-publish-" + digest(material)[7:])
    if not final or final.get("intent") != material or not staged:
        raise ActivityCleanupError("activity_cleanup_restore_completion_missing")
    _restored_state_matches(candidate, Path(material["destination"]), staged["state"])
    return {**candidate["restore_public"], **final["result"], "dry_run": False,
        "writes_performed": False, "replayed_completed_record": True}


def _restore_item_held(candidate, *, reviewer, claim, backend):
    from . import activity_cleanup_streams as streams
    from .operation_cancellation import checkpoint
    material = candidate["restore"]
    binding = restore_binding(candidate)
    context = binding.context(archive_id=services.read_archive_id(candidate["root"]), reviewer_claim=reviewer)
    services._require_exact_human_operation_approval(candidate["root"], binding, reviewer_claim=reviewer,
        expected_plan_sha256=binding.plan_sha256, expected_target_binding_sha256=binding.target_binding_sha256, claim=claim)
    claim.assert_ready_for_context(context)
    target = Path(material["destination"])
    journal = candidate["journal"]
    identity = digest(material)[7:]
    approval = {"intent": material, "approval_id": claim.public_summary()["approval_id"]}
    journal.write(_restore_request_label(material["number"], str(target)), approval)
    if isinstance(backend, OfficialPreservationBackend):
        backend.verifier.proof_store.capture_active_claim()
    checkpoint()
    if _directory_state(target.parent) != material["parent_state"]:
        raise ActivityCleanupError("activity_cleanup_restore_destination_changed")
    staged = journal.read("restore-publish-" + identity)
    if staged:
        if staged.get("intent_sha256") != digest(material) or staged.get("approval_id") != approval["approval_id"]:
            raise ActivityCleanupError("activity_cleanup_restore_evidence_changed")
        pending = Path(staged["temporary"])
        if pending.parent != target.parent or not re.fullmatch(r"\.wom-restore-[0-9a-f]{32}\.partial", pending.name):
            raise ActivityCleanupError("activity_cleanup_restore_evidence_changed")
        if os.path.lexists(target):
            _restored_state_matches(candidate, target, staged["state"])
        else:
            _restored_state_matches(candidate, pending, staged["state"])
            claim.assert_ready_for_context(context)
            from .object_storage_restore import _atomic_move_file_no_replace
            with services._activity_group_bound_directory_chain(Path(target.anchor), target.parent):
                _atomic_move_file_no_replace(pending, target)
            _restored_state_matches(candidate, target, staged["state"])
        result = {"ok": True, "body_verified": True, "alternate_streams_verified": len(material["streams"]),
            "new_file_created": True, "recovered_original_publication": True}
        with streams.hold(target, staged["state"], expected=material["streams"]) as (_rows, _handles, verify):
            claim.assert_ready_for_context(context)
            verify()
            journal.write("restore-" + identity, {"intent": material, "result": result,
                "approval_id": approval["approval_id"]})
            verify()
        return {**candidate["restore_public"], **result, "dry_run": False, "writes_performed": True}
    if os.path.lexists(target):
        raise ActivityCleanupError("activity_cleanup_restore_destination_changed")
    item = next(item for item in candidate["material"]["items"] if item["number"] == material["number"])
    body = backend.restore_object(item)
    checkpoint()
    if material["stream_item"] is not None:
        bundle = backend.restore_object(material["stream_item"])
        checkpoint()
    else:
        # Empty ADS inventory is still verified by the same restore path.
        bundle = services.archive_internal_path(candidate["root"], ROOT + "/" + candidate["material"]["activity_id"]
            + "/restore-empty-" + material["body_object_id"][7:] + ".zip")
        streams.build_bundle(body, file_state(body), [], bundle)
    claim.assert_ready_for_context(context)
    if _directory_state(target.parent) != material["parent_state"]:
        raise ActivityCleanupError("activity_cleanup_restore_destination_changed")
    def before_publish(temporary, state):
        claim.assert_ready_for_context(context)
        journal.write("restore-publish-" + identity, {"intent_sha256": digest(material),
            "temporary": str(temporary), "state": state, "approval_id": approval["approval_id"]})
    result = streams.restore_new(body, bundle, target, material["body_state"], material["streams"],
        before_publish=before_publish)
    staged = journal.read("restore-publish-" + identity)
    with streams.hold(target, staged["state"], expected=material["streams"]) as (_rows, _handles, verify):
        claim.assert_ready_for_context(context)
        verify()
        journal.write("restore-" + identity, {"intent": material, "result": result,
            "approval_id": claim.public_summary()["approval_id"]})
        verify()
    return {**candidate["restore_public"], **result, "dry_run": False, "writes_performed": True}


def status(candidate):
    """Read authenticated intent and item evidence without entering any writer.

    Preserved receipts describe a past verification, never a fresh remote check.
    Missing files without bound deletion evidence remain unresolved effects.
    """
    material, journal = candidate["material"], candidate["journal"]
    approval = journal.read("approval")
    expected = approval_binding(candidate)
    approval_matches = bool(approval and approval.get("plan_sha256") == expected.plan_sha256
                            and approval.get("target_binding_sha256") == expected.target_binding_sha256)
    counts = {"completed": 0, "pending": 0, "held": 0, "missing_without_evidence": 0,
              "replacement_retained": 0, "preserved_receipt": 0}
    results = []
    for item in material["items"]:
        label = "item-" + str(item["number"])
        deleted = journal.read(label + "-deleted")
        pending = journal.read(label + "-delete-intent")
        preserved = journal.read(label + "-preserved")
        has_path = os.path.lexists(item["path"])
        row = {"number": item["number"], "state": "pending", "code": None,
               "preserved_receipt_present": bool(preserved),
               "remote_bytes_verified_now": False}
        counts["preserved_receipt"] += bool(preserved)
        if deleted:
            if deleted.get("number") != item["number"] or deleted.get("state") != "absent_after_bound_delete_intent":
                row.update(state="held", code="activity_cleanup_deleted_record_invalid")
            else:
                row["state"] = "replacement_retained" if has_path else "completed"
        elif not has_path:
            if pending and pending.get("number") == item["number"] and pending.get("state") == item["state"]:
                row.update(state="held", code="activity_cleanup_delete_completion_requires_reconcile")
            else:
                row.update(state="missing_without_evidence", code="activity_cleanup_missing_without_delete_intent")
        else:
            try:
                if file_state(item["path"]) != item["state"]:
                    row.update(state="held", code="activity_cleanup_file_changed")
            except (ActivityCleanupError, OSError):
                row.update(state="held", code="activity_cleanup_file_state_unavailable")
        controls = {}
        for operation in ("chain", "upload", "offload"):
            control = journal.read(label + "-" + operation + "-control")
            controls[operation] = "recorded_effects_not_reconciled" if control else "not_recorded_effects_unknown"
        row["child_evidence"] = controls
        counts[row["state"]] += 1
        results.append(row)
    complete = counts["completed"] == len(material["items"])
    total = len(material["items"])
    freed = sum(int((item.get("state") or {}).get("size") or 0)
                for item, row in zip(material["items"], results) if row["state"] == "completed")
    remaining_bytes = sum(int((item.get("state") or {}).get("size") or 0)
                          for item, row in zip(material["items"], results) if row["state"] != "completed")
    # v0.4.56 (beta letter 179): say separately how far each part of the
    # person's task got; a successful install or synthetic test is not this.
    boundaries = {
        "remote_verification": {
            "state": "past_receipts_only",
            "items_with_preservation_receipt": counts["preserved_receipt"], "items_total": total,
            "remote_bytes_verified_now": False,
        },
        "original_cleanup": {
            "state": "complete" if complete else "partial",
            "completed": counts["completed"], "remaining": total - counts["completed"],
            "held": counts["held"], "missing_without_evidence": counts["missing_without_evidence"],
        },
        "local_space": {"bytes_freed_by_completed_items": freed, "bytes_still_local_in_remaining_items": remaining_bytes},
        "git_backup": {"state": "not_covered_by_this_command",
                       "next_action": "archive git-backup-plan <archive-root> --dry-run"},
        "closure": {"state": "selected_files_completed" if complete else "open"},
        "cost": {"state": "not_measured_by_this_command"},
    }
    return {"schema": "wom-kit/activity-cleanup-status/v1", "ok": True, "dry_run": True,
            "completion_boundaries": boundaries,
            "state": "selected_files_completed" if complete else "partial",
            "plan_sha256": digest(material), "approval_evidence_matches": approval_matches,
            "counts": counts, "items": results, "remaining": remaining_inventory(material),
            "whole_folder_cleanup_complete": False, "remote_bytes_verified_now": False,
            "writes_performed": False, "private_values_echoed": False,
            "next_action": "review_remaining_scope" if complete else "reconcile_authenticated_item_evidence"}


def execute(candidate, *, reviewer, claim, backend):
    # v0.4.59 (letter 180): non-overlapping timing of where the processing
    # time went (provider requests, manifest reads, index projection, intake,
    # local hashing, child claims, lock waits, child steps, unattributed).
    with work_timing.recording() as recorder:
        result = _execute(candidate, reviewer=reviewer, claim=claim, backend=backend)
    measurements = result.get("measurements") if isinstance(result, dict) else None
    if isinstance(measurements, dict):
        measurements["work_timing"] = recorder.summary(
            measurements.get("processing_seconds_including_child_waits") or 0.0)
    return result


def _execute(candidate, *, reviewer, claim, backend):
    if os.name != "nt":
        raise ActivityCleanupError("activity_cleanup_native_delete_not_supported")
    from .operation_target_leases import TargetLeases
    _notify(candidate.get("progress"), "activity-cleanup-items", "waiting-for-activity-writer")
    with TargetLeases(candidate["root"], [("activity", candidate["material"]["activity_id"])]) as leases:
        candidate["activity_writer_wait_seconds"] = leases.wait_seconds
        with candidate["journal"].writer_lock():
            return _execute_locked(candidate, reviewer=reviewer, claim=claim, backend=backend)


def _execute_locked(candidate, *, reviewer, claim, backend):
    """Backend uses the official intake/upload writers; no raw provider deletion."""
    from .legacy_cleanup_bound_delete import _delete_exact_approved_file, _delete_exact_approved_empty_directory
    from .operation_cancellation import checkpoint, OperationCancelled
    if os.name != "nt":
        raise ActivityCleanupError("activity_cleanup_native_delete_not_supported")
    material, root, journal = candidate["material"], candidate["root"], candidate["journal"]
    execution_started = time.monotonic()
    if material["blockers"]:
        raise ActivityCleanupError("activity_cleanup_plan_blocked")
    binding = approval_binding(candidate)
    context = binding.context(archive_id=material["archive_id"], reviewer_claim=reviewer)
    def authorize():
        claim.assert_ready_for_context(context)
        summary = claim.public_summary()
        if summary.get("approval_mechanism") == PERMISSION_INTERACTIVE_INTENT_MECHANISM:
            from .exact_human_approval_workflow import _resolved_session_permission, _UNSET_SESSION_PERMISSION
            grant, _ = _resolved_session_permission(root, _UNSET_SESSION_PERMISSION, context)
            if grant is None:
                raise ActivityCleanupError("activity_cleanup_session_permission_expired")
    services._require_exact_human_operation_approval(root, binding,
        reviewer_claim=reviewer, expected_plan_sha256=binding.plan_sha256,
        expected_target_binding_sha256=binding.target_binding_sha256, claim=claim)
    authorize()
    if isinstance(backend, OfficialPreservationBackend):
        backend.verifier.proof_store.capture_active_claim()
    # Immutable first intent is the only resume source; edited requests cannot
    # silently substitute different paths, roles or file identities.
    journal.write("intent", material)
    approval_record = {"approval_id": claim.public_summary()["approval_id"],
        "plan_sha256": binding.plan_sha256, "target_binding_sha256": binding.target_binding_sha256,
        "mechanism": claim.public_summary().get("approval_mechanism")}
    first_approval = journal.read("approval")
    if (first_approval is not None and first_approval.get("approval_id") != approval_record["approval_id"]
            and first_approval.get("plan_sha256") == binding.plan_sha256
            and first_approval.get("target_binding_sha256") == binding.target_binding_sha256):
        # v0.4.58 (letter 180): the same reconcile approved again (items still
        # pending) conflicted with the first approval record and stopped before
        # any item. Keep the first record and add this approval as an attempt.
        journal.write("attempt-" + re.sub(r"[^a-z0-9]+", "-", str(approval_record["approval_id"]).lower())[:80]
                      + "-approval", approval_record)
    else:
        journal.write("approval", approval_record)
    results = []
    cancelled = False
    child_interruption = None
    def stop_requested():
        try:
            checkpoint()
        except OperationCancelled:
            return True
        return False
    progress = candidate.get("progress")
    # v0.4.59 (letter 180): items already completed are skipped in their own
    # stage, so the item count and ETA cover only the real remaining work.
    completed_before = {item["number"] for item in material["items"]
                        if journal.read("item-" + str(item["number"]) + "-deleted")}
    work_total, work_position = len(material["items"]) - len(completed_before), 0
    _notify(progress, "activity-cleanup-skip-completed", "start", 0, len(completed_before))
    _notify(progress, "activity-cleanup-skip-completed", "done", len(completed_before), len(completed_before))
    _notify(progress, "activity-cleanup-items", "start", 0, work_total)
    for item in material["items"]:
        if stop_requested():
            cancelled = True
            break
        number, path = item["number"], Path(item["path"])
        name = "item-" + str(number)
        deleted = journal.read(name + "-deleted") if number in completed_before else None
        if deleted:
            results.append({"number": number, "state": "already_deleted" if not os.path.lexists(path) else "replacement_retained"})
            continue
        work_position += 1
        if backend is not None:
            backend.progress_position = (work_position, work_total)
        _notify(progress, "activity-cleanup-items", "file", work_position, work_total)
        if number in material.get("reconciliation", {}).get("retained_item_numbers", []):
            results.append({"number": number, "state": "retained", "code": "activity_cleanup_reconcile_item_requires_review"})
            continue
        if item["disposition"] == "retain":
            results.append({"number": number, "state": "retained", "code": "activity_cleanup_classification_retained_no_upload"})
            continue
        try:
            item_started = time.monotonic()
            authorize()
            pending = journal.read(name + "-delete-intent")
            if not os.path.lexists(path):
                if not pending:
                    raise ActivityCleanupError("activity_cleanup_missing_without_delete_intent")
                journal.write(name + "-deleted", {"number": number, "state": "absent_after_bound_delete_intent"})
                results.append({"number": number, "state": "already_absent_after_intent"})
                continue
            if file_state(path) != item["state"]:
                raise ActivityCleanupError("activity_cleanup_file_changed")
            if "alternate_streams" in item:
                from .activity_cleanup_streams import inventory as stream_inventory
                if stream_inventory(path, item["state"]) != item["alternate_streams"]:
                    raise ActivityCleanupError("activity_cleanup_streams_changed")
                journal.write(name + "-stream-inventory", {"object_id": item["object_id"],
                    "streams": item["alternate_streams"]})
            _assert_no_new_git_worktree_dependency(item)
            if item["disposition"] == "preserve":
                _notify(progress, "activity-cleanup-items", "preserving", work_position, work_total)
                backend.preserve(item, journal)
                checkpoint()
                authorize()
                _notify(progress, "activity-cleanup-items", "verifying-remote", work_position, work_total)
                # Even a resumed preserved item must check current remote bytes.
                if not backend.verify(item):
                    raise ActivityCleanupError("activity_cleanup_remote_preservation_unverified")
                checkpoint()
            if item["disposition"] == "preserve":
                authorize()
                _notify(progress, "activity-cleanup-items", "offloading-verified-copy", work_position, work_total)
                backend.finish_local_preservation(item)
                checkpoint()
            authorize()
            _notify(progress, "activity-cleanup-items", "deleting-bound-original", work_position, work_total)
            journal.write(name + "-delete-intent", {"number": number, "state": item["state"],
                "preservation": "remote_verified" if item["disposition"] == "preserve" else "explicit_discard"})
            _delete_exact_approved_file(item["root"], path, item["state"], allow_readonly=True,
                                        expected_streams=item.get("alternate_streams"))
            journal.write(name + "-deleted", {"number": number, "state": "absent_after_bound_delete_intent"})
            results.append({"number": number, "state": "deleted"})
        except OperationCancelled as error:
            # A child may acknowledge this parent's request after its own safe
            # receipt. Do not convert cancellation to retained-and-continue.
            cancelled = True
            child_interruption = getattr(error, "child_recovery", None)
            results.append({"number": number, "state": "interrupted", "code": error.code,
                "original_file_present": os.path.lexists(path),
                "child_effects_require_reconciliation": True})
            break
        except Exception as error:
            from .storage_cancellation import is_cancelled
            if is_cancelled(error):
                cancelled = True
                results.append({"number": number, "state": "interrupted", "code": "operation_cancelled_at_checkpoint",
                    "original_file_present": os.path.lexists(path), "child_effects_require_reconciliation": True})
                break
            code = getattr(error, "code", "activity_cleanup_item_failed")
            # Never echo provider messages, exception paths, or request prose.
            if not isinstance(code, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,127}", code):
                code = "activity_cleanup_item_failed"
            failed = {"number": number, "state": "retained" if os.path.lexists(path) else "outcome_unknown",
                      "code": code, "child_effects_require_reconciliation": item["disposition"] == "preserve"}
            # v0.4.58 (letter 180): exact_human_approval_state_unknown hid which
            # child step failed and why; keep the fixed stage and cause codes.
            for key, value in (("child_stage", getattr(backend, "current_child_stage", None)),
                               ("cause_code", getattr(error, "cause_code", None)),
                               ("cause_stage", getattr(error, "cause_stage", None))):
                if isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", value):
                    failed[key] = value
            results.append(failed)
        finally:
            if results and results[-1]["number"] == number:
                results[-1]["processing_seconds"] = round(time.monotonic() - item_started, 6)
    if not cancelled and stop_requested():
        cancelled = True
    if cancelled:
        recorded = {row["number"] for row in results}
        results.extend({"number": item["number"], "state": "not_attempted"}
                       for item in material["items"] if item["number"] not in recorded)
    _notify(progress, "activity-cleanup-items", "done", work_position, work_total)
    _notify(progress, "activity-cleanup-directories", "start", 0, len(material["directories"]))
    directory_results = []
    for index, directory in sorted(enumerate(material["directories"]), key=lambda pair: len(Path(pair[1]["path"]).parts), reverse=True):
        if cancelled or stop_requested():
            cancelled = True
            break
        path = Path(directory["path"])
        try:
            authorize()
            if not path.exists():
                directory_results.append({"number": index, "state": "absent"})
                continue
            if _directory_state(path) != directory["state"] or any(path.iterdir()):
                directory_results.append({"number": index, "state": "retained_nonempty_or_changed"})
                continue
            _delete_exact_approved_empty_directory(path.parent, path, directory["state"])
            journal.write("directory-" + str(index) + "-deleted", {"number": index, "state": "removed_empty"})
            directory_results.append({"number": index, "state": "removed_empty"})
        except OperationCancelled:
            cancelled = True
            break
        except Exception:
            directory_results.append({"number": index, "state": "retained" if os.path.lexists(path) else "outcome_unknown"})
    if not cancelled and stop_requested():
        cancelled = True
    if cancelled:
        recorded = {row["number"] for row in directory_results}
        directory_results.extend({"number": number, "state": "not_attempted"}
                                 for number in range(len(material["directories"])) if number not in recorded)
    success = all(row["state"] in {"deleted", "already_deleted", "already_absent_after_intent"} for row in results)
    success = success and all(row["state"] in {"absent", "removed_empty"} for row in directory_results)
    result = {**candidate["public"], "ok": success, "dry_run": False,
        "state": "completed" if success else "partial", "writes_performed": True,
        "items": results, "directories": directory_results, "whole_folder_preservation_claimed": False,
        "remaining": remaining_inventory(material)}
    if cancelled:
        success = False
        result.update(ok=False, state="cancelled_at_checkpoint", cause_code="operation_cancelled_at_checkpoint",
            cause_stage="activity_cleanup", reason_codes=["operation_cancelled_at_checkpoint"],
            cancel_requested=True, cancel_acknowledged=True, provider_request_in_flight=False,
            process_killed=False, same_claim_resume_supported=True,
            child_operation_terminal_verified=False, child_recovery=child_interruption,
            next_safe_actions=["preserve_original_activity_intent_and_child_controls", "resume_original_activity_cleanup"])
    deleted_now = {row["number"] for row in results if row["state"] == "deleted"}
    unique_preserved = {item["object_id"]: item["state"]["size"] for item in material["items"]
                        if item["disposition"] == "preserve"}
    result["measurements"] = {
        "activity_writer_wait_seconds": round(candidate.get("activity_writer_wait_seconds", 0), 6),
        "approval_resolution_seconds": candidate.get("approval_resolution_seconds"),
        "processing_seconds_including_child_waits": round(time.monotonic() - execution_started, 6),
        "newly_deleted_file_payload_bytes": sum(item["state"]["size"] + sum(s["size"] for s in item.get("alternate_streams", []))
            for item in material["items"] if item["number"] in deleted_now),
        "unique_body_bytes_selected_for_preservation": sum(unique_preserved.values()),
        "unique_body_bytes_excludes_ads_bundle_overhead": True,
        "actual_physical_disk_reclaimed_bytes": None,
        "physical_disk_measurement_state": "not_attributable_from_file_payload_sizes",
        "completed_item_count": sum(row["state"] in {"deleted", "already_deleted", "already_absent_after_intent"} for row in results),
        "retained_item_count": sum(row["state"] in {"retained", "replacement_retained"} for row in results),
        "unprocessed_item_count": sum(row["state"] == "not_attempted" for row in results),
        "interrupted_item_count": sum(row["state"] == "interrupted" for row in results),
        "unknown_local_outcome_count": sum(row["state"] == "outcome_unknown" for row in results),
    }
    if isinstance(backend, OfficialPreservationBackend):
        observe = getattr(backend.transport, "transfer_observation", None)
        result["measurements"]["remote_transfer"] = observe() if callable(observe) else {"state": "transport_measurement_unavailable"}
        result["measurements"]["manifest_lookup"] = backend.manifest_lookup.observations()
    journal.write("attempt-" + uuid.uuid4().hex, result)
    if success and journal.read("completed") is None:
        journal.write("completed", result)
    return result


class OfficialPreservationBackend:
    """Compose supported intake, upload and offload, preserving every source link.

    Child writers retain their real approval/permission checks. A valid retained
    full-access grant opens no dialogs, including during resumed work.
    """
    def __init__(self, candidate, *, reviewer, transport_factory):
        from .remote_preservation_proof import PreservationVerifier, ProofStore, ExecutionTransport
        self.root, self.material = candidate["root"], candidate["material"]
        self.journal = candidate["journal"]
        self.progress = candidate.get("progress")
        self.reviewer, self.transport_factory = reviewer, transport_factory
        storage = self.material["storage"]
        self.provider_kind = storage.get("provider_kind", "cloudflare-r2")
        self.store_ref = storage.get("store_ref")
        self.transport = ExecutionTransport(transport_factory())
        self.verifier = PreservationVerifier(self.transport, store_ref=self.store_ref,
            execution_sha256=digest(self.material), proof_store=ProofStore(self.root))
        from .manifest_lookup import ManifestLookup
        self.manifest_lookup = ManifestLookup(self.root)

    def _staged(self, item):
        suffix = Path(item["path"]).suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,12}", suffix):
            suffix = ".bin"
        return "staging/incoming/activity-" + self.material["activity_id"] + "/" + str(item["number"]) + suffix

    def _stage(self, item):
        from .object_storage_restore import _atomic_move_file_no_replace
        target = services.archive_internal_path(self.root, self._staged(item))
        if target.exists():
            state = file_state(target)
            if state["sha256"] != item["state"]["sha256"] or state["size"] != item["state"]["size"]:
                raise ActivityCleanupError("activity_cleanup_staging_conflict")
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        _safe_path(target.parent)
        # A private temporary file never becomes an intake source until its bytes
        # match the exact approved source. A failed copy cannot justify cleanup.
        temporary = target.with_suffix(target.suffix + ".copying")
        residue = file_state(temporary) if temporary.exists() else None
        sha, count = hashlib.sha256(), 0
        with Path(item["path"]).open("rb") as source, temporary.open("r+b" if residue else "xb") as destination:
            opened = os.fstat(source.fileno())
            expected = item["state"]
            if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (expected["identity"]["device"], expected["identity"]["inode"], expected["size"], expected["mtime_ns"]):
                raise ActivityCleanupError("activity_cleanup_file_changed")
            if residue:
                current = os.fstat(destination.fileno())
                if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (residue["identity"]["device"], residue["identity"]["inode"], residue["size"], residue["mtime_ns"]):
                    raise ActivityCleanupError("activity_cleanup_staging_conflict")
                # Resume only an exact prefix of the unchanged approved source.
                # Foreign/replaced residue is retained and never truncated.
                for chunk in iter(lambda: destination.read(1024 * 1024), b""):
                    if source.read(len(chunk)) != chunk:
                        raise ActivityCleanupError("activity_cleanup_staging_conflict")
                    sha.update(chunk)
                    count += len(chunk)
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                destination.write(chunk)
                sha.update(chunk)
                count += len(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        if sha.hexdigest() != expected["sha256"] or count != expected["size"] or file_state(item["path"]) != expected:
            raise ActivityCleanupError("activity_cleanup_file_changed")
        _atomic_move_file_no_replace(temporary, target)
        return target

    def _remote(self, item):
        from .object_storage_restore import _remote_location
        rows = self.manifest_lookup.rows(item["object_id"])
        keys = {location["remote_key"] for row in rows
            if (location := _remote_location(row, provider_kind=self.provider_kind, store_ref=self.store_ref, archive_root=self.root))}
        if len(keys) != 1:
            return None
        return next(iter(keys))

    def _storage_step(self, item, operation, fresh_plan):
        from . import storage_cost
        with storage_cost.composed_child_planning(), work_timing.measure(operation + "_child_other"):
            return self._storage_step_inner(item, operation, fresh_plan)

    def _storage_step_inner(self, item, operation, fresh_plan):
        """Resume the original child; an upload that cannot resume is uploaded again.

        v0.4.60 (letter 180 follow-up, item A): an upload child whose claim was
        left started before any remote effect can no longer resume once the
        object's manifest row changed (later versions, a second row for the
        same bytes); the reconcile then ended in exact_human_approval_state_unknown
        every time. Uploading is content-addressed and idempotent and the full
        remote bytes are verified afterwards, so when the original cannot resume,
        the remote copy is absent and the local object still holds the exact
        bytes, the started claim is closed as failed (never as succeeded) and
        the upload runs again under this approval. Anything else keeps the file.
        """
        entry_saved = self._child_label(item, operation)[1]
        try:
            return self._storage_step_core(item, operation, fresh_plan)
        except Exception as error:
            from .operation_cancellation import OperationCancelled
            from .storage_cancellation import is_cancelled
            if (operation != "upload" or not entry_saved or isinstance(error, OperationCancelled)
                    or is_cancelled(error)):
                raise
            reason = _safe_code(getattr(error, "cause_code", None)) or _safe_code(getattr(error, "code", None)) \
                or "activity_cleanup_upload_original_not_resumable"
            if self._verify_body(item):
                self._close_started_child_claims(entry_saved["context_sha256"],
                                                 "activity_cleanup_upload_superseded_by_remote_proof")
                return {"ok": True, "prior_completed_child": True, "remote_proof": True,
                        "original_not_resumable_reason": reason}
            if not self._local_object_exact(item):
                raise
            self._close_started_child_claims(entry_saved["context_sha256"],
                                             "activity_cleanup_upload_superseded_original_not_resumable")
            result = self._storage_step_core(item, operation, fresh_plan, force_fresh=True)
            return {**result, "superseded_original_child": True, "original_not_resumable_reason": reason}

    def _storage_step_core(self, item, operation, fresh_plan, force_fresh=False):
        """Resume the original authenticated child execution, not a new claim."""
        from . import exact_approval_claims as claims, object_storage_upload_exact as upload, object_storage_offload as offload, object_storage_restore as restore
        from .exact_human_approval import exact_human_approval_context_sha256, _authenticated_claim_reference_core
        from .exact_operation_manifest import ExactOperationApprovalAuthority, exact_operation_execution_sha256
        from .exact_human_approval_workflow import _production_key_provider
        module = {"upload": upload, "offload": offload, "restore": restore}[operation]
        self.current_child_stage = operation
        label, saved, successor = self._child_label(item, operation)
        if force_fresh:
            label, saved = successor, None
        load = getattr(module, "load_object_storage_" + operation + "_plan")
        if saved and operation == "upload" and self._verify_body(item):
            # v0.4.58 (letter 180, item A): the full remote bytes already match
            # the object, so the upload effect is complete whatever its child
            # claim recorded. Close a claim left started (never as succeeded)
            # instead of resuming a plan whose preimage can no longer match.
            self._close_started_child_claims(saved["context_sha256"], "activity_cleanup_upload_superseded_by_remote_proof")
            return {"ok": True, "prior_completed_child": True, "remote_proof": True}
        if saved:
            try:
                plan = load(self.root, manifest_sha256=saved["manifest_sha256"])
            except Exception:
                control_path = services.archive_internal_path(self.root, module._control_relative(saved["manifest_sha256"]))
                if os.path.lexists(control_path):
                    raise ActivityCleanupError("activity_cleanup_child_control_present_but_invalid") from None
                # A missing control is not evidence of no prior effects. The
                # exact original plan cannot be rebuilt (its manifest binds the
                # whole archive inventory, which other items changed), so
                # v0.4.58 (letter 180, item B) proves instead that the step had
                # no effect, closes its started claim and starts the step again
                # under this approval; any sign of an effect keeps the file.
                plan = fresh_plan()
                rebuilt = (plan.manifest is not None and plan.manifest.manifest_sha256 == saved["manifest_sha256"]
                           and exact_human_approval_context_sha256(getattr(module, "object_storage_" + operation + "_context")(
                               plan, reviewer_claim=self.reviewer)) == saved["context_sha256"])
                if rebuilt:
                    from .exact_operation_manifest import exact_operation_writer_lock
                    with exact_operation_writer_lock(self.root, timeout_seconds=30):
                        module._persist_control(plan)
                    plan = load(self.root, manifest_sha256=plan.manifest.manifest_sha256)
                else:
                    claimed = self._child_claims(saved["context_sha256"])
                    if any(row["status"] == "succeeded" for row in claimed):
                        # The step recorded success; accept it only with a full
                        # remote byte proof of the object it preserved.
                        if self._verify_body(item):
                            return {"ok": True, "prior_completed_child": True, "remote_proof": True}
                        raise ActivityCleanupError("activity_cleanup_child_control_missing_original_not_reconstructable") from None
                    if operation != "offload" or not self._offload_had_no_effect(item):
                        raise ActivityCleanupError("activity_cleanup_child_control_missing_effects_unproven") from None
                    self._close_started_child_claims(saved["context_sha256"], "activity_cleanup_offload_superseded_no_effects")
                    label, saved = successor, None
        else:
            plan = fresh_plan()
        if not plan.approveable:
            if getattr(plan, "blockers", ()):
                raise ActivityCleanupError("activity_cleanup_" + operation + "_plan_blocked")
            return {"ok": True, "no_new_effects": True}
        context = getattr(module, "object_storage_" + operation + "_context")(plan, reviewer_claim=self.reviewer)
        context_sha = exact_human_approval_context_sha256(context)
        self.journal.write(label, {"manifest_sha256": plan.manifest.manifest_sha256, "context_sha256": context_sha})
        listing = claims.list_exact_human_approval_claims(self.root, status="all", max_claims=claims.MAX_LISTED_CLAIMS)
        if listing["blocker_codes"]:
            raise ActivityCleanupError("activity_cleanup_child_claim_evidence_incomplete")
        prior = [row for row in listing["claims"] if row["context_sha256"] == context_sha and row["status"] in {"started", "succeeded"}]
        if len(prior) > 1:
            raise ActivityCleanupError("activity_cleanup_child_claim_ambiguous")
        if prior:
            plan = load(self.root, manifest_sha256=plan.manifest.manifest_sha256)
            row = prior[0]
            if row["status"] == "succeeded":
                if operation == "upload":
                    valid = self._verify_body(item)
                else:
                    valid = getattr(module, "verify_object_storage_" + operation)(plan).get("ok") is True
                if not valid:
                    raise ActivityCleanupError("activity_cleanup_child_completion_changed")
                return {"ok": True, "prior_completed_child": True}
            reference = _production_key_provider().use_key(self.root,
                lambda key: _authenticated_claim_reference_core(self.root, row["approval_id"], key)[0], create_if_missing=False)
            execution = exact_operation_execution_sha256(plan.manifest,
                approval_authority=ExactOperationApprovalAuthority.from_reference(reference))
            from .exact_operation_manifest import validate_exact_operation_resume_checkpoint_read_only, verify_exact_operation
            checkpoint = validate_exact_operation_resume_checkpoint_read_only(self.root, plan.manifest,
                execution_sha256=execution, approval_authority=ExactOperationApprovalAuthority.from_reference(reference))
            if checkpoint:
                result = getattr(module, "resume_object_storage_" + operation)(plan, reviewer_claim=self.reviewer,
                    approval_id=row["approval_id"], execution_sha256=execution, transport_factory=lambda: self.transport)
            else:
                from .exact_human_approval_workflow import _resume_exact_human_approved_write_core
                def original_preimage(claim):
                    claim.assert_ready_for_context(context)
                    if operation == "upload":
                        from . import object_storage_preservation as preservation
                        verifier = module._Verifier(plan,
                            preservation.ObjectStorageRemoteQueryAdapter(self.transport),
                            preservation._ManifestBoundPreservationLedger(plan))
                    else:
                        verifier = module._Verifier(plan)
                    return (self.journal.read(label) == {"manifest_sha256": plan.manifest.manifest_sha256, "context_sha256": context_sha}
                        and verify_exact_operation(plan.manifest, verifier=verifier, state="pre")["all_match"] is True)
                def continue_original(claim):
                    if not original_preimage(claim):
                        raise ActivityCleanupError("activity_cleanup_child_effects_require_reconcile")
                    options = {"reviewed_by": self.reviewer} if operation == "upload" else {}
                    return module._apply_core(plan, claim, context=context, transport_factory=lambda: self.transport,
                                              resume=False, **options)
                result = _resume_exact_human_approved_write_core(self.root, context, row["approval_id"],
                    original_preimage, continue_original)
        else:
            result = getattr(module, "execute_object_storage_" + operation)(plan, reviewer_claim=self.reviewer,
                transport_factory=lambda: self.transport)
        if result.get("cause_code") == "operation_cancelled_at_checkpoint":
            from .operation_cancellation import OperationCancelled
            error = OperationCancelled()
            error.child_recovery = result.get("recovery")
            raise error
        if not result.get("ok"):
            raise ActivityCleanupError("activity_cleanup_" + operation + "_incomplete")
        return result

    @work_timing.timed("intake_capture")
    def _intake_step(self, item, relative, journal):
        from . import source_intake_chain_exact as chain, exact_approval_claims as claims
        from .exact_human_approval import exact_human_approval_context_sha256
        from .exact_human_approval_workflow import _resume_exact_human_approved_write_core
        self.current_child_stage = "chain"
        label = "item-" + str(item["number"]) + "-chain-control"
        saved = journal.read(label)
        plan = chain.plan_source_intake_chain(self.root, self.root / relative,
            staged_path=self._staged(item), item_id="activity-" + str(item["number"]),
            _recovery_capture_preview=saved["capture_preview"] if saved else None)
        if not plan.approveable:
            raise ActivityCleanupError("activity_cleanup_intake_blocked")
        context = chain.approval_context(plan, reviewer_claim=self.reviewer)
        context_sha = exact_human_approval_context_sha256(context)
        control = {"capture_preview": plan.capture_preview, "context_sha256": context_sha,
            "plan_sha256": context.plan_sha256, "target_binding_sha256": context.target_binding_sha256}
        journal.write(label, control)
        listing = claims.list_exact_human_approval_claims(self.root, status="all", max_claims=claims.MAX_LISTED_CLAIMS)
        if listing["blocker_codes"]:
            raise ActivityCleanupError("activity_cleanup_child_claim_evidence_incomplete")
        prior = [row for row in listing["claims"] if row["context_sha256"] == context_sha and row["status"] in {"started", "succeeded"}]
        if len(prior) > 1:
            raise ActivityCleanupError("activity_cleanup_child_claim_ambiguous")
        if not prior:
            return chain.execute_source_intake_chain(plan, reviewer_claim=self.reviewer)
        if prior[0]["status"] == "succeeded":
            raw = services.archive_internal_path(self.root, plan.receipt_relative_path).read_bytes()
            receipt = json.loads(raw)
            local = self.root / "objects/sha256" / item["object_id"][7:9] / item["object_id"][7:]
            state = file_state(local)
            if (receipt.get("state") != "completed" or receipt.get("chain_id") != plan.chain_id
                or state["sha256"] != item["state"]["sha256"] or state["size"] != item["state"]["size"]):
                raise ActivityCleanupError("activity_cleanup_child_completion_changed")
            return {"ok": True, "chain_id": plan.chain_id, "receipt_path": plan.receipt_relative_path,
                "prior_completed_child": True}
        return _resume_exact_human_approved_write_core(self.root, context, prior[0]["approval_id"],
            lambda claim: journal.read(label) == control,
            lambda claim: chain._execute_core(plan, claim, reviewer_claim=self.reviewer, _resume=True))

    def _preserve_body(self, item, journal):
        from . import source_intake_chain_exact as chain, object_storage_upload_exact as upload
        from .object_storage_scope import ObjectScope
        from .object_storage_offload import _create_or_match_document
        name = "item-" + str(item["number"])
        if journal.read(name + "-intake") is None:
            _notify(self.progress, "activity-cleanup-items", "staging-source",
                    *(getattr(self, "progress_position", None) or (_position(item), len(self.material["items"]))))
            staged = self._stage(item)
            relative = ROOT + "/" + self.material["activity_id"] + "/" + name + "-source-plan.json"
            saved_plan = journal.read(name + "-intake-plan")
            intake = saved_plan if saved_plan is not None else services.source_intake_plan(self.root, local_path=staged,
                title="Activity source " + str(item["number"]), redact_local_paths=True)
            if not intake.get("ok"):
                raise ActivityCleanupError("activity_cleanup_intake_plan_blocked")
            journal.write(name + "-intake-plan", intake)
            _create_or_match_document(self.root, relative, encoded(intake),
                failure_code="object_storage_offload_receipt_conflict", max_bytes=MAX_CONTROL_BYTES)
            result = self._intake_step(item, relative, journal)
            if result.get("cause_code") == "operation_cancelled_at_checkpoint":
                from .operation_cancellation import OperationCancelled
                error = OperationCancelled()
                error.child_recovery = result.get("recovery")
                raise error
            if not result.get("ok"):
                raise ActivityCleanupError("activity_cleanup_intake_incomplete")
            journal.write(name + "-intake", {"object_id": item["object_id"], "source_state": item["state"],
                "chain_id": result["chain_id"], "receipt_path": result["receipt_path"]})
        # Reuse existing object bytes across identical sources; each item still
        # retains its own intake and original source association in the journal.
        if self._remote(item) is None or journal.read(name + "-upload-control"):
            _notify(self.progress, "activity-cleanup-items", "uploading-or-resuming",
                    *(getattr(self, "progress_position", None) or (_position(item), len(self.material["items"]))))
            self._storage_step(item, "upload", lambda: upload.plan_object_storage_upload(self.root,
                provider_kind=self.provider_kind, store_ref=self.store_ref,
                scope=ObjectScope("object_list", (item["object_id"],))))
        if not self._verify_body(item):
            raise ActivityCleanupError("activity_cleanup_remote_preservation_unverified")
        journal.write(name + "-preserved", {"object_id": item["object_id"], "size": item["state"]["size"],
            "state": "remote_verified", "source_link_preserved": True})

    def _child_label(self, item, operation):
        """v0.4.58: the newest control label of a child step and the next one (labels are create-once)."""
        base = "item-" + str(item["number"]) + "-" + operation + "-control"
        label, saved, index = base, self.journal.read(base), 0
        while saved is not None:
            following = base + "-r" + str(index + 1)
            document = self.journal.read(following)
            if document is None:
                return label, saved, following
            label, saved, index = following, document, index + 1
        return label, saved, base + "-r" + str(index + 1)

    def _child_claims(self, context_sha256):
        from . import exact_approval_claims as claims
        listing = claims.list_exact_human_approval_claims(self.root, status="all", max_claims=claims.MAX_LISTED_CLAIMS)
        if listing["blocker_codes"]:
            raise ActivityCleanupError("activity_cleanup_child_claim_evidence_incomplete")
        return [row for row in listing["claims"] if row["context_sha256"] == context_sha256
                and row["status"] in {"started", "succeeded"}]

    def _close_started_child_claims(self, context_sha256, failure_code):
        """Close this step's started child claims as failed with a fixed code; never as succeeded."""
        from . import exact_approval_claims as claims
        for row in self._child_claims(context_sha256):
            if row["status"] != "started":
                continue

            def close(key, boundary, approval_id=row["approval_id"]):
                if boundary is None:
                    raise ActivityCleanupError("activity_cleanup_child_claim_evidence_incomplete")
                bound_root, parent_binding = boundary
                claim = claims._rehydrate_started_claim_without_context(
                    self.root, approval_id, key, expected_context_sha256=context_sha256, clock=claims._utc_now,
                    bound_archive_root=bound_root, claim_parent_binding=parent_binding)
                try:
                    claim.finalize_failed(failure_code)
                finally:
                    claim.close()

            claims._with_key_and_boundary(self.root, close, key_provider=None, claims_boundary=None)

    def _local_object_exact(self, item):
        """The archive's local object file exists and hashes to its object id."""
        object_id = str(item.get("object_id") or "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", object_id):
            return False
        local = self.root / "objects/sha256" / object_id[7:9] / object_id[7:]
        try:
            info = os.lstat(local)
            if not stat.S_ISREG(info.st_mode):
                return False
            observed = hashlib.sha256()
            with local.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    observed.update(chunk)
        except OSError:
            return False
        return "sha256:" + observed.hexdigest() == object_id

    def _offload_had_no_effect(self, item):
        """The local object still holds the exact bytes and its manifest location is not offloaded."""
        from . import object_storage_restore as restore
        object_id = str(item.get("object_id") or "")
        # Called on a read-only probe by the diagnosis, so not via self.
        if not OfficialPreservationBackend._local_object_exact(self, item):
            return False
        logical_key = restore._logical_key(object_id)
        for row in services.load_manifest_records(self.root):
            if isinstance(row, dict) and str(row.get("object_id") or "") == object_id:
                if restore._local_location_state(row, logical_key) == "offloaded":
                    return False
        return True

    def _verify_body(self, item):
        key = self._remote(item)
        return key is not None and self.verifier.verify(key=key, object_id=item["object_id"],
            size=item["state"]["size"]).get("state") == "verified_match"

    def _finish_body(self, item):
        from . import object_storage_offload as offload
        from .object_storage_scope import ObjectScope
        from .legacy_cleanup_bound_delete import _delete_exact_approved_file
        self._storage_step(item, "offload", lambda: offload.plan_object_storage_offload(self.root,
            provider_kind=self.provider_kind, store_ref=self.store_ref,
            scope=ObjectScope("object_list", (item["object_id"],)), min_age_days=0))
        staged = services.archive_internal_path(self.root, self._staged(item))
        if staged.exists():
            state = file_state(staged)
            if state["sha256"] != item["state"]["sha256"] or state["size"] != item["state"]["size"]:
                raise ActivityCleanupError("activity_cleanup_staging_conflict")
            if not self._verify_body(item):
                raise ActivityCleanupError("activity_cleanup_remote_preservation_unverified")
            _delete_exact_approved_file(self.root, staged, state)

    def _stream_item(self, item, *, create=False):
        from .activity_cleanup_streams import build_bundle
        rows = item.get("alternate_streams", [])
        if not rows:
            return None
        label = "item-" + str(item["number"]) + "-streams"
        saved = self.journal.read(label)
        if saved is not None:
            if saved.get("parent_object_id") != item["object_id"] or saved.get("streams") != rows:
                raise ActivityCleanupError("activity_cleanup_stream_evidence_changed")
            return saved["item"]
        if not create:
            raise ActivityCleanupError("activity_cleanup_stream_preservation_missing")
        path = services.archive_internal_path(self.root, ROOT + "/" + self.material["activity_id"] + "/" + label + ".zip")
        path.parent.mkdir(parents=True, exist_ok=True)
        _safe_path(path.parent)
        build_bundle(Path(item["path"]), item["state"], rows, path)
        state = file_state(path)
        child = {"number": str(item["number"]) + "-streams", "path": str(path), "root": str(path.parent),
                 "role": "evidence", "disposition": "preserve", "state": state, "object_id": "sha256:" + state["sha256"]}
        self.journal.write(label, {"parent_object_id": item["object_id"], "streams": rows, "item": child})
        return child

    def preserve(self, item, journal):
        self._preserve_body(item, journal)
        child = self._stream_item(item, create=True)
        if child is not None:
            self._preserve_body(child, journal)
        if not self.verify(item):
            raise ActivityCleanupError("activity_cleanup_remote_preservation_unverified")

    @work_timing.timed("remote_verification")
    def verify(self, item):
        if not self._verify_body(item):
            return False
        child = self._stream_item(item)
        return child is None or self._verify_body(child)

    def finish_local_preservation(self, item):
        self._finish_body(item)
        child = self._stream_item(item)
        if child is not None:
            self._finish_body(child)
            path = Path(child["path"])
            if os.path.lexists(path):
                if not self._verify_body(child) or file_state(path) != child["state"]:
                    raise ActivityCleanupError("activity_cleanup_stream_preservation_changed")
                from .legacy_cleanup_bound_delete import _delete_exact_approved_file
                _delete_exact_approved_file(self.root, path, child["state"])

    def restore_object(self, item):
        from . import object_storage_restore as restore
        from .object_storage_scope import ObjectScope
        path = self.root / "objects/sha256" / item["object_id"][7:9] / item["object_id"][7:]
        if not os.path.lexists(path) or self.journal.read("item-" + str(item["number"]) + "-restore-control"):
            self._storage_step(item, "restore", lambda: restore.plan_object_storage_restore(self.root,
                provider_kind=self.provider_kind, store_ref=self.store_ref,
                scope=ObjectScope("object_list", (item["object_id"],))))
        state = file_state(path)
        if state["sha256"] != item["state"]["sha256"] or state["size"] != item["state"]["size"]:
            raise ActivityCleanupError("activity_cleanup_restore_body_changed")
        return path
