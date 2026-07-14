from __future__ import annotations

import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent
MATRIX_PATH = KIT_ROOT / "docs" / "capability-matrix.md"
PRODUCT_ROADMAP_PATH = KIT_ROOT / "docs" / "product-roadmap.md"
BASE_TYPES_PATH = KIT_ROOT / "zettel-kasten" / "types.yml"
FAKE_ARCHIVE_TYPES_PATH = KIT_ROOT / "examples" / "fake-life-archive" / "zettel-kasten" / "types.yml"
FREEZE_DOC_PATH = KIT_ROOT / "docs" / "v02x-freeze-v03-entry-boundary.md"
PROJECT_INTAKE_COOKBOOK_PATH = KIT_ROOT / "docs" / "project-intake-cookbook.md"
CREDENTIAL_STORE_CONTRACT_PATH = KIT_ROOT / "docs" / "credential-store-contract.md"
CREDENTIAL_REF_INVENTORY_PATH = KIT_ROOT / "docs" / "credential-ref-inventory-and-onboarding.md"
CREDENTIAL_STORE_RECOMMENDATIONS_PATH = KIT_ROOT / "docs" / "credential-store-recommendations.md"
CREDENTIAL_VAULT_ONBOARDING_PATH = KIT_ROOT / "docs" / "credential-vault-onboarding-plan.md"
BEGINNER_SETUP_MANUAL_PATH = KIT_ROOT / "docs" / "beginner-setup-manual.md"
PHASE_2_QUICKSTART_PATH = KIT_ROOT / "docs" / "phase-2-quickstart.md"
CONNECTED_ACCOUNTS_PATH = KIT_ROOT / "docs" / "connected-accounts.md"
CREDENTIAL_SEMANTIC_RECIPE_PATH = KIT_ROOT / "docs" / "credential-semantic-extraction-recipe.md"
CREDENTIAL_PLAINTEXT_MIGRATION_PATH = KIT_ROOT / "docs" / "credential-plaintext-migration-plan.md"
OBJECT_STORAGE_RECOMMENDATIONS_PATH = KIT_ROOT / "docs" / "object-storage-recommendations.md"
OBJECT_STORAGE_ADAPTER_READINESS_PATH = KIT_ROOT / "docs" / "object-storage-adapter-readiness-plan.md"
OBJECT_STORAGE_OPERATION_REQUEST_PATH = KIT_ROOT / "docs" / "object-storage-operation-request-plan.md"
OBJECT_STORAGE_ADAPTER_EXECUTION_CONTRACT_PATH = KIT_ROOT / "docs" / "object-storage-adapter-execution-contract.md"
OBJECT_STORAGE_UPLOAD_EVIDENCE_PATH = KIT_ROOT / "docs" / "object-storage-upload-evidence.md"
OBJECT_STORAGE_UPLOAD_EVIDENCE_AUDIT_PATH = KIT_ROOT / "docs" / "object-storage-upload-evidence-audit.md"
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
EXTERNAL_IMPORTS_PATH = KIT_ROOT / "docs" / "external-imports.md"
CONNECTION_IMPORT_PLAN_PATH = KIT_ROOT / "docs" / "connection-import-plan.md"
CONNECTION_EVIDENCE_PARSER_CONTRACT_PATH = KIT_ROOT / "docs" / "connection-evidence-parser-contract.md"
CONNECTION_EVIDENCE_FIXTURE_PARSER_PATH = KIT_ROOT / "docs" / "connection-evidence-fixture-parser.md"
CONNECTION_EDGE_INTELLIGENCE_PATH = KIT_ROOT / "docs" / "connection-edge-intelligence-plan.md"
NOTION_NESTED_TREE_PLAN_PATH = KIT_ROOT / "docs" / "notion-nested-tree-plan.md"
NOTION_ANCESTOR_CRAWL_PLAN_PATH = KIT_ROOT / "docs" / "notion-ancestor-crawl-plan.md"
NOTION_ANCESTOR_FETCH_ADAPTER_EXECUTION_CONTRACT_PATH = KIT_ROOT / "docs" / "notion-ancestor-fetch-adapter-execution-contract.md"
NOTION_ANCESTOR_FETCH_ADAPTER_RUN_PATH = KIT_ROOT / "docs" / "notion-ancestor-fetch-adapter-run.md"
NOTION_CONNECTION_PLAN_PATH = KIT_ROOT / "docs" / "notion-connection-plan.md"
NOTION_OAUTH_CONNECTION_PREFLIGHT_PATH = KIT_ROOT / "docs" / "notion-oauth-connection-preflight.md"
NOTION_RECOVER_PATH = KIT_ROOT / "docs" / "notion-recover.md"
NOTION_MEDIA_FETCH_ADAPTER_EXECUTION_CONTRACT_PATH = KIT_ROOT / "docs" / "notion-media-fetch-adapter-execution-contract.md"
NOTION_MEDIA_RESULT_VERIFICATION_PLAN_PATH = KIT_ROOT / "docs" / "notion-media-result-verification-plan.md"
NOTION_BLOCK_MIRROR_TREE_FIXTURE_PLAN_PATH = KIT_ROOT / "docs" / "notion-block-mirror-tree-fixture-plan.md"
NOTION_ANCESTOR_MERGE_PLAN_PATH = KIT_ROOT / "docs" / "notion-ancestor-merge-plan.md"
NOTION_CLIENT_ISSUE_VERIFICATION_PLAN_PATH = KIT_ROOT / "docs" / "notion-client-issue-verification-plan.md"
NOTION_CLIENT_FIXTURE_REQUEST_PLAN_PATH = KIT_ROOT / "docs" / "notion-client-fixture-request-plan.md"
TIRO_IMPORT_PLAN_PATH = KIT_ROOT / "docs" / "tiro-import-plan.md"
TIRO_LOSSLESS_RECOVERY_PATH = KIT_ROOT / "docs" / "tiro-lossless-recovery.md"
ZET_MARKDOWN_STYLE_GUIDE_PATH = KIT_ROOT / "docs" / "zet-markdown-style-guide.md"
ZETTEL_EDGE_WRITE_PATH = KIT_ROOT / "docs" / "zettel-edge-write.md"
ZETTEL_EDGE_BATCH_PATH = KIT_ROOT / "docs" / "zettel-edge-batch.md"
ZET_SURFACE_PROTOTYPES_PATH = KIT_ROOT / "docs" / "zet-surface-prototypes.md"
ZET_PROJECTION_PLAN_PATH = KIT_ROOT / "docs" / "zet-projection-plan-preview.md"
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
IMAP_MAILBOX_MATERIAL_CAPTURE_EXECUTION_CONTRACT_PATH = KIT_ROOT / "docs" / "imap-mailbox-material-capture-execution-contract.md"
IMAP_MAILBOX_MATERIAL_CAPTURE_APPROVAL_PATH = KIT_ROOT / "docs" / "imap-mailbox-material-capture-approval-plan.md"
IMAP_MAILBOX_MATERIAL_CAPTURE_APPROVAL_AUDIT_PATH = KIT_ROOT / "docs" / "imap-mailbox-material-capture-approval-audit.md"
VERSION_TRUTH_SOURCE_PATH = KIT_ROOT / "docs" / "version-truth-source.md"
RUNTIME_CANONICAL_ENTRYPOINTS_PATH = KIT_ROOT / "docs" / "runtime-canonical-entrypoints.md"
OPERATIONAL_CONTEXT_PATH = KIT_ROOT / "docs" / "operational-context.md"
NOTION_PAGE_SNAPSHOT_MODEL_PATH = KIT_ROOT / "docs" / "notion-page-snapshot-model.md"
OBJET_REF_RESOLUTION_PATH = KIT_ROOT / "docs" / "objet-ref-resolution.md"
ZETTEL_OBJET_LINKS_PATH = KIT_ROOT / "docs" / "zettel-objet-links.md"
NOTION_OBJET_LINK_PLAN_PATH = KIT_ROOT / "docs" / "notion-objet-link-plan.md"
NOTION_OBJET_LINK_INDEX_PATH = KIT_ROOT / "docs" / "notion-objet-link-index.md"
NOTION_OBJET_LINK_REWRITE_PLAN_PATH = KIT_ROOT / "docs" / "notion-objet-link-rewrite-plan.md"
NOTION_OBJET_LINK_CONVERT_PATH = KIT_ROOT / "docs" / "notion-objet-link-convert.md"
NOTION_OBJET_MANIFEST_LOCATOR_LABEL_PATH = KIT_ROOT / "docs" / "notion-objet-manifest-locator-label.md"
NOTION_OBJET_IMPORT_CLUE_AUDIT_PATH = KIT_ROOT / "docs" / "notion-objet-import-clue-audit.md"
NOTION_OBJET_SOURCE_MAP_LINK_PLAN_PATH = KIT_ROOT / "docs" / "notion-objet-source-map-link-plan.md"
VIEW_HEALTH_PATH = KIT_ROOT / "docs" / "view-health.md"
VIEW_RECOMMENDATION_PLAN_PATH = KIT_ROOT / "docs" / "view-recommendation-plan.md"
INDEX_HEALTH_PATH = KIT_ROOT / "docs" / "index-health.md"
SOURCE_OBJECT_STORAGE_POLICY_PATH = KIT_ROOT / "docs" / "source-object-storage-policy.md"
TEXT_PROVENANCE_HIERARCHY_PATH = KIT_ROOT / "docs" / "text-provenance-hierarchy.md"
AI_RESPONSE_CONCEPT_GUIDE_PATH = KIT_ROOT / "docs" / "ai-response-concept-guide.md"
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
            "Archive identity reconcile",
            "AI response concept guide",
            "AI usage observability",
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
            "Object storage adapter execution contract",
            "Object storage upload evidence",
            "Object storage upload evidence audit",
            "Object storage upload adapter (Stage 2)",
            "Credential plaintext migration plan",
            "Credential access broker plan",
            "Credential access approval plan",
            "Credential policy check",
            "Credential adapter readiness plan",
            "Credential adapter manifest plan",
            "Credential adapter audit plan",
            "External export plan",
            "External import",
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
            "Connection edge intelligence plan",
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

    def test_archive_identity_reconcile_public_contract_is_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        guide_text = (KIT_ROOT / "docs" / "archive-identity-reconcile.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.226.md").read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        versioning_text = (REPO_ROOT / "VERSIONING.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        for phrase in (
            "archive.yml principal",
            "identity-reconcile <archive-root> --dry-run",
            "proposed `archive-identity.yml` SHA-256",
            "stores no display-name or identity value",
            "Forced process or machine termination",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide_text)
        for text in (matrix_text, release_text, upgrade_text):
            with self.subTest(document="release-surface"):
                self.assertIn("identity-reconcile", text)
                self.assertIn("proposed", text)
                self.assertIn("SHA-256", text)
        self.assertIn("v0.3.240 pre-release", versioning_text)
        self.assertIn("0.3.240", versioning_text)
        self.assertIn("archive-identity-reconcile.md", public_map_text)

    def test_aggregate_edge_progress_public_contract_is_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        progress_text = (KIT_ROOT / "docs" / "large-command-progress-and-output.md").read_text(
            encoding="utf-8"
        )
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.227.md").read_text(
            encoding="utf-8"
        )
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-12-v03227-aggregate-edge-progress.md"
        ).read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        benchmark_text = (KIT_ROOT / "tools" / "benchmark_doctor_progress_volume.py").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "Status: v0.3.227 aggregate full-Doctor edge progress checkpoint",
            "Version: v0.3.240, release candidate",
            "cumulative source/candidate/cache-hit counts",
            "does not perform another broad pass",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (progress_text, release_text, decision_text, upgrade_text):
            with self.subTest(document="progress-contract"):
                self.assertIn("edge-receipt-source-load-detail", text)
                self.assertIn("cache_hits", text)
                self.assertIn("10-second", text)
        for phrase in (
            "source-count",
            "index-receipt-count",
            "timing_claim_boundary",
            "real_archive_read",
            "private_values_emitted",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, benchmark_text)
        self.assertIn("v0.3.240 (current checkpoint)", readme_text)
        self.assertIn("v0.3.240 (현재 checkpoint)", readme_ko_text)

    def test_actionable_full_doctor_results_and_current_profile_progress_are_documented(
        self,
    ) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        runtime_text = (
            KIT_ROOT / "docs" / "runtime-context-quick-and-full-inspection.md"
        ).read_text(encoding="utf-8")
        progress_text = (
            KIT_ROOT / "docs" / "large-command-progress-and-output.md"
        ).read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.228.md").read_text(
            encoding="utf-8"
        )
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-13-v03228-actionable-full-doctor-results.md"
        ).read_text(encoding="utf-8")
        benchmark_text = (
            KIT_ROOT / "tools" / "benchmark_local_profile_secret_safety.py"
        ).read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.228 actionable full-Doctor result and current-stage progress checkpoint",
            "Version: v0.3.240, release candidate",
            "doctor_findings",
            "up to 100 detailed items",
            "up to 20 deduplicated suggested commands",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (runtime_text, release_text, decision_text):
            with self.subTest(document="finding-contract"):
                self.assertIn("doctor_findings", text)
                self.assertIn("ERROR/WARN", text)
                self.assertIn("cannot truthfully reconstruct", text)
        for text in (matrix_text, progress_text, release_text, decision_text):
            with self.subTest(document="current-stage-progress"):
                self.assertIn("checked_files", text)
                self.assertIn("content_scanned", text)
                self.assertIn("local_profiles", text)
                self.assertIn("skipped_dirs", text)
        for phrase in (
            "real_archive_read",
            "persistent_files_written",
            "file_count",
            "elapsed_seconds",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, benchmark_text)

    def test_executable_bom_reconcile_guidance_is_documented_and_fail_closed(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        reconcile_text = (KIT_ROOT / "docs" / "mint-receipt-reconcile.md").read_text(
            encoding="utf-8"
        )
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.229.md").read_text(
            encoding="utf-8"
        )
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-13-v03229-executable-bom-reconcile-command.md"
        ).read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        cli_text = (KIT_ROOT / "src" / "wom_kit" / "archive_cli.py").read_text(
            encoding="utf-8"
        )
        bom_start = cli_text.index('if self._zettel_has_bom_cached(target_path):')
        bom_end = cli_text.index(
            'receipt_progress("checking target mint receipt link")', bom_start
        )
        bom_block = cli_text[bom_start:bom_end]

        for phrase in (
            "Status: v0.3.229 executable BOM reconcile guidance checkpoint",
            "Version: v0.3.240, release candidate",
            "actual validated canonical frontmatter id",
            "omits the command when the id is absent or unsafe",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (reconcile_text, release_text, decision_text, upgrade_text):
            with self.subTest(document="bom-guidance"):
                self.assertIn("--diagnostic-only", text)
                self.assertIn("format_drift", text)
                self.assertIn("content_change", text)
                self.assertIn("retire-draft-reconcile", text)
        self.assertIn('target_data.get("id")', bom_block)
        self.assertIn("valid_draft_zettel_id(target_zettel_id)", bom_block)
        self.assertIn('f"--zettel-id {target_zettel_id} "', bom_block)
        self.assertNotIn("--zettel-id <id>", bom_block)

    def test_digest_bound_content_change_review_is_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        reconcile_text = (KIT_ROOT / "docs" / "mint-receipt-reconcile.md").read_text(
            encoding="utf-8"
        )
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.230.md").read_text(
            encoding="utf-8"
        )
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-13-v03230-digest-bound-content-change-review.md"
        ).read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")

        for phrase in (
            "Status: v0.3.230 digest-bound content-change review checkpoint",
            "Version: v0.3.240, release candidate",
            "Previous checkpoint: Status: v0.3.229",
            "--reviewed-plan-sha256 <sha256>",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (reconcile_text, release_text, decision_text, upgrade_text, upgrade_ko_text):
            with self.subTest(document="review-contract"):
                self.assertIn("human_review_plan", text)
                self.assertIn("review_plan_sha256", text)
                self.assertIn("intentional_change", text)
                self.assertIn("unintentional_change", text)
                self.assertIn("uncertain", text)
        self.assertIn("v0.3.240 pre-release", readme_text)
        self.assertIn("v0.3.240 pre-release", readme_ko_text)
        self.assertIn("v0.3.240 (current checkpoint)", readme_text)
        self.assertIn("v0.3.240 (현재 checkpoint)", readme_ko_text)

    def test_first_read_readiness_gate_is_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        guide_text = (KIT_ROOT / "docs" / "first-read-readiness.md").read_text(
            encoding="utf-8"
        )
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.231.md").read_text(
            encoding="utf-8"
        )
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-14-v03231-first-read-readiness.md"
        ).read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        runtime_skill_text = (
            KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"
        ).read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "Status: v0.3.231 first-read readiness checkpoint",
            "Version: v0.3.240, release candidate",
            "First-read readiness gate",
            "explicit abstract",
            "uniquely resolvable safe id",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (guide_text, release_text, decision_text, upgrade_text, runtime_skill_text):
            with self.subTest(document="first-read-readiness"):
                self.assertIn("first-read-readiness", text)
                self.assertIn("zet-catalog-pass", text)
                self.assertIn("does not", text.lower())
        self.assertIn("first-read-readiness.md", public_map_text)

    def test_explicit_abstract_publication_gate_is_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        guide_text = (KIT_ROOT / "docs" / "explicit-abstract-publication.md").read_text(
            encoding="utf-8"
        )
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.232.md").read_text(
            encoding="utf-8"
        )
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-14-v03232-explicit-abstract-publication.md"
        ).read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        runtime_skill_text = (
            KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"
        ).read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "Status: v0.3.232 explicit abstract publication checkpoint",
            "Version: v0.3.240, release candidate",
            "Explicit abstract publication invariant",
            "compatibility fields",
            "full draft SHA-256 and abstract SHA-256",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (
            guide_text,
            release_text,
            decision_text,
            upgrade_text,
            upgrade_ko_text,
            runtime_skill_text,
        ):
            with self.subTest(document="explicit-abstract-publication"):
                self.assertIn("first_read_check", text)
                self.assertIn("abstract", text)
        self.assertIn("explicit-abstract-publication.md", public_map_text)

    def test_abstract_freshness_evidence_is_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        guide_text = (KIT_ROOT / "docs" / "abstract-freshness.md").read_text(
            encoding="utf-8"
        )
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.233.md").read_text(
            encoding="utf-8"
        )
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-14-v03233-abstract-freshness.md"
        ).read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        runtime_text = (KIT_ROOT / "docs" / "runtime-canonical-entrypoints.md").read_text(
            encoding="utf-8"
        )
        runtime_skill_text = (
            KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"
        ).read_text(encoding="utf-8")
        agent_template_texts = [
            (KIT_ROOT / "templates" / archive_type / "AGENTS.md").read_text(
                encoding="utf-8"
            )
            for archive_type in ("personal", "company", "family")
        ]
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(
            encoding="utf-8"
        )
        public_map_ko_text = (
            KIT_ROOT / "docs" / "public-documentation-map.ko.md"
        ).read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")

        for phrase in (
            "Previous checkpoint: Status: v0.3.233 abstract freshness evidence checkpoint",
            "Version: v0.3.240, release candidate",
            "Abstract freshness evidence",
            "O(canonical_zets + evidence_candidate_receipts + receipt_items)",
            "semantic truth",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (
            guide_text,
            release_text,
            decision_text,
            upgrade_text,
            upgrade_ko_text,
            runtime_text,
            runtime_skill_text,
        ):
            with self.subTest(document="abstract-freshness"):
                self.assertIn("abstract-freshness", text)
                self.assertIn("unverified", text)
        combined_text = "\n".join(
            (
                guide_text,
                release_text,
                decision_text,
                upgrade_text,
                upgrade_ko_text,
                runtime_text,
                runtime_skill_text,
            )
        )
        self.assertTrue(
            "human review" in combined_text.lower() or "사람 검토" in combined_text
        )
        for text in agent_template_texts:
            with self.subTest(document="archive-agent-template"):
                self.assertIn("abstract-freshness", text)
                self.assertIn("never permission to auto-rewrite", text)
        self.assertIn("abstract-freshness.md", public_map_text)
        self.assertIn("abstract-freshness.md", public_map_ko_text)
        self.assertIn("the Memento Problem", readme_text)
        self.assertIn("메멘토 문제", readme_ko_text)

    def test_scalable_first_read_diagnostics_and_three_zet_pilot_are_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        first_read_text = (KIT_ROOT / "docs" / "first-read-readiness.md").read_text(
            encoding="utf-8"
        )
        freshness_text = (KIT_ROOT / "docs" / "abstract-freshness.md").read_text(
            encoding="utf-8"
        )
        pilot_text = (KIT_ROOT / "docs" / "abstract-backfill-pilot.md").read_text(
            encoding="utf-8"
        )
        pilot_ko_text = (
            KIT_ROOT / "docs" / "abstract-backfill-pilot.ko.md"
        ).read_text(encoding="utf-8")
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-14-v03240-scalable-first-read-diagnostics.md"
        ).read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.240.md").read_text(
            encoding="utf-8"
        )
        public_map_text = (
            KIT_ROOT / "docs" / "public-documentation-map.md"
        ).read_text(encoding="utf-8")
        public_map_ko_text = (
            KIT_ROOT / "docs" / "public-documentation-map.ko.md"
        ).read_text(encoding="utf-8")

        for phrase in (
            "Version: v0.3.240, release candidate",
            "result schema v0.2",
            "evidence_candidate_receipts",
            "no whole receipt-tree enumeration",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (first_read_text, release_text, decision_text):
            self.assertIn("readiness_met", text)
            self.assertIn("diagnostic", text.lower())
        for text in (freshness_text, release_text, decision_text):
            self.assertIn("stage=1/2", text)
            self.assertIn("persistent cache", text.lower())
        for text in (pilot_text, pilot_ko_text):
            self.assertIn("--max-items 3", text)
            self.assertIn("zet-abstract-backfill-write", text)
            self.assertIn("zet-abstract-backfill-receipt-audit", text)
        self.assertIn("abstract-backfill-pilot.md", public_map_text)
        self.assertIn("abstract-backfill-pilot.ko.md", public_map_ko_text)

    def test_canonical_zet_revision_plan_is_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        guide_text = (KIT_ROOT / "docs" / "zet-revision-plan.md").read_text(
            encoding="utf-8"
        )
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.234.md").read_text(
            encoding="utf-8"
        )
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-14-v03234-canonical-revision-plan.md"
        ).read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(
            encoding="utf-8"
        )
        public_map_ko_text = (
            KIT_ROOT / "docs" / "public-documentation-map.ko.md"
        ).read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")

        for phrase in (
            "Status: v0.3.234 canonical zet revision plan checkpoint",
            "Version: v0.3.240, release candidate",
            "Canonical zet revision plan",
            ".wom-scratch/revisions/",
            "plan_digest",
            "separate CLI writer dry-run",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (
            guide_text,
            release_text,
            decision_text,
            upgrade_text,
            upgrade_ko_text,
            readme_text,
            readme_ko_text,
            kit_readme_text,
        ):
            with self.subTest(document="canonical-revision-plan"):
                self.assertIn("zet-revision-plan", text)
                self.assertIn(".wom-scratch/revisions/", text)
        combined = "\n".join((guide_text, release_text, decision_text, upgrade_text))
        for phrase in (
            "remint-reconcile",
            "writes no zet",
            "no actual zet id",
            "not truth",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), combined.lower())
        self.assertIn("approved_write_implemented", guide_text)
        self.assertIn("zet-revision-plan.md", public_map_text)
        self.assertIn("zet-revision-plan.md", public_map_ko_text)

    def test_canonical_zet_revision_write_is_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        guide_text = (KIT_ROOT / "docs" / "zet-revision-write.md").read_text(
            encoding="utf-8"
        )
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.235.md").read_text(
            encoding="utf-8"
        )
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-14-v03235-canonical-revision-write.md"
        ).read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(
            encoding="utf-8"
        )
        public_map_ko_text = (
            KIT_ROOT / "docs" / "public-documentation-map.ko.md"
        ).read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        schema_text = (
            KIT_ROOT / "schemas" / "zet-revision-receipt.schema.json"
        ).read_text(encoding="utf-8")
        guide_compact = " ".join(guide_text.split())

        for phrase in (
            "Status: v0.3.235 canonical zet revision write checkpoint",
            "Version: v0.3.240, release candidate",
            "Canonical zet revision write",
            "approval-gated local CLI write",
            "MCP exposes no writer",
            "Distinct plans for one canonical zet serialize through that lock",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (
            guide_text,
            release_text,
            decision_text,
            upgrade_text,
            upgrade_ko_text,
            readme_text,
            readme_ko_text,
            kit_readme_text,
        ):
            with self.subTest(document="canonical-revision-write"):
                self.assertIn("zet-revision-write", text)
        for phrase in (
            "write_plan.actual_digest",
            "--affirm-abstract-body-pair-reviewed",
            "--affirm-edge-changes-reviewed",
            "receipts/revisions/canonical/",
            "process is interrupted",
            "no revision write tool",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), guide_compact.lower())
        self.assertIn("CLI-only `zet-revision-write`", decision_text)
        self.assertIn("write-ahead lock", decision_text)
        self.assertIn("wom-kit/zet-revision-receipt/v0.1", schema_text)
        self.assertIn("zet-revision-write.md", public_map_text)
        self.assertIn("zet-revision-write.md", public_map_ko_text)

    def test_canonical_zet_revision_receipt_audit_is_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        guide_text = (
            KIT_ROOT / "docs" / "zet-revision-receipt-audit.md"
        ).read_text(encoding="utf-8")
        release_text = (
            KIT_ROOT / "docs" / "releases" / "v0.3.236.md"
        ).read_text(encoding="utf-8")
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-14-v03236-canonical-revision-audit.md"
        ).read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(
            encoding="utf-8"
        )
        public_map_text = (
            KIT_ROOT / "docs" / "public-documentation-map.md"
        ).read_text(encoding="utf-8")
        public_map_ko_text = (
            KIT_ROOT / "docs" / "public-documentation-map.ko.md"
        ).read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        runtime_skill_text = (
            KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"
        ).read_text(encoding="utf-8")
        entrypoint_text = (
            KIT_ROOT / "docs" / "runtime-canonical-entrypoints.md"
        ).read_text(encoding="utf-8")
        status_board_text = (
            KIT_ROOT / "docs" / "archive-status-board.md"
        ).read_text(encoding="utf-8")
        guide_compact = " ".join(guide_text.split())

        for phrase in (
            "Status: v0.3.236 canonical zet revision receipt and lock audit checkpoint",
            "Version: v0.3.240, release candidate",
            "Canonical zet revision receipt audit",
            "implemented local read-only CLI",
            "O(receipt_files log receipt_files + revision_chains + lock_files)",
            "malformed non-hash digest values",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "ordinary-and-restore chronological revision event-chain audit in v0.3.239",
            "recoverable_missing_receipt",
            "A -> B -> A",
            "never deletes a lock",
            "old content can be recreated from hashes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide_compact)
        for text in (
            release_text,
            decision_text,
            upgrade_text,
            upgrade_ko_text,
            readme_text,
            readme_ko_text,
            kit_readme_text,
            runtime_skill_text,
            entrypoint_text,
            status_board_text,
        ):
            with self.subTest(document="canonical-revision-audit"):
                self.assertIn("zet-revision-receipt-audit", text)
        self.assertIn("CLI-only, read-only `zet-revision-receipt-audit`", decision_text)
        self.assertIn("zet-revision-receipt-audit.md", public_map_text)
        self.assertIn("zet-revision-receipt-audit.md", public_map_ko_text)

    def test_canonical_zet_revision_restore_plan_is_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        guide_text = (
            KIT_ROOT / "docs" / "zet-revision-restore-plan.md"
        ).read_text(encoding="utf-8")
        release_text = (
            KIT_ROOT / "docs" / "releases" / "v0.3.237.md"
        ).read_text(encoding="utf-8")
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-14-v03237-canonical-revision-restore-plan.md"
        ).read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(
            encoding="utf-8"
        )
        public_map_text = (
            KIT_ROOT / "docs" / "public-documentation-map.md"
        ).read_text(encoding="utf-8")
        public_map_ko_text = (
            KIT_ROOT / "docs" / "public-documentation-map.ko.md"
        ).read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        runtime_skill_text = (
            KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"
        ).read_text(encoding="utf-8")
        entrypoint_text = (
            KIT_ROOT / "docs" / "runtime-canonical-entrypoints.md"
        ).read_text(encoding="utf-8")
        status_board_text = (
            KIT_ROOT / "docs" / "archive-status-board.md"
        ).read_text(encoding="utf-8")
        restore_guide_compact = " ".join(guide_text.split())

        for phrase in (
            "Status: v0.3.237 canonical zet revision restore plan checkpoint",
            "Version: v0.3.240, release candidate",
            "Canonical zet revision restore plan",
            "separately recovered full-zet bytes",
            "before a separate reviewed writer; no MCP duplicate",
            "ready_for_human_review",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "latest-event-bound recovered-full-zet restore planning in v0.3.239",
            "never tries to reconstruct text from a hash",
            "archive-wide `zet-revision-receipt-audit` to be healthy",
            "current publication policy",
            "Since v0.3.239, pass the exact plan evidence",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, restore_guide_compact)
        for text in (
            release_text,
            decision_text,
            upgrade_text,
            upgrade_ko_text,
            readme_text,
            readme_ko_text,
            kit_readme_text,
            runtime_skill_text,
            entrypoint_text,
            status_board_text,
        ):
            with self.subTest(document="canonical-revision-restore-plan"):
                self.assertIn("zet-revision-restore-plan", text)
        self.assertIn("Add CLI-only, read-only `zet-revision-restore-plan`", decision_text)
        self.assertIn("zet-revision-restore-plan.md", public_map_text)
        self.assertIn("zet-revision-restore-plan.md", public_map_ko_text)

    def test_canonical_zet_exact_byte_restore_write_is_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        guide_text = (
            KIT_ROOT / "docs" / "zet-revision-restore-write.md"
        ).read_text(encoding="utf-8")
        schema_text = (
            KIT_ROOT
            / "schemas"
            / "zet-revision-restore-receipt.schema.json"
        ).read_text(encoding="utf-8")
        release_text = (
            KIT_ROOT / "docs" / "releases" / "v0.3.239.md"
        ).read_text(encoding="utf-8")
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-14-v03239-exact-byte-restore-write.md"
        ).read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(
            encoding="utf-8"
        )
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(
            encoding="utf-8"
        )
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        runtime_skill_text = (
            KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"
        ).read_text(encoding="utf-8")
        entrypoint_text = (
            KIT_ROOT / "docs" / "runtime-canonical-entrypoints.md"
        ).read_text(encoding="utf-8")
        public_map_text = (
            KIT_ROOT / "docs" / "public-documentation-map.md"
        ).read_text(encoding="utf-8")
        public_map_ko_text = (
            KIT_ROOT / "docs" / "public-documentation-map.ko.md"
        ).read_text(encoding="utf-8")
        guide_compact = " ".join(guide_text.split())

        for phrase in (
            "Status: v0.3.239 approved exact-byte canonical restore checkpoint",
            "Version: v0.3.240, release candidate",
            "Canonical zet exact-byte restore write",
            "implemented approval-gated local CLI",
            "writes the recovered proposal bytes exactly",
            "MCP exposes no restore writer",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "approval-gated exact-byte canonical restore in v0.3.239",
            "does not recreate missing words from hashes",
            "recovered historical `updated_at`",
            "resume when the canonical zet still has its prewrite bytes",
            "calls no model, provider, object store, database, credential store, or network",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide_compact)
        for text in (
            release_text,
            decision_text,
            upgrade_text,
            upgrade_ko_text,
            readme_text,
            readme_ko_text,
            kit_readme_text,
            runtime_skill_text,
            entrypoint_text,
        ):
            with self.subTest(document="canonical-exact-restore-write"):
                self.assertIn("zet-revision-restore-write", text)
        self.assertIn("zet_revision_restore_write", schema_text)
        self.assertIn("zet-revision-restore-write.md", public_map_text)
        self.assertIn("zet-revision-restore-write.md", public_map_ko_text)

    def test_chronological_revision_event_chain_is_documented(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        audit_text = (
            KIT_ROOT / "docs" / "zet-revision-receipt-audit.md"
        ).read_text(encoding="utf-8")
        restore_text = (
            KIT_ROOT / "docs" / "zet-revision-restore-plan.md"
        ).read_text(encoding="utf-8")
        release_text = (
            KIT_ROOT / "docs" / "releases" / "v0.3.238.md"
        ).read_text(encoding="utf-8")
        decision_text = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-14-v03238-revision-event-chain.md"
        ).read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(
            encoding="utf-8"
        )
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(
            encoding="utf-8"
        )
        runtime_skill_text = (
            KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"
        ).read_text(encoding="utf-8")
        audit_compact = " ".join(audit_text.split())
        restore_compact = " ".join(restore_text.split())

        for phrase in (
            "Status: v0.3.238 chronological revision event-chain checkpoint",
            "Version: v0.3.240, release candidate",
            "orders each identity's events by unique normalized timestamp",
            "A -> B -> A",
            "O(receipt_files log receipt_files + revision_chains + lock_files)",
            "actual newest chronological event",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "ordinary-and-restore chronological revision event-chain audit in v0.3.239",
            "orders each group by event time",
            "branch/replay transition",
            "not the latest event",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, audit_compact)
        for phrase in (
            "actual newest event",
            "after-state bytes happen to match again",
            "actual event-chain tip",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, restore_compact)
        for text in (
            release_text,
            decision_text,
            upgrade_text,
            upgrade_ko_text,
            readme_text,
            readme_ko_text,
            runtime_skill_text,
        ):
            with self.subTest(document="chronological-revision-event-chain"):
                self.assertIn("A -> B -> A", text)

    def test_external_import_docs_explain_source_ref_preservation_boundary(self) -> None:
        imports_text = EXTERNAL_IMPORTS_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        root_readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.105.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "source_refs, when the manifest supplies explicit safe object refs",
            "Source Ref Preservation",
            "object_id",
            "objet_ref",
            "source_ref_count",
            "source_refs_preserved",
            "does not treat the imported text body hash as an object ref",
            "calls no providers",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, imports_text)
        for phrase in (
            "External import",
            "archive import-external <archive-root> --source notion|google_drive --export <folder-or-manifest> --dry-run|--approve --reviewed-by <actor>",
            "source_ref_count",
            "source_refs_preserved",
            "does not call Notion or Google Drive APIs",
            "MCP exposes read-only `external_import_plan` only",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "explicit safe object refs",
            "source_refs",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
                self.assertIn(phrase, root_readme_text)
        for phrase in (
            "# v0.3.105 - External Import Source Ref Preservation",
            "does not treat the imported text body hash as a source object id",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)

    def test_projection_plan_docs_surface_supported_values_and_notion_boundary(self) -> None:
        text = ZET_PROJECTION_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.94.md").read_text(encoding="utf-8")
        for phrase in (
            "v0.3.94 improves the dry-run help",
            "`generic_surface`",
            "`private_workspace`",
            "`rss_feed`",
            "`static_site`",
            "`wordpress_private_blog`",
            "`notion` is not a `projection-plan` surface kind",
            "`projection_contract.supported_surface_kinds`",
            "--projection-format metadata_only|safe_html_summary|plain_text_summary",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Projection plan",
            "supported projection surfaces",
            "zet-surface-prototype --surface-kind notion",
            "No rendering, receipt, provider call, publication",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "projection planning with supported-surface help",
            "v0.3.94 - 2026-06-17",
            "projection_contract",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in readme_text or phrase in changelog_text)

    def test_mint_checklist_guidance_is_documented_for_beginner_dry_run(self) -> None:
        quickstart_text = PHASE_2_QUICKSTART_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.116.md").read_text(encoding="utf-8")
        staleness_release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.118.md").read_text(encoding="utf-8")
        batch_release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.119.md").read_text(encoding="utf-8")
        retire_validate_release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.120.md").read_text(encoding="utf-8")
        scoped_validate_release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.121.md").read_text(encoding="utf-8")
        for phrase in (
            "checklist guidance",
            "mint_checklist_guidance",
            "one_clear_purpose",
            "sensitive_content_reviewed",
            "mint:",
            "checklist:",
            "promotion.checklist",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, quickstart_text)
        for phrase in (
            "Mint lifecycle",
            "mint_checklist_guidance",
            "preferred `mint.checklist` frontmatter path",
            "`duplicate_check` metadata",
            "use the generated index instead of rereading every canonical zet body",
            "Current-format generated indexes include `index_metadata`",
            "`staleness_check: index_metadata`",
            "`live_staleness_paths_checked: 0`",
            "upserts the new canonical row",
            "updates `index_metadata`",
            "mint-zet-batch",
            "retire-draft-batch",
            "bulk-mint",
            "bulk-retire",
            "failed_items",
            "do not spawn per-item shell processes",
            "source-zettel-path edge receipt index",
            "filename-only edge-receipt index per Doctor",
            "neither rescan nor reopen the full edge receipt corpus per receipt",
            "Archive validation",
            "validate --since",
            "validate --scope",
            "not a replacement for periodic full archive validation",
            "body_sha256",
            "approved_body_sha256",
            "forbidden_location_reference_found",
            "validate --progress",
            "ETA to stderr",
            "source path resolution uses that file before falling back to the legacy archive-wide id scan",
            "mint target SHA that changed only through approved post-receipt zettel-edge writes can still retire",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "minting with dry-run checklist guidance",
            "v0.3.95 - 2026-06-17",
            "mint_checklist_guidance",
            "v0.3.118 - 2026-06-20",
            "generated-index metadata",
            "v0.3.119 - 2026-06-20",
            "mint-zet-batch",
            "retire-draft-batch",
            "per-item shell",
            "v0.3.120 - 2026-06-20",
            "edge receipt",
            "v0.3.121 - 2026-06-21",
            "scoped validation",
            "validate --since",
            "validate --scope",
            "body_sha256",
            "--progress",
            "v0.3.116 - 2026-06-19",
            "standard `inbox/<zettel_id>.md`",
            "v0.3.114 - 2026-06-19",
            "generated index",
            "retire-draft",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in readme_text or phrase in changelog_text)
        for phrase in (
            "# v0.3.116 - Mint Source Resolve Fast Path",
            "direct standard-path fast path",
            "no longer reparses every zettel just to find the standard",
            "frontmatter id does not match",
            "remove the legacy id scan fallback",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)
        for phrase in (
            "# v0.3.118 - Mint Index Staleness Fast Path",
            "index_metadata",
            "globbing every canonical zettel",
            "file mtime",
            "staleness_check: index_metadata",
            "live_staleness_paths_checked: 0",
            "Older generated indexes do not have `index_metadata`",
            "falls back to the legacy live staleness scan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, staleness_release_text)
        for phrase in (
            "# v0.3.119 - Batch Mint/Retire Robustness",
            "mint-zet-batch",
            "retire-draft-batch",
            "one WOM-kit process",
            "--skip-existing",
            "--max-items",
            "failed_items",
            "no per-item shell process spawning",
            "receipts/mint/batches/",
            "receipts/mint/retired-drafts/batches/",
            "MCP write tools",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, batch_release_text)
        for phrase in (
            "# v0.3.120 - Retire/Validate Edge Receipt Index",
            "source-zettel-path edge receipt index",
            "retire-draft-batch",
            "O(1) source, canonical target, mint receipt, and snapshot SHA replay",
            "Doctor-level edge receipt cache",
            "No archive migration is required",
            "does not",
            "add `validate --since`",
            "progress logging or ETA output",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, retire_validate_release_text)
        for phrase in (
            "# v0.3.121 - Scoped Validate and Progress",
            "archive validate --since",
            "archive validate --scope",
            "generated index",
            "body_sha256",
            "approved_body_sha256",
            "stderr",
            "not a replacement for full archive validation",
            "No archive migration is required",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, scoped_validate_release_text)

    def test_public_product_roadmap_is_linked_from_release_surfaces(self) -> None:
        roadmap_text = PRODUCT_ROADMAP_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        releases_readme_text = (KIT_ROOT / "docs" / "releases" / "README.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.115.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.115 public roadmap baseline",
            "`v0.1.x` | Idea and protocol language",
            "`v0.2.x` | Local implementation",
            "`v0.3.x` | WOM real-use feedback",
            "`v0.4.x` | Custom UI control layer",
            "`v0.5.x` | ZET real-use feedback",
            "It is not a promise that future features already exist.",
            "It is not a claim that production ZET",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, roadmap_text)
        for phrase in (
            "v0.3.116 pre-release",
            "[WOM Product Roadmap](wom-kit/docs/product-roadmap.md)",
            "v0.3.x` is the current WOM real-use",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "Status: v0.3.115 public roadmap baseline",
            "Public product roadmap",
            "planned `v0.4.x` custom UI control layer",
            "planned `v0.5.x` ZET real-use feedback",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        self.assertIn("[WOM Product Roadmap](product-roadmap.md)", public_map_text)
        self.assertIn("[WOM Product Roadmap](https://github.com/mow-coding/zettel-kasten/blob/main/wom-kit/docs/product-roadmap.md)", releases_readme_text)
        self.assertIn("v0.3.115 - 2026-06-19", changelog_text)
        self.assertIn("v0.3.115 adds the public product roadmap", kit_readme_text)
        self.assertIn("# v0.3.115 - Public Roadmap Baseline", release_text)
        self.assertIn("documentation-only", release_text)

    def test_version_truth_source_doc_and_matrix_make_current_cli_explicit(self) -> None:
        version_text = VERSION_TRUTH_SOURCE_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.57.md").read_text(encoding="utf-8")
        historical_release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.137.md").read_text(encoding="utf-8")
        current_release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.215.md").read_text(encoding="utf-8")
        update_text = (KIT_ROOT / "docs" / "project-version-update.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.215 read-only version truth plus approval-gated project update",
            "archive --version",
            "archive version --format json",
            "archive version <project-or-archive-root> --format json",
            "archive runtime-context <archive-root> --format json",
            "archive project-version-update <project-or-archive-root> --target vX.Y.Z --dry-run --format json",
            "wom_kit.__version__",
            ".zettel-kasten/source/installed-version.txt",
            "parent_of_archive/.zettel-kasten/installed-version.txt",
            ".zettel-kasten/source",
            "project_source_mirror",
            "latest fetched semver tag",
            "consistency_state: project_source_mirror_behind_latest_fetched_tag",
            "consistency_state: project_pin_mismatch",
            "version check writes no files and calls no providers",
            "update dry-run is also local",
            "reads no secrets",
            "repairs no project source mirror",
            "redacts local absolute paths by default",
            "not an unattended auto-updater",
            "does not verify a cryptographic tag signature",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, version_text)
        for phrase in (
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "WOM-kit version truth source",
            "archive --version",
            "archive version [root] --format json",
            "runtime-context field `wom_kit_version`",
            "project_source_mirror",
            "parent_of_archive/.zettel-kasten/installed-version.txt",
            "project_source_mirror_behind_latest_fetched_tag",
            "writes no files, repairs no mirror, calls no providers, and reads no secrets",
            "Project WOM-kit version update",
            "project-version-update",
            "updated_restart_required",
            "v0.3.215 is the one-time bootstrap boundary",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.240 pre-release",
            "[Version Truth Source](wom-kit/docs/version-truth-source.md)",
            "[Project Version Update](wom-kit/docs/project-version-update.md)",
            "read-only WOM-kit version truth-source checks",
            "parent project installed-version pin discovery",
            "project-version-update",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/version-truth-source.md",
            "docs/project-version-update.md",
            "version",
            "Print the running WOM-kit CLI version",
            "source mirror status",
            "project-version-update",
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
        for phrase in (
            "project_source_mirror",
            "latest fetched semver tag",
            "The version check remains read-only",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, historical_release_text)
        for phrase in (
            "project-version-update",
            "annotated-tag",
            "rollback",
            "cryptographic tag signature",
            "final existing/manual verified bootstrap update",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, current_release_text)
        for phrase in (
            "Status: implemented in v0.3.215",
            "ready_to_fetch_on_approve",
            "non-force, atomic Git fetch",
            "failed_rollback_incomplete",
            "New Process Required",
            "Bootstrap Boundary",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, update_text)
        self.assertIn("[Version Truth Source](version-truth-source.md)", public_map_text)
        self.assertIn("[Version Truth Source](version-truth-source.md)", public_map_ko_text)
        self.assertIn("[Project Version Update](project-version-update.md)", public_map_text)
        self.assertIn("[프로젝트 버전 갱신](project-version-update.md)", public_map_ko_text)

    def test_one_process_catalog_pass_docs_expose_private_scratch_lifecycle(self) -> None:
        catalog_pass_text = (KIT_ROOT / "docs" / "zet-catalog-one-process-pass.md").read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.216.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        runtime_skill_text = (KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: implemented in v0.3.216",
            "archive zet-catalog-pass <archive-root>",
            "Intermediate pages reuse that materialized snapshot in process memory",
            "catalog_snapshot_changed",
            "catalog_pass_header",
            "catalog_pass_footer",
            "complete output is published",
            "forced process termination can leave a hidden private partial",
            "uses no persistent catalog cache",
            "does not solve model",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, catalog_pass_text)
        for phrase in (
            "Previous checkpoint: Status: v0.3.216 one-process strict catalog pass checkpoint",
            "archive zet-catalog-pass",
            "complete-only catalog JSONL",
            "no persisted cache",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (readme_text, readme_ko_text, kit_readme_text, upgrade_text, upgrade_ko_text, runtime_skill_text):
            with self.subTest(document="operator-surface"):
                self.assertIn("zet-catalog-pass", text)
        for text in (kit_readme_text, upgrade_text, upgrade_ko_text, runtime_skill_text):
            with self.subTest(document="detailed-operator-surface"):
                self.assertIn(".wom-scratch/diagnostics/", text)
                self.assertIn(".jsonl", text)
        for phrase in (
            "v0.3.216 - 2026-07-11",
            "One command, one frontmatter scan",
            "Complete-only private output",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, changelog_text)
        for phrase in (
            "# v0.3.216 - one-process strict catalog pass",
            "process-memory snapshot",
            "complete-only",
            "must not be committed",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)
        self.assertIn("[zet Catalog One-Process Pass](zet-catalog-one-process-pass.md)", public_map_text)
        self.assertIn("[한 프로세스 zet 카탈로그 완주](zet-catalog-one-process-pass.md)", public_map_ko_text)

    def test_catalog_pass_artifact_lifecycle_docs_expose_hash_read_and_cleanup_boundaries(self) -> None:
        lifecycle_text = (KIT_ROOT / "docs" / "zet-catalog-pass-artifact-lifecycle.md").read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.217.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        runtime_skill_text = (KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: implemented in v0.3.217",
            "create -> pin SHA-256 -> validate -> read one page",
            "archive zet-catalog-pass-read <archive-root>",
            "archive zet-catalog-pass-cleanup <archive-root>",
            "A malformed or changed artifact returns no catalog page",
            "Cleanup is never automatic",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, lifecycle_text)
        for phrase in (
            "Previous checkpoint: Status: v0.3.217 SHA-bound catalog artifact lifecycle checkpoint",
            "zet-catalog-pass-read",
            "zet-catalog-pass-cleanup",
            "writes no receipt",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (readme_text, readme_ko_text, kit_readme_text, upgrade_text, upgrade_ko_text, runtime_skill_text):
            with self.subTest(document="operator-surface"):
                self.assertIn("zet-catalog-pass-read", text)
                self.assertIn("zet-catalog-pass-cleanup", text)
        for phrase in (
            "v0.3.217 - 2026-07-11",
            "Pinned complete artifact",
            "Explicit scratch ending",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, changelog_text)
        for phrase in (
            "v0.3.217 - SHA-Bound Catalog Artifact Lifecycle",
            "Private page output requires the expected SHA-256",
            "writes no receipt",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)
        self.assertIn("[zet Catalog Pass Artifact Lifecycle](zet-catalog-pass-artifact-lifecycle.md)", public_map_text)
        self.assertIn("[zet Catalog Pass 임시 파일 수명주기](zet-catalog-pass-artifact-lifecycle.md)", public_map_ko_text)

    def test_abstract_backfill_plan_docs_expose_exact_version_private_review_boundary(self) -> None:
        plan_text = (KIT_ROOT / "docs" / "zet-abstract-backfill-plan.md").read_text(encoding="utf-8")
        schema_text = (KIT_ROOT / "schemas" / "zet-abstract-backfill-proposal.schema.json").read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.218.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        runtime_skill_text = (KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: implemented as read-only planning in v0.3.218",
            "find gap -> read one canonical body -> pin exact file bytes",
            "integrity.file_sha256",
            "archive zet-abstract-backfill-plan <archive-root>",
            "5,000 rows",
            "The v0.3.218 planner itself never writes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, plan_text)
        for phrase in (
            "wom-kit/zet-abstract-backfill-proposal/v0.1",
            "expected_file_sha256",
            "canonical_zet_body",
            "ai_assisted",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, schema_text)
        for phrase in (
            "Previous checkpoint: Status: v0.3.218 reviewed abstract backfill planning checkpoint",
            "zet abstract backfill plan",
            "ready_for_human_review",
            "grants no write authority",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (readme_text, readme_ko_text, kit_readme_text, upgrade_text, upgrade_ko_text, runtime_skill_text):
            with self.subTest(document="operator-surface"):
                self.assertIn("zet-abstract-backfill-plan", text)
        for text in (kit_readme_text, upgrade_text, upgrade_ko_text, runtime_skill_text):
            with self.subTest(document="detailed-operator-surface"):
                self.assertIn(".wom-scratch/abstract-backfill/", text)
        for phrase in (
            "v0.3.218 - 2026-07-11",
            "Exact source-version binding",
            "No automatic repair",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, changelog_text)
        for phrase in (
            "v0.3.218 - Reviewed Abstract Backfill Planning",
            "Redacted zet hashes remain suppressed",
            "does not approve or apply a revision",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)
        self.assertIn("[zet Abstract Backfill Plan](zet-abstract-backfill-plan.md)", public_map_text)
        self.assertIn("[zet 초록 보충 계획](zet-abstract-backfill-plan.md)", public_map_ko_text)

    def test_abstract_backfill_write_docs_expose_human_authority_transaction_and_crash_boundary(self) -> None:
        guide_text = (KIT_ROOT / "docs" / "zet-abstract-backfill-write.md").read_text(encoding="utf-8")
        receipt_schema_text = (KIT_ROOT / "schemas" / "zet-abstract-backfill-receipt.schema.json").read_text(encoding="utf-8")
        decision_text = (
            KIT_ROOT / "docs" / "archive-infra-decision-log-2026-07-11-v03219-abstract-backfill-write.md"
        ).read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.219.md").read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        runtime_skill_text = (KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: implemented as an approval-gated transactional write in v0.3.219",
            "--expected-proposal-sha256 <proposal.sha256>",
            "--affirm-abstracts-reviewed",
            "one canonical zet: 16 MiB",
            "one write batch:   256 MiB",
            "Forced process termination",
            "already_applied",
            "stores no body text and no abstract text",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide_text)
        for phrase in (
            "wom-kit/zet-abstract-backfill-receipt/v0.1",
            "all_proposed_abstracts_reviewed",
            "before_file_sha256",
            "after_file_sha256",
            "abstract_text_stored_in_receipt",
            "crash_recovery_journal_written",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, receipt_schema_text)
        for phrase in (
            "Previous checkpoint: Status: v0.3.219 approval-gated transactional abstract revision checkpoint",
            "zet abstract backfill write",
            "approval-gated write",
            "forced termination or machine failure",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (readme_text, readme_ko_text, kit_readme_text, upgrade_text, upgrade_ko_text, runtime_skill_text):
            with self.subTest(document="operator-surface"):
                self.assertIn("zet-abstract-backfill-write", text)
        for text in (kit_readme_text, upgrade_text, upgrade_ko_text, runtime_skill_text):
            with self.subTest(document="detailed-operator-surface"):
                self.assertIn("--affirm-abstracts-reviewed", text)
        for phrase in (
            "v0.3.219 - 2026-07-11",
            "Whole-batch runtime rollback",
            "Durable revision evidence",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, changelog_text)
        for phrase in (
            "v0.3.219 - Approval-Gated Transactional Abstract Revision",
            "Matching re-run is verified no-write",
            "crash-recovery journal",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)
        for phrase in (
            "Keep planning and writing as separate commands",
            "Snapshot exact canonical bytes in bounded memory",
            "is not crash-safe",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, decision_text)
        self.assertIn("[zet Abstract Backfill Write](zet-abstract-backfill-write.md)", public_map_text)
        self.assertIn("[zet 초록 승인 후 쓰기](zet-abstract-backfill-write.md)", public_map_ko_text)

    def test_abstract_backfill_revert_docs_expose_receipt_audit_exact_inverse_and_removal_authority(self) -> None:
        guide_text = (KIT_ROOT / "docs" / "zet-abstract-backfill-revert.md").read_text(encoding="utf-8")
        schema_text = (KIT_ROOT / "schemas" / "zet-abstract-backfill-revert-receipt.schema.json").read_text(encoding="utf-8")
        decision_text = (
            KIT_ROOT / "docs" / "archive-infra-decision-log-2026-07-11-v03220-abstract-backfill-revert.md"
        ).read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.220.md").read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        runtime_skill_text = (KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: implemented as a receipt-audited approval-gated revert in v0.3.220",
            "--expected-receipt-sha256 <receipt.sha256>",
            "--affirm-abstract-removal-reviewed",
            "removing only that line reconstructs the exact recorded",
            "one revert batch:  256 MiB",
            "stores no body text and no abstract text",
            "new proposal SHA-256",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide_text)
        for phrase in (
            "wom-kit/zet-abstract-backfill-revert-receipt/v0.1",
            "abstract_removal_reviewed",
            "applied_file_sha256",
            "reverted_file_sha256",
            "removed_abstract_sha256",
            "exact_before_file_hash_restored",
            "crash_recovery_journal_written",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, schema_text)
        for phrase in (
            "Previous checkpoint: Status: v0.3.220 receipt-audited deterministic abstract rollback checkpoint",
            "zet abstract backfill revert",
            "Any later canonical edit",
            "Reapplying later requires a newly reviewed proposal byte sequence",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (readme_text, readme_ko_text, kit_readme_text, upgrade_text, upgrade_ko_text, runtime_skill_text):
            with self.subTest(document="operator-surface"):
                self.assertIn("zet-abstract-backfill-revert", text)
        for text in (kit_readme_text, upgrade_text, upgrade_ko_text, runtime_skill_text):
            with self.subTest(document="detailed-operator-surface"):
                self.assertIn("--affirm-abstract-removal-reviewed", text)
        for phrase in (
            "v0.3.220 - 2026-07-11",
            "One-field inverse proof",
            "Transactional revert evidence",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, changelog_text)
        for phrase in (
            "v0.3.220 - Receipt-Audited Deterministic Abstract Rollback",
            "Matching re-run is verified no-write",
            "new proposal hash",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)
        for phrase in (
            "Make the immutable applied receipt",
            "removing only the deterministic first `abstract:` line",
            "not a general revision engine",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, decision_text)
        self.assertIn("[zet Abstract Backfill Revert](zet-abstract-backfill-revert.md)", public_map_text)
        self.assertIn("[zet 초록 보충 되돌리기](zet-abstract-backfill-revert.md)", public_map_ko_text)

    def test_abstract_receipt_lifecycle_audit_docs_expose_complete_bounded_content_free_contract(self) -> None:
        guide_text = (KIT_ROOT / "docs" / "zet-abstract-backfill-receipt-audit.md").read_text(encoding="utf-8")
        decision_text = (
            KIT_ROOT / "docs" / "archive-infra-decision-log-2026-07-11-v03221-abstract-receipt-audit.md"
        ).read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.221.md").read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        runtime_skill_text = (KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: implemented as an archive-wide read-only audit in v0.3.221",
            "--max-receipts 5000 --max-locks 5000 --max-problems 100",
            "Applied And Current",
            "Reverted And Current",
            "It reads the filename shape, never the lock file content",
            "audit_digest",
            "problems_truncated",
            "writes or deletes nothing",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide_text)
        for phrase in (
            "Status: v0.3.221 archive-wide abstract receipt and lock audit checkpoint",
            "Version: v0.3.240, release candidate",
            "zet abstract receipt lifecycle audit",
            "Up to 5,000 receipts and 5,000 locks",
            "Green proves bounded local consistency",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (readme_text, readme_ko_text, kit_readme_text, upgrade_text, upgrade_ko_text, runtime_skill_text):
            with self.subTest(document="operator-surface"):
                self.assertIn("zet-abstract-backfill-receipt-audit", text)
        for text in (kit_readme_text, upgrade_text, upgrade_ko_text, runtime_skill_text):
            with self.subTest(document="detailed-operator-surface"):
                self.assertIn("--max-problems", text)
        for phrase in (
            "v0.3.221 - 2026-07-11",
            "Complete lifecycle scan",
            "Bounded AI output",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, changelog_text)
        for phrase in (
            "v0.3.221 - Archive-Wide Abstract Receipt And Lock Audit",
            "Completed-operation locks warn",
            "Healthy rows collapse into counts",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)
        for phrase in (
            "Listing every healthy receipt in JSON",
            "Read lock filenames only",
            "future paged audit",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, decision_text)
        self.assertIn(
            "[zet Abstract Receipt Lifecycle Audit](zet-abstract-backfill-receipt-audit.md)",
            public_map_text,
        )
        self.assertIn(
            "[zet 초록 수정 영수증 전체 검진](zet-abstract-backfill-receipt-audit.md)",
            public_map_ko_text,
        )

    def test_tiro_import_plan_doc_and_matrix_cover_read_only_meeting_manifest_contract(self) -> None:
        tiro_text = TIRO_IMPORT_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.137.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.137 read-only Tiro meeting transcript import planning",
            "archive tiro-import-plan <archive-root> --manifest workbench/tiro-meeting.sample.json --dry-run --format json",
            "tiro_import_plan",
            "wom-tiro-import-manifest/v0.1",
            "workbench/tiro-meeting.sample.json",
            "meeting metadata presence",
            "participant and speaker counts",
            "transcript segment count",
            "audio object id",
            "does not echo meeting titles",
            "writes no files",
            "calls no Tiro API",
            "reads no audio bytes",
            "writes no derived text",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, tiro_text)
        for phrase in (
            "Tiro meeting import plan",
            "archive tiro-import-plan",
            "MCP `tiro_import_plan`",
            "echoes no meeting title",
            "calls no Tiro API",
            "reads no audio bytes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "[Tiro Import Plan](wom-kit/docs/tiro-import-plan.md)",
            "read-only Tiro meeting transcript import planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/tiro-import-plan.md",
            "tiro-import-plan",
            "Plan Tiro meeting transcript and audio-objet import",
            "archive tiro-import-plan --manifest workbench/tiro-meeting.sample.json --dry-run",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[Tiro Import Plan](tiro-import-plan.md)", public_map_text)
        self.assertIn("[Tiro Import Plan](tiro-import-plan.md)", public_map_ko_text)
        for phrase in (
            "v0.3.137 adds the first read-only WOM-kit planning gate",
            "archive tiro-import-plan",
            "MCP `tiro_import_plan`",
            "no transcript/title/link echo",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)

    def test_tiro_lossless_recovery_and_zet_markdown_style_docs_are_publicly_indexed(self) -> None:
        tiro_text = TIRO_LOSSLESS_RECOVERY_PATH.read_text(encoding="utf-8")
        style_text = ZET_MARKDOWN_STYLE_GUIDE_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.143.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.143 live Tiro REST fetch with OS credential-store read checkpoint",
            "archive tiro-lossless-recovery-plan <archive-root>",
            "archive tiro-lossless-recovery-fetch-run <archive-root>",
            "archive tiro-lossless-recovery-capture <archive-root>",
            "keyring:<safe-tiro-label>",
            "credential-manager:<safe-tiro-label>",
            "Windows Credential Manager",
            "workspaces",
            "transcript paragraphs",
            "generated note documents",
            "word memories",
            "wiki info",
            "base API: `https://api.tiro.ooo`",
            "600 requests per 60 seconds",
            "receipts/tiro/lossless-fetches/*.json",
            "objects/sha256/<prefix>/<sha256>",
            "v0.3.143 implements the live credential-bounded Tiro REST fetch adapter",
            "auto-detect exactly one Windows generic credential target",
            "audio_original_bytes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, tiro_text)
        for phrase in (
            "Status: v0.3.184 zet Markdown authoring and frontmatter viewer checkpoint",
            "archive zet-markdown-style-guide <archive-root> --topic range_tilde --dry-run --format json",
            "A ~ B",
            "A~~B",
            "Double tilde is used only when the human explicitly wants Markdown",
            "archive read-zettel <archive-root> --zettel-id <id> --section document",
            "storage metadata, not document prose",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, style_text)
        for phrase in (
            "Status: v0.3.143 Tiro OS credential-store read checkpoint",
            "Tiro lossless recovery",
            "archive tiro-lossless-recovery-plan",
            "archive tiro-lossless-recovery-fetch-run",
            "archive tiro-lossless-recovery-capture",
            "archive tiro-recovery-fetch-run",
            "credential-manager:<safe-label>",
            "Windows Credential Manager-backed",
            "zet Markdown style guide",
            "archive zet-markdown-style-guide",
            "A ~ B",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "[Tiro Lossless Recovery](wom-kit/docs/tiro-lossless-recovery.md)",
            "[zet Markdown Style Guide](wom-kit/docs/zet-markdown-style-guide.md)",
            "raw Tiro recovery bundle capture",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/tiro-lossless-recovery.md",
            "docs/zet-markdown-style-guide.md",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[Tiro Lossless Recovery](tiro-lossless-recovery.md)", public_map_text)
        self.assertIn("[zet Markdown Style Guide](zet-markdown-style-guide.md)", public_map_text)
        self.assertIn("[Tiro Lossless Recovery](tiro-lossless-recovery.md)", public_map_ko_text)
        self.assertIn("[zet Markdown Style Guide](zet-markdown-style-guide.md)", public_map_ko_text)
        for phrase in (
            "v0.3.143 removes the last `env:`-only blocker",
            "archive tiro-lossless-recovery-plan",
            "archive tiro-lossless-recovery-fetch-run",
            "archive tiro-lossless-recovery-capture",
            "Dry-run still reads no credential value",
            "Windows Credential Manager",
            "audio_original_bytes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)

    def test_runtime_canonical_entrypoints_doc_and_matrix_keep_orientation_read_only(self) -> None:
        entrypoints_text = RUNTIME_CANONICAL_ENTRYPOINTS_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.58.md").read_text(encoding="utf-8")
        current_release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.106.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.240 quick handoff, scalable first-read diagnostics, chronological revision-audit, and exact-restore checkpoint",
            "archive runtime-context <archive-root> --format json",
            "operational_context",
            "ops/operational-context.yml",
            "operational_context.session_start_injection",
            "canonical_entrypoints",
            "ai_runtime_order",
            "recommended_first_commands",
            "material_link_routes",
            "AI Runtime Order",
            "archive.yml",
            "AGENTS.md",
            "archive operational-context <archive-root> --dry-run --format json",
            "archive ai-response-concept-guide <archive-root> --topic all --dry-run",
            "notion-objet-import-clue-audit",
            "notion-objet-source-map-link-plan",
            "notion-objet-link-index",
            "source-bindings.yml",
            "provider-bindings.yml",
            "objects/manifests/files.jsonl",
            "objects/manifests/derived-text.jsonl",
            "reads no other file bodies",
            "writes no files",
            "calls no providers",
            "reads no secrets",
            "echoes no local absolute paths by default",
            "does not enforce migration",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, entrypoints_text)
        for phrase in (
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "Runtime canonical entrypoints",
            "Runtime-context field `canonical_entrypoints`",
            "AI operational context rehydration",
            "Runtime-context field `operational_context`",
            "`ai_runtime_order`",
            "`recommended_first_commands`",
            "`material_link_routes`",
            "`archive.yml` as the start-here file",
            "`source-bindings.yml`",
            "`ops/operational-context.yml`",
            "echoes no local absolute paths by default",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
            "[Runtime Canonical Entry Points](wom-kit/docs/runtime-canonical-entrypoints.md)",
            "runtime-context canonical entrypoint metadata",
            "AI operational context rehydration",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/runtime-canonical-entrypoints.md",
            "docs/operational-context.md",
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
        for phrase in (
            "# v0.3.106 - Runtime AI Guide Handoff",
            "`ai_runtime_order`",
            "`recommended_first_commands`",
            "`material_link_routes`",
            "run `runtime-context`",
            "read `AGENTS.md`",
            "run `ai-response-concept-guide`",
            "provider-free",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, current_release_text)
        self.assertIn("[Runtime Canonical Entry Points](runtime-canonical-entrypoints.md)", public_map_text)
        self.assertIn("[Runtime Canonical Entry Points](runtime-canonical-entrypoints.md)", public_map_ko_text)

    def test_operational_context_doc_and_release_surfaces_define_rehydration_boundary(self) -> None:
        operational_text = OPERATIONAL_CONTEXT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.117.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.117 AI operational context rehydration checkpoint",
            "ops/operational-context.yml",
            "operational_context.record",
            "operational_context.session_start_injection",
            "archive operational-context <archive-root> --dry-run --format json",
            "workbench/operational-context.next.yml",
            "--approve --reviewed-by",
            "receipts/operational-context/",
            "must not contain provider URLs, local absolute paths",
            "exposes no MCP write tool",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, operational_text)
        for phrase in (
            "Status: v0.3.117 AI operational context rehydration checkpoint",
            "AI operational context rehydration",
            "approval-gated write",
            "Runtime-context field `operational_context`",
            "`ops/operational-context.yml`",
            "`archive operational-context <archive-root> --dry-run --format json`",
            "`receipts/operational-context/*.operational-context.json`",
            "MCP write tool",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.117 pre-release",
            "AI operational context rehydration",
            "`ops/operational-context.yml`",
            "`archive operational-context`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/operational-context.md",
            "v0.3.117 adds AI operational context rehydration",
            "CLI `archive operational-context`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        for phrase in (
            "v0.3.117 - 2026-06-20",
            "AI operational context rehydration",
            "provider URLs, local path hints, email-like",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, changelog_text)
        for phrase in (
            "# v0.3.117 - AI Operational Context Rehydration",
            "session_start_injection",
            "scan broad archive bodies",
            "Candidate values that contain provider URLs",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)
        self.assertIn("[Operational Context](operational-context.md)", public_map_text)
        self.assertIn("[Operational Context](operational-context.md)", public_map_ko_text)

    def test_ai_usage_observability_is_documented_without_prompt_logging(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.122.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.122 AI usage observability checkpoint",
            "AI usage observability",
            "archive ai-usage-plan --dry-run",
            "archive ai-usage-record --dry-run|--approve",
            "archive ai-usage-report --dry-run",
            "receipts/ai-usage/",
            "stores no prompts or responses",
            "calls no LLM providers",
            "does not enforce hard runtime budgets yet",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.122 pre-release",
            "AI token usage observability",
            "archive ai-usage-plan --dry-run",
            "archive ai-usage-record --approve",
            "archive ai-usage-report --dry-run",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "v0.3.122 adds the first AI usage observability layer",
            "local token-accounting ledger baseline",
            "does not call LLM providers",
            "store prompts",
            "store responses",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        for phrase in (
            "v0.3.122 - 2026-06-21",
            "ai-usage-plan",
            "ai-usage-record",
            "ai-usage-report",
            "non-secret AI runtime token usage receipts",
            "store prompts",
            "store responses",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, changelog_text)
        for phrase in (
            "# v0.3.122 - AI Usage Observability Baseline",
            "How much context did this AI task plan to read?",
            "receipts/ai-usage/",
            "It stores no prompt body and no response body.",
            "archive ai-usage-report --dry-run",
            "No archive migration is required.",
            "does not",
            "call LLM providers",
            "enforce hard runtime budgets",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)

    def test_ai_artifact_lifecycle_inventory_is_documented_without_body_logging(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.187.md").read_text(encoding="utf-8")
        decision_log_text = (
            KIT_ROOT / "docs" / "archive-infra-decision-log-2026-07-07-v03187-ai-artifact-lifecycle-inventory.md"
        ).read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.187 AI artifact lifecycle inventory checkpoint",
            "AI artifact lifecycle inventory",
            "archive ai-artifact-inventory --dry-run",
            "unreviewed_ai_artifact",
            "source_intake_recorded",
            "preserve raw bytes as an objet",
            "reads no file bodies",
            "does not echo archive-relative paths unless `--show-relative-paths`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.187 pre-release",
            "read-only AI artifact inventory",
            "archive ai-artifact-inventory --dry-run",
            "calling providers",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "v0.3.187 pre-release",
            "AI artifact inventory",
            "파일 본문을 읽지 않고",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_ko_text)
        for text in (changelog_text, upgrade_text, release_text, decision_log_text):
            with self.subTest(document=text[:40]):
                self.assertIn("ai-artifact-inventory", text)
                self.assertIn("objet", text)
                self.assertIn("file bodies", text)

    def test_containment_link_type_is_documented_with_model_gap_guardrail(self) -> None:
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.123.md").read_text(encoding="utf-8")
        guide_text = AI_RESPONSE_CONCEPT_GUIDE_PATH.read_text(encoding="utf-8")
        connection_text = CONNECTION_IMPORT_PLAN_PATH.read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.123 containment link type and model-gap escalation checkpoint",
            "`contains` for structural child page/database containment",
            "`notion_containment` child page/database/view nesting",
            "model-gap escalation",
            "developer decision required",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.123 pre-release",
            "base connection edge vocabulary including `contains`",
            "model-gap escalation when no active edge type fits",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "v0.3.123 adds a dedicated containment edge vocabulary checkpoint",
            "notion_containment",
            "contains",
            "model-gap escalation",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        for phrase in (
            "v0.3.123 - 2026-06-21",
            "dedicated `contains` link type",
            "`notion_containment` evidence",
            "developer decision required",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, changelog_text)
        for phrase in (
            "# v0.3.123 - Containment Link Type",
            "parent page or zet contains child page",
            "`notion_containment` evidence and maps it to `contains`",
            "Report a model gap and ask for a developer decision",
            "does not",
            "read real exports",
            "write durable edges by itself",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)
        for phrase in (
            "`contains` explanation",
            "model-gap escalation guard",
            "structural containment has its own `contains` meaning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide_text)
        for phrase in (
            "notion_containment",
            "child page/database/view nesting",
            "`contains` is for structural nesting",
            "developer decision",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, connection_text)

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
        latest_release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.76.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.76 read-only large-media export trap checkpoint",
            "archive external-export-plan <archive-root>",
            "full_media_requested",
            "stop_and_split_media_before_export",
            "large_media_export_trap",
            "workspace_or_database_export_can_pull_bulk_media",
            "text_only_review",
            "targeted_page_or_database_review",
            "selected_media_after_review",
            "top-level pages",
            "uploaded files, attachments, images, audio, or video",
            "writes no archive receipts",
            "echo provider URLs, local paths, filenames, account ids, emails, tokens, or",
            "does not implement provider export automation",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "External export plan",
            "archive external-export-plan --source notion|google_drive|generic_workspace --dry-run",
            "large_media_export_trap",
            "text-only/targeted first-pass commands",
            "stop-and-split-media modes",
            "writes nothing, starts no provider export",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
            "[External Export Plan](wom-kit/docs/external-export-plan.md)",
            "explicit large-media trap detection",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "external-export-plan",
            "Plan a text-first Notion, Google Drive, or generic workspace export",
            "detects the broad workspace/database export trap",
            "text-only and targeted first-pass command shapes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        for phrase in (
            "[External Export Plan](external-export-plan.md)",
            "v0.3.66 - External Export Plan",
            "starts no provider export",
            "v0.3.76 - Large Media Export Trap",
            "large_media_export_trap",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    phrase in public_map_text
                    or phrase in public_map_ko_text
                    or phrase in release_text
                    or phrase in latest_release_text
                )

    def test_connection_import_plan_maps_notion_connection_evidence_without_writes(self) -> None:
        text = CONNECTION_IMPORT_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.77.md").read_text(encoding="utf-8")
        latest_release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.79.md").read_text(encoding="utf-8")
        base_types_text = BASE_TYPES_PATH.read_text(encoding="utf-8")
        fake_types_text = FAKE_ARCHIVE_TYPES_PATH.read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.79 read-only connection edge vocabulary checkpoint",
            "archive connection-import-plan <archive-root>",
            "relation_property",
            "notion_containment",
            "synced_block_reference",
            "database_view_filter",
            "internal_url_hyperlink",
            "mention_page",
            "comment_context",
            "objet_embed",
            "`contains`",
            "`material`, `derived`",
            "`view_query`",
            "recommended edge types are allowed link types",
            "The WOM-kit base and fake archive",
            "model gap",
            "developer decision",
            "Dynamic Snapshot Rule",
            "call Notion",
            "write edges",
            "comment bodies",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "Connection import plan",
            "archive connection-import-plan --source notion --connection-kind all --dry-run",
            "MCP `connection_import_plan`",
            "`material`, `derived`, `semantic`, `embed`, `mention`, `contains`, `supersedes`, `view_query`, `comment_context`",
            "The base `zettel-kasten/types.yml` now defines the recommended connection edge vocabulary",
            "notion_containment",
            "model-gap escalation",
            "write no edges",
            "comment bodies",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
            "[Connection Import Plan](wom-kit/docs/connection-import-plan.md)",
            "read-only Notion connection import planning for typed-edge candidates with base connection edge vocabulary",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/connection-import-plan.md",
            "connection-import-plan",
            "Plan Notion connection evidence import into WOM typed-edge candidates",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        for phrase in (
            "[Connection Import Plan](connection-import-plan.md)",
            "v0.3.77 - Connection Import Plan",
            "connection_import_plan",
            "v0.3.79 - Connection Edge Vocabulary",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    phrase in public_map_text
                    or phrase in public_map_ko_text
                    or phrase in release_text
                    or phrase in latest_release_text
                )
        for edge_type in ("material", "derived", "semantic", "embed", "mention", "contains", "view_query", "comment_context"):
            with self.subTest(edge_type=edge_type):
                self.assertIn(f"- id: {edge_type}", base_types_text)
                self.assertIn(f"- id: {edge_type}", fake_types_text)

    def test_connection_evidence_parser_contract_is_documented_without_overclaiming_parser(self) -> None:
        text = CONNECTION_EVIDENCE_PARSER_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.80.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.80 read-only parser contract checkpoint",
            "archive connection-evidence-parser-contract <archive-root>",
            "connection-parser-contract",
            "notion-connection-parser-contract",
            "connection_evidence_parser_contract",
            "relation_property",
            "database_view_filter",
            "notion_containment",
            "comment_context",
            "objet_embed",
            "candidate_id",
            "review_status",
            "Dynamic view/filter and comment-context evidence must include reviewed static",
            "model-gap review",
            "execute a parser",
            "write candidate edge records",
            "comment bodies",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Connection evidence parser contract",
            "archive connection-evidence-parser-contract --source notion --connection-kind all --dry-run",
            "MCP `connection_evidence_parser_contract`",
            "candidate_id",
            "executes no parser",
            "writes no candidate records",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
            "[Connection Evidence Parser Contract](wom-kit/docs/connection-evidence-parser-contract.md)",
            "a read-only connection evidence parser contract before real export parsing",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/connection-evidence-parser-contract.md",
            "connection-evidence-parser-contract",
            "Preview the future Notion connection evidence parser contract",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        for phrase in (
            "[Connection Evidence Parser Contract](connection-evidence-parser-contract.md)",
            "v0.3.80 - Connection Evidence Parser Contract",
            "connection_evidence_parser_contract",
            "no Notion call",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    phrase in public_map_text
                    or phrase in public_map_ko_text
                    or phrase in release_text
                    or phrase in changelog_text
                )

    def test_connection_evidence_fixture_parser_is_documented_as_sanitized_only(self) -> None:
        text = CONNECTION_EVIDENCE_FIXTURE_PARSER_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.81.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        fixture_text = (KIT_ROOT / "examples" / "fake-life-archive" / "workbench" / "connection-evidence.sample.json").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.81 read-only sanitized fixture parser checkpoint",
            "archive connection-evidence-parse-fixture <archive-root>",
            "workbench/connection-evidence.sample.json",
            "connection-evidence-parser-fixture",
            "notion-connection-evidence-parser-fixture",
            "connection_evidence_parse_fixture",
            "candidate_id",
            "write_status",
            "not_written",
            "It does not read real Notion",
            "write candidate edge records",
            "comment bodies",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "Connection evidence fixture parser",
            "archive connection-evidence-parse-fixture --evidence workbench/connection-evidence.sample.json --source notion --connection-kind all --dry-run",
            "MCP `connection_evidence_parse_fixture`",
            "9 fixture records emit 11 candidate previews",
            "reads no real source exports",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
            "[Connection Evidence Fixture Parser](wom-kit/docs/connection-evidence-fixture-parser.md)",
            "a sanitized fixture parser that emits candidate edge previews without writes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/connection-evidence-fixture-parser.md",
            "connection-evidence-parse-fixture",
            "Parse a sanitized archive-internal Notion connection evidence fixture",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        for phrase in (
            "[Connection Evidence Fixture Parser](connection-evidence-fixture-parser.md)",
            "v0.3.81 - Connection Evidence Fixture Parser",
            "connection_evidence_parse_fixture",
            "no Notion call",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    phrase in public_map_text
                    or phrase in public_map_ko_text
                    or phrase in release_text
                    or phrase in changelog_text
                )
        for phrase in (
            '"fixture_kind": "connection_evidence_fixture"',
            '"connection_kind": "database_view_filter"',
            '"connection_kind": "comment_context"',
            '"connection_kind": "objet_embed"',
            '"connection_kind": "notion_containment"',
            '"child_refs"',
            '"review_status": "fixture_reviewed"',
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, fixture_text)

    def test_connection_edge_intelligence_plan_is_documented_as_read_only_review_layer(self) -> None:
        text = CONNECTION_EDGE_INTELLIGENCE_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.87.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.87 read-only connection edge intelligence checkpoint",
            "Status: v0.3.102 read-only connection edge review summary and supersedes heuristic checkpoint",
            "archive connection-edge-intelligence-plan",
            "archive zettel-edge-batch",
            "connection-edge-classification-plan",
            "source_mechanism",
            "relationship_meaning",
            "Version Chain Heuristic",
            "version_replacement",
            "structural_containment",
            "contains",
            "supersedes",
            "Review Counters",
            "human_review_required_count",
            "durable_write_human_approval_required_count",
            "auto_writable_count",
            "format_variant",
            "responds_to",
            "fulfills",
            "enabling",
            "model gaps",
            "call an LLM",
            "write edges",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "Connection edge intelligence plan",
            "archive connection-edge-intelligence-plan --evidence workbench/connection-evidence.sample.json --source notion --connection-kind all --dry-run",
            "source_mechanism",
            "relationship_meaning",
            "version_replacement",
            "structural_containment",
            "supersedes",
            "review_summary",
            "human_review_required_count",
            "auto_writable_count: 0",
            "format_variant",
            "MCP exposes no tool for this surface",
            "calls no LLM",
            "writes no candidate records",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
            "[Connection Edge Intelligence Plan](wom-kit/docs/connection-edge-intelligence-plan.md)",
            "read-only connection edge intelligence planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/connection-edge-intelligence-plan.md",
            "connection-edge-intelligence-plan",
            "Plan meaning/mechanism classification",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[Connection Edge Intelligence Plan](connection-edge-intelligence-plan.md)", public_map_text)
        self.assertIn("[Connection Edge Intelligence Plan](connection-edge-intelligence-plan.md)", public_map_ko_text)
        for phrase in (
            "v0.3.87 - Connection Edge Intelligence Plan",
            "Status: v0.3.87 read-only connection edge intelligence checkpoint",
            "connection_edge_intelligence_plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in release_text or phrase in changelog_text)

    def test_notion_nested_tree_plan_is_documented_as_read_only_recovery_gate(self) -> None:
        text = NOTION_NESTED_TREE_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.125.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.125 read-only nested child-page recovery checkpoint",
            "archive notion-nested-tree-plan",
            "notion_nested_tree_plan",
            "generation_roots",
            "recovery_queue",
            "hold_queue",
            "structure_skip_queue",
            "untraceable",
            "`content_class` is now optional",
            "blocks instead of",
            "does not",
            "read real Notion exports",
            "read page titles",
            "write zets",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Status: v0.3.124 Notion nested tree recovery checkpoint",
            "Notion nested tree recovery plan",
            "archive notion-nested-tree-plan --tree workbench/notion-nested-tree.sample.json --source notion --dry-run",
            "DB1/DB2/DB3",
            "untraceable",
            "auto_writable_count: 0",
            "reads no page titles",
            "mints no pages",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.133 pre-release",
            "read-only Notion nested tree recovery planning",
            "reports untraceable parent chains instead of guessing from partial mirrors",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "v0.3.133 pre-release",
            "read-only nested tree recovery planning",
            "추적불능 parent chain",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_ko_text)
        for phrase in (
            "docs/notion-nested-tree-plan.md",
            "notion-nested-tree-plan",
            "Plan nested Notion child-page recovery",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[Notion Nested Tree Plan](notion-nested-tree-plan.md)", public_map_text)
        self.assertIn("[Notion Nested Tree Plan](notion-nested-tree-plan.md)", public_map_ko_text)
        for phrase in (
            "# v0.3.125 - Notion Ancestor Crawl Request Plan",
            "notion_nested_tree_plan",
            "notion_ancestor_crawl_plan",
            "reports `untraceable`",
            "partial success",
            "missing ancestor",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in release_text or phrase in changelog_text)

    def test_notion_ancestor_crawl_plan_is_documented_as_read_only_request_gate(self) -> None:
        text = NOTION_ANCESTOR_CRAWL_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.129.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.133 read-only scoped missing ancestor crawl request checkpoint",
            "archive notion-ancestor-crawl-plan",
            "notion_ancestor_crawl_plan",
            "missing_ancestor_ref",
            "crawl_request_queue",
            "--scope-generation-id",
            "scope_filter",
            "scope_generation_id_may_not_match_generation_unknown_untraceable_leaf_requests",
            "required_return_fields",
            "provider adapter",
            "does not call Notion",
            "read page titles",
            "write zets",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Notion ancestor crawl request plan",
            "archive notion-ancestor-crawl-plan --tree workbench/notion-nested-tree.sample.json --source notion --scope-generation-id DB1 --dry-run",
            "crawl_request_queue",
            "scope_generation_ids",
            "provider URLs",
            "tokens",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.133 pre-release",
            "read-only Notion ancestor crawl request planning",
            "blocks oversized nested-tree fixtures instead of returning partial success",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "v0.3.133 pre-release",
            "조상 crawl 요청 큐",
            "부분 성공으로 위장하지 않도록 차단",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_ko_text)
        for phrase in (
            "docs/notion-ancestor-crawl-plan.md",
            "notion-ancestor-crawl-plan",
            "Plan missing Notion ancestor crawl requests",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[Notion Ancestor Crawl Plan](notion-ancestor-crawl-plan.md)", public_map_text)
        self.assertIn("[Notion Ancestor Crawl Plan](notion-ancestor-crawl-plan.md)", public_map_ko_text)
        for phrase in (
            "# v0.3.129 - Notion Ancestor Crawl Scope Filters",
            "notion_ancestor_crawl_plan",
            "scope filters",
            "credential-bounded adapter",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in release_text or phrase in changelog_text)

    def test_notion_ancestor_fetch_adapter_execution_contract_is_documented_as_read_only_live_run_handoff(self) -> None:
        text = NOTION_ANCESTOR_FETCH_ADAPTER_EXECUTION_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        guide_text = (KIT_ROOT / "docs" / "ai-response-concept-guide.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.133.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.134 read-only recursive fetch contract and live-run handoff checkpoint",
            "archive notion-ancestor-fetch-adapter-execution-contract",
            "notion_ancestor_fetch_adapter_execution_contract",
            "adapter_input_contract",
            "adapter_output_contract",
            "execution_actor_contract",
            "Recursive Fetch Requirement",
            "notion_ancestor_result_fixture",
            "does not call Notion",
            "retrieve credential values",
            "write receipts",
            "archive notion-ancestor-fetch-adapter-run",
            "The contract command stays",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Status: v0.3.134 Notion ancestor live structure fetch checkpoint",
            "Notion ancestor fetch adapter execution contract",
            "archive notion-ancestor-fetch-adapter-execution-contract",
            "notion_ancestor_fetch_adapter_execution_contract",
            "live fetch subject must be a WOM local credential-bounded adapter process",
            "client-supplied ancestor fixtures",
            "parent-chain fetch to recurse",
            "This contract command performs no live fetch",
            "retrieves no secrets",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.134 pre-release",
            "recursive fetch adapter execution contract",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "v0.3.134 pre-release",
            "recursive fetch adapter execution contract",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_ko_text)
        for phrase in (
            "docs/notion-ancestor-fetch-adapter-execution-contract.md",
            "notion-ancestor-fetch-adapter-execution-contract",
            "Preview the read-only execution and actor contract",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("notion-ancestor-fetch-adapter-execution-contract", guide_text)
        self.assertIn(
            "[Notion Ancestor Fetch Adapter Execution Contract](notion-ancestor-fetch-adapter-execution-contract.md)",
            public_map_text,
        )
        self.assertIn(
            "[Notion Ancestor Fetch Adapter Execution Contract](notion-ancestor-fetch-adapter-execution-contract.md)",
            public_map_ko_text,
        )
        for phrase in (
            "# v0.3.133 - Notion Recursive Live Fetch Contract",
            "notion_ancestor_fetch_adapter_execution_contract",
            "recursive_fetch_contract",
            "scope_generation_id_may_not_match_generation_unknown_untraceable_leaf_requests",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in release_text or phrase in changelog_text)

    def test_notion_ancestor_fetch_adapter_run_is_documented_as_approval_gated_live_structure_fetch(self) -> None:
        text = NOTION_ANCESTOR_FETCH_ADAPTER_RUN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        guide_text = (KIT_ROOT / "docs" / "ai-response-concept-guide.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.134.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.141 approval-gated local Notion ancestor structure fetch with actionable provider failure classification",
            "archive notion-ancestor-fetch-adapter-run",
            "credential access approval receipt",
            "notion_ancestor_result_fixture",
            "receipts/notion/ancestor-fetches",
            "known_generation_root_ref_reached",
            "notion-ancestor-merge-plan",
            "There is no MCP live execution tool",
            "does not read page titles",
            "does not read page bodies",
            "does not download media bytes",
            "Retrieve a page",
            "Parent object",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Notion ancestor fetch adapter run",
            "approval-gated write",
            "archive notion-ancestor-fetch-adapter-run",
            "env:WOM_NOTION_READONLY_TOKEN",
            "receipts/notion/ancestor-fetches",
            "does not expose an MCP live provider-call tool",
            "page titles",
            "media bytes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.134 pre-release",
            "first approval-gated local Notion ancestor structure fetch adapter",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "v0.3.134 pre-release",
            "첫 local Notion ancestor structure fetch adapter",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_ko_text)
        for phrase in (
            "docs/notion-ancestor-fetch-adapter-run.md",
            "notion-ancestor-fetch-adapter-run",
            "first approval-gated local Notion ancestor structure fetch adapter",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("notion-ancestor-fetch-adapter-run", guide_text)
        self.assertIn(
            "[Notion Ancestor Fetch Adapter Run](notion-ancestor-fetch-adapter-run.md)",
            public_map_text,
        )
        self.assertIn(
            "[Notion Ancestor Fetch Adapter Run](notion-ancestor-fetch-adapter-run.md)",
            public_map_ko_text,
        )
        for phrase in (
            "# v0.3.134 - Notion Ancestor Live Structure Fetch",
            "notion-ancestor-fetch-adapter-run",
            "approval-gated local",
            "env:",
            "Notion API",
            "no MCP live provider-call tool",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in release_text or phrase in changelog_text)

    def test_notion_recover_doc_and_matrix_explain_one_command_wrapper(self) -> None:
        text = NOTION_RECOVER_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        manual_text = BEGINNER_SETUP_MANUAL_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (
            (KIT_ROOT / "docs" / "releases" / "v0.3.138.md").read_text(encoding="utf-8")
            + "\n"
            + (KIT_ROOT / "docs" / "releases" / "v0.3.136.md").read_text(encoding="utf-8")
        )
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.141 beginner-friendly one-command local Notion location recovery with actionable failure classification",
            "archive notion-recover",
            "auto-selects the reviewed Notion tree fixture",
            "file:<path>",
            "hidden local terminal prompt",
            "Vault/keyring refs",
            "choose a page id",
            "create or name an environment variable",
            "copy an approval receipt path",
            "echo the local token-file path",
            "read page titles",
            "read page bodies",
            "download media bytes",
            "Power-user commands",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Notion recover",
            "approval-gated write",
            "archive notion-recover",
            "file:<path>",
            "hidden local terminal prompt",
            "live vault/keyring/OAuth reads are not implemented",
            "does not require beginners to choose a page id",
            "echo approval receipt paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        self.assertIn("archive notion-recover", manual_text)
        self.assertIn("file:<path>", manual_text)
        self.assertIn("hidden local terminal prompt", manual_text)
        self.assertIn("[Notion Recover](wom-kit/docs/notion-recover.md)", readme_text)
        self.assertIn("[Notion Recover](wom-kit/docs/notion-recover.md)", readme_ko_text)
        self.assertIn("docs/notion-recover.md", kit_readme_text)
        self.assertIn("[Notion Recover](notion-recover.md)", public_map_text)
        self.assertIn("[Notion Recover](notion-recover.md)", public_map_ko_text)
        for phrase in (
            "# v0.3.138 - Notion Recover File-Ref Credential Handoff",
            "# v0.3.136 - Notion Recover One-Command Wrapper",
            "archive notion-recover",
            "file:<path>",
            "approval->fetch->merge-preview",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in release_text or phrase in changelog_text)

    def test_notion_connection_plan_docs_explain_one_click_contract_and_actionable_failures(self) -> None:
        text = NOTION_CONNECTION_PLAN_PATH.read_text(encoding="utf-8")
        recover_text = NOTION_RECOVER_PATH.read_text(encoding="utf-8")
        fetch_text = NOTION_ANCESTOR_FETCH_ADAPTER_RUN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.141.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.142 one-click Notion connection contract plus OAuth preflight checkpoint",
            "archive notion-connection-plan <archive-root> --dry-run --format json",
            "notion-connect-plan",
            "Connect Notion -> human approves once in browser",
            "Internal connections use a static installation token",
            "Personal access tokens are user-scoped static tokens",
            "Public connections use OAuth 2.0",
            "archive notion-oauth-connection-preflight",
            "notion_connection_not_shared_or_permission_denied",
            "browser OAuth authorization",
            "writes nothing, calls no provider, opens no browser",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Status: v0.3.141 beginner-friendly one-command local Notion location recovery with actionable failure classification",
            "Failure Categories",
            "notion_connection_not_shared_or_permission_denied",
            "notion-connection-plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, recover_text)
        for phrase in (
            "Status: v0.3.141 approval-gated local Notion ancestor structure fetch with actionable provider failure classification",
            "provider_permission_denied_connection_not_shared_raw_error_redacted",
            "provider_network_or_timeout_raw_error_redacted",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, fetch_text)
        for phrase in (
            "Status: v0.3.142 Notion OAuth connection preflight checkpoint",
            "Notion connection plan",
            "Notion OAuth connection preflight",
            "archive notion-connection-plan",
            "archive notion-connect-plan",
            "archive notion-oauth-connection-preflight",
            "notion_connection_not_shared_or_permission_denied",
            "Vault/keyring/OAuth one-click handoff remains planned",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        self.assertIn("[Notion Connection Plan](wom-kit/docs/notion-connection-plan.md)", readme_text)
        self.assertIn("[Notion Connection Plan](wom-kit/docs/notion-connection-plan.md)", readme_ko_text)
        self.assertIn("docs/notion-connection-plan.md", kit_readme_text)
        self.assertIn("[Notion Connection Plan](notion-connection-plan.md)", public_map_text)
        self.assertIn("[Notion Connection Plan](notion-connection-plan.md)", public_map_ko_text)
        for phrase in (
            "# v0.3.141 - Notion One-Click Connection Contract And Actionable Failures",
            "archive notion-connection-plan",
            "token_invalid_or_expired",
            "notion_connection_not_shared_or_permission_denied",
            "browser OAuth authorization",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in release_text or phrase in changelog_text)

    def test_notion_oauth_connection_preflight_docs_explain_secret_blind_local_runtime_boundary(self) -> None:
        preflight_text = NOTION_OAUTH_CONNECTION_PREFLIGHT_PATH.read_text(encoding="utf-8")
        connection_text = NOTION_CONNECTION_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.142.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.142 secret-blind Notion OAuth connection preflight checkpoint",
            "archive notion-oauth-connection-preflight <archive-root>",
            "notion-oauth-preflight",
            "notion-connect-oauth-preflight",
            "Connect Notion -> human approves once in browser -> trusted local runtime stores tokens",
            "the callback URI is local loopback HTTP only",
            "OAuth state is required for the future live flow",
            "the future access/refresh token store is keyring",
            "oauth_state_mismatch",
            "starts no callback server",
            "echoes no credential refs, redirect URI",
            "https://developers.notion.com/guides/get-started/authorization",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, preflight_text)
        for phrase in (
            "What v0.3.142 Adds",
            "archive notion-oauth-connection-preflight",
            "The current next command for local readiness",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, connection_text)
        for phrase in (
            "Status: v0.3.142 Notion OAuth connection preflight checkpoint",
            "Notion OAuth connection preflight",
            "archive notion-oauth-connection-preflight",
            "archive notion-oauth-preflight",
            "secret-blind local OAuth runtime contract",
            "rejecting plain env token storage",
            "writes nothing, calls no provider, opens no browser",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        self.assertIn("[Notion OAuth Connection Preflight](wom-kit/docs/notion-oauth-connection-preflight.md)", readme_text)
        self.assertIn("[Notion OAuth Connection Preflight](wom-kit/docs/notion-oauth-connection-preflight.md)", readme_ko_text)
        self.assertIn("docs/notion-oauth-connection-preflight.md", kit_readme_text)
        self.assertIn("[Notion OAuth Connection Preflight](notion-oauth-connection-preflight.md)", public_map_text)
        self.assertIn("[Notion OAuth Connection Preflight](notion-oauth-connection-preflight.md)", public_map_ko_text)
        for phrase in (
            "# v0.3.142 - Notion OAuth Connection Preflight",
            "archive notion-oauth-connection-preflight",
            "secret-blind local OAuth runtime contract",
            "OAuth token exchange",
            "No archive migration is required.",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in release_text or phrase in changelog_text)

    def test_notion_media_fetch_adapter_execution_contract_is_documented_as_closed_media_byte_boundary(self) -> None:
        fetch_text = NOTION_MEDIA_FETCH_ADAPTER_EXECUTION_CONTRACT_PATH.read_text(encoding="utf-8")
        verify_text = NOTION_MEDIA_RESULT_VERIFICATION_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        guide_text = (KIT_ROOT / "docs" / "ai-response-concept-guide.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.132.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.132 read-only future media byte fetch adapter contract checkpoint",
            "archive notion-media-fetch-adapter-execution-contract",
            "notion_media_fetch_adapter_execution_contract",
            "notion_media_result_fixture",
            "already_preserved",
            "newly_preserved",
            "fetch_failed",
            "download media bytes",
            "hash media bytes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, fetch_text)
        for phrase in (
            "Status: v0.3.132 read-only media result fixture verification checkpoint",
            "archive notion-media-result-verification-plan",
            "notion_media_result_verification_plan",
            "objects/manifests/files.jsonl",
            "object_id` / `sha256`",
            "download media bytes",
            "hash media bytes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, verify_text)
        for phrase in (
            "Status: v0.3.132 Notion media byte fetch contract checkpoint",
            "Notion media fetch adapter execution contract",
            "archive notion-media-fetch-adapter-execution-contract",
            "notion_media_fetch_adapter_execution_contract",
            "Notion media result verification plan",
            "archive notion-media-result-verification-plan",
            "notion_media_result_verification_plan",
            "downloads no media bytes",
            "hashes no bytes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.133 pre-release",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
                self.assertIn(phrase, readme_ko_text)
        for phrase in (
            "docs/notion-media-fetch-adapter-execution-contract.md",
            "docs/notion-media-result-verification-plan.md",
            "notion-media-fetch-adapter-execution-contract",
            "notion-media-result-verification-plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("notion-media-fetch-adapter-execution-contract", guide_text)
        self.assertIn("notion-media-result-verification-plan", guide_text)
        self.assertIn(
            "[Notion Media Fetch Adapter Execution Contract](notion-media-fetch-adapter-execution-contract.md)",
            public_map_text,
        )
        self.assertIn(
            "[Notion Media Result Verification Plan](notion-media-result-verification-plan.md)",
            public_map_text,
        )
        self.assertIn(
            "[Notion Media Fetch Adapter Execution Contract](notion-media-fetch-adapter-execution-contract.md)",
            public_map_ko_text,
        )
        self.assertIn(
            "[Notion Media Result Verification Plan](notion-media-result-verification-plan.md)",
            public_map_ko_text,
        )
        for phrase in (
            "# v0.3.132 - Notion Media Byte Fetch Contract",
            "notion_media_fetch_adapter_execution_contract",
            "notion_media_result_verification_plan",
            "fresh provider file refs",
            "media byte downloads",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in release_text or phrase in changelog_text)

    def test_notion_block_mirror_and_ancestor_merge_are_documented_as_local_recovery_loop(self) -> None:
        mirror_text = NOTION_BLOCK_MIRROR_TREE_FIXTURE_PLAN_PATH.read_text(encoding="utf-8")
        merge_text = NOTION_ANCESTOR_MERGE_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.126.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.126 read-only reviewed block-mirror fixture checkpoint",
            "archive notion-block-mirror-tree-fixture-plan",
            "notion_block_mirror_tree_fixture_plan",
            "nested_tree_fixture_preview",
            "nested_tree_plan_preview",
            "does not read page titles",
            "write a fixture",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, mirror_text)
        for phrase in (
            "Status: v0.3.126 read-only sanitized ancestor merge and replan checkpoint",
            "archive notion-ancestor-merge-plan",
            "notion_ancestor_merge_plan",
            "merged_tree_fixture_preview",
            "nested_tree_plan_after_merge",
            "does not call Notion",
            "write or merge fixture files",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, merge_text)
        for phrase in (
            "Status: v0.3.126 Notion local tree fixture and ancestor merge checkpoint",
            "Notion block mirror tree fixture plan",
            "Notion ancestor merge plan",
            "archive notion-block-mirror-tree-fixture-plan --mirror workbench/notion-block-mirror.sample.json --source notion --dry-run",
            "archive notion-ancestor-merge-plan --tree workbench/notion-nested-tree.sample.json --ancestors workbench/notion-ancestor-result.sample.json --source notion --dry-run",
            "notion_block_mirror_tree_fixture_plan",
            "notion_ancestor_merge_plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.133 pre-release",
            "builds nested tree fixture previews from reviewed block mirror metadata",
            "merges sanitized ancestor result nodes with immediate after-merge replanning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "v0.3.133 pre-release",
            "reviewed block mirror",
            "merge/replan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_ko_text)
        for phrase in (
            "docs/notion-block-mirror-tree-fixture-plan.md",
            "docs/notion-ancestor-merge-plan.md",
            "notion-block-mirror-tree-fixture-plan",
            "notion-ancestor-merge-plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[Notion Block Mirror Tree Fixture Plan](notion-block-mirror-tree-fixture-plan.md)", public_map_text)
        self.assertIn("[Notion Ancestor Merge Plan](notion-ancestor-merge-plan.md)", public_map_text)
        self.assertIn("[Notion Block Mirror Tree Fixture Plan](notion-block-mirror-tree-fixture-plan.md)", public_map_ko_text)
        self.assertIn("[Notion Ancestor Merge Plan](notion-ancestor-merge-plan.md)", public_map_ko_text)
        for phrase in (
            "# v0.3.126 - Notion Local Tree Fixture And Ancestor Merge",
            "notion_block_mirror_tree_fixture_plan",
            "notion_ancestor_merge_plan",
            "local and read-only",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in release_text or phrase in changelog_text)

    def test_notion_client_issue_verification_plan_is_documented_as_read_only_verdict_bundle(self) -> None:
        text = NOTION_CLIENT_ISSUE_VERIFICATION_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        guide_text = (KIT_ROOT / "docs" / "ai-response-concept-guide.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.127.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.127 read-only client issue verification checkpoint",
            "archive notion-client-issue-verification-plan",
            "notion_client_issue_verification_plan",
            "client_issue_reproduced_missing_ancestor_evidence_needed",
            "client_issue_verified_closed_by_sanitized_ancestor_merge",
            "no_missing_ancestor_issue_detected_in_sanitized_input",
            "does not call Notion",
            "write verification files",
            "write or merge fixture files",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Status: v0.3.127 Notion client issue verification checkpoint",
            "Notion client issue verification plan",
            "archive notion-client-issue-verification-plan --tree workbench/notion-nested-tree.sample.json --ancestors workbench/notion-ancestor-result.sample.json --source notion --dry-run",
            "client_issue_verified_closed_by_sanitized_ancestor_merge",
            "notion_client_issue_verification_plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.133 pre-release",
            "verifies client nested-tree issues from sanitized local fixture bundles",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "v0.3.133 pre-release",
            "클라이언트 nested-tree issue를 검증",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_ko_text)
        for phrase in (
            "docs/notion-client-issue-verification-plan.md",
            "notion-client-issue-verification-plan",
            "Verify a client Notion nested-tree issue",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("notion-client-issue-verification-plan", guide_text)
        self.assertIn("[Notion Client Issue Verification Plan](notion-client-issue-verification-plan.md)", public_map_text)
        self.assertIn("[Notion Client Issue Verification Plan](notion-client-issue-verification-plan.md)", public_map_ko_text)
        for phrase in (
            "# v0.3.127 - Notion Client Issue Verification Bundle",
            "notion_client_issue_verification_plan",
            "local fixture bundles",
            "no live Notion transport",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in release_text or phrase in changelog_text)

    def test_notion_client_fixture_request_plan_is_documented_as_read_only_request_package(self) -> None:
        text = NOTION_CLIENT_FIXTURE_REQUEST_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        guide_text = (KIT_ROOT / "docs" / "ai-response-concept-guide.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.128.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.128 read-only client fixture request checkpoint",
            "archive notion-client-fixture-request-plan",
            "notion_client_fixture_request_plan",
            "requested_next_fixture",
            "notion_ancestor_result_fixture",
            "redaction checklist",
            "does not send client messages",
            "write request files",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Status: v0.3.128 Notion client fixture request checkpoint",
            "Notion client fixture request plan",
            "archive notion-client-fixture-request-plan --source notion --dry-run",
            "notion_client_fixture_request_plan",
            "redaction rules",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.133 pre-release",
            "packages the minimal sanitized fixture request contract for client follow-up",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "v0.3.133 pre-release",
            "최소 sanitized fixture request contract",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_ko_text)
        for phrase in (
            "docs/notion-client-fixture-request-plan.md",
            "notion-client-fixture-request-plan",
            "Package the sanitized fixture request contract",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("notion-client-fixture-request-plan", guide_text)
        self.assertIn("[Notion Client Fixture Request Plan](notion-client-fixture-request-plan.md)", public_map_text)
        self.assertIn("[Notion Client Fixture Request Plan](notion-client-fixture-request-plan.md)", public_map_ko_text)
        for phrase in (
            "# v0.3.128 - Notion Client Fixture Request Package",
            "notion_client_fixture_request_plan",
            "minimal sanitized fixture request contract",
            "no client message sending",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in release_text or phrase in changelog_text)

    def test_zettel_edge_write_and_batch_are_documented_as_approval_gated_writers(self) -> None:
        text = ZETTEL_EDGE_WRITE_PATH.read_text(encoding="utf-8")
        batch_text = ZETTEL_EDGE_BATCH_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.99.md").read_text(encoding="utf-8")
        latest_release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.108.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.108 approval-gated zettel edge write and revert checkpoint",
            "archive revert-edge <archive-root>",
            "rollback-edge",
            "receipts/edges/reverts/*.zettel-edge-revert.json",
            "archive zettel-edge <archive-root>",
            "link-zettel-edge",
            "write-zettel-edge",
            "--approve",
            "--reviewed-by person:reviewer",
            "receipts/edges/*.zettel-edge.json",
            "single-edge safety gate",
            "MCP does not expose a write or revert tool",
            "echo zettel body text",
            "echo zettel titles",
            "[Zettel Edge Batch](zettel-edge-batch.md)",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        for phrase in (
            "Status: v0.3.108 approval-gated policy batch zettel edge write scale and rollback checkpoint",
            "archive zettel-edge-batch <archive-root>",
            "archive revert-batch <archive-root>",
            "--skip-existing",
            "bulk-zettel-edge",
            "batch-zettel-edge",
            "rollback-batch",
            "human_review_queue",
            "skipped_existing_edges",
            "archive-relative",
            "receipts/edges/batches/*.zettel-edge-batch.json",
            "receipts/edges/batches/reverts/*.zettel-edge-batch-revert.json",
            "preloads",
            "policy.auto_write_edge_types",
            "policy.minimum_confidence",
            "expose a matching MCP write tool",
            "Relationship To Connection Intelligence",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, batch_text)
        for phrase in (
            "Status: v0.3.108 edge batch scale and rollback checkpoint",
            "Zettel edge write",
            "archive zettel-edge --from-zettel <zet> --target <zet-or-objet> --edge-type <type> --dry-run|--approve",
            "archive zettel-edge-batch --plan <json> --dry-run|--approve [--skip-existing]",
            "archive revert-edge --receipt <edge-receipt> --dry-run|--approve",
            "archive revert-batch --receipt <batch-receipt> --dry-run|--approve",
            "receipts/edges/*.zettel-edge.json",
            "receipts/edges/batches/*.zettel-edge-batch.json",
            "receipts/edges/reverts/*.zettel-edge-revert.json",
            "receipts/edges/batches/reverts/",
            "preloads the manifest once",
            "preserve original write receipts",
            "human_review_queue",
            "skipped_existing_edges",
            "MCP exposes no write or revert tool",
            "echo no zettel body text",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.109 pre-release",
            "[Zettel Edge Write](wom-kit/docs/zettel-edge-write.md)",
            "[Zettel Edge Batch](wom-kit/docs/zettel-edge-batch.md)",
            "approval-gated single-edge zettel edge writes",
            "approval-gated policy batch zettel edge writes",
            "receipt-based `revert-edge` and `revert-batch`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/zettel-edge-write.md",
            "docs/zettel-edge-batch.md",
            "zettel-edge",
            "zettel-edge-batch",
            "revert-edge",
            "revert-batch",
            "Preview or approve one typed edge",
            "Preview or approve policy-gated typed edge batches",
            "Preview or approve removing one previously approved edge",
            "Preview or approve removing all edges listed",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        for phrase in (
            "[Zettel Edge Write](zettel-edge-write.md)",
            "[Zettel Edge Batch](zettel-edge-batch.md)",
            "v0.3.108 - Edge Batch Scale And Rollback",
            "v0.3.99 - Policy Batch Zettel Edge Write",
            "archive zettel-edge",
            "archive zettel-edge-batch",
            "MCP exposes no matching write tool",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    phrase in public_map_text
                    or phrase in public_map_ko_text
                    or phrase in release_text
                    or phrase in latest_release_text
                    or phrase in changelog_text
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
            "--mime-field mime",
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
                    "--mime-field mime",
                    "Older external records lack MIME values",
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
                    "--mime-field mime",
                    "falling back to `application/octet-stream`",
                    "recordMap / blocks JSON -> source/original objet",
                    "[Notion Page Snapshot Model](notion-page-snapshot-model.md)",
                ),
            ),
            (
                matrix_text,
                (
                    "Notion page snapshot model",
                    "optional safe MIME values through `--mime-field`",
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

    def test_ai_response_concept_guide_explains_hash_location_and_layer_boundaries(self) -> None:
        guide_text = AI_RESPONSE_CONCEPT_GUIDE_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")

        for phrase in (
            "Status: v0.3.104 read-only concept, operational terminology, and material-clue routing checkpoint",
            "archive ai-response-concept-guide <archive-root> --topic all --locale ko-KR --dry-run --format json",
            "ai-concept-guide",
            "wom-concept-guide",
            "sha256 identity vs location URL",
            "manifest vs zet",
            "objet -> derived text -> zet",
            "operational terminology translation layer",
            "material-clue routing after body locator omission",
            "derived_from",
            "supersedes",
            "WOM identifies source objets by content fingerprint",
            "The sha256 is the fingerprint. R2 or a local folder is only a shelf",
            "WOM은 \"지금 파일이 어디 폴더에 있나\"보다",
            "The manifest is like a catalog",
            "A safe `store_ref` is not the same as a verified",
            "Do not say:",
            "The manifest proves the remote file is definitely online.",
            "The AI must not say:",
            "notion-objet-import-clue-audit",
            "notion-objet-source-map-link-plan",
            "notion-objet-link-index",
            "notion-nested-tree-plan",
            "Upload/sync bytes: future work unless a later release explicitly adds",
            "[Source Object Storage Policy](source-object-storage-policy.md)",
            "[Text Provenance Hierarchy](text-provenance-hierarchy.md)",
            "[Notion Objet Import Clue Audit](notion-objet-import-clue-audit.md)",
            "[Notion Objet Source Map Link Plan](notion-objet-source-map-link-plan.md)",
            "[Notion Nested Tree Plan](notion-nested-tree-plan.md)",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide_text)

        for phrase in (
            "AI response concept guide",
            "sha256 object identity vs location",
            "operational terminology translation layer",
            "`read-only preview`",
            "CLI `archive ai-response-concept-guide --topic all --locale ko-KR --dry-run`",
            "`notion-objet-import-clue-audit`",
            "`notion-objet-source-map-link-plan`",
            "`notion-nested-tree-plan`",
            "writes nothing, adds no MCP tool, calls no providers",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)

        for phrase in (
            "read-only `archive ai-response-concept-guide --dry-run`",
            "sha256 object identity vs location",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)

        self.assertIn("[AI Response Concept Guide](ai-response-concept-guide.md)", public_map_text)
        self.assertIn("[AI 응대 개념 설명 가이드](ai-response-concept-guide.md)", public_map_ko_text)

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
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "Objet ref resolver",
            "archive resolve-objet-ref --object-id sha256:<hex> --dry-run",
            "MCP `resolve_objet_ref`",
            "do not decide deletion safety",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
            "[Presigned URL Plan](wom-kit/docs/presigned-url-plan.md)",
            "presigned URL planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Presigned URL Plan](presigned-url-plan.md)", public_map_text)

    def test_zettel_objet_links_doc_and_matrix_keep_read_only_boundaries(self) -> None:
        links_text = ZETTEL_OBJET_LINKS_PATH.read_text(encoding="utf-8")
        notion_plan_text = NOTION_OBJET_LINK_PLAN_PATH.read_text(encoding="utf-8")
        notion_index_text = NOTION_OBJET_LINK_INDEX_PATH.read_text(encoding="utf-8")
        notion_rewrite_text = NOTION_OBJET_LINK_REWRITE_PLAN_PATH.read_text(encoding="utf-8")
        notion_convert_text = NOTION_OBJET_LINK_CONVERT_PATH.read_text(encoding="utf-8")
        notion_label_text = NOTION_OBJET_MANIFEST_LOCATOR_LABEL_PATH.read_text(encoding="utf-8")
        notion_import_audit_text = NOTION_OBJET_IMPORT_CLUE_AUDIT_PATH.read_text(encoding="utf-8")
        notion_source_map_text = NOTION_OBJET_SOURCE_MAP_LINK_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.107.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
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
            "archive notion-objet-link-plan --dry-run",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, links_text)
        for phrase in (
            "Status: v0.3.89 read-only locator bridge",
            "archive notion-objet-link-plan",
            "notion_objet_link_plan",
            "locator_fingerprint",
            "suggested `objet:sha256:<hex>` ref",
            "provider URLs",
            "page titles",
            "Redacted zettels are blocked",
            "notion-objet-manifest-locator-label",
            "Approval-gated reviewed `embed` edge conversion now exists",
            "Body replacement remains future work",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, notion_plan_text)
        for phrase in (
            "Status: v0.3.96 read-only bulk locator index",
            "archive notion-objet-link-index",
            "notion_objet_link_index",
            "archive-wide counts",
            "locator rows with and without manifest candidates",
            "suggested `objet:sha256:<hex>` refs",
            "provider URLs",
            "zettel body text",
            "Redacted zettels are counted",
            "notion-objet-manifest-locator-label",
            "Approval-gated reviewed `embed` edge conversion now exists",
            "Body replacement remains future work",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, notion_index_text)
        for phrase in (
            "Status: v0.3.101 read-only conversion review checkpoint",
            "archive notion-objet-link-rewrite-plan",
            "notion_objet_link_rewrite_plan",
            "locator_fingerprint",
            "expected_occurrence_count",
            "objet_ref_rewrite",
            "embed_edge",
            "provider URLs",
            "page titles",
            "notion-objet-manifest-locator-label",
            "notion-objet-link-convert",
            "target_mode=embed_edge",
            "receipts without rewriting body text",
            "Body rewrite remains future work",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, notion_rewrite_text)
        for phrase in (
            "Status: v0.3.101 approval-gated embed edge conversion checkpoint",
            "archive notion-objet-link-convert",
            "--target-mode embed_edge",
            "--expected-occurrence-count",
            "--reviewed-by person:reviewer",
            "receipts/objects/notion-link-conversions/",
            "There is no MCP write tool",
            "does not rewrite zettel body text",
            "target_mode=objet_ref_rewrite",
            "needs a separate, narrower replacement guard",
            "notion-objet-link-rewrite-plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, notion_convert_text)
        for phrase in (
            "Status: v0.3.100 approval-gated manifest locator label write checkpoint",
            "archive notion-objet-manifest-locator-label",
            "notion-objet-locator-label",
            "provider_locator_sha256",
            "provider_locator_sha256_values",
            "receipts/objects/notion-locator-labels",
            "MCP exposes no write tool",
            "does not store or print the Notion URL",
            "notion-objet-link-index",
            "notion-objet-link-rewrite-plan",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, notion_label_text)
        for phrase in (
            "Status: v0.3.107 read-only scaled import material-clue audit",
            "archive notion-objet-import-clue-audit",
            "notion_objet_import_clue_audit",
            "preserved_object_ref_or_edge",
            "source_map_join_available",
            "missing_material_clue_after_locator_omission",
            "no_omission_signal_or_body_locator_path_needed",
            "large-manifest startup fix",
            "preloaded manifest index",
            "reads no zettel body text",
            "provider URLs",
            "frontmatter values",
            "source_locator_omitted_count",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, notion_import_audit_text)
        for phrase in (
            "Status: v0.3.107 read-only scaled source-map material-link planner",
            "archive notion-objet-source-map-link-plan",
            "notion_objet_source_map_link_plan",
            "source-maps/*.jsonl",
            "download/retrieval ledgers",
            "manifest once and reusing a local object-id index",
            "large-manifest optimization",
            "page -> file -> `sha256`",
            "target_mode=embed_edge",
            "body provider locators",
            "provider URLs",
            "page titles",
            "zettel body text",
            "Future import adapters should remove provider locators from zettel bodies",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, notion_source_map_text)
        for phrase in (
            "Zettel objet link preview",
            "archive zettel-objet-links --path <zet.md>|--zettel-id <id> --dry-run",
            "MCP `zettel_objet_links`",
            "echo no zettel body text or frontmatter values",
            "block redacted zettels",
            "Notion objet locator bridge",
            "archive notion-objet-link-plan --path <zet.md>|--zettel-id <id> --dry-run",
            "MCP `notion_objet_link_plan`",
            "archive notion-objet-link-index <archive-root> --dry-run",
            "MCP `notion_objet_link_index`",
            "Notion objet import material-clue audit",
            "archive notion-objet-import-clue-audit <archive-root> --source-map <archive-relative-jsonl> --ledger <archive-relative-jsonl> --dry-run",
            "MCP `notion_objet_import_clue_audit`",
            "missing_material_clue_after_locator_omission",
            "Notion objet source-map material bridge",
            "archive notion-objet-source-map-link-plan <archive-root> --source-map <archive-relative-jsonl> --ledger <archive-relative-jsonl> --dry-run",
            "MCP `notion_objet_source_map_link_plan`",
            "preloads the manifest once",
            "large manifests do not trigger per-object full manifest resolution",
            "body provider locators",
            "candidate_id",
            "human_review_required",
            "archive notion-objet-link-rewrite-plan --path <zet.md>|--zettel-id <id> --locator-fingerprint sha256:<hex> --object-id sha256:<hex> --dry-run",
            "MCP `notion_objet_link_rewrite_plan`",
            "archive notion-objet-manifest-locator-label --object-id sha256:<hex> --locator-fingerprint sha256:<hex> --dry-run|--approve",
            "receipts/objects/notion-locator-labels/*.notion-objet-manifest-locator-label.json",
            "archive notion-objet-link-convert --path <zet.md>|--zettel-id <id> --locator-fingerprint sha256:<hex> --object-id sha256:<hex> --target-mode embed_edge --expected-occurrence-count <n> --dry-run|--approve",
            "receipts/objects/notion-link-conversions/*.notion-objet-link-convert.json",
            "occurrence-count drift guard",
            "does not rewrite zettel body text",
            "provider URLs, provider locator text",
            "skip or block redacted zettel content",
            "MCP exposes no write tool for the manifest label or conversion surface",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "[Zettel Objet Links](wom-kit/docs/zettel-objet-links.md)",
            "[Notion Objet Link Plan](wom-kit/docs/notion-objet-link-plan.md)",
            "[Notion Objet Link Index](wom-kit/docs/notion-objet-link-index.md)",
            "[Notion Objet Import Clue Audit](wom-kit/docs/notion-objet-import-clue-audit.md)",
            "[Notion Objet Source Map Link Plan](wom-kit/docs/notion-objet-source-map-link-plan.md)",
            "[Notion Objet Link Rewrite Plan](wom-kit/docs/notion-objet-link-rewrite-plan.md)",
            "[Notion Objet Link Convert](wom-kit/docs/notion-objet-link-convert.md)",
            "[Notion Objet Manifest Locator Label](wom-kit/docs/notion-objet-manifest-locator-label.md)",
            "zettel objet link previews",
            "import material-clue auditing",
            "scaled source-map/ledger based Notion material-link planning",
            "approval-gated Notion objet manifest locator fingerprint labels",
            "approval-gated Notion locator conversion to reviewed `embed` edges",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "# v0.3.107 - Source Map Scale Fix",
            "large-manifest startup hang",
            "reuses a local object-id index",
            "19,055",
            "Both affected commands completed in seconds",
            "read-only",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)
        self.assertIn("[Zettel Objet Links](zettel-objet-links.md)", public_map_text)
        self.assertIn("[Notion Objet Link Plan](notion-objet-link-plan.md)", public_map_text)
        self.assertIn("[Notion Objet Link Index](notion-objet-link-index.md)", public_map_text)
        self.assertIn("[Notion Objet Import Clue Audit](notion-objet-import-clue-audit.md)", public_map_text)
        self.assertIn("[Notion Objet Import Clue Audit](notion-objet-import-clue-audit.md)", public_map_ko_text)
        self.assertIn("[Notion Objet Source Map Link Plan](notion-objet-source-map-link-plan.md)", public_map_text)
        self.assertIn("[Notion Objet Source Map Link Plan](notion-objet-source-map-link-plan.md)", public_map_ko_text)
        self.assertIn("[Notion Objet Link Rewrite Plan](notion-objet-link-rewrite-plan.md)", public_map_text)
        self.assertIn("[Notion Objet Link Convert](notion-objet-link-convert.md)", public_map_text)
        self.assertIn("[Notion Objet Manifest Locator Label](notion-objet-manifest-locator-label.md)", public_map_text)

    def test_view_health_doc_and_matrix_explain_empty_saved_view_diagnostics(self) -> None:
        view_health_text = VIEW_HEALTH_PATH.read_text(encoding="utf-8")
        view_recommendation_text = VIEW_RECOMMENDATION_PLAN_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.90 read-only saved view diagnostics",
            "Status: v0.3.93 read-only saved view and facet role diagnostics",
            "archive view-health <archive-root> --dry-run",
            "view_health",
            "active",
            "empty_result",
            "blocked",
            "observed facet value samples",
            "facet_role_summary",
            "facet_roles",
            "notion_status",
            "migration_batch",
            "unknown",
            "read zettel bodies",
            "echo zettel titles",
            "Relationship To `view-zets`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, view_health_text)
        for phrase in (
            "Status: v0.3.97 read-only saved view recommendation checkpoint",
            "archive view-recommendation-plan <archive-root> --dry-run",
            "view_recommendation_plan",
            "candidate single-facet saved views",
            "view.ai.<axis>.<value>",
            "facets.<key>",
            "write view files",
            "echo zettel titles",
            "Relationship To `view-health`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, view_recommendation_text)
        for phrase in (
            "Saved view health and recommendation",
            "archive view-health --dry-run",
            "MCP `view_health`",
            "archive view-recommendation-plan --dry-run",
            "MCP `view_recommendation_plan`",
            "observed facet distribution samples",
            "facet_role_summary",
            "safe recommendation filters",
            "navigation axes",
            "internal/import metadata",
            "echo no zettel titles",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "[View Health](wom-kit/docs/view-health.md)",
            "[View Recommendation Plan](wom-kit/docs/view-recommendation-plan.md)",
            "saved view health, facet role diagnostics, saved view recommendations",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[View Health](view-health.md)", public_map_text)
        self.assertIn("[View Recommendation Plan](view-recommendation-plan.md)", public_map_text)

    def test_index_health_doc_and_matrix_explain_generated_index_drift(self) -> None:
        index_health_text = INDEX_HEALTH_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.91 read-only generated index drift check",
            "archive index-health <archive-root> --dry-run",
            "index_health",
            "live_zettels_missing_from_index",
            "live_zettel_modified_after_index",
            "rebuild the index",
            "echo zettel body text",
            "echo zettel titles",
            "Relationship To `archive index`",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, index_health_text)
        for phrase in (
            "Generated index health",
            "archive index-health --dry-run",
            "MCP `index_health`",
            "modified after the index",
            "echo no zettel body text",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "[Index Health](wom-kit/docs/index-health.md)",
            "generated index health checks",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Index Health](index-health.md)", public_map_text)

    def test_derived_text_coverage_doc_and_matrix_expose_agent_contract(self) -> None:
        coverage_text = DERIVED_TEXT_COVERAGE_PATH.read_text(encoding="utf-8")
        derived_text = (KIT_ROOT / "docs" / "derived-text.md").read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.83 read-only coverage, manifest quality, toolchain doctor hints, and agent contract",
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
            "`manifest_quality`",
            "tool_version",
            "derived_text_manifest_quality_issues",
            "missing or weakening required provenance",
            "`textual_signal: derived_text_record_present`",
            "misleading `0/0` coverage reading",
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
            "They are coverage, manifest-quality, and routing gates.",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, coverage_text)
        self.assertIn("[Derived Text Coverage And Toolchain](derived-text-coverage-and-toolchain.md)", derived_text)
        self.assertIn("derived-text-capture-manifest-item.schema.json", derived_text)
        for phrase in (
            "Derived text coverage and toolchain",
            "archive derive-text coverage --dry-run",
            "existing derived-text records when older external manifests lack useful MIME",
            "`manifest_quality`",
            "false complete coverage claim",
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
            "v0.3.87 pre-release",
            "[Derived Text Coverage And Toolchain](wom-kit/docs/derived-text-coverage-and-toolchain.md)",
            "derived-text coverage/toolchain/doctor/agent-contract",
            "manifest-quality checks",
            "existing derived-text records as a fallback textual signal",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "Derived text completeness signal",
            "`derive-text coverage` now returns `completeness_signal`",
            "manifest-scoped derived-text coverage",
            "full external workspace/mailbox/cloud-drive mirror completion",
            "does not claim full external account coverage",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
            "[IMAP Mailbox Material Selection Plan](wom-kit/docs/imap-mailbox-material-selection-plan.md)",
            "read-only material selection, capture request, capture execution-contract planning, and material capture approval audits",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
            "[IMAP Mailbox Material Capture Request Plan](wom-kit/docs/imap-mailbox-material-capture-request-plan.md)",
            "read-only material selection, capture request, capture execution-contract planning, and material capture approval audits",
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

    def test_imap_mailbox_material_capture_execution_contract_doc_and_matrix_keep_material_reads_closed(self) -> None:
        contract_text = IMAP_MAILBOX_MATERIAL_CAPTURE_EXECUTION_CONTRACT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.70.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.70 read-only IMAP material capture execution contract checkpoint",
            "archive imap-mailbox-material-capture-execution-contract <archive-root>",
            "imap-material-capture-execution-contract",
            "mailbox-material-capture-execution-contract",
            "message_body_capture",
            "attachment_capture",
            "derived_text_capture",
            "It does not read the original IMAP header scan execution receipt.",
            "contract_ready_for_future_material_capture_implementation",
            "future_local_cli",
            "required future inputs",
            "reads message bodies",
            "reads attachment bytes",
            "creates derived text",
            "writes files",
            "echoes material selection receipt paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contract_text)
        for phrase in (
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "IMAP material capture execution contract",
            "archive imap-mailbox-material-capture-execution-contract --material-selection-receipt <path>",
            "contract_ready_for_future_material_capture_implementation",
            "future local-adapter inputs",
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
            "v0.3.87 pre-release",
            "[IMAP Mailbox Material Capture Execution Contract](wom-kit/docs/imap-mailbox-material-capture-execution-contract.md)",
            "read-only material selection, capture request, capture execution-contract planning, and material capture approval audits",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-material-capture-execution-contract.md",
            "imap-mailbox-material-capture-execution-contract",
            "Print the future execution contract for body, attachment, or derived-text capture",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("v0.3.70 - IMAP Material Capture Execution Contract", release_text)
        self.assertIn("read-only IMAP material capture execution contract checkpoint", release_text)
        self.assertIn("[IMAP Mailbox Material Capture Execution Contract](imap-mailbox-material-capture-execution-contract.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Material Capture Execution Contract](imap-mailbox-material-capture-execution-contract.md)", public_map_ko_text)

    def test_imap_mailbox_material_capture_approval_plan_doc_and_matrix_keep_material_reads_closed(self) -> None:
        approval_text = IMAP_MAILBOX_MATERIAL_CAPTURE_APPROVAL_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.71.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.71 approval-gated IMAP material capture approval receipt checkpoint",
            "archive imap-mailbox-material-capture-approval-plan <archive-root>",
            "imap-material-capture-approval-plan",
            "mailbox-material-capture-approval-plan",
            "imap-mailbox-material-capture-approval",
            "needs_review",
            "approve_once",
            "deny",
            "receipts/imap/material-capture-approvals/",
            "does not record the material selection receipt path",
            "reads message bodies",
            "reads attachment bytes",
            "creates derived text",
            "writes message material",
            "echoes material selection receipt paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, approval_text)
        for phrase in (
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "IMAP material capture approval plan",
            "archive imap-mailbox-material-capture-approval-plan --material-selection-receipt <path>",
            "approval-gated write",
            "receipts/imap/material-capture-approvals/*.json",
            "records a non-secret human decision receipt",
            "writes no material selection receipt path",
            "reads no headers/bodies/attachments",
            "creates no derived text",
            "echoes no material selection receipt path",
            "candidate refs",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
            "[IMAP Mailbox Material Capture Approval Plan](wom-kit/docs/imap-mailbox-material-capture-approval-plan.md)",
            "approval-gated material capture approval receipts",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-material-capture-approval-plan.md",
            "imap-mailbox-material-capture-approval-plan",
            "Preview or approve writing one non-secret material capture approval receipt",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("v0.3.71 - IMAP Material Capture Approval Receipt", release_text)
        self.assertIn("approval-gated IMAP material capture approval receipt checkpoint", release_text)
        self.assertIn("[IMAP Mailbox Material Capture Approval Plan](imap-mailbox-material-capture-approval-plan.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Material Capture Approval Plan](imap-mailbox-material-capture-approval-plan.md)", public_map_ko_text)

    def test_imap_mailbox_material_capture_approval_audit_doc_and_matrix_keep_material_reads_closed(self) -> None:
        audit_text = IMAP_MAILBOX_MATERIAL_CAPTURE_APPROVAL_AUDIT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.72.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.72 read-only IMAP material capture approval audit checkpoint",
            "archive imap-mailbox-material-capture-approval-audit <archive-root>",
            "imap-material-capture-approval-audit",
            "mailbox-material-capture-approval-audit",
            "approval_receipt_verified_for_future_material_capture",
            "future capture is authorized",
            "reads message bodies",
            "reads attachment bytes",
            "creates derived text",
            "writes files",
            "echoes approval receipt paths",
            "material selection receipt paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, audit_text)
        for phrase in (
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "IMAP material capture approval audit",
            "archive imap-mailbox-material-capture-approval-audit --material-selection-receipt <path>",
            "approval_receipt_verified_for_future_material_capture",
            "reads no original execution receipt",
            "reads no headers/bodies/attachments",
            "creates no derived text",
            "echoes no approval receipt path",
            "material selection receipt path",
            "candidate refs",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
            "[IMAP Mailbox Material Capture Approval Audit](wom-kit/docs/imap-mailbox-material-capture-approval-audit.md)",
            "material capture approval audits",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/imap-mailbox-material-capture-approval-audit.md",
            "imap-mailbox-material-capture-approval-audit",
            "Audit one non-secret material capture approval receipt",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("v0.3.72 - IMAP Material Capture Approval Audit", release_text)
        self.assertIn("read-only IMAP material capture approval audit checkpoint", release_text)
        self.assertIn("[IMAP Mailbox Material Capture Approval Audit](imap-mailbox-material-capture-approval-audit.md)", public_map_text)
        self.assertIn("[IMAP Mailbox Material Capture Approval Audit](imap-mailbox-material-capture-approval-audit.md)", public_map_ko_text)

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
            "v0.3.87 pre-release",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.113 read-only recommendation baseline with account recovery scenarios",
            "credential-store-recommendation",
            "credential-store-plan",
            "secret-store-recommendation",
            "credential_store_recommendation",
            "personal_local_first",
            "browser_or_platform_password_manager",
            "automation_or_dev_secrets",
            "local_app_adapter",
            "account_recovery_codes",
            "break_glass_secrets",
            "offline:physical-safe",
            "Minimum safe policy",
            "check for circular dependency",
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
            "account_recovery_codes",
            "break_glass_secrets",
            "at least two independent locations",
            "single digital copy",
            "circular dependency",
            "read no browser store",
            "future credential access broker boundaries",
            "without implementing secret retrieval",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
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
            "v0.3.87 pre-release",
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
            "Status: v0.3.138 beginner setup manual with Notion file-ref recovery credential guidance",
            "archive beginner-setup-manual",
            "archive notion-recover",
            "first-use-setup-manual",
            "setup-manual",
            "first_secret_and_text_tools",
            "credential_vault",
            "credential_bulk_migration",
            "derived_text_tools",
            "object_storage_setup_manual",
            "notion_nested_recovery",
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
            "folder, shelf, upper page, and item location",
            "ask Notion again for the missing location links",
            "file:<path>",
            "hidden local terminal prompt",
            "live vault/keyring one-click reads are still a future",
            "ask AI to tidy and merge the recovered locations",
            "The AI does not receive your Notion token.",
            "run Notion location fetches",
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
        self.assertIn("--topic notion_nested_recovery", matrix_text)
        self.assertIn("Notion nested recovery human-step guidance", matrix_text)
        self.assertIn("Notion recover", matrix_text)
        self.assertIn("archive notion-recover", matrix_text)
        self.assertIn("writes no approval receipts", matrix_text)
        self.assertIn("runs no Notion location fetches", matrix_text)
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
            "Status: v0.3.87 connection edge intelligence checkpoint",
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
            "v0.3.87 pre-release",
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
            "v0.3.87 pre-release",
            "[Object Storage Operation Request Plan](wom-kit/docs/object-storage-operation-request-plan.md)",
            "operation request packaging",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        self.assertIn("[Object Storage Operation Request Plan](object-storage-operation-request-plan.md)", public_map_text)
        self.assertIn("docs/object-storage-operation-request-plan.md", kit_readme_text)

    def test_object_storage_adapter_execution_contract_doc_and_matrix_keep_upload_closed(self) -> None:
        contract_text = OBJECT_STORAGE_ADAPTER_EXECUTION_CONTRACT_PATH.read_text(encoding="utf-8")
        readiness_text = OBJECT_STORAGE_ADAPTER_READINESS_PATH.read_text(encoding="utf-8")
        request_text = OBJECT_STORAGE_OPERATION_REQUEST_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.78.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.78 read-only upload execution-contract checkpoint",
            "archive object-storage-adapter-execution-contract <archive-root>",
            "object-storage-upload-execution-contract",
            "objet-storage-adapter-execution-contract",
            "object_storage_adapter_execution_contract",
            "sha256 content-addressed",
            "local object whose content SHA-256 matches",
            "provider HEAD/idempotency check",
            "bounded retry and resume ledger",
            "non-secret execution receipt",
            "update `objects/manifests/files.jsonl`",
            "ETag is not treated as the WOM SHA-256",
            "read object bytes",
            "hash local object bytes",
            "upload objects",
            "write resume ledgers",
            "write execution receipts",
            "update manifests",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, contract_text)
        self.assertIn("object-storage-adapter-execution-contract", readiness_text)
        self.assertIn("object-storage-adapter-execution-contract", request_text)
        for phrase in (
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "Object storage adapter execution contract",
            "archive object-storage-adapter-execution-contract --operation upload_object --dry-run",
            "archive object-storage-upload-execution-contract",
            "MCP `object_storage_adapter_execution_contract`",
            "sha256 content-addressed key shape",
            "bounded retry/resume ledger",
            "manifest update only after provider confirmation",
            "read no object bytes",
            "hash no object bytes",
            "upload nothing",
            "write no resume ledgers or receipts",
            "update no manifests",
            "echo no bucket names",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
            "[Object Storage Adapter Execution Contract](wom-kit/docs/object-storage-adapter-execution-contract.md)",
            "upload execution-contract planning",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/object-storage-adapter-execution-contract.md",
            "object-storage-adapter-execution-contract",
            "sha256 content-addressed keys",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[Object Storage Adapter Execution Contract](object-storage-adapter-execution-contract.md)", public_map_text)
        self.assertIn("[Object Storage Adapter Execution Contract](object-storage-adapter-execution-contract.md)", public_map_ko_text)
        for phrase in (
            "v0.3.78 - Object Storage Upload Execution Contract",
            "Status: v0.3.78 read-only object-storage upload execution-contract checkpoint",
            "This release still does not implement a live object-storage adapter.",
            "python -m pytest wom-kit\\tests\\test_cli.py -k object_storage_adapter_execution_contract",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)

    def test_object_storage_upload_evidence_doc_and_matrix_register_reviewed_external_uploads_only(self) -> None:
        evidence_text = OBJECT_STORAGE_UPLOAD_EVIDENCE_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.85.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.85 approval-gated upload evidence registration checkpoint",
            "archive object-storage-upload-evidence <archive-root>",
            "object-storage-external-upload-evidence",
            "objet-storage-upload-evidence",
            "No MCP write tool is exposed for this surface.",
            "Accepted success statuses",
            "uploaded",
            "verified",
            "declared_uploaded",
            "byte_verification_by_wom_kit",
            "provider_confirmation_by_wom_kit",
            "This command does not:",
            "compute local source-object hashes",
            "call provider APIs",
            "upload objects",
            "Client feedback #11",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, evidence_text)
        for phrase in (
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "Object storage upload evidence",
            "archive object-storage-upload-evidence --ledger <jsonl> --dry-run|--approve",
            "`approval-gated write`",
            "receipt and object-storage manifest locations",
            "declared_uploaded",
            "provider_confirmation_by_wom_kit: false",
            "MCP exposes no write tool for this surface",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
            "[Object Storage Upload Evidence](wom-kit/docs/object-storage-upload-evidence.md)",
            "approval-gated external upload evidence registration",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/object-storage-upload-evidence.md",
            "object-storage-upload-evidence",
            "reviewed external object-storage upload evidence",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[Object Storage Upload Evidence](object-storage-upload-evidence.md)", public_map_text)
        self.assertIn("[Object Storage Upload Evidence](object-storage-upload-evidence.md)", public_map_ko_text)
        for phrase in (
            "v0.3.85 - Object Storage Upload Evidence",
            "Status: v0.3.85 approval-gated object-storage upload evidence checkpoint",
            "does not implement a live object-storage upload adapter",
            "python -m pytest wom-kit\\tests\\test_cli.py -k object_storage_upload_evidence",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)

    def test_object_storage_upload_evidence_audit_doc_and_matrix_stay_read_only(self) -> None:
        audit_text = OBJECT_STORAGE_UPLOAD_EVIDENCE_AUDIT_PATH.read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.86.md").read_text(encoding="utf-8")
        for phrase in (
            "Status: v0.3.86 read-only upload evidence audit checkpoint",
            "archive object-storage-upload-evidence-audit <archive-root>",
            "object-storage-external-upload-evidence-audit",
            "objet-storage-upload-evidence-audit",
            "No MCP tool is exposed for this surface.",
            "Did WOM-kit record the reviewed external upload evidence consistently?",
            "availability: declared_uploaded",
            "byte_verification_by_wom_kit: false",
            "provider_confirmation_by_wom_kit: false",
            "The command does not print receipt paths, manifest paths, object ids, or",
            "This command does not:",
            "write audit receipts",
            "check remote availability",
            "The future live adapter still needs credential retrieval",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, audit_text)
        for phrase in (
            "Status: v0.3.87 connection edge intelligence checkpoint",
            "Object storage upload evidence audit",
            "archive object-storage-upload-evidence-audit --receipt <archive-relative-json> --dry-run",
            "`read-only preview`",
            "receipt/location count consistency",
            "writes nothing, calls no providers",
            "echoes no receipt path, manifest path, object ids, locations",
            "MCP exposes no tool for this surface",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
            "[Object Storage Upload Evidence Audit](wom-kit/docs/object-storage-upload-evidence-audit.md)",
            "read-only upload evidence auditing",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme_text)
        for phrase in (
            "docs/object-storage-upload-evidence-audit.md",
            "object-storage-upload-evidence-audit",
            "Audit one upload evidence receipt against objects/manifests/files.jsonl",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, kit_readme_text)
        self.assertIn("[Object Storage Upload Evidence Audit](object-storage-upload-evidence-audit.md)", public_map_text)
        self.assertIn("[Object Storage Upload Evidence Audit](object-storage-upload-evidence-audit.md)", public_map_ko_text)
        for phrase in (
            "v0.3.86 - Object Storage Upload Evidence Audit",
            "Status: v0.3.86 read-only object-storage upload evidence audit checkpoint",
            "This release remains read-only.",
            "python -m pytest wom-kit\\tests\\test_cli.py -k object_storage_upload_evidence_audit",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, release_text)

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
            "v0.3.87 pre-release",
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
            "Status: v0.3.113 read-only semantic extraction recipe with store-scenario routing",
            "credential-semantic-extraction-recipe",
            "credential-extraction-recipe",
            "secret-semantic-extraction-recipe",
            "multi_account_same_service",
            "sso_or_passkey_route",
            "wallet_seed_or_private_key_material",
            "recovery_codes -> account_recovery_codes",
            "wallet_seed_or_private_key_material -> break_glass_secrets",
            "independent offline redundancy",
            "circular-dependency",
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
            "routes `recovery_codes` toward `account_recovery_codes`",
            "break_glass_secrets",
            "returns no secret values to AI",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for phrase in (
            "v0.3.87 pre-release",
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
            "v0.3.87 pre-release",
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
            "v0.3.87 pre-release",
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
            "v0.3.87 pre-release",
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
            "v0.3.87 pre-release",
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
            "v0.3.87 pre-release",
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
            "v0.3.87 pre-release",
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
            "v0.3.87 pre-release",
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
            "v0.3.87 pre-release",
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

    def test_ai_start_here_docs_separate_quick_entry_from_full_doctor(self) -> None:
        start_here_text = (KIT_ROOT / "docs" / "ai-start-here.md").read_text(encoding="utf-8")
        progress_text = (KIT_ROOT / "docs" / "large-command-progress-and-output.md").read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.222.md").read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(encoding="utf-8")
        runtime_skill_text = (
            KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"
        ).read_text(encoding="utf-8")

        for phrase in (
            "Status: quick/default and explicit full-Doctor contract implemented in v0.3.222",
            "inspection.mode: quick",
            "inspection.doctor_summary.checked: false",
            "--full-doctor",
            "mint-receipts -> mint_receipts",
            "at most once per 30 seconds",
            "no credential store accessed",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, start_here_text)
        for phrase in (
            "same-count suppression and counted-unit/rate contract in v0.3.222",
            "stage elapsed time",
            "processed items per second",
            "stage/count for 30 seconds",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, progress_text)
        for phrase in (
            "Status: v0.3.222 fast AI start-here and honest progress checkpoint",
            "Previous checkpoint: Status: v0.3.221",
            "Default `inspection.mode: quick`",
            "`mint-receipts` explicitly counts mint receipt files",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (
            readme_text,
            readme_ko_text,
            kit_readme_text,
            upgrade_text,
            upgrade_ko_text,
            changelog_text,
            release_text,
            runtime_skill_text,
        ):
            with self.subTest(document="operator-surface"):
                self.assertIn("--full-doctor", text)
        self.assertIn("[AI Start-Here Quick And Full Inspection](ai-start-here.md)", public_map_text)
        self.assertIn("[AI 스타팅 메뉴얼 빠른 안내와 전체 검진](ai-start-here.md)", public_map_ko_text)

    def test_full_doctor_phase_docs_keep_shared_output_bounded(self) -> None:
        start_here_text = (KIT_ROOT / "docs" / "ai-start-here.md").read_text(encoding="utf-8")
        progress_text = (KIT_ROOT / "docs" / "large-command-progress-and-output.md").read_text(encoding="utf-8")
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.223.md").read_text(encoding="utf-8")
        runtime_skill_text = (
            KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"
        ).read_text(encoding="utf-8")

        for phrase in (
            "safe full-Doctor receipt phase and callback coalescing added in v0.3.223",
            "fixed safe",
            "edge_receipt_index",
            "before formatter/lock work",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, start_here_text)
        for phrase in (
            "phase and reporter coalescing in v0.3.223",
            "source_file_ref",
            "target_edge_evolution",
            "Path-bearing source text is never copied",
            "work is skipped",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, progress_text)
        for phrase in (
            "Status: v0.3.223 full-Doctor receipt phase and callback coalescing checkpoint",
            "Previous checkpoint: Status: v0.3.222",
            "nine fixed safe mint-receipt phases",
            "coalesced before the shared formatter/lock",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (
            kit_readme_text,
            upgrade_text,
            upgrade_ko_text,
            changelog_text,
            release_text,
            runtime_skill_text,
        ):
            with self.subTest(document="operator-surface"):
                self.assertIn("edge_receipt_index", text)

    def test_runtime_context_quick_and_no_repeat_handoff_docs_match_v03224(self) -> None:
        runtime_text = (
            KIT_ROOT / "docs" / "runtime-context-quick-and-full-inspection.md"
        ).read_text(encoding="utf-8")
        start_here_text = (KIT_ROOT / "docs" / "ai-start-here.md").read_text(encoding="utf-8")
        entrypoint_text = (KIT_ROOT / "docs" / "runtime-canonical-entrypoints.md").read_text(
            encoding="utf-8"
        )
        progress_text = (KIT_ROOT / "docs" / "large-command-progress-and-output.md").read_text(
            encoding="utf-8"
        )
        matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko_text = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        kit_readme_text = (KIT_ROOT / "README.md").read_text(encoding="utf-8")
        upgrade_text = (REPO_ROOT / "UPGRADE.md").read_text(encoding="utf-8")
        upgrade_ko_text = (REPO_ROOT / "UPGRADE.ko.md").read_text(encoding="utf-8")
        changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        release_text = (KIT_ROOT / "docs" / "releases" / "v0.3.224.md").read_text(encoding="utf-8")
        runtime_skill_text = (
            KIT_ROOT / "templates" / "ai-runtime" / "wom-archive" / "SKILL.md"
        ).read_text(encoding="utf-8")
        public_map_text = (KIT_ROOT / "docs" / "public-documentation-map.md").read_text(encoding="utf-8")
        public_map_ko_text = (KIT_ROOT / "docs" / "public-documentation-map.ko.md").read_text(
            encoding="utf-8"
        )

        for phrase in (
            "quick/default and explicit full-Doctor contract implemented in v0.3.224",
            "doctor_summary.checked: false",
            "full_doctor: true",
            "completed_commands",
            "next_commands",
            "remaining_ai_runtime_order",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, runtime_text)
        for phrase in (
            "no-repeat runtime-context handoff added in v0.3.224",
            "run_required: false",
            "does not copy that already",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, start_here_text)
        for phrase in (
            "Status: v0.3.240 quick handoff, scalable first-read diagnostics, chronological revision-audit, and exact-restore checkpoint",
            "Do not run both back-to-back",
            "canonical_entrypoints.next_commands",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, entrypoint_text)
        self.assertIn("explicit runtime-context full-Doctor", progress_text)
        self.assertIn(
            "archive runtime-context <archive-root> --full-doctor --progress --format json",
            progress_text,
        )
        for phrase in (
            "Status: v0.3.224 quick runtime-context and no-repeat AI handoff checkpoint",
            "Previous checkpoint: Status: v0.3.223",
            "MCP `full_doctor: true`",
            "completed, next-command, and remaining-runtime-order collections",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, matrix_text)
        for text in (
            readme_text,
            readme_ko_text,
            kit_readme_text,
            upgrade_text,
            upgrade_ko_text,
            changelog_text,
            release_text,
            runtime_skill_text,
        ):
            with self.subTest(document="operator-surface"):
                self.assertIn("next_commands", text)
        self.assertIn(
            "[Runtime Context Quick And Full Inspection](runtime-context-quick-and-full-inspection.md)",
            public_map_text,
        )
        self.assertIn(
            "[빠른 인수인계 문서와 전체 검진](runtime-context-quick-and-full-inspection.md)",
            public_map_ko_text,
        )


if __name__ == "__main__":
    unittest.main()
