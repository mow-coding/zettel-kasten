from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wom_kit import archive_cli
from wom_kit.exact_human_approval_windows import (
    APPROVE_BUTTON_ID,
    IDCANCEL,
)


PLAN_SHA256 = "a" * 64
TARGET_SHA256 = "b" * 64


class FakeNative:
    def __init__(self, events: list[str], *, approved: bool = True) -> None:
        self.events = events
        self.approved = approved
        self.calls: list[dict[str, str]] = []

    def show(self, **kwargs: str) -> tuple[int, bool]:
        self.events.append("dialog")
        self.calls.append(dict(kwargs))
        if self.approved:
            return APPROVE_BUTTON_ID, True
        return IDCANCEL, False


class FakeKeyProvider:
    def __init__(self, events: list[str], *, fail: bool = False) -> None:
        self.events = events
        self.fail = fail
        self.calls = 0

    def use_key(self, archive_root, consumer, *, create_if_missing=False):
        self.calls += 1
        self.events.append("key")
        if self.fail:
            raise RuntimeError("private-provider-detail")
        self.assert_create_if_missing(create_if_missing)
        return consumer(memoryview(bytearray(b"k" * 32)))

    @staticmethod
    def assert_create_if_missing(value: bool) -> None:
        if value is not True:
            raise AssertionError("live exact approval must request the stable key")


class Letter136ExactHumanCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()

    def make_archive(self, parent: Path) -> Path:
        root = parent / "archive"
        root.mkdir()
        (root / "archive.yml").write_text(
            "archive_id: archive:test-exact-human-cli\n",
            encoding="utf-8",
        )
        return root

    def run_args(self, values: list[str]) -> tuple[int, str, str]:
        args = self.parser.parse_args(values)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = args.func(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def session_args(self, root: Path) -> list[str]:
        return [
            "source-fidelity-session-evidence",
            str(root),
            "--source-file",
            ".wom-scratch/private/source-fidelity/session-evidence/private-name.txt",
            "--session-ref",
            "private-session-ref",
            "--source-role",
            "reviewed_session_transcript",
            "--producer-kind",
            "human",
            "--produced-at",
            "2026-08-20T00:00:00Z",
            "--captured-at",
            "2026-08-20T00:01:00Z",
            "--approve",
            "--expected-plan-sha256",
            PLAN_SHA256,
            "--reviewed-by",
            "person:test-reviewer",
            "--format",
            "json",
        ]

    def create_args(self, root: Path) -> list[str]:
        return [
            "create-draft",
            str(root),
            "--title",
            "PRIVATE TITLE MUST NOT LEAK",
            "--body",
            "PRIVATE BODY MUST NOT LEAK",
            "--abstract",
            "reviewed abstract",
            "--facet",
            "topic=private",
            "--creation-mode",
            "ai_generated",
            "--assisted-by",
            "ai:test-runtime",
            "--draft-id",
            "zet_20260820_exact_human_test",
            "--created-at",
            "2026-08-20T09:00:00+09:00",
            "--expected-body-sha256",
            TARGET_SHA256,
            "--draft-approved-by",
            "person:test-reviewer",
            "--source-fidelity",
            "faithful_summary",
            "--fidelity-audience",
            "private_self",
            "--fidelity-source-object-id",
            "sha256:" + "c" * 64,
            "--expected-source-fidelity-plan-sha256",
            PLAN_SHA256,
            "--approve",
            "--format",
            "json",
        ]

    def test_session_approve_preflights_then_uses_fake_native_and_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            events: list[str] = []
            native = FakeNative(events)
            provider = FakeKeyProvider(events)

            def plan(*_args, **_kwargs):
                events.append("preflight")
                return {
                    "ok": True,
                    "plan_sha256": PLAN_SHA256,
                    "source": {"raw_sha256": TARGET_SHA256},
                    "warnings": [],
                }

            def approve(*_args, **_kwargs):
                events.append("writer")
                return {"ok": True, "state": "approved"}

            with (
                patch.object(
                    archive_cli.source_fidelity_session_evidence,
                    "plan_session_evidence",
                    side_effect=plan,
                ),
                patch.object(
                    archive_cli.source_fidelity_session_evidence,
                    "approve_session_evidence",
                    side_effect=approve,
                ),
                patch(
                    "wom_kit.exact_human_approval_windows._CtypesTaskDialogNative",
                    return_value=native,
                ),
                patch(
                    "wom_kit.exact_human_approval_workflow._production_key_provider",
                    return_value=provider,
                ),
            ):
                code, stdout, stderr = self.run_args(self.session_args(root))

            self.assertEqual(code, 0, stderr)
            self.assertEqual(events, ["preflight", "dialog", "key", "writer"])
            result = json.loads(stdout)
            self.assertEqual(result["exact_human_approval"]["status"], "succeeded")
            self.assertEqual(
                result["exact_human_approval"]["approval_id"],
                result["exact_human_approval_reference"]["approval_id"],
            )
            primary = native.calls[0]["content"]
            advanced = native.calls[0]["expanded_information"]
            self.assertNotIn("sha256:" + PLAN_SHA256, primary)
            self.assertNotIn("sha256:" + TARGET_SHA256, primary)
            self.assertIn("sha256:" + PLAN_SHA256, advanced)
            self.assertIn("sha256:" + TARGET_SHA256, advanced)
            rendered = primary + "\n" + advanced
            self.assertNotIn("private-session-ref", rendered)
            self.assertNotIn("private-name.txt", rendered)

    def test_session_cancel_never_acquires_key_or_enters_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            events: list[str] = []
            native = FakeNative(events, approved=False)
            provider = FakeKeyProvider(events)

            with (
                patch.object(
                    archive_cli.source_fidelity_session_evidence,
                    "plan_session_evidence",
                    return_value={
                        "ok": True,
                        "plan_sha256": PLAN_SHA256,
                        "source": {"raw_sha256": TARGET_SHA256},
                        "warnings": [],
                    },
                ),
                patch.object(
                    archive_cli.source_fidelity_session_evidence,
                    "approve_session_evidence",
                    side_effect=AssertionError("writer entered after cancellation"),
                ),
                patch(
                    "wom_kit.exact_human_approval_windows._CtypesTaskDialogNative",
                    return_value=native,
                ),
                patch(
                    "wom_kit.exact_human_approval_workflow._production_key_provider",
                    return_value=provider,
                ),
            ):
                code, stdout, stderr = self.run_args(self.session_args(root))

            self.assertEqual(code, 1, stderr)
            self.assertEqual(events, ["dialog"])
            self.assertEqual(provider.calls, 0)
            result = json.loads(stdout)
            self.assertEqual(
                result["reason_codes"], ["exact_human_approval_cancelled"]
            )
            combined = stdout + stderr
            self.assertNotIn("private-session-ref", combined)
            self.assertNotIn("private-name.txt", combined)
            self.assertFalse((root / "profiles").exists())

    def test_session_partial_write_returns_started_claim_for_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            events: list[str] = []

            with (
                patch.object(
                    archive_cli.source_fidelity_session_evidence,
                    "plan_session_evidence",
                    return_value={
                        "ok": True,
                        "plan_sha256": PLAN_SHA256,
                        "source": {"raw_sha256": TARGET_SHA256},
                        "warnings": [],
                    },
                ),
                patch.object(
                    archive_cli.source_fidelity_session_evidence,
                    "approve_session_evidence",
                    return_value={
                        "ok": False,
                        "state": "partial",
                        "blockers": ["session_evidence_final_verification_failed"],
                        "persistence": {"files_written_count": 1},
                    },
                ),
                patch(
                    "wom_kit.exact_human_approval_windows._CtypesTaskDialogNative",
                    return_value=FakeNative(events),
                ),
                patch(
                    "wom_kit.exact_human_approval_workflow._production_key_provider",
                    return_value=FakeKeyProvider(events),
                ),
            ):
                code, stdout, stderr = self.run_args(self.session_args(root))

            self.assertEqual(code, 1, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["state"], "partial")
            self.assertEqual(result["exact_human_approval"]["status"], "started")
            self.assertEqual(
                result["exact_human_approval_reconciliation"]["reason_code"],
                "approval_claim_reconciliation_required",
            )
            self.assertFalse(
                result["exact_human_approval_reconciliation"]
                ["automatic_retry_allowed"]
            )
            self.assertNotIn("exact_human_approval_operation_blocked", stdout)

    def test_ai_create_approve_binds_reviewed_plan_and_body_before_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            events: list[str] = []
            native = FakeNative(events)
            provider = FakeKeyProvider(events)

            def create(_root, **kwargs):
                if kwargs["dry_run"]:
                    events.append("preflight")
                    return {
                        "ok": True,
                        "dry_run": True,
                        "source_fidelity_plan_sha256": PLAN_SHA256,
                        "body_sha256": TARGET_SHA256,
                        "warnings": ["private-warning-detail"],
                    }
                events.append("writer")
                return {
                    "ok": True,
                    "dry_run": False,
                    "zettel_id": "zet_20260820_exact_human_test",
                    "path": "inbox/zet_20260820_exact_human_test.md",
                    "warnings": [],
                }

            with (
                patch.object(
                    archive_cli.archive_services,
                    "create_draft_zettel",
                    side_effect=create,
                ),
                patch(
                    "wom_kit.exact_human_approval_windows._CtypesTaskDialogNative",
                    return_value=native,
                ),
                patch(
                    "wom_kit.exact_human_approval_workflow._production_key_provider",
                    return_value=provider,
                ),
            ):
                code, stdout, stderr = self.run_args(self.create_args(root))

            self.assertEqual(code, 0, stderr)
            self.assertEqual(events, ["preflight", "dialog", "key", "writer"])
            result = json.loads(stdout)
            self.assertEqual(result["exact_human_approval"]["status"], "succeeded")
            primary = native.calls[0]["content"]
            advanced = native.calls[0]["expanded_information"]
            self.assertNotIn("sha256:" + PLAN_SHA256, primary)
            self.assertNotIn("sha256:" + TARGET_SHA256, primary)
            self.assertNotRegex(primary, r"warning_set_[0-9a-f]{52}")
            self.assertIn("sha256:" + PLAN_SHA256, advanced)
            self.assertIn("sha256:" + TARGET_SHA256, advanced)
            self.assertRegex(advanced, r"warning_set_[0-9a-f]{52}")
            rendered = primary + "\n" + advanced
            self.assertNotIn("PRIVATE TITLE", rendered)
            self.assertNotIn("PRIVATE BODY", rendered)
            self.assertNotIn("private-warning-detail", rendered)

    def test_ai_create_key_failure_is_fixed_and_content_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            events: list[str] = []
            native = FakeNative(events)
            provider = FakeKeyProvider(events, fail=True)
            writer_calls = 0

            def create(_root, **kwargs):
                nonlocal writer_calls
                if kwargs["dry_run"]:
                    return {
                        "ok": True,
                        "dry_run": True,
                        "source_fidelity_plan_sha256": PLAN_SHA256,
                        "body_sha256": TARGET_SHA256,
                        "warnings": [],
                    }
                writer_calls += 1
                return {"ok": True}

            with (
                patch.object(
                    archive_cli.archive_services,
                    "create_draft_zettel",
                    side_effect=create,
                ),
                patch(
                    "wom_kit.exact_human_approval_windows._CtypesTaskDialogNative",
                    return_value=native,
                ),
                patch(
                    "wom_kit.exact_human_approval_workflow._production_key_provider",
                    return_value=provider,
                ),
            ):
                code, stdout, stderr = self.run_args(self.create_args(root))

            self.assertEqual(code, 1, stderr)
            self.assertEqual(events, ["dialog", "key"])
            self.assertEqual(writer_calls, 0)
            result = json.loads(stdout)
            self.assertEqual(
                result["reason_codes"],
                ["exact_human_approval_key_unavailable"],
            )
            combined = stdout + stderr
            self.assertNotIn("PRIVATE TITLE", combined)
            self.assertNotIn("PRIVATE BODY", combined)
            self.assertNotIn("private-provider-detail", combined)

    def test_ai_create_writer_exception_is_unknown_and_content_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            events: list[str] = []
            native = FakeNative(events)
            provider = FakeKeyProvider(events)

            def create(_root, **kwargs):
                if kwargs["dry_run"]:
                    return {
                        "ok": True,
                        "dry_run": True,
                        "source_fidelity_plan_sha256": PLAN_SHA256,
                        "body_sha256": TARGET_SHA256,
                        "warnings": [],
                    }
                events.append("writer")
                raise RuntimeError("PRIVATE WRITE FAILURE DETAIL")

            with (
                patch.object(
                    archive_cli.archive_services,
                    "create_draft_zettel",
                    side_effect=create,
                ),
                patch(
                    "wom_kit.exact_human_approval_windows._CtypesTaskDialogNative",
                    return_value=native,
                ),
                patch(
                    "wom_kit.exact_human_approval_workflow._production_key_provider",
                    return_value=provider,
                ),
            ):
                code, stdout, stderr = self.run_args(self.create_args(root))

            self.assertEqual(code, 1, stderr)
            self.assertEqual(events, ["dialog", "key", "writer"])
            result = json.loads(stdout)
            self.assertEqual(
                result["reason_codes"],
                ["exact_human_approval_state_unknown"],
            )
            combined = stdout + stderr
            self.assertNotIn("PRIVATE TITLE", combined)
            self.assertNotIn("PRIVATE BODY", combined)
            self.assertNotIn("PRIVATE WRITE FAILURE DETAIL", combined)
            claims = list(
                (
                    root
                    / "profiles"
                    / "local"
                    / "exact-human-approvals"
                    / "claims"
                ).glob("*.json")
            )
            self.assertEqual(len(claims), 1)
            self.assertEqual(json.loads(claims[0].read_text(encoding="utf-8"))["status"], "started")

    def test_ai_create_non_success_preserves_reconciliation_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_archive(Path(tmp))
            events: list[str] = []

            def create(_root, **kwargs):
                if kwargs["dry_run"]:
                    return {
                        "ok": True,
                        "dry_run": True,
                        "source_fidelity_plan_sha256": PLAN_SHA256,
                        "body_sha256": TARGET_SHA256,
                        "warnings": [],
                    }
                return {
                    "ok": False,
                    "state": "partial",
                    "blockers": ["draft_receipt_final_verification_failed"],
                }

            with (
                patch.object(
                    archive_cli.archive_services,
                    "create_draft_zettel",
                    side_effect=create,
                ),
                patch(
                    "wom_kit.exact_human_approval_windows._CtypesTaskDialogNative",
                    return_value=FakeNative(events),
                ),
                patch(
                    "wom_kit.exact_human_approval_workflow._production_key_provider",
                    return_value=FakeKeyProvider(events),
                ),
            ):
                code, stdout, stderr = self.run_args(self.create_args(root))

            self.assertEqual(code, 1, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["state"], "partial")
            self.assertEqual(result["exact_human_approval"]["status"], "started")
            self.assertTrue(
                result["exact_human_approval_reconciliation"]["required"]
            )
            self.assertNotIn("exact_human_approval_operation_blocked", stdout)

    def test_promote_mint_and_retire_project_reconciliation_instead_of_success(self) -> None:
        partial = {
            "ok": False,
            "state": "canonical_written_index_update_failed",
            "exact_human_approval": {"status": "started"},
            "exact_human_approval_reconciliation": {
                "required": True,
                "reason_code": "approval_claim_reconciliation_required",
                "automatic_retry_allowed": False,
            },
        }
        binding = SimpleNamespace(
            plan_sha256="sha256:" + PLAN_SHA256,
            target_binding_sha256="sha256:" + TARGET_SHA256,
            context=lambda **_kwargs: object(),
        )
        cases = (
            (
                [
                    "promote",
                    "ARCHIVE",
                    "--path",
                    "inbox/example.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test-reviewer",
                    "--format",
                    "json",
                ],
                "promote_zettel_dry_run",
                "promote_zet_approval_binding",
                {"ok": True, "blockers": [], "warnings": []},
            ),
            (
                [
                    "mint-zet",
                    "ARCHIVE",
                    "--path",
                    "inbox/example.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test-reviewer",
                    "--format",
                    "json",
                ],
                "mint_zettel_dry_run",
                "mint_zet_approval_binding",
                {"ok": True, "blockers": [], "warnings": []},
            ),
            (
                [
                    "retire-draft",
                    "ARCHIVE",
                    "--path",
                    "inbox/example.md",
                    "--approve",
                    "--reviewed-by",
                    "person:test-reviewer",
                    "--format",
                    "json",
                ],
                "retire_minted_draft",
                "retire_draft_approval_binding",
                {"ok": True, "blockers": [], "warnings": []},
            ),
        )
        for args, preview_name, binding_name, preview in cases:
            with self.subTest(command=args[0]):
                with (
                    patch.object(
                        archive_cli.archive_services,
                        preview_name,
                        return_value=preview,
                    ),
                    patch.object(
                        archive_cli.operation_approval_binding,
                        binding_name,
                        return_value=binding,
                    ),
                    patch.object(
                        archive_cli.archive_services,
                        "read_archive_id",
                        return_value="archive:test",
                    ),
                    patch.object(
                        archive_cli,
                        "_execute_exact_human_approved_write",
                        return_value=dict(partial),
                    ),
                ):
                    code, stdout, stderr = self.run_args(args)
                    text_code, text_stdout, text_stderr = self.run_args(
                        args[:-2]
                    )
                self.assertEqual(code, 1, stderr)
                result = json.loads(stdout)
                self.assertEqual(
                    result["exact_human_approval"]["status"], "started"
                )
                self.assertEqual(
                    result["exact_human_approval_reconciliation"]["reason_code"],
                    "approval_claim_reconciliation_required",
                )
                self.assertEqual(text_code, 1, text_stderr)
                self.assertIn("requires reconciliation", text_stdout)
                self.assertIn("do not retry automatically", text_stdout)
                self.assertIn("Approval claim: started", text_stdout)
                self.assertNotIn("Promoted ", text_stdout)
                self.assertNotIn("Minted ", text_stdout)
                self.assertNotIn("Retired inbox draft", text_stdout)


if __name__ == "__main__":
    unittest.main()
