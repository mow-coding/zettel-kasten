"""Generation-pinned relation discovery and exact, source-grouped judgments.

The index projection is read evidence only. Selected source and target documents
are independently re-read before a write plan is made. One source receives one
edges-field compare-and-swap, even when several judgments add relationships.
"""
from collections import defaultdict
import hashlib
import json
import os
import re
import uuid

from . import archive_services as services, completion_workflows as workflows
from . import local_recovery_execution as recovery, search_snapshots
from .exact_human_approval import exact_human_approval_archive_identity_sha256
from .exact_operation_manifest import (
    ExactFieldEffect, ExactOperationEvidence, ExactOperationItem,
    ExactOperationManifest, _ensure_private_directory, _read_plain_file,
    hash_field_value,
)
from .operation_target_leases import TargetLease
from .snapshot_pagination import SnapshotPager, content_sha256

SCHEMA = "wom-kit/relation-generation/v1"
REQUEST_SCHEMA = "wom-kit/relation-batch-request/v1"
BASIS_SCHEMA = "wom-kit/relation-batch-basis/v1"
LEDGER_SCHEMA = "wom-kit/relation-batch-judgments/v1"
MAX_BYTES = 64 * 1024 * 1024
MAX_DECISIONS = 2000
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_SET_KEYS = ("activity_groups", "time_coordinates", "category_coordinates", "series",
             "sequence_groups", "format_groups", "source_refs", "title_tokens",
             "existing_targets", "derived_from", "body_refs")
_MATCH_KEYS = _SET_KEYS[:8] + ("derived_from",)


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _fail(code):
    return services.ArchiveServiceError(code)


def _values(value):
    if isinstance(value, str):
        return {value} if value else set()
    if isinstance(value, list):
        return set().union(*(_values(item) for item in value)) if value else set()
    if isinstance(value, dict):
        return set().union(*(_values(value.get(key)) for key in ("value", "id", "zettel_id", "object_id", "ref", "source")))
    return set()


def _projection(frontmatter, body, relative, raw_sha256):
    facets = frontmatter.get("facets") or {}
    provenance = frontmatter.get("provenance") or {}
    if not isinstance(facets, dict) or not isinstance(provenance, dict):
        raise ValueError("metadata")
    edges = frontmatter.get("edges") or []
    tokens = {token.casefold() for token in re.findall(r"[\w가-힣]{2,}", str(frontmatter.get("title") or ""))}
    tokens -= {"the", "and", "for", "with", "from", "this", "that", "synthetic"}
    result = {
        "zettel_id": frontmatter["id"], "path": relative, "raw_sha256": raw_sha256,
        "activity_groups": _values(facets.get("activity_group")),
        "time_coordinates": set().union(*(workflows._relation_time_values(facets.get(key)) for key in
            ("notion_event_time_start", "notion_event_time_end", "thought_date"))),
        "category_coordinates": set().union(*(_values(facets.get(key)) for key in
            ("source_category", "db1_category", "db1_subcategory"))),
        "series": _values(facets.get("recurring_series")) | _values(facets.get("series")),
        "sequence_groups": set().union(*(_values(facets.get(key)) for key in
            ("sequence", "process_sequence", "administrative_sequence"))),
        "format_groups": _values(facets.get("format_group")),
        "source_refs": set().union(*(_values(frontmatter.get(key)) for key in ("source_refs", "sources", "source_ref"))),
        "title_tokens": tokens,
        "existing_targets": {str(edge.get("target") or "") for edge in edges if isinstance(edge, dict)},
        "derived_from": _values(provenance.get("derived_from")),
        "body_refs": set(re.findall(r"\bzet_[A-Za-z0-9_]+\b", body)),
        "sequence_index": facets.get("sequence_index") if type(facets.get("sequence_index")) is int else None,
    }
    return {key: sorted(value) if isinstance(value, set) else value for key, value in result.items()}


def _directory(root, create=False):
    if create:
        return _ensure_private_directory(root, ("db", "relation-snapshots"))
    from .source_intake_batch_exact import _reject_link_or_reparse_chain
    path = root / "db/relation-snapshots"
    if not path.exists():
        raise _fail("relation_generation_missing_run_index")
    _reject_link_or_reparse_chain(path, code="relation_generation_invalid")
    return path


def publish(archive_root, *, source_snapshot=None):
    """Index-writer hook: derive once from a verified immutable SQLite snapshot."""
    root = services.require_existing_archive_root(archive_root)
    source_snapshot = source_snapshot or search_snapshots._latest(root)
    if not source_snapshot:
        raise _fail("relation_generation_missing_run_index")
    entries, rejected = {}, 0
    with search_snapshots.open_snapshot(root, source_snapshot) as (connection, _metadata):
        for row in connection.execute("SELECT path, zettel_id, status, body, frontmatter_json, file_sha256 FROM zettels ORDER BY path"):
            if row["status"] != "canonical":
                continue
            try:
                fm = json.loads(row["frontmatter_json"])
                if fm.get("visibility") == "redacted" or not services.ZETTEL_EDGE_ZETTEL_ID_RE.fullmatch(fm["id"]):
                    rejected += 1
                    continue
                if fm["id"] in entries:
                    raise _fail("relation_generation_duplicate_id")
                entries[fm["id"]] = _projection(fm, row["body"] or "", row["path"], row["file_sha256"])
            except (ValueError, KeyError, TypeError):
                rejected += 1
    document = {"schema": SCHEMA, "archive_id": services.read_archive_id(root),
                "source_snapshot": source_snapshot, "entries": entries,
                "not_judged_count": rejected, "read_evidence_only": True}
    raw = _canonical(document)
    if len(raw) > MAX_BYTES:
        raise _fail("relation_generation_too_large")
    digest = hashlib.sha256(raw).hexdigest()
    with TargetLease(root, kind="file", reference="db/relation-snapshots/latest.json"):
        folder = _directory(root, True)
        path = folder / (digest + ".json")
        try:
            services._publish_derived_generation_file(path, raw)
        except FileExistsError:
            if _read_plain_file(path, max_bytes=MAX_BYTES, heartbeat=lambda: None) != raw:
                raise _fail("relation_generation_changed") from None
        pending = folder / (uuid.uuid4().hex + ".pending")
        try:
            with pending.open("xb") as stream:
                stream.write(_canonical({"schema": SCHEMA, "snapshot": digest}))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, folder / "latest.json")
        finally:
            if pending.exists():
                pending.unlink()
    return {"ok": True, "snapshot_ref": digest, "zettel_count": len(entries), "not_judged_count": rejected}


def _read(archive_root, snapshot_ref=None):
    root = services.require_existing_archive_root(archive_root)
    folder = _directory(root)
    if snapshot_ref is None:
        pointer = json.loads(_read_plain_file(folder / "latest.json", max_bytes=4096, heartbeat=lambda: None))
        if pointer.get("schema") != SCHEMA:
            raise _fail("relation_generation_invalid")
        snapshot_ref = pointer.get("snapshot")
    if type(snapshot_ref) is not str or not _DIGEST.fullmatch(snapshot_ref):
        raise _fail("relation_generation_invalid")
    path = folder / (snapshot_ref + ".json")
    if not path.exists():
        raise _fail("relation_generation_expired_restart_query")
    raw = _read_plain_file(path, max_bytes=MAX_BYTES, heartbeat=lambda: None)
    if hashlib.sha256(raw).hexdigest() != snapshot_ref:
        raise _fail("relation_generation_changed")
    document = json.loads(raw)
    if document.get("schema") != SCHEMA or document.get("archive_id") != services.read_archive_id(root):
        raise _fail("relation_generation_invalid")
    return root, snapshot_ref, document


def _candidate(source, target):
    source = {key: set(value) if key in _SET_KEYS else value for key, value in source.items()}
    target = {key: set(value) if key in _SET_KEYS else value for key, value in target.items()}
    signals, types, score = workflows._relation_signal(source, target)
    if target["zettel_id"] in source["derived_from"]:
        signals.insert(0, {"kind": "native_provenance_derived_from", "strength": "high"})
        types.insert(0, "derived_from")
        score += 100
    if target["zettel_id"] in source["body_refs"]:
        signals.insert(0, {"kind": "explicit_body_zettel_reference", "strength": "high"})
        types.insert(0, "references")
        score += 80
    if source["derived_from"] & target["derived_from"]:
        signals.append({"kind": "shared_native_derivation_source", "strength": "medium", "relation_implied": False})
        types.append("semantic")
        score += 40
    if not signals:
        return None
    basis = {"from_zettel": source["zettel_id"], "target_zettel": target["zettel_id"],
             "source_sha256": source["raw_sha256"], "target_sha256": target["raw_sha256"], "signals": signals}
    return {"candidate_id": "candidate:" + hashlib.sha256(_canonical(basis)).hexdigest(), **basis,
            "suggested_types": list(dict.fromkeys(types)), "score": score,
            "already_related": target["zettel_id"] in source["existing_targets"],
            "automatic_acceptance": False}


def _candidates(document, from_zettel):
    entries = document["entries"]
    if from_zettel not in entries:
        raise _fail("relation_source_not_in_generation")
    source = entries[from_zettel]
    # Compare projected coordinates only. No file reads or O(N^2) all-pairs build.
    rows = []
    direct = set(source["derived_from"]) | set(source["body_refs"])
    for target_id, target in entries.items():
        if target_id == from_zettel:
            continue
        if target_id not in direct and not any(set(source[key]) & set(target[key]) for key in _MATCH_KEYS):
            continue
        row = _candidate(source, target)
        if row is not None:
            rows.append(row)
    return sorted(rows, key=lambda row: (-row["score"], row["candidate_id"]))


def query(archive_root, *, from_zettel, snapshot_ref=None, page_size=100, cursor=None):
    if type(from_zettel) is not str or not services.ZETTEL_EDGE_ZETTEL_ID_RE.fullmatch(from_zettel):
        raise _fail("relation_source_invalid")
    if type(page_size) is not int or not 1 <= page_size <= 2000:
        raise _fail("relation_page_size_invalid")
    if cursor and snapshot_ref is None:
        raise _fail("relation_cursor_requires_snapshot")
    _root, snapshot, document = _read(archive_root, snapshot_ref)
    rows = _candidates(document, from_zettel)
    pager = SnapshotPager.build(rows, generation_sha256="sha256:" + snapshot,
                               query_sha256=content_sha256({"from_zettel": from_zettel}))
    return {"ok": True, "schema": "wom-kit/relation-candidates/v1", "snapshot_ref": snapshot,
            "not_judged_count": document["not_judged_count"], **pager.page(page_size=page_size, cursor=cursor),
            "read_only": True, "current_targets_rechecked": False, "private_paths_echoed": False}


def _read_target(root, entry):
    relative = entry["path"]
    if not relative.startswith("zettels/"):
        raise _fail("relation_target_unsafe")
    path = services.archive_internal_path(root, relative)
    raw, reason = services._bounded_stable_regular_file_read(path, max_bytes=recovery.MAX_CANONICAL_BYTES)
    if raw is None or reason is not None:
        raise _fail("relation_target_unreadable")
    boundary = services.parse_approval_zettel_content_boundary(raw.decode("utf-8"))
    fm, body = boundary.get("frontmatter"), boundary.get("body")
    if (boundary.get("state") == "blocked" or not isinstance(fm, dict) or fm.get("id") != entry["zettel_id"]
            or fm.get("archive_id") != services.read_archive_id(root) or fm.get("status") != "canonical"
            or fm.get("visibility") == "redacted" or type(fm.get("edges")) is not list):
        raise _fail("relation_target_invalid")
    return raw, fm, body


def _context_hash(fm, body):
    return _sha(_canonical({"frontmatter": {key: value for key, value in fm.items() if key != "edges"}, "body": body}))


def verify_spec_basis(root, spec):
    """Recheck only this source's judgment dependencies; ignore later edge edits."""
    document = json.loads(spec.source_value)
    if document.get("schema") != BASIS_SCHEMA or not isinstance(document.get("basis"), list):
        raise _fail("relation_basis_invalid")
    for entry in document["basis"]:
        _raw, fm, body = _read_target(root, entry)
        if _context_hash(fm, body) != entry["context_sha256"]:
            raise _fail("relation_judgment_basis_changed")


def plan(archive_root, request):
    """Return the shared native-approval/checkpoint plan, without writes."""
    if (type(request) is not dict or set(request) != {"schema", "snapshot_ref", "reviewed_by", "decisions"}
            or request.get("schema") != REQUEST_SCHEMA or type(request.get("decisions")) is not list
            or not 1 <= len(request["decisions"]) <= MAX_DECISIONS
            or services.safe_project_intake_actor_id(request.get("reviewed_by")) is None):
        raise _fail("relation_batch_request_invalid")
    root, snapshot, generation = _read(archive_root, request["snapshot_ref"])
    cached_candidates, snapshots, decisions, seen = {}, {}, [], set()
    entries = generation["entries"]
    for row in request["decisions"]:
        required = {"from_zettel", "candidate_id", "decision", "edge_type", "visibility", "reason", "confidence"}
        if (type(row) is not dict or set(row) not in (required, required | {"target_zettel"})
                or any(type(row[key]) is not str for key in
                       ("from_zettel", "candidate_id", "decision", "visibility", "reason", "confidence"))
                or not services.ZETTEL_EDGE_ZETTEL_ID_RE.fullmatch(row["from_zettel"])
                or not re.fullmatch(r"candidate:[0-9a-f]{64}", row["candidate_id"])
                or ("target_zettel" in row and (type(row["target_zettel"]) is not str
                    or not services.ZETTEL_EDGE_ZETTEL_ID_RE.fullmatch(row["target_zettel"])))
                or (row["edge_type"] is not None and type(row["edge_type"]) is not str)
                or row["decision"] not in {"accept", "reject", "defer"}
                or row["confidence"] not in {"low", "medium", "high"}
                or row["visibility"] not in {"private", "shared", "family", "company", "public"}
                or services.safe_operator_feedback_scalar(row["reason"], max_length=600) is None):
            raise _fail("relation_batch_decision_invalid")
        source_id = row["from_zettel"]
        if "target_zettel" in row:
            target_id = row["target_zettel"]
            candidate = (_candidate(entries[source_id], entries[target_id])
                         if source_id in entries and target_id in entries and source_id != target_id else None)
            if candidate is not None and candidate["candidate_id"] != row["candidate_id"]:
                candidate = None
        else:
            if source_id not in cached_candidates:
                cached_candidates[source_id] = {item["candidate_id"]: item for item in _candidates(generation, source_id)}
            candidate = cached_candidates[source_id].get(row["candidate_id"])
        if candidate is None or row["candidate_id"] in seen:
            raise _fail("relation_candidate_missing_or_duplicate")
        seen.add(row["candidate_id"])
        target_id = candidate["target_zettel"]
        if row["decision"] == "accept":
            contract, blockers = services.zettel_edge_entity_type_contract(root, row["edge_type"], {"kind": "zettel", "verified": True})
            if blockers or contract.get("status") != "allowed":
                raise _fail("relation_edge_type_contract_invalid")
        elif row["edge_type"] is not None:
            raise _fail("relation_nonaccept_edge_type_forbidden")
        for zid in (source_id, target_id):
            if zid not in snapshots:
                snapshots[zid] = _read_target(root, entries[zid])
                if _sha(snapshots[zid][0]) != entries[zid]["raw_sha256"]:
                    raise _fail("relation_generation_target_changed")
        decisions.append({**row, "target_zettel": target_id, "signals": candidate["signals"]})
    archive_id = services.read_archive_id(root)
    ledger = {"schema": LEDGER_SCHEMA, "archive_id": archive_id, "snapshot_ref": snapshot,
              "reviewed_by": request["reviewed_by"], "decisions": decisions}
    ledger_bytes = _canonical(ledger) + b"\n"
    ledger_relative = recovery.local_recovery_ledger_relative("relation_batch", ledger_bytes)
    ledger_ref = "judgment:" + hashlib.sha256(ledger_bytes).hexdigest()
    items, specs = [], []

    def append_spec(kind, relative, zid, field, before, after, source):
        identity = (recovery.local_recovery_zettel_identity_sha256(archive_id, zid, relative) if kind == "zettel"
                    else recovery.local_recovery_ledger_identity_sha256(archive_id, "relation_batch", relative))
        item = ExactOperationItem(ordinal=len(items), item_id=f"item:{len(items):06d}", target_kind=kind,
            target_ref=identity, target_identity_sha256=identity,
            fields=(ExactFieldEffect(field_ref=field, pre_sha256=hash_field_value(before),
                    post_sha256=hash_field_value(after), source_sha256=hash_field_value(source)),))
        items.append(item)
        specs.append(recovery.LocalRecoveryFieldSpec(item_id=item.item_id, target_kind=kind,
            target_ref=identity, target_identity_sha256=identity, field_ref=field, target_relative=relative,
            zettel_id=zid, pre_value=before, post_value=after, source_value=source))

    # Ledger first: any written edge already has a durable reason to resolve.
    append_spec("local_recovery_ledger", ledger_relative, None, "classification.ledger", None,
                ledger_bytes, _canonical({"request_sha256": _sha(_canonical(request))}))
    grouped = defaultdict(list)
    for row in decisions:
        if row["decision"] == "accept":
            grouped[row["from_zettel"]].append(row)
    edge_count = 0
    for source_id, rows in sorted(grouped.items()):
        fm = snapshots[source_id][1]
        edges = json.loads(_canonical(fm["edges"]))
        basis_ids = {source_id}
        for row in rows:
            target_id = row["target_zettel"]
            if any(edge.get("type") == row["edge_type"] and edge.get("target") == target_id for edge in edges if isinstance(edge, dict)):
                raise _fail("relation_edge_already_present")
            seed = {"from": source_id, "target": target_id, "type": row["edge_type"], "visibility": row["visibility"]}
            edges.append({"type": row["edge_type"], "target": target_id, "visibility": row["visibility"],
                          "edge_id": "edge_" + hashlib.sha256(_canonical(seed)).hexdigest()[:32],
                          "receipt": ledger_relative,
                          "provenance": {"source": "relation_batch", "reviewed_by": request["reviewed_by"],
                              "judgment_ref": ledger_ref, "candidate_id": row["candidate_id"]}})
            basis_ids.add(target_id)
            edge_count += 1
        basis = [{"path": entries[zid]["path"], "zettel_id": zid,
                  "context_sha256": _context_hash(snapshots[zid][1], snapshots[zid][2])} for zid in sorted(basis_ids)]
        append_spec("zettel", entries[source_id]["path"], source_id, "frontmatter.edges", _canonical(fm["edges"]),
                    _canonical(edges), _canonical({"schema": BASIS_SCHEMA, "judgment_ref": ledger_ref, "basis": basis}))
    evidence = ExactOperationEvidence(schema="wom-kit/relation-batch-evidence/v1",
        counts=tuple(sorted({"decision_count": len(decisions), "edge_count": edge_count, "source_write_count": len(grouped)}.items())),
        digests=(("judgments_sha256", _sha(ledger_bytes)), ("request_sha256", _sha(_canonical(request)))))
    manifest = ExactOperationManifest.build(operation=recovery.APPLY_OPERATION,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(archive_id), items=items, operation_evidence=evidence)
    return recovery.build_local_recovery_plan(root, domain="relation_batch", manifest=manifest, specs=specs,
        public_summary={"decision_count": len(decisions), "edge_count": edge_count,
                        "source_write_count": len(grouped), "judgment_ref": ledger_ref, "automatic_acceptance": False})


def judgment(archive_root, judgment_ref):
    """Explicit local decision lookup; reasons may contain private context."""
    root = services.require_existing_archive_root(archive_root)
    if type(judgment_ref) is not str or not re.fullmatch(r"judgment:[0-9a-f]{64}", judgment_ref):
        raise _fail("relation_judgment_ref_invalid")
    path = services.archive_internal_path(root, recovery.LEDGER_ROOT + "/relation_batch/" + judgment_ref.split(":")[1] + ".json")
    raw = _read_plain_file(path, max_bytes=recovery.MAX_LOCAL_FIELD_BYTES, heartbeat=lambda: None)
    if "judgment:" + hashlib.sha256(raw).hexdigest() != judgment_ref:
        raise _fail("relation_judgment_changed")
    document = json.loads(raw)
    if document.get("schema") != LEDGER_SCHEMA or document.get("archive_id") != services.read_archive_id(root):
        raise _fail("relation_judgment_invalid")
    return {"ok": True, "judgment_ref": judgment_ref, "private_local_detail": True, "judgments": document["decisions"],
            "edge_application_must_be_checked_separately": True}


def semantics(archive_root):
    """Describe every active link type rather than a five-example subset."""
    root = services.require_existing_archive_root(archive_root)
    local = services.archive_internal_path(root, "zettel-kasten/types.yml")
    path = local if local.exists() else services.KIT_ZETTEL_KASTEN_ROOT / "types.yml"
    raw = _read_plain_file(path, max_bytes=4 * 1024 * 1024, heartbeat=lambda: None)
    document = services.load_yaml(raw.decode("utf-8"))
    definitions = document.get("link_types") if isinstance(document, dict) else None
    if not isinstance(definitions, list):
        raise _fail("relation_type_registry_invalid")
    rows, seen = [], set()
    for entry in definitions:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or entry["id"] in seen:
            raise _fail("relation_type_registry_invalid")
        valid_from, from_types = services.safe_zettel_edge_entity_types(entry.get("from"))
        valid_to, to_types = services.safe_zettel_edge_entity_types(entry.get("to"))
        if not valid_from or not valid_to:
            raise _fail("relation_type_registry_invalid")
        seen.add(entry["id"])
        rows.append({"edge_type": entry["id"], "meaning": entry.get("description"),
                     "from": sorted(from_types), "to": sorted(to_types),
                     "zettel_candidate_batch_supported": "Zettel" in from_types and "Zettel" in to_types,
                     "automatic_type_inference": False})
    return {"ok": True, "schema": "wom-kit/relation-semantics/v1", "registry_sha256": _sha(raw),
            "type_count": len(rows), "types": rows, "current_registry_complete": True,
            "coordinate_sharing_is_relation_proof": False}
