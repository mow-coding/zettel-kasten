"""A valid draft preview must not claim a stale-index write is ready."""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock


TESTS = Path(__file__).resolve().parent
for location in (TESTS.parent / "src", TESTS):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from wom_kit import archive_services
import test_v03313_source_fidelity as fidelity_fixtures


class DraftWritePreflightTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fidelity_fixtures.SourceFidelityV03313Tests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.root = self.fixture.root
        object_id = self.fixture.manifested_source(b"Original synthetic source.\n")
        self.arguments = self.fixture.ai_kwargs(object_id)

    def preview(self):
        return archive_services.create_draft_zettel(
            self.root, dry_run=True, **self.arguments,
        )

    def test_current_index_preview_is_ready_without_writes(self):
        before = self.fixture.archive_file_snapshot()
        result = self.preview()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["write_preflight"]["state"], "passed")
        self.assertTrue(result["approval_handoff"]["ready"])
        self.assertEqual(result["next_safe_actions"], [])
        self.assertEqual(self.fixture.archive_file_snapshot(), before)

    def test_missing_index_preserves_valid_input_but_blocks_approval_handoff(self):
        database = self.root / archive_services.INDEX_RELATIVE_PATH
        database.rename(database.with_suffix(".held-fixture"))
        before = self.fixture.archive_file_snapshot()
        result = self.preview()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["write_preflight"], {
            "state": "failed", "reason_code": archive_services.INDEX_REBUILD_REQUIRED,
        })
        self.assertFalse(result["approval_handoff"]["ready"])
        self.assertEqual(result["approval_handoff"]["stage"], "blocked")
        self.assertEqual(result["next_safe_actions"], list(archive_services.INDEX_REBUILD_NEXT_SAFE_ACTIONS))
        self.assertEqual(self.fixture.archive_file_snapshot(), before)

    def test_unavailable_observation_is_not_a_confirmed_stale_index(self):
        before = self.fixture.archive_file_snapshot()
        sentinel = "PRIVATE_READ_FAILURE_DO_NOT_ECHO"
        with mock.patch.object(archive_services, "require_current_zettel_index", side_effect=OSError(sentinel)):
            result = self.preview()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["write_preflight"]["state"], "unavailable")
        self.assertFalse(result["approval_handoff"]["ready"])
        self.assertNotIn(archive_services.INDEX_REBUILD_NEXT_SAFE_ACTIONS[0], result["next_safe_actions"])
        self.assertNotIn(sentinel, json.dumps(result))
        self.assertEqual(self.fixture.archive_file_snapshot(), before)

    def test_approval_replay_uses_the_same_unavailable_reason_without_rebuild_advice(self):
        before = self.fixture.archive_file_snapshot()
        with mock.patch.object(
            archive_services, "require_current_zettel_index",
            side_effect=OSError("private_observation_marker"),
        ):
            result = archive_services.create_draft_zettel(
                self.root, dry_run=True, **(self.arguments | {"approved": True}),
            )
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["write_preflight"], {
            "state": "unavailable", "reason_code": "archive_index_observation_unavailable",
        })
        self.assertEqual(result["blockers"], ["archive_index_observation_unavailable"])
        self.assertFalse(result["approval_handoff"]["ready"])
        self.assertNotIn(archive_services.INDEX_REBUILD_NEXT_SAFE_ACTIONS[0], result["next_safe_actions"])
        self.assertNotIn("private_observation_marker", json.dumps(result))
        self.assertEqual(self.fixture.archive_file_snapshot(), before)


if __name__ == "__main__":
    unittest.main()
