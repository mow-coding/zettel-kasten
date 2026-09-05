"""Source-mirror service checks tolerate allocation-only directory changes."""

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TESTS = Path(__file__).resolve().parent
for location in (TESTS.parent / "src", TESTS):
    if str(location) not in sys.path:
        sys.path.insert(0, str(location))

from wom_kit import archive_services
import test_cli as cli_fixtures


class SourceDirectoryIdentityTests(unittest.TestCase):
    def test_mirror_service_accepts_directory_size_change_but_rejects_file_drift(self):
        fixture_builder = cli_fixtures.ArchiveCliTests()
        self.addCleanup(fixture_builder.doCleanups)
        with tempfile.TemporaryDirectory(prefix="wom-source-identity-") as temporary:
            fixture = fixture_builder.create_project_version_update_fixture(Path(temporary))
            project = fixture["project_root"]
            mirror = fixture["mirror"]

            def observe():
                return archive_services.wom_kit_runtime_mirror_integrity(
                    project, mirror, fixture["metadata_root"] / "installed-version.txt",
                    mirror / "wom-kit" / "cli" / "archive.py",
                    source_version=fixture["old_version"],
                )

            baseline = observe()
            self.assertTrue(baseline["verified"], baseline)
            original_lstat = os.lstat
            changed_observations = []

            class DirectoryStat:
                def __init__(self, original, size):
                    self.original = original
                    self.st_size = size

                def __getattr__(self, name):
                    return getattr(self.original, name)

            def allocation_changes(path, *args, **kwargs):
                information = original_lstat(path, *args, **kwargs)
                if stat.S_ISDIR(information.st_mode):
                    size = 0 if len(changed_observations) % 2 == 0 else 4096
                    changed_observations.append(size)
                    return DirectoryStat(information, size)
                return information

            with mock.patch.object(os, "lstat", side_effect=allocation_changes):
                observed = observe()
            self.assertTrue(observed["verified"], observed)
            self.assertEqual(set(changed_observations), {0, 4096})
            source = fixture["unchanged_runtime_path"]
            original_bytes = source.read_bytes()
            source.write_bytes(original_bytes + b"# actual source change\n")
            with mock.patch.object(os, "lstat", side_effect=allocation_changes):
                drifted = observe()
            self.assertFalse(drifted["verified"], drifted)
            self.assertEqual(source.read_bytes(), original_bytes + b"# actual source change\n")


if __name__ == "__main__":
    unittest.main()
