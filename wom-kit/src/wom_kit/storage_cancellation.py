"""Content-free cancellation results for checkpointed storage operations.

Call checkpoint only at a domain boundary, never from progress/heartbeat or
inside a provider request. The existing signed cancellation record is the
authority for acknowledgement; exact-operation evidence remains resumable.
"""
from .exact_operation_manifest import exact_operation_execution_sha256


def is_cancelled(error):
    return (getattr(error, "cause_code", None) or getattr(error, "code", None)) == "operation_cancelled_at_checkpoint"


def exact_result(*, schema, manifest, authority, checkpoints, durable_receipt_count):
    execution = exact_operation_execution_sha256(manifest, approval_authority=authority)
    rows = checkpoints.load(execution, heartbeat=lambda: None)
    checkpointed_items = len({row["item_ordinal"] for row in rows if row["stage"] == "item_verified"})
    return {
        "schema_version": schema, "ok": False, "state": "cancelled_at_checkpoint",
        "cause_code": "operation_cancelled_at_checkpoint", "cause_stage": "domain_writer",
        "reason_codes": ["operation_cancelled_at_checkpoint"],
        "blockers": ["operation_cancelled_at_checkpoint"],
        "cancel_requested": True, "cancel_acknowledged": True,
        "process_killed": False, "provider_request_in_flight": False,
        "manifest_sha256": manifest.manifest_sha256, "execution_sha256": execution,
        "durable_terminal_receipt_count": durable_receipt_count,
        "checkpointed_item_count": checkpointed_items,
        "execution": {"status": "interrupted", "execution_sha256": execution,
                      "manifest_sha256": manifest.manifest_sha256, "checkpoint_count": len(rows)},
        "recovery": {"approval_id": authority.approval_id, "execution_sha256": execution,
                     "manifest_sha256": manifest.manifest_sha256,
                     "same_claim_resume_supported": bool(rows), "automatic_retry_allowed": False},
        "next_safe_actions": ["preserve_original_control_receipts_and_checkpoints", "resume_the_original_storage_execution"],
        "private_values_echoed": False, "remote_keys_echoed": False,
        "local_paths_echoed": False, "credential_values_echoed": False,
    }
