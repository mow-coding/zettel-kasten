"""Typed Git routing selectors never become human approval or current authority."""

from contextlib import ExitStack
from dataclasses import FrozenInstanceError
import json
import unittest
from unittest import mock

import test_v0420_work_session_actor as fixture
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_actor_execution as actor_guard
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit import work_session_service as service


MANIFEST = "sha256:" + "a" * 64
CONTEXT = "sha256:" + "b" * 64
PLAN = "sha256:" + "c" * 64
UNSUPPORTED = "work_session_original_operation_kind_unsupported"


def selector(kind="git_backup"):
    return actor.PendingOperationSelector.from_document({
        "kind": kind, "manifest_sha256": MANIFEST, "context_sha256": CONTEXT,
    })


class ActorGitPendingTests(unittest.TestCase):
    setUp = fixture.WorkSessionActorTests.setUp
    transition = fixture.WorkSessionActorTests.transition
    fields = fixture.WorkSessionActorTests.fields
    save = fixture.WorkSessionActorTests.save
    files = fixture.WorkSessionActorTests.files
    rejected = fixture.WorkSessionActorTests.rejected

    def test_legacy_pair_bytes_digest_summary_and_noop_remain_exact(self):
        saved = self.save(pending_manifest_sha256=MANIFEST, pending_context_sha256=CONTEXT)
        raw, digest, summary = saved._raw, saved.sha256, saved.public_summary()
        self.assertEqual(set(saved.document()), actor._KEYS)
        self.assertNotIn("pending_operation_kind", saved.document())
        self.assertNotIn("pending_original_operation_kind", summary)
        self.assertEqual(saved.pending_operation().document(), selector("human_session_decision").document())
        self.assertEqual(actor.ActorContext(raw)._raw, raw)
        self.assertEqual(actor.ActorContext(raw).sha256, digest)
        self.assertEqual(actor.ActorContext(raw).public_summary(), summary)
        before = self.files()
        self.assertEqual(self.save(digest, pending_manifest_sha256=MANIFEST,
                                  pending_context_sha256=CONTEXT)._raw, raw)
        self.assertEqual(self.files(), before)

    def test_typed_git_pending_roundtrip_and_terminal_clear_keep_original_generations(self):
        old = self.save()
        pending = self.save(old.sha256, pending_operation=selector())
        value = pending.document()
        self.assertEqual(value["pending_operation_kind"], "git_backup")
        self.assertEqual(value["pending_manifest_sha256"], MANIFEST)
        self.assertEqual(value["pending_context_sha256"], CONTEXT)
        self.assertEqual(self.actor.read().pending_operation().document(), selector().document())
        self.assertEqual(self.save(pending.sha256, pending_operation=selector())._raw, pending._raw)
        completed = actor.CompletedOperationSelector.from_document(selector().document())
        registry_before = self.registry.read().sha256
        terminal = self.save(pending.sha256, pending_operation=None, last_completed_operation=completed)
        self.assertIsNone(terminal.pending_operation())
        self.assertIsNone(terminal.document()["pending_manifest_sha256"])
        self.assertIsNone(terminal.document()["pending_context_sha256"])
        self.assertNotIn("pending_operation_kind", terminal.document())
        self.assertEqual(terminal.document()["last_completed_operation"], completed.document())
        self.assertEqual(self.registry.read().sha256, registry_before)
        self.assertEqual((self.directory / "000000000001.json").read_bytes(), old._raw)
        self.assertEqual((self.directory / "000000000002.json").read_bytes(), pending._raw)
        self.assertEqual(self.save(terminal.sha256)._raw, terminal._raw)

    def test_exact_typed_selector_required_and_git_cannot_silently_become_legacy_human(self):
        for value in (True, "git_backup", selector().document(), []):
            with self.subTest(input_type=type(value).__name__):
                self.rejected(lambda: self.save(pending_operation=value))
        self.rejected(lambda: self.save(pending_operation=selector(), pending_manifest_sha256=MANIFEST,
                                       pending_context_sha256=CONTEXT))
        self.rejected(lambda: self.save(pending_operation=selector(), pending_registry_intent_plan_sha256=PLAN))
        pending = self.save(pending_operation=selector())
        self.rejected(lambda: self.save(pending.sha256, pending_manifest_sha256=MANIFEST,
                                       pending_context_sha256=CONTEXT), "work_session_actor_changed")
        self.rejected(lambda: self.save(None, pending_operation=selector()), "work_session_actor_changed")
        with exact.ExactOperationWriterLock(self.root) as held:
            held.verify_held()
            changed = self.actor.save(expected_sha256=pending.sha256, held_lock=held,
                                      pending_operation=selector("human_session_decision"), **self.fields())
            held.verify_held()
        self.assertEqual(changed.pending_operation().document()["kind"], "human_session_decision")

    def test_selector_grammar_and_actor_kind_are_strict_and_private(self):
        valid = selector().document()
        invalid = (None, True, [], {}, {**valid, "kind": []}, {**valid, "kind": "private-kind"},
                   {**valid, "manifest_sha256": True}, {**valid, "context_sha256": "private"},
                   {**valid, "approve": True}, {"kind": "git_backup", "manifest_sha256": MANIFEST})
        for value in invalid:
            with self.subTest(input_type=type(value).__name__):
                self.rejected(lambda: actor.PendingOperationSelector.from_document(value))
                self.rejected(lambda: actor.CompletedOperationSelector.from_document(value))
        duplicate = ('{"kind":"git_backup","kind":"human_session_decision",'
                     '"manifest_sha256":"' + MANIFEST + '","context_sha256":"' + CONTEXT + '"}').encode()
        for raw in (duplicate, b'{"kind":NaN}', b"x" * (actor.MAX_ACTOR_BYTES + 1)):
            self.rejected(lambda: actor.PendingOperationSelector(raw))
        old = self.save()
        for fields in ({"pending_operation_kind": "git_backup"},
                       {"pending_operation_kind": None},
                       {"pending_operation_kind": "private-kind", "pending_manifest_sha256": MANIFEST,
                        "pending_context_sha256": CONTEXT},
                       {"pending_operation_kind": True, "pending_manifest_sha256": MANIFEST,
                        "pending_context_sha256": CONTEXT}):
            value = {**old.document(), **fields}
            basis = {key: item for key, item in value.items() if key != "actor_sha256"}
            raw = registry._canonical({**basis, "actor_sha256": actor._sha(registry._canonical(basis))})
            self.rejected(lambda: actor.ActorContext(raw))
        selected = selector()
        with self.assertRaises(FrozenInstanceError):
            selected._raw = b"private"
        detached = selected.document()
        detached["kind"] = "human_session_decision"
        self.assertEqual(selected.document()["kind"], "git_backup")
        saved = self.save(old.sha256, pending_operation=selected)
        summary = saved.public_summary()
        self.assertEqual(summary["pending_original_operation_kind"], "git_backup")
        self.assertFalse(summary["pending_selector_is_authority"])
        self.assertFalse(summary["routing_is_write_authority"])
        output = json.dumps(summary) + repr(selected) + repr(saved)
        for marker in (MANIFEST, CONTEXT, self.app, self.route, self.session, self.claim, str(self.root)):
            self.assertNotIn(marker, output)

    def test_git_pending_remains_a_blocker_for_generic_fresh_writer(self):
        pending = self.save(pending_operation=selector())
        before = self.files()
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(actor_guard.WorkSessionTaskSelectionError) as caught:
                actor_guard._require_actor_selection_for_write_held(
                    self.root, held=held, client_app_ref=self.app, task_route_ref=self.route,
                    work_session_ref=self.session)
            held.verify_held()
        self.assertEqual(caught.exception.code, "work_session_original_operation_pending")
        self.assertEqual(self.actor.read()._raw, pending._raw)
        self.assertEqual(self.files(), before)

    def public_original_calls(self):
        route = dict(client_app_ref=self.app, task_route_ref=self.route)
        session = {**route, "work_session_ref": self.session}
        handoff = {**session, "target_app_ref": self.other_app}
        return (
            lambda: service.resume_task_create(self.root, **route),
            lambda: service.resume_task_accept(self.root, **route),
            lambda: service.review_original_task_create(self.root, **route),
            lambda: service.review_original_task_accept(self.root, **route),
            lambda: service.recover_task(self.root, original_resume=True, **session),
            lambda: service.review_original_task_recovery(self.root, **session),
            lambda: service.handoff_task(self.root, original_resume=True, **handoff),
            lambda: service.review_original_task_handoff(self.root, **handoff),
        )

    def assert_public_refused_without_original_proof_or_write(self, calls):
        before = self.files()
        with ExitStack() as stack:
            guards = [stack.enter_context(mock.patch.object(module, name,
                         side_effect=AssertionError("private original authority boundary entered")))
                      for module, name in (
                          (bundle, "load_context_bound_session_decision"),
                          (workflow, "_production_key_provider"), (windows, "_CtypesTaskDialogNative"),
                          (operation, "apply_session_decision_with_claim"),
                          (actor.WorkSessionActorStore, "save"), (registry.WorkSessionRegistryStore, "commit"))]
            for number, call in enumerate(calls):
                with self.subTest(call=number), self.assertRaises(service.WorkSessionServiceError) as caught:
                    call()
                self.assertEqual(caught.exception.code, UNSUPPORTED)
                self.assertIsNone(caught.exception.__context__)
                self.assertIsNone(caught.exception.__cause__)
            for guard in guards:
                guard.assert_not_called()
        self.assertEqual(self.files(), before)

    def test_public_human_original_flows_refuse_explicit_git_pending_before_proof_or_authority(self):
        self.save(pending_operation=selector())
        self.assert_public_refused_without_original_proof_or_write(self.public_original_calls())

    def test_public_human_original_flows_refuse_git_completed_without_human_fallback(self):
        self.save(last_completed_operation=actor.CompletedOperationSelector.from_document(selector().document()))
        self.assert_public_refused_without_original_proof_or_write(self.public_original_calls())


if __name__ == "__main__":
    unittest.main()
