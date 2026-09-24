"""v0.4.41: `notion-page-trash` end to end below the Notion boundary.

A synthetic recovery lands in a copy of the fake archive; the CLI plans the
trash, then `--approve` goes through one exact approval (injected dialog and
key), issues the trash capability and hands a secret-free invocation to the
worker. The worker is replaced by one that runs the trash engine against a
fake Notion, so no process is spawned and no credential is read.
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

from wom_kit import archive_cli, archive_services, credential_workflows, notion_page_trash
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit.credential_capability import CREDENTIAL_CAPABILITY_TRASH_OPERATION
from wom_kit.notion_page_recovery import ProviderResponse, _execute_recovery, plan_recovery

import test_notion_page_recovery as recovery_fixtures
import test_notion_page_trash as trash_fixtures
import test_v0421_lifecycle_batches_exact_approval as lifecycle

REQUEST = "profiles/local/notion-page-recovery/synthetic-trash.json"
REVIEWER = "person:synthetic-trash-reviewer"


class NotionPageTrashCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-notion-trash-cli-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(lifecycle.KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.manifest = recovery_fixtures.make_manifest((3,))
        self.manifest["archive_id"] = archive_services.read_archive_id(self.root)
        path = self.root.joinpath(*REQUEST.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.manifest), encoding="utf-8")
        pages = trash_fixtures.PAGES
        provider = recovery_fixtures.FakeProvider(
            metadata={page: [recovery_fixtures.ok_metadata(page)] for page in pages[:2]}
            | {pages[2]: [ProviderResponse(404, {"reason_code": "not_found"})]},
            markdown={page: [recovery_fixtures.ok_markdown(page, f"# synthetic {page}\n")] for page in pages[:2]},
        )
        plan = plan_recovery(self.root, self.manifest, max_items=3)
        _execute_recovery(
            self.root, self.manifest, expected_plan_sha256=plan["plan_sha256"], reviewed_by="reviewer-1",
            max_items=3, provider=provider, credential_broker=recovery_fixtures.FakeBroker(),
            request_pacer=lambda: None, sleep=lambda _delay: None, jitter=lambda: 0.0,
            clock=recovery_fixtures.fixed_clock,
        )
        self.notion = trash_fixtures.TrashProvider()
        self.native = lifecycle._PagedNative()
        self.invocations: list = []
        test = self

        class FakeSpawner:
            def __init__(self, target=None) -> None:
                pass

            def run_worker(self, invocation):
                test.invocations.append(invocation)
                result = notion_page_trash.execute_trash(
                    invocation.archive_root, invocation.manifest,
                    expected_plan_sha256=invocation.expected_plan_sha256,
                    max_items=invocation.max_items, offset=invocation.offset, restore=invocation.restore,
                    provider=test.notion, credential_broker=recovery_fixtures.FakeBroker(),
                )
                return credential_workflows._NotionRecoveryWorkerRunOutcome(worker_started=True, result=result)

        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))
        stack.enter_context(patch.object(credential_workflows, "_SpawnNotionRecoveryWorkerSpawner", FakeSpawner))

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main(["notion-page-trash", str(self.root), "--request", REQUEST,
                                     "--max-items", "3", *args, "--format", "json"])
        return code, json.loads(out.getvalue())

    def test_dry_run_then_approve_trashes_after_one_dialog(self) -> None:
        code, plan = self.run_cli("--dry-run")
        self.assertEqual(code, 0, plan)
        self.assertEqual(plan["counts"]["eligible_item_count"], 2)
        code, result = self.run_cli("--approve", "--reviewed-by", REVIEWER,
                                    "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(result["counts"]["trashed"], 2)
        self.assertFalse(result["permanent_delete"])
        capability = self.invocations[0].credential_capability
        self.assertEqual(capability["operation"], CREDENTIAL_CAPABILITY_TRASH_OPERATION)
        self.assertEqual(capability["allowed_methods"], ["GET", "PATCH"])
        for page in trash_fixtures.PAGES:
            self.assertNotIn(page, json.dumps(result))
        # Everything settled: a rerun needs no dialog and no worker.
        code, again = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, again)
        self.assertEqual(again["state"], "nothing_to_write")
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(len(self.invocations), 1)

    def test_a_declined_dialog_reaches_no_worker(self) -> None:
        self.native.approve = False
        code, _error = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(self.invocations, [])
        self.assertEqual(self.notion.patches, [])

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        result = credential_workflows.execute_spawned_authenticated_notion_page_trash(
            self.root, self.manifest, expected_plan_sha256="sha256:" + "0" * 64,
            reviewed_by=REVIEWER, max_items=3,
        )
        self.assertEqual(result["blockers"], ["compound_exact_human_approval_binding_required"])
        self.assertEqual(self.notion.patches, [])


if __name__ == "__main__":
    unittest.main()
