from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit.exact_human_approval import (  # noqa: E402
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import (  # noqa: E402
    ExactHumanApprovalOperation,
)
from wom_kit import exact_operation_manifest as manifest_module  # noqa: E402
from wom_kit.exact_operation_manifest import (  # noqa: E402
    APPROVAL_AUTHORITY_SCHEMA,
    CHECKPOINT_SCHEMA,
    FIELD_RECEIPT_SCHEMA,
    FIRST_STATUS_DEADLINE_SECONDS,
    HEARTBEAT_INTERVAL_SECONDS,
    ExactFieldEffect,
    ExactOperationApprovalAuthority,
    ExactOperationEvidence,
    ExactOperationWriterLock,
    FileExactOperationCheckpointStore,
    ExactOperationItem,
    ExactOperationManifest,
    ExactOperationManifestError,
    apply_exact_operation,
    exact_operation_execution_sha256,
    exact_operation_writer_lock,
    hash_field_value,
    revert_exact_operation_fields,
    verify_exact_operation,
)
from wom_kit.operation_approval_binding import (  # noqa: E402
    OperationApprovalBindingError,
    exact_operation_manifest_approval_binding,
)


class _Payloads:
    def __init__(self, values: dict[tuple[str, str, str], bytes | None]) -> None:
        self.values = values

    def field_value(
        self,
        *,
        item_id: str,
        field_ref: str,
        state: str,
        heartbeat,
    ) -> bytes | None:
        heartbeat()
        return self.values[(item_id, field_ref, state)]


class _Target:
    def __init__(self) -> None:
        self.identities: dict[tuple[str, str], str] = {}
        self.values: dict[tuple[str, str, str], bytes | None] = {}


class _Writer:
    def __init__(self, target: _Target, *, fail_after_write: bool = False) -> None:
        self.target = target
        self.fail_after_write = fail_after_write
        self.write_count = 0

    def write_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        value: bytes | None,
        heartbeat,
    ) -> None:
        heartbeat()
        self.target.values[(target_kind, target_ref, field_ref)] = value
        self.write_count += 1
        if self.fail_after_write:
            self.fail_after_write = False
            raise OSError("synthetic_crash_after_write")


class _Verifier:
    def __init__(self, target: _Target) -> None:
        self.target = target

    def target_identity_sha256(
        self,
        *,
        target_kind: str,
        target_ref: str,
        heartbeat,
    ) -> str:
        heartbeat()
        return self.target.identities[(target_kind, target_ref)]

    def read_field(
        self,
        *,
        target_kind: str,
        target_ref: str,
        field_ref: str,
        heartbeat,
    ) -> bytes | None:
        heartbeat()
        return self.target.values[(target_kind, target_ref, field_ref)]


class _CheckpointStore:
    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, object]]] = {}
        self.results: dict[str, dict[str, object]] = {}

    def load(self, execution_sha256: str, *, heartbeat):
        heartbeat()
        return copy.deepcopy(self.rows.get(execution_sha256, []))

    def append(self, execution_sha256: str, checkpoint, *, heartbeat) -> None:
        heartbeat()
        self.rows.setdefault(execution_sha256, []).append(copy.deepcopy(checkpoint))

    def finalize(self, result, *, heartbeat) -> str:
        heartbeat()
        execution_sha256 = result["execution_sha256"]
        current = self.results.get(execution_sha256)
        if current is not None and current != result:
            raise OSError("result_mismatch")
        self.results[execution_sha256] = copy.deepcopy(result)
        return result["result_sha256"]


class ExactOperationManifestTests(unittest.TestCase):
    archive_id = "archive:test:exact-operation"

    def fixture(
        self,
        *,
        item_fields: tuple[tuple[str, tuple[str, ...]], ...] = (
            ("item:one", ("body", "title")),
        ),
    ) -> tuple[ExactOperationManifest, _Payloads, _Target, _Verifier]:
        items: list[ExactOperationItem] = []
        payload_values: dict[tuple[str, str, str], bytes | None] = {}
        target = _Target()
        for ordinal, (item_id, field_refs) in enumerate(item_fields):
            target_ref = f"private/target-{ordinal}.md"
            identity = hash_field_value(f"identity-{ordinal}".encode("ascii"))
            target.identities[("zettel", target_ref)] = identity
            fields: list[ExactFieldEffect] = []
            for field_ref in sorted(field_refs):
                pre = f"pre-{ordinal}-{field_ref}".encode("ascii")
                post = f"post-{ordinal}-{field_ref}".encode("ascii")
                source = f"source-{ordinal}-{field_ref}".encode("ascii")
                target.values[("zettel", target_ref, field_ref)] = pre
                payload_values[(item_id, field_ref, "pre")] = pre
                payload_values[(item_id, field_ref, "post")] = post
                payload_values[(item_id, field_ref, "source")] = source
                fields.append(
                    ExactFieldEffect(
                        field_ref=field_ref,
                        pre_sha256=hash_field_value(pre),
                        post_sha256=hash_field_value(post),
                        source_sha256=hash_field_value(source),
                    )
                )
            items.append(
                ExactOperationItem(
                    ordinal=ordinal,
                    item_id=item_id,
                    target_kind="zettel",
                    target_ref=target_ref,
                    target_identity_sha256=identity,
                    fields=tuple(fields),
                )
            )
        manifest = ExactOperationManifest.build(
            operation="create_draft",
            archive_identity_sha256=(
                exact_human_approval_archive_identity_sha256(self.archive_id)
            ),
            items=items,
        )
        return manifest, _Payloads(payload_values), target, _Verifier(target)

    def test_manifest_round_trip_rejects_tamper_and_reuses_native_approval(self) -> None:
        manifest, _, _, _ = self.fixture()
        self.assertEqual(
            ExactOperationManifest.from_document(manifest.document()),
            manifest,
        )
        approval = exact_operation_manifest_approval_binding(
            manifest,
            operation=ExactHumanApprovalOperation.create_draft,
            archive_id=self.archive_id,
            warnings=["private source warning"],
        )
        self.assertEqual(approval.plan_sha256, manifest.manifest_sha256)
        self.assertEqual(
            approval.target_binding_sha256,
            manifest.target_set_sha256,
        )
        serialized = json.dumps(approval.public_document(), ensure_ascii=False)
        self.assertNotIn("private/target", serialized)
        self.assertNotIn("private source warning", serialized)

        tampered = manifest.document()
        tampered["items"][0]["fields"][0]["post_sha256"] = "sha256:" + "f" * 64
        with self.assertRaises(ExactOperationManifestError) as captured:
            ExactOperationManifest.from_document(tampered)
        self.assertEqual(
            captured.exception.code,
            "exact_operation_manifest_digest_mismatch",
        )
        with self.assertRaises(ExactOperationManifestError):
            replace(manifest, target_set_sha256="sha256:" + "e" * 64)
        with self.assertRaises(OperationApprovalBindingError) as mismatch:
            exact_operation_manifest_approval_binding(
                manifest,
                operation=ExactHumanApprovalOperation.create_draft,
                archive_id="archive:test:other",
            )
        self.assertEqual(
            mismatch.exception.code,
            "operation_approval_binding_mismatch",
        )

    def test_operation_evidence_is_manifest_bound_and_durable(self) -> None:
        legacy, payloads, target, verifier = self.fixture(
            item_fields=(("item:one", ("title",)),)
        )
        evidence_document = {
            "schema": "wom-kit/notion-property-backfill-evidence/v1",
            "counts": {
                "backfill": 1,
                "mapped": 1,
                "review": 137,
                "total": 11585,
                "unmapped": 2882,
            },
            "digests": {
                "classification_set_sha256": "sha256:" + "a" * 64,
                "mirror_snapshot_sha256": "sha256:" + "b" * 64,
                "unmapped_set_sha256": "sha256:" + "c" * 64,
            },
            "private_values_echoed": False,
        }
        manifest = ExactOperationManifest.build(
            operation=legacy.operation,
            archive_identity_sha256=legacy.archive_identity_sha256,
            items=legacy.items,
            operation_evidence=evidence_document,
        )
        self.assertNotIn("operation_evidence", legacy.document())
        self.assertNotEqual(manifest.manifest_sha256, legacy.manifest_sha256)
        self.assertEqual(
            ExactOperationManifest.from_document(manifest.document()),
            manifest,
        )
        self.assertEqual(
            manifest.operation_evidence,
            ExactOperationEvidence.from_document(evidence_document),
        )
        self.assertEqual(
            manifest.approval_digest_context()["operation_evidence_sha256"],
            manifest.operation_evidence.evidence_sha256,
        )

        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                result = apply_exact_operation(
                    manifest,
                    payloads=payloads,
                    writer=_Writer(target),
                    verifier=verifier,
                    checkpoint_store=store,
                )
                receipt = store.load_final_receipt(result["execution_sha256"])
        self.assertEqual(result["operation_evidence"], evidence_document)
        self.assertEqual(receipt["result"]["operation_evidence"], evidence_document)

        tampered = manifest.document()
        tampered["operation_evidence"]["counts"]["unmapped"] = 2881
        with self.assertRaises(ExactOperationManifestError) as mismatch:
            ExactOperationManifest.from_document(tampered)
        self.assertEqual(
            mismatch.exception.code,
            "exact_operation_manifest_digest_mismatch",
        )

    def test_operation_evidence_rejects_reflective_or_unbounded_shapes(self) -> None:
        base = {
            "schema": "wom-kit/synthetic-evidence/v1",
            "counts": {"total": 1},
            "digests": {"set_sha256": "sha256:" + "d" * 64},
            "private_values_echoed": False,
        }
        invalid_documents = []
        private = copy.deepcopy(base)
        private["private_values_echoed"] = True
        invalid_documents.append(private)
        reflective = copy.deepcopy(base)
        reflective["private_path"] = "private/value"
        invalid_documents.append(reflective)
        boolean_count = copy.deepcopy(base)
        boolean_count["counts"]["total"] = True
        invalid_documents.append(boolean_count)
        bad_digest = copy.deepcopy(base)
        bad_digest["digests"]["set_sha256"] = "private/value"
        invalid_documents.append(bad_digest)
        bad_schema = copy.deepcopy(base)
        bad_schema["schema"] = "private/value"
        invalid_documents.append(bad_schema)

        for document in invalid_documents:
            with self.subTest(document_keys=tuple(sorted(document))):
                with self.assertRaises(ExactOperationManifestError):
                    ExactOperationEvidence.from_document(document)

    def test_apply_writes_hash_chained_field_receipts_and_heartbeats(self) -> None:
        manifest, payloads, target, verifier = self.fixture()
        store = _CheckpointStore()
        writer = _Writer(target)
        progress = []

        result = apply_exact_operation(
            manifest,
            payloads=payloads,
            writer=writer,
            verifier=verifier,
            checkpoint_store=store,
            progress_hook=progress.append,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["written_field_count"], 2)
        self.assertEqual(result["field_receipt_count"], 2)
        self.assertEqual(result["checkpoint_count"], 4)
        rows = next(iter(store.rows.values()))
        self.assertTrue(all(row["schema"] == CHECKPOINT_SCHEMA for row in rows))
        field_rows = [row for row in rows if row["stage"] == "field_verified"]
        self.assertTrue(
            all(
                isinstance(row["field_receipt_sha256"], str)
                and row["field_receipt_sha256"].startswith("sha256:")
                for row in field_rows
            )
        )
        self.assertEqual(FIELD_RECEIPT_SCHEMA, "wom-kit/exact-operation-field-receipt/v1")
        self.assertIsNone(progress[0].execution_sha256)
        self.assertEqual(progress[0].stage, "preflight")
        self.assertEqual(FIRST_STATUS_DEADLINE_SECONDS, 2)
        self.assertEqual(HEARTBEAT_INTERVAL_SECONDS, 10)
        self.assertTrue(
            verify_exact_operation(manifest, verifier=verifier, state="post")[
                "all_match"
            ]
        )

    def test_heartbeat_is_throttled_until_the_ten_second_boundary(self) -> None:
        manifest, _, _, _ = self.fixture()
        now = [100.0]
        events = []
        publisher = manifest_module._ProgressPublisher(
            events.append,
            clock=lambda: now[0],
        )
        initial = manifest_module.ExactOperationProgress(
            manifest.manifest_sha256,
            None,
            "apply",
            "preflight",
            0,
            1,
            0,
            2,
        )
        publisher.publish(initial)
        for _ in range(8_569):
            publisher.heartbeat()
        self.assertEqual(len(events), 1)

        now[0] = 109.999
        publisher.heartbeat()
        self.assertEqual(len(events), 1)
        now[0] = 110.0
        publisher.heartbeat()
        self.assertEqual([event.stage for event in events], ["preflight", "heartbeat"])
        for _ in range(8_569):
            publisher.heartbeat()
        self.assertEqual(len(events), 2)

        now[0] = 119.0
        publisher.publish(replace(initial, stage="field_verified"))
        now[0] = 128.999
        publisher.heartbeat()
        self.assertEqual(len(events), 3)
        now[0] = 129.0
        publisher.heartbeat()
        self.assertEqual(events[-1].stage, "heartbeat")
        self.assertEqual(len(events), 4)

    def test_resume_recovers_write_completed_before_field_receipt(self) -> None:
        manifest, payloads, target, verifier = self.fixture(
            item_fields=(("item:one", ("title",)),)
        )
        store = _CheckpointStore()
        crashing_writer = _Writer(target, fail_after_write=True)
        with self.assertRaises(ExactOperationManifestError) as captured:
            apply_exact_operation(
                manifest,
                payloads=payloads,
                writer=crashing_writer,
                verifier=verifier,
                checkpoint_store=store,
            )
        self.assertEqual(captured.exception.code, "exact_operation_write_failed")
        self.assertEqual(len(next(iter(store.rows.values()))), 1)

        resumed_writer = _Writer(target)
        result = apply_exact_operation(
            manifest,
            payloads=payloads,
            writer=resumed_writer,
            verifier=verifier,
            checkpoint_store=store,
            resume=True,
        )
        self.assertEqual(result["written_field_count"], 0)
        self.assertEqual(result["resumed_field_count"], 1)
        self.assertEqual(resumed_writer.write_count, 0)
        self.assertEqual(result["field_receipt_count"], 1)

        rows = next(iter(store.rows.values()))
        rows[1]["field_receipt_sha256"] = "sha256:" + "0" * 64
        with self.assertRaises(ExactOperationManifestError) as tampered:
            apply_exact_operation(
                manifest,
                payloads=payloads,
                writer=_Writer(target),
                verifier=verifier,
                checkpoint_store=store,
                resume=True,
            )
        self.assertEqual(tampered.exception.code, "exact_operation_checkpoint_invalid")

    def test_field_scoped_revert_ignores_later_unselected_field_revision(self) -> None:
        manifest, payloads, target, verifier = self.fixture()
        apply_exact_operation(
            manifest,
            payloads=payloads,
            writer=_Writer(target),
            verifier=verifier,
            checkpoint_store=_CheckpointStore(),
        )
        item = manifest.items[0]
        body_key = (item.target_kind, item.target_ref, "body")
        title_key = (item.target_kind, item.target_ref, "title")
        later_body = b"later-legitimate-body-revision"
        target.values[body_key] = later_body

        result = revert_exact_operation_fields(
            manifest,
            selected_fields=((item.item_id, "title"),),
            payloads=payloads,
            writer=_Writer(target),
            verifier=verifier,
            checkpoint_store=_CheckpointStore(),
        )

        self.assertEqual(result["field_count"], 1)
        self.assertEqual(target.values[body_key], later_body)
        self.assertEqual(
            hash_field_value(target.values[title_key]),
            next(field for field in item.fields if field.field_ref == "title").pre_sha256,
        )
        selected_verification = verify_exact_operation(
            manifest,
            verifier=verifier,
            state="pre",
            selected_fields=((item.item_id, "title"),),
        )
        self.assertTrue(selected_verification["all_match"])

    def test_full_preflight_prevents_partial_write_when_later_target_drifted(self) -> None:
        manifest, payloads, target, verifier = self.fixture(
            item_fields=(
                ("item:one", ("title",)),
                ("item:two", ("title",)),
            )
        )
        first = manifest.items[0]
        second = manifest.items[1]
        first_key = (first.target_kind, first.target_ref, "title")
        second_key = (second.target_kind, second.target_ref, "title")
        first_before = target.values[first_key]
        target.values[second_key] = b"unexpected-drift"
        store = _CheckpointStore()
        writer = _Writer(target)

        with self.assertRaises(ExactOperationManifestError) as captured:
            apply_exact_operation(
                manifest,
                payloads=payloads,
                writer=writer,
                verifier=verifier,
                checkpoint_store=store,
            )
        self.assertEqual(
            captured.exception.code,
            "exact_operation_target_state_drifted",
        )
        self.assertEqual(writer.write_count, 0)
        self.assertEqual(target.values[first_key], first_before)
        self.assertEqual(store.rows, {})

    def test_file_store_resumes_and_finalizes_one_stable_result_receipt(self) -> None:
        manifest, payloads, target, verifier = self.fixture()
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                first = apply_exact_operation(
                    manifest,
                    payloads=payloads,
                    writer=_Writer(target),
                    verifier=verifier,
                    checkpoint_store=store,
                )
                receipt = store.load_final_receipt(first["execution_sha256"])
                self.assertIsNotNone(receipt)
                self.assertEqual(
                    receipt["result"]["result_sha256"],
                    first["result_sha256"],
                )
                self.assertTrue(
                    list(
                        (
                            archive_root
                            / "profiles"
                            / "local"
                            / "exact-operations"
                            / "checkpoints"
                        ).glob("*.jsonl")
                    )
                )
                self.assertFalse(
                    (
                        archive_root
                        / "receipts"
                        / "ops"
                        / "exact-operations"
                        / ".writer.lock"
                    ).exists()
                )

            with exact_operation_writer_lock(archive_root) as writer_lock:
                resumed_store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                resumed = apply_exact_operation(
                    manifest,
                    payloads=payloads,
                    writer=_Writer(target),
                    verifier=verifier,
                    checkpoint_store=resumed_store,
                    resume=True,
                )
                self.assertEqual(resumed["result_sha256"], first["result_sha256"])
                self.assertEqual(
                    resumed["final_receipt_sha256"],
                    first["final_receipt_sha256"],
                )
                self.assertEqual(resumed["written_field_count"], 0)
                self.assertEqual(resumed["resumed_field_count"], 2)

    def test_resume_idempotently_finalizes_after_last_checkpoint_crash(self) -> None:
        manifest, payloads, target, verifier = self.fixture(
            item_fields=(("item:one", ("title",)),)
        )
        execution_sha256 = exact_operation_execution_sha256(manifest)

        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                durable_store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )

                class _CrashBeforeFinalReceipt:
                    def load(self, execution, *, heartbeat):
                        return durable_store.load(
                            execution,
                            heartbeat=heartbeat,
                        )

                    def append(self, execution, checkpoint, *, heartbeat):
                        durable_store.append(
                            execution,
                            checkpoint,
                            heartbeat=heartbeat,
                        )

                    def finalize(self, _result, *, heartbeat):
                        heartbeat()
                        raise OSError("synthetic_crash_before_final_receipt")

                with self.assertRaises(ExactOperationManifestError) as crashed:
                    apply_exact_operation(
                        manifest,
                        payloads=payloads,
                        writer=_Writer(target),
                        verifier=verifier,
                        checkpoint_store=_CrashBeforeFinalReceipt(),
                    )
                self.assertEqual(
                    crashed.exception.code,
                    "exact_operation_result_receipt_failed",
                )
                self.assertEqual(
                    len(
                        durable_store.load(
                            execution_sha256,
                            heartbeat=lambda: None,
                        )
                    ),
                    3,
                )
                self.assertIsNone(
                    durable_store.load_final_receipt(execution_sha256)
                )

            with exact_operation_writer_lock(archive_root) as writer_lock:
                resumed_store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                resumed = apply_exact_operation(
                    manifest,
                    payloads=payloads,
                    writer=_Writer(target),
                    verifier=verifier,
                    checkpoint_store=resumed_store,
                    resume=True,
                )
                receipt = resumed_store.load_final_receipt(execution_sha256)
                self.assertIsNotNone(receipt)
                self.assertEqual(
                    receipt["result"]["result_sha256"],
                    resumed["result_sha256"],
                )

    def test_final_receipt_requires_complete_checkpoint_evidence(self) -> None:
        manifest, payloads, target, verifier = self.fixture(
            item_fields=(("item:one", ("title",)),)
        )
        completed = apply_exact_operation(
            manifest,
            payloads=payloads,
            writer=_Writer(target),
            verifier=verifier,
            checkpoint_store=_CheckpointStore(),
        )
        stable_result = {
            key: completed[key]
            for key in (
                "schema",
                "status",
                "mode",
                "manifest_sha256",
                "execution_sha256",
                "approval_binding_sha256",
                "item_count",
                "field_count",
                "checkpoint_count",
                "field_receipt_count",
                "field_receipt_set_sha256",
                "independent_verification_sha256",
                "private_values_echoed",
                "result_sha256",
            )
        }

        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                empty_store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                with self.assertRaises(ExactOperationManifestError) as blocked:
                    empty_store.finalize(
                        stable_result,
                        heartbeat=lambda: None,
                    )
                self.assertEqual(
                    blocked.exception.code,
                    "exact_operation_result_receipt_failed",
                )

    def test_checkpoint_binds_one_exact_human_approval_authority(self) -> None:
        manifest, payloads, target, verifier = self.fixture(
            item_fields=(("item:one", ("title",)),)
        )
        reference = {
            "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
            "approval_id": "approval_" + "1" * 32,
            "context_sha256": "sha256:" + "2" * 64,
            "approval_authority_sha256": "sha256:" + "3" * 64,
            "one_use": True,
        }
        authority = ExactOperationApprovalAuthority.from_reference(reference)
        self.assertEqual(authority.document()["schema"], APPROVAL_AUTHORITY_SCHEMA)
        execution_sha256 = exact_operation_execution_sha256(
            manifest,
            approval_authority=authority,
        )

        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            with exact_operation_writer_lock(archive_root) as writer_lock:
                store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                result = apply_exact_operation(
                    manifest,
                    payloads=payloads,
                    writer=_Writer(target),
                    verifier=verifier,
                    checkpoint_store=store,
                    approval_authority=authority,
                )
                self.assertEqual(result["execution_sha256"], execution_sha256)
                self.assertEqual(
                    result["approval_binding_sha256"],
                    authority.binding_sha256,
                )
                self.assertTrue(store.resume_checkpoint_present(execution_sha256))
                rows = store.load(execution_sha256, heartbeat=lambda: None)
                self.assertEqual(rows[0]["stage"], "started")
                self.assertEqual(rows[0]["approval"], authority.document())
                receipt = store.load_final_receipt(execution_sha256)
                receipt_text = json.dumps(receipt, sort_keys=True)
                self.assertNotIn(reference["approval_id"], receipt_text)
                self.assertNotIn(reference["context_sha256"], receipt_text)
                self.assertIn(authority.binding_sha256, receipt_text)

            other_reference = dict(reference)
            other_reference["approval_id"] = "approval_" + "4" * 32
            other_authority = ExactOperationApprovalAuthority.from_reference(
                other_reference
            )
            for mismatched_authority in (None, other_authority):
                with self.subTest(
                    mismatched_authority=mismatched_authority
                ), exact_operation_writer_lock(archive_root) as writer_lock:
                    store = FileExactOperationCheckpointStore(
                        archive_root,
                        writer_lock=writer_lock,
                    )
                    with self.assertRaises(ExactOperationManifestError) as blocked:
                        apply_exact_operation(
                            manifest,
                            payloads=payloads,
                            writer=_Writer(target),
                            verifier=verifier,
                            checkpoint_store=store,
                            approval_authority=mismatched_authority,
                            resume=True,
                        )
                    self.assertEqual(
                        blocked.exception.code,
                        "exact_operation_resume_checkpoint_missing",
                    )

            with exact_operation_writer_lock(archive_root) as writer_lock:
                store = FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=writer_lock,
                )
                resumed = apply_exact_operation(
                    manifest,
                    payloads=payloads,
                    writer=_Writer(target),
                    verifier=verifier,
                    checkpoint_store=store,
                    approval_authority=authority,
                    resume=True,
                )
                self.assertEqual(resumed["result_sha256"], result["result_sha256"])

    def test_archive_wide_writer_lock_is_fixed_bounded_and_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive_root = Path(temporary) / "archive"
            archive_root.mkdir()
            first = ExactOperationWriterLock(archive_root)
            with first:
                expected_lock = (
                    archive_root.resolve()
                    / "profiles"
                    / "local"
                    / "exact-operations"
                    / ".writer.lock"
                )
                self.assertEqual(first.path, expected_lock)
                self.assertTrue(expected_lock.is_file())
                with self.assertRaises(ExactOperationManifestError) as busy:
                    with exact_operation_writer_lock(
                        archive_root,
                        timeout_seconds=0.05,
                    ):
                        self.fail("a second archive-wide writer lock was acquired")
                self.assertEqual(busy.exception.code, "exact_operation_writer_busy")
            with exact_operation_writer_lock(archive_root) as released:
                released.verify_held()
            with self.assertRaises(ExactOperationManifestError) as required:
                FileExactOperationCheckpointStore(
                    archive_root,
                    writer_lock=released,
                )
            self.assertEqual(
                required.exception.code,
                "exact_operation_writer_lock_required",
            )

    def test_file_store_rejects_checkpoint_and_final_receipt_tamper(self) -> None:
        for tamper_target in ("checkpoint", "result"):
            with (
                self.subTest(tamper_target=tamper_target),
                tempfile.TemporaryDirectory() as temporary,
            ):
                manifest, payloads, target, verifier = self.fixture()
                archive_root = Path(temporary) / "archive"
                archive_root.mkdir()
                with exact_operation_writer_lock(archive_root) as writer_lock:
                    store = FileExactOperationCheckpointStore(
                        archive_root,
                        writer_lock=writer_lock,
                    )
                    result = apply_exact_operation(
                        manifest,
                        payloads=payloads,
                        writer=_Writer(target),
                        verifier=verifier,
                        checkpoint_store=store,
                    )
                if tamper_target == "checkpoint":
                    path = next(
                        (
                            archive_root
                            / "profiles"
                            / "local"
                            / "exact-operations"
                            / "checkpoints"
                        ).glob("*.jsonl")
                    )
                    path.write_bytes(path.read_bytes() + b"{}\n")
                else:
                    path = next(
                        (
                            archive_root
                            / "receipts"
                            / "ops"
                            / "exact-operations"
                        ).glob("*.json")
                    )
                    path.write_bytes(path.read_bytes().replace(b"completed", b"tampered", 1))

                with exact_operation_writer_lock(archive_root) as writer_lock:
                    tampered_store = FileExactOperationCheckpointStore(
                        archive_root,
                        writer_lock=writer_lock,
                    )
                    if tamper_target == "checkpoint":
                        with self.assertRaises(ExactOperationManifestError):
                            apply_exact_operation(
                                manifest,
                                payloads=payloads,
                                writer=_Writer(target),
                                verifier=verifier,
                                checkpoint_store=tampered_store,
                                resume=True,
                            )
                    else:
                        with self.assertRaises(ExactOperationManifestError) as captured:
                            tampered_store.load_final_receipt(
                                result["execution_sha256"]
                            )
                        self.assertEqual(
                            captured.exception.code,
                            "exact_operation_result_receipt_failed",
                        )


if __name__ == "__main__":
    unittest.main()
