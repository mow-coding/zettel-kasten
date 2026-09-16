"""Whole document observations never invent ownership from a field hash."""

import copy
from pathlib import Path
import shutil
import tempfile
import unittest

import test_local_recovery_execution as fixture
from wom_kit import exact_operation_manifest as exact
from wom_kit import local_recovery_execution as recovery
from wom_kit import local_recovery_document_images as subject


class DocumentImageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        shutil.copytree(fixture.FIXTURE, self.root)
        self.plan = fixture.LocalRecoveryExecutionTests().title_plan(self.root)
        self.path = self.root / self.plan.specs[0].target_relative

    def test_capture_is_readonly_and_matches_the_real_replacement_bytes(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}
            rows = subject._capture_held(self.plan, held)
            self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob("*")
                                      if path.is_file() and path.name != ".writer.lock"})
            raw = self.path.read_bytes()
            candidate = recovery.archive_services.zet_title_remap_candidate_bytes(raw, "Recovered exact title")
            self.assertEqual(rows[0]["pre_sha256"], recovery._sha(raw))
            self.assertEqual(rows[0]["post_sha256"], recovery._sha(candidate))
            subject._assert_replacement(rows[0], before=raw, after=candidate)
            self.assertTrue(subject._matches_state_held(self.plan, rows, state="pre", held=held))
            self.assertFalse(subject._matches_state_held(self.plan, rows, state="post", held=held))
            self.path.write_bytes(candidate)  # Synthetic observation; no approval claim is inferred.
            self.assertTrue(subject._matches_state_held(self.plan, rows, state="post", held=held))

    def test_unrelated_body_edit_keeps_field_state_but_invalidates_whole_image(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            rows = subject._capture_held(self.plan, held)
            self.path.write_bytes(self.path.read_bytes() + b"\nSynthetic later body edit.\n")
            self.assertTrue(recovery.verify_local_recovery_state(self.plan, state="pre")["all_match"])
            self.assertFalse(subject._matches_state_held(self.plan, rows, state="pre", held=held))
            changed = subject._capture_held(self.plan, held)
            self.assertNotEqual(rows[0]["pre_sha256"], changed[0]["pre_sha256"])
            self.assertNotEqual(rows[0]["post_sha256"], changed[0]["post_sha256"])
            raw = self.path.read_bytes()
            replacement = recovery._zettel_replacement(raw, self.plan.specs[0], self.plan.specs[0].post_value)
            with self.assertRaises(recovery.LocalRecoveryError):
                subject._assert_replacement(rows[0], before=raw, after=replacement)

    def test_incomplete_substituted_paths_and_invalid_images_are_rejected(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            rows = subject._capture_held(self.plan, held)
            invalid = [[], rows + rows]
            for name, value in (("relative_path", "unrelated.md"), ("item_id", "item:000009"),
                                ("target_ref", "sha256:" + "0" * 64), ("pre_bytes", True),
                                ("post_bytes", 0), ("pre_sha256", "invalid")):
                changed = copy.deepcopy(rows)
                changed[0][name] = value
                invalid.append(changed)
            for changed in invalid:
                with self.assertRaises(recovery.LocalRecoveryError):
                    subject._validate(self.plan, changed)

    def test_foreign_or_released_lock_is_not_document_observation_authority(self):
        elsewhere = self.root.parent / "other"
        shutil.copytree(fixture.FIXTURE, elsewhere)
        with exact.ExactOperationWriterLock(elsewhere) as wrong:
            with self.assertRaises(recovery.LocalRecoveryError):
                subject._capture_held(self.plan, wrong)
        with exact.ExactOperationWriterLock(self.root) as held:
            pass
        with self.assertRaises(recovery.LocalRecoveryError):
            subject._capture_held(self.plan, held)


if __name__ == "__main__":
    unittest.main()
