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
PRIVATE_ZETTEL = "zet_PRIVATE-RECONCILE-SECRET"
PRIVATE_PATH = "zettels/PRIVATE-RECONCILE-SECRET.md"
PRIVATE_REVIEWER = "person:PRIVATE-RECONCILE-REVIEWER-SECRET"
PRIVATE_PLAN = "PRIVATE-RECONCILE-PLAN-SECRET"


def _archive_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class Letter137ReconcileServiceBoundaryTests(unittest.TestCase):
    def _archive_root(self, parent: Path) -> Path:
        root = parent / "archive"
        root.mkdir()
        (root / "archive.yml").write_text(
            "archive_id: archive:personal:reconcile-gate-test\n",
            encoding="utf-8",
        )
        return root

    def _assert_blocked(
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
        self.assertEqual(result["write_status"], "blocked")
        self.assertEqual(result["lifecycle_action"], lifecycle_action)
        self.assertEqual(result["blockers"], [COMPOUND_APPROVAL_BLOCKER])
        self.assertEqual(result["would_change"], [])
        self.assertEqual(result["files_written"], [])
        self.assertIs(result["private_values_echoed"], False)
        self.assertEqual(_archive_snapshot(root), before)
        serialized = json.dumps(result, ensure_ascii=False)
        for value in (
            PRIVATE_ZETTEL,
            PRIVATE_PATH,
            PRIVATE_REVIEWER,
            PRIVATE_PLAN,
        ):
            self.assertNotIn(value, serialized)

    def test_remint_reconcile_blocks_before_plan_receipt_or_canonical_read(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive_root(Path(tmp))
            with mock.patch.object(
                archive_services,
                "remint_reconcile_plan",
                side_effect=AssertionError("reconcile plan must not run"),
            ) as plan:
                self._assert_blocked(
                    root=root,
                    lifecycle_action="remint_reconcile",
                    invoke=lambda: archive_services.remint_reconcile_apply(
                        root,
                        zettel_id=PRIVATE_ZETTEL,
                        relative_path=PRIVATE_PATH,
                        reviewed_by=PRIVATE_REVIEWER,
                        content_changed_ack=True,
                        reviewed_plan_sha256=PRIVATE_PLAN,
                        strip_bom=True,
                    ),
                )
            plan.assert_not_called()

    def test_retire_reconcile_blocks_before_plan_receipt_or_canonical_read(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._archive_root(Path(tmp))
            with mock.patch.object(
                archive_services,
                "retire_draft_reconcile_plan",
                side_effect=AssertionError("reconcile plan must not run"),
            ) as plan:
                self._assert_blocked(
                    root=root,
                    lifecycle_action="retire_draft_reconcile",
                    invoke=lambda: archive_services.retire_draft_reconcile_apply(
                        root,
                        zettel_id=PRIVATE_ZETTEL,
                        reviewed_by=PRIVATE_REVIEWER,
                        content_changed_ack=True,
                        reviewed_plan_sha256=PRIVATE_PLAN,
                        strip_bom=True,
                    ),
                )
            plan.assert_not_called()


class Letter137ReconcileCliBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()

    def _assert_cli_blocks_before_service(
        self,
        *,
        values: list[str],
        service_name: str,
        lifecycle_action: str,
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
        for value in (
            PRIVATE_ZETTEL,
            PRIVATE_PATH,
            PRIVATE_REVIEWER,
            PRIVATE_PLAN,
        ):
            self.assertNotIn(value, serialized)

    def test_remint_reconcile_approve_blocks_before_service(self) -> None:
        self._assert_cli_blocks_before_service(
            values=[
                "remint-reconcile",
                "C:/private/archive",
                "--path",
                PRIVATE_PATH,
                "--approve",
                "--reviewed-by",
                PRIVATE_REVIEWER,
                "--content-changed-ack",
                "--reviewed-plan-sha256",
                PRIVATE_PLAN,
                "--strip-bom",
                "--format",
                "json",
            ],
            service_name="remint_reconcile_apply",
            lifecycle_action="remint_reconcile",
        )

    def test_retire_reconcile_approve_blocks_before_service(self) -> None:
        self._assert_cli_blocks_before_service(
            values=[
                "retire-draft-reconcile",
                "C:/private/archive",
                "--zettel-id",
                PRIVATE_ZETTEL,
                "--approve",
                "--reviewed-by",
                PRIVATE_REVIEWER,
                "--content-changed-ack",
                "--reviewed-plan-sha256",
                PRIVATE_PLAN,
                "--strip-bom",
                "--format",
                "json",
            ],
            service_name="retire_draft_reconcile_apply",
            lifecycle_action="retire_draft_reconcile",
        )


if __name__ == "__main__":
    unittest.main()
