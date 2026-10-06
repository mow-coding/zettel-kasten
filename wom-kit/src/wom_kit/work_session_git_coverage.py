"""Content-free explanation of what a session-scoped Git preview covers.

v0.4.65 (beta letter 184). A preview that selects two outputs after a
conversation completed 21 objet registrations and 43 zettel-objet links did
not say what the two were, nor that the other work is outside what a
session-scoped backup can prove. This module only counts and labels:

- one observation scope per fresh preview: progress counts for the long
  authentication loops, a memo so the discovery and the selection stage do
  not authenticate the same originals twice, and the changed-path list;
- the roles of all Git-changed paths (fixed labels from product directory
  names, never a path);
- the selected outputs by kind;
- this session's own succeeded approvals by operation, from the MAC-verified
  claim store, with whether their Git changes can be proven session-owned.

Nothing here selects a change, authorizes a write, or reads a document body.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import time


_ACTIVE: ContextVar = ContextVar("wom_session_git_observation", default=None)

# Operations whose Git-managed outputs a session-scoped backup can prove,
# and the producer that proves them.
PROVEN_OPERATIONS = {
    "work_session": "authenticated_work_session_completion_receipt",
    "source_intake_batch": "authenticated_source_intake_batch_output",
    "source_intake_record": "authenticated_source_intake_record_output",
    "local_recovery": "authenticated_local_recovery_document_output",
    # v0.4.66: the changed zettel, link receipt, before-snapshot and usage
    # record. The objet ledger stays archive-wide by design.
    "zettel_objet_link": "session_claimed_zettel_objet_link_output",
}
# Operations that write no Git-managed archive file of their own, or whose
# effects are remote or outside the archive tree.
NO_GIT_OUTPUT_OPERATIONS = frozenset({
    "git_backup", "object_storage_bytes_upload", "object_storage_bytes_offload",
    "object_storage_bytes_restore", "object_storage_bytes_preservation", "object_storage_open",
    "object_storage_remote_cleanup", "activity_cleanup", "system_cleanup", "ai_scratch_gc",
    "project_version_update", "runtime_skill_install", "runtime_skill_uninstall",
    "credential_lifecycle", "object_storage_credential_import",
})
_ROLE_BY_PREFIX = (
    ("receipts/ops/exact-operations/", "exact_operation_receipts"),
    ("receipts/ops/source-intake-batches/", "source_intake_batch_receipts"),
    ("receipts/ops/", "operation_receipts_other"),
    ("receipts/objects/zettel-links/", "zettel_objet_link_receipts"),
    ("receipts/objects/", "objet_receipts"),
    ("receipts/session-object-usage/", "session_object_usage_records"),
    ("receipts/sources/", "source_receipts"),
    ("receipts/lineage/", "lineage_receipts"),
    ("receipts/", "receipts_other"),
    ("objects/manifests/", "objet_ledger"),
    ("objects/", "objet_files_under_objects"),
    ("zettels/", "zettel_documents"),
    ("inbox/", "inbox_drafts"),
    ("db/", "index_db"),
    ("ops/", "ops_records"),
    ("views/", "views"),
    ("workbench/", "workbench"),
    ("workpacks/", "workpacks"),
    ("staging/", "staging_copy"),
)
_MAX_PATHS = 1_000_000


def changed_path_role(path):
    """A fixed label from product directory names; never the path itself."""
    if type(path) is not str:
        return "other"
    for prefix, label in _ROLE_BY_PREFIX:
        if path.startswith(prefix):
            return label
    return "archive_root_file" if "/" not in path else "other"


class _Observation:
    def __init__(self, emit):
        self._emit = emit
        self.memo = {}
        self.changed_paths = None
        self.current = 0
        self.total = 0
        self._last = 0.0
        self.phase = None

    def stage(self, phase):
        self.phase = phase
        self._last = 0.0

    def add_total(self, count):
        if type(count) is int and count > 0:
            self.total += count
            self._send(force=True)

    def tick(self):
        self.current += 1
        self._send(force=self.current >= self.total)

    def _send(self, *, force):
        now = time.monotonic()
        if self._emit is None or self.phase is None or (not force and now - self._last < 1.0):
            return
        self._last = now
        try:
            self._emit(self.phase, min(self.current, self.total), self.total)
        except Exception:
            # Presentation only; a display failure never changes the outcome.
            self._emit = None


@contextmanager
def observing(emit=None):
    observation = _Observation(emit)
    token = _ACTIVE.set(observation)
    try:
        yield observation
    finally:
        _ACTIVE.reset(token)


def active():
    return _ACTIVE.get()


def stage(phase):
    observation = _ACTIVE.get()
    if observation is not None:
        observation.stage(phase)


def add_total(count):
    observation = _ACTIVE.get()
    if observation is not None:
        observation.add_total(count)


def tick():
    observation = _ACTIVE.get()
    if observation is not None:
        observation.tick()


def memo():
    observation = _ACTIVE.get()
    return None if observation is None else observation.memo


def record_changed_paths(paths):
    observation = _ACTIVE.get()
    if observation is not None:
        observation.changed_paths = [path for path in paths if type(path) is str][:_MAX_PATHS]


def _selected_kind(proof):
    producer = proof.get("producer")
    if producer == "authenticated_work_session_completion_receipt":
        return "work_session_decision_receipt"
    kind = proof.get("output_kind")
    return kind if type(kind) is str else "other"


def session_operation_counts(root, work_session_ref, *, key_provider=None):
    """This session's succeeded approvals by operation, from MAC-verified claims.

    An approval given through a window carries no session mark and is not
    counted for any session. Unavailable evidence is reported as such; it is
    never read as "no operations".
    """
    try:
        from . import exact_approval_claims as claims

        listing = claims.list_exact_human_approval_claims(
            root, status="all", max_claims=claims.MAX_LISTED_CLAIMS, key_provider=key_provider)
        if listing.get("blocker_codes"):
            return {"state": "unavailable", "reason_code": "approval_claim_listing_incomplete"}
        counts, unmarked = {}, 0
        for claim in listing["claims"]:
            if claim.get("status") != "succeeded" or type(claim.get("operation")) is not str:
                continue
            presenter = claim.get("session_presenter")
            if type(presenter) is not dict:
                unmarked += 1
                continue
            if presenter.get("work_session_ref") == work_session_ref:
                counts[claim["operation"]] = counts.get(claim["operation"], 0) + 1
        return {"state": "counted", "counts": dict(sorted(counts.items())),
                "succeeded_approvals_without_session_mark": unmarked}
    except Exception:
        return {"state": "unavailable", "reason_code": "approval_claim_listing_unavailable"}


def build(*, proofs, selected_refs, changed_paths, inspected_path_count, operations):
    """The public, content-free coverage block of a session-scoped Git preview."""
    selected_by_kind = {}
    for proof in proofs:
        if proof.get("change_ref") in selected_refs:
            kind = _selected_kind(proof)
            selected_by_kind[kind] = selected_by_kind.get(kind, 0) + 1
    roles = {}
    for path in changed_paths or ():
        label = changed_path_role(path)
        roles[label] = roles.get(label, 0) + 1
    result = {
        "schema": "wom-kit/work-session-git-coverage/v1",
        "selected_by_kind": dict(sorted(selected_by_kind.items())),
        "selected_total": sum(selected_by_kind.values()),
        "changed_paths_by_role": dict(sorted(roles.items())) if changed_paths is not None else None,
        "changed_path_total": len(changed_paths) if changed_paths is not None else None,
        "session_owned_candidate_path_count": inspected_path_count,
        "changed_paths_are_all_sessions_and_activities": True,
        # Shared files carry several conversations' changes and belong to the
        # archive (decided before v0.4.65); no session can own them.
        "shared_by_design_roles": ["objet_ledger"],
        "shared_by_design_changed_path_count": roles.get("objet_ledger", 0),
        "official_route_for_unselected_changes": (
            "archive git-backup-plan <archive-root> --dry-run --format json previews an archive-wide backup. It "
            "includes the pending changes of every conversation and activity, so use it only after the person "
            "agrees to that; never split a shared file or commit by hand."),
        "proven_operation_kinds": sorted(PROVEN_OPERATIONS),
        "object_bytes": {
            "included_in_git_backup": False,
            "remote_preservation_evaluated": False,
            "next_action": ("object-storage-upload <archive-root> --this-session --dry-run reports which of "
                            "this session's objet bytes are already preserved remotely and which are not; "
                            "object-storage-restore --this-session --dry-run checks that they can be read back"),
        },
        "private_values_echoed": False, "paths_echoed": False,
    }
    lines = []
    if selected_by_kind:
        lines.append("Selected for this session's Git backup: "
                     + ", ".join(f"{count} {kind}" for kind, count in sorted(selected_by_kind.items())) + ".")
    else:
        lines.append("Nothing was selected for this session's Git backup.")
    if operations.get("state") == "counted":
        rows, uncovered = [], 0
        for operation, count in operations["counts"].items():
            if operation in PROVEN_OPERATIONS:
                state = "session_ownership_provable"
            elif operation in NO_GIT_OUTPUT_OPERATIONS:
                state = "no_git_managed_output"
            else:
                state = "not_provable_as_session_owned_yet"
                uncovered += count
            rows.append({"operation": operation, "succeeded_approval_count": count, "git_changes": state})
        result["session_operations"] = {
            "state": "counted", "operations": rows,
            "approval_count_whose_git_changes_are_not_selected": uncovered,
            "succeeded_approvals_without_session_mark":
                operations["succeeded_approvals_without_session_mark"],
            "reason_code": "no_session_bound_whole_file_proof_for_this_operation" if uncovered else None,
        }
        held = [row for row in rows if row["git_changes"] == "not_provable_as_session_owned_yet"]
        if held:
            lines.append(
                "This session also completed "
                + ", ".join(f"{row['succeeded_approval_count']} {row['operation']}" for row in held)
                + " approval(s). Their Git-managed changes (changed zettels, objet ledger rows, their receipts) are "
                  "NOT in this selection: a session-scoped backup selects a file only when an authenticated record "
                  "proves the whole file is this session's output, and these operations have no such record yet. "
                  "They stay uncommitted and untouched; this is not an error and nothing was lost.")
            lines.append("Do not treat the selected count as a backup of the whole conversation, and do not "
                         "commit the remaining changes by hand to work around it.")
    else:
        result["session_operations"] = {"state": "unavailable",
                                        "reason_code": operations.get("reason_code")}
        lines.append("This session's own approvals could not be counted, so the preview cannot say which of its "
                     "operations are outside the selection.")
    if changed_paths is not None:
        lines.append(f"Git currently sees {len(changed_paths)} changed path(s) from all conversations and "
                     f"activities; {inspected_path_count} of them were candidates for this session.")
    if roles.get("objet_ledger"):
        lines.append("The objet ledger is one file shared by every conversation; a session-scoped backup leaves it "
                     "out by design.")
    lines.append("Changes outside the selection are backed up only by the archive-wide git-backup-plan, which "
                 "includes every conversation's pending changes; ask the person before using it.")
    lines.append("Objet bytes are never part of a Git backup; check their remote preservation separately.")
    result["plain_summary"] = lines
    return result


LONG_RUN_GUIDANCE = {
    "preview_is_read_only": True,
    "interrupting_a_preview_has_effects": False,
    "resume_supported": False,
    "resume_note": "A preview keeps nothing to resume; running it again starts over.",
    "progress": ("Progress lines for git_output_scope_discovery and git_receipt_provenance carry current and "
                 "total: the number of authenticated originals and receipt candidates checked so far."),
    "when_to_interrupt": ("If current has not advanced for 5 minutes, interrupt the preview and send the last "
                          "progress line (stage, current, total, elapsed_seconds) to the developer. A stage that "
                          "is still counting is working."),
}
