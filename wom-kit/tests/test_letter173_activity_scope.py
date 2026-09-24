"""Letter 173 D (owner decision 2026-09-24): close an activity by its own scope.

`activity-cleanup` accepts the archive's AI scratch roots (a file a zet still
references is blocked), and `session-handoff-checkpoint --activity-root` reads
every page of exactly that activity and counts objet-preserved copies as
preserved. Synthetic archive only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wom_kit import activity_cleanup as cleanup
from wom_kit import archive_services

import test_activity_cleanup as base


class InArchiveScratchCleanupTests(unittest.TestCase):
    setUp = base.ActivityCleanupTests.setUp
    plan = base.ActivityCleanupTests.plan
    execute = base.ActivityCleanupTests.execute

    def use_scratch(self, name="note.md"):
        scratch = self.root / ".wom-scratch" / "activity-173"
        scratch.mkdir(parents=True, exist_ok=True)
        path = scratch / name
        path.write_bytes(b"temporary AI working note\n")
        self.document.update({
            "roots": [str(scratch)],
            "items": [{"path": str(path), "role": "temporary", "reason": "AI working note for this activity",
                       "disposition": "discard", "discard_intent": True}],
            "remove_empty_directories": [],
        })
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        return path

    def test_in_archive_ai_scratch_is_activity_material(self):
        path = self.use_scratch()
        candidate = self.plan()
        self.assertTrue(candidate["public"]["ok"], candidate["public"]["blockers"])
        if os.name == "nt":
            result = self.execute(candidate)
            self.assertTrue(result["ok"], result)
            self.assertFalse(path.exists())
            self.backend.preserve.assert_not_called()

    def test_scratch_a_zet_still_references_is_blocked(self):
        path = self.use_scratch()
        draft = self.root / "inbox" / "zet_20260519_draft_ai_lunch_note.md"
        draft.write_text(draft.read_text(encoding="utf-8")
                         + "\nSee .wom-scratch/activity-173/note.md\n", encoding="utf-8")
        blockers = self.plan()["public"]["blockers"]
        self.assertIn("activity_cleanup_scratch_still_referenced_by_zet", blockers)
        self.assertTrue(path.exists())

    def test_other_archive_state_is_still_refused(self):
        self.document["roots"] = [str(self.root / "zettels")]
        self.document["items"] = [{"path": str(next((self.root / "zettels").glob("*.md"))), "role": "temporary",
                                   "reason": "should never be accepted", "disposition": "discard",
                                   "discard_intent": True}]
        self.document["remove_empty_directories"] = []
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        with self.assertRaises(cleanup.ActivityCleanupError) as caught:
            self.plan()
        self.assertEqual(caught.exception.code, "activity_cleanup_archive_state_not_external_source")


class ActivityScopedHandoffTests(unittest.TestCase):
    setUp = base.ActivityCleanupTests.setUp

    def test_every_page_is_read_and_objet_copies_count_as_preserved(self):
        scratch = self.root / ".wom-scratch" / "activity-173"
        scratch.mkdir(parents=True)
        for index in range(1004):
            (scratch / f"note-{index:04d}.md").write_text(f"working note {index}\n", encoding="utf-8")
        preserved_bytes = (self.root / "objects" / "sample" / "fake-school-record.txt").read_bytes()
        (scratch / "copy-of-objet.txt").write_bytes(preserved_bytes)

        scoped = archive_services.session_handoff_checkpoint(
            self.root, dry_run=True, activity_roots=[".wom-scratch/activity-173/"],
        )
        scope = scoped["activity_scope"]
        self.assertTrue(scope["complete"], scope)
        self.assertEqual(scope["total_candidate_count"], 1005)
        self.assertEqual(scope["fate_counts"].get("preserved_as_objet"), 1)
        self.assertEqual(scope["fate_counts"].get("unreviewed_ai_artifact"), 1004)
        gaps = " ".join(scoped["next_safe_actions"]) + json.dumps(scoped)
        self.assertNotIn("inventory is truncated", gaps)
        self.assertNotIn(str(self.root), json.dumps(scoped))

        legacy = archive_services.session_handoff_checkpoint(self.root, dry_run=True)
        self.assertIsNone(legacy["activity_scope"])
        self.assertTrue(any("--activity-root" in action for action in legacy["next_safe_actions"]))
        self.assertNotEqual(legacy["state_digest"], scoped["state_digest"])


if __name__ == "__main__":
    unittest.main()
