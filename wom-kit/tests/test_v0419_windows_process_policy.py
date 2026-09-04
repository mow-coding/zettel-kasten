from __future__ import annotations

import ast
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

from wom_kit import (
    archive_cli,
    archive_services,
    credential_workflows,
    process_launch,
    project_runtime,
)


PACKAGE_ROOT = Path(archive_cli.__file__).resolve().parent
DIRECT_SUBPROCESS_RE = re.compile(r"\bsubprocess\.(?:run|Popen)\s*\(")
CREATIONFLAGS_RE = re.compile(r"\bcreationflags\s*=")
MULTIPROCESS_PROCESS_RE = re.compile(r"\bcontext\.Process\s*\(")
DIRECT_PROCESS_START_RE = re.compile(r"\bprocess\.start\s*\(")
POLICY_PROCESS_START_RE = re.compile(
    r"\bprocess_launch\.start_multiprocessing_process_no_console\s*\("
)

_INTERACTIVE_SUBPROCESS_SITE = (
    "archive_services.py",
    "_run_keepassxc_cli_add",
    "run",
)
_BOUND_CREATION_FLAGS_SITE = (
    "git_backup_plan.py",
    "_run_transport_capped",
    "Popen",
)


class _DirectSubprocessVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.function_stack: list[str] = []
        self.calls: list[tuple[str, ast.Call]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        if (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "subprocess"
            and function.attr in {"run", "Popen"}
        ):
            enclosing = self.function_stack[-1] if self.function_stack else "<module>"
            self.calls.append((enclosing, node))
        self.generic_visit(node)


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    matches = [item.value for item in call.keywords if item.arg == name]
    if len(matches) > 1:
        raise AssertionError("duplicate_call_keyword")
    return matches[0] if matches else None


def _expression_shape(source: str) -> str:
    return ast.dump(
        ast.parse(source, mode="eval").body,
        annotate_fields=True,
        include_attributes=False,
    )


def _is_common_creationflags_call(expression: ast.AST) -> bool:
    return (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "noninteractive_creationflags"
        and not expression.args
        and not expression.keywords
    )


def _subprocess_import_discipline_errors(
    tree: ast.Module,
    *,
    filename: str,
) -> list[str]:
    errors: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for imported in node.names:
                if imported.name == "subprocess" and imported.asname is not None:
                    errors.append(
                        f"{filename}:{node.lineno}:subprocess_import_alias_forbidden"
                    )
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            errors.append(
                f"{filename}:{node.lineno}:subprocess_from_import_forbidden"
            )
    return errors


def _bound_transport_creation_flags_are_exact(tree: ast.Module) -> bool:
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_run_transport_capped"
    ]
    if len(functions) != 1:
        return False
    function = functions[0]
    assignments: list[ast.AST] = []
    stores = 0
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store)
            and node.id == "creation_flags"
        ):
            stores += 1
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "creation_flags"
            for target in node.targets
        ):
            assignments.append(node.value)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "creation_flags"
            and node.value is not None
        ):
            assignments.append(node.value)
        elif (
            isinstance(node, ast.AugAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "creation_flags"
        ):
            return False
    expected = {
        _expression_shape("noninteractive_creationflags()"),
        _expression_shape(
            "noninteractive_creationflags("
            "subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004)"
        ),
    }
    observed = {
        ast.dump(item, annotate_fields=True, include_attributes=False)
        for item in assignments
    }
    return stores == 2 and len(assignments) == 2 and observed == expected


def _direct_subprocess_policy_errors(
    sources: dict[str, str],
) -> tuple[list[str], int]:
    errors: list[str] = []
    call_count = 0
    interactive_count = 0
    bound_transport_count = 0
    parsed: dict[str, ast.Module] = {}
    for filename, source in sorted(sources.items()):
        tree = ast.parse(source, filename=filename)
        parsed[filename] = tree
        errors.extend(
            _subprocess_import_discipline_errors(tree, filename=filename)
        )
        visitor = _DirectSubprocessVisitor()
        visitor.visit(tree)
        for function_name, call in visitor.calls:
            call_count += 1
            assert isinstance(call.func, ast.Attribute)
            site = (filename, function_name, call.func.attr)
            creationflags = _keyword(call, "creationflags")
            label = f"{filename}:{function_name}:{call.lineno}"
            if site == _INTERACTIVE_SUBPROCESS_SITE:
                interactive_count += 1
                if creationflags is not None:
                    errors.append(f"{label}:interactive_subprocess_must_stay_visible")
                continue
            if creationflags is None:
                errors.append(f"{label}:subprocess_creationflags_missing")
                continue
            if _is_common_creationflags_call(creationflags):
                continue
            if (
                site == _BOUND_CREATION_FLAGS_SITE
                and isinstance(creationflags, ast.Name)
                and creationflags.id == "creation_flags"
            ):
                bound_transport_count += 1
                continue
            errors.append(f"{label}:subprocess_creationflags_not_common_policy")
    if interactive_count != 1:
        errors.append(f"interactive_subprocess_site_count:{interactive_count}")
    if bound_transport_count != 1:
        errors.append(f"bound_transport_creation_flags_site_count:{bound_transport_count}")
    transport_tree = parsed.get(_BOUND_CREATION_FLAGS_SITE[0])
    if transport_tree is None or not _bound_transport_creation_flags_are_exact(
        transport_tree
    ):
        errors.append("bound_transport_creation_flags_derivation_invalid")
    return errors, call_count


def _bridge_subprocess_policy_errors(source: str) -> tuple[list[str], int]:
    tree = ast.parse(source, filename="<project-bridge-bootstrap>")
    visitor = _DirectSubprocessVisitor()
    visitor.visit(tree)
    errors = _subprocess_import_discipline_errors(
        tree,
        filename="<project-bridge-bootstrap>",
    )
    expected = _expression_shape(
        'getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) '
        'if os.name == "nt" else 0'
    )
    for function_name, call in visitor.calls:
        assert isinstance(call.func, ast.Attribute)
        creationflags = _keyword(call, "creationflags")
        label = f"{function_name}:{call.lineno}"
        if call.func.attr != "Popen" or function_name != "git":
            errors.append(f"{label}:bridge_subprocess_site_unexpected")
        elif creationflags is None:
            errors.append(f"{label}:bridge_creationflags_missing")
        elif (
            ast.dump(
                creationflags,
                annotate_fields=True,
                include_attributes=False,
            )
            != expected
        ):
            errors.append(f"{label}:bridge_creationflags_not_exact")
    if len(visitor.calls) != 1:
        errors.append(f"bridge_subprocess_site_count:{len(visitor.calls)}")
    return errors, len(visitor.calls)


class _MultiprocessingPolicyVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.class_stack: list[str] = []
        self.function_stack: list[str] = []
        self.process_creations: list[tuple[str, str, int]] = []
        self.policy_starts: list[tuple[str, str, int]] = []
        self.direct_starts: list[tuple[str, str, int]] = []

    def _scope(self) -> str:
        return ".".join([*self.class_stack, *self.function_stack]) or "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        if _is_context_process_call(node.value):
            names = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]
            if len(names) == 1 and len(node.targets) == 1:
                self.process_creations.append(
                    (self._scope(), names[0], node.lineno)
                )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if (
            node.value is not None
            and _is_context_process_call(node.value)
            and isinstance(node.target, ast.Name)
        ):
            self.process_creations.append(
                (self._scope(), node.target.id, node.lineno)
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        if (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "process_launch"
            and function.attr == "start_multiprocessing_process_no_console"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and not node.keywords
        ):
            self.policy_starts.append(
                (self._scope(), node.args[0].id, node.lineno)
            )
        elif (
            isinstance(function, ast.Attribute)
            and function.attr == "start"
            and isinstance(function.value, ast.Name)
            and not node.args
            and not node.keywords
        ):
            self.direct_starts.append(
                (self._scope(), function.value.id, node.lineno)
            )
        self.generic_visit(node)


def _is_context_process_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "context"
        and node.func.attr == "Process"
    )


def _multiprocessing_policy_errors(source: str) -> tuple[list[str], int]:
    tree = ast.parse(source, filename="credential_workflows.py")
    errors: list[str] = []
    process_launch_imports = [
        imported
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module is None
        for imported in node.names
        if imported.name == "process_launch"
    ]
    if len(process_launch_imports) != 1 or process_launch_imports[0].asname is not None:
        errors.append("process_launch_import_discipline_invalid")
    visitor = _MultiprocessingPolicyVisitor()
    visitor.visit(tree)
    for scope, variable, line in visitor.process_creations:
        starts = [
            item
            for item in visitor.policy_starts
            if item[0] == scope and item[1] == variable
        ]
        direct = [
            item
            for item in visitor.direct_starts
            if item[0] == scope and item[1] == variable
        ]
        if len(starts) != 1:
            errors.append(
                f"{scope}:{line}:multiprocessing_policy_start_count:{len(starts)}"
            )
        if direct:
            errors.append(f"{scope}:{line}:multiprocessing_direct_start_forbidden")
    for scope, variable, line in visitor.policy_starts:
        creations = [
            item
            for item in visitor.process_creations
            if item[0] == scope and item[1] == variable
        ]
        if len(creations) != 1:
            errors.append(
                f"{scope}:{line}:multiprocessing_policy_start_unbound"
            )
    if len(visitor.process_creations) != 2:
        errors.append(
            f"multiprocessing_process_creation_count:{len(visitor.process_creations)}"
        )
    return errors, len(visitor.process_creations)


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

    def test_windows_spawn_uses_pythonw_and_restores_previous_executable(self) -> None:
        process = mock.Mock()
        previous = b"C:\\Runtime\\python.exe"
        hidden = "C:\\Runtime\\pythonw.exe"
        events: list[tuple[str, object]] = []

        def set_executable(value: object) -> None:
            events.append(("set", value))

        def start() -> None:
            events.append(("start", None))

        process.start.side_effect = start
        with (
            mock.patch.object(process_launch, "_IS_WINDOWS", True),
            mock.patch.object(
                process_launch,
                "_windows_pythonw_executable",
                return_value=hidden,
            ),
            mock.patch.object(
                process_launch.multiprocessing_spawn,
                "get_executable",
                return_value=previous,
            ),
            mock.patch.object(
                process_launch.multiprocessing,
                "set_executable",
                side_effect=set_executable,
            ),
        ):
            process_launch.start_multiprocessing_process_no_console(process)

        self.assertEqual(
            events,
            [("set", hidden), ("start", None), ("set", previous)],
        )

    def test_windows_spawn_restores_previous_executable_after_start_failure(self) -> None:
        process = mock.Mock()
        process.start.side_effect = RuntimeError("synthetic start failure")
        previous = b"C:\\Runtime\\python.exe"
        with (
            mock.patch.object(process_launch, "_IS_WINDOWS", True),
            mock.patch.object(
                process_launch,
                "_windows_pythonw_executable",
                return_value="C:\\Runtime\\pythonw.exe",
            ),
            mock.patch.object(
                process_launch.multiprocessing_spawn,
                "get_executable",
                return_value=previous,
            ),
            mock.patch.object(
                process_launch.multiprocessing,
                "set_executable",
            ) as set_executable,
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic start failure"):
                process_launch.start_multiprocessing_process_no_console(process)

        self.assertEqual(
            [call.args[0] for call in set_executable.call_args_list],
            ["C:\\Runtime\\pythonw.exe", previous],
        )

    def test_non_windows_spawn_uses_ordinary_process_start(self) -> None:
        process = mock.Mock()
        with mock.patch.object(process_launch, "_IS_WINDOWS", False):
            process_launch.start_multiprocessing_process_no_console(process)
        process.start.assert_called_once_with()

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

        sources = {
            source.name: source.read_text(encoding="utf-8")
            for source in sorted(PACKAGE_ROOT.glob("*.py"))
        }
        errors, direct_call_count = _direct_subprocess_policy_errors(sources)

        self.assertGreater(direct_call_count, 0)
        self.assertEqual(errors, [])

    def test_direct_subprocess_ast_policy_rejects_mutants(self) -> None:
        base_sources = {
            "archive_services.py": (
                "import subprocess\n"
                "def _run_keepassxc_cli_add(argv):\n"
                "    return subprocess.run(argv, check=False)\n"
            ),
            "git_backup_plan.py": (
                "import os\n"
                "import subprocess\n"
                "def _run_transport_capped(command):\n"
                "    creation_flags = noninteractive_creationflags()\n"
                "    if os.name == 'nt':\n"
                "        creation_flags = noninteractive_creationflags(\n"
                "            subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004\n"
                "        )\n"
                "    return subprocess.Popen(command, creationflags=creation_flags)\n"
            ),
        }
        mutants = {
            "missing": (
                "import subprocess\n"
                "def probe():\n"
                "    return subprocess.run(['probe'])\n",
                "subprocess_creationflags_missing",
            ),
            "raw-zero": (
                "import subprocess\n"
                "def probe():\n"
                "    return subprocess.run(['probe'], creationflags=0)\n",
                "subprocess_creationflags_not_common_policy",
            ),
            "helper-positional-argument": (
                "import subprocess\n"
                "def probe():\n"
                "    return subprocess.run(\n"
                "        ['probe'], creationflags=noninteractive_creationflags(0)\n"
                "    )\n",
                "subprocess_creationflags_not_common_policy",
            ),
            "aliased-subprocess-import": (
                "import subprocess as child_process\n"
                "def probe():\n"
                "    return child_process.run(['probe'])\n",
                "subprocess_import_alias_forbidden",
            ),
            "from-subprocess-import": (
                "from subprocess import Popen\n"
                "def probe():\n"
                "    return Popen(['probe'])\n",
                "subprocess_from_import_forbidden",
            ),
            "count-offset": (
                "import subprocess\n"
                "creationflags = object()\n"
                "def missing():\n"
                "    return subprocess.run(['missing'])\n"
                "def declared():\n"
                "    return subprocess.run(\n"
                "        ['declared'], creationflags=noninteractive_creationflags()\n"
                "    )\n",
                "subprocess_creationflags_missing",
            ),
        }
        for label, (mutant, expected_error) in mutants.items():
            with self.subTest(label=label):
                sources = {**base_sources, "mutant.py": mutant}
                errors, _call_count = _direct_subprocess_policy_errors(sources)
                self.assertTrue(
                    any(expected_error in error for error in errors),
                    errors,
                )
                if label == "count-offset":
                    combined = "\n".join(sources.values())
                    self.assertEqual(
                        len(DIRECT_SUBPROCESS_RE.findall(combined)),
                        len(CREATIONFLAGS_RE.findall(combined)) + 1,
                    )

    def test_production_multiprocessing_children_use_no_console_policy(self) -> None:
        source = Path(credential_workflows.__file__).read_text(encoding="utf-8")
        errors, process_count = _multiprocessing_policy_errors(source)

        self.assertEqual(process_count, 2)
        self.assertEqual(errors, [])

    def test_multiprocessing_ast_policy_rejects_mutants(self) -> None:
        header = (
            "from . import process_launch\n"
            "class First:\n"
            "    def run_worker(self):\n"
            "        context = multiprocessing.get_context('spawn')\n"
            "        process = context.Process(target=first)\n"
        )
        second = (
            "class Second:\n"
            "    def run_worker(self):\n"
            "        context = multiprocessing.get_context('spawn')\n"
            "        process = context.Process(target=second)\n"
            "        process_launch.start_multiprocessing_process_no_console(process)\n"
        )
        mutants = {
            "missing": (
                header + second,
                "multiprocessing_policy_start_count:0",
            ),
            "raw-direct-start": (
                header + "        process.start()\n" + second,
                "multiprocessing_direct_start_forbidden",
            ),
            "count-offset": (
                header
                + second
                + "        process_launch.start_multiprocessing_process_no_console(process)\n",
                "multiprocessing_policy_start_count:0",
            ),
        }
        for label, (mutant, expected_error) in mutants.items():
            with self.subTest(label=label):
                errors, _process_count = _multiprocessing_policy_errors(mutant)
                self.assertTrue(
                    any(expected_error in error for error in errors),
                    errors,
                )
                if label == "count-offset":
                    self.assertEqual(
                        len(MULTIPROCESS_PROCESS_RE.findall(mutant)),
                        len(POLICY_PROCESS_START_RE.findall(mutant)),
                    )
                    self.assertEqual(
                        len(DIRECT_PROCESS_START_RE.findall(mutant)),
                        0,
                    )

    def test_project_bridge_bootstrap_hides_its_git_child(self) -> None:
        source = archive_services.WOM_KIT_PROJECT_BRIDGE_BOOTSTRAP
        errors, call_count = _bridge_subprocess_policy_errors(source)
        self.assertEqual(call_count, 1)
        self.assertEqual(errors, [])

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
            first_observed_generation: dict[Path, os.stat_result] = {}
            projected_directory_generations: list[os.stat_result] = []
            real_directory_identity = doctor._inventory_directory_identity

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
                canonical = Path(path)
                generation = real_lstat(path)
                observed.append(canonical)
                first_observed_generation.setdefault(canonical, generation)
                return generation

            def projected_directory_identity(
                generation: os.stat_result,
            ) -> tuple[int, ...]:
                projected_directory_generations.append(generation)
                return real_directory_identity(generation)

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
                mock.patch.object(
                    doctor,
                    "_inventory_directory_identity",
                    side_effect=projected_directory_identity,
                ),
            ):
                doctor._check_symlink_boundaries()

            canonical_root = doctor.archive_root
            canonical_nested = canonical_root / "nested"
            canonical_file = canonical_nested / "record.json"
            counts = Counter(observed)
            # The root has its separate immutable boundary revalidation; the
            # performance regression concerned projection from the first
            # scandir-child generation. Traversal later revalidates a queued
            # directory before and after retaining its safe directory handle.
            self.assertGreaterEqual(counts[canonical_root], 1)
            self.assertGreaterEqual(counts[canonical_nested], 1)
            self.assertEqual(counts[canonical_file], 1)
            self.assertEqual(
                sum(
                    generation
                    is first_observed_generation[canonical_nested]
                    for generation in projected_directory_generations
                ),
                1,
            )
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
