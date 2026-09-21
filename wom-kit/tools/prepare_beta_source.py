"""Prepare one deterministic, uniquely numbered beta source checkout.

Run only in the disposable clean checkout used by the beta workflow. The
generated source commit is tagged; the wheel and supply lock share its version.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess


def prepare(root: Path, number: int) -> dict:
    if not 1 <= number <= 10**18:
        raise ValueError("invalid_beta_number")
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root):
        raise ValueError("beta_source_must_be_clean")
    package = root / "wom-kit/src/wom_kit/__init__.py"
    version = re.search(r'(?m)^__version__ = "([^"]+)"$', package.read_text(encoding="utf-8")).group(1)
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("beta_base_must_be_stable_source")
    major, minor, patch = map(int, version.split("."))
    beta = f"{major}.{minor}.{patch + 1}b{number}"
    files = ["wom-kit/pyproject.toml", "wom-kit/src/wom_kit/__init__.py", "wom_kit/__init__.py"]
    for name in files:
        path = root / name
        path.write_text(path.read_text(encoding="utf-8").replace(f'"{version}"', f'"{beta}"'),
                        encoding="utf-8", newline="\n")
    policy_path = root / "wom-kit/project-runtime-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    old_lock_name = policy["supply_lock"]
    old_hash = policy["supply_lock_sha256"]
    lock = json.loads((root / old_lock_name).read_text(encoding="utf-8"))
    lock["target_tag"] = "v" + beta
    lock_bytes = (json.dumps(lock, ensure_ascii=True, indent=2) + "\n").encode()
    lock_name = f"wom-kit/project-runtime-supply-lock-v{beta}.json"
    (root / lock_name).write_bytes(lock_bytes)
    policy["supply_lock"] = lock_name
    policy["supply_lock_sha256"] = "sha256:" + hashlib.sha256(lock_bytes).hexdigest()
    policy_path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8", newline="\n")
    runtime = root / "wom-kit/src/wom_kit/project_runtime.py"
    runtime_text = runtime.read_text(encoding="utf-8")
    if old_lock_name not in runtime_text or old_hash not in runtime_text:
        raise ValueError("runtime_supply_contract_not_found")
    runtime.write_text(runtime_text.replace(old_lock_name, lock_name).replace(old_hash, policy["supply_lock_sha256"]),
                       encoding="utf-8", newline="\n")
    note = root / f"wom-kit/docs/releases/v{beta}.md"
    note.write_text(f"# WOM-kit v{beta} — opt-in beta\n\n"
                    f"Base source: `{source}`. This prerelease does not replace stable latest.\n\n"
                    "Install only the exact published wheel and select its exact beta target explicitly. "
                    "See the attached evidence for checks actually completed. "
                    "A beta does not claim stable release validation or customer acceptance.\n",
                    encoding="utf-8", newline="\n")
    spec = importlib.util.spec_from_file_location("beta_resource_sync", root / "wom-kit/tools/sync_package_resources.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    manifest, payloads = module.expected_manifest()
    for relative, data in payloads.items():
        path = module.DESTINATION_ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    previous_note = module.DESTINATION_ROOT / "release-notes" / f"v{version}.md"
    previous_note.unlink()
    module.write_manifest_atomic(manifest)
    return {"schema": "wom-kit/beta-source/v1", "base_commit": source,
            "version": beta, "tag": "v" + beta, "base_version": version}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--number", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(Path(__file__).resolve().parents[2], args.number)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
