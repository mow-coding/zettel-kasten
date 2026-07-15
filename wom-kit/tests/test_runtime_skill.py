from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = KIT_ROOT / "tools" / "check_runtime_skill.py"
SKILL_ROOT = KIT_ROOT / "templates" / "ai-runtime" / "wom-archive"

spec = importlib.util.spec_from_file_location("check_runtime_skill", CHECKER_PATH)
assert spec is not None and spec.loader is not None
check_runtime_skill = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_runtime_skill
spec.loader.exec_module(check_runtime_skill)


class RuntimeSkillTests(unittest.TestCase):
    def test_bundled_runtime_skill_passes(self) -> None:
        report = check_runtime_skill.check_runtime_skill(SKILL_ROOT)

        self.assertTrue(report.passed, "\n".join(report.problems))
        self.assertEqual(report.name, "wom-archive")
        self.assertLessEqual(report.root_lines, 200)
        self.assertGreaterEqual(report.reference_count, 6)

    def test_frontmatter_name_must_match_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "wrong-directory"
            references = root / "references"
            references.mkdir(parents=True)
            (root / "SKILL.md").write_text(
                "---\nname: another-name\ndescription: Test skill.\n---\n\n"
                "[One](references/one.md)\n[Two](references/two.md)\n",
                encoding="utf-8",
            )
            (references / "one.md").write_text("# One\n", encoding="utf-8")
            (references / "two.md").write_text("# Two\n", encoding="utf-8")

            report = check_runtime_skill.check_runtime_skill(root)

        self.assertFalse(report.passed)
        self.assertIn("frontmatter.name must match directory name 'wrong-directory'", report.problems)

    def test_broken_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "test-skill"
            references = root / "references"
            references.mkdir(parents=True)
            (root / "SKILL.md").write_text(
                "---\nname: test-skill\ndescription: Test skill.\n---\n\n"
                "[Missing](references/missing.md)\n[One](references/one.md)\n",
                encoding="utf-8",
            )
            (references / "one.md").write_text("# One\n", encoding="utf-8")

            report = check_runtime_skill.check_runtime_skill(root)

        self.assertFalse(report.passed)
        self.assertTrue(any("broken Markdown link" in problem for problem in report.problems))

    def test_reference_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "test-skill"
            references = root / "references"
            references.mkdir(parents=True)
            (root / "SKILL.md").write_text(
                "---\nname: test-skill\ndescription: Test skill.\n---\n\n"
                "[Escape](../outside.md)\n[One](references/one.md)\n"
                "[Two](references/two.md)\n",
                encoding="utf-8",
            )
            (references / "one.md").write_text("# One\n", encoding="utf-8")
            (references / "two.md").write_text("# Two\n", encoding="utf-8")

            report = check_runtime_skill.check_runtime_skill(root)

        self.assertFalse(report.passed)
        self.assertTrue(any("escapes skill root" in problem for problem in report.problems))


if __name__ == "__main__":
    unittest.main()
