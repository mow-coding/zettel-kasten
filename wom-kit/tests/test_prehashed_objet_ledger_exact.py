"""v0.4.41 (letters 038-039, 164, 168): prehashed-objet-ledger --approve runs again.

Hash-only registration stays: WOM-kit records the reviewed sha256/size rows as
external objets without reading or moving bytes and says it did not verify
them. The dry-run returns a plan digest over the ledger files, the store label
and the exact candidates; `--approve` registers them after one exact approval
bound to it. The native dialog and archive key are injected.
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

REVIEWER = "person:synthetic-ledger-reviewer"


class PrehashedObjetLedgerExactTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-prehashed-")
        self.addCleanup(temporary.cleanup)
        tmp = Path(temporary.name)
        self.root = tmp / "archive"
        shutil.copytree(lifecycle.KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.ledger = tmp / "ledger.jsonl"
        self.ledger.write_text(
            "".join(json.dumps({"sha256": digit * 64, "bytes": 10 + index, "mime": "text/plain"}) + "\n"
                    for index, digit in enumerate("ab")),
            encoding="utf-8",
        )
        self.native = lifecycle._PagedNative()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=lifecycle._KeyProvider()))

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main(["prehashed-objet-ledger", str(self.root), "--ledger", str(self.ledger),
                                     "--store-ref", "synthetic-store", *args, "--format", "json"])
        return code, json.loads(out.getvalue())

    def manifest_ids(self) -> set[str]:
        return {str(row.get("object_id")) for row in archive_services.load_manifest_records(self.root)}

    def test_approve_registers_the_reviewed_hashes_after_one_dialog(self) -> None:
        code, plan = self.run_cli("--dry-run")
        self.assertEqual(code, 0, plan)
        self.assertRegex(plan["plan_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(plan["registration"]["would_append_manifest_records"], 2)
        code, result = self.run_cli("--approve", "--reviewed-by", REVIEWER,
                                    "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(result["registration"]["appended_manifest_records"], 2)
        self.assertFalse(result["registration"]["byte_verification_by_wom_kit"])
        self.assertIn("sha256:" + "a" * 64, self.manifest_ids())
        # Everything is registered: a rerun needs no dialog.
        code, again = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, again)
        self.assertEqual(self.native.calls, 1)

    def test_a_changed_ledger_is_refused_before_the_dialog(self) -> None:
        _code, plan = self.run_cli("--dry-run")
        with self.ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"sha256": "c" * 64, "bytes": 5, "mime": "text/plain"}) + "\n")
        code, error = self.run_cli("--approve", "--reviewed-by", REVIEWER,
                                   "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["prehashed_objet_ledger_register_plan_changed"])
        self.assertEqual(self.native.calls, 0)
        self.assertNotIn("sha256:" + "a" * 64, self.manifest_ids())

    def test_a_declined_dialog_registers_nothing(self) -> None:
        self.native.approve = False
        code, _error = self.run_cli("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertNotIn("sha256:" + "a" * 64, self.manifest_ids())

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        result = archive_services.prehashed_objet_ledger_register(
            self.root, [self.ledger], store_ref="synthetic-store", dry_run=False, approve=True,
            reviewed_by=REVIEWER,
        )
        self.assertEqual(result["reason_codes"], [command_status.COMPOUND_APPROVAL_REASON_CODE])

    def test_inventory_is_open(self) -> None:
        self.assertNotIn("prehashed-objet-ledger", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)


if __name__ == "__main__":
    unittest.main()
