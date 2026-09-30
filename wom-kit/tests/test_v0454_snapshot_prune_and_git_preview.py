"""v0.4.54 (letter 177 follow-up): old index snapshots are deleted; the Git preview reads private remotes.

Every index run published a new generation in db/search-snapshots (a full copy
of the index), db/relation-snapshots, db/title-snapshots and
db/finder-snapshots, and nothing removed the old ones, so they kept growing on
the operator's disk. Old generations are now deleted after each run; the
current one, the newest other one and anything younger than an hour stay. A
generation that an earlier backup had already committed to Git then shows up
only as a small deletion, which the next backup records.

The general Git backup preview read the remote without a login by default, so
a private backup repository was reported as "remote ref not observable". It
now uses the Git login already saved on the PC by default, like the session
backup and the writer, and says what to do when the remote cannot be read.

Synthetic example archive; no network, no client data.
"""

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from wom_kit import archive_cli, archive_services as services
from wom_kit import git_backup_plan as planning

KIT_ROOT = Path(__file__).resolve().parents[1]


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


class SnapshotPruneTests(unittest.TestCase):
    def archive(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", root)
        return root

    def age_generations(self, root, seconds=7200):
        past = time.time() - seconds
        for folder in ("search-snapshots", "relation-snapshots", "title-snapshots"):
            for path in (root / "db" / folder).glob("*"):
                if path.name not in {".gitignore", "latest.json"}:
                    os.utime(path, (past, past))

    def edit_a_zettel(self, root, run):
        zettel = sorted((root / "zettels").rglob("*.md"))[0]
        with zettel.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(f"\nsynthetic edit {run}\n")

    def generations(self, root, folder):
        return sorted(path.name for path in (root / "db" / folder).glob("*")
                      if path.name not in {".gitignore", "latest.json"})

    def test_repeated_index_runs_keep_at_most_two_generations(self):
        root = self.archive()
        for run in range(5):
            if run:
                self.edit_a_zettel(root, run)
            self.assertTrue(services.index_archive(root)["ok"])
            self.age_generations(root)
        for folder in ("search-snapshots", "relation-snapshots", "title-snapshots"):
            with self.subTest(folder=folder):
                self.assertLessEqual(len(self.generations(root, folder)), 2, self.generations(root, folder))
        latest = services.load_yaml((root / "db" / "search-snapshots" / "latest.json").read_text(encoding="utf-8"))
        self.assertIn(latest["snapshot"] + ".sqlite", self.generations(root, "search-snapshots"))

    def test_young_generations_are_kept_for_open_cursors(self):
        root = self.archive()
        for run in range(4):
            if run:
                self.edit_a_zettel(root, run)
            self.assertTrue(services.index_archive(root)["ok"])
        self.assertEqual(len(self.generations(root, "search-snapshots")), 4)

    def test_a_committed_old_generation_becomes_a_small_deletion(self):
        root = self.archive()
        (root / ".gitignore").write_text("**/db/archive-index.sqlite*\nobjects/sha256/\n", encoding="utf-8")
        _git(root, "init", "-q")
        self.assertTrue(services.index_archive(root)["ok"])
        # an archive that committed its snapshots before v0.4.53
        _git(root, "-c", "core.autocrlf=false", "add", "-A", "-f")
        _git(root, "-c", "user.email=synthetic@example.invalid", "-c", "user.name=synthetic", "commit", "-qm", "base")
        committed = set(self.generations(root, "search-snapshots"))
        self.age_generations(root)
        for run in (1, 2, 3):
            self.edit_a_zettel(root, run)
            self.assertTrue(services.index_archive(root)["ok"])
            self.age_generations(root)
        status = _git(root, "status", "--porcelain", "--untracked-files=all").splitlines()
        snapshot_rows = [line for line in status if "snapshots/" in line]
        self.assertTrue(snapshot_rows)
        for line in snapshot_rows:
            with self.subTest(line=line):
                self.assertTrue(line.startswith(" D ") or line.endswith("latest.json"), line)
        self.assertFalse(committed & set(self.generations(root, "search-snapshots")))

    def test_only_wom_named_files_are_deleted(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        past = time.time() - 90000
        names = [("%064x" % index) + ".sqlite" for index in range(4)]
        for name in [*names, "notes.txt", "latest.json", ".gitignore", ("b" * 32) + ".building"]:
            (folder / name).write_bytes(b"x")
            os.utime(folder / name, (past, past))
        removed = services.prune_derived_generations(folder, keep_digest="%064x" % 3)
        self.assertEqual(removed, 3)  # two old generations and the abandoned partial file
        self.assertEqual(sorted(path.name for path in folder.iterdir()),
                         sorted([".gitignore", "latest.json", "notes.txt", names[0], names[3]]))


class GitPreviewCredentialTests(unittest.TestCase):
    def test_the_preview_reads_with_the_saved_git_login_by_default(self):
        parser = archive_cli.build_parser()
        args = parser.parse_args(["git-backup-plan", "PRIVATE_ROOT", "--dry-run"])
        self.assertEqual(args.credential_mode, "stored")
        args = parser.parse_args(["git-backup-plan", "PRIVATE_ROOT", "--dry-run", "--credential-mode", "anonymous"])
        self.assertEqual(args.credential_mode, "anonymous")

    def test_an_unreadable_remote_names_the_next_step(self):
        anonymous = planning._remote_blocker_guidance(["git_transport_ref_observation_unavailable"], "anonymous")
        self.assertEqual(len(anonymous), 1)
        self.assertIn("--credential-mode stored", anonymous[0])
        stored = planning._remote_blocker_guidance(["git_transport_ref_observation_unavailable"], "stored")
        self.assertIn("git fetch", stored[0])
        unsafe = planning._remote_blocker_guidance(["configured_remote_unavailable_or_unsafe"], "stored")
        self.assertIn("https://", unsafe[0])
        self.assertEqual(planning._remote_blocker_guidance(["changed_item_limit_exceeded"], "stored"), [])


if __name__ == "__main__":
    unittest.main()
