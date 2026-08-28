from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RELEASE = KIT / "docs" / "releases" / "v0.4.13.md"
DECISION = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-29-v0413-create-only-object-storage-preservation.md"
)
LOCK = KIT / "project-runtime-supply-lock-v0.4.13.json"
LOCK_SHA256 = "6ede0cfb75b4c2715cc2d53fb1d3129898d582731057d0f4f1c3e68fcdc160dd"


class V0413ReleaseDocsTests(unittest.TestCase):
    def test_current_version_surfaces_are_exact(self) -> None:
        expected = "0.4.13"
        package_init = (KIT / "src" / "wom_kit" / "__init__.py").read_text(
            encoding="utf-8"
        )
        root_shim = (ROOT / "wom_kit" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn(f'__version__ = "{expected}"', package_init)
        self.assertIn(f'__version__ = "{expected}"', root_shim)
        self.assertIn(
            f'version = "{expected}"',
            (KIT / "pyproject.toml").read_text(encoding="utf-8"),
        )
        self.assertIn(
            f'version: "{expected}"',
            (ROOT / "CITATION.cff").read_text(encoding="utf-8"),
        )
        versioning = (ROOT / "VERSIONING.md").read_text(encoding="utf-8")
        self.assertIn("Current public baseline:\n\n```text\nv0.4.13", versioning)
        self.assertIn("current `wom-kit` package metadata is:\n\n```text\n0.4.13", versioning)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko = (ROOT / "README.ko.md").read_text(encoding="utf-8")
        for document in (readme, readme_ko):
            self.assertIn("releases/download/v0.4.13/wom_kit-0.4.13-py3-none-any.whl", document)
        self.assertIn("Previous public baseline: v0.4.12.", readme)
        self.assertIn("이전 공개 기준: v0.4.12.", readme_ko)

    def test_supply_lock_changes_only_target_tag_and_policy_is_exact(self) -> None:
        current = LOCK.read_bytes()
        previous = (KIT / "project-runtime-supply-lock-v0.4.12.json").read_bytes()
        expected = previous.replace(b"\r\n", b"\n").replace(
            b'"target_tag": "v0.4.12"',
            b'"target_tag": "v0.4.13"',
        )
        self.assertEqual(current, expected)
        self.assertEqual(len(current), 1178)
        self.assertNotIn(b"\r", current)
        self.assertEqual(hashlib.sha256(current).hexdigest(), LOCK_SHA256)

        policy = json.loads((KIT / "project-runtime-policy.json").read_text(encoding="utf-8"))
        self.assertEqual(
            policy["supply_lock"],
            "wom-kit/project-runtime-supply-lock-v0.4.13.json",
        )
        self.assertEqual(policy["supply_lock_sha256"], f"sha256:{LOCK_SHA256}")
        source = (KIT / "src" / "wom_kit" / "project_runtime.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(policy["supply_lock"], source)
        self.assertIn(policy["supply_lock_sha256"], source)

    def test_release_contract_is_create_only_resumable_and_honest(self) -> None:
        text = RELEASE.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        for required in (
            "exact-first",
            "If-None-Match: *",
            "multipart",
            "HEAD plus a complete GET rehash",
            "bytes_preserved",
            "already_remote_verified",
            "review_required",
            "nonterminal and resumable",
            "manifest-bound provider-call ceiling",
            "Preservation is not formal adoption",
            "person is not asked to count records or compare digests",
            "Publishing or installing v0.4.13 does not read a client archive",
            "synthetic transport tests are not that proof",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), flat.casefold())

        self.assertTrue(DECISION.is_file())
        decision = DECISION.read_text(encoding="utf-8")
        self.assertIn("conditional create", decision)
        self.assertIn("without\n  issuing a second unconditional upload", decision)
        self.assertIn("whole-archive backup claim", decision)

    def test_public_v0413_documents_do_not_publish_client_evidence(self) -> None:
        documents = (
            RELEASE,
            DECISION,
            KIT / "docs" / "object-storage-adapter-readiness-plan.md",
            KIT / "docs" / "object-storage-adapter-execution-contract.md",
            KIT / "docs" / "ai-assisted-onboarding-and-provider-setup.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in documents)
        self.assertNotRegex(combined, r"(?i)letter\s*\d+")
        self.assertNotRegex(combined, r"(?i)feedback[/\\]letters")
        self.assertNotRegex(combined, r"(?i)[A-Z]:\\Users\\(?!<user>)")
        self.assertNotRegex(combined, r"(?i)sha256:[0-9a-f]{64}")
        self.assertNotRegex(combined, r"(?i)https?://[^\s)>]+(?:r2\.cloudflarestorage|amazonaws)\.com")

    def test_current_guides_separate_install_setup_and_provider_execution(self) -> None:
        files = (
            ROOT / "UPGRADE.md",
            ROOT / "UPGRADE.ko.md",
            KIT / "README.md",
            KIT / "docs" / "python-tool-install.md",
            KIT / "docs" / "python-tool-install.ko.md",
            KIT / "docs" / "version-truth-source.md",
            KIT / "docs" / "runtime-canonical-entrypoints.md",
            KIT / "docs" / "public-documentation-map.md",
            KIT / "docs" / "public-documentation-map.ko.md",
        )
        for path in files:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("v0.4.13", text)

        upgrade = (ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        flat_upgrade = " ".join(upgrade.split())
        self.assertIn("Publishing, installing, or planning the release performs no upload", flat_upgrade)
        self.assertIn("person chooses run or cancel", flat_upgrade)
        self.assertIn("does not require a public archive-format migration", flat_upgrade)


if __name__ == "__main__":
    unittest.main()
