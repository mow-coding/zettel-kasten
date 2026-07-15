from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import __version__
from wom_kit import resource_paths


KIT_ROOT = Path(__file__).resolve().parents[1]
SYNC_TOOL = KIT_ROOT / "tools" / "sync_package_resources.py"
PACKAGED_ROOT = KIT_ROOT / "src" / "wom_kit" / "_resources"


class PackageResourceTests(unittest.TestCase):
    def test_committed_package_resources_match_source_truth(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SYNC_TOOL), "--check"],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("package resources are synchronized", completed.stdout)

    def test_package_resource_manifest_has_exact_bytes_and_current_release(self) -> None:
        manifest_path = PACKAGED_ROOT / "resource-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rows = manifest["files"]
        self.assertEqual(manifest["schema"], "wom-kit/package-resource-manifest/v0.1")
        self.assertEqual(manifest["version"], __version__)
        self.assertEqual(manifest["file_count"], len(rows))
        self.assertGreaterEqual(len(rows), 84)
        packaged_paths = {row["packaged"] for row in rows}
        self.assertIn(f"release-notes/v{__version__}.md", packaged_paths)
        self.assertIn("templates/personal/archive.yml", packaged_paths)
        self.assertIn("schemas/archive.schema.json", packaged_paths)
        self.assertIn("zettel-kasten/types.yml", packaged_paths)
        for row in rows:
            with self.subTest(path=row["packaged"]):
                data = (PACKAGED_ROOT / row["packaged"]).read_bytes()
                self.assertEqual(len(data), row["bytes"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), row["sha256"])

    def test_resource_resolver_prefers_source_checkout(self) -> None:
        self.assertTrue(resource_paths.source_checkout_available())
        self.assertEqual(
            resource_paths.runtime_resource_root("templates"),
            KIT_ROOT / "templates",
        )
        self.assertEqual(
            resource_paths.runtime_release_note_path(__version__),
            KIT_ROOT / "docs" / "releases" / f"v{__version__}.md",
        )

    def test_resource_resolver_falls_back_to_packaged_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_source = Path(tmp) / "missing-source-checkout"
            with patch.object(resource_paths, "SOURCE_KIT_ROOT", missing_source):
                self.assertFalse(resource_paths.source_checkout_available())
                self.assertEqual(
                    resource_paths.runtime_resource_root("schemas"),
                    PACKAGED_ROOT / "schemas",
                )
                self.assertTrue(
                    (resource_paths.runtime_resource_root("templates") / "personal" / "archive.yml").is_file()
                )
                self.assertTrue(
                    (resource_paths.runtime_resource_root("zettel-kasten") / "types.yml").is_file()
                )
                self.assertTrue(resource_paths.runtime_release_note_path(__version__).is_file())

    def test_unknown_resource_group_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown WOM-kit resource group"):
            resource_paths.runtime_resource_root("private-or-unknown")


if __name__ == "__main__":
    unittest.main()
