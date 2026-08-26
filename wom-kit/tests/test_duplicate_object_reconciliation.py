from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest import mock

from wom_kit import duplicate_object_reconciliation as duplicate_module
from wom_kit.duplicate_object_reconciliation import (
    DuplicateObjectReconciliationError,
    _DuplicateObjectReconciliationPlan as DuplicateObjectReconciliationPlan,
    _DuplicateObjectReconciliationRevertPlan as DuplicateObjectReconciliationRevertPlan,
    _apply_duplicate_object_reconciliation_core as apply_duplicate_object_reconciliation,
    _apply_duplicate_object_reconciliation_revert_core as apply_duplicate_object_reconciliation_revert,
    _duplicate_object_reconciliation_context as duplicate_object_reconciliation_context,
    _duplicate_object_reconciliation_revert_context as duplicate_object_reconciliation_revert_context,
    _finalize_duplicate_object_reconciliation_revert_core as finalize_duplicate_object_reconciliation_revert,
    _plan_duplicate_object_reconciliation_core as plan_duplicate_object_reconciliation,
    _plan_duplicate_object_reconciliation_revert_core as _plan_duplicate_object_reconciliation_revert,
)
from wom_kit.exact_human_approval import (
    CLAIMS_RELATIVE_ROOT,
    _ClaimedExactHumanApproval as ClaimedExactHumanApproval,
    _audit_exact_human_approval_terminal_record_core,
    _claim_exact_human_approval_core as claim_exact_human_approval,
)
from wom_kit.exact_human_approval_windows import (
    APPROVE_BUTTON_ID,
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
    ExactHumanApprovalOperation,
)
from wom_kit.exact_human_approval_workflow import (
    ExactHumanApprovalWorkflowError,
    _execute_exact_human_approved_write_core as execute_exact_human_approved_write,
    _resume_exact_human_approved_transaction_core as resume_exact_human_approved_transaction,
)


AUTHENTICATION_KEY = bytes(range(32))
REVIEWER_CLAIM = "person:operator"


def _terminal_auditor(root: Path):
    def _audit(
        reference,
        expected_operation,
        expected_plan_sha256,
        expected_target_binding_sha256,
        allowed_statuses,
        expected_succeeded_evidence,
        payload,
        expected_mac,
    ):
        return _audit_exact_human_approval_terminal_record_core(
            root,
            reference,
            expected_operation=expected_operation,
            expected_plan_sha256=expected_plan_sha256,
            expected_target_binding_sha256=expected_target_binding_sha256,
            allowed_statuses=allowed_statuses,
            expected_succeeded_evidence_digests=(
                expected_succeeded_evidence
            ),
            payload=payload,
            expected_mac=expected_mac,
            receipt_authentication_key=memoryview(AUTHENTICATION_KEY),
        )

    return _audit


def plan_duplicate_object_reconciliation_revert(
    root: Path,
    *,
    terminal_auditor=None,
):
    return _plan_duplicate_object_reconciliation_revert(
        root,
        terminal_auditor=(terminal_auditor or _terminal_auditor(root)),
    )


class _Native:
    def __init__(self) -> None:
        self.calls = 0

    def show(self, **_kwargs: str) -> tuple[int, bool]:
        self.calls += 1
        return APPROVE_BUTTON_ID, True


class _KeyProvider:
    def use_key(
        self,
        _root: Path | str,
        consumer: Callable[[memoryview], Any],
        *,
        create_if_missing: bool = False,
    ) -> Any:
        del create_if_missing
        return consumer(memoryview(AUTHENTICATION_KEY))


def archive_snapshot(root: Path) -> tuple[tuple[str, ...], dict[str, str]]:
    directories = tuple(
        sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_dir()
        )
    )
    files = {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
    return directories, files


class DuplicateObjectReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text(
            "archive_id: archive:test\n", encoding="utf-8"
        )
        self.manifest = self.root / "objects" / "manifests" / "files.jsonl"
        self.manifest.parent.mkdir(parents=True)
        self.claims: list[ClaimedExactHumanApproval] = []

    def tearDown(self) -> None:
        for claim in self.claims:
            claim.close()
        self.temporary.cleanup()

    def row(self, digest: str, **overrides):
        document = {
            "object_id": f"sha256:{digest}",
            "sha256": digest,
            "logical_key": f"objects/sha256/{digest[:2]}/{digest}",
            "mime": "text/plain",
            "size_bytes": 5,
            "locations": [],
            "provenance": {"source": "test"},
        }
        document.update(overrides)
        return document

    def write_rows(self, *rows) -> bytes:
        raw = b"".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")
            + b"\n"
            for row in rows
        )
        self.manifest.write_bytes(raw)
        return raw

    def _rewrite_json(self, path: Path, mutate) -> None:
        document = json.loads(path.read_text(encoding="utf-8"))
        mutate(document)
        path.write_bytes(duplicate_module._canonical_bytes(document))

    def strict_pair(
        self,
        payload: bytes,
        *,
        store_kind: str = "private_store",
        canonical_mime: str = "text/plain",
        external_mime: str = "application/octet-stream",
        private_marker: str = "private-source-marker",
    ) -> tuple[dict, dict]:
        digest = hashlib.sha256(payload).hexdigest()
        canonical_key = f"objects/sha256/{digest[:2]}/{digest}"
        object_path = self.root.joinpath(*canonical_key.split("/"))
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(payload)
        canonical = self.row(
            digest,
            logical_key=canonical_key,
            mime=canonical_mime,
            size_bytes=len(payload),
            locations=[
                {
                    "provider": "local",
                    "path": canonical_key,
                    "availability": "available",
                }
            ],
            provenance={"source": "canonical-capture", "marker": private_marker},
        )
        external = self.row(
            digest,
            logical_key=(
                f"objects/external/prehashed/{store_kind}/{digest[:2]}/{digest}"
            ),
            mime=external_mime,
            size_bytes=len(payload),
            locations=[
                {
                    "provider": "external_prehashed",
                    "store_kind": store_kind,
                    "store_ref": private_marker,
                    "availability": "declared_external",
                }
            ],
            provenance={"source": "external-ledger", "marker": private_marker},
        )
        return canonical, external

    def claim(self, context, *, seed: int) -> ClaimedExactHumanApproval:
        decision = ExactHumanApprovalDecision(
            approved=True,
            synthetic_acknowledged=False,
            reason_code="exact_human_approval_approved",
            plan_sha256=context.plan_sha256,
            target_binding_sha256=context.target_binding_sha256,
        )
        claim = claim_exact_human_approval(
            self.root,
            context,
            decision,
            AUTHENTICATION_KEY,
            random_hex=lambda _size: f"{seed:032x}",
        )
        self.claims.append(claim)
        return claim

    def complete_revert(self, plan, context, *, seed: int):
        claim = self.claim(context, seed=seed)
        result = apply_duplicate_object_reconciliation_revert(
            plan,
            claim,
            context=context,
        )
        claim.finalize_succeeded()
        finalize_duplicate_object_reconciliation_revert(
            plan,
            claim,
            context=context,
        )
        return result, claim

    def ready_plan(self, digest: str = "e"):
        row = self.row(digest * 64)
        original = self.write_rows(row, row, self.row("f" * 64))
        plan = plan_duplicate_object_reconciliation(self.root)
        context = duplicate_object_reconciliation_context(
            plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        return original, plan, context

    def test_exact_rows_are_approveable_and_public_result_is_content_free(self) -> None:
        row = self.row("a" * 64)
        self.write_rows(row, row, self.row("b" * 64))
        plan = plan_duplicate_object_reconciliation(self.root)
        public = plan.public_document()
        self.assertTrue(public["ok"])
        self.assertEqual(public["removable_row_count"], 1)
        self.assertEqual(public["classification_counts"]["exact_byte_duplicate"], 1)
        serialized = json.dumps(public, sort_keys=True)
        self.assertNotIn("sha256:" + "a" * 64, serialized)
        self.assertNotIn(str(self.root), serialized)

    def test_compatible_evidence_is_not_auto_merged(self) -> None:
        digest = "c" * 64
        first = self.row(digest)
        second = self.row(digest, provenance={"source": "other"})
        self.write_rows(first, second)
        plan = plan_duplicate_object_reconciliation(self.root)
        self.assertFalse(plan.approveable)
        self.assertEqual(plan.compatible_group_count, 1)
        self.assertEqual(plan.removable_row_count, 0)

    def test_json_equal_rows_with_different_line_bytes_are_not_exact_duplicates(
        self,
    ) -> None:
        row = self.row("7" * 64)
        content = json.dumps(row, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        original = content + b"\n" + content + b"\r\n"
        self.manifest.write_bytes(original)

        plan = plan_duplicate_object_reconciliation(self.root)

        self.assertFalse(plan.approveable)
        self.assertEqual(plan.exact_group_count, 0)
        self.assertEqual(plan.compatible_group_count, 1)
        self.assertEqual(plan.exact_duplicate_row_group_count, 0)
        self.assertEqual(plan.removable_row_count, 0)
        self.assertEqual(plan._replacement_bytes, original)

    def test_conflicting_definition_is_blocked(self) -> None:
        digest = "d" * 64
        first = self.row(digest)
        second = self.row(digest, logical_key="objects/unsafe/conflict")
        self.write_rows(first, second)
        plan = plan_duplicate_object_reconciliation(self.root)
        self.assertFalse(plan.approveable)
        self.assertEqual(plan.conflicting_group_count, 1)
        context = duplicate_object_reconciliation_context(
            plan, reviewer_claim=REVIEWER_CLAIM
        )
        claim = self.claim(context, seed=1)
        before = archive_snapshot(self.root)

        with self.assertRaises(DuplicateObjectReconciliationError) as captured:
            apply_duplicate_object_reconciliation(plan, claim, context=context)

        self.assertEqual(
            captured.exception.code, "duplicate_object_human_resolution_required"
        )
        self.assertEqual(archive_snapshot(self.root), before)
        self.assertEqual(claim.status, "started")

    def test_exact_repair_preserves_snapshot_receipt_and_returned_reference(self) -> None:
        original, plan, context = self.ready_plan()
        self.assertIs(
            context.operation, ExactHumanApprovalOperation.duplicate_object_reconcile
        )
        claim = self.claim(context, seed=2)

        result = apply_duplicate_object_reconciliation(
            plan,
            claim,
            context=context,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(claim.status, "started")
        self.assertEqual(self.manifest.read_bytes().count(b"\n"), 2)
        snapshots = list(
            (self.root / "snapshots" / "objects" / "duplicate-reconciliation").glob(
                "*.manifest.bin"
            )
        )
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].read_bytes(), original)
        receipt_paths = list(
            (
                self.root
                / "receipts"
                / "objects"
                / "duplicate-reconciliation"
            ).glob("*.json")
        )
        journal_paths = list(
            (
                self.root
                / "journals"
                / "objects"
                / "duplicate-reconciliation"
            ).glob("*.json")
        )
        self.assertEqual(len(receipt_paths), 1)
        self.assertEqual(len(journal_paths), 1)
        receipt = json.loads(receipt_paths[0].read_text(encoding="utf-8"))
        journal = json.loads(journal_paths[0].read_text(encoding="utf-8"))
        self.assertEqual(receipt["approval_reference"], claim.public_reference())
        self.assertEqual(journal["approval_reference"], claim.public_reference())
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertNotIn("sha256:" + "e" * 64, json.dumps(result))

    def test_mixed_groups_remove_only_exact_rows_and_keep_unresolved_inventory(self) -> None:
        exact = self.row("a" * 64)
        compatible = self.row("b" * 64)
        compatible_distinct = self.row(
            "b" * 64,
            provenance={"source": "still-unresolved"},
        )
        conflicting = self.row("c" * 64)
        conflicting_distinct = self.row(
            "c" * 64,
            logical_key="objects/alternate/conflicting-definition",
        )

        def encoded(row: dict) -> bytes:
            return (
                json.dumps(row, sort_keys=False, separators=(",", ":"))
                .encode("utf-8")
                + b"\n"
            )

        exact_line = encoded(exact)
        compatible_line = encoded(compatible)
        compatible_distinct_line = encoded(compatible_distinct)
        conflicting_line = encoded(conflicting)
        conflicting_distinct_line = encoded(conflicting_distinct)
        original = b"".join(
            (
                exact_line,
                exact_line,
                compatible_line,
                compatible_line,
                compatible_distinct_line,
                conflicting_line,
                conflicting_line,
                conflicting_distinct_line,
            )
        )
        expected = b"".join(
            (
                exact_line,
                compatible_line,
                compatible_distinct_line,
                conflicting_line,
                conflicting_distinct_line,
            )
        )
        self.manifest.write_bytes(original)

        plan = plan_duplicate_object_reconciliation(self.root)
        public = plan.public_document()
        self.assertTrue(plan.approveable)
        self.assertEqual(plan.removable_row_count, 3)
        self.assertEqual(plan.exact_group_count, 1)
        self.assertEqual(plan.compatible_group_count, 1)
        self.assertEqual(plan.conflicting_group_count, 1)
        self.assertEqual(plan.exact_duplicate_row_group_count, 3)
        self.assertEqual(plan._replacement_bytes, expected)
        self.assertEqual(public["unresolved_group_count"], 2)
        self.assertTrue(public["human_resolution_still_required"])
        self.assertEqual(
            public["reason_code"],
            "duplicate_object_exact_reconciliation_ready_with_unresolved_groups",
        )
        self.assertEqual(
            public["next_safe_actions"],
            [
                "approve_exact_duplicate_row_reconciliation",
                "review_duplicate_object_evidence_without_mutation",
            ],
        )

        context = duplicate_object_reconciliation_context(
            plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        claim = self.claim(context, seed=9)
        result = apply_duplicate_object_reconciliation(
            plan,
            claim,
            context=context,
        )

        self.assertEqual(self.manifest.read_bytes(), expected)
        self.assertEqual(result["removed_exact_duplicate_row_count"], 3)
        self.assertEqual(result["compatible_group_count"], 1)
        self.assertEqual(result["conflicting_group_count"], 1)
        self.assertEqual(result["unresolved_group_count"], 2)
        self.assertTrue(result["human_resolution_still_required"])
        self.assertFalse(result["automatic_merge_performed"])
        self.assertFalse(result["unresolved_distinct_rows_modified"])
        self.assertEqual(
            result["reason_code"],
            "duplicate_object_exact_rows_removed_with_unresolved_groups",
        )

        snapshot_paths = list(
            (self.root / "snapshots" / "objects" / "duplicate-reconciliation").glob(
                "*.manifest.bin"
            )
        )
        receipt_paths = list(
            (
                self.root
                / "receipts"
                / "objects"
                / "duplicate-reconciliation"
            ).glob("*.json")
        )
        self.assertEqual(len(snapshot_paths), 1)
        self.assertEqual(snapshot_paths[0].read_bytes(), original)
        self.assertEqual(len(receipt_paths), 1)
        receipt = json.loads(receipt_paths[0].read_text(encoding="utf-8"))
        self.assertEqual(receipt["compatible_group_count"], 1)
        self.assertEqual(receipt["conflicting_group_count"], 1)
        self.assertEqual(receipt["unresolved_group_count"], 2)
        self.assertTrue(receipt["human_resolution_still_required"])
        self.assertFalse(receipt["automatic_merge_performed"])
        self.assertFalse(receipt["unresolved_distinct_rows_modified"])
        inventory = receipt["unresolved_inventory"]
        self.assertEqual(
            inventory["schema_version"],
            "wom-kit/duplicate-object-unresolved-inventory/v0.1",
        )
        self.assertEqual(inventory["unresolved_group_count"], 2)
        inventory_by_type = {
            item["classification"]: item
            for item in inventory["classification_groups"]
        }
        for classification in (
            "compatible_repeated_evidence",
            "conflicting_definition",
        ):
            with self.subTest(classification=classification):
                item = inventory_by_type[classification]
                self.assertEqual(item["group_count"], 1)
                self.assertEqual(item["row_count_before"], 3)
                self.assertEqual(
                    item["row_count_after_exact_deduplication"], 2
                )
                self.assertEqual(item["exact_duplicate_row_count_removed"], 1)

        public_and_receipt = json.dumps(
            {"public": public, "result": result, "receipt": receipt},
            sort_keys=True,
        )
        for private_value in (
            "sha256:" + "a" * 64,
            "sha256:" + "b" * 64,
            "sha256:" + "c" * 64,
            "objects/alternate/conflicting-definition",
            "still-unresolved",
            str(self.root),
        ):
            self.assertNotIn(private_value, public_and_receipt)

    def test_fake_mapping_subclass_and_wrong_context_block_with_zero_writes(self) -> None:
        _original, plan, context = self.ready_plan("1")
        before = archive_snapshot(self.root)
        fake_mapping = {
            "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
            "approval_id": "approval_" + "a" * 32,
            "context_sha256": "sha256:" + "b" * 64,
            "approval_authority_sha256": "sha256:" + "c" * 64,
            "one_use": True,
        }
        with self.assertRaises(DuplicateObjectReconciliationError) as mapping_error:
            apply_duplicate_object_reconciliation(
                plan,
                fake_mapping,  # type: ignore[arg-type]
                context=context,
            )
        self.assertEqual(
            mapping_error.exception.code,
            "duplicate_object_approval_required",
        )
        self.assertEqual(archive_snapshot(self.root), before)

        class ClaimSubclass(ClaimedExactHumanApproval):
            pass

        fake_subclass = object.__new__(ClaimSubclass)
        with self.assertRaises(DuplicateObjectReconciliationError) as subclass_error:
            apply_duplicate_object_reconciliation(
                plan,
                fake_subclass,
                context=context,
            )
        self.assertEqual(
            subclass_error.exception.code,
            "duplicate_object_approval_required",
        )
        self.assertEqual(archive_snapshot(self.root), before)

        claim = self.claim(context, seed=3)
        wrong_context = duplicate_object_reconciliation_context(
            plan,
            reviewer_claim="person:other-reviewer",
        )
        before_wrong_context = archive_snapshot(self.root)
        with self.assertRaises(DuplicateObjectReconciliationError) as context_error:
            apply_duplicate_object_reconciliation(
                plan,
                claim,
                context=wrong_context,
            )
        self.assertEqual(
            context_error.exception.code,
            "duplicate_object_approval_required",
        )
        self.assertEqual(archive_snapshot(self.root), before_wrong_context)
        self.assertEqual(claim.status, "started")

    def test_current_claim_tamper_blocks_before_first_mutation(self) -> None:
        _original, plan, context = self.ready_plan("2")
        claim = self.claim(context, seed=4)
        claim_path = self.root / CLAIMS_RELATIVE_ROOT / f"{claim.approval_id}.json"
        document = json.loads(claim_path.read_text(encoding="utf-8"))
        document["context"]["plan_sha256"] = "sha256:" + "9" * 64
        claim_path.write_text(json.dumps(document), encoding="utf-8")
        before = archive_snapshot(self.root)

        with self.assertRaises(DuplicateObjectReconciliationError) as captured:
            apply_duplicate_object_reconciliation(plan, claim, context=context)

        self.assertEqual(
            captured.exception.code,
            "duplicate_object_approval_required",
        )
        self.assertEqual(archive_snapshot(self.root), before)
        self.assertFalse((self.root / "snapshots").exists())
        self.assertFalse((self.root / "journals").exists())
        self.assertFalse((self.root / "receipts").exists())

    def test_manifest_change_blocks_with_valid_claim_and_zero_writes(self) -> None:
        original, plan, context = self.ready_plan("3")
        claim = self.claim(context, seed=5)
        self.manifest.write_bytes(original + b"\n")
        before = archive_snapshot(self.root)

        with self.assertRaises(DuplicateObjectReconciliationError) as captured:
            apply_duplicate_object_reconciliation(plan, claim, context=context)

        self.assertEqual(
            captured.exception.code,
            "duplicate_object_manifest_changed",
        )
        self.assertEqual(archive_snapshot(self.root), before)
        self.assertEqual(claim.status, "started")

    def test_writer_does_not_finalize_and_terminal_claim_cannot_replay(self) -> None:
        original, plan, context = self.ready_plan("4")
        claim = self.claim(context, seed=6)

        result = apply_duplicate_object_reconciliation(plan, claim, context=context)

        self.assertTrue(result["ok"])
        self.assertEqual(claim.status, "started")
        after_success = archive_snapshot(self.root)
        with self.assertRaises(DuplicateObjectReconciliationError) as stale:
            apply_duplicate_object_reconciliation(plan, claim, context=context)
        self.assertEqual(
            stale.exception.code,
            "duplicate_object_manifest_changed",
        )
        self.assertEqual(archive_snapshot(self.root), after_success)

        self.manifest.write_bytes(original)
        claim.finalize_succeeded()
        before_terminal_replay = archive_snapshot(self.root)
        with self.assertRaises(DuplicateObjectReconciliationError) as replay:
            apply_duplicate_object_reconciliation(plan, claim, context=context)
        self.assertEqual(
            replay.exception.code,
            "duplicate_object_approval_required",
        )
        self.assertEqual(archive_snapshot(self.root), before_terminal_replay)
        self.assertEqual(claim.status, "succeeded")

    def test_concurrent_same_plan_has_one_winner_and_preserves_winner_lock(self) -> None:
        _original, plan, context = self.ready_plan("5")
        claims = [self.claim(context, seed=7), self.claim(context, seed=8)]
        barrier = threading.Barrier(2)
        original_assert = ClaimedExactHumanApproval.assert_ready_for_context

        def gated_assert(claim, exact_context):
            reference = original_assert(claim, exact_context)
            barrier.wait(timeout=5)
            return reference

        def worker(index: int):
            try:
                return apply_duplicate_object_reconciliation(
                    plan,
                    claims[index],
                    context=context,
                )
            except BaseException as exc:
                return exc

        with mock.patch.object(
            ClaimedExactHumanApproval,
            "assert_ready_for_context",
            new=gated_assert,
        ):
            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(worker, (0, 1)))

        successes = [item for item in outcomes if isinstance(item, dict)]
        failures = [item for item in outcomes if isinstance(item, BaseException)]
        self.assertEqual(len(successes), 1, outcomes)
        self.assertEqual(len(failures), 1, outcomes)
        self.assertIsInstance(failures[0], DuplicateObjectReconciliationError)
        self.assertEqual(
            failures[0].code,
            "duplicate_object_reconciliation_conflict",
        )
        self.assertEqual([claim.status for claim in claims], ["started", "started"])
        lock_paths = list(
            (
                self.root
                / "profiles"
                / "local"
                / "duplicate-object-reconciliation"
                / "locks"
            ).glob("*.lock")
        )
        self.assertEqual(len(lock_paths), 1)
        self.assertEqual(
            len(
                list(
                    (
                        self.root
                        / "receipts"
                        / "objects"
                        / "duplicate-reconciliation"
                    ).glob("*.json")
                )
            ),
            1,
        )
        self.assertEqual(self.manifest.read_bytes().count(b"\n"), 2)

    def test_1149_strict_canonical_external_pairs_reconcile_losslessly(self) -> None:
        rows: list[dict] = []
        for index in range(1149):
            canonical, external = self.strict_pair(
                f"pair-{index}\n".encode("ascii"),
                private_marker=f"private-marker-{index}",
            )
            rows.extend((canonical, external))
        self.write_rows(*rows)
        plan = plan_duplicate_object_reconciliation(self.root)
        public = plan.public_document()

        self.assertTrue(plan.approveable)
        self.assertEqual(plan.canonical_external_pair_group_count, 1149)
        self.assertEqual(plan.exact_removable_row_count, 0)
        self.assertEqual(plan.conflicting_group_count, 0)
        self.assertEqual(public["unresolved_group_count"], 0)
        context = duplicate_object_reconciliation_context(
            plan, reviewer_claim=REVIEWER_CLAIM
        )
        claim = self.claim(context, seed=10)
        result = apply_duplicate_object_reconciliation(
            plan, claim, context=context
        )

        reconciled = [
            json.loads(line)
            for line in self.manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(reconciled), 1149)
        self.assertEqual(
            result["reconciled_canonical_external_pair_count"], 1149
        )
        self.assertEqual(
            result["reason_code"],
            "duplicate_object_reconciliation_succeeded",
        )
        self.assertEqual(result["removed_exact_duplicate_row_count"], 0)
        self.assertTrue(
            all(
                row["_wom_private_duplicate_reconciliation"]["schema_version"]
                == "wom-kit/private-canonical-external-object-reconciliation/v0.1"
                for row in reconciled
            )
        )
        public_serialized = json.dumps(
            {"plan": public, "result": result}, sort_keys=True
        )
        self.assertNotIn("private-marker-0", public_serialized)
        self.assertNotIn("objects/sha256/", public_serialized)

    def test_pair_keeps_canonical_definition_and_external_mime_provenance_losslessly(self) -> None:
        private_marker = f"{self.root}-private-provider-ref"
        canonical, external = self.strict_pair(
            b"same verified bytes",
            canonical_mime="text/plain",
            external_mime="application/x-private-format",
            private_marker=private_marker,
        )
        original = self.write_rows(canonical, external)
        source_lines = original.splitlines(keepends=True)
        plan = plan_duplicate_object_reconciliation(self.root)
        context = duplicate_object_reconciliation_context(
            plan, reviewer_claim=REVIEWER_CLAIM
        )
        result = apply_duplicate_object_reconciliation(
            plan, self.claim(context, seed=11), context=context
        )

        reconciled = json.loads(self.manifest.read_text(encoding="utf-8"))
        evidence = reconciled["_wom_private_duplicate_reconciliation"]
        self.assertEqual(reconciled["mime"], "text/plain")
        self.assertEqual(reconciled["provenance"], canonical["provenance"])
        self.assertEqual(len(reconciled["locations"]), 2)
        self.assertEqual(
            evidence["superseded_external_definition"], external
        )
        self.assertEqual(
            [item["row_sha256"] for item in evidence["source_rows"]],
            [
                "sha256:" + hashlib.sha256(source_lines[0]).hexdigest(),
                "sha256:" + hashlib.sha256(source_lines[1]).hexdigest(),
            ],
        )
        receipt_path = next(
            (
                self.root
                / "receipts"
                / "objects"
                / "duplicate-reconciliation"
            ).glob("*.json")
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        public_and_receipt = json.dumps(
            {"plan": plan.public_document(), "result": result, "receipt": receipt},
            sort_keys=True,
        )
        self.assertNotIn(private_marker, public_and_receipt)
        self.assertNotIn("application/x-private-format", public_and_receipt)
        self.assertNotIn(str(self.root), public_and_receipt)

    def test_local_hash_size_and_path_drift_block_before_writer_outputs(self) -> None:
        for drift in ("hash", "size", "path"):
            with self.subTest(drift=drift):
                canonical, external = self.strict_pair(
                    b"verified local payload", private_marker=f"private-{drift}"
                )
                self.write_rows(canonical, external)
                plan = plan_duplicate_object_reconciliation(self.root)
                context = duplicate_object_reconciliation_context(
                    plan, reviewer_claim=REVIEWER_CLAIM
                )
                claim = self.claim(context, seed={"hash": 12, "size": 13, "path": 14}[drift])
                object_path = self.root.joinpath(*canonical["logical_key"].split("/"))
                if drift == "hash":
                    original_payload = object_path.read_bytes()
                    object_path.write_bytes(
                        bytes((original_payload[0] ^ 1,)) + original_payload[1:]
                    )
                elif drift == "size":
                    object_path.write_bytes(b"verified local payload-extra")
                else:
                    object_path.unlink()
                before = archive_snapshot(self.root)

                with self.assertRaises(DuplicateObjectReconciliationError) as captured:
                    apply_duplicate_object_reconciliation(
                        plan, claim, context=context
                    )

                self.assertEqual(
                    captured.exception.code,
                    "duplicate_object_local_evidence_changed",
                )
                self.assertEqual(archive_snapshot(self.root), before)
                self.assertFalse((self.root / "snapshots").exists())
                self.assertFalse((self.root / "journals").exists())
                self.assertFalse((self.root / "receipts").exists())

    def test_strict_pair_repairs_without_touching_unrelated_conflict(self) -> None:
        canonical, external = self.strict_pair(b"verified pair")
        conflicting_a = self.row("9" * 64)
        conflicting_b = self.row(
            "9" * 64, logical_key="objects/alternate/unresolved"
        )
        self.write_rows(canonical, external, conflicting_a, conflicting_b)
        plan = plan_duplicate_object_reconciliation(self.root)
        self.assertEqual(plan.canonical_external_pair_group_count, 1)
        self.assertEqual(plan.conflicting_group_count, 1)
        context = duplicate_object_reconciliation_context(
            plan, reviewer_claim=REVIEWER_CLAIM
        )
        result = apply_duplicate_object_reconciliation(
            plan, self.claim(context, seed=15), context=context
        )

        records = [
            json.loads(line)
            for line in self.manifest.read_text(encoding="utf-8").splitlines()
        ]
        unresolved = [row for row in records if row["object_id"] == "sha256:" + "9" * 64]
        self.assertEqual(unresolved, [conflicting_a, conflicting_b])
        self.assertEqual(result["unresolved_group_count"], 1)
        self.assertTrue(result["human_resolution_still_required"])
        self.assertEqual(
            result["reason_code"],
            "duplicate_object_reconciliation_succeeded_with_unresolved_groups",
        )

    def test_apply_then_native_approved_revert_restores_exact_manifest_bytes(self) -> None:
        canonical, external = self.strict_pair(
            b"verified pair for exact revert", private_marker="private-revert"
        )
        original = self.write_rows(canonical, external, self.row("8" * 64))
        plan = plan_duplicate_object_reconciliation(self.root)
        context = duplicate_object_reconciliation_context(
            plan, reviewer_claim=REVIEWER_CLAIM
        )
        apply_duplicate_object_reconciliation(
            plan, self.claim(context, seed=16), context=context
        )
        post_state = self.manifest.read_bytes()
        self.assertNotEqual(post_state, original)

        revert_plan = plan_duplicate_object_reconciliation_revert(self.root)
        self.assertIsInstance(
            revert_plan, DuplicateObjectReconciliationRevertPlan
        )
        revert_context = duplicate_object_reconciliation_revert_context(
            revert_plan, reviewer_claim=REVIEWER_CLAIM
        )
        revert_result, _revert_claim = self.complete_revert(
            revert_plan,
            revert_context,
            seed=17,
        )

        self.assertEqual(self.manifest.read_bytes(), original)
        self.assertTrue(
            revert_result["restored_exact_original_manifest_bytes"]
        )
        post_snapshots = list(
            (
                self.root
                / "snapshots"
                / "objects"
                / "duplicate-reconciliation-revert"
            ).glob("*.post.manifest.bin")
        )
        self.assertEqual(len(post_snapshots), 1)
        self.assertEqual(post_snapshots[0].read_bytes(), post_state)
        revert_receipts = list(
            (
                self.root
                / "receipts"
                / "objects"
                / "duplicate-reconciliation-revert"
            ).glob("*.json")
        )
        self.assertEqual(len(revert_receipts), 1)
        serialized = json.dumps(
            {
                "plan": revert_plan.public_document(),
                "result": revert_result,
                "receipt": json.loads(revert_receipts[0].read_text(encoding="utf-8")),
            },
            sort_keys=True,
        )
        self.assertNotIn("private-revert", serialized)
        self.assertNotIn(str(self.root), serialized)

    def test_revert_discovery_fails_closed_on_ambiguous_or_corrupt_receipts(self) -> None:
        canonical, external = self.strict_pair(b"receipt discovery proof")
        self.write_rows(canonical, external)
        plan = plan_duplicate_object_reconciliation(self.root)
        context = duplicate_object_reconciliation_context(
            plan, reviewer_claim=REVIEWER_CLAIM
        )
        apply_duplicate_object_reconciliation(
            plan, self.claim(context, seed=18), context=context
        )
        receipt_directory = (
            self.root / "receipts" / "objects" / "duplicate-reconciliation"
        )
        source_receipt = next(receipt_directory.glob("*.json"))
        duplicate_receipt = receipt_directory / "second-valid-copy.json"
        duplicate_receipt.write_bytes(source_receipt.read_bytes())

        with self.assertRaises(DuplicateObjectReconciliationError) as ambiguous:
            plan_duplicate_object_reconciliation_revert(self.root)
        self.assertEqual(
            ambiguous.exception.code,
            "duplicate_object_revert_evidence_invalid",
        )
        duplicate_receipt.unlink()
        (receipt_directory / "corrupt.json").write_bytes(b'{"schema_version":')
        before = archive_snapshot(self.root)
        with self.assertRaises(DuplicateObjectReconciliationError) as corrupt:
            plan_duplicate_object_reconciliation_revert(self.root)
        self.assertEqual(
            corrupt.exception.code,
            "duplicate_object_revert_evidence_invalid",
        )
        self.assertEqual(archive_snapshot(self.root), before)

    def test_success_receipt_counts_cannot_be_rehashed_into_false_revert_evidence(
        self,
    ) -> None:
        canonical, external = self.strict_pair(b"successful count binding proof")
        self.write_rows(canonical, external)
        plan = plan_duplicate_object_reconciliation(self.root)
        context = duplicate_object_reconciliation_context(
            plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        apply_duplicate_object_reconciliation(
            plan,
            self.claim(context, seed=29),
            context=context,
        )
        receipt_path = next(
            (
                self.root
                / "receipts"
                / "objects"
                / "duplicate-reconciliation"
            ).glob("*.json")
        )
        journal_path = next(
            (
                self.root
                / "journals"
                / "objects"
                / "duplicate-reconciliation"
            ).glob("*.json")
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["removed_exact_duplicate_row_count"] = 777
        receipt_raw = duplicate_module._canonical_bytes(receipt)
        receipt_path.write_bytes(receipt_raw)
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["receipt_sha256"] = duplicate_module._sha256(receipt_raw)
        journal_path.write_bytes(duplicate_module._canonical_bytes(journal))
        before = archive_snapshot(self.root)

        with self.assertRaises(DuplicateObjectReconciliationError) as rejected:
            plan_duplicate_object_reconciliation_revert(self.root)

        self.assertEqual(
            rejected.exception.code,
            "duplicate_object_revert_evidence_invalid",
        )
        self.assertEqual(archive_snapshot(self.root), before)

    def test_revert_manifest_drift_and_reparse_snapshot_block_without_writes(self) -> None:
        canonical, external = self.strict_pair(b"revert drift proof")
        self.write_rows(canonical, external)
        plan = plan_duplicate_object_reconciliation(self.root)
        context = duplicate_object_reconciliation_context(
            plan, reviewer_claim=REVIEWER_CLAIM
        )
        apply_duplicate_object_reconciliation(
            plan, self.claim(context, seed=19), context=context
        )
        post_state = self.manifest.read_bytes()
        self.manifest.write_bytes(post_state + b"\n")
        drifted = archive_snapshot(self.root)

        with self.assertRaises(DuplicateObjectReconciliationError) as drift:
            plan_duplicate_object_reconciliation_revert(self.root)

        self.assertEqual(
            drift.exception.code,
            "duplicate_object_revert_candidate_missing",
        )
        self.assertEqual(archive_snapshot(self.root), drifted)

        self.manifest.write_bytes(post_state)
        snapshot_path = next(
            (
                self.root
                / "snapshots"
                / "objects"
                / "duplicate-reconciliation"
            ).glob("*.manifest.bin")
        )
        snapshot_inode = snapshot_path.stat().st_ino
        original_reparse_check = duplicate_module._is_reparse_point

        def simulated_reparse(value):
            return (
                int(value.st_ino) == int(snapshot_inode)
                or original_reparse_check(value)
            )

        before_reparse_plan = archive_snapshot(self.root)
        with (
            mock.patch.object(
                duplicate_module,
                "_is_reparse_point",
                side_effect=simulated_reparse,
            ),
            self.assertRaises(DuplicateObjectReconciliationError) as reparse,
        ):
            plan_duplicate_object_reconciliation_revert(self.root)

        self.assertEqual(
            reparse.exception.code,
            "duplicate_object_revert_evidence_invalid",
        )
        self.assertEqual(archive_snapshot(self.root), before_reparse_plan)

    def test_interrupted_after_manifest_replace_has_native_approved_exact_revert(
        self,
    ) -> None:
        original, plan, context = self.ready_plan("a")
        old_claim = self.claim(context, seed=20)
        real_atomic_replace = duplicate_module._atomic_replace

        def replace_manifest_then_fail(root: Path, path: Path, raw: bytes) -> None:
            real_atomic_replace(root, path, raw)
            if path.resolve() == self.manifest.resolve():
                raise OSError("simulated power loss after manifest replace")

        with (
            mock.patch.object(
                duplicate_module,
                "_atomic_replace",
                side_effect=replace_manifest_then_fail,
            ),
            self.assertRaises(DuplicateObjectReconciliationError) as interrupted,
        ):
            apply_duplicate_object_reconciliation(
                plan,
                old_claim,
                context=context,
            )

        self.assertEqual(
            interrupted.exception.code,
            "duplicate_object_reconciliation_state_unknown",
        )
        self.assertEqual(old_claim.status, "started")
        self.assertEqual(self.manifest.read_bytes(), plan._replacement_bytes)
        lock_path = next(
            (
                self.root
                / "profiles"
                / "local"
                / "duplicate-object-reconciliation"
                / "locks"
            ).glob("*.lock")
        )
        self.assertEqual(lock_path.read_bytes(), plan.plan_sha256.encode() + b"\n")

        revert_plan = plan_duplicate_object_reconciliation_revert(self.root)
        self.assertEqual(
            revert_plan.source_evidence_kind,
            "interrupted_started_journal",
        )
        revert_context = duplicate_object_reconciliation_revert_context(
            revert_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        result, _revert_claim = self.complete_revert(
            revert_plan,
            revert_context,
            seed=21,
        )

        self.assertEqual(self.manifest.read_bytes(), original)
        self.assertTrue(result["restored_exact_original_manifest_bytes"])
        self.assertFalse(
            result["interrupted_source_journal_finalized_rolled_back"]
        )
        source_journal = json.loads(
            next(
                (
                    self.root
                    / "journals"
                    / "objects"
                    / "duplicate-reconciliation"
                ).glob("*.json")
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(source_journal["status"], "started")

    def test_interrupted_after_receipt_publish_reverts_from_exact_receipt_bundle(
        self,
    ) -> None:
        original, plan, context = self.ready_plan("b")
        old_claim = self.claim(context, seed=22)
        real_create_only = duplicate_module._create_only

        def create_receipt_then_fail(root: Path, path: Path, raw: bytes) -> None:
            real_create_only(root, path, raw)
            if (
                "receipts/objects/duplicate-reconciliation/"
                in path.as_posix()
            ):
                raise OSError("simulated power loss after receipt publish")

        with (
            mock.patch.object(
                duplicate_module,
                "_create_only",
                side_effect=create_receipt_then_fail,
            ),
            self.assertRaises(DuplicateObjectReconciliationError) as interrupted,
        ):
            apply_duplicate_object_reconciliation(
                plan,
                old_claim,
                context=context,
            )

        self.assertEqual(
            interrupted.exception.code,
            "duplicate_object_reconciliation_state_unknown",
        )
        revert_plan = plan_duplicate_object_reconciliation_revert(self.root)
        self.assertEqual(
            revert_plan.source_evidence_kind,
            "interrupted_receipt_published",
        )
        self.assertIsNotNone(revert_plan.source_receipt_sha256)
        revert_context = duplicate_object_reconciliation_revert_context(
            revert_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        result, _revert_claim = self.complete_revert(
            revert_plan,
            revert_context,
            seed=23,
        )
        self.assertEqual(self.manifest.read_bytes(), original)
        self.assertEqual(
            result["source_evidence_kind"],
            "interrupted_receipt_published",
        )

    def test_interrupted_source_approval_tamper_blocks_before_revert_writes(
        self,
    ) -> None:
        _original, plan, context = self.ready_plan("c")
        old_claim = self.claim(context, seed=24)
        real_atomic_replace = duplicate_module._atomic_replace

        def replace_manifest_then_fail(root: Path, path: Path, raw: bytes) -> None:
            real_atomic_replace(root, path, raw)
            if path.resolve() == self.manifest.resolve():
                raise OSError("simulated interruption")

        with (
            mock.patch.object(
                duplicate_module,
                "_atomic_replace",
                side_effect=replace_manifest_then_fail,
            ),
            self.assertRaises(DuplicateObjectReconciliationError),
        ):
            apply_duplicate_object_reconciliation(
                plan,
                old_claim,
                context=context,
            )

        journal_path = next(
            (
                self.root
                / "journals"
                / "objects"
                / "duplicate-reconciliation"
            ).glob("*.json")
        )
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["approval_reference"]["approval_id"] = (
            "approval_" + "f" * 32
        )
        journal_path.write_bytes(duplicate_module._canonical_bytes(journal))
        revert_plan = plan_duplicate_object_reconciliation_revert(self.root)
        revert_context = duplicate_object_reconciliation_revert_context(
            revert_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        revert_claim = self.claim(revert_context, seed=25)
        before = archive_snapshot(self.root)

        with self.assertRaises(DuplicateObjectReconciliationError) as rejected:
            apply_duplicate_object_reconciliation_revert(
                revert_plan,
                revert_claim,
                context=revert_context,
            )

        self.assertEqual(
            rejected.exception.code,
            "duplicate_object_revert_evidence_invalid",
        )
        self.assertEqual(archive_snapshot(self.root), before)
        self.assertFalse(
            (
                self.root
                / "snapshots"
                / "objects"
                / "duplicate-reconciliation-revert"
            ).exists()
        )

    def test_forward_journal_finalize_after_effect_is_a_normal_revert_candidate(
        self,
    ) -> None:
        original, plan, context = self.ready_plan("d")
        old_claim = self.claim(context, seed=26)
        real_atomic_replace = duplicate_module._atomic_replace

        def finalize_journal_then_fail(root: Path, path: Path, raw: bytes) -> None:
            real_atomic_replace(root, path, raw)
            if (
                "journals/objects/duplicate-reconciliation/"
                in path.as_posix()
                and json.loads(raw)["status"] == "succeeded"
            ):
                raise OSError("simulated interruption after journal finalize")

        with (
            mock.patch.object(
                duplicate_module,
                "_atomic_replace",
                side_effect=finalize_journal_then_fail,
            ),
            self.assertRaises(DuplicateObjectReconciliationError) as interrupted,
        ):
            apply_duplicate_object_reconciliation(
                plan,
                old_claim,
                context=context,
            )

        self.assertEqual(
            interrupted.exception.code,
            "duplicate_object_reconciliation_state_unknown",
        )
        revert_plan = plan_duplicate_object_reconciliation_revert(self.root)
        self.assertEqual(revert_plan.source_evidence_kind, "successful_receipt")
        revert_context = duplicate_object_reconciliation_revert_context(
            revert_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        result, _revert_claim = self.complete_revert(
            revert_plan,
            revert_context,
            seed=27,
        )
        self.assertEqual(self.manifest.read_bytes(), original)
        self.assertFalse(
            result["interrupted_source_journal_finalized_rolled_back"]
        )

    def test_interruption_before_manifest_replace_never_creates_revert_candidate(
        self,
    ) -> None:
        original, plan, context = self.ready_plan("0")
        old_claim = self.claim(context, seed=28)
        real_create_only = duplicate_module._create_only

        def create_started_journal_then_fail(
            root: Path,
            path: Path,
            raw: bytes,
        ) -> None:
            real_create_only(root, path, raw)
            if (
                "journals/objects/duplicate-reconciliation/"
                in path.as_posix()
            ):
                raise OSError("simulated interruption before manifest replace")

        with (
            mock.patch.object(
                duplicate_module,
                "_create_only",
                side_effect=create_started_journal_then_fail,
            ),
            self.assertRaises(DuplicateObjectReconciliationError) as interrupted,
        ):
            apply_duplicate_object_reconciliation(
                plan,
                old_claim,
                context=context,
            )

        self.assertEqual(
            interrupted.exception.code,
            "duplicate_object_reconciliation_conflict",
        )
        self.assertEqual(self.manifest.read_bytes(), original)
        with self.assertRaises(DuplicateObjectReconciliationError) as absent:
            plan_duplicate_object_reconciliation_revert(self.root)
        self.assertEqual(
            absent.exception.code,
            "duplicate_object_revert_candidate_missing",
        )
        retried = apply_duplicate_object_reconciliation(
            plan,
            self.claim(context, seed=30),
            context=context,
        )
        self.assertTrue(retried["ok"], retried)
        self.assertEqual(self.manifest.read_bytes(), plan._replacement_bytes)

    def test_interruption_after_snapshot_create_is_adopted_by_exact_retry(
        self,
    ) -> None:
        original, plan, context = self.ready_plan("1")
        real_create_only = duplicate_module._create_only

        def create_snapshot_then_fail(root: Path, path: Path, raw: bytes) -> None:
            real_create_only(root, path, raw)
            if (
                "snapshots/objects/duplicate-reconciliation/"
                in path.as_posix()
                and path.name.endswith(".manifest.bin")
            ):
                raise OSError("simulated interruption after snapshot create")

        with (
            mock.patch.object(
                duplicate_module,
                "_create_only",
                side_effect=create_snapshot_then_fail,
            ),
            self.assertRaises(DuplicateObjectReconciliationError) as interrupted,
        ):
            apply_duplicate_object_reconciliation(
                plan,
                self.claim(context, seed=31),
                context=context,
            )

        self.assertEqual(
            interrupted.exception.code,
            "duplicate_object_reconciliation_conflict",
        )
        self.assertEqual(self.manifest.read_bytes(), original)
        retried = apply_duplicate_object_reconciliation(
            plan,
            self.claim(context, seed=32),
            context=context,
        )
        self.assertTrue(retried["ok"], retried)
        self.assertEqual(self.manifest.read_bytes(), plan._replacement_bytes)

    def test_forward_prewrite_retry_supersedes_old_approval_and_receipts_new_one(
        self,
    ) -> None:
        _original, plan, context = self.ready_plan("2")
        first_native = _Native()
        second_native = _Native()
        key_provider = _KeyProvider()
        real_create_only = duplicate_module._create_only

        def publish_journal_then_fail(root: Path, path: Path, raw: bytes) -> None:
            real_create_only(root, path, raw)
            if "journals/objects/duplicate-reconciliation/" in path.as_posix():
                raise OSError("simulated interruption after journal publish")

        with (
            mock.patch.object(
                duplicate_module,
                "_create_only",
                side_effect=publish_journal_then_fail,
            ),
            self.assertRaises(ExactHumanApprovalWorkflowError),
        ):
            execute_exact_human_approved_write(
                self.root,
                context,
                lambda claim: apply_duplicate_object_reconciliation(
                    plan, claim, context=context
                ),
                native=first_native,
                key_provider=key_provider,
            )

        result = execute_exact_human_approved_write(
            self.root,
            context,
            lambda claim: apply_duplicate_object_reconciliation(
                plan, claim, context=context
            ),
            native=second_native,
            key_provider=key_provider,
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(first_native.calls, 1)
        self.assertEqual(second_native.calls, 1)

        claim_documents = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (self.root / CLAIMS_RELATIVE_ROOT).glob("*.json")
        ]
        by_status = {
            document["status"]: document for document in claim_documents
        }
        self.assertEqual(set(by_status), {"started", "succeeded"})
        receipt = json.loads(
            next(
                (
                    self.root
                    / "receipts"
                    / "objects"
                    / "duplicate-reconciliation"
                ).glob("*.json")
            ).read_text(encoding="utf-8")
        )
        journal = json.loads(
            next(
                (
                    self.root
                    / "journals"
                    / "objects"
                    / "duplicate-reconciliation"
                ).glob("*.json")
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            receipt["approval_reference"]["approval_id"],
            by_status["succeeded"]["approval_id"],
        )
        self.assertNotEqual(
            receipt["approval_reference"]["approval_id"],
            by_status["started"]["approval_id"],
        )
        self.assertEqual(
            journal["approval_reference"], receipt["approval_reference"]
        )
        self.assertEqual(
            journal["approval_supersession"]["reason_code"],
            "interrupted_prewrite_approval_superseded",
        )

    def test_successful_superseded_forward_journal_tamper_fails_closed(
        self,
    ) -> None:
        _original, plan, context = self.ready_plan("f")
        real_create_only = duplicate_module._create_only

        def publish_started_journal_then_fail(
            root: Path, path: Path, raw: bytes
        ) -> None:
            real_create_only(root, path, raw)
            if "journals/objects/duplicate-reconciliation/" in path.as_posix():
                raise OSError("simulated prewrite interruption")

        with (
            mock.patch.object(
                duplicate_module,
                "_create_only",
                side_effect=publish_started_journal_then_fail,
            ),
            self.assertRaises(DuplicateObjectReconciliationError),
        ):
            apply_duplicate_object_reconciliation(
                plan,
                self.claim(context, seed=57),
                context=context,
            )
        result = apply_duplicate_object_reconciliation(
            plan,
            self.claim(context, seed=58),
            context=context,
        )
        self.assertTrue(result["ok"], result)

        journal_path = next(
            (
                self.root
                / "journals"
                / "objects"
                / "duplicate-reconciliation"
            ).glob("*.json")
        )
        for name, mutate in (
            (
                "reason_code",
                lambda journal: journal["approval_supersession"].update(
                    {"reason_code": "forged"}
                ),
            ),
            (
                "replacement_approval",
                lambda journal: journal["approval_supersession"].update(
                    {"replacement_approval_reference_sha256": "sha256:" + "0" * 64}
                ),
            ),
            (
                "superseded_journal_digest",
                lambda journal: journal["approval_supersession"].update(
                    {"superseded_journal_sha256": "sha256:" + "0" * 64}
                ),
            ),
            (
                "superseded_approval_digest",
                lambda journal: journal["approval_supersession"].update(
                    {
                        "superseded_approval_reference_sha256": (
                            "sha256:" + "0" * 64
                        )
                    }
                ),
            ),
            (
                "deleted_supersession",
                lambda journal: journal.pop("approval_supersession"),
            ),
        ):
            with self.subTest(tamper=name):
                copy_root = Path(self.temporary.name) / f"supersession-{name}"
                shutil.copytree(self.root, copy_root)
                copy_journal_path = copy_root / journal_path.relative_to(self.root)
                journal = json.loads(copy_journal_path.read_text(encoding="utf-8"))
                mutate(journal)
                copy_journal_path.write_bytes(duplicate_module._canonical_bytes(journal))
                before = archive_snapshot(copy_root)

                with self.assertRaises(DuplicateObjectReconciliationError) as rejected:
                    plan_duplicate_object_reconciliation_revert(copy_root)

                self.assertEqual(
                    rejected.exception.code,
                    "duplicate_object_revert_evidence_invalid",
                )
                self.assertEqual(archive_snapshot(copy_root), before)

    def test_nested_forward_superseded_approval_hmac_blocks_retry(
        self,
    ) -> None:
        _original, plan, context = self.ready_plan("d")
        real_create_only = duplicate_module._create_only

        def publish_journal_then_fail(
            root: Path, path: Path, raw: bytes
        ) -> None:
            real_create_only(root, path, raw)
            if "journals/objects/duplicate-reconciliation/" in path.as_posix():
                raise OSError("simulated initial journal interruption")

        with (
            mock.patch.object(
                duplicate_module,
                "_create_only",
                side_effect=publish_journal_then_fail,
            ),
            self.assertRaises(DuplicateObjectReconciliationError),
        ):
            apply_duplicate_object_reconciliation(
                plan, self.claim(context, seed=64), context=context
            )
        real_atomic_replace = duplicate_module._atomic_replace

        def fail_before_forward_replace(
            root: Path, path: Path, raw: bytes
        ) -> None:
            if path.resolve() == self.manifest.resolve():
                raise OSError("simulated second retry interruption")
            real_atomic_replace(root, path, raw)

        with (
            mock.patch.object(
                duplicate_module,
                "_atomic_replace",
                side_effect=fail_before_forward_replace,
            ),
            self.assertRaises(DuplicateObjectReconciliationError),
        ):
            apply_duplicate_object_reconciliation(
                plan, self.claim(context, seed=65), context=context
            )
        with (
            mock.patch.object(
                duplicate_module,
                "_atomic_replace",
                side_effect=fail_before_forward_replace,
            ),
            self.assertRaises(DuplicateObjectReconciliationError),
        ):
            apply_duplicate_object_reconciliation(
                plan, self.claim(context, seed=66), context=context
            )
        journal_path = next(
            (
                self.root
                / "journals"
                / "objects"
                / "duplicate-reconciliation"
            ).glob("*.json")
        )
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        supersession = journal["approval_supersession"]
        middle_journal = supersession["superseded_journal_evidence"][
            "journal"
        ]
        nested_supersession = middle_journal["approval_supersession"]
        superseded_journal = nested_supersession[
            "superseded_journal_evidence"
        ]["journal"]
        superseded_journal["approval_reference"]["approval_id"] = (
            "approval_" + "0" * 32
        )
        nested_supersession["superseded_approval_reference_sha256"] = (
            duplicate_module._sha256(
                duplicate_module._canonical_bytes(
                    superseded_journal["approval_reference"]
                )
            )
        )
        nested_supersession["superseded_journal_sha256"] = duplicate_module._sha256(
            duplicate_module._canonical_bytes(superseded_journal)
        )
        supersession["superseded_journal_sha256"] = duplicate_module._sha256(
            duplicate_module._canonical_bytes(middle_journal)
        )
        journal_path.write_bytes(duplicate_module._canonical_bytes(journal))
        retry_claim = self.claim(context, seed=77)
        before = archive_snapshot(self.root)

        with self.assertRaises(DuplicateObjectReconciliationError) as rejected:
            apply_duplicate_object_reconciliation(
                plan, retry_claim, context=context
            )

        self.assertEqual(
            rejected.exception.code,
            "duplicate_object_reconciliation_conflict",
        )
        self.assertEqual(archive_snapshot(self.root), before)

    def test_forward_supersession_depth_is_bounded(self) -> None:
        _original, plan, context = self.ready_plan("c")
        real_create_only = duplicate_module._create_only

        def publish_journal_then_fail(
            root: Path, path: Path, raw: bytes
        ) -> None:
            real_create_only(root, path, raw)
            if "journals/objects/duplicate-reconciliation/" in path.as_posix():
                raise OSError("simulated initial journal interruption")

        with (
            mock.patch.object(
                duplicate_module,
                "_create_only",
                side_effect=publish_journal_then_fail,
            ),
            self.assertRaises(DuplicateObjectReconciliationError),
        ):
            apply_duplicate_object_reconciliation(
                plan, self.claim(context, seed=67), context=context
            )
        real_atomic_replace = duplicate_module._atomic_replace

        def fail_before_forward_replace(
            root: Path, path: Path, raw: bytes
        ) -> None:
            if path.resolve() == self.manifest.resolve():
                raise OSError("simulated retry interruption")
            real_atomic_replace(root, path, raw)

        for seed in range(68, 68 + duplicate_module._MAX_APPROVAL_SUPERSESSION_DEPTH):
            with (
                mock.patch.object(
                    duplicate_module,
                    "_atomic_replace",
                    side_effect=fail_before_forward_replace,
                ),
                self.assertRaises(DuplicateObjectReconciliationError),
            ):
                apply_duplicate_object_reconciliation(
                    plan, self.claim(context, seed=seed), context=context
                )
        overflow_claim = self.claim(context, seed=76)
        before = archive_snapshot(self.root)
        with self.assertRaises(DuplicateObjectReconciliationError) as rejected:
            apply_duplicate_object_reconciliation(
                plan, overflow_claim, context=context
            )

        self.assertEqual(
            rejected.exception.code,
            "duplicate_object_reconciliation_conflict",
        )
        self.assertEqual(archive_snapshot(self.root), before)

    def _ready_successful_revert(self, digest: str, *, seed: int):
        original, plan, context = self.ready_plan(digest)
        apply_duplicate_object_reconciliation(
            plan,
            self.claim(context, seed=seed),
            context=context,
        )
        revert_plan = plan_duplicate_object_reconciliation_revert(self.root)
        revert_context = duplicate_object_reconciliation_revert_context(
            revert_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        return original, revert_plan, revert_context

    def _completed_interrupted_forward_revert(
        self,
        digest: str,
        *,
        seed: int,
    ) -> tuple[
        bytes,
        DuplicateObjectReconciliationPlan,
        Path,
        Callable[..., bool],
    ]:
        original, forward_plan, forward_context = self.ready_plan(digest)
        real_atomic_replace = duplicate_module._atomic_replace

        def replace_forward_manifest_then_fail(
            root: Path, path: Path, raw: bytes
        ) -> None:
            real_atomic_replace(root, path, raw)
            if path.resolve() == self.manifest.resolve():
                raise OSError("simulated forward replace after-effect")

        with (
            mock.patch.object(
                duplicate_module,
                "_atomic_replace",
                side_effect=replace_forward_manifest_then_fail,
            ),
            self.assertRaises(ExactHumanApprovalWorkflowError) as interrupted,
        ):
            execute_exact_human_approved_write(
                self.root,
                forward_context,
                lambda claim: apply_duplicate_object_reconciliation(
                    forward_plan,
                    claim,
                    context=forward_context,
                ),
                native=_Native(),
                key_provider=_KeyProvider(),
            )
        self.assertEqual(
            interrupted.exception.code,
            "exact_human_approval_state_unknown",
        )
        self.assertEqual(
            self.manifest.read_bytes(), forward_plan._replacement_bytes
        )

        revert_plan = plan_duplicate_object_reconciliation_revert(self.root)
        self.assertEqual(
            revert_plan.source_evidence_kind,
            "interrupted_started_journal",
        )
        revert_context = duplicate_object_reconciliation_revert_context(
            revert_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        completed = execute_exact_human_approved_write(
            self.root,
            revert_context,
            lambda claim: apply_duplicate_object_reconciliation_revert(
                revert_plan,
                claim,
                context=revert_context,
            ),
            claim_succeeded_finalizer=lambda claim: (
                finalize_duplicate_object_reconciliation_revert(
                    revert_plan,
                    claim,
                    context=revert_context,
                )
            ),
            native=_Native(),
            key_provider=_KeyProvider(),
        )
        self.assertTrue(completed["ok"], completed)
        self.assertEqual(self.manifest.read_bytes(), original)

        marker_path = duplicate_module._terminal_compensation_path(
            self.root, forward_plan.plan_sha256
        )
        self.assertTrue(marker_path.is_file())
        auditor_claim = self.claim(revert_context, seed=seed)
        terminal_auditor = duplicate_module._claim_terminal_auditor(
            auditor_claim
        )
        return original, forward_plan, marker_path, terminal_auditor

    def _assert_same_forward_plan_is_read_only_blocked(
        self,
        root: Path,
        forward_plan: DuplicateObjectReconciliationPlan,
        *,
        seed: int,
    ) -> None:
        before = archive_snapshot(root)
        with self.assertRaises(DuplicateObjectReconciliationError) as rejected:
            plan_duplicate_object_reconciliation(root)
        self.assertEqual(
            rejected.exception.code,
            "duplicate_object_reconciliation_conflict",
        )
        self.assertEqual(archive_snapshot(root), before)

        context = duplicate_object_reconciliation_context(
            forward_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        claim = self.claim(context, seed=seed)
        before_apply = archive_snapshot(root)
        with self.assertRaises(DuplicateObjectReconciliationError) as replay:
            apply_duplicate_object_reconciliation(
                forward_plan,
                claim,
                context=context,
            )
        self.assertEqual(
            replay.exception.code,
            "duplicate_object_reconciliation_conflict",
        )
        self.assertEqual(archive_snapshot(root), before_apply)

    def _assert_completed_revert_remains_terminal(
        self,
        root: Path,
        terminal_auditor: Callable[..., bool],
    ) -> None:
        before = archive_snapshot(root)
        with self.assertRaises(DuplicateObjectReconciliationError) as absent:
            plan_duplicate_object_reconciliation_revert(
                root,
                terminal_auditor=terminal_auditor,
            )
        self.assertEqual(
            absent.exception.code,
            "duplicate_object_revert_candidate_missing",
        )
        self.assertEqual(archive_snapshot(root), before)

    def test_terminal_compensation_marker_blocks_same_forward_replay(self) -> None:
        _original, forward_plan, _marker_path, terminal_auditor = (
            self._completed_interrupted_forward_revert("c", seed=90)
        )

        self._assert_same_forward_plan_is_read_only_blocked(
            self.root, forward_plan, seed=92
        )
        self._assert_completed_revert_remains_terminal(
            self.root, terminal_auditor
        )

    def test_deleted_terminal_marker_uses_completed_revert_history_to_block(
        self,
    ) -> None:
        _original, forward_plan, marker_path, terminal_auditor = (
            self._completed_interrupted_forward_revert("d", seed=94)
        )
        marker_path.unlink()

        self._assert_same_forward_plan_is_read_only_blocked(
            self.root, forward_plan, seed=96
        )
        self.assertFalse(marker_path.exists())
        self._assert_completed_revert_remains_terminal(
            self.root, terminal_auditor
        )

    def test_tampered_terminal_marker_blocks_without_damaging_revert_history(
        self,
    ) -> None:
        _original, forward_plan, marker_path, terminal_auditor = (
            self._completed_interrupted_forward_revert("e", seed=98)
        )
        marker_path.write_bytes(marker_path.read_bytes() + b" ")

        self._assert_same_forward_plan_is_read_only_blocked(
            self.root, forward_plan, seed=100
        )
        self._assert_completed_revert_remains_terminal(
            self.root, terminal_auditor
        )

    def test_revert_manifest_restore_after_effect_converges(self) -> None:
        original, plan, context = self._ready_successful_revert("3", seed=40)
        real_atomic_replace = duplicate_module._atomic_replace

        def restore_then_fail(root: Path, path: Path, raw: bytes) -> None:
            real_atomic_replace(root, path, raw)
            if path.resolve() == self.manifest.resolve():
                raise OSError("simulated restore after-effect")

        revert_claim = self.claim(context, seed=41)
        with mock.patch.object(
            duplicate_module,
            "_atomic_replace",
            side_effect=restore_then_fail,
        ):
            result = apply_duplicate_object_reconciliation_revert(
                plan,
                revert_claim,
                context=context,
            )
        revert_claim.finalize_succeeded()
        finalize_duplicate_object_reconciliation_revert(
            plan, revert_claim, context=context
        )
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["manifest_write_performed_this_run"])
        self.assertEqual(self.manifest.read_bytes(), original)

    def test_revert_receipt_publish_after_effect_converges(self) -> None:
        original, plan, context = self._ready_successful_revert("4", seed=42)
        real_create_only = duplicate_module._create_only

        def receipt_then_fail(root: Path, path: Path, raw: bytes) -> None:
            real_create_only(root, path, raw)
            if "duplicate-reconciliation-revert" in path.as_posix() and (
                "/receipts/" in "/" + path.as_posix()
            ):
                raise OSError("simulated receipt after-effect")

        revert_claim = self.claim(context, seed=43)
        with mock.patch.object(
            duplicate_module,
            "_create_only",
            side_effect=receipt_then_fail,
        ):
            result = apply_duplicate_object_reconciliation_revert(
                plan,
                revert_claim,
                context=context,
            )
        revert_claim.finalize_succeeded()
        finalize_duplicate_object_reconciliation_revert(
            plan, revert_claim, context=context
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.manifest.read_bytes(), original)

    def test_revert_journal_finalize_after_effect_converges(self) -> None:
        original, plan, context = self._ready_successful_revert("5", seed=44)
        real_atomic_replace = duplicate_module._atomic_replace

        def finalize_then_fail(root: Path, path: Path, raw: bytes) -> None:
            real_atomic_replace(root, path, raw)
            if (
                "journals/objects/duplicate-reconciliation-revert/"
                in path.as_posix()
                and json.loads(raw)["status"] == "succeeded"
            ):
                raise OSError("simulated journal-finalize after-effect")

        revert_claim = self.claim(context, seed=45)
        result = apply_duplicate_object_reconciliation_revert(
            plan,
            revert_claim,
            context=context,
        )
        revert_claim.finalize_succeeded()
        with mock.patch.object(
            duplicate_module,
            "_atomic_replace",
            side_effect=finalize_then_fail,
        ):
            finalize_duplicate_object_reconciliation_revert(
                plan, revert_claim, context=context
            )
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.manifest.read_bytes(), original)

    def test_revert_pre_state_is_discovered_and_finalized_without_second_write(
        self,
    ) -> None:
        original, plan, context = self._ready_successful_revert("6", seed=46)
        first_revert_claim = self.claim(context, seed=47)
        real_create_only = duplicate_module._create_only

        def fail_before_revert_receipt(
            root: Path, path: Path, raw: bytes
        ) -> None:
            if (
                "receipts/objects/duplicate-reconciliation-revert/"
                in path.as_posix()
            ):
                raise OSError("simulated power loss before revert receipt")
            real_create_only(root, path, raw)

        with (
            mock.patch.object(
                duplicate_module,
                "_create_only",
                side_effect=fail_before_revert_receipt,
            ),
            self.assertRaises(DuplicateObjectReconciliationError) as interrupted,
        ):
            apply_duplicate_object_reconciliation_revert(
                plan,
                first_revert_claim,
                context=context,
            )
        self.assertEqual(
            interrupted.exception.code,
            "duplicate_object_revert_state_unknown",
        )
        self.assertEqual(self.manifest.read_bytes(), original)

        resumed_plan = plan_duplicate_object_reconciliation_revert(self.root)
        self.assertEqual(resumed_plan.plan_sha256, plan.plan_sha256)
        resumed_context = duplicate_object_reconciliation_revert_context(
            resumed_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        result = apply_duplicate_object_reconciliation_revert(
            resumed_plan,
            first_revert_claim,
            context=resumed_context,
        )
        first_revert_claim.finalize_succeeded()
        finalize_duplicate_object_reconciliation_revert(
            resumed_plan,
            first_revert_claim,
            context=resumed_context,
        )
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["finalize_only"])
        self.assertFalse(result["manifest_write_performed_this_run"])
        self.assertEqual(self.manifest.read_bytes(), original)

        receipt = json.loads(
            next(
                (
                    self.root
                    / "receipts"
                    / "objects"
                    / "duplicate-reconciliation-revert"
                ).glob("*.json")
            ).read_text(encoding="utf-8")
        )
        journal = json.loads(
            next(
                (
                    self.root
                    / "journals"
                    / "objects"
                    / "duplicate-reconciliation-revert"
                ).glob("*.json")
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            receipt["approval_reference"], first_revert_claim.public_reference()
        )
        self.assertEqual(
            journal["finalization_approval_reference"],
            first_revert_claim.public_reference(),
        )

    def test_interrupted_forward_revert_pre_state_resumes_from_source_journal(
        self,
    ) -> None:
        original, forward_plan, forward_context = self.ready_plan("9")
        forward_claim = self.claim(forward_context, seed=54)
        real_atomic_replace = duplicate_module._atomic_replace

        def replace_forward_manifest_then_fail(
            root: Path, path: Path, raw: bytes
        ) -> None:
            real_atomic_replace(root, path, raw)
            if path.resolve() == self.manifest.resolve():
                raise OSError("simulated forward replace after-effect")

        with (
            mock.patch.object(
                duplicate_module,
                "_atomic_replace",
                side_effect=replace_forward_manifest_then_fail,
            ),
            self.assertRaises(DuplicateObjectReconciliationError) as forward,
        ):
            apply_duplicate_object_reconciliation(
                forward_plan,
                forward_claim,
                context=forward_context,
            )
        self.assertEqual(
            forward.exception.code,
            "duplicate_object_reconciliation_state_unknown",
        )
        self.assertEqual(forward_claim.status, "started")
        self.assertEqual(
            self.manifest.read_bytes(), forward_plan._replacement_bytes
        )

        revert_plan = plan_duplicate_object_reconciliation_revert(self.root)
        self.assertEqual(
            revert_plan.source_evidence_kind,
            "interrupted_started_journal",
        )
        revert_context = duplicate_object_reconciliation_revert_context(
            revert_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        first_revert_claim = self.claim(revert_context, seed=55)
        real_create_only = duplicate_module._create_only

        def fail_before_revert_receipt(
            root: Path, path: Path, raw: bytes
        ) -> None:
            if (
                "receipts/objects/duplicate-reconciliation-revert/"
                in path.as_posix()
            ):
                raise OSError("simulated power loss before revert receipt")
            real_create_only(root, path, raw)

        with (
            mock.patch.object(
                duplicate_module,
                "_create_only",
                side_effect=fail_before_revert_receipt,
            ),
            self.assertRaises(DuplicateObjectReconciliationError) as revert,
        ):
            apply_duplicate_object_reconciliation_revert(
                revert_plan,
                first_revert_claim,
                context=revert_context,
            )
        self.assertEqual(
            revert.exception.code,
            "duplicate_object_revert_state_unknown",
        )
        self.assertEqual(self.manifest.read_bytes(), original)
        source_receipt_root = (
            self.root / "receipts" / "objects" / "duplicate-reconciliation"
        )
        self.assertFalse(
            source_receipt_root.exists()
            and any(source_receipt_root.glob("*.json"))
        )

        resumed_plan = plan_duplicate_object_reconciliation_revert(self.root)
        self.assertEqual(resumed_plan.plan_sha256, revert_plan.plan_sha256)
        self.assertEqual(
            resumed_plan.source_evidence_kind,
            "interrupted_started_journal",
        )
        resumed_context = duplicate_object_reconciliation_revert_context(
            resumed_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        manifest_writes = 0

        def count_manifest_writes(
            root: Path, path: Path, raw: bytes
        ) -> None:
            nonlocal manifest_writes
            if path.resolve() == self.manifest.resolve():
                manifest_writes += 1
            real_atomic_replace(root, path, raw)

        with mock.patch.object(
            duplicate_module,
            "_atomic_replace",
            side_effect=count_manifest_writes,
        ):
            result = apply_duplicate_object_reconciliation_revert(
                resumed_plan,
                first_revert_claim,
                context=resumed_context,
            )
        first_revert_claim.finalize_succeeded()
        finalize_duplicate_object_reconciliation_revert(
            resumed_plan,
            first_revert_claim,
            context=resumed_context,
        )
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["finalize_only"])
        self.assertFalse(result["manifest_write_performed_this_run"])
        self.assertEqual(manifest_writes, 0)
        self.assertEqual(self.manifest.read_bytes(), original)

        receipt = json.loads(
            next(
                (
                    self.root
                    / "receipts"
                    / "objects"
                    / "duplicate-reconciliation-revert"
                ).glob("*.json")
            ).read_text(encoding="utf-8")
        )
        journal = json.loads(
            next(
                (
                    self.root
                    / "journals"
                    / "objects"
                    / "duplicate-reconciliation-revert"
                ).glob("*.json")
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            receipt["approval_reference"],
            first_revert_claim.public_reference(),
        )
        self.assertEqual(
            journal["finalization_approval_reference"],
            first_revert_claim.public_reference(),
        )

    def test_interrupted_forward_revert_pre_state_source_evidence_fails_closed(
        self,
    ) -> None:
        original, forward_plan, forward_context = self.ready_plan("e")
        real_atomic_replace = duplicate_module._atomic_replace

        def replace_forward_manifest_then_fail(
            root: Path, path: Path, raw: bytes
        ) -> None:
            real_atomic_replace(root, path, raw)
            if path.resolve() == self.manifest.resolve():
                raise OSError("simulated forward replace after-effect")

        with (
            mock.patch.object(
                duplicate_module,
                "_atomic_replace",
                side_effect=replace_forward_manifest_then_fail,
            ),
            self.assertRaises(DuplicateObjectReconciliationError),
        ):
            apply_duplicate_object_reconciliation(
                forward_plan,
                self.claim(forward_context, seed=59),
                context=forward_context,
            )
        revert_plan = plan_duplicate_object_reconciliation_revert(self.root)
        revert_context = duplicate_object_reconciliation_revert_context(
            revert_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        real_create_only = duplicate_module._create_only

        def fail_before_revert_receipt(
            root: Path, path: Path, raw: bytes
        ) -> None:
            if "receipts/objects/duplicate-reconciliation-revert/" in path.as_posix():
                raise OSError("simulated power loss before revert receipt")
            real_create_only(root, path, raw)

        with (
            mock.patch.object(
                duplicate_module,
                "_create_only",
                side_effect=fail_before_revert_receipt,
            ),
            self.assertRaises(DuplicateObjectReconciliationError),
        ):
            apply_duplicate_object_reconciliation_revert(
                revert_plan,
                self.claim(revert_context, seed=60),
                context=revert_context,
            )
        self.assertEqual(self.manifest.read_bytes(), original)
        source_journal_path = next(
            (
                self.root
                / "journals"
                / "objects"
                / "duplicate-reconciliation"
            ).glob("*.json")
        )
        for name, mutate in (
            (
                "tamper",
                lambda path: path.write_bytes(path.read_bytes() + b" "),
            ),
            ("orphan", lambda path: path.unlink()),
        ):
            with self.subTest(source_evidence=name):
                copy_root = Path(self.temporary.name) / f"source-{name}"
                shutil.copytree(self.root, copy_root)
                mutate(copy_root / source_journal_path.relative_to(self.root))
                before = archive_snapshot(copy_root)

                with self.assertRaises(DuplicateObjectReconciliationError) as rejected:
                    plan_duplicate_object_reconciliation_revert(copy_root)

                self.assertEqual(
                    rejected.exception.code,
                    "duplicate_object_revert_evidence_invalid",
                )
                self.assertEqual(archive_snapshot(copy_root), before)

    def test_revert_supersession_evidence_and_receipt_tamper_fail_closed(
        self,
    ) -> None:
        _original, plan, context = self._ready_successful_revert("a", seed=78)
        real_create_or_exact = duplicate_module._create_or_exact_revert_file

        def publish_revert_journal_then_fail(
            root: Path, path: Path, raw: bytes, *, maximum_bytes: int
        ) -> None:
            real_create_or_exact(
                root, path, raw, maximum_bytes=maximum_bytes
            )
            if "journals/objects/duplicate-reconciliation-revert/" in path.as_posix():
                raise OSError("simulated initial revert journal interruption")

        with (
            mock.patch.object(
                duplicate_module,
                "_create_or_exact_revert_file",
                side_effect=publish_revert_journal_then_fail,
            ),
            self.assertRaises(DuplicateObjectReconciliationError),
        ):
            apply_duplicate_object_reconciliation_revert(
                plan, self.claim(context, seed=79), context=context
            )
        real_atomic_replace = duplicate_module._atomic_replace

        def fail_before_revert_restore(
            root: Path, path: Path, raw: bytes
        ) -> None:
            if path.resolve() == self.manifest.resolve():
                raise OSError("simulated revert retry interruption")
            real_atomic_replace(root, path, raw)

        with (
            mock.patch.object(
                duplicate_module,
                "_atomic_replace",
                side_effect=fail_before_revert_restore,
            ),
            self.assertRaises(DuplicateObjectReconciliationError),
        ):
            apply_duplicate_object_reconciliation_revert(
                plan, self.claim(context, seed=80), context=context
            )
        journal_path = next(
            (
                self.root
                / "journals"
                / "objects"
                / "duplicate-reconciliation-revert"
            ).glob("*.json")
        )
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        supersession = journal["approval_supersession"]
        superseded_journal = supersession["superseded_journal_evidence"][
            "journal"
        ]
        superseded_journal["approval_reference"]["approval_id"] = (
            "approval_" + "0" * 32
        )
        supersession["superseded_approval_reference_sha256"] = (
            duplicate_module._sha256(
                duplicate_module._canonical_bytes(
                    superseded_journal["approval_reference"]
                )
            )
        )
        supersession["superseded_journal_sha256"] = duplicate_module._sha256(
            duplicate_module._canonical_bytes(superseded_journal)
        )
        journal_path.write_bytes(duplicate_module._canonical_bytes(journal))
        retry_claim = self.claim(context, seed=81)
        before = archive_snapshot(self.root)

        with self.assertRaises(DuplicateObjectReconciliationError) as rejected:
            apply_duplicate_object_reconciliation_revert(
                plan, retry_claim, context=context
            )

        self.assertEqual(
            rejected.exception.code,
            "duplicate_object_revert_evidence_invalid",
        )
        self.assertEqual(archive_snapshot(self.root), before)

    def test_revert_partial_evidence_tamper_fails_closed(self) -> None:
        _original, plan, context = self._ready_successful_revert("7", seed=49)
        real_replace_or_exact = duplicate_module._replace_or_exact_revert_file

        def stop_before_final_journal(
            root: Path,
            path: Path,
            raw: bytes,
            *,
            maximum_bytes: int,
        ) -> None:
            if (
                "journals/objects/duplicate-reconciliation-revert/"
                in path.as_posix()
                and json.loads(raw)["status"] == "succeeded"
            ):
                raise DuplicateObjectReconciliationError(
                    "duplicate_object_revert_state_unknown"
                )
            real_replace_or_exact(
                root,
                path,
                raw,
                maximum_bytes=maximum_bytes,
            )

        finalization_claim = self.claim(context, seed=50)
        apply_duplicate_object_reconciliation_revert(
            plan,
            finalization_claim,
            context=context,
        )
        finalization_claim.finalize_succeeded()
        with (
            mock.patch.object(
                duplicate_module,
                "_replace_or_exact_revert_file",
                side_effect=stop_before_final_journal,
            ),
            self.assertRaises(DuplicateObjectReconciliationError),
        ):
            finalize_duplicate_object_reconciliation_revert(
                plan,
                finalization_claim,
                context=context,
            )

        relative_targets = {
            "lock": next(
                (self.root / "profiles/local/duplicate-object-reconciliation/revert-locks").glob("*.lock")
            ).relative_to(self.root),
            "snapshot": next(
                (self.root / "snapshots/objects/duplicate-reconciliation-revert").glob("*.bin")
            ).relative_to(self.root),
            "journal": next(
                (self.root / "journals/objects/duplicate-reconciliation-revert").glob("*.json")
            ).relative_to(self.root),
            "receipt": next(
                (self.root / "receipts/objects/duplicate-reconciliation-revert").glob("*.json")
            ).relative_to(self.root),
        }
        for name, relative in relative_targets.items():
            with self.subTest(evidence=name):
                copy_root = Path(self.temporary.name) / f"tamper-{name}"
                shutil.copytree(self.root, copy_root)
                target = copy_root / relative
                target.write_bytes(target.read_bytes() + b"tamper")
                before = archive_snapshot(copy_root)
                with self.assertRaises(
                    DuplicateObjectReconciliationError
                ) as rejected:
                    plan_duplicate_object_reconciliation_revert(copy_root)
                self.assertEqual(
                    rejected.exception.code,
                    "duplicate_object_revert_evidence_invalid",
                )
                self.assertEqual(archive_snapshot(copy_root), before)

    def test_historical_completed_revert_does_not_block_a_new_exact_candidate(
        self,
    ) -> None:
        _original, first_plan, first_context = self._ready_successful_revert(
            "8", seed=51
        )
        first_result, _first_revert_claim = self.complete_revert(
            first_plan,
            first_context,
            seed=52,
        )
        self.assertTrue(first_result["ok"], first_result)

        next_row = self.row("9" * 64)
        self.write_rows(next_row, next_row, self.row("a" * 64))
        next_plan = plan_duplicate_object_reconciliation(self.root)
        next_context = duplicate_object_reconciliation_context(
            next_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        apply_duplicate_object_reconciliation(
            next_plan,
            self.claim(next_context, seed=53),
            context=next_context,
        )

        discovered = plan_duplicate_object_reconciliation_revert(self.root)
        self.assertNotEqual(discovered.plan_sha256, first_plan.plan_sha256)
        self.assertEqual(
            discovered.manifest_current_sha256,
            duplicate_module._sha256(next_plan._replacement_bytes),
        )

    def test_terminally_compensated_source_history_does_not_block_new_revert(
        self,
    ) -> None:
        (
            _old_original,
            old_forward_plan,
            compensation_marker,
            _old_terminal_auditor,
        ) = self._completed_interrupted_forward_revert("a", seed=117)
        self.assertTrue(compensation_marker.is_file())

        new_original, new_forward_plan, new_forward_context = self.ready_plan(
            "b"
        )
        self.assertNotEqual(
            old_forward_plan.plan_sha256,
            new_forward_plan.plan_sha256,
        )
        applied = apply_duplicate_object_reconciliation(
            new_forward_plan,
            self.claim(new_forward_context, seed=118),
            context=new_forward_context,
        )
        self.assertTrue(applied["ok"], applied)

        discovered = plan_duplicate_object_reconciliation_revert(self.root)
        self.assertEqual(
            discovered.manifest_current_sha256,
            duplicate_module._sha256(new_forward_plan._replacement_bytes),
        )
        self.assertEqual(
            discovered.manifest_restore_sha256,
            duplicate_module._sha256(new_original),
        )

        revert_context = duplicate_object_reconciliation_revert_context(
            discovered,
            reviewer_claim=REVIEWER_CLAIM,
        )
        result, _claim = self.complete_revert(
            discovered,
            revert_context,
            seed=119,
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.manifest.read_bytes(), new_original)

    def test_completed_revert_is_not_reoffered_or_rewritten(self) -> None:
        _original, plan, context = self._ready_successful_revert("b", seed=61)
        completed, _completed_claim = self.complete_revert(
            plan,
            context,
            seed=62,
        )
        self.assertTrue(completed["ok"], completed)
        before_plan = archive_snapshot(self.root)

        with self.assertRaises(DuplicateObjectReconciliationError) as absent:
            plan_duplicate_object_reconciliation_revert(self.root)

        self.assertEqual(
            absent.exception.code,
            "duplicate_object_revert_candidate_missing",
        )
        self.assertEqual(archive_snapshot(self.root), before_plan)

        second_claim = self.claim(context, seed=63)
        before_second_apply = archive_snapshot(self.root)
        with self.assertRaises(DuplicateObjectReconciliationError) as rejected:
            apply_duplicate_object_reconciliation_revert(
                plan,
                second_claim,
                context=context,
            )

        self.assertEqual(
            rejected.exception.code,
            "duplicate_object_revert_candidate_missing",
        )
        self.assertEqual(archive_snapshot(self.root), before_second_apply)

    def _ready_finalization_pending_revert(self, digest: str, *, seed: int):
        original, forward_plan, forward_context = self.ready_plan(digest)
        forward_claim = self.claim(forward_context, seed=seed)
        forward_result = apply_duplicate_object_reconciliation(
            forward_plan,
            forward_claim,
            context=forward_context,
        )
        self.assertTrue(forward_result["ok"], forward_result)

        revert_plan = plan_duplicate_object_reconciliation_revert(
            self.root,
            terminal_auditor=duplicate_module._claim_terminal_auditor(
                forward_claim
            ),
        )
        revert_context = duplicate_object_reconciliation_revert_context(
            revert_plan,
            reviewer_claim=REVIEWER_CLAIM,
        )
        pending_claim = self.claim(revert_context, seed=seed + 1)
        pending_result = apply_duplicate_object_reconciliation_revert(
            revert_plan,
            pending_claim,
            context=revert_context,
        )
        self.assertTrue(pending_result["ok"], pending_result)
        self.assertEqual(self.manifest.read_bytes(), original)

        journal_path = next(
            (
                self.root
                / "journals"
                / "objects"
                / "duplicate-reconciliation-revert"
            ).glob("*.json")
        )
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        self.assertEqual(journal["status"], "finalization_pending")
        self.assertEqual(
            journal["pending_finalization_approval_reference"],
            pending_claim.public_reference(),
        )
        self.assertIn("terminal_authentication", journal)
        return revert_plan, revert_context, pending_claim, journal_path

    def test_authenticated_finalization_pending_is_a_read_only_candidate(
        self,
    ) -> None:
        plan, _context, pending_claim, _journal_path = (
            self._ready_finalization_pending_revert("2", seed=103)
        )
        before = archive_snapshot(self.root)

        discovered = plan_duplicate_object_reconciliation_revert(
            self.root,
            terminal_auditor=duplicate_module._claim_terminal_auditor(
                pending_claim
            ),
        )

        self.assertTrue(duplicate_module._same_revert_plan(plan, discovered))
        self.assertEqual(archive_snapshot(self.root), before)

        pending_claim.finalize_succeeded()
        after_claim_success = archive_snapshot(self.root)
        discovered_after_claim_success = (
            plan_duplicate_object_reconciliation_revert(
                self.root,
                terminal_auditor=duplicate_module._claim_terminal_auditor(
                    pending_claim
                ),
            )
        )
        self.assertTrue(
            duplicate_module._same_revert_plan(
                plan,
                discovered_after_claim_success,
            )
        )
        self.assertEqual(archive_snapshot(self.root), after_claim_success)

    def test_shape_valid_missing_pending_reference_fails_closed(self) -> None:
        _plan, _context, pending_claim, journal_path = (
            self._ready_finalization_pending_revert("3", seed=105)
        )
        self._rewrite_json(
            journal_path,
            lambda document: document[
                "pending_finalization_approval_reference"
            ].update({"approval_id": "approval_" + "f" * 32}),
        )
        before = archive_snapshot(self.root)

        with self.assertRaises(DuplicateObjectReconciliationError) as rejected:
            plan_duplicate_object_reconciliation_revert(
                self.root,
                terminal_auditor=duplicate_module._claim_terminal_auditor(
                    pending_claim
                ),
            )

        self.assertEqual(
            rejected.exception.code,
            "duplicate_object_revert_evidence_invalid",
        )
        self.assertEqual(archive_snapshot(self.root), before)

    def test_missing_pending_claim_fails_closed_with_independent_auditor(
        self,
    ) -> None:
        _plan, context, pending_claim, _journal_path = (
            self._ready_finalization_pending_revert("4", seed=107)
        )
        auditor_claim = self.claim(context, seed=109)
        claim_path = (
            self.root
            / CLAIMS_RELATIVE_ROOT
            / f"{pending_claim.approval_id}.json"
        )
        claim_path.unlink()
        before = archive_snapshot(self.root)

        with self.assertRaises(DuplicateObjectReconciliationError) as rejected:
            plan_duplicate_object_reconciliation_revert(
                self.root,
                terminal_auditor=duplicate_module._claim_terminal_auditor(
                    auditor_claim
                ),
            )

        self.assertEqual(
            rejected.exception.code,
            "duplicate_object_revert_evidence_invalid",
        )
        self.assertEqual(archive_snapshot(self.root), before)

    def test_public_revert_planner_uses_its_production_terminal_auditor(
        self,
    ) -> None:
        _original, forward_plan, forward_context = self.ready_plan("d")
        forward_claim = self.claim(forward_context, seed=110)
        applied = apply_duplicate_object_reconciliation(
            forward_plan,
            forward_claim,
            context=forward_context,
        )
        self.assertTrue(applied["ok"], applied)
        auditor = duplicate_module._claim_terminal_auditor(forward_claim)
        expected = plan_duplicate_object_reconciliation_revert(
            self.root,
            terminal_auditor=auditor,
        )

        with mock.patch.object(
            duplicate_module,
            "_production_terminal_auditor",
            return_value=auditor,
        ) as production_auditor:
            public_plan = (
                duplicate_module.plan_duplicate_object_reconciliation_revert(
                    self.root
                )
            )

        production_auditor.assert_called_once_with(self.root)
        self.assertTrue(public_plan["ok"], public_plan)
        self.assertEqual(public_plan["candidate_count"], 1)
        self.assertEqual(public_plan["plan_sha256"], expected.plan_sha256)

    def test_started_pending_revert_resumes_same_claim_without_manifest_write(
        self,
    ) -> None:
        plan, context, pending_claim, _journal_path = (
            self._ready_finalization_pending_revert("5", seed=111)
        )
        approval_id = duplicate_module._duplicate_object_reconciliation_revert_resume_approval_id(
            plan,
            terminal_auditor=_terminal_auditor(self.root),
        )
        self.assertEqual(approval_id, pending_claim.approval_id)
        pending_claim.close()
        manifest_writes = 0
        real_atomic_replace = duplicate_module._atomic_replace

        def count_manifest_writes(root: Path, path: Path, raw: bytes) -> None:
            nonlocal manifest_writes
            if path.resolve() == self.manifest.resolve():
                manifest_writes += 1
            real_atomic_replace(root, path, raw)

        with mock.patch.object(
            duplicate_module,
            "_atomic_replace",
            side_effect=count_manifest_writes,
        ):
            result = resume_exact_human_approved_transaction(
                self.root,
                context,
                approval_id,
                lambda claim: duplicate_module._duplicate_object_reconciliation_revert_resume_checkpoint_matches(
                    plan,
                    claim,
                    context=context,
                    expected_claim_status="started",
                ),
                lambda claim: apply_duplicate_object_reconciliation_revert(
                    plan,
                    claim,
                    context=context,
                ),
                lambda claim: duplicate_module._duplicate_object_reconciliation_revert_resume_checkpoint_matches(
                    plan,
                    claim,
                    context=context,
                    expected_claim_status="succeeded",
                ),
                lambda claim: finalize_duplicate_object_reconciliation_revert(
                    plan,
                    claim,
                    context=context,
                ),
                key_provider=_KeyProvider(),
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual(
            result["exact_human_approval_resume_branch"], "started_writer"
        )
        self.assertFalse(result["native_approval_redisplayed"])
        self.assertFalse(result["manifest_write_performed_this_run"])
        self.assertEqual(manifest_writes, 0)

    def test_succeeded_pending_revert_resumes_finalizer_without_writer(
        self,
    ) -> None:
        plan, context, pending_claim, _journal_path = (
            self._ready_finalization_pending_revert("6", seed=113)
        )
        pending_claim.finalize_succeeded()
        approval_id = duplicate_module._duplicate_object_reconciliation_revert_resume_approval_id(
            plan,
            terminal_auditor=_terminal_auditor(self.root),
        )
        self.assertEqual(approval_id, pending_claim.approval_id)
        pending_claim.close()
        manifest_writes = 0
        real_atomic_replace = duplicate_module._atomic_replace

        def count_manifest_writes(root: Path, path: Path, raw: bytes) -> None:
            nonlocal manifest_writes
            if path.resolve() == self.manifest.resolve():
                manifest_writes += 1
            real_atomic_replace(root, path, raw)

        def writer_must_not_run(_claim) -> dict[str, Any]:
            raise AssertionError("succeeded resume must not re-enter writer")

        with mock.patch.object(
            duplicate_module,
            "_atomic_replace",
            side_effect=count_manifest_writes,
        ):
            result = resume_exact_human_approved_transaction(
                self.root,
                context,
                approval_id,
                lambda claim: duplicate_module._duplicate_object_reconciliation_revert_resume_checkpoint_matches(
                    plan,
                    claim,
                    context=context,
                    expected_claim_status="started",
                ),
                writer_must_not_run,
                lambda claim: duplicate_module._duplicate_object_reconciliation_revert_resume_checkpoint_matches(
                    plan,
                    claim,
                    context=context,
                    expected_claim_status="succeeded",
                ),
                lambda claim: finalize_duplicate_object_reconciliation_revert(
                    plan,
                    claim,
                    context=context,
                ),
                key_provider=_KeyProvider(),
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual(
            result["exact_human_approval_resume_branch"], "succeeded_tail"
        )
        self.assertFalse(result["native_approval_redisplayed"])
        self.assertFalse(result["domain_writer_reentered"])
        self.assertEqual(manifest_writes, 0)

        with self.assertRaises(DuplicateObjectReconciliationError) as absent:
            plan_duplicate_object_reconciliation_revert(self.root)
        self.assertEqual(
            absent.exception.code,
            "duplicate_object_revert_candidate_missing",
        )

    def test_terminal_revert_finalization_reference_and_seal_fail_closed(
        self,
    ) -> None:
        _original, plan, context = self._ready_successful_revert("f", seed=101)
        _result, finalization_claim = self.complete_revert(
            plan,
            context,
            seed=102,
        )
        journal_path = next(
            (
                self.root
                / "journals"
                / "objects"
                / "duplicate-reconciliation-revert"
            ).glob("*.json")
        )
        claim_path = (
            self.root
            / CLAIMS_RELATIVE_ROOT
            / f"{finalization_claim.approval_id}.json"
        )
        for name, mutate in (
            (
                "shape_valid_missing_reference",
                lambda root: self._rewrite_json(
                    root / journal_path.relative_to(self.root),
                    lambda document: document[
                        "finalization_approval_reference"
                    ].update({"approval_id": "approval_" + "f" * 32}),
                ),
            ),
            (
                "missing_authenticated_claim",
                lambda root: (
                    root / claim_path.relative_to(self.root)
                ).unlink(),
            ),
            (
                "terminal_mac_tamper",
                lambda root: self._rewrite_json(
                    root / journal_path.relative_to(self.root),
                    lambda document: document["terminal_authentication"].update(
                        {"mac": "hmac-sha256:" + "0" * 64}
                    ),
                ),
            ),
        ):
            with self.subTest(evidence=name):
                copy_root = Path(self.temporary.name) / f"terminal-{name}"
                shutil.copytree(self.root, copy_root)
                mutate(copy_root)
                before = archive_snapshot(copy_root)

                with self.assertRaises(
                    DuplicateObjectReconciliationError
                ) as rejected:
                    plan_duplicate_object_reconciliation_revert(copy_root)

                self.assertEqual(
                    rejected.exception.code,
                    "duplicate_object_revert_evidence_invalid",
                )
                self.assertEqual(archive_snapshot(copy_root), before)

    def test_forward_terminal_seal_blocks_coordinated_supersession_deletion(
        self,
    ) -> None:
        _original, plan, context = self.ready_plan("1")
        real_create_only = duplicate_module._create_only

        def publish_journal_then_fail(root: Path, path: Path, raw: bytes) -> None:
            real_create_only(root, path, raw)
            if "journals/objects/duplicate-reconciliation/" in path.as_posix():
                raise OSError("simulated prewrite interruption")

        with (
            mock.patch.object(
                duplicate_module,
                "_create_only",
                side_effect=publish_journal_then_fail,
            ),
            self.assertRaises(ExactHumanApprovalWorkflowError),
        ):
            execute_exact_human_approved_write(
                self.root,
                context,
                lambda claim: apply_duplicate_object_reconciliation(
                    plan, claim, context=context
                ),
                native=_Native(),
                key_provider=_KeyProvider(),
            )
        succeeded = execute_exact_human_approved_write(
            self.root,
            context,
            lambda claim: apply_duplicate_object_reconciliation(
                plan, claim, context=context
            ),
            native=_Native(),
            key_provider=_KeyProvider(),
        )
        self.assertTrue(succeeded["ok"], succeeded)
        journal_path = next(
            (
                self.root / "journals" / "objects" / "duplicate-reconciliation"
            ).glob("*.json")
        )
        receipt_path = next(
            (
                self.root / "receipts" / "objects" / "duplicate-reconciliation"
            ).glob("*.json")
        )
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertIn("approval_supersession", journal)
        journal.pop("approval_supersession")
        receipt.pop("approval_supersession_sha256")
        receipt_raw = duplicate_module._canonical_bytes(receipt)
        receipt_path.write_bytes(receipt_raw)
        journal["receipt_sha256"] = duplicate_module._sha256(receipt_raw)
        journal_path.write_bytes(duplicate_module._canonical_bytes(journal))
        before = archive_snapshot(self.root)

        with self.assertRaises(DuplicateObjectReconciliationError) as rejected:
            plan_duplicate_object_reconciliation_revert(self.root)

        self.assertEqual(
            rejected.exception.code,
            "duplicate_object_revert_evidence_invalid",
        )
        self.assertEqual(archive_snapshot(self.root), before)

    def test_no_duplicate_and_invalid_manifest_use_fixed_errors(self) -> None:
        self.write_rows(self.row("6" * 64))
        with self.assertRaises(DuplicateObjectReconciliationError) as captured:
            plan_duplicate_object_reconciliation(self.root)
        self.assertEqual(captured.exception.code, "duplicate_object_no_duplicates")
        self.manifest.write_bytes(b'{"object_id":"private-secret"}\n')
        with self.assertRaises(DuplicateObjectReconciliationError) as captured:
            plan_duplicate_object_reconciliation(self.root)
        self.assertEqual(captured.exception.code, "duplicate_object_manifest_invalid")
        self.assertNotIn("private-secret", str(captured.exception))


if __name__ == "__main__":
    unittest.main()
