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

    def test_edge_batch_revert_approve_fails_closed_before_receipt_read(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive_root(Path(tmp))
            self._assert_approve_is_content_free_and_zero_write(
                service=archive_services.zettel_edge_batch_revert,
                root=root,
                receipt=PRIVATE_BATCH_RECEIPT,
                lifecycle_action="zettel_edge_batch_revert",
            )


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

    def test_edge_revert_approve_blocks_before_service(self) -> None:
        self._assert_cli_blocks_before_service(
            command="revert-edge",
            receipt=PRIVATE_RECEIPT,
            service_name="zettel_edge_revert",
            lifecycle_action="zettel_edge_revert",
        )

    def test_edge_batch_revert_approve_blocks_before_service(self) -> None:
        self._assert_cli_blocks_before_service(
            command="revert-batch",
            receipt=PRIVATE_BATCH_RECEIPT,
            service_name="zettel_edge_batch_revert",
            lifecycle_action="zettel_edge_batch_revert",
        )


if __name__ == "__main__":
    unittest.main()
