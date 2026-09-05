"""Synthetic retained-data/storage tests; no approval/owner/write workflow."""

from dataclasses import replace
import inspect
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_v0410_source_intake_batch_exact as fixtures
from test_v0420_work_session_binding import binding_fixture
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_batch_exact as intake
from wom_kit import work_session_source_intake_bundle as subject
from wom_kit.work_session_establishment import EstablishmentSelector


def measure_source_intake_bundle_scale():
    """Explicit one-off 1000-item metadata measurement, not a speed assertion.

    Deliberately not an auto-discovered test: measure cardinality using the
    real existing synthetic planner without adding a costly CI speed gate.
    Source bodies are small varied fixture bytes, not a deep-byte workload.
    """
    fixture = fixtures.SourceIntakeBatchExactTests(methodName="runTest")
    fixture.setUp()
    try:
        fixture._write_request(1000)
        started = time.perf_counter()
        plan = intake.plan_source_intake_batch(fixture.root, fixture.request_path)
        plan_seconds = time.perf_counter() - started
        if not plan.approveable or len(plan.items) != 1000:
            raise AssertionError("synthetic scale plan failed")
        raw = fixture.request_path.read_bytes()
        measurements = {"item_count": len(plan.items), "exact_target_count": len(plan.manifest.items),
            "source_bytes": sum(item.source_size_bytes for item in plan.items),
            "request_bytes": len(raw), "plan_seconds": plan_seconds}
        with patch.object(subject, "_decode_input", wraps=subject._decode_input) as decodes:
            started = time.perf_counter()
            scope = subject._SourceIntakeBatchSessionScope.build(plan=plan, request_bytes=raw,
                work_session_binding=binding_fixture(plan.manifest.archive_identity_sha256, revision=7),
                task_route_ref="task_route_" + "4" * 32, actor_sha256="sha256:" + "5" * 64,
                registry_preimage_sha256="sha256:" + "6" * 64, claim_ref="claim_" + "7" * 32,
                original_establishment=EstablishmentSelector("create", "sha256:" + "8" * 64, "sha256:" + "9" * 64),
                establishment_execution_sha256="sha256:" + "a" * 64,
                establishment_receipt_sha256="sha256:" + "b" * 64)
            measurements["scope_seconds"] = time.perf_counter() - started
            started = time.perf_counter()
            prepared = subject._prepare_session_source_intake_batch(plan, request_bytes=raw, scope=scope)
            measurements["prepared_seconds"] = time.perf_counter() - started
            measurements["retained_prepared_bytes"] = len(prepared._raw)
            started = time.perf_counter()
            context = intake.approval_context(prepared.plan, reviewer_claim=fixtures.REVIEWER)
            measurements["context_factory_seconds"] = time.perf_counter() - started
            with exact.ExactOperationWriterLock(plan.archive_root) as held:
                started = time.perf_counter()
                saved = subject._save_original_source_intake_context_held(prepared, context=context, held=held)
                measurements["save_seconds"] = time.perf_counter() - started
                measurements["retained_context_bytes"] = len(saved._raw)
                started = time.perf_counter()
                loaded = subject._load_original_source_intake_context_held(plan.archive_root,
                    manifest_sha256=context.plan_sha256, held=held)
                measurements["load_seconds"] = time.perf_counter() - started
            if loaded._raw != saved._raw:
                raise AssertionError("synthetic scale readback failed")
            measurements["complete_input_decode_calls"] = decodes.call_count
        return {"ok": True, "metadata_cardinality_measurement_only": True,
                "installed_runtime_verified": False, "large_source_byte_workload_verified": False,
                **measurements}
    finally:
        fixture.tearDown()


class SourceIntakeBundleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SourceIntakeBatchExactTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.sources = self.fixture._write_request(2)
        self.root = self.fixture.root
        self.plan = intake.plan_source_intake_batch(self.root, self.fixture.request_path)
        # The actual planner resolves Windows short TEMP aliases. Preserve
        # its canonical original spelling; do not compare a fixture alias.
        self.root = self.plan.archive_root
        self.original_receipts = self.receipts()
        self.raw_request = self.fixture.request_path.read_bytes()
        self.scope = self.make_scope()
        self.prepared = subject._prepare_session_source_intake_batch(
            self.plan, request_bytes=self.raw_request, scope=self.scope)
        self.context = intake.approval_context(self.prepared.plan, reviewer_claim=fixtures.REVIEWER)

    def make_scope(self, **changes):
        arguments = dict(plan=self.plan, request_bytes=self.raw_request,
            work_session_binding=binding_fixture(self.plan.manifest.archive_identity_sha256, revision=7),
            task_route_ref="task_route_" + "4" * 32, actor_sha256="sha256:" + "5" * 64,
            registry_preimage_sha256="sha256:" + "6" * 64, claim_ref="claim_" + "7" * 32,
            original_establishment=EstablishmentSelector("create", "sha256:" + "8" * 64, "sha256:" + "9" * 64),
            establishment_execution_sha256="sha256:" + "a" * 64,
            establishment_receipt_sha256="sha256:" + "b" * 64)
        arguments.update(changes)
        return subject._SourceIntakeBatchSessionScope.build(**arguments)

    def path(self):
        return self.root.joinpath(*subject.PRIVATE_ROOT) / (self.prepared.plan.manifest.manifest_sha256[7:] + ".json")

    def receipts(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in (self.root / "receipts").rglob("*") if path.is_file()}

    def save(self, held, **changes):
        values = dict(context=self.context, held=held)
        values.update(changes)
        return subject._save_original_source_intake_context_held(self.prepared, **values)

    def load(self, held):
        return subject._load_original_source_intake_context_held(self.root,
            manifest_sha256=self.prepared.plan.manifest.manifest_sha256, held=held)

    def assert_error(self, call, code=None):
        with self.assertRaises(subject.WorkSessionIntakeBundleError) as caught:
            call()
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__cause__)
        self.assertIsNone(caught.exception.__context__)
        for marker in (str(self.root), fixtures.REVIEWER, "SYNTHETIC_PRIVATE"):
            self.assertNotIn(marker, str(caught.exception) + repr(caught.exception))

    def test_roundtrip_retains_full_legacy_evidence_and_only_new_scope_extension(self):
        original = self.plan.manifest.document()
        scoped = self.prepared.plan.manifest
        self.assertEqual(self.plan.manifest.document(), original)
        self.assertIsNone(self.plan.manifest.work_session_binding)
        self.assertEqual(scoped.items, self.plan.manifest.items)
        expected = self.plan.manifest.operation_evidence.document()
        expected["schema"] = subject.EVIDENCE_SCHEMA
        expected["digests"]["session_scope_sha256"] = self.scope.document()["scope_sha256"]
        self.assertEqual(scoped.operation_evidence.document(), expected)
        self.assertEqual(scoped.work_session_binding.revision, 7)
        self.assertNotEqual(scoped.manifest_sha256, self.plan.manifest.manifest_sha256)
        self.assertEqual(self.prepared.plan.request_path, self.plan.request_path)
        self.assertEqual(self.prepared.plan.items, self.plan.items)
        with exact.ExactOperationWriterLock(self.root) as held:
            saved = self.save(held)
            original_bytes, original_mtime = self.path().read_bytes(), self.path().stat().st_mtime_ns
            with patch.object(subject.registry, "_write_private_pending", side_effect=AssertionError("rewrite")), \
                 patch.object(subject.durable, "_atomic_move_file_no_replace", side_effect=AssertionError("replace")):
                repeated = self.save(held)
                loaded = self.load(held)
            self.assertEqual(saved._raw, repeated._raw)
            self.assertEqual(saved._raw, loaded._raw)
            self.assertEqual(self.path().read_bytes(), original_bytes)
            self.assertEqual(self.path().stat().st_mtime_ns, original_mtime)
        self.assertEqual(loaded.prepared._raw, self.prepared._raw)
        self.assertEqual(loaded.context, self.context)
        self.assertFalse((self.root / approval.CLAIMS_RELATIVE_ROOT).exists())
        self.assertEqual(self.receipts(), self.original_receipts)

    def test_load_original_rows_after_request_and_sources_removed_performs_no_replan_or_authentication(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            saved = self.save(held)
            self.fixture.request_path.unlink()
            for source in self.sources:
                source.unlink()
            with patch.object(intake, "plan_source_intake_batch", side_effect=AssertionError("replan")), \
                 patch.object(intake, "_stable_request_bytes", side_effect=AssertionError("request read")), \
                 patch.object(intake, "_stable_source_digest", side_effect=AssertionError("source read")), \
                 patch.object(intake, "_build_item", side_effect=AssertionError("source planner")), \
                 patch.object(broker, "_production_key_provider", side_effect=AssertionError("key")), \
                 patch.object(approval, "_claim_exact_human_approval_core", side_effect=AssertionError("claim")), \
                 patch.object(subject.registry.WorkSessionRegistryStore, "require_claimed_binding", side_effect=AssertionError("owner")):
                loaded = self.load(held)
                self.assertEqual(loaded._raw, saved._raw)
                self.assertEqual(loaded.prepared.plan.request_path, self.plan.request_path)
                self.assertEqual(loaded.prepared.plan.request_bytes_sha256, intake._sha_bytes(self.raw_request))
                rows = loaded.prepared.request_items()
                self.assertEqual(list(rows.values()), json.loads(self.raw_request)["items"])
                rows[next(iter(rows))]["local_path"] = "SYNTHETIC_PRIVATE_REPLACEMENT"
                self.assertEqual(list(loaded.prepared.request_items().values()), json.loads(self.raw_request)["items"])
        self.assertEqual(self.receipts(), self.original_receipts)

    def test_absolute_caller_spelling_is_retained_without_resolving_missing_source(self):
        request = json.loads(self.raw_request)
        for row, source in zip(request["items"], self.sources):
            row["local_path"] = str(source)
        raw = json.dumps(request).encode("utf-8")
        self.fixture.request_path.write_bytes(raw)
        plan = intake.plan_source_intake_batch(self.root, self.fixture.request_path)
        self.assertTrue(plan.approveable)
        prepared = subject._prepare_session_source_intake_batch(plan, request_bytes=raw,
            scope=self.make_scope(plan=plan, request_bytes=raw))
        self.fixture.request_path.unlink()
        for source in self.sources:
            source.unlink()
        self.assertEqual(prepared.plan.items, plan.items)
        self.assertEqual(list(prepared.request_items().values()), request["items"])

    def test_inconsistent_full_legacy_evidence_is_rejected_not_hidden_by_scope_digest(self):
        for section, name, value in (("counts", "source_item_count", 999),
                                     ("digests", "item_source_set_sha256", "sha256:" + "e" * 64)):
            evidence = self.plan.manifest.operation_evidence.document()
            evidence[section][name] = value
            manifest = exact.ExactOperationManifest.build(operation=self.plan.manifest.operation,
                archive_identity_sha256=self.plan.manifest.archive_identity_sha256,
                items=self.plan.manifest.items, operation_evidence=evidence)
            self.assert_error(lambda: self.make_scope(plan=replace(self.plan, manifest=manifest)))
            # Rehash every nested convenience layer, including the scoped
            # manifest. Integrity hashes alone cannot excuse a false count or
            # source/receipt digest inside the retained original evidence.
            document = json.loads(self.prepared._raw)
            document["input"]["unbound_manifest"] = manifest.document()
            document["scope"]["unbound_manifest_sha256"] = manifest.manifest_sha256
            document["scope"]["retained_input_sha256"] = subject._sha(document["input"])
            document["scope"]["scope_sha256"] = subject._sha({
                key: value for key, value in document["scope"].items() if key != "scope_sha256"})
            evidence["schema"] = subject.EVIDENCE_SCHEMA
            evidence["digests"]["session_scope_sha256"] = document["scope"]["scope_sha256"]
            document["manifest"] = exact.ExactOperationManifest.build(operation=manifest.operation,
                archive_identity_sha256=manifest.archive_identity_sha256, items=manifest.items,
                operation_evidence=evidence, work_session_binding=self.prepared.plan.manifest.work_session_binding).document()
            self.assert_error(lambda: subject.PreparedSessionSourceIntakeBatch(self.root, subject._canonical(document)))

    def test_scope_dimensions_change_new_manifest_without_rewriting_original_binding(self):
        for changes in ({"task_route_ref": "task_route_" + "d" * 32},
                        {"actor_sha256": "sha256:" + "d" * 64},
                        {"registry_preimage_sha256": "sha256:" + "d" * 64},
                        {"claim_ref": "claim_" + "d" * 32},
                        {"original_establishment": EstablishmentSelector("accept", "sha256:" + "8" * 64, "sha256:" + "9" * 64)},
                        {"establishment_execution_sha256": "sha256:" + "d" * 64},
                        {"establishment_receipt_sha256": "sha256:" + "d" * 64}):
            changed = subject._prepare_session_source_intake_batch(self.plan,
                request_bytes=self.raw_request, scope=self.make_scope(**changes))
            self.assertNotEqual(changed.plan.manifest.manifest_sha256, self.prepared.plan.manifest.manifest_sha256)
            self.assertEqual(changed.plan.manifest.work_session_binding.revision, 7)
        self.assert_error(lambda: self.make_scope(work_session_binding=binding_fixture()))
        self.assert_error(lambda: self.make_scope(original_establishment={"action": "create"}))
        self.assert_error(lambda: self.make_scope(actor_sha256=True))

    def test_legacy_bound_input_and_untyped_scope_never_open_execution(self):
        self.assert_error(lambda: subject._prepare_session_source_intake_batch(
            self.plan, request_bytes=self.raw_request, scope=self.scope.document()))
        self.assert_error(lambda: self.make_scope(plan=self.prepared.plan))
        with patch.object(intake, "_execute_exact_human_approved_write") as native:
            with self.assertRaises(intake.SourceIntakeBatchExactError) as caught:
                intake.execute_source_intake_batch(self.prepared.plan, reviewer_claim=fixtures.REVIEWER)
            self.assertEqual(caught.exception.code, "source_intake_batch_scope_context_required")
            native.assert_not_called()

    def test_request_raw_and_prepared_payload_tamper_fail_even_with_recomputed_input_digest(self):
        self.assert_error(lambda: self.make_scope(request_bytes=self.raw_request + b"\n"))
        changed_item = replace(self.plan.items[0], receipt_bytes=b"{\"SYNTHETIC_PRIVATE\":true}")
        altered = replace(self.plan, items=(changed_item, *self.plan.items[1:]))
        self.assert_error(lambda: self.make_scope(plan=altered))
        for mutate in (
            lambda data: data["input"]["items"][0].__setitem__("source_bytes_sha256", "sha256:" + "e" * 64),
            lambda data: data["input"]["items"][0].__setitem__("capture_staged_path", "different.bin"),
            lambda data: data["input"]["prepared_capture_request"].__setitem__("request_bytes", subject._encoded(b"{}\n")),
            lambda data: data["input"].__setitem__("request_document_sha256", "sha256:" + "e" * 64),
        ):
            data = json.loads(self.prepared._raw)
            mutate(data)
            data["scope"]["retained_input_sha256"] = subject._sha(data["input"])
            data["scope"]["scope_sha256"] = subject._sha({k: v for k, v in data["scope"].items() if k != "scope_sha256"})
            self.assert_error(lambda: subject.PreparedSessionSourceIntakeBatch(self.root, subject._canonical(data)))

    def test_total_budget_is_checked_before_base64_and_original_legacy_plan_is_unchanged(self):
        original = self.plan.manifest.document()
        large = b"x" * intake._MAX_RECEIPT_BYTES
        changed = replace(self.plan, items=tuple(replace(item, receipt_bytes=large, source_basis_bytes=large)
                                                for item in self.plan.items))
        with patch.object(subject, "_encoded", side_effect=AssertionError("encoded over-budget inputs")) as encoded:
            self.assert_error(lambda: self.make_scope(plan=changed))
            encoded.assert_not_called()
        self.assertEqual(self.plan.manifest.document(), original)
        self.assertEqual(subject.MAX_BUNDLE_BYTES, 32 * 1024 * 1024)
        with patch.object(subject, "MAX_BUNDLE_BYTES", len(self.prepared._raw) - 1):
            self.assert_error(lambda: subject._prepare_session_source_intake_batch(
                self.plan, request_bytes=self.raw_request, scope=self.scope))

    def test_context_mismatch_and_replacement_reviewer_cannot_overwrite_original(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            for context in (replace(self.context, plan_sha256="sha256:" + "e" * 64),
                            replace(self.context, target_binding_sha256="sha256:" + "e" * 64),
                            replace(self.context, warning_codes=("changed",))):
                self.assert_error(lambda: self.save(held, context=context), "work_session_intake_bundle_context_invalid")
                self.assertFalse(self.path().exists())
            saved = self.save(held)
            replacement = intake.approval_context(self.prepared.plan, reviewer_claim="person:replacement-reviewer")
            self.assert_error(lambda: self.save(held, context=replacement), "work_session_intake_bundle_changed")
            self.assertEqual(self.path().read_bytes(), saved._raw)

    def test_corrupt_duplicate_noncanonical_original_is_preserved_and_never_repaired(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            saved = self.save(held)
            invalid = (b"{", b" " + saved._raw,
                saved._raw[:-1] + b',"schema":' + json.dumps(subject.CONTEXT_SCHEMA).encode("ascii") + b"}")
            for raw in invalid:
                self.path().write_bytes(raw)
                self.assert_error(lambda: self.load(held))
                self.assert_error(lambda: self.save(held))
                self.assertEqual(self.path().read_bytes(), raw)

    def test_real_foreign_released_lock_and_cross_archive_copy_refuse(self):
        self.assert_error(lambda: self.save(object()), "work_session_intake_bundle_lock_required")
        other = self.fixture.workspace / "other-archive"
        other.mkdir()
        (other / "archive.yml").write_text("archive_id: archive:personal:other-synthetic\n", encoding="utf-8")
        with exact.ExactOperationWriterLock(other) as foreign:
            self.assert_error(lambda: self.save(foreign), "work_session_intake_bundle_lock_required")
        with exact.ExactOperationWriterLock(self.root) as held:
            saved = self.save(held)
        self.assert_error(lambda: self.load(held), "work_session_intake_bundle_lock_required")
        target = other.joinpath(*subject.PRIVATE_ROOT) / self.path().name
        target.parent.mkdir(parents=True)
        target.write_bytes(saved._raw)
        with exact.ExactOperationWriterLock(other) as foreign:
            self.assert_error(lambda: subject._load_original_source_intake_context_held(other,
                manifest_sha256=self.prepared.plan.manifest.manifest_sha256, held=foreign))
        self.assertEqual(target.read_bytes(), saved._raw)

    def test_reparse_parent_and_existing_directory_target_refuse_without_replacement(self):
        real_lstat = os.lstat
        with exact.ExactOperationWriterLock(self.root) as held:
            self.save(held)
            raw = self.path().read_bytes()
            def reparse(path, *args, **kwargs):
                info = real_lstat(path, *args, **kwargs)
                if Path(path) == self.path().parent:
                    return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
                return info
            with patch.object(subject.os, "lstat", side_effect=reparse):
                self.assert_error(lambda: self.load(held), "work_session_intake_bundle_path_unsafe")
            self.assertEqual(self.path().read_bytes(), raw)
            self.path().unlink()
            self.path().mkdir()
            self.assert_error(lambda: self.save(held))
            self.assertTrue(self.path().is_dir())

    def test_first_directory_flush_and_pre_rename_failure_never_report_publication(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(subject.durable, "_require_directory_durable", side_effect=OSError("SYNTHETIC_PRIVATE_FLUSH")):
                self.assert_error(lambda: self.save(held), "work_session_intake_bundle_durability_unknown")
            self.assertFalse(self.path().exists())
            with patch.object(subject.durable, "_atomic_move_file_no_replace", side_effect=OSError("SYNTHETIC_PRIVATE_MOVE")):
                self.assert_error(lambda: self.save(held), "work_session_intake_bundle_durability_unknown")
            self.assertFalse(self.path().exists())
            pending = list(self.path().parent.glob(".pending_*"))
            self.assertEqual(len(pending), 1)
            raw = pending[0].read_bytes()
            self.assert_error(lambda: self.load(held), "work_session_intake_bundle_missing")
            self.assertEqual(pending[0].read_bytes(), raw)

    def test_post_rename_cut_repeats_durably_without_rewrite_and_checks_after_flush(self):
        real_flush = subject.durable._require_directory_durable
        def cut(path):
            if self.path().exists():
                raise OSError("SYNTHETIC_PRIVATE_POST_RENAME")
            return real_flush(path)
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(subject.durable, "_require_directory_durable", side_effect=cut):
                self.assert_error(lambda: self.save(held), "work_session_intake_bundle_durability_unknown")
            raw = self.path().read_bytes()
            with patch.object(subject.registry, "_write_private_pending", side_effect=AssertionError("rewrite")):
                self.assertEqual(self.save(held)._raw, raw)
            def mutate(path):
                real_flush(path)
                self.path().write_bytes(b"{")
            with patch.object(subject.durable, "_require_directory_durable", side_effect=mutate):
                self.assert_error(lambda: self.save(held))
            self.assertEqual(self.path().read_bytes(), b"{")

    def test_parent_identity_drift_and_pending_readback_fail_preserving_evidence(self):
        real_write = subject.registry._write_private_pending
        def change_pending(path, raw, **kwargs):
            real_write(path, raw, **kwargs)
            path.write_bytes(raw + b" ")
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(subject.durable, "_assert_named_reservation_directory_identity",
                              side_effect=OSError("SYNTHETIC_PRIVATE_IDENTITY")):
                self.assert_error(lambda: self.save(held), "work_session_intake_bundle_durability_unknown")
            self.assertFalse(self.path().exists())
            with patch.object(subject.registry, "_write_private_pending", side_effect=change_pending):
                self.assert_error(lambda: self.save(held), "work_session_intake_bundle_changed")
            self.assertFalse(self.path().exists())
            self.assertEqual(len(list(self.path().parent.glob(".pending_*"))), 1)

    def test_detached_views_and_save_before_callback_do_not_retain_caller_mutations(self):
        original = self.prepared._raw
        view = self.prepared.plan
        object.__setattr__(view.items[0], "receipt_bytes", b"SYNTHETIC_PRIVATE_MUTATION")
        self.assertEqual(self.prepared.plan.items, self.plan.items)
        real_held = subject._held_root
        def mutate(root, held):
            object.__setattr__(self.prepared, "_raw", b"{")
            return real_held(root, held)
        manifest_sha = self.prepared.plan.manifest.manifest_sha256
        with exact.ExactOperationWriterLock(self.root) as held, patch.object(subject, "_held_root", side_effect=mutate):
            saved = self.save(held)
        self.assertEqual(saved.prepared._raw, original)
        self.assertEqual(saved.prepared.plan.manifest.manifest_sha256, manifest_sha)

    def test_errors_reprs_and_interfaces_do_not_supply_authority(self):
        class PrivateString(str):
            def __hash__(self):
                raise AssertionError("SYNTHETIC_PRIVATE_HASH")
        for value in ([], {}, None, True, PrivateString("work_session_intake_bundle_missing"), "SYNTHETIC_PRIVATE"):
            self.assertEqual(str(subject.WorkSessionIntakeBundleError(value)), "work_session_intake_bundle_invalid")
        for function in (subject._save_original_source_intake_context_held, subject._load_original_source_intake_context_held):
            self.assertTrue({"approve", "approval_id", "key_provider", "native", "claim", "completed"}.isdisjoint(
                inspect.signature(function).parameters))
        for value in (self.scope, self.prepared):
            for marker in (str(self.root), self.plan.items[0].capture_staged_path, fixtures.REVIEWER):
                self.assertNotIn(marker, repr(value))
        subclass = type("UntrustedScope", (subject._SourceIntakeBatchSessionScope,), {})
        self.assert_error(lambda: subject._prepare_session_source_intake_batch(self.plan,
            request_bytes=self.raw_request, scope=object.__new__(subclass)))
        subclass = type("UntrustedPrepared", (subject.PreparedSessionSourceIntakeBatch,), {})
        self.assert_error(lambda: subject._save_original_source_intake_context_held(object.__new__(subclass),
            context=self.context, held=None))


if __name__ == "__main__":
    unittest.main()
