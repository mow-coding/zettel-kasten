"""Private provider artifacts staged for the existing approved intake chain.

These helpers grant no execution authority. Callers must enter their existing
approved provider workflow before writing. They never mutate canonical objets.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid


class ProviderArtifactError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def safe_path(root: Path, relative: str, *, create_parent: bool = False) -> Path:
    from .source_intake_batch_exact import SourceIntakeBatchExactError, _reject_link_or_reparse_chain

    if not isinstance(relative, str) or "\\" in relative:
        raise ProviderArtifactError("provider_artifact_path_invalid")
    parts = relative.split("/")
    if not parts or any(part in {"", ".", ".."} or ":" in part for part in parts):
        raise ProviderArtifactError("provider_artifact_path_invalid")
    target = root.joinpath(*parts)
    existing = target
    while not os.path.lexists(existing):
        existing = existing.parent
    try:
        _reject_link_or_reparse_chain(existing, code="provider_artifact_path_unsafe")
    except (ValueError, SourceIntakeBatchExactError):
        raise ProviderArtifactError("provider_artifact_path_unsafe") from None
    if create_parent:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            _reject_link_or_reparse_chain(target.parent, code="provider_artifact_path_unsafe")
        except SourceIntakeBatchExactError:
            raise ProviderArtifactError("provider_artifact_path_unsafe") from None
    if target.exists():
        info = target.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ProviderArtifactError("provider_artifact_path_unsafe")
    return target


@contextmanager
def bound_artifact_parent(root: Path, relative: str):
    """Reuse WOM's held-directory contract while an artifact is written."""
    from .archive_services import _activity_group_bound_directory_chain
    root = root.resolve(strict=True)
    target = safe_path(root, relative)
    with _activity_group_bound_directory_chain(root, target.parent, create=True):
        yield root, target


def write_blob(root: Path, raw: bytes, extension: str) -> dict:
    with bound_artifact_parent(root, "workbench/provider-blobs/write.bin") as (bound_root, _):
        return _write_blob_bound(bound_root, raw, extension)


def _write_blob_bound(root: Path, raw: bytes, extension: str) -> dict:
    """Deduplicate exact bytes only; a collision or modified blob fails closed."""
    if extension not in {"eml", "txt", "bin", "json", "html"}:
        raise ProviderArtifactError("provider_artifact_extension_invalid")
    sha = digest(raw)
    relative = f"workbench/provider-blobs/{sha[7:]}.{extension}"
    target = safe_path(root, relative, create_parent=True)
    if target.exists():
        if target.read_bytes() != raw:
            raise ProviderArtifactError("provider_artifact_collision") from None
    else:
        partial = target.with_name(uuid.uuid4().hex + ".partial")
        try:
            descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            from .project_update_transaction import _atomic_move_file_no_replace
            try:
                _atomic_move_file_no_replace(partial, target)
            except FileExistsError:
                if safe_path(root, relative).read_bytes() != raw:
                    raise ProviderArtifactError("provider_artifact_collision") from None
        finally:
            if partial.exists():
                partial.unlink()
    return {"path": relative, "sha256": sha, "size_bytes": len(raw)}


def write_json(root: Path, relative: str, value: object) -> None:
    with bound_artifact_parent(root, relative) as (bound_root, _):
        _write_json_bound(bound_root, relative, value)


def _write_json_bound(root: Path, relative: str, value: object) -> None:
    target = safe_path(root, relative, create_parent=True)
    partial = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
    descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
        safe_path(root, relative)
        os.replace(partial, target)
    finally:
        if partial.exists():
            partial.unlink()


def read_json(root: Path, relative: str) -> dict:
    path = safe_path(root, relative)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ProviderArtifactError("provider_manifest_oversize")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise ProviderArtifactError("provider_manifest_invalid") from None
    if not isinstance(value, dict):
        raise ProviderArtifactError("provider_manifest_invalid")
    return value


def write_intake_requests(root: Path, directory: str, batch_id: str, items: list[dict]):
    """One physical source per intake; retain item aliases for all occurrences.

    Intake has an actual 1000-item bound. Split at that bound without asking
    callers to hand-edit the provider's generated manifest.
    """
    unique, by_path, aliases = [], {}, {}
    for item in items:
        prior = by_path.get(item["local_path"])
        if prior is None:
            by_path[item["local_path"]] = item["item_id"]
            unique.append(item)
        else:
            aliases[item["item_id"]] = prior
    paths = []
    for start in range(0, len(unique), 1000):
        ordinal = start // 1000
        suffix = "" if ordinal == 0 else f"-{ordinal + 1:04d}"
        path = directory + "/source-intake-batch-request" + suffix + ".json"
        write_json(root, path, {"schema": "wom-kit/source-intake-batch-request/v0.1", "batch_id": batch_id + suffix,
            "items": unique[start:start + 1000]})
        paths.append(path)
    return paths, aliases


@contextmanager
def exclusive_run(root: Path, relative: str):
    """OS lock released on process exit; no persistent stale-lock takeover."""
    with bound_artifact_parent(root, relative) as (bound_root, target):
        with _locked_regular_file(bound_root, relative, target):
            yield


@contextmanager
def _locked_regular_file(root, relative, target):
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(target, flags, 0o600), "r+b") as stream:
        safe_path(root, relative)
        opened, current = os.fstat(stream.fileno()), target.lstat()
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)):
            raise ProviderArtifactError("provider_artifact_path_unsafe")
        if target.stat().st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ProviderArtifactError("provider_run_busy") from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
