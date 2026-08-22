from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import unittest

from wom_kit import __version__, archive_cli, command_status


ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "wom-kit"
RESOURCE_ROOT = KIT / "src" / "wom_kit" / "_resources"
MANIFEST_PATH = RESOURCE_ROOT / "resource-manifest.json"
RELEASE_PATH = KIT / "docs" / "releases" / "v0.4.2.md"
PACKAGED_RELEASE_PATH = RESOURCE_ROOT / "release-notes" / "v0.4.2.md"
HISTORICAL_V0401_RELEASE = KIT / "docs" / "releases" / "v0.4.1.md"
PLAN_GUIDE = KIT / "docs" / "git-backup-plan.md"
DECISION_PATH = (
    KIT
    / "docs"
    / "archive-infra-decision-log-2026-08-21-v042-letter139-read-only-git-backup-planning.md"
)
WHEEL_URL = (
    "https://github.com/mow-coding/zettel-kasten/releases/download/"
    "v0.4.2/wom_kit-0.4.2-py3-none-any.whl"
)


class V0402ReleaseDocsTests(unittest.TestCase):
    def test_version_sources_and_wheel_contract_are_synchronized(self) -> None:
        self.assertEqual(__version__, "0.4.2")
        self.assertIn(
            'version = "0.4.2"',
            (KIT / "pyproject.toml").read_text(encoding="utf-8"),
        )
        for version_file in (
            KIT / "src" / "wom_kit" / "__init__.py",
            ROOT / "wom_kit" / "__init__.py",
        ):
            with self.subTest(version_file=version_file):
                self.assertIn(
                    '__version__ = "0.4.2"',
                    version_file.read_text(encoding="utf-8"),
                )
        self.assertIn(
            'PACKAGE_VERSION = "0.4.2"',
            (KIT / "tests" / "test_wheel_install.py").read_text(encoding="utf-8"),
        )

    def test_current_release_and_public_resources_are_exactly_packaged(self) -> None:
        self.assertEqual(RELEASE_PATH.read_bytes(), PACKAGED_RELEASE_PATH.read_bytes())
        self.assertEqual(
            sorted(
                path.name
                for path in (RESOURCE_ROOT / "release-notes").glob("v*.md")
            ),
            ["v0.4.2.md"],
        )

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.4.2")
        self.assertEqual(manifest["file_count"], len(manifest["files"]))
        packaged_paths = [row["packaged"] for row in manifest["files"]]
        self.assertEqual(len(packaged_paths), len(set(packaged_paths)))
        self.assertIn("release-notes/v0.4.2.md", packaged_paths)
        self.assertNotIn("release-notes/v0.4.1.md", packaged_paths)
        for row in manifest["files"]:
            with self.subTest(packaged=row["packaged"]):
                source = KIT / row["source"]
                packaged = RESOURCE_ROOT / row["packaged"]
                source_bytes = source.read_bytes()
                self.assertEqual(source_bytes, packaged.read_bytes())
                self.assertEqual(row["bytes"], len(source_bytes))
                self.assertEqual(row["sha256"], hashlib.sha256(source_bytes).hexdigest())

    def test_plan_stays_read_only_and_reconcile_family_hosts_exact_writer(self) -> None:
        parser = archive_cli.build_parser()
        subcommands = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        for command in ("git-backup-plan", "git-backup-reconcile-plan"):
            with self.subTest(command=command):
                command_parser = subcommands.choices[command]
                options = {
                    option
                    for action in command_parser._actions
                    for option in action.option_strings
                }
                self.assertIn("--dry-run", options)
                if command == "git-backup-plan":
                    self.assertNotIn("--approve", options)
                else:
                    self.assertIn("--approve", options)
                    self.assertIn("--selection-manifest", options)
                    self.assertIn("--resume-approval-id", options)

        mcp_source = (KIT / "src" / "wom_kit" / "mcp_server.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('"git-backup-plan"', mcp_source)
        self.assertNotIn('"git-backup-reconcile-plan"', mcp_source)

        historical_blocked = frozenset(
            {*archive_cli.COMPOUND_APPROVAL_BLOCKED_COMMANDS, "migrate"}
        )
        counts = command_status.build_command_status_inventory(
            parser,
            historical_blocked,
        )["counts"]
        self.assertEqual(counts["canonical_executable_command_count"], 315)
        self.assertEqual(counts["alias_invocation_path_count"], 259)
        self.assertEqual(counts["invocation_path_count"], 574)
        self.assertEqual(counts["approval_available_command_count"], 37)
        self.assertEqual(counts["approval_fixed_closed_command_count"], 77)
        self.assertEqual(counts["approval_not_exposed_command_count"], 201)
        self.assertEqual(counts["dry_run_exposed_command_count"], 270)

    def test_public_contract_is_narrow_and_letter139_remains_partial(self) -> None:
        public_map = KIT / "docs" / "public-documentation-map.md"
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                RELEASE_PATH,
                PLAN_GUIDE,
                DECISION_PATH,
                ROOT / "README.md",
                ROOT / "README.ko.md",
                ROOT / "UPGRADE.md",
                ROOT / "UPGRADE.ko.md",
                KIT / "README.md",
                public_map,
            )
        )
        for token in (
            WHEEL_URL,
            "git-backup-plan",
            "git-backup-reconcile-plan",
            "ready_for_write",
            "writer_available",
            "anonymous HTTPS",
            "provider",
            "Letter 139",
        ):
            with self.subTest(token=token):
                self.assertIn(token, combined)
        for path in (RELEASE_PATH, DECISION_PATH):
            normalized = " ".join(path.read_text(encoding="utf-8").split()).lower()
            with self.subTest(path=path):
                self.assertIn("read-only", normalized)
                self.assertIn("writer", normalized)
                self.assertTrue(
                    "incomplete" in normalized
                    or "partial response" in normalized
                    or "only the read-only" in normalized
                )
        current_guide = " ".join(PLAN_GUIDE.read_text(encoding="utf-8").split()).lower()
        for token in (
            "private exact selection",
            "git add -- <paths>",
            "non-force push",
            "resume",
            "24 kib",
        ):
            self.assertIn(token, current_guide)

        public_map_text = public_map.read_text(encoding="utf-8")
        self.assertIn("git-backup-plan.md", public_map_text)
        self.assertIn(DECISION_PATH.name, public_map_text)
        self.assertIn("releases/v0.4.2.md", public_map_text)

        for path in (RELEASE_PATH, PLAN_GUIDE):
            text = path.read_text(encoding="utf-8")
            with self.subTest(attributes_boundary=path):
                self.assertIn(".gitattributes", text)
                self.assertIn("do not delete or disable", text.casefold())
                self.assertIn("future work", text.casefold())

    def test_v0401_release_remains_immutable(self) -> None:
        self.assertEqual(
            hashlib.sha256(HISTORICAL_V0401_RELEASE.read_bytes()).hexdigest(),
            "a5d3f506d93877768ecb9368e01a6e1581daa131287b392d6522a136f0d42704",
        )

    def test_release_documents_the_index_bound_content_free_privacy_gate(self) -> None:
        release = " ".join(RELEASE_PATH.read_text(encoding="utf-8").split())
        for token in (
            "exact regular file blobs staged in the Git index",
            "regardless of filename extension",
            "staged secret",
            "changing-index",
            "only fixed codes, safe relative paths, types, and counts",
            "never print a matched token",
            "not proof that every possible secret format is absent",
        ):
            with self.subTest(token=token):
                self.assertIn(token, release)


if __name__ == "__main__":
    unittest.main()
