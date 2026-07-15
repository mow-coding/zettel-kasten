#!/usr/bin/env python3
"""Synchronize public runtime resources into the installable WOM-kit package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Iterable


KIT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = KIT_ROOT / "src" / "wom_kit"
DESTINATION_ROOT = PACKAGE_ROOT / "_resources"
VERSION_FILE = PACKAGE_ROOT / "__init__.py"
GROUP_SOURCES = {
    "schemas": KIT_ROOT / "schemas",
    "templates": KIT_ROOT / "templates",
    "zettel-kasten": KIT_ROOT / "zettel-kasten",
}
MANIFEST_PATH = DESTINATION_ROOT / "resource-manifest.json"
VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def current_version() -> str:
    match = VERSION_RE.search(VERSION_FILE.read_text(encoding="utf-8"))
    if match is None:
        raise RuntimeError("Could not read WOM-kit version from package __init__.py.")
    return match.group(1)


def iter_source_rows() -> Iterable[tuple[str, Path, Path]]:
    for group, source_root in GROUP_SOURCES.items():
        for source_path in sorted(source_root.rglob("*")):
            if source_path.is_symlink():
                raise RuntimeError(f"Runtime resource must not be a symlink: {source_path}")
            if source_path.is_file():
                yield group, source_path, source_path.relative_to(source_root)

    version = current_version()
    release_note = KIT_ROOT / "docs" / "releases" / f"v{version}.md"
    if not release_note.is_file():
        raise RuntimeError(f"Current release note is missing: {release_note}")
    yield "release-notes", release_note, Path(release_note.name)


def expected_manifest() -> tuple[dict[str, object], dict[str, bytes]]:
    files: list[dict[str, object]] = []
    payloads: dict[str, bytes] = {}
    for group, source_path, relative in iter_source_rows():
        data = source_path.read_bytes()
        packaged_relative = (Path(group) / relative).as_posix()
        source_relative = source_path.relative_to(KIT_ROOT).as_posix()
        payloads[packaged_relative] = data
        files.append(
            {
                "source": source_relative,
                "packaged": packaged_relative,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
            }
        )
    manifest: dict[str, object] = {
        "schema": "wom-kit/package-resource-manifest/v0.1",
        "version": current_version(),
        "source_of_truth": "wom-kit source resource directories",
        "file_count": len(files),
        "files": files,
    }
    return manifest, payloads


def assert_safe_destination() -> None:
    package_root = PACKAGE_ROOT.resolve()
    destination = DESTINATION_ROOT.resolve()
    if destination == package_root or not destination.is_relative_to(package_root):
        raise RuntimeError(f"Unsafe package resource destination: {destination}")
    if DESTINATION_ROOT.is_symlink():
        raise RuntimeError("Package resource destination must not be a symlink.")


def sync_resources() -> dict[str, object]:
    assert_safe_destination()
    manifest, payloads = expected_manifest()
    DESTINATION_ROOT.mkdir(parents=True, exist_ok=True)
    for group in [*GROUP_SOURCES, "release-notes"]:
        destination = DESTINATION_ROOT / group
        if destination.is_symlink():
            raise RuntimeError(f"Package resource group must not be a symlink: {destination}")
        if destination.exists():
            shutil.rmtree(destination)
    for packaged_relative, data in payloads.items():
        destination = DESTINATION_ROOT / Path(packaged_relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def check_resources() -> tuple[bool, list[str], dict[str, object]]:
    manifest, payloads = expected_manifest()
    problems: list[str] = []
    try:
        actual_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        actual_manifest = None
        problems.append(f"resource manifest unreadable: {exc}")
    if actual_manifest != manifest:
        problems.append("resource manifest does not match source resources")

    expected_paths = set(payloads)
    actual_paths = {
        path.relative_to(DESTINATION_ROOT).as_posix()
        for path in DESTINATION_ROOT.rglob("*")
        if path.is_file()
        and path.name != "__init__.py"
        and path.name != MANIFEST_PATH.name
        and "__pycache__" not in path.parts
    }
    for missing in sorted(expected_paths - actual_paths):
        problems.append(f"packaged resource missing: {missing}")
    for unexpected in sorted(actual_paths - expected_paths):
        problems.append(f"unexpected packaged resource: {unexpected}")
    for relative in sorted(expected_paths & actual_paths):
        if (DESTINATION_ROOT / relative).read_bytes() != payloads[relative]:
            problems.append(f"packaged resource bytes differ: {relative}")
    return not problems, problems, manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check the committed package mirror without writing files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        ok, problems, manifest = check_resources()
        if ok:
            print(
                "WOM-kit package resources are synchronized: "
                f"{manifest['file_count']} files for v{manifest['version']}."
            )
            return 0
        for problem in problems:
            print(f"ERROR: {problem}", file=sys.stderr)
        return 1

    manifest = sync_resources()
    print(
        "Synchronized WOM-kit package resources: "
        f"{manifest['file_count']} files for v{manifest['version']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
