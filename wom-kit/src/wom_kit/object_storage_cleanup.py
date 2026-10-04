"""Approved permanent disposal of exactly qualified remote temporary objects.

Remote keys are opaque data, never filesystem paths. Qualification is separate
from upload/adoption: missing upload receipts are not a permanent exclusion.
All locator-bearing evidence and the authenticated, resumable journal stay in
the ignored local profile. A pending tombstone is published under the archive
writer lock before a fresh whole GET and DELETE. Other WOM writers must call
``assert_referenceable`` / ``assert_remote_available`` under that same lock.

R2 conditional DELETE is not assumed. Without a verified conditional-delete
adapter, execution requires reviewed evidence excluding other writers and
binding these exact immutable keys to this archive. Local leases alone cannot
protect another device or a writer outside WOM.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import stat
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from . import archive_services as services
from .exact_operation_manifest import exact_operation_writer_lock
from .operation_target_leases import TargetLeases
from .remote_preservation_proof import strong_etag

ROOT = "profiles/local/remote-disposal"
REQUEST_SCHEMA = "wom-kit/remote-disposal-request/v1"
MANAGEMENT_SCHEMA = "wom-kit/remote-disposal-management/v1"
CLASSIFICATION_SCHEMA = "wom-kit/remote-disposal-classification/v1"
INVENTORY_SCHEMA = "wom-kit/remote-disposal-inventory/v1"
PLAN_SCHEMA = "wom-kit/object-storage-cleanup-plan/v1"
RESULT_SCHEMA = "wom-kit/object-storage-cleanup-result/v1"
QUALIFICATION_SCHEMA = "wom-kit/remote-disposal-qualification/v1"
MAX_ENTRIES = 100_000
MAX_DOCUMENT = 64 * 1024 * 1024
MAX_CONTENT_SAMPLE_ENTRIES = 4096
CONTENT_SAMPLE_BYTES = 4096
OID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DOMAIN = b"wom-kit/remote-disposal-journal/v1\0"


class ObjectStorageCleanupError(services.ArchiveServiceError):
    """Fixed-code boundary; no remote key, private path or provider body."""

    def __init__(self, code="object_storage_cleanup_invalid"):
        self.code = code if re.fullmatch(r"[a-z_]{1,96}", str(code)) else "object_storage_cleanup_invalid"
        super().__init__(self.code)


def _fail(code="object_storage_cleanup_invalid"):
    return ObjectStorageCleanupError(code)


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, TypeError, UnicodeError):
        raise _fail() from None


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _fail()
        result[key] = value
    return result


def _json(raw):
    if len(raw) > MAX_DOCUMENT:
        raise _fail("object_storage_cleanup_evidence_too_large")
    try:
        return json.loads(raw, object_pairs_hook=_unique_pairs)
    except (ValueError, TypeError, UnicodeError):
        raise _fail("object_storage_cleanup_evidence_invalid") from None


def _root(root):
    return services.require_existing_archive_root(root)


def _read(root, relative):
    try:
        path = services.archive_internal_path(root, relative)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_DOCUMENT:
            raise _fail()
        raw = path.read_bytes()
        return _json(raw), "sha256:" + hashlib.sha256(raw).hexdigest()
    except ObjectStorageCleanupError:
        raise
    except Exception:
        raise _fail("object_storage_cleanup_evidence_unreadable") from None


def _private_read(root, relative):
    from .operator_feedback_body import _require_effective_gitignore
    if not isinstance(relative, str) or not relative.startswith("profiles/local/"):
        raise _fail("object_storage_cleanup_private_evidence_required")
    _require_effective_gitignore(root, relative)
    return _read(root, relative)


def _private_write(root, relative, document):
    from .operator_feedback_body import _require_effective_gitignore
    _require_effective_gitignore(root, relative)
    path = services.archive_internal_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Resolve again after creation to reject a changed/reparse-point path chain.
    path = services.archive_internal_path(root, relative)
    services.write_bytes_atomic(path, _canonical(document) + b"\n")


def _mac(root, document, key_provider=None):
    from .exact_human_approval_workflow import _production_key_provider
    from .operation_cancellation import ACTIVE_CLAIM
    # The broker's active-claim scope also supplies this fixed-domain journal
    # capability. Do not reopen a protected key consumer inside its callback.
    active = ACTIVE_CLAIM.get()
    if active is not None:
        return active.remote_disposal_mac(root, _canonical(document))
    provider = key_provider or _production_key_provider()
    return provider.use_key(root, lambda key: hmac.new(bytes(key), _DOMAIN + _canonical(document), hashlib.sha256).hexdigest(),
                            create_if_missing=False)


def _save_signed(root, relative, document, key_provider=None):
    _private_write(root, relative, {"document": document, "mac": _mac(root, document, key_provider)})


def _load_signed(root, relative, key_provider=None):
    value, _ = _private_read(root, relative)
    try:
        if not hmac.compare_digest(value["mac"], _mac(root, value["document"], key_provider)):
            raise _fail()
        return value["document"]
    except Exception:
        raise _fail("object_storage_cleanup_journal_invalid") from None


def _archive_identity(root):
    from .exact_human_approval import exact_human_approval_archive_identity_sha256
    return exact_human_approval_archive_identity_sha256(services.read_archive_id(root))


def _key(value):
    # S3 keys may include spaces, unicode, literal percent signs and '..'. No
    # filesystem operation receives this value; SigV4 encodes it exactly once.
    if (not isinstance(value, str) or not value or len(value.encode("utf-8")) > 1024
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise _fail("object_storage_cleanup_key_invalid")
    return value


def _store(value):
    if not isinstance(value, str) or value != value.strip() or not services.safe_object_storage_ref(value):
        raise _fail("object_storage_cleanup_store_invalid")
    return value


def _binding(value):
    if (not isinstance(value, dict) or set(value) != {"service", "endpoint_host", "bucket", "region"}
            or value["service"] != "s3" or any(not isinstance(v, str) or not v for v in value.values())):
        raise _fail("object_storage_cleanup_remote_binding_invalid")
    if (not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]{1,5})?", value["endpoint_host"])
            or not services.safe_object_storage_bucket_name(value["bucket"])
            or not services.safe_object_storage_region(value["region"])):
        raise _fail("object_storage_cleanup_remote_binding_invalid")
    return value


def entry_id(store_ref, remote_key):
    return _digest({"store_ref": store_ref, "remote_key": _key(remote_key)})


def _read_entries(root, request, key_provider=None):
    if request.get("inventory_path"):
        inventory = _load_signed(root, request["inventory_path"], key_provider)
        if (inventory.get("schema") != INVENTORY_SCHEMA or inventory.get("archive_identity_sha256") != _archive_identity(root)
                or inventory.get("store_ref") != request["store_ref"] or inventory.get("remote_binding") != request["remote_binding"]
                or inventory.get("complete") is not True):
            raise _fail("object_storage_cleanup_inventory_incomplete")
        selected = request.get("entry_ids")
        if (not isinstance(selected, list) or not selected or any(not isinstance(value, str) for value in selected)
                or len(set(selected)) != len(selected)):
            raise _fail()
        rows = [row for row in inventory["entries"] if row["entry_id"] in selected]
        if len(rows) != len(selected):
            raise _fail("object_storage_cleanup_selection_invalid")
    else:
        rows = request.get("entries")
    if not isinstance(rows, list) or not rows or len(rows) > MAX_ENTRIES:
        raise _fail("object_storage_cleanup_selection_invalid")
    entries = []
    for row in rows:
        if not isinstance(row, dict):
            raise _fail()
        key, oid, size = _key(row.get("remote_key")), row.get("object_id"), row.get("size")
        if not isinstance(oid, str) or not OID.fullmatch(oid) or type(size) is not int or size < 0:
            raise _fail("object_storage_cleanup_identity_required")
        entries.append({"entry_id": entry_id(request["store_ref"], key), "store_ref": request["store_ref"],
                        "remote_key": key, "object_id": oid, "size": size})
    if len({row["entry_id"] for row in entries}) != len(entries):
        raise _fail("object_storage_cleanup_duplicate_key")
    return sorted(entries, key=lambda row: row["entry_id"])


def _files(root, base):
    """No omitted links/unreadable directories in a deletion safety scan."""
    paths = []
    def checked(path):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise _fail("object_storage_cleanup_reference_scan_incomplete")
        return info
    try:
        if not stat.S_ISDIR(checked(base).st_mode):
            return [base]
        def fail_walk(_error):
            raise _fail("object_storage_cleanup_reference_scan_incomplete")
        for directory, names, files in os.walk(base, followlinks=False, onerror=fail_walk):
            for name in names:
                checked(Path(directory) / name)
            for name in files:
                path = Path(directory) / name
                if not stat.S_ISREG(checked(path).st_mode) or not path.resolve().is_relative_to(root):
                    raise _fail("object_storage_cleanup_reference_scan_incomplete")
                paths.append(path)
        return sorted(paths)
    except ObjectStorageCleanupError:
        raise
    except (OSError, ValueError):
        raise _fail("object_storage_cleanup_reference_scan_incomplete") from None


def _mentioned_ids(text):
    return {"sha256:" + digest for digest in re.findall(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", text)}


# v0.4.62 (letter 181 B): the reference scan ran once per deleted key and spent
# most of its time re-deriving the same facts from unchanged bytes. Every file
# is still read and hashed on every scan (the evidence digest is unchanged);
# only the pure results derived from exactly those bytes are remembered.
_MENTION_MEMO: dict[str, frozenset[str]] = {}
_MANIFEST_LINE_MEMO: dict[bytes, tuple[Any, ...]] = {}
_MEMO_LIMIT = 400_000


def _remembered_mentions(digest: str, raw: bytes) -> frozenset[str]:
    mentioned = _MENTION_MEMO.get(digest)
    if mentioned is None:
        mentioned = frozenset(_mentioned_ids(raw.decode("utf-8")))
        if len(_MENTION_MEMO) >= _MEMO_LIMIT:
            _MENTION_MEMO.clear()
        _MENTION_MEMO[digest] = mentioned
    return mentioned


def _manifest_line_facts(line: bytes) -> tuple[Any, ...]:
    facts = _MANIFEST_LINE_MEMO.get(line)
    if facts is None:
        row = _json(line)
        if not isinstance(row, dict):
            raise _fail("object_storage_cleanup_reference_scan_incomplete")
        provenance = row.get("provenance") or {}
        source = provenance.get("source") if isinstance(provenance, dict) else None
        encoded = _canonical(row).decode("ascii")
        snapshot_like = isinstance(source, str) and any(
            word in source for word in ("snapshot", "revision", "title_remap", "activity_group"))
        facts = (row.get("object_id"), snapshot_like, frozenset(_mentioned_ids(encoded)), encoded,
                 json.dumps(row, sort_keys=True))
        if len(_MANIFEST_LINE_MEMO) >= _MEMO_LIMIT:
            _MANIFEST_LINE_MEMO.clear()
        _MANIFEST_LINE_MEMO[line] = facts
    # A fresh row object per scan: callers never share mutable state.
    return (*facts[:4], json.loads(facts[4]))


def _references(root, entries):
    """Full local reference scan. Any unreadable evidence fails the whole scan.

    Receipts that merely say an object was uploaded are not usage. Retained
    revisions, drafts and derived text are. Active target operations serialize
    through the shared object leases; new references honor the pending fence.
    Own file-manifest identity is excluded, but snapshot provenance protects
    snapshot objects and cross-object fields protect their dependencies.
    """
    ids = {row["object_id"] for row in entries}
    targets_by_location = {(row["store_ref"], row["remote_key"]): row for row in entries}
    refs = {oid: [] for oid in ids}
    evidence = []
    areas = ("zettels", "inbox", "receipts/revisions", "receipts/activity-groups",
             "receipts/source-fidelity", "objects/manifests/derived-text.jsonl")
    for area in areas:
        base = services.archive_internal_path(root, area)
        if not base.exists():
            continue
        paths = _files(root, base)
        for path in sorted(paths):
            if path.is_dir():
                continue
            try:
                if path.is_symlink() or path.stat().st_size > MAX_DOCUMENT:
                    raise _fail()
                raw = path.read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                mentioned = _remembered_mentions(digest, raw)
                relative = path.relative_to(root).as_posix()
            except Exception:
                raise _fail("object_storage_cleanup_reference_scan_incomplete") from None
            evidence.append([relative, digest])
            for oid in ids & mentioned:
                refs[oid].append(_digest(relative))
    manifest = services.archive_internal_path(root, "objects/manifests/files.jsonl")
    if manifest.exists():
        if manifest.stat().st_size > MAX_DOCUMENT:
            raise _fail("object_storage_cleanup_reference_scan_incomplete")
        raw = manifest.read_bytes()
        evidence.append(["objects/manifests/files.jsonl", hashlib.sha256(raw).hexdigest()])
        for line in raw.splitlines():
            if not line.strip():
                continue
            own, snapshot_like, mentioned, encoded, row = _manifest_line_facts(line)
            for oid in ids & mentioned:
                if own == oid:
                    if snapshot_like:
                        refs[oid].append("retained_snapshot_or_provider_object")
                elif oid[7:] in encoded:
                    refs[oid].append("other_object_dependency")
            if snapshot_like:
                # A retained old note can be the only remaining use of a source
                # object. Inspect that immutable note, not just its receipt's hash.
                local = [location for location in row.get("locations", []) if isinstance(location, dict)
                         and location.get("provider") == "local" and location.get("availability") == "available"]
                if not local or not isinstance(own, str) or not OID.fullmatch(own):
                    raise _fail("object_storage_cleanup_reference_scan_incomplete")
                for location in local:
                    relative = location.get("path")
                    try:
                        if services.objet_capture_path_chain_blockers(root, relative):
                            raise _fail()
                        path = services.archive_internal_path(root, relative)
                        if path.stat().st_size > MAX_DOCUMENT:
                            raise _fail()
                        snapshot = path.read_bytes()
                        if hashlib.sha256(snapshot).hexdigest() != own[7:]:
                            raise _fail()
                        mentions = _mentioned_ids(snapshot.decode("utf-8"))
                    except Exception:
                        raise _fail("object_storage_cleanup_reference_scan_incomplete") from None
                    evidence.append([relative, own[7:]])
                    for oid in ids & mentions:
                        refs[oid].append("retained_snapshot_dependency")
            for location in row.get("locations", []) or []:
                if isinstance(location, dict) and location.get("provider") == "object_storage":
                    target = targets_by_location.get((location.get("store_ref"), location.get("remote_key")))
                    if target and own != target["object_id"]:
                        refs[target["object_id"]].append("remote_key_shared_by_other_object")
    # Draft fidelity scanner also follows the retained source receipts.
    from .object_storage_offload import _draft_retention_evidence
    drafts = _draft_retention_evidence(root)
    if drafts.unreadable_draft_count or drafts.unreadable_fidelity_receipt_count:
        raise _fail("object_storage_cleanup_reference_scan_incomplete")
    for oid in ids & (drafts.referenced | drafts.fidelity_sources):
        refs[oid].append("draft_or_fidelity_dependency")
    return refs, _digest(sorted(evidence))


def _prepare(root, request_path, key_provider=None):
    request, request_sha = _private_read(root, request_path)
    if not isinstance(request, dict) or request.get("schema") != REQUEST_SCHEMA:
        raise _fail()
    _store(request.get("store_ref"))
    _binding(request.get("remote_binding"))
    if request.get("provider_kind") not in {"cloudflare-r2", "generic-s3"}:
        raise _fail()
    entries = _read_entries(root, request, key_provider)
    classification, classification_sha = _private_read(root, request.get("classification_path"))
    management, management_sha = _private_read(root, request.get("management_path"))
    if (classification.get("schema") != CLASSIFICATION_SCHEMA or management.get("schema") != MANAGEMENT_SCHEMA
            or management.get("archive_identity_sha256") != _archive_identity(root)
            or management.get("remote_binding") != request["remote_binding"]
            or management.get("store_ref") != request["store_ref"]):
        raise _fail("object_storage_cleanup_qualification_invalid")
    decisions = classification.get("entries")
    if not isinstance(decisions, list) or any(not isinstance(row, dict) for row in decisions):
        raise _fail()
    by_id = {row.get("entry_id"): row for row in decisions}
    if len(by_id) != len(decisions):
        raise _fail()
    managed_ids = management.get("entry_ids")
    if not isinstance(managed_ids, list) or any(not isinstance(value, str) or not OID.fullmatch(value) for value in managed_ids):
        raise _fail()
    refs, refs_sha = _references(root, entries)
    eligible = []
    for row in entries:
        judgment = by_id.get(row["entry_id"], {})
        reasons = []
        if (judgment.get("decision") != "temporary_unnecessary" or not isinstance(judgment.get("reason"), str)
                or not judgment["reason"].strip() or judgment.get("object_id") != row["object_id"]):
            reasons.append("needs_classification")
        if row["entry_id"] not in managed_ids or management.get("authority") != "exclusive_wom":
            reasons.append("needs_management_binding")
        if management.get("external_writers") != "excluded" or management.get("immutable_keys") is not True:
            reasons.append("external_writer_possible")
        if refs[row["object_id"]]:
            reasons.append("referenced_or_retained")
        row["reason_codes"] = reasons
        if not reasons:
            eligible.append(row["entry_id"])
    binding = {"schema": PLAN_SCHEMA, "archive_identity_sha256": _archive_identity(root),
               "request_sha256": request_sha, "classification_sha256": classification_sha,
               "management_sha256": management_sha, "reference_scan_sha256": refs_sha,
               "entries": entries, "permanent": True, "recovery_guaranteed": False}
    return request, entries, binding, eligible


def plan_cleanup(archive_root, *, request_path, key_provider=None):
    root = _root(archive_root)
    request, entries, binding, eligible = _prepare(root, request_path, key_provider)
    return {"schema": PLAN_SCHEMA, "ok": True, "blockers": [], "plan_sha256": _digest(binding), "state": "ready" if eligible else "review_required",
            "selected_count": len(entries), "eligible_count": len(eligible), "permanent": True, "recovery_guaranteed": False,
            "items": [{"entry_id": row["entry_id"], "state": "qualified" if not row["reason_codes"] else "review_required",
                       "reason_codes": row["reason_codes"]} for row in entries], "private_values_echoed": False}


def _authorize(root, *, operation, reviewed_by, exact_human_approval_claim, expected_plan_sha256,
               expected_exact_approval_plan_sha256, expected_exact_approval_target_binding_sha256):
    from .exact_human_approval_windows import ExactHumanApprovalOperation
    from .operation_approval_binding import plan_digest_approval_binding
    if exact_human_approval_claim is None:
        raise _fail("object_storage_cleanup_approval_required")
    reviewer = services.safe_project_intake_actor_id(reviewed_by)
    if reviewer is None:
        raise _fail("object_storage_cleanup_reviewer_invalid")
    services._require_exact_human_operation_approval(
        root, plan_digest_approval_binding(getattr(ExactHumanApprovalOperation, operation), expected_plan_sha256),
        reviewer_claim=reviewer, expected_plan_sha256=expected_exact_approval_plan_sha256,
        expected_target_binding_sha256=expected_exact_approval_target_binding_sha256, claim=exact_human_approval_claim)


def _state_path(store_ref, remote_key):
    return ROOT + "/targets/" + entry_id(store_ref, remote_key)[7:] + ".json"


def assert_remote_available(archive_root, *, store_ref, remote_key, object_id=None, key_provider=None):
    """Writers/readers call under their existing archive lock; never clears state."""
    root = _root(archive_root)
    relative = _state_path(store_ref, remote_key)
    if services.archive_internal_path(root, relative).exists():
        state = _load_signed(root, relative, key_provider)
        if state.get("state") in {"pending", "deleted", "outcome_unknown"}:
            raise _fail("object_storage_remote_disposed_or_pending")


def assert_referenceable(archive_root, object_ids, *, key_provider=None):
    """Fence concurrent object use while deletion's remote result is unknown.

    A completed deletion removes one location, not every copy of the same hash.
    A new reference then requires a surviving hash-verified local copy or another
    official verified remote location. This helper never calls the provider.
    """
    root = _root(archive_root)
    directory = services.archive_internal_path(root, ROOT + "/targets")
    if not directory.exists():
        return
    ids = set(object_ids)
    deleted_ids = set()
    for path in _files(root, directory):
        if path.suffix != ".json":
            raise _fail("object_storage_cleanup_journal_invalid")
        state = _load_signed(root, path.relative_to(root).as_posix(), key_provider)
        if state.get("object_id") in ids and state.get("state") in {"pending", "outcome_unknown"}:
            raise _fail("object_storage_remote_disposed_or_pending")
        if state.get("object_id") in ids and state.get("state") == "deleted":
            deleted_ids.add(state["object_id"])
    if deleted_ids:
        _require_surviving_copies(root, deleted_ids, key_provider=key_provider)


def _local_copy_matches(root, location, object_id, size):
    relative = location.get("path")
    if not isinstance(relative, str) or location.get("availability") != "available":
        return False
    try:
        if services.objet_capture_path_chain_blockers(root, relative):
            return False
        path = services.archive_internal_path(root, relative)
        before = path.lstat()
        if (not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode)
                or getattr(before, "st_file_attributes", 0) & 0x400 or before.st_size != size):
            return False
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_size) != (before.st_dev, before.st_ino, size):
                return False
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            after = os.fstat(handle.fileno())
        final = path.lstat()
        fields = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
        return fields(before) == fields(after) == fields(final) and digest.hexdigest() == object_id[7:]
    except (OSError, ValueError, services.ArchiveServiceError):
        return False


def _require_surviving_copies(root, object_ids, *, key_provider=None):
    manifest = services.archive_internal_path(root, "objects/manifests/files.jsonl")
    try:
        if not manifest.is_file() or manifest.stat().st_size > MAX_DOCUMENT:
            raise _fail()
        rows = [_json(line) for line in manifest.read_bytes().splitlines() if line.strip()]
    except Exception:
        raise _fail("object_storage_remote_disposed_without_usable_copy") from None
    usable = set()
    sizes = {}
    for row in rows:
        if not isinstance(row, dict):
            raise _fail("object_storage_cleanup_evidence_invalid")
        oid, size = row.get("object_id"), row.get("size_bytes")
        if oid not in object_ids or oid in usable or type(size) is not int or size < 0:
            continue
        sizes.setdefault(oid, set()).add(size)
        locations = filter_remote_locations(root, row.get("locations", []), object_id=oid, key_provider=key_provider)
        for location in locations:
            if location.get("provider") == "local" and _local_copy_matches(root, location, oid, size):
                usable.add(oid)
                break
            if (location.get("provider") == "object_storage" and location.get("availability") == "wom_uploaded"
                    and location.get("remote_key_verified") is True and location.get("provider_confirmation_by_wom_kit") is True
                    and isinstance(location.get("execution_receipt_ref"), str) and location["execution_receipt_ref"]
                    and location.get("remote_key") and location.get("store_ref")):
                # Existing official remote evidence can authorize a link without
                # downloading again during a local note write. Merely declared
                # locations are never enough; open/restore still reprove bytes.
                errors = services.object_storage_wom_uploaded_audit_location_errors(location, digest=oid[7:],
                    provider_kind=str(location.get("provider_kind") or ""), store_ref=str(location["store_ref"]))
                if not errors:
                    usable.add(oid)
                    break
    # Emergency preservation is intentionally receipt-backed until adoption.
    # It can be a valid surviving copy without a remote manifest location.
    remaining = object_ids - usable
    if remaining:
        from . import object_storage_preservation as preservation
        directory = services.archive_internal_path(root, preservation.RECEIPT_ROOT)
        if directory.is_dir():
            for oid in remaining:
                expected_sizes = sizes.get(oid, set())
                if len(expected_sizes) != 1:
                    continue
                size = next(iter(expected_sizes))
                for path in directory.glob(oid[7:] + ".*.json"):
                    try:
                        document, _ = _read(root, path.relative_to(root).as_posix())
                        if document.get("preservation_status") not in {"bytes_preserved", "already_remote_verified"}:
                            continue
                        store, provider, inventory = document.get("store_ref"), document.get("provider_kind"), document.get("source_inventory_sha256")
                        _store(store)
                        if provider not in {"cloudflare-r2", "generic-s3"} or not isinstance(inventory, str) or not OID.fullmatch(inventory):
                            continue
                        token = preservation._receipt_token(object_id=oid, size_bytes=size, provider_kind=provider,
                            store_ref=store, inventory_sha256=inventory)
                        if not preservation._existing_receipt_matches(document, receipt_token=token, object_id=oid,
                            size_bytes=size, provider_kind=provider, store_ref=store, inventory_sha256=inventory):
                            continue
                        key = preservation.object_storage_bytes_preserved_remote_key(oid)
                        if filter_remote_locations(root, [{"provider": "object_storage", "store_ref": store, "remote_key": key}],
                                                   object_id=oid, key_provider=key_provider):
                            usable.add(oid)
                            break
                    except Exception:
                        continue
    if object_ids - usable:
        raise _fail("object_storage_remote_disposed_without_usable_copy")


def filter_remote_locations(archive_root, locations, *, object_id=None, key_provider=None):
    """Project manifest locations through the authoritative private tombstones.

    Keep every local/other-provider location and each independently retained
    remote key. Invalid journal authentication fails closed, never hides damage.
    """
    root = _root(archive_root)
    result = []
    for location in locations:
        if not isinstance(location, dict):
            raise _fail("object_storage_cleanup_location_invalid")
        if location.get("provider") != "object_storage" or not location.get("remote_key"):
            result.append(location)
            continue
        relative = _state_path(location.get("store_ref"), location["remote_key"])
        if services.archive_internal_path(root, relative).exists():
            state = _load_signed(root, relative, key_provider)
            if state.get("state") in {"pending", "deleted", "outcome_unknown"}:
                continue
        result.append(location)
    return result


class CleanupTransportAdapter:
    """Typed data-plane adapter over the existing authenticated S3 transport."""
    conditional_delete_supported = False  # R2 support is not inferred from AWS.

    def __init__(self, transport):
        self.transport = transport

    def preservation_binding(self):
        return self.transport.preservation_binding()

    def head_object(self, **kwargs):
        return self.transport.head_object(**kwargs)

    def inspect_object(self, *, key):
        inspect = getattr(self.transport, "inspect_object", None)
        return (inspect(key=key, max_prefix_bytes=CONTENT_SAMPLE_BYTES) if callable(inspect)
                else self.transport.head_object(key=key, presence_only=False))

    def delete_exact(self, *, key, etag=None):
        # Never use the legacy delete_object method which discards HTTP status.
        response = self.transport._dispatch(method="DELETE", key=key, payload_hash=services.SIGV4_UNSIGNED_PAYLOAD)
        if response.get("transport_error"):
            return {"state": "unknown"}
        status = response.get("status")
        return {"state": "accepted" if status in {200, 202, 204, 404} else "rejected"}

    def list_page(self, *, prefix, continuation_token=None):
        query = {"list-type": "2", "prefix": prefix, "max-keys": "1000", "encoding-type": "url"}
        if continuation_token:
            query["continuation-token"] = continuation_token
        response = self.transport._dispatch(method="GET", key="", payload_hash=services.SIGV4_UNSIGNED_PAYLOAD, query=query)
        raw = response.get("body")
        if (response.get("transport_error") or response.get("body_truncated") or response.get("body_complete") is False
                or response.get("status") != 200 or not isinstance(raw, bytes)
                or len(raw) > 4 * 1024 * 1024 or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper()):
            raise _fail("object_storage_cleanup_inventory_unavailable")
        try:
            from urllib.parse import unquote
            tree = ElementTree.fromstring(raw)
            ns = "{http://s3.amazonaws.com/doc/2006-03-01/}" if tree.tag.startswith("{") else ""
            keys = [_key(unquote(node.findtext(ns + "Key"), errors="strict")) for node in tree.findall(ns + "Contents")]
            truncated = tree.findtext(ns + "IsTruncated")
            if truncated not in {"true", "false"}:
                raise ValueError()
            token = tree.findtext(ns + "NextContinuationToken") if truncated == "true" else None
            if truncated == "true" and not token:
                raise ValueError()
            return {"keys": keys, "continuation_token": token}
        except Exception:
            raise _fail("object_storage_cleanup_inventory_invalid") from None


def _adapt(transport):
    return transport if callable(getattr(transport, "delete_exact", None)) else CleanupTransportAdapter(transport)


def _proof(transport, entry):
    try:
        result = transport.head_object(key=entry["remote_key"], presence_only=False)
    except Exception:
        return "remote_unavailable", None
    if result.get("presence_state") == "absent" and result.get("present") is False:
        return "absent", None
    if (result.get("presence_state") != "present" or result.get("present") is not True
            or result.get("verification_state") != "complete"):
        return "remote_unavailable", None
    if result.get("size") != entry["size"] or result.get("checksum_sha256") != entry["object_id"][7:]:
        return "remote_changed", None
    return "verified", strong_etag(result.get("whole_get_etag"))


def _absent(transport, key):
    try:
        value = transport.head_object(key=key, presence_only=True)
        return value.get("presence_state") == "absent" and value.get("present") is False
    except Exception:
        return False


def _cleanup_checkpoint(result, entries):
    """Acknowledge only before a request or after its durable outcome record."""
    from .operation_cancellation import checkpoint, OperationCancelled
    try:
        checkpoint()
    except OperationCancelled:
        recorded = {item["entry_id"] for item in result["items"]}
        result["items"].extend({"entry_id": item["entry_id"], "state": "not_attempted"}
                               for item in entries if item["entry_id"] not in recorded)
        result.update(ok=False, state="cancelled_at_checkpoint", cause_code="operation_cancelled_at_checkpoint",
            blockers=["operation_cancelled_at_checkpoint"], cancel_requested=True, cancel_acknowledged=True,
            process_killed=False, provider_request_in_flight=False,
            recorded_item_count=len(recorded),
            unknown_outcome_count=sum(item["state"] == "outcome_unknown" for item in result["items"]),
            per_key_journal_resume_supported=True, same_claim_resume_supported=False,
            next_safe_actions=["preserve_per_key_disposal_journal", "resume_exact_cleanup_request_after_current_approval"])
        return True
    return False


def execute_cleanup_approved(archive_root, *, request_path, expected_plan_sha256, reviewed_by,
                             exact_human_approval_claim, expected_exact_approval_plan_sha256,
                             expected_exact_approval_target_binding_sha256, transport_factory,
                             key_provider=None, heartbeat=lambda: None, fault_hook=lambda _stage, _entry: None,
                             progress=None):
    root = _root(archive_root)
    _authorize(root, operation="object_storage_remote_cleanup", reviewed_by=reviewed_by,
               exact_human_approval_claim=exact_human_approval_claim, expected_plan_sha256=expected_plan_sha256,
               expected_exact_approval_plan_sha256=expected_exact_approval_plan_sha256,
               expected_exact_approval_target_binding_sha256=expected_exact_approval_target_binding_sha256)
    request, entries, binding, eligible = _prepare(root, request_path, key_provider)
    if _digest(binding) != expected_plan_sha256:
        raise _fail("object_storage_cleanup_plan_changed")
    result = {"schema": RESULT_SCHEMA, "ok": True, "plan_sha256": expected_plan_sha256, "items": [], "private_values_echoed": False,
              "permanent": True, "recovery_guaranteed": False}
    if not eligible:
        result["ok"] = False
        result["state"] = "review_required"
        result["items"] = [{"entry_id": row["entry_id"], "state": "review_required", "reason_codes": row["reason_codes"]} for row in entries]
        return result
    transport = _adapt(transport_factory())
    if transport.preservation_binding() != request["remote_binding"]:
        raise _fail("object_storage_cleanup_remote_binding_changed")
    total = len(entries)
    index = 0
    while index < total:
        if _cleanup_checkpoint(result, entries):
            return result
        heartbeat()
        group = []
        while index < total and len(group) < CLEANUP_FENCE_CHUNK:
            entry = entries[index]
            index += 1
            if entry["reason_codes"]:
                result["items"].append({"entry_id": entry["entry_id"], "state": "review_required", "reason_codes": entry["reason_codes"]})
                continue
            group.append(entry)
        if not group:
            continue
        # v0.4.62 (letter 181 B): one fresh reference scan under the writer
        # lock publishes the pending fences of a whole chunk (the fence other
        # writers honour under the same lock); each key then still does
        # proof -> delete intent -> DELETE -> absence check -> final journal.
        targets = [target for entry in group for target in (("object", entry["object_id"]), ("execution", entry["entry_id"]))]
        with TargetLeases(root, targets, heartbeat=heartbeat) as lease:
            fenced = []
            with exact_operation_writer_lock(root):
                # Bind all private source files again after waiting for leases.
                fresh_request, fresh_entries, fresh_binding, fresh_eligible = _prepare(root, request_path, key_provider)
                if _digest(fresh_binding) != expected_plan_sha256 or any(entry["entry_id"] not in fresh_eligible for entry in group):
                    raise _fail("object_storage_cleanup_plan_changed")
                for entry in group:
                    relative = _state_path(request["store_ref"], entry["remote_key"])
                    path = services.archive_internal_path(root, relative)
                    previous = _load_signed(root, relative, key_provider) if path.exists() else None
                    if previous and (previous.get("entry_id") != entry["entry_id"] or previous.get("object_id") != entry["object_id"]
                                     or previous.get("remote_binding") != request["remote_binding"]):
                        raise _fail("object_storage_cleanup_journal_conflict")
                    if previous and previous.get("state") == "deleted":
                        result["items"].append({"entry_id": entry["entry_id"], "state": "already_deleted"})
                        continue
                    journal = {"schema": QUALIFICATION_SCHEMA, "archive_identity_sha256": _archive_identity(root),
                               "entry_id": entry["entry_id"], "object_id": entry["object_id"], "remote_key": entry["remote_key"],
                               "size": entry["size"], "store_ref": request["store_ref"], "remote_binding": request["remote_binding"],
                               "plan_sha256": expected_plan_sha256, "classification_sha256": binding["classification_sha256"],
                               "management_sha256": binding["management_sha256"], "reference_scan_sha256": binding["reference_scan_sha256"],
                               "state": "pending", "delete_intent_recorded": bool(previous and previous.get("delete_intent_recorded")),
                               "recovery_guaranteed": False}
                    _save_signed(root, relative, journal, key_provider)
                    fenced.append((entry, relative, journal))
            for position, (entry, relative, journal) in enumerate(fenced):
                if position and _cancel_requested():
                    # No request was sent for the rest of this chunk: release
                    # their fences (a key with a recorded delete intent keeps
                    # its pending journal for the absence-confirming resume).
                    with exact_operation_writer_lock(root):
                        lease.verify_held()
                        for _rest, rest_relative, rest_journal in fenced[position:]:
                            if not rest_journal["delete_intent_recorded"]:
                                rest_journal.update(state="preserved", result_code="not_attempted")
                                _save_signed(root, rest_relative, rest_journal, key_provider)
                    _cleanup_checkpoint(result, entries)
                    return result
                _report_cleanup_progress(progress, result, total)
                state = _dispose_fenced_key(root, transport, entry, relative, journal, lease, key_provider,
                                            heartbeat, fault_hook)
                result["items"].append({"entry_id": entry["entry_id"], "state": state})
        _report_cleanup_progress(progress, result, total)
        # Never put cancellation between DELETE and its direct absence check,
        # or before the unknown/deleted result reaches the signed journal.
        if _cleanup_checkpoint(result, entries):
            return result
    result["state"] = "completed" if all(row["state"] in {"deleted", "already_deleted", "already_absent"} for row in result["items"]) else "review_required"
    result["ok"] = result["state"] == "completed"
    return result


CLEANUP_FENCE_CHUNK = 16


def _cancel_requested() -> bool:
    from .operation_cancellation import checkpoint, OperationCancelled
    try:
        checkpoint()
    except OperationCancelled:
        return True
    return False


def _report_cleanup_progress(progress, result, total):
    """v0.4.62 (letter 181 B): counts, not only a stage, for the remote cleanup."""
    if progress is None:
        return
    done = sum(row["state"] in {"deleted", "already_deleted", "already_absent"} for row in result["items"])
    held = len(result["items"]) - done
    try:
        progress("object-storage-cleanup-keys", "progress", done + held, total)
    except Exception:
        pass


def _dispose_fenced_key(root, transport, entry, relative, journal, lease, key_provider, heartbeat, fault_hook):
    """One fenced key: proof, delete intent, DELETE, direct absence check, final journal."""
    fault_hook("pending_published", entry["entry_id"])
    lease.verify_held()
    # Resume after an unknown DELETE by confirming absence, never by
    # blindly repeating a destructive request against a possibly new key.
    if journal["delete_intent_recorded"] and _absent(transport, entry["remote_key"]):
        state = "deleted"
    else:
        state, etag = _proof(transport, entry)
        if state == "verified":
            conditional = getattr(transport, "conditional_delete_supported", False) is True
            if conditional and etag is None:
                state = "validator_required"
            else:
                # The explicit exclusive-management contract is mandatory
                # even for a provider adapter with conditional DELETE.
                lease.verify_held()
                journal.update(delete_intent_recorded=True, etag=etag)
                with exact_operation_writer_lock(root):
                    _save_signed(root, relative, journal, key_provider)
                fault_hook("delete_intent_recorded", entry["entry_id"])
                heartbeat()
                try:
                    deletion = transport.delete_exact(key=entry["remote_key"], etag=etag if conditional else None)
                except Exception:
                    deletion = {"state": "unknown"}
                fault_hook("delete_returned", entry["entry_id"])
                state = "deleted" if _absent(transport, entry["remote_key"]) else (
                    "delete_rejected" if deletion.get("state") == "rejected" else "outcome_unknown")
        elif state == "absent":
            state = "already_absent"
    with exact_operation_writer_lock(root):
        lease.verify_held()
        journal["state"] = "deleted" if state in {"deleted", "already_absent"} else (
            "outcome_unknown" if journal["delete_intent_recorded"] else "preserved")
        journal["result_code"] = state
        _save_signed(root, relative, journal, key_provider)
    fault_hook("receipt_published", entry["entry_id"])
    return state


def _inventory_request(root, request_path):
    request, sha = _private_read(root, request_path)
    if request.get("schema") != "wom-kit/remote-disposal-inventory-request/v1":
        raise _fail()
    _store(request.get("store_ref"))
    _binding(request.get("remote_binding"))
    include_content_samples = request.get("include_content_samples", False)
    if type(include_content_samples) is not bool:
        raise _fail("object_storage_cleanup_inventory_samples_invalid")
    keys = request.get("keys")
    prefix = request.get("prefix")
    if (keys is None) == (prefix is None):
        raise _fail("object_storage_cleanup_inventory_selection_required")
    if keys is not None:
        if (not isinstance(keys, list) or not keys or len(keys) > MAX_ENTRIES
                or any(not isinstance(key, str) for key in keys) or len(set(keys)) != len(keys)):
            raise _fail()
        for key in keys:
            _key(key)
        if include_content_samples and len(keys) > MAX_CONTENT_SAMPLE_ENTRIES:
            raise _fail("object_storage_cleanup_inventory_sample_limit")
    elif not isinstance(prefix, str) or not prefix or len(prefix.encode("utf-8")) > 1024:
        raise _fail("object_storage_cleanup_inventory_prefix_required")
    return request, _digest({"request_sha256": sha, "archive_identity_sha256": _archive_identity(root), "effect": "inventory_full_get"})


def plan_inventory(archive_root, *, request_path):
    root = _root(archive_root)
    request, digest = _inventory_request(root, request_path)
    return {"schema": "wom-kit/remote-disposal-inventory-plan/v1", "ok": True, "blockers": [], "plan_sha256": digest, "state": "ready",
            "selection_kind": "exact_keys" if request.get("keys") is not None else "explicit_prefix",
            "whole_get_required": True, "content_samples_private": request.get("include_content_samples", False),
            "remote_write": False, "private_values_echoed": False}


def execute_inventory_approved(archive_root, *, request_path, expected_plan_sha256, reviewed_by,
                               exact_human_approval_claim, expected_exact_approval_plan_sha256,
                               expected_exact_approval_target_binding_sha256, transport_factory,
                               key_provider=None, heartbeat=lambda: None):
    root = _root(archive_root)
    _authorize(root, operation="object_storage_remote_cleanup", reviewed_by=reviewed_by,
               exact_human_approval_claim=exact_human_approval_claim, expected_plan_sha256=expected_plan_sha256,
               expected_exact_approval_plan_sha256=expected_exact_approval_plan_sha256,
               expected_exact_approval_target_binding_sha256=expected_exact_approval_target_binding_sha256)
    request, digest = _inventory_request(root, request_path)
    if digest != expected_plan_sha256:
        raise _fail("object_storage_cleanup_plan_changed")
    transport = _adapt(transport_factory())
    if transport.preservation_binding() != request["remote_binding"]:
        raise _fail("object_storage_cleanup_remote_binding_changed")
    def stopped(inspected):
        from .operation_cancellation import checkpoint, OperationCancelled
        try:
            checkpoint()
        except OperationCancelled:
            return {"schema": "wom-kit/remote-disposal-inventory-result/v1", "ok": False,
                "state": "cancelled_at_checkpoint", "cause_code": "operation_cancelled_at_checkpoint",
                "blockers": ["operation_cancelled_at_checkpoint"], "cancel_requested": True,
                "cancel_acknowledged": True, "provider_request_in_flight": False,
                "inspected_entry_count": inspected, "inventory_created": False, "remote_write": False,
                "private_values_echoed": False}
        return None
    keys = request.get("keys")
    if keys is None:
        keys, token, seen, seen_keys = [], None, set(), set()
        while True:
            cancellation = stopped(0)
            if cancellation is not None:
                return cancellation
            heartbeat()
            page = transport.list_page(prefix=request["prefix"], continuation_token=token)
            for key in page["keys"]:
                _key(key)
                if not key.startswith(request["prefix"]) or key in seen_keys:
                    raise _fail("object_storage_cleanup_inventory_changed")
                keys.append(key)
                seen_keys.add(key)
            if len(keys) > MAX_ENTRIES:
                raise _fail("object_storage_cleanup_inventory_limit")
            if request.get("include_content_samples") and len(keys) > MAX_CONTENT_SAMPLE_ENTRIES:
                raise _fail("object_storage_cleanup_inventory_sample_limit")
            token = page.get("continuation_token")
            if token is None:
                break
            if not isinstance(token, str) or not token or token in seen:
                raise _fail("object_storage_cleanup_inventory_incomplete")
            seen.add(token)
    rows = []
    for key in sorted(keys):
        cancellation = stopped(len(rows))
        if cancellation is not None:
            return cancellation
        heartbeat()
        proof = (transport.inspect_object(key=key) if request.get("include_content_samples")
                 else transport.head_object(key=key, presence_only=False))
        if (proof.get("presence_state") != "present" or proof.get("present") is not True
                or proof.get("verification_state") != "complete" or type(proof.get("size")) is not int
                or proof["size"] < 0 or not re.fullmatch(r"[0-9a-f]{64}", str(proof.get("checksum_sha256")))):
            raise _fail("object_storage_cleanup_inventory_proof_unavailable")
        row = {"entry_id": entry_id(request["store_ref"], key), "remote_key": key,
                     "object_id": "sha256:" + proof["checksum_sha256"], "size": proof["size"],
                     "etag": strong_etag(proof.get("whole_get_etag"))}
        if request.get("include_content_samples"):
            prefix = proof.get("content_prefix")
            if not isinstance(prefix, bytes) or len(prefix) != min(CONTENT_SAMPLE_BYTES, proof["size"]):
                raise _fail("object_storage_cleanup_inventory_sample_unavailable")
            row["content_prefix_base64"] = base64.b64encode(prefix).decode("ascii")
            row["content_prefix_bytes"] = len(prefix)
            row["content_prefix_complete"] = len(prefix) == proof["size"]
        rows.append(row)
    cancellation = stopped(len(rows))
    if cancellation is not None:
        return cancellation
    document = {"schema": INVENTORY_SCHEMA, "archive_identity_sha256": _archive_identity(root),
                "store_ref": request["store_ref"], "remote_binding": request["remote_binding"],
                "plan_sha256": expected_plan_sha256, "complete": True, "entries": rows}
    relative = ROOT + "/inventories/" + _digest(document)[7:] + ".json"
    with exact_operation_writer_lock(root):
        _save_signed(root, relative, document, key_provider)
    return {"schema": "wom-kit/remote-disposal-inventory-result/v1", "ok": True, "state": "completed", "entry_count": len(rows),
            "inventory_path": relative, "remote_write": False, "private_values_echoed": False}
