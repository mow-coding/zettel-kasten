"""Actual public session/intake journey; only native input and key are synthetic.

The injected failure happens after a real receipt publication and before its
common checkpoint. It models an interruption, not a native power-loss claim.
"""

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import io
import json
import unittest
from unittest import mock

import test_v0410_source_intake_batch_exact as intake_fixture
from test_v0420_work_session_execution import SessionNative
from wom_kit import archive_cli as cli
from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import exact_operation_manifest as exact
from wom_kit import source_intake_batch_exact as intake
from wom_kit import work_session_actor as actor
from wom_kit import work_session_registration as registration
from wom_kit import work_session_source_intake_bundle as bundle


class _SyntheticKey(intake_fixture._KeyProvider):
    def __init__(self):
        super().__init__()
        self.active = False

    def use_key(self, root, consumer, *, create_if_missing=False):
        if self.active:
            raise AssertionError("nested synthetic key consumer")
        self.active = True
        try:
            return super().use_key(root, consumer, create_if_missing=create_if_missing)
        finally:
            self.active = False


class PublicSessionSourceIntakeJourneyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = intake_fixture.SourceIntakeBatchExactTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = self.fixture.root
        self.sources = self.fixture._write_request(2)
        self.request = self.fixture.request_path
        self.source_bytes = {path: path.read_bytes() for path in self.sources}
        self.original_request_bytes = self.request.read_bytes()
        self.outputs = []
        self.key, self.native = _SyntheticKey(), SessionNative()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        self.stack.enter_context(mock.patch.object(broker, "_production_key_provider", return_value=self.key))

        # No internal registry seed or actor.save: every establishment mutation
        # below enters the real public CLI, runtime guard and held facade.
        preview = self.session_command("--action", "register-app", "--dry-run", "--request-stdin",
            request={"label": "SYNTHETIC_PRIVATE_INTAKE_APP"})
        self.session_command("--action", "register-app", "--apply", "--request-stdin",
            request={"selection": preview, "label": "SYNTHETIC_PRIVATE_INTAKE_APP"})
        self.app = preview["client_app_ref"]
        route = self.session_command("--action", "request-init", "--client-app-ref", self.app)
        self.route = route["task_route_ref"]
        self.refs = ("--client-app-ref", self.app, "--task-route-ref", self.route)
        created = self.session_command("--action", "create", "--approve", "--request-stdin", *self.refs,
            request={"label": "SYNTHETIC_PRIVATE_INTAKE_SESSION", "reviewer_claim": "person:synthetic-session-reviewer"})
        self.session = created["work_session_binding"]["work_session_ref"]
        claimed = self.session_command("--action", "claim", "--apply", *self.refs,
            "--work-session-ref", self.session)
        self.assertTrue(claimed["current_claim_ownership_verified"])
        self.assertEqual(self.native.calls, 1)
        # These are independent, read-only assertion handles, never fixture
        # authority injected into the command under test.
        self.store = registration._store(self.root)
        self.routing = actor.WorkSessionActorStore(self.store,
            client_app_ref=self.app, task_route_ref=self.route)

    def call(self, command, *flags, request=None, ok=True):
        output, errors = io.StringIO(), io.StringIO()
        input_stream = io.StringIO("" if request is None else json.dumps(request))
        with mock.patch.object(cli.sys, "stdin", input_stream), redirect_stdout(output), redirect_stderr(errors):
            code = cli.main([command, str(self.root), "--format", "json", "--no-progress", *flags])
        result = json.loads(output.getvalue())
        self.assertEqual(code == 0, ok, result)
        self.assertEqual(result["ok"], ok, result)
        self.assertEqual(errors.getvalue(), "")
        self.outputs.append(result)
        return result

    def session_command(self, *flags, request=None):
        return self.call("work-session", *flags, request=request)["result"]

    def register_unrelated_app(self):
        """Real public registration after A's cut, without changing A's claim."""
        before, selected = self.store.read(), self.routing._read(current=False)
        claims, native_calls = self.claims(), self.native.calls
        label = "SYNTHETIC_PRIVATE_CONCURRENT_APP_B"
        preview = self.session_command("--action", "register-app", "--dry-run", "--request-stdin",
            request={"label": label})
        self.session_command("--action", "register-app", "--apply", "--request-stdin",
            request={"selection": preview, "label": label})
        after = self.store.read()
        self.assertNotEqual(preview["client_app_ref"], self.app)
        self.assertNotEqual(after.sha256, before.sha256)
        self.assertEqual(after.binding(self.session), before.binding(self.session))
        self.assertEqual(self.routing._read(current=False)._raw, selected._raw)
        self.assertEqual(self.claims(), claims)
        self.assertEqual(self.native.calls, native_calls)
        return after.sha256

    def claims(self):
        return {path.name: path.read_bytes()
                for path in self.root.joinpath(approval.CLAIMS_RELATIVE_ROOT).glob("*.json")}

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file() and path.name != ".writer.lock"}

    def retained(self, pointer):
        with exact.ExactOperationWriterLock(self.root) as held:
            return bundle._load_original_source_intake_context_held(self.root,
                manifest_sha256=pointer["manifest_sha256"], held=held)

    def test_public_interrupted_intake_resumes_original_then_replays_without_inputs(self):
        original_claims = self.claims()
        original_files = self.files()
        registry_before = self.store.read().sha256
        archive_before = (self.root / "archive.yml").read_bytes()
        first_effect = []
        write_field = intake._Writer.write_field

        def effect_then_cut(writer, **kwargs):
            result = write_field(writer, **kwargs)
            if kwargs["target_kind"] == intake.TARGET_KIND and not first_effect:
                path = self.root / kwargs["target_ref"]
                self.assertTrue(path.is_file())
                first_effect.append((kwargs["target_ref"], path.read_bytes()))
                raise OSError("SYNTHETIC_PRIVATE_INTAKE_EFFECT_CUT")
            return result

        with mock.patch.object(intake._Writer, "write_field", new=effect_then_cut):
            interrupted = self.call("source-intake-batch", *self.refs,
                "--work-session-ref", self.session, "--manifest", str(self.request),
                "--approve", "--reviewed-by", "person:synthetic-intake-reviewer", ok=False)
        self.assertEqual(interrupted["reason_code"], "exact_human_approval_state_unknown")
        self.assertFalse(interrupted["original_completion_verified"])
        self.assertEqual(len(first_effect), 1)
        self.assertEqual(self.native.calls, 2)
        selected = self.routing._read(current=False)
        pointer = selected.pending_operation().document()
        self.assertEqual(pointer["kind"], "source_intake_batch")
        bound = self.retained(pointer)
        plan, context = bound.prepared.plan, bound.context
        self.assertEqual(len(plan.items), 2)
        self.assertEqual(plan.manifest.work_session_binding, self.store.read().binding(self.session))
        self.assertEqual(sum((self.root / item.receipt_relative_path).is_file() for item in plan.items), 1)
        self.assertFalse((self.root / plan.prepared_capture_request.relative_path).exists())
        claims_after_cut = self.claims()
        created_claims = set(claims_after_cut) - set(original_claims)
        self.assertEqual(len(created_claims), 1)
        claim_name = next(iter(created_claims))
        started = json.loads(claims_after_cut[claim_name])
        self.assertEqual(started["status"], "started")
        self.assertEqual(started["context_sha256"], pointer["context_sha256"])
        self.assertEqual(started["context"]["plan_sha256"], plan.manifest.manifest_sha256)
        checkpoints_before = {path: raw for path, raw in self.files().items()
                              if path not in original_files and path.endswith(".jsonl")
                              and "/exact-operations/checkpoints/" in path}
        self.assertEqual(len(checkpoints_before), 1)
        for raw in checkpoints_before.values():
            rows = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual([row["stage"] for row in rows], ["started"])
        self.assertEqual(self.store.read().sha256, registry_before)
        self.assertEqual(self.request.read_bytes(), self.original_request_bytes)
        for path, raw in self.source_bytes.items():
            self.assertEqual(path.read_bytes(), raw)

        # Delete precisely the synthetic caller JSON, not the retained request
        # or either source. Public continuation supplies no approval IDs/digests.
        self.request.unlink()
        self.assertFalse(self.request.exists())
        resumed_writes = []

        def observed_write(writer, **kwargs):
            resumed_writes.append(kwargs["target_ref"])
            return write_field(writer, **kwargs)

        with ExitStack() as stack:
            for owner, name in ((intake, "plan_source_intake_batch"), (intake, "_request_items"),
                                (bundle, "_save_original_source_intake_context_held"),
                                (approval, "_claim_exact_human_approval_core"),
                                (windows, "_CtypesTaskDialogNative")):
                stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("original resume rebuilt inputs")))
            stack.enter_context(mock.patch.object(intake._Writer, "write_field", new=observed_write))
            completed = self.call("source-intake-batch", *self.refs, "--resume")
        self.assertTrue(completed["original_completion_verified"])
        self.assertTrue(completed["completion_authentication_verified"])
        self.assertTrue(completed["independent_verification"])
        self.assertTrue(completed["actor_completion_published"])
        self.assertFalse(completed["original_operation_already_completed"])
        self.assertFalse(completed["artifact_capture_performed"])
        self.assertTrue(completed["requires_new_capture_approval"])
        self.assertEqual(completed["completed_item_count"], 2)
        self.assertNotIn(first_effect[0][0], resumed_writes)
        self.assertEqual(set(resumed_writes), {item.receipt_relative_path for item in plan.items
            if item.receipt_relative_path != first_effect[0][0]} | {plan.prepared_capture_request.relative_path})
        self.assertEqual(self.retained(pointer)._raw, bound._raw)
        self.assertEqual(self.retained(pointer).context, context)
        self.assertEqual(completed["context_sha256"], pointer["context_sha256"])
        self.assertEqual(set(self.claims()), set(claims_after_cut))
        succeeded = json.loads(self.claims()[claim_name])
        self.assertEqual(succeeded["status"], "succeeded")
        for field in ("approval_id", "context", "context_sha256", "approval_authority_sha256",
                      "reviewer_claim_sha256", "approved_at", "started_at"):
            self.assertEqual(succeeded[field], started[field])
        for name, raw in original_claims.items():
            self.assertEqual(self.claims()[name], raw)
        for path, raw in checkpoints_before.items():
            self.assertTrue(self.files()[path].startswith(raw))
            self.assertTrue(path.endswith(completed["execution_sha256"].removeprefix("sha256:") + ".jsonl"))
        self.assertIsNone(self.routing._read(current=False).pending_operation())
        self.assertEqual(self.routing._read(current=False).document()["last_completed_operation"], pointer)
        self.assertEqual(self.store.read().sha256, registry_before)

        # Fresh whole-output observation plus original common terminal MAC and
        # checkpoint-chain verification, independently of the public response.
        final = exact.load_exact_operation_final_receipt_read_only(self.root, completed["execution_sha256"])
        self.assertEqual(final["receipt_sha256"], completed["common_final_receipt_sha256"])
        self.assertEqual(final["result"]["completion_authentication"]["approval_reference"]["approval_id"], started["approval_id"])
        verified = intake.reconcile_source_intake_batch(plan,
            execution_sha256=completed["execution_sha256"], key_provider=self.key)
        self.assertTrue(verified["ok"] and verified["completion_authentication_verified"] and verified["independent_verification"])
        for item, source in zip(plan.items, self.sources):
            self.assertEqual((self.root / item.receipt_relative_path).read_bytes(), item.receipt_bytes)
            self.assertEqual(item.capture_staged_path, source.relative_to(self.root).as_posix())
            self.assertEqual(item.source_bytes_sha256, "sha256:" + hashlib.sha256(self.source_bytes[source]).hexdigest())
        capture = plan.prepared_capture_request
        self.assertEqual((self.root / capture.relative_path).read_bytes(), capture.request_bytes)
        self.assertEqual((self.root / first_effect[0][0]).read_bytes(), first_effect[0][1])

        for source in self.sources:
            source.unlink()
        self.assertFalse(self.request.exists())
        before_replay = self.files()
        with ExitStack() as stack:
            for owner, name in ((intake, "plan_source_intake_batch"), (intake, "_request_items"),
                                (intake, "_revalidate_item"), (intake, "_run_session_source_intake_batch_exact_operation"),
                                (intake._Writer, "write_field"), (bundle, "_save_original_source_intake_context_held"),
                                (actor.WorkSessionActorStore, "save"), (approval, "_claim_exact_human_approval_core"),
                                (approval._ClaimedExactHumanApproval, "exact_terminal_record_mac"),
                                (windows, "_CtypesTaskDialogNative")):
                stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError("completed replay mutated or reread inputs")))
            replay = self.call("source-intake-batch", *self.refs, "--resume")
        self.assertTrue(replay["original_operation_already_completed"] and replay["original_completion_verified"])
        self.assertFalse(replay["writes_performed"] or replay["actor_completion_published"])
        self.assertFalse(replay["source_bytes_reverified"])
        self.assertFalse(replay["artifact_capture_performed"])
        self.assertEqual(replay["execution_sha256"], completed["execution_sha256"])
        self.assertEqual(replay["common_final_receipt_sha256"], completed["common_final_receipt_sha256"])
        self.assertEqual(self.files(), before_replay)
        self.assertEqual(self.native.calls, 2)
        self.assertEqual((self.root / "archive.yml").read_bytes(), archive_before)
        self.assertFalse(self.key.active)
        for marker in ("SYNTHETIC_PRIVATE", str(self.root), str(self.request), started["approval_id"],
                       self.routing._read(current=False).document()["claim_ref"]):
            self.assertNotIn(marker, json.dumps(self.outputs))


if __name__ == "__main__":
    unittest.main()
