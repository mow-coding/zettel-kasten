"""Routing-only terminal discovery; original approvals remain independently verified."""

from dataclasses import FrozenInstanceError
import json
import subprocess
import sys
import unittest
from unittest import mock

import test_v0420_work_session_actor as fixture
from wom_kit import exact_operation_manifest as exact
from wom_kit import process_launch
from wom_kit import work_session_actor as actor
from wom_kit import work_session_registry as registry


MANIFEST = "sha256:" + "a" * 64
CONTEXT = "sha256:" + "b" * 64
PLAN = "sha256:" + "c" * 64
NEXT_PLAN = "sha256:" + "d" * 64


class ActorContinuationTests(unittest.TestCase):
    # Compose the established real-registry fixture without inheriting and
    # rerunning its independent test methods.
    setUp = fixture.WorkSessionActorTests.setUp
    transition = fixture.WorkSessionActorTests.transition
    fields = fixture.WorkSessionActorTests.fields
    save = fixture.WorkSessionActorTests.save
    files = fixture.WorkSessionActorTests.files
    rejected = fixture.WorkSessionActorTests.rejected
    child_read = fixture.WorkSessionActorTests.child_read

    def human(self):
        return actor.CompletedOperationSelector.from_document({
            "kind": "human_session_decision", "manifest_sha256": MANIFEST,
            "context_sha256": CONTEXT,
        })

    def registry_completed(self, plan=PLAN):
        return actor.CompletedOperationSelector.from_document({
            "kind": "registry_transition", "plan_sha256": plan,
        })

    def test_old_raw_digest_summary_and_noop_are_unchanged(self):
        saved = self.save()
        self.assertEqual(set(saved.document()), actor._KEYS)
        self.assertEqual(actor.ActorContext(saved._raw)._raw, saved._raw)
        self.assertEqual(actor.ActorContext(saved._raw).sha256, saved.sha256)
        expected_summary = {
            "schema": actor.ACTOR_SCHEMA, "revision": 1,
            "scope": "private_actor_routing", "routing_identity_level": "self_declared",
            "identity_is_app_attestation": False, "session_selected": True,
            "claim_assertion_present": True, "pending_original_operation_selected": False,
            "routing_is_write_authority": False, "claim_tokens_echoed": False,
            "private_labels_echoed": False,
        }
        self.assertEqual(saved.public_summary(), expected_summary)
        before = self.files()
        self.assertEqual(self.save(saved.sha256)._raw, saved._raw)
        self.assertEqual(self.actor.read()._raw, saved._raw)
        self.assertEqual(self.files(), before)

    def test_explicit_null_extensions_append_once_without_rewriting_old_bytes(self):
        old = self.save()
        extended = self.save(old.sha256, pending_registry_intent_plan_sha256=None,
                             last_completed_operation=None)
        self.assertEqual(extended.document()["revision"], 2)
        self.assertIsNone(extended.document()["last_completed_operation"])
        self.assertIsNone(extended.document()["pending_registry_intent_plan_sha256"])
        self.assertEqual((self.directory / "000000000001.json").read_bytes(), old._raw)
        before = self.files()
        self.assertEqual(self.save(extended.sha256)._raw, extended._raw)
        self.assertEqual(self.files(), before)

    def test_old_raw_first_registry_pending_addition_is_not_a_noop_key_error(self):
        old = self.save()
        pending = self.save(old.sha256, pending_registry_intent_plan_sha256=PLAN)
        self.assertEqual(pending.document()["revision"], 2)
        self.assertEqual(pending.document()["pending_registry_intent_plan_sha256"], PLAN)
        self.assertEqual(pending.document()["previous_sha256"], old.sha256)
        self.assertEqual((self.directory / "000000000001.json").read_bytes(), old._raw)
        self.assertEqual(self.actor.read()._raw, pending._raw)

    def test_human_pending_to_terminal_is_one_cas_image_without_registry_mutation(self):
        pending = self.save(pending_manifest_sha256=MANIFEST, pending_context_sha256=CONTEXT)
        registry_before = self.registry.read().sha256
        terminal = self.save(pending.sha256, last_completed_operation=self.human())
        value = terminal.document()
        self.assertEqual(value["revision"], 2)
        self.assertEqual(value["previous_sha256"], pending.sha256)
        self.assertIsNone(value["pending_manifest_sha256"])
        self.assertIsNone(value["pending_context_sha256"])
        self.assertEqual(value["last_completed_operation"], self.human().document())
        self.assertEqual(self.registry.read().sha256, registry_before)
        self.assertEqual((self.directory / "000000000001.json").read_bytes(), pending._raw)
        self.assertEqual(len(tuple(self.directory.glob("*.json"))), 2)
        summary = terminal.public_summary()
        self.assertFalse(summary["pending_original_operation_selected"])
        self.assertTrue(summary["last_completed_operation_selected"])
        self.assertEqual(summary["last_completed_operation_kind"], "human_session_decision")
        self.assertFalse(summary["completion_selector_is_authority"])
        self.assertFalse((self.root / "profiles/local/exact-human-approvals").exists())

    def test_registry_pending_to_terminal_uses_original_plan_selector(self):
        pending = self.save(pending_registry_intent_plan_sha256=PLAN)
        self.assertTrue(pending.public_summary()["pending_original_operation_selected"])
        self.assertTrue(pending.public_summary()["pending_registry_operation_selected"])
        terminal = self.save(pending.sha256, pending_registry_intent_plan_sha256=None,
                             last_completed_operation=self.registry_completed())
        self.assertEqual(terminal.document()["revision"], 2)
        self.assertEqual(terminal.document()["previous_sha256"], pending.sha256)
        self.assertIsNone(terminal.document()["pending_registry_intent_plan_sha256"])
        self.assertEqual(terminal.document()["last_completed_operation"], {
            "kind": "registry_transition", "plan_sha256": PLAN})
        self.assertNotIn("intent_sha256", terminal.document()["last_completed_operation"])
        self.assertFalse(terminal.public_summary()["pending_original_operation_selected"])
        self.assertFalse(terminal.public_summary()["completion_selector_is_authority"])

    def test_older_caller_preserves_completed_selector_and_new_pending_can_coexist(self):
        terminal = self.save(last_completed_operation=self.human())
        pending = self.save(terminal.sha256, pending_registry_intent_plan_sha256=PLAN)
        self.assertEqual(pending.document()["last_completed_operation"], self.human().document())
        self.assertEqual(self.save(pending.sha256)._raw, pending._raw)
        # A full old selection update carries both new fields forward.
        updated = self.save(pending.sha256, claim_ref=None)
        self.assertEqual(updated.document()["pending_registry_intent_plan_sha256"], PLAN)
        self.assertEqual(updated.document()["last_completed_operation"], self.human().document())
        self.rejected(lambda: self.save(updated.sha256, last_completed_operation=None),
                      "work_session_actor_changed")
        replaced = self.save(updated.sha256, pending_registry_intent_plan_sha256=None,
                             last_completed_operation=self.registry_completed())
        self.assertEqual(replaced.document()["last_completed_operation"], self.registry_completed().document())
        self.assertEqual((self.directory / "000000000001.json").read_bytes(), terminal._raw)

    def test_pending_kinds_are_mutually_exclusive_and_omission_does_not_clear_registry(self):
        self.rejected(lambda: self.save(pending_manifest_sha256=MANIFEST,
            pending_context_sha256=CONTEXT, pending_registry_intent_plan_sha256=PLAN))
        pending = self.save(pending_registry_intent_plan_sha256=PLAN)
        self.rejected(lambda: self.save(pending.sha256,
            pending_manifest_sha256=MANIFEST, pending_context_sha256=CONTEXT))
        human = self.save(pending.sha256, pending_registry_intent_plan_sha256=None,
                         pending_manifest_sha256=MANIFEST, pending_context_sha256=CONTEXT)
        self.assertIsNone(human.document()["pending_registry_intent_plan_sha256"])
        self.assertEqual(human.document()["pending_manifest_sha256"], MANIFEST)
        self.assertEqual(human.document()["pending_context_sha256"], CONTEXT)

    def test_strict_completed_union_rejects_unknown_fields_types_and_private_text(self):
        invalid = (
            None, True, [], "private-selector", {}, {"kind": []},
            {"kind": "private-unknown-kind", "plan_sha256": PLAN},
            {"kind": "registry_transition", "intent_sha256": PLAN},
            {"kind": "registry_transition", "plan_sha256": True},
            {"kind": "registry_transition", "plan_sha256": "private-digest"},
            {"kind": "registry_transition", "plan_sha256": PLAN, "reviewed_by": "private-person"},
            {"kind": "human_session_decision", "manifest_sha256": MANIFEST},
            {"kind": "human_session_decision", "manifest_sha256": MANIFEST, "context_sha256": None},
            {"kind": "human_session_decision", "manifest_sha256": MANIFEST,
             "context_sha256": CONTEXT, "plan_sha256": PLAN},
        )
        for number, value in enumerate(invalid):
            with self.subTest(case=number):
                self.rejected(lambda: actor.CompletedOperationSelector.from_document(value))
        self.rejected(lambda: self.save(last_completed_operation=self.human().document()))
        for value in (True, {}, "private-digest", "sha256:" + "A" * 64):
            with self.subTest(value_type=type(value).__name__):
                self.rejected(lambda: self.save(pending_registry_intent_plan_sha256=value))

    def test_selector_raw_decoder_rejects_duplicates_unknowns_and_bad_actor_extension(self):
        duplicate = ('{"kind":"registry_transition","kind":"registry_transition",'
                     '"plan_sha256":"' + PLAN + '"}').encode()
        for raw in (duplicate, b'{"kind":"registry_transition","plan_sha256":NaN}',
                    b"x" * (actor.MAX_ACTOR_BYTES + 1)):
            with self.subTest(size=len(raw)):
                self.rejected(lambda: actor.CompletedOperationSelector(raw))
        old = self.save()
        for changes in (
            {"last_completed_operation": {"kind": "registry_transition", "plan_sha256": "private"}},
            {"pending_registry_intent_plan_sha256": PLAN,
             "pending_manifest_sha256": MANIFEST, "pending_context_sha256": CONTEXT},
            {"unknown_private_field": "private"},
        ):
            value = {**old.document(), **changes}
            basis = {key: item for key, item in value.items() if key != "actor_sha256"}
            raw = registry._canonical({**basis, "actor_sha256": actor._sha(registry._canonical(basis))})
            self.rejected(lambda: actor.ActorContext(raw))

    def test_detached_selector_and_context_summary_do_not_echo_private_selectors(self):
        original = self.human()
        with self.assertRaises(FrozenInstanceError):
            original._raw = b"private replacement"
        changed = original.document()
        changed["manifest_sha256"] = NEXT_PLAN
        self.assertEqual(original.document()["manifest_sha256"], MANIFEST)
        terminal = self.save(last_completed_operation=original,
                             pending_registry_intent_plan_sha256=PLAN)
        detached = terminal.document()
        detached["last_completed_operation"]["context_sha256"] = NEXT_PLAN
        self.assertEqual(terminal.document()["last_completed_operation"], original.document())
        output = repr(original) + repr(terminal) + json.dumps(terminal.public_summary())
        for value in (MANIFEST, CONTEXT, PLAN, self.app, self.route, self.claim, self.session,
                      str(self.root), "Synthetic private"):
            self.assertNotIn(value, output)
        self.assertFalse(terminal.public_summary()["routing_is_write_authority"])
        self.assertFalse(terminal.public_summary()["completion_selector_is_authority"])

    def test_registry_pending_preserves_original_assertion_but_never_current_authority(self):
        pending = self.save(pending_registry_intent_plan_sha256=PLAN)
        self.transition(action="recover", client_app_ref=self.app, work_session_ref=self.session)
        self.assertEqual(self.actor.read()._raw, pending._raw)
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(registry.WorkSessionRegistryError):
                self.registry.require_claimed_binding(client_app_ref=self.app,
                    work_session_ref=self.session, claim_ref=self.claim,
                    expected_binding=self.binding, held_lock=held)
        # Terminal selection alone must not exempt an obsolete current assertion.
        self.rejected(lambda: self.save(pending.sha256, pending_registry_intent_plan_sha256=None,
                      last_completed_operation=self.registry_completed()), "work_session_actor_changed")
        current = self.registry.read()
        terminal = self.save(pending.sha256, pending_registry_intent_plan_sha256=None,
            last_completed_operation=self.registry_completed(), observed_binding=current.binding(self.session),
            claim_ref=current._document["sessions"][self.session]["claim_ref"])
        self.assertEqual(terminal.document()["last_completed_operation"], self.registry_completed().document())
        self.assertEqual(self.actor.read()._raw, terminal._raw)

    def test_terminal_save_requires_cas_and_does_not_reuse_old_history(self):
        pending = self.save(pending_registry_intent_plan_sha256=PLAN)
        terminal = self.save(pending.sha256, pending_registry_intent_plan_sha256=None,
                             last_completed_operation=self.registry_completed())
        self.rejected(lambda: self.save(pending.sha256, last_completed_operation=self.human()),
                      "work_session_actor_changed")
        before = self.files()
        self.assertEqual(self.save(terminal.sha256, last_completed_operation=self.registry_completed())._raw,
                         terminal._raw)
        self.assertEqual(self.files(), before)

    def test_cut_before_terminal_publish_preserves_pending_and_original_bytes(self):
        pending = self.save(pending_manifest_sha256=MANIFEST, pending_context_sha256=CONTEXT)
        with mock.patch.object(actor.durable, "_atomic_move_file_no_replace",
                               side_effect=OSError("private-failure-marker")):
            with self.assertRaisesRegex(actor.WorkSessionActorError, "^work_session_actor_durability_unknown$") as error:
                self.save(pending.sha256, last_completed_operation=self.human())
        self.assertIsNone(error.exception.__context__)
        self.assertIsNone(error.exception.__cause__)
        self.assertEqual(self.actor.read()._raw, pending._raw)
        self.assertFalse((self.directory / "000000000002.json").exists())
        retained = tuple(self.directory.glob(".pending_*"))
        self.assertEqual(len(retained), 1)
        self.assertEqual((self.directory / "000000000001.json").read_bytes(), pending._raw)
        self.assertTrue(self.actor.read().public_summary()["pending_original_operation_selected"])

    def test_failure_after_terminal_publish_retains_discoverable_exact_selector(self):
        pending = self.save(pending_manifest_sha256=MANIFEST, pending_context_sha256=CONTEXT)
        real_move = actor.durable._atomic_move_file_no_replace

        def publish_then_interrupt(*args, **kwargs):
            real_move(*args, **kwargs)
            raise OSError("private-post-publish-marker")

        with mock.patch.object(actor.durable, "_atomic_move_file_no_replace", side_effect=publish_then_interrupt):
            with self.assertRaisesRegex(actor.WorkSessionActorError, "^work_session_actor_durability_unknown$"):
                self.save(pending.sha256, last_completed_operation=self.human())
        # The storage error is not claimed as completion. A separate reader can
        # discover the original selector for the authenticated completed-only path.
        restored = self.actor.read()
        self.assertEqual(restored.document()["last_completed_operation"], self.human().document())
        self.assertFalse(restored.public_summary()["pending_original_operation_selected"])
        self.assertFalse(restored.public_summary()["completion_selector_is_authority"])
        self.assertEqual((self.directory / "000000000001.json").read_bytes(), pending._raw)

    def test_fresh_process_reads_terminal_original_selector_without_pending_blocker(self):
        pending = self.save(pending_manifest_sha256=MANIFEST, pending_context_sha256=CONTEXT)
        terminal = self.save(pending.sha256, last_completed_operation=self.human())
        before = self.files()
        child = self.child_read(self.route, terminal._raw)
        self.assertEqual(child.returncode, 0, "Synthetic actor child failed")
        self.assertEqual(child.stderr, b"")
        self.assertEqual(json.loads(child.stdout), terminal.public_summary())
        for value in (MANIFEST, CONTEXT, self.app, self.route, self.session, self.claim, str(self.root)):
            self.assertNotIn(value.encode(), child.stdout + child.stderr)
        self.assertEqual(self.files(), before)

    def test_real_child_exit_after_terminal_actor_save_is_fresh_process_discoverable(self):
        pending = self.save(pending_manifest_sha256=MANIFEST, pending_context_sha256=CONTEXT)
        script = """
import json, os, sys
from pathlib import Path
from wom_kit import exact_human_approval as a, exact_operation_manifest as e
from wom_kit import work_session_actor as actor, work_session_registry as r
root, identity = a._archive_identity(Path(sys.argv[1]))
store = r.WorkSessionRegistryStore(root, a.exact_human_approval_archive_identity_sha256(identity))
route = actor.WorkSessionActorStore(store, client_app_ref=sys.argv[2], task_route_ref=sys.argv[3])
with e.ExactOperationWriterLock(root) as held:
    prior = route.read()
    value = prior.document()
    terminal = actor.CompletedOperationSelector.from_document({
        'kind': 'human_session_decision', 'manifest_sha256': value['pending_manifest_sha256'],
        'context_sha256': value['pending_context_sha256'],
    })
    snapshot = store.read()
    route.save(expected_sha256=prior.sha256, held_lock=held,
        work_session_ref=value['work_session_ref'], claim_ref=value['claim_ref'],
        observed_binding=snapshot.binding(value['work_session_ref']), last_completed_operation=terminal)
    # This fixture tests terminal selector persistence only. It deliberately
    # does not assert that fabricated selectors are authenticated completion.
    os._exit(73)
"""
        child = subprocess.run([sys.executable, "-B", "-c", script,
            str(self.root), self.app, self.route], capture_output=True, timeout=60,
            creationflags=process_launch.noninteractive_creationflags())
        self.assertEqual(child.returncode, 73, "Synthetic cut did not reach terminal save")
        self.assertEqual(child.stdout + child.stderr, b"")
        terminal = self.actor.read()
        self.assertEqual(terminal.document()["last_completed_operation"], self.human().document())
        self.assertFalse(terminal.public_summary()["pending_original_operation_selected"])
        self.assertFalse(terminal.public_summary()["completion_selector_is_authority"])
        self.assertEqual((self.directory / "000000000001.json").read_bytes(), pending._raw)
        # Acquiring the same real OS lock proves that the dead child did not
        # leave a lock owner that would block the next explicit operation.
        with exact.ExactOperationWriterLock(self.root) as held:
            held.verify_held()
        before = self.files()
        observer = self.child_read(self.route, terminal._raw)
        self.assertEqual(observer.returncode, 0, "Synthetic fresh reader failed")
        self.assertEqual(observer.stderr, b"")
        self.assertEqual(json.loads(observer.stdout), terminal.public_summary())
        self.assertEqual(self.files(), before)


if __name__ == "__main__":
    unittest.main()
