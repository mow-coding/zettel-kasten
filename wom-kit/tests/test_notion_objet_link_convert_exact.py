"""v0.4.41 (feature request 34): Notion links convert to recovered objets.

The conversion had nothing to convert: no manifest record said which objet a
Notion locator meant. A page recovered by `notion-page-recovery` now supplies
that mapping (its projection row names the page and the recovered objet), so
a zettel link to that page gets the recovered objet as a candidate, and
`--approve` writes the embed edge and the conversion receipt after one exact
approval. The native dialog and archive key are injected.
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
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import archive_cli, archive_services, command_status
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_v0421_lifecycle_batches_exact_approval as lifecycle

PAGE_HEX = "0123456789abcdef0123456789abcdef"
PAGE_ID = "01234567-89ab-cdef-0123-456789abcdef"
NOTION_URL = f"https://www.notion.so/private-workspace/Recovered-Page-{PAGE_HEX}"
OBJECT_HEX = "c" * 64
OBJECT_ID = f"sha256:{OBJECT_HEX}"
REVIEWER = "person:synthetic-link-reviewer"
ZETTEL = "inbox/zet_notion_recovered_link.md"


class NotionObjetLinkConvertExactTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-link-convert-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(lifecycle.KIT_ROOT / "examples" / "fake-life-archive", self.root)
        manifest = self.root / "objects" / "manifests" / "files.jsonl"
        with manifest.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "object_id": OBJECT_ID, "sha256": OBJECT_HEX, "mime": "text/markdown", "size_bytes": 42,
                "logical_key": f"objects/sha256/{OBJECT_HEX[:2]}/{OBJECT_HEX}",
                "locations": [{"provider": "local", "path": f"objects/sha256/{OBJECT_HEX[:2]}/{OBJECT_HEX}",
                               "availability": "available"}],
                "provenance": {"source": "notion_page_recovery"},
            }, sort_keys=True) + "\n")
        projection = self.root / "receipts" / "import" / "notion-page-recovery-synthetic.jsonl"
        projection.parent.mkdir(parents=True, exist_ok=True)
        projection.write_text(json.dumps({"page_id": PAGE_ID, "object_id": OBJECT_ID, "outcome": "recovered"}) + "\n",
                              encoding="utf-8")
        self.zettel = self.root.joinpath(*ZETTEL.split("/"))
        self.zettel.write_text(
            "---\nid: zet_notion_recovered_link\nstatus: draft\ntitle: Recovered link\n---\n\n"
            f"See {NOTION_URL} for the source.\n",
            encoding="utf-8",
        )
        self.assertTrue(archive_services.index_archive(self.root)["ok"])
        self.native = lifecycle._PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        return code, json.loads(out.getvalue())

    def test_a_recovered_page_is_a_candidate_and_converts_after_one_dialog(self) -> None:
        code, plan = self.run_cli("notion-objet-link-plan", str(self.root), "--path", ZETTEL, "--dry-run")
        self.assertEqual(code, 0, plan)
        locator = plan["locators"][0]
        self.assertEqual(locator["candidate_state"], "matched_manifest_object")
        self.assertEqual(locator["candidates"][0]["object_id"], OBJECT_ID)
        self.assertEqual(locator["candidates"][0]["match_fields"][0]["match_kind"], "recovered_notion_page")
        common = ["notion-objet-link-convert", str(self.root), "--path", ZETTEL,
                  "--locator-fingerprint", locator["locator_fingerprint"], "--object-id", OBJECT_ID,
                  "--target-mode", "embed_edge", "--expected-occurrence-count", "1"]
        code, preview = self.run_cli(*common, "--dry-run")
        self.assertEqual(code, 0, preview)
        code, result = self.run_cli(*common, "--approve", "--reviewed-by", REVIEWER,
                                    "--expected-plan-sha256", preview["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertIn(NOTION_URL, self.zettel.read_text(encoding="utf-8"))
        self.assertNotIn(NOTION_URL, json.dumps(result))

    def test_a_declined_dialog_writes_nothing(self) -> None:
        code, plan = self.run_cli("notion-objet-link-plan", str(self.root), "--path", ZETTEL, "--dry-run")
        before = self.zettel.read_bytes()
        self.native.approve = False
        code, _error = self.run_cli(
            "notion-objet-link-convert", str(self.root), "--path", ZETTEL,
            "--locator-fingerprint", plan["locators"][0]["locator_fingerprint"], "--object-id", OBJECT_ID,
            "--target-mode", "embed_edge", "--expected-occurrence-count", "1",
            "--approve", "--reviewed-by", REVIEWER,
        )
        self.assertEqual(code, 1)
        self.assertEqual(self.zettel.read_bytes(), before)

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        result = archive_services.notion_objet_link_convert(
            self.root, relative_path=ZETTEL, locator_fingerprint="sha256:" + "0" * 64, object_id=OBJECT_ID,
            expected_occurrence_count=1, approve=True, reviewed_by=REVIEWER,
        )
        self.assertEqual(result["reason_codes"], [command_status.COMPOUND_APPROVAL_REASON_CODE])

    def test_inventory_is_open(self) -> None:
        self.assertNotIn("notion-objet-link-convert", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)


if __name__ == "__main__":
    unittest.main()
