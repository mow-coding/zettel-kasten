"""Authenticated object-use evidence emitted by successful zet writers.

Approval of some operation alone never authenticates an arbitrary copied domain
receipt. The payload is bound to the actual writer claim with a terminal MAC.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

ROOT = "receipts/session-object-usage"
OPERATIONS = frozenset({"create_draft", "mint_zet", "mint_zet_batch", "zet_revision_write", "draft_revision_write", "zettel_objet_link", "source_intake_chain"})
SCHEMA = "wom-kit/session-object-usage/v1"


def encoded(value):
    from .exact_human_approval import _canonical_bytes
    return _canonical_bytes(value)


def record(root, context, claim, result):
    if context.operation.value not in OPERATIONS:
        return
    from . import archive_services as services
    from .object_storage_scope import OID, _reference_ids, _snapshot_object_refs
    from .object_storage_offload import _create_or_match_document
    root = services.require_existing_archive_root(Path(root))
    reference = claim.public_reference()
    ids, visited = set(), set()

    def explicit_ids(value):
        """A diagnostic sentence mentioning an objet is not evidence of use."""
        found = set()
        if isinstance(value, list):
            for item in value:
                found.update(explicit_ids(item))
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {"object_id", "source_object_id"} and isinstance(item, str) and OID.fullmatch(item):
                    found.add(item)
                elif key == "object_ids" and isinstance(item, list):
                    found.update(oid for oid in item if isinstance(oid, str) and OID.fullmatch(oid))
                elif isinstance(item, (dict, list)):
                    found.update(explicit_ids(item))
        return found

    def collect(value):
        if isinstance(value, list):
            for item in value:
                collect(item)
        if not isinstance(value, dict):
            return
        ids.update(explicit_ids(value))
        if isinstance(value.get("path"), str) and isinstance(value.get("body_sha256"), str):
            path = services.archive_internal_path(root, value["path"])
            snapshot = services._source_fidelity_raw_draft_snapshot(root, path)
            if snapshot.get("ok") and hashlib.sha256(snapshot["body_bytes"]).hexdigest() == value["body_sha256"].removeprefix("sha256:"):
                ids.update(_reference_ids(snapshot["body_bytes"].decode("utf-8")))
        # Read only exact hash-bound versions named by the writer's own result
        # or receipt. Current mutable note contents alone are not usage evidence.
        for path_key, sha_key in (("path", "sha256"), ("canonical_path", "file_sha256"),
                                  ("zettel_path", "after_zettel_sha256"),
                                  ("before_snapshot_path", "snapshot_sha256")):
            ids.update(_snapshot_object_refs(root, value.get(path_key), value.get(sha_key)))
        after = value.get("after") or {}
        if isinstance(after, dict):
            ids.update(_snapshot_object_refs(root, value.get("canonical_path") or value.get("draft_path"), after.get("file_sha256")))
        for key, item in value.items():
            if key in {"receipt_path", "source_fidelity_draft_receipt_path", "revision_receipt_path", "mint_receipt_path"} and isinstance(item, str) and item not in visited:
                visited.add(item)
                path = services.archive_internal_path(root, item)
                # Results may also carry a *future* cleanup plan. Such an
                # absent planned receipt is not evidence of completed work.
                if not path.exists():
                    continue
                if (not item.startswith("receipts/") or services.objet_capture_path_chain_blockers(root, item)
                    or path.stat().st_size > 8 * 1024 * 1024):
                    raise ValueError("session_usage_receipt_invalid")
                collect(json.loads(path.read_bytes()))
            elif key == "mint_receipts" and isinstance(item, list):
                for receipt_path in item:
                    collect({"receipt_path": receipt_path})
            elif isinstance(item, (list, dict)):
                collect(item)
    collect(result)
    ids = sorted(ids)
    part_count = max(1, (len(ids) + 499) // 500)
    all_ids_sha256 = "sha256:" + hashlib.sha256(encoded({"object_ids": ids})).hexdigest()
    # Batch operations may touch many objects; bound every independently
    # authenticated record below the approval terminal-payload size limit.
    for number, start in enumerate(range(0, max(1, len(ids)), 500)):
        payload = {"schema": SCHEMA, "archive_id": services.read_archive_id(root),
            "operation": context.operation.value, "plan_sha256": context.plan_sha256,
            "target_binding_sha256": context.target_binding_sha256,
            "approval": reference, "part": number, "part_count": part_count,
            "all_object_ids_sha256": all_ids_sha256, "object_ids": ids[start:start + 500]}
        document = {"payload": payload, "mac": claim.exact_terminal_record_mac(encoded(payload))}
        _create_or_match_document(root, ROOT + "/" + claim.approval_id + "-" + str(number) + ".json",
            encoded(document), failure_code="object_storage_offload_receipt_conflict", max_bytes=128 * 1024)


def add_owners(root, claims, owners, *, key_provider=None):
    from . import archive_services as services
    from .exact_human_approval import audit_exact_human_approval_succeeded_terminal_record_read_only as audit
    from .exact_human_approval_windows import ExactHumanApprovalOperation
    from .object_storage_scope import OID, SESSION, ObjectStorageScopeError
    documents, _, complete, _ = services._staged_cleanup_receipt_documents(root, ROOT, safety_required=True)
    if not complete:
        raise ObjectStorageScopeError("object_storage_scope_evidence_incomplete")
    groups = {}
    for _, document in documents:
        try:
            payload = document["payload"]
            reference = payload["approval"]
            claim = claims.get(reference["approval_id"])
            owner = (claim.get("session_presenter") or {}).get("work_session_ref") if claim else None
            if (payload["schema"] != SCHEMA or payload["archive_id"] != services.read_archive_id(root)
                or not isinstance(owner, str) or not SESSION.fullmatch(owner)
                or claim.get("status") != "succeeded" or claim.get("context_sha256") != reference["context_sha256"]
                or payload["operation"] not in OPERATIONS or claim.get("operation") != payload["operation"]
                or type(payload.get("part")) is not int or type(payload.get("part_count")) is not int
                or not 1 <= payload["part_count"] <= 201 or not 0 <= payload["part"] < payload["part_count"]
                or not isinstance(payload.get("all_object_ids_sha256"), str)
                or not isinstance(payload["object_ids"], list)
                or any(not isinstance(oid, str) or not OID.fullmatch(oid) for oid in payload["object_ids"])):
                continue
            if not audit(root, reference, expected_operation=ExactHumanApprovalOperation(payload["operation"]),
                expected_plan_sha256=payload["plan_sha256"], expected_target_binding_sha256=payload["target_binding_sha256"],
                payload=encoded(payload), expected_mac=document["mac"], key_provider=key_provider):
                continue
            groups.setdefault(reference["approval_id"], []).append((owner, payload))
        except (KeyError, TypeError, ValueError):
            continue
    for parts in groups.values():
        ordered = sorted(parts, key=lambda entry: entry[1]["part"])
        first = ordered[0][1]
        if (len(ordered) != first["part_count"]
            or [entry[1]["part"] for entry in ordered] != list(range(first["part_count"]))
            or any(owner != ordered[0][0] or payload["part_count"] != first["part_count"]
                   or payload["all_object_ids_sha256"] != first["all_object_ids_sha256"]
                   for owner, payload in ordered)):
            continue
        ids = [oid for _, payload in ordered for oid in payload["object_ids"]]
        if "sha256:" + hashlib.sha256(encoded({"object_ids": ids})).hexdigest() != first["all_object_ids_sha256"]:
            continue
        for oid in ids:
            owners.setdefault(oid, set()).add(ordered[0][0])
