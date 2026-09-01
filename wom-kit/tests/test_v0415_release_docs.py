from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from wom_kit import __version__


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RESOURCE_ROOT = KIT / "src" / "wom_kit" / "_resources"
RELEASE = KIT / "docs" / "releases" / "v0.4.15.md"
LOCK = KIT / "project-runtime-supply-lock-v0.4.15.json"
LOCK_SHA256 = "8cc4597742bab8bb4f7c1f4e4c28d90d0b8cddd1293247e680c615531d31953d"
CURRENT_LOCK_SHA256 = (
    "4a321346b9231646c0c74e0784d42ca75a866200e497283f54b015165a87a28f"
)


class V0415ReleaseDocsTests(unittest.TestCase):
    def test_v0415_is_preserved_as_source_history(self) -> None:
        self.assertEqual(__version__, "0.4.17")
        self.assertTrue(RELEASE.is_file())
        self.assertFalse(
            (RESOURCE_ROOT / "release-notes" / "v0.4.15.md").exists()
        )
        for path in (
            KIT / "src" / "wom_kit" / "__init__.py",
            ROOT / "wom_kit" / "__init__.py",
        ):
            with self.subTest(path=path):
                self.assertIn(
                    '__version__ = "0.4.17"',
                    path.read_text(encoding="utf-8"),
                )
        self.assertIn(
            'version = "0.4.17"',
            (KIT / "pyproject.toml").read_text(encoding="utf-8"),
        )
        versioning = (ROOT / "VERSIONING.md").read_text(encoding="utf-8")
        self.assertIn("Current public baseline:\n\n```text\nv0.4.17", versioning)
        self.assertIn("Previous public baseline:\n\n```text\nv0.4.16", versioning)

    def test_v0415_supply_lock_is_historical_and_policy_is_v0417(self) -> None:
        current = LOCK.read_bytes()
        previous = (KIT / "project-runtime-supply-lock-v0.4.14.json").read_bytes()
        expected = previous.replace(b"\r\n", b"\n").replace(
            b'"target_tag": "v0.4.14"',
            b'"target_tag": "v0.4.15"',
        )
        self.assertEqual(current, expected)
        self.assertEqual(len(current), 1178)
        self.assertNotIn(b"\r", current)
        self.assertEqual(hashlib.sha256(current).hexdigest(), LOCK_SHA256)

        policy = json.loads(
            (KIT / "project-runtime-policy.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            policy["supply_lock"],
            "wom-kit/project-runtime-supply-lock-v0.4.17.json",
        )
        self.assertEqual(
            policy["supply_lock_sha256"],
            f"sha256:{CURRENT_LOCK_SHA256}",
        )

    def test_v0415_release_contract_remains_honest_history(self) -> None:
        flat = " ".join(RELEASE.read_text(encoding="utf-8").split())
        for required in (
            "One locator-free recovery command",
            "requires no caller-supplied `--target`, `--transaction-ref`, `--approval-id`, or `--reviewed-by`",
            "terminal_cleanup_outcome_unknown",
            "not authenticated outcome or cleanup authority",
            "Create-only emergency feedback preservation",
            "Installing the wheel changes no archive data",
            "Require exactly `archive 0.4.15`",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), flat.casefold())

    def test_v0415_is_not_repackaged_as_current(self) -> None:
        release_names = sorted(
            path.name for path in (RESOURCE_ROOT / "release-notes").glob("v*.md")
        )
        self.assertEqual(release_names, ["v0.4.17.md"])
        manifest = json.loads(
            (RESOURCE_ROOT / "resource-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "0.4.17")
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.4.17.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.15.md", packaged_paths)

    def test_public_v0415_history_has_no_client_evidence(self) -> None:
        text = RELEASE.read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?i)letter\s*15[01]")
        self.assertNotRegex(text, r"(?i)feedback[/\\]letters")
        self.assertNotRegex(text, r"(?i)[A-Z]:\\Users\\(?!<user>)")


if __name__ == "__main__":
    unittest.main()
