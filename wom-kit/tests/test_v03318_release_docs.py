from __future__ import annotations

import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RELEASE = KIT / "docs" / "releases" / "v0.3.318.md"
PACKAGED_RELEASE = (
    KIT / "src" / "wom_kit" / "_resources" / "release-notes" / "v0.3.318.md"
)
HISTORICAL_RELEASE = KIT / "docs" / "releases" / "v0.3.317.md"
HISTORICAL_PACKAGED_RELEASE = PACKAGED_RELEASE.with_name("v0.3.317.md")
GUIDE = KIT / "docs" / "letter131-credential-console-paste-and-failure-stages.md"
DECISION = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-13-v03318-letter131-credential-input.md"
)


class V03318ReleaseDocsTests(unittest.TestCase):
    def test_historical_release_stays_source_only(self) -> None:
        self.assertTrue(RELEASE.is_file())
        self.assertFalse(PACKAGED_RELEASE.exists())
        self.assertTrue(HISTORICAL_RELEASE.is_file())
        self.assertFalse(HISTORICAL_PACKAGED_RELEASE.exists())

    def test_release_and_guide_preserve_v03318_contract(self) -> None:
        release = RELEASE.read_text(encoding="utf-8")
        guide = GUIDE.read_text(encoding="utf-8")
        combined = " ".join((" ".join(release.split()), " ".join(guide.split())))
        for token in (
            "Ctrl+V",
            "Shift+Insert",
            "Ctrl+Shift+V",
            "right-click",
            "입력값을 받았습니다. 검증 중입니다.",
            "credential_input_cancelled_or_empty",
            "credential_input_not_received",
            "provider_auth_rejected",
            "provider_identity_endpoint_unavailable",
            "reviewed_anchor_inaccessible",
            "wom-credential-secure-intake-result/v0.2",
            "wom-credential-workflow-result/v0.2",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

        for token in (
            "Ctrl+C",
            "empty Enter",
            "actual physical paste gesture",
            "does not prove merge, external CI, exact tag, GitHub Release",
        ):
            with self.subTest(token=token):
                self.assertIn(token, release)

        for forbidden in ("C:\\Users\\", "wom-feedback-", "protected archive"):
            for document_name, text in (("release", release), ("guide", guide)):
                with self.subTest(forbidden=forbidden, document=document_name):
                    self.assertNotIn(forbidden, text)

    def test_decision_preserves_fixed_security_and_failure_stage_boundaries(self) -> None:
        text = DECISION.read_text(encoding="utf-8")
        for token in (
            "credential_input_cancelled_or_empty",
            "credential_input_not_received",
            "provider_auth_rejected",
            "provider_identity_endpoint_unavailable",
            "reviewed_anchor_inaccessible",
            "rollback",
            "echo",
            "clipboard",
        ):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_historical_docs_keep_manual_tool_route_without_binding_current_schema(self) -> None:
        relative_tool = "tools/check_windows_credential_console_host.py"
        for path in (RELEASE, GUIDE):
            with self.subTest(document=path.name):
                self.assertIn(relative_tool, path.read_text(encoding="utf-8"))

    def test_public_history_still_points_to_v03318(self) -> None:
        for path in (
            KIT / "docs" / "public-documentation-map.md",
            KIT / "docs" / "public-documentation-map.ko.md",
        ):
            with self.subTest(document=path.name):
                self.assertIn("0.3.318", path.read_text(encoding="utf-8"))

    def test_v03318_public_source_artifacts_remain_byte_exact(self) -> None:
        expected = {
            RELEASE: "649899aa8ad6150f27f8ffb551e72c90dce20eecaea8e78c098d342e6e174735",
            GUIDE: "674f8707b4fe176ff7e73661820691e09a8af54bacc982daa390cff3c72cb49b",
            DECISION: "a80000aa0011204a30114377968402c5c491a91c5115a8b53cbd0629a6c65e8d",
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
