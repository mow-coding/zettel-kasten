from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_cli, archive_services, completion_workflows


REASON = "compound_exact_human_approval_binding_required"
PRIVATE_LABEL = "PRIVATE reviewed label must never echo"
PRIVATE_RECEIPT = "receipts/zettel-objet-links/PRIVATE-person-link.json"
PRIVATE_OBJECT_ID = (
    "sha256:9dabf9b965a3f789b1b36100f3f70515ce8dfd81b411b1503e1e2c3304303647"
)
ZETTEL_ID = "zet_20240504_fake_lunch_thought"
KIT_ROOT = Path(__file__).resolve().parents[1]


class Letter137ZettelObjetLinkCompoundFailClosedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "PRIVATE-archive-name"
        self.root.mkdir()
        (self.root / "sentinel.bin").write_bytes(b"must remain exact")

    def _snapshot(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }

    def _run_cli(self, arguments: list[str]) -> tuple[int, dict, str]:
        parsed = self.parser.parse_args(arguments)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = parsed.func(parsed)
        output = stdout.getvalue()
        return code, json.loads(output) if output else {}, stderr.getvalue()

    def _assert_fixed_block(self, result: dict, lifecycle_action: str) -> None:
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")
        self.assertFalse(result["dry_run"])
        self.assertFalse(result["approved"])
        self.assertEqual(result["lifecycle_action"], lifecycle_action)
        self.assertEqual(result["blockers"], [REASON])
        self.assertEqual(result["reason_codes"], [REASON])
        self.assertEqual(result["would_change"], [])
        self.assertEqual(result["files_written"], [])
        self.assertFalse(result["privacy_guards"]["writes"])
        self.assertFalse(result["privacy_guards"]["zettel_body_echoed"])

    def test_service_apply_requires_exact_human_inputs_while_revert_stays_fixed_closed(self) -> None:
        before = self._snapshot()
        with (
            mock.patch.object(
                completion_workflows,
                "_zettel_objet_link_plan_core",
                side_effect=AssertionError("apply preflight read entered"),
            ) as apply_preflight,
            mock.patch.object(
                completion_workflows,
                "_zettel_objet_link_revert_plan_core",
                side_effect=AssertionError("revert preflight read entered"),
            ) as revert_preflight,
            mock.patch.object(
                archive_services,
                "write_bytes_atomic",
                side_effect=AssertionError("canonical writer entered"),
            ) as atomic_writer,
            mock.patch.object(
                archive_services,
                "_write_bytes_create_if_absent",
                side_effect=AssertionError("receipt writer entered"),
            ) as create_writer,
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "exact_human_approval_required",
            ) as raised:
                completion_workflows.zettel_objet_link_apply(
                    self.root,
                    relative_path="zettels/PRIVATE-person-name.md",
                    object_id=PRIVATE_OBJECT_ID,
                    role="source_document",
                    label=PRIVATE_LABEL,
                    expected_plan_sha256="b" * 64,
                    reviewed_by="person:PRIVATE-reviewer",
                )
            reverted = completion_workflows.zettel_objet_link_revert(
                self.root,
                receipt=PRIVATE_RECEIPT,
                expected_plan_sha256="c" * 64,
                reviewed_by="person:PRIVATE-reviewer",
            )

        apply_preflight.assert_not_called()
        revert_preflight.assert_not_called()
        atomic_writer.assert_not_called()
        create_writer.assert_not_called()
        self.assertEqual(self._snapshot(), before)
        self._assert_fixed_block(reverted, "zettel_objet_link_revert")
        rendered = (
            str(raised.exception)
            + json.dumps(reverted, ensure_ascii=False)
        )
        for private in (
            PRIVATE_LABEL,
            PRIVATE_RECEIPT,
            PRIVATE_OBJECT_ID,
            "PRIVATE-person-name.md",
            "PRIVATE-reviewer",
            str(self.root),
        ):
            self.assertNotIn(private, rendered)

    def test_cli_apply_routes_through_exact_human_workflow_while_revert_stays_closed(self) -> None:
        shutil.copytree(
            KIT_ROOT / "examples" / "fake-life-archive",
            self.root,
            dirs_exist_ok=True,
        )
        indexed = archive_services.index_archive(self.root)
        self.assertTrue(indexed["ok"], indexed)
        self.assertEqual(indexed["index_state"], "current", indexed)
        preview = completion_workflows.zettel_objet_link_plan(
            self.root,
            zettel_id=ZETTEL_ID,
            object_id=PRIVATE_OBJECT_ID,
            role="source_document",
            label=PRIVATE_LABEL,
        )
        self.assertTrue(preview["ok"], preview)
        before = self._snapshot()

        successful_apply = {
            "ok": True,
            "state": "applied",
            "dry_run": False,
            "approved": True,
            "lifecycle_action": "zettel_objet_link_apply",
            "summary": {},
            "blockers": [],
            "warnings": [],
            "would_change": [],
            "files_written": [],
            "private_values_echoed": False,
            "privacy_guards": {
                "writes": True,
                "zettel_body_echoed": False,
            },
        }
        approval_claim = object()
        approval_contexts = []

        def execute_exact_workflow(root, context, writer):
            self.assertTrue(Path(root).samefile(self.root))
            approval_contexts.append(context)
            return writer(approval_claim)

        with (
            mock.patch.object(
                completion_workflows,
                "zettel_objet_link_apply",
                return_value=successful_apply,
            ) as apply_service,
            mock.patch.object(
                archive_cli,
                "_execute_zettel_objet_link_exact_human_approved_write",
                side_effect=execute_exact_workflow,
            ) as exact_workflow,
            mock.patch.object(
                completion_workflows,
                "zettel_objet_link_revert",
                side_effect=AssertionError("revert service called"),
            ) as revert_service,
        ):
            apply_code, applied, apply_error = self._run_cli(
                [
                    "zettel-objet-link",
                    str(self.root),
                    "--zettel-id",
                    ZETTEL_ID,
                    "--object-id",
                    PRIVATE_OBJECT_ID,
                    "--role",
                    "source_document",
                    "--label",
                    PRIVATE_LABEL,
                    "--approve",
                    "--expected-plan-sha256",
                    preview["summary"]["plan_sha256"],
                    "--reviewed-by",
                    "person:PRIVATE-reviewer",
                    "--format",
                    "json",
                ]
            )
            revert_code, reverted, revert_error = self._run_cli(
                [
                    "zettel-objet-link-revert",
                    str(self.root),
                    "--receipt",
                    PRIVATE_RECEIPT,
                    "--approve",
                    "--expected-plan-sha256",
                    "c" * 64,
                    "--reviewed-by",
                    "person:PRIVATE-reviewer",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(apply_code, 0, apply_error)
        self.assertEqual(revert_code, 1, revert_error)
        exact_workflow.assert_called_once()
        apply_service.assert_called_once()
        revert_service.assert_not_called()
        self.assertEqual(self._snapshot(), before)
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(len(approval_contexts), 1)
        apply_kwargs = apply_service.call_args.kwargs
        self.assertIs(
            apply_kwargs["exact_human_approval_claim"],
            approval_claim,
        )
        self.assertEqual(
            apply_kwargs["expected_exact_approval_plan_sha256"],
            approval_contexts[0].plan_sha256,
        )
        self.assertEqual(
            apply_kwargs["expected_exact_approval_target_binding_sha256"],
            approval_contexts[0].target_binding_sha256,
        )
        self._assert_fixed_block(reverted, "zettel_objet_link_revert")
        rendered = json.dumps([applied, reverted], ensure_ascii=False)
        for private in (
            PRIVATE_LABEL,
            PRIVATE_RECEIPT,
            PRIVATE_OBJECT_ID,
            "PRIVATE-person-name.md",
            "PRIVATE-reviewer",
            str(self.root),
        ):
            self.assertNotIn(private, rendered)

    def test_cli_dry_runs_and_receipt_lookup_still_route_to_read_services(self) -> None:
        def safe_result(action: str) -> dict:
            return {
                "ok": True,
                "state": "ready",
                "dry_run": True,
                "lifecycle_action": action,
                "summary": {},
                "blockers": [],
                "warnings": [],
                "would_change": [],
                "privacy_guards": {"writes": False},
            }

        with (
            mock.patch.object(
                completion_workflows,
                "zettel_objet_link_plan",
                return_value=safe_result("zettel_objet_link_plan"),
            ) as link_plan,
            mock.patch.object(
                completion_workflows,
                "zettel_objet_link_revert_plan",
                return_value=safe_result("zettel_objet_link_revert_plan"),
            ) as revert_plan,
            mock.patch.object(
                completion_workflows,
                "zettel_objet_link_receipts",
                return_value=safe_result("zettel_objet_link_receipts"),
            ) as receipt_lookup,
        ):
            link_code, link, link_error = self._run_cli(
                [
                    "zettel-objet-link",
                    str(self.root),
                    "--zettel-id",
                    "zet_private_target",
                    "--object-id",
                    PRIVATE_OBJECT_ID,
                    "--role",
                    "evidence",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            revert_code, revert, revert_error = self._run_cli(
                [
                    "zettel-objet-link-revert",
                    str(self.root),
                    "--receipt",
                    PRIVATE_RECEIPT,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            receipts_code, receipts, receipts_error = self._run_cli(
                [
                    "zettel-objet-link-receipts",
                    str(self.root),
                    "--zettel-id",
                    "zet_private_target",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(link_code, 0, link_error)
        self.assertEqual(revert_code, 0, revert_error)
        self.assertEqual(receipts_code, 0, receipts_error)
        self.assertTrue(link["dry_run"])
        self.assertTrue(revert["dry_run"])
        self.assertTrue(receipts["dry_run"])
        link_plan.assert_called_once()
        revert_plan.assert_called_once()
        receipt_lookup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
