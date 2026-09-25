"""Fetch whole IMAP messages losslessly into the archive (v0.4.42).

Beta letters asked to keep whole mail messages with their attachments, not
only headers. The header scan could never run (its legacy credential-access
approval receipt no longer exists) and would not have met the request. This
fetch stores each selected message as its raw RFC 822 bytes (`.eml`), which
keeps every attachment inside it losslessly, and writes a ready
`source-intake-batch` request so the existing intake chain captures the files
as objets under its own approval.

Safety:
- The dry-run reads no credential and opens no connection. Its `plan_sha256`
  binds the source, the host, port and credential references (only as
  hashes), the mailbox, the selection rule and window, the message cap and
  the output folder.
- The live fetch runs only after one exact approval bound to that digest
  (checked by the caller) and reads the credential references then.
- The mailbox is opened read-only (EXAMINE) and bodies are fetched with
  `BODY.PEEK[]`, so no message flag (such as Seen) changes on the server.
- Output files are created new under an absent folder; nothing is
  overwritten. Mail headers, subjects, addresses and bodies are never echoed.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import imaplib
import json
import os
import re
from pathlib import Path
from typing import Any, Callable

PLAN_SCHEMA = "wom-kit/imap-mailbox-message-fetch-plan/v0.1"
RECEIPT_SCHEMA = "wom-kit/imap-mailbox-message-fetch-receipt/v0.1"
INTAKE_REQUEST_SCHEMA = "wom-kit/source-intake-batch-request/v0.1"
OUTPUT_PREFIX = "workbench/imap-fetch"
RECEIPT_DIR = "receipts/imap-message-fetch"
MAX_MESSAGES = 1000
SELECTION_RULES = ("newest_first", "oldest_first", "unread_first", "since_days_window")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,99}$")
_SAFE_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$")
_SAFE_MAILBOX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._/+-]{0,99}$")
_ENV_REF_RE = re.compile(r"^env:([A-Za-z_][A-Za-z0-9_]{0,127})$")


def _client_factory(host: str, port: int, timeout: int) -> Any:
    """The live IMAP client; replaced in tests."""

    return imaplib.IMAP4_SSL(host, port, timeout=timeout)


class ImapFetchError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _hash(value: str | None) -> str | None:
    text = str(value or "").strip()
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None


def _source_binding(root: Path, source_id: str) -> dict[str, Any] | None:
    from .archive_services import load_source_bindings, source_bindings_list

    for item in source_bindings_list(load_source_bindings(root)):
        if isinstance(item, dict) and item.get("source_id") == source_id:
            return item
    return None


def _search_criterion(selection_rule: str, since_days: int | None) -> str:
    from .archive_services import imap_header_scan_search_criterion

    return imap_header_scan_search_criterion(selection_rule, since_days)


def plan_fetch(
    archive_root: Path | str,
    *,
    source_id: str,
    batch_id: str,
    imap_host: str,
    imap_port: int = 993,
    username_ref: str,
    app_password_ref: str,
    mailbox: str = "INBOX",
    selection_rule: str = "newest_first",
    since_days: int | None = None,
    max_messages: int = 50,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Read-only plan; reads no credential and opens no connection."""

    from .archive_services import read_archive_id, require_existing_archive_root

    root = require_existing_archive_root(archive_root)
    archive_id = read_archive_id(root)
    blockers: list[str] = []
    if not _SAFE_ID_RE.fullmatch(str(batch_id or "")):
        blockers.append("imap_fetch_batch_id_invalid")
    binding = _source_binding(root, str(source_id or ""))
    if binding is None:
        blockers.append("imap_fetch_source_not_registered")
    elif binding.get("source_type") != "imap_mailbox":
        blockers.append("imap_fetch_source_not_imap_mailbox")
    if not _SAFE_HOST_RE.fullmatch(str(imap_host or "")):
        blockers.append("imap_fetch_host_invalid")
    if not isinstance(imap_port, int) or isinstance(imap_port, bool) or not 1 <= imap_port <= 65535:
        blockers.append("imap_fetch_port_invalid")
    for ref in (username_ref, app_password_ref):
        if not _ENV_REF_RE.fullmatch(str(ref or "")):
            blockers.append("imap_fetch_credential_ref_invalid")
    if not _SAFE_MAILBOX_RE.fullmatch(str(mailbox or "")):
        blockers.append("imap_fetch_mailbox_invalid")
    if selection_rule not in SELECTION_RULES:
        blockers.append("imap_fetch_selection_rule_invalid")
    if selection_rule == "since_days_window" and not (isinstance(since_days, int) and since_days > 0):
        blockers.append("imap_fetch_since_days_required")
    if not isinstance(max_messages, int) or isinstance(max_messages, bool) or not 1 <= max_messages <= MAX_MESSAGES:
        blockers.append("imap_fetch_max_messages_invalid")
    if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 120:
        blockers.append("imap_fetch_timeout_invalid")
    output_relative = f"{OUTPUT_PREFIX}/{batch_id}"
    if _SAFE_ID_RE.fullmatch(str(batch_id or "")) and root.joinpath(*output_relative.split("/")).exists():
        blockers.append("imap_fetch_output_exists")
    plan_sha256 = "sha256:" + hashlib.sha256(json.dumps({
        "schema": PLAN_SCHEMA,
        "archive_id": archive_id,
        "source_id": source_id,
        "batch_id": batch_id,
        "imap_host_sha256": _hash(imap_host),
        "imap_port": imap_port,
        "username_ref_sha256": _hash(username_ref),
        "app_password_ref_sha256": _hash(app_password_ref),
        "mailbox_sha256": _hash(mailbox),
        "selection_rule": selection_rule,
        "since_days": since_days,
        "max_messages": max_messages,
        "timeout_seconds": timeout_seconds,
        "output": output_relative,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "ok": not blockers,
        "dry_run": True,
        "lifecycle_action": "imap_mailbox_message_fetch_plan",
        "plan_sha256": plan_sha256,
        "source_id": source_id,
        "batch_id": batch_id,
        "output": output_relative,
        "selection_rule": selection_rule,
        "max_messages": max_messages,
        "would_write": [f"{output_relative}/mail-NNNN.eml", f"{output_relative}/source-intake-batch-request.json",
                        f"{RECEIPT_DIR}/{batch_id}.json"] if not blockers else [],
        "server_flags_changed": False,
        "credential_reads": 0,
        "provider_calls": 0,
        "privacy_guards": {"host_echoed": False, "credential_ref_values_read": False,
                           "headers_echoed": False, "bodies_echoed": False},
        "blockers": sorted(set(blockers)),
        "next_step": "archive imap-mailbox-message-fetch ... --approve --reviewed-by <you>" if not blockers else None,
    }


def execute_fetch(
    archive_root: Path | str,
    *,
    source_id: str,
    batch_id: str,
    imap_host: str,
    imap_port: int = 993,
    username_ref: str,
    app_password_ref: str,
    mailbox: str = "INBOX",
    selection_rule: str = "newest_first",
    since_days: int | None = None,
    max_messages: int = 50,
    timeout_seconds: int = 30,
    expected_plan_sha256: str,
    environment: Callable[[str], str | None] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Run one reviewed fetch. The caller has verified the exact approval."""

    from .archive_services import read_archive_id, require_existing_archive_root

    arguments = dict(source_id=source_id, batch_id=batch_id, imap_host=imap_host, imap_port=imap_port,
                     username_ref=username_ref, app_password_ref=app_password_ref, mailbox=mailbox,
                     selection_rule=selection_rule, since_days=since_days, max_messages=max_messages,
                     timeout_seconds=timeout_seconds)
    plan = plan_fetch(archive_root, **arguments)
    if not plan["ok"]:
        return {**plan, "dry_run": False}
    if plan["plan_sha256"] != expected_plan_sha256:
        raise ImapFetchError("imap_fetch_plan_changed")
    root = require_existing_archive_root(archive_root)
    read_env = environment or os.environ.get
    username = read_env(_ENV_REF_RE.fullmatch(username_ref).group(1))
    password = read_env(_ENV_REF_RE.fullmatch(app_password_ref).group(1))
    if not username or not password:
        return {**plan, "dry_run": False, "ok": False, "credential_reads": 2,
                "blockers": ["imap_fetch_credential_unavailable"]}
    output = root.joinpath(*plan["output"].split("/"))
    output.mkdir(parents=True, exist_ok=False)
    items: list[dict[str, Any]] = []
    fetched_bytes = 0
    status = "failed"
    stop_reason: str | None = None
    client = None
    try:
        client = _client_factory(imap_host, imap_port, timeout_seconds)
        if str(client.login(username, password)[0]).upper() != "OK":
            raise ImapFetchError("imap_fetch_login_failed")
        if str(client.select(f'"{mailbox}"', readonly=True)[0]).upper() != "OK":
            raise ImapFetchError("imap_fetch_mailbox_unavailable")
        search_status, search_data = client.uid("search", None, _search_criterion(selection_rule, since_days))
        if str(search_status).upper() != "OK":
            raise ImapFetchError("imap_fetch_search_failed")
        uids: list[bytes] = []
        for chunk in search_data or []:
            if isinstance(chunk, (bytes, str)):
                raw = chunk.encode("ascii", "ignore") if isinstance(chunk, str) else chunk
                uids.extend(part for part in raw.split() if part)
        if selection_rule in {"newest_first", "since_days_window"}:
            uids.reverse()
        uids = uids[:max_messages]
        for index, uid in enumerate(uids, start=1):
            fetch_status, fetch_data = client.uid("fetch", uid, "(BODY.PEEK[])")
            message = None
            for part in fetch_data or []:
                if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], (bytes, bytearray)):
                    message = bytes(part[1])
                    break
            if str(fetch_status).upper() != "OK" or not message:
                stop_reason = "imap_fetch_message_unavailable"
                continue
            name = f"mail-{index:04d}.eml"
            path = output / name
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
            try:
                os.write(descriptor, message)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            fetched_bytes += len(message)
            items.append({
                "item_id": f"mail-{index:04d}",
                "local_path": f"{plan['output']}/{name}",
                "source_role": "primary_source",
                "mime": "message/rfc822",
                "_sha256": "sha256:" + hashlib.sha256(message).hexdigest(),
                "_size": len(message),
            })
        status = "succeeded" if stop_reason is None else "partial"
    except ImapFetchError as exc:
        stop_reason = exc.code
    except Exception:
        stop_reason = "imap_fetch_connection_failed"
    finally:
        username = password = None
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass
    request_relative = None
    if items:
        request = {
            "schema": INTAKE_REQUEST_SCHEMA,
            "batch_id": f"imap-{batch_id}",
            "items": [{key: value for key, value in item.items() if not key.startswith("_")} for item in items],
        }
        request_relative = f"{plan['output']}/source-intake-batch-request.json"
        (root.joinpath(*request_relative.split("/"))).write_text(
            json.dumps(request, indent=2) + "\n", encoding="utf-8")
    now = (clock() if clock else datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "archive_id": read_archive_id(root),
        "plan_sha256": plan["plan_sha256"],
        "source_id": source_id,
        "batch_id": batch_id,
        "status": status,
        "stop_reason": stop_reason,
        "message_count": len(items),
        "total_bytes": fetched_bytes,
        "files": [{"path": item["local_path"], "sha256": item["_sha256"], "size_bytes": item["_size"]} for item in items],
        "server_flags_changed": False,
        "completed_at": now.isoformat().replace("+00:00", "Z"),
    }
    receipt_path = root.joinpath(*RECEIPT_DIR.split("/"), f"{batch_id}.json")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": stop_reason is None,
        "dry_run": False,
        "lifecycle_action": "imap_mailbox_message_fetch",
        "plan_sha256": plan["plan_sha256"],
        "status": status,
        "reason_code": stop_reason or "imap_fetch_completed",
        "blockers": [stop_reason] if stop_reason else [],
        "message_count": len(items),
        "total_bytes": fetched_bytes,
        "output": plan["output"],
        "intake_request": request_relative,
        "receipt_path": f"{RECEIPT_DIR}/{batch_id}.json",
        "server_flags_changed": False,
        "privacy_guards": plan["privacy_guards"],
        "next_step": (
            f"archive source-intake-batch <archive-root> --manifest {request_relative} --dry-run"
            if request_relative else None
        ),
    }


def execute_fetch_approved(
    archive_root: Path | str,
    *,
    reviewed_by: str,
    exact_human_approval_claim: Any,
    expected_plan_sha256: str,
    expected_exact_approval_plan_sha256: str | None,
    expected_exact_approval_target_binding_sha256: str | None,
    **arguments: Any,
) -> dict[str, Any]:
    """Reauthenticate the exact approval for the plan digest, then fetch."""

    from . import archive_services
    from .exact_human_approval_windows import ExactHumanApprovalOperation
    from .operation_approval_binding import OperationApprovalBindingError, plan_digest_approval_binding

    if exact_human_approval_claim is None:
        return archive_services._compound_exact_human_approval_blocked(
            lifecycle_action="imap_mailbox_message_fetch",
        )
    reviewer = archive_services.safe_project_intake_actor_id(reviewed_by)
    if reviewer is None:
        raise archive_services.ArchiveServiceError("imap_fetch_reviewer_invalid")
    root = archive_services.require_existing_archive_root(archive_root)
    try:
        archive_services._require_exact_human_operation_approval(
            root,
            plan_digest_approval_binding(ExactHumanApprovalOperation.imap_mailbox_message_fetch, expected_plan_sha256),
            reviewer_claim=reviewer,
            expected_plan_sha256=expected_exact_approval_plan_sha256,
            expected_target_binding_sha256=expected_exact_approval_target_binding_sha256,
            claim=exact_human_approval_claim,
        )
    except OperationApprovalBindingError as exc:
        raise archive_services.ArchiveServiceError(exc.code) from None
    return execute_fetch(root, expected_plan_sha256=expected_plan_sha256, **arguments)
