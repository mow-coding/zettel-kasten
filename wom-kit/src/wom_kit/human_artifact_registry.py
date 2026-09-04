"""Private registry and append-only lifecycle receipts for human artifacts.

This module is the local registry writer.  It is deliberately separate from
the existing ``human-artifact-store`` planning surface, which remains a
read-only future adapter contract.  Public results expose opaque identifiers,
fixed codes, counts, digests, and booleans only.  Absolute paths and file names
remain inside the ignored-local registry.

Filesystem scans are bounded and metadata-only: ordinary artifact bodies are
never opened or hashed.  A transition therefore records a caller-supplied
content SHA-256 as an exact reviewed binding and states explicitly that the
registry did not verify it by reading content.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

import yaml

from .exact_human_approval import (
    _ClaimedExactHumanApproval,
    exact_human_approval_archive_identity_sha256,
)
from .exact_human_approval_windows import (
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)
from .process_launch import noninteractive_creationflags


REGISTRY_SCHEMA_VERSION = "wom-kit/human-artifact-registry/v0.1"
AUTHORITY_SCHEMA_VERSION = "wom-kit/human-artifact-registry-authority/v0.1"
ROOT_SCHEMA_VERSION = "wom-kit/human-artifact-root-registration/v0.1"
APPROVAL_USE_SCHEMA_VERSION = "wom-kit/human-artifact-approval-use/v0.1"
RECEIPT_SCHEMA_VERSION = "wom-kit/human-artifact-transition-receipt/v0.1"
EXACT_HUMAN_APPROVAL_REFERENCE_SCHEMA = (
    "wom-kit/exact-human-approval-reference/v0.1"
)

REGISTRY_RELATIVE_ROOT = "profiles/local/human-artifact-registry"
AUTHORITY_FILENAME = "authority.json"
ROOTS_DIRECTORY = "roots"
APPROVAL_USES_DIRECTORY = "approval-uses"
RECEIPTS_DIRECTORY = "transition-receipts"
PENDING_DIRECTORY = ".pending"
EXTERNAL_PROJECT_SCAN_RELATIVE_ROOT = ".wom-scratch"
EXTERNAL_DELIVERY_SCAN_RELATIVE_ROOT = "."
# Backward-compatible name for callers that only know the original project
# scratch registration mode.
EXTERNAL_SCAN_RELATIVE_ROOT = EXTERNAL_PROJECT_SCAN_RELATIVE_ROOT
EXTERNAL_ROOT_KINDS = frozenset({"external_project", "external_delivery"})

ARCHIVE_MANAGED_SCOPES = (
    ("archive_scratch", ".wom-scratch"),
    ("archive_workbench_scratch", "workbench/ai-scratch"),
)

LIFECYCLE_STATES = frozenset(
    {
        "working",
        "review_requested",
        "reviewed_current",
        "superseded",
        "preserved_as_objet",
        "distilled_to_zet",
        "discarded_with_receipt",
    }
)
OPEN_STATES = frozenset({"unclassified", "working", "review_requested"})
DURABLE_FATE_STATES = frozenset(
    {
        "reviewed_current",
        "superseded",
        "preserved_as_objet",
        "distilled_to_zet",
        "discarded_with_receipt",
    }
)
ALLOWED_TRANSITIONS = {
    "unclassified": LIFECYCLE_STATES - {"superseded"},
    "working": LIFECYCLE_STATES - {"working"},
    "review_requested": LIFECYCLE_STATES - {"review_requested"},
    "reviewed_current": frozenset(
        {
            "superseded",
            "preserved_as_objet",
            "distilled_to_zet",
            "discarded_with_receipt",
        }
    ),
    "superseded": frozenset(
        {
            "preserved_as_objet",
            "distilled_to_zet",
            "discarded_with_receipt",
        }
    ),
    "preserved_as_objet": frozenset(),
    "distilled_to_zet": frozenset(),
    "discarded_with_receipt": frozenset(),
}

DEFAULT_MAX_ENTRIES_PER_ROOT = 10_000
MAX_ENTRIES_PER_ROOT = 100_000
MAX_REGISTERED_ROOTS = 256
MAX_RECEIPTS_PER_ARTIFACT = 10_000
MAX_CONTROL_FILE_BYTES = 128 * 1024
MAX_GITIGNORE_BYTES = 1 * 1024 * 1024

REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
HMAC_SHA256_RE = re.compile(r"^hmac-sha256:[0-9a-f]{64}$")
APPROVAL_ID_RE = re.compile(r"^approval_[0-9a-f]{32}$")
ROOT_ID_RE = re.compile(r"^har_root_[0-9a-f]{32}$")
ARTIFACT_ID_RE = re.compile(r"^har_artifact_[0-9a-f]{32}$")
VERSION_ID_RE = re.compile(r"^har_version_[0-9a-f]{32}$")
RECEIPT_ID_RE = re.compile(r"^har_receipt_[0-9a-f]{32}$")
ROOT_FILENAME_RE = re.compile(r"^root-binding-[0-9a-f]{64}\.json$")
RECEIPT_FILENAME_RE = re.compile(r"^[0-9a-f]{64}\.json$")
SAFE_ID_RE = re.compile(r"^[a-z][a-z0-9._:-]{0,127}$")
ZET_ID_RE = re.compile(r"^zet_[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")

_AUTHENTICATION_DOMAIN = b"wom-kit/human-artifact-registry-auth/v0.1\x00"
_ARCHIVE_IDENTITY_DOMAIN = b"wom-kit/human-artifact-archive/v0.1\x00"
_ROOT_IDENTITY_DOMAIN = b"wom-kit/human-artifact-root-identity/v0.1\x00"
_ROOT_BINDING_DOMAIN = b"wom-kit/human-artifact-root-binding/v0.1\x00"
_ARTIFACT_ID_DOMAIN = b"wom-kit/human-artifact-id/v0.1\x00"
_VERSION_ID_DOMAIN = b"wom-kit/human-artifact-version/v0.1\x00"
_PLAN_DOMAIN = b"wom-kit/human-artifact-plan/v0.1\x00"
_STATE_DOMAIN = b"wom-kit/human-artifact-current-state/v0.1\x00"


class HumanArtifactRegistryError(RuntimeError):
    """Fixed-code failure that never reflects caller or filesystem values."""

    _CODES = {
        "human_artifact_archive_invalid",
        "human_artifact_private_registry_not_ignored",
        "human_artifact_registry_path_unsafe",
        "human_artifact_registry_document_invalid",
        "human_artifact_registry_authentication_invalid",
        "human_artifact_registry_authority_invalid",
        "human_artifact_external_root_unsafe",
        "human_artifact_external_root_identity_unavailable",
        "human_artifact_external_root_already_registered",
        "human_artifact_root_registration_conflict",
        "human_artifact_expected_plan_mismatch",
        "human_artifact_exact_approval_reference_invalid",
        "human_artifact_exact_approval_replayed",
        "human_artifact_artifact_id_invalid",
        "human_artifact_artifact_not_found",
        "human_artifact_scan_incomplete",
        "human_artifact_transition_state_invalid",
        "human_artifact_transition_not_allowed",
        "human_artifact_content_binding_invalid",
        "human_artifact_related_ref_invalid",
        "human_artifact_current_state_mismatch",
        "human_artifact_transition_conflict",
        "human_artifact_transition_receipt_invalid",
        "human_artifact_artifact_changed_during_transition",
        "human_artifact_time_invalid",
        "human_artifact_randomness_invalid",
    }

    def __init__(self, code: str) -> None:
        self.code = (
            code
            if code in self._CODES
            else "human_artifact_registry_document_invalid"
        )
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"HumanArtifactRegistryError({self.code!r})"


def _fail(code: str) -> HumanArtifactRegistryError:
    return HumanArtifactRegistryError(code)


def _external_scan_relative_root(root_kind: str) -> str:
    if root_kind == "external_project":
        return EXTERNAL_PROJECT_SCAN_RELATIVE_ROOT
    if root_kind == "external_delivery":
        return EXTERNAL_DELIVERY_SCAN_RELATIVE_ROOT
    raise _fail("human_artifact_external_root_unsafe")


def _external_scan_scope_label(root_kind: str) -> str:
    if root_kind == "external_project":
        return "registered_project_root/.wom-scratch"
    if root_kind == "external_delivery":
        return "registered_delivery_root"
    raise _fail("human_artifact_external_root_unsafe")


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                dict(value),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError, UnicodeError):
        raise _fail("human_artifact_registry_document_invalid") from None


def _sha256_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _sha256_document(domain: bytes, value: Mapping[str, Any]) -> str:
    return _sha256_bytes(domain + _canonical_bytes(value))


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        stat.S_ISLNK(info.st_mode)
        or (REPARSE_FLAG and getattr(info, "st_file_attributes", 0) & REPARSE_FLAG)
    )


def _identity(info: os.stat_result) -> dict[str, int]:
    return {
        "mode_type": int(stat.S_IFMT(info.st_mode)),
        "device": int(getattr(info, "st_dev", 0)),
        "inode": int(getattr(info, "st_ino", 0)),
    }


def _directory_snapshot(info: os.stat_result) -> dict[str, int]:
    return {
        **_identity(info),
        "modified_ns": int(info.st_mtime_ns),
    }


def _same_identity(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    return all(
        type(first.get(name)) is int
        and type(second.get(name)) is int
        and first[name] == second[name]
        for name in ("mode_type", "device", "inode")
    )


def _same_directory_snapshot(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> bool:
    return bool(
        _same_identity(first, second)
        and type(first.get("modified_ns")) is int
        and type(second.get("modified_ns")) is int
        and first["modified_ns"] == second["modified_ns"]
    )


def _now(clock: Callable[[], datetime]) -> str:
    try:
        value = clock()
    except BaseException:
        raise _fail("human_artifact_time_invalid") from None
    if type(value) is not datetime or value.tzinfo is None:
        raise _fail("human_artifact_time_invalid")
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _validated_random_hex(
    random_hex: Callable[[int], str],
    *,
    prefix: str,
) -> str:
    try:
        value = random_hex(16)
    except BaseException:
        raise _fail("human_artifact_randomness_invalid") from None
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{32}", value) is None:
        raise _fail("human_artifact_randomness_invalid")
    return prefix + value


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _fail("human_artifact_registry_document_invalid")
        result[key] = value
    return result


def _read_stable_bytes(path: Path, *, maximum: int, code: str) -> bytes:
    descriptor: int | None = None
    try:
        before = os.lstat(path)
        if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise _fail(code)
        flags = os.O_RDONLY
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            _is_reparse(opened)
            or not stat.S_ISREG(opened.st_mode)
            or (int(before.st_dev), int(before.st_ino))
            != (int(opened.st_dev), int(opened.st_ino))
        ):
            raise _fail(code)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(64 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise _fail(code)
        opened_after = os.fstat(descriptor)
        after = os.lstat(path)
        if (
            (int(opened.st_dev), int(opened.st_ino), int(opened.st_size))
            != (
                int(opened_after.st_dev),
                int(opened_after.st_ino),
                int(opened_after.st_size),
            )
            or (int(before.st_dev), int(before.st_ino))
            != (int(after.st_dev), int(after.st_ino))
            or _is_reparse(after)
        ):
            raise _fail(code)
        return b"".join(chunks)
    except HumanArtifactRegistryError:
        raise
    except OSError:
        raise _fail(code) from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _read_json_document(path: Path, *, code: str) -> dict[str, Any]:
    raw = _read_stable_bytes(path, maximum=MAX_CONTROL_FILE_BYTES, code=code)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs)
    except HumanArtifactRegistryError:
        raise
    except (UnicodeError, json.JSONDecodeError):
        raise _fail(code) from None
    if not isinstance(value, Mapping):
        raise _fail(code)
    document = dict(value)
    if not hmac.compare_digest(raw, _canonical_bytes(document)):
        raise _fail(code)
    return document


def _exclusive_create(
    path: Path,
    document: Mapping[str, Any],
    *,
    pending_directory: Path,
    code: str,
) -> None:
    raw = _canonical_bytes(document)
    descriptor: int | None = None
    temporary: Path | None = None
    try:
        _safe_directory(pending_directory, create=True)
        temporary = pending_directory / (
            "pending_" + secrets.token_hex(16) + ".json"
        )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        descriptor = os.open(temporary, flags, 0o600)
        view = memoryview(raw)
        offset = 0
        while offset < len(view):
            written = os.write(descriptor, view[offset:])
            if written <= 0:
                raise OSError("short write")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.link(temporary, path)
    except FileExistsError:
        raise _fail(code) from None
    except HumanArtifactRegistryError:
        raise
    except OSError:
        raise _fail(code) from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            except OSError:
                # The final create-only document, if linked, remains valid.
                # A stranded pending file is intentionally never treated as
                # registry state or automatically garbage-collected here.
                pass


@dataclass(frozen=True)
class _ArchiveContext:
    root: Path
    archive_id: str
    identity_sha256: str


@dataclass(frozen=True)
class _ObservedArtifact:
    artifact_id: str
    root_id: str
    root_kind: str
    path: Path
    observation: dict[str, Any]


@dataclass(frozen=True)
class _ReceiptChain:
    receipts: tuple[dict[str, Any], ...]

    @property
    def latest(self) -> dict[str, Any] | None:
        return self.receipts[-1] if self.receipts else None


@dataclass(frozen=True)
class _ArtifactState:
    observed: _ObservedArtifact
    chain: _ReceiptChain
    lifecycle_state: str
    current_state: dict[str, Any]
    current_state_sha256: str
    artifact_version_id: str | None
    content_sha256: str | None
    version_relationship: str


@dataclass(frozen=True)
class _ScanResult:
    public: dict[str, Any]
    states: dict[str, _ArtifactState]
    chains: dict[str, _ReceiptChain]
    authority: tuple[bytes, dict[str, Any]] | None


def _validated_archive(archive_root: Path | str) -> _ArchiveContext:
    try:
        supplied = Path(os.path.abspath(os.fspath(Path(archive_root).expanduser())))
        supplied_info = os.lstat(supplied)
        if _is_reparse(supplied_info) or not stat.S_ISDIR(supplied_info.st_mode):
            raise _fail("human_artifact_archive_invalid")
        root = supplied.resolve(strict=True)
        if not os.path.samefile(supplied, root):
            raise _fail("human_artifact_archive_invalid")
        marker_raw = _read_stable_bytes(
            root / "archive.yml",
            maximum=64 * 1024,
            code="human_artifact_archive_invalid",
        )
        marker = yaml.safe_load(marker_raw.decode("utf-8"))
    except HumanArtifactRegistryError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError, UnicodeError, yaml.YAMLError):
        raise _fail("human_artifact_archive_invalid") from None
    archive_id = marker.get("archive_id") if isinstance(marker, Mapping) else None
    if type(archive_id) is not str or SAFE_ID_RE.fullmatch(archive_id) is None:
        raise _fail("human_artifact_archive_invalid")
    identity_sha256 = _sha256_bytes(
        _ARCHIVE_IDENTITY_DOMAIN + archive_id.encode("utf-8")
    )
    return _ArchiveContext(root=root, archive_id=archive_id, identity_sha256=identity_sha256)


def _safe_directory(path: Path, *, create: bool) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        if not create:
            raise
        try:
            path.mkdir()
            info = os.lstat(path)
        except FileExistsError:
            try:
                info = os.lstat(path)
            except OSError:
                raise _fail("human_artifact_registry_path_unsafe") from None
        except OSError:
            raise _fail("human_artifact_registry_path_unsafe") from None
    except OSError:
        raise _fail("human_artifact_registry_path_unsafe") from None
    if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
        raise _fail("human_artifact_registry_path_unsafe")


def _registry_path(context: _ArchiveContext, *, create: bool) -> Path | None:
    current = context.root
    for name in PurePosixPath(REGISTRY_RELATIVE_ROOT).parts:
        current = current / name
        try:
            _safe_directory(current, create=create)
        except FileNotFoundError:
            return None
    return current


def _registry_subdirectory(
    context: _ArchiveContext,
    name: str,
    *,
    create: bool,
) -> Path | None:
    root = _registry_path(context, create=create)
    if root is None:
        return None
    child = root / name
    try:
        _safe_directory(child, create=create)
    except FileNotFoundError:
        return None
    return child


def _require_private_registry_ignored(context: _ArchiveContext) -> None:
    try:
        raw = _read_stable_bytes(
            context.root / ".gitignore",
            maximum=MAX_GITIGNORE_BYTES,
            code="human_artifact_private_registry_not_ignored",
        )
        text = raw.decode("utf-8-sig")
    except HumanArtifactRegistryError:
        raise
    except UnicodeError:
        raise _fail("human_artifact_private_registry_not_ignored") from None
    if "\x00" in text:
        raise _fail("human_artifact_private_registry_not_ignored")
    ignored = False
    reincluded = False
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        if line in {
            "profiles/local/",
            "/profiles/local/",
            "profiles/local",
            "/profiles/local",
        }:
            ignored = True
            reincluded = False
        elif ignored and line.startswith("!"):
            reincluded = True
    if not ignored or reincluded:
        raise _fail("human_artifact_private_registry_not_ignored")

    git_admin_present = False
    for candidate in (context.root, *context.root.parents):
        try:
            os.lstat(candidate / ".git")
        except FileNotFoundError:
            continue
        except OSError:
            raise _fail("human_artifact_private_registry_not_ignored") from None
        git_admin_present = True
        break
    if not git_admin_present:
        return
    try:
        tracked = subprocess.run(
            [
                "git",
                "-C",
                os.fspath(context.root),
                "ls-files",
                "--",
                REGISTRY_RELATIVE_ROOT,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
            creationflags=noninteractive_creationflags(),
        )
    except (OSError, subprocess.SubprocessError):
        raise _fail("human_artifact_private_registry_not_ignored") from None
    if tracked.returncode != 0 or tracked.stdout.strip():
        raise _fail("human_artifact_private_registry_not_ignored")


def _validate_external_directory(path: Path | str) -> tuple[Path, dict[str, int]]:
    try:
        supplied = Path(os.path.abspath(os.fspath(Path(path).expanduser())))
        anchor = Path(supplied.anchor)
        current = anchor
        parts = supplied.parts[1:] if supplied.anchor else supplied.parts
        for part in parts:
            current = current / part
            info = os.lstat(current)
            if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
                raise _fail("human_artifact_external_root_unsafe")
        resolved = supplied.resolve(strict=True)
        final = os.lstat(resolved)
        if (
            _is_reparse(final)
            or not stat.S_ISDIR(final.st_mode)
            or not os.path.samefile(supplied, resolved)
        ):
            raise _fail("human_artifact_external_root_unsafe")
    except HumanArtifactRegistryError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError):
        raise _fail("human_artifact_external_root_unsafe") from None
    identity = _identity(final)
    if identity["inode"] <= 0:
        raise _fail("human_artifact_external_root_identity_unavailable")
    return resolved, identity


def _root_identity_sha256(identity: Mapping[str, Any]) -> str:
    return _sha256_document(_ROOT_IDENTITY_DOMAIN, identity)


def _root_binding_hex(path: Path) -> str:
    normalized = os.path.normcase(os.path.normpath(os.fspath(path)))
    return hashlib.sha256(
        _ROOT_BINDING_DOMAIN + normalized.encode("utf-8")
    ).hexdigest()


def _artifact_id(
    context: _ArchiveContext,
    *,
    root_id: str,
    relative_path: str,
) -> str:
    digest = hashlib.sha256(
        _ARTIFACT_ID_DOMAIN
        + context.identity_sha256.encode("ascii")
        + b"\x00"
        + root_id.encode("ascii")
        + b"\x00"
        + relative_path.encode("utf-8")
    ).hexdigest()
    return "har_artifact_" + digest[:32]


def _artifact_version_id(
    artifact_id: str,
    content_sha256: str,
    size_bytes: int,
) -> str:
    digest = hashlib.sha256(
        _VERSION_ID_DOMAIN
        + artifact_id.encode("ascii")
        + b"\x00"
        + content_sha256.encode("ascii")
        + b"\x00"
        + str(size_bytes).encode("ascii")
    ).hexdigest()
    return "har_version_" + digest[:32]


def _observation(
    artifact_id: str,
    info: os.stat_result,
) -> dict[str, Any]:
    core = {
        "artifact_id": artifact_id,
        "size_bytes": int(info.st_size),
        "modified_ns": int(info.st_mtime_ns),
        "device": int(info.st_dev),
        "inode": int(info.st_ino),
    }
    return {
        **core,
        "observation_sha256": _sha256_document(_STATE_DOMAIN, core),
    }


def _validate_exact_approval_reference(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail("human_artifact_exact_approval_reference_invalid")
    result = dict(value)
    if set(result) != {
        "schema_version",
        "approval_id",
        "context_sha256",
        "approval_authority_sha256",
        "one_use",
    }:
        raise _fail("human_artifact_exact_approval_reference_invalid")
    if result.get("schema_version") != EXACT_HUMAN_APPROVAL_REFERENCE_SCHEMA:
        raise _fail("human_artifact_exact_approval_reference_invalid")
    if type(result.get("approval_id")) is not str or APPROVAL_ID_RE.fullmatch(
        result["approval_id"]
    ) is None:
        raise _fail("human_artifact_exact_approval_reference_invalid")
    for name in ("context_sha256", "approval_authority_sha256"):
        if type(result.get(name)) is not str or SHA256_RE.fullmatch(result[name]) is None:
            raise _fail("human_artifact_exact_approval_reference_invalid")
    if result.get("one_use") is not True:
        raise _fail("human_artifact_exact_approval_reference_invalid")
    return result


def _validate_related_refs(
    values: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, str]]:
    if values is None:
        return []
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise _fail("human_artifact_related_ref_invalid")
    if len(values) > 32:
        raise _fail("human_artifact_related_ref_invalid")
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for value in values:
        if not isinstance(value, Mapping) or set(value) != {"kind", "ref"}:
            raise _fail("human_artifact_related_ref_invalid")
        kind = value.get("kind")
        ref = value.get("ref")
        if type(kind) is not str or type(ref) is not str:
            raise _fail("human_artifact_related_ref_invalid")
        valid = bool(
            (kind == "object_id" and SHA256_RE.fullmatch(ref))
            or (kind == "zet_id" and ZET_ID_RE.fullmatch(ref))
            or (kind == "receipt_id" and SAFE_ID_RE.fullmatch(ref))
            or (kind == "artifact_version_id" and VERSION_ID_RE.fullmatch(ref))
        )
        if not valid or (kind, ref) in seen:
            raise _fail("human_artifact_related_ref_invalid")
        seen.add((kind, ref))
        result.append({"kind": kind, "ref": ref})
    return result


def _require_target_related_ref(
    target_state: str,
    refs: Sequence[Mapping[str, str]],
    *,
    code: str,
) -> None:
    required_kind = {
        "superseded": "artifact_version_id",
        "preserved_as_objet": "object_id",
        "distilled_to_zet": "zet_id",
    }.get(target_state)
    if required_kind is not None and not any(
        value.get("kind") == required_kind for value in refs
    ):
        raise _fail(code)


def _validate_content_binding(content_sha256: str, size_bytes: int) -> None:
    if type(content_sha256) is not str or SHA256_RE.fullmatch(content_sha256) is None:
        raise _fail("human_artifact_content_binding_invalid")
    if type(size_bytes) is not int or size_bytes < 0:
        raise _fail("human_artifact_content_binding_invalid")


def _authentication_payload(document: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(document)
    payload.pop("authentication", None)
    return payload


def _document_mac(document: Mapping[str, Any], key: bytes) -> str:
    return "hmac-sha256:" + hmac.new(
        key,
        _AUTHENTICATION_DOMAIN + _canonical_bytes(_authentication_payload(document)),
        hashlib.sha256,
    ).hexdigest()


def _authenticated(document: Mapping[str, Any], key: bytes) -> dict[str, Any]:
    result = dict(document)
    result["authentication"] = {
        "algorithm": "hmac-sha256",
        "mac": _document_mac(result, key),
    }
    return result


def _validate_authentication(document: Mapping[str, Any], key: bytes) -> None:
    authentication = document.get("authentication")
    if (
        not isinstance(authentication, Mapping)
        or set(authentication) != {"algorithm", "mac"}
        or authentication.get("algorithm") != "hmac-sha256"
        or type(authentication.get("mac")) is not str
        or HMAC_SHA256_RE.fullmatch(authentication["mac"]) is None
        or not hmac.compare_digest(authentication["mac"], _document_mac(document, key))
    ):
        raise _fail("human_artifact_registry_authentication_invalid")


def _validated_random_bytes(random_bytes: Callable[[int], bytes]) -> bytes:
    try:
        value = random_bytes(32)
    except BaseException:
        raise _fail("human_artifact_randomness_invalid") from None
    if type(value) is not bytes or len(value) != 32:
        raise _fail("human_artifact_randomness_invalid")
    return value


def _load_authority(
    context: _ArchiveContext,
    *,
    create: bool,
    clock: Callable[[], datetime] = _default_clock,
    random_bytes: Callable[[int], bytes] = secrets.token_bytes,
) -> tuple[bytes, dict[str, Any]] | None:
    registry = _registry_path(context, create=create)
    if registry is None:
        return None
    path = registry / AUTHORITY_FILENAME
    try:
        document = _read_json_document(
            path,
            code="human_artifact_registry_authority_invalid",
        )
    except HumanArtifactRegistryError as exc:
        if exc.code != "human_artifact_registry_authority_invalid":
            raise
        try:
            os.lstat(path)
        except FileNotFoundError:
            if not create:
                return None
            key = _validated_random_bytes(random_bytes)
            created = {
                "schema_version": AUTHORITY_SCHEMA_VERSION,
                "authority_id": _sha256_bytes(
                    _AUTHENTICATION_DOMAIN + key
                ),
                "key_hex": key.hex(),
                "created_at": _now(clock),
            }
            try:
                _exclusive_create(
                    path,
                    created,
                    pending_directory=registry / PENDING_DIRECTORY,
                    code="human_artifact_registry_authority_invalid",
                )
                return key, created
            except HumanArtifactRegistryError:
                document = _read_json_document(
                    path,
                    code="human_artifact_registry_authority_invalid",
                )
        except OSError:
            raise _fail("human_artifact_registry_authority_invalid") from None
        else:
            raise
    if set(document) != {
        "schema_version",
        "authority_id",
        "key_hex",
        "created_at",
    } or document.get("schema_version") != AUTHORITY_SCHEMA_VERSION:
        raise _fail("human_artifact_registry_authority_invalid")
    key_hex = document.get("key_hex")
    if type(key_hex) is not str or re.fullmatch(r"[0-9a-f]{64}", key_hex) is None:
        raise _fail("human_artifact_registry_authority_invalid")
    key = bytes.fromhex(key_hex)
    expected_authority = _sha256_bytes(_AUTHENTICATION_DOMAIN + key)
    if (
        type(document.get("authority_id")) is not str
        or not hmac.compare_digest(document["authority_id"], expected_authority)
        or type(document.get("created_at")) is not str
    ):
        raise _fail("human_artifact_registry_authority_invalid")
    return key, document


def _validate_root_document(document: Mapping[str, Any], key: bytes) -> dict[str, Any]:
    result = dict(document)
    if set(result) != {
        "schema_version",
        "root_id",
        "root_kind",
        "canonical_path",
        "scan_relative_root",
        "identity",
        "identity_sha256",
        "registered_at",
        "registration_plan_sha256",
        "approval_reference",
        "registry_writer_role",
        "authentication",
    } or result.get("schema_version") != ROOT_SCHEMA_VERSION:
        raise _fail("human_artifact_registry_document_invalid")
    if type(result.get("root_id")) is not str or ROOT_ID_RE.fullmatch(result["root_id"]) is None:
        raise _fail("human_artifact_registry_document_invalid")
    root_kind = result.get("root_kind")
    if root_kind not in EXTERNAL_ROOT_KINDS:
        raise _fail("human_artifact_registry_document_invalid")
    if type(result.get("canonical_path")) is not str or not os.path.isabs(
        result["canonical_path"]
    ):
        raise _fail("human_artifact_registry_document_invalid")
    if result.get("scan_relative_root") != _external_scan_relative_root(
        str(root_kind)
    ):
        raise _fail("human_artifact_registry_document_invalid")
    identity = result.get("identity")
    if (
        not isinstance(identity, Mapping)
        or set(identity) != {"mode_type", "device", "inode"}
        or any(type(identity.get(name)) is not int for name in identity)
        or identity.get("inode", 0) <= 0
    ):
        raise _fail("human_artifact_registry_document_invalid")
    if (
        type(result.get("identity_sha256")) is not str
        or not hmac.compare_digest(
            result["identity_sha256"], _root_identity_sha256(identity)
        )
        or type(result.get("registered_at")) is not str
        or type(result.get("registration_plan_sha256")) is not str
        or SHA256_RE.fullmatch(result["registration_plan_sha256"]) is None
        or result.get("registry_writer_role") != "actual_local_registry_writer"
    ):
        raise _fail("human_artifact_registry_document_invalid")
    result["approval_reference"] = _validate_exact_approval_reference(
        result.get("approval_reference")
    )
    _validate_authentication(result, key)
    return result


def _load_root_documents(
    context: _ArchiveContext,
    authority: tuple[bytes, dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    directory = _registry_subdirectory(context, ROOTS_DIRECTORY, create=False)
    if directory is None:
        return []
    if authority is None:
        raise _fail("human_artifact_registry_authority_invalid")
    key = authority[0]
    try:
        entries = list(os.scandir(directory))
    except OSError:
        raise _fail("human_artifact_registry_path_unsafe") from None
    if len(entries) > MAX_REGISTERED_ROOTS:
        raise _fail("human_artifact_registry_document_invalid")
    roots: list[dict[str, Any]] = []
    ids: set[str] = set()
    for entry in sorted(entries, key=lambda item: item.name):
        if ROOT_FILENAME_RE.fullmatch(entry.name) is None:
            raise _fail("human_artifact_registry_document_invalid")
        try:
            info = entry.stat(follow_symlinks=False)
        except OSError:
            raise _fail("human_artifact_registry_document_invalid") from None
        if _is_reparse(info) or not stat.S_ISREG(info.st_mode):
            raise _fail("human_artifact_registry_document_invalid")
        document = _validate_root_document(
            _read_json_document(
                Path(entry.path),
                code="human_artifact_registry_document_invalid",
            ),
            key,
        )
        expected_name = "root-binding-" + _root_binding_hex(
            Path(document["canonical_path"])
        ) + ".json"
        expected_plan = _plan_sha256(
            {
                "operation": "register_project_root",
                "archive_identity_sha256": context.identity_sha256,
                "root_identity_sha256": document["identity_sha256"],
                "root_binding_sha256": (
                    "sha256:"
                    + _root_binding_hex(Path(document["canonical_path"]))
                ),
                "scan_relative_root": document["scan_relative_root"],
                "root_kind": document["root_kind"],
                "registry_writer_role": document["registry_writer_role"],
            }
        )
        if not (
            hmac.compare_digest(entry.name, expected_name)
            and hmac.compare_digest(
                document["registration_plan_sha256"],
                expected_plan,
            )
        ):
            raise _fail("human_artifact_registry_document_invalid")
        if document["root_id"] in ids:
            raise _fail("human_artifact_registry_document_invalid")
        ids.add(document["root_id"])
        roots.append(document)
    return roots


def _validate_registered_root(document: Mapping[str, Any]) -> tuple[Path, str | None]:
    try:
        path, identity = _validate_external_directory(document["canonical_path"])
    except HumanArtifactRegistryError:
        return Path(document["canonical_path"]), "registered_root_unsafe"
    if not _same_identity(document["identity"], identity):
        return path, "registered_root_identity_drift"
    if not hmac.compare_digest(
        document["identity_sha256"], _root_identity_sha256(identity)
    ):
        return path, "registered_root_identity_drift"
    return path, None


def _validate_approval_use_document(
    document: Mapping[str, Any],
    key: bytes,
) -> dict[str, Any]:
    result = dict(document)
    if set(result) != {
        "schema_version",
        "approval_id",
        "operation",
        "target_id",
        "context_sha256",
        "approval_authority_sha256",
        "used_at",
        "authentication",
    } or result.get("schema_version") != APPROVAL_USE_SCHEMA_VERSION:
        raise _fail("human_artifact_registry_document_invalid")
    if type(result.get("approval_id")) is not str or APPROVAL_ID_RE.fullmatch(
        result["approval_id"]
    ) is None:
        raise _fail("human_artifact_registry_document_invalid")
    if result.get("operation") not in {"register_project_root", "transition_artifact"}:
        raise _fail("human_artifact_registry_document_invalid")
    if type(result.get("target_id")) is not str or not (
        ROOT_ID_RE.fullmatch(result["target_id"])
        or ARTIFACT_ID_RE.fullmatch(result["target_id"])
    ):
        raise _fail("human_artifact_registry_document_invalid")
    for name in ("context_sha256", "approval_authority_sha256"):
        if type(result.get(name)) is not str or SHA256_RE.fullmatch(result[name]) is None:
            raise _fail("human_artifact_registry_document_invalid")
    if type(result.get("used_at")) is not str:
        raise _fail("human_artifact_registry_document_invalid")
    _validate_authentication(result, key)
    return result


def _spend_approval(
    context: _ArchiveContext,
    key: bytes,
    approval_reference: Mapping[str, Any],
    *,
    operation: str,
    target_id: str,
    used_at: str,
) -> None:
    directory = _registry_subdirectory(
        context,
        APPROVAL_USES_DIRECTORY,
        create=True,
    )
    assert directory is not None
    document = _authenticated(
        {
            "schema_version": APPROVAL_USE_SCHEMA_VERSION,
            "approval_id": approval_reference["approval_id"],
            "operation": operation,
            "target_id": target_id,
            "context_sha256": approval_reference["context_sha256"],
            "approval_authority_sha256": approval_reference[
                "approval_authority_sha256"
            ],
            "used_at": used_at,
        },
        key,
    )
    _validate_approval_use_document(document, key)
    path = directory / (approval_reference["approval_id"] + ".json")
    pending = _registry_subdirectory(
        context,
        PENDING_DIRECTORY,
        create=True,
    )
    assert pending is not None
    _exclusive_create(
        path,
        document,
        pending_directory=pending,
        code="human_artifact_exact_approval_replayed",
    )


def _plan_sha256(document: Mapping[str, Any]) -> str:
    return _sha256_document(_PLAN_DOMAIN, document)


def _approval_target_binding(document: Mapping[str, Any]) -> str:
    return _sha256_document(_PLAN_DOMAIN, document)


def project_root_registration_approval_context(
    archive_root: Path | str,
    project_root: Path | str,
    *,
    reviewer_claim: str,
    root_kind: str = "external_project",
) -> ExactHumanApprovalContext:
    """Build the only exact-human context accepted by root registration."""

    context = _validated_archive(archive_root)
    plan = plan_project_root_registration(
        archive_root,
        project_root,
        root_kind=root_kind,
    )
    target_binding = _approval_target_binding(
        {
            "operation": "register_project_root",
            "plan_sha256": plan["plan_sha256"],
            "root_identity_sha256": plan["root_identity_sha256"],
            "scan_scope": plan["scan_scope"],
        }
    )
    return ExactHumanApprovalContext(
        operation=ExactHumanApprovalOperation.human_artifact_lifecycle,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(
            context.archive_id
        ),
        plan_sha256=plan["plan_sha256"],
        target_binding_sha256=target_binding,
        reviewer_claim=reviewer_claim,
        review_binding_codes=(
            "project_root_identity",
            "registry_plan",
            "scan_scope",
        ),
        warning_codes=(),
    )


def plan_project_root_registration(
    archive_root: Path | str,
    project_root: Path | str,
    *,
    root_kind: str = "external_project",
) -> dict[str, Any]:
    """Return a write-free, path-free registration plan for one project root."""

    context = _validated_archive(archive_root)
    _require_private_registry_ignored(context)
    scan_relative_root = _external_scan_relative_root(root_kind)
    scan_scope = _external_scan_scope_label(root_kind)
    external, identity = _validate_external_directory(project_root)
    if os.path.samefile(external, context.root):
        raise _fail("human_artifact_external_root_unsafe")
    authority = _load_authority(context, create=False)
    roots = _load_root_documents(context, authority)
    for registered in roots:
        try:
            duplicate = os.path.samefile(external, registered["canonical_path"])
        except OSError:
            duplicate = False
        if duplicate:
            raise _fail("human_artifact_external_root_already_registered")
    plan_document = {
        "operation": "register_project_root",
        "archive_identity_sha256": context.identity_sha256,
        "root_identity_sha256": _root_identity_sha256(identity),
        "root_binding_sha256": "sha256:" + _root_binding_hex(external),
        "root_kind": root_kind,
        "scan_relative_root": scan_relative_root,
        "registry_writer_role": "actual_local_registry_writer",
    }
    return {
        "ok": True,
        "state": "ready_for_exact_human_approval",
        "lifecycle_action": "human_artifact_project_root_registration_plan",
        "plan_sha256": _plan_sha256(plan_document),
        "root_identity_sha256": plan_document["root_identity_sha256"],
        "registered_root_kind": root_kind,
        "scan_scope": scan_scope,
        "registry_writer_role": "actual_local_registry_writer",
        "human_artifact_store_adapter_write_performed": False,
        "requires_exact_human_approval_claim": True,
        "would_change": ["private_registry_root_registration"],
        "privacy_guards": {
            "absolute_paths_echoed": False,
            "file_names_echoed": False,
            "artifact_bodies_read": False,
            "provider_called": False,
        },
    }


def register_project_root(
    archive_root: Path | str,
    project_root: Path | str,
    *,
    expected_plan_sha256: str,
    approval_claim: _ClaimedExactHumanApproval,
    reviewer_claim: str,
    root_kind: str = "external_project",
    clock: Callable[[], datetime] = _default_clock,
    random_hex: Callable[[int], str] = secrets.token_hex,
    random_bytes: Callable[[int], bytes] = secrets.token_bytes,
) -> dict[str, Any]:
    """Create one private root registration after exact claim reauthentication."""

    if type(approval_claim) is not _ClaimedExactHumanApproval:
        raise _fail("human_artifact_exact_approval_reference_invalid")
    plan = plan_project_root_registration(
        archive_root,
        project_root,
        root_kind=root_kind,
    )
    if (
        type(expected_plan_sha256) is not str
        or not hmac.compare_digest(expected_plan_sha256, plan["plan_sha256"])
    ):
        raise _fail("human_artifact_expected_plan_mismatch")
    context = _validated_archive(archive_root)
    _require_private_registry_ignored(context)
    external, identity = _validate_external_directory(project_root)
    exact_context = project_root_registration_approval_context(
        archive_root,
        project_root,
        reviewer_claim=reviewer_claim,
        root_kind=root_kind,
    )
    approval = _validate_exact_approval_reference(
        approval_claim.assert_ready_for_context(exact_context)
    )
    authority = _load_authority(
        context,
        create=True,
        clock=clock,
        random_bytes=random_bytes,
    )
    assert authority is not None
    key = authority[0]
    roots = _registry_subdirectory(context, ROOTS_DIRECTORY, create=True)
    assert roots is not None
    root_id = _validated_random_hex(random_hex, prefix="har_root_")
    registered_at = _now(clock)
    try:
        _spend_approval(
            context,
            key,
            approval,
            operation="register_project_root",
            target_id=root_id,
            used_at=registered_at,
        )
        document = _authenticated(
            {
                "schema_version": ROOT_SCHEMA_VERSION,
                "root_id": root_id,
                "root_kind": root_kind,
                "canonical_path": os.fspath(external),
                "scan_relative_root": _external_scan_relative_root(root_kind),
                "identity": identity,
                "identity_sha256": _root_identity_sha256(identity),
                "registered_at": registered_at,
                "registration_plan_sha256": plan["plan_sha256"],
                "approval_reference": approval,
                "registry_writer_role": "actual_local_registry_writer",
            },
            key,
        )
        filename = "root-binding-" + _root_binding_hex(external) + ".json"
        _exclusive_create(
            roots / filename,
            document,
            pending_directory=(
                context.root / REGISTRY_RELATIVE_ROOT / PENDING_DIRECTORY
            ),
            code="human_artifact_root_registration_conflict",
        )
    except BaseException:
        # The shared exact-human workflow is the sole terminal-state owner.
        # If this writer fails after any uncertain append, leaving the claim
        # started is the reconciliation-safe outcome.
        raise
    return {
        "ok": True,
        "state": "registered",
        "lifecycle_action": "human_artifact_project_root_registration",
        "root_id": root_id,
        "root_identity_sha256": document["identity_sha256"],
        "registered_root_kind": root_kind,
        "scan_scope": _external_scan_scope_label(root_kind),
        "registry_writer_role": "actual_local_registry_writer",
        "human_artifact_store_adapter_write_performed": False,
        "exact_human_approval_reference_shape_validated": True,
        "exact_human_approval_claim_reauthenticated": True,
        "exact_human_approval_claim_finalized": False,
        "exact_human_approval_claim_finalization_owner": "approval_workflow",
        "files_written": [
            "private_registry_approval_use",
            "private_registry_root_registration",
        ],
        "privacy_guards": {
            "absolute_paths_echoed": False,
            "file_names_echoed": False,
            "artifact_bodies_read": False,
            "provider_called": False,
        },
    }


def _state_document(
    *,
    artifact_id: str,
    observation_sha256: str,
    lifecycle_state: str,
    artifact_version_id: str | None,
    content_sha256: str | None,
    size_bytes: int,
    last_receipt_id: str | None,
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "observation_sha256": observation_sha256,
        "lifecycle_state": lifecycle_state,
        "artifact_version_id": artifact_version_id,
        "content_sha256": content_sha256,
        "size_bytes": size_bytes,
        "last_receipt_id": last_receipt_id,
    }


def _state_sha256(document: Mapping[str, Any]) -> str:
    return _sha256_document(_STATE_DOMAIN, document)


def _validate_observation(value: Any, *, artifact_id: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail("human_artifact_transition_receipt_invalid")
    result = dict(value)
    if set(result) != {
        "artifact_id",
        "size_bytes",
        "modified_ns",
        "device",
        "inode",
        "observation_sha256",
    }:
        raise _fail("human_artifact_transition_receipt_invalid")
    if result.get("artifact_id") != artifact_id:
        raise _fail("human_artifact_transition_receipt_invalid")
    for name in ("size_bytes", "modified_ns", "device", "inode"):
        if type(result.get(name)) is not int or result[name] < 0:
            raise _fail("human_artifact_transition_receipt_invalid")
    core = {name: result[name] for name in result if name != "observation_sha256"}
    if (
        type(result.get("observation_sha256")) is not str
        or not hmac.compare_digest(
            result["observation_sha256"], _sha256_document(_STATE_DOMAIN, core)
        )
    ):
        raise _fail("human_artifact_transition_receipt_invalid")
    return result


def _validate_version(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _fail("human_artifact_transition_receipt_invalid")
    result = dict(value)
    if set(result) != {
        "artifact_version_id",
        "content_sha256",
        "size_bytes",
        "relationship",
        "previous_artifact_version_id",
    }:
        raise _fail("human_artifact_transition_receipt_invalid")
    if type(result.get("artifact_version_id")) is not str or VERSION_ID_RE.fullmatch(
        result["artifact_version_id"]
    ) is None:
        raise _fail("human_artifact_transition_receipt_invalid")
    _validate_content_binding(result.get("content_sha256"), result.get("size_bytes"))
    if result.get("relationship") not in {"initial", "same_version", "supersedes"}:
        raise _fail("human_artifact_transition_receipt_invalid")
    previous = result.get("previous_artifact_version_id")
    if previous is not None and (
        type(previous) is not str or VERSION_ID_RE.fullmatch(previous) is None
    ):
        raise _fail("human_artifact_transition_receipt_invalid")
    if (result["relationship"] == "initial") != (previous is None):
        raise _fail("human_artifact_transition_receipt_invalid")
    return result


def _validate_receipt_document(
    document: Mapping[str, Any],
    key: bytes,
) -> dict[str, Any]:
    result = dict(document)
    if set(result) != {
        "schema_version",
        "receipt_id",
        "artifact_id",
        "root_id",
        "root_kind",
        "sequence",
        "previous_receipt_id",
        "expected_current_state_sha256",
        "resulting_current_state_sha256",
        "from_state",
        "to_state",
        "observation",
        "version",
        "related_refs",
        "transition_plan_sha256",
        "approval_reference",
        "created_at",
        "automatic_deletion_performed",
        "content_sha256_verified_by_registry",
        "authentication",
    } or result.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise _fail("human_artifact_transition_receipt_invalid")
    if type(result.get("receipt_id")) is not str or RECEIPT_ID_RE.fullmatch(
        result["receipt_id"]
    ) is None:
        raise _fail("human_artifact_transition_receipt_invalid")
    if type(result.get("artifact_id")) is not str or ARTIFACT_ID_RE.fullmatch(
        result["artifact_id"]
    ) is None:
        raise _fail("human_artifact_transition_receipt_invalid")
    if type(result.get("root_id")) is not str or not (
        ROOT_ID_RE.fullmatch(result["root_id"])
        or result["root_id"] in {item[0] for item in ARCHIVE_MANAGED_SCOPES}
    ):
        raise _fail("human_artifact_transition_receipt_invalid")
    if result.get("root_kind") not in {"external_registered", "archive_managed"}:
        raise _fail("human_artifact_transition_receipt_invalid")
    if type(result.get("sequence")) is not int or result["sequence"] < 1:
        raise _fail("human_artifact_transition_receipt_invalid")
    previous_receipt_id = result.get("previous_receipt_id")
    if previous_receipt_id is not None and (
        type(previous_receipt_id) is not str
        or RECEIPT_ID_RE.fullmatch(previous_receipt_id) is None
    ):
        raise _fail("human_artifact_transition_receipt_invalid")
    for name in (
        "expected_current_state_sha256",
        "resulting_current_state_sha256",
        "transition_plan_sha256",
    ):
        if type(result.get(name)) is not str or SHA256_RE.fullmatch(result[name]) is None:
            raise _fail("human_artifact_transition_receipt_invalid")
    if result.get("from_state") not in OPEN_STATES | DURABLE_FATE_STATES:
        raise _fail("human_artifact_transition_receipt_invalid")
    if result.get("to_state") not in LIFECYCLE_STATES:
        raise _fail("human_artifact_transition_receipt_invalid")
    if result["to_state"] not in ALLOWED_TRANSITIONS[result["from_state"]]:
        raise _fail("human_artifact_transition_receipt_invalid")
    result["observation"] = _validate_observation(
        result.get("observation"), artifact_id=result["artifact_id"]
    )
    result["version"] = _validate_version(result.get("version"))
    expected_version_id = _artifact_version_id(
        result["artifact_id"],
        result["version"]["content_sha256"],
        result["version"]["size_bytes"],
    )
    if not hmac.compare_digest(
        result["version"]["artifact_version_id"],
        expected_version_id,
    ):
        raise _fail("human_artifact_transition_receipt_invalid")
    result["related_refs"] = _validate_related_refs(result.get("related_refs"))
    _require_target_related_ref(
        result["to_state"],
        result["related_refs"],
        code="human_artifact_transition_receipt_invalid",
    )
    result["approval_reference"] = _validate_exact_approval_reference(
        result.get("approval_reference")
    )
    if (
        type(result.get("created_at")) is not str
        or result.get("automatic_deletion_performed") is not False
        or result.get("content_sha256_verified_by_registry") is not False
    ):
        raise _fail("human_artifact_transition_receipt_invalid")
    state = _state_document(
        artifact_id=result["artifact_id"],
        observation_sha256=result["observation"]["observation_sha256"],
        lifecycle_state=result["to_state"],
        artifact_version_id=result["version"]["artifact_version_id"],
        content_sha256=result["version"]["content_sha256"],
        size_bytes=result["version"]["size_bytes"],
        last_receipt_id=result["receipt_id"],
    )
    if not hmac.compare_digest(
        result["resulting_current_state_sha256"], _state_sha256(state)
    ):
        raise _fail("human_artifact_transition_receipt_invalid")
    plan_document = {
        "operation": "transition_artifact",
        "artifact_id": result["artifact_id"],
        "root_id": result["root_id"],
        "root_kind": result["root_kind"],
        "expected_current_state_sha256": result[
            "expected_current_state_sha256"
        ],
        "from_state": result["from_state"],
        "to_state": result["to_state"],
        "observation_sha256": result["observation"][
            "observation_sha256"
        ],
        "version": result["version"],
        "related_refs": result["related_refs"],
        "automatic_deletion_performed": False,
    }
    if not hmac.compare_digest(
        result["transition_plan_sha256"],
        _plan_sha256(plan_document),
    ):
        raise _fail("human_artifact_transition_receipt_invalid")
    _validate_authentication(result, key)
    return result


def _load_receipt_chains(
    context: _ArchiveContext,
    authority: tuple[bytes, dict[str, Any]] | None,
) -> dict[str, _ReceiptChain]:
    directory = _registry_subdirectory(context, RECEIPTS_DIRECTORY, create=False)
    if directory is None:
        return {}
    if authority is None:
        raise _fail("human_artifact_registry_authority_invalid")
    key = authority[0]
    try:
        artifact_entries = list(os.scandir(directory))
    except OSError:
        raise _fail("human_artifact_registry_path_unsafe") from None
    chains: dict[str, _ReceiptChain] = {}
    for artifact_entry in sorted(artifact_entries, key=lambda item: item.name):
        artifact_id = artifact_entry.name
        try:
            info = artifact_entry.stat(follow_symlinks=False)
        except OSError:
            raise _fail("human_artifact_transition_receipt_invalid") from None
        if (
            ARTIFACT_ID_RE.fullmatch(artifact_id) is None
            or _is_reparse(info)
            or not stat.S_ISDIR(info.st_mode)
        ):
            raise _fail("human_artifact_transition_receipt_invalid")
        try:
            receipt_entries = list(os.scandir(artifact_entry.path))
        except OSError:
            raise _fail("human_artifact_transition_receipt_invalid") from None
        if len(receipt_entries) > MAX_RECEIPTS_PER_ARTIFACT:
            raise _fail("human_artifact_transition_receipt_invalid")
        receipts: list[dict[str, Any]] = []
        for receipt_entry in receipt_entries:
            if RECEIPT_FILENAME_RE.fullmatch(receipt_entry.name) is None:
                raise _fail("human_artifact_transition_receipt_invalid")
            try:
                receipt_info = receipt_entry.stat(follow_symlinks=False)
            except OSError:
                raise _fail("human_artifact_transition_receipt_invalid") from None
            if _is_reparse(receipt_info) or not stat.S_ISREG(receipt_info.st_mode):
                raise _fail("human_artifact_transition_receipt_invalid")
            receipt = _validate_receipt_document(
                _read_json_document(
                    Path(receipt_entry.path),
                    code="human_artifact_transition_receipt_invalid",
                ),
                key,
            )
            if receipt["artifact_id"] != artifact_id or not hmac.compare_digest(
                receipt_entry.name,
                receipt["expected_current_state_sha256"].removeprefix("sha256:")
                + ".json",
            ):
                raise _fail("human_artifact_transition_receipt_invalid")
            receipts.append(receipt)
        receipts.sort(key=lambda item: item["sequence"])
        previous: dict[str, Any] | None = None
        for index, receipt in enumerate(receipts, start=1):
            if receipt["sequence"] != index:
                raise _fail("human_artifact_transition_receipt_invalid")
            expected_previous = previous["receipt_id"] if previous else None
            if receipt["previous_receipt_id"] != expected_previous:
                raise _fail("human_artifact_transition_receipt_invalid")
            if previous is None:
                expected_from_state = "unclassified"
                expected_state = _state_sha256(
                    _state_document(
                        artifact_id=artifact_id,
                        observation_sha256=receipt["observation"][
                            "observation_sha256"
                        ],
                        lifecycle_state="unclassified",
                        artifact_version_id=None,
                        content_sha256=None,
                        size_bytes=receipt["observation"]["size_bytes"],
                        last_receipt_id=None,
                    )
                )
            else:
                if hmac.compare_digest(
                    receipt["observation"]["observation_sha256"],
                    previous["observation"]["observation_sha256"],
                ):
                    expected_state = previous["resulting_current_state_sha256"]
                    expected_from_state = previous["to_state"]
                else:
                    expected_from_state = "unclassified"
                    expected_state = _state_sha256(
                        _state_document(
                            artifact_id=artifact_id,
                            observation_sha256=receipt["observation"][
                                "observation_sha256"
                            ],
                            lifecycle_state="unclassified",
                            artifact_version_id=None,
                            content_sha256=None,
                            size_bytes=receipt["observation"]["size_bytes"],
                            last_receipt_id=previous["receipt_id"],
                        )
                    )
            if receipt["from_state"] != expected_from_state or not hmac.compare_digest(
                receipt["expected_current_state_sha256"],
                expected_state,
            ):
                raise _fail("human_artifact_transition_receipt_invalid")
            if previous is not None:
                if receipt["version"]["previous_artifact_version_id"] != previous[
                    "version"
                ]["artifact_version_id"]:
                    raise _fail("human_artifact_transition_receipt_invalid")
                same_version = bool(
                    hmac.compare_digest(
                        receipt["version"]["artifact_version_id"],
                        previous["version"]["artifact_version_id"],
                    )
                    and hmac.compare_digest(
                        receipt["version"]["content_sha256"],
                        previous["version"]["content_sha256"],
                    )
                    and receipt["version"]["size_bytes"]
                    == previous["version"]["size_bytes"]
                )
                if (receipt["version"]["relationship"] == "same_version") != same_version:
                    raise _fail("human_artifact_transition_receipt_invalid")
            previous = receipt
        chains[artifact_id] = _ReceiptChain(tuple(receipts))
    return chains


def _scope_path(parent: Path, relative: str) -> tuple[Path, bool]:
    current = parent
    for part in PurePosixPath(relative).parts:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            return current, False
        except OSError:
            raise _fail("human_artifact_scan_incomplete") from None
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise _fail("human_artifact_scan_incomplete")
    return current, True


def _scan_scope(
    context: _ArchiveContext,
    *,
    root_id: str,
    root_kind: str,
    parent: Path,
    relative_root: str,
    max_entries: int,
    scan_scope_label: str | None = None,
) -> tuple[dict[str, Any], list[_ObservedArtifact]]:
    summary: dict[str, Any] = {
        "root_id": root_id,
        "root_kind": root_kind,
        "scan_scope": (
            scan_scope_label
            if scan_scope_label is not None
            else root_id
        ),
        "present": False,
        "coverage_complete": True,
        "entries_seen": 0,
        "file_count": 0,
        "directory_count": 0,
        "link_or_reparse_count": 0,
        "special_file_count": 0,
        "unreadable_count": 0,
        "changed_during_scan_count": 0,
        "truncated": False,
        "reason_codes": [],
    }
    try:
        scope, present = _scope_path(parent, relative_root)
    except HumanArtifactRegistryError:
        summary.update(
            {
                "coverage_complete": False,
                "reason_codes": ["scan_scope_unsafe"],
            }
        )
        return summary, []
    if not present:
        return summary, []
    summary["present"] = True
    try:
        root_info = os.lstat(scope)
    except OSError:
        summary.update(
            {
                "coverage_complete": False,
                "unreadable_count": 1,
                "reason_codes": ["scan_scope_unreadable"],
            }
        )
        return summary, []
    root_identity = _directory_snapshot(root_info)
    pending: list[tuple[Path, dict[str, int]]] = [(scope, root_identity)]
    observed: list[_ObservedArtifact] = []
    reasons: list[str] = []
    while pending and summary["entries_seen"] < max_entries:
        directory, expected_identity = pending.pop()
        try:
            before = os.lstat(directory)
            before_snapshot = _directory_snapshot(before)
            if (
                _is_reparse(before)
                or not stat.S_ISDIR(before.st_mode)
                or not _same_directory_snapshot(
                    expected_identity,
                    before_snapshot,
                )
            ):
                summary["changed_during_scan_count"] += 1
                reasons.append("directory_identity_changed")
                continue
            iterator = os.scandir(directory)
        except OSError:
            summary["unreadable_count"] += 1
            reasons.append("directory_unreadable")
            continue
        with iterator:
            for entry in iterator:
                if summary["entries_seen"] >= max_entries:
                    summary["truncated"] = True
                    reasons.append("entry_limit_reached")
                    break
                summary["entries_seen"] += 1
                try:
                    # Windows DirEntry.stat() may report zero device/inode even
                    # when lstat() exposes the stable file identity. Use the
                    # named non-following observation consistently here and at
                    # the final transition check.
                    info = os.lstat(entry.path)
                except OSError:
                    summary["unreadable_count"] += 1
                    reasons.append("entry_unreadable")
                    continue
                if _is_reparse(info):
                    summary["link_or_reparse_count"] += 1
                    reasons.append("link_or_reparse_skipped")
                    continue
                if stat.S_ISDIR(info.st_mode):
                    summary["directory_count"] += 1
                    pending.append(
                        (Path(entry.path), _directory_snapshot(info))
                    )
                    continue
                if not stat.S_ISREG(info.st_mode):
                    summary["special_file_count"] += 1
                    reasons.append("special_file_skipped")
                    continue
                summary["file_count"] += 1
                relative = Path(entry.path).relative_to(scope).as_posix()
                artifact_id = _artifact_id(
                    context,
                    root_id=root_id,
                    relative_path=relative,
                )
                observed.append(
                    _ObservedArtifact(
                        artifact_id=artifact_id,
                        root_id=root_id,
                        root_kind=root_kind,
                        path=Path(entry.path),
                        observation=_observation(artifact_id, info),
                    )
                )
        try:
            after = os.lstat(directory)
        except OSError:
            summary["changed_during_scan_count"] += 1
            reasons.append("directory_identity_changed")
            continue
        if _is_reparse(after) or not _same_directory_snapshot(
            before_snapshot,
            _directory_snapshot(after),
        ):
            summary["changed_during_scan_count"] += 1
            reasons.append("directory_identity_changed")
    if pending:
        summary["truncated"] = True
        reasons.append("entry_limit_reached")
    summary["reason_codes"] = list(dict.fromkeys(reasons))
    summary["coverage_complete"] = not any(
        (
            summary["truncated"],
            summary["link_or_reparse_count"],
            summary["special_file_count"],
            summary["unreadable_count"],
            summary["changed_during_scan_count"],
        )
    )
    return summary, observed


def _current_artifact_state(
    observed: _ObservedArtifact,
    chain: _ReceiptChain,
) -> _ArtifactState:
    latest = chain.latest
    matching = bool(
        latest is not None
        and hmac.compare_digest(
            latest["observation"]["observation_sha256"],
            observed.observation["observation_sha256"],
        )
    )
    if matching:
        lifecycle_state = latest["to_state"]
        artifact_version_id = latest["version"]["artifact_version_id"]
        content_sha256 = latest["version"]["content_sha256"]
        relationship = latest["version"]["relationship"]
    else:
        lifecycle_state = "unclassified"
        artifact_version_id = None
        content_sha256 = None
        relationship = "new" if latest is None else "changed_since_last_transition"
    current_state = _state_document(
        artifact_id=observed.artifact_id,
        observation_sha256=observed.observation["observation_sha256"],
        lifecycle_state=lifecycle_state,
        artifact_version_id=artifact_version_id,
        content_sha256=content_sha256,
        size_bytes=observed.observation["size_bytes"],
        last_receipt_id=latest["receipt_id"] if latest else None,
    )
    return _ArtifactState(
        observed=observed,
        chain=chain,
        lifecycle_state=lifecycle_state,
        current_state=current_state,
        current_state_sha256=_state_sha256(current_state),
        artifact_version_id=artifact_version_id,
        content_sha256=content_sha256,
        version_relationship=relationship,
    )


def _normalize_scan_limit(value: int) -> int:
    if type(value) is not int or not 1 <= value <= MAX_ENTRIES_PER_ROOT:
        raise _fail("human_artifact_scan_incomplete")
    return value


def _scan_internal(
    archive_root: Path | str,
    *,
    max_entries_per_root: int,
) -> _ScanResult:
    context = _validated_archive(archive_root)
    limit = _normalize_scan_limit(max_entries_per_root)
    authority = _load_authority(context, create=False)
    roots = _load_root_documents(context, authority)
    chains = _load_receipt_chains(context, authority)
    summaries: list[dict[str, Any]] = []
    artifacts: list[_ObservedArtifact] = []
    blockers: list[str] = []

    for root_id, relative_root in ARCHIVE_MANAGED_SCOPES:
        summary, observed = _scan_scope(
            context,
            root_id=root_id,
            root_kind="archive_managed",
            parent=context.root,
            relative_root=relative_root,
            max_entries=limit,
        )
        summaries.append(summary)
        artifacts.extend(observed)
        if not summary["coverage_complete"]:
            blockers.append("archive_managed_scope_incomplete")

    for registered in roots:
        project_root, reason = _validate_registered_root(registered)
        if reason is not None:
            summaries.append(
                {
                    "root_id": registered["root_id"],
                    "root_kind": "external_registered",
                    "scan_scope": _external_scan_scope_label(
                        registered["root_kind"]
                    ),
                    "present": False,
                    "coverage_complete": False,
                    "entries_seen": 0,
                    "file_count": 0,
                    "directory_count": 0,
                    "link_or_reparse_count": 0,
                    "special_file_count": 0,
                    "unreadable_count": 0,
                    "changed_during_scan_count": 0,
                    "truncated": False,
                    "reason_codes": [reason],
                }
            )
            blockers.append(reason)
            continue
        summary, observed = _scan_scope(
            context,
            root_id=registered["root_id"],
            root_kind="external_registered",
            parent=project_root,
            relative_root=registered["scan_relative_root"],
            max_entries=limit,
            scan_scope_label=_external_scan_scope_label(
                registered["root_kind"]
            ),
        )
        summaries.append(summary)
        artifacts.extend(observed)
        if not summary["coverage_complete"]:
            blockers.append("registered_root_scope_incomplete")

    states: dict[str, _ArtifactState] = {}
    for observed in artifacts:
        if observed.artifact_id in states:
            raise _fail("human_artifact_registry_document_invalid")
        states[observed.artifact_id] = _current_artifact_state(
            observed,
            chains.get(observed.artifact_id, _ReceiptChain(())),
        )

    items: list[dict[str, Any]] = []
    state_counts: dict[str, int] = {}
    unresolved_count = 0
    for artifact_id in sorted(states):
        state = states[artifact_id]
        durable = state.lifecycle_state in DURABLE_FATE_STATES
        if not durable:
            unresolved_count += 1
        state_counts[state.lifecycle_state] = state_counts.get(state.lifecycle_state, 0) + 1
        items.append(
            {
                "artifact_id": artifact_id,
                "root_id": state.observed.root_id,
                "root_kind": state.observed.root_kind,
                "present": True,
                "lifecycle_state": state.lifecycle_state,
                "current_state_sha256": state.current_state_sha256,
                "observation_sha256": state.observed.observation[
                    "observation_sha256"
                ],
                "size_bytes": state.observed.observation["size_bytes"],
                "artifact_version_id": state.artifact_version_id,
                "content_sha256": state.content_sha256,
                "version_relationship": state.version_relationship,
                "durable_fate_recorded": durable,
            }
        )

    missing_artifact_count = 0
    missing_unresolved_count = 0
    for artifact_id, chain in sorted(chains.items()):
        if artifact_id in states or chain.latest is None:
            continue
        missing_artifact_count += 1
        latest = chain.latest
        resolved = latest["to_state"] in {
            "superseded",
            "preserved_as_objet",
            "distilled_to_zet",
            "discarded_with_receipt",
        }
        if not resolved:
            missing_unresolved_count += 1
            unresolved_count += 1
        state_counts["missing"] = state_counts.get("missing", 0) + 1
        items.append(
            {
                "artifact_id": artifact_id,
                "root_id": latest["root_id"],
                "root_kind": latest["root_kind"],
                "present": False,
                "lifecycle_state": latest["to_state"],
                "current_state_sha256": latest[
                    "resulting_current_state_sha256"
                ],
                "observation_sha256": None,
                "size_bytes": latest["version"]["size_bytes"],
                "artifact_version_id": latest["version"][
                    "artifact_version_id"
                ],
                "content_sha256": latest["version"]["content_sha256"],
                "version_relationship": "artifact_not_currently_present",
                "durable_fate_recorded": resolved,
            }
        )

    coverage_complete = not blockers and all(
        summary["coverage_complete"] for summary in summaries
    )
    closeout_complete = bool(coverage_complete and unresolved_count == 0)
    public = {
        "ok": coverage_complete,
        "state": "complete" if closeout_complete else "lifecycle_open",
        "lifecycle_action": "human_artifact_registry_scan",
        "registry_schema_version": REGISTRY_SCHEMA_VERSION,
        "registry_writer_role": "actual_local_registry_writer",
        "human_artifact_store_adapter_role": "read_only_future_contract",
        "scan_mode": "bounded_metadata_only",
        "max_entries_per_root": limit,
        "registered_root_count": len(roots),
        "root_summaries": sorted(summaries, key=lambda item: item["root_id"]),
        "artifact_count": len(states),
        "missing_artifact_count": missing_artifact_count,
        "missing_unresolved_count": missing_unresolved_count,
        "new_unclassified_count": state_counts.get("unclassified", 0),
        "unresolved_artifact_count": unresolved_count,
        "state_counts": state_counts,
        "items": sorted(items, key=lambda item: item["artifact_id"]),
        "coverage_complete": coverage_complete,
        "closeout_complete": closeout_complete,
        "blocker_codes": list(dict.fromkeys(blockers)),
        "next_safe_actions": (
            []
            if closeout_complete
            else [
                (
                    "Obtain exact human review and append a lifecycle "
                    "transition receipt for every open artifact version."
                ),
                (
                    "Do not delete registered-root or archive-scratch "
                    "artifacts automatically."
                ),
                (
                    "Do not mark closeout complete until scan coverage is "
                    "complete and every artifact has a durable fate."
                ),
            ]
        ),
        "automatic_deletion_performed": False,
        "privacy_guards": {
            "absolute_paths_echoed": False,
            "file_names_echoed": False,
            "artifact_bodies_opened": False,
            "artifact_bodies_read": False,
            "content_hashes_calculated_by_scan": False,
            "provider_called": False,
        },
    }
    return _ScanResult(public=public, states=states, chains=chains, authority=authority)


def scan_human_artifacts(
    archive_root: Path | str,
    *,
    max_entries_per_root: int = DEFAULT_MAX_ENTRIES_PER_ROOT,
) -> dict[str, Any]:
    """Scan registered and archive-managed scratch without reading bodies."""

    return _scan_internal(
        archive_root,
        max_entries_per_root=max_entries_per_root,
    ).public


def _transition_plan_internal(
    archive_root: Path | str,
    artifact_id: str,
    *,
    target_state: str,
    content_sha256: str,
    size_bytes: int,
    related_refs: Sequence[Mapping[str, Any]] | None,
    max_entries_per_root: int,
) -> tuple[dict[str, Any], _ArtifactState, dict[str, Any]]:
    if type(artifact_id) is not str or ARTIFACT_ID_RE.fullmatch(artifact_id) is None:
        raise _fail("human_artifact_artifact_id_invalid")
    if target_state not in LIFECYCLE_STATES:
        raise _fail("human_artifact_transition_state_invalid")
    _validate_content_binding(content_sha256, size_bytes)
    refs = _validate_related_refs(related_refs)
    _require_target_related_ref(
        target_state,
        refs,
        code="human_artifact_related_ref_invalid",
    )
    scan = _scan_internal(
        archive_root,
        max_entries_per_root=max_entries_per_root,
    )
    if not scan.public["coverage_complete"]:
        raise _fail("human_artifact_scan_incomplete")
    state = scan.states.get(artifact_id)
    if state is None:
        raise _fail("human_artifact_artifact_not_found")
    if target_state not in ALLOWED_TRANSITIONS[state.lifecycle_state]:
        raise _fail("human_artifact_transition_not_allowed")
    if size_bytes != state.observed.observation["size_bytes"]:
        raise _fail("human_artifact_content_binding_invalid")
    previous = state.chain.latest
    if previous is None:
        relationship = "initial"
        previous_version_id = None
    else:
        previous_version_id = previous["version"]["artifact_version_id"]
        relationship = (
            "same_version"
            if hmac.compare_digest(
                previous["version"]["content_sha256"], content_sha256
            )
            and previous["version"]["size_bytes"] == size_bytes
            else "supersedes"
        )
    version = {
        "artifact_version_id": _artifact_version_id(
            artifact_id,
            content_sha256,
            size_bytes,
        ),
        "content_sha256": content_sha256,
        "size_bytes": size_bytes,
        "relationship": relationship,
        "previous_artifact_version_id": previous_version_id,
    }
    plan_document = {
        "operation": "transition_artifact",
        "artifact_id": artifact_id,
        "root_id": state.observed.root_id,
        "root_kind": state.observed.root_kind,
        "expected_current_state_sha256": state.current_state_sha256,
        "from_state": state.lifecycle_state,
        "to_state": target_state,
        "observation_sha256": state.observed.observation["observation_sha256"],
        "version": version,
        "related_refs": refs,
        "automatic_deletion_performed": False,
    }
    plan_sha256 = _plan_sha256(plan_document)
    public = {
        "ok": True,
        "state": "ready_for_exact_human_approval",
        "lifecycle_action": "human_artifact_transition_plan",
        "artifact_id": artifact_id,
        "root_id": state.observed.root_id,
        "root_kind": state.observed.root_kind,
        "from_state": state.lifecycle_state,
        "to_state": target_state,
        "expected_current_state_sha256": state.current_state_sha256,
        "plan_sha256": plan_sha256,
        "version": version,
        "related_refs": refs,
        "content_sha256_verified_by_registry": False,
        "requires_exact_human_approval_claim": True,
        "automatic_deletion_performed": False,
        "privacy_guards": {
            "absolute_paths_echoed": False,
            "file_names_echoed": False,
            "artifact_bodies_opened": False,
            "artifact_bodies_read": False,
            "provider_called": False,
        },
    }
    return public, state, plan_document


def plan_artifact_transition(
    archive_root: Path | str,
    artifact_id: str,
    *,
    target_state: str,
    content_sha256: str,
    size_bytes: int,
    related_refs: Sequence[Mapping[str, Any]] | None = None,
    max_entries_per_root: int = DEFAULT_MAX_ENTRIES_PER_ROOT,
) -> dict[str, Any]:
    """Plan one append-only state transition without writing or reading content."""

    public, _state, _private = _transition_plan_internal(
        archive_root,
        artifact_id,
        target_state=target_state,
        content_sha256=content_sha256,
        size_bytes=size_bytes,
        related_refs=related_refs,
        max_entries_per_root=max_entries_per_root,
    )
    return public


def artifact_transition_approval_context(
    archive_root: Path | str,
    artifact_id: str,
    *,
    target_state: str,
    content_sha256: str,
    size_bytes: int,
    reviewer_claim: str,
    related_refs: Sequence[Mapping[str, Any]] | None = None,
    max_entries_per_root: int = DEFAULT_MAX_ENTRIES_PER_ROOT,
) -> ExactHumanApprovalContext:
    """Build the only exact-human context accepted by the transition writer."""

    context = _validated_archive(archive_root)
    plan, _state, private = _transition_plan_internal(
        archive_root,
        artifact_id,
        target_state=target_state,
        content_sha256=content_sha256,
        size_bytes=size_bytes,
        related_refs=related_refs,
        max_entries_per_root=max_entries_per_root,
    )
    target_binding = _approval_target_binding(
        {
            "operation": "transition_artifact",
            "plan_sha256": plan["plan_sha256"],
            "artifact_id": artifact_id,
            "expected_current_state_sha256": private[
                "expected_current_state_sha256"
            ],
            "to_state": target_state,
            "version": private["version"],
            "related_refs": private["related_refs"],
        }
    )
    return ExactHumanApprovalContext(
        operation=ExactHumanApprovalOperation.human_artifact_lifecycle,
        archive_identity_sha256=exact_human_approval_archive_identity_sha256(
            context.archive_id
        ),
        plan_sha256=plan["plan_sha256"],
        target_binding_sha256=target_binding,
        reviewer_claim=reviewer_claim,
        review_binding_codes=(
            "artifact_content_sha256",
            "artifact_observation",
            "current_state_digest",
            "lifecycle_target",
            "registry_plan",
        ),
        warning_codes=(
            "content_sha256_caller_supplied_not_registry_verified",
        ),
    )


def _artifact_observation_still_matches(state: _ArtifactState) -> bool:
    try:
        info = os.lstat(state.observed.path)
    except OSError:
        return False
    if _is_reparse(info) or not stat.S_ISREG(info.st_mode):
        return False
    return hmac.compare_digest(
        _observation(state.observed.artifact_id, info)["observation_sha256"],
        state.observed.observation["observation_sha256"],
    )


def write_artifact_transition(
    archive_root: Path | str,
    artifact_id: str,
    *,
    target_state: str,
    content_sha256: str,
    size_bytes: int,
    expected_plan_sha256: str,
    expected_current_state_sha256: str,
    approval_claim: _ClaimedExactHumanApproval,
    reviewer_claim: str,
    related_refs: Sequence[Mapping[str, Any]] | None = None,
    max_entries_per_root: int = DEFAULT_MAX_ENTRIES_PER_ROOT,
    clock: Callable[[], datetime] = _default_clock,
    random_hex: Callable[[int], str] = secrets.token_hex,
    random_bytes: Callable[[int], bytes] = secrets.token_bytes,
) -> dict[str, Any]:
    """Append one exact-state receipt; never modify or delete artifact bytes."""

    if type(approval_claim) is not _ClaimedExactHumanApproval:
        raise _fail("human_artifact_exact_approval_reference_invalid")
    plan, state, private = _transition_plan_internal(
        archive_root,
        artifact_id,
        target_state=target_state,
        content_sha256=content_sha256,
        size_bytes=size_bytes,
        related_refs=related_refs,
        max_entries_per_root=max_entries_per_root,
    )
    if (
        type(expected_plan_sha256) is not str
        or not hmac.compare_digest(expected_plan_sha256, plan["plan_sha256"])
    ):
        raise _fail("human_artifact_expected_plan_mismatch")
    if (
        type(expected_current_state_sha256) is not str
        or not hmac.compare_digest(
            expected_current_state_sha256,
            state.current_state_sha256,
        )
    ):
        raise _fail("human_artifact_current_state_mismatch")
    exact_context = artifact_transition_approval_context(
        archive_root,
        artifact_id,
        target_state=target_state,
        content_sha256=content_sha256,
        size_bytes=size_bytes,
        reviewer_claim=reviewer_claim,
        related_refs=related_refs,
        max_entries_per_root=max_entries_per_root,
    )
    approval = _validate_exact_approval_reference(
        approval_claim.assert_ready_for_context(exact_context)
    )

    context = _validated_archive(archive_root)
    _require_private_registry_ignored(context)
    authority = _load_authority(
        context,
        create=True,
        clock=clock,
        random_bytes=random_bytes,
    )
    assert authority is not None
    key = authority[0]
    try:
        fresh_plan, fresh_state, fresh_private = _transition_plan_internal(
            archive_root,
            artifact_id,
            target_state=target_state,
            content_sha256=content_sha256,
            size_bytes=size_bytes,
            related_refs=related_refs,
            max_entries_per_root=max_entries_per_root,
        )
        if not (
            hmac.compare_digest(fresh_plan["plan_sha256"], expected_plan_sha256)
            and hmac.compare_digest(
                fresh_state.current_state_sha256,
                expected_current_state_sha256,
            )
        ):
            raise _fail("human_artifact_current_state_mismatch")
        if not _artifact_observation_still_matches(fresh_state):
            raise _fail("human_artifact_artifact_changed_during_transition")

        created_at = _now(clock)
        receipt_id = _validated_random_hex(random_hex, prefix="har_receipt_")
        latest = fresh_state.chain.latest
        resulting_state = _state_document(
            artifact_id=artifact_id,
            observation_sha256=fresh_state.observed.observation[
                "observation_sha256"
            ],
            lifecycle_state=target_state,
            artifact_version_id=fresh_private["version"]["artifact_version_id"],
            content_sha256=fresh_private["version"]["content_sha256"],
            size_bytes=fresh_private["version"]["size_bytes"],
            last_receipt_id=receipt_id,
        )
        receipt = _authenticated(
            {
                "schema_version": RECEIPT_SCHEMA_VERSION,
                "receipt_id": receipt_id,
                "artifact_id": artifact_id,
                "root_id": fresh_state.observed.root_id,
                "root_kind": fresh_state.observed.root_kind,
                "sequence": len(fresh_state.chain.receipts) + 1,
                "previous_receipt_id": latest["receipt_id"] if latest else None,
                "expected_current_state_sha256": expected_current_state_sha256,
                "resulting_current_state_sha256": _state_sha256(resulting_state),
                "from_state": fresh_state.lifecycle_state,
                "to_state": target_state,
                "observation": fresh_state.observed.observation,
                "version": fresh_private["version"],
                "related_refs": fresh_private["related_refs"],
                "transition_plan_sha256": fresh_plan["plan_sha256"],
                "approval_reference": approval,
                "created_at": created_at,
                "automatic_deletion_performed": False,
                "content_sha256_verified_by_registry": False,
            },
            key,
        )
        _validate_receipt_document(receipt, key)
        _spend_approval(
            context,
            key,
            approval,
            operation="transition_artifact",
            target_id=artifact_id,
            used_at=created_at,
        )
        receipts_root = _registry_subdirectory(
            context,
            RECEIPTS_DIRECTORY,
            create=True,
        )
        assert receipts_root is not None
        artifact_receipts = receipts_root / artifact_id
        _safe_directory(artifact_receipts, create=True)
        receipt_path = artifact_receipts / (
            expected_current_state_sha256.removeprefix("sha256:") + ".json"
        )
        _exclusive_create(
            receipt_path,
            receipt,
            pending_directory=(
                context.root / REGISTRY_RELATIVE_ROOT / PENDING_DIRECTORY
            ),
            code="human_artifact_transition_conflict",
        )
        if not _artifact_observation_still_matches(fresh_state):
            raise _fail("human_artifact_artifact_changed_during_transition")
    except BaseException:
        # The shared exact-human workflow owns the single terminal finalize.
        raise
    return {
        "ok": True,
        "state": "transition_recorded",
        "lifecycle_action": "human_artifact_transition_write",
        "artifact_id": artifact_id,
        "root_id": fresh_state.observed.root_id,
        "root_kind": fresh_state.observed.root_kind,
        "from_state": fresh_state.lifecycle_state,
        "to_state": target_state,
        "receipt_id": receipt_id,
        "expected_current_state_sha256": expected_current_state_sha256,
        "resulting_current_state_sha256": receipt[
            "resulting_current_state_sha256"
        ],
        "version": fresh_private["version"],
        "related_refs": fresh_private["related_refs"],
        "content_sha256_verified_by_registry": False,
        "exact_human_approval_reference_shape_validated": True,
        "exact_human_approval_claim_reauthenticated": True,
        "exact_human_approval_claim_finalized": False,
        "exact_human_approval_claim_finalization_owner": "approval_workflow",
        "automatic_deletion_performed": False,
        "files_written": [
            "private_registry_approval_use",
            "append_only_transition_receipt",
        ],
        "privacy_guards": {
            "absolute_paths_echoed": False,
            "file_names_echoed": False,
            "artifact_bodies_opened": False,
            "artifact_bodies_read": False,
            "provider_called": False,
        },
    }


__all__ = [
    "ALLOWED_TRANSITIONS",
    "APPROVAL_USE_SCHEMA_VERSION",
    "ARCHIVE_MANAGED_SCOPES",
    "AUTHORITY_SCHEMA_VERSION",
    "DEFAULT_MAX_ENTRIES_PER_ROOT",
    "DURABLE_FATE_STATES",
    "EXTERNAL_ROOT_KINDS",
    "EXACT_HUMAN_APPROVAL_REFERENCE_SCHEMA",
    "HumanArtifactRegistryError",
    "LIFECYCLE_STATES",
    "MAX_ENTRIES_PER_ROOT",
    "RECEIPT_SCHEMA_VERSION",
    "REGISTRY_RELATIVE_ROOT",
    "REGISTRY_SCHEMA_VERSION",
    "ROOT_SCHEMA_VERSION",
    "artifact_transition_approval_context",
    "plan_artifact_transition",
    "plan_project_root_registration",
    "project_root_registration_approval_context",
    "register_project_root",
    "scan_human_artifacts",
    "write_artifact_transition",
]
