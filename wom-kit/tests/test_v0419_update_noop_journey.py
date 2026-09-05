"""Public CLI/broker journey using a real, locally supplied Windows wheel."""

import json
import os
import platform
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock


TESTS_ROOT = Path(__file__).resolve().parent
SRC_ROOT = TESTS_ROOT.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(TESTS_ROOT) not in sys.path:
    sys.path.append(str(TESTS_ROOT))

from wom_kit import archive_cli, archive_services, exact_human_approval_windows
from wom_kit import exact_human_approval_workflow, project_runtime
import test_cli


WINDOWS_RUNTIME = (
    os.name == "nt"
    and sys.version_info[:2] == (3, 12)
    and platform.machine().casefold() in {"amd64", "x86_64"}
)


class _MemoryOnlyApprovalKey:
    def use_key(self, _root, consumer, *, create_if_missing=False):
        key = bytearray(b"j" * 32)
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


# The installed-only driver is stdlib-only until this observer is constructed.
# Reuse its exact privacy/forwarding contract instead of maintaining two copies.
import importlib.util
_observation_spec = importlib.util.spec_from_file_location(
    "wom_runtime_journey_observation", TESTS_ROOT.parent / "tools" / "check_project_runtime_wheel_journey.py")
_observation_module = importlib.util.module_from_spec(_observation_spec)
_observation_spec.loader.exec_module(_observation_module)
_FirstUpdateObservation = _observation_module.FirstUpdateObservation

@unittest.skipUnless(WINDOWS_RUNTIME, "Real Windows CPython 3.12 runtime")
class UpdateNoopJourneyTests(unittest.TestCase):
    def test_update_then_real_noop_and_failed_revalidation(self):
        # Do not invoke the legacy helper's setUp: it replaces the public
        # approval wrapper. Only its local Git/wheel fixture builders are used.
        helper = test_cli.ArchiveCliTests(methodName="runTest")
        self.addCleanup(helper.doCleanups)
        with tempfile.TemporaryDirectory(prefix="wom-noop-journey-") as temporary:
            root = Path(temporary)
            fixture = helper.create_project_version_update_fixture(
                root, project_runtime_policy=True,
            )
            artifacts = helper.project_runtime_candidate_artifact_fixture(root, fixture)
            approved = [
                "project-version-update", str(fixture["project_root"]),
                "--target", fixture["target_tag"], "--approve",
                "--affirm-external-writers-quiescent",
                "--reviewed-by", "person:synthetic-journey-reviewer", "--format", "json",
            ]
            with ExitStack() as stack:
                stack.enter_context(mock.patch.object(
                    archive_services, "wom_kit_project_update_runtime_policy",
                    return_value=artifacts["policy"],
                ))
                stack.enter_context(mock.patch.object(
                    archive_services, "wom_kit_project_update_runtime_supply",
                    return_value=artifacts["supply"],
                ))
                stack.enter_context(mock.patch.object(
                    project_runtime, "bootstrap_wheel_for_target",
                    return_value=(artifacts["bootstrap"], artifacts["bootstrap_summary"]),
                ))
                stack.enter_context(mock.patch.object(
                    exact_human_approval_workflow, "_production_key_provider",
                    return_value=_MemoryOnlyApprovalKey(),
                ))
                observation = _FirstUpdateObservation()
                with mock.patch.object(
                    project_runtime, "_download_exact_artifact",
                    side_effect=artifacts["download"],
                ), mock.patch.object(
                    exact_human_approval_windows._CtypesTaskDialogNative, "show",
                    return_value=(exact_human_approval_windows.APPROVE_BUTTON_ID, False),
                ) as native_decision, mock.patch.object(
                    project_runtime, "prepare_runtime_candidate",
                    new=observation.boundary("runtime_prepare", project_runtime.prepare_runtime_candidate),
                ), mock.patch.object(
                    archive_cli, "_execute_project_version_update_exact_human_approved_write",
                    new=observation.boundary("approval_broker", archive_cli._execute_project_version_update_exact_human_approved_write),
                ), mock.patch.object(
                    archive_cli, "_project_version_update_privacy_safe_failure_result",
                    new=observation.failure_projector(archive_cli._project_version_update_privacy_safe_failure_result),
                ):
                    try:
                        first_code, first_stdout, first_stderr = helper.run_cli_split(approved)
                    except Exception as error:
                        observation.record("first_cli_call", error)
                        raise AssertionError(observation.diagnostic(native_observed=native_decision.called)) from None
                self.assertEqual(first_code, 0, observation.diagnostic(native_observed=native_decision.called))
                first = json.loads(first_stdout)
                self.assertEqual(first["status"], "updated_restart_required", first)
                native_decision.assert_called_once()
                self.assertTrue(first["terminal_finalization"]["transaction_cleanup_completed"])
                claims_root = fixture["archive_root"] / "profiles" / "local" / "exact-human-approvals" / "claims"
                claims = [json.loads(path.read_text(encoding="utf-8")) for path in claims_root.glob("approval_*.json")]
                self.assertEqual(len(claims), 1)
                self.assertEqual(claims[0]["status"], "succeeded")

                runtime = project_runtime.runtime_path(fixture["project_root"], fixture["target_version"])
                before_runtime = project_runtime._candidate_inventory_snapshot(runtime)
                pin = fixture["metadata_root"] / "installed-version.txt"
                launcher = fixture["project_root"] / project_runtime.PROJECT_RUNTIME_LAUNCHER_RELATIVE
                receipts = fixture["metadata_root"] / "receipts" / "version-updates"
                before_domain = {
                    path: path.read_bytes()
                    for path in [pin, launcher, *receipts.glob("*.json")]
                }
                before_receipt_names = {path.name for path in receipts.glob("*.json")}
                with mock.patch.object(
                    project_runtime, "_download_exact_artifact",
                    side_effect=AssertionError("no-op must not download"),
                ) as download, mock.patch.object(
                    project_runtime, "prepare_runtime_candidate",
                    side_effect=AssertionError("no-op must not prepare a candidate"),
                ) as prepare, mock.patch.object(
                    project_runtime, "_initialize_runtime_payload",
                    side_effect=AssertionError("no-op must not create a venv"),
                ) as initialize, mock.patch.object(
                    exact_human_approval_windows._CtypesTaskDialogNative, "show",
                    side_effect=AssertionError("no-op must not request approval"),
                ) as unexpected_native:
                    code, stdout, stderr = helper.run_cli_split(approved)
                self.assertEqual(code, 0, stdout + stderr)
                result = json.loads(stdout)
                self.assertEqual(result["status"], "no_change", result)
                self.assertEqual(result["files_written"], [])
                self.assertTrue(result["project_runtime"]["installed"]["verified"])
                self.assertEqual(result["project_runtime"]["preparation_revalidation"]["state"], "passed")
                for sentinel in (download, prepare, initialize, unexpected_native):
                    sentinel.assert_not_called()
                self.assertEqual(project_runtime._candidate_inventory_snapshot(runtime), before_runtime)
                self.assertEqual({path.name for path in receipts.glob("*.json")}, before_receipt_names)
                for path, original in before_domain.items():
                    self.assertEqual(path.read_bytes(), original)
                self.assert_no_active_update(fixture)

                module = runtime / "Lib" / "site-packages" / "wom_kit" / "__init__.py"
                original_module = module.read_bytes()
                try:
                    module.write_bytes(original_module + b"# synthetic corruption\n")
                    dry = [
                        "project-version-update", str(fixture["project_root"]),
                        "--target", fixture["target_tag"], "--dry-run", "--format", "json",
                    ]
                    dry_code, dry_stdout, dry_stderr = helper.run_cli_split(dry)
                    self.assertEqual(dry_code, 0, dry_stdout + dry_stderr)
                    self.assertTrue(json.loads(dry_stdout)["project_runtime"]["runtime_repair_required"])
                finally:
                    module.write_bytes(original_module)

                native_lstat = Path.lstat

                def unavailable(path, *args, **kwargs):
                    if path == runtime:
                        raise PermissionError("synthetic observation unavailable")
                    return native_lstat(path, *args, **kwargs)

                with mock.patch.object(Path, "lstat", unavailable), mock.patch.object(
                    project_runtime, "prepare_runtime_candidate",
                    side_effect=AssertionError("unknown runtime cannot authorize repair"),
                ) as forbidden_repair:
                    unavailable_code, unavailable_stdout, unavailable_stderr = helper.run_cli_split(dry)
                self.assertNotEqual(unavailable_code, 0, unavailable_stdout + unavailable_stderr)
                forbidden_repair.assert_not_called()
                self.assert_no_active_update(fixture)

                with mock.patch.object(
                    project_runtime, "_run_bounded",
                    side_effect=project_runtime.ProjectRuntimeError("project-runtime-noop-pip-check_timeout"),
                ), mock.patch.object(
                    project_runtime, "prepare_runtime_candidate",
                    side_effect=AssertionError("probe timeout cannot authorize repair"),
                ) as timeout_prepare, mock.patch.object(
                    project_runtime, "_download_exact_artifact",
                    side_effect=AssertionError("probe timeout must not download"),
                ) as timeout_download, mock.patch.object(
                    exact_human_approval_windows._CtypesTaskDialogNative, "show",
                    side_effect=AssertionError("probe timeout must not request approval"),
                ) as timeout_native:
                    timeout_code, timeout_stdout, timeout_stderr = helper.run_cli_split(approved)
                self.assertNotEqual(timeout_code, 0, timeout_stdout + timeout_stderr)
                timeout_result = json.loads(timeout_stdout)
                timeout_observation = timeout_result["project_runtime"]["existing_runtime_noop_verification"]
                self.assertEqual(timeout_observation["state"], "unavailable")
                self.assertFalse(timeout_observation["repair_required"])
                for sentinel in (timeout_prepare, timeout_download, timeout_native):
                    sentinel.assert_not_called()
                self.assert_no_active_update(fixture)

                original_noop = project_runtime.verify_existing_runtime_for_noop
                probe_count = 0

                def change_after_first_proof(*args, **kwargs):
                    nonlocal probe_count
                    observation = original_noop(*args, **kwargs)
                    probe_count += 1
                    if probe_count == 1 and observation["reusable"]:
                        module.write_bytes(original_module + b"# post-proof mutation\n")
                    return observation

                try:
                    with mock.patch.object(
                        project_runtime, "verify_existing_runtime_for_noop",
                        side_effect=change_after_first_proof,
                    ), mock.patch.object(
                        project_runtime, "prepare_runtime_candidate",
                        side_effect=AssertionError("drift must not silently become repair"),
                    ), mock.patch.object(
                        exact_human_approval_windows._CtypesTaskDialogNative, "show",
                        side_effect=AssertionError("drift must not request approval"),
                    ):
                        drift_code, drift_stdout, drift_stderr = helper.run_cli_split(approved)
                    self.assertNotEqual(drift_code, 0, drift_stdout + drift_stderr)
                    self.assertIn("project_version_update_state_changed_during_runtime_preparation", drift_stdout + drift_stderr)
                    self.assert_no_active_update(fixture)
                finally:
                    module.write_bytes(original_module)
                for path, original in before_domain.items():
                    self.assertEqual(path.read_bytes(), original)

                # A fully verified no-op still is not clean success if its
                # own authenticated abort-history compaction cannot finish.
                before_failed_cleanup = project_runtime._candidate_inventory_snapshot(runtime)
                with mock.patch.object(
                    archive_services.project_update_transaction.ReservedProjectUpdateTransaction,
                    "exact_cleanup", return_value=False,
                ) as refused_cleanup, mock.patch.object(
                    project_runtime, "prepare_runtime_candidate",
                    side_effect=AssertionError("no-op must not prepare a candidate"),
                ), mock.patch.object(
                    exact_human_approval_windows._CtypesTaskDialogNative, "show",
                    side_effect=AssertionError("no-op must not request approval"),
                ):
                    failed_code, failed_stdout, failed_stderr = helper.run_cli_split(approved)
                refused_cleanup.assert_called_once()
                failed_result = json.loads(failed_stdout)
                self.assertNotEqual(failed_code, 0, failed_stdout + failed_stderr)
                self.assertEqual(failed_result["status"], "terminal_cleanup_outcome_unknown")
                self.assertNotEqual(failed_result["status"], "no_change")
                self.assertTrue(failed_result["automatic_resume_discovery"])
                self.assertEqual(project_runtime._candidate_inventory_snapshot(runtime), before_failed_cleanup)
                for path, original in before_domain.items():
                    self.assertEqual(path.read_bytes(), original)

    def assert_no_active_update(self, fixture):
        transaction_type = archive_services.project_update_transaction
        self.assertFalse((fixture["project_root"] / transaction_type.PROJECT_UPDATE_LOCK_LOGICAL).exists())
        transaction_root = fixture["project_root"] / transaction_type.TRANSACTION_ROOT_LOGICAL
        if transaction_root.exists():
            for path in transaction_root.iterdir():
                if not path.is_dir():
                    continue
                self.assertFalse(path.name.startswith(".cleanup_update_"))
                if path.name.startswith("update_"):
                    self.fail("Completed command must compact its own exact terminal history")
        self.assertFalse(any(path.name == project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME for path in fixture["metadata_root"].rglob("*")))


if __name__ == "__main__":
    unittest.main()
