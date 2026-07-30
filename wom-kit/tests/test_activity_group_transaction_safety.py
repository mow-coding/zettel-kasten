from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

import test_cli as cli_test_helpers
from wom_kit import archive_services


UNRESOLVED_EVIDENCE_BLOCKER = (
    "activity_group_unresolved_transaction_evidence_exists"
)
EVIDENCE_SCAN_FAILED_BLOCKER = (
    "activity_group_transaction_evidence_scan_failed"
)
MAX_SCAN_ENTRIES = 5000
ADD_JOURNAL_SUFFIX = (
    ".activity-group-membership.transaction.json"
)
REMOVAL_JOURNAL_SUFFIX = (
    ".activity-group-membership-removal.transaction.json"
)


class ActivityGroupTransactionSafetyTests(unittest.TestCase):
    """Fail-first safety contracts shared by add and future removal writers."""

    def setUp(self) -> None:
        self.fixture_builder = (
            cli_test_helpers.ArchiveCliTests(methodName="runTest")
        )

    def create_fixture(
        self,
        tmp_root: Path,
        *,
        suffix: str,
        member_count: int = 1,
    ) -> tuple[Path, dict[str, Any]]:
        archive_root = tmp_root / f"archive-{suffix}"
        fixture = (
            self.fixture_builder.create_activity_group_write_fixture(
                archive_root,
                archive_id=(
                    f"archive:personal:activity-group-safety-{suffix}"
                ),
                suffix=suffix,
                member_count=member_count,
            )
        )
        return archive_root, fixture

    @staticmethod
    def add_private_root(archive_root: Path) -> Path:
        return (
            archive_root
            / ".wom-scratch"
            / "private"
            / "activity-groups"
        )

    @staticmethod
    def removal_private_root(archive_root: Path) -> Path:
        return (
            archive_root
            / ".wom-scratch"
            / "private"
            / "activity-group-removals"
        )

    @staticmethod
    def writer_lock_path(archive_root: Path) -> Path:
        return (
            ActivityGroupTransactionSafetyTests.add_private_root(
                archive_root
            )
            / archive_services
            .ACTIVITY_GROUP_MEMBERSHIP_WRITE_LOCK_NAME
        )

    @staticmethod
    def recovery_guard_path(archive_root: Path) -> Path:
        return (
            ActivityGroupTransactionSafetyTests.add_private_root(
                archive_root
            )
            / archive_services
            .ACTIVITY_GROUP_MEMBERSHIP_RECOVERY_GUARD_NAME
        )

    @staticmethod
    def reserved_journal_path(
        private_root: Path,
        *,
        digest: str,
        suffix: str,
    ) -> Path:
        if len(digest) != 64:
            raise AssertionError("test journal digest must be 64 hex chars")
        return private_root / f".{digest}{suffix}"

    @staticmethod
    def mutation_inventory(archive_root: Path) -> dict[str, bytes]:
        """Capture only trees the writer may mutate, excluding test evidence."""

        inventory: dict[str, bytes] = {}
        for relative_root in ("zettels", "objects", "receipts"):
            root = archive_root / relative_root
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_file() and not path.is_symlink():
                    inventory[
                        path.relative_to(archive_root).as_posix()
                    ] = path.read_bytes()
        return inventory

    @staticmethod
    def call_writer(
        archive_root: Path,
        fixture: dict[str, Any],
    ) -> dict[str, Any]:
        return archive_services.activity_group_membership_write(
            archive_root,
            request_path=fixture["request_relative"],
            expected_request_sha256=fixture["request_sha256"],
            expected_review_plan_sha256=fixture[
                "review_plan_sha256"
            ],
            approve=True,
            reviewed_by="person:activity-group-safety-reviewer",
            affirm_memberships_reviewed=True,
        )

    def run_activity_group_child_hard_exit(
        self,
        archive_root: Path,
        fixture: dict[str, Any],
        *,
        mode: str,
        exit_code: int,
        recovery_plan_sha256: str = "",
        target_path: Path | None = None,
    ) -> None:
        child_source = """
import os
from pathlib import Path
from wom_kit import archive_services

root = Path(os.environ["WOM_TEST_ARCHIVE_ROOT"])
mode = os.environ["WOM_TEST_MODE"]
request_sha256 = os.environ["WOM_TEST_REQUEST_SHA256"]
exit_code = int(os.environ["WOM_TEST_EXIT_CODE"])
if mode == "writer_before_snapshots":
    def exit_before_snapshots(*args, **kwargs):
        os._exit(exit_code)

    archive_services.preserve_activity_group_membership_before_snapshots = (
        exit_before_snapshots
    )
    archive_services.activity_group_membership_write(
        root,
        request_path=os.environ["WOM_TEST_REQUEST_RELATIVE"],
        expected_request_sha256=request_sha256,
        expected_review_plan_sha256=os.environ[
            "WOM_TEST_REVIEW_PLAN_SHA256"
        ],
        approve=True,
        reviewed_by="person:activity-group-hard-exit-reviewer",
        affirm_memberships_reviewed=True,
    )
elif mode == "recovery_after_delete":
    target_path = Path(os.environ["WOM_TEST_TARGET_PATH"])
    original_delete = archive_services.delete_activity_group_evidence_exact

    def exit_after_target_delete(root_arg, path, *args, **kwargs):
        candidate = Path(path)
        matched = candidate.name == target_path.name
        if matched:
            try:
                matched = os.path.samefile(
                    candidate.parent,
                    target_path.parent,
                )
            except OSError:
                matched = (
                    os.path.normcase(os.path.realpath(candidate.parent))
                    == os.path.normcase(os.path.realpath(target_path.parent))
                )
        original_delete(root_arg, path, *args, **kwargs)
        if matched:
            os._exit(exit_code)

    archive_services.delete_activity_group_evidence_exact = (
        exit_after_target_delete
    )
    archive_services.activity_group_membership_recover(
        root,
        expected_request_sha256=request_sha256,
        expected_recovery_plan_sha256=os.environ[
            "WOM_TEST_RECOVERY_PLAN_SHA256"
        ],
        approve=True,
        reviewed_by="person:activity-group-hard-exit-reviewer",
        affirm_recovery_reviewed=True,
    )
else:
    raise SystemExit(71)
raise SystemExit(70)
"""
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SRC_ROOT)
        environment["WOM_TEST_ARCHIVE_ROOT"] = str(archive_root)
        environment["WOM_TEST_MODE"] = mode
        environment["WOM_TEST_REQUEST_RELATIVE"] = fixture[
            "request_relative"
        ]
        environment["WOM_TEST_REQUEST_SHA256"] = fixture[
            "request_sha256"
        ]
        environment["WOM_TEST_REVIEW_PLAN_SHA256"] = fixture[
            "review_plan_sha256"
        ]
        environment["WOM_TEST_RECOVERY_PLAN_SHA256"] = (
            recovery_plan_sha256
        )
        environment["WOM_TEST_TARGET_PATH"] = str(target_path or "")
        environment["WOM_TEST_EXIT_CODE"] = str(exit_code)
        completed = subprocess.run(
            [sys.executable, "-c", child_source],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            exit_code,
            completed.stdout + completed.stderr,
        )

    @staticmethod
    def call_recovery(
        archive_root: Path,
        fixture: dict[str, Any],
        recovery_plan: dict[str, Any],
    ) -> dict[str, Any]:
        return archive_services.activity_group_membership_recover(
            archive_root,
            expected_request_sha256=fixture["request_sha256"],
            expected_recovery_plan_sha256=recovery_plan[
                "recovery_plan_sha256"
            ],
            approve=True,
            reviewed_by="person:activity-group-safety-reviewer",
            affirm_recovery_reviewed=True,
        )

    def prepare_partial_recovery_transaction(
        self,
        archive_root: Path,
        fixture: dict[str, Any],
    ) -> tuple[list[bytes], dict[str, Any]]:
        before_bytes = [
            path.read_bytes()
            for path in fixture["member_paths"]
        ]
        original_compare_and_swap = (
            archive_services
            .replace_activity_group_canonical_bytes_compare_and_swap
        )
        forward_attempts = 0

        def interrupt_second_forward(
            root: Path,
            path: Path,
            **kwargs: Any,
        ) -> bool:
            nonlocal forward_attempts
            if not kwargs.get("allow_already_replacement", False):
                forward_attempts += 1
                if forward_attempts == 2:
                    raise KeyboardInterrupt(
                        "PRIVATE_PARTIAL_RECOVERY_SETUP"
                    )
            return original_compare_and_swap(
                root,
                path,
                **kwargs,
            )

        with patch.object(
            archive_services,
            (
                "replace_activity_group_canonical_bytes_"
                "compare_and_swap"
            ),
            new=interrupt_second_forward,
        ):
            with self.assertRaises(KeyboardInterrupt):
                self.call_writer(archive_root, fixture)

        recovery_plan = (
            archive_services
            .activity_group_membership_recovery_plan(
                archive_root,
                expected_request_sha256=fixture["request_sha256"],
                dry_run=True,
            )
        )
        self.assertTrue(recovery_plan["ok"], recovery_plan)
        self.assertEqual(
            recovery_plan["transaction_state"],
            "partially_applied_without_receipt",
        )
        self.assertEqual(
            recovery_plan["recovery_action"],
            "rollback_uncommitted_memberships_to_before",
        )
        return before_bytes, recovery_plan

    def prepare_lock_only_recovery_transaction(
        self,
        archive_root: Path,
        fixture: dict[str, Any],
    ) -> tuple[list[bytes], dict[str, Any]]:
        before_bytes = [
            path.read_bytes()
            for path in fixture["member_paths"]
        ]
        self.run_activity_group_child_hard_exit(
            archive_root,
            fixture,
            mode="writer_before_snapshots",
            exit_code=94,
        )
        recovery_plan = (
            archive_services
            .activity_group_membership_recovery_plan(
                archive_root,
                expected_request_sha256=fixture["request_sha256"],
                dry_run=True,
            )
        )
        self.assertTrue(recovery_plan["ok"], recovery_plan)
        self.assertEqual(
            recovery_plan["transaction_state"],
            "lock_only_before_journal",
        )
        self.assertEqual(
            recovery_plan["recovery_action"],
            "cleanup_unstarted_lock",
        )
        return before_bytes, recovery_plan

    def prepare_recovery_evidence_case(
        self,
        tmp_root: Path,
        *,
        evidence_kind: str,
        suffix: str,
    ) -> dict[str, Any]:
        if evidence_kind not in {"journal", "lock"}:
            raise AssertionError("unsupported guard terminal test case")
        archive_root, fixture = self.create_fixture(
            tmp_root,
            suffix=suffix,
            member_count=2 if evidence_kind == "journal" else 1,
        )
        if evidence_kind == "journal":
            before_bytes, recovery_plan = (
                self.prepare_partial_recovery_transaction(
                    archive_root,
                    fixture,
                )
            )
        else:
            before_bytes, recovery_plan = (
                self.prepare_lock_only_recovery_transaction(
                    archive_root,
                    fixture,
                )
            )
        journal_path = (
            archive_services
            .activity_group_membership_transaction_journal_path(
                archive_root,
                fixture["request_sha256"],
            )
        )
        lock_path = self.writer_lock_path(archive_root)
        guard_path = self.recovery_guard_path(archive_root)
        semantic_path = (
            journal_path
            if evidence_kind == "journal"
            else lock_path
        )
        self.assertTrue(semantic_path.is_file())
        return {
            "evidence_kind": evidence_kind,
            "archive_root": archive_root,
            "fixture": fixture,
            "before_bytes": before_bytes,
            "recovery_plan": recovery_plan,
            "journal_path": journal_path,
            "lock_path": lock_path,
            "guard_path": guard_path,
            "semantic_path": semantic_path,
            "semantic_bytes": semantic_path.read_bytes(),
        }

    def assert_case_canonical_before(
        self,
        case: dict[str, Any],
    ) -> None:
        self.assertEqual(
            case["before_bytes"],
            [
                path.read_bytes()
                for path in case["fixture"]["member_paths"]
            ],
        )

    def assert_case_semantic_evidence_retained(
        self,
        case: dict[str, Any],
    ) -> None:
        self.assertEqual(
            case["semantic_bytes"],
            case["semantic_path"].read_bytes(),
        )
        self.assert_case_canonical_before(case)
        inventory = (
            archive_services.scan_activity_group_transaction_evidence(
                case["archive_root"]
            )
        )
        if case["evidence_kind"] == "journal":
            self.assertFalse(inventory["ok"], inventory)
            self.assertEqual(
                inventory["journal_paths"],
                [case["journal_path"]],
            )
            self.assertFalse(case["lock_path"].exists())
        else:
            self.assertTrue(inventory["ok"], inventory)
            self.assertEqual(inventory["journal_count"], 0)
            self.assertFalse(case["journal_path"].exists())
            self.assertTrue(case["lock_path"].is_file())

    def assert_failed_recovery_evidence_retained(
        self,
        result: dict[str, Any],
    ) -> None:
        self.assertFalse(result["ok"], result)
        self.assertFalse(result["approved"])
        self.assertEqual(
            result["status"],
            "failed_recovery_evidence_retained",
        )
        self.assertIn(
            "activity_group_recovery_execution_failed",
            result["blockers"],
        )
        self.assertIn(
            "activity_group_recovery_guard_retained",
            result["blockers"],
        )

    def assert_no_terminal_evidence_and_writer_retry(
        self,
        case: dict[str, Any],
    ) -> None:
        for evidence_path in (
            case["guard_path"],
            case["lock_path"],
            case["journal_path"],
        ):
            self.assertFalse(evidence_path.exists())
        self.assert_case_canonical_before(case)
        for member_path in case["fixture"]["member_paths"]:
            swap_path, previous_path = (
                archive_services.activity_group_canonical_swap_paths(
                    member_path,
                    case["fixture"]["request_sha256"],
                )
            )
            self.assertFalse(swap_path.exists())
            self.assertFalse(previous_path.exists())
        inventory = (
            archive_services.scan_activity_group_transaction_evidence(
                case["archive_root"]
            )
        )
        self.assertTrue(inventory["ok"], inventory)
        self.assertEqual(inventory["journal_count"], 0)
        no_evidence_plan = (
            archive_services.activity_group_membership_recovery_plan(
                case["archive_root"],
                expected_request_sha256=case["fixture"][
                    "request_sha256"
                ],
                dry_run=True,
            )
        )
        self.assertFalse(no_evidence_plan["ok"])
        self.assertEqual(no_evidence_plan["status"], "blocked")
        self.assertEqual(
            no_evidence_plan["transaction_state"],
            "no_recovery_evidence",
        )
        self.assertIsNone(no_evidence_plan["recovery_action"])
        self.assertEqual(
            no_evidence_plan["blockers"],
            ["activity_group_recovery_evidence_missing"],
        )
        retry = self.call_writer(
            case["archive_root"],
            case["fixture"],
        )
        self.assertTrue(retry["ok"], retry)
        self.assertEqual(retry["status"], "applied")
        for evidence_path in (
            case["guard_path"],
            case["lock_path"],
            case["journal_path"],
        ):
            self.assertFalse(evidence_path.exists())
        final_inventory = (
            archive_services.scan_activity_group_transaction_evidence(
                case["archive_root"]
            )
        )
        self.assertTrue(final_inventory["ok"], final_inventory)

    def assert_content_free(
        self,
        result: dict[str, Any],
        *,
        forbidden_values: tuple[str, ...],
    ) -> None:
        serialized = json.dumps(result, ensure_ascii=False)
        for value in forbidden_values:
            with self.subTest(forbidden_value=value):
                self.assertNotIn(value, serialized)

    def guarded_path_open(
        self,
        forbidden_read_paths: set[Path],
    ) -> Callable[..., Any]:
        real_path_open = Path.open
        normalized = {
            os.path.abspath(os.fspath(path))
            for path in forbidden_read_paths
        }

        def guarded_open(
            path: Path,
            mode: str = "r",
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            candidate = os.path.abspath(os.fspath(path))
            if candidate in normalized and "r" in mode:
                raise AssertionError(
                    "reserved transaction evidence content was read"
                )
            return real_path_open(path, mode, *args, **kwargs)

        return guarded_open

    @staticmethod
    def same_directory_entry(
        candidate: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        expected: Path,
    ) -> bool:
        candidate_path = Path(candidate)
        if candidate_path.name != expected.name:
            return False
        try:
            return os.path.samefile(
                candidate_path.parent,
                expected.parent,
            )
        except OSError:
            return (
                os.path.normcase(
                    os.path.realpath(candidate_path.parent)
                )
                == os.path.normcase(
                    os.path.realpath(expected.parent)
                )
            )

    @staticmethod
    def create_directory_reparse(
        link: Path,
        target: Path,
    ) -> None:
        link.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            completed = subprocess.run(
                [
                    "cmd.exe",
                    "/d",
                    "/c",
                    "mklink",
                    "/J",
                    str(link),
                    str(target),
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if completed.returncode != 0:
                raise OSError("Windows junction creation failed")
            return
        link.symlink_to(target, target_is_directory=True)

    @staticmethod
    def remove_directory_reparse(link: Path) -> None:
        if os.name == "nt":
            os.rmdir(link)
        else:
            link.unlink()

    def assert_writer_blocked_before_lock(
        self,
        archive_root: Path,
        fixture: dict[str, Any],
        *,
        expected_blocker: str,
        forbidden_read_paths: set[Path],
        forbidden_values: tuple[str, ...],
    ) -> dict[str, Any]:
        before = self.mutation_inventory(archive_root)
        write_lock_path = self.writer_lock_path(archive_root)
        real_os_open = os.open
        writer_lock_attempted = False

        def observe_os_open(
            path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            *args: Any,
            **kwargs: Any,
        ) -> int:
            nonlocal writer_lock_attempted
            if self.same_directory_entry(path, write_lock_path):
                writer_lock_attempted = True
            return real_os_open(path, *args, **kwargs)

        with (
            patch.object(
                Path,
                "open",
                new=self.guarded_path_open(forbidden_read_paths),
            ),
            patch.object(
                archive_services.os,
                "open",
                new=observe_os_open,
            ),
        ):
            result = self.call_writer(archive_root, fixture)

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blockers"], [expected_blocker])
        self.assertEqual(
            result["summary"]["canonical_write_attempt_count"],
            0,
        )
        self.assertFalse(writer_lock_attempted)
        self.assertFalse(write_lock_path.exists())
        self.assertEqual(before, self.mutation_inventory(archive_root))
        self.assert_content_free(
            result,
            forbidden_values=forbidden_values,
        )
        return result

    def test_writer_blocks_foreign_journals_before_lock_without_reading_or_echoing(
        self,
    ) -> None:
        cases = (
            ("add-root", ADD_JOURNAL_SUFFIX, False, False),
            (
                "reserved-removal-root",
                REMOVAL_JOURNAL_SUFFIX,
                False,
                False,
            ),
            ("oversized-add-root", ADD_JOURNAL_SUFFIX, True, False),
            ("same-request-add-root", ADD_JOURNAL_SUFFIX, False, True),
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            for index, (
                name,
                journal_suffix,
                oversized,
                matching_request,
            ) in enumerate(
                cases,
                start=1,
            ):
                with self.subTest(case=name):
                    archive_root, fixture = self.create_fixture(
                        tmp_root,
                        suffix=f"8{index}",
                    )
                    private_root = (
                        self.removal_private_root(archive_root)
                        if journal_suffix == REMOVAL_JOURNAL_SUFFIX
                        else self.add_private_root(archive_root)
                    )
                    private_root.mkdir(parents=True, exist_ok=True)
                    digest = (
                        fixture["request_sha256"].removeprefix(
                            "sha256:"
                        )
                        if matching_request
                        else str(index) * 64
                    )
                    if not matching_request:
                        self.assertNotEqual(
                            "sha256:" + digest,
                            fixture["request_sha256"],
                        )
                    journal_path = self.reserved_journal_path(
                        private_root,
                        digest=digest,
                        suffix=journal_suffix,
                    )
                    private_sentinel = (
                        f"PRIVATE_FOREIGN_JOURNAL_BODY_{name}"
                    )
                    with journal_path.open("wb") as handle:
                        handle.write(private_sentinel.encode("utf-8"))
                        if oversized:
                            handle.truncate(
                                archive_services
                                .ACTIVITY_GROUP_MEMBERSHIP_MAX_TRANSACTION_JOURNAL_BYTES
                                + 1
                            )
                    evidence_stat = journal_path.stat()

                    self.assert_writer_blocked_before_lock(
                        archive_root,
                        fixture,
                        expected_blocker=(
                            UNRESOLVED_EVIDENCE_BLOCKER
                        ),
                        forbidden_read_paths={journal_path},
                        forbidden_values=(
                            private_sentinel,
                            journal_path.name,
                            *(() if matching_request else (digest,)),
                            str(journal_path),
                        ),
                    )
                    retained_stat = journal_path.stat()
                    self.assertEqual(
                        evidence_stat.st_size,
                        retained_stat.st_size,
                    )
                    self.assertEqual(
                        evidence_stat.st_mtime_ns,
                        retained_stat.st_mtime_ns,
                    )

    def test_writer_blocks_malformed_managed_suffix_without_reading_it(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="83m",
            )
            journal_path = self.add_private_root(archive_root) / (
                ".malformed-private-digest"
                + ADD_JOURNAL_SUFFIX
            )
            private_sentinel = (
                "PRIVATE_MALFORMED_MANAGED_JOURNAL_BODY"
            )
            journal_path.write_text(
                private_sentinel,
                encoding="utf-8",
            )

            self.assert_writer_blocked_before_lock(
                archive_root,
                fixture,
                expected_blocker=UNRESOLVED_EVIDENCE_BLOCKER,
                forbidden_read_paths={journal_path},
                forbidden_values=(
                    private_sentinel,
                    journal_path.name,
                    str(journal_path),
                ),
            )
            self.assertTrue(journal_path.is_file())

    def test_writer_rescans_reserved_removal_journal_under_lock_before_snapshots(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="84",
                member_count=2,
            )
            removal_root = self.removal_private_root(archive_root)
            foreign_digest = "4" * 64
            journal_path = self.reserved_journal_path(
                removal_root,
                digest=foreign_digest,
                suffix=REMOVAL_JOURNAL_SUFFIX,
            )
            private_sentinel = (
                "PRIVATE_UNDER_LOCK_REMOVAL_JOURNAL_BODY"
            )
            write_lock_path = self.writer_lock_path(archive_root)
            before = self.mutation_inventory(archive_root)
            real_bound_write = (
                archive_services.write_activity_group_bytes_new_file_bound
            )
            evidence_injected = False
            observed_bound_write_paths: list[str] = []

            def inject_after_writer_lock_create(
                binding: dict[str, Any],
                path: Path,
                raw: bytes,
            ) -> None:
                nonlocal evidence_injected
                observed_bound_write_paths.append(str(path))
                real_bound_write(binding, path, raw)
                if (
                    not evidence_injected
                    and self.same_directory_entry(
                        path,
                        write_lock_path,
                    )
                ):
                    evidence_injected = True
                    removal_root.mkdir(parents=True, exist_ok=True)
                    journal_path.write_text(
                        private_sentinel,
                        encoding="utf-8",
                    )

            with (
                patch.object(
                    Path,
                    "open",
                    new=self.guarded_path_open({journal_path}),
                ),
                patch.object(
                    archive_services,
                    "write_activity_group_bytes_new_file_bound",
                    new=inject_after_writer_lock_create,
                ),
            ):
                result = self.call_writer(archive_root, fixture)

            self.assertTrue(
                evidence_injected,
                {
                    "result": result,
                    "observed_bound_write_paths": (
                        observed_bound_write_paths
                    ),
                    "expected_write_lock_path": str(write_lock_path),
                },
            )
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(
                result["blockers"],
                [UNRESOLVED_EVIDENCE_BLOCKER],
            )
            self.assertEqual(
                result["summary"]["canonical_write_attempt_count"],
                0,
            )
            self.assertFalse(write_lock_path.exists())
            self.assertTrue(journal_path.is_file())
            self.assertEqual(
                private_sentinel,
                journal_path.read_text(encoding="utf-8"),
            )
            self.assertEqual(before, self.mutation_inventory(archive_root))
            self.assert_content_free(
                result,
                forbidden_values=(
                    private_sentinel,
                    journal_path.name,
                    foreign_digest,
                    str(journal_path),
                ),
            )

    def test_recovery_holds_oversized_foreign_journal_without_reading_or_mutating(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="85",
            )
            removal_root = self.removal_private_root(archive_root)
            removal_root.mkdir(parents=True, exist_ok=True)
            foreign_digest = "5" * 64
            journal_path = self.reserved_journal_path(
                removal_root,
                digest=foreign_digest,
                suffix=REMOVAL_JOURNAL_SUFFIX,
            )
            private_sentinel = (
                "PRIVATE_RECOVERY_FOREIGN_JOURNAL_BODY"
            )
            with journal_path.open("wb") as handle:
                handle.write(private_sentinel.encode("utf-8"))
                handle.truncate(
                    archive_services
                    .ACTIVITY_GROUP_MEMBERSHIP_MAX_TRANSACTION_JOURNAL_BYTES
                    + 1
                )
            evidence_stat = journal_path.stat()
            before = self.mutation_inventory(archive_root)

            with patch.object(
                Path,
                "open",
                new=self.guarded_path_open({journal_path}),
            ):
                plan = (
                    archive_services
                    .activity_group_membership_recovery_plan(
                        archive_root,
                        expected_request_sha256=fixture[
                            "request_sha256"
                        ],
                        dry_run=True,
                    )
                )

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
            self.assertIn(
                UNRESOLVED_EVIDENCE_BLOCKER,
                plan["blockers"],
            )
            self.assertIn(
                "activity_group_recovery_manual_forensic_hold",
                plan["blockers"],
            )
            self.assertNotIn(
                "activity_group_recovery_evidence_missing",
                plan["blockers"],
            )
            self.assertEqual([], plan["would_change"])
            self.assertFalse(
                plan["approval_boundary"][
                    "manual_forensic_hold_executable"
                ]
            )
            self.assertTrue(
                plan["privacy_guards"]["writes"] is False
            )

            with patch.object(
                Path,
                "open",
                new=self.guarded_path_open({journal_path}),
            ):
                recover = (
                    archive_services.activity_group_membership_recover(
                        archive_root,
                        expected_request_sha256=fixture[
                            "request_sha256"
                        ],
                        expected_recovery_plan_sha256=plan[
                            "recovery_plan_sha256"
                        ],
                        approve=True,
                        reviewed_by=(
                            "person:activity-group-safety-reviewer"
                        ),
                        affirm_recovery_reviewed=True,
                    )
                )
            self.assertFalse(recover["ok"], recover)
            self.assertEqual(recover["status"], "blocked")
            self.assertIn(
                "plan:" + UNRESOLVED_EVIDENCE_BLOCKER,
                recover["blockers"],
            )
            self.assertIn(
                "recovery_action_not_executable",
                recover["blockers"],
            )
            self.assertFalse(self.writer_lock_path(archive_root).exists())
            self.assertFalse(self.recovery_guard_path(archive_root).exists())
            self.assertEqual(before, self.mutation_inventory(archive_root))
            retained_stat = journal_path.stat()
            self.assertEqual(
                evidence_stat.st_size,
                retained_stat.st_size,
            )
            self.assertEqual(
                evidence_stat.st_mtime_ns,
                retained_stat.st_mtime_ns,
            )
            self.assert_content_free(
                plan,
                forbidden_values=(
                    private_sentinel,
                    journal_path.name,
                    foreign_digest,
                    str(journal_path),
                ),
            )
            self.assert_content_free(
                recover,
                forbidden_values=(
                    private_sentinel,
                    journal_path.name,
                    foreign_digest,
                    str(journal_path),
                ),
            )

    def test_scanner_is_non_recursive_for_nested_reserved_suffix(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="86",
            )
            nested_root = (
                self.removal_private_root(archive_root)
                / "nested-private-material"
            )
            nested_root.mkdir(parents=True, exist_ok=True)
            nested_digest = "6" * 64
            nested_journal = self.reserved_journal_path(
                nested_root,
                digest=nested_digest,
                suffix=REMOVAL_JOURNAL_SUFFIX,
            )
            private_sentinel = (
                "PRIVATE_NESTED_RESERVED_JOURNAL_BODY"
            )
            nested_journal.write_text(
                private_sentinel,
                encoding="utf-8",
            )

            with patch.object(
                Path,
                "open",
                new=self.guarded_path_open({nested_journal}),
            ):
                result = self.call_writer(archive_root, fixture)

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status"], "applied")
            self.assertEqual(
                result["summary"]["canonical_write_attempt_count"],
                1,
            )
            self.assertTrue(nested_journal.is_file())
            self.assert_content_free(
                result,
                forbidden_values=(
                    private_sentinel,
                    nested_journal.name,
                    nested_digest,
                    str(nested_journal),
                ),
            )

    def test_writer_fails_closed_when_removal_scan_root_is_not_a_directory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="87",
            )
            removal_root = self.removal_private_root(archive_root)
            removal_root.parent.mkdir(parents=True, exist_ok=True)
            private_sentinel = (
                "PRIVATE_NON_DIRECTORY_REMOVAL_ROOT_BODY"
            )
            removal_root.write_text(
                private_sentinel,
                encoding="utf-8",
            )

            self.assert_writer_blocked_before_lock(
                archive_root,
                fixture,
                expected_blocker=EVIDENCE_SCAN_FAILED_BLOCKER,
                forbidden_read_paths={removal_root},
                forbidden_values=(
                    private_sentinel,
                    removal_root.name,
                    str(removal_root),
                ),
            )
            self.assertTrue(removal_root.is_file())

    def test_writer_blocks_reserved_journal_symlink_without_following_it(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            archive_root, fixture = self.create_fixture(
                tmp_root,
                suffix="88",
            )
            external_target = tmp_root / "external-private-journal"
            private_sentinel = (
                "PRIVATE_EXTERNAL_SYMLINK_JOURNAL_BODY"
            )
            external_target.write_text(
                private_sentinel,
                encoding="utf-8",
            )
            foreign_digest = "8" * 64
            journal_path = self.reserved_journal_path(
                self.add_private_root(archive_root),
                digest=foreign_digest,
                suffix=ADD_JOURNAL_SUFFIX,
            )
            try:
                journal_path.symlink_to(external_target)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(
                    f"file symlink unavailable on this platform: {exc}"
                )

            self.assert_writer_blocked_before_lock(
                archive_root,
                fixture,
                expected_blocker=UNRESOLVED_EVIDENCE_BLOCKER,
                forbidden_read_paths={journal_path, external_target},
                forbidden_values=(
                    private_sentinel,
                    journal_path.name,
                    foreign_digest,
                    str(journal_path),
                    str(external_target),
                ),
            )
            self.assertTrue(journal_path.is_symlink())
            self.assertEqual(
                private_sentinel,
                external_target.read_text(encoding="utf-8"),
            )

    def test_writer_fails_closed_when_removal_scan_root_is_a_symlink(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            archive_root, fixture = self.create_fixture(
                tmp_root,
                suffix="89",
            )
            external_root = tmp_root / "external-private-removal-root"
            external_root.mkdir()
            private_sentinel = (
                "PRIVATE_EXTERNAL_REMOVAL_ROOT_JOURNAL_BODY"
            )
            external_journal = self.reserved_journal_path(
                external_root,
                digest="9" * 64,
                suffix=REMOVAL_JOURNAL_SUFFIX,
            )
            external_journal.write_text(
                private_sentinel,
                encoding="utf-8",
            )
            removal_root = self.removal_private_root(archive_root)
            removal_root.parent.mkdir(parents=True, exist_ok=True)
            try:
                removal_root.symlink_to(
                    external_root,
                    target_is_directory=True,
                )
            except (NotImplementedError, OSError) as exc:
                self.skipTest(
                    f"directory symlink unavailable on this platform: {exc}"
                )

            self.assert_writer_blocked_before_lock(
                archive_root,
                fixture,
                expected_blocker=EVIDENCE_SCAN_FAILED_BLOCKER,
                forbidden_read_paths={external_journal},
                forbidden_values=(
                    private_sentinel,
                    external_journal.name,
                    str(external_journal),
                    str(external_root),
                ),
            )
            self.assertTrue(removal_root.is_symlink())
            self.assertTrue(external_journal.is_file())

    def test_writer_fails_closed_when_scan_entry_bound_is_exceeded(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="90",
            )
            removal_root = self.removal_private_root(archive_root)
            removal_root.mkdir(parents=True, exist_ok=True)
            for index in range(MAX_SCAN_ENTRIES + 1):
                (removal_root / f"bounded-scan-entry-{index:04d}").touch()
            private_filename = (
                f"bounded-scan-entry-{MAX_SCAN_ENTRIES:04d}"
            )

            self.assert_writer_blocked_before_lock(
                archive_root,
                fixture,
                expected_blocker=EVIDENCE_SCAN_FAILED_BLOCKER,
                forbidden_read_paths=set(),
                forbidden_values=(
                    private_filename,
                    str(removal_root),
                ),
            )
            self.assertEqual(
                MAX_SCAN_ENTRIES + 1,
                sum(1 for _ in removal_root.iterdir()),
            )

    def test_writer_fails_closed_for_windows_junction_scan_root(
        self,
    ) -> None:
        if os.name != "nt":
            self.skipTest("Windows junction contract")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            archive_root, fixture = self.create_fixture(
                tmp_root,
                suffix="91",
            )
            external_root = tmp_root / "external-removal-junction"
            external_root.mkdir()
            external_journal = self.reserved_journal_path(
                external_root,
                digest="a" * 64,
                suffix=REMOVAL_JOURNAL_SUFFIX,
            )
            private_sentinel = (
                "PRIVATE_WINDOWS_JUNCTION_JOURNAL_BODY"
            )
            external_journal.write_text(
                private_sentinel,
                encoding="utf-8",
            )
            removal_root = self.removal_private_root(archive_root)
            self.create_directory_reparse(
                removal_root,
                external_root,
            )
            try:
                self.assert_writer_blocked_before_lock(
                    archive_root,
                    fixture,
                    expected_blocker=EVIDENCE_SCAN_FAILED_BLOCKER,
                    forbidden_read_paths={external_journal},
                    forbidden_values=(
                        private_sentinel,
                        external_journal.name,
                        str(external_journal),
                        str(external_root),
                    ),
                )
                self.assertTrue(external_journal.is_file())
            finally:
                self.remove_directory_reparse(removal_root)

    def test_windows_scan_handle_blocks_directory_swap_and_restore(
        self,
    ) -> None:
        if os.name != "nt":
            self.skipTest("Windows directory-handle contract")
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="91s",
            )
            removal_root = self.removal_private_root(archive_root)
            removal_root.mkdir(parents=True, exist_ok=True)
            foreign_journal = self.reserved_journal_path(
                removal_root,
                digest="b" * 64,
                suffix=REMOVAL_JOURNAL_SUFFIX,
            )
            private_sentinel = "PRIVATE_SWAP_RESTORE_JOURNAL_BODY"
            foreign_journal.write_text(
                private_sentinel,
                encoding="utf-8",
            )
            hidden_root = removal_root.with_name(
                removal_root.name + "-hidden"
            )
            real_scandir = os.scandir
            swap_attempted = False
            swap_blocked = False

            def attempt_empty_directory_swap(
                path: Any,
            ) -> Any:
                nonlocal swap_attempted, swap_blocked
                if (
                    not swap_attempted
                    and isinstance(path, (str, bytes, os.PathLike))
                    and self.same_directory_entry(
                        Path(path) / "scan-probe",
                        removal_root / "scan-probe",
                    )
                ):
                    swap_attempted = True
                    try:
                        removal_root.rename(hidden_root)
                    except OSError:
                        swap_blocked = True
                        raise
                    try:
                        removal_root.mkdir()
                        iterator = real_scandir(removal_root)
                        os.rmdir(removal_root)
                        hidden_root.rename(removal_root)
                        return iterator
                    finally:
                        if hidden_root.exists():
                            if removal_root.exists():
                                os.rmdir(removal_root)
                            hidden_root.rename(removal_root)
                return real_scandir(path)

            with patch.object(
                archive_services.os,
                "scandir",
                new=attempt_empty_directory_swap,
            ):
                result = self.call_writer(
                    archive_root,
                    fixture,
                )

            self.assertTrue(swap_attempted)
            self.assertTrue(swap_blocked)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(
                result["blockers"],
                [EVIDENCE_SCAN_FAILED_BLOCKER],
            )
            self.assertTrue(foreign_journal.is_file())
            self.assertEqual(
                private_sentinel,
                foreign_journal.read_text(encoding="utf-8"),
            )
            self.assertFalse(
                self.writer_lock_path(archive_root).exists()
            )
            self.assert_content_free(
                result,
                forbidden_values=(
                    private_sentinel,
                    foreign_journal.name,
                    str(foreign_journal),
                ),
            )

    def test_scanner_rejects_parent_chain_reparse_swap(
        self,
    ) -> None:
        if os.name != "nt":
            self.skipTest("Windows parent-junction contract")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            archive_root, fixture = self.create_fixture(
                tmp_root,
                suffix="91p",
            )
            private_parent = (
                archive_root / ".wom-scratch" / "private"
            )
            request_bytes = fixture["request_path"].read_bytes()
            hidden_parent = private_parent.with_name(
                "private-original"
            )
            private_parent.rename(hidden_parent)
            original_add_root = hidden_parent / "activity-groups"
            foreign_journal = self.reserved_journal_path(
                original_add_root,
                digest="c" * 64,
                suffix=ADD_JOURNAL_SUFFIX,
            )
            private_sentinel = "PRIVATE_PARENT_SWAP_JOURNAL_BODY"
            foreign_journal.write_text(
                private_sentinel,
                encoding="utf-8",
            )
            external_parent = tmp_root / "external-private-parent"
            external_parent.mkdir()
            external_add_root = external_parent / "activity-groups"
            external_add_root.mkdir()
            (
                external_add_root / fixture["request_path"].name
            ).write_bytes(request_bytes)
            self.create_directory_reparse(
                private_parent,
                external_parent,
            )
            try:
                result = (
                    archive_services
                    .scan_activity_group_transaction_evidence(
                        archive_root,
                    )
                )
                self.assertFalse(result["ok"], result)
                self.assertFalse(result["complete"])
                self.assertEqual(
                    result["blockers"],
                    [EVIDENCE_SCAN_FAILED_BLOCKER],
                )
                self.assertTrue(foreign_journal.is_file())
                self.assertEqual(
                    private_sentinel,
                    foreign_journal.read_text(encoding="utf-8"),
                )
                self.assert_content_free(
                    result,
                    forbidden_values=(
                        private_sentinel,
                        foreign_journal.name,
                        str(foreign_journal),
                        str(hidden_parent),
                        str(external_parent),
                    ),
                )
            finally:
                self.remove_directory_reparse(private_parent)
                hidden_parent.rename(private_parent)

    def test_writer_rechecks_receipt_path_after_callback_before_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            archive_root, fixture = self.create_fixture(
                tmp_root,
                suffix="92",
                member_count=2,
            )
            external_root = tmp_root / "external-receipt-junction"
            external_root.mkdir()
            receipt_path = (
                archive_services
                .activity_group_membership_receipt_path(
                    archive_root,
                    fixture["request_sha256"],
                )
            )
            receipt_parent = receipt_path.parent
            swap_attempted = False
            swap_blocked = False
            injected = False

            def inject_receipt_parent_reparse(
                operation: str,
                state: str,
                current: int | None,
                total: int | None,
            ) -> None:
                del current, total
                nonlocal injected, swap_attempted, swap_blocked
                if (
                    not swap_attempted
                    and operation
                    == "activity-group-membership-receipt"
                    and state == "start"
                ):
                    swap_attempted = True
                    try:
                        self.create_directory_reparse(
                            receipt_parent,
                            external_root,
                        )
                    except OSError:
                        swap_blocked = True
                    else:
                        injected = True

            result = (
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
                        "person:activity-group-safety-reviewer"
                    ),
                    affirm_memberships_reviewed=True,
                    progress_callback=inject_receipt_parent_reparse,
                )
            )
            try:
                self.assertTrue(swap_attempted)
                self.assertTrue(swap_blocked)
                self.assertFalse(injected)
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["status"], "applied")
                self.assertFalse(
                    (external_root / receipt_path.name).exists()
                )
                self.assertTrue(receipt_path.is_file())
                self.assertFalse(
                    self.writer_lock_path(archive_root).exists()
                )
                self.assert_content_free(
                    result,
                    forbidden_values=(
                        str(external_root),
                        str(receipt_parent),
                    ),
                )
            finally:
                if injected:
                    self.remove_directory_reparse(receipt_parent)

    def test_rollback_closes_receipt_binding_before_empty_dir_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="92c",
            )
            receipt_path = (
                archive_services
                .activity_group_membership_receipt_path(
                    archive_root,
                    fixture["request_sha256"],
                )
            )
            receipt_parent = receipt_path.parent
            real_bound_directory_chain = (
                archive_services.activity_group_bound_directory_chain
            )
            real_cleanup_empty_archive_dirs = (
                archive_services.cleanup_empty_archive_dirs
            )
            receipt_binding_open = False
            receipt_binding_seen = False
            receipt_cleanup_seen = False

            @contextmanager
            def tracked_bound_directory_chain(
                root: Path,
                target: Path,
                *,
                create: bool = False,
            ) -> Any:
                nonlocal receipt_binding_open, receipt_binding_seen
                is_receipt_parent = target == receipt_parent
                try:
                    with real_bound_directory_chain(
                        root,
                        target,
                        create=create,
                    ) as binding:
                        if is_receipt_parent:
                            receipt_binding_open = True
                            receipt_binding_seen = True
                        yield binding
                finally:
                    if is_receipt_parent:
                        receipt_binding_open = False

            def guarded_cleanup_empty_archive_dirs(
                root: Path,
                paths: list[Path],
            ) -> None:
                nonlocal receipt_cleanup_seen
                if receipt_path in paths:
                    receipt_cleanup_seen = True
                    self.assertFalse(
                        receipt_binding_open,
                        "receipt parent cleanup ran before binding close",
                    )
                real_cleanup_empty_archive_dirs(root, paths)

            def fail_before_receipt_write(
                operation: str,
                state: str,
                current: int | None,
                total: int | None,
            ) -> None:
                del current, total
                if (
                    operation == "activity-group-membership-receipt"
                    and state == "start"
                ):
                    raise RuntimeError("synthetic pre-receipt failure")

            with (
                patch.object(
                    archive_services,
                    "activity_group_bound_directory_chain",
                    new=tracked_bound_directory_chain,
                ),
                patch.object(
                    archive_services,
                    "cleanup_empty_archive_dirs",
                    new=guarded_cleanup_empty_archive_dirs,
                ),
            ):
                result = (
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
                            "person:activity-group-safety-reviewer"
                        ),
                        affirm_memberships_reviewed=True,
                        progress_callback=fail_before_receipt_write,
                    )
                )

            self.assertTrue(receipt_binding_seen)
            self.assertTrue(receipt_cleanup_seen)
            self.assertFalse(receipt_binding_open)
            self.assertFalse(receipt_parent.exists())
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["status"], "failed_rolled_back")
            self.assertTrue(result["rollback"]["succeeded"], result)

    def test_canonical_compare_and_swap_preserves_last_moment_foreign_bytes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="cas-foreign",
            )
            canonical_path = (
                archive_root.resolve()
                / "zettels"
                / fixture["member_paths"][0].name
            )
            expected_bytes = canonical_path.read_bytes()
            replacement_bytes = expected_bytes + b"\nCAS_REPLACEMENT\n"
            foreign_bytes = expected_bytes + b"\nFOREIGN_CONCURRENT_EDIT\n"

            if os.name == "nt":
                primitive_name = (
                    "_replace_activity_group_file_with_backup_windows"
                )
            else:
                primitive_name = (
                    "_exchange_activity_group_entries_posix"
                )
            original_primitive = getattr(
                archive_services,
                primitive_name,
            )
            injected = False

            def inject_foreign_before_swap(
                *args: Any,
                **kwargs: Any,
            ) -> None:
                nonlocal injected
                if not injected:
                    injected = True
                    canonical_path.write_bytes(foreign_bytes)
                original_primitive(*args, **kwargs)

            with patch.object(
                archive_services,
                primitive_name,
                new=inject_foreign_before_swap,
            ):
                with self.assertRaises(OSError):
                    (
                        archive_services
                        .replace_activity_group_canonical_bytes_compare_and_swap(
                            archive_root.resolve(),
                            canonical_path,
                            expected_bytes=expected_bytes,
                            replacement_bytes=replacement_bytes,
                            request_sha256=fixture["request_sha256"],
                        )
                    )

            self.assertTrue(injected)
            self.assertEqual(foreign_bytes, canonical_path.read_bytes())

    def test_canonical_compare_and_swap_preserves_post_swap_foreign_bytes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="cas-post-swap-foreign",
            )
            canonical_path = (
                archive_root.resolve()
                / "zettels"
                / fixture["member_paths"][0].name
            )
            expected_bytes = canonical_path.read_bytes()
            replacement_bytes = expected_bytes + b"\nCAS_REPLACEMENT\n"
            foreign_bytes = expected_bytes + b"\nFOREIGN_AFTER_SWAP\n"
            primitive_name = (
                "_replace_activity_group_file_with_backup_windows"
                if os.name == "nt"
                else "_exchange_activity_group_entries_posix"
            )
            original_primitive = getattr(
                archive_services,
                primitive_name,
            )
            injected = False

            def inject_foreign_after_swap(
                *args: Any,
                **kwargs: Any,
            ) -> None:
                nonlocal injected
                original_primitive(*args, **kwargs)
                if not injected:
                    injected = True
                    canonical_path.write_bytes(foreign_bytes)

            with patch.object(
                archive_services,
                primitive_name,
                new=inject_foreign_after_swap,
            ):
                with self.assertRaises(OSError):
                    (
                        archive_services
                        .replace_activity_group_canonical_bytes_compare_and_swap(
                            archive_root.resolve(),
                            canonical_path,
                            expected_bytes=expected_bytes,
                            replacement_bytes=replacement_bytes,
                            request_sha256=fixture["request_sha256"],
                        )
                    )

            self.assertTrue(injected)
            self.assertEqual(foreign_bytes, canonical_path.read_bytes())

    def test_canonical_mismatch_restore_does_not_hide_newer_foreign_bytes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="cas-restore-race",
            )
            canonical_path = (
                archive_root.resolve()
                / "zettels"
                / fixture["member_paths"][0].name
            )
            expected_bytes = canonical_path.read_bytes()
            replacement_bytes = expected_bytes + b"\nCAS_REPLACEMENT\n"
            first_foreign = expected_bytes + b"\nFOREIGN_BEFORE_SWAP\n"
            newer_foreign = expected_bytes + b"\nFOREIGN_BEFORE_RESTORE\n"
            primitive_name = (
                "_replace_activity_group_file_with_backup_windows"
                if os.name == "nt"
                else "_exchange_activity_group_entries_posix"
            )
            original_primitive = getattr(
                archive_services,
                primitive_name,
            )
            original_no_replace = (
                archive_services._move_activity_group_entry_no_replace
            )
            before_swap_injected = False
            before_restore_injected = False

            def inject_first_foreign(
                *args: Any,
                **kwargs: Any,
            ) -> None:
                nonlocal before_swap_injected
                if not before_swap_injected:
                    before_swap_injected = True
                    canonical_path.write_bytes(first_foreign)
                original_primitive(*args, **kwargs)

            def inject_newer_foreign_before_capture(
                binding: dict[str, Any],
                source: Path,
                destination: Path,
            ) -> None:
                nonlocal before_restore_injected
                if (
                    not before_restore_injected
                    and source == canonical_path
                ):
                    before_restore_injected = True
                    canonical_path.write_bytes(newer_foreign)
                original_no_replace(
                    binding,
                    source,
                    destination,
                )

            with (
                patch.object(
                    archive_services,
                    primitive_name,
                    new=inject_first_foreign,
                ),
                patch.object(
                    archive_services,
                    "_move_activity_group_entry_no_replace",
                    new=inject_newer_foreign_before_capture,
                ),
            ):
                with self.assertRaises(OSError):
                    (
                        archive_services
                        .replace_activity_group_canonical_bytes_compare_and_swap(
                            archive_root.resolve(),
                            canonical_path,
                            expected_bytes=expected_bytes,
                            replacement_bytes=replacement_bytes,
                            request_sha256=fixture["request_sha256"],
                        )
                    )

            self.assertTrue(before_swap_injected)
            self.assertTrue(before_restore_injected)
            self.assertEqual(newer_foreign, canonical_path.read_bytes())

    def test_writer_rollback_never_overwrites_unknown_participant_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="rollback-drift",
                member_count=2,
            )
            first_member, second_member = fixture["member_paths"]
            second_before = second_member.read_bytes()
            foreign_bytes = (
                first_member.read_bytes()
                + b"\nFOREIGN_DURING_RUNTIME_ROLLBACK\n"
            )
            original_compare_and_swap = (
                archive_services
                .replace_activity_group_canonical_bytes_compare_and_swap
            )
            forward_attempts = 0

            def drift_then_fail_second_forward(
                root: Path,
                path: Path,
                **kwargs: Any,
            ) -> bool:
                nonlocal forward_attempts
                if not kwargs.get("allow_already_replacement", False):
                    forward_attempts += 1
                    if forward_attempts == 2:
                        first_member.write_bytes(foreign_bytes)
                        raise OSError(
                            "PRIVATE_SECOND_FORWARD_FAILURE_AFTER_DRIFT"
                        )
                return original_compare_and_swap(
                    root,
                    path,
                    **kwargs,
                )

            with patch.object(
                archive_services,
                (
                    "replace_activity_group_canonical_bytes_"
                    "compare_and_swap"
                ),
                new=drift_then_fail_second_forward,
            ):
                result = self.call_writer(archive_root, fixture)

            self.assertFalse(result["ok"], result)
            self.assertEqual(
                result["status"],
                "failed_rollback_incomplete",
            )
            self.assertFalse(result["rollback"]["succeeded"])
            self.assertEqual(foreign_bytes, first_member.read_bytes())
            self.assertEqual(second_before, second_member.read_bytes())
            self.assertTrue(
                archive_services
                .activity_group_membership_transaction_journal_path(
                    archive_root,
                    fixture["request_sha256"],
                )
                .is_file()
            )
            self.assertTrue(self.writer_lock_path(archive_root).is_file())

    def test_writer_final_inventory_rejects_foreign_journal_after_own_unlink(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="final-inventory",
            )
            own_journal = (
                archive_services
                .activity_group_membership_transaction_journal_path(
                    archive_root,
                    fixture["request_sha256"],
                )
            )
            foreign_journal = self.reserved_journal_path(
                self.removal_private_root(archive_root),
                digest="f" * 64,
                suffix=REMOVAL_JOURNAL_SUFFIX,
            )
            original_delete = (
                archive_services.delete_activity_group_evidence_exact
            )
            injected = False

            def inject_foreign_after_own_journal_delete(
                root: Path,
                path: Path,
                **kwargs: Any,
            ) -> None:
                nonlocal injected
                original_delete(root, path, **kwargs)
                if path == own_journal and not injected:
                    injected = True
                    foreign_journal.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    foreign_journal.write_bytes(b"FOREIGN_RESERVED_EVIDENCE")

            with patch.object(
                archive_services,
                "delete_activity_group_evidence_exact",
                new=inject_foreign_after_own_journal_delete,
            ):
                result = self.call_writer(archive_root, fixture)

            self.assertTrue(injected)
            self.assertFalse(result["ok"], result)
            self.assertEqual(
                result["status"],
                "applied_evidence_conflict",
            )
            self.assertIn(
                UNRESOLVED_EVIDENCE_BLOCKER,
                result["blockers"],
            )
            self.assertFalse(own_journal.exists())
            self.assertTrue(foreign_journal.is_file())
            self.assertFalse(self.writer_lock_path(archive_root).exists())

    def test_writer_retains_same_name_replacement_lock_after_receipt_commit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="writer-lock-replacement",
            )
            lock_path = self.writer_lock_path(archive_root)
            journal_path = (
                archive_services
                .activity_group_membership_transaction_journal_path(
                    archive_root,
                    fixture["request_sha256"],
                )
            )
            receipt_path = archive_root / (
                archive_services
                .activity_group_membership_receipt_relative_path(
                    fixture["request_sha256"]
                )
            )
            original_read_lock = (
                archive_services
                .read_activity_group_membership_write_lock
            )
            replacement_raw = b""
            injected = False

            def replace_lock_before_success_cleanup(
                root: Path,
                path: Path,
                **kwargs: Any,
            ) -> tuple[bytes, dict[str, Any]]:
                nonlocal injected, replacement_raw
                if (
                    not injected
                    and path.name == lock_path.name
                    and path.parent.resolve()
                    == lock_path.parent.resolve()
                    and receipt_path.is_file()
                ):
                    document = json.loads(
                        lock_path.read_text(encoding="utf-8")
                    )
                    document["review_plan_sha256"] = (
                        "sha256:" + "f" * 64
                    )
                    replacement_raw = (
                        json.dumps(
                            document,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                    lock_path.write_bytes(replacement_raw)
                    injected = True
                return original_read_lock(root, path, **kwargs)

            with patch.object(
                archive_services,
                "read_activity_group_membership_write_lock",
                new=replace_lock_before_success_cleanup,
            ):
                result = self.call_writer(archive_root, fixture)

            self.assertTrue(injected)
            self.assertFalse(result["ok"], result)
            self.assertEqual(
                result["status"],
                "applied_evidence_conflict",
            )
            self.assertEqual(replacement_raw, lock_path.read_bytes())
            self.assertTrue(journal_path.is_file())
            self.assertTrue(receipt_path.is_file())

    def test_hard_exit_after_atomic_swap_is_recoverable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="swap-hard-exit",
            )
            before_bytes = fixture["member_paths"][0].read_bytes()
            if os.name == "nt":
                primitive_name = (
                    "_replace_activity_group_file_with_backup_windows"
                )
            else:
                primitive_name = (
                    "_exchange_activity_group_entries_posix"
                )
            original_primitive = getattr(
                archive_services,
                primitive_name,
            )
            interrupted = False

            def interrupt_after_swap(
                *args: Any,
                **kwargs: Any,
            ) -> None:
                nonlocal interrupted
                original_primitive(*args, **kwargs)
                if not interrupted:
                    interrupted = True
                    raise KeyboardInterrupt(
                        "PRIVATE_EXIT_AFTER_ATOMIC_SWAP"
                    )

            with patch.object(
                archive_services,
                primitive_name,
                new=interrupt_after_swap,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self.call_writer(archive_root, fixture)

            self.assertTrue(interrupted)
            plan = (
                archive_services
                .activity_group_membership_recovery_plan(
                    archive_root,
                    expected_request_sha256=fixture["request_sha256"],
                    dry_run=True,
                )
            )
            self.assertTrue(plan["ok"], plan)
            self.assertEqual(
                plan["recovery_action"],
                "rollback_uncommitted_memberships_to_before",
            )
            recovered = (
                archive_services.activity_group_membership_recover(
                    archive_root,
                    expected_request_sha256=fixture["request_sha256"],
                    expected_recovery_plan_sha256=(
                        plan["recovery_plan_sha256"]
                    ),
                    approve=True,
                    reviewed_by="person:activity-group-safety-reviewer",
                    affirm_recovery_reviewed=True,
                )
            )
            self.assertTrue(recovered["ok"], recovered)
            self.assertEqual(recovered["status"], "recovered")
            self.assertEqual(
                before_bytes,
                fixture["member_paths"][0].read_bytes(),
            )

    def test_recovery_hard_exit_after_exact_journal_delete_is_not_stranded(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case = self.prepare_recovery_evidence_case(
                Path(tmp),
                evidence_kind="journal",
                suffix="recovery-journal-delete-hard-exit",
            )
            self.run_activity_group_child_hard_exit(
                case["archive_root"],
                case["fixture"],
                mode="recovery_after_delete",
                recovery_plan_sha256=case["recovery_plan"][
                    "recovery_plan_sha256"
                ],
                target_path=case["journal_path"],
                exit_code=92,
            )
            self.assert_no_terminal_evidence_and_writer_retry(case)

    def test_lock_only_recovery_hard_exit_after_exact_lock_delete_is_not_stranded(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case = self.prepare_recovery_evidence_case(
                Path(tmp),
                evidence_kind="lock",
                suffix="recovery-lock-delete-hard-exit",
            )
            self.run_activity_group_child_hard_exit(
                case["archive_root"],
                case["fixture"],
                mode="recovery_after_delete",
                recovery_plan_sha256=case["recovery_plan"][
                    "recovery_plan_sha256"
                ],
                target_path=case["lock_path"],
                exit_code=93,
            )
            self.assert_no_terminal_evidence_and_writer_retry(case)

    def test_recovery_guard_delete_failure_retains_last_semantic_evidence(
        self,
    ) -> None:
        for evidence_kind in ("journal", "lock"):
            with self.subTest(evidence_kind=evidence_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    case = self.prepare_recovery_evidence_case(
                        Path(tmp),
                        evidence_kind=evidence_kind,
                        suffix=(
                            "guard-delete-failure-" + evidence_kind
                        ),
                    )
                    original_delete = (
                        archive_services
                        .delete_activity_group_evidence_exact
                    )
                    guard_delete_attempts = 0

                    def fail_exact_guard_delete(
                        root: Path,
                        path: Path,
                        *args: Any,
                        **kwargs: Any,
                    ) -> None:
                        nonlocal guard_delete_attempts
                        if self.same_directory_entry(
                            path,
                            case["guard_path"],
                        ):
                            guard_delete_attempts += 1
                            raise OSError(
                                "PRIVATE_EXACT_GUARD_DELETE_FAILURE"
                            )
                        original_delete(
                            root,
                            path,
                            *args,
                            **kwargs,
                        )

                    with patch.object(
                        archive_services,
                        "delete_activity_group_evidence_exact",
                        new=fail_exact_guard_delete,
                    ):
                        result = self.call_recovery(
                            case["archive_root"],
                            case["fixture"],
                            case["recovery_plan"],
                        )

                    self.assertEqual(guard_delete_attempts, 1)
                    self.assert_failed_recovery_evidence_retained(
                        result
                    )
                    self.assertTrue(case["guard_path"].is_file())
                    self.assert_case_semantic_evidence_retained(case)

    def test_recovery_guard_same_name_replacement_is_never_redeleted(
        self,
    ) -> None:
        for evidence_kind in ("journal", "lock"):
            with self.subTest(evidence_kind=evidence_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    case = self.prepare_recovery_evidence_case(
                        Path(tmp),
                        evidence_kind=evidence_kind,
                        suffix=(
                            "guard-replacement-" + evidence_kind
                        ),
                    )
                    original_delete = (
                        archive_services
                        .delete_activity_group_evidence_exact
                    )
                    guard_delete_calls = 0
                    replacement_guard_bytes: bytes | None = None

                    def replace_guard_after_exact_delete(
                        root: Path,
                        path: Path,
                        *args: Any,
                        **kwargs: Any,
                    ) -> None:
                        nonlocal guard_delete_calls, replacement_guard_bytes
                        is_guard = self.same_directory_entry(
                            path,
                            case["guard_path"],
                        )
                        if is_guard:
                            guard_delete_calls += 1
                            if guard_delete_calls == 1:
                                replacement_guard_bytes = (
                                    case["guard_path"].read_bytes()
                                )
                        original_delete(
                            root,
                            path,
                            *args,
                            **kwargs,
                        )
                        if is_guard and guard_delete_calls == 1:
                            assert replacement_guard_bytes is not None
                            case["guard_path"].write_bytes(
                                replacement_guard_bytes
                            )

                    with patch.object(
                        archive_services,
                        "delete_activity_group_evidence_exact",
                        new=replace_guard_after_exact_delete,
                    ):
                        result = self.call_recovery(
                            case["archive_root"],
                            case["fixture"],
                            case["recovery_plan"],
                        )

                    self.assertEqual(guard_delete_calls, 1)
                    self.assert_failed_recovery_evidence_retained(
                        result
                    )
                    self.assertIsNotNone(replacement_guard_bytes)
                    self.assertEqual(
                        replacement_guard_bytes,
                        case["guard_path"].read_bytes(),
                    )
                    self.assert_case_semantic_evidence_retained(case)

    def test_hard_exit_after_guard_delete_leaves_semantic_evidence_recoverable(
        self,
    ) -> None:
        expected_retry = {
            "journal": (
                "prepared_not_started",
                "cleanup_unstarted_transaction_evidence",
            ),
            "lock": (
                "lock_only_before_journal",
                "cleanup_unstarted_lock",
            ),
        }
        for index, evidence_kind in enumerate(
            ("journal", "lock"),
            start=1,
        ):
            with self.subTest(evidence_kind=evidence_kind):
                with tempfile.TemporaryDirectory() as tmp:
                    case = self.prepare_recovery_evidence_case(
                        Path(tmp),
                        evidence_kind=evidence_kind,
                        suffix=(
                            "guard-delete-hard-exit-" + evidence_kind
                        ),
                    )
                    self.run_activity_group_child_hard_exit(
                        case["archive_root"],
                        case["fixture"],
                        mode="recovery_after_delete",
                        recovery_plan_sha256=case[
                            "recovery_plan"
                        ]["recovery_plan_sha256"],
                        target_path=case["guard_path"],
                        exit_code=95 + index,
                    )

                    self.assertFalse(case["guard_path"].exists())
                    self.assert_case_semantic_evidence_retained(case)

                    retry_plan = (
                        archive_services
                        .activity_group_membership_recovery_plan(
                            case["archive_root"],
                            expected_request_sha256=case["fixture"][
                                "request_sha256"
                            ],
                            dry_run=True,
                        )
                    )
                    self.assertTrue(retry_plan["ok"], retry_plan)
                    self.assertEqual(
                        (
                            retry_plan["transaction_state"],
                            retry_plan["recovery_action"],
                        ),
                        expected_retry[evidence_kind],
                    )
                    recovered = self.call_recovery(
                        case["archive_root"],
                        case["fixture"],
                        retry_plan,
                    )
                    self.assertTrue(recovered["ok"], recovered)
                    self.assertEqual(
                        recovered["status"],
                        "cleanup_completed",
                    )
                    self.assertFalse(case["guard_path"].exists())
                    self.assertFalse(case["lock_path"].exists())
                    self.assertFalse(case["journal_path"].exists())
                    final_inventory = (
                        archive_services
                        .scan_activity_group_transaction_evidence(
                            case["archive_root"]
                        )
                    )
                    self.assertTrue(
                        final_inventory["ok"],
                        final_inventory,
                    )

    def test_recovery_compare_and_swap_preserves_post_classification_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="recovery-cas-drift",
                member_count=2,
            )
            original_compare_and_swap = (
                archive_services
                .replace_activity_group_canonical_bytes_compare_and_swap
            )
            forward_attempts = 0

            def interrupt_second_forward(
                root: Path,
                path: Path,
                **kwargs: Any,
            ) -> bool:
                nonlocal forward_attempts
                if not kwargs.get("allow_already_replacement", False):
                    forward_attempts += 1
                    if forward_attempts == 2:
                        raise KeyboardInterrupt(
                            "PRIVATE_PARTIAL_RECOVERY_SETUP"
                        )
                return original_compare_and_swap(
                    root,
                    path,
                    **kwargs,
                )

            with patch.object(
                archive_services,
                (
                    "replace_activity_group_canonical_bytes_"
                    "compare_and_swap"
                ),
                new=interrupt_second_forward,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self.call_writer(archive_root, fixture)

            plan = (
                archive_services
                .activity_group_membership_recovery_plan(
                    archive_root,
                    expected_request_sha256=fixture["request_sha256"],
                    dry_run=True,
                )
            )
            self.assertTrue(plan["ok"], plan)
            drifted_member = fixture["member_paths"][0]
            foreign_bytes = (
                drifted_member.read_bytes()
                + b"\nFOREIGN_AFTER_RECOVERY_CLASSIFICATION\n"
            )
            drift_injected = False

            def inject_drift_inside_recovery_cas(
                root: Path,
                path: Path,
                **kwargs: Any,
            ) -> bool:
                nonlocal drift_injected
                if (
                    kwargs.get("allow_already_replacement", False)
                    and not drift_injected
                ):
                    drift_injected = True
                    path.write_bytes(foreign_bytes)
                return original_compare_and_swap(
                    root,
                    path,
                    **kwargs,
                )

            with patch.object(
                archive_services,
                (
                    "replace_activity_group_canonical_bytes_"
                    "compare_and_swap"
                ),
                new=inject_drift_inside_recovery_cas,
            ):
                recovered = (
                    archive_services.activity_group_membership_recover(
                        archive_root,
                        expected_request_sha256=fixture[
                            "request_sha256"
                        ],
                        expected_recovery_plan_sha256=(
                            plan["recovery_plan_sha256"]
                        ),
                        approve=True,
                        reviewed_by=(
                            "person:activity-group-safety-reviewer"
                        ),
                        affirm_recovery_reviewed=True,
                    )
                )

            self.assertTrue(drift_injected)
            self.assertFalse(recovered["ok"], recovered)
            self.assertEqual(
                recovered["status"],
                "failed_recovery_evidence_retained",
            )
            self.assertEqual(foreign_bytes, drifted_member.read_bytes())
            self.assertTrue(
                archive_services
                .activity_group_membership_transaction_journal_path(
                    archive_root,
                    fixture["request_sha256"],
                )
                .is_file()
            )

    def test_recovery_rejects_same_name_missing_lock_claim_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root, fixture = self.create_fixture(
                Path(tmp),
                suffix="claim-replacement",
                member_count=2,
            )
            original_compare_and_swap = (
                archive_services
                .replace_activity_group_canonical_bytes_compare_and_swap
            )
            attempts = 0

            def interrupt_second_forward(
                root: Path,
                path: Path,
                **kwargs: Any,
            ) -> bool:
                nonlocal attempts
                attempts += 1
                if attempts == 2:
                    raise KeyboardInterrupt(
                        "PRIVATE_CLAIM_REPLACEMENT_SETUP"
                    )
                return original_compare_and_swap(
                    root,
                    path,
                    **kwargs,
                )

            with patch.object(
                archive_services,
                (
                    "replace_activity_group_canonical_bytes_"
                    "compare_and_swap"
                ),
                new=interrupt_second_forward,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self.call_writer(archive_root, fixture)

            lock_path = self.writer_lock_path(archive_root)
            lock_path.unlink()
            plan = (
                archive_services
                .activity_group_membership_recovery_plan(
                    archive_root,
                    expected_request_sha256=fixture["request_sha256"],
                    dry_run=True,
                )
            )
            self.assertTrue(plan["ok"], plan)
            original_bound_write = (
                archive_services.write_activity_group_bytes_new_file_bound
            )
            replacement_raw = b""
            injected = False

            def replace_claim_after_exclusive_create(
                binding: dict[str, Any],
                path: Path,
                raw: bytes,
            ) -> None:
                nonlocal injected, replacement_raw
                original_bound_write(binding, path, raw)
                if (
                    not injected
                    and path.name
                    == archive_services
                    .ACTIVITY_GROUP_MEMBERSHIP_WRITE_LOCK_NAME
                ):
                    document = json.loads(raw.decode("utf-8"))
                    replacement_raw = (
                        json.dumps(
                            document,
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n"
                    ).encode("utf-8")
                    path.write_bytes(replacement_raw)
                    injected = True

            with patch.object(
                archive_services,
                "write_activity_group_bytes_new_file_bound",
                new=replace_claim_after_exclusive_create,
            ):
                recovered = (
                    archive_services
                    .activity_group_membership_recover(
                        archive_root,
                        expected_request_sha256=fixture[
                            "request_sha256"
                        ],
                        expected_recovery_plan_sha256=(
                            plan["recovery_plan_sha256"]
                        ),
                        approve=True,
                        reviewed_by=(
                            "person:activity-group-safety-reviewer"
                        ),
                        affirm_recovery_reviewed=True,
                    )
                )

            self.assertTrue(injected)
            self.assertFalse(recovered["ok"], recovered)
            self.assertEqual(
                recovered["status"],
                "failed_recovery_evidence_retained",
            )
            self.assertEqual(replacement_raw, lock_path.read_bytes())
            self.assertTrue(
                archive_services
                .activity_group_membership_transaction_journal_path(
                    archive_root,
                    fixture["request_sha256"],
                )
                .is_file()
            )

    @unittest.skipIf(os.name == "nt", "POSIX descriptor-relative contract")
    def test_posix_exact_delete_preserves_same_name_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            evidence_parent = archive_root / ".wom-scratch" / "private"
            evidence_parent.mkdir(parents=True)
            evidence_path = evidence_parent / "reviewed.json"
            evidence_bytes = b'{"reviewed":true}\n'
            foreign_bytes = b'{"foreign":true}\n'
            evidence_path.write_bytes(evidence_bytes)
            foreign_staging = evidence_parent / "foreign-staging"
            foreign_staging.write_bytes(foreign_bytes)
            original_rename = archive_services.os.rename
            injected = False

            def replace_immediately_before_capture(
                source: Any,
                destination: Any,
                *args: Any,
                **kwargs: Any,
            ) -> None:
                nonlocal injected
                if (
                    not injected
                    and os.fspath(source) == evidence_path.name
                    and os.fspath(destination) == "evidence"
                ):
                    injected = True
                    source_dir_fd = kwargs.get("src_dir_fd")
                    original_rename(
                        foreign_staging.name,
                        evidence_path.name,
                        src_dir_fd=source_dir_fd,
                        dst_dir_fd=source_dir_fd,
                    )
                original_rename(
                    source,
                    destination,
                    *args,
                    **kwargs,
                )

            with patch.object(
                archive_services.os,
                "rename",
                new=replace_immediately_before_capture,
            ):
                with self.assertRaises(OSError):
                    archive_services.delete_activity_group_evidence_exact(
                        archive_root,
                        evidence_path,
                        expected_sha256=(
                            "sha256:"
                            + hashlib.sha256(evidence_bytes).hexdigest()
                        ),
                        max_bytes=1024,
                    )

            self.assertTrue(injected)
            self.assertEqual(foreign_bytes, evidence_path.read_bytes())

    @unittest.skipIf(os.name == "nt", "POSIX open-fd mutation contract")
    def test_posix_exact_delete_rejects_in_place_mutation_after_first_hash(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            evidence_parent = archive_root / ".wom-scratch" / "private"
            evidence_parent.mkdir(parents=True)
            evidence_path = evidence_parent / "reviewed.json"
            evidence_bytes = b'{"reviewed":true}\n'
            foreign_bytes = b'{"reviewed":null}\n'
            self.assertEqual(len(evidence_bytes), len(foreign_bytes))
            evidence_path.write_bytes(evidence_bytes)
            writer_descriptor = os.open(
                evidence_path,
                os.O_WRONLY,
            )
            original_lseek = archive_services.os.lseek
            injected = False

            def mutate_before_stable_rewind(
                descriptor: int,
                offset: int,
                whence: int,
            ) -> int:
                nonlocal injected
                if not injected:
                    injected = True
                    original_lseek(
                        writer_descriptor,
                        0,
                        os.SEEK_SET,
                    )
                    os.write(writer_descriptor, foreign_bytes)
                    os.fsync(writer_descriptor)
                return original_lseek(descriptor, offset, whence)

            try:
                with patch.object(
                    archive_services.os,
                    "lseek",
                    new=mutate_before_stable_rewind,
                ):
                    with self.assertRaises(OSError):
                        (
                            archive_services
                            .delete_activity_group_evidence_exact(
                                archive_root,
                                evidence_path,
                                expected_sha256=(
                                    "sha256:"
                                    + hashlib.sha256(
                                        evidence_bytes
                                    ).hexdigest()
                                ),
                                max_bytes=1024,
                            )
                        )
            finally:
                os.close(writer_descriptor)

            self.assertTrue(injected)
            self.assertEqual(foreign_bytes, evidence_path.read_bytes())

    @unittest.skipIf(os.name == "nt", "POSIX hard-exit quarantine contract")
    def test_posix_exact_delete_hard_exit_quarantine_is_globally_discoverable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            evidence_path = (
                archive_root
                / "zettels"
                / (
                    ".reviewed"
                    + archive_services
                    .ACTIVITY_GROUP_MEMBERSHIP_CANONICAL_SWAP_SUFFIX
                )
            )
            evidence_path.parent.mkdir(parents=True)
            evidence_bytes = b"REVIEWED_SWAP_RESIDUE\n"
            evidence_path.write_bytes(evidence_bytes)
            child_source = """
import hashlib
import os
from pathlib import Path
from wom_kit import archive_services

root = Path(os.environ["WOM_TEST_ARCHIVE_ROOT"])
path = Path(os.environ["WOM_TEST_EVIDENCE_PATH"])
expected = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
original_rename = archive_services.os.rename

def exit_after_capture(*args, **kwargs):
    original_rename(*args, **kwargs)
    os._exit(91)

archive_services.os.rename = exit_after_capture
archive_services.delete_activity_group_evidence_exact(
    root,
    path,
    expected_sha256=expected,
    max_bytes=1024,
)
"""
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(SRC_ROOT)
            environment["WOM_TEST_ARCHIVE_ROOT"] = str(
                archive_root
            )
            environment["WOM_TEST_EVIDENCE_PATH"] = str(
                evidence_path
            )
            completed = subprocess.run(
                [sys.executable, "-c", child_source],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                91,
                completed.stdout + completed.stderr,
            )
            self.assertFalse(evidence_path.exists())
            inventory = (
                archive_services.scan_activity_group_transaction_evidence(
                    archive_root
                )
            )
            self.assertFalse(inventory["ok"], inventory)
            self.assertEqual(inventory["journal_count"], 1)
            quarantine_path = inventory["journal_paths"][0]
            self.assertEqual(
                self.add_private_root(archive_root),
                quarantine_path.parent,
            )
            self.assertTrue(quarantine_path.is_dir())
            self.assertEqual(
                evidence_bytes,
                (quarantine_path / "evidence").read_bytes(),
            )

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_recovery_claim_stays_under_held_private_root_binding(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            archive_root, fixture = self.create_fixture(
                tmp_root,
                suffix="recovery-claim-binding",
                member_count=2,
            )
            original_compare_and_swap = (
                archive_services
                .replace_activity_group_canonical_bytes_compare_and_swap
            )
            attempts = 0

            def interrupt_second_forward(
                root: Path,
                path: Path,
                **kwargs: Any,
            ) -> bool:
                nonlocal attempts
                attempts += 1
                if attempts == 2:
                    raise KeyboardInterrupt(
                        "PRIVATE_MISSING_LOCK_BINDING_SETUP"
                    )
                return original_compare_and_swap(
                    root,
                    path,
                    **kwargs,
                )

            with patch.object(
                archive_services,
                (
                    "replace_activity_group_canonical_bytes_"
                    "compare_and_swap"
                ),
                new=interrupt_second_forward,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    self.call_writer(archive_root, fixture)

            self.writer_lock_path(archive_root).unlink()
            plan = (
                archive_services
                .activity_group_membership_recovery_plan(
                    archive_root,
                    expected_request_sha256=fixture["request_sha256"],
                    dry_run=True,
                )
            )
            self.assertTrue(plan["ok"], plan)
            private_root = self.add_private_root(archive_root)
            hidden_root = private_root.with_name(
                private_root.name + "-hidden"
            )
            external_root = tmp_root / "external-private-root"
            external_root.mkdir()
            original_bound_write = (
                archive_services.write_activity_group_bytes_new_file_bound
            )
            swap_attempted = False
            swap_blocked = False

            def attempt_private_root_swap_before_claim(
                binding: dict[str, Any],
                path: Path,
                raw: bytes,
            ) -> None:
                nonlocal swap_attempted, swap_blocked
                if (
                    path.name
                    == archive_services
                    .ACTIVITY_GROUP_MEMBERSHIP_WRITE_LOCK_NAME
                    and not swap_attempted
                ):
                    swap_attempted = True
                    try:
                        private_root.rename(hidden_root)
                    except OSError:
                        swap_blocked = True
                    else:
                        self.create_directory_reparse(
                            private_root,
                            external_root,
                        )
                original_bound_write(binding, path, raw)

            with patch.object(
                archive_services,
                "write_activity_group_bytes_new_file_bound",
                new=attempt_private_root_swap_before_claim,
            ):
                recovered = (
                    archive_services.activity_group_membership_recover(
                        archive_root,
                        expected_request_sha256=fixture[
                            "request_sha256"
                        ],
                        expected_recovery_plan_sha256=(
                            plan["recovery_plan_sha256"]
                        ),
                        approve=True,
                        reviewed_by=(
                            "person:activity-group-safety-reviewer"
                        ),
                        affirm_recovery_reviewed=True,
                    )
                )

            try:
                self.assertTrue(swap_attempted)
                self.assertTrue(swap_blocked)
                self.assertTrue(recovered["ok"], recovered)
                self.assertEqual(list(external_root.iterdir()), [])
            finally:
                if private_root.is_symlink():
                    self.remove_directory_reparse(private_root)
                if hidden_root.exists() and not private_root.exists():
                    hidden_root.rename(private_root)


if __name__ == "__main__":
    unittest.main()
