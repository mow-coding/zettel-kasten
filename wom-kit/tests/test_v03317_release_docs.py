from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

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
DECISION = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-13-v03317-letter130-staged-cleanup-evidence.md"
)


class V03317ReleaseDocsTests(unittest.TestCase):
    def test_historical_release_stays_source_only(self) -> None:
        self.assertTrue(RELEASE.is_file())
        self.assertFalse(PACKAGED_RELEASE.exists())
        self.assertTrue(HISTORICAL_RELEASE.is_file())
        self.assertFalse(HISTORICAL_PACKAGED_RELEASE.exists())

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
        staged = DECISION.read_text(encoding="utf-8")
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

    def test_public_history_still_points_to_v03317(self) -> None:
        for path in (
            KIT / "docs" / "public-documentation-map.md",
            KIT / "docs" / "public-documentation-map.ko.md",
        ):
            with self.subTest(document=path.name):
                self.assertIn("0.3.317", path.read_text(encoding="utf-8"))

    def test_v03317_public_source_artifacts_remain_byte_exact(self) -> None:
        expected = {
            RELEASE: (
                "a8dd4507aec59f9dd919806b2fb33fae5e6908471e66386f3185d2dd55e9c691"
            ),
            DECISION: (
                "75c46c9cebe21b1a1340aa8ea61111fcfc786506d88a069d6b9c46abd6bab624"
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
