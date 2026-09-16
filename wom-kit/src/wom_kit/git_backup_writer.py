"""Exact, resumable commit-and-push writer for reviewed Git backup plans.

The public planner keeps paths and commit subjects private.  This module reads
one operator-owned selection manifest, binds every ordinal ``change_ref`` to
exactly one commit group, adapts that selection to ``ExactOperationManifest
v1``, and executes it through the existing native exact-human approval
workflow.  It never pulls, fetches, merges, rebases, resets, cleans, deletes a
ref, force-pushes, or stages an unclassified path.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import subprocess
import tempfile
import threading
import time
from contextvars import copy_context
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from . import archive_services
from . import git_backup_plan as planning
from .exact_human_approval import (
    _ClaimedExactHumanApproval,
    exact_human_approval_archive_identity_sha256,
    exact_human_approval_context_sha256,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)
from .exact_human_approval_workflow import (
    _execute_exact_human_approved_write_core,
    _resume_exact_human_approved_write_core,
)
from .exact_operation_manifest import (
    EXACT_OPERATION_LOCAL_ROOT,
    ExactFieldEffect,
    ExactOperationApprovalAuthority,
    ExactOperationItem,
    ExactOperationManifest,
    ExactOperationManifestError,
    ExactOperationProgress,
    ExactOperationWriterLock,
    FileExactOperationCheckpointStore,
    apply_exact_operation,
    exact_operation_execution_sha256,
    exact_operation_writer_lock,
    hash_field_value,
)
from .operation_approval_binding import exact_operation_manifest_approval_binding
from .git_backup_session_scope import _GitBackupSessionScope
from .work_session_binding import WorkSessionBinding, WorkSessionBindingError


GIT_BACKUP_SELECTION_SCHEMA = "wom-kit/git-backup-selection/v1"
GIT_BACKUP_SELECTION_V2_SCHEMA = "wom-kit/git-backup-selection/v2"
# Explicit declarations supplied by the session-aware planner, not ownership
# inferred from a filename, timestamp, author or the current caller.
GIT_BACKUP_EXCLUSION_REASONS = {
    "other_session": "other_session_change",
    "mixed": "mixed_session_change",
    "legacy_unattributed": "legacy_unattributed_change",
    "unknown": "ownership_unverified",
}
GIT_BACKUP_EXACT_PLAN_SCHEMA = "wom-kit/git-backup-exact-plan/v1"
GIT_BACKUP_DOMAIN_RECEIPT_SCHEMA = "wom-kit/git-backup-completion/v1"

GIT_BACKUP_MAX_SELECTION_BYTES = 16 * 1024 * 1024
GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES = 256 * 1024 * 1024
GIT_BACKUP_MAX_GROUPS = 10_000
GIT_BACKUP_MAX_COMMIT_SUBJECT_BYTES = 240
GIT_BACKUP_MAX_COMMAND_PATH_BYTES = 24 * 1024
# Windows CreateProcess has a 32,767 UTF-16 code-unit command-line ceiling.
# Reserve more than 8 KiB for the pinned Git path, archive root, fixed safety
# options, and the temporary commit-message path.  Safe Git paths cannot carry
# quotes or backslashes, but we still measure Python's Windows quoting form and
# fail before approval if the literal path argv alone exceeds this cap.
GIT_BACKUP_WINDOWS_MAX_COMMAND_LINE_CHARS = 32_767
GIT_BACKUP_MAX_LITERAL_PATH_ARGV_CHARS = 24 * 1024
GIT_BACKUP_MAX_COMMIT_OUTPUT_BYTES = 4 * 1024 * 1024
GIT_BACKUP_PUSH_TIMEOUT_SECONDS = 300
GIT_BACKUP_COMMIT_TIMEOUT_SECONDS = 120
GIT_BACKUP_CONTENT_POLICY = "exact_worktree_bytes_core_autocrlf_false"

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CHANGE_REF_RE = re.compile(r"^change:[0-9]{6}$")
_GROUP_ID_RE = re.compile(r"^group:[a-z0-9][a-z0-9._-]{0,78}$")
_OID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_SENSITIVE_SUBJECT_RE = re.compile(
    r"(?i)(?:github_pat_|ghp_|sk-|ntn_|secret_)[A-Za-z0-9_./+=-]{12,}"
    r"|(?:password|token|secret|credential)\s*[:=]\s*\S{8,}"
    r"|(?:[A-Za-z]:\\Users\\|/home/)[^\s]+"
)

_PENDING = b"pending"
_COMMITTED = b"committed"
_REMOTE_VERIFIED = b"remote_verified"
_UNKNOWN = b"unknown_or_drifted"


class GitBackupWriterError(RuntimeError):
    """A fixed-code failure that never retains private Git values."""

    _CODES = {
        "git_backup_exact_plan_blocked",
        "git_backup_selection_invalid",
        "git_backup_selection_unstable",
        "git_backup_selection_incomplete",
        "git_backup_no_selected_changes",
        "git_backup_work_session_binding_invalid",
        "git_backup_session_scope_invalid",
        "git_backup_scope_context_required",
        "git_backup_selection_plan_mismatch",
        "git_backup_repository_relation_unsafe",
        "git_backup_manifest_drifted",
        "git_backup_git_executable_drifted",
        "git_backup_git_state_drifted",
        "git_backup_exact_add_failed",
        "git_backup_commit_failed",
        "git_backup_commit_verification_failed",
        "git_backup_push_failed",
        "git_backup_remote_verification_failed",
        "git_backup_completion_receipt_failed",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "git_backup_exact_plan_blocked"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"GitBackupWriterError({self.code!r})"


def _fail(code: str) -> GitBackupWriterError:
    return GitBackupWriterError(code)


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("git_backup_selection_invalid") from None


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical(value))


def _strict_json(raw: bytes) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate_json_member")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise _fail("git_backup_selection_invalid") from None
    if not isinstance(value, dict):
        raise _fail("git_backup_selection_invalid")
    return value


def _read_stable_plain_file(
    path: Path,
    *,
    max_bytes: int = GIT_BACKUP_MAX_SELECTION_BYTES,
) -> bytes:
    descriptor = -1
    try:
        supplied = Path(os.path.abspath(str(path)))
        before = os.lstat(supplied)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or (reparse and getattr(before, "st_file_attributes", 0) & reparse)
            or before.st_size < 2
            or before.st_size > max_bytes
        ):
            raise OSError("unsafe_selection_file")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(supplied, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_size != before.st_size
            or (opened.st_ino and before.st_ino and opened.st_ino != before.st_ino)
            or (opened.st_dev and before.st_dev and opened.st_dev != before.st_dev)
        ):
            raise OSError("selection_file_drifted")
        chunks: list[bytes] = []
        total = 0
        while total <= max_bytes:
            chunk = os.read(
                descriptor,
                min(64 * 1024, max_bytes + 1 - total),
            )
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
        named = os.lstat(supplied)
        if (
            total != opened.st_size
            or total > max_bytes
            or after.st_size != opened.st_size
            or after.st_mtime_ns != opened.st_mtime_ns
            or after.st_ctime_ns != opened.st_ctime_ns
            or named.st_size != after.st_size
            or named.st_mtime_ns != after.st_mtime_ns
            or (after.st_ino and named.st_ino and after.st_ino != named.st_ino)
            or (after.st_dev and named.st_dev and after.st_dev != named.st_dev)
        ):
            raise OSError("selection_file_drifted")
        return b"".join(chunks)
    except OSError:
        raise _fail("git_backup_selection_unstable") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


@dataclass(frozen=True)
class _SelectionGroup:
    ordinal: int
    group_id: str
    change_refs: tuple[str, ...]
    commit_subject: str


@dataclass(frozen=True)
class _PreparedGroup:
    ordinal: int
    group_id: str
    change_refs: tuple[str, ...]
    commit_subject: str
    paths: tuple[str, ...]
    source_payload: bytes
    source_sha256: str
    target_identity_sha256: str
    commit_message: bytes
    private_changes: tuple[Mapping[str, Any], ...]

    @property
    def target_ref(self) -> str:
        return f"commit_group:{self.ordinal + 1:06d}"


@dataclass(frozen=True)
class PreparedGitBackup:
    root: Path
    archive_id: str
    remote_name: str
    remote_url: str
    credential_mode: str
    target_ref: str
    initial_head_oid: str
    initial_remote_oid: str
    expected_plan_sha256: str
    selection_sha256: str
    git_executable_sha256: str
    git_config_trust_sha256: str
    groups: tuple[_PreparedGroup, ...]
    push_source_payload: bytes
    push_target_identity_sha256: str
    manifest: ExactOperationManifest
    max_changes: int
    max_changed_bytes: int
    selection_schema: str = GIT_BACKUP_SELECTION_SCHEMA
    excluded_changes: tuple[Mapping[str, Any], ...] = ()
    session_scope: _GitBackupSessionScope | None = None

    def public_plan(self) -> dict[str, Any]:
        result = {
            "schema": GIT_BACKUP_EXACT_PLAN_SCHEMA,
            "ok": True,
            "dry_run": True,
            "lifecycle_action": "git_backup_exact_plan",
            "status": "ready_for_exact_human_approval",
            "expected_plan_sha256": self.expected_plan_sha256,
            "selection_sha256": self.selection_sha256,
            "manifest_sha256": self.manifest.manifest_sha256,
            "target_set_sha256": self.manifest.target_set_sha256,
            "source_set_sha256": self.manifest.source_set_sha256,
            "effect_set_sha256": self.manifest.effect_set_sha256,
            "commit_group_count": len(self.groups),
            "classified_change_count": sum(
                len(group.change_refs) for group in self.groups
            ),
            "ready_for_write": True,
            "writer_available": True,
            "requires_native_exact_human_approval": True,
            "resume_supported": True,
            "revert_supported": False,
            "windows_command_line_max_chars": (
                GIT_BACKUP_WINDOWS_MAX_COMMAND_LINE_CHARS
            ),
            "literal_path_argv_max_chars_per_group": (
                GIT_BACKUP_MAX_LITERAL_PATH_ARGV_CHARS
            ),
            "would_change": [
                {
                    "action": "commit_group",
                    "ordinal": group.ordinal + 1,
                    "change_count": len(group.change_refs),
                }
                for group in self.groups
            ]
            + [{"action": "push_and_requery_exact_remote_ref"}],
            "paths_echoed": False,
            "commit_messages_echoed": False,
            "remote_url_echoed": False,
            "credential_values_echoed": False,
            "private_values_echoed": False,
            "warnings": [
                "git_backup_push_has_no_automatic_revert",
                "completion_receipt_is_written_after_push_and_is_local_until_a_later_backup",
            ],
            "blockers": [],
        }
        if self.selection_schema == GIT_BACKUP_SELECTION_V2_SCHEMA:
            selected_count = sum(len(group.change_refs) for group in self.groups)
            result.update(
                selection_schema=self.selection_schema,
                selected_change_count=selected_count,
                excluded_change_count=len(self.excluded_changes),
                classified_change_count=selected_count + len(self.excluded_changes),
                exclusion_scope_counts={
                    scope: sum(row["scope"] == scope for row in self.excluded_changes)
                    for scope in GIT_BACKUP_EXCLUSION_REASONS
                },
                exclusion_scope_source="explicit_declaration_not_ownership_attestation",
                excluded_index_and_worktree_preservation_required=True,
            )
        if self.manifest.work_session_binding is not None:
            result["work_session_binding"] = self.manifest.work_session_binding.document()
        if self.session_scope is not None:
            result.update(
                operation_evidence=self.session_scope.operation_evidence().document(),
                ready_for_write=False, writer_available=False, status="scope_context_required",
                blockers=["git_backup_scope_context_required"],
            )
        return result


def _selection_groups(
    document: Mapping[str, Any],
    *,
    expected_plan_sha256: str,
    observed_change_refs: Sequence[str],
) -> tuple[tuple[_SelectionGroup, ...], str]:
    if set(document) != {"schema", "expected_plan_sha256", "groups"}:
        raise _fail("git_backup_selection_invalid")
    if (
        document.get("schema") != GIT_BACKUP_SELECTION_SCHEMA
        or document.get("expected_plan_sha256") != expected_plan_sha256
    ):
        raise _fail("git_backup_selection_plan_mismatch")
    raw_groups = document.get("groups")
    if (
        not isinstance(raw_groups, list)
        or not raw_groups
        or len(raw_groups) > GIT_BACKUP_MAX_GROUPS
    ):
        raise _fail("git_backup_selection_invalid")
    groups: list[_SelectionGroup] = []
    seen_group_ids: set[str] = set()
    selected_refs: list[str] = []
    for ordinal, raw_group in enumerate(raw_groups):
        if not isinstance(raw_group, Mapping) or set(raw_group) != {
            "group_id",
            "change_refs",
            "commit_subject",
        }:
            raise _fail("git_backup_selection_invalid")
        group_id = raw_group.get("group_id")
        change_refs = raw_group.get("change_refs")
        subject = raw_group.get("commit_subject")
        if (
            type(group_id) is not str
            or _GROUP_ID_RE.fullmatch(group_id) is None
            or group_id in seen_group_ids
            or not isinstance(change_refs, list)
            or not change_refs
            or any(
                type(value) is not str or _CHANGE_REF_RE.fullmatch(value) is None
                for value in change_refs
            )
            or change_refs != sorted(set(change_refs))
            or type(subject) is not str
            or not subject.strip()
            or subject != subject.strip()
            or "\n" in subject
            or "\r" in subject
            or any(ord(character) < 32 or ord(character) == 127 for character in subject)
            or len(subject.encode("utf-8")) > GIT_BACKUP_MAX_COMMIT_SUBJECT_BYTES
            or _SENSITIVE_SUBJECT_RE.search(subject) is not None
        ):
            raise _fail("git_backup_selection_invalid")
        seen_group_ids.add(group_id)
        selected_refs.extend(change_refs)
        groups.append(
            _SelectionGroup(
                ordinal=ordinal,
                group_id=group_id,
                change_refs=tuple(change_refs),
                commit_subject=subject,
            )
        )
    if (
        len(selected_refs) != len(set(selected_refs))
        or set(selected_refs) != set(observed_change_refs)
    ):
        raise _fail("git_backup_selection_incomplete")
    selection_sha256 = _sha256_json(dict(document))
    return tuple(groups), selection_sha256


def _selection_partition(
    document: Mapping[str, Any],
    *,
    expected_plan_sha256: str,
    observed_change_refs: Sequence[str],
) -> tuple[tuple[_SelectionGroup, ...], str, tuple[Mapping[str, str], ...]]:
    """Keep v1 strict-all-selected; v2 binds every explicit exclusion as well."""

    if document.get("schema") != GIT_BACKUP_SELECTION_V2_SCHEMA:
        groups, selection_sha256 = _selection_groups(
            document,
            expected_plan_sha256=expected_plan_sha256,
            observed_change_refs=observed_change_refs,
        )
        return groups, selection_sha256, ()
    if set(document) != {
        "schema", "expected_plan_sha256", "selected_groups", "excluded_changes"
    }:
        raise _fail("git_backup_selection_invalid")
    if document.get("expected_plan_sha256") != expected_plan_sha256:
        raise _fail("git_backup_selection_plan_mismatch")
    exclusions = document.get("excluded_changes")
    if not isinstance(exclusions, list) or len(exclusions) > len(observed_change_refs):
        raise _fail("git_backup_selection_invalid")
    excluded_refs: list[str] = []
    for row in exclusions:
        if (
            not isinstance(row, Mapping)
            or set(row) != {"change_ref", "scope", "reason"}
            or type(row.get("change_ref")) is not str
            or _CHANGE_REF_RE.fullmatch(row["change_ref"]) is None
            or type(row.get("scope")) is not str
            or row["scope"] not in GIT_BACKUP_EXCLUSION_REASONS
            or row.get("reason") != GIT_BACKUP_EXCLUSION_REASONS[row["scope"]]
        ):
            raise _fail("git_backup_selection_invalid")
        excluded_refs.append(row["change_ref"])
    if (
        excluded_refs != sorted(set(excluded_refs))
        or not set(excluded_refs).issubset(observed_change_refs)
    ):
        raise _fail("git_backup_selection_incomplete")
    if document.get("selected_groups") == [] and set(excluded_refs) == set(observed_change_refs):
        raise _fail("git_backup_no_selected_changes")
    # Reuse the unchanged v1 group validator against precisely the complement;
    # it still rejects missing refs, overlap, duplicates and unknown changes.
    groups, _ = _selection_groups(
        {
            "schema": GIT_BACKUP_SELECTION_SCHEMA,
            "expected_plan_sha256": expected_plan_sha256,
            "groups": document.get("selected_groups"),
        },
        expected_plan_sha256=expected_plan_sha256,
        observed_change_refs=tuple(sorted(set(observed_change_refs) - set(excluded_refs))),
    )
    return groups, _sha256_json(dict(document)), tuple(dict(row) for row in exclusions)


def _validated_selection_v2_document(raw: bytes) -> dict[str, Any]:
    """Validate declared selection syntax, not live refs or session ownership."""

    code = "git_backup_selection_invalid"
    try:
        if type(raw) is not bytes or not 2 <= len(raw) <= GIT_BACKUP_MAX_SELECTION_BYTES:
            raise _fail(code)
        document = _strict_json(raw)
        expected = document.get("expected_plan_sha256")
        if (document.get("schema") != GIT_BACKUP_SELECTION_V2_SCHEMA
                or type(expected) is not str or _SHA256_RE.fullmatch(expected) is None):
            raise _fail(code)
        # The existing codec validates every row and the disjoint partition.
        # Completeness against the actual Git plan is checked again in prepare.
        refs: set[str] = set()
        groups, exclusions = document.get("selected_groups"), document.get("excluded_changes")
        if type(groups) is list:
            for group in groups:
                if type(group) is dict and type(group.get("change_refs")) is list:
                    refs.update(ref for ref in group["change_refs"] if type(ref) is str)
        if type(exclusions) is list:
            refs.update(row["change_ref"] for row in exclusions
                        if type(row) is dict and type(row.get("change_ref")) is str)
        _selection_partition(document, expected_plan_sha256=expected,
                             observed_change_refs=tuple(sorted(refs)))
        return document
    except GitBackupWriterError as error:
        code = error.code
    except (TypeError, ValueError, UnicodeError, RecursionError):
        pass
    # JSON/codec exceptions may retain private bytes even with `from None`.
    raise _fail(code)


@dataclass(frozen=True, slots=True, repr=False)
class _GitBackupSelectionV2:
    """Private immutable input only; it grants no archive or session authority."""

    raw_json: bytes

    def __post_init__(self) -> None:
        _validated_selection_v2_document(self.raw_json)

    def __repr__(self) -> str:
        return "_GitBackupSelectionV2(<private>)"


def _validated_git_backup_session_scope(scope, binding, selection_document, *, private_changes=None):
    if scope is None:
        return None
    try:
        if type(scope) is not _GitBackupSessionScope or type(binding) is not WorkSessionBinding:
            raise _fail("git_backup_session_scope_invalid")
        frozen = _GitBackupSessionScope.from_document(scope.document())
        frozen.validate_selection(binding, selection_document)
        if private_changes is not None:
            frozen.validate_sources(private_changes)
        return frozen
    except Exception:
        pass
    raise _fail("git_backup_session_scope_invalid")


def _change_paths(row: Mapping[str, Any]) -> tuple[str, ...]:
    paths = [row.get("path")]
    if row.get("original_path") is not None:
        paths.append(row["original_path"])
    if (
        any(type(path) is not str or not path for path in paths)
        or len(set(paths)) != len(paths)
        or not archive_services.wom_kit_project_update_safe_worktree_paths(paths)
    ):
        raise _fail("git_backup_manifest_drifted")
    return tuple(sorted(paths))


def _validated_work_session_binding(
    value: WorkSessionBinding | Mapping[str, Any] | None, archive_id: str,
) -> WorkSessionBinding | None:
    if value is None:
        return None
    try:
        if type(value) is WorkSessionBinding:
            binding = WorkSessionBinding.from_document(value.document())
        elif isinstance(value, Mapping):
            binding = WorkSessionBinding.from_document(value)
        else:
            raise WorkSessionBindingError()
        if binding.archive_identity_sha256 != exact_human_approval_archive_identity_sha256(archive_id):
            raise WorkSessionBindingError()
    except (WorkSessionBindingError, TypeError, ValueError):
        raise _fail("git_backup_work_session_binding_invalid") from None
    return binding


def _commit_message(
    subject: str, selection_sha256: str, ordinal: int, source_sha256: str,
    work_session_binding: WorkSessionBinding | None = None,
) -> bytes:
    message = (
        subject + "\n\n"
        + f"WOM-Git-Backup-Selection: {selection_sha256}\n"
        + f"WOM-Git-Backup-Group: {ordinal + 1:06d}\n"
        + f"WOM-Git-Backup-Source: {source_sha256}\n"
    )
    if work_session_binding is not None:
        message += (
            f"WOM-Client-App: {work_session_binding.client_app_ref}\n"
            f"WOM-Workstream: {work_session_binding.workstream_ref}\n"
            f"WOM-Work-Session: {work_session_binding.work_session_ref}\n"
            f"WOM-Work-Session-Revision: {work_session_binding.revision}\n"
            f"WOM-Work-Session-Binding: {work_session_binding.binding_sha256}\n"
        )
    return message.encode("utf-8")


def _literal_path_argv_metrics(paths: Sequence[str]) -> tuple[int, int]:
    """Return private UTF-8 bytes and Windows-quoted argv characters."""

    return (
        sum(len(path.encode("utf-8")) + 1 for path in paths),
        len(subprocess.list2cmdline(["--", *paths])),
    )


def _literal_path_argv_is_bounded(paths: Sequence[str]) -> bool:
    path_bytes, windows_chars = _literal_path_argv_metrics(paths)
    return bool(
        paths
        and path_bytes <= GIT_BACKUP_MAX_COMMAND_PATH_BYTES
        and windows_chars <= GIT_BACKUP_MAX_LITERAL_PATH_ARGV_CHARS
    )


def _build_exact_manifest(
    *,
    archive_id: str,
    groups: Sequence[_PreparedGroup],
    push_source_payload: bytes,
    push_target_identity_sha256: str,
    work_session_binding: WorkSessionBinding | None = None,
    session_scope: _GitBackupSessionScope | None = None,
) -> ExactOperationManifest:
    items: list[ExactOperationItem] = []
    for group in groups:
        items.append(
            ExactOperationItem(
                ordinal=group.ordinal,
                item_id=f"item:git_commit:{group.ordinal + 1:06d}",
                target_kind="git_commit_group",
                target_ref=group.target_ref,
                target_identity_sha256=group.target_identity_sha256,
                fields=(
                    ExactFieldEffect(
                        field_ref="commit_state",
                        pre_sha256=hash_field_value(_PENDING),
                        post_sha256=hash_field_value(_COMMITTED),
                        source_sha256=group.source_sha256,
                    ),
                ),
            )
        )
    push_ordinal = len(groups)
    items.append(
        ExactOperationItem(
            ordinal=push_ordinal,
            item_id=f"item:git_remote:{push_ordinal + 1:06d}",
            target_kind="git_remote_ref",
            target_ref="remote_ref:target",
            target_identity_sha256=push_target_identity_sha256,
            fields=(
                ExactFieldEffect(
                    field_ref="remote_state",
                    pre_sha256=hash_field_value(_PENDING),
                    post_sha256=hash_field_value(_REMOTE_VERIFIED),
                    source_sha256=_sha256_bytes(push_source_payload),
                ),
            ),
        )
    )
    return ExactOperationManifest.build(
        operation=ExactHumanApprovalOperation.git_backup.value,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(
            archive_id
        ),
        items=items,
        work_session_binding=work_session_binding,
        operation_evidence=session_scope.operation_evidence() if session_scope is not None else None,
    )


def prepare_git_backup(
    archive_root: Path | str,
    *,
    expected_plan_sha256: str,
    selection_manifest_path: Path | str,
    remote_name: str = "origin",
    branch: str | None = None,
    credential_mode: str = "anonymous",
    max_changes: int = planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGES,
    max_changed_bytes: int = planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGED_BYTES,
    progress_hook: Callable[[Mapping[str, Any]], None] | None = None,
    work_session_binding: WorkSessionBinding | Mapping[str, Any] | None = None,
) -> PreparedGitBackup:
    """Prepare one private exact operation without returning paths or prose."""

    return _prepare_git_backup_core(
        archive_root, expected_plan_sha256=expected_plan_sha256,
        selection_manifest_path=selection_manifest_path, selection=None, session_scope=None,
        remote_name=remote_name, branch=branch, credential_mode=credential_mode,
        max_changes=max_changes, max_changed_bytes=max_changed_bytes,
        progress_hook=progress_hook, work_session_binding=work_session_binding,
    )


def _prepare_git_backup_from_selection(
    archive_root: Path | str,
    *,
    expected_plan_sha256: str,
    selection: _GitBackupSelectionV2,
    remote_name: str = "origin",
    branch: str | None = None,
    credential_mode: str = "anonymous",
    max_changes: int = planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGES,
    max_changed_bytes: int = planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGED_BYTES,
    progress_hook: Callable[[Mapping[str, Any]], None] | None = None,
    work_session_binding: WorkSessionBinding | Mapping[str, Any] | None = None,
    session_scope: _GitBackupSessionScope | None = None,
) -> PreparedGitBackup:
    """Replan from typed private bytes without creating a selection file.

    This is preparation only. The execution boundary must independently verify
    its held archive lock, exact state, and any session authority it requires.
    """

    if type(selection) is not _GitBackupSelectionV2:
        raise _fail("git_backup_selection_invalid")
    # Revalidate and detach before a planner progress hook can run.
    frozen = _GitBackupSelectionV2(getattr(selection, "raw_json", None))
    frozen_scope = _validated_git_backup_session_scope(
        session_scope, work_session_binding, _strict_json(frozen.raw_json),
    )
    return _prepare_git_backup_core(
        archive_root, expected_plan_sha256=expected_plan_sha256,
        selection_manifest_path=None, selection=frozen, session_scope=frozen_scope,
        remote_name=remote_name, branch=branch, credential_mode=credential_mode,
        max_changes=max_changes, max_changed_bytes=max_changed_bytes,
        progress_hook=progress_hook, work_session_binding=work_session_binding,
    )


def _prepare_git_backup_core(
    archive_root: Path | str,
    *,
    expected_plan_sha256: str,
    selection_manifest_path: Path | str | None,
    selection: _GitBackupSelectionV2 | None,
    session_scope: _GitBackupSessionScope | None,
    remote_name: str,
    branch: str | None,
    credential_mode: str,
    max_changes: int,
    max_changed_bytes: int,
    progress_hook: Callable[[Mapping[str, Any]], None] | None,
    work_session_binding: WorkSessionBinding | Mapping[str, Any] | None,
) -> PreparedGitBackup:
    in_memory_raw = selection.raw_json if selection is not None else None
    if (
        type(expected_plan_sha256) is not str
        or _SHA256_RE.fullmatch(expected_plan_sha256) is None
        or credential_mode != "stored"
    ):
        raise _fail("git_backup_selection_plan_mismatch")
    binding = None
    if work_session_binding is not None:
        # Bound calls must reject another archive before planning can query its
        # configured remote. Freeze the supplied document before any callback.
        try:
            bound_root = archive_services.require_existing_archive_root(Path(archive_root))
            bound_archive_id = archive_services.read_archive_id(bound_root)
        except (archive_services.ArchiveServiceError, OSError):
            raise _fail("git_backup_exact_plan_blocked") from None
        binding = _validated_work_session_binding(work_session_binding, bound_archive_id)
    capture: dict[str, Any] = {}
    public_plan = planning.git_backup_plan(
        archive_root,
        remote_name=remote_name,
        branch=branch,
        credential_mode=credential_mode,
        max_changes=max_changes,
        max_changed_bytes=max_changed_bytes,
        dry_run=True,
        _private_capture=capture,
        progress_hook=progress_hook,
    )
    if public_plan.get("ok") is not True or not capture:
        raise _fail("git_backup_exact_plan_blocked")
    if not hmac.compare_digest(
        str(public_plan.get("plan_sha256") or ""),
        expected_plan_sha256,
    ):
        raise _fail("git_backup_selection_plan_mismatch")
    repository = public_plan.get("repository")
    relation = repository.get("relation") if isinstance(repository, Mapping) else None
    if (
        not isinstance(relation, Mapping)
        or relation.get("state") != "equal"
        or capture.get("remote_state") != "present"
        or type(capture.get("local_head_oid")) is not str
        or type(capture.get("remote_oid")) is not str
        or not hmac.compare_digest(
            capture["local_head_oid"],
            capture["remote_oid"],
        )
    ):
        raise _fail("git_backup_repository_relation_unsafe")

    raw_selection = (_read_stable_plain_file(Path(selection_manifest_path))
                     if in_memory_raw is None else in_memory_raw)
    selection_document = _strict_json(raw_selection)
    private_changes = capture.get("private_changes")
    if not isinstance(private_changes, list) or not private_changes:
        raise _fail("git_backup_selection_incomplete")
    by_ref: dict[str, Mapping[str, Any]] = {}
    for row in private_changes:
        if not isinstance(row, Mapping):
            raise _fail("git_backup_exact_plan_blocked")
        public = row.get("public_observation")
        change_ref = public.get("change_ref") if isinstance(public, Mapping) else None
        if type(change_ref) is not str or change_ref in by_ref:
            raise _fail("git_backup_exact_plan_blocked")
        by_ref[change_ref] = row
    groups, selection_sha256, exclusions = _selection_partition(
        selection_document,
        expected_plan_sha256=expected_plan_sha256,
        observed_change_refs=tuple(sorted(by_ref)),
    )
    binding = _validated_work_session_binding(binding, capture["archive_id"])
    if binding is not None and selection_document["schema"] != GIT_BACKUP_SELECTION_V2_SCHEMA:
        raise _fail("git_backup_work_session_binding_invalid")
    session_scope = _validated_git_backup_session_scope(
        session_scope, binding, selection_document, private_changes=private_changes,
    )

    prepared_groups: list[_PreparedGroup] = []
    all_paths: set[str] = set()
    for group in groups:
        selected_rows = tuple(by_ref[reference] for reference in group.change_refs)
        paths: list[str] = []
        for row in selected_rows:
            for key in ("path", "original_path"):
                value = row.get(key)
                if value is None:
                    continue
                if type(value) is not str or not value:
                    raise _fail("git_backup_exact_plan_blocked")
                paths.append(value)
        exact_paths = tuple(sorted(set(paths)))
        if (
            not _literal_path_argv_is_bounded(exact_paths)
            or any(path in all_paths for path in exact_paths)
        ):
            raise _fail("git_backup_selection_invalid")
        all_paths.update(exact_paths)
        group_basis = {
            "schema": "wom-kit/git-backup-commit-group-source/v1",
            "git_content_policy": GIT_BACKUP_CONTENT_POLICY,
            "expected_plan_sha256": expected_plan_sha256,
            "selection_sha256": selection_sha256,
            "group_ordinal": group.ordinal,
            "group_id": group.group_id,
            "commit_subject": group.commit_subject,
            "changes": [dict(row) for row in selected_rows],
        }
        if binding is not None:
            group_basis["schema"] = "wom-kit/git-backup-commit-group-source/v2"
            group_basis["work_session_binding"] = binding.document()
        source_payload = _canonical(group_basis)
        source_sha256 = _sha256_bytes(source_payload)
        target_identity_sha256 = _sha256_json(
            {
                "schema": "wom-kit/git-backup-commit-group-target/v1",
                "source_sha256": source_sha256,
                "path_set_sha256": _sha256_json(exact_paths),
            }
        )
        commit_message = _commit_message(
            group.commit_subject, selection_sha256, group.ordinal, source_sha256, binding
        )
        prepared_groups.append(
            _PreparedGroup(
                ordinal=group.ordinal,
                group_id=group.group_id,
                change_refs=group.change_refs,
                commit_subject=group.commit_subject,
                paths=exact_paths,
                source_payload=source_payload,
                source_sha256=source_sha256,
                target_identity_sha256=target_identity_sha256,
                commit_message=commit_message,
                private_changes=selected_rows,
            )
        )

    prepared_exclusions: list[Mapping[str, Any]] = []
    for exclusion in exclusions:
        row = by_ref[exclusion["change_ref"]]
        paths = _change_paths(row)
        if any(path in all_paths for path in paths):
            raise _fail("git_backup_selection_invalid")
        all_paths.update(paths)
        prepared_exclusions.append({**exclusion, "private_change": dict(row)})

    push_basis = {
        "schema": "wom-kit/git-backup-push-source/v1",
        "expected_plan_sha256": expected_plan_sha256,
        "selection_sha256": selection_sha256,
        "remote_name": capture.get("remote_name"),
        "remote_url": capture.get("remote_url"),
        "target_ref": capture.get("target_ref"),
        "initial_head_oid": capture.get("local_head_oid"),
        "initial_remote_oid": capture.get("remote_oid"),
        "commit_group_source_sha256": [
            group.source_sha256 for group in prepared_groups
        ],
    }
    if selection_document["schema"] == GIT_BACKUP_SELECTION_V2_SCHEMA:
        push_basis["schema"] = "wom-kit/git-backup-push-source/v2"
        push_basis["excluded_changes"] = prepared_exclusions
    if binding is not None:
        push_basis["work_session_binding"] = binding.document()
    push_source_payload = _canonical(push_basis)
    push_source_sha256 = _sha256_bytes(push_source_payload)
    push_target_identity_sha256 = _sha256_json(
        {
            "schema": "wom-kit/git-backup-push-target/v1",
            "push_source_sha256": push_source_sha256,
        }
    )
    manifest = _build_exact_manifest(
        archive_id=capture["archive_id"],
        groups=prepared_groups,
        push_source_payload=push_source_payload,
        push_target_identity_sha256=push_target_identity_sha256,
        work_session_binding=binding,
        session_scope=session_scope,
    )
    return PreparedGitBackup(
        root=Path(capture["root"]),
        archive_id=capture["archive_id"],
        remote_name=remote_name,
        remote_url=capture["remote_url"],
        credential_mode=credential_mode,
        target_ref=capture["target_ref"],
        initial_head_oid=capture["local_head_oid"],
        initial_remote_oid=capture["remote_oid"],
        expected_plan_sha256=expected_plan_sha256,
        selection_sha256=selection_sha256,
        git_executable_sha256=capture["git_executable_sha256"],
        git_config_trust_sha256=capture["git_config_trust_sha256"],
        groups=tuple(prepared_groups),
        push_source_payload=push_source_payload,
        push_target_identity_sha256=push_target_identity_sha256,
        manifest=manifest,
        max_changes=max_changes,
        max_changed_bytes=max_changed_bytes,
        selection_schema=selection_document["schema"],
        excluded_changes=tuple(prepared_exclusions),
        session_scope=session_scope,
    )


def _private_bundle_root(root: Path, *, create: bool) -> Path:
    current = root
    for part in (*Path(EXACT_OPERATION_LOCAL_ROOT).parts, "git-backup-plans"):
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            if not create:
                raise _fail("git_backup_manifest_drifted") from None
            try:
                os.mkdir(current, 0o700)
                info = os.lstat(current)
            except OSError:
                raise _fail("git_backup_manifest_drifted") from None
        except OSError:
            raise _fail("git_backup_manifest_drifted") from None
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or (reparse and getattr(info, "st_file_attributes", 0) & reparse)
        ):
            raise _fail("git_backup_manifest_drifted")
    return current


def _bundle_document(prepared: PreparedGitBackup) -> dict[str, Any]:
    basis = {
        "schema": "wom-kit/git-backup-private-execution-bundle/v1",
        "archive_id": prepared.archive_id,
        "remote_name": prepared.remote_name,
        "remote_url": prepared.remote_url,
        "credential_mode": prepared.credential_mode,
        "target_ref": prepared.target_ref,
        "initial_head_oid": prepared.initial_head_oid,
        "initial_remote_oid": prepared.initial_remote_oid,
        "expected_plan_sha256": prepared.expected_plan_sha256,
        "selection_sha256": prepared.selection_sha256,
        "git_executable_sha256": prepared.git_executable_sha256,
        "git_config_trust_sha256": prepared.git_config_trust_sha256,
        "max_changes": prepared.max_changes,
        "max_changed_bytes": prepared.max_changed_bytes,
        "groups": [
            {
                "ordinal": group.ordinal,
                "group_id": group.group_id,
                "change_refs": list(group.change_refs),
                "commit_subject": group.commit_subject,
                "paths": list(group.paths),
                "source": json.loads(group.source_payload.decode("ascii")),
                "source_sha256": group.source_sha256,
                "target_identity_sha256": group.target_identity_sha256,
                "private_changes": [dict(row) for row in group.private_changes],
            }
            for group in prepared.groups
        ],
        "push_source": json.loads(prepared.push_source_payload.decode("ascii")),
        "push_target_identity_sha256": prepared.push_target_identity_sha256,
        "manifest": prepared.manifest.document(),
    }
    if prepared.selection_schema == GIT_BACKUP_SELECTION_V2_SCHEMA:
        basis["schema"] = "wom-kit/git-backup-private-execution-bundle/v2"
        basis["excluded_changes"] = [dict(row) for row in prepared.excluded_changes]
    if prepared.manifest.work_session_binding is not None:
        if prepared.selection_schema != GIT_BACKUP_SELECTION_V2_SCHEMA:
            raise _fail("git_backup_manifest_drifted")
        basis["work_session_binding"] = prepared.manifest.work_session_binding.document()
    if prepared.session_scope is not None:
        if (prepared.selection_schema != GIT_BACKUP_SELECTION_V2_SCHEMA
                or prepared.manifest.work_session_binding is None
                or type(prepared.session_scope) is not _GitBackupSessionScope):
            raise _fail("git_backup_manifest_drifted")
        basis["session_scope"] = prepared.session_scope.document()
    return {**basis, "bundle_sha256": _sha256_json(basis)}


def _persist_private_bundle(
    prepared: PreparedGitBackup,
    *,
    writer_lock: ExactOperationWriterLock,
) -> None:
    writer_lock.verify_held()
    directory = _private_bundle_root(prepared.root, create=True)
    filename = prepared.manifest.manifest_sha256.removeprefix("sha256:") + ".json"
    path = directory / filename
    raw = _canonical(_bundle_document(prepared)) + b"\n"
    if len(raw) > GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES:
        raise _fail("git_backup_manifest_drifted")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags, 0o600)
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise OSError("short_bundle_write")
            offset += written
        os.fsync(descriptor)
    except FileExistsError:
        existing = _read_stable_plain_file(
            path,
            max_bytes=GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES,
        )
        if existing != raw:
            raise _fail("git_backup_manifest_drifted") from None
        return
    except (OSError, GitBackupWriterError):
        raise _fail("git_backup_manifest_drifted") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    reread = _read_stable_plain_file(
        path,
        max_bytes=GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES,
    )
    if reread != raw:
        raise _fail("git_backup_manifest_drifted")


def load_private_git_backup_bundle(
    archive_root: Path | str,
    *,
    manifest_sha256: str,
) -> PreparedGitBackup:
    if type(manifest_sha256) is not str or _SHA256_RE.fullmatch(manifest_sha256) is None:
        raise _fail("git_backup_manifest_drifted")
    root = archive_services.require_existing_archive_root(Path(archive_root))
    directory = _private_bundle_root(root, create=False)
    path = directory / (manifest_sha256.removeprefix("sha256:") + ".json")
    raw = _read_stable_plain_file(
        path,
        max_bytes=GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES,
    )
    if not raw.endswith(b"\n"):
        raise _fail("git_backup_manifest_drifted")
    document = _strict_json(raw[:-1])
    return _decode_private_git_backup_bundle(root, document, manifest_sha256=manifest_sha256)


def _decode_private_git_backup_bundle(
    root: Path, document: Mapping[str, Any], *, manifest_sha256: str,
) -> PreparedGitBackup:
    """Reconstruct exact execution facts without trusting convenience views."""

    is_v2 = document.get("schema") == "wom-kit/git-backup-private-execution-bundle/v2"
    has_binding = is_v2 and "work_session_binding" in document
    has_scope = is_v2 and "session_scope" in document
    expected_keys = {
        "schema",
        "archive_id",
        "remote_name",
        "remote_url",
        "credential_mode",
        "target_ref",
        "initial_head_oid",
        "initial_remote_oid",
        "expected_plan_sha256",
        "selection_sha256",
        "git_executable_sha256",
        "git_config_trust_sha256",
        "max_changes",
        "max_changed_bytes",
        "groups",
        "push_source",
        "push_target_identity_sha256",
        "manifest",
        "bundle_sha256",
    }
    if is_v2:
        expected_keys.add("excluded_changes")
    if has_binding:
        expected_keys.add("work_session_binding")
    if has_scope:
        expected_keys.add("session_scope")
    if set(document) != expected_keys:
        raise _fail("git_backup_manifest_drifted")
    basis = dict(document)
    supplied_bundle = basis.pop("bundle_sha256")
    if (
        document.get("schema")
        != (
            "wom-kit/git-backup-private-execution-bundle/v2"
            if is_v2 else "wom-kit/git-backup-private-execution-bundle/v1"
        )
        or type(supplied_bundle) is not str
        or not hmac.compare_digest(supplied_bundle, _sha256_json(basis))
        or document.get("credential_mode") != "stored"
        or archive_services.read_archive_id(root) != document.get("archive_id")
        or type(document.get("remote_name")) is not str
        or planning.GIT_BACKUP_REMOTE_NAME_RE.fullmatch(document["remote_name"])
        is None
        or type(document.get("remote_url")) is not str
        or not planning._safe_remote_url(document["remote_url"])
        or type(document.get("target_ref")) is not str
        or not planning._validate_full_branch_ref(document["target_ref"])
        or type(document.get("initial_head_oid")) is not str
        or _OID_RE.fullmatch(document["initial_head_oid"]) is None
        or type(document.get("initial_remote_oid")) is not str
        or _OID_RE.fullmatch(document["initial_remote_oid"]) is None
        or not hmac.compare_digest(
            document["initial_head_oid"], document["initial_remote_oid"]
        )
        or type(document.get("expected_plan_sha256")) is not str
        or _SHA256_RE.fullmatch(document["expected_plan_sha256"]) is None
        or type(document.get("selection_sha256")) is not str
        or _SHA256_RE.fullmatch(document["selection_sha256"]) is None
        or type(document.get("git_executable_sha256")) is not str
        or _SHA256_RE.fullmatch(document["git_executable_sha256"]) is None
        or type(document.get("git_config_trust_sha256")) is not str
        or _SHA256_RE.fullmatch(document["git_config_trust_sha256"]) is None
        or not planning._valid_limit(
            document.get("max_changes"),
            minimum=1,
            maximum=planning.GIT_BACKUP_PLAN_MAX_CHANGES,
        )
        or not planning._valid_limit(
            document.get("max_changed_bytes"),
            minimum=1,
            maximum=planning.GIT_BACKUP_PLAN_MAX_CHANGED_BYTES,
        )
    ):
        raise _fail("git_backup_manifest_drifted")
    binding = None
    if has_binding:
        if document["work_session_binding"] is None:
            raise _fail("git_backup_manifest_drifted")
        try:
            binding = _validated_work_session_binding(
                document["work_session_binding"], document["archive_id"]
            )
        except GitBackupWriterError:
            raise _fail("git_backup_manifest_drifted") from None
    session_scope = None
    if has_scope:
        try:
            if not has_binding:
                raise _fail("git_backup_manifest_drifted")
            session_scope = _GitBackupSessionScope.from_document(document["session_scope"])
        except Exception:
            pass
        if session_scope is None:
            raise _fail("git_backup_manifest_drifted")
    raw_groups = document.get("groups")
    if (
        not isinstance(raw_groups, list)
        or not raw_groups
        or len(raw_groups) > GIT_BACKUP_MAX_GROUPS
    ):
        raise _fail("git_backup_manifest_drifted")
    groups: list[_PreparedGroup] = []
    seen_group_ids: set[str] = set()
    seen_change_refs: set[str] = set()
    seen_paths: set[str] = set()
    for ordinal, value in enumerate(raw_groups):
        if not isinstance(value, Mapping) or set(value) != {
            "ordinal",
            "group_id",
            "change_refs",
            "commit_subject",
            "paths",
            "source",
            "source_sha256",
            "target_identity_sha256",
            "private_changes",
        }:
            raise _fail("git_backup_manifest_drifted")
        if value.get("ordinal") != ordinal:
            raise _fail("git_backup_manifest_drifted")
        source_payload = _canonical(value.get("source"))
        source_sha256 = _sha256_bytes(source_payload)
        paths = value.get("paths")
        change_refs = value.get("change_refs")
        private_changes = value.get("private_changes")
        subject = value.get("commit_subject")
        if (
            type(value.get("group_id")) is not str
            or _GROUP_ID_RE.fullmatch(value["group_id"]) is None
            or value["group_id"] in seen_group_ids
            or not isinstance(paths, list)
            or paths != sorted(set(paths))
            or any(type(path_value) is not str or not path_value for path_value in paths)
            or not archive_services.wom_kit_project_update_safe_worktree_paths(paths)
            or not _literal_path_argv_is_bounded(paths)
            or any(path_value in seen_paths for path_value in paths)
            or not isinstance(change_refs, list)
            or change_refs != sorted(set(change_refs))
            or not change_refs
            or any(type(ref) is not str or _CHANGE_REF_RE.fullmatch(ref) is None for ref in change_refs)
            or any(ref in seen_change_refs for ref in change_refs)
            or type(subject) is not str
            or not subject.strip()
            or subject != subject.strip()
            or "\n" in subject
            or "\r" in subject
            or any(ord(character) < 32 or ord(character) == 127 for character in subject)
            or len(subject.encode("utf-8")) > GIT_BACKUP_MAX_COMMIT_SUBJECT_BYTES
            or _SENSITIVE_SUBJECT_RE.search(subject) is not None
            or not isinstance(private_changes, list)
            or len(private_changes) != len(change_refs)
            or any(not isinstance(row, Mapping) for row in private_changes)
            or not hmac.compare_digest(str(value.get("source_sha256") or ""), source_sha256)
        ):
            raise _fail("git_backup_manifest_drifted")
        seen_group_ids.add(value["group_id"])
        seen_change_refs.update(change_refs)
        seen_paths.update(paths)
        source = value.get("source")
        if (
            not isinstance(source, Mapping)
            or source.get("schema")
            != (
                "wom-kit/git-backup-commit-group-source/v2"
                if has_binding else "wom-kit/git-backup-commit-group-source/v1"
            )
            or ("work_session_binding" in source) != has_binding
            or (has_binding and source.get("work_session_binding") != binding.document())
            or source.get("git_content_policy") != GIT_BACKUP_CONTENT_POLICY
            or source.get("expected_plan_sha256")
            != document["expected_plan_sha256"]
            or source.get("selection_sha256") != document["selection_sha256"]
            or source.get("group_ordinal") != ordinal
            or source.get("group_id") != value["group_id"]
            or source.get("commit_subject") != subject
            or source.get("changes") != private_changes
        ):
            raise _fail("git_backup_manifest_drifted")
        source_refs: list[str] = []
        source_paths: list[str] = []
        for row in private_changes:
            public = row.get("public_observation")
            if not isinstance(public, Mapping) or type(public.get("change_ref")) is not str:
                raise _fail("git_backup_manifest_drifted")
            source_refs.append(public["change_ref"])
            for key in ("path", "original_path"):
                path_value = row.get(key)
                if path_value is None and key == "original_path":
                    continue
                if type(path_value) is not str or not path_value:
                    raise _fail("git_backup_manifest_drifted")
                source_paths.append(path_value)
        if source_refs != change_refs or sorted(set(source_paths)) != paths:
            raise _fail("git_backup_manifest_drifted")
        target_identity = _sha256_json(
            {
                "schema": "wom-kit/git-backup-commit-group-target/v1",
                "source_sha256": source_sha256,
                "path_set_sha256": _sha256_json(tuple(paths)),
            }
        )
        if not hmac.compare_digest(
            str(value.get("target_identity_sha256") or ""),
            target_identity,
        ):
            raise _fail("git_backup_manifest_drifted")
        commit_message = _commit_message(
            subject, document["selection_sha256"], ordinal, source_sha256, binding
        )
        groups.append(
            _PreparedGroup(
                ordinal=ordinal,
                group_id=value["group_id"],
                change_refs=tuple(change_refs),
                commit_subject=subject,
                paths=tuple(paths),
                source_payload=source_payload,
                source_sha256=source_sha256,
                target_identity_sha256=target_identity,
                commit_message=commit_message,
                private_changes=tuple(dict(row) for row in private_changes),
            )
        )
    excluded_changes: tuple[Mapping[str, Any], ...] = ()
    if is_v2:
        raw_exclusions = document.get("excluded_changes")
        if not isinstance(raw_exclusions, list) or len(raw_exclusions) > document["max_changes"]:
            raise _fail("git_backup_manifest_drifted")
        exclusion_declarations: list[Mapping[str, str]] = []
        for row in raw_exclusions:
            if (
                not isinstance(row, Mapping)
                or set(row) != {"change_ref", "scope", "reason", "private_change"}
                or not isinstance(row.get("private_change"), Mapping)
            ):
                raise _fail("git_backup_manifest_drifted")
            private_change = row["private_change"]
            public = private_change.get("public_observation")
            if (
                not isinstance(public, Mapping)
                or public.get("change_ref") != row["change_ref"]
            ):
                raise _fail("git_backup_manifest_drifted")
            paths = _change_paths(private_change)
            if any(path in seen_paths for path in paths):
                raise _fail("git_backup_manifest_drifted")
            seen_paths.update(paths)
            exclusion_declarations.append({
                key: row[key] for key in ("change_ref", "scope", "reason")
            })
        selection_document = {
            "schema": GIT_BACKUP_SELECTION_V2_SCHEMA,
            "expected_plan_sha256": document["expected_plan_sha256"],
            "selected_groups": [
                {"group_id": group.group_id, "change_refs": list(group.change_refs),
                 "commit_subject": group.commit_subject}
                for group in groups
            ],
            "excluded_changes": exclusion_declarations,
        }
        try:
            _, selection_sha256, _ = _selection_partition(
                selection_document,
                expected_plan_sha256=document["expected_plan_sha256"],
                observed_change_refs=tuple(sorted(
                    seen_change_refs | {row["change_ref"] for row in exclusion_declarations}
                )),
            )
        except (GitBackupWriterError, TypeError, ValueError):
            raise _fail("git_backup_manifest_drifted") from None
        if not hmac.compare_digest(selection_sha256, document["selection_sha256"]):
            raise _fail("git_backup_manifest_drifted")
        excluded_changes = tuple(dict(row) for row in raw_exclusions)
    if session_scope is not None:
        session_scope = _validated_git_backup_session_scope(
            session_scope, binding, selection_document,
            private_changes=[row for group in groups for row in group.private_changes]
                            + [row["private_change"] for row in excluded_changes],
        )
    push_source_payload = _canonical(document.get("push_source"))
    push_source = document.get("push_source")
    if (
        not isinstance(push_source, Mapping)
        or set(push_source)
        != ({
            "schema",
            "expected_plan_sha256",
            "selection_sha256",
            "remote_name",
            "remote_url",
            "target_ref",
            "initial_head_oid",
            "initial_remote_oid",
            "commit_group_source_sha256",
        } | ({"excluded_changes"} if is_v2 else set())
          | ({"work_session_binding"} if has_binding else set()))
        or push_source.get("schema") != (
            "wom-kit/git-backup-push-source/v2"
            if is_v2 else "wom-kit/git-backup-push-source/v1"
        )
        or (is_v2 and push_source.get("excluded_changes") != list(excluded_changes))
        or (has_binding and push_source.get("work_session_binding") != binding.document())
        or push_source.get("expected_plan_sha256")
        != document["expected_plan_sha256"]
        or push_source.get("selection_sha256") != document["selection_sha256"]
        or push_source.get("remote_name") != document["remote_name"]
        or push_source.get("remote_url") != document["remote_url"]
        or push_source.get("target_ref") != document["target_ref"]
        or push_source.get("initial_head_oid") != document["initial_head_oid"]
        or push_source.get("initial_remote_oid") != document["initial_remote_oid"]
        or push_source.get("commit_group_source_sha256")
        != [group.source_sha256 for group in groups]
    ):
        raise _fail("git_backup_manifest_drifted")
    push_target = _sha256_json(
        {
            "schema": "wom-kit/git-backup-push-target/v1",
            "push_source_sha256": _sha256_bytes(push_source_payload),
        }
    )
    if not hmac.compare_digest(
        str(document.get("push_target_identity_sha256") or ""),
        push_target,
    ):
        raise _fail("git_backup_manifest_drifted")
    manifest = _build_exact_manifest(
        archive_id=document["archive_id"],
        groups=groups,
        push_source_payload=push_source_payload,
        push_target_identity_sha256=push_target,
        work_session_binding=binding,
        session_scope=session_scope,
    )
    supplied_manifest = ExactOperationManifest.from_document(document["manifest"])
    if (
        manifest.document() != supplied_manifest.document()
        or not hmac.compare_digest(manifest.manifest_sha256, manifest_sha256)
    ):
        raise _fail("git_backup_manifest_drifted")
    return PreparedGitBackup(
        root=root,
        archive_id=document["archive_id"],
        remote_name=document["remote_name"],
        remote_url=document["remote_url"],
        credential_mode="stored",
        target_ref=document["target_ref"],
        initial_head_oid=document["initial_head_oid"],
        initial_remote_oid=document["initial_remote_oid"],
        expected_plan_sha256=document["expected_plan_sha256"],
        selection_sha256=document["selection_sha256"],
        git_executable_sha256=document["git_executable_sha256"],
        git_config_trust_sha256=document["git_config_trust_sha256"],
        groups=tuple(groups),
        push_source_payload=push_source_payload,
        push_target_identity_sha256=push_target,
        manifest=manifest,
        max_changes=document["max_changes"],
        max_changed_bytes=document["max_changed_bytes"],
        selection_schema=(GIT_BACKUP_SELECTION_V2_SCHEMA if is_v2 else GIT_BACKUP_SELECTION_SCHEMA),
        excluded_changes=excluded_changes,
        session_scope=session_scope,
    )


def _freeze_validated_prepared(prepared: PreparedGitBackup) -> PreparedGitBackup:
    """Deeply detach execution observations only after all source bindings match.

    The historical bundle decoder already checks source observations, paths,
    commit subjects, remote facts and the reconstructed manifest. Reuse it in
    memory before any operation file or Git mutation; a frozen dataclass alone
    does not freeze the nested dictionaries held by a caller.
    """

    try:
        if type(prepared) is not PreparedGitBackup:
            raise _fail("git_backup_manifest_drifted")
        raw = _canonical(_bundle_document(prepared))
        if len(raw) + 1 > GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES:
            raise _fail("git_backup_manifest_drifted")
        root = archive_services.require_existing_archive_root(prepared.root)
        frozen = _decode_private_git_backup_bundle(
            root, _strict_json(raw), manifest_sha256=prepared.manifest.manifest_sha256,
        )
        # Includes derived commit-message bytes, which the bundle deliberately
        # reconstructs rather than retaining as another independent authority.
        if frozen != prepared:
            raise _fail("git_backup_manifest_drifted")
        return frozen
    except Exception:
        pass
    # Do not retain a rejected private value through exception chaining.
    raise _fail("git_backup_manifest_drifted")


def _private_change_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    public = result.get("public_observation")
    if isinstance(public, Mapping):
        public_projection = dict(public)
        public_projection.pop("change_ref", None)
        result["public_observation"] = public_projection
    return result


def _query_exact_remote_ref_with_stored_credentials(
    prepared: PreparedGitBackup,
) -> tuple[str, str | None]:
    """Query the approved URL and exact ref without returning either value."""

    if not planning._safe_remote_url(prepared.remote_url):
        return "unavailable", None
    command = planning._git_command(
        prepared.root,
        [
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.https.allow=always",
            "-c",
            "credential.interactive=never",
            "ls-remote",
            "--quiet",
            "--refs",
            "--exit-code",
            prepared.remote_url,
            prepared.target_ref,
        ],
    )
    environment = planning._local_git_environment()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GCM_INTERACTIVE"] = "never"
    result = planning._run_transport_capped(
        command,
        environment=environment,
        timeout_seconds=planning.GIT_BACKUP_REMOTE_TIMEOUT_SECONDS,
        max_output_bytes=64 * 1024,
    )
    if result is None:
        return "unavailable", None
    return_code, raw = result
    if return_code == 2 and raw == b"":
        return "target_ref_missing", None
    if return_code != 0:
        return "unavailable", None
    try:
        rows = [row for row in raw.decode("utf-8", errors="strict").splitlines() if row]
    except UnicodeError:
        return "invalid_response", None
    if len(rows) != 1:
        return "invalid_response", None
    fields = rows[0].split("\t")
    if (
        len(fields) != 2
        or fields[1] != prepared.target_ref
        or _OID_RE.fullmatch(fields[0].lower()) is None
    ):
        return "invalid_response", None
    return "present", fields[0].lower()


@contextmanager
def _pinned_git_runtime(prepared: PreparedGitBackup):
    pinned = planning._pin_git_executable()
    if (
        pinned is None
        or not hmac.compare_digest(pinned.sha256, prepared.git_executable_sha256)
    ):
        raise _fail("git_backup_git_executable_drifted")
    token = planning._PINNED_GIT_EXECUTABLE.set(pinned)
    active_error = False
    try:
        yield
    except BaseException:
        active_error = True
        raise
    finally:
        planning._PINNED_GIT_EXECUTABLE.reset(token)
        final = planning._pin_git_at(Path(pinned.path))
        if not active_error and final != pinned:
            raise _fail("git_backup_git_executable_drifted")


class _GitBackupBackend:
    def __init__(self, prepared: PreparedGitBackup, *, resume: bool = False) -> None:
        self.prepared = prepared
        self.resume = bool(resume)
        self._group_by_target = {
            group.target_ref: group for group in prepared.groups
        }
        self._cache: dict[str, Any] | None = None
        self._runtime_binding_last: bool | None = None
        self._runtime_binding_checked_monotonic: float | None = None
        self.commit_oids: list[str] = []
        self.final_remote_oid: str | None = None

    def invalidate(self) -> None:
        self._cache = None

    def _git_raw(
        self,
        args: list[str],
        *,
        max_output_bytes: int = GIT_BACKUP_MAX_COMMIT_OUTPUT_BYTES,
        timeout_seconds: int = planning.GIT_BACKUP_LOCAL_TIMEOUT_SECONDS,
        input_bytes: bytes | None = None,
        extra_environment: Mapping[str, str] | None = None,
    ) -> tuple[int, bytes] | None:
        environment = planning._local_git_environment()
        if extra_environment:
            environment.update(extra_environment)
        return archive_services._wom_kit_project_update_run_capped(
            planning._git_command(self.prepared.root, args),
            environment=environment,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
            input_bytes=input_bytes,
        )

    def _git_text(
        self,
        args: list[str],
        *,
        max_output_bytes: int = 64 * 1024,
    ) -> tuple[int, str] | None:
        result = self._git_raw(args, max_output_bytes=max_output_bytes)
        if result is None:
            return None
        try:
            return result[0], result[1].decode("utf-8", errors="strict").rstrip(
                "\r\n"
            )
        except UnicodeError:
            return None

    def _head(self) -> str | None:
        result = self._git_text(["rev-parse", "--verify", "HEAD"], max_output_bytes=128)
        value = result[1].lower() if result is not None and result[0] == 0 else ""
        return value if _OID_RE.fullmatch(value) is not None else None

    def _commit_object(self, oid: str) -> tuple[str, bytes] | None:
        result = self._git_raw(
            ["cat-file", "commit", oid],
            max_output_bytes=GIT_BACKUP_MAX_COMMIT_OUTPUT_BYTES,
        )
        if result is None or result[0] != 0 or b"\n\n" not in result[1]:
            return None
        headers, message = result[1].split(b"\n\n", 1)
        parents: list[str] = []
        for line in headers.splitlines():
            if line.startswith(b"parent "):
                try:
                    parent = line[7:].decode("ascii").lower()
                except UnicodeError:
                    return None
                if _OID_RE.fullmatch(parent) is None:
                    return None
                parents.append(parent)
        if len(parents) != 1:
            return None
        return parents[0], message

    def _commit_paths(self, oid: str) -> tuple[str, ...] | None:
        result = self._git_raw(
            [
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "--no-renames",
                "-r",
                "-z",
                oid,
            ],
            max_output_bytes=planning.GIT_BACKUP_PLAN_MAX_GIT_OUTPUT_BYTES,
        )
        if result is None or result[0] != 0:
            return None
        raw_paths = result[1].split(b"\0")
        if raw_paths and raw_paths[-1] == b"":
            raw_paths.pop()
        paths: list[str] = []
        try:
            for raw in raw_paths:
                value = raw.decode("utf-8", errors="strict")
                if not value:
                    return None
                paths.append(value)
        except UnicodeError:
            return None
        return tuple(sorted(set(paths))) if len(paths) == len(set(paths)) else None

    @staticmethod
    def _expected_group_worktree(
        group: _PreparedGroup,
    ) -> dict[str, Mapping[str, Any]] | None:
        expected: dict[str, Mapping[str, Any]] = {}
        for row in group.private_changes:
            path = row.get("path")
            public = row.get("public_observation")
            worktree = public.get("worktree") if isinstance(public, Mapping) else None
            if type(path) is not str or not isinstance(worktree, Mapping):
                return None
            if path in expected and dict(expected[path]) != dict(worktree):
                return None
            expected[path] = worktree
            original_path = row.get("original_path")
            original_worktree = row.get("original_worktree")
            if original_path is not None:
                if (
                    type(original_path) is not str
                    or not isinstance(original_worktree, Mapping)
                    or (
                        original_path in expected
                        and dict(expected[original_path]) != dict(original_worktree)
                    )
                ):
                    return None
                expected[original_path] = original_worktree
        return expected if set(expected) == set(group.paths) else None

    def _entries_match_expected(
        self,
        tree_entries: Mapping[str, tuple[str, str]],
        expected: Mapping[str, Mapping[str, Any]],
    ) -> bool:
        present_expected = {
            path
            for path, observation in expected.items()
            if observation.get("state") == "regular_file"
        }
        if set(tree_entries) != present_expected:
            return False
        if any(
            observation.get("state") not in {"regular_file", "missing"}
            for observation in expected.values()
        ):
            return False

        oid_expected: dict[str, tuple[int, str]] = {}
        for path in sorted(present_expected):
            mode, oid = tree_entries[path]
            observation = expected[path]
            size = observation.get("bytes")
            digest = observation.get("sha256")
            if (
                mode not in {"100644", "100755"}
                or type(size) is not int
                or size < 0
                or type(digest) is not str
                or _SHA256_RE.fullmatch(digest) is None
            ):
                return False
            prior = oid_expected.get(oid)
            if prior is not None and prior != (size, digest):
                return False
            oid_expected[oid] = (size, digest)
        if not oid_expected:
            return True
        total_bytes = sum(size for size, _ in oid_expected.values())
        if total_bytes > planning.GIT_BACKUP_PLAN_MAX_BLOB_BATCH_BYTES:
            return False
        request = b"".join(oid.encode("ascii") + b"\n" for oid in oid_expected)
        framing_cap = len(oid_expected) * 129
        blobs = self._git_raw(
            ["cat-file", "--batch"],
            max_output_bytes=total_bytes + framing_cap,
            input_bytes=request,
        )
        if blobs is None or blobs[0] != 0:
            return False
        output = blobs[1]
        cursor = 0
        for oid, (expected_size, expected_digest) in oid_expected.items():
            header_end = output.find(b"\n", cursor, min(len(output), cursor + 129))
            if header_end < 0:
                return False
            expected_header = f"{oid} blob {expected_size}".encode("ascii")
            if output[cursor:header_end].lower() != expected_header:
                return False
            blob_start = header_end + 1
            blob_end = blob_start + expected_size
            if blob_end >= len(output) or output[blob_end : blob_end + 1] != b"\n":
                return False
            if not hmac.compare_digest(
                _sha256_bytes(output[blob_start:blob_end]),
                expected_digest,
            ):
                return False
            cursor = blob_end + 1
        return cursor == len(output)

    def _tree_matches_group(self, treeish: str, group: _PreparedGroup) -> bool:
        """Verify exact selected tree paths and approved bytes in one batch."""

        expected = self._expected_group_worktree(group)
        if expected is None:
            return False
        tree_result = self._git_raw(
            ["ls-tree", "-r", "-z", treeish, "--", *group.paths],
            max_output_bytes=planning.GIT_BACKUP_PLAN_MAX_GIT_OUTPUT_BYTES,
        )
        if tree_result is None or tree_result[0] != 0:
            return False
        parsed = planning._parse_tree(tree_result[1])
        if parsed is None:
            return False
        tree_entries, symlinks, gitlinks = parsed
        return not symlinks and not gitlinks and self._entries_match_expected(
            tree_entries,
            expected,
        )

    def _index_matches_group(self, group: _PreparedGroup) -> bool:
        expected = self._expected_group_worktree(group)
        if expected is None:
            return False
        index_result = self._git_raw(
            ["ls-files", "--stage", "-z", "--", *group.paths],
            max_output_bytes=planning.GIT_BACKUP_PLAN_MAX_GIT_OUTPUT_BYTES,
        )
        if index_result is None or index_result[0] != 0:
            return False
        parsed = planning._parse_index(index_result[1])
        if parsed is None or parsed[1]:
            return False
        entries: dict[str, tuple[str, str]] = {}
        for path, rows in parsed[0].items():
            if len(rows) != 1 or rows[0][2] != 0:
                return False
            entries[path] = (rows[0][0], rows[0][1])
        return self._entries_match_expected(entries, expected)

    def _commit_prefix(self) -> tuple[str, ...] | None:
        head = self._head()
        if head is None:
            return None
        if hmac.compare_digest(head, self.prepared.initial_head_oid):
            return ()
        ancestor = self._git_raw(
            [
                "merge-base",
                "--is-ancestor",
                self.prepared.initial_head_oid,
                head,
            ],
            max_output_bytes=64,
        )
        if ancestor is None or ancestor[0] != 0:
            return None
        rows = self._git_text(
            [
                "rev-list",
                "--first-parent",
                "--reverse",
                f"{self.prepared.initial_head_oid}..{head}",
            ],
            max_output_bytes=max(128, (len(self.prepared.groups) + 1) * 66),
        )
        if rows is None or rows[0] != 0:
            return None
        commits = tuple(row.lower() for row in rows[1].splitlines() if row)
        if (
            len(commits) > len(self.prepared.groups)
            or any(_OID_RE.fullmatch(oid) is None for oid in commits)
        ):
            return None
        expected_parent = self.prepared.initial_head_oid
        for ordinal, oid in enumerate(commits):
            group = self.prepared.groups[ordinal]
            commit = self._commit_object(oid)
            if (
                commit is None
                or not hmac.compare_digest(commit[0], expected_parent)
                or commit[1] != group.commit_message
                or self._commit_paths(oid) != group.paths
                or not self._tree_matches_group(oid, group)
            ):
                return None
            expected_parent = oid
        return commits

    def _current_private_changes(self) -> tuple[Mapping[str, Any], ...] | None:
        branch = self.prepared.target_ref.removeprefix("refs/heads/")
        snapshot, blockers = planning._structural_snapshot(
            self.prepared.root,
            branch=branch,
            preflight_verified=False,
            max_status_records=self.prepared.max_changes,
        )
        if snapshot is None or blockers:
            return None
        observations, worktree_bytes, file_blockers = planning._observe_changed_files(
            self.prepared.root,
            snapshot["status"],
            max_total_bytes=self.prepared.max_changed_bytes,
        )
        if file_blockers:
            return None
        blobs, _, blob_blockers = planning._git_blob_inventory(
            self.prepared.root,
            snapshot,
            max_total_bytes=self.prepared.max_changed_bytes - worktree_bytes,
        )
        if blob_blockers:
            return None
        _, private, change_blockers = planning._change_inventory(
            snapshot,
            observations,
            blobs,
        )
        return tuple(private) if not change_blockers else None

    def _runtime_binding_matches(self, *, include_trust_digest: bool) -> bool:
        fetch_url = planning._configured_remote_url(
            self.prepared.root,
            self.prepared.remote_name,
        )
        push_urls = planning._local_git_text(
            self.prepared.root,
            [
                "remote",
                "get-url",
                "--push",
                "--all",
                self.prepared.remote_name,
            ],
            max_output_bytes=16 * 1024,
        )
        transport_matches = bool(
            fetch_url == self.prepared.remote_url
            and push_urls is not None
            and push_urls[0] == 0
            and push_urls[1].splitlines() == [self.prepared.remote_url]
        )
        return bool(
            transport_matches
            and (
                not include_trust_digest
                or planning._git_config_trust_digest(self.prepared.root)
                == self.prepared.git_config_trust_sha256
            )
        )

    def _verify_runtime_binding(
        self,
        *,
        fresh: bool,
        include_trust_digest: bool = True,
    ) -> bool:
        if fresh or self._runtime_binding_last is None:
            self._runtime_binding_last = self._runtime_binding_matches(
                include_trust_digest=include_trust_digest,
            )
            self._runtime_binding_checked_monotonic = time.monotonic()
        return self._runtime_binding_last is True

    def _refresh(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache
        commits = self._commit_prefix()
        runtime_binding_matches = self._verify_runtime_binding(fresh=False)
        current_changes = (
            self._current_private_changes() if runtime_binding_matches else None
        )
        by_path: dict[tuple[str, str | None], Mapping[str, Any]] = {}
        if current_changes is not None:
            for row in current_changes:
                key = (str(row.get("path") or ""), row.get("original_path"))
                if not key[0] or key in by_path:
                    current_changes = None
                    by_path = {}
                    break
                by_path[key] = row
        current_paths = {
            value
            for row in (current_changes or ())
            for value in (row.get("path"), row.get("original_path"))
            if type(value) is str
        }
        expected_pending_paths = (
            {
                path
                for group in self.prepared.groups[len(commits) :]
                for path in group.paths
            }
            if commits is not None
            else set()
        )
        excluded_match = self._excluded_changes_match(by_path)
        if excluded_match:
            expected_pending_paths.update(self._excluded_paths())
        self._cache = {
            "commits": commits,
            "changes": current_changes,
            "by_path": by_path,
            "runtime_binding_matches": runtime_binding_matches,
            "excluded_changes_match": excluded_match,
            "classification_complete": bool(
                commits is not None
                and current_changes is not None
                and current_paths == expected_pending_paths
                and excluded_match
            ),
        }
        return self._cache

    def _excluded_paths(self) -> set[str]:
        return {
            path
            for row in self.prepared.excluded_changes
            for path in _change_paths(row["private_change"])
        }

    def _excluded_changes_match(
        self, by_path: Mapping[tuple[str, str | None], Mapping[str, Any]]
    ) -> bool:
        if self.prepared.selection_schema == GIT_BACKUP_SELECTION_V2_SCHEMA:
            # Mutable caller-owned dictionaries cannot substitute observations
            # after approval; the source bytes, not these convenience views,
            # are the authority bound into the exact manifest.
            source = json.loads(self.prepared.push_source_payload.decode("ascii"))
            if (
                source.get("schema") != "wom-kit/git-backup-push-source/v2"
                or source.get("excluded_changes") != list(self.prepared.excluded_changes)
                or _sha256_bytes(self.prepared.push_source_payload)
                != self.prepared.manifest.items[-1].fields[0].source_sha256
            ):
                return False
            binding = self.prepared.manifest.work_session_binding
            binding_document = binding.document() if binding is not None else None
            if (
                ("work_session_binding" in source) != (binding is not None)
                or source.get("work_session_binding") != binding_document
            ):
                return False
            for group in self.prepared.groups:
                group_source = json.loads(group.source_payload.decode("ascii"))
                if (
                    ("work_session_binding" in group_source) != (binding is not None)
                    or group_source.get("work_session_binding") != binding_document
                    or group.commit_message != _commit_message(
                        group.commit_subject, self.prepared.selection_sha256,
                        group.ordinal, group.source_sha256, binding,
                    )
                ):
                    return False
        elif self.prepared.excluded_changes:
            return False
        for exclusion in self.prepared.excluded_changes:
            expected = exclusion["private_change"]
            current = by_path.get((expected["path"], expected.get("original_path")))
            # Ordinal refs are regenerated after selected commits disappear.
            # Every actual index/worktree value and identity remains bound.
            if current is None or _private_change_projection(current) != _private_change_projection(expected):
                return False
        return True

    def _worktree_matches_group(self, group: _PreparedGroup) -> bool:
        def matches(
            relative_path: str,
            expected_observation: Mapping[str, Any],
            expected_identity: Any,
        ) -> bool:
            observation = planning._hash_stable_plain_file(
                self.prepared.root,
                self.prepared.root.joinpath(*Path(relative_path).parts),
                max_bytes=planning.GIT_BACKUP_PLAN_MAX_FILE_BYTES,
            )
            return bool(
                planning._worktree_public_observation(observation)
                == dict(expected_observation)
                and (
                    list(observation.identity)
                    if observation.identity is not None
                    else None
                )
                == expected_identity
            )

        for row in group.private_changes:
            path = row.get("path")
            public = row.get("public_observation")
            worktree = public.get("worktree") if isinstance(public, Mapping) else None
            if (
                type(path) is not str
                or not isinstance(worktree, Mapping)
                or not matches(path, worktree, row.get("worktree_identity"))
            ):
                return False
            original_path = row.get("original_path")
            if original_path is not None:
                original_worktree = row.get("original_worktree")
                if (
                    type(original_path) is not str
                    or not isinstance(original_worktree, Mapping)
                    or not matches(
                        original_path,
                        original_worktree,
                        row.get("original_worktree_identity"),
                    )
                ):
                    return False
        return True

    def _resume_staged_group_is_pending(
        self,
        group: _PreparedGroup,
        *,
        commits: Sequence[str],
        changes: Sequence[Mapping[str, Any]],
    ) -> bool:
        if not self.resume or group.ordinal != len(commits):
            return False
        current_paths = {
            value
            for row in changes
            for value in (row.get("path"), row.get("original_path"))
            if type(value) is str
        }
        expected_pending_paths = {
            path
            for pending in self.prepared.groups[len(commits) :]
            for path in pending.paths
        }
        expected_pending_paths.update(self._excluded_paths())
        return bool(
            current_paths == expected_pending_paths
            and self._excluded_changes_match({
                (row["path"], row.get("original_path")): row for row in changes
            })
            and self._worktree_matches_group(group)
            and self._index_matches_group(group)
        )

    def _group_state(self, group: _PreparedGroup) -> bytes:
        state = self._refresh()
        commits = state["commits"]
        changes = state["changes"]
        if (
            commits is None
            or changes is None
            or state.get("classification_complete") is not True
        ):
            return _UNKNOWN
        if group.ordinal < len(commits):
            changed_paths = {
                path
                for row in changes
                for path in (row.get("path"), row.get("original_path"))
                if type(path) is str
            }
            if any(path in changed_paths for path in group.paths):
                return _UNKNOWN
            return _COMMITTED
        if group.ordinal > len(commits):
            # Later groups are also pending while earlier exact groups remain
            # uncommitted.  Their private observations must still be exact.
            pass
        by_path = state["by_path"]
        for expected in group.private_changes:
            key = (str(expected.get("path") or ""), expected.get("original_path"))
            current = by_path.get(key)
            if current is None or _private_change_projection(
                current
            ) != _private_change_projection(expected):
                return (
                    _PENDING
                    if self._resume_staged_group_is_pending(
                        group,
                        commits=commits,
                        changes=changes,
                    )
                    else _UNKNOWN
                )
        return _PENDING

    def _remote_observation(self) -> tuple[str, str | None]:
        return _query_exact_remote_ref_with_stored_credentials(self.prepared)

    def _remote_state(self) -> bytes:
        commits = self._refresh()["commits"]
        if (
            commits is None
            or self._refresh().get("classification_complete") is not True
        ):
            return _UNKNOWN
        remote_state, remote_oid = self._remote_observation()
        if remote_state != "present" or remote_oid is None:
            return _UNKNOWN
        head = self._head()
        if (
            len(commits) == len(self.prepared.groups)
            and head is not None
            and hmac.compare_digest(remote_oid, head)
        ):
            self.commit_oids = list(commits)
            self.final_remote_oid = remote_oid
            return _REMOTE_VERIFIED
        if hmac.compare_digest(remote_oid, self.prepared.initial_remote_oid):
            return _PENDING
        return _UNKNOWN

    @staticmethod
    def _path_batches(paths: Sequence[str]) -> Iterable[list[str]]:
        batch: list[str] = []
        size = 0
        for path in paths:
            encoded = len(path.encode("utf-8")) + 1
            if batch and size + encoded > GIT_BACKUP_MAX_COMMAND_PATH_BYTES:
                yield batch
                batch = []
                size = 0
            batch.append(path)
            size += encoded
        if batch:
            yield batch

    def _exact_add(self, group: _PreparedGroup) -> str:
        """Prove exact staging in an isolated index without touching user state."""

        descriptor, index_name = tempfile.mkstemp(prefix="wom-git-backup-", suffix=".index")
        os.close(descriptor)
        try:
            os.unlink(index_name)
            environment = {"GIT_INDEX_FILE": index_name}
            initialized = self._git_raw(
                ["read-tree", "HEAD"],
                max_output_bytes=64 * 1024,
                extra_environment=environment,
            )
            if initialized is None or initialized[0] != 0:
                raise _fail("git_backup_exact_add_failed")
            for batch in self._path_batches(group.paths):
                result = self._git_raw(
                    [
                        "-c",
                        "core.autocrlf=false",
                        "-c",
                        "core.safecrlf=true",
                        "add",
                        "--",
                        *batch,
                    ],
                    max_output_bytes=64 * 1024,
                    extra_environment=environment,
                )
                if result is None or result[0] != 0:
                    raise _fail("git_backup_exact_add_failed")
            written = self._git_text_with_environment(
                ["write-tree"],
                extra_environment=environment,
                max_output_bytes=128,
            )
            tree_oid = (
                written[1].lower()
                if written is not None and written[0] == 0
                else ""
            )
            if _OID_RE.fullmatch(tree_oid) is None:
                raise _fail("git_backup_exact_add_failed")
            delta = self._git_raw(
                [
                    "diff-tree",
                    "--no-commit-id",
                    "--name-only",
                    "--no-renames",
                    "-r",
                    "-z",
                    "HEAD",
                    tree_oid,
                ],
                max_output_bytes=planning.GIT_BACKUP_PLAN_MAX_GIT_OUTPUT_BYTES,
            )
            if delta is None or delta[0] != 0:
                raise _fail("git_backup_exact_add_failed")
            raw_paths = delta[1].split(b"\0")
            if raw_paths and raw_paths[-1] == b"":
                raw_paths.pop()
            try:
                delta_paths = tuple(
                    sorted(value.decode("utf-8", errors="strict") for value in raw_paths)
                )
            except UnicodeError:
                raise _fail("git_backup_exact_add_failed") from None
            if delta_paths != group.paths or not self._tree_matches_group(
                tree_oid,
                group,
            ):
                raise _fail("git_backup_exact_add_failed")
            return tree_oid
        finally:
            try:
                os.unlink(index_name)
            except OSError:
                pass

    def _git_text_with_environment(
        self,
        args: list[str],
        *,
        extra_environment: Mapping[str, str],
        max_output_bytes: int,
    ) -> tuple[int, str] | None:
        result = self._git_raw(
            args,
            max_output_bytes=max_output_bytes,
            extra_environment=extra_environment,
        )
        if result is None:
            return None
        try:
            return result[0], result[1].decode("ascii", errors="strict").strip()
        except UnicodeError:
            return None

    def _commit_group(self, group: _PreparedGroup) -> None:
        if self._group_state(group) == _COMMITTED:
            return
        if self._group_state(group) != _PENDING:
            raise _fail("git_backup_git_state_drifted")
        commits = self._refresh()["commits"]
        if commits is None or len(commits) != group.ordinal:
            raise _fail("git_backup_git_state_drifted")
        last_binding_check = self._runtime_binding_checked_monotonic
        if (
            last_binding_check is None
            or time.monotonic() - last_binding_check > 10.0
        ) and not self._verify_runtime_binding(fresh=True):
            raise _fail("git_backup_git_state_drifted")
        # The isolated index proves that `git add -- <exact paths>` produces
        # only the reviewed tree delta and exact approved blob bytes.  The
        # porcelain commit then receives the same bounded literal path list;
        # `--only` preserves any pre-existing staging outside this group.
        self._exact_add(group)
        exact_add = self._git_raw(
            [
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.safecrlf=true",
                "add",
                "--",
                *group.paths,
            ],
            max_output_bytes=64 * 1024,
        )
        self.invalidate()
        head_after_add = self._head()
        if (
            exact_add is None
            or exact_add[0] != 0
            or head_after_add is None
            or not hmac.compare_digest(
                head_after_add,
                (
                    self.prepared.initial_head_oid
                    if group.ordinal == 0
                    else commits[-1]
                ),
            )
            or not self._worktree_matches_group(group)
            or not self._index_matches_group(group)
            or (
                self.prepared.selection_schema == GIT_BACKUP_SELECTION_V2_SCHEMA
                and self._refresh().get("classification_complete") is not True
            )
        ):
            raise _fail("git_backup_exact_add_failed")
        descriptor, message_name = tempfile.mkstemp(prefix="wom-git-backup-", suffix=".msg")
        try:
            offset = 0
            while offset < len(group.commit_message):
                written = os.write(descriptor, group.commit_message[offset:])
                if written <= 0:
                    raise OSError("short_commit_message_write")
                offset += written
            os.fsync(descriptor)
        except OSError:
            raise _fail("git_backup_commit_failed") from None
        finally:
            os.close(descriptor)
        try:
            result = self._git_raw(
                [
                    "-c",
                    "core.autocrlf=false",
                    "-c",
                    "core.safecrlf=true",
                    "commit",
                    "--only",
                    "--no-verify",
                    "--no-gpg-sign",
                    "--cleanup=verbatim",
                    f"--file={message_name}",
                    "--",
                    *group.paths,
                ],
                timeout_seconds=GIT_BACKUP_COMMIT_TIMEOUT_SECONDS,
            )
        finally:
            try:
                os.unlink(message_name)
            except OSError:
                pass
        if result is None or result[0] != 0:
            raise _fail("git_backup_commit_failed")
        self.invalidate()
        if self._group_state(group) != _COMMITTED:
            raise _fail("git_backup_commit_verification_failed")

    def _push(self) -> None:
        # Recheck the privately approved effective fetch/push URL and complete
        # config digest immediately before the transport boundary.  Passing the
        # exact URL, rather than a mutable remote-name lookup, keeps the push
        # destination bound to the approved source.
        self.invalidate()
        if not self._verify_runtime_binding(
            fresh=True,
            include_trust_digest=False,
        ):
            raise _fail("git_backup_git_state_drifted")
        if self._remote_state() == _REMOTE_VERIFIED:
            return
        commits = self._refresh()["commits"]
        head = self._head()
        if (
            commits is None
            or len(commits) != len(self.prepared.groups)
            or head is None
            or (
                self.prepared.selection_schema == GIT_BACKUP_SELECTION_V2_SCHEMA
                and self._refresh().get("classification_complete") is not True
            )
        ):
            raise _fail("git_backup_git_state_drifted")
        remote_state, remote_oid = self._remote_observation()
        if (
            remote_state != "present"
            or remote_oid is None
            or not hmac.compare_digest(remote_oid, self.prepared.initial_remote_oid)
        ):
            raise _fail("git_backup_remote_verification_failed")
        environment = planning._local_git_environment()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["GCM_INTERACTIVE"] = "never"
        command = planning._git_command(
            self.prepared.root,
            [
                "-c",
                "protocol.allow=never",
                "-c",
                "protocol.https.allow=always",
                "-c",
                "credential.interactive=never",
                "push",
                "--porcelain",
                self.prepared.remote_url,
                f"{head}:{self.prepared.target_ref}",
            ],
        )
        result = planning._run_transport_capped(
            command,
            environment=environment,
            timeout_seconds=GIT_BACKUP_PUSH_TIMEOUT_SECONDS,
            max_output_bytes=GIT_BACKUP_MAX_COMMIT_OUTPUT_BYTES,
        )
        if result is None or result[0] != 0:
            raise _fail("git_backup_push_failed")
        self.invalidate()
        if self._remote_state() != _REMOTE_VERIFIED:
            raise _fail("git_backup_remote_verification_failed")

    def target_identity(self, target_kind: str, target_ref: str) -> str:
        if target_kind == "git_commit_group" and target_ref in self._group_by_target:
            return self._group_by_target[target_ref].target_identity_sha256
        if target_kind == "git_remote_ref" and target_ref == "remote_ref:target":
            return self.prepared.push_target_identity_sha256
        return _sha256_bytes(_UNKNOWN)

    def read(self, target_kind: str, target_ref: str, field_ref: str) -> bytes:
        if (
            target_kind == "git_commit_group"
            and field_ref == "commit_state"
            and target_ref in self._group_by_target
        ):
            return self._group_state(self._group_by_target[target_ref])
        if (
            target_kind == "git_remote_ref"
            and target_ref == "remote_ref:target"
            and field_ref == "remote_state"
        ):
            return self._remote_state()
        return _UNKNOWN

    def write(self, target_kind: str, target_ref: str, field_ref: str, value: bytes) -> None:
        if (
            target_kind == "git_commit_group"
            and field_ref == "commit_state"
            and value == _COMMITTED
            and target_ref in self._group_by_target
        ):
            self._commit_group(self._group_by_target[target_ref])
            return
        if (
            target_kind == "git_remote_ref"
            and target_ref == "remote_ref:target"
            and field_ref == "remote_state"
            and value == _REMOTE_VERIFIED
        ):
            self._push()
            return
        raise _fail("git_backup_git_state_drifted")


def _heartbeat_call(heartbeat: Callable[[], None], operation: Callable[[], Any]) -> Any:
    context = copy_context()
    completed = threading.Event()
    values: list[Any] = []
    failures: list[BaseException] = []

    def run() -> None:
        try:
            values.append(context.run(operation))
        except BaseException as exc:  # preserved only in-process and re-raised
            failures.append(exc)
        finally:
            completed.set()

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    heartbeat()
    while not completed.wait(timeout=1.0):
        heartbeat()
    worker.join()
    heartbeat()
    if failures:
        raise failures[0]
    return values[0] if values else None


class _GitBackupPayloads:
    def __init__(self, prepared: PreparedGitBackup) -> None:
        self.prepared = prepared
        self.groups = {group.target_ref: group for group in prepared.groups}

    def field_value(
        self,
        *,
        item_id: str,
        field_ref: str,
        state: str,
        heartbeat: Callable[[], None],
    ) -> bytes:
        heartbeat()
        if state == "source":
            if item_id.startswith("item:git_commit:"):
                ordinal = int(item_id.rsplit(":", 1)[1]) - 1
                if 0 <= ordinal < len(self.prepared.groups):
                    return self.prepared.groups[ordinal].source_payload
            if item_id.startswith("item:git_remote:"):
                return self.prepared.push_source_payload
        if item_id.startswith("item:git_commit:") and field_ref == "commit_state":
            return _PENDING if state == "pre" else _COMMITTED
        if item_id.startswith("item:git_remote:") and field_ref == "remote_state":
            return _PENDING if state == "pre" else _REMOTE_VERIFIED
        raise _fail("git_backup_manifest_drifted")


class _GitBackupVerifier:
    def __init__(self, backend: _GitBackupBackend) -> None:
        self.backend = backend

    def target_identity_sha256(
        self,
        *,
        target_kind: str,
        target_ref: str,
        heartbeat: Callable[[], None],
    ) -> str:
        heartbeat()
        return self.backend.target_identity(target_kind, target_ref)

    def read_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        heartbeat: Callable[[], None],
    ) -> bytes:
        return _heartbeat_call(
            heartbeat,
            lambda: self.backend.read(target_kind, target_ref, field_ref),
        )


class _GitBackupWriter:
    def __init__(self, backend: _GitBackupBackend) -> None:
        self.backend = backend

    def write_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        value: bytes | None,
        heartbeat: Callable[[], None],
    ) -> None:
        if value is None:
            raise _fail("git_backup_manifest_drifted")
        _heartbeat_call(
            heartbeat,
            lambda: self.backend.write(target_kind, target_ref, field_ref, value),
        )


def _safe_directory_chain(root: Path, parts: Sequence[str]) -> Path:
    current = root
    for part in parts:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            try:
                os.mkdir(current, 0o700)
                info = os.lstat(current)
            except OSError:
                raise _fail("git_backup_completion_receipt_failed") from None
        except OSError:
            raise _fail("git_backup_completion_receipt_failed") from None
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or (reparse and getattr(info, "st_file_attributes", 0) & reparse)
        ):
            raise _fail("git_backup_completion_receipt_failed")
    return current


def _persist_domain_receipt(
    prepared: PreparedGitBackup,
    *,
    writer_lock: ExactOperationWriterLock,
    authority: ExactOperationApprovalAuthority,
    result: Mapping[str, Any],
    backend: _GitBackupBackend,
) -> str:
    writer_lock.verify_held()
    execution_sha256 = result.get("execution_sha256")
    final_receipt_sha256 = result.get("final_receipt_sha256")
    if (
        type(execution_sha256) is not str
        or _SHA256_RE.fullmatch(execution_sha256) is None
        or type(final_receipt_sha256) is not str
        or _SHA256_RE.fullmatch(final_receipt_sha256) is None
        or len(backend.commit_oids) != len(prepared.groups)
        or backend.final_remote_oid is None
    ):
        raise _fail("git_backup_completion_receipt_failed")
    basis = {
        "schema": GIT_BACKUP_DOMAIN_RECEIPT_SCHEMA,
        "status": "completed",
        "manifest_sha256": prepared.manifest.manifest_sha256,
        "execution_sha256": execution_sha256,
        "approval_binding_sha256": authority.binding_sha256,
        "approval_id": authority.approval_id,
        "selection_sha256": prepared.selection_sha256,
        "initial_head_oid": prepared.initial_head_oid,
        "commit_count": len(backend.commit_oids),
        "commit_oid_set_sha256": _sha256_json(backend.commit_oids),
        "terminal_commit_oid": backend.final_remote_oid,
        "remote_ref_binding_sha256": _sha256_json(
            {
                "remote_name": prepared.remote_name,
                "target_ref": prepared.target_ref,
            }
        ),
        "exact_remote_ref_requeried": True,
        "remote_oid_matches_terminal_commit": True,
        "force_push_used": False,
        "pull_merge_rebase_reset_clean_delete_used": False,
        "common_final_receipt_sha256": final_receipt_sha256,
        "private_values_echoed": False,
    }
    if prepared.selection_schema == GIT_BACKUP_SELECTION_V2_SCHEMA:
        basis.update(
            selection_schema=prepared.selection_schema,
            selected_change_count=sum(len(group.change_refs) for group in prepared.groups),
            excluded_change_count=len(prepared.excluded_changes),
            excluded_index_and_worktree_observations_verified=True,
            exclusion_scope_source="explicit_declaration_not_ownership_attestation",
        )
    if prepared.manifest.work_session_binding is not None:
        basis["work_session_binding"] = prepared.manifest.work_session_binding.document()
    receipt_sha256 = _sha256_json(basis)
    document = {**basis, "receipt_sha256": receipt_sha256}
    raw = _canonical(document) + b"\n"
    directory = _safe_directory_chain(
        prepared.root,
        ("receipts", "ops", "git-backups"),
    )
    path = directory / (execution_sha256.removeprefix("sha256:") + ".json")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags, 0o600)
        offset = 0
        while offset < len(raw):
            count = os.write(descriptor, raw[offset:])
            if count <= 0:
                raise OSError("short_receipt_write")
            offset += count
        os.fsync(descriptor)
    except FileExistsError:
        try:
            existing = _read_stable_plain_file(path, max_bytes=1024 * 1024)
        except GitBackupWriterError:
            raise _fail("git_backup_completion_receipt_failed") from None
        if existing != raw:
            raise _fail("git_backup_completion_receipt_failed")
        return receipt_sha256
    except OSError:
        raise _fail("git_backup_completion_receipt_failed") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if _read_stable_plain_file(path, max_bytes=1024 * 1024) != raw:
        raise _fail("git_backup_completion_receipt_failed")
    return receipt_sha256


def _require_git_backup_held_lock(
    prepared: PreparedGitBackup,
    held: ExactOperationWriterLock,
) -> None:
    """Require the caller's real, still-held lock for this exact archive."""

    if type(held) is not ExactOperationWriterLock:
        raise _fail("git_backup_git_state_drifted")
    try:
        held.verify_held()
        if os.path.samefile(held.archive_root, prepared.root):
            return
    except (OSError, ExactOperationManifestError):
        pass
    # Raise outside the handler: even a suppressed exception context could
    # otherwise retain a private filesystem path from the failed observation.
    raise _fail("git_backup_git_state_drifted")


@contextmanager
def _git_backup_post_decision_boundary(
    prepared: PreparedGitBackup,
    lock_box: dict[str, ExactOperationWriterLock],
    *,
    held: ExactOperationWriterLock | None = None,
):
    _freeze_validated_prepared(prepared)
    claims_parent = (
        prepared.root
        / "profiles"
        / "local"
        / "exact-human-approvals"
        / "claims"
    )
    credential_parent = prepared.root / "profiles" / "local" / "credential-intake"
    with ExitStack() as stack:
        if held is None:
            lock = stack.enter_context(
                exact_operation_writer_lock(prepared.root, timeout_seconds=2.0)
            )
        else:
            _require_git_backup_held_lock(prepared, held)
            lock = held
        stack.enter_context(
            archive_services._activity_group_bound_directory_chain(
                prepared.root,
                credential_parent,
                create=True,
            )
        )
        claims_binding = stack.enter_context(
            archive_services._activity_group_bound_directory_chain(
                prepared.root,
                claims_parent,
                create=True,
            )
        )
        if held is not None:
            _require_git_backup_held_lock(prepared, held)
        lock_box["lock"] = lock
        try:
            yield prepared.root, claims_binding
        finally:
            lock_box.pop("lock", None)


def _require_legacy_git_backup_scope(prepared: PreparedGitBackup) -> None:
    # A scope records immutable facts, not current ownership or post-click
    # approval composition. No existing execution entry may infer that authority.
    if type(prepared) is not PreparedGitBackup:
        raise _fail("git_backup_manifest_drifted")
    if prepared.session_scope is not None:
        raise _fail("git_backup_scope_context_required")


def _apply_prepared_with_claim(
    prepared: PreparedGitBackup,
    *,
    context: ExactHumanApprovalContext,
    claim: _ClaimedExactHumanApproval,
    writer_lock: ExactOperationWriterLock,
    resume: bool,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
) -> dict[str, Any]:
    _require_legacy_git_backup_scope(prepared)
    prepared = _freeze_validated_prepared(prepared)
    result, backend = _run_git_backup_exact_operation(
        prepared, context=context, claim=claim, writer_lock=writer_lock,
        resume=resume, progress_hook=progress_hook,
    )
    authority = ExactOperationApprovalAuthority.from_reference(claim.assert_ready_for_context(context))
    git_receipt_sha256 = _persist_domain_receipt(
        prepared, writer_lock=writer_lock, authority=authority, result=result, backend=backend,
    )
    response = {
        **result,
        "ok": True,
        "lifecycle_action": "git_backup_exact_apply",
        "git_backup_completion_receipt_sha256": git_receipt_sha256,
        "commit_count": len(prepared.groups),
        "remote_ref_independently_requeried": True,
        "paths_echoed": False,
        "commit_messages_echoed": False,
        "remote_url_echoed": False,
        "credential_values_echoed": False,
        "private_values_echoed": False,
    }
    if prepared.selection_schema == GIT_BACKUP_SELECTION_V2_SCHEMA:
        response.update(
            selection_schema=prepared.selection_schema,
            selected_change_count=sum(len(group.change_refs) for group in prepared.groups),
            excluded_change_count=len(prepared.excluded_changes),
            excluded_index_and_worktree_observations_verified=True,
        )
    if prepared.manifest.work_session_binding is not None:
        response["work_session_binding"] = prepared.manifest.work_session_binding.document()
    return response


def _run_git_backup_exact_operation(
    prepared: PreparedGitBackup, *, context: ExactHumanApprovalContext,
    claim: _ClaimedExactHumanApproval, writer_lock: ExactOperationWriterLock,
    resume: bool, progress_hook: Callable[[ExactOperationProgress], None] | None,
):
    """Shared exact backend, with concrete admission for the scoped lane.

    No caller-supplied authority flag or guard can admit a scoped operation.
    Its workflow rechecks actual pending/current ownership and original MACs.
    Legacy callers retain their unsigned common result and domain receipt.
    """
    prepared = _freeze_validated_prepared(prepared)
    _require_git_backup_held_lock(prepared, writer_lock)
    expected_context = _git_backup_approval_context(
        prepared, reviewer_claim=context.reviewer_claim,
    )
    if not hmac.compare_digest(
        exact_human_approval_context_sha256(context),
        exact_human_approval_context_sha256(expected_context),
    ):
        raise _fail("git_backup_manifest_drifted")
    reference = claim.assert_ready_for_context(context)
    authority = ExactOperationApprovalAuthority.from_reference(reference)
    completion_options = {}
    domain_writer = None
    if prepared.session_scope is not None:
        from .work_session_git_workflow import (
            _require_pending_scope_held, _SessionGitBackupWriter, _SessionGitBackupVerifier,
        )
        _require_pending_scope_held(prepared, context=context, claim=claim, held=writer_lock)

        def authenticate_completion(payload):
            _require_pending_scope_held(prepared, context=context, claim=claim, held=writer_lock)
            return {"approval_reference": claim.public_reference(),
                    "terminal_mac": claim.exact_terminal_record_mac(payload)}

        completion_options["completion_authenticator"] = authenticate_completion
    _persist_private_bundle(prepared, writer_lock=writer_lock)
    checkpoint_store = FileExactOperationCheckpointStore(
        prepared.root,
        writer_lock=writer_lock,
    )
    backend = _GitBackupBackend(prepared, resume=resume)
    domain_writer = (_SessionGitBackupWriter(backend, context, claim, writer_lock)
                     if prepared.session_scope is not None else _GitBackupWriter(backend))
    with _pinned_git_runtime(prepared):
        result = apply_exact_operation(
            prepared.manifest,
            payloads=_GitBackupPayloads(prepared),
            writer=domain_writer,
            verifier=(_SessionGitBackupVerifier(backend) if prepared.session_scope is not None
                      else _GitBackupVerifier(backend)),
            checkpoint_store=checkpoint_store,
            approval_authority=authority,
            resume=resume,
            progress_hook=progress_hook,
            **completion_options,
        )
    return result, backend


def _git_backup_approval_context(
    prepared: PreparedGitBackup, *, reviewer_claim: str,
) -> ExactHumanApprovalContext:
    binding = exact_operation_manifest_approval_binding(
        prepared.manifest,
        operation=ExactHumanApprovalOperation.git_backup,
        archive_id=prepared.archive_id,
        warnings=(
            "git_backup_push_has_no_automatic_revert",
            "completion_receipt_is_written_after_push",
        ),
    )
    return binding.context(archive_id=prepared.archive_id, reviewer_claim=reviewer_claim)


def execute_git_backup(
    prepared: PreparedGitBackup,
    *,
    selection_manifest_path: Path | str,
    reviewer_claim: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    native: Any | None = None,
    key_provider: Any | None = None,
) -> dict[str, Any]:
    """Show one native approval, then re-observe, commit, push, and verify."""

    _require_legacy_git_backup_scope(prepared)
    _freeze_validated_prepared(prepared)
    return _execute_git_backup_core(
        prepared,
        selection_manifest_path=selection_manifest_path,
        reviewer_claim=reviewer_claim,
        progress_hook=progress_hook,
        native=native,
        key_provider=key_provider,
        held=None,
    )


def _execute_git_backup_held(
    prepared: PreparedGitBackup,
    *,
    held: ExactOperationWriterLock,
    selection_manifest_path: Path | str,
    reviewer_claim: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    native: Any | None = None,
    key_provider: Any | None = None,
) -> dict[str, Any]:
    """Compose the original writer under a caller-owned same-archive lock.

    The lock must already be held before native review and remains owned by
    the caller. This private seam neither attests current actor/provenance nor
    selects or resumes an original approval; those require separate evidence.
    """

    _require_legacy_git_backup_scope(prepared)
    _freeze_validated_prepared(prepared)
    _require_git_backup_held_lock(prepared, held)
    return _execute_git_backup_core(
        prepared,
        selection_manifest_path=selection_manifest_path,
        reviewer_claim=reviewer_claim,
        progress_hook=progress_hook,
        native=native,
        key_provider=key_provider,
        held=held,
    )


def _execute_git_backup_core(
    prepared: PreparedGitBackup,
    *,
    selection_manifest_path: Path | str,
    reviewer_claim: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None,
    native: Any | None,
    key_provider: Any | None,
    held: ExactOperationWriterLock | None,
) -> dict[str, Any]:
    _require_legacy_git_backup_scope(prepared)
    _freeze_validated_prepared(prepared)
    context = _git_backup_approval_context(prepared, reviewer_claim=reviewer_claim)
    lock_box: dict[str, ExactOperationWriterLock] = {}

    def writer(claim: _ClaimedExactHumanApproval) -> Mapping[str, Any]:
        # Approval claims and the common writer lock intentionally live below
        # ignored local-only roots.  Rebuilding the *public* plan here would
        # therefore drift its ignored-inventory digest because of the approval
        # machinery itself.  Re-read the private selection, then let the exact
        # runner freshly re-observe every bound commit group, HEAD/index state,
        # and exact remote ref under the common lock before its first write.
        selection_document = _strict_json(
            _read_stable_plain_file(Path(selection_manifest_path))
        )
        if not hmac.compare_digest(
            _sha256_json(selection_document),
            prepared.selection_sha256,
        ):
            raise _fail("git_backup_manifest_drifted")
        lock = lock_box.get("lock")
        if lock is None:
            raise _fail("git_backup_git_state_drifted")
        if held is not None:
            if lock is not held:
                raise _fail("git_backup_git_state_drifted")
            _require_git_backup_held_lock(prepared, held)
        return _apply_prepared_with_claim(
            prepared,
            context=context,
            claim=claim,
            writer_lock=lock,
            resume=False,
            progress_hook=progress_hook,
        )

    return _execute_exact_human_approved_write_core(
        prepared.root,
        context,
        writer,
        native=native,
        key_provider=key_provider,
        post_decision_boundary=lambda: _git_backup_post_decision_boundary(
            prepared,
            lock_box,
            held=held,
        ),
    )


def resume_git_backup(
    prepared: PreparedGitBackup,
    *,
    reviewer_claim: str,
    approval_id: str,
    progress_hook: Callable[[ExactOperationProgress], None] | None = None,
    key_provider: Any | None = None,
) -> dict[str, Any]:
    """Resume one authenticated started claim and its exact checkpoint only."""

    _require_legacy_git_backup_scope(prepared)
    _freeze_validated_prepared(prepared)
    context = _git_backup_approval_context(prepared, reviewer_claim=reviewer_claim)
    lock_box: dict[str, ExactOperationWriterLock] = {}
    authority_box: dict[str, ExactOperationApprovalAuthority] = {}

    def checkpoint_guard(claim: _ClaimedExactHumanApproval) -> bool:
        lock = lock_box.get("lock")
        if lock is None:
            return False
        reference = claim.assert_ready_for_context(context)
        authority = ExactOperationApprovalAuthority.from_reference(reference)
        execution_sha256 = exact_operation_execution_sha256(
            prepared.manifest,
            mode="apply",
            approval_authority=authority,
        )
        store = FileExactOperationCheckpointStore(
            prepared.root,
            writer_lock=lock,
        )
        present = store.resume_checkpoint_present(execution_sha256)
        if present:
            authority_box["authority"] = authority
        return present

    def writer(claim: _ClaimedExactHumanApproval) -> Mapping[str, Any]:
        lock = lock_box.get("lock")
        if lock is None or "authority" not in authority_box:
            raise _fail("git_backup_git_state_drifted")
        reference = claim.assert_ready_for_context(context)
        current_authority = ExactOperationApprovalAuthority.from_reference(reference)
        if current_authority != authority_box["authority"]:
            raise _fail("git_backup_manifest_drifted")
        return _apply_prepared_with_claim(
            prepared,
            context=context,
            claim=claim,
            writer_lock=lock,
            resume=True,
            progress_hook=progress_hook,
        )

    return _resume_exact_human_approved_write_core(
        prepared.root,
        context,
        approval_id,
        checkpoint_guard,
        writer,
        key_provider=key_provider,
        resume_boundary=lambda: _git_backup_post_decision_boundary(
            prepared,
            lock_box,
        ),
    )


__all__ = [
    "GIT_BACKUP_EXACT_PLAN_SCHEMA",
    "GIT_BACKUP_SELECTION_SCHEMA",
    "GIT_BACKUP_SELECTION_V2_SCHEMA",
    "GIT_BACKUP_EXCLUSION_REASONS",
    "GitBackupWriterError",
    "PreparedGitBackup",
    "execute_git_backup",
    "load_private_git_backup_bundle",
    "prepare_git_backup",
    "resume_git_backup",
]
