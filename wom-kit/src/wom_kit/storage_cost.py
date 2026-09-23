"""Capacity and planning estimates, never a claim about an account invoice."""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
import re

SOURCE = "https://developers.cloudflare.com/r2/pricing/"
AS_OF = "2026-09-23"
GB = 1_000_000_000


def estimate(*, remote_bytes, class_a=0, class_b=0, provider_kind="cloudflare-r2", storage_class="standard"):
    if any(type(value) is not int or value < 0 for value in (remote_bytes, class_a, class_b)):
        raise ValueError("storage_cost_nonnegative_integer_required")
    if provider_kind != "cloudflare-r2" or storage_class != "standard":
        return {"available": False, "reason": "provider_or_storage_class_rate_not_configured",
            "account_free_allowance_remaining_known": False}
    monthly = Decimal(remote_bytes) / GB
    a, b = Decimal(class_a) / 1_000_000, Decimal(class_b) / 1_000_000
    return {"available": True, "currency": "USD", "source": SOURCE, "rates_as_of": AS_OF,
        "provider_kind": provider_kind, "storage_class": storage_class,
        "remote_gb_month_assumed": float(monthly),
        "monthly_storage_usd_before_free_allowance": float(monthly.to_integral_value(rounding=ROUND_CEILING) * Decimal("0.015")),
        "planned_class_a_requests": class_a, "planned_class_b_requests": class_b,
        "request_usage_usd_before_rounding": float(a * Decimal("4.50") + b * Decimal("0.36")),
        "request_usd_if_billed_as_separate_usage": float(a.to_integral_value(rounding=ROUND_CEILING) * Decimal("4.50") + b.to_integral_value(rounding=ROUND_CEILING) * Decimal("0.36")),
        "account_free_allowance_remaining_known": False, "free_allowance_subtracted": False,
        "actual_account_invoice_estimated": False,
        "assumptions": ["Projected bytes remain for a full month; actual storage uses daily peaks.",
            "Decimal GB, whole billing-unit rounding; account-wide usage and remaining free quota are unknown.",
            "Request counts are this plan's no-retry estimate; retries and other account traffic are separate.",
            "Standard storage only; other classes need their own retrieval and retention rates."]}


def estimate_capacity(capacity_summary, *, class_a=0, class_b=0, provider_kind="cloudflare-r2"):
    """Refuse a total-cost figure when the manifest coverage is incomplete."""
    if (not isinstance(capacity_summary, dict)
        or capacity_summary.get("estimate_coverage") != "complete"
        or capacity_summary.get("scan_complete") is False):
        return {"available": False, "reason": "capacity_inventory_incomplete",
            "known_remote_bytes_lower_bound": (capacity_summary or {}).get("projected_remote_bytes"),
            "account_free_allowance_remaining_known": False, "actual_account_invoice_estimated": False}
    return estimate(remote_bytes=capacity_summary["projected_remote_bytes"], class_a=class_a,
        class_b=class_b, provider_kind=provider_kind)


def capacity(root, groups, *, provider_kind=None, store_ref=None, planned_uploads=(), offloadable_bytes=None, receipt_cache=None):
    from . import archive_services as services
    total = local = remote = local_only = unknown = 0
    known_remote = set()
    cache = receipt_cache if receipt_cache is not None else {}
    archive_id = services.read_archive_id(root)
    for oid, rows in groups.items():
        if not isinstance(oid, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", oid):
            unknown += 1
            continue
        sizes = {row.get("size_bytes") for row in rows if type(row.get("size_bytes")) is int and row["size_bytes"] >= 0}
        if len(sizes) != 1 or any(type(row.get("size_bytes")) is not int for row in rows):
            unknown += 1
            continue
        size = next(iter(sizes))
        total += size
        has_local = has_remote = False
        for row in rows:
            for location in row.get("locations", []) if isinstance(row.get("locations"), list) else []:
                if not isinstance(location, dict):
                    continue
                if location.get("provider") == "local" and location.get("availability") == "available":
                    has_local = True
                if (location.get("provider") == "object_storage" and location.get("availability") == "wom_uploaded"
                    and (provider_kind is None or location.get("provider_kind") == provider_kind)
                    and (store_ref is None or location.get("store_ref") == store_ref)):
                    codes, _ = services.backup_evidence_receipt_validation_codes(root, archive_id=archive_id,
                        object_id=oid, location=location, receipt_cache=cache)
                    if not codes:
                        has_remote = True
        local += size if has_local else 0
        remote += size if has_remote else 0
        local_only += size if has_local and not has_remote else 0
        if has_remote:
            known_remote.add(oid)
    additions, conflicting_uploads = {}, set()
    for oid, size in planned_uploads:
        if (not isinstance(oid, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", oid)
            or type(size) is not int or size < 0):
            unknown += 1
            continue
        if oid in known_remote:
            continue
        if oid in additions and additions[oid] != size:
            conflicting_uploads.add(oid)
        else:
            additions[oid] = size
    for oid in conflicting_uploads:
        additions.pop(oid, None)
    unknown += len(conflicting_uploads)
    return {"unique_object_bytes": total, "local_recorded_bytes": local,
        "local_only_bytes": local_only, "remote_preserved_bytes_at_recorded_time": remote,
        "offloadable_bytes_pending_live_verification": offloadable_bytes,
        "projected_remote_bytes": remote + sum(additions.values()), "unknown_or_conflicting_object_count": unknown,
        "estimate_coverage": "complete" if unknown == 0 else "incomplete",
        "deduplicated_by_object_id": True, "current_remote_availability_checked": False,
        "local_bytes_rehashed_for_this_summary": False, "evidence_basis": "manifest and validated recorded-time upload receipts"}
