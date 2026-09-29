"""Bind previously authenticated intake members to a new provider occurrence.

Filesystem names are discovery hints only.  The ordinary capture planner
authenticates the original completed intake and its entire prepared-request
chain before an existing member may be reused.  The original manifests and
their exact-operation guards remain unchanged.
"""
from __future__ import annotations

import os
import re

from . import archive_services as services, provider_artifacts as artifacts
from . import objet_capture_batch_exact as capture, source_intake_batch_exact as intake
from .exact_operation_manifest import (
    EXACT_OPERATION_RECEIPTS_ROOT,
    ExactOperationManifestError,
    load_exact_operation_final_receipt_read_only,
)


def _sha(value):
    return "sha256:" + str(value).removeprefix("sha256:")


def _member(plan, item):
    """Compare every incoming source binding to the authenticated old member."""
    for row in plan.selection_document["items"]:
        if (row.get("source_intake_receipt_path") != item.receipt_relative_path
                or row.get("staged_path") != item.capture_staged_path
                or _sha(row.get("source_intake_plan_sha256")) != item.source_intake_plan_sha256
                or _sha(row.get("approved_object_id")) != item.source_bytes_sha256
                or type(row.get("expected_size_bytes")) is not int
                or row["expected_size_bytes"] != item.source_size_bytes):
            continue
        receipt = artifacts.safe_path(plan.archive_root, item.receipt_relative_path)
        raw, reason = services._bounded_stable_regular_file_read(receipt, max_bytes=8 * 1024 * 1024)
        if raw is None or reason or raw != item.receipt_bytes:
            continue
        return {
            "item_id": item.request_item_id,
            "original_item_id": row["item_id"],
            "object_id": item.source_bytes_sha256,
            "source_size_bytes": item.source_size_bytes,
            "source_path_sha256": artifacts.digest(item.capture_staged_path.encode()),
            "source_intake_receipt_sha256": artifacts.digest(raw),
            "source_intake_plan_sha256": item.source_intake_plan_sha256,
            "intake_execution_sha256": plan.intake_execution_sha256,
            "intake_final_receipt_sha256": plan.intake_final_receipt_sha256,
            "intake_chain_binding_sha256": plan.intake_chain_binding_sha256,
        }
    return None


def _prior_candidates(root, needed):
    directory = artifacts.safe_path(root, EXACT_OPERATION_RECEIPTS_ROOT + "/.provider-reuse-probe").parent
    if not directory.is_dir():
        return
    with services._activity_group_bound_directory_chain(root, directory, create=False):
        names = os.listdir(directory)
        if len(names) > 100000:
            raise artifacts.ProviderArtifactError("provider_intake_discovery_limit")
        for name in sorted(names):
            if not re.fullmatch(r"[a-f0-9]{64}\.json", name):
                continue
            execution = "sha256:" + name[:-5]
            try:
                final = load_exact_operation_final_receipt_read_only(root, execution)
                result = final.get("result", {}) if final else {}
                auth = result.get("completion_authentication", {})
                if auth.get("operation") != "source_intake_batch" or result.get("status") != "completed":
                    continue
                sha = result.get("operation_evidence", {}).get("digests", {}).get("prepared_capture_request_sha256")
                if type(sha) is not str or re.fullmatch(r"sha256:[a-f0-9]{64}", sha) is None:
                    continue
                # This cheap filter grants no authority; the selected whole
                # request and all its receipts are authenticated below.
                request = artifacts.read_json(root, intake.CAPTURE_REQUESTS_ROOT + "/" + sha[7:] + ".objet-capture-request.json")
                refs = {row.get("source_intake_receipt_path") for row in request.get("items", []) if isinstance(row, dict)}
                if needed.isdisjoint(refs):
                    continue
            except (ExactOperationManifestError, artifacts.ProviderArtifactError, OSError, TypeError, AttributeError):
                continue
            yield execution


def discover(plan, *, key_provider=None):
    """Return a private reuse strategy, or refuse unproved existing members."""
    if plan.manifest is None or not plan.items or not plan.resume_candidate:
        return None
    retained_path = _retained_path(plan)
    if artifacts.safe_path(plan.archive_root, retained_path).exists():
        retained = artifacts.read_json(plan.archive_root, retained_path)
        verify(plan, retained, key_provider=key_provider)
        return retained
    existing = [item for item in plan.items if item.target_state == "exact_target_present"]
    if not existing:
        return None
    outstanding = {item.request_item_id: item for item in existing}
    matched = {}
    for execution in _prior_candidates(plan.archive_root, {item.receipt_relative_path for item in existing}):
        try:
            prior = capture.plan_objet_capture_batch(plan.archive_root,
                intake_execution_sha256=execution, claim_key_provider=key_provider)
        except capture.ObjetCaptureBatchExactError:
            continue
        if not prior.approveable:
            continue
        for name, item in tuple(outstanding.items()):
            proof = _member(prior, item)
            if proof is not None:
                matched[name] = proof
                del outstanding[name]
        if not outstanding:
            break
    if outstanding:
        return None
    request = artifacts.read_json(plan.archive_root, plan.request_path.relative_to(plan.archive_root).as_posix())
    ready = {item.request_item_id for item in plan.items if item.target_state == "ready_to_create"}
    basis = {
        "schema": "wom-kit/provider-intake-reuse/v1",
        "request_sha256": plan.request_bytes_sha256,
        "manifest_sha256": plan.manifest.manifest_sha256,
        "reused_items": [matched[item.request_item_id] for item in existing],
        "new_items": [row for row in request["items"] if row["item_id"] in ready],
    }
    sha = artifacts.digest(artifacts.canonical(basis))
    return {**basis, "plan_sha256": sha, "request_path": f"workbench/provider-intake/{sha[7:]}.json"}


def verify(plan, strategy, *, key_provider=None):
    """Recheck the same evidence immediately before each approved publication."""
    basis = {key: value for key, value in strategy.items() if key not in {"plan_sha256", "request_path"}}
    sha = artifacts.digest(artifacts.canonical(basis))
    if strategy["plan_sha256"] != sha or strategy["request_path"] != f"workbench/provider-intake/{sha[7:]}.json":
        raise artifacts.ProviderArtifactError("provider_intake_reuse_evidence_changed")
    current = intake.plan_source_intake_batch(plan.archive_root, plan.request_path)
    if (current.manifest is None or current.manifest.manifest_sha256 != strategy["manifest_sha256"]
            or current.request_bytes_sha256 != strategy["request_sha256"]):
        raise artifacts.ProviderArtifactError("provider_intake_reuse_evidence_changed")
    by_id = {item.request_item_id: item for item in current.items}
    request = artifacts.read_json(plan.archive_root, plan.request_path.relative_to(plan.archive_root).as_posix())
    reused_ids = [proof["item_id"] for proof in strategy["reused_items"]]
    new_ids = [row["item_id"] for row in strategy["new_items"]]
    if (len(set(reused_ids + new_ids)) != len(reused_ids + new_ids)
            or set(reused_ids + new_ids) != set(by_id)
            or strategy["new_items"] != [row for row in request["items"] if row["item_id"] in set(new_ids)]):
        raise artifacts.ProviderArtifactError("provider_intake_reuse_evidence_changed")
    prior_plans = {}
    for proof in strategy["reused_items"]:
        execution = proof["intake_execution_sha256"]
        if execution not in prior_plans:
            try:
                prior_plans[execution] = capture.plan_objet_capture_batch(plan.archive_root,
                    intake_execution_sha256=execution, claim_key_provider=key_provider)
            except capture.ObjetCaptureBatchExactError:
                raise artifacts.ProviderArtifactError("provider_intake_reuse_evidence_changed") from None
        prior = prior_plans[execution]
        item = by_id.get(proof["item_id"])
        if not prior.approveable or item is None or _member(prior, item) != proof:
            raise artifacts.ProviderArtifactError("provider_intake_reuse_evidence_changed")


def _retained_path(plan):
    return "workbench/provider-intake/reuse-" + plan.manifest.manifest_sha256.removeprefix("sha256:") + ".json"


def publish_new_request(plan, strategy, *, key_provider=None):
    """Called only inside the provider's digest-bound approval writer."""
    verify(plan, strategy, key_provider=key_provider)
    artifacts.write_json(plan.archive_root, _retained_path(plan), strategy)
    if strategy["new_items"]:
        artifacts.write_json(plan.archive_root, strategy["request_path"], {
            "schema": "wom-kit/source-intake-batch-request/v0.1",
            "batch_id": "provider-" + strategy["plan_sha256"][7:31],
            "items": strategy["new_items"],
        })
    return {"ok": True, "reused_item_count": len(strategy["reused_items"]),
        "new_item_count": len(strategy["new_items"])}
