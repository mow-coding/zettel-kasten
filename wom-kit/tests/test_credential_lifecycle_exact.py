"""v0.4.41 (letter 119): credential-lifecycle --approve runs again.

An adopted Notion credential becomes usable for page recovery only after a
lifecycle decision records it as the workspace default (its scope binding is
then persisted). Until v0.4.40 that approval was fixed closed, so no adopted
credential could ever serve a recovery request. Now `--approve` records the
reviewed decision after one exact approval bound to the plan digest. The
Windows credential store, the native dialog and the approval key are fakes.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, command_status, credential_workflows
from wom_kit import credential_secure_intake_windows as intake_windows
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_credential_workflows as fixtures
import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = "person:synthetic-lifecycle-reviewer"


class CredentialLifecycleExactTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-lifecycle-")
        self.addCleanup(temporary.cleanup)
        self.root = fixtures.make_archive(Path(temporary.name))
        self.native = fixtures.FakeWindowsNative()
        self.key_provider = fixtures.StableArchiveFingerprintKeyProvider(
            self.native, random_bytes=lambda size: fixtures.ARCHIVE_KEY if size == 32 else b"",
        )
        plan = fixtures.make_plan()
        spawner = fixtures.InjectedCredentialAdoptionWorkerSpawner(
            native=self.native,
            notion_adapter=fixtures.NotionHttpAdapter(transport=fixtures.intake_transport()),
            key_provider=self.key_provider,
            now_factory=lambda: fixtures.NOW,
            credential_id_factory=lambda: fixtures.CREDENTIAL_ID,
            backend_id_factory=lambda: fixtures.BACKEND_ID,
        )
        adopted = fixtures.execute_windows_notion_credential_adoption(
            self.root, plan, expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=fixtures.ARCHIVE_ID, reviewed_anchor_uuid=fixtures.ANCHOR,
            requested_capabilities=fixtures.CAPABILITIES, approved=True, worker_spawner=spawner,
        )
        self.assertTrue(adopted["ok"], adopted)
        self.dialog = lifecycle._PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(intake_windows, "_CtypesWindowsNativeFacade", return_value=self.native))
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.dialog))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))
        self.workspace = str(self.row()["verified_workspace_fingerprint"])

    def row(self) -> dict:
        return credential_workflows.list_authenticated_secure_credentials(
            self.root, native=self.native, key_provider=self.key_provider,
        )["credentials"][0]

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([
                "credential-lifecycle", str(self.root), "--workspace-fingerprint", self.workspace,
                "--default-credential-id", fixtures.CREDENTIAL_ID, *args, "--format", "json",
            ])
        return code, json.loads(out.getvalue())

    def test_approve_makes_the_adopted_credential_recovery_ready(self) -> None:
        self.assertIsNot(self.row()["scope_binding"]["persisted"], True)
        code, plan = self.run_cli("--dry-run")
        self.assertEqual(code, 0, plan)
        code, result = self.run_cli("--approve", "--reviewed-by", REVIEWER,
                                    "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual(self.dialog.calls, 1)
        self.assertFalse(result["delete_performed"])
        self.assertIs(self.row()["scope_binding"]["persisted"], True)

    def test_a_declined_dialog_records_nothing(self) -> None:
        self.dialog.approve = False
        code, _error = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertIsNot(self.row()["scope_binding"]["persisted"], True)

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        result = credential_workflows.approve_authenticated_credential_lifecycle(
            self.root, provider="notion", workspace_fingerprint=self.workspace,
            selected_default_credential_id=fixtures.CREDENTIAL_ID, expected_plan_sha256="sha256:" + "0" * 64,
            reviewed_by=REVIEWER, native=self.native, key_provider=self.key_provider,
        )
        self.assertEqual(result["reason_code"], "compound_exact_human_approval_binding_required")
        self.assertIsNot(self.row()["scope_binding"]["persisted"], True)

    def test_inventory_is_open(self) -> None:
        self.assertNotIn("credential-lifecycle", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)


if __name__ == "__main__":
    unittest.main()
