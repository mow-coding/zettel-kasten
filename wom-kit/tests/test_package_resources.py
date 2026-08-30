from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wom_kit import __version__
from wom_kit import resource_paths


KIT_ROOT = Path(__file__).resolve().parents[1]
SYNC_TOOL = KIT_ROOT / "tools" / "sync_package_resources.py"
PACKAGED_ROOT = KIT_ROOT / "src" / "wom_kit" / "_resources"


class PackageResourceTests(unittest.TestCase):
    def _load_sync_tool_module(self):
        spec = importlib.util.spec_from_file_location(
            "wom_kit_test_sync_package_resources",
            SYNC_TOOL,
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_committed_package_resources_match_source_truth(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SYNC_TOOL), "--check"],
            cwd=KIT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        self.assertIn("package resources are synchronized", completed.stdout)

    def test_package_resource_manifest_has_exact_bytes_and_current_release(self) -> None:
        manifest_path = PACKAGED_ROOT / "resource-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rows = manifest["files"]
        self.assertEqual(manifest["schema"], "wom-kit/package-resource-manifest/v0.1")
        self.assertEqual(manifest["version"], __version__)
        self.assertEqual(manifest["file_count"], len(rows))
        self.assertGreaterEqual(len(rows), 84)
        packaged_paths = {row["packaged"] for row in rows}
        self.assertIn(f"release-notes/v{__version__}.md", packaged_paths)
        self.assertIn("templates/personal/archive.yml", packaged_paths)
        self.assertIn("schemas/archive.schema.json", packaged_paths)
        self.assertIn("zettel-kasten/types.yml", packaged_paths)
        for row in rows:
            with self.subTest(path=row["packaged"]):
                data = (PACKAGED_ROOT / row["packaged"]).read_bytes()
                self.assertEqual(len(data), row["bytes"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), row["sha256"])

    def test_manifest_order_is_platform_independent(self) -> None:
        # pathlib sorts Windows paths case-insensitively and POSIX paths
        # case-sensitively. Sorting Path objects therefore emitted a manifest
        # whose order depended on the generating machine, so `--check` failed
        # on Linux for a tree that was correct on Windows. Each group must stay
        # ordered by its packaged POSIX string, which sorts identically
        # everywhere.
        manifest_path = PACKAGED_ROOT / "resource-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        grouped: dict[str, list[str]] = {}
        for row in manifest["files"]:
            group = row["packaged"].split("/", 1)[0]
            grouped.setdefault(group, []).append(row["packaged"])
        self.assertIn("templates", grouped)
        for group, packaged_paths in grouped.items():
            with self.subTest(group=group):
                self.assertEqual(packaged_paths, sorted(packaged_paths))

    def test_sync_tool_sorts_sources_without_pathlib_case_folding(self) -> None:
        # Guard the mechanism, not only its current output: a mixed-case tree
        # must come back in case-sensitive POSIX order on every platform.
        sync_tool_source = SYNC_TOOL.read_text(encoding="utf-8")
        self.assertIn("key=lambda path: path.relative_to(source_root).as_posix()", sync_tool_source)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "references").mkdir()
            (root / "references" / "operator-contract.md").write_bytes(b"a")
            (root / "SKILL.md").write_bytes(b"b")
            (root / "archive.yml").write_bytes(b"c")
            (root / "README.md").write_bytes(b"d")
            ordered = [
                path.relative_to(root).as_posix()
                for path in sorted(
                    root.rglob("*"),
                    key=lambda path: path.relative_to(root).as_posix(),
                )
                if path.is_file()
            ]
        self.assertEqual(
            ordered,
            ["README.md", "SKILL.md", "archive.yml", "references/operator-contract.md"],
        )

    def test_manifest_writer_replaces_atomically_and_cleans_temporary_file(self) -> None:
        sync_tool = self._load_sync_tool_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "resource-manifest.json"
            manifest_path.write_bytes(b"old\n")
            with (
                patch.object(sync_tool, "DESTINATION_ROOT", root),
                patch.object(sync_tool, "MANIFEST_PATH", manifest_path),
            ):
                sync_tool.write_manifest_atomic({"schema": "test/v1"})
            self.assertEqual(
                manifest_path.read_bytes(),
                b'{\n  "schema": "test/v1"\n}\n',
            )
            self.assertEqual(
                list(root.glob(".resource-manifest.*.tmp")),
                [],
            )
            if os.name != "nt":
                self.assertEqual(
                    stat.S_IMODE(manifest_path.stat().st_mode),
                    0o644,
                )

    def test_manifest_writer_retries_one_windows_sharing_failure(self) -> None:
        sync_tool = self._load_sync_tool_module()
        real_replace = os.replace
        attempts = 0

        def replace_after_one_failure(source, destination):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise PermissionError("synthetic sharing violation")
            return real_replace(source, destination)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "resource-manifest.json"
            manifest_path.write_bytes(b"old\n")
            with (
                patch.object(sync_tool, "DESTINATION_ROOT", root),
                patch.object(sync_tool, "MANIFEST_PATH", manifest_path),
                patch.object(sync_tool, "_IS_WINDOWS", True),
                patch.object(
                    sync_tool.os,
                    "replace",
                    side_effect=replace_after_one_failure,
                ),
                patch.object(sync_tool.time, "sleep"),
            ):
                sync_tool.write_manifest_atomic({"schema": "test/v1"})
            self.assertEqual(attempts, 2)
            self.assertEqual(
                manifest_path.read_bytes(),
                b'{\n  "schema": "test/v1"\n}\n',
            )
            self.assertEqual(list(root.glob("*.tmp")), [])

    def test_manifest_writer_exhaustion_preserves_original_and_cleans_temp(self) -> None:
        sync_tool = self._load_sync_tool_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "resource-manifest.json"
            manifest_path.write_bytes(b"old\n")
            with (
                patch.object(sync_tool, "DESTINATION_ROOT", root),
                patch.object(sync_tool, "MANIFEST_PATH", manifest_path),
                patch.object(sync_tool, "_IS_WINDOWS", True),
                patch.object(
                    sync_tool.os,
                    "replace",
                    side_effect=PermissionError(
                        "synthetic persistent sharing violation"
                    ),
                ) as replace_mock,
                patch.object(sync_tool.time, "sleep"),
            ):
                with self.assertRaises(PermissionError):
                    sync_tool.write_manifest_atomic({"schema": "test/v1"})
            self.assertEqual(
                replace_mock.call_count,
                sync_tool.MANIFEST_REPLACE_ATTEMPTS,
            )
            self.assertEqual(manifest_path.read_bytes(), b"old\n")
            self.assertEqual(list(root.glob("*.tmp")), [])

    def test_manifest_writer_closes_descriptor_when_fdopen_fails(self) -> None:
        sync_tool = self._load_sync_tool_module()
        real_close = os.close
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "resource-manifest.json"
            manifest_path.write_bytes(b"old\n")
            with (
                patch.object(sync_tool, "DESTINATION_ROOT", root),
                patch.object(sync_tool, "MANIFEST_PATH", manifest_path),
                patch.object(
                    sync_tool.os,
                    "fdopen",
                    side_effect=OSError("synthetic fdopen failure"),
                ),
                patch.object(
                    sync_tool.os,
                    "close",
                    wraps=real_close,
                ) as close_mock,
            ):
                with self.assertRaises(OSError):
                    sync_tool.write_manifest_atomic({"schema": "test/v1"})
            self.assertEqual(close_mock.call_count, 1)
            self.assertEqual(manifest_path.read_bytes(), b"old\n")
            self.assertEqual(list(root.glob("*.tmp")), [])

    def test_resource_resolver_prefers_source_checkout(self) -> None:
        self.assertTrue(resource_paths.source_checkout_available())
        self.assertEqual(
            resource_paths.runtime_resource_root("templates"),
            KIT_ROOT / "templates",
        )
        self.assertEqual(
            resource_paths.runtime_release_note_path(__version__),
            KIT_ROOT / "docs" / "releases" / f"v{__version__}.md",
        )

    def test_resource_resolver_falls_back_to_packaged_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing_source = Path(tmp) / "missing-source-checkout"
            with patch.object(resource_paths, "SOURCE_KIT_ROOT", missing_source):
                self.assertFalse(resource_paths.source_checkout_available())
                self.assertEqual(
                    resource_paths.runtime_resource_root("schemas"),
                    PACKAGED_ROOT / "schemas",
                )
                self.assertTrue(
                    (resource_paths.runtime_resource_root("templates") / "personal" / "archive.yml").is_file()
                )
                self.assertTrue(
                    (resource_paths.runtime_resource_root("zettel-kasten") / "types.yml").is_file()
                )
                self.assertTrue(resource_paths.runtime_release_note_path(__version__).is_file())

    def test_unknown_resource_group_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown WOM-kit resource group"):
            resource_paths.runtime_resource_root("private-or-unknown")


if __name__ == "__main__":
    unittest.main()
