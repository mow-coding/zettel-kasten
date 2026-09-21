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


def validate(directory: Path, *, tree: str, candidate: str, tag: str, run: dict,
             verified_plan: dict | None = None, baseline_run: dict | None = None) -> dict:
    if not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag):
        raise ValueError("stable_tag_required")
    source = json.loads((directory / "source-proof.json").read_text(encoding="utf-8-sig"))
    report = json.loads((directory / "wheel-check.json").read_text(encoding="utf-8-sig"))
    jobs = {job["name"]: job["conclusion"] for job in run["jobs"]}
    producer = run
    producer_tree, producer_candidate = tree, candidate
    if verified_plan is not None:
        focused = [f'Focused regression {os_name} py{version}' for os_name, version in
                   [('ubuntu-latest', '3.10'), ('ubuntu-latest', '3.12'), ('windows-latest', '3.12')]]
        if (verified_plan.get('schema') != 'wom-kit/incremental-ci-plan/v1'
                or verified_plan.get('head') != candidate or baseline_run is None
                or any(jobs.get(name) != 'success' for name in focused)
                or baseline_run.get('databaseId') != verified_plan.get('baseline_run')
                or baseline_run.get('attempt') != verified_plan.get('baseline_attempt')):
            raise ValueError('incremental_validation_mismatch')
        producer = baseline_run
        producer_tree = verified_plan['baseline_tree']
        producer_candidate = verified_plan['baseline_head']
    producer_jobs = {job['name']: job['conclusion'] for job in producer['jobs']}
    if (source.get("schema") != "wom-kit/installed-wheel-artifact/v1"
            or source.get("source_tree") != producer_tree or source.get("candidate_commit") != producer_candidate
            or producer.get('headSha') != producer_candidate or producer.get('event') != 'pull_request'
            or run.get("headSha") != candidate or run.get("event") != "pull_request"
            or run.get("conclusion") != "success"
            or str(producer.get("databaseId")) != source.get("run_id")
            or str(producer.get("attempt")) != source.get("attempt")
            or jobs.get("Required CI") != "success"
            or producer_jobs.get("Installed public entrypoints and workflow gate (Windows py3.12)") != "success"
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
            "artifact_ci_run": producer['databaseId'],
            "basis": ("same_full_tree_and_same_verified_wheel_bytes" if verified_plan is None
                      else "unchanged_product_and_execution_inputs_with_focused_revalidation"),
            "incremental_plan": verified_plan,
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
    parser.add_argument("--incremental-plan", type=Path)
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
    plan, baseline = None, None
    if args.incremental_plan:
        from incremental_ci import baseline_plan
        saved = json.loads(args.incremental_plan.read_text(encoding='utf-8'))
        plan = baseline_plan(args.repo, saved['baseline_run'], pr['headRefOid'], args.pr)
        if plan != saved:
            raise ValueError('fresh_incremental_evidence_changed')
        baseline = json.loads(output('gh', 'run', 'view', str(plan['baseline_run']), '--repo', args.repo,
                                     '--json', 'headSha,event,conclusion,databaseId,attempt,jobs'))
    report = validate(args.directory, tree=output("git", "rev-parse", merge + "^{tree}"),
                      candidate=pr["headRefOid"], tag=args.tag, run=run,
                      verified_plan=plan, baseline_run=baseline)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
