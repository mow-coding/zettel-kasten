from __future__ import annotations

from collections import Counter
from contextlib import redirect_stderr
import io
import os
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest import mock

from wom_kit import archive_cli, archive_services, process_launch, project_runtime


PACKAGE_ROOT = Path(archive_cli.__file__).resolve().parent
DIRECT_SUBPROCESS_RE = re.compile(r"\bsubprocess\.(?:run|Popen)\s*\(")
CREATIONFLAGS_RE = re.compile(r"\bcreationflags\s*=")


class WindowsChildProcessPolicyTests(unittest.TestCase):
    def test_windows_policy_preserves_existing_flags_and_adds_no_window(self) -> None:
        existing = 0x00000200
        with mock.patch.object(process_launch, "_IS_WINDOWS", True):
            flags = process_launch.noninteractive_creationflags(existing)

        self.assertEqual(flags & existing, existing)
        self.assertEqual(
            flags & process_launch.WINDOWS_CREATE_NO_WINDOW,
            process_launch.WINDOWS_CREATE_NO_WINDOW,
        )

    def test_non_windows_policy_keeps_portable_zero(self) -> None:
        with mock.patch.object(process_launch, "_IS_WINDOWS", False):
            self.assertEqual(process_launch.noninteractive_creationflags(), 0)

    def test_policy_rejects_ambiguous_or_negative_flags(self) -> None:
        for value in (True, -1, "0"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError,
                    "noninteractive_creationflags_invalid",
                ):
                    process_launch.noninteractive_creationflags(value)  # type: ignore[arg-type]

    def test_project_runtime_background_python_uses_no_console_policy(self) -> None:
        process = mock.Mock()
        process.poll.return_value = 0
        process.returncode = 0
        process.stdout = None
        events: list[tuple[str, str, int | None, int | None]] = []
        with (
            mock.patch.object(process_launch, "_IS_WINDOWS", True),
            mock.patch.object(
                project_runtime.subprocess,
                "Popen",
                return_value=process,
            ) as popen,
        ):
            project_runtime._run_bounded(
                ["python", "-I", "-c", "pass"],
                stage="runtime_probe",
                callback=lambda *event: events.append(event),
            )

        flags = popen.call_args.kwargs["creationflags"]
        self.assertEqual(
            flags & process_launch.WINDOWS_CREATE_NO_WINDOW,
            process_launch.WINDOWS_CREATE_NO_WINDOW,
        )
        self.assertEqual(events[0][:2], ("runtime_probe", "start"))
        self.assertEqual(events[-1][:2], ("runtime_probe", "done"))

    def test_direct_production_subprocess_calls_declare_visibility(self) -> None:
        """Every direct child launch is hidden or explicitly human-visible."""

        direct_call_count = 0
        declared_visibility_count = 0
        for source in sorted(PACKAGE_ROOT.glob("*.py")):
            text = source.read_text(encoding="utf-8")
            direct_call_count += len(DIRECT_SUBPROCESS_RE.findall(text))
            declared_visibility_count += len(CREATIONFLAGS_RE.findall(text))

        # The one intentional exception is _run_keepassxc_cli_add: its local
        # database-unlock prompt belongs to the human and must stay visible.
        self.assertGreater(direct_call_count, 0)
        self.assertEqual(direct_call_count, declared_visibility_count + 1)

    def test_project_bridge_bootstrap_hides_its_git_child(self) -> None:
        source = archive_services.WOM_KIT_PROJECT_BRIDGE_BOOTSTRAP
        self.assertEqual(len(DIRECT_SUBPROCESS_RE.findall(source)), 1)
        self.assertEqual(len(CREATIONFLAGS_RE.findall(source)), 1)

    def test_keepassxc_human_unlock_prompt_is_not_hidden(self) -> None:
        completed = mock.Mock(returncode=0)
        with mock.patch.object(
            archive_services.subprocess,
            "run",
            return_value=completed,
        ) as run:
            result = archive_services._run_keepassxc_cli_add(["keepassxc-cli"])

        self.assertEqual(result, 0)
        self.assertNotIn("creationflags", run.call_args.kwargs)


class DoctorGenerationProjectionTests(unittest.TestCase):
    def test_tree_inventory_projects_each_entry_from_one_lstat_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "archive"
            nested = root / "nested"
            nested.mkdir(parents=True)
            file_path = nested / "record.json"
            file_path.write_text('{"safe":true}\n', encoding="utf-8")
            doctor = archive_cli.Doctor(root)
            real_scandir = os.scandir
            real_lstat = os.lstat
            observed: list[Path] = []

            class EntryProjection:
                def __init__(self, entry: os.DirEntry[str]) -> None:
                    self.name = entry.name
                    self.path = entry.path

                def stat(self, *, follow_symlinks: bool = True) -> os.stat_result:
                    raise AssertionError("inventory_repeated_direntry_stat")

            class ProjectedScandir:
                def __init__(self, path: object) -> None:
                    with real_scandir(path) as iterator:
                        self.entries = [EntryProjection(item) for item in iterator]

                def __enter__(self) -> list[EntryProjection]:
                    return self.entries

                def __exit__(self, *_args: object) -> None:
                    return None

            def counted_lstat(path: object) -> os.stat_result:
                observed.append(Path(path))
                return real_lstat(path)

            with (
                mock.patch.object(
                    archive_cli.os,
                    "scandir",
                    side_effect=ProjectedScandir,
                ),
                mock.patch.object(
                    archive_cli.os,
                    "lstat",
                    side_effect=counted_lstat,
                ),
            ):
                doctor._check_symlink_boundaries()

            canonical_root = doctor.archive_root
            canonical_nested = canonical_root / "nested"
            canonical_file = canonical_nested / "record.json"
            counts = Counter(observed)
            # The root has its separate immutable boundary revalidation; the
            # performance regression concerned each scandir child generation.
            self.assertGreaterEqual(counts[canonical_root], 1)
            self.assertEqual(counts[canonical_nested], 1)
            self.assertEqual(counts[canonical_file], 1)
            self.assertTrue(doctor._archive_tree_inventory_complete)
            self.assertIn(
                doctor._archive_tree_key("nested/record.json"),
                doctor._archive_tree_file_identities,
            )

    def test_doctor_progress_starts_immediately_and_heartbeats_independently(self) -> None:
        output = io.StringIO()
        with redirect_stderr(output):
            reporter = archive_cli.CommandProgressReporter(
                True,
                label="doctor",
                heartbeat_interval_seconds=0.02,
            )
            try:
                reporter.progress("doctor-run", "start", None, None)
                threading.Event().wait(0.06)
            finally:
                reporter.close()

        lines = output.getvalue().splitlines()
        self.assertTrue(lines)
        self.assertIn("[doctor] doctor-run: start", lines[0])
        self.assertTrue(
            any("[doctor] doctor-run: heartbeat" in line for line in lines[1:])
        )


if __name__ == "__main__":
    unittest.main()
