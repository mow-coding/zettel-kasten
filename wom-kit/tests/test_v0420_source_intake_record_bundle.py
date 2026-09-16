"""Synthetic retained data/storage only, not execution or ownership proof."""

from contextlib import ExitStack
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import test_v049_source_intake_record_exact as fixtures
from test_v0420_work_session_binding import binding_fixture
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_record_exact as intake
from wom_kit import work_session_source_intake_record_bundle as subject
from wom_kit.work_session_establishment import EstablishmentSelector


class SourceIntakeRecordBundleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SourceIntakeRecordExactTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        # Fixed metadata makes the pre-extraction 859d8d83 golden independent
        # of temp path, clock and OS stat identity. No source content claim.
        self.fixture.source_document["source_metadata"]["modified_at"] = "2026-01-01T00:00:00+00:00"
        self.fixture.source_document["source_metadata"]["local_file_identity_sha256"] = "sha256:" + "a" * 64
        self.fixture._write_document(self.fixture.source_document, self.fixture.plan_path)
        self.plan = self.fixture._plan()
        self.root = self.plan.archive_root
        self.input_bytes = self.fixture.plan_path.read_bytes()
        self.scope = self.make_scope()
        self.prepared = subject._prepare_session_source_intake_record(
            self.plan, input_plan_bytes=self.input_bytes, scope=self.scope)
        self.context = intake.approval_context(self.prepared.plan, reviewer_claim=fixtures.REVIEWER)

    def make_scope(self, **changes):
        arguments = dict(plan=self.plan, input_plan_bytes=self.input_bytes,
            work_session_binding=binding_fixture(self.plan.manifest.archive_identity_sha256, revision=7),
            task_route_ref="task_route_" + "4" * 32, actor_sha256="sha256:" + "5" * 64,
            registry_preimage_sha256="sha256:" + "6" * 64, claim_ref="claim_" + "7" * 32,
            original_establishment=EstablishmentSelector("create", "sha256:" + "8" * 64, "sha256:" + "9" * 64),
            establishment_execution_sha256="sha256:" + "a" * 64,
            establishment_receipt_sha256="sha256:" + "b" * 64)
        arguments.update(changes)
        return subject._SourceIntakeRecordSessionScope.build(**arguments)

    def path(self):
        return self.root.joinpath(*subject.PRIVATE_ROOT) / (self.context.plan_sha256[7:] + ".json")

    def save(self, held, **changes):
        values = dict(context=self.context, held=held)
        values.update(changes)
        return subject._save_original_source_intake_record_context_held(self.prepared, **values)

    def load(self, held):
        return subject._load_original_source_intake_record_context_held(
            self.root, manifest_sha256=self.context.plan_sha256, held=held)

    def assert_error(self, call, code=None):
        with self.assertRaises(subject.WorkSessionIntakeRecordBundleError) as caught:
            call()
        if code is not None:
            self.assertEqual(caught.exception.code, "work_session_intake_record_bundle_" + code)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        for private in (str(self.root), str(self.fixture.plan_path), fixtures.REVIEWER, "PRIVATE_REJECTED"):
            self.assertNotIn(private, repr(caught.exception) + str(caught.exception))

    def rehash_scope(self, document):
        document["scope"]["retained_input_sha256"] = subject._sha(document["input"])
        document["scope"]["scope_sha256"] = subject._sha({key: value for key, value in document["scope"].items()
                                                      if key != "scope_sha256"})

    def test_pre_extraction_legacy_goldens_and_pure_factory_are_exact(self):
        plan = self.plan
        self.assertEqual(plan.manifest.manifest_sha256,
            "sha256:95659c8f0c5e10238ba3bb2d3872d3c0101fa7d5a1171aa2477022726f91735e")
        self.assertEqual(plan.input_plan_bytes_sha256,
            "sha256:622428d796e21593ff48cf15619ac756dbfd346e14e47e4f5167baa2095935bd")
        self.assertEqual(plan.source_intake_plan_sha256,
            "sha256:36f67c671287ff6817936c1b74dc471c19c1e1465bee43b6592d63df7730ac98")
        self.assertEqual(intake._sha_bytes(plan.receipt_bytes),
            "sha256:a1005d87e5d507854bef5b1362ef4173d8d8a15bd66f652f0b42b28e2ebd4069")
        self.assertEqual(intake._sha_bytes(plan.source_basis_bytes),
            "sha256:43bc10356d904b965b38434d35a92d83a936a7ca98ce0b6f7ab482cbb2c47264")
        self.assertEqual(approval.exact_human_approval_context_sha256(
            intake.approval_context(plan, reviewer_claim=fixtures.REVIEWER)),
            "sha256:0bd0ba44d380f3381dfc2d554f771468388a96e1fd480557e6ebba4dad153b04")
        with patch.object(intake, "_stable_regular_bytes", side_effect=AssertionError("input read")), \
             patch.object(intake.archive_services, "archive_internal_path", side_effect=AssertionError("target read")):
            rebuilt = intake._source_intake_record_plan_from_bytes(self.root, archive_id=plan.archive_id,
                input_plan_path=plan.input_plan_path, input_plan_bytes=self.input_bytes)
        self.assertEqual(rebuilt, plan)

    def test_roundtrip_retains_one_record_and_only_the_explicit_scope_extension(self):
        expected = self.plan.manifest.operation_evidence.document()
        expected["schema"] = subject.EVIDENCE_SCHEMA
        expected["digests"]["session_scope_sha256"] = self.scope.document()["scope_sha256"]
        scoped = self.prepared.plan
        self.assertEqual(scoped.manifest.operation_evidence.document(), expected)
        self.assertEqual(scoped.manifest.items, self.plan.manifest.items)
        self.assertEqual(len(scoped.manifest.items), 1)
        self.assertEqual(scoped.receipt_bytes, self.plan.receipt_bytes)
        self.assertEqual(scoped.source_basis_bytes, self.plan.source_basis_bytes)
        self.assertEqual(scoped.input_plan_path, self.plan.input_plan_path)
        self.assertEqual(scoped.manifest.work_session_binding.revision, 7)
        self.assertIsNone(self.plan.manifest.work_session_binding)
        before = self.fixture._snapshot(self.root)
        with exact.ExactOperationWriterLock(self.root) as held:
            saved = self.save(held)
            original, mtime = self.path().read_bytes(), self.path().stat().st_mtime_ns
            with patch.object(subject.registry, "_write_private_pending", side_effect=AssertionError("rewrite")), \
                 patch.object(subject.durable, "_atomic_move_file_no_replace", side_effect=AssertionError("replace")):
                repeated, loaded = self.save(held), self.load(held)
            self.assertEqual((saved._raw, repeated._raw, loaded._raw), (original,) * 3)
            self.assertEqual(self.path().stat().st_mtime_ns, mtime)
        self.assertEqual(loaded.prepared._raw, self.prepared._raw)
        self.assertEqual(loaded.context, self.context)
        after = self.fixture._snapshot(self.root)
        for name, raw in before.items():
            self.assertEqual(after[name], raw)
        self.assertFalse(any(name.startswith("receipts/") for name in set(after) - set(before)))
        self.assertFalse((self.root / approval.CLAIMS_RELATIVE_ROOT).exists())
        self.assertEqual(subject.PRIVATE_ROOT[-1], "source-intake-record-contexts")

    def test_load_after_input_and_source_deletion_has_no_replan_target_or_authority_read(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            saved = self.save(held)
            self.fixture.plan_path.unlink()
            self.fixture.selected.unlink()
            with ExitStack() as stack:
                for owner, name in ((intake, "plan_source_intake_record"), (intake, "_stable_regular_bytes"),
                                    (intake._Verifier, "read_field"), (intake._Writer, "write_field"),
                                    (broker, "_production_key_provider"), (approval, "_claim_exact_human_approval_core"),
                                    (subject.registry.WorkSessionRegistryStore, "require_claimed_binding")):
                    stack.enter_context(patch.object(owner, name, side_effect=AssertionError(name)))
                loaded = self.load(held)
                plan, scope, raw = subject._decode_prepared(self.root, loaded.prepared._raw)
                self.assertEqual(raw, self.input_bytes)
                self.assertEqual(plan.input_plan_path, self.plan.input_plan_path)
                self.assertEqual(plan.receipt_bytes, self.plan.receipt_bytes)
                self.assertEqual(loaded._raw, saved._raw)
                detached = scope.document()
                detached["claim_ref"] = "PRIVATE_REJECTED"
                self.assertEqual(loaded.prepared.scope.document(), self.scope.document())
        for value in (self.prepared, self.scope, loaded):
            self.assertNotIn(str(self.fixture.plan_path), repr(value))
            self.assertNotIn(fixtures.REVIEWER, repr(value))

    def test_input_bytes_and_all_reconstructed_plan_fields_are_strict(self):
        for raw in (b"", b"{}", b'{"a":1,"a":2}', b'{"a":NaN}', self.input_bytes + b"\n"):
            with self.subTest(raw_size=len(raw)):
                self.assert_error(lambda: self.make_scope(input_plan_bytes=raw))
        for changes in ({"receipt_bytes": b"PRIVATE_REJECTED"}, {"source_basis_bytes": b"PRIVATE_REJECTED"},
                        {"receipt_relative_path": "receipts/sources/other.json"},
                        {"input_plan_bytes_sha256": "sha256:" + "c" * 64}, {"blockers": []},
                        {"input_plan_path": Path("relative.json")}, {"state": "preexisting_unverified"}):
            self.assert_error(lambda: self.make_scope(plan=replace(self.plan, **changes)))
        self.assert_error(lambda: self.make_scope(plan=self.prepared.plan))
        self.assert_error(lambda: subject._prepare_session_source_intake_record(
            self.plan, input_plan_bytes=self.input_bytes, scope=self.scope.document()))

    def test_bound_legacy_execute_refuses_before_native_key_replan_or_context(self):
        scoped = self.prepared.plan
        self.assertEqual(intake.approval_context(scoped, reviewer_claim=fixtures.REVIEWER), self.context)
        with ExitStack() as stack:
            spies = [stack.enter_context(patch.object(owner, name, side_effect=AssertionError(name)))
                     for owner, name in ((intake, "_execute_exact_human_approved_write"),
                                         (intake, "plan_source_intake_record"), (intake, "approval_context"),
                                         (broker, "_production_key_provider"))]
            for plan in (scoped, replace(scoped, state="preexisting_unverified",
                         blockers=("source_intake_record_completion_evidence_required",))):
                with self.assertRaises(intake.SourceIntakeRecordExactError) as caught:
                    intake.execute_source_intake_record(plan, expected_plan_sha256="malformed",
                        reviewer_claim=fixtures.REVIEWER)
                self.assertEqual(caught.exception.code, "source_intake_record_scope_context_required")
                self.assertIsNone(caught.exception.__context__)
                self.assertIsNone(caught.exception.__cause__)
            for spy in spies:
                spy.assert_not_called()

    def test_rehashed_false_manifest_evidence_and_payloads_cannot_be_reconstructed(self):
        for section, key, value in (("counts", "receipt_create_count", 2),
                                     ("digests", "receipt_bytes_sha256", "sha256:" + "d" * 64)):
            evidence = self.plan.manifest.operation_evidence.document()
            evidence[section][key] = value
            manifest = exact.ExactOperationManifest.build(operation=intake.OPERATION,
                archive_identity_sha256=self.plan.manifest.archive_identity_sha256,
                items=self.plan.manifest.items, operation_evidence=evidence)
            self.assert_error(lambda: self.make_scope(plan=replace(self.plan, manifest=manifest)))
            document = json.loads(self.prepared._raw)
            document["input"]["unbound_manifest"] = manifest.document()
            document["scope"]["unbound_manifest_sha256"] = manifest.manifest_sha256
            self.rehash_scope(document)
            evidence["schema"] = subject.EVIDENCE_SCHEMA
            evidence["digests"]["session_scope_sha256"] = document["scope"]["scope_sha256"]
            document["manifest"] = exact.ExactOperationManifest.build(operation=intake.OPERATION,
                archive_identity_sha256=manifest.archive_identity_sha256, items=manifest.items,
                operation_evidence=evidence, work_session_binding=self.prepared.plan.manifest.work_session_binding).document()
            self.assert_error(lambda: subject.PreparedSessionSourceIntakeRecord(self.root, subject._canonical(document)))
        document = json.loads(self.prepared._raw)
        document["input"]["unbound_manifest"]["item_count"] = True
        self.rehash_scope(document)
        self.assert_error(lambda: subject._decode_prepared(self.root, subject._canonical(document)))

    def test_scope_dimensions_bind_new_manifest_but_are_not_authenticated_authority(self):
        for changes in ({"task_route_ref": "task_route_" + "d" * 32}, {"actor_sha256": "sha256:" + "d" * 64},
                        {"registry_preimage_sha256": "sha256:" + "d" * 64}, {"claim_ref": "claim_" + "d" * 32},
                        {"original_establishment": EstablishmentSelector("accept", "sha256:" + "8" * 64, "sha256:" + "9" * 64)},
                        {"establishment_execution_sha256": "sha256:" + "d" * 64},
                        {"establishment_receipt_sha256": "sha256:" + "d" * 64},
                        {"work_session_binding": binding_fixture(self.plan.manifest.archive_identity_sha256, revision=8)}):
            changed = subject._prepare_session_source_intake_record(self.plan,
                input_plan_bytes=self.input_bytes, scope=self.make_scope(**changes))
            self.assertNotEqual(changed.plan.manifest.manifest_sha256, self.context.plan_sha256)
            self.assertEqual(changed.plan.receipt_bytes, self.plan.receipt_bytes)
        for changes in ({"work_session_binding": binding_fixture()}, {"actor_sha256": True},
                        {"claim_ref": "PRIVATE_REJECTED"}, {"original_establishment": {"action": "create"}}):
            self.assert_error(lambda: self.make_scope(**changes))

    def test_cross_input_path_scope_and_same_document_different_raw_are_bound(self):
        raw = self.input_bytes + b"\n"
        plan = intake._source_intake_record_plan_from_bytes(self.root, archive_id=self.plan.archive_id,
            input_plan_path=self.plan.input_plan_path, input_plan_bytes=raw)
        self.assertEqual(plan.receipt_bytes, self.plan.receipt_bytes)
        self.assertNotEqual(plan.manifest.manifest_sha256, self.plan.manifest.manifest_sha256)
        self.assert_error(lambda: subject._prepare_session_source_intake_record(plan, input_plan_bytes=raw, scope=self.scope))
        changed_path = self.plan.input_plan_path.with_name("PRIVATE_REJECTED.json")
        changed = replace(self.plan, input_plan_path=changed_path)
        self.assert_error(lambda: subject._prepare_session_source_intake_record(
            changed, input_plan_bytes=self.input_bytes, scope=self.scope))
        rebound = subject._prepare_session_source_intake_record(changed, input_plan_bytes=self.input_bytes,
            scope=self.make_scope(plan=changed))
        self.assertEqual(rebound.plan.input_plan_path, changed_path)
        self.assertNotEqual(rebound.plan.manifest.manifest_sha256, self.context.plan_sha256)

    def test_canonical_closed_codec_and_budget_reject_before_retained_allocation(self):
        for raw in (self.prepared._raw + b"\n", b'{"schema":1,"schema":2}', b'{"x":NaN}', b'[]'):
            self.assert_error(lambda: subject.PreparedSessionSourceIntakeRecord(self.root, raw))
        document = json.loads(self.prepared._raw)
        document["input"]["extra"] = "PRIVATE_REJECTED"
        self.rehash_scope(document)
        self.assert_error(lambda: subject.PreparedSessionSourceIntakeRecord(self.root, subject._canonical(document)))
        for name in ("schema", "actor_sha256", "work_session_binding"):
            scope = self.scope.document()
            scope.pop(name)
            self.assert_error(lambda: subject._SourceIntakeRecordSessionScope(subject._canonical(scope)))
        with patch.object(subject, "MAX_BUNDLE_BYTES", 8), \
             patch.object(subject.base64, "b64encode", side_effect=AssertionError("over-budget encoding")) as encode:
            self.assert_error(lambda: self.make_scope())
            encode.assert_not_called()
        with patch.object(intake, "_MAX_PLAN_BYTES", len(self.input_bytes) - 1):
            self.assert_error(lambda: self.make_scope())
        with patch.object(subject, "MAX_BUNDLE_BYTES", len(self.prepared._raw) - 1):
            self.assert_error(lambda: subject._prepare_session_source_intake_record(
                self.plan, input_plan_bytes=self.input_bytes, scope=self.scope))

    def test_context_mismatch_and_replacement_reviewer_never_overwrite(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            self.assert_error(lambda: self.save(held, context=replace(self.context,
                target_binding_sha256="sha256:" + "d" * 64)), "context_invalid")
            self.assertFalse(self.path().exists())
            saved = self.save(held)
            other = intake.approval_context(self.prepared.plan, reviewer_claim="person:replacement")
            self.assert_error(lambda: self.save(held, context=other), "changed")
            self.assertEqual(self.path().read_bytes(), saved._raw)
            document = json.loads(saved._raw)
            document["context"]["review_binding_codes"] = []
            document["bundle_sha256"] = subject._sha({key: value for key, value in document.items() if key != "bundle_sha256"})
            # Invalid native-context shape is rejected by its own constructor
            # before the factory-equivalence context_invalid comparison.
            self.assert_error(lambda: subject.ContextBoundSourceIntakeRecord(
                self.root, subject._canonical(document), self.context.plan_sha256), "invalid")

    def test_missing_released_other_archive_and_pathbearing_lock_failures(self):
        self.assert_error(lambda: self.save(None), "lock_required")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.assert_error(lambda: self.load(held), "missing")
            self.assertFalse(self.root.joinpath(*subject.PRIVATE_ROOT).exists())
        self.assert_error(lambda: self.save(held), "lock_required")
        other = self.fixture.workspace / "copied-archive"
        shutil.copytree(self.root, other)
        with exact.ExactOperationWriterLock(other) as foreign:
            self.assert_error(lambda: self.save(foreign), "lock_required")
        with exact.ExactOperationWriterLock(self.root) as held, \
             patch.object(exact.ExactOperationWriterLock, "verify_held", side_effect=OSError("PRIVATE_REJECTED")):
            self.assert_error(lambda: self.save(held), "lock_required")

    def test_unsafe_directory_and_hardlinked_control_are_not_loaded(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            parent = self.root.joinpath(*subject.PRIVATE_ROOT)
            parent.parent.mkdir(parents=True, exist_ok=True)
            parent.write_bytes(b"PRIVATE_REJECTED")
            self.assert_error(lambda: self.save(held), "path_unsafe")
            parent.unlink()
            saved = self.save(held)
            alias = self.fixture.workspace / "context-hardlink.json"
            os.link(self.path(), alias)
            self.assert_error(lambda: self.load(held))
            alias.unlink()
            self.assertEqual(self.load(held)._raw, saved._raw)

    def test_readback_change_and_lost_lock_cannot_report_loaded_original(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            saved = self.save(held)
            real = subject._read_raw
            calls = []
            def drift(root, manifest):
                raw = real(root, manifest)
                calls.append(raw)
                return raw if len(calls) == 1 else raw + b"\n"
            with patch.object(subject, "_read_raw", side_effect=drift):
                self.assert_error(lambda: self.load(held), "changed")
            self.assertEqual(self.path().read_bytes(), saved._raw)
            real_held = subject._held_root
            entered = []
            def release(root, lock):
                entered.append(True)
                if len(entered) == 2:
                    raise OSError("PRIVATE_REJECTED")
                return real_held(root, lock)
            with patch.object(subject, "_held_root", side_effect=release):
                self.assert_error(lambda: self.load(held))
            self.assertEqual(len(entered), 2)

    def test_durability_failure_and_conflicting_bytes_are_preserved_without_repair(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            saved = self.save(held)
            with patch.object(subject, "_flush_chain", side_effect=OSError("PRIVATE_REJECTED")):
                self.assert_error(lambda: self.save(held), "durability_unknown")
            self.assertEqual(self.path().read_bytes(), saved._raw)
            self.path().write_bytes(b"PRIVATE_REJECTED")
            self.assert_error(lambda: self.save(held), "changed")
            self.assertEqual(self.path().read_bytes(), b"PRIVATE_REJECTED")

    def test_new_publish_failure_and_caller_object_mutation_keep_detached_original(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(subject.durable, "_atomic_move_file_no_replace", side_effect=OSError("PRIVATE_REJECTED")):
                self.assert_error(lambda: self.save(held), "durability_unknown")
            self.assertFalse(self.path().exists())
            self.assertTrue(tuple(self.path().parent.glob(".pending_*")))
            original = self.prepared._raw
            real = subject._held_root
            mutated = []
            def mutate(root, lock):
                if not mutated:
                    mutated.append(True)
                    object.__setattr__(self.prepared, "_raw", b"PRIVATE_REJECTED")
                return real(root, lock)
            with patch.object(subject, "_held_root", side_effect=mutate):
                saved = self.save(held)
            self.assertEqual(saved.prepared._raw, original)
            self.assertEqual(saved.context, self.context)


if __name__ == "__main__":
    unittest.main()
