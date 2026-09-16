"""Real private single-record workflow; synthetic native/key, not CLI acceptance.

The source is only a fixture for the reviewed redacted JSON. This workflow
records that JSON; it does not retain source bytes or prepare a capture request.
"""

from contextlib import ExitStack
import inspect
import json
import unittest
from unittest.mock import patch

import test_v049_source_intake_record_exact as record_fixture
import test_v0410_source_intake_batch_exact as batch_fixture
from test_v0420_work_session_execution import SessionNative
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_record_exact as record
from wom_kit import work_session_actor as actor
from wom_kit import work_session_establishment as establishment
from wom_kit import work_session_execution as execution
from wom_kit import work_session_registry as registry
from wom_kit import work_session_source_intake_record_bundle as bundle
from wom_kit import work_session_source_intake_record_execution as domain
from wom_kit import work_session_source_intake_record_workflow as subject


class _ActiveKey(batch_fixture._KeyProvider):
    def __init__(self):
        super().__init__()
        self.active = False
        self.before_consumer = None

    def use_key(self, root, consumer, *, create_if_missing=False):
        if self.active:
            raise AssertionError("nested synthetic key provider")
        self.active = True
        try:
            if self.before_consumer is not None:
                self.before_consumer(create_if_missing)
            return super().use_key(root, consumer, create_if_missing=create_if_missing)
        finally:
            self.active = False


class SessionSourceIntakeRecordWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = record_fixture.SourceIntakeRecordExactTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root, self.plan_path = self.fixture.root, self.fixture.plan_path
        self.key, self.native = _ActiveKey(), record_fixture._Native(approved=True)
        self.store, _archive = execution._store(self.root)
        self.route = actor.new_task_route_ref()
        # The same actual lifecycle/broker fixture as the batch workflow. No
        # claimed-actor/receipt JSON is pre-seeded and no approval is bypassed.
        with exact.ExactOperationWriterLock(self.root) as held:
            registered = registry.plan_transition(self.store.read(), action="register-app", label="Synthetic record app")
            self.store.commit(registered, held_lock=held)
            self.app = registered.result_refs[0]
            original = execution._execute_session_decision_held(self.root, held=held, action="create",
                client_app_ref=self.app, task_route_ref=self.route, label="Synthetic record task",
                reviewer_claim="person:record-fixture", native=SessionNative(), key_provider=self.key)
            self.session = original["work_session_binding"]["work_session_ref"]
            claimed = registry.plan_transition(self.store.read(), action="claim", client_app_ref=self.app,
                work_session_ref=self.session)
            self.store.commit(claimed, held_lock=held)
            self.binding = self.store.read().binding(self.session)
            self.claim_ref = self.store.read()._document["sessions"][self.session]["claim_ref"]
            self.routing = actor.WorkSessionActorStore(self.store, client_app_ref=self.app, task_route_ref=self.route)
            origin = establishment.EstablishmentSelector.from_document({"action": "create",
                "manifest_sha256": original["manifest_sha256"],
                "context_sha256": original["exact_human_approval_reference"]["context_sha256"]})
            self.selected = self.routing.save(expected_sha256=None, held_lock=held,
                work_session_ref=self.session, claim_ref=self.claim_ref, observed_binding=self.binding,
                established_origin=origin)

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def claims(self):
        return {path.name: path.read_bytes()
                for path in self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json")}

    def execute(self, held, **changes):
        values = dict(held=held, client_app_ref=self.app, task_route_ref=self.route,
            work_session_ref=self.session, reviewer_claim="person:record-reviewer",
            native=self.native, key_provider=self.key)
        values.update(changes)
        return subject._execute_session_source_intake_record_held(self.root, self.plan_path, **values)

    def resume(self, held, **changes):
        values = dict(held=held, client_app_ref=self.app, task_route_ref=self.route, key_provider=self.key)
        values.update(changes)
        return subject._resume_session_source_intake_record_held(self.root, **values)

    def refuse(self, call, code=None, *, completed=False):
        with self.assertRaises(subject.WorkSessionIntakeWorkflowError) as caught:
            call()
        error = caught.exception
        if code is not None:
            self.assertEqual(error.code, code)
        self.assertEqual(error.original_completion_verified, completed)
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        self.assert_private_safe(str(error) + repr(error))
        return error

    def assert_private_safe(self, value):
        rendered = value if type(value) is str else json.dumps(value)
        for marker in (str(self.root), str(self.plan_path), record_fixture.PRIVATE_NAME,
                       record_fixture.PRIVATE_BODY, self.app, self.route, self.session, self.claim_ref):
            for variant in (marker, marker.replace("\\", "/"), marker.replace("\\", "\\\\")):
                self.assertNotIn(variant, rendered)

    def retained(self, held):
        selected = self.routing._read(current=False)
        pointer = (selected.pending_operation().document() if selected.pending_operation() is not None
                   else selected.document()["last_completed_operation"])
        self.assertEqual(pointer["kind"], "source_intake_record")
        return bundle._load_original_source_intake_record_context_held(self.root,
            manifest_sha256=pointer["manifest_sha256"], held=held)

    def forbid_original_reconstruction(self, stack, *, completed=False):
        for owner, name in ((record, "plan_source_intake_record"),
                            (bundle, "_save_original_source_intake_record_context_held"),
                            (broker, "_claim_exact_human_approval_core"),
                            (windows, "_CtypesTaskDialogNative")):
            stack.enter_context(patch.object(owner, name, side_effect=AssertionError("original reconstruction forbidden")))
        stack.enter_context(patch.object(self.native, "show", side_effect=AssertionError("native redisplay")))
        if completed:
            stack.enter_context(patch.object(approval._ClaimedExactHumanApproval, "exact_terminal_record_mac",
                                            side_effect=AssertionError("completed re-sign")))
            stack.enter_context(patch.object(actor.WorkSessionActorStore, "save",
                                            side_effect=AssertionError("completed actor rewrite")))

    def test_actual_publish_cut_then_json_deleted_resume_and_source_gone_completed_replay(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.files()
            preview = subject._preview_session_source_intake_record_held(self.root, self.plan_path,
                held=held, client_app_ref=self.app, task_route_ref=self.route,
                work_session_ref=self.session, key_provider=self.key)
            self.assertTrue(preview["ready_for_write"])
            self.assertFalse(preview["original_completion_verified"] or preview["writes_performed"])
            self.assertFalse(preview["prepared_capture_request_created"] or preview["source_bytes_retained"])
            self.assertEqual(self.files(), before)
            self.assertEqual(self.native.calls, 0)
            old_claims, registry_before = self.claims(), self.store.read().sha256
            original_move = domain.durable._atomic_move_file_no_replace
            published = []

            def cut(source, target, **kwargs):
                result = original_move(source, target, **kwargs)
                if target.name.endswith(".source-intake-plan.json"):
                    self.assertTrue(target.parent.samefile(self.root / "receipts" / "sources"))
                    self.assertEqual(json.loads(target.read_bytes()), self.fixture.source_document)
                    published.append((target, target.read_bytes(), target.stat().st_ino, target.stat().st_mtime_ns))
                    raise OSError("synthetic after actual record publication before checkpoint")
                return result

            with patch.object(domain.durable, "_atomic_move_file_no_replace", side_effect=cut):
                self.refuse(lambda: self.execute(held), "exact_human_approval_state_unknown")
            held.verify_held()
            self.assertEqual(len(published), 1, "must reach the actual receipt publication cut")
            bound = self.retained(held)
            plan, context = bound.prepared.plan, bound.context
            self.assertEqual(len(plan.manifest.items), 1)
            self.assertEqual(plan.manifest.work_session_binding, self.binding)
            self.assertEqual(plan.receipt_bytes, published[0][1])
            self.assertEqual(self.native.calls, 1)
            new_claims = set(self.claims()) - set(old_claims)
            self.assertEqual(len(new_claims), 1)
            claim_name = next(iter(new_claims))
            started = json.loads(self.claims()[claim_name])
            self.assertEqual(started["status"], "started")
            self.assertEqual(started["context_sha256"], approval.exact_human_approval_context_sha256(context))
            checkpoints = {name: raw for name, raw in self.files().items()
                           if name not in before and "/exact-operations/checkpoints/" in name and name.endswith(".jsonl")}
            self.assertEqual(len(checkpoints), 1)
            self.assertEqual([json.loads(line)["stage"] for raw in checkpoints.values()
                              for line in raw.splitlines()], ["started"])
            self.assertEqual(self.store.read().sha256, registry_before)
            self.plan_path.unlink()
            key_offset = len(self.key.create_if_missing_calls)
            def no_receipt_republication(source, target, **kwargs):
                if target.name.endswith(".source-intake-plan.json"):
                    raise AssertionError("original receipt must not be republished")
                return original_move(source, target, **kwargs)
            with ExitStack() as stack:
                self.forbid_original_reconstruction(stack)
                stack.enter_context(patch.object(domain.durable, "_atomic_move_file_no_replace",
                                                 side_effect=no_receipt_republication))
                completed = self.resume(held)
            self.assertTrue(completed["ok"] and completed["original_completion_verified"])
            self.assertEqual(completed["started_resume_state"], "checkpoint_present")
            self.assertTrue(completed["completion_authentication_verified"] and completed["actor_completion_published"])
            self.assertFalse(completed["writes_performed"])
            self.assertFalse(completed["artifact_capture_performed"] or completed["prepared_capture_request_created"])
            self.assertFalse(completed["source_bytes_retained"])
            self.assertEqual(completed["receipt_create_count"], 1)
            self.assertNotIn(True, self.key.create_if_missing_calls[key_offset:])
            self.assertEqual(self.retained(held)._raw, bound._raw)
            self.assertEqual(set(self.claims()), set(old_claims) | new_claims)
            succeeded = json.loads(self.claims()[claim_name])
            self.assertEqual(succeeded["status"], "succeeded")
            for field in ("approval_id", "context", "context_sha256", "approval_authority_sha256",
                          "reviewer_claim_sha256", "approved_at", "started_at"):
                self.assertEqual(succeeded[field], started[field])
            target, raw, inode, mtime = published[0]
            self.assertEqual((target.read_bytes(), target.stat().st_ino, target.stat().st_mtime_ns), (raw, inode, mtime))
            for name, raw in old_claims.items():
                self.assertEqual(self.claims()[name], raw)
            for name, raw in checkpoints.items():
                self.assertTrue(self.files()[name].startswith(raw))
            final = exact.load_exact_operation_final_receipt_read_only(self.root, completed["execution_sha256"])
            self.assertEqual(final["receipt_sha256"], completed["common_final_receipt_sha256"])
            self.assertEqual(final["result"]["item_count"], 1)
            self.assertEqual(final["result"]["completion_authentication"]["approval_reference"]["approval_id"], started["approval_id"])
            self.assertIsNone(self.routing._read(current=False).pending_operation())
            self.assertEqual(self.store.read().sha256, registry_before)
            added = set(self.files()) - set(before)
            self.assertEqual({name for name in added if name.startswith("receipts/sources/")}, {plan.receipt_relative_path})
            self.assertFalse(any("capture" in name for name in added), "single-record must not prepare a capture request")
            self.fixture.selected.unlink()
            replay_before = self.files()
            with ExitStack() as stack:
                self.forbid_original_reconstruction(stack, completed=True)
                stack.enter_context(patch.object(domain.durable, "_atomic_move_file_no_replace",
                                                 side_effect=AssertionError("completed domain publication")))
                replay = self.resume(held)
            self.assertTrue(replay["original_completion_verified"] and replay["original_operation_already_completed"])
            self.assertFalse(replay["writes_performed"] or replay["actor_completion_published"])
            self.assertEqual(self.files(), replay_before)
            self.assertEqual(self.native.calls, 1)
            self.assert_private_safe([preview, completed, replay])

    def test_current_registry_owner_loss_refuses_before_native_or_context(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            paused = registry.plan_transition(self.store.read(), action="pause", client_app_ref=self.app,
                work_session_ref=self.session, claim_ref=self.claim_ref)
            self.store.commit(paused, held_lock=held)
            before = self.files()
            with patch.object(bundle, "_save_original_source_intake_record_context_held",
                              side_effect=AssertionError("context before current ownership")):
                self.refuse(lambda: self.execute(held))
            self.assertEqual(self.native.calls, 0)
            self.assertEqual(self.files(), before)

    def test_failed_no_replace_publication_preserves_private_stage_and_original_resume(self):
        original_move = domain.durable._atomic_move_file_no_replace
        stages = []
        def fail_before_move(source, target, **kwargs):
            if target.name.endswith(".source-intake-plan.json"):
                self.assertTrue(source.parent.samefile(self.root / "receipts" / "sources"))
                self.assertTrue(source.name.startswith(".pending_"))
                self.assertFalse(target.exists())
                stages.append((source, source.read_bytes(), target))
                raise OSError("synthetic no-replace publication failure")
            return original_move(source, target, **kwargs)
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(domain.durable, "_atomic_move_file_no_replace", side_effect=fail_before_move):
                self.refuse(lambda: self.execute(held), "exact_human_approval_state_unknown")
            self.assertEqual(len(stages), 1, "must reach actual durable stage before the no-replace move")
            pending, raw, target = stages[0]
            self.assertTrue(pending.exists())
            self.assertFalse(target.exists())
            bound = self.retained(held)
            self.assertEqual(raw, bound.prepared.plan.receipt_bytes)
            self.plan_path.unlink()
            with ExitStack() as stack:
                self.forbid_original_reconstruction(stack)
                completed = self.resume(held)
            self.assertTrue(completed["original_completion_verified"])
            self.assertEqual(target.read_bytes(), raw)
            self.assertEqual(pending.read_bytes(), raw, "untrusted old private stage is not adopted or removed")
            self.assertEqual(self.retained(held)._raw, bound._raw)
            self.assertEqual(self.native.calls, 1)

    def test_native_return_actor_cas_drift_refuses_without_pending_or_receipt(self):
        show = self.native.show
        mutations = []
        with exact.ExactOperationWriterLock(self.root) as held:
            claims = self.claims()
            def change(**kwargs):
                result = show(**kwargs)
                current = self.routing._read(current=False)
                changed = self.routing.save(expected_sha256=current.sha256, held_lock=held,
                    work_session_ref=self.session, claim_ref=None, observed_binding=self.binding)
                self.assertNotEqual(changed._raw, current._raw, "the callback must actually change the actor")
                mutations.append(changed._raw)
                return result
            with patch.object(self.native, "show", side_effect=change), \
                 patch.object(bundle, "_save_original_source_intake_record_context_held",
                              side_effect=AssertionError("drifted context publication")):
                self.refuse(lambda: self.execute(held), "work_session_intake_changed")
            self.assertEqual(len(mutations), 1)
            self.assertEqual(self.routing._read(current=False)._raw, mutations[0])
            self.assertIsNone(self.routing._read(current=False).pending_operation())
            self.assertEqual(self.claims(), claims)
            self.assertEqual(self.native.calls, 1)

    def test_native_return_exact_input_byte_drift_refuses_before_context_or_claim(self):
        show, raw = self.native.show, self.plan_path.read_bytes()
        mutations = []
        def change(**kwargs):
            result = show(**kwargs)
            self.plan_path.write_bytes(raw + b"\n")
            mutations.append(True)
            return result
        with exact.ExactOperationWriterLock(self.root) as held:
            before = self.files()
            with patch.object(self.native, "show", side_effect=change), \
                 patch.object(bundle, "_save_original_source_intake_record_context_held",
                              side_effect=AssertionError("input drift context publication")):
                self.refuse(lambda: self.execute(held), "work_session_intake_changed")
            self.assertEqual(mutations, [True])
            self.assertEqual(json.loads(self.plan_path.read_bytes()), json.loads(raw))
            self.assertNotEqual(self.plan_path.read_bytes(), raw)
            self.assertEqual(self.files(), before)

    def test_copied_exact_receipt_without_original_claim_never_authorizes_resume(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            with patch.object(broker, "_claim_exact_human_approval_core",
                              side_effect=OSError("synthetic before original approval claim")) as cut:
                self.refuse(lambda: self.execute(held))
            cut.assert_called_once()
            bound = self.retained(held)
            target = self.root / bound.prepared.plan.receipt_relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bound.prepared.plan.receipt_bytes)
            self.plan_path.unlink()
            before, actor_raw = self.files(), self.routing._read(current=False)._raw
            key_offset = len(self.key.create_if_missing_calls)
            with ExitStack() as stack:
                self.forbid_original_reconstruction(stack)
                self.refuse(lambda: self.resume(held), "work_session_intake_original_approval_missing")
            self.assertEqual(self.files(), before)
            self.assertEqual(self.routing._read(current=False)._raw, actor_raw)
            self.assertNotIn(True, self.key.create_if_missing_calls[key_offset:])
            self.assertEqual(self.native.calls, 1)

    def test_rehashed_tampered_terminal_mac_refuses_completed_replay_read_only(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            completed = self.execute(held)
            self.assertTrue(completed["original_completion_verified"])
            path = self.root / "receipts" / "ops" / "exact-operations" / (completed["execution_sha256"].removeprefix("sha256:") + ".json")
            final = json.loads(path.read_bytes())
            final["result"]["completion_authentication"]["terminal_mac"] = "hmac-sha256:" + "0" * 64
            oracle = batch_fixture.SourceIntakeBatchExactTests
            result_basis = dict(final["result"])
            result_basis.pop("result_sha256")
            final["result"]["result_sha256"] = oracle._exact_document_sha256(result_basis)
            receipt_basis = dict(final)
            receipt_basis.pop("receipt_sha256")
            final["receipt_sha256"] = oracle._exact_document_sha256(receipt_basis)
            path.write_bytes(oracle._canonical_exact_bytes(final) + b"\n")
            self.assertIsNotNone(exact.load_exact_operation_final_receipt_read_only(self.root, completed["execution_sha256"]),
                                 "tamper must remain a structurally valid rehashed receipt")
            self.plan_path.unlink()
            before = self.files()
            with ExitStack() as stack:
                self.forbid_original_reconstruction(stack, completed=True)
                self.refuse(lambda: self.resume(held))
            self.assertEqual(self.files(), before)
            self.assertEqual(self.native.calls, 1)


class SessionSourceIntakeRecordInterfaceTests(unittest.TestCase):
    def test_resume_interface_contains_no_fresh_plan_reviewer_or_approval_selector(self):
        self.assertEqual(set(inspect.signature(subject._resume_session_source_intake_record_held).parameters),
            {"root", "held", "client_app_ref", "task_route_ref", "work_session_ref", "key_provider", "progress_hook"})


if __name__ == "__main__":
    unittest.main()
