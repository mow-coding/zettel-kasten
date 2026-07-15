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


if __name__ == "__main__":
    unittest.main()
