"""Letter 173 C (2026-09-24): Git backup and ignored attribute files.

Synthetic repositories only. An ignored .gitattributes that cannot reach any
committable path no longer blocks the plan; one that can still blocks before
any filter runs. The session route names the fixed sub-cause and a preview
failure reports no effects.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from wom_kit import git_backup_plan as planner
from wom_kit import git_backup_session_command as command
from wom_kit import work_session_git_provenance as provenance
from wom_kit import work_session_git_workflow as workflow

ATTRIBUTE_CODES = {"repository_attributes_not_supported", "tracked_repository_attributes_not_supported",
                   "git_info_attributes_not_supported"}


@unittest.skipUnless(shutil.which("git"), "git is required")
class IgnoredAttributeTests(unittest.TestCase):
    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True, text=True).stdout

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "archive"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "archive-test")
        self.git("config", "user.email", "archive-test@example.invalid")
        (self.root / "archive.yml").write_text("archive_id: archive:personal:letter173\n", encoding="utf-8")
        (self.root / "tracked.txt").write_text("before\n", encoding="utf-8")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "kept.txt").write_text("kept\n", encoding="utf-8")
        self.git("add", "archive.yml", "tracked.txt", "sub/kept.txt")
        self.git("commit", "-m", "fixture")
        self.sentinel = Path(self.temp.name) / "filter-ran.sentinel"
        script = Path(self.temp.name) / "filter.py"
        script.write_text(f"from pathlib import Path\nPath({str(self.sentinel)!r}).write_text('ran')\n", encoding="utf-8")
        self.git("config", "filter.malicious.clean", f'"{sys.executable}" "{script}"')

    def attribute_blockers(self):
        return [code for code in planner.git_backup_plan(self.root)["blockers"] if code in ATTRIBUTE_CODES]

    def test_attribute_file_inside_ignored_scratch_folder_is_inert(self):
        (self.root / ".gitignore").write_text("scratch/\n", encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-m", "ignore scratch")
        scratch = self.root / "scratch" / "restore-test-copy"
        scratch.mkdir(parents=True)
        (scratch / ".gitattributes").write_text("* filter=malicious\n", encoding="utf-8")
        (scratch / "copy.txt").write_text("restored copy\n", encoding="utf-8")
        (self.root / "tracked.txt").write_text("after\n", encoding="utf-8")
        self.assertEqual(self.attribute_blockers(), [])
        self.assertFalse(self.sentinel.exists())

    def test_ignored_attribute_file_next_to_a_tracked_file_still_blocks(self):
        (self.root / ".gitignore").write_text("sub/.gitattributes\n", encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-m", "ignore only the attribute file")
        (self.root / "sub" / ".gitattributes").write_text("*.txt filter=malicious\n", encoding="utf-8")
        (self.root / "sub" / "kept.txt").write_text("changed\n", encoding="utf-8")
        self.assertEqual(self.attribute_blockers(), ["repository_attributes_not_supported"])
        self.assertFalse(self.sentinel.exists())

    def test_root_level_ignored_attribute_file_still_blocks(self):
        (self.root / ".gitignore").write_text(".gitattributes\n", encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-m", "ignore root attributes")
        (self.root / ".gitattributes").write_text("*.txt filter=malicious\n", encoding="utf-8")
        self.assertEqual(self.attribute_blockers(), ["repository_attributes_not_supported"])
        self.assertFalse(self.sentinel.exists())


class SessionRouteCauseTests(unittest.TestCase):
    def test_plan_blocker_code_survives_both_layers_with_a_next_action(self):
        def blocked():
            raise provenance.WorkSessionGitProvenanceError(
                "work_session_git_snapshot_unavailable", cause_code="repository_attributes_not_supported")
        with self.assertRaises(workflow.WorkSessionGitWorkflowError) as raised:
            workflow._safe_call(lambda: provenance._safe_failure(blocked))
        self.assertEqual(raised.exception.code, "work_session_git_unavailable")
        self.assertEqual(raised.exception.cause_code, "repository_attributes_not_supported")
        result = command._failure(raised.exception.code, mode="preview", effects_started=True,
                                  cause_code=raised.exception.cause_code)
        # The existing conservative contract stays: after entering the session
        # lock the effect state is not claimed, but the cause is now named.
        self.assertEqual(result["effects_state"], "unknown")
        self.assertEqual(result["cause_code"], "repository_attributes_not_supported")
        self.assertIn("do not delete or disable attribute files", result["next_safe_actions"][0])
        applied = command._failure("work_session_git_unavailable", mode="apply", effects_started=True)
        self.assertEqual(applied["effects_state"], "unknown")
        self.assertNotIn("cause_code", applied)

    def test_free_text_never_becomes_a_cause(self):
        error = provenance.WorkSessionGitProvenanceError("work_session_git_snapshot_unavailable",
                                                         cause_code="C:\\private\\path failed")
        self.assertIsNone(error.cause_code)


if __name__ == "__main__":
    unittest.main()
