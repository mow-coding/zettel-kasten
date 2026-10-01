"""Beta letter 180: the two items a reconcile could not finish (A and B).

A: an item's child upload wrote the remote bytes, then the process was cut
before its claim was finalized; the reconcile stopped with
exact_human_approval_state_unknown. B: an item's child offload claim started
but its control file was never written; the reconcile could not rebuild the
original plan (activity_cleanup_child_control_missing_original_not_reconstructable).
Since v0.4.58 the reconcile preview diagnoses each unfinished item read-only,
an upload whose full remote bytes match is completed (its started claim is
closed as failed, never as succeeded), an offload proven to have had no effect
is started again under the new approval, an offload whose claim succeeded is
completed after the remote proof, and anything unproven keeps the file.

Also: a non-count progress value no longer kills the heartbeat thread,
operation-control gives activity-cleanup guidance instead of the index-health
text, and composed child plans skip the display-only capacity scan.

Synthetic archive, synthetic bytes and an in-memory transport only.
"""
import hashlib
import io
import json
import os
import tempfile
import threading
import time
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from wom_kit import activity_cleanup as cleanup
from wom_kit import archive_cli, archive_services as services
from wom_kit import exact_approval_claims
from wom_kit import exact_human_approval_workflow as broker, exact_human_approval_windows as windows
from wom_kit import object_storage_offload as offload, object_storage_upload_exact as upload
from wom_kit import operation_control, storage_cost

from . import test_activity_cleanup as fixture
from .test_object_storage_preservation import _MemoryTransport
from .test_v0421_source_intake_chain_exact_approval import _Native

KEYCHAIN = ["--rebind-access-key-id-ref", "credential-manager:wom-synthetic-r2-access-180",
            "--rebind-secret-access-key-ref", "credential-manager:wom-synthetic-r2-secret-180"]


def _oid(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@unittest.skipUnless(os.name == "nt", "native activity cleanup")
class Letter180ReconcileTests(unittest.TestCase):
    def setUp(self):
        fixture.ActivityCleanupTests.setUp(self)
        common = dict(archive_id=services.read_archive_id(self.root), profile_id="profile:synthetic:activity",
            profile_slug="synthetic-activity", provider_kind="cloudflare-r2", storage_account_ref="synthetic-store",
            bucket_name="synthetic-activity-bucket", region="auto", endpoint_ref="provider:endpoint:synthetic",
            objet_prefix="archives/synthetic/objets/", visibility="private")
        binding = services.build_object_storage_provider_binding(**common)
        (self.root / "provider-bindings.yml").write_text(services.dump_yaml({"version": "provider-bindings/v0.1",
            "archive_id": common["archive_id"], "bindings": [binding]}), encoding="utf-8")
        relative = services.object_storage_provider_setup_receipt_path(common["bucket_name"])
        receipt = services.build_object_storage_provider_setup_receipt(**common, receipt_path=relative,
            reviewed_by="person:synthetic", timestamp="2026-09-23T00:00:00Z", dry_run=False, manual_steps=[])
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt), encoding="utf-8")
        services.index_archive(self.root)
        self.bodies, items = {}, []
        for number in range(4):
            path = self.external / f"synthetic-{number}.bin"
            raw = f"synthetic letter-180 item {number} ".encode() * (3 + number)
            path.write_bytes(raw)
            self.bodies[number] = raw
            items.append({"path": str(path), "role": "source", "reason": "Synthetic l180 source",
                          "disposition": "preserve"})
        self.source.unlink()
        self.document["items"] = items
        self.document["storage"] = {"provider_kind": "cloudflare-r2", "store_ref": "synthetic-store",
            "access_key_id_ref": "env:WOM_SYNTHETIC_R2_ACCESS_180",
            "secret_access_key_ref": "env:WOM_SYNTHETIC_R2_SECRET_180"}
        self.request.write_text(json.dumps(self.document), encoding="utf-8")
        self.transport = _MemoryTransport()
        self.native = _Native()

    def run_cli(self, *extra, patches=()):
        output = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(broker, "_production_key_provider", return_value=self.key))
            stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
            stack.enter_context(patch.object(archive_cli, "_object_storage_live_transport_factory",
                                             return_value=lambda: self.transport))
            stack.enter_context(patch.dict(os.environ, {"WOM_SYNTHETIC_R2_ACCESS_180": "a",
                                                        "WOM_SYNTHETIC_R2_SECRET_180": "s"}))
            stack.enter_context(patch.object(services, "_tiro_windows_credential_manager_read_secret",
                                             return_value=("synthetic-secret", {})))
            for target, name, value in patches:
                stack.enter_context(patch.object(target, name, value))
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                code = archive_cli.main(["activity-cleanup", str(self.root), "--request", str(self.request),
                                         "--no-progress", *extra])
        return code, json.loads(output.getvalue())

    def reconcile(self):
        code, preview = self.run_cli("--reconcile", *KEYCHAIN, "--dry-run")
        self.assertEqual(code, 0, preview)
        code, result = self.run_cli("--reconcile", *KEYCHAIN, "--approve", "--reviewed-by", "person:synthetic",
                                    "--expected-plan-sha256", preview["plan_sha256"])
        return preview, code, result

    def claim_statuses(self, operation):
        listing = exact_approval_claims.list_exact_human_approval_claims(self.root, status="all", key_provider=self.key)
        statuses = {}
        for row in listing["claims"]:
            if row.get("operation") == operation:
                statuses[row["status"]] = statuses.get(row["status"], 0) + 1
        return statuses

    def item(self, result, number):
        return next(row for row in result["items"] if row["number"] == number)

    def assert_all_done(self, code, result):
        self.assertEqual(code, 0, result)
        self.assertEqual(result["state"], "completed")
        self.assertTrue(all(row["state"] in {"deleted", "already_deleted"} for row in result["items"]), result["items"])
        for number in range(4):
            self.assertFalse(Path(self.document["items"][number]["path"]).exists())

    def cut_offload_before_control(self, number):
        target, fired = _oid(self.bodies[number]), [False]
        original = offload._apply_concurrent

        def cut(plan, *a, **k):
            if not fired[0] and any(spec.object_id == target for spec in plan.specs):
                fired[0] = True
                raise OSError("synthetic cut before the offload control is written")
            return original(plan, *a, **k)
        return (offload, "_apply_concurrent", cut)

    def test_a_upload_cut_after_remote_put_completes_on_reconcile_and_again(self):
        target, fired = _oid(self.bodies[1]), [False]
        original_put = self.transport.put_object

        def put(**kwargs):
            result = original_put(**kwargs)
            if not fired[0] and kwargs.get("key", "").endswith(target[7:]):
                fired[0] = True
                raise OSError("synthetic cut after the remote PUT, before the receipt")
            return result
        code, first = self.run_cli("--approve", "--reviewed-by", "person:synthetic",
                                   patches=[(self.transport, "put_object", put)])
        self.assertEqual(code, 1)
        failed = self.item(first, 1)
        self.assertEqual(failed["state"], "retained")
        self.assertEqual(failed.get("child_stage"), "upload")
        self.assertEqual(self.claim_statuses("object_storage_bytes_upload").get("started"), 1)

        preview, code, result = self.reconcile()
        diagnosis = preview["pending_item_diagnosis"]
        self.assertEqual(diagnosis["state"], "read_only_diagnosis")
        self.assertFalse(diagnosis["remote_bytes_checked_now"])
        self.assertEqual([row["number"] for row in diagnosis["items"]], [1])
        self.assertEqual(diagnosis["items"][0]["reconcile_route"],
                         "upload_complete_after_remote_proof_or_resume_original_child")
        self.assertEqual(diagnosis["items"][0]["child_steps"]["upload"]["claims"], {"started": 1})
        self.assertNotIn(str(self.external), json.dumps(diagnosis))
        self.assert_all_done(code, result)
        # The started child claim is closed as failed, never as succeeded.
        self.assertNotIn("started", self.claim_statuses("object_storage_bytes_upload"))

        # Approving the same reconcile again no longer conflicts.
        _preview, code, again = self.reconcile()
        self.assert_all_done(code, again)

    def test_b_offload_cut_before_control_restarts_after_no_effect_proof(self):
        code, first = self.run_cli("--approve", "--reviewed-by", "person:synthetic",
                                   patches=[self.cut_offload_before_control(2)])
        self.assertEqual(code, 1)
        self.assertEqual(self.item(first, 2).get("child_stage"), "offload")
        preview, code, result = self.reconcile()
        row = preview["pending_item_diagnosis"]["items"][0]
        self.assertEqual(row["number"], 2)
        self.assertEqual(row["child_steps"]["offload"]["control_file"], "absent")
        self.assertEqual(row["reconcile_route"], "offload_had_no_effect_restart_offload")
        self.assert_all_done(code, result)
        self.assertNotIn("started", self.claim_statuses("object_storage_bytes_offload"))

    def test_b_offload_completed_and_control_removed_completes_after_remote_proof(self):
        target, fired = _oid(self.bodies[2]), [False]
        original = cleanup.OfficialPreservationBackend.finish_local_preservation

        def cut(backend, item):
            result = original(backend, item)
            if not fired[0] and item["object_id"] == target:
                fired[0] = True
                raise OSError("synthetic parent cut after the offload, before the delete intent")
            return result
        code, _first = self.run_cli("--approve", "--reviewed-by", "person:synthetic",
            patches=[(cleanup.OfficialPreservationBackend, "finish_local_preservation", cut)])
        self.assertEqual(code, 1)
        pointer = cleanup.Journal(self.root, "synthetic-activity", self.key).read("item-2-offload-control")
        control = self.root / offload._control_relative(pointer["manifest_sha256"])
        control.unlink()  # the customer's state: the control file is absent
        preview, code, result = self.reconcile()
        self.assertEqual(preview["pending_item_diagnosis"]["items"][0]["reconcile_route"],
                         "offload_completed_control_absent_complete_after_remote_proof")
        self.assert_all_done(code, result)

    def test_b_offload_without_control_and_unproven_effects_keeps_the_file(self):
        code, _first = self.run_cli("--approve", "--reviewed-by", "person:synthetic",
                                    patches=[self.cut_offload_before_control(2)])
        self.assertEqual(code, 1)
        target = _oid(self.bodies[2])
        local = self.root / "objects/sha256" / target[7:9] / target[7:]
        local.write_bytes(b"synthetic changed local bytes")  # no longer provably untouched
        preview, code, result = self.reconcile()
        self.assertEqual(preview["pending_item_diagnosis"]["items"][0]["reconcile_route"],
                         "offload_effects_unproven_file_kept")
        self.assertEqual(code, 1)
        kept = self.item(result, 2)
        self.assertEqual(kept["state"], "retained")
        self.assertEqual(kept["code"], "activity_cleanup_child_control_missing_effects_unproven")
        self.assertEqual(kept["child_stage"], "offload")
        self.assertTrue(Path(self.document["items"][2]["path"]).exists())


class Letter180ProgressTests(unittest.TestCase):
    def test_non_count_current_does_not_kill_the_heartbeat(self):
        caught, previous = [], threading.excepthook
        threading.excepthook = lambda arguments: caught.append(arguments.exc_type.__name__)
        self.addCleanup(setattr, threading, "excepthook", previous)
        with redirect_stderr(io.StringIO()) as stream:
            reporter = archive_cli.CommandProgressReporter(True, label="activity-cleanup",
                                                           heartbeat_interval_seconds=0.02)
            try:
                reporter.progress("activity-cleanup-items", "start", 0, 3)
                reporter.progress("activity-cleanup-items", "staging-source", "2-streams", 3)
                time.sleep(0.2)
                alive = reporter._thread.is_alive()
            finally:
                reporter.close()
        self.assertTrue(alive)
        self.assertEqual(caught, [])
        self.assertIn("heartbeat", stream.getvalue())
        self.assertEqual(reporter.observations()["progress_contract_violations"], 1)

    def test_stream_child_reports_its_parent_position(self):
        self.assertEqual(cleanup._position({"number": 4}), 5)
        self.assertEqual(cleanup._position({"number": "4-streams"}), 5)
        self.assertIsNone(cleanup._position({"number": "streams"}))


class Letter180OperationControlTests(unittest.TestCase):
    def completed(self, root, command):
        relative = ".wom-scratch/diagnostics/" + command + ".json"
        journal = operation_control.OperationRunJournal.prepare(root, output_relative=relative, command=command,
            run_id=hashlib.md5(command.encode()).hexdigest())
        path = root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ok": False, "state": "partial", "dry_run": False, "writes_performed": True,
            "items": [{"number": 0, "state": "deleted"},
                      {"number": 1, "state": "retained", "code": "activity_cleanup_child_control_missing_effects_unproven"}],
            "measurements": {"completed_item_count": 1, "retained_item_count": 1, "unprocessed_item_count": 0},
            "cli_execution": {"status": "completed", "run_id": journal.run_id, "command": journal.command,
                              "exit_code": 1, "result_available": True},
            "cli_output_artifact": {"command": journal.command, "operation": journal.metadata()}}
        path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        self.assertTrue(journal.complete(exit_code=1, result_available=True, result_ok=False, result_path=path))
        return operation_control.recovery_plan(root, journal.operation_ref)

    def test_recovery_plan_names_the_command_not_index_health(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "archive.yml").write_text("archive_id: synthetic\n", encoding="utf-8")
            plan = self.completed(root, "activity-cleanup")
            text = " ".join(plan["next_safe_actions"])
            self.assertNotIn("index-health", text)
            self.assertIn("--reconcile --dry-run", text)
            self.assertIn("do not mean the cleanup succeeded", text)
            self.assertEqual(plan["command_outcome"], "finished_not_successful")
            domain = plan["result"]["domain"]
            self.assertEqual(domain["state"], "partial")
            self.assertEqual(domain["counts"]["retained_item_count"], 1)
            self.assertEqual(domain["item_codes"], ["activity_cleanup_child_control_missing_effects_unproven"])
            upload_plan = self.completed(root, "object-storage-upload")
            self.assertNotIn("index-health", " ".join(upload_plan["next_safe_actions"]))
            self.assertIn("object-storage-upload --dry-run", " ".join(upload_plan["next_safe_actions"]))


class Letter180CapacityTests(unittest.TestCase):
    def test_composed_child_planning_skips_the_display_only_capacity_scan(self):
        with storage_cost.composed_child_planning():
            summary = storage_cost.capacity(Path("unused"), {"sha256:" + "0" * 64: [{"size_bytes": 1}]})
        self.assertEqual(summary["state"], storage_cost.NOT_COMPUTED)
        estimate = storage_cost.estimate_capacity(summary)
        self.assertFalse(estimate["available"])
        self.assertEqual(estimate["reason"], storage_cost.NOT_COMPUTED)


if __name__ == "__main__":
    unittest.main()
