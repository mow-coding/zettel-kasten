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
    "promote_zet_approval_binding",
    "retire_draft_approval_binding",
    "warning_override_approval_binding",
    "zettel_edge_approval_binding",
    "zettel_objet_link_approval_binding",
]
