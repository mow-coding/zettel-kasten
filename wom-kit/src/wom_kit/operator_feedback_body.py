"""Approval-bound, privacy-safe operator-feedback body preservation.

This module is intentionally a companion to the existing operator-feedback
metadata lifecycle.  It owns only one reviewed Markdown body and its body
receipt; it never creates or updates ``ops/feedback/<id>.yml`` and it never
performs external delivery.

The public projection is content-free.  A rejected title, section value, local
request path, or matched private value is never copied into a result or error.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import subprocess
import threading
from typing import Any, Mapping

import yaml


REQUEST_SCHEMA = "wom-kit/operator-feedback-body-request/v0.1"
PLAN_SCHEMA = "wom-kit/operator-feedback-body-plan/v0.1"
RECEIPT_SCHEMA = "wom-kit/operator-feedback-body-receipt/v0.1"
REVISION_RECEIPT_SCHEMA = "wom-kit/operator-feedback-body-revision-receipt/v0.1"
SUPERSESSION_RECEIPT_SCHEMA = (
    "wom-kit/operator-feedback-body-supersession-receipt/v0.1"
)
RESULT_SCHEMA = "wom-kit/operator-feedback-body-result/v0.1"
CLI_REQUIRE_ARCHIVE_MARKER = True

REQUEST_PREFIX = "profiles/local/operator-feedback/requests"
REQUEST_PATH_PATTERN = "profiles/local/operator-feedback/requests/<name>.json"
BODY_PREFIX = "ops/feedback/letters"
RECEIPT_PREFIX = "receipts/operator-feedback/body"
REVISION_PREFIX = f"{RECEIPT_PREFIX}/revisions"
SUPERSESSION_PREFIX = f"{RECEIPT_PREFIX}/supersessions"
RECORD_PREFIX = "ops/feedback"

MAX_REQUEST_BYTES = 256 * 1024
MAX_BODY_BYTES = 256 * 1024
MAX_RECORD_BYTES = 256 * 1024
MAX_RECEIPT_BYTES = 64 * 1024
MAX_GITIGNORE_BYTES = 256 * 1024

REQUIRED_SECTIONS = (
    "environment",
    "task",
    "observed_failure",
    "suspected_cause",
    "requested_resolution",
    "reproduction",
)
REQUEST_KEYS = {"schema", "feedback_id", "title", "sections"}
SECTION_KEYS = set(REQUIRED_SECTIONS)
RECEIPT_KEYS = {
    "schema",
    "feedback_id",
    "feedback_ref",
    "body_path",
    "body_utf8_bytes",
    "plan_sha256",
    "request_sha256",
    "reviewed_by",
    "approved_at",
}
REVISION_RECEIPT_KEYS = {
    "schema",
    "feedback_id",
    "prior_feedback_ref",
    "revised_feedback_ref",
    "body_path",
    "prior_body_snapshot_path",
    "prior_record_sha256",
    "plan_sha256",
    "request_sha256",
    "reviewed_by",
    "approved_at",
}
SUPERSESSION_RECEIPT_KEYS = {
    "schema",
    "superseded_feedback_id",
    "superseding_feedback_id",
    "superseded_feedback_ref",
    "superseding_feedback_ref",
    "superseded_status",
    "superseded_record_sha256",
    "superseding_body_path",
    "plan_sha256",
    "request_sha256",
    "reviewed_by",
    "approved_at",
}
COMPOSE_INTENTS = ("create", "revise", "supersede")
IMMUTABLE_FEEDBACK_STATUSES = frozenset(
    {"delivered", "acknowledged", "resolved", "archived"}
)

FEEDBACK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,120}$")
REQUEST_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.json$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FEEDBACK_REF_RE = re.compile(r"^feedback-body-sha256:[0-9a-f]{64}$")
REVIEWER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}$")
TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?Z$"
)

REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

SECRET_VALUE_RE = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|secret|token|password|credential|"
    r"aws_secret_access_key)\s*[:=]\s*['\"]?[^\s'\"]{8,}"
    r"|-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|\bAKIA[0-9A-Z]{16}\b"
    r"|\b(?:github_pat_|ghp_)[A-Za-z0-9_]{20,}\b"
    r"|\bsk-[A-Za-z0-9_-]{8,}\b"
    r"|\b(?:secret|ntn)_[A-Za-z0-9_-]{12,}\b"
    r"|\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9._~+/-]{8,}"
    r"|\bBearer\s+[A-Za-z0-9._~+/-]{16,}"
    r"|\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
    r"|\b(?:xox[baprs]-|glpat-)[A-Za-z0-9_-]{12,}\b"
    r"|\bAIza[A-Za-z0-9_-]{20,}\b"
)
PROVIDER_URL_RE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]{1,15}://[^\s<>\"']+")
EMAIL_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@"
    r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9.-])"
)
WINDOWS_ABSOLUTE_PATH_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:[A-Z]:[\\/]|\\\\[^\\/\s]+[\\/][^\s]+)"
)
POSIX_ABSOLUTE_PATH_RE = re.compile(
    r"(?m)(?:^|[\s(])/(?:Users|home|var|tmp|etc|opt|mnt|srv)/[^\s)]+"
)
PHONE_LIKE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[ .-]?)?(?:\(?\d{2,4}\)?[ .-])"
    r"\d{3,4}[ .-]\d{4}(?!\d)"
    r"|(?<!\d)0(?:1[016789]|2|[3-6][1-5])\d{7,8}(?!\d)"
)

MARKER = "<!-- wom-kit/operator-feedback-body/v0.1 -->"
STRUCTURE_LINES = (
    "## 1. 환경",
    "## 2. 수행 작업",
    "## 3. 관찰된 실패와 추정 원인",
    "### 관찰된 실패 (사실)",
    "### 추정 원인 (추정)",
    "## 4. 바라는 해결",
    "## 5. 재현",
)

_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class _BodyContractError(RuntimeError):
    """Internal exception carrying one content-free reason code."""

    def __init__(self, code: str) -> None:
        self.code = code if re.fullmatch(r"[a-z0-9_]+", str(code or "")) else "feedback_body_failed"
        super().__init__(self.code)


@dataclass(repr=False)
class _PreparedPlan:
    root: Path = field(repr=False)
    request_relative: str = field(repr=False)
    request_sha256: str
    feedback_id: str
    title: str = field(repr=False)
    sections: dict[str, str] = field(repr=False)
    section_summary: dict[str, dict[str, Any]]
    body_bytes: bytes = field(repr=False)
    body_digest: str
    feedback_ref: str
    proposed_relative_path: str
    plan_sha256: str
    intent: str = "create"
    expected_body_sha256: str | None = None
    prior_body_bytes: bytes | None = field(default=None, repr=False)
    prior_record_sha256: str | None = None
    prior_status: str | None = None
    supersedes_feedback_id: str | None = None
    revision_resume_pending: bool = False


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        stat.S_ISLNK(info.st_mode)
        or (REPARSE_FLAG and getattr(info, "st_file_attributes", 0) & REPARSE_FLAG)
    )


def _fail(code: str) -> _BodyContractError:
    return _BodyContractError(code)


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise _fail("feedback_body_request_invalid") from None


def _validated_root(
    archive_root: Path | str,
    *,
    require_archive_marker: bool = False,
) -> Path:
    supplied = Path(archive_root)
    if not supplied.is_absolute():
        supplied = Path(os.path.abspath(os.fspath(supplied)))
    try:
        info = os.lstat(supplied)
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise _fail("feedback_body_archive_root_unsafe")
        root = supplied.resolve(strict=True)
    except _BodyContractError:
        raise
    except OSError:
        raise _fail("feedback_body_archive_root_unavailable") from None
    if require_archive_marker:
        try:
            marker = os.lstat(root / "archive.yml")
        except OSError:
            raise _fail("feedback_body_archive_root_invalid") from None
        if _is_reparse(marker) or not stat.S_ISREG(marker.st_mode):
            raise _fail("feedback_body_archive_root_invalid")
    return root


def _archive_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise _fail("feedback_body_internal_path_invalid")
    candidate = root.joinpath(*parts)
    try:
        candidate.relative_to(root)
    except ValueError:
        raise _fail("feedback_body_internal_path_invalid") from None
    return candidate


def _normalize_request_path(root: Path, request_path: Path | str) -> str:
    supplied = Path(request_path)
    if supplied.is_absolute():
        absolute = Path(os.path.abspath(os.fspath(supplied)))
        try:
            relative_path = absolute.relative_to(root)
        except ValueError:
            raise _fail("feedback_body_request_path_invalid") from None
    else:
        relative_path = supplied
    parts = relative_path.parts
    if any(part in {"", ".", ".."} for part in parts):
        raise _fail("feedback_body_request_path_invalid")
    relative = PurePosixPath(*parts).as_posix()
    pure = PurePosixPath(relative)
    if (
        pure.parent.as_posix() != REQUEST_PREFIX
        or REQUEST_FILE_RE.fullmatch(pure.name) is None
        or ":" in relative
    ):
        raise _fail("feedback_body_request_path_invalid")
    return relative


def _read_exact_bytes(
    root: Path,
    path: Path,
    *,
    maximum: int,
    missing_code: str,
    invalid_code: str,
) -> bytes:
    """Read one regular file through a stable, non-following descriptor."""

    try:
        relative = path.relative_to(root)
    except ValueError:
        raise _fail(invalid_code) from None

    current = root
    for part in relative.parts:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            raise _fail(missing_code) from None
        except OSError:
            raise _fail(invalid_code) from None
        if _is_reparse(info):
            raise _fail(invalid_code)
        if current != path and not stat.S_ISDIR(info.st_mode):
            raise _fail(invalid_code)

    try:
        before = os.lstat(path)
    except FileNotFoundError:
        raise _fail(missing_code) from None
    except OSError:
        raise _fail(invalid_code) from None
    if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
        raise _fail(invalid_code)
    if before.st_size <= 0 or before.st_size > maximum:
        raise _fail(invalid_code)

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            _is_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_size != before.st_size
            or (before.st_ino and opened.st_ino and before.st_ino != opened.st_ino)
            or (before.st_dev and opened.st_dev and before.st_dev != opened.st_dev)
        ):
            raise _fail(invalid_code)
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                raise _fail(invalid_code)
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise _fail(invalid_code)
        after = os.lstat(path)
        if (
            _is_reparse(after)
            or not stat.S_ISREG(after.st_mode)
            or after.st_size != opened.st_size
            or (after.st_ino and opened.st_ino and after.st_ino != opened.st_ino)
            or (after.st_dev and opened.st_dev and after.st_dev != opened.st_dev)
        ):
            raise _fail(invalid_code)
        return b"".join(chunks)
    except _BodyContractError:
        raise
    except OSError:
        raise _fail(invalid_code) from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _require_effective_gitignore(root: Path, request_relative: str) -> None:
    raw = _read_exact_bytes(
        root,
        _archive_path(root, ".gitignore"),
        maximum=MAX_GITIGNORE_BYTES,
        missing_code="feedback_body_request_not_ignored",
        invalid_code="feedback_body_request_not_ignored",
    )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        raise _fail("feedback_body_request_not_ignored") from None
    if "\x00" in text:
        raise _fail("feedback_body_request_not_ignored")

    # Require WOM's exact private-profile boundary. Python fnmatch is not a
    # Git wildmatch substitute because its ``*`` can cross slash boundaries.
    local_ignore_seen = False
    local_reincluded = False
    for raw_line in text.splitlines():
        # Do not strip or reinterpret backslashes: both change Git pattern
        # meaning and could promote a non-ignore line into private authority.
        line = raw_line
        if not line or line.startswith("#"):
            continue
        if line in {
            "profiles/local/",
            "/profiles/local/",
            "profiles/local",
            "/profiles/local",
        }:
            local_ignore_seen = True
            local_reincluded = False
            continue
        if not local_ignore_seen or not line.startswith("!"):
            continue
        # Full Git wildmatch includes escapes, bracket classes, and trailing
        # space rules. Conservatively reject every later negation rather than
        # risk accepting a request Git would re-include.
        local_reincluded = True
    if not local_ignore_seen or local_reincluded:
        raise _fail("feedback_body_request_not_ignored")

    # An ignore rule does not make an already tracked file private.  When the
    # archive lives in a Git worktree, require the exact request path to be
    # absent from the index as well.  Non-Git archives keep the literal
    # profiles/local boundary above.
    git_admin_present = False
    for candidate_root in (root, *root.parents):
        try:
            os.lstat(candidate_root / ".git")
        except FileNotFoundError:
            continue
        except OSError:
            raise _fail("feedback_body_request_not_ignored") from None
        git_admin_present = True
        break
    if not git_admin_present:
        return

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        tracked = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--error-unmatch",
                "--",
                request_relative,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.SubprocessError):
        raise _fail("feedback_body_request_not_ignored") from None
    if tracked.returncode == 0:
        raise _fail("feedback_body_request_not_ignored")
    if tracked.returncode != 1:
        raise _fail("feedback_body_request_not_ignored")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _fail("feedback_body_request_invalid")
        result[key] = value
    return result


def _parse_request(raw: bytes) -> Mapping[str, Any]:
    try:
        text = raw.decode("utf-8")
        if text.startswith("\ufeff"):
            raise _fail("feedback_body_request_invalid")
        document = json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
    except _BodyContractError:
        raise
    except (UnicodeError, json.JSONDecodeError):
        raise _fail("feedback_body_request_invalid") from None
    if not isinstance(document, Mapping):
        raise _fail("feedback_body_request_invalid")
    return document


def _contains_private_or_secret_value(value: str) -> bool:
    return bool(
        SECRET_VALUE_RE.search(value)
        or PROVIDER_URL_RE.search(value)
        or EMAIL_RE.search(value)
        or WINDOWS_ABSOLUTE_PATH_RE.search(value)
        or POSIX_ABSOLUTE_PATH_RE.search(value)
        or PHONE_LIKE_RE.search(value)
    )


def _document_contains_private_or_secret_value(value: Any) -> bool:
    """Inspect every JSON string, including values in rejected unknown fields."""

    if isinstance(value, str):
        return _contains_private_or_secret_value(value)
    if isinstance(value, Mapping):
        return any(
            _document_contains_private_or_secret_value(key)
            or _document_contains_private_or_secret_value(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_document_contains_private_or_secret_value(item) for item in value)
    return False


def _safe_canonical_text(value: Any, *, maximum: int) -> str | None:
    if not isinstance(value, str) or not value or len(value) > maximum:
        return None
    if value != value.strip() or "\x00" in value or "\r" in value:
        return None
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError:
        return None
    return value


def _safe_utf8_size(value: Any) -> int:
    if not isinstance(value, str):
        return 0
    try:
        return len(value.encode("utf-8", errors="strict"))
    except UnicodeError:
        return 0


def _section_summary(sections: Any) -> dict[str, dict[str, Any]]:
    source = sections if isinstance(sections, Mapping) else {}
    return {
        name: {
            "present": bool(
                isinstance(source.get(name), str)
                and str(source.get(name)).strip()
                and _safe_utf8_size(source.get(name))
            ),
            "utf8_bytes": _safe_utf8_size(source.get(name)),
        }
        for name in REQUIRED_SECTIONS
    }


def _render_markdown(title: str, feedback_id: str, sections: Mapping[str, str]) -> bytes:
    text = (
        f"# {title}\n\n"
        f"{MARKER}\n\n"
        f"Feedback ID: `{feedback_id}`\n\n"
        "## 1. 환경\n\n"
        f"{sections['environment']}\n\n"
        "## 2. 수행 작업\n\n"
        f"{sections['task']}\n\n"
        "## 3. 관찰된 실패와 추정 원인\n\n"
        "### 관찰된 실패 (사실)\n\n"
        f"{sections['observed_failure']}\n\n"
        "### 추정 원인 (추정)\n\n"
        f"{sections['suspected_cause']}\n\n"
        "## 4. 바라는 해결\n\n"
        f"{sections['requested_resolution']}\n\n"
        "## 5. 재현\n\n"
        f"{sections['reproduction']}\n"
    )
    return text.encode("utf-8")


def _empty_result(action: str, *, dry_run: bool) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "ok": False,
        "state": "blocked",
        "dry_run": dry_run,
        "approved": False,
        "lifecycle_action": action,
        "feedback_id": None,
        "intent": None,
        "expected_body_sha256": None,
        "supersedes_feedback_id": None,
        "feedback_ref": None,
        "plan_sha256": None,
        "request_sha256": None,
        "proposed_relative_path": None,
        "proposed_receipt_relative_path": None,
        "section_count": 0,
        "section_summary": _section_summary({}),
        "body_utf8_bytes": 0,
        "body_persisted": False,
        "receipt_persisted": False,
        "record_binding": {
            "record_present": False,
            "feedback_ref_bound": False,
        },
        "blockers": [],
        "warnings": [],
        "would_change": [],
        "files_written": [],
        "next_safe_actions": [],
        "requirements": {
            "archive_root": "existing WOM archive root containing archive.yml",
            "request_path_scope": "archive_relative",
            "request_path_pattern": REQUEST_PATH_PATTERN,
            "request_must_be_private_and_git_ignored": True,
            "same_id_revision_status": "draft_only",
            "immutable_statuses": sorted(IMMUTABLE_FEEDBACK_STATUSES),
        },
        "external_delivery_performed": False,
        "privacy_guards": {
            "title_echoed": False,
            "section_values_echoed": False,
            "request_path_echoed": False,
            "matched_private_value_echoed": False,
            "provider_called": False,
            "network_checked": False,
        },
    }


def _blocked(action: str, code: str, *, dry_run: bool) -> dict[str, Any]:
    result = _empty_result(action, dry_run=dry_run)
    result["blockers"] = [code]
    return result


def _feedback_record_state(root: Path, feedback_id: str) -> dict[str, Any]:
    """Read the exact lifecycle authority needed by revise/supersede planning."""

    relative = f"{RECORD_PREFIX}/{feedback_id}.yml"
    raw = _read_optional_exact(
        root,
        _archive_path(root, relative),
        maximum=MAX_RECORD_BYTES,
        invalid_code="feedback_record_binding_invalid",
    )
    if raw is None:
        raise _fail("feedback_record_binding_missing")
    try:
        document = yaml.load(raw.decode("utf-8"), Loader=_UniqueYamlLoader)
    except Exception:
        raise _fail("feedback_record_binding_invalid") from None
    if not isinstance(document, Mapping):
        raise _fail("feedback_record_binding_invalid")
    status = document.get("status")
    feedback_ref = document.get("feedback_ref")
    if (
        document.get("feedback_id") != feedback_id
        or status not in {"draft", *IMMUTABLE_FEEDBACK_STATUSES}
        or not isinstance(feedback_ref, str)
        or FEEDBACK_REF_RE.fullmatch(feedback_ref) is None
    ):
        raise _fail("feedback_record_binding_invalid")
    return {
        "status": status,
        "feedback_ref": feedback_ref,
        "record_sha256": hashlib.sha256(raw).hexdigest(),
    }


def _prepare_plan(
    archive_root: Path | str,
    request_path: Path | str,
    *,
    action: str,
    dry_run: bool,
    intent: str = "create",
    expected_body_sha256: str | None = None,
    supersedes_feedback_id: str | None = None,
    require_archive_marker: bool = False,
) -> tuple[dict[str, Any], _PreparedPlan | None]:
    normalized_intent = str(intent or "").strip().lower()
    if normalized_intent not in COMPOSE_INTENTS:
        return _blocked(
            action,
            "feedback_body_intent_invalid",
            dry_run=dry_run,
        ), None
    normalized_expected = (
        expected_body_sha256.strip().lower()
        if isinstance(expected_body_sha256, str)
        else None
    )
    if normalized_intent in {"revise", "supersede"}:
        if normalized_expected is None:
            return _blocked(
                action,
                "feedback_body_expected_sha256_required",
                dry_run=dry_run,
            ), None
        if SHA256_RE.fullmatch(normalized_expected) is None:
            return _blocked(
                action,
                "feedback_body_expected_sha256_invalid",
                dry_run=dry_run,
            ), None
    elif expected_body_sha256 is not None:
        return _blocked(
            action,
            "feedback_body_expected_sha256_not_allowed",
            dry_run=dry_run,
        ), None

    try:
        root = _validated_root(
            archive_root,
            require_archive_marker=require_archive_marker,
        )
        request_relative = _normalize_request_path(root, request_path)
        _require_effective_gitignore(root, request_relative)
        raw = _read_exact_bytes(
            root,
            _archive_path(root, request_relative),
            maximum=MAX_REQUEST_BYTES,
            missing_code="feedback_body_request_missing",
            invalid_code="feedback_body_request_unsafe_or_invalid",
        )
        request_sha256 = hashlib.sha256(raw).hexdigest()
        document = _parse_request(raw)
    except _BodyContractError as exc:
        return _blocked(action, exc.code, dry_run=dry_run), None
    except Exception:
        return _blocked(action, "feedback_body_plan_failed", dry_run=dry_run), None

    # A matched private value must not influence even otherwise-safe projected
    # identifiers, paths, counts, or digests. Return one fixed empty envelope.
    if _document_contains_private_or_secret_value(document):
        return (
            _blocked(
                action,
                "feedback_body_private_or_secret_content_detected",
                dry_run=dry_run,
            ),
            None,
        )

    result = _empty_result(action, dry_run=dry_run)
    result["intent"] = normalized_intent
    result["expected_body_sha256"] = normalized_expected
    result["request_sha256"] = request_sha256
    blockers: list[str] = []
    if set(document) != REQUEST_KEYS:
        blockers.append("feedback_body_request_schema_invalid")
    if document.get("schema") != REQUEST_SCHEMA:
        blockers.append("feedback_body_request_schema_invalid")

    feedback_id = document.get("feedback_id")
    safe_id = (
        feedback_id
        if isinstance(feedback_id, str) and FEEDBACK_ID_RE.fullmatch(feedback_id)
        else None
    )
    if safe_id is None:
        blockers.append("feedback_body_id_invalid")
    else:
        result["feedback_id"] = safe_id
        result["proposed_relative_path"] = f"{BODY_PREFIX}/{safe_id}.md"

    safe_supersedes_id: str | None = None
    if normalized_intent == "supersede":
        if (
            not isinstance(supersedes_feedback_id, str)
            or FEEDBACK_ID_RE.fullmatch(supersedes_feedback_id) is None
            or _contains_private_or_secret_value(supersedes_feedback_id)
        ):
            blockers.append("feedback_body_supersedes_id_invalid")
        elif supersedes_feedback_id == safe_id:
            blockers.append("feedback_body_supersession_same_id_forbidden")
        else:
            safe_supersedes_id = supersedes_feedback_id
            result["supersedes_feedback_id"] = safe_supersedes_id
    elif supersedes_feedback_id is not None:
        blockers.append("feedback_body_supersedes_id_not_allowed")

    title = _safe_canonical_text(document.get("title"), maximum=240)
    if title is None or "\n" in title:
        blockers.append("feedback_body_title_invalid")

    sections_value = document.get("sections")
    summary = _section_summary(sections_value)
    result["section_summary"] = summary
    result["section_count"] = sum(1 for item in summary.values() if item["present"])
    if not isinstance(sections_value, Mapping) or set(sections_value) != SECTION_KEYS:
        blockers.append("feedback_body_sections_invalid")

    normalized_sections: dict[str, str] = {}
    if isinstance(sections_value, Mapping):
        for name in REQUIRED_SECTIONS:
            value = _safe_canonical_text(sections_value.get(name), maximum=MAX_BODY_BYTES)
            if value is None:
                blockers.append("feedback_body_sections_invalid")
                continue
            if any(line in STRUCTURE_LINES or line == MARKER for line in value.splitlines()):
                blockers.append("feedback_body_sections_structurally_ambiguous")
                continue
            normalized_sections[name] = value

    body_bytes = b""
    if safe_id is not None and title is not None and len(normalized_sections) == len(REQUIRED_SECTIONS):
        body_bytes = _render_markdown(title, safe_id, normalized_sections)
        result["body_utf8_bytes"] = len(body_bytes)
        if len(body_bytes) > MAX_BODY_BYTES:
            blockers.append("feedback_body_size_invalid")

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        result["blockers"] = blockers
        return result, None

    body_digest = hashlib.sha256(body_bytes).hexdigest()
    feedback_ref = f"feedback-body-sha256:{body_digest}"
    proposed_relative = f"{BODY_PREFIX}/{safe_id}.md"
    prior_body_bytes: bytes | None = None
    prior_record_sha256: str | None = None
    prior_status: str | None = None
    revision_resume_pending = False
    lifecycle_id = (
        safe_supersedes_id if normalized_intent == "supersede" else safe_id
    )
    if normalized_intent in {"revise", "supersede"}:
        assert lifecycle_id is not None
        assert normalized_expected is not None
        lifecycle_body_relative = f"{BODY_PREFIX}/{lifecycle_id}.md"
        try:
            current_body = _read_optional_exact(
                root,
                _archive_path(root, lifecycle_body_relative),
                maximum=MAX_BODY_BYTES,
                invalid_code="feedback_body_existing_body_unsafe",
            )
            record_state = _feedback_record_state(root, lifecycle_id)
        except _BodyContractError as exc:
            result["blockers"] = [exc.code]
            return result, None
        if current_body is None:
            result["blockers"] = ["feedback_body_existing_body_missing"]
            return result, None
        current_digest = hashlib.sha256(current_body).hexdigest()
        expected_ref = f"feedback-body-sha256:{normalized_expected}"
        if record_state["feedback_ref"] != expected_ref:
            result["blockers"] = ["feedback_record_binding_mismatch"]
            return result, None
        prior_record_sha256 = str(record_state["record_sha256"])
        prior_status = str(record_state["status"])
        if normalized_intent == "revise":
            if prior_status != "draft":
                result["blockers"] = [
                    "feedback_body_revision_status_immutable"
                ]
                return result, None
            if current_digest != normalized_expected:
                snapshot_relative = (
                    f"{REVISION_PREFIX}/{safe_id}/{normalized_expected}.md"
                )
                try:
                    snapshot = _read_optional_exact(
                        root,
                        _archive_path(root, snapshot_relative),
                        maximum=MAX_BODY_BYTES,
                        invalid_code="feedback_body_prior_snapshot_invalid",
                    )
                except _BodyContractError as exc:
                    result["blockers"] = [exc.code]
                    return result, None
                if (
                    current_digest == body_digest
                    and snapshot is not None
                    and hashlib.sha256(snapshot).hexdigest()
                    == normalized_expected
                ):
                    prior_body_bytes = snapshot
                    revision_resume_pending = True
                else:
                    result["blockers"] = ["feedback_body_compare_and_swap_changed"]
                    return result, None
            else:
                prior_body_bytes = current_body
        else:
            if prior_status not in IMMUTABLE_FEEDBACK_STATUSES:
                result["blockers"] = [
                    "feedback_body_supersession_requires_immutable_source"
                ]
                return result, None
            if current_digest != normalized_expected:
                result["blockers"] = ["feedback_body_compare_and_swap_changed"]
                return result, None
            prior_body_bytes = current_body

    section_hashes = {
        name: hashlib.sha256(normalized_sections[name].encode("utf-8")).hexdigest()
        for name in REQUIRED_SECTIONS
    }
    plan_material = {
        "schema": PLAN_SCHEMA,
        "request_sha256": request_sha256,
        "feedback_id": safe_id,
        "title_sha256": hashlib.sha256(title.encode("utf-8")).hexdigest(),
        "section_sha256": section_hashes,
        "section_utf8_bytes": {
            name: summary[name]["utf8_bytes"] for name in REQUIRED_SECTIONS
        },
        "body_sha256": body_digest,
        "body_utf8_bytes": len(body_bytes),
        "proposed_relative_path": proposed_relative,
    }
    if normalized_intent != "create":
        plan_material.update(
            {
                "intent": normalized_intent,
                "expected_body_sha256": normalized_expected,
                "prior_record_sha256": prior_record_sha256,
                "prior_status": prior_status,
                "supersedes_feedback_id": safe_supersedes_id,
            }
        )
    plan_sha256 = hashlib.sha256(_canonical_json_bytes(plan_material)).hexdigest()
    prepared = _PreparedPlan(
        root=root,
        request_relative=request_relative,
        request_sha256=request_sha256,
        feedback_id=safe_id,
        title=title,
        sections=normalized_sections,
        section_summary=summary,
        body_bytes=body_bytes,
        body_digest=body_digest,
        feedback_ref=feedback_ref,
        proposed_relative_path=proposed_relative,
        plan_sha256=plan_sha256,
        intent=normalized_intent,
        expected_body_sha256=normalized_expected,
        prior_body_bytes=prior_body_bytes,
        prior_record_sha256=prior_record_sha256,
        prior_status=prior_status,
        supersedes_feedback_id=safe_supersedes_id,
        revision_resume_pending=revision_resume_pending,
    )
    would_change = [
        f"write {proposed_relative}",
        f"write {RECEIPT_PREFIX}/{safe_id}.{body_digest[:16]}.json",
    ]
    if normalized_intent == "revise":
        assert normalized_expected is not None
        would_change.extend(
            [
                f"preserve {REVISION_PREFIX}/{safe_id}/{normalized_expected}.md",
                (
                    f"write {REVISION_PREFIX}/{safe_id}/"
                    f"{normalized_expected[:16]}-to-{body_digest[:16]}.json"
                ),
            ]
        )
    elif normalized_intent == "supersede":
        would_change.append(f"write {SUPERSESSION_PREFIX}/<binding>.json")
    result.update(
        {
            "ok": True,
            "state": "preview" if dry_run else "ready",
            "feedback_ref": feedback_ref,
            "plan_sha256": plan_sha256,
            "would_change": would_change,
            "revision_resume_pending": revision_resume_pending,
        }
    )
    return result, prepared


def plan_operator_feedback_body(
    archive_root: Path | str,
    request_path: Path | str,
    *,
    intent: str = "create",
    expected_body_sha256: str | None = None,
    supersedes_feedback_id: str | None = None,
    require_archive_marker: bool = False,
) -> dict[str, Any]:
    """Return a content-free, write-free plan for one reviewed body request."""

    result, _ = _prepare_plan(
        archive_root,
        request_path,
        action="operator_feedback_body_plan",
        dry_run=True,
        intent=intent,
        expected_body_sha256=expected_body_sha256,
        supersedes_feedback_id=supersedes_feedback_id,
        require_archive_marker=require_archive_marker,
    )
    return result


def _safe_reviewer(value: Any) -> str | None:
    if not isinstance(value, str) or REVIEWER_RE.fullmatch(value) is None:
        return None
    if _contains_private_or_secret_value(value):
        return None
    return value


def _ensure_directory_chain(root: Path, directory: Path) -> None:
    try:
        relative = directory.relative_to(root)
    except ValueError:
        raise _fail("feedback_body_output_path_unsafe") from None
    current = root
    for part in relative.parts:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            try:
                os.mkdir(current, 0o700)
                info = os.lstat(current)
            except OSError:
                raise _fail("feedback_body_output_directory_failed") from None
        except OSError:
            raise _fail("feedback_body_output_directory_failed") from None
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise _fail("feedback_body_output_path_unsafe")


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except (OSError, ValueError):
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, value: bytes) -> None:
    written = 0
    while written < len(value):
        count = os.write(descriptor, value[written:])
        if count <= 0:
            raise OSError("write returned no progress")
        written += count


def _write_create_if_absent(root: Path, path: Path, value: bytes) -> bool:
    """Publish complete bytes with a same-directory hard link, never replace."""

    _ensure_directory_chain(root, path.parent)
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    descriptor: int | None = None
    linked = False
    try:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(temporary, flags, 0o600)
        opened = os.fstat(descriptor)
        if _is_reparse(opened) or not stat.S_ISREG(opened.st_mode):
            raise OSError("temporary file is unsafe")
        _write_all(descriptor, value)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        _ensure_directory_chain(root, path.parent)
        try:
            os.link(temporary, path, follow_symlinks=False)
        except TypeError:  # pragma: no cover - compatibility fallback.
            os.link(temporary, path)
        linked = True
        _fsync_directory(path.parent)
        return True
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            if not linked:
                raise


def _read_optional_exact(
    root: Path,
    path: Path,
    *,
    maximum: int,
    invalid_code: str,
) -> bytes | None:
    try:
        return _read_exact_bytes(
            root,
            path,
            maximum=maximum,
            missing_code="feedback_body_optional_file_missing",
            invalid_code=invalid_code,
        )
    except _BodyContractError as exc:
        if exc.code == "feedback_body_optional_file_missing":
            return None
        raise


def _approved_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _receipt_document(
    prepared: _PreparedPlan,
    reviewer: str,
    approved_at: str,
) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "feedback_id": prepared.feedback_id,
        "feedback_ref": prepared.feedback_ref,
        "body_path": prepared.proposed_relative_path,
        "body_utf8_bytes": len(prepared.body_bytes),
        "plan_sha256": prepared.plan_sha256,
        "request_sha256": prepared.request_sha256,
        "reviewed_by": reviewer,
        "approved_at": approved_at,
    }


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or TIMESTAMP_RE.fullmatch(value) is None:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _parse_json_mapping(raw: bytes, code: str) -> Mapping[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs)
    except (_BodyContractError, UnicodeError, json.JSONDecodeError):
        raise _fail(code) from None
    if not isinstance(value, Mapping):
        raise _fail(code)
    return value


def _receipt_matches(
    raw: bytes,
    prepared: _PreparedPlan,
    reviewer: str,
) -> bool:
    try:
        document = _parse_json_mapping(raw, "feedback_body_receipt_invalid")
    except _BodyContractError:
        return False
    expected = _receipt_document(prepared, reviewer, str(document.get("approved_at") or ""))
    return set(document) == RECEIPT_KEYS and document == expected and _valid_timestamp(
        document.get("approved_at")
    )


def _thread_lock(root: Path, feedback_id: str) -> threading.RLock:
    key = os.path.normcase(f"{root}|{feedback_id}")
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _feedback_writer_lock(root: Path, feedback_id: str):
    """Share the same cross-process lock family as the metadata writer."""

    lock_directory = _archive_path(
        root,
        "receipts/operator-feedback/.locks",
    )
    _ensure_directory_chain(root, lock_directory)
    lock_name = hashlib.sha256(feedback_id.encode("utf-8")).hexdigest()
    handle = (lock_directory / f"{lock_name}.lock").open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    continue
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


@contextmanager
def _feedback_writer_locks(root: Path, feedback_ids: list[str]):
    """Acquire multiple feedback locks in stable order to avoid deadlock."""

    with ExitStack() as stack:
        for feedback_id in sorted(set(feedback_ids)):
            stack.enter_context(_feedback_writer_lock(root, feedback_id))
        yield


def _replace_exact_body(root: Path, path: Path, value: bytes) -> None:
    """Publish complete revised bytes atomically inside the existing parent."""

    _ensure_directory_chain(root, path.parent)
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.revise.tmp"
    descriptor: int | None = None
    try:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(temporary, flags, 0o600)
        opened = os.fstat(descriptor)
        if _is_reparse(opened) or not stat.S_ISREG(opened.st_mode):
            raise OSError("temporary file is unsafe")
        _write_all(descriptor, value)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        temporary.unlink(missing_ok=True)


def _revision_receipt_relative(prepared: _PreparedPlan) -> str:
    assert prepared.expected_body_sha256 is not None
    return (
        f"{REVISION_PREFIX}/{prepared.feedback_id}/"
        f"{prepared.expected_body_sha256[:16]}-to-{prepared.body_digest[:16]}.json"
    )


def _revision_receipt_document(
    prepared: _PreparedPlan,
    reviewer: str,
    approved_at: str,
) -> dict[str, Any]:
    assert prepared.expected_body_sha256 is not None
    assert prepared.prior_record_sha256 is not None
    return {
        "schema": REVISION_RECEIPT_SCHEMA,
        "feedback_id": prepared.feedback_id,
        "prior_feedback_ref": (
            f"feedback-body-sha256:{prepared.expected_body_sha256}"
        ),
        "revised_feedback_ref": prepared.feedback_ref,
        "body_path": prepared.proposed_relative_path,
        "prior_body_snapshot_path": (
            f"{REVISION_PREFIX}/{prepared.feedback_id}/"
            f"{prepared.expected_body_sha256}.md"
        ),
        "prior_record_sha256": prepared.prior_record_sha256,
        "plan_sha256": prepared.plan_sha256,
        "request_sha256": prepared.request_sha256,
        "reviewed_by": reviewer,
        "approved_at": approved_at,
    }


def _revision_receipt_matches(
    raw: bytes,
    prepared: _PreparedPlan,
    reviewer: str,
) -> bool:
    try:
        document = _parse_json_mapping(raw, "feedback_body_revision_receipt_invalid")
    except _BodyContractError:
        return False
    expected = _revision_receipt_document(
        prepared,
        reviewer,
        str(document.get("approved_at") or ""),
    )
    return (
        set(document) == REVISION_RECEIPT_KEYS
        and document == expected
        and _valid_timestamp(document.get("approved_at"))
    )


def _approve_operator_feedback_revision(
    prepared: _PreparedPlan,
    result: dict[str, Any],
    reviewer: str,
) -> dict[str, Any]:
    assert prepared.expected_body_sha256 is not None
    assert prepared.prior_body_bytes is not None
    body_path = _archive_path(prepared.root, prepared.proposed_relative_path)
    ordinary_receipt_relative = (
        f"{RECEIPT_PREFIX}/{prepared.feedback_id}.{prepared.body_digest[:16]}.json"
    )
    ordinary_receipt_path = _archive_path(
        prepared.root,
        ordinary_receipt_relative,
    )
    snapshot_relative = (
        f"{REVISION_PREFIX}/{prepared.feedback_id}/"
        f"{prepared.expected_body_sha256}.md"
    )
    snapshot_path = _archive_path(prepared.root, snapshot_relative)
    revision_relative = _revision_receipt_relative(prepared)
    revision_path = _archive_path(prepared.root, revision_relative)
    files_written: list[str] = []
    result["proposed_receipt_relative_path"] = ordinary_receipt_relative

    with _thread_lock(prepared.root, prepared.feedback_id), _feedback_writer_lock(
        prepared.root,
        prepared.feedback_id,
    ):
        try:
            record_state = _feedback_record_state(
                prepared.root,
                prepared.feedback_id,
            )
            current_body = _read_optional_exact(
                prepared.root,
                body_path,
                maximum=MAX_BODY_BYTES,
                invalid_code="feedback_body_existing_body_unsafe",
            )
        except _BodyContractError as exc:
            result.update({"ok": False, "state": "blocked", "blockers": [exc.code]})
            return result
        if (
            record_state["status"] != "draft"
            or record_state["record_sha256"] != prepared.prior_record_sha256
            or record_state["feedback_ref"]
            != f"feedback-body-sha256:{prepared.expected_body_sha256}"
        ):
            result.update(
                {
                    "ok": False,
                    "state": "blocked",
                    "blockers": ["feedback_body_revision_lifecycle_changed"],
                }
            )
            return result
        if current_body is None:
            result.update(
                {
                    "ok": False,
                    "state": "blocked",
                    "blockers": ["feedback_body_existing_body_missing"],
                }
            )
            return result
        current_digest = hashlib.sha256(current_body).hexdigest()
        if current_digest not in {
            prepared.expected_body_sha256,
            prepared.body_digest,
        }:
            result.update(
                {
                    "ok": False,
                    "state": "blocked",
                    "blockers": ["feedback_body_compare_and_swap_changed"],
                }
            )
            return result

        existing_snapshot = _read_optional_exact(
            prepared.root,
            snapshot_path,
            maximum=MAX_BODY_BYTES,
            invalid_code="feedback_body_prior_snapshot_invalid",
        )
        if existing_snapshot is None:
            if current_digest != prepared.expected_body_sha256:
                result.update(
                    {
                        "ok": False,
                        "state": "partial",
                        "blockers": ["feedback_body_prior_snapshot_missing"],
                    }
                )
                return result
            _write_create_if_absent(
                prepared.root,
                snapshot_path,
                prepared.prior_body_bytes,
            )
            files_written.append(snapshot_relative)
        elif existing_snapshot != prepared.prior_body_bytes:
            result.update(
                {
                    "ok": False,
                    "state": "blocked",
                    "blockers": ["feedback_body_prior_snapshot_conflict"],
                }
            )
            return result

        ordinary_receipt = _read_optional_exact(
            prepared.root,
            ordinary_receipt_path,
            maximum=MAX_RECEIPT_BYTES,
            invalid_code="feedback_body_existing_receipt_unsafe",
        )
        if ordinary_receipt is None:
            receipt_bytes = _canonical_json_bytes(
                _receipt_document(prepared, reviewer, _approved_at())
            ) + b"\n"
            _write_create_if_absent(
                prepared.root,
                ordinary_receipt_path,
                receipt_bytes,
            )
            files_written.append(ordinary_receipt_relative)
        elif not _receipt_matches(ordinary_receipt, prepared, reviewer):
            result.update(
                {
                    "ok": False,
                    "state": "blocked",
                    "blockers": ["feedback_body_existing_receipt_conflict"],
                }
            )
            return result

        if current_digest == prepared.expected_body_sha256:
            try:
                _replace_exact_body(prepared.root, body_path, prepared.body_bytes)
            except OSError:
                result.update(
                    {
                        "ok": False,
                        "state": "partial",
                        "blockers": ["feedback_body_revision_write_failed"],
                        "files_written": files_written,
                    }
                )
                return result
            files_written.append(prepared.proposed_relative_path)

        revision_receipt = _read_optional_exact(
            prepared.root,
            revision_path,
            maximum=MAX_RECEIPT_BYTES,
            invalid_code="feedback_body_revision_receipt_invalid",
        )
        if revision_receipt is None:
            revision_bytes = _canonical_json_bytes(
                _revision_receipt_document(
                    prepared,
                    reviewer,
                    _approved_at(),
                )
            ) + b"\n"
            try:
                _write_create_if_absent(
                    prepared.root,
                    revision_path,
                    revision_bytes,
                )
            except (OSError, _BodyContractError):
                result.update(
                    {
                        "ok": False,
                        "state": "partial",
                        "blockers": ["feedback_body_revision_receipt_write_failed"],
                        "files_written": files_written,
                        "next_safe_actions": [
                            "rerun the unchanged revision request with the same expected body SHA-256"
                        ],
                    }
                )
                return result
            files_written.append(revision_relative)
            revision_receipt = revision_bytes
        if not _revision_receipt_matches(
            revision_receipt,
            prepared,
            reviewer,
        ):
            result.update(
                {
                    "ok": False,
                    "state": "partial",
                    "blockers": ["feedback_body_revision_receipt_invalid"],
                    "files_written": files_written,
                }
            )
            return result

        final_body = _read_optional_exact(
            prepared.root,
            body_path,
            maximum=MAX_BODY_BYTES,
            invalid_code="feedback_body_existing_body_unsafe",
        )
        final_snapshot = _read_optional_exact(
            prepared.root,
            snapshot_path,
            maximum=MAX_BODY_BYTES,
            invalid_code="feedback_body_prior_snapshot_invalid",
        )
        if final_body != prepared.body_bytes or final_snapshot != prepared.prior_body_bytes:
            result.update(
                {
                    "ok": False,
                    "state": "partial",
                    "blockers": ["feedback_body_revision_final_verification_failed"],
                    "files_written": files_written,
                }
            )
            return result

    result.update(
        {
            "ok": True,
            "state": "already_written" if not files_written else "revised",
            "approved": True,
            "dry_run": False,
            "body_persisted": True,
            "receipt_persisted": True,
            "blockers": [],
            "would_change": [],
            "files_written": files_written,
            "revision_evidence": {
                "prior_body_snapshot_path": snapshot_relative,
                "revision_receipt_path": revision_relative,
                "prior_body_sha256": prepared.expected_body_sha256,
                "revised_body_sha256": prepared.body_digest,
                "immutable": True,
            },
            "record_binding": {
                "record_present": True,
                "feedback_ref_bound": False,
            },
            "next_safe_actions": [
                "use operator-feedback-record update with the fresh current record SHA-256 to bind this revised feedback_ref while status remains draft"
            ],
        }
    )
    return result


def _supersession_receipt_relative(prepared: _PreparedPlan) -> str:
    binding = hashlib.sha256(
        _canonical_json_bytes(
            {
                "plan_sha256": prepared.plan_sha256,
                "superseded_feedback_id": prepared.supersedes_feedback_id,
                "superseding_feedback_id": prepared.feedback_id,
            }
        )
    ).hexdigest()
    return f"{SUPERSESSION_PREFIX}/{binding[:32]}.json"


def _supersession_receipt_document(
    prepared: _PreparedPlan,
    reviewer: str,
    approved_at: str,
) -> dict[str, Any]:
    assert prepared.supersedes_feedback_id is not None
    assert prepared.expected_body_sha256 is not None
    assert prepared.prior_status is not None
    assert prepared.prior_record_sha256 is not None
    return {
        "schema": SUPERSESSION_RECEIPT_SCHEMA,
        "superseded_feedback_id": prepared.supersedes_feedback_id,
        "superseding_feedback_id": prepared.feedback_id,
        "superseded_feedback_ref": (
            f"feedback-body-sha256:{prepared.expected_body_sha256}"
        ),
        "superseding_feedback_ref": prepared.feedback_ref,
        "superseded_status": prepared.prior_status,
        "superseded_record_sha256": prepared.prior_record_sha256,
        "superseding_body_path": prepared.proposed_relative_path,
        "plan_sha256": prepared.plan_sha256,
        "request_sha256": prepared.request_sha256,
        "reviewed_by": reviewer,
        "approved_at": approved_at,
    }


def _supersession_receipt_matches(
    raw: bytes,
    prepared: _PreparedPlan,
    reviewer: str,
) -> bool:
    try:
        document = _parse_json_mapping(
            raw,
            "feedback_body_supersession_receipt_invalid",
        )
    except _BodyContractError:
        return False
    expected = _supersession_receipt_document(
        prepared,
        reviewer,
        str(document.get("approved_at") or ""),
    )
    return (
        set(document) == SUPERSESSION_RECEIPT_KEYS
        and document == expected
        and _valid_timestamp(document.get("approved_at"))
    )


def approve_operator_feedback_body(
    archive_root: Path | str,
    request_path: Path | str,
    *,
    expected_plan_sha256: str,
    reviewed_by: str,
    intent: str = "create",
    expected_body_sha256: str | None = None,
    supersedes_feedback_id: str | None = None,
    require_archive_marker: bool = False,
) -> dict[str, Any]:
    """Write the exact reviewed body and receipt without touching metadata."""

    result, prepared = _prepare_plan(
        archive_root,
        request_path,
        action="operator_feedback_body_approve",
        dry_run=False,
        intent=intent,
        expected_body_sha256=expected_body_sha256,
        supersedes_feedback_id=supersedes_feedback_id,
        require_archive_marker=require_archive_marker,
    )
    if prepared is None:
        return result
    expected = (
        expected_plan_sha256
        if isinstance(expected_plan_sha256, str) and SHA256_RE.fullmatch(expected_plan_sha256)
        else None
    )
    if expected is None:
        result.update({"ok": False, "state": "blocked", "blockers": ["feedback_body_plan_sha256_invalid"]})
        return result
    if expected != prepared.plan_sha256:
        result.update({"ok": False, "state": "blocked", "blockers": ["feedback_body_plan_changed"]})
        return result
    reviewer = _safe_reviewer(reviewed_by)
    if reviewer is None:
        result.update({"ok": False, "state": "blocked", "blockers": ["feedback_body_reviewer_invalid"]})
        return result

    if prepared.intent == "revise":
        return _approve_operator_feedback_revision(prepared, result, reviewer)

    body_path = _archive_path(prepared.root, prepared.proposed_relative_path)
    receipt_relative = (
        f"{RECEIPT_PREFIX}/{prepared.feedback_id}.{prepared.body_digest[:16]}.json"
    )
    receipt_path = _archive_path(prepared.root, receipt_relative)
    result["proposed_receipt_relative_path"] = receipt_relative
    files_written: list[str] = []

    lock_ids = [prepared.feedback_id]
    if prepared.supersedes_feedback_id is not None:
        lock_ids.append(prepared.supersedes_feedback_id)
    with _thread_lock(
        prepared.root,
        prepared.feedback_id,
    ), _feedback_writer_locks(prepared.root, lock_ids):
        if prepared.intent == "supersede":
            assert prepared.supersedes_feedback_id is not None
            assert prepared.expected_body_sha256 is not None
            try:
                superseded_state = _feedback_record_state(
                    prepared.root,
                    prepared.supersedes_feedback_id,
                )
                superseded_body = _read_optional_exact(
                    prepared.root,
                    _archive_path(
                        prepared.root,
                        f"{BODY_PREFIX}/{prepared.supersedes_feedback_id}.md",
                    ),
                    maximum=MAX_BODY_BYTES,
                    invalid_code="feedback_body_existing_body_unsafe",
                )
            except _BodyContractError as exc:
                result.update(
                    {"ok": False, "state": "blocked", "blockers": [exc.code]}
                )
                return result
            if (
                superseded_state["status"] not in IMMUTABLE_FEEDBACK_STATUSES
                or superseded_state["record_sha256"]
                != prepared.prior_record_sha256
                or superseded_state["feedback_ref"]
                != f"feedback-body-sha256:{prepared.expected_body_sha256}"
                or superseded_body is None
                or hashlib.sha256(superseded_body).hexdigest()
                != prepared.expected_body_sha256
            ):
                result.update(
                    {
                        "ok": False,
                        "state": "blocked",
                        "blockers": ["feedback_body_supersession_source_changed"],
                    }
                )
                return result
        try:
            existing_body = _read_optional_exact(
                prepared.root,
                body_path,
                maximum=MAX_BODY_BYTES,
                invalid_code="feedback_body_existing_body_unsafe",
            )
            existing_receipt = _read_optional_exact(
                prepared.root,
                receipt_path,
                maximum=MAX_RECEIPT_BYTES,
                invalid_code="feedback_body_existing_receipt_unsafe",
            )
        except _BodyContractError as exc:
            result.update({"ok": False, "state": "blocked", "blockers": [exc.code]})
            return result

        if existing_body is not None and existing_body != prepared.body_bytes:
            result.update({"ok": False, "state": "blocked", "blockers": ["feedback_body_existing_body_conflict"]})
            return result
        if existing_receipt is not None and existing_body is None:
            result.update({"ok": False, "state": "blocked", "blockers": ["feedback_body_receipt_without_body"]})
            return result
        if existing_receipt is not None and not _receipt_matches(existing_receipt, prepared, reviewer):
            result.update({"ok": False, "state": "blocked", "blockers": ["feedback_body_existing_receipt_conflict"]})
            return result

        body_persisted = existing_body == prepared.body_bytes
        receipt_persisted = existing_receipt is not None
        if not body_persisted:
            try:
                _write_create_if_absent(prepared.root, body_path, prepared.body_bytes)
                files_written.append(prepared.proposed_relative_path)
            except FileExistsError:
                try:
                    concurrent = _read_optional_exact(
                        prepared.root,
                        body_path,
                        maximum=MAX_BODY_BYTES,
                        invalid_code="feedback_body_existing_body_unsafe",
                    )
                except _BodyContractError as exc:
                    result.update({"ok": False, "state": "blocked", "blockers": [exc.code]})
                    return result
                if concurrent != prepared.body_bytes:
                    result.update({"ok": False, "state": "blocked", "blockers": ["feedback_body_concurrent_conflict"]})
                    return result
            except (OSError, _BodyContractError):
                result.update({"ok": False, "state": "failed", "blockers": ["feedback_body_write_failed"]})
                return result
            try:
                body_persisted = _read_optional_exact(
                    prepared.root,
                    body_path,
                    maximum=MAX_BODY_BYTES,
                    invalid_code="feedback_body_existing_body_unsafe",
                ) == prepared.body_bytes
            except _BodyContractError:
                body_persisted = False
            if not body_persisted:
                result.update(
                    {
                        "ok": False,
                        "state": "failed",
                        "blockers": ["feedback_body_write_verification_failed"],
                    }
                )
                return result

        if not receipt_persisted:
            receipt_bytes = _canonical_json_bytes(
                _receipt_document(prepared, reviewer, _approved_at())
            ) + b"\n"
            try:
                _write_create_if_absent(prepared.root, receipt_path, receipt_bytes)
                files_written.append(receipt_relative)
            except FileExistsError:
                pass
            except (OSError, _BodyContractError):
                result.update(
                    {
                        "ok": False,
                        "state": "partial" if body_persisted else "failed",
                        "blockers": ["feedback_body_receipt_write_failed"],
                        "body_persisted": body_persisted,
                        "receipt_persisted": False,
                        "files_written": files_written,
                        "next_safe_actions": ["rerun the unchanged approved feedback body request"],
                    }
                )
                return result
            try:
                existing_receipt = _read_optional_exact(
                    prepared.root,
                    receipt_path,
                    maximum=MAX_RECEIPT_BYTES,
                    invalid_code="feedback_body_existing_receipt_unsafe",
                )
            except _BodyContractError:
                existing_receipt = None
            receipt_persisted = bool(
                existing_receipt is not None
                and _receipt_matches(existing_receipt, prepared, reviewer)
            )
            if not receipt_persisted:
                result.update(
                    {
                        "ok": False,
                        "state": "partial",
                        "blockers": ["feedback_body_receipt_write_verification_failed"],
                        "body_persisted": body_persisted,
                        "receipt_persisted": False,
                        "files_written": files_written,
                        "next_safe_actions": ["rerun the unchanged approved feedback body request"],
                    }
                )
                return result

        # The body and receipt are separate files, so verification of one must
        # not be mistaken for a joint commit. Re-read both authorities in one
        # final pass after receipt publication. This catches an external or
        # concurrent body change that lands between the earlier body check and
        # the receipt write, and keeps the public persistence claim honest.
        try:
            final_body = _read_optional_exact(
                prepared.root,
                body_path,
                maximum=MAX_BODY_BYTES,
                invalid_code="feedback_body_existing_body_unsafe",
            )
            final_receipt = _read_optional_exact(
                prepared.root,
                receipt_path,
                maximum=MAX_RECEIPT_BYTES,
                invalid_code="feedback_body_existing_receipt_unsafe",
            )
        except _BodyContractError:
            final_body = None
            final_receipt = None
        final_body_persisted = final_body == prepared.body_bytes
        final_receipt_persisted = bool(
            final_receipt is not None
            and _receipt_matches(final_receipt, prepared, reviewer)
        )
        if not final_body_persisted or not final_receipt_persisted:
            result.update(
                {
                    "ok": False,
                    "state": "partial",
                    "blockers": ["feedback_body_final_verification_failed"],
                    "body_persisted": final_body_persisted,
                    "receipt_persisted": final_receipt_persisted,
                    "files_written": files_written,
                    "next_safe_actions": [
                        "inspect the feedback body authority and rerun the unchanged approved request"
                    ],
                }
            )
            return result

        if prepared.intent == "supersede":
            supersession_relative = _supersession_receipt_relative(prepared)
            supersession_path = _archive_path(
                prepared.root,
                supersession_relative,
            )
            try:
                supersession_receipt = _read_optional_exact(
                    prepared.root,
                    supersession_path,
                    maximum=MAX_RECEIPT_BYTES,
                    invalid_code="feedback_body_supersession_receipt_invalid",
                )
            except _BodyContractError as exc:
                result.update(
                    {
                        "ok": False,
                        "state": "partial",
                        "blockers": [exc.code],
                        "files_written": files_written,
                    }
                )
                return result
            if supersession_receipt is None:
                supersession_bytes = _canonical_json_bytes(
                    _supersession_receipt_document(
                        prepared,
                        reviewer,
                        _approved_at(),
                    )
                ) + b"\n"
                try:
                    _write_create_if_absent(
                        prepared.root,
                        supersession_path,
                        supersession_bytes,
                    )
                except (OSError, _BodyContractError):
                    result.update(
                        {
                            "ok": False,
                            "state": "partial",
                            "blockers": [
                                "feedback_body_supersession_receipt_write_failed"
                            ],
                            "files_written": files_written,
                        }
                    )
                    return result
                files_written.append(supersession_relative)
                supersession_receipt = supersession_bytes
            if not _supersession_receipt_matches(
                supersession_receipt,
                prepared,
                reviewer,
            ):
                result.update(
                    {
                        "ok": False,
                        "state": "partial",
                        "blockers": [
                            "feedback_body_supersession_receipt_invalid"
                        ],
                        "files_written": files_written,
                    }
                )
                return result
            result["supersession_evidence"] = {
                "superseded_feedback_id": prepared.supersedes_feedback_id,
                "superseding_feedback_id": prepared.feedback_id,
                "supersession_receipt_path": supersession_relative,
                "superseded_body_modified": False,
                "immutable": True,
            }

    state = (
        "already_written"
        if not files_written
        else "superseding_body_written"
        if prepared.intent == "supersede"
        else "written"
    )
    result.update(
        {
            "ok": True,
            "state": state,
            "approved": True,
            "dry_run": False,
            "body_persisted": True,
            "receipt_persisted": True,
            "blockers": [],
            "would_change": [],
            "files_written": files_written,
            "next_safe_actions": [
                "bind this feedback_ref through the existing operator-feedback metadata review workflow"
            ],
        }
    )
    return result


def _parse_body_structure(raw: bytes, feedback_id: str) -> bool:
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        return False
    if text.startswith("\ufeff") or "\r" in text or "\x00" in text or not text.endswith("\n"):
        return False
    if any(text.splitlines().count(line) != 1 for line in STRUCTURE_LINES):
        return False
    if text.splitlines().count(MARKER) != 1:
        return False
    escaped_id = re.escape(feedback_id)
    pattern = re.compile(
        rf"\A# (?P<title>[^\n]{{1,240}})\n\n"
        rf"{re.escape(MARKER)}\n\n"
        rf"Feedback ID: `{escaped_id}`\n\n"
        r"## 1\. 환경\n\n(?P<environment>.+?)\n\n"
        r"## 2\. 수행 작업\n\n(?P<task>.+?)\n\n"
        r"## 3\. 관찰된 실패와 추정 원인\n\n"
        r"### 관찰된 실패 \(사실\)\n\n(?P<observed_failure>.+?)\n\n"
        r"### 추정 원인 \(추정\)\n\n(?P<suspected_cause>.+?)\n\n"
        r"## 4\. 바라는 해결\n\n(?P<requested_resolution>.+?)\n\n"
        r"## 5\. 재현\n\n(?P<reproduction>.+)\n\Z",
        re.DOTALL,
    )
    match = pattern.fullmatch(text)
    if match is None:
        return False
    title = _safe_canonical_text(match.group("title"), maximum=240)
    if title is None or "\n" in title:
        return False
    for name in REQUIRED_SECTIONS:
        value = _safe_canonical_text(match.group(name), maximum=MAX_BODY_BYTES)
        if value is None:
            return False
    return True


class _UniqueYamlLoader(yaml.SafeLoader):
    pass


def _construct_unique_yaml_mapping(
    loader: _UniqueYamlLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except (TypeError, ValueError):
            raise _fail("feedback_record_binding_invalid") from None
        if duplicate:
            raise _fail("feedback_record_binding_invalid")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_yaml_mapping,
)


def _record_binding(
    root: Path,
    feedback_id: str,
    feedback_ref: str,
) -> tuple[dict[str, bool], str | None]:
    path = _archive_path(root, f"{RECORD_PREFIX}/{feedback_id}.yml")
    try:
        raw = _read_optional_exact(
            root,
            path,
            maximum=MAX_RECORD_BYTES,
            invalid_code="feedback_record_binding_invalid",
        )
    except _BodyContractError:
        return {"record_present": True, "feedback_ref_bound": False}, "feedback_record_binding_invalid"
    if raw is None:
        return {"record_present": False, "feedback_ref_bound": False}, "feedback_record_binding_missing"
    try:
        document = yaml.load(raw.decode("utf-8"), Loader=_UniqueYamlLoader)
    except Exception:
        return {"record_present": True, "feedback_ref_bound": False}, "feedback_record_binding_invalid"
    if not isinstance(document, Mapping):
        return {"record_present": True, "feedback_ref_bound": False}, "feedback_record_binding_invalid"
    bound = document.get("feedback_id") == feedback_id and document.get("feedback_ref") == feedback_ref
    return {"record_present": True, "feedback_ref_bound": bool(bound)}, (
        None if bound else "feedback_record_binding_mismatch"
    )


def _check_receipt(
    root: Path,
    feedback_id: str,
    feedback_ref: str,
    body_relative: str,
    body_bytes: int,
) -> tuple[bool, str | None, str]:
    digest = feedback_ref.rsplit(":", 1)[-1]
    relative = f"{RECEIPT_PREFIX}/{feedback_id}.{digest[:16]}.json"
    path = _archive_path(root, relative)
    try:
        raw = _read_optional_exact(
            root,
            path,
            maximum=MAX_RECEIPT_BYTES,
            invalid_code="feedback_body_receipt_invalid",
        )
    except _BodyContractError:
        return False, "feedback_body_receipt_invalid", relative
    if raw is None:
        return False, "feedback_body_receipt_missing", relative
    try:
        document = _parse_json_mapping(raw, "feedback_body_receipt_invalid")
    except _BodyContractError:
        return False, "feedback_body_receipt_invalid", relative
    if (
        set(document) != RECEIPT_KEYS
        or document.get("schema") != RECEIPT_SCHEMA
        or document.get("feedback_id") != feedback_id
        or document.get("feedback_ref") != feedback_ref
        or document.get("body_path") != body_relative
        or document.get("body_utf8_bytes") != body_bytes
        or not isinstance(document.get("plan_sha256"), str)
        or SHA256_RE.fullmatch(document["plan_sha256"]) is None
        or not isinstance(document.get("request_sha256"), str)
        or SHA256_RE.fullmatch(document["request_sha256"]) is None
        or _safe_reviewer(document.get("reviewed_by")) is None
        or not _valid_timestamp(document.get("approved_at"))
    ):
        return False, "feedback_body_receipt_invalid", relative
    return True, None, relative


def check_operator_feedback_body(
    archive_root: Path | str,
    feedback_id: str,
    *,
    require_archive_marker: bool = False,
) -> dict[str, Any]:
    """Verify body, receipt, and existing metadata binding without echoing body."""

    result = _empty_result("operator_feedback_body_check", dry_run=True)
    if not isinstance(feedback_id, str) or FEEDBACK_ID_RE.fullmatch(feedback_id) is None:
        result["blockers"] = ["feedback_body_id_invalid"]
        return result
    if _contains_private_or_secret_value(feedback_id):
        result["blockers"] = ["feedback_body_private_or_secret_content_detected"]
        return result
    result["feedback_id"] = feedback_id
    body_relative = f"{BODY_PREFIX}/{feedback_id}.md"
    result["proposed_relative_path"] = body_relative
    try:
        root = _validated_root(
            archive_root,
            require_archive_marker=require_archive_marker,
        )
        raw = _read_exact_bytes(
            root,
            _archive_path(root, body_relative),
            maximum=MAX_BODY_BYTES,
            missing_code="feedback_body_missing",
            invalid_code="feedback_body_unsafe_or_invalid",
        )
    except _BodyContractError as exc:
        result["blockers"] = [exc.code]
        return result
    except Exception:
        result["blockers"] = ["feedback_body_check_failed"]
        return result

    digest = hashlib.sha256(raw).hexdigest()
    feedback_ref = f"feedback-body-sha256:{digest}"
    structure_valid = _parse_body_structure(raw, feedback_id)
    try:
        text = raw.decode("utf-8")
        privacy_valid = not _contains_private_or_secret_value(text)
    except UnicodeError:
        privacy_valid = False
    blockers: list[str] = []
    if not structure_valid:
        blockers.append("feedback_body_structure_invalid")
    if not privacy_valid:
        blockers.append("feedback_body_private_or_secret_content_detected")

    receipt_valid, receipt_blocker, receipt_relative = _check_receipt(
        root,
        feedback_id,
        feedback_ref,
        body_relative,
        len(raw),
    )
    result["proposed_receipt_relative_path"] = receipt_relative
    if receipt_blocker:
        blockers.append(receipt_blocker)

    binding, binding_blocker = _record_binding(root, feedback_id, feedback_ref)
    if binding_blocker:
        blockers.append(binding_blocker)

    blockers = list(dict.fromkeys(blockers))
    result.update(
        {
            "ok": not blockers,
            "state": "verified" if not blockers else "blocked",
            "feedback_ref": feedback_ref,
            "body_utf8_bytes": len(raw),
            "body_persisted": True,
            "receipt_persisted": receipt_valid,
            "record_binding": binding,
            "body_check": {
                "structure_valid": structure_valid,
                "privacy_valid": privacy_valid,
                "exact_hash_bound_by_receipt": receipt_valid,
            },
            "blockers": blockers,
            "next_safe_actions": (
                ["bind this feedback_ref through the existing operator-feedback metadata review workflow"]
                if binding_blocker == "feedback_record_binding_missing"
                else []
            ),
        }
    )
    return result


__all__ = [
    "CLI_REQUIRE_ARCHIVE_MARKER",
    "approve_operator_feedback_body",
    "check_operator_feedback_body",
    "plan_operator_feedback_body",
]
