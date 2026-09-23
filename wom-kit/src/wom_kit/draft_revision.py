"""Official same-identity revision of an unpublished zet.

The original creation receipt remains immutable. A before snapshot, an exact
proposal binding and an append-only revision receipt describe each new edit.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import archive_services as services
from .exact_human_approval_windows import ExactHumanApprovalOperation
from .operation_approval_binding import ExactOperationApprovalBinding
from .exact_operation_manifest import exact_operation_writer_lock

ROOT = "receipts/revisions/drafts"
MAX_BYTES = 8 * 1024 * 1024
MUTABLE = frozenset({"title", "abstract", "document_type", "audience", "parse_review", "quality_review", "correction_events"})


class DraftRevisionError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def _read(root, relative, *, zettel_id=None):
    path = services.archive_internal_path(root, relative)
    if services.objet_capture_path_chain_blockers(root, relative):
        raise DraftRevisionError("draft_revision_path_unsafe")
    snapshot = services.validated_approval_zettel_snapshot(path, max_bytes=MAX_BYTES,
        expected_zettel_id=zettel_id, expected_archive_id=services.read_archive_id(root), expected_status="draft")
    if not snapshot.get("ok"):
        raise DraftRevisionError("draft_revision_snapshot_invalid")
    return path, snapshot


def plan(root, *, draft, proposal, resume_plan_sha256=None):
    root = services.require_existing_archive_root(Path(root))
    draft_relative = services.normalize_archive_relative_path(draft)
    proposal_relative = services.normalize_archive_relative_path(proposal)
    if not draft_relative.startswith("inbox/") or draft_relative == proposal_relative:
        raise DraftRevisionError("draft_revision_unpublished_target_required")
    target, before = _read(root, draft_relative)
    zettel_id = before["frontmatter"]["id"]
    canonical = services.resolve_zet_revision_canonical_candidate(root, zettel_id)
    if canonical != target and canonical.is_file():
        raise DraftRevisionError("draft_revision_already_published")
    candidate, after = _read(root, proposal_relative, zettel_id=zettel_id)
    current_bytes = before["bytes"]
    if resume_plan_sha256:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", resume_plan_sha256):
            raise DraftRevisionError("draft_revision_plan_invalid")
        intent_path = services.archive_internal_path(root, ROOT + "/" + resume_plan_sha256[7:] + ".intent.json")
        try:
            intent = json.loads(intent_path.read_bytes())
            if intent["draft_path"] != draft_relative or intent["proposal_sha256"] != _sha(after["bytes"]):
                raise ValueError()
            _, saved = _read(root, intent["snapshot_path"], zettel_id=before["frontmatter"]["id"])
            if _sha(saved["bytes"]) != intent["before_sha256"] or current_bytes not in (saved["bytes"], after["bytes"]):
                raise ValueError()
            before = saved
        except (OSError, ValueError, KeyError):
            raise DraftRevisionError("draft_revision_resume_changed") from None
    immutable_before = {k: v for k, v in before["frontmatter"].items() if k not in MUTABLE}
    immutable_after = {k: v for k, v in after["frontmatter"].items() if k not in MUTABLE}
    blockers = []
    if immutable_before != immutable_after:
        blockers.append("draft_revision_identity_or_links_changed")
    # Existing inline objet references are connections too, even when they are
    # absent from frontmatter. Added references still undergo fidelity checks.
    references = lambda body: set(re.findall(r"objet:sha256:[0-9a-f]{64}", body))
    if not references(before["body"]).issubset(references(after["body"])):
        blockers.append("draft_revision_existing_object_connection_removed")
    fidelity = services._source_fidelity_verify_for_mint(root, target, affirmations=None, _candidate_path=candidate)
    blockers.extend(fidelity.get("blockers") or [])
    quality = services.zettel_quality_assessment(root, target, after["frontmatter"], after["body"])
    if quality.get("blocker_count"):
        blockers.append("draft_revision_quality_blocked")
    material = {"schema": "wom-kit/draft-revision-plan/v1", "archive_id": services.read_archive_id(root),
        "draft_path": draft_relative, "proposal_path": proposal_relative,
        "zettel_id": before["frontmatter"]["id"], "before_sha256": _sha(before["bytes"]),
        "proposal_sha256": _sha(after["bytes"]), "fidelity_plan_sha256": fidelity.get("current_plan_sha256")}
    digest = _sha(_encoded(material))
    if resume_plan_sha256 and digest != resume_plan_sha256:
        blockers.append("draft_revision_resume_changed")
    public = {"schema": material["schema"], "ok": not blockers, "dry_run": True,
        "lifecycle_action": "draft_revision_write", "plan_sha256": digest,
        "target_binding_sha256": _sha(_encoded({"draft": draft_relative, "before": material["before_sha256"]})),
        "before_sha256": material["before_sha256"], "proposal_sha256": material["proposal_sha256"],
        "blockers": sorted(set(blockers)), "quality_check": quality,
        "source_fidelity_verified": fidelity.get("ok") is True, "auto_publish": False,
        "next_safe_actions": ["Run draft-revision-write with the exact plan, then zet-quality-check and mint separately."],
        "private_values_echoed": False}
    # Existing quality service includes archive-relative note identity; private
    # draft planning exposes counts/explanations only in the public projection.
    public["quality_check"] = {k: quality[k] for k in ("ok", "quality_state", "blocker_count", "warning_count", "warning_explanations")}
    return {"public": public, "material": material, "root": root, "target": target,
            "before_bytes": before["bytes"], "after_bytes": after["bytes"]}


def approval_binding(candidate):
    doc = candidate["public"]
    if not doc["ok"]:
        raise DraftRevisionError("draft_revision_preflight_blocked")
    return ExactOperationApprovalBinding(operation=ExactHumanApprovalOperation.draft_revision_write,
        plan_sha256=doc["plan_sha256"], target_binding_sha256=doc["target_binding_sha256"],
        warning_codes=(), review_binding_codes=("draft_revision_before_snapshot", "draft_revision_same_identity"))


def write(root, *, draft, proposal, expected_plan_sha256, reviewer, claim, binding, resume=False):
    from .object_storage_offload import _create_or_match_document
    root = services.require_existing_archive_root(Path(root))
    with exact_operation_writer_lock(root):
        fresh = plan(root, draft=draft, proposal=proposal,
            resume_plan_sha256=expected_plan_sha256 if resume else None)
        public, material = fresh["public"], fresh["material"]
        if not public["ok"] or public["plan_sha256"] != expected_plan_sha256:
            raise DraftRevisionError("draft_revision_plan_changed")
        approval = services._require_exact_human_operation_approval(root, approval_binding(fresh),
            reviewer_claim=reviewer, expected_plan_sha256=binding.plan_sha256,
            expected_target_binding_sha256=binding.target_binding_sha256, claim=claim)
        digest = expected_plan_sha256[7:]
        snapshot_path = ROOT + "/snapshots/" + material["before_sha256"][7:] + ".md"
        intent = {**material, "snapshot_path": snapshot_path, "approval": claim.public_reference()}
        _create_or_match_document(root, snapshot_path, fresh["before_bytes"], failure_code="object_storage_offload_receipt_conflict", max_bytes=MAX_BYTES)
        _create_or_match_document(root, ROOT + "/" + digest + ".intent.json", _encoded(intent), failure_code="object_storage_offload_receipt_conflict")
        # Exact bytes checked through a retained native handle; a replaced target
        # or mismatched recovery residue never gets overwritten.
        services._replace_regular_file_bytes_compare_and_swap(root, fresh["target"],
            expected_bytes=fresh["before_bytes"], replacement_bytes=fresh["after_bytes"],
            transaction_sha256=expected_plan_sha256, swap_suffix=".draft-revision.swap",
            max_bytes=MAX_BYTES, error_prefix="draft_revision", allow_already_replacement=resume)
        receipt = {"schema": "wom-kit/draft-revision-receipt/v1", "action": "draft_revision_write",
            "status": "applied", **material, "snapshot": {"path": snapshot_path, "sha256": material["before_sha256"]},
            "after": {"file_sha256": material["proposal_sha256"]},
            "exact_human_approval": approval, "creation_receipt_overwritten": False,
            "quality_check": public["quality_check"], "auto_publish": False}
        receipt["schema"] = "wom-kit/draft-revision-receipt/v1"
        receipt_path = ROOT + "/" + digest + ".revision.json"
        existing = services.archive_internal_path(root, receipt_path)
        if existing.exists():
            previous = json.loads(existing.read_bytes())
            if any(previous.get(k) != receipt[k] for k in (*material, "schema", "action", "status", "snapshot", "after", "auto_publish", "creation_receipt_overwritten")):
                raise DraftRevisionError("draft_revision_receipt_conflict")
        else:
            _create_or_match_document(root, receipt_path, _encoded(receipt), failure_code="object_storage_offload_receipt_conflict")
        services.index_archive(root)
        return {**public, "dry_run": False, "state": "draft_revised", "writes_performed": True,
                "before_snapshot_preserved": True, "revision_receipt_written": True, "revision_receipt_path": receipt_path,
                "creation_receipt_overwritten": False, "auto_publish": False}
