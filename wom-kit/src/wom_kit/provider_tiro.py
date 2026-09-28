"""Stage Tiro originals, explicitly mapped audio, and separate AI derivations.

The caller owns the approved source scope. This module reads only explicitly
listed archive-relative audio paths, never searches a user's recording folders.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import provider_artifacts as artifacts
from .provider_notion_media import _stream_blob

BUNDLE_SCHEMA = "wom-tiro-lossless-recovery-bundle/v0.1"


def _note_ids(bundle):
    ids = set()
    for note in bundle.get("notes", []):
        if not isinstance(note, dict):
            raise artifacts.ProviderArtifactError("tiro_note_invalid")
        guid = note.get("guid") or note.get("id")
        if not isinstance(guid, str) or not guid:
            raise artifacts.ProviderArtifactError("tiro_note_id_missing")
        ids.add(guid)
    return ids


def _text_objects(value):
    if isinstance(value, list):
        for item in value:
            yield from _text_objects(item)
    elif isinstance(value, dict):
        if isinstance(value.get("content"), str):
            yield value["content"]
        for key, child in value.items():
            if key != "content" or not isinstance(child, str):
                yield from _text_objects(child)


def stage_bundle(root: Path, *, raw_bundle: bytes, batch_id: str, audio_sources=(), enrichments=(), max_audio_bytes=512 * 1024 * 1024):
    """Produce ready intake input; never claim canonical capture or AI calls."""
    if not batch_id or not all(char.isascii() and (char.isalnum() or char in "-_") for char in batch_id):
        raise artifacts.ProviderArtifactError("tiro_batch_id_invalid")
    try:
        bundle = json.loads(raw_bundle)
    except (ValueError, UnicodeError):
        raise artifacts.ProviderArtifactError("tiro_bundle_invalid") from None
    if not isinstance(bundle, dict) or bundle.get("schema") != BUNDLE_SCHEMA:
        raise artifacts.ProviderArtifactError("tiro_bundle_schema_invalid")
    notes = _note_ids(bundle)
    source_sha = artifacts.digest(raw_bundle)
    raw = artifacts.write_blob(root, raw_bundle, "json")
    items = [{"item_id": "tiro-original", "local_path": raw["path"], "source_role": "primary_source", "mime": "application/json"}]
    rows, mapped = [], set()
    for guid in sorted(notes):
        paragraphs = bundle.get("paragraphs_by_note", {}).get(guid)
        if paragraphs is None:
            rows.append({"note_guid": guid, "category": "transcript", "status": "not_returned"})
            continue
        text = "\n\n".join(_text_objects(paragraphs)).encode("utf-8")
        if text:
            blob = artifacts.write_blob(root, text, "txt")
            item_id = "transcript-" + hashlib.sha256(guid.encode()).hexdigest()[:24]
            items.append({"item_id": item_id,
                "local_path": blob["path"], "source_role": "derived_context", "mime": "text/plain"})
            rows.append({"note_guid": guid, "category": "transcript", "status": "staged", "text_item_id": item_id,
                "parent_item_id": "tiro-original", **blob})
    for ordinal, audio in enumerate(audio_sources):
        guid = audio.get("note_guid")
        if guid not in notes or not isinstance(audio.get("source_sha256"), str):
            raise artifacts.ProviderArtifactError("tiro_audio_binding_invalid")
        path = artifacts.safe_path(root, audio["local_path"])
        with open(path, "rb") as source:
            blob = _stream_blob(root, source, max_bytes=max_audio_bytes)
        if blob["sha256"] != audio["source_sha256"]:
            raise artifacts.ProviderArtifactError("tiro_audio_source_changed")
        item_id = f"tiro-audio-{ordinal:04d}"
        items.append({"item_id": item_id, "local_path": blob["path"], "source_role": "attachment", "mime": audio.get("mime", "application/octet-stream")})
        rows.append({"note_guid": guid, "category": "audio", "status": "staged", "item_id": item_id,
            "parent_item_id": "tiro-original", "source_kind": "explicit_local_export", **blob})
        mapped.add(guid)
    for guid in sorted(notes - mapped):
        rows.append({"note_guid": guid, "category": "audio", "status": "availability_unconfirmed"})
    for ordinal, enrichment in enumerate(enrichments):
        provenance = enrichment.get("model_provenance", {})
        if (enrichment.get("note_guid") not in notes or enrichment.get("source_sha256") != source_sha
                or not all(isinstance(provenance.get(key), str) and provenance[key] for key in ("provider", "model", "run_id"))
                or not isinstance(enrichment.get("content"), str) or not enrichment["content"]):
            raise artifacts.ProviderArtifactError("tiro_enrichment_provenance_invalid")
        derivative = {"schema": "wom-kit/tiro-ai-enrichment/v1", "source_sha256": source_sha,
            "note_guid": enrichment["note_guid"], "model_provenance": provenance, "content": enrichment["content"],
            "origin": "ai_derivation", "original_modified": False}
        blob = artifacts.write_blob(root, artifacts.canonical(derivative), "json")
        text = artifacts.write_blob(root, enrichment["content"].encode("utf-8"), "txt")
        items.extend([{"item_id": f"tiro-enrichment-{ordinal:04d}", "local_path": blob["path"], "source_role": "derived_context", "mime": "application/json"},
            {"item_id": f"tiro-enrichment-text-{ordinal:04d}", "local_path": text["path"], "source_role": "derived_context", "mime": "text/plain"}])
        rows.append({"note_guid": enrichment["note_guid"], "category": "ai_enrichment", "status": "staged",
            "text_item_id": f"tiro-enrichment-text-{ordinal:04d}", "parent_item_id": f"tiro-enrichment-{ordinal:04d}", **blob})
    request_path = f"workbench/tiro-content/{batch_id}/source-intake-batch-request.json"
    receipt_path = f"workbench/tiro-content/{batch_id}/content-receipt.json"
    paths, aliases = artifacts.write_intake_requests(root, f"workbench/tiro-content/{batch_id}", "tiro-" + batch_id, items)
    artifacts.write_json(root, receipt_path, {"schema": "wom-kit/tiro-content-receipt/v1", "original": raw, "items": rows,
        "provider_fetch_gaps": bundle.get("fetch_gaps", []), "source_sha256": source_sha, "intake_requests": paths, "intake_item_aliases": aliases})
    return {"ok": True, "original_staged": True, "audio_staged": len(audio_sources), "audio_unconfirmed": len(notes - mapped),
        "enrichment_staged": len(enrichments), "capture_completed": False, "intake_request": request_path, "receipt_path": receipt_path,
        "intake_requests": paths, "provider_api_called": False, "ai_model_called": False}
