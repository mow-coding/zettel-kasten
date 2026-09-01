from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
TESTS_ROOT = Path(__file__).resolve().parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(TESTS_ROOT) not in sys.path:
    sys.path.append(str(TESTS_ROOT))

from wom_kit import project_runtime
from wom_kit.legacy_cleanup_bound_delete import LegacyCleanupBoundDeleteError

from test_project_runtime import (
    _supply_for_dependency,
    _write_dependency_wheel,
    _write_minimal_wheel,
)


WINDOWS_RUNTIME = (
    os.name == "nt"
    and sys.version_info[:2] == (3, 12)
    and platform.machine().casefold() in {"amd64", "x86_64"}
)


class CompleteRuntimeCandidateTests(unittest.TestCase):
    def _prepare(
        self,
        root: Path,
        project: Path,
        transaction_ref: str,
        *,
        created_at: str = "2026-08-23T12:34:56Z",
        progress_callback: Callable[
            [str, str, int | None, int | None], None
        ] | None = None,
    ) -> tuple[
        project_runtime.PreparedRuntimeCandidate,
        project_runtime.BootstrapWheel,
        project_runtime.RuntimeSupplyLock,
    ]:
        transaction = (
            project
            / project_runtime.PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
            / transaction_ref
        )
        transaction.mkdir(parents=True)
        wheel_path = root / "wom_kit-0.4.3-py3-none-any.whl"
        dependency_path = root / "synthetic_dependency-1.2.3-cp312-cp312-win_amd64.whl"
        if not wheel_path.exists():
            wheel_path = _write_minimal_wheel(root, "0.4.3")
        if not dependency_path.exists():
            dependency_path = _write_dependency_wheel(root)
        supply = _supply_for_dependency(dependency_path)
        bootstrap = project_runtime.BootstrapWheel(
            version="0.4.3",
            tag="v0.4.3",
            url=(
                "https://github.com/mow-coding/zettel-kasten/releases/download/"
                "v0.4.3/wom_kit-0.4.3-py3-none-any.whl"
            ),
            sha256=hashlib.sha256(wheel_path.read_bytes()).hexdigest(),
            file_name=wheel_path.name,
        )
        sources = {
            wheel_path.name: wheel_path,
            dependency_path.name: dependency_path,
        }

        def copy_artifact(**kwargs: object) -> int:
            destination = kwargs["destination"]
            assert isinstance(destination, Path)
            source = sources[destination.name]
            shutil.copyfile(source, destination)
            return source.stat().st_size

        with patch.object(
            project_runtime,
            "_download_exact_artifact",
            side_effect=copy_artifact,
        ):
            candidate = project_runtime.prepare_runtime_candidate(
                project,
                transaction,
                target="v0.4.3",
                target_commit="b" * 40,
                bootstrap=bootstrap,
                supply=supply,
                running_version="0.4.3",
                receipt_created_at=created_at,
                progress_callback=progress_callback,
            )
        return candidate, bootstrap, supply

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Complete project runtime candidates are CPython 3.12 Windows AMD64.",
    )
    def test_runtime_script_cleanup_retries_only_transient_windows_locks(
        self,
    ) -> None:
        import ctypes

        def make_runtime(root: Path) -> tuple[Path, Path]:
            runtime = root / "runtime"
            scripts = runtime / "Scripts"
            scripts.mkdir(parents=True)
            (scripts / "python.exe").write_bytes(b"python")
            (scripts / "pythonw.exe").write_bytes(b"pythonw")
            removable = scripts / "archive.exe"
            removable.write_bytes(b"launcher")
            return runtime, removable

        def transient_open_error(winerror: int) -> LegacyCleanupBoundDeleteError:
            error = LegacyCleanupBoundDeleteError(
                "legacy_cleanup_bound_win32_open_uncertain"
            )
            error.__cause__ = ctypes.WinError(winerror)
            return error

        original_delete = project_runtime._delete_exact_owned_runtime_file

        for winerror in sorted(
            project_runtime.PROJECT_RUNTIME_TRANSIENT_WINDOWS_ERRORS
        ):
            with self.subTest(winerror=winerror), tempfile.TemporaryDirectory() as tmp:
                runtime, removable = make_runtime(Path(tmp) / "transient")
                attempts = 0

                def transient_once(
                    root: Path,
                    path: Path,
                    record: dict[str, object],
                ) -> None:
                    nonlocal attempts
                    attempts += 1
                    if attempts == 1:
                        raise transient_open_error(winerror)
                    original_delete(root, path, record)

                with patch.object(
                    project_runtime,
                    "_delete_exact_owned_runtime_file",
                    side_effect=transient_once,
                ), patch.object(project_runtime.time, "sleep") as sleep:
                    project_runtime._prune_runtime_scripts(runtime)
                self.assertEqual(attempts, 2)
                sleep.assert_called_once()
                self.assertFalse(removable.exists())

        with tempfile.TemporaryDirectory() as tmp:
            runtime, removable = make_runtime(Path(tmp) / "persistent")
            attempts = 0

            def always_locked(
                root: Path,
                path: Path,
                record: dict[str, object],
            ) -> None:
                del root, path, record
                nonlocal attempts
                attempts += 1
                raise transient_open_error(32)

            with patch.object(
                project_runtime,
                "_delete_exact_owned_runtime_file",
                side_effect=always_locked,
            ), patch.object(project_runtime.time, "sleep") as sleep:
                with self.assertRaisesRegex(
                    project_runtime.ProjectRuntimeError,
                    "project_runtime_scripts_cleanup_failed",
                ):
                    project_runtime._prune_runtime_scripts(runtime)
            self.assertEqual(
                attempts,
                project_runtime.PROJECT_RUNTIME_TRANSIENT_UNLINK_ATTEMPTS,
            )
            self.assertEqual(
                sleep.call_count,
                project_runtime.PROJECT_RUNTIME_TRANSIENT_UNLINK_ATTEMPTS - 1,
            )
            self.assertTrue(removable.exists())

        for semantic_code in (
            "legacy_cleanup_bound_win32_disposition_uncertain",
            "legacy_cleanup_bound_win32_close_uncertain",
        ):
            with self.subTest(code=semantic_code), tempfile.TemporaryDirectory() as tmp:
                runtime, removable = make_runtime(Path(tmp) / "semantic")
                attempts = 0

                def semantic_failure(
                    root: Path,
                    path: Path,
                    record: dict[str, object],
                ) -> None:
                    del root, path, record
                    nonlocal attempts
                    attempts += 1
                    error = LegacyCleanupBoundDeleteError(semantic_code)
                    error.__cause__ = ctypes.WinError(32)
                    raise error

                with patch.object(
                    project_runtime,
                    "_delete_exact_owned_runtime_file",
                    side_effect=semantic_failure,
                ), patch.object(project_runtime.time, "sleep") as sleep:
                    with self.assertRaisesRegex(
                        project_runtime.ProjectRuntimeError,
                        "project_runtime_scripts_cleanup_failed",
                    ):
                        project_runtime._prune_runtime_scripts(runtime)
                self.assertEqual(attempts, 1)
                sleep.assert_not_called()
                self.assertTrue(removable.exists())

        with tempfile.TemporaryDirectory() as tmp:
            runtime, removable = make_runtime(Path(tmp) / "replacement")
            attempts = 0

            def replace_during_lock(
                root: Path,
                path: Path,
                record: dict[str, object],
            ) -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    path.unlink()
                    path.write_bytes(b"foreign-replacement")
                    raise transient_open_error(32)
                original_delete(root, path, record)

            with patch.object(
                project_runtime,
                "_delete_exact_owned_runtime_file",
                side_effect=replace_during_lock,
            ), patch.object(project_runtime.time, "sleep") as sleep:
                with self.assertRaisesRegex(
                    project_runtime.ProjectRuntimeError,
                    "project_runtime_scripts_unsafe",
                ):
                    project_runtime._prune_runtime_scripts(runtime)
            self.assertEqual(attempts, 2)
            sleep.assert_called_once()
            self.assertEqual(removable.read_bytes(), b"foreign-replacement")

    def test_runtime_bytecode_cleanup_retries_one_exact_tree_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "runtime"
            bytecode_directory = runtime / "package" / "__pycache__"
            bytecode_directory.mkdir(parents=True)
            bytecode = bytecode_directory / "module.cpython-312.pyc"
            bytecode_bytes = b"synthetic-bytecode"
            bytecode.write_bytes(bytecode_bytes)
            attempts = 0

            def transient_then_stable(
                observed_runtime: Path,
                **kwargs: object,
            ) -> list[tuple[str, Path, int, str]]:
                nonlocal attempts
                attempts += 1
                self.assertEqual(observed_runtime, runtime)
                self.assertEqual(
                    kwargs,
                    {"require_stable_tree_generation": True},
                )
                if attempts == 1:
                    raise project_runtime.ProjectRuntimeError(
                        "project_runtime_tree_changed"
                    )
                return [
                    (
                        "package/__pycache__/module.cpython-312.pyc",
                        bytecode,
                        len(bytecode_bytes),
                        hashlib.sha256(bytecode_bytes).hexdigest(),
                    )
                ]

            with patch.object(
                project_runtime,
                "_walk_regular_files",
                side_effect=transient_then_stable,
            ), patch.object(project_runtime.time, "sleep") as sleep:
                project_runtime._remove_runtime_bytecode(runtime)

            self.assertEqual(attempts, 2)
            self.assertEqual(
                [item.args for item in sleep.call_args_list],
                [
                    (
                        project_runtime
                        .PROJECT_RUNTIME_TRANSIENT_TREE_SCAN_BACKOFF_SECONDS,
                    )
                ],
            )
            self.assertFalse(bytecode.exists())
            self.assertFalse(bytecode_directory.exists())

    def test_runtime_bytecode_cleanup_exhausts_tree_changes_without_delete(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "runtime"
            bytecode_directory = runtime / "package" / "__pycache__"
            bytecode_directory.mkdir(parents=True)
            bytecode = bytecode_directory / "module.cpython-312.pyc"
            bytecode_bytes = b"must-remain"
            bytecode.write_bytes(bytecode_bytes)
            attempts = 0

            def always_changed(
                observed_runtime: Path,
                **kwargs: object,
            ) -> list[tuple[str, Path, int, str]]:
                nonlocal attempts
                attempts += 1
                self.assertEqual(observed_runtime, runtime)
                self.assertEqual(
                    kwargs,
                    {"require_stable_tree_generation": True},
                )
                raise project_runtime.ProjectRuntimeError(
                    "project_runtime_tree_changed"
                )

            with patch.object(
                project_runtime,
                "_walk_regular_files",
                side_effect=always_changed,
            ), patch.object(project_runtime.time, "sleep") as sleep:
                with self.assertRaisesRegex(
                    project_runtime.ProjectRuntimeError,
                    "project_runtime_tree_changed",
                ):
                    project_runtime._remove_runtime_bytecode(runtime)

            self.assertEqual(
                attempts,
                project_runtime.PROJECT_RUNTIME_TRANSIENT_TREE_SCAN_ATTEMPTS,
            )
            self.assertEqual(
                [item.args for item in sleep.call_args_list],
                [
                    (
                        project_runtime
                        .PROJECT_RUNTIME_TRANSIENT_TREE_SCAN_BACKOFF_SECONDS,
                    ),
                    (
                        project_runtime
                        .PROJECT_RUNTIME_TRANSIENT_TREE_SCAN_BACKOFF_SECONDS
                        * 2,
                    ),
                ],
            )
            self.assertEqual(bytecode.read_bytes(), bytecode_bytes)
            self.assertTrue(bytecode_directory.is_dir())

    def test_runtime_bytecode_cleanup_does_not_retry_nonexact_tree_errors(
        self,
    ) -> None:
        failures = (
            ("project_runtime_tree_unsafe",),
            ("project_runtime_tree_changed", "nonexact-detail"),
        )
        for failure_args in failures:
            with (
                self.subTest(failure_args=failure_args),
                tempfile.TemporaryDirectory() as tmp,
            ):
                runtime = Path(tmp) / "runtime"
                bytecode_directory = runtime / "package" / "__pycache__"
                bytecode_directory.mkdir(parents=True)
                bytecode = bytecode_directory / "module.cpython-312.pyc"
                bytecode_bytes = b"must-remain"
                bytecode.write_bytes(bytecode_bytes)
                failure = project_runtime.ProjectRuntimeError(*failure_args)

                with patch.object(
                    project_runtime,
                    "_walk_regular_files",
                    side_effect=failure,
                ) as walk, patch.object(
                    project_runtime.time,
                    "sleep",
                ) as sleep:
                    with self.assertRaises(
                        project_runtime.ProjectRuntimeError
                    ) as caught:
                        project_runtime._remove_runtime_bytecode(runtime)

                self.assertEqual(caught.exception.args, failure_args)
                walk.assert_called_once_with(
                    runtime,
                    require_stable_tree_generation=True,
                )
                sleep.assert_not_called()
                self.assertEqual(bytecode.read_bytes(), bytecode_bytes)
                self.assertTrue(bytecode_directory.is_dir())

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Complete project runtime candidates are CPython 3.12 Windows AMD64.",
    )
    def test_complete_candidate_survives_one_transient_script_prune_open(
        self,
    ) -> None:
        import ctypes

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            events: list[tuple[str, str]] = []
            attempts = 0
            injected = 0
            original_delete = project_runtime._delete_exact_owned_runtime_file

            def transient_once(
                runtime_root: Path,
                path: Path,
                record: dict[str, object],
            ) -> None:
                nonlocal attempts, injected
                attempts += 1
                if injected == 0:
                    injected += 1
                    error = LegacyCleanupBoundDeleteError(
                        "legacy_cleanup_bound_win32_open_uncertain"
                    )
                    error.__cause__ = ctypes.WinError(32)
                    raise error
                original_delete(runtime_root, path, record)

            with patch.object(
                project_runtime,
                "_delete_exact_owned_runtime_file",
                side_effect=transient_once,
            ):
                candidate, _bootstrap, _supply = self._prepare(
                    root,
                    project,
                    "txn-transient-prune-001",
                    progress_callback=lambda stage, phase, _current, _total: events.append(
                        (stage, phase)
                    ),
                )

            self.assertEqual(injected, 1)
            self.assertGreaterEqual(attempts, 2)
            self.assertTrue(candidate.public_summary()["complete_runtime_image"])
            self.assertTrue(candidate.verification["pip_check"])
            self.assertIn(
                ("project-runtime-candidate-prune-scripts", "done"),
                events,
            )
            self.assertIn(
                ("project-runtime-candidate-static-inventory", "done"),
                events,
            )
            self.assertIn(
                ("project-runtime-candidate-pip-check", "done"),
                events,
            )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Complete project runtime candidates are CPython 3.12 Windows AMD64.",
    )
    def test_partial_candidate_is_preserved_for_transaction_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            transaction = (
                project
                / project_runtime.PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
                / "txn-partial-001"
            )
            transaction.mkdir(parents=True)
            wheel_path = _write_minimal_wheel(root, "0.4.3")
            dependency_path = _write_dependency_wheel(root)
            supply = _supply_for_dependency(dependency_path)
            bootstrap = project_runtime.BootstrapWheel(
                version="0.4.3",
                tag="v0.4.3",
                url=(
                    "https://github.com/mow-coding/zettel-kasten/releases/download/"
                    "v0.4.3/wom_kit-0.4.3-py3-none-any.whl"
                ),
                sha256=hashlib.sha256(wheel_path.read_bytes()).hexdigest(),
                file_name=wheel_path.name,
            )
            with patch.object(
                project_runtime,
                "_download_exact_artifact",
                side_effect=project_runtime.ProjectRuntimeError(
                    "synthetic_preapproval_download_failure"
                ),
            ):
                with self.assertRaisesRegex(
                    project_runtime.PreparedRuntimeCandidateIncompleteError,
                    "project_runtime_candidate_preparation_incomplete",
                ):
                    project_runtime.prepare_runtime_candidate(
                        project,
                        transaction,
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=bootstrap,
                        supply=supply,
                        running_version="0.4.3",
                        receipt_created_at="2026-08-23T12:34:56Z",
                    )
            self.assertTrue(
                (transaction / project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME).is_dir()
            )
            self.assertTrue(
                (project / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT).is_dir()
            )
            self.assertFalse(
                (transaction / project_runtime.PROJECT_RUNTIME_CANDIDATE_SEAL_NAME).exists()
            )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Complete project runtime candidates are CPython 3.12 Windows AMD64.",
    )
    def test_preapproval_complete_candidate_and_static_only_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            old_runtime = (
                root
                / "untouched-project"
                / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT
                / "v0.4.2"
            )
            old_runtime.mkdir(parents=True)
            old_sentinel = old_runtime / "keep.txt"
            old_sentinel.write_bytes(b"old-runtime-must-survive")
            path_before = os.environ.get("PATH")

            original_directory_barrier = project_runtime._flush_directory_durable
            with patch.object(
                project_runtime,
                "_flush_directory_durable",
                wraps=original_directory_barrier,
            ) as observed_barrier:
                candidate, bootstrap, supply = self._prepare(
                    root,
                    project,
                    "txn-candidate-001",
                )
            barrier_paths = [call.args[0] for call in observed_barrier.call_args_list]
            self.assertIn(candidate.candidate_root, barrier_paths)
            self.assertGreaterEqual(barrier_paths.count(candidate.transaction_root), 2)
            summary = candidate.public_summary()
            self.assertTrue(summary["complete_runtime_image"])
            self.assertTrue(summary["marker_free_final_postimage"])
            self.assertFalse(summary["post_approval_child_process_allowed"])
            self.assertFalse(summary["post_approval_network_allowed"])
            self.assertFalse(summary["post_approval_copy_allowed"])
            self.assertTrue(summary["same_volume_verified"])
            rendered = json.dumps(summary, ensure_ascii=False)
            self.assertNotIn(str(project), rendered)
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("path_identities", summary)
            self.assertIn(
                ".zettel-kasten/private/version-updates/txn-candidate-001/"
                "runtime-candidate",
                summary["candidate_locator"],
            )
            self.assertFalse(
                (candidate.candidate_root / project_runtime.PROJECT_RUNTIME_INSTALLING_NAME).exists()
            )
            self.assertTrue(
                (candidate.candidate_root / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME).is_file()
            )
            self.assertEqual(os.environ.get("PATH"), path_before)

            with (
                patch.object(
                    subprocess,
                    "Popen",
                    side_effect=AssertionError("candidate reopen child forbidden"),
                ),
                patch.object(
                    project_runtime,
                    "_run_bounded",
                    side_effect=AssertionError("candidate reopen toolchain forbidden"),
                ),
                patch.object(
                    project_runtime,
                    "_trusted_pip_wheel",
                    side_effect=AssertionError("candidate reopen pip discovery forbidden"),
                ),
                patch.object(
                    urllib.request,
                    "urlopen",
                    side_effect=AssertionError("candidate reopen network forbidden"),
                ),
                patch.object(
                    socket,
                    "create_connection",
                    side_effect=AssertionError("candidate reopen socket forbidden"),
                ),
                patch.object(sys, "executable", "CANDIDATE-REOPEN-FORBIDDEN"),
            ):
                reopened = project_runtime.load_prepared_runtime_candidate(
                    project,
                    candidate.transaction_root,
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                )
            self.assertEqual(reopened.inventory_sha256, candidate.inventory_sha256)
            self.assertEqual(reopened.public_summary(), candidate.public_summary())
            candidate = reopened

            deep = (
                candidate.candidate_root
                / "Lib"
                / "site-packages"
                / "wom_kit"
                / "archive_cli.py"
            )
            before = deep.read_bytes()
            before_stat = deep.stat()
            changed = bytes([before[0] ^ 1]) + before[1:]
            self.assertEqual(len(changed), len(before))
            deep.write_bytes(changed)
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_candidate_drift",
            ):
                project_runtime.verify_prepared_runtime_candidate(
                    candidate,
                    project_root=project,
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                )
            self.assertFalse(project_runtime.cleanup_prepared_runtime_candidate(candidate))
            self.assertTrue(candidate.candidate_root.exists())
            deep.write_bytes(before)
            os.utime(
                deep,
                ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns),
            )

            extra = deep.parent / "unsealed-extra.py"
            extra.write_bytes(b"extra")
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_candidate_drift",
            ):
                project_runtime.verify_prepared_runtime_candidate(
                    candidate,
                    project_root=project,
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                )
            extra.unlink()

            hardlink = root / "candidate-hardlink"
            os.link(deep, hardlink)
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "hardlink_unsafe",
            ):
                project_runtime.verify_prepared_runtime_candidate(
                    candidate,
                    project_root=project,
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                )
            hardlink.unlink()

            symlink = deep.parent / "candidate-symlink.py"
            try:
                symlink.symlink_to(deep)
            except OSError:
                symlink = None
            if symlink is not None:
                with self.assertRaisesRegex(
                    project_runtime.ProjectRuntimeError,
                    "project_runtime_candidate_unsafe",
                ):
                    project_runtime.verify_prepared_runtime_candidate(
                        candidate,
                        project_root=project,
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=bootstrap,
                        supply=supply,
                    )
                symlink.unlink()

            forged_volume = dataclasses.replace(
                candidate,
                same_volume_identity=candidate.same_volume_identity + 1,
            )
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "identity_drift",
            ):
                project_runtime.verify_prepared_runtime_candidate(
                    forged_volume,
                    project_root=project,
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                )

            runtime_parent = project / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT
            self.assertFalse(candidate.runtime_parent_existed_before)
            quarantine = candidate.transaction_root / (
                f"runtime-candidate-cleanup-{candidate.inventory_sha256[:16]}"
            )
            with patch.object(
                project_runtime,
                "_flush_directory_durable",
                side_effect=project_runtime.ProjectRuntimeError(
                    "project_runtime_directory_durability_failed"
                ),
            ):
                self.assertFalse(
                    project_runtime.cleanup_prepared_runtime_candidate(candidate)
                )
            self.assertFalse(candidate.candidate_root.exists())
            self.assertTrue(quarantine.is_dir())
            self.assertTrue(candidate.seal_path.is_file())
            concurrent_parent_entry = runtime_parent / "concurrent-owner-entry.txt"
            concurrent_parent_entry.write_bytes(b"must-not-delete")
            self.assertFalse(project_runtime.cleanup_prepared_runtime_candidate(candidate))
            self.assertTrue(quarantine.is_dir())
            self.assertTrue(candidate.seal_path.is_file())
            self.assertEqual(concurrent_parent_entry.read_bytes(), b"must-not-delete")
            self.assertTrue(runtime_parent.is_dir())
            concurrent_parent_entry.unlink()
            self.assertTrue(project_runtime.cleanup_prepared_runtime_candidate(candidate))
            self.assertFalse(runtime_parent.exists())

            candidate, bootstrap, supply = self._prepare(
                root,
                project,
                "txn-candidate-001-promote",
            )
            self.assertFalse(candidate.runtime_parent_existed_before)

            final = project_runtime.runtime_path(project, "v0.4.3")

            def concurrent_destination(_source: Path, destination: Path) -> None:
                destination.mkdir()
                raise OSError("simulated destination race")

            with patch.object(
                project_runtime,
                "_atomic_promote_directory_no_replace",
                side_effect=concurrent_destination,
            ):
                with self.assertRaisesRegex(
                    project_runtime.ProjectRuntimeError,
                    "project_runtime_candidate_promotion_ambiguous",
                ):
                    project_runtime.promote_runtime_candidate(
                        project,
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=bootstrap,
                        supply=supply,
                        prepared_candidate=candidate,
                        mutation_tracker=project_runtime.RuntimeMutationTracker(),
                    )
            self.assertTrue(candidate.candidate_root.is_dir())
            self.assertTrue(final.is_dir())
            final.rmdir()

            with patch.object(
                project_runtime,
                "_flush_directory_durable",
                side_effect=project_runtime.ProjectRuntimeError(
                    "project_runtime_directory_durability_failed"
                ),
            ):
                with self.assertRaisesRegex(
                    project_runtime.ProjectRuntimeError,
                    "project_runtime_candidate_promotion_ambiguous",
                ):
                    project_runtime.promote_runtime_candidate(
                        project,
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=bootstrap,
                        supply=supply,
                        prepared_candidate=candidate,
                        mutation_tracker=project_runtime.RuntimeMutationTracker(),
                    )
            self.assertFalse(candidate.candidate_root.exists())
            self.assertTrue(final.is_dir())
            self.assertTrue(candidate.seal_path.is_file())
            project_runtime._atomic_promote_directory_no_replace(
                final,
                candidate.candidate_root,
            )
            original_directory_barrier(candidate.transaction_root)
            original_directory_barrier(project / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT)

            with (
                patch.object(
                    subprocess,
                    "Popen",
                    side_effect=AssertionError("postapproval child process forbidden"),
                ),
                patch.object(
                    project_runtime,
                    "_run_bounded",
                    side_effect=AssertionError("postapproval toolchain forbidden"),
                ),
                patch.object(
                    project_runtime,
                    "_trusted_pip_wheel",
                    side_effect=AssertionError("postapproval pip discovery forbidden"),
                ),
                patch.object(
                    project_runtime,
                    "_initialize_runtime_payload",
                    side_effect=AssertionError("postapproval runtime build forbidden"),
                ),
                patch.object(
                    project_runtime,
                    "_download_exact_artifact",
                    side_effect=AssertionError("postapproval download forbidden"),
                ),
                patch.object(
                    urllib.request,
                    "urlopen",
                    side_effect=AssertionError("postapproval network forbidden"),
                ),
                patch.object(
                    socket,
                    "create_connection",
                    side_effect=AssertionError("postapproval socket forbidden"),
                ),
                patch.object(
                    shutil,
                    "copyfile",
                    side_effect=AssertionError("postapproval copy forbidden"),
                ),
                patch.object(
                    shutil,
                    "copytree",
                    side_effect=AssertionError("postapproval copy forbidden"),
                ),
                patch.object(sys, "executable", "POSTAPPROVAL-FORBIDDEN"),
            ):
                installed = project_runtime.promote_runtime_candidate(
                    project,
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                    prepared_candidate=candidate,
                    mutation_tracker=project_runtime.RuntimeMutationTracker(),
                )
            self.assertTrue(installed.created)
            self.assertTrue(final.is_dir())
            self.assertFalse(candidate.candidate_root.exists())
            self.assertTrue(old_sentinel.is_file())
            self.assertEqual(old_sentinel.read_bytes(), b"old-runtime-must-survive")
            self.assertEqual(os.environ.get("PATH"), path_before)
            self.assertTrue(project_runtime.cleanup_prepared_runtime_candidate(candidate))

            # A second preapproval build is the sealed reference candidate for
            # reuse.  The postapproval reuse decision remains static-only.
            reused_candidate, reused_bootstrap, reused_supply = self._prepare(
                root,
                project,
                "txn-candidate-002",
            )
            self.assertTrue(reused_candidate.existing_runtime_reusable)
            with (
                patch.object(
                    subprocess,
                    "Popen",
                    side_effect=AssertionError("reuse child process forbidden"),
                ),
                patch.object(
                    project_runtime,
                    "_run_bounded",
                    side_effect=AssertionError("reuse toolchain forbidden"),
                ),
                patch.object(
                    project_runtime,
                    "_trusted_pip_wheel",
                    side_effect=AssertionError("reuse pip discovery forbidden"),
                ),
                patch.object(
                    urllib.request,
                    "urlopen",
                    side_effect=AssertionError("reuse network forbidden"),
                ),
                patch.object(
                    socket,
                    "create_connection",
                    side_effect=AssertionError("reuse socket forbidden"),
                ),
                patch.object(sys, "executable", "POSTAPPROVAL-FORBIDDEN"),
            ):
                reused = project_runtime.promote_runtime_candidate(
                    project,
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=reused_bootstrap,
                    supply=reused_supply,
                    prepared_candidate=reused_candidate,
                )
            self.assertFalse(reused.created)
            self.assertTrue(final.is_dir())
            self.assertTrue(reused_candidate.candidate_root.is_dir())
            self.assertTrue(
                project_runtime.cleanup_prepared_runtime_candidate(reused_candidate)
            )
            self.assertTrue(final.is_dir())

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Complete project runtime candidates are CPython 3.12 Windows AMD64.",
    )
    def test_same_version_corrupt_runtime_repair_is_crash_reopenable_and_reversible(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            baseline, bootstrap, supply = self._prepare(
                root,
                project,
                "txn-repair-baseline",
            )
            baseline_runtime = project_runtime.promote_runtime_candidate(
                project,
                target="v0.4.3",
                target_commit="b" * 40,
                bootstrap=bootstrap,
                supply=supply,
                prepared_candidate=baseline,
            )
            self.assertTrue(baseline_runtime.created)
            self.assertTrue(
                project_runtime.cleanup_prepared_runtime_candidate(baseline)
            )
            final = project_runtime.runtime_path(project, "v0.4.3")
            corrupt_path = (
                final
                / "Lib"
                / "site-packages"
                / "wom_kit"
                / "archive_cli.py"
            )
            corrupt_path.write_bytes(corrupt_path.read_bytes() + b"\n# corrupt\n")
            corrupt_bytes = corrupt_path.read_bytes()
            self.assertEqual(
                project_runtime.inspect_runtime(
                    project,
                    "v0.4.3",
                    expected_commit="b" * 40,
                    expected_wheel_sha256=bootstrap.sha256,
                    expected_supply_lock_sha256=supply.sha256,
                )["status"],
                "invalid",
            )
            plan, blockers, warnings = project_runtime.plan_runtime(
                project,
                "v0.4.3",
                policy_state="required",
                target_commit="b" * 40,
                bootstrap=bootstrap,
                bootstrap_summary=bootstrap.public_summary(),
                supply=supply,
            )
            self.assertTrue(plan["runtime_repair_required"])
            self.assertFalse(plan["repair_preimage_exactly_bound"])
            self.assertTrue(
                plan["will_bind_repair_preimage_exactly_before_approval"]
            )
            self.assertTrue(
                plan["will_preserve_during_active_transaction"]
            )
            self.assertEqual(
                plan["old_invalid_runtime_deletion_stage"],
                "terminal_cleanup_after_authenticated_success",
            )
            self.assertNotIn("project_runtime_target_directory_invalid", blockers)
            self.assertTrue(any("private replacement" in item for item in warnings))

            candidate, repair_bootstrap, repair_supply = self._prepare(
                root,
                project,
                "txn-repair-exact",
            )
            self.assertTrue(candidate.existing_runtime_repair_required)
            self.assertFalse(candidate.existing_runtime_reusable)
            self.assertEqual(
                project_runtime.runtime_repair_state(candidate),
                "preimage_final",
            )
            summary_text = json.dumps(candidate.public_summary())
            self.assertNotIn(str(project), summary_text)
            self.assertNotIn(str(root), summary_text)

            original_move = project_runtime._atomic_promote_directory_no_replace
            move_count = 0

            def fail_second_move(source: Path, destination: Path) -> None:
                nonlocal move_count
                move_count += 1
                if move_count == 2:
                    raise OSError("synthetic second rename failure")
                original_move(source, destination)

            tracker = project_runtime.RuntimeMutationTracker()
            with patch.object(
                project_runtime,
                "_atomic_promote_directory_no_replace",
                side_effect=fail_second_move,
            ):
                with self.assertRaisesRegex(
                    project_runtime.ProjectRuntimeError,
                    "project_runtime_repair_promotion_rolled_back",
                ):
                    project_runtime.promote_runtime_candidate(
                        project,
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=repair_bootstrap,
                        supply=repair_supply,
                        prepared_candidate=candidate,
                        mutation_tracker=tracker,
                    )
            self.assertTrue(tracker.cleanup_verified)
            self.assertEqual(corrupt_path.read_bytes(), corrupt_bytes)
            self.assertEqual(
                project_runtime.runtime_repair_state(candidate),
                "preimage_final",
            )

            repair_backup = project_runtime._runtime_repair_backup_path(candidate)
            original_move(final, repair_backup)
            project_runtime._flush_directory_durable(
                project / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT
            )
            project_runtime._flush_directory_durable(candidate.transaction_root)
            self.assertEqual(
                project_runtime.runtime_repair_state(candidate),
                "backup_only",
            )
            reopened = project_runtime.load_prepared_runtime_candidate(
                project,
                candidate.transaction_root,
                target="v0.4.3",
                target_commit="b" * 40,
                bootstrap=repair_bootstrap,
                supply=repair_supply,
            )
            self.assertEqual(reopened.public_summary(), candidate.public_summary())
            installed = project_runtime.promote_runtime_candidate(
                project,
                target="v0.4.3",
                target_commit="b" * 40,
                bootstrap=repair_bootstrap,
                supply=repair_supply,
                prepared_candidate=reopened,
            )
            self.assertTrue(installed.created)
            self.assertTrue(installed.repaired)
            self.assertEqual(
                project_runtime.runtime_repair_state(reopened),
                "candidate_final_plus_backup",
            )
            self.assertTrue(
                project_runtime.inspect_runtime(
                    project,
                    "v0.4.3",
                    expected_commit="b" * 40,
                    expected_wheel_sha256=repair_bootstrap.sha256,
                    expected_supply_lock_sha256=repair_supply.sha256,
                )["receipt_candidate_valid"]
            )
            self.assertTrue(
                project_runtime.remove_materialized_runtime(project, installed)
            )
            self.assertEqual(corrupt_path.read_bytes(), corrupt_bytes)
            self.assertFalse(repair_backup.exists())
            self.assertFalse(
                (
                    candidate.transaction_root
                    / project_runtime.PROJECT_RUNTIME_ROLLBACK_CANDIDATE_NAME
                ).exists()
            )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Complete project runtime candidates are CPython 3.12 Windows AMD64.",
    )
    def test_same_version_empty_runtime_repair_rolls_back_to_exact_empty_preimage(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            final = project_runtime.runtime_path(project, "v0.4.3")
            final.mkdir(parents=True)

            candidate, bootstrap, supply = self._prepare(
                root,
                project,
                "txn-repair-empty",
            )
            self.assertTrue(candidate.existing_runtime_repair_required)
            self.assertEqual(candidate.existing_runtime_inventory, ())

            installed = project_runtime.promote_runtime_candidate(
                project,
                target="v0.4.3",
                target_commit="b" * 40,
                bootstrap=bootstrap,
                supply=supply,
                prepared_candidate=candidate,
            )
            self.assertTrue(installed.repaired)
            self.assertTrue(any(final.iterdir()))

            self.assertTrue(
                project_runtime.remove_materialized_runtime(project, installed)
            )
            self.assertTrue(final.is_dir())
            self.assertEqual(tuple(final.iterdir()), ())
            self.assertTrue(
                project_runtime._runtime_inventory_matches(
                    final,
                    identity=candidate.existing_runtime_root_identity,
                    inventory=(),
                )
            )
            self.assertFalse(
                project_runtime._runtime_repair_backup_path(candidate).exists()
            )
            self.assertFalse(
                (
                    candidate.transaction_root
                    / project_runtime.PROJECT_RUNTIME_ROLLBACK_CANDIDATE_NAME
                ).exists()
            )

    def test_transaction_root_and_legacy_phase_boundary_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            outside = root / "outside-transaction"
            outside.mkdir()
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_legacy_bundle_api_disabled",
            ):
                project_runtime.prepare_runtime_bundle()
            with self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_transaction_root_invalid",
            ):
                project_runtime._candidate_paths(project, outside)


if __name__ == "__main__":
    unittest.main()
