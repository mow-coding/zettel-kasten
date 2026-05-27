from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True)
class ReleaseCheck:
    name: str
    script_path: str


@dataclass(frozen=True)
class ReleaseCheckResult:
    check: ReleaseCheck
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0


Runner = Callable[..., subprocess.CompletedProcess[str]]

RELEASE_CHECKS: tuple[ReleaseCheck, ...] = (
    ReleaseCheck("public link hygiene", "wom-kit/tools/check_public_links.py"),
    ReleaseCheck("Korean product-language hygiene", "wom-kit/tools/check_korean_product_language.py"),
    ReleaseCheck("public privacy hygiene", "wom-kit/tools/check_public_privacy.py"),
)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def run_one_check(repo_root: Path, check: ReleaseCheck, runner: Runner = subprocess.run) -> ReleaseCheckResult:
    result = runner(
        [sys.executable, str(repo_root / check.script_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return ReleaseCheckResult(
        check=check,
        returncode=result.returncode,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
    )


def run_release_checks(repo_root: Path, runner: Runner = subprocess.run) -> list[ReleaseCheckResult]:
    return [run_one_check(repo_root, check, runner) for check in RELEASE_CHECKS]


def print_failure_output(result: ReleaseCheckResult) -> None:
    if result.stdout.strip():
        print()
        print(f"--- {result.check.name} stdout ---")
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print()
        print(f"--- {result.check.name} stderr ---")
        print(result.stderr.rstrip())


def summarize_results(results: Sequence[ReleaseCheckResult]) -> int:
    print("Release readiness gate:")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"- {status}: {result.check.name} ({result.check.script_path})")
        if not result.passed:
            print_failure_output(result)
    return 0 if all(result.passed for result in results) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local public-release readiness hygiene checks.")
    parser.add_argument("--repo-root", default=None, help="Repository root. Defaults to the script's repository.")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_script()
    results = run_release_checks(repo_root)
    return summarize_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
