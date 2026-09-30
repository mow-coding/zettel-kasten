"""Beta letter 177: rebuildable index snapshots never become Git changes.

Every index run writes search, relation and title snapshots under db/; the
search snapshot is a full copy of the archive index. In archives whose root
.gitignore predates those folders they appeared as untracked changes, and a
large archive's general Git backup stopped at the file size limit on one. Each
snapshot folder now carries a self-ignoring .gitignore, so this holds for old
archives too; new archives also get the patterns in their root .gitignore.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from wom_kit import archive_cli, archive_services as services

KIT_ROOT = Path(__file__).resolve().parents[1]
OLD_ROOT_GITIGNORE_WITHOUT_SNAPSHOTS = "\n".join([
    "profiles/local/", ".wom-scratch/", "**/db/archive-index.sqlite", "**/db/archive-index.sqlite-wal",
    "**/db/archive-index.sqlite-shm", "**/db/archive-index.sqlite-journal", "objects/sha256/", "",
])


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


class SnapshotGitIgnoreTests(unittest.TestCase):
    def archive(self, gitignore=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        if gitignore is not None:
            (root / ".gitignore").write_text(gitignore, encoding="utf-8")
        _git(root, "init", "-q")
        _git(root, "-c", "core.autocrlf=false", "add", "-A")
        _git(root, "-c", "user.email=synthetic@example.invalid", "-c", "user.name=synthetic", "commit", "-qm", "base")
        return root

    def changed(self, root):
        return [line[3:] for line in _git(root, "status", "--porcelain", "--untracked-files=all").splitlines()]

    def test_index_snapshots_are_not_git_changes_in_an_old_archive(self):
        root = self.archive(OLD_ROOT_GITIGNORE_WITHOUT_SNAPSHOTS)
        self.assertTrue(services.index_archive(root)["ok"])
        for folder in ("search-snapshots", "relation-snapshots", "title-snapshots"):
            self.assertTrue(any((root / "db" / folder).glob("*")), folder)
            self.assertEqual((root / "db" / folder / ".gitignore").read_bytes(),
                             services.DERIVED_DIRECTORY_GITIGNORE)
        self.assertEqual([path for path in self.changed(root) if "snapshots/" in path], [])

    def test_a_new_archive_has_no_changes_after_indexing(self):
        root = self.archive()
        self.assertTrue(services.index_archive(root)["ok"])
        self.assertEqual(self.changed(root), [])

    def test_an_existing_folder_gitignore_is_left_alone(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        (folder / ".gitignore").write_bytes(b"custom\n")
        services.ensure_derived_directory_ignored(folder)
        self.assertEqual((folder / ".gitignore").read_bytes(), b"custom\n")

    def test_init_template_lists_the_snapshot_folders(self):
        template = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, template, True)
        archive_cli._write_safe_gitignore(template)
        text = (template / ".gitignore").read_text(encoding="utf-8")
        example = (KIT_ROOT / "examples" / "fake-life-archive" / ".gitignore").read_text(encoding="utf-8")
        for pattern in ("**/db/search-snapshots/", "**/db/relation-snapshots/", "**/db/title-snapshots/",
                        "**/db/finder-snapshots/"):
            self.assertIn(pattern, text)
            self.assertIn(pattern, example)


if __name__ == "__main__":
    unittest.main()
