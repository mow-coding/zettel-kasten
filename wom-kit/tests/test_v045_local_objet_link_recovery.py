from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path, PurePosixPath

from wom_kit import archive_cli, archive_services
from wom_kit.local_objet_link_recovery import (
    zettel_objet_link_recovery_plan,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = KIT_ROOT / "examples" / "fake-life-archive"
ZETTEL = "zet_20240504_fake_lunch_thought"
OBJECT_ID = (
    "sha256:"
    "9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
)
SOURCE_ID = "12345678-1234-1234-1234-1234567890ab"
PRIVATE_TITLE = "PRIVATE RECOVERY TITLE 8841"


class V045LocalObjetLinkRecoveryTests(unittest.TestCase):
    def archive(self, parent: Path, *, source_id: bool, matching_title: bool) -> Path:
        root = parent / "archive"
        shutil.copytree(FIXTURE, root)
        zettel = root / "zettels" / f"{ZETTEL}.md"
        text = zettel.read_text(encoding="utf-8")
        if matching_title:
            text = text.replace(
                "title: Fake thought while eating alone",
                f"title: {PRIVATE_TITLE}",
                1,
            )
        if source_id:
            text = text.replace(
                "  domain: personal\n",
                f"  source_page_id: {SOURCE_ID}\n  domain: personal\n",
                1,
            )
        zettel.write_text(text, encoding="utf-8", newline="")
        self.write_receipt(root)
        return root

    @staticmethod
    def receipt_relative() -> str:
        return "receipts/objet-capture/20260822T000000Z-000000000001.json"

    def write_receipt(self, root: Path) -> None:
        digest = OBJECT_ID.removeprefix("sha256:")
        item = {
            "item_id": "item:synthetic",
            "approved_object_id": OBJECT_ID,
            "object_id": OBJECT_ID,
            "logical_key": f"objects/sha256/{digest[:2]}/{digest}",
            "size_bytes": 42,
            "mime": "text/markdown",
            "source_staged_path": (
                f"staging/private/{PRIVATE_TITLE} {SOURCE_ID.replace('-', '')}.md"
            ),
            "original_filename": (
                f"{PRIVATE_TITLE} {SOURCE_ID.replace('-', '')}.md"
            ),
            "source_intake_plan_sha256": "sha256:" + "1" * 64,
            "planned_action": "capture",
            "action": "captured",
            "stored_sha256_verified": True,
            "manifest_record_appended": True,
            "blockers": [],
            "warnings": [],
        }
        receipt_name = PurePosixPath(self.receipt_relative()).name
        receipt = {
            "receipt_id": f"receipt:objet-capture:{receipt_name[:-5]}",
            "schema": "wom-kit/objet-capture-receipt/v0.2",
            "dry_run": False,
            "ok": True,
            "aborted": False,
            "archive_id": archive_services.read_archive_id(root),
            "selection_manifest_id": "approved:local-objet-capture:test",
            "selection_manifest_sha256": "sha256:" + "2" * 64,
            "project_intake_context": None,
            "reviewed_by": "person:test",
            "captured_at": "2026-08-22T00:00:00Z",
            "items": [item],
            "summary": archive_services.objet_capture_summary(
                [item], approve=True
            ),
            "blockers": [],
            "warnings": [],
        }
        path = root.joinpath(*self.receipt_relative().split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_unique_preserved_source_id_builds_exact_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(
                Path(tmp), source_id=True, matching_title=True
            )
            result = zettel_objet_link_recovery_plan(
                root,
                capture_receipt=self.receipt_relative(),
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["summary"]["capture_item_count"], 1)
            self.assertEqual(result["summary"]["exact_link_ready"], 1)
            self.assertEqual(result["summary"]["classified_item_count"], 1)
            manifest = result["exact_operation_manifest"]
            self.assertIsInstance(manifest, dict)
            self.assertEqual(manifest["operation"], "zettel_objet_link_recovery")
            self.assertEqual(manifest["item_count"], 1)
            self.assertNotIn(PRIVATE_TITLE, json.dumps(result))
            self.assertNotIn(SOURCE_ID, json.dumps(result))
            self.assertNotIn(SOURCE_ID.replace("-", ""), json.dumps(result))
            self.assertNotIn(OBJECT_ID, json.dumps(result))

    def test_title_only_match_requires_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(
                Path(tmp), source_id=False, matching_title=True
            )
            result = zettel_objet_link_recovery_plan(
                root,
                capture_receipt=self.receipt_relative(),
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["summary"]["review_required"], 1)
            self.assertIsNone(result["exact_operation_manifest"])
            self.assertEqual(
                result["items"][0]["blocker_codes"],
                ["title_only_evidence_requires_review"],
            )

    def test_no_match_is_complete_no_target_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(
                Path(tmp), source_id=False, matching_title=False
            )
            result = zettel_objet_link_recovery_plan(
                root,
                capture_receipt=self.receipt_relative(),
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["summary"]["no_target"], 1)
            self.assertEqual(result["summary"]["classified_item_count"], 1)
            self.assertEqual(result["privacy_guards"]["writes"], False)

    def test_duplicate_key_receipt_fails_closed_without_private_echo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(
                Path(tmp), source_id=True, matching_title=True
            )
            path = root.joinpath(*self.receipt_relative().split("/"))
            raw = path.read_text(encoding="utf-8")
            path.write_text(
                raw.replace('"ok": true,', '"ok": true,\n  "ok": true,', 1),
                encoding="utf-8",
            )
            result = zettel_objet_link_recovery_plan(
                root,
                capture_receipt=self.receipt_relative(),
            )
            self.assertFalse(result["ok"])
            self.assertEqual(
                result["blockers"],
                ["zettel_objet_link_recovery_evidence_invalid"],
            )
            self.assertNotIn(PRIVATE_TITLE, json.dumps(result))

    def test_cli_reuses_existing_family_and_keeps_receipt_apply_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(
                Path(tmp), source_id=False, matching_title=False
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = archive_cli.main(
                    [
                        "zettel-objet-link",
                        str(root),
                        "--capture-receipt",
                        self.receipt_relative(),
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual(code, 0, (stdout.getvalue(), stderr.getvalue()))
            result = json.loads(stdout.getvalue())
            self.assertEqual(
                result["lifecycle_action"],
                "zettel_objet_link_recovery_plan",
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                blocked = archive_cli.main(
                    [
                        "zettel-objet-link",
                        str(root),
                        "--capture-receipt",
                        self.receipt_relative(),
                        "--approve",
                    ]
                )
            self.assertEqual(blocked, 1)

if __name__ == "__main__":
    unittest.main()
