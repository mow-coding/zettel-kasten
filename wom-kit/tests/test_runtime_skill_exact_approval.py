"""v0.4.41: runtime-skill-install/-uninstall --approve run again.

Until v0.4.40 both writers were fixed closed, so the WOM agent skill could
only be copied by hand. Now `--approve --archive-root <archive>` runs after
one exact approval recorded in that archive and bound to the dry-run
operation_plan_sha256; the skill itself is written to the host skills
folder. The native dialog and archive key are injected so no real window
opens.
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

from wom_kit import archive_cli, command_status, runtime_skill_install
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker

import test_v0421_lifecycle_batches_exact_approval as lifecycle

REVIEWER = "person:synthetic-skill-reviewer"


class RuntimeSkillExactApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-skill-")
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.root = self.tmp / "archive"
        shutil.copytree(lifecycle.KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.skills = self.tmp / "skills"
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

    def skill(self, command: str, *mode: str) -> tuple[int, dict]:
        return self.run_cli(command, "--host", "custom", "--scope", "custom", "--skills-root", str(self.skills), *mode)

    def test_install_then_uninstall_each_after_one_dialog(self) -> None:
        code, plan = self.skill("runtime-skill-install", "--dry-run")
        self.assertEqual(code, 0, plan)
        code, result = self.skill("runtime-skill-install", "--approve", "--reviewed-by", REVIEWER,
                                  "--expected-plan-sha256", plan["operation_plan_sha256"],
                                  "--archive-root", str(self.root))
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "installed")
        self.assertEqual(self.native.calls, 1)
        code, status = self.run_cli("runtime-skill-status", "--host", "custom", "--scope", "custom",
                                    "--skills-root", str(self.skills))
        self.assertEqual(status["status"], "managed_current", status)
        code, result = self.skill("runtime-skill-uninstall", "--approve", "--reviewed-by", REVIEWER,
                                  "--archive-root", str(self.root))
        self.assertEqual(code, 0, result)
        self.assertEqual(self.native.calls, 2)
        self.assertFalse(any(self.skills.rglob("SKILL.md")))

    def test_approve_without_archive_root_or_with_a_declined_dialog_writes_nothing(self) -> None:
        code, error = self.skill("runtime-skill-install", "--approve", "--reviewed-by", REVIEWER)
        self.assertEqual(code, 1)
        self.assertEqual(error["reason_codes"], ["runtime_skill_archive_root_required"])
        self.native.approve = False
        code, _error = self.skill("runtime-skill-install", "--approve", "--reviewed-by", REVIEWER,
                                  "--archive-root", str(self.root))
        self.assertEqual(code, 1)
        self.assertEqual(self.native.calls, 1)
        self.assertFalse(any(self.skills.rglob("SKILL.md")) if self.skills.exists() else False)

    def test_the_service_stays_blocked_without_a_claim(self) -> None:
        result = runtime_skill_install.runtime_skill_install(
            dry_run=False, approve=True, reviewed_by=REVIEWER, expected_plan_sha256="a" * 64,
            host="custom", scope="custom", skills_root=self.skills, approval_archive_root=self.root,
        )
        self.assertEqual(result["reason_codes"], [command_status.COMPOUND_APPROVAL_REASON_CODE])
        self.assertFalse(self.skills.exists())

    def test_inventory_is_open(self) -> None:
        for name in ("runtime-skill-install", "runtime-skill-uninstall"):
            self.assertNotIn(name, command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)


if __name__ == "__main__":
    unittest.main()
