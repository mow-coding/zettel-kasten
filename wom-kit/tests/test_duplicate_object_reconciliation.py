from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
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
    _plan_duplicate_object_reconciliation_core as plan_duplicate_object_reconciliation,
    _plan_duplicate_object_reconciliation_revert_core as plan_duplicate_object_reconciliation_revert,
)
from wom_kit.exact_human_approval import (
    CLAIMS_RELATIVE_ROOT,
    _ClaimedExactHumanApproval as ClaimedExactHumanApproval,
    _claim_exact_human_approval_core as claim_exact_human_approval,
)
from wom_kit.exact_human_approval_windows import (
    _ExactHumanApprovalDecision as ExactHumanApprovalDecision,
    ExactHumanApprovalOperation,
)


AUTHENTICATION_KEY = bytes(range(32))
REVIEWER_CLAIM = "person:operator"


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
        revert_result = apply_duplicate_object_reconciliation_revert(
            revert_plan,
            self.claim(revert_context, seed=17),
            context=revert_context,
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
            "duplicate_object_revert_candidate_ambiguous",
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
