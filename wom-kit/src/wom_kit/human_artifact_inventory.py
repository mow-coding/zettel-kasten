"""Complete metadata inventory pages and one reviewed lifecycle batch.

Inventory generations are private read evidence, never write authority. The
batch independently authenticates the registry and observes only its selected
files. It appends the existing per-artifact receipt format without modifying
artifact bytes. A interrupted batch resumes from those authenticated receipts.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid

from . import archive_services as services, human_artifact_registry as registry
from .exact_human_approval import ExactHumanApprovalError
from .exact_operation_manifest import ExactOperationManifestError, _ensure_private_directory, _read_plain_file
from .operation_target_leases import TargetLease
from .snapshot_pagination import SnapshotPager, content_sha256

SCHEMA = "wom-kit/human-artifact-inventory/v1"
REQUEST_SCHEMA = "wom-kit/human-artifact-batch-request/v1"
CONTROL_SCHEMA = "wom-kit/human-artifact-batch-control/v1"
MAX_BYTES = 64 * 1024 * 1024
MAX_BATCH = 2000
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _fail(code):
    return services.ArchiveServiceError(code)


def _folder(root, create=False):
    if create:
        return _ensure_private_directory(root, ("db", "human-artifact-inventories"))
    from .source_intake_batch_exact import _reject_link_or_reparse_chain
    folder = root / "db/human-artifact-inventories"
    if not folder.exists():
        raise _fail("human_artifact_inventory_missing")
    _reject_link_or_reparse_chain(folder, code="human_artifact_inventory_invalid")
    return folder


def _scopes(context, authority, *, selected_root_ids=None):
    scopes = {}
    for root_id, relative in registry.ARCHIVE_MANAGED_SCOPES:
        if selected_root_ids is not None and root_id not in selected_root_ids:
            continue
        scope, _present = registry._scope_path(context.root, relative)
        scopes[root_id] = (scope, "archive_managed")
    for document in registry._load_root_documents(context, authority):
        if selected_root_ids is not None and document["root_id"] not in selected_root_ids:
            continue
        path, reason = registry._validate_registered_root(document)
        if reason is None:
            scope, _present = registry._scope_path(path, document["scan_relative_root"])
            scopes[document["root_id"]] = (scope, "external_registered")
    return scopes


def publish(archive_root):
    """Explicit refresh; traverse each registered metadata scope once, no cap."""
    root = services.require_existing_archive_root(archive_root)
    scan = registry._scan_internal(root, max_entries_per_root=registry.MAX_ENTRIES_PER_ROOT, _complete_inventory=True)
    context = registry._validated_archive(root)
    scopes = _scopes(context, scan.authority)
    locators = {}
    for artifact_id, state in scan.states.items():
        scope, _kind = scopes[state.observed.root_id]
        locators[artifact_id] = {"root_id": state.observed.root_id,
                                "relative_path": state.observed.path.relative_to(scope).as_posix()}
    document = {"schema": SCHEMA, "archive_id": context.archive_id,
                "report": scan.public, "private_locators": locators, "read_evidence_only": True}
    raw = _canonical(document)
    if len(raw) > MAX_BYTES:
        raise _fail("human_artifact_inventory_too_large")
    digest = hashlib.sha256(raw).hexdigest()
    with TargetLease(root, kind="file", reference="db/human-artifact-inventories/latest.json"):
        folder = _folder(root, True)
        path = folder / (digest + ".json")
        try:
            services._write_bytes_create_if_absent(path, raw)
        except FileExistsError:
            if _read_plain_file(path, max_bytes=MAX_BYTES, heartbeat=lambda: None) != raw:
                raise _fail("human_artifact_inventory_changed") from None
        pending = folder / (uuid.uuid4().hex + ".pending")
        try:
            with pending.open("xb") as stream:
                stream.write(_canonical({"schema": SCHEMA, "snapshot": digest}))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, folder / "latest.json")
        finally:
            if pending.exists():
                pending.unlink()
    return {"ok": scan.public["coverage_complete"], "snapshot_ref": digest,
            "artifact_count": scan.public["artifact_count"], "coverage_complete": scan.public["coverage_complete"],
            "closeout_complete": scan.public["closeout_complete"], "blocker_codes": scan.public["blocker_codes"],
            "artifact_bodies_read": False}


def _read(root, snapshot_ref=None):
    folder = _folder(root)
    if snapshot_ref is None:
        pointer = json.loads(_read_plain_file(folder / "latest.json", max_bytes=4096, heartbeat=lambda: None))
        if pointer.get("schema") != SCHEMA:
            raise _fail("human_artifact_inventory_invalid")
        snapshot_ref = pointer.get("snapshot")
    if type(snapshot_ref) is not str or not _DIGEST.fullmatch(snapshot_ref):
        raise _fail("human_artifact_inventory_invalid")
    path = folder / (snapshot_ref + ".json")
    if not path.exists():
        raise _fail("human_artifact_inventory_expired_refresh")
    raw = _read_plain_file(path, max_bytes=MAX_BYTES, heartbeat=lambda: None)
    if hashlib.sha256(raw).hexdigest() != snapshot_ref:
        raise _fail("human_artifact_inventory_changed")
    document = json.loads(raw)
    if document.get("schema") != SCHEMA or document.get("archive_id") != services.read_archive_id(root):
        raise _fail("human_artifact_inventory_invalid")
    return snapshot_ref, document


def query(archive_root, *, snapshot_ref=None, page_size=100, cursor=None, state=None):
    root = services.require_existing_archive_root(archive_root)
    if type(page_size) is not int or not 1 <= page_size <= 2000:
        raise _fail("human_artifact_inventory_page_size_invalid")
    if state is not None and state not in registry.LIFECYCLE_STATES | {"unclassified"}:
        raise _fail("human_artifact_inventory_state_invalid")
    if cursor and snapshot_ref is None:
        raise _fail("human_artifact_inventory_cursor_requires_snapshot")
    snapshot, document = _read(root, snapshot_ref)
    report = document["report"]
    rows = [row for row in report["items"] if state is None or row["lifecycle_state"] == state]
    pager = SnapshotPager.build(rows, generation_sha256="sha256:" + snapshot,
                               query_sha256=content_sha256({"state": state}))
    return {"ok": True, "schema": SCHEMA, "snapshot_ref": snapshot, **pager.page(page_size=page_size, cursor=cursor),
            "coverage_complete": report["coverage_complete"], "closeout_complete": report["closeout_complete"],
            "blocker_codes": report["blocker_codes"], "snapshot_is_historical": True,
            "current_targets_rechecked": False, "paths_echoed": False, "artifact_bodies_read": False}


def _request(value):
    if (type(value) is not dict or set(value) != {"schema", "snapshot_ref", "items"}
            or value.get("schema") != REQUEST_SCHEMA or type(value.get("items")) is not list
            or not 1 <= len(value["items"]) <= MAX_BATCH):
        raise _fail("human_artifact_batch_request_invalid")
    seen = set()
    for row in value["items"]:
        if (type(row) is not dict or set(row) != {"artifact_id", "target_state", "content_sha256", "size_bytes", "related_refs"}
                or type(row["artifact_id"]) is not str or not registry.ARTIFACT_ID_RE.fullmatch(row["artifact_id"])
                or type(row["target_state"]) is not str or row["target_state"] not in registry.LIFECYCLE_STATES
                or row["artifact_id"] in seen):
            raise _fail("human_artifact_batch_request_invalid")
        seen.add(row["artifact_id"])
    return json.loads(_canonical(value))


def _selected_states(root, locators, ids, *, allow_unavailable=False):
    context = registry._validated_archive(root)
    authority = registry._load_authority(context, create=False)
    scopes = _scopes(context, authority, selected_root_ids={locator["root_id"] for key, locator in locators.items()
                                                          if key in ids and isinstance(locator, dict) and "root_id" in locator})
    chains = registry._load_receipt_chains(context, authority, _artifact_ids=set(ids))
    states = {}

    def observe(artifact_id):
        locator = locators.get(artifact_id)
        if not locator or locator.get("root_id") not in scopes:
            raise _fail("human_artifact_batch_target_unavailable")
        scope, kind = scopes[locator["root_id"]]
        relative = locator.get("relative_path")
        if type(relative) is not str or not relative or "\\" in relative:
            raise _fail("human_artifact_batch_target_unsafe")
        parsed = PurePosixPath(relative)
        if parsed.is_absolute() or ".." in parsed.parts or relative != parsed.as_posix():
            raise _fail("human_artifact_batch_target_unsafe")
        parent, present = registry._scope_path(scope, parsed.parent.as_posix())
        if not present:
            raise _fail("human_artifact_batch_target_unavailable")
        path = parent / parsed.name
        try:
            info = os.lstat(path)
        except OSError:
            raise _fail("human_artifact_batch_target_unavailable") from None
        if registry._is_reparse(info) or not stat.S_ISREG(info.st_mode):
            raise _fail("human_artifact_batch_target_unsafe")
        if registry._artifact_id(context, root_id=locator["root_id"], relative_path=relative) != artifact_id:
            raise _fail("human_artifact_batch_target_identity_changed")
        observed = registry._ObservedArtifact(artifact_id, locator["root_id"], kind, path, registry._observation(artifact_id, info))
        return registry._current_artifact_state(observed, chains.get(artifact_id, registry._ReceiptChain(())))

    for artifact_id in ids:
        try:
            states[artifact_id] = observe(artifact_id)
        except (services.ArchiveServiceError, registry.HumanArtifactRegistryError):
            if not allow_unavailable:
                raise
            states[artifact_id] = None
    return context, authority, states


def _prepare(root, request):
    request = _request(request)
    snapshot, inventory = _read(root, request["snapshot_ref"])
    ids = [row["artifact_id"] for row in request["items"]]
    locators = {key: inventory["private_locators"].get(key) for key in ids}
    _context, _authority, states = _selected_states(root, locators, ids)
    previous = {row["artifact_id"]: row for row in inventory["report"]["items"]}
    private = []
    for row in request["items"]:
        state = states[row["artifact_id"]]
        if previous.get(row["artifact_id"], {}).get("current_state_sha256") != state.current_state_sha256:
            raise _fail("human_artifact_batch_inventory_target_changed")
        _public, _state, item = registry._transition_plan_internal(root, **row,
            max_entries_per_root=registry.DEFAULT_MAX_ENTRIES_PER_ROOT, _selected_state=state)
        private.append(item)
    basis = {"schema": "wom-kit/human-artifact-batch-plan/v1", "archive_id": services.read_archive_id(root),
             "request_sha256": _sha(_canonical(request)), "snapshot_ref": snapshot, "items": private}
    return request, basis, locators, _sha(_canonical(basis))


def plan(archive_root, request):
    root = services.require_existing_archive_root(archive_root)
    _request_value, basis, _locators, digest = _prepare(root, request)
    return {"ok": True, "plan_sha256": digest, "item_count": len(basis["items"]),
            "items": [{"artifact_id": row["artifact_id"], "from_state": row["from_state"], "to_state": row["to_state"],
                       "expected_current_state_sha256": row["expected_current_state_sha256"]} for row in basis["items"]],
            "whole_archive_closeout_claimed": False, "automatic_deletion_performed": False,
            "content_hashes_caller_supplied_not_verified": True, "paths_echoed": False}


def _control_path(root, digest, create=False):
    if type(digest) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise _fail("human_artifact_batch_plan_invalid")
    folder = ( _ensure_private_directory(root, ("profiles", "local", "human-artifact-batches"))
              if create else root / "profiles/local/human-artifact-batches")
    return folder / (digest.split(":")[1] + ".json")


def _load_control(root, digest):
    context = registry._validated_archive(root)
    authority = registry._load_authority(context, create=False)
    if authority is None:
        raise _fail("human_artifact_batch_control_invalid")
    control = json.loads(_read_plain_file(_control_path(root, digest), max_bytes=MAX_BYTES, heartbeat=lambda: None))
    registry._validate_authentication(control, authority[0])
    if (control.get("schema") != CONTROL_SCHEMA or control.get("plan_sha256") != digest
            or control.get("basis", {}).get("archive_id") != context.archive_id
            or _sha(_canonical(control["basis"])) != digest):
        raise _fail("human_artifact_batch_control_invalid")
    return control


def _approval_context(root, basis, digest, reviewer):
    return registry.ExactHumanApprovalContext(
        operation=registry.ExactHumanApprovalOperation.human_artifact_lifecycle,
        archive_identity_sha256=registry.exact_human_approval_archive_identity_sha256(services.read_archive_id(root)),
        plan_sha256=digest, target_binding_sha256=registry._approval_target_binding(basis),
        reviewer_claim=reviewer,
        review_binding_codes=("artifact_content_sha256", "artifact_observation", "current_state_digest", "lifecycle_target", "registry_plan"),
        warning_codes=("content_sha256_caller_supplied_not_registry_verified",))


def approval_context(archive_root, request, *, reviewer_claim, expected_plan_sha256=None, resume=False):
    root = services.require_existing_archive_root(archive_root)
    if resume:
        control = _load_control(root, expected_plan_sha256)
        if control["request"] != _request(request) or control["reviewer_claim"] != reviewer_claim:
            raise _fail("human_artifact_batch_resume_mismatch")
        basis, digest = control["basis"], control["plan_sha256"]
    else:
        _request_value, basis, _locators, digest = _prepare(root, request)
        if expected_plan_sha256 is not None and expected_plan_sha256 != digest:
            raise _fail("human_artifact_batch_plan_changed")
    return _approval_context(root, basis, digest, reviewer_claim)


def _append(context, key, state, item, approval, created_at):
    latest = state.chain.latest
    receipt_id = registry._validated_random_hex(registry.secrets.token_hex, prefix="har_receipt_")
    resulting = registry._state_document(artifact_id=item["artifact_id"],
        observation_sha256=state.observed.observation["observation_sha256"], lifecycle_state=item["to_state"],
        artifact_version_id=item["version"]["artifact_version_id"], content_sha256=item["version"]["content_sha256"],
        size_bytes=item["version"]["size_bytes"], last_receipt_id=receipt_id)
    receipt = registry._authenticated({"schema_version": registry.RECEIPT_SCHEMA_VERSION,
        "receipt_id": receipt_id, "artifact_id": item["artifact_id"], "root_id": item["root_id"], "root_kind": item["root_kind"],
        "sequence": len(state.chain.receipts) + 1, "previous_receipt_id": latest["receipt_id"] if latest else None,
        "expected_current_state_sha256": item["expected_current_state_sha256"],
        "resulting_current_state_sha256": registry._state_sha256(resulting), "from_state": item["from_state"],
        "to_state": item["to_state"], "observation": state.observed.observation, "version": item["version"],
        "related_refs": item["related_refs"], "transition_plan_sha256": registry._plan_sha256(item),
        "approval_reference": approval, "created_at": created_at, "automatic_deletion_performed": False,
        "content_sha256_verified_by_registry": False}, key)
    registry._validate_receipt_document(receipt, key)
    folder = registry._registry_subdirectory(context, registry.RECEIPTS_DIRECTORY, create=True) / item["artifact_id"]
    registry._safe_directory(folder, create=True)
    receipt_path = folder / (item["expected_current_state_sha256"].split(":")[1] + ".json")
    registry._exclusive_create(receipt_path, receipt,
        pending_directory=context.root / registry.REGISTRY_RELATIVE_ROOT / registry.PENDING_DIRECTORY,
        code="human_artifact_transition_conflict")
    verified = registry._validate_receipt_document(registry._read_json_document(receipt_path,
        code="human_artifact_transition_receipt_invalid"), key)
    if verified != receipt:
        raise _fail("human_artifact_batch_post_verification_failed")
    return verified


def apply(archive_root, request, *, expected_plan_sha256, reviewer_claim, approval_claim, resume=False, progress_hook=None):
    """Called inside the shared approval workflow; never finalize its claim."""
    root = services.require_existing_archive_root(archive_root)
    if type(approval_claim) is not registry._ClaimedExactHumanApproval:
        raise _fail("human_artifact_batch_approval_required")
    if type(expected_plan_sha256) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_plan_sha256):
        raise _fail("human_artifact_batch_plan_invalid")
    request = _request(request)
    # Serialize replay of this exact run, not unrelated registry batches.
    with TargetLease(root, kind="execution", reference="human-artifact-batch:" + expected_plan_sha256):
        context = registry._validated_archive(root)
        registry._require_private_registry_ignored(context)
        if resume:
            control = _load_control(root, expected_plan_sha256)
            if control["request"] != request or control["reviewer_claim"] != reviewer_claim:
                raise _fail("human_artifact_batch_resume_mismatch")
            basis, locators, digest = control["basis"], control["private_locators"], control["plan_sha256"]
        else:
            request, basis, locators, digest = _prepare(root, request)
            if digest != expected_plan_sha256:
                raise _fail("human_artifact_batch_plan_changed")
        completed_claim = False
        approval_context_value = _approval_context(root, basis, digest, reviewer_claim)
        try:
            reference = approval_claim.assert_ready_for_context(approval_context_value)
        except ExactHumanApprovalError:
            if not resume:
                raise
            reference = approval_claim.assert_succeeded_for_context(approval_context_value)
            completed_claim = True
        approval = registry._validate_exact_approval_reference(reference)
        with TargetLease(root, kind="file", reference=registry.REGISTRY_RELATIVE_ROOT + "/" + registry.AUTHORITY_FILENAME):
            authority = registry._load_authority(context, create=True)
        key = authority[0]
        if resume:
            if control["approval_reference"] != approval:
                raise _fail("human_artifact_batch_resume_approval_changed")
        else:
            created_at = registry._now(registry._default_clock)
            control = registry._authenticated({"schema": CONTROL_SCHEMA, "plan_sha256": digest,
                "request": request, "basis": basis, "private_locators": locators, "reviewer_claim": reviewer_claim,
                "approval_reference": approval, "created_at": created_at}, key)
            path = _control_path(root, digest, True)
            registry._exclusive_create(path, control, pending_directory=path.parent,
                                       code="human_artifact_transition_conflict")
        # If interrupted between control and spend, resume consumes the same
        # claim exactly once before any item. Existing usage must match it.
        used_path = context.root / registry.REGISTRY_RELATIVE_ROOT / registry.APPROVAL_USES_DIRECTORY / (approval["approval_id"] + ".json")
        batch_id = "har_batch_" + digest.split(":")[1]
        if used_path.exists():
            usage = registry._validate_approval_use_document(registry._read_json_document(used_path,
                code="human_artifact_registry_document_invalid"), key)
            if (not resume or usage["operation"] != "transition_batch" or usage["target_id"] != batch_id
                    or usage["context_sha256"] != approval["context_sha256"]
                    or usage["approval_authority_sha256"] != approval["approval_authority_sha256"]):
                raise _fail("human_artifact_batch_approval_replayed")
        else:
            if completed_claim:
                raise _fail("human_artifact_batch_completed_claim_usage_missing")
            registry._spend_approval(context, key, approval, operation="transition_batch", target_id=batch_id, used_at=control["created_at"])
        ids = [row["artifact_id"] for row in basis["items"]]
        _context, _authority, states = _selected_states(root, locators, ids, allow_unavailable=True)
        chains = registry._load_receipt_chains(context, authority, _artifact_ids=set(ids))
        results = []
        for item in basis["items"]:
            state = states[item["artifact_id"]]
            matching = [receipt for receipt in chains.get(item["artifact_id"], registry._ReceiptChain(())).receipts
                        if receipt["transition_plan_sha256"] == registry._plan_sha256(item)
                        and receipt["approval_reference"] == approval]
            if matching:
                results.append({"artifact_id": item["artifact_id"], "state": "already_recorded",
                                "receipt_id": matching[0]["receipt_id"],
                                "current_file_matches_recorded_observation": bool(state is not None and
                                    state.observed.observation["observation_sha256"] == matching[0]["observation"]["observation_sha256"])})
                continue
            if completed_claim:
                results.append({"artifact_id": item["artifact_id"], "state": "recorded_receipt_missing_requires_review"})
                continue
            if (state is None or state.current_state_sha256 != item["expected_current_state_sha256"]
                    or not registry._artifact_observation_still_matches(state)):
                results.append({"artifact_id": item["artifact_id"], "state": "conflict_requires_review"})
                continue
            try:
                # A busy artifact does not hold back other items in this batch.
                # Resume retries it against the original claim and state CAS.
                with TargetLease(root, kind="file",
                                 reference=registry.REGISTRY_RELATIVE_ROOT + "/" + registry.RECEIPTS_DIRECTORY + "/" + item["artifact_id"],
                                 timeout_seconds=0):
                    receipt = _append(context, key, state, item, approval, control["created_at"])
            except ExactOperationManifestError as error:
                if str(error) != "exact_operation_writer_busy":
                    raise
                results.append({"artifact_id": item["artifact_id"], "state": "target_busy_retryable"})
                continue
            except registry.HumanArtifactRegistryError as error:
                # A legacy single-item writer may race this batch's observation.
                # Its exclusive receipt creation wins only this artifact; keep
                # the remaining disjoint items moving without rewriting it.
                if str(error) != "human_artifact_transition_conflict":
                    raise
                results.append({"artifact_id": item["artifact_id"], "state": "conflict_requires_review"})
                continue
            status = "recorded" if registry._artifact_observation_still_matches(state) else "recorded_but_artifact_changed"
            results.append({"artifact_id": item["artifact_id"], "state": status, "receipt_id": receipt["receipt_id"]})
            if progress_hook:
                progress_hook({"completed_count": len(results), "item_count": len(ids)})
        conflicts = sum(row["state"] not in {"recorded", "already_recorded"} for row in results)
        retryable = sum(row["state"] == "target_busy_retryable" for row in results)
        state = "recorded" if not conflicts else "partial_retryable" if conflicts == retryable else "partial_requires_review"
        return {"ok": conflicts == 0, "state": state,
                "plan_sha256": digest, "item_count": len(ids), "recorded_count": len(results) - conflicts,
                "conflict_count": conflicts, "retryable_count": retryable, "items": results, "resume_supported": True,
                "completed_claim_reconciliation_only": completed_claim,
                "whole_archive_closeout_claimed": False, "automatic_deletion_performed": False,
                "artifact_bodies_read": False, "paths_echoed": False}
