"""Read-only connection between scoped handoff and authenticated cleanup evidence."""
from . import activity_cleanup as cleanup


def _preservation_recorded(item, journal):
    proof = journal.read("item-" + str(item["number"]) + "-preserved")
    return bool(proof and proof.get("object_id") == item["object_id"]
                and proof.get("size") == item["state"]["size"]
                and proof.get("state") == "remote_verified"
                and proof.get("source_link_preserved") is True)


def evidence(root, request_paths):
    rows = []
    for ordinal, path in enumerate(request_paths):
        try:
            candidate = cleanup.plan(root, path, resume=True)
            state = cleanup.status(candidate)
            material, journal = candidate["material"], candidate["journal"]
            backup_required = [item for item in material["items"] if item["disposition"] == "preserve"]
            preserved = 0
            for item in backup_required:
                if not _preservation_recorded(item, journal):
                    continue
                streams = journal.read("item-" + str(item["number"]) + "-streams")
                if item.get("alternate_streams"):
                    if (not streams or streams.get("parent_object_id") != item["object_id"]
                            or streams.get("streams") != item["alternate_streams"]
                            or not isinstance(streams.get("item"), dict)
                            or not _preservation_recorded(streams["item"], journal)):
                        continue
                elif "alternate_streams" not in item:
                    inventory = journal.read("item-" + str(item["number"]) + "-stream-inventory")
                    if not inventory or inventory.get("object_id") != item["object_id"] or inventory.get("streams"):
                        continue
                preserved += 1
            directories_done = all(not cleanup.os.path.lexists(item["path"]) for item in material["directories"])
            complete = (state["counts"]["completed"] == len(material["items"])
                and preserved == len(backup_required) and directories_done
                and state["remaining"]["changed_root_count"] == 0)
            rows.append({"request_number": ordinal, "state": "complete" if complete else "partial",
                "intent_sha256": cleanup.digest(material), "cleanup_counts": state["counts"],
                "recorded_backup": {"required_items": len(backup_required), "verified_preservation_receipts": preserved,
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
