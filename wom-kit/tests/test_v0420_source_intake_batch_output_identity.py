"""Scoped output identity only; real temporary files, claims and retained history."""

from contextlib import contextmanager
import os
import unittest
from unittest.mock import patch

import test_v0420_work_session_source_intake_bundle as bundle_fixture
import test_v0420_source_intake_completion_reader as completion_fixture
from wom_kit import archive_services
from wom_kit import exact_human_approval as approval
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_batch_exact as intake
from wom_kit import work_session_bundle as controls
from wom_kit import work_session_source_intake_completion as completion


def _targets(plan):
    item = plan.items[0]
    artifact = plan.prepared_capture_request
    return (
        (intake.TARGET_KIND, item.receipt_relative_path, intake.FIELD_REF, item.receipt_bytes),
        (intake.CAPTURE_REQUEST_TARGET_KIND, artifact.relative_path,
         intake.CAPTURE_REQUEST_FIELD_REF, artifact.request_bytes),
    )


def _read(plan, row, heartbeat=lambda: None):
    kind, relative, field, _raw = row
    return intake._Verifier(plan).read_field(target_kind=kind, target_ref=relative,
                                           field_ref=field, heartbeat=heartbeat)


class SourceIntakeBatchOutputIdentityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = bundle_fixture.SourceIntakeBundleTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.legacy = self.fixture.plan
        self.scoped = self.fixture.prepared.plan
        self.root = self.scoped.archive_root
        for item in self.scoped.items:
            path = self.root / item.receipt_relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(item.receipt_bytes)
        artifact = self.scoped.prepared_capture_request
        path = self.root / artifact.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(artifact.request_bytes)

    def refuse(self, call):
        with self.assertRaises(intake.SourceIntakeBatchExactError) as caught:
            call()
        self.assertEqual(caught.exception.code, "source_intake_batch_target_collision")
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn(str(self.root), repr(caught.exception))

    def test_real_hardlinks_refuse_scoped_postimage_and_preserve_unbound_behavior(self):
        documents = (self.legacy.manifest.document(), self.scoped.manifest.document())
        context = intake.approval_context(self.legacy, reviewer_claim="person:fixture")
        for index, row in enumerate(_targets(self.scoped)):
            with self.subTest(target_kind=row[0]):
                path = self.root / row[1]
                alias = self.fixture.fixture.workspace / ("output-alias-" + str(index))
                os.link(path, alias)
                try:
                    self.assertEqual(os.lstat(path).st_nlink, 2)
                    self.assertEqual(path.read_bytes(), row[3])
                    self.assertEqual(_read(self.legacy, row), row[3])
                    self.assertTrue(exact.verify_exact_operation(self.legacy.manifest,
                        verifier=intake._Verifier(self.legacy), state="post")["all_match"])
                    self.refuse(lambda: _read(self.scoped, row))
                    with self.assertRaises(exact.ExactOperationManifestError):
                        exact.verify_exact_operation(self.scoped.manifest,
                            verifier=intake._Verifier(self.scoped), state="post")
                    self.assertEqual(alias.read_bytes(), row[3])
                finally:
                    alias.unlink()
                self.assertEqual(_read(self.scoped, row), row[3])
        self.assertEqual(documents, (self.legacy.manifest.document(), self.scoped.manifest.document()))
        self.assertEqual(context, intake.approval_context(self.legacy, reviewer_claim="person:fixture"))

    def test_plain_and_absent_outputs_keep_heartbeat_and_legacy_reader_path(self):
        for row in _targets(self.scoped):
            with self.subTest(target_kind=row[0]):
                calls = []
                with patch.object(controls, "_read_control", wraps=controls._read_control) as reader:
                    self.assertEqual(_read(self.scoped, row, lambda: calls.append(True)), row[3])
                    self.assertEqual(reader.call_count, 1)
                    self.assertEqual(_read(self.legacy, row), row[3])
                    self.assertEqual(reader.call_count, 1)
                self.assertEqual(calls, [True, True])
                path = self.root / row[1]
                path.unlink()
                try:
                    self.assertIsNone(_read(self.scoped, row))
                    self.assertIsNone(_read(self.legacy, row))
                finally:
                    path.write_bytes(row[3])

    def test_strict_read_failures_and_same_byte_held_identity_disagreement_are_private(self):
        row = _targets(self.scoped)[0]
        for error in (OSError(str(self.root)), controls.WorkSessionBundleError("work_session_bundle_changed"),
                      exact.ExactOperationManifestError(str(self.root))):
            with self.subTest(error_type=type(error).__name__), \
                 patch.object(controls, "_read_control", side_effect=error):
                self.refuse(lambda: _read(self.scoped, row))
                self.assertEqual(_read(self.legacy, row), row[3])
        with patch.object(controls, "_read_control", return_value=row[3][:-1] + b" "):
            self.refuse(lambda: _read(self.scoped, row))
        original = archive_services._hold_activity_group_evidence_file

        @contextmanager
        def wrong_identity(*args, **kwargs):
            with original(*args, **kwargs) as held:
                yield {**held, "identity": (held["identity"][0], held["identity"][1] + 1)}

        with patch.object(archive_services, "_hold_activity_group_evidence_file", new=wrong_identity):
            self.refuse(lambda: _read(self.scoped, row))
        self.assertEqual(_read(self.scoped, row), row[3])


class SourceIntakeBatchHistoricalOutputIdentityTests(unittest.TestCase):
    def test_real_completed_history_rejects_both_linked_outputs_and_provider_entry_drift(self):
        # One actual completed batch supplies every subcase, without source or
        # caller-request reads during historical verification.
        fixture = completion_fixture.SourceIntakeCompletionReaderTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        active = fixture.claim()
        own = approval._rehydrate_exact_human_approval_core(fixture.root, fixture.context,
            fixture.reference["approval_id"], bytes(range(32)), _expected_status="succeeded")
        self.addCleanup(own.close)
        fixture.fixture.request.unlink()
        for source in fixture.fixture.sources:
            source.unlink()
        expected = fixture.read().proof_document()
        before = fixture.fixture.files()
        keys_before = len(fixture.fixture.key.create_if_missing_calls)
        with patch.object(intake, "plan_source_intake_batch", side_effect=AssertionError("replan")), \
             patch.object(intake, "_stable_source_digest", side_effect=AssertionError("source read")), \
             patch.object(intake, "_stable_request_bytes", side_effect=AssertionError("request read")), \
             patch.object(intake._Writer, "write_field", side_effect=AssertionError("writer")), \
             patch.object(approval._ClaimedExactHumanApproval, "exact_terminal_record_mac",
                          side_effect=AssertionError("sign")):
            for index, row in enumerate(_targets(fixture.plan)):
                with self.subTest(target_kind=row[0]):
                    path = fixture.root / row[1]
                    alias = fixture.fixture.fixture.workspace / ("historical-alias-" + str(index))
                    os.link(path, alias)
                    try:
                        self.assertEqual(os.lstat(path).st_nlink, 2)
                        self.assertEqual(path.read_bytes(), row[3])
                        with self.assertRaises(intake.SourceIntakeBatchExactError) as caught:
                            intake._verify_source_intake_batch_completion_with_claim_held(fixture.plan,
                                context=fixture.context, claim=own, writer_lock=fixture.held)
                        self.assertIsNone(caught.exception.__context__)
                        self.assertIsNone(caught.exception.__cause__)
                        fixture.refuse(fixture.read)
                        fixture.refuse(fixture.image)
                        with patch.object(fixture.fixture.key, "use_key", side_effect=AssertionError("nested key")):
                            fixture.refuse(lambda: fixture.verify(active))
                        self.assertEqual(alias.read_bytes(), row[3])
                    finally:
                        alias.unlink()
                    self.assertEqual(fixture.image().proof_document(), expected)

            row = _targets(fixture.plan)[0]
            alias = fixture.fixture.fixture.workspace / "provider-entry-output-alias"
            inserted = []

            def insert(create_if_missing):
                self.assertFalse(create_if_missing)
                os.link(fixture.root / row[1], alias)
                inserted.append(True)

            fixture.fixture.key.before_consumer = insert
            try:
                fixture.refuse(fixture.read)
                self.assertEqual(inserted, [True])
                self.assertEqual(os.lstat(fixture.root / row[1]).st_nlink, 2)
                self.assertEqual(alias.read_bytes(), row[3])
            finally:
                fixture.fixture.key.before_consumer = None
                if alias.exists():
                    alias.unlink()
            self.assertEqual(fixture.read().proof_document(), expected)
        self.assertEqual(active.status, "started")
        self.assertEqual(own.status, "succeeded")
        self.assertTrue(fixture.fixture.key.create_if_missing_calls[keys_before:])
        self.assertEqual(set(fixture.fixture.key.create_if_missing_calls[keys_before:]), {False})
        self.assertEqual(fixture.fixture.files(), before)


if __name__ == "__main__":
    unittest.main()
