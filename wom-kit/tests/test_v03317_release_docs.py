from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from wom_kit import __version__


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RELEASE = KIT / "docs" / "releases" / "v0.3.317.md"
PACKAGED_RELEASE = (
    KIT / "src" / "wom_kit" / "_resources" / "release-notes" / "v0.3.317.md"
)
HISTORICAL_RELEASE = KIT / "docs" / "releases" / "v0.3.316.md"
HISTORICAL_PACKAGED_RELEASE = PACKAGED_RELEASE.with_name("v0.3.316.md")
CREDENTIAL_DECISION = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-10-v03311-letter118-119-credential-lifecycle.md"
)
STAGED_DECISION = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-13-v03317-letter130-staged-cleanup-evidence.md"
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


class V03317ReleaseDocsTests(unittest.TestCase):
    def test_version_and_current_packaged_release_are_synchronized(self) -> None:
        self.assertEqual(__version__, "0.3.317")
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
        self.assertEqual(manifest["version"], "0.3.317")
        self.assertEqual(manifest["file_count"], 145)
        packaged = {row["packaged"] for row in manifest["files"]}
        self.assertIn("release-notes/v0.3.317.md", packaged)
        self.assertNotIn("release-notes/v0.3.316.md", packaged)

    def test_release_states_both_corrected_real_use_boundaries(self) -> None:
        text = RELEASE.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        for token in (
            "one clearly visible black Windows window",
            "matching authenticated registration is reused",
            "verifies its secret fingerprint",
            "currently reviewed Notion anchor",
            "--task-summary",
            "--connection-reason",
            "--replace-existing",
            "input echo is disabled",
            "console closes before the Credential Manager write",
            "bot.workspace_id",
            "notion_pat_token_scope_v1",
            "same saved PAT can therefore be reused for another reviewed page",
            "v0.3.311-v0.3.316 are legacy v0.1 records",
            "authenticated local workspace-scope evolution",
            "opens no input console",
            "performs no Credential Manager write or deletion",
            "duplicate or complex lifecycle state stops for review",
            "Ordinary objet preservation",
            "direct terminal derived-text receipt",
            "same-size change with a restored modification time",
            "A legacy `--deferred` entry means",
            "`safe_to_cleanup` false",
            "Exit `1` means cleanup is not authorized",
            "does not prove merge, external CI, exact tag, GitHub Release",
        ):
            with self.subTest(token=token):
                self.assertIn(token, flat)

        for forbidden in (
            "C:\\Users\\",
            "wom-feedback-",
            "protected archive",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_decisions_and_operator_guidance_match_release_contract(self) -> None:
        credential = CREDENTIAL_DECISION.read_text(encoding="utf-8")
        staged = STAGED_DECISION.read_text(encoding="utf-8")
        operation = (KIT / "docs" / "operation-control.md").read_text(
            encoding="utf-8"
        )
        runtime = (KIT / "docs" / "runtime-canonical-entrypoints.md").read_text(
            encoding="utf-8"
        )
        for token in (
            "reviewed public-safe current-task",
            "WOM owns fixed security",
            "authenticating the matching receipt",
            "secret fingerprint",
            "current reviewed Notion anchor",
            "`--replace-existing`",
            "`bot.workspace_id`",
            "`notion_pat_token_scope_v1`",
            "workspace-scope evolution",
            "v0.3.311-v0.3.316 v0.1 receipts immutable",
        ):
            with self.subTest(surface="credential", token=token):
                self.assertIn(token, credential)
        for token in (
            "strict canonical object-manifest row",
            "valid direct derived-text terminal receipt",
            "same-size in-place writer",
            "Deferred means",
            "process exit `1`",
        ):
            with self.subTest(surface="staged", token=token):
                self.assertIn(token, staged)
        for token in (
            "staged-cleanup-check",
            "safe_to_cleanup: false",
            "process exit `1`",
            "Deferred entries remain",
        ):
            with self.subTest(surface="operation", token=token):
                self.assertIn(token, operation)
        for token in (
            "`bot.workspace_id`",
            "`notion_pat_token_scope_v1`",
            "same saved PAT can therefore serve another reviewed page",
            "no-prompt, append-only local scope evolution",
            "duplicate or complex lifecycle state stops for review",
        ):
            with self.subTest(surface="runtime", token=token):
                self.assertIn(token, runtime)

    def test_current_maps_readmes_and_install_guides_point_to_v03317(self) -> None:
        paths = (
            ROOT / "README.md",
            ROOT / "README.ko.md",
            ROOT / "UPGRADE.md",
            ROOT / "UPGRADE.ko.md",
            ROOT / "VERSIONING.md",
            KIT / "README.md",
            KIT / "cli" / "README.md",
            KIT / "docs" / "python-tool-install.md",
            KIT / "docs" / "python-tool-install.ko.md",
            KIT / "docs" / "runtime-canonical-entrypoints.md",
            KIT / "docs" / "version-truth-source.md",
            KIT / "docs" / "ai-command-path-routing.md",
            KIT / "docs" / "capability-matrix.md",
            KIT / "docs" / "public-documentation-map.md",
            KIT / "docs" / "public-documentation-map.ko.md",
        )
        for path in paths:
            with self.subTest(document=path.name):
                self.assertIn("0.3.317", path.read_text(encoding="utf-8"))

        install = (KIT / "docs" / "python-tool-install.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("wom_kit-0.3.317-py3-none-any.whl", install)
        self.assertIn("installed v0.3.316 client", install.lower())

    def test_runtime_skill_is_bounded_and_package_mirrors_match(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(skill.splitlines()), 200)
        self.assertLessEqual(len(skill.split()), 1400)
        for token in (
            "first enrollment or an explicitly reviewed replacement",
            "WOM owns the fixed",
            "separate echo-disabled Windows console",
            "exact Windows Credential Manager entry",
            "saved PAT may be revalidated for another reviewed page",
            "no-prompt scope-evolution path",
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

    def test_v03316_public_source_artifacts_remain_byte_exact(self) -> None:
        expected = {
            HISTORICAL_RELEASE: (
                "adca13da21c1a4f560cb53b5a59cac48a7783c949eebe97be99016d0245515b9"
            ),
            KIT
            / "docs"
            / "archive-infra-decision-log-2026-08-12-v03316-letter129.md": (
                "5ecb1354459e37e41ae63c8b986bb2cc1d159f78e13f5a43d26f391f9056b07d"
            ),
        }
        for path, expected_sha256 in expected.items():
            with self.subTest(path=path.name):
                canonical_git_text = path.read_bytes().replace(b"\r\n", b"\n")
                self.assertEqual(
                    hashlib.sha256(canonical_git_text).hexdigest(),
                    expected_sha256,
                )


if __name__ == "__main__":
    unittest.main()
