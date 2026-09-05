"""Immutable private establishment routing, not human approval evidence."""

from copy import deepcopy
import json
import unittest
from unittest import mock

import test_v0420_work_session_actor as fixture
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_registry as registry


MANIFEST = "sha256:" + "a" * 64
CONTEXT = "sha256:" + "b" * 64
PLAN = "sha256:" + "c" * 64


class ActorEstablishmentTests(unittest.TestCase):
    setUp = fixture.WorkSessionActorTests.setUp
    transition = fixture.WorkSessionActorTests.transition
    fields = fixture.WorkSessionActorTests.fields
    save = fixture.WorkSessionActorTests.save
    files = fixture.WorkSessionActorTests.files
    rejected = fixture.WorkSessionActorTests.rejected

    def origin(self, action="create", **changes):
        from wom_kit.work_session_establishment import EstablishmentSelector
        return EstablishmentSelector.from_document({
            "action": action, "manifest_sha256": MANIFEST, "context_sha256": CONTEXT, **changes,
        })

    def encode(self, document):
        basis = {key: value for key, value in document.items() if key != "actor_sha256"}
        return registry._canonical({**basis, "actor_sha256": actor._sha(registry._canonical(basis))})

    def test_legacy_bytes_and_summary_never_infer_establishment_from_last_operation(self):
        completed = actor.CompletedOperationSelector.from_document({
            "kind": "human_session_decision", "manifest_sha256": MANIFEST, "context_sha256": CONTEXT,
        })
        old = self.save(last_completed_operation=completed)
        original_summary = old.public_summary()
        self.assertNotIn("established_origin", old.document())
        self.assertNotIn("established_origin_selected", original_summary)
        before = self.files()
        with mock.patch.object(registry, "_write_private_pending", side_effect=AssertionError("legacy rewritten")):
            self.assertEqual(self.save(old.sha256)._raw, old._raw)
            self.assertEqual(self.actor.read()._raw, old._raw)
        self.assertEqual(self.files(), before)
        self.assertEqual(actor.ActorContext(old._raw).sha256, old.sha256)
        self.assertEqual(actor.ActorContext(old._raw).public_summary(), original_summary)
        registry_before = self.registry.read().sha256
        # Explicit pointer recording is a new actor CAS, not an assertion that
        # this synthetic selector has been authenticated by the storage layer.
        added = self.save(old.sha256, established_origin=self.origin())
        self.assertEqual(added.document()["revision"], 2)
        self.assertEqual(added.document()["previous_sha256"], old.sha256)
        self.assertEqual((self.directory / "000000000001.json").read_bytes(), old._raw)
        self.assertEqual(self.registry.read().sha256, registry_before)
        self.assertFalse(added.public_summary()["establishment_selector_is_authority"])

    def test_create_and_accept_are_private_detached_routing_selectors(self):
        for action in ("create", "accept"):
            with self.subTest(action=action):
                route = actor.new_task_route_ref()
                store = actor.WorkSessionActorStore(self.registry, client_app_ref=self.app, task_route_ref=route)
                origin = self.origin(action)
                detached = origin.document()
                with exact.ExactOperationWriterLock(self.root) as held:
                    value = store.save(expected_sha256=None, established_origin=origin,
                                       held_lock=held, **self.fields())
                detached["context_sha256"] = PLAN
                view = value.document()
                view["established_origin"]["manifest_sha256"] = PLAN
                self.assertEqual(store.read().document()["established_origin"], origin.document())
                summary = value.public_summary()
                self.assertTrue(summary["established_origin_selected"])
                self.assertFalse(summary["routing_is_write_authority"])
                self.assertFalse(summary["establishment_selector_is_authority"])
                for private in (MANIFEST, CONTEXT, self.app, route, self.session, self.claim, str(self.root)):
                    self.assertNotIn(private, json.dumps(summary) + repr(value) + repr(origin))

    def test_origin_survives_pending_and_terminal_cas_but_cannot_be_replaced(self):
        origin = self.origin()
        first = self.save(established_origin=origin)
        pending = self.save(first.sha256, pending_registry_intent_plan_sha256=PLAN)
        completed = actor.CompletedOperationSelector.from_document({"kind": "registry_transition", "plan_sha256": PLAN})
        terminal = self.save(pending.sha256, pending_registry_intent_plan_sha256=None,
                             last_completed_operation=completed)
        self.assertEqual(terminal.document()["established_origin"], origin.document())
        self.assertEqual(terminal.document()["last_completed_operation"], completed.document())
        self.assertEqual((self.directory / "000000000001.json").read_bytes(), first._raw)
        before = self.files()
        self.assertEqual(self.save(terminal.sha256, established_origin=self.origin())._raw, terminal._raw)
        self.assertEqual(self.files(), before)
        for replacement in (None, self.origin("accept"), self.origin(manifest_sha256=PLAN),
                            self.origin(context_sha256=PLAN), self.origin().document(), True):
            with self.subTest(kind=type(replacement).__name__):
                self.rejected(lambda: self.save(terminal.sha256, established_origin=replacement))
        self.rejected(lambda: self.save(first.sha256, established_origin=origin), "work_session_actor_changed")
        self.rejected(lambda: self.actor.save(expected_sha256=terminal.sha256, established_origin=origin,
                                              held_lock=None, **self.fields()), "work_session_actor_lock_required")

    def test_established_route_cannot_clear_or_select_another_session(self):
        initial = self.save(established_origin=self.origin())
        second = self.transition(action="create", client_app_ref=self.app, label="Synthetic distinct task").result_refs[-1]
        self.rejected(lambda: self.save(initial.sha256, work_session_ref=None, observed_binding=None, claim_ref=None),
                      "work_session_actor_changed")
        self.rejected(lambda: self.save(initial.sha256, work_session_ref=second,
                      observed_binding=self.registry.read().binding(second), claim_ref=None), "work_session_actor_changed")

    def test_strict_actor_decoder_rejects_malformed_origin_and_missing_session(self):
        saved = self.save(established_origin=self.origin())
        for origin in (False, [], "Synthetic private", {}, {"action": "create"},
                       {**self.origin().document(), "action": "recover"},
                       {**self.origin().document(), "context_sha256": "private"},
                       {**self.origin().document(), "label": "Synthetic private"}):
            with self.subTest(kind=type(origin).__name__):
                changed = saved.document()
                changed["established_origin"] = origin
                self.rejected(lambda: actor.ActorContext(self.encode(changed)))
        changed = saved.document()
        changed.update(work_session_ref=None, observed_binding=None, claim_ref=None)
        self.rejected(lambda: actor.ActorContext(self.encode(changed)))

    def test_retained_parent_read_rejects_rehashed_origin_removal_and_substitution(self):
        first = self.save(established_origin=self.origin())
        latest = self.save(first.sha256, pending_registry_intent_plan_sha256=PLAN)
        path = self.directory / "000000000002.json"
        for origin in (None, self.origin("accept").document(), self.origin(context_sha256=PLAN).document(), "missing"):
            with self.subTest(kind=type(origin).__name__):
                changed = latest.document()
                if origin == "missing":
                    del changed["established_origin"]
                else:
                    changed["established_origin"] = origin
                # Schema-valid self-hash is not permission to replace the
                # original pointer in the already retained parent chain.
                raw = self.encode(changed)
                actor.ActorContext(raw)
                path.write_bytes(raw)
                self.rejected(self.actor.read, "work_session_actor_changed")
        path.write_bytes(latest._raw)
        self.assertEqual(self.actor.read()._raw, latest._raw)


if __name__ == "__main__":
    unittest.main()
