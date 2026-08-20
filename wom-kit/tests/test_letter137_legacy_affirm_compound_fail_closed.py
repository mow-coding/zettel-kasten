from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType
from unittest import mock

from wom_kit import archive_cli, archive_services, completion_workflows


COMPOUND_APPROVAL_BLOCKER = "compound_exact_human_approval_binding_required"
PRIVATE_CLI_ROOT = "C:/PRIVATE-LEGACY-AFFIRM-ARCHIVE-SECRET"
PRIVATE_REQUEST = (
    ".wom-scratch/private/activity-groups/PRIVATE-REQUEST-SECRET.json"
)
PRIVATE_PROPOSAL = ".wom-scratch/PRIVATE-PROPOSAL-SECRET.jsonl"
PRIVATE_RECEIPT = "receipts/PRIVATE-RECEIPT-SECRET.json"
PRIVATE_ZETTEL = "zet_PRIVATE-LEGACY-AFFIRM-SECRET"
PRIVATE_REVIEWER = "person:PRIVATE-LEGACY-AFFIRM-REVIEWER-SECRET"
PRIVATE_DIGEST = "sha256:PRIVATE-LEGACY-AFFIRM-DIGEST-SECRET"
PRIVATE_REASON = "PRIVATE-DISCARD-REASON-SECRET"
PRIVATE_VALUES = (
    PRIVATE_CLI_ROOT,
    PRIVATE_REQUEST,
    PRIVATE_PROPOSAL,
    PRIVATE_RECEIPT,
    PRIVATE_ZETTEL,
    PRIVATE_REVIEWER,
    PRIVATE_DIGEST,
    PRIVATE_REASON,
)


def _archive_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class _BoundaryAssertions(unittest.TestCase):
    def _archive_root(self, parent: Path) -> Path:
        root = parent / "PRIVATE-LEGACY-AFFIRM-ARCHIVE-SECRET"
        root.mkdir()
        (root / "archive.yml").write_text(
            "archive_id: archive:personal:legacy-affirm-gate-test\n",
            encoding="utf-8",
        )
        (root / "sentinel.bin").write_bytes(b"must remain byte exact")
        return root

    def _assert_service_block(
        self,
        *,
        root: Path,
        lifecycle_action: str,
        invoke: Callable[[], dict[str, object]],
    ) -> None:
        before = _archive_snapshot(root)
        result = invoke()

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["lifecycle_action"], lifecycle_action)
        blockers = result.get("blockers") or result.get("reason_codes")
        self.assertEqual(blockers, [COMPOUND_APPROVAL_BLOCKER])
        self.assertEqual(result["would_change"], [])
        self.assertEqual(result["files_written"], [])
        self.assertIs(result["private_values_echoed"], False)
        self.assertEqual(_archive_snapshot(root), before)
        rendered = json.dumps(result, ensure_ascii=False)
        for private in (*PRIVATE_VALUES, str(root)):
            self.assertNotIn(private, rendered)


class Letter137LegacyAffirmServiceBoundaryTests(_BoundaryAssertions):
    def test_activity_group_approve_routes_block_before_private_core(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive_root(Path(tmp))
            with (
                mock.patch.object(
                    archive_services,
                    "_activity_group_membership_write",
                    side_effect=AssertionError("membership writer entered"),
                ) as writer,
                mock.patch.object(
                    archive_services,
                    "_activity_group_membership_recover",
                    side_effect=AssertionError("membership recovery entered"),
                ) as recovery,
            ):
                calls = (
                    (
                        "activity_group_membership_write",
                        lambda: archive_services.activity_group_membership_write(
                            root,
                            request_path=PRIVATE_REQUEST,
                            expected_request_sha256=PRIVATE_DIGEST,
                            expected_review_plan_sha256=PRIVATE_DIGEST,
                            approve=True,
                            reviewed_by=PRIVATE_REVIEWER,
                            affirm_memberships_reviewed=True,
                        ),
                    ),
                    (
                        "activity_group_membership_removal_write",
                        lambda: archive_services.activity_group_membership_removal_write(
                            root,
                            request_path=PRIVATE_REQUEST,
                            expected_request_sha256=PRIVATE_DIGEST,
                            expected_review_plan_sha256=PRIVATE_DIGEST,
                            approve=True,
                            reviewed_by=PRIVATE_REVIEWER,
                            affirm_removals_reviewed=True,
                        ),
                    ),
                    (
                        "activity_group_membership_recover",
                        lambda: archive_services.activity_group_membership_recover(
                            root,
                            expected_request_sha256=PRIVATE_DIGEST,
                            expected_recovery_plan_sha256=PRIVATE_DIGEST,
                            approve=True,
                            reviewed_by=PRIVATE_REVIEWER,
                            affirm_recovery_reviewed=True,
                        ),
                    ),
                    (
                        "activity_group_membership_removal_recover",
                        lambda: archive_services.activity_group_membership_removal_recover(
                            root,
                            expected_request_sha256=PRIVATE_DIGEST,
                            expected_recovery_plan_sha256=PRIVATE_DIGEST,
                            approve=True,
                            reviewed_by=PRIVATE_REVIEWER,
                            affirm_recovery_reviewed=True,
                        ),
                    ),
                )
                for action, invoke in calls:
                    with self.subTest(action=action):
                        self._assert_service_block(
                            root=root,
                            lifecycle_action=action,
                            invoke=invoke,
                        )

            writer.assert_not_called()
            recovery.assert_not_called()

    def test_abstract_approve_routes_block_before_private_path_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive_root(Path(tmp))
            original_resolver = archive_services.resolve_archive_relative_path

            def archive_identity_only(
                archive_root: Path | str,
                relative_path: str,
            ) -> Path:
                if relative_path != "archive.yml":
                    raise AssertionError("private abstract path read entered")
                return original_resolver(archive_root, relative_path)

            with mock.patch.object(
                archive_services,
                "resolve_archive_relative_path",
                side_effect=archive_identity_only,
            ) as resolver:
                calls = (
                    (
                        "zet_abstract_backfill_write",
                        lambda: archive_services.zet_abstract_backfill_write(
                            root,
                            proposal_path=PRIVATE_PROPOSAL,
                            expected_proposal_sha256=PRIVATE_DIGEST,
                            approve=True,
                            reviewed_by=PRIVATE_REVIEWER,
                            affirm_abstracts_reviewed=True,
                        ),
                    ),
                    (
                        "zet_abstract_backfill_revert",
                        lambda: archive_services.zet_abstract_backfill_revert(
                            root,
                            receipt_path=PRIVATE_RECEIPT,
                            expected_receipt_sha256=PRIVATE_DIGEST,
                            approve=True,
                            reviewed_by=PRIVATE_REVIEWER,
                            affirm_abstract_removal_reviewed=True,
                        ),
                    ),
                    (
                        "zet_abstract_backfill_recover",
                        lambda: archive_services.zet_abstract_backfill_recover(
                            root,
                            operation="apply",
                            basis_sha256=PRIVATE_DIGEST,
                            expected_plan_digest=PRIVATE_DIGEST,
                            expected_action=(
                                "cleanup_unstarted_transaction_evidence"
                            ),
                            approve=True,
                            reviewed_by=PRIVATE_REVIEWER,
                            affirm_recovery_reviewed=True,
                            affirm_archive_quiescent=True,
                        ),
                    ),
                )
                for action, invoke in calls:
                    with self.subTest(action=action):
                        self._assert_service_block(
                            root=root,
                            lifecycle_action=action,
                            invoke=invoke,
                        )

            self.assertEqual(
                [call.args[1] for call in resolver.call_args_list],
                [],
            )
            resolver.assert_not_called()

    def test_title_approve_routes_block_before_private_path_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive_root(Path(tmp))
            original_resolver = archive_services.resolve_archive_relative_path

            def archive_identity_only(
                archive_root: Path | str,
                relative_path: str,
            ) -> Path:
                if relative_path != "archive.yml":
                    raise AssertionError("private title path read entered")
                return original_resolver(archive_root, relative_path)

            with mock.patch.object(
                archive_services,
                "resolve_archive_relative_path",
                side_effect=archive_identity_only,
            ) as resolver:
                calls = (
                    (
                        "zet_title_remap_write",
                        lambda: archive_services.zet_title_remap_write(
                            root,
                            proposal_path=PRIVATE_PROPOSAL,
                            expected_proposal_sha256=PRIVATE_DIGEST,
                            expected_plan_digest=PRIVATE_DIGEST,
                            expected_write_plan_digest=PRIVATE_DIGEST,
                            approve=True,
                            reviewed_by=PRIVATE_REVIEWER,
                            affirm_titles_reviewed=True,
                        ),
                    ),
                    (
                        "zet_title_remap_revert",
                        lambda: archive_services.zet_title_remap_revert(
                            root,
                            receipt_path=PRIVATE_RECEIPT,
                            expected_receipt_sha256=PRIVATE_DIGEST,
                            expected_plan_digest=PRIVATE_DIGEST,
                            approve=True,
                            reviewed_by=PRIVATE_REVIEWER,
                            affirm_title_reversions_reviewed=True,
                            affirm_archive_quiescent=True,
                        ),
                    ),
                    (
                        "zet_title_remap_recover",
                        lambda: archive_services.zet_title_remap_recover(
                            root,
                            case_sha256=PRIVATE_DIGEST,
                            expected_plan_digest=PRIVATE_DIGEST,
                            expected_action=(
                                "cleanup_unstarted_title_transaction_evidence"
                            ),
                            approve=True,
                            reviewed_by=PRIVATE_REVIEWER,
                            affirm_recovery_reviewed=True,
                            affirm_archive_quiescent=True,
                        ),
                    ),
                    (
                        "zet_title_remap_revert_recover",
                        lambda: archive_services.zet_title_remap_revert_recover(
                            root,
                            case_sha256=PRIVATE_DIGEST,
                            expected_plan_digest=PRIVATE_DIGEST,
                            expected_action=(
                                "cleanup_unstarted_title_revert_transaction_evidence"
                            ),
                            approve=True,
                            reviewed_by=PRIVATE_REVIEWER,
                            affirm_recovery_reviewed=True,
                            affirm_archive_quiescent=True,
                        ),
                    ),
                )
                for action, invoke in calls:
                    with self.subTest(action=action):
                        self._assert_service_block(
                            root=root,
                            lifecycle_action=action,
                            invoke=invoke,
                        )

            self.assertEqual(
                [call.args[1] for call in resolver.call_args_list],
                [],
            )
            resolver.assert_not_called()

    def test_discard_approve_routes_block_before_plan_or_archive_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive_root(Path(tmp))
            with (
                mock.patch.object(
                    completion_workflows,
                    "_draft_discard_plan_core",
                    side_effect=AssertionError("discard plan entered"),
                ) as discard_plan,
                mock.patch.object(
                    completion_workflows,
                    "_draft_discard_restore_plan_core",
                    side_effect=AssertionError("restore plan entered"),
                ) as restore_plan,
            ):
                self._assert_service_block(
                    root=root,
                    lifecycle_action="discard_draft_apply",
                    invoke=lambda: completion_workflows.draft_discard_apply(
                        root,
                        zettel_id=PRIVATE_ZETTEL,
                        reason=PRIVATE_REASON,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                )
                self._assert_service_block(
                    root=root,
                    lifecycle_action="discard_draft_restore",
                    invoke=lambda: completion_workflows.draft_discard_restore(
                        root,
                        receipt=PRIVATE_RECEIPT,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                )

            discard_plan.assert_not_called()
            restore_plan.assert_not_called()


class Letter137LegacyAffirmCliBoundaryTests(_BoundaryAssertions):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()

    def _assert_cli_block(
        self,
        *,
        arguments: list[str],
        service_module: ModuleType,
        service_name: str,
        lifecycle_action: str,
    ) -> None:
        args = self.parser.parse_args(arguments)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(
                service_module,
                service_name,
                side_effect=AssertionError("legacy approval service entered"),
            ) as service,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = args.func(args)

        self.assertEqual(code, 1, stderr.getvalue())
        service.assert_not_called()
        result = json.loads(stdout.getvalue())
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["lifecycle_action"], lifecycle_action)
        self.assertEqual(result["reason_codes"], [COMPOUND_APPROVAL_BLOCKER])
        self.assertIs(result["private_values_echoed"], False)
        rendered = stdout.getvalue() + stderr.getvalue()
        for private in PRIVATE_VALUES:
            self.assertNotIn(private, rendered)

    def test_activity_group_approve_routes_block_before_service(self) -> None:
        common = [
            "--expected-request-sha256",
            PRIVATE_DIGEST,
            "--approve",
            "--reviewed-by",
            PRIVATE_REVIEWER,
            "--format",
            "json",
        ]
        calls = (
            (
                [
                    "activity-group-membership-write",
                    PRIVATE_CLI_ROOT,
                    "--request",
                    PRIVATE_REQUEST,
                    "--expected-review-plan-sha256",
                    PRIVATE_DIGEST,
                    "--affirm-memberships-reviewed",
                    *common,
                ],
                "activity_group_membership_write",
                "activity_group_membership_write",
            ),
            (
                [
                    "activity-group-membership-removal-write",
                    PRIVATE_CLI_ROOT,
                    "--request",
                    PRIVATE_REQUEST,
                    "--expected-review-plan-sha256",
                    PRIVATE_DIGEST,
                    "--affirm-removals-reviewed",
                    *common,
                ],
                "activity_group_membership_removal_write",
                "activity_group_membership_removal_write",
            ),
            (
                [
                    "activity-group-membership-recover",
                    PRIVATE_CLI_ROOT,
                    "--expected-recovery-plan-sha256",
                    PRIVATE_DIGEST,
                    "--affirm-recovery-reviewed",
                    *common,
                ],
                "activity_group_membership_recover",
                "activity_group_membership_recover",
            ),
            (
                [
                    "activity-group-membership-removal-recover",
                    PRIVATE_CLI_ROOT,
                    "--expected-recovery-plan-sha256",
                    PRIVATE_DIGEST,
                    "--affirm-recovery-reviewed",
                    *common,
                ],
                "activity_group_membership_removal_recover",
                "activity_group_membership_removal_recover",
            ),
        )
        for arguments, service, action in calls:
            with self.subTest(action=action):
                self._assert_cli_block(
                    arguments=arguments,
                    service_module=archive_services,
                    service_name=service,
                    lifecycle_action=action,
                )

    def test_abstract_approve_routes_block_before_service(self) -> None:
        calls = (
            (
                [
                    "zet-abstract-backfill-write",
                    PRIVATE_CLI_ROOT,
                    "--proposal",
                    PRIVATE_PROPOSAL,
                    "--expected-proposal-sha256",
                    PRIVATE_DIGEST,
                    "--approve",
                    "--reviewed-by",
                    PRIVATE_REVIEWER,
                    "--affirm-abstracts-reviewed",
                    "--format",
                    "json",
                ],
                "zet_abstract_backfill_write",
                "zet_abstract_backfill_write",
            ),
            (
                [
                    "zet-abstract-backfill-revert",
                    PRIVATE_CLI_ROOT,
                    "--receipt",
                    PRIVATE_RECEIPT,
                    "--expected-receipt-sha256",
                    PRIVATE_DIGEST,
                    "--approve",
                    "--reviewed-by",
                    PRIVATE_REVIEWER,
                    "--affirm-abstract-removal-reviewed",
                    "--format",
                    "json",
                ],
                "zet_abstract_backfill_revert",
                "zet_abstract_backfill_revert",
            ),
            (
                [
                    "zet-abstract-backfill-recover",
                    PRIVATE_CLI_ROOT,
                    "--operation",
                    "apply",
                    "--basis-sha256",
                    PRIVATE_DIGEST,
                    "--expected-plan-digest",
                    PRIVATE_DIGEST,
                    "--expected-action",
                    "cleanup_unstarted_transaction_evidence",
                    "--approve",
                    "--reviewed-by",
                    PRIVATE_REVIEWER,
                    "--affirm-recovery-reviewed",
                    "--affirm-archive-quiescent",
                    "--format",
                    "json",
                ],
                "zet_abstract_backfill_recover",
                "zet_abstract_backfill_recover",
            ),
        )
        for arguments, service, action in calls:
            with self.subTest(action=action):
                self._assert_cli_block(
                    arguments=arguments,
                    service_module=archive_services,
                    service_name=service,
                    lifecycle_action=action,
                )

    def test_title_approve_routes_block_before_service(self) -> None:
        approval = [
            "--approve",
            "--reviewed-by",
            PRIVATE_REVIEWER,
            "--format",
            "json",
        ]
        calls = (
            (
                [
                    "zet-title-remap-write",
                    PRIVATE_CLI_ROOT,
                    "--proposal",
                    PRIVATE_PROPOSAL,
                    "--expected-proposal-sha256",
                    PRIVATE_DIGEST,
                    "--expected-plan-digest",
                    PRIVATE_DIGEST,
                    "--expected-write-plan-digest",
                    PRIVATE_DIGEST,
                    "--affirm-titles-reviewed",
                    *approval,
                ],
                "zet_title_remap_write",
                "zet_title_remap_write",
            ),
            (
                [
                    "zet-title-remap-revert",
                    PRIVATE_CLI_ROOT,
                    "--receipt",
                    PRIVATE_RECEIPT,
                    "--expected-receipt-sha256",
                    PRIVATE_DIGEST,
                    "--expected-plan-digest",
                    PRIVATE_DIGEST,
                    "--affirm-title-reversions-reviewed",
                    "--affirm-archive-quiescent",
                    *approval,
                ],
                "zet_title_remap_revert",
                "zet_title_remap_revert",
            ),
            (
                [
                    "zet-title-remap-recover",
                    PRIVATE_CLI_ROOT,
                    "--case-sha256",
                    PRIVATE_DIGEST,
                    "--expected-plan-digest",
                    PRIVATE_DIGEST,
                    "--expected-action",
                    "cleanup_unstarted_title_transaction_evidence",
                    "--affirm-recovery-reviewed",
                    "--affirm-archive-quiescent",
                    *approval,
                ],
                "zet_title_remap_recover",
                "zet_title_remap_recover",
            ),
            (
                [
                    "zet-title-remap-revert-recover",
                    PRIVATE_CLI_ROOT,
                    "--case-sha256",
                    PRIVATE_DIGEST,
                    "--expected-plan-digest",
                    PRIVATE_DIGEST,
                    "--expected-action",
                    "cleanup_unstarted_title_revert_transaction_evidence",
                    "--affirm-recovery-reviewed",
                    "--affirm-archive-quiescent",
                    *approval,
                ],
                "zet_title_remap_revert_recover",
                "zet_title_remap_revert_recover",
            ),
        )
        for arguments, service, action in calls:
            with self.subTest(action=action):
                self._assert_cli_block(
                    arguments=arguments,
                    service_module=archive_services,
                    service_name=service,
                    lifecycle_action=action,
                )

    def test_discard_approve_routes_block_before_service(self) -> None:
        calls = (
            (
                [
                    "discard-draft",
                    PRIVATE_CLI_ROOT,
                    "--zettel-id",
                    PRIVATE_ZETTEL,
                    "--reason",
                    PRIVATE_REASON,
                    "--approve",
                    "--expected-plan-sha256",
                    PRIVATE_DIGEST,
                    "--reviewed-by",
                    PRIVATE_REVIEWER,
                    "--format",
                    "json",
                ],
                "draft_discard_apply",
                "discard_draft_apply",
            ),
            (
                [
                    "discard-draft-restore",
                    PRIVATE_CLI_ROOT,
                    "--receipt",
                    PRIVATE_RECEIPT,
                    "--approve",
                    "--expected-plan-sha256",
                    PRIVATE_DIGEST,
                    "--reviewed-by",
                    PRIVATE_REVIEWER,
                    "--format",
                    "json",
                ],
                "draft_discard_restore",
                "discard_draft_restore",
            ),
        )
        for arguments, service, action in calls:
            with self.subTest(action=action):
                self._assert_cli_block(
                    arguments=arguments,
                    service_module=completion_workflows,
                    service_name=service,
                    lifecycle_action=action,
                )


if __name__ == "__main__":
    unittest.main()
