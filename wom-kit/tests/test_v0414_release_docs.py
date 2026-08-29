from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from wom_kit import __version__


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RESOURCE_ROOT = KIT / "src" / "wom_kit" / "_resources"
RELEASE = KIT / "docs" / "releases" / "v0.4.14.md"
LOCK = KIT / "project-runtime-supply-lock-v0.4.14.json"
LOCK_SHA256 = "f3a3e0f5f2b766974bc9b376c7ce6d767b199ecc9c57d05cb7d28e738777ce93"


class V0414ReleaseDocsTests(unittest.TestCase):
    def test_current_version_and_release_surfaces_are_exact(self) -> None:
        self.assertEqual(__version__, "0.4.14")
        for path in (
            KIT / "src" / "wom_kit" / "__init__.py",
            ROOT / "wom_kit" / "__init__.py",
        ):
            with self.subTest(path=path):
                self.assertIn(
                    '__version__ = "0.4.14"',
                    path.read_text(encoding="utf-8"),
                )
        self.assertIn(
            'version = "0.4.14"',
            (KIT / "pyproject.toml").read_text(encoding="utf-8"),
        )
        self.assertIn(
            'version: "0.4.14"',
            (ROOT / "CITATION.cff").read_text(encoding="utf-8"),
        )
        versioning = (ROOT / "VERSIONING.md").read_text(encoding="utf-8")
        self.assertIn("Current public baseline:\n\n```text\nv0.4.14", versioning)
        self.assertIn("Previous public baseline:\n\n```text\nv0.4.13", versioning)

    def test_supply_lock_changes_only_target_tag_and_current_policy_is_exact(self) -> None:
        current = LOCK.read_bytes()
        previous = (KIT / "project-runtime-supply-lock-v0.4.13.json").read_bytes()
        expected = previous.replace(b"\r\n", b"\n").replace(
            b'"target_tag": "v0.4.13"',
            b'"target_tag": "v0.4.14"',
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
            "wom-kit/project-runtime-supply-lock-v0.4.14.json",
        )
        self.assertEqual(policy["supply_lock_sha256"], f"sha256:{LOCK_SHA256}")

    def test_release_contract_is_reference_aware_private_and_honest(self) -> None:
        text = RELEASE.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        for required in (
            "Historical omission markers are no longer restored blindly",
            "hash-bound reviewed reference bindings",
            "Partial evidence stays partial",
            "ExactOperationManifest v1",
            "The person is not asked to count rows or compare hashes",
            "Missing, ambiguous, or mismatched evidence",
            "These clues never enter the machine plan, approval digest, receipt, or public output",
            "Incomplete bounded pages remain canonical source",
            "Publishing or installing v0.4.14 does not inspect, classify, or change a client archive",
            "Client completion requires that run's approved receipt",
            "Require exactly `archive 0.4.14`",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), flat.casefold())

    def test_current_release_is_the_only_packaged_note(self) -> None:
        packaged = RESOURCE_ROOT / "release-notes" / "v0.4.14.md"
        self.assertEqual(RELEASE.read_bytes(), packaged.read_bytes())
        release_names = sorted(
            path.name for path in (RESOURCE_ROOT / "release-notes").glob("v*.md")
        )
        self.assertEqual(release_names, ["v0.4.14.md"])
        manifest = json.loads(
            (RESOURCE_ROOT / "resource-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "0.4.14")
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.4.14.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.13.md", packaged_paths)

    def test_public_v0414_surfaces_do_not_publish_client_evidence(self) -> None:
        documents = (
            RELEASE,
            ROOT / "CHANGELOG.md",
            ROOT / "README.md",
            ROOT / "README.ko.md",
            ROOT / "UPGRADE.md",
            ROOT / "UPGRADE.ko.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in documents)
        self.assertNotRegex(combined, r"(?i)letter\s*1(?:45|47|48|49)")
        self.assertNotRegex(combined, r"(?i)feedback[/\\]letters")
        self.assertNotRegex(combined, r"(?i)[A-Z]:\\Users\\(?!<user>)")


if __name__ == "__main__":
    unittest.main()
