"""Actual original registry registration; caller retains selectors before write."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import exact_human_approval as approval
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_registration as subject
from wom_kit import work_session_registry as registry
from wom_kit import work_session_registry_intent as intents


LABEL = "Synthetic private registration label"


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-registration-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        self.root.mkdir()
        self.archive_id = "archive:personal:synthetic-registration"
        (self.root / "archive.yml").write_text("archive_id: " + self.archive_id + "\n", encoding="utf-8")
        self.store = registry.WorkSessionRegistryStore(
            self.root, approval.exact_human_approval_archive_identity_sha256(self.archive_id),
        )

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def preview(self):
        return subject.preview_registration(self.root, label=LABEL)

    def apply(self, selected, **changes):
        arguments = dict(selection=selected, label=LABEL)
        arguments.update(changes)
        return subject.apply_or_resume_registration(self.root, **arguments)

    def reject(self, call, code=None):
        with self.assertRaises(subject.WorkSessionRegistrationError) as caught:
            call()
        if code is not None:
            self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn(LABEL, repr(caught.exception))
        self.assertNotIn(str(self.root), repr(caught.exception))
        self.assertNotIn("private_error_marker", repr(caught.exception))

    def test_preview_has_only_content_free_original_selectors_no_lock_intent_or_write(self):
        before = self.files()
        with patch.object(exact.ExactOperationWriterLock, "__enter__", side_effect=AssertionError("preview acquired lock")), \
                patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("preview prepared intent")), \
                patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("preview committed")):
            selected = self.preview()
        self.assertEqual(set(selected), subject._SELECTION_KEYS)
        self.assertEqual(selected["before_sha256"], self.store.read().sha256)
        self.assertTrue(registry._ref(selected["client_app_ref"], "client_app"))
        self.assertEqual(selected["label_sha256"], registry._label_digest(LABEL))
        self.assertNotIn(LABEL, json.dumps(selected))
        self.assertNotIn(str(self.root), json.dumps(selected))
        self.assertEqual(self.files(), before)
        self.assertFalse((self.root / "profiles").exists())

    def test_preview_generation_drift_refuses_without_replanning(self):
        original = registry.plan_transition
        calls = []

        def changed(snapshot, **kwargs):
            calls.append(kwargs["label"])
            planned = original(snapshot, **kwargs)
            # The real external commit also replays its own original request.
            # Inject only after this preview, not inside that independent replay.
            if kwargs["label"] != LABEL:
                return planned
            other = original(snapshot, action="register-app", label="Synthetic other app")
            with exact.ExactOperationWriterLock(self.root) as held:
                self.store.commit(other, held_lock=held)
            return planned

        with patch.object(registry, "plan_transition", new=changed):
            self.reject(self.preview, "work_session_registration_changed")
        self.assertEqual(calls.count(LABEL), 1)
        self.assertEqual(self.store.read().revision, 1)
        self.assertFalse(self.root.joinpath(*intents.PRIVATE_ROOT).exists())

    def test_apply_and_original_resume_keep_one_app_and_stored_identity_after_other_generation(self):
        selected = self.preview()
        result = self.apply(selected)
        self.assertEqual(result["status"], "committed")
        self.assertEqual(result["client_app_ref"], selected["client_app_ref"])
        self.assertEqual(result["identity_level"], "self_declared")
        for flag in ("human_approval_granted", "current_claim_authority_evaluated", "identity_is_app_attestation",
                     "routing_is_write_authority", "private_labels_echoed", "claim_refs_echoed"):
            self.assertIs(result[flag], False)
        self.assertEqual(self.store.read().revision, 1)
        other = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic other app")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(other, held_lock=held)
        before = self.files()
        with patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("old registration wrote")), \
                patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("old intent regenerated")):
            resumed = self.apply(selected)
        self.assertEqual(resumed["status"], "already_committed")
        self.assertEqual(resumed["client_app_ref"], selected["client_app_ref"])
        self.assertEqual(resumed["target_revision"], 1)
        self.assertEqual(self.files(), before)
        self.assertNotIn(LABEL, json.dumps(result) + json.dumps(resumed))
        self.assertNotIn(str(self.root), json.dumps(result) + json.dumps(resumed))

    def test_bad_selection_types_extra_private_fields_and_changed_original_are_zero_effects(self):
        selected = self.preview()

        class StringSubclass(str):
            pass

        variants = [None, [], True, {**selected, "credential": "private_error_marker"},
                    {**selected, "schema": StringSubclass(selected["schema"])},
                    {StringSubclass(key): value for key, value in selected.items()}]
        for key in selected:
            missing = dict(selected)
            del missing[key]
            variants.append(missing)
            variants.append({**selected, key: True})
        variants.extend([
            {**selected, "client_app_ref": registry._new_ref("client_app")},
            {**selected, "plan_sha256": "sha256:" + "a" * 64},
            {**selected, "before_sha256": "sha256:" + "a" * 64},
            {**selected, "label_sha256": "sha256:" + "a" * 64},
            {**selected, "archive_identity_sha256": "sha256:" + "a" * 64},
        ])
        before = self.files()
        with patch.object(intents, "save_registry_intent", side_effect=AssertionError("invalid selection saved")), \
                patch.object(registry.WorkSessionRegistryStore, "commit", side_effect=AssertionError("invalid selection wrote")):
            for value in variants:
                with self.subTest(index=variants.index(value)):
                    self.reject(lambda value=value: self.apply(value))
            self.reject(lambda: self.apply(selected, label=LABEL + " changed"))
            changed = {**selected, "label_sha256": registry._label_digest(LABEL + " changed")}
            self.reject(lambda: self.apply(changed, label=LABEL + " changed"))
        self.assertEqual(self.files(), before)

    def test_existing_intent_requires_original_app_label_and_predecessor(self):
        selected = self.preview()
        self.apply(selected)
        before = self.files()
        variants = [{**selected, "client_app_ref": registry._new_ref("client_app")},
                    {**selected, "before_sha256": "sha256:" + "a" * 64}]
        with patch.object(intents, "observe_or_apply_registry_intent", side_effect=AssertionError("wrong original reached writer")):
            for value in variants:
                self.reject(lambda value=value: self.apply(value), "work_session_registration_changed")
            label = LABEL + " changed"
            self.reject(lambda: self.apply({**selected, "label_sha256": registry._label_digest(label)}, label=label),
                        "work_session_registration_changed")
        self.assertEqual(self.files(), before)

    def test_missing_intent_after_actual_commit_never_manufactures_original_evidence(self):
        selected = self.preview()
        transition = registry.plan_transition(self.store.read(), action="register-app", label=LABEL,
                                               _ref_factory=lambda _prefix: selected["client_app_ref"])
        self.assertEqual(transition.plan_sha256, selected["plan_sha256"])
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(transition, held_lock=held)
        before = self.files()
        with patch.object(intents, "prepare_registry_intent", side_effect=AssertionError("manufactured evidence")), \
                patch.object(intents, "save_registry_intent", side_effect=AssertionError("saved invented history")):
            self.reject(lambda: self.apply(selected), "work_session_registration_changed")
        self.assertEqual(self.files(), before)
        self.assertFalse(self.root.joinpath(*intents.PRIVATE_ROOT).exists())

    def test_actual_predecessor_or_archive_change_refuses_without_intent(self):
        selected = self.preview()
        other = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic other app")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(other, held_lock=held)
        before = self.files()
        self.reject(lambda: self.apply(selected), "work_session_registration_changed")
        self.assertEqual(self.files(), before)
        (self.root / "archive.yml").write_text("archive_id: archive:personal:synthetic-other-registration\n", encoding="utf-8")
        changed = self.files()
        self.reject(lambda: self.apply(selected), "work_session_registration_changed")
        self.assertEqual(self.files(), changed)

    def test_cancellation_and_private_errors_do_not_echo_or_write(self):
        selected = self.preview()
        before = self.files()
        with exact.ExactOperationWriterLock(self.root):
            self.reject(lambda: self.apply(selected, cancel_requested=lambda: True), "work_session_registration_cancelled")
        self.assertEqual(self.files(), before)
        with patch.object(intents, "load_registry_intent", side_effect=OSError("private_error_marker " + LABEL + str(self.root))):
            self.reject(lambda: self.apply(selected), "work_session_registration_unavailable")
        self.assertEqual(self.files(), before)

    def test_wait_progress_cannot_mutate_retained_original_selection(self):
        selected = self.preview()
        original = dict(selected)

        def progress(_event):
            selected["client_app_ref"] = registry._new_ref("client_app")
            selected["plan_sha256"] = "sha256:" + "b" * 64

        result = self.apply(selected, progress=progress)
        self.assertEqual(result["client_app_ref"], original["client_app_ref"])
        self.assertEqual(result["plan_sha256"], original["plan_sha256"])
        self.assertEqual(list(self.store.read()._document["apps"]), [original["client_app_ref"]])

    def test_real_child_cuts_resume_same_original_identity_and_single_generation(self):
        child = r'''
import json, os, sys
from pathlib import Path
from wom_kit import work_session_registration as subject, work_session_registry as registry
from wom_kit import work_session_registry_intent as intents
root, selection_json, mode = sys.argv[1:]
selection = json.loads(selection_json)
if mode in {'before_intent', 'after_intent'}:
    original_save = intents.save_registry_intent
    def save(*args, **kwargs):
        if mode == 'before_intent':
            os._exit(71)
        result = original_save(*args, **kwargs)
        os._exit(72)
    intents.save_registry_intent = save
elif mode == 'after_commit':
    original_commit = registry.WorkSessionRegistryStore.commit
    def commit(*args, **kwargs):
        result = original_commit(*args, **kwargs)
        os._exit(73)
    registry.WorkSessionRegistryStore.commit = commit
result = subject.apply_or_resume_registration(Path(root), selection=selection,
    label='Synthetic private registration label')
print(json.dumps(result, sort_keys=True))
'''
        environment = dict(os.environ)
        kit = Path(__file__).resolve().parents[1]
        environment["PYTHONPATH"] = str(kit / "src")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        for mode, code in (("before_intent", 71), ("after_intent", 72), ("after_commit", 73)):
            with self.subTest(stage=mode):
                case_root = self.root.parent / mode
                case_root.mkdir()
                (case_root / "archive.yml").write_text("archive_id: " + self.archive_id + "\n", encoding="utf-8")
                selected = subject.preview_registration(case_root, label=LABEL)
                retained = json.dumps(selected, sort_keys=True)
                command = [sys.executable, "-B", "-c", child, str(case_root), retained]
                cut = subprocess.run([*command, mode], env=environment, capture_output=True, text=True,
                                     encoding="utf-8", timeout=90, **options)
                self.assertEqual((cut.returncode, cut.stdout, cut.stderr), (code, "", ""))
                store = registry.WorkSessionRegistryStore(case_root, selected["archive_identity_sha256"])
                self.assertEqual(store.read().revision, 1 if mode == "after_commit" else 0)
                intent_files = list(case_root.joinpath(*intents.PRIVATE_ROOT).glob("*.json"))
                self.assertEqual(len(intent_files), 0 if mode == "before_intent" else 1)
                resumed = subprocess.run([*command, "resume"], env=environment, capture_output=True, text=True,
                                         encoding="utf-8", timeout=90, **options)
                self.assertEqual((resumed.returncode, resumed.stderr), (0, ""))
                result = json.loads(resumed.stdout)
                self.assertTrue(result["ok"])
                self.assertEqual(result["client_app_ref"], selected["client_app_ref"])
                self.assertEqual(result["plan_sha256"], selected["plan_sha256"])
                self.assertEqual(store.read().revision, 1)
                self.assertEqual(list(store.read()._document["apps"]), [selected["client_app_ref"]])
                self.assertEqual(len(list(case_root.joinpath(*intents.PRIVATE_ROOT).glob("*.json"))), 1)
                self.assertNotIn(LABEL, resumed.stdout)
                self.assertFalse(case_root.joinpath("profiles", "local", "work-sessions", "actors").exists())


if __name__ == "__main__":
    unittest.main()
