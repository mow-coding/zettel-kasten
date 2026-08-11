from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from wom_kit import __version__


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RELEASE = KIT / "docs" / "releases" / "v0.3.316.md"
PACKAGED_RELEASE = (
    KIT / "src" / "wom_kit" / "_resources" / "release-notes" / "v0.3.316.md"
)
HISTORICAL_RELEASE = KIT / "docs" / "releases" / "v0.3.315.md"
HISTORICAL_PACKAGED_RELEASE = PACKAGED_RELEASE.with_name("v0.3.315.md")
DECISION = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-12-v03316-letter129.md"
)
SKILL_ROOT = KIT / "templates" / "ai-runtime" / "wom-archive"
PACKAGED_SKILL_ROOT = (
    KIT
    / "src"
    / "wom_kit"
    / "_resources"
    / "templates"
    / "ai-runtime"
    / "wom-archive"
)


class V03316ReleaseDocsTests(unittest.TestCase):
    def test_version_and_current_packaged_release_are_synchronized(self) -> None:
        self.assertEqual(__version__, "0.3.316")
        self.assertEqual(RELEASE.read_bytes(), PACKAGED_RELEASE.read_bytes())
        self.assertTrue(HISTORICAL_RELEASE.is_file())
        self.assertFalse(HISTORICAL_PACKAGED_RELEASE.exists())

        manifest = json.loads(
            (
                KIT
                / "src"
                / "wom_kit"
                / "_resources"
                / "resource-manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "0.3.316")
        packaged = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.3.316.md", packaged)
        self.assertNotIn("release-notes/v0.3.315.md", packaged)

    def test_release_states_the_complete_recovery_and_evidence_boundaries(self) -> None:
        text = RELEASE.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        for token in (
            "v0.3.315 update correctly detected 25 ignored Python",
            "--action inspect-all",
            "materialization_plan_sha256",
            "complete opaque collision set",
            "Counts alone are never repair authority",
            "project-bytecode-repair-plan",
            "Exact-set-bound cache repair",
            "same exclusive project-version-update lock",
            "final pre-write HEAD and tracked-byte drift check remains",
            "--affirm-external-writers-quiescent",
            "fresh updater preview",
            "Repair success is not update success",
            "does not prove merge, external CI, exact tag, GitHub Release",
        ):
            with self.subTest(token=token):
                self.assertIn(token, flat)

        for forbidden in (
            "C:\\Users\\",
            "wom-feedback-",
            "protected archive",
            "update-entry:0025",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_decision_and_operator_guidance_match_the_release_contract(self) -> None:
        decision = DECISION.read_text(encoding="utf-8")
        for token in (
            "no-UI, AI-host-operated v0.3.x product direction",
            "--action inspect-all",
            "Counts are informational, not authority",
            "exact internal path set",
            "external-writer quiescence",
            "fresh updater preview",
        ):
            with self.subTest(token=token):
                self.assertIn(token, decision)

        expectations = {
            "docs/project-version-update.md": (
                "inspect-all",
                "project-bytecode-repair",
                "fresh",
            ),
            "docs/operation-control.md": ("inspect-all", "fresh"),
            "docs/runtime-canonical-entrypoints.md": (
                "inspect-all",
                "project-bytecode-repair",
                "fresh",
            ),
            "docs/version-truth-source.md": (
                "inspect-all",
                "project-bytecode-repair",
                "fresh",
            ),
            "docs/ai-command-path-routing.md": (
                "inspect-all",
                "project-bytecode-repair",
            ),
        }
        for relative, tokens in expectations.items():
            text = (KIT / relative).read_text(encoding="utf-8")
            for token in tokens:
                with self.subTest(document=relative, token=token):
                    self.assertIn(token, text.lower())

    def test_current_maps_readmes_and_install_guides_point_to_v03316(self) -> None:
        paths = (
            ROOT / "README.md",
            ROOT / "README.ko.md",
            ROOT / "UPGRADE.md",
            ROOT / "UPGRADE.ko.md",
            KIT / "README.md",
            KIT / "cli" / "README.md",
            KIT / "docs" / "python-tool-install.md",
            KIT / "docs" / "python-tool-install.ko.md",
            KIT / "docs" / "runtime-canonical-entrypoints.md",
            KIT / "docs" / "version-truth-source.md",
            KIT / "docs" / "ai-command-path-routing.md",
            KIT / "docs" / "public-documentation-map.md",
            KIT / "docs" / "public-documentation-map.ko.md",
        )
        for path in paths:
            with self.subTest(document=path.name):
                self.assertIn("0.3.316", path.read_text(encoding="utf-8"))

        install = (KIT / "docs" / "python-tool-install.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("wom_kit-0.3.316-py3-none-any.whl", install)
        self.assertIn("installed v0.3.315 client cannot use", install.lower())

    def test_runtime_skill_is_bounded_and_package_mirrors_match(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(skill.splitlines()), 200)
        self.assertLessEqual(len(skill.split()), 1400)
        for token in (
            "--action inspect-all",
            "exact all-supported cache set",
            "project-bytecode-repair",
            "fresh updater preview and separate approval",
        ):
            with self.subTest(token=token):
                self.assertIn(token, skill)

        for relative in (
            Path("SKILL.md"),
            Path("references/startup-and-update.md"),
            Path("references/operator-contract.md"),
        ):
            with self.subTest(resource=relative.as_posix()):
                self.assertEqual(
                    (SKILL_ROOT / relative).read_bytes(),
                    (PACKAGED_SKILL_ROOT / relative).read_bytes(),
                )

    def test_v03315_public_source_artifacts_remain_byte_exact(self) -> None:
        expected = {
            HISTORICAL_RELEASE: (
                "daeb6d327bf231dbe366a8936505702fe1c8f374c280249da66bf6bcee9143e8"
            ),
            KIT
            / "docs"
            / "archive-infra-decision-log-2026-08-11-v03315-letter127.md": (
                "1c0057e831181167c535b74752bf225e8d677d24966fe55f1c2c1a5bc02791ad"
            ),
            KIT
            / "docs"
            / "archive-infra-decision-log-2026-08-11-v03315-letter128.md": (
                "8802d6c2a9189c3ccaa73dccfc8b91a0cff29d94c8529723d43ed291d3b04137"
            ),
        }
        for path, expected_sha256 in expected.items():
            with self.subTest(path=path.name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    expected_sha256,
                )


if __name__ == "__main__":
    unittest.main()
