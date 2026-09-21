"""Classify exact Git changes and validate intentional CI omissions."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

DOC_FILES = frozenset({"CONTRIBUTING.md", "CLAUDE.md"})
DOC_PREFIXES = ("wom-kit/docs/development/",)
HEAVY_JOBS = ("tests", "doctor_scale", "link_index_scale", "installed_wheel")
SHA = re.compile(r"[0-9a-f]{40}\Z")


def documentation_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if not parts or path.startswith("/") or ".." in parts or "\\" in path:
        return False
    if path in DOC_FILES:
        return True
    if not path.endswith(".md"):
        return False
    return (path.startswith(DOC_PREFIXES)
            or (len(parts) == 2 and parts[0] == "meeting-minutes")
            or (len(parts) == 3 and parts[:2] == ("wom-kit", "docs")
                and parts[2].startswith("archive-infra-decision-log-")))


def classify(paths: list[str], *, event: str) -> str:
    # Explicit full verification stays available; an empty/unknown change is
    # never proof of a documentation-only change.
    if event == "pull_request" and paths and all(map(documentation_path, paths)):
        return "docs"
    if event == "push":
        return "post_merge"
    return "full"


def check_results(lane: str, needs: dict) -> list[str]:
    if lane not in {"docs", "full", "post_merge", "incremental"}:
        return ["invalid_lane"]
    expected = {"classify": "success", "gate": "success"}
    expected.update({name: "success" if lane == "full" else "skipped"
                     for name in HEAVY_JOBS})
    expected['focused'] = 'success' if lane == 'incremental' else 'skipped'
    return sorted(set(needs) - set(expected)) + [name for name, result in expected.items()
            if not isinstance(needs.get(name), dict)
            or needs[name].get("result") != result]


def changed_paths(base: str, head: str, *, cwd: Path | None = None) -> list[str]:
    if not SHA.fullmatch(base) or not SHA.fullmatch(head):
        raise ValueError("invalid_commit_identity")
    raw = subprocess.check_output(
        ["git", "diff", "--no-renames", "--name-only", "-z", base, head, "--"], cwd=cwd)
    return sorted(set(p.decode("utf-8", errors="strict") for p in raw.split(b"\0") if p))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-results", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.verify_results:
        lane = os.environ.get("CI_LANE", "")
        needs = json.loads(os.environ.get("CI_NEEDS_JSON", "{}"))
        failures = check_results(lane, needs)
        report = {"schema": "wom-kit/ci-result/v1", "lane": lane,
                  "ok": not failures, "unexpected_results": failures,
                  "commit": os.environ.get("GITHUB_SHA"), "jobs": needs}
        output = json.dumps(report, sort_keys=True)
        print(output)
        if args.output:
            args.output.write_text(output + "\n", encoding="utf-8")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write("### Required CI: " + ("passed" if not failures else "failed")
                        + "\n\n```json\n" + output + "\n```\n")
        return int(bool(failures))
    event = os.environ.get("GITHUB_EVENT_NAME", "workflow_dispatch")
    paths = []
    if event == "pull_request":
        paths = changed_paths(os.environ.get("CI_BASE_SHA", ""),
                              os.environ.get("CI_HEAD_SHA", ""))
    lane = classify(paths, event=event)
    if lane == 'full' and event == 'pull_request' and os.environ.get('CI_PR_NUMBER'):
        from incremental_ci import find_plan
        plan = find_plan(os.environ['GITHUB_REPOSITORY'], os.environ['CI_HEAD_SHA'],
                         int(os.environ['CI_PR_NUMBER']))
        if plan is not None:
            Path(os.environ['CI_PLAN_PATH']).write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
            lane = 'incremental'
    report = {"schema": "wom-kit/ci-change-plan/v1", "lane": lane,
              "base": os.environ.get("CI_BASE_SHA"), "head": os.environ.get("CI_HEAD_SHA"),
              "changed_path_count": len(paths),
              "changed_paths_sha256": hashlib.sha256(json.dumps(paths).encode()).hexdigest()}
    print(json.dumps(report, sort_keys=True))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"lane={lane}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
