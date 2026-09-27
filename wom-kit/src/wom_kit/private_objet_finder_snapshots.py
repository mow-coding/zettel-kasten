"""Private finder generations validated by the original C1-C11 lifecycle.

No queries or query results are persisted. The SQLite copy contains the same
private projections as the generated index and is only historical read evidence.
"""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
import os
import sqlite3
import uuid

from . import archive_services as services, search_snapshots as common
from . import private_objet_metadata_index_health as health
from .private_objet_metadata_index_session import _PrivateObjetIndexReadAPI, _sqlite_read_authorizer

SCHEMA = "wom-kit/private-finder-generation/v1"


def directory(root, *, create=False):
    from .exact_operation_manifest import _ensure_private_directory
    from .source_intake_batch_exact import _reject_link_or_reparse_chain
    if create:
        return _ensure_private_directory(root, ("db", "finder-snapshots"))
    result = root / "db/finder-snapshots"
    _reject_link_or_reparse_chain(result, code="search_snapshot_invalid")
    return result


def latest(root):
    from .exact_operation_manifest import _read_plain_file
    if not (root / "db/finder-snapshots").exists():
        return None
    path = directory(root) / "latest.json"
    if not path.exists():
        return None
    doc = json.loads(_read_plain_file(path, max_bytes=4096, heartbeat=lambda: None))
    if (type(doc) is not dict or set(doc) != {"schema", "snapshot"} or doc["schema"] != SCHEMA
            or type(doc["snapshot"]) is not str or not common.DIGEST.fullmatch(doc["snapshot"])):
        raise common._error("search_snapshot_invalid")
    return doc["snapshot"]


def publish(root, archive_id):
    from .operation_target_leases import TargetLease
    from .object_storage_restore import _atomic_move_file_no_replace
    partial = pointer = None
    try:
        with TargetLease(root, kind="file", reference="db/finder-snapshots/latest.json", timeout_seconds=0):
            folder = directory(root, create=True)
            partial = folder / (uuid.uuid4().hex + ".building")
            with partial.open("xb"):
                pass
            copied = False
            def consumer(api, evidence):
                nonlocal copied
                if health._case_id_from_envelope(evidence) in {"C10", "C11"}:
                    api._copy_pinned_generation(partial)
                    copied = True
            decision = health._evaluate_private_objet_metadata_index_with_consumer(root, archive_id, consumer)
            if not copied or decision.case_id not in {"C10", "C11"}:
                return {"ok": False, "decision": decision}
            metadata = {"schema": SCHEMA, "archive_binding": common._archive_binding(root),
                "captured_at": datetime.now(timezone.utc).isoformat(), "health": decision.envelope,
                "case_id": decision.case_id, "authoritative_for_writes": False}
            with closing(sqlite3.connect(partial)) as connection:
                connection.execute("CREATE TABLE wom_finder_snapshot_metadata (document TEXT NOT NULL)")
                connection.execute("INSERT INTO wom_finder_snapshot_metadata VALUES (?)", (json.dumps(metadata),))
                connection.commit()
            with partial.open("r+b") as stream:
                os.fsync(stream.fileno())
            digest, _ = common._file_digest(partial)
            _atomic_move_file_no_replace(partial, folder / (digest + ".sqlite"))
            partial = None
            pointer = folder / (uuid.uuid4().hex + ".pointer")
            with pointer.open("xb") as stream:
                stream.write(common._canonical({"schema": SCHEMA, "snapshot": digest}))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pointer, folder / "latest.json")
            pointer = None
            return {"ok": True, "snapshot": digest}
    except Exception:
        return {"ok": False, "decision": health.unavailable_private_objet_metadata_index_health()}
    finally:
        for path in (partial, pointer):
            if path is not None:
                try:
                    path.unlink()
                except OSError:
                    pass


@contextmanager
def open_generation(root, snapshot):
    if type(snapshot) is not str or not common.DIGEST.fullmatch(snapshot):
        raise common._error("search_cursor_invalid")
    path = directory(root) / (snapshot + ".sqlite")
    before = common._file_digest(path)
    if before[0] != snapshot:
        raise common._error("search_snapshot_changed")
    connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
    api = None
    try:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute("SELECT document FROM wom_finder_snapshot_metadata").fetchall()
        doc = json.loads(rows[0][0]) if len(rows) == 1 else None
        if (type(doc) is not dict or doc.get("schema") != SCHEMA
                or doc.get("archive_binding") != common._archive_binding(root)
                or doc.get("authoritative_for_writes") is not False
                or doc.get("case_id") not in {"C10", "C11"}
                or health._case_id_from_envelope(doc["health"]) != doc["case_id"]):
            raise common._error("search_snapshot_invalid")
        decision = health._decision(doc["case_id"], doc["health"])
        connection.execute("BEGIN")
        connection.set_authorizer(_sqlite_read_authorizer)
        api = _PrivateObjetIndexReadAPI(connection)
        yield api, decision, doc
        if common._file_digest(path) != before:
            raise common._error("search_snapshot_changed")
    finally:
        if api is not None:
            api._deactivate()
        connection.close()
