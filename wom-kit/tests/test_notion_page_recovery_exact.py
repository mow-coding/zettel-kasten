"""v0.4.41 (letters 116-118, 142/148/156): Notion page recovery runs again.

Until v0.4.40 the execution was fixed closed and the request contract
accepted only the letter-118 577+43 batch, so no other request could run.
Now any self-consistent reviewed request plans, and execution runs after one
exact approval (a native dialog, or none under a valid session grant) bound
to the plan digest, which covers the exact page list. The recovery engine
itself is covered by test_notion_page_recovery / test_credential_workflows;
here the engine is replaced so no credential or network is touched, and the
native dialog and archive key are injected so no real window opens.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, command_status, credential_workflows, work_session_permission
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = "person:synthetic-notion-reviewer"
REQUEST = "profiles/local/notion-page-recovery/synthetic.json"


def _request(expected_item_count: int = 2) -> dict:
    return {
        "schema": "wom-kit/notion-page-recovery-request/v0.1",
        "batch_id": "synthetic-small-batch",
        "archive_id": "archive:personal:fake-life",
        "expected_item_count": expected_item_count,
        "groups": [{
            "group_id": "synthetic_db",
            "expected_count": 2,
            "scope_binding": {
                "credential_id": "cred_synthetic_00000001",
                "workspace_fingerprint": "sha256:" + "1" * 64,
                "scope_receipt_sha256": "sha256:" + "2" * 64,
                "revision": "scope-r1",
                "persisted": True,
                "workspace_evidence_verified": True,
            },
        }],
        "items": [
            {"item_id": f"reviewed-{index:04d}", "group_id": "synthetic_db", "page_id": str(uuid.UUID(int=index))}
            for index in (1, 2)
        ],
    }


class NotionPageRecoveryExactTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-notion-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(lifecycle.KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.write_request(_request())
        self.native = lifecycle._PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))
        self.engine_calls: list[dict] = []

        def fake_engine(root, manifest, **kwargs):
            self.engine_calls.append(kwargs)
            return {"ok": True, "schema": "synthetic", "plan_sha256": kwargs["expected_plan_sha256"],
                    "counts": {"processed_item_count": 2}, "blockers": []}

        stack.enter_context(patch.object(
            credential_workflows, "_execute_spawned_authenticated_notion_page_recovery_core", side_effect=fake_engine))

    def write_request(self, document: dict) -> None:
        path = self.root.joinpath(*REQUEST.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        return code, json.loads(out.getvalue())

    def test_a_small_self_consistent_request_plans(self) -> None:
        code, plan = self.run_cli("notion-page-recovery-plan", str(self.root), "--request", REQUEST, "--dry-run")
        self.assertEqual(code, 0, plan)
        self.assertEqual(plan["counts"]["input_item_count"], 2)
        self.assertEqual(plan["provider_calls"], 0)

    def test_an_inconsistent_request_is_refused(self) -> None:
        self.write_request(_request(expected_item_count=3))
        code, plan = self.run_cli("notion-page-recovery-plan", str(self.root), "--request", REQUEST, "--dry-run")
        self.assertEqual(code, 1)
        self.assertEqual(plan["reason_code"], "notion_page_recovery_reviewed_batch_contract_mismatch")

    def test_execution_runs_once_after_one_dialog(self) -> None:
        code, result = self.run_cli("notion-page-recovery", str(self.root), "--request", REQUEST,
                                    "--approve", "--reviewed-by", REVIEWER, "--max-items", "2")
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(len(self.engine_calls), 1)
        self.assertEqual(self.engine_calls[0]["reviewed_by"], REVIEWER)
        self.assertNotIn(str(uuid.UUID(int=1)), json.dumps(result))

    def test_a_declined_dialog_never_reaches_the_engine(self) -> None:
        self.native.approve = False
        code, _error = self.run_cli("notion-page-recovery", str(self.root), "--request", REQUEST,
                                    "--approve", "--reviewed-by", REVIEWER, "--max-items", "2")
        self.assertEqual(code, 1)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(self.engine_calls, [])

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        result = credential_workflows.execute_spawned_authenticated_notion_page_recovery(
            self.root, _request(), expected_plan_sha256="sha256:" + "0" * 64, reviewed_by=REVIEWER, max_items=2,
        )
        self.assertEqual(result["blockers"], [command_status.COMPOUND_APPROVAL_REASON_CODE])
        self.assertEqual(self.engine_calls, [])

    def test_inventory_is_open_and_grantable(self) -> None:
        self.assertNotIn("notion-page-recovery", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
        self.assertIn(windows.ExactHumanApprovalOperation.notion_page_recovery,
                      work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
