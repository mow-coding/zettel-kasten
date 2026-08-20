from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from wom_kit import archive_cli, archive_services


COMPOUND_APPROVAL_BLOCKER = "compound_exact_human_approval_binding_required"
PRIVATE_ZETTEL = "zet_PRIVATE-REVISION-SECRET"
PRIVATE_PROPOSAL = ".wom-scratch/revisions/PRIVATE-PROPOSAL-SECRET.md"
PRIVATE_RECEIPT = "receipts/zet-revisions/PRIVATE-RECEIPT-SECRET.json"
PRIVATE_RESTORE = (
    ".wom-scratch/revisions/restores/PRIVATE-RESTORE-PROPOSAL-SECRET.md"
)
PRIVATE_REVIEWER = "person:PRIVATE-REVISION-REVIEWER-SECRET"
PRIVATE_DIGEST = "sha256:PRIVATE-DIGEST-SECRET"


def _archive_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class Letter137RevisionServiceBoundaryTests(unittest.TestCase):
    def _archive_root(self, parent: Path) -> Path:
        root = parent / "archive"
        root.mkdir()
        (root / "archive.yml").write_text(
            "archive_id: archive:personal:revision-gate-test\n",
            encoding="utf-8",
        )
        return root

    def _assert_blocked(
        self,
        *,
        root: Path,
        lifecycle_action: str,
        invoke: Callable[[], dict[str, object]],
        private_values: tuple[str, ...],
    ) -> None:
        before = _archive_snapshot(root)
        result = invoke()

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["write_status"], "blocked")
        self.assertEqual(result["lifecycle_action"], lifecycle_action)
        self.assertEqual(result["blockers"], [COMPOUND_APPROVAL_BLOCKER])
        self.assertEqual(result["would_change"], [])
        self.assertEqual(result["files_written"], [])
        self.assertIs(result["private_values_echoed"], False)
        self.assertEqual(_archive_snapshot(root), before)
        serialized = json.dumps(result, ensure_ascii=False)
        for value in private_values:
            self.assertNotIn(value, serialized)

    def test_revision_approve_blocks_before_proposal_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive_root(Path(tmp))
            self._assert_blocked(
                root=root,
                lifecycle_action="zet_revision_write",
                invoke=lambda: archive_services.zet_revision_write(
                    root,
                    zettel_id=PRIVATE_ZETTEL,
                    proposal_path=PRIVATE_PROPOSAL,
                    expected_canonical_sha256=PRIVATE_DIGEST,
                    expected_proposal_sha256=PRIVATE_DIGEST,
                    expected_proposal_semantic_sha256=PRIVATE_DIGEST,
                    expected_plan_digest=PRIVATE_DIGEST,
                    expected_write_plan_digest=PRIVATE_DIGEST,
                    approve=True,
                    reviewed_by=PRIVATE_REVIEWER,
                    affirm_revision_reviewed=True,
                    affirm_abstract_body_pair_reviewed=True,
                    affirm_edge_changes_reviewed=True,
                ),
                private_values=(
                    PRIVATE_ZETTEL,
                    PRIVATE_PROPOSAL,
                    PRIVATE_REVIEWER,
                    PRIVATE_DIGEST,
                ),
            )

    def test_revision_restore_approve_blocks_before_receipt_or_proposal_read(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive_root(Path(tmp))
            self._assert_blocked(
                root=root,
                lifecycle_action="zet_revision_restore_write",
                invoke=lambda: archive_services.zet_revision_restore_write(
                    root,
                    receipt_path=PRIVATE_RECEIPT,
                    expected_receipt_sha256=PRIVATE_DIGEST,
                    restore_proposal_path=PRIVATE_RESTORE,
                    expected_current_sha256=PRIVATE_DIGEST,
                    expected_restore_proposal_sha256=PRIVATE_DIGEST,
                    expected_restore_proposal_semantic_sha256=PRIVATE_DIGEST,
                    expected_restore_plan_digest=PRIVATE_DIGEST,
                    expected_write_plan_digest=PRIVATE_DIGEST,
                    approve=True,
                    reviewed_by=PRIVATE_REVIEWER,
                    affirm_restore_reviewed=True,
                    affirm_abstract_body_pair_reviewed=True,
                    affirm_edge_changes_reviewed=True,
                ),
                private_values=(
                    PRIVATE_RECEIPT,
                    PRIVATE_RESTORE,
                    PRIVATE_REVIEWER,
                    PRIVATE_DIGEST,
                ),
            )


class Letter137RevisionCliBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()

    def _assert_cli_blocks_before_service(
        self,
        *,
        values: list[str],
        service_name: str,
        lifecycle_action: str,
        private_values: tuple[str, ...],
    ) -> None:
        args = self.parser.parse_args(values)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(
                archive_cli.archive_services,
                service_name,
                return_value={"ok": True, "files_written": ["unexpected"]},
            ) as service,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = args.func(args)

        self.assertEqual(code, 1, stderr.getvalue())
        service.assert_not_called()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["state"], "blocked")
        self.assertEqual(payload["lifecycle_action"], lifecycle_action)
        self.assertEqual(payload["reason_codes"], [COMPOUND_APPROVAL_BLOCKER])
        self.assertIs(payload["private_values_echoed"], False)
        serialized = stdout.getvalue() + stderr.getvalue()
        for value in private_values:
            self.assertNotIn(value, serialized)

    def test_revision_approve_blocks_before_service(self) -> None:
        self._assert_cli_blocks_before_service(
            values=[
                "zet-revision-write",
                "C:/private/archive",
                "--zettel-id",
                PRIVATE_ZETTEL,
                "--proposal",
                PRIVATE_PROPOSAL,
                "--expected-canonical-sha256",
                PRIVATE_DIGEST,
                "--expected-proposal-sha256",
                PRIVATE_DIGEST,
                "--expected-proposal-semantic-sha256",
                PRIVATE_DIGEST,
                "--expected-plan-digest",
                PRIVATE_DIGEST,
                "--expected-write-plan-digest",
                PRIVATE_DIGEST,
                "--approve",
                "--reviewed-by",
                PRIVATE_REVIEWER,
                "--affirm-revision-reviewed",
                "--affirm-abstract-body-pair-reviewed",
                "--affirm-edge-changes-reviewed",
                "--format",
                "json",
            ],
            service_name="zet_revision_write",
            lifecycle_action="zet_revision_write",
            private_values=(
                PRIVATE_ZETTEL,
                PRIVATE_PROPOSAL,
                PRIVATE_REVIEWER,
                PRIVATE_DIGEST,
            ),
        )

    def test_revision_restore_approve_blocks_before_service(self) -> None:
        self._assert_cli_blocks_before_service(
            values=[
                "zet-revision-restore-write",
                "C:/private/archive",
                "--receipt",
                PRIVATE_RECEIPT,
                "--expected-receipt-sha256",
                PRIVATE_DIGEST,
                "--restore-proposal",
                PRIVATE_RESTORE,
                "--expected-current-sha256",
                PRIVATE_DIGEST,
                "--expected-restore-proposal-sha256",
                PRIVATE_DIGEST,
                "--expected-restore-proposal-semantic-sha256",
                PRIVATE_DIGEST,
                "--expected-restore-plan-digest",
                PRIVATE_DIGEST,
                "--expected-write-plan-digest",
                PRIVATE_DIGEST,
                "--approve",
                "--reviewed-by",
                PRIVATE_REVIEWER,
                "--affirm-restore-reviewed",
                "--affirm-abstract-body-pair-reviewed",
                "--affirm-edge-changes-reviewed",
                "--format",
                "json",
            ],
            service_name="zet_revision_restore_write",
            lifecycle_action="zet_revision_restore_write",
            private_values=(
                PRIVATE_RECEIPT,
                PRIVATE_RESTORE,
                PRIVATE_REVIEWER,
                PRIVATE_DIGEST,
            ),
        )


if __name__ == "__main__":
    unittest.main()
