"""Original nonhuman intents survive output loss without becoming authority."""

from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from wom_kit import exact_human_approval as approval
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_registry as registry
from wom_kit import work_session_registry_intent as intents


ARCHIVE_ID = "archive:personal:synthetic-registry-intent"


class RegistryIntentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="wom-registry-intent-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text("archive_id: " + ARCHIVE_ID + "\n", encoding="utf-8")
        self.store = registry.WorkSessionRegistryStore(
            self.root, approval.exact_human_approval_archive_identity_sha256(ARCHIVE_ID),
        )
        self.directory = self.root.joinpath(*intents.PRIVATE_ROOT)

    def register_plan(self, label="Synthetic private app"):
        return registry.plan_transition(self.store.read(), action="register-app", label=label)

    def commit_fixture(self, transition):
        # Synthetic predecessor setup only; the new intent API never accepts
        # this human-authority seam or admits the create action.
        with exact.ExactOperationWriterLock(self.root) as held:
            return self.store.commit(transition, held_lock=held,
                                     verify_human_authority=lambda digest: digest == transition.plan_sha256)

    def claim_plan(self):
        app = self.register_plan()
        self.commit_fixture(app)
        create = registry.plan_transition(self.store.read(), action="create",
                                          client_app_ref=app.result_refs[0], label="Synthetic private task")
        self.commit_fixture(create)
        return registry.plan_transition(self.store.read(), action="claim",
                                        client_app_ref=app.result_refs[0], work_session_ref=create.result_refs[-1])

    def prepare_save(self, plan):
        with exact.ExactOperationWriterLock(self.root) as held:
            intent = intents.prepare_registry_intent(self.store, plan, held_lock=held)
            intents.save_registry_intent(self.store, intent, held_lock=held)
        return intent

    def load(self, digest):
        with exact.ExactOperationWriterLock(self.root) as held:
            return intents.load_registry_intent(self.store, plan_sha256=digest, held_lock=held)

    def apply(self, digest):
        with exact.ExactOperationWriterLock(self.root) as held:
            return intents.observe_or_apply_registry_intent(self.store, plan_sha256=digest, held_lock=held)

    def path(self, digest):
        return self.directory / (digest[7:] + ".json")

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def assert_fixed(self, call, code=None):
        with self.assertRaises(intents.WorkSessionRegistryIntentError) as caught:
            call()
        self.assertIn(caught.exception.code, intents._ERRORS)
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn("Synthetic", repr(caught.exception))
        self.assertNotIn(str(self.root), str(caught.exception))

    def rehash(self, document):
        document["intent_sha256"] = intents._sha(intents._canonical(
            {key: value for key, value in document.items() if key != "intent_sha256"},
        ))
        return intents._canonical(document)

    def test_minimal_private_intent_roundtrip_is_not_a_registry_write_or_approval(self):
        plan = self.register_plan()
        before = self.store.read().sha256
        intent = self.prepare_save(plan)
        self.assertEqual(self.store.read().sha256, before)
        raw = self.path(intent.plan_sha256).read_bytes()
        document = json.loads(raw)
        self.assertEqual(set(document), intents._DOCUMENT_KEYS)
        self.assertNotIn("after", document)
        self.assertNotIn("apps", document)
        self.assertLess(len(raw), 64 * 1024)
        self.assertEqual(document["request"], plan._request)
        self.assertEqual(document["generated_refs"], list(plan._generated_refs))
        self.assertIn(b"Synthetic private app", raw)
        self.assertEqual(len(list(self.directory.iterdir())), 1)
        before_files = self.files()
        with mock.patch.object(registry, "_write_private_pending", side_effect=AssertionError("load wrote")):
            restored = self.load(intent.plan_sha256)
        self.assertEqual(self.files(), before_files)
        self.assertEqual(restored, intent)
        public = json.dumps(restored.public_summary())
        for private in ("Synthetic private app", str(self.root), plan._generated_refs[0]):
            self.assertNotIn(private, public)
            self.assertNotIn(private, repr(restored))
        self.assertFalse(restored.public_summary()["current_claim_authority_evaluated"])
        self.assertFalse((self.root / "profiles/local/exact-human-approvals").exists())
        self.assertFalse((self.root / "receipts").exists())

    def test_register_commit_and_reobserve_never_mint_another_reference(self):
        plan = self.register_plan()
        intent = self.prepare_save(plan)
        with mock.patch.dict(registry.plan_transition.__kwdefaults__,
                             {"_ref_factory": lambda _prefix: self.fail("new reference requested")}):
            first = self.apply(intent.plan_sha256)
            files = self.files()
            with mock.patch.object(self.store, "commit", side_effect=AssertionError("committed again")):
                second = self.apply(intent.plan_sha256)
        self.assertEqual((first.status, second.status), ("committed", "already_committed"))
        self.assertEqual(first.transition, plan)
        self.assertEqual(second.transition, plan)
        self.assertEqual(self.store.read().revision, 1)
        self.assertEqual(self.files(), files)

    def test_claim_history_is_observed_after_pause_but_is_not_current_claim_authority(self):
        plan = self.claim_plan()
        intent = self.prepare_save(plan)
        outcome = self.apply(intent.plan_sha256)
        session = plan._request["work_session_ref"]
        claim = plan.after._document["sessions"][session]["claim_ref"]
        paused = registry.plan_transition(self.store.read(), action="pause",
                                          client_app_ref=plan._request["client_app_ref"],
                                          work_session_ref=session, claim_ref=claim)
        self.commit_fixture(paused)
        before = self.files()
        historical = self.apply(intent.plan_sha256)
        self.assertEqual(historical.status, "already_committed")
        self.assertEqual(historical.transition, outcome.transition)
        self.assertEqual(self.files(), before)
        self.assertEqual(self.store.read().sha256, paused.after.sha256)
        self.assertNotIn(claim, json.dumps(historical.public_summary()))
        self.assertFalse(historical.public_summary()["current_claim_authority_evaluated"])
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(registry.WorkSessionRegistryError):
                self.store.require_claimed_binding(client_app_ref=plan._request["client_app_ref"],
                                                   work_session_ref=session, claim_ref=claim, held_lock=held)

    def test_other_transition_occupying_target_rejects_without_new_plan_or_writes(self):
        plan = self.register_plan()
        intent = self.prepare_save(plan)
        other = self.register_plan("Synthetic other app")
        self.commit_fixture(other)
        before = self.files()
        with mock.patch.object(self.store, "commit", side_effect=AssertionError("drift committed")):
            self.assert_fixed(lambda: self.apply(intent.plan_sha256), "work_session_registry_intent_changed")
        self.assertEqual(self.files(), before)
        self.assertEqual(self.store.read().sha256, other.after.sha256)

    def test_human_and_remaining_unimplemented_nonhuman_actions_are_refused(self):
        plan = self.claim_plan()
        intent = self.prepare_save(plan)
        document = json.loads(intent._raw)
        for action in ("create", "handoff", "accept", "recover", "complete"):
            with self.subTest(action=action):
                changed = deepcopy(document)
                changed["request"]["action"] = action
                raw = self.rehash(changed)
                self.assert_fixed(lambda: intents.RegistryTransitionIntent(raw),
                                  "work_session_registry_intent_action_refused")
        create = registry.plan_transition(self.store.read(), action="create",
                                          client_app_ref=plan._request["client_app_ref"], label="Synthetic another task")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.assert_fixed(lambda: intents.prepare_registry_intent(self.store, create, held_lock=held),
                              "work_session_registry_intent_action_refused")

    def test_strict_schema_and_rehashed_request_or_reference_forgery_are_refused(self):
        plan = self.claim_plan()
        intent = self.prepare_save(plan)
        path, original = self.path(intent.plan_sha256), intent._raw
        base = json.loads(original)
        changes = [
            ("before_revision", True), ("before_revision", 0), ("before_sha256", "sha256:" + "f" * 64),
            ("after_sha256", "sha256:" + "f" * 64), ("plan_sha256", "sha256:" + "f" * 64),
            ("generated_refs", []), ("generated_refs", ["claim_" + "f" * 32]),
            ("generated_refs", ["client_app_" + "f" * 32]), ("extra", "Synthetic private arbitrary payload"),
        ]
        mutations = [original + b"\n", original.replace(b'"schema":', b'"schema":"duplicate","schema":', 1)]
        for key, value in changes:
            changed = deepcopy(base)
            changed[key] = value
            mutations.append(self.rehash(changed))
        for key, value in (("client_app_ref", "client_app_" + "f" * 32),
                           ("work_session_ref", "work_session_" + "f" * 32),
                           ("claim_ref", "claim_" + "f" * 32), ("label", "Synthetic injected label"),
                           ("provider", "Synthetic injected key")):
            changed = deepcopy(base)
            changed["request"][key] = value
            mutations.append(self.rehash(changed))
        for index, raw in enumerate(mutations):
            with self.subTest(index=index):
                self.assertNotEqual(raw, original, "mutation fixture must actually alter bytes")
                path.write_bytes(raw)
                self.assert_fixed(lambda: self.apply(intent.plan_sha256))
                self.assertEqual(path.read_bytes(), raw)
                self.assertEqual(self.store.read().revision, plan.after.revision - 1)
        path.write_bytes(original)

    def test_forged_after_image_and_other_app_claim_do_not_get_saved(self):
        app = self.register_plan()
        self.commit_fixture(app)
        other = self.register_plan("Synthetic second app")
        self.commit_fixture(other)
        create = registry.plan_transition(self.store.read(), action="create",
                                          client_app_ref=app.result_refs[0], label="Synthetic private task")
        self.commit_fixture(create)
        plan = registry.plan_transition(self.store.read(), action="claim", client_app_ref=app.result_refs[0],
                                        work_session_ref=create.result_refs[-1])
        foreign = replace(plan, _request={**plan._request, "client_app_ref": other.result_refs[0]})
        after = deepcopy(plan.after._document)
        after["apps"][plan._request["client_app_ref"]]["label"] = "Synthetic hidden mutation"
        forged = replace(plan, after=registry.RegistrySnapshot(after))
        forged = replace(forged, plan_sha256=registry._digest(forged._basis()))
        before = self.files()
        with exact.ExactOperationWriterLock(self.root) as held:
            for invalid in (foreign, forged):
                with self.subTest(kind="foreign" if invalid is foreign else "postimage"):
                    self.assert_fixed(lambda: intents.prepare_registry_intent(self.store, invalid, held_lock=held))
        self.assertEqual(self.files(), before)
        self.assertFalse(self.directory.exists())

    def test_lock_archive_and_explicit_identifier_are_required_without_creating_intent(self):
        plan = self.register_plan()
        other = self.root.parent / "other"
        other.mkdir()
        (other / "archive.yml").write_text("archive_id: archive:personal:synthetic-other\n", encoding="utf-8")
        other_store = registry.WorkSessionRegistryStore(other, self.store.archive_identity_sha256)
        for held in (None, True, exact.ExactOperationWriterLock(self.root)):
            self.assert_fixed(lambda: intents.prepare_registry_intent(self.store, plan, held_lock=held),
                              "work_session_registry_intent_lock_required")
        with exact.ExactOperationWriterLock(other) as held:
            self.assert_fixed(lambda: intents.prepare_registry_intent(self.store, plan, held_lock=held),
                              "work_session_registry_intent_lock_required")
            self.assert_fixed(lambda: intents.prepare_registry_intent(other_store, plan, held_lock=held),
                              "work_session_registry_intent_changed")
        with exact.ExactOperationWriterLock(self.root) as held:
            for invalid in (None, True, [], "../private", "sha256:" + "A" * 64):
                self.assert_fixed(lambda: intents.load_registry_intent(self.store, plan_sha256=invalid, held_lock=held))
        self.assertFalse(self.directory.exists())

    def test_existing_bytes_are_never_replaced_and_late_intent_is_not_manufactured(self):
        plan = self.register_plan()
        intent = self.prepare_save(plan)
        path = self.path(intent.plan_sha256)
        before = os.lstat(path)
        with exact.ExactOperationWriterLock(self.root) as held:
            with mock.patch.object(registry, "_write_private_pending", side_effect=AssertionError("resave wrote")):
                intents.save_registry_intent(self.store, intent, held_lock=held)
        after = os.lstat(path)
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
        self.apply(intent.plan_sha256)
        path.unlink()
        with exact.ExactOperationWriterLock(self.root) as held:
            self.assert_fixed(lambda: intents.save_registry_intent(self.store, intent, held_lock=held),
                              "work_session_registry_intent_changed")
        self.assertFalse(path.exists())

    def test_payload_limit_hardlink_reparse_and_private_error_chain(self):
        intent = self.prepare_save(self.register_plan())
        path = self.path(intent.plan_sha256)
        original = path.read_bytes()
        path.write_bytes(b"x" * (intents.MAX_INTENT_BYTES + 1))
        self.assert_fixed(lambda: self.load(intent.plan_sha256))
        path.write_bytes(original)
        alias = self.root.parent / "synthetic-hardlink"
        os.link(path, alias)
        self.assert_fixed(lambda: self.load(intent.plan_sha256))
        alias.unlink()
        native_lstat = os.lstat

        class Reparse:
            def __init__(self, info):
                self.info = info
                self.st_file_attributes = getattr(info, "st_file_attributes", 0) | 0x400

            def __getattr__(self, name):
                return getattr(self.info, name)

        def lstat(target, *args, **kwargs):
            observed = native_lstat(target, *args, **kwargs)
            return Reparse(observed) if Path(target) == self.directory else observed

        with mock.patch.object(os, "lstat", side_effect=lstat):
            self.assert_fixed(lambda: self.load(intent.plan_sha256), "work_session_registry_intent_path_unsafe")
        with mock.patch.object(intents.bundle, "_read_control", side_effect=OSError("Synthetic private path/key")):
            self.assert_fixed(lambda: self.load(intent.plan_sha256))
        self.assertEqual(path.read_bytes(), original)

    def test_saved_payload_changed_at_commit_boundary_never_commits(self):
        intent = self.prepare_save(self.register_plan())
        path = self.path(intent.plan_sha256)
        original_read = intents._read_raw
        calls = []

        def change_on_second_read(store, digest):
            calls.append(True)
            if len(calls) == 2:
                path.write_bytes(b"Synthetic changed original intent")
            return original_read(store, digest)

        with mock.patch.object(intents, "_read_raw", side_effect=change_on_second_read):
            with mock.patch.object(self.store, "commit", side_effect=AssertionError("changed source committed")):
                self.assert_fixed(lambda: self.apply(intent.plan_sha256))
        self.assertEqual(self.store.read().revision, 0)

    def test_lost_lock_after_private_pending_write_preserves_bytes_without_publication(self):
        plan = self.register_plan()
        original = registry._write_private_pending
        with exact.ExactOperationWriterLock(self.root) as held:
            intent = intents.prepare_registry_intent(self.store, plan, held_lock=held)

            def lose_lock(path, raw, *, root):
                original(path, raw, root=root)
                held.__exit__(None, None, None)

            with mock.patch.object(registry, "_write_private_pending", side_effect=lose_lock):
                self.assert_fixed(lambda: intents.save_registry_intent(self.store, intent, held_lock=held),
                                  "work_session_registry_intent_durability_unknown")
        self.assertFalse(self.path(intent.plan_sha256).exists())
        pending = list(self.directory.glob(".pending_*"))
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].read_bytes(), intent._raw)
        self.assertEqual(self.store.read().revision, 0)

    def test_copied_original_intent_is_not_valid_for_a_different_archive(self):
        intent = self.prepare_save(self.register_plan())
        other = self.root.parent / "other-real-archive"
        other.mkdir()
        archive_id = "archive:personal:synthetic-different-intent"
        (other / "archive.yml").write_text("archive_id: " + archive_id + "\n", encoding="utf-8")
        store = registry.WorkSessionRegistryStore(other, approval.exact_human_approval_archive_identity_sha256(archive_id))
        directory = other.joinpath(*intents.PRIVATE_ROOT)
        directory.mkdir(parents=True)
        copied = directory / self.path(intent.plan_sha256).name
        copied.write_bytes(intent._raw)
        with exact.ExactOperationWriterLock(other) as held:
            self.assert_fixed(lambda: intents.observe_or_apply_registry_intent(
                store, plan_sha256=intent.plan_sha256, held_lock=held), "work_session_registry_intent_changed")
        self.assertEqual(store.read().revision, 0)
        self.assertEqual(copied.read_bytes(), intent._raw)

    @unittest.skipUnless(os.name == "nt", "native retained Windows parent")
    def test_private_intent_write_keeps_its_real_windows_parent_retained(self):
        original = registry.durable._write_new
        attempts = []

        def write(path, raw, *, within):
            if path.parent == self.directory:
                with self.assertRaises(OSError):
                    path.parent.rename(path.parent.with_name("synthetic-moved-intents"))
                attempts.append(True)
            return original(path, raw, within=within)

        with mock.patch.object(registry.durable, "_write_new", side_effect=write):
            intent = self.prepare_save(self.register_plan())
        self.assertEqual(attempts, [True])
        self.assertEqual(self.path(intent.plan_sha256).read_bytes(), intent._raw)
        self.assertFalse(self.directory.with_name("synthetic-moved-intents").exists())

    @unittest.skipUnless(os.name == "nt", "native Windows last-check-to-publish boundary")
    def test_last_pending_verification_to_move_keeps_original_parent_retained(self):
        original = registry.durable._atomic_move_file_no_replace
        attempts = []

        def move(source, destination, *, expected_parent_identity=None):
            with self.assertRaises(OSError):
                source.parent.rename(source.parent.with_name("synthetic-replacement-cut"))
            actual = os.lstat(source.parent)
            self.assertEqual(expected_parent_identity, (actual.st_dev, actual.st_ino))
            attempts.append(True)
            return original(source, destination, expected_parent_identity=expected_parent_identity)

        with mock.patch.object(registry.durable, "_atomic_move_file_no_replace", side_effect=move):
            intent = self.prepare_save(self.register_plan())
        self.assertEqual(attempts, [True])
        self.assertEqual(self.path(intent.plan_sha256).read_bytes(), intent._raw)
        self.assertFalse(self.directory.with_name("synthetic-replacement-cut").exists())

    def test_real_process_exit_after_commit_reopens_original_claim_without_new_reference(self):
        plan = self.claim_plan()
        intent = self.prepare_save(plan)
        script = (
            "import json, os, sys\nfrom pathlib import Path\n"
            "from wom_kit import exact_human_approval as a, exact_operation_manifest as e\n"
            "from wom_kit import work_session_registry as r, work_session_registry_intent as i\n"
            "root, archive_id = a._archive_identity(Path(sys.argv[1]))\n"
            "store = r.WorkSessionRegistryStore(root, a.exact_human_approval_archive_identity_sha256(archive_id))\n"
            "def refuse_new_ref(_prefix): raise AssertionError('unexpected new reference')\n"
            "r.plan_transition.__kwdefaults__['_ref_factory'] = refuse_new_ref\n"
            "original = store.commit\n"
            "def cut(*args, **kwargs):\n"
            " result = original(*args, **kwargs)\n"
            " os._exit(73)\n"
            "if sys.argv[3] == 'cut': store.commit = cut\n"
            "with e.ExactOperationWriterLock(root) as held:\n"
            " result = i.observe_or_apply_registry_intent(store, plan_sha256=sys.argv[2], held_lock=held)\n"
            "print(json.dumps(result.public_summary(), sort_keys=True))\n"
        )
        command = [sys.executable, "-B", "-c", script, str(self.root), intent.plan_sha256]
        options = dict(capture_output=True, text=True, timeout=60,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        crashed = subprocess.run([*command, "cut"], **options)
        self.assertEqual(crashed.returncode, 73, crashed.stderr)
        self.assertEqual(crashed.stdout, "")
        self.assertEqual(self.store.read().sha256, plan.after.sha256)
        before = self.files()
        resumed = subprocess.run([*command, "resume"], **options)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        result = json.loads(resumed.stdout)
        self.assertEqual(result["status"], "already_committed")
        self.assertFalse(result["current_claim_authority_evaluated"])
        self.assertEqual(self.store.read().revision, plan.after.revision)
        self.assertEqual(self.files(), before)
        self.assertNotIn(plan._generated_refs[0], resumed.stdout)


if __name__ == "__main__":
    unittest.main()
