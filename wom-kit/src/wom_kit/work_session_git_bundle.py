"""Durable private Git payload plus its exact retained approval context.

This is storage, not approval, actor routing, automatic resume or completion
proof. Callers must retain the context before publishing its original claim;
only the existing broker can subsequently authenticate that claim. A wrapper
hash cannot establish that an approval occurred or that a caller owns a route.

The existing Git codec currently binds an optional work-session revision, but
not a task route or session claim identity. This module accepts neither of those
as unsigned sidecar assertions. A future route-aware workflow requires an exact
manifest scope extension first. Existing Git bundles are never upgraded and
their missing context is never inferred from a new reviewer or current session.
"""

from __future__ import annotations

from dataclasses import dataclass
import hmac
import os
from pathlib import Path
import stat
import uuid

from . import exact_human_approval as approval
from . import exact_operation_manifest as exact
from . import git_backup_writer as writer
from . import project_update_transaction as durable
from . import work_session_bundle as session_bundle
from . import work_session_registry as registry
from .exact_human_approval_windows import ExactHumanApprovalContext, ExactHumanApprovalOperation


CONTEXT_BUNDLE_SCHEMA = "wom-kit/work-session-git-private-context/v1"
PRIVATE_ROOT = ("profiles", "local", "exact-operations", "git-backup-contexts")
# Keep the existing Git payload bound; allow only a small context envelope.
MAX_BUNDLE_BYTES = writer.GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES + 64 * 1024
_ERRORS = frozenset({
    "work_session_git_bundle_invalid", "work_session_git_bundle_missing",
    "work_session_git_bundle_changed", "work_session_git_bundle_context_invalid",
    "work_session_git_bundle_path_unsafe", "work_session_git_bundle_lock_required",
    "work_session_git_bundle_durability_unknown",
})


class WorkSessionGitBundleError(RuntimeError):
    def __init__(self, code="work_session_git_bundle_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_git_bundle_invalid"
        super().__init__(self.code)


def _safe_call(call):
    # Raise outside the handler; even a suppressed exception chain can retain
    # private paths, reviewer text, remote URLs, or a rejected nested document.
    code = "work_session_git_bundle_invalid"
    try:
        return call()
    except WorkSessionGitBundleError as error:
        code = error.code
    except Exception:
        pass
    raise WorkSessionGitBundleError(code)


def _held_root(archive_root, held):
    if type(held) is not exact.ExactOperationWriterLock:
        raise WorkSessionGitBundleError("work_session_git_bundle_lock_required")
    root, archive_id = approval._archive_identity(archive_root)
    failure = False
    try:
        held.verify_held()
        failure = not os.path.samefile(held.archive_root, root)
    except Exception:
        failure = True
    if failure:
        raise WorkSessionGitBundleError("work_session_git_bundle_lock_required")
    return root, archive_id


def _canonical(document):
    raw = writer._canonical(document)
    if not raw or len(raw) > MAX_BUNDLE_BYTES:
        raise WorkSessionGitBundleError()
    return raw


def _factory_context(prepared, context):
    if type(context) is not ExactHumanApprovalContext:
        raise WorkSessionGitBundleError("work_session_git_bundle_context_invalid")
    expected = writer._git_backup_approval_context(prepared, reviewer_claim=context.reviewer_claim)
    if not hmac.compare_digest(approval.exact_human_approval_context_sha256(expected),
                               approval.exact_human_approval_context_sha256(context)):
        raise WorkSessionGitBundleError("work_session_git_bundle_context_invalid")
    # Native-only preview is not authority and is deliberately not persisted.
    return expected


def _context_from_document(document):
    if (type(document) is not dict or set(document) != session_bundle._CONTEXT_KEYS
            or type(document["review_binding_codes"]) is not list
            or type(document["warning_codes"]) is not list):
        raise WorkSessionGitBundleError("work_session_git_bundle_context_invalid")
    return ExactHumanApprovalContext(
        operation=ExactHumanApprovalOperation(document["operation"]),
        archive_identity_sha256=document["archive_identity_sha256"],
        plan_sha256=document["plan_sha256"], target_binding_sha256=document["target_binding_sha256"],
        reviewer_claim=document["reviewer_claim"],
        review_binding_codes=tuple(document["review_binding_codes"]),
        warning_codes=tuple(document["warning_codes"]),
    )


def _decode(root, raw, manifest_sha256):
    if (type(raw) is not bytes or not raw or len(raw) > MAX_BUNDLE_BYTES
            or not registry._is_digest(manifest_sha256)):
        raise WorkSessionGitBundleError()
    document = writer._strict_json(raw)
    if (set(document) != {"schema", "prepared", "context", "context_sha256", "bundle_sha256"}
            or document["schema"] != CONTEXT_BUNDLE_SCHEMA or _canonical(document) != raw
            or not registry._is_digest(document["bundle_sha256"])
            or not registry._is_digest(document["context_sha256"])):
        raise WorkSessionGitBundleError()
    basis = {key: value for key, value in document.items() if key != "bundle_sha256"}
    if not hmac.compare_digest(document["bundle_sha256"], writer._sha256_bytes(_canonical(basis))):
        raise WorkSessionGitBundleError("work_session_git_bundle_changed")
    prepared_document = document["prepared"]
    if (type(prepared_document) is not dict
            or len(writer._canonical(prepared_document)) + 1 > writer.GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES):
        raise WorkSessionGitBundleError()
    # Reconstruct sources, commit messages, selection, exclusions and manifest
    # through the existing codec; do not trust the embedded convenience views.
    prepared = writer._decode_private_git_backup_bundle(
        root, prepared_document, manifest_sha256=manifest_sha256,
    )
    context = _context_from_document(document["context"])
    if not hmac.compare_digest(document["context_sha256"],
                               approval.exact_human_approval_context_sha256(context)):
        raise WorkSessionGitBundleError("work_session_git_bundle_context_invalid")
    return prepared, _factory_context(prepared, context)


@dataclass(frozen=True, repr=False)
class ContextBoundGitBackup:
    """Immutable private bytes; every prepared/context view is detached data."""

    _root: Path
    _raw: bytes
    _manifest_sha256: str

    def __post_init__(self):
        _safe_call(lambda: _decode(self._root, self._raw, self._manifest_sha256))

    @property
    def prepared(self):
        return _safe_call(lambda: _decode(self._root, self._raw, self._manifest_sha256)[0])

    @property
    def context(self):
        return _safe_call(lambda: _decode(self._root, self._raw, self._manifest_sha256)[1])

    def __repr__(self):
        return "<ContextBoundGitBackup private context; no approval, route or completion authority>"


def _directory(root):
    current = root
    for part in PRIVATE_ROOT:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            return None
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or exact._path_is_reparse(info):
            raise WorkSessionGitBundleError("work_session_git_bundle_path_unsafe")
    return current


def _read_raw(root, manifest_sha256):
    if not registry._is_digest(manifest_sha256):
        raise WorkSessionGitBundleError()
    directory = _directory(root)
    if directory is None:
        raise WorkSessionGitBundleError("work_session_git_bundle_missing")
    try:
        # The reader retains the complete parent chain and rejects links,
        # oversized/unstable files, and ancestor replacement on both platforms.
        return session_bundle._read_control(
            directory / (manifest_sha256[7:] + ".json"), maximum=MAX_BUNDLE_BYTES,
        )
    except FileNotFoundError:
        raise WorkSessionGitBundleError("work_session_git_bundle_missing") from None


def _load_original_git_context_held(archive_root, *, held, manifest_sha256) -> ContextBoundGitBackup:
    """Read only; no fallback to legacy bundles, current reviewer, or actor."""
    def load():
        root, _archive_id = _held_root(archive_root, held)
        raw = _read_raw(root, manifest_sha256)
        result = ContextBoundGitBackup(root, raw, manifest_sha256)
        _held_root(root, held)
        if _read_raw(root, manifest_sha256) != raw:
            raise WorkSessionGitBundleError("work_session_git_bundle_changed")
        return result
    return _safe_call(load)


def _save_original_git_context_held(
    prepared: writer.PreparedGitBackup, *, context: ExactHumanApprovalContext, held,
) -> ContextBoundGitBackup:
    """Publish once before the caller's claim publication, never grant approval.

    Exact repeat is idempotent. A different context for the same manifest,
    corrupt existing file, or partial publication is never replaced or repaired.
    The caller still owns current actor/provenance checks and the original
    authenticated claim boundary; this storage helper performs no Git commands.
    """
    def save():
        if type(prepared) is not writer.PreparedGitBackup:
            raise WorkSessionGitBundleError()
        root, _archive_id = _held_root(prepared.root, held)
        frozen = writer._freeze_validated_prepared(prepared)
        original_context = _factory_context(frozen, context)
        basis = {"schema": CONTEXT_BUNDLE_SCHEMA, "prepared": writer._bundle_document(frozen),
                 "context": session_bundle._context_document(original_context),
                 "context_sha256": approval.exact_human_approval_context_sha256(original_context)}
        raw = _canonical({**basis, "bundle_sha256": writer._sha256_bytes(_canonical(basis))})
        manifest_sha = frozen.manifest.manifest_sha256
        result = ContextBoundGitBackup(root, raw, manifest_sha)
        directory = _directory(root)
        if directory is not None and os.path.lexists(directory / (manifest_sha[7:] + ".json")):
            existing = _load_original_git_context_held(root, held=held, manifest_sha256=manifest_sha)
            if existing._raw != raw:
                raise WorkSessionGitBundleError("work_session_git_bundle_changed")
            failure = False
            try:
                # A previous cut may have occurred after the atomic rename
                # but before directory flush. Confirm durability on repeat
                # without replacing or rewriting the already published bytes.
                with durable._bound_directory_for_move(directory) as parent:
                    durable._require_directory_durable(directory)
                    durable._assert_named_reservation_directory_identity(directory, parent.identity)
            except Exception:
                failure = True
            if failure:
                raise WorkSessionGitBundleError("work_session_git_bundle_durability_unknown")
            # Directory flushing is not a file-content proof. An external
            # actor may have replaced the retained bytes since the first load.
            confirmed = _load_original_git_context_held(root, held=held, manifest_sha256=manifest_sha)
            if confirmed._raw != raw:
                raise WorkSessionGitBundleError("work_session_git_bundle_changed")
            return confirmed
        failure = False
        try:
            directory = exact._ensure_private_directory(root, PRIVATE_ROOT)
            with durable._bound_directory_for_move(directory) as parent:
                durable._require_directory_durable(directory)
                pending = directory / (".pending_" + uuid.uuid4().hex)
                destination = directory / (manifest_sha[7:] + ".json")
                registry._write_private_pending(pending, raw, root=root)
                durable._require_directory_durable(directory)
                _held_root(root, held)
                _decode(root, raw, manifest_sha)
                if session_bundle._read_control(pending, maximum=MAX_BUNDLE_BYTES) != raw:
                    raise WorkSessionGitBundleError("work_session_git_bundle_changed")
                durable._assert_named_reservation_directory_identity(directory, parent.identity)
                durable._atomic_move_file_no_replace(
                    pending, destination, expected_parent_identity=parent.identity,
                )
                durable._require_directory_durable(directory)
                durable._assert_named_reservation_directory_identity(directory, parent.identity)
        except WorkSessionGitBundleError:
            raise
        except Exception:
            failure = True
        if failure:
            raise WorkSessionGitBundleError("work_session_git_bundle_durability_unknown")
        restored = _load_original_git_context_held(root, held=held, manifest_sha256=manifest_sha)
        if restored._raw != result._raw:
            raise WorkSessionGitBundleError("work_session_git_bundle_changed")
        return restored
    return _safe_call(save)
