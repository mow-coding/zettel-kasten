"""Original task routing is digest-bound; old approved bytes stay unchanged."""

from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch

import test_v0420_work_session_operation as operation_fixture
import test_v0420_work_session_lifecycle as lifecycle_fixture
from wom_kit import exact_human_approval as approval
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_actor as actor
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_execution as execution
from wom_kit import work_session_lifecycle as lifecycle
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry


class TaskRouteBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = operation_fixture.SessionOperationTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store, self.transition = self.fixture.store, self.fixture.transition
        self.route = actor.new_task_route_ref()

    def prepare(self, route=None):
        return operation.prepare_session_decision(self.transition, task_route_ref=route)

    def context(self, prepared):
        return prepared.context(archive_id=operation_fixture.ARCHIVE_ID, reviewer_claim="person:synthetic")

    def test_none_keeps_historical_manifest_source_private_bundle_and_context_exact(self):
        prepared = operation.prepare_session_decision(self.transition)
        explicit_none = self.prepare(None)
        self.assertEqual(prepared, explicit_none)
        self.assertIsNone(prepared.task_route_ref)
        self.assertIsNone(prepared.task_route_binding_sha256)
        legacy_source = registry._canonical({
            "schema": "wom-kit/work-session-transition-source/v1",
            "previous_generation_sha256": self.transition.before_sha256,
            "transition_sha256": self.transition.plan_sha256,
            "action": self.transition.action,
        })
        self.assertEqual(prepared.source_bytes, legacy_source)
        legacy_manifest = exact.ExactOperationManifest.build(
            operation="work_session", archive_identity_sha256=self.store.archive_identity_sha256,
            items=prepared.manifest.items,
            work_session_binding=self.transition.after.binding(self.transition.result_refs[-1]),
            operation_evidence=exact.ExactOperationEvidence(
                schema="wom-kit/work-session-decision-evidence/v1", counts=(("generation_count", 1),),
                digests=(("transition_sha256", self.transition.plan_sha256),),
            ),
        )
        self.assertEqual(registry._canonical(prepared.manifest.document()), registry._canonical(legacy_manifest.document()))
        legacy_basis = {
            "schema": bundle.BUNDLE_SCHEMA,
            "archive_identity_sha256": self.store.archive_identity_sha256,
            "transition": {
                "action": self.transition.action, "before_sha256": self.transition.before_sha256,
                "after": self.transition.after._document, "result_refs": list(self.transition.result_refs),
                "plan_sha256": self.transition.plan_sha256, "request": self.transition._request,
                "generated_refs": list(self.transition._generated_refs),
            },
            "source_ascii": legacy_source.decode("ascii"), "manifest": legacy_manifest.document(),
        }
        legacy_document = {**legacy_basis, "bundle_sha256": bundle._sha(bundle._canonical(legacy_basis))}
        self.assertEqual(bundle._canonical(bundle._document(prepared)), bundle._canonical(legacy_document))
        self.assertEqual(self.context(prepared), self.fixture.context)
        self.assertEqual(self.context(explicit_none), self.fixture.context)
        legacy_context_basis = {
            "schema": bundle.CONTEXT_BUNDLE_SCHEMA, "prepared": legacy_document,
            "context": bundle._context_document(self.fixture.context),
            "context_sha256": approval.exact_human_approval_context_sha256(self.fixture.context),
        }
        expected = {**legacy_context_basis, "bundle_sha256": bundle._sha(bundle._canonical(legacy_context_basis))}
        self.assertEqual(bundle._canonical(bundle._context_bound_document(prepared, self.context(prepared))),
                         bundle._canonical(expected))

    def test_route_changes_original_approval_digest_but_not_registry_effect_or_source_bytes(self):
        old = self.prepare()
        first, second = self.prepare(self.route), self.prepare(actor.new_task_route_ref())
        for prepared in (first, second):
            prepared.validate()
            self.assertEqual(prepared.source_bytes, old.source_bytes)
            self.assertEqual(prepared.manifest.items, old.manifest.items)
            self.assertEqual(prepared.manifest.work_session_binding, old.manifest.work_session_binding)
            self.assertEqual(dict(prepared.manifest.operation_evidence.digests)["task_route_binding_sha256"],
                             prepared.task_route_binding_sha256)
            self.assertNotIn(prepared.task_route_ref, json.dumps(prepared.manifest.document()))
            self.assertNotIn(prepared.task_route_ref, repr(prepared))
        self.assertEqual(len({item.manifest.manifest_sha256 for item in (old, first, second)}), 3)
        self.assertEqual(len({approval.exact_human_approval_context_sha256(self.context(item))
                              for item in (old, first, second)}), 3)
        changed_app = registry._new_ref("client_app")
        changed_archive = "sha256:" + "f" * 64
        base = dict(archive_identity_sha256=self.store.archive_identity_sha256,
                    client_app_ref=self.fixture.app, task_route_ref=self.route)
        original = operation.task_route_binding_sha256(**base)
        self.assertNotEqual(original, operation.task_route_binding_sha256(**{**base, "client_app_ref": changed_app}))
        self.assertNotEqual(original, operation.task_route_binding_sha256(**{**base, "archive_identity_sha256": changed_archive}))

    def test_route_shape_and_mutated_prepared_values_are_refused(self):
        for invalid in (True, 1, "private route marker", {}, [], self.fixture.app):
            with self.subTest(kind=type(invalid).__name__):
                with self.assertRaises(registry.WorkSessionRegistryError) as caught:
                    self.prepare(invalid)
                self.assertEqual(str(caught.exception), "work_session_transition_invalid")
        prepared = self.prepare(self.route)
        for altered in (replace(prepared, task_route_ref=None),
                        replace(prepared, task_route_ref=actor.new_task_route_ref()),
                        replace(self.prepare(), task_route_ref=self.route)):
            with self.assertRaises(registry.WorkSessionRegistryError):
                altered.validate()

    def test_original_private_bundle_roundtrip_and_route_tamper_or_retrofit_refusal(self):
        prepared = self.prepare(self.route)
        context = self.context(prepared)
        with exact.ExactOperationWriterLock(self.fixture.root) as held:
            bundle.save_context_bound_session_decision(self.store, prepared, context=context, held_lock=held)
        restored = bundle.load_context_bound_session_decision(self.store, manifest_sha256=prepared.manifest.manifest_sha256)
        self.assertEqual((restored.prepared, restored.context), (prepared, context))
        document = bundle._document(prepared)
        variants = []
        for route in (None, True, actor.new_task_route_ref()):
            variants.append({**deepcopy(document), "task_route_ref": route})
        missing = deepcopy(document)
        del missing["task_route_ref"]
        variants.append(missing)
        variants.append({**deepcopy(document), "unexpected_route": self.route})
        legacy = bundle._document(self.prepare())
        variants.append({**legacy, "task_route_ref": self.route})
        for row in variants:
            row["bundle_sha256"] = bundle._sha(bundle._canonical({k: v for k, v in row.items() if k != "bundle_sha256"}))
            with self.assertRaises(bundle.WorkSessionBundleError):
                bundle._decode(self.store, bundle._canonical(row), row["manifest"]["manifest_sha256"])
        other = self.prepare(actor.new_task_route_ref())
        wrong_context = bundle._context_bound_document(other, context)
        with self.assertRaises(bundle.WorkSessionBundleError):
            bundle._decode_context_bound(self.store, bundle._canonical(wrong_context), other.manifest.manifest_sha256)


class OriginalTaskRouteJourneyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = lifecycle_fixture.TaskLifecycleTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_copied_pending_pointer_cannot_resume_other_route_but_original_route_can(self):
        t = self.fixture
        t.cut_before_writer()
        original = t.routing.read().document()
        other_route = actor.new_task_route_ref()
        other = actor.WorkSessionActorStore(t.store, client_app_ref=t.app, task_route_ref=other_route)
        with exact.ExactOperationWriterLock(t.root) as held:
            other.save(expected_sha256=None, held_lock=held,
                       pending_manifest_sha256=original["pending_manifest_sha256"],
                       pending_context_sha256=original["pending_context_sha256"])
        before = t.domain_files()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("wrong route wrote")) as writer:
            t.reject(lambda: t.resume(task_route_ref=other_route))
        writer.assert_not_called()
        self.assertEqual(t.domain_files(), before)
        result = t.resume()
        self.assertTrue(result["ok"])
        self.assertEqual(t.native.calls, 1)

    def test_copied_completed_pointer_cannot_alias_other_route(self):
        t = self.fixture
        result = t.create()
        original = t.routing.read().document()
        other_route = actor.new_task_route_ref()
        other = actor.WorkSessionActorStore(t.store, client_app_ref=t.app, task_route_ref=other_route)
        with exact.ExactOperationWriterLock(t.root) as held:
            other.save(expected_sha256=None, held_lock=held,
                       last_completed_operation=actor.CompletedOperationSelector.from_document(original["last_completed_operation"]))
        before = t.domain_files()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("wrong route wrote")) as writer:
            t.reject(lambda: t.resume(task_route_ref=other_route))
        writer.assert_not_called()
        self.assertEqual(t.domain_files(), before)
        self.assertEqual(t.resume()["receipt_sha256"], result["receipt_sha256"])

    def test_legacy_approved_bundle_stays_resumable_only_by_original_core_without_rebinding(self):
        t = self.fixture
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=OSError("synthetic output loss")):
            with self.assertRaises(Exception):
                execution._execute_session_decision_core(
                    t.root, action="create", client_app_ref=t.app, label="Synthetic old task",
                    reviewer_claim="person:synthetic-legacy", native=t.native, key_provider=t.key,
                )
        paths = list(t.root.joinpath(*bundle.PRIVATE_ROOT).glob("*.json"))
        self.assertEqual(len(paths), 1)
        old_bytes = paths[0].read_bytes()
        manifest_sha = "sha256:" + paths[0].stem
        old = bundle.load_context_bound_session_decision(t.store, manifest_sha256=manifest_sha)
        self.assertIsNone(old.prepared.task_route_ref)
        with exact.ExactOperationWriterLock(t.root) as held:
            t.routing.save(expected_sha256=None, held_lock=held, pending_manifest_sha256=manifest_sha,
                           pending_context_sha256=approval.exact_human_approval_context_sha256(old.context))
        before = t.domain_files()
        with patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("retrofit wrote")) as writer:
            t.reject(t.resume)
        writer.assert_not_called()
        self.assertEqual(t.domain_files(), before)
        result = execution._resume_session_decision_core(t.root, manifest_sha256=manifest_sha, key_provider=t.key)
        self.assertTrue(result["ok"])
        self.assertTrue(result["independent_post_verification"])
        self.assertEqual(paths[0].read_bytes(), old_bytes)
        self.assertEqual(t.native.calls, 1)


if __name__ == "__main__":
    unittest.main()
