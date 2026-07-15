from __future__ import annotations

import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent


class MowHarnessCompatibilityDocsTests(unittest.TestCase):
    def test_optional_harness_boundary_is_public_and_fail_closed(self) -> None:
        guide = (KIT_ROOT / "docs" / "mow-harness-compatibility.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "WOM works without MOW Harness",
            "<archive-root>/collab/",
            "<archive-root>/.mow-harness/",
            "is still a source alpha and is not published to npm",
            "--adopt --dry-run",
            "--adopt --yes",
            "Installing or updating files does not turn MOW Harness on",
            "does not call the MOW CLI",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)

        archive_cli = (KIT_ROOT / "src" / "wom_kit" / "archive_cli.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"/collab/"', archive_cli)
        self.assertIn('"/.mow-harness/"', archive_cli)

    def test_public_navigation_and_capability_matrix_link_the_boundary(self) -> None:
        for relative_path in (
            "docs/ai-assisted-onboarding-and-provider-setup.md",
            "docs/project-intake-session.md",
            "docs/public-documentation-map.md",
            "docs/public-documentation-map.ko.md",
        ):
            with self.subTest(path=relative_path):
                text = (KIT_ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("mow-harness-compatibility.md", text)

        matrix = (KIT_ROOT / "docs" / "capability-matrix.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Optional MOW Harness compatibility", matrix)
        self.assertIn("implemented namespace isolation", matrix)
        self.assertIn("grants no Harness write or activation approval", matrix)


if __name__ == "__main__":
    unittest.main()
