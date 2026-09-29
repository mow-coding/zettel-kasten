"""Real Notion source parsers; mechanism evidence remains distinct from meaning.

Local exports may omit a mechanism. Missing evidence is an explicit coverage
gap, not a guessed relationship. The module prepares the established batch
writer input and never authorizes or writes canonical edges itself.
"""
from __future__ import annotations

import csv
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import uuid

from . import provider_artifacts as artifacts

KINDS = {"relation_property", "synced_block_reference", "database_view_filter", "internal_url_hyperlink", "mention_page", "comment_context"}
LENSES = {"mechanism_lens", "meaning_lens", "strict_zettelkasten_lens"}


def page_id(value):
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        pass
    parsed = urlsplit(value)
    if parsed.scheme and parsed.hostname not in {"notion.so", "www.notion.so", "notion.site", "www.notion.site"} and not (parsed.hostname or "").endswith(".notion.site"):
        return None
    match = re.search(r"([0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})(?:[./?#]|$)", unquote(parsed.path))
    return str(uuid.UUID(match.group(1))) if match else None


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(value for key, value in attrs if key == "href" and value)


def parse_source(raw: bytes, *, source_ref: str, source_page_id: str, format: str,
                 relation_columns: dict[str, str] | list[str] | None = None) -> dict:
    if isinstance(relation_columns, list):
        mapping = {}
        for entry in relation_columns:
            if not isinstance(entry, str):
                raise artifacts.ProviderArtifactError("notion_relation_column_binding_invalid")
            column, separator, property_id = entry.partition("=")
            if not separator or not column or not property_id or column in mapping:
                raise artifacts.ProviderArtifactError("notion_relation_column_binding_invalid")
            mapping[column] = property_id
        relation_columns = mapping
    if relation_columns is not None and (not isinstance(relation_columns, dict)
            or any(not isinstance(key, str) or not key or not isinstance(value, str) or not value for key, value in relation_columns.items())):
        raise artifacts.ProviderArtifactError("notion_relation_column_binding_invalid")
    source_id = page_id(source_page_id)
    if source_id is None:
        raise artifacts.ProviderArtifactError("notion_connection_source_id_invalid")
    basis = artifacts.digest(raw)
    candidates, warnings = [], []

    def add(kind, target, pointer, detail=None):
        normalized = page_id(target)
        if normalized is None:
            warnings.append("notion_connection_target_unresolved")
            return
        candidate = {"connection_kind": kind, "source_page_id": source_id, "target_page_id": normalized,
            "source_ref": source_ref, "source_sha256": basis, "pointer": pointer, "evidence": detail or {},
            "meaning": None, "requires_human_review": True}
        candidate["candidate_id"] = "candidate:" + artifacts.digest(artifacts.canonical(candidate))[7:39]
        candidates.append(candidate)

    def walk(value, pointer=""):
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, pointer + "/" + str(index))
        elif isinstance(value, dict):
            kind = value.get("type")
            if kind == "relation" and isinstance(value.get("relation"), list):
                for index, relation in enumerate(value["relation"]):
                    add("relation_property", relation.get("id"), pointer + "/relation/" + str(index), {"property_id": value.get("id")})
                if value.get("has_more"):
                    warnings.append("notion_relation_pagination_required")
            if kind == "synced_block":
                original = value.get("synced_block", {}).get("synced_from")
                if isinstance(original, dict):
                    add("synced_block_reference", original.get("block_id"), pointer + "/synced_block/synced_from")
            if kind == "mention" and isinstance(value.get("mention"), dict):
                mention = value["mention"]
                target = mention.get("page", mention.get("database", {})).get("id")
                if target:
                    add("mention_page", target, pointer + "/mention")
            if value.get("object") == "comment":
                parent = value.get("parent", {})
                target = parent.get("page_id", parent.get("block_id"))
                if target:
                    add("comment_context", target, pointer, {"comment_id": value.get("id"), "discussion_id": value.get("discussion_id")})
            if value.get("object") == "view_query":
                for index, result in enumerate(value.get("results", [])):
                    add("database_view_filter", result.get("id"), pointer + "/results/" + str(index),
                        {"view_id": value.get("view_id"), "query_id": value.get("id"), "captured_at": value.get("captured_at"),
                         "configuration": value.get("configuration"), "result_snapshot_sha256": basis})
                if value.get("has_more"):
                    warnings.append("notion_view_query_incomplete")
            if isinstance(value.get("href"), str) and page_id(value["href"]):
                add("internal_url_hyperlink", value["href"], pointer + "/href")
            link = value.get("text", {}).get("link") if isinstance(value.get("text"), dict) else None
            if isinstance(link, dict) and page_id(link.get("url")):
                add("internal_url_hyperlink", link["url"], pointer + "/text/link")
            for key, child in value.items():
                walk(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))

    try:
        text = raw.decode("utf-8-sig")
        if format == "json":
            walk(json.loads(text))
        elif format in {"html", "markdown"}:
            if format == "html":
                parser = _Links()
                parser.feed(text)
                links = parser.links
            else:
                links = re.findall(r"\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", text)
            for index, link in enumerate(links):
                if page_id(link):
                    add("internal_url_hyperlink", link, "/links/" + str(index))
        elif format == "csv":
            if not relation_columns:
                warnings.append("notion_csv_relation_schema_required")
            for index, row in enumerate(csv.DictReader(io.StringIO(text))):
                for column, property_id in (relation_columns or {}).items():
                    for target in re.findall(r"(?:https://[^\s,]+|[0-9a-fA-F-]{32,36})", row.get(column, "")):
                        add("relation_property", target, f"/rows/{index}/{column}", {"property_id": property_id})
        else:
            raise artifacts.ProviderArtifactError("notion_connection_format_invalid")
    except (UnicodeError, ValueError, TypeError, AttributeError):
        raise artifacts.ProviderArtifactError("notion_connection_source_malformed") from None
    candidates = list({row["candidate_id"]: row for row in candidates}.values())
    observed = {row["connection_kind"] for row in candidates}
    return {"schema": "wom-kit/notion-connection-candidates/v1", "source_ref": source_ref,
        "source_sha256": basis, "candidates": candidates, "observed_kinds": sorted(observed),
        "unobserved_kinds": sorted(KINDS - observed), "warnings": sorted(set(warnings)), "edges_written": 0}


def materialize_view(view_id, *, retrieve, create_query, query_page, delete_query, captured_at: str) -> dict:
    """A single cached query generation; never splice pages across queries."""
    configuration = retrieve(view_id)
    query = create_query(view_id)
    query_id = query.get("id")
    if not isinstance(query_id, str) or not isinstance(query.get("results"), list):
        raise artifacts.ProviderArtifactError("notion_view_query_malformed")
    rows, cursors = list(query["results"]), set()
    try:
        while query.get("has_more"):
            cursor = query.get("next_cursor")
            if not isinstance(cursor, str) or not cursor or cursor in cursors:
                raise artifacts.ProviderArtifactError("notion_view_query_cursor_invalid")
            cursors.add(cursor)
            query = query_page(view_id, query_id, cursor)
            if query.get("id", query_id) != query_id or not isinstance(query.get("results"), list):
                raise artifacts.ProviderArtifactError("notion_view_query_generation_changed")
            rows.extend(query["results"])
        return {"object": "view_query", "id": query_id, "view_id": view_id, "configuration": configuration,
            "results": rows, "captured_at": captured_at, "has_more": False,
            "result_sha256": artifacts.digest(artifacts.canonical(rows))}
    finally:
        delete_query(view_id, query_id)


def reviewed_edge_plan(candidates: list[dict], judgments: list[dict], bindings: dict[str, str]) -> dict:
    """Host AI judgments are inputs with provenance, never fabricated here."""
    by_id = {row["candidate_id"]: row for row in judgments}
    edges, pending = [], []
    for candidate in candidates:
        decision = by_id.get(candidate["candidate_id"], {})
        lenses = decision.get("lenses", {})
        provenance = decision.get("model_provenance", {})
        valid = (set(lenses) == LENSES and all(isinstance(lenses[name], dict) and lenses[name].get("evidence_ref") == candidate["source_ref"] for name in LENSES)
            and all(provenance.get(key) for key in ("provider", "model", "run_id"))
            and decision.get("source_sha256") == candidate["source_sha256"]
            and decision.get("review_status") == "approved")
        meanings = {lenses[name].get("edge_type") for name in LENSES} if valid else set()
        directions = {lenses[name].get("direction") for name in LENSES} if valid else set()
        source, target = bindings.get(candidate["source_page_id"]), bindings.get(candidate["target_page_id"])
        if (not valid or len(meanings) != 1 or not next(iter(meanings), None) or not source or not target
                or len(directions) != 1 or next(iter(directions), None) not in {"source_to_target", "target_to_source"}):
            pending.append(candidate["candidate_id"])
            continue
        if directions == {"target_to_source"}:
            source, target = target, source
        edges.append({"candidate_id": candidate["candidate_id"], "from_zettel": source, "target": target,
            "edge_type": next(iter(meanings)), "visibility": "private", "confidence": "high",
            "review_status": "approved", "requires_human_review": False, "evidence_ref": candidate["source_ref"]})
    unique, provenance = {}, {}
    for edge in edges:
        key = (edge["from_zettel"], edge["edge_type"], edge["target"], edge["visibility"])
        retained = unique.setdefault(key, edge)
        provenance.setdefault(retained["candidate_id"], []).append(edge["candidate_id"])
    edges = list(unique.values())
    return {"policy": {"policy_id": "policy:notion-reviewed-connections", "auto_write_edge_types": sorted({edge["edge_type"] for edge in edges}),
        "minimum_confidence": "high", "ambiguous_edges_to_review_queue": True}, "edges": edges,
        "pending_candidate_ids": pending, "edge_candidate_provenance": provenance, "edges_written": 0}
