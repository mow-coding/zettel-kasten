"""Internal, authenticated whole-output provenance for an exact Git selection.

The original producer proves the whole canonical *new completion receipt* of
an authenticated work-session decision. A separate producer verifies exact
outputs of completed scoped intake batches and single metadata records. Only
the batch producer includes a capture request (not captured object bytes).
Neither proves the documents that a
session discussed, nor authorize Git, establish the current claimant, or claim
that an archive has been backed up. Public routing and approved writer/resume
composition remain separate work. No names, paths, times, or caller booleans
are treated as authorship evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from . import exact_human_approval as approval
from . import exact_operation_manifest as exact
from . import git_backup_plan as planning
from . import git_backup_writer as writer
from . import work_session_bundle as bundle
from . import work_session_execution as execution
from .work_session_binding import WorkSessionBinding


_RECEIPT_PATH = re.compile(r"receipts/ops/exact-operations/([0-9a-f]{64})\.json")
# Bound the expensive authenticated claim scans. v0.4.53 (beta letter 177): the
# budget counts only receipts whose own original decision names the selected
# session (a cheap, unauthenticated read of the receipt and its manifest). A
# large archive's receipts from other activities and sessions are excluded as
# ownership-unverified without the expensive proof and never consume the
# budget; they could not be selected anyway. Exceeding the budget still fails
# the whole classification; it is not truncation.
_MAX_RECEIPT_CANDIDATES = 512


class WorkSessionGitProvenanceError(RuntimeError):
    """Fixed-code errors; rejected private input is never retained as context."""

    def __init__(self, code="work_session_git_provenance_invalid", *, cause_code=None):
        self.code = code if type(code) is str and code in {
            "work_session_git_provenance_invalid", "work_session_git_snapshot_unavailable",
            "work_session_git_snapshot_changed", "work_session_git_receipt_limit",
        } else "work_session_git_provenance_invalid"
        # Letter 173 C: the ordinary plan's fixed blocker code, never free text.
        self.cause_code = cause_code if type(cause_code) is str and SAFE_CAUSE_CODE_RE.fullmatch(cause_code) else None
        super().__init__(self.code)


SAFE_CAUSE_CODE_RE = re.compile(r"[a-z][a-z0-9_]{0,95}")


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
        return "<private authenticated-output Git selection; not approval>"

    def _private_document(self):
        return json.loads(self._raw)

    def public_summary(self):
        data = self._private_document()
        partition = data["selection"]
        selected = sum(len(group["change_refs"]) for group in partition["selected_groups"])
        exclusions = partition["excluded_changes"]
        result = {
            "status": "receipt_selection_classified" if selected else "no_eligible_receipts",
            "selected_receipt_count": selected,
            "excluded_change_count": len(exclusions),
            "other_session_receipt_count": sum(row["scope"] == "other_session" for row in exclusions),
            "ownership_unverified_count": sum(row["scope"] == "unknown" for row in exclusions),
            "unverified_receipt_candidate_count": data["unverified_receipt_candidates"],
            # v0.4.53: receipts whose original decision names another session;
            # excluded without the expensive proof (ownership not verified).
            "other_session_hint_receipt_count": data.get("other_session_hint_receipts", 0),
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
        selected_refs = {ref for group in partition["selected_groups"] for ref in group["change_refs"]}
        intake = [proof for proof in data["proofs"]
                  if proof["producer"] in ("authenticated_source_intake_batch_output",
                                           "authenticated_source_intake_record_output")]
        documents = [proof for proof in data["proofs"]
                     if proof["producer"] == "authenticated_local_recovery_document_output"
                     and proof["output_kind"] == "canonical_zettel_document"]
        intake_summary = data.get("intake_provenance_summary")
        document_summary = data.get("document_provenance_summary")
        selected_documents = [proof for proof in documents if proof["change_ref"] in selected_refs]
        link_summary = data.get("link_provenance_summary")
        link_outputs = [proof for proof in data["proofs"]
                        if proof["producer"] == "session_claimed_zettel_objet_link_output"
                        and proof["change_ref"] in selected_refs]
        linked_zettels = [proof for proof in link_outputs if proof["output_kind"] == "linked_zettel_document"]
        link_non_receipts = sum(proof["output_kind"] in ("linked_zettel_document", "zettel_link_before_snapshot")
                                for proof in link_outputs)
        if link_outputs or link_summary is not None:
            # v0.4.66 (letter 184): link outputs are counted on their own.
            result.update(
                status="session_output_selection_classified" if selected else "no_eligible_session_outputs",
                selected_output_count=selected,
                selected_receipt_count=selected - link_non_receipts,
                selected_link_output_count=len(link_outputs),
                selected_linked_zettel_count=len(linked_zettels),
                receipt_only=not link_non_receipts,
                document_provenance_evaluated=True,
                whole_document_ownership_verified=False,
                source_bytes_backed_up=False, artifact_capture_performed=False,
            )
            if link_summary is not None:
                result.update(
                    authenticated_link_approval_count=link_summary["authenticated_link_approval_count"],
                    accepted_link_receipt_count=link_summary["accepted_link_receipt_count"],
                    linked_zettel_candidate_count=link_summary["linked_zettel_candidate_count"],
                    linked_zettel_not_selected_count=link_summary["linked_zettel_not_selected_count"],
                )
        if intake or selected_documents or intake_summary is not None or document_summary is not None:
            selected_intake = [proof for proof in intake if proof["change_ref"] in selected_refs]
            requests = sum(proof["output_kind"] == "prepared_capture_request" for proof in selected_intake)
            other_requests = sum(proof["output_kind"] == "prepared_capture_request"
                                 and proof["change_ref"] not in selected_refs for proof in intake)
            other_documents = sum(proof["change_ref"] not in selected_refs for proof in documents)
            result.update(
                status="session_output_selection_classified" if selected else "no_eligible_session_outputs",
                selected_output_count=selected,
                selected_receipt_count=selected - requests - len(selected_documents) - link_non_receipts,
                selected_intake_output_count=len(selected_intake), selected_document_count=len(selected_documents),
                receipt_only=not requests and not selected_documents and not link_non_receipts,
                other_session_output_count=result["other_session_receipt_count"],
                other_session_receipt_count=result["other_session_receipt_count"] - other_requests - other_documents,
                source_bytes_backed_up=False, artifact_capture_performed=False,
                document_provenance_evaluated=bool(documents or document_summary is not None),
                whole_document_ownership_verified=False,
            )
            if intake_summary is not None:
                result.update(
                    intake_context_count=intake_summary["context_hint_count"],
                    authenticated_intake_original_count=intake_summary["authenticated_original_count"],
                    unverified_intake_context_count=intake_summary["unverified_context_hint_count"],
                )
            if document_summary is not None:
                result.update(
                    document_control_count=document_summary["document_control_count"],
                    authenticated_recovery_count=document_summary["authenticated_recovery_count"],
                    unverified_document_control_count=document_summary["unverified_document_control_count"],
                    overlapping_document_count=document_summary["overlapping_document_count"],
                )
        return result


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
        blockers = plan.get("blockers") if isinstance(plan.get("blockers"), list) else []
        cause = next((code for code in blockers if type(code) is str and SAFE_CAUSE_CODE_RE.fullmatch(code)), None)
        if cause == "changed_path_attribute_state_unavailable":
            cause = next((code for code in blockers if type(code) is str
                          and code.startswith("changed_path_attribute_")
                          and code != cause and SAFE_CAUSE_CODE_RE.fullmatch(code)), cause)
        raise WorkSessionGitProvenanceError("work_session_git_snapshot_unavailable",
                                            cause_code=cause or ("git_backup_plan_inspection_incomplete"
                                                                 if plan.get("inspection_complete") is not True else None))
    capture["root"] = str(capture["root"])
    return _canonical({"plan_sha256": plan["plan_sha256"], "capture": capture, "options": options})


def _safe_failure(call):
    # Raise outside the handler so private exception data cannot survive in
    # __context__/__cause__, including callbacks and OS errors carrying paths.
    failure, cause = None, None
    try:
        return call()
    except WorkSessionGitProvenanceError as exc:
        failure, cause = exc.code, exc.cause_code
    except Exception:
        failure = "work_session_git_provenance_invalid"
    raise WorkSessionGitProvenanceError(failure, cause_code=cause)


def _capture_git_snapshot_held(
    archive_root, *, held, remote_name="origin", branch=None,
    credential_mode="stored", max_changes=planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGES,
    max_changed_bytes=planning.GIT_BACKUP_PLAN_DEFAULT_MAX_CHANGED_BYTES,
    inspection_paths=None,
) -> _GitChangeSnapshot:
    """Capture only a successful complete existing plan under the archive lock."""
    def capture():
        store, _archive_id = execution._store(archive_root)
        options = dict(remote_name=remote_name, branch=branch, credential_mode=credential_mode,
                       max_changes=max_changes, max_changed_bytes=max_changed_bytes)
        if inspection_paths is not None:
            options["_inspection_paths"] = list(inspection_paths)
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


def _receipt_session_hint(store, held, execution_sha):
    """The session a completion receipt's original decision names, or None.

    Unauthenticated and read-only: it only narrows which receipts receive the
    expensive proof. It never selects a change and never establishes
    ownership; a receipt whose hint names another session is excluded as
    ownership-unverified. The full proof reads the same original binding, so
    a receipt the proof would attribute to this session always has a matching
    hint.
    """
    try:
        receipt = exact.load_exact_operation_final_receipt_read_only(
            store.root, execution_sha, heartbeat=held.verify_held,
        )
        if receipt is None:
            return None
        bound = bundle.load_context_bound_session_decision(
            store, manifest_sha256=receipt["result"]["manifest_sha256"])
        binding = bound.prepared.manifest.work_session_binding
        return None if binding is None else _session_identity(binding)
    except Exception:
        return None


def _authenticated_inspection_paths_held(archive_root, *, held, selected_binding,
                                       branch=None, key_provider=None):
    """Discover owned output paths before observing changed file bodies.

    Paths come from authenticated producer output maps or completed exact
    decisions. They are candidates to inspect, not permission to commit. The
    normal selector still compares actual bytes to each original proof later.
    In particular an owned file that grew beyond the content budget stays in
    this set and raises the normal size blocker instead of being omitted.
    """
    def discover():
        if type(selected_binding) is not WorkSessionBinding:
            raise WorkSessionGitProvenanceError()
        store, _archive_id = execution._store(archive_root)
        store._require_held_lock(held)
        if selected_binding.archive_identity_sha256 != store.archive_identity_sha256:
            raise WorkSessionGitProvenanceError()
        from . import work_session_intake_git_provenance as intake
        from . import work_session_local_recovery_git_provenance as documents
        from . import work_session_link_git_provenance as links
        owned, producer_paths = set(), set()
        for module in (intake, documents, links):
            inventory = module._authenticated_output_inventory_held(
                store.root, held, selected_binding, key_provider)
            origins, outputs = inventory[:2]
            producer_paths.update(outputs)
            for path, (key, _output) in outputs.items():
                original = WorkSessionBinding.from_document(origins[key]["work_session_binding"])
                if _session_identity(original) == _session_identity(selected_binding):
                    owned.add(path)
        # Structural Git metadata is bounded independently of content budgets.
        # An empty inspection set performs no changed-path attribute/hash/blob
        # inspection. It only supplies exact receipt discovery hints.
        pinned = planning._pin_git_executable()
        if pinned is None:
            raise WorkSessionGitProvenanceError("work_session_git_snapshot_unavailable",
                                                cause_code="git_executable_unavailable_or_unsafe")
        token = planning._PINNED_GIT_EXECUTABLE.set(pinned)
        try:
            state, blockers = planning._structural_snapshot(
                store.root, branch=branch, inspection_paths=())
            if state is None or blockers:
                raise WorkSessionGitProvenanceError("work_session_git_snapshot_unavailable",
                    cause_code=next(iter(blockers), "git_metadata_snapshot_unavailable"))
            wanted = _session_identity(selected_binding)
            paths = set()
            # v0.4.65 (letter 184): the changed-path roles and the number of
            # receipt candidates are reported, content-free, by the preview.
            from . import work_session_git_coverage as coverage
            coverage.record_changed_paths(row.path for row in state["all_status"])
            receipt_candidates = sorted(row.path for row in state["all_status"]
                                        if _RECEIPT_PATH.fullmatch(row.path) and row.path not in producer_paths)
            coverage.add_total(len(receipt_candidates))
            for candidate in receipt_candidates:
                held.verify_held()
                coverage.tick()
                hint = _receipt_session_hint(
                    store, held, "sha256:" + _RECEIPT_PATH.fullmatch(candidate)[1])
                if hint == wanted:
                    paths.add(candidate)
            if len(paths) > _MAX_RECEIPT_CANDIDATES:
                raise WorkSessionGitProvenanceError("work_session_git_receipt_limit")
            coverage.add_total(len(paths))
            for path in sorted(paths):
                held.verify_held()
                coverage.tick()
                execution_sha = "sha256:" + _RECEIPT_PATH.fullmatch(path)[1]
                try:
                    receipt = exact.load_exact_operation_final_receipt_read_only(
                        store.root, execution_sha, heartbeat=held.verify_held)
                    if receipt is None:
                        continue
                    raw = exact._canonical_json_bytes(receipt) + b"\n"
                    row = {"public_observation": {"change_ref": "change:000001", "worktree": {
                        "bytes": len(raw), "sha256": "sha256:" + hashlib.sha256(raw).hexdigest()}}}
                    proof = _authenticated_receipt(store, held, row, execution_sha, key_provider=key_provider)
                    if proof is not None and _session_identity(WorkSessionBinding.from_document(
                            proof["original_work_session_binding"])) == _session_identity(selected_binding):
                        owned.add(path)
                except Exception:
                    # Unauthenticated hints never establish ownership.
                    continue
            if planning._pin_git_at(Path(pinned.path)) != pinned:
                raise WorkSessionGitProvenanceError("work_session_git_snapshot_changed")
        finally:
            planning._PINNED_GIT_EXECUTABLE.reset(token)
        store._require_held_lock(held)
        return tuple(sorted(owned))
    return _safe_failure(discover)


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
        from . import work_session_intake_git_provenance as intake_provenance
        intake_selection = intake_provenance._select_intake_output_changes_held(
            store.root, held=held, snapshot=snapshot, selected_binding=binding, key_provider=key_provider,
        )
        intake_data = intake_selection._private_document()
        intake_proofs = {proof["change_ref"]: proof for proof in intake_data["proofs"]}
        if len(intake_proofs) != len(intake_data["proofs"]):
            raise WorkSessionGitProvenanceError()
        from . import work_session_local_recovery_git_provenance as document_provenance
        document_selection = document_provenance._select_document_changes_held(
            store.root, held=held, snapshot=snapshot, selected_binding=binding, key_provider=key_provider,
        )
        document_data = document_selection._private_document()
        document_proofs = {proof["change_ref"]: proof for proof in document_data["proofs"]}
        if len(document_proofs) != len(document_data["proofs"]) or set(document_proofs) & set(intake_proofs):
            raise WorkSessionGitProvenanceError()
        # v0.4.66 (letter 184): this session's zettel-objet link outputs.
        from . import work_session_link_git_provenance as link_provenance
        link_selection = link_provenance._select_link_changes_held(
            store.root, held=held, snapshot=snapshot, selected_binding=binding, key_provider=key_provider,
        )
        link_data = link_selection._private_document()
        link_proofs = {proof["change_ref"]: proof for proof in link_data["proofs"]
                       if proof["change_ref"] not in intake_proofs and proof["change_ref"] not in document_proofs}
        # Intake outputs and recovery documents are authenticated once per
        # original, not once per changed output or by falling through the
        # human-decision parser.
        wanted = _session_identity(binding)
        own_receipt_refs, other_hint_refs = set(), set()
        from . import work_session_git_coverage as coverage
        coverage.add_total(2 * len(rows))
        for row in rows:
            coverage.tick()
            change_ref = row["public_observation"]["change_ref"]
            match = _RECEIPT_PATH.fullmatch(row["path"])
            if (match is None or change_ref in intake_proofs or change_ref in document_proofs
                    or change_ref in link_proofs):
                continue
            store._require_held_lock(held)
            hint = _receipt_session_hint(store, held, "sha256:" + match[1])
            if hint == wanted:
                own_receipt_refs.add(change_ref)
            elif hint is not None:
                other_hint_refs.add(change_ref)
        if len(own_receipt_refs) > _MAX_RECEIPT_CANDIDATES:
            raise WorkSessionGitProvenanceError("work_session_git_receipt_limit")
        selected, excluded, proofs, unverified = [], [], [], 0
        for row in rows:
            store._require_held_lock(held)
            coverage.tick()
            change_ref = row["public_observation"]["change_ref"]
            match = _RECEIPT_PATH.fullmatch(row["path"])
            proof = (intake_proofs.get(change_ref) or document_proofs.get(change_ref)
                     or link_proofs.get(change_ref))
            if (proof is None and match is not None and change_ref in own_receipt_refs
                    and _new_whole_receipt(row)):
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
        has_selected_intake = any(row["public_observation"]["change_ref"] in intake_proofs for row in selected)
        has_selected_document = any(
            row["public_observation"]["change_ref"] in document_proofs
            and document_proofs[row["public_observation"]["change_ref"]]["output_kind"] == "canonical_zettel_document"
            for row in selected)
        has_selected_link = any(row["public_observation"]["change_ref"] in link_proofs for row in selected)
        subject = ("Back up authenticated session documents and outputs" if has_selected_document
                   else "Back up this session's zettel-objet links" if has_selected_link
                   else "Back up authenticated session outputs" if has_selected_intake
                   else "Back up authenticated session receipts")

        def flush_group():
            if group_rows:
                groups.append({"group_id": "group:session-receipts-" + str(len(groups) + 1).zfill(6),
                               "change_refs": sorted(row["public_observation"]["change_ref"] for row in group_rows),
                               "commit_subject": subject})
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
        result = {
            "selection": partition, "proofs": proofs,
            "selected_identity_binding": binding.document(),
            "unverified_receipt_candidates": unverified,
            "other_session_hint_receipts": len(other_hint_refs),
        }
        if intake_data["hint_inventory_state"] == "present":
            result["intake_provenance_summary"] = intake_selection.public_summary()
        if document_data["control_inventory_state"] == "present":
            result["document_provenance_summary"] = document_selection.public_summary()
        if link_data["approval_count"]:
            result["link_provenance_summary"] = link_selection.public_summary()
        return _ReceiptSelection(_canonical(result))
    return _safe_failure(select)
