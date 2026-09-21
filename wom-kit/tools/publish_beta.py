"""Publish one checked beta without replacing tags, assets or stable latest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request


def run(*args: str) -> str:
    return subprocess.check_output(list(args), text=True, encoding="utf-8").strip()


def artifact_row(path: Path) -> dict:
    return {"name": path.name, "size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def validate_inputs(source: dict, proof: dict, check: dict, wheel: Path) -> dict:
    version = source.get("version", "")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+b[1-9][0-9]*", version):
        raise ValueError("not_a_beta")
    row = artifact_row(wheel)
    if (not proof.get("ok") or proof.get("merge_commit") != source.get("base_commit")
            or source.get("tag") != "v" + version or not check.get("ok")
            or check.get("package_version") != version
            or row["name"] != f"wom_kit-{version}-py3-none-any.whl"
            or check.get("wheel_sha256") != row["sha256"]
            or check.get("wheel_filename") != row["name"]):
        raise ValueError("beta_evidence_mismatch")
    journey = check.get("installed_v0419_runtime_journey", {})
    if journey.get("ok") is not True:
        raise ValueError("windows_installed_update_evidence_missing")
    return row


def download(url: str, destination: Path) -> dict:
    # Intentionally no Authorization header or gh-authenticated download.
    with urllib.request.urlopen(url, timeout=120) as response, destination.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
    return artifact_row(destination)


def publish(repo: str, directory: Path) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("invalid_repository")
    source = json.loads((directory / "beta-source.json").read_text())
    proof = json.loads((directory / "source-proof.json").read_text())
    check = json.loads((directory / "wheel-check.json").read_text(encoding="utf-8-sig"))
    wheel = directory / f"wom_kit-{source['version']}-py3-none-any.whl"
    row = validate_inputs(source, proof, check, wheel)
    tag = source["tag"]
    commit = run("git", "rev-parse", "HEAD")
    if run("git", "status", "--porcelain"):
        raise ValueError("generated_source_not_clean")
    if run("git", "rev-parse", "HEAD^") != source["base_commit"]:
        raise ValueError("generated_source_parent_mismatch")
    evidence = {"schema": "wom-kit/beta-delivery/v1", "channel": "beta",
                "base_commit": source["base_commit"], "generated_commit": commit,
                "tree": run("git", "rev-parse", "HEAD^{tree}"), "tag": tag,
                "source_proof": proof, "wheel": row,
                "validation": {"installed_wheel": "passed", "customer": "not_verified",
                               "stable_release": "not_claimed"}}
    evidence_path = directory / "beta-evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    notes = directory / "release-notes.md"
    notes.write_text(f"# WOM {tag} 베타\n\n"
                     "베타 사용을 명시적으로 선택한 경우에만 설치하세요. 안정판 latest는 유지됩니다.\n\n"
                     f"기준 소스: `{source['base_commit']}`\n\n"
                     f"검증된 수정: [PR #{proof['pull_request']}](https://github.com/{repo}/pull/{proof['pull_request']})\n\n"
                     f"파일: `{row['name']}` — {row['size_bytes']} bytes\n\n"
                     f"SHA-256: `{row['sha256']}`\n\n"
                     "기존 안정판 실행기가 베타 번호를 아직 지원하지 않는 경우, 이 wheel을 별도의 새 Python 3.12 환경에 설치한 실행기로 프로젝트 업데이트를 시작하세요. "
                     f"업데이트 대상은 정확히 `{tag}`로 지정합니다. 베타 wheel 설치만으로 기존 프로젝트가 갱신된 것은 아닙니다.\n\n"
                     "첨부 증거에서 검사 범위를 확인하세요. 고객의 실제 사용 성공과 안정판 출시 검증은 별도입니다.\n",
                     encoding="utf-8")
    remote = run("git", "ls-remote", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}")
    if remote:
        if f"{commit}\trefs/tags/{tag}^{{}}" not in remote.splitlines():
            raise ValueError("existing_tag_has_different_source")
    else:
        run("git", "tag", "-a", tag, "-m", f"WOM opt-in beta {tag}", commit)
        run("git", "push", "origin", f"refs/tags/{tag}")
    # Listing is read-only and distinguishes absence from authentication/network errors.
    releases = json.loads(run("gh", "api", "--paginate", "--slurp", f"repos/{repo}/releases?per_page=100"))
    matches = [r for page in releases for r in page if r["tag_name"] == tag]
    if not matches:
        run("gh", "release", "create", tag, "--repo", repo, "--verify-tag", "--draft",
            "--prerelease", "--latest=false", "--title", f"WOM {tag} beta", "--notes-file", str(notes))
    release = json.loads(run("gh", "api", f"repos/{repo}/releases/tags/{tag}"))
    if not release["prerelease"]:
        raise ValueError("existing_release_is_not_beta")
    assets = {a["name"]: a for a in release["assets"]}
    expected_files = [wheel, evidence_path, directory / "wheel-check.json"]
    # Never use --clobber. Retries reuse exactly matching assets or stop.
    for path in expected_files:
        expected = artifact_row(path)
        if path.name in assets:
            with tempfile.TemporaryDirectory() as tmp:
                run("gh", "release", "download", tag, "--repo", repo,
                    "--pattern", path.name, "--dir", tmp)
                downloaded = Path(tmp) / path.name
                if path.name == "wheel-check.json":
                    # Durations may differ on retry. Preserve the earlier valid
                    # report for exactly these wheel bytes; never replace it.
                    validate_inputs(source, proof, json.loads(downloaded.read_text(encoding="utf-8-sig")), wheel)
                elif artifact_row(downloaded) != expected:
                    raise ValueError("existing_release_asset_differs")
        else:
            if not release["draft"]:
                raise ValueError("published_release_is_incomplete")
            run("gh", "release", "upload", tag, str(path), "--repo", repo)
    # Download draft bytes after upload too: reported metadata alone is insufficient.
    with tempfile.TemporaryDirectory() as tmp:
        run("gh", "release", "download", tag, "--repo", repo, "--pattern", wheel.name, "--dir", tmp)
        if artifact_row(Path(tmp) / wheel.name) != row:
            raise ValueError("draft_wheel_mismatch")
    if release["draft"]:
        latest_before = json.loads(run("gh", "api", f"repos/{repo}/releases/latest"))["tag_name"]
        run("gh", "release", "edit", tag, "--repo", repo, "--draft=false", "--prerelease", "--latest=false")
        latest_after = json.loads(run("gh", "api", f"repos/{repo}/releases/latest"))["tag_name"]
        if latest_after != latest_before:
            raise ValueError("stable_latest_changed_during_beta_publication")
    url = f"https://github.com/{repo}/releases/download/{tag}/{wheel.name}"
    with tempfile.TemporaryDirectory() as tmp:
        observed = download(url, Path(tmp) / wheel.name)
        if observed != row:
            raise ValueError("anonymous_wheel_mismatch")
        venv = Path(tmp) / "fresh"
        run(sys.executable, "-m", "venv", str(venv))
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(str(python), "-I", "-m", "pip", "--isolated", "install", "--disable-pip-version-check",
            url + "#sha256=" + row["sha256"])
        run(str(python), "-I", "-m", "pip", "check")
        version = run(str(python), "-I", "-c", "import wom_kit;print(wom_kit.__version__)")
        if version != source["version"]:
            raise ValueError("public_fresh_install_version_mismatch")
    result = {**evidence, "public_url": url, "anonymous_download": "passed", "public_fresh_install": "passed"}
    (directory / "public-verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write(f"베타 [{tag}]({url}) 공개 및 익명 다운로드 검증 완료. 고객 확인: 미확인.\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.repo, args.directory)))
