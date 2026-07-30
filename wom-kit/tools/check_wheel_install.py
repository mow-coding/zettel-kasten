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
import shutil
import subprocess
import sys
import tempfile
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
) -> subprocess.CompletedProcess[str] | dict[str, Any]:
    environment = dict(os.environ)
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
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
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise WheelCheckError(f"{label} failed with exit {completed.returncode}: {detail}")
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
        entrypoint_names = ["archive", "archive-mcp", "wom", "wom-mcp"]
        run(
            [str(python), "-m", "pip", "install", str(wheel)],
            cwd=temp_root,
            label="wheel install",
        )
        missing_entrypoints = [
            name for name in entrypoint_names if not executable(scripts, name).is_file()
        ]
        if missing_entrypoints:
            raise WheelCheckError(
                "Installed wheel omitted entrypoints: " + ", ".join(missing_entrypoints)
            )
        version = run(
            [str(archive), "version", "--format", "json"],
            cwd=temp_root,
            label="installed version probe",
            parse_json=True,
        )
        if version.get("consistency_state") != "package_version_only":
            raise WheelCheckError("Installed version probe did not use package-only mode.")

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
        skill_applied = run(
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
        )
        if not skill_applied.get("ok") or skill_applied.get("status") != "installed":
            raise WheelCheckError("Installed runtime skill write was not successful.")
        skill_status = run(
            [str(archive), "runtime-skill-status", *common_skill_target[1:]],
            cwd=temp_root,
            label="installed runtime skill status",
            parse_json=True,
        )
        if skill_status.get("status") != "managed_current":
            raise WheelCheckError("Installed runtime skill did not verify as managed_current.")
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
        )
        uninstall_plan_sha256 = uninstall_preview.get("operation_plan_sha256")
        if (
            uninstall_preview.get("status") != "ready_to_uninstall"
            or not isinstance(uninstall_plan_sha256, str)
        ):
            raise WheelCheckError("Installed runtime skill uninstall preview was not ready.")
        uninstalled = run(
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
        )
        if not uninstalled.get("ok") or uninstalled.get("status") != "uninstalled":
            raise WheelCheckError("Installed runtime skill uninstall was not successful.")
        if skill_target.exists():
            raise WheelCheckError("Installed runtime skill target remained after uninstall.")

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
        )
        if not preview.get("ok") or not preview.get("dry_run"):
            raise WheelCheckError("Installed onboarding preview was not ready.")
        applied = run(
            [*common_onboard, "--approve"],
            cwd=temp_root,
            label="installed onboarding write",
            parse_json=True,
        )
        if not applied.get("ok"):
            raise WheelCheckError("Installed onboarding write was not successful.")

        required_archive_files = [
            "archive.yml",
            "archive-identity.yml",
            "AGENTS.md",
            "zettel-kasten/types.yml",
            "zettel-kasten/zettel-rules.yml",
        ]
        missing_archive_files = [
            relative for relative in required_archive_files if not (target / relative).is_file()
        ]
        if missing_archive_files:
            raise WheelCheckError(
                "Installed onboarding omitted required files: " + ", ".join(missing_archive_files)
            )

        doctor = run(
            [
                str(archive),
                "doctor",
                str(target),
                "--strict",
                "--summary",
                "--format",
                "json",
            ],
            cwd=temp_root,
            label="installed strict doctor",
            parse_json=True,
        )
        if not doctor.get("ok"):
            raise WheelCheckError("Installed strict Doctor did not pass on the new archive.")

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

        return {
            "ok": True,
            "schema": "wom-kit/wheel-install-check/v0.1",
            "package_version": version.get("version"),
            **wheel_counts,
            "entrypoints_checked": entrypoint_names,
            "runtime_skill_lifecycle": "passed",
            "onboarding_preview": "passed",
            "onboarding_write": "passed",
            "strict_doctor": "passed",
            "wheel_filename": wheel.name,
            "wheel_sha256": wheel_sha256,
            "wheel_artifact_preserved": artifact_preserved,
            "temporary_environment_removed_on_exit": True,
        }


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
                        "schema": "wom-kit/wheel-install-check/v0.1",
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
            f"runtime skill lifecycle, onboarding, and strict Doctor green, "
            f"sha256={result['wheel_sha256']}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
