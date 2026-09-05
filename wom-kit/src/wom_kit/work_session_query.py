"""Content-free, generation-bound registry queries, never ownership authority.

Private labels and claim tokens stay in the registry. A complete registry
snapshot says nothing about the attribution of legacy archive artifacts.
Readers do not take the writer lock or create registry/operation files.
"""

from pathlib import Path

from . import exact_human_approval as approval
from . import work_session_registry as registry
from .snapshot_pagination import SnapshotPager, SnapshotPaginationError, content_sha256
from .work_session_binding import WorkSessionBinding


QUERY_SCHEMA = "wom-kit/work-session-query/v1"
MAX_PAGE_SIZE = 2000
_KINDS = {"app": ("apps", "client_app"), "workstream": ("workstreams", "workstream"),
          "session": ("sessions", "work_session")}
_ERRORS = frozenset({"work_session_query_invalid", "work_session_query_unavailable",
                     "work_session_query_changed", "work_session_query_not_found",
                     "snapshot_pagination_cursor_invalid", "snapshot_pagination_query_changed",
                     "snapshot_pagination_generation_changed"})


class WorkSessionQueryError(ValueError):
    def __init__(self, code="work_session_query_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_query_invalid"
        super().__init__(self.code)


def _capture(root):
    archive_root, archive_id = approval._archive_identity(root)
    archive_sha = approval.exact_human_approval_archive_identity_sha256(archive_id)
    store = registry.WorkSessionRegistryStore(Path(archive_root), archive_sha)
    snapshot = store.read()
    # The store binds its directory chain; independently refuse archive identity
    # drift around the read. New registry generations do not invalidate an
    # already complete snapshot, but a cursor must match on the next call.
    final_root, final_id = approval._archive_identity(root)
    if final_root != archive_root or final_id != archive_id:
        raise WorkSessionQueryError("work_session_query_changed")
    return snapshot


def _row(document, kind, reference):
    table, _prefix = _KINDS[kind]
    value = document[table][reference]
    row = {"kind": kind, "ref": reference}
    if kind == "app":
        row.update(identity_level=value["identity_level"],
                   label_sha256=registry._label_digest(value["label"]),
                   identity_is_app_attestation=False)
    elif kind == "workstream":
        row.update(active_session_ref=value["active_session_ref"],
                   label_sha256=registry._label_digest(value["label"]))
    else:
        row.update({name: value[name] for name in (
            "client_app_ref", "workstream_ref", "revision", "state", "predecessor_ref", "handoff_app_ref",
        )})
        row["ownership_state_is_write_authority"] = False
    return row


def _base(snapshot):
    return {"schema": QUERY_SCHEMA, "ok": True, "read_only": True,
            "registry": snapshot.public_summary(), "scope": "work_session_registry_only",
            "artifact_attribution_evaluated": False, "private_labels_echoed": False,
            "claim_tokens_echoed": False, "query_is_write_authority": False}


def _list(snapshot, *, kind, client_app_ref, workstream_ref, page_size, cursor):
    if (type(kind) is not str or kind not in _KINDS or type(page_size) is not int
            or not 1 <= page_size <= MAX_PAGE_SIZE):
        raise WorkSessionQueryError()
    if kind != "session" and (client_app_ref is not None or workstream_ref is not None):
        raise WorkSessionQueryError()
    for reference, prefix in ((client_app_ref, "client_app"), (workstream_ref, "workstream")):
        if reference is not None and not registry._ref(reference, prefix):
            raise WorkSessionQueryError()
    document = snapshot._document
    if ((client_app_ref is not None and client_app_ref not in document["apps"])
            or (workstream_ref is not None and workstream_ref not in document["workstreams"])):
        raise WorkSessionQueryError("work_session_query_not_found")
    table, _prefix = _KINDS[kind]
    rows = []
    for reference, value in sorted(document[table].items()):
        if kind == "session" and (
            (client_app_ref is not None and value["client_app_ref"] != client_app_ref)
            or (workstream_ref is not None and value["workstream_ref"] != workstream_ref)
        ):
            continue
        rows.append(_row(document, kind, reference))
    query = {"schema": QUERY_SCHEMA, "action": "list", "kind": kind,
             "client_app_ref": client_app_ref, "workstream_ref": workstream_ref}
    pager = SnapshotPager.build(rows, generation_sha256=snapshot.sha256, query_sha256=content_sha256(query))
    return {**_base(snapshot), "action": "list", "kind": kind,
            "counts": {"registry_kind_total": len(document[table]), "selected": len(rows),
                       "excluded_by_filters": len(document[table]) - len(rows)},
            **pager.page(page_size=page_size, cursor=cursor)}


def _inspect(snapshot, *, kind, reference):
    if type(kind) is not str or kind not in _KINDS:
        raise WorkSessionQueryError()
    table, prefix = _KINDS[kind]
    if not registry._ref(reference, prefix):
        raise WorkSessionQueryError()
    document = snapshot._document
    if reference not in document[table]:
        raise WorkSessionQueryError("work_session_query_not_found")
    row = _row(document, kind, reference)
    if kind == "session":
        value = document[table][reference]
        # Build from this already validated frozen generation, not another disk
        # lookup or validation of the entire registry for every returned row.
        row["binding"] = WorkSessionBinding.build(
            client_app_ref=value["client_app_ref"], workstream_ref=value["workstream_ref"],
            work_session_ref=reference, revision=value["revision"],
            archive_identity_sha256=document["archive_identity_sha256"],
            client_app_label_sha256=registry._label_digest(document["apps"][value["client_app_ref"]]["label"]),
            workstream_label_sha256=registry._label_digest(document["workstreams"][value["workstream_ref"]]["label"]),
        ).document()
    return {**_base(snapshot), "action": "inspect", "kind": kind, "item": row}


def query_work_sessions(root, *, action="list", kind="session", reference=None,
                        client_app_ref=None, workstream_ref=None, page_size=20, cursor=None):
    """Public read service: no native prompt, claim/key lookup, writes or provider.

Opaque filters and cursor are routing data only. Unknown refs are not silently
treated as an empty project, and all exceptions leave only fixed public codes.
"""
    code = "work_session_query_unavailable"
    try:
        if type(action) is not str or action not in {"list", "inspect"}:
            raise WorkSessionQueryError()
        if (action == "list" and reference is not None) or (action == "inspect" and (
                client_app_ref is not None or workstream_ref is not None or cursor is not None)):
            raise WorkSessionQueryError()
        snapshot = _capture(root)
        if action == "list":
            return _list(snapshot, kind=kind, client_app_ref=client_app_ref,
                         workstream_ref=workstream_ref, page_size=page_size, cursor=cursor)
        return _inspect(snapshot, kind=kind, reference=reference)
    except (WorkSessionQueryError, SnapshotPaginationError) as error:
        code = error.code
    except Exception:
        pass
    # Raise outside the handler to avoid attaching private exceptions/context.
    raise WorkSessionQueryError(code)
