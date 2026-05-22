"""Path helpers for portable archive-internal paths.

Archive files may be opened from Windows, macOS, or Linux, but paths stored in
JSON/MCP output and archive metadata should be stable POSIX-style relative paths.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath


WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
UNC_PATH_RE = re.compile(r"^[\\/]{2}[^\\/]+[\\/][^\\/]+")
PROVIDER_URL_RE = re.compile(r"\b(?:s3|b2|r2|gs)://", re.IGNORECASE)
LOCAL_ABSOLUTE_REFERENCE_RE = re.compile(
    r"(^|[\s'\"(<])(?:[A-Za-z]:[\\/]|\\\\[^\\/\s]+[\\/][^\\/\s]+|/(?:Users|home|root|Volumes|mnt|media|tmp|var|etc|opt|private)/)",
    re.IGNORECASE,
)
FORBIDDEN_LOCATION_RE = re.compile(
    PROVIDER_URL_RE.pattern + "|" + LOCAL_ABSOLUTE_REFERENCE_RE.pattern,
    re.IGNORECASE,
)


class ArchivePathError(ValueError):
    """Raised when an archive-relative path is unsafe or malformed."""


def archive_relative_path(path: Path, archive_root: Path) -> str:
    """Return a stable POSIX-style path relative to an archive root."""

    root = archive_root.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ArchivePathError(f"Path escapes archive root: {path}")
    relative = resolved.relative_to(root)
    if not relative.parts:
        return "."
    return PurePosixPath(*relative.parts).as_posix()


def is_path_within_root(path: Path, archive_root: Path) -> bool:
    """Return true only when a path resolves inside an archive root."""

    try:
        return path.resolve().is_relative_to(archive_root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False


def normalize_archive_relative_path(raw_path: str) -> str:
    """Normalize user/archive input into a safe POSIX-style relative path."""

    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ArchivePathError("Archive-relative path must be a non-empty string.")
    if "\x00" in raw_path:
        raise ArchivePathError("Archive-relative path must not contain NUL bytes.")
    if WINDOWS_ABSOLUTE_RE.match(raw_path) or UNC_PATH_RE.match(raw_path):
        raise ArchivePathError("Archive-relative path must not be absolute.")

    normalized = raw_path.replace("\\", "/").strip()
    if normalized.startswith("/"):
        raise ArchivePathError("Archive-relative path must not be absolute.")
    normalized = normalized.rstrip("/")
    if not normalized:
        raise ArchivePathError("Archive-relative path must not be empty.")

    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ArchivePathError("Archive-relative path must not contain empty, dot, or parent segments.")
    return PurePosixPath(*parts).as_posix()


def resolve_archive_relative_path(archive_root: Path, raw_path: str) -> Path:
    """Resolve a safe archive-relative path against an archive root."""

    normalized = normalize_archive_relative_path(raw_path)
    candidate = archive_root.resolve().joinpath(*PurePosixPath(normalized).parts).resolve()
    if not candidate.is_relative_to(archive_root.resolve()):
        raise ArchivePathError("Archive-relative path escapes archive root.")
    return candidate


def contains_forbidden_location_reference(text: str) -> bool:
    """Return true if text appears to contain provider URLs or local absolute paths."""

    return bool(FORBIDDEN_LOCATION_RE.search(text))
