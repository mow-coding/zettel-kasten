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
PRIVATE_RECEIPT = "receipts/edges/PRIVATE-RECEIPT-SECRET.json"
PRIVATE_BATCH_RECEIPT = (
    "receipts/edges/batches/PRIVATE-BATCH-RECEIPT-SECRET.json"
)
PRIVATE_REVIEWER = "person:PRIVATE-REVIEWER-SECRET"


def _archive_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class Letter137EdgeRevertServiceBoundaryTests(unittest.TestCase):
    def _archive_root(self, parent: Path) -> Path:
        root = parent / "archive"
        root.mkdir()
        (root / "archive.yml").write_text(
            "archive_id: archive:personal:edge-revert-gate-test\n",
            encoding="utf-8",
        )
        return root

    def _assert_approve_is_content_free_and_zero_write(
        self,
        *,
        service: Callable[..., dict[str, object]],
        root: Path,
        receipt: str,
        lifecycle_action: str,
    ) -> None:
        before = _archive_snapshot(root)
        result = service(
            root,
            receipt=receipt,
            approve=True,
            reviewed_by=PRIVATE_REVIEWER,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["write_status"], "blocked")
        self.assertEqual(result["lifecycle_action"], lifecycle_action)
        self.assertEqual(result["blockers"], [COMPOUND_APPROVAL_BLOCKER])
        self.assertEqual(result["would_change"], [])
        self.assertEqual(result["files_written"], [])
        self.assertIs(result["private_values_echoed"], False)
        self.assertEqual(_archive_snapshot(root), before)
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(receipt, serialized)
        self.assertNotIn(PRIVATE_REVIEWER, serialized)

    def test_edge_revert_approve_fails_closed_before_receipt_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive_root(Path(tmp))
            self._assert_approve_is_content_free_and_zero_write(
                service=archive_services.zettel_edge_revert,
                root=root,
                receipt=PRIVATE_RECEIPT,
                lifecycle_action="zettel_edge_revert",
            )

    def test_edge_batch_revert_approve_requires_the_claim_before_receipt_read(
        self,
    ) -> None:
        # v0.4.21 reopened revert-batch under one exact approval: an unbound
        # approve call raises the fixed code before the receipt is read and
        # echoes nothing private.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive_root(Path(tmp))
            before = _archive_snapshot(root)
            with self.assertRaises(archive_services.ArchiveServiceError) as caught:
                archive_services.zettel_edge_batch_revert(
                    root,
                    receipt=PRIVATE_BATCH_RECEIPT,
                    approve=True,
                    reviewed_by=PRIVATE_REVIEWER,
                )
            self.assertEqual(str(caught.exception), "exact_human_approval_required")
            self.assertEqual(_archive_snapshot(root), before)
            self.assertNotIn(PRIVATE_BATCH_RECEIPT, repr(caught.exception))


class Letter137EdgeRevertCliBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()

    def _assert_cli_blocks_before_service(
        self,
        *,
        command: str,
        receipt: str,
        service_name: str,
        lifecycle_action: str,
    ) -> None:
        args = self.parser.parse_args(
            [
                command,
                "C:/private/archive",
                "--receipt",
                receipt,
                "--approve",
                "--reviewed-by",
                PRIVATE_REVIEWER,
                "--format",
                "json",
            ]
        )
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
        self.assertNotIn(receipt, serialized)
        self.assertNotIn(PRIVATE_REVIEWER, serialized)

    def test_edge_revert_approve_on_missing_archive_never_enters_the_writer(self) -> None:
        # v0.4.30 (letter 163 ③c): revert-edge --approve no longer needs
        # --exact-local; the preview runs, and on a missing archive the
        # writer and the broker are never entered.
        original = archive_cli.archive_services.zettel_edge_revert

        def preflight_only(*args, **kwargs):
            if kwargs.get("approve"):
                raise AssertionError("approved writer entered")
            return original(*args, **kwargs)

        args = self.parser.parse_args(
            [
                "revert-edge",
                "C:/private/archive",
                "--receipt",
                PRIVATE_RECEIPT,
                "--approve",
                "--reviewed-by",
                PRIVATE_REVIEWER,
                "--format",
                "json",
            ]
        )
        self.assertFalse(args.exact_local)
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(
                archive_cli.archive_services,
                "zettel_edge_revert",
                side_effect=preflight_only,
            ) as service,
            mock.patch.object(
                archive_cli,
                "_execute_exact_human_approved_write",
            ) as broker,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = args.func(args)
        self.assertEqual(code, 1, stderr.getvalue())
        self.assertEqual(service.call_count, 1)
        broker.assert_not_called()
        serialized = stdout.getvalue() + stderr.getvalue()
        self.assertNotIn(PRIVATE_RECEIPT, serialized)
        self.assertNotIn(PRIVATE_REVIEWER, serialized)

    def test_edge_batch_revert_approve_on_missing_archive_never_enters_the_writer(self) -> None:
        original = archive_cli.archive_services.zettel_edge_batch_revert

        def preflight_only(*args, **kwargs):
            if kwargs.get("approve"):
                raise AssertionError("approved writer entered")
            return original(*args, **kwargs)

        args = self.parser.parse_args(
            [
                "revert-batch",
                "C:/private/archive",
                "--receipt",
                PRIVATE_BATCH_RECEIPT,
                "--approve",
                "--reviewed-by",
                PRIVATE_REVIEWER,
                "--format",
                "json",
            ]
        )
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(
                archive_cli.archive_services,
                "zettel_edge_batch_revert",
                side_effect=preflight_only,
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = args.func(args)
        self.assertEqual(code, 1, stderr.getvalue())
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["state"], "blocked")
        self.assertEqual(payload["lifecycle_action"], "zettel_edge_batch_revert")
        self.assertEqual(payload["reason_codes"], ["zettel_edge_batch_revert_workflow_failed_safely"])
        self.assertIs(payload["private_values_echoed"], False)
        serialized = stdout.getvalue() + stderr.getvalue()
        self.assertNotIn(PRIVATE_BATCH_RECEIPT, serialized)
        self.assertNotIn(PRIVATE_REVIEWER, serialized)


if __name__ == "__main__":
    unittest.main()
