from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PUBLIC_TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".json5",
    ".yml",
    ".yaml",
    ".toml",
    ".py",
    ".html",
    ".css",
    ".js",
    ".ts",
}
PRIVATE_PATH_PREFIXES = ("meeting-minutes/",)
PRIVATE_FILE_PREFIXES = ("archive-infra-decision-log-",)
PLACEHOLDER_MARKERS = (
    "example",
    "placeholder",
    "fake",
    "sample",
    "demo",
    "redacted",
    "never put",
    "<",
)
PLACEHOLDER_USER_SEGMENTS = {"example", "placeholder", "sample", "demo", "user", "username"}

WINDOWS_USER_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/]+Users[\\/]+([^\\/\s`\"'<>|]+)[\\/]+[^\s`\"'<>|]+")
POSIX_USER_PATH_RE = re.compile(r"(?<!\w)/(?:Users|home)/([^/\s`\"'<>|]+)/[^\s`\"'<>|]+")
TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GitHub classic token", re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
)
PRIVATE_KEY_HEADER_RE = re.compile(
    r"BEGIN (?:RSA |OPENSSH |DSA |EC )?PRIVATE KEY",
    re.IGNORECASE,
)
SEED_PHRASE_RE = re.compile(
    r"\b(seed phrase|mnemonic|recovery phrase)\s*[:=]\s*([^\n\r]+)",
    re.IGNORECASE,
)
PRIVATE_URL_RE = re.compile(
    r"\bhttp://(?:localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(?::\d+)?(?:/[^\s`\"'<>)]*)?",
    re.IGNORECASE,
)
CREDENTIAL_URL_RE = re.compile(
    r"\bhttps?://[^\s`\"'<>/@:]+(?::[^\s`\"'<>/@]+)?@[^\s`\"'<>/]+(?:/[^\s`\"'<>)]*)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PrivacyProblem:
    file: str
    message: str
    snippet: str

    def format(self) -> str:
        return f"{self.file}: {self.message}\n  text: {self.snippet}"


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


def is_public_text_path(path: str) -> bool:
    if path.startswith(PRIVATE_PATH_PREFIXES):
        return False
    if any(Path(path).name.startswith(prefix) for prefix in PRIVATE_FILE_PREFIXES):
        return False
    return Path(path).suffix.lower() in PUBLIC_TEXT_SUFFIXES


def public_text_files(paths: list[str]) -> list[str]:
    return sorted(path for path in paths if is_public_text_path(path))


def has_placeholder_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def is_placeholder_user_segment(user_segment: str) -> bool:
    return user_segment.lower() in PLACEHOLDER_USER_SEGMENTS


def safe_snippet(value: str, limit: int = 160) -> str:
    text = " ".join(value.strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def placeholder_context(text: str, start: int, end: int, radius: int = 40) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def redact_url_userinfo(value: str) -> str:
    return re.sub(r"^(https?://)[^@/\s]+@", r"\1<redacted-userinfo>@", value, flags=re.IGNORECASE)


def credential_url_has_placeholder_userinfo(value: str) -> bool:
    without_scheme = re.sub(r"^https?://", "", value, flags=re.IGNORECASE)
    userinfo = without_scheme.split("@", 1)[0]
    return has_placeholder_marker(userinfo)


def check_text_for_privacy(*, path: str, text: str) -> list[PrivacyProblem]:
    problems: list[PrivacyProblem] = []

    for pattern, message in (
        (WINDOWS_USER_PATH_RE, "Local Windows user-home path must not appear in public files."),
        (POSIX_USER_PATH_RE, "Local macOS/Linux user-home path must not appear in public files."),
    ):
        for match in pattern.finditer(text):
            user_segment = match.group(1)
            if is_placeholder_user_segment(user_segment):
                continue
            problems.append(PrivacyProblem(path, message, safe_snippet(match.group(0))))

    for label, pattern in TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            token = match.group(0)
            if has_placeholder_marker(token):
                continue
            problems.append(PrivacyProblem(path, f"{label} pattern must not appear in public files.", safe_snippet(token)))

    for match in PRIVATE_KEY_HEADER_RE.finditer(text):
        value = match.group(0)
        if has_placeholder_marker(value):
            continue
        problems.append(PrivacyProblem(path, "Private key block header must not appear in public files.", safe_snippet(value)))

    for match in SEED_PHRASE_RE.finditer(text):
        value = match.group(2)
        if has_placeholder_marker(value):
            continue
        problems.append(PrivacyProblem(path, "Seed phrase, mnemonic, or recovery phrase text must be placeholder-only.", safe_snippet(match.group(0))))

    for match in PRIVATE_URL_RE.finditer(text):
        context = placeholder_context(text, match.start(), match.end())
        if has_placeholder_marker(context):
            continue
        problems.append(PrivacyProblem(path, "Private/local provider URL must not appear in public files.", safe_snippet(match.group(0))))

    for match in CREDENTIAL_URL_RE.finditer(text):
        value = match.group(0)
        if credential_url_has_placeholder_userinfo(value):
            continue
        problems.append(PrivacyProblem(path, "Credential-bearing URL must not appear in public files.", safe_snippet(redact_url_userinfo(value))))

    return problems


def check_public_privacy(repo_root: Path) -> list[PrivacyProblem]:
    paths = run_git_ls_files(repo_root)
    problems: list[PrivacyProblem] = []
    for text_path in public_text_files(paths):
        text = (repo_root / text_path).read_text(encoding="utf-8", errors="replace")
        problems.extend(check_text_for_privacy(path=text_path, text=text))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check public files for obvious local path, token, seed phrase, and private URL leaks.")
    parser.add_argument("--repo-root", default=None, help="Repository root. Defaults to the script's repository.")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_script()

    try:
        problems = check_public_privacy(repo_root)
    except Exception as exc:
        print(f"public privacy hygiene check failed to run: {exc}", file=sys.stderr)
        return 2

    if problems:
        print("Public privacy hygiene check found problems:")
        for problem in problems:
            print()
            print(problem.format())
        print()
        print("Remove real local paths, tokens, private keys, seed phrases, and private/local provider URLs from public files.")
        return 1

    print("Public privacy hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
