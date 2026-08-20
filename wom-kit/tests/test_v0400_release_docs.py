from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import unittest

from wom_kit import __version__, archive_cli


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RESOURCE_ROOT = KIT / "src" / "wom_kit" / "_resources"
MANIFEST_PATH = RESOURCE_ROOT / "resource-manifest.json"
RELEASE_PATH = KIT / "docs" / "releases" / "v0.4.0.md"
PACKAGED_RELEASE_PATH = RESOURCE_ROOT / "release-notes" / "v0.4.0.md"

NEW_SCHEMAS = (
    "agent-instruction-policy-v0.1.schema.json",
    "approval-handoff-v0.1.schema.json",
    "approval-integrity-audit-result-v0.1.schema.json",
    "approval-integrity-overlay-entry-v0.1.schema.json",
    "duplicate-object-reconciliation-receipt-v0.1.schema.json",
    "exact-human-approval-link-receipt-v0.1.schema.json",
    "human-artifact-registry-v0.1.schema.json",
    "operation-exact-human-approval-v0.1.schema.json",
    "source-fidelity-draft-receipt-v0.2.schema.json",
    "source-fidelity-session-evidence-receipt-v0.1.schema.json",
)

CURRENT_SURFACES = (
    ROOT / "README.md",
    ROOT / "README.ko.md",
    ROOT / "UPGRADE.md",
    ROOT / "UPGRADE.ko.md",
    ROOT / "VERSIONING.md",
    KIT / "README.md",
    KIT / "cli" / "README.md",
    KIT / "docs" / "exact-human-approval-contract.md",
    KIT / "docs" / "runtime-canonical-entrypoints.md",
    KIT / "docs" / "capability-matrix.md",
    KIT / "docs" / "human-artifact-store-contract.md",
    RELEASE_PATH,
)


class V0400ReleaseDocsTests(unittest.TestCase):
    def test_version_sources_and_current_release_are_synchronized(self) -> None:
        self.assertEqual(__version__, "0.4.0")
        self.assertIn('version = "0.4.0"', (KIT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertIn(
            '__version__ = "0.4.0"',
            (KIT / "src" / "wom_kit" / "__init__.py").read_text(encoding="utf-8"),
        )
        self.assertIn(
            '__version__ = "0.4.0"',
            (ROOT / "wom_kit" / "__init__.py").read_text(encoding="utf-8"),
        )
        self.assertEqual(RELEASE_PATH.read_bytes(), PACKAGED_RELEASE_PATH.read_bytes())
        packaged_release_names = sorted(
            path.name for path in (RESOURCE_ROOT / "release-notes").glob("v*.md")
        )
        self.assertEqual(packaged_release_names, ["v0.4.0.md"])

    def test_manifest_has_exact_v0400_resource_set(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.4.0")
        self.assertEqual(manifest["file_count"], 156)
        self.assertEqual(len(manifest["files"]), 156)
        packaged = [row["packaged"] for row in manifest["files"]]
        self.assertEqual(len(packaged), len(set(packaged)))
        self.assertEqual(
            [path for path in packaged if path.startswith("release-notes/")],
            ["release-notes/v0.4.0.md"],
        )
        self.assertEqual(
            hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
            "b0442f0dd6d8606970f0e86cab3545896ac42167b837cca453982f25dc8df5d9",
        )

    def test_all_ten_new_public_schemas_are_packaged_byte_for_byte(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        packaged = {row["packaged"] for row in manifest["files"]}
        for name in NEW_SCHEMAS:
            with self.subTest(schema=name):
                source = KIT / "schemas" / name
                mirror = RESOURCE_ROOT / "schemas" / name
                self.assertTrue(source.is_file())
                self.assertEqual(source.read_bytes(), mirror.read_bytes())
                self.assertIn(f"schemas/{name}", packaged)

    def test_exact_human_contract_matches_started_claim_workflow(self) -> None:
        combined = " ".join(
            " ".join(path.read_text(encoding="utf-8").split())
            for path in (
                RELEASE_PATH,
                KIT / "docs" / "exact-human-approval-contract.md",
                KIT / "docs" / "runtime-canonical-entrypoints.md",
            )
        )
        for token in (
            "TaskDialog",
            "authenticated durable claim in started state",
            "writer",
            "workflow",
            "succeeded",
            "failed",
            "There is no separately issued",
            "There is no claim expiry",
            "Any non-success after the writer boundary",
            "ok: false",
            "approval_claim_reconciliation_required",
            "must not be retried automatically",
            "effect=created",
            "already_present_exact",
            "Comctl32 v6 activation context",
            "DllGetVersion",
            "exact_human_approval_activation_context_required",
            "https://learn.microsoft.com/en-us/windows/win32/api/commctrl/nf-commctrl-taskdialogindirect",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_compound_and_repair_executors_are_fixed_fail_closed(self) -> None:
        combined = " ".join(
            " ".join(path.read_text(encoding="utf-8").split())
            for path in CURRENT_SURFACES
        )
        for command in (
            "mint-zet-batch",
            "retire-draft-batch",
            "zettel-edge-batch",
            "revert-edge",
            "revert-batch",
            "zet-revision-write",
            "zet-revision-restore-write",
            "zettel-objet-link",
            "zettel-objet-link-revert",
            "notion-objet-link-convert",
            "relation-candidate",
            "activity-group-membership-write",
            "activity-group-membership-removal-write",
            "activity-group-membership-recover",
            "activity-group-membership-removal-recover",
            "zet-abstract-backfill-write",
            "zet-abstract-backfill-revert",
            "zet-abstract-backfill-recover",
            "zet-title-remap-write",
            "zet-title-remap-revert",
            "zet-title-remap-recover",
            "zet-title-remap-revert-recover",
            "discard-draft",
            "discard-draft-restore",
            "remint-reconcile",
            "retire-draft-reconcile",
        ):
            with self.subTest(command=command):
                self.assertIn(command, combined)
        self.assertIn("compound_exact_human_approval_binding_required", combined)
        self.assertIn("before private target read or mutation", combined)

    def test_all_seventy_nine_cli_fixed_close_commands_are_published_exactly(self) -> None:
        blocked = archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS
        self.assertEqual(len(blocked), 79)

        release = RELEASE_PATH.read_text(encoding="utf-8")
        self.assertIn("exactly 79 top-level", release)
        for command in sorted(blocked):
            with self.subTest(command=command):
                self.assertIn(f"\n{command}\n", release)

        parser = archive_cli.build_parser()
        subcommands = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        for command in sorted(blocked):
            with self.subTest(help=command):
                actions = [
                    action
                    for action in subcommands.choices[command]._actions
                    if "--approve" in action.option_strings
                ]
                self.assertEqual(len(actions), 1)
                self.assertEqual(
                    actions[0].help,
                    archive_cli.COMPOUND_APPROVAL_BLOCKED_HELP,
                )

        release_folded = " ".join(RELEASE_PATH.read_text(encoding="utf-8").split())
        for token in (
            "Four fixed-close surfaces",
            "derive-text capture",
            "create-draft",
            "CLI and MCP `init`",
            "`parcel`, with compatibility alias `pack`",
            "legacy_unbound",
            "future_operation_authorized",
            "would_allow_future_adapter_after_receipt",
            "future_capture_authorized",
            "remain `false`",
        ):
            with self.subTest(token=token):
                self.assertIn(token, release_folded)

    def test_letter138_typed_property_recovery_is_explicitly_out_of_scope(self) -> None:
        combined = " ".join(
            " ".join(path.read_text(encoding="utf-8").split())
            for path in (
                RELEASE_PATH,
                ROOT / "UPGRADE.md",
                KIT / "README.md",
                KIT / "docs" / "capability-matrix.md",
            )
        )
        for token in (
            "Letter 138",
            "not part of v0.4.0",
            "typed-property loss",
            "page bodies or locations",
            "not a complete source mirror",
            "read-only loss audit",
            "exact-approved backfill",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_human_artifact_root_kinds_and_closeout_boundary_are_exact(self) -> None:
        contract = " ".join(
            (KIT / "docs" / "human-artifact-store-contract.md")
            .read_text(encoding="utf-8")
            .split()
        )
        for token in (
            "external_project",
            "<registered-root>/.wom-scratch",
            "external_delivery",
            "registered root itself (`.`)",
            "--project-root",
            "--external-root",
            "--root-kind",
            "never auto-discovers Downloads or a home directory",
            "closeout authority",
            "bounded metadata-only",
        ):
            with self.subTest(token=token):
                self.assertIn(token, contract)

    def test_public_release_claims_remain_evidence_bounded_and_private(self) -> None:
        release = RELEASE_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "C:\\Users\\",
            "archive:personal:",
            "Bearer ",
            "secret_",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, release)
        folded = release.casefold()
        for boundary in (
            "do not prove merge",
            "external ci",
            "github release publication",
            "fresh installation",
            "live provider behavior",
        ):
            with self.subTest(boundary=boundary):
                self.assertIn(boundary, folded)


if __name__ == "__main__":
    unittest.main()
