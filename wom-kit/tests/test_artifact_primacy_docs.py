from __future__ import annotations

import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent


class ArtifactPrimacyDocumentationTests(unittest.TestCase):
    def test_public_philosophy_preserves_human_drift_boundary(self) -> None:
        english = (KIT_ROOT / "docs" / "concepts" / "product-philosophy.md").read_text(
            encoding="utf-8"
        )
        korean = (
            KIT_ROOT / "docs" / "concepts" / "product-philosophy.ko.md"
        ).read_text(encoding="utf-8")

        for phrase in (
            "Durable artifacts are primary evidence",
            "A neat graph can be a false graph",
            "`canonical` is an archive lifecycle status",
            "Matching names or labels must not silently merge",
            "The goal is not deterministic knowledge",
        ):
            with self.subTest(language="en", phrase=phrase):
                self.assertIn(phrase, english)

        for phrase in (
            "아티팩트 우선과 인간 변화 원칙",
            "예쁜 그래프가 거짓 그래프일 수 있습니다",
            "객관적이거나 영원한 진실이라는 인증이 아닙니다",
            "하나의 엔티티로 자동",
            "결정론적 지식을 만드는 것이 아닙니다",
        ):
            with self.subTest(language="ko", phrase=phrase):
                self.assertIn(phrase, korean)

    def test_whitepaper_blueprint_and_decision_log_share_the_boundary(self) -> None:
        whitepaper = (
            KIT_ROOT / "docs" / "concepts" / "foundational-product-whitepaper.md"
        ).read_text(encoding="utf-8")
        blueprint = (
            KIT_ROOT / "specs" / "zettelkasten-zet-product-blueprint.md"
        ).read_text(encoding="utf-8")
        decision = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-15-v03246-artifact-primacy-human-drift.md"
        ).read_text(encoding="utf-8")
        whitepaper_prose = " ".join(whitepaper.split())

        self.assertIn("Artifact Primacy, Not Entity Certainty", whitepaper)
        self.assertIn("not a canonical ontology", whitepaper_prose)
        self.assertIn("global entity resolution as a source of truth", blueprint)
        self.assertIn("Matching labels never authorize a silent identity merge", decision)
        self.assertIn("Inference is replaceable", decision)

    def test_v03246_release_surfaces_publish_the_doctrine(self) -> None:
        release = (KIT_ROOT / "docs" / "releases" / "v0.3.246.md").read_text(
            encoding="utf-8"
        )
        matrix = (KIT_ROOT / "docs" / "capability-matrix.md").read_text(
            encoding="utf-8"
        )
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")

        self.assertIn("# v0.3.246 - Artifact Primacy And Human Drift", release)
        self.assertIn("Artifact primacy and human drift doctrine", matrix)
        self.assertIn("an artifact-first human-memory doctrine", readme)
        self.assertIn("아티팩트 우선 인간 기억 원칙", readme_ko)

    def test_runtime_operator_surfaces_apply_the_doctrine(self) -> None:
        skill_root = KIT_ROOT / "templates" / "ai-runtime" / "wom-archive"
        skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        reading = (skill_root / "references" / "reading-memory-and-revision.md").read_text(
            encoding="utf-8"
        )
        capture = (skill_root / "references" / "capture-draft-and-publication.md").read_text(
            encoding="utf-8"
        )
        operator = (skill_root / "references" / "operator-contract.md").read_text(
            encoding="utf-8"
        )
        skill_prose = " ".join(skill.split())
        reading_prose = " ".join(reading.split())
        capture_prose = " ".join(capture.split())

        for phrase in (
            "time-situated artifacts and their chronology as primary evidence",
            "`canonical` means the current human-reviewed archive state",
            "Matching names or labels never authorize a silent identity merge",
        ):
            with self.subTest(surface="runtime-skill", phrase=phrase):
                self.assertIn(phrase, skill_prose)

        self.assertIn("Preserve Human Change Without Inventing Entity Certainty", reading)
        self.assertIn("never as proof of one identity or one stable meaning", reading_prose)
        self.assertIn("A matching name or label is not permission", capture_prose)
        self.assertIn("ARTIFACT PRIMACY AND HUMAN DRIFT", operator)

        for profile in ("personal", "company", "family"):
            agents = (KIT_ROOT / "templates" / profile / "AGENTS.md").read_text(
                encoding="utf-8"
            )
            with self.subTest(profile=profile):
                self.assertIn("ARTIFACT PRIMACY AND HUMAN DRIFT", agents)
                self.assertIn("Matching names or labels never authorize", agents)

    def test_v03247_release_surfaces_publish_runtime_enforcement_boundary(self) -> None:
        release = (KIT_ROOT / "docs" / "releases" / "v0.3.247.md").read_text(
            encoding="utf-8"
        )
        decision = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-15-v03247-runtime-artifact-primacy.md"
        ).read_text(encoding="utf-8")
        matrix = (KIT_ROOT / "docs" / "capability-matrix.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("# v0.3.247 - Runtime Artifact Primacy", release)
        self.assertIn("Status: Accepted for v0.3.247", decision)
        self.assertIn("implemented runtime operator contract", matrix)
        for text in (release, decision):
            with self.subTest(document=text[:40]):
                self.assertIn("matching names or labels", text.lower())
                self.assertIn("no entity resolver", text.lower())


if __name__ == "__main__":
    unittest.main()
