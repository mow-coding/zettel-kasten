"""Private selector publication precedes the original authenticated claim."""

import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_execution as execution
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
import test_v0420_work_session_execution as fixtures


class PendingPublicationTests(unittest.TestCase):
    def setUp(self):
        fixtures.SessionExecutionTests.setUp(self)

    def claims(self):
        return fixtures.SessionExecutionTests.claims(self)

    def execute(self, held, callback):
        return execution._execute_session_decision_held(
            self.root, held=held, action="create", client_app_ref=self.app,
            label="Synthetic pending workstream", reviewer_claim="person:synthetic-pending-reviewer",
            native=self.native, key_provider=self.key, before_claim_publication=callback,
        )

    def assert_publication_failure(self, callback, code):
        with exact.ExactOperationWriterLock(self.root) as held:
            with mock.patch.object(workflow, "_claim_exact_human_approval_core", wraps=workflow._claim_exact_human_approval_core) as claim:
                with mock.patch.object(operation, "apply_session_decision_with_claim", wraps=operation.apply_session_decision_with_claim) as writer:
                    with self.assertRaises(execution.WorkSessionExecutionError) as caught:
                        self.execute(held, lambda prepared, context: callback(prepared, context, held))
                    claim.assert_not_called()
                    writer.assert_not_called()
        self.assertEqual(caught.exception.code, code)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn("Synthetic", str(caught.exception))
        self.assertNotIn(str(self.root), repr(caught.exception))
        self.assertEqual(self.claims(), {})
        self.assertFalse((self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT).exists())
        return caught.exception

    def test_callback_sees_durable_detached_original_before_claim_and_runner_uses_same_operation(self):
        calls, prepared_calls = [], []
        original_prepare = operation.prepare_session_decision

        def prepare(transition):
            result = original_prepare(transition)
            prepared_calls.append(result)
            return result

        with exact.ExactOperationWriterLock(self.root) as held:
            def persist_selection(prepared, context):
                held.verify_held()
                self.assertEqual(self.claims(), {})
                self.assertEqual(self.store.read().revision, 1)
                retained = bundle.load_context_bound_session_decision(
                    self.store, manifest_sha256=prepared.manifest.manifest_sha256,
                )
                self.assertEqual(retained.prepared, prepared)
                self.assertEqual(retained.context, context)
                self.assertEqual(prepared, prepared_calls[0])
                self.assertIsNot(prepared, prepared_calls[0])
                self.assertIsNot(prepared.transition.after._document, prepared_calls[0].transition.after._document)
                calls.append((prepared.manifest.manifest_sha256, approval.exact_human_approval_context_sha256(context)))

            with mock.patch.object(operation, "prepare_session_decision", side_effect=prepare):
                result = self.execute(held, persist_selection)
            self.assertTrue(result["ok"])
            self.assertTrue(result["independent_post_verification"])
            held.verify_held()
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["manifest_sha256"], calls[0][0])
        self.assertEqual(self.native.calls, 1)
        self.assertEqual(len(self.claims()), 1)
        self.assertEqual(self.store.read().revision, 2)

    def test_callback_error_has_no_claim_writer_or_private_exception_chain(self):
        def unavailable(_prepared, _context, _held):
            raise OSError("Synthetic private actor path and claim marker")

        with mock.patch.object(self.key, "use_key", wraps=self.key.use_key) as key:
            self.assert_publication_failure(unavailable, "work_session_execution_pending_selection_failed")
        # Native decision/key and an empty claim directory may already exist;
        # neither is a published authenticated approval or a registry mutation.
        self.assertEqual(self.native.calls, 1)
        key.assert_called_once()
        claim_directory = self.root.joinpath(*Path(approval.CLAIMS_RELATIVE_ROOT).parts)
        self.assertTrue(claim_directory.is_dir())
        self.assertEqual(list(claim_directory.glob("*.json")), [])
        self.assertEqual(self.store.read().revision, 1)
        self.assertEqual(len(list(self.root.joinpath(*bundle.PRIVATE_ROOT).glob("*.json"))), 1)

    def test_callback_return_value_is_not_authority(self):
        self.assert_publication_failure(lambda *_args: {"approved": True},
                                        "work_session_execution_pending_selection_failed")
        self.assertEqual(self.store.read().revision, 1)

    def test_callback_cannot_change_detached_prepared_request(self):
        def mutate(prepared, _context, _held):
            prepared.transition._request["label"] = "Synthetic substituted callback request"

        self.assert_publication_failure(mutate, "work_session_execution_changed")
        self.assertEqual(self.store.read().revision, 1)
        plan = next(self.root.joinpath(*bundle.PRIVATE_ROOT).glob("*.json"))
        retained = bundle.load_context_bound_session_decision(self.store, manifest_sha256="sha256:" + plan.stem)
        self.assertEqual(retained.prepared.transition._request["label"], "Synthetic pending workstream")

    def test_callback_cannot_change_detached_original_context(self):
        def mutate(_prepared, context, _held):
            object.__setattr__(context, "reviewer_claim", "person:synthetic-substituted-reviewer")

        self.assert_publication_failure(mutate, "work_session_execution_changed")
        self.assertEqual(self.store.read().revision, 1)
        plan = next(self.root.joinpath(*bundle.PRIVATE_ROOT).glob("*.json"))
        retained = bundle.load_context_bound_session_decision(self.store, manifest_sha256="sha256:" + plan.stem)
        self.assertEqual(retained.context.reviewer_claim, "person:synthetic-pending-reviewer")

    def test_bundle_revalidation_failure_prevents_callback_itself(self):
        original = bundle.save_context_bound_session_decision
        callback = mock.Mock()

        def corrupt(store, prepared, **kwargs):
            original(store, prepared, **kwargs)
            path = store.root.joinpath(*bundle.PRIVATE_ROOT) / (prepared.manifest.manifest_sha256[7:] + ".json")
            path.write_bytes(path.read_bytes() + b"\n")

        with mock.patch.object(bundle, "save_context_bound_session_decision", side_effect=corrupt):
            self.assert_publication_failure(callback, "work_session_execution_changed")
        callback.assert_not_called()

    def test_callback_bundle_change_is_retained_and_refused_before_claim(self):
        changed = []

        def mutate(prepared, _context, _held):
            path = self.root.joinpath(*bundle.PRIVATE_ROOT) / (prepared.manifest.manifest_sha256[7:] + ".json")
            raw = path.read_bytes() + b"\n"
            path.write_bytes(raw)
            changed.append((path, raw))

        self.assert_publication_failure(mutate, "work_session_execution_changed")
        self.assertEqual(changed[0][0].read_bytes(), changed[0][1])
        self.assertEqual(self.store.read().revision, 1)

    def test_callback_registry_drift_is_not_replanned_or_claimed(self):
        def mutate(_prepared, _context, _held):
            path = self.store.path / "000000000001.json"
            document = json.loads(path.read_bytes())
            document["apps"][self.app]["label"] = "Synthetic registry drift"
            path.write_bytes(registry._canonical(document))

        self.assert_publication_failure(mutate, "work_session_execution_changed")
        self.assertEqual(self.store.read().revision, 1)

    def test_callback_lock_release_cannot_publish_claim(self):
        def release(_prepared, _context, held):
            held.__exit__(None, None, None)

        self.assert_publication_failure(release, "work_session_execution_changed")
        self.assertEqual(self.store.read().revision, 1)

    def test_cancel_and_invalid_callback_do_not_publish_bundle_or_open_callback(self):
        self.native.approve = False
        with exact.ExactOperationWriterLock(self.root) as held:
            with mock.patch.object(self.key, "use_key", side_effect=AssertionError("cancel reached key")):
                with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                    self.execute(held, lambda *_args: self.fail("cancel called callback"))
            self.assertEqual(self.native.calls, 1)
            with self.assertRaises(execution.WorkSessionExecutionError):
                self.execute(held, object())
            self.assertEqual(self.native.calls, 1)
        self.assertFalse(self.root.joinpath(*bundle.PRIVATE_ROOT).exists())
        self.assertEqual(self.claims(), {})
        for function in (execution._execute_session_decision_core, execution._resume_session_decision_core,
                         execution._resume_session_decision_held):
            self.assertNotIn("before_claim_publication", inspect.signature(function).parameters)

    def test_process_exit_in_callback_keeps_original_bundle_but_creates_no_claim(self):
        script = (
            "import os, sys\nfrom pathlib import Path\n"
            "from wom_kit import exact_operation_manifest as e, work_session_execution as x\n"
            "from test_v0420_work_session_operation import _Key\n"
            "from test_v0420_work_session_execution import SessionNative\n"
            "def cut(prepared, context): os._exit(74)\n"
            "with e.ExactOperationWriterLock(Path(sys.argv[1])) as held:\n"
            " x._execute_session_decision_held(Path(sys.argv[1]), held=held, action='create',\n"
            "  client_app_ref=sys.argv[2], label='Synthetic pending workstream',\n"
            "  reviewer_claim='person:synthetic-pending-reviewer', native=SessionNative(), key_provider=_Key(),\n"
            "  before_claim_publication=cut)\n"
        )
        completed = subprocess.run([sys.executable, "-B", "-c", script, str(self.root), self.app],
                                   capture_output=True, text=True, timeout=60,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(completed.returncode, 74, completed.stderr)
        self.assertEqual(completed.stdout, "")
        self.assertEqual(self.claims(), {})
        self.assertEqual(self.store.read().revision, 1)
        plans = list(self.root.joinpath(*bundle.PRIVATE_ROOT).glob("*.json"))
        self.assertEqual(len(plans), 1)
        original = plans[0].read_bytes()
        # The OS released the child lock, but the bundle alone is not approval.
        with exact.ExactOperationWriterLock(self.root) as held:
            with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                execution._resume_session_decision_held(self.root, held=held,
                    manifest_sha256="sha256:" + plans[0].stem, key_provider=self.key)
        self.assertEqual(self.claims(), {})
        self.assertEqual(self.store.read().revision, 1)
        self.assertEqual(plans[0].read_bytes(), original)

    def snapshot_files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def test_completed_only_refuses_real_started_checkpoint_without_mutation(self):
        original_commit = registry.WorkSessionRegistryStore.commit

        def cut_after_commit(store, transition, **kwargs):
            original_commit(store, transition, **kwargs)
            raise OSError("Synthetic process loss after durable registry write")

        with mock.patch.object(registry.WorkSessionRegistryStore, "commit", autospec=True, side_effect=cut_after_commit):
            with exact.ExactOperationWriterLock(self.root) as held:
                with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                    self.execute(held, None)
        manifest = "sha256:" + next(self.root.joinpath(*bundle.PRIVATE_ROOT).glob("*.json")).stem
        self.assertEqual(len(self.claims()), 1)
        checkpoints = self.root / exact.EXACT_OPERATION_LOCAL_ROOT / "checkpoints"
        self.assertTrue(any(checkpoints.rglob("*")))
        before = self.snapshot_files()
        with exact.ExactOperationWriterLock(self.root) as held:
            with mock.patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("completed pointer ran writer")) as writer:
                with self.assertRaises(workflow.ExactHumanApprovalWorkflowError):
                    execution._resume_session_decision_held(self.root, held=held, manifest_sha256=manifest,
                                                            key_provider=self.key, completed_only=True)
                writer.assert_not_called()
        self.assertEqual(self.snapshot_files(), before)
        # The unchanged default still resumes the original authenticated work.
        with exact.ExactOperationWriterLock(self.root) as held:
            resumed = execution._resume_session_decision_held(self.root, held=held, manifest_sha256=manifest,
                                                             key_provider=self.key)
        self.assertTrue(resumed["ok"])
        self.assertEqual(self.native.calls, 1)

    def test_completed_only_checks_real_succeeded_receipt_and_never_calls_writer(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            result = self.execute(held, None)
        before = self.snapshot_files()
        with exact.ExactOperationWriterLock(self.root) as held:
            with mock.patch.object(operation, "apply_session_decision_with_claim", side_effect=AssertionError("completed pointer ran writer")) as writer:
                observed = execution._resume_session_decision_held(self.root, held=held,
                    manifest_sha256=result["manifest_sha256"], key_provider=self.key, completed_only=True)
                writer.assert_not_called()
        self.assertTrue(observed["ok"])
        self.assertTrue(observed["independent_post_verification"])
        self.assertEqual(observed["execution_sha256"], result["execution_sha256"])
        self.assertEqual(observed["receipt_sha256"], result["receipt_sha256"])
        self.assertEqual(self.snapshot_files(), before)
        self.assertEqual(self.native.calls, 1)

    def test_completed_only_is_strict_bool_and_not_an_added_core_argument(self):
        with exact.ExactOperationWriterLock(self.root) as held:
            for invalid in (None, 0, 1, "true", [], {}):
                with self.subTest(kind=type(invalid).__name__):
                    with self.assertRaises(execution.WorkSessionExecutionError):
                        execution._resume_session_decision_held(self.root, held=held, manifest_sha256="sha256:" + "f" * 64,
                                                                key_provider=self.key, completed_only=invalid)
        self.assertEqual(self.claims(), {})
        self.assertFalse(self.root.joinpath(*bundle.PRIVATE_ROOT).exists())
        self.assertNotIn("completed_only", inspect.signature(execution._resume_session_decision_core).parameters)


if __name__ == "__main__":
    unittest.main()
