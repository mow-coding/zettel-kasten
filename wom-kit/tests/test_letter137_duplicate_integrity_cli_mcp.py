from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wom_kit import (
    approval_integrity,
    archive_cli,
    archive_services,
    duplicate_object_reconciliation,
    mcp_server,
)
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID


AUTH_KEY = b"i" * 32
REVIEWER = "person:local-reviewer"
PRIVATE_OBJECT_ID = "sha256:" + "a" * 64
PRIVATE_RECEIPT_NAME = "PRIVATE-source.related." + "3" * 16 + ".zettel-edge.json"
PRIVATE_PATH = "inbox/PRIVATE-person-name.md"
PRIVATE_REVIEWER = "person:PRIVATE-reviewer-name"


class _ApprovingNative:
    def __init__(self) -> None:
        self.contents: list[str] = []

    def show(self, **kwargs: str) -> tuple[int, bool]:
        self.contents.append(str(kwargs["content"]))
        return APPROVE_BUTTON_ID, True


class _StableKeyProvider:
    def use_key(self, archive_root, consumer, *, create_if_missing=False):
        if create_if_missing is not True:
            raise AssertionError("exact approval must request the stable key")
        return consumer(memoryview(bytearray(AUTH_KEY)))


def _with_test_key(_archive_root, consumer):
    return consumer(memoryview(bytearray(AUTH_KEY)))


class Letter137DuplicateIntegrityCliMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.archive = self._make_archive(self.base / "archive")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _make_archive(root: Path) -> Path:
        root.mkdir()
        (root / "archive.yml").write_text(
            "archive_id: archive:test-duplicate-integrity-cli\n",
            encoding="utf-8",
        )
        return root

    @staticmethod
    def _write_duplicate_manifest(root: Path) -> Path:
        manifest = root / "objects" / "manifests" / "files.jsonl"
        manifest.parent.mkdir(parents=True)
        row = {
            "object_id": PRIVATE_OBJECT_ID,
            "sha256": "a" * 64,
            "logical_key": "PRIVATE/logical/name",
            "mime": "text/plain",
            "size_bytes": 41,
            "locations": [
                {
                    "provider": "local",
                    "kind": "local",
                    "path": PRIVATE_PATH,
                }
            ],
            "provenance": {"source": "test"},
        }
        encoded = json.dumps(row, separators=(",", ":")) + "\n"
        manifest.write_text(encoded + encoded, encoding="utf-8")
        indexed = archive_services.index_archive(root)
        if not indexed["ok"] or indexed["index_state"] != "current":
            raise AssertionError(indexed)
        return manifest

    @staticmethod
    def _write_edge_receipt(root: Path) -> str:
        relative = "receipts/edges/" + PRIVATE_RECEIPT_NAME
        path = root.joinpath(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "schema_version": "wom-kit/zettel-edge-receipt/v0.1",
            "lifecycle_action": "zettel_edge_write",
            "receipt_kind": "zettel_edge_write",
            "created_at": "2026-08-20T09:00:00Z",
            "archive_id": "archive:test-duplicate-integrity-cli",
            "edge_id": "edge:" + "3" * 64,
            "edge_type": "related",
            "source_zettel_id": "zet_private_source",
            "source_zettel_path": PRIVATE_PATH,
            "target_ref": "zet:PRIVATE-target",
            "target_kind": "zettel",
            "visibility": "private",
            "reviewed_by": PRIVATE_REVIEWER,
            "result": {
                "edge_written": True,
                "zettel_frontmatter_updated": True,
                "receipt_written": True,
            },
        }
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return relative

    def _run_cli(self, arguments: list[str]) -> tuple[int, dict, str]:
        parsed = self.parser.parse_args(arguments)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = parsed.func(parsed)
        output = stdout.getvalue()
        return code, json.loads(output) if output else {}, stderr.getvalue()

    @staticmethod
    def _approval_patches(native: _ApprovingNative):
        return (
            mock.patch(
                "wom_kit.exact_human_approval_windows._CtypesTaskDialogNative",
                return_value=native,
            ),
            mock.patch(
                "wom_kit.exact_human_approval_workflow._production_key_provider",
                return_value=_StableKeyProvider(),
            ),
        )

    def test_duplicate_cli_plans_then_applies_only_exact_rows(self) -> None:
        manifest = self._write_duplicate_manifest(self.archive)
        code, plan, error = self._run_cli(
            [
                "duplicate-object-reconciliation",
                str(self.archive),
                "--dry-run",
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 0, error)
        self.assertTrue(plan["exact_row_deduplication_permitted"])
        self.assertEqual(plan["removable_row_count"], 1)

        native = _ApprovingNative()
        patches = self._approval_patches(native)
        with patches[0], patches[1]:
            code, result, error = self._run_cli(
                [
                    "duplicate-object-reconcile",
                    str(self.archive),
                    "--approve",
                    "--expected-plan-sha256",
                    plan["plan_sha256"],
                    "--expected-manifest-sha256",
                    plan["manifest_sha256"],
                    "--reviewed-by",
                    REVIEWER,
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 0, error)
        self.assertEqual(result["removed_exact_duplicate_row_count"], 1)
        self.assertTrue(result["snapshot_preserved"])
        self.assertEqual(result["exact_human_approval"]["status"], "succeeded")
        self.assertEqual(len(manifest.read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual(len(native.contents), 1)
        serialized = json.dumps(result)
        self.assertNotIn(PRIVATE_OBJECT_ID, serialized)
        self.assertNotIn(PRIVATE_PATH, serialized)
        self.assertNotIn(PRIVATE_OBJECT_ID, native.contents[0])
        self.assertNotIn(PRIVATE_PATH, native.contents[0])

    def test_integrity_cli_audit_guard_and_exact_overlay_workflow(self) -> None:
        relative = self._write_edge_receipt(self.archive)
        key_patch = mock.patch.object(
            archive_cli,
            "_use_archive_receipt_authentication_key",
            side_effect=_with_test_key,
        )
        with key_patch:
            code, audit, error = self._run_cli(
                [
                    "approval-receipt-integrity-audit",
                    str(self.archive),
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 0, error)
        self.assertTrue(audit["exact_human_approval_claims_checked"])
        self.assertEqual(audit["receipt_count"], 1)
        inspected = audit["results"][0]

        guard_args = [
            "approval-integrity-guard",
            str(self.archive),
            "--affected-kind",
            inspected["affected_kind"],
            "--affected-id-sha256",
            inspected["affected_id_sha256"],
            "--format",
            "json",
        ]
        with key_patch:
            code, guard, error = self._run_cli(guard_args)
        self.assertEqual(code, 0, error)
        self.assertTrue(guard["allowed"])

        overlay_base = [
            "approval-integrity-repair",
            str(self.archive),
            "--operation-receipt",
            relative,
            "--expected-operation-receipt-sha256",
            inspected["operation_receipt_sha256"],
            "--affected-kind",
            inspected["affected_kind"],
            "--affected-id-sha256",
            inspected["affected_id_sha256"],
            "--state",
            "review_required",
            "--format",
            "json",
        ]
        with key_patch:
            code, plan, error = self._run_cli(overlay_base + ["--dry-run"])
        self.assertEqual(code, 0, error)
        self.assertTrue(plan["approval_required_for_write"])

        native = _ApprovingNative()
        patches = self._approval_patches(native)
        with key_patch, patches[0], patches[1]:
            code, overlay, error = self._run_cli(
                overlay_base
                + [
                    "--approve",
                    "--expected-current-overlay-digest",
                    plan["prior_overlay_digest"],
                    "--expected-plan-sha256",
                    plan["plan_sha256"],
                    "--reviewed-by",
                    REVIEWER,
                ]
            )
        self.assertEqual(code, 0, error)
        self.assertTrue(overlay["claim_finalization_required"])
        self.assertEqual(overlay["claim_status_at_return"], "started")
        self.assertEqual(overlay["exact_human_approval"]["status"], "succeeded")
        self.assertEqual(len(native.contents), 1)

        with key_patch:
            code, blocked_guard, error = self._run_cli(guard_args)
        self.assertEqual(code, 1, error)
        self.assertTrue(blocked_guard["blocked"])
        self.assertEqual(blocked_guard["current_state"], "review_required")

        serialized = json.dumps(
            [audit, guard, plan, overlay, blocked_guard],
            ensure_ascii=False,
        )
        for private in (
            PRIVATE_RECEIPT_NAME,
            PRIVATE_PATH,
            PRIVATE_REVIEWER,
            str(self.archive),
        ):
            self.assertNotIn(private, serialized)

        overlay_parser = self.parser._subparsers._group_actions[0].choices[
            "approval-integrity-overlay"
        ]
        option_names = {
            option
            for action in overlay_parser._actions
            for option in action.option_strings
        }
        self.assertNotIn("--receipt-authentication-key", option_names)

    def test_read_key_helpers_use_callback_boundary_without_creating_a_key(self) -> None:
        native = object()
        provider = mock.Mock()

        def use_key(archive_root, consumer, *, create_if_missing=False):
            self.assertEqual(Path(archive_root), self.archive)
            self.assertFalse(create_if_missing)
            return consumer(memoryview(bytearray(AUTH_KEY)))

        provider.use_key.side_effect = use_key
        with (
            mock.patch(
                "wom_kit.credential_secure_intake_windows._CtypesWindowsNativeFacade",
                return_value=native,
            ) as native_factory,
            mock.patch(
                "wom_kit.credential_secure_registry._StableArchiveFingerprintKeyProvider",
                return_value=provider,
            ) as provider_factory,
        ):
            cli_result = archive_cli._use_archive_receipt_authentication_key(
                self.archive,
                lambda key: {"ok": bytes(key) == AUTH_KEY},
            )
            mcp_result = mcp_server._mcp_use_archive_receipt_authentication_key(
                self.archive,
                lambda key: {"ok": bytes(key) == AUTH_KEY},
            )

        self.assertTrue(cli_result["ok"])
        self.assertTrue(mcp_result["ok"])
        self.assertEqual(provider.use_key.call_count, 2)
        self.assertEqual(native_factory.call_count, 2)
        self.assertEqual(provider_factory.call_count, 2)
        native_factory.assert_called_with(cli_live_approved=True)
        provider_factory.assert_called_with(native)

    def test_mcp_read_surfaces_and_write_intents_are_fail_closed(self) -> None:
        duplicate_archive = self._make_archive(self.base / "duplicate-mcp")
        self._write_duplicate_manifest(duplicate_archive)
        relative = self._write_edge_receipt(self.archive)
        before = {
            path.relative_to(self.archive).as_posix(): path.read_bytes()
            for path in self.archive.rglob("*")
            if path.is_file()
        }

        duplicate = mcp_server.handle_tools_call(
            {
                "name": "duplicate_object_reconciliation_plan",
                "arguments": {"archive_root": str(duplicate_archive)},
            }
        )["structuredContent"]
        self.assertTrue(duplicate["ok"])

        key_patch = mock.patch.object(
            mcp_server,
            "_mcp_use_archive_receipt_authentication_key",
            side_effect=_with_test_key,
        )
        with key_patch:
            audit = mcp_server.handle_tools_call(
                {
                    "name": "approval_integrity_audit",
                    "arguments": {"archive_root": str(self.archive)},
                }
            )["structuredContent"]
            inspected = audit["results"][0]
            guard = mcp_server.handle_tools_call(
                {
                    "name": "approval_integrity_guard",
                    "arguments": {
                        "archive_root": str(self.archive),
                        "affected_kind": inspected["affected_kind"],
                        "affected_id_sha256": inspected["affected_id_sha256"],
                    },
                }
            )["structuredContent"]
            overlay_plan = mcp_server.handle_tools_call(
                {
                    "name": "approval_integrity_overlay_plan",
                    "arguments": {
                        "archive_root": str(self.archive),
                        "operation_receipt": relative,
                        "expected_operation_receipt_sha256": inspected[
                            "operation_receipt_sha256"
                        ],
                        "affected_kind": inspected["affected_kind"],
                        "affected_id_sha256": inspected["affected_id_sha256"],
                        "state": "review_required",
                    },
                }
            )["structuredContent"]
        self.assertTrue(audit["ok"])
        self.assertTrue(guard["allowed"])
        self.assertTrue(overlay_plan["ok"])
        after = {
            path.relative_to(self.archive).as_posix(): path.read_bytes()
            for path in self.archive.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)

        with (
            mock.patch.object(
                duplicate_object_reconciliation,
                "_apply_duplicate_object_reconciliation_core",
                side_effect=AssertionError("duplicate writer called"),
            ) as duplicate_writer,
            mock.patch.object(
                approval_integrity,
                "create_approval_integrity_overlay",
                side_effect=AssertionError("overlay writer called"),
            ) as overlay_writer,
        ):
            blocked_duplicate = mcp_server.tool_duplicate_object_reconciliation_plan(
                {"approve": True}
            )["structuredContent"]
            blocked_overlay = mcp_server.tool_approval_integrity_overlay_plan(
                {"approved": True}
            )["structuredContent"]
        duplicate_writer.assert_not_called()
        overlay_writer.assert_not_called()
        for result in (blocked_duplicate, blocked_overlay):
            self.assertEqual(
                result["reason_codes"],
                ["exact_human_approval_cli_required"],
            )
            self.assertTrue(result["requires_local_native_approval_ui"])
            self.assertFalse(result["write_performed"])

        names = {item["name"] for item in mcp_server.TOOL_DEFINITIONS}
        self.assertTrue(
            {
                "duplicate_object_reconciliation_plan",
                "approval_integrity_audit",
                "approval_integrity_guard",
                "approval_integrity_overlay_plan",
            }.issubset(names)
        )
        for definition in mcp_server.TOOL_DEFINITIONS:
            if definition["name"] in {
                "duplicate_object_reconciliation_plan",
                "approval_integrity_audit",
                "approval_integrity_guard",
                "approval_integrity_overlay_plan",
            }:
                properties = definition["inputSchema"]["properties"]
                self.assertIs(properties["approve"]["const"], False)
                self.assertNotIn("receipt_authentication_key", properties)

        serialized = json.dumps(
            [duplicate, audit, guard, overlay_plan],
            ensure_ascii=False,
        )
        for private in (
            PRIVATE_OBJECT_ID,
            PRIVATE_RECEIPT_NAME,
            PRIVATE_PATH,
            PRIVATE_REVIEWER,
            str(self.archive),
        ):
            self.assertNotIn(private, serialized)


if __name__ == "__main__":
    unittest.main()
