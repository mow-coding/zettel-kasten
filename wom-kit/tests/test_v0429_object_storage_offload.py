"""v0.4.29: object-storage offload (OB-02) — the offloaded state and its readers.

Part 1 (this block): every reader of a local objet location treats
``availability: offloaded`` as a recovery dependency, never as corruption or a
strict failure. Doctor reports INFO, backup-evidence counts remote-only
objects, staged-cleanup-check defers the staged copy until restore.
Part 2 (below): the offload writer itself.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from wom_kit import archive_cli, archive_services

import test_v0428_object_storage_restore as restore_tests

KIT_ROOT = Path(__file__).resolve().parents[1]
STORE = restore_tests.STORE
PROVIDER = restore_tests.PROVIDER


def _offloaded(raw: bytes) -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "provider": "local",
        "path": f"objects/sha256/{digest[:2]}/{digest}",
        "availability": "offloaded",
        "offload_receipt_ref": "receipts/providers/object-storage-offload/synthetic.json",
        "offloaded_at": "2026-09-19T00:00:00Z",
    }


def _fake_archive(parent: Path) -> Path:
    root = parent / "archive"
    shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
    return root


def _append_rows(root: Path, rows: list[dict]) -> None:
    manifest = root / "objects" / "manifests" / "files.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    archive_id = archive_services.read_archive_id(root)
    with manifest.open("a", encoding="utf-8") as handle:
        for row in rows:
            row = dict(row)
            row["provenance"] = {**row["provenance"], "created_in": f"archive:{archive_id}"}
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    archive_services.index_archive(root)


def _doctor(root: Path, *extra: str) -> tuple[int, list[dict]]:
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        code = archive_cli.main(["doctor", str(root), *extra, "--format", "json"])
    return code, json.loads(out.getvalue())


class OffloadedStateReaderTests(unittest.TestCase):
    def test_doctor_reports_offloaded_bytes_as_info_and_strict_still_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fake_archive(Path(tmp))
            baseline_code, baseline = _doctor(root, "--strict")
            self.assertEqual(baseline_code, 0, [d for d in baseline if d.get("severity") != "INFO"])
            gone = b"offloaded bytes, not on disk"
            _append_rows(root, [restore_tests._row(gone, locations=[_offloaded(gone), restore_tests._remote(gone)])])
            code, diagnostics = _doctor(root, "--strict")
            codes = [item.get("code") for item in diagnostics]
            self.assertIn("local_object_offloaded", codes)
            self.assertNotIn("local_object_missing", codes)
            self.assertEqual(code, 0, [d for d in diagnostics if d.get("severity") != "INFO"])
            info = next(item for item in diagnostics if item.get("code") == "local_object_offloaded")
            self.assertEqual(info["severity"], "INFO")
            self.assertIn("object-storage-restore", info["message"])
            summary = next(item for item in diagnostics if item.get("code") == "local_object_bytes_rehashed_now")["details"]
            self.assertEqual(summary["offloaded_local_reference_count"], 1)
            self.assertEqual(summary["unresolved_local_reference_count"], 0)
            self.assertTrue(summary["byte_integrity_verified"], summary)
            self.assertNotIn(str(root), json.dumps(diagnostics))

    def test_doctor_warns_when_bytes_exist_under_an_offloaded_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fake_archive(Path(tmp))
            back = b"bytes came back by hand"
            _append_rows(root, [restore_tests._row(back, locations=[_offloaded(back), restore_tests._remote(back)])])
            restore_tests._write_local(root, back)
            code, diagnostics = _doctor(root, "--strict")
            codes = [item.get("code") for item in diagnostics]
            self.assertIn("local_object_offloaded_but_present", codes)
            self.assertNotIn("local_object_offloaded", codes)
            self.assertNotIn("local_object_missing", codes)
            self.assertEqual(code, 1)  # a WARN under --strict: the row should be reactivated
            warn = next(item for item in diagnostics if item.get("code") == "local_object_offloaded_but_present")
            self.assertEqual(warn["severity"], "WARN")
            self.assertIn("object-storage-restore --only", warn["message"])
            summary = next(item for item in diagnostics if item.get("code") == "local_object_bytes_rehashed_now")["details"]
            self.assertEqual(summary["offloaded_local_reference_count"], 0)
            self.assertTrue(summary["byte_integrity_verified"], summary)

    def test_backup_evidence_counts_remote_only_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            local = b"local and remote"
            offloaded = b"offloaded with valid remote evidence"
            offloaded_unproven = b"offloaded but only declared"
            rows = [
                restore_tests._row(local, locations=[restore_tests._local(local), restore_tests._remote(local)]),
                restore_tests._row(offloaded, locations=[_offloaded(offloaded), restore_tests._remote(offloaded)]),
                restore_tests._row(offloaded_unproven, locations=[_offloaded(offloaded_unproven), {"provider": "object_storage", "availability": "declared_uploaded", "store_ref": STORE}]),
            ]
            restore_tests._write_rows(root, rows)
            restore_tests._write_local(root, local)
            result = archive_services.backup_evidence_status(root)
            lane = result["lanes"]["object_storage"]
            self.assertEqual(lane["local_location_object_count"], 1)
            self.assertEqual(lane["offloaded_local_location_object_count"], 2)
            # the synthetic remote location points at no execution receipt, so no
            # object counts as receipt-verified here; remote_only requires valid evidence
            self.assertEqual(lane["remote_only_object_count"], lane["receipt_verified_object_count"] and 1 or 0)
            self.assertFalse(result["privacy_guards"]["object_ids_echoed"])

    def test_staged_cleanup_defers_an_offloaded_objet_instead_of_calling_it_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fake_archive(Path(tmp))
            staged = root / "staging" / "incoming"
            staged.mkdir(parents=True, exist_ok=True)
            raw = b"staged copy of an offloaded objet"
            (staged / "note.txt").write_bytes(raw)
            _append_rows(root, [restore_tests._row(raw, locations=[_offloaded(raw), restore_tests._remote(raw)])])
            result = archive_services.staged_cleanup_check(root, "staging/incoming")
            self.assertFalse(result["safe_to_cleanup"])
            self.assertEqual(result["state"], "not_safe_to_cleanup")
            entry = next(item for item in result["files"] if item["path"] == "note.txt")
            self.assertEqual(entry["status"], "deferred")
            self.assertFalse(entry["preserved_bytes_verified"])
            self.assertTrue(entry["manifest_record_present"])
            entries = [item for item in result["entries"] if item["status"] == "deferred"]
            self.assertTrue(any(item["reason_code"] == "objet_bytes_offloaded_remote_only_restore_before_cleanup" for item in entries), result["entries"])
            self.assertNotIn("objet_store_missing_or_sha256_mismatch", json.dumps(result))
            self.assertFalse(result["deletion_performed"])
            self.assertNotIn(str(root), json.dumps(result))


# --- Part 2: the offload writer ---------------------------------------------------

import os
from contextlib import ExitStack
from unittest.mock import patch

from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import object_storage_offload as offload
from wom_kit import object_storage_restore as restore
from wom_kit.exact_human_approval_windows import ExactHumanApprovalOperation
from wom_kit.exact_operation_manifest import (
    ExactOperationManifestError,
    FileExactOperationCheckpointStore,
    exact_operation_writer_lock,
)
from wom_kit.work_session_permission import ALWAYS_DIALOG_OPERATIONS

REVIEWER = "person:synthetic-offload-reviewer"
OLD = "2026-01-01T00:00:00Z"


class _ProofTransport:
    """Provider double for offload: hash-only GET through head_object."""

    def __init__(self, objects: dict[str, bytes], *, unavailable_first: int = 0) -> None:
        self.objects = dict(objects)
        self.head_calls = 0
        self.get_calls = 0
        self.put_calls = 0
        self.delete_calls = 0
        self.unavailable_first = unavailable_first

    def head_object(self, *, key, presence_only=False):
        self.head_calls += 1
        if self.unavailable_first > 0:
            self.unavailable_first -= 1
            return {"present": False, "size": None, "checksum_sha256": None, "presence_state": "unavailable", "verification_state": "unavailable"}
        if key not in self.objects:
            return {"present": False, "size": None, "checksum_sha256": None, "presence_state": "absent", "verification_state": "complete"}
        body = self.objects[key]
        return {
            "present": True,
            "size": len(body),
            "checksum_sha256": None if presence_only else hashlib.sha256(body).hexdigest(),
            "presence_state": "present",
            "verification_state": "complete",
        }

    def get_object(self, **_kwargs):
        self.get_calls += 1
        raise AssertionError("offload proves remote bytes through the hash-only GET, never a sink")

    def put_object(self, **_kwargs):
        self.put_calls += 1
        raise AssertionError("offload never PUTs")

    def delete_object(self, **_kwargs):
        self.delete_calls += 1
        raise AssertionError("offload never deletes the remote object")


def _aged_row(raw: bytes, *, captured_at: str = OLD, source: str = "b4_local_objet_capture") -> dict:
    row = restore_tests._row(raw, locations=[restore_tests._local(raw), restore_tests._remote(raw)])
    row["provenance"] = {**row["provenance"], "captured_at": captured_at, "source": source}
    return row


def _run_offload(plan, transport, *, resume=False):
    with exact_operation_writer_lock(plan.archive_root) as lock:
        offload._persist_control(plan)
        checkpoints = FileExactOperationCheckpointStore(plan.archive_root, writer_lock=lock)
        return offload._apply_with_store(plan, restore_tests._authority(), transport, checkpoints, resume=resume, progress_hook=None)


def _objects_for(plan, payloads: dict[str, bytes]) -> dict[str, bytes]:
    by_id = {"sha256:" + hashlib.sha256(raw).hexdigest(): raw for raw in payloads.values()}
    return {spec.remote_key: by_id[spec.object_id] for spec in plan.specs if spec.object_id in by_id}


def _write_draft(root: Path, name: str, body: str, *, frontmatter_extra: str = "") -> Path:
    inbox = root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / f"{name}.md"
    path.write_text(
        "---\n"
        f"id: {name}\n"
        "status: draft\n"
        f"title: {name}\n"
        f"{frontmatter_extra}"
        "---\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return path


class OffloadPlanTests(unittest.TestCase):
    def test_kind_is_registered_and_grantable_since_v0436(self):
        kind = ExactHumanApprovalOperation.object_storage_bytes_offload
        self.assertNotIn(kind, ALWAYS_DIALOG_OPERATIONS)  # v0.4.36 (letter 168 ⑥): grantable
        self.assertEqual(windows._OPERATION_LABELS[kind], "오브제 로컬 바이트 비우기")
        self.assertTrue(windows._OPERATION_QUESTIONS[kind].endswith("까요?"))
        self.assertIn("삭제하지 않습니다", windows._OPERATION_SUMMARIES[kind])
        self.assertIn("offloaded", windows._OPERATION_SUMMARIES[kind])

    def test_plan_applies_every_retention_predicate_and_counts_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            eligible = b"eligible old object bytes"
            young = b"captured yesterday"
            small = b"tiny"
            referenced = b"referenced by a draft"
            fidelity = b"fidelity source of a draft"
            absent = b"no local bytes"
            conflict = b"local bytes differ"
            declared = b"declared only"
            already = b"already offloaded"
            snapshot = b"zet revision before-snapshot"
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            rows = [
                _aged_row(eligible),
                _aged_row(snapshot, source="canonical_zet_before_revision"),
                _aged_row(young, captured_at=now),
                _aged_row(small),
                _aged_row(referenced),
                _aged_row(fidelity),
                {**_aged_row(absent), "locations": [restore_tests._remote(absent)]},
                _aged_row(conflict),
                restore_tests._row(declared, locations=[restore_tests._local(declared), {"provider": "object_storage", "availability": "declared_uploaded", "store_ref": STORE}]),
                restore_tests._row(already, locations=[_offloaded(already), restore_tests._remote(already)]),
            ]
            restore_tests._write_rows(root, rows)
            for raw in (eligible, young, small, referenced, fidelity, declared, snapshot):
                restore_tests._write_local(root, raw)
            restore_tests._write_local(root, conflict).write_bytes(b"NOT the manifest bytes")
            referenced_id = "sha256:" + hashlib.sha256(referenced).hexdigest()
            _write_draft(root, "draft-refs", f"See objet:{referenced_id} for the original.")
            fidelity_id = "sha256:" + hashlib.sha256(fidelity).hexdigest()
            plan_sha = "5" * 64
            receipts = root / archive_services.SOURCE_FIDELITY_DRAFT_RECEIPTS_DIR
            receipts.mkdir(parents=True, exist_ok=True)
            (receipts / f"{plan_sha}.json").write_text(
                json.dumps({"source_fidelity": {"source": {"object_id": fidelity_id}}}), encoding="utf-8"
            )
            _write_draft(root, "draft-fidelity", "Body without a token.", frontmatter_extra=f"source_fidelity:\n  creation_plan_sha256: {plan_sha}\n")

            plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, min_age_days=7, min_size_bytes=10)
            document = plan.public_document()
            if os.name == "nt":
                self.assertTrue(document["ok"], document)
                self.assertTrue(document["platform_supported"])
            else:
                self.assertFalse(document["ok"])
                self.assertEqual(document["reason_codes"], ["object_storage_offload_platform_unsupported"])
                self.assertFalse(document["platform_supported"])
            self.assertEqual(document["offload_target_count"], 1)
            self.assertEqual([spec.object_id for spec in plan.specs], ["sha256:" + hashlib.sha256(eligible).hexdigest()])
            self.assertEqual(document["below_min_age_count"], 1)
            self.assertEqual(document["below_min_size_count"], 1)
            self.assertEqual(document["referenced_by_unminted_draft_count"], 1)
            self.assertEqual(document["fidelity_source_of_unminted_draft_count"], 1)
            self.assertEqual(document["local_bytes_absent_count"], 1)
            self.assertEqual(document["local_bytes_conflict_count"], 1)
            self.assertEqual(document["remote_evidence_missing_count"], 1)
            self.assertEqual(document["already_offloaded_count"], 1)
            self.assertEqual(document["provenance_source_excluded_count"], 1)
            self.assertEqual(document["unminted_draft_count"], 2)
            self.assertEqual(document["planned_local_bytes_freed"], len(eligible))
            self.assertFalse(document["provider_api_called"])
            self.assertFalse(document["remote_delete_supported"])
            self.assertFalse(document["manifest_location_removed"])
            rendered = json.dumps(document)
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("draft-refs", rendered)
            for spec in plan.specs:
                self.assertNotIn(spec.remote_key, rendered)
                self.assertNotIn(spec.object_id, rendered)
            # --only bypasses the age/size filters but never the safety predicates
            only_small = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, only=hashlib.sha256(small).hexdigest(), min_size_bytes=10)
            self.assertEqual(len(only_small.specs), 1)
            only_referenced = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, only=referenced_id)
            self.assertEqual(len(only_referenced.specs), 0)
            self.assertFalse(only_referenced.public_document()["ok"])
            # a preservation receipt alone lets bytes be restored, never offloaded
            preserved = b"preserved receipt only, no manifest location"
            restore_tests._write_rows(root, rows + [{**_aged_row(preserved), "locations": [restore_tests._local(preserved)]}])
            restore_tests._write_local(root, preserved)
            receipt_dir = root / restore_tests.preservation.RECEIPT_ROOT
            receipt_dir.mkdir(parents=True, exist_ok=True)
            preserved_digest = hashlib.sha256(preserved).hexdigest()
            (receipt_dir / f"{preserved_digest}.0123456789abcdef.json").write_text(json.dumps({
                "schema_version": restore_tests.preservation.RECEIPT_SCHEMA,
                "object_id": "sha256:" + preserved_digest,
                "provider_kind": PROVIDER,
                "store_ref": STORE,
                "remote_key_strategy": "wom_bytes_preserved_v1",
                "preservation_status": "bytes_preserved",
            }), encoding="utf-8")
            only_preserved = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, only=preserved_digest)
            self.assertEqual(len(only_preserved.specs), 0)
            self.assertEqual(only_preserved.public_document()["bytes_preserved_receipt_only_count"], 1)
            self.assertTrue(restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE, only=preserved_digest, mode=restore.MODE_VERIFY_ONLY).specs)
            with self.assertRaises(offload.ObjectStorageOffloadError):
                offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, min_age_days=0, min_size_bytes=0, max_objects=1)

    def test_unreadable_fidelity_receipt_blocks_the_whole_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            raw = b"eligible but a draft receipt is unreadable"
            restore_tests._write_rows(root, [_aged_row(raw)])
            restore_tests._write_local(root, raw)
            _write_draft(root, "draft-broken", "Body.", frontmatter_extra="source_fidelity:\n  creation_plan_sha256: sha256:" + "7" * 64 + "\n")
            plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, min_age_days=0)
            document = plan.public_document()
            self.assertFalse(document["ok"])
            self.assertEqual(document["state"], "blocked")
            # POSIX runners also carry the platform gate; the retention blocker
            # must be present and be the only other reason.
            self.assertEqual(
                [code for code in document["reason_codes"] if code != "object_storage_offload_platform_unsupported"],
                ["object_storage_offload_retention_evidence_unreadable"],
            )
            self.assertEqual(document["unreadable_fidelity_receipt_count"], 1)
            self.assertIsNone(plan.manifest)


@unittest.skipUnless(os.name == "nt", "the handle-bound compare-and-delete is Windows-only by design")
class OffloadExecutionTests(unittest.TestCase):
    def test_offload_removes_verified_bytes_and_keeps_a_tombstone_the_readers_understand(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fake_archive(Path(tmp))
            first = b"first object to offload " * 2
            second = b"second object to offload"
            _append_rows(root, [_aged_row(first), _aged_row(second)])
            for raw in (first, second):
                restore_tests._write_local(root, raw)
            # setup evidence for the fake archive store
            plan = None
            with patch.object(restore, "_require_setup_evidence", lambda *a, **k: None):
                plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, min_age_days=0)
                self.assertEqual(len(plan.specs), 2)
                self.assertEqual(len(plan.manifest.items), 3)
                transport = _ProofTransport(_objects_for(plan, {"a": first, "b": second}))
                result = _run_offload(plan, transport)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["state"], "offload_completed")
            self.assertEqual(result["status_counts"]["bytes_offloaded"], 2)
            self.assertEqual(result["local_bytes_freed"], len(first) + len(second))
            self.assertEqual(result["manifest_location_updates"], 2)
            self.assertEqual(transport.head_calls, 2)
            self.assertEqual(transport.delete_calls, 0)
            self.assertEqual(transport.put_calls, 0)
            self.assertFalse(result["remote_delete_performed"])
            for raw in (first, second):
                self.assertFalse(restore_tests._dest(root, raw).exists())
                self.assertTrue(restore_tests._dest(root, raw).parent.is_dir())  # the shard directory stays
            rows_after = restore_tests._rows_after(root)
            for raw in (first, second):
                row = rows_after["sha256:" + hashlib.sha256(raw).hexdigest()]
                local = [loc for loc in row["locations"] if loc.get("provider") == "local"]
                self.assertEqual(len(local), 1, row)
                self.assertEqual(local[0]["availability"], "offloaded")
                self.assertTrue(local[0]["offload_receipt_ref"].startswith(offload.RECEIPT_ROOT + "/"))
                self.assertTrue(local[0]["offloaded_at"])
            for spec in plan.specs:
                receipt = json.loads((root / spec.receipt_relative).read_text(encoding="utf-8"))
                self.assertEqual(receipt["schema_version"], offload.RECEIPT_SCHEMA)
                self.assertEqual(receipt["offload_status"], "bytes_offloaded")
                self.assertTrue(receipt["remote_verification"]["same_run"])
                self.assertTrue(receipt["local_bytes_removed"])
                self.assertFalse(receipt["remote_delete_performed"])
                self.assertEqual(receipt["restore_command"], "object-storage-restore")
                self.assertNotIn("remote_key", receipt)
                self.assertNotIn(str(root), json.dumps(receipt))
            self.assertFalse(any((root / offload.MARKER_ROOT).rglob("*.proof.json")))
            with patch.object(restore, "_require_setup_evidence", lambda *a, **k: None):
                self.assertTrue(offload.verify_object_storage_offload(plan)["ok"])
            # the readers: Doctor --strict, resolver, backup-evidence, staged cleanup
            code, diagnostics = _doctor(root, "--strict")
            self.assertEqual(code, 0, [d for d in diagnostics if d.get("severity") != "INFO"])
            self.assertEqual(sum(1 for d in diagnostics if d.get("code") == "local_object_offloaded"), 2)
            resolved = archive_services.resolve_objet_ref(root, object_id="sha256:" + hashlib.sha256(first).hexdigest())
            self.assertEqual(resolved["resolution_state"], "remote_verified_local_absent")
            self.assertEqual(resolved["restore_workflow"], "object-storage-restore")
            lane = archive_services.backup_evidence_status(root)["lanes"]["object_storage"]
            self.assertEqual(lane["offloaded_local_location_object_count"], 2)
            # and the way back: v0.4.28 restore reactivates the rows
            with patch.object(restore, "_require_setup_evidence", lambda *a, **k: None):
                back = restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE)
                self.assertEqual(back.public_document()["local_location_reactivate_count"], 2)
                restored = restore_tests._run(back, restore_tests._MemoryTransport({spec.remote_key: raw for spec, raw in zip(back.specs, sorted([first, second], key=lambda b: "sha256:" + hashlib.sha256(b).hexdigest()))}))
            self.assertTrue(restored["ok"], restored)
            for raw in (first, second):
                self.assertEqual(restore_tests._dest(root, raw).read_bytes(), raw)
            rows_after = restore_tests._rows_after(root)
            for raw in (first, second):
                row = rows_after["sha256:" + hashlib.sha256(raw).hexdigest()]
                local = [loc for loc in row["locations"] if loc.get("provider") == "local"]
                self.assertEqual(local[0]["availability"], "available")
                self.assertNotIn("offload_receipt_ref", local[0])
            code, diagnostics = _doctor(root, "--strict")
            self.assertEqual(code, 0, [d for d in diagnostics if d.get("severity") != "INFO"])

    def test_remote_mismatch_or_absence_keeps_local_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            corrupt = b"remote copy is corrupt"
            absent = b"remote copy is absent"
            good = b"remote copy is good"
            restore_tests._write_rows(root, [_aged_row(corrupt), _aged_row(absent), _aged_row(good)])
            for raw in (corrupt, absent, good):
                restore_tests._write_local(root, raw)
            plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, min_age_days=0)
            by_id = {spec.object_id: spec for spec in plan.specs}
            objects = {
                by_id["sha256:" + hashlib.sha256(corrupt).hexdigest()].remote_key: b"REMOTE copy is corrupt",
                by_id["sha256:" + hashlib.sha256(good).hexdigest()].remote_key: good,
            }
            transport = _ProofTransport(objects)
            result = _run_offload(plan, transport)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status_counts"]["bytes_offloaded"], 1)
            self.assertEqual(result["status_counts"]["review_required"], 2)
            self.assertEqual(result["local_bytes_freed"], len(good))
            self.assertEqual(restore_tests._dest(root, corrupt).read_bytes(), corrupt)
            self.assertEqual(restore_tests._dest(root, absent).read_bytes(), absent)
            self.assertFalse(restore_tests._dest(root, good).exists())
            rows_after = restore_tests._rows_after(root)
            for raw in (corrupt, absent):
                row = rows_after["sha256:" + hashlib.sha256(raw).hexdigest()]
                self.assertTrue(any(loc.get("availability") == "available" for loc in row["locations"]), row)
            reasons = {spec.object_id: json.loads((root / spec.receipt_relative).read_text(encoding="utf-8"))["review_reason"] for spec in plan.specs}
            self.assertEqual(reasons["sha256:" + hashlib.sha256(corrupt).hexdigest()], "remote_checksum_mismatch")
            self.assertEqual(reasons["sha256:" + hashlib.sha256(absent).hexdigest()], "remote_absent")
            self.assertEqual(transport.delete_calls, 0)
            self.assertTrue(offload.verify_object_storage_offload(plan)["ok"])

    def test_crash_after_unlink_before_receipt_recovers_from_the_proof_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            raw = b"unlinked then crashed"
            restore_tests._write_rows(root, [_aged_row(raw)])
            restore_tests._write_local(root, raw)
            plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, min_age_days=0)
            transport = _ProofTransport(_objects_for(plan, {"a": raw}))
            with patch.object(offload, "_create_receipt", side_effect=RuntimeError("crash after unlink")):
                with self.assertRaises(ExactOperationManifestError):
                    _run_offload(plan, transport)
            self.assertFalse(restore_tests._dest(root, raw).exists())
            self.assertTrue(any((root / offload.MARKER_ROOT).rglob("*.proof.json")))
            self.assertFalse((root / plan.specs[0].receipt_relative).exists())
            resumed = _run_offload(offload.load_object_storage_offload_plan(root, manifest_sha256=plan.manifest.manifest_sha256), transport, resume=True)
            self.assertTrue(resumed["ok"], resumed)
            self.assertEqual(transport.head_calls, 1)  # no second download
            receipt = json.loads((root / plan.specs[0].receipt_relative).read_text(encoding="utf-8"))
            self.assertEqual(receipt["offload_status"], "bytes_offloaded")
            self.assertFalse(any((root / offload.MARKER_ROOT).rglob("*.proof.json")))
            rows_after = restore_tests._rows_after(root)
            row = rows_after[plan.specs[0].object_id]
            self.assertTrue(any(loc.get("availability") == "offloaded" for loc in row["locations"]))

    def test_a_marker_of_another_execution_never_authorises_a_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            raw = b"proved under an abandoned approval"
            restore_tests._write_rows(root, [_aged_row(raw)])
            restore_tests._write_local(root, raw)
            plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, min_age_days=0)
            spec = plan.specs[0]
            foreign_execution = "sha256:" + "e" * 64
            identity = offload._file_identity(restore_tests._dest(root, raw))
            with exact_operation_writer_lock(root):
                offload._persist_control(plan)
                offload._write_marker(plan, spec, identity=identity, execution_sha256=foreign_execution)
            transport = _ProofTransport(_objects_for(plan, {"a": raw}))
            result = _run_offload(plan, transport)
            self.assertTrue(result["ok"], result)
            self.assertEqual(transport.head_calls, 1)  # a fresh proof: the foreign marker was not honoured
            self.assertFalse(restore_tests._dest(root, raw).exists())
            # the foreign marker is still there (never a proof, never touched); ours is gone
            markers = list((root / offload.MARKER_ROOT).rglob("*.proof.json"))
            self.assertEqual(len(markers), 1)
            self.assertIn(foreign_execution.removeprefix("sha256:")[:16], str(markers[0]))

    def test_torn_marker_with_bytes_present_is_discarded_and_proven_afresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            raw = b"torn marker survivor"
            restore_tests._write_rows(root, [_aged_row(raw)])
            restore_tests._write_local(root, raw)
            plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, min_age_days=0)
            transport = _ProofTransport(_objects_for(plan, {"a": raw}))
            with exact_operation_writer_lock(root) as lock:
                offload._persist_control(plan)
                checkpoints = FileExactOperationCheckpointStore(root, writer_lock=lock)
                authority = restore_tests._authority()
                from wom_kit.exact_operation_manifest import exact_operation_execution_sha256
                execution = exact_operation_execution_sha256(plan.manifest, approval_authority=authority)
                torn = root / offload._marker_relative(plan, plan.specs[0], execution_sha256=execution)
                torn.parent.mkdir(parents=True, exist_ok=True)
                torn.write_bytes(b'{"schema_version": "wom-kit/object-storage-offload-proof-marker/v0.1", "obj')
                result = offload._apply_with_store(plan, authority, transport, checkpoints, resume=False, progress_hook=None)
            self.assertTrue(result["ok"], result)
            self.assertEqual(transport.head_calls, 1)
            self.assertFalse(restore_tests._dest(root, raw).exists())
            self.assertFalse(torn.exists())

    def test_bytes_that_reappear_before_the_projection_keep_the_row_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            raw = b"re-materialised by a capture"
            restore_tests._write_rows(root, [_aged_row(raw)])
            restore_tests._write_local(root, raw)
            plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, min_age_days=0)
            transport = _ProofTransport(_objects_for(plan, {"a": raw}))
            real_apply = offload._apply_manifest_batch

            def reappear_then_apply(plan_, *, lifecycle):
                restore_tests._write_local(root, raw)
                return real_apply(plan_, lifecycle=lifecycle)

            with patch.object(offload, "_apply_manifest_batch", reappear_then_apply):
                result = _run_offload(plan, transport)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status_counts"]["bytes_offloaded"], 1)
            self.assertEqual(result["local_bytes_reappeared_count"], 1)
            self.assertEqual(result["manifest_location_updates"], 0)
            row = restore_tests._rows_after(root)[plan.specs[0].object_id]
            self.assertTrue(any(loc.get("availability") == "available" for loc in row["locations"]))
            self.assertTrue(offload.verify_object_storage_offload(plan)["ok"])

    def test_local_bytes_gone_without_a_proof_marker_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            raw = b"someone deleted the file by hand"
            restore_tests._write_rows(root, [_aged_row(raw)])
            restore_tests._write_local(root, raw)
            plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, min_age_days=0)
            restore_tests._dest(root, raw).unlink()
            transport = _ProofTransport(_objects_for(plan, {"a": raw}))
            with self.assertRaises(ExactOperationManifestError):
                _run_offload(plan, transport)
            self.assertEqual(transport.head_calls, 0)
            self.assertFalse((root / plan.specs[0].receipt_relative).exists())
            rows_after = restore_tests._rows_after(root)
            self.assertTrue(any(loc.get("availability") == "available" for loc in rows_after[plan.specs[0].object_id]["locations"]))

    def test_transport_trouble_is_resumable_and_a_new_draft_reference_stops_the_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = restore_tests._build_root(Path(tmp))
            first = b"first is offloaded"
            second = b"second stalls"
            restore_tests._write_rows(root, [_aged_row(first), _aged_row(second)])
            for raw in (first, second):
                restore_tests._write_local(root, raw)
            plan = offload.plan_object_storage_offload(root, provider_kind=PROVIDER, store_ref=STORE, min_age_days=0)
            order = sorted([first, second], key=lambda b: "sha256:" + hashlib.sha256(b).hexdigest())

            class _StallSecond(_ProofTransport):
                def head_object(self, *, key, presence_only=False):
                    if key == plan.specs[1].remote_key and self.head_calls == 1:
                        self.head_calls += 1
                        return {"present": False, "size": None, "checksum_sha256": None, "presence_state": "unavailable", "verification_state": "unavailable"}
                    return super().head_object(key=key, presence_only=presence_only)

            transport = _StallSecond(_objects_for(plan, {"a": first, "b": second}))
            with self.assertRaises(ExactOperationManifestError):
                _run_offload(plan, transport)
            self.assertFalse(restore_tests._dest(root, order[0]).exists())
            self.assertEqual(restore_tests._dest(root, order[1]).read_bytes(), order[1])
            # a draft now references the second object: the resume refuses to remove it
            _write_draft(root, "late-draft", f"objet:{plan.specs[1].object_id} is needed")
            archive_services.index_archive(root)
            loaded = offload.load_object_storage_offload_plan(root, manifest_sha256=plan.manifest.manifest_sha256)
            with self.assertRaises(offload.ObjectStorageOffloadError) as ctx:
                offload._fresh_revalidated(loaded)  # the resume path re-checks retention first
            self.assertEqual(ctx.exception.code, "object_storage_offload_plan_changed")
            self.assertEqual(restore_tests._dest(root, order[1]).read_bytes(), order[1])
            # without that draft the resume completes with one more GET and no re-download of the first
            (root / "inbox" / "late-draft.md").unlink()
            archive_services.index_archive(root)
            loaded = offload._fresh_revalidated(offload.load_object_storage_offload_plan(root, manifest_sha256=plan.manifest.manifest_sha256))
            resumed = _run_offload(loaded, transport, resume=True)
            self.assertTrue(resumed["ok"], resumed)
            self.assertEqual(transport.head_calls, 3)
            self.assertFalse(restore_tests._dest(root, order[1]).exists())
            self.assertEqual(resumed["manifest_location_updates"], 2)


@unittest.skipUnless(os.name == "nt", "the handle-bound compare-and-delete is Windows-only by design")
class OffloadCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-v0429-offload-")
        self.addCleanup(temporary.cleanup)
        self.root = restore_tests._build_root(Path(temporary.name))
        self.raw = b"cli offloaded object bytes"
        restore_tests._write_rows(self.root, [_aged_row(self.raw)])
        restore_tests._write_local(self.root, self.raw)
        self.native = restore_tests._Native()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=restore_tests._KeyProvider()))
        stack.enter_context(patch.dict(os.environ, {"WOM_TEST_OFFLOAD_AK": "AKIAEXAMPLE", "WOM_TEST_OFFLOAD_SK": "s" * 40}))
        self.outputs: list[str] = []

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        self.outputs.extend((out.getvalue(), err.getvalue()))
        return code, json.loads(out.getvalue())

    def base_args(self) -> list[str]:
        return [
            "object-storage-offload", str(self.root),
            "--provider-kind", PROVIDER, "--store-ref", STORE, "--min-age-days", "0",
            "--endpoint-host", "acct.r2.cloudflarestorage.com", "--bucket", "private-bucket",
            "--access-key-id-ref", "env:WOM_TEST_OFFLOAD_AK", "--secret-access-key-ref", "env:WOM_TEST_OFFLOAD_SK",
        ]

    def test_dry_run_then_approve_offloads_through_the_live_transport_seam(self):
        code, preview = self.run_cli(*self.base_args(), "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["state"], "ready_for_exact_human_approval")
        self.assertEqual(preview["offload_target_count"], 1)
        self.assertEqual(self.native.calls, 0)
        send, calls = restore_tests._sink_sender(self.raw)
        with patch.object(archive_services, "_default_urllib_sender", return_value=send):
            code, result = self.run_cli(
                *self.base_args(), "--approve", "--reviewed-by", REVIEWER,
                "--expected-manifest-sha256", preview["plan_sha256"],
            )
        self.assertEqual(code, 0, result)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.native.calls, 1)
        context = self.native.contexts[0]
        self.assertIn("비우기", str(context.get("main_instruction")) + str(context.get("approve_button_text")))
        self.assertEqual(result["status_counts"]["bytes_offloaded"], 1)
        self.assertEqual(result["local_bytes_freed"], len(self.raw))
        methods = [c["method"] for c in calls]
        self.assertEqual(methods, ["HEAD", "GET"])  # one proof: HEAD then the full GET re-hash
        self.assertFalse(restore_tests._dest(self.root, self.raw).exists())
        rendered = "".join(self.outputs) + json.dumps(self.native.contexts, ensure_ascii=False)
        self.assertNotIn("s" * 40, rendered)
        self.assertNotIn(str(self.root), rendered)
        self.assertNotIn(REVIEWER, "".join(self.outputs))

    def test_cancelled_dialog_removes_nothing(self):
        code, preview = self.run_cli(*self.base_args(), "--dry-run")
        self.native.approve = False
        send, calls = restore_tests._sink_sender(self.raw)
        with patch.object(archive_services, "_default_urllib_sender", return_value=send):
            code, result = self.run_cli(
                *self.base_args(), "--approve", "--reviewed-by", REVIEWER,
                "--expected-manifest-sha256", preview["plan_sha256"],
            )
        self.assertEqual(code, 1, result)
        self.assertEqual(calls, [])
        self.assertEqual(restore_tests._dest(self.root, self.raw).read_bytes(), self.raw)

    def test_usage_refusals_carry_fixed_codes(self):
        code, result = self.run_cli(*self.base_args())
        self.assertEqual(result["reason_codes"][0], "object_storage_offload_plan_invalid")
        code, result = self.run_cli(*self.base_args(), "--approve")
        self.assertEqual(result["reason_codes"][0], "object_storage_offload_approval_required")
        code, result = self.run_cli(*self.base_args(), "--approve", "--reviewed-by", REVIEWER, "--expected-manifest-sha256", "sha256:" + "0" * 64)
        self.assertEqual(result["reason_codes"][0], "object_storage_offload_plan_changed")
        self.assertEqual(self.native.calls, 0)
        self.assertEqual(restore_tests._dest(self.root, self.raw).read_bytes(), self.raw)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
