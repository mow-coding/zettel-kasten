from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from wom_kit import __version__


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RESOURCE_ROOT = KIT / "src" / "wom_kit" / "_resources"
MANIFEST_PATH = RESOURCE_ROOT / "resource-manifest.json"
RELEASE_PATH = KIT / "docs" / "releases" / "v0.4.2.md"
PACKAGED_RELEASE_PATH = RESOURCE_ROOT / "release-notes" / "v0.4.2.md"
EXPECTED_RELEASE_SHA256 = (
    "eff8541b1923b75c01e7c365b22617735be6dec14d7d2226c1663b040bb0b053"
)


class V0402HistoricalReleaseTests(unittest.TestCase):
    def test_historical_release_is_preserved_byte_for_byte(self) -> None:
        self.assertEqual(
            hashlib.sha256(RELEASE_PATH.read_bytes()).hexdigest(),
            EXPECTED_RELEASE_SHA256,
        )

    def test_v0402_is_not_repackaged_as_the_current_release(self) -> None:
        self.assertEqual(__version__, "0.4.18")
        self.assertFalse(PACKAGED_RELEASE_PATH.exists())
        release_names = sorted(
            path.name
            for path in (RESOURCE_ROOT / "release-notes").glob("v*.md")
        )
        self.assertEqual(release_names, ["v0.4.18.md"])

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.4.18")
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.4.18.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.14.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.13.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.12.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.11.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.10.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.9.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.7.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.2.md", packaged_paths)

    def test_historical_note_keeps_the_original_read_only_boundary(self) -> None:
        normalized = " ".join(RELEASE_PATH.read_text(encoding="utf-8").split())
        for token in (
            "git-backup-plan",
            "git-backup-reconcile-plan",
            "ready_for_write",
            "writer_available",
            "read-only",
            "remains incomplete",
        ):
            with self.subTest(token=token):
                self.assertIn(token, normalized)


if __name__ == "__main__":
    unittest.main()
