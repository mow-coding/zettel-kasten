"""Private, append-only draft holds. A met condition never authorizes deletion.

The original draft and its creation/revision receipts are not rewritten. Read
operations do not create a directory. Each new event binds the current draft
bytes and the previous event; only the existing exact-approval broker can
authorize it. Old drafts need no migration before their first hold.
"""
from datetime import datetime, timezone
import hashlib
import json
import re
import stat
from pathlib import Path

from . import archive_services as services
from .exact_human_approval import _ClaimedExactHumanApproval, exact_human_approval_archive_identity_sha256
from .exact_human_approval_windows import ExactHumanApprovalContext, ExactHumanApprovalOperation
from .exact_operation_manifest import _ensure_private_directory, _read_plain_file
from .operation_target_leases import TargetLeases

REQUEST_SCHEMA = "wom-kit/draft-disposition-request/v1"
EVENT_SCHEMA = "wom-kit/draft-disposition-event/v1"
ROOT_PARTS = ("profiles", "local", "draft-dispositions")
MAX_BYTES = 1024 * 1024
MAX_EVENTS = 10000


def _error(code):
    return services.ArchiveServiceError(code)


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _sha(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _target(root, zettel_id=None, relative_path=None):
    if bool(zettel_id) == bool(relative_path):
        raise _error("draft_disposition_target_required")
    try:
        path = services.resolve_inbox_draft_path(root, zettel_id, relative_path)
    except services.ArchiveServiceError:
        raise _error("draft_disposition_target_unavailable") from None
    raw, reason = services._bounded_stable_regular_file_read(path, max_bytes=64 * 1024 * 1024)
    if raw is None or reason:
        raise _error("draft_disposition_target_unreadable")
    try:
        boundary = services.parse_approval_zettel_content_boundary(raw.decode("utf-8-sig"))
        metadata = boundary["frontmatter"]
        identity = metadata["id"]
        if metadata.get("status") != "draft" or not isinstance(identity, str) or not identity:
            raise ValueError()
    except (UnicodeError, ValueError, KeyError, TypeError):
        raise _error("draft_disposition_target_not_draft") from None
    return path, identity, _sha(raw)


def _folder(root, identity, create=False):
    parts = (*ROOT_PARTS, hashlib.sha256(identity.encode("utf-8")).hexdigest())
    if create:
        return _ensure_private_directory(root, parts)
    path = root
    for part in parts:
        path /= part
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if path.is_symlink() or not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise _error("draft_disposition_path_unsafe")
    return path


def _events(root, identity):
    folder = _folder(root, identity)
    if not folder.exists():
        return []
    names = sorted(folder.iterdir(), key=lambda path: path.name)
    if len(names) > MAX_EVENTS:
        raise _error("draft_disposition_history_limit_exceeded")
    events, previous = [], None
    for number, path in enumerate(names, 1):
        if path.name != f"{number:08d}.json":
            raise _error("draft_disposition_history_invalid")
        try:
            document = json.loads(_read_plain_file(path, max_bytes=MAX_BYTES, heartbeat=lambda: None))
            digest = document.pop("event_sha256")
            if (document["schema"] != EVENT_SCHEMA or document["zettel_id"] != identity
                    or document["archive_id"] != services.read_archive_id(root)
                    or document["sequence"] != number or document["previous_event_sha256"] != previous
                    or _sha(_canonical(document)) != digest):
                raise ValueError()
            document["event_sha256"] = digest
        except (ValueError, KeyError, TypeError):
            raise _error("draft_disposition_history_invalid") from None
        previous = digest
        events.append(document)
    return events


def _text(value, code, maximum=2000):
    if type(value) is not str or not value.strip() or len(value.encode("utf-8")) > maximum or "\0" in value:
        raise _error(code)
    return value.strip()


def _request(value):
    allowed = {"schema", "action", "zettel_id", "relative_path", "reason", "conditions",
               "intended_next_action", "expected_previous_event_sha256"}
    if type(value) is not dict or set(value) - allowed or value.get("schema") != REQUEST_SCHEMA:
        raise _error("draft_disposition_request_invalid")
    result = dict(value)
    if type(result.get("action")) is not str or result["action"] not in {"hold", "review", "release"}:
        raise _error("draft_disposition_action_invalid")
    result["reason"] = _text(result.get("reason"), "draft_disposition_reason_required")
    if (type(result.get("intended_next_action")) is not str
            or result["intended_next_action"] not in {"revise", "publish", "discard"}):
        raise _error("draft_disposition_next_action_invalid")
    target_keys = set(result) & {"zettel_id", "relative_path"}
    if len(target_keys) != 1 or any(type(result[key]) is not str or not result[key] for key in target_keys):
        raise _error("draft_disposition_target_required")
    if "zettel_id" in result and not services.ZETTEL_EDGE_ZETTEL_ID_RE.fullmatch(result["zettel_id"]):
        raise _error("draft_disposition_target_required")
    previous = result.get("expected_previous_event_sha256")
    if previous is not None and (type(previous) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", previous)):
        raise _error("draft_disposition_previous_event_invalid")
    conditions = result.get("conditions", [])
    if type(conditions) is not list or len(conditions) > 100:
        raise _error("draft_disposition_conditions_invalid")
    seen, normalized = set(), []
    for condition in conditions:
        if (type(condition) is not dict or set(condition) - {"condition_id", "description", "state", "evidence_ref"}
                or type(condition.get("condition_id")) is not str
                or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", condition["condition_id"])
                or condition["condition_id"] in seen or type(condition.get("state")) is not str
                or condition["state"] not in {"unmet", "met", "unknown"}):
            raise _error("draft_disposition_conditions_invalid")
        row = dict(condition)
        row["description"] = _text(row.get("description"), "draft_disposition_conditions_invalid")
        if "evidence_ref" in row:
            row["evidence_ref"] = _text(row["evidence_ref"], "draft_disposition_evidence_invalid")
        if row["state"] == "met" and not row.get("evidence_ref"):
            raise _error("draft_disposition_met_condition_evidence_required")
        seen.add(row["condition_id"])
        normalized.append(row)
    if result["action"] == "hold" and not normalized:
        raise _error("draft_disposition_hold_conditions_required")
    result["conditions"] = normalized
    return result


def history(archive_root, *, zettel_id):
    """Preserve access to decisions after a separate mint/discard operation."""
    root = services.require_existing_archive_root(archive_root)
    if type(zettel_id) is not str or not services.ZETTEL_EDGE_ZETTEL_ID_RE.fullmatch(zettel_id):
        raise _error("draft_disposition_target_required")
    events = _events(root, zettel_id)
    return {"schema": "wom-kit/draft-disposition-history/v1", "ok": True, "read_only": True,
            "zettel_id": zettel_id, "event_count": len(events), "events": events,
            "current_document_status_checked": False, "conditions_are_delete_authority": False}


def inspect(archive_root, *, zettel_id=None, relative_path=None):
    root = services.require_existing_archive_root(archive_root)
    try:
        _path, identity, digest = _target(root, zettel_id, relative_path)
    except services.ArchiveServiceError as exc:
        if str(exc) != "draft_disposition_target_unavailable" or not zettel_id or relative_path:
            raise
        recorded = history(root, zettel_id=zettel_id)
        if not recorded["events"]:
            raise
        return {"schema": "wom-kit/draft-disposition-status/v1", "ok": True, "read_only": True,
                "state": "draft_not_currently_resolved_history_retained", "zettel_id": zettel_id,
                "draft_sha256": None, "event_count": recorded["event_count"], "latest": recorded["events"][-1],
                "final_disposition_inferred": False, "conditions_are_delete_authority": False,
                "draft_bytes_modified": False}
    events = _events(root, identity)
    latest = events[-1] if events else None
    changed = latest is not None and latest["draft_sha256"] != digest
    return {"schema": "wom-kit/draft-disposition-status/v1", "ok": True, "read_only": True,
            "state": "review_required_draft_changed" if changed else latest["state"] if latest else "unrecorded",
            "zettel_id": identity, "draft_sha256": digest, "event_count": len(events),
            "latest": latest, "conditions_are_delete_authority": False, "draft_bytes_modified": False}


def workflow_guidance(archive_root, *, zettel_id=None, relative_path=None):
    """Advisory read-only status attached to an existing workflow's result.

    An unreadable old ledger cannot undo a successful revision/mint/discard.
    Its uncertainty remains visible; it never becomes permission to act.
    """
    identity = (zettel_id if type(zettel_id) is str and services.ZETTEL_EDGE_ZETTEL_ID_RE.fullmatch(zettel_id) else None)
    try:
        root = services.require_existing_archive_root(archive_root)
        # Existing callers already have the identity. The common unrecorded
        # case needs no document body read or creation of private directories.
        if identity and relative_path is None and not _folder(root, identity).exists():
            status = {"ok": True, "read_only": True, "state": "unrecorded", "zettel_id": identity,
                      "event_count": 0, "latest": None, "draft_bytes_modified": False}
        else:
            status = inspect(root, zettel_id=zettel_id, relative_path=relative_path)
            identity = status.get("zettel_id") or identity
    except Exception as error:
        code = str(error)
        if not re.fullmatch(r"draft_disposition_[a-z_]+", code):
            code = "draft_disposition_status_unavailable"
        status = {"ok": False, "read_only": True, "state": "status_unavailable", "reason_code": code,
                  "draft_bytes_modified": False, "final_disposition_inferred": False}
    selector = "--zettel-id" if identity else "--path"
    selector_placeholder = "<zettel-id>" if identity else "<inbox-relative-path>"
    actions = [
        {"action": "revise_plan", "command": "draft-revision-plan", "selector_argument": "--draft",
         "required_arguments": ["archive_root", "--draft", "--proposal", "--dry-run"], "read_only": True,
         "command_template": "archive draft-revision-plan <archive-root> --draft <inbox-relative-path> --proposal <private-proposal> --dry-run"},
        {"action": "revise_write", "command": "draft-revision-write", "selector_argument": "--draft",
         "required_arguments": ["archive_root", "--draft", "--proposal", "--expected-plan-sha256", "--reviewed-by", "--approve"],
         "read_only": False, "fresh_plan_required": True,
         "command_template": "archive draft-revision-write <archive-root> --draft <inbox-relative-path> --proposal <private-proposal> --expected-plan-sha256 <current-plan-sha256> --reviewed-by <reviewer> --approve"},
        {"action": "quality_check", "command": "zet-quality-check", "selector_argument": selector,
         "required_arguments": ["archive_root", selector, "--dry-run"], "read_only": True,
         "command_template": f"archive zet-quality-check <archive-root> {selector} {selector_placeholder} --dry-run"},
        {"action": "publish_plan", "command": "mint-zet", "selector_argument": selector,
         "required_arguments": ["archive_root", selector, "--dry-run"], "read_only": True,
         "command_template": f"archive mint-zet <archive-root> {selector} {selector_placeholder} --dry-run"},
        {"action": "discard_plan", "command": "discard-draft", "selector_argument": selector,
         "required_arguments": ["archive_root", selector, "--reason", "--dry-run"], "read_only": True,
         "command_template": f"archive discard-draft <archive-root> {selector} {selector_placeholder} --reason <reviewed-reason> --dry-run"},
        {"action": "hold_history", "command": "draft-disposition", "selector_argument": "--zettel-id",
         "required_arguments": ["archive_root", "--history", "--zettel-id"], "read_only": True,
         "command_template": "archive draft-disposition <archive-root> --history --zettel-id <zettel-id>"},
    ]
    return {"schema": "wom-kit/draft-disposition-workflow-guidance/v1", "ok": status["ok"],
            "read_only": True, "disposition": status, "next_actions": actions,
            "conditions_are_publish_authority": False, "conditions_are_delete_authority": False,
            "automatic_action_performed": False, "approval_policy": "existing_session_mode",
            "workflow_result_is_unchanged": True, "private_paths_echoed": False}


def _prepare(archive_root, request):
    root = services.require_existing_archive_root(archive_root)
    value = _request(request)
    path, identity, draft_sha = _target(root, value.get("zettel_id"), value.get("relative_path"))
    events = _events(root, identity)
    previous = events[-1] if events else None
    previous_sha = previous["event_sha256"] if previous else None
    if "expected_previous_event_sha256" in value and value["expected_previous_event_sha256"] != previous_sha:
        raise _error("draft_disposition_previous_event_changed")
    if value["action"] in {"review", "release"} and previous is None:
        raise _error("draft_disposition_hold_missing")
    if previous and previous["state"] == "released" and value["action"] != "hold":
        raise _error("draft_disposition_already_released")
    state = ("released" if value["action"] == "release" else
             "ready_for_review" if value["conditions"] and all(row["state"] == "met" for row in value["conditions"])
             else "held_pending_review")
    material = {"schema": "wom-kit/draft-disposition-plan/v1", "archive_id": services.read_archive_id(root),
                "zettel_id": identity, "draft_sha256": draft_sha, "previous_event_sha256": previous_sha,
                "action": value["action"], "reason": value["reason"], "conditions": value["conditions"],
                "intended_next_action": value["intended_next_action"], "state": state, "sequence": len(events) + 1}
    return root, path, material


def plan(archive_root, request):
    _root, _path, material = _prepare(archive_root, request)
    return {"ok": True, "dry_run": True, "schema": material["schema"], "plan_sha256": _sha(_canonical(material)),
            "zettel_id": material["zettel_id"], "draft_sha256": material["draft_sha256"],
            "previous_event_sha256": material["previous_event_sha256"], "state": material["state"],
            "condition_count": len(material["conditions"]), "conditions_are_delete_authority": False,
            "draft_bytes_modified": False}


def _context(material, reviewer_claim):
    digest = _sha(_canonical(material))
    return ExactHumanApprovalContext(operation=ExactHumanApprovalOperation.draft_disposition,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(material["archive_id"]),
        plan_sha256=digest, target_binding_sha256=_sha(_canonical([material["zettel_id"], material["draft_sha256"], digest])),
        reviewer_claim=reviewer_claim, review_binding_codes=("disposition_only", "draft_content", "previous_disposition"))


def _resumed_material(root, value, identity, expected_plan_sha256, reviewer_claim):
    for event in _events(root, identity):
        if event["plan_sha256"] == expected_plan_sha256:
            material = {key: event[key] for key in (
                "archive_id", "zettel_id", "draft_sha256", "previous_event_sha256", "action", "reason",
                "conditions", "intended_next_action", "state", "sequence")}
            material["schema"] = "wom-kit/draft-disposition-plan/v1"
            if (event["reviewed_by"] != reviewer_claim or any(value[key] != material[key]
                    for key in ("action", "reason", "conditions", "intended_next_action"))
                    or "expected_previous_event_sha256" in value
                    and value["expected_previous_event_sha256"] != material["previous_event_sha256"]
                    or _sha(_canonical(material)) != expected_plan_sha256):
                raise _error("draft_disposition_resume_request_changed")
            return material, event
    return None


def approval_context(archive_root, request, *, reviewer_claim, expected_plan_sha256=None, resume=False):
    if resume:
        root = services.require_existing_archive_root(archive_root)
        value = _request(request)
        identity = value.get("zettel_id")
        if not identity:
            _path, identity, _draft_sha = _target(root, None, value.get("relative_path"))
        original = _resumed_material(root, value, identity, expected_plan_sha256, reviewer_claim)
        if original is not None:
            return _context(original[0], reviewer_claim)
    material = _prepare(archive_root, request)[2]
    if expected_plan_sha256 is not None and _sha(_canonical(material)) != expected_plan_sha256:
        raise _error("draft_disposition_plan_changed")
    return _context(material, reviewer_claim)


def _result(event, *, resumed=False):
    return {"schema": "wom-kit/draft-disposition-result/v1", "ok": True, "state": event["state"],
            "event_sha256": event["event_sha256"], "plan_sha256": event["plan_sha256"],
            "conditions_are_delete_authority": False, "draft_bytes_modified": False,
            "automatic_deletion": False, "independent_post_verification": True, "resumed": resumed}


def apply(archive_root, request, *, expected_plan_sha256, reviewer_claim, approval_claim, resume=False):
    if type(approval_claim) is not _ClaimedExactHumanApproval:
        raise _error("draft_disposition_exact_approval_required")
    root = services.require_existing_archive_root(archive_root)
    value = _request(request)
    if resume and value.get("zettel_id"):
        original = _resumed_material(root, value, value["zettel_id"], expected_plan_sha256, reviewer_claim)
        if original is not None:
            material, event = original
            context = _context(material, reviewer_claim)
            try:
                approval_claim.assert_ready_for_context(context)
            except Exception:
                approval_claim.assert_succeeded_for_context(context)
            return _result(event, resumed=True)
    _path, identity, _draft_sha = _target(root, value.get("zettel_id"), value.get("relative_path"))
    with TargetLeases(root, [("zet", identity)]):
        if resume:
            original = _resumed_material(root, value, identity, expected_plan_sha256, reviewer_claim)
            if original is not None:
                material, event = original
                context = _context(material, reviewer_claim)
                try:
                    approval_claim.assert_ready_for_context(context)
                except Exception:
                    approval_claim.assert_succeeded_for_context(context)
                return _result(event, resumed=True)
        root, _path, material = _prepare(root, request)
        if _sha(_canonical(material)) != expected_plan_sha256:
            raise _error("draft_disposition_plan_changed")
        approval = approval_claim.assert_ready_for_context(_context(material, reviewer_claim))
        event = {**material, "schema": EVENT_SCHEMA, "plan_sha256": expected_plan_sha256,
                 "reviewed_by": reviewer_claim, "approval_reference": approval,
                 "created_at": datetime.now(timezone.utc).isoformat(), "automatic_deletion": False}
        event["event_sha256"] = _sha(_canonical(event))
        folder = _folder(root, identity, create=True)
        target = folder / f"{material['sequence']:08d}.json"
        services._write_bytes_create_if_absent(target, _canonical(event) + b"\n")
        verified = _events(root, identity)
        if verified[-1] != event:
            raise _error("draft_disposition_post_verification_failed")
    return _result(event)
