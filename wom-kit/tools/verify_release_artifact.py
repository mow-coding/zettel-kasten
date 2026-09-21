"""Verify a retained CI wheel against the actual merged and tagged source.

Read-only: no build, tag, upload or release mutation. Reuse verified bytes rather
than rebuilding an indistinguishable source tree and discarding the first wheel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile


def validate(directory: Path, *, tree: str, candidate: str, tag: str, run: dict) -> dict:
    if not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag):
        raise ValueError("stable_tag_required")
    source = json.loads((directory / "source-proof.json").read_text(encoding="utf-8-sig"))
    report = json.loads((directory / "wheel-check.json").read_text(encoding="utf-8-sig"))
    jobs = {job["name"]: job["conclusion"] for job in run["jobs"]}
    if (source.get("schema") != "wom-kit/installed-wheel-artifact/v1"
            or source.get("source_tree") != tree or source.get("candidate_commit") != candidate
            or run.get("headSha") != candidate or run.get("event") != "pull_request"
            or run.get("conclusion") != "success"
            or str(run.get("databaseId")) != source.get("run_id")
            or str(run.get("attempt")) != source.get("attempt")
            or jobs.get("Required CI") != "success"
            or jobs.get("Installed public entrypoints and workflow gate (Windows py3.12)") != "success"
            or report.get("ok") is not True or report.get("package_version") != tag[1:]
            or report.get("installed_v0419_runtime_journey", {}).get("ok") is not True):
        raise ValueError("release_source_or_validation_mismatch")
    name = f"wom_kit-{tag[1:]}-py3-none-any.whl"
    wheel = directory / name
    observed = {"name": name, "size_bytes": wheel.stat().st_size,
                "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()}
    if (source.get("wheel") != observed or report.get("wheel_filename") != name
            or report.get("wheel_sha256") != observed["sha256"]):
        raise ValueError("retained_wheel_bytes_mismatch")
    with zipfile.ZipFile(wheel) as archive:
        metadata = archive.read(f"wom_kit-{tag[1:]}.dist-info/METADATA").decode("utf-8")
        if f"Version: {tag[1:]}" not in metadata.splitlines():
            raise ValueError("retained_wheel_version_mismatch")
    return {"schema": "wom-kit/release-artifact-reuse/v1", "ok": True, "tag": tag,
            "candidate_commit": candidate, "merge_tree": tree,
            "ci_run": run["databaseId"], "ci_attempt": run["attempt"], "wheel": observed,
            "basis": "same_full_tree_and_same_verified_wheel_bytes",
            "public_download": "not_checked", "customer": "not_checked"}


def output(*args: str) -> str:
    return subprocess.check_output(list(args), text=True, encoding="utf-8").strip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--run", type=int, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pr = json.loads(output("gh", "pr", "view", str(args.pr), "--repo", args.repo,
                           "--json", "state,headRefOid,mergeCommit"))
    if pr["state"] != "MERGED":
        raise ValueError("merged_pr_required")
    merge = pr["mergeCommit"]["oid"]
    if output("git", "cat-file", "-t", "refs/tags/" + args.tag) != "tag":
        raise ValueError("annotated_tag_required")
    if output("git", "rev-parse", "refs/tags/" + args.tag + "^{commit}") != merge:
        raise ValueError("tag_merge_mismatch")
    run = json.loads(output("gh", "run", "view", str(args.run), "--repo", args.repo,
                            "--json", "headSha,event,conclusion,databaseId,attempt,jobs"))
    report = validate(args.directory, tree=output("git", "rev-parse", merge + "^{tree}"),
                      candidate=pr["headRefOid"], tag=args.tag, run=run)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
