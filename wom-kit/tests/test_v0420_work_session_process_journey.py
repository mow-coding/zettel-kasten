"""Real process-loss/restart journeys through the internal session executor.

Only native human input and the archive authentication key are synthetic.
The three crash hooks call the real durable operation and then os._exit,
without Python exception handling or finally cleanup. This is source-checkout
integration evidence, not public CLI discovery or installed-wheel evidence.
"""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import exact_human_approval as approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit import exact_operation_manifest as exact
from wom_kit import work_session_bundle as bundle
from wom_kit import work_session_execution as execution
from wom_kit import work_session_operation as operation
from wom_kit import work_session_registry as registry
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID


ARCHIVE_ID = "archive:personal:synthetic-process-journey"
REVIEWER = "person:synthetic-original-reviewer"
CUT_EXIT_CODE = 73
CUTS = ("started_before_checkpoint", "registry_published", "succeeded_before_output")
REPOSITORY = Path(__file__).resolve().parents[2]


class _SyntheticNative:
    def show(self, **_kwargs):
        raise AssertionError("synthetic_collection_preview_was_bypassed")

    def show_collection(self, *, session, **_kwargs):
        if session.button_clicked(APPROVE_BUTTON_ID) != "close":
            raise AssertionError("synthetic_collection_approval_did_not_close")
        print("synthetic_native_called", flush=True)
        return APPROVE_BUTTON_ID, True


class _SyntheticKey:
    def __init__(self, *, resuming=False):
        self.resuming = resuming

    def use_key(self, _root, consumer, *, create_if_missing=False):
        if self.resuming and create_if_missing:
            raise AssertionError("synthetic_resume_attempted_key_creation")
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


def _new_store(root):
    resolved, archive_id = approval._archive_identity(root)
    return registry.WorkSessionRegistryStore(
        resolved, approval.exact_human_approval_archive_identity_sha256(archive_id),
    )


def _one_payload(store):
    # This fixture deliberately has one pending payload. Filename selection
    # grants no authority: strict bundle loading and the broker authenticate
    # it afterwards. Public app/workstream-scoped discovery is a separate gate.
    candidates = tuple(store.root.joinpath(*bundle.PRIVATE_ROOT).glob("*.json"))
    if len(candidates) != 1:
        raise AssertionError("synthetic_payload_selection_not_unique")
    digest = "sha256:" + candidates[0].stem
    return digest, bundle.load_context_bound_session_decision(store, manifest_sha256=digest)


def _process_worker(root, mode, cut):
    if mode not in {"cut", "resume"} or cut not in CUTS:
        raise AssertionError("synthetic_worker_arguments_invalid")
    print("synthetic_worker_ready", flush=True)

    def stop():
        print("synthetic_cut:" + cut, flush=True)
        os._exit(CUT_EXIT_CODE)

    with ExitStack() as seams:
        # Accidentally falling through to real credential/native providers is
        # always an error, never permission to display UI in the test host.
        seams.enter_context(patch.object(workflow, "_production_key_provider",
                                         side_effect=AssertionError("synthetic_production_key_forbidden")))
        if mode == "cut":
            store = _new_store(root)
            apps = tuple(store.read()._document["apps"])
            if len(apps) != 1:
                raise AssertionError("synthetic_app_selection_not_unique")
            if cut == "started_before_checkpoint":
                original = workflow._claim_exact_human_approval_core

                def claim_then_stop(*args, **kwargs):
                    original(*args, **kwargs)  # Real authenticated, durable started claim.
                    stop()

                seams.enter_context(patch.object(workflow, "_claim_exact_human_approval_core",
                                                 side_effect=claim_then_stop))
            elif cut == "registry_published":
                original = registry.WorkSessionRegistryStore.commit

                def commit_then_stop(store, transition, **kwargs):
                    original(store, transition, **kwargs)  # Real generation publication.
                    stop()

                seams.enter_context(patch.object(registry.WorkSessionRegistryStore, "commit",
                                                 autospec=True, side_effect=commit_then_stop))
            else:
                original = approval._ClaimedExactHumanApproval.finalize_succeeded

                def finalize_then_stop(claim):
                    original(claim)  # Real CAS/HMAC finalization and its reread.
                    stop()

                seams.enter_context(patch.object(approval._ClaimedExactHumanApproval, "finalize_succeeded",
                                                 autospec=True, side_effect=finalize_then_stop))
            execution._execute_session_decision_core(
                root, action="create", client_app_ref=apps[0],
                label="Synthetic private process workstream", reviewer_claim=REVIEWER,
                native=_SyntheticNative(), key_provider=_SyntheticKey(),
            )
            raise AssertionError("synthetic_crash_hook_not_reached")

        # A fresh process accepts neither reviewer nor approval identifier.
        # Original context comes only from the private payload, then the
        # existing broker authenticates and selects its original claim.
        seams.enter_context(patch.object(workflow, "_request_exact_human_approval_core",
                                         side_effect=AssertionError("synthetic_resume_native_forbidden")))
        if cut in {"registry_published", "succeeded_before_output"}:
            seams.enter_context(patch.object(registry.WorkSessionRegistryStore, "commit",
                                             side_effect=AssertionError("synthetic_generation_republished")))
        if cut == "succeeded_before_output":
            seams.enter_context(patch.object(operation, "apply_session_decision_with_claim",
                                             side_effect=AssertionError("synthetic_succeeded_writer_reentered")))
        store = _new_store(root)
        digest, original = _one_payload(store)
        expected_context = approval.exact_human_approval_context_sha256(original.context)
        result = execution._resume_session_decision_core(
            root, manifest_sha256=digest, key_provider=_SyntheticKey(resuming=True),
        )
        # A private context SHA proves identity without printing its reviewer.
        print(json.dumps({"result": result, "original_context_sha256": expected_context},
                         ensure_ascii=True, sort_keys=True), flush=True)


class SessionProcessJourneyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wom-session-process-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text("archive_id: " + ARCHIVE_ID + "\n", encoding="utf-8")
        self.store = _new_store(self.root)
        registered = registry.plan_transition(self.store.read(), action="register-app",
                                              label="Synthetic private process app")
        with exact.ExactOperationWriterLock(self.root) as held:
            self.store.commit(registered, held_lock=held)
        self.initial_generation = self.store.read().sha256

    def child(self, mode, cut):
        # runpy retains the repo-root source shim on sys.path; no venv, wheel,
        # environment mutation or credential transfer to the child is needed.
        script = (
            "import runpy, sys; path=sys.argv[1]; sys.argv=sys.argv[1:]; "
            "runpy.run_path(path, run_name='__main__')"
        )
        return subprocess.run(
            [sys.executable, "-B", "-c", script, str(Path(__file__).resolve()),
             "--worker", str(self.root), mode, cut],
            cwd=REPOSITORY, capture_output=True, text=True, timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def claims(self):
        return {path.name: path.read_bytes()
                for path in self.root.joinpath(*Path(approval.CLAIMS_RELATIVE_ROOT).parts).glob("*.json")}

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def claim_routing(self, filename):
        return _SyntheticKey(resuming=True).use_key(
            self.root, lambda key: approval._authenticated_claim_routing_core(self.root, filename[:-5], key))

    def run_journey(self, cut):
        crashed = self.child("cut", cut)
        self.assertEqual(crashed.returncode, CUT_EXIT_CODE, crashed.stderr)
        self.assertEqual(crashed.stdout.splitlines(), ["synthetic_worker_ready", "synthetic_native_called",
                                                      "synthetic_cut:" + cut])
        self.assertEqual(crashed.stderr, "")
        old_claims = self.claims()
        self.assertEqual(len(old_claims), 1)
        manifest_sha, bound = _one_payload(self.store)
        self.assertEqual(bound.context.reviewer_claim, REVIEWER)
        original_context_sha = approval.exact_human_approval_context_sha256(bound.context)
        expected_status = "succeeded" if cut == "succeeded_before_output" else "started"
        claim_name = next(iter(old_claims))
        self.assertEqual(self.claim_routing(claim_name), (original_context_sha, expected_status))
        if cut == "started_before_checkpoint":
            self.assertEqual(self.store.read().sha256, self.initial_generation)
            self.assertFalse((self.root / exact.EXACT_OPERATION_LOCAL_ROOT / "checkpoints").exists())
            self.assertFalse((self.root / exact.EXACT_OPERATION_RECEIPTS_ROOT).exists())
        else:
            self.assertEqual(self.store.read().sha256, bound.prepared.transition.after.sha256)
            self.assertTrue(tuple((self.root / exact.EXACT_OPERATION_LOCAL_ROOT / "checkpoints").glob("*.jsonl")))
        # Exiting without finally must release the real OS lock and retained
        # filesystem handles. This cannot pass by using a process-local mutex.
        with exact.ExactOperationWriterLock(self.root) as held:
            held.verify_held()
        plan_path = self.root.joinpath(*bundle.PRIVATE_ROOT) / (manifest_sha[7:] + ".json")
        original_plan_bytes = plan_path.read_bytes()
        generation_path = self.store.path / "000000000002.json"
        generation_bytes = generation_path.read_bytes() if generation_path.exists() else None
        resumed = self.child("resume", cut)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(resumed.stderr, "")
        lines = resumed.stdout.splitlines()
        self.assertEqual(lines[0], "synthetic_worker_ready")
        self.assertEqual(len(lines), 2)
        response = json.loads(lines[1])
        result = response["result"]
        self.assertTrue(result["ok"], result)
        self.assertEqual(response["original_context_sha256"], original_context_sha)
        self.assertFalse(result["native_approval_redisplayed"])
        self.assertTrue(result["independent_post_verification"])
        self.assertEqual(self.claims().keys(), old_claims.keys())
        self.assertEqual(self.claim_routing(claim_name), (original_context_sha, "succeeded"))
        self.assertEqual(plan_path.read_bytes(), original_plan_bytes)
        self.assertEqual(self.store.read().revision, 2)
        self.assertEqual(self.store.read().sha256, bound.prepared.transition.after.sha256)
        if generation_bytes is not None:
            self.assertEqual(generation_path.read_bytes(), generation_bytes)
        if cut == "started_before_checkpoint":
            self.assertEqual(result["started_resume_state"], "authenticated_before_first_checkpoint")
            self.assertFalse(result["resume_discovery"]["checkpoint_chain_validated_read_only"])
            self.assertTrue(result["resume_discovery"]["authenticated_precheckpoint_preimage_verified"])
        elif cut == "registry_published":
            self.assertEqual(result["started_resume_state"], "checkpoint_present")
        else:
            self.assertEqual(result["exact_human_approval_resume_branch"], "succeeded_tail")
            self.assertFalse(result["domain_writer_reentered"])
            self.assertEqual(self.claims(), old_claims)
        for marker in (REVIEWER, "Synthetic private process", str(self.root)):
            self.assertNotIn(marker, resumed.stdout)
        self.assertNotIn(claim_name[:-5], resumed.stdout)
        # Independently reread disk evidence and validate terminal HMAC with
        # the existing common audit, not merely the worker's reported success.
        before_audit = self.files()
        receipt = exact.load_exact_operation_final_receipt_read_only(self.root, result["execution_sha256"])
        self.assertEqual(receipt["receipt_sha256"], result["receipt_sha256"])
        self.assertEqual(receipt["result"]["manifest_sha256"], manifest_sha)
        authentication = receipt["result"]["completion_authentication"]
        payload = exact.exact_operation_completion_authentication_payload(receipt["result"])
        self.assertTrue(approval.audit_exact_human_approval_succeeded_terminal_record_read_only(
            self.root, authentication["approval_reference"], expected_mac=authentication["terminal_mac"],
            expected_operation=bound.context.operation, expected_plan_sha256=manifest_sha,
            expected_target_binding_sha256=bound.context.target_binding_sha256, payload=payload,
            key_provider=_SyntheticKey(resuming=True),
        ))
        verified = exact.verify_exact_operation(bound.prepared.manifest,
                                                verifier=operation._Verifier(self.store, bound.prepared), state="post")
        self.assertTrue(verified["all_match"])
        self.assertEqual(self.files(), before_audit)

    def test_started_claim_survives_real_exit_before_first_checkpoint(self):
        self.run_journey("started_before_checkpoint")

    def test_published_registry_survives_real_exit_without_republication(self):
        self.run_journey("registry_published")

    def test_succeeded_claim_survives_real_exit_before_output_without_new_writer(self):
        self.run_journey("succeeded_before_output")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--worker"]:
        if len(sys.argv) != 5:
            raise AssertionError("synthetic_worker_arity_invalid")
        _process_worker(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
    else:
        unittest.main()
