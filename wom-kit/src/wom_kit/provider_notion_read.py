"""Private PAT worker: bounded authorized media and connection source reads."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import provider_artifacts as artifacts, provider_notion_connections as connections
from .provider_notion_media import discover, fetch_media, open_media


def _pages(call):
    cursor, seen = None, set()
    while True:
        value = call(cursor)
        if not isinstance(value.get("results"), list):
            raise artifacts.ProviderArtifactError("notion_content_list_invalid")
        yield from value["results"]
        if not value.get("has_more"):
            break
        cursor = value.get("next_cursor")
        if not isinstance(cursor, str) or not cursor or cursor in seen:
            raise artifacts.ProviderArtifactError("notion_content_cursor_invalid")
        seen.add(cursor)


def collect(root: Path, *, request, plan, broker, adapter, include_media=True, include_connections=False,
            max_provider_requests=20000, download=open_media, pacer=None):
    """No public tokens or raw responses; root pages come from the approved plan."""
    if type(include_media) is not bool or type(include_connections) is not bool:
        raise artifacts.ProviderArtifactError("notion_content_options_invalid")
    directory = "workbench/notion-content/" + plan.plan_sha256[7:31]
    groups = {group.group_id: group for group in request.groups}
    secrets, provider_calls, items, bindings, candidates, warnings = {}, 0, [], [], [], []
    try:
        for item in plan.selected_items:
            if item.group_id not in secrets:
                secrets[item.group_id] = broker.resolve(groups[item.group_id].scope_binding)
            secret = secrets[item.group_id]
            known, documents = {item.page_id}, {}
            def call(endpoint, invoke):
                nonlocal provider_calls
                if provider_calls >= max_provider_requests:
                    raise artifacts.ProviderArtifactError("notion_content_request_limit")
                if pacer is not None:
                    pacer.before_request()
                secret.revalidate_authority()
                secret.authorize_provider_request(endpoint)
                provider_calls += 1
                response = invoke()
                if response.status != 200 or not isinstance(response.payload, dict):
                    raise artifacts.ProviderArtifactError("notion_content_provider_read_failed")
                return response.payload
            def read(kind, object_id, cursor=None):
                if object_id not in known or kind not in {"page", "block", "children", "comments", "view", "database_views", "data_source_views"}:
                    raise artifacts.ProviderArtifactError("notion_content_target_not_selected")
                value = call("retrieve_source", lambda: adapter.retrieve_source_object(kind, object_id, secret, cursor=cursor))
                documents[(kind, object_id, cursor)] = value
                if kind in {"children", "database_views", "data_source_views"}:
                    for row in value.get("results", []):
                        if isinstance(row, dict) and connections.page_id(row.get("id")):
                            known.add(connections.page_id(row["id"]))
                return value
            media_batch = plan.plan_sha256[7:23] + "-" + item.page_id.replace("-", "")
            if include_media:
                media = fetch_media(root, page_ids=[item.page_id], batch_id=media_batch, read=read, download=download)
                if not media["ok"]:
                    raise artifacts.ProviderArtifactError("notion_content_media_incomplete")
                if media["receipt_path"]:
                    receipt = artifacts.read_json(root, media["receipt_path"])
                    for row in receipt["items"]:
                        media_id = "media-" + row["reference_sha256"][7:31]
                        items.append({"item_id": media_id, "local_path": row["path"], "source_role": "attachment"})
                        bindings.append({"source_page_id": item.page_id, "container_id": row["container_id"],
                            "child_item_id": media_id, "role": "attachment", "pointer": row["pointer"]})
            else:
                # The same traversal discovers nested connections even when
                # downloading attachments was not part of the approved scope.
                discover([item.page_id], read)
            if include_connections:
                page = documents.get(("page", item.page_id, None), {})
                for property_value in page.get("properties", {}).values():
                    if not isinstance(property_value, dict) or property_value.get("type") != "relation" or not property_value.get("has_more"):
                        continue
                    property_id = property_value.get("id")
                    relation_rows = list(_pages(lambda cursor: call("retrieve_page_property", lambda:
                        adapter.retrieve_page_property(item.page_id, property_id, secret, cursor=cursor))))
                    if any(not isinstance(row, dict) or not isinstance(row.get("relation"), dict)
                           or connections.page_id(row["relation"].get("id")) is None for row in relation_rows):
                        raise artifacts.ProviderArtifactError("notion_relation_property_invalid")
                    property_value["relation"] = [row["relation"] for row in relation_rows]
                    property_value["has_more"] = False
                # Read comments for every observed page/block; do not read
                # arbitrary linked targets, which remain evidence only.
                content_ids = sorted(known)
                for object_id in content_ids:
                    list(_pages(lambda cursor: read("comments", object_id, cursor)))
                database_ids = set()
                for (kind, _, _), value in list(documents.items()):
                    if kind == "children":
                        database_ids.update(row["id"] for row in value.get("results", [])
                            if isinstance(row, dict) and row.get("type") == "child_database")
                parent = page.get("parent", {})
                if parent.get("type") == "data_source_id" and connections.page_id(parent.get("data_source_id")):
                    parent_id = connections.page_id(parent["data_source_id"])
                    known.add(parent_id)
                    views = list(_pages(lambda cursor: read("data_source_views", parent_id, cursor)))
                else:
                    views = []
                for database_id in sorted(database_ids):
                    views.extend(_pages(lambda cursor: read("database_views", database_id, cursor)))
                for view in {row["id"]: row for row in views if isinstance(row, dict) and isinstance(row.get("id"), str)}.values():
                    view_id = view["id"]
                    snapshot = connections.materialize_view(view_id, retrieve=lambda key: read("view", key),
                        create_query=lambda key: call("create_view_query", lambda: adapter.query_view(key, secret)),
                        query_page=lambda key, query, cursor: call("retrieve_view_query", lambda: adapter.query_view(key, secret, query_id=query, cursor=cursor)),
                        delete_query=lambda key, query: call("delete_view_query", lambda: adapter.query_view(key, secret, query_id=query, delete=True)),
                        captured_at=datetime.now(timezone.utc).isoformat())
                    documents[("view_query", view_id, None)] = snapshot
            source = {"schema": "wom-kit/notion-private-content-source/v1", "page_id": item.page_id,
                "documents": [{"kind": kind, "id": object_id, "payload": value} for (kind, object_id, _), value in documents.items()]}
            raw = artifacts.canonical(source)
            blob = artifacts.write_blob(root, raw, "json")
            source_item = "notion-source-" + item.page_id.replace("-", "")
            items.append({"item_id": source_item, "local_path": blob["path"], "source_role": "primary_source", "mime": "application/json"})
            bindings.append({"source_page_id": item.page_id, "child_item_id": source_item, "role": "api_source"})
            if include_connections:
                parsed = connections.parse_source(raw, source_ref="source:" + blob["sha256"], source_page_id=item.page_id, format="json")
                candidates.extend(parsed["candidates"])
                warnings.extend(parsed["warnings"])
        paths, aliases = artifacts.write_intake_requests(root, directory, "notion-content-" + plan.plan_sha256[7:23], items)
        receipt_path = directory + "/content-receipt.json"
        artifacts.write_json(root, receipt_path, {"schema": "wom-kit/notion-content-stage/v1", "items": items,
            "bindings": bindings, "candidates": candidates, "warnings": sorted(set(warnings)), "intake_item_aliases": aliases,
            "intake_requests": paths, "provider_calls": provider_calls})
        return {"ok": True, "provider_calls": provider_calls, "item_count": len(items), "candidate_count": len(candidates),
            "intake_requests": paths, "receipt_path": receipt_path, "capture_completed": False}
    finally:
        for secret in secrets.values():
            secret.close()
