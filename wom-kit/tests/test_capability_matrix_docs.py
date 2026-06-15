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
CREDENTIAL_PLAINTEXT_MIGRATION_PATH = KIT_ROOT / "docs" / "credential-plaintext-migration-plan.md"
DERIVED_TEXT_COVERAGE_PATH = KIT_ROOT / "docs" / "derived-text-coverage-and-toolchain.md"
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
ZET_SURFACE_PROTOTYPES_PATH = KIT_ROOT / "docs" / "zet-surface-prototypes.md"
IMAP_MAILBOX_SOURCE_PATH = KIT_ROOT / "docs" / "imap-mailbox-source.md"
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
            "Credential plaintext migration plan",
            "Credential access broker plan",
            "Credential access approval plan",
            "Credential policy check",
            "Credential adapter readiness plan",
            "Credential adapter manifest plan",
            "Credential adapter audit plan",
            "IMAP mailbox source plan",
            "Notion page snapshot model",
            "Objet ref resolver",
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
            "Status: v0.3.34 derived-text coverage checkpoint",
            "Objet ref resolver",
            "archive resolve-objet-ref --object-id sha256:<hex> --dry-run",
            "MCP `resolve_objet_ref`",
            "do not decide deletion safety",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.34 pre-release",
            "[Objet Ref Resolution](wom-kit/docs/objet-ref-resolution.md)",
            "read-only objet reference resolution",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Objet Ref Resolution](objet-ref-resolution.md)", public_map_text)

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
            "Status: v0.3.34 read-only coverage gate and agent contract",
            "archive derive-text coverage",
            "archive derive-text-coverage",
            "archive derive-text toolchain",
            "archive derive-text-toolchain",
            "archive derive-text agent-contract",
            "maximum textual coverage is the default",
            "missing_derived_text",
            "needs_password_or_encrypted",
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
            "archive derive-text agent-contract --dry-run",
            "maximum textual coverage is the default",
            "read no source bytes",
            "echo no source filenames",
            "write no derived text",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.34 pre-release",
            "[Derived Text Coverage And Toolchain](wom-kit/docs/derived-text-coverage-and-toolchain.md)",
            "derived-text coverage/toolchain/agent-contract",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md)", public_map_text)
        self.assertIn("[Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md)", public_map_ko_text)

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
            "v0.3.34 pre-release",
            "[IMAP Mailbox Source](wom-kit/docs/imap-mailbox-source.md)",
            "read-only IMAP mailbox source planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[IMAP Mailbox Source](imap-mailbox-source.md)", public_map_text)

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
            "v0.3.34 pre-release",
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
            "v0.3.34 pre-release",
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
            "v0.3.34 pre-release",
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
            "v0.3.34 pre-release",
            "[Credential Vault Onboarding Plan](wom-kit/docs/credential-vault-onboarding-plan.md)",
            "vault onboarding planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Vault Onboarding Plan](credential-vault-onboarding-plan.md)", public_map_text)
        self.assertIn("[Credential Vault Onboarding Plan](credential-vault-onboarding-plan.md)", public_map_ko_text)

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
            "v0.3.34 pre-release",
            "[Credential Plaintext Migration Plan](wom-kit/docs/credential-plaintext-migration-plan.md)",
            "plaintext migration planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Credential Plaintext Migration Plan](credential-plaintext-migration-plan.md)", public_map_text)
        self.assertIn("[Credential Plaintext Migration Plan](credential-plaintext-migration-plan.md)", public_map_ko_text)

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
            "v0.3.34 pre-release",
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
            "v0.3.34 pre-release",
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
            "v0.3.34 pre-release",
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
            "v0.3.34 pre-release",
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
            "v0.3.34 pre-release",
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
            "v0.3.34 pre-release",
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
            "v0.3.34 pre-release",
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
            "v0.3.34 pre-release",
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
