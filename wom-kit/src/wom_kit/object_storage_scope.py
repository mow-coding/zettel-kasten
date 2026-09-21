"""Explicit storage selection, separate from permission to execute a writer.

The CLI defaults to the retained work-session selector. No selector or missing
provenance must ever expand to the whole archive. A reviewed object list is the
escape hatch for historical captures without session attribution.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
import os
import json
import hashlib
from pathlib import Path
import re
import stat

OID = re.compile(r"sha256:[0-9a-f]{64}\Z")
SESSION = re.compile(r"work_session_[0-9a-f]{32}\Z")


class ObjectStorageScopeError(ValueError):
    def __init__(self, code="object_storage_scope_invalid"):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ObjectScope:
    kind: str
    object_ids: tuple[str, ...] = ()
    session_ref: str | None = None
    shared_object_ids: tuple[str, ...] = ()

    def document(self):
        return {"kind": self.kind, "object_ids": list(self.object_ids),
                "session_ref": self.session_ref, "shared_object_ids": list(self.shared_object_ids)}

    @classmethod
    def from_document(cls, value):
        if not isinstance(value, dict) or set(value) != {"kind", "object_ids", "session_ref", "shared_object_ids"}:
            raise ObjectStorageScopeError()
        kind, ids, session, shared = (value[k] for k in ("kind", "object_ids", "session_ref", "shared_object_ids"))
        if (not isinstance(kind, str) or kind not in {"all_sessions", "object_list", "single_object", "captured_by_session"}
                or not isinstance(ids, list) or not isinstance(shared, list)
                or any(not isinstance(x, str) or not OID.fullmatch(x) for x in ids + shared)
                or ids != sorted(set(ids)) or shared != sorted(set(shared))
                or not set(shared) <= set(ids)
                or (kind == "all_sessions" and (ids or shared or session is not None))
                or (kind != "all_sessions" and not ids)
                or (kind == "captured_by_session" and (not isinstance(session, str) or not SESSION.fullmatch(session)))
                or (kind != "captured_by_session" and session is not None)):
            raise ObjectStorageScopeError()
        return cls(kind, tuple(ids), session, tuple(shared))

    def evidence(self, target_count):
        raw = json.dumps(self.document(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {"schema": "wom-kit/object-storage-scope/v1", "counts": {"selected_object_count": target_count},
                "digests": {"selection_sha256": "sha256:" + hashlib.sha256(raw).hexdigest()},
                "private_values_echoed": False}

    @cached_property
    def _members(self):
        return frozenset(self.object_ids)

    def includes(self, object_id, *, destructive=False):
        # Shared captures are still in the selected session. Selection is not
        # exclusive ownership; existing remote-proof/retention checks govern offload.
        return self.kind == "all_sessions" or object_id in self._members

    def summary(self, total):
        count = total if self.kind == "all_sessions" else len(self.object_ids)
        return {"scope_kind": self.kind, "scope_object_count": count,
                "excluded_out_of_scope_count": max(0, total - count),
                "shared_scope_object_count": len(self.shared_object_ids),
                "scope_is_ownership_proof": False,
                "scope_warning_codes": ["object_storage_all_sessions_explicit"] if self.kind == "all_sessions" else []}


def _session_objects(root, session_ref, *, key_provider=None):
    from . import archive_services as services, exact_approval_claims as claims

    try:
        listing = claims.list_exact_human_approval_claims(root, status="all", max_claims=claims.MAX_LISTED_CLAIMS,
                                                        key_provider=key_provider)
    except Exception:
        raise ObjectStorageScopeError("object_storage_scope_evidence_unavailable") from None
    if listing["blocker_codes"]:
        raise ObjectStorageScopeError("object_storage_scope_evidence_incomplete")
    by_id = {c["approval_id"]: c for c in listing["claims"]}
    documents, _names, complete, _authorities = services._staged_cleanup_receipt_documents(
        root, services.OBJET_CAPTURE_RECEIPTS_DIR, safety_required=True)
    if not complete:
        raise ObjectStorageScopeError("object_storage_scope_evidence_incomplete")
    archive_id = services.read_archive_id(root)
    owners: dict[str, set[str]] = {}
    for filename, receipt in documents:
        if not services._staged_cleanup_valid_objet_receipt_envelope(receipt, filename=filename, archive_id=archive_id):
            continue
        reference = receipt.get("exact_human_approval") or {}
        if not isinstance(reference, dict):
            continue
        approval_id = reference.get("approval_id")
        if not isinstance(approval_id, str):
            continue
        claim = by_id.get(approval_id)
        if not claim or claim.get("operation") not in {"objet_capture", "objet_capture_batch"} or claim["context_sha256"] != reference.get("context_sha256"):
            continue
        presenter = claim.get("session_presenter") or {}
        owner = presenter.get("work_session_ref")
        if not isinstance(owner, str) or not SESSION.fullmatch(owner):
            continue
        for item in receipt["items"]:
            oid = item.get("object_id")
            if (isinstance(oid, str) and OID.fullmatch(oid) and not item.get("blockers")
                    and item.get("action") in {"captured", "repair_appended", "re_materialized", "skip_already_present"}
                    and item.get("approved_object_id") == oid
                    and item.get("logical_key") == f"objects/sha256/{oid[7:9]}/{oid[7:]}"
                    and {"capture": "captured", "repair_append": "repair_appended", "re_materialize": "re_materialized", "skip_already_present": "skip_already_present"}.get(item.get("planned_action")) == item.get("action")):
                owners.setdefault(oid, set()).add(owner)
    ids = tuple(sorted(oid for oid, sessions in owners.items() if session_ref in sessions))
    if not ids:
        raise ObjectStorageScopeError("object_storage_session_scope_unavailable_use_object_list")
    shared = tuple(oid for oid in ids if len(owners[oid]) > 1)
    return ObjectScope("captured_by_session", ids, session_ref, shared)


def resolve_scope(root, *, only=None, object_list=None, captured_by_session=None,
                  this_session=False, all_sessions=False, key_provider=None):
    if sum(bool(x) for x in (only, object_list, captured_by_session, this_session, all_sessions)) > 1:
        raise ObjectStorageScopeError("object_storage_scope_options_conflict")
    if all_sessions:
        return ObjectScope("all_sessions")
    if only:
        if isinstance(only, str) and re.fullmatch(r"[0-9a-f]{64}", only):
            only = "sha256:" + only
        if not isinstance(only, str) or not OID.fullmatch(only):
            raise ObjectStorageScopeError()
        return ObjectScope("single_object", (only,))
    if object_list:
        try:
            path = Path(object_list)
            before = path.lstat()
            if not stat.S_ISREG(before.st_mode) or getattr(before, "st_file_attributes", 0) & 0x400 or before.st_size > 8 * 1024 * 1024:
                raise ValueError()
            raw = path.read_bytes()
            after = path.lstat()
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise ValueError()
            ids = tuple(sorted(set(raw.decode("utf-8-sig").splitlines())))
            if not ids or any(not OID.fullmatch(oid) for oid in ids):
                raise ValueError()
        except Exception:
            raise ObjectStorageScopeError("object_storage_object_list_invalid") from None
        return ObjectScope("object_list", ids)
    session = captured_by_session or os.environ.get("WOM_WORK_SESSION_REF")
    if not isinstance(session, str) or not SESSION.fullmatch(session):
        raise ObjectStorageScopeError("object_storage_session_scope_required")
    return _session_objects(Path(root), session, key_provider=key_provider)


def cli_scope(root, args):
    return resolve_scope(root, only=getattr(args, "only", None), object_list=getattr(args, "object_list", None),
                         captured_by_session=getattr(args, "captured_by_session", None),
                         this_session=getattr(args, "this_session", False),
                         all_sessions=getattr(args, "all_sessions", False))


def validate_scope(root, selected, available_ids, only=None):
    selected = selected if selected is not None else resolve_scope(root, only=only)
    selected = ObjectScope.from_document(selected.document())
    if selected.kind not in {"all_sessions", "single_object"} and not set(selected.object_ids) <= set(available_ids):
        raise ObjectStorageScopeError("object_storage_scope_object_missing")
    return selected
