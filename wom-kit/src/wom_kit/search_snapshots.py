"""Historical, verified SQLite search generations; never write authority.

Publication uses SQLite's backup API from a pinned, validated read transaction.
No archive writer lock is taken. Readers retain a digest-named generation across
pages, including while the live index is dirty. This cache is private and
disposable; its results cannot authorize capture, edits, or deletion.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

SCHEMA = "wom-kit/search-generation/v1"
CURSOR_SCHEMA = "wom-kit/search-cursor/v1"
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
CHANNELS = ("zettel", "object", "derived_text", "view", "source_map")


def _error(code):
    from .archive_services import ArchiveServiceError
    return ArchiveServiceError(code)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _sha(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _archive_binding(root):
    info = os.stat(root)
    return _sha([info.st_dev, info.st_ino])


def _directory(root, *, create=False):
    from .exact_operation_manifest import _ensure_private_directory
    from .source_intake_batch_exact import _reject_link_or_reparse_chain
    if create:
        from . import archive_services as _services
        return _services.ensure_derived_directory_ignored(
            _ensure_private_directory(root, ("db", "search-snapshots")))
    path = root / "db/search-snapshots"
    _reject_link_or_reparse_chain(path, code="search_snapshot_invalid")
    return path


def _file_digest(path):
    from .source_intake_batch_exact import _stable_source_digest
    digest, _size, identity, info = _stable_source_digest(path, heartbeat=lambda: None)
    if info.st_nlink != 1:
        raise _error("search_snapshot_invalid")
    return digest.removeprefix("sha256:"), identity


def _latest(root):
    from .exact_operation_manifest import _read_plain_file
    if not (root / "db/search-snapshots").exists():
        return None
    path = _directory(root) / "latest.json"
    if not path.exists():
        return None
    value = json.loads(_read_plain_file(path, max_bytes=4096, heartbeat=lambda: None))
    if (type(value) is not dict or set(value) != {"schema", "snapshot"}
            or value["schema"] != SCHEMA or type(value["snapshot"]) is not str
            or not DIGEST.fullmatch(value["snapshot"])):
        raise _error("search_snapshot_invalid")
    return value["snapshot"]


def publish(root, *, timeout_seconds=5):
    """Best-effort cache refresh, outside the shared mutation critical section.

    The old published generation survives any failure or a concurrent mutation.
    A fresh search also attempts this refresh; existing cursors never do.
    """
    from . import archive_services as services
    from .operation_target_leases import TargetLease
    root = services.require_existing_archive_root(root)
    if not (root / services.INDEX_RELATIVE_PATH).is_file():
        return {"ok": False, "reason": "archive_index_missing"}
    source = target = None
    partial = pointer_partial = None
    started = time.monotonic()
    try:
        with TargetLease(root, kind="file", reference="db/search-snapshots/latest.json",
                         timeout_seconds=0):
            source = services.connect_archive_index(root / services.INDEX_RELATIVE_PATH, row_factory=True)
            source.execute("PRAGMA busy_timeout=100")
            source.execute("BEGIN")
            metadata = services.read_archive_index_metadata(source)
            identity = _sha(metadata)
            previous = _latest(root)
            if previous:
                with open_snapshot(root, previous) as (old, old_meta):
                    reusable = old_meta["index_metadata_sha256"] == identity
                if reusable:
                    pruned = services.prune_derived_generations(_directory(root), keep_digest=previous)
                    return {"ok": True, "snapshot": previous, "reused": True,
                            "live_source_freshness_checked": False, "pruned_generations": pruned}
            evidence = services.require_current_zettel_index(root, connection=source)
            if evidence.get("ok") is not True:
                return {"ok": False, "reason": "search_live_index_not_ready"}
            started = time.monotonic()
            directory = _directory(root, create=True)
            partial = directory / (uuid.uuid4().hex + ".building")
            descriptor = os.open(partial, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            target = sqlite3.connect(partial)

            def progress(_status, _remaining, _total):
                if time.monotonic() - started > timeout_seconds:
                    raise _error("search_snapshot_refresh_timeout")

            source.backup(target, pages=256, progress=progress, sleep=0.01)
            # The pinned transaction is already fully validated. Subsequent
            # source edits do not invalidate this explicitly historical view.
            source.rollback()
            source.close()
            source = None
            snapshot_meta = {"schema": SCHEMA, "archive_binding": _archive_binding(root),
                "index_metadata_sha256": identity, "index_generation": metadata.get("generation"),
                "indexed_at": metadata.get("updated_at"), "captured_at": datetime.now(timezone.utc).isoformat(),
                "index_evidence": evidence, "authoritative_for_writes": False}
            target.execute("CREATE TABLE wom_search_snapshot_metadata (document TEXT NOT NULL)")
            target.execute("INSERT INTO wom_search_snapshot_metadata VALUES (?)", (_canonical(snapshot_meta).decode(),))
            target.commit()
            target.close()
            target = None
            with partial.open("r+b") as stream:
                os.fsync(stream.fileno())
            digest, _identity = _file_digest(partial)
            from .object_storage_restore import _atomic_move_file_no_replace
            _atomic_move_file_no_replace(partial, directory / (digest + ".sqlite"))
            partial = None
            pointer_partial = directory / (uuid.uuid4().hex + ".pointer")
            with pointer_partial.open("xb") as stream:
                stream.write(_canonical({"schema": SCHEMA, "snapshot": digest}))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pointer_partial, directory / "latest.json")
            pointer_partial = None
            # v0.4.54: old full-index copies no longer pile up on the disk.
            pruned = services.prune_derived_generations(directory, keep_digest=digest)
            return {"ok": True, "snapshot": digest, "reused": False, "pruned_generations": pruned}
    except Exception:
        # Fixed reason: never expose SQLite paths or a rejected private value.
        return {"ok": False, "reason": "search_snapshot_refresh_unavailable"}
    finally:
        if source is not None:
            source.close()
        if target is not None:
            target.close()
        for owned in (partial, pointer_partial):
            if owned is not None:
                try:
                    owned.unlink()
                except OSError:
                    pass


@contextmanager
def open_snapshot(root, snapshot):
    if type(snapshot) is not str or not DIGEST.fullmatch(snapshot):
        raise _error("search_cursor_invalid")
    path = _directory(root) / (snapshot + ".sqlite")
    digest, identity = _file_digest(path)
    if digest != snapshot:
        raise _error("search_snapshot_changed")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute("SELECT document FROM wom_search_snapshot_metadata").fetchall()
        meta = json.loads(rows[0][0]) if len(rows) == 1 else None
        if (type(meta) is not dict or meta.get("schema") != SCHEMA
                or meta.get("archive_binding") != _archive_binding(root)
                or meta.get("authoritative_for_writes") is not False):
            raise _error("search_snapshot_invalid")
        yield connection, meta
        if _file_digest(path) != (digest, identity):
            raise _error("search_snapshot_changed")
    finally:
        connection.close()


def cursor_encode(snapshot, binding, offset):
    value = {"schema": CURSOR_SCHEMA, "snapshot": snapshot, "binding": binding, "offset": offset}
    return base64.urlsafe_b64encode(_canonical({**value, "checksum": _sha(value)})).decode().rstrip("=")


def cursor_decode(cursor, binding):
    try:
        if type(cursor) is not str or not 0 < len(cursor) <= 2048:
            raise ValueError()
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        value = json.loads(raw)
        if type(value) is not dict or set(value) != {"schema", "snapshot", "binding", "offset", "checksum"}:
            raise ValueError()
        checksum = value.pop("checksum")
        if (value["schema"] != CURSOR_SCHEMA or value["binding"] != binding
                or type(value["snapshot"]) is not str or not DIGEST.fullmatch(value["snapshot"])
                or type(value["offset"]) is not int or value["offset"] <= 0 or checksum != _sha(value)):
            raise ValueError()
        return value["snapshot"], value["offset"]
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise _error("search_cursor_invalid") from None


def _row(channel, row, query):
    from .archive_services import make_snippet
    if channel == "zettel":
        return dict(type=channel, path=row["path"], id=row["zettel_id"], title=row["title"],
            status=row["status"], kind=row["kind"], snippet=make_snippet(row["body"] or row["frontmatter_json"] or "", query))
    if channel == "object":
        return dict(type=channel, path=row["logical_key"], id=row["object_id"], title=row["logical_key"],
            mime=row["mime"], snippet=make_snippet(row["manifest_json"] or "", query))
    if channel == "derived_text":
        return dict(type=channel, path=row["text_logical_key"], id=row["derived_text_id"], title=row["source_object_id"],
            source_object_id=row["source_object_id"], derivation_kind=row["derivation_kind"],
            review_status=row["review_status"], language=row["language"],
            snippet=make_snippet(row["text_body"] or row["manifest_json"] or "", query))
    if channel == "view":
        return {"type": channel, "path": row["path"], "id": row["view_id"], "title": row["name"],
                "for": row["view_for"], "snippet": make_snippet(row["view_json"] or "", query)}
    return dict(type=channel, path=row["relative_path"] or row["external_url"], id=row["item_id"],
        title=row["relative_path"] or row["external_url"] or row["item_id"], source_id=row["source_id"],
        item_kind=row["item_kind"], scan_status=row["scan_status"], snippet=make_snippet(row["source_json"] or "", query))


def search(root, query, *, limit=100, types=None, cursor=None):
    from .archive_services import ArchiveServiceError
    try:
        return _search(root, query, limit=limit, types=types, cursor=cursor)
    except ArchiveServiceError:
        raise
    except Exception:
        raise _error("search_snapshot_unavailable") from None


def _search(root, query, *, limit, types, cursor):
    from . import archive_services as services
    root = services.require_existing_archive_root(root)
    if type(query) is not str or not query.strip():
        raise _error("search_query_required")
    limit = min(100, max(1, int(limit)))
    selected = tuple(channel for channel in CHANNELS if types is None or channel in types)
    if not selected or (types is not None and any(kind not in CHANNELS for kind in types)):
        raise _error("search_type_invalid")
    binding = _sha({"archive": _archive_binding(root), "query": query, "types": selected, "limit": limit})
    if cursor:
        snapshot, offset = cursor_decode(cursor, binding)
        refresh = {"ok": False, "reason": "cursor_retains_original_generation"}
    else:
        refresh = publish(root)
        snapshot, offset = refresh.get("snapshot") or _latest(root), 0
    if snapshot is None:
        return {**services.blocked_search_result(query, limit=limit,
            index_evidence={"ok": False, "reason_codes": [refresh.get("reason", "search_snapshot_not_ready")]}),
            "next_cursor": None, "next_action": "index"}
    orders = {"zettel": "path", "object": "logical_key, object_id", "derived_text": "text_logical_key, derived_text_id",
              "view": "path", "source_map": "source_id, relative_path, external_url, item_id"}
    results, counts = [], {}
    with open_snapshot(root, snapshot) as (connection, metadata):
        remaining_offset = offset
        for channel, table, where in services.SEARCH_CHANNEL_TABLES:
            if channel not in selected:
                continue
            like = "%" + query.lower() + "%"
            count = int(connection.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", (like,)).fetchone()[0])
            if count:
                counts[channel] = count
            if remaining_offset >= count:
                remaining_offset -= count
                continue
            budget = limit - len(results)
            if budget:
                rows = connection.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY {orders[channel]} LIMIT ? OFFSET ?",
                                          (like, budget, remaining_offset))
                results.extend(_row(channel, row, query) for row in rows)
            remaining_offset = 0
    total = sum(counts.values())
    if offset > total:
        raise _error("search_cursor_invalid")
    remaining = max(0, total - offset - len(results))
    return {"ok": True, "query": query, "count": len(results), "returned": len(results),
        "truncated": remaining > 0, "complete": offset == 0 and remaining == 0,
        "page_sequence_complete": remaining == 0, "total_matches": total, "total_matches_known": True,
        "matches_by_type": counts, "limit_applied": limit, "limit_ceiling": 100, "types": list(selected),
        "offset": offset, "remaining": remaining, "results": results,
        "next_cursor": cursor_encode(snapshot, binding, offset + len(results)) if remaining else None,
        "snapshot": {"sha256": "sha256:" + snapshot, "index_generation": metadata["index_generation"],
            "indexed_at": metadata["indexed_at"], "captured_at": metadata["captured_at"],
            "historical_view": True, "authoritative_for_writes": False},
        "index_evidence": {**metadata["index_evidence"], "evidence_scope": "captured_generation"}, "refresh": refresh,
        "global_absence_proven": False, "remote_preservation_proven": False}
