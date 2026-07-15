#!/usr/bin/env python3
"""Build and smoke-test a WOM-kit wheel in one clean temporary environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any
import zipfile


KIT_ROOT = Path(__file__).resolve().parents[1]
SYNC_TOOL = KIT_ROOT / "tools" / "sync_package_resources.py"


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


def assert_wheel_resources(wheel: Path) -> dict[str, int]:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        try:
            manifest_name = next(
                name for name in names if name.endswith("wom_kit/_resources/resource-manifest.json")
            )
        except StopIteration as exc:
            raise WheelCheckError("Wheel has no packaged resource manifest.") from exc
        manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
        expected = {
            f"wom_kit/_resources/{row['packaged']}"
            for row in manifest.get("files", [])
            if isinstance(row, dict) and isinstance(row.get("packaged"), str)
        }
        missing = sorted(expected - set(names))
        if missing:
            raise WheelCheckError(f"Wheel is missing {len(missing)} manifested resources.")
        required = {
            "wom_kit/_resources/templates/personal/archive.yml",
            "wom_kit/_resources/schemas/archive.schema.json",
            "wom_kit/_resources/zettel-kasten/types.yml",
        }
        if not required.issubset(names):
            raise WheelCheckError("Wheel is missing one or more required runtime resources.")
        return {
            "manifested_resource_count": len(expected),
            "wheel_file_count": len(names),
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
            f"v{result['package_version']}, {result['manifested_resource_count']} resources, "
            f"onboarding and strict Doctor green, sha256={result['wheel_sha256']}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
