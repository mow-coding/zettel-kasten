from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent
CHECKER_PATH = KIT_ROOT / "tools" / "check_public_links.py"

spec = importlib.util.spec_from_file_location("check_public_links", CHECKER_PATH)
assert spec is not None and spec.loader is not None
check_public_links = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_public_links
spec.loader.exec_module(check_public_links)


class PublicLinkHygieneTests(unittest.TestCase):
    def assert_problem_contains(self, problems, needle: str) -> None:
        formatted = "\n".join(problem.format() for problem in problems)
        self.assertIn(needle, formatted)

    def test_repo_markdown_local_links_resolve_case_sensitively(self) -> None:
        tracked = {"docs/Guide.md"}
        ok = check_public_links.check_markdown_text(
            markdown_path="README.md",
            text="[Guide](docs/Guide.md)",
            tracked=tracked,
            repo_root=REPO_ROOT,
        )
        self.assertEqual(ok, [])
        bad = check_public_links.check_markdown_text(
            markdown_path="README.md",
            text="[Guide](docs/guide.md)",
            tracked=tracked,
            repo_root=REPO_ROOT,
        )
        self.assertEqual(len(bad), 1)
        self.assert_problem_contains(bad, "case-sensitive path")

    def test_release_notes_reject_repo_local_relative_file_links(self) -> None:
        problems = check_public_links.check_markdown_text(
            markdown_path="wom-kit/docs/releases/v0.2.49.md",
            text="[Model](../zet-radio-frequency-recommendation-model.md)",
            tracked={"wom-kit/docs/zet-radio-frequency-recommendation-model.md"},
            repo_root=REPO_ROOT,
        )
        self.assertEqual(len(problems), 1)
        self.assert_problem_contains(problems, "GitHub Release bodies")

    def test_release_notes_reject_repo_local_relative_directory_links(self) -> None:
        problems = check_public_links.check_markdown_text(
            markdown_path="wom-kit/docs/releases/v0.2.49.md",
            text="[Examples](../examples/zet-radio-frequency-recommendation/)",
            tracked={"wom-kit/examples/zet-radio-frequency-recommendation/README.md"},
            repo_root=REPO_ROOT,
        )
        self.assertEqual(len(problems), 1)
        self.assert_problem_contains(problems, "GitHub Release bodies")

    def test_release_notes_accept_github_blob_links_to_tracked_files(self) -> None:
        url = "https://github.com/mow-coding/zettel-kasten/blob/main/wom-kit/docs/public-release-link-hygiene.md"
        problems = check_public_links.check_markdown_text(
            markdown_path="wom-kit/docs/releases/v0.2.49.md",
            text=f"[Link Hygiene]({url})",
            tracked={"wom-kit/docs/public-release-link-hygiene.md"},
            repo_root=REPO_ROOT,
        )
        self.assertEqual(problems, [])

    def test_release_notes_reject_github_blob_links_to_untracked_files(self) -> None:
        url = "https://github.com/mow-coding/zettel-kasten/blob/main/wom-kit/docs/missing-public-doc.md"
        problems = check_public_links.check_markdown_text(
            markdown_path="wom-kit/docs/releases/v0.2.49.md",
            text=f"[Missing]({url})",
            tracked={"wom-kit/docs/public-release-link-hygiene.md"},
            repo_root=REPO_ROOT,
        )
        self.assertEqual(len(problems), 1)
        self.assert_problem_contains(problems, "not tracked")

    def test_release_notes_reject_bad_github_tree_file_links(self) -> None:
        url = "https://github.com/mow-coding/zettel-kasten/tree/main/wom-kit/docs/public-release-link-hygiene.md"
        problems = check_public_links.check_markdown_text(
            markdown_path="wom-kit/docs/releases/v0.2.49.md",
            text=f"[Bad]({url})",
            tracked={"wom-kit/docs/public-release-link-hygiene.md"},
            repo_root=REPO_ROOT,
        )
        self.assertEqual(len(problems), 1)
        self.assert_problem_contains(problems, "use /blob/")

    def test_release_notes_accept_github_tree_links_to_tracked_directories(self) -> None:
        url = "https://github.com/mow-coding/zettel-kasten/tree/main/wom-kit/docs/releases"
        problems = check_public_links.check_markdown_text(
            markdown_path="wom-kit/docs/releases/v0.2.49.md",
            text=f"[Releases]({url})",
            tracked={"wom-kit/docs/releases/v0.2.49.md"},
            repo_root=REPO_ROOT,
        )
        self.assertEqual(problems, [])

    def test_full_checker_passes_current_repository(self) -> None:
        problems = check_public_links.check_public_links(REPO_ROOT)
        self.assertEqual([problem.format() for problem in problems], [])


if __name__ == "__main__":
    unittest.main()
