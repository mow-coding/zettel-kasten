"""Read-only evidence for field-scoped ``frontmatter.assets`` evolution.

This module deliberately proves less than a full-file history.  It can show
that one unique chain of completed local-recovery exact operations binds an
anchor ``assets`` value to the current ``assets`` value while every other
zettel field remains unchanged.  It does not call that chain a historical
full-file SHA chain and it does not independently authenticate the person who
approved the original operation.

The archive is indexed once per evidence family.  Classification consumes
caller-supplied snapshots and performs no archive reread, so a Doctor-style
caller can reuse one index across thousands of mint receipts.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping

from . import archive_services
from .exact_operation_manifest import (
    APPROVAL_AUTHORITY_SCHEMA,
    EXACT_OPERATION_LOCAL_ROOT,
    EXACT_OPERATION_RECEIPTS_ROOT,
    ExactOperationApprovalAuthority,
    ExactOperationManifestError,
    exact_operation_execution_sha256,
    load_exact_operation_final_receipt_read_only,
    validate_exact_operation_resume_checkpoint_read_only,
)
from .local_recovery_execution import (
    APPLY_OPERATION,
    CONTROL_ROOT,
    MAX_CONTROL_BYTES,
    MAX_CONTROL_FILES,
    RESUME_LOCATOR_SCHEMA,
    RESUME_ROOT,
    SUPERSESSION_FINAL_SCHEMA,
    SUPERSESSION_PENDING_SCHEMA,
    SUPERSESSION_ROOT,
    LocalRecoveryError,
    LocalRecoveryPlan,
    load_local_recovery_plan,
    _frontmatter_value_replacement,
)


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONTROL_NAME_RE = re.compile(r"^([0-9a-f]{64})\.json$")
_LOCATOR_NAME_RE = re.compile(
    r"^([0-9a-f]{64})\.(apply|revert)\."
    r"(approval_[0-9a-f]{32})\.json$"
)
_EXECUTION_NAME_RE = re.compile(r"^([0-9a-f]{64})\.(?:json|jsonl)$")
_SUPERSESSION_NAME_RE = re.compile(
    r"^([0-9a-f]{64})\.([0-9a-f]{64})\.(pending|final)\.json$"
)
_MAX_LOCATOR_BYTES = 64 * 1024
_MAX_SUPERSESSION_BYTES = 64 * 1024
_MAX_CHECKPOINT_BYTES = 256 * 1024 * 1024
_MAX_ZETTEL_BYTES = 16 * 1024 * 1024
_EXPECTED_DOMAIN = "zettel_objet_link"
_ASSETS_FIELD = "frontmatter.assets"


@dataclass(frozen=True)
class _AssetsTransition:
    target_relative: str
    zettel_id: str
    pre_assets: bytes
    post_assets: bytes
    manifest_sha256: str
    execution_sha256: str


@dataclass(frozen=True)
class LocalRecoveryAssetsEvolutionIndex:
    """Content-private reusable index; public projections expose counts only."""

    archive_root: Path
    transitions_by_target: Mapping[str, tuple[_AssetsTransition, ...]]
    blocked_targets: Mapping[str, tuple[str, ...]]
    reason_codes: tuple[str, ...]
    scan_counts: Mapping[str, int]

    @property
    def valid(self) -> bool:
        return not self.reason_codes

    def public_scan_counts(self) -> dict[str, int]:
        return dict(self.scan_counts)


class _DuplicateJsonKey(ValueError):
    pass


def _reject_constant(_value: str) -> None:
    raise ValueError("non-finite-json-number")


def _pairs_to_dict(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _strict_json(raw: bytes) -> Any:
    return json.loads(
        raw.decode("ascii"),
        object_pairs_hook=_pairs_to_dict,
        parse_constant=_reject_constant,
    )


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _canonical_line(value: Mapping[str, Any]) -> bytes:
    return _canonical_bytes(dict(value)) + b"\n"


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _is_reparse(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _safe_directory_entries_once(
    root: Path,
    relative: str,
) -> tuple[Path, ...]:
    directory = archive_services.archive_internal_path(root, relative)
    try:
        before = os.lstat(directory)
    except FileNotFoundError:
        return ()
    if (
        not stat.S_ISDIR(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or _is_reparse(before)
    ):
        raise ValueError("unsafe-directory")
    entries = tuple(sorted(directory.iterdir(), key=lambda path: path.name))
    if len(entries) > MAX_CONTROL_FILES:
        raise ValueError("too-many-entries")
    after = os.lstat(directory)
    if (
        not stat.S_ISDIR(after.st_mode)
        or stat.S_ISLNK(after.st_mode)
        or _is_reparse(after)
        or (before.st_dev, before.st_ino, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_mtime_ns)
    ):
        raise ValueError("directory-changed")
    for path in entries:
        info = os.lstat(path)
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_ISLNK(info.st_mode)
            or _is_reparse(info)
        ):
            raise ValueError("unsafe-entry")
    return entries


def _stable_file(path: Path, *, max_bytes: int) -> bytes:
    raw, reason = archive_services._bounded_stable_regular_file_read(
        path,
        max_bytes=max_bytes,
    )
    if raw is None or reason is not None:
        raise ValueError("unsafe-file")
    return raw


def _canonical_json_file(path: Path, *, max_bytes: int) -> tuple[dict[str, Any], bytes]:
    raw = _stable_file(path, max_bytes=max_bytes)
    if not raw.endswith(b"\n") or raw == b"\n":
        raise ValueError("canonical-newline")
    document = _strict_json(raw[:-1])
    if not isinstance(document, dict) or _canonical_line(document) != raw:
        raise ValueError("canonical-json")
    return document, raw


def _safe_target_relative(value: str) -> str:
    if type(value) is not str or not value or "\\" in value:
        raise ValueError("target-relative")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or not value.startswith("zettels/")
        or path.suffix.lower() != ".md"
    ):
        raise ValueError("target-relative")
    return path.as_posix()


def _asset_state(value: bytes | None) -> list[dict[str, Any]]:
    if type(value) is not bytes:
        raise ValueError("assets-state")
    parsed = _strict_json(value)
    if (
        type(parsed) is not list
        or any(type(item) is not dict for item in parsed)
        or _canonical_bytes(parsed) != value
    ):
        raise ValueError("assets-state")
    return parsed


def _source_state(value: bytes) -> dict[str, Any]:
    parsed = _strict_json(value)
    expected = {
        "capture_receipt_sha256",
        "receipt_ordinal",
        "object_id",
        "source_ids",
    }
    if (
        not isinstance(parsed, dict)
        or set(parsed) != expected
        or _canonical_bytes(parsed) != value
        or _SHA256_RE.fullmatch(str(parsed.get("capture_receipt_sha256") or ""))
        is None
        or type(parsed.get("receipt_ordinal")) is not int
        or parsed["receipt_ordinal"] < 0
        or type(parsed.get("object_id")) is not str
        or _SHA256_RE.fullmatch(parsed["object_id"]) is None
        or type(parsed.get("source_ids")) is not list
        or any(type(item) is not str or not item for item in parsed["source_ids"])
        or parsed["source_ids"] != sorted(set(parsed["source_ids"]))
    ):
        raise ValueError("source-state")
    return parsed


def _validated_assets_specs(plan: LocalRecoveryPlan) -> tuple[Any, ...]:
    if plan.domain != _EXPECTED_DOMAIN or plan.manifest.operation != APPLY_OPERATION:
        return ()
    specs = tuple(spec for spec in plan.specs if spec.field_ref == _ASSETS_FIELD)
    for spec in specs:
        if (
            spec.target_kind != "zettel"
            or type(spec.zettel_id) is not str
            or not spec.zettel_id
            or spec.post_file_bytes is not None
            or spec.marker_pre_body is not None
            or spec.marker_post_body is not None
        ):
            raise ValueError("assets-spec")
        _safe_target_relative(spec.target_relative)
        pre = _asset_state(spec.pre_value)
        post = _asset_state(spec.post_value)
        source = _source_state(spec.source_value)
        if (
            len(post) != len(pre) + 1
            or post[:-1] != pre
            or set(post[-1]) != {"object_id", "role"}
            or post[-1].get("object_id") != source["object_id"]
            or type(post[-1].get("role")) is not str
            or not post[-1]["role"]
        ):
            raise ValueError("assets-transition")
    return specs


def _validated_locator(
    path: Path,
    match: re.Match[str],
) -> dict[str, Any]:
    document, _raw = _canonical_json_file(path, max_bytes=_MAX_LOCATOR_BYTES)
    expected = {
        "schema_version",
        "domain",
        "mode",
        "approval_id",
        "execution_sha256",
        "apply_manifest_sha256",
        "operation_manifest_sha256",
        "private_values_echoed",
        "paths_echoed",
    }
    manifest_sha256 = "sha256:" + match.group(1)
    mode = match.group(2)
    approval_id = match.group(3)
    if (
        set(document) != expected
        or document.get("schema_version") != RESUME_LOCATOR_SCHEMA
        or document.get("mode") != mode
        or document.get("approval_id") != approval_id
        or document.get("apply_manifest_sha256") != manifest_sha256
        or _SHA256_RE.fullmatch(str(document.get("execution_sha256") or ""))
        is None
        or _SHA256_RE.fullmatch(
            str(document.get("operation_manifest_sha256") or "")
        )
        is None
        or type(document.get("domain")) is not str
        or document.get("private_values_echoed") is not False
        or document.get("paths_echoed") is not False
    ):
        raise ValueError("locator")
    if mode == "apply" and document["operation_manifest_sha256"] != manifest_sha256:
        raise ValueError("locator-operation")
    return document


def _checkpoint_authority(
    path: Path,
    *,
    expected_manifest_sha256: str,
    expected_execution_sha256: str,
) -> tuple[ExactOperationApprovalAuthority, bytes]:
    raw = _stable_file(path, max_bytes=_MAX_CHECKPOINT_BYTES)
    if not raw or not raw.endswith(b"\n"):
        raise ValueError("checkpoint")
    first_line = raw.splitlines()[0]
    row = _strict_json(first_line)
    if not isinstance(row, dict) or _canonical_bytes(row) != first_line:
        raise ValueError("checkpoint")
    approval = row.get("approval")
    if (
        row.get("manifest_sha256") != expected_manifest_sha256
        or row.get("execution_sha256") != expected_execution_sha256
        or row.get("mode") != "apply"
        or row.get("sequence") != 0
        or row.get("stage") != "started"
        or not isinstance(approval, dict)
        or set(approval)
        != {
            "schema",
            "approval_id",
            "context_sha256",
            "approval_authority_sha256",
            "binding_sha256",
        }
        or approval.get("schema") != APPROVAL_AUTHORITY_SCHEMA
    ):
        raise ValueError("checkpoint-authority")
    authority = ExactOperationApprovalAuthority(
        approval_id=approval["approval_id"],
        context_sha256=approval["context_sha256"],
        approval_authority_sha256=approval["approval_authority_sha256"],
        binding_sha256=approval["binding_sha256"],
    )
    return authority, raw


def _validated_supersession_shape(
    path: Path,
    match: re.Match[str],
) -> None:
    document, _raw = _canonical_json_file(
        path,
        max_bytes=_MAX_SUPERSESSION_BYTES,
    )
    parent = "sha256:" + match.group(1)
    compensation = "sha256:" + match.group(2)
    kind = match.group(3)
    if kind == "pending":
        expected = {
            "schema_version",
            "status",
            "parent_apply_manifest_sha256",
            "parent_apply_operation_manifest_sha256",
            "parent_apply_execution_sha256",
            "parent_apply_approval_id",
            "compensation_manifest_sha256",
            "compensation_operation_manifest_sha256",
            "compensation_execution_sha256",
            "compensation_approval_authority",
            "compensation_resume_locator_sha256",
            "compensation_field_count",
            "private_values_echoed",
            "paths_echoed",
            "supersession_sha256",
        }
        authority = document.get("compensation_approval_authority")
        supplied = document.get("supersession_sha256")
        basis = dict(document)
        basis.pop("supersession_sha256", None)
        if (
            set(document) != expected
            or document.get("schema_version") != SUPERSESSION_PENDING_SCHEMA
            or document.get("status") != "pending"
            or document.get("parent_apply_execution_sha256") != parent
            or document.get("compensation_execution_sha256") != compensation
            or any(
                _SHA256_RE.fullmatch(str(document.get(key) or "")) is None
                for key in (
                    "parent_apply_manifest_sha256",
                    "parent_apply_operation_manifest_sha256",
                    "compensation_manifest_sha256",
                    "compensation_operation_manifest_sha256",
                    "compensation_resume_locator_sha256",
                )
            )
            or re.fullmatch(
                r"approval_[0-9a-f]{32}",
                str(document.get("parent_apply_approval_id") or ""),
            )
            is None
            or not isinstance(authority, dict)
            or set(authority)
            != {
                "schema",
                "approval_id",
                "context_sha256",
                "approval_authority_sha256",
                "binding_sha256",
            }
            or type(document.get("compensation_field_count")) is not int
            or document["compensation_field_count"] <= 0
            or document.get("private_values_echoed") is not False
            or document.get("paths_echoed") is not False
            or type(supplied) is not str
            or not hmac.compare_digest(supplied, _digest(_canonical_bytes(basis)))
        ):
            raise ValueError("supersession")
        try:
            ExactOperationApprovalAuthority(
                approval_id=authority["approval_id"],
                context_sha256=authority["context_sha256"],
                approval_authority_sha256=authority[
                    "approval_authority_sha256"
                ],
                binding_sha256=authority["binding_sha256"],
            )
        except (KeyError, ExactOperationManifestError):
            raise ValueError("supersession") from None
        return

    expected = {
        "schema_version",
        "status",
        "parent_apply_manifest_sha256",
        "parent_apply_execution_sha256",
        "compensation_manifest_sha256",
        "compensation_execution_sha256",
        "pending_supersession_sha256",
        "compensation_final_receipt_sha256",
        "parent_pre_state_verified",
        "parent_pre_verification_sha256",
        "private_values_echoed",
        "paths_echoed",
        "supersession_final_sha256",
    }
    supplied = document.get("supersession_final_sha256")
    basis = dict(document)
    basis.pop("supersession_final_sha256", None)
    if (
        set(document) != expected
        or document.get("schema_version") != SUPERSESSION_FINAL_SCHEMA
        or document.get("status") != "final"
        or document.get("parent_apply_execution_sha256") != parent
        or document.get("compensation_execution_sha256") != compensation
        or any(
            _SHA256_RE.fullmatch(str(document.get(key) or "")) is None
            for key in (
                "parent_apply_manifest_sha256",
                "compensation_manifest_sha256",
                "pending_supersession_sha256",
                "compensation_final_receipt_sha256",
                "parent_pre_verification_sha256",
            )
        )
        or document.get("parent_pre_state_verified") is not True
        or document.get("private_values_echoed") is not False
        or document.get("paths_echoed") is not False
        or type(supplied) is not str
        or not hmac.compare_digest(supplied, _digest(_canonical_bytes(basis)))
    ):
        raise ValueError("supersession")


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def build_local_recovery_assets_evolution_index(
    archive_root: Path | str,
    *,
    heartbeat: Callable[[], None] | None = None,
) -> LocalRecoveryAssetsEvolutionIndex:
    """Build one read-only, reusable index of completed assets transitions."""

    callback = heartbeat or (lambda: None)
    root = Path(archive_root).resolve()
    counts: dict[str, int] = {
        "control_directory_scans": 0,
        "control_entry_count": 0,
        "plan_load_count": 0,
        "validated_plan_count": 0,
        "locator_directory_scans": 0,
        "locator_entry_count": 0,
        "final_directory_scans": 0,
        "final_entry_count": 0,
        "checkpoint_directory_scans": 0,
        "checkpoint_entry_count": 0,
        "supersession_directory_scans": 0,
        "supersession_entry_count": 0,
        "final_receipt_validation_count": 0,
        "checkpoint_validation_count": 0,
        "transition_count": 0,
    }
    reasons: list[str] = []
    blocked_targets: dict[str, set[str]] = {}
    transitions: dict[str, list[_AssetsTransition]] = {}

    try:
        root = archive_services.require_existing_archive_root(root)
    except (archive_services.ArchiveServiceError, OSError, ValueError):
        reasons.append("local_recovery_assets_archive_invalid")
        return LocalRecoveryAssetsEvolutionIndex(
            root,
            MappingProxyType({}),
            MappingProxyType({}),
            _unique(reasons),
            MappingProxyType(dict(counts)),
        )

    directory_specs = (
        ("control", CONTROL_ROOT),
        ("locator", RESUME_ROOT),
        ("final", EXACT_OPERATION_RECEIPTS_ROOT),
        ("checkpoint", f"{EXACT_OPERATION_LOCAL_ROOT}/checkpoints"),
        ("supersession", SUPERSESSION_ROOT),
    )
    entries_by_kind: dict[str, tuple[Path, ...]] = {}
    for kind, relative in directory_specs:
        counts[f"{kind}_directory_scans"] += 1
        try:
            entries = _safe_directory_entries_once(root, relative)
        except (OSError, ValueError):
            reasons.append(f"local_recovery_assets_{kind}_index_invalid")
            entries = ()
        entries_by_kind[kind] = entries
        counts[f"{kind}_entry_count"] = len(entries)
        callback()

    plans: dict[str, tuple[LocalRecoveryPlan, tuple[Any, ...]]] = {}
    for path in entries_by_kind["control"]:
        match = _CONTROL_NAME_RE.fullmatch(path.name)
        if match is None:
            reasons.append("local_recovery_assets_control_index_invalid")
            continue
        manifest_sha256 = "sha256:" + match.group(1)
        try:
            _document, before_raw = _canonical_json_file(
                path,
                max_bytes=MAX_CONTROL_BYTES,
            )
            counts["plan_load_count"] += 1
            plan = load_local_recovery_plan(
                root,
                manifest_sha256=manifest_sha256,
            )
            _after_document, after_raw = _canonical_json_file(
                path,
                max_bytes=MAX_CONTROL_BYTES,
            )
            if before_raw != after_raw or not plan.loaded_from_control:
                raise ValueError("control-changed")
            specs = _validated_assets_specs(plan)
            if specs:
                plans[manifest_sha256] = (plan, specs)
                counts["validated_plan_count"] += 1
        except (
            OSError,
            UnicodeError,
            ValueError,
            json.JSONDecodeError,
            LocalRecoveryError,
            ExactOperationManifestError,
        ):
            reasons.append("local_recovery_assets_control_invalid")
        callback()

    locators_by_manifest: dict[str, list[dict[str, Any]]] = {}
    for path in entries_by_kind["locator"]:
        match = _LOCATOR_NAME_RE.fullmatch(path.name)
        if match is None:
            reasons.append("local_recovery_assets_locator_index_invalid")
            continue
        try:
            locator = _validated_locator(path, match)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            reasons.append("local_recovery_assets_locator_invalid")
            continue
        manifest_sha256 = locator["apply_manifest_sha256"]
        if locator["mode"] == "apply":
            locators_by_manifest.setdefault(manifest_sha256, []).append(locator)
        callback()

    final_names: set[str] = set()
    for path in entries_by_kind["final"]:
        match = _EXECUTION_NAME_RE.fullmatch(path.name)
        if match is None or not path.name.endswith(".json"):
            reasons.append("local_recovery_assets_final_index_invalid")
        else:
            final_names.add("sha256:" + match.group(1))

    checkpoint_names: set[str] = set()
    for path in entries_by_kind["checkpoint"]:
        match = _EXECUTION_NAME_RE.fullmatch(path.name)
        if match is None or not path.name.endswith(".jsonl"):
            reasons.append("local_recovery_assets_checkpoint_index_invalid")
        else:
            checkpoint_names.add("sha256:" + match.group(1))

    supersessions_by_parent: dict[str, list[Path]] = {}
    for path in entries_by_kind["supersession"]:
        match = _SUPERSESSION_NAME_RE.fullmatch(path.name)
        if match is None:
            reasons.append("local_recovery_assets_supersession_index_invalid")
            continue
        try:
            _validated_supersession_shape(path, match)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            reasons.append("local_recovery_assets_supersession_invalid")
            continue
        supersessions_by_parent.setdefault(
            "sha256:" + match.group(1),
            [],
        ).append(path)
        callback()

    checkpoint_root = archive_services.archive_internal_path(
        root,
        f"{EXACT_OPERATION_LOCAL_ROOT}/checkpoints",
    )
    for manifest_sha256, (plan, specs) in plans.items():
        target_relatives = tuple(spec.target_relative for spec in specs)

        def block(code: str) -> None:
            for target_relative in target_relatives:
                blocked_targets.setdefault(target_relative, set()).add(code)

        candidates = locators_by_manifest.get(manifest_sha256, [])
        if len(candidates) != 1:
            block(
                "local_recovery_assets_execution_missing"
                if not candidates
                else "local_recovery_assets_execution_ambiguous"
            )
            continue
        locator = candidates[0]
        execution = locator["execution_sha256"]
        if locator.get("domain") != plan.domain:
            block("local_recovery_assets_locator_invalid")
            continue
        if supersessions_by_parent.get(execution):
            block("local_recovery_assets_supersession_present")
            continue
        if execution not in final_names or execution not in checkpoint_names:
            block("local_recovery_assets_execution_incomplete")
            continue
        checkpoint_path = checkpoint_root / (
            execution.removeprefix("sha256:") + ".jsonl"
        )
        try:
            authority, checkpoint_before = _checkpoint_authority(
                checkpoint_path,
                expected_manifest_sha256=manifest_sha256,
                expected_execution_sha256=execution,
            )
            if authority.approval_id != locator["approval_id"]:
                raise ValueError("approval-id")
            if not hmac.compare_digest(
                exact_operation_execution_sha256(
                    plan.manifest,
                    mode="apply",
                    approval_authority=authority,
                ),
                execution,
            ):
                raise ValueError("execution")
            counts["checkpoint_validation_count"] += 1
            if not validate_exact_operation_resume_checkpoint_read_only(
                root,
                plan.manifest,
                execution_sha256=execution,
                approval_authority=authority,
                heartbeat=callback,
            ):
                raise ValueError("checkpoint-missing")
            counts["final_receipt_validation_count"] += 1
            final = load_exact_operation_final_receipt_read_only(
                root,
                execution,
                heartbeat=callback,
            )
            if final is None:
                raise ValueError("final-missing")
            result = final["result"]
            expected_evidence = (
                plan.manifest.operation_evidence.document()
                if plan.manifest.operation_evidence is not None
                else None
            )
            actual_evidence = result.get("operation_evidence")
            if (
                result.get("status") != "completed"
                or result.get("mode") != "apply"
                or result.get("manifest_sha256") != manifest_sha256
                or result.get("execution_sha256") != execution
                or result.get("approval_binding_sha256")
                != authority.binding_sha256
                or result.get("item_count") != len(plan.manifest.items)
                or result.get("field_count")
                != sum(len(item.fields) for item in plan.manifest.items)
                or actual_evidence != expected_evidence
            ):
                raise ValueError("final-binding")
            authentication = result.get("completion_authentication")
            if authentication is not None:
                reference = authentication.get("approval_reference")
                authenticated_authority = (
                    ExactOperationApprovalAuthority.from_reference(reference)
                )
                if (
                    authentication.get("operation") != APPLY_OPERATION
                    or authentication.get("target_binding_sha256")
                    != plan.manifest.target_set_sha256
                    or authenticated_authority != authority
                ):
                    raise ValueError("completion-authentication")
            checkpoint_after = _stable_file(
                checkpoint_path,
                max_bytes=_MAX_CHECKPOINT_BYTES,
            )
            if checkpoint_before != checkpoint_after:
                raise ValueError("checkpoint-changed")
        except (
            OSError,
            UnicodeError,
            ValueError,
            json.JSONDecodeError,
            ExactOperationManifestError,
        ):
            block("local_recovery_assets_execution_evidence_invalid")
            continue

        for spec in specs:
            transition = _AssetsTransition(
                target_relative=spec.target_relative,
                zettel_id=spec.zettel_id or "",
                pre_assets=spec.pre_value or b"",
                post_assets=spec.post_value or b"",
                manifest_sha256=manifest_sha256,
                execution_sha256=execution,
            )
            transitions.setdefault(spec.target_relative, []).append(transition)
            counts["transition_count"] += 1

    immutable_transitions = MappingProxyType(
        {
            key: tuple(value)
            for key, value in sorted(transitions.items())
        }
    )
    immutable_blocked = MappingProxyType(
        {
            key: tuple(sorted(value))
            for key, value in sorted(blocked_targets.items())
        }
    )
    return LocalRecoveryAssetsEvolutionIndex(
        root,
        immutable_transitions,
        immutable_blocked,
        _unique(reasons),
        MappingProxyType(dict(counts)),
    )


def _failure(
    index: LocalRecoveryAssetsEvolutionIndex,
    *reason_codes: str,
    ambiguous: bool = False,
) -> dict[str, Any]:
    return {
        "schema": "wom-kit/local-recovery-assets-evolution-classification/v1",
        "success": False,
        "proof_tier": "ambiguous" if ambiguous else "unsupported",
        "reason_codes": list(_unique(reason_codes)),
        "matched_evidence_count": 0,
        "field_scope_only": True,
        "full_file_sha_chain_proven": False,
        "cryptographic_approval_claimed": False,
        "field_state_transition_proven": False,
        "chronological_post_mint_evolution_proven": False,
        "mint_sha_mismatch_softening_allowed": False,
        "scan_counts": index.public_scan_counts(),
        "private_values_echoed": False,
        "paths_echoed": False,
    }


def _zettel_snapshot(raw: bytes) -> tuple[dict[str, Any], str, bool]:
    if type(raw) is not bytes or not raw or len(raw) > _MAX_ZETTEL_BYTES:
        raise ValueError("zettel-bytes")
    text = raw.decode("utf-8")
    has_bom = text.startswith("\ufeff")
    boundary = archive_services.parse_approval_zettel_content_boundary(text)
    if boundary.get("state") != "readable":
        raise ValueError("zettel-boundary")
    payload = text[1:] if has_bom else text
    match = archive_services.FRONTMATTER_RE.match(payload)
    if match is None:
        raise ValueError("zettel-boundary")
    frontmatter = boundary.get("frontmatter")
    if not isinstance(frontmatter, dict):
        raise ValueError("zettel-frontmatter")
    return frontmatter, payload[match.end() :], has_bom


def _parse_cutoff(value: str) -> datetime:
    if type(value) is not str or not value or len(value) > 64:
        raise ValueError("mint-cutoff")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("mint-cutoff")
    return parsed


def _unique_transition_paths(
    transitions: tuple[_AssetsTransition, ...],
    start: bytes,
    destination: bytes,
) -> list[tuple[_AssetsTransition, ...]]:
    by_pre: dict[bytes, list[_AssetsTransition]] = {}
    for transition in transitions:
        by_pre.setdefault(transition.pre_assets, []).append(transition)
    paths: list[tuple[_AssetsTransition, ...]] = []

    def visit(
        current: bytes,
        path: tuple[_AssetsTransition, ...],
        seen: frozenset[bytes],
    ) -> None:
        if len(paths) > 1:
            return
        if current == destination:
            if path:
                paths.append(path)
            return
        for transition in by_pre.get(current, []):
            if transition.post_assets in seen:
                continue
            visit(
                transition.post_assets,
                (*path, transition),
                seen | {transition.post_assets},
            )

    visit(start, (), frozenset({start}))
    return paths


def classify_field_scoped_assets_evolution(
    index: LocalRecoveryAssetsEvolutionIndex,
    *,
    target_relative: str,
    mint_anchor_bytes: bytes,
    mint_anchor_sha256: str,
    mint_cutoff: str,
    current_bytes: bytes,
) -> dict[str, Any]:
    """Classify two caller-owned zet snapshots without rereading the archive."""

    if type(index) is not LocalRecoveryAssetsEvolutionIndex:
        raise TypeError("index must be LocalRecoveryAssetsEvolutionIndex")
    if index.reason_codes:
        return _failure(index, *index.reason_codes)
    try:
        relative = _safe_target_relative(target_relative)
    except ValueError:
        return _failure(index, "local_recovery_assets_target_invalid")
    try:
        _parse_cutoff(mint_cutoff)
    except (TypeError, ValueError):
        return _failure(index, "mint_cutoff_invalid")
    if type(mint_anchor_bytes) is not bytes or type(current_bytes) is not bytes:
        return _failure(index, "zettel_snapshot_invalid")
    if (
        type(mint_anchor_sha256) is not str
        or _SHA256_RE.fullmatch(mint_anchor_sha256) is None
        or not hmac.compare_digest(_digest(mint_anchor_bytes), mint_anchor_sha256)
    ):
        return _failure(index, "mint_anchor_sha256_mismatch")
    if hmac.compare_digest(_digest(current_bytes), mint_anchor_sha256):
        return _failure(index, "mint_anchor_already_current")
    try:
        anchor_frontmatter, anchor_body, anchor_bom = _zettel_snapshot(
            mint_anchor_bytes
        )
        current_frontmatter, current_body, current_bom = _zettel_snapshot(
            current_bytes
        )
    except (UnicodeError, ValueError):
        return _failure(index, "zettel_snapshot_invalid")

    anchor_id = anchor_frontmatter.get("id")
    current_id = current_frontmatter.get("id")
    if (
        type(anchor_id) is not str
        or not anchor_id
        or current_id != anchor_id
    ):
        return _failure(index, "zettel_identity_changed")
    if (
        anchor_frontmatter.get("status") != "canonical"
        or current_frontmatter.get("status") != "canonical"
    ):
        return _failure(index, "zettel_status_not_canonical")
    if anchor_bom != current_bom:
        return _failure(index, "zettel_encoding_marker_changed")
    if anchor_frontmatter.get("title") != current_frontmatter.get("title"):
        return _failure(index, "title_changed_outside_assets_scope")
    if anchor_body != current_body:
        return _failure(index, "body_changed_outside_assets_scope")
    if anchor_frontmatter.get("updated_at") != current_frontmatter.get(
        "updated_at"
    ):
        return _failure(index, "updated_at_change_not_evidence_bound")

    anchor_assets = anchor_frontmatter.get("assets")
    current_assets = current_frontmatter.get("assets")
    if type(anchor_assets) is not list or type(current_assets) is not list:
        return _failure(index, "assets_field_invalid")
    anchor_other = dict(anchor_frontmatter)
    current_other = dict(current_frontmatter)
    anchor_other.pop("assets", None)
    current_other.pop("assets", None)
    if anchor_other != current_other:
        return _failure(index, "frontmatter_changed_outside_assets_scope")
    try:
        anchor_state = _canonical_bytes(anchor_assets)
        current_state = _canonical_bytes(current_assets)
    except (TypeError, ValueError):
        return _failure(index, "assets_field_invalid")
    if anchor_state == current_state:
        return _failure(index, "assets_field_unchanged")

    blocked = index.blocked_targets.get(relative, ())
    if blocked:
        return _failure(
            index,
            *blocked,
            ambiguous=any(code.endswith("_ambiguous") for code in blocked),
        )
    target_transitions = tuple(
        transition
        for transition in index.transitions_by_target.get(relative, ())
        if transition.zettel_id == anchor_id
    )
    if not target_transitions:
        return _failure(index, "local_recovery_assets_evidence_missing")
    paths = _unique_transition_paths(
        target_transitions,
        anchor_state,
        current_state,
    )
    if not paths:
        pre_states = {transition.pre_assets for transition in target_transitions}
        post_states = {transition.post_assets for transition in target_transitions}
        reason_codes = []
        if anchor_state not in pre_states:
            reason_codes.append("assets_pre_state_not_evidence_bound")
        if current_state not in post_states:
            reason_codes.append("assets_post_state_not_evidence_bound")
        return _failure(
            index,
            *(reason_codes or ["assets_transition_chain_missing"]),
        )
    if len(paths) != 1:
        return _failure(
            index,
            "local_recovery_assets_evidence_ambiguous",
            ambiguous=True,
        )
    # v0.4.7 exact-operation controls, locators, checkpoints, and final
    # receipts contain no authenticated completion timestamp.  The archive's
    # HMAC-authenticated approval claim does contain approved/finished times,
    # but the established public read-only auditor returns only a boolean and
    # local recovery did not persist a terminal-MAC payload in its final
    # receipt.  Therefore this module can prove the field-state chain but must
    # not call it a post-mint evolution or soften a mint target SHA mismatch.
    return {
        "schema": "wom-kit/local-recovery-assets-evolution-classification/v1",
        "success": False,
        "proof_tier": "field_scoped_assets_state_evidence_without_chronology",
        "reason_codes": [
            "local_recovery_completion_time_not_evidence_bound"
        ],
        "matched_evidence_count": len(paths[0]),
        "field_scope_only": True,
        "full_file_sha_chain_proven": False,
        "cryptographic_approval_claimed": False,
        "field_state_transition_proven": True,
        "chronological_post_mint_evolution_proven": False,
        "mint_sha_mismatch_softening_allowed": False,
        "scan_counts": index.public_scan_counts(),
        "private_values_echoed": False,
        "paths_echoed": False,
    }


def classify_current_bytes_against_mint_sha(
    index: LocalRecoveryAssetsEvolutionIndex,
    *,
    target_relative: str,
    mint_anchor_sha256: str,
    mint_cutoff: str,
    current_bytes: bytes,
) -> dict[str, Any]:
    """Reconstruct one exact historical anchor from assets-only evidence.

    A mint receipt retains the full historical SHA but not the historical file
    bytes.  The local-recovery writer changed only ``frontmatter.assets`` with
    a byte-preserving replacement routine.  This function reverses each unique
    evidence-bound pre-state against the caller's current stable bytes and
    accepts exactly one candidate whose full-file SHA matches the mint receipt.
    It then delegates to the ordinary field-scoped classifier.  Chronology is
    still unavailable, so even a successful field-state match never softens a
    mint SHA error.
    """

    if type(index) is not LocalRecoveryAssetsEvolutionIndex:
        raise TypeError("index must be LocalRecoveryAssetsEvolutionIndex")
    if index.reason_codes:
        return _failure(index, *index.reason_codes)
    try:
        relative = _safe_target_relative(target_relative)
        _parse_cutoff(mint_cutoff)
    except (TypeError, ValueError):
        return _failure(index, "local_recovery_assets_query_invalid")
    if (
        type(current_bytes) is not bytes
        or not current_bytes
        or len(current_bytes) > _MAX_ZETTEL_BYTES
        or type(mint_anchor_sha256) is not str
        or _SHA256_RE.fullmatch(mint_anchor_sha256) is None
    ):
        return _failure(index, "local_recovery_assets_query_invalid")
    blocked = index.blocked_targets.get(relative, ())
    if blocked:
        return _failure(
            index,
            *blocked,
            ambiguous=any(code.endswith("_ambiguous") for code in blocked),
        )
    transitions = index.transitions_by_target.get(relative, ())
    if not transitions:
        return _failure(index, "local_recovery_assets_evidence_missing")

    candidates: dict[str, bytes] = {}
    for pre_state in dict.fromkeys(
        transition.pre_assets for transition in transitions
    ):
        try:
            candidate = _frontmatter_value_replacement(
                current_bytes,
                "assets",
                _asset_state(pre_state),
            )
        except ValueError:
            continue
        candidate_sha256 = _digest(candidate)
        if hmac.compare_digest(candidate_sha256, mint_anchor_sha256):
            candidates[candidate_sha256 + ":" + _digest(pre_state)] = candidate

    if not candidates:
        return _failure(
            index,
            "mint_anchor_bytes_not_reconstructable_from_assets_evidence",
        )
    if len(candidates) != 1:
        return _failure(
            index,
            "mint_anchor_assets_reconstruction_ambiguous",
            ambiguous=True,
        )
    mint_anchor_bytes = next(iter(candidates.values()))
    return classify_field_scoped_assets_evolution(
        index,
        target_relative=relative,
        mint_anchor_bytes=mint_anchor_bytes,
        mint_anchor_sha256=mint_anchor_sha256,
        mint_cutoff=mint_cutoff,
        current_bytes=current_bytes,
    )


__all__ = [
    "LocalRecoveryAssetsEvolutionIndex",
    "build_local_recovery_assets_evolution_index",
    "classify_current_bytes_against_mint_sha",
    "classify_field_scoped_assets_evolution",
]
