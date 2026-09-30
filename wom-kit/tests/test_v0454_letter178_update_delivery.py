"""v0.4.54 (beta letter 178): a finished update that did not finish its result delivery.

The customer's approved update to v0.4.52 succeeded but reported
post_update_attention_required with durable_result_delivery_acknowledged false,
and the next version's preview stopped with terminal_cleanup_outcome_unknown
and "report to WOM development". Reproduced here through the real CLI:

* one unrelated operation journal that fails the strict reader (a torn last
  line from a killed process) made the delivery re-check raise, and the CLI
  silently recorded "not acknowledged";
* a delivery renamed to display-pending but never finalised made the next
  preview look clean while approve failed generically;
* the advised --resume command lacked --affirm-external-writers-quiescent, so
  copying it failed;
* outcome_unknown named no cause.

Synthetic project fixture, fake approval window; no client data.
"""

from contextlib import ExitStack
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wom_kit import archive_services, exact_human_approval_windows, exact_human_approval_workflow
from wom_kit import operation_control, project_runtime

import test_cli
from test_v0419_update_noop_journey import _MemoryOnlyApprovalKey


class UpdateDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.helper = test_cli.ArchiveCliTests(methodName="runTest")
        self.addCleanup(self.helper.doCleanups)
        temporary = tempfile.TemporaryDirectory(prefix="wom-l178-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.fixture = self.helper.create_project_version_update_fixture(self.root, project_runtime_policy=True)
        self.project = self.fixture["project_root"]
        self.steps = 0

    def bump(self, version):
        helper, fixture = self.helper, self.fixture
        helper.write_project_update_fixture_version(fixture["upstream"], version)
        helper.git_fixture_command(fixture["upstream"], "add", "wom-kit/pyproject.toml", "wom-kit/src/wom_kit/__init__.py",
                                   "wom_kit/__init__.py", "wom-kit/src/wom_kit/_resources/resource-manifest.json")
        helper.git_fixture_command(fixture["upstream"], "commit", "-m", "synthetic next")
        helper.git_fixture_command(fixture["upstream"], "tag", "-a", "v" + version, "-m", "synthetic")
        fixture.update(target_version=version, target_tag="v" + version,
                       target_commit=helper.git_fixture_command(fixture["upstream"], "rev-parse", "HEAD"))

    def run_cli(self, args, extra=()):
        # A fresh process never holds the in-memory delivery capability.
        with archive_services._PROJECT_UPDATE_TERMINAL_DELIVERY_CAPABILITIES_LOCK:
            archive_services._PROJECT_UPDATE_TERMINAL_DELIVERY_CAPABILITIES.clear()
        self.steps += 1
        artifact_root = self.root / f"artifacts-{self.steps}"
        artifact_root.mkdir()
        artifacts = self.helper.project_runtime_candidate_artifact_fixture(artifact_root, self.fixture)
        with ExitStack() as stack:
            stack.enter_context(patch.object(archive_services, "wom_kit_project_update_runtime_policy", return_value=artifacts["policy"]))
            stack.enter_context(patch.object(archive_services, "wom_kit_project_update_runtime_supply", return_value=artifacts["supply"]))
            stack.enter_context(patch.object(project_runtime, "bootstrap_wheel_for_target",
                                             return_value=(artifacts["bootstrap"], artifacts["bootstrap_summary"])))
            stack.enter_context(patch.object(project_runtime, "_download_exact_artifact", side_effect=artifacts["download"]))
            stack.enter_context(patch.object(exact_human_approval_workflow, "_production_key_provider", return_value=_MemoryOnlyApprovalKey()))
            stack.enter_context(patch.object(exact_human_approval_windows._CtypesTaskDialogNative, "show",
                                             return_value=(exact_human_approval_windows.APPROVE_BUTTON_ID, False)))
            for context in extra:
                stack.enter_context(context)
            code, stdout, _stderr = self.helper.run_cli_split(args)
        try:
            return code, json.loads(stdout)
        except ValueError:
            return code, {}

    def approve_first(self, extra=()):
        return self.run_cli(["project-version-update", str(self.project), "--target", "v" + self.fixture["target_version"],
                             "--approve", "--affirm-external-writers-quiescent", "--reviewed-by", "person:synthetic-reviewer",
                             "--format", "json"], extra)

    def next_preview(self):
        if not hasattr(self, "next_version"):
            major, minor, patch_level = map(int, self.fixture["target_version"].split("."))
            self.next_version = f"{major}.{minor}.{patch_level + 1}"
            self.bump(self.next_version)
        return self.run_cli(["project-version-update", str(self.project), "--target", "v" + self.next_version,
                             "--dry-run", "--format", "json"])

    def resume(self):
        return self.run_cli(["project-version-update", str(self.project), "--resume",
                             "--affirm-external-writers-quiescent", "--format", "json"])

    def test_an_unrelated_torn_journal_no_longer_blocks_result_delivery(self):
        operations = self.project / ".zettel-kasten" / "operations"
        operations.mkdir(parents=True, exist_ok=True)
        (operations / ("ab" * 32 + ".jsonl")).write_bytes(b'{"torn": tr')
        code, result = self.approve_first()
        self.assertEqual(code, 0, result)
        self.assertTrue(result["terminal_finalization"]["durable_result_delivery_acknowledged"])
        self.assertFalse(result["post_update_attention_required"])
        code, preview = self.next_preview()
        self.assertEqual(code, 0, preview)
        self.assertNotEqual(preview.get("reason_code"), "project_version_update_terminal_cleanup_outcome_unknown")

    def test_an_unfinished_display_pending_delivery_is_named_with_the_exact_command(self):
        real_discover = operation_control.discover_pending_project_update_terminal_delivery

        def discover(root, *, allow_active_handoff=False):
            if not allow_active_handoff:
                raise OSError("synthetic post-acknowledgement discovery failure")
            return real_discover(root, allow_active_handoff=allow_active_handoff)

        code, result = self.approve_first(
            [patch.object(operation_control, "discover_pending_project_update_terminal_delivery", side_effect=discover)])
        self.assertEqual(code, 0, result)
        terminal = result["terminal_finalization"]
        self.assertFalse(terminal["durable_result_delivery_acknowledged"])
        self.assertEqual(terminal["result_delivery_failure_code"], "delivery_discovery_failed")
        self.assertTrue(result["post_update_attention_required"])
        code, preview = self.next_preview()
        self.assertEqual(code, 1, preview)
        self.assertEqual(preview["outcome_basis"], "previous_update_result_delivery_pending")
        self.assertIn("--resume --affirm-external-writers-quiescent", preview["next_safe_actions"][0])
        code, resumed = self.resume()
        self.assertEqual(code, 0, resumed)
        code, preview = self.next_preview()
        self.assertEqual(code, 0, preview)
        self.assertNotEqual(preview.get("outcome_basis"), "previous_update_result_delivery_pending")

    def test_an_unacknowledged_delivery_names_its_cause_and_the_copyable_command(self):
        code, result = self.approve_first(
            [patch.object(archive_services, "_project_update_acknowledge_terminal_result_delivery", return_value=False)])
        self.assertEqual(code, 0, result)
        self.assertEqual(result["terminal_finalization"]["result_delivery_failure_code"], "delivery_not_attempted")
        self.assertTrue(result["post_update_attention_required"])
        self.assertTrue(any("--resume --affirm-external-writers-quiescent" in action
                            for action in result.get("next_safe_actions") or []))
        code, preview = self.next_preview()
        self.assertEqual(code, 1, preview)
        self.assertNotEqual(preview["reason_code"], "project_version_update_terminal_cleanup_outcome_unknown")
        code, resumed = self.resume()
        self.assertEqual(code, 0, resumed)
        code, preview = self.next_preview()
        self.assertEqual(code, 0, preview)


class OutcomeUnknownCauseTests(unittest.TestCase):
    def test_the_unknown_result_names_its_cause_and_a_names_free_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            terminal = project / ".zettel-kasten" / "private" / "version-update-terminal"
            terminal.mkdir(parents=True)
            (terminal / "display-pending.json").write_text("{}", encoding="utf-8")
            updates = project / ".zettel-kasten" / "private" / "version-updates"
            updates.mkdir(parents=True)
            (updates / ".runtime-candidate-cleanup_secret-name.json").write_text("{}", encoding="utf-8")
            (project / ".zettel-kasten" / "version-update.lock").write_text("x", encoding="utf-8")
            result = archive_services._project_update_terminal_cleanup_outcome_unknown_result(
                operator_resume_identifiers_supplied=False, archive_identity_metadata_read=False,
                cause_code="transaction_residue_unresolved", project_root=project)
        self.assertEqual(result["cause_code"], "transaction_residue_unresolved")
        inventory = result["residue_inventory"]
        self.assertTrue(inventory["version_update_lock_present"])
        self.assertTrue(inventory["terminal_display_pending_present"])
        self.assertEqual(inventory["runtime_cleanup_sidecar_count"], 1)
        self.assertNotIn("secret-name", json.dumps(result))
        self.assertIn("--affirm-external-writers-quiescent", result["next_safe_actions"][1])
        unknown = archive_services._project_update_terminal_cleanup_outcome_unknown_result(
            operator_resume_identifiers_supplied=False, archive_identity_metadata_read=False, cause_code="not-a-code")
        self.assertEqual(unknown["cause_code"], "unclassified")

    def test_the_advised_delivery_command_is_complete(self):
        self.assertIn("archive project-version-update <archive-root> --resume --affirm-external-writers-quiescent",
                      archive_services._PROJECT_UPDATE_TERMINAL_DELIVERY_ACTION)


if __name__ == "__main__":
    unittest.main()
