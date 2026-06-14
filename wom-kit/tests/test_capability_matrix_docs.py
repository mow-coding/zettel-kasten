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
            "opaque `item-0001` style refs",
            "archive project-intake-session-guide",
            "archive project-intake-record-answer",
            "archive project-intake-status",
            "archive source-intake-record",
            "archive objet-capture-selection",
            "archive objet-capture",
            "archive staged-cleanup-check",
            "does not echo the answer text",
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
