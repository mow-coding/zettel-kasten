from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


REPO_OWNER = "mow-coding"
REPO_NAME = "zettel-kasten"
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:")


@dataclass(frozen=True)
class LinkProblem:
    file: str
    link: str
    message: str

    def format(self) -> str:
        return f"{self.file}: {self.message}\n  link: {self.link}"


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


def tracked_markdown_files(tracked: set[str]) -> list[str]:
    return sorted(path for path in tracked if path.lower().endswith(".md"))


def split_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if "#" in target:
        target = target.split("#", 1)[0]
    return unquote(target)


def is_ignored_link(raw_target: str) -> bool:
    target = raw_target.strip()
    return not target or target.startswith("#") or target.startswith(EXTERNAL_PREFIXES)


def is_release_note(markdown_path: str) -> bool:
    return markdown_path.startswith("wom-kit/docs/releases/") and markdown_path.endswith(".md")


def resolve_repo_local_link(markdown_path: str, target: str) -> str:
    base = Path(markdown_path).parent
    resolved = (base / target).as_posix()
    parts: list[str] = []
    for part in resolved.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            else:
                parts.append(part)
        else:
            parts.append(part)
    return "/".join(parts)


def directory_exists(repo_root: Path, repo_relative_path: str, tracked: set[str] | None = None) -> bool:
    if not (repo_root / repo_relative_path).is_dir():
        return False
    if tracked is None:
        return True
    prefix = repo_relative_path.rstrip("/") + "/"
    return any(path.startswith(prefix) for path in tracked)


def github_tree_directory_path(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 5:
        return None
    owner, repo, kind = parts[0], parts[1], parts[2]
    if owner != REPO_OWNER or repo != REPO_NAME or kind != "tree":
        return None
    path = "/".join(parts[4:])
    if Path(path).suffix:
        return None
    return path


def github_file_path_from_blob_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.netloc.lower() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 5:
        return None
    owner, repo, kind = parts[0], parts[1], parts[2]
    if owner != REPO_OWNER or repo != REPO_NAME:
        return None
    if kind != "blob":
        return None
    return "/".join(parts[4:])


def github_tree_file_like_path(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 5:
        return None
    owner, repo, kind = parts[0], parts[1], parts[2]
    if owner != REPO_OWNER or repo != REPO_NAME or kind != "tree":
        return None
    path = "/".join(parts[4:])
    if Path(path).suffix:
        return path
    return None


def check_markdown_text(
    *,
    markdown_path: str,
    text: str,
    tracked: set[str],
    repo_root: Path,
) -> list[LinkProblem]:
    problems: list[LinkProblem] = []
    for match in MARKDOWN_LINK_RE.finditer(text):
        raw_target = match.group(2).strip()
        target = split_link_target(raw_target)
        if is_ignored_link(raw_target):
            if raw_target.startswith("https://github.com/") or raw_target.startswith("http://github.com/"):
                tree_file_path = github_tree_file_like_path(raw_target)
                if tree_file_path:
                    problems.append(
                        LinkProblem(
                            markdown_path,
                            raw_target,
                            "GitHub file links must use /blob/ rather than /tree/.",
                        )
                    )
                tree_dir_path = github_tree_directory_path(raw_target)
                if tree_dir_path is not None and not directory_exists(repo_root, tree_dir_path, tracked):
                    problems.append(
                        LinkProblem(
                            markdown_path,
                            raw_target,
                            "GitHub tree link points to a directory that does not exist in this repository.",
                        )
                    )
                blob_path = github_file_path_from_blob_url(raw_target)
                if blob_path is not None and blob_path not in tracked:
                    problems.append(
                        LinkProblem(
                            markdown_path,
                            raw_target,
                            "GitHub blob link points to a file that is not tracked in this repository.",
                        )
                    )
            continue

        if is_release_note(markdown_path):
            problems.append(
                LinkProblem(
                    markdown_path,
                    raw_target,
                    "Release notes are copied into GitHub Release bodies; use an absolute GitHub blob URL for repository file links or an absolute GitHub tree URL for directory links.",
                )
            )
            continue

        resolved = resolve_repo_local_link(markdown_path, target)
        if resolved in tracked:
            continue
        if target.endswith("/") and directory_exists(repo_root, resolved, tracked):
            continue
        problems.append(
            LinkProblem(
                markdown_path,
                raw_target,
                "Repo-local Markdown link does not resolve to a tracked file or existing directory with case-sensitive path matching.",
            )
        )
    return problems


def check_public_links(repo_root: Path) -> list[LinkProblem]:
    tracked = set(run_git_ls_files(repo_root))
    problems: list[LinkProblem] = []
    for markdown_path in tracked_markdown_files(tracked):
        text = (repo_root / markdown_path).read_text(encoding="utf-8")
        problems.extend(
            check_markdown_text(
                markdown_path=markdown_path,
                text=text,
                tracked=tracked,
                repo_root=repo_root,
            )
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check repository Markdown links for public release hygiene.")
    parser.add_argument("--repo-root", default=None, help="Repository root. Defaults to the script's repository.")
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_script()

    try:
        problems = check_public_links(repo_root)
    except Exception as exc:
        print(f"public link hygiene check failed to run: {exc}", file=sys.stderr)
        return 2

    if problems:
        print("Public link hygiene check found problems:")
        for problem in problems:
            print()
            print(problem.format())
        print()
        print("Use repo-local links in normal Markdown docs, but use absolute GitHub /blob/ URLs for links that may be copied into GitHub Release bodies.")
        return 1

    print("Public link hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
