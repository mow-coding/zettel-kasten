"""Open one verified remote Objet through an ephemeral SigV4 GET URL.

The signed URL is a bearer credential: it goes directly to the browser adapter,
never to stdout, receipts, exception text or a durable file. The existing exact
approval/session permission gate controls this egress. Signing is local; the
fresh whole-byte proof uses the existing authenticated S3 data plane.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re
import webbrowser

from . import archive_services as services
from . import object_storage_cleanup as cleanup
from .exact_operation_manifest import exact_operation_writer_lock
from .operation_target_leases import TargetLeases

PLAN_SCHEMA = "wom-kit/object-storage-open-plan/v1"
RESULT_SCHEMA = "wom-kit/object-storage-open-result/v1"
DEFAULT_TTL_SECONDS = 900


class ObjectStorageOpenError(services.ArchiveServiceError):
    def __init__(self, code="object_storage_open_invalid"):
        self.code = code if re.fullmatch(r"[a-z_]{1,96}", str(code)) else "object_storage_open_invalid"
        super().__init__(self.code)


def _prepare(root, *, object_id, store_ref, ttl_seconds, provider_kind, remote_binding):
    if (not isinstance(object_id, str) or not cleanup.OID.fullmatch(object_id)
            or type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 86400
            or provider_kind not in {"cloudflare-r2", "generic-s3"}):
        raise ObjectStorageOpenError()
    cleanup._store(store_ref)
    cleanup._binding(remote_binding)
    path = services.archive_internal_path(root, "objects/manifests/files.jsonl")
    try:
        if path.stat().st_size > cleanup.MAX_DOCUMENT:
            raise ObjectStorageOpenError()
        raw = path.read_bytes()
        rows = [cleanup._json(line) for line in raw.splitlines() if line.strip()]
    except Exception:
        raise ObjectStorageOpenError("object_storage_open_manifest_unreadable") from None
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            raise ObjectStorageOpenError("object_storage_open_manifest_invalid")
        if row.get("object_id") != object_id:
            continue
        for location in row.get("locations", []) or []:
            if (isinstance(location, dict) and location.get("provider") == "object_storage"
                    and location.get("store_ref") == store_ref and location.get("provider_kind") == provider_kind
                    and location.get("availability") == "wom_uploaded"
                    and location.get("provider_confirmation_by_wom_kit") is True
                    and location.get("remote_key_verified") is True):
                key = cleanup._key(location.get("remote_key"))
                size = row.get("size_bytes")
                if type(size) is not int or size < 0:
                    raise ObjectStorageOpenError("object_storage_open_identity_missing")
                candidate = {"remote_key": key, "object_id": object_id, "size": size}
                if candidate not in candidates:
                    candidates.append(candidate)
    if len(candidates) != 1:
        raise ObjectStorageOpenError("object_storage_open_remote_location_ambiguous" if candidates else "object_storage_open_remote_location_missing")
    target = candidates[0]
    cleanup.assert_remote_available(root, store_ref=store_ref, remote_key=target["remote_key"], object_id=object_id)
    from .object_storage_setup_registration import validate_object_storage_setup_evidence
    setup = validate_object_storage_setup_evidence(root, provider_kind=provider_kind, store_ref=store_ref)
    # Setup registration binds the selected store. Live identity is checked by
    # the credential resolver/transport and the full GET, not a declared URL.
    binding = {"schema": PLAN_SCHEMA, "archive_identity_sha256": cleanup._archive_identity(root),
               "manifest_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(), "target": target,
               "provider_kind": provider_kind, "store_ref": store_ref, "ttl_seconds": ttl_seconds, "remote_binding": remote_binding,
               "setup_evidence_sha256": cleanup._digest(setup.public_document()), "delivery": "browser"}
    return target, binding


def plan_open(archive_root, *, object_id, store_ref, remote_binding, ttl_seconds=DEFAULT_TTL_SECONDS, provider_kind="cloudflare-r2"):
    root = cleanup._root(archive_root)
    target, binding = _prepare(root, object_id=object_id, store_ref=store_ref, ttl_seconds=ttl_seconds, provider_kind=provider_kind, remote_binding=remote_binding)
    return {"schema": PLAN_SCHEMA, "ok": True, "blockers": [], "state": "ready", "plan_sha256": cleanup._digest(binding),
            "ttl_seconds": ttl_seconds, "delivery": "browser", "whole_get_required": True,
            "private_values_echoed": False, "signed_url_returned": False}


def presign_get(transport, *, key, ttl_seconds, now=None):
    """SigV4 query authentication using the existing transport's signing helpers.

    Only this local adapter accesses signing material. It accepts the already
    resolved transport, never a path/token reference or a provider control API.
    """
    if type(ttl_seconds) is not int or not 60 <= ttl_seconds <= 86400:
        raise ObjectStorageOpenError("object_storage_open_ttl_invalid")
    cleanup._key(key)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ObjectStorageOpenError("object_storage_open_time_invalid")
    now = now.astimezone(timezone.utc)
    try:
        remote = cleanup._binding(transport.preservation_binding())
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        scope = services._sigv4_scope(amz_date, remote["region"], remote["service"])
        query = {"X-Amz-Algorithm": "AWS4-HMAC-SHA256", "X-Amz-Credential": transport._access_key_id + "/" + scope,
                 "X-Amz-Date": amz_date, "X-Amz-Expires": str(ttl_seconds), "X-Amz-SignedHeaders": "host"}
        uri = services._sigv4_canonical_uri(remote["bucket"] + "/" + key)
        block, signed = services._sigv4_canonical_headers({"host": remote["endpoint_host"]})
        canonical = services._sigv4_canonical_request("GET", uri, services._sigv4_query_encode(query), block, signed, services.SIGV4_UNSIGNED_PAYLOAD)
        string_to_sign = services._sigv4_string_to_sign(amz_date, scope, canonical)
        signing_key = services._sigv4_signing_key(transport._secret_access_key, amz_date[:8], remote["region"], remote["service"])
        query["X-Amz-Signature"] = services._sigv4_signature(signing_key, string_to_sign)
        return "https://" + remote["endpoint_host"] + uri + "?" + services._sigv4_query_encode(query)
    except Exception:
        raise ObjectStorageOpenError("object_storage_open_signing_failed") from None


def execute_open_approved(archive_root, *, object_id, store_ref, remote_binding, expected_plan_sha256, reviewed_by,
                          exact_human_approval_claim, expected_exact_approval_plan_sha256,
                          expected_exact_approval_target_binding_sha256, transport_factory,
                          ttl_seconds=DEFAULT_TTL_SECONDS, provider_kind="cloudflare-r2",
                          deliver=None, signer=None, key_provider=None, now=None, heartbeat=lambda: None):
    root = cleanup._root(archive_root)
    cleanup._authorize(root, operation="object_storage_open", reviewed_by=reviewed_by,
                       exact_human_approval_claim=exact_human_approval_claim, expected_plan_sha256=expected_plan_sha256,
                       expected_exact_approval_plan_sha256=expected_exact_approval_plan_sha256,
                       expected_exact_approval_target_binding_sha256=expected_exact_approval_target_binding_sha256)
    target, binding = _prepare(root, object_id=object_id, store_ref=store_ref, ttl_seconds=ttl_seconds, provider_kind=provider_kind, remote_binding=remote_binding)
    if cleanup._digest(binding) != expected_plan_sha256:
        raise ObjectStorageOpenError("object_storage_open_plan_changed")
    with TargetLeases(root, [("object", object_id)], heartbeat=heartbeat):
        with exact_operation_writer_lock(root):
            target, fresh = _prepare(root, object_id=object_id, store_ref=store_ref, ttl_seconds=ttl_seconds, provider_kind=provider_kind, remote_binding=remote_binding)
            if cleanup._digest(fresh) != expected_plan_sha256:
                raise ObjectStorageOpenError("object_storage_open_plan_changed")
        transport = transport_factory()
        if transport.preservation_binding() != remote_binding:
            raise ObjectStorageOpenError("object_storage_open_remote_binding_changed")
        status, _etag = cleanup._proof(transport, target)
        if status != "verified":
            return {"schema": RESULT_SCHEMA, "ok": False, "state": "review_required", "reason_codes": [status],
                    "private_values_echoed": False, "signed_url_returned": False}
        heartbeat()
        signing_time = now or datetime.now(timezone.utc)
        if signing_time.tzinfo is None:
            raise ObjectStorageOpenError("object_storage_open_time_invalid")
        url = (signer or presign_get)(transport, key=target["remote_key"], ttl_seconds=ttl_seconds, now=signing_time)
        # No arbitrary URL scheme enters the browser even when an adapter is injected.
        from urllib.parse import urlsplit
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc != transport.preservation_binding()["endpoint_host"]:
            raise ObjectStorageOpenError("object_storage_open_signing_failed")
        try:
            delivered = bool((deliver or webbrowser.open)(url))
        except Exception:
            delivered = False
        finally:
            del url
        expires = (signing_time + timedelta(seconds=ttl_seconds)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        receipt = {"schema": "wom-kit/object-storage-open-receipt/v1", "plan_sha256": expected_plan_sha256,
                   "object_id": object_id, "opened": delivered, "expires_at": expires, "ttl_seconds": ttl_seconds,
                   "signed_url_retained": False, "remote_bytes_verified": True}
        relative = "profiles/local/remote-open/" + cleanup._digest(receipt)[7:] + ".json"
        with exact_operation_writer_lock(root):
            cleanup._save_signed(root, relative, receipt, key_provider)
        return {"schema": RESULT_SCHEMA, "ok": delivered, "state": "browser_opened" if delivered else "browser_delivery_failed",
                "expires_at": expires, "ttl_seconds": ttl_seconds, "remote_bytes_verified": True,
                "signed_url_returned": False, "private_values_echoed": False}
