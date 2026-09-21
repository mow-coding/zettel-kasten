"""Bind a main merge to a successful CI run over the identical source tree."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def gh_json(repo: str, endpoint: str):
    return json.loads(subprocess.check_output(
        ["gh", "api", f"repos/{repo}/{endpoint}"], text=True, encoding="utf-8"))


def verify(repo: str, commit: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("invalid_repository")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("invalid_source_commit")
    tree = gh_json(repo, f"git/commits/{commit}")["tree"]["sha"]
    pulls = gh_json(repo, f"commits/{commit}/pulls")
    for pr in pulls:
        if (not pr.get("merged_at") or pr["merge_commit_sha"] != commit
                or pr["base"]["ref"] != "main"):
            continue
        head = pr["head"]["sha"]
        if gh_json(repo, f"git/commits/{head}")["tree"]["sha"] != tree:
            continue
        runs = gh_json(repo, f"actions/workflows/ci.yml/runs?head_sha={head}&event=pull_request&per_page=100")
        # A later failed/restarted attempt must never be hidden by an old green run.
        candidates = sorted(runs["workflow_runs"], key=lambda r: r["id"], reverse=True)
        if not candidates or candidates[0]["conclusion"] != "success":
            continue
        run = candidates[0]
        jobs = gh_json(repo, f"actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs?per_page=100")
        required = [j for j in jobs["jobs"] if j["name"] == "Required CI"]
        if len(required) != 1 or required[0]["conclusion"] != "success":
            continue
        return {"schema": "wom-kit/delivery-source-proof/v1", "ok": True,
                "merge_commit": commit, "candidate_commit": head, "tree": tree,
                "pull_request": pr["number"], "ci_run": run["id"],
                "ci_attempt": run["run_attempt"], "ci_url": run["html_url"],
                "reused": "identical_tree_including_workflows_and_dependency_locks"}
    raise ValueError("no_successful_exact_tree_pr_evidence")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    proof = verify(args.repo, args.commit)
    args.output.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof))
