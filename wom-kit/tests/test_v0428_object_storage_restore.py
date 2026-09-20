"""v0.4.28: object-storage restore (OB-01 general remote proof + OB-03 rehydrate).

Transport level: the restore GET primitive streams the body into a create-only
sink, keeps it only when size and sha256 reproduce the manifest identity, and
never overwrites an earlier sink. Command level tests live below the transport
tests and use an in-memory transport plus the fake dialog.
"""
from __future__ import annotations

import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wom_kit import archive_services


_CREDENTIAL = {
    "endpoint_host": "acct.r2.cloudflarestorage.com",
    "bucket": "private-bucket",
    "access_key_id": "AKIAEXAMPLE",
    "secret_access_key": "s" * 40,
    "region": "auto",
}


def _live_transport(send):
    transport = archive_services._object_storage_resolve_transport(
        "cloudflare-r2", send=send, credential=_CREDENTIAL
    )
    assert transport is not None
    return transport


def _sink_sender(body: bytes, *, status: int = 200, content_length: int | None = None):
    """A fake injected sender honouring the two restore-only sink keywords."""

    calls: list[dict] = []

    def send(*, method, url, headers, data_path=None, data_bytes=None, sink_path=None, sink_max_bytes=None):
        calls.append(
            {
                "method": method,
                "url": url,
                "authorization": headers.get("authorization"),
                "sink_path": None if sink_path is None else Path(sink_path),
                "sink_max_bytes": sink_max_bytes,
            }
        )
        if status != 200:
            return {"status": status, "headers": {}, "body": b"<Error><Code>NoSuchKey</Code></Error>"}
        if sink_path is None:
            return {
                "status": 200,
                "headers": {"content-length": str(len(body))},
                "body": b"",
                "body_sha256": hashlib.sha256(body).hexdigest(),
                "body_size": len(body),
                "body_complete": True,
                "body_length_known": True,
                "body_truncated": False,
                "transport_error": False,
            }
        length = len(body) if content_length is None else content_length
        limit = int(sink_max_bytes) if isinstance(sink_max_bytes, int) else None
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        try:
            fd = os.open(sink_path, flags, 0o600)
        except OSError:
            return {"status": 200, "headers": {}, "body": b"", "body_complete": False, "sink_written": False, "transport_error": True}
        with os.fdopen(fd, "wb") as out:
            if limit is not None and len(body) > limit:
                out.write(body[: limit + 1])
                return {"status": 200, "headers": {}, "body": b"", "body_complete": False, "sink_written": False, "transport_error": True}
            out.write(body)
        complete = len(body) == length
        return {
            "status": 200,
            "headers": {"content-length": str(length)},
            "body": b"",
            "body_sha256": hashlib.sha256(body).hexdigest() if complete else None,
            "body_size": len(body),
            "body_complete": complete,
            "body_length_known": True,
            "body_truncated": False,
            "sink_written": complete,
            "transport_error": not complete,
        }

    return send, calls


class RestoreTransportPrimitiveTests(unittest.TestCase):
    def test_protocol_and_null_transport_expose_get_object(self):
        self.assertTrue(hasattr(archive_services.ObjectStorageTransport, "get_object"))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(archive_services.ObjectStorageTransportNotImplemented):
                archive_services.NullTransport().get_object(
                    key="sha256/aa/" + "a" * 64,
                    sink_path=Path(tmp) / "sink",
                    expected_size=1,
                    expected_sha256="a" * 64,
                )

    def test_matching_body_keeps_the_sink_and_signs_a_get(self):
        body = b"objet original bytes"
        digest = hashlib.sha256(body).hexdigest()
        send, calls = _sink_sender(body)
        transport = _live_transport(send)
        with tempfile.TemporaryDirectory() as tmp:
            sink = Path(tmp) / "restore.part"
            result = transport.get_object(
                key=f"sha256/{digest[:2]}/{digest}",
                sink_path=sink,
                expected_size=len(body),
                expected_sha256=digest,
            )
            self.assertEqual(result["status_class"], "ok")
            self.assertTrue(result["sink_written"])
            self.assertTrue(result["size_match"])
            self.assertTrue(result["checksum_match"])
            self.assertEqual(result["size"], len(body))
            self.assertEqual(sink.read_bytes(), body)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["method"], "GET")
        self.assertEqual(calls[0]["sink_path"], sink)
        self.assertEqual(calls[0]["sink_max_bytes"], len(body))
        self.assertIn("AWS4-HMAC-SHA256", calls[0]["authorization"])
        self.assertNotIn("s" * 40, calls[0]["authorization"])
        self.assertNotIn("url", result)
        self.assertNotIn("body", result)

    def test_checksum_mismatch_discards_the_sink(self):
        body = b"remote bytes differ"
        send, _calls = _sink_sender(body)
        transport = _live_transport(send)
        with tempfile.TemporaryDirectory() as tmp:
            sink = Path(tmp) / "restore.part"
            result = transport.get_object(
                key="sha256/aa/" + "a" * 64,
                sink_path=sink,
                expected_size=len(body),
                expected_sha256="a" * 64,
            )
            self.assertEqual(result["status_class"], "ok")
            self.assertTrue(result["size_match"])
            self.assertFalse(result["checksum_match"])
            self.assertFalse(result["sink_written"])
            self.assertFalse(sink.exists())

    def test_size_mismatch_discards_the_sink(self):
        body = b"short"
        digest = hashlib.sha256(body).hexdigest()
        send, _calls = _sink_sender(body)
        transport = _live_transport(send)
        with tempfile.TemporaryDirectory() as tmp:
            sink = Path(tmp) / "restore.part"
            result = transport.get_object(
                key="sha256/aa/" + digest,
                sink_path=sink,
                expected_size=len(body) + 7,
                expected_sha256=digest,
            )
            self.assertEqual(result["status_class"], "ok")
            self.assertFalse(result["size_match"])
            self.assertFalse(result["sink_written"])
            self.assertFalse(sink.exists())

    def test_absent_and_transport_error_leave_no_sink(self):
        send, _calls = _sink_sender(b"", status=404)
        transport = _live_transport(send)
        with tempfile.TemporaryDirectory() as tmp:
            sink = Path(tmp) / "restore.part"
            result = transport.get_object(
                key="sha256/aa/" + "a" * 64, sink_path=sink, expected_size=0, expected_sha256="a" * 64
            )
            self.assertEqual(result["status_class"], "absent")
            self.assertFalse(sink.exists())
            incomplete, _ = _sink_sender(b"abc", content_length=9)
            result = _live_transport(incomplete).get_object(
                key="sha256/aa/" + "a" * 64, sink_path=sink, expected_size=9, expected_sha256="a" * 64
            )
            self.assertEqual(result["status_class"], "rate_limited")
            self.assertFalse(result["sink_written"])
            self.assertFalse(sink.exists())

    def test_invalid_expectations_never_call_the_provider(self):
        send, calls = _sink_sender(b"x")
        transport = _live_transport(send)
        with tempfile.TemporaryDirectory() as tmp:
            result = transport.get_object(
                key="sha256/aa/" + "a" * 64,
                sink_path=Path(tmp) / "sink",
                expected_size=-1,
                expected_sha256="a" * 64,
            )
            self.assertEqual(result["status_class"], "failed")
            result = transport.get_object(
                key="sha256/aa/" + "a" * 64,
                sink_path=Path(tmp) / "sink",
                expected_size=1,
                expected_sha256="not-a-digest",
            )
            self.assertEqual(result["status_class"], "failed")
        self.assertEqual(calls, [])

    def test_default_sender_streams_into_a_create_only_sink(self):
        body = b"z" * (archive_services.OBJECT_STORAGE_HTTP_STREAM_CHUNK_BYTES + 17)
        digest = hashlib.sha256(body).hexdigest()

        class _Headers:
            def items(self):
                return [("Content-Length", str(len(body))), ("ETag", '"opaque"')]

        class _Response:
            status = 200
            headers = _Headers()

            def __init__(self):
                self._buffer = io.BytesIO(body)

            def read(self, size):
                return self._buffer.read(size)

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

        class _Opener:
            def open(self, request, timeout=None):
                self.request = request
                self.timeout = timeout
                return _Response()

        opener = _Opener()
        with mock.patch("urllib.request.build_opener", return_value=opener):
            send = archive_services._default_urllib_sender()
        with tempfile.TemporaryDirectory() as tmp:
            sink = Path(tmp) / "restore.part"
            evidence = send(
                method="GET",
                url="https://acct.r2.cloudflarestorage.com/private-bucket/sha256/aa/" + digest,
                headers={"host": "acct.r2.cloudflarestorage.com"},
                sink_path=sink,
                sink_max_bytes=len(body),
            )
            self.assertTrue(evidence["body_complete"])
            self.assertTrue(evidence["sink_written"])
            self.assertEqual(opener.timeout, archive_services.OBJECT_STORAGE_HTTP_IDLE_TIMEOUT_SECONDS)
            self.assertEqual(evidence["body_sha256"], digest)
            self.assertEqual(evidence["body_size"], len(body))
            self.assertEqual(evidence["body"], b"")
            self.assertEqual(sink.read_bytes(), body)
            # A stale sink is never appended to or overwritten (O_EXCL).
            stale = send(
                method="GET",
                url="https://acct.r2.cloudflarestorage.com/private-bucket/sha256/aa/" + digest,
                headers={"host": "acct.r2.cloudflarestorage.com"},
                sink_path=sink,
                sink_max_bytes=len(body),
            )
            self.assertTrue(stale["transport_error"])
            self.assertFalse(stale["sink_written"])
            self.assertEqual(sink.read_bytes(), body)
            # The sink ceiling stops a body longer than the manifest size.
            capped = send(
                method="GET",
                url="https://acct.r2.cloudflarestorage.com/private-bucket/sha256/aa/" + digest,
                headers={"host": "acct.r2.cloudflarestorage.com"},
                sink_path=Path(tmp) / "capped.part",
                sink_max_bytes=len(body) - 1,
            )
            self.assertTrue(capped["transport_error"])
            self.assertFalse(capped["sink_written"])
            # The verification GET without a sink keeps its original evidence shape.
            plain = send(
                method="GET",
                url="https://acct.r2.cloudflarestorage.com/private-bucket/sha256/aa/" + digest,
                headers={"host": "acct.r2.cloudflarestorage.com"},
            )
            self.assertTrue(plain["body_complete"])
            self.assertNotIn("sink_written", plain)
            self.assertEqual(plain["body_sha256"], digest)


import json
import shutil
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from unittest.mock import patch

from wom_kit import archive_cli
from wom_kit import exact_human_approval_windows as windows
from wom_kit import exact_human_approval_workflow as broker
from wom_kit import object_storage_preservation as preservation
from wom_kit import object_storage_restore as restore
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID, IDCANCEL, ExactHumanApprovalOperation
from wom_kit.exact_operation_manifest import (
    ExactOperationApprovalAuthority,
    ExactOperationManifestError,
    FileExactOperationCheckpointStore,
    exact_operation_writer_lock,
)
from wom_kit.work_session_permission import ALWAYS_DIALOG_OPERATIONS

STORE = "storage:account:test"
PROVIDER = "cloudflare-r2"
REVIEWER = "person:synthetic-restore-reviewer"


class _MemoryTransport:
    """Provider double for restore: objects by key; counts every call kind."""

    def __init__(self, objects: dict[str, bytes], *, unavailable_first: int = 0) -> None:
        self.objects = dict(objects)
        self.get_calls = 0
        self.head_calls = 0
        self.put_calls = 0
        self.delete_calls = 0
        self.unavailable_first = unavailable_first

    def head_object(self, **_kwargs):
        self.head_calls += 1
        raise AssertionError("restore never HEADs; the GET is the proof")

    def put_object(self, **_kwargs):
        self.put_calls += 1
        raise AssertionError("restore never PUTs")

    def delete_object(self, **_kwargs):
        self.delete_calls += 1
        raise AssertionError("restore never deletes the remote object")

    def get_object(self, *, key, sink_path, expected_size, expected_sha256):
        self.get_calls += 1
        sink = Path(sink_path)
        if self.unavailable_first > 0:
            self.unavailable_first -= 1
            return {"status_class": "rate_limited", "size": None, "checksum_sha256": None,
                    "size_match": False, "checksum_match": False, "sink_written": False}
        if key not in self.objects:
            return {"status_class": "absent", "size": None, "checksum_sha256": None,
                    "size_match": False, "checksum_match": False, "sink_written": False}
        body = self.objects[key]
        digest = hashlib.sha256(body).hexdigest()
        size_match = len(body) == expected_size
        checksum_match = digest == expected_sha256
        written = size_match and checksum_match
        if written:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
            fd = os.open(sink, flags, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(body)
        return {"status_class": "ok", "size": len(body), "checksum_sha256": digest,
                "size_match": size_match, "checksum_match": checksum_match, "sink_written": written}


class _Native:
    def __init__(self) -> None:
        self.approve = True
        self.calls = 0
        self.contexts: list[dict] = []

    def show(self, **kwargs):
        self.calls += 1
        self.contexts.append(dict(kwargs))
        return (APPROVE_BUTTON_ID if self.approve else IDCANCEL), True


class _KeyProvider:
    def use_key(self, _root, consumer, *, create_if_missing=False):
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


def _authority() -> ExactOperationApprovalAuthority:
    return ExactOperationApprovalAuthority.from_reference(
        {
            "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
            "approval_id": "approval_" + "a" * 32,
            "context_sha256": "sha256:" + "b" * 64,
            "approval_authority_sha256": "sha256:" + "c" * 64,
            "one_use": True,
        }
    )


def _build_root(parent: Path) -> Path:
    root = parent / "archive"
    (root / "objects" / "manifests").mkdir(parents=True)
    (root / "archive.yml").write_text("archive_id: archive:test:object-storage-restore\n", encoding="utf-8")
    archive_id = archive_services.read_archive_id(root)
    common = dict(
        archive_id=archive_id,
        profile_id="profile:test:object-storage-restore",
        profile_slug="object-storage-restore",
        provider_kind=PROVIDER,
        storage_account_ref=STORE,
        bucket_name="zettel-kasten-object-storage-restore-objets",
        region="auto",
        endpoint_ref="provider:endpoint:cloudflare-r2",
        objet_prefix=f"archives/{archive_id}/objets/",
        visibility="private",
    )
    binding = archive_services.build_object_storage_provider_binding(**common)
    (root / "provider-bindings.yml").write_text(
        archive_services.dump_yaml({"version": "provider-bindings/v0.1", "archive_id": archive_id, "bindings": [binding]}),
        encoding="utf-8",
    )
    receipt_relative = archive_services.object_storage_provider_setup_receipt_path(common["bucket_name"])
    receipt = archive_services.build_object_storage_provider_setup_receipt(
        **common,
        receipt_path=receipt_relative,
        reviewed_by="person:test",
        timestamp="2026-08-25T00:00:00+09:00",
        dry_run=False,
        manual_steps=[],
    )
    receipt_path = root / receipt_relative
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    return root


def _row(raw: bytes, *, locations: list[dict]) -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "object_id": "sha256:" + digest,
        "sha256": digest,
        "logical_key": f"objects/sha256/{digest[:2]}/{digest}",
        "mime": "application/octet-stream",
        "size_bytes": len(raw),
        "locations": locations,
        "provenance": {"created_in": "archive:test:object-storage-restore", "source": "test-fixture", "captured_at": "2026-08-28T00:00:00Z"},
    }


def _remote(raw: bytes, *, key: str | None = None, verification: str = "content_hash") -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    return archive_services.object_storage_wom_uploaded_location(
        digest=digest,
        provider_kind=PROVIDER,
        store_ref=STORE,
        execution_receipt_ref="receipts/providers/object-storage-executions/synthetic.json",
        uploaded_at="2026-08-22T00:00:00Z",
        key_strategy="prefix" if key else "sha256_content_addressed",
        remote_key=key or f"sha256/{digest[:2]}/{digest}",
        remote_key_verification=verification,
        remote_size=len(raw),
    )


def _local(raw: bytes, *, availability: str = "available") -> dict:
    digest = hashlib.sha256(raw).hexdigest()
    return {"provider": "local", "path": f"objects/sha256/{digest[:2]}/{digest}", "availability": availability}


def _write_rows(root: Path, rows: list[dict]) -> None:
    (root / "objects" / "manifests" / "files.jsonl").write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8"
    )
    archive_services.index_archive(root)


def _write_local(root: Path, raw: bytes) -> Path:
    digest = hashlib.sha256(raw).hexdigest()
    path = root / "objects" / "sha256" / digest[:2] / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _dest(root: Path, raw: bytes) -> Path:
    digest = hashlib.sha256(raw).hexdigest()
    return root / "objects" / "sha256" / digest[:2] / digest


def _rows_after(root: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in (root / "objects/manifests/files.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["object_id"]: row for row in rows}


def _run(plan, transport, *, resume=False):
    with exact_operation_writer_lock(plan.archive_root) as lock:
        restore._persist_control(plan)
        checkpoints = FileExactOperationCheckpointStore(plan.archive_root, writer_lock=lock)
        return restore._apply_with_store(plan, _authority(), transport, checkpoints, resume=resume, progress_hook=None)


class RestorePlanTests(unittest.TestCase):
    def test_kind_is_registered_and_grantable_since_v0436(self):
        kind = ExactHumanApprovalOperation.object_storage_bytes_restore
        self.assertNotIn(kind, ALWAYS_DIALOG_OPERATIONS)  # v0.4.36 (letter 168 ⑥): grantable
        self.assertEqual(windows._OPERATION_LABELS[kind], "오브제 원격 바이트 되찾기")
        self.assertTrue(windows._OPERATION_QUESTIONS[kind].endswith("까요?"))
        self.assertIn("덮어쓰지 않고", windows._OPERATION_SUMMARIES[kind])
        self.assertIn("삭제하지 않습니다", windows._OPERATION_SUMMARIES[kind])

    def test_plan_selects_remote_verified_objects_without_local_bytes_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _build_root(Path(tmp))
            missing = b"missing local bytes"          # wom_uploaded, no local file, no local location
            gone = b"local location but file gone"     # local location says available, file deleted by hand
            present = b"present and matching"          # local present + matching -> already present
            conflict = b"conflicting local bytes"      # local file holds other bytes -> never overwritten
            declared = b"declared only"                # declared_uploaded is not a proof
            other_store = b"other store"               # wom_uploaded for a different store
            preserved = b"preserved receipt only"      # v0.4.13 preservation receipt, no manifest location
            offloaded = b"offloaded by v0.4.29"        # local location offloaded, remote verified
            rows = [
                _row(missing, locations=[_remote(missing)]),
                _row(gone, locations=[_local(gone), _remote(gone, key="custom/" + hashlib.sha256(gone).hexdigest(), verification="presence_size")]),
                _row(present, locations=[_local(present), _remote(present)]),
                _row(conflict, locations=[_local(conflict), _remote(conflict)]),
                _row(declared, locations=[{"provider": "object_storage", "availability": "declared_uploaded"}]),
                _row(other_store, locations=[{**_remote(other_store), "store_ref": "storage:account:other"}]),
                _row(preserved, locations=[]),
                _row(offloaded, locations=[_local(offloaded, availability="offloaded"), _remote(offloaded)]),
            ]
            _write_rows(root, rows)
            _write_local(root, present)
            _write_local(root, conflict).write_bytes(b"NOT the manifest bytes")
            # a preservation receipt for `preserved`
            preserved_digest = hashlib.sha256(preserved).hexdigest()
            receipt_dir = root / preservation.RECEIPT_ROOT
            receipt_dir.mkdir(parents=True)
            (receipt_dir / f"{preserved_digest}.0123456789abcdef.json").write_text(json.dumps({
                "schema_version": preservation.RECEIPT_SCHEMA,
                "object_id": "sha256:" + preserved_digest,
                "provider_kind": PROVIDER,
                "store_ref": STORE,
                "remote_key_strategy": "wom_bytes_preserved_v1",
                "preservation_status": "bytes_preserved",
            }), encoding="utf-8")

            plan = restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE)
            document = plan.public_document()
            self.assertTrue(document["ok"], document)
            self.assertEqual(document["mode"], "restore")
            self.assertEqual(document["restore_target_count"], 4)
            self.assertEqual(document["already_present_count"], 1)
            self.assertEqual(document["local_conflict_count"], 1)
            self.assertEqual(document["remote_evidence_missing_count"], 2)
            self.assertEqual(document["wom_uploaded_source_count"], 3)
            self.assertEqual(document["bytes_preserved_receipt_source_count"], 1)
            self.assertEqual(document["local_location_add_count"], 2)      # missing + preserved
            self.assertEqual(document["local_location_reactivate_count"], 1)  # offloaded
            self.assertEqual(document["planned_download_bytes"], len(missing) + len(gone) + len(preserved) + len(offloaded))
            self.assertEqual(document["manifest_rewrite_planned_count"], 1)
            self.assertFalse(document["provider_api_called"])
            self.assertFalse(document["writes_performed"])
            self.assertFalse(document["remote_keys_echoed"])
            rendered = json.dumps(document)
            for spec in plan.specs:
                self.assertNotIn(spec.remote_key, rendered)
                self.assertNotIn(spec.object_id, rendered)
            self.assertNotIn(str(root), rendered)
            kinds = {spec.object_id: spec.remote_source_kind for spec in plan.specs}
            self.assertEqual(kinds["sha256:" + preserved_digest], restore.REMOTE_SOURCE_PRESERVED)
            # verify-only covers every remote-verified object, present or not
            verify = restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE, mode=restore.MODE_VERIFY_ONLY)
            self.assertEqual(verify.public_document()["verify_target_count"], 5)
            self.assertEqual(verify.public_document()["manifest_rewrite_planned_count"], 0)
            # --only and --max-objects
            only = restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE, only=hashlib.sha256(missing).hexdigest())
            self.assertEqual(len(only.specs), 1)
            with self.assertRaises(restore.ObjectStorageRestoreError) as ctx:
                restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE, max_objects=1)
            self.assertEqual(ctx.exception.code, "object_storage_restore_plan_invalid")

    def test_plan_requires_setup_evidence_for_the_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _build_root(Path(tmp))
            raw = b"x"
            _write_rows(root, [_row(raw, locations=[_remote(raw)])])
            with self.assertRaises(restore.ObjectStorageRestoreError) as ctx:
                restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref="storage:account:unregistered")
            self.assertIn(ctx.exception.code, {"object_storage_restore_setup_evidence_missing", "object_storage_restore_setup_evidence_mismatch"})


    def test_resolver_names_remote_verified_objects_and_the_restore_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _build_root(Path(tmp))
            missing = b"remote verified, local absent"
            declared = b"declared only"
            present = b"present locally"
            _write_rows(root, [
                _row(missing, locations=[_remote(missing)]),
                _row(declared, locations=[{"provider": "object_storage", "availability": "declared_uploaded", "store_ref": STORE}]),
                _row(present, locations=[_local(present), _remote(present)]),
            ])
            _write_local(root, present)
            resolved = archive_services.resolve_objet_ref(root, object_id="sha256:" + hashlib.sha256(missing).hexdigest())
            self.assertEqual(resolved["resolution_state"], "remote_verified_local_absent")
            self.assertTrue(resolved["remote_verified_local_absent"])
            self.assertEqual(resolved["restore_workflow"], "object-storage-restore")
            self.assertTrue(any("object-storage-restore" in action for action in resolved["next_safe_actions"]))
            self.assertTrue(resolved["external_candidates"][0]["remote_verified_by_wom_kit"])
            self.assertFalse(resolved["privacy_guards"]["download_performed"])
            self.assertNotIn("remote_key", json.dumps(resolved))
            declared_result = archive_services.resolve_objet_ref(root, object_id="sha256:" + hashlib.sha256(declared).hexdigest())
            self.assertEqual(declared_result["resolution_state"], "external_declared")
            self.assertIsNone(declared_result["restore_workflow"])
            present_result = archive_services.resolve_objet_ref(root, object_id="sha256:" + hashlib.sha256(present).hexdigest())
            self.assertEqual(present_result["resolution_state"], "local_available")
            self.assertFalse(present_result["remote_verified_local_absent"])

    def test_receipt_validates_against_the_packaged_schema(self):
        from jsonschema import Draft202012Validator

        with tempfile.TemporaryDirectory() as tmp:
            root = _build_root(Path(tmp))
            raw = b"schema validated receipt"
            _write_rows(root, [_row(raw, locations=[_remote(raw)])])
            plan = restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE)
            result = _run(plan, _MemoryTransport({plan.specs[0].remote_key: raw}))
            self.assertTrue(result["ok"], result)
            schema_path = Path(__file__).resolve().parents[1] / "schemas" / "object-storage-restore-receipt-v0.1.schema.json"
            packaged = Path(__file__).resolve().parents[1] / "src" / "wom_kit" / "_resources" / "schemas" / "object-storage-restore-receipt-v0.1.schema.json"
            self.assertEqual(schema_path.read_bytes(), packaged.read_bytes())
            validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
            receipt = json.loads((root / plan.specs[0].receipt_relative).read_text(encoding="utf-8"))
            self.assertEqual(sorted(validator.iter_errors(receipt), key=str), [])


class RestoreExecutionTests(unittest.TestCase):
    def test_restore_writes_verified_bytes_receipts_and_one_manifest_projection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _build_root(Path(tmp))
            missing = b"missing local bytes " * 3
            gone = b"file gone by hand"
            offloaded = b"offloaded object"
            rows = [
                _row(missing, locations=[_remote(missing)]),
                _row(gone, locations=[_local(gone), _remote(gone)]),
                _row(offloaded, locations=[{**_local(offloaded, availability="offloaded"), "offload_receipt_ref": "receipts/x.json", "offloaded_at": "2026-09-01T00:00:00Z"}, _remote(offloaded)]),
            ]
            _write_rows(root, rows)
            plan = restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE)
            self.assertEqual(len(plan.specs), 3)
            self.assertEqual(len(plan.manifest.items), 4)  # 3 receipts + 1 projection
            transport = _MemoryTransport({spec.remote_key: raw for spec, raw in zip(plan.specs, sorted([missing, gone, offloaded], key=lambda b: "sha256:" + hashlib.sha256(b).hexdigest()))})
            result = _run(plan, transport)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["state"], "restore_completed")
            self.assertEqual(result["status_counts"]["bytes_restored"], 3)
            self.assertEqual(result["provider_get_call_count"], 3)
            self.assertEqual(result["manifest_location_updates"], 2)  # missing gets a location, offloaded is reactivated; gone already active
            self.assertEqual(transport.get_calls, 3)
            self.assertEqual(transport.delete_calls, 0)
            self.assertEqual(transport.put_calls, 0)
            self.assertFalse(result["remote_delete_performed"])
            for raw in (missing, gone, offloaded):
                self.assertEqual(_dest(root, raw).read_bytes(), raw)
            rows_after = _rows_after(root)
            for raw in (missing, gone, offloaded):
                row = rows_after["sha256:" + hashlib.sha256(raw).hexdigest()]
                active = [loc for loc in row["locations"] if loc.get("provider") == "local" and loc.get("availability") == "available"]
                self.assertEqual(len(active), 1, row)
                self.assertNotIn("offload_receipt_ref", active[0])
            for spec in plan.specs:
                receipt = json.loads((root / spec.receipt_relative).read_text(encoding="utf-8"))
                self.assertEqual(receipt["schema_version"], restore.RECEIPT_SCHEMA)
                self.assertEqual(receipt["restore_status"], "bytes_restored")
                self.assertTrue(receipt["local_bytes_written"])
                self.assertTrue(receipt["remote_verification"]["whole_object_sha256_match"])
                self.assertFalse(receipt["remote_delete_performed"])
                self.assertFalse(receipt["local_overwrite_performed"])
                self.assertNotIn("remote_key", receipt)
                self.assertNotIn(str(root), json.dumps(receipt))
            # no sink residue
            self.assertFalse(any((root / restore.SINK_ROOT).rglob("*.part")))
            # idempotent verification and a second run is a no-op
            verified = restore.verify_object_storage_restore(plan)
            self.assertTrue(verified["ok"], verified)
            # index is current after the projection
            self.assertTrue(archive_services.require_current_zettel_index(root)["ok"])
            # Doctor deep sees the restored bytes
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                code = archive_cli.main(["doctor", str(root), "--format", "json"])
            doctor = json.loads(out.getvalue())
            summary = next(item for item in doctor if item.get("code") == "local_object_bytes_rehashed_now")["details"]
            self.assertTrue(summary["byte_integrity_verified"], summary)
            self.assertEqual(summary["local_reference_count"], 3)
            self.assertEqual(summary["unresolved_local_reference_count"], 0)
            self.assertFalse(any(item.get("code") == "local_object_missing" for item in doctor))

    def test_remote_mismatch_or_absence_is_review_required_without_local_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _build_root(Path(tmp))
            corrupt = b"corrupt remote copy"
            absent = b"absent remote copy"
            good = b"good remote copy"
            _write_rows(root, [_row(corrupt, locations=[_remote(corrupt)]), _row(absent, locations=[_remote(absent)]), _row(good, locations=[_remote(good)])])
            plan = restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE)
            by_id = {spec.object_id: spec for spec in plan.specs}
            objects = {
                by_id["sha256:" + hashlib.sha256(corrupt).hexdigest()].remote_key: b"CORRUPT remote copy",
                by_id["sha256:" + hashlib.sha256(good).hexdigest()].remote_key: good,
            }
            transport = _MemoryTransport(objects)
            result = _run(plan, transport)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status_counts"]["bytes_restored"], 1)
            self.assertEqual(result["status_counts"]["review_required"], 2)
            self.assertFalse(_dest(root, corrupt).exists())
            self.assertFalse(_dest(root, absent).exists())
            self.assertEqual(_dest(root, good).read_bytes(), good)
            self.assertEqual(result["manifest_location_updates"], 1)
            rows_after = _rows_after(root)
            for raw in (corrupt, absent):
                row = rows_after["sha256:" + hashlib.sha256(raw).hexdigest()]
                self.assertFalse(any(loc.get("provider") == "local" for loc in row["locations"]), row)
            reasons = {}
            for spec in plan.specs:
                receipt = json.loads((root / spec.receipt_relative).read_text(encoding="utf-8"))
                reasons[spec.object_id] = receipt["review_reason"]
            self.assertEqual(reasons["sha256:" + hashlib.sha256(corrupt).hexdigest()], "remote_checksum_mismatch")
            self.assertEqual(reasons["sha256:" + hashlib.sha256(absent).hexdigest()], "remote_absent")
            self.assertIsNone(reasons["sha256:" + hashlib.sha256(good).hexdigest()])
            self.assertFalse(any((root / restore.SINK_ROOT).rglob("*.part")))
            self.assertTrue(restore.verify_object_storage_restore(plan)["ok"])

    def test_transport_trouble_is_resumable_without_a_second_download_of_done_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _build_root(Path(tmp))
            first = b"first object restored"
            second = b"second object stalls"
            _write_rows(root, [_row(first, locations=[_remote(first)]), _row(second, locations=[_remote(second)])])
            plan = restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE)
            objects = {spec.remote_key: raw for spec, raw in zip(plan.specs, sorted([first, second], key=lambda b: "sha256:" + hashlib.sha256(b).hexdigest()))}
            order = [raw for raw in sorted([first, second], key=lambda b: "sha256:" + hashlib.sha256(b).hexdigest())]

            class _StallSecond(_MemoryTransport):
                def get_object(self, *, key, **kwargs):
                    if key == plan.specs[1].remote_key and self.get_calls == 1:
                        self.get_calls += 1
                        return {"status_class": "rate_limited", "size": None, "checksum_sha256": None, "size_match": False, "checksum_match": False, "sink_written": False}
                    return super().get_object(key=key, **kwargs)

            transport = _StallSecond(objects)
            with self.assertRaises(ExactOperationManifestError):
                _run(plan, transport)
            self.assertEqual(_dest(root, order[0]).read_bytes(), order[0])
            self.assertFalse(_dest(root, order[1]).exists())
            self.assertTrue((root / plan.specs[0].receipt_relative).exists())
            self.assertFalse((root / plan.specs[1].receipt_relative).exists())
            loaded = restore.load_object_storage_restore_plan(root, manifest_sha256=plan.manifest.manifest_sha256)
            self.assertTrue(loaded.loaded_from_control)
            resumed = _run(loaded, transport, resume=True)
            self.assertTrue(resumed["ok"], resumed)
            self.assertEqual(transport.get_calls, 3)  # 1 ok + 1 stall + 1 ok; the first object is never fetched twice
            self.assertEqual(_dest(root, order[1]).read_bytes(), order[1])
            self.assertEqual(resumed["manifest_location_updates"], 2)

    def test_crash_after_promotion_before_receipt_recovers_from_disk_without_a_second_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _build_root(Path(tmp))
            raw = b"promoted then crashed"
            _write_rows(root, [_row(raw, locations=[_remote(raw)])])
            plan = restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE)
            transport = _MemoryTransport({plan.specs[0].remote_key: raw})
            with patch.object(restore, "_create_receipt", side_effect=RuntimeError("crash after move")):
                with self.assertRaises(ExactOperationManifestError):
                    _run(plan, transport)
            self.assertEqual(_dest(root, raw).read_bytes(), raw)
            self.assertFalse((root / plan.specs[0].receipt_relative).exists())
            resumed = _run(restore.load_object_storage_restore_plan(root, manifest_sha256=plan.manifest.manifest_sha256), transport, resume=True)
            self.assertTrue(resumed["ok"], resumed)
            self.assertEqual(transport.get_calls, 1)
            receipt = json.loads((root / plan.specs[0].receipt_relative).read_text(encoding="utf-8"))
            self.assertEqual(receipt["restore_status"], "already_present_verified")
            self.assertFalse(receipt["remote_verification"]["performed"])

    def test_local_conflict_never_overwrites_and_stale_sink_is_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _build_root(Path(tmp))
            raw = b"the manifest bytes"
            _write_rows(root, [_row(raw, locations=[_remote(raw)])])
            plan = restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE)
            self.assertEqual(len(plan.specs), 1)
            # a stale sink from an interrupted attempt
            sink = root / restore._sink_relative(plan, plan.specs[0])
            sink.parent.mkdir(parents=True, exist_ok=True)
            sink.write_bytes(b"stale partial")
            # foreign bytes appear at the destination after the plan
            _dest(root, raw).parent.mkdir(parents=True, exist_ok=True)
            _dest(root, raw).write_bytes(b"foreign bytes at dest")
            transport = _MemoryTransport({plan.specs[0].remote_key: raw})
            with self.assertRaises(ExactOperationManifestError):
                _run(plan, transport)
            self.assertEqual(_dest(root, raw).read_bytes(), b"foreign bytes at dest")
            self.assertEqual(transport.get_calls, 0)
            # remove the foreign file: the stale sink is discarded and the object restored
            _dest(root, raw).unlink()
            result = _run(restore.load_object_storage_restore_plan(root, manifest_sha256=plan.manifest.manifest_sha256), transport, resume=True)
            self.assertTrue(result["ok"], result)
            self.assertEqual(_dest(root, raw).read_bytes(), raw)
            self.assertFalse(sink.exists())

    def test_verify_only_proves_remote_bytes_without_touching_local_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _build_root(Path(tmp))
            present = b"present locally"
            missing = b"missing locally"
            _write_rows(root, [_row(present, locations=[_local(present), _remote(present)]), _row(missing, locations=[_remote(missing)])])
            _write_local(root, present)
            plan = restore.plan_object_storage_restore(root, provider_kind=PROVIDER, store_ref=STORE, mode=restore.MODE_VERIFY_ONLY)
            self.assertEqual(len(plan.specs), 2)
            self.assertEqual(len(plan.manifest.items), 2)
            manifest_before = (root / "objects/manifests/files.jsonl").read_bytes()
            objects = {spec.remote_key: raw for spec, raw in zip(plan.specs, sorted([present, missing], key=lambda b: "sha256:" + hashlib.sha256(b).hexdigest()))}
            transport = _MemoryTransport(objects)
            result = _run(plan, transport)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["state"], "remote_verification_completed")
            self.assertEqual(result["status_counts"]["remote_verified"], 2)
            self.assertEqual(result["manifest_location_updates"], 0)
            self.assertFalse(_dest(root, missing).exists())
            self.assertEqual((root / "objects/manifests/files.jsonl").read_bytes(), manifest_before)
            self.assertFalse(any((root / restore.SINK_ROOT).rglob("*.part")))
            for spec in plan.specs:
                receipt = json.loads((root / spec.receipt_relative).read_text(encoding="utf-8"))
                self.assertEqual(receipt["restore_status"], "remote_verified")
                self.assertFalse(receipt["local_bytes_written"])
                self.assertEqual(receipt["mode"], "verify_only")


class RestoreCliTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wom-v0428-restore-")
        self.addCleanup(temporary.cleanup)
        self.root = _build_root(Path(temporary.name))
        self.raw = b"cli restored object bytes"
        _write_rows(self.root, [_row(self.raw, locations=[_remote(self.raw)])])
        self.native = _Native()
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(windows, "_CtypesTaskDialogNative", return_value=self.native))
        stack.enter_context(patch.object(broker, "_production_key_provider", return_value=_KeyProvider()))
        stack.enter_context(patch.dict(os.environ, {"WOM_TEST_RESTORE_AK": "AKIAEXAMPLE", "WOM_TEST_RESTORE_SK": "s" * 40}))
        self.outputs: list[str] = []

    def run_cli(self, *args: str) -> tuple[int, dict]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = archive_cli.main([*args, "--format", "json"])
        self.outputs.extend((out.getvalue(), err.getvalue()))
        return code, json.loads(out.getvalue())

    def base_args(self) -> list[str]:
        return [
            "object-storage-restore", str(self.root),
            "--provider-kind", PROVIDER, "--store-ref", STORE,
            "--endpoint-host", "acct.r2.cloudflarestorage.com", "--bucket", "private-bucket",
            "--access-key-id-ref", "env:WOM_TEST_RESTORE_AK", "--secret-access-key-ref", "env:WOM_TEST_RESTORE_SK",
        ]

    def test_dry_run_then_approve_restores_through_the_live_transport_seam(self):
        code, preview = self.run_cli(*self.base_args(), "--dry-run")
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["state"], "ready_for_exact_human_approval")
        self.assertEqual(preview["restore_target_count"], 1)
        self.assertEqual(self.native.calls, 0)
        digest = hashlib.sha256(self.raw).hexdigest()
        send, calls = _sink_sender(self.raw)
        with patch.object(archive_services, "_default_urllib_sender", return_value=send):
            code, result = self.run_cli(
                *self.base_args(), "--approve", "--reviewed-by", REVIEWER,
                "--expected-manifest-sha256", preview["plan_sha256"],
            )
        self.assertEqual(code, 0, result)
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.native.calls, 1)
        context = self.native.contexts[0]
        self.assertIn("되찾기", str(context.get("main_instruction")) + str(context.get("approve_button_text")))
        self.assertEqual(result["status_counts"]["bytes_restored"], 1)
        self.assertEqual(len([c for c in calls if c["method"] == "GET"]), 1)
        self.assertEqual(len([c for c in calls if c["method"] != "GET"]), 0)
        self.assertEqual(_dest(self.root, self.raw).read_bytes(), self.raw)
        rendered = "".join(self.outputs) + json.dumps(self.native.contexts, ensure_ascii=False)
        self.assertNotIn("s" * 40, rendered)
        self.assertNotIn(f"sha256/{digest[:2]}/{digest}", rendered)
        self.assertNotIn(str(self.root), rendered)
        self.assertNotIn(REVIEWER, "".join(self.outputs))

    def test_cancelled_dialog_writes_nothing(self):
        code, preview = self.run_cli(*self.base_args(), "--dry-run")
        self.native.approve = False
        send, calls = _sink_sender(self.raw)
        with patch.object(archive_services, "_default_urllib_sender", return_value=send):
            code, result = self.run_cli(
                *self.base_args(), "--approve", "--reviewed-by", REVIEWER,
                "--expected-manifest-sha256", preview["plan_sha256"],
            )
        self.assertEqual(code, 1, result)
        self.assertFalse(result["ok"])
        self.assertEqual(calls, [])
        self.assertFalse(_dest(self.root, self.raw).exists())

    def test_usage_refusals_carry_fixed_codes(self):
        code, result = self.run_cli(*self.base_args())
        self.assertEqual(result["reason_codes"][0], "object_storage_restore_plan_invalid")
        code, result = self.run_cli(*self.base_args(), "--approve")
        self.assertEqual(result["reason_codes"][0], "object_storage_restore_approval_required")
        code, result = self.run_cli(*self.base_args(), "--approve", "--reviewed-by", REVIEWER, "--expected-manifest-sha256", "sha256:" + "0" * 64)
        self.assertEqual(result["reason_codes"][0], "object_storage_restore_plan_changed")
        code, result = self.run_cli(*self.base_args(), "--approve", "--reviewed-by", REVIEWER, "--expected-manifest-sha256", "sha256:" + "0" * 64, "--resume-approval-id", "approval_" + "a" * 32)
        self.assertEqual(result["reason_codes"][0], "object_storage_restore_resume_invalid")
        self.assertEqual(self.native.calls, 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
