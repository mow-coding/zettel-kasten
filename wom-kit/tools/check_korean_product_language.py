from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


BASELINE_PATH = "wom-kit/docs/concepts/korean-product-language-baseline.ko.md"
PRIVATE_MARKDOWN_PREFIXES = ("meeting-minutes/",)
PRIVATE_MARKDOWN_FILES = ("archive-infra-decision-log-",)

BASELINE_ANCHORS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("WOM pronunciation", ("WOM", "옴")),
    ("zettel-kasten Korean explanation", ("zettel-kasten", "기록 계층")),
    ("zet Korean explanation", ("zet", "쪽글|토막글")),
    ("ZET Korean explanation", ("ZET", "공유 계층")),
    ("objet Korean explanation", ("objet", "오브제")),
    ("mint Korean product verb", ("mint", "발행")),
    ("delegate Korean product verb", ("delegate", "공유")),
    ("attest Korean product verb", ("attest", "수용")),
    ("anchor Korean product verb", ("anchor", "반영")),
    ("attest + anchor renewal", ("attest + anchor", "갱신")),
    ("foreign block Korean product term", ("foreign block", "소포")),
    ("quarantine Korean product term", ("quarantine", "검문소")),
    ("trust Korean product term", ("trust", "인증")),
    ("import Korean product term", ("import", "반입")),
    ("acceptance Korean product term", ("acceptance", "채택")),
    ("block Korean product term", ("block", "상자")),
    ("header Korean product term", ("header", "초록")),
    ("body Korean product term", ("body", "본문")),
    ("radio-frequency Korean product term", ("radio-frequency", "라디오 주파수 방식")),
    ("key-sharing Korean product term", ("key-sharing", "키 방식")),
    ("mirroring Korean product term", ("mirroring", "미러링 방식")),
    ("projection Korean product term", ("projection", "구현")),
    ("surface Korean product term", ("surface", "수제 앱")),
    ("prompt-as-algorithm Korean product term", ("prompt-as-algorithm", "수제 알고리즘")),
    ("neighbor Korean product term", ("neighbor", "이웃")),
    ("feed Korean product term", ("feed", "담벼락")),
    ("broadcast Korean product term", ("broadcast", "송출")),
    ("receipt Korean product term", ("receipt", "영수증")),
    ("provenance Korean product term", ("provenance", "족보")),
    ("canonical Korean product term", ("canonical", "정본")),
    ("node Korean product term", ("node", "노드")),
    ("messenger-type ZET thread Korean term", ("메신저형 ZET", "스레드")),
    ("SNS-type followed update phrase", ("SNS형 ZET", "젯 갱신하기")),
    ("SNS-type recommendation phrase", ("SNS형 ZET", "쿠키 굽기")),
)

CURRENT_FACING_VARIANTS = ("Wo" + "m", "Wo" + "M", "Ze" + "t", "Ze" + "ts")
CURRENT_FACING_VARIANT_RE = re.compile(r"\b(?:" + "|".join(CURRENT_FACING_VARIANTS) + r")\b")
TAGLINE_DRIFT = "기억 지평"
THREAD_RISK_RE = re.compile(
    r"스레드[^\n]*(?:blockchain|cryptocurrency|mining|staking|consensus|public ledger|trustless public chain|블록체인|암호화폐|채굴|스테이킹|합의|공개 원장)",
    re.IGNORECASE,
)
THREAD_NEGATION_RE = re.compile(
    r"(?:아닙니다|아니다|뜻하지 않습니다|not|does not|is not|isn't|doesn't mean|not mean)",
    re.IGNORECASE,
)
WORDPRESS_CLAIM_RE = re.compile(
    r"WordPress(?:\s+(?:is|as|becomes|become)\b|\s*=|\s*(?:가|은|는))[^\n]{0,120}(?:WOM/ZET UI|WOM/ZET interface|WOM/ZET itself|WOM/ZET system itself|canonical UI|ZET transport|real ZET transport)",
    re.IGNORECASE,
)
WORDPRESS_NEGATIONS = ("not", "no ", "does not", "하지 않습니다", "아니", "아닙니다", "아닙니", "아니다")


@dataclass(frozen=True)
class LanguageProblem:
    file: str
    message: str
    snippet: str | None = None

    def format(self) -> str:
        if self.snippet:
            return f"{self.file}: {self.message}\n  text: {self.snippet}"
        return f"{self.file}: {self.message}"


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def run_git_ls_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git ls-files failed")
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def is_public_markdown(path: str) -> bool:
    if not path.lower().endswith(".md"):
        return False
    if path.startswith(PRIVATE_MARKDOWN_PREFIXES):
        return False
    name = Path(path).name
    if any(name.startswith(prefix) for prefix in PRIVATE_MARKDOWN_FILES):
        return False
    return True


def public_markdown_files(paths: list[str]) -> list[str]:
    return sorted(path for path in paths if is_public_markdown(path))


def _contains_anchor(text: str, anchor: str) -> bool:
    if "|" in anchor:
        return any(part in text for part in anchor.split("|"))
    return anchor in text


def _line_allows_wom_negative_phrase(line: str) -> bool:
    return "웜" in line and ("읽지 않습니다" in line or "not" in line.lower())


def _line_is_clear_denial(line: str) -> bool:
    return bool(THREAD_NEGATION_RE.search(line)) or any(negation in line for negation in WORDPRESS_NEGATIONS)


def _line_has_wordpress_risk_claim(line: str) -> bool:
    return bool(WORDPRESS_CLAIM_RE.search(line)) and not _line_is_clear_denial(line)


def check_baseline_text(*, markdown_path: str, text: str) -> list[LanguageProblem]:
    problems: list[LanguageProblem] = []
    for label, anchors in BASELINE_ANCHORS:
        missing = [anchor for anchor in anchors if not _contains_anchor(text, anchor)]
        if missing:
            problems.append(
                LanguageProblem(
                    markdown_path,
                    f"Missing Korean product-language baseline anchor for {label}: {', '.join(missing)}",
                )
            )

    for line in text.splitlines():
        if "웜" in line and not _line_allows_wom_negative_phrase(line):
            problems.append(
                LanguageProblem(
                    markdown_path,
                    "`웜` may appear only in the negative pronunciation phrase.",
                    line.strip(),
                )
            )
    return problems


def check_public_markdown_text(*, markdown_path: str, text: str) -> list[LanguageProblem]:
    problems: list[LanguageProblem] = []

    for match in CURRENT_FACING_VARIANT_RE.finditer(text):
        problems.append(
            LanguageProblem(
                markdown_path,
                "Current-facing docs must use `WOM`, `zet`, and `ZET`, not mixed-case variants.",
                match.group(0),
            )
        )

    if TAGLINE_DRIFT in text:
        problems.append(
            LanguageProblem(
                markdown_path,
                "Do not drift the WOM tagline back to `기억 지평`; use `인간 인식의 지평`.",
                TAGLINE_DRIFT,
            )
        )

    for line in text.splitlines():
        if "웜" in line and not _line_allows_wom_negative_phrase(line):
            problems.append(
                LanguageProblem(
                    markdown_path,
                    "Do not explain `WOM` as `웜`; `웜` is allowed only in the negative pronunciation phrase.",
                    line.strip(),
                )
            )
        if THREAD_RISK_RE.search(line) and not _line_is_clear_denial(line):
            problems.append(
                LanguageProblem(
                    markdown_path,
                    "Do not describe messenger-type `스레드` as blockchain, cryptocurrency, mining, staking, consensus, or public-ledger technology.",
                    line.strip(),
                )
            )
        if _line_has_wordpress_risk_claim(line):
            problems.append(
                LanguageProblem(
                    markdown_path,
                    "Do not claim WordPress is the WOM/ZET UI, canonical UI, ZET transport, or real ZET transport.",
                    line.strip(),
                )
            )
    return problems


def check_korean_product_language(repo_root: Path) -> list[LanguageProblem]:
    paths = run_git_ls_files(repo_root)
    public_docs = public_markdown_files(paths)
    problems: list[LanguageProblem] = []

    if BASELINE_PATH not in paths:
        problems.append(LanguageProblem(BASELINE_PATH, "Required Korean product-language baseline document is missing."))
    else:
        baseline_text = (repo_root / BASELINE_PATH).read_text(encoding="utf-8")
        problems.extend(check_baseline_text(markdown_path=BASELINE_PATH, text=baseline_text))

    for markdown_path in public_docs:
        text = (repo_root / markdown_path).read_text(encoding="utf-8")
        problems.extend(check_public_markdown_text(markdown_path=markdown_path, text=text))

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Korean product-language baseline hygiene in public docs.")
    parser.add_argument("--repo-root", default=None, help="Repository root. Defaults to the script's repository.")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_script()

    try:
        problems = check_korean_product_language(repo_root)
    except Exception as exc:
        print(f"Korean product-language hygiene check failed to run: {exc}", file=sys.stderr)
        return 2

    if problems:
        print("Korean product-language hygiene check found problems:")
        for problem in problems:
            print()
            print(problem.format())
        print()
        print("Keep Korean product-language terms aligned with wom-kit/docs/concepts/korean-product-language-baseline.ko.md.")
        return 1

    print("Korean product-language hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
