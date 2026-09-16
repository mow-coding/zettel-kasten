"""Registry-only completion with original task authority and durable replay."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_registry as registry
from wom_kit import work_session_registry_intent as intents
import test_v0420_work_session_state as state_fixture


class CompletionTests(unittest.TestCase):
    def task(self):
        case = state_fixture.WorkSessionStateTests("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        return case, case.fixture

    def test_complete_closes_only_registry_ownership_and_replays_without_writes(self):
        case, task = self.task()
        (task.root / "synthetic-preserved-object.bin").write_bytes(b"synthetic canonical bytes")
        (task.root / "synthetic-preserved-receipt.json").write_bytes(b'{"synthetic":true}')
        files = task.domain_files()
        receipts = task.claims()
        prior_claim = task.routing.read().document()["claim_ref"]
        result = case.run_state("complete")
        current = task.store.read()
        session = current._document["sessions"][case.session]
        self.assertEqual(session["state"], "completed")
        self.assertIsNone(session["claim_ref"])
        self.assertIsNone(current._document["workstreams"][session["workstream_ref"]]["active_session_ref"])
        self.assertIsNone(task.routing.read().document()["claim_ref"])
        self.assertEqual(result["state"], "completed")
        self.assertFalse(result["current_claim_ownership_verified"])
        self.assertTrue(result["current_state_verified"])
        self.assertEqual(task.claims(), receipts)
        for path, value in files.items():
            self.assertEqual((task.root / path).read_bytes(), value)
        # An unrelated generation cannot make the old completion write again.
        with exact.ExactOperationWriterLock(task.root) as held:
            task.store.commit(registry.plan_transition(task.store.read(), action="register-app",
                              label="Synthetic unrelated app"), held_lock=held)
        before = task.domain_files()
        with patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("replanned")), \
             patch.object(intents, "observe_or_apply_registry_intent", side_effect=AssertionError("executed")), \
             patch.object(actor.WorkSessionActorStore, "save", side_effect=AssertionError("rewrote routing")):
            replay = case.run_state("complete", True)
        self.assertEqual(replay["plan_sha256"], result["plan_sha256"])
        self.assertTrue(replay["original_operation_already_completed"])
        self.assertEqual(task.domain_files(), before)
        self.assertEqual(task.native.calls, 1)
        for private in (str(task.root), prior_claim, "Synthetic private"):
            self.assertNotIn(private, json.dumps([result, replay]))

    def test_completion_pending_committed_and_terminal_loss_reuse_one_intent(self):
        for boundary in ("pending", "registry", "before_terminal", "terminal"):
            with self.subTest(boundary=boundary):
                case, task = self.task()
                receipts = task.claims()
                case.cut("complete", boundary)
                selected = task.routing.read().document()
                plan = (selected["pending_registry_intent_plan_sha256"]
                        or selected["last_completed_operation"]["plan_sha256"])
                with patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("new intent")), \
                     patch.object(intents, "save_registry_intent", side_effect=AssertionError("rewrote intent")):
                    if boundary == "pending":
                        result = case.run_state("complete", True)
                    else:
                        with patch.object(registry.WorkSessionRegistryStore, "commit",
                                          side_effect=AssertionError("duplicate completion")):
                            result = case.run_state("complete", True)
                self.assertEqual(result["plan_sha256"], plan)
                self.assertEqual(result["state"], "completed")
                self.assertFalse(result["current_claim_ownership_verified"])
                self.assertEqual(task.store.read().revision, 4)
                self.assertEqual(task.claims(), receipts)
                self.assertEqual(task.native.calls, 1)

    def test_unselected_intent_and_fresh_repeat_never_authorize_completion(self):
        case, task = self.task()
        case.cut("complete", "intent")
        before = task.domain_files()
        with patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("guessed intent")), \
             patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("committed orphan")):
            case.reject(lambda: case.run_state("complete", True), "work_session_state_action_mismatch")
        self.assertEqual(task.domain_files(), before)
        case.run_state("complete")
        before = task.domain_files()
        for action, original in (("complete", False), ("pause", False), ("resume", False),
                                 ("pause", True), ("resume", True)):
            with self.subTest(action=action, original=original):
                case.reject(lambda: case.run_state(action, original))
        self.assertEqual(task.domain_files(), before)

    def test_completion_requires_current_claim_exact_route_and_original_mac(self):
        case, task = self.task()
        before = task.domain_files()
        for changes in ({"work_session_ref": None}, {"work_session_ref": registry._new_ref("work_session")},
                        {"task_route_ref": actor.new_task_route_ref()}, {"client_app_ref": registry._new_ref("client_app")}):
            with self.subTest(fields=tuple(changes)):
                case.reject(lambda: case.run_state("complete", **changes))
        with patch.object(task.key, "use_key", side_effect=OSError("PRIVATE_FAILURE")):
            case.reject(lambda: case.run_state("complete"))
        self.assertEqual(task.domain_files(), before)
        case.run_state("pause")
        before = task.domain_files()
        case.reject(lambda: case.run_state("complete"))
        self.assertEqual(task.domain_files(), before)

    def test_complete_intent_exact_consumed_claim_and_required_origin(self):
        case, task = self.task()
        old_claim = task.routing.read().document()["claim_ref"]
        case.cut("complete", "pending")
        plan = task.routing.read().document()["pending_registry_intent_plan_sha256"]
        path = task.root.joinpath(*intents.PRIVATE_ROOT, plan[7:] + ".json")
        raw = path.read_bytes()
        base = json.loads(raw)
        self.assertEqual(base["request"]["action"], "complete")
        self.assertEqual(base["request"]["claim_ref"], old_claim)
        self.assertEqual(base["generated_refs"], [])
        self.assertIsNone(base["request"]["label"])
        self.assertIsNone(base["request"]["target_app_ref"])
        self.assertIn("original_establishment_selector", base)
        changes = []
        missing = deepcopy(base)
        del missing["original_establishment_selector"]
        changes.append(missing)
        for key, value in (("generated_refs", [old_claim]), ("original_establishment_selector", None)):
            changed = deepcopy(base)
            changed[key] = value
            changes.append(changed)
        for key, value in (("claim_ref", None), ("label", "Synthetic forbidden"), ("target_app_ref", task.app)):
            changed = deepcopy(base)
            changed["request"][key] = value
            changes.append(changed)
        for changed in changes:
            with self.subTest(fields=tuple(changed)):
                changed["intent_sha256"] = intents._sha(intents._canonical(
                    {key: value for key, value in changed.items() if key != "intent_sha256"}))
                with self.assertRaises(intents.WorkSessionRegistryIntentError):
                    intents.RegistryTransitionIntent(intents._canonical(changed))
        # Self-consistent JSON/hash is not proof of the consumed original claim.
        for field in ("claim", "context", "action"):
            with self.subTest(field=field):
                changed = deepcopy(base)
                if field == "claim":
                    changed["request"]["claim_ref"] = registry._new_ref("claim")
                elif field == "context":
                    changed["original_establishment_selector"]["context_sha256"] = "sha256:" + "f" * 64
                else:
                    changed["request"]["action"] = "pause"
                changed["intent_sha256"] = intents._sha(intents._canonical(
                    {key: value for key, value in changed.items() if key != "intent_sha256"}))
                path.write_bytes(intents._canonical(changed))
                before = task.domain_files()
                with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("forged completion")):
                    case.reject(lambda: case.run_state("complete", True))
                self.assertEqual(task.domain_files(), before)
        path.write_bytes(raw)

    def test_historical_completion_never_claims_current_closure_after_later_registry_drift(self):
        case, task = self.task()
        case.run_state("complete")
        completed = task.store.read()
        for fault in ("reactivated", "different_active_session"):
            with self.subTest(fault=fault):
                # Inject an untrusted but schema-valid later generation, not a
                # supported lifecycle transition or a new approval. Original
                # completed bytes remain untouched; current topology must fail.
                changed = deepcopy(completed._document)
                changed["revision"] += 1
                changed["previous_sha256"] = completed.sha256
                old_session = changed["sessions"][case.session]
                stream = changed["workstreams"][old_session["workstream_ref"]]
                if fault == "reactivated":
                    old_session.update(state="claimed", claim_ref=registry._new_ref("claim"))
                    stream["active_session_ref"] = case.session
                else:
                    new_ref = registry._new_ref("work_session")
                    successor = deepcopy(old_session)
                    successor.update(state="created", revision=1, predecessor_ref=case.session)
                    changed["sessions"][new_ref] = successor
                    stream["active_session_ref"] = new_ref
                forged = registry.RegistrySnapshot(changed)
                task.store.path.joinpath(f"{forged.revision:012d}.json").write_bytes(registry._canonical(changed))
                before = task.domain_files()
                case.reject(lambda: case.run_state("complete", True),
                            "work_session_state_current_unavailable", committed=True)
                self.assertEqual(task.domain_files(), before)


if __name__ == "__main__":
    unittest.main()
