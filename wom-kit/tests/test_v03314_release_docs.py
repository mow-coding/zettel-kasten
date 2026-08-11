from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RELEASE = KIT / "docs" / "releases" / "v0.3.314.md"
PACKAGED_RELEASE = (
    KIT / "src" / "wom_kit" / "_resources" / "release-notes" / "v0.3.314.md"
)
SKILL = KIT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"


class V03314ReleaseDocsTests(unittest.TestCase):
    def test_historical_release_stays_source_only(self) -> None:
        self.assertTrue(RELEASE.is_file())
        self.assertFalse(PACKAGED_RELEASE.exists())
        historical_packaged = PACKAGED_RELEASE.with_name("v0.3.313.md")
        self.assertFalse(historical_packaged.exists())

    def test_release_states_exact_implemented_and_unsupported_boundaries(self) -> None:
        text = RELEASE.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        for token in (
            "11,184",
            "2.538 seconds",
            "rollback `DELETE` mode",
            "operation-control",
            "operation_cancel_not_supported",
            "cancel_supported: false",
            "cancel_requested: false",
            "resume_supported: false",
            "There is no daemon, queue, background launcher",
            "does not prove merge, external CI, exact tag, GitHub Release",
        ):
            with self.subTest(token=token):
                self.assertIn(token, flat)
        self.assertNotIn("C:\\Users\\", text)
        self.assertNotIn("](../", text)

    def test_runtime_skill_is_bounded_and_routes_timeout_recovery(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertLessEqual(len(text.split()), 1400)
        for token in (
            "operation_ref",
            "operation-control --action status --dry-run",
            "bounded",
            "Cancel and resume are unsupported",
            "do not start a duplicate writer",
        ):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_current_public_guides_use_valid_output_examples(self) -> None:
        paths = (
            KIT / "docs" / "project-version-update.md",
            KIT / "docs" / "version-truth-source.md",
            KIT / "docs" / "python-tool-install.md",
            KIT / "docs" / "python-tool-install.ko.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        self.assertIn(".zettel-kasten/diagnostics/update-", combined)
        self.assertNotIn("update-<new-name>", combined)
        self.assertIn("operation_ref", combined)


if __name__ == "__main__":
    unittest.main()
