"""Deterministic, content-free exact-human bindings for legacy writers.

The affected writers already construct comprehensive dry-run plans.  This
module turns those plans into one stable plan digest and one target-set digest
without reflecting their private values into the dialog, result, or log.  The
same derivation is run once before the dialog and again inside each writer
immediately before mutation; any drift fails closed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .exact_operation_manifest import ExactOperationManifest
from .exact_human_approval import (
    REFERENCE_SCHEMA_VERSION,
    exact_human_approval_archive_identity_sha256,
    exact_human_approval_context_sha256,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
    exact_human_approval_warning_codes,
)


BINDING_SCHEMA_VERSION = "wom-kit/operation-exact-human-approval-plan/v0.1"
_SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_WARNING_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ZETTEL_OBJET_ROLE_RE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_ZETTEL_OBJET_LINK_ID_RE = re.compile(r"^asset:sha256:[0-9a-f]{64}$")
_ZETTEL_OBJET_CONTROL_SHA256 = "sha256:" + hashlib.sha256(
    b"wom-kit/zettel-objet-link-lock/v0.1\n"
).hexdigest()
_APPROVAL_ID_RE = re.compile(r"^approval_[0-9a-f]{32}$")
_STABLE_VERSION_TAG_RE = re.compile(
    r"^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$"
)
_STABLE_VERSION_RE = re.compile(
    r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$"
)
_RUNTIME_DISTRIBUTION_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,126}[A-Za-z0-9])?$"
)
_RUNTIME_WHEEL_FILE_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}\.whl$"
)
_RUNTIME_SUPPLY_ARTIFACT_KEYS = frozenset(
    {
        "role",
        "distribution",
        "version",
        "file_name",
        "size_bytes",
        "sha256",
        "source_kind",
        "download_url_echoed",
    }
)
_RUNTIME_PREPARED_ARTIFACT_KEYS = frozenset(
    {
        "role",
        "distribution",
        "version",
        "file_name",
        "size_bytes",
        "sha256",
    }
)
_RUNTIME_CANDIDATE_KEYS = frozenset(
    {
        "schema",
        "status",
        "target_tag",
        "target_version",
        "target_commit",
        "transaction_ref",
        "candidate_locator",
        "seal_locator",
        "inventory_sha256",
        "candidate_sha256",
        "inventory_count",
        "inventory_bytes",
        "receipt_sha256",
        "wheel_file_name",
        "wheel_sha256",
        "supply_lock_sha256",
        "artifact_inventory",
        "installed_payload_sha256",
        "python_version",
        "verification",
        "existing_runtime_reusable",
        "complete_runtime_image",
        "network_complete",
        "toolchain_complete",
        "same_volume_verified",
        "runtime_parent_existed_before",
        "post_approval_child_process_allowed",
        "post_approval_network_allowed",
        "post_approval_copy_allowed",
        "marker_free_final_postimage",
        "reopenable_from_private_seal",
        "durability_barriers_complete",
        "cleanup_contract",
        "download_urls_echoed",
        "private_values_echoed",
        "absolute_paths_echoed",
    }
)
_RUNTIME_CANDIDATE_VERIFICATION_KEYS = frozenset(
    {
        "wheel_sha256",
        "pip_check",
        "version",
        "package_resources",
        "new_process",
        "supply_lock",
        "artifact_hashes",
        "artifact_sizes",
        "artifact_inventory",
        "installed_payload",
        "live_process",
    }
)
_PROJECT_UPDATE_APPROVAL_PREPARATION_KEYS = frozenset(
    {
        "lock_held",
        "network_complete",
        "post_approval_network_allowed",
        "target_ref_snapshot",
        "preapproval_control_writes_completed",
        "preapproval_domain_writes_completed",
        "fetched_refs_may_change",
        "preapproval_control_scaffold_created",
        "preapproval_persistent_domain_effect",
        "preapproval_runtime_content_installed",
        "preapproval_activation_changed",
        "runtime_postapproval_child_process_allowed",
        "project_update_postapproval_local_git_allowed",
        "postapproval_git_transport_allowed",
        "trusted_git_runner",
        "transaction",
        "runtime_candidate",
        "static_receipt",
    }
)
_PROJECT_UPDATE_TRANSACTION_KEYS = frozenset(
    {
        "schema",
        "transaction_ref",
        "transaction_logical_ref",
        "intent_sha256",
        "lock_backlinked",
        "directory_fsync_required",
        "static_receipt_domain_plan_sha256",
        "static_receipt_domain_target_binding_sha256",
    }
)
_PROJECT_UPDATE_STATIC_RECEIPT_KEYS = frozenset(
    {
        "schema",
        "logical_path",
        "sha256",
        "domain_plan_sha256",
        "domain_target_binding_sha256",
        "dynamic_claim_fields_embedded",
        "deterministic_one_pass_construction",
    }
)
_PROJECT_UPDATE_TRUSTED_GIT_RUNNER_KEYS = frozenset(
    {
        "schema",
        "runner_sha256",
        "executable_sha256",
        "size_bytes",
        "phase",
        "absolute_path_echoed",
        "path_lookup_after_resolution",
        "executable_handle_held",
        "postapproval_transport_allowed",
    }
)
_MAX_CANONICAL_BYTES = 16 * 1024 * 1024
OPERATION_RECEIPT_SCHEMA_VERSION = "wom-kit/operation-exact-human-approval/v0.1"


class OperationApprovalBindingError(RuntimeError):
    _CODES = {
        "operation_approval_plan_invalid",
        "operation_approval_plan_blocked",
        "operation_approval_binding_mismatch",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "operation_approval_plan_invalid"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"OperationApprovalBindingError({self.code!r})"


def _fail(code: str) -> OperationApprovalBindingError:
    return OperationApprovalBindingError(code)


def _canonical(value: Any) -> bytes:
    try:
        raw = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("operation_approval_plan_invalid") from None
    if len(raw) > _MAX_CANONICAL_BYTES:
        raise _fail("operation_approval_plan_invalid")
    return raw


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _service_jsonl_sha256(value: Any) -> str:
    """Reproduce completion-workflow canonical JSONL digests for safe fields."""

    try:
        raw = (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("operation_approval_plan_invalid") from None
    if len(raw) > _MAX_CANONICAL_BYTES:
        raise _fail("operation_approval_plan_invalid")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _plain_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail("operation_approval_plan_invalid")
    return dict(value)


def _sha_ref(value: Any) -> str:
    text = str(value or "").strip().lower()
    if _SHA256_RE.fullmatch(text) is None:
        raise _fail("operation_approval_plan_invalid")
    return text if text.startswith("sha256:") else "sha256:" + text


def _warning_codes(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    safe = {
        item
        for item in value
        if type(item) is str and _WARNING_CODE_RE.fullmatch(item) is not None
    }
    if any(type(item) is not str or item not in safe for item in value):
        safe.add("non_code_warning_present")
    return tuple(sorted(safe))[:32]


def _runtime_distribution_key(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).casefold()


def _runtime_artifact_row(
    value: Any,
    *,
    supply_summary: bool,
) -> dict[str, Any]:
    row = _plain_mapping(value)
    expected_keys = (
        _RUNTIME_SUPPLY_ARTIFACT_KEYS
        if supply_summary
        else _RUNTIME_PREPARED_ARTIFACT_KEYS
    )
    role = row.get("role")
    distribution = row.get("distribution")
    version = row.get("version")
    file_name = row.get("file_name")
    size_bytes = row.get("size_bytes")
    sha256 = row.get("sha256")
    if (
        set(row) != expected_keys
        or role not in ({"dependency"} if supply_summary else {"runtime", "dependency"})
        or type(distribution) is not str
        or _RUNTIME_DISTRIBUTION_RE.fullmatch(distribution) is None
        or type(version) is not str
        or _STABLE_VERSION_RE.fullmatch(version) is None
        or type(file_name) is not str
        or _RUNTIME_WHEEL_FILE_RE.fullmatch(file_name) is None
        or type(size_bytes) is not int
        or not (1 <= size_bytes <= 128 * 1024 * 1024)
        or type(sha256) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", sha256) is None
        or (
            supply_summary
            and (
                row.get("source_kind") != "public_pypi_file"
                or row.get("download_url_echoed") is not False
            )
        )
    ):
        raise _fail("operation_approval_plan_invalid")
    return {
        "role": role,
        "distribution": distribution,
        "version": version,
        "file_name": file_name,
        "size_bytes": size_bytes,
        "sha256": sha256,
    }


def _runtime_supply_artifacts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not (1 <= len(value) <= 32):
        raise _fail("operation_approval_plan_invalid")
    normalized: list[dict[str, Any]] = []
    seen_distributions: set[str] = set()
    seen_files: set[str] = set()
    previous_sort_key: tuple[str, str, str] | None = None
    for value_row in value:
        row = _runtime_artifact_row(value_row, supply_summary=True)
        distribution_key = _runtime_distribution_key(row["distribution"])
        file_key = row["file_name"].casefold()
        sort_key = (distribution_key, row["version"], file_key)
        if (
            distribution_key in seen_distributions
            or file_key in seen_files
            or (previous_sort_key is not None and sort_key <= previous_sort_key)
        ):
            raise _fail("operation_approval_plan_invalid")
        seen_distributions.add(distribution_key)
        seen_files.add(file_key)
        previous_sort_key = sort_key
        normalized.append(row)
    return normalized


def _runtime_prepared_artifacts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not (2 <= len(value) <= 33):
        raise _fail("operation_approval_plan_invalid")
    normalized: list[dict[str, Any]] = []
    seen_distributions: set[str] = set()
    seen_files: set[str] = set()
    previous_sort_key: tuple[str, str] | None = None
    for value_row in value:
        row = _runtime_artifact_row(value_row, supply_summary=False)
        distribution_key = _runtime_distribution_key(row["distribution"])
        file_key = row["file_name"].casefold()
        sort_key = (file_key, row["file_name"])
        if (
            distribution_key in seen_distributions
            or file_key in seen_files
            or (previous_sort_key is not None and sort_key <= previous_sort_key)
        ):
            raise _fail("operation_approval_plan_invalid")
        seen_distributions.add(distribution_key)
        seen_files.add(file_key)
        previous_sort_key = sort_key
        normalized.append(row)
    return normalized


@dataclass(frozen=True)
class ExactOperationApprovalBinding:
    operation: ExactHumanApprovalOperation
    plan_sha256: str
    target_binding_sha256: str
    warning_codes: tuple[str, ...]
    review_binding_codes: tuple[str, ...]

    def context(
        self,
        *,
        archive_id: str,
        reviewer_claim: str,
    ) -> ExactHumanApprovalContext:
        return ExactHumanApprovalContext(
            operation=self.operation,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                archive_id
            ),
            plan_sha256=self.plan_sha256,
            target_binding_sha256=self.target_binding_sha256,
            reviewer_claim=reviewer_claim,
            review_binding_codes=self.review_binding_codes,
            warning_codes=self.warning_codes,
        )

    def public_document(self) -> dict[str, Any]:
        return {
            "schema_version": BINDING_SCHEMA_VERSION,
            "operation": self.operation.value,
            "plan_sha256": self.plan_sha256,
            "target_binding_sha256": self.target_binding_sha256,
            "warning_codes": list(self.warning_codes),
            "review_binding_codes": list(self.review_binding_codes),
            "private_values_echoed": False,
            "paths_echoed": False,
        }


def mint_zet_approval_binding(
    dry_run: Mapping[str, Any],
) -> ExactOperationApprovalBinding:
    plan = _plain_mapping(dry_run)
    if plan.get("ok") is not True or plan.get("dry_run") is not True:
        raise _fail("operation_approval_plan_blocked")
    receipt = _plain_mapping(plan.get("receipt_preview"))
    source = _plain_mapping(receipt.get("source"))
    source_sha = _sha_ref(source.get("sha256"))
    checklist = plan.get("checklist")
    if not isinstance(checklist, list):
        raise _fail("operation_approval_plan_invalid")
    checklist_projection: list[dict[str, Any]] = []
    for item in checklist:
        row = _plain_mapping(item)
        item_id = row.get("id")
        status = row.get("status")
        if type(item_id) is not str or type(status) is not str:
            raise _fail("operation_approval_plan_invalid")
        checklist_projection.append({"id": item_id, "status": status})
    scratch_cleanup = _plain_mapping(plan.get("scratch_cleanup"))
    scratch_receipt_path = scratch_cleanup.get("receipt_path")
    volatile_scratch_receipt_write = (
        f"write {scratch_receipt_path}"
        if type(scratch_receipt_path) is str and scratch_receipt_path
        else None
    )

    def _without_volatile_scratch_receipt_locator(value: Any) -> Any:
        if not isinstance(value, list) or volatile_scratch_receipt_write is None:
            return value
        return [item for item in value if item != volatile_scratch_receipt_write]

    scratch_cleanup_projection = {
        key: scratch_cleanup.get(key)
        for key in (
            "blockers",
            "candidate_count",
            "candidates",
            "missing",
            "safe_to_cleanup",
            "scratch_reference_count",
            "would_change",
            "zettel_id",
            "zettel_path",
        )
    }
    scratch_cleanup_projection["would_change"] = (
        _without_volatile_scratch_receipt_locator(
            scratch_cleanup_projection.get("would_change")
        )
    )
    target = {
        "source_sha256": source_sha,
        "zettel_id_digest": _sha256(plan.get("zettel_id")),
        "proposed_paths_digest": _sha256(
            [
                plan.get("proposed_canonical_path"),
                plan.get("proposed_mint_receipt_path"),
                plan.get("proposed_draft_snapshot_path"),
            ]
        ),
    }
    basis = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "operation": "mint_zet",
        "source_sha256": source_sha,
        "target": target,
        "warnings": plan.get("warnings"),
        "checklist": checklist_projection,
        "near_duplicates_digest": _sha256(plan.get("near_duplicates")),
        "duplicate_check_digest": _sha256(plan.get("duplicate_check")),
        "first_read_check_digest": _sha256(plan.get("first_read_check")),
        "quality_check_digest": _sha256(plan.get("quality_check")),
        "self_contained_check_digest": _sha256(plan.get("self_contained_check")),
        "source_fidelity_digest": _sha256(plan.get("source_fidelity")),
        # The eventual cleanup receipt filename contains a fresh timestamp and
        # cannot be predicted across the approval dialog.  Bind every cleanup
        # candidate and policy fact, but not that post-mint receipt locator.
        "scratch_cleanup_digest": _sha256(scratch_cleanup_projection),
        "receipt_preview_digest": _sha256(receipt),
        "would_change_digest": _sha256(
            _without_volatile_scratch_receipt_locator(
                plan.get("would_change")
            )
        ),
    }
    return ExactOperationApprovalBinding(
        operation=ExactHumanApprovalOperation.mint_zet,
        plan_sha256=_sha256(basis),
        target_binding_sha256=_sha256(target),
        warning_codes=_warning_codes(plan.get("warnings")),
        review_binding_codes=(
            "checklist_codes",
            "draft_bytes_digest",
            "mint_target_set",
            "near_duplicate_evidence",
            "warning_codes",
        ),
    )


def _promotion_approval_binding(
    dry_run: Mapping[str, Any],
    *,
    operation: ExactHumanApprovalOperation,
    require_warnings: bool,
) -> ExactOperationApprovalBinding:
    """Bind one legacy promotion without exposing its private plan values."""

    plan = _plain_mapping(dry_run)
    if plan.get("ok") is not True or plan.get("dry_run") is not True:
        raise _fail("operation_approval_plan_blocked")

    warnings = plan.get("warnings")
    if (
        not isinstance(warnings, list)
        or any(type(item) is not str for item in warnings)
        or (require_warnings and not warnings)
    ):
        raise _fail("operation_approval_plan_invalid")

    receipt = _plain_mapping(plan.get("receipt_preview"))
    receipt_source = _plain_mapping(receipt.get("source"))
    receipt_target = _plain_mapping(receipt.get("target"))
    source_sha = _sha_ref(plan.get("source_sha256"))

    required_text = {
        "draft_path": plan.get("draft_path"),
        "proposed_canonical_path": plan.get("proposed_canonical_path"),
        "proposed_receipt_path": plan.get("proposed_receipt_path"),
        "zettel_id": plan.get("zettel_id"),
    }
    if any(
        type(value) is not str or not value.strip()
        for value in required_text.values()
    ):
        raise _fail("operation_approval_plan_invalid")
    if (
        receipt.get("action") != "promote_zettel"
        or receipt.get("dry_run") is not True
        or receipt.get("receipt_path") != required_text["proposed_receipt_path"]
        or receipt_source.get("path") != required_text["draft_path"]
        or _sha_ref(receipt_source.get("sha256")) != source_sha
        or receipt_target.get("path")
        != required_text["proposed_canonical_path"]
        or receipt.get("warnings") != warnings
        or receipt.get("blockers") != plan.get("blockers")
        or receipt.get("checklist") != plan.get("checklist")
        or receipt.get("near_duplicates") != plan.get("near_duplicates")
        or receipt.get("first_read_check") != plan.get("first_read_check")
        or receipt.get("abstract_review_basis")
        != plan.get("abstract_review_basis")
    ):
        raise _fail("operation_approval_plan_invalid")

    for field in ("checklist", "near_duplicates", "would_change"):
        if not isinstance(plan.get(field), list):
            raise _fail("operation_approval_plan_invalid")
    for field in ("duplicate_check", "first_read_check"):
        if not isinstance(plan.get(field), Mapping):
            raise _fail("operation_approval_plan_invalid")
    if plan.get("abstract_review_basis") is not None and not isinstance(
        plan.get("abstract_review_basis"), Mapping
    ):
        raise _fail("operation_approval_plan_invalid")

    target = {
        "source_sha256": source_sha,
        "draft_path_digest": _sha256(required_text["draft_path"]),
        "canonical_path_digest": _sha256(
            required_text["proposed_canonical_path"]
        ),
        "receipt_path_digest": _sha256(
            required_text["proposed_receipt_path"]
        ),
        "zettel_id_digest": _sha256(required_text["zettel_id"]),
    }
    basis = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "operation": operation.value,
        "target": target,
        "warning_set_digest": _sha256(warnings),
        "checklist_digest": _sha256(plan.get("checklist")),
        "near_duplicates_digest": _sha256(plan.get("near_duplicates")),
        "duplicate_check_digest": _sha256(plan.get("duplicate_check")),
        "first_read_check_digest": _sha256(plan.get("first_read_check")),
        "abstract_review_basis_digest": _sha256(
            plan.get("abstract_review_basis")
        ),
        "receipt_preview_digest": _sha256(receipt),
        "would_change_digest": _sha256(plan.get("would_change")),
    }
    return ExactOperationApprovalBinding(
        operation=operation,
        plan_sha256=_sha256(basis),
        target_binding_sha256=_sha256(target),
        warning_codes=exact_human_approval_warning_codes(warnings),
        review_binding_codes=(
            (
                "canonical_target_set",
                "draft_bytes_digest",
                "duplicate_evidence",
                "promotion_plan",
                "warning_set",
            )
            if warnings
            else (
                "canonical_target_set",
                "draft_bytes_digest",
                "duplicate_evidence",
                "promotion_plan",
            )
        ),
    )


def promote_zet_approval_binding(
    dry_run: Mapping[str, Any],
) -> ExactOperationApprovalBinding:
    return _promotion_approval_binding(
        dry_run,
        operation=ExactHumanApprovalOperation.promote_zet,
        require_warnings=False,
    )


def warning_override_approval_binding(
    dry_run: Mapping[str, Any],
) -> ExactOperationApprovalBinding:
    return _promotion_approval_binding(
        dry_run,
        operation=ExactHumanApprovalOperation.warning_override,
        require_warnings=True,
    )


def zettel_edge_approval_binding(
    dry_run: Mapping[str, Any],
) -> ExactOperationApprovalBinding:
    plan = _plain_mapping(dry_run)
    if plan.get("ok") is not True or plan.get("dry_run") is not True:
        raise _fail("operation_approval_plan_blocked")
    source = _plain_mapping(plan.get("source"))
    target = _plain_mapping(plan.get("target"))
    source_sha = _sha_ref(source.get("current_sha256"))
    if target.get("verified") is not True:
        raise _fail("operation_approval_plan_invalid")
    proposed_edge = _plain_mapping(plan.get("proposed_edge"))
    proposed_edge_projection = {
        key: proposed_edge.get(key)
        for key in ("type", "target", "visibility", "edge_id", "receipt")
    }
    target_projection = {
        "source_current_sha256": source_sha,
        "source_identity_digest": _sha256(source),
        "target_identity_digest": _sha256(target),
        "edge_id_digest": _sha256(plan.get("edge_id")),
        "receipt_target_digest": _sha256(plan.get("receipt_path")),
    }
    basis = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "operation": "zettel_edge",
        "target": target_projection,
        # Reviewer and timestamp provenance are written only after approval;
        # the dialog binds their authority through reviewer_claim instead of
        # trying to predict a clock value during dry-run.
        "proposed_edge_digest": _sha256(proposed_edge_projection),
        "entity_type_contract_digest": _sha256(plan.get("entity_type_contract")),
        "warnings": plan.get("warnings"),
        "would_change_digest": _sha256(plan.get("would_change")),
    }
    return ExactOperationApprovalBinding(
        operation=ExactHumanApprovalOperation.zettel_edge,
        plan_sha256=_sha256(basis),
        target_binding_sha256=_sha256(target_projection),
        warning_codes=_warning_codes(plan.get("warnings")),
        review_binding_codes=(
            "edge_contract",
            "edge_target_digest",
            "source_current_digest",
            "warning_codes",
        ),
    )


def zettel_edge_revert_approval_binding(
    dry_run: Mapping[str, Any],
) -> ExactOperationApprovalBinding:
    plan = _plain_mapping(dry_run)
    if (
        plan.get("ok") is not True
        or plan.get("dry_run") is not True
        or plan.get("lifecycle_action") != "zettel_edge_revert_plan"
    ):
        raise _fail("operation_approval_plan_blocked")
    source = _plain_mapping(plan.get("source"))
    edge = _plain_mapping(plan.get("edge"))
    source_sha = _sha_ref(source.get("current_sha256"))
    target_projection = {
        "source_current_sha256": source_sha,
        "source_identity_digest": _sha256(source),
        "edge_digest": _sha256(edge),
        "edge_receipt_digest": _sha256(plan.get("edge_receipt_path")),
        "revert_receipt_digest": _sha256(plan.get("revert_receipt_path")),
    }
    basis = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "operation": "zettel_edge_revert",
        "target": target_projection,
        "would_change_digest": _sha256(plan.get("would_change")),
        "warnings": plan.get("warnings"),
    }
    return ExactOperationApprovalBinding(
        operation=ExactHumanApprovalOperation.zettel_edge_revert,
        plan_sha256=_sha256(basis),
        target_binding_sha256=_sha256(target_projection),
        warning_codes=_warning_codes(plan.get("warnings")),
        review_binding_codes=(
            "edge_receipt_digest",
            "edge_target_digest",
            "source_current_digest",
        ),
    )


def objet_capture_approval_binding(
    dry_run: Mapping[str, Any],
    *,
    operation: ExactHumanApprovalOperation = (
        ExactHumanApprovalOperation.objet_capture
    ),
) -> ExactOperationApprovalBinding:
    if operation not in (
        ExactHumanApprovalOperation.objet_capture,
        ExactHumanApprovalOperation.objet_capture_batch,
    ):
        raise _fail("operation_approval_plan_invalid")
    plan = _plain_mapping(dry_run)
    if (
        plan.get("ok") is not True
        or plan.get("dry_run") is not True
        or plan.get("lifecycle_action") != "objet_capture_plan"
        or not isinstance(plan.get("items"), list)
        or not plan.get("items")
    ):
        raise _fail("operation_approval_plan_blocked")
    selection_sha = _sha_ref(plan.get("selection_manifest_sha256"))
    target_projection = {
        "selection_manifest_sha256": selection_sha,
        "items_digest": _sha256(plan.get("items")),
        "planned_writes_digest": _sha256(plan.get("planned_writes")),
        "summary_digest": _sha256(plan.get("summary")),
        "project_intake_context_digest": _sha256(
            plan.get("project_intake_context")
        ),
    }
    basis = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "operation": operation.value,
        "target": target_projection,
        "warnings": plan.get("warnings"),
    }
    return ExactOperationApprovalBinding(
        operation=operation,
        plan_sha256=_sha256(basis),
        target_binding_sha256=_sha256(target_projection),
        warning_codes=_warning_codes(plan.get("warnings")),
        review_binding_codes=(
            "capture_item_set",
            "capture_source_digests",
            "selection_manifest_digest",
        ),
    )


def zettel_objet_link_approval_binding(
    dry_run: Mapping[str, Any],
) -> ExactOperationApprovalBinding:
    """Bind one zettel-to-objet write and its complete support-effect set.

    The service plan intentionally exposes only content-free identifiers,
    digests, relative paths, counts, and state codes.  Paths and identifiers
    are reduced to digests again before the public binding is returned.
    """

    plan = _plain_mapping(dry_run)
    if plan.get("ok") is not True or plan.get("dry_run") is not True:
        raise _fail("operation_approval_plan_blocked")
    if (
        plan.get("state") != "ready"
        or plan.get("lifecycle_action") != "zettel_objet_link_plan"
        or plan.get("blockers") != []
    ):
        raise _fail("operation_approval_plan_invalid")

    warnings = plan.get("warnings")
    would_change = plan.get("would_change")
    if (
        not isinstance(warnings, list)
        or any(type(item) is not str for item in warnings)
        or not isinstance(would_change, list)
        or any(type(item) is not str for item in would_change)
    ):
        raise _fail("operation_approval_plan_invalid")

    summary = _plain_mapping(plan.get("summary"))
    data = _plain_mapping(plan.get("data"))
    required_text = {
        name: summary.get(name)
        for name in (
            "zettel_id",
            "zettel_path",
            "role",
            "link_id",
            "receipt_path",
            "snapshot_path",
            "snapshot_state",
            "transaction_sha256",
            "canonical_swap_path",
            "canonical_previous_path",
            "canonical_swap_state",
            "control_artifact_path",
            "control_artifact_state",
        )
    }
    if any(
        type(value) is not str or not value.strip()
        for value in required_text.values()
    ):
        raise _fail("operation_approval_plan_invalid")
    if _ZETTEL_OBJET_ROLE_RE.fullmatch(required_text["role"]) is None:
        raise _fail("operation_approval_plan_invalid")
    if _ZETTEL_OBJET_LINK_ID_RE.fullmatch(required_text["link_id"]) is None:
        raise _fail("operation_approval_plan_invalid")
    if required_text["snapshot_state"] not in {"absent", "existing_exact"}:
        raise _fail("operation_approval_plan_invalid")
    if required_text["canonical_swap_state"] != "absent":
        raise _fail("operation_approval_plan_invalid")
    if required_text["control_artifact_state"] not in {
        "absent",
        "existing_exact",
    }:
        raise _fail("operation_approval_plan_invalid")

    label_present = summary.get("label_present")
    if type(label_present) is not bool:
        raise _fail("operation_approval_plan_invalid")
    counts = {
        "current_asset_count": summary.get("current_asset_count"),
        "manifest_record_count": summary.get("manifest_record_count"),
        "receipt_generation": summary.get("receipt_generation"),
    }
    if (
        type(counts["current_asset_count"]) is not int
        or counts["current_asset_count"] < 0
        or type(counts["manifest_record_count"]) is not int
        or counts["manifest_record_count"] != 1
        or type(counts["receipt_generation"]) is not int
        or counts["receipt_generation"] < 1
    ):
        raise _fail("operation_approval_plan_invalid")
    if (
        data.get("manifest_record_set_complete") is not True
        or data.get("manifest_record_set_unique") is not True
    ):
        raise _fail("operation_approval_plan_invalid")

    zettel_sha256 = _sha_ref(summary.get("zettel_sha256"))
    object_id = _sha_ref(summary.get("object_id"))
    manifest_record_set_sha256 = _sha_ref(
        summary.get("manifest_record_set_sha256")
    )
    label_sha256 = _sha_ref(summary.get("label_sha256"))
    snapshot_sha256 = _sha_ref(summary.get("snapshot_sha256"))
    support_effect_set_sha256 = _sha_ref(
        summary.get("support_effect_set_sha256")
    )
    transaction_sha256 = _sha_ref(summary.get("transaction_sha256"))
    control_artifact_sha256 = _sha_ref(
        summary.get("control_artifact_sha256")
    )
    service_plan_sha256 = _sha_ref(summary.get("plan_sha256"))
    if not hmac.compare_digest(snapshot_sha256, zettel_sha256):
        raise _fail("operation_approval_plan_invalid")
    expected_control_path = (
        "receipts/objects/zettel-links/.locks/"
        + hashlib.sha256(required_text["zettel_id"].encode("utf-8")).hexdigest()
        + ".lock"
    )
    if (
        required_text["control_artifact_path"] != expected_control_path
        or not hmac.compare_digest(
            control_artifact_sha256,
            _ZETTEL_OBJET_CONTROL_SHA256,
        )
    ):
        raise _fail("operation_approval_plan_invalid")

    support_effect_set = _plain_mapping(data.get("support_effect_set"))
    if set(support_effect_set) != {
        "zettel",
        "snapshot",
        "receipt",
        "canonical_compare_and_swap",
    }:
        raise _fail("operation_approval_plan_invalid")
    zettel_effect = _plain_mapping(support_effect_set.get("zettel"))
    snapshot_effect = _plain_mapping(support_effect_set.get("snapshot"))
    receipt_effect = _plain_mapping(support_effect_set.get("receipt"))
    swap_effect = _plain_mapping(
        support_effect_set.get("canonical_compare_and_swap")
    )
    if (
        set(zettel_effect) != {"path", "before_sha256"}
        or set(snapshot_effect) != {"path", "state", "sha256"}
        or set(receipt_effect) != {"path", "generation"}
        or set(swap_effect)
        != {"transaction_sha256", "swap_path", "previous_path", "state"}
    ):
        raise _fail("operation_approval_plan_invalid")
    if (
        zettel_effect.get("path") != required_text["zettel_path"]
        or _sha_ref(zettel_effect.get("before_sha256")) != zettel_sha256
        or snapshot_effect.get("path") != required_text["snapshot_path"]
        or snapshot_effect.get("state") != required_text["snapshot_state"]
        or _sha_ref(snapshot_effect.get("sha256")) != snapshot_sha256
        or receipt_effect.get("path") != required_text["receipt_path"]
        or receipt_effect.get("generation") != counts["receipt_generation"]
        or _sha_ref(swap_effect.get("transaction_sha256"))
        != transaction_sha256
        or swap_effect.get("swap_path")
        != required_text["canonical_swap_path"]
        or swap_effect.get("previous_path")
        != required_text["canonical_previous_path"]
        or swap_effect.get("state") != required_text["canonical_swap_state"]
        or not hmac.compare_digest(
            _service_jsonl_sha256(support_effect_set),
            support_effect_set_sha256,
        )
    ):
        raise _fail("operation_approval_plan_invalid")

    control_artifact = _plain_mapping(data.get("control_artifact"))
    if set(control_artifact) != {"kind", "path", "state", "sha256"}:
        raise _fail("operation_approval_plan_invalid")
    if (
        control_artifact.get("kind") != "zettel_objet_link_lock"
        or control_artifact.get("path")
        != required_text["control_artifact_path"]
        or control_artifact.get("state")
        != required_text["control_artifact_state"]
        or _sha_ref(control_artifact.get("sha256"))
        != control_artifact_sha256
    ):
        raise _fail("operation_approval_plan_invalid")

    target = {
        "zettel_id_digest": _sha256(required_text["zettel_id"]),
        "zettel_path_digest": _sha256(required_text["zettel_path"]),
        "zettel_current_sha256": zettel_sha256,
        "current_asset_count": counts["current_asset_count"],
        "object_id": object_id,
        "manifest_record_count": counts["manifest_record_count"],
        "manifest_record_set_complete": True,
        "manifest_record_set_unique": True,
        "manifest_record_set_sha256": manifest_record_set_sha256,
        "role": required_text["role"],
        "label_present": label_present,
        "label_sha256": label_sha256,
        "link_id": required_text["link_id"],
        "receipt_path_digest": _sha256(required_text["receipt_path"]),
        "receipt_generation": counts["receipt_generation"],
        "snapshot_path_digest": _sha256(required_text["snapshot_path"]),
        "snapshot_state": required_text["snapshot_state"],
        "snapshot_sha256": snapshot_sha256,
        "support_effect_set_sha256": support_effect_set_sha256,
        "transaction_sha256": transaction_sha256,
        "canonical_swap_path_digest": _sha256(
            required_text["canonical_swap_path"]
        ),
        "canonical_previous_path_digest": _sha256(
            required_text["canonical_previous_path"]
        ),
        "canonical_swap_state": required_text["canonical_swap_state"],
        "control_artifact_path_digest": _sha256(
            required_text["control_artifact_path"]
        ),
        "control_artifact_state": required_text["control_artifact_state"],
        "control_artifact_sha256": control_artifact_sha256,
    }
    basis = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "operation": "zettel_objet_link",
        "service_plan_sha256": service_plan_sha256,
        "target": target,
        # Bind future content-free plan fields too, while keeping them out of
        # the returned public document.
        "summary_digest": _sha256(summary),
        "data_digest": _sha256(data),
        "warning_set_digest": _sha256(warnings),
        "would_change_digest": _sha256(would_change),
    }
    return ExactOperationApprovalBinding(
        operation=ExactHumanApprovalOperation.zettel_objet_link,
        plan_sha256=_sha256(basis),
        target_binding_sha256=_sha256(target),
        warning_codes=_warning_codes(warnings),
        review_binding_codes=(
            "control_artifact",
            "label_digest",
            "manifest_record_set",
            "support_effect_set",
            "warning_codes",
            "zettel_objet_target_set",
        ),
    )


def retire_draft_approval_binding(
    dry_run: Mapping[str, Any],
) -> ExactOperationApprovalBinding:
    plan = _plain_mapping(dry_run)
    if plan.get("ok") is not True or plan.get("dry_run") is not True:
        raise _fail("operation_approval_plan_blocked")
    receipt = _plain_mapping(plan.get("receipt_preview"))
    refs: dict[str, str] = {}
    for name in ("source", "target", "mint_receipt", "snapshot"):
        refs[name] = _sha_ref(_plain_mapping(receipt.get(name)).get("sha256"))
    target = {
        "reference_sha256": refs,
        "retire_receipt_digest": _sha256(plan.get("retire_receipt_path")),
        "zettel_id_digest": _sha256(plan.get("zettel_id")),
    }
    basis = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "operation": "retire_draft",
        "target": target,
        "warnings": plan.get("warnings"),
        "receipt_preview_digest": _sha256(receipt),
        "would_change_digest": _sha256(plan.get("would_change")),
    }
    return ExactOperationApprovalBinding(
        operation=ExactHumanApprovalOperation.retire_draft,
        plan_sha256=_sha256(basis),
        target_binding_sha256=_sha256(target),
        warning_codes=_warning_codes(plan.get("warnings")),
        review_binding_codes=(
            "canonical_digest",
            "draft_digest",
            "mint_receipt_digest",
            "snapshot_digest",
            "warning_codes",
        ),
    )


def exact_operation_manifest_approval_binding(
    manifest: ExactOperationManifest,
    *,
    operation: ExactHumanApprovalOperation,
    archive_id: str,
    warnings: Sequence[str] = (),
) -> ExactOperationApprovalBinding:
    """Adapt a domain-neutral manifest to the existing native approval broker.

    This helper deliberately creates no new approval authority.  It verifies
    that the manifest's operation and archive digest match the already selected
    native operation context, then reuses ``ExactOperationApprovalBinding`` and
    its one-use exact-human workflow unchanged.
    """

    if (
        type(manifest) is not ExactOperationManifest
        or type(operation) is not ExactHumanApprovalOperation
        or manifest.operation != operation.value
        or type(warnings) not in {tuple, list}
        or any(type(warning) is not str for warning in warnings)
    ):
        raise _fail("operation_approval_plan_invalid")
    try:
        archive_identity_sha256 = exact_human_approval_archive_identity_sha256(
            archive_id
        )
        warning_codes = exact_human_approval_warning_codes(list(warnings))
    except Exception:
        raise _fail("operation_approval_plan_invalid") from None
    if not hmac.compare_digest(
        manifest.archive_identity_sha256,
        archive_identity_sha256,
    ):
        raise _fail("operation_approval_binding_mismatch")
    return ExactOperationApprovalBinding(
        operation=operation,
        plan_sha256=manifest.manifest_sha256,
        target_binding_sha256=manifest.target_set_sha256,
        warning_codes=warning_codes,
        review_binding_codes=(
            "exact_operation_effect_set",
            "exact_operation_manifest",
            "exact_operation_source_set",
            "exact_operation_target_set",
        ),
    )


def project_version_update_approval_binding(
    dry_run: Mapping[str, Any],
) -> ExactOperationApprovalBinding:
    """Bind one lock-held, network-complete project update preparation."""

    plan = _plain_mapping(dry_run)
    if (
        plan.get("ok") is not True
        or plan.get("lifecycle_action") != "project_version_update"
        or plan.get("mode") != "approval_prepared"
        or plan.get("status") != "ready_for_approval"
    ):
        raise _fail("operation_approval_plan_blocked")
    target_plan = _plain_mapping(plan.get("target"))
    source = _plain_mapping(plan.get("source_mirror"))
    pins = _plain_mapping(plan.get("pins"))
    fetch = _plain_mapping(plan.get("fetch"))
    materialization = _plain_mapping(plan.get("materialization_preflight"))
    project_runtime = _plain_mapping(plan.get("project_runtime"))
    project_runtime_bootstrap = _plain_mapping(
        project_runtime.get("bootstrap")
    )
    project_runtime_supply = _plain_mapping(
        project_runtime.get("supply", {})
    )
    project_runtime_candidate = _plain_mapping(
        project_runtime.get("runtime_candidate", {})
    )
    preparation = _plain_mapping(plan.get("approval_preparation"))
    prepared_ref_snapshot = _plain_mapping(
        preparation.get("target_ref_snapshot")
    )
    trusted_git_runner = _plain_mapping(
        preparation.get("trusted_git_runner")
    )
    transaction = _plain_mapping(preparation.get("transaction"))
    runtime_candidate = _plain_mapping(
        preparation.get("runtime_candidate")
    )
    static_receipt = _plain_mapping(preparation.get("static_receipt"))
    write_boundary = _plain_mapping(plan.get("write_boundary"))
    target_tag = target_plan.get("tag")
    target_version = target_plan.get("version")
    head_before = target_plan.get("target_commit")
    source_head = source.get("head_commit_before")
    if (
        type(target_tag) is not str
        or _STABLE_VERSION_TAG_RE.fullmatch(target_tag) is None
        or type(target_version) is not str
        or _STABLE_VERSION_RE.fullmatch(target_version) is None
        or target_tag != f"v{target_version}"
        or type(source_head) is not str
        or re.fullmatch(r"[0-9a-f]{40,64}", source_head) is None
        or type(head_before) is not str
        or re.fullmatch(r"[0-9a-f]{40,64}", head_before) is None
        or target_plan.get("tag_available_locally") is not True
        or target_plan.get("annotated_tag_verified") is not True
        or target_plan.get("configured_origin_main_ancestry_verified") is not True
        or fetch.get("attempted") is not True
        or fetch.get("succeeded") is not True
        or fetch.get("git_transport_called") is not True
        or fetch.get("phase") != "before_native_approval"
        or write_boundary.get("checkpointed_change_detection") is not True
        or write_boundary.get("external_writer_quiescence_required") is not True
        or write_boundary.get("preapproval_control_writes_completed") is not True
        or write_boundary.get("preapproval_domain_writes_completed") is not False
        or write_boundary.get("fetched_refs_may_change") is not True
        or write_boundary.get("post_approval_network_allowed") is not False
        or write_boundary.get("project_update_lock_acquired") is not True
        or write_boundary.get("preapproval_control_scaffold_created")
        is not preparation.get("preapproval_control_scaffold_created")
        or write_boundary.get("preapproval_persistent_domain_effect") is not False
        or write_boundary.get("preapproval_runtime_content_installed") is not False
        or write_boundary.get("preapproval_activation_changed") is not False
        or write_boundary.get("runtime_postapproval_child_process_allowed")
        is not False
        or write_boundary.get("project_update_postapproval_local_git_allowed")
        is not True
        or write_boundary.get("postapproval_git_transport_allowed") is not False
        or set(preparation) != _PROJECT_UPDATE_APPROVAL_PREPARATION_KEYS
        or preparation.get("lock_held") is not True
        or preparation.get("network_complete") is not True
        or preparation.get("post_approval_network_allowed") is not False
        or preparation.get("preapproval_control_writes_completed") is not True
        or preparation.get("preapproval_domain_writes_completed") is not False
        or preparation.get("fetched_refs_may_change") is not True
        or type(preparation.get("preapproval_control_scaffold_created")) is not bool
        or preparation.get("preapproval_persistent_domain_effect") is not False
        or preparation.get("preapproval_runtime_content_installed") is not False
        or preparation.get("preapproval_activation_changed") is not False
        or preparation.get("runtime_postapproval_child_process_allowed") is not False
        or preparation.get("project_update_postapproval_local_git_allowed") is not True
        or preparation.get("postapproval_git_transport_allowed") is not False
        or set(trusted_git_runner)
        != _PROJECT_UPDATE_TRUSTED_GIT_RUNNER_KEYS
        or trusted_git_runner.get("schema")
        != "wom-kit/project-update-trusted-git-runner/v0.4.3"
        or type(trusted_git_runner.get("runner_sha256")) is not str
        or re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            trusted_git_runner["runner_sha256"],
        )
        is None
        or type(trusted_git_runner.get("executable_sha256")) is not str
        or re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            trusted_git_runner["executable_sha256"],
        )
        is None
        or type(trusted_git_runner.get("size_bytes")) is not int
        or not 1 <= trusted_git_runner["size_bytes"] <= 256 * 1024 * 1024
        or trusted_git_runner.get("phase") != "local_only"
        or trusted_git_runner.get("absolute_path_echoed") is not False
        or trusted_git_runner.get("path_lookup_after_resolution") is not False
        or trusted_git_runner.get("executable_handle_held") is not True
        or trusted_git_runner.get("postapproval_transport_allowed") is not False
        or set(prepared_ref_snapshot)
        != {"tag_object", "target_commit", "origin_main"}
        or any(
            type(prepared_ref_snapshot.get(key)) is not str
            or re.fullmatch(
                r"[0-9a-f]{40,64}",
                prepared_ref_snapshot[key],
            )
            is None
            for key in ("tag_object", "target_commit", "origin_main")
        )
        or prepared_ref_snapshot.get("target_commit") != head_before
        or set(transaction) != _PROJECT_UPDATE_TRANSACTION_KEYS
        or transaction.get("schema")
        != "wom-kit/project-update-transaction-public-summary/v0.4.3"
        or re.fullmatch(
            r"update_[0-9a-f]{32}",
            str(transaction.get("transaction_ref") or ""),
        )
        is None
        or transaction.get("transaction_logical_ref")
        != (
            ".zettel-kasten/private/version-updates/"
            + str(transaction.get("transaction_ref"))
        )
        or any(
            re.fullmatch(r"sha256:[0-9a-f]{64}", str(transaction.get(key) or ""))
            is None
            for key in (
                "intent_sha256",
                "static_receipt_domain_plan_sha256",
                "static_receipt_domain_target_binding_sha256",
            )
        )
        or transaction.get("lock_backlinked") is not True
        or transaction.get("directory_fsync_required") is not True
        or set(static_receipt) != _PROJECT_UPDATE_STATIC_RECEIPT_KEYS
        or static_receipt.get("schema")
        != "wom-kit/project-version-update-receipt/v0.3"
        or static_receipt.get("logical_path")
        != (
            ".zettel-kasten/receipts/version-updates/"
            + str(transaction.get("transaction_ref"))
            + ".json"
        )
        or any(
            re.fullmatch(r"sha256:[0-9a-f]{64}", str(static_receipt.get(key) or ""))
            is None
            for key in (
                "sha256",
                "domain_plan_sha256",
                "domain_target_binding_sha256",
            )
        )
        or static_receipt.get("dynamic_claim_fields_embedded") is not False
        or static_receipt.get("deterministic_one_pass_construction") is not True
        or static_receipt.get("domain_plan_sha256")
        != transaction.get("static_receipt_domain_plan_sha256")
        or static_receipt.get("domain_target_binding_sha256")
        != transaction.get("static_receipt_domain_target_binding_sha256")
        or materialization.get("evaluated") is not True
        or materialization.get("safe") is not True
        or materialization.get("bounded") is not True
        or materialization.get("no_write") is not True
        or materialization.get("state") not in {"ready", "not_required"}
        or not isinstance(pins.get("planned"), list)
        or project_runtime.get("required") is not True
        or project_runtime.get("policy_state") != "required"
        or "prepared_bundle" in project_runtime
        or runtime_candidate != project_runtime_candidate
    ):
        raise _fail("operation_approval_plan_invalid")
    if project_runtime.get("required") is True:
        wheel_sha256 = project_runtime_bootstrap.get("wheel_sha256")
        policy = _plain_mapping(project_runtime.get("policy"))
        supply_interpreter = _plain_mapping(
            project_runtime_supply.get("interpreter")
        )
        supply_lock_sha256 = project_runtime_supply.get("lock_sha256")
        prepared_artifacts = runtime_candidate.get(
            "artifact_inventory"
        )
        supply_artifacts = _runtime_supply_artifacts(
            project_runtime_supply.get("artifacts")
        )
        normalized_prepared_artifacts = _runtime_prepared_artifacts(
            prepared_artifacts
        )
        candidate_verification = _plain_mapping(
            runtime_candidate.get("verification")
        )
        runtime_artifacts = [
            item
            for item in normalized_prepared_artifacts
            if item["role"] == "runtime"
        ]
        dependency_artifacts = [
            item
            for item in normalized_prepared_artifacts
            if item["role"] == "dependency"
        ]
        expected_prepared_artifacts = (
            [dict(runtime_artifacts[0]), *supply_artifacts]
            if len(runtime_artifacts) == 1
            else []
        )
        expected_prepared_artifacts.sort(
            key=lambda item: (
                str(item["file_name"]).casefold(),
                str(item["file_name"]),
            )
        )
        if (
            project_runtime.get("policy_state") != "required"
            or set(policy)
            != {
                "state",
                "required",
                "schema",
                "policy_sha256",
                "source_path",
                "supply_lock_path",
                "supply_lock_sha256",
            }
            or policy.get("state") != "required"
            or policy.get("required") is not True
            or policy.get("schema")
            != "wom-kit/project-runtime-policy/v0.1"
            or policy.get("source_path")
            != "wom-kit/project-runtime-policy.json"
            or type(policy.get("supply_lock_path")) is not str
            or not str(policy["supply_lock_path"]).startswith("wom-kit/")
            or ".." in str(policy["supply_lock_path"]).split("/")
            or project_runtime_bootstrap.get("available") is not True
            or set(project_runtime_bootstrap)
            != {
                "available",
                "reason_code",
                "source_kind",
                "release_tag",
                "wheel_file_name",
                "wheel_sha256",
                "download_url_echoed",
            }
            or project_runtime_bootstrap.get("reason_code")
            != "exact_public_release_wheel_verified"
            or project_runtime_bootstrap.get("source_kind")
            != "public_github_release"
            or project_runtime_bootstrap.get("release_tag") != target_tag
            or type(project_runtime_bootstrap.get("wheel_file_name"))
            is not str
            or _RUNTIME_WHEEL_FILE_RE.fullmatch(
                project_runtime_bootstrap["wheel_file_name"]
            )
            is None
            or project_runtime_bootstrap.get("download_url_echoed") is not False
            or type(wheel_sha256) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", wheel_sha256) is None
            or type(policy.get("policy_sha256")) is not str
            or re.fullmatch(
                r"sha256:[0-9a-f]{64}",
                policy["policy_sha256"],
            )
            is None
            or type(supply_lock_sha256) is not str
            or re.fullmatch(
                r"sha256:[0-9a-f]{64}",
                supply_lock_sha256,
            )
            is None
            or policy.get("supply_lock_sha256") != supply_lock_sha256
            or set(project_runtime_supply)
            != {
                "schema",
                "target_tag",
                "lock_sha256",
                "interpreter",
                "artifacts",
                "index_resolution",
                "all_artifacts_hash_and_size_bound",
                "download_urls_echoed",
            }
            or project_runtime_supply.get("schema")
            != "wom-kit/project-runtime-supply-lock/v0.1"
            or project_runtime_supply.get("target_tag") != target_tag
            or set(supply_interpreter)
            != {
                "implementation",
                "python_version",
                "python_tag",
                "abi_tag",
                "platform_tag",
            }
            or supply_interpreter.get("implementation") != "cpython"
            or type(supply_interpreter.get("python_version")) is not str
            or re.fullmatch(
                r"[1-9][0-9]*\.[0-9]+",
                supply_interpreter["python_version"],
            )
            is None
            or type(supply_interpreter.get("python_tag")) is not str
            or re.fullmatch(
                r"cp[0-9]{2,3}",
                supply_interpreter["python_tag"],
            )
            is None
            or supply_interpreter.get("abi_tag")
            != supply_interpreter.get("python_tag")
            or supply_interpreter.get("python_tag")
            != "cp" + supply_interpreter["python_version"].replace(".", "")
            or supply_interpreter.get("platform_tag") != "win_amd64"
            or project_runtime_supply.get(
                "all_artifacts_hash_and_size_bound"
            )
            is not True
            or project_runtime_supply.get("index_resolution") is not False
            or project_runtime_supply.get("download_urls_echoed") is not False
            or set(runtime_candidate) != _RUNTIME_CANDIDATE_KEYS
            or runtime_candidate.get("schema")
            != "wom-kit/project-runtime-candidate/v0.1"
            or runtime_candidate.get("status") != "sealed"
            or runtime_candidate.get("target_tag") != target_tag
            or runtime_candidate.get("target_version") != target_version
            or runtime_candidate.get("target_commit") != head_before
            or runtime_candidate.get("transaction_ref")
            != transaction.get("transaction_ref")
            or runtime_candidate.get("candidate_locator")
            != transaction.get("transaction_logical_ref") + "/runtime-candidate"
            or runtime_candidate.get("seal_locator")
            != transaction.get("transaction_logical_ref")
            + "/runtime-candidate-seal.json"
            or any(
                re.fullmatch(
                    r"sha256:[0-9a-f]{64}",
                    str(runtime_candidate.get(key) or ""),
                )
                is None
                for key in (
                    "inventory_sha256",
                    "candidate_sha256",
                    "receipt_sha256",
                    "wheel_sha256",
                    "supply_lock_sha256",
                    "installed_payload_sha256",
                )
            )
            or type(runtime_candidate.get("inventory_count")) is not int
            or runtime_candidate["inventory_count"] < 1
            or type(runtime_candidate.get("inventory_bytes")) is not int
            or runtime_candidate["inventory_bytes"] < 1
            or runtime_candidate.get("wheel_file_name")
            != project_runtime_bootstrap.get("wheel_file_name")
            or runtime_candidate.get("wheel_sha256") != wheel_sha256
            or runtime_candidate.get("supply_lock_sha256")
            != supply_lock_sha256
            or not isinstance(prepared_artifacts, list)
            or not prepared_artifacts
            or len(runtime_artifacts) != 1
            or len(dependency_artifacts) != len(supply_artifacts)
            or runtime_artifacts[0].get("distribution") != "wom-kit"
            or runtime_artifacts[0].get("version") != target_version
            or runtime_artifacts[0].get("file_name")
            != project_runtime_bootstrap.get("wheel_file_name")
            or runtime_artifacts[0].get("sha256") != wheel_sha256
            or normalized_prepared_artifacts
            != expected_prepared_artifacts
            or type(runtime_candidate.get("python_version")) is not str
            or re.fullmatch(
                r"[1-9][0-9]*\.[0-9]+\.[0-9]+",
                runtime_candidate["python_version"],
            )
            is None
            or not runtime_candidate["python_version"].startswith(
                supply_interpreter["python_version"] + "."
            )
            or set(candidate_verification)
            != _RUNTIME_CANDIDATE_VERIFICATION_KEYS
            or any(value is not True for value in candidate_verification.values())
            or type(runtime_candidate.get("existing_runtime_reusable")) is not bool
            or runtime_candidate.get("complete_runtime_image") is not True
            or runtime_candidate.get("network_complete") is not True
            or runtime_candidate.get("toolchain_complete") is not True
            or runtime_candidate.get("same_volume_verified") is not True
            or type(runtime_candidate.get("runtime_parent_existed_before"))
            is not bool
            or preparation.get("preapproval_control_scaffold_created")
            is runtime_candidate.get("runtime_parent_existed_before")
            or runtime_candidate.get("post_approval_child_process_allowed")
            is not False
            or runtime_candidate.get("post_approval_network_allowed") is not False
            or runtime_candidate.get("post_approval_copy_allowed") is not False
            or runtime_candidate.get("marker_free_final_postimage") is not True
            or runtime_candidate.get("reopenable_from_private_seal") is not True
            or runtime_candidate.get("durability_barriers_complete") is not True
            or runtime_candidate.get("cleanup_contract")
            != "sealed_exact_tree_only"
            or runtime_candidate.get("download_urls_echoed") is not False
            or runtime_candidate.get("private_values_echoed") is not False
            or runtime_candidate.get("absolute_paths_echoed") is not False
            or project_runtime.get("project_runtime_argv")
            != [r".\.zettel-kasten\bin\archive.cmd"]
        ):
            raise _fail("operation_approval_plan_invalid")

    target = {
        "target_tag": target_tag,
        "target_version": target_plan.get("version"),
        "target_commit": head_before,
        "prepared_target_ref_snapshot_digest": _sha256(
            prepared_ref_snapshot
        ),
        "approval_preparation_digest": _sha256(preparation),
        "transaction_intent_sha256": transaction["intent_sha256"],
        "transaction_summary_digest": _sha256(transaction),
        "domain_plan_sha256": static_receipt["domain_plan_sha256"],
        "domain_target_binding_sha256": static_receipt[
            "domain_target_binding_sha256"
        ],
        "runtime_candidate_digest": _sha256(runtime_candidate),
        "trusted_git_runner_digest": _sha256(trusted_git_runner),
        "static_receipt_sha256": static_receipt["sha256"],
        "static_receipt_summary_digest": _sha256(static_receipt),
        "target_tag_available_locally": target_plan.get(
            "tag_available_locally"
        ),
        "source_head_commit_before": source_head,
        "source_mirror_path_digest": _sha256(source.get("path")),
        "pins_digest": _sha256(pins.get("planned")),
        "materialization_preflight_digest": _sha256(materialization),
        "project_runtime_digest": _sha256(project_runtime),
        "would_change_digest": _sha256(plan.get("would_change")),
    }
    basis = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "operation": "project_version_update",
        "target": target,
        # The prepared preview is already content-free.  Binding the complete
        # snapshot makes every current and future safe precondition part of the
        # one-use approval without copying it into the native dialog.
        "service_preview_digest": _sha256(
            {
                key: value
                for key, value in plan.items()
                if key != "exact_human_approval"
            }
        ),
    }
    return ExactOperationApprovalBinding(
        operation=ExactHumanApprovalOperation.project_version_update,
        plan_sha256=_sha256(basis),
        target_binding_sha256=_sha256(target),
        warning_codes=exact_human_approval_warning_codes(
            tuple(
                item
                for item in plan.get("warnings", [])
                if type(item) is str
            )
        ),
        review_binding_codes=(
            "external_writers_quiescent",
            "forward_only",
            "materialization_preflight",
            "preapproval_control_and_ref_effects",
            "project_runtime_candidate",
            "project_runtime_policy",
            "project_runtime_supply_lock",
            "project_runtime_wheel_sha256",
            "project_source_head",
            "project_update_domain_plan",
            "project_update_domain_target",
            "project_update_intent",
            "project_update_lock",
            "project_update_static_receipt",
            "project_update_transaction_durability",
            "recognized_version_pins",
            "remote_ref_snapshot",
            "target_release_commit",
            "target_release_tag",
            "trusted_git_runner",
        ),
    )


def assert_same_binding(
    current: ExactOperationApprovalBinding,
    *,
    expected_plan_sha256: str,
    expected_target_binding_sha256: str,
) -> None:
    if type(current) is not ExactOperationApprovalBinding:
        raise _fail("operation_approval_binding_mismatch")
    expected_plan = _sha_ref(expected_plan_sha256)
    expected_target = _sha_ref(expected_target_binding_sha256)
    if not (
        hmac.compare_digest(current.plan_sha256, expected_plan)
        and hmac.compare_digest(current.target_binding_sha256, expected_target)
    ):
        raise _fail("operation_approval_binding_mismatch")


def build_operation_exact_human_approval_receipt(
    binding: ExactOperationApprovalBinding,
    *,
    archive_id: str,
    reviewer_claim: str,
    exact_human_approval_reference: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the content-free claim reference against this exact binding.

    Claim authentication remains the responsibility of the one-use approval
    workflow.  The writer independently re-derives the approved plan and
    target binding, then this helper proves that the supplied reference names
    the same context before the operation receipt is written.
    """

    if type(binding) is not ExactOperationApprovalBinding or not isinstance(
        exact_human_approval_reference, Mapping
    ):
        raise _fail("operation_approval_binding_mismatch")
    reference = dict(exact_human_approval_reference)
    if set(reference) != {
        "schema_version",
        "approval_id",
        "context_sha256",
        "approval_authority_sha256",
        "one_use",
    }:
        raise _fail("operation_approval_binding_mismatch")
    if (
        reference.get("schema_version") != REFERENCE_SCHEMA_VERSION
        or _APPROVAL_ID_RE.fullmatch(str(reference.get("approval_id") or ""))
        is None
        or reference.get("one_use") is not True
    ):
        raise _fail("operation_approval_binding_mismatch")
    context_sha256 = _sha_ref(reference.get("context_sha256"))
    authority_sha256 = _sha_ref(reference.get("approval_authority_sha256"))
    expected_context_sha256 = exact_human_approval_context_sha256(
        binding.context(archive_id=archive_id, reviewer_claim=reviewer_claim)
    )
    if not hmac.compare_digest(context_sha256, expected_context_sha256):
        raise _fail("operation_approval_binding_mismatch")
    validated_reference = {
        "schema_version": REFERENCE_SCHEMA_VERSION,
        "approval_id": reference["approval_id"],
        "context_sha256": context_sha256,
        "approval_authority_sha256": authority_sha256,
        "one_use": True,
    }
    return {
        "schema_version": OPERATION_RECEIPT_SCHEMA_VERSION,
        "operation": binding.operation.value,
        "plan_sha256": binding.plan_sha256,
        "target_binding_sha256": binding.target_binding_sha256,
        "exact_human_approval": validated_reference,
    }


__all__ = [
    "BINDING_SCHEMA_VERSION",
    "OPERATION_RECEIPT_SCHEMA_VERSION",
    "ExactOperationApprovalBinding",
    "OperationApprovalBindingError",
    "assert_same_binding",
    "build_operation_exact_human_approval_receipt",
    "exact_operation_manifest_approval_binding",
    "mint_zet_approval_binding",
    "objet_capture_approval_binding",
    "promote_zet_approval_binding",
    "retire_draft_approval_binding",
    "warning_override_approval_binding",
    "zettel_edge_approval_binding",
    "zettel_edge_revert_approval_binding",
    "zettel_objet_link_approval_binding",
]
