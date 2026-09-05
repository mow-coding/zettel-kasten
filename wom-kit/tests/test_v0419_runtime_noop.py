"""No-download runtime reuse exercised against actual Windows venv bytes."""

import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TESTS_ROOT = Path(__file__).resolve().parent
SRC_ROOT = TESTS_ROOT.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(TESTS_ROOT) not in sys.path:
    sys.path.append(str(TESTS_ROOT))

from wom_kit import project_runtime
from test_project_runtime import _supply_for_dependency, _write_dependency_wheel, _write_minimal_wheel


WINDOWS_RUNTIME = os.name == "nt" and sys.version_info[:2] == (3, 12) and platform.machine().casefold() in {"amd64", "x86_64"}


@unittest.skipUnless(WINDOWS_RUNTIME, "Real Windows CPython 3.12 runtime")
class ExistingRuntimeNoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="wom-noop-fixture-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.project = cls.root / "project"
        cls.runtime = project_runtime.runtime_path(cls.project, "0.4.3")
        artifacts = cls.runtime / project_runtime.PROJECT_RUNTIME_ARTIFACTS_NAME
        artifacts.mkdir(parents=True)
        wheel = _write_minimal_wheel(artifacts, "0.4.3")
        dependency = _write_dependency_wheel(artifacts)
        cls.supply = _supply_for_dependency(dependency)
        cls.bootstrap = project_runtime.BootstrapWheel(
            version="0.4.3", tag="v0.4.3", url="https://invalid.example/never-used",
            sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(), file_name=wheel.name,
        )
        (artifacts / project_runtime.PROJECT_RUNTIME_RETAINED_LOCK_NAME).write_bytes(cls.supply.raw_bytes)
        verification, packages, python_version = project_runtime._initialize_runtime_payload(
            cls.runtime, wheelhouse=artifacts, wheel_paths=[wheel, dependency],
            bootstrap=cls.bootstrap, supply=cls.supply,
            stage_prefix="synthetic-noop-fixture", progress_callback=None,
        )
        inventory = [
            project_runtime._artifact_inventory_entry(
                role="runtime", distribution="wom-kit", version="0.4.3", file_name=wheel.name,
                size_bytes=wheel.stat().st_size, sha256=cls.bootstrap.sha256,
            ),
            *[
                project_runtime._artifact_inventory_entry(
                    role=item.role, distribution=item.distribution, version=item.version,
                    file_name=item.file_name, size_bytes=item.size_bytes, sha256=item.sha256,
                ) for item in cls.supply.artifacts
            ],
        ]
        receipt = {
            "schema": project_runtime.PROJECT_RUNTIME_RECEIPT_SCHEMA,
            "status": "verified", "created_at": "2026-09-05T00:00:00Z",
            "target_tag": "v0.4.3", "target_version": "0.4.3", "target_commit": "b" * 40,
            "wheel_file_name": wheel.name, "wheel_sha256": "sha256:" + cls.bootstrap.sha256,
            "supply_lock_sha256": "sha256:" + cls.supply.sha256,
            "artifact_inventory": sorted(inventory, key=lambda item: item["file_name"].casefold()),
            "installed_payload_sha256": "sha256:" + project_runtime._runtime_payload_sha256(cls.runtime),
            "python_version": python_version, "installer_running_version": "0.4.3",
            "installed_distributions": packages, "verification": verification,
            "global_path_mutation": False, "previous_runtime_deleted": False, "absolute_paths_echoed": False,
        }
        cls.receipt_path = cls.runtime / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
        cls.receipt_bytes = (json.dumps(receipt, indent=2) + "\n").encode()
        cls.receipt_path.write_bytes(cls.receipt_bytes)
        project_runtime._candidate_receipt_document(cls.receipt_bytes)

    def observe(self):
        return project_runtime.verify_existing_runtime_for_noop(
            self.project, target="v0.4.3", target_commit="b" * 40,
            bootstrap=self.bootstrap, supply=self.supply,
        )

    def refresh_forged_receipt_hash(self):
        receipt = json.loads(self.receipt_bytes)
        receipt["installed_payload_sha256"] = "sha256:" + project_runtime._runtime_payload_sha256(self.runtime)
        self.receipt_path.write_bytes((json.dumps(receipt, indent=2) + "\n").encode())

    def test_valid_runtime_runs_real_checks_without_download_install_or_file_changes(self):
        before = project_runtime._candidate_inventory_snapshot(self.runtime)
        native_run = project_runtime._run_bounded
        with mock.patch.object(project_runtime, "_run_bounded", wraps=native_run) as runs, mock.patch.object(project_runtime, "_download_exact_artifact", side_effect=AssertionError("no network permitted")), mock.patch.object(project_runtime, "_initialize_runtime_payload", side_effect=AssertionError("no candidate permitted")):
            observed = self.observe()
        self.assertEqual(observed["state"], "passed", observed)
        self.assertTrue(observed["reusable"])
        self.assertFalse(observed["repair_required"])
        self.assertEqual(project_runtime._candidate_inventory_snapshot(self.runtime), before)
        self.assertEqual(self.receipt_path.read_bytes(), self.receipt_bytes)
        stages = {call.kwargs["stage"] for call in runs.call_args_list}
        self.assertTrue({"project-runtime-noop-pip-check", "project-runtime-noop-version", "project-runtime-noop-resources", "project-runtime-noop-new-process"} <= stages)
        for call in runs.call_args_list:
            self.assertIn("-I", call.args[0])
            self.assertIn("-B", call.args[0])
        self.assertNotIn(str(self.project), json.dumps(observed))

    def test_forged_receipt_cannot_authorize_tampered_startup_or_package(self):
        relative_paths = ("Scripts/python.exe", "pyvenv.cfg", "Lib/site-packages/wom_kit/__init__.py", "unapproved.dll")
        for relative in relative_paths:
            with self.subTest(relative=relative):
                target = self.runtime / relative
                original = target.read_bytes() if target.exists() else None
                try:
                    target.write_bytes(b"forged-untrusted-startup\n")
                    self.refresh_forged_receipt_hash()
                    with mock.patch.object(project_runtime, "_run_bounded", side_effect=AssertionError("untrusted process must not run")):
                        observed = self.observe()
                    self.assertEqual(observed["state"], "failed", observed)
                    self.assertFalse(observed["reusable"])
                    self.assertTrue(observed["repair_required"])
                finally:
                    if original is None:
                        target.unlink()
                    else:
                        target.write_bytes(original)
                    self.receipt_path.write_bytes(self.receipt_bytes)

    def test_missing_retained_wheel_is_repair_required_before_process_execution(self):
        wheel = self.runtime / project_runtime.PROJECT_RUNTIME_ARTIFACTS_NAME / self.bootstrap.file_name
        original = wheel.read_bytes()
        try:
            wheel.unlink()
            with mock.patch.object(project_runtime, "_run_bounded", side_effect=AssertionError("untrusted process must not run")):
                observed = self.observe()
            self.assertEqual(observed["state"], "failed", observed)
            self.assertTrue(observed["repair_required"])
        finally:
            wheel.write_bytes(original)

    def test_runtime_access_failure_is_not_repair_authority(self):
        native_lstat = Path.lstat

        def unavailable(path, *args, **kwargs):
            if path == self.runtime:
                raise PermissionError("synthetic unavailable")
            return native_lstat(path, *args, **kwargs)

        with mock.patch.object(Path, "lstat", unavailable):
            observed = self.observe()
        self.assertEqual(observed["state"], "unavailable", observed)
        self.assertFalse(observed["repair_required"])

    def test_fresh_probe_timeout_or_launch_failure_is_not_repair_authority(self):
        for error in (
            project_runtime.ProjectRuntimeError("project-runtime-noop-pip-check_timeout"),
            project_runtime.ProjectRuntimeError("project-runtime-noop-pip-check_failed"),
            OSError("synthetic child launch unavailable"),
        ):
            with self.subTest(error_type=type(error).__name__, reason=str(error)):
                # Static package/startup verification is real; only the first
                # subprocess boundary fails to return usable evidence.
                with mock.patch.object(project_runtime, "_run_bounded", side_effect=error):
                    observed = self.observe()
                self.assertEqual(observed["state"], "unavailable", observed)
                self.assertFalse(observed["repair_required"])
                self.assertFalse(observed["reusable"])

    def test_new_process_drift_invalidates_noop_proof(self):
        native_run = project_runtime._run_bounded
        unexpected = self.runtime / "unexpected"

        def drift_after_execution(*args, **kwargs):
            result = native_run(*args, **kwargs)
            if kwargs.get("stage") == "project-runtime-noop-python-version":
                unexpected.write_bytes(b"changed during verification")
            return result

        try:
            with mock.patch.object(project_runtime, "_run_bounded", side_effect=drift_after_execution):
                observed = self.observe()
            self.assertEqual(observed["state"], "failed", observed)
            self.assertEqual(observed["reason_code"], "project_runtime_existing_payload_changed")
            self.assertFalse(observed["repair_required"])
            self.assertFalse(observed["reusable"])
        finally:
            unexpected.unlink(missing_ok=True)

    def test_observed_generation_change_is_not_repair_authority(self):
        for reason in (
            "project_runtime_existing_receipt_changed",
            "project_runtime_existing_payload_changed",
            "project_runtime_tree_changed",
            "project_runtime_candidate_concurrent_drift",
        ):
            with self.subTest(reason=reason), mock.patch.object(
                project_runtime, "_candidate_inventory_snapshot",
                side_effect=project_runtime.ProjectRuntimeError(reason),
            ), mock.patch.object(project_runtime, "_run_bounded") as process:
                observed = self.observe()
            self.assertEqual(observed["state"], "failed")
            self.assertEqual(observed["reason_code"], reason)
            self.assertFalse(observed["repair_required"])
            self.assertFalse(observed["reusable"])
            process.assert_not_called()

    def test_retained_wheel_mutation_during_static_verification_cannot_authorize_repair(self):
        wheel = self.runtime / project_runtime.PROJECT_RUNTIME_ARTIFACTS_NAME / self.bootstrap.file_name
        original = wheel.read_bytes()
        verify = project_runtime._verify_retained_artifacts

        def change_after_captured_inventory(*args, **kwargs):
            wheel.write_bytes(original + b"synthetic concurrent artifact mutation")
            return verify(*args, **kwargs)

        try:
            with mock.patch.object(
                project_runtime, "_verify_retained_artifacts", side_effect=change_after_captured_inventory,
            ), mock.patch.object(project_runtime, "_run_bounded") as process:
                observed = self.observe()
            self.assertEqual(observed["state"], "failed")
            self.assertEqual(observed["reason_code"], "project_runtime_existing_payload_changed")
            self.assertFalse(observed["repair_required"])
            process.assert_not_called()
        finally:
            wheel.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
