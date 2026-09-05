"""Caller task intent is checked even when another task's claim is valid."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_actor_execution as subject
from wom_kit import work_session_registry as registry
import test_v0420_work_session_actor as fixture


class TaskSelectionExecutionTests(unittest.TestCase):
    setUp = fixture.WorkSessionActorTests.setUp
    transition = fixture.WorkSessionActorTests.transition
    fields = fixture.WorkSessionActorTests.fields
    save = fixture.WorkSessionActorTests.save

    def require(self, held, **changes):
        request = {"client_app_ref": self.app, "task_route_ref": self.route,
                   "work_session_ref": self.session}
        request.update(changes)
        return subject._require_actor_selection_for_write_held(self.root, held=held, **request)

    def rejected(self, held, code, **changes):
        with self.assertRaises(subject.WorkSessionTaskSelectionError) as caught:
            self.require(held, **changes)
        self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        for marker in (self.app, self.session, self.route, self.claim, str(self.root)):
            self.assertNotIn(marker, repr(caught.exception))

    def test_real_claimed_selection_is_read_only_and_returns_only_binding(self):
        original = self.save()
        generation = self.registry.read().sha256
        with exact.ExactOperationWriterLock(self.root) as held:
            binding = self.require(held)
            self.assertEqual(binding, self.binding)
            held.verify_held()
        self.assertEqual(self.actor.read()._raw, original._raw)
        self.assertEqual(self.registry.read().sha256, generation)
        self.assertNotIn(self.claim, json.dumps(binding.document()))

    def test_registry_pending_blocks_but_completed_selector_does_not_grant_or_block_ownership(self):
        original = self.save()
        intent_sha = "sha256:" + "a" * 64
        with exact.ExactOperationWriterLock(self.root) as held:
            pending = self.actor.save(expected_sha256=original.sha256, held_lock=held,
                **self.fields(), pending_registry_intent_plan_sha256=intent_sha)
            with patch.object(registry.WorkSessionRegistryStore, "require_claimed_binding",
                              side_effect=AssertionError("pending must fail before claim admission")):
                self.rejected(held, "work_session_original_operation_pending")
            self.actor.save(expected_sha256=pending.sha256, held_lock=held,
                **self.fields(), pending_registry_intent_plan_sha256=None,
                last_completed_operation=actor.CompletedOperationSelector.from_document({
                    "kind": "registry_transition", "plan_sha256": intent_sha,
                }))
            # No completion claim follows from this synthetic pointer. The
            # existing actual ownership guard still independently decides.
            self.assertEqual(self.require(held), self.binding)
            with patch.object(registry.WorkSessionRegistryStore, "require_claimed_binding",
                              side_effect=registry.WorkSessionRegistryError("work_session_claim_conflict")):
                self.rejected(held, "work_session_task_ownership_unavailable")

    def test_two_valid_claims_do_not_allow_substituting_another_task_route(self):
        self.save()
        second = self.transition(action="create", client_app_ref=self.app,
                                 label="Synthetic other task").result_refs[-1]
        self.transition(action="claim", client_app_ref=self.app, work_session_ref=second)
        snapshot = self.registry.read()
        second_route = actor.new_task_route_ref()
        second_store = actor.WorkSessionActorStore(self.registry, client_app_ref=self.app,
                                                   task_route_ref=second_route)
        with exact.ExactOperationWriterLock(self.root) as held:
            second_store.save(expected_sha256=None, held_lock=held,
                work_session_ref=second, observed_binding=snapshot.binding(second),
                claim_ref=snapshot._document["sessions"][second]["claim_ref"])
            self.assertEqual(self.require(held), self.binding)
            self.assertEqual(self.require(held, task_route_ref=second_route,
                                          work_session_ref=second), snapshot.binding(second))
            with patch.object(registry.WorkSessionRegistryStore, "require_claimed_binding",
                              side_effect=AssertionError("wrong caller task must fail first")):
                self.rejected(held, "work_session_task_context_mismatch", task_route_ref=second_route)
                self.rejected(held, "work_session_task_context_mismatch", work_session_ref=second)

    def test_missing_and_malformed_context_never_chooses_latest(self):
        self.save()
        with exact.ExactOperationWriterLock(self.root) as held:
            for name in ("client_app_ref", "task_route_ref", "work_session_ref"):
                with self.subTest(field=name):
                    self.rejected(held, "work_session_task_context_required", **{name: None})
                    self.rejected(held, "work_session_task_context_mismatch", **{name: "PRIVATE-MARKER"})
            self.rejected(held, "work_session_task_context_required", task_route_ref=actor.new_task_route_ref())

    def test_missing_actor_context_is_not_created(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            self.rejected(held, "work_session_task_context_required")
        self.assertFalse(self.directory.exists())

    def test_pending_original_operation_cannot_authorize_a_fresh_write(self):
        original = self.save(pending_manifest_sha256="sha256:" + "a" * 64,
                             pending_context_sha256="sha256:" + "b" * 64)
        with exact.ExactOperationWriterLock(self.root) as held, patch.object(
            registry.WorkSessionRegistryStore, "require_claimed_binding",
            side_effect=AssertionError("pending operation must resume first"),
        ):
            self.rejected(held, "work_session_original_operation_pending")
        self.assertEqual(self.actor.read()._raw, original._raw)

    def test_stale_or_unclaimed_selection_is_not_recovered_by_this_guard(self):
        self.save()
        self.transition(action="pause", client_app_ref=self.app,
                        work_session_ref=self.session, claim_ref=self.claim)
        with exact.ExactOperationWriterLock(self.root) as held:
            self.rejected(held, "work_session_task_ownership_unavailable")

    def test_route_change_after_claim_check_still_refuses_dispatch(self):
        original = self.save()
        guard = registry.WorkSessionRegistryStore.require_claimed_binding
        with exact.ExactOperationWriterLock(self.root) as held:
            def change_after_guard(store, **kwargs):
                result = guard(store, **kwargs)
                self.actor.save(expected_sha256=original.sha256, held_lock=held)
                return result
            with patch.object(registry.WorkSessionRegistryStore, "require_claimed_binding", change_after_guard):
                self.rejected(held, "work_session_task_context_changed")

    def test_foreign_or_released_lock_is_not_ownership_authority(self):
        self.save()
        with tempfile.TemporaryDirectory(prefix="wom-task-foreign-") as temporary:
            with exact.ExactOperationWriterLock(Path(temporary)) as foreign:
                self.rejected(foreign, "work_session_lock_required")
        with exact.ExactOperationWriterLock(self.root) as held:
            held.verify_held()
        self.rejected(held, "work_session_lock_required")


if __name__ == "__main__":
    unittest.main()
