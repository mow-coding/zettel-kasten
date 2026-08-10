from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
import unittest


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent
SRC_ROOT = KIT_ROOT / "src"
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "v0.3.297-surface-baseline.json"
RESOURCE_MANIFEST_PATH = SRC_ROOT / "wom_kit" / "_resources" / "resource-manifest.json"

PREDECESSOR_COMMIT = "96a37f10907951039130ea0b1cc574e2b3f80ffa"
FIXTURE_SCHEMA = "wom-kit/test-fixture/v0.3.297-predecessor-surfaces/v0.1"
SERIALIZER_METADATA = {
    "algorithm": (
        "json.dumps(value, ensure_ascii=True, sort_keys=True, "
        "separators=(',', ':')) + '\\n', then UTF-8 encode and SHA-256"
    ),
    "encoding": "utf-8",
    "ensure_ascii": True,
    "separators": [",", ":"],
    "sort_keys": True,
    "trailing_newline": True,
}
BASELINE_EXPECTATIONS = {
    "cli": {
        "count": 503,
        "canonical_sha256": "88b1996bee09d35a422e53a6791e3b9b1c776a8892d0113f2172c926b3a9e77d",
        "value_key": "paths",
    },
    "mcp": {
        "count": 121,
        "canonical_sha256": "b031dd940504250a5c451d55ba072367c694898bb1ebef2098fa904ed58d5c8f",
        "value_key": "tools",
    },
    "database": {
        "count": 3,
        "canonical_sha256": "06173af07c47ea345c7b94c447832142f2c1da615e6e3681a020b3078dbabfe5",
        "value_key": "sources",
    },
    "package_resources": {
        "count": 111,
        "canonical_sha256": "0cd99923a931a57044386797fbfb6fd4edbe4fb2b39976d906180767ada8c390",
        "value_key": "packaged_paths",
    },
}
CLI_ADDITIONS = {
    ("archive-authoring-conventions",),
    ("archive-lifecycle-inventory",),
    ("authoring-conventions",),
    ("artifact-inventory",),
    ("artifact-lifecycle-inventory",),
    ("credential-adopt",),
    ("credential-lifecycle",),
    ("credential-secure-list",),
    ("discard-draft",),
    ("discard-draft-restore",),
    ("external-locator-plan",),
    ("external-locator-record",),
    ("external-locator-deactivate-plan",),
    ("external-locator-deactivate",),
    ("external-locator-recovery-plan",),
    ("external-locator-revert",),
    ("find-objet",),
    ("legacy-coordination-cleanup",),
    ("markup-normalization",),
    ("markup-normalization-plan",),
    ("markup-normalization-recovery",),
    ("markup-normalization-revert",),
    ("markup-style-guide",),
    ("notion-page-recovery",),
    ("notion-page-recovery-plan",),
    ("notion-reviewed-page-recovery",),
    ("notion-reviewed-page-recovery-plan",),
    ("objet-capture-batch",),
    ("operator-feedback-body-check",),
    ("operator-feedback-compose",),
    ("principal-list",),
    ("principal-register",),
    ("principal-register-plan",),
    ("principal-unregister",),
    ("principal-unregister-plan",),
    ("project-bytecode-repair",),
    ("project-bytecode-repair-plan",),
    ("relation-candidate-decide",),
    ("relation-candidate-plan",),
    ("relation-semantics-guide",),
    ("saved-view-revert",),
    ("saved-view-write",),
    ("source-reference-coverage-audit",),
    ("source-intake-batch",),
    ("zet-objet-link",),
    ("zet-objet-link-revert",),
    ("zettel-objet-link",),
    ("zettel-objet-link-revert",),
}
CURRENT_CLI_COUNT = 551
CURRENT_CLI_CANONICAL_SHA256 = (
    "a177a1fcbfd86601c04f23a26f1605b8e685205988c2fbe70b342d3b7241f638"
)
CURRENT_DATABASE_COUNT = 3
CURRENT_DATABASE_CANONICAL_SHA256 = (
    "d9a42f08ee12a6d42e40214cfb12441e4077bf50c38c25b2692ec1344328294a"
)
RESOURCE_ADDITIONS = {
    "release-notes/v0.3.312.md",
    "schemas/artifact-lifecycle-inventory.schema.json",
    "schemas/authoring-conventions.schema.json",
    "schemas/draft-discard-receipt.schema.json",
    "schemas/draft-discard-restore-receipt.schema.json",
    "schemas/external-locator-receipt.schema.json",
    "schemas/external-locator-record.schema.json",
    "schemas/external-locator-revert-receipt.schema.json",
    "schemas/markup-normalization-journal.schema.json",
    "schemas/markup-normalization-plan.schema.json",
    "schemas/markup-normalization-receipt.schema.json",
    "schemas/markup-normalization-recovery-receipt.schema.json",
    "schemas/markup-normalization-revert-receipt.schema.json",
    "schemas/markup-reference-binding-manifest.schema.json",
    "schemas/objet-capture-batch-receipt.schema.json",
    "schemas/objet-capture-batch-request.schema.json",
    "schemas/principal-record.schema.json",
    "schemas/principal-registration-receipt.schema.json",
    "schemas/principal-unregistration-receipt.schema.json",
    "schemas/private-objet-finder-request-v0.1.schema.json",
    "schemas/private-objet-finder-result-v0.1.schema.json",
    "schemas/project-bytecode-repair-receipt.schema.json",
    "schemas/relation-candidate-plan.schema.json",
    "schemas/relation-judgment-receipt.schema.json",
    "schemas/relation-judgment.schema.json",
    "schemas/saved-view-revert-journal.schema.json",
    "schemas/saved-view-revert-receipt.schema.json",
    "schemas/saved-view-write-receipt.schema.json",
    "schemas/saved-view-write-request.schema.json",
    "schemas/source-reference-coverage-audit-result-v0.1.schema.json",
    "schemas/source-intake-batch-receipt.schema.json",
    "schemas/source-intake-batch-request.schema.json",
    "schemas/zettel-objet-link-receipt.schema.json",
    "schemas/zettel-objet-link-revert-receipt.schema.json",
}
RESOURCE_REMOVALS = {"release-notes/v0.3.297.md"}
CURRENT_RESOURCE_COUNT = 144
CURRENT_RESOURCE_CANONICAL_SHA256 = (
    "07f85acf825687c4447225048db1542c40e866bae8950552e25468093bdb4f65"
)


# Put this worktree's source checkout ahead of installed packages and repository
# shims before importing the public surfaces that the snapshot protects.
src_root_text = str(SRC_ROOT)
if src_root_text in sys.path:
    sys.path.remove(src_root_text)
sys.path.insert(0, src_root_text)

from wom_kit import archive_cli, mcp_server  # noqa: E402


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def current_cli_paths() -> list[list[str]]:
    discovered: set[tuple[str, ...]] = set()

    def visit(parser: argparse.ArgumentParser, prefix: tuple[str, ...]) -> None:
        for action in parser._actions:
            if not isinstance(action, argparse._SubParsersAction):
                continue
            for label, child_parser in action.choices.items():
                path = prefix + (label,)
                discovered.add(path)
                visit(child_parser, path)

    visit(archive_cli.build_parser(), ())
    return [list(path) for path in sorted(discovered)]


def current_mcp_tools() -> list[dict[str, Any]]:
    names = [row.get("name") for row in mcp_server.TOOL_DEFINITIONS]
    if any(not isinstance(name, str) or not name for name in names):
        raise AssertionError("Every MCP tool definition must have a non-empty string name.")
    if len(names) != len(set(names)):
        duplicates = sorted({name for name in names if names.count(name) > 1})
        raise AssertionError(f"MCP tool names must be unique; duplicates={duplicates!r}")

    rows: list[dict[str, Any]] = []
    for definition in mcp_server.TOOL_DEFINITIONS:
        if "inputSchema" not in definition:
            raise AssertionError(f"MCP tool {definition['name']!r} has no inputSchema.")
        rows.append(
            {
                "name": definition["name"],
                "inputSchema": definition["inputSchema"],
            }
        )
    return sorted(rows, key=lambda row: row["name"])


def current_database_sources() -> list[dict[str, Any]]:
    candidates = {
        path
        for path in (KIT_ROOT / "templates").glob("*/db/schema.sql")
        if path.is_file()
    }
    for relative_root in ("wom-kit/migrations", "wom-kit/src/wom_kit/migrations"):
        migration_root = REPO_ROOT / relative_root
        if migration_root.is_dir():
            candidates.update(path for path in migration_root.rglob("*") if path.is_file())

    rows = []
    for path in sorted(candidates, key=lambda item: item.relative_to(REPO_ROOT).as_posix()):
        data = path.read_bytes()
        rows.append(
            {
                "bytes": len(data),
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return rows


def compact(values: list[str], limit: int = 30) -> str:
    if not values:
        return "[]"
    shown = values[:limit]
    suffix = "" if len(values) <= limit else f", ... ({len(values) - limit} more)"
    return "[" + ", ".join(repr(value) for value in shown) + suffix + "]"


def path_diff_message(expected: list[list[str]], actual: list[list[str]]) -> str:
    expected_paths = {" ".join(path) for path in expected}
    actual_paths = {" ".join(path) for path in actual}
    return (
        "CLI command paths differ from the exact v0.3.297 predecessor surface. "
        f"missing={compact(sorted(expected_paths - actual_paths))}; "
        f"extra={compact(sorted(actual_paths - expected_paths))}"
    )


def named_row_diff_message(
    label: str,
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    key: str,
) -> str:
    expected_by_key = {row[key]: row for row in expected}
    actual_by_key = {row[key]: row for row in actual}
    expected_keys = set(expected_by_key)
    actual_keys = set(actual_by_key)
    changed = sorted(
        row_key
        for row_key in expected_keys & actual_keys
        if expected_by_key[row_key] != actual_by_key[row_key]
    )
    return (
        f"{label} differs from the exact v0.3.297 predecessor surface. "
        f"missing={compact(sorted(expected_keys - actual_keys))}; "
        f"extra={compact(sorted(actual_keys - expected_keys))}; "
        f"changed={compact(changed)}"
    )


class V03299PredecessorSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_fixture()

    def test_00_fixture_identity_and_canonical_hashes_are_intact(self) -> None:
        self.assertEqual(self.fixture["schema"], FIXTURE_SCHEMA)
        self.assertEqual(self.fixture["predecessor_commit"], PREDECESSOR_COMMIT)
        self.assertEqual(self.fixture["serializer"], SERIALIZER_METADATA)

        for section_name, expectation in BASELINE_EXPECTATIONS.items():
            with self.subTest(section=section_name):
                section = self.fixture[section_name]
                values = section[expectation["value_key"]]
                self.assertEqual(section["count"], expectation["count"])
                self.assertEqual(len(values), expectation["count"])
                self.assertEqual(
                    section["canonical_sha256"],
                    expectation["canonical_sha256"],
                )
                self.assertEqual(
                    canonical_sha256(values),
                    expectation["canonical_sha256"],
                )

        cli_paths = self.fixture["cli"]["paths"]
        self.assertEqual(cli_paths, sorted(cli_paths))
        self.assertEqual(len(cli_paths), len({tuple(path) for path in cli_paths}))

        mcp_tools = self.fixture["mcp"]["tools"]
        self.assertEqual(
            [row["name"] for row in mcp_tools],
            sorted(row["name"] for row in mcp_tools),
        )
        self.assertEqual(
            len(mcp_tools),
            len({row["name"] for row in mcp_tools}),
        )
        self.assertTrue(all(set(row) == {"name", "inputSchema"} for row in mcp_tools))

        database_rows = self.fixture["database"]["sources"]
        self.assertEqual(
            [row["path"] for row in database_rows],
            sorted(row["path"] for row in database_rows),
        )
        self.assertTrue(
            all(set(row) == {"path", "bytes", "sha256"} for row in database_rows)
        )

        packaged_paths = self.fixture["package_resources"]["packaged_paths"]
        self.assertEqual(packaged_paths, sorted(packaged_paths))
        self.assertEqual(len(packaged_paths), len(set(packaged_paths)))

    def test_01_surface_modules_are_imported_from_this_worktree(self) -> None:
        for module in (archive_cli, mcp_server):
            with self.subTest(module=module.__name__):
                imported_path = Path(module.__file__).resolve()
                try:
                    imported_path.relative_to(SRC_ROOT.resolve())
                except ValueError:
                    self.fail(
                        f"{module.__name__} was imported outside this worktree's source checkout."
                    )

    def test_cli_paths_are_v03297_plus_exact_v03298_v03312_delta(self) -> None:
        predecessor = self.fixture["cli"]["paths"]
        predecessor_set = {tuple(path) for path in predecessor}
        self.assertFalse(CLI_ADDITIONS & predecessor_set)
        expected = [
            list(path)
            for path in sorted(predecessor_set | CLI_ADDITIONS)
        ]
        actual = current_cli_paths()
        self.assertEqual(actual, expected, path_diff_message(expected, actual))
        self.assertEqual(len(actual), CURRENT_CLI_COUNT)
        self.assertEqual(
            canonical_sha256(actual),
            CURRENT_CLI_CANONICAL_SHA256,
        )

    def test_database_sources_add_only_the_v03300_principal_projection(self) -> None:
        predecessor = self.fixture["database"]["sources"]
        actual = current_database_sources()
        self.assertEqual(
            [row["path"] for row in actual],
            [row["path"] for row in predecessor],
        )
        self.assertNotEqual(actual, predecessor)
        self.assertTrue(
            all(
                "CREATE TABLE IF NOT EXISTS principals"
                in (REPO_ROOT / row["path"]).read_text(encoding="utf-8")
                for row in actual
            )
        )
        self.assertEqual(len(actual), CURRENT_DATABASE_COUNT)
        self.assertEqual(
            canonical_sha256(actual),
            CURRENT_DATABASE_CANONICAL_SHA256,
        )

    def test_mcp_name_and_input_schema_rows_exactly_match_v03297(self) -> None:
        expected = self.fixture["mcp"]["tools"]
        actual = current_mcp_tools()
        self.assertEqual(
            actual,
            expected,
            named_row_diff_message("MCP name/inputSchema rows", expected, actual, "name"),
        )
        self.assertEqual(len(actual), BASELINE_EXPECTATIONS["mcp"]["count"])
        self.assertEqual(
            canonical_sha256(actual),
            BASELINE_EXPECTATIONS["mcp"]["canonical_sha256"],
        )

    def test_resource_paths_are_v03297_plus_exact_v03298_v03312_delta(self) -> None:
        predecessor_paths = set(self.fixture["package_resources"]["packaged_paths"])
        self.assertTrue(
            RESOURCE_REMOVALS <= predecessor_paths,
            "The declared removal must exist in the v0.3.297 predecessor fixture.",
        )
        self.assertFalse(
            RESOURCE_ADDITIONS & predecessor_paths,
            "The declared additions must be new relative to v0.3.297.",
        )
        expected = sorted((predecessor_paths - RESOURCE_REMOVALS) | RESOURCE_ADDITIONS)
        self.assertEqual(len(expected), CURRENT_RESOURCE_COUNT)

        manifest = json.loads(RESOURCE_MANIFEST_PATH.read_text(encoding="utf-8"))
        rows = manifest["files"]
        actual = sorted(row["packaged"] for row in rows)
        self.assertEqual(manifest["schema"], "wom-kit/package-resource-manifest/v0.1")
        self.assertEqual(manifest["file_count"], len(rows))
        self.assertEqual(
            len(actual),
            len(set(actual)),
            "The current resource manifest contains duplicate packaged paths.",
        )

        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        self.assertEqual(
            actual,
            expected,
            "Current package-resource paths must be the full v0.3.297 set plus "
            "the exact cumulative v0.3.298 through v0.3.312 delta. "
            f"missing={compact(missing)}; extra={compact(extra)}",
        )
        self.assertEqual(manifest["version"], "0.3.312")
        self.assertEqual(len(actual), CURRENT_RESOURCE_COUNT)
        self.assertEqual(
            canonical_sha256(actual),
            CURRENT_RESOURCE_CANONICAL_SHA256,
        )

    def test_v03297_release_note_keeps_predecessor_claim_boundary(self) -> None:
        predecessor_release = KIT_ROOT / "docs" / "releases" / "v0.3.297.md"
        predecessor_text = predecessor_release.read_text(encoding="utf-8")
        predecessor_flat = " ".join(predecessor_text.split())
        self.assertIn("exit code `1`", predecessor_flat)
        self.assertIn(
            "fresh `archive index-health --dry-run`",
            predecessor_flat,
        )
        self.assertIn("does not undo", predecessor_flat)
        self.assertNotIn("C:\\Users\\", predecessor_text)

    def test_v03312_release_note_is_public_and_synchronized(self) -> None:
        current_source_release = KIT_ROOT / "docs" / "releases" / "v0.3.312.md"
        current_packaged_release = (
            SRC_ROOT
            / "wom_kit"
            / "_resources"
            / "release-notes"
            / "v0.3.312.md"
        )
        self.assertEqual(
            current_source_release.read_bytes(),
            current_packaged_release.read_bytes(),
        )
        current_text = current_source_release.read_text(encoding="utf-8")
        current_flat = " ".join(current_text.split())
        for token in (
            "mint-zet --progress",
            "view-zets",
            "operator-feedback-compose",
            "operator-feedback-body-check",
            "archive_index_rebuild_required",
            "zero protected query rows",
            "UTF-8 JSON object",
            "feedback-body-sha256:<64 hex>",
            "No beta archive was modified or automatically rebuilt",
            "do not submit feedback externally",
            "prove human receipt",
        ):
            with self.subTest(token=token):
                self.assertIn(token, current_flat)
        for forbidden in (
            "C:\\Users\\",
            "private-canary.hwpx",
            "DO-NOT-REFLECT-PRIVATE-QUERY",
            "https://private.example",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, current_text)

    def test_older_terminal_failstop_boundaries_remain_public(self) -> None:
        predecessor_release = KIT_ROOT / "docs" / "releases" / "v0.3.296.md"
        english_documents = (
            predecessor_release,
            KIT_ROOT / "docs" / "private-objet-metadata-safe-label.md",
            REPO_ROOT / "UPGRADE.md",
        )
        for path in english_documents:
            with self.subTest(document=path.name):
                text = path.read_text(encoding="utf-8")
                flat = " ".join(text.split())
                self.assertIn("exit code 74", flat)
                self.assertIn("fresh dry-run", flat)
                self.assertIn("normal JSON result", flat)
                self.assertIn("three consecutive", flat)
                self.assertNotIn("C:\\Users\\", text)

        korean_upgrade = (REPO_ROOT / "UPGRADE.ko.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "process exit code 74",
            "fresh dry-run",
            "정상 JSON",
            "3회",
        ):
            with self.subTest(korean_phrase=phrase):
                self.assertIn(phrase, korean_upgrade)
        self.assertNotIn("C:\\Users\\", korean_upgrade)


if __name__ == "__main__":
    unittest.main()
