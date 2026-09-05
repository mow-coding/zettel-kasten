"""Prepared payload persistence is private, immutable, and not human authority."""

from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

import test_v0420_work_session_operation as fixtures
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_bundle as bundles
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation, ExactHumanApprovalTargetPreview


class SessionBundleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SessionOperationTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.store, self.prepared = self.fixture.root, self.fixture.store, self.fixture.prepared
        self.directory = self.root.joinpath(*bundles.PRIVATE_ROOT)
        self.digest = self.prepared.manifest.manifest_sha256
        self.path = self.directory / (self.digest[7:] + ".json")

    def save(self, prepared=None):
        with exact.ExactOperationWriterLock(self.root) as held:
            return bundles.save_prepared_session_decision(self.store, prepared or self.prepared, held_lock=held)

    def load(self):
        return bundles.load_prepared_session_decision(self.store, manifest_sha256=self.digest)

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def rehash(self, document):
        document["bundle_sha256"] = bundles._sha(bundles._canonical(
            {key: value for key, value in document.items() if key != "bundle_sha256"}
        ))
        return bundles._canonical(document)

    def assert_fixed_error(self, call, code=None):
        with self.assertRaises(bundles.WorkSessionBundleError) as caught:
            call()
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertIn(str(caught.exception), bundles._ERRORS)
        self.assertIsNone(caught.exception.__context__)
        self.assertNotIn("Synthetic", repr(caught.exception))

    def test_roundtrip_is_private_readonly_and_does_not_create_authority(self):
        before = self.store.read().sha256
        self.assertIsNone(self.save())
        self.assertEqual(self.store.read().sha256, before)
        self.assertFalse((self.root / "receipts").exists())
        self.assertFalse((self.root / "profiles/local/exact-human-approvals").exists())
        self.assertEqual(len(list(self.directory.iterdir())), 1)
        self.assertIn(b"Synthetic private task", self.path.read_bytes())
        files = self.files()
        with (mock.patch.object(bundles.registry, "_write_private_pending", side_effect=AssertionError("read wrote")),
              mock.patch.object(bundles.durable, "_atomic_move_file_no_replace", side_effect=AssertionError("read moved")),
              mock.patch.object(bundles.exact, "_ensure_private_directory", side_effect=AssertionError("read created"))):
            restored = self.load()
        self.assertEqual(self.files(), files)
        self.assertEqual(restored, self.prepared)
        self.assertIsNot(restored.transition.after._document, self.prepared.transition.after._document)
        self.assertIsNot(restored.transition._request, self.prepared.transition._request)
        self.assertNotIn("Synthetic", repr(restored))
        self.assertNotIn("Synthetic", json.dumps(restored.manifest.document()))
        self.assertEqual(restored.context(archive_id=fixtures.ARCHIVE_ID, reviewer_claim="person:synthetic"),
                         self.fixture.context)
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(registry.WorkSessionRegistryError):
                operation.apply_session_decision_with_claim(self.store, restored, context=self.fixture.context,
                                                           claim=True, held_lock=held)
        self.assertEqual(self.store.read().sha256, before)

    def test_new_process_loads_the_same_payload_without_credentials(self):
        self.save()
        script = (
            "from pathlib import Path\nimport sys\n"
            "from wom_kit import exact_human_approval as a, work_session_registry as r, work_session_bundle as b\n"
            "root, archive_id = a._archive_identity(Path(sys.argv[1]))\n"
            "store = r.WorkSessionRegistryStore(root, a.exact_human_approval_archive_identity_sha256(archive_id))\n"
            "prepared = b.load_prepared_session_decision(store, manifest_sha256=sys.argv[2])\n"
            "print(prepared.manifest.manifest_sha256)\n"
        )
        before = self.files()
        completed = subprocess.run([sys.executable, "-B", "-c", script, str(self.root), self.digest],
                                   capture_output=True, text=True, timeout=30,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), self.digest)
        self.assertEqual(self.files(), before)

    def test_missing_or_bad_identifier_read_has_no_filesystem_effect(self):
        before = self.files()
        self.assert_fixed_error(self.load, "work_session_bundle_missing")
        for invalid in ("../private", "sha256:" + "A" * 64, [], None, True):
            with self.subTest(kind=type(invalid).__name__):
                self.assert_fixed_error(lambda: bundles.load_prepared_session_decision(
                    self.store, manifest_sha256=invalid))
        self.assertEqual(self.files(), before)
        self.assertFalse(self.directory.exists())

    def test_wrong_archive_or_unheld_lock_is_refused_before_plan_files(self):
        other = self.root.parent / "other"
        other.mkdir()
        (other / "archive.yml").write_text("archive_id: archive:personal:other-synthetic\n", encoding="utf-8")
        other_store = registry.WorkSessionRegistryStore(other, approval.exact_human_approval_archive_identity_sha256(
            "archive:personal:other-synthetic"))
        for held in (None, True, exact.ExactOperationWriterLock(self.root)):
            with self.subTest(kind=type(held).__name__):
                self.assert_fixed_error(lambda: bundles.save_prepared_session_decision(
                    self.store, self.prepared, held_lock=held), "work_session_bundle_lock_required")
        with exact.ExactOperationWriterLock(other) as held:
            self.assert_fixed_error(lambda: bundles.save_prepared_session_decision(
                self.store, self.prepared, held_lock=held), "work_session_bundle_lock_required")
            self.assert_fixed_error(lambda: bundles.save_prepared_session_decision(
                other_store, self.prepared, held_lock=held))
            lying_store = registry.WorkSessionRegistryStore(other, self.store.archive_identity_sha256)
            self.assert_fixed_error(lambda: bundles.save_prepared_session_decision(
                lying_store, self.prepared, held_lock=held), "work_session_bundle_changed")
        self.assertFalse(self.directory.exists())
        self.assertFalse(other.joinpath(*bundles.PRIVATE_ROOT).exists())

    def test_canonical_schema_duplicate_keys_and_rehashed_payload_tampering_reject(self):
        self.save()
        original = self.path.read_bytes()
        document = json.loads(original)
        mutations = [original + b"\n", original.replace(b'{"archive_identity_sha256":', b'{"schema":"extra","archive_identity_sha256":', 1)]
        for key, value in (("source_ascii", "Synthetic private altered source"),
                           ("manifest", {}), ("schema", "not-the-schema"), ("extra", True)):
            changed = deepcopy(document)
            changed[key] = value
            mutations.append(self.rehash(changed))
        for raw in mutations:
            with self.subTest(ordinal=mutations.index(raw)):
                self.path.write_bytes(raw)
                self.assert_fixed_error(self.load)
        self.path.write_bytes(original)
        with mock.patch.object(bundles, "MAX_BUNDLE_BYTES", len(original) - 1):
            self.assert_fixed_error(self.load)
        self.assertEqual(self.load(), self.prepared)

    def test_rehashed_forged_postimage_or_generated_refs_fail_before_saving(self):
        after = deepcopy(self.prepared.transition.after._document)
        after["apps"][self.fixture.app]["label"] = "Synthetic hidden change"
        transition = replace(self.prepared.transition, after=registry.RegistrySnapshot(after))
        transition = replace(transition, plan_sha256=registry._digest(transition._basis()))
        forged = operation.prepare_session_decision(transition)
        forged.validate()  # Digest agreement alone is not transition legality.
        self.assert_fixed_error(lambda: self.save(forged))
        for generated in ((), ("claim_" + "a" * 32,), self.prepared.transition._generated_refs + ("claim_" + "a" * 32,)):
            with self.subTest(count=len(generated)):
                invalid = operation.prepare_session_decision(replace(self.prepared.transition, _generated_refs=generated))
                self.assert_fixed_error(lambda: self.save(invalid))
        self.assertFalse(self.directory.exists())
        self.assertEqual(self.store.read().revision, 1)
        # Rehashing every payload/manifest field and choosing its new filename
        # still cannot make the same illegal transition acceptable to loading.
        self.directory.mkdir(parents=True)
        forged_path = self.directory / (forged.manifest.manifest_sha256[7:] + ".json")
        forged_raw = bundles._canonical(bundles._document(forged))
        forged_path.write_bytes(forged_raw)
        self.assert_fixed_error(lambda: bundles.load_prepared_session_decision(
            self.store, manifest_sha256=forged.manifest.manifest_sha256))
        self.assertEqual(forged_path.read_bytes(), forged_raw)
        self.assertEqual(self.store.read().revision, 1)

    def test_existing_file_is_checked_and_never_overwritten(self):
        self.save()
        original = self.path.read_bytes()
        before = os.lstat(self.path)
        with mock.patch.object(registry, "_write_private_pending", side_effect=AssertionError("idempotent save wrote")):
            self.save()
        after = os.lstat(self.path)
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
        altered = original + b"Synthetic private corruption"
        self.path.write_bytes(altered)
        self.assert_fixed_error(self.save)
        self.assertEqual(self.path.read_bytes(), altered)

    def test_matching_historical_target_load_keeps_original_binding(self):
        self.save()
        original = self.path.read_bytes()
        self.fixture.execute()
        for index in range(3):
            transition = registry.plan_transition(self.store.read(), action="register-app", label=f"Synthetic later {index}")
            with exact.ExactOperationWriterLock(self.root) as held:
                self.store.commit(transition, held_lock=held)
        before = self.files()
        restored = self.load()
        self.assertEqual(restored, self.prepared)
        self.assertEqual(self.files(), before)
        with mock.patch.object(registry, "_write_private_pending", side_effect=AssertionError("historical save wrote")):
            self.save()
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(restored.manifest.work_session_binding.document(),
                         self.prepared.manifest.work_session_binding.document())
        # The original predecessor is now older than the store's latest-two scan.
        path = self.store.path / "000000000001.json"
        previous = json.loads(path.read_bytes())
        previous["apps"][self.fixture.app]["label"] = "Synthetic changed history"
        path.write_bytes(registry._canonical(previous))
        self.assertEqual(self.store.read().revision, 5)
        self.assert_fixed_error(self.load, "work_session_bundle_changed")

    def test_other_generation_occupying_target_cannot_rebind_old_payload(self):
        self.save()
        original = self.path.read_bytes()
        unrelated = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic unrelated")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(unrelated, held_lock=held)
        self.assert_fixed_error(self.load, "work_session_bundle_changed")
        self.assert_fixed_error(self.save, "work_session_bundle_changed")
        self.assertEqual(self.path.read_bytes(), original)

    def test_hardlink_and_symlink_bundle_are_not_read_or_replaced(self):
        self.save()
        link = self.root.parent / "synthetic-hardlink"
        os.link(self.path, link)
        self.assert_fixed_error(self.load)
        self.assert_fixed_error(self.save)
        link.unlink()
        original = self.path.read_bytes()
        self.path.unlink()
        link.write_bytes(original)
        try:
            self.path.symlink_to(link)
        except OSError:
            self.path.write_bytes(original)
            self.skipTest("host does not permit symlink creation; hardlink refusal passed")
        self.assert_fixed_error(self.load)
        self.assert_fixed_error(self.save)
        self.assertTrue(self.path.is_symlink())
        self.assertEqual(link.read_bytes(), original)

    def test_partial_pending_and_uncertain_atomic_publication_preserve_evidence(self):
        original_write = registry._write_private_pending

        def partial(path, raw, *, root):
            original_write(path, raw[:20], root=root)
            raise RuntimeError("Synthetic private write interruption")

        with mock.patch.object(registry, "_write_private_pending", side_effect=partial):
            self.assert_fixed_error(self.save, "work_session_bundle_durability_unknown")
        pending = list(self.directory.glob(".pending_*"))
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].stat().st_size, 20)
        self.assertFalse(self.path.exists())
        original_move = bundles.durable._atomic_move_file_no_replace

        def moved_then_interrupted(source, destination):
            original_move(source, destination)
            raise RuntimeError("Synthetic private move interruption")

        with mock.patch.object(bundles.durable, "_atomic_move_file_no_replace", side_effect=moved_then_interrupted):
            self.assert_fixed_error(self.save, "work_session_bundle_durability_unknown")
        self.assertTrue(self.path.exists())
        self.assertEqual(self.load(), self.prepared)
        self.save()
        self.assertTrue(pending[0].exists())
        self.assertEqual(self.store.read().revision, 1)
        self.assertFalse((self.root / "receipts").exists())

    def test_cas_change_during_pending_write_preserves_both_generation_and_pending(self):
        original_write = registry._write_private_pending
        invoked = []
        with exact.ExactOperationWriterLock(self.root) as held:
            def write_then_change(path, raw, *, root):
                original_write(path, raw, root=root)
                if path.parent == self.directory and not invoked:
                    invoked.append(True)
                    later = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic new app")
                    self.store.commit(later, held_lock=held)

            with mock.patch.object(registry, "_write_private_pending", side_effect=write_then_change):
                self.assert_fixed_error(lambda: bundles.save_prepared_session_decision(
                    self.store, self.prepared, held_lock=held), "work_session_bundle_changed")
        self.assertFalse(self.path.exists())
        self.assertEqual(len(list(self.directory.glob(".pending_*"))), 1)
        self.assertEqual(self.store.read().revision, 2)

    def test_original_nested_view_change_cannot_modify_detached_saved_payload(self):
        original = bundles._canonical(bundles._document(self.prepared))
        original_write = registry._write_private_pending

        def mutate_original(path, raw, *, root):
            original_write(path, raw, root=root)
            self.prepared.transition.after._document["apps"][self.fixture.app]["label"] = "Synthetic changed caller"

        with mock.patch.object(registry, "_write_private_pending", side_effect=mutate_original):
            self.save()
        self.assertEqual(self.path.read_bytes(), original)
        restored = self.load()
        self.assertEqual(restored.transition.after._document["apps"][self.fixture.app]["label"], "Synthetic app")

    def test_every_human_action_roundtrips_its_original_exact_request(self):
        self.save()
        self.fixture.execute()
        session = self.prepared.transition.result_refs[-1]
        other = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic other app")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(other, held_lock=held)
            claimed = registry.plan_transition(self.store.read(), action="claim",
                                               client_app_ref=self.fixture.app, work_session_ref=session)
            self.store.commit(claimed, held_lock=held)
        claim = claimed.after._document["sessions"][session]["claim_ref"]
        requests = [
            {"action": "handoff", "client_app_ref": self.fixture.app, "work_session_ref": session,
             "claim_ref": claim, "target_app_ref": other.result_refs[0]},
            {"action": "accept", "client_app_ref": other.result_refs[0], "work_session_ref": session},
        ]
        for request in requests:
            prepared = operation.prepare_session_decision(registry.plan_transition(self.store.read(), **request))
            with self.subTest(action=request["action"]):
                self.save(prepared)
                restored = bundles.load_prepared_session_decision(self.store, manifest_sha256=prepared.manifest.manifest_sha256)
                self.assertEqual(restored, prepared)
                self.fixture.prepared = restored
                self.fixture.context = restored.context(archive_id=fixtures.ARCHIVE_ID, reviewer_claim="person:synthetic")
                self.assertTrue(self.fixture.execute()["ok"])
        session = prepared.transition.result_refs[-1]
        claimed = registry.plan_transition(self.store.read(), action="claim",
                                           client_app_ref=other.result_refs[0], work_session_ref=session)
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(claimed, held_lock=held)
        recovered = operation.prepare_session_decision(registry.plan_transition(
            self.store.read(), action="recover", client_app_ref=other.result_refs[0], work_session_ref=session))
        self.save(recovered)
        self.assertEqual(bundles.load_prepared_session_decision(self.store,
                         manifest_sha256=recovered.manifest.manifest_sha256), recovered)
        self.assertEqual(self.store.read().sha256, claimed.after.sha256)

    def test_named_store_redirection_is_rejected_before_external_read(self):
        original = self.store.path
        self.store.path = self.root.parent / "do-not-read"
        try:
            with mock.patch.object(self.store, "_observe_names", side_effect=AssertionError("untrusted path read")):
                self.assert_fixed_error(self.save, "work_session_bundle_path_unsafe")
                self.assert_fixed_error(self.load, "work_session_bundle_path_unsafe")
        finally:
            self.store.path = original
        self.assertFalse(self.directory.exists())

    def test_historical_predecessor_change_during_read_is_detected_at_final_barrier(self):
        self.save()
        self.fixture.execute()
        for index in range(3):
            plan = registry.plan_transition(self.store.read(), action="register-app", label=f"Synthetic app {index}")
            with exact.ExactOperationWriterLock(self.root) as held:
                self.store.commit(plan, held_lock=held)
        original = bundles._generation
        changed = []

        def mutate_after_observation(store, revision, names):
            result = original(store, revision, names)
            if revision == 1 and not changed:
                changed.append(True)
                value = deepcopy(result._document)
                value["apps"][self.fixture.app]["label"] = "Synthetic racing history"
                (self.store.path / "000000000001.json").write_bytes(registry._canonical(value))
            return result

        with mock.patch.object(bundles, "_generation", side_effect=mutate_after_observation):
            self.assert_fixed_error(self.load, "work_session_bundle_changed")
        self.assertEqual(changed, [True])

    @unittest.skipUnless(os.name == "nt", "native retained Windows parent")
    def test_private_write_retains_parent_and_rejects_reparse_directory(self):
        original = registry.durable._write_new
        attempts = []

        def write(path, raw, *, within):
            if path.parent == self.directory:
                with self.assertRaises(OSError):
                    path.parent.rename(path.parent.with_name("synthetic-moved-plans"))
                attempts.append(True)
            return original(path, raw, within=within)

        with mock.patch.object(registry.durable, "_write_new", side_effect=write):
            self.save()
        self.assertEqual(attempts, [True])
        real_lstat = bundles.os.lstat

        class Reparse:
            def __init__(self, info):
                self.info = info
                self.st_file_attributes = getattr(info, "st_file_attributes", 0) | 0x400

            def __getattr__(self, name):
                return getattr(self.info, name)

        def lstat(path, *args, **kwargs):
            result = real_lstat(path, *args, **kwargs)
            return Reparse(result) if Path(path) == self.directory else result

        with mock.patch.object(bundles.os, "lstat", side_effect=lstat):
            self.assert_fixed_error(self.load, "work_session_bundle_path_unsafe")
            self.assert_fixed_error(self.save, "work_session_bundle_path_unsafe")

    @unittest.skipIf(os.name == "nt", "retained POSIX read handle")
    def test_posix_parent_replacement_never_reads_the_external_bundle(self):
        self.save()
        outside = self.root.parent / "synthetic-external"
        outside.mkdir()
        (outside / self.path.name).write_bytes(b"Synthetic private external bytes")
        moved = self.directory.with_name("synthetic-retained-plans")
        original = bundles.os.open
        replaced = []

        def swap(path, flags, *args, **kwargs):
            if path == self.path.name and "dir_fd" in kwargs and not replaced:
                self.directory.rename(moved)
                self.directory.symlink_to(outside, target_is_directory=True)
                replaced.append(True)
            return original(path, flags, *args, **kwargs)

        observed = []
        original_read = bundles.os.read

        def read(descriptor, amount):
            value = original_read(descriptor, amount)
            observed.append(value)
            return value

        with mock.patch.object(bundles.os, "open", side_effect=swap), mock.patch.object(bundles.os, "read", side_effect=read):
            self.assert_fixed_error(self.load)
        self.assertEqual(replaced, [True])
        self.assertNotIn(b"Synthetic private external bytes", b"".join(observed))
        self.assertTrue((moved / self.path.name).exists())


class SessionContextBundleTests(unittest.TestCase):
    def setUp(self):
        # Composition avoids collecting the complete pure-bundle suite twice.
        self.pure = SessionBundleTests(methodName="runTest")
        self.pure.setUp()
        self.addCleanup(self.pure.doCleanups)
        self.fixture = self.pure.fixture
        self.root, self.store, self.prepared = self.pure.root, self.pure.store, self.pure.prepared
        self.path, self.directory, self.digest = self.pure.path, self.pure.directory, self.pure.digest
        self.context = self.fixture.context

    def save(self, context=None):
        with exact.ExactOperationWriterLock(self.root) as held:
            return bundles.save_context_bound_session_decision(
                self.store, self.prepared, context=context or self.context, held_lock=held)

    def load(self):
        return bundles.load_context_bound_session_decision(self.store, manifest_sha256=self.digest)

    def test_exact_context_roundtrip_has_no_authority_or_native_preview(self):
        preview = ExactHumanApprovalTargetPreview(kind="zet", primary="Synthetic preview only")
        supplied = replace(self.context, target_preview=preview)
        authority_sha = approval.exact_human_approval_context_sha256(self.context)
        self.assertEqual(approval.exact_human_approval_context_sha256(supplied), authority_sha)
        original_revision = self.store.read().sha256
        self.assertIsNone(self.save(supplied))
        raw = self.path.read_bytes()
        self.assertNotIn(b"Synthetic preview only", raw)
        self.assertNotIn(b"target_preview", raw)
        document = json.loads(raw)
        self.assertEqual(document["schema"], bundles.CONTEXT_BUNDLE_SCHEMA)
        self.assertEqual(document["prepared"], bundles._document(self.prepared))
        self.assertEqual(document["context_sha256"], authority_sha)
        self.assertEqual(document["context"]["reviewer_claim"], self.context.reviewer_claim)
        before = self.pure.files()
        with (mock.patch.object(registry, "_write_private_pending", side_effect=AssertionError("read wrote")),
              mock.patch.object(bundles.exact, "_ensure_private_directory", side_effect=AssertionError("read created"))):
            restored = self.load()
        self.assertEqual(restored.prepared, self.prepared)
        self.assertEqual(restored.context, self.context)
        self.assertIsNone(restored.context.target_preview)
        self.assertEqual(approval.exact_human_approval_context_sha256(restored.context), authority_sha)
        self.assertNotIn("Synthetic", repr(restored))
        self.assertNotIn("person:", repr(restored))
        self.assertEqual(self.pure.files(), before)
        self.assertEqual(self.store.read().sha256, original_revision)
        self.assertFalse((self.root / "profiles/local/exact-human-approvals").exists())
        self.assertFalse((self.root / "receipts").exists())

    def test_original_reviewer_is_preserved_across_process_and_later_generations(self):
        self.context = replace(self.context, reviewer_claim="human:original.synthetic")
        self.fixture.context = self.context
        self.save()
        original = self.path.read_bytes()
        self.fixture.execute()
        later = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic later app")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(later, held_lock=held)
        script = (
            "from pathlib import Path\nimport sys\n"
            "from wom_kit import exact_human_approval as a, work_session_registry as r, work_session_bundle as b\n"
            "root, archive_id = a._archive_identity(Path(sys.argv[1]))\n"
            "store = r.WorkSessionRegistryStore(root, a.exact_human_approval_archive_identity_sha256(archive_id))\n"
            "loaded = b.load_context_bound_session_decision(store, manifest_sha256=sys.argv[2])\n"
            "print(a.exact_human_approval_context_sha256(loaded.context))\n"
        )
        before = self.pure.files()
        completed = subprocess.run([sys.executable, "-B", "-c", script, str(self.root), self.digest],
                                   capture_output=True, text=True, timeout=30,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), approval.exact_human_approval_context_sha256(self.context))
        self.assertEqual(self.load().context.reviewer_claim, "human:original.synthetic")
        with mock.patch.object(registry, "_write_private_pending", side_effect=AssertionError("save rewrote")):
            self.save()
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.pure.files(), before)

    def test_new_reviewer_never_overwrites_saved_original(self):
        self.save()
        original = self.path.read_bytes()
        before = os.lstat(self.path)
        with mock.patch.object(registry, "_write_private_pending", side_effect=AssertionError("save rewrote")):
            self.save()
            self.pure.assert_fixed_error(lambda: self.save(replace(self.context, reviewer_claim="person:other")),
                                         "work_session_bundle_changed")
        after = os.lstat(self.path)
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.load().context, self.context)

    def test_pure_payload_is_neither_context_inferred_nor_upgraded(self):
        self.pure.save()
        original = self.path.read_bytes()
        self.pure.assert_fixed_error(self.load, "work_session_bundle_context_missing")
        self.pure.assert_fixed_error(self.save, "work_session_bundle_context_missing")
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.pure.load(), self.prepared)
        self.assertEqual(len(list(self.directory.iterdir())), 1)
        # An invalid old payload must not masquerade as merely lacking context.
        changed = json.loads(original)
        changed["source_ascii"] = "Synthetic invalid original source"
        self.path.write_bytes(self.pure.rehash(changed))
        self.pure.assert_fixed_error(self.load, "work_session_bundle_invalid")

    def test_context_payload_cannot_be_downgraded_by_pure_save(self):
        self.save()
        original = self.path.read_bytes()
        self.pure.assert_fixed_error(self.pure.save)
        self.pure.assert_fixed_error(self.pure.load)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.load().context, self.context)

    def test_all_factory_context_fields_are_checked_before_plan_write(self):
        changes = (
            {"operation": ExactHumanApprovalOperation.git_backup},
            {"archive_identity_sha256": "sha256:" + "1" * 64},
            {"plan_sha256": "sha256:" + "2" * 64},
            {"target_binding_sha256": "sha256:" + "3" * 64},
            {"review_binding_codes": ("synthetic_other_review",)},
            {"warning_codes": ("work_session_handoff",)},
        )
        for change in changes:
            with self.subTest(field=next(iter(change))):
                self.pure.assert_fixed_error(lambda: self.save(replace(self.context, **change)),
                                             "work_session_bundle_context_invalid")
                self.assertFalse(self.directory.exists())
        self.assertEqual(self.store.read().revision, 1)

    def test_rehashed_context_tampering_still_must_match_factory(self):
        self.save()
        original = self.path.read_bytes()
        contexts = (
            replace(self.context, operation=ExactHumanApprovalOperation.git_backup),
            replace(self.context, archive_identity_sha256="sha256:" + "1" * 64),
            replace(self.context, plan_sha256="sha256:" + "2" * 64),
            replace(self.context, target_binding_sha256="sha256:" + "3" * 64),
            replace(self.context, review_binding_codes=("synthetic_other_review",)),
            replace(self.context, warning_codes=("work_session_accept",)),
        )
        for index, context in enumerate(contexts):
            with self.subTest(index=index):
                document = json.loads(original)
                document["context"] = bundles._context_document(context)
                document["context_sha256"] = approval.exact_human_approval_context_sha256(context)
                self.path.write_bytes(self.pure.rehash(document))
                self.pure.assert_fixed_error(self.load, "work_session_bundle_context_invalid")
        self.path.write_bytes(original)
        self.assertEqual(self.load().context, self.context)

    def test_schema_hash_and_review_claim_tampering_are_rejected_without_echo(self):
        self.save()
        original = self.path.read_bytes()
        alterations = []
        for field, value in (("reviewer_claim", "person:other"), ("reviewer_claim", "Synthetic private invalid reviewer"),
                             ("warning_codes", "work_session_start"), ("extra", "Synthetic private text")):
            changed = json.loads(original)
            changed["context"][field] = value
            alterations.append(self.pure.rehash(changed))
        for field, value in (("context_sha256", "sha256:" + "0" * 64),
                             ("prepared", {}), ("extra", "Synthetic private text")):
            changed = json.loads(original)
            changed[field] = value
            alterations.append(self.pure.rehash(changed))
        alterations.extend((original + b"\n", original.replace(b'{"bundle_sha256":', b'{"schema":"extra","bundle_sha256":', 1)))
        for index, raw in enumerate(alterations):
            with self.subTest(index=index):
                self.path.write_bytes(raw)
                self.pure.assert_fixed_error(self.load)
        self.path.write_bytes(original)
        with mock.patch.object(bundles, "MAX_BUNDLE_BYTES", len(original) - 1):
            self.pure.assert_fixed_error(self.load)

    def test_rehashed_new_reviewer_payload_cannot_resume_original_authenticated_claim(self):
        self.save()
        result = self.fixture.execute()
        receipt = exact.load_exact_operation_final_receipt_read_only(self.root, result["execution_sha256"])
        reference = receipt["result"]["completion_authentication"]["approval_reference"]
        changed = replace(self.context, reviewer_claim="person:other")
        self.path.write_bytes(bundles._canonical(bundles._context_bound_document(self.prepared, changed)))
        loaded = self.load()
        # Private payload integrity is not authorization: the old HMAC claim
        # binds the original reviewer context and refuses a rehashed substitute.
        self.assertNotEqual(approval.exact_human_approval_context_sha256(loaded.context),
                            approval.exact_human_approval_context_sha256(self.context))
        guard = mock.Mock(return_value=True)
        finish = mock.Mock(return_value={"ok": True})
        before = self.pure.files()
        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
            workflow._resume_succeeded_claim_finalizer_core(
                self.root, loaded.context, reference["approval_id"], guard, finish,
                key_provider=self.fixture.key)
        guard.assert_not_called()
        finish.assert_not_called()
        self.assertEqual(self.pure.files(), before)

    def test_context_save_requires_same_held_lock_and_checks_hardlinks(self):
        self.pure.assert_fixed_error(lambda: bundles.save_context_bound_session_decision(
            self.store, self.prepared, context=self.context, held_lock=None), "work_session_bundle_lock_required")
        self.assertFalse(self.directory.exists())
        self.save()
        link = self.root.parent / "synthetic-context-hardlink"
        os.link(self.path, link)
        before = self.path.read_bytes()
        self.pure.assert_fixed_error(self.load)
        self.pure.assert_fixed_error(self.save)
        self.assertEqual(link.read_bytes(), before)
        link.unlink()
        self.assertEqual(self.load().context, self.context)

    def test_context_partial_pending_is_retained_and_no_authority_is_created(self):
        original_write = registry._write_private_pending

        def interrupted(path, raw, *, root):
            original_write(path, raw[:24], root=root)
            raise RuntimeError("Synthetic private interruption")

        with mock.patch.object(registry, "_write_private_pending", side_effect=interrupted):
            self.pure.assert_fixed_error(self.save, "work_session_bundle_durability_unknown")
        pending = list(self.directory.glob(".pending_*"))
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].stat().st_size, 24)
        self.assertFalse(self.path.exists())
        self.save()
        self.assertEqual(self.load().context, self.context)
        self.assertTrue(pending[0].exists())
        self.assertEqual(self.store.read().revision, 1)
        self.assertFalse((self.root / "profiles/local/exact-human-approvals").exists())

    def test_saved_context_and_payload_are_detached_before_pending_callback(self):
        expected = bundles._canonical(bundles._context_bound_document(self.prepared, self.context))
        original_write = registry._write_private_pending

        def mutate_caller(path, raw, *, root):
            original_write(path, raw, root=root)
            self.prepared.transition.after._document["apps"][self.fixture.app]["label"] = "Synthetic changed caller"
            object.__setattr__(self.context, "reviewer_claim", "person:changed-caller")

        with mock.patch.object(registry, "_write_private_pending", side_effect=mutate_caller):
            self.save()
        self.assertEqual(self.path.read_bytes(), expected)
        loaded = self.load()
        self.assertEqual(loaded.context.reviewer_claim, "person:synthetic")
        self.assertEqual(loaded.prepared.transition.after._document["apps"][self.fixture.app]["label"], "Synthetic app")


if __name__ == "__main__":
    unittest.main()
