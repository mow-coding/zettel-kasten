"""Private whole-document classification for an exact session Git backup.

The supplied Git snapshot is DATA. This adapter authenticates completed
session local recoveries whose retained control recorded whole canonical
document preimages and postimages, then matches Git's own observations:
HEAD must hold the approved preimage, the worktree the approved postimage,
and the index one of the two. It performs no Git/network observation, actor
mutation, approval or backup, and never attributes a pre-existing uncommitted
body edit or an overlapping second approval to a title operation.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from . import exact_human_approval as approval
from . import git_backup_session_scope as scope_codec
from . import git_backup_writer as writer
from . import local_recovery_completion as completion
from . import local_recovery_execution as recovery
from . import local_recovery_session as sessions
from . import work_session_git_provenance as snapshots
from . import work_session_registry as registry
from . import work_session_source_intake_bundle as bundle
from .work_session_binding import WorkSessionBinding


_MAX_PROOFS = 8192
_MAX_PROOF_BYTES = 16 * 1024 * 1024
_MAX_RESULT_BYTES = 32 * 1024 * 1024
_PRODUCER = scope_codec._DOCUMENT_PRODUCER
_PROOF_FACTS = frozenset({"manifest_sha256", "context_sha256", "execution_sha256",
                          "common_final_receipt_sha256", "recovery_scope_sha256", "work_session_binding"})
_MAP_KEYS = frozenset({"output_kind", "output_identity_sha256", "head_sha256", "head_bytes", "sha256", "size_bytes"})
_ERRORS = frozenset({
    "work_session_document_git_invalid", "work_session_document_git_lock_required",
    "work_session_document_git_limit", "work_session_document_git_proof_unavailable",
})


class WorkSessionDocumentGitProvenanceError(RuntimeError):
    def __init__(self, code="work_session_document_git_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_document_git_invalid"
        super().__init__(self.code)


def _safe_call(call):
    code = "work_session_document_git_invalid"
    try:
        return call()
    except WorkSessionDocumentGitProvenanceError as error:
        code = error.code
    except bundle.WorkSessionIntakeBundleError as error:
        if error.code == "work_session_intake_bundle_lock_required":
            code = "work_session_document_git_lock_required"
    except Exception:
        pass
    raise WorkSessionDocumentGitProvenanceError(code)


def _reader_api(mode):
    """Fixed concrete APIs/types; no caller-supplied producer implementation."""
    if mode == "key":
        return completion._read_completed_local_recovery_held, completion._VerifiedLocalRecoveryCompletion
    if mode == "claim":
        return completion._verify_completed_local_recovery_with_claim_held, completion._VerifiedLocalRecoveryCompletion
    if mode == "image":
        return completion._read_local_recovery_completion_image_held, completion._LocalRecoveryCompletionImage
    raise WorkSessionDocumentGitProvenanceError()


def _canonical(value, maximum=_MAX_RESULT_BYTES):
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(raw) > maximum:
        raise WorkSessionDocumentGitProvenanceError("work_session_document_git_limit")
    return raw


def _digest(value):
    return type(value) is str and registry._is_digest(value)


@dataclass(frozen=True, slots=True, repr=False)
class _DocumentSelection:
    _raw: bytes

    def __repr__(self):
        return "<private document selection; not Git or write authority>"

    def _private_document(self):
        return json.loads(self._raw)

    def public_summary(self):
        data = self._private_document()
        partition = data["selection"]
        selected_refs = {ref for group in partition["selected_groups"] for ref in group["change_refs"]}
        proofs = data["proofs"]
        documents = [proof for proof in proofs if proof["output_kind"] == completion.DOCUMENT_OUTPUT_KIND]
        excluded = partition["excluded_changes"]
        return {"state": "document_selection_classified", "selected_output_count": len(selected_refs),
                "selected_document_count": sum(proof["change_ref"] in selected_refs for proof in documents),
                "other_session_output_count": sum(row["scope"] == "other_session" for row in excluded),
                "ownership_unverified_count": sum(row["scope"] == "unknown" for row in excluded),
                "control_inventory_state": data["control_inventory_state"],
                "document_control_count": data["document_control_count"],
                "authenticated_recovery_count": data["authenticated_recovery_count"],
                "unverified_document_control_count": data["unverified_document_control_count"],
                "overlapping_document_count": data["overlapping_document_count"],
                "snapshot_partition_complete": True, "git_snapshot_revalidated": False,
                "current_claim_authority_evaluated": False, "whole_document_ownership_verified": False,
                "backup_performed": False, "private_values_echoed": False, "paths_echoed": False}


def _rows(private_changes):
    if type(private_changes) is not list:
        raise WorkSessionDocumentGitProvenanceError()
    copied = json.loads(_canonical(private_changes, writer.GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES))
    if any(type(row) is not dict or type(row.get("path")) is not str
           or type(row.get("public_observation")) is not dict for row in copied):
        raise WorkSessionDocumentGitProvenanceError()
    refs = [row["public_observation"].get("change_ref") for row in copied]
    if (any(type(ref) is not str or scope_codec._CHANGE_REF.fullmatch(ref) is None for ref in refs)
            or len(set(refs)) != len(refs)):
        raise WorkSessionDocumentGitProvenanceError()
    return copied


def _snapshot(root, archive_id, snapshot):
    if type(snapshot) is not snapshots._GitChangeSnapshot or type(snapshot._raw) is not bytes:
        raise WorkSessionDocumentGitProvenanceError()
    if len(snapshot._raw) > writer.GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES:
        raise WorkSessionDocumentGitProvenanceError("work_session_document_git_limit")
    data = snapshots._GitChangeSnapshot(snapshot._raw)._document()
    capture = data["capture"]
    rows = _rows(capture["private_changes"])
    if (type(capture.get("root")) is not str or Path(capture["root"]) != root
            or capture.get("archive_id") != archive_id or not _digest(data.get("plan_sha256"))
            or capture["public_changes"] != [row["public_observation"] for row in rows]):
        raise WorkSessionDocumentGitProvenanceError()
    return data["plan_sha256"], rows


def _origin(view, expected_type):
    if type(view) is not expected_type:
        raise WorkSessionDocumentGitProvenanceError("work_session_document_git_proof_unavailable")
    facts = view.proof_document()
    outputs = view.approved_output_map()
    if (type(facts) is not dict or set(facts) != _PROOF_FACTS
            or any(not _digest(facts[name]) for name in _PROOF_FACTS - {"work_session_binding"})
            or type(facts["work_session_binding"]) is not dict or type(outputs) is not dict):
        raise WorkSessionDocumentGitProvenanceError("work_session_document_git_proof_unavailable")
    binding = WorkSessionBinding.from_document(facts["work_session_binding"])
    detached = {}
    for path, row in outputs.items():
        receipt = type(row) is dict and row.get("output_kind") == completion.RECEIPT_OUTPUT_KIND
        if (type(path) is not str or type(row) is not dict or set(row) != _MAP_KEYS
                or type(row["output_kind"]) is not str
                or row["output_kind"] not in (completion.DOCUMENT_OUTPUT_KIND, completion.RECEIPT_OUTPUT_KIND)
                or not _digest(row["sha256"]) or not _digest(row["output_identity_sha256"])
                or type(row["size_bytes"]) is not int or not 1 <= row["size_bytes"] <= scope_codec._MAX_FILE_BYTES
                or (receipt and (row["head_sha256"] is not None or row["head_bytes"] is not None))
                or (not receipt and (not _digest(row["head_sha256"]) or type(row["head_bytes"]) is not int
                                     or not 1 <= row["head_bytes"] <= scope_codec._MAX_FILE_BYTES))):
            raise WorkSessionDocumentGitProvenanceError("work_session_document_git_proof_unavailable")
        proof = _proof(facts, row, path, "change:000001")
        if receipt and scope_codec._proof_output_path(proof) != path:
            raise WorkSessionDocumentGitProvenanceError("work_session_document_git_proof_unavailable")
        detached[path] = json.loads(_canonical(row))
    return json.loads(_canonical(facts)), detached, binding


def _proof(facts, output, path, change_ref):
    return {"change_ref": change_ref, "producer": _PRODUCER, "output_kind": output["output_kind"],
            "output_identity_sha256": output["output_identity_sha256"],
            "document_path_sha256": scope_codec._sha_text(path),
            "whole_file_sha256": output["sha256"], "whole_file_bytes": output["size_bytes"],
            "head_file_sha256": output["head_sha256"], "head_file_bytes": output["head_bytes"],
            "manifest_sha256": facts["manifest_sha256"], "context_sha256": facts["context_sha256"],
            "execution_sha256": facts["execution_sha256"], "receipt_sha256": facts["common_final_receipt_sha256"],
            "recovery_scope_sha256": facts["recovery_scope_sha256"],
            "original_work_session_binding": facts["work_session_binding"]}


def _matches(row, output):
    """Git-side predicate only; authenticated producer facts are separate."""
    public = row["public_observation"]
    if output["output_kind"] == completion.RECEIPT_OUTPUT_KIND:
        worktree = public["worktree"]
        return (snapshots._new_whole_receipt(row) and type(worktree["bytes"]) is int
                and worktree["sha256"] == output["sha256"] and worktree["bytes"] == output["size_bytes"])
    if row["original_path"] is not None:
        return False
    return scope_codec._modified_document_matches(public, {
        "head_file_sha256": output["head_sha256"], "head_file_bytes": output["head_bytes"],
        "whole_file_sha256": output["sha256"], "whole_file_bytes": output["size_bytes"]})


def _partition(plan_sha, rows, proofs, binding):
    proof_by_ref = {proof["change_ref"]: proof for proof in proofs}
    selected, excluded = [], []
    for row in rows:
        ref = row["public_observation"]["change_ref"]
        proof = proof_by_ref.get(ref)
        kind = "unknown"
        if proof is not None:
            original = WorkSessionBinding.from_document(proof["original_work_session_binding"])
            if snapshots._session_identity(original) == snapshots._session_identity(binding):
                selected.append(row)
                continue
            kind = "other_session"
        excluded.append({"change_ref": ref, "scope": kind, "reason": writer.GIT_BACKUP_EXCLUSION_REASONS[kind]})
    groups, current = [], []

    def flush():
        if current:
            groups.append({"group_id": "group:session-documents-" + str(len(groups) + 1).zfill(6),
                           "commit_subject": "Back up authenticated session document changes",
                           "change_refs": sorted(row["public_observation"]["change_ref"] for row in current)})
            current.clear()

    for row in selected:
        if current and not writer._literal_path_argv_is_bounded([value["path"] for value in (*current, row)]):
            flush()
        current.append(row)
    flush()
    partition = {"schema": writer.GIT_BACKUP_SELECTION_V2_SCHEMA, "expected_plan_sha256": plan_sha,
                 "selected_groups": groups, "excluded_changes": sorted(excluded, key=lambda row: row["change_ref"])}
    try:
        writer._selection_partition(partition, expected_plan_sha256=plan_sha,
            observed_change_refs=[row["public_observation"]["change_ref"] for row in rows])
    except writer.GitBackupWriterError as error:
        if error.code != "git_backup_no_selected_changes":
            raise
    return partition


def _control_candidates(root, held):
    """Bounded manifest digests of retained controls; contents are read later."""
    held.verify_held()
    entries = recovery._safe_control_entries(root)
    digests = []
    for path in entries:
        name = path.name
        if not name.endswith(".json") or not registry._is_digest("sha256:" + name[:-5]):
            continue
        digests.append("sha256:" + name[:-5])
    return tuple(digests)


def _select_document_changes_held(root, *, held, snapshot, selected_binding, key_provider=None):
    def select():
        if type(selected_binding) is not WorkSessionBinding:
            raise WorkSessionDocumentGitProvenanceError()
        binding = WorkSessionBinding.from_document(selected_binding.document())
        actual, archive_id = bundle._held_root(root, held)
        if binding.archive_identity_sha256 != approval.exact_human_approval_archive_identity_sha256(archive_id):
            raise WorkSessionDocumentGitProvenanceError()
        plan_sha, rows = _snapshot(actual, archive_id, snapshot)
        candidates = _control_candidates(actual, held)
        read, expected = _reader_api("key")
        origins, outputs, overlapping, document_controls, unverified = {}, {}, set(), 0, 0
        for manifest_sha in candidates:
            held.verify_held()
            plan = None
            try:
                plan = recovery.load_local_recovery_plan(actual, manifest_sha256=manifest_sha)
                if plan.session_context is None:
                    continue
                view = sessions._view(plan)
                if sessions._document_images(plan) is None:
                    continue
                document_controls += 1
                context_sha = approval.exact_human_approval_context_sha256(view.context)
                verified = read(actual, held=held, manifest_sha256=manifest_sha,
                                context_sha256=context_sha, key_provider=key_provider)
                facts, approved, original = _origin(verified, expected)
                if (facts["manifest_sha256"] != manifest_sha or facts["context_sha256"] != context_sha
                        or original.archive_identity_sha256 != binding.archive_identity_sha256):
                    raise WorkSessionDocumentGitProvenanceError()
            except Exception:
                # Invalid, incomplete or unauthenticated controls are unverified,
                # never absence, ownership or a reason to repair anything.
                if plan is not None and plan.session_context is not None:
                    unverified += 1
                continue
            key = (facts["manifest_sha256"], facts["context_sha256"], facts["execution_sha256"])
            origins[key] = facts
            for path, output in approved.items():
                if path in outputs and outputs[path][0] != key:
                    # Two completed approvals over one document need actual
                    # consecutive evidence; without it the path stays unknown.
                    overlapping.add(path)
                outputs[path] = (key, output)
        for path in overlapping:
            outputs.pop(path, None)
        proofs = []
        for row in rows:
            found = outputs.get(row["path"])
            if found is not None and _matches(row, found[1]):
                proofs.append(_proof(origins[found[0]], found[1], row["path"], row["public_observation"]["change_ref"]))
                if len(proofs) > _MAX_PROOFS:
                    raise WorkSessionDocumentGitProvenanceError("work_session_document_git_limit")
        proofs.sort(key=lambda row: row["change_ref"])
        _canonical(proofs, _MAX_PROOF_BYTES)
        partition = _partition(plan_sha, rows, proofs, binding)
        if _control_candidates(actual, held) != candidates:
            raise WorkSessionDocumentGitProvenanceError()
        bundle._held_root(actual, held)
        return _DocumentSelection(_canonical({"schema": "wom-kit/private-document-git-selection/v1",
            "selection": partition, "proofs": proofs, "selected_identity_binding": binding.document(),
            "control_inventory_state": "present" if candidates else "absent",
            "document_control_count": document_controls, "authenticated_recovery_count": len(origins),
            "unverified_document_control_count": unverified, "overlapping_document_count": len(overlapping)}))
    return _safe_call(select)


def _stored(proofs, private_changes):
    if type(proofs) is not list or not 1 <= len(proofs) <= _MAX_PROOFS:
        raise WorkSessionDocumentGitProvenanceError()
    detached = json.loads(_canonical(proofs, _MAX_PROOF_BYTES))
    rows = {row["public_observation"]["change_ref"]: row for row in _rows(private_changes)}
    grouped, refs, manifests = {}, set(), {}
    for proof in detached:
        if (not scope_codec._is_document_proof(proof) or set(proof) != scope_codec._DOCUMENT_KEYS
                or type(proof["change_ref"]) is not str
                or scope_codec._CHANGE_REF.fullmatch(proof["change_ref"]) is None
                or any(not _digest(proof[name]) for name in scope_codec._DOCUMENT_DIGESTS)
                or type(proof["output_kind"]) is not str or proof["output_kind"] not in scope_codec._DOCUMENT_KINDS
                or type(proof["whole_file_bytes"]) is not int
                or not 1 <= proof["whole_file_bytes"] <= scope_codec._MAX_FILE_BYTES
                or type(proof["original_work_session_binding"]) is not dict
                or proof["change_ref"] in refs or proof["change_ref"] not in rows):
            raise WorkSessionDocumentGitProvenanceError()
        WorkSessionBinding.from_document(proof["original_work_session_binding"])
        key = (proof["manifest_sha256"], proof["context_sha256"], proof["execution_sha256"])
        if proof["manifest_sha256"] in manifests and manifests[proof["manifest_sha256"]] != key:
            raise WorkSessionDocumentGitProvenanceError("work_session_document_git_proof_unavailable")
        manifests[proof["manifest_sha256"]] = key
        refs.add(proof["change_ref"])
        grouped.setdefault(key, []).append(proof)
    return grouped, rows


def _verify_stored_group(view, expected_type, proofs, rows, archive_id):
    facts, outputs, binding = _origin(view, expected_type)
    if binding.archive_identity_sha256 != approval.exact_human_approval_archive_identity_sha256(archive_id):
        raise WorkSessionDocumentGitProvenanceError("work_session_document_git_proof_unavailable")
    for proof in proofs:
        row = rows[proof["change_ref"]]
        output = outputs.get(row["path"])
        if (output is None or not _matches(row, output)
                or _proof(facts, output, row["path"], proof["change_ref"]) != proof):
            raise WorkSessionDocumentGitProvenanceError("work_session_document_git_proof_unavailable")


def _revalidate(root, held, proofs, private_changes, mode, *, key_provider=None, claim=None):
    grouped, rows = _stored(proofs, private_changes)  # Detach before callbacks.
    actual, archive_id = bundle._held_root(root, held)
    verified, images = [], []
    for (manifest, context, execution), group in sorted(grouped.items()):
        read, expected = _reader_api(mode)
        arguments = dict(held=held, manifest_sha256=manifest, context_sha256=context)
        if mode == "image":
            view = read(actual, execution_sha256=execution, **arguments)
        elif mode == "claim":
            view = read(actual, execution_sha256=execution, claim=claim, **arguments)
        else:
            view = read(actual, key_provider=key_provider, **arguments)
        _verify_stored_group(view, expected, group, rows, archive_id)
        if not _digest(view.image_sha256):
            raise WorkSessionDocumentGitProvenanceError("work_session_document_git_proof_unavailable")
        images.append((manifest, context, execution, view.image_sha256))
        verified.extend(group)
        bundle._held_root(actual, held)
    return tuple(images) if mode == "image" else sorted(verified, key=lambda row: row["change_ref"])


def _revalidate_document_proofs_held(root, *, held, proofs, private_changes, key_provider=None):
    return _safe_call(lambda: _revalidate(root, held, proofs, private_changes, "key", key_provider=key_provider))


def _revalidate_document_proofs_with_claim_held(root, *, held, proofs, private_changes, claim):
    def verify():
        if type(claim) is not approval._ClaimedExactHumanApproval:
            raise WorkSessionDocumentGitProvenanceError()
        return _revalidate(root, held, proofs, private_changes, "claim", claim=claim)
    return _safe_call(verify)


def _original_document_proof_images_held(root, *, held, proofs, private_changes):
    return _safe_call(lambda: _revalidate(root, held, proofs, private_changes, "image"))
