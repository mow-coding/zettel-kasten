from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
import threading
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterator


PUBLIC_TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".json5",
    ".yml",
    ".yaml",
    ".toml",
    ".py",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".cfg",
    ".conf",
    ".ini",
    ".key",
    ".pem",
    ".properties",
    ".ps1",
    ".sh",
    ".xml",
}
PLACEHOLDER_MARKERS = (
    "example",
    "placeholder",
    "fake",
    "sample",
    "demo",
    "redacted",
    "never put",
    "<",
)
PLACEHOLDER_USER_SEGMENTS = {"example", "placeholder", "sample", "demo", "user", "username"}

WINDOWS_USER_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/]+Users[\\/]+([^\\/\s`\"'<>|]+)[\\/]+[^\s`\"'<>|]+")
POSIX_USER_PATH_RE = re.compile(r"(?<!\w)/(?:Users|home)/([^/\s`\"'<>|]+)/[^\s`\"'<>|]+")
TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PRIV003", re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b")),
    ("PRIV004", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("PRIV005", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("PRIV006", re.compile(r"\b(?:AKIA|ASIA|A3T[A-Z0-9])[A-Z0-9]{16}\b")),
)
AWS_SECRET_ACCESS_KEY_RE = re.compile(
    r"\bAWS_SECRET_ACCESS_KEY\b\s*['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})(?=['\"\s,}\]]|$)",
    re.IGNORECASE,
)
PRIVATE_KEY_HEADER_RE = re.compile(
    r"BEGIN (?:RSA |OPENSSH |DSA |EC )?PRIVATE KEY",
    re.IGNORECASE,
)
SEED_PHRASE_RE = re.compile(
    r"\b(seed phrase|mnemonic|recovery phrase)\s*[:=]\s*([^\n\r]+)",
    re.IGNORECASE,
)
PRIVATE_URL_RE = re.compile(
    r"\bhttp://(?:localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(?::\d+)?(?:/[^\s`\"'<>)]*)?",
    re.IGNORECASE,
)
CREDENTIAL_URL_RE = re.compile(
    r"\bhttps?://[^\s`\"'<>/@:]+(?::[^\s`\"'<>/@]+)?@[^\s`\"'<>/]+(?:/[^\s`\"'<>)]*)?",
    re.IGNORECASE,
)

PROBLEM_TYPES = {
    "PRIV001": "local_windows_user_path",
    "PRIV002": "local_posix_user_path",
    "PRIV003": "github_classic_token",
    "PRIV004": "github_fine_grained_token",
    "PRIV005": "openai_api_key",
    "PRIV006": "aws_access_key",
    "PRIV007": "aws_secret_access_key",
    "PRIV008": "private_key_header",
    "PRIV009": "recovery_phrase",
    "PRIV010": "private_or_local_url",
    "PRIV011": "credential_bearing_url",
    "PRIV012": "non_plain_tracked_entry",
    "PRIV013": "non_plain_untracked_entry",
    "PRIV014": "tracked_entry_changed_during_scan",
    "PRIV015": "untracked_entry_changed_during_scan",
    "PRIV016": "scan_entry_limit_exceeded",
    "PRIV017": "scan_file_size_limit_exceeded",
    "PRIV018": "scan_total_size_limit_exceeded",
    "PRIV019": "index_blob_read_failed",
    "PRIV020": "index_snapshot_drift",
}

REGULAR_GIT_MODES = {"100644", "100755"}
WINDOWS_REPARSE_POINT_ATTRIBUTE = 0x0400
MAX_LISTED_ENTRIES = 20_000
MAX_GIT_LISTING_BYTES = 32 * 1024 * 1024
MAX_SINGLE_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_SCAN_BYTES = 256 * 1024 * 1024
MAX_GIT_INPUT_BYTES = 2 * 1024 * 1024
MAX_BATCH_CHECK_LINE_BYTES = 128
MAX_BATCH_RESPONSE_OVERHEAD_BYTES = 128
GIT_COMMAND_TIMEOUT_SECONDS = 30.0
FULL_OBJECT_ID_RE = re.compile(r"\A[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?\Z")


class PrivacyScanError(RuntimeError):
    """A deliberately content-free scanner failure."""


class PrivacyLimitError(RuntimeError):
    def __init__(self, code: str, path: str = ".") -> None:
        super().__init__(code)
        self.code = code
        self.path = path


@dataclass
class ScanBudget:
    observed_bytes: int = 0

    def reserve(self, size: int, *, path: str) -> None:
        if size < 0 or size > MAX_SINGLE_FILE_BYTES:
            raise PrivacyLimitError("PRIV017", path)
        if self.observed_bytes + size > MAX_TOTAL_SCAN_BYTES:
            raise PrivacyLimitError("PRIV018")
        self.observed_bytes += size


@dataclass(frozen=True)
class GitPathEntry:
    path: str
    tracked: bool
    mode: str | None = None
    object_id: str | None = None
    stage: int | None = None


@dataclass(frozen=True)
class PrivacyProblem:
    file: str
    code: str
    count: int = 1

    @property
    def kind(self) -> str:
        return PROBLEM_TYPES[self.code]

    @property
    def message(self) -> str:
        """Compatibility accessor containing fixed, content-free text only."""

        return self.kind

    def format(self) -> str:
        return f"code={self.code} type={self.kind} count={self.count} path={safe_display_path(self.file)}"


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_bounded_process(
    command: list[str],
    *,
    cwd: Path,
    payload: bytes | None,
    max_stdout: int,
    timeout_seconds: float,
    output_limit_code: str | None = None,
) -> bytes:
    if max_stdout < 0 or timeout_seconds <= 0:
        raise PrivacyScanError("process_limits_invalid")
    if payload is not None and len(payload) > MAX_GIT_INPUT_BYTES:
        raise PrivacyLimitError("PRIV016")

    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.PIPE if payload is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert process.stdout is not None
    output = bytearray()
    output_overflow = threading.Event()
    reader_failed = threading.Event()
    writer_failed = threading.Event()

    def terminate() -> None:
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass

    def read_stdout() -> None:
        try:
            while True:
                chunk = process.stdout.read(64 * 1024)
                if not chunk:
                    return
                remaining = max_stdout - len(output)
                if len(chunk) > remaining:
                    if remaining > 0:
                        output.extend(chunk[:remaining])
                    output_overflow.set()
                    terminate()
                    return
                output.extend(chunk)
        except (OSError, ValueError):
            reader_failed.set()
        finally:
            try:
                process.stdout.close()
            except OSError:
                pass

    def write_stdin() -> None:
        assert process.stdin is not None
        try:
            process.stdin.write(payload or b"")
            process.stdin.flush()
        except (BrokenPipeError, OSError):
            writer_failed.set()
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass

    reader = threading.Thread(target=read_stdout, name="privacy-git-stdout", daemon=True)
    reader.start()
    writer: threading.Thread | None = None
    if payload is not None:
        writer = threading.Thread(target=write_stdin, name="privacy-git-stdin", daemon=True)
        writer.start()

    timed_out = False
    try:
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate()
        try:
            returncode = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            returncode = -1

    if writer is not None:
        writer.join(timeout=5)
    reader.join(timeout=5)
    if reader.is_alive() or (writer is not None and writer.is_alive()):
        terminate()
        try:
            process.stdout.close()
        except OSError:
            pass
        reader.join(timeout=1)
        if writer is not None:
            writer.join(timeout=1)
        raise PrivacyScanError("process_pipe_stalled")
    if output_overflow.is_set():
        if output_limit_code is not None:
            raise PrivacyLimitError(output_limit_code)
        raise PrivacyScanError("process_stdout_limit")
    if timed_out:
        raise PrivacyScanError("process_timeout")
    if returncode != 0 or reader_failed.is_set() or writer_failed.is_set():
        raise PrivacyScanError("process_failed")
    return bytes(output)


def _run_git_bytes(repo_root: Path, args: list[str]) -> bytes:
    return _run_bounded_process(
        ["git", *args],
        cwd=repo_root,
        payload=None,
        max_stdout=MAX_GIT_LISTING_BYTES,
        timeout_seconds=GIT_COMMAND_TIMEOUT_SECONDS,
        output_limit_code="PRIV016",
    )


def _decode_git_path(raw_path: bytes) -> str:
    try:
        return raw_path.decode("utf-8")
    except UnicodeDecodeError:
        raise PrivacyScanError("git_path_encoding_invalid") from None


def list_git_entries(repo_root: Path) -> list[GitPathEntry]:
    tracked_output = _run_git_bytes(repo_root, ["ls-files", "--cached", "--stage", "-z"])
    untracked_output = _run_git_bytes(repo_root, ["ls-files", "--others", "--exclude-standard", "-z"])
    entries: list[GitPathEntry] = []

    for raw_record in tracked_output.split(b"\0"):
        if not raw_record:
            continue
        metadata, separator, raw_path = raw_record.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            raise PrivacyScanError("git_tracked_record_invalid")
        try:
            mode = fields[0].decode("ascii")
            object_id = fields[1].decode("ascii").lower()
            stage = int(fields[2].decode("ascii"))
        except UnicodeDecodeError:
            raise PrivacyScanError("git_tracked_mode_invalid") from None
        except ValueError:
            raise PrivacyScanError("git_tracked_stage_invalid") from None
        if not FULL_OBJECT_ID_RE.fullmatch(object_id) or stage not in {0, 1, 2, 3}:
            raise PrivacyScanError("git_tracked_metadata_invalid")
        path = _decode_git_path(raw_path)
        entries.append(GitPathEntry(path=path, tracked=True, mode=mode, object_id=object_id, stage=stage))

    for raw_path in untracked_output.split(b"\0"):
        if not raw_path:
            continue
        path = _decode_git_path(raw_path)
        entries.append(GitPathEntry(path=path, tracked=False))

    if len(entries) > MAX_LISTED_ENTRIES:
        raise PrivacyLimitError("PRIV016")
    return sorted(entries, key=lambda entry: (entry.path, not entry.tracked, entry.stage or 0))


def run_git_ls_files(repo_root: Path) -> list[str]:
    """Compatibility helper returning the listed relative paths."""

    return [entry.path for entry in list_git_entries(repo_root)]


def tracked_index_snapshot(entries: list[GitPathEntry]) -> tuple[tuple[str, str, str, int], ...]:
    """Bind endpoint-visible index state; a malicious between-check ABA is outside this local gate."""

    snapshot: list[tuple[str, str, str, int]] = []
    for entry in entries:
        if not entry.tracked or entry.mode is None or entry.object_id is None or entry.stage is None:
            continue
        snapshot.append((entry.path, entry.mode, entry.object_id, entry.stage))
    return tuple(sorted(snapshot))


def is_public_text_path(path: str) -> bool:
    return Path(path).suffix.lower() in PUBLIC_TEXT_SUFFIXES


def is_sensitive_untracked_path(path: str) -> bool:
    name = PurePosixPath(path).name.lower()
    return (
        is_public_text_path(path)
        or name == ".env"
        or name.startswith(".env.")
        or name in {"credentials", "credentials.json", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
    )


def public_text_files(paths: list[str]) -> list[str]:
    return sorted(path for path in paths if is_public_text_path(path))


def has_placeholder_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def is_placeholder_user_segment(user_segment: str) -> bool:
    return user_segment.lower() in PLACEHOLDER_USER_SEGMENTS


def is_obvious_synthetic_aws_access_key(value: str) -> bool:
    body = value[4:]
    return body in {"ABCDEFGHIJKLMNOP", "1234567890ABCDEF"} or len(set(body)) == 1


def placeholder_context(text: str, start: int, end: int, radius: int = 40) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def credential_url_has_placeholder_userinfo(value: str) -> bool:
    without_scheme = re.sub(r"^https?://", "", value, flags=re.IGNORECASE)
    userinfo = without_scheme.split("@", 1)[0]
    return has_placeholder_marker(userinfo)


def safe_display_path(path: str) -> str:
    """Return an injection-safe relative path or a fixed redaction marker."""

    if path == ".":
        return "."
    if not path or len(path) > 512 or "\\" in path:
        return "<redacted-path>"
    if not path.isprintable() or any(
        unicodedata.category(character) in {"Cc", "Cf", "Cs"}
        or unicodedata.bidirectional(character) in {"LRE", "RLE", "LRO", "RLO", "PDF", "LRI", "RLI", "FSI", "PDI"}
        for character in path
    ):
        return "<redacted-path>"
    parts = path.split("/")
    if path.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        return "<redacted-path>"

    lowered = path.lower()
    if any(marker in lowered for marker in ("seed phrase", "mnemonic", "recovery phrase", "private key")):
        return "<redacted-path>"
    path_patterns = (
        WINDOWS_USER_PATH_RE,
        POSIX_USER_PATH_RE,
        AWS_SECRET_ACCESS_KEY_RE,
        PRIVATE_KEY_HEADER_RE,
        SEED_PHRASE_RE,
        PRIVATE_URL_RE,
        CREDENTIAL_URL_RE,
        *(pattern for _, pattern in TOKEN_PATTERNS),
    )
    if any(pattern.search(path) for pattern in path_patterns):
        return "<redacted-path>"
    return path


def _add_problem_count(counts: dict[str, int], code: str, amount: int = 1) -> None:
    counts[code] = counts.get(code, 0) + amount


def check_text_for_privacy(*, path: str, text: str) -> list[PrivacyProblem]:
    counts: dict[str, int] = {}

    for pattern, code in (
        (WINDOWS_USER_PATH_RE, "PRIV001"),
        (POSIX_USER_PATH_RE, "PRIV002"),
    ):
        for match in pattern.finditer(text):
            user_segment = match.group(1)
            if is_placeholder_user_segment(user_segment):
                continue
            _add_problem_count(counts, code)

    for code, pattern in TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            if has_placeholder_marker(match.group(0)):
                continue
            if code == "PRIV006" and is_obvious_synthetic_aws_access_key(match.group(0)):
                continue
            _add_problem_count(counts, code)

    for match in AWS_SECRET_ACCESS_KEY_RE.finditer(text):
        if has_placeholder_marker(match.group(1)):
            continue
        _add_problem_count(counts, "PRIV007")

    for match in PRIVATE_KEY_HEADER_RE.finditer(text):
        if has_placeholder_marker(match.group(0)):
            continue
        _add_problem_count(counts, "PRIV008")

    for match in SEED_PHRASE_RE.finditer(text):
        if has_placeholder_marker(match.group(2)):
            continue
        _add_problem_count(counts, "PRIV009")

    for match in PRIVATE_URL_RE.finditer(text):
        context = placeholder_context(text, match.start(), match.end())
        if has_placeholder_marker(context):
            continue
        _add_problem_count(counts, "PRIV010")

    for match in CREDENTIAL_URL_RE.finditer(text):
        if credential_url_has_placeholder_userinfo(match.group(0)):
            continue
        _add_problem_count(counts, "PRIV011")

    return [PrivacyProblem(file=path, code=code, count=count) for code, count in sorted(counts.items())]


def _relative_path_parts(path: str) -> tuple[str, ...] | None:
    if not path or "\\" in path or "\0" in path:
        return None
    pure_path = PurePosixPath(path)
    parts = pure_path.parts
    if pure_path.is_absolute() or not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    return parts


def _is_reparse_point(file_stat: os.stat_result) -> bool:
    return bool(getattr(file_stat, "st_file_attributes", 0) & WINDOWS_REPARSE_POINT_ATTRIBUTE)


def _filesystem_entry_state(repo_root: Path, parts: tuple[str, ...]) -> tuple[str, Path | None]:
    candidate = repo_root
    for index, part in enumerate(parts):
        candidate = candidate / part
        try:
            file_stat = os.lstat(candidate)
        except FileNotFoundError:
            return "missing", None
        except OSError:
            return "non_plain", None
        if stat.S_ISLNK(file_stat.st_mode) or _is_reparse_point(file_stat):
            return "non_plain", None
        is_last = index == len(parts) - 1
        if not is_last and not stat.S_ISDIR(file_stat.st_mode):
            return "non_plain", None
        if is_last and not stat.S_ISREG(file_stat.st_mode):
            return "non_plain", None
    return "plain", candidate


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        stat.S_ISREG(left.st_mode)
        and stat.S_ISREG(right.st_mode)
        and not _is_reparse_point(left)
        and not _is_reparse_point(right)
        and left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
    )


def _open_windows_no_follow(path: Path) -> int:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path),
        0x80000000,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x00200000 | 0x08000000,
        None,
    )
    invalid_handle = wintypes.HANDLE(-1).value
    if handle == invalid_handle:
        raise OSError("safe_open_failed")
    try:
        return msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY | os.O_NOINHERIT)
    except Exception:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)
        raise OSError("safe_open_failed") from None


@contextmanager
def _open_binary_no_follow(path: Path) -> Iterator[BinaryIO]:
    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if os.name == "nt":
        descriptor = _open_windows_no_follow(path)
    else:
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        yield stream


def _read_verified_plain_bytes(
    repo_root: Path,
    parts: tuple[str, ...],
    path: Path,
    budget: ScanBudget,
    display_path: str,
) -> bytes:
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or _is_reparse_point(before):
        raise PrivacyScanError("entry_not_plain")
    budget.reserve(before.st_size, path=display_path)
    with _open_binary_no_follow(path) as stream:
        opened = os.fstat(stream.fileno())
        state, current_path = _filesystem_entry_state(repo_root, parts)
        if state != "plain" or current_path is None:
            raise PrivacyScanError("entry_changed")
        current = os.lstat(current_path)
        if not _same_file_identity(before, opened) or not _same_file_identity(opened, current):
            raise PrivacyScanError("entry_changed")
        content = stream.read(before.st_size + 1)
        if len(content) != before.st_size:
            raise PrivacyScanError("entry_changed")
        final = os.lstat(current_path)
        if not _same_file_identity(opened, final):
            raise PrivacyScanError("entry_changed")
    return content


def _entry_problem(entry: GitPathEntry, tracked_code: str, untracked_code: str) -> PrivacyProblem:
    return PrivacyProblem(file=entry.path, code=tracked_code if entry.tracked else untracked_code)


def _run_git_with_input(repo_root: Path, args: list[str], payload: bytes, *, max_stdout: int) -> bytes:
    return _run_bounded_process(
        ["git", "--no-replace-objects", *args],
        cwd=repo_root,
        payload=payload,
        max_stdout=max_stdout,
        timeout_seconds=GIT_COMMAND_TIMEOUT_SECONDS,
    )


def _decode_observed_bytes(content: bytes) -> str:
    sample = content[:8192]
    control_count = sum(byte < 9 or (13 < byte < 32) for byte in sample)
    looks_binary = b"\0" in sample or (bool(sample) and control_count * 10 > len(sample) * 3)
    if looks_binary:
        return content.decode("latin-1")
    return content.decode("utf-8", errors="replace")


def _read_index_blobs(
    repo_root: Path,
    entries: list[GitPathEntry],
    budget: ScanBudget,
) -> dict[str, bytes]:
    paths_by_object: dict[str, list[str]] = {}
    for entry in entries:
        if entry.object_id is None or not FULL_OBJECT_ID_RE.fullmatch(entry.object_id):
            raise PrivacyScanError("git_object_id_invalid")
        paths_by_object.setdefault(entry.object_id, []).append(entry.path)
    object_ids = sorted(paths_by_object)
    if not object_ids:
        return {}

    payload = ("\n".join(object_ids) + "\n").encode("ascii")
    check_output = _run_git_with_input(
        repo_root,
        ["cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
        payload,
        max_stdout=len(object_ids) * MAX_BATCH_CHECK_LINE_BYTES,
    )
    check_lines = check_output.splitlines()
    if len(check_lines) != len(object_ids):
        raise PrivacyScanError("git_object_metadata_invalid")

    object_sizes: dict[str, int] = {}
    for expected_object_id, line in zip(object_ids, check_lines, strict=True):
        fields = line.split()
        if len(fields) != 3:
            raise PrivacyScanError("git_object_metadata_invalid")
        try:
            returned_object_id = fields[0].decode("ascii").lower()
            object_type = fields[1].decode("ascii")
            object_size = int(fields[2].decode("ascii"))
        except (UnicodeDecodeError, ValueError):
            raise PrivacyScanError("git_object_metadata_invalid") from None
        if returned_object_id != expected_object_id or object_type != "blob":
            raise PrivacyScanError("git_object_metadata_invalid")
        budget.reserve(object_size, path=paths_by_object[expected_object_id][0])
        object_sizes[expected_object_id] = object_size

    batch_output_limit = sum(object_sizes.values()) + len(object_ids) * MAX_BATCH_RESPONSE_OVERHEAD_BYTES
    batch_output = _run_git_with_input(
        repo_root,
        ["cat-file", "--batch"],
        payload,
        max_stdout=batch_output_limit,
    )
    blobs: dict[str, bytes] = {}
    offset = 0
    for expected_object_id in object_ids:
        header_end = batch_output.find(b"\n", offset)
        if header_end < 0:
            raise PrivacyScanError("git_object_batch_invalid")
        header = batch_output[offset:header_end].split()
        if len(header) != 3:
            raise PrivacyScanError("git_object_batch_invalid")
        try:
            returned_object_id = header[0].decode("ascii").lower()
            object_type = header[1].decode("ascii")
            object_size = int(header[2].decode("ascii"))
        except (UnicodeDecodeError, ValueError):
            raise PrivacyScanError("git_object_batch_invalid") from None
        if (
            returned_object_id != expected_object_id
            or object_type != "blob"
            or object_size != object_sizes[expected_object_id]
        ):
            raise PrivacyScanError("git_object_batch_invalid")
        content_start = header_end + 1
        content_end = content_start + object_size
        if content_end >= len(batch_output) or batch_output[content_end : content_end + 1] != b"\n":
            raise PrivacyScanError("git_object_batch_invalid")
        blobs[expected_object_id] = batch_output[content_start:content_end]
        offset = content_end + 1
    if offset != len(batch_output):
        raise PrivacyScanError("git_object_batch_invalid")
    return blobs


def _scan_index_entries(
    repo_root: Path,
    entries: list[GitPathEntry],
    budget: ScanBudget,
) -> list[PrivacyProblem]:
    regular_entries = [entry for entry in entries if entry.tracked and entry.mode in REGULAR_GIT_MODES]
    blobs = _read_index_blobs(repo_root, regular_entries, budget)
    findings_by_object: dict[str, list[PrivacyProblem]] = {}
    problems: list[PrivacyProblem] = []
    for entry in regular_entries:
        assert entry.object_id is not None
        if entry.object_id not in findings_by_object:
            text = _decode_observed_bytes(blobs[entry.object_id])
            findings_by_object[entry.object_id] = check_text_for_privacy(path=".", text=text)
        for finding in findings_by_object[entry.object_id]:
            problems.append(PrivacyProblem(file=entry.path, code=finding.code, count=finding.count))
    return problems


def check_public_privacy(repo_root: Path) -> list[PrivacyProblem]:
    try:
        entries = list_git_entries(repo_root)
    except PrivacyLimitError as limit:
        return [PrivacyProblem(file=limit.path, code=limit.code)]

    budget = ScanBudget()
    initial_index_snapshot = tracked_index_snapshot(entries)
    problems: list[PrivacyProblem] = []
    for entry in entries:
        problems.extend(check_text_for_privacy(path=entry.path, text=entry.path))
    try:
        problems.extend(_scan_index_entries(repo_root, entries, budget))
    except PrivacyLimitError as limit:
        return [PrivacyProblem(file=limit.path, code=limit.code)]
    except PrivacyScanError:
        return [PrivacyProblem(file=".", code="PRIV019")]

    processed_worktree_paths: set[str] = set()
    for entry in entries:
        parts = _relative_path_parts(entry.path)
        if entry.tracked and (entry.mode not in REGULAR_GIT_MODES or parts is None):
            problems.append(_entry_problem(entry, "PRIV012", "PRIV013"))
            continue
        if not entry.tracked and parts is None:
            problems.append(_entry_problem(entry, "PRIV012", "PRIV013"))
            continue
        assert parts is not None

        if entry.path in processed_worktree_paths:
            continue
        processed_worktree_paths.add(entry.path)

        state, candidate = _filesystem_entry_state(repo_root, parts)
        if state == "missing":
            continue
        if state != "plain" or candidate is None:
            problems.append(_entry_problem(entry, "PRIV012", "PRIV013"))
            continue
        if not entry.tracked and not is_sensitive_untracked_path(entry.path):
            continue

        try:
            content = _read_verified_plain_bytes(repo_root, parts, candidate, budget, entry.path)
        except PrivacyLimitError as limit:
            return [PrivacyProblem(file=limit.path, code=limit.code)]
        except (OSError, PrivacyScanError):
            problems.append(_entry_problem(entry, "PRIV014", "PRIV015"))
            continue
        text = _decode_observed_bytes(content)
        problems.extend(check_text_for_privacy(path=entry.path, text=text))

    try:
        final_entries = list_git_entries(repo_root)
    except PrivacyLimitError as limit:
        return [PrivacyProblem(file=limit.path, code=limit.code)]
    if tracked_index_snapshot(final_entries) != initial_index_snapshot:
        return [PrivacyProblem(file=".", code="PRIV020")]
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check public files for obvious local path, token, seed phrase, and private URL leaks.")
    parser.add_argument("--repo-root", default=None, help="Repository root. Defaults to the script's repository.")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_script()

    try:
        problems = check_public_privacy(repo_root)
    except Exception:
        print("code=PRIV900 type=scanner_runtime_error count=1 path=<repository>", file=sys.stderr)
        return 2

    if problems:
        print(f"code=PRIV901 type=privacy_findings count={sum(problem.count for problem in problems)} path=.")
        for problem in problems:
            print(problem.format())
        return 1

    print("code=PRIV000 type=clean count=0 path=.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
