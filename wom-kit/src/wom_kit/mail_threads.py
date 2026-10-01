"""v0.4.57 (owner idea 2026-10-01): archived mail is also readable as threads, per mailbox account.

Mail is kept as whole ``.eml`` objets (imap-mailbox-message-fetch); every
header (From, To, Cc, Date, Message-ID, In-Reply-To, References) is inside the
bytes, but nothing presented a conversation as one. Following the owner's
decision, threads are a DERIVED SNAPSHOT, like the search, relation and title
snapshots:

* rebuilt from the immutable mail objets on demand (``mail-threads --build``),
  never appended in place and never a zet; the objets stay the evidence and a
  person may mint a zet from a thread through the normal draft and mint flow;
* grouped by RFC 5322 Message-ID / In-Reply-To / References (the way Gmail and
  other providers thread), with a subject-and-participants fallback for mail
  without those headers; the same message fetched twice is counted once;
* grouped per receiving mailbox account: the account a fetch recorded
  (``profiles/local/mail-accounts``, private) or the mail's own Delivered-To /
  X-Original-To / From / To headers;
* each thread is one Markdown text record under
  ``db/mail-threads/<generation>/<account>/`` with participants and every
  message in date order (sender, recipients, date, subject, body text with
  quoted lines folded, the objet it came from, attachment names). Old
  generations are deleted like other snapshots. The folder ignores itself in
  Git; command output never echoes addresses, subjects or bodies.
"""

from __future__ import annotations

import email
import email.policy
import hashlib
import json
import os
import re
import shutil
import stat
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any

SCHEMA = "wom-kit/mail-threads-generation/v0.1"
RESULT_SCHEMA = "wom-kit/mail-threads-result/v0.1"
ACCOUNT_RECORD_SCHEMA = "wom-kit/mail-account-record/v0.1"
GENERATIONS_RELATIVE = ("db", "mail-threads")
ACCOUNTS_RELATIVE = ("profiles", "local", "mail-accounts")
MAX_MESSAGE_BYTES = 64 * 1024 * 1024
MAX_BODY_CHARS = 200_000
KEEP_GENERATIONS = 2
GENERATION_MIN_AGE_SECONDS = 3600
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_SUBJECT_PREFIX_RE = re.compile(r"^\s*((re|fw|fwd|aw|sv|vs|답장|회신|전달)\s*(\[\d+\])?\s*:\s*)+", re.IGNORECASE)
_SAFE_SOURCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,99}$")
_ADDRESS_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


# --------------------------------------------------------------------------- accounts

def record_mail_account(root: Path, *, source_id: str, account_address: str, mailbox: str) -> None:
    """Called by a fetch: remember which mailbox account a source reads (private, never echoed)."""

    address = str(account_address or "").strip().lower()
    if not _SAFE_SOURCE_RE.fullmatch(str(source_id or "")) or not _ADDRESS_RE.fullmatch(address):
        return
    folder = Path(root).joinpath(*ACCOUNTS_RELATIVE)
    folder.mkdir(parents=True, exist_ok=True)
    record = {"schema": ACCOUNT_RECORD_SCHEMA, "source_id": source_id, "account_address": address,
              "mailbox": str(mailbox or ""), "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    temporary = folder / f".{source_id}.{uuid.uuid4().hex}.tmp"
    temporary.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, folder / f"{source_id}.json")


def _known_accounts(root: Path) -> set[str]:
    folder = Path(root).joinpath(*ACCOUNTS_RELATIVE)
    accounts: set[str] = set()
    if folder.is_dir():
        for path in folder.glob("*.json"):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(record, dict) and record.get("schema") == ACCOUNT_RECORD_SCHEMA:
                address = str(record.get("account_address") or "").lower()
                if _ADDRESS_RE.fullmatch(address):
                    accounts.add(address)
    return accounts


# --------------------------------------------------------------------------- parsing

def _addresses(message: Any, *names: str) -> list[tuple[str, str]]:
    values = []
    for name in names:
        values.extend(str(value) for value in message.get_all(name, []) or [])
    result = []
    for display, address in getaddresses(values):
        address = address.strip().lower()
        if _ADDRESS_RE.fullmatch(address):
            result.append((display.strip(), address))
    return result


def _ids(value: Any) -> list[str]:
    return [item.lower() for item in re.findall(r"<([^<>\s]+)>", str(value or ""))]


def _body_text(message: Any) -> tuple[str, list[str]]:
    plain: list[str] = []
    html: list[str] = []
    attachments: list[str] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        disposition = str(part.get_content_disposition() or "")
        filename = part.get_filename()
        if disposition == "attachment" or (filename and disposition != "inline"):
            attachments.append(str(filename or "unnamed"))
            continue
        content_type = part.get_content_type()
        if content_type not in ("text/plain", "text/html"):
            continue
        try:
            text = part.get_content()
        except Exception:  # noqa: BLE001 - undecodable parts are skipped, the objet keeps them
            continue
        (plain if content_type == "text/plain" else html).append(str(text))
    if plain:
        body = "\n".join(plain)
    elif html:
        body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", "\n".join(html), flags=re.IGNORECASE | re.DOTALL)
        body = re.sub(r"<br\s*/?>|</p>|</div>", "\n", body, flags=re.IGNORECASE)
        body = re.sub(r"<[^>]+>", "", body)
        body = re.sub(r"&nbsp;", " ", body)
    else:
        body = ""
    return body.replace("\r\n", "\n").strip()[:MAX_BODY_CHARS], attachments


def _fold_quotes(body: str) -> tuple[str, int]:
    kept, folded = [], 0
    for line in body.split("\n"):
        if line.lstrip().startswith(">"):
            folded += 1
            continue
        kept.append(line)
    return "\n".join(kept).strip(), folded


def _parse(raw: bytes, object_id: str) -> dict[str, Any] | None:
    try:
        message = email.message_from_bytes(raw, policy=email.policy.default)
    except Exception:  # noqa: BLE001
        return None
    if not message.keys():
        return None
    try:
        date = parsedate_to_datetime(str(message.get("Date"))) if message.get("Date") else None
        if date is not None and date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        date = None
    message_ids = _ids(message.get("Message-ID"))
    body, attachments = _body_text(message)
    return {
        "object_id": object_id,
        "message_id": message_ids[0] if message_ids else f"objet:{object_id}",
        "references": _ids(message.get("References")) + _ids(message.get("In-Reply-To")),
        "subject": str(message.get("Subject") or "").strip(),
        "from": _addresses(message, "From"),
        "to": _addresses(message, "To"),
        "cc": _addresses(message, "Cc"),
        "delivered_to": [address for _display, address in _addresses(message, "Delivered-To", "X-Original-To")],
        "date": date,
        "body": body,
        "attachments": attachments,
    }


def _account_for(message: dict[str, Any], known: set[str]) -> str:
    candidates = [*message["delivered_to"], *(a for _d, a in message["from"]),
                  *(a for _d, a in message["to"]), *(a for _d, a in message["cc"])]
    for address in candidates:
        if address in known:
            return address
    if message["delivered_to"]:
        return message["delivered_to"][0]
    return "unknown-account"


# --------------------------------------------------------------------------- collection

def _mail_objects(root: Path) -> list[tuple[str, Path | None]]:
    from . import archive_services

    found: dict[str, Path | None] = {}
    for row in archive_services.load_manifest_records(root):
        if not isinstance(row, dict):
            continue
        provenance = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
        name = str(provenance.get("original_filename") or row.get("logical_key") or "")
        if str(row.get("mime") or "").lower() != "message/rfc822" and not name.lower().endswith(".eml"):
            continue
        object_id = str(row.get("object_id") or "")
        digest = object_id.removeprefix("sha256:")
        if not _DIGEST_RE.fullmatch(digest):
            continue
        path = root / "objects" / "sha256" / digest[:2] / digest
        found.setdefault(object_id, path)
    return sorted(found.items())


def _collect(root: Path) -> dict[str, Any]:
    known = _known_accounts(root)
    messages: list[dict[str, Any]] = []
    counts = {"mail_objet_count": 0, "local_bytes_absent_count": 0, "unreadable_count": 0, "duplicate_count": 0}
    for object_id, path in _mail_objects(root):
        counts["mail_objet_count"] += 1
        try:
            info = os.lstat(path)
        except OSError:
            counts["local_bytes_absent_count"] += 1
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_MESSAGE_BYTES:
            counts["unreadable_count"] += 1
            continue
        try:
            raw = Path(path).read_bytes()
        except OSError:
            counts["local_bytes_absent_count"] += 1
            continue
        if hashlib.sha256(raw).hexdigest() != object_id.removeprefix("sha256:"):
            counts["unreadable_count"] += 1
            continue
        parsed = _parse(raw, object_id)
        if parsed is None:
            counts["unreadable_count"] += 1
            continue
        parsed["account"] = _account_for(parsed, known)
        messages.append(parsed)
    threads: list[dict[str, Any]] = []
    by_account: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for message in messages:
        by_account[message["account"]].append(message)
    for account, group in sorted(by_account.items()):
        unique: dict[str, dict[str, Any]] = {}
        for message in sorted(group, key=lambda item: item["object_id"]):
            if message["message_id"] in unique:
                counts["duplicate_count"] += 1
                continue
            unique[message["message_id"]] = message
        threads.extend(_thread(account, list(unique.values())))
    threads.sort(key=lambda item: (item["account"], item["first_date"], item["thread_id"]))
    return {"threads": threads, "counts": counts, "account_count": len(by_account), "message_count": len(messages)}


def _thread(account: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parent: dict[str, str] = {}

    def find(key: str) -> str:
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    referenced: set[str] = set()
    for message in messages:
        find(message["message_id"])
        for reference in message["references"]:
            union(message["message_id"], reference)
            referenced.add(reference)
    # Fallback for mail without threading headers: same normalised subject and
    # the same set of participants.
    fallback: dict[tuple[str, frozenset[str]], str] = {}
    for message in messages:
        if message["references"] or message["message_id"] in referenced:
            continue
        subject = _SUBJECT_PREFIX_RE.sub("", message["subject"]).strip().lower()
        if not subject:
            continue
        people = frozenset(a for _d, a in [*message["from"], *message["to"], *message["cc"]])
        key = (subject, people)
        if key in fallback:
            union(fallback[key], message["message_id"])
        else:
            fallback[key] = message["message_id"]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for message in messages:
        groups[find(message["message_id"])].append(message)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    threads = []
    for root_id, members in groups.items():
        members.sort(key=lambda item: (item["date"] or epoch, item["object_id"]))
        first = members[0]
        threads.append({
            "account": account,
            "thread_id": hashlib.sha256(f"{account}\0{root_id}".encode("utf-8")).hexdigest()[:16],
            "subject": _SUBJECT_PREFIX_RE.sub("", first["subject"]).strip() or "(제목 없음)",
            "first_date": (first["date"] or epoch).isoformat(),
            "messages": members,
        })
    return threads


# --------------------------------------------------------------------------- rendering

def _who(pairs: list[tuple[str, str]]) -> str:
    return ", ".join(f"{display} <{address}>" if display else address for display, address in pairs) or "-"


def _render(thread: dict[str, Any]) -> str:
    members = thread["messages"]
    people: list[str] = []
    for message in members:
        for _display, address in [*message["from"], *message["to"], *message["cc"]]:
            if address not in people:
                people.append(address)
    dates = [message["date"] for message in members if message["date"] is not None]
    span = f"{min(dates):%Y-%m-%d} – {max(dates):%Y-%m-%d}" if dates else "날짜 없음"
    lines = [
        f"# {thread['subject']}",
        "",
        f"- 메일함 계정: {thread['account']}",
        f"- 참여자: {', '.join(people) or '-'}",
        f"- 메일 수: {len(members)} · 기간: {span}",
        "- 이 문서는 원본 메일 오브제에서 다시 만든 쓰레드 보기입니다. 근거는 각 메일의 원본 오브제입니다.",
        "",
    ]
    for index, message in enumerate(members, start=1):
        when = f"{message['date']:%Y-%m-%d %H:%M %z}" if message["date"] else "날짜 없음"
        body, folded = _fold_quotes(message["body"])
        lines += [
            f"## {index}. {when} · {_who(message['from'])}",
            "",
            f"- 받는 사람: {_who(message['to'])}",
        ]
        if message["cc"]:
            lines.append(f"- 참조: {_who(message['cc'])}")
        lines += [
            f"- 제목: {message['subject'] or '(제목 없음)'}",
            f"- 원본 오브제: {message['object_id']}",
        ]
        if message["attachments"]:
            lines.append(f"- 첨부 {len(message['attachments'])}개: {', '.join(message['attachments'])}")
        lines += ["", body or "(본문 없음)"]
        if folded:
            lines += ["", f"(이전 메일 인용 {folded}줄은 접었습니다. 원본 오브제에 그대로 있습니다.)"]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _slug(account: str) -> str:
    return re.sub(r"[^a-z0-9._-]", "_", account.replace("@", "_at_").lower())[:120] or "unknown-account"


def _rendered_files(threads: list[dict[str, Any]]) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for thread in threads:
        date = thread["first_date"][:10].replace("-", "")
        relative = f"{_slug(thread['account'])}/{date}-{thread['thread_id']}.md"
        files[relative] = _render(thread).encode("utf-8")
    return files


# --------------------------------------------------------------------------- generations

def _generations_root(root: Path, *, create: bool = False) -> Path:
    folder = Path(root).joinpath(*GENERATIONS_RELATIVE)
    if create:
        from . import archive_services

        folder.mkdir(parents=True, exist_ok=True)
        archive_services.ensure_derived_directory_ignored(folder)
    return folder


def _prune(folder: Path, keep: str) -> int:
    removed = 0
    now = time.time()
    entries = []
    for entry in os.scandir(folder):
        if entry.is_dir(follow_symlinks=False) and _DIGEST_RE.fullmatch(entry.name) and entry.name != keep:
            entries.append((entry.stat(follow_symlinks=False).st_mtime, Path(entry.path)))
        elif entry.name.endswith(".building") and now - entry.stat(follow_symlinks=False).st_mtime > 86400:
            shutil.rmtree(entry.path, ignore_errors=True)
            removed += 1
    entries.sort(reverse=True)
    for index, (mtime, path) in enumerate(entries):
        if index < KEEP_GENERATIONS - 1 or now - mtime <= GENERATION_MIN_AGE_SECONDS:
            continue
        shutil.rmtree(path, ignore_errors=True)
        removed += 0 if path.exists() else 1
    return removed


def _summary(collected: dict[str, Any]) -> dict[str, Any]:
    threads = collected["threads"]
    return {
        "account_count": collected["account_count"],
        "thread_count": len(threads),
        "message_count": collected["message_count"] - collected["counts"]["duplicate_count"],
        "multi_message_thread_count": sum(1 for thread in threads if len(thread["messages"]) > 1),
        **collected["counts"],
    }


def plan_mail_threads(archive_root: Path | str) -> dict[str, Any]:
    """Read-only: what a build would produce, counts only."""

    from . import archive_services

    root = archive_services.require_existing_archive_root(archive_root)
    collected = _collect(root)
    files = _rendered_files(collected["threads"])
    generation = hashlib.sha256(json.dumps(
        {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())}, sort_keys=True).encode()).hexdigest()
    return {"schema": RESULT_SCHEMA, "ok": True, "dry_run": True, "lifecycle_action": "mail_threads",
            "generation": generation, **_summary(collected),
            "location": "/".join(GENERATIONS_RELATIVE) + "/" + generation,
            "derived_rebuildable": True, "objets_changed": False,
            "next_safe_actions": ["Run mail-threads --build to write the thread snapshot; it is rebuilt from the mail objets and never changes them."],
            "addresses_echoed": False, "subjects_echoed": False, "bodies_echoed": False}


def build_mail_threads(archive_root: Path | str) -> dict[str, Any]:
    """Write one snapshot generation of thread text records and point latest at it."""

    from . import archive_services

    root = archive_services.require_existing_archive_root(archive_root)
    collected = _collect(root)
    files = _rendered_files(collected["threads"])
    generation = hashlib.sha256(json.dumps(
        {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())}, sort_keys=True).encode()).hexdigest()
    folder = _generations_root(root, create=True)
    target = folder / generation
    reused = target.is_dir()
    if not reused:
        building = folder / f"{uuid.uuid4().hex}.building"
        try:
            for relative, raw in files.items():
                path = building.joinpath(*relative.split("/"))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            index = {"schema": SCHEMA, "generation": generation,
                     "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "threads": [{"file": relative} for relative in sorted(files)], **_summary(collected)}
            building.mkdir(parents=True, exist_ok=True)
            (building / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(building, target)
        finally:
            if building.exists():
                shutil.rmtree(building, ignore_errors=True)
    pointer = folder / f".{uuid.uuid4().hex}.pointer"
    pointer.write_text(json.dumps({"schema": SCHEMA, "generation": generation}) + "\n", encoding="utf-8")
    os.replace(pointer, folder / "latest.json")
    pruned = _prune(folder, generation)
    return {"schema": RESULT_SCHEMA, "ok": True, "dry_run": False, "lifecycle_action": "mail_threads",
            "generation": generation, "reused": reused, "pruned_generations": pruned, **_summary(collected),
            "location": "/".join(GENERATIONS_RELATIVE) + "/" + generation,
            "derived_rebuildable": True, "objets_changed": False,
            "next_safe_actions": ["Read the thread text records under location; to keep a conversation as knowledge, draft a zet from it and cite the mail objets."],
            "addresses_echoed": False, "subjects_echoed": False, "bodies_echoed": False}


__all__ = ["build_mail_threads", "plan_mail_threads", "record_mail_account"]
