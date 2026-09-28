"""Incremental read-only IMAP and MIME extraction for approved fetches."""
from __future__ import annotations

from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
import re
from pathlib import Path
from typing import Any

from . import provider_artifacts as artifacts

STATE_SCHEMA = "wom-kit/imap-uid-state/v1"


@dataclass(frozen=True)
class MimePart:
    mime: str
    path: str
    content: bytes = field(repr=False)
    content_id: str | None = field(default=None, repr=False)
    filename: str | None = field(default=None, repr=False)


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"br", "p", "div", "li", "tr"}:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.chunks.append(data)


def extract_mime(raw: bytes) -> tuple[bytes, tuple[MimePart, ...], tuple[str, ...]]:
    """Keep originals elsewhere; derived text never claims byte fidelity."""
    message = BytesParser(policy=policy.default).parsebytes(raw)
    plain, html, attachments, warnings = [], [], [], set()

    def walk(part, path, depth=0):
        if depth > 50:
            warnings.add("mime_nesting_limit")
            return
        if part.defects:
            warnings.add("mime_parse_defect")
        mime = part.get_content_type()
        attached = part.get_content_disposition() == "attachment" or part.get_filename() is not None
        if mime == "message/rfc822":
            nested = part.get_payload()
            if isinstance(nested, list):
                payload = b"\r\n".join(item.as_bytes(policy=policy.SMTP) for item in nested)
            else:
                payload = part.get_payload(decode=True) or b""
            attachments.append(MimePart(mime, path, payload, str(part.get("Content-ID", "")) or None, part.get_filename()))
            return
        if part.is_multipart():
            for index, child in enumerate(part.iter_parts()):
                walk(child, f"{path}.{index}", depth + 1)
            return
        data = part.get_payload(decode=True)
        if data is None:
            warnings.add("mime_payload_unavailable")
            return
        if attached or not mime.startswith("text/"):
            attachments.append(MimePart(mime, path, data, str(part.get("Content-ID", "")) or None, part.get_filename()))
            return
        charset = part.get_content_charset() or "utf-8"
        try:
            text = data.decode(charset, errors="strict")
        except (LookupError, UnicodeError):
            text = data.decode("utf-8", errors="replace")
            warnings.add("mime_text_decode_fallback")
        if mime == "text/plain":
            plain.append(text)
        elif mime == "text/html":
            parser = _HTMLText()
            parser.feed(text)
            html.append("".join(parser.chunks))
    walk(message, "0")
    return "\n\n".join(plain or html).encode("utf-8"), tuple(attachments), tuple(sorted(warnings))


def scope_identity(arguments: dict) -> str:
    return artifacts.digest(artifacts.canonical({key: arguments[key] for key in
        ("source_id", "imap_host", "imap_port", "username_ref", "mailbox")}))


def state_path(scope: str) -> str:
    return f"workbench/imap-fetch/state/{scope[7:]}.json"


def state_digest(root: Path, scope: str) -> str | None:
    path = artifacts.safe_path(root, state_path(scope))
    return artifacts.digest(path.read_bytes()) if path.exists() else None


def _uid(value: Any) -> str:
    if isinstance(value, bytes):
        value = value.decode("ascii", "strict")
    value = str(value)
    if not re.fullmatch(r"[1-9][0-9]{0,9}", value) or int(value) > 4294967295:
        raise artifacts.ProviderArtifactError("imap_uid_invalid")
    return value


def uidvalidity(client) -> str:
    _kind, values = client.response("UIDVALIDITY")
    if not values or len(values) != 1:
        raise artifacts.ProviderArtifactError("imap_uidvalidity_unavailable")
    return _uid(values[0])


def _record_items(record):
    prefix = "mail-" + record["uidvalidity"] + "-" + record["uid"]
    items = [{"item_id": prefix, "local_path": record["raw"]["path"],
        "source_role": "primary_source", "mime": "message/rfc822"}]
    if record.get("body"):
        items.append({"item_id": prefix + "-body", "local_path": record["body"]["path"],
            "source_role": "derived_context", "mime": "text/plain"})
    items.extend({"item_id": part["item_id"], "local_path": part["path"],
        "source_role": "attachment", "mime": part["mime"]} for part in record.get("parts", []))
    return items


def execute(root: Path, *, arguments: dict, plan: dict, username: str, password: str, factory) -> dict:
    """Called only by execute_fetch after its existing exact approval check."""
    scope = scope_identity(arguments)
    with artifacts.exclusive_run(root, f"workbench/imap-fetch/state/{scope[7:]}.lock"):
        if state_digest(root, scope) != plan.get("uid_state_sha256"):
            raise artifacts.ProviderArtifactError("imap_fetch_state_changed")
        return _execute_locked(root, arguments=arguments, plan=plan, username=username, password=password, factory=factory, scope=scope)


def _execute_locked(root, *, arguments, plan, username, password, factory, scope):
    from .imap_message_fetch import _search_criterion

    relative = state_path(scope)
    state = artifacts.read_json(root, relative) if artifacts.safe_path(root, relative).exists() else {
        "schema": STATE_SCHEMA, "scope_sha256": scope, "epochs": {}}
    if state.get("schema") != STATE_SCHEMA or state.get("scope_sha256") != scope or not isinstance(state.get("epochs"), dict):
        raise artifacts.ProviderArtifactError("imap_uid_state_invalid")
    account = artifacts.digest(username.encode("utf-8"))
    if state.get("account_sha256") not in {None, account}:
        raise artifacts.ProviderArtifactError("imap_authenticated_account_changed")
    state["account_sha256"] = account
    output = plan["output"]
    request_path = output + "/source-intake-batch-request.json"
    run_path = output + "/sync-run.json"
    run = artifacts.read_json(root, run_path) if arguments.get("resume") and artifacts.safe_path(root, run_path).exists() else {
        "scope_sha256": scope, "items": [], "occurrences": [], "warnings": []}
    if run.get("scope_sha256") != scope:
        raise artifacts.ProviderArtifactError("imap_resume_scope_changed")
    client, reason, fetched, remaining, failed_count, cached_count = None, None, 0, 0, 0, 0
    try:
        client = factory(arguments["imap_host"], arguments["imap_port"], arguments["timeout_seconds"])
        if str(client.login(username, password)[0]).upper() != "OK":
            raise artifacts.ProviderArtifactError("imap_fetch_login_failed")
        if str(client.select('"' + arguments["mailbox"] + '"', readonly=True)[0]).upper() != "OK":
            raise artifacts.ProviderArtifactError("imap_fetch_mailbox_unavailable")
        epoch = uidvalidity(client)
        completed = state["epochs"].setdefault(epoch, {})
        if not isinstance(completed, dict):
            raise artifacts.ProviderArtifactError("imap_uid_state_invalid")
        status, chunks = client.uid("search", None, _search_criterion(arguments["selection_rule"], arguments["since_days"]))
        if str(status).upper() != "OK":
            raise artifacts.ProviderArtifactError("imap_fetch_search_failed")
        uids = sorted({_uid(item) for chunk in chunks or [] if isinstance(chunk, bytes) for item in chunk.split()}, key=int)
        pending, cached = [], []
        for uid in uids:
            record = completed.get(uid)
            if record and arguments.get("sync") and (not arguments.get("extract_mime") or record.get("mime_extracted")):
                blobs = [record["raw"], *record.get("parts", [])]
                if record.get("body"):
                    blobs.append(record["body"])
                for blob in blobs:
                    path = artifacts.safe_path(root, blob["path"])
                    if not path.exists() or artifacts.digest(path.read_bytes()) != blob["sha256"]:
                        raise artifacts.ProviderArtifactError("imap_completed_source_missing_or_changed")
                cached.append(record)
            else:
                pending.append(uid)
        if arguments["selection_rule"] in {"newest_first", "since_days_window"}:
            pending.reverse()
            cached.reverse()
        if not pending and not run["items"]:
            # Download completion is not canonical capture completion. Rebind
            # the bounded current selection to the ordinary authenticated
            # intake/capture path, without fetching the bytes again.
            selected = cached[:arguments["max_messages"]]
            run["occurrences"] = selected
            run["items"] = [item for record in selected for item in _record_items(record)]
            cached_count = len(selected)
        remaining = max(0, len(pending) - arguments["max_messages"])
        for uid in pending[:arguments["max_messages"]]:
            status, parts = client.uid("fetch", uid.encode("ascii"), "(BODY.PEEK[])")
            raw = next((bytes(p[1]) for p in parts or [] if isinstance(p, tuple) and len(p) >= 2 and isinstance(p[1], bytes)), None)
            if str(status).upper() != "OK" or raw is None:
                reason = "imap_fetch_message_unavailable"
                failed_count += 1
                continue
            blob = artifacts.write_blob(root, raw, "eml")
            prefix = "mail-" + epoch + "-" + uid
            items = [{"item_id": prefix, "local_path": blob["path"], "source_role": "primary_source", "mime": "message/rfc822"}]
            record = {"uid": uid, "uidvalidity": epoch, "raw": blob, "parts": [], "mime_extracted": bool(arguments.get("extract_mime"))}
            if arguments.get("extract_mime"):
                body, attachments, warnings = extract_mime(raw)
                run["warnings"] = sorted(set(run["warnings"]) | set(warnings))
                if body:
                    text = artifacts.write_blob(root, body, "txt")
                    items.append({"item_id": prefix + "-body", "local_path": text["path"], "source_role": "derived_context", "mime": "text/plain"})
                    record["body"] = text
                for ordinal, attachment in enumerate(attachments):
                    part = artifacts.write_blob(root, attachment.content, "bin")
                    item_id = prefix + "-attachment-" + str(ordinal)
                    items.append({"item_id": item_id, "local_path": part["path"], "source_role": "attachment", "mime": attachment.mime})
                    record["parts"].append({**part, "mime": attachment.mime, "mime_path": attachment.path, "item_id": item_id,
                        "content_id": attachment.content_id, "filename": attachment.filename, "parent_item_id": prefix})
            known = {item["item_id"] for item in run["items"]}
            run["items"].extend(item for item in items if item["item_id"] not in known)
            # A resumed raw-only run may add MIME extraction. Replace its
            # occurrence so the new attachment/body binding is recoverable.
            run["occurrences"] = [item for item in run["occurrences"]
                if not (item["uid"] == uid and item["uidvalidity"] == epoch)]
            run["occurrences"].append(record)
            # Durable run/intake first: a completed UID always has a recoverable
            # intake request, even if the process exits before the next UID.
            run["intake_requests"], run["intake_item_aliases"] = artifacts.write_intake_requests(
                root, output, "imap-" + arguments["batch_id"], run["items"])
            artifacts.write_json(root, run_path, run)
            completed[uid] = record
            artifacts.write_json(root, relative, state)
            fetched += 1
        # A successfully inspected empty mailbox still needs a durable receipt
        # for the approved zero-item completion. Never create an empty intake.
        run["intake_requests"], run["intake_item_aliases"] = artifacts.write_intake_requests(
            root, output, "imap-" + arguments["batch_id"], run["items"])
        artifacts.write_json(root, run_path, run)
    except artifacts.ProviderArtifactError as exc:
        reason = exc.code
    except Exception:
        reason = "imap_fetch_connection_failed"
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass
    return {"ok": reason is None, "dry_run": False, "lifecycle_action": "imap_mailbox_message_fetch",
        "plan_sha256": plan["plan_sha256"], "status": "partial" if (reason or remaining) and run["items"] else "failed" if reason else "succeeded",
        "reason_code": reason or "imap_fetch_completed", "blockers": [reason] if reason else [],
        "message_count": fetched, "cached_message_count": cached_count,
        "capture_scope_message_count": len(run["occurrences"]), "remaining_message_count": remaining, "output": output,
        "collection_complete": reason is None and remaining == 0, "pending_message_count": remaining + failed_count,
        "intake_request": request_path if run["items"] else None,
        "receipt_path": run_path if artifacts.safe_path(root, run_path).exists() else None,
        "intake_requests": run.get("intake_requests", []),
        "server_flags_changed": False, "warnings": run["warnings"], "capture_completed": False,
        "next_step": f"archive source-intake-batch <archive-root> --manifest {request_path} --dry-run" if run["items"] else None}
