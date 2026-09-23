"""Whole-byte preservation proofs, bound to the response that supplied the bytes.

An ETag is a validator, never a content checksum. Persisted proofs are MAC-bound
with the existing archive key and are usable only after a conditional HEAD.
Missing/legacy/weak proofs require a streamed GET; no local object is restored.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path

DOMAIN = b"wom-kit/remote-preservation-proof/v1\0"
SCHEMA = "wom-kit/remote-preservation-proof/v1"
ROOT = "receipts/providers/remote-byte-proofs"


def strong_etag(value):
    if isinstance(value, str) and re.fullmatch(r'"[\x21\x23-\x7e]+"', value):
        return value
    return None


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


class ProofStore:
    """Private, immutable evidence. A lost key merely forces fresh byte proof."""
    def __init__(self, root, key_provider=None):
        self.root = Path(root)
        self.key_provider = key_provider

    def _mac(self, document):
        from .exact_human_approval_workflow import _production_key_provider
        provider = self.key_provider or _production_key_provider()
        return provider.use_key(self.root,
            lambda key: hmac.new(bytes(key), DOMAIN + _canonical(document), hashlib.sha256).hexdigest(),
            create_if_missing=False)

    def _directory(self, binding):
        return ROOT + "/" + hashlib.sha256(_canonical(binding)).hexdigest()

    def load(self, binding):
        from . import archive_services as services
        directory = services.archive_internal_path(self.root, self._directory(binding))
        if not directory.exists():
            return None
        candidates = services.safe_archive_glob(directory, "*.json", self.root, recursive=False)
        for path in sorted(candidates, reverse=True):
            try:
                if path.is_symlink() or path.stat().st_size > 16384:
                    continue
                signed = json.loads(path.read_bytes())
                document, mac = signed["proof"], signed["mac"]
                if (document.get("schema") == SCHEMA and document.get("binding") == binding
                        and strong_etag(document.get("etag")) and document.get("execution_sha256")
                        and hmac.compare_digest(mac, self._mac(document))):
                    return document
            except Exception:
                continue
        return None

    def save(self, proof):
        from .object_storage_offload import _create_or_match_document
        signed = {"proof": proof, "mac": self._mac(proof)}
        raw = _canonical(signed) + b"\n"
        name = hashlib.sha256(raw).hexdigest() + ".json"
        _create_or_match_document(self.root, self._directory(proof["binding"]) + "/" + name,
            raw, failure_code="object_storage_offload_receipt_conflict")


class ExecutionTransport:
    """Explicit single-run scope shared by composed official child writers."""
    def __init__(self, transport):
        import uuid
        self.transport = transport
        self.preservation_execution_token = "sha256:" + hashlib.sha256(uuid.uuid4().bytes).hexdigest()
        self.preservation_execution_proofs = {}
    def __getattr__(self, name):
        return getattr(self.transport, name)


class PreservationVerifier:
    """One execution's cache; lifetime must not cross an execution boundary."""
    def __init__(self, transport, *, store_ref, execution_sha256, proof_store=None):
        self.transport = transport
        self.store_ref = store_ref
        self.execution_sha256 = getattr(transport, "preservation_execution_token", execution_sha256)
        self.proof_store = proof_store
        shared = getattr(transport, "preservation_execution_proofs", None)
        self.proofs = shared if isinstance(shared, dict) else {}
        self.get_count = 0
        self.conditional_head_count = 0

    def verify(self, *, key, object_id, size, heartbeat=lambda: None):
        from .object_storage_preservation import _call_with_heartbeat
        if (not isinstance(object_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", object_id)
                or type(size) is not int or size < 0):
            return {"state": "verification_unavailable"}
        identity = getattr(self.transport, "preservation_binding", lambda: None)()
        binding = {"remote": identity, "store_ref": self.store_ref, "key": key,
                   "object_id": object_id, "size": size}
        token = hashlib.sha256(_canonical(binding)).hexdigest()
        # Revalidate against remote mutation without downloading the bytes again.
        cached = self.proofs.get(token)
        if cached is None and self.proof_store is not None and identity:
            cached = self.proof_store.load(binding)
        conditional = getattr(self.transport, "head_object_if_match", None)
        if cached is not None and strong_etag(cached.get("etag")) and conditional:
            self.conditional_head_count += 1
            try:
                check = _call_with_heartbeat(lambda: conditional(key=key, etag=cached["etag"]), heartbeat=heartbeat)
            except Exception:
                return {"state": "verification_unavailable"}
            if check.get("state") == "unchanged" and check.get("size") == size and check.get("etag") == cached["etag"]:
                self.proofs[token] = cached
                return {"state": "verified_match", "method": "conditional_head", "proof": cached}
            if check.get("state") != "changed":
                return {"state": "verification_unavailable"}
        elif cached is not None and cached.get("execution_sha256") == self.execution_sha256:
            # No validator available: reuse only in this explicit execution.
            return {"state": "verified_match", "method": "same_execution", "proof": cached}
        self.get_count += 1
        try:
            result = _call_with_heartbeat(lambda: self.transport.head_object(key=key, presence_only=False), heartbeat=heartbeat)
        except Exception:
            return {"state": "verification_unavailable"}
        return self.accept(key=key, object_id=object_id, size=size, result=result)

    def accept(self, *, key, object_id, size, result):
        """Record a just-completed whole GET from an existing upload writer."""
        identity = getattr(self.transport, "preservation_binding", lambda: None)()
        binding = {"remote": identity, "store_ref": self.store_ref, "key": key,
                   "object_id": object_id, "size": size}
        token = hashlib.sha256(_canonical(binding)).hexdigest()
        if not isinstance(result, dict):
            return {"state": "verification_unavailable"}
        if result.get("presence_state") == "absent" and result.get("present") is False:
            return {"state": "absent"}
        if result.get("presence_state") != "present" or result.get("present") is not True:
            return {"state": "verification_unavailable"}
        if type(result.get("size")) is not int or result.get("verification_state") not in (None, "complete"):
            return {"state": "verification_unavailable"}
        if result["size"] != size:
            return {"state": "size_mismatch"}
        checksum = result.get("checksum_sha256")
        if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
            return {"state": "verification_unavailable"}
        if not hmac.compare_digest(checksum, object_id[7:]):
            return {"state": "checksum_mismatch"}
        proof = {"schema": SCHEMA, "binding": binding, "sha256": checksum, "size": size,
                 "etag": strong_etag(result.get("whole_get_etag")), "execution_sha256": self.execution_sha256}
        self.proofs[token] = proof
        if self.proof_store is not None and identity and proof["etag"]:
            try:
                self.proof_store.save(proof)
            except Exception:
                # Failure to retain an optimization cannot invent cached proof.
                # The just-completed full GET is still valid for this execution.
                pass
        return {"state": "verified_match", "method": "whole_get", "proof": proof}


class RecordingTransport:
    """Retain the upload writer's own whole-GET evidence without a second GET."""
    def __init__(self, transport, verifier, expected):
        self.transport, self.verifier, self.expected = transport, verifier, expected
    def __getattr__(self, name):
        return getattr(self.transport, name)
    def head_object(self, *, key, presence_only=False):
        result = self.transport.head_object(key=key, presence_only=presence_only)
        if not presence_only and key in self.expected:
            oid, size = self.expected[key]
            self.verifier.accept(key=key, object_id=oid, size=size, result=result)
        return result


class PreservationQueryAdapter:
    def __init__(self, verifier):
        self.verifier = verifier
    def query(self, *, remote_key, expected_size, expected_sha256, heartbeat):
        from .object_storage_preservation import ObjectStorageRemoteQueryResult
        state = self.verifier.verify(key=remote_key, object_id="sha256:" + expected_sha256,
            size=expected_size, heartbeat=heartbeat)["state"]
        return ObjectStorageRemoteQueryResult(state,
            state not in {"absent", "verification_unavailable"},
            state in {"checksum_mismatch", "verified_match"}, state == "verified_match")
