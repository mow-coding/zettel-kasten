from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


DURABLE_ARCHIVE_RECORD = "DURABLE_ARCHIVE_RECORD"
DURABLE_UNTIL_RESOLVED = "DURABLE_UNTIL_RESOLVED"
DURABLE_WITH_EXPIRY = "DURABLE_WITH_EXPIRY"
REBUILDABLE_GENERATED = "REBUILDABLE_GENERATED"
DISPOSABLE_AFTER_REVIEW = "DISPOSABLE_AFTER_REVIEW"
LOCAL_ONLY_SECRET_CONFIG = "LOCAL_ONLY_SECRET_CONFIG"
EXTERNAL_LIVE_NEVER_TOUCH = "EXTERNAL_LIVE_NEVER_TOUCH"
EXTERNAL_MANUAL_OR_DEFERRED = "EXTERNAL_MANUAL_OR_DEFERRED"
LOCAL_ONLY_COLLAB_HARNESS = "LOCAL_ONLY_COLLAB_HARNESS"
UNCLASSIFIED_REVIEW = "UNCLASSIFIED_REVIEW"

REQUIRED_ARCHIVE_GITIGNORE_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "!.env.example",
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.kdbx",
    "secrets/",
    "profiles/local/",
    "profiles/*.local.yml",
    "keyrings/local/",
    "keyrings/*.local.yml",
    ".archive-local/",
    "rclone.conf",
    "credentials.json",
    "token.json",
    "tmp/",
    ".wom-scratch/",
    "workbench/ai-scratch/",
    "node_modules/",
    ".next/",
    ".vercel/",
    "/collab/",
    "/.mow-harness/",
    "**/db/archive-index.sqlite",
    "**/db/archive-index.sqlite-wal",
    "**/db/archive-index.sqlite-shm",
    "**/db/archive-index.sqlite-journal",
    "objects/sha256/",
    "objects/derived-text/sha256/",
    "/objets/",
)

SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
}

COLLAB_HARNESS_DIRS = {"collab", ".mow-harness"}


@dataclass(frozen=True)
class ArtifactObservation:
    path: str
    category: str
    note: str

    def format(self) -> str:
        return f"{self.path}: {self.category} - {self.note}"


@dataclass(frozen=True)
class HygieneProblem:
    path: str
    message: str
    severity: str = "error"

    def format(self) -> str:
        return f"{self.severity.upper()}: {self.path}: {self.message}"


@dataclass(frozen=True)
class HygieneReport:
    target: str
    observations: tuple[ArtifactObservation, ...]
    problems: tuple[HygieneProblem, ...]

    @property
    def passed(self) -> bool:
        return not self.problems

    def category_counts(self) -> Counter[str]:
        return Counter(observation.category for observation in self.observations)


def normalize_relative_path(path: str | Path) -> str:
    return str(path).replace("\\", "/").strip("/")


def starts_with_path(path: str, prefix: str) -> bool:
    normalized = normalize_relative_path(path).lower()
    clean_prefix = normalize_relative_path(prefix).lower()
    return normalized == clean_prefix or normalized.startswith(clean_prefix + "/")


def has_part_starting_with(path: str, prefix: str) -> bool:
    return any(part.lower().startswith(prefix.lower()) for part in normalize_relative_path(path).split("/"))


def classify_artifact(relative_path: str) -> ArtifactObservation:
    path = normalize_relative_path(relative_path)
    lower = path.lower()
    name = Path(path).name.lower()

    if lower in {".env", "rclone.conf", "credentials.json", "token.json"}:
        return ArtifactObservation(path, LOCAL_ONLY_SECRET_CONFIG, "local-only secret/config file")
    if name.endswith((".key", ".pem", ".p12", ".pfx", ".kdbx")):
        return ArtifactObservation(path, LOCAL_ONLY_SECRET_CONFIG, "local-only key or credential material")
    if name.startswith(".env.") and name != ".env.example":
        return ArtifactObservation(path, LOCAL_ONLY_SECRET_CONFIG, "local-only env variant")
    if starts_with_path(path, "profiles/local") or starts_with_path(path, "keyrings/local"):
        return ArtifactObservation(path, LOCAL_ONLY_SECRET_CONFIG, "ignored local profile or keyring state")
    if starts_with_path(path, ".archive-local") or starts_with_path(path, "secrets"):
        return ArtifactObservation(path, LOCAL_ONLY_SECRET_CONFIG, "ignored local-only private state")
    if name.endswith(".local.yml") and (starts_with_path(path, "profiles") or starts_with_path(path, "keyrings")):
        return ArtifactObservation(path, LOCAL_ONLY_SECRET_CONFIG, "ignored local profile/keyring override")

    if lower == "collab" or lower.startswith("collab/") or lower == ".mow-harness" or lower.startswith(".mow-harness/"):
        return ArtifactObservation(path, LOCAL_ONLY_COLLAB_HARNESS, "local-only collaboration or harness state")

    if lower in {
        "db/archive-index.sqlite",
        "db/archive-index.sqlite-wal",
        "db/archive-index.sqlite-shm",
        "db/archive-index.sqlite-journal",
    }:
        return ArtifactObservation(path, REBUILDABLE_GENERATED, "generated SQLite search index")

    if lower == "tmp" or lower.startswith("tmp/") or has_part_starting_with(path, "tmp-"):
        return ArtifactObservation(path, DISPOSABLE_AFTER_REVIEW, "temporary artifact; cleanup requires review")
    if lower == ".wom-scratch" or lower.startswith(".wom-scratch/") or starts_with_path(path, "workbench/ai-scratch"):
        return ArtifactObservation(path, DISPOSABLE_AFTER_REVIEW, "AI scratch artifact; cleanup requires review")
    if lower == "node_modules" or lower.startswith("node_modules/") or lower == ".next" or lower.startswith(".next/"):
        return ArtifactObservation(path, REBUILDABLE_GENERATED, "web/app dependency or build artifact; keep outside WOM archive root")
    if lower == ".vercel" or lower.startswith(".vercel/"):
        return ArtifactObservation(path, LOCAL_ONLY_SECRET_CONFIG, "Vercel project state is local-only provider configuration")
    if "dry-run" in lower or "sandbox" in lower:
        return ArtifactObservation(path, DISPOSABLE_AFTER_REVIEW, "sandbox or dry-run artifact; cleanup requires review")

    if lower == "inbox" or lower.startswith("inbox/"):
        return ArtifactObservation(path, DURABLE_UNTIL_RESOLVED, "draft or pending AI work until minted/deferred/abandoned")
    if lower == "workpacks" or lower.startswith("workpacks/"):
        return ArtifactObservation(path, DURABLE_WITH_EXPIRY, "portable transfer/export record with expiry review")

    durable_exact = {
        ".env.example",
        ".gitignore",
        "agents.md",
        "archive.yml",
        "archive-identity.yml",
        "db/schema.sql",
        "provider-bindings.yml",
        "source-bindings.yml",
    }
    if lower in durable_exact:
        return ArtifactObservation(path, DURABLE_ARCHIVE_RECORD, "archive control or placeholder record")
    for prefix in (
        "zettels",
        "objects/manifests",
        "objects/sha256",
        "objects/derived-text/sha256",
        "source-maps",
        "receipts",
        "views",
    ):
        if starts_with_path(path, prefix):
            return ArtifactObservation(path, DURABLE_ARCHIVE_RECORD, "archive memory, manifest, source map, receipt, or view")

    if lower.endswith("-objets") or "/-objets/" in lower:
        return ArtifactObservation(path, EXTERNAL_LIVE_NEVER_TOUCH, "real local objet store must never be auto-touched")

    return ArtifactObservation(path, UNCLASSIFIED_REVIEW, "not classified by the current report-only rules")


def target_looks_external_live_never_touch(target: Path) -> bool:
    parts = [part.lower() for part in target.resolve().parts]
    if any(part.startswith("zettel-kasten-") for part in parts):
        return True
    if any(part.endswith("-objets") for part in parts):
        return True
    return False


def target_looks_like_archive(target: Path) -> bool:
    return (target / "archive.yml").exists() or (target / "archive-identity.yml").exists()


def read_gitignore_patterns(target: Path) -> set[str]:
    gitignore = target / ".gitignore"
    if not gitignore.exists():
        return set()
    patterns: set[str] = set()
    for line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.add(stripped)
    return patterns


def check_archive_gitignore(target: Path) -> list[HygieneProblem]:
    if not target_looks_like_archive(target):
        return []

    gitignore = target / ".gitignore"
    if not gitignore.exists():
        return [
            HygieneProblem(
                ".gitignore",
                "Generated archive .gitignore is missing; local-only secrets, collaboration state, and indexes may be exposed.",
            )
        ]

    patterns = read_gitignore_patterns(target)
    missing = [pattern for pattern in REQUIRED_ARCHIVE_GITIGNORE_PATTERNS if pattern not in patterns]
    return [
        HygieneProblem(
            ".gitignore",
            f"Missing generated archive .gitignore pattern: {pattern}",
        )
        for pattern in missing
    ]


def iter_observable_paths(target: Path, max_paths: int) -> tuple[list[Path], bool]:
    observed: list[Path] = []
    pending: list[Path] = [target]
    truncated = False

    while pending:
        current = pending.pop()
        try:
            children = sorted(current.iterdir(), key=lambda child: child.name.lower())
        except OSError:
            continue
        for child in children:
            if len(observed) >= max_paths:
                truncated = True
                return observed, truncated
            if child.name in SKIP_DIR_NAMES:
                continue
            observed.append(child)
            if child.is_dir() and child.name not in COLLAB_HARNESS_DIRS:
                pending.append(child)

    return observed, truncated


def check_artifact_hygiene(
    target: Path,
    *,
    allow_external_live_read: bool = False,
    max_paths: int = 1000,
) -> HygieneReport:
    resolved = target.resolve()
    if not resolved.exists():
        return HygieneReport(
            target=str(resolved),
            observations=(),
            problems=(HygieneProblem(str(resolved), "Target path does not exist."),),
        )

    if target_looks_external_live_never_touch(resolved) and not allow_external_live_read:
        return HygieneReport(
            target=str(resolved),
            observations=(),
            problems=(
                HygieneProblem(
                    str(resolved),
                    "Target is classified as EXTERNAL_LIVE_NEVER_TOUCH and was not scanned. Use explicit human approval before any read-only inspection.",
                    severity="blocker",
                ),
            ),
        )

    observed_paths, truncated = iter_observable_paths(resolved, max_paths=max_paths)
    observations = tuple(
        classify_artifact(path.relative_to(resolved).as_posix())
        for path in observed_paths
    )
    problems = list(check_archive_gitignore(resolved))

    for observation in observations:
        if observation.category == LOCAL_ONLY_SECRET_CONFIG and not target_looks_like_archive(resolved):
            problems.append(
                HygieneProblem(
                    observation.path,
                    "Local-only secret/config artifact found outside a recognized archive; verify it is ignored and not public.",
                    severity="warning",
                )
            )

    if truncated:
        problems.append(
            HygieneProblem(
                str(resolved),
                f"Path scan stopped after {max_paths} entries; rerun with a higher --max-paths only after confirming the target is safe to inspect.",
                severity="warning",
            )
        )

    return HygieneReport(target=str(resolved), observations=observations, problems=tuple(problems))


def print_report(report: HygieneReport) -> None:
    print("WOM artifact hygiene report")
    print(f"Target: {report.target}")
    print()

    if report.observations:
        print("Artifact classes:")
        for category, count in sorted(report.category_counts().items()):
            print(f"- {category}: {count}")
    else:
        print("Artifact classes: none scanned")

    if report.problems:
        print()
        print("Findings:")
        for problem in report.problems:
            print(f"- {problem.format()}")
    else:
        print()
        print("Findings: none")

    print()
    if report.passed:
        print("Artifact hygiene check passed.")
    else:
        print("Artifact hygiene check found report-only findings. No files were changed.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report-only WOM artifact hygiene checker. Never deletes, moves, uploads, or rewrites files.")
    parser.add_argument("--target", required=True, help="Archive, throwaway archive, or explicitly approved path to inspect.")
    parser.add_argument(
        "--allow-external-live-read",
        action="store_true",
        help="Allow read-only path-name inspection of a target that looks like a real archive or local -objets store.",
    )
    parser.add_argument("--max-paths", type=int, default=1000, help="Maximum number of paths to classify before stopping.")
    args = parser.parse_args(argv)

    try:
        report = check_artifact_hygiene(
            Path(args.target),
            allow_external_live_read=args.allow_external_live_read,
            max_paths=args.max_paths,
        )
    except Exception as exc:
        print(f"artifact hygiene check failed to run: {exc}", file=sys.stderr)
        return 2

    print_report(report)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
