"""Read-only connection between scoped handoff and authenticated cleanup evidence."""
from . import activity_cleanup as cleanup


def _preservation_recorded(item, journal):
    proof = journal.read("item-" + str(item["number"]) + "-preserved")
    return bool(proof and proof.get("object_id") == item["object_id"]
                and proof.get("size") == item["state"]["size"]
                and proof.get("state") == "remote_verified"
                and proof.get("source_link_preserved") is True)


def _plain_summary(required, verified, body_missing, stream_missing, unknown):
    if verified == required:
        return f"All {required} preserved items have verified backup evidence."
    parts = [f"{verified} of {required} preserved items have verified backup evidence."]
    if body_missing:
        parts.append(f"{body_missing} have no verified body backup receipt.")
    if stream_missing:
        parts.append(f"{stream_missing} had extra Windows data streams whose backup is not recorded.")
    if unknown:
        parts.append(
            f"{unknown} were deleted by an older WOM in a way that recorded no proof of whether they carried extra "
            "Windows data streams; their bodies are backed up and their originals are already gone, so this cannot "
            "be determined now. It is reported, not assumed empty."
        )
    return " ".join(parts)


def evidence(root, request_paths):
    rows = []
    for ordinal, path in enumerate(request_paths):
        try:
            candidate = cleanup.plan(root, path, resume=True)
            state = cleanup.status(candidate)
            material, journal = candidate["material"], candidate["journal"]
            backup_required = [item for item in material["items"] if item["disposition"] == "preserve"]
            preserved = 0
            # v0.4.61 (letter 181 A): say how each item's alternate-stream
            # state is proven, and count what cannot be proven, instead of
            # accepting only an empty recorded inventory.
            guard_deleted = cleanup.guard_deleted_numbers(journal, material)
            by_basis, unknown, body_missing, stream_missing = {}, [], 0, 0
            for item in backup_required:
                if not _preservation_recorded(item, journal):
                    body_missing += 1
                    continue
                basis = cleanup.stream_evidence_basis(journal, item, guard_deleted)
                if basis is None:
                    unknown.append(item["number"])
                    continue
                if basis in {"stream_backup_missing", "stream_evidence_changed"}:
                    stream_missing += 1
                    continue
                by_basis[basis] = by_basis.get(basis, 0) + 1
                preserved += 1
            directories_done = all(not cleanup.os.path.lexists(item["path"]) for item in material["directories"])
            effects_done = (state["counts"]["completed"] == len(material["items"])
                and directories_done and state["remaining"]["changed_root_count"] == 0)
            complete = effects_done and preserved == len(backup_required)
            # v0.4.61 (letter 181 A): the only shortfall is that older records
            # cannot prove the stream state of already deleted items.
            legacy_boundary_only = bool(not complete and effects_done and unknown
                                        and preserved + len(unknown) == len(backup_required))
            rows.append({"request_number": ordinal, "state": "complete" if complete else "partial",
                "legacy_stream_boundary_only": legacy_boundary_only,
                "intent_sha256": cleanup.digest(material), "cleanup_counts": state["counts"],
                "recorded_backup": {"required_items": len(backup_required), "verified_preservation_receipts": preserved,
                    "verified_by_basis": dict(sorted(by_basis.items())),
                    "body_receipt_missing_count": body_missing,
                    "stream_backup_missing_count": stream_missing,
                    "legacy_stream_state_unknown_count": len(unknown),
                    "legacy_stream_state_unknown_items": unknown[:200],
                    "plain_summary": _plain_summary(len(backup_required), preserved, body_missing, stream_missing, len(unknown)),
                    "remote_bytes_verified_now": False, "git_remote_ref_verified_now": False},
                "requested_directories_removed": directories_done,
                "remaining": state["remaining"], "reason_code": None,
                "unselected_remaining_files_are_not_included_in_completion": True})
        except (cleanup.ActivityCleanupError, OSError, ValueError, KeyError, TypeError):
            rows.append({"request_number": ordinal, "state": "development_wait",
                "reason_code": "activity_closeout_original_evidence_unavailable",
                "next_action": "inspect_original_activity_status_without_repeating_completed_effects"})
    state = "development_wait" if any(r["state"] == "development_wait" for r in rows) else (
        "complete" if rows and all(r["state"] == "complete" for r in rows) else "partial")
    return {"schema": "wom-kit/activity-closeout-evidence/v1", "state": state, "requests": rows,
        "evidence_sha256": cleanup.digest(rows), "writes_performed": False, "private_values_echoed": False,
        "completion_scope": "explicit_cleanup_requests_and_requested_directories",
        "whole_archive_completion_claimed": False, "customer_acceptance_confirmed": False}
