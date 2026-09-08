"""Regression: unrelated registry change is allowed; actual owner loss is not.

Only synthetic public fixtures/native/key are used. An injected preclaim
exception models a reachable interruption; it is not native power-loss proof.
The earlier whole-registry refusal is retained in the integration record.
"""

import json
import unittest
from unittest.mock import patch

import test_v0420_source_intake_session_public_workflow as public_fixture
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_registry as registry
from wom_kit import work_session_source_intake_workflow as workflow


class SourceIntakeRegistryConcurrencyDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.fixture = public_fixture.PublicSessionSourceIntakeJourneyTests("runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.root = self.fixture.root

    def test_unrelated_registration_passes_but_actual_pause_blocks_retained_review(self):
        fixture = self.fixture
        claims_before = fixture.claims()
        with patch.object(broker, "_claim_exact_human_approval_core",
                          side_effect=RuntimeError("SYNTHETIC_PRIVATE_CONCURRENCY_PRECLAIM_CUT")) as cut:
            interrupted = fixture.call("source-intake-batch", *fixture.refs,
                "--work-session-ref", fixture.session, "--manifest", str(fixture.request),
                "--approve", "--reviewed-by", "person:synthetic-intake-reviewer", ok=False)
        cut.assert_called_once()
        self.assertFalse(interrupted["original_completion_verified"])
        self.assertEqual(fixture.native.calls, 2)
        self.assertEqual(fixture.claims(), claims_before)
        selected = fixture.routing._read(current=False)
        pointer = selected.pending_operation().document()
        self.assertEqual(pointer["kind"], "source_intake_batch")
        retained = fixture.retained(pointer)
        plan, context = retained.prepared.plan, retained.context
        scope = retained.prepared.scope.document()
        registry_before = fixture.store.read()
        binding_before = registry_before.binding(fixture.session)
        self.assertEqual(binding_before, plan.manifest.work_session_binding)
        self.assertEqual(scope["registry_preimage_sha256"], registry_before.sha256)
        self.assertEqual(pointer["context_sha256"], approval.exact_human_approval_context_sha256(context))

        # No domain or authority substitute: the actual same-session claim and
        # current guard both pass before the unrelated registry mutation.
        with exact.ExactOperationWriterLock(self.root) as held:
            view = workflow._source_intake_operation_view(retained.prepared, context, held)
            self.assertEqual(fixture.store.require_claimed_binding(
                client_app_ref=fixture.app, work_session_ref=fixture.session,
                claim_ref=scope["claim_ref"], expected_binding=binding_before, held_lock=held), binding_before)
            workflow._current(view, fixture.store, fixture.routing, selected, held)

        before_normal = fixture.files()
        normal_before = fixture.call("source-intake-batch", *fixture.refs, "--resume", ok=False)
        self.assertEqual(normal_before["reason_code"], "work_session_intake_original_approval_missing")
        self.assertEqual(fixture.files(), before_normal)

        # B is a genuinely new public app registration, not a forged registry
        # edit, A actor rewrite, or guessed ownership grant.
        preview = fixture.session_command("--action", "register-app", "--dry-run", "--request-stdin",
            request={"label": "SYNTHETIC_PRIVATE_CONCURRENT_APP_B"})
        fixture.session_command("--action", "register-app", "--apply", "--request-stdin",
            request={"selection": preview, "label": "SYNTHETIC_PRIVATE_CONCURRENT_APP_B"})
        self.assertNotEqual(preview["client_app_ref"], fixture.app)
        registry_after = fixture.store.read()
        self.assertNotEqual(registry_after.sha256, registry_before.sha256)
        self.assertEqual(registry_after.binding(fixture.session), binding_before)
        after_actor = fixture.routing._read(current=False)
        self.assertEqual(after_actor._raw, selected._raw)
        self.assertEqual(after_actor.pending_operation().document(), pointer)
        self.assertEqual(after_actor.document()["claim_ref"], selected.document()["claim_ref"])
        self.assertEqual(fixture.retained(pointer)._raw, retained._raw)
        self.assertEqual(fixture.retained(pointer).context, context)
        self.assertEqual(fixture.claims(), claims_before)
        self.assertEqual(fixture.native.calls, 2)
        self.assertEqual(fixture.request.read_bytes(), fixture.original_request_bytes)
        for path, raw in fixture.source_bytes.items():
            self.assertEqual(path.read_bytes(), raw)

        # Isolate the two real predicates under the same actual held lock.
        # Both real predicates now accept A without changing its original scope.
        with exact.ExactOperationWriterLock(self.root) as held:
            self.assertEqual(fixture.store.require_claimed_binding(
                client_app_ref=fixture.app, work_session_ref=fixture.session,
                claim_ref=scope["claim_ref"], expected_binding=binding_before, held_lock=held), binding_before)
            workflow._current(view, fixture.store, fixture.routing, selected, held)

        # A real registry transition, not a stubbed ownership guard, removes
        # A's claim. Pause needs current ownership; it creates no human approval.
        with exact.ExactOperationWriterLock(self.root) as held:
            paused = registry.plan_transition(fixture.store.read(), action="pause",
                client_app_ref=fixture.app, work_session_ref=fixture.session, claim_ref=scope["claim_ref"])
            fixture.store.commit(paused, held_lock=held)
        self.assertEqual(fixture.store.read()._document["sessions"][fixture.session]["state"], "paused")

        before_continuation = fixture.files()
        normal_after = fixture.call("source-intake-batch", *fixture.refs, "--resume", ok=False)
        review_after = fixture.call("source-intake-batch", *fixture.refs, "--approve", "--review-original", ok=False)
        self.assertEqual(normal_after["reason_code"], "work_session_intake_original_approval_missing")
        self.assertFalse(review_after["ok"])
        self.assertFalse(review_after["original_completion_verified"])
        self.assertEqual(fixture.files(), before_continuation)
        self.assertEqual(fixture.routing._read(current=False)._raw, selected._raw)
        self.assertEqual(fixture.retained(pointer)._raw, retained._raw)
        self.assertEqual(fixture.claims(), claims_before)
        self.assertEqual(fixture.native.calls, 2)
        outputs = [item.receipt_relative_path for item in plan.items]
        if plan.prepared_capture_request is not None:
            outputs.append(plan.prepared_capture_request.relative_path)
        self.assertTrue(all(not (self.root / relative).exists() for relative in outputs))
        self.assertFalse(fixture.key.active)
        print(json.dumps({
            "regression": "unrelated_registration_allowed_actual_pause_refused",
            "same_claimed_binding": True, "same_actor_pending_and_original_context": True,
            "whole_registry_digest_changed": True, "session_claim_guard_passed_after_registration": True,
            "workflow_guard_passed_after_registration": True, "actual_pause_refused": True,
            "normal_resume_reason_before": normal_before["reason_code"],
            "normal_resume_reason_after": normal_after["reason_code"],
            "explicit_original_review_reason": review_after["reason_code"],
            "native_redisplayed": False, "continuation_writes_performed": False,
        }, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
