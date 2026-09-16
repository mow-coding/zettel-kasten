"""Exact pause/resume intent replay; not public or human-MAC acceptance proof.

The original create predecessor uses the established synthetic registry fixture.
Its real context-bound bundle is preserved, but only the separate state facade
authenticates the original completed human approval and caller route.
"""

from copy import deepcopy
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

import test_v0420_work_session_registry_intent as fixtures
from wom_kit import exact_human_approval as approval
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit import work_session_registry_intent as intents


class StateIntentTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RegistryIntentTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.store = self.fixture.root, self.fixture.store
        app = self.fixture.register_plan()
        self.fixture.commit_fixture(app)
        self.app = app.result_refs[0]
        create = registry.plan_transition(self.store.read(), action="create", client_app_ref=self.app,
                                          label="Synthetic private state task")
        prepared = operation.prepare_session_decision(create, task_route_ref="task_route_" + "a" * 32)
        context = prepared.context(archive_id=fixtures.ARCHIVE_ID, reviewer_claim="person:synthetic-state")
        self.origin = {"manifest_sha256": prepared.manifest.manifest_sha256,
                       "context_sha256": approval.exact_human_approval_context_sha256(context)}
        with exact.ExactOperationWriterLock(self.root) as held:
            bundle.save_context_bound_session_decision(self.store, prepared, context=context, held_lock=held)
        self.fixture.commit_fixture(create)
        self.session = create.result_refs[-1]
        claim = registry.plan_transition(self.store.read(), action="claim", client_app_ref=self.app,
                                         work_session_ref=self.session)
        self.old_claim = claim._generated_refs[0]
        claimed = self.prepare_save(claim)
        self.fixture.apply(claimed.plan_sha256)

    def plan(self, action):
        arguments = {"action": action, "client_app_ref": self.app, "work_session_ref": self.session}
        if action == "pause":
            arguments["claim_ref"] = self.store.read()._document["sessions"][self.session]["claim_ref"]
        return registry.plan_transition(self.store.read(), **arguments)

    def prepare_save(self, plan):
        with exact.ExactOperationWriterLock(self.root) as held:
            intent = intents.prepare_registry_intent(self.store, plan, held_lock=held,
                                                      original_create_selector=self.origin)
            intents.save_registry_intent(self.store, intent, held_lock=held)
        return intent

    def completed(self, intent):
        with exact.ExactOperationWriterLock(self.root) as held:
            return intents.observe_committed_registry_intent(self.store, plan_sha256=intent.plan_sha256,
                                                              held_lock=held)

    def test_pause_resume_preserves_exact_claim_and_never_mints_authority(self):
        pause = self.prepare_save(self.plan("pause"))
        raw = json.loads(pause._raw)
        self.assertEqual(raw["generated_refs"], [])
        self.assertEqual(raw["request"]["claim_ref"], self.old_claim)
        self.fixture.apply(pause.plan_sha256)
        paused = self.store.read()
        self.assertEqual(paused._document["sessions"][self.session]["state"], "paused")
        self.assertIsNone(paused._document["sessions"][self.session]["claim_ref"])
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(registry.WorkSessionRegistryError):
                self.store.require_claimed_binding(client_app_ref=self.app, work_session_ref=self.session,
                                                   claim_ref=self.old_claim, held_lock=held)
        plan = self.plan("resume")
        resume = self.prepare_save(plan)
        new_claim = plan._generated_refs[0]
        self.assertNotEqual(new_claim, self.old_claim)
        self.assertEqual(json.loads(resume._raw)["generated_refs"], [new_claim])
        self.assertIsNone(json.loads(resume._raw)["request"]["claim_ref"])
        with mock.patch.dict(registry.plan_transition.__kwdefaults__,
                             {"_ref_factory": lambda _prefix: self.fail("unexpected new reference")}):
            first = self.fixture.apply(resume.plan_sha256)
            before = self.fixture.files()
            with mock.patch.object(self.store, "commit", side_effect=AssertionError("replay committed again")):
                second = self.fixture.apply(resume.plan_sha256)
                self.completed(pause)
        self.assertEqual((first.status, second.status), ("committed", "already_committed"))
        self.assertEqual(self.fixture.files(), before)
        with exact.ExactOperationWriterLock(self.root) as held:
            self.assertEqual(self.store.require_claimed_binding(
                client_app_ref=self.app, work_session_ref=self.session, claim_ref=new_claim,
                held_lock=held, expected_binding=plan.after.binding(self.session)), plan.after.binding(self.session))
        public = json.dumps([pause.public_summary(), resume.public_summary(), first.public_summary()])
        for private in (self.old_claim, new_claim, "Synthetic private state task"):
            self.assertNotIn(private, public)
        self.assertFalse(first.public_summary()["current_claim_authority_evaluated"])
        self.assertFalse((self.root / "profiles/local/exact-human-approvals").exists())
        self.assertFalse((self.root / "receipts").exists())

    def test_action_specific_shapes_and_required_origin_are_strict(self):
        pause = self.prepare_save(self.plan("pause"))
        self.fixture.apply(pause.plan_sha256)
        resume = self.prepare_save(self.plan("resume"))
        for intent in (pause, resume):
            base = json.loads(intent._raw)
            changes = []
            missing = deepcopy(base)
            missing.pop("original_create_selector")
            changes.append(missing)
            for key, value in (("original_create_selector", None), ("original_create_selector", {}),
                               ("before_revision", True), ("generated_refs", None),
                               ("generated_refs", ["claim_" + "f" * 32] * 2)):
                changed = deepcopy(base)
                changed[key] = value
                changes.append(changed)
            for key, value in (("label", "Synthetic forbidden label"),
                               ("target_app_ref", self.app), ("claim_ref", None if intent is pause else self.old_claim),
                               ("approval", True)):
                changed = deepcopy(base)
                changed["request"][key] = value
                changes.append(changed)
            changed = deepcopy(base)
            changed["generated_refs"] = [self.old_claim] if intent is pause else []
            changes.append(changed)
            for index, changed in enumerate(changes):
                with self.subTest(action=base["request"]["action"], index=index):
                    raw = self.fixture.rehash(changed)
                    self.assertNotEqual(raw, intent._raw)
                    self.fixture.assert_fixed(lambda: intents.RegistryTransitionIntent(raw))

    def test_rehashed_original_claim_or_origin_tamper_cannot_change_registry(self):
        intent = self.prepare_save(self.plan("pause"))
        base, path = json.loads(intent._raw), self.fixture.path(intent.plan_sha256)
        changes = []
        for key, value in (("claim_ref", "claim_" + "f" * 32), ("client_app_ref", "client_app_" + "f" * 32),
                           ("work_session_ref", "work_session_" + "f" * 32)):
            changed = deepcopy(base)
            changed["request"][key] = value
            changes.append(changed)
        for key in ("manifest_sha256", "context_sha256"):
            changed = deepcopy(base)
            changed["original_create_selector"][key] = "sha256:" + "f" * 64
            changes.append(changed)
        before = self.store.read().sha256
        for index, changed in enumerate(changes):
            with self.subTest(index=index):
                raw = self.fixture.rehash(changed)
                path.write_bytes(raw)
                with mock.patch.object(self.store, "commit", side_effect=AssertionError("tamper committed")):
                    self.fixture.assert_fixed(lambda: self.fixture.apply(intent.plan_sha256))
                self.assertEqual(self.store.read().sha256, before)
                self.assertEqual(path.read_bytes(), raw)

    def test_completed_selector_never_executes_pending_and_history_is_not_current_authority(self):
        pause = self.prepare_save(self.plan("pause"))
        before = self.fixture.files()
        self.fixture.assert_fixed(lambda: self.completed(pause), "work_session_registry_intent_changed")
        self.assertEqual(self.fixture.files(), before)
        self.fixture.apply(pause.plan_sha256)
        resume = self.prepare_save(self.plan("resume"))
        before = self.fixture.files()
        self.fixture.assert_fixed(lambda: self.completed(resume), "work_session_registry_intent_changed")
        self.assertEqual(self.fixture.files(), before)
        self.fixture.apply(resume.plan_sha256)
        later_pause = self.prepare_save(self.plan("pause"))
        self.fixture.apply(later_pause.plan_sha256)
        before = self.fixture.files()
        for original in (pause, resume):
            result = self.completed(original)
            self.assertEqual(result.status, "already_committed")
            self.assertFalse(result.public_summary()["current_claim_authority_evaluated"])
        self.assertEqual(self.fixture.files(), before)
        self.assertEqual(self.store.read()._document["sessions"][self.session]["state"], "paused")

    def test_valid_shape_rehashed_resume_identity_action_or_postimage_is_not_replay_authority(self):
        pause = self.prepare_save(self.plan("pause"))
        self.fixture.apply(pause.plan_sha256)
        intent = self.prepare_save(self.plan("resume"))
        base, path = json.loads(intent._raw), self.fixture.path(intent.plan_sha256)
        changes = []
        for key, value in (("generated_refs", ["claim_" + "f" * 32]),
                           ("after_sha256", "sha256:" + "f" * 64),
                           ("before_sha256", "sha256:" + "f" * 64)):
            changed = deepcopy(base)
            changed[key] = value
            changes.append(changed)
        changed = deepcopy(base)
        changed["request"]["action"] = "claim"
        changes.append(changed)
        before = self.store.read().sha256
        for index, changed in enumerate(changes):
            with self.subTest(index=index):
                raw = self.fixture.rehash(changed)
                self.assertNotEqual(raw, intent._raw)
                # Syntax and self-hash alone are valid; replay must still
                # reconstruct the original paused predecessor and exact output.
                self.assertEqual(intents.RegistryTransitionIntent(raw)._raw, raw)
                path.write_bytes(raw)
                with mock.patch.object(self.store, "commit", side_effect=AssertionError("forged resume committed")):
                    self.fixture.assert_fixed(lambda: self.fixture.apply(intent.plan_sha256))
                self.assertEqual(self.store.read().sha256, before)
                self.assertEqual(path.read_bytes(), raw)

    def test_exact_predecessor_drift_is_refused_without_replanning(self):
        pause = self.prepare_save(self.plan("pause"))
        self.fixture.commit_fixture(self.fixture.register_plan("Synthetic unrelated app"))
        before = self.fixture.files()
        with mock.patch.object(self.store, "commit", side_effect=AssertionError("drift committed")):
            self.fixture.assert_fixed(lambda: self.fixture.apply(pause.plan_sha256),
                                      "work_session_registry_intent_changed")
        self.assertEqual(self.fixture.files(), before)

    def test_saved_state_intent_is_not_overwritten_or_manufactured_after_commit(self):
        intent = self.prepare_save(self.plan("pause"))
        path = self.fixture.path(intent.plan_sha256)
        before = os.lstat(path)
        with exact.ExactOperationWriterLock(self.root) as held:
            with mock.patch.object(registry, "_write_private_pending", side_effect=AssertionError("resave wrote")):
                intents.save_registry_intent(self.store, intent, held_lock=held)
        after = os.lstat(path)
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
        self.fixture.apply(intent.plan_sha256)
        path.unlink()
        with exact.ExactOperationWriterLock(self.root) as held:
            self.fixture.assert_fixed(lambda: intents.save_registry_intent(self.store, intent, held_lock=held),
                                      "work_session_registry_intent_changed")
        self.assertFalse(path.exists())

    def test_legacy_register_and_claim_keep_exact_original_document_contract(self):
        for factory in (self.fixture.register_plan, self.fixture.claim_plan):
            plan = factory()
            with self.subTest(action=plan.action), exact.ExactOperationWriterLock(self.root) as held:
                intent = intents.prepare_registry_intent(self.store, plan, held_lock=held)
                expected = {"schema": intents.INTENT_SCHEMA,
                            "archive_identity_sha256": self.store.archive_identity_sha256,
                            "before_revision": plan.after.revision - 1, "before_sha256": plan.before_sha256,
                            "request": plan._request, "generated_refs": list(plan._generated_refs),
                            "after_sha256": plan.after.sha256, "plan_sha256": plan.plan_sha256}
                expected["intent_sha256"] = intents._sha(intents._canonical(expected))
                original_bytes = intents._canonical(expected)
                self.assertEqual(intent._raw, original_bytes)
                self.assertEqual(intents.RegistryTransitionIntent(original_bytes)._raw, original_bytes)
                self.assertIsNone(intent.original_create_selector)
                self.assertEqual(set(json.loads(original_bytes)), intents._DOCUMENT_KEYS)

    def test_real_process_cuts_resume_pause_and_original_fixed_resume_claim(self):
        script = (
            "import json, os, sys\nfrom pathlib import Path\n"
            "from wom_kit import exact_human_approval as a, exact_operation_manifest as e\n"
            "from wom_kit import work_session_registry as r, work_session_registry_intent as i\n"
            "root, archive_id = a._archive_identity(Path(sys.argv[1]))\n"
            "store = r.WorkSessionRegistryStore(root, a.exact_human_approval_archive_identity_sha256(archive_id))\n"
            "def refuse(_prefix): raise AssertionError('unexpected fresh reference')\n"
            "r.plan_transition.__kwdefaults__['_ref_factory'] = refuse\n"
            "original = store.commit\n"
            "def cut(*args, **kwargs):\n"
            " if sys.argv[3] == 'before': os._exit(73)\n"
            " result = original(*args, **kwargs)\n"
            " if sys.argv[3] == 'after': os._exit(73)\n"
            " return result\n"
            "store.commit = cut\n"
            "with e.ExactOperationWriterLock(root) as held:\n"
            " result = i.observe_or_apply_registry_intent(store, plan_sha256=sys.argv[2], held_lock=held)\n"
            "print(json.dumps(result.public_summary(), sort_keys=True))\n"
        )
        for action, cut in (("pause", "before"), ("resume", "after")):
            with self.subTest(action=action):
                plan = self.plan(action)
                intent = self.prepare_save(plan)
                command = [sys.executable, "-B", "-c", script, str(self.root), intent.plan_sha256]
                options = dict(capture_output=True, text=True, timeout=60,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                crashed = subprocess.run([*command, cut], **options)
                self.assertEqual(crashed.returncode, 73, "synthetic child did not reach requested cut")
                self.assertEqual(crashed.stdout, "")
                self.assertEqual(self.store.read().sha256, plan.before_sha256 if cut == "before" else plan.after.sha256)
                resumed = subprocess.run([*command, "continue"], **options)
                self.assertEqual(resumed.returncode, 0, "synthetic original intent continuation failed")
                public = json.loads(resumed.stdout)
                self.assertEqual(public["status"], "committed" if cut == "before" else "already_committed")
                self.assertFalse(public["current_claim_authority_evaluated"])
                self.assertEqual(self.store.read().sha256, plan.after.sha256)
                self.assertEqual(self.fixture.path(intent.plan_sha256).read_bytes(), intent._raw)
                for private in (self.old_claim, *plan._generated_refs):
                    self.assertNotIn(private, resumed.stdout)


if __name__ == "__main__":
    unittest.main()
