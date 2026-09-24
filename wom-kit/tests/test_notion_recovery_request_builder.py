"""v0.4.41 (letters 142/148/156): build a Notion recovery request.

No command produced the scope bindings a recovery request needs, so the
customer could not create any request. The builder takes a private page list
and a group -> adopted credential mapping, fills the bindings from the
authenticated credential listing (replaced here by synthetic rows), and writes
a request that `notion-page-recovery-plan` accepts. No Notion data is read.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
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

from wom_kit import archive_cli

import test_v0421_lifecycle_batches_exact_approval as lifecycle

PREFIX = "profiles/local/notion-page-recovery/"


def _credential(credential_id: str, digit: str, *, ready: bool = True) -> dict:
    return {
        "credential_id": credential_id,
        "provider": "notion",
        "scope_binding": {
            "credential_id": credential_id,
            "workspace_fingerprint": "sha256:" + digit * 64,
            "scope_receipt_sha256": "sha256:" + chr(ord(digit) + 1) * 64,
            "revision": "scope-r1",
            "persisted": ready,
            "workspace_evidence_verified": ready,
        },
    }


class NotionRecoveryRequestBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-notion-build-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(lifecycle.KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.pages = [str(uuid.UUID(int=index)) for index in range(1, 6)]
        lines = [{"page_id": page, "group": "db_main" if index < 3 else "db_side"}
                 for index, page in enumerate(self.pages)]
        lines.append({"page_id": self.pages[0].replace("-", ""), "group": "db_main"})  # duplicate, compact form
        path = self.root.joinpath(*(PREFIX + "pages.jsonl").split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
        self.credentials = [_credential("cred_main_0000000000000001", "1"), _credential("cred_side_0000000000000001", "3")]
        patcher = patch.object(archive_cli, "_notion_request_build_credentials",
                               side_effect=lambda root: self.credentials)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        return code, json.loads(out.getvalue())

    def build(self, *mode: str) -> tuple[int, dict]:
        return self.run_cli("notion-page-recovery-request-build", str(self.root), "--pages", PREFIX + "pages.jsonl",
                            "--group", "db_main=cred_main_0000000000000001", "--group", "db_side=cred_side_0000000000000001",
                            "--batch-id", "synthetic-build", *mode)

    def test_dry_run_counts_pages_without_writing_or_echoing(self) -> None:
        code, result = self.build("--dry-run")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["page_count"], 5)
        self.assertEqual(result["group_counts"], {"db_main": 3, "db_side": 2})
        self.assertEqual(result["writes"], 0)
        self.assertNotIn(self.pages[0], json.dumps(result))
        self.assertFalse(self.root.joinpath(*(PREFIX + "synthetic-build.json").split("/")).exists())

    def test_written_request_is_accepted_by_the_recovery_plan(self) -> None:
        code, result = self.build("--write")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["writes"], 1)
        code, plan = self.run_cli("notion-page-recovery-plan", str(self.root), "--request",
                                  PREFIX + "synthetic-build.json", "--max-items", "5", "--dry-run")
        self.assertEqual(code, 0, plan)
        self.assertEqual(plan["counts"]["input_item_count"], 5)
        code, again = self.build("--write")
        self.assertEqual(again["blockers"], ["notion_request_output_exists"])

    def test_a_credential_that_is_not_ready_blocks(self) -> None:
        self.credentials = [_credential("cred_main_0000000000000001", "1", ready=False), _credential("cred_side_0000000000000001", "3")]
        code, result = self.build("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("notion_request_credential_not_ready", result["blockers"])
        self.assertEqual(result["credential_state"]["db_main"], "credential_not_ready")

    def test_an_unmapped_group_blocks(self) -> None:
        code, result = self.run_cli("notion-page-recovery-request-build", str(self.root), "--pages",
                                    PREFIX + "pages.jsonl", "--group", "db_main=cred_main_0000000000000001",
                                    "--batch-id", "synthetic-build", "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("notion_request_page_group_unmapped", result["blockers"])


if __name__ == "__main__":
    unittest.main()
