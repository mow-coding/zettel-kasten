"""Started exact-approval claims: read-only listing and reviewed finalize.

v0.4.30 (beta letter 163 ⑥): a domain writer that raised after its claim was
published leaves the claim ``started`` on purpose, and the client's archive
collected 27 such claims with no way to see or close them.  This module adds

* ``list_exact_human_approval_claims`` — a MAC-verified enumeration of the
  claim store that projects fixed fields only (never the reviewer id, the
  archive id or a path), and
* ``plan_exact_human_approval_claim_finalize`` /
  ``finalize_exact_human_approval_claims`` — the reviewed (dialog or session
  grant) closing of started claims through the same compare-and-swap finalizer as
  success, refused when any receipt under the archive references the claim,
  when the claim is younger than the minimum age (a writer may still be
  running) or when the claim belongs to ``project_version_update`` (its own
  ``--resume --abandon-started-approval`` path owns that store).

The failure code written is ``operator_closed_started_claim_after_review``,
deliberately not the v0.4.22 abandon code, so ordinary resume discovery never
treats a closed claim as absence.  Write evidence is receipts only: the
finalize receipt records exactly what was scanned.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .exact_human_approval import (
    CLAIMS_RELATIVE_ROOT,
    ExactHumanApprovalError,
    _ClaimedExactHumanApproval,
    _archive_identity,
    _authenticated_claim_document_core,
    _parse_timestamp,
    _validated_key,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_windows import ExactHumanApprovalOperation
from . import exact_human_approval_workflow as _workflow

LISTING_SCHEMA_VERSION = "wom-kit/exact-human-approval-claims-listing/v0.1"
FINALIZE_PLAN_SCHEMA_VERSION = "wom-kit/exact-approval-claim-finalize-plan/v0.1"
FINALIZE_RECEIPT_SCHEMA_VERSION = (
    "wom-kit/exact-human-approval-claim-finalize-receipt/v0.1"
)
FINALIZE_RECEIPTS_RELATIVE = "receipts/exact-human-approvals/claim-finalize"
FINALIZE_FAILURE_CODE = "operator_closed_started_claim_after_review"
DEFAULT_MIN_AGE_MINUTES = 30
MAX_FINALIZE_SET = 256
MAX_LISTED_CLAIMS = 100_000
# Receipt roots scanned for a reference to a selected claim; every JSON file
# below them is read leniently so no envelope shape or operation is missed.
EVIDENCE_SCAN_ROOTS = (
    ("receipts",),
    (".zettel-kasten", "receipts", "version-updates"),
)
_MAX_EVIDENCE_FILES = 500_000
# v0.4.32 (letter 164 ②): receipts are scanned as byte streams, so a 3 MB
# Doctor or title-remap receipt is read in full instead of counted as
# unreadable; only a file above this ceiling is skipped, and it is named.
_MAX_EVIDENCE_FILE_BYTES = 256 * 1024 * 1024
_EVIDENCE_CHUNK_BYTES = 1024 * 1024
_EVIDENCE_OVERLAP_BYTES = 64
_MAX_NAMED_EVIDENCE_PATHS = 16
_APPROVAL_ID_BYTES_RE = re.compile(rb"approval_[0-9a-f]{32}")
# Operations whose success always leaves a receipt under the scanned roots
# that names the claim; the letter-137 audit reads exactly these kinds.
RECEIPTED_OPERATIONS = frozenset(
    {
        "mint_zet",
        "mint_zet_batch",
        "retire_draft",
        "retire_draft_batch",
        "remint_reconcile",
        "retire_draft_reconcile",
        "ai_scratch_gc",
        "markup_normalization",
        "markup_normalization_revert",
        "markup_normalization_recovery",
        "zettel_objet_link_revert",
        "zettel_edge",
        "zettel_edge_batch",
        "zettel_edge_revert",
        "zettel_edge_batch_revert",
    }
)
STATUS_FILTERS = ("started", "succeeded", "failed", "all")

_APPROVAL_ID_RE = re.compile(r"^approval_[0-9a-f]{32}$")
_APPROVAL_ID_TOKEN_RE = re.compile(r"approval_[0-9a-f]{32}")
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,95}$")
_PLAN_DOMAIN = b"wom-kit/exact-approval-claim-finalize-plan/v0.1\x00"
_TARGET_DOMAIN = b"wom-kit/exact-approval-claim-finalize-target/v0.1\x00"


class ExactApprovalClaimsError(RuntimeError):
    """Fixed-code failure; caller text, paths and reviewer ids are discarded."""

    _CODES = frozenset(
        {
            "exact_approval_claim_argument_invalid",
            "exact_approval_claim_store_unavailable",
            "exact_approval_claim_key_unavailable",
            "exact_approval_claim_finalize_plan_mismatch",
            "exact_approval_claim_finalize_plan_blocked",
            "exact_approval_claim_finalize_claim_invalid",
            "exact_approval_claim_finalize_receipt_write_failed",
            "exact_approval_claim_finalize_lock_unavailable",
            "exact_approval_claim_finalize_state_unknown",
        }
    )

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "exact_approval_claim_store_unavailable"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"ExactApprovalClaimsError({self.code!r})"


def _fail(code: str) -> ExactApprovalClaimsError:
    return ExactApprovalClaimsError(code)


def _canonical_bytes(document: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            dict(document),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _sha256_of(domain: bytes, document: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(domain + _canonical_bytes(document)).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _string_codes(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if type(item) is str and _CODE_RE.fullmatch(item)]


# ---------------------------------------------------------------- listing


def _claims_boundary_default(archive_root: Path | str):
    """Bind the claim directory chain without creating recovery state."""

    from . import archive_services
    from contextlib import contextmanager

    @contextmanager
    def _boundary():
        canonical_root = archive_services.require_existing_archive_root(
            Path(archive_root)
        )
        claims_parent = canonical_root.joinpath(*Path(CLAIMS_RELATIVE_ROOT).parts)
        with archive_services._activity_group_bound_directory_chain(
            canonical_root,
            claims_parent,
            create=False,
        ) as claims_binding:
            yield canonical_root, claims_binding

    return _boundary


def _project_claim(
    parsed: Mapping[str, Any], *, clock: Callable[[], datetime]
) -> dict[str, Any]:
    """Fixed, content-free projection of one authenticated claim document."""

    context = parsed.get("context") if isinstance(parsed.get("context"), Mapping) else {}
    intent = (
        parsed.get("interactive_intent")
        if isinstance(parsed.get("interactive_intent"), Mapping)
        else {}
    )
    started_at = parsed.get("started_at")
    age_minutes: int | None = None
    try:
        started = _parse_timestamp(started_at)
        age_minutes = max(0, int((clock() - started).total_seconds() // 60))
    except (ExactHumanApprovalError, TypeError, ValueError):
        age_minutes = None
    operation = context.get("operation")
    presenter = parsed.get("session_presenter")
    presenter_recorded = isinstance(presenter, Mapping)
    return {
        "approval_id": parsed.get("approval_id"),
        "operation": operation if type(operation) is str else None,
        "status": parsed.get("status"),
        "started_at": started_at if type(started_at) is str else None,
        "finished_at": (
            parsed.get("finished_at")
            if type(parsed.get("finished_at")) is str
            else None
        ),
        "failure_code": (
            parsed.get("failure_code")
            if type(parsed.get("failure_code")) is str
            else None
        ),
        "age_minutes": age_minutes,
        "approval_mechanism": (
            intent.get("mechanism") if type(intent.get("mechanism")) is str else None
        ),
        "context_sha256": parsed.get("context_sha256"),
        "review_binding_codes": _string_codes(context.get("review_binding_codes")),
        "warning_codes": _string_codes(context.get("warning_codes")),
        # v0.4.34 (letter 165 [A]): which presenter used a session grant.
        "presenter_recorded": presenter_recorded,
        "session_presenter": (
            {
                "work_session_ref": presenter.get("work_session_ref"),
                "fingerprint_state": presenter.get("fingerprint_state"),
                "process_fingerprint_sha256": presenter.get("process_fingerprint_sha256"),
                "presenters_observed_before_this_claim": presenter.get("presenters_observed_before_this_claim"),
                "scan_truncated": presenter.get("scan_truncated"),
            }
            if presenter_recorded
            else None
        ),
    }


PRESENTER_SCAN_LIMIT = 2_000
_PRESENTER_SCAN_SLACK_SECONDS = 300


def _presenters_seen_with_key(
    archive_root: Path | str,
    key: memoryview,
    filesystem_boundary: tuple[Path, dict[str, Any]] | None,
    *,
    work_session_ref: str,
    not_before: str | None = None,
) -> tuple[set[str], bool]:
    """(distinct fingerprint digests recorded for this session, scan_truncated).

    Read-only and bounded: only claim files modified since ``not_before``
    (the grant's ``granted_at``, minus a slack) are opened, newest first, at
    most PRESENTER_SCAN_LIMIT of them; invalid claims are skipped. A grant
    claim older than the grant cannot be a presenter of this grant. Used
    inside the broker's key scope before a new grant claim is written.
    """

    if filesystem_boundary is None:
        # A writer without its own filesystem boundary (the plain CLI route)
        # still gets the bounded read-only claim-store binding.
        root, _archive_id = _archive_identity(archive_root)
        if not root.joinpath(*Path(CLAIMS_RELATIVE_ROOT).parts).is_dir():
            return set(), False
        with _claims_boundary_default(archive_root)() as bound:
            return _presenters_seen_with_key(
                archive_root, key, bound, work_session_ref=work_session_ref, not_before=not_before,
            )
    bound_archive_root, claim_parent_binding = filesystem_boundary
    claims_root = Path(bound_archive_root).joinpath(*Path(CLAIMS_RELATIVE_ROOT).parts)
    if claim_parent_binding.get("path") != claims_root:
        raise _fail("exact_approval_claim_store_unavailable")
    directory_target = claim_parent_binding.get("descriptor")
    if type(directory_target) is not int:
        directory_target = claim_parent_binding.get("path")
    floor = None
    if type(not_before) is str:
        try:
            floor = _parse_timestamp(not_before).timestamp() - _PRESENTER_SCAN_SLACK_SECONDS
        except (ExactHumanApprovalError, TypeError, ValueError, OverflowError):
            floor = None
    try:
        with os.scandir(directory_target) as entries:
            candidates = []
            for entry in entries:
                match = _workflow._APPROVAL_CLAIM_FILENAME_RE.fullmatch(entry.name)
                if match is None:
                    continue
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if not stat.S_ISREG(info.st_mode):
                    continue
                if floor is not None and info.st_mtime < floor:
                    continue
                candidates.append((info.st_mtime, match.group(1)))
    except (OSError, TypeError, ValueError):
        raise _fail("exact_approval_claim_store_unavailable") from None
    candidates.sort(reverse=True)
    truncated = len(candidates) > PRESENTER_SCAN_LIMIT
    seen: set[str] = set()
    for _mtime, approval_id in candidates[:PRESENTER_SCAN_LIMIT]:
        try:
            parsed, _archive_id = _authenticated_claim_document_core(
                archive_root, approval_id, key,
                bound_archive_root=bound_archive_root, claim_parent_binding=claim_parent_binding,
            )
        except ExactHumanApprovalError:
            continue
        presenter = parsed.get("session_presenter")
        if (isinstance(presenter, Mapping) and presenter.get("work_session_ref") == work_session_ref
                and type(presenter.get("process_fingerprint_sha256")) is str):
            seen.add(presenter["process_fingerprint_sha256"])
    return seen, truncated


def _enumerate_claims_with_key(
    archive_root: Path | str,
    key: memoryview,
    filesystem_boundary: tuple[Path, dict[str, Any]] | None,
    *,
    max_claims: int,
    clock: Callable[[], datetime],
) -> tuple[list[dict[str, Any]], int, int, bool]:
    """Return (projected claims, scanned, invalid, complete)."""

    if filesystem_boundary is None:
        raise _fail("exact_approval_claim_store_unavailable")
    bound_archive_root, claim_parent_binding = filesystem_boundary
    claims_root = Path(bound_archive_root).joinpath(*Path(CLAIMS_RELATIVE_ROOT).parts)
    if claim_parent_binding.get("path") != claims_root:
        raise _fail("exact_approval_claim_store_unavailable")
    directory_target = claim_parent_binding.get("descriptor")
    if type(directory_target) is not int:
        directory_target = claim_parent_binding.get("path")
    try:
        names = os.listdir(directory_target)
    except (OSError, TypeError, ValueError):
        raise _fail("exact_approval_claim_store_unavailable") from None
    if len(names) > _workflow._MAX_RESUME_CLAIM_DIRECTORY_ENTRIES or any(
        type(name) is not str for name in names
    ):
        raise _fail("exact_approval_claim_store_unavailable")
    matching = sorted(
        match.group(1)
        for match in (
            _workflow._APPROVAL_CLAIM_FILENAME_RE.fullmatch(name) for name in names
        )
        if match is not None
    )
    complete = True
    if len(matching) > max_claims:
        matching = matching[:max_claims]
        complete = False
    claims: list[dict[str, Any]] = []
    invalid = 0
    for approval_id in matching:
        try:
            parsed, _archive_id = _authenticated_claim_document_core(
                archive_root,
                approval_id,
                key,
                bound_archive_root=bound_archive_root,
                claim_parent_binding=claim_parent_binding,
            )
        except ExactHumanApprovalError:
            invalid += 1
            continue
        claims.append(_project_claim(parsed, clock=clock))
    return claims, len(matching), invalid, complete


def _with_key_and_boundary(
    archive_root: Path | str,
    consumer: Callable[[memoryview, tuple[Path, dict[str, Any]] | None], Any],
    *,
    key_provider: Any | None,
    claims_boundary: Callable[[], AbstractContextManager[Any]] | None,
) -> Any:
    boundary = (
        claims_boundary
        if claims_boundary is not None
        else _claims_boundary_default(archive_root)
    )
    try:
        with boundary() as filesystem_boundary:
            provider = (
                key_provider
                if key_provider is not None
                else _workflow._production_key_provider()
            )
            return provider.use_key(
                archive_root,
                lambda key: consumer(key, filesystem_boundary),
                create_if_missing=False,
            )
    except ExactApprovalClaimsError:
        raise
    except _workflow.ExactHumanApprovalWorkflowError as error:
        if error.code == "exact_human_approval_key_unavailable":
            raise _fail("exact_approval_claim_key_unavailable") from None
        raise _fail("exact_approval_claim_store_unavailable") from None
    except BaseException:
        raise _fail("exact_approval_claim_key_unavailable") from None


def list_exact_human_approval_claims(
    archive_root: Path | str,
    *,
    status: str = "started",
    operation: str | None = None,
    max_claims: int = 10_000,
    key_provider: Any | None = None,
    claims_boundary: Callable[[], AbstractContextManager[Any]] | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> dict[str, Any]:
    """Enumerate the MAC-verified claim store; fixed fields only, no writes."""

    if (
        status not in STATUS_FILTERS
        or (operation is not None and operation not in {m.value for m in ExactHumanApprovalOperation})
        or type(max_claims) is not int
        or isinstance(max_claims, bool)
        or not 1 <= max_claims <= MAX_LISTED_CLAIMS
    ):
        raise _fail("exact_approval_claim_argument_invalid")

    def _consumer(key: memoryview, boundary: tuple[Path, dict[str, Any]] | None):
        return _enumerate_claims_with_key(
            archive_root, key, boundary, max_claims=max_claims, clock=clock
        )

    root, _archive_id = _archive_identity(archive_root)
    claims_root = root.joinpath(*Path(CLAIMS_RELATIVE_ROOT).parts)
    if not claims_root.is_dir():
        # No claim was ever published for this archive: an empty store, not
        # an error, and no key is needed to say so.
        claims, scanned, invalid, complete = [], 0, 0, True
    else:
        claims, scanned, invalid, complete = _with_key_and_boundary(
            archive_root,
            _consumer,
            key_provider=key_provider,
            claims_boundary=claims_boundary,
        )
    status_counts = {"started": 0, "succeeded": 0, "failed": 0}
    started_operation_counts: dict[str, int] = {}
    mechanism_counts: dict[str, int] = {}
    presenter_unknown_count = 0
    for claim in claims:
        if claim["status"] in status_counts:
            status_counts[claim["status"]] += 1
        if claim["status"] == "started" and claim["operation"]:
            started_operation_counts[claim["operation"]] = (
                started_operation_counts.get(claim["operation"], 0) + 1
            )
        mechanism = claim.get("approval_mechanism")
        if type(mechanism) is str:
            mechanism_counts[mechanism] = mechanism_counts.get(mechanism, 0) + 1
            if mechanism == "work_session_permission_mode" and not claim.get("presenter_recorded"):
                presenter_unknown_count += 1
    selected = [
        claim
        for claim in claims
        if (status == "all" or claim["status"] == status)
        and (operation is None or claim["operation"] == operation)
    ]
    selected.sort(key=lambda item: (item["started_at"] or "", item["approval_id"] or ""))
    blocker_codes: list[str] = []
    if invalid:
        blocker_codes.append("exact_approval_claim_listing_entry_invalid")
    if not complete:
        blocker_codes.append("exact_approval_claim_limit_exceeded")
    next_safe_actions: list[str] = []
    if status_counts["started"]:
        next_safe_actions.append(
            "Review each started claim (a writer may still be running for a "
            "young one); close reviewed ones with 'archive "
            "exact-approval-claim-finalize <archive-root> --approval-id <id> "
            "--dry-run' (or --all-started)."
        )
    if started_operation_counts.get("project_version_update"):
        next_safe_actions.append(
            "project_version_update claims are closed with 'archive "
            "project-version-update <archive-root> --resume "
            "--abandon-started-approval --affirm-external-writers-quiescent'."
        )
    return {
        "schema_version": LISTING_SCHEMA_VERSION,
        "ok": not blocker_codes,
        "complete": complete and not invalid,
        "read_only": True,
        "claim_limit": max_claims,
        "claims_scanned": scanned,
        "invalid_claim_count": invalid,
        "status_filter": status,
        "operation_filter": operation,
        "claim_count": len(selected),
        "status_counts": status_counts,
        "started_operation_counts": dict(sorted(started_operation_counts.items())),
        # v0.4.34 (letter 165 [A]): how each claim was decided, and how many
        # grant claims predate presenter evidence (they stay immutable).
        "mechanism_counts": dict(sorted(mechanism_counts.items())),
        "presenter_unknown_count": presenter_unknown_count,
        "presenter_evidence_note": (
            "claims before v0.4.34 stay immutable; presenter evidence starts with the next grant"
        ),
        "claims": selected,
        "blocker_codes": blocker_codes,
        "next_safe_actions": next_safe_actions,
        "private_values_echoed": False,
        "paths_echoed": False,
        "reviewer_echoed": False,
    }


# ---------------------------------------------------------------- evidence scan


def _is_reparse(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & reparse)


def _collect_approval_ids(value: Any, into: set[str], *, depth: int = 0) -> None:
    if depth > 64:
        return
    if isinstance(value, Mapping):
        for item in value.values():
            _collect_approval_ids(item, into, depth=depth + 1)
    elif isinstance(value, list):
        for item in value:
            _collect_approval_ids(item, into, depth=depth + 1)
    elif type(value) is str:
        for match in _APPROVAL_ID_TOKEN_RE.findall(value):
            into.add(match)


def _scan_file_for_approval_ids(path: Path, wanted: set[str]) -> set[str]:
    """Stream one file and return the wanted approval ids it contains.

    A byte-level search (chunked, with overlap) rather than a JSON parse:
    strictly more lenient — any occurrence of an id string counts as a
    reference, whatever the envelope shape or size — and bounded in memory.
    """

    found: set[str] = set()
    wanted_bytes = {item.encode("ascii") for item in wanted}
    tail = b""
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_EVIDENCE_CHUNK_BYTES)
            if not chunk:
                break
            window = tail + chunk
            for match in _APPROVAL_ID_BYTES_RE.finditer(window):
                token = match.group(0)
                if token in wanted_bytes:
                    found.add(token.decode("ascii"))
            tail = window[-_EVIDENCE_OVERLAP_BYTES:]
    return found


def scan_receipt_references(
    root: Path,
    approval_ids: set[str],
) -> dict[str, Any]:
    """Which of ``approval_ids`` any receipt file under the scan roots names.

    Lenient by design: every ``*.json`` regular file is streamed and searched
    for an approval id, so batch item envelopes, version-update journals,
    oversized Doctor receipts and future receipt shapes all count. A file
    that cannot be read, or one above the byte ceiling, makes the scan
    incomplete and is named (archive-relative); the caller fails closed.
    """

    referenced: dict[str, int] = {}
    files_scanned = 0
    unreadable = 0
    oversize_skipped = 0
    unreadable_paths: list[str] = []
    oversize_paths: list[str] = []
    complete = True

    def _relative(path: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.name
    for parts in EVIDENCE_SCAN_ROOTS:
        base = root.joinpath(*parts)
        try:
            base_info = os.lstat(base)
        except OSError:
            continue
        if _is_reparse(base_info) or not stat.S_ISDIR(base_info.st_mode):
            continue
        for current, directories, files in os.walk(base):
            current_path = Path(current)
            kept: list[str] = []
            for name in sorted(directories):
                try:
                    info = os.lstat(current_path / name)
                except OSError:
                    complete = False
                    continue
                if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
                    continue
                kept.append(name)
            directories[:] = kept
            for name in sorted(files):
                if not name.endswith(".json"):
                    continue
                files_scanned += 1
                if files_scanned > _MAX_EVIDENCE_FILES:
                    complete = False
                    break
                path = current_path / name
                try:
                    info = os.lstat(path)
                    if _is_reparse(info) or not stat.S_ISREG(info.st_mode):
                        continue
                    if info.st_size > _MAX_EVIDENCE_FILE_BYTES:
                        oversize_skipped += 1
                        complete = False
                        if len(oversize_paths) < _MAX_NAMED_EVIDENCE_PATHS:
                            oversize_paths.append(_relative(path))
                        continue
                    found = _scan_file_for_approval_ids(path, approval_ids) if approval_ids else set()
                except OSError:
                    unreadable += 1
                    complete = False
                    if len(unreadable_paths) < _MAX_NAMED_EVIDENCE_PATHS:
                        unreadable_paths.append(_relative(path))
                    continue
                for approval_id in found:
                    referenced[approval_id] = referenced.get(approval_id, 0) + 1
            if not complete and files_scanned > _MAX_EVIDENCE_FILES:
                break
    return {
        "scan_roots": ["/".join(parts) for parts in EVIDENCE_SCAN_ROOTS],
        "scan_method": "byte_stream_search",
        "files_scanned": files_scanned,
        "unreadable_file_count": unreadable,
        "unreadable_receipt_paths": unreadable_paths,
        "oversize_skipped_count": oversize_skipped,
        "oversize_skipped_receipt_paths": oversize_paths,
        "oversize_ceiling_bytes": _MAX_EVIDENCE_FILE_BYTES,
        "complete": complete,
        "referenced": referenced,
    }


def evidence_inventory_fingerprint(root: Path) -> dict[str, Any]:
    """v0.4.36 (beta letter 168 ③): a cheap digest of the receipt inventory.

    The same roots and filters as ``scan_receipt_references``, but only
    (relative path, size, mtime_ns) per ``*.json`` regular file: seconds,
    not minutes. Bound into the finalize plan digest, it lets the approve
    skip the byte-stream re-scan when nothing under the roots changed since
    the dry-run; any new, removed or rewritten receipt changes it.
    """

    rows: list[list[Any]] = []
    complete = True
    for parts in EVIDENCE_SCAN_ROOTS:
        base = root.joinpath(*parts)
        try:
            base_info = os.lstat(base)
        except OSError:
            continue
        if _is_reparse(base_info) or not stat.S_ISDIR(base_info.st_mode):
            continue
        for current, directories, files in os.walk(base):
            current_path = Path(current)
            kept: list[str] = []
            for name in sorted(directories):
                try:
                    info = os.lstat(current_path / name)
                except OSError:
                    complete = False
                    continue
                if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
                    continue
                kept.append(name)
            directories[:] = kept
            for name in sorted(files):
                if not name.endswith(".json"):
                    continue
                path = current_path / name
                try:
                    info = os.lstat(path)
                except OSError:
                    complete = False
                    continue
                if _is_reparse(info) or not stat.S_ISREG(info.st_mode):
                    continue
                try:
                    relative = path.relative_to(root).as_posix()
                except ValueError:
                    relative = name
                rows.append([relative, int(info.st_size), int(getattr(info, "st_mtime_ns", 0))])
                if len(rows) > _MAX_EVIDENCE_FILES:
                    complete = False
                    break
            if not complete and len(rows) > _MAX_EVIDENCE_FILES:
                break
    rows.sort()
    digest = hashlib.sha256(
        json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {"sha256": "sha256:" + digest, "file_count": len(rows), "complete": complete}


# ---------------------------------------------------------------- finalize plan


def _finalize_plan_basis(
    *, archive_id: str, min_age_minutes: int, warnings: list[str], selected: list[dict[str, Any]],
    fingerprint: Mapping[str, Any], evidence_clean: bool,
) -> dict[str, Any]:
    """The digest basis: the selection, the receipt inventory fingerprint and whether the scan was clean."""

    return {
        "schema": FINALIZE_PLAN_SCHEMA_VERSION,
        "archive_identity_sha256": exact_human_approval_archive_identity_sha256(archive_id),
        "failure_code": FINALIZE_FAILURE_CODE,
        "min_age_minutes": min_age_minutes,
        "warnings": list(warnings),
        "claims": [
            {
                "approval_id": item["approval_id"],
                "context_sha256": item["context_sha256"],
                "operation": item["operation"],
                "started_at": item["started_at"],
                "backfill": item["backfill"],
            }
            for item in selected
        ],
        # v0.4.36 (letter 168 ③)
        "evidence_inventory_fingerprint": str(fingerprint["sha256"]),
        "evidence_clean": bool(evidence_clean),
    }


def _finalize_receipt_relative(approval_id: str) -> str:
    return f"{FINALIZE_RECEIPTS_RELATIVE}/{approval_id}.claim-finalize.json"


def _selection_inputs_valid(
    approval_ids: tuple[str, ...] | None,
    all_started: bool,
    operation: str | None,
    min_age_minutes: int,
) -> bool:
    if type(all_started) is not bool:
        return False
    if approval_ids is not None and (
        type(approval_ids) is not tuple
        or not approval_ids
        or any(type(item) is not str or _APPROVAL_ID_RE.fullmatch(item) is None for item in approval_ids)
        or len(set(approval_ids)) != len(approval_ids)
    ):
        return False
    if (approval_ids is None) == (not all_started):
        return False
    if operation is not None and operation not in {m.value for m in ExactHumanApprovalOperation}:
        return False
    if type(min_age_minutes) is not int or isinstance(min_age_minutes, bool) or not 0 <= min_age_minutes <= 100_000:
        return False
    return True


def plan_exact_human_approval_claim_finalize(
    archive_root: Path | str,
    *,
    approval_ids: tuple[str, ...] | None = None,
    all_started: bool = False,
    operation: str | None = None,
    min_age_minutes: int = DEFAULT_MIN_AGE_MINUTES,
    key_provider: Any | None = None,
    claims_boundary: Callable[[], AbstractContextManager[Any]] | None = None,
    clock: Callable[[], datetime] = _utc_now,
    trusted_plan_sha256: str | None = None,
) -> dict[str, Any]:
    """Select started claims to close and prove no receipt references them.

    No dialog, no claim, no write.  The plan digest binds the exact selected
    claims (id and context digest), the failure code that will be written and
    every warning, so the dialog and the writer see the same set.
    """

    if not _selection_inputs_valid(approval_ids, all_started, operation, min_age_minutes):
        raise _fail("exact_approval_claim_argument_invalid")
    root, archive_id = _archive_identity(archive_root)
    listing = list_exact_human_approval_claims(
        archive_root,
        status="all",
        max_claims=MAX_LISTED_CLAIMS,
        key_provider=key_provider,
        claims_boundary=claims_boundary,
        clock=clock,
    )
    by_id = {claim["approval_id"]: claim for claim in listing["claims"] if claim["approval_id"]}
    blockers: list[str] = list(listing["blocker_codes"])
    warnings: list[str] = []
    selected: list[dict[str, Any]] = []
    skipped_too_recent = 0
    excluded_project_version_update = 0

    def _backfill_candidate(claim: Mapping[str, Any]) -> bool:
        return (
            claim["status"] == "failed"
            and claim["failure_code"] == FINALIZE_FAILURE_CODE
            and not (root / _finalize_receipt_relative(str(claim["approval_id"]))).exists()
        )

    if approval_ids is not None:
        for approval_id in approval_ids:
            claim = by_id.get(approval_id)
            if claim is None:
                blockers.append("exact_approval_claim_not_found")
                continue
            if operation is not None and claim["operation"] != operation:
                blockers.append("exact_approval_claim_operation_mismatch")
                continue
            if claim["operation"] == ExactHumanApprovalOperation.project_version_update.value:
                blockers.append("exact_approval_claim_finalize_use_project_version_update_abandon")
                continue
            if _backfill_candidate(claim):
                selected.append({**claim, "backfill": True})
                continue
            if claim["status"] != "started":
                blockers.append("exact_approval_claim_not_started")
                continue
            if claim["age_minutes"] is None or claim["age_minutes"] < min_age_minutes:
                blockers.append("exact_approval_claim_too_recent")
                continue
            selected.append({**claim, "backfill": False})
    else:
        for claim in listing["claims"]:
            if operation is not None and claim["operation"] != operation:
                continue
            if _backfill_candidate(claim):
                selected.append({**claim, "backfill": True})
                continue
            if claim["status"] != "started":
                continue
            if claim["operation"] == ExactHumanApprovalOperation.project_version_update.value:
                excluded_project_version_update += 1
                continue
            if claim["age_minutes"] is None or claim["age_minutes"] < min_age_minutes:
                skipped_too_recent += 1
                continue
            selected.append({**claim, "backfill": False})
    selected.sort(key=lambda item: (item["started_at"] or "", item["approval_id"] or ""))
    if len(selected) > MAX_FINALIZE_SET:
        blockers.append("exact_approval_claim_finalize_set_too_large")
    if not selected and not blockers:
        blockers.append("exact_approval_claim_finalize_nothing_selected")
    if min_age_minutes == 0:
        warnings.append("exact_approval_claim_min_age_overridden")
    if any(item["operation"] not in RECEIPTED_OPERATIONS for item in selected):
        warnings.append("exact_approval_claim_write_evidence_receipts_only")

    # v0.4.36 (beta letter 168 ③): the receipt inventory fingerprint is part
    # of the plan digest. When the caller trusts a digest (the approve
    # writer with the reviewed plan) and the digest computed from the same
    # selection, the current fingerprint and a CLEAN scan equals it, the
    # dry-run's byte-stream scan stands and is not repeated.
    fingerprint = evidence_inventory_fingerprint(root)
    trusted_clean = False
    if trusted_plan_sha256 is not None and selected and fingerprint["complete"]:
        candidate = _finalize_plan_basis(
            archive_id=archive_id, min_age_minutes=min_age_minutes, warnings=sorted(set(warnings)),
            selected=selected, fingerprint=fingerprint, evidence_clean=True,
        )
        trusted_clean = hmac.compare_digest(_sha256_of(_PLAN_DOMAIN, candidate), str(trusted_plan_sha256))
    evidence = {
        "scan_roots": ["/".join(parts) for parts in EVIDENCE_SCAN_ROOTS],
        "scan_method": "fingerprint_matched_plan",
        "files_scanned": fingerprint["file_count"],
        "unreadable_file_count": 0,
        "unreadable_receipt_paths": [],
        "oversize_skipped_count": 0,
        "oversize_skipped_receipt_paths": [],
        "oversize_ceiling_bytes": _MAX_EVIDENCE_FILE_BYTES,
        "complete": True,
        "referenced": {},
    } if trusted_clean else scan_receipt_references(
        root, {str(item["approval_id"]) for item in selected}
    ) if selected else {
        "scan_roots": ["/".join(parts) for parts in EVIDENCE_SCAN_ROOTS],
        "scan_method": "byte_stream_search",
        "files_scanned": 0,
        "unreadable_file_count": 0,
        "unreadable_receipt_paths": [],
        "oversize_skipped_count": 0,
        "oversize_skipped_receipt_paths": [],
        "oversize_ceiling_bytes": _MAX_EVIDENCE_FILE_BYTES,
        "complete": True,
        "referenced": {},
    }
    referenced_count = 0
    for item in selected:
        hits = evidence["referenced"].get(str(item["approval_id"]), 0)
        item["receipt_reference_count"] = hits
        if hits:
            referenced_count += 1
    if referenced_count:
        blockers.append("exact_approval_claim_referenced_by_receipt")
    if not evidence["complete"]:
        blockers.append("exact_approval_claim_evidence_scan_incomplete")
    blockers = sorted(set(blockers))
    warnings = sorted(set(warnings))
    archive_identity_sha256 = exact_human_approval_archive_identity_sha256(archive_id)
    plan_basis = _finalize_plan_basis(
        archive_id=archive_id, min_age_minutes=min_age_minutes, warnings=warnings, selected=selected,
        fingerprint=fingerprint, evidence_clean=(evidence["complete"] and not referenced_count),
    )
    target_basis = {
        "claims": [
            {"approval_id": item["approval_id"], "context_sha256": item["context_sha256"]}
            for item in selected
        ]
    }
    plan_sha256 = _sha256_of(_PLAN_DOMAIN, plan_basis)
    target_binding_sha256 = _sha256_of(_TARGET_DOMAIN, target_basis)
    ok = not blockers
    next_safe_actions: list[str] = []
    if ok:
        next_safe_actions.append(
            "Re-run the same selection with --approve --reviewed-by <id> "
            "--expected-plan-sha256 <plan_sha256>; one native dialog (none under a valid "
            "session grant) closes the listed claims as failed."
        )
    if excluded_project_version_update:
        next_safe_actions.append(
            "project_version_update claims were excluded; close them with "
            "'archive project-version-update <archive-root> --resume "
            "--abandon-started-approval --affirm-external-writers-quiescent'."
        )
    if skipped_too_recent:
        next_safe_actions.append(
            f"{skipped_too_recent} started claim(s) younger than {min_age_minutes} "
            "minute(s) were left alone; wait, or pass --min-age-minutes 0 after "
            "confirming no writer is running."
        )
    if referenced_count:
        next_safe_actions.append(
            "A receipt references a selected claim: that write happened; audit it "
            "with 'archive approval-integrity-audit <archive-root>' instead of "
            "closing the claim."
        )
    if not evidence["complete"]:
        next_safe_actions.append(
            "The receipt scan is incomplete: write_evidence names the unreadable or "
            "oversize receipts (archive-relative); repair or move them, then rerun."
        )
    return {
        "ok": ok,
        "dry_run": True,
        "state": "ready" if ok else "blocked",
        "lifecycle_action": "exact_approval_claim_finalize_plan",
        "schema_version": FINALIZE_PLAN_SCHEMA_VERSION,
        "plan_sha256": plan_sha256 if ok else None,
        "target_binding_sha256": target_binding_sha256 if ok else None,
        "review_binding_codes": [
            "claim_context_digest",
            "claim_identity",
            "failure_code",
            "warning_codes",
        ],
        "warning_codes": warnings,
        "failure_code": FINALIZE_FAILURE_CODE,
        "min_age_minutes": min_age_minutes,
        "selected": [
            {
                "approval_id": item["approval_id"],
                "operation": item["operation"],
                "status": item["status"],
                "started_at": item["started_at"],
                "age_minutes": item["age_minutes"],
                "approval_mechanism": item["approval_mechanism"],
                "backfill": item["backfill"],
                "receipt_reference_count": item["receipt_reference_count"],
            }
            for item in selected
        ],
        "selected_count": len(selected),
        "backfill_count": sum(1 for item in selected if item["backfill"]),
        "skipped_too_recent_count": skipped_too_recent,
        "excluded_project_version_update_count": excluded_project_version_update,
        # v0.4.36 (letter 168 ③): the approve repeats the scan only when this
        # fingerprint changed; otherwise it takes seconds after the dialog.
        "evidence_inventory_fingerprint": fingerprint["sha256"],
        "evidence_inventory_file_count": fingerprint["file_count"],
        "approve_rescans_receipts": "only_when_the_inventory_fingerprint_changed",
        "write_evidence": {
            "scan_roots": evidence["scan_roots"],
            "scan_method": evidence.get("scan_method", "byte_stream_search"),
            "files_scanned": evidence["files_scanned"],
            "unreadable_file_count": evidence["unreadable_file_count"],
            "unreadable_receipt_paths": list(evidence.get("unreadable_receipt_paths") or []),
            "oversize_skipped_count": int(evidence.get("oversize_skipped_count") or 0),
            "oversize_skipped_receipt_paths": list(evidence.get("oversize_skipped_receipt_paths") or []),
            "oversize_ceiling_bytes": int(evidence.get("oversize_ceiling_bytes") or 0),
            "referenced_count": referenced_count,
            "complete": evidence["complete"],
            "kind": "receipts_only",
        },
        "blockers": blockers,
        "warnings": warnings,
        "would_change": [
            (
                f"receipt for already closed claim {item['approval_id']}"
                if item["backfill"]
                else f"claim {item['approval_id']}: started -> failed ({FINALIZE_FAILURE_CODE})"
            )
            for item in selected
        ]
        if ok
        else [],
        "next_safe_actions": next_safe_actions,
        "private_values_echoed": False,
        # archive-relative receipt paths appear only to name a skipped or
        # unreadable receipt (letter 164 ②); never a private path.
        "paths_echoed": bool(
            evidence.get("unreadable_receipt_paths") or evidence.get("oversize_skipped_receipt_paths")
        ),
        "reviewer_echoed": False,
    }


# ---------------------------------------------------------------- finalize writer


def _rehydrate_started_claim_without_context(
    archive_root: Path | str,
    approval_id: str,
    key: memoryview,
    *,
    expected_context_sha256: str,
    clock: Callable[[], datetime],
    bound_archive_root: Path,
    claim_parent_binding: dict[str, Any],
) -> _ClaimedExactHumanApproval:
    """Rebuild one started claim capability from its authenticated bytes.

    The operator reviewed the claim by id and context digest; both are
    re-checked here before the compare-and-swap finalizer runs.
    """

    parsed, archive_id = _authenticated_claim_document_core(
        archive_root,
        approval_id,
        key,
        bound_archive_root=bound_archive_root,
        claim_parent_binding=claim_parent_binding,
    )
    context_sha256 = parsed.get("context_sha256")
    if (
        parsed.get("status") != "started"
        or type(context_sha256) is not str
        or not hmac.compare_digest(context_sha256, expected_context_sha256)
    ):
        raise _fail("exact_approval_claim_finalize_claim_invalid")
    intent = parsed.get("interactive_intent")
    mechanism = intent.get("mechanism") if isinstance(intent, Mapping) else None
    claims_root = Path(bound_archive_root).joinpath(*Path(CLAIMS_RELATIVE_ROOT).parts)
    return _ClaimedExactHumanApproval(
        _mechanism=str(mechanism),
        _path=claims_root / f"{approval_id}.json",
        _archive_id=archive_id,
        _key=_validated_key(key),
        _approval_id=approval_id,
        _context_sha256=context_sha256,
        _authority_sha256=str(parsed.get("approval_authority_sha256")),
        _clock=clock,
        _bound_archive_root=bound_archive_root,
        _claim_parent_binding=claim_parent_binding,
    )


def _write_finalize_receipt(root: Path, relative: str, document: Mapping[str, Any]) -> None:
    path = root.joinpath(*relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical_bytes(document))
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def finalize_exact_human_approval_claims(
    archive_root: Path | str,
    *,
    approval_ids: tuple[str, ...] | None = None,
    all_started: bool = False,
    operation: str | None = None,
    min_age_minutes: int = DEFAULT_MIN_AGE_MINUTES,
    expected_plan_sha256: str,
    exact_human_approval_claim: Any,
    key_provider: Any | None = None,
    claims_boundary: Callable[[], AbstractContextManager[Any]] | None = None,
    clock: Callable[[], datetime] = _utc_now,
) -> dict[str, Any]:
    """Close the reviewed started claims as failed and receipt each closing.

    Runs under the archive-wide exact-operation writer lock, re-derives the
    plan, re-scans the receipts and then closes one claim at a time through
    the claim's own compare-and-swap finalizer.  A failure mid-set leaves the
    already closed claims closed (each swap is durable) and raises; the next
    dry-run shows the smaller set with a new digest.
    """

    from . import archive_services
    from .exact_operation_manifest import exact_operation_writer_lock

    if type(expected_plan_sha256) is not str or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", expected_plan_sha256
    ):
        raise archive_services.ArchiveServiceError("exact_approval_claim_finalize_plan_mismatch")
    root, archive_id = _archive_identity(archive_root)
    try:
        lock = exact_operation_writer_lock(root)
    except Exception:
        raise archive_services.ArchiveServiceError("exact_approval_claim_finalize_lock_unavailable") from None
    with lock:
        plan = plan_exact_human_approval_claim_finalize(
            archive_root,
            approval_ids=approval_ids,
            all_started=all_started,
            operation=operation,
            min_age_minutes=min_age_minutes,
            key_provider=key_provider,
            claims_boundary=claims_boundary,
            clock=clock,
            # v0.4.36 (letter 168 ③): the reviewed digest lets the plan
            # skip the byte-stream scan when the inventory is unchanged.
            trusted_plan_sha256=expected_plan_sha256,
        )
        if plan["ok"] is not True or plan["blockers"]:
            raise archive_services.ArchiveServiceError("exact_approval_claim_finalize_plan_blocked")
        if not hmac.compare_digest(str(plan["plan_sha256"]), expected_plan_sha256):
            raise archive_services.ArchiveServiceError("exact_approval_claim_finalize_plan_mismatch")
        finalize_reference = (
            exact_human_approval_claim.public_reference()
            if hasattr(exact_human_approval_claim, "public_reference")
            else None
        )
        archive_identity_sha256 = exact_human_approval_archive_identity_sha256(archive_id)
        selected = list(plan["selected"])
        # The listing used by the plan carries the context digests; re-read
        # them here from the same authenticated store inside the lock.
        listing = list_exact_human_approval_claims(
            archive_root,
            status="all",
            max_claims=MAX_LISTED_CLAIMS,
            key_provider=key_provider,
            claims_boundary=claims_boundary,
            clock=clock,
        )
        digests = {
            claim["approval_id"]: claim["context_sha256"]
            for claim in listing["claims"]
        }
        finished_by_id = {
            claim["approval_id"]: claim["finished_at"]
            for claim in listing["claims"]
        }
        finalized: list[dict[str, Any]] = []
        created: list[str] = []

        def _close_all(key: memoryview, boundary: tuple[Path, dict[str, Any]] | None) -> None:
            if boundary is None:
                raise _fail("exact_approval_claim_store_unavailable")
            bound_root, parent_binding = boundary
            # Re-check once more inside the lock, right before the first swap: a
            # receipt written since the dry-run means that write happened and
            # its claim must stay started. v0.4.36 (letter 168 ③): the check
            # is the inventory fingerprint bound into the plan; only a changed
            # inventory triggers the byte-stream scan again.
            current = evidence_inventory_fingerprint(root)
            if not current["complete"] or current["sha256"] != plan["evidence_inventory_fingerprint"]:
                recheck = scan_receipt_references(
                    root, {str(item["approval_id"]) for item in selected}
                )
                if not recheck["complete"] or recheck["referenced"]:
                    raise _fail("exact_approval_claim_finalize_claim_invalid")
                recheck_method = "byte_stream_search"
            else:
                recheck = {"scan_roots": plan["write_evidence"]["scan_roots"], "files_scanned": current["file_count"]}
                recheck_method = "fingerprint_matched_plan"
            for item in selected:
                approval_id = str(item["approval_id"])
                expected_context = digests.get(approval_id)
                if type(expected_context) is not str:
                    raise _fail("exact_approval_claim_finalize_claim_invalid")
                receipt_relative = _finalize_receipt_relative(approval_id)
                finished_at: str
                if item["backfill"]:
                    finished_at = str(finished_by_id.get(approval_id) or _timestamp(clock()))
                else:
                    claim = _rehydrate_started_claim_without_context(
                        archive_root,
                        approval_id,
                        key,
                        expected_context_sha256=expected_context,
                        clock=clock,
                        bound_archive_root=bound_root,
                        claim_parent_binding=parent_binding,
                    )
                    try:
                        claim.finalize_failed(FINALIZE_FAILURE_CODE)
                    except ExactHumanApprovalError:
                        raise _fail("exact_approval_claim_finalize_state_unknown") from None
                    finally:
                        claim.close()
                    finished_at = _timestamp(clock())
                receipt = {
                    "schema_version": FINALIZE_RECEIPT_SCHEMA_VERSION,
                    "archive_identity_sha256": archive_identity_sha256,
                    "target_approval_id": approval_id,
                    "target_context_sha256": expected_context,
                    "target_operation": item["operation"],
                    "target_started_at": item["started_at"],
                    "failure_code": FINALIZE_FAILURE_CODE,
                    "finished_at": finished_at,
                    "backfilled": bool(item["backfill"]),
                    "write_evidence": {
                        "kind": "receipts_only",
                        "scan_roots": recheck["scan_roots"],
                        "scan_method": recheck_method,
                        "files_scanned": recheck["files_scanned"],
                        "reference_found": False,
                        "complete": True,
                        "operation_receipted_on_success": item["operation"] in RECEIPTED_OPERATIONS,
                    },
                    "finalize_plan_sha256": plan["plan_sha256"],
                    "finalize_approval": finalize_reference,
                    "private_values_echoed": False,
                    "paths_echoed": False,
                    "reviewer_echoed": False,
                }
                try:
                    _write_finalize_receipt(root, receipt_relative, receipt)
                except OSError:
                    raise _fail("exact_approval_claim_finalize_receipt_write_failed") from None
                created.append(receipt_relative)
                finalized.append(
                    {
                        "approval_id": approval_id,
                        "operation": item["operation"],
                        "failure_code": FINALIZE_FAILURE_CODE,
                        "backfilled": bool(item["backfill"]),
                    }
                )

        try:
            _with_key_and_boundary(
                archive_root,
                lambda key, boundary: _close_all(key, boundary),
                key_provider=key_provider,
                claims_boundary=claims_boundary,
            )
        except ExactApprovalClaimsError as error:
            # Partial progress is durable; surface a fixed code and the count.
            raise archive_services.ArchiveServiceError(error.code) from None
        return {
            "ok": True,
            "dry_run": False,
            "lifecycle_action": "exact_approval_claim_finalize",
            "schema_version": FINALIZE_PLAN_SCHEMA_VERSION,
            "plan_sha256": plan["plan_sha256"],
            "target_binding_sha256": plan["target_binding_sha256"],
            "failure_code": FINALIZE_FAILURE_CODE,
            "finalized": finalized,
            "finalized_count": len(finalized),
            "backfilled_count": sum(1 for item in finalized if item["backfilled"]),
            "created_paths": created,
            "files_written": created,
            "next_safe_actions": [
                "archive exact-approval-claims <archive-root> --status started",
            ],
            "private_values_echoed": False,
            "reviewer_echoed": False,
        }


__all__ = [
    "DEFAULT_MIN_AGE_MINUTES",
    "ExactApprovalClaimsError",
    "FINALIZE_FAILURE_CODE",
    "FINALIZE_PLAN_SCHEMA_VERSION",
    "FINALIZE_RECEIPT_SCHEMA_VERSION",
    "FINALIZE_RECEIPTS_RELATIVE",
    "LISTING_SCHEMA_VERSION",
    "RECEIPTED_OPERATIONS",
    "STATUS_FILTERS",
    "finalize_exact_human_approval_claims",
    "list_exact_human_approval_claims",
    "plan_exact_human_approval_claim_finalize",
    "scan_receipt_references",
]
