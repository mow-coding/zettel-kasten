from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from wom_kit import __version__


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RESOURCE_ROOT = KIT / "src" / "wom_kit" / "_resources"
MANIFEST_PATH = RESOURCE_ROOT / "resource-manifest.json"
RELEASE_PATH = KIT / "docs" / "releases" / "v0.4.3.md"
PACKAGED_RELEASE_PATH = RESOURCE_ROOT / "release-notes" / "v0.4.3.md"
WHEEL_URL = (
    "https://github.com/mow-coding/zettel-kasten/releases/download/"
    "v0.4.3/wom_kit-0.4.3-py3-none-any.whl"
)


class V0403ReleaseDocsTests(unittest.TestCase):
    def test_same_account_client_scope_is_explicit(self) -> None:
        surfaces = (
            KIT / "docs" / "python-tool-install.md",
            KIT / "docs" / "python-tool-install.ko.md",
            KIT / "docs" / "version-truth-source.md",
            RELEASE_PATH,
        )
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in surfaces
        )
        for token in (
            "archive --version",
            "archive version <project-or-archive-root> --format json",
            "PATH",
            "per-folder sandbox",
            "temporary virtual environment",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_version_sources_and_wheel_contract_are_synchronized(self) -> None:
        self.assertEqual(__version__, "0.4.3")
        self.assertIn(
            'version = "0.4.3"',
            (KIT / "pyproject.toml").read_text(encoding="utf-8"),
        )
        for version_file in (
            KIT / "src" / "wom_kit" / "__init__.py",
            ROOT / "wom_kit" / "__init__.py",
        ):
            with self.subTest(version_file=version_file):
                self.assertIn(
                    '__version__ = "0.4.3"',
                    version_file.read_text(encoding="utf-8"),
                )
        self.assertIn(
            'PACKAGE_VERSION = "0.4.3"',
            (KIT / "tests" / "test_wheel_install.py").read_text(encoding="utf-8"),
        )

    def test_current_release_and_resources_are_packaged_exactly(self) -> None:
        self.assertEqual(RELEASE_PATH.read_bytes(), PACKAGED_RELEASE_PATH.read_bytes())
        release_names = sorted(
            path.name
            for path in (RESOURCE_ROOT / "release-notes").glob("v*.md")
        )
        self.assertEqual(release_names, ["v0.4.3.md"])

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.4.3")
        self.assertEqual(manifest["file_count"], len(manifest["files"]))
        packaged_paths = [row["packaged"] for row in manifest["files"]]
        self.assertEqual(len(packaged_paths), len(set(packaged_paths)))
        self.assertIn("release-notes/v0.4.3.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.2.md", packaged_paths)
        for row in manifest["files"]:
            with self.subTest(packaged=row["packaged"]):
                source = KIT / row["source"]
                packaged = RESOURCE_ROOT / row["packaged"]
                source_bytes = source.read_bytes()
                self.assertEqual(source_bytes, packaged.read_bytes())
                self.assertEqual(row["bytes"], len(source_bytes))
                self.assertEqual(
                    row["sha256"], hashlib.sha256(source_bytes).hexdigest()
                )

    def test_release_defines_the_outcome_and_nonclaim_boundaries(self) -> None:
        documents = (
            RELEASE_PATH,
            ROOT / "README.md",
            ROOT / "README.ko.md",
            ROOT / "UPGRADE.md",
            ROOT / "UPGRADE.ko.md",
            KIT / "docs" / "exact-operation-manifest-v1.md",
            KIT / "docs" / "project-version-update.md",
        )
        combined = " ".join(
            " ".join(path.read_text(encoding="utf-8").split())
            for path in documents
        )
        for token in (
            WHEEL_URL,
            "ExactOperationManifest v1",
            "notion-source-properties",
            "unmapped_no_canonical_target",
            "Git",
            "non-force push",
            "remote ref",
            "project-version-update",
            "field-scoped revert",
            "independent",
            "native exact-human",
            "not by itself proof",
        ):
            with self.subTest(token=token):
                self.assertIn(token.casefold(), combined.casefold())

    def test_current_schemas_are_valid_and_exactly_packaged(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        for source in sorted((KIT / "schemas").glob("*.json")):
            with self.subTest(schema=source.name):
                schema = json.loads(source.read_text(encoding="utf-8"))
                Draft202012Validator.check_schema(schema)
                packaged = RESOURCE_ROOT / "schemas" / source.name
                self.assertEqual(source.read_bytes(), packaged.read_bytes())
                self.assertIn(f"schemas/{source.name}", packaged_paths)

    def test_release_note_links_are_github_release_safe(self) -> None:
        release = RELEASE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("](../", release)
        self.assertNotIn("](../../../", release)
        self.assertNotIn("C:\\Users\\", release)


if __name__ == "__main__":
    unittest.main()
