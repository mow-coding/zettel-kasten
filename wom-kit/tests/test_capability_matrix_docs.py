from __future__ import annotations

import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent
MATRIX_PATH = KIT_ROOT / "docs" / "capability-matrix.md"
FREEZE_DOC_PATH = KIT_ROOT / "docs" / "v02x-freeze-v03-entry-boundary.md"
PROJECT_INTAKE_COOKBOOK_PATH = KIT_ROOT / "docs" / "project-intake-cookbook.md"
CREDENTIAL_STORE_CONTRACT_PATH = KIT_ROOT / "docs" / "credential-store-contract.md"
CREDENTIAL_REF_INVENTORY_PATH = KIT_ROOT / "docs" / "credential-ref-inventory-and-onboarding.md"
CREDENTIAL_STORE_RECOMMENDATIONS_PATH = KIT_ROOT / "docs" / "credential-store-recommendations.md"
CREDENTIAL_VAULT_ONBOARDING_PATH = KIT_ROOT / "docs" / "credential-vault-onboarding-plan.md"
BEGINNER_SETUP_MANUAL_PATH = KIT_ROOT / "docs" / "beginner-setup-manual.md"
CONNECTED_ACCOUNTS_PATH = KIT_ROOT / "docs" / "connected-accounts.md"
CREDENTIAL_SEMANTIC_RECIPE_PATH = KIT_ROOT / "docs" / "credential-semantic-extraction-recipe.md"
CREDENTIAL_PLAINTEXT_MIGRATION_PATH = KIT_ROOT / "docs" / "credential-plaintext-migration-plan.md"
OBJECT_STORAGE_RECOMMENDATIONS_PATH = KIT_ROOT / "docs" / "object-storage-recommendations.md"
OBJECT_STORAGE_ADAPTER_READINESS_PATH = KIT_ROOT / "docs" / "object-storage-adapter-readiness-plan.md"
OBJECT_STORAGE_OPERATION_REQUEST_PATH = KIT_ROOT / "docs" / "object-storage-operation-request-plan.md"
PRESIGNED_URL_PLAN_PATH = KIT_ROOT / "docs" / "presigned-url-plan.md"
DERIVED_TEXT_COVERAGE_PATH = KIT_ROOT / "docs" / "derived-text-coverage-and-toolchain.md"
DERIVED_TEXT_COMPLETENESS_SIGNAL_PATH = KIT_ROOT / "docs" / "derived-text-completeness-signal.md"
CREDENTIAL_ACCESS_BROKER_PATH = KIT_ROOT / "docs" / "credential-access-broker-plan.md"
CREDENTIAL_ACCESS_APPROVAL_PATH = KIT_ROOT / "docs" / "credential-access-approval-plan.md"
CREDENTIAL_POLICY_CHECK_PATH = KIT_ROOT / "docs" / "credential-policy-check.md"
CREDENTIAL_KEEPASSXC_COMMAND_PATH = KIT_ROOT / "docs" / "credential-keepassxc-command-plan.md"
CREDENTIAL_KEEPASSXC_WRITE_PATH = KIT_ROOT / "docs" / "credential-keepassxc-write.md"
CREDENTIAL_ADAPTER_READINESS_PATH = KIT_ROOT / "docs" / "credential-adapter-readiness-plan.md"
CREDENTIAL_ADAPTER_MANIFEST_PATH = KIT_ROOT / "docs" / "credential-adapter-manifest-plan.md"
CREDENTIAL_ADAPTER_MANIFEST_SCHEMA_PATH = KIT_ROOT / "schemas" / "credential-adapter-manifest.schema.json"
CREDENTIAL_ADAPTER_AUDIT_PATH = KIT_ROOT / "docs" / "credential-adapter-audit-plan.md"
HUMAN_ARTIFACT_STORE_CONTRACT_PATH = KIT_ROOT / "docs" / "human-artifact-store-contract.md"
EXTERNAL_EXPORT_PLAN_PATH = KIT_ROOT / "docs" / "external-export-plan.md"
ZET_SURFACE_PROTOTYPES_PATH = KIT_ROOT / "docs" / "zet-surface-prototypes.md"
IMAP_MAILBOX_SOURCE_PATH = KIT_ROOT / "docs" / "imap-mailbox-source.md"
IMAP_MAILBOX_OPERATION_REQUEST_PATH = KIT_ROOT / "docs" / "imap-mailbox-operation-request-plan.md"
IMAP_MAILBOX_ADAPTER_READINESS_PATH = KIT_ROOT / "docs" / "imap-mailbox-adapter-readiness-plan.md"
IMAP_MAILBOX_SELECTION_PATH = KIT_ROOT / "docs" / "imap-mailbox-selection-plan.md"
IMAP_MAILBOX_ADAPTER_MANIFEST_PATH = KIT_ROOT / "docs" / "imap-mailbox-adapter-manifest-plan.md"
IMAP_MAILBOX_ADAPTER_MANIFEST_WRITE_PATH = KIT_ROOT / "docs" / "imap-mailbox-adapter-manifest-write.md"
IMAP_MAILBOX_ADAPTER_MANIFEST_SCHEMA_PATH = KIT_ROOT / "schemas" / "imap-mailbox-adapter-manifest.schema.json"
IMAP_MAILBOX_ADAPTER_AUDIT_PATH = KIT_ROOT / "docs" / "imap-mailbox-adapter-audit-plan.md"
IMAP_MAILBOX_ADAPTER_AUDIT_WRITE_PATH = KIT_ROOT / "docs" / "imap-mailbox-adapter-audit-write.md"
IMAP_MAILBOX_ADAPTER_PREFLIGHT_PATH = KIT_ROOT / "docs" / "imap-mailbox-adapter-preflight-plan.md"
IMAP_MAILBOX_ADAPTER_EXECUTION_CONTRACT_PATH = KIT_ROOT / "docs" / "imap-mailbox-adapter-execution-contract.md"
IMAP_MAILBOX_HEADER_METADATA_SCAN_PATH = KIT_ROOT / "docs" / "imap-mailbox-header-metadata-scan.md"
IMAP_MAILBOX_HEADER_SCAN_RECEIPT_AUDIT_PATH = KIT_ROOT / "docs" / "imap-mailbox-header-scan-receipt-audit.md"
IMAP_MAILBOX_MATERIAL_SELECTION_PATH = KIT_ROOT / "docs" / "imap-mailbox-material-selection-plan.md"
IMAP_MAILBOX_MATERIAL_SELECTION_RECORD_PATH = KIT_ROOT / "docs" / "imap-mailbox-material-selection-record.md"
IMAP_MAILBOX_MATERIAL_CAPTURE_REQUEST_PATH = KIT_ROOT / "docs" / "imap-mailbox-material-capture-request-plan.md"
VERSION_TRUTH_SOURCE_PATH = KIT_ROOT / "docs" / "version-truth-source.md"
RUNTIME_CANONICAL_ENTRYPOINTS_PATH = KIT_ROOT / "docs" / "runtime-canonical-entrypoints.md"
NOTION_PAGE_SNAPSHOT_MODEL_PATH = KIT_ROOT / "docs" / "notion-page-snapshot-model.md"
OBJET_REF_RESOLUTION_PATH = KIT_ROOT / "docs" / "objet-ref-resolution.md"
ZETTEL_OBJET_LINKS_PATH = KIT_ROOT / "docs" / "zettel-objet-links.md"
SOURCE_OBJECT_STORAGE_POLICY_PATH = KIT_ROOT / "docs" / "source-object-storage-policy.md"
TEXT_PROVENANCE_HIERARCHY_PATH = KIT_ROOT / "docs" / "text-provenance-hierarchy.md"
NOTION_THREE_STORE_EXAMPLE_PATH = KIT_ROOT / "docs" / "notion-source-export-three-store-example.md"


class CapabilityMatrixDocsTests(unittest.TestCase):
    def test_capability_matrix_covers_required_statuses(self) -> None:
        text = MATRIX_PATH.read_text(encoding="utf-8")
        for status in (
            "implemented local command",
            "read-only preview",
            "approval-gated write",
            "local hygiene tool",
            "documented-only",
            "not implemented",
        ):
            with self.subTest(status=status):
                self.assertIn(status, text)

    def test_capability_matrix_covers_current_and_future_surfaces(self) -> None:
        text = MATRIX_PATH.read_text(encoding="utf-8")
        required_rows = (
            "Archive doctor",
            "Mint lifecycle",
            "Delegate lifecycle",
            "Block header preview",
            "Foreign block intake",
            "Foreign block quarantine write",
            "Attestation review candidate plan",
            "Attestation statement draft preview",
            "Attestation statement draft write",
            "Projection plan",
            "Credential ref plan",
            "Credential ref inventory",
            "Credential store recommendation",
            "Credential vault onboarding plan",
            "Beginner setup manual",
            "Connected accounts bridge",
            "Credential semantic extraction recipe",
            "Object storage recommendation",
            "Object storage adapter readiness plan",
            "Object storage operation request plan",
            "Credential plaintext migration plan",
            "Credential access broker plan",
            "Credential access approval plan",
            "Credential policy check",
            "Credential adapter readiness plan",
            "Credential adapter manifest plan",
            "Credential adapter audit plan",
            "External export plan",
            "IMAP mailbox source plan",
            "IMAP mailbox operation request plan",
            "IMAP mailbox adapter manifest plan",
            "IMAP mailbox adapter manifest write",
            "IMAP mailbox adapter readiness plan",
            "IMAP mailbox selection plan",
            "IMAP mailbox adapter audit plan",
            "IMAP mailbox adapter audit write",
            "IMAP mailbox adapter preflight plan",
            "IMAP mailbox adapter execution contract",
            "IMAP mailbox header metadata scan",
            "WOM-kit version truth source",
            "Runtime canonical entrypoints",
            "Derived text completeness signal",
            "Notion page snapshot model",
            "Objet ref resolver",
            "Presigned URL plan",
            "Publication surface baseline",
            "Closed sharing model",
            "Radio-frequency recommendation model",
            "Shared update record baseline",
            "Shared update record review preview",
            "Shared update record review index",
            "Shared update attestation/review write",
            "ZET transport threat model / would-transport plan",
            "v0.2.x freeze / v0.3.0 entry boundary",
            "Public proof anchoring",
            "DID-compatible identity research",
            "Release readiness gate",
            "Main branch protection readiness",
            "Real ZET transport",
            "Key-sharing registry",
            "Provider sync / WordPress",
            "Redis / queues / workers",
            "System token / validator governance",
            "Payments / blockchain / token / consensus",
        )
        for row in required_rows:
            with self.subTest(row=row):
                self.assertIn(row, text)

    def test_version_truth_source_doc_and_matrix_make_current_cli_explicit(self) -> None:
        version_text = VERSION_TRUTH_SOURCE_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.57.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.65 read-only version truth-source checkpoint with parent project pin discovery",
            "archive --version",
            "archive version --format json",
            "archive version <project-or-archive-root> --format json",
            "archive runtime-context <archive-root> --format json",
            "wom_kit.__version__",
            ".zettel-kasten/source/installed-version.txt",
            "parent_of_archive/.zettel-kasten/installed-version.txt",
            "consistency_state: project_pin_mismatch",
            "writes no files",
            "calls no providers",
            "reads no secrets",
            "redacts local absolute paths by default",
            "does not provide automatic upgrade",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, version_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "WOM-kit version truth source",
            "archive --version",
            "archive version [root] --format json",
            "runtime-context field `wom_kit_version`",
            "parent_of_archive/.zettel-kasten/installed-version.txt",
            "writes no files, calls no providers, and reads no secrets",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Version Truth Source](wom-kit/docs/version-truth-source.md)",
            "read-only WOM-kit version truth-source checks",
            "parent project installed-version pin discovery",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/version-truth-source.md",
            "version",
            "Print the running WOM-kit CLI version",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        for phrase in (
            "v0.3.57 - Version Truth Source",
            "archive version [inspection-root] --format text|json",
            "write no files",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)
        self.assertIn("[Version Truth Source](version-truth-source.md)", public_map_text)
        self.assertIn("[Version Truth Source](version-truth-source.md)", public_map_ko_text)

    def test_runtime_canonical_entrypoints_doc_and_matrix_keep_orientation_read_only(self) -> None:
        entrypoints_text = RUNTIME_CANONICAL_ENTRYPOINTS_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.58.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.58 read-only runtime canonical entrypoint checkpoint",
            "archive runtime-context <archive-root> --format json",
            "canonical_entrypoints",
            "archive.yml",
            "AGENTS.md",
            "source-bindings.yml",
            "provider-bindings.yml",
            "objects/manifests/files.jsonl",
            "objects/manifests/derived-text.jsonl",
            "reads no file bodies",
            "writes no files",
            "calls no providers",
            "reads no secrets",
            "echoes no local absolute paths by default",
            "does not enforce migration",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, entrypoints_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "Runtime canonical entrypoints",
            "Runtime-context field `canonical_entrypoints`",
            "`archive.yml` as the start-here file",
            "`source-bindings.yml`",
            "reads no file bodies",
            "echoes no local absolute paths by default",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Runtime Canonical Entry Points](wom-kit/docs/runtime-canonical-entrypoints.md)",
            "runtime-context canonical entrypoint metadata",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/runtime-canonical-entrypoints.md",
            "canonical entrypoint metadata",
            "WOM-kit version",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        for phrase in (
            "v0.3.58 - Runtime Canonical Entry Points",
            "`runtime-context` field `canonical_entrypoints`",
            "reads no file bodies",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)
        self.assertIn("[Runtime Canonical Entry Points](runtime-canonical-entrypoints.md)", public_map_text)
        self.assertIn("[Runtime Canonical Entry Points](runtime-canonical-entrypoints.md)", public_map_ko_text)

    def test_capability_matrix_documents_closing_plan_without_product_behavior(self) -> None:
        text = MATRIX_PATH.read_text(encoding="utf-8")
        self.assertIn("v0.3.0 Boundary Status", text)
        self.assertIn("v0.2 line closed", text)
        self.assertIn("avoid any new product CLI, MCP, service", text)
        self.assertIn("no real transport", text)
        self.assertIn("v0.2.60", text)
        self.assertIn("documentation, version, and test coverage only", text)
        self.assertIn("CLI-only shared update attestation/review record plus receipt", text)
        self.assertIn("MCP write/apply tools", text)
        self.assertIn("public proof anchoring", text)
        self.assertIn("DID/wallet/key custody", text)

    def test_readme_release_tag_sequence_includes_v0255(self) -> None:
        for relative in ("README.md", "README.ko.md"):
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            positions = [text.index(tag) for tag in ("v0.2.57", "v0.2.56", "v0.2.55", "v0.2.54")]
            with self.subTest(relative=relative):
                self.assertEqual(positions, sorted(positions))
                self.assertIn("wom-kit/docs/capability-matrix.md", text)
                self.assertIn("wom-kit/docs/v02x-freeze-v03-entry-boundary.md", text)

    def test_project_intake_cookbook_keeps_manual_receipt_spine(self) -> None:
        text = PROJECT_INTAKE_COOKBOOK_PATH.read_text(encoding="utf-8")
        for phrase in (
            "fake-archive rehearsal",
            "Bulk Raw First, Selective Promotion Later",
            "archive prehashed-objet-ledger --ledger ... --approve",
            "human-guided promotion spine",
            "archive-objets/` as a recommended local staging",
            "content-addressed store must be moved there",
            "archive project-intake-unpack-queue",
            "archive project-intake-unpack-choice",
            "opaque `item-0001` style refs",
            "archive project-intake-session-guide",
            "archive project-intake-record-answer",
            "archive project-intake-status",
            "archive source-intake-record",
            "archive objet-capture-selection",
            "archive objet-capture",
            "archive staged-cleanup-check",
            "does not echo the answer text",
            "$unpackChoiceReceipt",
            "$sourceIntakeReceipt",
            "$selectionJson",
            "Treat receipts as context, not automatic permission.",
            "WOM-kit still never deletes it for you.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_human_artifact_store_contract_separates_surface_from_system_records(self) -> None:
        text = HUMAN_ARTIFACT_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.13 contract baseline",
            "Raw data store",
            "Human artifact store",
            "System/AI artifact store",
            "The app name is never enough.",
            "| WordPress | projection surface |",
            "| Joplin | working note store / human artifact store |",
            "| Notion | workspace note / source export, depending on context |",
            "| Obsidian | local Markdown vault / working note store |",
            "Capture Action Shape",
            "human explicitly asks to capture a note/report/handoff",
            "system/AI artifact store records refs, source maps, receipts, and hashes",
            "automatically a manifest, source map, receipt, index entry, or trusted memory",
            "Write a separate local WOM receipt describing what changed.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_external_export_plan_keeps_large_media_export_text_first(self) -> None:
        text = EXTERNAL_EXPORT_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.66.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.66 read-only text-first external export planning checkpoint",
            "archive external-export-plan <archive-root>",
            "full_media_requested",
            "stop_and_split_media_before_export",
            "uploaded files, attachments, images, audio, or video",
            "writes no archive receipts",
            "echo provider URLs, local paths, filenames, account ids, emails, tokens, or",
            "does not implement provider export automation",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "External export plan",
            "archive external-export-plan --source notion|google_drive|generic_workspace --dry-run",
            "stop-and-split-media modes",
            "writes nothing, starts no provider export",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[External Export Plan](wom-kit/docs/external-export-plan.md)",
            "text-first external export planning before large media downloads",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "external-export-plan",
            "Plan a text-first Notion, Google Drive, or generic workspace export",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        for phrase in (
            "[External Export Plan](external-export-plan.md)",
            "v0.3.66 - External Export Plan",
            "starts no provider export",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    phrase in public_map_text
                    or phrase in public_map_ko_text
                    or phrase in release_text
                )

    def test_zet_surface_prototypes_point_to_shared_human_artifact_contract(self) -> None:
        text = ZET_SURFACE_PROTOTYPES_PATH.read_text(encoding="utf-8")
        for phrase in (
            "[Human Artifact Store Contract](human-artifact-store-contract.md)",
            "contract describes what a future",
            "adapter must prove before it can safely write",
            "Shared Contract Questions",
            "how the human-facing artifact links back to WOM object ids, zets, receipts",
            "which provider credentials, local paths, account data, and private URLs stay",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_notion_page_snapshot_model_keeps_snapshot_text_and_zet_layers_separate(self) -> None:
        text = NOTION_PAGE_SNAPSHOT_MODEL_PATH.read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.16 model baseline",
            "A provider page snapshot is a source/original objet.",
            "recordMap",
            "blocks",
            "It is not automatically:",
            "a derived text body",
            "Notion export / retrieval",
            "page snapshot JSON as source/original objet",
            "extracted readable block text as derived text",
            "human-reviewed note or conclusion as draft/minted zet",
            "archive prehashed-objet-ledger <archive-root>",
            "--store-kind notion_source_export",
            "--store-ref notion-export-20260614",
            "Do not treat raw page snapshot JSON as the derived text body.",
            "archive derive-text capture <archive-root>",
            "object_id  -> what bytes are being identified",
            "store_kind -> what storage family supplied the external ledger",
            "store_ref  -> which reviewed external store label contains those bytes",
            "must not be a raw local",
            "absolute path, private URL, account id, token, email address, or secret",
            "does not prove byte availability by itself",
            "None of those are implemented in v0.3.16",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_storage_and_provenance_docs_link_notion_snapshot_and_store_ref_policy(self) -> None:
        storage_text = SOURCE_OBJECT_STORAGE_POLICY_PATH.read_text(encoding="utf-8")
        provenance_text = TEXT_PROVENANCE_HIERARCHY_PATH.read_text(encoding="utf-8")
        notion_example_text = NOTION_THREE_STORE_EXAMPLE_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        expected_pairs = (
            (
                storage_text,
                (
                    "Store Ref Semantics",
                    "object_id  -> what bytes are being identified",
                    "store_ref  -> which reviewed external store label contains those bytes",
                    "Provider Page Snapshots",
                    "page snapshot JSON -> source/original objet",
                    "See `notion-page-snapshot-model.md`.",
                ),
            ),
            (
                provenance_text,
                (
                    "provider page snapshot JSON such as Notion `recordMap` / `blocks`",
                    "Notion recordMap/blocks JSON -> source/original objet",
                    "extracted block text -> derived text record",
                    "human summary/decision -> minted zet",
                ),
            ),
            (
                notion_example_text,
                (
                    "Page Snapshot JSON",
                    "recordMap / blocks JSON -> source/original objet",
                    "[Notion Page Snapshot Model](notion-page-snapshot-model.md)",
                ),
            ),
            (
                matrix_text,
                (
                    "Notion page snapshot model",
                    "No Notion API, provider sync, page-snapshot schema, extraction helper, or byte materialization adapter exists",
                ),
            ),
            (
                readme_text,
                (
                    "[Notion Page Snapshot Model](wom-kit/docs/notion-page-snapshot-model.md)",
                    "provider page/block snapshot JSON",
                ),
            ),
        )
        for doc_text, phrases in expected_pairs:
            for phrase in phrases:
                with self.subTest(phrase=phrase):
                    self.assertIn(phrase, doc_text)

    def test_objet_ref_resolution_doc_and_matrix_keep_read_only_boundaries(self) -> None:
        resolver_text = OBJET_REF_RESOLUTION_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.17 read-only baseline",
            "archive resolve-objet-ref <archive-root> --object-id sha256:<hex> --dry-run",
            "objects/manifests/files.jsonl",
            "Local candidates",
            "External candidates",
            "does not print local absolute paths",
            "does not hash the file",
            "again during resolution",
            "store_ref` remains a reviewed external",
            "call provider APIs",
            "create presigned URLs",
            "download objects",
            "prove remote availability",
            "decide whether local originals can be deleted",
            "None of those are implemented in v0.3.17",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, resolver_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "Objet ref resolver",
            "archive resolve-objet-ref --object-id sha256:<hex> --dry-run",
            "MCP `resolve_objet_ref`",
            "do not decide deletion safety",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Objet Ref Resolution](wom-kit/docs/objet-ref-resolution.md)",
            "read-only objet reference resolution",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Objet Ref Resolution](objet-ref-resolution.md)", public_map_text)

    def test_presigned_url_plan_doc_and_matrix_keep_read_only_boundaries(self) -> None:
        plan_text = PRESIGNED_URL_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.40 read-only planning baseline",
            "archive presigned-url-plan <archive-root>",
            "object-presigned-url-plan",
            "objet-presigned-url-plan",
            "MCP:",
            "presigned_url_plan",
            "objects/manifests/files.jsonl",
            "provider-bindings.yml",
            "current_capability.presigned_url_creation_implemented",
            "create presigned URLs",
            "call provider APIs",
            "retrieve credential values",
            "read object file bytes",
            "echo provider URLs",
            "echo local absolute paths",
            "echo exact credential refs",
            "future provider adapter, not implemented in v0.3.40",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, plan_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "Presigned URL plan",
            "archive presigned-url-plan --object-id sha256:<hex> --dry-run",
            "MCP `presigned_url_plan`",
            "create no presigned URLs",
            "retrieve no secrets",
            "keep live execution false",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Presigned URL Plan](wom-kit/docs/presigned-url-plan.md)",
            "presigned URL planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Presigned URL Plan](presigned-url-plan.md)", public_map_text)

    def test_zettel_objet_links_doc_and_matrix_keep_read_only_boundaries(self) -> None:
        links_text = ZETTEL_OBJET_LINKS_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.18 read-only preview",
            "archive zettel-objet-links <archive-root>",
            "MCP:",
            "zettel_objet_links",
            "sha256:<64 hex characters>",
            "objet:sha256:<64 hex characters>",
            "body text",
            "frontmatter values",
            "absolute local paths",
            "provider URLs",
            "presigned URLs",
            "Redacted zettels are blocked",
            "Provider-backed presigned URLs are separate future work",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, links_text)
        for phrase in (
            "Zettel objet link preview",
            "archive zettel-objet-links --path <zet.md>|--zettel-id <id> --dry-run",
            "MCP `zettel_objet_links`",
            "echo no zettel body text or frontmatter values",
            "block redacted zettels",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "[Zettel Objet Links](wom-kit/docs/zettel-objet-links.md)",
            "zettel objet link previews",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Zettel Objet Links](zettel-objet-links.md)", public_map_text)

    def test_derived_text_coverage_doc_and_matrix_expose_agent_contract(self) -> None:
        coverage_text = DERIVED_TEXT_COVERAGE_PATH.read_text(encoding="utf-8")
        derived_text = (KIT_ROOT / "docs" / "derived-text.md").read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.36 read-only coverage, toolchain doctor hints, and agent contract",
            "archive derive-text coverage",
            "archive derive-text-coverage",
            "archive derive-text toolchain",
            "archive derive-text-toolchain",
            "archive derive-text doctor",
            "archive derive-text-doctor",
            "--tool-hints local-tool-hints.json",
            "archive derive-text agent-contract",
            "maximum textual coverage is the default",
            "missing_derived_text",
            "needs_password_or_encrypted",
            "Toolchain Doctor",
            "derived-text-tool-hints/v0.1",
            "hint file path",
            "does not echo executable paths",
            "does not execute the hinted tool",
            "does not install tools",
            "python-docx",
            "openpyxl",
            "python-pptx",
            "LibreOffice command-line parameters",
            "Tesseract OCR documentation",
            "PyMuPDF documentation",
            "pyhwp converters",
            "They are coverage and routing gates.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, coverage_text)
        self.assertIn("[Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md)", derived_text)
        for phrase in (
            "Derived text coverage and toolchain",
            "archive derive-text coverage --dry-run",
            "archive derive-text-coverage --dry-run",
            "archive derive-text toolchain --extension <ext> --dry-run",
            "archive derive-text doctor --tool-hints <json> --dry-run",
            "archive derive-text-doctor --tool-hints <json> --dry-run",
            "archive derive-text agent-contract --dry-run",
            "maximum textual coverage is the default",
            "Tool hints let a user provide local executable paths",
            "read no source bytes",
            "echo no source filenames",
            "executable paths",
            "import paths",
            "write no derived text",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Derived Text Coverage And Toolchain](wom-kit/docs/derived-text-coverage-and-toolchain.md)",
            "derived-text coverage/toolchain/doctor/agent-contract",
            "tool-hint paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md)", public_map_text)
        self.assertIn("[Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md)", public_map_ko_text)

    def test_derived_text_completeness_signal_doc_and_matrix_prevent_full_mirror_overclaim(self) -> None:
        signal_text = DERIVED_TEXT_COMPLETENESS_SIGNAL_PATH.read_text(encoding="utf-8")
        coverage_text = DERIVED_TEXT_COVERAGE_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.59.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.59 read-only derived text completeness signal checkpoint",
            "archive derive-text coverage <archive-root> --dry-run --format json",
            "archive derive-text-coverage <archive-root> --dry-run --format json",
            "completeness_signal.scope_kind = manifest_scoped",
            "completeness_signal.full_mirror_claimed = false",
            "completeness_signal.full_mirror_proof_present = false",
            "external workspace was fully exported",
            "mailbox was fully mirrored",
            "cloud drive was fully mirrored",
            "human-reviewed mirror/export receipt",
            "reads no source file bodies",
            "scans no external workspaces",
            "calls no providers",
            "reads no secrets",
            "echoes no local absolute paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, signal_text)
        for phrase in (
            "v0.3.59 also returns `completeness_signal`",
            "manifest-scoped",
            "not proof that a Notion workspace",
            "folder was fully mirrored",
            "human-reviewed source/export mirror receipt",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, coverage_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "Derived text completeness signal",
            "`derive-text coverage` now returns `completeness_signal`",
            "manifest-scoped derived-text coverage",
            "full external workspace/mailbox/cloud-drive mirror completion",
            "does not claim full external account coverage",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Derived Text Completeness Signal](wom-kit/docs/derived-text-completeness-signal.md)",
            "manifest-scoped completeness signals",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("docs/derived-text-completeness-signal.md", kit_readme_text)
        self.assertIn("v0.3.59 - Derived Text Completeness Signal", release_text)
        self.assertIn("manifest-scoped completeness signal", release_text)
        self.assertIn("[Derived Text Completeness Signal](derived-text-completeness-signal.md)", public_map_text)
        self.assertIn("[Derived Text Completeness Signal](derived-text-completeness-signal.md)", public_map_ko_text)

    def test_imap_mailbox_source_doc_and_matrix_keep_read_only_boundaries(self) -> None:
        imap_text = IMAP_MAILBOX_SOURCE_PATH.read_text(encoding="utf-8")
        source_maps_text = (KIT_ROOT / "docs" / "source-maps.md").read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.19 read-only source planning baseline",
            "imap_mailbox",
            "archive.py imap-mailbox-plan",
            "imap_mailbox_plan",
            "gmail",
            "naver",
            "generic_imap",
            "imap.gmail.com",
            "imap.naver.com",
            "Credential Refs Only",
            "Do not pass real emails",
            "does not connect",
            "read no message headers",
            "read no message bodies",
            "read no attachments",
            "send no email",
            "delete no email",
            "change no message flags",
            "Actual mail reading remains future",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, imap_text)
        for phrase in (
            "imap_mailbox",
            "archive.py imap-mailbox-plan",
            "does not connect, login, read headers, read bodies",
            "imap_mailbox_plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, source_maps_text)
        for phrase in (
            "IMAP mailbox source plan",
            "archive imap-mailbox-plan --dry-run",
            "MCP `imap_mailbox_plan`",
            "`imap_mailbox` source",
            "scan-source` fails closed",
            "reads no headers, bodies, or attachments",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Source](wom-kit/docs/imap-mailbox-source.md)",
            "read-only IMAP mailbox source planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[IMAP Mailbox Source](imap-mailbox-source.md)", public_map_text)

    def test_imap_mailbox_operation_request_doc_and_matrix_keep_live_reads_closed(self) -> None:
        request_text = IMAP_MAILBOX_OPERATION_REQUEST_PATH.read_text(encoding="utf-8")
        imap_text = IMAP_MAILBOX_SOURCE_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.46 read-only request package baseline",
            "archive imap-mailbox-operation-request-plan <archive-root>",
            "imap-mailbox-request-plan",
            "mailbox-operation-request-plan",
            "imap_mailbox_operation_request_plan",
            "credential-policy-check",
            "mail_source_read",
            "header_metadata_scan",
            "ready_for_future_adapter_after_approval",
            "approval_receipt_verified",
            "does not echo",
            "open an IMAP connection",
            "read message headers",
            "read message bodies",
            "read attachments",
            "start OAuth",
            "not the adapter itself",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, request_text)
        for phrase in (
            "imap-mailbox-operation-request-plan",
            "imap_mailbox_operation_request_plan",
            "mail_source_read",
            "package the approval request",
            "privacy boundary",
            "summarize adapter readiness",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, imap_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP mailbox operation request plan",
            "archive imap-mailbox-operation-request-plan --dry-run",
            "MCP `imap_mailbox_operation_request_plan`",
            "needs_human_approval",
            "ready_for_future_adapter_after_approval",
            "open no IMAP connection",
            "echo no email addresses",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Operation Request Plan](wom-kit/docs/imap-mailbox-operation-request-plan.md)",
            "operation request packaging",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-source.md",
            "docs/imap-mailbox-operation-request-plan.md",
            "imap-mailbox-plan",
            "imap-mailbox-operation-request-plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[IMAP Mailbox Operation Request Plan](imap-mailbox-operation-request-plan.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Operation Request Plan](imap-mailbox-operation-request-plan.md)", public_map_ko_text)

    def test_imap_mailbox_adapter_readiness_doc_and_matrix_keep_live_reads_closed(self) -> None:
        readiness_text = IMAP_MAILBOX_ADAPTER_READINESS_PATH.read_text(encoding="utf-8")
        imap_text = IMAP_MAILBOX_SOURCE_PATH.read_text(encoding="utf-8")
        request_text = IMAP_MAILBOX_OPERATION_REQUEST_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.55 read-only adapter readiness plus manifest status baseline",
            "archive imap-mailbox-adapter-readiness-plan <archive-root>",
            "--adapter-id local-imap",
            "imap-mailbox-adapter-plan",
            "mailbox-adapter-readiness",
            "imap_mailbox_adapter_readiness_plan",
            "adapter_manifest_summary",
            "present_and_schema_valid",
            "imap-mailbox-adapter-manifest.schema.json",
            "imaplib",
            "email",
            "ready_for_request_package",
            "ready_for_future_adapter_after_approval",
            "does not echo",
            "open an IMAP connection",
            "read message headers",
            "read message bodies",
            "read attachments",
            "start OAuth",
            "not a mailbox adapter",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readiness_text)
        for phrase in (
            "imap-mailbox-adapter-readiness-plan",
            "imap_mailbox_adapter_readiness_plan",
            "local Python module",
            "opens no IMAP connection",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, imap_text)
        for phrase in (
            "imap-mailbox-adapter-readiness-plan",
            "imap_mailbox_adapter_readiness_plan",
            "future IMAP adapter, not implemented in v0.3.47",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, request_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP mailbox adapter readiness plan",
            "archive imap-mailbox-adapter-readiness-plan --adapter-id <id> --dry-run",
            "MCP `imap_mailbox_adapter_readiness_plan`",
            "adapter_manifest_summary.status",
            "present_and_schema_valid",
            "ready_for_request_package",
            "ready_for_future_adapter_after_approval",
            "open no IMAP connection",
            "echo no email addresses",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Adapter Readiness Plan](wom-kit/docs/imap-mailbox-adapter-readiness-plan.md)",
            "adapter readiness checks",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-adapter-readiness-plan.md",
            "imap-mailbox-adapter-readiness-plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[IMAP Mailbox Adapter Readiness Plan](imap-mailbox-adapter-readiness-plan.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Adapter Readiness Plan](imap-mailbox-adapter-readiness-plan.md)", public_map_ko_text)

    def test_imap_mailbox_selection_doc_and_matrix_keep_message_lists_closed(self) -> None:
        selection_text = IMAP_MAILBOX_SELECTION_PATH.read_text(encoding="utf-8")
        imap_text = IMAP_MAILBOX_SOURCE_PATH.read_text(encoding="utf-8")
        request_text = IMAP_MAILBOX_OPERATION_REQUEST_PATH.read_text(encoding="utf-8")
        readiness_text = IMAP_MAILBOX_ADAPTER_READINESS_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.49 read-only mailbox selection planning baseline",
            "archive imap-mailbox-selection-plan <archive-root>",
            "imap-mailbox-message-selection-plan",
            "mailbox-selection-plan",
            "imap_mailbox_selection_plan",
            "newest_first",
            "unread_first",
            "since_days_window",
            "human_review_queue",
            "needs_human_approval",
            "ready_for_future_adapter_after_approval",
            "does not echo",
            "select a mailbox",
            "search a mailbox",
            "list candidate messages",
            "read IMAP UIDs",
            "read Message-ID values",
            "read message headers",
            "not implemented in v0.3.50",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, selection_text)
        for phrase in (
            "imap-mailbox-selection-plan",
            "imap_mailbox_selection_plan",
            "message ids, subjects, senders",
            "does not implement reads, searches, message lists",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, imap_text)
        for phrase in (
            "imap-mailbox-selection-plan",
            "imap_mailbox_selection_plan",
            "future IMAP adapter, not implemented in v0.3.50",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, request_text)
        for phrase in (
            "imap-mailbox-selection-plan",
            "imap_mailbox_selection_plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readiness_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP mailbox selection plan",
            "archive imap-mailbox-selection-plan --dry-run",
            "MCP `imap_mailbox_selection_plan`",
            "search no mailbox",
            "list no candidate messages",
            "Message-ID values",
            "echo no email addresses",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Selection Plan](wom-kit/docs/imap-mailbox-selection-plan.md)",
            "mailbox selection planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "imap-mailbox-selection-plan",
            "docs/imap-mailbox-selection-plan.md",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[IMAP Mailbox Selection Plan](imap-mailbox-selection-plan.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Selection Plan](imap-mailbox-selection-plan.md)", public_map_ko_text)

    def test_imap_mailbox_adapter_audit_doc_and_matrix_keep_receipt_preview_safe(self) -> None:
        audit_text = IMAP_MAILBOX_ADAPTER_AUDIT_PATH.read_text(encoding="utf-8")
        imap_text = IMAP_MAILBOX_SOURCE_PATH.read_text(encoding="utf-8")
        request_text = IMAP_MAILBOX_OPERATION_REQUEST_PATH.read_text(encoding="utf-8")
        readiness_text = IMAP_MAILBOX_ADAPTER_READINESS_PATH.read_text(encoding="utf-8")
        selection_text = IMAP_MAILBOX_SELECTION_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.50 read-only IMAP adapter audit receipt preview baseline",
            "archive imap-mailbox-adapter-audit-plan <archive-root>",
            "imap-mailbox-adapter-audit",
            "mailbox-adapter-audit-plan",
            "imap_mailbox_adapter_audit_plan",
            "receipts/imap/adapter-audits/",
            "candidate count bucket",
            "does not write audit receipts",
            "It is an audit receipt preview, not an adapter runner.",
            "open an IMAP connection",
            "list candidate messages",
            "read IMAP UIDs",
            "read Message-ID values",
            "read message headers",
            "read message bodies",
            "read attachments",
            "not implemented in v0.3.50",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, audit_text)
        for phrase in (
            "imap-mailbox-adapter-audit-plan",
            "imap_mailbox_adapter_audit_plan",
            "non-secret receipt shape",
            "does not execute the adapter",
            "v0.3.56 can now",
            "receipt writes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, imap_text)
        for phrase in (
            "imap-mailbox-adapter-audit-plan",
            "imap_mailbox_adapter_audit_plan",
            "future IMAP adapter, not implemented in v0.3.50",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, request_text)
        for phrase in (
            "imap-mailbox-adapter-audit-plan",
            "imap_mailbox_adapter_audit_plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readiness_text)
                self.assertIn(phrase, selection_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP mailbox adapter audit plan",
            "archive imap-mailbox-adapter-audit-plan --adapter-id <id>",
            "MCP `imap_mailbox_adapter_audit_plan`",
            "write no audit receipts",
            "execute no live adapters",
            "search no mailbox",
            "list no candidate messages",
            "Message-ID values",
            "selection receipt paths",
            "echo no email addresses",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Adapter Audit Plan](wom-kit/docs/imap-mailbox-adapter-audit-plan.md)",
            "adapter audit receipt previews",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "imap-mailbox-adapter-audit-plan",
            "docs/imap-mailbox-adapter-audit-plan.md",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[IMAP Mailbox Adapter Audit Plan](imap-mailbox-adapter-audit-plan.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Adapter Audit Plan](imap-mailbox-adapter-audit-plan.md)", public_map_ko_text)

    def test_imap_mailbox_adapter_audit_write_doc_and_matrix_keep_mail_access_closed(self) -> None:
        audit_write_text = IMAP_MAILBOX_ADAPTER_AUDIT_WRITE_PATH.read_text(encoding="utf-8")
        imap_text = IMAP_MAILBOX_SOURCE_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.56 approval-gated local audit receipt write baseline",
            "archive imap-mailbox-adapter-audit-write <archive-root>",
            "mailbox-adapter-audit-write",
            "There is no MCP live write tool",
            "receipts/imap/adapter-audits/",
            "refuses replay",
            "open an IMAP connection",
            "read Message-ID values",
            "not permission to read mail",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, audit_write_text)
        for phrase in (
            "imap-mailbox-adapter-audit-write",
            "receipts/imap/adapter-audits/",
            "v0.3.56 can now",
            "write a reviewed non-secret audit receipt",
            "still does not implement reads, searches",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, imap_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP mailbox adapter audit write",
            "archive imap-mailbox-adapter-audit-write --adapter-id <id>",
            "alias `archive mailbox-adapter-audit-write`",
            "approval-gated write",
            "receipts/imap/adapter-audits/",
            "MCP has no live write tool",
            "blocks replay",
            "open no IMAP connection",
            "echoes no email addresses",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Adapter Audit Write](wom-kit/docs/imap-mailbox-adapter-audit-write.md)",
            "adapter audit receipt writes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-adapter-audit-write.md",
            "imap-mailbox-adapter-audit-write",
            "MCP exposes no live write tool",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[IMAP Mailbox Adapter Audit Write](imap-mailbox-adapter-audit-write.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Adapter Audit Write](imap-mailbox-adapter-audit-write.md)", public_map_ko_text)

    def test_imap_mailbox_adapter_manifest_doc_and_matrix_keep_manifest_preview_safe(self) -> None:
        manifest_text = IMAP_MAILBOX_ADAPTER_MANIFEST_PATH.read_text(encoding="utf-8")
        manifest_write_text = IMAP_MAILBOX_ADAPTER_MANIFEST_WRITE_PATH.read_text(encoding="utf-8")
        imap_text = IMAP_MAILBOX_SOURCE_PATH.read_text(encoding="utf-8")
        request_text = IMAP_MAILBOX_OPERATION_REQUEST_PATH.read_text(encoding="utf-8")
        readiness_text = IMAP_MAILBOX_ADAPTER_READINESS_PATH.read_text(encoding="utf-8")
        selection_text = IMAP_MAILBOX_SELECTION_PATH.read_text(encoding="utf-8")
        audit_text = IMAP_MAILBOX_ADAPTER_AUDIT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        schema_text = IMAP_MAILBOX_ADAPTER_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.55 read-only IMAP adapter manifest preview plus schema baseline",
            "archive imap-mailbox-adapter-manifest-plan <archive-root>",
            "imap-mailbox-adapter-manifest",
            "mailbox-adapter-manifest-plan",
            "imap_mailbox_adapter_manifest_plan",
            "imap-mailbox-adapter-manifest.schema.json",
            "config/imap-adapters/",
            "supported providers",
            "supported operations",
            "supported selection rules",
            "does not write IMAP adapter manifests",
            "It is a manifest preview, not a manifest writer or adapter runner.",
            "imap-mailbox-adapter-manifest-write",
            "open an IMAP connection",
            "list candidate messages",
            "read IMAP UIDs",
            "read Message-ID values",
            "not implemented in v0.3.55",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, manifest_text)
        for phrase in (
            "Status: v0.3.55 approval-gated local manifest write baseline",
            "archive imap-mailbox-adapter-manifest-write <archive-root>",
            "mailbox-adapter-manifest-write",
            "There is no MCP live write tool",
            "config/imap-adapters/<adapter-id>.imap-mailbox-adapter.json",
            "receipts/imap/adapter-manifests/<case-id>.imap-mailbox-adapter-manifest-write.json",
            "imap-mailbox-adapter-manifest.schema.json",
            "v0.3.55 can write a reviewed, non-secret local adapter manifest",
            "It still does not:",
            "open an IMAP connection",
            "read message headers",
            "retrieve credential values",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, manifest_write_text)
        for phrase in (
            "wom-kit/imap-mailbox-adapter-manifest/v0.1",
            "imap_mailbox_adapter_manifest",
            "supported_providers",
            "supported_operations",
            "privacy_contract",
            "message_headers_in_manifest",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, schema_text)
        for phrase in (
            "imap-mailbox-adapter-manifest-plan",
            "imap_mailbox_adapter_manifest_plan",
            "non-secret declaration",
            "imap-mailbox-adapter-manifest-write",
            "v0.3.56 can now",
            "write the reviewed non-secret manifest",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, imap_text)
        for phrase in (
            "imap-mailbox-adapter-manifest-plan",
            "imap_mailbox_adapter_manifest_plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, request_text)
                self.assertIn(phrase, readiness_text)
                self.assertIn(phrase, selection_text)
                self.assertIn(phrase, audit_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP mailbox adapter manifest plan",
            "IMAP mailbox adapter manifest write",
            "archive imap-mailbox-adapter-manifest-plan --adapter-id <id>",
            "archive imap-mailbox-adapter-manifest-write --adapter-id <id>",
            "MCP `imap_mailbox_adapter_manifest_plan`",
            "MCP has no live write tool",
            "imap-mailbox-adapter-manifest.schema.json",
            "write no adapter manifests",
            "writes one schema-validated non-secret IMAP adapter manifest",
            "execute no live adapters",
            "search no mailbox",
            "list no candidate messages",
            "Message-ID values",
            "selection receipt paths",
            "echo no email addresses",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Adapter Manifest Plan](wom-kit/docs/imap-mailbox-adapter-manifest-plan.md)",
            "[IMAP Mailbox Adapter Manifest Write](wom-kit/docs/imap-mailbox-adapter-manifest-write.md)",
            "adapter manifest previews",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "imap-mailbox-adapter-manifest-plan",
            "docs/imap-mailbox-adapter-manifest-plan.md",
            "imap-mailbox-adapter-manifest-write",
            "docs/imap-mailbox-adapter-manifest-write.md",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[IMAP Mailbox Adapter Manifest Plan](imap-mailbox-adapter-manifest-plan.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Adapter Manifest Plan](imap-mailbox-adapter-manifest-plan.md)", public_map_ko_text)
        self.assertIn("[IMAP Mailbox Adapter Manifest Write](imap-mailbox-adapter-manifest-write.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Adapter Manifest Write](imap-mailbox-adapter-manifest-write.md)", public_map_ko_text)

    def test_imap_mailbox_adapter_preflight_doc_and_matrix_keep_live_execution_closed(self) -> None:
        preflight_text = IMAP_MAILBOX_ADAPTER_PREFLIGHT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.55 read-only IMAP adapter preflight baseline",
            "archive imap-mailbox-adapter-preflight-plan <archive-root>",
            "imap-mailbox-adapter-execution-preflight",
            "mailbox-adapter-preflight",
            "imap_mailbox_adapter_preflight_plan",
            "present_and_schema_valid",
            "ready_for_future_adapter_after_approval",
            "approval receipt is supplied and verified",
            "open an IMAP connection",
            "read Message-ID values",
            "schema validation issue values",
            "not execution permission",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, preflight_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP mailbox adapter preflight plan",
            "archive imap-mailbox-adapter-preflight-plan --adapter-id <id> --dry-run",
            "MCP `imap_mailbox_adapter_preflight_plan`",
            "ready_for_future_adapter_after_approval",
            "approval receipt verification",
            "write nothing",
            "open no IMAP connection",
            "echo no email addresses",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Adapter Preflight Plan](wom-kit/docs/imap-mailbox-adapter-preflight-plan.md)",
            "adapter preflight checks",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-adapter-preflight-plan.md",
            "imap-mailbox-adapter-preflight-plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[IMAP Mailbox Adapter Preflight Plan](imap-mailbox-adapter-preflight-plan.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Adapter Preflight Plan](imap-mailbox-adapter-preflight-plan.md)", public_map_ko_text)

    def test_imap_mailbox_adapter_execution_contract_doc_and_matrix_keep_live_adapter_future(self) -> None:
        contract_text = IMAP_MAILBOX_ADAPTER_EXECUTION_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.61.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.61 read-only IMAP adapter execution contract baseline",
            "archive imap-mailbox-adapter-execution-contract <archive-root>",
            "imap-mailbox-adapter-execution-plan",
            "mailbox-adapter-execution-contract",
            "contract_ready_for_future_implementation",
            "ready_for_future_adapter_after_approval",
            "future_allowed_actions_after_implementation_and_approval",
            "mail_material_output_contract",
            "open an IMAP TLS connection",
            "read only the minimum header metadata",
            "performs none of them",
            "does not implement secret retrieval",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contract_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP mailbox adapter execution contract",
            "archive imap-mailbox-adapter-execution-contract --adapter-id <id> --dry-run",
            "contract_ready_for_future_implementation",
            "non-secret execution receipt shape",
            "opens no IMAP connection",
            "retrieves no secrets",
            "keeps live execution unimplemented",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Adapter Execution Contract](wom-kit/docs/imap-mailbox-adapter-execution-contract.md)",
            "adapter execution-contract planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-adapter-execution-contract.md",
            "imap-mailbox-adapter-execution-contract",
            "Print the read-only future execution contract",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("v0.3.61 - IMAP Adapter Execution Contract", release_text)
        self.assertIn("read-only execution contract", release_text)
        self.assertIn("[IMAP Mailbox Adapter Execution Contract](imap-mailbox-adapter-execution-contract.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Adapter Execution Contract](imap-mailbox-adapter-execution-contract.md)", public_map_ko_text)

    def test_imap_mailbox_header_metadata_scan_doc_and_matrix_keep_body_capture_closed(self) -> None:
        scan_text = IMAP_MAILBOX_HEADER_METADATA_SCAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.62.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.62 approval-gated local IMAP header metadata scan baseline",
            "archive imap-mailbox-header-metadata-scan <archive-root>",
            "imap-header-metadata-scan",
            "mailbox-header-metadata-scan",
            "app-password auth only",
            "`env:` username and app-password refs only",
            "`header_metadata_scan` only",
            "execution contract required",
            "open an IMAP TLS connection",
            "fetch limited header metadata",
            "Candidate refs are opaque hashes",
            "does not implement",
            "body capture",
            "attachment capture",
            "derived-text capture",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, scan_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP mailbox header metadata scan",
            "archive imap-mailbox-header-metadata-scan --dry-run|--approve",
            "first narrow live IMAP adapter path",
            "`env:` username/app-password refs",
            "fetch limited headers",
            "non-secret receipt with counts and opaque candidate refs",
            "returns no username/password values",
            "raw headers",
            "local absolute paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Header Metadata Scan](wom-kit/docs/imap-mailbox-header-metadata-scan.md)",
            "first approval-gated local IMAP header metadata scan",
            "broad IMAP ingestion beyond the first approval-gated header metadata scan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-header-metadata-scan.md",
            "imap-mailbox-header-metadata-scan",
            "Run the first approval-gated local IMAP header metadata scan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("v0.3.62 - IMAP Header Metadata Scan", release_text)
        self.assertIn("first narrow, approval-gated live IMAP adapter path", release_text)
        self.assertIn("[IMAP Mailbox Header Metadata Scan](imap-mailbox-header-metadata-scan.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Header Metadata Scan](imap-mailbox-header-metadata-scan.md)", public_map_ko_text)

    def test_imap_mailbox_header_scan_receipt_audit_doc_and_matrix_keep_mail_access_closed(self) -> None:
        audit_text = IMAP_MAILBOX_HEADER_SCAN_RECEIPT_AUDIT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.63.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.63 approval-gated IMAP header scan receipt audit",
            "archive imap-mailbox-header-scan-receipt-audit <archive-root>",
            "imap-header-scan-receipt-audit",
            "mailbox-header-scan-audit",
            "receipts/imap/adapter-execution-audits/",
            "does not connect to IMAP again",
            "does not include the original execution receipt path",
            "never:",
            "reads message bodies",
            "opens an OS keyring",
            "calls providers",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, audit_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP header scan receipt audit",
            "archive imap-mailbox-header-scan-receipt-audit --execution-receipt <path> --dry-run|--approve",
            "receipts/imap/adapter-execution-audits/*.json",
            "audits an existing non-secret IMAP header metadata scan execution receipt",
            "opens no IMAP connection",
            "echoes no execution receipt path",
            "candidate refs",
            "local absolute paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Header Scan Receipt Audit](wom-kit/docs/imap-mailbox-header-scan-receipt-audit.md)",
            "offline audit checkpoint for those header scan execution receipts",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-header-scan-receipt-audit.md",
            "imap-mailbox-header-scan-receipt-audit",
            "Audit one IMAP header metadata scan execution receipt",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("v0.3.63 - IMAP Header Scan Receipt Audit", release_text)
        self.assertIn("non-secret audit checkpoint", release_text)
        self.assertIn("[IMAP Mailbox Header Scan Receipt Audit](imap-mailbox-header-scan-receipt-audit.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Header Scan Receipt Audit](imap-mailbox-header-scan-receipt-audit.md)", public_map_ko_text)

    def test_imap_mailbox_material_selection_plan_doc_and_matrix_keep_message_material_closed(self) -> None:
        plan_text = IMAP_MAILBOX_MATERIAL_SELECTION_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.67.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.67 read-only IMAP material selection planning checkpoint",
            "archive imap-mailbox-material-selection-plan <archive-root>",
            "imap-material-selection-plan",
            "mailbox-material-selection-plan",
            "body_candidates",
            "attachment_candidates",
            "derived_text_candidates",
            "The candidate refs are validated but not echoed.",
            "It writes no review queue file in v0.3.67.",
            "reads message bodies",
            "reads attachment bytes",
            "writes queue files",
            "echoes execution receipt paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, plan_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP material selection plan",
            "archive imap-mailbox-material-selection-plan --execution-receipt <path>",
            "body_candidates|attachment_candidates|derived_text_candidates",
            "plans the next human material review lane",
            "writes no queue files",
            "reads no headers/bodies/attachments",
            "echoes no execution receipt path",
            "attachment names",
            "local absolute paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Material Selection Plan](wom-kit/docs/imap-mailbox-material-selection-plan.md)",
            "read-only material selection and capture request planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-material-selection-plan.md",
            "imap-mailbox-material-selection-plan",
            "Plan the next human message-material review lane",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("v0.3.67 - IMAP Material Selection Plan", release_text)
        self.assertIn("read-only planning checkpoint", release_text)
        self.assertIn("[IMAP Mailbox Material Selection Plan](imap-mailbox-material-selection-plan.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Material Selection Plan](imap-mailbox-material-selection-plan.md)", public_map_ko_text)

    def test_imap_mailbox_material_selection_record_doc_and_matrix_keep_candidate_refs_closed(self) -> None:
        record_text = IMAP_MAILBOX_MATERIAL_SELECTION_RECORD_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.68.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.68 approval-gated IMAP material selection record",
            "archive imap-mailbox-material-selection-record <archive-root>",
            "imap-material-selection-record",
            "mailbox-material-selection-record",
            "--selected-index 1",
            "--selected-index 3",
            "records a human-reviewed selection",
            "It does not include the original execution receipt path or the candidate refs.",
            "reads message bodies",
            "reads attachment bytes",
            "creates derived text",
            "echoes execution receipt paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, record_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP material selection record",
            "archive imap-mailbox-material-selection-record --execution-receipt <path>",
            "receipts/imap/material-selections/*.json",
            "records one-based candidate positions",
            "writes no candidate refs",
            "reads no headers/bodies/attachments",
            "echoes no execution receipt path",
            "attachment names",
            "local absolute paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Material Selection Record](wom-kit/docs/imap-mailbox-material-selection-record.md)",
            "approval-gated non-secret material selection records",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-material-selection-record.md",
            "imap-mailbox-material-selection-record",
            "Preview or approve writing one non-secret material selection receipt",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("v0.3.68 - IMAP Material Selection Record", release_text)
        self.assertIn("approval-gated IMAP material selection record", release_text)
        self.assertIn("[IMAP Mailbox Material Selection Record](imap-mailbox-material-selection-record.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Material Selection Record](imap-mailbox-material-selection-record.md)", public_map_ko_text)

    def test_imap_mailbox_material_capture_request_plan_doc_and_matrix_keep_material_reads_closed(self) -> None:
        request_text = IMAP_MAILBOX_MATERIAL_CAPTURE_REQUEST_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.69.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.69 read-only IMAP material capture request planning checkpoint",
            "archive imap-mailbox-material-capture-request-plan <archive-root>",
            "imap-material-capture-request-plan",
            "mailbox-material-capture-request-plan",
            "message_body_capture",
            "attachment_capture",
            "derived_text_capture",
            "It does not read the original IMAP header scan execution receipt.",
            "ready_for_future_material_capture_after_approval",
            "reads message bodies",
            "reads attachment bytes",
            "creates derived text",
            "writes files",
            "echoes material selection receipt paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, request_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "IMAP material capture request plan",
            "archive imap-mailbox-material-capture-request-plan --material-selection-receipt <path>",
            "ready_for_future_material_capture_after_approval",
            "reads no original execution receipt",
            "reads no headers/bodies/attachments",
            "creates no derived text",
            "echoes no material selection receipt path",
            "execution receipt path",
            "candidate refs",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[IMAP Mailbox Material Capture Request Plan](wom-kit/docs/imap-mailbox-material-capture-request-plan.md)",
            "read-only material selection and capture request planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-material-capture-request-plan.md",
            "imap-mailbox-material-capture-request-plan",
            "Plan a future body, attachment, or derived-text capture request",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("v0.3.69 - IMAP Material Capture Request Plan", release_text)
        self.assertIn("read-only IMAP material capture request planning checkpoint", release_text)
        self.assertIn("[IMAP Mailbox Material Capture Request Plan](imap-mailbox-material-capture-request-plan.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Material Capture Request Plan](imap-mailbox-material-capture-request-plan.md)", public_map_ko_text)

    def test_credential_store_contract_doc_and_matrix_keep_secret_boundaries(self) -> None:
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.20 read-only credential reference baseline",
            "archive.py credential-ref-plan",
            "credential_ref_plan",
            "env:NAME",
            "keyring:name",
            "secret:name",
            "wallet:name",
            "mail_app_password",
            "mail_oauth_token",
            "openai_api_key",
            "ocr_api_key",
            "Windows Credential Manager",
            "does not implement any read/write adapter",
            "does not store passwords",
            "read from any keyring",
            "read environment variables",
            "call OpenAI",
            "call OCR providers",
            "never appears in Git, zets, receipts, logs, source maps",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contract_text)
        for phrase in (
            "Credential ref plan",
            "archive credential-ref-plan --dry-run",
            "MCP `credential_ref_plan`",
            "OpenAI API keys",
            "OCR API keys",
            "read no environment variables",
            "open no OS keyring",
            "never echo raw keys",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential Store Contract](wom-kit/docs/credential-store-contract.md)",
            "read-only credential reference planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Store Contract](credential-store-contract.md)", public_map_text)

    def test_credential_ref_inventory_doc_and_matrix_keep_secret_boundaries(self) -> None:
        inventory_text = CREDENTIAL_REF_INVENTORY_PATH.read_text(encoding="utf-8")
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.21 read-only inventory baseline",
            "WOM should not become a plaintext password vault",
            "credential-ref-inventory",
            "credentials",
            "credential-status",
            "credential_ref_inventory",
            "profiles/local/credential-refs.local.yml",
            "does not echo the exact ref value",
            "Windows Credential Manager",
            "KeePassXC",
            "`account_ref` is not a secret",
            "read passwords",
            "read API keys",
            "open an OS keyring",
            "It is a catalog of refs, not a secret reader.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, inventory_text)
        for phrase in (
            "Credential Ref Inventory And Onboarding",
            "credential-ref-inventory",
            "profiles/local/credential-refs.local.yml",
            "does not echo the exact ref value",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contract_text)
        for phrase in (
            "Credential ref inventory",
            "archive credential-ref-inventory --dry-run",
            "MCP `credential_ref_inventory`",
            "credentials",
            "credential-status",
            "profiles/local/credential-refs.local.yml",
            "without echoing exact ref values or secrets",
            "reads no environment variables",
            "opens no OS keyring",
            "never prints passwords",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential Ref Inventory And Onboarding](wom-kit/docs/credential-ref-inventory-and-onboarding.md)",
            "read-only credential reference planning, inventory",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Ref Inventory And Onboarding](credential-ref-inventory-and-onboarding.md)", public_map_text)
        self.assertIn("[Credential Ref Inventory And Onboarding](credential-ref-inventory-and-onboarding.md)", public_map_ko_text)

    def test_credential_store_recommendations_doc_and_matrix_keep_broker_boundary(self) -> None:
        recommendation_text = CREDENTIAL_STORE_RECOMMENDATIONS_PATH.read_text(encoding="utf-8")
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        inventory_text = CREDENTIAL_REF_INVENTORY_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.22 read-only recommendation baseline",
            "credential-store-recommendation",
            "credential-store-plan",
            "secret-store-recommendation",
            "credential_store_recommendation",
            "personal_local_first",
            "browser_or_platform_password_manager",
            "automation_or_dev_secrets",
            "local_app_adapter",
            "Future Credential Access Broker",
            "The AI should not freely scrape browser databases",
            "human selects the file in a local UI",
            "tool writes to the chosen vault/keyring through an approved adapter",
            "It is a recommendation planner, not a secret broker.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, recommendation_text)
        for phrase in (
            "Credential Store Recommendations",
            "which external store class fits a human scenario",
            "opening a vault or reading any secret value",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contract_text)
        self.assertIn("[Credential Store Recommendations](credential-store-recommendations.md)", inventory_text)
        for phrase in (
            "Credential store recommendation",
            "archive credential-store-recommendation --scenario <scenario> --dry-run",
            "MCP `credential_store_recommendation`",
            "browser/platform password manager",
            "read no browser store",
            "future credential access broker boundaries",
            "without implementing secret retrieval",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential Store Recommendations](wom-kit/docs/credential-store-recommendations.md)",
            "external store recommendation",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Store Recommendations](credential-store-recommendations.md)", public_map_text)
        self.assertIn("[Credential Store Recommendations](credential-store-recommendations.md)", public_map_ko_text)

    def test_credential_vault_onboarding_doc_and_matrix_keep_vaults_closed(self) -> None:
        onboarding_text = CREDENTIAL_VAULT_ONBOARDING_PATH.read_text(encoding="utf-8")
        recommendation_text = CREDENTIAL_STORE_RECOMMENDATIONS_PATH.read_text(encoding="utf-8")
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.28 read-only vault onboarding planning baseline",
            "credential-vault-onboarding-plan",
            "credential-vault-onboarding",
            "secret-vault-onboarding-plan",
            "credential_vault_onboarding_plan",
            "recommended",
            "keepassxc",
            "browser_or_platform_password_manager",
            "os_keyring",
            "developer_secret_manager",
            "environment_variable",
            "WOM does not open those tools in v0.3.28.",
            "It is a vault onboarding planner, not a vault adapter.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, onboarding_text)
        self.assertIn("[Credential Vault Onboarding Plan](credential-vault-onboarding-plan.md)", recommendation_text)
        self.assertIn("[Credential Vault Onboarding Plan](credential-vault-onboarding-plan.md)", contract_text)
        for phrase in (
            "Credential vault onboarding plan",
            "archive credential-vault-onboarding-plan --scenario <scenario> --store-id recommended|keepassxc|bitwarden|1password|browser_or_platform_password_manager|os_keyring|developer_secret_manager|environment_variable --dry-run",
            "MCP `credential_vault_onboarding_plan`",
            "open no password manager",
            "read no keyring",
            "read no browser store",
            "return no secret values to AI",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential Vault Onboarding Plan](wom-kit/docs/credential-vault-onboarding-plan.md)",
            "vault onboarding planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Vault Onboarding Plan](credential-vault-onboarding-plan.md)", public_map_text)
        self.assertIn("[Credential Vault Onboarding Plan](credential-vault-onboarding-plan.md)", public_map_ko_text)

    def test_beginner_setup_manual_doc_and_matrix_bridge_recommendations_to_steps(self) -> None:
        manual_text = BEGINNER_SETUP_MANUAL_PATH.read_text(encoding="utf-8")
        onboarding_text = CREDENTIAL_VAULT_ONBOARDING_PATH.read_text(encoding="utf-8")
        derived_text = DERIVED_TEXT_COVERAGE_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.64 read-only beginner setup manual with object storage setup screens",
            "archive beginner-setup-manual",
            "first-use-setup-manual",
            "setup-manual",
            "first_secret_and_text_tools",
            "credential_vault",
            "credential_bulk_migration",
            "derived_text_tools",
            "object_storage_setup_manual",
            "CSV encoding: UTF-8",
            "Database > Merge from Database",
            "temporary database and working CSV copy",
            "Object Storage Setup Manual",
            "Cloudflare R2",
            "Bucket name: use the value returned by WOM",
            "Default storage class: Standard",
            "API token permission: Object Read & Write",
            "API token bucket scope: specific bucket only",
            "Cloudflare token restrictions",
            "what a vault is",
            "Do not paste passwords",
            "secret:keepassxc-openai-api",
            "derived-text-tool-hints/v0.1",
            "does not execute the tools",
            "It is a human setup guide and command checklist",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, manual_text)
        self.assertIn("credential-vault-onboarding-plan", manual_text)
        self.assertIn("derive-text-doctor", manual_text)
        self.assertIn("[Beginner Setup Manual](beginner-setup-manual.md)", public_map_text)
        self.assertIn("[Beginner Setup Manual](beginner-setup-manual.md)", public_map_ko_text)
        self.assertIn("[Beginner Setup Manual](wom-kit/docs/beginner-setup-manual.md)", readme_text)
        self.assertIn("Beginner setup manual", matrix_text)
        self.assertIn("archive beginner-setup-manual --topic first_secret_and_text_tools --dry-run", matrix_text)
        self.assertIn("--topic credential_bulk_migration", matrix_text)
        self.assertIn("--topic object_storage_setup_manual", matrix_text)
        self.assertIn("Cloudflare R2 bucket/API-token screen guidance", matrix_text)
        self.assertIn("creates no bucket or API token", matrix_text)
        self.assertIn("reads no CSV or vault", matrix_text)
        self.assertIn("Database > Merge from Database", matrix_text)
        self.assertIn("opens no password manager, keyring, provider dashboard", matrix_text)
        self.assertIn("installs no tools", matrix_text)
        self.assertIn("tool hint paths", matrix_text)
        self.assertIn("[Beginner Setup Manual](beginner-setup-manual.md)", onboarding_text)
        self.assertIn("Toolchain Doctor", derived_text)

    def test_connected_accounts_doc_and_matrix_bridge_account_metadata_without_secrets(self) -> None:
        connected_text = CONNECTED_ACCOUNTS_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.42 read-only connected accounts bridge",
            "archive connected-accounts",
            "accounts",
            "account-status",
            "provider-bindings.yml",
            "source-bindings.yml",
            "profiles/local/credential-refs.local.yml",
            "provider/source accounts",
            "It is an account map, not an account connector.",
            "does not show exact credential refs",
            "open IMAP connections",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, connected_text)
        for phrase in (
            "Connected accounts bridge",
            "archive connected-accounts --dry-run",
            "archive accounts --dry-run",
            "archive account-status --dry-run",
            "safe non-secret account labels",
            "open no IMAP connection",
            "echo no exact credential refs",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        self.assertIn("[Connected Accounts](connected-accounts.md)", public_map_text)
        self.assertIn("[Connected Accounts](connected-accounts.md)", public_map_ko_text)
        self.assertIn("[Connected Accounts](wom-kit/docs/connected-accounts.md)", readme_text)
        self.assertIn("connected accounts bridge", readme_text)
        self.assertIn("docs/connected-accounts.md", kit_readme_text)
        self.assertIn("connected-accounts", kit_readme_text)

    def test_object_storage_recommendations_doc_and_matrix_match_without_provider_calls(self) -> None:
        recommendation_text = OBJECT_STORAGE_RECOMMENDATIONS_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.64 read-only manifest-aware object storage recommendation matching with setup bridge",
            "archive object-storage-recommendation",
            "object-storage-match",
            "objet-storage-recommendation",
            "personal_low_ops",
            "backup_cost_sensitive",
            "google_cloud_native",
            "archive object-storage --dry-run",
            "recommended_setup_values.bucket_name",
            "Cloudflare R2 Setup Bridge",
            "next_exact_commands.object_storage_setup_manual",
            "next_exact_commands.object_storage_dry_run",
            "R2 public buckets",
            "It is a recommendation matcher, not a storage connector.",
            "does not:",
            "create API tokens",
            "create presigned URLs",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, recommendation_text)
        for phrase in (
            "Object storage recommendation",
            "archive object-storage-recommendation --scenario <scenario|auto_from_manifest> --dry-run",
            "archive object-storage-match --dry-run",
            "archive objet-storage-recommendation --dry-run",
            "surface the proposed bucket name",
            "Cloudflare R2 field guidance",
            "perform no live price lookup",
            "create no buckets or API tokens",
            "create no presigned URLs",
            "echo no provider URLs",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        self.assertIn("[Object Storage Recommendations](object-storage-recommendations.md)", public_map_text)
        self.assertIn("[Object Storage Recommendations](object-storage-recommendations.md)", public_map_ko_text)
        self.assertIn("[Object Storage Recommendations](wom-kit/docs/object-storage-recommendations.md)", readme_text)
        self.assertIn("object-storage recommendation matching", readme_text)
        self.assertIn("docs/object-storage-recommendations.md", kit_readme_text)
        self.assertIn("object-storage-recommendation", kit_readme_text)

    def test_object_storage_adapter_readiness_doc_and_matrix_keep_live_adapter_closed(self) -> None:
        readiness_text = OBJECT_STORAGE_ADAPTER_READINESS_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.41 read-only adapter readiness baseline",
            "archive object-storage-adapter-readiness-plan <archive-root>",
            "object-storage-adapter-plan",
            "objet-storage-adapter-readiness",
            "object_storage_adapter_readiness_plan",
            "provider-status",
            "setup-managed",
            "provider setup receipt paths",
            "credential policy check",
            "human approval receipt",
            "call provider APIs",
            "retrieve credential values",
            "create presigned URLs",
            "upload objects",
            "download objects",
            "read object bytes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readiness_text)
        for phrase in (
            "Status: v0.3.69 IMAP material capture request planning checkpoint",
            "Object storage adapter readiness plan",
            "archive object-storage-adapter-readiness-plan --operation presigned_download --dry-run",
            "MCP `object_storage_adapter_readiness_plan`",
            "call no providers",
            "retrieve no secrets",
            "create no presigned URLs",
            "echo no bucket names",
            "provider setup receipt paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Object Storage Adapter Readiness Plan](wom-kit/docs/object-storage-adapter-readiness-plan.md)",
            "adapter readiness planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Object Storage Adapter Readiness Plan](object-storage-adapter-readiness-plan.md)", public_map_text)
        self.assertIn("docs/object-storage-adapter-readiness-plan.md", kit_readme_text)

    def test_object_storage_operation_request_doc_and_matrix_keep_live_operation_closed(self) -> None:
        request_text = OBJECT_STORAGE_OPERATION_REQUEST_PATH.read_text(encoding="utf-8")
        readiness_text = OBJECT_STORAGE_ADAPTER_READINESS_PATH.read_text(encoding="utf-8")
        presigned_text = PRESIGNED_URL_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.45 read-only request package baseline",
            "archive object-storage-operation-request-plan <archive-root>",
            "object-storage-request-plan",
            "objet-storage-operation-request",
            "object_storage_operation_request_plan",
            "object-storage-adapter-readiness-plan",
            "presigned-url-plan",
            "resolve-objet-ref",
            "credential-policy-check",
            "needs_human_approval",
            "ready_for_future_adapter_after_approval",
            "live_execution_allowed_now",
            "approval_receipt_path_echoed",
            "call provider APIs",
            "retrieve credential values",
            "create presigned URLs",
            "upload objects",
            "download objects",
            "read object bytes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, request_text)
        self.assertIn("object-storage-operation-request-plan", readiness_text)
        self.assertIn("object-storage-operation-request-plan", presigned_text)
        for phrase in (
            "Object storage operation request plan",
            "archive object-storage-operation-request-plan --operation presigned_download --dry-run",
            "archive object-storage-request-plan",
            "MCP `object_storage_operation_request_plan`",
            "needs_human_approval",
            "ready_for_future_adapter_after_approval",
            "live execution remains false",
            "approval receipt paths",
            "retrieve no secrets",
            "create no presigned URLs",
            "echo no bucket names",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Object Storage Operation Request Plan](wom-kit/docs/object-storage-operation-request-plan.md)",
            "operation request packaging",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Object Storage Operation Request Plan](object-storage-operation-request-plan.md)", public_map_text)
        self.assertIn("docs/object-storage-operation-request-plan.md", kit_readme_text)

    def test_credential_plaintext_migration_doc_and_matrix_keep_secret_import_closed(self) -> None:
        migration_text = CREDENTIAL_PLAINTEXT_MIGRATION_PATH.read_text(encoding="utf-8")
        onboarding_text = CREDENTIAL_VAULT_ONBOARDING_PATH.read_text(encoding="utf-8")
        recommendation_text = CREDENTIAL_STORE_RECOMMENDATIONS_PATH.read_text(encoding="utf-8")
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.29 read-only plaintext secret migration planning baseline",
            "credential-plaintext-migration-plan",
            "secret-migration-plan",
            "credential-import-plan",
            "credential_plaintext_migration_plan",
            "source-label",
            "v0.3.29 does not accept or print the real local path",
            "It is a plaintext migration planner, not a migration executor.",
            "Broad\nsecret detection, keyring writes, cleanup, and deletion remain",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, migration_text)
        self.assertIn("[Credential Plaintext Migration Plan](credential-plaintext-migration-plan.md)", onboarding_text)
        self.assertIn("[Credential Plaintext Migration Plan](credential-plaintext-migration-plan.md)", recommendation_text)
        self.assertIn("[Credential Plaintext Migration Plan](credential-plaintext-migration-plan.md)", contract_text)
        for phrase in (
            "Credential plaintext migration plan",
            "archive credential-plaintext-migration-plan --source-label <safe-label> --credential-id <id> --target-store-id <store> --dry-run",
            "MCP `credential_plaintext_migration_plan`",
            "read no plaintext file",
            "print no plaintext file path",
            "delete no plaintext notes",
            "return no secret values to AI",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential Plaintext Migration Plan](wom-kit/docs/credential-plaintext-migration-plan.md)",
            "plaintext migration planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Plaintext Migration Plan](credential-plaintext-migration-plan.md)", public_map_text)
        self.assertIn("[Credential Plaintext Migration Plan](credential-plaintext-migration-plan.md)", public_map_ko_text)

    def test_credential_semantic_extraction_recipe_doc_and_matrix_split_complex_notes_first(self) -> None:
        semantic_text = CREDENTIAL_SEMANTIC_RECIPE_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.60.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.60 read-only semantic extraction recipe",
            "credential-semantic-extraction-recipe",
            "credential-extraction-recipe",
            "secret-semantic-extraction-recipe",
            "multi_account_same_service",
            "sso_or_passkey_route",
            "wallet_seed_or_private_key_material",
            "toggle_or_status_note",
            "does not read plaintext files",
            "does not detect secret values",
            "does not open password managers",
            "does not return secret values to AI",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, semantic_text)
        for phrase in (
            "Credential semantic extraction recipe",
            "archive credential-semantic-extraction-recipe --source-label <safe-label> --dry-run",
            "multi-account",
            "multi-secret",
            "SSO/passkey",
            "wallet/recovery",
            "returns no secret values to AI",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential Semantic Extraction Recipe](wom-kit/docs/credential-semantic-extraction-recipe.md)",
            "credential semantic extraction recipe",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/credential-semantic-extraction-recipe.md",
            "credential-semantic-extraction-recipe",
            "Print a read-only semantic recipe",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("v0.3.60 - Credential Semantic Extraction Recipe", release_text)
        self.assertIn("read-only semantic recipe", release_text)
        self.assertIn("[Credential Semantic Extraction Recipe](credential-semantic-extraction-recipe.md)", public_map_text)
        self.assertIn("[Credential Semantic Extraction Recipe](credential-semantic-extraction-recipe.md)", public_map_ko_text)

    def test_credential_access_broker_doc_and_matrix_keep_secret_values_out_of_ai(self) -> None:
        broker_text = CREDENTIAL_ACCESS_BROKER_PATH.read_text(encoding="utf-8")
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        recommendation_text = CREDENTIAL_STORE_RECOMMENDATIONS_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.23 read-only broker planning baseline",
            "credential-access-broker-plan",
            "credential-broker-plan",
            "secret-access-broker-plan",
            "credential_access_broker_plan",
            "The exact `credential_ref` value is not echoed back.",
            "mail_source_read",
            "model_api_call",
            "ocr_api_call",
            "object_storage_request",
            "cli_token_auth",
            "browser_login_fill",
            "plaintext_secret_migration",
            "human chooses a plaintext note through a local UI",
            "read a plaintext secret note",
            "It is a broker contract planner, not a broker adapter.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, broker_text)
        for phrase in (
            "Credential Access Broker Plan",
            "future approved secret use",
            "without implementing secret retrieval",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contract_text)
        self.assertIn("[Credential Access Broker Plan](credential-access-broker-plan.md)", recommendation_text)
        for phrase in (
            "Credential access broker plan",
            "archive credential-access-broker-plan --action-kind <action> --dry-run",
            "MCP `credential_access_broker_plan`",
            "plaintext secret migration planning",
            "read no plaintext secret note",
            "echo no exact credential ref values",
            "return no secret values to AI",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential Access Broker Plan](wom-kit/docs/credential-access-broker-plan.md)",
            "future access broker planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Access Broker Plan](credential-access-broker-plan.md)", public_map_text)
        self.assertIn("[Credential Access Broker Plan](credential-access-broker-plan.md)", public_map_ko_text)

    def test_credential_access_approval_doc_and_matrix_preview_no_live_approval(self) -> None:
        approval_text = CREDENTIAL_ACCESS_APPROVAL_PATH.read_text(encoding="utf-8")
        broker_text = CREDENTIAL_ACCESS_BROKER_PATH.read_text(encoding="utf-8")
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.31 credential approval receipt writer checkpoint",
            "credential-access-approval-plan",
            "credential-access-approval",
            "secret-access-approval-plan",
            "credential_access_approval_plan",
            "needs_review",
            "approve_once",
            "deny",
            "The exact `credential_ref` value is not echoed back.",
            "Use the local CLI for `--approve`.",
            "needs_review` remains",
            "writes one archive-internal JSON receipt",
            "grant live approval",
            "grant live adapter execution",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, approval_text)
        self.assertIn("[Credential Access Approval Plan](credential-access-approval-plan.md)", broker_text)
        for phrase in (
            "Credential Access Approval Plan",
            "human-reviewed, non-secret approval",
            "without granting live adapter access",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contract_text)
        for phrase in (
            "Credential access approval plan",
            "archive credential-access-approval-plan --decision approve_once|deny|needs_review --dry-run",
            "archive credential-access-approval --decision approve_once|deny --approve --reviewed-by <actor>",
            "MCP `credential_access_approval_plan`",
            "records one non-secret archive-internal receipt",
            "grants no live adapter access",
            "includes no secret values in the receipt",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential Access Approval Plan](wom-kit/docs/credential-access-approval-plan.md)",
            "local approval receipt preview/write",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Access Approval Plan](credential-access-approval-plan.md)", public_map_text)
        self.assertIn("[Credential Access Approval Plan](credential-access-approval-plan.md)", public_map_ko_text)

    def test_credential_policy_check_doc_and_matrix_gate_execution_without_running_adapters(self) -> None:
        policy_text = CREDENTIAL_POLICY_CHECK_PATH.read_text(encoding="utf-8")
        approval_text = CREDENTIAL_ACCESS_APPROVAL_PATH.read_text(encoding="utf-8")
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.32 credential policy gate plus KeePassXC preflight checkpoint",
            "credential-policy-check",
            "credential-access-policy-check",
            "secret-policy-check",
            "credential_policy_check",
            "ready_after_approval_receipt",
            "denied_by_policy",
            "live_execution_allowed_now",
            "--approval-receipt",
            "verify a written credential access approval receipt",
            "It is a policy gate, not a secret executor.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, policy_text)
        self.assertIn("[Credential Policy Check](credential-policy-check.md)", approval_text)
        self.assertIn("[Credential Policy Check](credential-policy-check.md)", contract_text)
        for phrase in (
            "Credential policy check",
            "archive credential-policy-check --action-kind <action> --approval-decision approve_once|deny|needs_review --adapter-kind <adapter> --operation <operation> --approval-receipt <path> --dry-run",
            "MCP `credential_policy_check`",
            "denied_by_policy",
            "run no live adapters",
            "live_execution_allowed_now` false",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential Policy Check](wom-kit/docs/credential-policy-check.md)",
            "credential policy checking",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Policy Check](credential-policy-check.md)", public_map_text)
        self.assertIn("[Credential Policy Check](credential-policy-check.md)", public_map_ko_text)

    def test_credential_keepassxc_command_plan_doc_and_matrix_require_verified_receipt(self) -> None:
        keepassxc_text = CREDENTIAL_KEEPASSXC_COMMAND_PATH.read_text(encoding="utf-8")
        approval_text = CREDENTIAL_ACCESS_APPROVAL_PATH.read_text(encoding="utf-8")
        policy_text = CREDENTIAL_POLICY_CHECK_PATH.read_text(encoding="utf-8")
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        recommendation_text = CREDENTIAL_STORE_RECOMMENDATIONS_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.32 read-only KeePassXC command preflight",
            "credential-keepassxc-command-plan",
            "keepassxc-command-plan",
            "credential-keepassxc-write-plan",
            "credential_keepassxc_command_plan",
            "--approval-receipt",
            "--entry-label",
            "--password-prompt",
            "approval_receipt is required",
            "run `keepassxc-cli`",
            "It is a command preflight, not a vault adapter.",
            "database_path_included",
            "secret_value_in_argv",
            "secret_value_in_stdin",
            "live_execution_allowed_now",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, keepassxc_text)
        self.assertIn("[Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md)", approval_text)
        self.assertIn("[Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md)", policy_text)
        self.assertIn("[Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md)", contract_text)
        self.assertIn("[Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md)", recommendation_text)
        for phrase in (
            "Credential KeePassXC command plan",
            "archive credential-keepassxc-command-plan --approval-receipt <path> --entry-label <safe-label> --dry-run",
            "MCP `credential_keepassxc_command_plan`",
            "verify a written approval receipt",
            "run no `keepassxc-cli`",
            "store no `.kdbx` paths",
            "place no secret values in argv",
            "command_execution_implemented` false",
            "live_execution_allowed_now` false",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential KeePassXC Command Plan](wom-kit/docs/credential-keepassxc-command-plan.md)",
            "KeePassXC command preflight",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md)", public_map_text)
        self.assertIn("[Credential KeePassXC Command Plan](credential-keepassxc-command-plan.md)", public_map_ko_text)

    def test_credential_keepassxc_write_doc_and_matrix_are_cli_only_and_non_secret(self) -> None:
        write_text = CREDENTIAL_KEEPASSXC_WRITE_PATH.read_text(encoding="utf-8")
        command_text = CREDENTIAL_KEEPASSXC_COMMAND_PATH.read_text(encoding="utf-8")
        approval_text = CREDENTIAL_ACCESS_APPROVAL_PATH.read_text(encoding="utf-8")
        policy_text = CREDENTIAL_POLICY_CHECK_PATH.read_text(encoding="utf-8")
        plaintext_text = CREDENTIAL_PLAINTEXT_MIGRATION_PATH.read_text(encoding="utf-8")
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        recommendation_text = CREDENTIAL_STORE_RECOMMENDATIONS_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.33 CLI-only KeePassXC write adapter",
            "credential-keepassxc-write",
            "keepassxc-write",
            "--approve",
            "--database-path",
            "keepassxc-cli add --password-prompt",
            "receipts/credentials/keepassxc-writes/",
            "There is no MCP live execution tool.",
            "mcp_live_tool_exposed: false",
            "database_path_included: false",
            "raw_adapter_output_echoed: false",
            "replay is blocked",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, write_text)
        for doc_text in (command_text, approval_text, policy_text, plaintext_text, contract_text, recommendation_text):
            self.assertIn("[Credential KeePassXC Write](credential-keepassxc-write.md)", doc_text)
        for phrase in (
            "Credential KeePassXC write",
            "local CLI adapter write",
            "archive credential-keepassxc-write --approval-receipt <path> --entry-label <safe-label> --database-path <local.kdbx> --approve",
            "MCP has no live write tool",
            "blocks replay",
            "echoes no secret values",
            "raw adapter output",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential KeePassXC Write](wom-kit/docs/credential-keepassxc-write.md)",
            "CLI-only KeePassXC write execution",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential KeePassXC Write](credential-keepassxc-write.md)", public_map_text)
        self.assertIn("[Credential KeePassXC Write](credential-keepassxc-write.md)", public_map_ko_text)

    def test_credential_adapter_readiness_doc_and_matrix_keep_live_adapters_closed(self) -> None:
        adapter_text = CREDENTIAL_ADAPTER_READINESS_PATH.read_text(encoding="utf-8")
        broker_text = CREDENTIAL_ACCESS_BROKER_PATH.read_text(encoding="utf-8")
        approval_text = CREDENTIAL_ACCESS_APPROVAL_PATH.read_text(encoding="utf-8")
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.25 read-only adapter readiness baseline",
            "credential-adapter-readiness-plan",
            "credential-adapter-plan",
            "secret-adapter-readiness",
            "credential_adapter_readiness_plan",
            "windows_credential_manager",
            "keepassxc_cli",
            "plaintext_secret_migration",
            "The exact `credential_ref` value is not echoed back.",
            "does not implement live adapter execution",
            "open Windows Credential Manager",
            "It is an adapter readiness preview, not a keyring reader",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, adapter_text)
        self.assertIn("[Credential Adapter Readiness Plan](credential-adapter-readiness-plan.md)", broker_text)
        self.assertIn("[Credential Adapter Readiness Plan](credential-adapter-readiness-plan.md)", approval_text)
        for phrase in (
            "Credential Adapter Readiness Plan",
            "future local adapter contract",
            "without opening a keyring",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contract_text)
        for phrase in (
            "Credential adapter readiness plan",
            "archive credential-adapter-readiness-plan --adapter-kind <adapter> --operation <operation> --dry-run",
            "MCP `credential_adapter_readiness_plan`",
            "require broker and approval boundaries",
            "write no adapter manifests or receipts",
            "retrieve or write no secret values",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential Adapter Readiness Plan](wom-kit/docs/credential-adapter-readiness-plan.md)",
            "adapter readiness planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Adapter Readiness Plan](credential-adapter-readiness-plan.md)", public_map_text)
        self.assertIn("[Credential Adapter Readiness Plan](credential-adapter-readiness-plan.md)", public_map_ko_text)

    def test_credential_adapter_manifest_doc_schema_and_matrix_are_non_secret_preview(self) -> None:
        manifest_text = CREDENTIAL_ADAPTER_MANIFEST_PATH.read_text(encoding="utf-8")
        readiness_text = CREDENTIAL_ADAPTER_READINESS_PATH.read_text(encoding="utf-8")
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        schema_text = CREDENTIAL_ADAPTER_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.26 read-only adapter manifest preview baseline",
            "credential-adapter-manifest-plan",
            "credential-adapter-manifest",
            "secret-adapter-manifest-plan",
            "credential_adapter_manifest_plan",
            "credential-adapter-manifest.schema.json",
            "config/credential-adapters/<adapter-id>.credential-adapter.json",
            "must not contain",
            "does not write adapter manifests",
            "It is a manifest preview and schema baseline",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, manifest_text)
        for phrase in (
            "wom-kit/credential-adapter-manifest/v0.1",
            "credential_adapter_manifest",
            "adapter_kind",
            "supported_operations",
            "privacy_contract",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, schema_text)
        self.assertIn("[Credential Adapter Manifest Plan](credential-adapter-manifest-plan.md)", readiness_text)
        self.assertIn("[Credential Adapter Manifest Plan](credential-adapter-manifest-plan.md)", contract_text)
        for phrase in (
            "Credential adapter manifest plan",
            "archive credential-adapter-manifest-plan --adapter-id <id> --adapter-kind <adapter> --dry-run",
            "MCP `credential_adapter_manifest_plan`",
            "credential-adapter-manifest.schema.json",
            "write no adapter manifests",
            "include no secret values",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential Adapter Manifest Plan](wom-kit/docs/credential-adapter-manifest-plan.md)",
            "adapter manifest preview",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Adapter Manifest Plan](credential-adapter-manifest-plan.md)", public_map_text)
        self.assertIn("[Credential Adapter Manifest Plan](credential-adapter-manifest-plan.md)", public_map_ko_text)

    def test_credential_adapter_audit_doc_and_matrix_keep_live_execution_closed(self) -> None:
        audit_text = CREDENTIAL_ADAPTER_AUDIT_PATH.read_text(encoding="utf-8")
        manifest_text = CREDENTIAL_ADAPTER_MANIFEST_PATH.read_text(encoding="utf-8")
        contract_text = CREDENTIAL_STORE_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.27 read-only adapter audit receipt preview baseline",
            "credential-adapter-audit-plan",
            "credential-adapter-audit",
            "secret-adapter-audit-plan",
            "credential_adapter_audit_plan",
            "receipts/credentials/adapter-audits/<case-id>.credential-adapter-audit.json",
            "must not contain",
            "does not write audit receipts",
            "It is an audit receipt preview, not an adapter runner.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, audit_text)
        self.assertIn("[Credential Adapter Audit Plan](credential-adapter-audit-plan.md)", manifest_text)
        self.assertIn("[Credential Adapter Audit Plan](credential-adapter-audit-plan.md)", contract_text)
        for phrase in (
            "Credential adapter audit plan",
            "archive credential-adapter-audit-plan --adapter-id <id> --adapter-kind <adapter> --operation <operation> --result-status not_run|succeeded|failed|denied --dry-run",
            "MCP `credential_adapter_audit_plan`",
            "write no audit receipts",
            "execute no live adapters",
            "include no secret values",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.69 pre-release",
            "[Credential Adapter Audit Plan](wom-kit/docs/credential-adapter-audit-plan.md)",
            "adapter audit receipt preview",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Adapter Audit Plan](credential-adapter-audit-plan.md)", public_map_text)
        self.assertIn("[Credential Adapter Audit Plan](credential-adapter-audit-plan.md)", public_map_ko_text)

    def test_v02x_freeze_boundary_doc_covers_public_proof_and_non_goals(self) -> None:
        text = FREEZE_DOC_PATH.read_text(encoding="utf-8")
        for phrase in (
            "v0.2.x built the safe local ground.",
            "one narrow receiver-side, approval-gated write",
            "attestation/review record + receipt",
            "replay-gated",
            "human-approved",
            "local-first",
            "body-safe",
            "InfraBlockchain / COOV-style",
            "private personal data stays local/off-chain/on-device",
            "hashes",
            "receipt references",
            "delegation/share proof references",
            "attestation proof references",
            "revocation pointers",
            "DID-compatible identity may be future research",
            "does not implement DID",
            "system token",
            "public proof anchoring",
            "real ZET transport",
            "automatic feed update",
            "trust graph mutation",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
