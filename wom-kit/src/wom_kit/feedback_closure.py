"""Read-only, per-outcome closure checks; letter delivery is not implementation.

The private request ledger names required scenarios and byte-bound evidence.
Reports are observations, never permission to change customer acceptance or to
silently close sibling requests. A recurrence explicitly reopens its ancestor.
"""
from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path

SCHEMA = "wom-kit/feedback-request-ledger/v1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_SHA = re.compile(r"(?:sha256:)?[a-f0-9]{64}")
_COMMIT = re.compile(r"[a-f0-9]{40}")


class FeedbackClosureError(ValueError):
    def __init__(self):
        super().__init__("feedback_closure_input_invalid")
        self.code = "feedback_closure_input_invalid"


def _read(path: Path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or getattr(info, "st_file_attributes", 0) & 0x400:
        raise FeedbackClosureError()
    if info.st_size > 16 * 1024 * 1024:
        raise FeedbackClosureError()
    return path.read_bytes()


def _evidence_bytes(base, reference):
    if type(reference) is not dict or set(reference) != {"path", "sha256"}:
        raise FeedbackClosureError()
    name, digest = reference["path"], reference["sha256"]
    if type(name) is not str or type(digest) is not str or not _SHA.fullmatch(digest):
        raise FeedbackClosureError()
    relative = Path(name)
    if relative.is_absolute() or relative.drive or ".." in relative.parts or ":" in name:
        raise FeedbackClosureError()
    current = base
    for part in relative.parts:
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise FeedbackClosureError()
    raw = _read(current)
    if hashlib.sha256(raw).hexdigest() != digest.removeprefix("sha256:"):
        raise FeedbackClosureError()
    return raw


def _evidence(base, reference):
    value = json.loads(_evidence_bytes(base, reference))
    if type(value) is not dict:
        raise FeedbackClosureError()
    return value


def check(ledger_path: Path | str):
    """Check every criterion against installed-flow and public-release evidence."""
    try:
        path = Path(ledger_path)
        raw = _read(path)
        ledger = json.loads(raw.decode("utf-8-sig"))
        requests = ledger["requests"]
        if ledger.get("schema") != SCHEMA or type(requests) is not list or not requests:
            raise FeedbackClosureError()
        by_id = {}
        for row in requests:
            identity = row.get("request_id") if type(row) is dict else None
            if type(identity) is not str or not _ID.fullmatch(identity) or identity in by_id:
                raise FeedbackClosureError()
            criteria = row.get("criteria")
            if type(criteria) is not list or not criteria or any(type(item) is not str or not _ID.fullmatch(item) for item in criteria) or len(set(criteria)) != len(criteria):
                raise FeedbackClosureError()
            if type(row.get("original_requirement")) is not str or not row["original_requirement"].strip():
                raise FeedbackClosureError()
            by_id[identity] = row
        descendants = {identity: [] for identity in by_id}
        for row in requests:
            predecessor = row.get("recurrence_of")
            if predecessor is not None:
                if predecessor not in by_id or predecessor == row["request_id"]:
                    raise FeedbackClosureError()
                descendants[predecessor].append(row["request_id"])
        # A recurrence chain must not contain cycles, regardless of row order.
        def visit(identity, ancestors):
            if identity in ancestors:
                raise FeedbackClosureError()
            for child in descendants[identity]:
                visit(child, ancestors | {identity})
        for identity in by_id:
            visit(identity, set())
        output = []
        for identity, row in by_id.items():
            missing, verified = [], []
            reports = {}
            for ref in row.get("verification", []):
                report = _evidence(path.parent, ref)
                criterion = report.get("criterion_id")
                if criterion in reports:
                    raise FeedbackClosureError()
                reports[criterion] = report
            release = _evidence(path.parent, row["release"]) if row.get("release") else None
            for criterion in row["criteria"]:
                report = reports.get(criterion)
                valid = bool(report and report.get("schema") == "wom-kit/feedback-flow-evidence/v1"
                    and report.get("request_id") == identity and report.get("ok") is True
                    and report.get("execution_kind") == "installed_product"
                    and report.get("exit_code") == 0 and report.get("actual_effect_verified") is True
                    and type(report.get("commit")) is str and _COMMIT.fullmatch(report["commit"])
                    and type(report.get("wheel_sha256")) is str and _SHA.fullmatch(report["wheel_sha256"]))
                (verified if valid else missing).append(criterion)
            released = bool(not missing and release
                and release.get("schema") == "wom-kit/feedback-release-evidence/v1"
                and release.get("public_download_verified") is True
                and release.get("fresh_install_verified") is True
                and release.get("tag_commit_verified") is True
                and type(release.get("version")) is str and release["version"]
                and all(report.get("commit") == release.get("commit")
                    and report.get("wheel_sha256") == release.get("wheel_sha256")
                    for name, report in reports.items() if name in row["criteria"]))
            product_complete = released
            claims = row.get("reply_claim", "not_resolved")
            if claims not in {"resolved", "partially_resolved", "not_resolved"}:
                raise FeedbackClosureError()
            reply_verified = False
            if row.get("reply_evidence"):
                reply = _evidence(path.parent, row["reply_evidence"])
                reply_bytes = _evidence_bytes(path.parent, reply["reply_file"])
                reply_verified = bool(reply_bytes.strip()
                    and reply.get("schema") == "wom-kit/feedback-reply-evidence/v1"
                    and reply.get("claims", {}).get(identity) == claims
                    and reply.get("claims_reviewed_against_body") is True)
            acceptance = row.get("customer_confirmation", "pending")
            if acceptance not in {"pending", "confirmed", "failed"}:
                raise FeedbackClosureError()
            customer_verified = False
            if row.get("customer_evidence"):
                customer = _evidence(path.parent, row["customer_evidence"])
                customer_verified = bool(
                    customer.get("schema") == "wom-kit/feedback-customer-evidence/v1"
                    and customer.get("request_id") == identity
                    and customer.get("outcome") == acceptance
                    and customer.get("source") == "customer_report"
                    and customer.get("version") == (release or {}).get("version")
                    and _evidence_bytes(path.parent, customer["report_file"]).strip())
            if acceptance == "confirmed" and not customer_verified:
                acceptance = "pending"
            output.append({"request_id": identity, "verified_criteria": verified,
                "missing_criteria": missing, "implementation_verified": not missing,
                "release_verified": released, "reopened_by_recurrence": False,
                "product_complete": product_complete, "customer_confirmation": acceptance,
                "customer_evidence_verified": customer_verified, "reply_evidence_verified": reply_verified,
                "reply_claim": claims, "reply_overclaims": claims == "resolved" and not product_complete,
                "state": "reopened" if acceptance == "failed" else (
                    "customer_confirmed" if product_complete and acceptance == "confirmed" else
                    "released_customer_pending" if product_complete else "open"),
                "remaining_actions": (["implement_or_verify_missing_criteria"] if missing else [])
                    + (["verify_public_release_of_tested_bytes"] if not released else [])
                    + (["verify_reply_claims_against_current_body"] if not reply_verified else [])})
        results = {item["request_id"]: item for item in output}
        def unresolved_descendant(identity):
            return any(not results[child]["product_complete"]
                or results[child]["customer_confirmation"] == "failed"
                or unresolved_descendant(child) for child in descendants[identity])
        for item in output:
            if unresolved_descendant(item["request_id"]):
                item.update(product_complete=False, reopened_by_recurrence=True, state="reopened")
                item["remaining_actions"].append("resolve_recurrence")
            item["reply_overclaims"] = item["reply_claim"] == "resolved" and not item["product_complete"]
        return {"schema": "wom-kit/feedback-closure-check/v1", "read_only": True,
            "ok": all(row["product_complete"] and row["reply_evidence_verified"] and not row["reply_overclaims"] for row in output),
            "ledger_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(), "requests": output,
            "summary": {"total": len(output), "product_complete": sum(row["product_complete"] for row in output),
                "open": sum(not row["product_complete"] for row in output),
                "reply_overclaims": sum(row["reply_overclaims"] for row in output)},
            "letter_delivery_is_closure": False, "customer_acceptance_inferred": False,
            "private_values_echoed": False, "paths_echoed": False}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise FeedbackClosureError() from None
