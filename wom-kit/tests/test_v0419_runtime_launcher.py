"""Target-version launcher compatibility, independent of the running updater."""

from pathlib import Path
import sys
import tempfile
import unittest
import zipfile


TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.append(str(TESTS_ROOT))

from wom_kit import project_runtime
from test_project_runtime import _write_minimal_wheel


class RuntimeLauncherCompatibilityTests(unittest.TestCase):
    def test_old_targets_keep_exact_historical_launcher_bytes(self):
        for version in ("0.3.320", "0.4.3", "0.4.18"):
            with self.subTest(version=version):
                expected = (
                    "@echo off\r\nsetlocal\r\n"
                    'set "PYTHONDONTWRITEBYTECODE=1"\r\n'
                    'set "PYTHONNOUSERSITE=1"\r\n'
                    'set "PYTHONSAFEPATH=1"\r\n'
                    f'"%~dp0..\\runtimes\\v{version}\\Scripts\\python.exe" '
                    '-I -B -X utf8 -m wom_kit.archive_cli %*\r\n'
                ).encode("utf-8")
                self.assertEqual(project_runtime.launcher_bytes(version), expected)
                self.assertEqual(project_runtime.launcher_bytes("v" + version), expected)

    def test_new_targets_use_bootstrap_by_numeric_version_not_string_order(self):
        for version in ("0.4.19", "0.4.20", "0.5.0", "0.10.0", "1.0.0"):
            with self.subTest(version=version):
                result = project_runtime.launcher_bytes(version)
                self.assertIn(b"-I -B -X utf8 -m wom_kit.cli_entry %*\r\n", result)
                self.assertNotIn(b"wom_kit.archive_cli", result)
                self.assertIn(f"runtimes\\v{version}".encode(), result)

    def test_synthetic_wheel_has_bootstrap_only_when_target_release_has_it(self):
        with tempfile.TemporaryDirectory(prefix="wom-launcher-wheel-") as temporary:
            for version in ("0.4.18", "0.4.19"):
                with self.subTest(version=version), zipfile.ZipFile(_write_minimal_wheel(Path(temporary), version)) as wheel:
                    self.assertEqual("wom_kit/cli_entry.py" in wheel.namelist(), version == "0.4.19")


if __name__ == "__main__":
    unittest.main()
