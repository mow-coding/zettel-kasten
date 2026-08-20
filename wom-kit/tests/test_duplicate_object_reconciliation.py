from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from wom_kit.duplicate_object_reconciliation import (
    DuplicateObjectReconciliationError,
    _DuplicateObjectReconciliationPlan as DuplicateObjectReconciliationPlan,
    _apply_duplicate_object_reconciliation_core as apply_duplicate_object_reconciliation,
    _duplicate_object_reconciliation_context as duplicate_object_reconciliation_context,
    _plan_duplicate_object_reconciliation_core as plan_duplicate_object_reconciliation,
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
