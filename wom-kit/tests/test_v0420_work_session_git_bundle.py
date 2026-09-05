"""Durable original-context storage only; real synthetic Git preparation.

These tests do not establish route ownership, authenticate an approval or claim
Git completion. Remote observations during fixture preparation are synthetic;
the wrapper itself must never run Git, native approval, or a credential broker.
"""

from dataclasses import replace
import inspect
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_git_backup_writer as fixtures
import test_v0420_git_selection as selection_fixtures
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import git_backup_writer as writer
from wom_kit import work_session_git_bundle as bundle


class GitContextBundlePrivacyTests(unittest.TestCase):
    def test_fixed_errors_and_public_signatures_do_not_accept_authority_assertions(self):
        class PrivateString(str):
            def __hash__(self):
                raise AssertionError("SYNTHETIC_PRIVATE_HASH")

        for value in ([], {}, None, True, "SYNTHETIC_PRIVATE_PATH", PrivateString("work_session_git_bundle_missing")):
            error = bundle.WorkSessionGitBundleError(value)
            self.assertEqual(str(error), "work_session_git_bundle_invalid")
            self.assertIsNone(error.__context__)
            self.assertIsNone(error.__cause__)
        for function in (bundle._save_original_git_context_held, bundle._load_original_git_context_held):
            fields = inspect.signature(function).parameters
            self.assertTrue({"approve", "approval_id", "key_provider", "native", "claim_ref",
                             "task_route_ref", "completed"}.isdisjoint(fields))


class GitContextBundleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.GitBackupWriterTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.prepared = self.fixture.plan_and_prepare()
        self.context = writer._git_backup_approval_context(
            self.prepared, reviewer_claim="person:synthetic-original-reviewer",
        )

    def path(self, prepared=None):
        prepared = self.prepared if prepared is None else prepared
        return self.root.joinpath(*bundle.PRIVATE_ROOT) / (prepared.manifest.manifest_sha256[7:] + ".json")

    def save(self, held, *, prepared=None, context=None):
        return bundle._save_original_git_context_held(
            self.prepared if prepared is None else prepared,
            context=self.context if context is None else context, held=held,
        )

    def load(self, held, *, prepared=None):
        prepared = self.prepared if prepared is None else prepared
        return bundle._load_original_git_context_held(
            self.root, held=held, manifest_sha256=prepared.manifest.manifest_sha256,
        )

    def assert_private_error(self, error, *, code=None):
        if code is not None:
            self.assertEqual(error.code, code)
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        for marker in (str(self.root), "SYNTHETIC_PRIVATE", "example.invalid", "reviewer"):
            self.assertNotIn(marker, str(error) + repr(error))

    def test_original_v1_roundtrip_is_no_git_no_approval_and_exact_repeat_has_no_rewrite(self):
        before_bundle = writer._canonical(writer._bundle_document(self.prepared))
        before_manifest = self.prepared.manifest.document()
        before_context = approval.exact_human_approval_context_sha256(self.context)
        with exact.ExactOperationWriterLock(self.root) as held:
            # An original preparation precedes ignored approval machinery.
            # Storage must not rebuild the full plan and drift its own digest.
            with patch.object(writer.planning, "git_backup_plan", side_effect=AssertionError("Git plan called")), \
                 patch.object(writer.planning, "_local_git_raw", side_effect=AssertionError("Git called")), \
                 patch.object(workflow, "_production_key_provider", side_effect=AssertionError("key called")), \
                 patch.object(writer, "_apply_prepared_with_claim", side_effect=AssertionError("writer called")), \
                 patch.object(approval, "_claim_exact_human_approval_core", side_effect=AssertionError("claim called")):
                saved = self.save(held)
                raw = self.path().read_bytes()
                identity = self.path().stat()
                with patch.object(bundle.registry, "_write_private_pending", side_effect=AssertionError("rewrote original")), \
                     patch.object(bundle.durable, "_atomic_move_file_no_replace", side_effect=AssertionError("replaced original")):
                    repeated = self.save(held)
                    loaded = self.load(held)
                self.assertEqual(saved._raw, repeated._raw)
                self.assertEqual(saved._raw, loaded._raw)
                self.assertEqual(self.path().read_bytes(), raw)
                self.assertEqual(self.path().stat().st_mtime_ns, identity.st_mtime_ns)
                self.assertEqual(writer._canonical(writer._bundle_document(loaded.prepared)), before_bundle)
                self.assertEqual(loaded.prepared.manifest.document(), before_manifest)
                self.assertEqual(approval.exact_human_approval_context_sha256(loaded.context), before_context)
                self.assertIsNone(loaded.prepared.manifest.work_session_binding)
                self.assertIsNone(loaded.prepared.manifest.operation_evidence)
                held.verify_held()
        self.assertEqual(self.fixture.git(self.root, "rev-parse", "HEAD").stdout.strip(), self.fixture.initial_head)
        self.assertEqual(self.fixture.remote_observer(self.root, "origin", "refs/heads/main"),
                         ("present", self.fixture.initial_head))
        self.assertFalse((self.root / "receipts").exists())
        self.assertFalse((self.root / approval.CLAIMS_RELATIVE_ROOT).exists())
        self.assertFalse((self.root / exact.EXACT_OPERATION_LOCAL_ROOT / "checkpoints").exists())
        for marker in (str(self.root), self.prepared.remote_url, self.context.reviewer_claim, "tracked.txt"):
            self.assertNotIn(marker, repr(saved))

    def test_bound_v2_retains_original_revision_and_detaches_nested_views(self):
        fixture = selection_fixtures.GitSelectionV2RealTests(methodName="runTest")
        fixture.fixture, fixture.root, fixture.git = self.fixture, self.root, self.fixture.git
        binding = selection_fixtures.archive_binding(revision=7)
        prepared = fixture.prepare(work_session_binding=binding)
        context = writer._git_backup_approval_context(prepared, reviewer_claim=self.context.reviewer_claim)
        expected = writer._canonical(writer._bundle_document(prepared))
        with exact.ExactOperationWriterLock(self.root) as held:
            saved = self.save(held, prepared=prepared, context=context)
            view = saved.prepared
            view.groups[0].private_changes[0]["path"] = "SYNTHETIC_PRIVATE_MUTATED_PATH"
            self.assertEqual(writer._canonical(writer._bundle_document(saved.prepared)), expected)
            self.assertEqual(saved.prepared.manifest.work_session_binding, binding)
            self.assertIsNone(saved.prepared.manifest.operation_evidence)
            # Historical payload decoding consults neither current Git changes
            # nor a current session revision and never inserts a new binding.
            (self.root / "new-private.txt").write_bytes(b"later unrelated synthetic bytes\n")
            loaded = self.load(held, prepared=prepared)
            self.assertEqual(writer._canonical(writer._bundle_document(loaded.prepared)), expected)
            self.assertEqual(loaded.prepared.manifest.work_session_binding.revision, 7)
            with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                self.save(held, prepared=view, context=context)
            self.assert_private_error(caught.exception)
            self.assertEqual(self.path(prepared).read_bytes(), saved._raw)

    def test_context_factory_rejects_changed_authority_and_original_reviewer_cannot_be_replaced(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            invalid = (
                replace(self.context, plan_sha256="sha256:" + "a" * 64),
                replace(self.context, target_binding_sha256="sha256:" + "b" * 64),
                replace(self.context, warning_codes=("synthetic_changed_warning",)),
            )
            for context in invalid:
                with self.subTest(field_context=approval.exact_human_approval_context_sha256(context)):
                    with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                        self.save(held, context=context)
                    self.assert_private_error(caught.exception, code="work_session_git_bundle_context_invalid")
                    self.assertFalse(self.path().exists())
            self.save(held)
            original = self.path().read_bytes()
            changed_reviewer = writer._git_backup_approval_context(
                self.prepared, reviewer_claim="person:synthetic-replacement-reviewer",
            )
            with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                self.save(held, context=changed_reviewer)
            self.assert_private_error(caught.exception, code="work_session_git_bundle_changed")
            self.assertEqual(self.path().read_bytes(), original)

    def test_plain_legacy_bundle_does_not_supply_or_get_upgraded_to_original_context(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            writer._persist_private_bundle(self.prepared, writer_lock=held)
            legacy = self.root / exact.EXACT_OPERATION_LOCAL_ROOT / "git-backup-plans" / self.path().name
            original = legacy.read_bytes()
            with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                self.load(held)
            self.assert_private_error(caught.exception, code="work_session_git_bundle_missing")
            self.assertEqual(legacy.read_bytes(), original)
            self.assertFalse(self.path().parent.exists())

    def test_corrupt_duplicate_noncanonical_and_rehashed_inconsistent_bundle_are_never_repaired(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            saved = self.save(held)
            document = json.loads(saved._raw)
            changed = json.loads(saved._raw)
            changed["context"]["warning_codes"] = ["synthetic_warning"]
            altered_context = bundle._context_from_document(changed["context"])
            changed["context_sha256"] = approval.exact_human_approval_context_sha256(altered_context)
            changed["bundle_sha256"] = writer._sha256_json({k: v for k, v in changed.items() if k != "bundle_sha256"})
            forged_scope = json.loads(saved._raw)
            forged_scope["task_route_ref"] = "task_route_" + "a" * 32
            forged_scope["bundle_sha256"] = writer._sha256_json({k: v for k, v in forged_scope.items() if k != "bundle_sha256"})
            malformed = (
                b"{", b" " + saved._raw,
                saved._raw[:-1] + b',"schema":' + json.dumps(document["schema"]).encode("ascii") + b"}",
                writer._canonical(changed), writer._canonical(forged_scope),
            )
            for raw in malformed:
                self.path().write_bytes(raw)
                with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                    self.load(held)
                self.assert_private_error(caught.exception)
                with self.assertRaises(bundle.WorkSessionGitBundleError):
                    self.save(held)
                self.assertEqual(self.path().read_bytes(), raw)

    def test_foreign_unheld_lock_and_cross_archive_copy_fail_without_private_errors(self):
        with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
            self.save(object())
        self.assert_private_error(caught.exception, code="work_session_git_bundle_lock_required")
        with tempfile.TemporaryDirectory(prefix="wom-git-context-foreign-") as temporary:
            other = Path(temporary)
            (other / "archive.yml").write_text("archive_id: archive:personal:other-synthetic\n", encoding="utf-8")
            with exact.ExactOperationWriterLock(other) as foreign:
                with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                    self.save(foreign)
                self.assert_private_error(caught.exception, code="work_session_git_bundle_lock_required")
            with exact.ExactOperationWriterLock(self.root) as held:
                raw = self.save(held)._raw
            target = other.joinpath(*bundle.PRIVATE_ROOT) / self.path().name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            with exact.ExactOperationWriterLock(other) as foreign:
                with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                    bundle._load_original_git_context_held(other, held=foreign,
                        manifest_sha256=self.prepared.manifest.manifest_sha256)
                self.assert_private_error(caught.exception)
            with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                self.load(held)
            self.assert_private_error(caught.exception, code="work_session_git_bundle_lock_required")

    def test_power_cut_before_rename_retains_pending_and_does_not_publish_original(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(bundle.durable, "_atomic_move_file_no_replace",
                              side_effect=OSError("SYNTHETIC_PRIVATE_RENAME_PATH")):
                with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                    self.save(held)
            self.assert_private_error(caught.exception, code="work_session_git_bundle_durability_unknown")
            self.assertFalse(self.path().exists())
            pending = list(self.path().parent.glob(".pending_*"))
            self.assertEqual(len(pending), 1)
            original_pending = pending[0].read_bytes()
            with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                self.load(held)
            self.assert_private_error(caught.exception, code="work_session_git_bundle_missing")
            self.assertEqual(pending[0].read_bytes(), original_pending)

    def test_post_rename_durability_cut_preserves_original_and_repeat_flushes_without_rewrite(self):
        original_flush = bundle.durable._require_directory_durable

        def cut_after_rename(path):
            if self.path().exists():
                raise OSError("SYNTHETIC_PRIVATE_FLUSH_PATH")
            return original_flush(path)

        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(bundle.durable, "_require_directory_durable", side_effect=cut_after_rename):
                with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                    self.save(held)
            self.assert_private_error(caught.exception, code="work_session_git_bundle_durability_unknown")
            raw = self.path().read_bytes()
            with patch.object(bundle.registry, "_write_private_pending", side_effect=AssertionError("rewrote original")), \
                 patch.object(bundle.durable, "_require_directory_durable", wraps=original_flush) as flushed:
                result = self.save(held)
            self.assertTrue(flushed.called)
            self.assertEqual(result._raw, raw)
            self.assertEqual(self.path().read_bytes(), raw)

    def test_pending_and_published_readback_detect_actual_changed_bytes(self):
        original_write = bundle.registry._write_private_pending
        original_move = bundle.durable._atomic_move_file_no_replace

        def changed_pending(path, raw, **kwargs):
            original_write(path, raw, **kwargs)
            path.write_bytes(raw + b" ")

        def changed_published(source, destination, **kwargs):
            original_move(source, destination, **kwargs)
            destination.write_bytes(b"{")

        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(bundle.registry, "_write_private_pending", side_effect=changed_pending):
                with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                    self.save(held)
            self.assert_private_error(caught.exception, code="work_session_git_bundle_changed")
            self.assertFalse(self.path().exists())
            pending = list(self.path().parent.glob(".pending_*"))
            self.assertEqual(len(pending), 1)
            self.assertTrue(pending[0].read_bytes().endswith(b" "))
            with patch.object(bundle.durable, "_atomic_move_file_no_replace", side_effect=changed_published):
                with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                    self.save(held)
            self.assert_private_error(caught.exception)
            self.assertEqual(self.path().read_bytes(), b"{")
            with self.assertRaises(bundle.WorkSessionGitBundleError):
                self.save(held)
            self.assertEqual(self.path().read_bytes(), b"{")

    def test_hardlinked_final_file_and_oversize_input_are_rejected_without_rewrite(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            saved = self.save(held)
            link = self.path().parent / "synthetic-evidence-link"
            os.link(self.path(), link)
            with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                self.load(held)
            self.assert_private_error(caught.exception)
            self.assertEqual(link.read_bytes(), saved._raw)
            with patch.object(bundle, "MAX_BUNDLE_BYTES", 32):
                with self.assertRaises(bundle.WorkSessionGitBundleError):
                    self.save(held)
            self.assertEqual(link.read_bytes(), saved._raw)

    def test_repeat_revalidates_original_bytes_after_directory_flush(self):
        original_flush = bundle.durable._require_directory_durable
        with exact.ExactOperationWriterLock(self.root) as held:
            saved = self.save(held)
            changed = json.loads(saved._raw)
            changed_context = writer._git_backup_approval_context(
                self.prepared, reviewer_claim="person:synthetic-other-reviewer",
            )
            changed["context"] = bundle.session_bundle._context_document(changed_context)
            changed["context_sha256"] = approval.exact_human_approval_context_sha256(changed_context)
            changed["bundle_sha256"] = writer._sha256_json({k: v for k, v in changed.items() if k != "bundle_sha256"})
            changed_raw = writer._canonical(changed)

            def replace_after_flush(path):
                result = original_flush(path)
                self.path().write_bytes(changed_raw)
                return result

            with patch.object(bundle.durable, "_require_directory_durable", side_effect=replace_after_flush), \
                 patch.object(bundle.registry, "_write_private_pending", side_effect=AssertionError("rewrote original")):
                with self.assertRaises(bundle.WorkSessionGitBundleError) as caught:
                    self.save(held)
            self.assert_private_error(caught.exception, code="work_session_git_bundle_changed")
            self.assertEqual(self.path().read_bytes(), changed_raw)


if __name__ == "__main__":
    unittest.main()
