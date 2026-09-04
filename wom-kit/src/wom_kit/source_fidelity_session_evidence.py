"""Approval-bound private session evidence for source-fidelity v0.2.

The source bytes stay below ``profiles/local/`` and every public result is
content- and path-free.  The sibling receipt contains only digests, bounded
provenance classes, timestamps, and review metadata.  A raw session reference
is validated, hashed, and then discarded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import subprocess
import threading
from typing import Any, Mapping, Sequence

import yaml

from .exact_human_approval import (
    _ClaimedExactHumanApproval,
    ExactHumanApprovalError,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_link import write_exact_human_approval_link
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
    exact_human_approval_warning_codes,
)
from .process_launch import noninteractive_creationflags


PLAN_SCHEMA = "wom-kit/source-fidelity-session-evidence-plan/v0.1"
RECEIPT_SCHEMA = "wom-kit/source-fidelity-session-evidence-receipt/v0.1"
RESULT_SCHEMA = "wom-kit/source-fidelity-session-evidence-result/v0.1"
COMPARISON_BASIS = "utf8_newlines_lf"

INPUT_PREFIX = ".wom-scratch/private/source-fidelity/session-evidence"
STORAGE_PREFIX = "profiles/local/source-fidelity/session-evidence"
RECEIPT_PREFIX = "receipts/source-fidelity/session-evidence"

SOURCE_ROLES = frozenset(
    {
        "external_primary_source",
        "external_context",
        "human_authored_source",
        "reviewed_session_transcript",
        "reviewed_multi_source_bundle",
        "human_reviewed_summary",
        "self_authored_candidate",
    }
)
PRODUCER_KINDS = frozenset({"human", "external_system", "ai_runtime", "mixed"})

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_RECEIPT_BYTES = 256 * 1024
MAX_GITIGNORE_BYTES = 256 * 1024
REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA256_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
EVIDENCE_ID_RE = re.compile(
    r"^source-fidelity-session-evidence:([0-9a-f]{64})$"
)
INPUT_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.txt$")
SESSION_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._+-]{0,199}$")
REVIEWER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._+-]{0,199}$")

_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


class SessionEvidenceError(RuntimeError):
    """Content-free contract failure."""

    def __init__(self, code: str) -> None:
        self.code = (
            code
            if re.fullmatch(r"[a-z0-9_]+", str(code or ""))
            else "session_evidence_failed"
        )
        super().__init__(self.code)


@dataclass(repr=False)
class _PreparedEvidence:
    root: Path = field(repr=False)
    archive_id: str
    input_relative: str = field(repr=False)
    raw: bytes = field(repr=False)
    normalized: bytes = field(repr=False)
    raw_sha256: str
    normalized_sha256: str
    session_ref_sha256: str
    source_role: str
    producer_kind: str
    produced_at: str
    captured_at: str
    input_provenance_sha256: tuple[str, ...]
    evidence_id: str
    evidence_digest: str
    plan_sha256: str


def _fail(code: str) -> SessionEvidenceError:
    return SessionEvidenceError(code)


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        stat.S_ISLNK(info.st_mode)
        or (REPARSE_FLAG and getattr(info, "st_file_attributes", 0) & REPARSE_FLAG)
    )


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise _fail("session_evidence_document_invalid") from None


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validated_root(archive_root: Path | str) -> Path:
    supplied = Path(archive_root)
    if not supplied.is_absolute():
        supplied = Path(os.path.abspath(os.fspath(supplied)))
    try:
        info = os.lstat(supplied)
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise _fail("session_evidence_archive_root_unsafe")
        root = supplied.resolve(strict=True)
        marker = os.lstat(root / "archive.yml")
        if _is_reparse(marker) or not stat.S_ISREG(marker.st_mode):
            raise _fail("session_evidence_archive_root_invalid")
    except SessionEvidenceError:
        raise
    except OSError:
        raise _fail("session_evidence_archive_root_unavailable") from None
    return root


def _archive_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise _fail("session_evidence_internal_path_invalid")
    candidate = root.joinpath(*parts)
    try:
        candidate.relative_to(root)
    except ValueError:
        raise _fail("session_evidence_internal_path_invalid") from None
    return candidate


def _normalize_input_path(root: Path, source_file: Path | str) -> str:
    raw = os.fspath(source_file)
    if "\x00" in raw or "\\" in raw or ":" in raw:
        raise _fail("session_evidence_source_path_invalid")
    supplied = Path(raw)
    if supplied.is_absolute():
        try:
            relative_path = supplied.resolve(strict=False).relative_to(root)
        except (OSError, ValueError):
            raise _fail("session_evidence_source_path_invalid") from None
    else:
        relative_path = supplied
    parts = relative_path.parts
    if any(part in {"", ".", ".."} for part in parts):
        raise _fail("session_evidence_source_path_invalid")
    relative = PurePosixPath(*parts).as_posix()
    pure = PurePosixPath(relative)
    if (
        pure.parent.as_posix() != INPUT_PREFIX
        or INPUT_FILE_RE.fullmatch(pure.name) is None
    ):
        raise _fail("session_evidence_source_path_invalid")
    return relative


def _read_exact_bytes(
    root: Path,
    path: Path,
    *,
    maximum: int,
    missing_code: str,
    invalid_code: str,
) -> bytes:
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
    if (
        _is_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_size <= 0
        or before.st_size > maximum
    ):
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
    except SessionEvidenceError:
        raise
    except OSError:
        raise _fail(invalid_code) from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


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
            missing_code="session_evidence_optional_file_missing",
            invalid_code=invalid_code,
        )
    except SessionEvidenceError as exc:
        if exc.code == "session_evidence_optional_file_missing":
            return None
        raise


def _git_admin_present(root: Path) -> bool:
    for candidate in (root, *root.parents):
        try:
            os.lstat(candidate / ".git")
        except FileNotFoundError:
            continue
        except OSError:
            raise _fail("session_evidence_private_boundary_unverified") from None
        return True
    return False


def _require_untracked(root: Path, relative: str) -> None:
    if not _git_admin_present(root):
        return
    try:
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", relative],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
            creationflags=noninteractive_creationflags(),
        )
    except (OSError, subprocess.SubprocessError):
        raise _fail("session_evidence_private_boundary_unverified") from None
    if tracked.returncode != 1:
        raise _fail("session_evidence_private_boundary_unverified")


def _require_private_boundaries(
    root: Path,
    *,
    input_relative: str,
    storage_relative: str,
) -> None:
    raw = _read_exact_bytes(
        root,
        _archive_path(root, ".gitignore"),
        maximum=MAX_GITIGNORE_BYTES,
        missing_code="session_evidence_private_boundary_unverified",
        invalid_code="session_evidence_private_boundary_unverified",
    )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        raise _fail("session_evidence_private_boundary_unverified") from None
    if "\x00" in text:
        raise _fail("session_evidence_private_boundary_unverified")
    targets = {
        "profiles/local": {
            "profiles/local/",
            "/profiles/local/",
            "profiles/local",
            "/profiles/local",
        },
        ".wom-scratch": {
            ".wom-scratch/",
            "/.wom-scratch/",
            ".wom-scratch",
            "/.wom-scratch",
        },
    }
    seen = {key: False for key in targets}
    unsafe_negation = {key: False for key in targets}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        for key, exact_patterns in targets.items():
            if line in exact_patterns:
                seen[key] = True
                unsafe_negation[key] = False
            elif seen[key] and line.startswith("!"):
                unsafe_negation[key] = True
    if any(not seen[key] or unsafe_negation[key] for key in targets):
        raise _fail("session_evidence_private_boundary_unverified")
    _require_untracked(root, input_relative)
    _require_untracked(root, storage_relative)


def _parse_timestamp(value: Any, code: str) -> tuple[str, datetime]:
    raw = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise _fail(code) from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _fail(code)
    normalized = parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
    return normalized, parsed.astimezone(timezone.utc)


def _archive_id(root: Path) -> str:
    raw = _read_exact_bytes(
        root,
        root / "archive.yml",
        maximum=1024 * 1024,
        missing_code="session_evidence_archive_root_invalid",
        invalid_code="session_evidence_archive_root_invalid",
    )
    try:
        document = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeError, yaml.YAMLError):
        raise _fail("session_evidence_archive_root_invalid") from None
    value = document.get("archive_id") if isinstance(document, Mapping) else None
    if not isinstance(value, str) or not value.strip():
        raise _fail("session_evidence_archive_root_invalid")
    return value.strip()


def _normalize_provenance_digests(values: Sequence[str] | None) -> tuple[str, ...]:
    result: list[str] = []
    for value in values or ():
        normalized = str(value or "").strip().lower()
        if SHA256_REF_RE.fullmatch(normalized) is None:
            raise _fail("session_evidence_input_provenance_sha256_invalid")
        if normalized not in result:
            result.append(normalized)
    return tuple(sorted(result))


def _base_result(
    *,
    action: str,
    dry_run: bool,
    prepared: _PreparedEvidence | None,
) -> dict[str, Any]:
    return {
        "ok": prepared is not None,
        "schema": RESULT_SCHEMA,
        "lifecycle_action": action,
        "state": "ready_for_review" if dry_run and prepared else "blocked",
        "dry_run": bool(dry_run),
        "approved": False,
        "evidence_id": prepared.evidence_id if prepared else None,
        "plan_sha256": prepared.plan_sha256 if prepared else None,
        "source": (
            {
                "raw_sha256": prepared.raw_sha256,
                "raw_size_bytes": len(prepared.raw),
                "normalized_sha256": prepared.normalized_sha256,
                "normalized_size_bytes": len(prepared.normalized),
                "comparison_basis": COMPARISON_BASIS,
                "newline_transformation_applied": prepared.raw != prepared.normalized,
                "text_echoed": False,
            }
            if prepared
            else None
        ),
        "provenance": (
            {
                "source_role": prepared.source_role,
                "producer_kind": prepared.producer_kind,
                "produced_at": prepared.produced_at,
                "captured_at": prepared.captured_at,
                "session_ref_sha256": "sha256:" + prepared.session_ref_sha256,
                "input_provenance_sha256": list(prepared.input_provenance_sha256),
                "semantic_fidelity_machine_verified": False,
            }
            if prepared
            else None
        ),
        "persistence": {
            "evidence_bytes_persisted": False,
            "receipt_persisted": False,
            "files_written_count": 0,
            "paths_echoed": False,
        },
        "privacy_guards": {
            "source_text_echoed": False,
            "source_path_echoed": False,
            "raw_session_ref_stored": False,
            "raw_session_ref_echoed": False,
            "absolute_local_paths_echoed": False,
        },
        "blockers": [] if prepared else ["session_evidence_plan_unavailable"],
        "warnings": [],
        "would_change_count": 2 if prepared and dry_run else 0,
    }


def _prepare(
    archive_root: Path | str,
    source_file: Path | str,
    *,
    session_ref: str,
    source_role: str,
    producer_kind: str,
    produced_at: str,
    captured_at: str,
    input_provenance_sha256: Sequence[str] | None,
) -> _PreparedEvidence:
    root = _validated_root(archive_root)
    input_relative = _normalize_input_path(root, source_file)
    raw = _read_exact_bytes(
        root,
        _archive_path(root, input_relative),
        maximum=MAX_SOURCE_BYTES,
        missing_code="session_evidence_source_missing",
        invalid_code="session_evidence_source_unsafe",
    )
    try:
        source_text = raw.decode("utf-8")
    except UnicodeError:
        raise _fail("session_evidence_source_not_utf8") from None
    if "\x00" in source_text:
        raise _fail("session_evidence_source_contains_nul")
    normalized = source_text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    if not normalized.decode("utf-8").lstrip("\ufeff").strip():
        raise _fail("session_evidence_source_empty")
    if SESSION_REF_RE.fullmatch(str(session_ref or "").strip()) is None:
        raise _fail("session_evidence_session_ref_invalid")
    if source_role not in SOURCE_ROLES:
        raise _fail("session_evidence_source_role_invalid")
    if producer_kind not in PRODUCER_KINDS:
        raise _fail("session_evidence_producer_kind_invalid")
    produced_normalized, produced_time = _parse_timestamp(
        produced_at, "session_evidence_produced_at_invalid"
    )
    captured_normalized, captured_time = _parse_timestamp(
        captured_at, "session_evidence_captured_at_invalid"
    )
    if produced_time > captured_time:
        raise _fail("session_evidence_temporal_order_invalid")
    provenance = _normalize_provenance_digests(input_provenance_sha256)
    if source_role in {
        "reviewed_multi_source_bundle",
        "human_reviewed_summary",
    } and not provenance:
        raise _fail("session_evidence_input_provenance_required")
    raw_sha = _sha256(raw)
    normalized_sha = _sha256(normalized)
    session_hash = _sha256(str(session_ref).strip().encode("utf-8"))
    authority = {
        "schema": PLAN_SCHEMA,
        "archive_id": _archive_id(root),
        "source": {
            "raw_sha256": raw_sha,
            "raw_size_bytes": len(raw),
            "normalized_sha256": normalized_sha,
            "normalized_size_bytes": len(normalized),
            "comparison_basis": COMPARISON_BASIS,
        },
        "provenance": {
            "source_role": source_role,
            "producer_kind": producer_kind,
            "produced_at": produced_normalized,
            "captured_at": captured_normalized,
            "session_ref_sha256": "sha256:" + session_hash,
            "input_provenance_sha256": list(provenance),
            "semantic_fidelity_machine_verified": False,
        },
    }
    evidence_digest = _sha256(_canonical_json_bytes(authority))
    evidence_id = "source-fidelity-session-evidence:" + evidence_digest
    plan = {
        **authority,
        "evidence_id": evidence_id,
        "private_storage_create_only": True,
        "digest_only_receipt_create_only": True,
    }
    _require_private_boundaries(
        root,
        input_relative=input_relative,
        storage_relative=f"{STORAGE_PREFIX}/{evidence_digest}.txt",
    )
    return _PreparedEvidence(
        root=root,
        archive_id=authority["archive_id"],
        input_relative=input_relative,
        raw=raw,
        normalized=normalized,
        raw_sha256=raw_sha,
        normalized_sha256=normalized_sha,
        session_ref_sha256=session_hash,
        source_role=source_role,
        producer_kind=producer_kind,
        produced_at=produced_normalized,
        captured_at=captured_normalized,
        input_provenance_sha256=provenance,
        evidence_id=evidence_id,
        evidence_digest=evidence_digest,
        plan_sha256=_sha256(_canonical_json_bytes(plan)),
    )


def plan_session_evidence(
    archive_root: Path | str,
    source_file: Path | str,
    *,
    session_ref: str,
    source_role: str,
    producer_kind: str,
    produced_at: str,
    captured_at: str,
    input_provenance_sha256: Sequence[str] | None = None,
) -> dict[str, Any]:
    try:
        prepared = _prepare(
            archive_root,
            source_file,
            session_ref=session_ref,
            source_role=source_role,
            producer_kind=producer_kind,
            produced_at=produced_at,
            captured_at=captured_at,
            input_provenance_sha256=input_provenance_sha256,
        )
    except SessionEvidenceError as exc:
        result = _base_result(
            action="source_fidelity_session_evidence_plan",
            dry_run=True,
            prepared=None,
        )
        result["blockers"] = [exc.code]
        return result
    return _base_result(
        action="source_fidelity_session_evidence_plan",
        dry_run=True,
        prepared=prepared,
    )


def _storage_relative(prepared: _PreparedEvidence) -> str:
    return f"{STORAGE_PREFIX}/{prepared.evidence_digest}.txt"


def _receipt_relative(prepared: _PreparedEvidence) -> str:
    return f"{RECEIPT_PREFIX}/{prepared.evidence_digest}.json"


def _ensure_directory_chain(root: Path, directory: Path) -> None:
    try:
        relative = directory.relative_to(root)
    except ValueError:
        raise _fail("session_evidence_output_path_unsafe") from None
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
                raise _fail("session_evidence_output_directory_failed") from None
        except OSError:
            raise _fail("session_evidence_output_directory_failed") from None
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise _fail("session_evidence_output_path_unsafe")


def _write_create_if_absent(root: Path, path: Path, value: bytes) -> bool:
    _ensure_directory_chain(root, path.parent)
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
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
            raise OSError("unsafe temporary")
        written = 0
        while written < len(value):
            count = os.write(descriptor, value[written:])
            if count <= 0:
                raise OSError("no write progress")
            written += count
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        try:
            os.link(temporary, path, follow_symlinks=False)
        except TypeError:  # pragma: no cover
            os.link(temporary, path)
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
            pass


def _approved_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _receipt_document(
    prepared: _PreparedEvidence,
    *,
    reviewed_by: str,
    approved_at: str,
) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "action": "approve_source_fidelity_session_evidence",
        "archive_id": prepared.archive_id,
        "evidence_id": prepared.evidence_id,
        "plan_sha256": prepared.plan_sha256,
        "source": {
            "raw_sha256": prepared.raw_sha256,
            "raw_size_bytes": len(prepared.raw),
            "normalized_sha256": prepared.normalized_sha256,
            "normalized_size_bytes": len(prepared.normalized),
            "comparison_basis": COMPARISON_BASIS,
            "newline_transformation_applied": prepared.raw != prepared.normalized,
        },
        "provenance": {
            "source_role": prepared.source_role,
            "producer_kind": prepared.producer_kind,
            "produced_at": prepared.produced_at,
            "captured_at": prepared.captured_at,
            "session_ref_sha256": "sha256:" + prepared.session_ref_sha256,
            "input_provenance_sha256": list(prepared.input_provenance_sha256),
            "semantic_fidelity_machine_verified": False,
        },
        "reviewed_by": reviewed_by,
        "approved_at": approved_at,
        "persistence": {
            "evidence_bytes_create_only": True,
            "receipt_create_only": True,
            "storage_content_sha256": prepared.raw_sha256,
        },
        "content_contract": {
            "source_text_stored_in_receipt": False,
            "source_path_stored": False,
            "raw_session_ref_stored": False,
        },
    }


def _parse_json(raw: bytes) -> Mapping[str, Any] | None:
    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicate,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError):
        return None
    return value if isinstance(value, Mapping) else None


def _receipt_matches(
    raw: bytes,
    prepared: _PreparedEvidence,
    *,
    reviewed_by: str,
) -> bool:
    document = _parse_json(raw)
    if document is None:
        return False
    approved_at = document.get("approved_at")
    try:
        _parse_timestamp(approved_at, "session_evidence_approved_at_invalid")
    except SessionEvidenceError:
        return False
    expected = _receipt_document(
        prepared,
        reviewed_by=reviewed_by,
        approved_at=str(approved_at),
    )
    return document == expected


def _thread_lock(root: Path, evidence_id: str) -> threading.RLock:
    key = os.path.normcase(f"{root}|{evidence_id}")
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


def approve_session_evidence(
    archive_root: Path | str,
    source_file: Path | str,
    *,
    session_ref: str,
    source_role: str,
    producer_kind: str,
    produced_at: str,
    captured_at: str,
    input_provenance_sha256: Sequence[str] | None,
    expected_plan_sha256: str,
    reviewed_by: str,
    exact_human_approval_claim: _ClaimedExactHumanApproval | None = None,
) -> dict[str, Any]:
    if type(exact_human_approval_claim) is not _ClaimedExactHumanApproval:
        result = _base_result(
            action="source_fidelity_session_evidence_approve",
            dry_run=False,
            prepared=None,
        )
        result["ok"] = False
        result["blockers"] = ["exact_human_approval_required"]
        return result
    try:
        prepared = _prepare(
            archive_root,
            source_file,
            session_ref=session_ref,
            source_role=source_role,
            producer_kind=producer_kind,
            produced_at=produced_at,
            captured_at=captured_at,
            input_provenance_sha256=input_provenance_sha256,
        )
    except SessionEvidenceError as exc:
        result = _base_result(
            action="source_fidelity_session_evidence_approve",
            dry_run=False,
            prepared=None,
        )
        result["blockers"] = [exc.code]
        return result
    result = _base_result(
        action="source_fidelity_session_evidence_approve",
        dry_run=False,
        prepared=prepared,
    )
    result["state"] = "blocked"
    if SHA256_RE.fullmatch(str(expected_plan_sha256 or "").strip()) is None:
        result["ok"] = False
        result["blockers"] = ["session_evidence_plan_sha256_invalid"]
        return result
    if not hmac.compare_digest(prepared.plan_sha256, str(expected_plan_sha256).strip()):
        result["ok"] = False
        result["blockers"] = ["session_evidence_plan_changed"]
        return result
    reviewer = str(reviewed_by or "").strip()
    if REVIEWER_RE.fullmatch(reviewer) is None:
        result["ok"] = False
        result["blockers"] = ["session_evidence_reviewer_invalid"]
        return result
    storage_relative = _storage_relative(prepared)
    receipt_relative = _receipt_relative(prepared)
    storage_path = _archive_path(prepared.root, storage_relative)
    receipt_path = _archive_path(prepared.root, receipt_relative)
    try:
        _require_private_boundaries(
            prepared.root,
            input_relative=prepared.input_relative,
            storage_relative=storage_relative,
        )
    except SessionEvidenceError as exc:
        result["ok"] = False
        result["blockers"] = [exc.code]
        return result

    files_written = 0
    with _thread_lock(prepared.root, prepared.evidence_id):
        try:
            existing_bytes = _read_optional_exact(
                prepared.root,
                storage_path,
                maximum=MAX_SOURCE_BYTES,
                invalid_code="session_evidence_existing_bytes_unsafe",
            )
            existing_receipt = _read_optional_exact(
                prepared.root,
                receipt_path,
                maximum=MAX_RECEIPT_BYTES,
                invalid_code="session_evidence_existing_receipt_unsafe",
            )
        except SessionEvidenceError as exc:
            result["ok"] = False
            result["blockers"] = [exc.code]
            return result
        if existing_bytes is not None and not hmac.compare_digest(existing_bytes, prepared.raw):
            result["ok"] = False
            result["blockers"] = ["session_evidence_existing_bytes_conflict"]
            return result
        if existing_receipt is not None and existing_bytes is None:
            result["ok"] = False
            result["blockers"] = ["session_evidence_receipt_without_bytes"]
            return result
        if existing_receipt is not None and not _receipt_matches(
            existing_receipt, prepared, reviewed_by=reviewer
        ):
            result["ok"] = False
            result["blockers"] = ["session_evidence_existing_receipt_conflict"]
            return result
        context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.source_fidelity_session_evidence,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                prepared.archive_id
            ),
            plan_sha256="sha256:" + prepared.plan_sha256,
            target_binding_sha256="sha256:" + prepared.raw_sha256,
            reviewer_claim=reviewer,
            review_binding_codes=(
                "evidence_bytes_reviewed",
                "provenance_reviewed",
                "storage_intent_reviewed",
            ),
            warning_codes=exact_human_approval_warning_codes(
                result.get("warnings")
                if isinstance(result.get("warnings"), list)
                else []
            ),
        )
        try:
            exact_approval_reference = (
                exact_human_approval_claim.assert_ready_for_context(context)
            )
        except ExactHumanApprovalError:
            result["ok"] = False
            result["blockers"] = ["exact_human_approval_invalid"]
            return result
        try:
            if existing_bytes is None:
                _write_create_if_absent(prepared.root, storage_path, prepared.raw)
                files_written += 1
            if existing_receipt is None:
                receipt_bytes = _canonical_json_bytes(
                    _receipt_document(
                        prepared,
                        reviewed_by=reviewer,
                        approved_at=_approved_at(),
                    )
                ) + b"\n"
                _write_create_if_absent(prepared.root, receipt_path, receipt_bytes)
                files_written += 1
        except (OSError, SessionEvidenceError, FileExistsError):
            result["ok"] = False
            result["state"] = "partial" if storage_path.exists() else "failed"
            result["blockers"] = ["session_evidence_write_failed"]
            result["persistence"]["files_written_count"] = files_written
            return result
        try:
            final_bytes = _read_optional_exact(
                prepared.root,
                storage_path,
                maximum=MAX_SOURCE_BYTES,
                invalid_code="session_evidence_existing_bytes_unsafe",
            )
            final_receipt = _read_optional_exact(
                prepared.root,
                receipt_path,
                maximum=MAX_RECEIPT_BYTES,
                invalid_code="session_evidence_existing_receipt_unsafe",
            )
        except SessionEvidenceError:
            final_bytes = None
            final_receipt = None
        bytes_ok = bool(
            final_bytes is not None and hmac.compare_digest(final_bytes, prepared.raw)
        )
        receipt_ok = bool(
            final_receipt is not None
            and _receipt_matches(final_receipt, prepared, reviewed_by=reviewer)
        )
        if not bytes_ok or not receipt_ok:
            result["ok"] = False
            result["state"] = "partial"
            result["blockers"] = ["session_evidence_final_verification_failed"]
            result["persistence"].update(
                {
                    "evidence_bytes_persisted": bytes_ok,
                    "receipt_persisted": receipt_ok,
                    "files_written_count": files_written,
                }
            )
            return result
        if final_receipt is None:
            raise SessionEvidenceError(
                "session_evidence_final_verification_failed"
            )
        exact_approval_link = write_exact_human_approval_link(
            prepared.root,
            approval_claim=exact_human_approval_claim,
            approval_context=context,
            operation=(
                ExactHumanApprovalOperation.source_fidelity_session_evidence
            ),
            plan_sha256=context.plan_sha256,
            target_binding_sha256=context.target_binding_sha256,
            source_operation_receipt=receipt_relative,
            expected_source_operation_receipt_sha256=(
                "sha256:" + _sha256(final_receipt)
            ),
            effect=(
                "created" if files_written > 0 else "already_present_exact"
            ),
        )

    result.update(
        {
            "ok": True,
            "state": "already_written" if files_written == 0 else "written",
            "approved": True,
            "blockers": [],
            "would_change_count": 0,
        }
    )
    result["persistence"].update(
        {
            "evidence_bytes_persisted": True,
            "receipt_persisted": True,
            "files_written_count": files_written,
        }
    )
    result["exact_human_approval_reference"] = exact_approval_reference
    result["exact_human_approval_link"] = exact_approval_link
    return result


def _receipt_shape_valid(document: Mapping[str, Any], evidence_id: str) -> bool:
    try:
        evidence_digest = EVIDENCE_ID_RE.fullmatch(evidence_id).group(1)  # type: ignore[union-attr]
    except AttributeError:
        return False
    if document.get("schema") != RECEIPT_SCHEMA or document.get("evidence_id") != evidence_id:
        return False
    if document.get("action") != "approve_source_fidelity_session_evidence":
        return False
    if not isinstance(document.get("archive_id"), str) or not document.get("archive_id"):
        return False
    if SHA256_RE.fullmatch(str(document.get("plan_sha256") or "")) is None:
        return False
    source = document.get("source")
    provenance = document.get("provenance")
    persistence = document.get("persistence")
    content_contract = document.get("content_contract")
    if not all(isinstance(value, Mapping) for value in (source, provenance, persistence, content_contract)):
        return False
    assert isinstance(source, Mapping)
    assert isinstance(provenance, Mapping)
    if SHA256_RE.fullmatch(str(source.get("raw_sha256") or "")) is None:
        return False
    if SHA256_RE.fullmatch(str(source.get("normalized_sha256") or "")) is None:
        return False
    if any(
        isinstance(source.get(key), bool) or not isinstance(source.get(key), int) or source.get(key) < 0
        for key in ("raw_size_bytes", "normalized_size_bytes")
    ):
        return False
    if source.get("comparison_basis") != COMPARISON_BASIS:
        return False
    if provenance.get("source_role") not in SOURCE_ROLES:
        return False
    if provenance.get("producer_kind") not in PRODUCER_KINDS:
        return False
    if SHA256_REF_RE.fullmatch(str(provenance.get("session_ref_sha256") or "")) is None:
        return False
    inputs = provenance.get("input_provenance_sha256")
    if not isinstance(inputs, list) or any(
        not isinstance(item, str) or SHA256_REF_RE.fullmatch(item) is None for item in inputs
    ):
        return False
    if provenance.get("semantic_fidelity_machine_verified") is not False:
        return False
    try:
        produced, produced_time = _parse_timestamp(
            provenance.get("produced_at"), "session_evidence_receipt_invalid"
        )
        captured, captured_time = _parse_timestamp(
            provenance.get("captured_at"), "session_evidence_receipt_invalid"
        )
        _parse_timestamp(document.get("approved_at"), "session_evidence_receipt_invalid")
    except SessionEvidenceError:
        return False
    if produced != provenance.get("produced_at") or captured != provenance.get("captured_at"):
        return False
    if produced_time > captured_time:
        return False
    if REVIEWER_RE.fullmatch(str(document.get("reviewed_by") or "")) is None:
        return False
    authority = {
        "schema": PLAN_SCHEMA,
        "archive_id": document.get("archive_id"),
        "source": {
            key: source.get(key)
            for key in (
                "raw_sha256",
                "raw_size_bytes",
                "normalized_sha256",
                "normalized_size_bytes",
                "comparison_basis",
            )
        },
        "provenance": dict(provenance),
    }
    if _sha256(_canonical_json_bytes(authority)) != evidence_digest:
        return False
    expected_plan = {
        **authority,
        "evidence_id": evidence_id,
        "private_storage_create_only": True,
        "digest_only_receipt_create_only": True,
    }
    if _sha256(_canonical_json_bytes(expected_plan)) != document.get(
        "plan_sha256"
    ):
        return False
    return bool(
        persistence.get("evidence_bytes_create_only") is True
        and persistence.get("receipt_create_only") is True
        and persistence.get("storage_content_sha256") == source.get("raw_sha256")
        and content_contract.get("source_text_stored_in_receipt") is False
        and content_contract.get("source_path_stored") is False
        and content_contract.get("raw_session_ref_stored") is False
    )


def _read_verified_session_evidence(
    archive_root: Path | str,
    evidence_id: Any,
) -> tuple[dict[str, Any] | None, bytes | None, list[str]]:
    """Read approved private evidence and return only safe metadata plus bytes."""

    normalized_id = str(evidence_id or "").strip().lower()
    match = EVIDENCE_ID_RE.fullmatch(normalized_id)
    if match is None:
        return None, None, ["source_fidelity_session_evidence_id_invalid"]
    try:
        root = _validated_root(archive_root)
        digest = match.group(1)
        storage_path = _archive_path(root, f"{STORAGE_PREFIX}/{digest}.txt")
        receipt_path = _archive_path(root, f"{RECEIPT_PREFIX}/{digest}.json")
        raw = _read_exact_bytes(
            root,
            storage_path,
            maximum=MAX_SOURCE_BYTES,
            missing_code="source_fidelity_session_evidence_missing",
            invalid_code="source_fidelity_session_evidence_unsafe",
        )
        receipt_raw = _read_exact_bytes(
            root,
            receipt_path,
            maximum=MAX_RECEIPT_BYTES,
            missing_code="source_fidelity_session_evidence_receipt_missing",
            invalid_code="source_fidelity_session_evidence_receipt_unsafe",
        )
    except SessionEvidenceError as exc:
        return None, None, [exc.code]
    document = _parse_json(receipt_raw)
    if document is None or not _receipt_shape_valid(document, normalized_id):
        return None, None, ["source_fidelity_session_evidence_receipt_invalid"]
    if document.get("archive_id") != _archive_id(root):
        return None, None, ["source_fidelity_session_evidence_archive_mismatch"]
    source = document["source"]
    if len(raw) != source.get("raw_size_bytes") or _sha256(raw) != source.get("raw_sha256"):
        return None, None, ["source_fidelity_session_evidence_bytes_drift"]
    try:
        text_value = raw.decode("utf-8")
    except UnicodeError:
        return None, None, ["source_fidelity_session_evidence_not_utf8"]
    normalized = text_value.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    if (
        len(normalized) != source.get("normalized_size_bytes")
        or _sha256(normalized) != source.get("normalized_sha256")
    ):
        return None, None, ["source_fidelity_session_evidence_normalization_drift"]
    provenance = document["provenance"]
    evidence = {
        "authority_kind": "reviewed_session_evidence",
        "evidence_id": normalized_id,
        "raw_sha256": source["raw_sha256"],
        "raw_size_bytes": source["raw_size_bytes"],
        "normalized_sha256": source["normalized_sha256"],
        "normalized_size_bytes": source["normalized_size_bytes"],
        "comparison_basis": COMPARISON_BASIS,
        "newline_transformation_applied": source["newline_transformation_applied"],
        "source_role": provenance["source_role"],
        "producer_kind": provenance["producer_kind"],
        "produced_at": provenance["produced_at"],
        "captured_at": provenance["captured_at"],
        "session_ref_sha256": provenance["session_ref_sha256"],
        "input_provenance_sha256": list(provenance["input_provenance_sha256"]),
        "semantic_fidelity_machine_verified": False,
        "receipt_sha256": "sha256:" + _sha256(receipt_raw),
        "source_text_stored": False,
        "source_locator_stored": False,
    }
    return evidence, normalized, []


__all__ = [
    "COMPARISON_BASIS",
    "PRODUCER_KINDS",
    "SOURCE_ROLES",
    "SessionEvidenceError",
    "approve_session_evidence",
    "plan_session_evidence",
]
