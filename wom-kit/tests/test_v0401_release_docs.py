from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from wom_kit import __version__, archive_cli, command_status


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RESOURCE_ROOT = KIT / "src" / "wom_kit" / "_resources"
MANIFEST_PATH = RESOURCE_ROOT / "resource-manifest.json"
RELEASE_PATH = KIT / "docs" / "releases" / "v0.4.1.md"
PACKAGED_RELEASE_PATH = RESOURCE_ROOT / "release-notes" / "v0.4.1.md"
HISTORICAL_V0400_RELEASE = KIT / "docs" / "releases" / "v0.4.0.md"
OPERATOR_CONTRACT = (
    KIT
    / "templates"
    / "ai-runtime"
    / "wom-archive"
    / "references"
    / "operator-contract.md"
)
CAPTURE_GUIDANCE = OPERATOR_CONTRACT.with_name(
    "capture-draft-and-publication.md"
)
PACKAGED_OPERATOR_CONTRACT = (
    RESOURCE_ROOT
    / "templates"
    / "ai-runtime"
    / "wom-archive"
    / "references"
    / "operator-contract.md"
)
PACKAGED_CAPTURE_GUIDANCE = PACKAGED_OPERATOR_CONTRACT.with_name(
    "capture-draft-and-publication.md"
)
WHEEL_URL = (
    "https://github.com/mow-coding/zettel-kasten/releases/download/"
    "v0.4.1/wom_kit-0.4.1-py3-none-any.whl"
)
NEW_SCHEMAS = (
    "cli-error-v0.1.schema.json",
    "command-approval-status-inventory-v0.1.schema.json",
)
CHANGED_SCHEMAS = (
    "operation-exact-human-approval-v0.1.schema.json",
    "zettel-objet-link-receipt.schema.json",
)


class V0401ReleaseDocsTests(unittest.TestCase):
    def test_historical_release_source_is_preserved_byte_for_byte(self) -> None:
        self.assertEqual(
            hashlib.sha256(RELEASE_PATH.read_bytes()).hexdigest(),
            "a5d3f506d93877768ecb9368e01a6e1581daa131287b392d6522a136f0d42704",
        )

    def test_current_public_resources_remain_exactly_packaged(self) -> None:
        self.assertFalse(PACKAGED_RELEASE_PATH.exists())
        release_names = sorted(
            path.name
            for path in (RESOURCE_ROOT / "release-notes").glob("v*.md")
        )
        self.assertEqual(release_names, [f"v{__version__}.md"])

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], __version__)
        self.assertEqual(manifest["file_count"], len(manifest["files"]))
        packaged_paths = [row["packaged"] for row in manifest["files"]]
        self.assertEqual(len(packaged_paths), len(set(packaged_paths)))
        self.assertIn(f"release-notes/v{__version__}.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.1.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.0.md", packaged_paths)
        for row in manifest["files"]:
            with self.subTest(packaged=row["packaged"]):
                source = KIT / row["source"]
                packaged = RESOURCE_ROOT / row["packaged"]
                self.assertTrue(source.is_file())
                self.assertTrue(packaged.is_file())
                self.assertEqual(source.read_bytes(), packaged.read_bytes())
                self.assertEqual(row["bytes"], len(source.read_bytes()))
                self.assertEqual(
                    row["sha256"],
                    hashlib.sha256(source.read_bytes()).hexdigest(),
                )

    def test_new_and_changed_schemas_are_valid_and_byte_identical(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        packaged_paths = {row["packaged"] for row in manifest["files"]}
        for name in (*NEW_SCHEMAS, *CHANGED_SCHEMAS):
            with self.subTest(schema=name):
                source = KIT / "schemas" / name
                packaged = RESOURCE_ROOT / "schemas" / name
                schema = json.loads(source.read_text(encoding="utf-8"))
                Draft202012Validator.check_schema(schema)
                self.assertEqual(source.read_bytes(), packaged.read_bytes())
                self.assertIn(f"schemas/{name}", packaged_paths)

    def test_current_parser_combines_all_released_writers(self) -> None:
        blocked = archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS
        self.assertEqual(len(blocked), 67)
        self.assertNotIn("migrate", blocked)
        self.assertNotIn("zettel-objet-link", blocked)
        self.assertIn("zettel-objet-link-revert", blocked)
        self.assertNotIn("project-version-update", blocked)
        self.assertNotIn("object-storage-adopt-existing", blocked)
        self.assertNotIn("object-storage", blocked)
        self.assertNotIn("objet-capture", blocked)
        self.assertNotIn("objet-capture-selection", blocked)
        self.assertNotIn("source-intake-record", blocked)
        self.assertNotIn("source-intake-batch", blocked)
        self.assertNotIn("objet-capture-batch", blocked)
        self.assertNotIn("revert-edge", blocked)
        self.assertIn("derive-text capture", blocked)
        self.assertIn("zet-revision-restore-proposal-from-snapshot", blocked)

        inventory = command_status.build_command_status_inventory(
            archive_cli.build_parser(),
            blocked,
        )
        counts = inventory["counts"]
        self.assertEqual(counts["canonical_executable_command_count"], 315)
        self.assertEqual(counts["alias_invocation_path_count"], 259)
        self.assertEqual(counts["invocation_path_count"], 574)
        self.assertEqual(counts["approval_available_command_count"], 47)
        self.assertEqual(counts["approval_fixed_closed_command_count"], 67)
        self.assertEqual(counts["approval_not_exposed_command_count"], 201)
        self.assertEqual(counts["conditional_approval_command_count"], 9)
        self.assertEqual(counts["dry_run_exposed_command_count"], 271)
        self.assertEqual(counts["unmatched_fixed_closed_command_count"], 0)
        by_path = {
            row["canonical_path"]: row for row in inventory["commands"]
        }
        self.assertEqual(
            by_path["zettel-objet-link"]["approval_status"],
            "approval_available",
        )
        self.assertEqual(
            by_path["git-backup-reconcile-plan"]["approval_status"],
            "approval_available",
        )
        self.assertEqual(
            by_path["zettel-objet-link-revert"]["approval_status"],
            "approval_fixed_closed",
        )
        self.assertEqual(
            by_path["derive-text capture"]["approval_status"],
            "approval_fixed_closed",
        )
        self.assertEqual(
            by_path["zet-revision-restore-proposal-from-snapshot"]["approval_status"],
            "approval_fixed_closed",
        )
        self.assertEqual(
            by_path["project-version-update"]["approval_status"],
            "approval_available",
        )
        self.assertEqual(
            by_path["source-intake-record"]["approval_status"],
            "approval_available",
        )
        self.assertEqual(
            by_path["source-intake-batch"]["approval_status"],
            "approval_available",
        )
        self.assertEqual(
            by_path["objet-capture-batch"]["approval_status"],
            "approval_available",
        )
        self.assertEqual(
            by_path["objet-capture"]["approval_scope"]["allowed_flags"],
            ["--exact-local"],
        )
        self.assertEqual(
            by_path["revert-edge"]["approval_scope"]["allowed_flags"],
            ["--exact-local"],
        )
        self.assertEqual(
            by_path["objet-capture-selection"]["approval_scope"]["allowed_flags"],
            ["--exact-existing-intake"],
        )
        self.assertEqual(
            by_path["relation-candidate-decide"]["approval_scope"]["allowed_values"],
            ["reject"],
        )
        self.assertEqual(
            by_path["migrate"]["approval_status"],
            "approval_available",
        )
        self.assertEqual(
            by_path["migrate"]["approval_scope"],
            {
                "kind": "argument_value_allowlist",
                "argument": "--target",
                "allowed_values": ["notion-source-properties"],
                "outside_scope_status": "approval_fixed_closed",
                "outside_scope_reason_code": (
                    "compound_exact_human_approval_binding_required"
                ),
            },
        )

    def test_public_docs_separate_global_bootstrap_from_project_update(self) -> None:
        current_surfaces = (
            ROOT / "README.md",
            ROOT / "README.ko.md",
            ROOT / "UPGRADE.md",
            ROOT / "UPGRADE.ko.md",
            ROOT / "VERSIONING.md",
            KIT / "README.md",
            KIT / "docs" / "python-tool-install.md",
            KIT / "docs" / "python-tool-install.ko.md",
            KIT / "docs" / "project-version-update.md",
            KIT / "docs" / "runtime-canonical-entrypoints.md",
            KIT / "docs" / "zettel-objet-links.md",
            KIT / "docs" / "agent-operator-capabilities.md",
            KIT / "docs" / "capability-matrix.md",
            RELEASE_PATH,
        )
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in current_surfaces
        )
        for token in (
            WHEEL_URL,
            "zettel-objet-link",
            "zettel-objet-link-revert",
            "project-version-update",
            "78",
            "79",
            "wom-kit/cli-error/v0.1",
            "wom-kit/command-approval-status-inventory/v0.1",
            "effects_state",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)
        self.assertNotIn(f'uv tool install --force "{WHEEL_URL}"', combined)
        self.assertIn("global CLI", combined)
        self.assertIn("project-local", combined)
        self.assertIn("fixed closed", combined)

    def test_active_operator_guidance_matches_v0401_link_authority(self) -> None:
        operator = OPERATOR_CONTRACT.read_text(encoding="utf-8")
        capture = CAPTURE_GUIDANCE.read_text(encoding="utf-8")
        version_truth = (KIT / "docs" / "version-truth-source.md").read_text(
            encoding="utf-8"
        )
        runtime_layer = (
            KIT / "docs" / "wom-ai-runtime-skill-plugin-layer.md"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            OPERATOR_CONTRACT.read_bytes(),
            PACKAGED_OPERATOR_CONTRACT.read_bytes(),
        )
        self.assertEqual(
            CAPTURE_GUIDANCE.read_bytes(),
            PACKAGED_CAPTURE_GUIDANCE.read_bytes(),
        )
        for text in (operator, capture):
            self.assertIn("v0.4.1", text)
            self.assertIn("zettel-objet-link", text)
            self.assertIn("revert", text)
            self.assertIn("fixed closed", text)
        self.assertIn("native exact-human", operator)
        self.assertIn("exact-human-approved replay", capture)
        self.assertNotIn(
            "In v0.4.0 both link and revert approval branches fail",
            operator,
        )
        self.assertNotIn(
            "Use `zettel-objet-link-revert` for exact-byte recovery",
            capture,
        )
        self.assertIn(f"Current checkpoint: Status: v{__version__}", version_truth)
        self.assertIn("exactly 78", runtime_layer)
        self.assertIn("single link apply", runtime_layer)
        self.assertIn("zettel-objet-link-revert` remains preview-only", runtime_layer)

    def test_historical_v0400_release_remains_immutable(self) -> None:
        self.assertEqual(
            hashlib.sha256(HISTORICAL_V0400_RELEASE.read_bytes()).hexdigest(),
            "511f86ee2ca48b84916d719974445e4e7f58272ed654a50d21722e28a2478579",
        )
        historical = HISTORICAL_V0400_RELEASE.read_text(encoding="utf-8")
        self.assertIn("exactly 79 top-level", historical)
        self.assertIn("\nzettel-objet-link\n", historical)
        self.assertIn("\nzettel-objet-link-revert\n", historical)

    def test_release_note_uses_github_release_safe_links(self) -> None:
        release = RELEASE_PATH.read_text(encoding="utf-8")
        for url in (
            "https://github.com/mow-coding/zettel-kasten/blob/main/"
            "wom-kit/docs/python-tool-install.md",
            "https://github.com/mow-coding/zettel-kasten/blob/main/UPGRADE.md",
            "https://github.com/mow-coding/zettel-kasten/blob/main/"
            "wom-kit/docs/project-version-update.md",
        ):
            self.assertIn(url, release)
        self.assertNotIn("](../", release)
        self.assertNotIn("](../../../", release)

    def test_current_link_docs_record_duplicate_and_windows_data_safety(self) -> None:
        release = RELEASE_PATH.read_text(encoding="utf-8")
        link_docs = (KIT / "docs" / "zettel-objet-links.md").read_text(
            encoding="utf-8"
        )
        for text in (release, link_docs):
            with self.subTest(surface="release" if text is release else "link"):
                normalized = " ".join(text.split())
                for token in (
                    "zettels/",
                    "inbox/",
                    "duplicate-id",
                    "duplicate-key",
                    "BackupRead",
                    "ReadDirectoryChangesW",
                    "CancelIoEx",
                    "GetOverlappedResult",
                    "closing guard",
                    "stable namespace snapshot",
                    "FileDispositionInfoEx",
                    "FILE_DISPOSITION_POSIX_SEMANTICS",
                    "FILE_DISPOSITION_IGNORE_READONLY_ATTRIBUTE",
                ):
                    self.assertIn(token, normalized)
                self.assertIn("never falls back", normalized)

    def test_release_note_states_upgrade_and_schema_impact(self) -> None:
        release = RELEASE_PATH.read_text(encoding="utf-8")
        for token in (
            "## Upgrade impact",
            "v0.4.0 beta testers",
            "No archive migration is required",
            "Zettel rules are unchanged",
            "Existing v0.1 link receipts remain readable",
            "new successful applies emit v0.2",
            "cli-error-v0.1.schema.json",
            "command-approval-status-inventory-v0.1.schema.json",
            "operation-exact-human-approval-v0.1.schema.json",
            "zettel-objet-link-receipt.schema.json",
        ):
            with self.subTest(token=token):
                self.assertIn(token, release)


if __name__ == "__main__":
    unittest.main()
