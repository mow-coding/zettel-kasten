from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "wom-kit" / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"
CAPTURE = SKILL.parent / "references" / "capture-draft-and-publication.md"
PERSONAL = ROOT / "wom-kit" / "templates" / "personal" / "AGENTS.md"
DOC = ROOT / "wom-kit" / "docs" / "source-fidelity-and-private-verbatim.md"
RESPONSE = ROOT / "wom-kit" / "docs" / "ai-response-contract.md"
RELEASE = ROOT / "wom-kit" / "docs" / "releases" / "v0.3.313.md"
HISTORICAL_PACKAGED_RELEASE = (
    ROOT
    / "wom-kit"
    / "src"
    / "wom_kit"
    / "_resources"
    / "release-notes"
    / "v0.3.313.md"
)
SCHEMA = ROOT / "wom-kit" / "schemas" / "source-fidelity-draft-receipt.schema.json"
PACKAGED_SCHEMA = (
    ROOT
    / "wom-kit"
    / "src"
    / "wom_kit"
    / "_resources"
    / "schemas"
    / "source-fidelity-draft-receipt.schema.json"
)
MATRIX = ROOT / "wom-kit" / "docs" / "capability-matrix.md"
RUNTIME = ROOT / "wom-kit" / "docs" / "runtime-canonical-entrypoints.md"
PUBLIC_MAP = ROOT / "wom-kit" / "docs" / "public-documentation-map.md"
PUBLIC_MAP_KO = ROOT / "wom-kit" / "docs" / "public-documentation-map.ko.md"


class V03313SourceFidelityDocsTests(unittest.TestCase):
    def test_runtime_surfaces_preserve_explicit_private_verbatim(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in (SKILL, CAPTURE, PERSONAL, RESPONSE)
        )
        for token in (
            "private_self",
            "verbatim",
            "faithful_summary",
            "sanitized_derivative",
            "credential secret",
            "human review",
        ):
            self.assertIn(token.lower(), combined.lower())
        self.assertNotIn("Do not paste a raw conversation log into a canonical zet", combined)

    def test_contract_is_honest_about_normalization_and_semantics(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for token in (
            "utf8_newlines_lf",
            "byte_exact: false",
            "does not trim",
            "normalize Unicode",
            "remove a BOM",
            "semantic faithfulness",
            "not an ACL",
        ):
            self.assertIn(token, text)

    def test_contract_uses_primary_standards_and_no_private_fixture(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for url in (
            "https://www.w3.org/TR/prov-o/",
            "https://www.rfc-editor.org/rfc/rfc9530.html",
            "https://www.rfc-editor.org/rfc/rfc8493.html",
            "https://public.ccsds.org/Pubs/650x0m3.pdf",
            "https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md",
            "https://slsa.dev/spec/v1.2/build-provenance",
        ):
            self.assertIn(url, text)
        lowered = text.lower()
        self.assertNotIn("kakao", lowered)
        self.assertNotIn("카카오", text)
        self.assertNotIn("c:\\users", lowered)
        self.assertNotIn("20260810-121", text)

    def test_runtime_skill_stays_bounded(self) -> None:
        words = SKILL.read_text(encoding="utf-8").split()
        self.assertLessEqual(len(words), 1400)

    def test_historical_release_stays_source_only_and_schema_is_packaged(self) -> None:
        self.assertTrue(RELEASE.is_file())
        self.assertFalse(HISTORICAL_PACKAGED_RELEASE.exists())
        self.assertEqual(SCHEMA.read_bytes(), PACKAGED_SCHEMA.read_bytes())

    def test_current_public_surfaces_link_the_contract_and_predecessor(self) -> None:
        expected_status = (
            "Status: v0.3.320 one-use credential capability broker checkpoint"
        )
        for path in (MATRIX, RUNTIME):
            with self.subTest(document=path.name):
                self.assertIn(expected_status, path.read_text(encoding="utf-8"))

        for path in (PUBLIC_MAP, PUBLIC_MAP_KO):
            text = path.read_text(encoding="utf-8")
            with self.subTest(document=path.name):
                self.assertIn("source-fidelity-and-private-verbatim.md", text)
                self.assertIn(
                    "archive-infra-decision-log-2026-08-10-v03313-source-fidelity.md",
                    text,
                )
                self.assertIn("releases/v0.3.313.md", text)
                self.assertIn("releases/v0.3.312.md", text)

    def test_release_is_private_value_free_and_honest_about_evidence(self) -> None:
        text = RELEASE.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        for token in (
            "Verified data loss is therefore zero",
            "does not prove merge, external CI, exact tag, GitHub Release",
            "Human-written legacy draft creation remains compatible",
            "ai_provenance_requires_ai_creation_mode",
            "Audience is descriptive intent, not an ACL",
            "mint_zettel_check",
        ):
            self.assertIn(token, flat)
        for forbidden in (
            "C:\\Users\\",
            "20260810-121",
            "Letter 121",
            "WOM-전달",
        ):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
