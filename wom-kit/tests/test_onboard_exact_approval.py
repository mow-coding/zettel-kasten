"""v0.4.41 new-user entry: `onboard --approve` creates a new archive.

Until v0.4.40 `onboard --approve` and `init` were fixed closed, so a new user
could not create any archive. Now the dry-run shows a plan digest and
`--approve` creates the archive after one exact approval bound to it. The
archive key and the approval claim live in the new archive, so only the
skeleton they need is created after the decision and removed again if the
claim cannot be written. The native dialog and the archive key are injected
so no real window opens and no Windows credential is touched.
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

from wom_kit import archive_cli, command_status, credential_secure_registry, work_session_permission
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = "person:synthetic-onboarding-reviewer"


class _ValidatingKeyProvider:
    """Like the production provider, the archive must already be valid."""

    def __init__(self) -> None:
        self.fail = False

    def use_key(self, root, consumer, *, create_if_missing=False):
        credential_secure_registry._validate_archive(root)
        if self.fail:
            raise RuntimeError("synthetic key failure")
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class OnboardExactApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-onboard-")
        self.addCleanup(temporary.cleanup)
        self.target = Path(temporary.name) / "archives" / "personal"
        self.native = lifecycle._PagedNative()
        self.keys = _ValidatingKeyProvider()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=self.keys))

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        return code, json.loads(out.getvalue())

    def onboard(self, *mode: str) -> tuple[int, dict]:
        return self.run_cli("onboard", "--target-root", str(self.target), "--type", "personal",
                            "--archive-id", "archive:personal:synthetic", "--principal-id", "person:synthetic",
                            *mode)

    def test_dry_run_shows_the_plan_digest_and_writes_nothing(self) -> None:
        code, plan = self.onboard("--dry-run")
        self.assertEqual(code, 0, plan)
        self.assertRegex(plan["plan_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertFalse(self.target.exists())
        self.assertEqual(self.native.calls, 0)

    def test_approve_creates_a_strict_clean_archive_after_one_dialog(self) -> None:
        _code, plan = self.onboard("--dry-run")
        code, result = self.onboard("--approve", "--reviewed-by", REVIEWER,
                                    "--expected-plan-sha256", plan["plan_sha256"])
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(result["doctor"]["errors"], 0, result["doctor"])
        self.assertEqual(result["doctor"]["warnings"], 0, result["doctor"])
        self.assertTrue((self.target / "archive.yml").is_file())
        self.assertTrue((self.target / "zettel-kasten").is_dir())
        receipt = json.loads((self.target / result["receipt_path"]).read_text(encoding="utf-8"))
        self.assertEqual(receipt["plan_sha256"], plan["plan_sha256"])
        self.assertEqual(receipt["reviewed_by"], REVIEWER)
        claims = list((self.target / "profiles" / "local" / "exact-human-approvals" / "claims").rglob("*.json"))
        self.assertTrue(claims)

    def test_a_declined_dialog_creates_nothing(self) -> None:
        self.native.approve = False
        code, _error = self.onboard("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(self.native.calls, 1)
        self.assertFalse(self.target.exists())

    def test_a_claim_failure_removes_the_skeleton(self) -> None:
        self.keys.fail = True
        code, error = self.onboard("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["onboard_workflow_precondition_failed"])
        self.assertFalse(self.target.exists())
        self.target.mkdir(parents=True)
        code, _error = self.onboard("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertTrue(self.target.is_dir())
        self.assertEqual(list(self.target.iterdir()), [])

    def test_a_non_empty_target_or_changed_plan_never_opens_the_dialog(self) -> None:
        code, error = self.onboard("--approve", "--reviewed-by", REVIEWER, "--expected-plan-sha256", "sha256:" + "0" * 64)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["onboard_plan_changed"])
        self.target.mkdir(parents=True)
        (self.target / "keep.txt").write_text("existing", encoding="utf-8")
        code, error = self.onboard("--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["onboard_preflight_blocked"])
        code, error = self.onboard("--approve")
        self.assertEqual(error["reason_codes"], ["onboard_reviewer_required"])
        self.assertEqual(self.native.calls, 0)
        self.assertEqual(sorted(path.name for path in self.target.iterdir()), ["keep.txt"])

    def test_init_approve_is_onboard_approve(self) -> None:
        code, result = self.run_cli("init", str(self.target), "--type", "personal",
                                    "--archive-id", "archive:personal:synthetic", "--principal-id", "person:synthetic",
                                    "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 1)
        self.assertTrue((self.target / "archive.yml").is_file())

    def test_inventory_is_open(self) -> None:
        self.assertNotIn("onboard", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
        self.assertIn(windows.ExactHumanApprovalOperation.onboard_archive,
                      work_session_permission.GRANTABLE_OPERATIONS)


if __name__ == "__main__":
    unittest.main()
