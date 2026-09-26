"""Writers whose --approve reaches the exact approval broker honour the session grant.

Since v0.4.36 (letter 168) the broker resolves the caller's work-session grant
from the environment refs whenever a caller leaves ``session_permission``
unset, and every operation kind is grantable. The 2026-09-26 coverage audit
found 28 writers still listed as ``pending`` although their ``--approve`` path
already reaches that broker. This test is the evidence for reclassifying them
as ``session_integrated`` with ``route: environment``:

- each command function statically reaches a broker entry point through
  module-level calls, and no function on the traced path passes
  ``session_permission=None`` (the onboarding-only "always dialog" switch);
- the broker entry points leave ``session_permission`` at its default.

The runtime proof that an unset permission resolves the environment grant and
skips the dialog is ``test_v0436_letter168``.
"""

from __future__ import annotations

import ast
import json
import unittest
from functools import lru_cache
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = KIT_ROOT / "src" / "wom_kit"
MANIFEST = KIT_ROOT / "docs" / "writer-session-coverage.json"

BROKER_ENTRIES = frozenset({
    "_execute_exact_human_approved_write",
    "execute_exact_human_approved_write",
})
AUDITED_2026_09_26 = (
    "zet-revision-write", "zet-revision-restore-write", "zettel-objet-link",
    "objet-capture-selection", "objet-capture", "objet-capture-batch",
    "source-intake-chain", "discard-draft", "discard-draft-restore", "mint-zet",
    "mint-zet-batch", "promote", "retire-draft", "retire-draft-batch",
    "zettel-edge", "zettel-edge-batch", "revert-batch", "revert-edge",
    "source-fidelity-session-evidence", "external-locator-record",
    "duplicate-object-reconcile", "human-artifact-register-root",
    "human-artifact-transition", "approval-integrity-overlay", "migrate",
    "object-storage", "object-storage-adopt-existing", "relation-candidate-decide",
)
MAX_DEPTH = 8


@lru_cache(maxsize=None)
def _functions() -> dict[str, list[ast.FunctionDef]]:
    """Every module-level function in the package, by name."""

    table: dict[str, list[ast.FunctionDef]] = {}
    for path in sorted(SOURCE_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                table.setdefault(node.name, []).append(node)
    return table


def _called_names(function: ast.FunctionDef) -> set[str]:
    """Names a function calls or passes on (a writer chosen into a variable)."""

    names: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            names.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            names.add(node.attr)
    return names


def _forces_dialog(function: ast.FunctionDef) -> bool:
    for node in ast.walk(function):
        if isinstance(node, ast.keyword) and node.arg == "session_permission":
            if isinstance(node.value, ast.Constant) and node.value.value is None:
                return True
    return False


def _reaches_broker(name: str) -> tuple[bool, list[str]]:
    """Breadth-first over module-level calls; returns (reached, forcing functions)."""

    functions = _functions()
    seen = {name}
    frontier = [name]
    forcing: list[str] = []
    for _ in range(MAX_DEPTH):
        following: list[str] = []
        for current in frontier:
            for definition in functions.get(current, []):
                if _forces_dialog(definition):
                    forcing.append(current)
                for called in _called_names(definition):
                    if called in BROKER_ENTRIES:
                        return True, forcing
                    if called in functions and called not in seen:
                        seen.add(called)
                        following.append(called)
        frontier = following
    return False, forcing


def _command_functions() -> dict[str, str]:
    from wom_kit import archive_cli

    parser = archive_cli.build_parser()
    table: dict[str, str] = {}
    for action in parser._subparsers._group_actions:  # noqa: SLF001 - parser inventory
        for name, subparser in action.choices.items():
            function = subparser.get_default("func")
            if function is not None:
                table.setdefault(name, function.__name__)
    return table


class WriterSessionEnvironmentRouteTests(unittest.TestCase):
    def test_every_audited_writer_reaches_the_broker_without_forcing_a_dialog(self) -> None:
        commands = _command_functions()
        for path in AUDITED_2026_09_26:
            with self.subTest(path=path):
                function = commands.get(path)
                self.assertIsNotNone(function, path)
                reached, forcing = _reaches_broker(function)
                self.assertTrue(reached, f"{path}: {function} no longer reaches the approval broker")
                self.assertEqual(forcing, [], f"{path}: session_permission=None on the path")

    def test_broker_entry_points_default_to_the_environment_grant(self) -> None:
        from wom_kit import exact_human_approval_workflow as workflow

        for name in ("_execute_exact_human_approved_write_core",):
            function = getattr(workflow, name)
            default = function.__kwdefaults__["session_permission"]
            self.assertIs(default, workflow._UNSET_SESSION_PERMISSION)

    def test_manifest_lists_the_audited_writers_as_environment_integrated(self) -> None:
        paths = json.loads(MANIFEST.read_text(encoding="utf-8"))["paths"]
        for path in AUDITED_2026_09_26:
            with self.subTest(path=path):
                row = paths[path]
                self.assertEqual(row["status"], "session_integrated")
                self.assertEqual(row["route"], "environment")
                self.assertIn("test_writer_session_environment_routes", row["evidence"])
        self.assertEqual(paths["credential-adopt"]["status"], "legacy_exception")
        self.assertNotIn("pending", {row["status"] for row in paths.values()})

    def test_the_onboarding_dialog_is_the_only_forced_dialog(self) -> None:
        forcing = sorted(
            name
            for name, definitions in _functions().items()
            for definition in definitions
            if _forces_dialog(definition)
        )
        self.assertEqual(forcing, ["_onboard_exact_route"])


if __name__ == "__main__":
    unittest.main()
