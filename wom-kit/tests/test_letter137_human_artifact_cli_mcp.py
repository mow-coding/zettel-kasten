from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wom_kit import archive_cli, human_artifact_registry, mcp_server
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID


REVIEWER = "person:local-reviewer"
PRIVATE_NAME = "PRIVATE-HUMAN-NAME.txt"
PRIVATE_BODY = b"PRIVATE HUMAN ARTIFACT BODY MUST NOT LEAK"


class _ApprovingNative:
    def __init__(self) -> None:
        self.contents: list[str] = []

    def show(self, **kwargs: str) -> tuple[int, bool]:
        self.contents.append(str(kwargs["content"]))
        return APPROVE_BUTTON_ID, True


class _StableKeyProvider:
    def use_key(self, archive_root, consumer, *, create_if_missing=False):
        if create_if_missing is not True:
            raise AssertionError("live approval must request a stable archive key")
        return consumer(memoryview(bytearray(b"h" * 32)))


class Letter137HumanArtifactCliMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = archive_cli.build_parser()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.archive = self.base / "archive"
        self.project = self.base / "project"
        self.archive.mkdir()
        self.project.mkdir()
        (self.archive / "archive.yml").write_text(
            "archive_id: archive:test-letter137-human-artifacts\n",
            encoding="utf-8",
        )
        (self.archive / ".gitignore").write_text(
            "profiles/local/\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _run_cli(self, arguments: list[str]) -> tuple[int, dict, str]:
        parsed = self.parser.parse_args(arguments)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = parsed.func(parsed)
        output = stdout.getvalue()
        return code, json.loads(output) if output else {}, stderr.getvalue()

    def _approval_patches(self):
        native = _ApprovingNative()
        provider = _StableKeyProvider()
        return native, (
            mock.patch(
                "wom_kit.exact_human_approval_windows._CtypesTaskDialogNative",
                return_value=native,
            ),
            mock.patch(
                "wom_kit.exact_human_approval_workflow._production_key_provider",
                return_value=provider,
            ),
        )

    def test_cli_full_lifecycle_uses_one_native_claim_per_write(self) -> None:
        alias = self.parser.parse_args(
            [
                "human-artifact-project-root",
                str(self.archive),
                "--project-root",
                str(self.project),
                "--dry-run",
            ]
        )
        self.assertIs(alias.func, archive_cli.command_human_artifact_register_root)

        code, registration_plan, error = self._run_cli(
            [
                "human-artifact-register-root",
                str(self.archive),
                "--project-root",
                str(self.project),
                "--dry-run",
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 0, error)
        self.assertTrue(registration_plan["requires_exact_human_approval_claim"])

        native, patches = self._approval_patches()
        with patches[0], patches[1]:
            code, registered, error = self._run_cli(
                [
                    "human-artifact-register-root",
                    str(self.archive),
                    "--project-root",
                    str(self.project),
                    "--approve",
                    "--expected-plan-sha256",
                    registration_plan["plan_sha256"],
                    "--reviewed-by",
                    REVIEWER,
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 0, error)
        self.assertEqual(registered["state"], "registered")
        self.assertFalse(registered["exact_human_approval_claim_finalized"])
        self.assertEqual(
            registered["exact_human_approval_claim_finalization_owner"],
            "approval_workflow",
        )
        self.assertEqual(registered["exact_human_approval"]["status"], "succeeded")
        self.assertEqual(len(native.contents), 1)
        self.assertNotIn(str(self.project), native.contents[0])

        scratch = self.project / ".wom-scratch"
        scratch.mkdir()
        artifact = scratch / PRIVATE_NAME
        artifact.write_bytes(PRIVATE_BODY)

        code, scan, error = self._run_cli(
            [
                "human-artifact-registry-scan",
                str(self.archive),
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(scan["artifact_count"], 1)
        artifact_id = scan["items"][0]["artifact_id"]
        serialized_scan = json.dumps(scan, ensure_ascii=False)
        self.assertNotIn(PRIVATE_NAME, serialized_scan)
        self.assertNotIn(str(self.project), serialized_scan)
        self.assertNotIn(PRIVATE_BODY.decode("ascii"), serialized_scan)

        digest = "sha256:" + hashlib.sha256(PRIVATE_BODY).hexdigest()
        transition_base = [
            "human-artifact-transition",
            str(self.archive),
            "--artifact-id",
            artifact_id,
            "--target-state",
            "reviewed_current",
            "--content-sha256",
            digest,
            "--size-bytes",
            str(len(PRIVATE_BODY)),
            "--related-ref",
            "receipt_id=receipt:human-review",
            "--format",
            "json",
        ]
        code, transition_plan, error = self._run_cli(
            transition_base + ["--dry-run"]
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(transition_plan["related_refs"][0]["kind"], "receipt_id")

        native, patches = self._approval_patches()
        with patches[0], patches[1]:
            code, transitioned, error = self._run_cli(
                transition_base
                + [
                    "--approve",
                    "--expected-plan-sha256",
                    transition_plan["plan_sha256"],
                    "--expected-current-state-sha256",
                    transition_plan["expected_current_state_sha256"],
                    "--reviewed-by",
                    REVIEWER,
                ]
            )
        self.assertEqual(code, 0, error)
        self.assertEqual(transitioned["state"], "transition_recorded")
        self.assertFalse(transitioned["exact_human_approval_claim_finalized"])
        self.assertEqual(transitioned["exact_human_approval"]["status"], "succeeded")
        self.assertEqual(len(native.contents), 1)
        self.assertTrue(artifact.is_file())
        self.assertEqual(artifact.read_bytes(), PRIVATE_BODY)

    def test_mcp_tools_are_read_only_and_return_no_private_names_or_paths(self) -> None:
        names = {item["name"] for item in mcp_server.TOOL_DEFINITIONS}
        self.assertTrue(
            {
                "human_artifact_root_registration_plan",
                "human_artifact_registry_scan",
                "human_artifact_transition_plan",
            }.issubset(names)
        )
        for definition in mcp_server.TOOL_DEFINITIONS:
            if definition["name"] in {
                "human_artifact_root_registration_plan",
                "human_artifact_registry_scan",
                "human_artifact_transition_plan",
            }:
                self.assertIs(
                    definition["inputSchema"]["properties"]["approve"]["const"],
                    False,
                )

        before = sorted(
            path.relative_to(self.archive).as_posix()
            for path in self.archive.rglob("*")
            if path.is_file()
        )
        root_plan = mcp_server.tool_human_artifact_root_registration_plan(
            {
                "archive_root": str(self.archive),
                "project_root": str(self.project),
            }
        )["structuredContent"]
        self.assertTrue(root_plan["ok"])

        scratch = self.archive / ".wom-scratch"
        scratch.mkdir()
        artifact = scratch / PRIVATE_NAME
        artifact.write_bytes(PRIVATE_BODY)
        scan = mcp_server.tool_human_artifact_registry_scan(
            {"archive_root": str(self.archive)}
        )["structuredContent"]
        artifact_id = scan["items"][0]["artifact_id"]
        digest = "sha256:" + hashlib.sha256(PRIVATE_BODY).hexdigest()
        transition = mcp_server.tool_human_artifact_transition_plan(
            {
                "archive_root": str(self.archive),
                "artifact_id": artifact_id,
                "target_state": "reviewed_current",
                "content_sha256": digest,
                "size_bytes": len(PRIVATE_BODY),
                "related_refs": [
                    {"kind": "receipt_id", "ref": "receipt:human-review"}
                ],
            }
        )["structuredContent"]
        self.assertTrue(transition["ok"])

        after = sorted(
            path.relative_to(self.archive).as_posix()
            for path in self.archive.rglob("*")
            if path.is_file()
        )
        self.assertEqual(
            after,
            sorted(before + [".wom-scratch/" + PRIVATE_NAME]),
        )
        serialized = json.dumps(
            [root_plan, scan, transition],
            ensure_ascii=False,
        )
        self.assertNotIn(PRIVATE_NAME, serialized)
        self.assertNotIn(str(self.archive), serialized)
        self.assertNotIn(str(self.project), serialized)
        self.assertNotIn(PRIVATE_BODY.decode("ascii"), serialized)

    def test_mcp_write_attempts_fail_closed_before_registry_writers(self) -> None:
        with (
            mock.patch.object(
                human_artifact_registry,
                "register_project_root",
                side_effect=AssertionError("registration writer called"),
            ) as registration_writer,
            mock.patch.object(
                human_artifact_registry,
                "write_artifact_transition",
                side_effect=AssertionError("transition writer called"),
            ) as transition_writer,
        ):
            registration = mcp_server.tool_human_artifact_root_registration_plan(
                {
                    "archive_root": str(self.archive),
                    "project_root": str(self.project),
                    "dry_run": False,
                    "approve": True,
                }
            )["structuredContent"]
            transition = mcp_server.tool_human_artifact_transition_plan(
                {
                    "archive_root": str(self.archive),
                    "approve": True,
                }
            )["structuredContent"]

        registration_writer.assert_not_called()
        transition_writer.assert_not_called()
        for result in (registration, transition):
            self.assertFalse(result["ok"])
            self.assertEqual(
                result["reason_codes"],
                ["exact_human_approval_cli_required"],
            )
            self.assertTrue(result["requires_local_native_approval_ui"])
            self.assertFalse(result["write_performed"])

    def test_delivery_root_mode_is_explicit_read_only_and_content_free(self) -> None:
        delivery = self.base / "PRIVATE-DELIVERY"
        delivery.mkdir()
        (delivery / PRIVATE_NAME).write_bytes(PRIVATE_BODY)

        code, cli_plan, error = self._run_cli(
            [
                "human-artifact-register-root",
                str(self.archive),
                "--external-root",
                str(delivery),
                "--root-kind",
                "external_delivery",
                "--dry-run",
                "--format",
                "json",
            ]
        )
        self.assertEqual(code, 0, error)
        self.assertEqual(cli_plan["registered_root_kind"], "external_delivery")
        self.assertEqual(cli_plan["scan_scope"], "registered_delivery_root")

        mcp_plan = mcp_server.tool_human_artifact_root_registration_plan(
            {
                "archive_root": str(self.archive),
                "project_root": str(delivery),
                "root_kind": "external_delivery",
            }
        )["structuredContent"]
        self.assertEqual(mcp_plan["registered_root_kind"], "external_delivery")
        self.assertEqual(mcp_plan["scan_scope"], "registered_delivery_root")
        rendered = json.dumps([cli_plan, mcp_plan])
        self.assertNotIn(str(delivery), rendered)
        self.assertNotIn("PRIVATE-DELIVERY", rendered)
        self.assertNotIn(PRIVATE_NAME, rendered)
        self.assertNotIn(PRIVATE_BODY.decode("ascii"), rendered)
        self.assertFalse((self.archive / "profiles").exists())


if __name__ == "__main__":
    unittest.main()
