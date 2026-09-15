"""Private immutable session facts for a proposed exact Git backup.

This binds supplied historical routing, claim and receipt-producer facts. It
does not read the current actor/registry, authenticate receipt MACs, attest app
identity, or grant approval. The owned-session execution route must
independently verify those facts before fresh work and after native review.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re

from . import work_session_registry as registry
from .exact_operation_manifest import ExactOperationEvidence
from .work_session_binding import WorkSessionBinding


_SCHEMA = "wom-kit/git-backup-session-scope/v1"
_EVIDENCE_SCHEMA = "wom-kit/git-backup-session-scope-evidence/v1"
_SCHEMA_V2 = "wom-kit/git-backup-session-scope/v2"
_EVIDENCE_SCHEMA_V2 = "wom-kit/git-backup-session-scope-evidence/v2"
# v3 additionally binds authenticated whole-document transitions of completed
# session local recoveries. It never reinterprets v1/v2 bytes or validators.
_SCHEMA_V3 = "wom-kit/git-backup-session-scope/v3"
_EVIDENCE_SCHEMA_V3 = "wom-kit/git-backup-session-scope-evidence/v3"
_LEVELS = {_SCHEMA: 1, _SCHEMA_V2: 2, _SCHEMA_V3: 3}
_MAX_BYTES = 512 * 1024
_MAX_V2_BYTES = 16 * 1024 * 1024
_MAX_SELECTION_BYTES = 16 * 1024 * 1024
_MAX_CHANGES = 100_000
# Historical v1 preserves its original 128-proof contract. The v2 data codec
# can bind a complete 1,000-item intake's 1,002 outputs, but does not implement
# authenticated discovery, current-owner admission or a backup producer.
_MAX_PROOFS = 128
_MAX_V2_PROOFS = 8192
_MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
_CHANGE_REF = re.compile(r"change:[0-9]{6}\Z")
_PRODUCER = "authenticated_work_session_completion_receipt"
_INTAKE_PRODUCER = "authenticated_source_intake_batch_output"
_RECORD_PRODUCER = "authenticated_source_intake_record_output"
_INTAKE_KINDS = frozenset({"source_intake_receipt", "prepared_capture_request", "common_completion_receipt"})
_RECORD_KINDS = frozenset({"source_intake_receipt", "common_completion_receipt"})
_DOCUMENT_PRODUCER = "authenticated_local_recovery_document_output"
_DOCUMENT_KINDS = frozenset({"canonical_zettel_document", "common_completion_receipt"})
_KEYS = frozenset({
    "schema", "task_route_ref", "actor_sha256", "registry_preimage_sha256", "claim_ref",
    "work_session_binding", "selection_sha256", "selected_change_count", "excluded_change_count",
    "producer_proofs", "scope_sha256",
})
_PROOF_DIGESTS = ("whole_file_sha256", "execution_sha256", "receipt_sha256", "manifest_sha256",
                  "context_sha256", "registry_generation_sha256")
_PROOF_KEYS = frozenset({"change_ref", "producer", "whole_file_bytes", "original_work_session_binding",
                         *_PROOF_DIGESTS})
_INTAKE_DIGESTS = tuple(name for name in _PROOF_DIGESTS if name != "registry_generation_sha256") + (
    "output_identity_sha256", "intake_scope_sha256")
_INTAKE_KEYS = frozenset({"change_ref", "producer", "whole_file_bytes", "original_work_session_binding",
                         "output_kind", *_INTAKE_DIGESTS})
_DOCUMENT_DIGESTS = ("whole_file_sha256", "execution_sha256", "receipt_sha256", "manifest_sha256",
                     "context_sha256", "recovery_scope_sha256", "output_identity_sha256", "document_path_sha256")
_DOCUMENT_KEYS = frozenset({"change_ref", "producer", "whole_file_bytes", "original_work_session_binding",
                            "output_kind", "head_file_sha256", "head_file_bytes", *_DOCUMENT_DIGESTS})
_ESTABLISHMENT_KEYS = frozenset({"manifest_sha256", "context_sha256", "execution_sha256", "receipt_sha256"})


class GitBackupSessionScopeError(ValueError):
    def __init__(self):
        self.code = "git_backup_session_scope_invalid"
        super().__init__(self.code)


def _canonical(value, *, max_bytes=_MAX_BYTES):
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True,
                     separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(raw) > max_bytes:
        raise GitBackupSessionScopeError()
    return raw


def _sha(value, *, max_bytes=_MAX_BYTES):
    return "sha256:" + hashlib.sha256(_canonical(value, max_bytes=max_bytes)).hexdigest()


def _session_identity(binding):
    return (binding.archive_identity_sha256, binding.client_app_ref,
            binding.workstream_ref, binding.work_session_ref)


def _scope_budget(value):
    return _MAX_V2_BYTES if type(value) is dict and value.get("schema") in (_SCHEMA_V2, _SCHEMA_V3) else _MAX_BYTES


def _sha_text(value):
    if type(value) is not str:
        raise GitBackupSessionScopeError()
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_document_proof(proof):
    return type(proof) is dict and type(proof.get("producer")) is str and proof["producer"] == _DOCUMENT_PRODUCER


def _intake_output_kinds(producer):
    """Closed domain families, never an injected producer implementation."""
    if type(producer) is str:
        if producer == _INTAKE_PRODUCER:
            return _INTAKE_KINDS
        if producer == _RECORD_PRODUCER:
            return _RECORD_KINDS
    return None


def _proof_output_path(proof):
    """Derive one claimed target spelling; this is not producer authentication."""
    if proof["producer"] == _PRODUCER:
        return "receipts/ops/exact-operations/" + proof["execution_sha256"][7:] + ".json"
    if _is_document_proof(proof):
        # A canonical document path is private plan data, not derivable from
        # digests. Callers compare its digest; the producer maps it from the
        # retained original plan.
        if proof["output_kind"] == "common_completion_receipt":
            return "receipts/ops/exact-operations/" + proof["execution_sha256"][7:] + ".json"
        raise GitBackupSessionScopeError()
    kinds = _intake_output_kinds(proof["producer"])
    if kinds is None or type(proof.get("output_kind")) is not str or proof["output_kind"] not in kinds:
        raise GitBackupSessionScopeError()
    if proof["output_kind"] == "common_completion_receipt":
        return "receipts/ops/exact-operations/" + proof["execution_sha256"][7:] + ".json"
    # Reuse the domain's path grammar. A path match remains insufficient: the
    # authenticated producer must prove membership in the ORIGINAL manifest.
    from . import archive_services
    from . import source_intake_batch_exact as intake
    if proof["output_kind"] == "source_intake_receipt":
        return archive_services.source_intake_record_path(proof["output_identity_sha256"])
    return intake.CAPTURE_REQUESTS_ROOT + "/" + proof["output_identity_sha256"][7:] + ".objet-capture-request.json"


def _validate_document(value):
    if (type(value) is not dict or set(value) not in (_KEYS, _KEYS | {"establishment_proof"})
            or value["schema"] not in _LEVELS):
        raise GitBackupSessionScopeError()
    level = _LEVELS[value["schema"]]
    version2 = level >= 2
    if "establishment_proof" in value:
        origin = value["establishment_proof"]
        if (type(origin) is not dict or set(origin) != _ESTABLISHMENT_KEYS
                or any(not registry._is_digest(field) for field in origin.values())):
            raise GitBackupSessionScopeError()
    if (not registry._ref(value["task_route_ref"], "task_route")
            or not registry._ref(value["claim_ref"], "claim")
            or any(not registry._is_digest(value[name]) for name in
                   ("actor_sha256", "registry_preimage_sha256", "selection_sha256", "scope_sha256"))
            or type(value["work_session_binding"]) is not dict):
        raise GitBackupSessionScopeError()
    binding = WorkSessionBinding.from_document(value["work_session_binding"])
    selected, excluded = value["selected_change_count"], value["excluded_change_count"]
    if (type(selected) is not int or type(excluded) is not int or selected < 1 or excluded < 0
            or selected + excluded > _MAX_CHANGES):
        raise GitBackupSessionScopeError()
    proofs = value["producer_proofs"]
    if (type(proofs) is not list or not 1 <= len(proofs) <= (_MAX_V2_PROOFS if version2 else _MAX_PROOFS)
            or not selected <= len(proofs) <= selected + excluded):
        raise GitBackupSessionScopeError()
    refs, intake_count, document_count = [], 0, 0
    for proof in proofs:
        if type(proof) is not dict:
            raise GitBackupSessionScopeError()
        if level >= 3 and _is_document_proof(proof):
            _validate_document_proof(proof, binding)
            refs.append(proof["change_ref"])
            document_count += 1
            continue
        kinds = _intake_output_kinds(proof.get("producer"))
        intake = version2 and kinds is not None
        keys, digests = (_INTAKE_KEYS, _INTAKE_DIGESTS) if intake else (_PROOF_KEYS, _PROOF_DIGESTS)
        if (set(proof) != keys
                or type(proof["change_ref"]) is not str or not _CHANGE_REF.fullmatch(proof["change_ref"])
                or not intake and proof["producer"] != _PRODUCER
                or any(not registry._is_digest(proof[name]) for name in digests)
                or type(proof["whole_file_bytes"]) is not int
                or not 1 <= proof["whole_file_bytes"] <= _MAX_FILE_BYTES
                or type(proof["original_work_session_binding"]) is not dict):
            raise GitBackupSessionScopeError()
        if intake:
            if (type(proof["output_kind"]) is not str or proof["output_kind"] not in kinds
                    or proof["output_kind"] == "common_completion_receipt"
                    and proof["output_identity_sha256"] != proof["execution_sha256"]):
                raise GitBackupSessionScopeError()
            intake_count += 1
        original = WorkSessionBinding.from_document(proof["original_work_session_binding"])
        if original.archive_identity_sha256 != binding.archive_identity_sha256:
            raise GitBackupSessionScopeError()
        refs.append(proof["change_ref"])
    if refs != sorted(set(refs)) or level == 2 and not intake_count or level == 3 and not document_count:
        raise GitBackupSessionScopeError()
    basis = {key: field for key, field in value.items() if key != "scope_sha256"}
    if not hmac.compare_digest(value["scope_sha256"], _sha(basis, max_bytes=_scope_budget(value))):
        raise GitBackupSessionScopeError()
    return value


def _validate_document_proof(proof, binding):
    """Closed whole-document proof shape; digests are data, not ownership."""
    receipt = proof.get("output_kind") == "common_completion_receipt"
    if (set(proof) != _DOCUMENT_KEYS
            or type(proof["change_ref"]) is not str or not _CHANGE_REF.fullmatch(proof["change_ref"])
            or type(proof["output_kind"]) is not str or proof["output_kind"] not in _DOCUMENT_KINDS
            or any(not registry._is_digest(proof[name]) for name in _DOCUMENT_DIGESTS)
            or type(proof["whole_file_bytes"]) is not int
            or not 1 <= proof["whole_file_bytes"] <= _MAX_FILE_BYTES
            or type(proof["original_work_session_binding"]) is not dict):
        raise GitBackupSessionScopeError()
    if receipt:
        if (proof["head_file_sha256"] is not None or proof["head_file_bytes"] is not None
                or proof["output_identity_sha256"] != proof["execution_sha256"]
                or proof["document_path_sha256"] != _sha_text(_proof_output_path(proof))):
            raise GitBackupSessionScopeError()
    elif (not registry._is_digest(proof["head_file_sha256"]) or type(proof["head_file_bytes"]) is not int
            or not 1 <= proof["head_file_bytes"] <= _MAX_FILE_BYTES):
        raise GitBackupSessionScopeError()
    original = WorkSessionBinding.from_document(proof["original_work_session_binding"])
    if original.archive_identity_sha256 != binding.archive_identity_sha256:
        raise GitBackupSessionScopeError()


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise GitBackupSessionScopeError()
            result[key] = value
        return result

    try:
        if type(raw) is not bytes or not 2 <= len(raw) <= _MAX_V2_BYTES:
            raise GitBackupSessionScopeError()
        value = json.loads(raw.decode("ascii"), object_pairs_hook=pairs)
        _validate_document(value)
        if _canonical(value, max_bytes=_scope_budget(value)) != raw:
            raise GitBackupSessionScopeError()
        return value
    except Exception:
        pass
    # Retain neither private input nor parser/OS/callback exception chains.
    raise GitBackupSessionScopeError()


@dataclass(frozen=True, slots=True, repr=False)
class _GitBackupSessionScope:
    _raw: bytes

    def __post_init__(self):
        _decode(self._raw)

    def __repr__(self):
        return "_GitBackupSessionScope(<private binding; not authority>)"

    @classmethod
    def build(cls, *, task_route_ref, actor_sha256, registry_preimage_sha256, claim_ref,
              work_session_binding, selection_sha256, selected_change_count,
              excluded_change_count, producer_proofs, establishment_proof=None):
        try:
            if type(work_session_binding) is not WorkSessionBinding or type(producer_proofs) is not list:
                raise GitBackupSessionScopeError()
            if any(_is_document_proof(proof) for proof in producer_proofs):
                schema = _SCHEMA_V3
            elif any(type(proof) is dict and _intake_output_kinds(proof.get("producer")) is not None
                     for proof in producer_proofs):
                schema = _SCHEMA_V2
            else:
                schema = _SCHEMA
            basis = {
                "schema": schema,
                "task_route_ref": task_route_ref, "actor_sha256": actor_sha256,
                "registry_preimage_sha256": registry_preimage_sha256, "claim_ref": claim_ref,
                "work_session_binding": work_session_binding.document(), "selection_sha256": selection_sha256,
                "selected_change_count": selected_change_count, "excluded_change_count": excluded_change_count,
                "producer_proofs": producer_proofs,
            }
            if establishment_proof is not None:
                basis["establishment_proof"] = establishment_proof
            return cls.from_document({**basis, "scope_sha256": _sha(basis, max_bytes=_scope_budget(basis))})
        except Exception:
            pass
        raise GitBackupSessionScopeError()

    @classmethod
    def from_document(cls, value):
        try:
            _validate_document(value)
            return cls(_canonical(value, max_bytes=_scope_budget(value)))
        except Exception:
            pass
        raise GitBackupSessionScopeError()

    def document(self):
        return _decode(self._raw)

    @property
    def scope_sha256(self):
        return self.document()["scope_sha256"]

    def operation_evidence(self):
        value = self.document()
        return ExactOperationEvidence(
            schema={1: _EVIDENCE_SCHEMA, 2: _EVIDENCE_SCHEMA_V2, 3: _EVIDENCE_SCHEMA_V3}[_LEVELS[value["schema"]]],
            counts=tuple(sorted({"selected_change_count": value["selected_change_count"],
                                 "excluded_change_count": value["excluded_change_count"],
                                 "producer_proof_count": len(value["producer_proofs"])}.items())),
            digests=tuple(sorted({"session_scope_sha256": value["scope_sha256"],
                                  "selection_sha256": value["selection_sha256"],
                                  "producer_proofs_sha256": _sha(value["producer_proofs"], max_bytes=_scope_budget(value))}.items())),
        )

    def validate_selection(self, binding, selection_document):
        """Check the bound partition and proof identities, not current authority."""
        try:
            value = self.document()
            if (type(binding) is not WorkSessionBinding or binding.document() != value["work_session_binding"]
                    or _sha(selection_document, max_bytes=_MAX_SELECTION_BYTES) != value["selection_sha256"]):
                raise GitBackupSessionScopeError()
            selected = {ref for group in selection_document["selected_groups"] for ref in group["change_refs"]}
            excluded = {row["change_ref"]: row for row in selection_document["excluded_changes"]}
            proofs = {row["change_ref"]: row for row in value["producer_proofs"]}
            if (len(selected) != value["selected_change_count"] or len(excluded) != value["excluded_change_count"]
                    or not selected <= set(proofs) or not set(proofs) <= selected | set(excluded)):
                raise GitBackupSessionScopeError()
            for ref, proof in proofs.items():
                original = WorkSessionBinding.from_document(proof["original_work_session_binding"])
                same_session = _session_identity(original) == _session_identity(binding)
                if ((ref in selected) != same_session
                        or ref in excluded and excluded[ref]["scope"] != "other_session"):
                    raise GitBackupSessionScopeError()
            if any(row["scope"] == "other_session" and ref not in proofs for ref, row in excluded.items()):
                raise GitBackupSessionScopeError()
            return
        except Exception:
            pass
        raise GitBackupSessionScopeError()

    def validate_sources(self, private_changes):
        """Match exact whole-new output paths/bytes; MAC and membership are separate."""
        try:
            rows = {row["public_observation"]["change_ref"]: row for row in private_changes}
            if len(rows) != len(private_changes):
                raise GitBackupSessionScopeError()
            for proof in self.document()["producer_proofs"]:
                row = rows[proof["change_ref"]]
                public = row["public_observation"]
                worktree, index = public["worktree"], public["index"]
                if _is_document_proof(proof):
                    if _sha_text(row["path"]) != proof["document_path_sha256"]:
                        raise GitBackupSessionScopeError()
                    if proof["output_kind"] == "canonical_zettel_document":
                        if row["original_path"] is not None or not _modified_document_matches(public, proof):
                            raise GitBackupSessionScopeError()
                        continue
                if (row["original_path"] is not None
                        or row["path"] != _proof_output_path(proof)
                        or public["operation"] not in {"added", "added_untracked"}
                        or public["head"]["state"] != "absent"
                        or worktree["state"] != "regular_file"
                        or worktree["sha256"] != proof["whole_file_sha256"]
                        or type(worktree["bytes"]) is not int
                        or worktree["bytes"] != proof["whole_file_bytes"]
                        or not (index["state"] == "absent" or (
                            index["state"] == "blob" and index["mode"] == "regular_file"
                            and type(index["bytes"]) is int
                            and index["sha256"] == worktree["sha256"] and index["bytes"] == worktree["bytes"]))):
                    raise GitBackupSessionScopeError()
            return
        except Exception:
            pass
        raise GitBackupSessionScopeError()

def _modified_document_matches(public, proof):
    """Whole modified-file predicate: HEAD is the approved preimage, the worktree
    the approved postimage, and the index equals exactly one of them. Matching
    bytes are still not ownership until the producer is authenticated."""
    head, index, worktree = public["head"], public["index"], public["worktree"]
    if (public["operation"] != "modified" or head["state"] != "blob" or head["mode"] != "regular_file"
            or type(head["bytes"]) is not int or head["sha256"] != proof["head_file_sha256"]
            or head["bytes"] != proof["head_file_bytes"]
            or worktree["state"] != "regular_file" or type(worktree["bytes"]) is not int
            or worktree["sha256"] != proof["whole_file_sha256"] or worktree["bytes"] != proof["whole_file_bytes"]
            or index["state"] != "blob" or index["mode"] != "regular_file" or type(index["bytes"]) is not int):
        return False
    return ((index["sha256"], index["bytes"]) == (head["sha256"], head["bytes"])
            or (index["sha256"], index["bytes"]) == (worktree["sha256"], worktree["bytes"]))
