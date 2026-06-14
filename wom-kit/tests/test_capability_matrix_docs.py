from __future__ import annotations

import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent
MATRIX_PATH = KIT_ROOT / "docs" / "capability-matrix.md"
FREEZE_DOC_PATH = KIT_ROOT / "docs" / "v02x-freeze-v03-entry-boundary.md"
PROJECT_INTAKE_COOKBOOK_PATH = KIT_ROOT / "docs" / "project-intake-cookbook.md"
HUMAN_ARTIFACT_STORE_CONTRACT_PATH = KIT_ROOT / "docs" / "human-artifact-store-contract.md"
ZET_SURFACE_PROTOTYPES_PATH = KIT_ROOT / "docs" / "zet-surface-prototypes.md"
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
            "Status: v0.3.18 zettel objet link preview checkpoint",
            "Objet ref resolver",
            "archive resolve-objet-ref --object-id sha256:<hex> --dry-run",
            "MCP `resolve_objet_ref`",
            "do not decide deletion safety",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.18 pre-release",
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
