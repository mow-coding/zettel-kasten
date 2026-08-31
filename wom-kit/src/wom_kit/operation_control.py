"""Bounded, content-free CLI operation journals and read-only control views.

The journal is deliberately observational.  It is not a queue, daemon, lock,
receipt, or substitute for command-specific authority checks.  v0.3 keeps
cancel and resume unsupported until transaction-aware control points exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import threading
import time
from typing import Any, Callable

from . import project_update_transaction


OPERATION_JOURNAL_SCHEMA = "wom-kit/operation-journal/v0.2"
LEGACY_OPERATION_JOURNAL_SCHEMA = "wom-kit/operation-journal/v0.1"
OPERATION_CONTROL_SCHEMA = "wom-kit/operation-control/v0.1"
OPERATION_REF_RE = re.compile(r"op:sha256:([0-9a-f]{64})")
RUN_ID_RE = re.compile(r"[0-9a-f]{32}")
SAFE_REVIEWER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}")
CONTROL_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
SAFE_DOMAIN_VALUE_RE = re.compile(r"[a-z][a-z0-9_]{0,127}")
SAFE_RELEASE_TAG_RE = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
SAFE_COLLISION_REF_RE = re.compile(r"update-entry:(?!0000)[0-9]{4}")
MAX_DOMAIN_BLOCKER_CODES = 32
MAX_DOMAIN_COLLISION_REFS = 32
MAX_STAGED_CLEANUP_SUMMARY_COUNT = 1_000_000
STAGED_CLEANUP_STATES = frozenset(
    {"safe_to_cleanup", "not_safe_to_cleanup", "inspection_blocked"}
)
STAGED_CLEANUP_REASON_CODES = frozenset(
    {
        "unsafe_staged_folder",
        "staged_folder_missing",
        "deferred_list_unreadable",
        "deferred_list_invalid",
        "staged_tree_unreadable",
        "staged_entry_not_preserved",
        "staged_entries_not_preserved",
        "staged_entry_unsafe",
        "staged_entries_unsafe",
        "staged_entry_unreadable",
        "staged_entry_path_unsafe",
        "staged_entry_explicitly_deferred",
        "staged_entries_deferred",
        "unsafe_symlink",
        "unsafe_entry",
        "objet_preservation_evidence_missing",
        "objet_capture_receipt_missing",
        "objet_capture_receipt_invalid",
        "objet_capture_receipt_scan_incomplete",
        "objet_manifest_missing",
        "objet_manifest_path_unsafe",
        "objet_manifest_scan_incomplete",
        "objet_store_missing",
        "objet_store_sha256_mismatch",
        "objet_store_missing_or_sha256_mismatch",
        "ordinary_manifest_missing",
        "ordinary_store_missing",
        "ordinary_store_mismatch",
        "derived_text_source_bytes_changed_by_normalization",
        "derived_text_manifest_missing",
        "derived_text_manifest_invalid",
        "derived_text_manifest_scan_incomplete",
        "derived_text_store_missing",
        "derived_text_store_sha256_mismatch",
        "derived_text_capture_receipt_missing",
        "derived_text_capture_receipt_invalid",
        "derived_text_receipt_scan_incomplete",
        "derived_text_receipt_missing",
        "derived_text_store_mismatch",
        "derived_text_source_mismatch",
        "derived_representation_only",
        "derived_text_receipt_not_terminal",
        "derived_text_receipt_unsupported",
        "legacy_receipt_not_exact",
        "evidence_scan_incomplete",
        "staged_tree_changed_during_inspection",
        "staged_evidence_changed_during_inspection",
    }
)
STAGED_CLEANUP_SUMMARY_KEYS = (
    "preserved",
    "deferred",
    "not_preserved",
    "unsafe",
)

MAX_JOURNAL_BYTES = 1024 * 1024
MAX_JOURNAL_RECORDS = 4096
MAX_JOURNAL_LINE_BYTES = 16 * 1024
MAX_RESULT_BYTES = 64 * 1024 * 1024
MAX_RESULT_SCAN_ENTRIES = 4096
MAX_RESULT_SCAN_BYTES = 256 * 1024 * 1024
HEARTBEAT_INTERVAL_SECONDS = 10.0
HEARTBEAT_STALE_SECONDS = 35.0
MAX_FUTURE_SKEW_SECONDS = 5.0
MAX_WAIT_SECONDS = 60

ARCHIVE_OUTPUT_PREFIX = ".wom-scratch/diagnostics/"
PROJECT_OUTPUT_PREFIX = ".zettel-kasten/diagnostics/"
ARCHIVE_JOURNAL_RELATIVE = PurePosixPath(
    ".wom-scratch/diagnostics/.operations"
)
PROJECT_JOURNAL_RELATIVE = PurePosixPath(".zettel-kasten/operations")

COMMAND_KINDS = {
    "project-version-update": "project_version_update",
    "index": "archive_index",
    "index-health": "archive_index_health",
    "staged-cleanup-check": "staged_cleanup_check",
}
KIND_COMMANDS = {value: key for key, value in COMMAND_KINDS.items()}
COMMAND_STAGES = {
    "project-version-update": frozenset(
        {
            "starting",
            "project-preflight",
            "fetch-release",
            "verify-release",
            "checkout-release",
            "write-pins",
            "write-receipt",
            "unknown",
        }
    ),
    "index": frozenset(
        {
            "starting",
            "index-lock-and-schema",
            "index-zettels",
            "index-objects",
            "index-derived-texts",
            "index-views",
            "index-source-maps",
            "index-commit",
            "unknown",
        }
    ),
    "index-health": frozenset(
        {
            "starting",
            "index-health-live-zettels",
            "index-health-index-rows",
            "index-health-compare",
            "unknown",
        }
    ),
    "staged-cleanup-check": frozenset(
        {
            "starting",
            "manifest",
            "zettel-references",
            "staged-walk",
            "verify",
            "source-hash",
            "store-hash",
            "unknown",
        }
    ),
}
JOURNAL_EVENTS = frozenset(
    {
        "started",
        "checkpoint",
        "heartbeat",
        "completed",
        "result_unavailable",
    }
)
RECORD_KEYS = (
    "schema",
    "operation_ref",
    "operation_kind",
    "root_ref",
    "output_ref",
    "run_id",
    "owner_ref",
    "control_digest",
    "sequence",
    "event",
    "stage",
    "observed_at",
    "elapsed_ms",
    "last_completed_stage",
    "terminal",
    "result_available",
    "result_ok",
    "exit_code",
    "result_sha256",
    "result_bytes",
    "terminal_delivery_acknowledged",
    "terminal_handoff_sha256",
    "recovery_required",
    "previous_record_sha256",
    "record_sha256",
)
LEGACY_RECORD_KEYS = tuple(
    key
    for key in RECORD_KEYS
    if key
    not in {
        "terminal_delivery_acknowledged",
        "terminal_handoff_sha256",
    }
)
PROJECT_UPDATE_TERMINAL_CONSUMED_PREFIX = (
    ".zettel-kasten/private/version-update-terminal/"
)
PROJECT_UPDATE_TERMINAL_ACTIVE_RELATIVE = (
    ".zettel-kasten/private/version-update-terminal/active.json"
)
PROJECT_UPDATE_TERMINAL_DISPLAY_PENDING_RELATIVE = (
    ".zettel-kasten/private/version-update-terminal/display-pending.json"
)
PROJECT_UPDATE_TERMINAL_GUARD_RELATIVE = (
    ".zettel-kasten/private/version-update-terminal/.handoff.guard"
)
PROJECT_UPDATE_TERMINAL_CAPSULE_MAX_BYTES = 4 * 1024 * 1024


class OperationControlError(RuntimeError):
    """Closed operation-control failure without a raw local error."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _is_reparse(observed: os.stat_result) -> bool:
    return bool(
        getattr(observed, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _require_real_directory(path: Path) -> os.stat_result:
    try:
        observed = os.lstat(path)
    except OSError:
        raise OperationControlError("operation_control_root_unavailable") from None
    if (
        stat.S_ISLNK(observed.st_mode)
        or _is_reparse(observed)
        or not stat.S_ISDIR(observed.st_mode)
    ):
        raise OperationControlError("operation_control_root_unsafe")
    return observed


def require_control_root(root: Path | str) -> Path:
    absolute = Path(os.path.abspath(str(Path(root))))
    _require_real_directory(absolute)
    try:
        resolved = absolute.resolve(strict=True)
        if not os.path.samefile(absolute, resolved):
            raise OperationControlError("operation_control_root_unsafe")
    except OperationControlError:
        raise
    except OSError:
        raise OperationControlError("operation_control_root_unavailable") from None
    return absolute


def _root_ref(root: Path) -> str:
    """Return an opaque binding to this exact, currently observed root."""

    observed = _require_real_directory(root)
    try:
        resolved = root.resolve(strict=True)
    except OSError:
        raise OperationControlError("operation_control_root_unavailable") from None
    framed = (
        "wom-kit-operation-root-v0.1\0"
        + os.path.normcase(str(resolved))
        + "\0"
        + str(int(observed.st_dev))
        + "\0"
        + str(int(observed.st_ino))
    ).encode("utf-8")
    return "root:sha256:" + hashlib.sha256(framed).hexdigest()


def _path_below(root: Path, relative: PurePosixPath) -> Path:
    if relative.is_absolute() or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise OperationControlError("operation_control_path_unsafe")
    candidate = root.joinpath(*relative.parts)
    try:
        if os.path.commonpath((str(root), str(candidate))) != str(root):
            raise OperationControlError("operation_control_path_unsafe")
    except ValueError:
        raise OperationControlError("operation_control_path_unsafe") from None
    return candidate


def _ensure_real_directory_chain(root: Path, relative: PurePosixPath) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        try:
            os.mkdir(current)
        except FileExistsError:
            pass
        except OSError:
            raise OperationControlError(
                "operation_journal_directory_unavailable"
            ) from None
        _require_real_directory(current)
    return current


def _validate_existing_chain(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise OperationControlError("operation_control_path_unsafe") from None
    current = root
    _require_real_directory(current)
    for part in relative.parts[:-1]:
        current = current / part
        _require_real_directory(current)


def _journal_relative_for_output(output_relative: str) -> PurePosixPath:
    normalized = output_relative.replace("\\", "/").strip()
    if normalized.startswith(ARCHIVE_OUTPUT_PREFIX):
        return ARCHIVE_JOURNAL_RELATIVE
    if normalized.startswith(PROJECT_OUTPUT_PREFIX):
        return PROJECT_JOURNAL_RELATIVE
    raise OperationControlError("operation_output_scope_invalid")


def _canonical_record_bytes(record: dict[str, Any]) -> bytes:
    payload = dict(record)
    payload.pop("record_sha256", None)
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _record_digest(record: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_record_bytes(record)).hexdigest()


def _operation_ref(
    command: str,
    run_id: str,
    output_ref: str,
    root_ref: str,
) -> str:
    framed = (
        "wom-kit-operation-ref-v0.1\0"
        + command
        + "\0"
        + run_id
        + "\0"
        + output_ref
        + "\0"
        + root_ref
    ).encode("utf-8")
    return "op:sha256:" + hashlib.sha256(framed).hexdigest()


def _output_ref(output_relative: str) -> str:
    normalized = output_relative.replace("\\", "/").strip()
    return "output:sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _opaque_digest(prefix: str, operation_ref: str, run_id: str) -> str:
    framed = f"{prefix}\0{operation_ref}\0{run_id}".encode("ascii")
    return f"{prefix}:sha256:" + hashlib.sha256(framed).hexdigest()


def _operation_hex(operation_ref: str) -> str:
    match = OPERATION_REF_RE.fullmatch(str(operation_ref or ""))
    if match is None:
        raise OperationControlError("operation_ref_invalid")
    return match.group(1)


def _require_result_path(root: Path, path: Path) -> os.stat_result:
    absolute = Path(os.path.abspath(str(path)))
    try:
        observed = os.lstat(absolute)
    except OSError:
        raise OperationControlError("operation_result_unavailable") from None
    if (
        stat.S_ISLNK(observed.st_mode)
        or _is_reparse(observed)
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_nlink != 1
        or not 0 < observed.st_size <= MAX_RESULT_BYTES
    ):
        raise OperationControlError("operation_result_unavailable")

    # Derive the descendant path from verified directory identities instead
    # of lexical spelling.  On Windows the same root may arrive through an
    # 8.3 alias while the output path is expanded to its long spelling.  Each
    # traversed parent is still lstat-checked, so aliases are accepted without
    # accepting a symlink/reparse escape.
    root_observed = _require_real_directory(root)
    root_identity = (
        int(root_observed.st_dev),
        int(root_observed.st_ino),
    )
    parts = [absolute.name]
    current = absolute.parent
    relative_path: PurePosixPath | None = None
    for _depth in range(256):
        current_observed = _require_real_directory(current)
        if (
            int(current_observed.st_dev),
            int(current_observed.st_ino),
        ) == root_identity:
            relative_path = PurePosixPath(*reversed(parts))
            break
        parent = current.parent
        if parent == current:
            break
        parts.append(current.name)
        current = parent
    if relative_path is None:
        raise OperationControlError("operation_result_path_unsafe") from None
    relative = relative_path.as_posix()
    if not (
        relative.startswith(ARCHIVE_OUTPUT_PREFIX)
        or relative.startswith(PROJECT_OUTPUT_PREFIX)
    ) or "/.operations/" in f"/{relative}":
        raise OperationControlError("operation_result_path_unsafe")
    return observed


def _hash_result_artifact(
    root: Path,
    path: Path,
) -> tuple[str, int, dict[str, Any]]:
    observed = _require_result_path(root, path)
    digest = hashlib.sha256()
    total = 0
    chunks: list[bytes] = []
    try:
        descriptor = os.open(
            str(path), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
        try:
            current = os.fstat(descriptor)
            if (
                not stat.S_ISREG(current.st_mode)
                or current.st_nlink != 1
                or (int(current.st_dev), int(current.st_ino))
                != (int(observed.st_dev), int(observed.st_ino))
                or current.st_size != observed.st_size
            ):
                raise OSError("operation_result_identity_changed")
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_RESULT_BYTES:
                    raise OSError("operation_result_too_large")
                digest.update(chunk)
                chunks.append(chunk)
            final = os.fstat(descriptor)
            if (
                (int(final.st_dev), int(final.st_ino))
                != (int(observed.st_dev), int(observed.st_ino))
                or final.st_size != observed.st_size
                or total != observed.st_size
            ):
                raise OSError("operation_result_identity_changed")
        finally:
            os.close(descriptor)
    except OSError:
        raise OperationControlError("operation_result_unavailable") from None
    try:
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise OperationControlError("operation_result_invalid") from None
    if not isinstance(payload, dict):
        raise OperationControlError("operation_result_invalid")
    return "sha256:" + digest.hexdigest(), total, payload


def _validated_result_payload(
    payload: dict[str, Any],
    *,
    operation_ref: str,
    run_id: str,
    root_ref: str,
    output_ref: str,
    command: str,
) -> tuple[int, bool, bool] | None:
    execution = payload.get("cli_execution")
    artifact = payload.get("cli_output_artifact")
    operation = artifact.get("operation") if isinstance(artifact, dict) else None
    exit_code = execution.get("exit_code") if isinstance(execution, dict) else None
    command_result_available = (
        execution.get("result_available")
        if isinstance(execution, dict)
        else None
    )
    inspection_ok = payload.get("ok")
    if command == "staged-cleanup-check":
        safe_to_cleanup = payload.get("safe_to_cleanup")
        if type(inspection_ok) is not bool or (
            inspection_ok is True and type(safe_to_cleanup) is not bool
        ) or (
            inspection_ok is False
            and safe_to_cleanup is not None
            and type(safe_to_cleanup) is not bool
        ):
            return None
        result_ok = bool(inspection_ok and safe_to_cleanup is True)
    else:
        result_ok = inspection_ok
    if (
        not isinstance(execution, dict)
        or not isinstance(artifact, dict)
        or not isinstance(operation, dict)
        or execution.get("status") != "completed"
        or execution.get("run_id") != run_id
        or execution.get("command") != command
        or artifact.get("command") != command
        or operation.get("operation_ref") != operation_ref
        or operation.get("root_ref") != root_ref
        or operation.get("output_ref") != output_ref
        or operation.get("operation_kind") != COMMAND_KINDS[command]
        or not isinstance(exit_code, int)
        or isinstance(exit_code, bool)
        or not 0 <= exit_code <= 255
        or type(command_result_available) is not bool
        or type(result_ok) is not bool
        or ((exit_code == 0) is not result_ok)
    ):
        return None
    return exit_code, result_ok, command_result_available


def _safe_matching_values(
    value: object,
    *,
    pattern: re.Pattern[str],
    limit: int,
) -> list[str]:
    if not isinstance(value, list) or len(value) > limit:
        return []
    matched: list[str] = []
    for item in value:
        if not isinstance(item, str) or pattern.fullmatch(item) is None:
            return []
        if item not in matched:
            matched.append(item)
    return matched


def _safe_domain_projection(
    payload: dict[str, Any],
    *,
    command: str,
) -> dict[str, Any] | None:
    """Project a tiny allowlisted command result without copying raw text.

    Operation control proves that the complete output artifact is bound to the
    journal.  It does not make domain claims true.  This projection exists only
    so a later process can distinguish a successful output transport from a
    blocked project update and give one blocker-specific, path-free next step.
    """

    if command == "staged-cleanup-check":
        return _safe_staged_cleanup_domain_projection(payload)
    if command != "project-version-update":
        return None
    raw_status = payload.get("status")
    status = (
        raw_status
        if isinstance(raw_status, str)
        and SAFE_DOMAIN_VALUE_RE.fullmatch(raw_status) is not None
        else None
    )
    target = payload.get("target")
    raw_target_tag = target.get("tag") if isinstance(target, dict) else None
    target_tag = (
        raw_target_tag
        if isinstance(raw_target_tag, str)
        and SAFE_RELEASE_TAG_RE.fullmatch(raw_target_tag) is not None
        else None
    )

    containers = [payload]
    for key in ("materialization_preflight", "materialization_plan"):
        candidate = payload.get(key)
        if isinstance(candidate, dict):
            containers.append(candidate)
    blocker_codes: list[str] = []
    collision_refs: list[str] = []
    materialization_plan_digests: list[str] = []
    for container in containers:
        plan_digest = container.get("materialization_plan_sha256")
        if (
            isinstance(plan_digest, str)
            and CONTROL_DIGEST_RE.fullmatch(plan_digest) is not None
            and plan_digest not in materialization_plan_digests
        ):
            materialization_plan_digests.append(plan_digest)
        for key in ("blocker_codes", "reason_codes"):
            for code in _safe_matching_values(
                container.get(key),
                pattern=SAFE_DOMAIN_VALUE_RE,
                limit=MAX_DOMAIN_BLOCKER_CODES,
            ):
                if (
                    code not in blocker_codes
                    and len(blocker_codes) < MAX_DOMAIN_BLOCKER_CODES
                ):
                    blocker_codes.append(code)
        for key in ("collision_refs", "entry_refs"):
            for entry_ref in _safe_matching_values(
                container.get(key),
                pattern=SAFE_COLLISION_REF_RE,
                limit=MAX_DOMAIN_COLLISION_REFS,
            ):
                if (
                    entry_ref not in collision_refs
                    and len(collision_refs) < MAX_DOMAIN_COLLISION_REFS
                ):
                    collision_refs.append(entry_ref)
        for key in ("collision_ref", "entry_ref"):
            entry_ref = container.get(key)
            if (
                isinstance(entry_ref, str)
                and SAFE_COLLISION_REF_RE.fullmatch(entry_ref) is not None
                and entry_ref not in collision_refs
                and len(collision_refs) < MAX_DOMAIN_COLLISION_REFS
            ):
                collision_refs.append(entry_ref)
        issue_values = container.get("issues")
        if not isinstance(issue_values, list):
            issue_values = container.get("collisions")
        if not isinstance(issue_values, list):
            issue_values = container.get("conflicts")
        if isinstance(issue_values, list) and len(issue_values) <= 128:
            for issue in issue_values:
                if not isinstance(issue, dict):
                    continue
                reason = issue.get("reason_code")
                if (
                    isinstance(reason, str)
                    and SAFE_DOMAIN_VALUE_RE.fullmatch(reason) is not None
                    and reason not in blocker_codes
                    and len(blocker_codes) < MAX_DOMAIN_BLOCKER_CODES
                ):
                    blocker_codes.append(reason)
                for reason_code in _safe_matching_values(
                    issue.get("reason_codes"),
                    pattern=SAFE_DOMAIN_VALUE_RE,
                    limit=MAX_DOMAIN_BLOCKER_CODES,
                ):
                    if (
                        reason_code not in blocker_codes
                        and len(blocker_codes) < MAX_DOMAIN_BLOCKER_CODES
                    ):
                        blocker_codes.append(reason_code)
                for key in ("collision_ref", "entry_ref"):
                    entry_ref = issue.get(key)
                    if (
                        isinstance(entry_ref, str)
                        and SAFE_COLLISION_REF_RE.fullmatch(entry_ref) is not None
                        and entry_ref not in collision_refs
                        and len(collision_refs) < MAX_DOMAIN_COLLISION_REFS
                    ):
                        collision_refs.append(entry_ref)

    result_ok = payload.get("ok")
    if type(result_ok) is not bool:
        return None
    terminal = payload.get("terminal_finalization")
    terminal_projection: dict[str, Any] | None = None
    terminal_boolean_fields = (
        "update_result_verified_in_current_invocation",
        "update_result_reauthenticated_from_durable_handoff",
        "claim_succeeded_verified",
        "transaction_completed_checkpoint_verified",
        "lock_absence_verified",
        "transaction_cleanup_completed",
        "service_resource_close_verified",
        "git_runner_close_verified",
        "attention_required",
        "domain_writer_reentry_allowed",
        "automatic_retry_allowed",
        "cleanup_proof_used_as_success_authority",
        "durable_terminal_handoff_ready",
        "durable_terminal_handoff_replayed",
        "durable_result_delivery_acknowledged",
        "private_paths_echoed",
        "private_identifiers_echoed",
    )
    terminal_keys = {"schema", *terminal_boolean_fields}
    if (
        type(terminal) is dict
        and set(terminal) == terminal_keys
        and terminal.get("schema")
        == "wom-kit/project-version-update-terminal-finalization/v0.1"
        and all(
            type(terminal.get(field)) is bool
            for field in terminal_boolean_fields
        )
        and terminal["claim_succeeded_verified"] is True
        and terminal["transaction_completed_checkpoint_verified"] is True
        and terminal["lock_absence_verified"] is True
        and terminal["domain_writer_reentry_allowed"] is False
        and terminal["automatic_retry_allowed"] is False
        and terminal["cleanup_proof_used_as_success_authority"] is False
        and terminal["durable_terminal_handoff_ready"] is True
        # The immutable CLI artifact is published before the ready capsule is
        # consumed.  It must therefore record delivery as pending.  Only the
        # exact operation-bound consumed capsule projection below may turn
        # this field true for status/readers.
        and terminal["durable_result_delivery_acknowledged"] is False
        and terminal["private_paths_echoed"] is False
        and terminal["private_identifiers_echoed"] is False
        and (
            terminal["update_result_verified_in_current_invocation"]
            is not terminal[
                "update_result_reauthenticated_from_durable_handoff"
            ]
        )
        and terminal["durable_terminal_handoff_replayed"]
        is terminal["update_result_reauthenticated_from_durable_handoff"]
        and terminal["attention_required"]
        is not (
            terminal["transaction_cleanup_completed"]
            and terminal["service_resource_close_verified"]
            and terminal["git_runner_close_verified"]
            and terminal["durable_result_delivery_acknowledged"]
        )
        and result_ok is True
    ):
        terminal_projection = {
            "schema": terminal["schema"],
            **{
                field: terminal[field]
                for field in terminal_boolean_fields
            },
        }
    materialization_plan_sha256 = (
        materialization_plan_digests[0]
        if len(materialization_plan_digests) == 1
        else None
    )
    terminal_finalization_invalid = bool(
        terminal is not None and terminal_projection is None
    )
    return {
        "command": "project-version-update",
        "status": status,
        "completion_ok": result_ok,
        "attention_required": bool(
            not result_ok
            or terminal_finalization_invalid
            or (
                terminal_projection is not None
                and terminal_projection["attention_required"] is True
            )
        ),
        "terminal_finalization": terminal_projection,
        "terminal_finalization_invalid": terminal_finalization_invalid,
        "target_tag": target_tag,
        "blocker_codes": blocker_codes,
        "collision_refs": collision_refs,
        "materialization_plan_sha256": materialization_plan_sha256,
        "local_paths_echoed": False,
        "private_values_echoed": False,
        "raw_blocker_messages_copied": False,
    }


def _canonical_document_sha256(value: Any) -> str:
    try:
        raw = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        return ""
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _project_update_private_file_sha256(
    root: Path,
    path: Path,
) -> str | None:
    if not os.path.lexists(path):
        try:
            relative = path.relative_to(root)
        except ValueError:
            raise OperationControlError(
                "operation_control_path_unsafe"
            ) from None
        current = root
        _require_real_directory(current)
        for part in relative.parts[:-1]:
            current = current / part
            try:
                observed_parent = os.lstat(current)
            except FileNotFoundError:
                return None
            except OSError:
                raise OperationControlError(
                    "operation_control_root_unavailable"
                ) from None
            if (
                stat.S_ISLNK(observed_parent.st_mode)
                or _is_reparse(observed_parent)
                or not stat.S_ISDIR(observed_parent.st_mode)
            ):
                raise OperationControlError(
                    "operation_control_root_unsafe"
                )
        if not os.path.lexists(path):
            return None
    _validate_existing_chain(root, path)
    try:
        observed = os.lstat(path)
    except FileNotFoundError:
        return None
    if (
        stat.S_ISLNK(observed.st_mode)
        or _is_reparse(observed)
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_nlink != 1
        or not 0 < observed.st_size
        <= PROJECT_UPDATE_TERMINAL_CAPSULE_MAX_BYTES
    ):
        raise OperationControlError("operation_control_path_unsafe")
    descriptor = os.open(
        str(path),
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        current = os.fstat(descriptor)
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or (int(current.st_dev), int(current.st_ino))
            != (int(observed.st_dev), int(observed.st_ino))
            or current.st_size != observed.st_size
        ):
            raise OperationControlError("operation_control_path_unsafe")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > PROJECT_UPDATE_TERMINAL_CAPSULE_MAX_BYTES:
                raise OperationControlError(
                    "operation_control_path_unsafe"
                )
            digest.update(chunk)
        final = os.fstat(descriptor)
        if (
            (int(final.st_dev), int(final.st_ino))
            != (int(observed.st_dev), int(observed.st_ino))
            or final.st_size != observed.st_size
            or total != observed.st_size
        ):
            raise OperationControlError("operation_control_path_unsafe")
    finally:
        os.close(descriptor)
    return "sha256:" + digest.hexdigest()


def _project_update_private_file_bytes(
    root: Path,
    path: Path,
    *,
    expected_sha256: str,
) -> bytes:
    """Read one exact private capsule without exposing its locator."""

    if re.fullmatch(r"sha256:[0-9a-f]{64}", expected_sha256) is None:
        raise OperationControlError("operation_terminal_delivery_invalid")
    _validate_existing_chain(root, path)
    try:
        observed = os.lstat(path)
    except OSError:
        raise OperationControlError("operation_terminal_delivery_invalid") from None
    if (
        stat.S_ISLNK(observed.st_mode)
        or _is_reparse(observed)
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_nlink != 1
        or not 0 < observed.st_size
        <= PROJECT_UPDATE_TERMINAL_CAPSULE_MAX_BYTES
    ):
        raise OperationControlError("operation_terminal_delivery_invalid")
    try:
        descriptor = os.open(
            str(path),
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError:
        raise OperationControlError("operation_terminal_delivery_invalid") from None
    try:
        current = os.fstat(descriptor)
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or (int(current.st_dev), int(current.st_ino))
            != (int(observed.st_dev), int(observed.st_ino))
            or current.st_size != observed.st_size
        ):
            raise OperationControlError("operation_terminal_delivery_invalid")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > PROJECT_UPDATE_TERMINAL_CAPSULE_MAX_BYTES:
                raise OperationControlError("operation_terminal_delivery_invalid")
            chunks.append(chunk)
        final = os.fstat(descriptor)
        if (
            (int(final.st_dev), int(final.st_ino))
            != (int(observed.st_dev), int(observed.st_ino))
            or final.st_size != observed.st_size
            or total != observed.st_size
        ):
            raise OperationControlError("operation_terminal_delivery_invalid")
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    observed_sha256 = "sha256:" + hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(observed_sha256, expected_sha256):
        raise OperationControlError("operation_terminal_delivery_invalid")
    return raw


def _project_update_consumed_capsule_matches(
    root: Path,
    handoff_sha256: object,
) -> tuple[bool, bool, bool]:
    durability_flush_attempted = False
    durability_flush_verified = False
    if not isinstance(handoff_sha256, str) or re.fullmatch(
        r"sha256:[0-9a-f]{64}",
        handoff_sha256,
    ) is None:
        return False, False, False
    relative = PurePosixPath(
        PROJECT_UPDATE_TERMINAL_CONSUMED_PREFIX
        + handoff_sha256.removeprefix("sha256:")
        + ".json"
    )
    try:
        active = _path_below(
            root,
            PurePosixPath(PROJECT_UPDATE_TERMINAL_ACTIVE_RELATIVE),
        )
        active_sha256 = _project_update_private_file_sha256(root, active)
        if active_sha256 is not None and hmac.compare_digest(
            active_sha256,
            handoff_sha256,
        ):
            return False, False, False
        display_pending = _path_below(
            root,
            PurePosixPath(
                PROJECT_UPDATE_TERMINAL_DISPLAY_PENDING_RELATIVE
            ),
        )
        display_pending_sha256 = _project_update_private_file_sha256(
            root,
            display_pending,
        )
        consumed = _path_below(root, relative)
        consumed_sha256 = _project_update_private_file_sha256(
            root,
            consumed,
        )
        pending_matches = bool(
            display_pending_sha256 is not None
            and hmac.compare_digest(
                display_pending_sha256,
                handoff_sha256,
            )
        )
        consumed_matches = bool(
            consumed_sha256 is not None
            and hmac.compare_digest(consumed_sha256, handoff_sha256)
        )
        if pending_matches and consumed_matches:
            return False, False, False
        if pending_matches or consumed_matches:
            # A rename may have become visible before the writer could prove
            # both directory entries durable.  A read-only status retry may
            # establish that durability, but it must not report delivery from
            # the visible file alone.
            durability_flush_attempted = True
            project_update_transaction._require_directory_durable(
                consumed.parent
            )
            durability_flush_verified = True
    except (
        OSError,
        OperationControlError,
        project_update_transaction.ProjectUpdateTransactionError,
    ):
        return False, durability_flush_attempted, False
    return (
        bool(
            pending_matches or consumed_matches
        ),
        durability_flush_attempted,
        durability_flush_verified,
    )


def _apply_project_update_delivery_projection(
    artifact: dict[str, Any],
    *,
    control_root: Path,
    journal_delivery_acknowledged: bool,
    journal_handoff_sha256: str | None = None,
) -> bool:
    """Reconcile output with its operation-bound consumed ready capsule."""

    domain = artifact.get("domain")
    terminal = (
        domain.get("terminal_finalization")
        if type(domain) is dict
        else None
    )
    delivery = artifact.get("terminal_delivery")
    artifact["terminal_delivery_durability_flush_attempted"] = False
    artifact["terminal_delivery_durability_flush_verified"] = False
    if (
        type(journal_delivery_acknowledged) is not bool
        or type(domain) is not dict
        or type(terminal) is not dict
        or terminal.get("durable_result_delivery_acknowledged") is not False
        or artifact.get("command_result_available") is not True
        or artifact.get("result_ok") is not True
        or artifact.get("exit_code") != 0
        or type(delivery) is not dict
        or set(delivery)
        != {
            "schema",
            "terminal_handoff_sha256",
            "result_payload_sha256",
            "output_relative_sha256",
            "run_id",
            "operation_ref",
            "proof",
        }
        or delivery.get("schema")
        != "wom-kit/project-version-update-terminal-delivery-binding/v0.4.16"
        or delivery.get("result_payload_sha256")
        != artifact.get("result_payload_sha256")
        or delivery.get("output_relative_sha256")
        != artifact.get("output_relative_sha256")
        or delivery.get("run_id") != artifact.get("run_id")
        or delivery.get("operation_ref") != artifact.get("operation_ref")
        or (
            journal_handoff_sha256 is not None
            and delivery.get("terminal_handoff_sha256")
            != journal_handoff_sha256
        )
        or type(delivery.get("proof")) is not str
        or re.fullmatch(
            r"hmac-sha256:[0-9a-f]{64}",
            delivery["proof"],
        )
        is None
    ):
        return False
    (
        capsule_matches,
        durability_flush_attempted,
        durability_flush_verified,
    ) = _project_update_consumed_capsule_matches(
        control_root,
        delivery.get("terminal_handoff_sha256"),
    )
    artifact["terminal_delivery_durability_flush_attempted"] = (
        durability_flush_attempted
    )
    artifact["terminal_delivery_durability_flush_verified"] = (
        durability_flush_verified
    )
    if not capsule_matches:
        return False
    projected_terminal = dict(terminal)
    projected_terminal["durable_result_delivery_acknowledged"] = True
    projected_terminal["attention_required"] = not (
        projected_terminal.get("transaction_cleanup_completed") is True
        and projected_terminal.get("service_resource_close_verified")
        is True
        and projected_terminal.get("git_runner_close_verified") is True
    )
    projected_domain = dict(domain)
    projected_domain["terminal_finalization"] = projected_terminal
    projected_domain["post_update_attention_required"] = projected_terminal[
        "attention_required"
    ]
    artifact["domain"] = projected_domain
    artifact["terminal_delivery_consumed_verified"] = True
    artifact["terminal_delivery_journal_pending"] = (
        not journal_delivery_acknowledged
    )
    return True


def _safe_staged_cleanup_domain_projection(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Project only fixed staged-cleanup truth and bounded aggregate counts."""

    inspection_ok = payload.get("ok")
    safe_to_cleanup = payload.get("safe_to_cleanup")
    state = payload.get("state")
    raw_summary = payload.get("summary")
    raw_reason_codes = payload.get("reason_codes")
    if (
        type(inspection_ok) is not bool
        or type(safe_to_cleanup) is not bool
        or not isinstance(state, str)
        or state not in STAGED_CLEANUP_STATES
        or not isinstance(raw_summary, dict)
        or not isinstance(raw_reason_codes, list)
        or len(raw_reason_codes) > MAX_DOMAIN_BLOCKER_CODES
    ):
        return None

    summary: dict[str, int] = {}
    for key in STAGED_CLEANUP_SUMMARY_KEYS:
        value = raw_summary.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= MAX_STAGED_CLEANUP_SUMMARY_COUNT
        ):
            return None
        summary[key] = value
    if sum(summary.values()) > MAX_STAGED_CLEANUP_SUMMARY_COUNT:
        return None

    reason_codes: list[str] = []
    for value in raw_reason_codes:
        if not isinstance(value, str) or value not in STAGED_CLEANUP_REASON_CODES:
            return None
        if value not in reason_codes:
            reason_codes.append(value)

    expected_state = (
        "inspection_blocked"
        if not inspection_ok
        else "safe_to_cleanup"
        if safe_to_cleanup
        else "not_safe_to_cleanup"
    )
    if state != expected_state:
        return None
    if not inspection_ok and safe_to_cleanup:
        return None
    if state == "safe_to_cleanup" and (
        reason_codes
        or summary["deferred"]
        or summary["not_preserved"]
        or summary["unsafe"]
    ):
        return None
    if state == "not_safe_to_cleanup" and (
        not reason_codes
        or not (
            summary["deferred"]
            or summary["not_preserved"]
            or summary["unsafe"]
        )
    ):
        return None
    if state == "inspection_blocked" and not reason_codes:
        return None

    return {
        "command": "staged-cleanup-check",
        "inspection_ok": inspection_ok,
        "safe_to_cleanup": safe_to_cleanup,
        "state": state,
        "attention_required": not (inspection_ok and safe_to_cleanup),
        "summary": summary,
        "reason_codes": reason_codes,
        "local_paths_echoed": False,
        "object_ids_echoed": False,
        "private_values_echoed": False,
        "raw_messages_copied": False,
    }


def _find_result_artifact(
    root: Path,
    *,
    operation_ref: str,
    run_id: str,
    root_ref: str,
    output_ref: str,
    command: str,
    expected_sha256: str | None = None,
    expected_bytes: int | None = None,
    expected_exit_code: int | None = None,
    expected_result_ok: bool | None = None,
    _include_private: bool = False,
) -> dict[str, Any] | None:
    if type(_include_private) is not bool:
        raise OperationControlError("operation_result_verification_unsafe")
    scanned_entries = 0
    scanned_bytes = 0
    matches: list[dict[str, Any]] = []
    search_roots = (
        _path_below(root, PurePosixPath(ARCHIVE_OUTPUT_PREFIX.rstrip("/"))),
        _path_below(root, PurePosixPath(PROJECT_OUTPUT_PREFIX.rstrip("/"))),
    )
    for search_root in search_roots:
        try:
            observed_root = os.lstat(search_root)
        except FileNotFoundError:
            continue
        except OSError:
            raise OperationControlError(
                "operation_result_verification_unavailable"
            ) from None
        _validate_existing_chain(root, search_root)
        if (
            stat.S_ISLNK(observed_root.st_mode)
            or _is_reparse(observed_root)
            or not stat.S_ISDIR(observed_root.st_mode)
        ):
            raise OperationControlError("operation_result_verification_unsafe")
        stack = [search_root]
        while stack:
            directory = stack.pop()
            try:
                entries = os.scandir(directory)
            except OSError:
                raise OperationControlError(
                    "operation_result_verification_unavailable"
                ) from None
            with entries:
                for entry in entries:
                    scanned_entries += 1
                    if scanned_entries > MAX_RESULT_SCAN_ENTRIES:
                        raise OperationControlError(
                            "operation_result_verification_bounded"
                        )
                    try:
                        observed = entry.stat(follow_symlinks=False)
                    except OSError:
                        raise OperationControlError(
                            "operation_result_verification_unavailable"
                        ) from None
                    if stat.S_ISLNK(observed.st_mode) or _is_reparse(observed):
                        raise OperationControlError(
                            "operation_result_verification_unsafe"
                        )
                    candidate = Path(entry.path)
                    if stat.S_ISDIR(observed.st_mode):
                        if entry.name != ".operations":
                            stack.append(candidate)
                        continue
                    try:
                        candidate_relative = candidate.relative_to(root).as_posix()
                    except ValueError:
                        raise OperationControlError(
                            "operation_result_verification_unsafe"
                        ) from None
                    if (
                        not stat.S_ISREG(observed.st_mode)
                        or not entry.name.lower().endswith(".json")
                        or _output_ref(candidate_relative) != output_ref
                        or (
                            expected_bytes is not None
                            and observed.st_size != expected_bytes
                        )
                        or not 0 < observed.st_size <= MAX_RESULT_BYTES
                    ):
                        continue
                    scanned_bytes += int(observed.st_size)
                    if scanned_bytes > MAX_RESULT_SCAN_BYTES:
                        raise OperationControlError(
                            "operation_result_verification_bounded"
                        )
                    try:
                        digest, size, payload = _hash_result_artifact(root, candidate)
                    except OperationControlError as exc:
                        if exc.code in {
                            "operation_result_invalid",
                            "operation_result_unavailable",
                        }:
                            continue
                        raise
                    if expected_sha256 is not None and digest != expected_sha256:
                        continue
                    if expected_bytes is not None and size != expected_bytes:
                        continue
                    validated = _validated_result_payload(
                        payload,
                        operation_ref=operation_ref,
                        run_id=run_id,
                        root_ref=root_ref,
                        output_ref=output_ref,
                        command=command,
                    )
                    if validated is None:
                        continue
                    (
                        exit_code,
                        result_ok,
                        command_result_available,
                    ) = validated
                    if (
                        expected_exit_code is not None
                        and exit_code != expected_exit_code
                    ) or (
                        expected_result_ok is not None
                        and result_ok is not expected_result_ok
                    ):
                        continue
                    match: dict[str, Any] = {
                            "sha256": digest,
                            "bytes": size,
                            "result_payload_sha256": (
                                _canonical_document_sha256(
                                    {
                                        key: value
                                        for key, value in payload.items()
                                        if key
                                        not in {
                                            "cli_execution",
                                            "cli_output_artifact",
                                        }
                                    }
                                )
                            ),
                            "output_relative_sha256": (
                                "sha256:"
                                + hashlib.sha256(
                                    candidate_relative.encode("utf-8")
                                ).hexdigest()
                            ),
                            "run_id": run_id,
                            "operation_ref": operation_ref,
                            "exit_code": exit_code,
                            "result_ok": result_ok,
                            "command_result_available": (
                                command_result_available
                            ),
                            "terminal_delivery": (
                                payload.get("cli_execution", {}).get(
                                    "terminal_delivery"
                                )
                                if type(payload.get("cli_execution"))
                                is dict
                                else None
                            ),
                            "domain": (
                                _safe_domain_projection(
                                    payload,
                                    command=command,
                                )
                                if command_result_available
                                else None
                            ),
                        }
                    if _include_private:
                        match["_private_output_path"] = candidate
                        match["_private_payload"] = payload
                    matches.append(match)
                    if len(matches) > 1:
                        raise OperationControlError(
                            "operation_result_artifact_ambiguous"
                        )
    return matches[0] if matches else None


@dataclass(frozen=True, repr=False)
class ProjectUpdatePendingTerminalDelivery:
    """Private structural candidate; claim reauthentication is still required."""

    control_root: Path = field(repr=False)
    journal_path: Path = field(repr=False)
    output_path: Path = field(repr=False)
    consumed_path: Path = field(repr=False)
    result_document: dict[str, Any] = field(repr=False)
    capsule_bytes: bytes = field(repr=False)
    operation_ref: str = field(repr=False)
    run_id: str = field(repr=False)
    root_ref: str = field(repr=False)
    output_ref: str = field(repr=False)
    result_sha256: str = field(repr=False)
    result_bytes: int = field(repr=False)
    terminal_handoff_sha256: str = field(repr=False)
    active_handoff: bool = field(default=False, repr=False)
    display_pending: bool = field(default=False, repr=False)


@dataclass
class OperationRunJournal:
    control_root: Path
    journal_path: Path
    command: str
    operation_kind: str
    operation_ref: str
    root_ref: str
    output_ref: str
    run_id: str
    owner_ref: str
    control_digest: str
    started_monotonic: float
    _identity: tuple[int, int]
    _sequence: int = 0
    _previous_digest: str | None = None
    _stage: str = "starting"
    _last_completed_stage: str | None = None
    _failed: bool = False
    _terminal: bool = False

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @classmethod
    def prepare(
        cls,
        control_root: Path | str,
        *,
        output_relative: str,
        command: str,
        run_id: str,
    ) -> "OperationRunJournal":
        root = require_control_root(control_root)
        if command not in COMMAND_KINDS or RUN_ID_RE.fullmatch(run_id) is None:
            raise OperationControlError("operation_journal_input_invalid")
        journal_relative = _journal_relative_for_output(output_relative)
        journal_root = _ensure_real_directory_chain(root, journal_relative)
        root_ref = _root_ref(root)
        output_ref = _output_ref(output_relative)
        operation_ref = _operation_ref(
            command,
            run_id,
            output_ref,
            root_ref,
        )
        operation_hex = _operation_hex(operation_ref)
        journal_path = journal_root / f"{operation_hex}.jsonl"
        owner_ref = _opaque_digest("owner", operation_ref, run_id)
        control_digest = _opaque_digest("control", operation_ref, run_id).replace(
            "control:sha256:", "sha256:"
        )
        try:
            descriptor = os.open(
                str(journal_path),
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_BINARY", 0),
                0o600,
            )
        except FileExistsError:
            raise OperationControlError("operation_journal_already_exists") from None
        except OSError:
            raise OperationControlError("operation_journal_create_failed") from None
        try:
            observed = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
            raise OperationControlError("operation_journal_create_failed")
        journal = cls(
            control_root=root,
            journal_path=journal_path,
            command=command,
            operation_kind=COMMAND_KINDS[command],
            operation_ref=operation_ref,
            root_ref=root_ref,
            output_ref=output_ref,
            run_id=run_id,
            owner_ref=owner_ref,
            control_digest=control_digest,
            started_monotonic=time.monotonic(),
            _identity=(int(observed.st_dev), int(observed.st_ino)),
        )
        journal._append("started", terminal=False)
        if journal._failed:
            raise OperationControlError("operation_journal_start_failed")
        journal._thread = threading.Thread(
            target=journal._heartbeat_loop,
            name=f"wom-operation-{command}",
            daemon=True,
        )
        journal._thread.start()
        return journal

    @property
    def tracking_ok(self) -> bool:
        return not self._failed

    def metadata(self) -> dict[str, Any]:
        return {
            "operation_ref": self.operation_ref,
            "operation_kind": self.operation_kind,
            "root_ref": self.root_ref,
            "output_ref": self.output_ref,
            "control_digest": self.control_digest,
            "status_command": (
                "archive operation-control <project-or-archive-root> "
                f"--operation-ref {self.operation_ref} --action status "
                "--dry-run --format json"
            ),
            "wait_command": (
                "archive operation-control <project-or-archive-root> "
                f"--operation-ref {self.operation_ref} --action wait "
                "--timeout-seconds 60 --dry-run --format json"
            ),
            "cancel_supported": False,
            "resume_supported": False,
        }

    def _safe_stage(self, stage: object) -> str:
        value = str(stage or "").strip().lower()
        return value if value in COMMAND_STAGES[self.command] else "unknown"

    def _record(
        self,
        event: str,
        *,
        terminal: bool,
        result_available: bool = False,
        result_ok: bool | None = None,
        exit_code: int | None = None,
        result_sha256: str | None = None,
        result_bytes: int | None = None,
        terminal_delivery_acknowledged: bool | None = None,
        terminal_handoff_sha256: str | None = None,
        recovery_required: bool = False,
    ) -> dict[str, Any]:
        record = {
            "schema": OPERATION_JOURNAL_SCHEMA,
            "operation_ref": self.operation_ref,
            "operation_kind": self.operation_kind,
            "root_ref": self.root_ref,
            "output_ref": self.output_ref,
            "run_id": self.run_id,
            "owner_ref": self.owner_ref,
            "control_digest": self.control_digest,
            "sequence": self._sequence,
            "event": event,
            "stage": self._stage,
            "observed_at": _utc_now(),
            "elapsed_ms": max(
                0, int((time.monotonic() - self.started_monotonic) * 1000)
            ),
            "last_completed_stage": self._last_completed_stage,
            "terminal": terminal,
            "result_available": result_available,
            "result_ok": result_ok,
            "exit_code": exit_code,
            "result_sha256": result_sha256,
            "result_bytes": result_bytes,
            "terminal_delivery_acknowledged": (
                terminal_delivery_acknowledged
            ),
            "terminal_handoff_sha256": terminal_handoff_sha256,
            "recovery_required": recovery_required,
            "previous_record_sha256": self._previous_digest,
            "record_sha256": None,
        }
        record["record_sha256"] = _record_digest(record)
        return record

    def _append(
        self,
        event: str,
        *,
        terminal: bool,
        result_available: bool = False,
        result_ok: bool | None = None,
        exit_code: int | None = None,
        result_sha256: str | None = None,
        result_bytes: int | None = None,
        terminal_delivery_acknowledged: bool | None = None,
        terminal_handoff_sha256: str | None = None,
        recovery_required: bool = False,
    ) -> None:
        if (
            self._failed
            or event not in JOURNAL_EVENTS
            or self._terminal
        ):
            return
        record = self._record(
            event,
            terminal=terminal,
            result_available=result_available,
            result_ok=result_ok,
            exit_code=exit_code,
            result_sha256=result_sha256,
            result_bytes=result_bytes,
            terminal_delivery_acknowledged=(
                terminal_delivery_acknowledged
            ),
            terminal_handoff_sha256=terminal_handoff_sha256,
            recovery_required=recovery_required,
        )
        encoded = (
            json.dumps(
                record,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
        if len(encoded) > MAX_JOURNAL_LINE_BYTES:
            self._failed = True
            return
        try:
            _validate_existing_chain(self.control_root, self.journal_path)
            before = os.lstat(self.journal_path)
            if (
                stat.S_ISLNK(before.st_mode)
                or _is_reparse(before)
                or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or (int(before.st_dev), int(before.st_ino)) != self._identity
                or before.st_size + len(encoded) > MAX_JOURNAL_BYTES
            ):
                raise OSError("operation_journal_identity_changed")
            descriptor = os.open(
                str(self.journal_path),
                os.O_WRONLY | os.O_APPEND | getattr(os, "O_BINARY", 0),
            )
            try:
                current = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(current.st_mode)
                    or current.st_nlink != 1
                    or (int(current.st_dev), int(current.st_ino))
                    != self._identity
                ):
                    raise OSError("operation_journal_identity_changed")
                written = 0
                try:
                    while written < len(encoded):
                        count = os.write(descriptor, encoded[written:])
                        if count <= 0:
                            raise OSError(
                                "operation_journal_append_incomplete"
                            )
                        written += count
                    os.fsync(descriptor)
                except OSError:
                    # Restore the exact verified prefix before reporting a
                    # failed append. This journal has one in-process writer;
                    # leaving a torn JSON tail would make every future read
                    # permanently ambiguous.
                    try:
                        os.ftruncate(descriptor, before.st_size)
                        os.fsync(descriptor)
                    except OSError:
                        pass
                    raise
            finally:
                os.close(descriptor)
            if terminal or event == "started":
                project_update_transaction._require_directory_durable(
                    self.journal_path.parent
                )
        except (
            OSError,
            OperationControlError,
            project_update_transaction.ProjectUpdateTransactionError,
        ):
            self._failed = True
            return
        self._previous_digest = str(record["record_sha256"])
        self._sequence += 1
        self._terminal = terminal

    def progress(
        self,
        stage: str,
        message: str,
        _current: int | None,
        _total: int | None,
    ) -> None:
        safe_stage = self._safe_stage(stage)
        normalized_message = str(message or "").strip().lower()
        checkpoint = normalized_message == "start" or normalized_message.startswith(
            "start "
        )
        completed = normalized_message == "done" or normalized_message.startswith(
            "done "
        )
        with self._lock:
            stage_changed = safe_stage != self._stage
            self._stage = safe_stage
            if completed and safe_stage != "unknown":
                self._last_completed_stage = safe_stage
            if stage_changed or checkpoint or completed:
                self._append("checkpoint", terminal=False)

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(HEARTBEAT_INTERVAL_SECONDS):
            with self._lock:
                self._append("heartbeat", terminal=False)

    def complete(
        self,
        *,
        exit_code: int,
        result_available: bool,
        result_ok: bool | None,
        result_path: Path | None = None,
        terminal_delivery_acknowledged: bool | None = None,
        terminal_handoff_sha256: str | None = None,
    ) -> bool:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        result_sha256: str | None = None
        result_bytes: int | None = None
        if (
            terminal_delivery_acknowledged is not None
            and type(terminal_delivery_acknowledged) is not bool
        ):
            self._failed = True
            return False
        if (
            terminal_handoff_sha256 is not None
            and (
                not isinstance(terminal_handoff_sha256, str)
                or re.fullmatch(
                    r"sha256:[0-9a-f]{64}", terminal_handoff_sha256
                )
                is None
            )
        ):
            self._failed = True
            return False
        if (
            self.command == "project-version-update"
            and terminal_delivery_acknowledged is True
        ):
            # The terminal journal is committed before the ready capsule is
            # moved. Delivery can only become true later by verifying that
            # exact operation-bound consumed capsule.
            self._failed = True
            return False
        terminal_delivery_state = (
            terminal_delivery_acknowledged
            if self.command == "project-version-update"
            else None
        )
        terminal_handoff_state = (
            terminal_handoff_sha256
            if self.command == "project-version-update"
            else None
        )
        if (
            self.command != "project-version-update"
            and terminal_handoff_sha256 is not None
            or self.command == "project-version-update"
            and (
                terminal_delivery_state is False
                and terminal_handoff_state is None
                or terminal_delivery_state is None
                and terminal_handoff_state is not None
            )
        ):
            self._failed = True
            return False
        if result_available:
            try:
                if result_path is None:
                    raise OperationControlError("operation_result_unavailable")
                result_sha256, result_bytes, payload = _hash_result_artifact(
                    self.control_root,
                    result_path,
                )
                validated = _validated_result_payload(
                    payload,
                    operation_ref=self.operation_ref,
                    run_id=self.run_id,
                    root_ref=self.root_ref,
                    output_ref=self.output_ref,
                    command=self.command,
                )
                if (
                    validated is None
                    or validated[:2] != (int(exit_code), result_ok)
                ):
                    raise OperationControlError("operation_result_binding_invalid")
                if validated[2] is not True:
                    # A CLI failure artifact can be durably bound to this run,
                    # but it is not the command's domain result. Preserve the
                    # terminal recovery record while returning an incomplete
                    # completion signal to the caller.
                    result_available = False
                    result_ok = None
                if self.command == "project-version-update":
                    execution = payload.get("cli_execution")
                    delivery = (
                        execution.get("terminal_delivery")
                        if type(execution) is dict
                        else None
                    )
                    if terminal_delivery_state is False:
                        if (
                            type(delivery) is not dict
                            or set(delivery)
                            != {
                                "schema",
                                "terminal_handoff_sha256",
                                "result_payload_sha256",
                                "output_relative_sha256",
                                "run_id",
                                "operation_ref",
                                "proof",
                            }
                            or delivery.get("schema")
                            != "wom-kit/project-version-update-terminal-delivery-binding/v0.4.16"
                            or delivery.get("terminal_handoff_sha256")
                            != terminal_handoff_state
                            or re.fullmatch(
                                r"hmac-sha256:[0-9a-f]{64}",
                                str(delivery.get("proof") or ""),
                            )
                            is None
                        ):
                            raise OperationControlError(
                                "operation_result_binding_invalid"
                            )
                    elif delivery is not None:
                        raise OperationControlError(
                            "operation_result_binding_invalid"
                        )
            except OperationControlError:
                if (
                    self.command == "project-version-update"
                    and terminal_delivery_state is False
                ):
                    self._failed = True
                    return False
                result_available = False
                result_ok = None
        if not self._lock.acquire(timeout=2.0):
            self._failed = True
            return False
        try:
            self._append(
                "completed" if result_available else "result_unavailable",
                terminal=True,
                result_available=result_available,
                result_ok=result_ok if result_available else None,
                exit_code=int(exit_code) if result_available else None,
                result_sha256=result_sha256 if result_available else None,
                result_bytes=result_bytes if result_available else None,
                terminal_delivery_acknowledged=(
                    terminal_delivery_state
                ),
                terminal_handoff_sha256=terminal_handoff_state,
                recovery_required=not result_available,
            )
        finally:
            self._lock.release()
        return bool(not self._failed and self._terminal and result_available)

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise OperationControlError("operation_journal_invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise OperationControlError("operation_journal_invalid") from None
    if parsed.tzinfo is None:
        raise OperationControlError("operation_journal_invalid")
    return parsed.astimezone(timezone.utc)


def _read_journal(path: Path, root: Path) -> list[dict[str, Any]]:
    _validate_existing_chain(root, path)
    try:
        observed = os.lstat(path)
    except OSError:
        raise OperationControlError("operation_journal_unavailable") from None
    if (
        stat.S_ISLNK(observed.st_mode)
        or _is_reparse(observed)
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_nlink != 1
        or not 0 < observed.st_size <= MAX_JOURNAL_BYTES
    ):
        raise OperationControlError("operation_journal_invalid")
    chunks: list[bytes] = []
    total = 0
    try:
        descriptor = os.open(
            str(path), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
        try:
            current = os.fstat(descriptor)
            identity = (int(observed.st_dev), int(observed.st_ino))
            if (
                not stat.S_ISREG(current.st_mode)
                or current.st_nlink != 1
                or (int(current.st_dev), int(current.st_ino)) != identity
                or not observed.st_size <= current.st_size <= MAX_JOURNAL_BYTES
            ):
                raise OSError("operation_journal_identity_changed")
            # Read the complete prefix observed by the initial lstat.  A
            # concurrent append may make the open file larger, but must not
            # invalidate the already fsynced newline-delimited prefix.
            remaining = int(observed.st_size)
            while remaining:
                chunk = os.read(descriptor, min(64 * 1024, remaining))
                if not chunk:
                    raise OSError("operation_journal_read_incomplete")
                total += len(chunk)
                remaining -= len(chunk)
                if total > MAX_JOURNAL_BYTES:
                    raise OSError("operation_journal_too_large")
                chunks.append(chunk)
            final = os.fstat(descriptor)
            if (
                (int(final.st_dev), int(final.st_ino)) != identity
                or not observed.st_size <= final.st_size <= MAX_JOURNAL_BYTES
                or total != observed.st_size
            ):
                raise OSError("operation_journal_identity_changed")
        finally:
            os.close(descriptor)
    except OSError:
        raise OperationControlError("operation_journal_unavailable") from None
    raw = b"".join(chunks)
    if not raw.endswith(b"\n"):
        raise OperationControlError("operation_journal_torn")
    lines = raw.splitlines()
    if not 0 < len(lines) <= MAX_JOURNAL_RECORDS:
        raise OperationControlError("operation_journal_invalid")
    records: list[dict[str, Any]] = []
    previous_digest: str | None = None
    fixed: tuple[str, str, str, str, str, str, str] | None = None
    journal_schema: str | None = None
    journal_record_keys: tuple[str, ...] | None = None
    terminal_seen = False
    previous_record: dict[str, Any] | None = None
    previous_elapsed = -1
    previous_timestamp: datetime | None = None
    for sequence, line in enumerate(lines):
        if not line or len(line) > MAX_JOURNAL_LINE_BYTES:
            raise OperationControlError("operation_journal_invalid")
        try:
            decoded = line.decode("ascii")
            record = json.loads(decoded)
        except (UnicodeError, json.JSONDecodeError):
            raise OperationControlError("operation_journal_invalid") from None
        if not isinstance(record, dict):
            raise OperationControlError("operation_journal_invalid")
        record_schema = record.get("schema")
        expected_record_keys = (
            RECORD_KEYS
            if record_schema == OPERATION_JOURNAL_SCHEMA
            else LEGACY_RECORD_KEYS
            if record_schema == LEGACY_OPERATION_JOURNAL_SCHEMA
            else ()
        )
        if tuple(record) != tuple(sorted(expected_record_keys)):
            # Writers sort keys on disk; requiring that order also rejects an
            # unexpected field before any untrusted value is reflected.
            raise OperationControlError("operation_journal_invalid")
        if set(record) != set(expected_record_keys):
            raise OperationControlError("operation_journal_invalid")
        digest_record = record
        legacy_record = record_schema == LEGACY_OPERATION_JOURNAL_SCHEMA
        handoff_bound_record = not legacy_record
        if legacy_record:
            record = {
                **record,
                "terminal_delivery_acknowledged": None,
                "terminal_handoff_sha256": None,
            }
        operation_ref = record.get("operation_ref")
        operation_kind = record.get("operation_kind")
        root_ref = record.get("root_ref")
        output_ref = record.get("output_ref")
        run_id = record.get("run_id")
        owner_ref = record.get("owner_ref")
        control_digest = record.get("control_digest")
        current_fixed = (
            str(operation_ref),
            str(operation_kind),
            str(root_ref),
            str(output_ref),
            str(run_id),
            str(owner_ref),
            str(control_digest),
        )
        if fixed is None:
            fixed = current_fixed
            journal_schema = str(record_schema)
            journal_record_keys = expected_record_keys
        if (
            current_fixed != fixed
            or record_schema != journal_schema
            or expected_record_keys != journal_record_keys
            or OPERATION_REF_RE.fullmatch(str(operation_ref or "")) is None
            or operation_kind not in KIND_COMMANDS
            or not re.fullmatch(r"root:sha256:[0-9a-f]{64}", str(root_ref or ""))
            or not re.fullmatch(
                r"output:sha256:[0-9a-f]{64}", str(output_ref or "")
            )
            or operation_ref
            != _operation_ref(
                KIND_COMMANDS[str(operation_kind)],
                str(run_id),
                str(output_ref),
                str(root_ref),
            )
            or RUN_ID_RE.fullmatch(str(run_id or "")) is None
            or not re.fullmatch(r"owner:sha256:[0-9a-f]{64}", str(owner_ref or ""))
            or CONTROL_DIGEST_RE.fullmatch(str(control_digest or "")) is None
            or owner_ref
            != _opaque_digest("owner", str(operation_ref), str(run_id))
            or control_digest
            != _opaque_digest(
                "control", str(operation_ref), str(run_id)
            ).replace("control:sha256:", "sha256:")
            or record.get("sequence") != sequence
            or record.get("event") not in JOURNAL_EVENTS
            or record.get("stage")
            not in COMMAND_STAGES[KIND_COMMANDS[str(operation_kind)]]
            or not isinstance(record.get("elapsed_ms"), int)
            or isinstance(record.get("elapsed_ms"), bool)
            or record["elapsed_ms"] < 0
            or record.get("last_completed_stage")
            not in {None, *COMMAND_STAGES[KIND_COMMANDS[str(operation_kind)]]}
            or type(record.get("terminal")) is not bool
            or type(record.get("result_available")) is not bool
            or (
                record.get("result_ok") is not None
                and type(record.get("result_ok")) is not bool
            )
            or (
                record.get("exit_code") is not None
                and (
                    not isinstance(record.get("exit_code"), int)
                    or isinstance(record.get("exit_code"), bool)
                    or not 0 <= record["exit_code"] <= 255
                )
            )
            or (
                record.get("result_sha256") is not None
                and not re.fullmatch(
                    r"sha256:[0-9a-f]{64}",
                    str(record.get("result_sha256")),
                )
            )
            or (
                record.get("result_bytes") is not None
                and (
                    not isinstance(record.get("result_bytes"), int)
                    or isinstance(record.get("result_bytes"), bool)
                    or not 0 < record["result_bytes"] <= MAX_RESULT_BYTES
                )
            )
            or (
                record.get("terminal_delivery_acknowledged") is not None
                and type(
                    record.get("terminal_delivery_acknowledged")
                )
                is not bool
            )
            or (
                record.get("terminal_handoff_sha256") is not None
                and re.fullmatch(
                    r"sha256:[0-9a-f]{64}",
                    str(record.get("terminal_handoff_sha256")),
                )
                is None
            )
            or type(record.get("recovery_required")) is not bool
            or record.get("previous_record_sha256") != previous_digest
            or record.get("record_sha256")
            != _record_digest(digest_record)
        ):
            raise OperationControlError("operation_journal_invalid")
        observed_at = _parse_timestamp(record.get("observed_at"))
        if (
            record["elapsed_ms"] < previous_elapsed
            or (previous_timestamp is not None and observed_at < previous_timestamp)
        ):
            raise OperationControlError("operation_journal_invalid")
        previous_elapsed = record["elapsed_ms"]
        previous_timestamp = observed_at
        event = record["event"]
        if terminal_seen:
            raise OperationControlError("operation_journal_invalid")
        if event == "started" and sequence != 0:
            raise OperationControlError("operation_journal_invalid")
        if (
            event
            in {
                "completed",
                "result_unavailable",
            }
        ) != bool(record["terminal"]):
            raise OperationControlError("operation_journal_invalid")
        if record["terminal"]:
            terminal_seen = True
            if event not in {"completed", "result_unavailable"}:
                raise OperationControlError("operation_journal_invalid")
        elif (
            record["result_available"]
            or record["result_ok"] is not None
            or record["exit_code"] is not None
            or record["recovery_required"]
            or record["result_sha256"] is not None
            or record["result_bytes"] is not None
            or record["terminal_delivery_acknowledged"] is not None
            or record["terminal_handoff_sha256"] is not None
        ):
            raise OperationControlError("operation_journal_invalid")
        if event == "completed" and (
            not record["result_available"]
            or record["result_ok"] is None
            or record["exit_code"] is None
            or record["result_sha256"] is None
            or record["result_bytes"] is None
            or record["recovery_required"]
            or (
                operation_kind == "project_version_update"
                and not (
                    legacy_record
                    and record["terminal_delivery_acknowledged"] is None
                    or not legacy_record
                    and record["terminal_delivery_acknowledged"]
                    in {None, False}
                )
            )
            or (
                operation_kind != "project_version_update"
                and record["terminal_delivery_acknowledged"] is not None
            )
            or (
                operation_kind == "project_version_update"
                and handoff_bound_record
                and (
                    record["terminal_delivery_acknowledged"] is False
                )
                != (record["terminal_handoff_sha256"] is not None)
            )
            or (
                operation_kind != "project_version_update"
                and record["terminal_handoff_sha256"] is not None
            )
        ):
            raise OperationControlError("operation_journal_invalid")
        if event == "result_unavailable" and (
            record["result_available"]
            or record["result_ok"] is not None
            or record["exit_code"] is not None
            or record["result_sha256"] is not None
            or record["result_bytes"] is not None
            or record["terminal_handoff_sha256"] is not None
            or (
                operation_kind == "project_version_update"
                and not (
                    legacy_record
                    and record["terminal_delivery_acknowledged"] is None
                    or not legacy_record
                    and record["terminal_delivery_acknowledged"]
                    in {None, False}
                )
            )
            or (
                operation_kind != "project_version_update"
                and record["terminal_delivery_acknowledged"] is not None
            )
            or not record["recovery_required"]
        ):
            raise OperationControlError("operation_journal_invalid")
        previous_digest = str(record["record_sha256"])
        previous_record = record
        records.append(record)
    if records[0]["event"] != "started":
        raise OperationControlError("operation_journal_invalid")
    return records


def _bounded_operation_journal_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    observed_entries = 0
    observed_bytes = 0
    for relative in (ARCHIVE_JOURNAL_RELATIVE, PROJECT_JOURNAL_RELATIVE):
        journal_root = _path_below(root, relative)
        try:
            observed_root = os.lstat(journal_root)
        except FileNotFoundError:
            continue
        except OSError:
            raise OperationControlError(
                "operation_terminal_delivery_scan_unavailable"
            ) from None
        _validate_existing_chain(root, journal_root)
        if (
            stat.S_ISLNK(observed_root.st_mode)
            or _is_reparse(observed_root)
            or not stat.S_ISDIR(observed_root.st_mode)
        ):
            raise OperationControlError("operation_terminal_delivery_scan_unsafe")
        try:
            entries = os.scandir(journal_root)
        except OSError:
            raise OperationControlError(
                "operation_terminal_delivery_scan_unavailable"
            ) from None
        with entries:
            for entry in entries:
                observed_entries += 1
                if observed_entries > MAX_RESULT_SCAN_ENTRIES:
                    raise OperationControlError(
                        "operation_terminal_delivery_scan_bounded"
                    )
                try:
                    observed = entry.stat(follow_symlinks=False)
                except OSError:
                    raise OperationControlError(
                        "operation_terminal_delivery_scan_unavailable"
                    ) from None
                if (
                    stat.S_ISLNK(observed.st_mode)
                    or _is_reparse(observed)
                    or not stat.S_ISREG(observed.st_mode)
                    or re.fullmatch(r"[0-9a-f]{64}\.jsonl", entry.name)
                    is None
                ):
                    raise OperationControlError(
                        "operation_terminal_delivery_scan_unsafe"
                    )
                observed_bytes += int(observed.st_size)
                if observed_bytes > MAX_RESULT_SCAN_BYTES:
                    raise OperationControlError(
                        "operation_terminal_delivery_scan_bounded"
                    )
                paths.append(Path(entry.path))
    return paths


def _pending_project_update_delivery_records(
    root: Path,
) -> list[tuple[Path, list[dict[str, Any]]]]:
    pending: list[tuple[Path, list[dict[str, Any]]]] = []
    expected_root_ref = _root_ref(root)
    for journal_path in _bounded_operation_journal_paths(root):
        records = _read_journal(journal_path, root)
        first = records[0]
        latest = records[-1]
        if (
            first["root_ref"] != expected_root_ref
            or journal_path.name
            != _operation_hex(str(first["operation_ref"])) + ".jsonl"
            or (
                _parse_timestamp(latest["observed_at"])
                - datetime.now(timezone.utc)
            ).total_seconds()
            > MAX_FUTURE_SKEW_SECONDS
        ):
            raise OperationControlError("operation_terminal_delivery_invalid")
        if first["operation_kind"] != "project_version_update":
            continue
        if (
            latest["event"] == "completed"
            and latest["terminal"] is True
            and latest["result_available"] is True
            and latest["result_ok"] is True
            and latest["exit_code"] == 0
            and latest["recovery_required"] is False
            and latest["terminal_delivery_acknowledged"] is False
        ):
            pending.append((journal_path, records))
    return pending


def _project_update_delivery_candidate(
    root: Path,
    journal_path: Path,
    records: list[dict[str, Any]],
    *,
    allow_active_handoff: bool = False,
    allow_display_pending: bool = False,
) -> ProjectUpdatePendingTerminalDelivery:
    latest = records[-1]
    try:
        active = _path_below(
            root,
            PurePosixPath(PROJECT_UPDATE_TERMINAL_ACTIVE_RELATIVE),
        )
        display_pending_path = _path_below(
            root,
            PurePosixPath(
                PROJECT_UPDATE_TERMINAL_DISPLAY_PENDING_RELATIVE
            ),
        )
        active_sha256 = _project_update_private_file_sha256(root, active)
        display_pending_sha256 = _project_update_private_file_sha256(
            root,
            display_pending_path,
        )
        if active_sha256 is not None and display_pending_sha256 is not None:
            raise OperationControlError("operation_terminal_delivery_invalid")
        artifact = _find_result_artifact(
            root,
            operation_ref=str(latest["operation_ref"]),
            run_id=str(latest["run_id"]),
            root_ref=str(latest["root_ref"]),
            output_ref=str(latest["output_ref"]),
            command="project-version-update",
            expected_sha256=str(latest["result_sha256"]),
            expected_bytes=int(latest["result_bytes"]),
            expected_exit_code=0,
            expected_result_ok=True,
            _include_private=True,
        )
    except OperationControlError:
        raise OperationControlError("operation_terminal_delivery_invalid") from None
    if artifact is None:
        raise OperationControlError("operation_terminal_delivery_invalid")
    domain = artifact.get("domain")
    terminal = (
        domain.get("terminal_finalization")
        if type(domain) is dict
        else None
    )
    delivery = artifact.get("terminal_delivery")
    if (
        type(terminal) is not dict
        or terminal.get("transaction_cleanup_completed") is not True
        or terminal.get("durable_terminal_handoff_ready") is not True
        or terminal.get("durable_result_delivery_acknowledged") is not False
        or artifact.get("command_result_available") is not True
        or type(delivery) is not dict
    ):
        raise OperationControlError("operation_terminal_delivery_invalid")
    handoff_sha256 = delivery.get("terminal_handoff_sha256")
    if not isinstance(handoff_sha256, str) or re.fullmatch(
        r"sha256:[0-9a-f]{64}", handoff_sha256
    ) is None:
        raise OperationControlError("operation_terminal_delivery_invalid")
    journal_handoff_sha256 = latest.get("terminal_handoff_sha256")
    if (
        journal_handoff_sha256 is not None
        and not hmac.compare_digest(
            str(journal_handoff_sha256), handoff_sha256
        )
    ):
        raise OperationControlError("operation_terminal_delivery_invalid")
    selected_active = bool(
        active_sha256 is not None
        and hmac.compare_digest(active_sha256, handoff_sha256)
    )
    selected_display_pending = bool(
        display_pending_sha256 is not None
        and hmac.compare_digest(display_pending_sha256, handoff_sha256)
    )
    if selected_active:
        if not allow_active_handoff:
            raise OperationControlError("operation_terminal_delivery_invalid")
        capsule_path = active
    elif selected_display_pending:
        if not allow_display_pending:
            raise OperationControlError("operation_terminal_delivery_invalid")
        expected_consumed = _path_below(
            root,
            PurePosixPath(
                PROJECT_UPDATE_TERMINAL_CONSUMED_PREFIX
                + handoff_sha256.removeprefix("sha256:")
                + ".json"
            ),
        )
        if (
            _project_update_private_file_sha256(
                root,
                expected_consumed,
            )
            is not None
        ):
            raise OperationControlError("operation_terminal_delivery_invalid")
        try:
            project_update_transaction._require_directory_durable(
                display_pending_path.parent
            )
        except (
            OSError,
            project_update_transaction.ProjectUpdateTransactionError,
        ):
            raise OperationControlError(
                "operation_terminal_delivery_durability_unverified"
            ) from None
        capsule_path = display_pending_path
    else:
        if not _apply_project_update_delivery_projection(
            artifact,
            control_root=root,
            journal_delivery_acknowledged=False,
            journal_handoff_sha256=journal_handoff_sha256,
        ):
            raise OperationControlError("operation_terminal_delivery_invalid")
        capsule_path = _path_below(
            root,
            PurePosixPath(
                PROJECT_UPDATE_TERMINAL_CONSUMED_PREFIX
                + handoff_sha256.removeprefix("sha256:")
                + ".json"
            ),
        )
    capsule_bytes = _project_update_private_file_bytes(
        root,
        capsule_path,
        expected_sha256=handoff_sha256,
    )
    output_path = artifact.get("_private_output_path")
    result_document = artifact.get("_private_payload")
    if not isinstance(output_path, Path) or type(result_document) is not dict:
        raise OperationControlError("operation_terminal_delivery_invalid")
    return ProjectUpdatePendingTerminalDelivery(
        control_root=root,
        journal_path=journal_path,
        output_path=output_path,
        consumed_path=capsule_path,
        result_document=result_document,
        capsule_bytes=capsule_bytes,
        operation_ref=str(latest["operation_ref"]),
        run_id=str(latest["run_id"]),
        root_ref=str(latest["root_ref"]),
        output_ref=str(latest["output_ref"]),
        result_sha256=str(latest["result_sha256"]),
        result_bytes=int(latest["result_bytes"]),
        terminal_handoff_sha256=handoff_sha256,
        active_handoff=selected_active,
        display_pending=selected_display_pending,
    )


def discover_pending_project_update_terminal_delivery(
    control_root: Path | str,
    *,
    allow_active_handoff: bool = False,
) -> ProjectUpdatePendingTerminalDelivery | None:
    """Return the sole exact pending terminal delivery without exposing IDs."""

    root = require_control_root(control_root)
    active = _path_below(
        root,
        PurePosixPath(PROJECT_UPDATE_TERMINAL_ACTIVE_RELATIVE),
    )
    display_pending = _path_below(
        root,
        PurePosixPath(PROJECT_UPDATE_TERMINAL_DISPLAY_PENDING_RELATIVE),
    )
    active_present = _project_update_private_file_sha256(root, active) is not None
    display_pending_present = (
        _project_update_private_file_sha256(root, display_pending) is not None
    )
    if active_present and display_pending_present:
        raise OperationControlError("operation_terminal_delivery_ambiguous")
    if not active_present and not display_pending_present:
        try:
            terminal_root_stat = os.lstat(active.parent)
        except FileNotFoundError:
            terminal_root_stat = None
        except OSError:
            raise OperationControlError(
                "operation_terminal_delivery_scan_unavailable"
            ) from None
        if terminal_root_stat is not None:
            if (
                stat.S_ISLNK(terminal_root_stat.st_mode)
                or _is_reparse(terminal_root_stat)
                or not stat.S_ISDIR(terminal_root_stat.st_mode)
            ):
                raise OperationControlError(
                    "operation_terminal_delivery_scan_unsafe"
                )
            try:
                project_update_transaction._require_directory_durable(
                    active.parent
                )
            except (
                OSError,
                project_update_transaction.ProjectUpdateTransactionError,
            ):
                raise OperationControlError(
                    "operation_terminal_delivery_durability_unverified"
                ) from None
        # A final pending->consumed rename may be visible before its parent
        # directory flush was verified. The namespace flush above closes that
        # uncertainty. Hashed consumed capsules are history, not replay
        # candidates, and disposable historical outputs are not required for a
        # future update preflight.
        return None
    if active_present and not allow_active_handoff:
        return None

    def matching_candidates() -> list[ProjectUpdatePendingTerminalDelivery]:
        matches: list[ProjectUpdatePendingTerminalDelivery] = []
        current_handoff_sha256 = (
            _project_update_private_file_sha256(root, active)
            if active_present
            else _project_update_private_file_sha256(root, display_pending)
        )
        if current_handoff_sha256 is None:
            raise OperationControlError("operation_terminal_delivery_changed")
        for journal_path, records in _pending_project_update_delivery_records(
            root
        ):
            if not hmac.compare_digest(
                str(records[-1].get("terminal_handoff_sha256") or ""),
                current_handoff_sha256,
            ):
                # Old and completed consumed histories may lose their
                # disposable result files. Their opaque terminal hash proves
                # they are unrelated to the one fixed live capsule.
                continue
            _require_operation_journal_durable(root, journal_path)
            candidate = _project_update_delivery_candidate(
                root,
                journal_path,
                records,
                allow_active_handoff=allow_active_handoff,
                allow_display_pending=True,
            )
            if active_present and not candidate.active_handoff:
                continue
            if display_pending_present and not candidate.display_pending:
                continue
            matches.append(candidate)
        return matches

    observed_matches = matching_candidates()
    if not observed_matches:
        if display_pending_present:
            raise OperationControlError("operation_terminal_delivery_invalid")
        return None
    if len(observed_matches) != 1:
        raise OperationControlError("operation_terminal_delivery_ambiguous")
    guard = _path_below(
        root,
        PurePosixPath(PROJECT_UPDATE_TERMINAL_GUARD_RELATIVE),
    )
    try:
        with project_update_transaction._exclusive_guard(guard, within=root):
            matches = matching_candidates()
            if not matches:
                raise OperationControlError(
                    "operation_terminal_delivery_changed"
                )
            if len(matches) != 1:
                raise OperationControlError(
                    "operation_terminal_delivery_ambiguous"
                )
            return matches[0]
    except project_update_transaction.ProjectUpdateTransactionError:
        raise OperationControlError(
            "operation_terminal_delivery_guard_unavailable"
        ) from None


def _terminal_delivery_candidate_still_exact(
    candidate: ProjectUpdatePendingTerminalDelivery,
) -> bool:
    try:
        active = _path_below(
            candidate.control_root,
            PurePosixPath(PROJECT_UPDATE_TERMINAL_ACTIVE_RELATIVE),
        )
        active_sha256 = _project_update_private_file_sha256(
            candidate.control_root,
            active,
        )
        if candidate.active_handoff:
            if active_sha256 != candidate.terminal_handoff_sha256:
                return False
        elif active_sha256 is not None:
            return False
        digest, size, payload = _hash_result_artifact(
            candidate.control_root,
            candidate.output_path,
        )
        capsule_bytes = _project_update_private_file_bytes(
            candidate.control_root,
            candidate.consumed_path,
            expected_sha256=candidate.terminal_handoff_sha256,
        )
    except OperationControlError:
        return False
    return bool(
        digest == candidate.result_sha256
        and size == candidate.result_bytes
        and payload == candidate.result_document
        and capsule_bytes == candidate.capsule_bytes
    )


def _require_operation_journal_durable(root: Path, journal_path: Path) -> None:
    """Re-establish exact journal file durability before directory durability."""

    _validate_existing_chain(root, journal_path)
    try:
        observed = os.lstat(journal_path)
        if (
            stat.S_ISLNK(observed.st_mode)
            or _is_reparse(observed)
            or not stat.S_ISREG(observed.st_mode)
            or observed.st_nlink != 1
            or not 0 < observed.st_size <= MAX_JOURNAL_BYTES
        ):
            raise OSError("operation_journal_identity_changed")
        descriptor = os.open(
            str(journal_path),
            os.O_RDWR | getattr(os, "O_BINARY", 0),
        )
        try:
            opened = os.fstat(descriptor)
            identity = (int(observed.st_dev), int(observed.st_ino))
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_nlink != 1
                or (int(opened.st_dev), int(opened.st_ino)) != identity
                or opened.st_size != observed.st_size
            ):
                raise OSError("operation_journal_identity_changed")
            os.fsync(descriptor)
            final = os.fstat(descriptor)
            if (
                (int(final.st_dev), int(final.st_ino)) != identity
                or final.st_size != observed.st_size
            ):
                raise OSError("operation_journal_identity_changed")
        finally:
            os.close(descriptor)
        project_update_transaction._require_directory_durable(
            journal_path.parent
        )
    except (
        OSError,
        OperationControlError,
        project_update_transaction.ProjectUpdateTransactionError,
    ):
        raise OperationControlError(
            "operation_terminal_delivery_commit_unverified"
        ) from None


def _terminal_delivery_capability_matches(
    candidate: ProjectUpdatePendingTerminalDelivery,
    capability: str,
) -> bool:
    if re.fullmatch(r"hmac-sha256:[0-9a-f]{64}", capability) is None:
        return False
    execution = candidate.result_document.get("cli_execution")
    delivery = (
        execution.get("terminal_delivery")
        if type(execution) is dict
        else None
    )
    if type(delivery) is not dict or set(delivery) != {
        "schema",
        "terminal_handoff_sha256",
        "result_payload_sha256",
        "output_relative_sha256",
        "run_id",
        "operation_ref",
        "proof",
    }:
        return False
    try:
        output_relative = candidate.output_path.relative_to(
            candidate.control_root
        ).as_posix()
    except ValueError:
        return False
    expected_binding = {
        "schema": (
            "wom-kit/project-version-update-terminal-delivery-binding/v0.4.16"
        ),
        "terminal_handoff_sha256": candidate.terminal_handoff_sha256,
        "result_payload_sha256": _canonical_document_sha256(
            {
                key: value
                for key, value in candidate.result_document.items()
                if key not in {"cli_execution", "cli_output_artifact"}
            }
        ),
        "output_relative_sha256": (
            "sha256:"
            + hashlib.sha256(output_relative.encode("utf-8")).hexdigest()
        ),
        "run_id": candidate.run_id,
        "operation_ref": candidate.operation_ref,
    }
    if any(
        delivery.get(key) != value for key, value in expected_binding.items()
    ):
        return False
    expected_proof = "hmac-sha256:" + hmac.new(
        capability.encode("ascii"),
        b"wom-kit/project-version-update-terminal-delivery-proof/v0.4.16\x00"
        + project_update_transaction.canonical_json_bytes(expected_binding),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(
        str(delivery.get("proof") or ""),
        expected_proof,
    )


def verify_pending_project_update_terminal_delivery(
    candidate: ProjectUpdatePendingTerminalDelivery,
    *,
    delivery_capability: str,
) -> ProjectUpdatePendingTerminalDelivery | None:
    """Re-read one candidate under guard and bind it to a claim capability."""

    if (
        type(candidate) is not ProjectUpdatePendingTerminalDelivery
        or not isinstance(delivery_capability, str)
    ):
        return None
    try:
        root = require_control_root(candidate.control_root)
        guard = _path_below(
            root,
            PurePosixPath(PROJECT_UPDATE_TERMINAL_GUARD_RELATIVE),
        )
        with project_update_transaction._exclusive_guard(guard, within=root):
            pending = _pending_project_update_delivery_records(root)
            matches: list[ProjectUpdatePendingTerminalDelivery] = []
            for journal_path, records in pending:
                if not hmac.compare_digest(
                    str(
                        records[-1].get("terminal_handoff_sha256") or ""
                    ),
                    candidate.terminal_handoff_sha256,
                ):
                    continue
                _require_operation_journal_durable(root, journal_path)
                observed = _project_update_delivery_candidate(
                    root,
                    journal_path,
                    records,
                    allow_active_handoff=(
                        candidate.active_handoff
                    ),
                    allow_display_pending=(
                        candidate.display_pending
                    ),
                )
                if (
                    observed.active_handoff != candidate.active_handoff
                    or observed.display_pending != candidate.display_pending
                ):
                    continue
                matches.append(observed)
            if len(matches) != 1:
                return None
            verified = matches[0]
            if (
                verified != candidate
                or not _terminal_delivery_capability_matches(
                    verified,
                    delivery_capability,
                )
            ):
                return None
            return verified
    except (
        OSError,
        OperationControlError,
        project_update_transaction.ProjectUpdateTransactionError,
    ):
        return None




def _control_base(operation_ref: str, action: str) -> dict[str, Any]:
    safe_operation_ref = (
        operation_ref
        if OPERATION_REF_RE.fullmatch(str(operation_ref or "")) is not None
        else None
    )
    return {
        "schema": OPERATION_CONTROL_SCHEMA,
        "ok": False,
        "dry_run": action != "cancel",
        "lifecycle_action": f"operation_control_{action.replace('-', '_')}",
        "operation_ref": safe_operation_ref,
        "operation_kind": None,
        "run_id": None,
        "owner": {"surface": "local_cli", "ref": None},
        "state": "blocked",
        "terminal": False,
        "terminal_source": None,
        "stage": None,
        "elapsed_ms": None,
        "last_observed_at": None,
        "checkpoint": {"sequence": None, "last_completed_stage": None},
        "result": {
            "available": False,
            "artifact_available": False,
            "command_result_available": False,
            "failure_artifact_available": False,
            "available_at_completion": False,
            "reconciled_from_complete_output": False,
            "binding_verified": False,
            "ok": None,
            "exit_code": None,
            "domain_truth_verified": False,
            "domain": None,
        },
        "control": {
            "control_digest": None,
            "cancel_supported": False,
            "cancel_requested": False,
            "resume_supported": False,
            "recovery_required": False,
        },
        "wait": None,
        "durability_flush": {
            "attempted": False,
            "verified": False,
            "logical_namespace_or_content_changed": False,
        },
        "next_safe_actions": [],
        "blockers": [],
        "warnings": [],
        "privacy_guards": {
            "writes": False,
            "logical_namespace_or_content_writes": False,
            "locks_acquired": False,
            "process_ids_echoed": False,
            "local_paths_echoed": False,
            "private_values_echoed": False,
            "raw_errors_echoed": False,
            "provider_or_network_called": False,
        },
    }


def _journal_candidates(root: Path, operation_hex: str) -> list[Path]:
    candidates = [
        _path_below(root, ARCHIVE_JOURNAL_RELATIVE)
        / f"{operation_hex}.jsonl",
        _path_below(root, PROJECT_JOURNAL_RELATIVE)
        / f"{operation_hex}.jsonl",
    ]
    return [path for path in candidates if path.exists() or path.is_symlink()]


_PROJECT_UPDATE_DRY_RUN_REVIEW_ACTIONS = (
    "Treat this completed result as dry-run only and review the full bound output",
    "If review still supports the update, use a separate fresh project-version-update approval",
)
_PROJECT_UPDATE_SUCCESS_STATUS_ACTIONS = {
    "ready_for_approval": _PROJECT_UPDATE_DRY_RUN_REVIEW_ACTIONS,
    "ready_to_fetch_on_approve": _PROJECT_UPDATE_DRY_RUN_REVIEW_ACTIONS,
    "preview_only_platform_unsupported": (
        "No update was applied; run a fresh project-version-update --dry-run on supported Windows before considering a separate approval",
    ),
    "updated_restart_required": (
        "Start a new process and run archive version <project-or-archive-root> --format json before claiming the update active",
    ),
    "no_change": (
        "No write or restart is required; run archive version <project-or-archive-root> --format json to verify the project is already current",
    ),
}
_PROJECT_UPDATE_UNKNOWN_SUCCESS_ACTIONS = (
    "Do not infer update, approval, or restart state from this unrecognized successful status",
    "Review the complete bound output and run a fresh project-version-update --dry-run before taking another action",
)

_STAGED_CLEANUP_COMPLETED_ACTIONS = {
    "safe_to_cleanup": (
        "Review the complete bound staged-cleanup result and run archive doctor --strict plus artifact-hygiene checks before any separate manual cleanup",
        "Treat cleanup as a separate human decision because staged-cleanup-check never deletes entries and operation-control is not deletion approval",
    ),
    "not_safe_to_cleanup": (
        "Do not delete or move staged entries",
        "Review the complete bound result's opaque entry references and preservation evidence; keep deferred entries staged, preserve unresolved bytes, then run a fresh staged-cleanup-check",
    ),
    "inspection_blocked": (
        "Do not delete or move staged entries",
        "Resolve the complete bound result's fixed reason codes, then run a fresh staged-cleanup-check",
    ),
}


def _project_update_completed_next_actions(
    domain: object,
) -> list[str] | None:
    if (
        not isinstance(domain, dict)
        or domain.get("command") != "project-version-update"
    ):
        return None
    if domain.get("completion_ok") is True:
        if domain.get("terminal_finalization_invalid") is True:
            return [
                "Preserve the bound output and terminal evidence because terminal finalization could not be validated",
                "Do not rerun the completed project update writer; inspect the bound output through a fresh operation-control status",
            ]
        status = domain.get("status")
        status_actions = (
            _PROJECT_UPDATE_SUCCESS_STATUS_ACTIONS.get(status)
            if isinstance(status, str)
            else None
        )
        actions = list(
            status_actions or _PROJECT_UPDATE_UNKNOWN_SUCCESS_ACTIONS
        )
        terminal = domain.get("terminal_finalization")
        if (
            isinstance(terminal, dict)
            and terminal.get("attention_required") is True
        ):
            if (
                terminal.get("transaction_cleanup_completed") is True
                and terminal.get("service_resource_close_verified") is True
                and terminal.get("git_runner_close_verified") is True
                and terminal.get("durable_result_delivery_acknowledged")
                is False
            ):
                return [
                    "Preserve the durable terminal handoff and use project-version-update --resume with a new project-scoped --output before another fresh update",
                    *actions,
                ]
            return [
                "Preserve terminal cleanup evidence and do not rerun the completed project update writer",
                *actions,
            ]
        return actions

    target_tag = domain.get("target_tag")
    collision_refs = domain.get("collision_refs")
    materialization_plan_sha256 = domain.get(
        "materialization_plan_sha256"
    )
    if (
        isinstance(target_tag, str)
        and SAFE_RELEASE_TAG_RE.fullmatch(target_tag) is not None
        and isinstance(materialization_plan_sha256, str)
        and CONTROL_DIGEST_RE.fullmatch(materialization_plan_sha256)
        is not None
        and isinstance(collision_refs, list)
        and collision_refs
        and isinstance(collision_refs[0], str)
        and SAFE_COLLISION_REF_RE.fullmatch(collision_refs[0]) is not None
    ):
        if len(collision_refs) > 1:
            return [
                "Inspect the complete bound collision set in one read-only "
                "batch without revealing local paths: "
                "archive project-version-update-collision "
                "<project-or-archive-root> "
                f"--target {target_tag} "
                f"--expected-plan-sha256 {materialization_plan_sha256} "
                "--action inspect-all --dry-run --format json"
            ]
        return [
            "Inspect the bound collision without revealing a local path: "
            "archive project-version-update-collision "
            "<project-or-archive-root> "
            f"--target {target_tag} --entry-ref {collision_refs[0]} "
            f"--expected-plan-sha256 {materialization_plan_sha256} "
            "--action inspect --dry-run --format json"
        ]

    blocker_codes = domain.get("blocker_codes")
    has_materialization_blocker = bool(
        isinstance(blocker_codes, list)
        and any(
            isinstance(code, str)
            and ("collision" in code or "materialization" in code)
            for code in blocker_codes
        )
    )
    if has_materialization_blocker:
        return [
            "Review the complete output artifact's opaque materialization issue references; do not rerun approved project-version-update until each collision has a fresh read-only inspection"
        ]
    return [
        "Review the complete output artifact's fixed blocker_codes and rerun only a fresh project-version-update --dry-run after the blocker is resolved; do not repeat approval from operation-control alone"
    ]


def _staged_cleanup_completed_next_actions(
    domain: object,
) -> list[str] | None:
    if (
        not isinstance(domain, dict)
        or domain.get("command") != "staged-cleanup-check"
    ):
        return None
    state = domain.get("state")
    actions = (
        _STAGED_CLEANUP_COMPLETED_ACTIONS.get(state)
        if isinstance(state, str)
        else None
    )
    return list(actions) if actions is not None else None


def _completed_result_next_actions(domain: object) -> list[str] | None:
    return _project_update_completed_next_actions(
        domain
    ) or _staged_cleanup_completed_next_actions(domain)


def inspect_operation(
    control_root: Path | str,
    operation_ref: str,
    *,
    action: str = "status",
) -> dict[str, Any]:
    result = _control_base(str(operation_ref or ""), action)
    try:
        operation_hex = _operation_hex(operation_ref)
        root = require_control_root(control_root)
        candidates = _journal_candidates(root, operation_hex)
        if not candidates:
            raise OperationControlError("operation_not_found")
        if len(candidates) != 1:
            raise OperationControlError("operation_journal_ambiguous")
        records = _read_journal(candidates[0], root)
        if records[0]["operation_ref"] != operation_ref:
            raise OperationControlError("operation_journal_invalid")
        if records[0]["root_ref"] != _root_ref(root):
            raise OperationControlError("operation_root_mismatch")
        if (
            _parse_timestamp(records[-1]["observed_at"])
            - datetime.now(timezone.utc)
        ).total_seconds() > MAX_FUTURE_SKEW_SECONDS:
            raise OperationControlError("operation_journal_future_timestamp")
    except OperationControlError as exc:
        result["state"] = "recovery_required"
        result["control"]["recovery_required"] = True
        result["blockers"] = [exc.code]
        result["next_safe_actions"] = [
            "Preserve any operation journal, result artifact, and command-owned lock; do not force-kill, delete, or retry the writer from this evidence alone."
        ]
        return result

    first = records[0]
    latest = records[-1]
    terminal = bool(latest["terminal"])
    last_observed = _parse_timestamp(latest["observed_at"])
    age_seconds = max(
        0.0, (datetime.now(timezone.utc) - last_observed).total_seconds()
    )
    artifact_match: dict[str, Any] | None = None
    verification_blocker: str | None = None
    should_reconcile_artifact = terminal or age_seconds > HEARTBEAT_STALE_SECONDS
    if should_reconcile_artifact:
        try:
            artifact_match = _find_result_artifact(
                root,
                operation_ref=str(latest["operation_ref"]),
                run_id=str(latest["run_id"]),
                root_ref=str(latest["root_ref"]),
                output_ref=str(latest["output_ref"]),
                command=KIND_COMMANDS[str(latest["operation_kind"])],
                expected_sha256=(
                    str(latest["result_sha256"])
                    if latest["result_available"]
                    else None
                ),
                expected_bytes=(
                    int(latest["result_bytes"])
                    if latest["result_available"]
                    else None
                ),
                expected_exit_code=(
                    int(latest["exit_code"])
                    if latest["result_available"]
                    else None
                ),
                expected_result_ok=(
                    bool(latest["result_ok"])
                    if latest["result_available"]
                    else None
                ),
            )
        except OperationControlError as exc:
            verification_blocker = exc.code
    if (
        artifact_match is not None
        and KIND_COMMANDS[str(latest["operation_kind"])]
        == "project-version-update"
    ):
        if terminal:
            delivery_projection_verified = (
                _apply_project_update_delivery_projection(
                    artifact_match,
                    control_root=root,
                    journal_delivery_acknowledged=False,
                    journal_handoff_sha256=(
                        latest.get("terminal_handoff_sha256")
                    ),
                )
            )
        else:
            # A complete-looking output cannot promote an unfinished journal.
            # The authenticated resume path can republish from the active
            # ready handoff; read-only control never invents that authority.
            artifact_match = None
            verification_blocker = (
                "operation_terminal_publication_unverified"
            )
    result_binding_verified = artifact_match is not None
    durability_flush_attempted = bool(
        artifact_match is not None
        and artifact_match.get(
            "terminal_delivery_durability_flush_attempted"
        )
        is True
    )
    durability_flush_verified = bool(
        artifact_match is not None
        and artifact_match.get(
            "terminal_delivery_durability_flush_verified"
        )
        is True
    )
    reconciled_from_output = result_binding_verified and not (
        terminal and latest["result_available"]
    )
    effective_terminal = terminal or reconciled_from_output
    command_result_available = bool(
        artifact_match is not None
        and artifact_match.get("command_result_available") is True
    )
    if result_binding_verified and command_result_available:
        state = "completed_result_available"
        recovery_required = False
    elif result_binding_verified:
        state = "completed_failure_artifact_available"
        recovery_required = True
    elif terminal and latest["result_available"]:
        state = "recovery_required"
        recovery_required = True
        if verification_blocker is None:
            verification_blocker = "operation_result_missing_or_unverifiable"
    elif terminal:
        state = "recovery_required"
        recovery_required = True
        if verification_blocker is None:
            verification_blocker = "operation_result_unavailable_at_completion"
    elif age_seconds <= HEARTBEAT_STALE_SECONDS:
        state = "running_observed"
        recovery_required = False
    else:
        state = "recovery_required"
        recovery_required = True
        if verification_blocker is None:
            verification_blocker = "operation_observation_stale"
    result.update(
        {
            "ok": not recovery_required,
            "operation_kind": latest["operation_kind"],
            "run_id": latest["run_id"],
            "owner": {"surface": "local_cli", "ref": latest["owner_ref"]},
            "state": state,
            "terminal": effective_terminal,
            "terminal_source": (
                "journal_and_complete_output"
                if terminal and result_binding_verified
                else "complete_output_reconciliation"
                if reconciled_from_output
                else "journal_without_verified_output"
                if terminal
                else None
            ),
            "stage": latest["stage"],
            "elapsed_ms": latest["elapsed_ms"],
            "last_observed_at": latest["observed_at"],
            "checkpoint": {
                "sequence": latest["sequence"],
                "last_completed_stage": latest["last_completed_stage"],
            },
            "result": {
                "available": bool(
                    result_binding_verified
                    and command_result_available
                ),
                "artifact_available": result_binding_verified,
                "command_result_available": command_result_available,
                "failure_artifact_available": bool(
                    result_binding_verified
                    and not command_result_available
                ),
                "available_at_completion": bool(latest["result_available"]),
                "reconciled_from_complete_output": reconciled_from_output,
                "binding_verified": result_binding_verified,
                "ok": (
                    artifact_match["result_ok"]
                    if artifact_match is not None
                    else latest["result_ok"]
                ),
                "exit_code": (
                    artifact_match["exit_code"]
                    if artifact_match is not None
                    else latest["exit_code"]
                ),
                "domain_truth_verified": False,
                "domain": (
                    artifact_match.get("domain")
                    if artifact_match is not None
                    else None
                ),
            },
            "control": {
                "control_digest": first["control_digest"],
                "cancel_supported": False,
                "cancel_requested": False,
                "resume_supported": False,
                "recovery_required": recovery_required,
            },
            "durability_flush": {
                "attempted": durability_flush_attempted,
                "verified": durability_flush_verified,
                "logical_namespace_or_content_changed": False,
            },
            "blockers": [verification_blocker] if verification_blocker else [],
        }
    )
    result["privacy_guards"]["writes"] = durability_flush_attempted
    if durability_flush_attempted:
        result["dry_run"] = False
    if state == "running_observed":
        result["next_safe_actions"] = [
            "Wait for the same operation; do not start a duplicate writer and do not treat a caller timeout as cancellation."
        ]
    elif state == "completed_result_available":
        result["next_safe_actions"] = (
            _completed_result_next_actions(result["result"].get("domain"))
            or [
                "Use the complete output artifact and the command-specific verification step before claiming domain completion."
            ]
        )
    elif state == "completed_failure_artifact_available":
        result["next_safe_actions"] = [
            "Use the bound failure artifact only as proof that the command ended; do not infer that no domain effects occurred or start a duplicate writer.",
            "Use the command-specific read-only recovery path before any retry.",
        ]
    else:
        result["next_safe_actions"] = [
            "Run operation-control recovery-plan; preserve journals, results, locks, and SQLite sidecars until command-specific authority is checked."
        ]
    return result


def wait_operation(
    control_root: Path | str,
    operation_ref: str,
    timeout_seconds: int,
    *,
    _clock: Callable[[], float] = time.monotonic,
    _sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, int)
        or not 1 <= timeout_seconds <= MAX_WAIT_SECONDS
    ):
        result = _control_base(operation_ref, "wait")
        result["blockers"] = ["operation_wait_timeout_invalid"]
        result["next_safe_actions"] = [
            "Choose --timeout-seconds from 1 through 60."
        ]
        return result
    deadline = _clock() + timeout_seconds
    while True:
        result = inspect_operation(
            control_root, operation_ref, action="wait"
        )
        if (
            not result["ok"]
            or result["terminal"]
            or result["control"]["recovery_required"]
        ):
            result["wait"] = {
                "outcome": "terminal_or_attention_observed",
                "timeout_seconds": timeout_seconds,
                "cancel_requested": False,
            }
            return result
        remaining = deadline - _clock()
        if remaining <= 0:
            result["wait"] = {
                "outcome": "deadline_reached",
                "timeout_seconds": timeout_seconds,
                "cancel_requested": False,
            }
            result["next_safe_actions"] = [
                "Waiting stopped; the operation may still be running. No cancel request was sent. Run status or wait again with the same operation_ref."
            ]
            return result
        _sleep(min(0.25, remaining))


def recovery_plan(
    control_root: Path | str,
    operation_ref: str,
) -> dict[str, Any]:
    result = inspect_operation(
        control_root, operation_ref, action="recovery-plan"
    )
    kind = result.get("operation_kind")
    if result.get("state") == "running_observed":
        actions = [
            "Wait for the same operation_ref; do not start a duplicate writer and do not send a force-kill."
        ]
    elif result.get("state") == "completed_result_available":
        if kind == "project_version_update":
            actions = (
                _project_update_completed_next_actions(
                    result.get("result", {}).get("domain")
                    if isinstance(result.get("result"), dict)
                    else None
                )
                or [
                    "Review the complete project-version-update output before deciding whether a fresh dry-run is safe."
                ]
            )
        elif kind == "staged_cleanup_check":
            actions = (
                _staged_cleanup_completed_next_actions(
                    result.get("result", {}).get("domain")
                    if isinstance(result.get("result"), dict)
                    else None
                )
                or [
                    "Do not delete or move staged entries; review the complete staged-cleanup result and run a fresh staged-cleanup-check before any manual cleanup"
                ]
            )
        elif kind == "archive_index":
            actions = [
                "Run archive index-health <archive-root> --dry-run --progress --format json before retrying an index-dependent command."
            ]
        else:
            actions = [
                "Review the complete index-health result together with its exit code and index_state."
            ]
    else:
        actions = [
            "Preserve the operation journal, complete result if present, command-owned locks, and SQLite sidecars.",
            "Do not force-kill, delete a lock or sidecar, claim cancellation, resume an old SQLite transaction, or start a duplicate writer from this evidence alone.",
        ]
        if kind == "project_version_update":
            actions.append(
                "Run archive version <project-or-archive-root> --format json and compare source, pins, tag, receipt, and import-origin evidence."
            )
        elif kind in {"archive_index", "archive_index_health"}:
            actions.append(
                "Run a fresh archive index-health <archive-root> --dry-run --progress --format json; treat committed SQLite truth as authoritative over missing terminal output."
            )
    result["next_safe_actions"] = actions
    return result


def unsupported_cancel(
    control_root: Path | str,
    operation_ref: str,
    *,
    approve: bool,
    reviewed_by: str | None,
    expected_control_digest: str | None,
) -> dict[str, Any]:
    # v0.3 intentionally has no cooperative cancel protocol.  Approval inputs
    # are accepted only for forward-compatible CLI parsing and never validated,
    # persisted, or treated as authorization in this unsupported surface.
    del approve, reviewed_by, expected_control_digest
    result = inspect_operation(control_root, operation_ref, action="cancel")
    result["ok"] = False
    result["dry_run"] = False
    blockers: list[str] = list(result.get("blockers") or [])
    if "operation_cancel_not_supported" not in blockers:
        blockers.append("operation_cancel_not_supported")
    result["state"] = "blocked"
    result["blockers"] = blockers
    result["control"]["cancel_supported"] = False
    result["control"]["cancel_requested"] = False
    result["control"]["resume_supported"] = False
    result["next_safe_actions"] = [
        "No cancel request was written. Use status or bounded wait; if observation becomes stale, use recovery-plan without deleting locks or sidecars."
    ]
    return result


__all__ = [
    "ARCHIVE_OUTPUT_PREFIX",
    "MAX_WAIT_SECONDS",
    "OPERATION_CONTROL_SCHEMA",
    "OPERATION_JOURNAL_SCHEMA",
    "PROJECT_OUTPUT_PREFIX",
    "OperationControlError",
    "OperationRunJournal",
    "inspect_operation",
    "recovery_plan",
    "require_control_root",
    "unsupported_cancel",
    "wait_operation",
]
