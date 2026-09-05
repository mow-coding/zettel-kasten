"""Fresh-process startup is observable without changing command authority."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import types
import unittest
from unittest import mock

import wom_kit
from wom_kit import cli_entry
from wom_kit.process_launch import noninteractive_creationflags


KIT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = KIT_ROOT / "src"


class CliStartupContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        cli_entry.handoff_startup_progress()

    def test_public_progress_names_and_defaults_match_actual_parser(self) -> None:
        from wom_kit import archive_cli

        observed: dict[str, bool] = {}

        def visit(parser: object, path: tuple[str, ...]) -> None:
            for action in parser._actions:
                if "--progress" in action.option_strings:
                    observed[" ".join(path)] = bool(parser.get_default(action.dest))
                if isinstance(getattr(action, "choices", None), dict):
                    for name, child in action.choices.items():
                        if hasattr(child, "_actions"):
                            visit(child, (*path, name))

        visit(archive_cli.build_parser(), ())
        self.assertEqual(cli_entry.STARTUP_PROGRESS_DEFAULTS, observed)

    def test_only_existing_requested_progress_modes_start(self) -> None:
        cases = [
            ([], False),
            (["unknown_private_marker", "--progress"], False),
            (["doctor"], True),
            (["source-intake-batch"], True),
            (["objet-capture-batch"], True),
            (["project-version-update"], False),
            (["project-version-update", "--progress"], True),
            (["runtime-context", "--progress"], True),
            (["doctor", "--no-progress"], False),
            (["doctor", "--progress", "--no-progress"], False),
            (["doctor", "--no-progress", "--progress"], False),
            (["doctor", "--help"], False),
            (["doctor", "-h"], False),
            (["doctor", "--version"], False),
            (["--version"], False),
            (["version"], False),
            (["project-version-update", "--", "--progress"], False),
            (["project-version-update", "--progress-log=--progress"], False),
            (["doctor", "--", "--no-progress"], True),
        ]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertEqual(cli_entry.startup_progress_requested(argv), expected)

    def test_exact_version_is_fast_and_other_arguments_keep_original_dispatch(self) -> None:
        fake = types.ModuleType("wom_kit.archive_cli")
        fake.main = mock.Mock(return_value=17)
        output = io.StringIO()
        with mock.patch.object(wom_kit, "archive_cli", fake, create=True), \
                mock.patch.dict(sys.modules, {"wom_kit.archive_cli": fake}), \
                mock.patch.object(cli_entry, "_start_startup_progress") as start, \
                contextlib.redirect_stdout(output):
            self.assertEqual(cli_entry.main(["--version"]), 0)
            self.assertEqual(output.getvalue(), f"archive {wom_kit.__version__}\n")
            fake.main.assert_not_called()
            start.assert_not_called()
            start.return_value = None
            argv = ["--version", "private_argument_marker"]
            self.assertEqual(cli_entry.main(argv), 17)
            fake.main.assert_called_once_with(argv)
            self.assertEqual(argv, ["--version", "private_argument_marker"])

    def test_child_has_fixed_program_minimal_environment_and_no_console(self) -> None:
        process = mock.Mock()
        process.wait.return_value = 0
        output = io.StringIO()
        with contextlib.redirect_stderr(output), \
                mock.patch.dict(os.environ, {"SECRET_TEST_MARKER": "private_secret_marker"}), \
                mock.patch("subprocess.Popen", return_value=process) as popen:
            watchdog = cli_entry._start_startup_progress(
                ["doctor", "private_path_marker", "--progress"]
            )
        self.assertIsNotNone(watchdog)
        watchdog.close()
        watchdog.close()
        args, kwargs = popen.call_args
        self.assertEqual(args[0], [sys.executable, "-I", "-B", "-c", cli_entry._WATCHDOG_PROGRAM])
        self.assertLessEqual(set(kwargs["env"]), {"SystemRoot", "WINDIR"})
        self.assertTrue(kwargs["close_fds"])
        self.assertEqual(kwargs["creationflags"], noninteractive_creationflags())
        self.assertNotIn("shell", kwargs)
        self.assertNotIn("start_new_session", kwargs)
        self.assertEqual(output.getvalue(), cli_entry.STARTUP_STATUS)
        self.assertNotIn("private_", repr(args))
        process.stdin.close.assert_called_once()
        process.wait.assert_called_once_with(timeout=2.0)

    def test_startup_failure_does_not_change_dispatch_or_reflect_errors(self) -> None:
        fake = types.ModuleType("wom_kit.archive_cli")
        fake.main = mock.Mock(return_value=23)
        output = io.StringIO()
        with mock.patch.object(wom_kit, "archive_cli", fake, create=True), \
                mock.patch.dict(sys.modules, {"wom_kit.archive_cli": fake}), \
                mock.patch("subprocess.Popen", side_effect=OSError("private_failure_marker")), \
                contextlib.redirect_stderr(output):
            self.assertEqual(cli_entry.main(["doctor", "private_argument_marker"]), 23)
        self.assertEqual(output.getvalue(), cli_entry.STARTUP_STATUS)
        fake.main.assert_called_once()

    def test_real_reporter_handoff_precedes_output_and_is_idempotent(self) -> None:
        from wom_kit import archive_cli

        watchdog = mock.Mock()
        cli_entry._active_watchdog = watchdog
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            reporter = archive_cli.CommandProgressReporter(True, label="doctor")
            try:
                reporter.progress("doctor-run", "start", None, None)
                reporter.progress("doctor-run", "done", None, None)
            finally:
                reporter.close()
        watchdog.close.assert_called_once()
        self.assertIsNone(cli_entry._active_watchdog)
        self.assertIn("doctor-run: start", output.getvalue())

    def test_public_console_routes_change_but_mcp_and_legacy_module_stay(self) -> None:
        project = (KIT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        for name in ("archive", "wom"):
            self.assertIn(f'{name} = "wom_kit.cli_entry:main"', project)
        for name in ("archive-mcp", "wom-mcp"):
            self.assertIn(f'{name} = "wom_kit.mcp_server:main"', project)
        source = (SOURCE_ROOT / "wom_kit" / "archive_cli.py").read_text(encoding="utf-8")
        self.assertIn('if __name__ == "__main__":\n    raise SystemExit(main())', source)


class CliStartupProcessTests(unittest.TestCase):
    def spawn(self, program: str) -> tuple[subprocess.Popen, queue.Queue, float]:
        started = time.monotonic()
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", "-c", program],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            close_fds=True,
            creationflags=noninteractive_creationflags(),
        )
        events: queue.Queue = queue.Queue()

        def read(stream: object, label: str) -> None:
            try:
                for line in stream:
                    events.put((label, time.monotonic() - started, line))
            finally:
                events.put((label, time.monotonic() - started, None))

        for label, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            threading.Thread(target=read, args=(stream, label), daemon=True).start()
        self.addCleanup(self.stop_process, process)
        return process, events, started

    @staticmethod
    def stop_process(process: subprocess.Popen) -> None:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()

    def collect(self, process: subprocess.Popen, events: queue.Queue, timeout: float = 60) -> list[tuple]:
        observed = []
        closed = set()
        deadline = time.monotonic() + timeout
        while closed != {"stdout", "stderr"}:
            try:
                event = events.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                self.fail("startup child streams did not close within the bounded timeout")
            observed.append(event)
            if event[2] is None:
                closed.add(event[0])
        process.wait(timeout=5)
        return observed

    @staticmethod
    def loader_program(body: str, tail: str) -> str:
        return f"""import importlib.abc, importlib.util, json, sys, time
sys.path.insert(0, {str(SOURCE_ROOT)!r})
from wom_kit import cli_entry
class SlowCli(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'wom_kit.archive_cli':
            return importlib.util.spec_from_loader(fullname, self)
    def create_module(self, spec):
        return None
    def exec_module(self, module):
{body}
sys.meta_path.insert(0, SlowCli())
{tail}
"""

    def test_actual_no_bytecode_compile_has_early_status_and_gil_independent_heartbeat(self) -> None:
        body = f"""        from pathlib import Path
        source = Path({str(SOURCE_ROOT / 'wom_kit' / 'archive_services.py')!r}).read_bytes()
        started = time.monotonic()
        iterations = 0
        while time.monotonic() - started < 11.0:
            compile(source, 'synthetic_service_compile', 'exec')
            iterations += 1
        module.main = lambda argv: (print(json.dumps({{'ok': True, 'compile_iterations': iterations}})), 0)[1]"""
        process, events, _ = self.spawn(self.loader_program(
            body, "raise SystemExit(cli_entry.main(['doctor', 'private_target_marker', '--format=json']))"
        ))
        observed = self.collect(process, events, timeout=90)
        self.assertEqual(process.returncode, 0)
        stderr = [(at, line) for label, at, line in observed if label == "stderr" and line is not None]
        self.assertGreaterEqual(len(stderr), 3)
        self.assertLessEqual(stderr[0][0], 2.0)
        self.assertEqual(stderr[0][1], cli_entry.STARTUP_STATUS)
        self.assertTrue(all(line == cli_entry.STARTUP_HEARTBEAT for _, line in stderr[1:]))
        self.assertTrue(all(after[0] - before[0] <= 10.0 for before, after in zip(stderr, stderr[1:])))
        terminal = next(at for label, at, line in observed if label == "stderr" and line is None)
        self.assertLessEqual(terminal - stderr[-1][0], 10.0)
        stdout = "".join(line for label, _, line in observed if label == "stdout" and line is not None)
        self.assertTrue(json.loads(stdout)["ok"])
        self.assertNotIn("private_target_marker", "".join(line for _, _, line in observed if line is not None))

    def test_import_error_and_interrupt_close_the_actual_watchdog(self) -> None:
        for exception_name in ("RuntimeError", "KeyboardInterrupt"):
            with self.subTest(exception=exception_name):
                body = f"""        global observed_watchdog
        observed_watchdog = cli_entry._active_watchdog.process
        raise {exception_name}('private_failure_marker')"""
                tail = f"""try:
    cli_entry.main(['doctor'])
except {exception_name}:
    print(json.dumps({{'child_exited': observed_watchdog.poll() is not None, 'registry_cleared': cli_entry._active_watchdog is None}}))"""
                process, events, _ = self.spawn(self.loader_program(body, tail))
                observed = self.collect(process, events)
                self.assertEqual(process.returncode, 0)
                stdout = "".join(line for label, _, line in observed if label == "stdout" and line is not None)
                self.assertEqual(json.loads(stdout), {"child_exited": True, "registry_cleared": True})
                self.assertNotIn("private_failure_marker", "".join(line for _, _, line in observed if line is not None))

    def test_parent_termination_closes_watchdog_inherited_streams(self) -> None:
        body = """        print(json.dumps({'watchdog_started': cli_entry._active_watchdog is not None}), flush=True)
        time.sleep(60)"""
        process, events, _ = self.spawn(self.loader_program(body, "cli_entry.main(['doctor'])"))
        before = []
        while True:
            event = events.get(timeout=10)
            before.append(event)
            if event[0] == "stdout" and event[2] is not None:
                self.assertTrue(json.loads(event[2])["watchdog_started"])
                break
        process.terminate()
        # The orphan watchdog inherits stderr. EOF is therefore independent
        # proof that it did not remain alive after the parent lost its pipe.
        observed = self.collect(process, events, timeout=8)
        self.assertTrue(any(label == "stderr" and line is None for label, _, line in observed))

    def test_module_version_and_quiet_import_do_not_start_status(self) -> None:
        program = f"""import sys
sys.path.insert(0, {str(SOURCE_ROOT)!r})
from wom_kit import cli_entry
assert 'wom_kit.archive_cli' not in sys.modules
raise SystemExit(cli_entry.main(['--version']))
"""
        process, events, _ = self.spawn(program)
        observed = self.collect(process, events)
        self.assertEqual(process.returncode, 0)
        self.assertEqual("".join(line for label, _, line in observed if label == "stderr" and line is not None), "")
        self.assertEqual("".join(line for label, _, line in observed if label == "stdout" and line is not None), f"archive {wom_kit.__version__}\n")

    def test_public_module_entry_uses_the_same_watchdog_registry_as_reporters(self) -> None:
        body = """        from wom_kit import cli_entry
        watchdog = cli_entry._active_watchdog
        assert watchdog is not None
        def main(argv):
            cli_entry.handoff_startup_progress()
            print(json.dumps({'child_exited_before_result': watchdog.process.poll() is not None, 'registry_cleared': cli_entry._active_watchdog is None}))
            return 0
        module.main = main"""
        tail = """import runpy
sys.argv = ['archive', 'doctor']
runpy.run_module('wom_kit.cli_entry', run_name='__main__')"""
        # Do not pre-import the entrypoint: this exercises its real -m registry
        # transition rather than relying on an already imported canonical alias.
        program = self.loader_program(body, tail).replace("from wom_kit import cli_entry\n", "", 1)
        process, events, _ = self.spawn(program)
        observed = self.collect(process, events)
        self.assertEqual(process.returncode, 0)
        stderr = "".join(line for label, _, line in observed if label == "stderr" and line is not None)
        self.assertEqual(stderr, cli_entry.STARTUP_STATUS)
        stdout = "".join(line for label, _, line in observed if label == "stdout" and line is not None)
        self.assertEqual(json.loads(stdout), {"child_exited_before_result": True, "registry_cleared": True})


if __name__ == "__main__":
    unittest.main()
