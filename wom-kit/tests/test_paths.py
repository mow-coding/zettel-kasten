from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit.paths import (  # noqa: E402
    ArchivePathError,
    archive_relative_path,
    contains_forbidden_location_reference,
    normalize_archive_relative_path,
    resolve_archive_relative_path,
)


class ArchivePathTests(unittest.TestCase):
    def test_archive_relative_paths_are_posix_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            target = root / "inbox" / "draft.md"
            target.parent.mkdir(parents=True)
            target.write_text("draft", encoding="utf-8")

            self.assertEqual(archive_relative_path(target, root), "inbox/draft.md")

    def test_normalize_accepts_windows_and_posix_relative_input(self) -> None:
        self.assertEqual(normalize_archive_relative_path("inbox\\draft.md"), "inbox/draft.md")
        self.assertEqual(normalize_archive_relative_path("inbox/draft.md"), "inbox/draft.md")

    def test_normalize_rejects_absolute_or_escaping_input(self) -> None:
        unsafe_paths = [
            "../archive.yml",
            "inbox/../archive.yml",
            "/home/example/archive.yml",
            "C:\\Users\\example\\archive.yml",
            "\\\\server\\share\\archive.yml",
        ]
        for unsafe_path in unsafe_paths:
            with self.subTest(unsafe_path=unsafe_path):
                with self.assertRaises(ArchivePathError):
                    normalize_archive_relative_path(unsafe_path)

    def test_resolve_archive_relative_path_stays_inside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()

            resolved = resolve_archive_relative_path(root, "views\\homebase.yml")
            self.assertEqual(archive_relative_path(resolved, root), "views/homebase.yml")

            with self.assertRaises(ArchivePathError):
                resolve_archive_relative_path(root, "../outside.yml")

    def test_forbidden_location_reference_detects_provider_and_local_absolute_paths(self) -> None:
        unsafe_texts = [
            "source is s3://bucket/key",
            "source is C:\\Users\\example\\private.txt",
            "source is /Users/example/private.txt",
            "source is /home/example/private.txt",
        ]
        for unsafe_text in unsafe_texts:
            with self.subTest(unsafe_text=unsafe_text):
                self.assertTrue(contains_forbidden_location_reference(unsafe_text))

        self.assertFalse(contains_forbidden_location_reference("source is objects/sample/fake.txt"))
        self.assertFalse(contains_forbidden_location_reference("see https://example.com/home/page"))


if __name__ == "__main__":
    unittest.main()
