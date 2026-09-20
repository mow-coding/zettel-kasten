"""v0.4.33 (beta letter 164 ①③④): object-storage-upload reopened as preservation PUT + adoption projection.

Synthetic archives and an in-memory transport only. The command level uses the
fake native dialog and patches the transport resolver inside the live seam.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from wom_kit import archive_cli, archive_services, command_status
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import object_storage_preservation as preservation
from wom_kit import object_storage_upload_exact as upload
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID, IDCANCEL, ExactHumanApprovalOperation
from wom_kit.exact_operation_manifest import (
    ExactOperationManifestError,
    FileExactOperationCheckpointStore,
    exact_operation_writer_lock,
)
from wom_kit.work_session_permission import ALWAYS_DIALOG_OPERATIONS, GRANTABLE_OPERATIONS

import test_v0428_object_storage_restore as restore_fixture
from test_object_storage_preservation import _MemoryTransport

STORE = restore_fixture.STORE
PROVIDER = restore_fixture.PROVIDER
REVIEWER = "person:synthetic-upload-reviewer"


def _key(raw: bytes) -> str:
    digest = hashlib.sha256(raw).hexdigest()
    return f"sha256/{digest[:2]}/{digest}"


def _oid(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _external_row(raw: bytes) -> dict:
    return restore_fixture._row(
        raw,
        locations=[
            {
                "provider": "external_prehashed",
                "store_kind": "usb",
                "store_ref": "shelf-a",
                "availability": "declared_external",
                "content_addressed": True,
                "byte_verification_by_wom_kit": False,
            }
        ],
    )


def _run(plan, transport, *, resume=False):
    with exact_operation_writer_lock(plan.archive_root) as lock:
        upload._persist_control(plan)
        checkpoints = FileExactOperationCheckpointStore(plan.archive_root, writer_lock=lock)
        return upload._apply_with_store(
            plan,
            restore_fixture._authority(),
            transport,
            checkpoints,
            reviewed_by=REVIEWER,
            resume=resume,
            progress_hook=None,
        )


class _Archive:
    """One synthetic archive with a registered store; rows are written on demand."""

    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="wom-v0433-upload-")
        self.root = restore_fixture._build_root(Path(self.temporary.name).resolve())

    def close(self) -> None:
        self.temporary.cleanup()

    def local(self, raw: bytes) -> dict:
        restore_fixture._write_local(self.root, raw)
        return restore_fixture._row(raw, locations=[restore_fixture._local(raw)])

    def write(self, rows: list[dict]) -> None:
        restore_fixture._write_rows(self.root, rows)

    def plan(self, **kwargs):
        return upload.plan_object_storage_upload(self.root, provider_kind=PROVIDER, store_ref=STORE, **kwargs)

    def rows(self) -> dict[str, dict]:
        return restore_fixture._rows_after(self.root)


class UploadPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.archive = _Archive()
        self.addCleanup(self.archive.close)

    def test_kind_is_registered_grantable_and_reopened(self) -> None:
        kind = ExactHumanApprovalOperation.object_storage_bytes_upload
        self.assertNotIn(kind, ALWAYS_DIALOG_OPERATIONS)  # v0.4.36 (letter 168 ⑥): grantable
        self.assertIn(kind, GRANTABLE_OPERATIONS)
        for table in (windows._OPERATION_LABELS, windows._OPERATION_QUESTIONS, windows._OPERATION_SUMMARIES, windows._OPERATION_APPROVE_BUTTONS):
            self.assertIn(kind, table)
        self.assertTrue(windows._OPERATION_QUESTIONS[kind].endswith("까요?"))
        self.assertNotIn("object-storage-upload", command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)
        self.assertIn("object-storage-upload", command_status.EXACT_APPROVAL_REOPENED_WRITERS)
        self.assertIs(archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS, command_status.COMPOUND_APPROVAL_FIXED_CLOSED_COMMANDS)

    def test_writer_line_comes_before_any_manifest_read(self) -> None:
        self.archive.write([self.archive.local(b"never read")])
        with patch.object(preservation, "_read_manifest_groups", side_effect=AssertionError("manifest read")):
            unsupported = upload.plan_object_storage_upload(self.archive.root, provider_kind="aws-s3", store_ref=STORE)
            missing = upload.plan_object_storage_upload(self.archive.root, provider_kind=PROVIDER, store_ref="storage:account:none")
            bad_ref = upload.plan_object_storage_upload(self.archive.root, provider_kind=PROVIDER, store_ref="not/a/label")
        for plan, reason in ((unsupported, "provider_unsupported"), (missing, "store_setup_missing"), (bad_ref, "store_ref_invalid")):
            document = plan.public_document()
            self.assertEqual(plan.writer_state, "unavailable")
            self.assertEqual(plan.writer_unavailable_reason, reason)
            self.assertFalse(plan.manifest_scanned)
            self.assertEqual(document["state"], "writer_unavailable")
            self.assertEqual(document["blockers"], ["writer_unavailable"])
            self.assertEqual(document["upload_planned_count"], 0)
            self.assertFalse(document["ok"])
            self.assertIsNone(document["plan_sha256"])

    def test_classification_counts_every_manifest_state_and_hashes_only_candidates(self) -> None:
        local = self.archive.local(b"plain local candidate")
        uploaded_raw = b"already uploaded"
        uploaded = restore_fixture._row(
            uploaded_raw, locations=[restore_fixture._local(uploaded_raw), restore_fixture._remote(uploaded_raw)]
        )
        restore_fixture._write_local(self.archive.root, uploaded_raw)
        offloaded_raw = b"offloaded bytes"
        offloaded = restore_fixture._row(offloaded_raw, locations=[restore_fixture._local(offloaded_raw, availability="offloaded")])
        absent_raw = b"manifest claims bytes that are absent"
        absent = restore_fixture._row(absent_raw, locations=[restore_fixture._local(absent_raw)])
        wrong_raw = b"size conflict bytes"
        wrong = restore_fixture._row(wrong_raw, locations=[restore_fixture._local(wrong_raw)])
        restore_fixture._write_local(self.archive.root, wrong_raw + b"!")
        wrong_path = restore_fixture._dest(self.archive.root, wrong_raw)
        wrong_path.parent.mkdir(parents=True, exist_ok=True)
        wrong_path.write_bytes(wrong_raw + b"!")
        external = _external_row(b"external prehashed")
        preserved_raw = b"emergency preserved only"
        preserved = self.archive.local(preserved_raw)
        receipt_dir = self.archive.root / preservation.RECEIPT_ROOT
        receipt_dir.mkdir(parents=True, exist_ok=True)
        (receipt_dir / f"{hashlib.sha256(preserved_raw).hexdigest()}.0000000000000000.json").write_text(
            json.dumps(
                {
                    "object_id": _oid(preserved_raw),
                    "provider_kind": PROVIDER,
                    "store_ref": STORE,
                    "preservation_status": "bytes_preserved",
                }
            ),
            encoding="utf-8",
        )
        self.archive.write([local, uploaded, offloaded, absent, wrong, external, preserved])

        refused = self.archive.plan()
        document = refused.public_document()
        self.assertEqual(document["state"], "local_bytes_missing")
        self.assertEqual(document["blockers"], ["local_bytes_missing"])
        self.assertFalse(document["ok"])
        classification = document["classification"]
        self.assertEqual(classification["excluded_byte_external_count"], 1)
        self.assertEqual(classification["excluded_already_uploaded_count"], 1)
        self.assertEqual(classification["excluded_already_preserved_count"], 1)
        self.assertEqual(classification["excluded_offloaded_count"], 1)
        self.assertEqual(classification["local_absent_count"], 1)
        self.assertEqual(classification["local_size_conflict_count"], 1)
        self.assertEqual(classification["candidate_count"], 1)
        self.assertEqual(document["provider_calls_in_plan"], 0)
        self.assertTrue(any("--local-bytes-only" in action for action in document["next_safe_actions"]))
        self.assertTrue(any("--formal-adoption" in action for action in document["next_safe_actions"]))

        proceeding = self.archive.plan(local_bytes_only=True)
        document = proceeding.public_document()
        self.assertEqual(document["state"], "ready_for_exact_human_approval")
        self.assertTrue(document["ok"])
        self.assertEqual(document["upload_planned_count"], 1)
        self.assertEqual(document["planned_upload_bytes"], len(b"plain local candidate"))
        self.assertEqual(document["classification"]["local_absent_count"], 1)
        self.assertTrue(proceeding.approveable)
        # privacy: no id, key, path or label of a row in the public plan
        rendered = json.dumps(document)
        for private in (hashlib.sha256(b"plain local candidate").hexdigest(), "objects/sha256", str(self.archive.root), "shelf-a"):
            self.assertNotIn(private, rendered)

    def test_max_objects_bounds_candidates_and_only_selects_one(self) -> None:
        rows = [self.archive.local(f"candidate {index}".encode()) for index in range(4)]
        self.archive.write(rows)
        bounded = self.archive.plan(max_objects=2)
        document = bounded.public_document()
        self.assertEqual(document["upload_planned_count"], 2)
        self.assertEqual(document["classification"]["excluded_by_filter_count"], 2)
        self.assertEqual(document["max_objects"], 2)
        chosen = rows[3]["object_id"]
        only = self.archive.plan(only=chosen)
        self.assertEqual(only.public_document()["upload_planned_count"], 1)
        self.assertEqual(only.specs[0].object_id, chosen)
        self.assertEqual(only.public_document()["classification"]["excluded_by_filter_count"], 3)
        with self.assertRaises(upload.ObjectStorageUploadError) as caught:
            self.archive.plan(only=_oid(b"not in the manifest"))
        self.assertEqual(caught.exception.code, "object_storage_upload_no_writes")

    def test_no_new_bytes_is_calm(self) -> None:
        raw = b"already uploaded everywhere"
        restore_fixture._write_local(self.archive.root, raw)
        self.archive.write([restore_fixture._row(raw, locations=[restore_fixture._local(raw), restore_fixture._remote(raw)])])
        document = self.archive.plan().public_document()
        self.assertEqual(document["state"], "no_new_bytes_to_upload")
        self.assertEqual(document["reason_codes"], ["object_storage_upload_no_writes"])
        self.assertIsNone(document["plan_sha256"])


class UploadExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.archive = _Archive()
        self.addCleanup(self.archive.close)
        self.a = b"alpha bytes absent remotely"
        self.b = b"beta bytes already remote and identical"
        self.c = b"gamma bytes whose remote copy differs"
        self.archive.write([self.archive.local(raw) for raw in (self.a, self.b, self.c)])
        self.transport = _MemoryTransport()
        self.transport.objects[_key(self.b)] = self.b
        self.conflict = bytes(len(self.c))  # same length, different bytes → checksum mismatch
        self.transport.objects[_key(self.c)] = self.conflict

    def test_put_skip_and_review_with_one_projection_and_receipts(self) -> None:
        plan = self.archive.plan()
        result = _run(plan, self.transport)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"], "completed_with_review")
        self.assertEqual(result["status_counts"], {"uploaded": 1, "skipped_remote_same": 1, "review_required": 1})
        self.assertEqual(self.transport.put_calls, 1)
        self.assertEqual(result["manifest_location_updates"], 2)
        self.assertEqual(result["receipts_created_count"], 3)
        self.assertEqual(result["bytes_uploaded"], len(self.a))
        self.assertFalse(result["existing_remote_copy_overwritten"])
        self.assertEqual(self.transport.objects[_key(self.c)], self.conflict)
        rows = self.archive.rows()
        for raw, expected in ((self.a, True), (self.b, True), (self.c, False)):
            present = any(location.get("availability") == "wom_uploaded" for location in rows[_oid(raw)]["locations"])
            self.assertEqual(present, expected, raw)
        location = next(l for l in rows[_oid(self.a)]["locations"] if l.get("availability") == "wom_uploaded")
        self.assertEqual(location["remote_key"], _key(self.a))
        self.assertEqual(location["remote_key_verification"], "content_hash")
        self.assertTrue(location["byte_verification_by_wom_kit"])
        self.assertTrue(archive_services.safe_object_storage_execution_receipt_relative(location["execution_receipt_ref"]))
        self.assertTrue(archive_services.require_current_zettel_index(self.archive.root)["ok"])
        # receipts: v0.3 execution-receipt contract plus the exact-approval fields
        by_id = {spec.object_id: spec for spec in plan.specs}
        uploaded = json.loads((self.archive.root / by_id[_oid(self.a)].receipt_relative).read_text(encoding="utf-8"))
        self.assertEqual(uploaded["schema"], archive_services.OBJECT_STORAGE_UPLOAD_RECEIPT_SCHEMA)
        self.assertEqual(uploaded["result_status"], "uploaded")
        self.assertTrue(uploaded["manifest_update_applied"])
        self.assertEqual(uploaded["exact_operation_manifest_sha256"], plan.manifest.manifest_sha256)
        self.assertEqual(uploaded["remote_verification"]["verification_kind"], "get_rehash_whole_object")
        self.assertEqual(uploaded["reviewed_by"], REVIEWER)
        self.assertFalse(uploaded["forced_reupload"])
        review = json.loads((self.archive.root / by_id[_oid(self.c)].receipt_relative).read_text(encoding="utf-8"))
        self.assertEqual(review["result_status"], "remote_conflict_different_bytes")
        self.assertFalse(review["manifest_update_applied"])
        self.assertEqual(review["review_reason"], "remote_checksum_mismatch")
        codes, _read = archive_services.backup_evidence_receipt_validation_codes(
            self.archive.root,
            archive_id=archive_services.read_archive_id(self.archive.root),
            object_id=_oid(self.a),
            location=location,
            receipt_cache={},
        )
        self.assertEqual(codes, [])
        verified = upload.verify_object_storage_upload(plan, transport=self.transport)
        self.assertTrue(verified["ok"])
        self.assertEqual(verified["verified_item_count"], 3)
        # a replan excludes the two verified objects and re-offers the conflict
        replan = self.archive.plan().public_document()
        self.assertEqual(replan["classification"]["excluded_already_uploaded_count"], 2)
        self.assertEqual(replan["upload_planned_count"], 1)

    def test_resume_after_the_objects_creates_projection_and_receipts_without_a_second_put(self) -> None:
        plan = self.archive.plan()
        # crash right after the per-object items: the batch item never ran
        with patch.object(upload, "_apply_manifest_batch", side_effect=RuntimeError("crash before projection")):
            with self.assertRaises(RuntimeError):
                _run(plan, self.transport)
        self.assertEqual(self.transport.put_calls, 1)
        rows = self.archive.rows()
        self.assertFalse(any(l.get("availability") == "wom_uploaded" for l in rows[_oid(self.a)]["locations"]))
        self.assertFalse(any((self.archive.root / spec.receipt_relative).exists() for spec in plan.specs))
        loaded = upload.load_object_storage_upload_plan(self.archive.root, manifest_sha256=plan.manifest.manifest_sha256)
        self.assertTrue(loaded.loaded_from_control)
        resumed = _run(loaded, self.transport, resume=True)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(self.transport.put_calls, 1)
        self.assertEqual(resumed["manifest_location_updates"], 2)
        self.assertEqual(resumed["receipts_created_count"], 3)
        # and a second resume is a no-op that still reports the durable state
        again = _run(
            upload.load_object_storage_upload_plan(self.archive.root, manifest_sha256=plan.manifest.manifest_sha256),
            self.transport,
            resume=True,
        )
        self.assertTrue(again["ok"], again)
        self.assertEqual(self.transport.put_calls, 1)
        self.assertEqual(again["manifest_location_updates"], 0)
        self.assertEqual(again["receipts_created_count"], 0)

    def test_transport_failure_leaves_no_receipt_and_resumes(self) -> None:
        self.archive.write([self.archive.local(self.a)])
        plan = self.archive.plan()
        failing = _MemoryTransport(unavailable_calls={1})
        # the exact framework wraps every writer failure into its own fixed code
        with self.assertRaises(ExactOperationManifestError) as caught:
            _run(plan, failing)
        self.assertEqual(caught.exception.code, "exact_operation_write_failed")
        self.assertEqual(failing.put_calls, 0)
        self.assertFalse((self.archive.root / plan.specs[0].receipt_relative).exists())
        loaded = upload.load_object_storage_upload_plan(self.archive.root, manifest_sha256=plan.manifest.manifest_sha256)
        resumed = _run(loaded, failing, resume=True)
        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(failing.put_calls, 1)
        self.assertEqual(resumed["status_counts"]["uploaded"], 1)

    def test_source_drift_is_refused_before_any_put(self) -> None:
        self.archive.write([self.archive.local(self.a)])
        plan = self.archive.plan()
        restore_fixture._dest(self.archive.root, self.a).write_bytes(self.a + b" drifted")
        with self.assertRaises(ExactOperationManifestError) as caught:
            _run(plan, self.transport)
        self.assertEqual(caught.exception.code, "exact_operation_payload_mismatch")
        self.assertEqual(self.transport.put_calls, 0)
        self.assertEqual(self.transport.head_calls, 0)

    def test_stale_index_blocks_before_any_put(self) -> None:
        plan = self.archive.plan()
        with patch.object(upload.restore, "_require_manifest_index_authority_for", side_effect=upload.restore.ObjectStorageRestoreError("archive_index_rebuild_required")):
            with self.assertRaises(upload.ObjectStorageUploadError) as caught:
                _run(plan, self.transport)
        self.assertEqual(caught.exception.code, "archive_index_rebuild_required")
        self.assertEqual(self.transport.put_calls, 0)


class _Native:
    def __init__(self) -> None:
        self.approve = True
        self.calls = 0
        self.contexts: list[dict] = []

    def show(self, **kwargs):
        self.calls += 1
        self.contexts.append(dict(kwargs))
        return (APPROVE_BUTTON_ID if self.approve else IDCANCEL), True


class UploadCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.archive = _Archive()
        self.addCleanup(self.archive.close)
        self.raw = b"cli uploaded object bytes"
        self.archive.write([self.archive.local(self.raw)])
        self.native = _Native()
        self.transport = _MemoryTransport()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=restore_fixture._KeyProvider()))
        stack.enter_context(patch.dict(os.environ, {"WOM_TEST_UPLOAD_AK": "AKIAEXAMPLE", "WOM_TEST_UPLOAD_SK": "s" * 40}))
        stack.enter_context(patch.object(archive_services, "_object_storage_resolve_transport", return_value=self.transport))
        self.outputs: list[str] = []

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        self.outputs.extend((out.getvalue(), err.getvalue()))
        return code, json.loads(out.getvalue())

    def base_args(self) -> list[str]:
        return [
            "object-storage-upload", str(self.archive.root),
            "--provider-kind", PROVIDER, "--store-ref", STORE,
            "--endpoint-host", "acct.r2.cloudflarestorage.com", "--bucket", "private-bucket",
            "--access-key-id-ref", "env:WOM_TEST_UPLOAD_AK", "--secret-access-key-ref", "env:WOM_TEST_UPLOAD_SK",
        ]

    def test_dry_run_then_approve_uploads_through_the_live_seam(self) -> None:
        code, preview = self.run_cli(*self.base_args(), "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["state"], "ready_for_exact_human_approval")
        self.assertEqual(preview["writer_state"], "available")
        self.assertEqual(preview["upload_planned_count"], 1)
        self.assertEqual(self.native.calls, 0)
        self.assertEqual(self.transport.put_calls, 0)
        code, result = self.run_cli(
            *self.base_args(), "--approve", "--reviewed-by", REVIEWER,
            "--expected-manifest-sha256", preview["plan_sha256"],
        )
        self.assertEqual(code, 0, result)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.native.calls, 1)
        context = self.native.contexts[0]
        self.assertIn("올리기", str(context.get("main_instruction")) + str(context.get("approve_button_text")))
        self.assertEqual(result["status_counts"]["uploaded"], 1)
        self.assertEqual(self.transport.put_calls, 1)
        self.assertEqual(self.transport.objects[_key(self.raw)], self.raw)
        rows = self.archive.rows()
        self.assertTrue(any(l.get("availability") == "wom_uploaded" for l in rows[_oid(self.raw)]["locations"]))
        rendered = "".join(self.outputs) + json.dumps(self.native.contexts, ensure_ascii=False)
        self.assertNotIn("s" * 40, rendered)
        self.assertNotIn(_key(self.raw), rendered)
        self.assertNotIn(str(self.archive.root), rendered)
        self.assertNotIn("private-bucket", rendered)
        self.assertNotIn("acct.r2.cloudflarestorage.com", rendered)
        self.assertNotIn(REVIEWER, "".join(self.outputs))
        self.assertNotIn("env:WOM_TEST_UPLOAD_SK", "".join(self.outputs))

    def test_cancelled_dialog_writes_nothing(self) -> None:
        _code, preview = self.run_cli(*self.base_args(), "--dry-run")
        self.native.approve = False
        code, result = self.run_cli(
            *self.base_args(), "--approve", "--reviewed-by", REVIEWER,
            "--expected-manifest-sha256", preview["plan_sha256"],
        )
        self.assertEqual(code, 1, result)
        self.assertFalse(result["ok"])
        self.assertEqual(self.transport.put_calls, 0)
        rows = self.archive.rows()
        self.assertFalse(any(l.get("availability") == "wom_uploaded" for l in rows[_oid(self.raw)]["locations"]))
        self.assertFalse((self.archive.root / archive_services.OBJECT_STORAGE_EXECUTIONS_DIR).exists())

    def test_writer_unavailable_dry_run_reports_the_line_first_and_approve_refuses(self) -> None:
        code, preview = self.run_cli("object-storage-upload", str(self.archive.root), "--provider-kind", "aws-s3", "--store-ref", STORE, "--dry-run")
        self.assertEqual(code, 1, preview)
        self.assertEqual(preview["state"], "writer_unavailable")
        self.assertEqual(preview["writer_unavailable_reason"], "provider_unsupported")
        self.assertFalse(preview["manifest_scanned"])
        code, refused = self.run_cli(
            "object-storage-upload", str(self.archive.root), "--provider-kind", "aws-s3", "--store-ref", STORE,
            "--endpoint-host", "acct.r2.cloudflarestorage.com", "--bucket", "private-bucket",
            "--access-key-id-ref", "env:WOM_TEST_UPLOAD_AK", "--secret-access-key-ref", "env:WOM_TEST_UPLOAD_SK",
            "--approve", "--reviewed-by", REVIEWER, "--expected-manifest-sha256", "sha256:" + "0" * 64,
        )
        self.assertEqual(code, 1, refused)
        self.assertIn("object_storage_upload_writer_unavailable", refused["reason_codes"])
        self.assertEqual(self.native.calls, 0)

    def test_stale_plan_digest_never_opens_a_dialog(self) -> None:
        code, refused = self.run_cli(
            *self.base_args(), "--approve", "--reviewed-by", REVIEWER,
            "--expected-manifest-sha256", "sha256:" + "f" * 64,
        )
        self.assertEqual(code, 1, refused)
        self.assertIn("object_storage_upload_plan_changed", refused["reason_codes"])
        self.assertEqual(self.native.calls, 0)
        self.assertEqual(self.transport.put_calls, 0)

    def test_legacy_service_function_still_refuses_approve(self) -> None:
        result = archive_services.object_storage_upload_run(self.archive.root, store_ref=STORE, approve=True, reviewed_by=REVIEWER)
        self.assertFalse(result["ok"])
        self.assertIn("compound_exact_human_approval_binding_required", result["reason_codes"])

    def test_help_and_progress_table_name_the_reopened_command(self) -> None:
        from wom_kit import cli_entry

        self.assertIn("object-storage-upload", cli_entry._PROGRESS_COMMANDS)
        self.assertIn("objet-storage-upload", cli_entry._PROGRESS_COMMANDS)
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            try:
                archive_cli.main(["object-storage-upload", "--help"])
            except SystemExit:
                pass
        help_text = out.getvalue()
        self.assertIn("--local-bytes-only", help_text)
        self.assertIn("--expected-manifest-sha256", help_text)
        self.assertNotIn("--force-reupload", help_text)
        self.assertNotIn("Unavailable in v", help_text)


if __name__ == "__main__":
    unittest.main()
