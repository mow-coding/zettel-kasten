from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
CHECKER_PATH = KIT_ROOT / "tools" / "check_artifact_hygiene.py"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

spec = importlib.util.spec_from_file_location("check_artifact_hygiene", CHECKER_PATH)
assert spec is not None and spec.loader is not None
check_artifact_hygiene = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_artifact_hygiene
spec.loader.exec_module(check_artifact_hygiene)

from wom_kit import archive_cli  # noqa: E402


class ArtifactHygieneTests(unittest.TestCase):
    def run_archive_cli(self, args: list[str]) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer), redirect_stderr(buffer):
            code = archive_cli.main(args)
        return code, buffer.getvalue()

    def test_classifies_core_artifact_paths(self) -> None:
        examples = {
            "archive.yml": check_artifact_hygiene.DURABLE_ARCHIVE_RECORD,
            "objects/manifests/files.jsonl": check_artifact_hygiene.DURABLE_ARCHIVE_RECORD,
            "source-maps/notion.jsonl": check_artifact_hygiene.DURABLE_ARCHIVE_RECORD,
            "receipts/mint/example.json": check_artifact_hygiene.DURABLE_ARCHIVE_RECORD,
            "inbox/draft.md": check_artifact_hygiene.DURABLE_UNTIL_RESOLVED,
            "workpacks/export/package.yml": check_artifact_hygiene.DURABLE_WITH_EXPIRY,
            "db/archive-index.sqlite": check_artifact_hygiene.REBUILDABLE_GENERATED,
            "tmp/session/report.json": check_artifact_hygiene.DISPOSABLE_AFTER_REVIEW,
            "profiles/local/source-roots.local.yml": check_artifact_hygiene.LOCAL_ONLY_SECRET_CONFIG,
            ".mow-harness/installed-version.txt": check_artifact_hygiene.LOCAL_ONLY_COLLAB_HARNESS,
            "collab/STATE.md": check_artifact_hygiene.LOCAL_ONLY_COLLAB_HARNESS,
        }
        for path, expected in examples.items():
            with self.subTest(path=path):
                self.assertEqual(check_artifact_hygiene.classify_artifact(path).category, expected)

    def test_missing_archive_gitignore_patterns_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            (root / "archive.yml").write_text("archive_id: archive:test\n", encoding="utf-8")
            (root / ".gitignore").write_text("profiles/local/\n", encoding="utf-8")

            problems = check_artifact_hygiene.check_archive_gitignore(root)
            formatted = "\n".join(problem.format() for problem in problems)

        self.assertIn("Missing generated archive .gitignore pattern: .env", formatted)
        self.assertIn("Missing generated archive .gitignore pattern: /.mow-harness/", formatted)
        self.assertIn("Missing generated archive .gitignore pattern: **/db/archive-index.sqlite", formatted)

    def test_throwaway_archive_init_gitignore_passes_artifact_hygiene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp) / "throwaway-personal-archive"
            code, output = self.run_archive_cli(
                [
                    "init",
                    str(archive_root),
                    "--type",
                    "personal",
                    "--archive-id",
                    "archive:personal:artifact-hygiene",
                    "--principal-id",
                    "person:test",
                    "--principal-name",
                    "Test Person",
                    "--name",
                    "Test Personal Archive",
                ]
            )
            self.assertEqual(code, 0, output)

            report = check_artifact_hygiene.check_artifact_hygiene(archive_root)

        self.assertTrue(report.passed, "\n".join(problem.format() for problem in report.problems))
        categories = report.category_counts()
        self.assertGreater(categories[check_artifact_hygiene.DURABLE_ARCHIVE_RECORD], 0)
        self.assertEqual(categories[check_artifact_hygiene.LOCAL_ONLY_COLLAB_HARNESS], 0)

    def test_external_live_objets_store_is_not_scanned_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "zettel-kasten-username-objets"
            root.mkdir()
            (root / "private-source-name.pdf").write_text("placeholder", encoding="utf-8")

            report = check_artifact_hygiene.check_artifact_hygiene(root)

        self.assertFalse(report.passed)
        self.assertEqual(report.observations, ())
        formatted = "\n".join(problem.format() for problem in report.problems)
        self.assertIn(check_artifact_hygiene.EXTERNAL_LIVE_NEVER_TOUCH, formatted)

    def test_external_live_archive_root_is_not_scanned_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "zettel-kasten-username"
            root.mkdir()
            (root / "archive.yml").write_text("archive_id: archive:personal:username\n", encoding="utf-8")

            report = check_artifact_hygiene.check_artifact_hygiene(root)

        self.assertFalse(report.passed)
        self.assertEqual(report.observations, ())
        formatted = "\n".join(problem.format() for problem in report.problems)
        self.assertIn(check_artifact_hygiene.EXTERNAL_LIVE_NEVER_TOUCH, formatted)

    def test_main_returns_nonzero_for_report_only_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            root.mkdir()
            (root / "archive.yml").write_text("archive_id: archive:test\n", encoding="utf-8")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = check_artifact_hygiene.main(["--target", str(root)])
            output = buffer.getvalue()

        self.assertEqual(code, 1)
        self.assertIn("No files were changed", output)

    def test_checker_source_has_no_mutation_network_or_provider_behavior(self) -> None:
        source = CHECKER_PATH.read_text(encoding="utf-8")
        banned = (
            ".write_text(",
            ".unlink(",
            ".rmdir(",
            "shutil",
            "subprocess",
            "requests",
            "urllib.request",
            "provider_api",
        )
        for needle in banned:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, source)


if __name__ == "__main__":
    unittest.main()
