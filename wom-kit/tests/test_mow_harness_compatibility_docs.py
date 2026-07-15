from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from wom_kit import archive_cli


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent


class MowHarnessCompatibilityDocsTests(unittest.TestCase):
    def run_archive_cli(self, args: list[str]) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = archive_cli.main(args)
        return code, buffer.getvalue()

    def test_optional_harness_boundary_is_public_and_fail_closed(self) -> None:
        guide = (KIT_ROOT / "docs" / "mow-harness-compatibility.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "WOM works without MOW Harness",
            "<archive-root>/collab/",
            "<archive-root>/.mow-harness/",
            "is still a source alpha and is not published to npm",
            "--adopt --dry-run",
            "--adopt --yes",
            "Installing or updating files does not turn MOW Harness on",
            "does not call the MOW CLI",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)

        archive_cli = (KIT_ROOT / "src" / "wom_kit" / "archive_cli.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"/collab/"', archive_cli)
        self.assertIn('"/.mow-harness/"', archive_cli)

    def test_public_navigation_and_capability_matrix_link_the_boundary(self) -> None:
        for relative_path in (
            "docs/ai-assisted-onboarding-and-provider-setup.md",
            "docs/project-intake-session.md",
            "docs/public-documentation-map.md",
            "docs/public-documentation-map.ko.md",
        ):
            with self.subTest(path=relative_path):
                text = (KIT_ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("mow-harness-compatibility.md", text)

        matrix = (KIT_ROOT / "docs" / "capability-matrix.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Optional MOW Harness compatibility", matrix)
        self.assertIn("implemented namespace isolation", matrix)
        self.assertIn("grants no Harness write or activation approval", matrix)

    def test_harness_namespaces_never_enter_catalog_or_zettel_read_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "archive"
            shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", archive_root)
            harness_files = {
                archive_root / "collab" / "STATE.md": b"PRIVATE HARNESS STATE MUST NOT BECOME A ZET\n",
                archive_root / ".mow-harness" / "operator-note.md": b"PRIVATE HARNESS NOTE MUST NOT BECOME A ZET\n",
            }
            for path, content in harness_files.items():
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
            self.assertNotIn("PRIVATE HARNESS", output)

            for relative_path in ("collab/STATE.md", ".mow-harness/operator-note.md"):
                with self.subTest(path=relative_path):
                    read_code, read_output = self.run_archive_cli(
                        ["read-zettel", str(archive_root), "--path", relative_path]
                    )
                    self.assertEqual(read_code, 1, read_output)
                    self.assertIn("inbox/ or zettels", read_output)

            for path, content in harness_files.items():
                self.assertEqual(path.read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
