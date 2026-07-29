from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch


# Import the existing fixture helpers only through their module.  Binding the
# large ArchiveCliTests class in this module would make unittest discover its
# complete suite a second time.  CI starts discovery from ``wom-kit/tests``
# while its working directory is the repository root, so bind the test module
# directory explicitly instead of assuming ``tests`` is importable as a
# namespace package.
TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

import test_cli as cli_test_module
from wom_kit import archive_services


JOURNAL_BINDING_BLOCKER = (
    "activity_group_receipt_journal_binding_invalid"
)
LOCK_BINDING_BLOCKER = (
    "activity_group_receipt_write_lock_binding_invalid"
)
MANUAL_HOLD_BLOCKER = (
    "activity_group_recovery_manual_forensic_hold"
)


class ActivityGroupReceiptEvidenceBindingTests(unittest.TestCase):
    """Adversarial contracts for receipt-to-residue recovery binding."""

    def setUp(self) -> None:
        self.fixture_builder = (
            cli_test_module.ArchiveCliTests(methodName="runTest")
        )

    def create_fixture(
        self,
        tmp_root: Path,
        *,
        suffix: str,
    ) -> tuple[Path, dict[str, Any]]:
        archive_root = tmp_root / f"archive-{suffix}"
        fixture = (
            self.fixture_builder.create_activity_group_write_fixture(
                archive_root,
                archive_id=(
                    f"archive:personal:activity-group-binding-{suffix}"
                ),
                suffix=suffix,
                member_count=2,
            )
        )
        return archive_root, fixture

    @staticmethod
    def receipt_path(
        archive_root: Path,
        request_sha256: str,
    ) -> Path:
        return archive_root / (
            archive_services
            .activity_group_membership_receipt_relative_path(
                request_sha256
            )
        )

    @staticmethod
    def journal_path(
        archive_root: Path,
        request_sha256: str,
    ) -> Path:
        return (
            archive_services
            .activity_group_membership_transaction_journal_path(
                archive_root,
                request_sha256,
            )
        )

    @staticmethod
    def lock_path(archive_root: Path) -> Path:
        return (
            archive_root
            / ".wom-scratch"
            / "private"
            / "activity-groups"
            / archive_services
            .ACTIVITY_GROUP_MEMBERSHIP_WRITE_LOCK_NAME
        )

    @staticmethod
    def guard_path(archive_root: Path) -> Path:
        return (
            archive_root
            / ".wom-scratch"
            / "private"
            / "activity-groups"
            / archive_services
            .ACTIVITY_GROUP_MEMBERSHIP_RECOVERY_GUARD_NAME
        )

    @staticmethod
    def sha256_path(path: Path) -> str:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def read_json(path: Path) -> dict[str, Any]:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise AssertionError("test evidence must be a JSON object")
        return document

    @staticmethod
    def write_json(path: Path, document: dict[str, Any]) -> None:
        path.write_bytes(
            (
                json.dumps(
                    document,
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8")
        )

    @classmethod
    def write_journal(
        cls,
        path: Path,
        journal: dict[str, Any],
    ) -> None:
        unsigned_journal = dict(journal)
        unsigned_journal.pop("journal_digest", None)
        journal["journal_digest"] = (
            archive_services.sha256_json_value(unsigned_journal)
        )
        cls.write_json(path, journal)

    @staticmethod
    def canonical_bytes(
        fixture: dict[str, Any],
    ) -> list[bytes]:
        return [
            path.read_bytes()
            for path in fixture["member_paths"]
        ]

    @staticmethod
    def evidence_bytes(*paths: Path) -> dict[Path, bytes]:
        return {
            path: path.read_bytes()
            for path in paths
            if path.exists() or path.is_symlink()
        }

    def write_completed_residue(
        self,
        archive_root: Path,
        fixture: dict[str, Any],
    ) -> tuple[Path, Path, Path]:
        journal_path = self.journal_path(
            archive_root,
            fixture["request_sha256"],
        )
        receipt_path = self.receipt_path(
            archive_root,
            fixture["request_sha256"],
        )
        lock_path = self.lock_path(archive_root)
        original_delete = (
            archive_services.delete_activity_group_evidence_exact
        )
        failed_once = False

        def fail_first_lock_cleanup(
            root: Path,
            path: Path,
            *args: Any,
            **kwargs: Any,
        ) -> None:
            nonlocal failed_once
            if (
                path.name == lock_path.name
                and path.parent.resolve()
                == lock_path.parent.resolve()
                and not failed_once
            ):
                failed_once = True
                raise OSError(
                    "PRIVATE_BINDING_TEST_LOCK_CLEANUP_FAILURE"
                )
            original_delete(root, path, *args, **kwargs)

        with patch.object(
            archive_services,
            "delete_activity_group_evidence_exact",
            new=fail_first_lock_cleanup,
        ):
            applied = (
                archive_services.activity_group_membership_write(
                    archive_root,
                    request_path=fixture["request_relative"],
                    expected_request_sha256=fixture[
                        "request_sha256"
                    ],
                    expected_review_plan_sha256=fixture[
                        "review_plan_sha256"
                    ],
                    approve=True,
                    reviewed_by="person:activity-group-binding-reviewer",
                    affirm_memberships_reviewed=True,
                )
            )

        self.assertFalse(applied["ok"], applied)
        self.assertEqual(
            applied["status"],
            "applied_evidence_conflict",
        )
        self.assertTrue(failed_once)
        self.assertTrue(journal_path.is_file())
        self.assertTrue(receipt_path.is_file())
        self.assertTrue(lock_path.is_file())
        return receipt_path, journal_path, lock_path

    @staticmethod
    def recovery_plan(
        archive_root: Path,
        fixture: dict[str, Any],
    ) -> dict[str, Any]:
        return (
            archive_services
            .activity_group_membership_recovery_plan(
                archive_root,
                expected_request_sha256=fixture[
                    "request_sha256"
                ],
                dry_run=True,
            )
        )

    @staticmethod
    def recover(
        archive_root: Path,
        fixture: dict[str, Any],
        recovery_plan_sha256: str,
    ) -> dict[str, Any]:
        return (
            archive_services.activity_group_membership_recover(
                archive_root,
                expected_request_sha256=fixture[
                    "request_sha256"
                ],
                expected_recovery_plan_sha256=(
                    recovery_plan_sha256
                ),
                approve=True,
                reviewed_by=(
                    "person:activity-group-recovery-reviewer"
                ),
                affirm_recovery_reviewed=True,
            )
        )

    def assert_manual_binding_hold(
        self,
        plan: dict[str, Any],
        *,
        blocker: str,
    ) -> None:
        self.assertFalse(plan["ok"], plan)
        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(
            plan["transaction_state"],
            "unknown_or_drifted",
        )
        self.assertEqual(
            plan["recovery_action"],
            "manual_forensic_hold",
        )
        self.assertIn(blocker, plan["blockers"])
        self.assertIn(MANUAL_HOLD_BLOCKER, plan["blockers"])
        self.assertFalse(
            plan["approval_boundary"][
                "manual_forensic_hold_executable"
            ]
        )

    def test_v01_receipt_and_journal_with_v02_lock_still_recover(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="71",
            )
            receipt_path, journal_path, lock_path = (
                self.write_completed_residue(
                    archive_root,
                    fixture,
                )
            )
            completed_bytes = self.canonical_bytes(fixture)
            receipt = self.read_json(receipt_path)
            journal = self.read_json(journal_path)
            lock = self.read_json(lock_path)

            self.assertEqual(
                receipt["schema"],
                "wom-kit/activity-group-membership-receipt/v0.1",
            )
            self.assertEqual(
                journal["schema"],
                (
                    "wom-kit/"
                    "activity-group-membership-transaction-journal/v0.1"
                ),
            )
            self.assertEqual(
                lock["schema"],
                "wom-kit/activity-group-membership-write-lock/v0.2",
            )
            for document in (receipt, journal):
                self.assertNotIn(
                    "transaction_binding_sha256",
                    document,
                )
            self.assertRegex(
                lock["transaction_binding_sha256"],
                r"\Asha256:[0-9a-f]{64}\Z",
            )

            plan = self.recovery_plan(archive_root, fixture)
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(
                plan["transaction_state"],
                "verified_completed_residue",
            )
            self.assertEqual(
                plan["recovery_action"],
                "cleanup_verified_completed_evidence",
            )
            self.assertEqual(
                plan["evidence"]["receipt_sha256"],
                self.sha256_path(receipt_path),
            )

            recovered = self.recover(
                archive_root,
                fixture,
                plan["recovery_plan_sha256"],
            )
            self.assertTrue(recovered["ok"], recovered)
            self.assertEqual(
                recovered["status"],
                "cleanup_completed",
            )
            self.assertFalse(journal_path.exists())
            self.assertFalse(lock_path.exists())
            self.assertTrue(receipt_path.is_file())
            self.assertEqual(
                completed_bytes,
                self.canonical_bytes(fixture),
            )

    def test_v02_lock_only_completion_is_automatic_only_on_windows(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="71l",
            )
            receipt_path, journal_path, lock_path = (
                self.write_completed_residue(
                    archive_root,
                    fixture,
                )
            )
            journal_path.unlink()
            plan = self.recovery_plan(archive_root, fixture)

            self.assertEqual(
                plan["transaction_state"],
                "verified_completed_lock_residue",
            )
            if os.name == "nt":
                self.assertTrue(plan["ok"], plan)
                self.assertEqual(
                    plan["recovery_action"],
                    "cleanup_verified_completed_evidence",
                )
                recovered = self.recover(
                    archive_root,
                    fixture,
                    plan["recovery_plan_sha256"],
                )
                self.assertTrue(recovered["ok"], recovered)
                self.assertFalse(lock_path.exists())
            else:
                self.assertFalse(plan["ok"], plan)
                self.assertEqual(
                    plan["recovery_action"],
                    "manual_forensic_hold",
                )
                self.assertIn(
                    (
                        "activity_group_posix_lock_only_completion_"
                        "requires_manual_hold"
                    ),
                    plan["blockers"],
                )
                self.assertTrue(lock_path.is_file())
            self.assertTrue(receipt_path.is_file())

    def test_journal_receipt_semantic_mismatches_enter_manual_hold(
        self,
    ) -> None:
        def mutate_timestamp(
            receipt: dict[str, Any],
            journal: dict[str, Any],
        ) -> None:
            journal["prepared_at"] = "2026-07-29T23:59:58+09:00"

        def mutate_reviewer(
            receipt: dict[str, Any],
            journal: dict[str, Any],
        ) -> None:
            receipt["reviewed_by"] = "person:different-reviewer"

        def mutate_digest(
            receipt: dict[str, Any],
            journal: dict[str, Any],
        ) -> None:
            receipt["write_plan_sha256"] = "sha256:" + ("a" * 64)

        def mutate_items_order(
            receipt: dict[str, Any],
            journal: dict[str, Any],
        ) -> None:
            journal["items"] = list(reversed(journal["items"]))

        def mutate_receipt_item_hash(
            receipt: dict[str, Any],
            journal: dict[str, Any],
        ) -> None:
            receipt["items"][0]["before_file_sha256"] = (
                "sha256:" + ("d" * 64)
            )

        def mutate_receipt_snapshot_size(
            receipt: dict[str, Any],
            journal: dict[str, Any],
        ) -> None:
            snapshot = receipt["items"][0]["before_snapshot"]
            snapshot["size_bytes"] = int(snapshot["size_bytes"]) + 1

        def mutate_receipt_items_order(
            receipt: dict[str, Any],
            journal: dict[str, Any],
        ) -> None:
            receipt["items"] = list(reversed(receipt["items"]))

        cases: tuple[
            tuple[
                str,
                str,
                Callable[
                    [dict[str, Any], dict[str, Any]],
                    None,
                ],
            ],
            ...,
        ] = (
            ("timestamp", "72", mutate_timestamp),
            ("reviewer", "73", mutate_reviewer),
            ("digest", "74", mutate_digest),
            ("items-order", "75", mutate_items_order),
            ("receipt-item-hash", "751", mutate_receipt_item_hash),
            (
                "receipt-snapshot-size",
                "752",
                mutate_receipt_snapshot_size,
            ),
            (
                "receipt-items-order",
                "753",
                mutate_receipt_items_order,
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            for name, suffix, mutate in cases:
                with self.subTest(mismatch=name):
                    archive_root, fixture = self.create_fixture(
                        tmp_root,
                        suffix=suffix,
                    )
                    (
                        receipt_path,
                        journal_path,
                        lock_path,
                    ) = self.write_completed_residue(
                        archive_root,
                        fixture,
                    )
                    completed_bytes = self.canonical_bytes(fixture)
                    receipt = self.read_json(receipt_path)
                    journal = self.read_json(journal_path)
                    mutate(receipt, journal)
                    self.write_json(receipt_path, receipt)
                    self.write_journal(journal_path, journal)
                    retained_evidence = self.evidence_bytes(
                        receipt_path,
                        journal_path,
                        lock_path,
                    )

                    plan = self.recovery_plan(
                        archive_root,
                        fixture,
                    )
                    self.assert_manual_binding_hold(
                        plan,
                        blocker=JOURNAL_BINDING_BLOCKER,
                    )
                    self.assertEqual(
                        retained_evidence,
                        self.evidence_bytes(
                            receipt_path,
                            journal_path,
                            lock_path,
                        ),
                    )
                    self.assertEqual(
                        completed_bytes,
                        self.canonical_bytes(fixture),
                    )

    def test_lock_only_review_and_write_digest_mismatches_enter_manual_hold(
        self,
    ) -> None:
        cases = (
            ("review_plan_sha256", "76", "b"),
            ("write_plan_sha256", "77", "c"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            for field, suffix, fill in cases:
                with self.subTest(lock_field=field):
                    archive_root, fixture = self.create_fixture(
                        tmp_root,
                        suffix=suffix,
                    )
                    (
                        receipt_path,
                        journal_path,
                        lock_path,
                    ) = self.write_completed_residue(
                        archive_root,
                        fixture,
                    )
                    completed_bytes = self.canonical_bytes(fixture)

                    # A completed writer may remove the journal and be
                    # interrupted before it removes its v0.1 lock.
                    journal_path.unlink()
                    lock = self.read_json(lock_path)
                    lock[field] = "sha256:" + (fill * 64)
                    self.write_json(lock_path, lock)
                    retained_evidence = self.evidence_bytes(
                        receipt_path,
                        lock_path,
                    )

                    plan = self.recovery_plan(
                        archive_root,
                        fixture,
                    )
                    self.assert_manual_binding_hold(
                        plan,
                        blocker=LOCK_BINDING_BLOCKER,
                    )
                    self.assertEqual(
                        retained_evidence,
                        self.evidence_bytes(
                            receipt_path,
                            lock_path,
                        ),
                    )
                    self.assertEqual(
                        completed_bytes,
                        self.canonical_bytes(fixture),
                    )

    def test_lock_only_receipt_semantic_truncation_enters_manual_hold(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="77s",
            )
            receipt_path, journal_path, lock_path = (
                self.write_completed_residue(
                    archive_root,
                    fixture,
                )
            )
            completed_bytes = self.canonical_bytes(fixture)
            journal_path.unlink()
            receipt = self.read_json(receipt_path)
            receipt["items"] = receipt["items"][:1]
            receipt["item_count"] = 1
            self.write_json(receipt_path, receipt)
            retained_evidence = self.evidence_bytes(
                receipt_path,
                lock_path,
            )

            plan = self.recovery_plan(archive_root, fixture)

            self.assert_manual_binding_hold(
                plan,
                blocker=LOCK_BINDING_BLOCKER,
            )
            self.assertEqual(
                retained_evidence,
                self.evidence_bytes(receipt_path, lock_path),
            )
            self.assertEqual(
                completed_bytes,
                self.canonical_bytes(fixture),
            )

    def test_legacy_v01_lock_only_completed_residue_enters_manual_hold(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="77l",
            )
            receipt_path, journal_path, lock_path = (
                self.write_completed_residue(
                    archive_root,
                    fixture,
                )
            )
            journal_path.unlink()
            lock = self.read_json(lock_path)
            lock["schema"] = (
                "wom-kit/activity-group-membership-write-lock/v0.1"
            )
            lock.pop("transaction_binding_sha256")
            self.write_json(lock_path, lock)

            plan = self.recovery_plan(archive_root, fixture)

            self.assert_manual_binding_hold(
                plan,
                blocker=LOCK_BINDING_BLOCKER,
            )

    def test_receipt_whitespace_rewrite_invalidates_old_plan_but_fresh_plan_passes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="78",
            )
            receipt_path, journal_path, lock_path = (
                self.write_completed_residue(
                    archive_root,
                    fixture,
                )
            )
            completed_bytes = self.canonical_bytes(fixture)
            old_plan = self.recovery_plan(archive_root, fixture)
            self.assertTrue(old_plan["ok"], old_plan)
            old_receipt_sha256 = self.sha256_path(receipt_path)

            receipt = self.read_json(receipt_path)
            receipt_path.write_bytes(
                (
                    json.dumps(
                        receipt,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8")
            )
            new_receipt_sha256 = self.sha256_path(receipt_path)
            self.assertNotEqual(
                old_receipt_sha256,
                new_receipt_sha256,
            )

            blocked = self.recover(
                archive_root,
                fixture,
                old_plan["recovery_plan_sha256"],
            )
            self.assertFalse(blocked["ok"], blocked)
            self.assertEqual(blocked["status"], "blocked")
            self.assertIn(
                "recovery_plan_sha256_mismatch",
                blocked["blockers"],
            )
            self.assertTrue(receipt_path.is_file())
            self.assertTrue(journal_path.is_file())
            self.assertTrue(lock_path.is_file())
            self.assertFalse(self.guard_path(archive_root).exists())
            self.assertEqual(
                completed_bytes,
                self.canonical_bytes(fixture),
            )

            fresh_plan = self.recovery_plan(
                archive_root,
                fixture,
            )
            self.assertTrue(fresh_plan["ok"], fresh_plan)
            self.assertNotEqual(
                old_plan["recovery_plan_sha256"],
                fresh_plan["recovery_plan_sha256"],
            )
            self.assertEqual(
                fresh_plan["evidence"]["receipt_sha256"],
                new_receipt_sha256,
            )

            recovered = self.recover(
                archive_root,
                fixture,
                fresh_plan["recovery_plan_sha256"],
            )
            self.assertTrue(recovered["ok"], recovered)
            self.assertEqual(
                recovered["status"],
                "cleanup_completed",
            )
            self.assertTrue(receipt_path.is_file())
            self.assertFalse(journal_path.exists())
            self.assertFalse(lock_path.exists())
            self.assertEqual(
                completed_bytes,
                self.canonical_bytes(fixture),
            )

    def test_receipt_sha_change_under_guard_retains_all_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="79",
            )
            receipt_path, journal_path, lock_path = (
                self.write_completed_residue(
                    archive_root,
                    fixture,
                )
            )
            completed_bytes = self.canonical_bytes(fixture)
            plan = self.recovery_plan(archive_root, fixture)
            self.assertTrue(plan["ok"], plan)
            original_receipt_sha256 = self.sha256_path(receipt_path)
            original_plan_function = (
                archive_services
                .activity_group_membership_recovery_plan
            )
            plan_calls = 0

            def mutate_after_locked_plan(
                *args: Any,
                **kwargs: Any,
            ) -> dict[str, Any]:
                nonlocal plan_calls
                result = original_plan_function(*args, **kwargs)
                plan_calls += 1
                if plan_calls == 2:
                    receipt = self.read_json(receipt_path)
                    receipt_path.write_bytes(
                        (
                            json.dumps(
                                receipt,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode("utf-8")
                    )
                return result

            with patch.object(
                archive_services,
                "activity_group_membership_recovery_plan",
                new=mutate_after_locked_plan,
            ):
                recovered = self.recover(
                    archive_root,
                    fixture,
                    plan["recovery_plan_sha256"],
                )

            self.assertEqual(plan_calls, 2)
            self.assertNotEqual(
                original_receipt_sha256,
                self.sha256_path(receipt_path),
            )
            self.assertFalse(recovered["ok"], recovered)
            self.assertEqual(
                recovered["status"],
                "failed_recovery_evidence_retained",
            )
            self.assertIn(
                "activity_group_recovery_execution_failed",
                recovered["blockers"],
            )
            self.assertTrue(receipt_path.is_file())
            self.assertTrue(journal_path.is_file())
            self.assertTrue(lock_path.is_file())
            self.assertFalse(self.guard_path(archive_root).exists())
            self.assertEqual(
                completed_bytes,
                self.canonical_bytes(fixture),
            )

    def test_completed_cleanup_rejects_aba_receipt_before_residue_use(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="receipt-aba-residue",
            )
            receipt_path, journal_path, lock_path = (
                self.write_completed_residue(
                    archive_root,
                    fixture,
                )
            )
            plan = self.recovery_plan(archive_root, fixture)
            self.assertTrue(plan["ok"], plan)
            anchor_path = (
                archive_root
                / "zettels"
                / f"{fixture['anchor_id']}.md"
            )
            anchor_bytes = anchor_path.read_bytes()
            unrelated_residue_bytes = b"UNRELATED_SWAP_RESIDUE\n"
            unrelated_swap_path, _previous_path = (
                archive_services.activity_group_canonical_swap_paths(
                    anchor_path,
                    fixture["request_sha256"],
                )
            )
            unrelated_swap_path.write_bytes(unrelated_residue_bytes)
            fake_document = {
                "items": [
                    {
                        "zettel_id": fixture["anchor_id"],
                        "before_file_sha256": (
                            "sha256:"
                            + hashlib.sha256(
                                unrelated_residue_bytes
                            ).hexdigest()
                        ),
                        "after_file_sha256": (
                            "sha256:"
                            + hashlib.sha256(anchor_bytes).hexdigest()
                        ),
                    }
                ]
            }
            fake_raw = (
                json.dumps(
                    fake_document,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            real_receipt_raw = receipt_path.read_bytes()
            original_cleanup_read = (
                archive_services
                .read_activity_group_membership_receipt_for_cleanup
            )
            injected = False

            def inject_temporary_aba_receipt(
                root: Path,
                path: Path,
                *,
                expected_sha256: str,
            ) -> tuple[bytes, dict[str, Any]]:
                nonlocal injected
                self.assertFalse(injected)
                injected = True
                receipt_path.write_bytes(fake_raw)
                try:
                    return original_cleanup_read(
                        root,
                        path,
                        expected_sha256=expected_sha256,
                    )
                finally:
                    receipt_path.write_bytes(real_receipt_raw)

            with patch.object(
                archive_services,
                "read_activity_group_membership_receipt_for_cleanup",
                new=inject_temporary_aba_receipt,
            ):
                recovered = self.recover(
                    archive_root,
                    fixture,
                    plan["recovery_plan_sha256"],
                )

            self.assertTrue(injected)
            self.assertFalse(recovered["ok"], recovered)
            self.assertEqual(
                recovered["status"],
                "failed_recovery_evidence_retained",
            )
            self.assertEqual(
                unrelated_residue_bytes,
                unrelated_swap_path.read_bytes(),
            )
            self.assertEqual(real_receipt_raw, receipt_path.read_bytes())
            self.assertTrue(journal_path.is_file())
            self.assertTrue(lock_path.is_file())

    def test_receipt_rewrite_after_final_verifier_return_is_caught_before_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="80",
            )
            receipt_path, journal_path, lock_path = (
                self.write_completed_residue(
                    archive_root,
                    fixture,
                )
            )
            completed_bytes = self.canonical_bytes(fixture)
            plan = self.recovery_plan(archive_root, fixture)
            self.assertTrue(plan["ok"], plan)
            original_receipt_sha256 = self.sha256_path(receipt_path)
            original_verifier = (
                archive_services
                .verify_activity_group_membership_receipt
            )
            verifier_calls = 0

            def rewrite_after_cleanup_verifier(
                *args: Any,
                **kwargs: Any,
            ) -> dict[str, Any]:
                nonlocal verifier_calls
                result = original_verifier(*args, **kwargs)
                verifier_calls += 1
                if verifier_calls == 4:
                    receipt = self.read_json(receipt_path)
                    receipt_path.write_bytes(
                        (
                            json.dumps(
                                receipt,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode("utf-8")
                    )
                return result

            with patch.object(
                archive_services,
                "verify_activity_group_membership_receipt",
                new=rewrite_after_cleanup_verifier,
            ):
                recovered = self.recover(
                    archive_root,
                    fixture,
                    plan["recovery_plan_sha256"],
                )

            self.assertEqual(verifier_calls, 4)
            self.assertEqual(
                original_receipt_sha256,
                self.sha256_path(receipt_path),
            )
            self.assertFalse(recovered["ok"], recovered)
            self.assertEqual(
                recovered["status"],
                "failed_recovery_evidence_retained",
            )
            self.assertIn(
                "activity_group_recovery_execution_failed",
                recovered["blockers"],
            )
            self.assertTrue(receipt_path.is_file())
            self.assertTrue(journal_path.is_file())
            self.assertTrue(lock_path.is_file())
            self.assertFalse(self.guard_path(archive_root).exists())
            self.assertEqual(
                completed_bytes,
                self.canonical_bytes(fixture),
            )

    def test_foreign_journal_appearing_after_cleanup_unlink_retains_shared_lock(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="81",
            )
            receipt_path, journal_path, lock_path = (
                self.write_completed_residue(
                    archive_root,
                    fixture,
                )
            )
            completed_bytes = self.canonical_bytes(fixture)
            plan = self.recovery_plan(archive_root, fixture)
            self.assertTrue(plan["ok"], plan)
            foreign_journal = (
                archive_services
                .activity_group_membership_transaction_journal_path(
                    archive_root,
                    "sha256:" + ("f" * 64),
                )
            )
            original_delete = (
                archive_services
                .delete_activity_group_evidence_exact
            )
            injected = False

            def inject_after_journal_unlink(
                root: Path,
                path: Path,
                *args: Any,
                **kwargs: Any,
            ) -> None:
                nonlocal injected
                original_delete(root, path, *args, **kwargs)
                if (
                    path.name == journal_path.name
                    and path.parent.resolve()
                    == journal_path.parent.resolve()
                    and not injected
                ):
                    injected = True
                    foreign_journal.write_text(
                        "PRIVATE_FOREIGN_JOURNAL_EVIDENCE",
                        encoding="utf-8",
                    )

            with patch.object(
                archive_services,
                "delete_activity_group_evidence_exact",
                new=inject_after_journal_unlink,
            ):
                recovered = self.recover(
                    archive_root,
                    fixture,
                    plan["recovery_plan_sha256"],
                )

            self.assertTrue(injected)
            self.assertFalse(recovered["ok"], recovered)
            self.assertEqual(
                recovered["status"],
                "failed_recovery_evidence_retained",
            )
            self.assertIn(
                "activity_group_recovery_execution_failed",
                recovered["blockers"],
            )
            self.assertTrue(receipt_path.is_file())
            self.assertFalse(journal_path.exists())
            self.assertTrue(foreign_journal.is_file())
            self.assertFalse(lock_path.exists())
            self.assertFalse(self.guard_path(archive_root).exists())
            self.assertEqual(
                completed_bytes,
                self.canonical_bytes(fixture),
            )

    def test_writer_retains_valid_truth_when_receipt_rewrite_follows_verifier(
        self,
    ) -> None:
        if os.name != "nt":
            self.skipTest("Windows no-write-share receipt contract")
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="82",
            )
            receipt_path = self.receipt_path(
                archive_root,
                fixture["request_sha256"],
            )
            journal_path = self.journal_path(
                archive_root,
                fixture["request_sha256"],
            )
            lock_path = self.lock_path(archive_root)
            original_verifier = (
                archive_services
                .verify_activity_group_membership_receipt
            )
            rewrite_attempted = False
            rewrite_blocked = False

            def attempt_rewrite_after_success(
                *args: Any,
                **kwargs: Any,
            ) -> dict[str, Any]:
                nonlocal rewrite_attempted, rewrite_blocked
                result = original_verifier(*args, **kwargs)
                if not rewrite_attempted:
                    rewrite_attempted = True
                    try:
                        receipt_path.write_bytes(
                            b'{"tampered":true}\n'
                        )
                    except OSError:
                        rewrite_blocked = True
                return result

            with patch.object(
                archive_services,
                "verify_activity_group_membership_receipt",
                new=attempt_rewrite_after_success,
            ):
                applied = (
                    archive_services
                    .activity_group_membership_write(
                        archive_root,
                        request_path=fixture["request_relative"],
                        expected_request_sha256=fixture[
                            "request_sha256"
                        ],
                        expected_review_plan_sha256=fixture[
                            "review_plan_sha256"
                        ],
                        approve=True,
                        reviewed_by=(
                            "person:activity-group-binding-reviewer"
                        ),
                        affirm_memberships_reviewed=True,
                    )
                )

            self.assertTrue(rewrite_attempted)
            self.assertTrue(rewrite_blocked)
            self.assertTrue(applied["ok"], applied)
            self.assertEqual(applied["status"], "applied")
            self.assertFalse(journal_path.exists())
            self.assertFalse(lock_path.exists())
            fresh = (
                archive_services
                .verify_activity_group_membership_receipt(
                    archive_root,
                    receipt_path,
                    archive_id=(
                        f"archive:personal:"
                        f"activity-group-binding-82"
                    ),
                    request_sha256=fixture["request_sha256"],
                )
            )
            self.assertTrue(fresh["ok"], fresh)

    def test_writer_rollback_retains_replaced_foreign_receipt(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="82r",
            )
            receipt_path = self.receipt_path(
                archive_root,
                fixture["request_sha256"],
            )
            journal_path = self.journal_path(
                archive_root,
                fixture["request_sha256"],
            )
            lock_path = self.lock_path(archive_root)
            canonical_before = self.canonical_bytes(fixture)
            original_verifier = (
                archive_services
                .verify_activity_group_membership_receipt
            )
            original_delete = (
                archive_services.delete_activity_group_evidence_exact
            )
            replacement = b'{"foreign_replacement":true}\n'
            replacement_injected = False

            def fail_written_receipt_verification(
                *args: Any,
                **kwargs: Any,
            ) -> dict[str, Any]:
                result = original_verifier(*args, **kwargs)
                if result.get("ok"):
                    result = dict(result)
                    result["ok"] = False
                return result

            def replace_before_exact_receipt_delete(
                root: Path,
                path: Path,
                *args: Any,
                **kwargs: Any,
            ) -> None:
                nonlocal replacement_injected
                if (
                    path.name == receipt_path.name
                    and path.parent.resolve()
                    == receipt_path.parent.resolve()
                    and not replacement_injected
                ):
                    replacement_injected = True
                    path.unlink()
                    path.write_bytes(replacement)
                original_delete(root, path, *args, **kwargs)

            with (
                patch.object(
                    archive_services,
                    "verify_activity_group_membership_receipt",
                    new=fail_written_receipt_verification,
                ),
                patch.object(
                    archive_services,
                    "delete_activity_group_evidence_exact",
                    new=replace_before_exact_receipt_delete,
                ),
            ):
                result = (
                    archive_services
                    .activity_group_membership_write(
                        archive_root,
                        request_path=fixture["request_relative"],
                        expected_request_sha256=fixture[
                            "request_sha256"
                        ],
                        expected_review_plan_sha256=fixture[
                            "review_plan_sha256"
                        ],
                        approve=True,
                        reviewed_by=(
                            "person:activity-group-binding-reviewer"
                        ),
                        affirm_memberships_reviewed=True,
                    )
                )

            self.assertTrue(replacement_injected, result)
            self.assertFalse(result["ok"], result)
            self.assertEqual(
                result["status"],
                "failed_rollback_incomplete",
            )
            self.assertIn(
                "activity_group_transaction_failed_recovery_required",
                result["blockers"],
            )
            self.assertFalse(result["rollback"]["succeeded"])
            self.assertFalse(result["rollback"]["receipt_removed"])
            self.assertFalse(
                result["rollback"]["transaction_journal_removed"]
            )
            self.assertFalse(
                result["rollback"]["write_lock_removed"]
            )
            self.assertEqual(
                replacement,
                receipt_path.read_bytes(),
            )
            self.assertTrue(journal_path.is_file())
            self.assertTrue(lock_path.is_file())
            self.assertEqual(
                canonical_before,
                self.canonical_bytes(fixture),
            )

    def test_recovery_does_not_delete_replaced_journal_or_lock_after_cleanup_check(
        self,
    ) -> None:
        for target in ("lock", "journal"):
            with self.subTest(target=target):
                with tempfile.TemporaryDirectory() as tmp:
                    archive_root, fixture = self.create_fixture(
                        Path(tmp),
                        suffix=(
                            "83l" if target == "lock" else "83j"
                        ),
                    )
                    receipt_path, journal_path, lock_path = (
                        self.write_completed_residue(
                            archive_root,
                            fixture,
                        )
                    )
                    plan = self.recovery_plan(
                        archive_root,
                        fixture,
                    )
                    self.assertTrue(plan["ok"], plan)
                    original_phase = (
                        archive_services
                        .verify_activity_group_membership_recovery_cleanup_phase
                    )
                    phase_calls = 0
                    replacement = (
                        f"PRIVATE_REPLACEMENT_{target.upper()}"
                    ).encode("utf-8")

                    def replace_after_phase(
                        *args: Any,
                        **kwargs: Any,
                    ) -> dict[str, Any] | None:
                        nonlocal phase_calls
                        result = original_phase(*args, **kwargs)
                        phase_calls += 1
                        should_replace = (
                            target == "lock" and phase_calls == 1
                        ) or (
                            target == "journal"
                            and phase_calls == 2
                        )
                        if should_replace:
                            path = (
                                lock_path
                                if target == "lock"
                                else journal_path
                            )
                            path.unlink()
                            path.write_bytes(replacement)
                        return result

                    with patch.object(
                        archive_services,
                        "verify_activity_group_membership_recovery_cleanup_phase",
                        new=replace_after_phase,
                    ):
                        recovered = self.recover(
                            archive_root,
                            fixture,
                            plan["recovery_plan_sha256"],
                        )

                    self.assertFalse(recovered["ok"], recovered)
                    self.assertEqual(
                        recovered["status"],
                        "failed_recovery_evidence_retained",
                    )
                    self.assertIn(
                        "activity_group_recovery_execution_failed",
                        recovered["blockers"],
                    )
                    replaced_path = (
                        lock_path
                        if target == "lock"
                        else journal_path
                    )
                    self.assertEqual(
                        replacement,
                        replaced_path.read_bytes(),
                    )
                    self.assertTrue(receipt_path.is_file())
                    self.assertTrue(journal_path.exists())
                    if target == "lock":
                        self.assertTrue(lock_path.exists())
                        self.assertEqual(phase_calls, 1)
                    else:
                        self.assertFalse(lock_path.exists())
                        self.assertEqual(phase_calls, 2)

    def test_phase2_reclassifies_participants_before_last_evidence_delete(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="84",
            )
            journal_path = self.journal_path(
                archive_root,
                fixture["request_sha256"],
            )
            lock_path = self.lock_path(archive_root)
            member_names = {
                path.name for path in fixture["member_paths"]
            }
            original_write = (
                archive_services
                .replace_activity_group_canonical_bytes_compare_and_swap
            )
            interrupted = False

            def interrupt_before_first_member(
                root: Path,
                path: Path,
                **kwargs: Any,
            ) -> None:
                nonlocal interrupted
                if path.name in member_names and not interrupted:
                    interrupted = True
                    raise KeyboardInterrupt(
                        "PRIVATE_PREPARED_NOT_STARTED_EXIT"
                    )
                original_write(root, path, **kwargs)

            with patch.object(
                archive_services,
                (
                    "replace_activity_group_canonical_bytes_"
                    "compare_and_swap"
                ),
                new=interrupt_before_first_member,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    archive_services.activity_group_membership_write(
                        archive_root,
                        request_path=fixture["request_relative"],
                        expected_request_sha256=fixture[
                            "request_sha256"
                        ],
                        expected_review_plan_sha256=fixture[
                            "review_plan_sha256"
                        ],
                        approve=True,
                        reviewed_by=(
                            "person:activity-group-binding-reviewer"
                        ),
                        affirm_memberships_reviewed=True,
                    )

            self.assertTrue(interrupted)
            self.assertTrue(journal_path.is_file())
            self.assertTrue(lock_path.is_file())
            plan = self.recovery_plan(archive_root, fixture)
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(
                plan["transaction_state"],
                "prepared_not_started",
            )
            original_phase = (
                archive_services
                .verify_activity_group_membership_recovery_cleanup_phase
            )
            phase_calls = 0
            drifted_member = fixture["member_paths"][0]
            drift_bytes = (
                drifted_member.read_bytes()
                + b"\nPRIVATE_PHASE2_PARTICIPANT_DRIFT"
            )

            def drift_after_first_phase(
                *args: Any,
                **kwargs: Any,
            ) -> dict[str, Any] | None:
                nonlocal phase_calls
                result = original_phase(*args, **kwargs)
                phase_calls += 1
                if phase_calls == 1:
                    drifted_member.write_bytes(drift_bytes)
                return result

            with patch.object(
                archive_services,
                "verify_activity_group_membership_recovery_cleanup_phase",
                new=drift_after_first_phase,
            ):
                recovered = self.recover(
                    archive_root,
                    fixture,
                    plan["recovery_plan_sha256"],
                )

            self.assertEqual(phase_calls, 1)
            self.assertFalse(recovered["ok"], recovered)
            self.assertEqual(
                recovered["status"],
                "failed_recovery_evidence_retained",
            )
            self.assertTrue(journal_path.is_file())
            self.assertFalse(lock_path.exists())
            self.assertEqual(
                drift_bytes,
                drifted_member.read_bytes(),
            )

    def test_lock_only_cleanup_rechecks_receipt_after_exact_lock_delete(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="85",
            )
            lock_path = self.lock_path(archive_root)
            journal_path = self.journal_path(
                archive_root,
                fixture["request_sha256"],
            )
            receipt_path = self.receipt_path(
                archive_root,
                fixture["request_sha256"],
            )
            canonical_before = self.canonical_bytes(fixture)

            with patch.object(
                archive_services,
                "preserve_activity_group_membership_before_snapshots",
                side_effect=KeyboardInterrupt(
                    "PRIVATE_LOCK_ONLY_HARD_EXIT"
                ),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    archive_services.activity_group_membership_write(
                        archive_root,
                        request_path=fixture["request_relative"],
                        expected_request_sha256=fixture[
                            "request_sha256"
                        ],
                        expected_review_plan_sha256=fixture[
                            "review_plan_sha256"
                        ],
                        approve=True,
                        reviewed_by=(
                            "person:activity-group-binding-reviewer"
                        ),
                        affirm_memberships_reviewed=True,
                    )

            self.assertTrue(lock_path.is_file())
            self.assertFalse(journal_path.exists())
            plan = self.recovery_plan(archive_root, fixture)
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(
                plan["transaction_state"],
                "lock_only_before_journal",
            )
            original_delete = (
                archive_services.delete_activity_group_evidence_exact
            )
            foreign_receipt = b'{"foreign_receipt":true}\n'
            receipt_injected = False

            def inject_receipt_after_lock_delete(
                root: Path,
                path: Path,
                *args: Any,
                **kwargs: Any,
            ) -> None:
                nonlocal receipt_injected
                original_delete(root, path, *args, **kwargs)
                if (
                    path.name == lock_path.name
                    and path.parent.resolve()
                    == lock_path.parent.resolve()
                    and not receipt_injected
                ):
                    receipt_injected = True
                    receipt_path.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    receipt_path.write_bytes(foreign_receipt)

            with patch.object(
                archive_services,
                "delete_activity_group_evidence_exact",
                new=inject_receipt_after_lock_delete,
            ):
                recovered = self.recover(
                    archive_root,
                    fixture,
                    plan["recovery_plan_sha256"],
                )

            self.assertTrue(receipt_injected, recovered)
            self.assertFalse(recovered["ok"], recovered)
            self.assertEqual(
                recovered["status"],
                "failed_recovery_evidence_retained",
            )
            self.assertEqual(
                recovered["transaction_state"],
                "lock_only_before_journal",
            )
            self.assertEqual(
                recovered["recovery_action"],
                "cleanup_unstarted_lock",
            )
            self.assertIn(
                "activity_group_recovery_execution_failed",
                recovered["blockers"],
            )
            self.assertTrue(
                recovered["summary"]["write_lock_removed"]
            )
            self.assertIsNone(
                recovered["summary"]["transaction_journal_removed"]
            )
            self.assertFalse(lock_path.exists())
            self.assertFalse(journal_path.exists())
            self.assertEqual(
                foreign_receipt,
                receipt_path.read_bytes(),
            )
            self.assertFalse(self.guard_path(archive_root).exists())
            self.assertEqual(
                canonical_before,
                self.canonical_bytes(fixture),
            )


if __name__ == "__main__":
    unittest.main()
