"""Complete, content-free title diagnostics over an immutable index-time census.

``publish`` belongs to the existing index writer. ``query`` and ``private_report``
only read its generation: pagination never opens the live canonical corpus.
"""
import hashlib
import json
import os
import re
import uuid

from . import archive_services as services
from .exact_operation_manifest import _ensure_private_directory, _read_plain_file
from .operation_target_leases import TargetLease
from .snapshot_pagination import SnapshotPager, content_sha256

SCHEMA = "wom-kit/title-diagnostics-generation/v1"
MAX_BYTES = 64 * 1024 * 1024
DIGEST = re.compile(r"[0-9a-f]{64}")


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _error(code):
    return services.ArchiveServiceError(code)


def _directory(root, create=False):
    if create:
        return services.ensure_derived_directory_ignored(
            _ensure_private_directory(root, ("db", "title-snapshots")))
    from .source_intake_batch_exact import _reject_link_or_reparse_chain
    path = root / "db/title-snapshots"
    if not path.exists():
        raise _error("title_diagnostics_generation_missing_run_index")
    _reject_link_or_reparse_chain(path, code="search_snapshot_invalid")
    return path


def _rules(value):
    if value is None:
        return []
    if type(value) is not list or len(value) > 100:
        raise _error("title_diagnostics_rules_invalid")
    result, seen = [], set()
    for rule in value:
        if (type(rule) is not dict or set(rule) != {"rule_id", "match", "value"}
                or type(rule["rule_id"]) is not str
                or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", rule["rule_id"])
                or rule["rule_id"] in seen or type(rule["match"]) is not str
                or rule["match"] not in {"exact", "prefix"}
                or type(rule["value"]) is not str or not 0 < len(rule["value"]) <= 200):
            raise _error("title_diagnostics_rules_invalid")
        seen.add(rule["rule_id"])
        result.append(dict(rule))
    return result


def _classify(root, entries, scan, catalog_snapshot, *, rules=None):
    selected_rules = _rules(rules)
    rows, details, counts = [], {}, {}
    for relative, item in entries:
        item_ref = "title-item:" + hashlib.sha256(relative.encode("utf-8")).hexdigest()
        title, reasons, signals = item.get("title"), [], []
        if item.get("redacted"):
            reasons.append("redacted_not_judged")
        elif not item.get("frontmatter_readable"):
            reasons.append("frontmatter_unreadable")
        elif not isinstance(title, str) or not title.strip():
            warnings = item.get("warnings") or []
            reasons.append("title_suppressed_private_or_unsafe" if any("title" in str(row) for row in warnings)
                           else "title_missing_or_empty")
        else:
            signals.extend(services.zet_title_identifier_signals(item))
            for rule in selected_rules:
                matches = title == rule["value"] if rule["match"] == "exact" else title.startswith(rule["value"])
                if matches:
                    signals.append("configured_marker:" + rule["rule_id"])
            if signals:
                reasons.append("title_review_recommended")
        state = "not_judged" if reasons and reasons[0] != "title_review_recommended" else "attention" if signals else "readable"
        counts[state] = counts.get(state, 0) + 1
        row = {"item_ref": item_ref, "state": state, "reason_codes": reasons, "signals": signals,
               "automatic_change_allowed": False}
        rows.append(row)
        details[item_ref] = {"relative_path": relative, "reason_codes": reasons,
                             "title": title if not item.get("redacted") else None,
                             "index_diagnostic_code": item.get("index_diagnostic_code")}
    rows.sort(key=lambda row: row["item_ref"])
    return {"schema": SCHEMA, "archive_id": services.read_archive_id(root), "rows": rows,
            "private_details": details, "counts": counts, "rules": selected_rules,
            "catalog_snapshot": catalog_snapshot, "scan": scan,
            "read_only_evidence_not_write_authority": True}


def collect(archive_root, *, rules=None):
    """Explicit filesystem census fallback, not used by the index hook."""
    root = services.require_existing_archive_root(archive_root)
    entries, scan = services.zet_catalog_entries(root, services.zet_catalog_paths(root, "canonical"), None)
    return _classify(root, [(services.archive_relative_path(path, root), item) for path, _status, item, _signature in entries],
                     scan, services.zet_catalog_snapshot(root, entries), rules=rules)


def collect_index_rows(archive_root, *, index_rows, index_generation=None, index_diagnostics=None, rules=None):
    """Pure projection of the index writer's captured rows, including errors."""
    root = services.require_existing_archive_root(archive_root)
    diagnostics = {}
    for row in index_diagnostics or []:
        if (type(row) is not dict or type(row.get("path")) is not str or type(row.get("code")) is not str
                or not re.fullmatch(r"[a-z][a-z0-9_]{0,100}", row["code"])):
            raise _error("title_diagnostics_index_metadata_invalid")
        diagnostics[row["path"]] = row["code"]
    entries = []
    for row in index_rows:
        if (not isinstance(row, dict) or not {"path", "title", "status", "frontmatter_json"} <= set(row)
                or type(row["path"]) is not str):
            raise _error("title_diagnostics_index_metadata_invalid")
        if not row["path"].startswith("zettels/"):
            continue
        redacted = row["status"] == "redacted"
        quarantined = row["status"] == services.ZETTEL_QUARANTINED_STATUS
        warnings = []
        try:
            fm = {} if redacted or quarantined else json.loads(row["frontmatter_json"])
            if not isinstance(fm, dict):
                raise ValueError()
        except (ValueError, TypeError):
            fm, quarantined = {}, True
        title = None if redacted or quarantined else services.safe_zettel_overview_string(row["title"], warnings, "$.frontmatter.title")
        entries.append((row["path"], {"title": title, "redacted": redacted, "frontmatter_readable": not quarantined,
            "facets": fm.get("facets"), "warnings": warnings,
            "index_diagnostic_code": diagnostics.get(row["path"], "frontmatter_quarantined" if quarantined else None)}))
    return _classify(root, entries, {"source": "index_writer_captured_rows", "zettel_rows": len(entries), "live_files_opened": 0},
        {"captured_rows_sha256": content_sha256(entries), "index_generation": index_generation}, rules=rules)


def collect_snapshot(archive_root, *, source_snapshot, index_diagnostics=None, rules=None):
    from . import search_snapshots
    root = services.require_existing_archive_root(archive_root)
    with search_snapshots.open_snapshot(root, source_snapshot) as (connection, metadata):
        rows = [dict(row) for row in connection.execute(
            "SELECT path, title, status, frontmatter_json FROM zettels WHERE path LIKE 'zettels/%' ORDER BY path")]
    result = collect_index_rows(root, index_rows=rows, index_generation=metadata["index_generation"],
                                index_diagnostics=index_diagnostics, rules=rules)
    result["scan"].update(source="verified_sqlite_generation", source_snapshot=source_snapshot)
    result["catalog_snapshot"]["source_snapshot"] = source_snapshot
    return result


def publish(archive_root, *, rules=None, source_snapshot=None, index_diagnostics=None, index_rows=None, index_generation=None):
    """Called by the index writer; retain old generations and never change zets."""
    root = services.require_existing_archive_root(archive_root)
    if source_snapshot is not None:
        document = collect_snapshot(root, source_snapshot=source_snapshot, index_diagnostics=index_diagnostics, rules=rules)
    elif index_rows is not None:
        document = collect_index_rows(root, index_rows=index_rows, index_generation=index_generation,
                                     index_diagnostics=index_diagnostics, rules=rules)
    else:
        document = collect(root, rules=rules)
    raw = _canonical(document)
    if len(raw) > MAX_BYTES:
        raise _error("title_diagnostics_generation_too_large")
    digest = hashlib.sha256(raw).hexdigest()
    with TargetLease(root, kind="file", reference="db/title-snapshots/latest.json"):
        folder = _directory(root, create=True)
        path = folder / (digest + ".json")
        try:
            services._publish_derived_generation_file(path, raw)
        except FileExistsError:
            if _read_plain_file(path, max_bytes=MAX_BYTES, heartbeat=lambda: None) != raw:
                raise _error("title_diagnostics_generation_changed") from None
        partial = folder / (uuid.uuid4().hex + ".pending")
        try:
            with partial.open("xb") as stream:
                stream.write(_canonical({"schema": SCHEMA, "snapshot": digest}))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(partial, folder / "latest.json")
        finally:
            if partial.exists():
                partial.unlink()
        # v0.4.54: old generations no longer pile up on the disk.
        pruned = services.prune_derived_generations(folder, keep_digest=digest)
    return {"ok": True, "snapshot_ref": digest, "counts": document["counts"], "zet_bytes_modified": False,
            "pruned_generations": pruned}


def _read(archive_root, snapshot_ref=None):
    root = services.require_existing_archive_root(archive_root)
    folder = _directory(root)
    if snapshot_ref is None:
        pointer = json.loads(_read_plain_file(folder / "latest.json", max_bytes=4096, heartbeat=lambda: None))
        if pointer.get("schema") != SCHEMA:
            raise _error("title_diagnostics_generation_invalid")
        snapshot_ref = pointer.get("snapshot")
    if type(snapshot_ref) is not str or DIGEST.fullmatch(snapshot_ref) is None:
        raise _error("title_diagnostics_generation_invalid")
    path = folder / (snapshot_ref + ".json")
    if not path.exists():
        raise _error("title_diagnostics_generation_expired_restart_query")
    raw = _read_plain_file(path, max_bytes=MAX_BYTES, heartbeat=lambda: None)
    if hashlib.sha256(raw).hexdigest() != snapshot_ref:
        raise _error("title_diagnostics_generation_changed")
    document = json.loads(raw)
    if document.get("schema") != SCHEMA or document.get("archive_id") != services.read_archive_id(root):
        raise _error("title_diagnostics_generation_invalid")
    return snapshot_ref, document


def query(archive_root, *, snapshot_ref=None, page_size=100, cursor=None, state=None):
    if state not in {None, "attention", "not_judged", "readable"}:
        raise _error("title_diagnostics_query_invalid")
    if type(page_size) is not int or not 1 <= page_size <= 2000:
        raise _error("title_diagnostics_page_size_invalid")
    if cursor and snapshot_ref is None:
        raise _error("title_diagnostics_cursor_requires_snapshot")
    snapshot, document = _read(archive_root, snapshot_ref)
    rows = [row for row in document["rows"] if state is None or row["state"] == state]
    pager = SnapshotPager.build(rows, generation_sha256="sha256:" + snapshot,
                               query_sha256=content_sha256({"state": state}))
    return {"schema": "wom-kit/title-diagnostics/v1", "ok": True, "read_only": True,
            "snapshot_ref": snapshot, "counts": document["counts"], **pager.page(page_size=page_size, cursor=cursor),
            "current_live_titles_rechecked": False, "title_values_echoed": False, "paths_echoed": False}


def private_report(archive_root, *, snapshot_ref=None):
    """Explicit private-export API; never include this in shareable summaries."""
    snapshot, document = _read(archive_root, snapshot_ref)
    return {"schema": "wom-kit/title-diagnostics-private/v1", "snapshot_ref": snapshot,
            "contains_private_paths_and_titles": True, "items": document["private_details"]}
