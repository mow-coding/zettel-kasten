from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib.util
import inspect
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from functools import wraps
from pathlib import Path
from typing import Any
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
TESTS_ROOT = Path(__file__).resolve().parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(TESTS_ROOT) not in sys.path:
    sys.path.append(str(TESTS_ROOT))

from wom_kit import project_runtime
from wom_kit import legacy_cleanup_bound_delete
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


@contextmanager
def _expect_exact_runtime_fault(expected_code: str):
    """Keep unexpected preflight failures' original traceback for diagnosis."""
    try:
        yield
    except project_runtime.ProjectRuntimeError as error:
        if error.args != (expected_code,):
            raise
    else:
        raise AssertionError("The exact injected runtime fault was not raised.")


_CANDIDATE_REUSE_REASONS = frozenset({
    "project_runtime_existing_missing",
    "project_runtime_existing_observation_unavailable",
    "project_runtime_existing_unsafe",
    "project_runtime_existing_install_incomplete",
    "project_runtime_existing_receipt_missing",
    "project_runtime_existing_receipt_invalid",
    "project_runtime_existing_receipt_mismatch",
    "project_runtime_existing_supply_mismatch",
    "project_runtime_existing_integrity_mismatch",
    "project_runtime_existing_artifact_mismatch",
    "project_runtime_existing_payload_mismatch",
    "project_runtime_existing_verified",
})


class _CandidateReuseObservation:
    """Failure-only projection of the second preparation's original comparison.

    The installed-journey observer supplies the same bounded runtime evidence.
    No comparison is repeated and no paths, source values or exception text are
    retained. Unknown results remain unclassified, never evidence of repair.
    """

    def __init__(self):
        self.observation = {"state": "unclassified", "reason_code": "unclassified", "matches": None}
        self.runtime_observation = None
        self.stack = ExitStack()

    def __enter__(self):
        # Load before preparation; the observed call performs no loader I/O.
        spec = importlib.util.spec_from_file_location(
            "wom_candidate_reuse_observation_driver",
            KIT_ROOT / "tools" / "check_project_runtime_wheel_journey.py",
        )
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        original = project_runtime._existing_runtime_candidate_observation
        owner_thread = threading.get_ident()

        @wraps(original)
        def observed(*args, **kwargs):
            if threading.get_ident() != owner_thread:
                return original(*args, **kwargs)
            self.observation = {"state": "unclassified", "reason_code": "unclassified", "matches": None}
            self.runtime_observation = None
            boundary = driver.RuntimeBoundaryObservation(project_runtime)
            try:
                with boundary:
                    result = original(*args, **kwargs)
            finally:
                try:
                    self.runtime_observation = boundary.snapshot()
                except Exception:
                    pass  # Diagnosis must not replace the original exception.
            if type(result) is dict:
                state, reason, matches = result.get("state"), result.get("reason_code"), result.get("matches")
                self.observation = {
                    "state": state if type(state) is str and state in {"passed", "failed", "unavailable"} else "unclassified",
                    "reason_code": reason if type(reason) is str and reason in _CANDIDATE_REUSE_REASONS else "unclassified",
                    "matches": matches if type(matches) is bool else None,
                }
            return result

        self.stack.enter_context(patch.object(project_runtime, "_existing_runtime_candidate_observation", observed))
        return self

    def __exit__(self, *exception_info):
        return self.stack.__exit__(*exception_info)

    def failure_message(self, candidate):
        reusable = candidate.existing_runtime_reusable
        repair = candidate.existing_runtime_repair_required
        return json.dumps({
            "schema": "wom-kit/test-candidate-reuse-observation/v1",
            "observation": self.observation,
            "existing_runtime_reusable": reusable if type(reusable) is bool else None,
            "existing_runtime_repair_required": repair if type(repair) is bool else None,
            "runtime_observation": self.runtime_observation,
        }, sort_keys=True)


class CompleteRuntimeCandidateTests(unittest.TestCase):
    def _candidate_inputs(
        self,
        root: Path,
    ) -> tuple[
        project_runtime.BootstrapWheel,
        project_runtime.RuntimeSupplyLock,
        dict[str, Path],
    ]:
        wheel_path = root / "wom_kit-0.4.3-py3-none-any.whl"
        dependency_path = (
            root / "synthetic_dependency-1.2.3-cp312-cp312-win_amd64.whl"
        )
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
        return bootstrap, supply, {
            wheel_path.name: wheel_path,
            dependency_path.name: dependency_path,
        }

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
        from wom_kit import project_update_transaction

        transaction_ref = (
            "update_"
            + hashlib.sha256(
                ("runtime-candidate-transaction:" + transaction_ref).encode(
                    "ascii"
                )
            ).hexdigest()[:32]
        )
        project_identity_sha256 = (
            "sha256:"
            + hashlib.sha256(
                ("runtime-candidate-project:" + transaction_ref).encode(
                    "ascii"
                )
            ).hexdigest()
        )
        ownership_nonce = hashlib.sha256(
            ("runtime-candidate-reservation:" + transaction_ref).encode(
                "ascii"
            )
        ).hexdigest()[:32]
        reservation = (
            project_update_transaction.ProjectUpdateTransaction
            .prepare_reservation(
                project_identity_sha256=project_identity_sha256,
                requested_target_tag="v0.4.3",
                transaction_ref=transaction_ref,
                ownership_nonce=ownership_nonce,
                created_at=created_at,
            )
        )
        transaction = (
            project_update_transaction.ProjectUpdateTransaction
            .reserve_or_resume_exact(
                project,
                reservation=reservation,
            )
            .transaction_root
        )
        bootstrap, supply, sources = self._candidate_inputs(root)

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

    def _small_materialization(
        self,
        project: Path,
        transaction_ref: str,
        *,
        repaired: bool = False,
        runtime_parent_existed_before: bool = False,
    ) -> tuple[
        project_runtime.RuntimeMaterialization,
        Path,
        Path,
        bytes,
        tuple[project_runtime.RuntimeCandidateInventoryEntry, ...],
        tuple[int, int],
    ]:
        transaction = (
            project
            / project_runtime.PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
            / transaction_ref
        )
        transaction.mkdir(parents=True)
        runtime_parent = project / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT
        if runtime_parent_existed_before:
            runtime_parent.mkdir(parents=True, exist_ok=True)

        backup: Path | None = None
        old_inventory: tuple[
            project_runtime.RuntimeCandidateInventoryEntry, ...
        ] = ()
        old_identity: tuple[int, int] | None = None
        if repaired:
            runtime_parent.mkdir(parents=True, exist_ok=True)
            old = project_runtime.runtime_path(project, "0.4.3")
            old.mkdir()
            (old / "previous-runtime.bin").write_bytes(b"previous-runtime")
            old_identity = project_runtime._path_identity(old)
            old_inventory = project_runtime._candidate_inventory_snapshot(old)
            backup = (
                transaction
                / project_runtime.PROJECT_RUNTIME_REPAIR_BACKUP_NAME
            )
            project_runtime._atomic_promote_directory_no_replace(old, backup)
            runtime_parent_existed_before = True

        final = project_runtime.runtime_path(project, "0.4.3")
        final.mkdir(parents=True)
        receipt_bytes = b'{"status":"verified"}\n'
        (final / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME).write_bytes(
            receipt_bytes
        )
        new_identity = project_runtime._path_identity(final)
        inventory = project_runtime._candidate_inventory_snapshot(final)
        parent_identity = project_runtime._path_identity(runtime_parent)
        runtime = project_runtime.RuntimeMaterialization(
            target_tag="v0.4.3",
            target_version="0.4.3",
            target_commit="b" * 40,
            final_path=final,
            logical_path=project_runtime.runtime_logical_path("0.4.3"),
            receipt_bytes=receipt_bytes,
            receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
            wheel_sha256="1" * 64,
            supply_lock_sha256="2" * 64,
            artifact_inventory=(),
            installed_payload_sha256="3" * 64,
            python_version="3.12.10",
            created=True,
            verification={},
            inventory=inventory,
            runtime_root_identity=new_identity,
            runtime_parent_identity=parent_identity,
            repaired=repaired,
            replaced_runtime_path=backup,
            replaced_runtime_identity=old_identity,
            replaced_runtime_inventory=old_inventory,
            transaction_root=transaction,
            transaction_root_identity=project_runtime._path_identity(
                transaction
            ),
            runtime_parent_existed_before=runtime_parent_existed_before,
            runtime_parent_created_identity=(
                None
                if runtime_parent_existed_before
                else parent_identity
            ),
        )
        return (
            runtime,
            final,
            transaction,
            receipt_bytes,
            old_inventory,
            old_identity or (0, 0),
        )

    def _small_quarantined_candidate(
        self,
        project: Path,
        transaction_ref: str,
        *,
        create_capsule: bool = True,
        move_to_quarantine: bool = True,
    ) -> tuple[
        project_runtime.PreparedRuntimeCandidate,
        Path,
        Path,
        Path,
    ]:
        """Build the durable post-rename state without constructing a wheel."""

        if not (
            transaction_ref.startswith("update_")
            and len(transaction_ref) == len("update_") + 32
            and all(
                character in "0123456789abcdef"
                for character in transaction_ref.removeprefix("update_")
            )
        ):
            transaction_ref = (
                "update_"
                + hashlib.sha256(transaction_ref.encode("utf-8")).hexdigest()[
                    :32
                ]
            )
        transaction = (
            project
            / project_runtime.PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
            / transaction_ref
        )
        transaction.mkdir(parents=True, exist_ok=True)
        append_guard = transaction / "append.guard"
        if not append_guard.exists():
            project_runtime._write_exact_new_file(append_guard, b"\x00")
            project_runtime._flush_directory_durable(transaction)
        self.assertEqual(append_guard.read_bytes(), b"\x00")
        runtime_parent = project / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT
        runtime_parent.mkdir(parents=True)
        candidate_root = (
            transaction / project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME
        )
        candidate_root.mkdir()
        (candidate_root / "root.bin").write_bytes(b"root")
        nested = candidate_root / "nested"
        nested.mkdir()
        (nested / "child.bin").write_bytes(b"child")
        (candidate_root / "empty").mkdir()
        candidate_identity = project_runtime._path_identity(candidate_root)
        inventory = project_runtime._candidate_inventory_snapshot(
            candidate_root
        )
        inventory_sha256 = (
            project_runtime._recursive_candidate_inventory_digest(inventory)
        )
        inventory_bytes = sum(item.size_bytes for item in inventory)
        project_identity = project_runtime._path_identity(project)
        transaction_identity = project_runtime._path_identity(transaction)
        runtime_parent_identity = project_runtime._path_identity(
            runtime_parent
        )
        logical_candidate_path = (
            ".zettel-kasten/private/version-updates/"
            f"{transaction_ref}/runtime-candidate"
        )
        logical_seal_path = (
            ".zettel-kasten/private/version-updates/"
            f"{transaction_ref}/runtime-candidate-seal.json"
        )
        supply_lock_bytes = b"{}\n"
        supply_lock_sha256 = hashlib.sha256(supply_lock_bytes).hexdigest()
        receipt_bytes = b'{"status":"verified"}\n'
        receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
        seal_path = (
            transaction / project_runtime.PROJECT_RUNTIME_CANDIDATE_SEAL_NAME
        )
        seal_document = {
            "schema": project_runtime.PROJECT_RUNTIME_CANDIDATE_SCHEMA,
            "status": "sealed",
            "target_tag": "v0.4.19",
            "target_commit": "b" * 40,
            "transaction_ref": transaction_ref,
            "candidate_locator": logical_candidate_path,
            "inventory_sha256": f"sha256:{inventory_sha256}",
            "candidate_sha256": "sha256:" + "3" * 64,
            "inventory_count": len(inventory),
            "inventory_bytes": inventory_bytes,
            "receipt_sha256": f"sha256:{receipt_sha256}",
            "wheel_file_name": "wom_kit-0.4.19-py3-none-any.whl",
            "wheel_sha256": "sha256:" + "1" * 64,
            "supply_lock_sha256": f"sha256:{supply_lock_sha256}",
            "same_volume_verified": True,
            "existing_runtime_reusable": False,
            "existing_runtime_repair_required": False,
            "existing_runtime_inventory_sha256": None,
            "existing_runtime_inventory_count": 0,
            "existing_runtime_inventory_bytes": 0,
            "runtime_parent_existed_before": False,
            "path_identities": {
                "project_root": list(project_identity),
                "transaction_root": list(transaction_identity),
                "candidate_root": list(candidate_identity),
                "runtime_parent": list(runtime_parent_identity),
                "runtime_parent_created": list(runtime_parent_identity),
                "existing_runtime_root": None,
            },
            "recursive_directory_durability_verified": True,
            "seal_parent_durability_required": True,
            "marker_free_final_postimage": True,
            "post_approval_child_process_allowed": False,
            "post_approval_network_allowed": False,
            "post_approval_copy_allowed": False,
            "absolute_paths_echoed": False,
        }
        seal_bytes = (
            json.dumps(
                seal_document,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        project_runtime._write_exact_new_file(seal_path, seal_bytes)
        project_runtime._flush_directory_durable(transaction)
        candidate = project_runtime.PreparedRuntimeCandidate(
            target_tag="v0.4.19",
            target_version="0.4.19",
            target_commit="b" * 40,
            transaction_ref=transaction_ref,
            logical_candidate_path=logical_candidate_path,
            logical_seal_path=logical_seal_path,
            project_root=project,
            transaction_root=transaction,
            candidate_root=candidate_root,
            seal_path=seal_path,
            project_root_identity=project_identity,
            transaction_root_identity=transaction_identity,
            candidate_root_identity=candidate_identity,
            runtime_parent_identity=runtime_parent_identity,
            runtime_parent_existed_before=False,
            runtime_parent_created_identity=runtime_parent_identity,
            same_volume_identity=candidate_identity[0],
            inventory=inventory,
            inventory_sha256=inventory_sha256,
            candidate_sha256="3" * 64,
            inventory_count=len(inventory),
            inventory_bytes=inventory_bytes,
            seal_bytes=seal_bytes,
            seal_sha256=hashlib.sha256(seal_bytes).hexdigest(),
            receipt_bytes=receipt_bytes,
            receipt_sha256=receipt_sha256,
            wheel_file_name="wom_kit-0.4.19-py3-none-any.whl",
            wheel_sha256="1" * 64,
            supply_lock_sha256=supply_lock_sha256,
            supply_lock_bytes=supply_lock_bytes,
            artifact_inventory=(),
            installed_payload_sha256="2" * 64,
            normalized_payload_inventory=(),
            python_version="3.12.10",
            installed_distributions=(),
            verification={},
            existing_runtime_reusable=False,
            existing_runtime_repair_required=False,
            existing_runtime_root_identity=None,
            existing_runtime_inventory=(),
            existing_runtime_inventory_sha256=None,
            existing_runtime_inventory_count=0,
            existing_runtime_inventory_bytes=0,
        )
        quarantine = transaction / (
            f"runtime-candidate-cleanup-{inventory_sha256[:16]}"
        )
        if create_capsule:
            capsule = project_runtime._create_runtime_candidate_cleanup_capsule(
                candidate
            )
            self.assertIsNotNone(capsule)
        if move_to_quarantine:
            self.assertTrue(create_capsule)
            project_runtime._atomic_promote_directory_no_replace(
                candidate_root,
                quarantine,
            )
            project_runtime._flush_directory_durable(transaction)
        return candidate, quarantine, seal_path, runtime_parent

    @staticmethod
    def _synthetic_runtime_cleanup_evidence(
        candidate: project_runtime.PreparedRuntimeCandidate,
    ) -> dict[str, object]:
        """Build shape-valid evidence for guard-race transaction tests."""

        from wom_kit import project_update_transaction

        capsule_sha = hashlib.sha256(
            ("capsule:" + candidate.transaction_ref).encode("ascii")
        ).hexdigest()
        capsule_identity_sha = hashlib.sha256(
            ("capsule-identity:" + candidate.transaction_ref).encode(
                "ascii"
            )
        ).hexdigest()
        return {
            "absolute_paths_echoed": False,
            "candidate_root_absent": True,
            "candidate_sha256": f"sha256:{candidate.candidate_sha256}",
            "cleanup_complete": True,
            "normal_seal_absent": True,
            "outer_transaction_ack_required_before_retire": True,
            "private_paths_echoed": False,
            "provider_inventory_bytes": candidate.inventory_bytes,
            "provider_inventory_count": candidate.inventory_count,
            "provider_inventory_sha256": (
                f"sha256:{candidate.inventory_sha256}"
            ),
            "quarantine_root_absent": True,
            "runtime_cleanup_capsule_identity_sha256": (
                f"sha256:{capsule_identity_sha}"
            ),
            "runtime_cleanup_capsule_sha256": f"sha256:{capsule_sha}",
            "runtime_parent_restored": True,
            "schema": (
                project_update_transaction
                .RUNTIME_CLEANUP_TERMINAL_EVIDENCE_SCHEMA
            ),
            "sidecar_must_retire_before_transaction_cleanup": True,
            "status": "terminal_cleanup_evidence",
            "target_tag": candidate.target_tag,
            "transaction_ref": candidate.transaction_ref,
        }

    def _reserved_small_candidate(
        self,
        project: Path,
        transaction_ref: str,
    ) -> tuple[object, bytes, project_runtime.PreparedRuntimeCandidate]:
        from wom_kit import project_update_transaction

        project_digest = (
            "sha256:"
            + hashlib.sha256(
                ("guard-project:" + transaction_ref).encode("ascii")
            ).hexdigest()
        )
        reserved = (
            project_update_transaction.ProjectUpdateTransaction.reserve(
                project,
                project_identity_sha256=project_digest,
                requested_target_tag="v0.4.19",
                transaction_ref=transaction_ref,
                ownership_nonce="0123456789abcdef0123456789abcdef",
                created_at="2026-09-05T00:00:00Z",
            )
        )
        lock_bytes = reserved.acquire_lock(
            observation=project_update_transaction.LockObservation(
                pid=1234,
                process_start="runtime-cleanup-guard-test",
            )
        )
        candidate, _quarantine, _seal, _runtime_parent = (
            self._small_quarantined_candidate(
                project,
                transaction_ref,
                create_capsule=False,
                move_to_quarantine=False,
            )
        )
        return reserved, lock_bytes, candidate

    def test_remove_materialized_runtime_has_one_imported_definition(self) -> None:
        source_path = Path(project_runtime.__file__).resolve()
        source = source_path.read_text(encoding="utf-8")
        definitions = [
            node
            for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "remove_materialized_runtime"
        ]
        self.assertEqual(len(definitions), 1)
        imported_line = inspect.getsourcelines(
            project_runtime.remove_materialized_runtime
        )[1]
        self.assertEqual(definitions[0].lineno, imported_line)
        self.assertNotIn(
            "shutil.rmtree",
            inspect.getsource(project_runtime.remove_materialized_runtime),
        )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_candidate_cleanup_tombstone_restarts_at_each_checkpoint(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for stage in (
                "rename",
                "parent",
                "child",
                "directory",
                "root",
                "seal",
            ):
                with self.subTest(stage=stage):
                    project = root / f"project-{stage}"
                    project.mkdir()
                    candidate, quarantine, seal, runtime_parent = (
                        self._small_quarantined_candidate(
                            project,
                            f"txn-cleanup-{stage}",
                            move_to_quarantine=stage != "rename",
                        )
                    )

                    if stage == "rename":
                        original_promote = (
                            project_runtime._atomic_promote_directory_no_replace
                        )
                        original_flush = project_runtime._flush_directory_durable
                        renamed = False

                        def rename_then_arm(
                            source: Path,
                            destination: Path,
                        ) -> None:
                            nonlocal renamed
                            original_promote(source, destination)
                            if destination == quarantine:
                                renamed = True

                        def stop_before_rename_parent_flush(path: Path) -> None:
                            if renamed and path == candidate.transaction_root:
                                raise project_runtime.ProjectRuntimeError(
                                    "synthetic_candidate_rename_power_cut"
                                )
                            original_flush(path)

                        interruptions = (
                            patch.object(
                                project_runtime,
                                "_atomic_promote_directory_no_replace",
                                side_effect=rename_then_arm,
                            ),
                            patch.object(
                                project_runtime,
                                "_flush_directory_durable",
                                side_effect=stop_before_rename_parent_flush,
                            ),
                        )
                    elif stage == "parent":
                        original_restore = (
                            project_runtime
                            ._restore_exact_owned_runtime_parent
                        )

                        def restore_then_stop(*args: Any, **kwargs: Any) -> bool:
                            self.assertTrue(original_restore(*args, **kwargs))
                            return False

                        interruptions = (
                            patch.object(
                                project_runtime,
                                "_restore_exact_owned_runtime_parent",
                                side_effect=restore_then_stop,
                            ),
                        )
                    elif stage == "child":
                        original_delete_file = (
                            legacy_cleanup_bound_delete
                            ._delete_exact_approved_file
                        )
                        original_flush = project_runtime._flush_directory_durable
                        child_deleted = False

                        def delete_child_then_arm(
                            approved_root: Path,
                            path: Path,
                            record: dict[str, Any],
                        ) -> None:
                            nonlocal child_deleted
                            original_delete_file(approved_root, path, record)
                            if quarantine in path.parents:
                                child_deleted = True

                        def stop_before_child_parent_flush(path: Path) -> None:
                            if child_deleted:
                                raise project_runtime.ProjectRuntimeError(
                                    "synthetic_child_delete_power_cut"
                                )
                            original_flush(path)

                        interruptions = (
                            patch.object(
                                legacy_cleanup_bound_delete,
                                "_delete_exact_approved_file",
                                side_effect=delete_child_then_arm,
                            ),
                            patch.object(
                                project_runtime,
                                "_flush_directory_durable",
                                side_effect=stop_before_child_parent_flush,
                            ),
                        )
                    elif stage == "directory":
                        original_delete_directory = (
                            legacy_cleanup_bound_delete
                            ._delete_exact_approved_empty_directory
                        )
                        original_flush = project_runtime._flush_directory_durable
                        directory_deleted = False

                        def delete_directory_then_arm(
                            approved_root: Path,
                            path: Path,
                            record: dict[str, Any],
                        ) -> None:
                            nonlocal directory_deleted
                            original_delete_directory(
                                approved_root,
                                path,
                                record,
                            )
                            if quarantine in path.parents:
                                directory_deleted = True

                        def stop_before_directory_parent_flush(path: Path) -> None:
                            if directory_deleted:
                                raise project_runtime.ProjectRuntimeError(
                                    "synthetic_directory_delete_power_cut"
                                )
                            original_flush(path)

                        interruptions = (
                            patch.object(
                                legacy_cleanup_bound_delete,
                                "_delete_exact_approved_empty_directory",
                                side_effect=delete_directory_then_arm,
                            ),
                            patch.object(
                                project_runtime,
                                "_flush_directory_durable",
                                side_effect=(
                                    stop_before_directory_parent_flush
                                ),
                            ),
                        )
                    elif stage == "seal":
                        original_delete_seal = (
                            project_runtime._delete_exact_cleanup_bound_seal
                        )

                        def delete_seal_then_stop(
                            cleanup_capsule: (
                                project_runtime.RuntimeCandidateCleanupCapsule
                            ),
                        ) -> bool:
                            self.assertTrue(
                                original_delete_seal(cleanup_capsule)
                            )
                            return False

                        interruptions = (
                            patch.object(
                                project_runtime,
                                "_delete_exact_cleanup_bound_seal",
                                side_effect=delete_seal_then_stop,
                            ),
                        )
                    else:
                        original_delete_root = (
                            project_runtime._delete_exact_empty_inventory_root
                        )

                        def delete_root_then_stop(
                            path: Path,
                            *,
                            root_identity: tuple[int, int],
                        ) -> bool:
                            self.assertTrue(
                                original_delete_root(
                                    path,
                                    root_identity=root_identity,
                                )
                            )
                            return False

                        interruptions = (
                            patch.object(
                                project_runtime,
                                "_delete_exact_empty_inventory_root",
                                side_effect=delete_root_then_stop,
                            ),
                        )

                    with ExitStack() as stack:
                        for interruption in interruptions:
                            stack.enter_context(interruption)
                        self.assertFalse(
                            project_runtime.cleanup_prepared_runtime_candidate(
                                candidate
                            )
                        )

                    if stage in {"rename", "parent", "child", "directory"}:
                        self.assertTrue(quarantine.is_dir())
                        self.assertTrue(seal.is_file())
                    elif stage == "seal":
                        self.assertFalse(quarantine.exists())
                        self.assertFalse(seal.exists())
                    else:
                        self.assertFalse(quarantine.exists())
                        self.assertTrue(seal.exists())
                    if stage == "rename":
                        self.assertTrue(runtime_parent.is_dir())
                    else:
                        self.assertFalse(runtime_parent.exists())
                    reopened = (
                        project_runtime.load_runtime_candidate_cleanup_capsule(
                            project,
                            candidate.transaction_root,
                        )
                    )
                    resumed = project_runtime.resume_runtime_candidate_cleanup(
                        reopened
                    )
                    self.assertIsInstance(
                        resumed,
                        project_runtime.RuntimeCandidateCleanupCapsule,
                    )
                    self.assertFalse(quarantine.exists())
                    self.assertFalse(seal.exists())
                    self.assertFalse(runtime_parent.exists())
                    self.assertTrue(reopened.capsule_path.is_file())

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_candidate_cleanup_preserves_foreign_quarantine_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            candidate, quarantine, seal, _runtime_parent = (
                self._small_quarantined_candidate(
                    project,
                    "txn-cleanup-foreign-root",
                )
            )
            owned_elsewhere = root / "owned-empty-quarantine"
            original_delete_root = (
                project_runtime._delete_exact_empty_inventory_root
            )

            def replace_before_root_delete(
                path: Path,
                *,
                root_identity: tuple[int, int],
            ) -> bool:
                path.rename(owned_elsewhere)
                path.mkdir()
                (path / "foreign-owner.bin").write_bytes(b"preserve")
                return original_delete_root(
                    path,
                    root_identity=root_identity,
                )

            with patch.object(
                project_runtime,
                "_delete_exact_empty_inventory_root",
                side_effect=replace_before_root_delete,
            ):
                self.assertFalse(
                    project_runtime.resume_runtime_candidate_cleanup(
                        project_runtime.load_runtime_candidate_cleanup_capsule(
                            project,
                            candidate.transaction_root,
                        )
                    )
                )
            self.assertTrue(seal.exists())
            self.assertTrue(owned_elsewhere.is_dir())
            self.assertTrue(quarantine.is_dir())
            self.assertEqual(
                (quarantine / "foreign-owner.bin").read_bytes(),
                b"preserve",
            )
            self.assertFalse(
                project_runtime.resume_runtime_candidate_cleanup(
                    project_runtime.load_runtime_candidate_cleanup_capsule(
                        project,
                        candidate.transaction_root,
                    )
                )
            )
            self.assertTrue(owned_elsewhere.is_dir())
            self.assertEqual(
                (quarantine / "foreign-owner.bin").read_bytes(),
                b"preserve",
            )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_partial_candidate_cleanup_resumes_in_a_fresh_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            candidate, quarantine, seal, runtime_parent = (
                self._small_quarantined_candidate(
                    project,
                    "txn-cleanup-fresh-process",
                )
            )
            item = next(
                entry
                for entry in candidate.inventory
                if entry.entry_type == "file"
            )
            child = quarantine / item.relative_path
            legacy_cleanup_bound_delete._delete_exact_approved_file(
                quarantine,
                child,
                {
                    "identity": {
                        "device": item.device,
                        "inode": item.inode,
                    },
                    "mtime_ns": item.mtime_ns,
                    "sha256": item.sha256,
                    "size": item.size_bytes,
                    "type": "file",
                },
            )
            project_runtime._flush_directory_durable(child.parent)
            self.assertTrue(quarantine.is_dir())
            self.assertTrue(seal.is_file())
            self.assertTrue(runtime_parent.is_dir())

            child_code = "\n".join(
                (
                    "import sys",
                    "from pathlib import Path",
                    "from wom_kit import project_runtime",
                    "capsule = project_runtime.load_runtime_candidate_cleanup_capsule(Path(sys.argv[1]), Path(sys.argv[2]))",
                    "completed = project_runtime.resume_runtime_candidate_cleanup(capsule)",
                    "evidence = project_runtime.runtime_candidate_cleanup_terminal_evidence(completed) if completed else None",
                    "raise SystemExit(0 if evidence and completed.capsule_path.is_file() else 41)",
                )
            )
            environment = dict(os.environ)
            environment["PYTHONPATH"] = os.pathsep.join(
                filter(
                    None,
                    (
                        str(SRC_ROOT),
                        environment.get("PYTHONPATH", ""),
                    ),
                )
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    child_code,
                    str(project),
                    str(candidate.transaction_root),
                ],
                cwd=str(KIT_ROOT),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                creationflags=project_runtime.noninteractive_creationflags(),
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr.decode("utf-8", errors="replace"),
            )
            self.assertFalse(quarantine.exists())
            self.assertFalse(seal.exists())
            self.assertFalse(runtime_parent.exists())
            self.assertTrue(
                project_runtime._runtime_candidate_cleanup_capsule_path(
                    candidate.transaction_root
                ).is_file()
            )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_capsule_requires_exact_outer_ack_before_retirement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            candidate, _quarantine, _seal, _runtime_parent = (
                self._small_quarantined_candidate(
                    project,
                    "txn-cleanup-ack",
                )
            )
            completed = project_runtime.cleanup_prepared_runtime_candidate(
                candidate
            )
            self.assertIsInstance(
                completed,
                project_runtime.RuntimeCandidateCleanupCapsule,
            )
            assert completed is not None
            evidence = project_runtime.runtime_candidate_cleanup_terminal_evidence(
                completed
            )
            self.assertIsNotNone(evidence)
            assert evidence is not None
            self.assertEqual(
                set(evidence),
                {
                    "absolute_paths_echoed",
                    "candidate_root_absent",
                    "candidate_sha256",
                    "cleanup_complete",
                    "normal_seal_absent",
                    "outer_transaction_ack_required_before_retire",
                    "private_paths_echoed",
                    "provider_inventory_bytes",
                    "provider_inventory_count",
                    "provider_inventory_sha256",
                    "quarantine_root_absent",
                    "runtime_cleanup_capsule_identity_sha256",
                    "runtime_cleanup_capsule_sha256",
                    "runtime_parent_restored",
                    "schema",
                    "sidecar_must_retire_before_transaction_cleanup",
                    "status",
                    "target_tag",
                    "transaction_ref",
                },
            )
            rendered = json.dumps(evidence, sort_keys=True)
            self.assertNotIn(str(project), rendered)
            self.assertNotIn(str(root), rendered)
            from wom_kit import project_update_transaction

            forged = object.__new__(
                project_update_transaction.RuntimeCleanupDurableAck
            )
            forged_fields = {
                "transaction_ref": completed.transaction_ref,
                "target_tag": completed.target_tag,
                "authority_kind": "runtime_verified",
                "authority_record_sha256": "sha256:" + "1" * 64,
                "authority_record_identity_sha256": (
                    "sha256:" + "2" * 64
                ),
                "transaction_identity_sha256": "sha256:" + "3" * 64,
                "runtime_cleanup_terminal_evidence_sha256": (
                    project_runtime._runtime_cleanup_terminal_evidence_sha256(
                        evidence
                    )
                ),
                "runtime_cleanup_capsule_sha256": (
                    evidence["runtime_cleanup_capsule_sha256"]
                ),
                "runtime_cleanup_capsule_identity_sha256": (
                    evidence["runtime_cleanup_capsule_identity_sha256"]
                ),
                "_project_root": project,
            }
            for name, value in forged_fields.items():
                object.__setattr__(forged, name, value)

            for transient in (
                evidence["runtime_cleanup_capsule_sha256"],
                dict(evidence),
                forged,
                object(),
            ):
                with self.subTest(transient_type=type(transient).__name__):
                    self.assertFalse(
                        project_runtime.retire_runtime_candidate_cleanup_capsule(
                            completed,
                            durable_ack=transient,
                        )
                    )
                self.assertFalse(
                    project_runtime.retire_runtime_candidate_cleanup_capsule(
                        None,
                        durable_ack=transient,
                        project_root=project,
                    )
                )
            self.assertTrue(completed.capsule_path.is_file())

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_capsule_retire_uses_disk_ack_and_fresh_restart(
        self,
    ) -> None:
        from wom_kit import project_update_transaction

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            transaction_ref = "update_abcdef0123456789abcdef0123456789"
            project_digest = (
                "sha256:"
                + hashlib.sha256(b"runtime-cleanup-project").hexdigest()
            )
            reserved = (
                project_update_transaction.ProjectUpdateTransaction.reserve(
                    project,
                    project_identity_sha256=project_digest,
                    requested_target_tag="v0.4.19",
                    transaction_ref=transaction_ref,
                    ownership_nonce="0123456789abcdef0123456789abcdef",
                    created_at="2026-09-05T00:00:00Z",
                )
            )
            lock_bytes = reserved.acquire_lock(
                observation=project_update_transaction.LockObservation(
                    pid=1234,
                    process_start="runtime-cleanup-test",
                )
            )
            candidate, _quarantine, _seal, _runtime_parent = (
                self._small_quarantined_candidate(
                    project,
                    transaction_ref,
                )
            )
            completed = project_runtime.cleanup_prepared_runtime_candidate(
                candidate
            )
            self.assertIsInstance(
                completed,
                project_runtime.RuntimeCandidateCleanupCapsule,
            )
            assert completed is not None
            evidence = project_runtime.runtime_candidate_cleanup_terminal_evidence(
                completed
            )
            self.assertIsNotNone(evidence)
            assert evidence is not None
            self.assertEqual(
                project_runtime._runtime_cleanup_terminal_evidence_sha256(
                    evidence
                ),
                project_update_transaction.sha256_document(evidence),
            )
            reserved.abort_before_intent_seal(
                expected_lock_bytes=lock_bytes,
                runtime_cleanup_terminal_evidence=evidence,
            )
            ack = (
                project_update_transaction
                .load_runtime_cleanup_durable_ack(
                    project,
                    transaction_ref,
                )
            )
            self.assertIsNotNone(ack)
            assert ack is not None
            self.assertTrue(
                project_update_transaction
                .revalidate_runtime_cleanup_durable_ack(ack)
            )
            original_delete_file = (
                legacy_cleanup_bound_delete._delete_exact_approved_file
            )

            def delete_capsule_then_stop(
                approved_root: Path,
                path: Path,
                record: dict[str, Any],
            ) -> None:
                original_delete_file(approved_root, path, record)
                if path == completed.capsule_path:
                    raise project_runtime.ProjectRuntimeError(
                        "synthetic_capsule_retire_power_cut"
                    )

            with patch.object(
                legacy_cleanup_bound_delete,
                "_delete_exact_approved_file",
                side_effect=delete_capsule_then_stop,
            ):
                self.assertFalse(
                    project_runtime.retire_runtime_candidate_cleanup_capsule(
                        completed,
                        durable_ack=ack,
                    )
                )
            self.assertFalse(completed.capsule_path.exists())

            environment = dict(os.environ)
            environment.update(
                {
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(SRC_ROOT),
                    "PYTHONUTF8": "1",
                }
            )
            worker = "\n".join(
                (
                    "from pathlib import Path",
                    "from wom_kit import project_runtime",
                    "from wom_kit import project_update_transaction",
                    "root = Path(__import__('sys').argv[1])",
                    "ref = __import__('sys').argv[2]",
                    "ack = project_update_transaction."
                    "load_runtime_cleanup_durable_ack(root, ref)",
                    "assert ack is not None",
                    "assert project_runtime."
                    "retire_runtime_candidate_cleanup_capsule("
                    "None, durable_ack=ack, project_root=root)",
                )
            )
            restarted = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    worker,
                    str(project),
                    transaction_ref,
                ],
                cwd=str(KIT_ROOT),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                creationflags=project_runtime.noninteractive_creationflags(),
                check=False,
            )
            self.assertEqual(
                restarted.returncode,
                0,
                restarted.stderr.decode("utf-8", errors="replace"),
            )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_capsule_is_durable_before_candidate_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            candidate, quarantine, seal, runtime_parent = (
                self._small_quarantined_candidate(
                    project,
                    "txn-cleanup-capsule-barrier",
                    create_capsule=False,
                    move_to_quarantine=False,
                )
            )
            capsule_path = (
                project_runtime._runtime_candidate_cleanup_capsule_path(
                    candidate.transaction_root
                )
            )
            self.assertEqual(
                capsule_path.parent,
                candidate.transaction_root.parent,
            )
            self.assertNotIn(candidate.transaction_root, capsule_path.parents)
            original_flush = project_runtime._flush_directory_durable

            def stop_after_capsule_create(path: Path) -> None:
                if (
                    path == candidate.transaction_root.parent
                    and capsule_path.is_file()
                ):
                    raise project_runtime.ProjectRuntimeError(
                        "synthetic_capsule_parent_power_cut"
                    )
                original_flush(path)

            with patch.object(
                project_runtime,
                "_flush_directory_durable",
                side_effect=stop_after_capsule_create,
            ):
                self.assertIsNone(
                    project_runtime._create_runtime_candidate_cleanup_capsule(
                        candidate
                    )
                )
            self.assertTrue(capsule_path.is_file())
            self.assertTrue(candidate.candidate_root.is_dir())
            self.assertFalse(quarantine.exists())
            self.assertTrue(seal.is_file())
            self.assertTrue(runtime_parent.is_dir())

            reopened = project_runtime.load_runtime_candidate_cleanup_capsule(
                project,
                candidate.transaction_root,
            )
            resumed = project_runtime.resume_runtime_candidate_cleanup(reopened)
            self.assertIsInstance(
                resumed,
                project_runtime.RuntimeCandidateCleanupCapsule,
            )
            self.assertFalse(candidate.candidate_root.exists())
            self.assertFalse(quarantine.exists())
            self.assertFalse(seal.exists())
            self.assertTrue(capsule_path.is_file())

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_capsule_guard_failure_has_no_candidate_side_effect(
        self,
    ) -> None:
        from wom_kit import project_update_transaction

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenarios = ("enter-unavailable", "revalidate-unavailable")
            for scenario in scenarios:
                with self.subTest(scenario=scenario):
                    project = root / scenario
                    project.mkdir()
                    candidate, quarantine, seal, runtime_parent = (
                        self._small_quarantined_candidate(
                            project,
                            f"cleanup-guard-{scenario}",
                            create_capsule=False,
                            move_to_quarantine=False,
                        )
                    )
                    capsule_path = (
                        project_runtime
                        ._runtime_candidate_cleanup_capsule_path(
                            candidate.transaction_root
                        )
                    )
                    before_inventory = (
                        project_runtime._candidate_inventory_snapshot(
                            candidate.candidate_root
                        )
                    )

                    @contextmanager
                    def unavailable_guard(
                        _project: Path,
                        _transaction_ref: str,
                    ) -> Any:
                        if scenario == "enter-unavailable":
                            raise (
                                project_update_transaction
                                .ProjectUpdateTransactionError(
                                    "project_update_transaction_"
                                    "checkpoint_write_failed"
                                )
                            )

                        def revalidate() -> None:
                            raise (
                                project_update_transaction
                                .ProjectUpdateTransactionError(
                                    "project_update_transaction_"
                                    "checkpoint_write_failed"
                                )
                            )

                        yield revalidate

                    with patch.object(
                        project_update_transaction,
                        "runtime_cleanup_sidecar_creation_guard",
                        side_effect=unavailable_guard,
                    ):
                        self.assertIsNone(
                            project_runtime
                            ._create_runtime_candidate_cleanup_capsule(
                                candidate
                            )
                        )

                    self.assertFalse(capsule_path.exists())
                    self.assertTrue(candidate.candidate_root.is_dir())
                    self.assertFalse(quarantine.exists())
                    self.assertTrue(seal.is_file())
                    self.assertTrue(runtime_parent.is_dir())
                    self.assertEqual(
                        project_runtime._candidate_inventory_snapshot(
                            candidate.candidate_root
                        ),
                        before_inventory,
                    )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_capsule_creator_and_empty_abort_are_serialized(
        self,
    ) -> None:
        from wom_kit import project_update_transaction

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Creator wins: abort cannot pass the same append.guard while
            # runtime is between namespace observation and O_EXCL publish.
            creator_project = root / "creator-wins"
            creator_project.mkdir()
            creator_ref = "update_11111111111111111111111111111111"
            reserved, lock_bytes, candidate = self._reserved_small_candidate(
                creator_project,
                creator_ref,
            )
            entered = threading.Event()
            release = threading.Event()
            creator_result: list[
                project_runtime.RuntimeCandidateCleanupCapsule | None
            ] = []
            creator_errors: list[BaseException] = []
            original_observation = (
                project_runtime
                ._runtime_cleanup_creation_observation_guard_held
            )

            def pause_inside_guard(
                observed_candidate: project_runtime.PreparedRuntimeCandidate,
                *,
                capsule_present: bool,
            ) -> tuple[tuple[int, int], tuple[int, int], int, int] | None:
                result = original_observation(
                    observed_candidate,
                    capsule_present=capsule_present,
                )
                if not capsule_present and result is not None:
                    entered.set()
                    if not release.wait(timeout=10):
                        raise RuntimeError("synthetic_guard_release_timeout")
                return result

            def create_capsule() -> None:
                try:
                    creator_result.append(
                        project_runtime
                        ._create_runtime_candidate_cleanup_capsule(candidate)
                    )
                except BaseException as error:  # pragma: no cover - evidence
                    creator_errors.append(error)

            with patch.object(
                project_runtime,
                "_runtime_cleanup_creation_observation_guard_held",
                side_effect=pause_inside_guard,
            ):
                creator = threading.Thread(target=create_capsule)
                creator.start()
                self.assertTrue(entered.wait(timeout=10))
                with self.assertRaises(
                    project_update_transaction.ProjectUpdateTransactionError
                ) as caught:
                    reserved.abort_before_intent_seal(
                        expected_lock_bytes=lock_bytes,
                    )
                self.assertEqual(
                    caught.exception.code,
                    "project_update_transaction_checkpoint_write_failed",
                )
                release.set()
                creator.join(timeout=10)
            self.assertFalse(creator.is_alive())
            self.assertEqual(creator_errors, [])
            self.assertEqual(len(creator_result), 1)
            self.assertIsInstance(
                creator_result[0],
                project_runtime.RuntimeCandidateCleanupCapsule,
            )
            self.assertFalse(
                (
                    candidate.transaction_root
                    / project_update_transaction.RESERVATION_ABORT_INTENT_NAME
                ).exists()
            )
            self.assertFalse(
                (
                    candidate.transaction_root
                    / project_update_transaction.RESERVATION_ABORT_RECEIPT_NAME
                ).exists()
            )

            # Abort wins: once a genuinely empty reservation has a durable
            # abort receipt, a stale candidate object cannot publish a sidecar.
            abort_project = root / "abort-wins"
            abort_project.mkdir()
            abort_ref = "update_22222222222222222222222222222222"
            aborted, aborted_lock, stale_candidate = (
                self._reserved_small_candidate(abort_project, abort_ref)
            )
            preserved_candidate = root / "preserved-candidate"
            project_runtime._atomic_promote_directory_no_replace(
                stale_candidate.candidate_root,
                preserved_candidate,
            )
            preserved_inventory = (
                project_runtime._candidate_inventory_snapshot(
                    preserved_candidate
                )
            )
            stale_candidate.seal_path.unlink()
            project_runtime._flush_directory_durable(
                stale_candidate.transaction_root
            )
            abort_receipt = aborted.abort_before_intent_seal(
                expected_lock_bytes=aborted_lock,
            )
            self.assertEqual(
                abort_receipt["state"],
                "aborted_before_intent_seal",
            )
            self.assertIsNone(
                project_runtime._create_runtime_candidate_cleanup_capsule(
                    stale_candidate
                )
            )
            self.assertFalse(
                project_runtime._runtime_candidate_cleanup_capsule_path(
                    stale_candidate.transaction_root
                ).exists()
            )
            self.assertEqual(
                project_runtime._candidate_inventory_snapshot(
                    preserved_candidate
                ),
                preserved_inventory,
            )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_capsule_hard_exit_releases_guard_and_preserves_sidecar(
        self,
    ) -> None:
        from wom_kit import project_update_transaction

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            transaction_ref = "update_33333333333333333333333333333333"
            environment = dict(os.environ)
            environment.update(
                {
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": os.pathsep.join(
                        (str(SRC_ROOT), str(TESTS_ROOT))
                    ),
                    "PYTHONUTF8": "1",
                }
            )
            worker = "\n".join(
                (
                    "import os",
                    "import sys",
                    "from pathlib import Path",
                    "from unittest.mock import patch",
                    "from test_project_runtime_candidate import "
                    "CompleteRuntimeCandidateTests",
                    "from wom_kit import project_runtime",
                    "project = Path(sys.argv[1])",
                    "project.mkdir()",
                    "fixture = CompleteRuntimeCandidateTests()",
                    "candidate, _, _, _ = fixture."
                    "_small_quarantined_candidate("
                    "project, sys.argv[2], create_capsule=False, "
                    "move_to_quarantine=False)",
                    "with patch.object("
                    "project_runtime, "
                    "'_runtime_candidate_cleanup_capsule_bytes', "
                    "side_effect=lambda *args, **kwargs: os._exit(73)):",
                    "    project_runtime."
                    "_create_runtime_candidate_cleanup_capsule(candidate)",
                    "raise SystemExit(74)",
                )
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    worker,
                    str(project),
                    transaction_ref,
                ],
                cwd=str(KIT_ROOT),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                creationflags=project_runtime.noninteractive_creationflags(),
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                73,
                completed.stderr.decode("utf-8", errors="replace"),
            )
            transaction = (
                project
                / project_runtime.PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
                / transaction_ref
            )
            capsule_path = (
                project_runtime._runtime_candidate_cleanup_capsule_path(
                    transaction
                )
            )
            self.assertTrue(capsule_path.is_file())
            self.assertEqual(capsule_path.read_bytes(), b"")
            self.assertTrue(
                (transaction / project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME)
                .is_dir()
            )
            self.assertTrue(
                (
                    transaction
                    / project_runtime.PROJECT_RUNTIME_CANDIDATE_SEAL_NAME
                ).is_file()
            )
            inventory = (
                project_runtime.runtime_candidate_cleanup_sidecar_inventory(
                    project
                )
            )
            self.assertEqual(
                inventory["review_required_transaction_refs"],
                (transaction_ref,),
            )
            with (
                project_update_transaction
                .runtime_cleanup_sidecar_creation_guard(
                    project,
                    transaction_ref,
                ) as revalidate
            ):
                revalidate()

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_sidecar_inventory_discovers_recoverable_and_orphaned(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            recoverable_project = root / "recoverable-project"
            recoverable_project.mkdir()
            recoverable, _quarantine, _seal, _runtime_parent = (
                self._small_quarantined_candidate(
                    recoverable_project,
                    "txn-cleanup-discovery",
                )
            )
            recoverable_capsule = (
                project_runtime._runtime_candidate_cleanup_capsule_path(
                    recoverable.transaction_root
                )
            )
            self.assertEqual(
                recoverable_capsule.parent,
                recoverable.transaction_root.parent,
            )
            self.assertNotIn(
                recoverable.transaction_root,
                recoverable_capsule.parents,
            )
            recoverable_inventory = (
                project_runtime.runtime_candidate_cleanup_sidecar_inventory(
                    recoverable_project
                )
            )
            self.assertEqual(recoverable_inventory["state"], "passed")
            self.assertEqual(
                recoverable_inventory["recoverable_transaction_refs"],
                (recoverable.transaction_ref,),
            )
            self.assertEqual(
                recoverable_inventory["orphaned_transaction_refs"],
                (),
            )
            self.assertFalse(
                recoverable_inventory["automatic_orphan_deletion_allowed"]
            )

            orphan_project = root / "orphan-project"
            orphan_project.mkdir()
            orphan, _quarantine, _seal, _runtime_parent = (
                self._small_quarantined_candidate(
                    orphan_project,
                    "txn-cleanup-orphan",
                )
            )
            orphan_capsule = (
                project_runtime._runtime_candidate_cleanup_capsule_path(
                    orphan.transaction_root
                )
            )
            detached_transaction = root / "preserved-orphan-transaction"
            orphan.transaction_root.rename(detached_transaction)
            orphan_inventory = (
                project_runtime.runtime_candidate_cleanup_sidecar_inventory(
                    orphan_project
                )
            )
            self.assertEqual(orphan_inventory["state"], "passed")
            self.assertEqual(
                orphan_inventory["orphaned_transaction_refs"],
                (orphan.transaction_ref,),
            )
            self.assertEqual(
                orphan_inventory["recoverable_transaction_refs"],
                (),
            )
            self.assertTrue(orphan_capsule.is_file())
            self.assertTrue(detached_transaction.is_dir())
            rendered = json.dumps(orphan_inventory, sort_keys=True)
            self.assertNotIn(str(root), rendered)
            self.assertNotIn(str(orphan_project), rendered)

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_sidecar_inventory_preserves_invalid_entries_for_review(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            candidate, quarantine, seal, _runtime_parent = (
                self._small_quarantined_candidate(
                    project,
                    "txn-cleanup-inventory-review",
                )
            )
            capsule_path = (
                project_runtime._runtime_candidate_cleanup_capsule_path(
                    candidate.transaction_root
                )
            )
            document = json.loads(capsule_path.read_text(encoding="utf-8"))
            document["inventory"][0]["relative_path"] = "."
            capsule_path.write_text(
                json.dumps(
                    document,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            unattributed = (
                candidate.transaction_root.parent
                / ".runtime-candidate-cleanup_-.json"
            )
            unattributed.write_bytes(b"preserve")
            inventory = (
                project_runtime.runtime_candidate_cleanup_sidecar_inventory(
                    project
                )
            )
            self.assertEqual(inventory["state"], "passed")
            self.assertEqual(
                inventory["review_required_transaction_refs"],
                (candidate.transaction_ref,),
            )
            self.assertEqual(inventory["unattributed_sidecar_count"], 1)
            self.assertEqual(inventory["sidecar_count"], 2)
            self.assertTrue(capsule_path.is_file())
            self.assertTrue(unattributed.is_file())
            self.assertTrue(quarantine.is_dir())
            self.assertTrue(seal.is_file())

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_sidecar_permission_failure_is_not_reported_as_absent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            candidate, quarantine, seal, _runtime_parent = (
                self._small_quarantined_candidate(
                    project,
                    "txn-cleanup-inventory-unavailable",
                )
            )
            capsule_path = (
                project_runtime._runtime_candidate_cleanup_capsule_path(
                    candidate.transaction_root
                )
            )
            with patch.object(
                project_runtime,
                "_file_link_count",
                side_effect=PermissionError(
                    13,
                    "raw-private-error-marker",
                    str(capsule_path),
                ),
            ):
                inventory = (
                    project_runtime
                    .runtime_candidate_cleanup_sidecar_inventory(project)
                )
            self.assertEqual(inventory["state"], "unavailable")
            self.assertEqual(
                inventory["unavailable_transaction_refs"],
                (candidate.transaction_ref,),
            )
            self.assertEqual(
                inventory["orphaned_transaction_refs"],
                (),
            )
            self.assertTrue(capsule_path.is_file())
            self.assertTrue(quarantine.is_dir())
            self.assertTrue(seal.is_file())
            rendered = json.dumps(inventory, sort_keys=True)
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("raw-private-error-marker", rendered)

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_sidecar_parent_identity_drift_is_preserved(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            candidate, quarantine, seal, runtime_parent = (
                self._small_quarantined_candidate(
                    project,
                    "txn-cleanup-sidecar-parent-drift",
                    create_capsule=False,
                    move_to_quarantine=False,
                )
            )
            sidecar_parent = candidate.transaction_root.parent
            capsule_path = (
                project_runtime._runtime_candidate_cleanup_capsule_path(
                    candidate.transaction_root
                )
            )
            preserved_parent = root / "preserved-version-updates"
            original_flush = project_runtime._flush_directory_durable
            replaced = False
            rename_blocked = False

            def replace_parent_before_barrier(path: Path) -> None:
                nonlocal rename_blocked, replaced
                if (
                    not replaced
                    and path == sidecar_parent
                    and capsule_path.is_file()
                ):
                    try:
                        sidecar_parent.rename(preserved_parent)
                    except OSError:
                        # The retained append.guard is allowed to make the
                        # attempted parent replacement impossible on Windows.
                        # Stop at the same barrier so the published sidecar is
                        # preserved and no candidate cleanup can begin.
                        rename_blocked = True
                        raise project_runtime.ProjectRuntimeError(
                            "project_runtime_cleanup_capsule_invalid"
                        ) from None
                    sidecar_parent.mkdir(parents=True)
                    replaced = True
                original_flush(path)

            with patch.object(
                project_runtime,
                "_flush_directory_durable",
                side_effect=replace_parent_before_barrier,
            ):
                self.assertIsNone(
                    project_runtime._create_runtime_candidate_cleanup_capsule(
                        candidate
                    )
                )
            preserved_transaction = (
                preserved_parent / candidate.transaction_ref
            )
            self.assertNotEqual(replaced, rename_blocked)
            observed_parent = preserved_parent if replaced else sidecar_parent
            observed_transaction = (
                preserved_transaction
                if replaced
                else candidate.transaction_root
            )
            self.assertTrue((observed_parent / capsule_path.name).is_file())
            self.assertTrue(
                (
                    observed_transaction
                    / project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME
                ).is_dir()
            )
            self.assertTrue(
                (
                    observed_transaction
                    / project_runtime.PROJECT_RUNTIME_CANDIDATE_SEAL_NAME
                ).is_file()
            )
            self.assertFalse(quarantine.exists())
            self.assertEqual(seal.exists(), not replaced)
            self.assertTrue(runtime_parent.is_dir())
            self.assertEqual(
                project_runtime.runtime_candidate_cleanup_sidecar_inventory(
                    project
                )["sidecar_count"],
                0 if replaced else 1,
            )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_capsule_tamper_and_cross_ref_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            for scenario in ("tamper", "wrong-ref", "wrong-project", "hardlink"):
                with self.subTest(scenario=scenario):
                    project = root / f"project-{scenario}"
                    project.mkdir()
                    candidate, quarantine, seal, _runtime_parent = (
                        self._small_quarantined_candidate(
                            project,
                            f"txn-cleanup-{scenario}",
                        )
                    )
                    capsule_path = (
                        project_runtime._runtime_candidate_cleanup_capsule_path(
                            candidate.transaction_root
                        )
                    )
                    if scenario == "tamper":
                        document = json.loads(
                            capsule_path.read_text(encoding="utf-8")
                        )
                        document["quarantine_locator"] = "../outside"
                        capsule_path.write_text(
                            json.dumps(
                                document,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n",
                            encoding="utf-8",
                        )
                        load_project = project
                        load_transaction = candidate.transaction_root
                    elif scenario == "wrong-ref":
                        load_project = project
                        load_transaction = (
                            project
                            / project_runtime.PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
                            / "different-transaction-ref"
                        )
                        load_transaction.mkdir()
                        shutil.copyfile(
                            capsule_path,
                            project_runtime._runtime_candidate_cleanup_capsule_path(
                                load_transaction
                            ),
                        )
                    elif scenario == "wrong-project":
                        load_project = root / "different-project"
                        load_project.mkdir()
                        load_transaction = (
                            load_project
                            / project_runtime.PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
                            / candidate.transaction_ref
                        )
                        load_transaction.mkdir(parents=True)
                        shutil.copyfile(
                            capsule_path,
                            project_runtime._runtime_candidate_cleanup_capsule_path(
                                load_transaction
                            ),
                        )
                    else:
                        outside_link = root / "cleanup-capsule-hardlink"
                        os.link(capsule_path, outside_link)
                        load_project = project
                        load_transaction = candidate.transaction_root

                    with self.assertRaises(
                        project_runtime.ProjectRuntimeError
                    ) as caught:
                        project_runtime.load_runtime_candidate_cleanup_capsule(
                            load_project,
                            load_transaction,
                        )
                    self.assertNotIn(str(root), str(caught.exception))
                    self.assertTrue(quarantine.is_dir())
                    self.assertTrue(seal.is_file())
                    if scenario == "hardlink":
                        outside_link.unlink()

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_capsule_cross_binds_every_surviving_seal_fact(
        self,
    ) -> None:
        scenarios = (
            "capsule-target-tag-version",
            "target-tag",
            "target-commit",
            "transaction-ref",
            "candidate-locator",
            "inventory-sha256",
            "inventory-count",
            "inventory-bytes",
            "candidate-sha256",
            "project-root-identity",
            "transaction-root-identity",
            "candidate-root-identity",
            "runtime-parent-identity",
            "runtime-parent-created-identity",
            "existing-runtime-root-identity",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for scenario in scenarios:
                with self.subTest(scenario=scenario):
                    project = root / f"project-{scenario}"
                    project.mkdir()
                    candidate, quarantine, seal, _runtime_parent = (
                        self._small_quarantined_candidate(
                            project,
                            f"txn-cross-bind-{scenario}",
                        )
                    )
                    capsule_path = (
                        project_runtime
                        ._runtime_candidate_cleanup_capsule_path(
                            candidate.transaction_root
                        )
                    )
                    seal_document = json.loads(
                        seal.read_text(encoding="utf-8")
                    )
                    capsule_document = json.loads(
                        capsule_path.read_text(encoding="utf-8")
                    )
                    if scenario == "capsule-target-tag-version":
                        capsule_document["target_tag"] = "v0.4.20"
                        capsule_document["target_version"] = "0.4.20"
                    elif scenario == "target-tag":
                        seal_document["target_tag"] = "v0.4.20"
                    elif scenario == "target-commit":
                        seal_document["target_commit"] = "c" * 40
                    elif scenario == "transaction-ref":
                        seal_document["transaction_ref"] = "txn-other-ref"
                    elif scenario == "candidate-locator":
                        seal_document["candidate_locator"] = (
                            seal_document["candidate_locator"] + "-other"
                        )
                    elif scenario == "inventory-sha256":
                        seal_document["inventory_sha256"] = (
                            "sha256:" + "4" * 64
                        )
                    elif scenario == "inventory-count":
                        seal_document["inventory_count"] += 1
                    elif scenario == "inventory-bytes":
                        seal_document["inventory_bytes"] += 1
                    elif scenario == "candidate-sha256":
                        seal_document["candidate_sha256"] = (
                            "sha256:" + "5" * 64
                        )
                    else:
                        identity_key = {
                            "project-root-identity": "project_root",
                            "transaction-root-identity": "transaction_root",
                            "candidate-root-identity": "candidate_root",
                            "runtime-parent-identity": "runtime_parent",
                            "runtime-parent-created-identity": (
                                "runtime_parent_created"
                            ),
                            "existing-runtime-root-identity": (
                                "existing_runtime_root"
                            ),
                        }[scenario]
                        if identity_key == "existing_runtime_root":
                            seal_document["path_identities"][identity_key] = (
                                list(candidate.candidate_root_identity)
                            )
                        else:
                            changed = list(
                                seal_document["path_identities"][identity_key]
                            )
                            changed[1] += 1
                            seal_document["path_identities"][identity_key] = (
                                changed
                            )

                    if scenario != "capsule-target-tag-version":
                        seal_raw = (
                            json.dumps(
                                seal_document,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode("utf-8")
                        seal.write_bytes(seal_raw)
                        seal_stat = seal.lstat()
                        capsule_document["seal_mtime_ns"] = int(
                            seal_stat.st_mtime_ns
                        )
                        capsule_document["seal_size_bytes"] = len(seal_raw)
                        capsule_document["seal_sha256"] = (
                            "sha256:"
                            + hashlib.sha256(seal_raw).hexdigest()
                        )
                    capsule_raw = (
                        json.dumps(
                            capsule_document,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                    capsule_path.write_bytes(capsule_raw)

                    with self.assertRaises(
                        project_runtime.ProjectRuntimeError
                    ) as caught:
                        project_runtime.load_runtime_candidate_cleanup_capsule(
                            project,
                            candidate.transaction_root,
                        )
                    self.assertNotIn(str(root), str(caught.exception))
                    self.assertTrue(capsule_path.is_file())
                    self.assertTrue(quarantine.is_dir())
                    self.assertTrue(seal.is_file())

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_capsule_and_seal_named_streams_block_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for target in ("capsule", "seal"):
                for phase in ("fresh-load", "loaded-then-resume"):
                    with self.subTest(target=target, phase=phase):
                        project = root / f"project-{target}-{phase}"
                        project.mkdir()
                        candidate, quarantine, seal, _runtime_parent = (
                            self._small_quarantined_candidate(
                                project,
                                f"txn-cleanup-ads-{target}-{phase}",
                            )
                        )
                        capsule_path = (
                            project_runtime
                            ._runtime_candidate_cleanup_capsule_path(
                                candidate.transaction_root
                            )
                        )
                        loaded = (
                            project_runtime
                            .load_runtime_candidate_cleanup_capsule(
                                project,
                                candidate.transaction_root,
                            )
                            if phase == "loaded-then-resume"
                            else None
                        )
                        guarded = (
                            capsule_path if target == "capsule" else seal
                        )
                        named_stream = Path(
                            str(guarded) + ":private-evidence"
                        )
                        try:
                            named_stream.write_bytes(b"preserve-stream")
                        except OSError as error:
                            self.skipTest(
                                f"alternate streams unavailable: {error}"
                            )
                        handle = legacy_cleanup_bound_delete._windows_open(
                            guarded,
                            directory=False,
                        )
                        try:
                            streams = (
                                legacy_cleanup_bound_delete
                                ._windows_stream_names(
                                    handle,
                                    directory=False,
                                )
                            )
                        finally:
                            legacy_cleanup_bound_delete._windows_close(handle)
                        self.assertNotEqual(streams, ("::$DATA",))

                        if loaded is None:
                            with self.assertRaises(
                                project_runtime.ProjectRuntimeError
                            ) as caught:
                                project_runtime.load_runtime_candidate_cleanup_capsule(
                                    project,
                                    candidate.transaction_root,
                                )
                            self.assertNotIn(
                                str(root),
                                str(caught.exception),
                            )
                        else:
                            self.assertIsNone(
                                project_runtime.resume_runtime_candidate_cleanup(
                                    loaded
                                )
                            )
                        inventory = (
                            project_runtime
                            .runtime_candidate_cleanup_sidecar_inventory(
                                project
                            )
                        )
                        self.assertEqual(
                            inventory["review_required_transaction_refs"],
                            (candidate.transaction_ref,),
                        )
                        self.assertTrue(capsule_path.is_file())
                        self.assertTrue(quarantine.is_dir())
                        self.assertTrue(seal.is_file())
                        self.assertEqual(
                            named_stream.read_bytes(),
                            b"preserve-stream",
                        )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_capsule_byte_identical_name_replacement_is_preserved(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            candidate, quarantine, seal, _runtime_parent = (
                self._small_quarantined_candidate(
                    project,
                    "txn-cleanup-capsule-replacement",
                )
            )
            capsule_path = (
                project_runtime._runtime_candidate_cleanup_capsule_path(
                    candidate.transaction_root
                )
            )
            loaded = project_runtime.load_runtime_candidate_cleanup_capsule(
                project,
                candidate.transaction_root,
            )
            original = root / "preserved-original-capsule"
            raw = capsule_path.read_bytes()
            capsule_path.rename(original)
            capsule_path.write_bytes(raw)
            self.assertNotEqual(
                project_runtime._path_identity(original),
                project_runtime._path_identity(capsule_path),
            )

            self.assertIsNone(
                project_runtime.resume_runtime_candidate_cleanup(loaded)
            )
            with self.assertRaises(project_runtime.ProjectRuntimeError) as caught:
                project_runtime.load_runtime_candidate_cleanup_capsule(
                    project,
                    candidate.transaction_root,
                )
            self.assertNotIn(str(root), str(caught.exception))
            self.assertEqual(original.read_bytes(), raw)
            self.assertEqual(capsule_path.read_bytes(), raw)
            self.assertTrue(quarantine.is_dir())
            self.assertTrue(seal.is_file())

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_empty_and_partial_cleanup_capsules_are_review_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for state in ("empty-hard-exit", "partial-hard-exit"):
                with self.subTest(state=state):
                    project = root / f"project-{state}"
                    project.mkdir()
                    candidate, quarantine, seal, runtime_parent = (
                        self._small_quarantined_candidate(
                            project,
                            f"txn-cleanup-{state}",
                            create_capsule=False,
                            move_to_quarantine=False,
                        )
                    )
                    capsule_path = (
                        project_runtime
                        ._runtime_candidate_cleanup_capsule_path(
                            candidate.transaction_root
                        )
                    )
                    if state == "empty-hard-exit":
                        with patch.object(
                            project_runtime,
                            "_runtime_candidate_cleanup_capsule_bytes",
                            side_effect=project_runtime.ProjectRuntimeError(
                                "synthetic_hard_exit_after_capsule_open"
                            ),
                        ):
                            self.assertIsNone(
                                project_runtime
                                ._create_runtime_candidate_cleanup_capsule(
                                    candidate
                                )
                            )
                        self.assertEqual(capsule_path.read_bytes(), b"")
                    else:
                        capsule_path.write_bytes(b'{"schema":')
                        self.assertIsNone(
                            project_runtime
                            ._create_runtime_candidate_cleanup_capsule(
                                candidate
                            )
                        )
                    inventory = (
                        project_runtime
                        .runtime_candidate_cleanup_sidecar_inventory(project)
                    )
                    self.assertEqual(inventory["state"], "passed")
                    self.assertEqual(
                        inventory["review_required_transaction_refs"],
                        (candidate.transaction_ref,),
                    )
                    self.assertTrue(capsule_path.is_file())
                    self.assertTrue(candidate.candidate_root.is_dir())
                    self.assertFalse(quarantine.exists())
                    self.assertTrue(seal.is_file())
                    self.assertTrue(runtime_parent.is_dir())

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_missing_seal_is_allowed_only_after_both_cleanup_roots_absent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for topology in ("candidate-present", "quarantine-present"):
                with self.subTest(topology=topology):
                    project = root / f"project-{topology}"
                    project.mkdir()
                    candidate, quarantine, seal, _runtime_parent = (
                        self._small_quarantined_candidate(
                            project,
                            f"txn-cleanup-no-seal-{topology}",
                            move_to_quarantine=(
                                topology == "quarantine-present"
                            ),
                        )
                    )
                    seal.unlink()
                    project_runtime._flush_directory_durable(
                        candidate.transaction_root
                    )
                    with self.assertRaises(
                        project_runtime.ProjectRuntimeError
                    ) as caught:
                        project_runtime.load_runtime_candidate_cleanup_capsule(
                            project,
                            candidate.transaction_root,
                        )
                    self.assertNotIn(str(root), str(caught.exception))
                    self.assertTrue(
                        candidate.candidate_root.is_dir()
                        if topology == "candidate-present"
                        else quarantine.is_dir()
                    )
                    self.assertTrue(
                        project_runtime
                        ._runtime_candidate_cleanup_capsule_path(
                            candidate.transaction_root
                        )
                        .is_file()
                    )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Candidate cleanup retained-handle deletion is Windows-only.",
    )
    def test_cleanup_capsule_blocks_and_preserves_replaced_normal_seal(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            candidate, quarantine, seal, _runtime_parent = (
                self._small_quarantined_candidate(
                    project,
                    "txn-cleanup-seal-replacement",
                )
            )
            original_seal = root / "exact-original-seal"
            seal_bytes = seal.read_bytes()
            loaded = project_runtime.load_runtime_candidate_cleanup_capsule(
                project,
                candidate.transaction_root,
            )
            seal.rename(original_seal)
            seal.write_bytes(seal_bytes)
            self.assertIsNone(
                project_runtime.resume_runtime_candidate_cleanup(loaded)
            )
            with self.assertRaises(project_runtime.ProjectRuntimeError) as caught:
                project_runtime.load_runtime_candidate_cleanup_capsule(
                    project,
                    candidate.transaction_root,
                )
            self.assertNotIn(str(root), str(caught.exception))
            self.assertTrue(quarantine.is_dir())
            self.assertEqual(original_seal.read_bytes(), seal_bytes)
            self.assertEqual(seal.read_bytes(), seal_bytes)
            self.assertTrue(
                project_runtime._runtime_candidate_cleanup_capsule_path(
                    candidate.transaction_root
                ).is_file()
            )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Complete project runtime candidates are CPython 3.12 Windows AMD64.",
    )
    def test_existing_runtime_observation_keeps_drift_and_io_distinct(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            baseline, bootstrap, supply = self._prepare(
                root,
                project,
                "txn-observation-baseline",
            )
            self.assertFalse(baseline.existing_runtime_reusable)
            self.assertFalse(baseline.existing_runtime_repair_required)
            absent_state, _absent_reason, absent_summary = (
                project_runtime.verify_prepared_runtime_candidate_observation(
                    baseline,
                    project_root=project,
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                )
            )
            self.assertEqual(absent_state, "passed")
            self.assertIsNotNone(absent_summary)
            final = project_runtime.runtime_path(project, "v0.4.3")
            original_presence = project_runtime._runtime_path_presence_observation

            def unavailable_target_presence(path: Path):
                if path == final:
                    return {"state": "unavailable", "present": None}
                return original_presence(path)

            with patch.object(
                project_runtime,
                "_runtime_path_presence_observation",
                side_effect=unavailable_target_presence,
            ):
                target_state, _target_reason, target_summary = (
                    project_runtime
                    .verify_prepared_runtime_candidate_observation(
                        baseline,
                        project_root=project,
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=bootstrap,
                        supply=supply,
                    )
                )
            self.assertEqual(target_state, "unavailable")
            self.assertIsNone(target_summary)
            project_runtime.promote_runtime_candidate(
                project,
                target="v0.4.3",
                target_commit="b" * 40,
                bootstrap=bootstrap,
                supply=supply,
                prepared_candidate=baseline,
            )
            self.assertTrue(
                project_runtime.cleanup_prepared_runtime_candidate(baseline)
            )
            candidate, candidate_bootstrap, candidate_supply = self._prepare(
                root,
                project,
                "txn-observation-reuse",
            )
            self.assertTrue(candidate.existing_runtime_reusable)
            normal = project_runtime._existing_runtime_candidate_observation(
                project,
                candidate,
            )
            self.assertEqual(normal["state"], "passed")
            self.assertTrue(normal["matches"])

            payload = (
                final
                / "Lib"
                / "site-packages"
                / "wom_kit"
                / "archive_cli.py"
            )
            original_bytes = payload.read_bytes()
            payload.write_bytes(original_bytes + b"\n# confirmed tamper\n")
            tampered = (
                project_runtime._existing_runtime_candidate_observation(
                    project,
                    candidate,
                )
            )
            self.assertEqual(tampered["state"], "failed")
            self.assertFalse(tampered["matches"])
            tamper_state, _tamper_reason, tamper_summary = (
                project_runtime.verify_prepared_runtime_candidate_observation(
                    candidate,
                    project_root=project,
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=candidate_bootstrap,
                    supply=candidate_supply,
                )
            )
            self.assertEqual(tamper_state, "failed")
            self.assertIsNone(tamper_summary)
            payload.write_bytes(original_bytes)

            original_lstat = Path.lstat

            def unavailable_final_lstat(
                path: Path,
                *args: Any,
                **kwargs: Any,
            ):
                if path == final:
                    raise PermissionError("synthetic runtime access failure")
                return original_lstat(path, *args, **kwargs)

            with patch.object(Path, "lstat", unavailable_final_lstat):
                unavailable = (
                    project_runtime._existing_runtime_candidate_observation(
                        project,
                        candidate,
                    )
                )
                unavailable_state, _reason, unavailable_summary = (
                    project_runtime
                    .verify_prepared_runtime_candidate_observation(
                        candidate,
                        project_root=project,
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=candidate_bootstrap,
                        supply=candidate_supply,
                    )
                )
            self.assertEqual(unavailable["state"], "unavailable")
            self.assertEqual(unavailable_state, "unavailable")
            self.assertIsNone(unavailable_summary)

            receipt_path = final / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
            original_read_limited = project_runtime._read_limited

            def unavailable_receipt_read(
                path: Path,
                *args: Any,
                **kwargs: Any,
            ):
                if path == receipt_path:
                    raise PermissionError("synthetic runtime read failure")
                return original_read_limited(path, *args, **kwargs)

            with patch.object(
                project_runtime,
                "_read_limited",
                side_effect=unavailable_receipt_read,
            ):
                read_unavailable = (
                    project_runtime._existing_runtime_candidate_observation(
                        project,
                        candidate,
                    )
                )
            self.assertEqual(read_unavailable["state"], "unavailable")
            self.assertTrue(
                project_runtime.cleanup_prepared_runtime_candidate(candidate)
            )

            corrupt_bytes = original_bytes + b"\n# repair preimage\n"
            payload.write_bytes(corrupt_bytes)
            repair_candidate, repair_bootstrap, repair_supply = self._prepare(
                root,
                project,
                "txn-observation-repair",
            )
            self.assertTrue(
                repair_candidate.existing_runtime_repair_required
            )
            repair_normal = project_runtime.runtime_repair_state_observation(
                repair_candidate
            )
            self.assertEqual(repair_normal["state"], "passed")
            self.assertEqual(
                repair_normal["repair_state"],
                "preimage_final",
            )
            repair_state, _repair_reason, repair_summary = (
                project_runtime.verify_prepared_runtime_candidate_observation(
                    repair_candidate,
                    project_root=project,
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=repair_bootstrap,
                    supply=repair_supply,
                )
            )
            self.assertEqual(repair_state, "passed")
            self.assertIsNotNone(repair_summary)

            repair_preimage_stat = payload.stat()
            payload.write_bytes(corrupt_bytes + b"# later tamper\n")
            repair_tampered = (
                project_runtime.runtime_repair_state_observation(
                    repair_candidate
                )
            )
            self.assertEqual(repair_tampered["state"], "failed")
            tampered_state, _reason, tampered_summary = (
                project_runtime.verify_prepared_runtime_candidate_observation(
                    repair_candidate,
                    project_root=project,
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=repair_bootstrap,
                    supply=repair_supply,
                )
            )
            self.assertEqual(tampered_state, "failed")
            self.assertIsNone(tampered_summary)
            payload.write_bytes(corrupt_bytes)
            os.utime(
                payload,
                ns=(
                    repair_preimage_stat.st_atime_ns,
                    repair_preimage_stat.st_mtime_ns,
                ),
            )

            with patch.object(Path, "lstat", unavailable_final_lstat):
                repair_unavailable = (
                    project_runtime.runtime_repair_state_observation(
                        repair_candidate
                    )
                )
                repair_unavailable_state, _reason, unavailable_summary = (
                    project_runtime
                    .verify_prepared_runtime_candidate_observation(
                        repair_candidate,
                        project_root=project,
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=repair_bootstrap,
                        supply=repair_supply,
                    )
                )
            self.assertEqual(repair_unavailable["state"], "unavailable")
            self.assertEqual(repair_unavailable_state, "unavailable")
            self.assertIsNone(unavailable_summary)
            self.assertTrue(
                project_runtime.cleanup_prepared_runtime_candidate(
                    repair_candidate
                )
            )

    def test_runtime_observation_error_classifier_keeps_confirmed_drift(self) -> None:
        self.assertFalse(
            project_runtime._runtime_error_is_observation_unavailable(
                project_runtime.ProjectRuntimeError(
                    "project_runtime_tree_changed"
                )
            )
        )
        self.assertTrue(
            project_runtime._runtime_error_is_observation_unavailable(
                project_runtime.ProjectRuntimeError(
                    "project_runtime_file_unreadable_or_changed"
                )
            )
        )

    def test_runtime_candidate_observation_redacts_raw_io_errors(self) -> None:
        private_path = r"C:\Users\example\runtime\payload.py"
        with patch.object(
            project_runtime,
            "verify_prepared_runtime_candidate",
            side_effect=PermissionError(private_path),
        ):
            state, reason_code, summary = (
                project_runtime.verify_prepared_runtime_candidate_observation(
                    object(),
                    project_root=Path("."),
                    target="v0.4.19",
                    target_commit="b" * 40,
                    bootstrap=object(),
                    supply=object(),
                )
            )
        self.assertEqual(state, "unavailable")
        self.assertEqual(
            reason_code,
            "project_runtime_candidate_observation_unavailable",
        )
        self.assertIsNone(summary)
        self.assertNotIn(private_path, reason_code)

        with patch.object(
            project_runtime,
            "verify_prepared_runtime_candidate",
            side_effect=project_runtime.ProjectRuntimeError(
                "project_runtime_candidate_concurrent_drift"
            ),
        ):
            drift_state, drift_reason, drift_summary = (
                project_runtime.verify_prepared_runtime_candidate_observation(
                    object(),
                    project_root=Path("."),
                    target="v0.4.19",
                    target_commit="b" * 40,
                    bootstrap=object(),
                    supply=object(),
                )
            )
        self.assertEqual(drift_state, "failed")
        self.assertEqual(
            drift_reason,
            "project_runtime_candidate_concurrent_drift",
        )
        self.assertIsNone(drift_summary)

    def test_candidate_inventory_io_faults_use_content_free_code(self) -> None:
        private_path = r"C:\Users\example\runtime\payload.py"

        def assert_content_free_unavailable(error: BaseException) -> None:
            self.assertEqual(
                str(error),
                "project_runtime_candidate_unreadable",
            )
            self.assertNotIn(private_path, str(error))
            self.assertTrue(
                project_runtime._runtime_error_is_observation_unavailable(error)
            )

        with self.subTest(fault="hash"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "candidate"
                root.mkdir()
                (root / "payload.py").write_bytes(b"payload")
                with patch.object(
                    project_runtime,
                    "_sha256_file",
                    side_effect=PermissionError(private_path),
                ):
                    with self.assertRaises(
                        project_runtime.ProjectRuntimeError
                    ) as raised:
                        project_runtime._candidate_inventory_snapshot(root)
                assert_content_free_unavailable(raised.exception)

        with self.subTest(fault="link_count"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "candidate"
                root.mkdir()
                (root / "payload.py").write_bytes(b"payload")
                with patch.object(
                    project_runtime,
                    "_file_link_count",
                    side_effect=PermissionError(private_path),
                ):
                    with self.assertRaises(
                        project_runtime.ProjectRuntimeError
                    ) as raised:
                        project_runtime._candidate_inventory_snapshot(root)
                assert_content_free_unavailable(raised.exception)

        with self.subTest(fault="post_hash_lstat"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "candidate"
                root.mkdir()
                payload = root / "payload.py"
                payload.write_bytes(b"payload")
                original_hash = project_runtime._sha256_file
                original_lstat = Path.lstat
                post_hash = False

                def hash_then_arm(*args: Any, **kwargs: Any):
                    nonlocal post_hash
                    result = original_hash(*args, **kwargs)
                    post_hash = True
                    return result

                def unavailable_post_hash_lstat(
                    path: Path,
                    *args: Any,
                    **kwargs: Any,
                ):
                    if path == payload and post_hash:
                        raise PermissionError(private_path)
                    return original_lstat(path, *args, **kwargs)

                with (
                    patch.object(
                        project_runtime,
                        "_sha256_file",
                        side_effect=hash_then_arm,
                    ),
                    patch.object(Path, "lstat", unavailable_post_hash_lstat),
                ):
                    with self.assertRaises(
                        project_runtime.ProjectRuntimeError
                    ) as raised:
                        project_runtime._candidate_inventory_snapshot(root)
                assert_content_free_unavailable(raised.exception)

    def test_candidate_inventory_confirmed_post_hash_drift_stays_failed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "candidate"
            root.mkdir()
            payload = root / "payload.py"
            payload.write_bytes(b"payload")
            original_hash = project_runtime._sha256_file

            def hash_then_mutate(path: Path, **kwargs: Any):
                result = original_hash(path, **kwargs)
                path.write_bytes(path.read_bytes() + b"-changed")
                return result

            with patch.object(
                project_runtime,
                "_sha256_file",
                side_effect=hash_then_mutate,
            ):
                with self.assertRaisesRegex(
                    project_runtime.ProjectRuntimeError,
                    "^project_runtime_candidate_concurrent_drift$",
                ) as raised:
                    project_runtime._candidate_inventory_snapshot(root)
            self.assertFalse(
                project_runtime._runtime_error_is_observation_unavailable(
                    raised.exception
                )
            )

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
                ".zettel-kasten/private/version-updates/"
                f"{candidate.transaction_ref}/runtime-candidate",
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
            drift_state, drift_reason, drift_summary = (
                project_runtime.verify_prepared_runtime_candidate_observation(
                    candidate,
                    project_root=project,
                    target="v0.4.3",
                    target_commit="b" * 40,
                    bootstrap=bootstrap,
                    supply=supply,
                )
            )
            self.assertEqual(drift_state, "failed")
            self.assertIn("drift", drift_reason)
            self.assertIsNone(drift_summary)
            self.assertFalse(project_runtime.cleanup_prepared_runtime_candidate(candidate))
            self.assertTrue(candidate.candidate_root.exists())
            deep.write_bytes(before)
            os.utime(
                deep,
                ns=(before_stat.st_atime_ns, before_stat.st_mtime_ns),
            )

            original_lstat = Path.lstat

            def unavailable_seal_lstat(path: Path, *args: Any, **kwargs: Any):
                if path == candidate.seal_path:
                    raise PermissionError("synthetic seal access failure")
                return original_lstat(path, *args, **kwargs)

            with patch.object(Path, "lstat", unavailable_seal_lstat):
                unavailable_state, unavailable_reason, unavailable_summary = (
                    project_runtime
                    .verify_prepared_runtime_candidate_observation(
                        candidate,
                        project_root=project,
                        target="v0.4.3",
                        target_commit="b" * 40,
                        bootstrap=bootstrap,
                        supply=supply,
                    )
                )
            self.assertEqual(unavailable_state, "unavailable")
            self.assertIn("unavailable", unavailable_reason)
            self.assertIsNone(unavailable_summary)

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

            def fail_after_candidate_cleanup_rename(path: Path) -> None:
                if path == candidate.transaction_root and quarantine.is_dir():
                    raise project_runtime.ProjectRuntimeError(
                        "project_runtime_directory_durability_failed"
                    )
                original_directory_barrier(path)

            with patch.object(
                project_runtime,
                "_flush_directory_durable",
                side_effect=fail_after_candidate_cleanup_rename,
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
            with _CandidateReuseObservation() as reuse_observation:
                reused_candidate, reused_bootstrap, reused_supply = self._prepare(
                    root,
                    project,
                    "txn-candidate-002",
                )
            self.assertTrue(
                reused_candidate.existing_runtime_reusable,
                reuse_observation.failure_message(reused_candidate)
                if not reused_candidate.existing_runtime_reusable else None,
            )
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
                with _expect_exact_runtime_fault("project_runtime_repair_promotion_rolled_back"):
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

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Complete project runtime candidates are CPython 3.12 Windows AMD64.",
    )
    def test_runtime_parent_unavailable_blocks_before_candidate_side_effects(
        self,
    ) -> None:
        for failure in (
            PermissionError("private runtime parent"),
            OSError(5, "private runtime parent"),
        ):
            with self.subTest(failure=type(failure).__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                project = root / "project"
                project.mkdir()
                transaction = (
                    project
                    / project_runtime.PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
                    / f"txn-parent-{type(failure).__name__.casefold()}"
                )
                transaction.mkdir(parents=True)
                bootstrap, supply, _sources = self._candidate_inputs(root)
                runtime_parent = (
                    project / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT
                )
                candidate_root = (
                    transaction / project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME
                )
                original_lstat = Path.lstat

                def deny_parent(path: Path, *args: Any, **kwargs: Any):
                    if path == runtime_parent:
                        raise failure
                    return original_lstat(path, *args, **kwargs)

                with patch.object(
                    Path,
                    "lstat",
                    deny_parent,
                ), patch.object(
                    project_runtime,
                    "_download_exact_artifact",
                    side_effect=AssertionError(
                        "network preparation must not start"
                    ),
                ), self.assertRaises(
                    project_runtime.ProjectRuntimeError
                ) as caught:
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
                self.assertEqual(
                    str(caught.exception),
                    "project_runtime_candidate_preimage_observation_unavailable",
                )
                self.assertFalse(os.path.lexists(runtime_parent))
                self.assertFalse(os.path.lexists(candidate_root))

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Complete project runtime candidates are CPython 3.12 Windows AMD64.",
    )
    def test_new_runtime_parent_durability_blocks_before_candidate_side_effects(
        self,
    ) -> None:
        for stage in ("new-directory", "parent-entry"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                project = root / "project"
                project.mkdir()
                transaction = (
                    project
                    / project_runtime.PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
                    / f"txn-parent-durability-{stage}"
                )
                transaction.mkdir(parents=True)
                bootstrap, supply, _sources = self._candidate_inputs(root)
                runtime_parent = (
                    project / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT
                )
                candidate_root = (
                    transaction / project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME
                )
                original_flush = project_runtime._flush_directory_durable
                observed_barriers: list[Path] = []

                def fail_creation_barrier(path: Path) -> None:
                    observed_barriers.append(path)
                    if (
                        stage == "new-directory"
                        and path == runtime_parent
                    ) or (
                        stage == "parent-entry"
                        and path == runtime_parent.parent
                    ):
                        raise project_runtime.ProjectRuntimeError(
                            "synthetic_parent_creation_power_cut"
                        )
                    original_flush(path)

                with patch.object(
                    project_runtime,
                    "_flush_directory_durable",
                    side_effect=fail_creation_barrier,
                ), patch.object(
                    project_runtime,
                    "_download_exact_artifact",
                    side_effect=AssertionError(
                        "candidate download must not start"
                    ),
                ), self.assertRaises(
                    project_runtime.PreparedRuntimeCandidateIncompleteError
                ) as caught:
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
                self.assertEqual(
                    str(caught.exception.__cause__),
                    "project_runtime_parent_creation_durability_failed",
                )
                self.assertEqual(
                    observed_barriers,
                    (
                        [runtime_parent]
                        if stage == "new-directory"
                        else [runtime_parent, runtime_parent.parent]
                    ),
                )
                self.assertTrue(runtime_parent.is_dir())
                self.assertFalse(candidate_root.exists())
                self.assertFalse(
                    (
                        transaction
                        / project_runtime.PROJECT_RUNTIME_CANDIDATE_SEAL_NAME
                    ).exists()
                )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Complete project runtime candidates are CPython 3.12 Windows AMD64.",
    )
    def test_new_runtime_parent_identity_drift_is_preserved_and_blocks(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            transaction = (
                project
                / project_runtime.PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
                / "txn-parent-barrier-drift"
            )
            transaction.mkdir(parents=True)
            bootstrap, supply, _sources = self._candidate_inputs(root)
            runtime_parent = (
                project / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT
            )
            candidate_root = (
                transaction / project_runtime.PROJECT_RUNTIME_CANDIDATE_NAME
            )
            owned_elsewhere = root / "exact-created-runtime-parent"
            original_flush = project_runtime._flush_directory_durable
            replaced = False

            def replace_after_new_directory_barrier(path: Path) -> None:
                nonlocal replaced
                original_flush(path)
                if path == runtime_parent and not replaced:
                    replaced = True
                    runtime_parent.rename(owned_elsewhere)
                    runtime_parent.mkdir()

            with patch.object(
                project_runtime,
                "_flush_directory_durable",
                side_effect=replace_after_new_directory_barrier,
            ), patch.object(
                project_runtime,
                "_download_exact_artifact",
                side_effect=AssertionError("candidate download must not start"),
            ), self.assertRaises(
                project_runtime.PreparedRuntimeCandidateIncompleteError
            ) as caught:
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
            self.assertEqual(
                str(caught.exception.__cause__),
                "project_runtime_parent_identity_drift",
            )
            self.assertTrue(owned_elsewhere.is_dir())
            self.assertTrue(runtime_parent.is_dir())
            self.assertNotEqual(
                project_runtime._path_identity(owned_elsewhere),
                project_runtime._path_identity(runtime_parent),
            )
            self.assertFalse(candidate_root.exists())

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Complete project runtime candidates are CPython 3.12 Windows AMD64.",
    )
    def test_runtime_parent_concurrent_create_is_preserved_and_fixed_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            transaction = (
                project
                / project_runtime.PROJECT_RUNTIME_TRANSACTION_RELATIVE_ROOT
                / "txn-parent-create-race"
            )
            transaction.mkdir(parents=True)
            bootstrap, supply, _sources = self._candidate_inputs(root)
            runtime_parent = (
                project / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT
            )
            original_mkdir = Path.mkdir

            def concurrent_create(path: Path, *args: Any, **kwargs: Any):
                if path == runtime_parent:
                    original_mkdir(path, *args, **kwargs)
                    raise FileExistsError("concurrent runtime parent")
                return original_mkdir(path, *args, **kwargs)

            with patch.object(
                Path,
                "mkdir",
                concurrent_create,
            ), patch.object(
                project_runtime,
                "_download_exact_artifact",
                side_effect=AssertionError("download must not start"),
            ), self.assertRaisesRegex(
                project_runtime.ProjectRuntimeError,
                "project_runtime_parent_concurrent_creation",
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
            self.assertTrue(runtime_parent.is_dir())
            self.assertEqual(tuple(runtime_parent.iterdir()), ())

    def test_runtime_parent_cleanup_requires_exact_created_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            runtime_parent = (
                project / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT
            )
            runtime_parent.mkdir(parents=True)
            original_identity = project_runtime._path_identity(runtime_parent)
            self.assertTrue(
                project_runtime._restore_exact_owned_runtime_parent(
                    project,
                    expected_identity=original_identity,
                    existed_before=True,
                    created_identity=None,
                    promoted_final_present=False,
                )
            )
            self.assertTrue(runtime_parent.is_dir())

            owned_elsewhere = root / "owned-runtime-parent"
            runtime_parent.rename(owned_elsewhere)
            runtime_parent.mkdir()
            replacement_identity = project_runtime._path_identity(
                runtime_parent
            )
            self.assertNotEqual(original_identity, replacement_identity)
            self.assertFalse(
                project_runtime._restore_exact_owned_runtime_parent(
                    project,
                    expected_identity=original_identity,
                    existed_before=False,
                    created_identity=original_identity,
                    promoted_final_present=False,
                )
            )
            self.assertTrue(runtime_parent.is_dir())
            self.assertTrue(owned_elsewhere.is_dir())

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Runtime rollback retained-handle deletion is Windows-only.",
    )
    def test_runtime_rollback_preserves_replacement_before_detach(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            runtime, final, transaction, receipt, _old, _old_id = (
                self._small_materialization(
                    project,
                    "txn-before-detach-race",
                )
            )
            owned_elsewhere = root / "exact-owned-runtime"
            original_move = project_runtime._atomic_promote_directory_no_replace

            def replace_source_before_move(
                source: Path,
                destination: Path,
            ) -> None:
                source.rename(owned_elsewhere)
                source.mkdir()
                (
                    source / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                ).write_bytes(b"foreign-owner")
                original_move(source, destination)

            with patch.object(
                project_runtime,
                "_atomic_promote_directory_no_replace",
                side_effect=replace_source_before_move,
            ):
                self.assertFalse(
                    project_runtime.remove_materialized_runtime(
                        project,
                        runtime,
                    )
                )
            rollback = (
                transaction
                / project_runtime.PROJECT_RUNTIME_ROLLBACK_CANDIDATE_NAME
            )
            self.assertFalse(final.exists())
            self.assertEqual(
                (
                    owned_elsewhere
                    / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                ).read_bytes(),
                receipt,
            )
            self.assertEqual(
                (
                    rollback / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                ).read_bytes(),
                b"foreign-owner",
            )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Runtime rollback retained-handle deletion is Windows-only.",
    )
    def test_runtime_rollback_resumes_after_detach_and_blocks_name_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for scenario in ("resume", "replace"):
                with self.subTest(scenario=scenario):
                    project = root / f"project-{scenario}"
                    project.mkdir()
                    runtime, final, transaction, receipt, _old, _old_id = (
                        self._small_materialization(
                            project,
                            f"txn-after-detach-{scenario}",
                        )
                    )
                    rollback = (
                        transaction
                        / project_runtime.PROJECT_RUNTIME_ROLLBACK_CANDIDATE_NAME
                    )
                    with patch.object(
                        project_runtime,
                        "_flush_directory_durable",
                        side_effect=project_runtime.ProjectRuntimeError(
                            "project_runtime_directory_durability_failed"
                        ),
                    ):
                        self.assertFalse(
                            project_runtime.remove_materialized_runtime(
                                project,
                                runtime,
                            )
                        )
                    self.assertFalse(final.exists())
                    self.assertEqual(
                        (
                            rollback
                            / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                        ).read_bytes(),
                        receipt,
                    )
                    if scenario == "resume":
                        # A reopened process must durably flush the visible
                        # detach before it is allowed to delete the only
                        # private exact image.
                        with patch.object(
                            project_runtime,
                            "_flush_directory_durable",
                            side_effect=project_runtime.ProjectRuntimeError(
                                "project_runtime_directory_durability_failed"
                            ),
                        ):
                            self.assertFalse(
                                project_runtime.remove_materialized_runtime(
                                    project,
                                    runtime,
                                )
                            )
                        self.assertEqual(
                            (
                                rollback
                                / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                            ).read_bytes(),
                            receipt,
                        )
                        self.assertTrue(
                            project_runtime.remove_materialized_runtime(
                                project,
                                runtime,
                            )
                        )
                        self.assertFalse(rollback.exists())
                        self.assertFalse(
                            (
                                project
                                / project_runtime.PROJECT_RUNTIME_RELATIVE_ROOT
                            ).exists()
                        )
                        continue

                    owned_elsewhere = root / "detached-exact-owned-runtime"
                    rollback.rename(owned_elsewhere)
                    rollback.mkdir()
                    (
                        rollback
                        / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                    ).write_bytes(b"foreign-after-detach")
                    self.assertFalse(
                        project_runtime.remove_materialized_runtime(
                            project,
                            runtime,
                        )
                    )
                    self.assertEqual(
                        (
                            owned_elsewhere
                            / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                        ).read_bytes(),
                        receipt,
                    )
                    self.assertEqual(
                        (
                            rollback
                            / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                        ).read_bytes(),
                        b"foreign-after-detach",
                    )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Runtime rollback retained-handle deletion is Windows-only.",
    )
    def test_runtime_rollback_rejects_hardlink_reparse_and_ads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            project = root / "project-hardlink"
            project.mkdir()
            runtime, final, _transaction, receipt, _old, _old_id = (
                self._small_materialization(project, "txn-hardlink")
            )
            receipt_path = final / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
            outside_link = root / "outside-runtime-link"
            os.link(receipt_path, outside_link)
            self.assertFalse(
                project_runtime.remove_materialized_runtime(project, runtime)
            )
            self.assertEqual(receipt_path.read_bytes(), receipt)
            self.assertEqual(outside_link.read_bytes(), receipt)

            project = root / "project-reparse"
            project.mkdir()
            runtime, final, _transaction, receipt, _old, _old_id = (
                self._small_materialization(project, "txn-reparse")
            )
            outside = root / "outside-reparse-target"
            outside.write_bytes(b"outside")
            reparse = final / "unexpected-reparse"
            try:
                reparse.symlink_to(outside)
            except OSError:
                reparse = None
            if reparse is not None:
                self.assertFalse(
                    project_runtime.remove_materialized_runtime(
                        project,
                        runtime,
                    )
                )
                self.assertEqual(
                    (
                        final / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                    ).read_bytes(),
                    receipt,
                )
                self.assertEqual(outside.read_bytes(), b"outside")

            project = root / "project-ads"
            project.mkdir()
            runtime, final, transaction, receipt, _old, _old_id = (
                self._small_materialization(project, "txn-ads")
            )
            receipt_path = final / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
            stream = Path(str(receipt_path) + ":private")
            try:
                stream.write_bytes(b"hidden")
            except OSError as error:
                self.skipTest(f"alternate streams unavailable: {error}")
            self.assertFalse(
                project_runtime.remove_materialized_runtime(project, runtime)
            )
            rollback = (
                transaction
                / project_runtime.PROJECT_RUNTIME_ROLLBACK_CANDIDATE_NAME
            )
            holder = final if final.exists() else rollback
            self.assertEqual(
                (
                    holder / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                ).read_bytes(),
                receipt,
            )
            self.assertEqual(
                Path(
                    str(
                        holder
                        / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                    )
                    + ":private"
                ).read_bytes(),
                b"hidden",
            )

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Runtime rollback retained-handle deletion is Windows-only.",
    )
    def test_runtime_repair_restore_collision_preserves_all_owners(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            runtime, final, transaction, receipt, old_inventory, old_identity = (
                self._small_materialization(
                    project,
                    "txn-repair-restore-collision",
                    repaired=True,
                )
            )
            backup = (
                transaction
                / project_runtime.PROJECT_RUNTIME_REPAIR_BACKUP_NAME
            )
            rollback = (
                transaction
                / project_runtime.PROJECT_RUNTIME_ROLLBACK_CANDIDATE_NAME
            )
            with patch.object(
                project_runtime,
                "_flush_directory_durable",
                side_effect=project_runtime.ProjectRuntimeError(
                    "project_runtime_directory_durability_failed"
                ),
            ):
                self.assertFalse(
                    project_runtime.remove_materialized_runtime(
                        project,
                        runtime,
                    )
                )
            self.assertFalse(final.exists())
            self.assertTrue(backup.is_dir())
            self.assertTrue(rollback.is_dir())

            final.mkdir()
            collision = final / "concurrent-owner.bin"
            collision.write_bytes(b"do-not-overwrite")
            self.assertFalse(
                project_runtime.remove_materialized_runtime(project, runtime)
            )
            self.assertEqual(collision.read_bytes(), b"do-not-overwrite")
            self.assertTrue(
                project_runtime._runtime_inventory_matches(
                    backup,
                    identity=old_identity,
                    inventory=old_inventory,
                )
            )
            self.assertEqual(
                (
                    rollback / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                ).read_bytes(),
                receipt,
            )

            collision.unlink()
            final.rmdir()
            self.assertTrue(
                project_runtime.remove_materialized_runtime(project, runtime)
            )
            self.assertTrue(
                project_runtime._runtime_inventory_matches(
                    final,
                    identity=old_identity,
                    inventory=old_inventory,
                )
            )
            self.assertFalse(backup.exists())
            self.assertFalse(rollback.exists())

    @unittest.skipUnless(
        WINDOWS_RUNTIME,
        "Runtime rollback retained-handle deletion is Windows-only.",
    )
    def test_runtime_repair_resume_flushes_restore_before_new_tree_delete(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            runtime, final, transaction, receipt, old_inventory, old_identity = (
                self._small_materialization(
                    project,
                    "txn-repair-post-restore-power-cut",
                    repaired=True,
                )
            )
            backup = (
                transaction
                / project_runtime.PROJECT_RUNTIME_REPAIR_BACKUP_NAME
            )
            rollback = (
                transaction
                / project_runtime.PROJECT_RUNTIME_ROLLBACK_CANDIDATE_NAME
            )
            original_move = project_runtime._atomic_promote_directory_no_replace
            move_count = 0

            def power_cut_after_move(
                source: Path,
                destination: Path,
            ) -> None:
                nonlocal move_count
                move_count += 1
                original_move(source, destination)
                if move_count == 2:
                    raise OSError("synthetic power cut after restore rename")

            with patch.object(
                project_runtime,
                "_atomic_promote_directory_no_replace",
                side_effect=power_cut_after_move,
            ):
                self.assertFalse(
                    project_runtime.remove_materialized_runtime(
                        project,
                        runtime,
                    )
                )
            self.assertTrue(
                project_runtime._runtime_inventory_matches(
                    final,
                    identity=old_identity,
                    inventory=old_inventory,
                )
            )
            self.assertFalse(backup.exists())
            self.assertEqual(
                (
                    rollback / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                ).read_bytes(),
                receipt,
            )

            with patch.object(
                project_runtime,
                "_flush_directory_durable",
                side_effect=project_runtime.ProjectRuntimeError(
                    "project_runtime_directory_durability_failed"
                ),
            ):
                self.assertFalse(
                    project_runtime.remove_materialized_runtime(
                        project,
                        runtime,
                    )
                )
            self.assertTrue(rollback.is_dir())
            self.assertEqual(
                (
                    rollback / project_runtime.PROJECT_RUNTIME_RECEIPT_NAME
                ).read_bytes(),
                receipt,
            )
            self.assertTrue(
                project_runtime.remove_materialized_runtime(project, runtime)
            )
            self.assertTrue(
                project_runtime._runtime_inventory_matches(
                    final,
                    identity=old_identity,
                    inventory=old_inventory,
                )
            )
            self.assertFalse(rollback.exists())

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
