"""Real synthetic wheel installs through stable -> beta -> beta -> stable.

Only artifact transport/supply fixtures and native button choice are controlled.
The public CLI, approval broker, updater, pip, receipts and fresh processes run.
The release workflow additionally tests the complete generated WOM wheel.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "src"))
if str(TESTS) not in sys.path:
    sys.path.append(str(TESTS))
from wom_kit import archive_cli, archive_services, project_runtime
from wom_kit import exact_human_approval_windows, exact_human_approval_workflow
import test_cli
from test_v0419_update_noop_journey import _MemoryOnlyApprovalKey


@unittest.skipUnless(os.name == "nt" and sys.version_info[:2] == (3, 12), "Windows CPython 3.12 runtime")
class BetaUpdateJourneyTests(unittest.TestCase):
    def test_stable_beta_beta_stable_actual_installs(self):
        helper = test_cli.ArchiveCliTests(methodName="runTest")
        self.addCleanup(helper.doCleanups)
        with tempfile.TemporaryDirectory(prefix="wom-beta-synthetic-") as temp:
            root = Path(temp)
            fixture = helper.create_project_version_update_fixture(root, project_runtime_policy=True)
            major, minor, patch_number = map(int, fixture["target_version"].split("."))
            final = f"{major}.{minor}.{patch_number + 1}"
            versions = [fixture["target_version"], final + "b1", final + "b2", final]
            for index, version in enumerate(versions):
                with self.subTest(target=version):
                    if index:
                        helper.write_project_update_fixture_version(fixture["upstream"], version)
                        helper.git_fixture_command(fixture["upstream"], "add", "wom-kit/pyproject.toml", "wom-kit/src/wom_kit/__init__.py", "wom_kit/__init__.py", "wom-kit/src/wom_kit/_resources/resource-manifest.json")
                        helper.git_fixture_command(fixture["upstream"], "commit", "-m", "synthetic next channel")
                        helper.git_fixture_command(fixture["upstream"], "tag", "-a", "v" + version, "-m", "synthetic channel")
                        fixture.update(target_version=version, target_tag="v" + version,
                                       target_commit=helper.git_fixture_command(fixture["upstream"], "rev-parse", "HEAD"))
                    artifact_root = root / f"artifacts-{index}"
                    artifact_root.mkdir()
                    artifacts = helper.project_runtime_candidate_artifact_fixture(artifact_root, fixture)
                    args = ["project-version-update", str(fixture["project_root"]), "--target", "v" + version,
                            "--approve", "--affirm-external-writers-quiescent", "--reviewed-by",
                            "person:synthetic-beta-reviewer", "--format", "json"]
                    with ExitStack() as stack:
                        stack.enter_context(patch.object(archive_services, "wom_kit_project_update_runtime_policy", return_value=artifacts["policy"]))
                        stack.enter_context(patch.object(archive_services, "wom_kit_project_update_runtime_supply", return_value=artifacts["supply"]))
                        stack.enter_context(patch.object(project_runtime, "bootstrap_wheel_for_target", return_value=(artifacts["bootstrap"], artifacts["bootstrap_summary"])))
                        stack.enter_context(patch.object(project_runtime, "_download_exact_artifact", side_effect=artifacts["download"]))
                        stack.enter_context(patch.object(exact_human_approval_workflow, "_production_key_provider", return_value=_MemoryOnlyApprovalKey()))
                        native = stack.enter_context(patch.object(exact_human_approval_windows._CtypesTaskDialogNative, "show", return_value=(exact_human_approval_windows.APPROVE_BUTTON_ID, False)))
                        code, stdout, stderr = helper.run_cli_split(args)
                        self.assertTrue(stdout.strip(), f"No JSON for {version}: exit={code}; {stderr}")
                        result = json.loads(stdout)
                        self.assertEqual(code, 0, result)
                        self.assertEqual(result["status"], "updated_restart_required", result)
                        self.assertTrue(result["terminal_finalization"]["transaction_cleanup_completed"])
                        self.assertEqual(native.call_count, 1)
                    self.assertEqual((fixture["metadata_root"] / "installed-version.txt").read_text().strip(), "v" + version)
                    runtime = project_runtime.runtime_path(fixture["project_root"], version)
                    actual = subprocess.check_output([str(runtime / "Scripts/python.exe"), "-I", "-B", "-c", "import wom_kit;print(wom_kit.__version__)"], text=True).strip()
                    self.assertEqual(actual, version)
            self.assertEqual(archive_services.latest_semver_tag(["v" + v for v in versions]), "v" + final)


if __name__ == "__main__":
    unittest.main()
