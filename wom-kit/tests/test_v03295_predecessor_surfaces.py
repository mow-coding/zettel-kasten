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
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "v0.3.294-surface-baseline.json"
RESOURCE_MANIFEST_PATH = SRC_ROOT / "wom_kit" / "_resources" / "resource-manifest.json"

PREDECESSOR_COMMIT = "845588144c713b585e67985bc93a0f341e6fe53c"
FIXTURE_SCHEMA = "wom-kit/test-fixture/v0.3.294-predecessor-surfaces/v0.1"
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
        "count": 502,
        "canonical_sha256": "deabfa45fca04d31f7fd6923e0b6e66779a95f3b7b0598a6a9736f6640df611e",
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
        "count": 103,
        "canonical_sha256": "369dfcf6a6f1d842e9eeabb34f81c0721567827f852914a42e97f9b8cccb3e78",
        "value_key": "packaged_paths",
    },
}
RESOURCE_ADDITIONS = {
    "schemas/private-objet-source-metadata-v0.1.schema.json",
    "schemas/objet-safe-label-projection-v0.1.schema.json",
    "release-notes/v0.3.295.md",
}
RESOURCE_REMOVALS = {"release-notes/v0.3.294.md"}


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
        "CLI command paths differ from the exact v0.3.294 predecessor surface. "
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
        f"{label} differs from the exact v0.3.294 predecessor surface. "
        f"missing={compact(sorted(expected_keys - actual_keys))}; "
        f"extra={compact(sorted(actual_keys - expected_keys))}; "
        f"changed={compact(changed)}"
    )


class V03295PredecessorSurfaceTests(unittest.TestCase):
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

    def test_cli_nested_paths_exactly_match_v03294(self) -> None:
        expected = self.fixture["cli"]["paths"]
        actual = current_cli_paths()
        self.assertEqual(actual, expected, path_diff_message(expected, actual))
        self.assertEqual(len(actual), BASELINE_EXPECTATIONS["cli"]["count"])
        self.assertEqual(
            canonical_sha256(actual),
            BASELINE_EXPECTATIONS["cli"]["canonical_sha256"],
        )

    def test_database_source_rows_exactly_match_v03294(self) -> None:
        expected = self.fixture["database"]["sources"]
        actual = current_database_sources()
        self.assertEqual(
            actual,
            expected,
            named_row_diff_message("Database source rows", expected, actual, "path"),
        )
        self.assertEqual(len(actual), BASELINE_EXPECTATIONS["database"]["count"])
        self.assertEqual(
            canonical_sha256(actual),
            BASELINE_EXPECTATIONS["database"]["canonical_sha256"],
        )

    def test_mcp_name_and_input_schema_rows_exactly_match_v03294(self) -> None:
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

    def test_package_resource_paths_are_exact_v03294_plus_v03295_delta(self) -> None:
        predecessor_paths = set(self.fixture["package_resources"]["packaged_paths"])
        self.assertTrue(
            RESOURCE_REMOVALS <= predecessor_paths,
            "The declared removal must exist in the v0.3.294 predecessor fixture.",
        )
        self.assertFalse(
            RESOURCE_ADDITIONS & predecessor_paths,
            "The declared additions must be new relative to v0.3.294.",
        )
        expected = sorted((predecessor_paths - RESOURCE_REMOVALS) | RESOURCE_ADDITIONS)
        self.assertEqual(len(expected), 105)

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
            "Current package-resource paths must be the full v0.3.294 set plus "
            "the exact v0.3.295 delta. "
            f"missing={compact(missing)}; extra={compact(extra)}",
        )
        self.assertEqual(manifest["version"], "0.3.295")
        self.assertEqual(len(actual), 105)


if __name__ == "__main__":
    unittest.main()
