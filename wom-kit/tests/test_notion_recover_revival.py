"""v0.4.44: `notion-recover` (Notion parent-location recovery) runs again.

A synthetic nested-tree fixture with one leaf whose parent is missing lands in
a copy of the fake archive. The CLI plans the parent-link reads with the
adopted credential's scope (listing injected), then `--approve` goes through
one exact approval (injected dialog and key), issues the ancestor capability
and hands a secret-free invocation to the worker. The worker is replaced by one
that runs the engine against a fake Notion, so no process is spawned and no
credential is read.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, command_status, credential_workflows, notion_ancestor_recovery
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit.credential_capability import CREDENTIAL_CAPABILITY_ANCESTOR_OPERATION
from wom_kit.notion_http_adapter import _parent_projection

import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = "person:synthetic-location-reviewer"
ROOT_DB = "a" * 32
PARENT = "b" * 32
GRANDPARENT = "c" * 32
LEAF = "d" * 32
TREE = "workbench/notion-nested-tree.synthetic.json"
SCOPE = {
    "credential_id": "cred_" + "s" * 20,
    "workspace_fingerprint": "sha256:" + "1" * 64,
    "scope_receipt_sha256": "sha256:" + "2" * 64,
    "revision": "rev-1",
    "persisted": True,
    "workspace_evidence_verified": True,
}


def _uuid(hex32: str) -> str:
    return f"{hex32[:8]}-{hex32[8:12]}-{hex32[12:16]}-{hex32[16:20]}-{hex32[20:]}"


class FakeNotion:
    """Parent chain: parent page -> grandparent page -> known root database."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def retrieve_parent(self, kind, object_id, credential, *, api_version):
        self.calls.append((kind, object_id))
        compact = object_id.replace("-", "")
        parents = {PARENT: ("page_id", GRANDPARENT), GRANDPARENT: ("database_id", ROOT_DB)}
        parent_type, parent_id = parents[compact]
        raw = {"object": "page", "id": _uuid(compact), "parent": {"type": parent_type, parent_type: _uuid(parent_id)},
               "in_trash": False, "properties": {"title": "SYNTHETIC PRIVATE TITLE"}}
        return SimpleNamespace(status=200, payload=_parent_projection(raw, expected_id=_uuid(compact)))


class NotionRecoverRevivalTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-notion-recover-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(lifecycle.KIT_ROOT / "examples" / "fake-life-archive", self.root)
        # Only the synthetic fixture should be auto-selected.
        for sample in (self.root / "workbench").glob("notion-nested-tree*.json"):
            sample.unlink()
        tree = {
            "fixture_kind": "notion_nested_tree_fixture",
            "source": "notion",
            "generation_roots": [{"generation_id": "DB1", "root_ref": f"database:{ROOT_DB}",
                                  "generation_label": "generation:synthetic"}],
            "minted_refs": [],
            "nodes": [
                {"node_ref": f"database:{ROOT_DB}", "node_kind": "database", "content_class": "structure",
                 "source_status": "live", "mint_state": "not_applicable", "review_status": "fixture_reviewed"},
                {"node_ref": f"page:{LEAF}", "parent_ref": f"page:{PARENT}", "node_kind": "page",
                 "content_class": "content", "source_status": "live", "mint_state": "not_minted",
                 "review_status": "fixture_reviewed"},
            ],
        }
        path = self.root.joinpath(*TREE.split("/"))
        path.write_text(json.dumps(tree), encoding="utf-8")
        self.notion = FakeNotion()
        self.native = lifecycle._PagedNative()
        self.invocations: list = []
        test = self

        class FakeSpawner:
            def __init__(self, target=None) -> None:
                pass

            def run_worker(self, invocation):
                test.invocations.append(invocation)
                result = notion_ancestor_recovery.execute_recovery(
                    invocation.archive_root, expected_plan_sha256=invocation.expected_plan_sha256,
                    scope=invocation.scope, provider=test.notion, credential_broker=lambda _scope: object(),
                    tree_path=invocation.tree_path, output_path=invocation.output_path,
                    max_items=invocation.max_items, max_depth=invocation.max_depth,
                )
                return credential_workflows._NotionRecoveryWorkerRunOutcome(worker_started=True, result=result)

        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))
        stack.enter_context(patch.object(credential_workflows, "_SpawnNotionRecoveryWorkerSpawner", FakeSpawner))
        self.rows = [{"provider": "notion", "credential_id": SCOPE["credential_id"], "is_default": True,
                      "scope_binding": dict(SCOPE)}]
        stack.enter_context(patch.object(archive_cli, "_notion_request_build_credentials",
                                         side_effect=lambda _root: self.rows))

    def run_cli(self, *args: str) -> tuple[int, dict, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main(["notion-recover", str(self.root), *args, "--format", "json"])
        return code, json.loads(out.getvalue()), out.getvalue()

    def test_dry_run_plans_parent_reads_without_provider_calls(self) -> None:
        code, plan, _raw = self.run_cli("--dry-run")
        self.assertEqual(code, 0, plan)
        self.assertEqual(plan["selected_tree_path"], TREE)
        self.assertEqual(plan["location_request_count"], 1)
        self.assertEqual(plan["provider_calls"], 0)
        self.assertEqual(self.notion.calls, [])

    def test_approve_walks_to_the_known_root_and_writes_sanitized_nodes(self) -> None:
        _code, plan, _raw = self.run_cli("--dry-run")
        code, result, raw = self.run_cli("--approve", "--reviewed-by", REVIEWER,
                                         "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(result["stop_conditions"], {"known_generation_root_ref_reached": 1})
        self.assertEqual(len(self.notion.calls), 2)
        fixture = json.loads((self.root / "workbench" / "notion-ancestor-result.live.json").read_text(encoding="utf-8"))
        refs = sorted(node["node_ref"] for node in fixture["nodes"])
        self.assertEqual(refs, sorted([f"page:{GRANDPARENT}", f"page:{PARENT}"]))
        self.assertNotIn("SYNTHETIC PRIVATE TITLE", json.dumps(fixture))
        self.assertNotIn("SYNTHETIC PRIVATE TITLE", raw)
        receipt = json.loads((self.root / result["receipt_path"]).read_text(encoding="utf-8"))
        self.assertFalse(receipt["titles_or_bodies_read"])
        invocation = self.invocations[0]
        self.assertEqual(invocation.credential_capability["operation"], CREDENTIAL_CAPABILITY_ANCESTOR_OPERATION)
        self.assertEqual(invocation.credential_capability["endpoint_classes"], ["retrieve_parent"])

    def test_no_adopted_default_credential_is_refused_before_the_dialog(self) -> None:
        self.rows = []
        code, error, _raw = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["notion_recover_preflight_blocked"])
        self.assertEqual(self.native.calls, 0)

    def test_a_declined_dialog_reads_nothing(self) -> None:
        self.native.approve = False
        code, _error, _raw = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(self.notion.calls, [])
        self.assertFalse((self.root / "workbench" / "notion-ancestor-result.live.json").exists())

    def test_the_command_is_no_longer_fixed_closed(self) -> None:
        self.assertNotIn("notion-recover", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
        self.assertIn("notion-recover", command_status.EXACT_APPROVAL_REOPENED_WRITERS)


if __name__ == "__main__":
    unittest.main()
