"""Additive typed origins preserve historical raw intents and their authority."""

from copy import deepcopy
import json
import unittest

from wom_kit import exact_human_approval as approval
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_establishment as establishment
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit import work_session_registry_intent as intents
import test_v0420_work_session_registry_intent as fixture


class EstablishmentIntentTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.RegistryIntentTests("runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.store, self.root = self.case.store, self.case.root
        registered = self.case.register_plan()
        self.case.commit_fixture(registered)
        self.app = registered.result_refs[0]
        create = registry.plan_transition(self.store.read(), action="create", client_app_ref=self.app,
                                          label="Synthetic private origin")
        prepared = operation.prepare_session_decision(create, task_route_ref=actor.new_task_route_ref())
        context = prepared.context(archive_id=fixture.ARCHIVE_ID, reviewer_claim="person:synthetic-origin")
        with exact.ExactOperationWriterLock(self.root) as held:
            bundle.save_context_bound_session_decision(self.store, prepared, context=context, held_lock=held)
        # Synthetic immutable predecessor only. Intent reading does not claim
        # that this context was approved; the separate real MAC tests do that.
        self.case.commit_fixture(create)
        self.session = create.result_refs[-1]
        self.legacy = {"manifest_sha256": prepared.manifest.manifest_sha256,
                       "context_sha256": approval.exact_human_approval_context_sha256(context)}
        self.selected = establishment.EstablishmentSelector.from_original_create(self.legacy)

    def plan(self, action):
        values = dict(action=action, client_app_ref=self.app, work_session_ref=self.session)
        if action in {"pause", "complete"}:
            values["claim_ref"] = self.store.read()._document["sessions"][self.session]["claim_ref"]
        return registry.plan_transition(self.store.read(), **values)

    def prepare(self, plan, **options):
        with exact.ExactOperationWriterLock(self.root) as held:
            return intents.prepare_registry_intent(self.store, plan, held_lock=held, **options)

    def test_default_and_legacy_bound_raw_bytes_are_exactly_the_old_contract(self):
        plan = self.plan("claim")
        for old in (None, self.legacy):
            with self.subTest(bound=old is not None):
                intent = self.prepare(plan, original_create_selector=old)
                basis = {"schema": intents.INTENT_SCHEMA, "archive_identity_sha256": self.store.archive_identity_sha256,
                         "before_revision": plan.after.revision - 1, "before_sha256": plan.before_sha256,
                         "request": plan._request, "generated_refs": list(plan._generated_refs),
                         "after_sha256": plan.after.sha256, "plan_sha256": plan.plan_sha256}
                if old is not None:
                    basis["original_create_selector"] = old
                expected = intents._canonical({**basis, "intent_sha256": intents._sha(intents._canonical(basis))})
                self.assertEqual(intent._raw, expected)
                self.assertEqual(intent.original_create_selector, old)
                self.assertEqual(intent.original_establishment_selector, self.selected if old is not None else None)
                before = self.case.files()
                self.assertEqual(intents.RegistryTransitionIntent(expected)._raw, expected)
                self.assertEqual(self.case.files(), before)
                self.assertNotIn("original_establishment_selector", json.loads(intent._raw))

    def test_typed_origin_roundtrip_and_complete_state_chain_without_approval_claim(self):
        for action in ("claim", "pause", "resume", "complete"):
            with self.subTest(action=action):
                plan = self.plan(action)
                intent = self.prepare(plan, original_establishment_selector=self.selected)
                with exact.ExactOperationWriterLock(self.root) as held:
                    intents.save_registry_intent(self.store, intent, held_lock=held)
                    outcome = intents.observe_or_apply_registry_intent(self.store,
                        plan_sha256=intent.plan_sha256, held_lock=held)
                    restored = intents.load_registry_intent(self.store,
                        plan_sha256=intent.plan_sha256, held_lock=held)
                self.assertEqual(outcome.transition, plan)
                self.assertEqual(restored._raw, intent._raw)
                self.assertEqual(restored.original_establishment_selector, self.selected)
                self.assertIsNone(restored.original_create_selector)
                self.assertFalse(restored.public_summary()["human_approval_granted"])
                self.assertNotIn(self.selected.context_sha256, json.dumps(restored.public_summary()))
        self.assertFalse((self.root / approval.CLAIMS_RELATIVE_ROOT).exists())

    def test_conflicting_null_unknown_or_untyped_origins_never_become_intents(self):
        plan = self.plan("claim")
        for options in (
            {"original_create_selector": self.legacy, "original_establishment_selector": self.selected},
            {"original_establishment_selector": self.selected.document()},
        ):
            self.case.assert_fixed(lambda: self.prepare(plan, **options))
        intent = self.prepare(plan, original_establishment_selector=self.selected)
        document = json.loads(intent._raw)
        invalid = []
        for value in (None, {}, [], True, {**self.selected.document(), "action": "recover"},
                      {**self.selected.document(), "extra": "PRIVATE_MARKER"}):
            invalid.append({**deepcopy(document), "original_establishment_selector": value})
        invalid.append({**deepcopy(document), "original_create_selector": self.legacy})
        for changed in invalid:
            self.case.assert_fixed(lambda: intents.RegistryTransitionIntent(self.case.rehash(changed)))
        registered = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic other")
        self.case.assert_fixed(lambda: self.prepare(registered, original_establishment_selector=self.selected),
                               "work_session_registry_intent_action_refused")

    def test_rehashed_typed_action_context_or_missing_bundle_is_not_original_source(self):
        plan = self.plan("claim")
        intent = self.prepare(plan, original_establishment_selector=self.selected)
        with exact.ExactOperationWriterLock(self.root) as held:
            intents.save_registry_intent(self.store, intent, held_lock=held)
        path, original = self.case.path(intent.plan_sha256), json.loads(intent._raw)
        before_registry = self.store.read().sha256
        for field, value in (("action", "accept"), ("context_sha256", "sha256:" + "f" * 64),
                             ("manifest_sha256", "sha256:" + "f" * 64)):
            changed = deepcopy(original)
            changed["original_establishment_selector"][field] = value
            path.write_bytes(self.case.rehash(changed))
            before = self.case.files()
            self.case.assert_fixed(lambda: self.case.load(intent.plan_sha256))
            self.assertEqual(self.case.files(), before)
            self.assertEqual(self.store.read().sha256, before_registry)
        path.write_bytes(intent._raw)


if __name__ == "__main__":
    unittest.main()
