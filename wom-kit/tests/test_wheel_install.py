from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from unittest import mock
import warnings
import zipfile


KIT_ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = KIT_ROOT / "tools" / "check_wheel_install.py"
RESOURCE_PREFIX = "wom_kit/_resources/"
MANIFEST_MEMBER = f"{RESOURCE_PREFIX}resource-manifest.json"

spec = importlib.util.spec_from_file_location("check_wheel_install", CHECKER_PATH)
assert spec is not None and spec.loader is not None
check_wheel_install = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_wheel_install
spec.loader.exec_module(check_wheel_install)


BASE_RESOURCES = {
    "schemas/archive.schema.json": b'{"fixture": "schema"}\n',
    "templates/personal/archive.yml": b"name: fixture archive\n",
    "templates/ai-runtime/wom-archive/SKILL.md": b"# Fixture skill\n",
    "templates/ai-runtime/wom-archive/references/operator-contract.md": (
        b"# Fixture operator contract\n"
    ),
    "zettel-kasten/types.yml": b"types: {}\n",
}


def manifest_for(resources: dict[str, bytes]) -> dict[str, object]:
    files = [
        {
            "source": packaged,
            "packaged": packaged,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        for packaged, data in sorted(resources.items())
    ]
    return {
        "schema": "wom-kit/package-resource-manifest/v0.1",
        "version": "0.3.289",
        "source_of_truth": "wom-kit source resource directories",
        "file_count": len(files),
        "files": files,
    }


def encode_manifest(manifest: dict[str, object]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def patch_central_directory_file_size(wheel: Path, member: str, size: int) -> None:
    data = bytearray(wheel.read_bytes())
    member_bytes = member.encode("utf-8")
    cursor = 0
    while True:
        cursor = data.find(b"PK\x01\x02", cursor)
        if cursor < 0:
            raise AssertionError(f"Central directory member not found: {member}")
        if cursor + 46 > len(data):
            raise AssertionError("Truncated central directory fixture.")
        filename_length, extra_length, comment_length = struct.unpack_from(
            "<HHH",
            data,
            cursor + 28,
        )
        name_start = cursor + 46
        name_end = name_start + filename_length
        if data[name_start:name_end] == member_bytes:
            struct.pack_into("<I", data, cursor + 24, size)
            wheel.write_bytes(data)
            return
        cursor = name_end + extra_length + comment_length


def patch_zip_member_name_bytes(wheel: Path, old_name: str, new_name: str) -> None:
    old_bytes = old_name.encode("utf-8")
    new_bytes = new_name.encode("utf-8")
    if len(old_bytes) != len(new_bytes):
        raise AssertionError("ZIP fixture member-name patch must preserve byte length.")
    data = wheel.read_bytes()
    occurrence_count = data.count(old_bytes)
    if occurrence_count != 2:
        raise AssertionError(
            f"Expected local and central member names, found {occurrence_count}: {old_name}"
        )
    wheel.write_bytes(data.replace(old_bytes, new_bytes))


class InstalledEntrypointTests(unittest.TestCase):
    PACKAGE_VERSION = "0.4.10"
    SERVER_NAME = "zettel-kasten-archive-mcp"

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory(
            prefix="wom-entrypoint-test-"
        )
        self.temp_root = Path(self.temp_directory.name)
        self.scripts = self.temp_root / "Scripts"
        self.scripts.mkdir()
        for name in ("archive", "archive-mcp", "wom", "wom-mcp"):
            check_wheel_install.executable(self.scripts, name).touch()

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_run_parses_an_expected_fixed_close_exit_as_json(self) -> None:
        payload = {
            "ok": False,
            "state": "blocked",
            "reason_codes": [
                "compound_exact_human_approval_binding_required"
            ],
        }
        command = [
            sys.executable,
            "-c",
            (
                "import json,sys; "
                f"print(json.dumps({payload!r})); "
                "raise SystemExit(1)"
            ),
        ]

        result = check_wheel_install.run(
            command,
            cwd=self.temp_root,
            label="fixed-close fixture",
            parse_json=True,
            expected_returncode=1,
            require_empty_stderr=True,
        )

        self.assertEqual(result, payload)
        with self.assertRaises(check_wheel_install.WheelCheckError):
            check_wheel_install.run(
                command,
                cwd=self.temp_root,
                label="unexpected success contract",
                parse_json=True,
            )

        noisy_command = [
            sys.executable,
            "-c",
            "import sys; print('fixed stderr', file=sys.stderr)",
        ]
        with self.assertRaises(check_wheel_install.WheelCheckError):
            check_wheel_install.run(
                noisy_command,
                cwd=self.temp_root,
                label="stderr must be empty",
                require_empty_stderr=True,
            )

    def test_installed_runtime_dependencies_are_pip_clean_and_unicode17(self) -> None:
        python = self.scripts / "python.exe"
        with mock.patch.object(
            check_wheel_install,
            "run",
            side_effect=[
                check_wheel_install.subprocess.CompletedProcess(
                    [str(python), "-m", "pip", "check"],
                    0,
                    "",
                    "",
                ),
                {
                    "distribution_version": "17.0.1",
                    "unicode_version": "17.0.0",
                },
            ],
        ) as run_mock:
            check_wheel_install._check_installed_runtime_dependencies(
                python,
                cwd=self.temp_root,
            )

        self.assertEqual(run_mock.call_count, 2)
        self.assertEqual(
            run_mock.call_args_list[0].args[0],
            [str(python), "-m", "pip", "check"],
        )
        isolated_command = run_mock.call_args_list[1].args[0]
        self.assertEqual(isolated_command[:3], [str(python), "-I", "-c"])
        self.assertTrue(run_mock.call_args_list[1].kwargs["parse_json"])

    def test_installed_unicode_runtime_mismatch_fails_closed(self) -> None:
        python = self.scripts / "python.exe"
        with mock.patch.object(
            check_wheel_install,
            "run",
            side_effect=[
                check_wheel_install.subprocess.CompletedProcess(
                    [str(python), "-m", "pip", "check"],
                    0,
                    "",
                    "",
                ),
                {
                    "distribution_version": "17.0.1",
                    "unicode_version": "unexpected",
                },
            ],
        ):
            with self.assertRaises(check_wheel_install.WheelCheckError):
                check_wheel_install._check_installed_runtime_dependencies(
                    python,
                    cwd=self.temp_root,
                )

    @staticmethod
    def completed(
        command: list[str],
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
    ) -> object:
        return check_wheel_install.subprocess.CompletedProcess(
            command,
            returncode,
            stdout,
            stderr,
        )

    def cli_stdout(self, *, version: str | None = None) -> str:
        return json.dumps(
            {
                "ok": True,
                "version": version or self.PACKAGE_VERSION,
                "consistency_state": "package_version_only",
            }
        )

    def mcp_stdout(
        self,
        tools: list[dict[str, object]],
        *,
        protocol_version: str | None = None,
        server_name: str | None = None,
        server_version: str | None = None,
        capabilities: object | None = None,
        next_cursor: object | None = None,
    ) -> str:
        tools_result: dict[str, object] = {"tools": tools}
        if next_cursor is not None:
            tools_result["nextCursor"] = next_cursor
        responses = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": (
                        protocol_version or check_wheel_install.MCP_PROTOCOL_VERSION
                    ),
                    "capabilities": (
                        {"tools": {"listChanged": False}}
                        if capabilities is None
                        else capabilities
                    ),
                    "serverInfo": {
                        "name": server_name or self.SERVER_NAME,
                        "version": server_version or self.PACKAGE_VERSION,
                    },
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": tools_result,
            },
        ]
        return "".join(json.dumps(response) + "\n" for response in responses)

    @staticmethod
    def executable_name(command: list[str]) -> str:
        name = Path(command[0]).name
        return name[:-4] if name.casefold().endswith(".exe") else name

    def test_all_four_entrypoints_are_executed_and_report_truthful_evidence(
        self,
    ) -> None:
        archive_tools = [
            {
                "name": "zeta",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "b": {"type": "integer"},
                        "a": {"type": "string"},
                    },
                },
            },
            {
                "name": "alpha",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]
        wom_tools = [
            {
                "inputSchema": {"properties": {}, "type": "object"},
                "name": "alpha",
            },
            {
                "inputSchema": {
                    "properties": {
                        "a": {"type": "string"},
                        "b": {"type": "integer"},
                    },
                    "type": "object",
                },
                "name": "zeta",
            },
        ]
        calls: list[tuple[list[str], dict[str, object]]] = []

        def fake_run(command: list[str], **kwargs: object) -> str:
            calls.append((command, kwargs))
            name = self.executable_name(command)
            if name in {"archive", "wom"}:
                self.assertEqual(command[1:], ["version", "--format", "json"])
                self.assertIsNone(kwargs.get("input_text"))
                return self.cli_stdout()
            self.assertEqual(command, [str(check_wheel_install.executable(self.scripts, name))])
            tools = archive_tools if name == "archive-mcp" else wom_tools
            return self.mcp_stdout(tools)

        with mock.patch.object(
            check_wheel_install,
            "_run_installed_entrypoint",
            side_effect=fake_run,
        ):
            package_version, checked, evidence = (
                check_wheel_install._check_installed_entrypoints(
                    self.scripts,
                    cwd=self.temp_root,
                )
            )

        self.assertEqual(package_version, self.PACKAGE_VERSION)
        self.assertEqual(
            checked,
            ["archive", "wom", "archive-mcp", "wom-mcp"],
        )
        self.assertEqual(len(calls), 4)
        for _command, kwargs in calls[2:]:
            request_lines = str(kwargs["input_text"]).splitlines()
            requests = [json.loads(line) for line in request_lines]
            self.assertEqual(
                [request["method"] for request in requests],
                [
                    "initialize",
                    "notifications/initialized",
                    "tools/list",
                ],
            )
            self.assertTrue(str(kwargs["input_text"]).endswith("\n"))

        agreement = evidence["agreement"]
        self.assertTrue(agreement["cli_versions_match"])
        self.assertTrue(agreement["mcp_server_versions_match_package"])
        self.assertTrue(
            agreement["mcp_canonical_inventories_byte_identical"]
        )
        archive_mcp = evidence["mcp_servers"]["archive-mcp"]
        wom_mcp = evidence["mcp_servers"]["wom-mcp"]
        self.assertEqual(archive_mcp["tool_count"], 2)
        self.assertEqual(
            archive_mcp["canonical_inventory_sha256"],
            wom_mcp["canonical_inventory_sha256"],
        )
        self.assertEqual(
            agreement["mcp_canonical_inventory_sha256"],
            archive_mcp["canonical_inventory_sha256"],
        )
        self.assertEqual(
            archive_mcp["request_sequence"],
            [
                "initialize",
                "notifications/initialized",
                "tools/list",
                "EOF",
            ],
        )
        self.assertTrue(archive_mcp["pagination_complete"])

    def test_entrypoint_process_failures_and_stderr_are_rejected(self) -> None:
        process_cases = {
            "nonzero exit": "import sys; raise SystemExit(7)",
            "nonempty stderr": (
                "import sys; sys.stderr.write('unexpected warning\\n')"
            ),
        }
        for case, script in process_cases.items():
            with self.subTest(case=case):
                with self.assertRaises(check_wheel_install.WheelCheckError):
                    check_wheel_install._run_installed_entrypoint(
                        [sys.executable, "-c", script],
                        cwd=self.temp_root,
                        label=case,
                    )

    def test_entrypoint_runner_sanitizes_python_environment(self) -> None:
        script = (
            "import json, os; "
            "print(json.dumps({"
            "'pythonpath': os.environ.get('PYTHONPATH'),"
            "'pythonhome': os.environ.get('PYTHONHOME'),"
            "'nousersite': os.environ.get('PYTHONNOUSERSITE'),"
            "'ioencoding': os.environ.get('PYTHONIOENCODING'),"
            "'utf8': os.environ.get('PYTHONUTF8')"
            "}))"
        )
        with mock.patch.dict(
            os.environ,
            {
                "PYTHONPATH": "PRIVATE_SOURCE_CHECKOUT",
                "PYTHONHOME": "PRIVATE_PYTHON_HOME",
                "PYTHONNOUSERSITE": "0",
                "PYTHONIOENCODING": "cp1252:ignore",
                "PYTHONUTF8": "0",
            },
        ):
            stdout = check_wheel_install._run_installed_entrypoint(
                [sys.executable, "-c", script],
                cwd=self.temp_root,
                label="environment probe",
            )

        self.assertEqual(
            json.loads(stdout),
            {
                "pythonpath": None,
                "pythonhome": None,
                "nousersite": "1",
                "ioencoding": "utf-8:strict",
                "utf8": "1",
            },
        )

    def test_entrypoint_runner_rejects_invalid_utf8_and_bounded_output(
        self,
    ) -> None:
        cases = {
            "invalid UTF-8": (
                "import sys; sys.stdout.buffer.write(bytes([255]))"
            ),
            "oversized output": (
                "import sys; sys.stdout.buffer.write(b'x' * 4096)"
            ),
        }
        for case, script in cases.items():
            output_limit = (
                64
                if case == "oversized output"
                else check_wheel_install.ENTRYPOINT_OUTPUT_LIMIT_BYTES
            )
            with self.subTest(case=case), mock.patch.object(
                check_wheel_install,
                "ENTRYPOINT_OUTPUT_LIMIT_BYTES",
                output_limit,
            ):
                with self.assertRaises(check_wheel_install.WheelCheckError):
                    check_wheel_install._run_installed_entrypoint(
                        [sys.executable, "-c", script],
                        cwd=self.temp_root,
                        label=case,
                    )

    def test_entrypoint_runner_checks_overflow_after_reader_join(self) -> None:
        class DelayedReader:
            def __init__(
                self,
                *,
                target: object,
                args: tuple[object, ...],
                daemon: bool,
            ) -> None:
                del daemon
                self._target = target
                self._args = args
                self._finished = False

            def start(self) -> None:
                pass

            def join(self, timeout: float | None = None) -> None:
                del timeout
                self._target(*self._args)  # type: ignore[operator]
                self._finished = True

            def is_alive(self) -> bool:
                return not self._finished

        script = (
            "import sys; "
            "sys.stdout.buffer.write(b'{}' + (b' ' * 63))"
        )
        with (
            mock.patch.object(
                check_wheel_install.threading,
                "Thread",
                DelayedReader,
            ),
            mock.patch.object(
                check_wheel_install,
                "ENTRYPOINT_OUTPUT_LIMIT_BYTES",
                64,
            ),
            self.assertRaises(check_wheel_install.WheelCheckError),
        ):
            check_wheel_install._run_installed_entrypoint(
                [sys.executable, "-c", script],
                cwd=self.temp_root,
                label="delayed overflow reader",
            )

    def test_entrypoint_timeout_includes_inherited_pipe_readers(self) -> None:
        script = (
            "import subprocess, sys; "
            "subprocess.Popen([sys.executable, '-c', "
            "'import time; time.sleep(1.5)']); "
            "raise SystemExit(0)"
        )
        started = time.monotonic()
        with (
            mock.patch.object(
                check_wheel_install,
                "ENTRYPOINT_TIMEOUT_SECONDS",
                0.25,
            ),
            self.assertRaises(check_wheel_install.WheelCheckError),
        ):
            check_wheel_install._run_installed_entrypoint(
                [sys.executable, "-c", script],
                cwd=self.temp_root,
                label="inherited pipe timeout",
            )
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 1.25)

    def test_entrypoint_rejects_detached_stdio_descendant(self) -> None:
        script = (
            "import subprocess, sys; "
            "subprocess.Popen("
            "[sys.executable, '-c', 'import time; time.sleep(5)'], "
            "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
            "stderr=subprocess.DEVNULL); "
            "raise SystemExit(0)"
        )
        started = time.monotonic()
        with self.assertRaises(check_wheel_install.WheelCheckError):
            check_wheel_install._run_installed_entrypoint(
                [sys.executable, "-c", script],
                cwd=self.temp_root,
                label="detached stdio descendant",
            )
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 2)

    @unittest.skipUnless(
        os.name == "nt",
        "Windows suspended-launch containment contract",
    )
    def test_windows_entrypoint_is_contained_before_first_instruction(
        self,
    ) -> None:
        original_popen = check_wheel_install.subprocess.Popen
        original_assign = check_wheel_install._assign_windows_kill_on_close_job
        original_resume = check_wheel_install._resume_windows_process
        events: list[str] = []

        def recording_popen(*args: object, **kwargs: object) -> object:
            creationflags = kwargs.get("creationflags")
            self.assertIs(type(creationflags), int)
            self.assertNotEqual(
                creationflags & check_wheel_install.WINDOWS_CREATE_SUSPENDED,
                0,
            )
            events.append("popen_suspended")
            return original_popen(*args, **kwargs)

        def recording_assign(process: object) -> object:
            events.append("job_assigned")
            return original_assign(process)  # type: ignore[arg-type]

        def recording_resume(process: object) -> bool:
            events.append("process_resumed")
            return original_resume(process)  # type: ignore[arg-type]

        with (
            mock.patch.object(
                check_wheel_install.subprocess,
                "Popen",
                side_effect=recording_popen,
            ),
            mock.patch.object(
                check_wheel_install,
                "_assign_windows_kill_on_close_job",
                side_effect=recording_assign,
            ),
            mock.patch.object(
                check_wheel_install,
                "_resume_windows_process",
                side_effect=recording_resume,
            ),
        ):
            output = check_wheel_install._run_installed_entrypoint(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.buffer.write(b'{}\\n')",
                ],
                cwd=self.temp_root,
                label="suspended launch ordering",
            )

        self.assertEqual(output, "{}\n")
        self.assertEqual(
            events[:3],
            ["popen_suspended", "job_assigned", "process_resumed"],
        )

    @unittest.skipUnless(
        os.name == "nt",
        "Windows suspended-launch containment contract",
    )
    def test_windows_process_resume_failure_is_fail_closed(self) -> None:
        with (
            mock.patch.object(
                check_wheel_install,
                "_resume_windows_process",
                return_value=False,
            ),
            self.assertRaises(check_wheel_install.WheelCheckError),
        ):
            check_wheel_install._run_installed_entrypoint(
                [sys.executable, "-c", "print('must not execute')"],
                cwd=self.temp_root,
                label="process resume failure",
            )

    @unittest.skipUnless(
        os.name == "nt",
        "Windows Job Object containment contract",
    )
    def test_windows_job_assignment_failure_is_fail_closed(self) -> None:
        with (
            mock.patch.object(
                check_wheel_install,
                "_assign_windows_kill_on_close_job",
                return_value=None,
            ),
            self.assertRaises(check_wheel_install.WheelCheckError),
        ):
            check_wheel_install._run_installed_entrypoint(
                [sys.executable, "-c", "print('must not pass')"],
                cwd=self.temp_root,
                label="job assignment failure",
            )

    def test_cli_version_probe_rejects_malformed_or_inconsistent_output(self) -> None:
        payload_cases = {
            "malformed JSON": "{not-json",
            "non-object JSON": "[]",
            "missing version": json.dumps(
                {"consistency_state": "package_version_only"}
            ),
            "invalid version": json.dumps(
                {
                    "version": " 0.3.296",
                    "consistency_state": "package_version_only",
                }
            ),
            "not package-only": json.dumps(
                {
                    "version": self.PACKAGE_VERSION,
                    "consistency_state": "source_checkout_match",
                }
            ),
            "reported failure": json.dumps(
                {
                    "ok": False,
                    "version": self.PACKAGE_VERSION,
                    "consistency_state": "package_version_only",
                }
            ),
        }
        for case, stdout in payload_cases.items():
            with self.subTest(case=case), mock.patch.object(
                check_wheel_install,
                "_run_installed_entrypoint",
                return_value=stdout,
            ):
                with self.assertRaises(check_wheel_install.WheelCheckError):
                    check_wheel_install._probe_cli_version(
                        Path("archive"),
                        cwd=self.temp_root,
                        entrypoint_name="archive",
                    )

    def test_mcp_probe_rejects_malformed_protocol_version_and_tools(self) -> None:
        valid_tool = {
            "name": "archive_doctor",
            "inputSchema": {"type": "object", "properties": {}},
        }
        malformed_cases = {
            "malformed JSON": "{not-json\n{}\n",
            "extra response": self.mcp_stdout([valid_tool]) + "{}\n",
            "protocol mismatch": self.mcp_stdout(
                [valid_tool],
                protocol_version="1900-01-01",
            ),
            "tools capability missing": self.mcp_stdout(
                [valid_tool],
                capabilities={},
            ),
            "unexpected server name": self.mcp_stdout(
                [valid_tool],
                server_name="unexpected-server",
            ),
            "package version mismatch": self.mcp_stdout(
                [valid_tool],
                server_version="0.0.0",
            ),
            "paginated inventory": self.mcp_stdout(
                [valid_tool],
                next_cursor="PRIVATE_NEXT_CURSOR",
            ),
            "duplicate tool name": self.mcp_stdout(
                [valid_tool, dict(valid_tool)]
            ),
            "empty tool inventory": self.mcp_stdout([]),
            "empty tool name": self.mcp_stdout(
                [
                    {
                        "name": "",
                        "inputSchema": {"type": "object"},
                    }
                ]
            ),
            "non-object input schema": self.mcp_stdout(
                [
                    {
                        "name": "archive_doctor",
                        "inputSchema": [],
                    }
                ]
            ),
            "wrong schema type": self.mcp_stdout(
                [
                    {
                        "name": "archive_doctor",
                        "inputSchema": {"type": "array"},
                    }
                ]
            ),
        }
        for case, stdout in malformed_cases.items():
            with self.subTest(case=case), mock.patch.object(
                check_wheel_install,
                "_run_installed_entrypoint",
                return_value=stdout,
            ):
                with self.assertRaises(check_wheel_install.WheelCheckError):
                    check_wheel_install._probe_mcp_server(
                        Path("archive-mcp"),
                        cwd=self.temp_root,
                        entrypoint_name="archive-mcp",
                        expected_package_version=self.PACKAGE_VERSION,
                    )

    def test_mcp_aliases_must_agree_on_server_name_and_inventory(self) -> None:
        mismatch_cases = {
            "server name": {
                "wom_server_name": "different-server",
                "wom_tools": [
                    {
                        "name": "same",
                        "inputSchema": {"type": "object"},
                    }
                ],
            },
            "inventory": {
                "wom_server_name": self.SERVER_NAME,
                "wom_tools": [
                    {
                        "name": "different",
                        "inputSchema": {"type": "object"},
                    }
                ],
            },
            "tool metadata": {
                "wom_server_name": self.SERVER_NAME,
                "wom_tools": [
                    {
                        "name": "same",
                        "description": "different description",
                        "inputSchema": {"type": "object"},
                    }
                ],
            },
        }
        archive_tools = [
            {
                "name": "same",
                "inputSchema": {"type": "object"},
            }
        ]
        for case, settings in mismatch_cases.items():
            def fake_run(command: list[str], **_kwargs: object) -> str:
                name = self.executable_name(command)
                if name in {"archive", "wom"}:
                    return self.cli_stdout()
                if name == "archive-mcp":
                    return self.mcp_stdout(archive_tools)
                return self.mcp_stdout(
                    settings["wom_tools"],  # type: ignore[arg-type]
                    server_name=str(settings["wom_server_name"]),
                )

            with self.subTest(case=case), mock.patch.object(
                check_wheel_install,
                "_run_installed_entrypoint",
                side_effect=fake_run,
            ):
                with self.assertRaises(check_wheel_install.WheelCheckError):
                    check_wheel_install._check_installed_entrypoints(
                        self.scripts,
                        cwd=self.temp_root,
                    )

    def test_success_result_assembly_preserves_v04_contract(self) -> None:
        wheel_counts = {
            "manifested_resource_count": 103,
            "verified_resource_count": 103,
            "verified_resource_bytes": 123456,
            "wheel_file_count": 120,
            "privacy_text_like_member_count": 119,
            "privacy_text_like_bytes_scanned": 234567,
            "privacy_windows_user_path_match_count": 0,
            "privacy_secret_pattern_match_count": 0,
        }
        evidence = {
            "agreement": {
                "package_version": self.PACKAGE_VERSION,
                "mcp_canonical_inventories_byte_identical": True,
            }
        }
        letter140_evidence = {
            "ok": True,
            "schema": "wom-kit/installed-letter140-wheel-smoke/v0.1",
            "body_bytes_preserved": True,
            "canonical_link_exact": True,
            "snapshot_exact": True,
            "receipt_schema": "wom-kit/zettel-objet-link-receipt/v0.2",
            "receipt_schema_validated_from_installed_package": True,
            "receipt_lookup": "passed",
            "validated_receipt_count": 1,
        }
        v049_evidence = {
            "ok": True,
            "schema": check_wheel_install.INSTALLED_V049_SMOKE_SCHEMA,
            "entrypoint_route": "installed_archive_cli_main",
            "installed_console_entrypoint_checked": True,
            "console_entrypoint_dry_run_count": 4,
            "approval_seam": "test_only_native_decision_injection",
        }
        v0410_batch_evidence = {
            "ok": True,
            "schema": check_wheel_install.INSTALLED_V0410_BATCH_SMOKE_SCHEMA,
            "item_count": 3,
            "fresh_separate_approvals": True,
        }
        result = check_wheel_install._wheel_install_success_result(
            package_version=self.PACKAGE_VERSION,
            wheel_counts=wheel_counts,
            entrypoints_checked=[
                "archive",
                "wom",
                "archive-mcp",
                "wom-mcp",
            ],
            entrypoint_evidence=evidence,
            letter140_link_evidence=letter140_evidence,
            v049_workflow_evidence=v049_evidence,
            v0410_batch_workflow_evidence=v0410_batch_evidence,
            wheel_filename="wom_kit-0.3.296-py3-none-any.whl",
            wheel_sha256="a" * 64,
            artifact_preserved=True,
        )

        self.assertEqual(
            result,
            {
                "ok": True,
                "schema": "wom-kit/wheel-install-check/v0.4",
                "package_version": self.PACKAGE_VERSION,
                **wheel_counts,
                "entrypoints_checked": [
                    "archive",
                    "wom",
                    "archive-mcp",
                    "wom-mcp",
                ],
                "entrypoint_evidence": evidence,
                "installed_letter140_link_workflow": letter140_evidence,
                "installed_v049_recovery_workflows": v049_evidence,
                "installed_v0410_batch_workflow": v0410_batch_evidence,
                "runtime_skill_lifecycle": "passed",
                "onboarding_preview": "passed",
                "onboarding_write": "fixed_closed",
                "onboarding_write_reason_code": (
                    "compound_exact_human_approval_binding_required"
                ),
                "strict_doctor": "passed_on_checked_in_fake_archive",
                "wheel_filename": "wom_kit-0.3.296-py3-none-any.whl",
                "wheel_sha256": "a" * 64,
                "wheel_artifact_preserved": True,
                "temporary_environment_removed_on_exit": True,
            },
        )

    def test_installed_letter140_link_workflow_requires_exact_evidence(self) -> None:
        compile(
            check_wheel_install.INSTALLED_LETTER140_SMOKE_SCRIPT,
            "<installed-letter140-wheel-smoke>",
            "exec",
        )
        python = self.scripts / "python.exe"
        archive_root = self.temp_root / "archive"
        expected = {
            "ok": True,
            "schema": check_wheel_install.INSTALLED_LETTER140_SMOKE_SCHEMA,
            "body_bytes_preserved": True,
            "canonical_link_exact": True,
            "snapshot_exact": True,
            "receipt_schema": "wom-kit/zettel-objet-link-receipt/v0.2",
            "receipt_schema_validated_from_installed_package": True,
            "receipt_lookup": "passed",
            "validated_receipt_count": 1,
        }
        with mock.patch.object(
            check_wheel_install,
            "run",
            return_value=expected,
        ) as run_mock:
            evidence = (
                check_wheel_install._check_installed_letter140_link_workflow(
                    python,
                    archive_root,
                    cwd=self.temp_root,
                )
            )

        self.assertEqual(evidence, expected)
        command = run_mock.call_args.args[0]
        self.assertEqual(command[:3], [str(python), "-I", "-c"])
        self.assertEqual(command[-1], str(archive_root))
        self.assertIn("import hashlib", command[3])
        self.assertIn("zettel_objet_link_apply", command[3])
        self.assertIn("receipt/v0.2", command[3])
        self.assertIn("WOM_WHEEL_SAFE_SYNTHETIC", command[3])
        self.assertTrue(run_mock.call_args.kwargs["parse_json"])
        self.assertTrue(run_mock.call_args.kwargs["require_empty_stderr"])

        invalid = dict(expected)
        invalid["body_bytes_preserved"] = False
        with mock.patch.object(
            check_wheel_install,
            "run",
            return_value=invalid,
        ):
            with self.assertRaises(check_wheel_install.WheelCheckError):
                check_wheel_install._check_installed_letter140_link_workflow(
                    python,
                    archive_root,
                    cwd=self.temp_root,
                )

    def test_installed_v049_workflows_require_exact_evidence(self) -> None:
        compile(
            check_wheel_install.INSTALLED_V049_SMOKE_SCRIPT,
            "<installed-v049-wheel-smoke>",
            "exec",
        )
        python = self.scripts / "python.exe"
        fixture_root = self.temp_root / "v049-fixture"
        archive_entrypoint = check_wheel_install.executable(
            self.scripts, "archive"
        )
        expected = {
            "ok": True,
            "schema": check_wheel_install.INSTALLED_V049_SMOKE_SCHEMA,
            "entrypoint_route": "installed_archive_cli_main",
            "installed_console_entrypoint_checked": True,
            "console_entrypoint_dry_run_count": 4,
            "approval_seam": "test_only_native_decision_injection",
            "capture": {
                "source_intake_recorded": True,
                "selection_recorded": True,
                "capture_count": 1,
                "object_bytes_exact": True,
                "native_approval_count": 3,
            },
            "object_storage": {
                "registration_completed": True,
                "setup_evidence_mode": "exact_registration_v1",
                "provider_api_called": False,
                "credential_value_read": False,
                "exact_revert_completed": True,
                "original_local_state_restored": True,
                "native_approval_count": 1,
                "revert_route": "installed_exact_operation_api",
            },
            "duplicate_reconciliation": {
                "strict_pair_reconciled_count": 1,
                "private_evidence_preserved": True,
                "whole_manifest_revert_completed": True,
                "original_manifest_bytes_restored": True,
                "native_approval_count": 2,
            },
            "native_approval_count": 6,
            "provider_api_called": False,
            "credential_value_read": False,
            "private_values_echoed": False,
        }
        with mock.patch.object(
            check_wheel_install,
            "_run_installed_entrypoint",
            return_value=json.dumps(expected),
        ) as run_mock:
            evidence = check_wheel_install._check_installed_v049_workflows(
                python,
                archive_entrypoint,
                fixture_root,
                cwd=self.temp_root,
            )

        self.assertEqual(evidence, expected)
        command = run_mock.call_args.args[0]
        self.assertEqual(command[:3], [str(python), "-I", "-c"])
        self.assertEqual(command[-2:], [str(fixture_root), str(archive_entrypoint)])
        self.assertIn("archive_cli.main", command[3])
        self.assertIn("source-intake-record", command[3])
        self.assertIn("objet-capture-selection", command[3])
        self.assertIn("object-storage", command[3])
        self.assertIn("duplicate-object-reconcile", command[3])
        self.assertLess(
            command[3].index("source_intake = _run_cli("),
            command[3].index(
                "plan = objet_capture_selection_exact."
                "plan_existing_intake_capture_selection("
            ),
        )

        invalid = dict(expected)
        invalid["native_approval_count"] = 4
        with mock.patch.object(
            check_wheel_install,
            "_run_installed_entrypoint",
            return_value=json.dumps(invalid),
        ):
            with self.assertRaises(check_wheel_install.WheelCheckError):
                check_wheel_install._check_installed_v049_workflows(
                    python,
                    archive_entrypoint,
                    fixture_root,
                    cwd=self.temp_root,
                )

    def test_installed_v0410_batch_workflow_requires_exact_evidence(self) -> None:
        compile(
            check_wheel_install.INSTALLED_V0410_BATCH_SMOKE_SCRIPT,
            "<installed-v0410-batch-wheel-smoke>",
            "exec",
        )
        python = self.scripts / "python.exe"
        fixture_root = self.temp_root / "v0410-batch-fixture"
        expected = {
            "ok": True,
            "schema": check_wheel_install.INSTALLED_V0410_BATCH_SMOKE_SCHEMA,
            "entrypoint_route": "installed_archive_cli_main",
            "item_count": 3,
            "source_receipt_count": 3,
            "prepared_capture_request_count": 1,
            "derived_prepared_request_only": True,
            "source_native_approval_count": 1,
            "capture_native_approval_count": 1,
            "fresh_separate_approvals": True,
            "capture_terminal_item_count": 3,
            "captured_item_count": 3,
            "object_bytes_exact": True,
            "no_progress_invocation_count": 4,
            "stderr_empty": True,
            "provider_api_called": False,
            "production_credential_store_accessed": False,
            "test_only_ephemeral_approval_key_used": True,
            "credential_material_used_for_local_authentication": True,
            "credential_values_echoed": False,
            "private_values_echoed": False,
            "absolute_paths_echoed": False,
        }
        with mock.patch.object(
            check_wheel_install,
            "_run_installed_entrypoint",
            return_value=json.dumps(expected),
        ) as run_mock:
            evidence = (
                check_wheel_install._check_installed_v0410_batch_workflow(
                    python,
                    fixture_root,
                    cwd=self.temp_root,
                )
            )

        self.assertEqual(evidence, expected)
        command = run_mock.call_args.args[0]
        self.assertEqual(command[:3], [str(python), "-I", "-c"])
        self.assertEqual(command[-1], str(fixture_root))
        self.assertIn("source-intake-batch", command[3])
        self.assertIn("objet-capture-batch", command[3])
        self.assertIn('"--no-progress"', command[3])
        self.assertNotIn('"--manifest",\n    prepared_ref', command[3])
        self.assertLess(
            command[3].index("source_result = _run_cli("),
            command[3].index("capture_plan = _run_cli("),
        )
        self.assertLess(
            command[3].index("before_capture_approval = native.calls"),
            command[3].index("capture_result = _run_cli("),
        )

        invalid = dict(expected)
        invalid["fresh_separate_approvals"] = False
        with mock.patch.object(
            check_wheel_install,
            "_run_installed_entrypoint",
            return_value=json.dumps(invalid),
        ):
            with self.assertRaises(check_wheel_install.WheelCheckError):
                check_wheel_install._check_installed_v0410_batch_workflow(
                    python,
                    fixture_root,
                    cwd=self.temp_root,
                )

    def test_installed_strict_doctor_explicitly_disables_default_progress(self) -> None:
        source = Path(check_wheel_install.__file__).read_text(encoding="utf-8")
        doctor_start = source.index('label="installed strict doctor"')
        doctor_command = source[source.rfind("doctor = run(", 0, doctor_start):doctor_start]
        self.assertIn('"--no-progress"', doctor_command)

    def test_main_uses_v04_success_and_failure_envelopes(self) -> None:
        success = {
            "ok": True,
            "schema": check_wheel_install.WHEEL_INSTALL_CHECK_SCHEMA,
            "package_version": self.PACKAGE_VERSION,
            "entrypoints_checked": [
                "archive",
                "wom",
                "archive-mcp",
                "wom-mcp",
            ],
            "entrypoint_evidence": {"agreement": {"cli_versions_match": True}},
        }
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(
                check_wheel_install,
                "check_wheel",
                return_value=success,
            ),
            mock.patch.object(
                check_wheel_install,
                "parse_args",
                return_value=check_wheel_install.argparse.Namespace(
                    format="json",
                    wheel_output_dir=None,
                ),
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = check_wheel_install.main()

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(json.loads(stdout.getvalue()), success)

        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(
                check_wheel_install,
                "check_wheel",
                side_effect=check_wheel_install.WheelCheckError(
                    "fixed failure"
                ),
            ),
            mock.patch.object(
                check_wheel_install,
                "parse_args",
                return_value=check_wheel_install.argparse.Namespace(
                    format="json",
                    wheel_output_dir=None,
                ),
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = check_wheel_install.main()

        self.assertEqual(code, 1)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "ok": False,
                "schema": check_wheel_install.WHEEL_INSTALL_CHECK_SCHEMA,
                "error": "fixed failure",
            },
        )


class WheelResourceIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory(prefix="wom-wheel-test-")
        self.temp_root = Path(self.temp_directory.name)
        self.fixture_kit_root = self.temp_root / "wom-kit"
        self.package_resource_root = (
            self.fixture_kit_root / "src" / "wom_kit" / "_resources"
        )
        self.package_resource_root.mkdir(parents=True)
        self.package_root_patch = mock.patch.object(
            check_wheel_install,
            "KIT_ROOT",
            self.fixture_kit_root,
        )
        self.package_root_patch.start()
        self.wheel_number = 0

    def tearDown(self) -> None:
        self.package_root_patch.stop()
        self.temp_directory.cleanup()

    def configure_committed_resources(
        self,
        *,
        manifest_bytes: bytes,
        mirror_resources: dict[str, bytes] | None = None,
    ) -> None:
        (self.package_resource_root / "resource-manifest.json").write_bytes(manifest_bytes)
        for relative, data in (mirror_resources or BASE_RESOURCES).items():
            path = self.package_resource_root / Path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def write_wheel(
        self,
        *,
        manifest_bytes: bytes,
        resources: dict[str, bytes] | None = None,
        extra_members: list[tuple[str, bytes]] | None = None,
        manifest_member: str = MANIFEST_MEMBER,
    ) -> Path:
        self.wheel_number += 1
        wheel = self.temp_root / f"fixture-{self.wheel_number}.whl"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr(manifest_member, manifest_bytes)
                for relative, data in (resources or BASE_RESOURCES).items():
                    archive.writestr(f"{RESOURCE_PREFIX}{relative}", data)
                for name, data in extra_members or []:
                    archive.writestr(name, data)
        return wheel

    def baseline(self) -> tuple[dict[str, object], bytes]:
        manifest = manifest_for(BASE_RESOURCES)
        manifest_bytes = encode_manifest(manifest)
        self.configure_committed_resources(manifest_bytes=manifest_bytes)
        return manifest, manifest_bytes

    def assert_wheel_rejected(
        self,
        wheel: Path,
        *,
        message_contains_any: tuple[str, ...] = (),
    ) -> str:
        with self.assertRaises(check_wheel_install.WheelCheckError) as caught:
            check_wheel_install.assert_wheel_resources(wheel)
        message = str(caught.exception)
        if message_contains_any:
            lowered = message.lower()
            self.assertTrue(
                any(needle.lower() in lowered for needle in message_contains_any),
                f"Expected one of {message_contains_any!r} in {message!r}",
            )
        return message

    def test_valid_wheel_verifies_every_resource_and_reports_exact_counts(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            extra_members=[
                (f"{RESOURCE_PREFIX}__init__.py", b'"""Packaged resources."""\n'),
                ("wom_kit-0.3.289.dist-info/METADATA", b"Name: wom-kit\n"),
            ],
        )

        result = check_wheel_install.assert_wheel_resources(wheel)

        self.assertEqual(
            result,
            {
                "manifested_resource_count": len(BASE_RESOURCES),
                "verified_resource_count": len(BASE_RESOURCES),
                "verified_resource_bytes": sum(map(len, BASE_RESOURCES.values())),
                "wheel_file_count": len(BASE_RESOURCES) + 3,
            },
        )

        privacy = check_wheel_install.assert_wheel_privacy(wheel)
        with zipfile.ZipFile(wheel) as archive:
            expected_text_bytes = sum(
                info.file_size for info in archive.infolist()
            )
        self.assertEqual(
            privacy,
            {
                "privacy_text_like_member_count": len(BASE_RESOURCES) + 3,
                "privacy_text_like_bytes_scanned": expected_text_bytes,
                "privacy_windows_user_path_match_count": 0,
                "privacy_secret_pattern_match_count": 0,
            },
        )

    def test_privacy_scan_rejects_windows_user_paths_without_echoing_them(self) -> None:
        _, manifest_bytes = self.baseline()
        private_value = (
            "C:"
            + "\\Us"
            + "ers\\"
            + "private-"
            + "account"
            + "\\archive"
        )
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            extra_members=[
                ("wom_kit/private_fixture.txt", private_value.encode("utf-8")),
            ],
        )

        with self.assertRaises(check_wheel_install.WheelCheckError) as caught:
            check_wheel_install.assert_wheel_privacy(wheel)

        message = str(caught.exception)
        self.assertEqual(message, "Wheel privacy scan detected forbidden content.")
        self.assertNotIn(private_value, message)
        self.assertNotIn("private_fixture.txt", message)

    def test_privacy_scan_allows_documented_generic_windows_user_placeholder(self) -> None:
        _, manifest_bytes = self.baseline()
        generic_account = "<" + "user" + ">"
        documented_path = (
            "C:"
            + "\\Us"
            + "ers\\"
            + generic_account
            + "\\synthetic-archive"
        )
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            extra_members=[
                (
                    "wom_kit/documented-example.txt",
                    documented_path.encode("utf-8"),
                ),
            ],
        )

        result = check_wheel_install.assert_wheel_privacy(wheel)

        self.assertEqual(result["privacy_windows_user_path_match_count"], 0)

    def test_privacy_scan_rejects_secret_patterns_in_all_text_like_members(self) -> None:
        _, manifest_bytes = self.baseline()
        private_value = "synthetic-private-credential-value"
        cases = (
            ("wom_kit/config.json", '{"access_token":"' + private_value + '"}'),
            ("wom_kit/extension.opaque", "password='" + private_value + "'"),
        )
        for member, content in cases:
            with self.subTest(member=member):
                wheel = self.write_wheel(
                    manifest_bytes=manifest_bytes,
                    extra_members=[(member, content.encode("utf-8"))],
                )
                with self.assertRaises(check_wheel_install.WheelCheckError) as caught:
                    check_wheel_install.assert_wheel_privacy(wheel)
                message = str(caught.exception)
                self.assertEqual(
                    message,
                    "Wheel privacy scan detected forbidden content.",
                )
                self.assertNotIn(private_value, message)
                self.assertNotIn(member, message)

    def test_privacy_scan_fails_closed_for_invalid_declared_text(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            extra_members=[("wom_kit/invalid.txt", b"\xff\xfe")],
        )

        with self.assertRaises(check_wheel_install.WheelCheckError) as caught:
            check_wheel_install.assert_wheel_privacy(wheel)

        self.assertEqual(
            str(caught.exception),
            "Wheel privacy scan could not verify a text member.",
        )

    def test_duplicate_zip_member_is_rejected_even_outside_resource_tree(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            extra_members=[
                ("wom_kit-0.3.289.dist-info/METADATA", b"first"),
                ("wom_kit-0.3.289.dist-info/METADATA", b"second"),
            ],
        )

        self.assert_wheel_rejected(wheel, message_contains_any=("duplicate",))

    def test_unsafe_or_non_normalized_zip_member_paths_are_rejected(self) -> None:
        unsafe_names = (
            "/absolute.txt",
            "//server/share.txt",
            "C:/windows-absolute.txt",
            "relative//empty-segment.txt",
            "./relative.txt",
            "relative/./dot.txt",
            "relative/../parent.txt",
            r"relative\backslash.txt",
            "relative/",
        )
        for unsafe_name in unsafe_names:
            with self.subTest(member=unsafe_name):
                _, manifest_bytes = self.baseline()
                written_name = unsafe_name.replace("\\", "/")
                wheel = self.write_wheel(
                    manifest_bytes=manifest_bytes,
                    extra_members=[(written_name, b"unsafe")],
                )
                if written_name != unsafe_name:
                    # ZipInfo normalizes backslashes on Windows while writing.
                    # Patch both filename copies so the checker receives the
                    # hostile raw member name that an untrusted ZIP may contain.
                    patch_zip_member_name_bytes(wheel, written_name, unsafe_name)
                self.assert_wheel_rejected(
                    wheel,
                    message_contains_any=("path", "member", "unsafe", "normalized"),
                )

    def test_windows_case_insensitive_member_alias_is_rejected(self) -> None:
        _, manifest_bytes = self.baseline()
        verified_member = f"{RESOURCE_PREFIX}{next(iter(BASE_RESOURCES))}"
        hostile_alias = verified_member.upper()
        self.assertNotEqual(hostile_alias, verified_member)
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            extra_members=[(hostile_alias, b"MALICIOUS-ALIAS-BYTES")],
        )

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("collision", "windows", "duplicate", "alias"),
        )

    def test_windows_case_collision_is_rejected_outside_resource_tree(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            extra_members=[
                ("example/Readme.txt", b"first"),
                ("EXAMPLE/README.TXT", b"second"),
            ],
        )

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("collision", "windows", "duplicate", "alias"),
        )

    def test_wheel_data_scheme_members_are_rejected_before_relocation(self) -> None:
        _, manifest_bytes = self.baseline()
        verified_member = f"{RESOURCE_PREFIX}{next(iter(BASE_RESOURCES))}"
        scheme_members = (
            f"alternate-1.0.data/purelib/{verified_member}",
            f"alternate-1.0.data/platlib/{verified_member}",
            "alternate-1.0.data/data/payload.txt",
            "alternate-1.0.data/headers/payload.h",
            "alternate-1.0.data/scripts/archive",
            f"alternate-1.0.DATA/purelib/{verified_member}",
        )
        for scheme_member in scheme_members:
            with self.subTest(member=scheme_member):
                wheel = self.write_wheel(
                    manifest_bytes=manifest_bytes,
                    extra_members=[(scheme_member, b"RELOCATED-ALIAS-BYTES")],
                )
                self.assert_wheel_rejected(
                    wheel,
                    message_contains_any=(
                        "data",
                        "scheme",
                        "relocat",
                        "pure",
                        "wheel",
                    ),
                )

    def test_windows_unsafe_segments_are_rejected(self) -> None:
        unsafe_names = (
            "example/alternate-stream.txt:payload",
            "example/less<than.txt",
            "example/greater>than.txt",
            'example/double"quote.txt',
            "example/pipe|name.txt",
            "example/question?.txt",
            "example/star*.txt",
            "example/trailing-dot.",
            "example/trailing-space ",
            "example/CON",
            "example/con.txt",
            "example/PRN.log",
            "example/AUX",
            "example/NUL.data",
            "example/COM1.txt",
            "example/com9",
            "example/COM¹.txt",
            "example/com²",
            "example/COM³.log",
            "example/LPT1.bin",
            "example/lpt9",
            "example/LPT¹.bin",
            "example/lpt²",
            "example/LPT³.log",
        )
        for unsafe_name in unsafe_names:
            with self.subTest(member=unsafe_name):
                _, manifest_bytes = self.baseline()
                wheel = self.write_wheel(
                    manifest_bytes=manifest_bytes,
                    extra_members=[(unsafe_name, b"unsafe-on-windows")],
                )
                self.assert_wheel_rejected(
                    wheel,
                    message_contains_any=(
                        "windows",
                        "reserved",
                        "colon",
                        "trailing",
                        "path",
                    ),
                )

    def test_manifest_must_use_the_exact_packaged_path(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            manifest_member=f"lookalike/{MANIFEST_MEMBER}",
        )

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("manifest",),
        )

    def test_malformed_zip_is_normalized_to_wheel_check_error(self) -> None:
        wheel = self.temp_root / "malformed.whl"
        wheel.write_bytes(b"this is not a zip archive")

        message = self.assert_wheel_rejected(
            wheel,
            message_contains_any=("zip", "archive", "wheel"),
        )
        self.assertEqual(message, "Wheel resource integrity check failed.")

    def test_malformed_manifest_utf8_and_json_are_rejected(self) -> None:
        malformed_manifests = {
            "utf8": b"\xff\xfe\xfa",
            "json": b'{"schema": ',
        }
        for case, manifest_bytes in malformed_manifests.items():
            with self.subTest(case=case):
                self.configure_committed_resources(manifest_bytes=manifest_bytes)
                wheel = self.write_wheel(manifest_bytes=manifest_bytes)
                self.assert_wheel_rejected(
                    wheel,
                    message_contains_any=("utf-8", "utf8", "json", "manifest"),
                )

    def test_duplicate_manifest_json_key_is_rejected(self) -> None:
        manifest = manifest_for(BASE_RESOURCES)
        compact = json.dumps(manifest, ensure_ascii=True, separators=(",", ":"))
        duplicate_key_json = compact.replace(
            '"schema":"wom-kit/package-resource-manifest/v0.1",',
            (
                '"schema":"wom-kit/package-resource-manifest/v0.1",'
                '"schema":"wom-kit/package-resource-manifest/v0.1",'
            ),
            1,
        ).encode("utf-8")
        self.configure_committed_resources(manifest_bytes=duplicate_key_json)
        wheel = self.write_wheel(manifest_bytes=duplicate_key_json)

        self.assert_wheel_rejected(wheel, message_contains_any=("duplicate",))

    def test_manifest_schema_and_types_are_strict(self) -> None:
        baseline = manifest_for(BASE_RESOURCES)

        cases: dict[str, dict[str, object]] = {}

        missing_key = dict(baseline)
        del missing_key["source_of_truth"]
        cases["missing top-level key"] = missing_key

        extra_key = dict(baseline)
        extra_key["unexpected"] = True
        cases["extra top-level key"] = extra_key

        wrong_schema = dict(baseline)
        wrong_schema["schema"] = "wom-kit/package-resource-manifest/v999"
        cases["wrong schema identifier"] = wrong_schema

        wrong_version_type = dict(baseline)
        wrong_version_type["version"] = 289
        cases["wrong version type"] = wrong_version_type

        wrong_source_of_truth_type = dict(baseline)
        wrong_source_of_truth_type["source_of_truth"] = ["not", "a", "string"]
        cases["wrong source-of-truth type"] = wrong_source_of_truth_type

        bool_file_count = dict(baseline)
        bool_file_count["file_count"] = True
        cases["bool is not an integer count"] = bool_file_count

        wrong_file_count = dict(baseline)
        wrong_file_count["file_count"] = len(BASE_RESOURCES) + 1
        cases["file count mismatch"] = wrong_file_count

        wrong_files_type = dict(baseline)
        wrong_files_type["files"] = {"not": "a list"}
        cases["files must be a list"] = wrong_files_type

        first_row = dict(baseline["files"][0])  # type: ignore[index]
        missing_row_key = dict(baseline)
        missing_row_key["files"] = [
            {key: value for key, value in first_row.items() if key != "sha256"},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        cases["missing row key"] = missing_row_key

        extra_row_key = dict(baseline)
        extra_row_key["files"] = [
            {**first_row, "unexpected": "value"},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        cases["extra row key"] = extra_row_key

        bool_byte_count = dict(baseline)
        bool_byte_count["files"] = [
            {**first_row, "bytes": True},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        cases["bool is not a byte count"] = bool_byte_count

        negative_byte_count = dict(baseline)
        negative_byte_count["files"] = [
            {**first_row, "bytes": -1},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        cases["negative byte count"] = negative_byte_count

        wrong_source_type = dict(baseline)
        wrong_source_type["files"] = [
            {**first_row, "source": 123},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        cases["row source must be a string"] = wrong_source_type

        malformed_sha = dict(baseline)
        malformed_sha["files"] = [
            {**first_row, "sha256": "not-a-sha256"},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        cases["malformed sha256"] = malformed_sha

        for case, manifest in cases.items():
            with self.subTest(case=case):
                manifest_bytes = encode_manifest(manifest)
                self.configure_committed_resources(manifest_bytes=manifest_bytes)
                wheel = self.write_wheel(manifest_bytes=manifest_bytes)
                self.assert_wheel_rejected(
                    wheel,
                    message_contains_any=("manifest", "schema", "field", "file_count"),
                )

    def test_duplicate_manifest_resource_path_is_rejected(self) -> None:
        manifest = manifest_for(BASE_RESOURCES)
        duplicate_row = dict(manifest["files"][0])  # type: ignore[index]
        manifest["files"] = [*manifest["files"], duplicate_row]  # type: ignore[index]
        manifest["file_count"] = len(manifest["files"])  # type: ignore[arg-type]
        manifest_bytes = encode_manifest(manifest)
        self.configure_committed_resources(manifest_bytes=manifest_bytes)
        wheel = self.write_wheel(manifest_bytes=manifest_bytes)

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("duplicate", "resource", "packaged"),
        )

    def test_missing_and_unmanifested_resources_are_rejected(self) -> None:
        _, manifest_bytes = self.baseline()
        missing_resources = dict(BASE_RESOURCES)
        missing_resources.pop(next(iter(missing_resources)))
        missing_wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            resources=missing_resources,
        )
        self.assert_wheel_rejected(
            missing_wheel,
            message_contains_any=("resource", "missing", "set"),
        )

        extra_resources = {
            **BASE_RESOURCES,
            "templates/unmanifested.txt": b"not declared",
        }
        extra_wheel = self.write_wheel(
            manifest_bytes=manifest_bytes,
            resources=extra_resources,
        )
        self.assert_wheel_rejected(
            extra_wheel,
            message_contains_any=("resource", "unexpected", "set"),
        )

    def test_declared_size_and_sha256_mismatches_are_rejected(self) -> None:
        baseline = manifest_for(BASE_RESOURCES)

        size_manifest = dict(baseline)
        size_row = dict(baseline["files"][0])  # type: ignore[index]
        size_manifest["files"] = [
            {**size_row, "bytes": size_row["bytes"] + 1},  # type: ignore[operator]
            *baseline["files"][1:],  # type: ignore[index]
        ]
        size_bytes = encode_manifest(size_manifest)
        self.configure_committed_resources(manifest_bytes=size_bytes)
        size_wheel = self.write_wheel(manifest_bytes=size_bytes)
        self.assert_wheel_rejected(
            size_wheel,
            message_contains_any=("size", "byte"),
        )

        sha_manifest = dict(baseline)
        sha_row = dict(baseline["files"][0])  # type: ignore[index]
        sha_manifest["files"] = [
            {**sha_row, "sha256": "0" * 64},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        sha_bytes = encode_manifest(sha_manifest)
        self.configure_committed_resources(manifest_bytes=sha_bytes)
        sha_wheel = self.write_wheel(manifest_bytes=sha_bytes)
        self.assert_wheel_rejected(
            sha_wheel,
            message_contains_any=("sha", "digest", "hash"),
        )

    def test_zip_member_size_and_actual_read_size_are_both_checked(self) -> None:
        baseline = manifest_for(BASE_RESOURCES)
        baseline_bytes = encode_manifest(baseline)
        self.configure_committed_resources(manifest_bytes=baseline_bytes)
        relative = next(iter(BASE_RESOURCES))
        member = f"{RESOURCE_PREFIX}{relative}"
        actual_size = len(BASE_RESOURCES[relative])

        wrong_zip_size = self.write_wheel(manifest_bytes=baseline_bytes)
        patch_central_directory_file_size(wrong_zip_size, member, actual_size + 1)
        self.assert_wheel_rejected(
            wrong_zip_size,
            message_contains_any=("size", "byte"),
        )

        actual_read_manifest = dict(baseline)
        actual_read_row = dict(baseline["files"][0])  # type: ignore[index]
        actual_read_manifest["files"] = [
            {**actual_read_row, "bytes": actual_size + 1},
            *baseline["files"][1:],  # type: ignore[index]
        ]
        actual_read_bytes = encode_manifest(actual_read_manifest)
        self.configure_committed_resources(manifest_bytes=actual_read_bytes)
        wrong_actual_read_size = self.write_wheel(manifest_bytes=actual_read_bytes)
        patch_central_directory_file_size(
            wrong_actual_read_size,
            member,
            actual_size + 1,
        )
        self.assert_wheel_rejected(
            wrong_actual_read_size,
            message_contains_any=("size", "byte", "read"),
        )

    def test_semantically_equal_but_byte_different_canonical_manifest_is_rejected(self) -> None:
        manifest = manifest_for(BASE_RESOURCES)
        canonical_bytes = encode_manifest(manifest)
        wheel_bytes = json.dumps(
            manifest,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(json.loads(canonical_bytes), json.loads(wheel_bytes))
        self.assertNotEqual(canonical_bytes, wheel_bytes)
        self.configure_committed_resources(manifest_bytes=canonical_bytes)
        wheel = self.write_wheel(manifest_bytes=wheel_bytes)

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("canonical", "manifest", "byte"),
        )

    def test_resource_bytes_must_equal_the_committed_packaged_mirror(self) -> None:
        _, manifest_bytes = self.baseline()
        mirror_resources = dict(BASE_RESOURCES)
        changed_relative = next(iter(mirror_resources))
        mirror_resources[changed_relative] = b"different committed mirror bytes"
        self.configure_committed_resources(
            manifest_bytes=manifest_bytes,
            mirror_resources=mirror_resources,
        )
        wheel = self.write_wheel(manifest_bytes=manifest_bytes)

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("mirror", "committed", "byte", "resource"),
        )

    def test_missing_canonical_or_mirror_files_are_normalized(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(manifest_bytes=manifest_bytes)

        canonical = self.package_resource_root / "resource-manifest.json"
        canonical.unlink()
        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("manifest", "resource", "read"),
        )

        self.configure_committed_resources(manifest_bytes=manifest_bytes)
        missing_mirror = self.package_resource_root / Path(next(iter(BASE_RESOURCES)))
        missing_mirror.unlink()
        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("mirror", "resource", "read"),
        )

    def test_corrupt_resource_member_read_is_normalized(self) -> None:
        _, manifest_bytes = self.baseline()
        wheel = self.write_wheel(manifest_bytes=manifest_bytes)
        member = f"{RESOURCE_PREFIX}{next(iter(BASE_RESOURCES))}"

        with zipfile.ZipFile(wheel) as archive:
            info = archive.getinfo(member)
            header_offset = info.header_offset
        with wheel.open("r+b") as stream:
            stream.seek(header_offset)
            header = stream.read(30)
            (
                signature,
                _extract_version,
                _flags,
                _compression,
                _time,
                _date,
                _crc,
                _compressed_size,
                _file_size,
                filename_length,
                extra_length,
            ) = struct.unpack("<IHHHHHIIIHH", header)
            self.assertEqual(signature, 0x04034B50)
            payload_offset = header_offset + 30 + filename_length + extra_length
            stream.seek(payload_offset)
            original = stream.read(1)
            self.assertTrue(original)
            stream.seek(payload_offset)
            stream.write(bytes([original[0] ^ 0xFF]))

        self.assert_wheel_rejected(
            wheel,
            message_contains_any=("zip", "resource", "read", "crc"),
        )


if __name__ == "__main__":
    unittest.main()
