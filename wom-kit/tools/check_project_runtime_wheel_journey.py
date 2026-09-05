#!/usr/bin/env python3
"""Installed-only Windows runtime journey; local synthetic project, real wheel.

Run only with the wheel checker's isolated bootstrap interpreter. This file
never inserts a source checkout in sys.path. Only release transport metadata,
local wheel transport, native button choice, and an ephemeral approval key are
controlled; policy, supply, installer, broker, writers and verifiers stay real.
"""

from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from unittest import mock


SCHEMA = "wom-kit/installed-v0419-runtime-journey/v0.1"
SAFE_REASON_CODES = frozenset({
    "origin_modules_incomplete", "source_checkout_import_denied", "synthetic_child_command_failed",
    "source_resource_path_invalid", "source_resource_drift", "windows_cpython312_required",
    "synthetic_fixture_must_be_new", "bootstrap_version_mismatch", "bootstrap_wheel_hash_mismatch",
    "fixture_invalid", "local_transport_hash_mismatch", "local_transport_size_mismatch",
    "public_update_failed", "public_native_broker_not_once", "update_cleanup_incomplete",
    "public_noop_failed", "noop_revalidation_missing", "noop_runtime_changed", "noop_receipt_added",
    "noop_pin_launcher_receipt_changed", "noop_blocks_next_command", "active_update_lock_remains",
    "active_update_transaction_remains", "runtime_candidate_remains", "runtime_origin_or_version_mismatch",
    "project_launcher_version_mismatch", "durable_broker_claim_missing", "journey_arguments_invalid",
    "doctor_startup_probe_failed", "doctor_startup_progress_missing", "doctor_startup_progress_deadline",
    "doctor_startup_output_invalid", "doctor_startup_probe_output_bound",
})


class JourneyCheckError(RuntimeError):
    """Only explicit harness assertions can supply public reason codes."""


def require(condition: object, reason: str) -> None:
    if not condition:
        raise JourneyCheckError(reason if reason in SAFE_REASON_CODES else "installed_runtime_journey_failed")


def verify_installed_origins(modules: dict[str, object], prefix: Path) -> bool:
    """Prove actual module origins, not just an import-success assertion."""
    site = (prefix / "Lib" / "site-packages").resolve(strict=True)
    require(set(modules) == {"wom_kit", "archive_cli", "project_runtime"}, "origin_modules_incomplete")
    for module in modules.values():
        origin = Path(getattr(module, "__file__", "")).resolve(strict=True)
        require(origin.is_file() and origin.is_relative_to(site), "source_checkout_import_denied")
    return True


def command(argv: list[str], *, cwd: Path, timeout: int = 120) -> str:
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        env=environment, timeout=timeout, check=False, **options,
    )
    require(completed.returncode == 0, "synthetic_child_command_failed")
    return completed.stdout.strip()


def progress_timing(status_seconds: list[float], terminal_seconds: float) -> dict[str, float | int]:
    """Include startup and the final silent interval; never clamp a bad gap."""
    require(bool(status_seconds), "doctor_startup_progress_missing")
    points = [0.0, *status_seconds, terminal_seconds]
    gaps = [after - before for before, after in zip(points, points[1:])]
    require(all(gap >= 0 for gap in gaps), "doctor_startup_output_invalid")
    maximum_gap = max(gaps)
    require(status_seconds[0] <= 2.0 and maximum_gap <= 10.0, "doctor_startup_progress_deadline")
    return {"first_status_seconds": status_seconds[0], "maximum_gap_seconds": maximum_gap,
            "terminal_seconds": terminal_seconds, "status_event_count": len(status_seconds)}


def measure_doctor_startup(argv: list[str], *, cwd: Path) -> dict[str, float | int]:
    """Measure the real public child from before launch, with bounded pipes.

    The enclosing checker already contains this entire descendant tree in its
    kill-on-close job. This observer creates no venv and stores no progress text.
    """
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    output: list[bytes] = []
    status_seconds: list[float] = []
    failures: list[bool] = []
    started = time.monotonic()
    process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=environment, **options)

    def read_pipe(stream, *, progress: bool):
        total = 0
        try:
            while True:
                chunk = stream.readline(4096) if progress else stream.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > 1024 * 1024:
                    failures.append(True)
                    process.kill()
                    break
                if progress:
                    if chunk.startswith((b"[wom] startup:", b"[doctor] ")):
                        status_seconds.append(time.monotonic() - started)
                else:
                    output.append(chunk)
        except (OSError, ValueError):
            failures.append(True)
        finally:
            stream.close()

    readers = [threading.Thread(target=read_pipe, args=(process.stdout,), kwargs={"progress": False}, daemon=True),
               threading.Thread(target=read_pipe, args=(process.stderr,), kwargs={"progress": True}, daemon=True)]
    for reader in readers:
        reader.start()
    try:
        code = process.wait(timeout=180)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
        raise JourneyCheckError("doctor_startup_probe_failed") from None
    finally:
        for reader in readers:
            reader.join(timeout=2)
    require(not failures and not any(reader.is_alive() for reader in readers), "doctor_startup_probe_output_bound")
    require(code == 0, "doctor_startup_probe_failed")
    # Completion is observable only after the child exits and both pipes are
    # drained. Timestamp that boundary, not an earlier wait()/reader race.
    terminal = time.monotonic() - started
    try:
        document = json.loads(b"".join(output).decode("utf-8"))
    except (ValueError, UnicodeError):
        raise JourneyCheckError("doctor_startup_output_invalid") from None
    require(isinstance(document, dict) and document.get("ok") is True, "doctor_startup_output_invalid")
    return progress_timing(status_seconds, terminal)


def git(root: Path, *args: str) -> str:
    return command(["git", "-C", str(root), *args], cwd=root)


def create_project(root: Path, source: Path, shim: Path, version: str) -> dict[str, Path | str]:
    """The old source is inert fixture data; the target is exact build input."""
    upstream = root / "upstream"
    package = upstream / "wom-kit" / "src" / "wom_kit"
    package.mkdir(parents=True)
    old_version = "0.0.1"
    (package / "__init__.py").write_text(f'__version__ = "{old_version}"\n', encoding="utf-8")
    (package / "archive_cli.py").write_text("def main(argv=None):\n    return 0\n", encoding="utf-8")
    (upstream / "wom-kit" / "pyproject.toml").write_text(
        f'[project]\nname = "wom-kit"\nversion = "{old_version}"\n', encoding="utf-8",
    )
    old_shim = upstream / "wom_kit" / "__init__.py"
    old_shim.parent.mkdir()
    old_shim.write_text(f'__version__ = "{old_version}"\n', encoding="utf-8")
    wrapper = upstream / "wom-kit" / "cli" / "archive.py"
    wrapper.parent.mkdir()
    shutil.copyfile(source / "cli" / "archive.py", wrapper)
    git(upstream, "init", "-b", "main")
    git(upstream, "config", "user.name", "wheel-fixture")
    git(upstream, "config", "user.email", "wheel-fixture.invalid")
    git(upstream, "config", "core.autocrlf", "false")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "synthetic predecessor")
    git(upstream, "tag", "-a", "v" + old_version, "-m", "synthetic predecessor")
    project = root / "project"
    metadata = project / ".zettel-kasten"
    metadata.mkdir(parents=True)
    mirror = metadata / "source"
    command([
        "git", "-c", "protocol.file.allow=always", "-c", "core.autocrlf=false",
        "clone", "--quiet", str(upstream), str(mirror),
    ], cwd=root)
    git(mirror, "checkout", "--detach", "--quiet", "v" + old_version)
    git(mirror, "config", "user.name", "wheel-fixture")
    git(mirror, "config", "user.email", "wheel-fixture.invalid")
    for pin in (metadata / "installed-version.txt", mirror / "installed-version.txt"):
        pin.write_text("v" + old_version + "\n", encoding="utf-8")
    archive = project / "archive"
    archive.mkdir()
    (archive / "archive.yml").write_text(
        "archive_id: archive:personal:wheel-runtime-fixture\narchive_type: personal\n",
        encoding="utf-8",
    )

    # Copy exact package source and every manifest-bound source resource from
    # the same immutable build input, not a tiny replacement WOM package.
    shutil.copytree(source / "src", upstream / "wom-kit" / "src", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"))
    manifest = json.loads((source / "src/wom_kit/_resources/resource-manifest.json").read_text(encoding="utf-8"))
    for row in manifest["files"]:
        relative = Path(row["source"])
        require(not relative.is_absolute() and ".." not in relative.parts, "source_resource_path_invalid")
        origin = source / relative
        require(hashlib.sha256(origin.read_bytes()).hexdigest() == row["sha256"], "source_resource_drift")
        destination = upstream / "wom-kit" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
    for name in ("pyproject.toml", "project-runtime-policy.json", f"project-runtime-supply-lock-v{version}.json"):
        shutil.copyfile(source / name, upstream / "wom-kit" / name)
    shutil.copyfile(shim, old_shim)
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "exact candidate source")
    git(upstream, "tag", "-a", "v" + version, "-m", "synthetic candidate tag")
    return {"project": project, "metadata": metadata, "archive": archive,
            "target_commit": git(upstream, "rev-parse", "HEAD")}


class _MemoryOnlyApprovalKey:
    def use_key(self, _root, consumer, *, create_if_missing=False):
        key = bytearray(b"w" * 32)
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


def run_journey(wheel: Path, source: Path, shim: Path, root: Path, expected_version: str) -> dict[str, object]:
    require(os.name == "nt" and sys.version_info[:2] == (3, 12), "windows_cpython312_required")
    require(not root.exists(), "synthetic_fixture_must_be_new")
    root.mkdir()
    started = time.monotonic()
    from wom_kit import archive_cli, archive_services, project_runtime
    from wom_kit import exact_human_approval_windows, exact_human_approval_workflow
    import wom_kit
    import_seconds = time.monotonic() - started
    modules = {"wom_kit": wom_kit, "archive_cli": archive_cli, "project_runtime": project_runtime}
    verify_installed_origins(modules, Path(sys.prefix))
    require(wom_kit.__version__ == expected_version, "bootstrap_version_mismatch")
    wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
    direct = json.loads(importlib.metadata.distribution("wom-kit").read_text("direct_url.json") or "{}")
    require(direct.get("archive_info", {}).get("hashes", {}).get("sha256") == wheel_hash, "bootstrap_wheel_hash_mismatch")
    fixture = create_project(root, source, shim, expected_version)
    project = fixture["project"]
    metadata = fixture["metadata"]
    require(isinstance(project, Path) and isinstance(metadata, Path), "fixture_invalid")
    bootstrap = project_runtime.BootstrapWheel(
        version=expected_version, tag="v" + expected_version,
        url="https://example.invalid/candidate/" + wheel.name,
        sha256=wheel_hash, file_name=wheel.name,
    )
    original_download = project_runtime._download_exact_artifact

    def transport(**kwargs):
        if kwargs["url"] != bootstrap.url:
            # Real, hash/size locked PyPI dependencies; no provider credentials.
            return original_download(**kwargs)
        payload = wheel.read_bytes()
        require(hashlib.sha256(payload).hexdigest() == kwargs["expected_sha256"], "local_transport_hash_mismatch")
        size = kwargs.get("expected_size")
        require(size is None or size == len(payload), "local_transport_size_mismatch")
        Path(kwargs["destination"]).write_bytes(payload)
        return len(payload)

    def cli(argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(argv)
        payload = json.loads(stdout.getvalue())
        return code, payload

    approved = ["project-version-update", str(project), "--target", "v" + expected_version,
                "--approve", "--affirm-external-writers-quiescent", "--reviewed-by",
                "person:wheel-runtime-reviewer", "--format", "json"]
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(project_runtime, "bootstrap_wheel_for_target",
                           return_value=(bootstrap, bootstrap.public_summary())))
        stack.enter_context(mock.patch.object(exact_human_approval_workflow, "_production_key_provider",
                           return_value=_MemoryOnlyApprovalKey()))
        update_start = time.monotonic()
        with mock.patch.object(project_runtime, "_download_exact_artifact", side_effect=transport), mock.patch.object(
            exact_human_approval_windows._CtypesTaskDialogNative, "show",
            return_value=(exact_human_approval_windows.APPROVE_BUTTON_ID, False),
        ) as native:
            code, first = cli(approved)
        require(code == 0 and first.get("status") == "updated_restart_required", "public_update_failed")
        require(native.call_count == 1, "public_native_broker_not_once")
        require(first.get("terminal_finalization", {}).get("transaction_cleanup_completed") is True, "update_cleanup_incomplete")
        update_seconds = time.monotonic() - update_start
        runtime = project_runtime.runtime_path(project, expected_version)
        before = project_runtime._candidate_inventory_snapshot(runtime)
        receipt_root = metadata / "receipts" / "version-updates"
        unchanged = {path: path.read_bytes() for path in [
            metadata / "installed-version.txt", project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE,
            *receipt_root.glob("*.json"),
        ]}
        receipt_names = {path.name for path in receipt_root.glob("*.json")}
        noop_start = time.monotonic()
        with ExitStack() as forbidden:
            for name in ("_download_exact_artifact", "prepare_runtime_candidate", "_initialize_runtime_payload"):
                forbidden.enter_context(mock.patch.object(project_runtime, name, side_effect=RuntimeError("noop_forbidden_effect")))
            forbidden.enter_context(mock.patch.object(exact_human_approval_windows._CtypesTaskDialogNative, "show",
                                                    side_effect=RuntimeError("noop_forbidden_approval")))
            code, noop = cli(approved)
        require(code == 0 and noop.get("status") == "no_change" and noop.get("files_written") == [], "public_noop_failed")
        require(noop.get("project_runtime", {}).get("preparation_revalidation", {}).get("state") == "passed", "noop_revalidation_missing")
        require(project_runtime._candidate_inventory_snapshot(runtime) == before, "noop_runtime_changed")
        require({path.name for path in receipt_root.glob("*.json")} == receipt_names, "noop_receipt_added")
        require(all(path.read_bytes() == content for path, content in unchanged.items()), "noop_pin_launcher_receipt_changed")
        noop_seconds = time.monotonic() - noop_start
        dry = ["project-version-update", str(project), "--target", "v" + expected_version,
               "--dry-run", "--format", "json"]
        code, after = cli(dry)
        require(code == 0 and after.get("status") != "terminal_cleanup_required", "noop_blocks_next_command")

    transaction = archive_services.project_update_transaction
    require(not (project / transaction.PROJECT_UPDATE_LOCK_LOGICAL).exists(), "active_update_lock_remains")
    transactions = project / transaction.TRANSACTION_ROOT_LOGICAL
    require(not transactions.exists() or not any(
        path.is_dir() and (path.name.startswith("update_") or path.name.startswith(".cleanup_update_"))
        for path in transactions.iterdir()
    ), "active_update_transaction_remains")
    require(not any(path.name == project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME for path in metadata.rglob("*")), "runtime_candidate_remains")
    runtime_python = runtime / "Scripts" / "python.exe"
    origin_script = (
        "import json,sys;from pathlib import Path;import wom_kit;"
        "from wom_kit import archive_cli,project_runtime;"
        "site=(Path(sys.prefix)/'Lib'/'site-packages').resolve();"
        "print(json.dumps({'version':wom_kit.__version__,'isolated':sys.flags.isolated==1,"
        "'origins':all(Path(m.__file__).resolve().is_relative_to(site) for m in "
        "(wom_kit,archive_cli,project_runtime)),'prefix':Path(sys.prefix).resolve()==Path(sys.argv[1]).resolve()}))"
    )
    fresh_start = time.monotonic()
    fresh = json.loads(command([str(runtime_python), "-I", "-B", "-c", origin_script, str(runtime)], cwd=root))
    fresh_seconds = time.monotonic() - fresh_start
    require(fresh == {"version": expected_version, "isolated": True, "origins": True, "prefix": True}, "runtime_origin_or_version_mismatch")
    launcher_start = time.monotonic()
    launcher = project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
    launcher_version = command([str(launcher), "--version"], cwd=project)
    launcher_seconds = time.monotonic() - launcher_start
    require(launcher_version == "archive " + expected_version, "project_launcher_version_mismatch")
    doctor_archive = root / "startup-doctor-archive"
    shutil.copytree(source / "examples" / "fake-life-archive", doctor_archive)
    startup = measure_doctor_startup([
        str(launcher), "doctor", str(doctor_archive), "--summary", "--format", "json", "--progress",
        "--object-byte-verification", "operational",
    ], cwd=project)
    claims = [json.loads(path.read_text(encoding="utf-8")) for path in
              (fixture["archive"] / "profiles/local/exact-human-approvals/claims").glob("approval_*.json")]
    require(len(claims) == 1 and claims[0].get("status") == "succeeded", "durable_broker_claim_missing")
    return {"ok": True, "schema": SCHEMA, "package_version": expected_version,
            "wheel_sha256": wheel_hash, "candidate_wheel_not_public_release_proof": True,
            "isolated_bootstrap_origins": True, "isolated_runtime_origins": True,
            "real_locked_dependencies": True, "real_public_cli_broker_writer": True,
            "update_then_noop_then_preview": True, "no_candidate_download_or_approval_on_noop": True,
            "pin_launcher_domain_receipts_unchanged_on_noop": True,
            "no_active_update_residue": True, "new_process_launcher_version": True,
            "public_launcher_doctor_startup_verified": True,
            "doctor_startup_status_event_count": startup["status_event_count"],
            "private_values_echoed": False,
            "seconds": {"bootstrap_import": round(import_seconds, 3), "update": round(update_seconds, 3),
                        "noop": round(noop_seconds, 3), "fresh_runtime_import": round(fresh_seconds, 3),
                        "project_launcher_version": round(launcher_seconds, 3),
                        "doctor_first_status": startup["first_status_seconds"],
                        "doctor_maximum_progress_gap": startup["maximum_gap_seconds"],
                        "doctor_terminal": startup["terminal_seconds"]}}


def main() -> int:
    try:
        require(len(sys.argv) == 6, "journey_arguments_invalid")
        result = run_journey(*(Path(value).resolve() for value in sys.argv[1:5]), sys.argv[5])
    except Exception as error:
        # Never print captured CLI output, private paths, transport values, or
        # traceback into the public wheel evidence. Known reasons are opaque.
        reason = str(error) if isinstance(error, JourneyCheckError) else "installed_runtime_journey_failed"
        result = {"ok": False, "schema": SCHEMA,
                  "reason_code": reason if reason in SAFE_REASON_CODES else "installed_runtime_journey_failed"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
