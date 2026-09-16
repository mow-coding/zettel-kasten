"""A retained intake selector routes only; it cannot authorize a human action.

Synthetic registry setup is private fixture preparation, not a public journey.
Actual public resume/re-review entry points must refuse before proof/key/write.
"""

import json
import unittest

import test_v0420_work_session_actor_git_pending as fixture
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_actor_execution as guard


def selector():
    return fixture.selector("source_intake_batch")


class ActorIntakePendingTests(unittest.TestCase):
    setUp = fixture.ActorGitPendingTests.setUp
    transition = fixture.ActorGitPendingTests.transition
    fields = fixture.ActorGitPendingTests.fields
    save = fixture.ActorGitPendingTests.save
    files = fixture.ActorGitPendingTests.files
    rejected = fixture.ActorGitPendingTests.rejected
    public_original_calls = fixture.ActorGitPendingTests.public_original_calls
    assert_public_refused_without_original_proof_or_write = (
        fixture.ActorGitPendingTests.assert_public_refused_without_original_proof_or_write)

    def test_typed_intake_roundtrip_clear_and_cas_preserve_original_bytes(self):
        old = self.save()
        pending = self.save(old.sha256, pending_operation=selector())
        self.assertEqual(self.actor.read().pending_operation().document(), selector().document())
        self.assertEqual(self.save(pending.sha256, pending_operation=selector())._raw, pending._raw)
        self.rejected(lambda: self.save(old.sha256, pending_operation=selector()),
                      "work_session_actor_changed")
        self.rejected(lambda: self.save(pending.sha256,
            pending_manifest_sha256=fixture.MANIFEST, pending_context_sha256=fixture.CONTEXT),
            "work_session_actor_changed")
        completed = actor.CompletedOperationSelector.from_document(selector().document())
        registry_before = self.registry.read().sha256
        terminal = self.save(pending.sha256, pending_operation=None,
                             last_completed_operation=completed)
        self.assertIsNone(terminal.pending_operation())
        self.assertNotIn("pending_operation_kind", terminal.document())
        self.assertEqual(terminal.document()["last_completed_operation"], completed.document())
        self.assertEqual(self.registry.read().sha256, registry_before)
        self.assertEqual((self.directory / "000000000001.json").read_bytes(), old._raw)
        self.assertEqual((self.directory / "000000000002.json").read_bytes(), pending._raw)

    def test_intake_pending_blocks_fresh_write_and_exposes_no_private_authority(self):
        pending = self.save(pending_operation=selector())
        before = self.files()
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(guard.WorkSessionTaskSelectionError) as caught:
                guard._require_actor_selection_for_write_held(self.root, held=held,
                    client_app_ref=self.app, task_route_ref=self.route,
                    work_session_ref=self.session)
            held.verify_held()
        self.assertEqual(caught.exception.code, "work_session_original_operation_pending")
        self.assertEqual(self.files(), before)
        summary = pending.public_summary()
        self.assertEqual(summary["pending_original_operation_kind"], "source_intake_batch")
        self.assertFalse(summary["pending_selector_is_authority"])
        self.assertFalse(summary["routing_is_write_authority"])
        for marker in (self.app, self.route, self.session, self.claim, str(self.root),
                       fixture.MANIFEST, fixture.CONTEXT):
            self.assertNotIn(marker, json.dumps(summary) + repr(pending) + repr(selector()))

    def test_all_human_original_routes_refuse_intake_pending_before_authority(self):
        self.save(pending_operation=selector())
        self.assert_public_refused_without_original_proof_or_write(self.public_original_calls())

    def test_all_human_original_routes_refuse_intake_completed_before_authority(self):
        self.save(last_completed_operation=actor.CompletedOperationSelector.from_document(selector().document()))
        self.assert_public_refused_without_original_proof_or_write(self.public_original_calls())


if __name__ == "__main__":
    unittest.main()
