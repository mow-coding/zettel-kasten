"""Approved provider content composition using the existing canonical writers.

Provider staging, canonical capture, derived-text registration and semantic
edge writing retain their own exact approval receipts. No secret is accepted
as a public argument and no local provider path grants canonical authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

from . import archive_services as services, provider_artifacts as artifacts
from . import objet_capture_batch_exact as capture, source_intake_batch_exact as intake
from .exact_human_approval_windows import ExactHumanApprovalOperation as Operation
from .exact_human_approval_workflow import _execute_exact_human_approved_write
from .operation_approval_binding import plan_digest_approval_binding, zettel_edge_batch_approval_binding


def _approve(root, operation, plan, reviewer, write, *, binding=None):
    if not plan.get("ok") or plan.get("blockers"):
        return {**plan, "ok": False, "dry_run": False}
    binding = binding or plan_digest_approval_binding(operation, plan["plan_sha256"])
    context = binding.context(archive_id=services.read_archive_id(root), reviewer_claim=reviewer)
    def guarded(claim):
        services._require_exact_human_operation_approval(root, binding, reviewer_claim=reviewer,
            expected_plan_sha256=binding.plan_sha256, expected_target_binding_sha256=binding.target_binding_sha256, claim=claim)
        return write(binding, claim)
    return _execute_exact_human_approved_write(root, context, guarded)


def _source(root, relative, *, max_bytes=64 * 1024 * 1024):
    path = artifacts.safe_path(root, relative)
    raw, reason = services._bounded_stable_regular_file_read(path, max_bytes=max_bytes)
    if raw is None or reason:
        raise artifacts.ProviderArtifactError("provider_source_unavailable")
    return raw


def _object_verified(root, object_id):
    resolution = services.resolve_objet_ref(root, object_id=object_id, dry_run=True)
    if not resolution.get("local_openable"):
        raise artifacts.ProviderArtifactError("provider_canonical_object_unavailable")
    records = services.load_manifest_records(root)
    for row in records:
        if row.get("object_id") == object_id:
            for location in row.get("locations", []):
                if location.get("provider") == "local" and isinstance(location.get("path"), str):
                    path = artifacts.safe_path(root, location["path"])
                    sha = hashlib.sha256()
                    with open(path, "rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            sha.update(chunk)
                    if "sha256:" + sha.hexdigest() == object_id:
                        return location["path"]
    raise artifacts.ProviderArtifactError("provider_canonical_object_hash_mismatch")


def _reuse_or_resume_intake(plan, *, reviewed_by, key_provider=None):
    """Discover hints only; the existing signed completion verifier is authority."""
    from .exact_operation_manifest import EXACT_OPERATION_RECEIPTS_ROOT, ExactOperationManifestError, load_exact_operation_final_receipt_read_only
    if not plan.resume_candidate or plan.manifest is None:
        return None
    directory = artifacts.safe_path(plan.archive_root, EXACT_OPERATION_RECEIPTS_ROOT + "/.provider-read-probe").parent
    if directory.is_dir():
        with services._activity_group_bound_directory_chain(plan.archive_root, directory, create=False):
            names = os.listdir(directory)
            if len(names) > 100000:
                raise artifacts.ProviderArtifactError("provider_intake_discovery_limit")
            for name in sorted(names):
                if not re.fullmatch(r"[a-f0-9]{64}\.json", name):
                    continue
                execution = "sha256:" + name[:-5]
                try:
                    final = load_exact_operation_final_receipt_read_only(plan.archive_root, execution)
                except ExactOperationManifestError:
                    continue
                result = final.get("result", {}) if final else {}
                if result.get("manifest_sha256") != plan.manifest.manifest_sha256:
                    continue
                verified = intake.reconcile_source_intake_batch(plan, execution_sha256=execution, key_provider=key_provider)
                if verified.get("ok"):
                    return {**verified, "authenticated_completion_reused": True}
    try:
        return intake.resume_source_intake_batch_auto(plan, reviewer_claim=reviewed_by, key_provider=key_provider)
    except intake.SourceIntakeBatchExactError:
        return None


def capture_staged_content(root, staged, *, reviewed_by, bindings=(), text_sources=(), receipt_name,
                           claim_key_provider=None):
    """Keep durable staging/recovery evidence if a later completion step fails."""
    try:
        return _capture_staged_content(root, staged, reviewed_by=reviewed_by, bindings=bindings,
            text_sources=text_sources, receipt_name=receipt_name, claim_key_provider=claim_key_provider)
    except Exception as error:
        # Existing canonical exceptions can carry local paths or provider text.
        # Only these locally authored content-free codes cross this boundary.
        allowed = {"provider_canonical_object_unavailable", "provider_canonical_object_hash_mismatch",
            "provider_attachment_binding_unresolved", "provider_text_binding_unresolved",
            "provider_search_verification_failed", "provider_object_search_verification_failed",
            "provider_source_receipt_changed", "provider_artifact_collision", "provider_artifact_path_unsafe",
            "provider_intake_reuse_evidence_changed"}
        code = error.code if type(error) is artifacts.ProviderArtifactError and error.code in allowed else "provider_content_completion_failed"
        return {"ok": False, "reason_code": code, "capture_completed": False, "search_verified": False,
            "source_staging_completed": True, "staging_receipt_path": staged.get("receipt_path"),
            "effects_state": "partial_or_unknown", "writes_may_have_occurred": True}


def _capture_staged_content(root, staged, *, reviewed_by, bindings=(), text_sources=(), receipt_name,
                            claim_key_provider=None):
    """Complete provider manifests without manual JSON editing.

    bindings contain parent_object_id or parent_item_id plus child_item_id.
    text_sources contain item_id and source_item_id, keeping a transcript
    attached to its preserved source rather than claiming it is the original.
    """
    root = services.require_existing_archive_root(root)
    # A first-use Notion recovery creates its canonical parent objects before
    # this composition starts; refresh the established index before intake.
    services.index_archive(root)
    item_objects, item_paths, executions, reused_intakes = {}, {}, [], []
    for path in staged.get("intake_requests", []):
        request = artifacts.read_json(root, path)
        item_paths.update({row["item_id"]: row["local_path"] for row in request["items"]})
        planned = intake.plan_source_intake_batch(root, path)
        received = (_reuse_or_resume_intake(planned, reviewed_by=reviewed_by, key_provider=claim_key_provider)
            if not planned.approveable else None)
        if received is None and not planned.approveable:
            from . import provider_intake_reuse
            strategy = provider_intake_reuse.discover(planned, key_provider=claim_key_provider)
            if strategy is None:
                return {"ok": False, "reason_code": "provider_intake_blocked", "capture_completed": False,
                    "intake_plan": planned.public_document(), "staging_receipt_path": staged.get("receipt_path"), "effects_state": "partial_or_unknown"}
            def publish_reuse(_binding, _claim):
                for proof in strategy["reused_items"]:
                    _object_verified(root, proof["object_id"])
                return provider_intake_reuse.publish_new_request(planned, strategy, key_provider=claim_key_provider)
            approved = _approve(root, Operation.source_intake_chain,
                {"ok": True, "plan_sha256": strategy["plan_sha256"], "blockers": []}, reviewed_by, publish_reuse)
            if not approved.get("ok"):
                return {**approved, "capture_completed": False, "staging_receipt_path": staged.get("receipt_path")}
            reused_intakes.append((planned, strategy))
            item_objects.update({proof["item_id"]: proof["object_id"] for proof in strategy["reused_items"]})
            if not strategy["new_items"]:
                continue
            planned = intake.plan_source_intake_batch(root, strategy["request_path"])
            received = (_reuse_or_resume_intake(planned, reviewed_by=reviewed_by, key_provider=claim_key_provider)
                if not planned.approveable else None)
            if received is None and not planned.approveable:
                return {"ok": False, "reason_code": "provider_intake_blocked", "capture_completed": False,
                    "intake_plan": planned.public_document(), "staging_receipt_path": staged.get("receipt_path"), "effects_state": "partial_or_unknown"}
        if received is None:
            received = intake.execute_source_intake_batch(planned,
                expected_plan_sha256=planned.manifest.manifest_sha256, reviewer_claim=reviewed_by)
        if not received.get("ok"):
            return {"ok": False, "reason_code": "provider_intake_incomplete", "capture_completed": False,
                "intake_result": received, "staging_receipt_path": staged.get("receipt_path"), "effects_state": "partial_or_unknown"}
        proposed = capture.plan_objet_capture_batch(root, root / planned.prepared_capture_request.relative_path,
            intake_execution_sha256=received["execution_sha256"], claim_key_provider=claim_key_provider)
        if not proposed.approveable:
            return {"ok": False, "reason_code": "provider_capture_blocked", "capture_completed": False,
                "intake_result": received, "staging_receipt_path": staged.get("receipt_path"), "effects_state": "partial_or_unknown"}
        captured = capture.execute_objet_capture_batch(proposed,
            expected_plan_sha256=proposed.batch_plan_sha256, reviewer_claim=reviewed_by)
        if not captured.get("ok"):
            return {"ok": False, "reason_code": "provider_capture_incomplete", "capture_completed": False,
                "capture_result": captured, "recovery": captured.get("recovery"), "intake_result": received,
                "staging_receipt_path": staged.get("receipt_path"), "effects_state": "partial_or_unknown"}
        item_objects.update({row["item_id"]: row["approved_object_id"] for row in proposed.selection_document["items"]})
        executions.append({"intake_execution_sha256": received["execution_sha256"],
            "capture_execution_sha256": captured.get("execution_sha256")})
    receipt = artifacts.read_json(root, staged["receipt_path"]) if staged.get("receipt_path") else {}
    for alias, original in receipt.get("intake_item_aliases", {}).items():
        if original in item_objects:
            item_objects[alias], item_paths[alias] = item_objects[original], item_paths[original]
    for object_id in set(item_objects.values()):
        _object_verified(root, object_id)
    linked = []
    for row in bindings:
        parent = row.get("parent_object_id") or item_objects.get(row.get("parent_item_id"))
        child = item_objects.get(row.get("child_item_id"))
        if not parent or not child:
            raise artifacts.ProviderArtifactError("provider_attachment_binding_unresolved")
        _object_verified(root, parent)
        linked.append({**row, "parent_object_id": parent, "child_object_id": child})
    derived = []
    for row in text_sources:
        item_id = row.get("item_id")
        source_id = row.get("source_object_id") or item_objects.get(row.get("source_item_id"))
        text_path = row.get("local_path") or item_paths.get(item_id)
        if text_path is None or source_id is None:
            raise artifacts.ProviderArtifactError("provider_text_binding_unresolved")
        _object_verified(root, source_id)
        options = {"text_file": artifacts.safe_path(root, text_path), "source_object_id": source_id,
            "derivation_kind": "parser", "tool_name": "wom-provider-source-parser", "tool_version": "1",
            "review_status": "unreviewed", "born_digital": True}
        preview = services.derived_text_capture_dry_run(root, **options)
        result = _approve(root, Operation.derived_text_capture, preview, reviewed_by, lambda binding, claim:
            services.derived_text_capture_approved(root, **options, expected_plan_sha256=preview["plan_sha256"], reviewed_by=reviewed_by,
                exact_human_approval_claim=claim, expected_exact_approval_plan_sha256=binding.plan_sha256,
                expected_exact_approval_target_binding_sha256=binding.target_binding_sha256))
        if not result.get("ok"):
            return {"ok": False, "reason_code": "provider_search_text_capture_incomplete", "capture_completed": True,
                "search_verified": False, "derived_text_result": result, "staging_receipt_path": staged.get("receipt_path"),
                "effects_state": "partial_or_unknown"}
        derived.append({"source_object_id": source_id, "derived_text_id": result.get("derived_text_id")})
    services.index_archive(root)
    searchable_objects = sorted(set(item_objects.values()) | {row["parent_object_id"] for row in linked})
    for object_id in searchable_objects:
        found = services.search_archive(root, object_id, limit=1000)
        if not any(item.get("type") == "object" and item.get("id") == object_id for item in found.get("results", [])):
            raise artifacts.ProviderArtifactError("provider_object_search_verification_failed")
    for row in derived:
        found = services.search_archive(root, row["derived_text_id"], limit=1000)
        if not any(item.get("id") == row["derived_text_id"] and item.get("source_object_id") == row["source_object_id"] for item in found.get("results", [])):
            raise artifacts.ProviderArtifactError("provider_search_verification_failed")
    document = {"schema": "wom-kit/provider-content-capture/v1", "items": item_objects,
        "source_receipt": staged.get("receipt_path"), "source_receipt_sha256": artifacts.digest(artifacts.canonical(receipt)),
        "bindings": linked, "derived_texts": derived, "executions": executions,
        "reused_intakes": [{"plan_sha256": strategy["plan_sha256"], "request_sha256": strategy["request_sha256"],
            "manifest_sha256": strategy["manifest_sha256"], "items": strategy["reused_items"]} for _, strategy in reused_intakes],
        "capture_completed": True, "search_verified": True, "object_search_count": len(searchable_objects)}
    target = f"receipts/provider-content/{receipt_name}.json"
    plan = {"ok": True, "plan_sha256": artifacts.digest(artifacts.canonical({"path": target, "document": document})), "blockers": []}
    def persist(_binding, _claim):
        for original_plan, strategy in reused_intakes:
            from . import provider_intake_reuse
            provider_intake_reuse.verify(original_plan, strategy, key_provider=claim_key_provider)
        for object_id in set(item_objects.values()) | {row["parent_object_id"] for row in linked}:
            _object_verified(root, object_id)
        if staged.get("receipt_path") and artifacts.digest(artifacts.canonical(artifacts.read_json(root, staged["receipt_path"]))) != document["source_receipt_sha256"]:
            raise artifacts.ProviderArtifactError("provider_source_receipt_changed")
        artifacts.write_json(root, target, document)
        return {"ok": True, "capture_completed": True, "search_verified": True, "object_count": len(set(item_objects.values())),
            "binding_count": len(linked), "search_text_count": len(derived),
            "reused_intake_item_count": sum(len(strategy["reused_items"]) for _, strategy in reused_intakes),
            "object_search_count": len(searchable_objects), "receipt_path": target}
    return _approve(root, Operation.source_intake_chain, plan, reviewed_by, persist)


def complete_imap_content(root, fetched, *, reviewed_by, claim_key_provider=None):
    """Finish an already approved IMAP fetch through capture and search gates."""
    receipt = artifacts.read_json(root, fetched["receipt_path"])
    bindings, texts = [], []
    for occurrence in receipt["occurrences"]:
        prefix = "mail-" + occurrence["uidvalidity"] + "-" + occurrence["uid"]
        if occurrence.get("body"):
            texts.append({"item_id": prefix + "-body", "source_item_id": prefix})
            bindings.append({"parent_item_id": prefix, "child_item_id": prefix + "-body", "role": "email_body"})
        for part in occurrence.get("parts", []):
            bindings.append({"parent_item_id": prefix, "child_item_id": part["item_id"], "role": "email_attachment",
                "mime_path": part["mime_path"], "content_id": part.get("content_id"), "filename": part.get("filename")})
    name = "imap-" + artifacts.digest(artifacts.canonical({"receipt": fetched["receipt_path"]}))[7:31]
    result = capture_staged_content(root, fetched, reviewed_by=reviewed_by, bindings=bindings, text_sources=texts,
        receipt_name=name, claim_key_provider=claim_key_provider)
    complete = fetched.get("collection_complete") is True
    return {**result, "ok": result.get("ok") is True and complete, "collection_complete": complete,
        "pending_message_count": fetched.get("pending_message_count"), "fetch_reason_code": fetched.get("reason_code")}


def _tiro_inputs(root, bundle_path, audio_manifest, enrichment_manifest):
    raw = _source(root, bundle_path)
    audio = json.loads(_source(root, audio_manifest)) if audio_manifest else []
    enrichments = json.loads(_source(root, enrichment_manifest)) if enrichment_manifest else []
    if not isinstance(audio, list) or not isinstance(enrichments, list):
        raise artifacts.ProviderArtifactError("tiro_content_manifest_invalid")
    for row in audio:
        if not isinstance(row, dict):
            raise artifacts.ProviderArtifactError("tiro_audio_binding_invalid")
        path = artifacts.safe_path(root, row["local_path"])
        sha = hashlib.sha256()
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                sha.update(chunk)
        if "sha256:" + sha.hexdigest() != row.get("source_sha256"):
            raise artifacts.ProviderArtifactError("tiro_audio_source_changed")
    return raw, audio, enrichments


def plan_tiro_content(root, *, bundle_path, batch_id, audio_manifest=None, enrichment_manifest=None):
    root = services.require_existing_archive_root(root)
    raw, audio, enrichments = _tiro_inputs(root, bundle_path, audio_manifest, enrichment_manifest)
    basis = {"archive_id": services.read_archive_id(root), "bundle_path": bundle_path, "source_sha256": artifacts.digest(raw),
        "batch_id": batch_id, "audio": audio, "enrichments": enrichments}
    return {"ok": True, "dry_run": True, "lifecycle_action": "tiro_content_import", "plan_sha256": artifacts.digest(artifacts.canonical(basis)),
        "audio_count": len(audio), "enrichment_count": len(enrichments), "provider_calls": 0, "writes": 0, "blockers": []}


def execute_tiro_content(root, *, reviewed_by, expected_plan_sha256, claim_key_provider=None, **options):
    from . import provider_tiro
    root = services.require_existing_archive_root(root)
    preview = plan_tiro_content(root, **options)
    if preview["plan_sha256"] != expected_plan_sha256:
        raise artifacts.ProviderArtifactError("provider_plan_changed")
    def stage(_binding, _claim):
        if plan_tiro_content(root, **options)["plan_sha256"] != expected_plan_sha256:
            raise artifacts.ProviderArtifactError("provider_plan_changed")
        raw, audio, enrichments = _tiro_inputs(root, options["bundle_path"], options.get("audio_manifest"), options.get("enrichment_manifest"))
        return provider_tiro.stage_bundle(root, raw_bundle=raw, batch_id=options["batch_id"], audio_sources=audio, enrichments=enrichments)
    staged = _approve(root, Operation.tiro_lossless_recovery_fetch, preview, reviewed_by, stage)
    if not staged.get("ok"):
        return staged
    receipt = artifacts.read_json(root, staged["receipt_path"])
    bindings = [{"parent_item_id": "tiro-original", "child_item_id": row["item_id"], "note_guid": row["note_guid"], "role": "audio"}
        for row in receipt["items"] if row["category"] == "audio" and row["status"] == "staged"]
    texts = [{"item_id": row["text_item_id"], "source_item_id": row["parent_item_id"]}
        for row in receipt["items"] if row.get("text_item_id")]
    bindings.extend({"parent_item_id": row["parent_item_id"], "child_item_id": row["text_item_id"],
        "note_guid": row["note_guid"], "role": row["category"]} for row in receipt["items"] if row.get("text_item_id"))
    completed = capture_staged_content(root, staged, reviewed_by=reviewed_by, bindings=bindings, text_sources=texts,
        receipt_name="tiro-" + options["batch_id"], claim_key_provider=claim_key_provider)
    return {**completed, "audio_unconfirmed": staged["audio_unconfirmed"], "ai_model_called": False}


def _connection_source(root, raw, *, source_page_id, format, relation_columns=None):
    from . import provider_notion_connections as connections
    value = json.loads(raw) if format == "json" else None
    if isinstance(value, dict) and value.get("schema") == "wom-kit/notion-content-stage/v1":
        blobs = {}
        for row in value.get("items", []):
            if row.get("source_role") == "primary_source":
                source = _source(root, row["local_path"])
                sha = artifacts.digest(source)
                _object_verified(root, sha)
                blobs[sha] = source
        candidates = value.get("candidates", [])
        if not isinstance(candidates, list):
            raise artifacts.ProviderArtifactError("notion_connection_candidates_invalid")
        verified = []
        for candidate in candidates:
            raw_source = blobs.get(candidate.get("source_sha256"))
            if raw_source is None:
                raise artifacts.ProviderArtifactError("notion_connection_source_binding_invalid")
            parsed = connections.parse_source(raw_source, source_ref=candidate["source_ref"], source_page_id=candidate["source_page_id"], format="json")
            if candidate not in parsed["candidates"]:
                raise artifacts.ProviderArtifactError("notion_connection_source_binding_invalid")
            verified.append(candidate)
        observed = {row["connection_kind"] for row in verified}
        return {"schema": "wom-kit/notion-connection-candidates/v1", "candidates": verified,
            "source_ref": "source:" + artifacts.digest(raw), "source_sha256": artifacts.digest(raw),
            "observed_kinds": sorted(observed), "unobserved_kinds": sorted(connections.KINDS - observed),
            "warnings": value.get("warnings", []), "edges_written": 0}
    return connections.parse_source(raw, source_ref="source:" + artifacts.digest(raw), source_page_id=source_page_id,
        format=format, relation_columns=relation_columns)


def plan_connection_import(root, *, source_path, source_page_id, format, batch_id, relation_columns=None,
                           judgments_path=None, bindings_path=None):
    from . import provider_notion_connections as connections
    root = services.require_existing_archive_root(root)
    raw = _source(root, source_path)
    parsed = _connection_source(root, raw, source_page_id=source_page_id, format=format, relation_columns=relation_columns)
    judgments = json.loads(_source(root, judgments_path)) if judgments_path else []
    bindings = json.loads(_source(root, bindings_path)) if bindings_path else {}
    plan = connections.reviewed_edge_plan(parsed["candidates"], judgments, bindings)
    basis = {"source_path": source_path, "parsed": parsed, "reviewed": plan, "batch_id": batch_id,
        "judgments": judgments, "bindings": bindings, "archive_id": services.read_archive_id(root)}
    return {"ok": True, "dry_run": True, "plan_sha256": artifacts.digest(artifacts.canonical(basis)),
        "candidate_count": len(parsed["candidates"]), "reviewed_edge_count": len(plan["edges"]),
        "pending_count": len(plan["pending_candidate_ids"]), "observed_kinds": parsed["observed_kinds"],
        "unobserved_kinds": parsed["unobserved_kinds"], "warnings": parsed["warnings"], "blockers": [], "provider_calls": 0, "writes": 0}


def execute_connection_import(root, *, reviewed_by, expected_plan_sha256, claim_key_provider=None, **options):
    from . import provider_notion_connections as connections
    root = services.require_existing_archive_root(root)
    preview = plan_connection_import(root, **options)
    if preview["plan_sha256"] != expected_plan_sha256:
        raise artifacts.ProviderArtifactError("provider_plan_changed")
    directory = "workbench/notion-connections/" + options["batch_id"]
    def stage(_binding, _claim):
        if plan_connection_import(root, **options)["plan_sha256"] != expected_plan_sha256:
            raise artifacts.ProviderArtifactError("provider_plan_changed")
        raw = _source(root, options["source_path"])
        blob = artifacts.write_blob(root, raw, "json" if options["format"] == "json" else "txt")
        parsed = _connection_source(root, raw, source_page_id=options["source_page_id"],
            format=options["format"], relation_columns=options.get("relation_columns"))
        judgments = json.loads(_source(root, options["judgments_path"])) if options.get("judgments_path") else []
        bindings = json.loads(_source(root, options["bindings_path"])) if options.get("bindings_path") else {}
        reviewed = connections.reviewed_edge_plan(parsed["candidates"], judgments, bindings)
        artifacts.write_json(root, directory + "/candidates.json", {**parsed, "source_artifact": blob, "judgments": judgments})
        artifacts.write_json(root, directory + "/edges.json", reviewed)
        paths, aliases = artifacts.write_intake_requests(root, directory, "notion-evidence-" + options["batch_id"],
            [{"item_id": "connection-evidence", "local_path": blob["path"], "source_role": "primary_source"}])
        artifacts.write_json(root, directory + "/source-receipt.json", {"source_artifact": blob, "intake_item_aliases": aliases})
        return {"ok": True, "pending_count": len(reviewed["pending_candidate_ids"]), "edge_count": len(reviewed["edges"]),
            "intake_requests": paths, "receipt_path": directory + "/source-receipt.json"}
    staged = _approve(root, Operation.zettel_edge_batch, preview, reviewed_by, stage)
    if staged.get("ok"):
        preserved = capture_staged_content(root, staged, reviewed_by=reviewed_by, receipt_name="connections-" + options["batch_id"],
            claim_key_provider=claim_key_provider)
        if not preserved.get("ok"):
            return preserved
    if not staged.get("ok") or not staged["edge_count"]:
        return {**staged, "edges_written": 0, "review_required": bool(staged.get("pending_count")), "evidence_path": directory + "/candidates.json"}
    edge_options = {"plan_path": directory + "/edges.json", "max_edges": 1000, "skip_existing": True}
    proposed = services.zettel_edge_batch_write(root, **edge_options, dry_run=True)
    if not proposed.get("ok"):
        return {"ok": False, "reason_code": "provider_connection_edge_plan_blocked", "edges_written": 0}
    if proposed.get("write_status") != "would_write":
        return {**proposed, "pending_count": staged["pending_count"]}
    binding = zettel_edge_batch_approval_binding(proposed)
    result = _approve(root, Operation.zettel_edge_batch, proposed, reviewed_by, lambda bound, claim:
        services.zettel_edge_batch_write(root, **edge_options, approve=True, reviewed_by=reviewed_by,
            exact_human_approval_claim=claim, expected_exact_approval_plan_sha256=bound.plan_sha256,
            expected_exact_approval_target_binding_sha256=bound.target_binding_sha256), binding=binding)
    return {**result, "pending_count": staged["pending_count"], "evidence_path": directory + "/candidates.json"}


def plan_notion_content(root, manifest, *, max_items=1000, offset=0, include_media=True, include_connections=False,
                        max_provider_requests=20000):
    from .notion_page_recovery import parse_manifest, build_plan
    root = services.require_existing_archive_root(root)
    request = parse_manifest(manifest)
    selected = build_plan(request, max_items=max_items, offset=offset)
    if request.archive_id != services.read_archive_id(root):
        raise artifacts.ProviderArtifactError("notion_content_archive_mismatch")
    if (type(include_media) is not bool or type(include_connections) is not bool or not (include_media or include_connections)
            or type(max_provider_requests) is not int or not 1 <= max_provider_requests <= 100000):
        raise artifacts.ProviderArtifactError("notion_content_options_invalid")
    basis = {"request_sha256": selected.request_sha256, "recovery_plan_sha256": selected.plan_sha256,
        "include_media": include_media, "include_connections": include_connections, "max_provider_requests": max_provider_requests}
    return {"ok": True, "dry_run": True, "lifecycle_action": "notion_provider_content", "request_sha256": selected.request_sha256,
        "plan_sha256": artifacts.digest(artifacts.canonical(basis)), "selected_page_count": len(selected.selected_items),
        "include_media": include_media, "include_connections": include_connections,
        "max_provider_requests": max_provider_requests, "credential_reads": 0, "provider_calls": 0, "writes": 0, "blockers": []}


def execute_notion_content(root, manifest, *, reviewed_by, expected_plan_sha256, claim_key_provider=None,
                           worker_spawner=None, **options):
    from . import credential_workflows
    root = services.require_existing_archive_root(root)
    preview = plan_notion_content(root, manifest, **options)
    if preview["plan_sha256"] != expected_plan_sha256:
        raise artifacts.ProviderArtifactError("provider_plan_changed")
    def fetch(binding, claim):
        return credential_workflows.execute_spawned_authenticated_notion_content(root, manifest,
            reviewed_by=reviewed_by, expected_plan_sha256=expected_plan_sha256, **options,
            exact_human_approval_claim=claim, expected_exact_approval_plan_sha256=binding.plan_sha256,
            expected_exact_approval_target_binding_sha256=binding.target_binding_sha256,
            worker_spawner=worker_spawner)
    fetched = _approve(root, Operation.notion_page_recovery, preview, reviewed_by, fetch)
    if not fetched.get("ok"):
        return fetched
    directory = "workbench/notion-content/" + expected_plan_sha256[7:31]
    path = directory + "/content-receipt.json"
    receipt = artifacts.read_json(root, path)
    stage = {"intake_requests": receipt["intake_requests"], "receipt_path": path}
    parents = services.notion_recovered_page_objects(root)
    bindings, texts, seen_parents = [], [], set()
    for row in receipt["bindings"]:
        objects = parents.get(row["source_page_id"], [])
        if not objects:
            return {"ok": False, "capture_completed": False, "reason_code": "notion_parent_recovery_required",
                "receipt_path": path, "provider_fetch_completed": True}
        bindings.extend({**row, "parent_object_id": object_id} for object_id in objects)
        for object_id in objects:
            if object_id not in seen_parents:
                texts.append({"source_object_id": object_id, "local_path": _object_verified(root, object_id)})
                seen_parents.add(object_id)
    result = capture_staged_content(root, stage, reviewed_by=reviewed_by, bindings=bindings,
        text_sources=texts, receipt_name="notion-" + expected_plan_sha256[7:31], claim_key_provider=claim_key_provider)
    return {**result, "provider_fetch_completed": True, "provider_calls": fetched["provider_calls"],
        "connection_candidate_count": len(receipt["candidates"]), "connection_review_required": bool(receipt["candidates"]),
        "connection_evidence_path": path if options.get("include_connections") else None}


def plan_notion_recovery_with_content(root, manifest, *, max_items=1000, offset=0, include_media=True,
                                     include_connections=False, max_provider_requests=20000):
    from .notion_page_recovery import plan_recovery
    body = plan_recovery(root, manifest, max_items=max_items, offset=offset)
    if not body.get("ok"):
        return body
    content = plan_notion_content(root, manifest, max_items=max_items, offset=offset, include_media=include_media,
        include_connections=include_connections, max_provider_requests=max_provider_requests)
    digest = artifacts.digest(artifacts.canonical({"body_plan_sha256": body["plan_sha256"],
        "content_plan_sha256": content["plan_sha256"]}))
    return {"ok": True, "dry_run": True, "lifecycle_action": "notion_recovery_with_content", "plan_sha256": digest,
        "body_plan_sha256": body["plan_sha256"], "content_plan_sha256": content["plan_sha256"],
        "selected_page_count": content["selected_page_count"], "include_media": include_media, "include_connections": include_connections,
        "credential_reads": 0, "provider_calls": 0, "writes": 0, "blockers": []}


def execute_notion_recovery_with_content(root, manifest, *, reviewed_by, expected_plan_sha256,
        body_worker_spawner=None, content_worker_spawner=None, claim_key_provider=None, **options):
    """One command binds both scopes, recovers the parent, then its content.

    Each existing writer still claims its own authenticated operation. Valid
    full-access/session grants are handled by the existing approval broker.
    """
    from . import credential_workflows
    from .notion_page_recovery import plan_recovery
    root = services.require_existing_archive_root(root)
    preview = plan_notion_recovery_with_content(root, manifest, **options)
    if not preview.get("ok") or preview.get("plan_sha256") != expected_plan_sha256:
        raise artifacts.ProviderArtifactError("provider_plan_changed")
    def approve_scope(_binding, _claim):
        fresh = plan_notion_recovery_with_content(root, manifest, **options)
        if fresh.get("plan_sha256") != expected_plan_sha256:
            raise artifacts.ProviderArtifactError("provider_plan_changed")
        return {"ok": True, "scope_plan_sha256": expected_plan_sha256, "provider_calls": 0,
            "body_plan_sha256": preview["body_plan_sha256"], "content_plan_sha256": preview["content_plan_sha256"]}
    approved_scope = _approve(root, Operation.notion_page_recovery, preview, reviewed_by, approve_scope)
    if not approved_scope.get("ok"):
        return approved_scope
    # Release the first archive-key callback before entering another operation
    # broker. Production key providers need not support nested consumers.
    def sequence():
        maximum, offset = options.get("max_items", 1000), options.get("offset", 0)
        body_plan = plan_recovery(root, manifest, max_items=maximum, offset=offset)
        body = _approve(root, Operation.notion_page_recovery, body_plan, reviewed_by, lambda binding, claim:
            credential_workflows.execute_spawned_authenticated_notion_page_recovery(root, manifest,
                expected_plan_sha256=preview["body_plan_sha256"], reviewed_by=reviewed_by, max_items=maximum, offset=offset,
                exact_human_approval_claim=claim, expected_exact_approval_plan_sha256=binding.plan_sha256,
                expected_exact_approval_target_binding_sha256=binding.target_binding_sha256, worker_spawner=body_worker_spawner))
        if not body.get("ok"):
            return {"ok": False, "reason_code": "notion_body_recovery_incomplete", "body_recovery": body,
                "content_started": False, "capture_completed": False}
        content = execute_notion_content(root, manifest, reviewed_by=reviewed_by,
            expected_plan_sha256=preview["content_plan_sha256"], **options,
            worker_spawner=content_worker_spawner, claim_key_provider=claim_key_provider)
        return {**content, "body_recovery_completed": True, "body_provider_calls": body.get("operations", {}).get("provider_calls"),
            "content_started": True, "composite_plan_sha256": expected_plan_sha256}
    return sequence()
