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
            )
        return candidate, bootstrap, supply

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
