"""Synthetic fresh-process benchmark of installed, official Windows launchers.

The preparation helpers create task-owned private runtimes and synthetic inputs.
Only uninstrumented archive.cmd invocations determine performance acceptance.
The optional profiling run uses the same installed entrypoint, but is explicitly
diagnostic and cannot be substituted for those official-launcher observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
import zipfile

SCHEMA = "wom-kit/installed-feedback-benchmark/v1"
OWNER = "wom-kit/synthetic-performance-workspace/v1"
BASELINE_TAG = "v0.4.47"
REPOSITORY = "mow-coding/zettel-kasten"
CASES = ("zettel-edge", "zettel-objet-link", "exact-approval-claims")
COUNTS = {"objects": 23000, "zettels": 8616, "manifest_bytes": 37 * 1024 * 1024, "claims": 1000}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write_new(path, document):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=True, indent=2, sort_keys=True)
        stream.write("\n")


def owned_root(value):
    root = Path(value).resolve()
    marker = root / "synthetic-benchmark-owner.json"
    if not root.exists():
        root.mkdir(parents=True)
    if not marker.exists():
        if any(root.iterdir()):
            raise RuntimeError("benchmark_workspace_not_empty_or_owned")
        write_new(marker, {"schema": OWNER, "synthetic_only": True})
    if json.loads(marker.read_text(encoding="utf-8")) != {"schema": OWNER, "synthetic_only": True}:
        raise RuntimeError("benchmark_workspace_owner_invalid")
    return root


def inside(root, path):
    candidate = Path(path).resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise RuntimeError("benchmark_target_outside_owned_workspace")
    return candidate


def run(command, *, cwd, timeout=120, output=None):
    started = time.perf_counter()
    environment = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(key, None)
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run([str(part) for part in command], cwd=cwd, env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    elapsed = time.perf_counter() - started
    if output:
        candidate = Path(output)
        serial = 0
        while Path(str(candidate) + ".stdout").exists() or Path(str(candidate) + ".stderr").exists():
            serial += 1
            candidate = Path(str(output) + f".{serial}")
        Path(str(candidate) + ".stdout").write_bytes(completed.stdout)
        Path(str(candidate) + ".stderr").write_bytes(completed.stderr)
    return completed, elapsed


def download_baseline(root):
    folder = root / "baseline-asset"
    folder.mkdir(exist_ok=True)
    request = urllib.request.Request(f"https://api.github.com/repos/{REPOSITORY}/releases/tags/{BASELINE_TAG}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "WOM-synthetic-benchmark"})
    with urllib.request.urlopen(request, timeout=60) as response:
        release = json.load(response)
    assets = [row for row in release["assets"] if row["name"] == "wom_kit-0.4.47-py3-none-any.whl"]
    if len(assets) != 1 or release["draft"] or release["prerelease"]:
        raise RuntimeError("benchmark_baseline_release_invalid")
    asset = assets[0]
    if not str(asset.get("digest", "")).startswith("sha256:"):
        raise RuntimeError("benchmark_baseline_digest_missing")
    target = folder / asset["name"]
    if not target.exists():
        request = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "WOM-synthetic-benchmark"})
        with urllib.request.urlopen(request, timeout=120) as response, target.open("xb") as stream:
            shutil.copyfileobj(response, stream)
    if target.stat().st_size != asset["size"] or "sha256:" + digest(target) != asset["digest"]:
        raise RuntimeError("benchmark_baseline_download_mismatch")
    proof = {"release_url": release["html_url"], "tag": BASELINE_TAG, "asset_id": asset["id"],
             "size_bytes": target.stat().st_size, "sha256": digest(target), "anonymous_download": True}
    if not (folder / "proof.json").exists():
        write_new(folder / "proof.json", proof)
    return target, proof


RUNTIME_SETUP = r'''
import json, sys, hashlib, zipfile
from pathlib import Path
import wom_kit
from wom_kit import project_runtime
runtime, launcher, wheel = map(Path, sys.argv[1:])
if runtime.resolve() != Path(sys.prefix).resolve(): raise RuntimeError('benchmark_runtime_binding_mismatch')
package = Path(wom_kit.__file__).parent
verified = 0
with zipfile.ZipFile(wheel) as zipped:
    for entry in zipped.infolist():
        if entry.filename.startswith('wom_kit/') and not entry.is_dir():
            relative = Path(entry.filename).relative_to('wom_kit')
            if (package / relative).read_bytes() != zipped.read(entry):
                raise RuntimeError('benchmark_installed_wheel_bytes_mismatch')
            verified += 1
launcher.parent.mkdir(parents=True, exist_ok=True)
expected_launcher = project_runtime.launcher_bytes(wom_kit.__version__)
if launcher.exists():
    if launcher.read_bytes() != expected_launcher: raise RuntimeError('benchmark_launcher_bytes_mismatch')
else:
    project_runtime._remove_runtime_bytecode(runtime)
    project_runtime._build_runtime_startup_cache(runtime)
    with launcher.open('xb') as stream: stream.write(expected_launcher)
print(json.dumps({'version': wom_kit.__version__, 'wheel_entries_verified': verified,
 'official_launcher_sha256': hashlib.sha256(launcher.read_bytes()).hexdigest(),
 'runtime_preparation': 'installed_project_runtime_helpers', 'python': sys.version.split()[0]}))
'''

CLAIM_SETUP = r'''
import json, sys
from datetime import datetime, timezone
from pathlib import Path
from wom_kit import exact_human_approval as approval, exact_human_approval_workflow as workflow
from wom_kit.exact_human_approval_windows import ExactHumanApprovalContext, ExactHumanApprovalOperation, _ExactHumanApprovalDecision
root, count = Path(sys.argv[1]), int(sys.argv[2])
from wom_kit import archive_services as services
archive_id = services.read_archive_id(root)
context = ExactHumanApprovalContext(operation=ExactHumanApprovalOperation.mint_zet,
 archive_identity_sha256=approval.exact_human_approval_archive_identity_sha256(archive_id),
 plan_sha256='sha256:'+'b'*64, target_binding_sha256='sha256:'+'c'*64,
 reviewer_claim='person:synthetic-benchmark', review_binding_codes=('body_digest','frontmatter_digest'), warning_codes=())
decision = _ExactHumanApprovalDecision(approved=True, synthetic_acknowledged=False,
 reason_code='exact_human_approval_approved', plan_sha256=context.plan_sha256, target_binding_sha256=context.target_binding_sha256)
def seed(key):
    for number in range(count):
        path = root / approval.CLAIMS_RELATIVE_ROOT / ('approval_' + format(number+1, '032x') + '.json')
        if path.exists():
            previous = approval._read_claim(path, archive_id=archive_id, key=key)
            if previous['context_sha256'] != approval.exact_human_approval_context_sha256(context):
                raise RuntimeError('benchmark_synthetic_claim_binding_mismatch')
            continue
        claim = approval._claim_exact_human_approval_core(root, context, decision, key,
          clock=lambda: datetime(2026,9,28,tzinfo=timezone.utc), random_hex=lambda size,n=number: format(n+1,'032x'))
        claim.close()
workflow._production_key_provider().use_key(root, seed, create_if_missing=True)
print(json.dumps({'synthetic_authenticated_claims': count, 'real_operation_executed': False}))
'''


def prepare_seed(root, python):
    """Create an isolated synthetic identity; never read another archive's key."""
    import benchmark_v0412_link_index as fixture
    seed = inside(root, root / "fixture-seed/archive")
    authority = root / "fixture-authority.json"
    if not authority.exists():
        write_new(authority, {"archive_id": "archive:synthetic:installed-perf:" + uuid.uuid4().hex,
                              "counts": COUNTS, "synthetic_only": True})
    specification = json.loads(authority.read_text(encoding="utf-8"))
    if specification["counts"] != COUNTS or not specification["archive_id"].startswith("archive:synthetic:installed-perf:"):
        raise RuntimeError("benchmark_fixture_authority_mismatch")
    legacy_id = fixture.ARCHIVE_ID
    fixture.ARCHIVE_ID = specification["archive_id"]
    try:
        if not seed.exists():
            seed.parent.mkdir(exist_ok=True)
            fixture.create_fixture(seed, fixture.BenchmarkProfile("installed-23000", COUNTS["zettels"], COUNTS["objects"], COUNTS["manifest_bytes"], 1, 10))
        # Resume an earlier setup that failed before creating any claims. This
        # changes only known synthetic identities in this owned fixture.
        files = [seed / "archive.yml", *sorted((seed / "zettels").glob("*.md"))]
        if len(files) != COUNTS["zettels"] + 1 or (seed / "objects/manifests/files.jsonl").stat().st_size != COUNTS["manifest_bytes"]:
            raise RuntimeError("benchmark_fixture_shape_mismatch")
        for path in files:
            original = path.read_bytes()
            replaced = original.replace(legacy_id.encode(), specification["archive_id"].encode())
            if original != replaced:
                if (seed / "profiles/local/exact-human-approvals/claims").exists():
                    raise RuntimeError("benchmark_claims_precede_fixture_identity")
                path.write_bytes(replaced)
        ignore = seed / ".gitignore"
        if "profiles/local/" not in ignore.read_text(encoding="utf-8").splitlines():
            with ignore.open("a", encoding="utf-8") as stream:
                stream.write("\nprofiles/local/\n")
        claim_proof = root / "claim-preparation.json"
        if not claim_proof.exists():
            completed, _ = run([python, "-I", "-B", "-X", "utf8", "-c", CLAIM_SETUP, seed, COUNTS["claims"]],
                                cwd=root, timeout=300, output=root / "claim-setup")
            if completed.returncode:
                raise RuntimeError("benchmark_synthetic_claim_setup_failed")
            write_new(claim_proof, json.loads(completed.stdout))
        return seed
    finally:
        fixture.ARCHIVE_ID = legacy_id


def wheel_version(wheel):
    with zipfile.ZipFile(wheel) as zipped:
        metadata = [name for name in zipped.namelist() if name.endswith('.dist-info/METADATA')]
        if len(metadata) != 1:
            raise RuntimeError("benchmark_wheel_metadata_invalid")
        version = next(line[9:] for line in zipped.read(metadata[0]).decode().splitlines() if line.startswith("Version: "))
    return version


def prepare(args):
    if os.name != "nt":
        raise RuntimeError("benchmark_official_windows_launcher_required")
    root = owned_root(args.work_dir)
    if args.label == "baseline":
        wheel, origin = download_baseline(root)
    else:
        wheel = Path(args.wheel).resolve()
        if not args.sha256 or digest(wheel) != args.sha256:
            raise RuntimeError("benchmark_candidate_digest_mismatch")
        origin = {"sha256": digest(wheel), "size_bytes": wheel.stat().st_size,
                  "public_release": False, "local_candidate": True}
    project = inside(root, root / args.label)
    if project.exists() and not args.resume:
        raise RuntimeError("benchmark_label_already_exists_use_saved_preparation")
    if (project / "preparation.json").exists():
        proof = json.loads((project / "preparation.json").read_text(encoding="utf-8"))
        if proof["wheel"]["sha256"] != origin["sha256"]:
            raise RuntimeError("benchmark_prepared_wheel_mismatch")
        print(json.dumps({"state": "already_prepared", "label": args.label, "wheel": origin}), flush=True)
        return
    project.mkdir(exist_ok=True)
    version = wheel_version(wheel)
    runtime = inside(root, project / ".zettel-kasten/runtimes" / ("v" + version))
    runtime.parent.mkdir(parents=True, exist_ok=True)
    fresh_runtime = not runtime.exists()
    if fresh_runtime:
        completed, _ = run([sys.executable, "-m", "venv", runtime], cwd=root)
        if completed.returncode:
            raise RuntimeError("benchmark_venv_creation_failed")
    python = runtime / "Scripts/python.exe"
    if fresh_runtime:
        completed, _ = run([python, "-m", "pip", "install", "--no-compile", "--disable-pip-version-check", wheel],
                            cwd=root, timeout=300, output=project / "install")
        if completed.returncode:
            raise RuntimeError("benchmark_wheel_install_failed")
    launcher = project / ".zettel-kasten/bin/archive.cmd"
    completed, _ = run([python, "-I", "-B", "-X", "utf8", "-c", RUNTIME_SETUP, runtime, launcher, wheel],
                        cwd=root, timeout=300, output=project / "runtime-setup")
    if completed.returncode:
        raise RuntimeError("benchmark_runtime_setup_failed")
    preparation = json.loads(completed.stdout)
    reuse_claims_fixture = getattr(args, "reuse_claims_fixture", False)
    if reuse_claims_fixture:
        if args.label != "candidate-claims-native":
            raise RuntimeError("benchmark_fixture_reuse_scope_invalid")
        reused = json.loads((root / "candidate-claims/preparation.json").read_text(encoding="utf-8"))
        archive = inside(root, root / reused["archive"])
        elapsed = None
    else:
        seed = prepare_seed(root, python)
        archive = project / "archive"
        if not archive.exists():
            shutil.copytree(seed, archive)
        completed, elapsed = run([launcher, "index", archive, "--format", "json"], cwd=project,
                                 timeout=1800, output=project / "index")
        result = json.loads(completed.stdout) if completed.stdout else {}
        if completed.returncode or result.get("ok") is not True:
            raise RuntimeError("benchmark_fixture_index_failed")
    completed, _ = run([python, "-m", "pip", "list", "--format=json", "--disable-pip-version-check"], cwd=root)
    proof = {"schema": SCHEMA, "label": args.label, "counts": COUNTS, "wheel": origin,
             "runtime": preparation, "index_setup_seconds": elapsed, "dependencies": json.loads(completed.stdout),
             "read_only_fixture_reused_from": "candidate-claims" if reuse_claims_fixture else None,
             "supported_cases": ["exact-approval-claims"] if reuse_claims_fixture else list(CASES),
             "launcher": str(launcher.relative_to(root)), "archive": str(archive.relative_to(root)),
             "python": str(python.relative_to(root)), "fixture_manifest_sha256": digest(archive / "objects/manifests/files.jsonl")}
    write_new(project / "preparation.json", proof)
    print(json.dumps({key: proof[key] for key in ("schema", "label", "counts", "wheel", "runtime", "index_setup_seconds")}), flush=True)


def case_arguments(name, archive):
    from benchmark_v0412_link_index import _zettel_id, _object_id
    if name == "zettel-edge":
        return [name, str(archive), "--from-zettel", _zettel_id(0), "--target", _zettel_id(1), "--edge-type", "references", "--dry-run", "--format", "json"]
    if name == "zettel-objet-link":
        return [name, str(archive), "--zettel-id", _zettel_id(0), "--object-id", _object_id(0), "--role", "evidence", "--dry-run", "--format", "json"]
    return [name, str(archive), "--status", "all", "--format", "json"]


def observe(completed, elapsed, *, label, case, sample):
    try:
        result = json.loads(completed.stdout)
    except (ValueError, UnicodeError):
        result = {}
    if not isinstance(result, dict):
        result = {}
    summary = {"label": label, "case": case, "sample": sample, "seconds": round(elapsed, 6),
               "exit_code": completed.returncode, "ok": result.get("ok") is True,
               "state": result.get("state"), "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
               "official_launcher": True, "instrumented": False, "new_process": True}
    if case == "exact-approval-claims":
        claims = result.get("claims")
        summary["claims_returned"] = len(claims) if isinstance(claims, list) else None
        summary["claims_count_correct"] = summary["claims_returned"] == COUNTS["claims"]
        summary["expected_result"] = (summary["claims_count_correct"] and result.get("complete") is True
            and result.get("invalid_claim_count") == 0 and result.get("claim_count") == COUNTS["claims"]
            and result.get("blocker_codes") == [])
    else:
        summary["expected_result"] = (result.get("dry_run") is True and result.get("blockers") == []
            and isinstance(result.get("would_change"), list) and bool(result["would_change"])
            and (result.get("write_status") == "would_write" if case == "zettel-edge" else result.get("state") == "ready"))
    return summary


def p95(values):
    if not values:
        raise ValueError("benchmark_missing_samples")
    ordered = sorted(values)
    return ordered[math.ceil(.95 * len(ordered)) - 1]


def fixture_fingerprint(archive, *, expected_counts=None):
    """Bind all measured input documents, excluding version-derived indexes."""
    expected = expected_counts or COUNTS
    archive = Path(archive)
    zettels = sorted((archive / "zettels").glob("*.md"))
    claims = sorted((archive / "profiles/local/exact-human-approvals/claims").glob("*.json"))
    manifest = archive / "objects/manifests/files.jsonl"
    with manifest.open("rb") as stream:
        objects = sum(1 for line in stream if line.strip())
    if (len(zettels) != expected["zettels"] or len(claims) != expected["claims"]
            or objects != expected["objects"] or manifest.stat().st_size != expected["manifest_bytes"]):
        raise RuntimeError("benchmark_fixture_counts_mismatch")
    files = [archive / "archive.yml", archive / ".gitignore", manifest, *zettels, *claims]
    result = hashlib.sha256()
    for path in sorted(files):
        result.update(path.relative_to(archive).as_posix().encode() + b"\0" + digest(path).encode() + b"\n")
    return {"sha256": result.hexdigest(), "input_files": len(files), "counts": expected,
            "version_derived_indexes_excluded": True}


def summarize(rows, *, expected_repeats=10, cases=CASES):
    if not cases or any(case not in CASES for case in cases) or len(set(cases)) != len(cases):
        raise ValueError("benchmark_command_failed_or_samples_missing")
    if len(rows) != len(cases) * 2 * (expected_repeats + 1):
        raise ValueError("benchmark_command_failed_or_samples_missing")
    summary = {}
    for case in cases:
        entries = {}
        for label in ("baseline", "candidate"):
            selected = [row for row in rows if row["case"] == case and row["label"] == label]
            if (len(selected) != expected_repeats + 1
                    or sorted(row["sample"] for row in selected) != list(range(expected_repeats + 1))
                    or any(row["exit_code"] or not row["ok"] or row.get("expected_result") is not True
                           or (case == "exact-approval-claims" and row.get("claims_count_correct") is not True)
                           or row.get("official_launcher") is not True or row.get("instrumented") is not False
                           or row.get("new_process") is not True or not math.isfinite(row["seconds"])
                           or row["seconds"] <= 0 for row in selected)):
                raise ValueError("benchmark_command_failed_or_samples_missing")
            repeat = [row["seconds"] for row in selected if row["sample"] > 0]
            entries[label] = {"first_process_seconds": next(row["seconds"] for row in selected if row["sample"] == 0), "repeat_new_process_p95_seconds": p95(repeat),
                              "repeat_samples": len(repeat)}
        baseline = entries["baseline"]["repeat_new_process_p95_seconds"]
        candidate = entries["candidate"]["repeat_new_process_p95_seconds"]
        entries["candidate_reduction_fraction"] = round(1 - candidate / baseline, 6)
        entries["goals"] = {"repeat_p95_at_most_5_seconds": candidate <= 5,
                            "at_least_50_percent_reduction": candidate <= baseline * .5,
                            "observed_first_process_at_most_20_seconds": entries["candidate"]["first_process_seconds"] <= 20}
        summary[case] = entries
    return summary


def measure(args):
    root = owned_root(args.work_dir)
    labels = {"baseline": "baseline", "candidate": args.candidate_label}
    cases = (args.case,) if args.case else CASES
    prefix = args.measurement_id + "-" if args.measurement_id else ""
    proofs = {label: json.loads((root / directory / "preparation.json").read_text(encoding="utf-8"))
              for label, directory in labels.items()}
    if any(not set(cases).issubset(proof.get("supported_cases", CASES)) for proof in proofs.values()):
        raise RuntimeError("benchmark_fixture_reuse_scope_invalid")
    if proofs["baseline"]["fixture_manifest_sha256"] != proofs["candidate"]["fixture_manifest_sha256"]:
        raise RuntimeError("benchmark_fixture_input_mismatch")
    inputs = {label: fixture_fingerprint(root / proof["archive"]) for label, proof in proofs.items()}
    if inputs["baseline"] != inputs["candidate"]:
        raise RuntimeError("benchmark_fixture_input_mismatch")
    output = root / (prefix + "official-launcher-measurements.jsonl")
    if output.exists():
        raise RuntimeError("benchmark_measurements_already_exist")
    rows = []
    with output.open("x", encoding="utf-8") as stream:
        for case in cases:
            for sample in range(args.repeat + 1):
                # Alternate order to reduce systematic file-cache/order bias.
                for label in (("baseline", "candidate") if sample % 2 == 0 else ("candidate", "baseline")):
                    proof = proofs[label]
                    completed, elapsed = run([root / proof["launcher"], *case_arguments(case, root / proof["archive"])],
                                             cwd=root / labels[label], timeout=180)
                    row = observe(completed, elapsed, label=label, case=case, sample=sample)
                    rows.append(row)
                    stream.write(json.dumps(row) + "\n")
                    stream.flush()
                    print(json.dumps(row), flush=True)
                    if row["exit_code"] or not row["ok"] or row.get("expected_result") is not True:
                        (root / (prefix + label + "-" + case + "-failure.stdout")).write_bytes(completed.stdout)
                        (root / (prefix + label + "-" + case + "-failure.stderr")).write_bytes(completed.stderr)
                        raise RuntimeError("benchmark_actual_installed_command_failed")
    result = {"schema": SCHEMA, "counts": COUNTS, "summary": summarize(rows, expected_repeats=args.repeat, cases=cases),
              "measured_cases": list(cases), "runtime_labels": labels,
              "environment": {"python": platform.python_version(), "os": platform.system(), "architecture": platform.machine()},
              "source_checkout_imported_by_measured_process": False, "acceptance_uses_official_launcher_only": True,
              "os_cache_flushed": False, "first_process_is_not_cold_os_p95": True,
              "process_startup_and_launcher_included_in_wall_time": True,
              "diagnostic_phase_timings_are_not_subtracted_from_wall_time": True,
              "fixture": inputs["baseline"], "input_equality_checked_before_measurement": True,
              "benchmark_script_sha256": digest(Path(__file__)),
              "fixture_generator_sha256": digest(Path(__file__).with_name("benchmark_v0412_link_index.py")),
              "not_measured_by_read_only_cases": ["approval_wait", "write_execution", "remote_transfer", "remote_request_deduplication"],
              "installed_wheels": {label: value["wheel"] for label, value in proofs.items()}}
    write_new(root / (prefix + "comparison.json"), result)
    print(json.dumps(result), flush=True)


def diagnose(args):
    root = owned_root(args.work_dir)
    probe = Path(__file__).with_name("benchmark_installed_feedback_probe.py").resolve()
    for label in ((args.label,) if args.label else ("baseline", "candidate")):
        proof = json.loads((root / label / "preparation.json").read_text(encoding="utf-8"))
        for case in ((args.case,) if args.case else CASES):
            output = root / (label + "-" + case + "-diagnostic.json")
            if output.exists():
                raise RuntimeError("benchmark_diagnostic_already_exists")
            completed, elapsed = run([root / proof["python"], "-I", "-B", "-X", "utf8", probe, output,
                                      *case_arguments(case, root / proof["archive"])],
                                     cwd=root / label, timeout=300, output=root / (label + "-" + case + "-diagnostic-command"))
            if completed.returncode or json.loads(completed.stdout).get("ok") is not True:
                raise RuntimeError("benchmark_diagnostic_command_failed")
            report = json.loads(output.read_text(encoding="utf-8"))
            print(json.dumps({"label": label, "case": case, "diagnostic_wall_seconds": elapsed,
                              "diagnostic_only": True, "report": report}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--work-dir", required=True)
    prep.add_argument("--label", choices=("baseline", "candidate", "candidate-claims", "candidate-claims-native", "candidate-startup-cache", "candidate-stat-scan"), required=True)
    prep.add_argument("--wheel")
    prep.add_argument("--sha256")
    prep.add_argument("--resume", action="store_true", help="Reuse only the owned runtime whose bytes match this exact wheel.")
    prep.add_argument("--reuse-claims-fixture", action="store_true", help="Reuse the previous owned read-only claims fixture; no index rebuild or other command is allowed.")
    measurement = sub.add_parser("measure")
    measurement.add_argument("--work-dir", required=True)
    measurement.add_argument("--repeat", type=int, default=10)
    measurement.add_argument("--case", choices=CASES)
    measurement.add_argument("--candidate-label", choices=("candidate", "candidate-claims", "candidate-claims-native", "candidate-startup-cache", "candidate-stat-scan"), default="candidate")
    measurement.add_argument("--measurement-id", choices=("claims-scope", "claims-native", "startup-cache", "stat-scan"), default="")
    diagnostic = sub.add_parser("diagnose")
    diagnostic.add_argument("--work-dir", required=True)
    diagnostic.add_argument("--label", choices=("baseline", "candidate"))
    diagnostic.add_argument("--case", choices=CASES)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args)
    elif args.mode == "measure":
        if not 2 <= args.repeat <= 100:
            raise RuntimeError("benchmark_repeat_invalid")
        measure(args)
    else:
        diagnose(args)


if __name__ == "__main__":
    main()
