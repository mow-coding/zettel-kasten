"""Notion parent-location recovery for `archive notion-recover` (v0.4.44).

`notion-recover` was the owner-requested one-command recovery (2026-06-22,
v0.3.136) of missing parent locations of nested Notion pages: for each leaf in
the reviewed sanitized tree fixture whose parent chain stops before a known
generation root, it asks Notion only for the parent link of the missing
ancestor, walks up until a known root, the workspace, the depth limit or a
cycle, and writes the sanitized ancestor nodes so `notion-ancestor-merge-plan`
can place the leaf again. Its fetch adapter was removed in v0.4.40 and its
legacy approval receipt became plan-only in v0.4.0, so it could not run.

The revival keeps the same scope and output and uses the current parts:
- the adopted Notion credential (the `credential-lifecycle` default, or an
  explicit `--credential-id`) resolved by the receipt-backed broker only in a
  spawned child;
- the one-attempt HTTP adapter's `retrieve_parent` GET, which keeps only the
  object kind, id, block type, parent link and trash flags (never titles,
  bodies, comments or media);
- one exact approval bound to the plan digest (a dialog, or none under a
  valid session grant).
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .notion_page_recovery import (
    NOTION_API_VERSION,
    ScopeBinding,
    _authorize_credential_provider_request,
    _close_resolved_credentials,
    _resolve_credential,
    _revalidate_credential_authority,
)

PLAN_SCHEMA = "wom-kit/notion-ancestor-recovery-plan/v0.1"
RECEIPT_SCHEMA = "wom-kit/notion-ancestor-recovery-receipt/v0.1"
RECEIPT_DIR = "receipts/notion/ancestor-recoveries"
MAX_DEPTH_LIMIT = 64


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


def select_credential(rows: list[Mapping[str, Any]], credential_id: str | None) -> tuple[dict[str, Any] | None, str | None]:
    """(scope binding, blocker) from the authenticated credential rows."""

    notion = [row for row in rows if isinstance(row, Mapping) and row.get("provider") == "notion"]
    if credential_id:
        chosen = [row for row in notion if row.get("credential_id") == credential_id]
    else:
        chosen = [row for row in notion if row.get("is_default") is True]
    if not chosen:
        return None, ("notion_recover_credential_not_found" if credential_id else "notion_recover_default_credential_missing")
    if len(chosen) > 1:
        return None, "notion_recover_default_credential_ambiguous"
    scope = chosen[0].get("scope_binding")
    if not isinstance(scope, Mapping) or scope.get("persisted") is not True or scope.get("workspace_evidence_verified") is not True:
        return None, "notion_recover_credential_not_ready"
    return dict(scope), None


def scope_binding_from(scope: Mapping[str, Any]) -> ScopeBinding:
    return ScopeBinding(
        credential_id=str(scope["credential_id"]),
        workspace_fingerprint=str(scope["workspace_fingerprint"]),
        scope_receipt_sha256=str(scope["scope_receipt_sha256"]),
        revision=str(scope["revision"]),
        persisted=scope.get("persisted") is True,
        workspace_evidence_verified=scope.get("workspace_evidence_verified") is True,
    )


def plan_recovery(
    archive_root: Path | str,
    *,
    scope: Mapping[str, Any] | None,
    scope_blocker: str | None = None,
    tree_path: str | None = None,
    output_path: str | None = None,
    max_items: int = 1000,
    max_depth: int = 16,
) -> dict[str, Any]:
    """Read-only plan: tree selection, the ancestor requests and one digest.

    Reads no credential value and calls no provider. The scope binding comes
    from the authenticated credential listing (content-free).
    """

    from . import archive_services as svc

    root = svc.require_existing_archive_root(archive_root)
    archive_id = svc.read_archive_id(root)
    blockers: list[str] = [scope_blocker] if scope_blocker else []
    warnings: list[str] = []
    if not (isinstance(max_depth, int) and 1 <= max_depth <= MAX_DEPTH_LIMIT):
        blockers.append("notion_recover_max_depth_invalid")
        max_depth = 16
    selection = svc.notion_recover_select_tree_fixture(
        root, tree_path=tree_path, source="notion", max_items=max_items, max_depth=max_depth,
        blockers=blockers, warnings=warnings,
    )
    selected = selection.get("selected_tree_path") or None
    output = svc.notion_ancestor_fetch_output_path(output_path or svc.NOTION_RECOVER_DEFAULT_OUTPUT_PATH, blockers)
    requests: list[dict[str, Any]] = []
    known_roots: list[str] = []
    tree_sha256 = None
    if selected and not blockers:
        crawl = svc.notion_ancestor_crawl_plan(
            root, tree_path=selected, source="notion", dry_run=True, max_items=max_items, max_depth=max_depth,
        )
        for request in crawl.get("crawl_request_queue") or []:
            if not isinstance(request, Mapping):
                continue
            requests.append({
                "request_id": str(request.get("request_id") or ""),
                "ancestor_ref": str(request.get("ancestor_ref") or ""),
                "max_depth": max(1, min(int(request.get("max_depth") or 1), MAX_DEPTH_LIMIT)),
                "affected_root_refs": sorted(str(ref) for ref in request.get("affected_root_refs") or []),
            })
        known_roots = sorted({
            ref
            for ref in (
                svc.notion_canonical_provider_ref(str(item.get("root_ref") or ""))
                for item in crawl.get("generation_roots") or []
                if isinstance(item, Mapping)
            )
            if ref
        })
        tree_sha256 = "sha256:" + hashlib.sha256(svc.archive_internal_path(root, selected).read_bytes()).hexdigest()
    if output and svc.archive_internal_path(root, output).exists():
        blockers.append("notion_recover_output_exists")
    scope_public = None
    if scope is not None:
        scope_public = {key: scope.get(key) for key in ("credential_id", "workspace_fingerprint",
                                                        "scope_receipt_sha256", "revision")}
    request_sha256 = _digest({"archive_id": archive_id, "tree_path": selected, "tree_sha256": tree_sha256,
                              "scope": scope_public})
    plan_sha256 = _digest({
        "schema": PLAN_SCHEMA, "request_sha256": request_sha256, "requests": requests,
        "known_generation_root_refs": known_roots, "output_path": output, "api_version": NOTION_API_VERSION,
    })
    budget = sum(item["max_depth"] for item in requests)
    return {
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "notion_recover",
        "recover_state": ("blocked" if blockers else ("ready_for_approval" if requests else "no_missing_locations")),
        "plan_sha256": plan_sha256,
        "request_sha256": request_sha256,
        "selected_tree_path": selected,
        "location_request_count": len(requests),
        "max_provider_requests": budget,
        "output_path": output,
        "would_write": ([output, f"{RECEIPT_DIR}/<plan>.json"] if requests and not blockers else []),
        "reads": "parent links only (object kind, id, parent, trash flags); no titles, bodies, comments or media",
        "credential": "adopted Notion credential (credential-lifecycle default or --credential-id)",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "provider_calls": 0,
        "credential_values_read": False,
        "next_step": (
            "archive notion-recover <archive-root> --approve --reviewed-by person:<you>"
            if requests and not blockers else None
        ),
        "_requests": requests,
        "_known_roots": known_roots,
        "_scope": dict(scope) if scope is not None else None,
    }


def public(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if not key.startswith("_")}


def _walk(request: Mapping[str, Any], *, known_roots: set[str], get_parent: Callable[[str, str], Any],
          fetched: dict[str, dict[str, Any]]) -> dict[str, Any]:
    from . import archive_services as svc

    current = svc.notion_canonical_provider_ref(str(request.get("ancestor_ref") or ""))
    roots = set(known_roots) | {
        ref for ref in (svc.notion_canonical_provider_ref(value) for value in request.get("affected_root_refs") or [])
        if ref
    }
    visited: list[str] = []
    fetched_refs: list[str] = []
    calls = 0
    stop = "parent_ref_missing_or_ambiguous"
    partial = False
    if not current:
        return {"request_id": request.get("request_id"), "stop_condition": "unsafe_ref_or_provider_secret_detected",
                "partial": True, "provider_calls": 0, "fetched_node_count": 0}
    for _ in range(int(request.get("max_depth") or 1)):
        if current in visited:
            partial = True
            break
        kind, provider_id = current.split(":", 1)
        response = get_parent(kind, provider_id)
        calls += 1
        status = getattr(response, "status", None)
        if status != 200:
            stop = {401: "credential_unauthorized", 403: "provider_access_denied",
                    404: "not_found_or_not_shared", 429: "provider_rate_limited"}.get(status, "provider_request_failed")
            partial = True
            break
        payload = dict(getattr(response, "payload", {}) or {})
        node, parent_ref, parent_stop = svc.notion_sanitized_ancestor_node_from_response(payload, fallback_ref=current)
        if not node:
            stop = parent_stop or "parent_ref_missing_or_ambiguous"
            partial = True
            break
        node_ref = str(node.get("node_ref") or "")
        fetched.setdefault(node_ref, node)
        fetched_refs.append(node_ref)
        visited.append(current)
        if node_ref in roots or (parent_ref and parent_ref in roots):
            stop = "known_generation_root_ref_reached"
            break
        if not parent_ref:
            stop = parent_stop or "space_or_workspace_root_reached"
            break
        current = svc.notion_canonical_provider_ref(parent_ref)
        if not current:
            partial = True
            break
    else:
        stop = "max_depth_reached"
        partial = True
    return {"request_id": request.get("request_id"), "stop_condition": stop, "partial": partial,
            "provider_calls": calls, "fetched_node_count": len(fetched_refs)}


def execute_recovery(
    archive_root: Path | str,
    *,
    expected_plan_sha256: str,
    scope: Mapping[str, Any],
    provider: Any,
    credential_broker: Any,
    tree_path: str | None = None,
    output_path: str | None = None,
    max_items: int = 1000,
    max_depth: int = 16,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Re-plan, refuse drift, walk every request with GET-only parent reads,
    write the sanitized ancestor fixture and a content-free receipt."""

    from . import archive_services as svc

    plan = plan_recovery(archive_root, scope=scope, tree_path=tree_path, output_path=output_path,
                         max_items=max_items, max_depth=max_depth)
    if plan["ok"] is not True:
        return {**public(plan), "dry_run": False, "reason_code": plan["blockers"][0]}
    if plan["plan_sha256"] != expected_plan_sha256:
        return {**public(plan), "dry_run": False, "ok": False, "reason_code": "notion_recover_plan_changed",
                "blockers": ["notion_recover_plan_changed"]}
    root = svc.require_existing_archive_root(archive_root)
    binding = scope_binding_from(scope)
    fetched: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    credentials: list[object] = []
    stop_reason = None
    try:
        credential = _resolve_credential(credential_broker, binding)
        credentials.append(credential)

        def get_parent(kind: str, provider_id: str) -> Any:
            _revalidate_credential_authority(credential)
            _authorize_credential_provider_request(credential, "retrieve_parent")
            return provider.retrieve_parent(kind, provider_id, credential, api_version=NOTION_API_VERSION)

        known = set(plan["_known_roots"])
        for request in plan["_requests"]:
            outcome = _walk(request, known_roots=known, get_parent=get_parent, fetched=fetched)
            results.append(outcome)
            if outcome["stop_condition"] == "credential_unauthorized":
                stop_reason = "notion_recover_credential_unauthorized"
                break
    except Exception:
        stop_reason = stop_reason or "notion_recover_execution_failed"
    finally:
        credentials_closed = _close_resolved_credentials(credentials)
    now = (clock() if clock else datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    output = plan["output_path"]
    files_written: list[str] = []
    if fetched:
        svc.write_json_new_file(svc.archive_internal_path(root, output), {
            "fixture_kind": "notion_ancestor_result_fixture",
            "source": "notion",
            "nodes": list(fetched.values()),
        })
        files_written.append(output)
    receipt_rel = f"{RECEIPT_DIR}/{plan['plan_sha256'].split(':', 1)[1][:24]}.json"
    stops: dict[str, int] = {}
    for item in results:
        stops[item["stop_condition"]] = stops.get(item["stop_condition"], 0) + 1
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "archive_id": svc.read_archive_id(root),
        "plan_sha256": plan["plan_sha256"],
        "request_sha256": plan["request_sha256"],
        "completed_at": now.isoformat().replace("+00:00", "Z"),
        "status": "failed" if stop_reason else ("partial" if any(item["partial"] for item in results) else "succeeded"),
        "stop_reason": stop_reason,
        "request_count": len(plan["_requests"]),
        "processed_request_count": len(results),
        "fetched_node_count": len(fetched),
        "provider_calls": sum(item["provider_calls"] for item in results),
        "stop_conditions": dict(sorted(stops.items())),
        "output_path": output if fetched else None,
        "titles_or_bodies_read": False,
    }
    receipt_path = svc.archive_internal_path(root, receipt_rel)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    svc.write_json_new_file(receipt_path, receipt)
    files_written.append(receipt_rel)
    return {
        **public(plan),
        "ok": stop_reason is None,
        "dry_run": False,
        "reason_code": stop_reason or "notion_recover_completed",
        "blockers": [stop_reason] if stop_reason else [],
        "status": receipt["status"],
        "fetched_node_count": len(fetched),
        "provider_calls": receipt["provider_calls"],
        "stop_conditions": receipt["stop_conditions"],
        "files_written": files_written,
        "receipt_path": receipt_rel,
        "credentials_closed": credentials_closed,
        "next_step": (
            f"archive notion-ancestor-merge-plan <archive-root> --tree {plan['selected_tree_path']} --ancestors {output} --dry-run"
            if fetched else None
        ),
    }
