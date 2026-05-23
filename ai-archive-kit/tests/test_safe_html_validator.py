from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ai_archive_kit import archive_cli  # noqa: E402


SAFE_DRAFT_BODY = (
    "# Safe Markdown draft\n\n"
    "This is a normal Markdown body with **emphasis**, a list, and a code reference.\n\n"
    "- one\n- two\n- three\n\n"
    "It contains no raw HTML, no scripts, no inline event handlers, and no javascript URLs.\n"
)
DRAFT_RELATIVE_PATH = "inbox/zet_20260519_draft_ai_lunch_note.md"


class SafeHtmlCheckTests(unittest.TestCase):
    def run_cli(self, args: list[str]) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = archive_cli.main(args)
        return code, buffer.getvalue()

    def copy_fake_archive(self, root: Path) -> Path:
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        return root

    def rewrite_draft_body(self, archive_root: Path, body: str) -> Path:
        path = archive_root / "inbox" / "zet_20260519_draft_ai_lunch_note.md"
        text = path.read_text(encoding="utf-8")
        match = archive_cli.FRONTMATTER_RE.match(text)
        self.assertIsNotNone(match)
        assert match is not None
        frontmatter_block = text[: match.end()]
        path.write_text(frontmatter_block + body, encoding="utf-8")
        return path

    def run_check(self, archive_root: Path) -> tuple[int, dict]:
        code, output = self.run_cli(
            [
                "check-safe-html",
                str(archive_root),
                "--path",
                DRAFT_RELATIVE_PATH,
                "--dry-run",
                "--format",
                "json",
            ]
        )
        return code, json.loads(output) if output.strip() else {}

    def test_safe_markdown_body_passes_with_no_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.rewrite_draft_body(archive_root, SAFE_DRAFT_BODY)

            code, result = self.run_check(archive_root)

            self.assertEqual(code, 0)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["lifecycle_action"], "check_safe_html")
            self.assertEqual(result["source_path"], "inbox/zet_20260519_draft_ai_lunch_note.md")
            self.assertEqual(result["detected_format"], "markdown_compatible")
            self.assertEqual(result["proposed_profile"], "wom-safe-html/v0.1-draft")
            self.assertEqual(result["blockers"], [])
            self.assertEqual(result["would_change"], [])
            self.assertEqual(
                result["html_profile_preview"]["blocked_elements"],
                ["script", "iframe", "object", "embed"],
            )
            self.assertEqual(result["html_profile_preview"]["detected_unsafe_categories"], [])
            self.assertGreater(result["text_extraction_preview"]["char_count"], 0)
            self.assertTrue(result["text_extraction_preview"]["has_yaml_frontmatter"])

    def test_script_tag_in_body_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.rewrite_draft_body(
                archive_root,
                "Body before.\n\n<script>alert('x')</script>\n\nBody after.\n",
            )

            code, result = self.run_check(archive_root)

            self.assertEqual(code, 1)
            self.assertFalse(result["ok"])
            self.assertTrue(any("<script>" in blocker for blocker in result["blockers"]))
            self.assertIn("script", result["html_profile_preview"]["detected_unsafe_categories"])

    def test_javascript_url_in_body_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.rewrite_draft_body(
                archive_root,
                "See this link: [click me](javascript:alert('x'))\n",
            )

            code, result = self.run_check(archive_root)

            self.assertEqual(code, 1)
            self.assertFalse(result["ok"])
            self.assertTrue(any("javascript:" in blocker for blocker in result["blockers"]))
            self.assertIn("javascript_url", result["html_profile_preview"]["detected_unsafe_categories"])

    def test_iframe_object_and_embed_tags_are_all_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.rewrite_draft_body(
                archive_root,
                "Body with three risky elements:\n\n"
                "<iframe src='https://example.test/'></iframe>\n"
                "<object data='https://example.test/'></object>\n"
                "<embed src='https://example.test/' />\n",
            )

            code, result = self.run_check(archive_root)

            self.assertEqual(code, 1)
            self.assertFalse(result["ok"])
            detected = result["html_profile_preview"]["detected_unsafe_categories"]
            self.assertIn("iframe", detected)
            self.assertIn("object", detected)
            self.assertIn("embed", detected)

    def test_inline_event_handler_attribute_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            self.rewrite_draft_body(
                archive_root,
                "Body with an inline event handler:\n\n"
                "<a href='/' onclick=\"steal()\">click</a>\n",
            )

            code, result = self.run_check(archive_root)

            self.assertEqual(code, 1)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("event handler" in blocker.lower() for blocker in result["blockers"])
            )
            self.assertIn(
                "inline_event_handler",
                result["html_profile_preview"]["detected_unsafe_categories"],
            )

    def test_dry_run_does_not_modify_the_zet_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            draft_path = self.rewrite_draft_body(
                archive_root,
                "Body with an unsafe element to make sure even blocked runs do not write.\n\n"
                "<script>alert('x')</script>\n",
            )
            before_bytes = draft_path.read_bytes()
            before_hash = hashlib.sha256(before_bytes).hexdigest()
            archive_files_before = sorted(
                str(p.relative_to(archive_root))
                for p in archive_root.rglob("*")
                if p.is_file()
            )

            code, _result = self.run_check(archive_root)
            self.assertEqual(code, 1)

            after_bytes = draft_path.read_bytes()
            after_hash = hashlib.sha256(after_bytes).hexdigest()
            self.assertEqual(before_bytes, after_bytes)
            self.assertEqual(before_hash, after_hash)
            archive_files_after = sorted(
                str(p.relative_to(archive_root))
                for p in archive_root.rglob("*")
                if p.is_file()
            )
            self.assertEqual(archive_files_before, archive_files_after)

    def test_check_safe_html_requires_dry_run_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = self.copy_fake_archive(Path(tmp) / "archive")
            code, output = self.run_cli(
                [
                    "check-safe-html",
                    str(archive_root),
                    "--path",
                    DRAFT_RELATIVE_PATH,
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertIn("--dry-run", output)


if __name__ == "__main__":
    unittest.main()
