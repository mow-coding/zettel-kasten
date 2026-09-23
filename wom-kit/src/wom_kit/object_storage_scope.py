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


def _session_owners(root, *, key_provider=None):
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
        if not claim or claim.get("operation") not in {"objet_capture", "objet_capture_batch", "source_intake_chain"} or claim["context_sha256"] != reference.get("context_sha256"):
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
    _add_zet_usage_owners(root, by_id, owners, key_provider=key_provider)
    return owners


def _session_objects(root, session_ref, *, key_provider=None):
    owners = _session_owners(root, key_provider=key_provider)
    ids = tuple(sorted(oid for oid, sessions in owners.items() if session_ref in sessions))
    if not ids:
        raise ObjectStorageScopeError("object_storage_session_scope_unavailable_use_object_list")
    shared = tuple(oid for oid in ids if len(owners[oid]) > 1)
    return ObjectScope("captured_by_session", ids, session_ref, shared)


def _reference_ids(value):
    if isinstance(value, str):
        return set(re.findall(r"objet:(sha256:[0-9a-f]{64})(?![0-9a-f])", value))
    if isinstance(value, dict):
        result = set()
        for key, item in value.items():
            if key in {"object_id", "source_object_id"} and isinstance(item, str) and OID.fullmatch(item):
                result.add(item)
            elif key == "object_ids" and isinstance(item, list):
                result.update(oid for oid in item if isinstance(oid, str) and OID.fullmatch(oid))
            else:
                result.update(_reference_ids(item))
        return result
    if isinstance(value, list):
        return set().union(*(_reference_ids(v) for v in value)) if value else set()
    return set()


def _snapshot_object_refs(root, relative, sha):
    from . import archive_services as services
    if not isinstance(relative, str) or not isinstance(sha, str):
        return set()
    digest = sha.removeprefix("sha256:")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        return set()
    try:
        path = services.archive_internal_path(root, relative)
        if services.objet_capture_path_chain_blockers(root, relative) or path.stat().st_size > 8 * 1024 * 1024:
            return set()
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            return set()
        # Only explicit object links in the exact version worked on. Never
        # infer activity from today's possibly edited note or its timestamp.
        return set(re.findall(r"objet:(sha256:[0-9a-f]{64})(?![0-9a-f])", raw.decode("utf-8")))
    except (OSError, ValueError, UnicodeError):
        return set()


def _add_zet_usage_owners(root, by_id, owners, *, key_provider=None):
    from . import archive_services as services, completion_workflows as workflows
    from .session_object_usage import add_owners
    add_owners(root, by_id, owners, key_provider=key_provider)
    # Historical unsigned usage receipts do not become trusted merely because
    # they copied a valid approval id. Preserve them as unattributed evidence.
    # Creation receipts are immutable and linked through authenticated receipts.
    # Replayed review does not turn an old creation into new session activity.
    creation_claims = [c for c in by_id.values() if c.get("operation") == "create_draft" and c.get("status") == "succeeded"]
    if not creation_claims:
        return
    from .exact_human_approval_link import read_exact_human_approval_link
    from .exact_human_approval_workflow import _production_key_provider
    provider = key_provider or _production_key_provider()
    for claim in creation_claims:
        owner = (claim.get("session_presenter") or {}).get("work_session_ref")
        if not isinstance(owner, str) or not SESSION.fullmatch(owner):
            continue
        try:
            link = provider.use_key(root, lambda key: read_exact_human_approval_link(root,
                claim["approval_id"], receipt_authentication_key=key), create_if_missing=False)
            if link.get("effect") != "created":
                continue
            source = link["source_operation_receipt"]
            raw = services.archive_internal_path(root, source["relative_path"]).read_bytes()
            if "sha256:" + hashlib.sha256(raw).hexdigest() != source["sha256"]:
                continue
            receipt = json.loads(raw)
            ids = _reference_ids(receipt.get("source_fidelity"))
            for oid in ids:
                owners.setdefault(oid, set()).add(owner)
        except Exception:
            # Legacy unlinked creations remain unattributed, never guessed.
            continue


def export_scope_list(root, *, output, sessions=(), object_lists=(), this_session=False, key_provider=None):
    from . import archive_services as services
    root = services.require_existing_archive_root(Path(root))
    chosen_sessions = set(sessions)
    if this_session or not (sessions or object_lists):
        chosen_sessions.add(os.environ.get("WOM_WORK_SESSION_REF"))
    if any(not isinstance(s, str) or not SESSION.fullmatch(s) for s in chosen_sessions):
        raise ObjectStorageScopeError("object_storage_session_scope_required")
    owners = _session_owners(root, key_provider=key_provider)
    available = {r["object_id"] for r in services.load_manifest_records(root)
                 if isinstance(r, dict) and OID.fullmatch(str(r.get("object_id") or ""))}
    selected = {oid for oid, sessions_for_oid in owners.items() if chosen_sessions & sessions_for_oid}
    for name in object_lists:
        selected.update(resolve_scope(root, object_list=name).object_ids)
    if not selected <= available:
        raise ObjectStorageScopeError("object_storage_scope_object_missing")
    payload = ("\n".join(sorted(selected)) + ("\n" if selected else "")).encode("utf-8")
    if selected:
        path = Path(output)
        # Explicit private output only; never overwrite another list or archive data.
        if path.resolve().is_relative_to(root.resolve()):
            raise ObjectStorageScopeError("object_storage_scope_output_inside_archive")
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    return {"schema": "wom-kit/object-storage-scope-list/v1", "ok": bool(selected),
            "selected_object_count": len(selected), "other_session_excluded_count": len((set(owners) & available) - selected),
            "shared_object_count": sum(len(owners.get(oid, ())) > 1 for oid in selected),
            "unattributed_object_count": len(available - set(owners)), "evidence_scan_complete": True,
            "list_written": bool(selected), "list_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "private_values_echoed": False, "next_command": "object-storage-upload --object-list <private-list> --dry-run"}


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
