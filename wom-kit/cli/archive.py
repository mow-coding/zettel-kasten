#!/usr/bin/env python3
"""Compatibility wrapper for the packaged archive CLI."""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import os
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path, PurePosixPath


EXPECTED_HEAD = globals().get("_WOM_BRIDGE_EXPECTED_HEAD")
EXPECTED_TAG = globals().get("_WOM_BRIDGE_EXPECTED_TAG")
EXPECTED_WRAPPER_BLOB = globals().get("_WOM_BRIDGE_EXPECTED_WRAPPER_BLOB")
BOUND_PROJECT_ROOT = globals().get("_WOM_BRIDGE_PROJECT_ROOT")
if isinstance(EXPECTED_HEAD, str) and isinstance(BOUND_PROJECT_ROOT, str):
    PROJECT_ROOT = Path(BOUND_PROJECT_ROOT)
    KIT_ROOT = PROJECT_ROOT / "wom-kit"
else:
    KIT_ROOT = Path(__file__).resolve().parents[1]
    PROJECT_ROOT = KIT_ROOT.parent
SRC_ROOT = KIT_ROOT / "src"
PACKAGE_INIT = SRC_ROOT / "wom_kit" / "__init__.py"
ARCHIVE_CLI = SRC_ROOT / "wom_kit" / "archive_cli.py"
WRAPPER_GIT_PATH = "wom-kit/cli/archive.py"
PACKAGE_GIT_PREFIX = "wom-kit/src/wom_kit/"
MAX_TRACKED_PYTHON_SOURCES = 512
MAX_SOURCE_TREE_ENTRIES = 8192
MAX_PYTHON_SOURCE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_PYTHON_SOURCE_BYTES = 128 * 1024 * 1024
MAX_GIT_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_GIT_STDIN_BYTES = 2 * 1024 * 1024
BRIDGE_RECOVERY_DOC_URL = "https://github.com/mow-coding/zettel-kasten/blob/main/wom-kit/docs/version-truth-source.md#wom-bridge-refusal-codes"
RESOURCE_MANIFEST_GIT_PATH = (
    "wom-kit/src/wom_kit/_resources/resource-manifest.json"
)
RESOURCE_SOURCE_PREFIXES = {
    "schemas": "wom-kit/schemas/",
    "templates": "wom-kit/templates/",
    "zettel-kasten": "wom-kit/zettel-kasten/",
    "docs": "wom-kit/docs/",
}
PACKAGED_RESOURCE_PREFIX = "wom-kit/src/wom_kit/_resources/"
FORBIDDEN_EXTENSION_SUFFIXES = tuple(
    sorted(
        {
            ".dll",
            ".dylib",
            ".pyd",
            ".so",
            *(suffix.lower() for suffix in importlib.machinery.EXTENSION_SUFFIXES),
        },
        key=len,
        reverse=True,
    )
)
sys.dont_write_bytecode = True


def _refuse(error_code: str) -> None:
    print(error_code, file=sys.stderr)
    print(
        f"WOM_BRIDGE_RECOVERY_DOC={BRIDGE_RECOVERY_DOC_URL}",
        file=sys.stderr,
    )
    raise SystemExit(1)


def _module_file_is_exact(module: object, expected: Path) -> bool:
    module_file = getattr(module, "__file__", None)
    module_spec = getattr(module, "__spec__", None)
    module_origin = getattr(module_spec, "origin", None)
    module_loader = getattr(module, "__loader__", None)
    if not isinstance(module_file, str):
        return False
    if not isinstance(module_origin, str):
        return False
    if not isinstance(module_loader, importlib.machinery.SourceFileLoader):
        return False
    try:
        resolved_source = SRC_ROOT.resolve(strict=True)
        resolved_expected = expected.resolve(strict=True)
        resolved_actual = Path(module_file).resolve(strict=True)
        resolved_origin = Path(module_origin).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return False
    return (
        resolved_expected.is_relative_to(resolved_source)
        and resolved_actual == resolved_expected
        and resolved_origin == resolved_expected
    )


def _sanitized_git_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    environment["GIT_NO_LAZY_FETCH"] = "1"
    return environment


def _run_capped(
    command: list[str],
    max_bytes: int,
    *,
    input_bytes: bytes | None = None,
) -> bytes | None:
    if (
        max_bytes < 0
        or (
            input_bytes is not None
            and (
                not isinstance(input_bytes, bytes)
                or len(input_bytes) > MAX_GIT_STDIN_BYTES
            )
        )
    ):
        return None
    try:
        process = subprocess.Popen(
            command,
            stdin=(
                subprocess.PIPE
                if input_bytes is not None
                else subprocess.DEVNULL
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=_sanitized_git_environment(),
        )
    except (OSError, ValueError):
        return None
    if process.stdout is None:
        process.kill()
        process.wait()
        return None
    output_box: list[bytes] = []
    read_failed = threading.Event()
    write_failed = threading.Event()

    def read_once() -> None:
        try:
            chunks: list[bytes] = []
            total = 0
            while total <= max_bytes:
                chunk = os.read(
                    process.stdout.fileno(),
                    min(64 * 1024, max_bytes + 1 - total),
                )
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            output_box.append(b"".join(chunks))
        except (OSError, ValueError):
            read_failed.set()

    reader = threading.Thread(target=read_once, daemon=True)
    reader.start()
    writer: threading.Thread | None = None
    if input_bytes is not None:
        if process.stdin is None:
            process.kill()
            process.wait()
            return None

        def write_once() -> None:
            try:
                offset = 0
                while offset < len(input_bytes):
                    written = os.write(
                        process.stdin.fileno(),
                        input_bytes[offset : offset + 64 * 1024],
                    )
                    if written <= 0:
                        write_failed.set()
                        break
                    offset += written
            except (BrokenPipeError, OSError, ValueError):
                write_failed.set()
            finally:
                try:
                    process.stdin.close()
                except (OSError, ValueError):
                    write_failed.set()

        writer = threading.Thread(target=write_once, daemon=True)
        writer.start()

    deadline = time.monotonic() + 10
    timed_out = False
    workers = [reader, *([writer] if writer is not None else [])]
    while any(worker.is_alive() for worker in workers):
        for worker in workers:
            worker.join(timeout=0.01)
        if time.monotonic() >= deadline:
            timed_out = True
            try:
                process.kill()
            except OSError:
                pass
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except (OSError, ValueError):
                    pass
            try:
                process.stdout.close()
            except OSError:
                pass
            break
    for worker in workers:
        worker.join(timeout=1.0)
    output = output_box[0] if output_box else b""
    overflow = len(output) > max_bytes
    worker_alive = any(worker.is_alive() for worker in workers)
    if (
        overflow
        or read_failed.is_set()
        or write_failed.is_set()
        or worker_alive
    ):
        try:
            process.kill()
        except OSError:
            pass
    try:
        return_code = process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        process.wait()
        return_code = -1
    try:
        process.stdout.close()
    except OSError:
        pass
    if (
        timed_out
        or overflow
        or read_failed.is_set()
        or write_failed.is_set()
        or worker_alive
        or return_code != 0
    ):
        return None
    return output


def _git_output(
    args: list[str],
    *,
    max_bytes: int = MAX_GIT_OUTPUT_BYTES,
    input_bytes: bytes | None = None,
) -> bytes | None:
    return _run_capped(
        [
            "git",
            "--no-optional-locks",
            "--no-replace-objects",
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            f"core.attributesFile={os.devnull}",
            "-c",
            f"core.excludesFile={os.devnull}",
            "-C",
            str(PROJECT_ROOT),
            *args,
        ],
        max_bytes,
        input_bytes=input_bytes,
    )


def _path_is_real(path: Path) -> bool:
    try:
        relative = path.relative_to(PROJECT_ROOT)
    except ValueError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    current = PROJECT_ROOT
    components = [PROJECT_ROOT]
    for part in relative.parts:
        current = current / part
        components.append(current)
    for component in components:
        try:
            component_stat = os.lstat(component)
        except OSError:
            return False
        if stat.S_ISLNK(component_stat.st_mode):
            return False
        if (
            reparse_flag
            and getattr(component_stat, "st_file_attributes", 0) & reparse_flag
        ):
            return False
    return True


def _sys_path_entry_aliases_project(entry: object) -> bool:
    """Reject import search entries that can resolve project-inserted modules."""

    if not isinstance(entry, str) or not entry:
        return True
    try:
        candidate = Path(entry)
        if not candidate.is_absolute():
            return True
        lexical_candidate = Path(os.path.abspath(str(candidate)))
        lexical_project = Path(os.path.abspath(str(PROJECT_ROOT)))
        resolved_candidate = candidate.resolve(strict=False)
        resolved_project = PROJECT_ROOT.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return True
    return bool(
        lexical_candidate == lexical_project
        or lexical_candidate.is_relative_to(lexical_project)
        or resolved_candidate == resolved_project
        or resolved_candidate.is_relative_to(resolved_project)
    )


def _git_metadata_is_local_real() -> bool:
    expected = PROJECT_ROOT / ".git"
    if not expected.is_dir() or not _path_is_real(expected):
        return False
    git_dir = _git_output(["rev-parse", "--absolute-git-dir"], max_bytes=65536)
    common_dir = _git_output(["rev-parse", "--git-common-dir"], max_bytes=65536)
    if git_dir is None or common_dir is None:
        return False
    try:
        reported_git = Path(git_dir.decode("utf-8").rstrip("\r\n"))
        reported_common = Path(
            common_dir.decode("utf-8").rstrip("\r\n")
        )
        if not reported_common.is_absolute():
            reported_common = PROJECT_ROOT / reported_common
        if (
            reported_git.resolve(strict=True) != expected.resolve(strict=True)
            or reported_common.resolve(strict=True)
            != expected.resolve(strict=True)
        ):
            return False
    except (OSError, RuntimeError, UnicodeError, ValueError):
        return False
    for forbidden_overlay in (
        expected / "objects" / "info" / "alternates",
        expected / "info" / "grafts",
        expected / "refs" / "replace",
    ):
        try:
            os.lstat(forbidden_overlay)
            return False
        except FileNotFoundError:
            pass
        except OSError:
            return False
    packed_refs = expected / "packed-refs"
    try:
        packed_info = os.lstat(packed_refs)
    except FileNotFoundError:
        packed_info = None
    except OSError:
        return False
    if packed_info is not None:
        if (
            not stat.S_ISREG(packed_info.st_mode)
            or packed_info.st_size > 4 * 1024 * 1024
        ):
            return False
        try:
            with packed_refs.open("rb") as handle:
                packed_bytes = handle.read(4 * 1024 * 1024 + 1)
        except OSError:
            return False
        if len(packed_bytes) > 4 * 1024 * 1024 or b"refs/replace/" in packed_bytes:
            return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    stack = [expected]
    seen = 0
    try:
        while stack:
            directory = stack.pop()
            with os.scandir(directory) as scanner:
                for entry in scanner:
                    seen += 1
                    if seen > 100_000:
                        return False
                    entry_stat = entry.stat(follow_symlinks=False)
                    if (
                        stat.S_ISLNK(entry_stat.st_mode)
                        or (
                            reparse_flag
                            and getattr(entry_stat, "st_file_attributes", 0)
                            & reparse_flag
                        )
                    ):
                        return False
                    if stat.S_ISDIR(entry_stat.st_mode):
                        stack.append(Path(entry.path))
                    elif not stat.S_ISREG(entry_stat.st_mode):
                        return False
    except OSError:
        return False
    return True


def _runtime_python_entries(ref: str) -> dict[str, tuple[str, str]] | None:
    top_level = _git_output(["rev-parse", "--show-toplevel"])
    if top_level is None:
        return None
    try:
        resolved_top_level = Path(
            top_level.decode("utf-8").rstrip("\r\n")
        ).resolve(strict=True)
    except (OSError, RuntimeError, UnicodeError, ValueError):
        return None
    if resolved_top_level != PROJECT_ROOT.resolve():
        return None

    tree = _git_output(
        [
            "ls-tree",
            "-r",
            "-z",
            ref,
            "--",
            WRAPPER_GIT_PATH,
            PACKAGE_GIT_PREFIX.rstrip("/"),
        ]
    )
    if tree is None:
        return None
    entries: dict[str, tuple[str, str]] = {}
    try:
        records = tree.decode("utf-8").split("\0")
    except UnicodeError:
        return None
    for record in records:
        if not record:
            continue
        try:
            metadata, relative_path = record.split("\t", 1)
            mode, object_type, object_id = metadata.split(" ", 2)
        except ValueError:
            return None
        is_runtime_python = (
            relative_path == WRAPPER_GIT_PATH
            or (
                relative_path.startswith(PACKAGE_GIT_PREFIX)
                and relative_path.endswith(".py")
            )
        )
        if not is_runtime_python:
            continue
        pure_path = PurePosixPath(relative_path)
        if (
            pure_path.is_absolute()
            or any(part in {"", ".", ".."} for part in pure_path.parts)
            or object_type != "blob"
            or mode not in {"100644", "100755"}
            or len(object_id) not in {40, 64}
            or any(character not in "0123456789abcdefABCDEF" for character in object_id)
            or relative_path in entries
        ):
            return None
        entries[relative_path] = (mode, object_id.lower())
    required_paths = {
        WRAPPER_GIT_PATH,
        f"{PACKAGE_GIT_PREFIX}__init__.py",
        f"{PACKAGE_GIT_PREFIX}archive_cli.py",
    }
    if (
        not required_paths.issubset(entries)
        or not 0 < len(entries) <= MAX_TRACKED_PYTHON_SOURCES
    ):
        return None
    return entries


def _runtime_python_index_matches_ref(
    ref_entries: dict[str, tuple[str, str]],
) -> bool:
    flags = _git_output(
        [
            "ls-files",
            "-v",
            "-z",
            "--",
            WRAPPER_GIT_PATH,
            PACKAGE_GIT_PREFIX.rstrip("/"),
        ]
    )
    if flags is None:
        return False
    flag_entries: dict[str, str] = {}
    try:
        flag_records = flags.decode("utf-8").split("\0")
    except UnicodeError:
        return False
    for record in flag_records:
        if not record:
            continue
        if len(record) < 3 or record[1] != " ":
            return False
        tag = record[0]
        relative_path = record[2:]
        if (
            relative_path == WRAPPER_GIT_PATH
            or (
                relative_path.startswith(PACKAGE_GIT_PREFIX)
                and relative_path.endswith(".py")
            )
        ):
            if relative_path in flag_entries:
                return False
            flag_entries[relative_path] = tag
    if set(flag_entries) != set(ref_entries):
        return False
    if any(tag != "H" for tag in flag_entries.values()):
        return False

    index = _git_output(
        [
            "ls-files",
            "--stage",
            "-z",
            "--",
            WRAPPER_GIT_PATH,
            PACKAGE_GIT_PREFIX.rstrip("/"),
        ]
    )
    if index is None:
        return False
    index_entries: dict[str, tuple[str, str]] = {}
    try:
        index_records = index.decode("utf-8").split("\0")
    except UnicodeError:
        return False
    for record in index_records:
        if not record:
            continue
        try:
            metadata, relative_path = record.split("\t", 1)
            mode, object_id, stage = metadata.split(" ", 2)
        except ValueError:
            return False
        if (
            relative_path == WRAPPER_GIT_PATH
            or (
                relative_path.startswith(PACKAGE_GIT_PREFIX)
                and relative_path.endswith(".py")
            )
        ):
            if (
                stage != "0"
                or len(object_id) not in {40, 64}
                or any(
                    character not in "0123456789abcdefABCDEF"
                    for character in object_id
                )
                or relative_path in index_entries
            ):
                return False
            index_entries[relative_path] = (mode, object_id.lower())
    return index_entries == ref_entries


def _all_tracked_index_flags_are_safe() -> bool:
    flags = _git_output(["ls-files", "-v", "-z"])
    if flags is None:
        return False
    try:
        records = flags.decode("utf-8").split("\0")
    except UnicodeError:
        return False
    seen = 0
    for record in records:
        if not record:
            continue
        if len(record) < 3 or record[0] != "H" or record[1] != " ":
            return False
        relative_path = PurePosixPath(record[2:])
        if (
            relative_path.is_absolute()
            or any(part in {"", ".", ".."} for part in relative_path.parts)
        ):
            return False
        seen += 1
        if seen > MAX_SOURCE_TREE_ENTRIES * 4:
            return False
    return seen > 0


def _source_tree_is_closed(tracked_paths: set[str]) -> bool:
    if not SRC_ROOT.is_dir() or not _path_is_real(SRC_ROOT):
        return False
    expected_python_paths = {
        relative_path
        for relative_path in tracked_paths
        if relative_path.startswith(PACKAGE_GIT_PREFIX)
    }
    actual_python_paths: set[str] = set()
    top_level_entries: list[tuple[str, bool]] = []
    stack = [SRC_ROOT]
    entry_count = 0
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    try:
        while stack:
            directory = stack.pop()
            with os.scandir(directory) as scanner:
                for entry in scanner:
                    entry_count += 1
                    if entry_count > MAX_SOURCE_TREE_ENTRIES:
                        return False
                    entry_path = Path(entry.path)
                    entry_stat = entry.stat(follow_symlinks=False)
                    is_reparse = bool(
                        reparse_flag
                        and getattr(
                            entry_stat,
                            "st_file_attributes",
                            0,
                        )
                        & reparse_flag
                    )
                    is_directory = stat.S_ISDIR(entry_stat.st_mode)
                    is_regular = stat.S_ISREG(entry_stat.st_mode)
                    if (
                        stat.S_ISLNK(entry_stat.st_mode)
                        or is_reparse
                        or not (is_directory or is_regular)
                        or not entry_path.is_relative_to(SRC_ROOT)
                    ):
                        return False
                    if directory == SRC_ROOT:
                        top_level_entries.append(
                            (entry.name, is_directory)
                        )
                    lower_name = entry.name.lower()
                    if is_directory:
                        if lower_name == "__pycache__":
                            return False
                        stack.append(entry_path)
                        continue
                    relative_path = (
                        entry_path.relative_to(PROJECT_ROOT).as_posix()
                    )
                    if lower_name.endswith(".py"):
                        actual_python_paths.add(relative_path)
                    if lower_name.endswith((".pyc", ".pyo")):
                        return False
                    if lower_name.endswith(FORBIDDEN_EXTENSION_SUFFIXES):
                        return False
    except (OSError, RuntimeError, ValueError):
        return False
    return (
        top_level_entries == [("wom_kit", True)]
        and actual_python_paths == expected_python_paths
    )


def _runtime_python_bytes_match_ref(
    ref_entries: dict[str, tuple[str, str]],
) -> bool:
    total_source_bytes = 0
    for relative_path, (_, expected_object_id) in sorted(ref_entries.items()):
        if (
            isinstance(EXPECTED_HEAD, str)
            and relative_path == WRAPPER_GIT_PATH
        ):
            # The bootstrap executes the expected wrapper Git blob directly
            # from memory. Re-opening the mutable wrapper path here would
            # reintroduce the very swap/read race the bootstrap removes.
            continue
        source_path = PROJECT_ROOT.joinpath(*relative_path.split("/"))
        if not source_path.is_file() or not _path_is_real(source_path):
            return False
        try:
            source_stat = os.lstat(source_path)
            source_size = source_stat.st_size
            if (
                not stat.S_ISREG(source_stat.st_mode)
                or source_size < 0
                or source_size > MAX_PYTHON_SOURCE_BYTES
            ):
                return False
            total_source_bytes += source_size
            if total_source_bytes > MAX_TOTAL_PYTHON_SOURCE_BYTES:
                return False
            source_bytes = source_path.read_bytes()
        except (OSError, OverflowError):
            return False
        if len(source_bytes) != source_size:
            return False
        if not _source_bytes_match_object_id(source_bytes, expected_object_id):
            return False
    return True


def _git_blob_at_ref(
    ref: str,
    relative_path: str,
    *,
    max_bytes: int,
) -> tuple[str, bytes] | None:
    tree = _git_output(
        ["ls-tree", "-z", ref, "--", relative_path],
        max_bytes=16 * 1024,
    )
    if tree is None:
        return None
    try:
        records = [record for record in tree.decode("utf-8").split("\0") if record]
        if len(records) != 1:
            return None
        metadata, actual_path = records[0].split("\t", 1)
        mode, object_type, object_id = metadata.split(" ", 2)
    except (UnicodeError, ValueError):
        return None
    if (
        actual_path != relative_path
        or mode not in {"100644", "100755"}
        or object_type != "blob"
        or len(object_id) not in {40, 64}
        or any(character not in "0123456789abcdefABCDEF" for character in object_id)
    ):
        return None
    blob = _git_output(
        ["cat-file", "blob", object_id],
        max_bytes=max_bytes,
    )
    if blob is None or len(blob) > max_bytes:
        return None
    if not _source_bytes_match_object_id(blob, object_id.lower()):
        return None
    return object_id.lower(), blob


def _strict_nul_records(
    value: bytes,
    *,
    max_records: int,
) -> list[bytes] | None:
    if (
        not value
        or not value.endswith(b"\0")
        or max_records < 1
    ):
        return None
    records = value[:-1].split(b"\0")
    if (
        not records
        or len(records) > max_records
        or any(not record for record in records)
    ):
        return None
    return records


def _safe_git_relative_path(value: str) -> bool:
    if (
        not value
        or "\\" in value
        or any(character in value for character in "\0\r\n")
    ):
        return False
    pure_path = PurePosixPath(value)
    return bool(
        pure_path.as_posix() == value
        and not pure_path.is_absolute()
        and pure_path.parts
        and all(part not in {"", ".", ".."} for part in pure_path.parts)
    )


def _git_tree_inventory(
    ref: str,
) -> dict[str, tuple[str, str, str]] | None:
    tree = _git_output(
        ["ls-tree", "-r", "-z", "--full-tree", ref],
        max_bytes=MAX_GIT_OUTPUT_BYTES,
    )
    if tree is None:
        return None
    records = _strict_nul_records(
        tree,
        max_records=MAX_SOURCE_TREE_ENTRIES,
    )
    if records is None:
        return None
    entries: dict[str, tuple[str, str, str]] = {}
    allowed_objects = {
        ("100644", "blob"),
        ("100755", "blob"),
        ("120000", "blob"),
        ("160000", "commit"),
    }
    for record in records:
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode_bytes, type_bytes, object_id_bytes = metadata.split(b" ", 2)
            mode = mode_bytes.decode("ascii")
            object_type = type_bytes.decode("ascii")
            object_id = object_id_bytes.decode("ascii")
            relative_path = raw_path.decode("utf-8")
        except (UnicodeError, ValueError):
            return None
        if (
            (mode, object_type) not in allowed_objects
            or len(object_id) not in {40, 64}
            or any(character not in "0123456789abcdef" for character in object_id)
            or not _safe_git_relative_path(relative_path)
            or relative_path in entries
        ):
            return None
        entries[relative_path] = (mode, object_type, object_id)
    return entries


def _git_stage_zero_index_inventory(
) -> dict[str, tuple[str, str]] | None:
    index = _git_output(
        ["ls-files", "--stage", "-z"],
        max_bytes=MAX_GIT_OUTPUT_BYTES,
    )
    if index is None:
        return None
    records = _strict_nul_records(
        index,
        max_records=MAX_SOURCE_TREE_ENTRIES * 4,
    )
    if records is None:
        return None
    entries: dict[str, tuple[str, str]] = {}
    for record in records:
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode_bytes, object_id_bytes, stage_bytes = metadata.split(b" ", 2)
            mode = mode_bytes.decode("ascii")
            object_id = object_id_bytes.decode("ascii")
            stage = stage_bytes.decode("ascii")
            relative_path = raw_path.decode("utf-8")
        except (UnicodeError, ValueError):
            return None
        if (
            stage != "0"
            or mode not in {"100644", "100755", "120000", "160000"}
            or len(object_id) not in {40, 64}
            or any(character not in "0123456789abcdef" for character in object_id)
            or not _safe_git_relative_path(relative_path)
            or relative_path in entries
        ):
            return None
        entries[relative_path] = (mode, object_id)
    return entries


def _git_blob_batch(
    expected_sizes: dict[str, int],
) -> dict[str, bytes] | None:
    if (
        not expected_sizes
        or len(expected_sizes) > MAX_SOURCE_TREE_ENTRIES * 2 + 1
    ):
        return None
    ordered_object_ids = sorted(expected_sizes)
    for object_id, expected_size in expected_sizes.items():
        if (
            len(object_id) not in {40, 64}
            or any(character not in "0123456789abcdef" for character in object_id)
            or isinstance(expected_size, bool)
            or not isinstance(expected_size, int)
            or expected_size < 0
            or expected_size > MAX_PYTHON_SOURCE_BYTES
        ):
            return None
    batch_input = b"".join(
        object_id.encode("ascii") + b"\n"
        for object_id in ordered_object_ids
    )
    if len(batch_input) > MAX_GIT_STDIN_BYTES:
        return None
    maximum_output = sum(expected_sizes.values()) + len(expected_sizes) * 128
    if maximum_output > MAX_TOTAL_PYTHON_SOURCE_BYTES + MAX_GIT_OUTPUT_BYTES:
        return None
    output = _git_output(
        ["cat-file", "--batch"],
        max_bytes=maximum_output,
        input_bytes=batch_input,
    )
    if output is None:
        return None

    offset = 0
    blobs: dict[str, bytes] = {}
    for expected_object_id in ordered_object_ids:
        header_end = output.find(b"\n", offset)
        if header_end < 0:
            return None
        header = output[offset:header_end]
        try:
            object_id_bytes, object_type, size_bytes = header.split(b" ")
            object_id = object_id_bytes.decode("ascii")
            size_text = size_bytes.decode("ascii")
        except (UnicodeError, ValueError):
            return None
        if (
            object_id != expected_object_id
            or object_type != b"blob"
            or not size_text.isascii()
            or not size_text.isdecimal()
            or (len(size_text) > 1 and size_text.startswith("0"))
        ):
            return None
        size = int(size_text)
        if size != expected_sizes[expected_object_id]:
            return None
        body_start = header_end + 1
        body_end = body_start + size
        if (
            body_end >= len(output)
            or output[body_end : body_end + 1] != b"\n"
        ):
            return None
        body = output[body_start:body_end]
        if not _source_bytes_match_object_id(body, expected_object_id):
            return None
        blobs[expected_object_id] = body
        offset = body_end + 1
    if offset != len(output) or set(blobs) != set(expected_sizes):
        return None
    return blobs


def _bounded_real_file_bytes(path: Path, *, max_bytes: int) -> bytes | None:
    if not path.is_file() or not _path_is_real(path):
        return None
    descriptor: int | None = None
    try:
        before = os.lstat(path)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size < 0
            or before.st_size > max_bytes
        ):
            return None
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_size != before.st_size
            or (before.st_ino and opened.st_ino and before.st_ino != opened.st_ino)
            or (before.st_dev and opened.st_dev and before.st_dev != opened.st_dev)
        ):
            return None
        value = b""
        while len(value) <= max_bytes:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - len(value)))
            if not chunk:
                break
            value += chunk
        after = os.fstat(descriptor)
        if (
            len(value) != opened.st_size
            or after.st_size != opened.st_size
            or after.st_mtime_ns != opened.st_mtime_ns
        ):
            return None
        return value
    except (OSError, OverflowError):
        return None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _packaged_resource_worktree_files() -> set[str] | None:
    resource_root = PROJECT_ROOT.joinpath(
        *PurePosixPath(PACKAGED_RESOURCE_PREFIX.rstrip("/")).parts
    )
    if not resource_root.is_dir() or not _path_is_real(resource_root):
        return None
    files: set[str] = set()
    stack = [resource_root]
    entry_count = 0
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    try:
        while stack:
            directory = stack.pop()
            with os.scandir(directory) as scanner:
                for entry in scanner:
                    entry_count += 1
                    if entry_count > MAX_SOURCE_TREE_ENTRIES:
                        return None
                    entry_stat = entry.stat(follow_symlinks=False)
                    if (
                        stat.S_ISLNK(entry_stat.st_mode)
                        or (
                            reparse_flag
                            and getattr(
                                entry_stat,
                                "st_file_attributes",
                                0,
                            )
                            & reparse_flag
                        )
                    ):
                        return None
                    if stat.S_ISDIR(entry_stat.st_mode):
                        stack.append(Path(entry.path))
                        continue
                    if not stat.S_ISREG(entry_stat.st_mode):
                        return None
                    relative_path = (
                        Path(entry.path).relative_to(PROJECT_ROOT).as_posix()
                    )
                    if (
                        not _safe_git_relative_path(relative_path)
                        or relative_path in files
                    ):
                        return None
                    files.add(relative_path)
    except (OSError, RuntimeError, ValueError):
        return None
    return files


def _runtime_resources_match_ref(ref: str) -> bool:
    tree_entries = _git_tree_inventory(ref)
    if tree_entries is None:
        return False
    manifest_entry = tree_entries.get(RESOURCE_MANIFEST_GIT_PATH)
    if (
        manifest_entry is None
        or manifest_entry[0] not in {"100644", "100755"}
        or manifest_entry[1] != "blob"
    ):
        return False
    manifest_mode, _, manifest_object_id = manifest_entry
    manifest_path = PROJECT_ROOT.joinpath(
        *PurePosixPath(RESOURCE_MANIFEST_GIT_PATH).parts
    )
    manifest_bytes = _bounded_real_file_bytes(
        manifest_path,
        max_bytes=2 * 1024 * 1024,
    )
    if (
        manifest_bytes is None
        or not _source_bytes_match_object_id(
            manifest_bytes,
            manifest_object_id,
        )
    ):
        return False
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(manifest, dict):
        return False
    files = manifest.get("files")
    file_count = manifest.get("file_count")
    if (
        manifest.get("schema") != "wom-kit/package-resource-manifest/v0.1"
        or not isinstance(files, list)
        or isinstance(file_count, bool)
        or not isinstance(file_count, int)
        or file_count != len(files)
        or not 0 < len(files) <= MAX_SOURCE_TREE_ENTRIES
    ):
        return False

    expected_paths = {RESOURCE_MANIFEST_GIT_PATH}
    expected_ref_entries = {
        RESOURCE_MANIFEST_GIT_PATH: (manifest_mode, manifest_object_id)
    }
    expected_sizes = {manifest_object_id: len(manifest_bytes)}
    total_bytes = len(manifest_bytes)
    seen_sources: set[str] = set()
    seen_packaged: set[str] = set()
    source_package_pairs: list[tuple[str, str, int, str]] = []
    for item in files:
        if not isinstance(item, dict):
            return False
        source = item.get("source")
        packaged = item.get("packaged")
        byte_count = item.get("bytes")
        digest = item.get("sha256")
        if (
            not isinstance(source, str)
            or not isinstance(packaged, str)
            or isinstance(byte_count, bool)
            or not isinstance(byte_count, int)
            or byte_count < 0
            or byte_count > MAX_PYTHON_SOURCE_BYTES
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or source in seen_sources
            or packaged in seen_packaged
        ):
            return False
        if (
            not _safe_git_relative_path(source)
            or not _safe_git_relative_path(packaged)
        ):
            return False
        source_pure = PurePosixPath(source)
        packaged_pure = PurePosixPath(packaged)
        source_prefix = RESOURCE_SOURCE_PREFIXES.get(source_pure.parts[0])
        if source_prefix is None:
            return False
        source_path = source_prefix + "/".join(source_pure.parts[1:])
        packaged_path = PACKAGED_RESOURCE_PREFIX + packaged_pure.as_posix()
        if (
            not _safe_git_relative_path(source_path)
            or not _safe_git_relative_path(packaged_path)
            or source_path in expected_paths
            or packaged_path in expected_paths
            or source_path == packaged_path
        ):
            return False
        seen_sources.add(source)
        seen_packaged.add(packaged)
        expected_paths.update({source_path, packaged_path})
        source_entry = tree_entries.get(source_path)
        packaged_entry = tree_entries.get(packaged_path)
        if (
            source_entry is None
            or packaged_entry is None
            or source_entry[0] not in {"100644", "100755"}
            or packaged_entry[0] not in {"100644", "100755"}
            or source_entry[1] != "blob"
            or packaged_entry[1] != "blob"
        ):
            return False
        source_object_id = source_entry[2]
        packaged_object_id = packaged_entry[2]
        expected_ref_entries[source_path] = (
            source_entry[0],
            source_object_id,
        )
        expected_ref_entries[packaged_path] = (
            packaged_entry[0],
            packaged_object_id,
        )
        for object_id in (source_object_id, packaged_object_id):
            previous_size = expected_sizes.get(object_id)
            if previous_size is not None and previous_size != byte_count:
                return False
            expected_sizes[object_id] = byte_count
        source_package_pairs.append(
            (source_object_id, packaged_object_id, byte_count, digest)
        )
        total_bytes += byte_count * 2
        if total_bytes > MAX_TOTAL_PYTHON_SOURCE_BYTES:
            return False

    resource_init_path = f"{PACKAGED_RESOURCE_PREFIX}__init__.py"
    expected_packaged_paths = {
        RESOURCE_MANIFEST_GIT_PATH,
        *(
            PACKAGED_RESOURCE_PREFIX + PurePosixPath(path).as_posix()
            for path in seen_packaged
        ),
    }
    tree_packaged_paths = {
        relative_path
        for relative_path in tree_entries
        if relative_path.startswith(PACKAGED_RESOURCE_PREFIX)
    }
    tree_packaged_payload_paths = tree_packaged_paths - {resource_init_path}
    if tree_packaged_payload_paths != expected_packaged_paths:
        return False
    if (
        resource_init_path in tree_entries
        and tree_entries[resource_init_path][:2] != ("100644", "blob")
        and tree_entries[resource_init_path][:2] != ("100755", "blob")
    ):
        return False

    blobs = _git_blob_batch(expected_sizes)
    if (
        blobs is None
        or blobs.get(manifest_object_id) != manifest_bytes
    ):
        return False

    index_entries = _git_stage_zero_index_inventory()
    if index_entries is None:
        return False
    actual_expected_index = {
        relative_path: index_entries[relative_path]
        for relative_path in expected_paths
        if relative_path in index_entries
    }
    if (
        actual_expected_index != expected_ref_entries
        or set(actual_expected_index) != expected_paths
    ):
        return False
    index_packaged_paths = {
        relative_path
        for relative_path in index_entries
        if relative_path.startswith(PACKAGED_RESOURCE_PREFIX)
    }
    if index_packaged_paths != tree_packaged_paths:
        return False
    if resource_init_path in tree_packaged_paths:
        init_tree_entry = tree_entries[resource_init_path]
        if index_entries.get(resource_init_path) != (
            init_tree_entry[0],
            init_tree_entry[2],
        ):
            return False

    worktree_packaged_paths = _packaged_resource_worktree_files()
    if worktree_packaged_paths != tree_packaged_paths:
        return False

    for relative_path, (_, object_id) in expected_ref_entries.items():
        expected_bytes = blobs.get(object_id)
        if expected_bytes is None:
            return False
        path = PROJECT_ROOT.joinpath(*PurePosixPath(relative_path).parts)
        actual_bytes = _bounded_real_file_bytes(
            path,
            max_bytes=(
                2 * 1024 * 1024
                if relative_path == RESOURCE_MANIFEST_GIT_PATH
                else MAX_PYTHON_SOURCE_BYTES
            ),
        )
        if (
            actual_bytes != expected_bytes
            or not _source_bytes_match_object_id(actual_bytes, object_id)
        ):
            return False

    for source_object_id, packaged_object_id, byte_count, digest in (
        source_package_pairs
    ):
        source_bytes = blobs.get(source_object_id)
        packaged_bytes = blobs.get(packaged_object_id)
        if (
            source_bytes is None
            or packaged_bytes is None
            or source_bytes != packaged_bytes
            or len(source_bytes) != byte_count
            or hashlib.sha256(source_bytes).hexdigest() != digest
        ):
            return False
    return True


def _expected_binding_is_valid() -> bool:
    if EXPECTED_HEAD is None and EXPECTED_TAG is None and EXPECTED_WRAPPER_BLOB is None:
        return True
    if (
        not isinstance(EXPECTED_HEAD, str)
        or len(EXPECTED_HEAD) not in {40, 64}
        or any(character not in "0123456789abcdef" for character in EXPECTED_HEAD)
        or not isinstance(EXPECTED_TAG, str)
        or not EXPECTED_TAG.startswith("v")
        or not isinstance(EXPECTED_WRAPPER_BLOB, str)
        or len(EXPECTED_WRAPPER_BLOB) not in {40, 64}
        or any(
            character not in "0123456789abcdef"
            for character in EXPECTED_WRAPPER_BLOB
        )
    ):
        return False
    if not _git_metadata_is_local_real():
        return False
    head = _git_output(["rev-parse", "--verify", "HEAD"], max_bytes=256)
    tag_type = _git_output(
        ["cat-file", "-t", f"refs/tags/{EXPECTED_TAG}"],
        max_bytes=256,
    )
    tag_commit = _git_output(
        ["rev-parse", "--verify", f"refs/tags/{EXPECTED_TAG}^{{commit}}"],
        max_bytes=256,
    )
    origin_key = _git_output(
        [
            "config",
            "--local",
            "--no-includes",
            "--name-only",
            "--get-regexp",
            r"^remote\.origin\.url$",
        ],
        max_bytes=1024,
    )
    ancestor = _git_output(
        [
            "merge-base",
            "--is-ancestor",
            EXPECTED_HEAD,
            "refs/remotes/origin/main",
        ],
        max_bytes=256,
    )
    wrapper = _git_blob_at_ref(
        EXPECTED_HEAD,
        WRAPPER_GIT_PATH,
        max_bytes=MAX_PYTHON_SOURCE_BYTES,
    )
    return bool(
        head is not None
        and head.decode("ascii", errors="ignore").strip().lower() == EXPECTED_HEAD
        and tag_type == b"tag\n"
        and tag_commit is not None
        and tag_commit.decode("ascii", errors="ignore").strip().lower()
        == EXPECTED_HEAD
        and origin_key is not None
        and [
            line.strip().lower()
            for line in origin_key.decode("utf-8", errors="ignore").splitlines()
            if line.strip()
        ]
        == ["remote.origin.url"]
        and ancestor is not None
        and wrapper is not None
        and wrapper[0] == EXPECTED_WRAPPER_BLOB
    )


def _source_bytes_match_object_id(
    source_bytes: bytes,
    expected_object_id: str,
) -> bool:
    if len(expected_object_id) == 40:
        hasher = hashlib.sha1()
    elif len(expected_object_id) == 64:
        hasher = hashlib.sha256()
    else:
        return False
    hasher.update(f"blob {len(source_bytes)}\0".encode("ascii"))
    hasher.update(source_bytes)
    return hasher.hexdigest() == expected_object_id


class _VerifiedSourceFileLoader(importlib.machinery.SourceFileLoader):
    def __init__(
        self,
        fullname: str,
        path: str,
        expected_object_id: str,
    ) -> None:
        super().__init__(fullname, path)
        self._expected_object_id = expected_object_id

    def get_code(self, fullname: str) -> object:
        source_path = self.get_filename(fullname)
        source_bytes = self.get_data(source_path)
        if not _source_bytes_match_object_id(
            source_bytes,
            self._expected_object_id,
        ):
            raise ImportError("WOM_BRIDGE_SOURCE_BYTES_MISMATCH")
        return self.source_to_code(
            source_bytes,
            source_path,
            _optimize=sys.flags.optimize,
        )


class _ProjectSourceOnlyFinder:
    def __init__(
        self,
        head_entries: dict[str, tuple[str, str]],
    ) -> None:
        self._head_entries = head_entries

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: object = None,
    ) -> object:
        del path, target
        if fullname != "wom_kit" and not fullname.startswith("wom_kit."):
            return None
        module_parts = fullname.split(".")[1:]
        module_stem = "/".join(module_parts)
        module_relative = (
            f"{PACKAGE_GIT_PREFIX}{module_stem}.py"
            if module_stem
            else ""
        )
        package_relative = (
            f"{PACKAGE_GIT_PREFIX}{module_stem}/__init__.py"
            if module_stem
            else f"{PACKAGE_GIT_PREFIX}__init__.py"
        )
        matches = [
            relative_path
            for relative_path in (module_relative, package_relative)
            if relative_path and relative_path in self._head_entries
        ]
        if len(matches) != 1:
            raise ModuleNotFoundError("WOM_BRIDGE_SOURCE_MODULE_UNAVAILABLE")
        relative_path = matches[0]
        source_path = PROJECT_ROOT.joinpath(*relative_path.split("/"))
        expected_object_id = self._head_entries[relative_path][1]
        loader = _VerifiedSourceFileLoader(
            fullname,
            str(source_path),
            expected_object_id,
        )
        if relative_path == package_relative:
            return importlib.util.spec_from_file_location(
                fullname,
                source_path,
                loader=loader,
                submodule_search_locations=[str(source_path.parent)],
            )
        return importlib.util.spec_from_file_location(
            fullname,
            source_path,
            loader=loader,
        )


if any(
    name == "wom_kit" or name.startswith("wom_kit.")
    for name in tuple(sys.modules)
):
    _refuse("WOM_BRIDGE_PRELOADED_MODULE")

try:
    runtime_ref = EXPECTED_HEAD if isinstance(EXPECTED_HEAD, str) else "HEAD"
    head_runtime_python_entries = _runtime_python_entries(runtime_ref)
    source_tree_safe = bool(
        _expected_binding_is_valid()
        and head_runtime_python_entries is not None
        and _all_tracked_index_flags_are_safe()
        and _runtime_python_index_matches_ref(head_runtime_python_entries)
        and _source_tree_is_closed(set(head_runtime_python_entries))
        and _runtime_python_bytes_match_ref(head_runtime_python_entries)
        and _runtime_resources_match_ref(runtime_ref)
    )
except BaseException:
    source_tree_safe = False
if not source_tree_safe:
    _refuse("WOM_BRIDGE_SOURCE_TREE_UNSAFE")

sys.path[:] = [
    entry
    for entry in sys.path
    if not _sys_path_entry_aliases_project(entry)
]
if any(_sys_path_entry_aliases_project(entry) for entry in sys.path):
    _refuse("WOM_BRIDGE_PROJECT_PATH_ON_SYS_PATH")
sys.meta_path.insert(
    0,
    _ProjectSourceOnlyFinder(dict(head_runtime_python_entries)),
)

try:
    import wom_kit as selected_wom_kit  # noqa: E402
except BaseException:
    _refuse("WOM_BRIDGE_IMPORT_FAILED")

if not _module_file_is_exact(selected_wom_kit, PACKAGE_INIT):
    _refuse("WOM_BRIDGE_IMPORT_SOURCE_MISMATCH")

try:
    from wom_kit import archive_cli as selected_archive_cli  # noqa: E402
except BaseException:
    _refuse("WOM_BRIDGE_IMPORT_FAILED")

if not _module_file_is_exact(selected_archive_cli, ARCHIVE_CLI):
    _refuse("WOM_BRIDGE_IMPORT_SOURCE_MISMATCH")

if not callable(getattr(selected_archive_cli, "main", None)):
    _refuse("WOM_BRIDGE_ENTRYPOINT_INVALID")


if __name__ == "__main__":
    raise SystemExit(selected_archive_cli.main())
