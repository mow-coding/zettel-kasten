"""Private intake-output classification; not current Git or write authority.

The supplied Git snapshot is DATA. Its owner must retain the existing exact
Git observer and selected/excluded preimage guards. This adapter performs no
Git/network observation, actor mutation, approval or backup. Context filenames
are only bounded discovery hints; ownership requires original completion MACs
and the retained approved output map. Legacy human producers remain separate.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from . import exact_human_approval as approval
from . import git_backup_session_scope as scope_codec
from . import git_backup_writer as writer
from . import work_session_git_provenance as snapshots
from . import work_session_registry as registry
from . import work_session_source_intake_bundle as bundle
from . import work_session_source_intake_inventory as inventory_module
from .work_session_binding import WorkSessionBinding


_MAX_PROOFS = 8192
_MAX_PROOF_BYTES = 16 * 1024 * 1024
_MAX_RESULT_BYTES = 32 * 1024 * 1024
_PRODUCER = "authenticated_source_intake_batch_output"
_PROOF_FACTS = frozenset({"manifest_sha256", "context_sha256", "execution_sha256",
    "common_final_receipt_sha256", "common_result_sha256", "approval_binding_sha256",
    "session_scope_sha256", "work_session_binding"})
_MAP_KEYS = frozenset({"output_kind", "target_kind", "field_ref", "sha256", "size_bytes", "output_identity_sha256"})
_ERRORS = frozenset({
    "work_session_intake_git_invalid", "work_session_intake_git_lock_required",
    "work_session_intake_git_inventory_unavailable", "work_session_intake_git_inventory_changed",
    "work_session_intake_git_limit", "work_session_intake_git_proof_unavailable",
    "work_session_intake_git_proof_ambiguous",
})


class WorkSessionIntakeGitProvenanceError(RuntimeError):
    def __init__(self, code="work_session_intake_git_invalid"):
        self.code = code if type(code) is str and code in _ERRORS else "work_session_intake_git_invalid"
        super().__init__(self.code)


def _safe_call(call):
    code = "work_session_intake_git_invalid"
    try:
        return call()
    except WorkSessionIntakeGitProvenanceError as error:
        code = error.code
    except bundle.WorkSessionIntakeBundleError as error:
        if error.code == "work_session_intake_bundle_lock_required":
            code = "work_session_intake_git_lock_required"
    except inventory_module.WorkSessionIntakeInventoryError as error:
        code = {"work_session_intake_inventory_changed": "work_session_intake_git_inventory_changed",
                "work_session_intake_inventory_limit": "work_session_intake_git_limit",
                "work_session_intake_inventory_lock_required": "work_session_intake_git_lock_required"}.get(
                    error.code, "work_session_intake_git_inventory_unavailable")
    except Exception:
        pass
    raise WorkSessionIntakeGitProvenanceError(code)


def _completion():
    from . import work_session_source_intake_completion
    return work_session_source_intake_completion


def _canonical(value, maximum=_MAX_RESULT_BYTES):
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    if len(raw) > maximum:
        raise WorkSessionIntakeGitProvenanceError("work_session_intake_git_limit")
    return raw


def _digest(value):
    return type(value) is str and registry._is_digest(value)


@dataclass(frozen=True, slots=True, repr=False)
class _IntakeOutputSelection:
    _raw: bytes

    def __repr__(self):
        return "<private intake-output selection; not Git or write authority>"

    def _private_document(self):
        return json.loads(self._raw)

    def public_summary(self):
        data = self._private_document()
        partition = data["selection"]
        selected = sum(len(group["change_refs"]) for group in partition["selected_groups"])
        excluded = partition["excluded_changes"]
        return {"state": "intake_output_selection_classified", "selected_output_count": selected,
                "other_session_output_count": sum(row["scope"] == "other_session" for row in excluded),
                "ownership_unverified_count": sum(row["scope"] == "unknown" for row in excluded),
                "hint_inventory_state": data["hint_inventory_state"],
                "context_hint_count": data["context_hint_count"],
                "authenticated_original_count": data["authenticated_original_count"],
                "unverified_context_hint_count": data["unverified_context_hint_count"],
                "snapshot_partition_complete": True, "git_snapshot_revalidated": False,
                "current_claim_authority_evaluated": False, "generic_document_provenance_evaluated": False,
                "backup_performed": False, "artifact_backup_complete": False,
                "private_values_echoed": False, "paths_echoed": False}


def _rows(private_changes):
    if type(private_changes) is not list:
        raise WorkSessionIntakeGitProvenanceError()
    # Excluded rows can dominate an existing Git snapshot. Reuse the writer's
    # historical private-input ceiling; the smaller new proof/result limits
    # must not silently become a legacy snapshot admission limit.
    copied = json.loads(_canonical(private_changes, writer.GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES))
    if any(type(row) is not dict or type(row.get("path")) is not str
           or type(row.get("public_observation")) is not dict for row in copied):
        raise WorkSessionIntakeGitProvenanceError()
    refs = [row["public_observation"].get("change_ref") for row in copied]
    if (any(type(ref) is not str or scope_codec._CHANGE_REF.fullmatch(ref) is None for ref in refs)
            or len(set(refs)) != len(refs)):
        raise WorkSessionIntakeGitProvenanceError()
    return copied


def _snapshot(root, archive_id, snapshot):
    if type(snapshot) is not snapshots._GitChangeSnapshot or type(snapshot._raw) is not bytes:
        raise WorkSessionIntakeGitProvenanceError()
    if len(snapshot._raw) > writer.GIT_BACKUP_MAX_PRIVATE_BUNDLE_BYTES:
        raise WorkSessionIntakeGitProvenanceError("work_session_intake_git_limit")
    data = snapshots._GitChangeSnapshot(snapshot._raw)._document()
    capture = data["capture"]
    rows = _rows(capture["private_changes"])
    if (type(capture.get("root")) is not str or Path(capture["root"]) != root
            or capture.get("archive_id") != archive_id or not _digest(data.get("plan_sha256"))
            or capture["public_changes"] != [row["public_observation"] for row in rows]):
        raise WorkSessionIntakeGitProvenanceError()
    return data["plan_sha256"], rows


def _origin(view, expected_type):
    if type(view) is not expected_type:
        raise WorkSessionIntakeGitProvenanceError("work_session_intake_git_proof_unavailable")
    facts = view.proof_document()
    outputs = view.approved_output_map()
    if (type(facts) is not dict or set(facts) != _PROOF_FACTS
            or any(not _digest(facts[name]) for name in _PROOF_FACTS - {"work_session_binding"})
            or type(facts["work_session_binding"]) is not dict or type(outputs) is not dict):
        raise WorkSessionIntakeGitProvenanceError("work_session_intake_git_proof_unavailable")
    binding = WorkSessionBinding.from_document(facts["work_session_binding"])
    detached = {}
    for path, row in outputs.items():
        if (type(path) is not str or type(row) is not dict or set(row) != _MAP_KEYS
                or type(row["output_kind"]) is not str or row["output_kind"] not in scope_codec._INTAKE_KINDS
                or type(row["target_kind"]) is not str or type(row["field_ref"]) is not str
                or not _digest(row["sha256"]) or not _digest(row["output_identity_sha256"])
                or type(row["size_bytes"]) is not int or not 1 <= row["size_bytes"] <= scope_codec._MAX_FILE_BYTES):
            raise WorkSessionIntakeGitProvenanceError("work_session_intake_git_proof_unavailable")
        proof = _proof(facts, row, "change:000001")
        if scope_codec._proof_output_path(proof) != path:
            raise WorkSessionIntakeGitProvenanceError("work_session_intake_git_proof_unavailable")
        detached[path] = json.loads(_canonical(row))
    return json.loads(_canonical(facts)), detached, binding


def _proof(facts, output, change_ref):
    return {"change_ref": change_ref, "producer": _PRODUCER, "output_kind": output["output_kind"],
            "output_identity_sha256": output["output_identity_sha256"],
            "whole_file_sha256": output["sha256"], "whole_file_bytes": output["size_bytes"],
            "manifest_sha256": facts["manifest_sha256"], "context_sha256": facts["context_sha256"],
            "execution_sha256": facts["execution_sha256"], "receipt_sha256": facts["common_final_receipt_sha256"],
            "intake_scope_sha256": facts["session_scope_sha256"],
            "original_work_session_binding": facts["work_session_binding"]}


def _matches(row, output):
    worktree = row["public_observation"]["worktree"]
    return (snapshots._new_whole_receipt(row) and type(worktree["bytes"]) is int
            and worktree["sha256"] == output["sha256"] and worktree["bytes"] == output["size_bytes"])


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
            groups.append({"group_id": "group:session-intake-" + str(len(groups) + 1).zfill(6),
                           "commit_subject": "Back up authenticated intake records",
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


def _select_intake_output_changes_held(root, *, held, snapshot, selected_binding, key_provider=None):
    def select():
        if type(selected_binding) is not WorkSessionBinding:
            raise WorkSessionIntakeGitProvenanceError()
        binding = WorkSessionBinding.from_document(selected_binding.document())
        actual, archive_id = bundle._held_root(root, held)
        if binding.archive_identity_sha256 != approval.exact_human_approval_archive_identity_sha256(archive_id):
            raise WorkSessionIntakeGitProvenanceError()
        plan_sha, rows = _snapshot(actual, archive_id, snapshot)
        hints = inventory_module._capture_source_intake_context_inventory_held(actual, held=held)
        reader = _completion()
        origins, outputs, unverified = {}, {}, 0
        for hint in hints.hints():
            held.verify_held()
            try:
                _prepared, context = bundle._decode_context(actual, hint.raw, hint.manifest_sha256)
                context_sha = approval.exact_human_approval_context_sha256(context)
                view = reader._read_completed_session_source_intake_held(actual, held=held,
                    manifest_sha256=hint.manifest_sha256, context_sha256=context_sha, key_provider=key_provider)
                facts, approved, original = _origin(view, reader._VerifiedSessionSourceIntakeCompletion)
                if (facts["manifest_sha256"] != hint.manifest_sha256 or facts["context_sha256"] != context_sha
                        or original.archive_identity_sha256 != binding.archive_identity_sha256):
                    raise WorkSessionIntakeGitProvenanceError()
            except Exception:
                # Incomplete/corrupt/unauthenticated evidence does not become
                # absence or filename ownership. Matching changes stay unknown.
                unverified += 1
                continue
            key = (facts["manifest_sha256"], facts["context_sha256"], facts["execution_sha256"])
            origins[key] = facts
            for path, output in approved.items():
                if path in outputs and outputs[path][0] != key:
                    raise WorkSessionIntakeGitProvenanceError("work_session_intake_git_proof_ambiguous")
                outputs[path] = (key, output)
        proofs = []
        for row in rows:
            found = outputs.get(row["path"])
            if found is not None and _matches(row, found[1]):
                proofs.append(_proof(origins[found[0]], found[1], row["public_observation"]["change_ref"]))
                if len(proofs) > _MAX_PROOFS:
                    raise WorkSessionIntakeGitProvenanceError("work_session_intake_git_limit")
        proofs.sort(key=lambda row: row["change_ref"])
        _canonical(proofs, _MAX_PROOF_BYTES)
        partition = _partition(plan_sha, rows, proofs, binding)
        inventory_module._require_source_intake_context_inventory_unchanged_held(actual, inventory=hints, held=held)
        bundle._held_root(actual, held)
        return _IntakeOutputSelection(_canonical({"schema": "wom-kit/private-intake-git-selection/v1",
            "selection": partition, "proofs": proofs, "selected_identity_binding": binding.document(),
            "hint_inventory_state": hints.state, "context_hint_count": len(hints.hints()),
            "authenticated_original_count": len(origins), "unverified_context_hint_count": unverified}))
    return _safe_call(select)


def _stored(proofs, private_changes):
    if type(proofs) is not list or not 1 <= len(proofs) <= _MAX_PROOFS:
        raise WorkSessionIntakeGitProvenanceError()
    detached = json.loads(_canonical(proofs, _MAX_PROOF_BYTES))
    rows = {row["public_observation"]["change_ref"]: row for row in _rows(private_changes)}
    grouped, refs, manifests = {}, set(), {}
    for proof in detached:
        if (type(proof) is not dict or set(proof) != scope_codec._INTAKE_KEYS
                or proof.get("producer") != _PRODUCER or type(proof["change_ref"]) is not str
                or scope_codec._CHANGE_REF.fullmatch(proof["change_ref"]) is None
                or any(not _digest(proof[name]) for name in scope_codec._INTAKE_DIGESTS)
                or type(proof["output_kind"]) is not str or proof["output_kind"] not in scope_codec._INTAKE_KINDS
                or type(proof["whole_file_bytes"]) is not int or not 1 <= proof["whole_file_bytes"] <= scope_codec._MAX_FILE_BYTES
                or type(proof["original_work_session_binding"]) is not dict
                or proof["change_ref"] in refs or proof["change_ref"] not in rows):
            raise WorkSessionIntakeGitProvenanceError()
        WorkSessionBinding.from_document(proof["original_work_session_binding"])
        if proof["output_kind"] == "common_completion_receipt" and proof["output_identity_sha256"] != proof["execution_sha256"]:
            raise WorkSessionIntakeGitProvenanceError()
        key = (proof["manifest_sha256"], proof["context_sha256"], proof["execution_sha256"])
        if proof["manifest_sha256"] in manifests and manifests[proof["manifest_sha256"]] != key:
            raise WorkSessionIntakeGitProvenanceError("work_session_intake_git_proof_ambiguous")
        manifests[proof["manifest_sha256"]] = key
        refs.add(proof["change_ref"])
        grouped.setdefault(key, []).append(proof)
    return grouped, rows


def _verify_stored_group(view, expected_type, proofs, rows, archive_id):
    facts, outputs, binding = _origin(view, expected_type)
    if binding.archive_identity_sha256 != approval.exact_human_approval_archive_identity_sha256(archive_id):
        raise WorkSessionIntakeGitProvenanceError("work_session_intake_git_proof_unavailable")
    for proof in proofs:
        row = rows[proof["change_ref"]]
        output = outputs.get(row["path"])
        if (output is None or not _matches(row, output)
                or _proof(facts, output, proof["change_ref"]) != proof):
            raise WorkSessionIntakeGitProvenanceError("work_session_intake_git_proof_unavailable")


def _revalidate(root, held, proofs, private_changes, mode, *, key_provider=None, claim=None):
    grouped, rows = _stored(proofs, private_changes)  # Detach before callbacks.
    actual, archive_id = bundle._held_root(root, held)
    reader, verified, images = _completion(), [], []
    for (manifest, context, execution), group in sorted(grouped.items()):
        arguments = dict(held=held, manifest_sha256=manifest, context_sha256=context)
        if mode == "image":
            view = reader._read_session_source_intake_completion_image_held(actual,
                execution_sha256=execution, **arguments)
            expected = reader._SessionSourceIntakeCompletionImage
        elif mode == "claim":
            view = reader._verify_completed_session_source_intake_with_claim_held(actual,
                execution_sha256=execution, claim=claim, **arguments)
            expected = reader._VerifiedSessionSourceIntakeCompletion
        else:
            view = reader._read_completed_session_source_intake_held(actual, key_provider=key_provider, **arguments)
            expected = reader._VerifiedSessionSourceIntakeCompletion
        _verify_stored_group(view, expected, group, rows, archive_id)
        if not _digest(view.image_sha256):
            raise WorkSessionIntakeGitProvenanceError("work_session_intake_git_proof_unavailable")
        images.append((manifest, context, execution, view.image_sha256))
        verified.extend(group)
        bundle._held_root(actual, held)
    return tuple(images) if mode == "image" else sorted(verified, key=lambda row: row["change_ref"])


def _revalidate_intake_output_proofs_held(root, *, held, proofs, private_changes, key_provider=None):
    return _safe_call(lambda: _revalidate(root, held, proofs, private_changes, "key", key_provider=key_provider))


def _revalidate_intake_output_proofs_with_claim_held(root, *, held, proofs, private_changes, claim):
    def verify():
        if type(claim) is not approval._ClaimedExactHumanApproval:
            raise WorkSessionIntakeGitProvenanceError()
        return _revalidate(root, held, proofs, private_changes, "claim", claim=claim)
    return _safe_call(verify)


def _original_intake_output_proof_images_held(root, *, held, proofs, private_changes):
    return _safe_call(lambda: _revalidate(root, held, proofs, private_changes, "image"))
