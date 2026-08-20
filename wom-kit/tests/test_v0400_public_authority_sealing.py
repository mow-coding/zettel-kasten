from __future__ import annotations

import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import wom_kit
from wom_kit import (
    archive_services,
    credential_capability,
    credential_continuity,
    credential_popup_windows,
    credential_secure_intake,
    credential_secure_intake_windows,
    credential_secure_registry,
    credential_visible_console_windows,
    credential_workflows,
    duplicate_object_reconciliation,
    exact_human_approval,
    exact_human_approval_link,
    exact_human_approval_windows,
    exact_human_approval_workflow,
    legacy_cleanup_bound_delete,
    notion_http_adapter,
    notion_page_recovery,
    source_fidelity_session_evidence,
)


class PublicAuthoritySealingTests(unittest.TestCase):
    def test_exact_human_public_surface_cannot_inject_or_mint_authority(self) -> None:
        retired_names = {
            exact_human_approval: (
                "ClaimedExactHumanApproval",
                "claim_exact_human_approval",
            ),
            exact_human_approval_windows: (
                "ExactHumanApprovalDecision",
                "ExactHumanApprovalNative",
                "request_exact_human_approval",
            ),
            exact_human_approval_workflow: (
                "ArchiveAuthenticationKeyProvider",
                "execute_exact_human_approved_write",
            ),
        }
        for module, names in retired_names.items():
            exported = tuple(getattr(module, "__all__", ()))
            for name in names:
                with self.subTest(module=module.__name__, name=name):
                    self.assertFalse(hasattr(module, name))
                    self.assertNotIn(name, exported)
                    self.assertFalse(hasattr(wom_kit, name))

        private_workflow = (
            exact_human_approval_workflow._execute_exact_human_approved_write
        )
        self.assertEqual(
            tuple(inspect.signature(private_workflow).parameters),
            ("archive_root", "context", "writer"),
        )
        with self.assertRaises(TypeError):
            private_workflow(
                ".",
                object(),  # type: ignore[arg-type]
                lambda _claim: {"ok": True},
                native=object(),  # type: ignore[call-arg]
                key_provider=object(),
            )

    def test_credential_adoption_public_surface_cannot_inject_worker(self) -> None:
        retired_names = (
            "CredentialAdoptionWorkerInvocation",
            "CredentialAdoptionWorkerSpawner",
            "InjectedCredentialAdoptionWorkerSpawner",
            "SpawnCredentialAdoptionWorkerSpawner",
            "InjectedNotionRecoveryWorkerSpawner",
            "NotionRecoveryWorkerInvocation",
            "NotionRecoveryWorkerSpawner",
            "SpawnNotionRecoveryWorkerSpawner",
        )
        for name in retired_names:
            with self.subTest(name=name):
                self.assertFalse(hasattr(credential_workflows, name))
                self.assertNotIn(name, credential_workflows.__all__)
                self.assertFalse(hasattr(wom_kit, name))

        public = credential_workflows.execute_windows_notion_credential_adoption
        self.assertNotIn("worker_spawner", inspect.signature(public).parameters)
        with self.assertRaises(TypeError):
            public(
                ".",
                {},
                expected_plan_digest="0" * 64,
                expected_archive_id="archive:test",
                reviewed_anchor_uuid="00000000-0000-0000-0000-000000000000",
                requested_capabilities=(),
                approved=False,
                worker_spawner=object(),  # type: ignore[call-arg]
            )

    def test_credential_and_provider_effect_engines_are_private(self) -> None:
        retired = {
            credential_capability: (
                "CredentialCapability",
                "CredentialCapabilityLease",
            ),
            credential_continuity: (
                "AdapterProcessResult",
                "CredentialAdoptionPlan",
                "CredentialProviderVerificationEvidence",
                "CredentialStoreVerificationEvidence",
                "CredentialUseBroker",
                "KeePassXCExactEntryAdapter",
                "TrustedConsumerRegistry",
                "WindowsCredentialManagerExactAdapter",
                "approve_credential_adoption",
                "execute_credential_broker_use",
                "verify_credential_provider_for_adoption",
                "verify_credential_store_for_adoption",
            ),
            credential_secure_registry: (
                "AuthenticatedArchiveReceiptCommitter",
                "ClaimedCredentialCapabilityUse",
                "ReceiptBackedNotionCredentialBroker",
                "StableArchiveFingerprintKeyProvider",
                "claim_credential_capability_use",
                "create_archive_atomic_json_receipt_committer",
                "evolve_legacy_authenticated_workspace_scope",
                "persist_duplicate_lifecycle_decision",
                "use_authenticated_secure_credential_for_revalidation",
            ),
            credential_secure_intake: (
                "AtomicJsonReceiptCommitter",
                "FileOneTimeRequestClaims",
                "IsolatedWorkerSpawner",
                "SecureIntakeProcessLauncher",
                "SecureIntakeWorker",
                "WindowsCredentialManagerExactStore",
                "WorkerInvocation",
            ),
            credential_secure_intake_windows: (
                "CtypesWindowsNativeFacade",
                "WindowsCredentialPopupSecretUI",
                "build_windows_secure_intake_worker",
            ),
            credential_popup_windows: (
                "prompt_secret_in_native_popup",
            ),
            credential_visible_console_windows: (
                "prompt_masked_secret_in_new_console",
            ),
            legacy_cleanup_bound_delete: (
                "delete_exact_approved_empty_directory",
                "delete_exact_approved_file",
            ),
            notion_page_recovery: (
                "FilesystemRecoveryStorage",
                "execute_recovery",
            ),
            notion_http_adapter: (
                "NotionBearerSecret",
                "NotionHttpAdapter",
                "NotionIdentityVerifier",
                "NotionSecureIntakeVerifier",
                "NotionSecureIntakeIdentity",
            ),
            archive_services: (
                "ResumeLedger",
                "S3CompatibleTransport",
                "notion_api_get_json",
                "notion_execute_one_ancestor_fetch_request",
                "object_storage_execute_one_upload",
                "object_storage_resolve_transport",
                "object_storage_upload_evidence_write_receipt",
                "object_storage_write_execution_receipt",
                "resolve_credential_value",
                "tiro_api_request_json",
                "tiro_optional_get",
                "tiro_paginated_get",
                "tiro_read_credential_value",
                "tiro_windows_credential_manager_read_secret",
                "update_manifest_with_object_storage_upload_evidence",
            ),
        }
        for module, names in retired.items():
            exported = tuple(getattr(module, "__all__", ()))
            for name in names:
                with self.subTest(module=module.__name__, name=name):
                    self.assertFalse(hasattr(module, name))
                    self.assertNotIn(name, exported)
                    self.assertFalse(hasattr(wom_kit, name))

    def test_credential_lifecycle_approval_blocks_before_key_access(self) -> None:
        calls = (
            lambda: credential_workflows.approve_authenticated_credential_lifecycle(
                ".",
                provider="notion",
                workspace_fingerprint="sha256:" + "a" * 64,
                selected_default_credential_id="credential_test",
                expected_plan_sha256="sha256:" + "b" * 64,
                reviewed_by="person:reviewer",
                native=object(),  # type: ignore[arg-type]
            ),
            lambda: credential_workflows.decide_authenticated_credential_lifecycle(
                ".",
                provider="notion",
                workspace_fingerprint="sha256:" + "a" * 64,
                selected_default_credential_id="credential_test",
                approved=True,
                expected_plan_sha256="sha256:" + "b" * 64,
                reviewed_by="person:reviewer",
                native=object(),  # type: ignore[arg-type]
            ),
        )
        with mock.patch.object(
            credential_workflows,
            "_key_provider",
            side_effect=AssertionError("credential key must not be read"),
        ) as key_provider:
            for invoke in calls:
                result = invoke()
                self.assertFalse(result["ok"])
                self.assertEqual(
                    result["reason_code"],
                    "compound_exact_human_approval_binding_required",
                )
        key_provider.assert_not_called()

    def test_unclaimed_exact_writers_block_before_private_reads(self) -> None:
        with mock.patch.object(
            archive_services,
            "require_existing_archive_root",
            side_effect=AssertionError("archive must not be read"),
        ) as root_reader:
            cases = (
                lambda: archive_services.promote_zettel(
                    ".",
                    relative_path="inbox/private.md",
                    reviewed_by="person:reviewer",
                ),
                lambda: archive_services.mint_zettel(
                    ".",
                    relative_path="inbox/private.md",
                    reviewed_by="person:reviewer",
                ),
                lambda: archive_services.retire_minted_draft(
                    ".",
                    relative_path="inbox/private.md",
                    reviewed_by="person:reviewer",
                    approve=True,
                ),
                lambda: archive_services.write_retired_draft_from_plan(
                    ".",
                    {},
                    reviewed_by="person:reviewer",
                ),
                lambda: archive_services.zettel_edge_write(
                    ".",
                    from_path="zettels/private.md",
                    target_ref="zet:private",
                    edge_type="related",
                    approve=True,
                    reviewed_by="person:reviewer",
                ),
            )
            for invoke in cases:
                with self.subTest(invoke=repr(invoke)):
                    with self.assertRaises(
                        archive_services.ArchiveServiceError
                    ) as captured:
                        invoke()
                    self.assertEqual(
                        str(captured.exception),
                        "exact_human_approval_required",
                    )
        root_reader.assert_not_called()

        with mock.patch.object(
            source_fidelity_session_evidence,
            "_prepare",
            side_effect=AssertionError("private source must not be read"),
        ) as prepare:
            blocked = source_fidelity_session_evidence.approve_session_evidence(
                ".",
                "profiles/local/private.txt",
                session_ref="private",
                source_role="source",
                producer_kind="human",
                produced_at="2026-08-20T00:00:00+00:00",
                captured_at="2026-08-20T00:00:00+00:00",
                input_provenance_sha256=None,
                expected_plan_sha256="a" * 64,
                reviewed_by="person:reviewer",
            )
        prepare.assert_not_called()
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["blockers"], ["exact_human_approval_required"])

        with mock.patch.object(
            exact_human_approval_link,
            "_archive_root",
            side_effect=AssertionError("archive must not be read"),
        ) as link_root:
            with self.assertRaises(
                exact_human_approval_link.ExactHumanApprovalLinkError
            ) as captured:
                exact_human_approval_link.write_exact_human_approval_link(
                    ".",
                    approval_claim=object(),  # type: ignore[arg-type]
                    approval_context=object(),  # type: ignore[arg-type]
                    operation="create_draft",
                    plan_sha256="sha256:" + "a" * 64,
                    target_binding_sha256="sha256:" + "b" * 64,
                    source_operation_receipt="private.json",
                    expected_source_operation_receipt_sha256=(
                        "sha256:" + "c" * 64
                    ),
                    effect="created",
                )
        link_root.assert_not_called()
        self.assertEqual(
            captured.exception.code,
            "exact_human_approval_link_approval_claim_invalid",
        )

    def test_duplicate_plan_public_api_returns_only_safe_projection(self) -> None:
        retired_names = (
            "DuplicateObjectReconciliationPlan",
            "apply_duplicate_object_reconciliation",
            "duplicate_object_reconciliation_context",
        )
        for name in retired_names:
            self.assertFalse(hasattr(duplicate_object_reconciliation, name))
            self.assertNotIn(name, duplicate_object_reconciliation.__all__)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "archive"
            manifest = root / "objects" / "manifests" / "files.jsonl"
            manifest.parent.mkdir(parents=True)
            (root / "archive.yml").write_text(
                "archive_id: archive:test\n",
                encoding="utf-8",
            )
            private_id = "sha256:" + "d" * 64
            row = {
                "object_id": private_id,
                "sha256": private_id,
                "logical_key": "private/location/name",
                "mime": "text/plain",
                "size_bytes": 7,
            }
            encoded = json.dumps(
                row,
                sort_keys=True,
                separators=(",", ":"),
            )
            manifest.write_text(encoded + "\n" + encoded + "\n", encoding="utf-8")
            result = (
                duplicate_object_reconciliation.plan_duplicate_object_reconciliation(
                    root
                )
            )

        self.assertIs(type(result), dict)
        self.assertFalse(any(hasattr(result, name) for name in ("archive_root", "_manifest_bytes")))
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(private_id, serialized)
        self.assertNotIn("private/location/name", serialized)
        self.assertFalse(result["object_ids_echoed"])
        self.assertFalse(result["paths_echoed"])
        self.assertFalse(result["row_content_echoed"])

    def test_private_evidence_bytes_reader_is_not_public(self) -> None:
        self.assertFalse(
            hasattr(
                source_fidelity_session_evidence,
                "read_verified_session_evidence",
            )
        )
        self.assertNotIn(
            "read_verified_session_evidence",
            source_fidelity_session_evidence.__all__,
        )


if __name__ == "__main__":
    unittest.main()
