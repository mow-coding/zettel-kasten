from __future__ import annotations

import argparse
import hashlib
import io
import inspect
import json
import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType
from unittest import mock

import wom_kit
from wom_kit import (
    archive_cli,
    archive_services,
    completion_workflows,
    credential_workflows,
    mcp_server,
)


COMPOUND_APPROVAL_BLOCKER = (
    "compound_exact_human_approval_binding_required"
)
PRIVATE_ROOT_NAME = "PRIVATE-DURABLE-EXTERNAL-ROOT-SECRET"
PRIVATE_LEDGER = ".wom-scratch/private/PRIVATE-LEDGER-SECRET.jsonl"
PRIVATE_TREE = ".wom-scratch/private/PRIVATE-NOTION-TREE-SECRET.json"
PRIVATE_OUTPUT = "workbench/PRIVATE-NOTION-OUTPUT-SECRET.json"
PRIVATE_REQUEST = ".wom-scratch/private/PRIVATE-RECOVERY-REQUEST-SECRET.json"
PRIVATE_PLAN = ".wom-scratch/private/PRIVATE-WRITE-PLAN-SECRET.json"
PRIVATE_MANIFEST = ".wom-scratch/private/PRIVATE-BATCH-MANIFEST-SECRET.json"
PRIVATE_RECEIPT = "receipts/PRIVATE-DURABLE-RECEIPT-SECRET.json"
PRIVATE_REVIEWER = "person:PRIVATE-DURABLE-REVIEWER-SECRET"
PRIVATE_DIGEST = "PRIVATE-DURABLE-PLAN-DIGEST-SECRET"
PRIVATE_STORE = "store:PRIVATE-DURABLE-STORE-SECRET"
PRIVATE_VIEW = "view:PRIVATE-DURABLE-VIEW-SECRET"
PRIVATE_LOCATOR = "PRIVATE-EXTERNAL-LOCATOR-SECRET"
PRIVATE_LOCATOR_ID = "locator:PRIVATE-EXTERNAL-SECRET"
PRIVATE_CASE = "case:PRIVATE-QUARANTINE-SECRET"


PRIVATE_VALUES = (
    PRIVATE_ROOT_NAME,
    PRIVATE_LEDGER,
    PRIVATE_TREE,
    PRIVATE_OUTPUT,
    PRIVATE_REQUEST,
    PRIVATE_PLAN,
    PRIVATE_MANIFEST,
    PRIVATE_RECEIPT,
    PRIVATE_REVIEWER,
    PRIVATE_DIGEST,
    PRIVATE_STORE,
    PRIVATE_VIEW,
    PRIVATE_LOCATOR,
    PRIVATE_LOCATOR_ID,
    PRIVATE_CASE,
)


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class _DurableExternalAssertions(unittest.TestCase):
    def _root(self, parent: Path) -> Path:
        root = parent / PRIVATE_ROOT_NAME
        root.mkdir()
        (root / "sentinel.bin").write_bytes(b"must remain byte exact")
        return root

    def _assert_fixed_service_block(
        self,
        *,
        root: Path,
        lifecycle_action: str,
        invoke: Callable[[], dict[str, object]],
    ) -> None:
        before = _snapshot(root)
        result = invoke()

        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["lifecycle_action"], lifecycle_action)
        self.assertEqual(result["blockers"], [COMPOUND_APPROVAL_BLOCKER])
        self.assertEqual(result["reason_codes"], [COMPOUND_APPROVAL_BLOCKER])
        self.assertEqual(result["would_change"], [])
        self.assertEqual(result["files_written"], [])
        self.assertIs(result["private_values_echoed"], False)
        self.assertEqual(_snapshot(root), before)
        rendered = json.dumps(result, ensure_ascii=False)
        for private in (str(root), *PRIVATE_VALUES):
            self.assertNotIn(private, rendered)


class Letter137DurableExternalServiceBoundaryTests(
    _DurableExternalAssertions
):
    def test_archive_services_block_before_archive_private_or_provider_reads(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            cases = (
                (
                    "object_storage_setup",
                    lambda: archive_services.approve_object_storage_setup_plan(
                        root,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "prehashed_objet_ledger_register",
                    lambda: archive_services.prehashed_objet_ledger_register(
                        root,
                        PRIVATE_LEDGER,
                        store_ref=PRIVATE_STORE,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "object_storage_upload_evidence_register",
                    lambda: archive_services.object_storage_upload_evidence_register(
                        root,
                        PRIVATE_LEDGER,
                        store_ref=PRIVATE_STORE,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "object_storage_upload_run",
                    lambda: archive_services.object_storage_upload_run(
                        root,
                        store_ref=PRIVATE_STORE,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "object_storage_adopt_existing",
                    lambda: archive_services.object_storage_adopt_existing_run(
                        root,
                        store_ref=PRIVATE_STORE,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "object_storage_wom_location_reconcile",
                    lambda: archive_services.object_storage_wom_location_reconcile_run(
                        root,
                        receipt=PRIVATE_RECEIPT,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "notion_ancestor_fetch_adapter_run",
                    lambda: archive_services.notion_ancestor_fetch_adapter_run(
                        root,
                        tree_path=PRIVATE_TREE,
                        output_path=PRIVATE_OUTPUT,
                        source="notion",
                        approve=True,
                        dry_run=False,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "source_intake_record",
                    lambda: archive_services.source_intake_record(
                        root,
                        PRIVATE_PLAN,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "source_intake_batch",
                    lambda: archive_services.source_intake_batch(
                        root,
                        PRIVATE_MANIFEST,
                        approve=True,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "quarantine_foreign_block",
                    lambda: archive_services.quarantine_foreign_block(
                        root,
                        plan_path=PRIVATE_PLAN,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                        expected_case_id=PRIVATE_CASE,
                    ),
                ),
                (
                    "record_quarantine_decision",
                    lambda: archive_services.record_quarantine_decision(
                        root,
                        decision_preview_path=PRIVATE_PLAN,
                        approve=True,
                        reviewed_by=PRIVATE_REVIEWER,
                        expected_case_id=PRIVATE_CASE,
                    ),
                ),
                (
                    "delegate",
                    lambda: archive_services.delegate_zets(
                        root,
                        view_id=PRIVATE_VIEW,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
            )
            with mock.patch.object(
                archive_services,
                "require_existing_archive_root",
                side_effect=AssertionError("archive/provider read entered"),
            ) as archive_read:
                for action, invoke in cases:
                    with self.subTest(action=action):
                        self._assert_fixed_service_block(
                            root=root,
                            lifecycle_action=action,
                            invoke=invoke,
                        )
            archive_read.assert_not_called()

    def test_external_locator_services_block_before_private_plan_core(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            cases = (
                (
                    "_locator_plan_core",
                    "external_locator_record",
                    lambda: completion_workflows.external_locator_record(
                        root,
                        zettel_id="zet_private",
                        locator_type="source_url",
                        locator_ref=PRIVATE_LOCATOR,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "_external_locator_deactivate_plan_core",
                    "external_locator_deactivate",
                    lambda: completion_workflows.external_locator_deactivate(
                        root,
                        zettel_id="zet_private",
                        locator_id=PRIVATE_LOCATOR_ID,
                        keep_locator_id=PRIVATE_LOCATOR_ID + "-keep",
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
                (
                    "_external_locator_revert_plan_core",
                    "external_locator_revert",
                    lambda: completion_workflows.external_locator_revert(
                        root,
                        receipt=PRIVATE_RECEIPT,
                        expected_plan_sha256=PRIVATE_DIGEST,
                        reviewed_by=PRIVATE_REVIEWER,
                    ),
                ),
            )
            for core_name, action, invoke in cases:
                with self.subTest(action=action), mock.patch.object(
                    completion_workflows,
                    core_name,
                    side_effect=AssertionError("external locator plan entered"),
                ) as core:
                    self._assert_fixed_service_block(
                        root=root,
                        lifecycle_action=action,
                        invoke=invoke,
                    )
                core.assert_not_called()

    def test_notion_page_recovery_services_block_before_credentials_or_worker(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            manifest = {
                "archive_id": "archive:PRIVATE-RECOVERY-SECRET",
                "request": PRIVATE_REQUEST,
            }
            with mock.patch.object(
                credential_workflows,
                "list_secure_credentials",
                side_effect=AssertionError("credential/archive read entered"),
            ) as credential_read, mock.patch.object(
                credential_workflows,
                "_execute_recovery",
                side_effect=AssertionError("low-level recovery engine entered"),
            ) as engine:
                self._assert_fixed_service_block(
                    root=root,
                    lifecycle_action=(
                        "authenticated_notion_page_recovery_execute"
                    ),
                    invoke=lambda: (
                        credential_workflows.execute_authenticated_notion_page_recovery(
                            root,
                            manifest,
                            expected_plan_sha256=PRIVATE_DIGEST,
                            reviewed_by=PRIVATE_REVIEWER,
                            max_items=5,
                            approved=True,
                            native=mock.sentinel.native,
                        )
                    ),
                )
                self._assert_fixed_service_block(
                    root=root,
                    lifecycle_action=(
                        "authenticated_notion_page_recovery_execute"
                    ),
                    invoke=lambda: (
                        credential_workflows.execute_spawned_authenticated_notion_page_recovery(
                            root,
                            manifest,
                            expected_plan_sha256=PRIVATE_DIGEST,
                            reviewed_by=PRIVATE_REVIEWER,
                            max_items=5,
                            approved=True,
                        )
                    ),
                )
            credential_read.assert_not_called()
            engine.assert_not_called()

    def test_low_level_injected_engines_are_not_public_dispatch_surfaces(self) -> None:
        retired_public_worker_names = (
            "CredentialAdoptionWorkerInvocation",
            "CredentialAdoptionWorkerSpawner",
            "InjectedCredentialAdoptionWorkerSpawner",
            "InjectedNotionRecoveryWorkerSpawner",
            "NotionRecoveryWorkerInvocation",
            "NotionRecoveryWorkerSpawner",
            "SpawnCredentialAdoptionWorkerSpawner",
            "SpawnNotionRecoveryWorkerSpawner",
        )
        for public_name in retired_public_worker_names:
            self.assertFalse(hasattr(credential_workflows, public_name))
            self.assertNotIn(public_name, credential_workflows.__all__)

        engines = (
            credential_workflows._execute_recovery,
            archive_services._notion_execute_one_ancestor_fetch_request,
            archive_services._object_storage_execute_one_upload,
            credential_workflows._execute_authenticated_notion_page_recovery_core,
            credential_workflows._execute_spawned_authenticated_notion_page_recovery_core,
        )
        cli_source = inspect.getsource(archive_cli)
        mcp_source = inspect.getsource(mcp_server)
        for engine in engines:
            self.assertFalse(hasattr(wom_kit, engine.__name__))
            self.assertNotIn(engine.__name__, cli_source)
            self.assertNotIn(engine.__name__, mcp_source)

        parser = archive_cli.build_parser()
        for action in parser._actions:
            choices = getattr(action, "choices", None)
            if not isinstance(choices, dict):
                continue
            for command_parser in choices.values():
                for engine in engines:
                    self.assertIsNot(
                        command_parser.get_default("func"),
                        engine,
                    )

    def test_legacy_notion_recover_executor_blocks_before_approval_or_fetch(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(Path(tmp))
            args = argparse.Namespace(archive_root=str(root))
            with mock.patch.object(
                archive_services,
                "credential_access_approval_plan",
                side_effect=AssertionError("credential approval entered"),
            ) as approval:
                self._assert_fixed_service_block(
                    root=root,
                    lifecycle_action="notion_recover",
                    invoke=lambda: archive_cli.run_approved_notion_recover(
                        args,
                        {"selected_tree_path": PRIVATE_TREE},
                        "env:PRIVATE-NOTION-CREDENTIAL-SECRET",
                    ),
                )
            approval.assert_not_called()


class Letter137DurableExternalCliBoundaryTests(
    _DurableExternalAssertions
):
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
                side_effect=AssertionError("durable/external service entered"),
            ) as service,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = args.func(args)

        self.assertEqual(code, 1, stderr.getvalue())
        service.assert_not_called()
        result = json.loads(stdout.getvalue())
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["lifecycle_action"], lifecycle_action)
        self.assertEqual(result["reason_codes"], [COMPOUND_APPROVAL_BLOCKER])
        self.assertIs(result["private_values_echoed"], False)
        rendered = stdout.getvalue() + stderr.getvalue()
        for private in (arguments[1], *PRIVATE_VALUES):
            self.assertNotIn(private, rendered)

    def test_all_durable_external_cli_writes_block_before_service_or_read(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root_path = self._root(Path(tmp))
            root = str(root_path)
            # ``object-storage`` now owns a separate exact-approved local-only
            # setup-registration contract.  Its provider-free writer and
            # dry-run are covered by test_object_storage_setup_registration;
            # this legacy list remains limited to still-fixed-closed external
            # writers.
            calls = (
                (
                    ["prehashed-objet-ledger", root, "--ledger", PRIVATE_LEDGER, "--approve", "--reviewed-by", PRIVATE_REVIEWER, "--format", "json"],
                    archive_services,
                    "prehashed_objet_ledger_register",
                    "prehashed_objet_ledger_register",
                ),
                (
                    ["object-storage-upload-evidence", root, "--ledger", PRIVATE_LEDGER, "--approve", "--reviewed-by", PRIVATE_REVIEWER, "--format", "json"],
                    archive_services,
                    "object_storage_upload_evidence_register",
                    "object_storage_upload_evidence_register",
                ),
                (
                    ["object-storage-upload", root, "--store-ref", PRIVATE_STORE, "--approve", "--reviewed-by", PRIVATE_REVIEWER, "--format", "json"],
                    archive_services,
                    "object_storage_upload_run",
                    "object_storage_upload_run",
                ),
                (
                    ["object-storage-adopt-existing", root, "--store-ref", PRIVATE_STORE, "--approve", "--reviewed-by", PRIVATE_REVIEWER, "--format", "json"],
                    archive_services,
                    "object_storage_adopt_existing_run",
                    "object_storage_adopt_existing",
                ),
                (
                    ["object-storage-wom-location-reconcile", root, "--receipt", PRIVATE_RECEIPT, "--approve", "--reviewed-by", PRIVATE_REVIEWER, "--format", "json"],
                    archive_services,
                    "object_storage_wom_location_reconcile_run",
                    "object_storage_wom_location_reconcile",
                ),
                (
                    ["notion-ancestor-fetch-adapter-run", root, "--tree", PRIVATE_TREE, "--source", "notion", "--approve", "--reviewed-by", PRIVATE_REVIEWER, "--format", "json"],
                    archive_services,
                    "notion_ancestor_fetch_adapter_run",
                    "notion_ancestor_fetch_adapter_run",
                ),
                (
                    ["notion-recover", root, "--approve", "--format", "json"],
                    archive_services,
                    "notion_recover_plan",
                    "notion_recover",
                ),
                (
                    ["notion-recover", root, "--format", "json"],
                    archive_services,
                    "notion_recover_plan",
                    "notion_recover",
                ),
                (
                    ["notion-page-recovery", root, "--request", PRIVATE_REQUEST, "--approve", "--expected-plan-sha256", PRIVATE_DIGEST, "--reviewed-by", PRIVATE_REVIEWER, "--format", "json"],
                    archive_services,
                    "require_existing_archive_root",
                    "authenticated_notion_page_recovery_execute",
                ),
                (
                    ["source-intake-batch", root, "--manifest", PRIVATE_MANIFEST, "--approve", "--expected-plan-sha256", PRIVATE_DIGEST, "--reviewed-by", PRIVATE_REVIEWER, "--format", "json"],
                    archive_services,
                    "source_intake_batch",
                    "source_intake_batch",
                ),
                (
                    ["external-locator-record", root, "--zettel-id", "zet_private", "--locator-type", "source_url", "--locator-ref", PRIVATE_LOCATOR, "--expected-plan-sha256", PRIVATE_DIGEST, "--approve", "--reviewed-by", PRIVATE_REVIEWER, "--format", "json"],
                    completion_workflows,
                    "external_locator_record",
                    "external_locator_record",
                ),
                (
                    ["external-locator-deactivate", root, "--zettel-id", "zet_private", "--locator-id", PRIVATE_LOCATOR_ID, "--keep-locator-id", PRIVATE_LOCATOR_ID + "-keep", "--expected-plan-sha256", PRIVATE_DIGEST, "--approve", "--reviewed-by", PRIVATE_REVIEWER, "--format", "json"],
                    completion_workflows,
                    "external_locator_deactivate",
                    "external_locator_deactivate",
                ),
                (
                    ["external-locator-revert", root, "--receipt", PRIVATE_RECEIPT, "--approve", "--expected-plan-sha256", PRIVATE_DIGEST, "--reviewed-by", PRIVATE_REVIEWER, "--format", "json"],
                    completion_workflows,
                    "external_locator_revert",
                    "external_locator_revert",
                ),
                (
                    ["quarantine-foreign-block", root, "--plan", PRIVATE_PLAN, "--approve", "--reviewed-by", PRIVATE_REVIEWER, "--expected-case-id", PRIVATE_CASE, "--format", "json"],
                    archive_services,
                    "quarantine_foreign_block",
                    "quarantine_foreign_block",
                ),
                (
                    ["record-quarantine-decision", root, "--decision-preview", PRIVATE_PLAN, "--approve", "--reviewed-by", PRIVATE_REVIEWER, "--expected-case-id", PRIVATE_CASE, "--format", "json"],
                    archive_services,
                    "record_quarantine_decision",
                    "record_quarantine_decision",
                ),
                (
                    ["delegate-zet", root, "--view", PRIVATE_VIEW, "--approve", "--reviewed-by", PRIVATE_REVIEWER, "--format", "json"],
                    archive_services,
                    "delegate_zets",
                    "delegate",
                ),
            )
            before = _snapshot(root_path)
            for arguments, module, service, action in calls:
                with self.subTest(command=arguments[0], action=action):
                    self._assert_cli_block(
                        arguments=arguments,
                        service_module=module,
                        service_name=service,
                        lifecycle_action=action,
                    )
            self.assertEqual(_snapshot(root_path), before)

    def test_read_only_plans_dry_runs_and_audits_still_dispatch(self) -> None:
        safe_result = {
            "ok": True,
            "state": "ready",
            "status": "ready",
            "dry_run": True,
            "blockers": [],
            "warnings": [],
            "would_change": [],
            "files_written": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root_path = self._root(Path(tmp))
            root = str(root_path)
            # The local-only ``object-storage`` dry-run is covered by its
            # dedicated v0.4.8 registration tests, not this legacy dispatcher
            # compatibility list.
            calls = (
                (["prehashed-objet-ledger", root, "--ledger", PRIVATE_LEDGER, "--dry-run", "--format", "json"], archive_services, "prehashed_objet_ledger_register"),
                (["object-storage-upload-evidence", root, "--ledger", PRIVATE_LEDGER, "--dry-run", "--format", "json"], archive_services, "object_storage_upload_evidence_register"),
                (["object-storage-upload", root, "--store-ref", PRIVATE_STORE, "--dry-run", "--format", "json"], archive_services, "object_storage_upload_run"),
                (["object-storage-adopt-existing", root, "--store-ref", PRIVATE_STORE, "--dry-run", "--format", "json"], archive_services, "object_storage_adopt_existing_run"),
                (["object-storage-wom-location-reconcile", root, "--receipt", PRIVATE_RECEIPT, "--dry-run", "--format", "json"], archive_services, "object_storage_wom_location_reconcile_run"),
                (["object-storage-upload-evidence-audit", root, "--receipt", PRIVATE_RECEIPT, "--dry-run", "--format", "json"], archive_services, "object_storage_upload_evidence_audit"),
                (["notion-ancestor-fetch-adapter-run", root, "--tree", PRIVATE_TREE, "--source", "notion", "--dry-run", "--format", "json"], archive_services, "notion_ancestor_fetch_adapter_run"),
                (["notion-recover", root, "--dry-run", "--format", "json"], archive_services, "notion_recover_plan"),
                (["source-intake-batch", root, "--manifest", PRIVATE_MANIFEST, "--dry-run", "--format", "json"], archive_services, "source_intake_batch"),
                (["external-locator-plan", root, "--zettel-id", "zet_private", "--locator-type", "source_url", "--locator-ref", PRIVATE_LOCATOR, "--dry-run", "--format", "json"], completion_workflows, "external_locator_plan"),
                (["external-locator-deactivate-plan", root, "--zettel-id", "zet_private", "--locator-id", PRIVATE_LOCATOR_ID, "--keep-locator-id", PRIVATE_LOCATOR_ID + "-keep", "--dry-run", "--format", "json"], completion_workflows, "external_locator_deactivate_plan"),
                (["external-locator-revert", root, "--receipt", PRIVATE_RECEIPT, "--dry-run", "--format", "json"], completion_workflows, "external_locator_revert_plan"),
                (["quarantine-foreign-block", root, "--plan", PRIVATE_PLAN, "--dry-run", "--format", "json"], archive_services, "quarantine_foreign_block"),
                (["record-quarantine-decision", root, "--decision-preview", PRIVATE_PLAN, "--dry-run", "--format", "json"], archive_services, "record_quarantine_decision"),
                (["delegate-zet", root, "--view", PRIVATE_VIEW, "--dry-run", "--format", "json"], archive_services, "delegate_zets_dry_run"),
            )
            before = _snapshot(root_path)
            for arguments, module, service_name in calls:
                with self.subTest(command=arguments[0]), mock.patch.object(
                    module,
                    service_name,
                    return_value=dict(safe_result),
                ) as service:
                    args = self.parser.parse_args(arguments)
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        code = args.func(args)
                    self.assertEqual(code, 0, stderr.getvalue())
                service.assert_called_once()

            recovery_args = self.parser.parse_args(
                [
                    "notion-page-recovery",
                    root,
                    "--request",
                    PRIVATE_REQUEST,
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            with mock.patch.object(
                archive_cli,
                "command_notion_page_recovery_plan",
                return_value=0,
            ) as recovery_plan:
                code = recovery_args.func(recovery_args)
            self.assertEqual(code, 0)
            recovery_plan.assert_called_once_with(recovery_args)
            self.assertEqual(_snapshot(root_path), before)


if __name__ == "__main__":
    unittest.main()
