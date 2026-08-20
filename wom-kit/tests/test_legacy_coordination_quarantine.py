from __future__ import annotations

import ast
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from wom_kit import archive_cli, archive_services


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent


class LegacyCoordinationQuarantineTests(unittest.TestCase):
    def run_archive_cli(self, args: list[str]) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = archive_cli.main(args)
        return code, buffer.getvalue()

    def test_active_onboarding_docs_do_not_advertise_retired_integration(self) -> None:
        active_docs = (
            REPO_ROOT / "README.md",
            REPO_ROOT / "README.ko.md",
            KIT_ROOT / "README.md",
            KIT_ROOT / "docs" / "ai-assisted-onboarding-and-provider-setup.md",
            KIT_ROOT / "docs" / "artifact-hygiene.md",
            KIT_ROOT / "docs" / "capability-matrix.md",
            KIT_ROOT / "docs" / "new-user-flow.md",
            KIT_ROOT / "docs" / "project-intake-session.md",
            KIT_ROOT / "docs" / "public-documentation-map.md",
            KIT_ROOT / "docs" / "public-documentation-map.ko.md",
            KIT_ROOT / "docs" / "python-tool-install.md",
            KIT_ROOT / "docs" / "python-tool-install.ko.md",
            KIT_ROOT / "docs" / "runtime-canonical-entrypoints.md",
            KIT_ROOT / "docs" / "validation-surface.md",
        )
        banned = (
            "github.com/mow-coding/mow-harness",
            "mow-harness-compatibility.md",
            "mow status ",
            "mow doctor ",
            "mow update ",
        )
        for path in active_docs:
            text = path.read_text(encoding="utf-8").lower()
            for phrase in banned:
                with self.subTest(path=path, phrase=phrase):
                    self.assertNotIn(phrase, text)

        self.assertFalse((KIT_ROOT / "docs" / "mow-harness-compatibility.md").exists())

    def test_runtime_schema_and_bundle_have_no_retired_integration_surface(self) -> None:
        pyproject = (KIT_ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
        self.assertNotIn("mow-harness =", pyproject)
        self.assertNotIn("mow_harness", pyproject)

        runtime_root = KIT_ROOT / "src" / "wom_kit"
        for path in sorted(runtime_root.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            lowered = source.lower()
            with self.subTest(surface="runtime-text", path=path):
                self.assertNotIn("github.com/mow-coding/mow-harness", lowered)
                self.assertNotIn("mow_harness", lowered)

            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = {alias.name.lower() for alias in node.names}
                    self.assertNotIn("mow_harness", imported, path)
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotEqual((node.module or "").lower(), "mow_harness", path)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertNotEqual(node.value.strip().lower(), "mow", path)

        nonhistorical_bundle_roots = (
            KIT_ROOT / "schemas",
            KIT_ROOT / "templates",
            runtime_root / "_resources" / "schemas",
            runtime_root / "_resources" / "templates",
            runtime_root / "_resources" / "zettel-kasten",
        )
        retired_markers = (
            "github.com/mow-coding/mow-harness",
            "mow-harness",
            "mow_harness",
            "mow harness",
        )
        for root in nonhistorical_bundle_roots:
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                text = path.read_text(encoding="utf-8").lower()
                for marker in retired_markers:
                    with self.subTest(surface="schema-or-bundle", path=path, marker=marker):
                        self.assertNotIn(marker, text)

        manifest = json.loads(
            (runtime_root / "_resources" / "resource-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        for item in manifest["files"]:
            for key in ("source", "packaged"):
                value = item[key].lower()
                with self.subTest(surface="resource-manifest", key=key, value=value):
                    self.assertNotIn("mow-harness", value)
                    self.assertNotIn("mow_harness", value)

    def test_intentional_history_is_marked_superseded_not_active(self) -> None:
        old_decision = (
            KIT_ROOT
            / "docs"
            / "archive-infra-decision-log-2026-07-16-v03253-mow-harness-compatibility.md"
        ).read_text(encoding="utf-8")
        current_release = (KIT_ROOT / "docs" / "releases" / "v0.3.306.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Status: superseded by v0.3.306", old_decision)
        self.assertIn("history, not current product guidance", current_release)

    def test_legacy_namespaces_never_enter_catalog_or_zettel_read_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", archive_root)
            quarantined_files = {
                archive_root / "collab" / "STATE.md": b"PRIVATE COORDINATION STATE MUST NOT BECOME A ZET\n",
                archive_root / ".mow-harness" / "operator-note.md": b"PRIVATE LEGACY TOOL NOTE MUST NOT BECOME A ZET\n",
            }
            for path, content in quarantined_files.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

            code, output = self.run_archive_cli(
                [
                    "zet-catalog",
                    str(archive_root),
                    "--status",
                    "all",
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 0, output)
            catalog = json.loads(output)
            catalog_paths = {item["path"] for item in catalog["items"]}
            self.assertNotIn("collab/STATE.md", catalog_paths)
            self.assertNotIn(".mow-harness/operator-note.md", catalog_paths)
            self.assertNotIn("PRIVATE COORDINATION", output)
            self.assertNotIn("PRIVATE LEGACY", output)

            for relative_path in ("collab/STATE.md", ".mow-harness/operator-note.md"):
                with self.subTest(path=relative_path):
                    read_code, read_output = self.run_archive_cli(
                        ["read-zettel", str(archive_root), "--path", relative_path]
                    )
                    self.assertEqual(read_code, 1, read_output)
                    self.assertIn("inbox/ or zettels", read_output)

            for path, content in quarantined_files.items():
                self.assertEqual(path.read_bytes(), content)

    def test_doctor_does_not_read_quarantined_root_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", archive_root)
            quarantined_files = {
                archive_root / "Collab" / "private-state.txt": b"api_key=private_sentinel_1234567890\n",
                archive_root / ".MOW-HARNESS" / "private-state.txt": b"token=private_sentinel_0987654321\n",
            }
            for path, content in quarantined_files.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            nested_coordination_path = archive_root / "inbox" / "collab" / "ordinary-state.txt"
            nested_coordination_path.parent.mkdir(parents=True, exist_ok=True)
            nested_coordination_path.write_bytes(b"api_key=nested_sentinel_1234567890\n")

            doctor = archive_cli.Doctor(archive_root)
            scanned_paths: list[Path] = []
            original_scan = doctor._file_contains_secret_value

            def guarded_scan(path: Path, *args: object, **kwargs: object) -> bool:
                scanned_paths.append(path)
                return original_scan(path, *args, **kwargs)

            with patch.object(
                doctor,
                "_file_contains_secret_value",
                side_effect=guarded_scan,
            ):
                doctor._check_local_profile_and_secret_safety()

            walked_directories: list[Path] = []
            original_walk = os.walk

            def guarded_walk(*args: object, **kwargs: object):
                for row in original_walk(*args, **kwargs):
                    walked_directories.append(Path(row[0]))
                    yield row

            with patch.object(archive_cli.os, "walk", side_effect=guarded_walk):
                doctor._check_symlink_boundaries()

            self.assertFalse(
                any(
                    scanned_path.samefile(quarantined_path)
                    for scanned_path in scanned_paths
                    for quarantined_path in quarantined_files
                ),
                scanned_paths,
            )
            self.assertTrue(
                any(scanned_path.samefile(nested_coordination_path) for scanned_path in scanned_paths),
                scanned_paths,
            )
            for quarantined_path in quarantined_files:
                self.assertFalse(
                    any(
                        walked_path.samefile(quarantined_path.parent)
                        for walked_path in walked_directories
                    ),
                    walked_directories,
                )
            self.assertTrue(
                any(
                    walked_path.samefile(nested_coordination_path.parent)
                    for walked_path in walked_directories
                ),
                walked_directories,
            )
            diagnostic_text = json.dumps(
                [item.as_dict() for item in doctor.diagnostics],
                ensure_ascii=False,
            )
            self.assertNotIn("private-state.txt", diagnostic_text)
            self.assertNotIn("private_sentinel", diagnostic_text)
            for path, content in quarantined_files.items():
                self.assertEqual(path.read_bytes(), content)

    def test_restore_drill_never_reads_or_copies_quarantined_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            target = Path(tmp) / "restore-copy"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", archive_root)
            quarantined_files = {
                archive_root / "Collab" / "private-state.txt": b"api_key=private_sentinel_1234567890\n",
                archive_root / ".MOW-HARNESS" / "private-state.txt": b"token=private_sentinel_0987654321\n",
            }
            for path, content in quarantined_files.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            nested_coordination_path = archive_root / "inbox" / "collab" / "ordinary-state.txt"
            nested_coordination_path.parent.mkdir(parents=True, exist_ok=True)
            nested_coordination_path.write_bytes(b"ordinary nested archive state\n")

            plan = archive_services.restore_drill_copy_plan(archive_root)
            self.assertIn("collab/", plan["excluded_paths"])
            self.assertIn(".mow-harness/", plan["excluded_paths"])
            restore_candidates = list(archive_services.iter_restore_drill_files(archive_root))
            self.assertFalse(
                any(
                    candidate.samefile(quarantined_path)
                    for candidate in restore_candidates
                    for quarantined_path in quarantined_files
                ),
                restore_candidates,
            )
            self.assertTrue(
                any(candidate.samefile(nested_coordination_path) for candidate in restore_candidates),
                restore_candidates,
            )
            ordered_target = Path(tmp) / "ordered-restore-copy"
            blocked_copy = archive_services.copy_restore_drill_tree(
                archive_root,
                ordered_target,
            )
            self.assertFalse(blocked_copy["ok"])
            self.assertEqual(
                blocked_copy["reason_codes"],
                ["compound_exact_human_approval_binding_required"],
            )
            self.assertEqual(blocked_copy["files_written"], [])
            self.assertFalse(ordered_target.exists())

            code, output = self.run_archive_cli(
                [
                    "restore-drill",
                    str(archive_root),
                    "--target",
                    str(target),
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1, output)
            self.assertEqual(
                json.loads(output),
                {
                    "ok": False,
                    "state": "blocked",
                    "lifecycle_action": "restore_drill",
                    "reason_codes": [
                        "compound_exact_human_approval_binding_required"
                    ],
                    "files_written": [],
                    "private_values_echoed": False,
                },
            )
            self.assertNotIn("private-state.txt", output)
            self.assertNotIn("private_sentinel", output)
            self.assertFalse(target.exists())
            for path, content in quarantined_files.items():
                self.assertEqual(path.read_bytes(), content)

    def test_archive_root_source_scan_never_indexes_quarantined_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", archive_root)
            quarantined_files = {
                archive_root / "Collab" / "private-state.txt": b"private coordination state\n",
                archive_root / ".MOW-HARNESS" / "private-state.txt": b"private retired state\n",
            }
            for path, content in quarantined_files.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            nested_coordination_path = (
                archive_root / "inbox" / "collab" / "ordinary-state.txt"
            )
            nested_coordination_path.parent.mkdir(parents=True, exist_ok=True)
            nested_coordination_path.write_bytes(b"ordinary nested archive state\n")
            warnings: list[str] = []

            items = archive_services.filesystem_source_map_items(
                archive_root,
                {
                    "source_id": "local:test",
                    "source_type": "local_folder",
                    "scope_policy": {"include": ["**/*"], "exclude": []},
                    "visibility": {
                        "scope": "private",
                        "source_visibility": "private",
                    },
                },
                "2026-08-08T00:00:00+00:00",
                10_000,
                warnings,
            )

            relative_paths = {str(item["relative_path"]) for item in items}
            self.assertFalse(
                any(
                    path.casefold().startswith(("collab/", ".mow-harness/"))
                    for path in relative_paths
                ),
                relative_paths,
            )
            self.assertIn("inbox/collab/ordinary-state.txt", relative_paths)
            self.assertIn(
                "Archive-root source scan excluded local coordination quarantine roots.",
                warnings,
            )
            for path, content in quarantined_files.items():
                self.assertEqual(path.read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
