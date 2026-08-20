#!/usr/bin/env python3
"""Build and smoke-test a WOM-kit wheel in one clean temporary environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import posixpath
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
import unicodedata
import zipfile


KIT_ROOT = Path(__file__).resolve().parents[1]
SYNC_TOOL = KIT_ROOT / "tools" / "sync_package_resources.py"
RESOURCE_PREFIX = "wom_kit/_resources/"
RESOURCE_MANIFEST_MEMBER = f"{RESOURCE_PREFIX}resource-manifest.json"
RESOURCE_PACKAGE_INIT_MEMBER = f"{RESOURCE_PREFIX}__init__.py"
RESOURCE_MANIFEST_SCHEMA = "wom-kit/package-resource-manifest/v0.1"
RESOURCE_SOURCE_OF_TRUTH = "wom-kit source resource directories"
RESOURCE_MANIFEST_KEYS = frozenset(
    {"schema", "version", "source_of_truth", "file_count", "files"}
)
RESOURCE_ROW_KEYS = frozenset({"source", "packaged", "bytes", "sha256"})
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
RESOURCE_READ_CHUNK_SIZE = 64 * 1024
WHEEL_INSTALL_CHECK_SCHEMA = "wom-kit/wheel-install-check/v0.3"
EXPECTED_UNICODEDATA2_DISTRIBUTION_VERSION = "17.0.1"
EXPECTED_UNICODEDATA_VERSION = "17.0.0"
MCP_PROTOCOL_VERSION = "2025-03-26"
MCP_SERVER_NAME = "zettel-kasten-archive-mcp"
ENTRYPOINT_TIMEOUT_SECONDS = 60
ENTRYPOINT_OUTPUT_LIMIT_BYTES = 8 * 1024 * 1024
ENTRYPOINT_READ_CHUNK_BYTES = 64 * 1024
WINDOWS_CREATE_SUSPENDED = 0x00000004
WINDOWS_JOB_TERMINATION_TIMEOUT_MILLISECONDS = 1000
WINDOWS_FORBIDDEN_SEGMENT_CHARACTERS = frozenset('<>:"|?*')
WINDOWS_RESERVED_DEVICE_BASENAMES = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
        "com¹",
        "com²",
        "com³",
        "lpt¹",
        "lpt²",
        "lpt³",
    }
)


class WheelCheckError(RuntimeError):
    pass


def run(
    command: list[str],
    *,
    cwd: Path,
    label: str,
    parse_json: bool = False,
    expected_returncode: int = 0,
    require_empty_stderr: bool = False,
) -> subprocess.CompletedProcess[str] | dict[str, Any]:
    environment = dict(os.environ)
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8:strict"
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        check=False,
    )
    if completed.returncode != expected_returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise WheelCheckError(
            f"{label} returned exit {completed.returncode}; "
            f"expected {expected_returncode}: {detail}"
        )
    if require_empty_stderr and completed.stderr:
        raise WheelCheckError(f"{label} wrote to stderr.")
    if not parse_json:
        return completed
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise WheelCheckError(f"{label} did not return JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise WheelCheckError(f"{label} did not return a JSON object.")
    return data


def ignored_copy_names(_directory: str, names: list[str]) -> set[str]:
    ignored = {"__pycache__", ".pytest_cache", "build", "dist"}
    return {
        name
        for name in names
        if name in ignored or name.endswith(".egg-info") or name.endswith(".pyc")
    }


def scripts_directory(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin")


def executable(scripts: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return scripts / f"{name}{suffix}"


def _check_installed_runtime_dependencies(python: Path, *, cwd: Path) -> None:
    """Verify dependency resolution and the pinned Unicode runtime in isolation."""

    run(
        [str(python), "-m", "pip", "check"],
        cwd=cwd,
        label="installed wheel dependency check",
    )
    evidence = run(
        [
            str(python),
            "-I",
            "-c",
            (
                "import importlib.metadata as m, json, unicodedata2 as u; "
                "print(json.dumps({"
                "'distribution_version': m.version('unicodedata2'), "
                "'unicode_version': u.unidata_version"
                "}, sort_keys=True))"
            ),
        ],
        cwd=cwd,
        label="installed Unicode runtime attestation",
        parse_json=True,
    )
    if evidence != {
        "distribution_version": EXPECTED_UNICODEDATA2_DISTRIBUTION_VERSION,
        "unicode_version": EXPECTED_UNICODEDATA_VERSION,
    }:
        raise WheelCheckError(
            "Installed Unicode runtime did not match the pinned v0.3.295 profile."
        )


def _package_resource_root() -> Path:
    """Return the committed package mirror, evaluated late for isolated tests."""

    return KIT_ROOT / "src" / "wom_kit" / "_resources"


def _assert_safe_relative_posix_path(value: str, *, label: str) -> None:
    if not value:
        raise WheelCheckError(f"{label} path must not be empty.")
    if "\x00" in value:
        raise WheelCheckError(f"{label} path contains a NUL byte.")
    if "\\" in value:
        raise WheelCheckError(f"{label} path must use forward slashes.")

    parts = value.split("/")
    if any(not part for part in parts):
        raise WheelCheckError(f"{label} path contains an empty segment.")
    if any(part in {".", ".."} for part in parts):
        raise WheelCheckError(f"{label} path contains a dot segment.")

    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if posix_path.is_absolute() or windows_path.is_absolute() or windows_path.drive:
        raise WheelCheckError(f"{label} path must be relative.")
    if posixpath.normpath(value) != value or posix_path.as_posix() != value:
        raise WheelCheckError(f"{label} path is not normalized.")
    if unicodedata.normalize("NFC", value) != value:
        raise WheelCheckError(f"{label} path is not Unicode-normalized.")

    for segment in parts:
        if any(character in WINDOWS_FORBIDDEN_SEGMENT_CHARACTERS for character in segment):
            raise WheelCheckError(
                f"{label} path contains a Win32-forbidden or ADS character."
            )
        if any(ord(character) < 32 for character in segment):
            raise WheelCheckError(f"{label} path contains a Win32 control character.")
        if segment.endswith((".", " ")):
            raise WheelCheckError(
                f"{label} path segment has a Win32-unsafe trailing dot or space."
            )
        device_basename = segment.split(".", 1)[0].rstrip(" .").casefold()
        if device_basename in WINDOWS_RESERVED_DEVICE_BASENAMES:
            raise WheelCheckError(
                f"{label} path uses a reserved Win32 device basename."
            )


def _windows_extraction_collision_key(value: str) -> tuple[str, ...]:
    """Return a conservative, platform-independent Windows extraction key."""

    return tuple(
        unicodedata.normalize("NFC", segment.casefold())
        for segment in value.split("/")
    )


def _assert_no_wheel_scheme_relocation(name: str) -> None:
    first_segment = name.split("/", 1)[0]
    if first_segment.casefold().endswith(".data") and "/" in name:
        raise WheelCheckError(
            "Wheel contains a top-level .data scheme tree, which this "
            "pure/no-data package forbids to prevent install relocation aliases."
        )


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise WheelCheckError(f"Resource manifest JSON has duplicate key {key!r}.")
        value[key] = item
    return value


def _reject_nonstandard_json_constant(value: str) -> None:
    raise WheelCheckError(
        f"Resource manifest JSON contains non-standard numeric constant {value!r}."
    )


def _parse_resource_manifest(manifest_bytes: bytes) -> dict[str, Any]:
    try:
        manifest_text = manifest_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WheelCheckError("Resource manifest is not valid UTF-8.") from exc
    try:
        manifest = json.loads(
            manifest_text,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise WheelCheckError(f"Resource manifest is not valid JSON: {exc}.") from exc
    if not isinstance(manifest, dict):
        raise WheelCheckError("Resource manifest must be a JSON object.")
    return manifest


def _require_exact_keys(
    value: dict[str, Any],
    expected: frozenset[str],
    *,
    label: str,
) -> None:
    actual = set(value)
    if actual == expected:
        return
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    details: list[str] = []
    if missing:
        details.append("missing " + ", ".join(missing))
    if unexpected:
        details.append("unexpected " + ", ".join(unexpected))
    raise WheelCheckError(f"{label} fields are invalid: {'; '.join(details)}.")


def _validated_resource_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    _require_exact_keys(
        manifest,
        RESOURCE_MANIFEST_KEYS,
        label="Resource manifest",
    )
    if manifest["schema"] != RESOURCE_MANIFEST_SCHEMA:
        raise WheelCheckError("Resource manifest schema identifier is unsupported.")
    version = manifest["version"]
    if not isinstance(version, str) or not version or version.strip() != version:
        raise WheelCheckError("Resource manifest version must be a non-empty string.")
    if manifest["source_of_truth"] != RESOURCE_SOURCE_OF_TRUTH:
        raise WheelCheckError("Resource manifest source_of_truth field is invalid.")

    file_count = manifest["file_count"]
    if type(file_count) is not int or file_count < 0:
        raise WheelCheckError("Resource manifest file_count must be a non-negative integer.")
    files = manifest["files"]
    if not isinstance(files, list):
        raise WheelCheckError("Resource manifest files field must be a list.")
    if file_count != len(files):
        raise WheelCheckError(
            "Resource manifest file_count does not match the files list length."
        )

    rows: list[dict[str, Any]] = []
    packaged_paths: set[str] = set()
    for index, item in enumerate(files):
        label = f"Resource manifest files[{index}]"
        if not isinstance(item, dict):
            raise WheelCheckError(f"{label} must be an object.")
        _require_exact_keys(item, RESOURCE_ROW_KEYS, label=label)

        source = item["source"]
        packaged = item["packaged"]
        byte_count = item["bytes"]
        sha256 = item["sha256"]
        if not isinstance(source, str):
            raise WheelCheckError(f"{label} source field must be a string.")
        if not isinstance(packaged, str):
            raise WheelCheckError(f"{label} packaged field must be a string.")
        _assert_safe_relative_posix_path(source, label=f"{label} source")
        _assert_safe_relative_posix_path(packaged, label=f"{label} packaged")
        if type(byte_count) is not int or byte_count < 0:
            raise WheelCheckError(f"{label} bytes field must be a non-negative integer.")
        if not isinstance(sha256, str) or SHA256_RE.fullmatch(sha256) is None:
            raise WheelCheckError(f"{label} sha256 field must be a lowercase SHA-256 digest.")
        if packaged in packaged_paths:
            raise WheelCheckError(
                f"Resource manifest has duplicate packaged resource {packaged!r}."
            )
        packaged_paths.add(packaged)
        rows.append(item)
    return rows


def _read_zip_member_bytes(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    *,
    expected_size: int,
    label: str,
) -> bytes:
    if info.file_size != expected_size:
        raise WheelCheckError(
            f"{label} ZIP member size does not match the expected byte count."
        )
    with archive.open(info, "r") as stream:
        data = stream.read(expected_size + 1)
        if stream.read(1):
            raise WheelCheckError(f"{label} contains more bytes than declared.")
    if len(data) != expected_size:
        raise WheelCheckError(f"{label} actual byte count does not match its ZIP member size.")
    return data


def _committed_resource_path(resource_root: Path, packaged: str) -> Path:
    root = resource_root.resolve()
    candidate = resource_root.joinpath(*packaged.split("/"))
    if candidate.is_symlink():
        raise WheelCheckError(
            f"Committed packaged resource mirror must not be a symlink: {packaged!r}."
        )
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise WheelCheckError(
            f"Committed packaged resource mirror could not be read: {packaged!r}."
        ) from exc
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise WheelCheckError(
            f"Committed packaged resource mirror is not a regular in-tree file: {packaged!r}."
        )
    return resolved


def _verify_resource_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    row: dict[str, Any],
    *,
    resource_root: Path,
) -> int:
    packaged = row["packaged"]
    declared_size = row["bytes"]
    if info.file_size != declared_size:
        raise WheelCheckError(
            f"Resource {packaged!r} ZIP member size does not match its declared byte count."
        )

    mirror_path = _committed_resource_path(resource_root, packaged)
    actual_sha256 = hashlib.sha256()
    actual_size = 0
    mirror_matches = True
    with archive.open(info, "r") as wheel_stream, mirror_path.open("rb") as mirror_stream:
        while True:
            chunk = wheel_stream.read(RESOURCE_READ_CHUNK_SIZE)
            if not chunk:
                break
            actual_size += len(chunk)
            actual_sha256.update(chunk)
            if mirror_stream.read(len(chunk)) != chunk:
                mirror_matches = False
        if mirror_stream.read(1):
            mirror_matches = False

    if actual_size != info.file_size or actual_size != declared_size:
        raise WheelCheckError(
            f"Resource {packaged!r} actual byte count does not match its declared size."
        )
    if actual_sha256.hexdigest() != row["sha256"]:
        raise WheelCheckError(
            f"Resource {packaged!r} SHA-256 does not match its declared digest."
        )
    if not mirror_matches:
        raise WheelCheckError(
            f"Resource {packaged!r} bytes differ from the committed packaged mirror."
        )
    return actual_size


def _assert_wheel_resources(wheel: Path) -> dict[str, int]:
    resource_root = _package_resource_root()
    with zipfile.ZipFile(wheel) as archive:
        infos = archive.infolist()
        infos_by_name: dict[str, zipfile.ZipInfo] = {}
        windows_extraction_names: dict[tuple[str, ...], str] = {}
        for info in infos:
            raw_name = info.orig_filename
            _assert_safe_relative_posix_path(raw_name, label="Raw ZIP member")
            name = info.filename
            _assert_safe_relative_posix_path(name, label="ZIP member")
            if raw_name != name:
                raise WheelCheckError("Raw ZIP member path was altered during normalization.")
            if name in infos_by_name:
                raise WheelCheckError(f"Wheel has duplicate ZIP member {name!r}.")
            windows_key = _windows_extraction_collision_key(name)
            colliding_name = windows_extraction_names.get(windows_key)
            if colliding_name is not None:
                raise WheelCheckError(
                    "Wheel members collide at the same case-insensitive Windows "
                    f"extraction path: {colliding_name!r} and {name!r}."
                )
            _assert_no_wheel_scheme_relocation(name)
            infos_by_name[name] = info
            windows_extraction_names[windows_key] = name

        manifest_info = infos_by_name.get(RESOURCE_MANIFEST_MEMBER)
        if manifest_info is None:
            raise WheelCheckError(
                f"Wheel has no resource manifest at {RESOURCE_MANIFEST_MEMBER!r}."
            )

        canonical_manifest_path = resource_root / "resource-manifest.json"
        if canonical_manifest_path.is_symlink():
            raise WheelCheckError("Canonical resource manifest must not be a symlink.")
        try:
            canonical_manifest_bytes = canonical_manifest_path.read_bytes()
        except OSError as exc:
            raise WheelCheckError("Canonical resource manifest could not be read.") from exc
        manifest_bytes = _read_zip_member_bytes(
            archive,
            manifest_info,
            expected_size=len(canonical_manifest_bytes),
            label="Resource manifest",
        )
        manifest = _parse_resource_manifest(manifest_bytes)
        rows = _validated_resource_rows(manifest)
        if manifest_bytes != canonical_manifest_bytes:
            raise WheelCheckError(
                "Wheel resource manifest bytes differ from the canonical committed manifest."
            )

        expected_resource_names = {
            f"{RESOURCE_PREFIX}{row['packaged']}" for row in rows
        }
        actual_resource_names = {
            name
            for name in infos_by_name
            if name.startswith(RESOURCE_PREFIX)
            and name not in {RESOURCE_MANIFEST_MEMBER, RESOURCE_PACKAGE_INIT_MEMBER}
        }
        if actual_resource_names != expected_resource_names:
            missing = len(expected_resource_names - actual_resource_names)
            unexpected = len(actual_resource_names - expected_resource_names)
            raise WheelCheckError(
                "Wheel resource set does not match the manifest "
                f"(missing={missing}, unexpected={unexpected})."
            )

        verified_resource_count = 0
        verified_resource_bytes = 0
        for row in rows:
            member_name = f"{RESOURCE_PREFIX}{row['packaged']}"
            verified_resource_bytes += _verify_resource_member(
                archive,
                infos_by_name[member_name],
                row,
                resource_root=resource_root,
            )
            verified_resource_count += 1

        return {
            "manifested_resource_count": len(rows),
            "verified_resource_count": verified_resource_count,
            "verified_resource_bytes": verified_resource_bytes,
            "wheel_file_count": len(infos),
        }


def assert_wheel_resources(wheel: Path) -> dict[str, int]:
    """Verify wheel resource integrity and normalize all low-level failures."""

    try:
        return _assert_wheel_resources(wheel)
    except WheelCheckError:
        raise
    except Exception as exc:
        raise WheelCheckError("Wheel resource integrity check failed.") from exc


def _parse_entrypoint_json_object(text: str, *, label: str) -> dict[str, Any]:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise WheelCheckError(f"{label} contains duplicate JSON key {key!r}.")
            value[key] = item
        return value

    def reject_nonstandard_constant(value: str) -> None:
        raise WheelCheckError(
            f"{label} contains non-standard JSON numeric constant {value!r}."
        )

    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonstandard_constant,
        )
    except json.JSONDecodeError as exc:
        raise WheelCheckError(f"{label} did not return valid JSON: {exc}.") from exc
    if not isinstance(value, dict):
        raise WheelCheckError(f"{label} did not return a JSON object.")
    return value


def _run_installed_entrypoint(
    command: list[str],
    *,
    cwd: Path,
    label: str,
    input_text: str | None = None,
) -> str:
    deadline = time.monotonic() + ENTRYPOINT_TIMEOUT_SECONDS
    environment = dict(os.environ)
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8:strict"
    environment["PYTHONUTF8"] = "1"
    input_bytes = (
        input_text.encode("utf-8")
        if input_text is not None
        else None
    )
    process_options: dict[str, Any] = {}
    if os.name == "nt":
        process_options["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | WINDOWS_CREATE_SUSPENDED
        )
    else:
        process_options["start_new_session"] = True
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=(
                subprocess.PIPE
                if input_bytes is not None
                else subprocess.DEVNULL
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            **process_options,
        )
    except OSError as exc:
        raise WheelCheckError(f"{label} could not complete: {exc}.") from exc
    windows_job = _assign_windows_kill_on_close_job(process)
    if os.name == "nt" and windows_job is None:
        _terminate_installed_process_tree(process)
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        if process.stdin is not None:
            process.stdin.close()
        assert process.stdout is not None
        assert process.stderr is not None
        process.stdout.close()
        process.stderr.close()
        raise WheelCheckError(
            f"{label} could not establish descendant containment."
        )
    if os.name == "nt" and not _resume_windows_process(process):
        _close_windows_job(windows_job)
        windows_job = None
        _terminate_installed_process_tree(process)
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        if process.stdin is not None:
            process.stdin.close()
        assert process.stdout is not None
        assert process.stderr is not None
        process.stdout.close()
        process.stderr.close()
        raise WheelCheckError(
            f"{label} could not start inside descendant containment."
        )

    assert process.stdout is not None
    assert process.stderr is not None
    stream_results: dict[str, dict[str, Any]] = {
        "stdout": {},
        "stderr": {},
    }

    def read_bounded(
        name: str,
        stream: Any,
    ) -> None:
        chunks: list[bytes] = []
        total = 0
        try:
            while True:
                chunk = stream.read(ENTRYPOINT_READ_CHUNK_BYTES)
                if not chunk:
                    break
                remaining = ENTRYPOINT_OUTPUT_LIMIT_BYTES - total
                if len(chunk) > remaining:
                    if remaining > 0:
                        chunks.append(chunk[:remaining])
                    stream_results[name]["overflow"] = True
                    try:
                        process.kill()
                    except OSError:
                        pass
                    break
                chunks.append(chunk)
                total += len(chunk)
        except BaseException as exc:  # pragma: no cover - OS pipe failure
            stream_results[name]["error"] = exc
            try:
                process.kill()
            except OSError:
                pass
        finally:
            stream_results[name]["bytes"] = b"".join(chunks)
            stream.close()

    readers = [
        threading.Thread(
            target=read_bounded,
            args=("stdout", process.stdout),
            daemon=True,
        ),
        threading.Thread(
            target=read_bounded,
            args=("stderr", process.stderr),
            daemon=True,
        ),
    ]
    for reader in readers:
        reader.start()

    if input_bytes is not None:
        assert process.stdin is not None
        try:
            process.stdin.write(input_bytes)
            process.stdin.flush()
        except BrokenPipeError:
            pass
        finally:
            try:
                process.stdin.close()
            except BrokenPipeError:
                pass

    timed_out = False
    windows_job_closed = True
    try:
        returncode = process.wait(
            timeout=max(0.0, deadline - time.monotonic()),
        )
    except subprocess.TimeoutExpired:
        timed_out = True
        windows_job_closed = _close_windows_job(windows_job)
        windows_job = None
        _terminate_installed_process_tree(process)
        try:
            returncode = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            returncode = -1
    active_descendant_processes = (
        _windows_job_active_processes(windows_job)
    )
    windows_job_closed = (
        _close_windows_job(windows_job) and windows_job_closed
    )
    windows_job = None
    posix_descendants_active = (
        _posix_process_group_has_descendants(process)
    )
    if posix_descendants_active:
        _terminate_installed_process_tree(process)

    overflowed = any(
        result.get("overflow")
        for result in stream_results.values()
    )
    if overflowed:
        _terminate_installed_process_tree(process)
    reader_deadline = (
        min(deadline, time.monotonic() + 1)
        if overflowed
        else deadline
    )
    for reader in readers:
        reader.join(
            timeout=max(0.0, reader_deadline - time.monotonic())
        )
    readers_still_running = any(reader.is_alive() for reader in readers)
    overflowed = any(
        result.get("overflow")
        for result in stream_results.values()
    )
    if readers_still_running:
        _terminate_installed_process_tree(process)
    if overflowed:
        _terminate_installed_process_tree(process)

    if timed_out or readers_still_running:
        raise WheelCheckError(f"{label} exceeded the execution timeout.")
    if os.name == "nt" and not windows_job_closed:
        raise WheelCheckError(
            f"{label} descendant containment could not close safely."
        )
    if (
        active_descendant_processes is not None
        and active_descendant_processes > 0
    ):
        raise WheelCheckError(
            f"{label} left descendant processes running."
        )
    if os.name == "nt" and active_descendant_processes is None:
        raise WheelCheckError(
            f"{label} descendant state could not be verified."
        )
    if posix_descendants_active:
        raise WheelCheckError(
            f"{label} left descendant processes running."
        )
    if overflowed:
        raise WheelCheckError(
            f"{label} exceeded the bounded output limit."
        )
    if any(
        result.get("error") is not None
        for result in stream_results.values()
    ):
        raise WheelCheckError(f"{label} output could not be read safely.")

    stdout_bytes = stream_results["stdout"].get("bytes", b"")
    stderr_bytes = stream_results["stderr"].get("bytes", b"")
    try:
        stdout = stdout_bytes.decode("utf-8")
        stderr = stderr_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WheelCheckError(
            f"{label} output was not valid UTF-8."
        ) from exc
    if returncode != 0:
        raise WheelCheckError(
            f"{label} failed with a nonzero exit status."
        )
    if stderr != "":
        raise WheelCheckError(f"{label} wrote to stderr.")
    return stdout


def _terminate_installed_process_tree(
    process: subprocess.Popen[bytes],
) -> None:
    """Best-effort tree termination without extending the caller's deadline."""

    if os.name == "nt":
        try:
            subprocess.run(
                [
                    "taskkill.exe",
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    try:
        process.kill()
    except OSError:
        pass


def _assign_windows_kill_on_close_job(
    process: subprocess.Popen[bytes],
) -> Any | None:
    """Put a Windows probe and its descendants in a kill-on-close job."""

    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class JobObjectBasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class JobObjectExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            (
                "BasicLimitInformation",
                JobObjectBasicLimitInformation,
            ),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_job = kernel32.CreateJobObjectW
    create_job.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    create_job.restype = wintypes.HANDLE
    set_job_information = kernel32.SetInformationJobObject
    set_job_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    set_job_information.restype = wintypes.BOOL
    assign_process = kernel32.AssignProcessToJobObject
    assign_process.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    assign_process.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    job = create_job(None, None)
    if not job:
        return None
    information = JobObjectExtendedLimitInformation()
    information.BasicLimitInformation.LimitFlags = 0x00002000
    if not set_job_information(
        job,
        9,
        ctypes.byref(information),
        ctypes.sizeof(information),
    ):
        close_handle(job)
        return None
    process_handle = wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
    if not assign_process(job, process_handle):
        close_handle(job)
        return None
    return job


def _resume_windows_process(process: subprocess.Popen[bytes]) -> bool:
    """Resume the one main thread after fail-closed Job Object assignment."""

    if os.name != "nt":
        return True
    import ctypes
    from ctypes import wintypes

    class ThreadEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_snapshot = kernel32.CreateToolhelp32Snapshot
    create_snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    create_snapshot.restype = wintypes.HANDLE
    thread_first = kernel32.Thread32First
    thread_first.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ThreadEntry32),
    ]
    thread_first.restype = wintypes.BOOL
    thread_next = kernel32.Thread32Next
    thread_next.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ThreadEntry32),
    ]
    thread_next.restype = wintypes.BOOL
    open_thread = kernel32.OpenThread
    open_thread.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    open_thread.restype = wintypes.HANDLE
    resume_thread = kernel32.ResumeThread
    resume_thread.argtypes = [wintypes.HANDLE]
    resume_thread.restype = wintypes.DWORD
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    snapshot = create_snapshot(0x00000004, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return False
    try:
        entry = ThreadEntry32()
        entry.dwSize = ctypes.sizeof(entry)
        found = bool(thread_first(snapshot, ctypes.byref(entry)))
        while found:
            if int(entry.th32OwnerProcessID) == process.pid:
                thread = open_thread(0x0002, False, entry.th32ThreadID)
                if not thread:
                    return False
                try:
                    return resume_thread(thread) != 0xFFFFFFFF
                finally:
                    close_handle(thread)
            found = bool(thread_next(snapshot, ctypes.byref(entry)))
    finally:
        close_handle(snapshot)
    return False


def _close_windows_job(job: Any | None) -> bool:
    if os.name != "nt" or job is None:
        return True
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL(
        "kernel32",
        use_last_error=True,
    )
    terminate_job = kernel32.TerminateJobObject
    terminate_job.argtypes = [wintypes.HANDLE, wintypes.UINT]
    terminate_job.restype = wintypes.BOOL
    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait_for_single_object.restype = wintypes.DWORD
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    terminated = bool(terminate_job(job, 1))
    wait_result = (
        wait_for_single_object(
            job,
            WINDOWS_JOB_TERMINATION_TIMEOUT_MILLISECONDS,
        )
        if terminated
        else 0xFFFFFFFF
    )
    closed = bool(close_handle(job))
    return terminated and wait_result == 0 and closed


def _windows_job_active_processes(job: Any | None) -> int | None:
    if os.name != "nt" or job is None:
        return None
    import ctypes
    from ctypes import wintypes

    class JobObjectBasicAccountingInformation(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_longlong),
            ("TotalKernelTime", ctypes.c_longlong),
            ("ThisPeriodTotalUserTime", ctypes.c_longlong),
            ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    query_job = ctypes.WinDLL(
        "kernel32",
        use_last_error=True,
    ).QueryInformationJobObject
    query_job.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    query_job.restype = wintypes.BOOL
    information = JobObjectBasicAccountingInformation()
    returned = wintypes.DWORD()
    if not query_job(
        job,
        1,
        ctypes.byref(information),
        ctypes.sizeof(information),
        ctypes.byref(returned),
    ):
        return None
    return int(information.ActiveProcesses)


def _posix_process_group_has_descendants(
    process: subprocess.Popen[bytes],
) -> bool:
    if os.name == "nt":
        return False
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _probe_cli_version(
    entrypoint: Path,
    *,
    cwd: Path,
    entrypoint_name: str,
) -> dict[str, Any]:
    label = f"installed {entrypoint_name} version probe"
    stdout = _run_installed_entrypoint(
        [str(entrypoint), "version", "--format", "json"],
        cwd=cwd,
        label=label,
    )
    payload = _parse_entrypoint_json_object(stdout, label=label)
    if payload.get("ok") is not True:
        raise WheelCheckError(f"{label} did not report success.")
    version = payload.get("version")
    if not isinstance(version, str) or not version or version.strip() != version:
        raise WheelCheckError(f"{label} returned an invalid package version.")
    if payload.get("consistency_state") != "package_version_only":
        raise WheelCheckError(f"{label} did not use package-only mode.")
    return {
        "command": ["version", "--format", "json"],
        "exit_code": 0,
        "stderr_empty": True,
        "version": version,
        "consistency_state": "package_version_only",
        "result_json_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
    }


def _mcp_request_text() -> str:
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "wom-wheel-install-check",
                    "version": "0.3",
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    ]
    return "".join(
        json.dumps(
            message,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for message in messages
    )


def _mcp_response_by_id(
    stdout: str,
    *,
    label: str,
) -> dict[int, dict[str, Any]]:
    lines = stdout.splitlines()
    if len(lines) != 2 or any(not line.strip() for line in lines):
        raise WheelCheckError(
            f"{label} must return exactly initialize and tools/list responses."
        )
    responses: dict[int, dict[str, Any]] = {}
    for index, line in enumerate(lines, start=1):
        response = _parse_entrypoint_json_object(
            line,
            label=f"{label} response line {index}",
        )
        if response.get("jsonrpc") != "2.0":
            raise WheelCheckError(f"{label} returned an invalid JSON-RPC version.")
        request_id = response.get("id")
        if type(request_id) is not int or request_id not in {1, 2}:
            raise WheelCheckError(f"{label} returned an unexpected response id.")
        if request_id in responses:
            raise WheelCheckError(f"{label} returned a duplicate response id.")
        if "error" in response:
            raise WheelCheckError(f"{label} returned a JSON-RPC error response.")
        if not isinstance(response.get("result"), dict):
            raise WheelCheckError(f"{label} response result must be an object.")
        responses[request_id] = response
    if set(responses) != {1, 2}:
        raise WheelCheckError(
            f"{label} did not return both initialize and tools/list responses."
        )
    return responses


def _canonical_mcp_inventory(
    tools: Any,
    *,
    label: str,
) -> tuple[bytes, int]:
    if not isinstance(tools, list):
        raise WheelCheckError(f"{label} tools/list result must contain a tools list.")
    if not tools:
        raise WheelCheckError(f"{label} tools/list result must not be empty.")
    inventory: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, tool in enumerate(tools):
        tool_label = f"{label} tools[{index}]"
        if not isinstance(tool, dict):
            raise WheelCheckError(f"{tool_label} must be an object.")
        name = tool.get("name")
        if not isinstance(name, str) or not name or name.strip() != name:
            raise WheelCheckError(f"{tool_label} name must be a non-empty string.")
        if name in names:
            raise WheelCheckError(f"{label} returned duplicate tool name {name!r}.")
        input_schema = tool.get("inputSchema")
        if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
            raise WheelCheckError(
                f"{tool_label} inputSchema must be an object JSON Schema."
            )
        names.add(name)
        inventory.append(tool)
    inventory.sort(key=lambda item: item["name"])
    try:
        canonical = json.dumps(
            inventory,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise WheelCheckError(
            f"{label} tool inventory is not canonical JSON data."
        ) from exc
    return canonical, len(inventory)


def _probe_mcp_server(
    entrypoint: Path,
    *,
    cwd: Path,
    entrypoint_name: str,
    expected_package_version: str,
) -> tuple[dict[str, Any], bytes]:
    label = f"installed {entrypoint_name} MCP probe"
    stdout = _run_installed_entrypoint(
        [str(entrypoint)],
        cwd=cwd,
        label=label,
        input_text=_mcp_request_text(),
    )
    responses = _mcp_response_by_id(stdout, label=label)
    initialize_result = responses[1]["result"]
    protocol_version = initialize_result.get("protocolVersion")
    if protocol_version != MCP_PROTOCOL_VERSION:
        raise WheelCheckError(
            f"{label} protocol version did not match the requested protocol."
        )
    capabilities = initialize_result.get("capabilities")
    if not isinstance(capabilities, dict):
        raise WheelCheckError(f"{label} capabilities must be an object.")
    tools_capability = capabilities.get("tools")
    if not isinstance(tools_capability, dict):
        raise WheelCheckError(
            f"{label} must advertise the tools capability."
        )
    list_changed = tools_capability.get("listChanged")
    if (
        list_changed is not None
        and type(list_changed) is not bool
    ):
        raise WheelCheckError(
            f"{label} tools listChanged capability must be Boolean."
        )
    server_info = initialize_result.get("serverInfo")
    if not isinstance(server_info, dict):
        raise WheelCheckError(f"{label} serverInfo must be an object.")
    server_name = server_info.get("name")
    server_version = server_info.get("version")
    if server_name != MCP_SERVER_NAME:
        raise WheelCheckError(
            f"{label} returned an unexpected server name."
        )
    if server_version != expected_package_version:
        raise WheelCheckError(
            f"{label} server version did not match the installed package version."
        )

    tools_result = responses[2]["result"]
    if tools_result.get("nextCursor") is not None:
        raise WheelCheckError(
            f"{label} returned a paginated tool inventory."
        )
    canonical_inventory, tool_count = _canonical_mcp_inventory(
        tools_result.get("tools"),
        label=label,
    )
    inventory_sha256 = hashlib.sha256(canonical_inventory).hexdigest()
    return (
        {
            "request_sequence": [
                "initialize",
                "notifications/initialized",
                "tools/list",
                "EOF",
            ],
            "exit_code": 0,
            "stderr_empty": True,
            "protocol_version": protocol_version,
            "server_name": server_name,
            "server_version": server_version,
            "tool_count": tool_count,
            "pagination_complete": True,
            "canonical_inventory_bytes": len(canonical_inventory),
            "canonical_inventory_sha256": inventory_sha256,
        },
        canonical_inventory,
    )


def _check_installed_entrypoints(
    scripts: Path,
    *,
    cwd: Path,
) -> tuple[str, list[str], dict[str, Any]]:
    required_entrypoints = ["archive", "archive-mcp", "wom", "wom-mcp"]
    installed = {
        name: executable(scripts, name)
        for name in required_entrypoints
    }
    missing_entrypoints = [
        name for name, path in installed.items() if not path.is_file()
    ]
    if missing_entrypoints:
        raise WheelCheckError(
            "Installed wheel omitted entrypoints: " + ", ".join(missing_entrypoints)
        )

    checked: list[str] = []
    cli_evidence: dict[str, dict[str, Any]] = {}
    for name in ("archive", "wom"):
        cli_evidence[name] = _probe_cli_version(
            installed[name],
            cwd=cwd,
            entrypoint_name=name,
        )
        checked.append(name)
    cli_versions = {item["version"] for item in cli_evidence.values()}
    if len(cli_versions) != 1:
        raise WheelCheckError(
            "Installed archive and wom package versions did not agree."
        )
    package_version = next(iter(cli_versions))

    mcp_evidence: dict[str, dict[str, Any]] = {}
    mcp_inventories: dict[str, bytes] = {}
    for name in ("archive-mcp", "wom-mcp"):
        evidence, canonical_inventory = _probe_mcp_server(
            installed[name],
            cwd=cwd,
            entrypoint_name=name,
            expected_package_version=package_version,
        )
        mcp_evidence[name] = evidence
        mcp_inventories[name] = canonical_inventory
        checked.append(name)

    if (
        mcp_evidence["archive-mcp"]["server_name"]
        != mcp_evidence["wom-mcp"]["server_name"]
    ):
        raise WheelCheckError(
            "Installed archive-mcp and wom-mcp server names did not agree."
        )
    if mcp_inventories["archive-mcp"] != mcp_inventories["wom-mcp"]:
        raise WheelCheckError(
            "Installed archive-mcp and wom-mcp canonical tool inventories "
            "were not byte-identical."
        )
    inventory_sha256 = hashlib.sha256(
        mcp_inventories["archive-mcp"]
    ).hexdigest()
    return (
        package_version,
        checked,
        {
            "cli_versions": cli_evidence,
            "mcp_servers": mcp_evidence,
            "agreement": {
                "package_version": package_version,
                "cli_versions_match": True,
                "mcp_protocol_versions_match": True,
                "mcp_server_names_match": True,
                "mcp_server_versions_match_package": True,
                "mcp_canonical_inventories_byte_identical": True,
                "mcp_canonical_inventory_sha256": inventory_sha256,
            },
        },
    )


def _wheel_install_success_result(
    *,
    package_version: str,
    wheel_counts: dict[str, int],
    entrypoints_checked: list[str],
    entrypoint_evidence: dict[str, Any],
    wheel_filename: str,
    wheel_sha256: str,
    artifact_preserved: bool,
) -> dict[str, Any]:
    """Assemble the versioned public success contract in one tested boundary."""

    return {
        "ok": True,
        "schema": WHEEL_INSTALL_CHECK_SCHEMA,
        "package_version": package_version,
        **wheel_counts,
        "entrypoints_checked": entrypoints_checked,
        "entrypoint_evidence": entrypoint_evidence,
        "runtime_skill_lifecycle": "passed",
        "onboarding_preview": "passed",
        "onboarding_write": "fixed_closed",
        "onboarding_write_reason_code": (
            "compound_exact_human_approval_binding_required"
        ),
        "strict_doctor": "passed_on_checked_in_fake_archive",
        "wheel_filename": wheel_filename,
        "wheel_sha256": wheel_sha256,
        "wheel_artifact_preserved": artifact_preserved,
        "temporary_environment_removed_on_exit": True,
    }


def check_wheel(output_dir: Path | None = None) -> dict[str, Any]:
    run(
        [sys.executable, str(SYNC_TOOL), "--check"],
        cwd=KIT_ROOT,
        label="package resource drift check",
    )
    with tempfile.TemporaryDirectory(prefix="wom-wheel-smoke-") as tmp:
        temp_root = Path(tmp)
        source_copy = temp_root / "wom-kit"
        shutil.copytree(KIT_ROOT, source_copy, ignore=ignored_copy_names)
        wheel_dir = temp_root / "dist"
        wheel_dir.mkdir()
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--wheel-dir",
                str(wheel_dir),
                str(source_copy),
            ],
            cwd=temp_root,
            label="wheel build",
        )
        wheels = list(wheel_dir.glob("*.whl"))
        if len(wheels) != 1:
            raise WheelCheckError(f"Expected one wheel, found {len(wheels)}.")
        wheel = wheels[0]
        wheel_counts = assert_wheel_resources(wheel)

        venv = temp_root / "venv"
        run([sys.executable, "-m", "venv", str(venv)], cwd=temp_root, label="venv creation")
        scripts = scripts_directory(venv)
        python = executable(scripts, "python")
        archive = executable(scripts, "archive")
        run(
            [str(python), "-m", "pip", "install", str(wheel)],
            cwd=temp_root,
            label="wheel install",
        )
        _check_installed_runtime_dependencies(python, cwd=temp_root)
        package_version, entrypoints_checked, entrypoint_evidence = (
            _check_installed_entrypoints(
                scripts,
                cwd=temp_root,
            )
        )

        skills_root = temp_root / "host-skills"
        skill_target = skills_root / "wom-archive"
        common_skill_target = [
            str(archive),
            "--host",
            "custom",
            "--scope",
            "custom",
            "--skills-root",
            str(skills_root),
            "--format",
            "json",
        ]
        skill_preview = run(
            [
                str(archive),
                "runtime-skill-install",
                *common_skill_target[1:],
                "--dry-run",
            ],
            cwd=temp_root,
            label="installed runtime skill preview",
            parse_json=True,
            require_empty_stderr=True,
        )
        skill_plan_sha256 = skill_preview.get("operation_plan_sha256")
        skill_preview_target = (
            skill_preview.get("target") if isinstance(skill_preview.get("target"), dict) else {}
        )
        if (
            not skill_preview.get("ok")
            or skill_preview.get("status") != "ready_to_install"
            or not isinstance(skill_plan_sha256, str)
            or skills_root.exists()
            or skill_preview_target.get("path") is not None
            or skill_preview_target.get("path_redacted") is not True
            or str(temp_root) in json.dumps(skill_preview)
        ):
            raise WheelCheckError("Installed runtime skill preview was not safely ready.")
        blocked_skill_install = run(
            [
                str(archive),
                "runtime-skill-install",
                *common_skill_target[1:],
                "--approve",
                "--reviewed-by",
                "person:wheel-smoke",
                "--expected-plan-sha256",
                skill_plan_sha256,
            ],
            cwd=temp_root,
            label="installed runtime skill write",
            parse_json=True,
            expected_returncode=1,
            require_empty_stderr=True,
        )
        if blocked_skill_install != {
            "ok": False,
            "state": "blocked",
            "lifecycle_action": "runtime_skill_install",
            "reason_codes": [
                "compound_exact_human_approval_binding_required"
            ],
            "files_written": [],
            "private_values_echoed": False,
        } or skills_root.exists() or skill_target.exists():
            raise WheelCheckError(
                "Installed runtime skill write was not fixed-closed without effects."
            )
        skill_status = run(
            [str(archive), "runtime-skill-status", *common_skill_target[1:]],
            cwd=temp_root,
            label="installed runtime skill status",
            parse_json=True,
            require_empty_stderr=True,
        )
        if skill_status.get("status") != "absent":
            raise WheelCheckError("Installed runtime skill did not remain absent.")
        uninstall_preview = run(
            [
                str(archive),
                "runtime-skill-uninstall",
                *common_skill_target[1:],
                "--dry-run",
            ],
            cwd=temp_root,
            label="installed runtime skill uninstall preview",
            parse_json=True,
            require_empty_stderr=True,
        )
        uninstall_plan_sha256 = uninstall_preview.get("operation_plan_sha256")
        if (
            uninstall_preview.get("status") != "already_absent"
            or not isinstance(uninstall_plan_sha256, str)
            or SHA256_RE.fullmatch(uninstall_plan_sha256) is None
        ):
            raise WheelCheckError(
                "Installed runtime skill uninstall preview was not safely already absent."
            )
        blocked_skill_uninstall = run(
            [
                str(archive),
                "runtime-skill-uninstall",
                *common_skill_target[1:],
                "--approve",
                "--reviewed-by",
                "person:wheel-smoke",
                "--expected-plan-sha256",
                uninstall_plan_sha256,
            ],
            cwd=temp_root,
            label="installed runtime skill uninstall",
            parse_json=True,
            expected_returncode=1,
            require_empty_stderr=True,
        )
        if blocked_skill_uninstall != {
            "ok": False,
            "state": "blocked",
            "lifecycle_action": "runtime_skill_uninstall",
            "reason_codes": [
                "compound_exact_human_approval_binding_required"
            ],
            "files_written": [],
            "private_values_echoed": False,
        } or skills_root.exists() or skill_target.exists():
            raise WheelCheckError(
                "Installed runtime skill uninstall was not fixed-closed without effects."
            )

        target = temp_root / "archive"
        common_onboard = [
            str(archive),
            "onboard",
            "--target-root",
            str(target),
            "--type",
            "personal",
            "--archive-id",
            "archive:personal:wheel-smoke",
            "--principal-id",
            "person:wheel-smoke",
            "--format",
            "json",
        ]
        preview = run(
            [*common_onboard, "--dry-run"],
            cwd=temp_root,
            label="installed onboarding preview",
            parse_json=True,
            require_empty_stderr=True,
        )
        if not preview.get("ok") or not preview.get("dry_run"):
            raise WheelCheckError("Installed onboarding preview was not ready.")
        blocked_write = run(
            [*common_onboard, "--approve"],
            cwd=temp_root,
            label="installed onboarding fixed-close probe",
            parse_json=True,
            expected_returncode=1,
            require_empty_stderr=True,
        )
        if blocked_write != {
            "ok": False,
            "state": "blocked",
            "lifecycle_action": "onboard",
            "reason_codes": [
                "compound_exact_human_approval_binding_required"
            ],
            "files_written": [],
            "private_values_echoed": False,
        } or target.exists():
            raise WheelCheckError(
                "Installed onboarding write was not fixed-closed without effects."
            )

        doctor_fixture = temp_root / "checked-in-fake-archive"
        shutil.copytree(
            source_copy / "examples" / "fake-life-archive",
            doctor_fixture,
        )

        doctor = run(
            [
                str(archive),
                "doctor",
                str(doctor_fixture),
                "--strict",
                "--summary",
                "--format",
                "json",
            ],
            cwd=temp_root,
            label="installed strict doctor",
            parse_json=True,
            require_empty_stderr=True,
        )
        if not doctor.get("ok"):
            raise WheelCheckError(
                "Installed strict Doctor did not pass on the checked-in fake archive."
            )

        wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
        artifact_preserved = False
        if output_dir is not None:
            destination_dir = output_dir.expanduser()
            if destination_dir.exists() and destination_dir.is_symlink():
                raise WheelCheckError("Wheel output directory must not be a symlink.")
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination_dir = destination_dir.resolve()
            destination = destination_dir / wheel.name
            if destination.exists():
                raise WheelCheckError(f"Wheel output already exists: {wheel.name}")
            shutil.copy2(wheel, destination)
            artifact_preserved = True

        return _wheel_install_success_result(
            package_version=package_version,
            wheel_counts=wheel_counts,
            entrypoints_checked=entrypoints_checked,
            entrypoint_evidence=entrypoint_evidence,
            wheel_filename=wheel.name,
            wheel_sha256=wheel_sha256,
            artifact_preserved=artifact_preserved,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument(
        "--wheel-output-dir",
        type=Path,
        help="Preserve the verified wheel in this directory; refuses overwrite.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = check_wheel(args.wheel_output_dir)
    except (OSError, WheelCheckError, subprocess.SubprocessError) as exc:
        if args.format == "json":
            print(
                json.dumps(
                    {
                        "ok": False,
                        "schema": WHEEL_INSTALL_CHECK_SCHEMA,
                        "error": str(exc),
                    },
                    indent=2,
                )
            )
        else:
            print(f"WOM-kit wheel install check failed: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(
            "WOM-kit wheel install check passed: "
            f"v{result['package_version']}, "
            f"manifested_resource_count={result['manifested_resource_count']}, "
            f"verified_resource_count={result['verified_resource_count']}, "
            f"verified_resource_bytes={result['verified_resource_bytes']}, "
            f"wheel_file_count={result['wheel_file_count']}, "
            f"runtime skill lifecycle, onboarding preview/fixed-close, "
            f"and strict Doctor fixture green, "
            f"sha256={result['wheel_sha256']}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
