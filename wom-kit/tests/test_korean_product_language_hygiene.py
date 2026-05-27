from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent
CHECKER_PATH = KIT_ROOT / "tools" / "check_korean_product_language.py"

spec = importlib.util.spec_from_file_location("check_korean_product_language", CHECKER_PATH)
assert spec is not None and spec.loader is not None
check_korean_product_language = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_korean_product_language
spec.loader.exec_module(check_korean_product_language)


class KoreanProductLanguageHygieneTests(unittest.TestCase):
    def assert_problem_contains(self, problems, needle: str) -> None:
        formatted = "\n".join(problem.format() for problem in problems)
        self.assertIn(needle, formatted)

    def test_full_checker_passes_current_repository(self) -> None:
        problems = check_korean_product_language.check_korean_product_language(REPO_ROOT)
        self.assertEqual([problem.format() for problem in problems], [])

    def test_missing_required_anchor_fails_with_useful_message(self) -> None:
        baseline_path = REPO_ROOT / check_korean_product_language.BASELINE_PATH
        text = baseline_path.read_text(encoding="utf-8").replace("검문소", "")
        problems = check_korean_product_language.check_baseline_text(
            markdown_path=check_korean_product_language.BASELINE_PATH,
            text=text,
        )
        self.assert_problem_contains(problems, "quarantine Korean product term")
        self.assert_problem_contains(problems, "검문소")

    def test_wom_as_worm_fails_but_negative_phrase_is_allowed(self) -> None:
        ok = check_korean_product_language.check_public_markdown_text(
            markdown_path="README.ko.md",
            text="`WOM`은 `옴`이고 `웜`이라고 읽지 않습니다.",
        )
        self.assertEqual(ok, [])

        problems = check_korean_product_language.check_public_markdown_text(
            markdown_path="README.ko.md",
            text="`WOM`은 `웜`입니다.",
        )
        self.assert_problem_contains(problems, "Do not explain `WOM` as `웜`")

    def test_memory_horizon_tagline_drift_fails(self) -> None:
        problems = check_korean_product_language.check_public_markdown_text(
            markdown_path="README.ko.md",
            text="WOM은 기억 지평을 넓히는 시스템입니다.",
        )
        self.assert_problem_contains(problems, "기억 지평")

    def test_current_facing_spelling_variants_fail(self) -> None:
        variants = ("Wo" + "m", "Wo" + "M", "Ze" + "t", "Ze" + "ts")
        problems = check_korean_product_language.check_public_markdown_text(
            markdown_path="README.md",
            text=", ".join(variants) + " are stale current-facing spellings.",
        )
        self.assertEqual(len(problems), 4)
        self.assert_problem_contains(problems, "mixed-case variants")

    def test_thread_as_blockchain_technology_fails(self) -> None:
        problems = check_korean_product_language.check_public_markdown_text(
            markdown_path="wom-kit/docs/concepts/example.md",
            text="스레드는 blockchain consensus public ledger technology입니다.",
        )
        self.assert_problem_contains(problems, "Do not describe messenger-type `스레드`")

    def test_thread_as_blockchain_inline_denial_is_allowed(self) -> None:
        examples = [
            "스레드는 blockchain이 아닙니다.",
            "스레드는 블록체인이 아닙니다.",
            "스레드는 blockchain 기술 구현을 뜻하지 않습니다.",
            "thread is not blockchain.",
        ]
        for text in examples:
            with self.subTest(text=text):
                problems = check_korean_product_language.check_public_markdown_text(
                    markdown_path="wom-kit/docs/concepts/example.md",
                    text=text,
                )
                self.assertEqual(problems, [])

    def test_thread_as_consensus_public_ledger_claim_fails(self) -> None:
        problems = check_korean_product_language.check_public_markdown_text(
            markdown_path="wom-kit/docs/concepts/example.md",
            text="스레드는 consensus public ledger behavior입니다.",
        )
        self.assert_problem_contains(problems, "public-ledger technology")

    def test_wordpress_as_real_zet_transport_fails(self) -> None:
        problems = check_korean_product_language.check_public_markdown_text(
            markdown_path="wom-kit/docs/example.md",
            text="WordPress is real ZET transport.",
        )
        self.assert_problem_contains(problems, "WordPress")

    def test_korean_wordpress_as_wom_zet_ui_or_transport_fails(self) -> None:
        examples = [
            "WordPress가 WOM/ZET UI입니다.",
            "WordPress는 real ZET transport입니다.",
            "WordPress는 canonical UI입니다.",
        ]
        for text in examples:
            with self.subTest(text=text):
                problems = check_korean_product_language.check_public_markdown_text(
                    markdown_path="wom-kit/docs/example.md",
                    text=text,
                )
                self.assert_problem_contains(problems, "WordPress")

    def test_safe_wordpress_borrowed_surface_wording_is_allowed(self) -> None:
        examples = [
            "WordPress is a borrowed custom surface example.",
            "WordPress는 빌려온 수제 앱 surface 예시입니다.",
            "WordPress is not WOM/ZET itself.",
            "WordPress is not real ZET transport.",
        ]
        for text in examples:
            with self.subTest(text=text):
                problems = check_korean_product_language.check_public_markdown_text(
                    markdown_path="wom-kit/docs/example.md",
                    text=text,
                )
                self.assertEqual(problems, [])

    def test_checker_has_no_network_imports(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        banned = ("req" + "uests", "urllib" + ".request", "http" + ".client", "url" + "open")
        for needle in banned:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, source)


if __name__ == "__main__":
    unittest.main()
