"""Internal, receipt-only provenance for an exact Git selection.

This first producer proves only the whole canonical *new completion receipt* of
an authenticated work-session decision. It does not prove the documents that a
session discussed, nor authorize Git, establish the current claimant, or claim
that an archive has been backed up. Public routing and approved writer/resume
composition remain separate work. No names, paths, times, or caller booleans
are treated as authorship evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from . import exact_human_approval as approval
from . import exact_operation_manifest as exact
from . import git_backup_plan as planning
from . import git_backup_writer as writer
from . import work_session_bundle as bundle
from . import work_session_execution as execution
from .work_session_binding import WorkSessionBinding


_RECEIPT_PATH = re.compile(r"receipts/ops/exact-operations/([0-9a-f]{64})\.json")
# Bound the initial adapter's potentially expensive authenticated claim scans.
# Count every matching changed path, including invalid/legacy receipts, before
# reading proof bodies. Exceeding this budget fails the whole classification;
# it is not truncation, pagination, or evidence that unvisited files are absent.
# A larger/streamed proof budget needs a separate bounded implementation.
_MAX_RECEIPT_CANDIDATES = 128


class WorkSessionGitProvenanceError(RuntimeError):
    """Fixed-code errors; rejected private input is never retained as context."""

    def __init__(self, code="work_session_git_provenance_invalid"):
        self.code = code if type(code) is str and code in {
            "work_session_git_provenance_invalid", "work_session_git_snapshot_unavailable",
            "work_session_git_snapshot_changed", "work_session_git_receipt_limit",
        } else "work_session_git_provenance_invalid"
        super().__init__(self.code)


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


@dataclass(frozen=True, repr=False)
class _GitChangeSnapshot:
    """Detached private planner input, never a capability or approval."""

    _raw: bytes

    def __repr__(self):
        return "<private Git change snapshot>"

    def _document(self):
        if type(self._raw) is not bytes:
            raise WorkSessionGitProvenanceError()
        return json.loads(self._raw)


@dataclass(frozen=True, repr=False)
class _ReceiptSelection:
    """Private partition and original proofs, with a content-free projection."""

    _raw: bytes

    def __repr__(self):
        return "<private receipt-only Git selection; not approval>"

    def _private_document(self):
        return json.loads(self._raw)

    def public_summary(self):
        data = self._private_document()
        partition = data["selection"]
        selected = sum(len(group["change_refs"]) for group in partition["selected_groups"])
        exclusions = partition["excluded_changes"]
        return {
            "status": "receipt_selection_classified" if selected else "no_eligible_receipts",
            "selected_receipt_count": selected,
            "excluded_change_count": len(exclusions),
            "other_session_receipt_count": sum(row["scope"] == "other_session" for row in exclusions),
            "ownership_unverified_count": sum(row["scope"] == "unknown" for row in exclusions),
            "unverified_receipt_candidate_count": data["unverified_receipt_candidates"],
            "snapshot_partition_complete": True,
            "receipt_only": True,
            "document_provenance_evaluated": False,
            "current_claim_authority_evaluated": False,
            "exact_human_approval_required": True,
            "ready_for_write": False,
            "backup_performed": False,
            "artifact_backup_complete": False,
            "private_values_echoed": False,
        }


def _observe(store, held, options):
    """Reuse the canonical planner, including independent refs and Git pin.

    There is deliberately no second status/blob/ignore or remote observer here.
    The stored-credential broker finishes before any receipt-key consumer starts.
    """
    store._require_held_lock(held)
    capture = {}
    plan = planning.git_backup_plan(store.root, _private_capture=capture, **options)
    store._require_held_lock(held)
    if (plan.get("ok") is not True or plan.get("inspection_complete") is not True
            or plan.get("blockers") != [] or not capture
            or plan.get("changes") != capture.get("public_changes")
            or plan.get("change_summary", {}).get("count") != len(capture.get("private_changes", []))):
        raise WorkSessionGitProvenanceError("work_session_git_snapshot_unavailable")
    capture["root"] = str(capture["root"])
    return _canonical({"plan_sha256": plan["plan_sha256"], "capture": capture, "options": options})


def _safe_failure(call):
    # Raise outside the handler so private exception data cannot survive in
    # __context__/__cause__, including callbacks and OS errors carrying paths.
    failure = None
    try:
        return call()
    except WorkSessionGitProvenanceError as exc:
        failure = exc.code
    except Exception:
        failure = "work_session_git_provenance_invalid"
    raise WorkSessionGitProvenanceError(failure)


def _capture_git_snapshot_held(
    archive_root, *, held, remote_name="origin", branch=None,
    credential_mode="stored", max_changes=planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGES,
    max_changed_bytes=planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGED_BYTES,
) -> _GitChangeSnapshot:
    """Capture only a successful complete existing plan under the archive lock."""
    def capture():
        store, _archive_id = execution._store(archive_root)
        options = dict(remote_name=remote_name, branch=branch, credential_mode=credential_mode,
                       max_changes=max_changes, max_changed_bytes=max_changed_bytes)
        return _GitChangeSnapshot(_observe(store, held, options))
    return _safe_failure(capture)


def _new_whole_receipt(row):
    observation = row["public_observation"]
    worktree, index = observation["worktree"], observation["index"]
    return (
        row["original_path"] is None
        and observation["operation"] in {"added", "added_untracked"}
        and observation["head"]["state"] == "absent"
        and worktree["state"] == "regular_file"
        and (index["state"] == "absent" or (
            index["state"] == "blob" and index["mode"] == "regular_file"
            and index["sha256"] == worktree["sha256"] and index["bytes"] == worktree["bytes"]
        ))
    )


def _authenticated_receipt(store, held, row, execution_sha, *, key_provider=None):
    """Prove canonical whole bytes, original context/MAC and immutable generation.

    completed_only rejects started/failed/missing/ambiguous evidence. It cannot
    enter the domain writer, publish a claim, or repair a missing checkpoint.
    The existing proof reader checks safe parent chains and bounded stable files.
    """
    receipt = exact.load_exact_operation_final_receipt_read_only(
        store.root, execution_sha, heartbeat=held.verify_held,
    )
    if receipt is None:
        return None
    raw = exact._canonical_json_bytes(receipt) + b"\n"
    worktree = row["public_observation"]["worktree"]
    if (len(raw) != worktree["bytes"]
            or "sha256:" + hashlib.sha256(raw).hexdigest() != worktree["sha256"]):
        return None
    manifest_sha = receipt["result"]["manifest_sha256"]
    bound = bundle.load_context_bound_session_decision(store, manifest_sha256=manifest_sha)
    original_binding = bound.prepared.manifest.work_session_binding
    if original_binding is None or original_binding.archive_identity_sha256 != store.archive_identity_sha256:
        return None
    verified = execution._resume_session_decision_held(
        store.root, held=held, manifest_sha256=manifest_sha, completed_only=True,
        key_provider=key_provider,
    )
    if (verified.get("ok") is not True or verified.get("independent_post_verification") is not True
            or verified.get("execution_sha256") != execution_sha
            or verified.get("receipt_sha256") != receipt["receipt_sha256"]
            or verified.get("work_session_binding") != original_binding.document()
            or verified.get("domain_writer_reentered") is not False
            or verified.get("native_approval_redisplayed") is not False):
        return None
    reread = exact.load_exact_operation_final_receipt_read_only(
        store.root, execution_sha, heartbeat=held.verify_held,
    )
    if reread != receipt:
        return None
    return {
        "change_ref": row["public_observation"]["change_ref"],
        "producer": "authenticated_work_session_completion_receipt",
        "whole_file_sha256": worktree["sha256"], "whole_file_bytes": len(raw),
        "execution_sha256": execution_sha, "receipt_sha256": receipt["receipt_sha256"],
        "manifest_sha256": manifest_sha,
        "context_sha256": approval.exact_human_approval_context_sha256(bound.context),
        "registry_generation_sha256": bound.prepared.transition.after.sha256,
        "original_work_session_binding": original_binding.document(),
    }


def _session_identity(binding):
    # A later revision is neither a new session nor permission to rewrite the
    # original binding. Current actor/claimed-binding authority is separate.
    return (binding.archive_identity_sha256, binding.client_app_ref,
            binding.workstream_ref, binding.work_session_ref)


def _select_receipt_changes_held(
    archive_root, *, held, snapshot: _GitChangeSnapshot, selected_binding: WorkSessionBinding,
    key_provider=None,
) -> _ReceiptSelection:
    """Automatically partition *every* captured change; never authorize a write.

    selected_binding is an internal classification identity, not current claim
    authority. A future held facade must independently validate current actor
    ownership and obtain exact human approval for the resulting Git manifest.
    The optional private provider only forwards the existing completed-proof
    reader's injection seam; classification never acquires a second key itself.
    """
    def select():
        if type(snapshot) is not _GitChangeSnapshot or type(selected_binding) is not WorkSessionBinding:
            raise WorkSessionGitProvenanceError()
        binding = WorkSessionBinding.from_document(selected_binding.document())
        store, _archive_id = execution._store(archive_root)
        store._require_held_lock(held)
        if binding.archive_identity_sha256 != store.archive_identity_sha256:
            raise WorkSessionGitProvenanceError()
        data = snapshot._document()
        if _observe(store, held, data["options"]) != snapshot._raw:
            raise WorkSessionGitProvenanceError("work_session_git_snapshot_changed")
        rows = data["capture"]["private_changes"]
        candidates = sum(_RECEIPT_PATH.fullmatch(row["path"]) is not None for row in rows)
        if candidates > _MAX_RECEIPT_CANDIDATES:
            raise WorkSessionGitProvenanceError("work_session_git_receipt_limit")
        selected, excluded, proofs, unverified = [], [], [], 0
        for row in rows:
            store._require_held_lock(held)
            change_ref = row["public_observation"]["change_ref"]
            match = _RECEIPT_PATH.fullmatch(row["path"])
            proof = None
            if match is not None and _new_whole_receipt(row):
                try:
                    proof = _authenticated_receipt(
                        store, held, row, "sha256:" + match[1], key_provider=key_provider,
                    )
                except Exception:
                    # Invalid/unavailable proof is unknown, never absent or
                    # implicitly owned. The final snapshot recheck still fails
                    # closed on changed receipt bytes or Git evidence.
                    proof = None
            scope = "unknown"
            if proof is not None:
                proofs.append(proof)
                original = WorkSessionBinding.from_document(proof["original_work_session_binding"])
                if _session_identity(original) == _session_identity(binding):
                    selected.append(row)
                    continue
                scope = "other_session"
            elif match is not None:
                unverified += 1
            excluded.append({"change_ref": change_ref, "scope": scope,
                             "reason": writer.GIT_BACKUP_EXCLUSION_REASONS[scope]})
        groups, group_rows = [], []

        def flush_group():
            if group_rows:
                groups.append({"group_id": "group:session-receipts-" + str(len(groups) + 1).zfill(6),
                               "change_refs": sorted(row["public_observation"]["change_ref"] for row in group_rows),
                               "commit_subject": "Back up authenticated session receipts"})
                group_rows.clear()

        for row in selected:
            if group_rows and not writer._literal_path_argv_is_bounded(
                    [item["path"] for item in (*group_rows, row)]):
                flush_group()
            group_rows.append(row)
        flush_group()
        partition = {
            "schema": writer.GIT_BACKUP_SELECTION_V2_SCHEMA,
            "expected_plan_sha256": data["plan_sha256"], "selected_groups": groups,
            "excluded_changes": sorted(excluded, key=lambda row: row["change_ref"]),
        }
        try:
            writer._selection_partition(partition, expected_plan_sha256=data["plan_sha256"],
                observed_change_refs=[row["change_ref"] for row in data["capture"]["public_changes"]])
        except writer.GitBackupWriterError as exc:
            # The existing validator verifies exclusions before rejecting its
            # all-excluded/no-write case. Preserve that honest classification.
            if exc.code != "git_backup_no_selected_changes":
                raise
        if _observe(store, held, data["options"]) != snapshot._raw:
            raise WorkSessionGitProvenanceError("work_session_git_snapshot_changed")
        return _ReceiptSelection(_canonical({
            "selection": partition, "proofs": proofs,
            "selected_identity_binding": binding.document(),
            "unverified_receipt_candidates": unverified,
        }))
    return _safe_failure(select)
