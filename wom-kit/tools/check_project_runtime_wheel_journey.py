#!/usr/bin/env python3
"""Installed-only Windows runtime journey; local synthetic project, real wheel.

Run only with the wheel checker's isolated bootstrap interpreter. This file
never inserts a source checkout in sys.path. Only release transport metadata,
local wheel transport, native button choice, and an ephemeral approval key are
controlled; policy, supply, installer, broker, writers and verifiers stay real.
"""

from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
from functools import wraps
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
PHASE_SCHEMA = "wom-kit/installed-runtime-phase-event/v0.1"
PHASE_PREFIX = "WOM_RUNTIME_PHASE_V1 "
PHASES = (
    "bootstrap_import", "synthetic_project", "initial_update", "healthy_noop",
    "next_preview", "source_drift", "ref_drift", "repair_preimage",
    "repair_prepare_to_cut", "repair_cut_validation", "repair_fresh_resume",
    "repair_result_validation", "repair_independent_noop", "terminal_control_check",
    "runtime_process_origin", "project_launcher_version", "doctor_startup", "final_claim_check",
)
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
    "drift_injection_not_observed", "drift_not_blocked",
    "drift_domain_changed", "drift_requested_effect", "repair_interruption_not_reached",
    "repair_preimage_changed_before_switch", "repair_checkpoint_missing", "repair_claim_missing",
    "repair_resume_failed", "repair_resume_requested_effect", "repair_payload_not_restored",
    "repair_worker_arguments_invalid", "repair_worker_origin_invalid",
})


class JourneyCheckError(RuntimeError):
    """Only explicit harness assertions can supply public reason codes."""


class PhaseReporter:
    """Bounded harness observations, never product recovery/approval evidence.

    Keep the original stderr sink so CLI output capture cannot swallow events.
    Child cut/resume are timed at the parent's actual invocation boundaries;
    this does not claim to observe the child's internal implementation stages.
    """

    def __init__(self, *, stream=None, clock=None):
        self.stream = sys.stderr if stream is None else stream
        self.clock = time.monotonic if clock is None else clock
        self.started = self.clock()
        self.sequence = 0
        self.index = 0
        self.active = None
        self.terminal = False

    def _emit(self, stage, event):
        # Do not clamp an over-budget observation into an apparent timely one.
        # The parent retains the validated prefix and marks protocol_invalid.
        elapsed = int((self.clock() - self.started) * 1000)
        self.sequence += 1
        payload = {"schema": PHASE_SCHEMA, "sequence": self.sequence,
                   "stage": stage, "event": event, "elapsed_ms": elapsed}
        self.stream.write(PHASE_PREFIX + json.dumps(payload, separators=(",", ":")) + "\n")
        self.stream.flush()

    def begin(self, stage):
        require(not self.terminal and self.active is None and self.index < len(PHASES)
                and stage == PHASES[self.index], "installed_runtime_journey_failed")
        self.active = stage
        self._emit(stage, "begin")

    def passed(self):
        require(not self.terminal and self.active is not None, "installed_runtime_journey_failed")
        self._emit(self.active, "passed")
        self.index += 1
        self.active = None

    def fail_active(self):
        if self.active is not None and not self.terminal:
            self._emit(self.active, "failed")
            self.terminal = True


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


def command(argv: list[str], *, cwd: Path, timeout: int = 120, expected_code: int = 0) -> str:
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
    require(completed.returncode == expected_code, "synthetic_child_command_failed")
    return completed.stdout.strip()


class CallObservation:
    """Observe real Python boundaries without replacing implementations.

    Only named boundaries are wrapped; their original implementation receives
    the original arguments and supplies the unchanged result or exception. A
    post-return fault may change synthetic disk state or terminate the child,
    but cannot manufacture a verifier/writer result. No global tracing/profile
    callback slows every unrelated file-tree operation.
    """

    def __init__(self, functions, *, on_return=None):
        self.functions = functions
        self.calls = {name: 0 for name in functions}
        self.on_return = on_return
        self.originals = []

    def _wrap(self, name, original):
        @wraps(original)
        def observed(*args, **kwargs):
            self.calls[name] += 1
            value = original(*args, **kwargs)
            if self.on_return is not None:
                self.on_return(name, None, value)
            return value
        return observed

    def __enter__(self):
        try:
            for name, (owner, attribute) in self.functions.items():
                original = getattr(owner, attribute)
                self.originals.append((owner, attribute, original))
                setattr(owner, attribute, self._wrap(name, original))
        except BaseException:
            self.__exit__()
            raise
        return self

    def __exit__(self, *_exception):
        for owner, attribute, original in reversed(self.originals):
            setattr(owner, attribute, original)
        self.originals.clear()


def cli_json(archive_cli, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = archive_cli.main(argv)
    return code, json.loads(stdout.getvalue())


def approved_arguments(project: Path, version: str) -> list[str]:
    return ["project-version-update", str(project), "--target", "v" + version,
            "--approve", "--affirm-external-writers-quiescent", "--reviewed-by",
            "person:wheel-runtime-reviewer", "--format", "json"]


def local_transport(project_runtime, wheel: Path, bootstrap):
    original_download = project_runtime._download_exact_artifact

    def transport(**kwargs):
        if kwargs["url"] != bootstrap.url:
            return original_download(**kwargs)
        payload = wheel.read_bytes()
        require(hashlib.sha256(payload).hexdigest() == kwargs["expected_sha256"], "local_transport_hash_mismatch")
        size = kwargs.get("expected_size")
        require(size is None or size == len(payload), "local_transport_size_mismatch")
        Path(kwargs["destination"]).write_bytes(payload)
        return len(payload)

    return transport


def assert_no_active_update(project: Path, project_runtime, transaction) -> None:
    require(not (project / transaction.PROJECT_UPDATE_LOCK_LOGICAL).exists(), "active_update_lock_remains")
    transactions = project / transaction.TRANSACTION_ROOT_LOGICAL
    require(not transactions.exists() or not any(
        path.is_dir() and (path.name.startswith("update_") or path.name.startswith(".cleanup_update_"))
        for path in transactions.iterdir()
    ), "active_update_transaction_remains")
    require(not any(path.name == project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME
                    for path in (project / ".zettel-kasten").rglob("*")), "runtime_candidate_remains")


def exercise_installed_drift(project, version, project_runtime, archive_services, native_type, cli, phases):
    """Change real source/ref after the first genuine installed-runtime proof."""
    metadata = project / ".zettel-kasten"
    mirror = metadata / "source"
    source_file = mirror / "wom-kit/src/wom_kit/__init__.py"
    source_before = source_file.read_bytes()
    tag = "refs/tags/v" + version
    tag_before = git(mirror, "rev-parse", tag)
    head = git(mirror, "rev-parse", "HEAD")
    runtime = project_runtime.runtime_path(project, version)
    runtime_before = project_runtime._candidate_inventory_snapshot(runtime)
    receipt_root = metadata / "receipts/version-updates"
    unchanged = {path: path.read_bytes() for path in [metadata / "installed-version.txt",
                 project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE, *receipt_root.glob("*.json")]}
    receipt_names = {path.name for path in receipt_root.glob("*.json")}
    durations = {}
    for kind in ("source", "ref"):
        if kind == "ref":
            phases.begin("ref_drift")
        injected = []

        def inject(name, _frame, result):
            if name != "verify" or injected:
                return
            require(isinstance(result, dict) and result.get("reusable") is True, "drift_injection_not_observed")
            if kind == "source":
                source_file.write_bytes(source_before + b"\n# synthetic source drift\n")
            else:
                git(mirror, "update-ref", tag, head, tag_before)
            injected.append(True)

        started = time.monotonic()
        try:
            with CallObservation({"verify": (project_runtime, "verify_existing_runtime_for_noop"),
                                  "prepare": (project_runtime, "prepare_runtime_candidate"),
                                  "initialize": (project_runtime, "_initialize_runtime_payload")}, on_return=inject) as observer, mock.patch.object(
                native_type, "show", side_effect=JourneyCheckError("drift_requested_effect"),
            ) as native, mock.patch.object(project_runtime, "_download_exact_artifact",
                                          side_effect=JourneyCheckError("drift_requested_effect")) as download:
                code, result = cli(approved_arguments(project, version))
            require(injected == [True], "drift_injection_not_observed")
            revalidation = result.get("project_runtime", {}).get("preparation_revalidation", {})
            dimension = "git_snapshot" if kind == "source" else "target_refs"
            require(code != 0 and result.get("status") == "blocked"
                    and dimension in revalidation.get("changed_dimensions", []), "drift_not_blocked")
            require(native.call_count == download.call_count == 0
                    and observer.calls["prepare"] == observer.calls["initialize"] == 0, "drift_requested_effect")
            require(project_runtime._candidate_inventory_snapshot(runtime) == runtime_before
                    and all(path.read_bytes() == content for path, content in unchanged.items())
                    and {path.name for path in receipt_root.glob("*.json")} == receipt_names
                    and git(mirror, "rev-parse", "HEAD") == head, "drift_domain_changed")
            require(source_file.read_bytes() == (source_before + b"\n# synthetic source drift\n" if kind == "source" else source_before)
                    and git(mirror, "rev-parse", tag) == (head if kind == "ref" else tag_before), "drift_domain_changed")
            assert_no_active_update(project, project_runtime, archive_services.project_update_transaction)
        finally:
            # Only the harness restores its own injected synthetic fault. WOM
            # must leave changed user bytes/refs intact when it refuses a write.
            if injected:
                if kind == "source":
                    source_file.write_bytes(source_before)
                else:
                    git(mirror, "update-ref", tag, tag_before, head)
        durations[kind + "_drift"] = round(time.monotonic() - started, 3)
        phases.passed()
    return durations


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


def run_repair_worker(wheel: Path, root: Path, version: str, mode: str) -> dict[str, object]:
    """Fresh installed process: one real repair, or exact ID-free continuation."""
    require(mode in {"interrupt", "resume"}, "repair_worker_arguments_invalid")
    require(os.name == "nt" and sys.version_info[:2] == (3, 12), "windows_cpython312_required")
    from wom_kit import archive_cli, archive_services, project_runtime
    from wom_kit import exact_human_approval_windows, exact_human_approval_workflow
    import wom_kit
    verify_installed_origins({"wom_kit": wom_kit, "archive_cli": archive_cli,
                              "project_runtime": project_runtime}, Path(sys.prefix))
    direct = json.loads(importlib.metadata.distribution("wom-kit").read_text("direct_url.json") or "{}")
    wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
    require(wom_kit.__version__ == version and
            direct.get("archive_info", {}).get("hashes", {}).get("sha256") == wheel_hash, "repair_worker_origin_invalid")
    project = root / "project"
    bootstrap = project_runtime.BootstrapWheel(version=version, tag="v" + version,
        url="https://example.invalid/candidate/" + wheel.name, sha256=wheel_hash, file_name=wheel.name)
    native_calls = []

    def native_decision(*_args, **_kwargs):
        native_calls.append(True)
        require(mode == "interrupt" and len(native_calls) == 1, "repair_resume_requested_effect")
        return exact_human_approval_windows.APPROVE_BUTTON_ID, False

    observer = None

    def interrupt_at_checkpoint(name, _frame, checkpoint):
        if (mode == "interrupt" and name == "append"
                and getattr(checkpoint, "phase", None) == "runtime"
                and getattr(checkpoint, "stage", None) == "intent"):
            require(native_calls == [True] and observer.calls["prepare"] == 1
                    and observer.calls["initialize"] == 1, "repair_interruption_not_reached")
            # The real append has returned: its fsynced journal and released
            # append guard exist, but runtime promotion has not executed yet.
            os._exit(86)

    argv = (approved_arguments(project, version) if mode == "interrupt" else
            ["project-version-update", str(project), "--resume",
             "--affirm-external-writers-quiescent", "--format", "json"])
    transport = local_transport(project_runtime, wheel, bootstrap)
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(project_runtime, "bootstrap_wheel_for_target",
                            return_value=(bootstrap, bootstrap.public_summary())))
        stack.enter_context(mock.patch.object(exact_human_approval_workflow, "_production_key_provider",
                            return_value=_MemoryOnlyApprovalKey()))
        stack.enter_context(mock.patch.object(exact_human_approval_windows._CtypesTaskDialogNative, "show",
                            side_effect=native_decision))
        download = stack.enter_context(mock.patch.object(project_runtime, "_download_exact_artifact", side_effect=transport))
        observer = stack.enter_context(CallObservation({"prepare": (project_runtime, "prepare_runtime_candidate"),
            "initialize": (project_runtime, "_initialize_runtime_payload"),
            "append": (archive_services.project_update_transaction.ProjectUpdateTransaction, "append")},
            on_return=interrupt_at_checkpoint))
        code, result = cli_json(archive_cli, argv)
    require(mode == "resume", "repair_interruption_not_reached")
    require(code == 0 and result.get("status") == "updated_restart_required"
            and result.get("terminal_finalization", {}).get("transaction_cleanup_completed") is True,
            "repair_resume_failed")
    require(native_calls == [] and download.call_count == 0
            and observer.calls["prepare"] == observer.calls["initialize"] == 0, "repair_resume_requested_effect")
    assert_no_active_update(project, project_runtime, archive_services.project_update_transaction)
    return {"ok": True, "schema": SCHEMA, "worker": "resume",
            "same_approval_resumed": True, "no_new_preparation_download_or_approval": True,
            "private_values_echoed": False}


def exercise_installed_repair(wheel, root, project, version, project_runtime, archive_services, cli, native_type, phases):
    phases.begin("repair_preimage")
    runtime = project_runtime.runtime_path(project, version)
    package_file = runtime / "Lib/site-packages/wom_kit/__init__.py"
    healthy_bytes = package_file.read_bytes()
    package_file.write_bytes(healthy_bytes + b"\n# synthetic installed payload damage\n")
    damaged_inventory = project_runtime._candidate_inventory_snapshot(runtime)
    metadata = project / ".zettel-kasten"
    receipt_root = metadata / "receipts/version-updates"
    stable = {path: path.read_bytes() for path in [metadata / "installed-version.txt",
              project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE, *receipt_root.glob("*.json")]}
    receipt_names = {path.name for path in receipt_root.glob("*.json")}
    worker = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--repair-worker",
              str(wheel), str(root), version]
    phases.passed()
    phases.begin("repair_prepare_to_cut")
    started = time.monotonic()
    command([*worker, "interrupt"], cwd=root, timeout=600, expected_code=86)
    interruption_seconds = time.monotonic() - started
    phases.passed()
    phases.begin("repair_cut_validation")
    require(project_runtime._candidate_inventory_snapshot(runtime) == damaged_inventory
            and all(path.read_bytes() == content for path, content in stable.items())
            and {path.name for path in receipt_root.glob("*.json")} == receipt_names, "repair_preimage_changed_before_switch")
    transaction = archive_services.project_update_transaction
    transaction_paths = [path for path in (project / transaction.TRANSACTION_ROOT_LOGICAL).iterdir()
                         if path.is_dir() and transaction.TRANSACTION_REF_RE.fullmatch(path.name)]
    require(len(transaction_paths) == 1, "repair_checkpoint_missing")
    opened = transaction.ProjectUpdateTransaction.open(project, transaction_paths[0].name)
    journal = opened.inspect().journal
    require(journal.state == "exact" and journal.verified_prefix[-1].phase == "runtime"
            and journal.verified_prefix[-1].stage == "intent"
            and any(item.phase == "approval_bound" for item in journal.verified_prefix)
            and (transaction_paths[0] / project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME).is_dir(), "repair_checkpoint_missing")
    claims_root = project / "archive/profiles/local/exact-human-approvals/claims"
    interrupted_claims = {path: path.read_bytes() for path in claims_root.glob("approval_*.json")}
    require(len(interrupted_claims) == 2, "repair_claim_missing")
    phases.passed()
    phases.begin("repair_fresh_resume")
    started = time.monotonic()
    resumed = json.loads(command([*worker, "resume"], cwd=root, timeout=600))
    resume_seconds = time.monotonic() - started
    require(resumed == {"ok": True, "schema": SCHEMA, "worker": "resume", "same_approval_resumed": True,
                        "no_new_preparation_download_or_approval": True, "private_values_echoed": False}, "repair_resume_failed")
    phases.passed()
    phases.begin("repair_result_validation")
    require(package_file.read_bytes() == healthy_bytes
            and all(path.read_bytes() == content for path, content in stable.items())
            and len({path.name for path in receipt_root.glob("*.json")} - receipt_names) == 1
            and set(claims_root.glob("approval_*.json")) == set(interrupted_claims), "repair_payload_not_restored")
    phases.passed()
    phases.begin("repair_independent_noop")
    # Independently re-run the entire retained-artifact, static executable,
    # package-resource and new-process proof after the real writer completed.
    started = time.monotonic()
    with CallObservation({"prepare": (project_runtime, "prepare_runtime_candidate"),
                          "initialize": (project_runtime, "_initialize_runtime_payload")}) as observer, mock.patch.object(
        native_type, "show", side_effect=JourneyCheckError("repair_resume_requested_effect"),
    ) as native, mock.patch.object(project_runtime, "_download_exact_artifact",
                                  side_effect=JourneyCheckError("repair_resume_requested_effect")) as download:
        code, verified = cli(approved_arguments(project, version))
    require(code == 0 and verified.get("status") == "no_change"
            and verified.get("project_runtime", {}).get("preparation_revalidation", {}).get("state") == "passed",
            "repair_payload_not_restored")
    require(native.call_count == download.call_count == observer.calls["prepare"] == observer.calls["initialize"] == 0,
            "repair_resume_requested_effect")
    assert_no_active_update(project, project_runtime, transaction)
    phases.passed()
    return {"repair_until_interruption": round(interruption_seconds, 3), "repair_fresh_resume": round(resume_seconds, 3),
            "repair_independent_noop": round(time.monotonic() - started, 3)}


def run_journey(wheel: Path, source: Path, shim: Path, root: Path, expected_version: str, *, phases=None) -> dict[str, object]:
    phases = PhaseReporter() if phases is None else phases
    phases.begin("bootstrap_import")
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
    phases.passed()
    phases.begin("synthetic_project")
    fixture = create_project(root, source, shim, expected_version)
    project = fixture["project"]
    metadata = fixture["metadata"]
    require(isinstance(project, Path) and isinstance(metadata, Path), "fixture_invalid")
    bootstrap = project_runtime.BootstrapWheel(
        version=expected_version, tag="v" + expected_version,
        url="https://example.invalid/candidate/" + wheel.name,
        sha256=wheel_hash, file_name=wheel.name,
    )
    transport = local_transport(project_runtime, wheel, bootstrap)
    cli = lambda argv: cli_json(archive_cli, argv)
    approved = approved_arguments(project, expected_version)
    phases.passed()
    phases.begin("initial_update")
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
        phases.passed()
        phases.begin("healthy_noop")
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
        phases.passed()
        phases.begin("next_preview")
        dry = ["project-version-update", str(project), "--target", "v" + expected_version,
               "--dry-run", "--format", "json"]
        code, after = cli(dry)
        require(code == 0 and after.get("status") != "terminal_cleanup_required", "noop_blocks_next_command")
        phases.passed()
        phases.begin("source_drift")
        drift_seconds = exercise_installed_drift(project, expected_version, project_runtime, archive_services,
                                                exact_human_approval_windows._CtypesTaskDialogNative, cli, phases)
        repair_seconds = exercise_installed_repair(wheel, root, project, expected_version, project_runtime,
                                                  archive_services, cli, exact_human_approval_windows._CtypesTaskDialogNative, phases)

    phases.begin("terminal_control_check")
    transaction = archive_services.project_update_transaction
    assert_no_active_update(project, project_runtime, transaction)
    phases.passed()
    phases.begin("runtime_process_origin")
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
    phases.passed()
    phases.begin("project_launcher_version")
    launcher_start = time.monotonic()
    launcher = project / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
    launcher_version = command([str(launcher), "--version"], cwd=project)
    launcher_seconds = time.monotonic() - launcher_start
    require(launcher_version == "archive " + expected_version, "project_launcher_version_mismatch")
    phases.passed()
    phases.begin("doctor_startup")
    doctor_archive = root / "startup-doctor-archive"
    shutil.copytree(source / "examples" / "fake-life-archive", doctor_archive)
    startup = measure_doctor_startup([
        str(launcher), "doctor", str(doctor_archive), "--summary", "--format", "json", "--progress",
        "--object-byte-verification", "operational",
    ], cwd=project)
    phases.passed()
    phases.begin("final_claim_check")
    claims = [json.loads(path.read_text(encoding="utf-8")) for path in
              (fixture["archive"] / "profiles/local/exact-human-approvals/claims").glob("approval_*.json")]
    require(len(claims) == 2 and all(claim.get("status") == "succeeded" for claim in claims), "durable_broker_claim_missing")
    phases.passed()
    return {"ok": True, "schema": SCHEMA, "package_version": expected_version,
            "wheel_sha256": wheel_hash, "candidate_wheel_not_public_release_proof": True,
            "isolated_bootstrap_origins": True, "isolated_runtime_origins": True,
            "real_locked_dependencies": True, "real_public_cli_broker_writer": True,
            "update_then_noop_then_preview": True, "no_candidate_download_or_approval_on_noop": True,
            "pin_launcher_domain_receipts_unchanged_on_noop": True,
            "no_active_update_residue": True, "new_process_launcher_version": True,
            "public_launcher_doctor_startup_verified": True,
            "real_source_and_ref_drift_blocked_before_approval": True,
            "real_candidate_repair_and_process_loss_resume": True,
            "pre_switch_damaged_preimage_and_active_pin_preserved": True,
            "same_approval_identifier_free_resume_without_rebuild": True,
            "repaired_runtime_independently_reverified": True,
            "doctor_startup_status_event_count": startup["status_event_count"],
            "private_values_echoed": False,
            "seconds": {**drift_seconds, **repair_seconds,
                        "bootstrap_import": round(import_seconds, 3), "update": round(update_seconds, 3),
                        "noop": round(noop_seconds, 3), "fresh_runtime_import": round(fresh_seconds, 3),
                        "project_launcher_version": round(launcher_seconds, 3),
                        "doctor_first_status": startup["first_status_seconds"],
                        "doctor_maximum_progress_gap": startup["maximum_gap_seconds"],
                        "doctor_terminal": startup["terminal_seconds"]}}


def main() -> int:
    phases = None
    try:
        if len(sys.argv) == 6 and sys.argv[1] == "--repair-worker":
            result = run_repair_worker(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve(), sys.argv[4], sys.argv[5])
        else:
            phases = PhaseReporter()
            require(len(sys.argv) == 6, "journey_arguments_invalid")
            result = run_journey(*(Path(value).resolve() for value in sys.argv[1:5]), sys.argv[5], phases=phases)
    except Exception as error:
        if phases is not None:
            try:
                phases.fail_active()
            except Exception:
                pass  # Broken diagnostic pipe must not replace the original failure.
        # Never print captured CLI output, private paths, transport values, or
        # traceback into the public wheel evidence. Known reasons are opaque.
        reason = str(error) if isinstance(error, JourneyCheckError) else "installed_runtime_journey_failed"
        result = {"ok": False, "schema": SCHEMA,
                  "reason_code": reason if reason in SAFE_REASON_CODES else "installed_runtime_journey_failed"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
