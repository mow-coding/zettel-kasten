"""Resolve WOM-kit runtime resources in source and installed layouts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_KIT_ROOT = Path(__file__).resolve().parents[2]
PACKAGED_RESOURCES_ROOT = PACKAGE_ROOT / "_resources"
RESOURCE_SOURCE_PATHS = {
    "schemas": Path("schemas"),
    "templates": Path("templates"),
    "zettel-kasten": Path("zettel-kasten"),
    "release-notes": Path("docs") / "releases",
}


def source_checkout_available() -> bool:
    """Return whether this import points into a complete WOM-kit checkout."""
    return (
        (SOURCE_KIT_ROOT / "pyproject.toml").is_file()
        and (SOURCE_KIT_ROOT / "templates").is_dir()
        and (SOURCE_KIT_ROOT / "schemas").is_dir()
    )


def runtime_resource_root(group: str) -> Path:
    """Return a checked-out resource root or its wheel-packaged mirror."""
    source_relative = RESOURCE_SOURCE_PATHS.get(group)
    if source_relative is None:
        raise ValueError(f"Unknown WOM-kit resource group: {group}")
    source_path = SOURCE_KIT_ROOT / source_relative
    if source_checkout_available() and source_path.is_dir():
        return source_path
    return PACKAGED_RESOURCES_ROOT / group


def runtime_release_note_path(version: str) -> Path:
    return runtime_resource_root("release-notes") / f"v{version}.md"


def packaged_resource_manifest() -> dict[str, Any]:
    path = PACKAGED_RESOURCES_ROOT / "resource-manifest.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
