"""Synthetic per-app/task routing with the real registry and writer lock."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError
import io
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
from wom_kit import work_session_actor as actor
from wom_kit import work_session_registry as registry


ARCHIVE_ID = "archive:personal:synthetic-actor-context"


class WorkSessionActorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-actor-context-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text("archive_id: " + ARCHIVE_ID + "\n", encoding="utf-8")
        self.registry = registry.WorkSessionRegistryStore(
            self.root, approval.exact_human_approval_archive_identity_sha256(ARCHIVE_ID))
        self.app = self.transition(action="register-app", label="Synthetic private app").result_refs[0]
        self.other_app = self.transition(action="register-app", label="Synthetic second app").result_refs[0]
        self.session = self.transition(action="create", client_app_ref=self.app,
                                       label="Synthetic private task").result_refs[-1]
        self.transition(action="claim", client_app_ref=self.app, work_session_ref=self.session)
        self.claim = self.registry.read()._document["sessions"][self.session]["claim_ref"]
        self.binding = self.registry.read().binding(self.session)
        self.route = actor.new_task_route_ref()
        self.actor = actor.WorkSessionActorStore(self.registry, client_app_ref=self.app,
                                                task_route_ref=self.route)
        self.directory = self.root.joinpath(*actor.PRIVATE_ROOT, self.app, self.route)

    def transition(self, **request):
        planned = registry.plan_transition(self.registry.read(), **request)
        with exact.ExactOperationWriterLock(self.root) as held:
            self.registry.commit(planned, held_lock=held,
                                 verify_human_authority=lambda digest: digest == planned.plan_sha256)
        return planned

    def fields(self, **changes):
        result = {"work_session_ref": self.session, "claim_ref": self.claim,
                  "observed_binding": self.binding}
        result.update(changes)
        return result

    def save(self, expected=None, **changes):
        with exact.ExactOperationWriterLock(self.root) as held:
            return self.actor.save(expected_sha256=expected, held_lock=held, **self.fields(**changes))

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()
                and path.name != ".writer.lock"}

    def rejected(self, call, code=None):
        before = self.files()
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            with self.assertRaises(actor.WorkSessionActorError) as caught:
                call()
        self.assertIn(str(caught.exception), actor._ERRORS)
        if code:
            self.assertEqual(str(caught.exception), code)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        for value in (self.app, self.route, self.claim, self.session, str(self.root), "Synthetic private"):
            self.assertNotIn(value, repr(caught.exception) + output.getvalue() + errors.getvalue())
        self.assertEqual(output.getvalue() + errors.getvalue(), "")
        self.assertEqual(self.files(), before)

    def test_missing_read_is_write_free_and_never_selects_another_app(self):
        before = self.files()
        self.assertIsNone(self.actor.read())
        self.assertFalse(self.directory.exists())
        self.assertEqual(self.files(), before)
        self.save()
        other = actor.WorkSessionActorStore(self.registry, client_app_ref=self.other_app,
                                            task_route_ref=self.route)
        self.assertIsNone(other.read())
        self.assertFalse(self.root.joinpath(*actor.PRIVATE_ROOT, self.other_app).exists())

    def test_private_context_roundtrip_detaches_and_does_not_attest_the_app(self):
        initial = self.save()
        restored = self.actor.read()
        self.assertEqual(initial._raw, restored._raw)
        with self.assertRaises(FrozenInstanceError):
            restored._raw = b"private replacement"
        private_view = restored.document()
        private_view["observed_binding"]["revision"] = 99
        self.assertEqual(restored.document()["observed_binding"], self.binding.document())
        summary = restored.public_summary()
        self.assertEqual(summary["routing_identity_level"], "self_declared")
        self.assertEqual(summary["scope"], "private_actor_routing")
        self.assertNotIn("identity_level", summary)
        self.assertFalse(summary["identity_is_app_attestation"])
        self.assertFalse(summary["routing_is_write_authority"])
        for value in (self.app, self.route, self.session, self.claim, str(self.root), "Synthetic private"):
            self.assertNotIn(value, json.dumps(summary) + repr(restored) + repr(self.actor))
        self.assertEqual(self.registry.read()._document["apps"][self.app]["identity_level"], "human_confirmed")

    def test_identical_save_is_noop_but_still_requires_exact_cas_and_lock(self):
        initial = self.save()
        before = self.files()
        self.assertEqual(self.save(initial.sha256)._raw, initial._raw)
        self.assertEqual(self.files(), before)
        self.rejected(lambda: self.save(), "work_session_actor_changed")
        self.rejected(lambda: self.actor.save(expected_sha256=initial.sha256,
                                              held_lock=None, **self.fields()),
                      "work_session_actor_lock_required")

    def test_selection_update_is_append_only_and_cannot_rebind_the_app(self):
        initial = self.save()
        cleared = self.save(initial.sha256, work_session_ref=None, claim_ref=None, observed_binding=None)
        self.assertEqual(cleared.document()["revision"], 2)
        self.assertEqual(cleared.document()["previous_sha256"], initial.sha256)
        self.assertEqual((self.directory / "000000000001.json").read_bytes(), initial._raw)
        self.assertEqual(self.actor.read()._raw, cleared._raw)
        self.rejected(lambda: self.save(initial.sha256), "work_session_actor_changed")
        changed = initial.document()
        changed["client_app_ref"] = self.other_app
        basis = {key: value for key, value in changed.items() if key != "actor_sha256"}
        changed["actor_sha256"] = actor._sha(registry._canonical(basis))
        self.rejected(lambda: actor.ActorContext(registry._canonical(changed)))

    def test_bad_or_unregistered_selector_never_creates_actor_files(self):
        for reference in (None, True, "../private", "client_app_" + "0" * 32):
            with self.subTest(kind=type(reference).__name__):
                self.rejected(lambda: actor.WorkSessionActorStore(self.registry, client_app_ref=reference,
                                                                  task_route_ref=self.route))
        self.assertFalse(self.directory.exists())

    def test_missing_malformed_and_unselected_task_route_never_fall_back(self):
        self.save()
        self.rejected(lambda: actor.WorkSessionActorStore(self.registry, client_app_ref=self.app))
        for reference in (None, True, "../private", self.app, "task_route_" + "A" * 32):
            with self.subTest(kind=type(reference).__name__):
                self.rejected(lambda: actor.WorkSessionActorStore(self.registry, client_app_ref=self.app,
                                                                  task_route_ref=reference))
        before = self.files()
        missing = actor.WorkSessionActorStore(self.registry, client_app_ref=self.app,
                                              task_route_ref=actor.new_task_route_ref())
        self.assertIsNone(missing.read())
        self.assertEqual(self.files(), before)

    def test_wrong_unheld_released_and_foreign_real_lock_are_rejected(self):
        unheld = exact.ExactOperationWriterLock(self.root)
        with exact.ExactOperationWriterLock(self.root) as released:
            released.verify_held()
        for lock in (None, True, object(), unheld, released):
            with self.subTest(kind=type(lock).__name__):
                self.rejected(lambda: self.actor.save(expected_sha256=None, held_lock=lock, **self.fields()),
                              "work_session_actor_lock_required")
        other = self.root.parent / "other"
        other.mkdir()
        (other / "archive.yml").write_text("archive_id: archive:personal:synthetic-foreign\n", encoding="utf-8")
        with exact.ExactOperationWriterLock(other) as held:
            self.rejected(lambda: self.actor.save(expected_sha256=None, held_lock=held, **self.fields()),
                          "work_session_actor_lock_required")

    def test_pending_original_pair_preserves_old_assertions_without_granting_authority(self):
        original = self.save(pending_manifest_sha256="sha256:" + "a" * 64,
                             pending_context_sha256="sha256:" + "b" * 64)
        self.transition(action="recover", client_app_ref=self.app, work_session_ref=self.session)
        self.assertEqual(self.actor.read()._raw, original._raw)
        # Possessing a valid actor record is not permission to continue the
        # old claim. Real fresh ownership validation independently rejects it.
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(registry.WorkSessionRegistryError):
                self.registry.require_claimed_binding(client_app_ref=self.app,
                    work_session_ref=self.session, claim_ref=self.claim,
                    expected_binding=self.binding, held_lock=held)
        self.assertFalse(original.public_summary()["routing_is_write_authority"])
        self.assertFalse((self.root / "profiles/local/exact-human-approvals").exists())

    def test_no_pending_stale_assertion_fails_and_explicit_cas_can_update_it(self):
        initial = self.save()
        self.transition(action="recover", client_app_ref=self.app, work_session_ref=self.session)
        self.rejected(self.actor.read, "work_session_actor_changed")
        current = self.registry.read()
        updated = self.save(initial.sha256, observed_binding=current.binding(self.session),
                            claim_ref=current._document["sessions"][self.session]["claim_ref"])
        self.assertEqual(self.actor.read()._raw, updated._raw)

    def test_unrelated_generation_does_not_change_this_routing_context(self):
        initial = self.save()
        self.transition(action="register-app", label="Synthetic unrelated app")
        self.assertEqual(self.actor.read()._raw, initial._raw)

    def test_malformed_pending_pair_and_cross_session_assertions_are_rejected(self):
        cases = (
            {"pending_manifest_sha256": "sha256:" + "a" * 64},
            {"pending_context_sha256": "sha256:" + "b" * 64},
            {"pending_manifest_sha256": "private", "pending_context_sha256": "private"},
            {"work_session_ref": None}, {"work_session_ref": "work_session_" + "0" * 32},
            {"claim_ref": "private claim"}, {"observed_binding": self.binding.document()},
        )
        for values in cases:
            with self.subTest(fields=sorted(values)):
                self.rejected(lambda: self.save(**values))
        other_session = self.transition(action="create", client_app_ref=self.other_app,
                                        label="Synthetic other task").result_refs[-1]
        self.rejected(lambda: self.save(work_session_ref=other_session, claim_ref=None,
                                       observed_binding=self.registry.read().binding(other_session)))

    def test_changed_archive_marker_and_store_path_are_rejected(self):
        self.save()
        (self.root / "archive.yml").write_text("archive_id: archive:personal:synthetic-changed\n", encoding="utf-8")
        self.rejected(self.actor.read, "work_session_actor_changed")
        (self.root / "archive.yml").write_text("archive_id: " + ARCHIVE_ID + "\n", encoding="utf-8")
        self.registry.path = self.root / "private-redirect"
        self.rejected(self.actor.read, "work_session_actor_path_unsafe")

    def test_unexpected_names_gaps_and_noncanonical_bytes_are_not_contexts(self):
        saved = self.save()
        first = self.directory / "000000000001.json"
        first.write_bytes(saved._raw + b"\n")
        self.rejected(self.actor.read)
        first.write_bytes(saved._raw)
        first.rename(self.directory / "000000000002.json")
        self.rejected(self.actor.read)
        (self.directory / "000000000002.json").rename(first)
        (self.directory / "unexpected.json").write_text("{}", encoding="utf-8")
        self.rejected(self.actor.read, "work_session_actor_path_unsafe")

    def test_oversize_and_hardlinked_images_fail_closed(self):
        saved = self.save()
        first = self.directory / "000000000001.json"
        first.write_bytes(b"x" * (actor.MAX_ACTOR_BYTES + 1))
        self.rejected(self.actor.read, "work_session_actor_path_unsafe")
        first.write_bytes(saved._raw)
        try:
            os.link(first, self.root / "synthetic-hardlink")
        except OSError:
            self.skipTest("Hardlinks unavailable on this filesystem")
        self.rejected(self.actor.read, "work_session_actor_path_unsafe")

    def test_symlink_parent_is_rejected_without_following_it(self):
        self.save()
        retained = self.directory.with_name("retained-actor")
        self.directory.rename(retained)
        try:
            self.directory.symlink_to(retained, target_is_directory=True)
        except OSError:
            retained.rename(self.directory)
            self.skipTest("Directory symlinks require host capability")
        self.addCleanup(lambda: self.directory.unlink(missing_ok=True))
        self.rejected(self.actor.read, "work_session_actor_path_unsafe")

    def test_cut_before_publish_retains_pending_and_never_selects_it(self):
        initial = self.save()
        with mock.patch.object(actor.durable, "_atomic_move_file_no_replace", side_effect=OSError("private failure")):
            with self.assertRaisesRegex(actor.WorkSessionActorError, "^work_session_actor_durability_unknown$") as caught:
                self.save(initial.sha256, work_session_ref=None, claim_ref=None, observed_binding=None)
        self.assertIsNone(caught.exception.__context__)
        pending = tuple(self.directory.glob(".pending_*"))
        self.assertEqual(len(pending), 1)
        self.assertEqual(self.actor.read()._raw, initial._raw)
        retried = self.save(initial.sha256, work_session_ref=None, claim_ref=None, observed_binding=None)
        self.assertEqual(retried.document()["revision"], 2)
        self.assertTrue(pending[0].exists())

    def test_late_cas_change_is_refused_before_generation_publication(self):
        initial = self.save()
        original_write = actor.registry._write_private_pending

        def change_after_pending(path, raw, *, root):
            original_write(path, raw, root=root)
            document = initial.document()
            document.update(work_session_ref=None, observed_binding=None, claim_ref=None)
            basis = {key: value for key, value in document.items() if key != "actor_sha256"}
            document["actor_sha256"] = actor._sha(registry._canonical(basis))
            (self.directory / "000000000001.json").write_bytes(registry._canonical(document))

        with mock.patch.object(actor.registry, "_write_private_pending", side_effect=change_after_pending):
            with self.assertRaisesRegex(actor.WorkSessionActorError, "^work_session_actor_changed$"):
                self.save(initial.sha256, pending_manifest_sha256="sha256:" + "a" * 64,
                          pending_context_sha256="sha256:" + "b" * 64)
        self.assertFalse((self.directory / "000000000002.json").exists())
        self.assertEqual(len(tuple(self.directory.glob(".pending_*"))), 1)

    def test_rehashed_other_app_context_cannot_replace_explicit_selector(self):
        self.save(work_session_ref=None, claim_ref=None, observed_binding=None)
        path = self.directory / "000000000001.json"
        document = self.actor.read().document()
        document["client_app_ref"] = self.other_app
        basis = {key: value for key, value in document.items() if key != "actor_sha256"}
        document["actor_sha256"] = actor._sha(registry._canonical(basis))
        path.write_bytes(registry._canonical(document))
        self.rejected(self.actor.read, "work_session_actor_changed")

    def test_rehashed_other_task_context_cannot_replace_explicit_route(self):
        saved = self.save()
        document = saved.document()
        document["task_route_ref"] = actor.new_task_route_ref()
        basis = {key: value for key, value in document.items() if key != "actor_sha256"}
        document["actor_sha256"] = actor._sha(registry._canonical(basis))
        (self.directory / "000000000001.json").write_bytes(registry._canonical(document))
        self.rejected(self.actor.read, "work_session_actor_changed")

    def child_read(self, route, expected):
        script = """
import json, sys
from pathlib import Path
from wom_kit import exact_human_approval as a, work_session_registry as r, work_session_actor as actor
root, identity = a._archive_identity(Path(sys.argv[1]))
store = r.WorkSessionRegistryStore(root, a.exact_human_approval_archive_identity_sha256(identity))
try:
    context = actor.WorkSessionActorStore(store, client_app_ref=sys.argv[2],
                                        task_route_ref=sys.argv[3] if len(sys.argv) > 3 else None).read()
except actor.WorkSessionActorError as error:
    print(error.code)
    raise SystemExit(2)
if context is None:
    print('work_session_actor_context_missing')
    raise SystemExit(3)
assert context is not None
# Expected private bytes are a synthetic assertion through stdin, not routing
# or authority supplied to the real store. No session/claim is passed in argv.
assert context._raw == sys.stdin.buffer.read()
value = context.document()
assert value['claim_ref'] == store.read()._document['sessions'][value['work_session_ref']]['claim_ref']
print(json.dumps(context.public_summary(), sort_keys=True))
"""
        argv = [sys.executable, "-B", "-c", script, str(self.root), self.app]
        if route is not None:
            argv.append(route)
        return subprocess.run(argv, input=expected, capture_output=True, timeout=60, check=False)

    def test_real_new_process_uses_explicit_app_and_task_route_and_reads_only(self):
        saved = self.save()
        before = self.files()
        completed = self.child_read(self.route, saved._raw)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), saved.public_summary())
        for value in (self.app, self.route, self.session, self.claim, str(self.root)):
            self.assertNotIn(value.encode(), completed.stdout + completed.stderr)
        self.assertEqual(self.files(), before)

    def test_same_app_two_tasks_interleave_and_resume_only_explicit_route(self):
        second_session = self.transition(action="create", client_app_ref=self.app,
                                          label="Synthetic concurrent task").result_refs[-1]
        self.transition(action="claim", client_app_ref=self.app, work_session_ref=second_session)
        snapshot = self.registry.read()
        second_route = actor.new_task_route_ref()
        self.assertNotEqual(second_route, self.route)
        second_store = actor.WorkSessionActorStore(self.registry, client_app_ref=self.app,
                                                   task_route_ref=second_route)
        first = self.save(pending_manifest_sha256="sha256:" + "a" * 64,
                          pending_context_sha256="sha256:" + "b" * 64)
        with exact.ExactOperationWriterLock(self.root) as held:
            second = second_store.save(expected_sha256=None, held_lock=held,
                work_session_ref=second_session, observed_binding=snapshot.binding(second_session),
                claim_ref=snapshot._document["sessions"][second_session]["claim_ref"],
                pending_manifest_sha256="sha256:" + "c" * 64,
                pending_context_sha256="sha256:" + "d" * 64)
        first_final = self.save(first.sha256)
        self.assertEqual(second_store.read()._raw, second._raw)
        self.assertEqual(self.actor.read()._raw, first_final._raw)
        self.assertEqual(second.document()["revision"], 1)
        self.assertEqual(first_final.document()["revision"], 2)
        # The two genuine claims both pass the independent current guard; that
        # cannot detect a wrong implicit task selection, hence explicit routes.
        with exact.ExactOperationWriterLock(self.root) as held:
            for context in (first_final, second):
                value = context.document()
                self.registry.require_claimed_binding(client_app_ref=self.app,
                    work_session_ref=value["work_session_ref"], claim_ref=value["claim_ref"],
                    held_lock=held)
        before = self.files()
        for route, expected in ((self.route, first_final), (second_route, second)):
            completed = self.child_read(route, expected._raw)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout), expected.public_summary())
        for route, status, message in ((None, 2, b"work_session_actor_invalid"),
                (actor.new_task_route_ref(), 3, b"work_session_actor_context_missing")):
            completed = self.child_read(route, b"")
            self.assertEqual(completed.returncode, status, completed.stderr)
            self.assertEqual(completed.stdout.strip(), message)
            self.assertEqual(completed.stderr, b"")
        self.assertEqual(self.files(), before)


if __name__ == "__main__":
    unittest.main()
