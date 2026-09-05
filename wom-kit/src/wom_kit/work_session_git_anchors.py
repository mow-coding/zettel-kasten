"""Read-only observation of the immutable commits asserted by an original backup.

An authenticated terminal record is still an assertion about Git. This helper
checks the original ordered commit objects, exact messages, selected paths and
blob bytes, then queries the original approved URL/ref. It neither authenticates
an approval nor grants resume/completion authority. Its caller must independently
authenticate retained original evidence. No public dispatch is added here.

Current HEAD and unrelated later work are not inputs to the old commit proof.
They must not cause a fresh planner to rewrite the original backup's identity.
Remote advancement is reported as a mismatch, not inferred preservation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hmac

from . import git_backup_plan as planning
from . import git_backup_writer as writer


class GitAnchorObservationError(RuntimeError):
    def __init__(self):
        super().__init__("work_session_git_anchor_input_invalid")


@dataclass(frozen=True, slots=True)
class _OriginalGitAnchorObservation:
    status: str
    commit_count: int
    commit_anchors_verified: bool = False
    remote_ref_independently_verified: bool = False
    current_head_relation: str = "not_reached"

    def document(self):
        return {
            "schema": "wom-kit/work-session-git-anchor-observation/v1",
            "status": self.status,
            "commit_count": self.commit_count,
            "commit_anchors_verified": self.commit_anchors_verified,
            "remote_ref_independently_verified": self.remote_ref_independently_verified,
            "current_head_relation": self.current_head_relation,
            "approval_authenticated": False,
            "backup_completion_verified": False,
            "git_mutation_performed": False,
            "private_values_echoed": False,
        }


def _observe_original_git_anchors_held(prepared, *, held, commit_oids):
    """Require a real held archive lock; return bounded evidence, never authority.

The original OIDs must be supplied as a complete ordered tuple. They remain
untrusted assertions here. Config/runtime and Git metadata checks are retained;
no dirty-tree planner, actor rewrite, claim/key-store access or Git write occurs.
Remote authentication uses the existing noninteractive stored-credential query.
"""
    valid = False
    try:
        frozen = writer._freeze_validated_prepared(prepared)
        writer._require_git_backup_held_lock(frozen, held)
        valid = (
            type(commit_oids) is tuple
            and len(commit_oids) == len(frozen.groups)
            and len(commit_oids) > 0
            and all(type(oid) is str and writer._OID_RE.fullmatch(oid) for oid in commit_oids)
            and len(set(commit_oids)) == len(commit_oids)
        )
    except Exception:
        pass
    if not valid:
        # Raise outside the handler so private paths/documents are not retained
        # even in a suppressed exception's __context__.
        raise GitAnchorObservationError()
    oids = tuple(commit_oids)
    count = len(oids)
    outcome = _OriginalGitAnchorObservation("runtime_unavailable", count)
    try:
        with writer._pinned_git_runtime(frozen):
            backend = writer._GitBackupBackend(frozen)
            if (not planning._git_metadata_is_local_real(frozen.root)
                    or not backend._runtime_binding_matches(include_trust_digest=True)):
                return outcome
            parent = frozen.initial_head_oid
            for oid, group in zip(oids, frozen.groups):
                commit = backend._commit_object(oid)
                if (commit is None or not hmac.compare_digest(commit[0], parent)
                        or commit[1] != group.commit_message
                        or backend._commit_paths(oid) != group.paths
                        or not backend._tree_matches_group(oid, group)):
                    return _OriginalGitAnchorObservation("commit_mismatch", count)
                parent = oid
            remote_state, remote_oid = writer._query_exact_remote_ref_with_stored_credentials(frozen)
            if remote_state == "target_ref_missing":
                status = "remote_absent"
            elif remote_state != "present" or type(remote_oid) is not str:
                status = "remote_unavailable"
            elif not hmac.compare_digest(remote_oid, oids[-1]):
                status = "remote_mismatch"
            else:
                status = "verified"
            writer._require_git_backup_held_lock(frozen, held)
            # Preserve the transport/config boundary across the potentially
            # long remote query, without tying proof to the current dirty tree.
            if (not planning._git_metadata_is_local_real(frozen.root)
                    or not backend._runtime_binding_matches(include_trust_digest=True)):
                return _OriginalGitAnchorObservation("observation_changed", count)
            # This is a separately observed current-state hint, not part of the
            # original proof. Read it after the remote query, which may be slow.
            head = backend._head()
            relation = "unavailable" if head is None else (
                "terminal" if hmac.compare_digest(head, oids[-1]) else "different"
            )
            outcome = _OriginalGitAnchorObservation(status, count, True, status == "verified", relation)
        return outcome
    except Exception:
        # A pinned-runtime/lock/transport failure is an unavailable observation,
        # not an invalidation of a previously authenticated historical receipt.
        pass
    return _OriginalGitAnchorObservation("runtime_unavailable", count)
