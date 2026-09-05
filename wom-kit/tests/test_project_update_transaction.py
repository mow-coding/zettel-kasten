from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import ExitStack, contextmanager, nullcontext
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import archive_cli
from wom_kit import archive_services
from wom_kit import exact_human_approval
from wom_kit.exact_human_approval_windows import (
    CURRENT_INTERACTIVE_INTENT_MECHANISM,
)
from wom_kit import project_update_transaction as transaction_module
from wom_kit.project_update_transaction import (
    ABSENT_COMPONENT_SHA256,
    CHECKPOINT_CHAIN_START_SHA256,
    CLEANUP_PLAN_NAME,
    CLEANUP_PLAN_SCHEMA,
    LEGACY_CLEANUP_PLAN_NAME,
    LEGACY_CLEANUP_PLAN_SCHEMA,
    ComponentExpectation,
    DirectoryDurability,
    LockObservation,
    ProjectUpdateBindings,
    ProjectUpdateComponent,
    ProjectUpdateTransaction,
    ProjectUpdateTransactionError,
    active_transaction_ref_for_resume_read_only,
    active_transaction_ref_from_lock_read_only,
    canonical_json_bytes,
    classify_components,
    digest_component,
    inspect_prelock_orphans,
    sha256_bytes,
)


def digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("ascii")).hexdigest()


class ProjectUpdateTransactionTests(unittest.TestCase):
    DEFAULT_TRANSACTION_REF = "update_0123456789abcdef0123456789abcdef"
    CREATED_AT = "2026-08-23T00:00:00Z"

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "project"
        self.project.mkdir()
        self.pre_values = {
            "source": b"source-old",
            "runtime": b"runtime-old",
            "launcher": b"launcher-old",
            "pin-shadow": b"pin-shadow-old",
            "receipt": b"receipt-old",
            "active-pin": b"v0.4.0\n",
        }
        self.post_values = {
            "source": b"source-new",
            "runtime": b"runtime-new",
            "launcher": b"launcher-new",
            "pin-shadow": b"pin-shadow-new",
            "receipt": self.static_receipt(self.DEFAULT_TRANSACTION_REF),
            "active-pin": b"v0.4.3\n",
        }

    def run_hard_exit_worker(
        self,
        worker: str,
        *arguments: str,
        expected_returncode: int,
    ) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(SRC_ROOT),
                "PYTHONUTF8": "1",
            }
        )
        completed = subprocess.run(
            [sys.executable, "-B", "-c", worker, *arguments],
            cwd=KIT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            expected_returncode,
            completed.stdout + completed.stderr,
        )
        return completed

    @staticmethod
    def bindings() -> ProjectUpdateBindings:
        return ProjectUpdateBindings(
            preflight_sha256=digest("preflight"),
            source_sha256=digest("source-binding"),
            config_sha256=digest("config"),
            ref_sha256=digest("ref"),
            pin_sha256=digest("pin-binding"),
            launcher_sha256=digest("launcher-binding"),
            runtime_sha256=digest("runtime-binding"),
            receipt_sha256=digest("receipt-binding"),
            bundle_sha256=digest("prepared-bundle-binding"),
        )

    def static_receipt(self, transaction_ref: str) -> bytes:
        return canonical_json_bytes(
            {
                "plan_sha256": digest("static-plan"),
                "schema": "wom-kit/project-version-update-static-receipt/v0.4.3",
                "target_binding_sha256": digest("static-target-binding"),
                "timestamp": self.CREATED_AT,
                "transaction_ref": transaction_ref,
            }
        ) + b"\n"

    def prepare_terminal_delivery_fixture(
        self,
        label: str,
        *,
        result_domain_override: dict[str, object] | None = None,
        proof_capability_override: str | None = None,
        terminal_overrides: dict[str, bool] | None = None,
    ) -> dict[str, object]:
        private_root = self.project / ".zettel-kasten" / "private"
        private_root.mkdir(parents=True, exist_ok=True)
        diagnostics = self.project / ".zettel-kasten" / "diagnostics"
        diagnostics.mkdir(parents=True, exist_ok=True)
        domain_result: dict[str, object] = {
            "ok": True,
            "status": "updated_restart_required",
            "warnings": [],
            "next_safe_actions": ["restart"],
        }
        terminal = {
            "schema": (
                "wom-kit/project-version-update-terminal-finalization/v0.1"
            ),
            "update_result_verified_in_current_invocation": True,
            "update_result_reauthenticated_from_durable_handoff": False,
            "claim_succeeded_verified": True,
            "transaction_completed_checkpoint_verified": True,
            "lock_absence_verified": True,
            "transaction_cleanup_completed": True,
            "service_resource_close_verified": True,
            "git_runner_close_verified": True,
            "attention_required": True,
            "domain_writer_reentry_allowed": False,
            "automatic_retry_allowed": False,
            "cleanup_proof_used_as_success_authority": False,
            "durable_terminal_handoff_ready": True,
            "durable_terminal_handoff_replayed": False,
            "durable_result_delivery_acknowledged": False,
            "private_paths_echoed": False,
            "private_identifiers_echoed": False,
        }
        if terminal_overrides is not None:
            terminal.update(terminal_overrides)
        effective_domain = result_domain_override or domain_result
        result = archive_services._project_update_terminal_result_from_domain(
            effective_domain,
            terminal,
        )
        self.assertIsNotNone(result)
        preview = {"status": "prepared"}
        basis = {"schema": "synthetic-recovery-basis"}
        postimage: dict[str, str] = {}
        attachments = {
            "prepared_preview": preview,
            "domain_result": domain_result,
            "recovery_basis": basis,
            "exact_postimage": postimage,
        }
        pending_payload = {
            "prepared_preview_sha256": (
                transaction_module.sha256_document(preview)
            ),
            "domain_result_sha256": (
                transaction_module.sha256_document(domain_result)
            ),
            "domain_result_size_bytes": len(
                transaction_module.canonical_json_bytes(domain_result)
            ),
            "recovery_basis_sha256": (
                transaction_module.sha256_document(basis)
            ),
            "exact_postimage_sha256": (
                transaction_module.sha256_document(postimage)
            ),
        }
        pending = {
            "payload": pending_payload,
            "attachments": attachments,
        }
        capability = (
            "hmac-sha256:"
            + hashlib.sha256(("capability-" + label).encode("ascii")).hexdigest()
        )
        ready = {
            "payload": {
                "delivery_capability_sha256": (
                    transaction_module.sha256_bytes(
                        capability.encode("ascii")
                    )
                )
            }
        }
        active = {
            "schema": archive_services._PROJECT_UPDATE_TERMINAL_HANDOFF_SCHEMA,
            "state": "terminal_ready",
            "pending": pending,
            "ready": ready,
        }
        handoff, guard = archive_services._project_update_terminal_handoff_paths(
            self.project
        )
        scaffold = archive_services._project_update_terminal_control_scaffold(
            self.project
        )
        self.assertTrue(os.path.samefile(scaffold, handoff.parent))
        self.assertEqual(guard.read_bytes(), b"\x00")
        handoff_raw = archive_services._project_update_canonical_bytes(active)
        handoff.write_bytes(handoff_raw)
        handoff_sha256 = transaction_module.sha256_bytes(handoff_raw)
        archive_services._project_update_register_terminal_delivery_capability(
            handoff_sha256,
            capability,
        )
        operation_ref = "op:sha256:" + hashlib.sha256(
            ("operation-" + label).encode("ascii")
        ).hexdigest()
        run_id = hashlib.sha256(
            ("run-" + label).encode("ascii")
        ).hexdigest()[:32]
        output_relative = (
            ".zettel-kasten/diagnostics/update-" + label + ".json"
        )
        proof = archive_services._project_update_terminal_delivery_output_proof(
            proof_capability_override or capability,
            result,
            handoff_sha256=handoff_sha256,
            output_relative=output_relative,
            run_id=run_id,
            operation_ref=operation_ref,
        )
        output_document = {
            **result,
            "cli_execution": {
                "status": "completed",
                "command": "project-version-update",
                "result_available": True,
                "exit_code": 0,
                "run_id": run_id,
                "terminal_delivery": proof,
            },
            "cli_output_artifact": {
                "operation": {"operation_ref": operation_ref}
            },
        }
        output_path = self.project.joinpath(
            *output_relative.split("/")
        )
        output_path.write_text(
            json.dumps(output_document, ensure_ascii=True, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return {
            "result": result,
            "handoff": handoff,
            "handoff_raw": handoff_raw,
            "handoff_sha256": handoff_sha256,
            "capability": capability,
            "output_relative": output_relative,
            "run_id": run_id,
            "operation_ref": operation_ref,
        }

    def components(
        self, *, receipt_postimage: bytes | None = None
    ) -> tuple[ProjectUpdateComponent, ...]:
        definitions = (
            ("source", "source", ".zettel-kasten/source-head"),
            ("runtime", "runtime", ".zettel-kasten/runtimes/v0.4.3"),
            ("launcher", "launcher", ".zettel-kasten/bin/archive.cmd"),
            (
                "pin-shadow",
                "non_active_pin",
                ".zettel-kasten/pins/v0.4.3.pending",
            ),
            ("receipt", "receipt", ".zettel-kasten/receipts/update-v0.4.3.json"),
            ("active-pin", "active_pin", ".zettel-kasten/installed-version.txt"),
        )
        result = []
        receipt_value = receipt_postimage or self.post_values["receipt"]
        for sequence, (component_ref, role, target) in enumerate(definitions, start=1):
            key = component_ref
            post_value = receipt_value if role == "receipt" else self.post_values[key]
            result.append(
                ProjectUpdateComponent(
                    component_ref=component_ref,
                    role=role,
                    sequence=sequence,
                    logical_target=target,
                    pre_sha256=digest_component(self.pre_values[key]),
                    post_sha256=digest_component(post_value),
                    preimage_key=key,
                )
            )
        return tuple(result)

    def create_transaction(
        self,
        *,
        transaction_ref: str = DEFAULT_TRANSACTION_REF,
    ) -> ProjectUpdateTransaction:
        static_receipt = self.static_receipt(transaction_ref)
        return ProjectUpdateTransaction.create(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.3",
            bindings=self.bindings(),
            components=self.components(receipt_postimage=static_receipt),
            preimages=dict(self.pre_values),
            runtime_bundle={
                "main-wheel": b"synthetic main wheel",
                "dependency-wheel": b"synthetic dependency wheel",
            },
            static_receipt_postimage=static_receipt,
            transaction_ref=transaction_ref,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )

    def reserve_and_build_candidate(
        self,
        *,
        transaction_ref: str = DEFAULT_TRANSACTION_REF,
        file_count: int = 3,
        acquire: bool = True,
    ):
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.3",
            transaction_ref=transaction_ref,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock(
            observation=LockObservation(
                pid=1234, process_start="candidate-builder-start"
            )
        ) if acquire else None
        runtime_parent = self.project / ".zettel-kasten" / "runtimes"
        runtime_parent_existed_before = runtime_parent.exists()
        runtime_parent.mkdir(exist_ok=True)
        candidate = reserved.runtime_candidate_path
        candidate.mkdir()
        artifacts = candidate / "runtime-artifacts"
        artifacts.mkdir()
        for index in range(file_count):
            (artifacts / f"artifact-{index:04d}.bin").write_bytes(
                f"artifact-{index}".encode("ascii")
            )
        runtime_receipt = canonical_json_bytes(
            {
                "installed_payload_sha256": digest("runtime-new"),
                "schema": "wom-kit/project-runtime-receipt/v0.1",
                "status": "verified",
            }
        ) + b"\n"
        (candidate / "runtime-receipt.json").write_bytes(runtime_receipt)
        tree = transaction_module._runtime_candidate_tree_inventory(
            candidate, transaction_root=reserved.transaction_root
        )
        project_info = self.project.stat()
        transaction_info = reserved.transaction_root.stat()
        candidate_info = candidate.stat()
        runtime_parent_info = runtime_parent.stat()
        runtime_parent_identity = [
            int(runtime_parent_info.st_dev),
            int(runtime_parent_info.st_ino),
        ]
        seal = {
            "absolute_paths_echoed": False,
            "candidate_locator": reserved.reservation.runtime_candidate_logical_ref,
            "candidate_sha256": digest("candidate-binding"),
            "existing_runtime_reusable": False,
            "existing_runtime_repair_required": False,
            "existing_runtime_inventory_sha256": None,
            "existing_runtime_inventory_count": 0,
            "existing_runtime_inventory_bytes": 0,
            "inventory_bytes": tree.total_bytes,
            "inventory_count": tree.inventory_count,
            "inventory_sha256": tree.recursive_tree_sha256,
            "marker_free_final_postimage": True,
            "path_identities": {
                "candidate_root": [
                    int(candidate_info.st_dev),
                    int(candidate_info.st_ino),
                ],
                "project_root": [
                    int(project_info.st_dev),
                    int(project_info.st_ino),
                ],
                "runtime_parent": runtime_parent_identity,
                "runtime_parent_created": (
                    None
                    if runtime_parent_existed_before
                    else runtime_parent_identity
                ),
                "transaction_root": [
                    int(transaction_info.st_dev),
                    int(transaction_info.st_ino),
                ],
                "existing_runtime_root": None,
            },
            "post_approval_child_process_allowed": False,
            "post_approval_copy_allowed": False,
            "post_approval_network_allowed": False,
            "receipt_sha256": sha256_bytes(runtime_receipt),
            "recursive_directory_durability_verified": True,
            "runtime_parent_existed_before": runtime_parent_existed_before,
            "same_volume_verified": True,
            "seal_parent_durability_required": True,
            "schema": "wom-kit/project-runtime-candidate/v0.1",
            "status": "sealed",
            "supply_lock_sha256": digest("supply-lock"),
            "target_commit": "a" * 40,
            "target_tag": "v0.4.3",
            "transaction_ref": transaction_ref,
            "wheel_file_name": "wom_kit-0.4.3-py3-none-any.whl",
            "wheel_sha256": digest("wheel"),
        }
        reserved.runtime_candidate_seal_path.write_bytes(
            canonical_json_bytes(seal) + b"\n"
        )
        return reserved, lock_bytes, tree

    def seal_reserved(
        self,
        reserved,
        tree,
        *,
        provider_inventory_sha256: str | None = None,
    ) -> ProjectUpdateTransaction:
        static_receipt = self.static_receipt(reserved.transaction_ref)
        components = self.components(receipt_postimage=static_receipt)
        runtime_post = next(
            component.post_sha256
            for component in components
            if component.role == "runtime"
        )
        return reserved.seal_intent(
            bindings=self.bindings(),
            components=components,
            preimages=dict(self.pre_values),
            private_binding_blobs={
                "git-runner-binding": canonical_json_bytes(
                    {
                        "runner_sha256": digest("git-runner"),
                        "schema": "wom-kit/git-runner-binding/v0.4.3",
                    }
                )
                + b"\n"
            },
            static_receipt_postimage=static_receipt,
            runtime_candidate_inventory_sha256=(
                provider_inventory_sha256 or tree.recursive_tree_sha256
            ),
            runtime_candidate_postimage_sha256=runtime_post,
        )

    def test_legacy_recovery_detached_seal_requires_exact_private_binding(self) -> None:
        reserved, lock_bytes, tree = self.reserve_and_build_candidate(
            acquire=False
        )
        self.assertIsNone(lock_bytes)
        binding = digest("legacy-recovery-binding")
        static_receipt = self.static_receipt(reserved.transaction_ref)
        components = self.components(receipt_postimage=static_receipt)
        runtime_post = next(
            component.post_sha256
            for component in components
            if component.role == "runtime"
        )
        common = {
            "bindings": self.bindings(),
            "components": components,
            "preimages": dict(self.pre_values),
            "static_receipt_postimage": static_receipt,
            "runtime_candidate_inventory_sha256": tree.recursive_tree_sha256,
            "runtime_candidate_postimage_sha256": runtime_post,
            "_legacy_recovery_binding_sha256": binding,
        }
        self.assert_code(
            "project_update_transaction_intent_invalid",
            lambda: reserved.seal_intent(
                **common,
                private_binding_blobs={
                    "git-runner-binding": b"private-runner",
                    "legacy-prewrite-recovery-binding": b"wrong\n",
                },
            ),
        )
        transaction = reserved.seal_intent(
            **common,
            private_binding_blobs={
                "git-runner-binding": b"private-runner",
                "legacy-prewrite-recovery-binding": (
                    binding + "\n"
                ).encode("ascii"),
            },
        )
        self.assertEqual(transaction.intent.requested_target_tag, "v0.4.3")
        self.assertTrue((reserved.transaction_root / "intent-seal.json").is_file())
        self.assertFalse((reserved.transaction_root / "checkpoints.jsonl").exists())
        self.assertFalse(
            (reserved.transaction_root / "reservation-lock-backlink.json").exists()
        )
        self.assertFalse(
            (reserved.transaction_root / "lock-backlink.json").exists()
        )

    def transaction_root(self, transaction: ProjectUpdateTransaction) -> Path:
        return (
            self.project
            / ".zettel-kasten"
            / "private"
            / "version-updates"
            / transaction.transaction_ref
        )

    def live_pre(self) -> dict[str, str]:
        return {key: digest_component(value) for key, value in self.pre_values.items()}

    def live_post(self) -> dict[str, str]:
        return {key: digest_component(value) for key, value in self.post_values.items()}

    def claim_evidence(
        self,
        transaction: ProjectUpdateTransaction,
        *,
        approval_reference: str,
        claim_receipt: str,
        claim_mac: str,
    ) -> dict[str, str]:
        static_receipt = next(
            record.sha256
            for record in transaction.intent.private_bindings
            if record.logical_key == "static-receipt-postimage"
        )
        return {
            "approval_reference_sha256": approval_reference,
            "claim_mac_sha256": claim_mac,
            "claim_receipt_sha256": claim_receipt,
            "static_receipt_sha256": static_receipt,
        }

    def activate(self, transaction: ProjectUpdateTransaction) -> bytes:
        lock_bytes = transaction.lock_bytes()
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        self.assertEqual(lock_path.read_bytes(), lock_bytes)
        transaction.bind_lock_backlink(lock_bytes)
        return lock_bytes

    def remove_sealed_candidate(self, transaction: ProjectUpdateTransaction) -> None:
        shutil.rmtree(transaction.runtime_candidate_path)
        (transaction.transaction_root / "runtime-candidate-seal.json").unlink()
        if not transaction.intent.runtime_candidate.runtime_parent_existed_before:
            (self.project / ".zettel-kasten" / "runtimes").rmdir()

    def runtime_cleanup_terminal_evidence(
        self,
        transaction,
    ) -> dict[str, object]:
        """Build the exact content-free runtime proof used by transaction tests."""

        if isinstance(transaction, ProjectUpdateTransaction):
            binding = transaction.intent.runtime_candidate
            transaction_ref = transaction.transaction_ref
            target_tag = transaction.intent.requested_target_tag
            candidate_sha256 = binding.provider_candidate_sha256
            inventory_sha256 = binding.provider_inventory_sha256
            inventory_count = binding.inventory_count
            inventory_bytes = binding.inventory_bytes
        elif transaction.runtime_candidate_seal_path.is_file():
            seal = json.loads(
                transaction.runtime_candidate_seal_path.read_text(
                    encoding="utf-8"
                )
            )
            transaction_ref = transaction.transaction_ref
            target_tag = transaction.reservation.requested_target_tag
            candidate_sha256 = seal["candidate_sha256"]
            inventory_sha256 = seal["inventory_sha256"]
            inventory_count = seal["inventory_count"]
            inventory_bytes = seal["inventory_bytes"]
        else:
            # A reservation may fail before the runtime candidate is built.
            # The runtime subsystem still emits a terminal cleanup capsule
            # proving the candidate/quarantine namespaces are absent; there is
            # no candidate binding in the reservation against which these
            # content-free inventory scalars could be compared.
            transaction_ref = transaction.transaction_ref
            target_tag = transaction.reservation.requested_target_tag
            candidate_sha256 = digest(
                "absent-runtime-candidate:" + transaction_ref
            )
            inventory_sha256 = digest(
                "absent-runtime-inventory:" + transaction_ref
            )
            inventory_count = 1
            inventory_bytes = 0
        return {
            "absolute_paths_echoed": False,
            "candidate_root_absent": True,
            "candidate_sha256": candidate_sha256,
            "cleanup_complete": True,
            "normal_seal_absent": True,
            "outer_transaction_ack_required_before_retire": True,
            "private_paths_echoed": False,
            "provider_inventory_bytes": inventory_bytes,
            "provider_inventory_count": inventory_count,
            "provider_inventory_sha256": inventory_sha256,
            "quarantine_root_absent": True,
            "runtime_cleanup_capsule_identity_sha256": digest(
                "runtime-cleanup-capsule-identity:" + transaction_ref
            ),
            "runtime_cleanup_capsule_sha256": digest(
                "runtime-cleanup-capsule:" + transaction_ref
            ),
            "runtime_parent_restored": True,
            "schema": (
                transaction_module.RUNTIME_CLEANUP_TERMINAL_EVIDENCE_SCHEMA
            ),
            "sidecar_must_retire_before_transaction_cleanup": True,
            "status": "terminal_cleanup_evidence",
            "target_tag": target_tag,
            "transaction_ref": transaction_ref,
        }

    def create_transaction_with_prepared_runtime_candidate(
        self,
        *,
        transaction_ref: str = DEFAULT_TRANSACTION_REF,
    ):
        """Create one real PreparedRuntimeCandidate for service seam tests."""

        runtime = archive_services.project_runtime
        reserved, reservation_lock, tree = self.reserve_and_build_candidate(
            transaction_ref=transaction_ref,
            acquire=True,
        )
        assert reservation_lock is not None
        candidate_root = reserved.runtime_candidate_path
        seal_path = reserved.runtime_candidate_seal_path
        inventory = runtime._candidate_inventory_snapshot(candidate_root)
        inventory_sha256 = runtime._recursive_candidate_inventory_digest(
            inventory
        )
        inventory_bytes = sum(
            item.size_bytes
            for item in inventory
            if item.entry_type == "file"
        )
        seal = json.loads(seal_path.read_text(encoding="ascii"))
        seal.update(
            {
                "inventory_sha256": "sha256:" + inventory_sha256,
                "inventory_count": len(inventory),
                "inventory_bytes": inventory_bytes,
            }
        )
        seal_bytes = canonical_json_bytes(seal) + b"\n"
        with seal_path.open("r+b") as stream:
            stream.seek(0)
            stream.write(seal_bytes)
            stream.truncate()
            stream.flush()
            os.fsync(stream.fileno())
        runtime._flush_directory_durable(reserved.transaction_root)
        transaction = self.seal_reserved(
            reserved,
            tree,
            provider_inventory_sha256="sha256:" + inventory_sha256,
        )
        transaction.bind_sealed_intent_to_lock(reservation_lock)
        lock_bytes = reservation_lock
        identities = seal["path_identities"]
        receipt_bytes = (
            candidate_root / "runtime-receipt.json"
        ).read_bytes()
        prepared = runtime.PreparedRuntimeCandidate(
            target_tag=seal["target_tag"],
            target_version=seal["target_tag"].removeprefix("v"),
            target_commit=seal["target_commit"],
            transaction_ref=transaction_ref,
            logical_candidate_path=seal["candidate_locator"],
            logical_seal_path=(
                seal_path.relative_to(self.project).as_posix()
            ),
            project_root=self.project,
            transaction_root=transaction.transaction_root,
            candidate_root=candidate_root,
            seal_path=seal_path,
            project_root_identity=tuple(identities["project_root"]),
            transaction_root_identity=tuple(identities["transaction_root"]),
            candidate_root_identity=tuple(identities["candidate_root"]),
            runtime_parent_identity=tuple(identities["runtime_parent"]),
            runtime_parent_existed_before=seal[
                "runtime_parent_existed_before"
            ],
            runtime_parent_created_identity=(
                None
                if identities["runtime_parent_created"] is None
                else tuple(identities["runtime_parent_created"])
            ),
            same_volume_identity=identities["candidate_root"][0],
            inventory=inventory,
            inventory_sha256=inventory_sha256,
            candidate_sha256=seal["candidate_sha256"].removeprefix(
                "sha256:"
            ),
            inventory_count=len(inventory),
            inventory_bytes=inventory_bytes,
            seal_bytes=seal_bytes,
            seal_sha256=hashlib.sha256(seal_bytes).hexdigest(),
            receipt_bytes=receipt_bytes,
            receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
            wheel_file_name=seal["wheel_file_name"],
            wheel_sha256=seal["wheel_sha256"].removeprefix("sha256:"),
            supply_lock_sha256=seal["supply_lock_sha256"].removeprefix(
                "sha256:"
            ),
            supply_lock_bytes=b"synthetic supply lock\n",
            artifact_inventory=(),
            installed_payload_sha256="0" * 64,
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
        return transaction, lock_bytes, prepared

    def prepare_typed_runtime_cleanup_capsule(
        self,
        transaction: ProjectUpdateTransaction,
        candidate,
    ):
        """Create real durable capsule/evidence while keeping it unretired."""

        runtime = archive_services.project_runtime
        self.assertIsInstance(candidate, runtime.PreparedRuntimeCandidate)
        capsule = runtime._create_runtime_candidate_cleanup_capsule(candidate)
        self.assertIsInstance(capsule, runtime.RuntimeCandidateCleanupCapsule)
        assert capsule is not None
        self.remove_sealed_candidate(transaction)
        evidence = runtime.runtime_candidate_cleanup_terminal_evidence(capsule)
        self.assertIsInstance(evidence, dict)
        return capsule, evidence

    @staticmethod
    def tree_snapshot(root: Path) -> dict[str, tuple[str, bytes | None]]:
        if not root.exists():
            return {}
        return {
            path.relative_to(root).as_posix(): (
                ("directory", None)
                if path.is_dir()
                else ("file", path.read_bytes())
            )
            for path in root.rglob("*")
        }

    def assert_preapproval_cancel_effect_truth(
        self,
        result: dict,
        *,
        live_lock_verified: bool,
        prior_lock_binding_verified: bool = True,
        lock_binding_verified_during_recovery: bool = False,
        reservation_abort_evidence: bool,
        candidate_cleanup: bool,
    ) -> None:
        self.assertEqual(result["files_written"], [])
        self.assertEqual(
            result["files_written_scope"],
            "project_domain_only",
        )
        self.assertEqual(
            result["effect_summary"],
            {
                "project_domain_writes_performed": False,
                "project_domain_files_written": [],
                "durable_control_evidence_written_or_verified": True,
                "reservation_abort_evidence_written_or_verified": (
                    reservation_abort_evidence
                ),
                "cancellation_checkpoints_written_or_verified": (
                    not reservation_abort_evidence
                ),
                "candidate_cleanup_performed_or_verified": (
                    candidate_cleanup
                ),
                "private_control_mutation_performed_or_verified": True,
                "private_control_mutation_may_be_incomplete": False,
                "candidate_absence_verified": True,
                "lock_release_performed_or_verified": True,
                "paths_or_identifiers_disclosed": False,
            },
        )
        recovery = result["preapproval_recovery"]
        self.assertNotIn("exact_live_lock_verified", recovery)
        self.assertIs(
            recovery["live_lock_verified"],
            live_lock_verified,
        )
        self.assertIs(
            recovery["prior_lock_binding_verified"],
            prior_lock_binding_verified,
        )
        self.assertIs(
            recovery["lock_binding_verified_during_recovery"],
            lock_binding_verified_during_recovery,
        )
        self.assertTrue(recovery["lock_absence_verified_after_recovery"])

    def assert_cleanup_hardlink_blocks_fresh_writer(self) -> None:
        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_artifact_classification_read_only(
                self.project
            ),
            ("unresolved", 0),
        )
        approval_calls: list[bool] = []
        with (
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_approval_authority_matches",
                return_value=True,
            ),
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_legacy_core",
                side_effect=AssertionError(
                    "hardlinked cleanup evidence entered project writer"
                ),
            ) as legacy_core,
        ):
            dry_run_result = archive_services.wom_kit_project_version_update(
                self.project,
                target="v0.4.17",
                dry_run=True,
            )
            approval_result = (
                archive_services
                ._wom_kit_project_version_update_live_approval_transaction(
                    self.project,
                    target="v0.4.17",
                    reviewed_by="person:hardlink-reviewer",
                    affirm_external_writers_quiescent=True,
                    approval_executor=lambda *_args, **_kwargs: (
                        approval_calls.append(True)
                    ),
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive-identity",
                )
            )
        self.assertEqual(dry_run_result, approval_result)
        self.assertFalse(dry_run_result["ok"])
        self.assertEqual(
            dry_run_result["status"],
            "terminal_cleanup_outcome_unknown",
        )
        self.assertEqual(
            dry_run_result["reason_code"],
            "project_version_update_terminal_cleanup_outcome_unknown",
        )
        self.assertFalse(dry_run_result["domain_writer_entered"])
        self.assertEqual(dry_run_result["project_domain_files_written"], [])
        self.assertEqual(dry_run_result["files_written"], [])
        self.assertEqual(approval_calls, [])
        legacy_core.assert_not_called()

    def assert_reopen_guard_failure_closes_all_handles(
        self,
        guard_type: type[archive_services._WomKitProjectUpdateDirectoryGuard],
        *,
        minimum_held: int,
        runner_close_fails: bool = False,
    ) -> None:
        metadata_root = self.project / ".zettel-kasten"
        mirror_path = metadata_root / "source"
        (mirror_path / "held" / "fail").mkdir(parents=True)
        transaction_ref = self.DEFAULT_TRANSACTION_REF
        candidate_summary = {"candidate": "sealed"}
        candidate = SimpleNamespace(
            candidate_root=self.project / "missing-runtime-candidate",
            legacy_resume_shape=False,
            public_summary=lambda: candidate_summary,
        )
        fake_transaction = SimpleNamespace(
            intent=SimpleNamespace(
                requested_target_tag="v0.4.3",
                components=(),
                runtime_candidate=SimpleNamespace(
                    legacy_document_shape=False,
                ),
            ),
            transaction_root=(
                metadata_root
                / "private"
                / "version-updates"
                / transaction_ref
            ),
            private_binding_bytes=lambda _key: b"bound-private-value",
            inspect=lambda: SimpleNamespace(
                journal=SimpleNamespace(
                    verified_prefix=(
                        SimpleNamespace(
                            phase="preapproval_cancel_requested"
                        ),
                    )
                )
            ),
        )
        private_plan = {
            "domain_plan": {
                "runtime_candidate_sha256": (
                    transaction_module.sha256_document(candidate_summary)
                ),
            },
            "expected_archive_identity_sha256": digest("archive-identity"),
            "mirror_logical": ".zettel-kasten/source",
            "reviewer": "reviewer-a",
            "runtime_bootstrap": {
                "available": True,
                "release_tag": "v0.4.3",
                "wheel_file_name": "wom_kit-0.4.3-py3-none-any.whl",
                "wheel_sha256": digest("wheel"),
            },
            "runtime_candidate_private": {},
            "static_receipt_schema": (
                "wom-kit/project-version-update-receipt/v0.3"
            ),
            "target_commit": "a" * 40,
            "target_tag": "v0.4.3",
            "target_version": "0.4.3",
            "transaction_ref": transaction_ref,
        }
        closed: list[str] = []
        def close_runner() -> None:
            closed.append("runner")
            if runner_close_fails:
                raise KeyboardInterrupt("private runner close failure")

        runner = SimpleNamespace(
            close_transport_boundary=lambda: closed.append("transport"),
            close=close_runner,
        )

        with (
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_approval_authority_matches",
                return_value=True,
            ),
            patch.object(
                archive_services.project_update_transaction,
                "active_transaction_ref_for_resume_read_only",
                return_value=transaction_ref,
            ),
            patch.object(
                archive_services.project_update_transaction.ProjectUpdateTransaction,
                "open",
                return_value=fake_transaction,
            ),
            patch.object(
                archive_services,
                "_project_update_parse_private_plan",
                return_value=private_plan,
            ),
            patch.object(
                archive_services,
                "exact_human_approval_archive_identity_sha256",
                return_value=digest("archive-identity"),
            ),
            patch.object(
                archive_services.project_update_git_runner,
                "load_private_binding_bytes",
                return_value=object(),
            ),
            patch.object(
                archive_services.project_update_git_runner.TrustedProjectUpdateGitRunner,
                "reopen_private",
                return_value=runner,
            ),
            patch.object(
                archive_services.project_runtime,
                "BootstrapWheel",
                return_value=object(),
            ),
            patch.object(
                archive_services.project_runtime,
                "project_runtime_supply_lock",
                return_value=object(),
            ),
            patch.object(
                archive_services,
                "_project_update_restore_runtime_candidate",
                return_value=candidate,
            ),
            patch.object(
                archive_services,
                "_WomKitProjectUpdateDirectoryGuard",
                guard_type,
            ),
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "project_version_update_directory_stability_unavailable",
            ):
                archive_services._project_update_reopen_durable_state(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    expected_approval_root=self.project,
                    expected_archive_id="archive-identity",
                )

        self.assertEqual(len(guard_type.instances), 1)
        guard = guard_type.instances[0]
        self.assertGreaterEqual(guard.maximum_held, minimum_held)
        self.assertEqual(guard._handles, {})
        self.assertEqual(guard._identities, {})
        self.assertEqual(closed, ["transport", "runner"])

        moved = self.project.with_name("project-after-guard-failure")
        self.project.rename(moved)
        shutil.rmtree(moved)
        self.assertFalse(moved.exists())

    def begin(
        self,
        transaction: ProjectUpdateTransaction,
        *,
        approval_reference: str | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        lock_bytes = self.activate(transaction)
        live = self.live_pre()
        first = transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=live,
        )
        self.assertEqual(first.previous_checkpoint_sha256, CHECKPOINT_CHAIN_START_SHA256)
        transaction.append(
            phase="approval_bound",
            stage="verified",
            live_component_sha256=live,
            approval_reference_sha256=(
                approval_reference or digest("main-approval-reference")
            ),
            approval_mac_sha256=digest("main-approval-mac"),
        )
        return lock_bytes, live

    def ready_forward(
        self,
        transaction: ProjectUpdateTransaction,
        *,
        approval_reference: str | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        lock_bytes, live = self.begin(
            transaction,
            approval_reference=approval_reference,
        )
        for component in transaction.intent.components:
            transaction.append(
                phase=component.role,
                stage="intent",
                component_ref=component.component_ref,
                live_component_sha256=live,
            )
            runtime_cleanup = None
            if component.role == "runtime":
                runtime_cleanup = self.runtime_cleanup_terminal_evidence(
                    transaction
                )
                self.remove_sealed_candidate(transaction)
            live[component.component_ref] = component.post_sha256
            transaction.append(
                phase=component.role,
                stage="verified",
                component_ref=component.component_ref,
                live_component_sha256=live,
                runtime_cleanup_terminal_evidence=runtime_cleanup,
            )
        transaction.append(
            phase="domain_committed",
            stage="verified",
            live_component_sha256=live,
        )
        transaction.append(
            phase="claim_succeeded",
            stage="verified",
            live_component_sha256=live,
            claim_receipt_sha256=digest("claim-receipt"),
            claim_mac_sha256=digest("claim-mac"),
            claim_evidence=self.claim_evidence(
                transaction,
                approval_reference=(
                    approval_reference or digest("main-approval-reference")
                ),
                claim_receipt=digest("claim-receipt"),
                claim_mac=digest("claim-mac"),
            ),
        )
        transaction.append(
            phase="ready_to_unlock",
            stage="verified",
            live_component_sha256=live,
        )
        return lock_bytes, live

    def finish_forward(
        self,
        transaction: ProjectUpdateTransaction,
        *,
        approval_reference: str | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        lock_bytes, live = self.ready_forward(
            transaction,
            approval_reference=approval_reference,
        )
        release = transaction.release_lock_exact(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
        )
        self.assertTrue(release.released)
        self.assertTrue(release.directory_durability.durable)
        transaction.append(
            phase="lock_released",
            stage="verified",
            live_component_sha256=live,
            lock_release_result=release,
        )
        transaction.append(
            phase="completed",
            stage="verified",
            live_component_sha256=live,
        )
        return lock_bytes, live

    def assert_code(self, expected: str, action) -> None:
        with self.assertRaises(ProjectUpdateTransactionError) as caught:
            action()
        self.assertEqual(caught.exception.code, expected)
        self.assertEqual(str(caught.exception), expected)

    def test_runtime_candidate_binding_accepts_only_exact_legacy_or_current_shape(
        self,
    ) -> None:
        current = self.create_transaction().intent.runtime_candidate.document()
        repair_fields = (
            "existing_runtime_repair_required",
            "existing_runtime_inventory_sha256",
            "existing_runtime_inventory_count",
            "existing_runtime_inventory_bytes",
        )
        self.assertTrue(all(field in current for field in repair_fields))
        legacy = dict(current)
        for field in repair_fields:
            legacy.pop(field)
        restored = transaction_module.RuntimeCandidateBinding.from_document(
            legacy
        )
        self.assertTrue(restored.legacy_document_shape)
        self.assertEqual(restored.document(), legacy)

        for missing in repair_fields:
            with self.subTest(missing=missing):
                mixed = dict(current)
                mixed.pop(missing)
                self.assert_code(
                    "project_update_transaction_candidate_invalid",
                    lambda mixed=mixed: (
                        transaction_module.RuntimeCandidateBinding.from_document(
                            mixed
                        )
                    ),
                )

    def test_resume_serialization_family_rejects_crossed_shapes_and_plan_keys(
        self,
    ) -> None:
        def transaction(legacy: bool) -> SimpleNamespace:
            return SimpleNamespace(
                intent=SimpleNamespace(
                    runtime_candidate=SimpleNamespace(
                        legacy_document_shape=legacy,
                    )
                )
            )

        def candidate(legacy: bool) -> SimpleNamespace:
            return SimpleNamespace(legacy_resume_shape=legacy)

        legacy_plan = {"schema": "private-plan"}
        current_plan = {
            "schema": "private-plan",
            "static_receipt_schema": (
                "wom-kit/project-version-update-receipt/v0.3"
            ),
        }
        self.assertTrue(
            archive_services._project_update_legacy_resume_serialization_family(
                transaction(True),
                candidate(True),
                legacy_plan,
            )
        )
        self.assertFalse(
            archive_services._project_update_legacy_resume_serialization_family(
                transaction(False),
                candidate(False),
                current_plan,
            )
        )
        invalid_cases = (
            (True, False, legacy_plan),
            (False, True, current_plan),
            (True, True, current_plan),
            (False, False, legacy_plan),
        )
        for transaction_legacy, candidate_legacy, private_plan in invalid_cases:
            with self.subTest(
                transaction_legacy=transaction_legacy,
                candidate_legacy=candidate_legacy,
                schema_present="static_receipt_schema" in private_plan,
            ):
                with self.assertRaisesRegex(
                    archive_services.ArchiveServiceError,
                    "project_version_update_resume_binding_mismatch",
                ):
                    archive_services._project_update_legacy_resume_serialization_family(
                        transaction(transaction_legacy),
                        candidate(candidate_legacy),
                        private_plan,
                    )

    def test_candidate_seal_rejects_partial_current_repair_shape(self) -> None:
        reserved, _lock_bytes, tree = self.reserve_and_build_candidate()
        seal = json.loads(
            reserved.runtime_candidate_seal_path.read_text(encoding="ascii")
        )
        seal.pop("existing_runtime_inventory_bytes")
        reserved.runtime_candidate_seal_path.write_bytes(
            canonical_json_bytes(seal) + b"\n"
        )
        self.assert_code(
            "project_update_transaction_candidate_invalid",
            lambda: self.seal_reserved(reserved, tree),
        )

    def test_active_transaction_ref_is_derived_from_exact_live_lock_read_only(self) -> None:
        transaction = self.create_transaction()
        before = {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in self.project.rglob("*")
            if path.is_file()
        }

        discovered = active_transaction_ref_from_lock_read_only(
            self.project
        )

        self.assertEqual(discovered, transaction.transaction_ref)
        self.assertEqual(
            {
                path.relative_to(self.project).as_posix(): path.read_bytes()
                for path in self.project.rglob("*")
                if path.is_file()
            },
            before,
        )

    def test_existing_reservation_lock_reader_never_recreates_a_missing_lock(self) -> None:
        transaction = self.create_transaction()
        reservation = transaction_module.ReservedProjectUpdateTransaction.open(
            self.project,
            transaction.transaction_ref,
        )
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        exact = lock_path.read_bytes()
        self.assertEqual(
            reservation.existing_lock_bytes_read_only(),
            exact,
        )

        lock_path.unlink()
        with self.assertRaises(ProjectUpdateTransactionError):
            reservation.existing_lock_bytes_read_only()
        self.assertFalse(lock_path.exists())

    def test_active_transaction_ref_missing_or_tampered_lock_fails_without_writes(self) -> None:
        transaction = self.create_transaction()
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        original = lock_path.read_bytes()
        lock_path.write_bytes(
            original.replace(b'"schema"', b'"broken"', 1)
        )
        tampered = lock_path.read_bytes()

        with self.assertRaises(ProjectUpdateTransactionError):
            active_transaction_ref_from_lock_read_only(self.project)
        self.assertEqual(lock_path.read_bytes(), tampered)
        self.assertTrue(transaction.transaction_root.is_dir())

        lock_path.unlink()
        before = sorted(
            path.relative_to(self.project).as_posix()
            for path in self.project.rglob("*")
        )
        with self.assertRaises(ProjectUpdateTransactionError):
            active_transaction_ref_from_lock_read_only(self.project)
        self.assertEqual(
            sorted(
                path.relative_to(self.project).as_posix()
                for path in self.project.rglob("*")
            ),
            before,
        )

    def test_terminal_cleanup_artifact_inspection_is_content_agnostic_and_read_only(
        self,
    ) -> None:
        original_project = self.project
        cases = (
            ("rename", ".cleanup_update_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "directory"),
            ("partial", ".cleanup_update_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "partial"),
            (
                "proof",
                ".cleanup-proof_update_cccccccccccccccccccccccccccccccc.json",
                "file",
            ),
            ("malformed", ".cleanup_not-a-valid-transaction", "file"),
            ("malformed-proof", ".cleanup-proof_broken", "directory"),
        )
        try:
            for index, (case, name, kind) in enumerate(cases, start=1):
                with self.subTest(case=case):
                    self.project = (
                        Path(self.temporary.name) / f"cleanup-shape-{index}"
                    )
                    self.project.mkdir()
                    parent = (
                        self.project
                        / ".zettel-kasten"
                        / "private"
                        / "version-updates"
                    )
                    parent.mkdir(parents=True)
                    artifact = parent / name
                    if kind == "directory":
                        artifact.mkdir()
                    elif kind == "partial":
                        artifact.mkdir()
                        (artifact / "untrusted-partial.bin").write_bytes(
                            b"private residue"
                        )
                    else:
                        artifact.write_bytes(b"untrusted content")
                    before = self.tree_snapshot(self.project)

                    observed = transaction_module.inspect_terminal_cleanup_artifacts_for_resume_read_only(
                        self.project
                    )

                    self.assertEqual(
                        observed,
                        "observed_or_scan_incomplete",
                    )
                    self.assertEqual(self.tree_snapshot(self.project), before)
        finally:
            self.project = original_project

    def test_terminal_cleanup_artifact_inspection_cap_is_fail_closed(
        self,
    ) -> None:
        parent = (
            self.project
            / ".zettel-kasten"
            / "private"
            / "version-updates"
        )
        parent.mkdir(parents=True)
        for index in range(
            transaction_module.MAX_TERMINAL_CLEANUP_SCAN_ENTRIES + 1
        ):
            (parent / f"benign-{index:04d}").write_bytes(b"")
        before = self.tree_snapshot(self.project)

        observed = transaction_module.inspect_terminal_cleanup_artifacts_for_resume_read_only(
            self.project
        )

        self.assertEqual(observed, "observed_or_scan_incomplete")
        self.assertEqual(self.tree_snapshot(self.project), before)

    def test_terminal_cleanup_artifact_inspection_absent_is_distinct(
        self,
    ) -> None:
        before = self.tree_snapshot(self.project)
        observed = transaction_module.inspect_terminal_cleanup_artifacts_for_resume_read_only(
            self.project
        )
        self.assertEqual(observed, "absent")
        self.assertEqual(self.tree_snapshot(self.project), before)

    def test_terminal_cleanup_scan_never_reads_artifact_content_or_type(
        self,
    ) -> None:
        parent = (
            self.project
            / ".zettel-kasten"
            / "private"
            / "version-updates"
        )
        parent.mkdir(parents=True)

        class UntrustedSpecialEntry:
            name = ".cleanup_special-untrusted-entry"

            def __getattr__(self, _name):
                raise AssertionError("cleanup entry metadata was trusted")

        class SpecialScanner:
            def __enter__(self):
                return iter((UntrustedSpecialEntry(),))

            def __exit__(self, *_args):
                return False

        with (
            patch.object(
                transaction_module.os,
                "scandir",
                return_value=SpecialScanner(),
            ),
            patch.object(
                transaction_module,
                "_read_regular",
                side_effect=AssertionError(
                    "cleanup artifact content was opened"
                ),
            ),
        ):
            observed = transaction_module.inspect_terminal_cleanup_artifacts_for_resume_read_only(
                self.project
            )
        self.assertEqual(observed, "observed_or_scan_incomplete")

        with patch.object(
            transaction_module.os,
            "scandir",
            side_effect=OSError("synthetic bounded scan failure"),
        ):
            self.assertEqual(
                transaction_module.inspect_terminal_cleanup_artifacts_for_resume_read_only(
                    self.project
                ),
                "observed_or_scan_incomplete",
            )

    def test_regular_locator_parent_scan_stops_at_fixed_cap(self) -> None:
        parent = (
            self.project
            / ".zettel-kasten"
            / "private"
            / "version-updates"
        )
        parent.mkdir(parents=True)
        consumed: list[int] = []

        class CountingScanner:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def __iter__(self):
                return self

            def __next__(self):
                index = len(consumed)
                if index > transaction_module.MAX_TERMINAL_CLEANUP_SCAN_ENTRIES:
                    raise AssertionError("regular locator exceeded fixed cap")
                consumed.append(index)
                return SimpleNamespace(
                    name=f"benign-{index:04d}",
                    path=str(parent / f"benign-{index:04d}"),
                )

        with patch.object(
            transaction_module.os,
            "scandir",
            return_value=CountingScanner(),
        ):
            self.assert_code(
                "project_update_transaction_scan_incomplete",
                lambda: active_transaction_ref_for_resume_read_only(
                    self.project
                ),
            )
        self.assertEqual(
            len(consumed),
            transaction_module.MAX_TERMINAL_CLEANUP_SCAN_ENTRIES + 1,
        )

    def test_terminal_cleanup_scan_rejects_malformed_new_lock_not_unknown(
        self,
    ) -> None:
        metadata = self.project / ".zettel-kasten"
        metadata.mkdir()
        (metadata / "version-update.lock").write_bytes(b"not-a-lock")
        with self.assertRaises(ProjectUpdateTransactionError) as caught:
            transaction_module.inspect_terminal_cleanup_artifacts_for_resume_read_only(
                self.project
            )
        self.assertNotEqual(
            caught.exception.code,
            "project_update_transaction_not_found",
        )

    def test_terminal_cleanup_artifact_scan_rechecks_new_lock_authoritatively(
        self,
    ) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.3",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        staged_lock = lock_path.with_name("version-update.lock.staged")
        lock_path.rename(staged_lock)
        parent = reserved.transaction_root.parent
        original_scandir = transaction_module.os.scandir
        published: list[bool] = []

        class PublishingScanner:
            def __init__(self, path) -> None:
                self.scanner = original_scandir(path)

            def __enter__(self):
                staged_lock.rename(lock_path)
                published.append(True)
                return self.scanner.__enter__()

            def __exit__(self, *args):
                return self.scanner.__exit__(*args)

        def publish_during_parent_scan(path):
            self.assertEqual(Path(path), parent)
            return PublishingScanner(path)

        with patch.object(
            transaction_module.os,
            "scandir",
            side_effect=publish_during_parent_scan,
        ):
            observed = transaction_module.inspect_terminal_cleanup_artifacts_for_resume_read_only(
                self.project
            )

        self.assertEqual(observed, "active_lock_changed")
        self.assertEqual(published, [True])
        self.assertEqual(lock_path.read_bytes(), lock_bytes)

    def test_resume_ref_is_discovered_after_exact_lock_unlink_without_writes(self) -> None:
        transaction = self.create_transaction()
        lock_bytes, live = self.ready_forward(transaction)
        released = transaction.release_lock_exact(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
        )
        self.assertTrue(released.released)
        before = {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in self.project.rglob("*")
            if path.is_file()
        }

        discovered = active_transaction_ref_for_resume_read_only(self.project)

        self.assertEqual(discovered, transaction.transaction_ref)
        self.assertEqual(
            {
                path.relative_to(self.project).as_posix(): path.read_bytes()
                for path in self.project.rglob("*")
                if path.is_file()
            },
            before,
        )

    def test_resume_ref_scan_rechecks_new_live_lock_authoritatively_without_writes(
        self,
    ) -> None:
        stale = self.create_transaction(
            transaction_ref="update_11111111111111111111111111111111"
        )
        self.finish_forward(stale)
        original_inspect = transaction_module.inspect_prelock_orphans
        race: dict[str, object] = {}

        def inspect_then_acquire_new_lock(project_root):
            stale_snapshot = original_inspect(project_root)
            current = self.create_transaction(
                transaction_ref="update_22222222222222222222222222222222"
            )
            race["current"] = current
            race["files"] = {
                path.relative_to(self.project).as_posix(): path.read_bytes()
                for path in self.project.rglob("*")
                if path.is_file()
            }
            return stale_snapshot

        with patch.object(
            transaction_module,
            "inspect_prelock_orphans",
            side_effect=inspect_then_acquire_new_lock,
        ):
            discovered = active_transaction_ref_for_resume_read_only(
                self.project
            )

        current = race["current"]
        self.assertIsInstance(current, ProjectUpdateTransaction)
        self.assertEqual(discovered, current.transaction_ref)
        self.assertNotEqual(discovered, stale.transaction_ref)
        self.assertEqual(
            {
                path.relative_to(self.project).as_posix(): path.read_bytes()
                for path in self.project.rglob("*")
                if path.is_file()
            },
            race["files"],
        )

    def test_resume_ref_missing_before_unlock_tail_fails_without_writes(self) -> None:
        transaction = self.create_transaction()
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        lock_path.unlink()
        before = {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in self.project.rglob("*")
            if path.is_file()
        }

        self.assert_code(
            "project_update_transaction_not_found",
            lambda: active_transaction_ref_for_resume_read_only(self.project),
        )

        self.assertFalse(lock_path.exists())
        self.assertTrue(transaction.transaction_root.is_dir())
        self.assertEqual(
            {
                path.relative_to(self.project).as_posix(): path.read_bytes()
                for path in self.project.rglob("*")
                if path.is_file()
            },
            before,
        )

    def test_resume_ref_present_malformed_lock_is_authoritative(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        malformed = b'{"schema":"untrusted"}\n'
        lock_path.write_bytes(malformed)
        before = {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in self.project.rglob("*")
            if path.is_file()
        }

        self.assert_code(
            "project_update_transaction_lock_invalid",
            lambda: active_transaction_ref_for_resume_read_only(self.project),
        )

        self.assertEqual(lock_path.read_bytes(), malformed)
        self.assertEqual(
            {
                path.relative_to(self.project).as_posix(): path.read_bytes()
                for path in self.project.rglob("*")
                if path.is_file()
            },
            before,
        )

    def test_resume_ref_ambiguous_unlock_tails_fail_without_writes(self) -> None:
        first = self.create_transaction(
            transaction_ref="update_11111111111111111111111111111111"
        )
        self.finish_forward(first)
        second = self.create_transaction(
            transaction_ref="update_22222222222222222222222222222222"
        )
        self.finish_forward(second)
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        self.assertFalse(lock_path.exists())
        before = {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in self.project.rglob("*")
            if path.is_file()
        }

        self.assert_code(
            "project_update_transaction_invalid",
            lambda: active_transaction_ref_for_resume_read_only(self.project),
        )

        self.assertFalse(lock_path.exists())
        self.assertEqual(
            {
                path.relative_to(self.project).as_posix(): path.read_bytes()
                for path in self.project.rglob("*")
                if path.is_file()
            },
            before,
        )

    def test_private_intent_binds_components_preimages_bundle_and_public_projection(self) -> None:
        transaction = self.create_transaction()
        intent = transaction.intent
        self.assertEqual(intent.components[-1].role, "active_pin")
        self.assertEqual(
            {record.logical_key for record in intent.preimages}, set(self.pre_values)
        )
        self.assertGreater(intent.runtime_candidate.inventory_count, 2)
        self.assertEqual(
            intent.runtime_candidate.postimage_sha256,
            next(
                component.post_sha256
                for component in intent.components
                if component.role == "runtime"
            ),
        )
        bundle_path = transaction.runtime_bundle_path("main-wheel")
        self.assertEqual(bundle_path.read_bytes(), b"synthetic main wheel")
        self.assertEqual(
            json.loads(
                transaction.private_binding_bytes("git-runner-binding")
            )["binding_sha256"],
            self.bindings().bundle_sha256,
        )
        self.assertEqual(
            transaction.private_binding_bytes("static-receipt-postimage"),
            self.static_receipt(transaction.transaction_ref),
        )

        summary = transaction.public_summary()
        serialized = json.dumps(summary, sort_keys=True)
        intent_text = (self.transaction_root(transaction) / "intent.json").read_text(
            encoding="ascii"
        )
        synthetic_windows_private = (
            "C:" + chr(92) + "Users" + chr(92) + "Alice"
        )
        synthetic_private_url = "https" + "://private.example"
        for private in (
            str(self.project),
            "synthetic main wheel",
            "source-old",
            synthetic_windows_private,
            synthetic_private_url,
        ):
            self.assertNotIn(private, serialized)
            self.assertNotIn(private, intent_text)
        self.assertTrue(summary["preapproval_control_writes_completed"])
        self.assertFalse(summary["preapproval_domain_writes_completed"])
        self.assertTrue(summary["fetched_refs_may_change"])
        self.assertEqual(summary["lifecycle"], "active")

    def test_prelock_orphan_scanner_classifies_complete_and_partial_without_deleting(self) -> None:
        transaction = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.3",
            transaction_ref="update_0123456789abcdef0123456789abcdef",
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at="2026-08-23T00:00:00Z",
        )
        orphan = inspect_prelock_orphans(self.project)
        self.assertEqual(len(orphan), 1)
        self.assertEqual(orphan[0].classification, "reserved_lock_absent")
        root = self.transaction_root(transaction)
        self.assertTrue(root.is_dir())
        transaction.acquire_lock()
        locked = inspect_prelock_orphans(self.project)
        self.assertEqual(locked[0].classification, "reserved_locked_unsealed")

        partial_ref = "update_11111111111111111111111111111111"
        partial = root.parent / partial_ref
        partial.mkdir()
        (partial / "marker.json").write_bytes(b"partial")
        scan = {item.transaction_ref: item for item in inspect_prelock_orphans(self.project)}
        self.assertEqual(
            scan[partial_ref].classification, "manual_review_incomplete_or_unsafe"
        )
        self.assertEqual((partial / "marker.json").read_bytes(), b"partial")

    def test_reopen_after_process_loss_completes_monotonic_forward_state_machine(self) -> None:
        transaction = self.create_transaction()
        _lock, live = self.begin(transaction)
        reference = transaction.transaction_ref
        del transaction
        reopened = ProjectUpdateTransaction.open(self.project, reference)
        self.assertEqual(len(reopened.inspect().journal.verified_prefix), 2)
        for component in reopened.intent.components:
            reopened.append(
                phase=component.role,
                stage="intent",
                component_ref=component.component_ref,
                live_component_sha256=live,
            )
            runtime_cleanup = None
            if component.role == "runtime":
                runtime_cleanup = self.runtime_cleanup_terminal_evidence(
                    reopened
                )
                self.remove_sealed_candidate(reopened)
            live[component.component_ref] = component.post_sha256
            reopened.append(
                phase=component.role,
                stage="verified",
                component_ref=component.component_ref,
                live_component_sha256=live,
                runtime_cleanup_terminal_evidence=runtime_cleanup,
            )
        reopened.append(
            phase="domain_committed", stage="verified", live_component_sha256=live
        )
        reopened.append(
            phase="claim_succeeded",
            stage="verified",
            live_component_sha256=live,
            claim_receipt_sha256=digest("claim-receipt"),
            claim_mac_sha256=digest("claim-mac"),
            claim_evidence=self.claim_evidence(
                reopened,
                approval_reference=digest("main-approval-reference"),
                claim_receipt=digest("claim-receipt"),
                claim_mac=digest("claim-mac"),
            ),
        )
        reopened.append(
            phase="ready_to_unlock", stage="verified", live_component_sha256=live
        )
        release = reopened.release_lock_exact(
            expected_lock_bytes=reopened.lock_bytes(),
            live_component_sha256=live,
        )
        reopened.append(
            phase="lock_released",
            stage="verified",
            live_component_sha256=live,
            lock_release_result=release,
        )
        reopened.append(
            phase="completed", stage="verified", live_component_sha256=live
        )
        inspection = reopened.inspect()
        self.assertTrue(inspection.terminal)
        self.assertEqual(reopened.public_summary()["lifecycle"], "terminal")

    def test_state_machine_rejects_completed_first_and_verified_without_intent(self) -> None:
        transaction = self.create_transaction()
        self.activate(transaction)
        pre = self.live_pre()
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: transaction.append(
                phase="completed", stage="verified", live_component_sha256=pre
            ),
        )
        transaction.append(
            phase="lock_backlinked", stage="verified", live_component_sha256=pre
        )
        transaction.append(
            phase="approval_bound",
            stage="verified",
            live_component_sha256=pre,
            approval_reference_sha256=digest("main-approval-reference"),
            approval_mac_sha256=digest("main-approval-mac"),
        )
        first = transaction.intent.components[0]
        post_too_early = dict(pre)
        post_too_early[first.component_ref] = first.post_sha256
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: transaction.append(
                phase=first.role,
                stage="verified",
                component_ref=first.component_ref,
                live_component_sha256=post_too_early,
            ),
        )

    def test_active_pin_must_be_last_and_old_value_preservation_cannot_be_disabled(self) -> None:
        components = list(self.components())
        bad = list(components)
        active = bad.pop()
        bad.insert(0, active)
        bad = [
            ProjectUpdateComponent(
                component_ref=item.component_ref,
                role=item.role,
                sequence=index,
                logical_target=item.logical_target,
                pre_sha256=item.pre_sha256,
                post_sha256=item.post_sha256,
                preimage_key=item.preimage_key,
            )
            for index, item in enumerate(bad, start=1)
        ]
        self.assert_code(
            "project_update_transaction_intent_invalid",
            lambda: ProjectUpdateTransaction.create(
                self.project,
                project_identity_sha256=digest("project"),
                requested_target_tag="v0.4.3",
                bindings=self.bindings(),
                components=bad,
                preimages=dict(self.pre_values),
                runtime_bundle={"main-wheel": b"wheel"},
                static_receipt_postimage=self.post_values["receipt"],
            ),
        )
        item = components[0]
        self.assert_code(
            "project_update_transaction_intent_invalid",
            lambda: ProjectUpdateComponent(
                component_ref=item.component_ref,
                role=item.role,
                sequence=item.sequence,
                logical_target=item.logical_target,
                pre_sha256=item.pre_sha256,
                post_sha256=item.post_sha256,
                preimage_key=item.preimage_key,
                preserve_old_value=False,
            ),
        )

    def test_every_append_detects_same_bytes_lock_replacement_by_identity(self) -> None:
        transaction = self.create_transaction()
        lock_bytes = self.activate(transaction)
        transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=self.live_pre(),
        )
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        replacement = lock_path.with_name("replacement.lock")
        replacement.write_bytes(lock_bytes)
        replacement.replace(lock_path)
        self.assert_code(
            "project_update_transaction_lock_invalid",
            lambda: transaction.append(
                phase="approval_bound",
                stage="verified",
                live_component_sha256=self.live_pre(),
                approval_reference_sha256=digest("main-approval-reference"),
                approval_mac_sha256=digest("main-approval-mac"),
            ),
        )

    def test_torn_tail_exposes_verified_prefix_and_blocks_resume_without_hiding_damage(
        self,
    ) -> None:
        transaction = self.create_transaction()
        self.begin(transaction)
        journal = self.transaction_root(transaction) / "checkpoints.jsonl"
        durable = journal.read_bytes()
        journal.write_bytes(durable + b'{"schema":"torn"')
        reopened = ProjectUpdateTransaction.open(
            self.project, transaction.transaction_ref
        )
        inspection = reopened.inspect()
        self.assertEqual(inspection.journal.state, "tail_torn")
        self.assertEqual(len(inspection.journal.verified_prefix), 2)
        self.assertEqual(
            inspection.journal.unverified_tail_sha256,
            sha256_bytes(b'{"schema":"torn"'),
        )
        self.assertGreater(inspection.journal.unverified_tail_size, 0)
        self.assertEqual(
            reopened.public_summary()["lifecycle"],
            "manual_review_journal_degraded",
        )
        first = reopened.intent.components[0]
        self.assert_code(
            "project_update_transaction_journal_degraded",
            lambda: reopened.append(
                phase=first.role,
                stage="intent",
                component_ref=first.component_ref,
                live_component_sha256=self.live_pre(),
            ),
        )
        self.assertEqual(journal.read_bytes(), durable + b'{"schema":"torn"')

    def test_corrupt_middle_and_duplicate_key_rows_are_contentfully_preserved(self) -> None:
        for mode in ("middle", "duplicate", "noncanonical"):
            with self.subTest(mode=mode):
                lock_path = self.project / ".zettel-kasten" / "version-update.lock"
                if lock_path.exists():
                    lock_path.unlink()
                if mode == "middle":
                    transaction = self.create_transaction()
                else:
                    transaction = self.create_transaction(
                        transaction_ref=(
                            "update_22222222222222222222222222222222"
                            if mode == "duplicate"
                            else "update_44444444444444444444444444444444"
                        )
                    )
                self.begin(transaction)
                journal = self.transaction_root(transaction) / "checkpoints.jsonl"
                original = journal.read_bytes()
                lines = original.splitlines()
                if mode == "middle":
                    first = json.loads(lines[0])
                    first["observed_state_sha256"] = digest("tampered")
                    damaged = canonical_json_bytes(first) + b"\n" + lines[1] + b"\n"
                elif mode == "duplicate":
                    damaged = original.replace(
                        b"{",
                        b'{"schema":"wom-kit/project-update-transaction-checkpoint/v0.4.3",',
                        1,
                    )
                else:
                    damaged = original.replace(b'"seq":1', b'"seq": 1', 1)
                journal.write_bytes(damaged)
                reopened = ProjectUpdateTransaction.open(
                    self.project, transaction.transaction_ref
                )
                report = reopened.inspect().journal
                self.assertEqual(report.state, "corrupt")
                self.assertIsNotNone(report.unverified_tail_sha256)
                self.assertEqual(journal.read_bytes(), damaged)

    def test_durable_component_expectations_classify_pre_mixed_post_unknown(self) -> None:
        transaction = self.create_transaction()
        self.assertEqual(
            transaction.classify_live_components(self.live_pre()).overall,
            "prewrite_exact",
        )
        mixed = self.live_pre()
        mixed["source"] = transaction.intent.components[0].post_sha256
        classification = transaction.classify_live_components(mixed)
        self.assertEqual(classification.overall, "mixed_exact")
        self.assertFalse(hasattr(classification, "action"))
        self.assertEqual(
            transaction.classify_live_components(self.live_post()).overall,
            "complete_exact",
        )
        unknown = self.live_post()
        unknown["launcher"] = digest("alien")
        self.assertEqual(
            transaction.classify_live_components(unknown).overall, "unknown"
        )
        neutral = ComponentExpectation("neutral", digest("same"), digest("same"))
        self.assertEqual(
            classify_components((neutral,), {"neutral": digest("same")}).overall,
            "prewrite_exact",
        )
        absent = ComponentExpectation(
            "absent", ABSENT_COMPONENT_SHA256, digest("created")
        )
        self.assertEqual(
            classify_components(
                (absent,), {"absent": ABSENT_COMPONENT_SHA256}
            ).overall,
            "prewrite_exact",
        )

    def test_explicit_rollback_authority_reverts_all_components_in_reverse_order(self) -> None:
        transaction = self.create_transaction()
        lock_bytes, live = self.begin(transaction)
        first = transaction.intent.components[0]
        transaction.append(
            phase=first.role,
            stage="intent",
            component_ref=first.component_ref,
            live_component_sha256=live,
        )
        live[first.component_ref] = first.post_sha256
        transaction.append(
            phase=first.role,
            stage="verified",
            component_ref=first.component_ref,
            live_component_sha256=live,
        )
        self.assertEqual(
            transaction.classify_live_components(live).overall, "mixed_exact"
        )
        transaction.append(
            phase="rollback_authorized",
            stage="verified",
            live_component_sha256=live,
            approval_reference_sha256=digest("rollback-approval-reference"),
            approval_mac_sha256=digest("rollback-approval-mac"),
        )
        for component in reversed(transaction.intent.components):
            transaction.append(
                phase="rollback_effect",
                stage="intent",
                component_ref=component.component_ref,
                live_component_sha256=live,
            )
            live[component.component_ref] = component.pre_sha256
            transaction.append(
                phase="rollback_effect",
                stage="verified",
                component_ref=component.component_ref,
                live_component_sha256=live,
            )
        transaction.append(
            phase="rollback_verified",
            stage="verified",
            live_component_sha256=live,
        )
        transaction.append(
            phase="claim_succeeded",
            stage="verified",
            live_component_sha256=live,
            claim_receipt_sha256=digest("rollback-claim-receipt"),
            claim_mac_sha256=digest("rollback-claim-mac"),
            claim_evidence=self.claim_evidence(
                transaction,
                approval_reference=digest("rollback-approval-reference"),
                claim_receipt=digest("rollback-claim-receipt"),
                claim_mac=digest("rollback-claim-mac"),
            ),
        )
        transaction.append(
            phase="ready_to_unlock",
            stage="verified",
            live_component_sha256=live,
        )
        release = transaction.release_lock_exact(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
        )
        transaction.append(
            phase="lock_released",
            stage="verified",
            live_component_sha256=live,
            lock_release_result=release,
        )
        transaction.append(
            phase="completed", stage="verified", live_component_sha256=live
        )
        self.assertTrue(transaction.inspect().terminal)
        self.assertEqual(
            transaction.classify_live_components(live).overall, "prewrite_exact"
        )

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_cleanup_refuses_nonterminal_then_terminal_cleanup_is_exact_and_idempotent(
        self,
    ) -> None:
        transaction = self.create_transaction()
        self.activate(transaction)
        root = self.transaction_root(transaction)
        self.assertFalse(
            transaction.exact_cleanup(cleanup_authority_sha256=digest("cleanup"))
        )
        self.assertTrue(root.is_dir())

        # Start a separate transaction because the first intentionally retains
        # the live lock and its nonterminal evidence.
        (self.project / ".zettel-kasten" / "version-update.lock").unlink()
        terminal = self.create_transaction(
            transaction_ref="update_33333333333333333333333333333333"
        )
        self.finish_forward(terminal)
        terminal_root = self.transaction_root(terminal)
        self.assertTrue(
            terminal.exact_cleanup(cleanup_authority_sha256=digest("cleanup-terminal"))
        )
        self.assertFalse(terminal_root.exists())
        self.assertTrue(
            terminal.exact_cleanup(cleanup_authority_sha256=digest("cleanup-terminal"))
        )

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_partial_cleanup_hard_exit_is_resumable_from_exact_tombstone(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        authority = digest("cleanup-authority")
        original_delete = transaction_module._delete_exact_cleanup_file
        deleted = {"count": 0}

        def fail_after_one(project: Path, path: Path, snapshot) -> None:
            deleted["count"] += 1
            if deleted["count"] == 2:
                raise OSError("simulated hard-exit boundary")
            original_delete(project, path, snapshot)

        with patch.object(
            transaction_module,
            "_delete_exact_cleanup_file",
            side_effect=fail_after_one,
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        tombstone = root.parent / f".cleanup_{transaction.transaction_ref}"
        self.assertFalse(root.exists())
        self.assertTrue(tombstone.is_dir())
        self.assertFalse(
            ProjectUpdateTransaction.resume_cleanup(
                self.project,
                transaction.transaction_ref,
                cleanup_authority_sha256=digest("wrong-authority"),
            )
        )
        self.assertTrue(tombstone.is_dir())
        self.assertTrue(
            ProjectUpdateTransaction.resume_cleanup(
                self.project,
                transaction.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        self.assert_code(
            "project_update_transaction_exists",
            lambda: self.create_transaction(
                transaction_ref=transaction.transaction_ref
            ),
        )
        self.assertFalse(tombstone.exists())
        proof = root.parent / f".cleanup-proof_{transaction.transaction_ref}.json"
        self.assertTrue(proof.is_file())
        self.assertTrue(
            ProjectUpdateTransaction.resume_cleanup(
                self.project,
                transaction.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_process_exit_after_exact_child_delete_resumes(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("cleanup-process-exit-child")
        worker = "\n".join(
            (
                "import os, sys",
                "from pathlib import Path",
                "from wom_kit import project_update_transaction as module",
                "transaction = module.ProjectUpdateTransaction.open(Path(sys.argv[1]), sys.argv[2])",
                "real_delete = module._delete_exact_cleanup_file",
                "def crash(project, path, snapshot):",
                "    real_delete(project, path, snapshot)",
                "    os._exit(81)",
                "module._delete_exact_cleanup_file = crash",
                "transaction.exact_cleanup(cleanup_authority_sha256=sys.argv[3])",
                "raise SystemExit(99)",
            )
        )
        self.run_hard_exit_worker(
            worker,
            str(self.project),
            transaction.transaction_ref,
            authority,
            expected_returncode=81,
        )
        self.assertTrue(
            ProjectUpdateTransaction.resume_cleanup(
                self.project,
                transaction.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_process_exit_after_identity_plan_visibility_resumes(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("cleanup-process-exit-plan-visible")
        worker = "\n".join(
            (
                "import os, sys",
                "from pathlib import Path",
                "from wom_kit import project_update_transaction as module",
                "transaction = module.ProjectUpdateTransaction.open(Path(sys.argv[1]), sys.argv[2])",
                "real_durable = module._require_directory_durable",
                "def crash(path):",
                "    if path == transaction.transaction_root and (path / module.CLEANUP_PLAN_NAME).exists():",
                "        os._exit(84)",
                "    return real_durable(path)",
                "module._require_directory_durable = crash",
                "transaction.exact_cleanup(cleanup_authority_sha256=sys.argv[3])",
                "raise SystemExit(99)",
            )
        )
        self.run_hard_exit_worker(
            worker,
            str(self.project),
            transaction.transaction_ref,
            authority,
            expected_returncode=84,
        )
        current_plan = transaction.transaction_root / CLEANUP_PLAN_NAME
        self.assertTrue(current_plan.is_file())
        reopened = ProjectUpdateTransaction.open(
            self.project,
            transaction.transaction_ref,
        )
        self.assertTrue(
            reopened.exact_cleanup(cleanup_authority_sha256=authority)
        )

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_process_exit_after_plan_to_proof_move_resumes(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("cleanup-process-exit-plan-proof")
        with patch.object(
            ProjectUpdateTransaction,
            "_resume_cleanup_paths",
            return_value=False,
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        worker = "\n".join(
            (
                "import os, sys",
                "from pathlib import Path",
                "from wom_kit import project_update_transaction as module",
                "real_move = module._atomic_move_file_no_replace",
                "def crash(source, destination):",
                "    real_move(source, destination)",
                "    os._exit(82)",
                "module._atomic_move_file_no_replace = crash",
                "module.ProjectUpdateTransaction.resume_cleanup(Path(sys.argv[1]), sys.argv[2], cleanup_authority_sha256=sys.argv[3])",
                "raise SystemExit(99)",
            )
        )
        self.run_hard_exit_worker(
            worker,
            str(self.project),
            transaction.transaction_ref,
            authority,
            expected_returncode=82,
        )
        self.assertTrue(
            ProjectUpdateTransaction.resume_cleanup(
                self.project,
                transaction.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_process_exit_after_duplicate_link_reconciliation_resumes(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("cleanup-process-exit-duplicate-link")
        with patch.object(
            ProjectUpdateTransaction,
            "_resume_cleanup_paths",
            return_value=False,
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        parent = self.transaction_root(transaction).parent
        proof = parent / f".cleanup-proof_{transaction.transaction_ref}.json"
        tombstone = parent / f".cleanup_{transaction.transaction_ref}"
        real_move = transaction_module._atomic_move_file_no_replace

        def leave_duplicate(source: Path, destination: Path) -> None:
            real_move(source, destination)
            os.link(destination, source)
            raise RuntimeError("synthetic duplicate-link crash state")

        with patch.object(
            transaction_module,
            "_atomic_move_file_no_replace",
            side_effect=leave_duplicate,
        ):
            with self.assertRaisesRegex(RuntimeError, "duplicate-link"):
                ProjectUpdateTransaction.resume_cleanup(
                    self.project,
                    transaction.transaction_ref,
                    cleanup_authority_sha256=authority,
                )
        self.assertEqual(proof.stat().st_nlink, 2)
        self.assertEqual((tombstone / CLEANUP_PLAN_NAME).stat().st_nlink, 2)
        worker = "\n".join(
            (
                "import os, sys",
                "from pathlib import Path",
                "from wom_kit import project_update_transaction as module",
                "real_unlink = module._unlink_exact_cleanup_plan_duplicate_windows",
                "def crash(*args, **kwargs):",
                "    real_unlink(*args, **kwargs)",
                "    os._exit(83)",
                "module._unlink_exact_cleanup_plan_duplicate_windows = crash",
                "module.ProjectUpdateTransaction.resume_cleanup(Path(sys.argv[1]), sys.argv[2], cleanup_authority_sha256=sys.argv[3])",
                "raise SystemExit(99)",
            )
        )
        self.run_hard_exit_worker(
            worker,
            str(self.project),
            transaction.transaction_ref,
            authority,
            expected_returncode=83,
        )
        self.assertTrue(
            ProjectUpdateTransaction.resume_cleanup(
                self.project,
                transaction.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_cleanup_proof_destination_race_never_replaces_foreign_file(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        authority = digest("cleanup-authority-race")
        tombstone = root.parent / f".cleanup_{transaction.transaction_ref}"
        proof = root.parent / f".cleanup-proof_{transaction.transaction_ref}.json"
        foreign = b"foreign proof race occupant\n"
        real_move = transaction_module._atomic_move_file_no_replace

        def inject_destination(source: Path, destination: Path) -> None:
            self.assertEqual(destination, proof)
            destination.write_bytes(foreign)
            real_move(source, destination)

        with patch.object(
            transaction_module,
            "_atomic_move_file_no_replace",
            side_effect=inject_destination,
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )

        self.assertFalse(root.exists())
        self.assertTrue(tombstone.is_dir())
        self.assertTrue((tombstone / CLEANUP_PLAN_NAME).is_file())
        self.assertEqual(proof.read_bytes(), foreign)
        self.assertFalse(
            ProjectUpdateTransaction.resume_cleanup(
                self.project,
                transaction.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        self.assertEqual(proof.read_bytes(), foreign)
        self.assertTrue((tombstone / CLEANUP_PLAN_NAME).is_file())

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_cleanup_proof_flushes_destination_before_source_directory(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        authority = digest("cleanup-authority-flush-order")
        parent = root.parent
        tombstone = parent / f".cleanup_{transaction.transaction_ref}"
        real_move = transaction_module._atomic_move_file_no_replace
        real_fsync = transaction_module._fsync_directory
        proof_moved = False
        post_move_flushes: list[Path] = []

        def observe_move(source: Path, destination: Path) -> None:
            nonlocal proof_moved
            real_move(source, destination)
            proof_moved = True

        def observe_fsync(path: Path):
            if proof_moved:
                post_move_flushes.append(path)
            return real_fsync(path)

        with patch.object(
            transaction_module,
            "_atomic_move_file_no_replace",
            side_effect=observe_move,
        ), patch.object(
            transaction_module,
            "_fsync_directory",
            side_effect=observe_fsync,
        ):
            self.assertTrue(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )

        self.assertGreaterEqual(len(post_move_flushes), 3)
        self.assertEqual(post_move_flushes[:3], [parent, tombstone, parent])

    def test_atomic_move_refuses_parent_swap_without_moving_foreign_source(
        self,
    ) -> None:
        parent = self.project / "move-parent"
        parent.mkdir()
        source = parent / "active.json"
        destination = parent / "display-pending.json"
        source.write_bytes(b"validated-source")
        renamed_parent = self.project / "move-parent-original"
        real_safe_directory = transaction_module._safe_directory
        calls = {"count": 0}

        def swap_after_validation(path: Path, *, within: Path):
            result = real_safe_directory(path, within=within)
            if path == parent:
                calls["count"] += 1
                if calls["count"] == 2:
                    parent.rename(renamed_parent)
                    parent.mkdir()
                    (parent / source.name).write_bytes(b"foreign-source")
            return result

        with patch.object(
            transaction_module,
            "_safe_directory",
            side_effect=swap_after_validation,
        ):
            with self.assertRaises(
                (OSError, ProjectUpdateTransactionError)
            ):
                transaction_module._atomic_move_file_no_replace(
                    source,
                    destination,
                )

        self.assertEqual(
            (renamed_parent / source.name).read_bytes(),
            b"validated-source",
        )
        self.assertEqual(source.read_bytes(), b"foreign-source")
        self.assertFalse(destination.exists())

    def test_cleanup_refuses_byte_identical_transaction_directory_swap(
        self,
    ) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        parent = root.parent
        tombstone = parent / f".cleanup_{transaction.transaction_ref}"
        preserved = parent / ".validated-transaction-preserved"
        real_move = transaction_module._atomic_move_directory_no_replace
        identities: dict[str, tuple[int, int]] = {}

        def swap_clone_then_move(source: Path, destination: Path) -> None:
            before = source.stat()
            identities["validated"] = (before.st_dev, before.st_ino)
            source.rename(preserved)
            shutil.copytree(preserved, source)
            clone = source.stat()
            identities["clone"] = (clone.st_dev, clone.st_ino)
            real_move(source, destination)

        with patch.object(
            transaction_module,
            "_atomic_move_directory_no_replace",
            side_effect=swap_clone_then_move,
        ):
            self.assertFalse(
                transaction.exact_cleanup(
                    cleanup_authority_sha256=digest("cleanup-root-swap")
                )
            )

        self.assertNotEqual(identities["validated"], identities["clone"])
        self.assertEqual(
            (preserved.stat().st_dev, preserved.stat().st_ino),
            identities["validated"],
        )
        self.assertEqual(
            (tombstone.stat().st_dev, tombstone.stat().st_ino),
            identities["clone"],
        )
        self.assertTrue((preserved / "intent.json").is_file())
        self.assertTrue((tombstone / CLEANUP_PLAN_NAME).is_file())
        self.assertFalse(
            (parent / f".cleanup-proof_{transaction.transaction_ref}.json")
            .exists()
        )

    def test_cleanup_refuses_tombstone_clone_before_immediate_resume(
        self,
    ) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        parent = self.transaction_root(transaction).parent
        tombstone = parent / f".cleanup_{transaction.transaction_ref}"
        preserved = parent / ".verified-tombstone-preserved"
        real_resume = ProjectUpdateTransaction._resume_cleanup_paths
        swapped = {"done": False}

        def swap_then_resume(project: Path, ref: str, authority: str) -> bool:
            tombstone.rename(preserved)
            shutil.copytree(preserved, tombstone)
            swapped["done"] = True
            return real_resume(project, ref, authority)

        with patch.object(
            ProjectUpdateTransaction,
            "_resume_cleanup_paths",
            side_effect=swap_then_resume,
        ):
            self.assertFalse(
                transaction.exact_cleanup(
                    cleanup_authority_sha256=digest(
                        "cleanup-tombstone-immediate-swap"
                    )
                )
            )

        self.assertTrue(swapped["done"])
        self.assertTrue((preserved / CLEANUP_PLAN_NAME).is_file())
        self.assertTrue((tombstone / CLEANUP_PLAN_NAME).is_file())
        self.assertNotEqual(preserved.stat().st_ino, tombstone.stat().st_ino)

    def test_cleanup_restart_refuses_byte_identical_tombstone_clone(
        self,
    ) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("cleanup-tombstone-restart-swap")
        with patch.object(
            ProjectUpdateTransaction,
            "_resume_cleanup_paths",
            return_value=False,
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        parent = self.transaction_root(transaction).parent
        tombstone = parent / f".cleanup_{transaction.transaction_ref}"
        preserved = parent / ".restart-tombstone-preserved"
        tombstone.rename(preserved)
        shutil.copytree(preserved, tombstone)

        self.assertFalse(
            ProjectUpdateTransaction.resume_cleanup(
                self.project,
                transaction.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )

        self.assertTrue((preserved / CLEANUP_PLAN_NAME).is_file())
        self.assertTrue((tombstone / CLEANUP_PLAN_NAME).is_file())
        self.assertNotEqual(preserved.stat().st_ino, tombstone.stat().st_ino)
        self.assertFalse(
            (parent / f".cleanup-proof_{transaction.transaction_ref}.json")
            .exists()
        )

    def test_current_cleanup_plan_requires_platform_birthtime_shape(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("cleanup-platform-birthtime-shape")
        with patch.object(
            ProjectUpdateTransaction,
            "_resume_cleanup_paths",
            return_value=False,
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        parent = self.transaction_root(transaction).parent
        tombstone = parent / f".cleanup_{transaction.transaction_ref}"
        plan = json.loads(
            (tombstone / CLEANUP_PLAN_NAME).read_text(encoding="ascii")
        )
        identity = plan["transaction_root_identity"]
        self.assertEqual(
            type(identity["birthtime_ns"]) is int,
            os.name == "nt",
        )
        identity["birthtime_ns"] = None if os.name == "nt" else 1

        with self.assertRaises(ProjectUpdateTransactionError) as captured:
            ProjectUpdateTransaction._validate_cleanup_plan_document(
                plan,
                transaction.transaction_ref,
                authority,
            )

        self.assertEqual(
            captured.exception.code,
            "project_update_transaction_cleanup_refused",
        )

    @unittest.skipUnless(os.name == "nt", "Windows directory generation binding")
    def test_cleanup_proof_refuses_recreated_tombstone_with_reused_inode(
        self,
    ) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("cleanup-tombstone-reused-inode")
        self.assertTrue(
            transaction.exact_cleanup(cleanup_authority_sha256=authority)
        )
        parent = self.transaction_root(transaction).parent
        tombstone = parent / f".cleanup_{transaction.transaction_ref}"
        proof = parent / f".cleanup-proof_{transaction.transaction_ref}.json"
        proof_before = proof.read_bytes()
        plan = json.loads(proof_before)
        planned = plan["transaction_root_identity"]
        self.assertGreater(planned["birthtime_ns"], 0)

        # Model delayed inode reuse: the pathname now names a different empty
        # directory whose device/inode happen to match the old plan. Windows
        # creation time remains the stable generation discriminator.
        tombstone.mkdir()
        recreated = tombstone.stat()
        real_identity = transaction_module._cleanup_directory_identity

        def reused_inode_generation(info: os.stat_result):
            if (
                int(info.st_dev),
                int(info.st_ino),
            ) == (int(recreated.st_dev), int(recreated.st_ino)):
                return (
                    planned["device"],
                    planned["inode"],
                    planned["birthtime_ns"] + 1,
                )
            return real_identity(info)

        with patch.object(
            transaction_module,
            "_cleanup_directory_identity",
            side_effect=reused_inode_generation,
        ), patch.object(
            transaction_module,
            "_delete_exact_cleanup_directory",
            side_effect=AssertionError(
                "generation-mismatched tombstone reached deletion"
            ),
        ) as exact_delete:
            self.assertFalse(
                ProjectUpdateTransaction.resume_cleanup(
                    self.project,
                    transaction.transaction_ref,
                    cleanup_authority_sha256=authority,
                )
            )

        exact_delete.assert_not_called()
        self.assertTrue(tombstone.is_dir())
        self.assertEqual(list(tombstone.iterdir()), [])
        self.assertEqual(proof.read_bytes(), proof_before)

    def test_cleanup_descendant_replacement_after_snapshot_survives(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        authority = digest("cleanup-descendant-race")
        with patch.object(
            ProjectUpdateTransaction,
            "_resume_cleanup_paths",
            return_value=False,
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        tombstone = root.parent / f".cleanup_{transaction.transaction_ref}"
        real_snapshot = ProjectUpdateTransaction._cleanup_descendant_snapshot
        injected: dict[str, Path | None] = {"path": None}
        foreign = b"FOREIGN-BYTES-CREATED-AFTER-VALIDATION"

        def replace_after_snapshot(path: Path, *, exclude: set[str]):
            result = real_snapshot(path, exclude=exclude)
            if injected["path"] is None and result[0]:
                relative = next(iter(result[0]))
                victim = path / PurePosixPath(relative)
                victim.unlink()
                victim.write_bytes(foreign)
                injected["path"] = victim
            return result

        with patch.object(
            ProjectUpdateTransaction,
            "_cleanup_descendant_snapshot",
            side_effect=replace_after_snapshot,
        ):
            self.assertFalse(
                ProjectUpdateTransaction.resume_cleanup(
                    self.project,
                    transaction.transaction_ref,
                    cleanup_authority_sha256=authority,
                )
            )

        victim = injected["path"]
        self.assertIsInstance(victim, Path)
        assert isinstance(victim, Path)
        self.assertEqual(victim.read_bytes(), foreign)
        self.assertTrue(tombstone.is_dir())

    @unittest.skipUnless(os.name == "nt", "Windows exact-link recovery")
    def test_cleanup_proof_duplicate_hardlink_crash_state_is_reconciled(
        self,
    ) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("cleanup-proof-duplicate")
        with patch.object(
            ProjectUpdateTransaction,
            "_resume_cleanup_paths",
            return_value=False,
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        parent = self.transaction_root(transaction).parent
        tombstone = parent / f".cleanup_{transaction.transaction_ref}"
        proof = parent / f".cleanup-proof_{transaction.transaction_ref}.json"
        real_move = transaction_module._atomic_move_file_no_replace

        def leave_duplicate(source: Path, destination: Path) -> None:
            real_move(source, destination)
            os.link(destination, source)
            raise RuntimeError("synthetic duplicate-link crash state")

        with patch.object(
            transaction_module,
            "_atomic_move_file_no_replace",
            side_effect=leave_duplicate,
        ):
            with self.assertRaisesRegex(RuntimeError, "duplicate-link"):
                ProjectUpdateTransaction.resume_cleanup(
                    self.project,
                    transaction.transaction_ref,
                    cleanup_authority_sha256=authority,
                )
        duplicate = tombstone / CLEANUP_PLAN_NAME
        self.assertEqual(proof.stat().st_nlink, 2)

        self.assertTrue(
            ProjectUpdateTransaction.resume_cleanup(
                self.project,
                transaction.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )

        self.assertFalse(tombstone.exists())
        self.assertTrue(proof.is_file())
        self.assertEqual(proof.stat().st_nlink, 1)

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_cleanup_proof_equal_but_distinct_duplicate_is_refused(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("cleanup-proof-distinct-copy")
        with patch.object(
            ProjectUpdateTransaction,
            "_resume_cleanup_paths",
            return_value=False,
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        parent = self.transaction_root(transaction).parent
        tombstone = parent / f".cleanup_{transaction.transaction_ref}"
        proof = parent / f".cleanup-proof_{transaction.transaction_ref}.json"
        duplicate = tombstone / CLEANUP_PLAN_NAME

        def copy_without_moving(source: Path, destination: Path) -> None:
            destination.write_bytes(source.read_bytes())

        with patch.object(
            transaction_module,
            "_atomic_move_file_no_replace",
            side_effect=copy_without_moving,
        ):
            self.assertFalse(
                ProjectUpdateTransaction.resume_cleanup(
                    self.project,
                    transaction.transaction_ref,
                    cleanup_authority_sha256=authority,
                )
            )

        self.assertFalse(
            ProjectUpdateTransaction.resume_cleanup(
                self.project,
                transaction.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        self.assertTrue(tombstone.is_dir())
        self.assertEqual(duplicate.read_bytes(), proof.read_bytes())
        self.assertNotEqual(duplicate.stat().st_ino, proof.stat().st_ino)

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_cleanup_plan_source_replacement_is_not_attributed_as_proof(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        authority = digest("cleanup-plan-source-race")
        with patch.object(
            ProjectUpdateTransaction,
            "_resume_cleanup_paths",
            return_value=False,
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        parent = root.parent
        tombstone = parent / f".cleanup_{transaction.transaction_ref}"
        proof = parent / f".cleanup-proof_{transaction.transaction_ref}.json"
        foreign = b"foreign plan source replacement\n"
        real_move = transaction_module._atomic_move_file_no_replace

        def replace_source_then_move(source: Path, destination: Path) -> None:
            source.unlink()
            source.write_bytes(foreign)
            real_move(source, destination)

        with patch.object(
            transaction_module,
            "_atomic_move_file_no_replace",
            side_effect=replace_source_then_move,
        ):
            self.assertFalse(
                ProjectUpdateTransaction.resume_cleanup(
                    self.project,
                    transaction.transaction_ref,
                    cleanup_authority_sha256=authority,
                )
            )

        self.assertEqual(proof.read_bytes(), foreign)
        self.assertTrue(tombstone.is_dir())

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_cleanup_existing_proof_replacement_never_returns_success(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("cleanup-proof-replacement")
        self.assertTrue(
            transaction.exact_cleanup(cleanup_authority_sha256=authority)
        )
        parent = self.transaction_root(transaction).parent
        proof = parent / f".cleanup-proof_{transaction.transaction_ref}.json"
        foreign = b"foreign proof replacement\n"
        real_read = transaction_module._read_cleanup_linked_regular
        reads = {"count": 0}

        def replace_after_first_read(project: Path, path: Path, *, maximum: int):
            result = real_read(project, path, maximum=maximum)
            reads["count"] += 1
            if reads["count"] == 1:
                path.unlink()
                path.write_bytes(foreign)
            return result

        with patch.object(
            transaction_module,
            "_read_cleanup_linked_regular",
            side_effect=replace_after_first_read,
        ):
            self.assertFalse(
                ProjectUpdateTransaction.resume_cleanup(
                    self.project,
                    transaction.transaction_ref,
                    cleanup_authority_sha256=authority,
                )
            )

        self.assertEqual(proof.read_bytes(), foreign)

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_cleanup_existing_proof_refuses_recreated_original(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("cleanup-proof-original-race")
        self.assertTrue(
            transaction.exact_cleanup(cleanup_authority_sha256=authority)
        )
        original = self.transaction_root(transaction)
        sentinel = original / "foreign.bin"
        real_read = transaction_module._read_cleanup_linked_regular
        reads = {"count": 0}

        def recreate_after_final_read(
            project: Path,
            path: Path,
            *,
            maximum: int,
        ):
            result = real_read(project, path, maximum=maximum)
            reads["count"] += 1
            if reads["count"] == 2:
                original.mkdir()
                sentinel.write_bytes(b"foreign original race occupant")
            return result

        with patch.object(
            transaction_module,
            "_read_cleanup_linked_regular",
            side_effect=recreate_after_final_read,
        ):
            self.assertFalse(
                ProjectUpdateTransaction.resume_cleanup(
                    self.project,
                    transaction.transaction_ref,
                    cleanup_authority_sha256=authority,
                )
            )

        self.assertEqual(sentinel.read_bytes(), b"foreign original race occupant")

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_cleanup_final_move_refuses_recreated_original(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("cleanup-final-original-race")
        with patch.object(
            ProjectUpdateTransaction,
            "_resume_cleanup_paths",
            return_value=False,
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        original = self.transaction_root(transaction)
        sentinel = original / "foreign.bin"
        real_read = transaction_module._read_cleanup_linked_regular
        reads = {"count": 0}

        def recreate_after_final_read(
            project: Path,
            path: Path,
            *,
            maximum: int,
        ):
            result = real_read(project, path, maximum=maximum)
            reads["count"] += 1
            if reads["count"] == 2:
                original.mkdir()
                sentinel.write_bytes(b"foreign original race occupant")
            return result

        with patch.object(
            transaction_module,
            "_read_cleanup_linked_regular",
            side_effect=recreate_after_final_read,
        ):
            self.assertFalse(
                ProjectUpdateTransaction.resume_cleanup(
                    self.project,
                    transaction.transaction_ref,
                    cleanup_authority_sha256=authority,
                )
            )

        self.assertEqual(sentinel.read_bytes(), b"foreign original race occupant")

    def test_complete_cleanup_tombstone_can_be_restored_for_legacy_resume(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        authority = digest("legacy-cleanup-authority")

        with patch.object(
            ProjectUpdateTransaction, "_resume_cleanup_paths", return_value=False
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        tombstone = root.parent / f".cleanup_{transaction.transaction_ref}"
        self.assertFalse(root.exists())
        self.assertTrue(tombstone.is_dir())
        # Recreate the exact predecessor production shape: the v0.4.15 plan
        # predates durable transaction-root identity binding.
        current_plan_path = tombstone / CLEANUP_PLAN_NAME
        legacy_plan_path = tombstone / LEGACY_CLEANUP_PLAN_NAME
        legacy_plan = json.loads(current_plan_path.read_text(encoding="ascii"))
        legacy_plan["schema"] = LEGACY_CLEANUP_PLAN_SCHEMA
        legacy_plan.pop("transaction_root_identity")
        legacy_plan_path.write_bytes(transaction_module._document_bytes(legacy_plan))
        current_plan_path.unlink()

        candidate = (
            ProjectUpdateTransaction.discover_complete_cleanup_tombstone_for_resume_read_only(
                self.project
            )
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.transaction_ref, transaction.transaction_ref)
        self.assertEqual(candidate.cleanup_authority_sha256, authority)

        reopened = ProjectUpdateTransaction.restore_complete_cleanup_tombstone_for_resume(
            self.project, candidate
        )
        self.assertFalse(tombstone.exists())
        self.assertTrue(root.is_dir())
        self.assertTrue(reopened.inspect().terminal)
        self.assertEqual(reopened.intent.sha256, candidate.intent_sha256)
        self.assertEqual(
            reopened.inspect().journal.head_sha256,
            candidate.terminal_checkpoint_sha256,
        )
        self.assertEqual(reopened.cleanup_authority_sha256_read_only(), authority)
        self.assertTrue((root / LEGACY_CLEANUP_PLAN_NAME).exists())
        binding = reopened.private_binding_bytes("git-runner-binding")
        binding_record = next(
            item
            for item in reopened.intent.private_bindings
            if item.logical_key == "git-runner-binding"
        )
        self.assertEqual(sha256_bytes(binding), binding_record.sha256)
        completed = reopened.exact_cleanup(cleanup_authority_sha256=authority)
        self.assertFalse(root.exists())
        discovered_after = (
            ProjectUpdateTransaction
            .discover_complete_cleanup_tombstone_for_resume_read_only(
                self.project,
            )
        )
        if os.name == "nt":
            self.assertTrue(completed)
            self.assertIsNone(discovered_after)
            proof = (
                root.parent
                / f".cleanup-proof_{transaction.transaction_ref}.json"
            )
            proof_document = json.loads(proof.read_text(encoding="ascii"))
            self.assertEqual(proof_document["schema"], CLEANUP_PLAN_SCHEMA)
            self.assertEqual(
                set(proof_document["transaction_root_identity"]),
                {"birthtime_ns", "device", "inode"},
            )
            self.assertGreater(
                proof_document["transaction_root_identity"]["birthtime_ns"],
                0,
            )
        else:
            # Approved project-update mutation is Windows-only. POSIX keeps
            # the exact tombstone for explicit attention and deletes nothing.
            self.assertFalse(completed)
            self.assertIsNotNone(discovered_after)

    def test_cleanup_tombstone_restore_refuses_partial_or_colliding_state(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        authority = digest("legacy-cleanup-authority")
        with patch.object(
            ProjectUpdateTransaction, "_resume_cleanup_paths", return_value=False
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        tombstone = root.parent / f".cleanup_{transaction.transaction_ref}"
        candidate = (
            ProjectUpdateTransaction.discover_complete_cleanup_tombstone_for_resume_read_only(
                self.project
            )
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None

        # A destination published after discovery must never be replaced.
        root.mkdir()
        self.assert_code(
            "project_update_transaction_cleanup_refused",
            lambda: ProjectUpdateTransaction.restore_complete_cleanup_tombstone_for_resume(
                self.project, candidate
            ),
        )
        self.assertTrue(root.is_dir())
        self.assertTrue(tombstone.is_dir())
        root.rmdir()

        # A missing original byte makes the tombstone incomplete; subset
        # matching is deliberately insufficient for historical attribution.
        victim = next(
            path
            for path in tombstone.rglob("*")
            if path.is_file() and path.name != CLEANUP_PLAN_NAME
        )
        victim.unlink()
        self.assert_code(
            "project_update_transaction_cleanup_refused",
            lambda: ProjectUpdateTransaction.discover_complete_cleanup_tombstone_for_resume_read_only(
                self.project
            ),
        )

    def test_cleanup_tombstone_restore_rechecks_foreign_lock_after_move(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        authority = digest("legacy-cleanup-authority")
        with patch.object(
            ProjectUpdateTransaction, "_resume_cleanup_paths", return_value=False
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        candidate = (
            ProjectUpdateTransaction.discover_complete_cleanup_tombstone_for_resume_read_only(
                self.project
            )
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        real_move = transaction_module._atomic_move_directory_no_replace
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"

        def move_then_publish_foreign_lock(source: Path, destination: Path) -> None:
            real_move(source, destination)
            lock_path.write_bytes(b"foreign malformed lock")

        with patch.object(
            transaction_module,
            "_atomic_move_directory_no_replace",
            side_effect=move_then_publish_foreign_lock,
        ):
            self.assert_code(
                "project_update_transaction_cleanup_refused",
                lambda: ProjectUpdateTransaction.restore_complete_cleanup_tombstone_for_resume(
                    self.project, candidate
                ),
            )
        self.assertTrue(root.is_dir())
        self.assertFalse(
            (root.parent / f".cleanup_{transaction.transaction_ref}").exists()
        )
        self.assertTrue(lock_path.is_file())

    def test_cleanup_tombstone_restore_rechecks_plan_bytes_after_move(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        authority = digest("legacy-cleanup-authority")
        with patch.object(
            ProjectUpdateTransaction, "_resume_cleanup_paths", return_value=False
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        candidate = (
            ProjectUpdateTransaction.discover_complete_cleanup_tombstone_for_resume_read_only(
                self.project
            )
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        real_move = transaction_module._atomic_move_directory_no_replace

        def move_then_mutate_plan(source: Path, destination: Path) -> None:
            real_move(source, destination)
            plan_path = destination / CLEANUP_PLAN_NAME
            plan = json.loads(plan_path.read_text(encoding="ascii"))
            plan["directories"] = sorted(
                [*plan["directories"], "zz-race-directory"]
            )
            plan_path.write_bytes(transaction_module._document_bytes(plan))

        with patch.object(
            transaction_module,
            "_atomic_move_directory_no_replace",
            side_effect=move_then_mutate_plan,
        ):
            self.assert_code(
                "project_update_transaction_cleanup_refused",
                lambda: ProjectUpdateTransaction.restore_complete_cleanup_tombstone_for_resume(
                    self.project, candidate
                ),
            )
        self.assertTrue(root.is_dir())

    def test_cleanup_tombstone_restore_rechecks_closed_siblings_after_move(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        authority = digest("legacy-cleanup-authority")
        with patch.object(
            ProjectUpdateTransaction, "_resume_cleanup_paths", return_value=False
        ):
            self.assertFalse(
                transaction.exact_cleanup(cleanup_authority_sha256=authority)
            )
        candidate = (
            ProjectUpdateTransaction.discover_complete_cleanup_tombstone_for_resume_read_only(
                self.project
            )
        )
        self.assertIsNotNone(candidate)
        assert candidate is not None
        real_move = transaction_module._atomic_move_directory_no_replace

        def move_then_publish_unknown_sibling(
            source: Path, destination: Path
        ) -> None:
            real_move(source, destination)
            (destination.parent / "unexpected-race-entry").write_bytes(b"unknown")

        with patch.object(
            transaction_module,
            "_atomic_move_directory_no_replace",
            side_effect=move_then_publish_unknown_sibling,
        ):
            self.assert_code(
                "project_update_transaction_cleanup_refused",
                lambda: ProjectUpdateTransaction.restore_complete_cleanup_tombstone_for_resume(
                    self.project, candidate
                ),
            )
        self.assertTrue(root.is_dir())

    @unittest.skipUnless(os.name == "nt", "exact cleanup apply is Windows-only")
    def test_cleanup_tombstone_discovery_treats_proof_only_as_inert_history(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        authority = digest("legacy-cleanup-authority")
        self.assertTrue(
            transaction.exact_cleanup(cleanup_authority_sha256=authority)
        )
        self.assertIsNone(
            ProjectUpdateTransaction.discover_complete_cleanup_tombstone_for_resume_read_only(
                self.project
            )
        )

    def test_release_revalidates_live_components_before_removing_lock(self) -> None:
        transaction = self.create_transaction()
        lock_bytes, live = self.ready_forward(transaction)
        drifted = dict(live)
        drifted["launcher"] = digest("unknown-launcher-drift")
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: transaction.release_lock_exact(
                expected_lock_bytes=lock_bytes,
                live_component_sha256=drifted,
            ),
        )
        self.assertTrue(
            (self.project / ".zettel-kasten" / "version-update.lock").is_file()
        )

    def test_hard_exit_after_effect_intent_reopens_and_verifies_exact_post(self) -> None:
        transaction = self.create_transaction()
        _lock, live = self.begin(transaction)
        component = transaction.intent.components[0]
        transaction.append(
            phase=component.role,
            stage="intent",
            component_ref=component.component_ref,
            live_component_sha256=live,
        )
        # The domain writer completed, then the process disappeared before its
        # verified checkpoint.  Only the exact durable post digest may resume.
        live[component.component_ref] = component.post_sha256
        reopened = ProjectUpdateTransaction.open(
            self.project, transaction.transaction_ref
        )
        verified = reopened.append(
            phase=component.role,
            stage="verified",
            component_ref=component.component_ref,
            live_component_sha256=live,
        )
        self.assertEqual(verified.component_ref, component.component_ref)
        self.assertEqual(verified.stage, "verified")

    def test_hard_exit_after_lock_unlink_confirms_absence_durably_before_checkpoint(self) -> None:
        transaction = self.create_transaction()
        lock_bytes, live = self.ready_forward(transaction)
        transaction.release_lock_exact(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
        )
        reference = transaction.transaction_ref
        del transaction
        reopened = ProjectUpdateTransaction.open(self.project, reference)
        recovered_release = reopened.confirm_lock_absence_durable(
            live_component_sha256=live
        )
        self.assertTrue(recovered_release.directory_durability.durable)
        reopened.append(
            phase="lock_released",
            stage="verified",
            live_component_sha256=live,
            lock_release_result=recovered_release,
        )
        reopened.append(
            phase="completed",
            stage="verified",
            live_component_sha256=live,
        )
        self.assertTrue(reopened.inspect().terminal)

    def test_tampered_lock_backlink_observation_is_rejected(self) -> None:
        transaction = self.create_transaction()
        self.activate(transaction)
        backlink_path = self.transaction_root(transaction) / "lock-backlink.json"
        backlink = json.loads(backlink_path.read_text(encoding="ascii"))
        backlink["live_lock_observation_sha256"] = digest("forged-observation")
        backlink_path.write_bytes(canonical_json_bytes(backlink) + b"\n")
        self.assert_code(
            "project_update_transaction_lock_invalid",
            lambda: ProjectUpdateTransaction.open(
                self.project, transaction.transaction_ref
            ),
        )

    def test_terminal_cleanup_refuses_unexpected_descendant_without_deleting_it(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        unexpected = root / "unexpected.private"
        unexpected.write_bytes(b"preserve-me")
        self.assertFalse(
            transaction.exact_cleanup(
                cleanup_authority_sha256=digest("cleanup-authority")
            )
        )
        self.assertEqual(unexpected.read_bytes(), b"preserve-me")
        self.assertTrue((root / "intent.json").is_file())

    def test_unknown_checkpoint_key_is_degraded_and_never_auto_rewritten(self) -> None:
        transaction = self.create_transaction()
        self.begin(transaction)
        journal = self.transaction_root(transaction) / "checkpoints.jsonl"
        lines = journal.read_bytes().splitlines()
        first = json.loads(lines[0])
        first["unexpected"] = True
        damaged = canonical_json_bytes(first) + b"\n" + lines[1] + b"\n"
        journal.write_bytes(damaged)
        reopened = ProjectUpdateTransaction.open(
            self.project, transaction.transaction_ref
        )
        self.assertEqual(reopened.inspect().journal.state, "corrupt")
        self.assertEqual(journal.read_bytes(), damaged)

    def test_path_escape_and_mocked_symlink_reparse_are_fail_closed(self) -> None:
        self.assert_code(
            "project_update_transaction_path_unsafe",
            lambda: ProjectUpdateTransaction.open(self.project, "../escape"),
        )
        first = self.components()[0]
        self.assert_code(
            "project_update_transaction_intent_invalid",
            lambda: ProjectUpdateComponent(
                component_ref=first.component_ref,
                role=first.role,
                sequence=first.sequence,
                logical_target="../outside",
                pre_sha256=first.pre_sha256,
                post_sha256=first.post_sha256,
                preimage_key=first.preimage_key,
            ),
        )
        original_lstat = Path.lstat

        for kind in ("symlink", "reparse"):
            with self.subTest(kind=kind):
                def fake_lstat(path: Path):
                    info = original_lstat(path)
                    if os.path.normcase(str(path)) == os.path.normcase(str(self.project)):
                        return SimpleNamespace(
                            st_mode=(
                                stat.S_IFLNK
                                if kind == "symlink"
                                else stat.S_IFDIR | 0o700
                            ),
                            st_file_attributes=(0x400 if kind == "reparse" else 0),
                            st_dev=info.st_dev,
                            st_ino=info.st_ino,
                            st_mtime_ns=info.st_mtime_ns,
                            st_size=info.st_size,
                            st_nlink=info.st_nlink,
                        )
                    return info

                with patch.object(Path, "lstat", new=fake_lstat):
                    self.assert_code(
                        "project_update_transaction_path_unsafe",
                        lambda: ProjectUpdateTransaction.create(
                            self.project,
                            project_identity_sha256=digest("project"),
                            requested_target_tag="v0.4.3",
                            bindings=self.bindings(),
                            components=self.components(),
                            preimages=dict(self.pre_values),
                            runtime_bundle={"main-wheel": b"wheel"},
                            static_receipt_postimage=self.post_values["receipt"],
                        ),
                    )

    def test_prepared_reservation_is_write_free_and_binds_exact_marker(self) -> None:
        reservation = ProjectUpdateTransaction.prepare_reservation(
            project_identity_sha256=digest("prepared-project"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )

        self.assertFalse((self.project / ".zettel-kasten").exists())
        self.assertEqual(reservation.transaction_ref, self.DEFAULT_TRANSACTION_REF)
        self.assertEqual(
            reservation.sha256,
            transaction_module.sha256_document(reservation.document()),
        )
        self.assertEqual(
            transaction_module.ProjectUpdateReservation.from_document(
                reservation.document()
            ),
            reservation,
        )

    def test_reserve_or_resume_exact_recovers_every_durable_prefix_after_hard_exit(
        self,
    ) -> None:
        worker = "\n".join(
            (
                "import json, os, sys",
                "from pathlib import Path",
                "from wom_kit.project_update_transaction import ProjectUpdateReservation, ProjectUpdateTransaction",
                "reservation = ProjectUpdateReservation.from_document(json.loads(sys.argv[2]))",
                "def stop_at_boundary(name):",
                "    if name == sys.argv[3]:",
                "        os._exit(79)",
                "ProjectUpdateTransaction.reserve_or_resume_exact(Path(sys.argv[1]), reservation=reservation, _durable_boundary_callback=stop_at_boundary)",
            )
        )
        expected_names = {
            "root_durable": (),
            "marker_durable": ("marker.json",),
            "append_guard_durable": ("append.guard", "marker.json"),
        }

        for index, (boundary, expected) in enumerate(expected_names.items(), start=1):
            with self.subTest(boundary=boundary):
                project = self.project.parent / f"hard-exit-{index}"
                project.mkdir()
                reservation = ProjectUpdateTransaction.prepare_reservation(
                    project_identity_sha256=digest(f"hard-exit-project-{index}"),
                    requested_target_tag="v0.4.19",
                    transaction_ref=self.DEFAULT_TRANSACTION_REF,
                    ownership_nonce=f"{index:032x}",
                    created_at=self.CREATED_AT,
                )
                self.run_hard_exit_worker(
                    worker,
                    str(project),
                    json.dumps(
                        reservation.document(),
                        ensure_ascii=True,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    boundary,
                    expected_returncode=79,
                )
                root = (
                    project
                    / ".zettel-kasten"
                    / "private"
                    / "version-updates"
                    / reservation.transaction_ref
                )
                self.assertEqual(tuple(sorted(item.name for item in root.iterdir())), expected)

                resumed = ProjectUpdateTransaction.reserve_or_resume_exact(
                    project,
                    reservation=reservation,
                )
                self.assertEqual(resumed.reservation, reservation)
                before = {
                    name: ((root / name).read_bytes(), (root / name).stat().st_ino)
                    for name in ("marker.json", "append.guard")
                }
                reopened = ProjectUpdateTransaction.reserve_or_resume_exact(
                    project,
                    reservation=reservation,
                )
                self.assertEqual(reopened.reservation.sha256, reservation.sha256)
                self.assertEqual(
                    {
                        name: ((root / name).read_bytes(), (root / name).stat().st_ino)
                        for name in ("marker.json", "append.guard")
                    },
                    before,
                )

    def test_reserve_or_resume_exact_two_processes_converge_on_one_reservation(
        self,
    ) -> None:
        project = self.project.parent / "concurrent-reservation"
        project.mkdir()
        reservation = ProjectUpdateTransaction.prepare_reservation(
            project_identity_sha256=digest("concurrent-project"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        first_worker = "\n".join(
            (
                "import json, sys, time",
                "from pathlib import Path",
                "from wom_kit.project_update_transaction import ProjectUpdateReservation, ProjectUpdateTransaction",
                "reservation = ProjectUpdateReservation.from_document(json.loads(sys.argv[2]))",
                "ready, release = Path(sys.argv[3]), Path(sys.argv[4])",
                "def hold_guard(name):",
                "    if name == 'root_durable':",
                "        ready.write_bytes(b'ready')",
                "        while not release.exists():",
                "            time.sleep(0.01)",
                "result = ProjectUpdateTransaction.reserve_or_resume_exact(Path(sys.argv[1]), reservation=reservation, _durable_boundary_callback=hold_guard)",
                "assert result.reservation.sha256 == reservation.sha256",
            )
        )
        second_worker = "\n".join(
            (
                "import json, sys",
                "from pathlib import Path",
                "from wom_kit.project_update_transaction import ProjectUpdateReservation, ProjectUpdateTransaction",
                "reservation = ProjectUpdateReservation.from_document(json.loads(sys.argv[2]))",
                "result = ProjectUpdateTransaction.reserve_or_resume_exact(Path(sys.argv[1]), reservation=reservation)",
                "assert result.reservation.sha256 == reservation.sha256",
            )
        )
        environment = dict(os.environ)
        environment.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(SRC_ROOT),
                "PYTHONUTF8": "1",
            }
        )
        document = json.dumps(
            reservation.document(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        ready = self.project.parent / "reservation-first-ready"
        release = self.project.parent / "reservation-first-release"
        first = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-c",
                first_worker,
                str(project),
                document,
                str(ready),
                str(release),
            ],
            cwd=KIT_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        second = None
        try:
            for _attempt in range(250):
                if ready.exists():
                    break
                if first.poll() is not None:
                    break
                threading.Event().wait(0.02)
            self.assertTrue(ready.is_file())
            second = subprocess.Popen(
                [sys.executable, "-B", "-c", second_worker, str(project), document],
                cwd=KIT_ROOT,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            threading.Event().wait(0.25)
            self.assertIsNone(second.poll(), "second process did not wait on the guard")
            root = (
                project
                / ".zettel-kasten"
                / "private"
                / "version-updates"
                / reservation.transaction_ref
            )
            self.assertEqual(tuple(root.iterdir()), ())
            release.write_bytes(b"release")
            first_stdout, first_stderr = first.communicate(timeout=30)
            second_stdout, second_stderr = second.communicate(timeout=30)
            self.assertEqual(first.returncode, 0, first_stdout + first_stderr)
            self.assertEqual(second.returncode, 0, second_stdout + second_stderr)
        finally:
            for process in (first, second):
                if process is not None and process.poll() is None:
                    process.kill()
                    process.communicate(timeout=10)
        reopened = ProjectUpdateTransaction.reserve_or_resume_exact(
            project,
            reservation=reservation,
        )
        self.assertEqual(reopened.reservation, reservation)
        self.assertEqual(
            tuple(sorted(item.name for item in reopened.transaction_root.iterdir())),
            ("append.guard", "marker.json"),
        )

    def test_reserve_or_resume_exact_blocks_nonexact_prefixes_without_deleting(
        self,
    ) -> None:
        class BoundaryStop(BaseException):
            pass

        def materialize_prefix(label: str, boundary: str):
            project = self.project.parent / label
            project.mkdir()
            reservation = ProjectUpdateTransaction.prepare_reservation(
                project_identity_sha256=digest(label),
                requested_target_tag="v0.4.19",
                transaction_ref=self.DEFAULT_TRANSACTION_REF,
                ownership_nonce=hashlib.sha256(label.encode("ascii")).hexdigest()[:32],
                created_at=self.CREATED_AT,
            )

            def stop(name: str) -> None:
                if name == boundary:
                    raise BoundaryStop()

            with self.assertRaises(BoundaryStop):
                ProjectUpdateTransaction.reserve_or_resume_exact(
                    project,
                    reservation=reservation,
                    _durable_boundary_callback=stop,
                )
            root = (
                project
                / ".zettel-kasten"
                / "private"
                / "version-updates"
                / reservation.transaction_ref
            )
            return project, root, reservation

        project, root, reservation = materialize_prefix("extra-entry", "root_durable")
        extra = root / "unbound.bin"
        extra.write_bytes(b"preserve-extra")
        self.assert_code(
            "project_update_transaction_reservation_state_changed",
            lambda: ProjectUpdateTransaction.reserve_or_resume_exact(
                project, reservation=reservation
            ),
        )
        self.assertEqual(extra.read_bytes(), b"preserve-extra")

        project, root, reservation = materialize_prefix("wrong-marker", "marker_durable")
        marker = root / "marker.json"
        marker.write_bytes(b"different-marker\n")
        self.assert_code(
            "project_update_transaction_reservation_state_changed",
            lambda: ProjectUpdateTransaction.reserve_or_resume_exact(
                project, reservation=reservation
            ),
        )
        self.assertEqual(marker.read_bytes(), b"different-marker\n")

        project, root, reservation = materialize_prefix(
            "wrong-guard", "append_guard_durable"
        )
        guard = root / "append.guard"
        guard.write_bytes(b"\x01")
        self.assert_code(
            "project_update_transaction_reservation_state_changed",
            lambda: ProjectUpdateTransaction.reserve_or_resume_exact(
                project, reservation=reservation
            ),
        )
        self.assertEqual(guard.read_bytes(), b"\x01")

        project = self.project.parent / "wrong-authority"
        project.mkdir()
        first = ProjectUpdateTransaction.prepare_reservation(
            project_identity_sha256=digest("wrong-authority"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="1" * 32,
            created_at=self.CREATED_AT,
        )
        ProjectUpdateTransaction.reserve_or_resume_exact(project, reservation=first)
        marker = (
            project
            / ".zettel-kasten"
            / "private"
            / "version-updates"
            / first.transaction_ref
            / "marker.json"
        )
        original_marker = marker.read_bytes()
        second = ProjectUpdateTransaction.prepare_reservation(
            project_identity_sha256=digest("wrong-authority"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="2" * 32,
            created_at=self.CREATED_AT,
        )
        self.assert_code(
            "project_update_transaction_reservation_state_changed",
            lambda: ProjectUpdateTransaction.reserve_or_resume_exact(
                project, reservation=second
            ),
        )
        self.assertEqual(marker.read_bytes(), original_marker)

    def test_reserve_or_resume_exact_rejects_hardlink_and_reparse_marker(self) -> None:
        reservation = ProjectUpdateTransaction.prepare_reservation(
            project_identity_sha256=digest("linked-project"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        reserved = ProjectUpdateTransaction.reserve_or_resume_exact(
            self.project, reservation=reservation
        )
        marker = reserved.transaction_root / "marker.json"
        outside = self.project / "linked-marker-copy"
        outside.write_bytes(marker.read_bytes())
        marker.unlink()
        os.link(outside, marker)
        self.assert_code(
            "project_update_transaction_reservation_state_changed",
            lambda: ProjectUpdateTransaction.reserve_or_resume_exact(
                self.project, reservation=reservation
            ),
        )
        self.assertTrue(marker.exists())
        self.assertTrue(outside.exists())

        marker.unlink()
        marker.write_bytes(
            canonical_json_bytes(reservation.document()) + b"\n"
        )
        original_lstat = Path.lstat

        def report_marker_reparse(path: Path):
            info = original_lstat(path)
            if os.path.normcase(str(path)) == os.path.normcase(str(marker)):
                return SimpleNamespace(
                    st_mode=info.st_mode,
                    st_file_attributes=0x400,
                    st_dev=info.st_dev,
                    st_ino=info.st_ino,
                    st_mtime_ns=info.st_mtime_ns,
                    st_size=info.st_size,
                    st_nlink=info.st_nlink,
                )
            return info

        with patch.object(Path, "lstat", new=report_marker_reparse):
            self.assert_code(
                "project_update_transaction_reservation_state_changed",
                lambda: ProjectUpdateTransaction.reserve_or_resume_exact(
                    self.project, reservation=reservation
                ),
            )
        self.assertEqual(marker.read_bytes(), canonical_json_bytes(reservation.document()) + b"\n")

    @unittest.skipUnless(os.name == "nt", "Windows retained directory handles")
    def test_reserve_or_resume_exact_retains_root_through_final_identity_check(
        self,
    ) -> None:
        reservation = ProjectUpdateTransaction.prepare_reservation(
            project_identity_sha256=digest("retained-root-project"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        root = (
            self.project
            / ".zettel-kasten"
            / "private"
            / "version-updates"
            / reservation.transaction_ref
        )
        moved = root.with_name(root.name + "-moved")
        blocked_boundaries: list[str] = []

        def attempt_generation_swap(boundary: str) -> None:
            if boundary not in {"root_bound", "prefix_verified"}:
                return
            try:
                root.rename(moved)
            except OSError:
                blocked_boundaries.append(boundary)
                return
            moved.rename(root)
            self.fail("retained root handle allowed a generation swap")

        with patch.object(
            transaction_module,
            "_reservation_generation_test_hook",
            side_effect=attempt_generation_swap,
        ):
            result = ProjectUpdateTransaction.reserve_or_resume_exact(
                self.project, reservation=reservation
            )
        self.assertEqual(blocked_boundaries, ["root_bound", "prefix_verified"])
        self.assertEqual(result.reservation, reservation)
        self.assertTrue(root.is_dir())
        self.assertFalse(moved.exists())

    @unittest.skipUnless(os.name == "nt", "NTFS alternate stream fixture")
    def test_reserve_or_resume_exact_rejects_named_streams_without_removing_them(
        self,
    ) -> None:
        reservation = ProjectUpdateTransaction.prepare_reservation(
            project_identity_sha256=digest("ads-project"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        reserved = ProjectUpdateTransaction.reserve_or_resume_exact(
            self.project, reservation=reservation
        )
        marker = reserved.transaction_root / "marker.json"
        named_stream = Path(str(marker) + ":unbound")
        try:
            named_stream.write_bytes(b"preserve-stream")
        except OSError as error:
            self.skipTest(f"NTFS named streams unavailable: {type(error).__name__}")
        self.assert_code(
            "project_update_transaction_reservation_state_changed",
            lambda: ProjectUpdateTransaction.reserve_or_resume_exact(
                self.project, reservation=reservation
            ),
        )
        self.assertEqual(named_stream.read_bytes(), b"preserve-stream")
        self.assertTrue(marker.is_file())

    @unittest.skipUnless(os.name == "nt", "Windows namespace guard injection")
    def test_cleanup_residue_is_rechecked_after_reservation_guard_acquisition(
        self,
    ) -> None:
        reservation = ProjectUpdateTransaction.prepare_reservation(
            project_identity_sha256=digest("cleanup-race-project"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        original_guard = transaction_module._reservation_materialization_guard
        published: list[Path] = []

        @contextmanager
        def publish_cleanup_inside_guard(parent: Path, transaction_ref: str):
            with original_guard(parent, transaction_ref) as binding:
                proof = parent / f".cleanup-proof_{transaction_ref}.json"
                proof.write_bytes(b"preserve-cleanup-proof")
                published.append(proof)
                yield binding

        with patch.object(
            transaction_module,
            "_reservation_materialization_guard",
            new=publish_cleanup_inside_guard,
        ):
            self.assert_code(
                "project_update_transaction_exists",
                lambda: ProjectUpdateTransaction.reserve_or_resume_exact(
                    self.project, reservation=reservation
                ),
            )
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].read_bytes(), b"preserve-cleanup-proof")
        self.assertFalse(
            (
                published[0].parent
                / reservation.transaction_ref
            ).exists()
        )

    @unittest.skipUnless(os.name != "nt", "POSIX descriptor-relative mutation")
    def test_posix_reservation_writes_never_follow_parent_or_root_generation_swap(
        self,
    ) -> None:
        for swap_boundary in ("guard_acquired", "root_bound"):
            with self.subTest(boundary=swap_boundary):
                project = self.project.parent / f"posix-{swap_boundary}"
                project.mkdir()
                reservation = ProjectUpdateTransaction.prepare_reservation(
                    project_identity_sha256=digest(f"posix-{swap_boundary}"),
                    requested_target_tag="v0.4.19",
                    transaction_ref=self.DEFAULT_TRANSACTION_REF,
                    ownership_nonce=("1" if swap_boundary == "guard_acquired" else "2")
                    * 32,
                    created_at=self.CREATED_AT,
                )
                parent = project / ".zettel-kasten" / "private" / "version-updates"
                root = parent / reservation.transaction_ref
                moved_parent = parent.with_name(parent.name + "-retained")
                moved_root = (
                    moved_parent / reservation.transaction_ref
                    if swap_boundary == "guard_acquired"
                    else root.with_name(root.name + "-retained")
                )

                def swap_generation(boundary: str) -> None:
                    if boundary != swap_boundary:
                        return
                    if swap_boundary == "guard_acquired":
                        parent.rename(moved_parent)
                        parent.mkdir()
                    else:
                        root.rename(moved_root)
                        root.mkdir()
                        (root / "foreign.bin").write_bytes(b"preserve-foreign")

                with patch.object(
                    transaction_module,
                    "_reservation_generation_test_hook",
                    side_effect=swap_generation,
                ):
                    self.assert_code(
                        "project_update_transaction_reservation_state_changed",
                        lambda: ProjectUpdateTransaction.reserve_or_resume_exact(
                            project, reservation=reservation
                        ),
                    )
                if swap_boundary == "guard_acquired":
                    self.assertFalse(root.exists())
                    self.assertEqual(
                        tuple(sorted(item.name for item in moved_root.iterdir())),
                        ("append.guard", "marker.json"),
                    )
                else:
                    self.assertEqual(
                        (root / "foreign.bin").read_bytes(), b"preserve-foreign"
                    )
                    self.assertEqual(
                        tuple(sorted(item.name for item in root.iterdir())),
                        ("foreign.bin",),
                    )
                    self.assertEqual(
                        tuple(sorted(item.name for item in moved_root.iterdir())),
                        ("append.guard", "marker.json"),
                    )

    def test_legacy_reserve_remains_create_only_for_an_exact_existing_prefix(self) -> None:
        reservation = ProjectUpdateTransaction.prepare_reservation(
            project_identity_sha256=digest("legacy-compatible-project"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        ProjectUpdateTransaction.reserve_or_resume_exact(
            self.project, reservation=reservation
        )
        self.assert_code(
            "project_update_transaction_exists",
            lambda: ProjectUpdateTransaction.reserve(
                self.project,
                project_identity_sha256=reservation.project_identity_sha256,
                requested_target_tag=reservation.requested_target_tag,
                transaction_ref=reservation.transaction_ref,
                ownership_nonce=reservation.ownership_nonce,
                created_at=reservation.created_at,
            ),
        )

    def test_two_stage_reservation_lock_and_large_candidate_are_sealed_in_place(self) -> None:
        reserved, lock_bytes, tree = self.reserve_and_build_candidate(file_count=300)
        self.assertIsNotNone(lock_bytes)
        self.assertEqual(reserved.created_at, self.CREATED_AT)
        self.assertEqual(
            reserved.runtime_candidate_path,
            reserved.transaction_root / "runtime-candidate",
        )
        self.assertGreater(tree.inventory_count, 256)
        candidate_identity = reserved.runtime_candidate_path.stat().st_ino
        transaction = self.seal_reserved(reserved, tree)
        self.assertEqual(
            transaction.runtime_candidate_path.stat().st_ino, candidate_identity
        )
        self.assertEqual(
            transaction.intent.runtime_candidate.inventory_count,
            tree.inventory_count,
        )
        self.assertFalse((transaction.transaction_root / "runtime-bundle").exists())
        self.assertEqual(
            {record.logical_key for record in transaction.intent.private_bindings},
            {
                "git-runner-binding",
                "runtime-candidate-path-identities",
                "static-receipt-postimage",
            },
        )
        transaction.bind_sealed_intent_to_lock(lock_bytes)
        reopened = ProjectUpdateTransaction.open(
            self.project, transaction.transaction_ref
        )
        self.assertEqual(reopened.intent.sha256, transaction.intent.sha256)
        self.assert_code(
            "project_update_transaction_exists",
            lambda: self.seal_reserved(reserved, tree),
        )

    def test_reservation_lock_blocks_competing_transaction_and_preserves_both_roots(self) -> None:
        first = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.3",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        first.acquire_lock()
        second = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.3",
            transaction_ref="update_99999999999999999999999999999999",
            ownership_nonce="99999999999999999999999999999999",
            created_at=self.CREATED_AT,
        )
        self.assert_code(
            "project_update_transaction_lock_invalid",
            lambda: second.acquire_lock(),
        )
        self.assertTrue(first.transaction_root.is_dir())
        self.assertTrue(second.transaction_root.is_dir())
        scan = {item.transaction_ref: item for item in inspect_prelock_orphans(self.project)}
        self.assertEqual(
            scan[first.transaction_ref].classification,
            "reserved_locked_unsealed",
        )
        self.assertEqual(
            scan[second.transaction_ref].classification,
            "manual_review_incomplete_or_unsafe",
        )

    def test_partial_candidate_and_partial_intent_are_manual_review_only(self) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.3",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        reserved.acquire_lock()
        reserved.runtime_candidate_path.mkdir()
        partial = reserved.runtime_candidate_path / "partial.bin"
        partial.write_bytes(b"preserve-partial-candidate")
        scan = inspect_prelock_orphans(self.project)
        self.assertEqual(scan[0].classification, "manual_review_candidate_partial")
        self.assert_code(
            "project_update_transaction_path_unsafe",
            lambda: ProjectUpdateTransaction.open(
                self.project, reserved.transaction_ref
            ),
        )
        self.assertEqual(partial.read_bytes(), b"preserve-partial-candidate")
        (reserved.transaction_root / "preimages").mkdir()
        scan_after = inspect_prelock_orphans(self.project)
        self.assertEqual(
            scan_after[0].classification,
            "manual_review_intent_seal_incomplete_or_invalid",
        )
        self.assertEqual(partial.read_bytes(), b"preserve-partial-candidate")

    def test_candidate_drift_is_rejected_and_runtime_promotion_can_resume_after_intent(self) -> None:
        transaction = self.create_transaction()
        root = self.transaction_root(transaction)
        artifact = next(
            (transaction.runtime_candidate_path / "artifacts").iterdir()
        )
        original = artifact.read_bytes()
        artifact.write_bytes(original + b"drift")
        self.assert_code(
            "project_update_transaction_candidate_invalid",
            lambda: ProjectUpdateTransaction.open(
                self.project, transaction.transaction_ref
            ),
        )
        artifact.write_bytes(original)
        transaction = ProjectUpdateTransaction.open(
            self.project, transaction.transaction_ref
        )
        _lock, live = self.begin(transaction)
        source = transaction.intent.components[0]
        transaction.append(
            phase=source.role,
            stage="intent",
            component_ref=source.component_ref,
            live_component_sha256=live,
        )
        live[source.component_ref] = source.post_sha256
        transaction.append(
            phase=source.role,
            stage="verified",
            component_ref=source.component_ref,
            live_component_sha256=live,
        )
        runtime = transaction.intent.components[1]
        transaction.append(
            phase=runtime.role,
            stage="intent",
            component_ref=runtime.component_ref,
            live_component_sha256=live,
        )
        runtime_cleanup = self.runtime_cleanup_terminal_evidence(transaction)
        final_parent = self.project / ".zettel-kasten" / "runtimes"
        final_parent.mkdir(exist_ok=True)
        transaction.runtime_candidate_path.replace(final_parent / "v0.4.3")
        (root / "runtime-candidate-seal.json").unlink()
        live[runtime.component_ref] = runtime.post_sha256
        reopened = ProjectUpdateTransaction.open(
            self.project, transaction.transaction_ref
        )
        checkpoint = reopened.append(
            phase=runtime.role,
            stage="verified",
            component_ref=runtime.component_ref,
            live_component_sha256=live,
            runtime_cleanup_terminal_evidence=runtime_cleanup,
        )
        self.assertEqual(checkpoint.component_ref, "runtime")
        ack = transaction_module.load_runtime_cleanup_durable_ack(
            self.project,
            transaction.transaction_ref,
        )
        self.assertIsNotNone(ack)
        assert ack is not None
        self.assertEqual(ack.authority_kind, "runtime_verified")
        self.assertTrue(
            transaction_module.revalidate_runtime_cleanup_durable_ack(ack)
        )

    def test_static_receipt_and_bounded_claim_evidence_form_exact_join(self) -> None:
        transaction = self.create_transaction()
        _lock, live = self.begin(transaction)
        for component in transaction.intent.components:
            transaction.append(
                phase=component.role,
                stage="intent",
                component_ref=component.component_ref,
                live_component_sha256=live,
            )
            runtime_cleanup = None
            if component.role == "runtime":
                runtime_cleanup = self.runtime_cleanup_terminal_evidence(
                    transaction
                )
                self.remove_sealed_candidate(transaction)
            live[component.component_ref] = component.post_sha256
            transaction.append(
                phase=component.role,
                stage="verified",
                component_ref=component.component_ref,
                live_component_sha256=live,
                runtime_cleanup_terminal_evidence=runtime_cleanup,
            )
        transaction.append(
            phase="domain_committed",
            stage="verified",
            live_component_sha256=live,
        )
        domain_guard = transaction.inspect().journal.head_sha256
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: transaction.append(
                phase="claim_succeeded",
                stage="verified",
                live_component_sha256=live,
                claim_receipt_sha256=digest("claim-receipt"),
                claim_mac_sha256=digest("claim-mac"),
            ),
        )
        evidence = self.claim_evidence(
            transaction,
            approval_reference=digest("main-approval-reference"),
            claim_receipt=digest("claim-receipt"),
            claim_mac=digest("claim-mac"),
        )
        wrong = dict(evidence)
        wrong["static_receipt_sha256"] = digest("wrong-static-receipt")
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: transaction.append(
                phase="claim_succeeded",
                stage="verified",
                live_component_sha256=live,
                claim_receipt_sha256=digest("claim-receipt"),
                claim_mac_sha256=digest("claim-mac"),
                claim_evidence=wrong,
            ),
        )
        checkpoint = transaction.finalize_succeeded_claim(
            checkpoint_guard_sha256=domain_guard,
            live_component_sha256=live,
            claim_receipt_sha256=digest("claim-receipt"),
            claim_mac_sha256=digest("claim-mac"),
            claim_evidence=evidence,
        )
        self.assertEqual(dict(checkpoint.claim_evidence_digests), evidence)
        self.assertEqual(
            transaction.finalize_succeeded_claim(
                checkpoint_guard_sha256=domain_guard,
                live_component_sha256=live,
                claim_receipt_sha256=digest("claim-receipt"),
                claim_mac_sha256=digest("claim-mac"),
                claim_evidence=evidence,
            ).checkpoint_sha256,
            checkpoint.checkpoint_sha256,
        )
        self.assertEqual(
            transaction.finalize_succeeded_claim(
                checkpoint_guard_sha256=checkpoint.checkpoint_sha256,
                live_component_sha256=live,
                claim_receipt_sha256=digest("claim-receipt"),
                claim_mac_sha256=digest("claim-mac"),
                claim_evidence=evidence,
            ).checkpoint_sha256,
            checkpoint.checkpoint_sha256,
        )
        self.assertEqual(
            transaction.intent.static_receipt_domain_plan_sha256,
            digest("static-plan"),
        )
        self.assertEqual(
            transaction.intent.static_receipt_domain_target_binding_sha256,
            digest("static-target-binding"),
        )
        approval_bound = next(
            item
            for item in transaction.inspect().journal.verified_prefix
            if item.phase == "approval_bound"
        )
        self.assertEqual(
            approval_bound.approval_reference_sha256,
            digest("main-approval-reference"),
        )
        self.assertNotEqual(
            approval_bound.approval_reference_sha256,
            transaction.intent.static_receipt_domain_plan_sha256,
        )
        self.assertNotIn(
            digest("main-approval-reference"),
            (transaction.transaction_root / "intent.json").read_text(
                encoding="ascii"
            ),
        )
        journal_text = (
            transaction.transaction_root / "checkpoints.jsonl"
        ).read_text(encoding="ascii")
        self.assertIn('"claim_evidence_digests"', journal_text)
        self.assertNotIn("approval_id", journal_text)
        transaction.append(
            phase="ready_to_unlock",
            stage="verified",
            live_component_sha256=live,
        )
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: transaction.finalize_succeeded_claim(
                checkpoint_guard_sha256=checkpoint.checkpoint_sha256,
                live_component_sha256=live,
                claim_receipt_sha256=digest("claim-receipt"),
                claim_mac_sha256=digest("claim-mac"),
                claim_evidence=evidence,
            ),
        )

    def test_runtime_cleanup_evidence_is_exact_and_ack_is_disk_issued(self) -> None:
        transaction = self.create_transaction()
        _lock, live = self.begin(transaction)
        source, runtime = transaction.intent.components[:2]
        for component in (source,):
            transaction.append(
                phase=component.role,
                stage="intent",
                component_ref=component.component_ref,
                live_component_sha256=live,
            )
            live[component.component_ref] = component.post_sha256
            transaction.append(
                phase=component.role,
                stage="verified",
                component_ref=component.component_ref,
                live_component_sha256=live,
            )
        transaction.append(
            phase=runtime.role,
            stage="intent",
            component_ref=runtime.component_ref,
            live_component_sha256=live,
        )
        evidence = self.runtime_cleanup_terminal_evidence(transaction)
        self.remove_sealed_candidate(transaction)
        live[runtime.component_ref] = runtime.post_sha256
        journal_path = transaction.transaction_root / "checkpoints.jsonl"
        journal_before = journal_path.read_bytes()

        missing = dict(evidence)
        missing.pop("runtime_cleanup_capsule_sha256")
        extra = dict(evidence, private_candidate_path="forbidden")
        cross_ref = dict(evidence, transaction_ref="update_" + "f" * 32)
        cross_candidate = dict(
            evidence,
            candidate_sha256=digest("different-candidate"),
        )
        false_required = dict(evidence, cleanup_complete=False)
        bool_count = dict(evidence, provider_inventory_count=True)
        for invalid in (
            missing,
            extra,
            cross_ref,
            cross_candidate,
            false_required,
            bool_count,
            [evidence],
        ):
            with self.subTest(invalid_type=type(invalid).__name__):
                self.assert_code(
                    "project_update_transaction_candidate_invalid",
                    lambda invalid=invalid: transaction.append(
                        phase=runtime.role,
                        stage="verified",
                        component_ref=runtime.component_ref,
                        live_component_sha256=live,
                        runtime_cleanup_terminal_evidence=invalid,
                    ),
                )
                self.assertEqual(journal_path.read_bytes(), journal_before)

        checkpoint = transaction.append(
            phase=runtime.role,
            stage="verified",
            component_ref=runtime.component_ref,
            live_component_sha256=live,
            runtime_cleanup_terminal_evidence=evidence,
        )
        self.assertEqual(
            checkpoint.runtime_cleanup_terminal_evidence_sha256,
            transaction_module.sha256_document(evidence),
        )
        self.assertEqual(
            checkpoint.runtime_cleanup_capsule_sha256,
            evidence["runtime_cleanup_capsule_sha256"],
        )
        self.assertEqual(
            checkpoint.runtime_cleanup_capsule_identity_sha256,
            evidence["runtime_cleanup_capsule_identity_sha256"],
        )

        ack = transaction_module.load_runtime_cleanup_durable_ack(
            self.project,
            transaction.transaction_ref,
        )
        self.assertIsInstance(
            ack,
            transaction_module.RuntimeCleanupDurableAck,
        )
        assert ack is not None
        self.assertEqual(ack.authority_kind, "runtime_verified")
        self.assertEqual(ack.authority_record_sha256, checkpoint.checkpoint_sha256)
        self.assertEqual(
            ack.runtime_cleanup_terminal_evidence_sha256,
            transaction_module.sha256_document(evidence),
        )
        self.assertTrue(
            transaction_module.revalidate_runtime_cleanup_durable_ack(ack)
        )
        self.assertNotIn(str(self.project), repr(ack))
        self.assertNotIn("private_candidate_path", repr(ack))
        for transient in (evidence, digest("plain-string"), object()):
            self.assertFalse(
                transaction_module.revalidate_runtime_cleanup_durable_ack(
                    transient
                )
            )
        forged = object.__new__(transaction_module.RuntimeCleanupDurableAck)
        for name, value in vars(ack).items():
            object.__setattr__(forged, name, value)
        self.assertFalse(
            transaction_module.revalidate_runtime_cleanup_durable_ack(forged)
        )
        with self.assertRaises(TypeError):
            copy.copy(ack)
        with self.assertRaises(TypeError):
            copy.deepcopy(ack)

        launcher = transaction.intent.components[2]
        transaction.append(
            phase=launcher.role,
            stage="intent",
            component_ref=launcher.component_ref,
            live_component_sha256=live,
        )
        self.assertFalse(
            transaction_module.revalidate_runtime_cleanup_durable_ack(ack)
        )
        current = transaction_module.load_runtime_cleanup_durable_ack(
            self.project,
            transaction.transaction_ref,
        )
        self.assertIsNotNone(current)
        assert current is not None
        self.assertTrue(
            transaction_module.revalidate_runtime_cleanup_durable_ack(current)
        )

    def test_runtime_cleanup_checkpoint_triplet_is_atomic_and_legacy_readable(
        self,
    ) -> None:
        transaction = self.create_transaction()
        _lock, live = self.begin(transaction)
        source, runtime = transaction.intent.components[:2]
        transaction.append(
            phase=source.role,
            stage="intent",
            component_ref=source.component_ref,
            live_component_sha256=live,
        )
        live[source.component_ref] = source.post_sha256
        transaction.append(
            phase=source.role,
            stage="verified",
            component_ref=source.component_ref,
            live_component_sha256=live,
        )
        transaction.append(
            phase=runtime.role,
            stage="intent",
            component_ref=runtime.component_ref,
            live_component_sha256=live,
        )
        evidence = self.runtime_cleanup_terminal_evidence(transaction)
        self.remove_sealed_candidate(transaction)
        live[runtime.component_ref] = runtime.post_sha256
        transaction.append(
            phase=runtime.role,
            stage="verified",
            component_ref=runtime.component_ref,
            live_component_sha256=live,
            runtime_cleanup_terminal_evidence=evidence,
        )
        journal_path = transaction.transaction_root / "checkpoints.jsonl"
        rows = [
            json.loads(line)
            for line in journal_path.read_text(encoding="ascii").splitlines()
        ]
        runtime_index = next(
            index
            for index, row in enumerate(rows)
            if row["phase"] == "runtime" and row["stage"] == "verified"
        )

        partial = [dict(row) for row in rows]
        partial[runtime_index].pop(
            "runtime_cleanup_capsule_identity_sha256"
        )
        journal_path.write_bytes(
            b"".join(
                canonical_json_bytes(row) + b"\n"
                for row in partial
            )
        )
        with self.assertRaises(ProjectUpdateTransactionError):
            transaction_module.load_runtime_cleanup_durable_ack(
                self.project,
                transaction.transaction_ref,
            )

        legacy = [dict(row) for row in rows]
        for name in (
            "runtime_cleanup_terminal_evidence_sha256",
            "runtime_cleanup_capsule_sha256",
            "runtime_cleanup_capsule_identity_sha256",
        ):
            legacy[runtime_index].pop(name)
        journal_path.write_bytes(
            b"".join(
                canonical_json_bytes(row) + b"\n"
                for row in legacy
            )
        )
        reopened = ProjectUpdateTransaction.open(
            self.project,
            transaction.transaction_ref,
            verify_candidate_content=False,
        )
        self.assertEqual(reopened.inspect().journal.state, "exact")
        self.assertIsNone(
            transaction_module.load_runtime_cleanup_durable_ack(
                self.project,
                transaction.transaction_ref,
            )
        )

    def test_dynamic_approval_fields_are_refused_before_static_receipt_seal(self) -> None:
        reserved, _lock, tree = self.reserve_and_build_candidate()
        dynamic_receipt = canonical_json_bytes(
            {
                "approval_id": "dynamic-approval-id",
                "plan_sha256": digest("static-plan"),
                "schema": "wom-kit/project-version-update-static-receipt/v0.4.3",
                "target_binding_sha256": digest("static-target-binding"),
                "timestamp": self.CREATED_AT,
                "transaction_ref": reserved.transaction_ref,
            }
        ) + b"\n"
        components = self.components(receipt_postimage=dynamic_receipt)
        runtime_post = next(
            component.post_sha256
            for component in components
            if component.role == "runtime"
        )
        self.assert_code(
            "project_update_transaction_intent_invalid",
            lambda: reserved.seal_intent(
                bindings=self.bindings(),
                components=components,
                preimages=dict(self.pre_values),
                private_binding_blobs={"git-runner-binding": b"private-runner"},
                static_receipt_postimage=dynamic_receipt,
                runtime_candidate_inventory_sha256=tree.recursive_tree_sha256,
                runtime_candidate_postimage_sha256=runtime_post,
            ),
        )
        self.assertFalse((reserved.transaction_root / "intent.json").exists())
        self.assertTrue(reserved.runtime_candidate_path.is_dir())
        self.assertEqual(
            inspect_prelock_orphans(self.project)[0].classification,
            "candidate_sealed_intent_unsealed",
        )

    def test_preapproval_cancel_is_terminal_idempotent_and_cleanup_gated(self) -> None:
        transaction = self.create_transaction()
        lock_bytes = self.activate(transaction)
        live = self.live_pre()
        transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=live,
        )
        plan = transaction.candidate_cleanup_plan_sha256()
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: transaction.begin_cancel_before_approval(
                expected_lock_bytes=lock_bytes,
                live_component_sha256=live,
                candidate_cleanup_plan_sha256=digest("invented-plan"),
            ),
        )
        requested = transaction.begin_cancel_before_approval(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
            candidate_cleanup_plan_sha256=plan,
        )
        self.assertEqual(requested.phase, "preapproval_cancel_requested")
        self.assertFalse(
            transaction.exact_cleanup(cleanup_authority_sha256=digest("cleanup"))
        )
        runtime_cleanup = self.runtime_cleanup_terminal_evidence(transaction)
        self.remove_sealed_candidate(transaction)
        receipt = transaction.candidate_cleanup_receipt_sha256()
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: transaction.cancel_before_approval(
                expected_lock_bytes=lock_bytes,
                live_component_sha256=live,
                runtime_cleanup_terminal_evidence=runtime_cleanup,
                candidate_cleanup_plan_sha256=plan,
                candidate_cleanup_receipt_sha256=digest("invented-receipt"),
            ),
        )
        completed = transaction.cancel_before_approval(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
            runtime_cleanup_terminal_evidence=runtime_cleanup,
            candidate_cleanup_plan_sha256=plan,
            candidate_cleanup_receipt_sha256=receipt,
        )
        self.assertEqual(completed.phase, "completed")
        self.assertFalse(
            (self.project / ".zettel-kasten" / "version-update.lock").exists()
        )
        reopened = ProjectUpdateTransaction.open(
            self.project, transaction.transaction_ref
        )
        repeated = reopened.cancel_before_approval(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
            runtime_cleanup_terminal_evidence=runtime_cleanup,
            candidate_cleanup_plan_sha256=plan,
            candidate_cleanup_receipt_sha256=receipt,
        )
        self.assertEqual(repeated.checkpoint_sha256, completed.checkpoint_sha256)
        ack = transaction_module.load_runtime_cleanup_durable_ack(
            self.project,
            transaction.transaction_ref,
        )
        self.assertIsNotNone(ack)
        assert ack is not None
        self.assertEqual(ack.authority_kind, "preapproval_cancelled")
        self.assertEqual(
            ack.runtime_cleanup_terminal_evidence_sha256,
            transaction_module.sha256_document(runtime_cleanup),
        )
        self.assertTrue(
            transaction_module.revalidate_runtime_cleanup_durable_ack(ack)
        )
        phases = [
            item.phase for item in reopened.inspect().journal.verified_prefix
        ]
        self.assertNotIn("approval_bound", phases)
        self.assertNotIn("claim_succeeded", phases)
        journal = (reopened.transaction_root / "checkpoints.jsonl").read_text(
            encoding="ascii"
        )
        self.assertIn('"candidate_cleanup_receipt_sha256"', journal)
        self.assertNotIn('"approval_reference_sha256"', journal)
        cleanup_completed = reopened.exact_cleanup(
            cleanup_authority_sha256=digest("cleanup-after-cancel")
        )
        if os.name == "nt":
            self.assertTrue(cleanup_completed)
        else:
            self.assertFalse(cleanup_completed)
            tombstone = (
                reopened.transaction_root.parent
                / f".cleanup_{reopened.transaction_ref}"
            )
            self.assertTrue(tombstone.is_dir())
            self.assertFalse(
                (
                    tombstone.parent
                    / f".cleanup-proof_{reopened.transaction_ref}.json"
                ).exists()
            )

    def test_claimless_cancel_false_or_exception_appends_zero_checkpoints(
        self,
    ) -> None:
        transaction = self.create_transaction()
        lock_bytes = self.activate(transaction)
        live = self.live_pre()
        transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=live,
        )
        journal_path = transaction.transaction_root / "checkpoints.jsonl"
        before = journal_path.read_bytes()

        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: transaction.begin_claimless_cancel_before_approval(
                expected_lock_bytes=lock_bytes,
                live_component_sha256=live,
                confirm_claim_store_empty=lambda: False,
            ),
        )
        self.assertEqual(journal_path.read_bytes(), before)

        def fail_confirmation() -> bool:
            raise RuntimeError("synthetic claim-store read failure")

        with self.assertRaisesRegex(
            RuntimeError,
            "synthetic claim-store read failure",
        ):
            transaction.begin_claimless_cancel_before_approval(
                expected_lock_bytes=lock_bytes,
                live_component_sha256=live,
                confirm_claim_store_empty=fail_confirmation,
            )
        self.assertEqual(journal_path.read_bytes(), before)

    def test_claimless_cancel_recheck_and_append_share_nonblocking_guard(
        self,
    ) -> None:
        transaction = self.create_transaction()
        lock_bytes = self.activate(transaction)
        live = self.live_pre()
        transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=live,
        )
        callback_observations: list[str] = []

        def confirm_empty_while_publisher_is_blocked() -> bool:
            with self.assertRaises(ProjectUpdateTransactionError) as caught:
                with transaction.append_guard_nonblocking():
                    self.fail("a second publisher acquired append.guard")
            callback_observations.append(caught.exception.code)
            return True

        requested = transaction.begin_claimless_cancel_before_approval(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
            confirm_claim_store_empty=(
                confirm_empty_while_publisher_is_blocked
            ),
        )

        self.assertEqual(requested.phase, "preapproval_cancel_requested")
        self.assertEqual(
            callback_observations,
            ["project_update_transaction_checkpoint_write_failed"],
        )
        with transaction.append_guard_nonblocking():
            pass

    def test_claim_publication_boundary_rejects_durable_cancel_intent(
        self,
    ) -> None:
        transaction = self.create_transaction()
        lock_bytes = self.activate(transaction)
        live = self.live_pre()
        transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=live,
        )
        transaction.begin_claimless_cancel_before_approval(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
            confirm_claim_store_empty=lambda: True,
        )

        with transaction.append_guard_nonblocking():
            self.assert_code(
                "project_update_transaction_state_transition_invalid",
                lambda: transaction
                .validate_claim_publication_boundary_guard_held(
                    expected_lock_bytes=lock_bytes,
                    live_component_sha256=live,
                ),
            )

    def test_claim_publication_boundary_blocks_claimless_cancel_nonblocking(
        self,
    ) -> None:
        transaction = self.create_transaction()
        lock_bytes = self.activate(transaction)
        live = self.live_pre()
        transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=live,
        )

        with transaction.append_guard_nonblocking():
            tail = transaction.validate_claim_publication_boundary_guard_held(
                expected_lock_bytes=lock_bytes,
                live_component_sha256=live,
            )
            self.assertEqual(tail.phase, "lock_backlinked")
            self.assert_code(
                "project_update_transaction_checkpoint_write_failed",
                lambda: transaction.begin_claimless_cancel_before_approval(
                    expected_lock_bytes=lock_bytes,
                    live_component_sha256=live,
                    confirm_claim_store_empty=lambda: True,
                ),
            )
        self.assertEqual(
            [
                item.phase
                for item in transaction.inspect().journal.verified_prefix
            ],
            ["lock_backlinked"],
        )

    def test_missing_claim_store_final_recheck_race_appends_nothing(
        self,
    ) -> None:
        transaction = self.create_transaction()
        lock_bytes = self.activate(transaction)
        live = self.live_pre()
        transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=live,
        )
        archive_root = self.project / "client-archive"
        archive_root.mkdir()
        (archive_root / "archive.yml").write_text(
            "archive_id: client-archive\n",
            encoding="utf-8",
        )
        state = SimpleNamespace(
            transaction=transaction,
            expected_lock_bytes=lock_bytes,
            expected_approval_root=archive_root,
            expected_archive_id="client-archive",
            inspection_root=self.project,
        )
        handler = archive_services._project_update_candidate_missing_handler(
            state,
            operator_resume_identifiers_supplied=False,
        )
        journal_path = transaction.transaction_root / "checkpoints.jsonl"
        before = journal_path.read_bytes()
        callback_entered = threading.Event()
        continue_recheck = threading.Event()
        failures: list[BaseException] = []
        original_recheck = (
            archive_services._project_update_claim_store_absent_read_only
        )

        def delayed_recheck(current_state) -> bool:
            callback_entered.set()
            if not continue_recheck.wait(timeout=10):
                raise RuntimeError("claim-store race test timed out")
            return original_recheck(current_state)

        def run_handler() -> None:
            try:
                handler("claim_store_absent")
            except BaseException as failure:
                failures.append(failure)

        def acquire_append_guard_again() -> None:
            with transaction.append_guard_nonblocking():
                self.fail("a second actor acquired append.guard")

        claims_root = archive_root.joinpath(
            "profiles",
            "local",
            "exact-human-approvals",
            "claims",
        )
        with (
            patch.object(
                archive_services,
                "_project_update_live_component_sha256",
                return_value=live,
            ),
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_approval_authority_matches",
                return_value=True,
            ),
            patch.object(
                archive_services,
                "_project_update_claim_store_absent_read_only",
                side_effect=delayed_recheck,
            ),
        ):
            worker = threading.Thread(target=run_handler, daemon=True)
            worker.start()
            try:
                self.assertTrue(callback_entered.wait(timeout=10))
                self.assert_code(
                    "project_update_transaction_checkpoint_write_failed",
                    acquire_append_guard_again,
                )
                claims_root.mkdir(parents=True)
            finally:
                continue_recheck.set()
                worker.join(timeout=10)

        self.assertFalse(worker.is_alive())
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], ProjectUpdateTransactionError)
        self.assertEqual(
            getattr(failures[0], "code", None),
            "project_update_transaction_state_transition_invalid",
        )
        self.assertEqual(journal_path.read_bytes(), before)

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_resume_missing_handler_reuses_state_and_preserves_client_tree(
        self,
    ) -> None:
        (
            transaction,
            lock_bytes,
            prepared_runtime_candidate,
        ) = self.create_transaction_with_prepared_runtime_candidate()
        live = self.live_pre()
        transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=live,
        )
        archive_root = self.project / "client-archive"
        archive_root.mkdir()
        (archive_root / "archive.yml").write_text(
            "archive_id: client-archive\n",
            encoding="utf-8",
        )
        (archive_root / "sentinel.bin").write_bytes(b"client archive")

        def archive_tree() -> dict[str, tuple[str, bytes | None]]:
            return {
                path.relative_to(archive_root).as_posix(): (
                    "directory",
                    None,
                )
                if path.is_dir()
                else ("file", path.read_bytes())
                for path in archive_root.rglob("*")
            }

        client_before = archive_tree()
        closed: list[str] = []
        state = SimpleNamespace(
            inspection_root=self.project,
            project_root=self.project,
            transaction=transaction,
            expected_lock_bytes=lock_bytes,
            expected_approval_root=archive_root,
            expected_archive_id="client-archive",
            prepared_preview={"status": "prepared"},
            reviewer="reviewer-a",
            runtime_candidate=prepared_runtime_candidate,
            directory_guard=SimpleNamespace(
                close=lambda: closed.append("directory")
            ),
            terminal_update_verified=False,
        )
        lifetime = SimpleNamespace(
            close_after_service_transaction=lambda: closed.append("runner")
        )
        executor_calls: list[tuple[tuple[object, ...], set[str]]] = []

        def approval_executor(*args, **kwargs):
            executor_calls.append((args, set(kwargs)))
            handler = kwargs["candidate_missing_handler"]
            journal_path = transaction.transaction_root / "checkpoints.jsonl"
            before = journal_path.read_bytes()
            with self.assertRaises(archive_services.ArchiveServiceError):
                handler("unexpected_missing_reason")
            self.assertEqual(journal_path.read_bytes(), before)
            return handler("authenticated_candidate_missing")

        def cleanup_candidate(candidate):
            capsule, _evidence = self.prepare_typed_runtime_cleanup_capsule(
                transaction,
                candidate,
            )
            return capsule

        with (
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_approval_authority_matches",
                return_value=True,
            ),
            patch.object(
                archive_services,
                "_project_update_resume_preapproval_transaction",
                return_value=None,
            ),
            patch.object(
                archive_services,
                "_project_update_reopen_durable_state",
                return_value=(state, lifetime),
            ) as reopen,
            patch.object(
                archive_services,
                "_project_update_live_component_sha256",
                return_value=live,
            ),
            patch.object(
                archive_services.project_runtime,
                "cleanup_prepared_runtime_candidate",
                side_effect=cleanup_candidate,
            ),
        ):
            result = (
                archive_services
                ._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=approval_executor,
                    _expected_approval_root=archive_root,
                    _expected_archive_id="client-archive",
                    _approval_identifier_supplied=True,
                )
            )

        self.assertEqual(result["status"], "preapproval_scaffold_cancelled")
        self.assertTrue(result["operator_resume_identifiers_supplied"])
        self.assert_preapproval_cancel_effect_truth(
            result,
            live_lock_verified=True,
            reservation_abort_evidence=False,
            candidate_cleanup=True,
        )
        self.assertEqual(reopen.call_count, 1)
        self.assertEqual(len(executor_calls), 1)
        self.assertEqual(len(executor_calls[0][0]), 6)
        self.assertEqual(
            executor_calls[0][1],
            {"candidate_missing_handler"},
        )
        self.assertEqual(executor_calls[0][0][5], "reviewer-a")
        self.assertEqual(closed, ["directory", "runner"])
        self.assertEqual(archive_tree(), client_before)

    def test_resume_returns_verified_update_when_only_followup_cleanup_is_unverified(
        self,
    ) -> None:
        cases = (
            ("transaction_cleanup", False, False, False),
            ("service_resource_close", True, True, False),
            ("runner_close", True, False, True),
            ("both_closes", True, True, True),
            ("fully_clean", True, False, False),
        )
        for (
            label,
            cleanup_completed,
            service_resource_close_fails,
            runner_close_fails,
        ) in cases:
            with self.subTest(case=label):
                closed: list[str] = []
                progress: list[tuple[str, str]] = []

                def close_service_resources() -> None:
                    closed.append("directory")
                    if service_resource_close_fails:
                        raise OSError("synthetic service-resource close")

                state = SimpleNamespace(
                    prepared_preview={"status": "prepared"},
                    reviewer="person:sealed-reviewer",
                    directory_guard=SimpleNamespace(
                        close=close_service_resources
                    ),
                    terminal_update_verified=False,
                    transaction_cleanup_completed=None,
                    terminal_domain_result=None,
                    terminal_handoff_sha256=None,
                )

                def close_runner() -> None:
                    closed.append("runner")
                    if runner_close_fails:
                        raise (
                            archive_services.project_update_git_runner
                            .ProjectUpdateGitRunnerError(
                                "project_update_git_runner_close_unverified"
                            )
                        )

                lifetime = SimpleNamespace(
                    close_after_service_transaction=close_runner
                )

                def approval_executor(*_args, **_kwargs):
                    domain_result = {
                        "ok": True,
                        "status": "updated_restart_required",
                        "warnings": [],
                        "next_safe_actions": ["restart"],
                    }
                    state.terminal_update_verified = True
                    state.transaction_cleanup_completed = cleanup_completed
                    state.terminal_domain_result = dict(domain_result)
                    state.terminal_handoff_sha256 = "sha256:" + "a" * 64
                    return domain_result

                def cleanup_gate(*_args, **kwargs):
                    observed = kwargs.get("_handoff_observation_out")
                    if isinstance(observed, list):
                        observed.append(None)
                    return None

                with (
                    patch.object(
                        archive_services,
                        "_project_update_terminal_cleanup_unknown_gate_read_only",
                        side_effect=cleanup_gate,
                    ),
                    patch.object(
                        archive_services,
                        "_project_update_resume_preapproval_transaction",
                        return_value=None,
                    ),
                    patch.object(
                        archive_services,
                        "_project_update_reopen_durable_state",
                        return_value=(state, lifetime),
                    ),
                    patch.object(
                        archive_services,
                        "_project_update_terminal_execution_lease",
                        return_value=nullcontext(),
                    ),
                ):
                    result = archive_services._wom_kit_project_version_update_resume_live_transaction(
                        self.project,
                        target=None,
                        reviewed_by=None,
                        transaction_ref=None,
                        approval_executor=approval_executor,
                        progress_callback=lambda stage, message, _current, _total: progress.append(
                            (stage, message)
                        ),
                        _expected_approval_root=self.project,
                        _expected_archive_id="archive-identity",
                    )

                terminal = result["terminal_finalization"]
                self.assertTrue(result["ok"])
                self.assertEqual(result["status"], "updated_restart_required")
                self.assertTrue(
                    terminal["update_result_verified_in_current_invocation"]
                )
                self.assertIs(
                    terminal["transaction_cleanup_completed"],
                    cleanup_completed,
                )
                self.assertIs(
                    terminal["service_resource_close_verified"],
                    not service_resource_close_fails,
                )
                self.assertIs(
                    terminal["git_runner_close_verified"],
                    not runner_close_fails,
                )
                self.assertTrue(terminal["attention_required"])
                self.assertFalse(
                    terminal["durable_result_delivery_acknowledged"]
                )
                self.assertFalse(
                    terminal["cleanup_proof_used_as_success_authority"]
                )
                self.assertFalse(terminal["domain_writer_reentry_allowed"])
                self.assertFalse(terminal["automatic_retry_allowed"])
                self.assertEqual(closed, ["directory", "runner"])
                self.assertEqual(
                    progress,
                    [
                        ("project-preflight", "resume-start"),
                        ("verify-release", "resume-authenticated-state"),
                        ("write-receipt", "resume-terminal-result"),
                    ],
                )
                rendered = json.dumps(result, ensure_ascii=False)
                self.assertNotIn(str(self.project), rendered)
                self.assertNotIn("transaction_ref", rendered)
                self.assertNotIn("approval_id", rendered)
                self.assertNotIn("exact_human_approval", rendered)

    def test_resume_keeps_preterminal_domain_failure_when_both_closes_fail(
        self,
    ) -> None:
        closed: list[str] = []

        def close_service_resources() -> None:
            closed.append("directory")
            raise OSError("synthetic service-resource close")

        state = SimpleNamespace(
            prepared_preview={"status": "prepared"},
            reviewer="person:sealed-reviewer",
            directory_guard=SimpleNamespace(
                close=close_service_resources
            ),
            terminal_update_verified=False,
            transaction_cleanup_completed=None,
        )

        def close_runner() -> None:
            closed.append("runner")
            raise (
                archive_services.project_update_git_runner
                .ProjectUpdateGitRunnerError(
                    "project_update_git_runner_close_unverified"
                )
            )

        def approval_executor(*_args, **_kwargs):
            raise archive_services.ArchiveServiceError(
                "synthetic_domain_failure"
            )

        def cleanup_gate(*_args, **kwargs):
            observed = kwargs.get("_handoff_observation_out")
            if isinstance(observed, list):
                observed.append(None)
            return None

        with (
            patch.object(
                archive_services,
                "_project_update_terminal_cleanup_unknown_gate_read_only",
                side_effect=cleanup_gate,
            ),
            patch.object(
                archive_services,
                "_project_update_resume_preapproval_transaction",
                return_value=None,
            ),
            patch.object(
                archive_services,
                "_project_update_reopen_durable_state",
                return_value=(
                    state,
                    SimpleNamespace(
                        close_after_service_transaction=close_runner
                    ),
                ),
            ),
            patch.object(
                archive_services,
                "_project_update_terminal_execution_lease",
                return_value=nullcontext(),
            ),
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "synthetic_domain_failure",
            ):
                archive_services._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=approval_executor,
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive-identity",
                )

        self.assertEqual(closed, ["directory", "runner"])

    def test_fresh_next_failure_preserves_primary_when_both_closes_fail(
        self,
    ) -> None:
        closed: list[str] = []
        primary = archive_services.ArchiveServiceError(
            "synthetic_primary_failure"
        )

        class FailingTransaction:
            def __next__(self):
                raise primary

            def close(self) -> None:
                closed.append("service")
                raise SystemExit("private service close failure")

        lifetime = SimpleNamespace(
            close_after_service_transaction=lambda: (
                closed.append("runner"),
                (_ for _ in ()).throw(
                    KeyboardInterrupt("private runner close failure")
                ),
            )[-1]
        )
        with (
            patch.object(
                archive_services,
                "_ProjectVersionUpdateGitRunnerLifetime",
                return_value=lifetime,
            ),
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_legacy_core_generator",
                return_value=FailingTransaction(),
            ),
        ):
            with self.assertRaises(archive_services.ArchiveServiceError) as caught:
                archive_services._wom_kit_project_version_update_legacy_core(
                    self.project,
                    target="v0.4.16",
                )

        self.assertIs(caught.exception, primary)
        self.assertEqual(closed, ["service", "runner"])

    def test_fresh_missing_executor_and_legacy_executor_failure_close_all(
        self,
    ) -> None:
        for mode in ("missing_executor", "executor_failure"):
            with self.subTest(mode=mode):
                closed: list[str] = []
                primary = archive_services.ArchiveServiceError(
                    "synthetic_legacy_executor_failure"
                )

                class PreparedTransaction:
                    def __next__(self):
                        return {"status": "prepared"}

                    def close(self) -> None:
                        closed.append("service")
                        raise SystemExit("private service close failure")

                def close_runner() -> None:
                    closed.append("runner")
                    raise KeyboardInterrupt("private runner close failure")

                lifetime = SimpleNamespace(
                    close_after_service_transaction=close_runner
                )
                with (
                    patch.object(
                        archive_services,
                        "_ProjectVersionUpdateGitRunnerLifetime",
                        return_value=lifetime,
                    ),
                    patch.object(
                        archive_services,
                        "_wom_kit_project_version_update_legacy_core_generator",
                        return_value=PreparedTransaction(),
                    ),
                ):
                    if mode == "missing_executor":
                        with self.assertRaisesRegex(
                            archive_services.ArchiveServiceError,
                            "project_version_update_live_approval_executor_required",
                        ):
                            archive_services._wom_kit_project_version_update_legacy_core(
                                self.project,
                                target="v0.4.16",
                            )
                    else:
                        with self.assertRaises(
                            archive_services.ArchiveServiceError
                        ) as caught:
                            archive_services._wom_kit_project_version_update_legacy_core(
                                self.project,
                                target="v0.4.16",
                                approval_executor=(
                                    lambda *_args, **_kwargs: (_ for _ in ()).throw(
                                        primary
                                    )
                                ),
                            )
                        self.assertIs(caught.exception, primary)

                self.assertEqual(closed, ["service", "runner"])

    def test_fresh_nonterminal_mapping_survives_both_close_failures(
        self,
    ) -> None:
        closed: list[str] = []

        class CompletedTransaction:
            def __next__(self):
                raise StopIteration(
                    {"ok": False, "status": "blocked"}
                )

            def close(self) -> None:
                closed.append("service")
                raise SystemExit("private service close failure")

        def close_runner() -> None:
            closed.append("runner")
            raise KeyboardInterrupt("private runner close failure")

        with (
            patch.object(
                archive_services,
                "_ProjectVersionUpdateGitRunnerLifetime",
                return_value=SimpleNamespace(
                    close_after_service_transaction=close_runner
                ),
            ),
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_legacy_core_generator",
                return_value=CompletedTransaction(),
            ),
        ):
            result = archive_services._wom_kit_project_version_update_legacy_core(
                self.project,
                target="v0.4.16",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(closed, ["service", "runner"])
        self.assertFalse(
            result["service_finalization"][
                "service_resource_close_verified"
            ]
        )
        self.assertFalse(
            result["service_finalization"]["git_runner_close_verified"]
        )

    def test_claimless_cancel_preserves_primary_when_both_closes_fail(
        self,
    ) -> None:
        closed: list[str] = []
        primary = archive_services.ArchiveServiceError(
            "synthetic_claimless_primary_failure"
        )

        def close_service() -> None:
            closed.append("service")
            raise SystemExit("private service close failure")

        def close_runner() -> None:
            closed.append("runner")
            raise KeyboardInterrupt("private runner close failure")

        state = SimpleNamespace(
            transaction=SimpleNamespace(
                _lock_path=self.project / "missing-version-update.lock"
            ),
            directory_guard=SimpleNamespace(close=close_service),
        )
        with (
            patch.object(
                archive_services,
                "_project_update_reopen_durable_state",
                return_value=(
                    state,
                    SimpleNamespace(
                        close_after_service_transaction=close_runner
                    ),
                ),
            ),
            patch.object(
                archive_services,
                "_project_update_cancel_claimless_preapproval_state",
                side_effect=primary,
            ),
        ):
            with self.assertRaises(archive_services.ArchiveServiceError) as caught:
                archive_services._wom_kit_project_version_update_cancel_claimless_preapproval_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    confirm_claim_store_empty=lambda: True,
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive-identity",
                )

        self.assertIs(caught.exception, primary)
        self.assertEqual(closed, ["service", "runner"])

    def test_sealed_preapproval_cancel_preserves_primary_when_both_closes_fail(
        self,
    ) -> None:
        metadata_root = self.project / ".zettel-kasten"
        metadata_root.mkdir()
        lock_path = metadata_root / "version-update.lock"
        lock_path.write_bytes(b"synthetic lock")
        transaction_ref = self.DEFAULT_TRANSACTION_REF
        closed: list[str] = []
        primary = archive_services.ArchiveServiceError(
            "synthetic_preapproval_primary_failure"
        )

        def close_service() -> None:
            closed.append("service")
            raise SystemExit("private service close failure")

        def close_runner() -> None:
            closed.append("runner")
            raise KeyboardInterrupt("private runner close failure")

        reopened_transaction = SimpleNamespace(
            inspect=lambda: SimpleNamespace(
                journal=SimpleNamespace(verified_prefix=())
            ),
            append=lambda **_kwargs: None,
        )
        state = SimpleNamespace(
            transaction=reopened_transaction,
            directory_guard=SimpleNamespace(close=close_service),
        )
        reservation = SimpleNamespace(
            existing_lock_bytes_read_only=lambda: b"synthetic lock"
        )
        sealed_transaction = SimpleNamespace(
            bind_sealed_intent_to_lock=lambda _lock: None
        )
        lifetime = SimpleNamespace(
            close_after_service_transaction=close_runner
        )
        with (
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_approval_authority_matches",
                return_value=True,
            ),
            patch.object(
                archive_services.project_update_transaction,
                "active_transaction_ref_from_lock_read_only",
                return_value=transaction_ref,
            ),
            patch.object(
                archive_services.project_update_transaction,
                "inspect_prelock_orphans",
                return_value=[
                    SimpleNamespace(
                        transaction_ref=transaction_ref,
                        classification="intent_sealed_lock_binding_incomplete",
                    )
                ],
            ),
            patch.object(
                archive_services.project_update_transaction.ReservedProjectUpdateTransaction,
                "open",
                return_value=reservation,
            ),
            patch.object(
                archive_services.project_update_transaction.ProjectUpdateTransaction,
                "open",
                return_value=sealed_transaction,
            ),
            patch.object(
                archive_services,
                "_project_update_reopen_durable_state",
                return_value=(state, lifetime),
            ),
            patch.object(
                archive_services,
                "_project_update_live_component_sha256",
                return_value={},
            ),
            patch.object(
                archive_services,
                "_project_update_cancel_before_native",
                side_effect=primary,
            ),
        ):
            with self.assertRaises(archive_services.ArchiveServiceError) as caught:
                archive_services._project_update_resume_preapproval_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    expected_approval_root=self.project,
                    expected_archive_id="archive-identity",
                    approval_identifier_supplied=False,
                )

        self.assertIs(caught.exception, primary)
        self.assertEqual(closed, ["service", "runner"])

    def test_claimless_cancel_mapping_survives_both_close_failures(
        self,
    ) -> None:
        closed: list[str] = []

        def close_service() -> None:
            closed.append("service")
            raise OSError("private service close failure")

        def close_runner() -> None:
            closed.append("runner")
            raise OSError("private runner close failure")

        state = SimpleNamespace(
            transaction=SimpleNamespace(
                _lock_path=self.project / "missing-version-update.lock"
            ),
            directory_guard=SimpleNamespace(close=close_service),
        )
        with (
            patch.object(
                archive_services,
                "_project_update_reopen_durable_state",
                return_value=(
                    state,
                    SimpleNamespace(
                        close_after_service_transaction=close_runner
                    ),
                ),
            ),
            patch.object(
                archive_services,
                "_project_update_cancel_claimless_preapproval_state",
                return_value=None,
            ),
        ):
            result = archive_services._wom_kit_project_version_update_cancel_claimless_preapproval_transaction(
                self.project,
                target=None,
                reviewed_by=None,
                transaction_ref=None,
                confirm_claim_store_empty=lambda: True,
                _expected_approval_root=self.project,
                _expected_archive_id="archive-identity",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "preapproval_scaffold_cancelled")
        self.assertEqual(closed, ["service", "runner"])
        self.assertEqual(
            result["service_finalization"],
            {
                "schema": "wom-kit/project-version-update-service-finalization/v0.4.16",
                "service_resource_close_verified": False,
                "git_runner_close_verified": False,
                "attention_required": True,
                "private_paths_echoed": False,
                "private_identifiers_echoed": False,
                "raw_errors_echoed": False,
            },
        )
        self.assertTrue(result["post_service_attention_required"])
        rendered = json.dumps(result)
        self.assertNotIn("private service close failure", rendered)
        self.assertNotIn("private runner close failure", rendered)

    def test_nonterminal_domain_mapping_survives_each_close_failure(
        self,
    ) -> None:
        for service_fails, runner_fails in (
            (True, False),
            (False, True),
            (True, True),
        ):
            with self.subTest(
                service_fails=service_fails,
                runner_fails=runner_fails,
            ):
                closed: list[str] = []

                def close_service() -> None:
                    closed.append("service")
                    if service_fails:
                        raise OSError("private service close failure")

                def close_runner() -> None:
                    closed.append("runner")
                    if runner_fails:
                        raise OSError("private runner close failure")

                result = archive_services._project_update_finish_service_result(
                    {"ok": False, "status": "domain_blocked"},
                    SimpleNamespace(terminal_update_verified=False),
                    SimpleNamespace(
                        close_after_service_transaction=close_runner
                    ),
                    close_owned_resources=close_service,
                )

                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], "domain_blocked")
                self.assertEqual(closed, ["service", "runner"])
                finalization = result["service_finalization"]
                self.assertIs(
                    finalization["service_resource_close_verified"],
                    not service_fails,
                )
                self.assertIs(
                    finalization["git_runner_close_verified"],
                    not runner_fails,
                )
                self.assertTrue(finalization["attention_required"])
                rendered = json.dumps(result)
                self.assertNotIn("private service close failure", rendered)
                self.assertNotIn("private runner close failure", rendered)

    def test_terminal_domain_projection_recursively_removes_private_locators(
        self,
    ) -> None:
        transaction_ref = "update_" + "a" * 32
        approval_id = "approval_" + "b" * 32
        transaction_locator = (
            ".zettel-kasten/private/version-updates/"
            f"{transaction_ref}"
        )
        candidate_locator = f"{transaction_locator}/runtime-candidate"
        result = {
            "ok": True,
            "status": "updated_restart_required",
            "transaction": {
                "transaction_ref": transaction_ref,
                "transaction_logical_ref": transaction_locator,
                "checkpoint_count": 8,
            },
            "project_runtime": {
                "runtime_candidate": {
                    "transaction_ref": transaction_ref,
                    "candidate_locator": candidate_locator,
                    "seal_locator": (
                        ".zettel-kasten/private/version-updates/"
                        f"{transaction_ref}/runtime-candidate-seal.json"
                    ),
                    "verified": True,
                },
            },
            "receipt": {
                "path": (
                    ".zettel-kasten/receipts/version-updates/"
                    f"{transaction_ref}.json"
                ),
                "written": True,
                "sha256": digest("terminal receipt"),
            },
            "files_written": [
                ".zettel-kasten/receipts/version-updates/"
                f"{transaction_ref}.json",
            ],
            "nested": [
                {
                    "approval_id": approval_id,
                    "summary": f"receipt for {transaction_ref}",
                },
                {"local_path": r"C:\private\project\receipt.json"},
                {"scratch": ".wom-scratch/private/terminal/state.json"},
                {"private_root": ".zettel-kasten/private"},
                {"scratch_root": ".wom-scratch/private"},
                {
                    "file_uri": (
                        "receipt at file:///" + "home/private/item.json"
                    )
                },
                {"unc": r"receipt at \\server\share\item.json"},
                {"posix": "receipt at /" + "home/private/item.json"},
                {"windows_rooted": r"receipt at \Users\private\item.json"},
                {"workspace": "receipt at /workspace/private/item.json"},
                {"srv": "receipt at /srv/private/item.json"},
                {"volumes": "receipt at /Volumes/private/item.json"},
                {"work_rooted": r"receipt at \Work\private\item.json"},
                {"embedded_drive": r"path:C:\private\item.json"},
                {"colon_posix": "path:/workspace/private/item.json"},
                {"colon_unc": r"path:\\server\share\item.json"},
                {"api_like_local_path": "/api/private/client.db"},
                {
                    "protocol_relative_local_path": (
                        "//private-server/share/client.db"
                    )
                },
                {"backtick_posix": "saved at `/workspace/private/item.json`"},
                {"bracket_unc": r"saved at [\\server\share\item.json]"},
                {"locator_echo": candidate_locator},
                {
                    "unknown_private_tail": (
                        f"{transaction_locator}/client-secret-name.json"
                    )
                },
            ],
            "dynamic_keys": {
                transaction_ref: "redacted key",
                approval_id: "redacted key",
            },
            "public_routes": {
                "docs": "//docs.example.com/public",
                "api": "/api/v1/status",
                "local_path": "/api/private/client.db",
                "DOCS": "//private-server/share/client.db",
                "API": "/api/private/client.db",
            },
            "wrapper": {
                "public_routes": {
                    "docs": "//private-server/share/client.db",
                    "api": "/api/private/client.db",
                }
            },
            "dynamic_route_key": {
                "//private-server/share/client.db": "value",
            },
            "operation_exact_human_approval": {
                "approval_id": approval_id,
            },
        }

        projected = archive_services._project_update_privacy_safe_domain_result(
            result
        )
        rendered = json.dumps(projected, ensure_ascii=False)

        self.assertNotIn(transaction_ref, rendered)
        self.assertNotIn(approval_id, rendered)
        self.assertNotIn(".zettel-kasten/private/", rendered)
        self.assertNotIn(".wom-scratch/private/", rendered)
        self.assertNotIn(r"C:\private\project", rendered)
        self.assertIsNone(
            re.search(r"(?i)(?:update|approval)_[0-9a-f]{32}", rendered)
        )
        self.assertNotIn("operation_exact_human_approval", projected)
        self.assertEqual(
            projected["transaction"],
            {"checkpoint_count": 8},
        )
        self.assertEqual(
            projected["project_runtime"]["runtime_candidate"],
            {"verified": True},
        )
        self.assertEqual(
            projected["receipt"],
            {
                "path": (
                    ".zettel-kasten/receipts/version-updates/"
                    "<private-transaction>.json"
                ),
                "written": True,
                "sha256": digest("terminal receipt"),
            },
        )
        self.assertEqual(
            projected["files_written"],
            [
                ".zettel-kasten/receipts/version-updates/"
                "<private-transaction>.json"
            ],
        )
        self.assertEqual(
            projected["nested"],
            [
                {"summary": "receipt for <private-transaction>"},
                {"local_path": "<private-local-path>"},
                {"scratch": "<private-project-metadata>"},
                {"private_root": "<private-project-metadata>"},
                {"scratch_root": "<private-project-metadata>"},
                {"file_uri": "<private-local-path>"},
                {"unc": "<private-local-path>"},
                {"posix": "<private-local-path>"},
                {"windows_rooted": "<private-local-path>"},
                {"workspace": "<private-local-path>"},
                {"srv": "<private-local-path>"},
                {"volumes": "<private-local-path>"},
                {"work_rooted": "<private-local-path>"},
                {"embedded_drive": "<private-local-path>"},
                {"colon_posix": "<private-local-path>"},
                {"colon_unc": "<private-local-path>"},
                {"api_like_local_path": "<private-local-path>"},
                {"protocol_relative_local_path": "<private-local-path>"},
                {"backtick_posix": "<private-local-path>"},
                {"bracket_unc": "<private-local-path>"},
                {"locator_echo": "<private-control-path>"},
                {"unknown_private_tail": "<private-project-metadata>"},
            ],
        )
        self.assertEqual(
            projected["dynamic_keys"],
            {
                "<private-transaction>": "redacted key",
                "<private-approval>": "redacted key",
            },
        )
        self.assertEqual(
            projected["public_routes"],
            {
                "docs": "//docs.example.com/public",
                "api": "/api/v1/status",
                "local_path": "<private-local-path>",
                "DOCS": "<private-local-path>",
                "API": "<private-local-path>",
            },
        )
        self.assertEqual(
            projected["wrapper"],
            {
                "public_routes": {
                    "docs": "<private-local-path>",
                    "api": "<private-local-path>",
                }
            },
        )
        self.assertEqual(
            projected["dynamic_route_key"],
            {"<private-local-path>": "value"},
        )
        self.assertEqual(
            projected["approval_verification"],
            {
                "exact_human_approval_succeeded": True,
                "one_use_claim_reauthenticated": True,
                "approval_identifiers_echoed": False,
                "private_paths_echoed": False,
            },
        )

        malformed_results = (
            {
                "ok": True,
                "status": "updated_restart_required",
                "unbound_control_identifier": "UPDATE_" + "e" * 32,
            },
            {"ok": True, "status": "updated_restart_required", "transaction_ref": "a"},
            {"ok": True, "status": "updated_restart_required", "approval_id": "e"},
            {"ok": True, "status": "updated_restart_required", "candidate_locator": "a"},
            {
                "ok": True,
                "status": "updated_restart_required",
                "transaction_ref": transaction_ref,
                "approval_id": approval_id,
                "claim_path": transaction_locator,
            },
            {
                "ok": True,
                "status": "updated_restart_required",
                "transaction_ref": transaction_ref,
                "approval_id": approval_id,
                "transaction_path": (
                    "profiles/local/exact-human-approvals/claims/"
                    f"{approval_id}.json"
                ),
            },
        )
        for malformed in malformed_results:
            with self.subTest(malformed=malformed), self.assertRaises(
                archive_services.ArchiveServiceError
            ):
                archive_services._project_update_privacy_safe_domain_result(
                    malformed
                )

        sequence_projection = (
            archive_services._project_update_privacy_safe_domain_result(
                {
                    "ok": True,
                    "status": "updated_restart_required",
                    "public_routes": {
                        "docs": ["//private-server/share/client.db"],
                        "api": ["/api/private/client.db"],
                    },
                }
            )
        )
        self.assertEqual(
            sequence_projection["public_routes"],
            {
                "docs": ["<private-local-path>"],
                "api": ["<private-local-path>"],
            },
        )

    def test_collision_mapping_and_primary_survive_runner_close_failure(
        self,
    ) -> None:
        for mode in ("mapping", "primary"):
            with self.subTest(mode=mode):
                closed: list[str] = []
                primary = archive_services.ArchiveServiceError(
                    "synthetic_collision_primary_failure"
                )

                def close_runner() -> None:
                    closed.append("runner")
                    raise SystemExit("private runner close failure")

                runner = SimpleNamespace(
                    close_transport_boundary=lambda: closed.append(
                        "transport"
                    ),
                    close=close_runner,
                )
                inner_result = {
                    "ok": False,
                    "status": "collision_state_recovery_required",
                    "service_finalization": {
                        "schema": "wom-kit/project-version-update-service-finalization/v0.4.16",
                        "service_resource_close_verified": False,
                        "git_runner_close_verified": True,
                        "attention_required": True,
                        "private_paths_echoed": False,
                        "private_identifiers_echoed": False,
                        "raw_errors_echoed": False,
                    },
                }
                inner_effect = (
                    primary if mode == "primary" else inner_result
                )
                with (
                    patch.object(
                        archive_services.project_update_git_runner.TrustedProjectUpdateGitRunner,
                        "resolve_preapproval",
                        return_value=runner,
                    ),
                    patch.object(
                        archive_services,
                        "_wom_kit_project_version_update_collision_legacy_core_with_runner",
                        side_effect=(
                            inner_effect
                            if isinstance(inner_effect, BaseException)
                            else None
                        ),
                        return_value=(
                            inner_effect
                            if not isinstance(inner_effect, BaseException)
                            else None
                        ),
                    ),
                ):
                    if mode == "primary":
                        with self.assertRaises(
                            archive_services.ArchiveServiceError
                        ) as caught:
                            archive_services._wom_kit_project_version_update_collision_legacy_core(
                                self.project,
                                target="v0.4.16",
                                entry_ref="entry",
                                action="preserve_relocate",
                            )
                        self.assertIs(caught.exception, primary)
                    else:
                        result = archive_services._wom_kit_project_version_update_collision_legacy_core(
                            self.project,
                            target="v0.4.16",
                            entry_ref="entry",
                            action="preserve_relocate",
                        )
                        self.assertEqual(
                            result["status"],
                            "collision_state_recovery_required",
                        )
                        self.assertFalse(
                            result["service_finalization"][
                                "service_resource_close_verified"
                            ]
                        )
                        self.assertFalse(
                            result["service_finalization"][
                                "git_runner_close_verified"
                            ]
                        )
                self.assertEqual(closed, ["transport", "runner"])

    def test_replayed_terminal_result_never_invents_close_proof(self) -> None:
        terminal = (
            archive_services
            ._project_update_replayed_terminal_finalization(
                cleanup_completed=True,
            )
        )
        result = archive_services._project_update_terminal_result_from_domain(
            {
                "ok": True,
                "status": "updated_restart_required",
                "warnings": [],
                "next_safe_actions": ["restart"],
            },
            terminal,
        )

        self.assertIsNotNone(result)
        self.assertTrue(result["ok"])
        replayed = result["terminal_finalization"]
        self.assertTrue(
            replayed["update_result_reauthenticated_from_durable_handoff"]
        )
        self.assertFalse(replayed["service_resource_close_verified"])
        self.assertFalse(replayed["git_runner_close_verified"])
        self.assertTrue(replayed["attention_required"])

    def test_terminal_success_survives_both_hard_close_failures(self) -> None:
        closed: list[str] = []
        domain = {
            "ok": True,
            "status": "updated_restart_required",
            "warnings": [],
            "next_safe_actions": ["restart"],
        }

        def close_service() -> None:
            closed.append("service")
            raise SystemExit("private service close failure")

        def close_runner() -> None:
            closed.append("runner")
            raise KeyboardInterrupt("private runner close failure")

        result = archive_services._project_update_finish_service_result(
            domain,
            SimpleNamespace(
                terminal_update_verified=True,
                transaction_cleanup_completed=True,
                terminal_domain_result=dict(domain),
                terminal_handoff_sha256="sha256:" + "a" * 64,
            ),
            SimpleNamespace(
                close_after_service_transaction=close_runner
            ),
            close_owned_resources=close_service,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "updated_restart_required")
        self.assertEqual(closed, ["service", "runner"])
        terminal = result["terminal_finalization"]
        self.assertFalse(terminal["service_resource_close_verified"])
        self.assertFalse(terminal["git_runner_close_verified"])
        self.assertTrue(terminal["attention_required"])

    def test_runner_lifetime_retains_authority_until_close_is_verified(
        self,
    ) -> None:
        calls: list[str] = []

        class RetryableRunner:
            def close(self) -> None:
                calls.append("close")
                if len(calls) == 1:
                    raise OSError("private runner close failure")

        runner = RetryableRunner()
        lifetime = archive_services._ProjectVersionUpdateGitRunnerLifetime()
        lifetime._runner = runner

        with self.assertRaisesRegex(
            OSError,
            "private runner close failure",
        ):
            lifetime.close_after_service_transaction()
        self.assertIs(lifetime._runner, runner)
        lifetime.close_after_service_transaction()
        self.assertIsNone(lifetime._runner)
        self.assertEqual(calls, ["close", "close"])

    @unittest.skipUnless(os.name == "nt", "Windows handle authority")
    def test_directory_guard_close_failure_keeps_handle_authority(
        self,
    ) -> None:
        guard = archive_services._WomKitProjectUpdateDirectoryGuard(
            self.project
        )
        guard._handles = {"first": 101, "second": 202}
        guard._identities = {
            "first": (1, 1),
            "second": (2, 2),
        }
        with patch.object(
            guard,
            "_close_handle",
            side_effect=[
                OSError("synthetic close failure"),
                None,
            ],
        ) as close_handle:
            with self.assertRaisesRegex(
                OSError,
                "project_update_directory_guard_close_failed",
            ):
                guard.close()
        self.assertEqual(close_handle.call_count, 2)
        self.assertEqual(guard._handles, {"first": 101})
        self.assertEqual(guard._identities, {"first": (1, 1)})
        with patch.object(guard, "_close_handle", return_value=None):
            guard.close()
        self.assertEqual(guard._handles, {})
        self.assertEqual(guard._identities, {})

    def test_directory_guard_checks_windows_closehandle_result(self) -> None:
        guard = object.__new__(
            archive_services._WomKitProjectUpdateDirectoryGuard
        )
        guard._kernel32 = SimpleNamespace(CloseHandle=lambda _handle: 0)
        with patch.object(archive_services.os, "name", "nt"):
            with self.assertRaisesRegex(
                OSError,
                "project_update_directory_guard_close_failed",
            ):
                guard._close_handle(101)

    def test_directory_guard_posix_close_error_is_never_retried(self) -> None:
        guard = archive_services._WomKitProjectUpdateDirectoryGuard(
            self.project
        )
        guard._handles = {"first": 303}
        guard._identities = {"first": (3, 3)}
        with (
            patch.object(archive_services.os, "name", "posix"),
            patch.object(
                archive_services.os,
                "close",
                side_effect=OSError("synthetic close failure"),
            ) as close_handle,
        ):
            with self.assertRaisesRegex(
                OSError,
                "project_update_directory_guard_close_failed",
            ):
                guard.close()
            self.assertEqual(guard._handles, {})
            self.assertEqual(guard._identities, {})
            guard.close()

        close_handle.assert_called_once_with(303)

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_delivery_atomic_rename_supports_two_updates(self) -> None:
        consumed_paths: list[Path] = []
        for label in ("first", "second"):
            fixture = self.prepare_terminal_delivery_fixture(label)
            acknowledged = (
                archive_services
                ._project_update_acknowledge_terminal_result_delivery(
                    self.project,
                    fixture["result"],
                    output_relative=str(fixture["output_relative"]),
                    run_id=str(fixture["run_id"]),
                    operation_ref=str(fixture["operation_ref"]),
                )
            )
            self.assertTrue(acknowledged)
            self.assertFalse(Path(fixture["handoff"]).exists())
            display_pending = (
                archive_services
                ._project_update_terminal_display_pending_path(
                    self.project
                )
            )
            self.assertEqual(
                display_pending.read_bytes(),
                fixture["handoff_raw"],
            )
            consumed = archive_services._project_update_terminal_consumed_path(
                self.project,
                str(fixture["handoff_sha256"]),
            )
            self.assertFalse(consumed.exists())
            finalized = (
                archive_services
                ._project_update_finalize_terminal_result_display(
                    self.project,
                    expected_handoff_sha256=str(
                        fixture["handoff_sha256"]
                    ),
                    delivery_capability=str(fixture["capability"]),
                )
            )
            self.assertTrue(finalized)
            self.assertFalse(display_pending.exists())
            self.assertEqual(
                consumed.read_bytes(),
                fixture["handoff_raw"],
            )
            consumed_before_retry = consumed.read_bytes()
            self.assertTrue(
                archive_services
                ._project_update_finalize_terminal_result_display(
                    self.project,
                    expected_handoff_sha256=str(
                        fixture["handoff_sha256"]
                    ),
                    delivery_capability=str(fixture["capability"]),
                )
            )
            self.assertEqual(consumed.read_bytes(), consumed_before_retry)
            consumed_paths.append(consumed)
        self.assertNotEqual(consumed_paths[0], consumed_paths[1])
        self.assertTrue(all(path.is_file() for path in consumed_paths))

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_delivery_acknowledgement_reuses_outer_lease_and_blocks_competitor(
        self,
    ) -> None:
        fixture = self.prepare_terminal_delivery_fixture(
            "outer-lease-acknowledgement"
        )
        handoff, _guard = (
            archive_services._project_update_terminal_handoff_paths(
                self.project
            )
        )
        display_pending = (
            archive_services._project_update_terminal_display_pending_path(
                self.project
            )
        )
        competing_acquired: list[bool] = []
        competing_finished = threading.Event()

        def competing_guard() -> None:
            try:
                with (
                    archive_services
                    ._project_update_terminal_control_boundary(self.project)
                ):
                    competing_acquired.append(True)
            except OSError:
                competing_acquired.append(False)
            finally:
                competing_finished.set()

        with archive_services._project_update_terminal_control_boundary(
            self.project
        ):
            competitor = threading.Thread(target=competing_guard)
            competitor.start()
            self.assertTrue(competing_finished.wait(timeout=5.0))
            competitor.join(timeout=5.0)
            self.assertFalse(competitor.is_alive())
            self.assertEqual(competing_acquired, [False])
            acknowledged = (
                archive_services
                ._project_update_acknowledge_terminal_result_delivery(
                    self.project,
                    fixture["result"],
                    output_relative=str(fixture["output_relative"]),
                    run_id=str(fixture["run_id"]),
                    operation_ref=str(fixture["operation_ref"]),
                )
            )

        self.assertTrue(acknowledged)
        self.assertFalse(handoff.exists())
        self.assertEqual(
            display_pending.read_bytes(),
            fixture["handoff_raw"],
        )
        self.assertFalse(
            archive_services._project_update_terminal_consumed_path(
                self.project,
                str(fixture["handoff_sha256"]),
            ).exists()
        )

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_stale_unbound_boundary_refuses_real_display_pending_before_output(
        self,
    ) -> None:
        initial = (
            archive_cli
            ._project_version_update_strict_active_handoff_snapshot(
                self.project
            )
        )
        self.assertIsNone(initial)
        fixture = self.prepare_terminal_delivery_fixture(
            "stale-real-display-pending"
        )
        acknowledged = (
            archive_services
            ._project_update_acknowledge_terminal_result_delivery(
                self.project,
                fixture["result"],
                output_relative=str(fixture["output_relative"]),
                run_id=str(fixture["run_id"]),
                operation_ref=str(fixture["operation_ref"]),
            )
        )
        self.assertTrue(acknowledged)

        handoff, _guard = (
            archive_services._project_update_terminal_handoff_paths(
                self.project
            )
        )
        display_pending = (
            archive_services._project_update_terminal_display_pending_path(
                self.project
            )
        )
        consumed = archive_services._project_update_terminal_consumed_path(
            self.project,
            str(fixture["handoff_sha256"]),
        )
        self.assertFalse(handoff.exists())
        self.assertEqual(
            display_pending.read_bytes(),
            fixture["handoff_raw"],
        )
        self.assertFalse(consumed.exists())

        diagnostics = self.project / ".zettel-kasten" / "diagnostics"
        diagnostics_before = {
            path.relative_to(diagnostics).as_posix(): path.read_bytes()
            for path in diagnostics.rglob("*")
            if path.is_file()
        }
        operations = self.project.joinpath(
            *archive_cli.operation_control.PROJECT_JOURNAL_RELATIVE.parts
        )
        self.assertFalse(os.path.lexists(operations))

        with ExitStack() as stale_stack:
            with self.assertRaises(
                archive_cli._ProjectVersionUpdateCleanupUnknownPreflight
            ) as raised:
                archive_cli._project_version_update_enter_unbound_terminal_delivery_boundary(
                    stale_stack,
                    self.project,
                    expected_observation=initial,
                )

        result = raised.exception.result
        self.assertEqual(result["status"], "terminal_cleanup_outcome_unknown")
        self.assertEqual(result["effects_state"], "unknown")
        self.assertFalse(result["archive_identity_metadata_read"])
        self.assertFalse(result["client_archive_domain_content_accessed"])
        self.assertFalse(result["domain_writer_entered"])
        self.assertEqual(result["files_written"], [])
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(str(self.project), serialized)
        self.assertIsNone(
            re.search(r"(?i)(?<![A-Za-z0-9])[A-Z]:[\\/]", serialized)
        )
        self.assertFalse(handoff.exists())
        self.assertEqual(
            display_pending.read_bytes(),
            fixture["handoff_raw"],
        )
        self.assertFalse(consumed.exists())
        self.assertEqual(
            {
                path.relative_to(diagnostics).as_posix(): path.read_bytes()
                for path in diagnostics.rglob("*")
                if path.is_file()
            },
            diagnostics_before,
        )
        self.assertFalse(os.path.lexists(operations))

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_delivery_waits_for_transaction_cleanup_before_ack(
        self,
    ) -> None:
        fixture = self.prepare_terminal_delivery_fixture(
            "cleanup-attention",
            terminal_overrides={
                "transaction_cleanup_completed": False,
                "service_resource_close_verified": False,
                "git_runner_close_verified": False,
            },
        )

        acknowledged = (
            archive_services
            ._project_update_acknowledge_terminal_result_delivery(
                self.project,
                fixture["result"],
                output_relative=str(fixture["output_relative"]),
                run_id=str(fixture["run_id"]),
                operation_ref=str(fixture["operation_ref"]),
            )
        )

        self.assertFalse(acknowledged)
        self.assertTrue(Path(fixture["handoff"]).is_file())
        self.assertFalse(
            archive_services
            ._project_update_terminal_display_pending_path(
                self.project
            )
            .exists()
        )
        self.assertFalse(
            archive_services._project_update_terminal_consumed_path(
                self.project,
                str(fixture["handoff_sha256"]),
            ).exists()
        )
        self.assertTrue(fixture["result"]["post_update_attention_required"])

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_delivery_is_independent_of_followup_close_attention(
        self,
    ) -> None:
        fixture = self.prepare_terminal_delivery_fixture(
            "followup-close-attention",
            terminal_overrides={
                "transaction_cleanup_completed": True,
                "service_resource_close_verified": False,
                "git_runner_close_verified": False,
            },
        )

        acknowledged = (
            archive_services
            ._project_update_acknowledge_terminal_result_delivery(
                self.project,
                fixture["result"],
                output_relative=str(fixture["output_relative"]),
                run_id=str(fixture["run_id"]),
                operation_ref=str(fixture["operation_ref"]),
            )
        )

        self.assertTrue(acknowledged)
        self.assertFalse(Path(fixture["handoff"]).exists())
        display_pending = (
            archive_services._project_update_terminal_display_pending_path(
                self.project
            )
        )
        self.assertEqual(
            display_pending.read_bytes(),
            fixture["handoff_raw"],
        )
        consumed = archive_services._project_update_terminal_consumed_path(
            self.project,
            str(fixture["handoff_sha256"]),
        )
        self.assertFalse(consumed.exists())
        self.assertTrue(
            archive_services
            ._project_update_finalize_terminal_result_display(
                self.project,
                expected_handoff_sha256=str(
                    fixture["handoff_sha256"]
                ),
                delivery_capability=str(fixture["capability"]),
            )
        )
        self.assertFalse(display_pending.exists())
        self.assertTrue(
            consumed.is_file()
        )
        self.assertTrue(fixture["result"]["post_update_attention_required"])

    def test_terminal_record_payload_uses_exact_human_canonical_bytes(
        self,
    ) -> None:
        document = {
            "schema": "wom-kit/test-terminal/v0.1",
            "message": "복구 완료",
        }
        payload = (
            archive_services._project_update_exact_terminal_payload_bytes(
                document
            )
        )
        self.assertEqual(
            exact_human_approval._terminal_record_payload(payload),
            payload,
        )
        self.assertTrue(payload.endswith(b"\n"))
        self.assertIn("복구 완료".encode("utf-8"), payload)
        with self.assertRaisesRegex(
            exact_human_approval.ExactHumanApprovalError,
            "exact_human_approval_terminal_record_payload_invalid",
        ):
            exact_human_approval._terminal_record_payload(
                canonical_json_bytes(document)
            )

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_write_creates_durable_same_directory_guard(self) -> None:
        handoff, guard = archive_services._project_update_terminal_handoff_paths(
            self.project
        )
        self.assertFalse(handoff.parent.exists())
        document = {
            "schema": archive_services._PROJECT_UPDATE_TERMINAL_HANDOFF_SCHEMA,
            "state": "terminal_pending",
        }

        written_sha256 = (
            archive_services._project_update_write_terminal_document_exact(
                self.project,
                handoff,
                document,
                expected_previous_value=None,
            )
        )

        self.assertEqual(guard.read_bytes(), b"\x00")
        self.assertEqual(handoff.parent, guard.parent)
        self.assertEqual(
            written_sha256,
            sha256_bytes(handoff.read_bytes()),
        )

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_initial_publication_race_never_replaces_foreign_file(
        self,
    ) -> None:
        handoff, _guard = archive_services._project_update_terminal_handoff_paths(
            self.project
        )
        document = {
            "schema": archive_services._PROJECT_UPDATE_TERMINAL_HANDOFF_SCHEMA,
            "state": "claim_succeeded_pre_unlock",
        }
        foreign_raw = archive_services._project_update_canonical_bytes(
            {"foreign": "initial-publication-race"}
        )
        if os.name == "nt":
            seam = "_project_update_terminal_windows_move_exact_no_replace"
            real_publish = getattr(archive_services, seam)

            def inject_destination(
                source: Path,
                destination: Path | None,
                **kwargs,
            ) -> bytes:
                if destination is None:
                    return real_publish(source, destination, **kwargs)
                destination.write_bytes(foreign_raw)
                return real_publish(source, destination, **kwargs)

        else:
            seam = "_project_update_terminal_posix_publish_unnamed_no_replace"
            real_publish = getattr(archive_services, seam)

            def inject_destination(
                binding: dict[str, object],
                destination: Path,
                raw: bytes,
                **kwargs,
            ) -> None:
                destination.write_bytes(foreign_raw)
                real_publish(binding, destination, raw, **kwargs)

        with patch.object(
            archive_services,
            seam,
            side_effect=inject_destination,
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "project_version_update_terminal_handoff_conflict",
            ):
                archive_services._project_update_write_terminal_document_exact(
                    self.project,
                    handoff,
                    document,
                    expected_previous_value=None,
                )

        self.assertEqual(handoff.read_bytes(), foreign_raw)

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_transition_race_never_replaces_changed_file(self) -> None:
        handoff, _guard = archive_services._project_update_terminal_handoff_paths(
            self.project
        )
        pending = {
            "schema": archive_services._PROJECT_UPDATE_TERMINAL_HANDOFF_SCHEMA,
            "state": "claim_succeeded_pre_unlock",
            "pending": {"record": "pending"},
        }
        ready = {
            "schema": archive_services._PROJECT_UPDATE_TERMINAL_HANDOFF_SCHEMA,
            "state": "terminal_ready",
            "pending": {"record": "pending"},
            "ready": {"record": "ready"},
        }
        archive_services._project_update_write_terminal_document_exact(
            self.project,
            handoff,
            pending,
            expected_previous_value=None,
        )
        foreign_raw = archive_services._project_update_canonical_bytes(
            {"foreign": "transition-race"}
        )
        real_cas = archive_services._replace_regular_file_bytes_compare_and_swap

        def inject_mutation(*args, **kwargs):
            handoff.write_bytes(foreign_raw)
            return real_cas(*args, **kwargs)

        with patch.object(
            archive_services,
            "_replace_regular_file_bytes_compare_and_swap",
            side_effect=inject_mutation,
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "project_version_update_terminal_handoff_conflict",
            ):
                archive_services._project_update_write_terminal_document_exact(
                    self.project,
                    handoff,
                    ready,
                    expected_previous_value=pending,
                )

        self.assertEqual(handoff.read_bytes(), foreign_raw)

    def test_terminal_handoff_access_error_is_not_treated_as_absence(
        self,
    ) -> None:
        handoff, _guard = archive_services._project_update_terminal_handoff_paths(
            self.project
        )
        with patch.object(
            archive_services.os,
            "lstat",
            side_effect=PermissionError("synthetic private access failure"),
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "project_version_update_terminal_handoff_invalid",
            ):
                archive_services._project_update_read_terminal_document(
                    self.project,
                    handoff,
                )

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_delivery_rejects_mutated_result_and_capability_mismatch(
        self,
    ) -> None:
        mutated = self.prepare_terminal_delivery_fixture(
            "mutated-result",
            result_domain_override={
                "ok": True,
                "status": "no_change",
                "warnings": [],
                "next_safe_actions": ["verify"],
            },
        )
        self.assertFalse(
            archive_services
            ._project_update_acknowledge_terminal_result_delivery(
                self.project,
                mutated["result"],
                output_relative=str(mutated["output_relative"]),
                run_id=str(mutated["run_id"]),
                operation_ref=str(mutated["operation_ref"]),
            )
        )
        self.assertTrue(Path(mutated["handoff"]).is_file())
        Path(mutated["handoff"]).unlink()

        wrong_capability = "hmac-sha256:" + "f" * 64
        mismatched = self.prepare_terminal_delivery_fixture(
            "capability-mismatch",
            proof_capability_override=wrong_capability,
        )
        self.assertFalse(
            archive_services
            ._project_update_acknowledge_terminal_result_delivery(
                self.project,
                mismatched["result"],
                output_relative=str(mismatched["output_relative"]),
                run_id=str(mismatched["run_id"]),
                operation_ref=str(mismatched["operation_ref"]),
            )
        )
        self.assertTrue(Path(mismatched["handoff"]).is_file())

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_delivery_rename_failure_preserves_active_handoff(
        self,
    ) -> None:
        fixture = self.prepare_terminal_delivery_fixture("rename-failure")
        with patch.object(
            archive_services.project_update_transaction,
            "_atomic_move_file_no_replace",
            side_effect=OSError("synthetic atomic rename failure"),
        ):
            acknowledged = (
                archive_services
                ._project_update_acknowledge_terminal_result_delivery(
                    self.project,
                    fixture["result"],
                    output_relative=str(fixture["output_relative"]),
                    run_id=str(fixture["run_id"]),
                    operation_ref=str(fixture["operation_ref"]),
                )
            )
        self.assertFalse(acknowledged)
        self.assertEqual(
            Path(fixture["handoff"]).read_bytes(),
            fixture["handoff_raw"],
        )
        self.assertFalse(
            archive_services
            ._project_update_terminal_display_pending_path(
                self.project
            )
            .exists()
        )
        self.assertFalse(
            archive_services._project_update_terminal_consumed_path(
                self.project,
                str(fixture["handoff_sha256"]),
            ).exists()
        )

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_delivery_destination_race_preserves_both_entries(self) -> None:
        fixture = self.prepare_terminal_delivery_fixture("destination-race")
        display_pending = (
            archive_services._project_update_terminal_display_pending_path(
                self.project
            )
        )
        foreign = b"foreign display-pending race occupant\n"
        real_move = (
            archive_services.project_update_transaction
            ._atomic_move_file_no_replace
        )

        def inject_destination(source: Path, destination: Path) -> None:
            self.assertEqual(destination, display_pending)
            destination.write_bytes(foreign)
            real_move(source, destination)

        with patch.object(
            archive_services.project_update_transaction,
            "_atomic_move_file_no_replace",
            side_effect=inject_destination,
        ):
            acknowledged = (
                archive_services
                ._project_update_acknowledge_terminal_result_delivery(
                    self.project,
                    fixture["result"],
                    output_relative=str(fixture["output_relative"]),
                    run_id=str(fixture["run_id"]),
                    operation_ref=str(fixture["operation_ref"]),
                )
            )

        self.assertFalse(acknowledged)
        self.assertEqual(
            Path(fixture["handoff"]).read_bytes(),
            fixture["handoff_raw"],
        )
        self.assertEqual(display_pending.read_bytes(), foreign)

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_finalize_destination_race_preserves_both_entries(self) -> None:
        fixture = self.prepare_terminal_delivery_fixture("finalize-race")
        self.assertTrue(
            archive_services._project_update_acknowledge_terminal_result_delivery(
                self.project,
                fixture["result"],
                output_relative=str(fixture["output_relative"]),
                run_id=str(fixture["run_id"]),
                operation_ref=str(fixture["operation_ref"]),
            )
        )
        display_pending = (
            archive_services._project_update_terminal_display_pending_path(
                self.project
            )
        )
        consumed = archive_services._project_update_terminal_consumed_path(
            self.project,
            str(fixture["handoff_sha256"]),
        )
        foreign = b"foreign consumed race occupant\n"
        real_move = (
            archive_services.project_update_transaction
            ._atomic_move_file_no_replace
        )

        def inject_destination(source: Path, destination: Path) -> None:
            self.assertEqual(source, display_pending)
            self.assertEqual(destination, consumed)
            destination.write_bytes(foreign)
            real_move(source, destination)

        with patch.object(
            archive_services.project_update_transaction,
            "_atomic_move_file_no_replace",
            side_effect=inject_destination,
        ):
            self.assertFalse(
                archive_services._project_update_finalize_terminal_result_display(
                    self.project,
                    expected_handoff_sha256=str(
                        fixture["handoff_sha256"]
                    ),
                    delivery_capability=str(fixture["capability"]),
                )
            )

        self.assertEqual(display_pending.read_bytes(), fixture["handoff_raw"])
        self.assertEqual(consumed.read_bytes(), foreign)

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_delivery_post_rename_fsync_failure_stays_unacknowledged(
        self,
    ) -> None:
        real_rename = (
            archive_services.project_update_transaction
            ._atomic_move_file_no_replace
        )
        real_require_directory_durable = (
            archive_services.project_update_transaction
            ._require_directory_durable
        )
        fixture = self.prepare_terminal_delivery_fixture(
            "post-rename-fsync"
        )
        renamed = False
        post_rename_paths: list[Path] = []

        def observe_rename(source: Path, destination: Path) -> None:
            nonlocal renamed
            self.assertEqual(Path(source).parent, Path(destination).parent)
            real_rename(source, destination)
            renamed = True

        def fail_after_rename(path: Path) -> object:
            if renamed:
                post_rename_paths.append(path)
                raise (
                    archive_services.project_update_transaction
                    .ProjectUpdateTransactionError(
                        "project_update_transaction_durability_unverified"
                    )
                )
            return real_require_directory_durable(path)

        with patch.object(
            archive_services.project_update_transaction,
            "_atomic_move_file_no_replace",
            side_effect=observe_rename,
        ), patch.object(
            archive_services.project_update_transaction,
            "_require_directory_durable",
            side_effect=fail_after_rename,
        ):
            acknowledged = (
                archive_services
                ._project_update_acknowledge_terminal_result_delivery(
                    self.project,
                    fixture["result"],
                    output_relative=str(fixture["output_relative"]),
                    run_id=str(fixture["run_id"]),
                    operation_ref=str(fixture["operation_ref"]),
                )
        )
        self.assertFalse(acknowledged)
        self.assertFalse(Path(fixture["handoff"]).exists())
        display_pending = (
            archive_services._project_update_terminal_display_pending_path(
                self.project
            )
        )
        self.assertEqual(
            display_pending.read_bytes(),
            fixture["handoff_raw"],
        )
        consumed = archive_services._project_update_terminal_consumed_path(
            self.project,
            str(fixture["handoff_sha256"]),
        )
        self.assertFalse(consumed.exists())
        self.assertTrue(
            archive_services
            ._project_update_finalize_terminal_result_display(
                self.project,
                expected_handoff_sha256=str(
                    fixture["handoff_sha256"]
                ),
                delivery_capability=str(fixture["capability"]),
            )
        )
        self.assertFalse(display_pending.exists())
        self.assertEqual(consumed.read_bytes(), fixture["handoff_raw"])
        self.assertEqual(post_rename_paths, [consumed.parent])

    def test_reopen_closes_directory_guard_when_second_hold_fails(
        self,
    ) -> None:
        base = archive_services._WomKitProjectUpdateDirectoryGuard

        class FailSecondHoldGuard(base):
            instances = []

            def __init__(self, project_root: Path) -> None:
                super().__init__(project_root)
                self.calls = 0
                self.maximum_held = 0
                self.__class__.instances.append(self)

            def hold(self, path: Path) -> bool:
                self.calls += 1
                if self.calls == 2:
                    return False
                result = super().hold(path)
                self.maximum_held = max(
                    self.maximum_held,
                    len(self._handles),
                )
                return result

        self.assert_reopen_guard_failure_closes_all_handles(
            FailSecondHoldGuard,
            minimum_held=1,
        )

    def test_reopen_closes_all_tree_handles_when_midscan_hold_fails(
        self,
    ) -> None:
        base = archive_services._WomKitProjectUpdateDirectoryGuard

        class FailTreeChildHoldGuard(base):
            instances = []

            def __init__(self, project_root: Path) -> None:
                super().__init__(project_root)
                self.maximum_held = 0
                self.__class__.instances.append(self)

            def hold(self, path: Path) -> bool:
                if path.name == "fail":
                    return False
                result = super().hold(path)
                self.maximum_held = max(
                    self.maximum_held,
                    len(self._handles),
                )
                return result

        self.assert_reopen_guard_failure_closes_all_handles(
            FailTreeChildHoldGuard,
            minimum_held=4,
        )

    def test_reopen_preserves_primary_when_guard_and_runner_close_fail(
        self,
    ) -> None:
        base = archive_services._WomKitProjectUpdateDirectoryGuard

        class FailHoldAndCloseGuard(base):
            instances = []

            def __init__(self, project_root: Path) -> None:
                super().__init__(project_root)
                self.calls = 0
                self.maximum_held = 0
                self.__class__.instances.append(self)

            def hold(self, path: Path) -> bool:
                self.calls += 1
                if self.calls == 2:
                    return False
                result = super().hold(path)
                self.maximum_held = max(
                    self.maximum_held,
                    len(self._handles),
                )
                return result

            def close(self) -> None:
                super().close()
                raise SystemExit("private directory close failure")

        self.assert_reopen_guard_failure_closes_all_handles(
            FailHoldAndCloseGuard,
            minimum_held=1,
            runner_close_fails=True,
        )

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_public_claimless_cancel_resumes_all_durable_cancel_tails(
        self,
    ) -> None:
        original_project = self.project
        cases = (
            ("requested", ("lock_backlinked", "preapproval_cancel_requested"), True),
            (
                "cancelled",
                (
                    "lock_backlinked",
                    "preapproval_cancel_requested",
                    "preapproval_cancelled",
                ),
                True,
            ),
            (
                "ready_to_unlock",
                (
                    "lock_backlinked",
                    "preapproval_cancel_requested",
                    "preapproval_cancelled",
                    "ready_to_unlock",
                ),
                True,
            ),
            (
                "post_unlink_pre_lock_released",
                (
                    "lock_backlinked",
                    "preapproval_cancel_requested",
                    "preapproval_cancelled",
                    "ready_to_unlock",
                ),
                False,
            ),
            (
                "lock_released",
                (
                    "lock_backlinked",
                    "preapproval_cancel_requested",
                    "preapproval_cancelled",
                    "ready_to_unlock",
                    "lock_released",
                ),
                False,
            ),
            (
                "completed_pre_cleanup",
                (
                    "lock_backlinked",
                    "preapproval_cancel_requested",
                    "preapproval_cancelled",
                    "ready_to_unlock",
                    "lock_released",
                    "completed",
                ),
                False,
            ),
        )
        try:
            for index, (case, expected_phases, lock_present) in enumerate(cases, start=1):
                with self.subTest(case=case):
                    self.project = (
                        Path(self.temporary.name) / f"cancel-tail-{index}"
                    )
                    self.project.mkdir()
                    transaction_ref = f"update_{index:032x}"
                    (
                        transaction,
                        lock_bytes,
                        prepared_runtime_candidate,
                    ) = self.create_transaction_with_prepared_runtime_candidate(
                        transaction_ref=transaction_ref
                    )
                    live = self.live_pre()
                    transaction.append(
                        phase="lock_backlinked",
                        stage="verified",
                        live_component_sha256=live,
                    )
                    transaction.begin_claimless_cancel_before_approval(
                        expected_lock_bytes=lock_bytes,
                        live_component_sha256=live,
                        confirm_claim_store_empty=lambda: True,
                    )

                    if case != "requested":
                        (
                            _cleanup_capsule,
                            runtime_cleanup,
                        ) = self.prepare_typed_runtime_cleanup_capsule(
                            transaction,
                            prepared_runtime_candidate,
                        )
                        original_append = transaction.append

                        def crash_at_boundary(*args, **kwargs):
                            phase = kwargs.get("phase")
                            if (
                                case == "cancelled"
                                and phase == "ready_to_unlock"
                            ) or (
                                case == "post_unlink_pre_lock_released"
                                and phase == "lock_released"
                            ) or (
                                case == "lock_released"
                                and phase == "completed"
                            ):
                                raise RuntimeError(
                                    f"simulated hard exit at {case}"
                                )
                            checkpoint = original_append(*args, **kwargs)
                            if (
                                case == "ready_to_unlock"
                                and phase == "ready_to_unlock"
                            ):
                                raise RuntimeError(
                                    "simulated hard exit after ready_to_unlock"
                                )
                            return checkpoint

                        if case == "completed_pre_cleanup":
                            transaction.cancel_before_approval(
                                expected_lock_bytes=lock_bytes,
                                live_component_sha256=live,
                                runtime_cleanup_terminal_evidence=(
                                    runtime_cleanup
                                ),
                            )
                        else:
                            with patch.object(
                                transaction,
                                "append",
                                side_effect=crash_at_boundary,
                            ):
                                with self.assertRaisesRegex(
                                    RuntimeError,
                                    "simulated hard exit",
                                ):
                                    transaction.cancel_before_approval(
                                        expected_lock_bytes=lock_bytes,
                                        live_component_sha256=live,
                                        runtime_cleanup_terminal_evidence=(
                                            runtime_cleanup
                                        ),
                                    )

                    self.assertEqual(
                        tuple(
                            item.phase
                            for item in transaction.inspect().journal.verified_prefix
                        ),
                        expected_phases,
                    )
                    lock_path = (
                        self.project
                        / ".zettel-kasten"
                        / "version-update.lock"
                    )
                    self.assertEqual(lock_path.exists(), lock_present)

                    proof_calls: list[bool] = []
                    closed: list[str] = []
                    state = SimpleNamespace(
                        project_root=self.project,
                        transaction=transaction,
                        expected_lock_bytes=lock_bytes,
                        runtime_candidate=prepared_runtime_candidate,
                        directory_guard=SimpleNamespace(
                            close=lambda: closed.append("directory")
                        ),
                    )
                    lifetime = SimpleNamespace(
                        close_after_service_transaction=(
                            lambda: closed.append("runner")
                        )
                    )

                    def cleanup_candidate(candidate):
                        capsule, _evidence = (
                            self.prepare_typed_runtime_cleanup_capsule(
                                transaction,
                                candidate,
                            )
                        )
                        return capsule

                    with (
                        patch.object(
                            archive_services,
                            "_project_update_reopen_durable_state",
                            return_value=(state, lifetime),
                        ),
                        patch.object(
                            archive_services,
                            "_project_update_live_component_sha256",
                            return_value=live,
                        ),
                        patch.object(
                            archive_services.project_runtime,
                            "cleanup_prepared_runtime_candidate",
                            side_effect=cleanup_candidate,
                        ),
                    ):
                        result = archive_services._wom_kit_project_version_update_cancel_claimless_preapproval_transaction(
                            self.project,
                            target=None,
                            reviewed_by=None,
                            transaction_ref=None,
                            confirm_claim_store_empty=lambda: (
                                proof_calls.append(True) or True
                            ),
                            _expected_approval_root=self.project,
                            _expected_archive_id="archive-identity",
                        )

                    self.assertEqual(
                        result["status"],
                        "preapproval_scaffold_cancelled",
                    )
                    self.assert_preapproval_cancel_effect_truth(
                        result,
                        live_lock_verified=lock_present,
                        reservation_abort_evidence=False,
                        candidate_cleanup=True,
                    )
                    self.assertEqual(proof_calls, [])
                    self.assertEqual(closed, ["directory", "runner"])
                    self.assertFalse(lock_path.exists())
                    self.assertFalse(transaction.transaction_root.exists())
        finally:
            self.project = original_project

    def test_public_claimless_cancel_rejects_tampered_tail_without_writes(
        self,
    ) -> None:
        transaction = self.create_transaction()
        lock_bytes = self.activate(transaction)
        live = self.live_pre()
        transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=live,
        )
        transaction.begin_claimless_cancel_before_approval(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
            confirm_claim_store_empty=lambda: True,
        )
        journal_path = transaction.transaction_root / "checkpoints.jsonl"
        with journal_path.open("ab") as stream:
            stream.write(b'{"torn":')
            stream.flush()
            os.fsync(stream.fileno())
        before = self.tree_snapshot(self.project)
        proof_calls: list[bool] = []
        cleanup_calls: list[bool] = []
        closed: list[str] = []
        state = SimpleNamespace(
            transaction=transaction,
            expected_lock_bytes=lock_bytes,
            runtime_candidate=object(),
            directory_guard=SimpleNamespace(
                close=lambda: closed.append("directory")
            ),
        )
        lifetime = SimpleNamespace(
            close_after_service_transaction=lambda: closed.append("runner")
        )

        with (
            patch.object(
                archive_services,
                "_project_update_reopen_durable_state",
                return_value=(state, lifetime),
            ),
            patch.object(
                archive_services,
                "_project_update_live_component_sha256",
                return_value=live,
            ),
            patch.object(
                archive_services.project_runtime,
                "cleanup_prepared_runtime_candidate",
                side_effect=lambda _candidate: (
                    cleanup_calls.append(True) or True
                ),
            ),
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "project_version_update_preapproval_recovery_failed",
            ):
                archive_services._wom_kit_project_version_update_cancel_claimless_preapproval_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    confirm_claim_store_empty=lambda: (
                        proof_calls.append(True) or True
                    ),
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive-identity",
                )

        self.assertEqual(self.tree_snapshot(self.project), before)
        self.assertEqual(proof_calls, [])
        self.assertEqual(cleanup_calls, [])
        self.assertEqual(closed, ["directory", "runner"])

    @unittest.skipUnless(
        os.name == "nt",
        "approved project-update mutation is Windows-only",
    )
    def test_fresh_executor_gets_publication_boundary_released_before_writer(
        self,
    ) -> None:
        project_transaction = self.create_transaction()
        lock_bytes = self.activate(project_transaction)
        live = self.live_pre()
        project_transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=live,
        )
        state = SimpleNamespace(
            inspection_root=self.project,
            project_root=self.project,
            transaction=project_transaction,
            expected_lock_bytes=lock_bytes,
            approved_plan_sha256=None,
            approved_target_binding_sha256=None,
            terminal_update_verified=False,
        )
        prepared = archive_services._ProjectVersionUpdatePreparedApproval(
            preview={},
            state=state,
        )

        def prepared_generator():
            yield prepared

        writer_guard_acquired: list[bool] = []

        def durable_writer(_state, _claim):
            with project_transaction.append_guard_nonblocking():
                writer_guard_acquired.append(True)
            return {"ok": True, "status": "writer-called"}

        executor_contract: list[tuple[int, set[str]]] = []

        def approval_executor(*args, **kwargs):
            executor_contract.append((len(args), set(kwargs)))
            with kwargs["claim_publication_boundary"]():
                self.assert_code(
                    "project_update_transaction_checkpoint_write_failed",
                    lambda: project_transaction
                    .begin_claimless_cancel_before_approval(
                        expected_lock_bytes=lock_bytes,
                        live_component_sha256=live,
                        confirm_claim_store_empty=lambda: True,
                    ),
                )
            return args[1](
                SimpleNamespace(),
                digest("approved-plan"),
                digest("approved-target"),
            )

        binding = SimpleNamespace(
            plan_sha256=digest("approved-plan"),
            target_binding_sha256=digest("approved-target"),
        )
        with (
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_legacy_core_generator",
                side_effect=lambda *_args, **_kwargs: prepared_generator(),
            ),
            patch.object(
                archive_services,
                "project_version_update_approval_binding",
                return_value=binding,
            ),
            patch.object(archive_services, "assert_same_binding"),
            patch.object(
                archive_services,
                "_project_update_live_component_sha256",
                return_value=live,
            ),
            patch.object(
                archive_services,
                "_project_update_durable_writer",
                side_effect=durable_writer,
            ),
        ):
            result = archive_services._wom_kit_project_version_update_legacy_core(
                self.project,
                target="v0.4.3",
                approve=True,
                reviewed_by="reviewer-a",
                approval_executor=approval_executor,
            )

        self.assertEqual(result["status"], "writer-called")
        self.assertEqual(
            executor_contract,
            [(5, {"claim_publication_boundary"})],
        )
        self.assertEqual(writer_guard_acquired, [True])
        self.assertEqual(
            [
                item.phase
                for item in project_transaction.inspect().journal.verified_prefix
            ],
            ["lock_backlinked"],
        )

    def test_claim_checkpoint_guard_explicitly_rejects_cancel_phases(
        self,
    ) -> None:
        transaction = self.create_transaction()
        lock_bytes = self.activate(transaction)
        live = self.live_pre()
        transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=live,
        )
        transaction.begin_claimless_cancel_before_approval(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
            confirm_claim_store_empty=lambda: True,
        )
        state = SimpleNamespace(transaction=transaction)
        claim = SimpleNamespace(
            public_reference=lambda: {"approval_id": "approval-a"}
        )
        with (
            patch.object(
                archive_services,
                "_project_update_claim_authority",
                return_value=(digest("reference"), digest("mac")),
            ),
            patch.object(
                archive_services,
                "_project_update_live_component_sha256",
                side_effect=AssertionError(
                    "cancellation guard should reject before live classification"
                ),
            ),
        ):
            for succeeded in (False, True):
                with self.subTest(succeeded=succeeded):
                    self.assertFalse(
                        archive_services._project_update_claim_checkpoint_guard(
                            state,
                            claim,
                            succeeded=succeeded,
                        )
                    )

    def test_preapproval_cancel_refuses_candidate_mixed_state_and_torn_tail(self) -> None:
        transaction = self.create_transaction()
        lock_bytes = self.activate(transaction)
        live = self.live_pre()
        plan = transaction.candidate_cleanup_plan_sha256()
        transaction.begin_cancel_before_approval(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
            candidate_cleanup_plan_sha256=plan,
        )
        runtime_cleanup = self.runtime_cleanup_terminal_evidence(transaction)
        self.assert_code(
            "project_update_transaction_candidate_invalid",
            lambda: transaction.cancel_before_approval(
                expected_lock_bytes=lock_bytes,
                live_component_sha256=live,
                runtime_cleanup_terminal_evidence=runtime_cleanup,
                candidate_cleanup_plan_sha256=plan,
            ),
        )
        self.remove_sealed_candidate(transaction)
        receipt = transaction.candidate_cleanup_receipt_sha256()
        mixed = dict(live)
        mixed["source"] = digest_component(self.post_values["source"])
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: transaction.cancel_before_approval(
                expected_lock_bytes=lock_bytes,
                live_component_sha256=mixed,
                runtime_cleanup_terminal_evidence=runtime_cleanup,
                candidate_cleanup_plan_sha256=plan,
                candidate_cleanup_receipt_sha256=receipt,
            ),
        )
        with (transaction.transaction_root / "checkpoints.jsonl").open("ab") as stream:
            stream.write(b'{"torn":')
            stream.flush()
            os.fsync(stream.fileno())
        self.assert_code(
            "project_update_transaction_journal_degraded",
            lambda: transaction.cancel_before_approval(
                expected_lock_bytes=lock_bytes,
                live_component_sha256=live,
                runtime_cleanup_terminal_evidence=runtime_cleanup,
                candidate_cleanup_plan_sha256=plan,
                candidate_cleanup_receipt_sha256=receipt,
            ),
        )
        self.assertTrue(
            (self.project / ".zettel-kasten" / "version-update.lock").exists()
        )

    def test_preapproval_cancel_rejects_same_bytes_lock_replacement(self) -> None:
        transaction = self.create_transaction()
        lock_bytes = self.activate(transaction)
        live = self.live_pre()
        plan = transaction.candidate_cleanup_plan_sha256()
        transaction.begin_cancel_before_approval(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
            candidate_cleanup_plan_sha256=plan,
        )
        runtime_cleanup = self.runtime_cleanup_terminal_evidence(transaction)
        self.remove_sealed_candidate(transaction)
        receipt = transaction.candidate_cleanup_receipt_sha256()
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        replacement = lock_path.with_suffix(".replacement")
        replacement.write_bytes(lock_bytes)
        os.replace(replacement, lock_path)
        self.assert_code(
            "project_update_transaction_lock_invalid",
            lambda: transaction.cancel_before_approval(
                expected_lock_bytes=lock_bytes,
                live_component_sha256=live,
                runtime_cleanup_terminal_evidence=runtime_cleanup,
                candidate_cleanup_plan_sha256=plan,
                candidate_cleanup_receipt_sha256=receipt,
            ),
        )
        self.assertEqual(lock_path.read_bytes(), lock_bytes)

    def test_preapproval_cancel_resumes_after_hard_exit_post_unlink(self) -> None:
        transaction = self.create_transaction()
        lock_bytes = self.activate(transaction)
        live = self.live_pre()
        plan = transaction.candidate_cleanup_plan_sha256()
        transaction.begin_cancel_before_approval(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
            candidate_cleanup_plan_sha256=plan,
        )
        runtime_cleanup = self.runtime_cleanup_terminal_evidence(transaction)
        self.remove_sealed_candidate(transaction)
        receipt = transaction.candidate_cleanup_receipt_sha256()
        original_append = transaction.append

        def crash_before_lock_released(*args, **kwargs):
            if kwargs.get("phase") == "lock_released":
                raise RuntimeError("simulated process loss")
            return original_append(*args, **kwargs)

        with patch.object(
            transaction, "append", side_effect=crash_before_lock_released
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated process loss"):
                transaction.cancel_before_approval(
                    expected_lock_bytes=lock_bytes,
                    live_component_sha256=live,
                    runtime_cleanup_terminal_evidence=runtime_cleanup,
                    candidate_cleanup_plan_sha256=plan,
                    candidate_cleanup_receipt_sha256=receipt,
                )
        self.assertFalse(
            (self.project / ".zettel-kasten" / "version-update.lock").exists()
        )
        reopened = ProjectUpdateTransaction.open(
            self.project, transaction.transaction_ref
        )
        completed = reopened.cancel_before_approval(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
            runtime_cleanup_terminal_evidence=runtime_cleanup,
            candidate_cleanup_plan_sha256=plan,
            candidate_cleanup_receipt_sha256=receipt,
        )
        self.assertEqual(completed.phase, "completed")
        ack = transaction_module.load_runtime_cleanup_durable_ack(
            self.project,
            transaction.transaction_ref,
        )
        self.assertIsNotNone(ack)
        assert ack is not None
        self.assertEqual(ack.authority_kind, "preapproval_cancelled")
        self.assertTrue(
            transaction_module.revalidate_runtime_cleanup_durable_ack(ack)
        )

    def prepare_terminal_reserved_abort(
        self,
        *,
        transaction_ref: str = DEFAULT_TRANSACTION_REF,
    ):
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.17",
            transaction_ref=transaction_ref,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        evidence = reserved.reservation_abort_plan_sha256()
        runtime_cleanup = self.runtime_cleanup_terminal_evidence(reserved)
        terminal = reserved.abort_before_intent_seal(
            expected_lock_bytes=lock_bytes,
            runtime_cleanup_terminal_evidence=runtime_cleanup,
            candidate_cleanup_evidence_sha256=evidence,
        )
        return reserved, terminal

    def test_reserved_fetch_failure_abort_is_durable_and_idempotent(self) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.3",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        evidence = reserved.reservation_abort_plan_sha256()
        runtime_cleanup = self.runtime_cleanup_terminal_evidence(reserved)
        result = reserved.abort_before_intent_seal(
            expected_lock_bytes=lock_bytes,
            runtime_cleanup_terminal_evidence=runtime_cleanup,
            candidate_cleanup_evidence_sha256=evidence,
        )
        self.assertEqual(result["state"], "aborted_before_intent_seal")
        self.assertFalse(
            (self.project / ".zettel-kasten" / "version-update.lock").exists()
        )
        reopened = transaction_module.ReservedProjectUpdateTransaction.open(
            self.project, reserved.transaction_ref
        )
        repeated = reopened.abort_before_intent_seal(
            expected_lock_bytes=lock_bytes,
            runtime_cleanup_terminal_evidence=runtime_cleanup,
            candidate_cleanup_evidence_sha256=evidence,
        )
        self.assertEqual(repeated, result)
        root = reserved.transaction_root
        self.assertEqual(
            result["schema"],
            transaction_module.RESERVATION_ABORT_RECEIPT_SCHEMA_V0419,
        )
        self.assertEqual(
            result["runtime_cleanup_terminal_evidence_sha256"],
            transaction_module.sha256_document(runtime_cleanup),
        )
        self.assertTrue((root / "reservation-abort-intent.json").is_file())
        self.assertTrue((root / "reservation-abort-receipt.json").is_file())
        intent_document = json.loads(
            (root / "reservation-abort-intent.json").read_text(
                encoding="ascii"
            )
        )
        receipt_document = json.loads(
            (root / "reservation-abort-receipt.json").read_text(
                encoding="ascii"
            )
        )
        self.assertEqual(
            intent_document["schema"],
            transaction_module.RESERVATION_ABORT_INTENT_SCHEMA_V0419,
        )
        for name in (
            "runtime_cleanup_terminal_evidence_sha256",
            "runtime_cleanup_capsule_sha256",
            "runtime_cleanup_capsule_identity_sha256",
        ):
            self.assertEqual(intent_document[name], receipt_document[name])
        ack = transaction_module.load_runtime_cleanup_durable_ack(
            self.project,
            reserved.transaction_ref,
        )
        self.assertIsNotNone(ack)
        assert ack is not None
        self.assertEqual(ack.authority_kind, "unsealed_abort")
        self.assertEqual(
            ack.runtime_cleanup_terminal_evidence_sha256,
            transaction_module.sha256_document(runtime_cleanup),
        )
        self.assertTrue(
            transaction_module.revalidate_runtime_cleanup_durable_ack(ack)
        )
        self.assertEqual(
            inspect_prelock_orphans(self.project)[0].classification,
            "reserved_aborted_before_intent_seal",
        )
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: reopened.acquire_lock(),
        )

    def test_unsealed_abort_rejects_nonexact_cleanup_evidence_without_writes(
        self,
    ) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        evidence = self.runtime_cleanup_terminal_evidence(reserved)
        before = self.tree_snapshot(self.project)
        invalid_documents = []
        missing = dict(evidence)
        missing.pop("runtime_parent_restored")
        invalid_documents.append(missing)
        invalid_documents.append(dict(evidence, unexpected="private"))
        invalid_documents.append(dict(evidence, target_tag="v9.9.9"))
        invalid_documents.append(
            dict(evidence, provider_inventory_count=0)
        )
        invalid_documents.append(
            dict(evidence, runtime_cleanup_capsule_sha256="not-a-digest")
        )
        for invalid in invalid_documents:
            with self.subTest(keys=tuple(sorted(invalid))):
                self.assert_code(
                    "project_update_transaction_candidate_invalid",
                    lambda invalid=invalid: reserved.abort_before_intent_seal(
                        expected_lock_bytes=lock_bytes,
                        runtime_cleanup_terminal_evidence=invalid,
                    ),
                )
                self.assertEqual(self.tree_snapshot(self.project), before)
                self.assertFalse(
                    (
                        reserved.transaction_root
                        / transaction_module.RESERVATION_ABORT_INTENT_NAME
                    ).exists()
                )

    def test_exact_empty_unsealed_abort_claims_namespace_and_capsule_blocks_omission(
        self,
    ) -> None:
        empty = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("empty-project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        empty_lock = empty.acquire_lock()
        terminal = empty.abort_before_intent_seal(
            expected_lock_bytes=empty_lock,
        )
        self.assertEqual(
            terminal["schema"],
            transaction_module.RESERVATION_ABORT_RECEIPT_SCHEMA_V0419,
        )
        root = empty.transaction_root
        anchor = root / transaction_module.EMPTY_ABORT_CLAIM_ANCHOR_NAME
        retirement = root / transaction_module.EMPTY_ABORT_CLAIM_RETIREMENT_NAME
        self.assertTrue(anchor.is_file())
        self.assertEqual(anchor.stat().st_nlink, 1)
        self.assertTrue(retirement.is_file())
        self.assertFalse(
            (
                root.parent
                / (
                    ".runtime-candidate-cleanup_"
                    + empty.transaction_ref
                    + ".json"
                )
            ).exists()
        )
        self.assertIn("empty_abort_claim_retirement_sha256", terminal)
        self.assertIsNone(
            transaction_module.load_runtime_cleanup_durable_ack(
                self.project,
                empty.transaction_ref,
            )
        )

        sidecar_ref = "update_99999999999999999999999999999999"
        sidecar = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("sidecar-project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=sidecar_ref,
            ownership_nonce="99999999999999999999999999999999",
            created_at=self.CREATED_AT,
        )
        sidecar_lock = sidecar.acquire_lock()
        sidecar_path = sidecar.transaction_root.parent / (
            ".runtime-candidate-cleanup_" + sidecar_ref + ".json"
        )
        sidecar_path.write_bytes(b"synthetic-runtime-cleanup-capsule\n")
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        lock_before = lock_path.read_bytes()
        self.assert_code(
            "project_update_transaction_candidate_invalid",
            lambda: sidecar.abort_before_intent_seal(
                expected_lock_bytes=sidecar_lock,
            ),
        )
        self.assertEqual(lock_path.read_bytes(), lock_before)
        self.assertEqual(
            sidecar_path.read_bytes(),
            b"synthetic-runtime-cleanup-capsule\n",
        )
        self.assertTrue(
            (
                sidecar.transaction_root
                / transaction_module.EMPTY_ABORT_CLAIM_INTENT_NAME
            ).is_file()
        )
        self.assertFalse(
            (
                sidecar.transaction_root
                / transaction_module.RESERVATION_ABORT_INTENT_NAME
            ).exists()
        )

    def test_empty_abort_sidecar_unavailable_preserves_every_owned_byte(self) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        lock_info = lock_path.stat()
        before = self.tree_snapshot(reserved.transaction_root)
        sidecar_path = reserved.transaction_root.parent / (
            ".runtime-candidate-cleanup_"
            + reserved.transaction_ref
            + ".json"
        )
        original_open = os.open

        for unavailable in (
            PermissionError("synthetic access denial"),
            OSError("synthetic observation failure"),
        ):
            with self.subTest(error_type=type(unavailable).__name__):

                def fail_sidecar_open(path, flags, *args, **kwargs):
                    if Path(path) == sidecar_path:
                        raise unavailable
                    return original_open(path, flags, *args, **kwargs)

                with patch.object(
                    transaction_module.os,
                    "open",
                    side_effect=fail_sidecar_open,
                ):
                    self.assert_code(
                        "project_update_transaction_candidate_invalid",
                        lambda: reserved.abort_before_intent_seal(
                            expected_lock_bytes=lock_bytes,
                        ),
                    )
                current = lock_path.stat()
                self.assertEqual(lock_path.read_bytes(), lock_bytes)
                self.assertEqual(
                    (current.st_dev, current.st_ino),
                    (lock_info.st_dev, lock_info.st_ino),
                )
                self.assertTrue(
                    (
                        reserved.transaction_root
                        / transaction_module.EMPTY_ABORT_CLAIM_INTENT_NAME
                    ).is_file()
                )
                self.assertFalse(sidecar_path.exists())

    def test_empty_abort_rechecks_raw_sidecar_before_any_durable_mutation(
        self,
    ) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        lock_info = lock_path.stat()
        sidecar_path = reserved.transaction_root.parent / (
            ".runtime-candidate-cleanup_"
            + reserved.transaction_ref
            + ".json"
        )
        sidecar_bytes = b"raw-external-sidecar-appearance\n"

        def inject_after_claim_intent(boundary: str) -> None:
            if boundary == "after_claim_intent_durable":
                sidecar_path.write_bytes(sidecar_bytes)

        with patch.object(
            transaction_module,
            "_empty_abort_claim_test_hook",
            side_effect=inject_after_claim_intent,
        ):
            self.assert_code(
                "project_update_transaction_candidate_invalid",
                lambda: reserved.abort_before_intent_seal(
                    expected_lock_bytes=lock_bytes,
                ),
            )
        current = lock_path.stat()
        self.assertEqual(lock_path.read_bytes(), lock_bytes)
        self.assertEqual(
            (current.st_dev, current.st_ino),
            (lock_info.st_dev, lock_info.st_ino),
        )
        self.assertTrue(
            (
                reserved.transaction_root
                / transaction_module.EMPTY_ABORT_CLAIM_INTENT_NAME
            ).is_file()
        )
        self.assertFalse(
            (
                reserved.transaction_root
                / transaction_module.RESERVATION_ABORT_INTENT_NAME
            ).exists()
        )
        self.assertEqual(sidecar_path.read_bytes(), sidecar_bytes)

    def test_runtime_sidecar_creator_and_empty_abort_share_one_guard(self) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        creator_results: list[str] = []
        with transaction_module.runtime_cleanup_sidecar_creation_guard(
            self.project,
            reserved.transaction_ref,
        ) as revalidate_creation:
            self.assertTrue(callable(revalidate_creation))
            revalidate_creation()

        def try_guard_respecting_creator(boundary: str) -> None:
            if boundary != "after_claim_intent_durable":
                return

            def creator() -> None:
                try:
                    with (
                        transaction_module
                        .runtime_cleanup_sidecar_creation_guard(
                            self.project,
                            reserved.transaction_ref,
                        )
                    ):
                        creator_results.append("entered")
                except ProjectUpdateTransactionError as error:
                    creator_results.append(error.code)

            thread = threading.Thread(target=creator)
            thread.start()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())

        with patch.object(
            transaction_module,
            "_empty_abort_claim_test_hook",
            side_effect=try_guard_respecting_creator,
        ):
            terminal = reserved.abort_before_intent_seal(
                expected_lock_bytes=lock_bytes,
            )
        self.assertEqual(
            creator_results,
            ["project_update_transaction_checkpoint_write_failed"],
        )
        self.assertEqual(
            terminal["schema"],
            transaction_module.RESERVATION_ABORT_RECEIPT_SCHEMA_V0419,
        )
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: (
                transaction_module.runtime_cleanup_sidecar_creation_guard(
                    self.project,
                    reserved.transaction_ref,
                ).__enter__()
            ),
        )

    def test_empty_abort_claim_resumes_every_durable_prefix(self) -> None:
        boundaries = [
            "claim_intent_after_create",
            "claim_intent_after_prefix",
            "claim_intent_after_complete",
            "after_claim_intent_durable",
            "claim_sidecar_after_create",
            "claim_sidecar_after_prefix",
            "claim_sidecar_after_complete",
            "after_claim_anchor",
            "after_claim_bound",
            "claim_abort_intent_after_create",
            "claim_abort_intent_after_prefix",
            "claim_abort_intent_after_complete",
            "after_abort_intent_durable",
            "after_abort_lock_unlinked",
            "claim_abort_receipt_after_create",
            "claim_abort_receipt_after_prefix",
            "claim_abort_receipt_after_complete",
            "after_abort_receipt_durable",
            "before_claim_original_name_retire",
            "after_claim_original_name_retired",
            "claim_retirement_after_create",
            "claim_retirement_after_prefix",
            "claim_retirement_after_complete",
            "after_claim_retirement_durable",
        ]
        if os.name != "nt":
            boundaries.append("before_claim_original_name_unlink")
        for index, boundary in enumerate(boundaries, start=0x100):
            with self.subTest(boundary=boundary):
                ref = f"update_{index:032x}"
                reserved = ProjectUpdateTransaction.reserve(
                    self.project,
                    project_identity_sha256=digest(f"project-{index}"),
                    requested_target_tag="v0.4.19",
                    transaction_ref=ref,
                    ownership_nonce=f"{index:032x}",
                    created_at=self.CREATED_AT,
                )
                lock_bytes = reserved.acquire_lock()
                crashed = False

                def stop_once(actual: str) -> None:
                    nonlocal crashed
                    if actual == boundary and not crashed:
                        crashed = True
                        raise RuntimeError("synthetic power loss")

                with patch.object(
                    transaction_module,
                    "_empty_abort_claim_test_hook",
                    side_effect=stop_once,
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "synthetic power loss",
                    ):
                        reserved.abort_before_intent_seal(
                            expected_lock_bytes=lock_bytes,
                        )
                self.assertTrue(crashed)
                reopened = (
                    transaction_module.ReservedProjectUpdateTransaction.open(
                        self.project,
                        ref,
                    )
                )
                terminal = reopened.abort_before_intent_seal(
                    expected_lock_bytes=lock_bytes,
                )
                self.assertEqual(
                    terminal["schema"],
                    transaction_module.RESERVATION_ABORT_RECEIPT_SCHEMA_V0419,
                )
                anchor = (
                    reopened.transaction_root
                    / transaction_module.EMPTY_ABORT_CLAIM_ANCHOR_NAME
                )
                self.assertEqual(anchor.stat().st_nlink, 1)
                self.assertTrue(
                    (
                        reopened.transaction_root
                        / transaction_module.EMPTY_ABORT_CLAIM_RETIREMENT_NAME
                    ).is_file()
                )
                sidecar = reopened.transaction_root.parent / (
                    ".runtime-candidate-cleanup_" + ref + ".json"
                )
                self.assertFalse(sidecar.exists())

    def test_empty_abort_unanchored_claim_is_never_resumed_or_deleted(
        self,
    ) -> None:
        boundaries = (
            "claim_sidecar_unbound_after_create",
            "before_claim_anchor",
        )
        for index, boundary in enumerate(boundaries, start=0x180):
            with self.subTest(boundary=boundary):
                ref = f"update_{index:032x}"
                reserved = ProjectUpdateTransaction.reserve(
                    self.project,
                    project_identity_sha256=digest(f"project-{boundary}"),
                    requested_target_tag="v0.4.19",
                    transaction_ref=ref,
                    ownership_nonce=f"{index:032x}",
                    created_at=self.CREATED_AT,
                )
                lock_bytes = reserved.acquire_lock()
                lock_path = (
                    self.project / ".zettel-kasten" / "version-update.lock"
                )
                lock_info = lock_path.stat()

                def stop(actual: str) -> None:
                    if actual == boundary:
                        raise RuntimeError("synthetic power loss")

                with patch.object(
                    transaction_module,
                    "_empty_abort_claim_test_hook",
                    side_effect=stop,
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "synthetic power loss",
                    ):
                        reserved.abort_before_intent_seal(
                            expected_lock_bytes=lock_bytes,
                        )
                sidecar = reserved.transaction_root.parent / (
                    ".runtime-candidate-cleanup_" + ref + ".json"
                )
                anchor = (
                    reserved.transaction_root
                    / transaction_module.EMPTY_ABORT_CLAIM_ANCHOR_NAME
                )
                self.assertEqual(sidecar.read_bytes(), b"")
                self.assertFalse(anchor.exists())
                if boundary == "claim_sidecar_unbound_after_create":
                    # A byte-identical replacement is intentionally
                    # indistinguishable without the same-inode anchor.
                    sidecar.unlink()
                    sidecar.write_bytes(b"")
                before = self.tree_snapshot(self.project)
                reopened = (
                    transaction_module.ReservedProjectUpdateTransaction.open(
                        self.project,
                        ref,
                    )
                )
                self.assert_code(
                    "project_update_transaction_candidate_invalid",
                    lambda: reopened.abort_before_intent_seal(
                        expected_lock_bytes=lock_bytes,
                    ),
                )
                self.assertEqual(self.tree_snapshot(self.project), before)
                current = lock_path.stat()
                self.assertEqual(lock_path.read_bytes(), lock_bytes)
                self.assertEqual(
                    (current.st_dev, current.st_ino),
                    (lock_info.st_dev, lock_info.st_ino),
                )
                sidecar.unlink()
                lock_path.unlink()

    def test_empty_abort_foreign_zero_byte_sidecar_after_claim_intent_is_preserved(
        self,
    ) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        lock_info = lock_path.stat()
        sidecar = reserved.transaction_root.parent / (
            ".runtime-candidate-cleanup_" + reserved.transaction_ref + ".json"
        )

        def inject(actual: str) -> None:
            if actual == "after_claim_intent_durable":
                sidecar.write_bytes(b"")

        with patch.object(
            transaction_module,
            "_empty_abort_claim_test_hook",
            side_effect=inject,
        ):
            self.assert_code(
                "project_update_transaction_candidate_invalid",
                lambda: reserved.abort_before_intent_seal(
                    expected_lock_bytes=lock_bytes,
                ),
            )
        current = lock_path.stat()
        self.assertEqual(sidecar.read_bytes(), b"")
        self.assertEqual(lock_path.read_bytes(), lock_bytes)
        self.assertEqual(
            (current.st_dev, current.st_ino),
            (lock_info.st_dev, lock_info.st_ino),
        )
        self.assertFalse(
            (
                reserved.transaction_root
                / transaction_module.EMPTY_ABORT_CLAIM_ANCHOR_NAME
            ).exists()
        )
        self.assertFalse(
            (
                reserved.transaction_root
                / transaction_module.RESERVATION_ABORT_INTENT_NAME
            ).exists()
        )

    def test_empty_abort_claim_physically_blocks_raw_create(self) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        sidecar = reserved.transaction_root.parent / (
            ".runtime-candidate-cleanup_" + reserved.transaction_ref + ".json"
        )
        raw_creator_blocked = False

        def raw_create(boundary: str) -> None:
            nonlocal raw_creator_blocked
            if boundary != "claim_sidecar_after_complete":
                return
            try:
                descriptor = os.open(
                    sidecar,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
            except FileExistsError:
                raw_creator_blocked = True
            else:
                os.close(descriptor)

        with patch.object(
            transaction_module,
            "_empty_abort_claim_test_hook",
            side_effect=raw_create,
        ):
            reserved.abort_before_intent_seal(
                expected_lock_bytes=lock_bytes,
            )
        self.assertTrue(raw_creator_blocked)

    def test_empty_abort_claim_rejects_foreign_hardlink_and_extra_link(self) -> None:
        cases = ("foreign_at_sidecar", "third_link_after_anchor")
        for index, case in enumerate(cases, start=0x200):
            with self.subTest(case=case):
                ref = f"update_{index:032x}"
                reserved = ProjectUpdateTransaction.reserve(
                    self.project,
                    project_identity_sha256=digest(f"project-{case}"),
                    requested_target_tag="v0.4.19",
                    transaction_ref=ref,
                    ownership_nonce=f"{index:032x}",
                    created_at=self.CREATED_AT,
                )
                lock_bytes = reserved.acquire_lock()
                sidecar = reserved.transaction_root.parent / (
                    ".runtime-candidate-cleanup_" + ref + ".json"
                )
                foreign = reserved.transaction_root.parent / f"foreign-{index}.bin"
                extra = reserved.transaction_root / "unexpected-third-link.json"

                def inject(boundary: str) -> None:
                    if (
                        case == "foreign_at_sidecar"
                        and boundary == "after_claim_intent_durable"
                    ):
                        foreign.write_bytes(b"")
                        os.link(foreign, sidecar)
                    elif (
                        case == "third_link_after_anchor"
                        and boundary == "after_claim_anchor"
                    ):
                        os.link(sidecar, extra)

                with patch.object(
                    transaction_module,
                    "_empty_abort_claim_test_hook",
                    side_effect=inject,
                ):
                    self.assert_code(
                        "project_update_transaction_candidate_invalid",
                        lambda: reserved.abort_before_intent_seal(
                            expected_lock_bytes=lock_bytes,
                        ),
                    )
                self.assertTrue(
                    (
                        self.project
                        / ".zettel-kasten"
                        / "version-update.lock"
                    ).is_file()
                )
                self.assertFalse(
                    (
                        reserved.transaction_root
                        / transaction_module.RESERVATION_ABORT_INTENT_NAME
                    ).exists()
                )
                if case == "foreign_at_sidecar":
                    self.assertEqual(foreign.stat().st_nlink, 2)
                    self.assertEqual(sidecar.stat().st_nlink, 2)
                    sidecar.unlink()
                    foreign.unlink()
                else:
                    self.assertEqual(sidecar.stat().st_nlink, 3)
                    self.assertEqual(extra.stat().st_nlink, 3)
                    extra.unlink()
                    sidecar.unlink()
                (
                    self.project
                    / ".zettel-kasten"
                    / "version-update.lock"
                ).unlink()

    def test_empty_abort_claim_anchor_replacement_is_preserved_and_blocked(
        self,
    ) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        anchor = (
            reserved.transaction_root
            / transaction_module.EMPTY_ABORT_CLAIM_ANCHOR_NAME
        )
        foreign = b"foreign-anchor\n"

        def replace_anchor(boundary: str) -> None:
            if boundary == "after_claim_bound":
                anchor.unlink()
                anchor.write_bytes(foreign)

        with patch.object(
            transaction_module,
            "_empty_abort_claim_test_hook",
            side_effect=replace_anchor,
        ):
            self.assert_code(
                "project_update_transaction_candidate_invalid",
                lambda: reserved.abort_before_intent_seal(
                    expected_lock_bytes=lock_bytes,
                ),
            )
        self.assertEqual(anchor.read_bytes(), foreign)
        self.assertTrue(
            (
                self.project / ".zettel-kasten" / "version-update.lock"
            ).is_file()
        )

    @unittest.skipUnless(os.name == "nt", "Windows ADS regression")
    def test_empty_abort_claim_ads_is_preserved_and_blocked(self) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        sidecar = reserved.transaction_root.parent / (
            ".runtime-candidate-cleanup_" + reserved.transaction_ref + ".json"
        )

        def add_ads(boundary: str) -> None:
            if boundary == "after_claim_bound":
                Path(str(sidecar) + ":foreign").write_bytes(b"private")

        with patch.object(
            transaction_module,
            "_empty_abort_claim_test_hook",
            side_effect=add_ads,
        ):
            self.assert_code(
                "project_update_transaction_cleanup_refused",
                lambda: reserved.abort_before_intent_seal(
                    expected_lock_bytes=lock_bytes,
                ),
            )
        self.assertEqual(
            Path(str(sidecar) + ":foreign").read_bytes(),
            b"private",
        )

    def test_empty_abort_claim_is_held_exact_through_lock_release_boundary(
        self,
    ) -> None:
        cases = ["sidecar_replace", "anchor_replace", "third_link"]
        if os.name == "nt":
            cases.append("ads")
        for index, case in enumerate(cases, start=0x280):
            with self.subTest(case=case):
                ref = f"update_{index:032x}"
                reserved = ProjectUpdateTransaction.reserve(
                    self.project,
                    project_identity_sha256=digest(f"project-{case}"),
                    requested_target_tag="v0.4.19",
                    transaction_ref=ref,
                    ownership_nonce=f"{index:032x}",
                    created_at=self.CREATED_AT,
                )
                lock_bytes = reserved.acquire_lock()
                lock_path = (
                    self.project / ".zettel-kasten" / "version-update.lock"
                )
                lock_info = lock_path.stat()
                sidecar = reserved.transaction_root.parent / (
                    ".runtime-candidate-cleanup_" + ref + ".json"
                )
                anchor = (
                    reserved.transaction_root
                    / transaction_module.EMPTY_ABORT_CLAIM_ANCHOR_NAME
                )
                extra = reserved.transaction_root / "foreign-third-link.json"
                foreign = ("foreign-" + case + "\n").encode("ascii")
                observed_claim = b""

                def mutate_after_intent(boundary: str) -> None:
                    nonlocal observed_claim
                    if boundary != "after_abort_intent_durable":
                        return
                    observed_claim = sidecar.read_bytes()
                    if case == "sidecar_replace":
                        sidecar.unlink()
                        sidecar.write_bytes(foreign)
                    elif case == "anchor_replace":
                        anchor.unlink()
                        anchor.write_bytes(foreign)
                    elif case == "third_link":
                        os.link(sidecar, extra)
                    else:
                        Path(str(sidecar) + ":foreign").write_bytes(foreign)

                with patch.object(
                    transaction_module,
                    "_empty_abort_claim_test_hook",
                    side_effect=mutate_after_intent,
                ):
                    self.assert_code(
                        "project_update_transaction_candidate_invalid",
                        lambda: reserved.abort_before_intent_seal(
                            expected_lock_bytes=lock_bytes,
                        ),
                    )
                current_lock = lock_path.stat()
                self.assertTrue(observed_claim)
                self.assertEqual(lock_path.read_bytes(), lock_bytes)
                self.assertEqual(
                    (current_lock.st_dev, current_lock.st_ino),
                    (lock_info.st_dev, lock_info.st_ino),
                )
                self.assertFalse(
                    (
                        reserved.transaction_root
                        / transaction_module.RESERVATION_ABORT_RECEIPT_NAME
                    ).exists()
                )
                if case == "third_link":
                    self.assertEqual(extra.read_bytes(), observed_claim)
                    self.assertEqual(extra.stat().st_nlink, 3)
                elif case == "ads":
                    self.assertEqual(
                        Path(str(sidecar) + ":foreign").read_bytes(),
                        foreign,
                    )
                elif os.name == "nt":
                    # Retained no-delete handles rejected replacement itself.
                    self.assertEqual(sidecar.read_bytes(), observed_claim)
                    self.assertEqual(anchor.read_bytes(), observed_claim)
                    self.assertEqual(sidecar.stat().st_nlink, 2)
                    self.assertEqual(anchor.stat().st_nlink, 2)
                elif case == "sidecar_replace":
                    self.assertEqual(sidecar.read_bytes(), foreign)
                    self.assertEqual(anchor.read_bytes(), observed_claim)
                else:
                    self.assertEqual(anchor.read_bytes(), foreign)
                    self.assertEqual(sidecar.read_bytes(), observed_claim)
                lock_path.unlink()

    def test_empty_abort_claim_replacement_before_retire_blocks_and_preserves(
        self,
    ) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        sidecar = reserved.transaction_root.parent / (
            ".runtime-candidate-cleanup_" + reserved.transaction_ref + ".json"
        )
        foreign = b"foreign-runtime-sidecar\n"
        replaced = False
        replacement_blocked = False

        def replace_before_retire(boundary: str) -> None:
            nonlocal replaced, replacement_blocked
            if boundary == "after_abort_receipt_durable" and not replaced:
                try:
                    sidecar.unlink()
                    sidecar.write_bytes(foreign)
                except OSError:
                    replacement_blocked = True
                    raise
                replaced = True

        with patch.object(
            transaction_module,
            "_empty_abort_claim_test_hook",
            side_effect=replace_before_retire,
        ):
            self.assert_code(
                "project_update_transaction_candidate_invalid",
                lambda: reserved.abort_before_intent_seal(
                    expected_lock_bytes=lock_bytes,
                ),
            )
        self.assertTrue(replaced or replacement_blocked)
        if replacement_blocked:
            # Windows retained no-delete handles reject the replacement
            # itself.  The durable receipt remains resumable and the exact
            # original claim is retired by the next process.
            self.assertNotEqual(sidecar.read_bytes(), foreign)
            reopened = (
                transaction_module.ReservedProjectUpdateTransaction.open(
                    self.project,
                    reserved.transaction_ref,
                )
            )
            terminal = reopened.resume_abort_after_lock_release()
            self.assertEqual(
                terminal["schema"],
                transaction_module.RESERVATION_ABORT_RECEIPT_SCHEMA_V0419,
            )
            self.assertFalse(sidecar.exists())
            return
        self.assertEqual(sidecar.read_bytes(), foreign)
        self.assertFalse(
            (
                reserved.transaction_root
                / transaction_module.EMPTY_ABORT_CLAIM_RETIREMENT_NAME
            ).exists()
        )
        before = self.tree_snapshot(self.project)
        reopened = transaction_module.ReservedProjectUpdateTransaction.open(
            self.project,
            reserved.transaction_ref,
        )
        self.assert_code(
            "project_update_transaction_candidate_invalid",
            lambda: reopened.resume_abort_after_lock_release(),
        )
        self.assertEqual(self.tree_snapshot(self.project), before)

    @unittest.skipUnless(
        os.name == "nt",
        "exact abort-history cleanup mutation is Windows-only",
    )
    def test_empty_abort_cleanup_preserves_foreign_sidecar_created_after_retire(
        self,
    ) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        sidecar = reserved.transaction_root.parent / (
            ".runtime-candidate-cleanup_" + reserved.transaction_ref + ".json"
        )
        foreign = b"post-retirement-foreign-sidecar\n"
        injected = False

        def inject_after_retire(boundary: str) -> None:
            nonlocal injected
            if boundary == "after_claim_original_name_retired" and not injected:
                sidecar.write_bytes(foreign)
                injected = True

        with patch.object(
            transaction_module,
            "_empty_abort_claim_test_hook",
            side_effect=inject_after_retire,
        ):
            terminal = reserved.abort_before_intent_seal(
                expected_lock_bytes=lock_bytes,
            )
        self.assertTrue(injected)
        self.assertEqual(sidecar.read_bytes(), foreign)
        self.assertTrue(
            reserved.exact_cleanup(
                cleanup_authority_sha256=terminal["receipt_sha256"],
            )
        )
        self.assertEqual(sidecar.read_bytes(), foreign)
        self.assertFalse(reserved.transaction_root.exists())

    def test_legacy_unsealed_abort_remains_readable_but_is_not_cleanup_authority(
        self,
    ) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        evidence = self.runtime_cleanup_terminal_evidence(reserved)
        reserved.abort_before_intent_seal(
            expected_lock_bytes=lock_bytes,
            runtime_cleanup_terminal_evidence=evidence,
        )
        ack = transaction_module.load_runtime_cleanup_durable_ack(
            self.project,
            reserved.transaction_ref,
        )
        self.assertIsNotNone(ack)
        assert ack is not None

        intent_path = (
            reserved.transaction_root
            / transaction_module.RESERVATION_ABORT_INTENT_NAME
        )
        receipt_path = (
            reserved.transaction_root
            / transaction_module.RESERVATION_ABORT_RECEIPT_NAME
        )
        intent = json.loads(intent_path.read_text(encoding="ascii"))
        receipt = json.loads(receipt_path.read_text(encoding="ascii"))
        for name in (
            "runtime_cleanup_terminal_evidence_sha256",
            "runtime_cleanup_capsule_sha256",
            "runtime_cleanup_capsule_identity_sha256",
        ):
            intent.pop(name)
            receipt.pop(name)
        intent["schema"] = transaction_module.RESERVATION_ABORT_INTENT_SCHEMA
        receipt["schema"] = (
            transaction_module.RESERVATION_ABORT_RECEIPT_SCHEMA
        )
        receipt["abort_intent_sha256"] = (
            transaction_module.sha256_document(intent)
        )
        intent_path.write_bytes(canonical_json_bytes(intent) + b"\n")
        receipt_path.write_bytes(canonical_json_bytes(receipt) + b"\n")

        terminal = reserved.inspect_abort_receipt()
        self.assertIsNotNone(terminal)
        assert terminal is not None
        self.assertEqual(
            terminal["schema"],
            transaction_module.RESERVATION_ABORT_RECEIPT_SCHEMA,
        )
        self.assertIsNone(
            transaction_module.load_runtime_cleanup_durable_ack(
                self.project,
                reserved.transaction_ref,
            )
        )
        self.assertFalse(
            transaction_module.revalidate_runtime_cleanup_durable_ack(ack)
        )

    def test_unsealed_abort_resumes_v0419_intent_before_lock_unlink(self) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.19",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        evidence = self.runtime_cleanup_terminal_evidence(reserved)
        with patch.object(
            reserved,
            "_verify_reservation_backlink",
            side_effect=RuntimeError("simulated stop before lock unlink"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "simulated stop before lock unlink",
            ):
                reserved.abort_before_intent_seal(
                    expected_lock_bytes=lock_bytes,
                    runtime_cleanup_terminal_evidence=evidence,
                )
        intent_path = (
            reserved.transaction_root
            / transaction_module.RESERVATION_ABORT_INTENT_NAME
        )
        receipt_path = (
            reserved.transaction_root
            / transaction_module.RESERVATION_ABORT_RECEIPT_NAME
        )
        lock_path = (
            self.project / ".zettel-kasten" / "version-update.lock"
        )
        self.assertTrue(intent_path.is_file())
        self.assertTrue(lock_path.is_file())
        self.assertFalse(receipt_path.exists())
        self.assertIsNone(
            transaction_module.load_runtime_cleanup_durable_ack(
                self.project,
                reserved.transaction_ref,
            )
        )
        before = self.tree_snapshot(self.project)
        reopened = transaction_module.ReservedProjectUpdateTransaction.open(
            self.project,
            reserved.transaction_ref,
        )
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: reopened.abort_before_intent_seal(
                expected_lock_bytes=lock_bytes,
            ),
        )
        self.assertEqual(self.tree_snapshot(self.project), before)
        terminal = reopened.abort_before_intent_seal(
            expected_lock_bytes=lock_bytes,
            runtime_cleanup_terminal_evidence=evidence,
        )
        self.assertEqual(
            terminal["schema"],
            transaction_module.RESERVATION_ABORT_RECEIPT_SCHEMA_V0419,
        )
        ack = transaction_module.load_runtime_cleanup_durable_ack(
            self.project,
            reserved.transaction_ref,
        )
        self.assertIsNotNone(ack)
        assert ack is not None
        self.assertEqual(ack.authority_kind, "unsealed_abort")
        self.assertTrue(
            transaction_module.revalidate_runtime_cleanup_durable_ack(ack)
        )

    @unittest.skipUnless(
        os.name == "nt",
        "exact project-update cleanup mutation is Windows-only",
    )
    def test_reserved_abort_terminal_history_cleanup_leaves_canonical_inert_proof(
        self,
    ) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        authority = terminal["receipt_sha256"]
        discovered = (
            transaction_module
            .discover_exact_reservation_abort_cleanup_read_only(self.project)
        )
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0].transaction_ref, reserved.transaction_ref)
        self.assertEqual(discovered[0].state, "terminal_original")
        self.assertIsNone(discovered[0].cleanup_authority_sha256)

        self.assertTrue(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        parent = reserved.transaction_root.parent
        proof = parent / f".cleanup-proof_{reserved.transaction_ref}.json"
        proof_raw = proof.read_bytes()
        proof_info = proof.stat()
        document = json.loads(proof_raw)
        self.assertEqual(
            document["schema"],
            transaction_module.RESERVATION_ABORT_CLEANUP_PLAN_SCHEMA,
        )
        self.assertEqual(document["cleanup_authority_sha256"], authority)
        self.assertEqual(document["abort_receipt_sha256"], authority)
        self.assertEqual(
            [item["relative_path"] for item in document["files"]],
            [
                "append.guard",
                "marker.json",
                "reservation-abort-intent.json",
                "reservation-abort-receipt.json",
                "reservation-lock-backlink.json",
            ],
        )
        ProjectUpdateTransaction._validate_cleanup_plan_document(
            document,
            reserved.transaction_ref,
            authority,
        )
        self.assertFalse(reserved.transaction_root.exists())
        self.assertFalse(
            (parent / f".cleanup_{reserved.transaction_ref}").exists()
        )
        self.assertEqual(
            transaction_module
            .discover_exact_reservation_abort_cleanup_read_only(self.project),
            (),
        )

        self.assertTrue(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        self.assertTrue(
            transaction_module.ReservedProjectUpdateTransaction.resume_cleanup(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        proof_after = proof.stat()
        self.assertEqual(proof.read_bytes(), proof_raw)
        self.assertEqual(
            (proof_after.st_dev, proof_after.st_ino, proof_after.st_mtime_ns),
            (proof_info.st_dev, proof_info.st_ino, proof_info.st_mtime_ns),
        )
        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_namespace_classification_read_only(
                self.project
            ),
            ("history_only_exact", 1),
        )

    @unittest.skipIf(
        os.name == "nt",
        "POSIX-only fail-closed mutation boundary",
    )
    def test_reserved_abort_cleanup_posix_refuses_before_control_mutation(
        self,
    ) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        before = self.tree_snapshot(self.project)

        self.assertFalse(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=terminal["receipt_sha256"],
            )
        )

        self.assertEqual(self.tree_snapshot(self.project), before)
        discovered = (
            transaction_module
            .discover_exact_reservation_abort_cleanup_read_only(self.project)
        )
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0].state, "terminal_original")

    def test_reserved_abort_cleanup_unsupported_platform_guard_precedes_mutation(
        self,
    ) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        before = self.tree_snapshot(self.project)

        with patch.object(transaction_module.os, "name", "posix"):
            self.assertFalse(
                reserved.exact_cleanup(
                    cleanup_authority_sha256=terminal["receipt_sha256"],
                )
            )
            self.assertFalse(
                transaction_module.ReservedProjectUpdateTransaction
                .resume_cleanup(
                    self.project,
                    reserved.transaction_ref,
                    cleanup_authority_sha256=terminal["receipt_sha256"],
                )
            )

        self.assertEqual(self.tree_snapshot(self.project), before)

    @unittest.skipUnless(
        os.name == "nt",
        "exact project-update cleanup mutation is Windows-only",
    )
    def test_reserved_abort_cleanup_resumes_after_partial_exact_delete(self) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        authority = terminal["receipt_sha256"]
        real_delete = transaction_module._delete_exact_cleanup_file
        deleted = {"count": 0}

        def crash_after_first_delete(project: Path, path: Path, snapshot) -> None:
            real_delete(project, path, snapshot)
            deleted["count"] += 1
            if deleted["count"] == 1:
                raise OSError("synthetic process loss after exact delete")

        with patch.object(
            transaction_module,
            "_delete_exact_cleanup_file",
            side_effect=crash_after_first_delete,
        ):
            self.assertFalse(
                reserved.exact_cleanup(cleanup_authority_sha256=authority)
            )
        tombstone = (
            reserved.transaction_root.parent
            / f".cleanup_{reserved.transaction_ref}"
        )
        self.assertFalse(reserved.transaction_root.exists())
        self.assertTrue(tombstone.is_dir())
        discovered = (
            transaction_module
            .discover_exact_reservation_abort_cleanup_read_only(self.project)
        )
        self.assertEqual(discovered[0].state, "cleanup_tombstone")
        self.assertEqual(discovered[0].cleanup_authority_sha256, authority)
        self.assertFalse(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=digest("wrong-abort-cleanup-authority"),
            )
        )
        self.assertTrue(tombstone.is_dir())
        self.assertTrue(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        self.assertFalse(tombstone.exists())

    @unittest.skipUnless(
        os.name == "nt",
        "exact project-update cleanup mutation is Windows-only",
    )
    def test_reserved_abort_cleanup_resumes_after_proof_publication(self) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        authority = terminal["receipt_sha256"]
        real_delete_directory = transaction_module._delete_exact_cleanup_directory
        crashed = {"done": False}

        def crash_before_tombstone_delete(project: Path, path: Path, snapshot) -> None:
            if path.name == f".cleanup_{reserved.transaction_ref}" and not crashed["done"]:
                crashed["done"] = True
                raise OSError("synthetic process loss after proof publication")
            real_delete_directory(project, path, snapshot)

        with patch.object(
            transaction_module,
            "_delete_exact_cleanup_directory",
            side_effect=crash_before_tombstone_delete,
        ):
            self.assertFalse(
                reserved.exact_cleanup(cleanup_authority_sha256=authority)
            )
        parent = reserved.transaction_root.parent
        tombstone = parent / f".cleanup_{reserved.transaction_ref}"
        proof = parent / f".cleanup-proof_{reserved.transaction_ref}.json"
        self.assertTrue(tombstone.is_dir())
        self.assertEqual(list(tombstone.iterdir()), [])
        proof_raw = proof.read_bytes()
        proof_info = proof.stat()
        discovered = (
            transaction_module
            .discover_exact_reservation_abort_cleanup_read_only(self.project)
        )
        self.assertEqual(discovered[0].state, "cleanup_tombstone")
        self.assertTrue(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        self.assertFalse(tombstone.exists())
        proof_after = proof.stat()
        self.assertEqual(proof.read_bytes(), proof_raw)
        self.assertEqual(
            (proof_after.st_dev, proof_after.st_ino, proof_after.st_mtime_ns),
            (proof_info.st_dev, proof_info.st_ino, proof_info.st_mtime_ns),
        )

    @unittest.skipUnless(
        os.name == "nt",
        "exact project-update cleanup mutation is Windows-only",
    )
    def test_reserved_abort_cleanup_resumes_after_plan_visibility(self) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        authority = terminal["receipt_sha256"]
        with patch.object(
            transaction_module,
            "_atomic_move_directory_no_replace",
            side_effect=OSError("synthetic process loss before tombstone move"),
        ):
            self.assertFalse(
                reserved.exact_cleanup(cleanup_authority_sha256=authority)
            )
        plan = (
            reserved.transaction_root
            / transaction_module.RESERVATION_ABORT_CLEANUP_PLAN_NAME
        )
        self.assertTrue(plan.is_file())
        discovered = (
            transaction_module
            .discover_exact_reservation_abort_cleanup_read_only(self.project)
        )
        self.assertEqual(discovered[0].state, "planned_original")
        self.assertEqual(discovered[0].cleanup_authority_sha256, authority)
        self.assertTrue(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )

    @unittest.skipUnless(os.name == "nt", "NTFS hardlink contract")
    def test_reserved_abort_planned_cleanup_refuses_external_hardlink(
        self,
    ) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        authority = terminal["receipt_sha256"]
        with patch.object(
            transaction_module,
            "_atomic_move_directory_no_replace",
            side_effect=OSError("synthetic stop after plan durability"),
        ):
            self.assertFalse(
                reserved.exact_cleanup(
                    cleanup_authority_sha256=authority
                )
            )
        plan = (
            reserved.transaction_root
            / transaction_module.RESERVATION_ABORT_CLEANUP_PLAN_NAME
        )
        external = (
            Path(self.temporary.name)
            / "external-abort-plan-hardlink.json"
        )
        plan_before = plan.read_bytes()
        try:
            os.link(plan, external)
        except OSError as failure:
            self.skipTest(f"hardlink creation unavailable: {failure}")
        self.assertEqual(plan.stat().st_nlink, 2)
        self.assertEqual(external.read_bytes(), plan_before)

        self.assert_code(
            "project_update_transaction_path_unsafe",
            lambda: transaction_module
            .discover_exact_reservation_abort_cleanup_read_only(
                self.project
            ),
        )
        self.assert_cleanup_hardlink_blocks_fresh_writer()
        self.assertFalse(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        self.assertTrue(reserved.transaction_root.is_dir())
        self.assertTrue(plan.is_file())
        self.assertTrue(external.is_file())
        self.assertEqual(plan.read_bytes(), plan_before)
        self.assertEqual(external.read_bytes(), plan_before)
        self.assertEqual(plan.stat().st_nlink, 2)

    @unittest.skipUnless(os.name == "nt", "NTFS hardlink contract")
    def test_reserved_abort_proof_only_refuses_external_hardlink(
        self,
    ) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        authority = terminal["receipt_sha256"]
        self.assertTrue(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        proof = (
            reserved.transaction_root.parent
            / f".cleanup-proof_{reserved.transaction_ref}.json"
        )
        external = (
            Path(self.temporary.name)
            / "external-abort-proof-hardlink.json"
        )
        proof_before = proof.read_bytes()
        try:
            os.link(proof, external)
        except OSError as failure:
            self.skipTest(f"hardlink creation unavailable: {failure}")
        self.assertEqual(proof.stat().st_nlink, 2)
        self.assertEqual(external.read_bytes(), proof_before)

        self.assert_code(
            "project_update_transaction_cleanup_refused",
            lambda: transaction_module
            .discover_exact_reservation_abort_cleanup_read_only(
                self.project
            ),
        )
        self.assert_cleanup_hardlink_blocks_fresh_writer()
        self.assertFalse(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        self.assertTrue(proof.is_file())
        self.assertTrue(external.is_file())
        self.assertEqual(proof.read_bytes(), proof_before)
        self.assertEqual(external.read_bytes(), proof_before)
        self.assertEqual(proof.stat().st_nlink, 2)

    @unittest.skipUnless(os.name == "nt", "NTFS named-stream contract")
    def test_reserved_abort_cleanup_refuses_named_stream_on_tombstone_plan(
        self,
    ) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        authority = terminal["receipt_sha256"]
        with patch.object(
            transaction_module,
            "_delete_exact_cleanup_file",
            side_effect=OSError("synthetic stop before exact delete"),
        ):
            self.assertFalse(
                reserved.exact_cleanup(cleanup_authority_sha256=authority)
            )

        parent = reserved.transaction_root.parent
        tombstone = parent / f".cleanup_{reserved.transaction_ref}"
        plan = tombstone / transaction_module.RESERVATION_ABORT_CLEANUP_PLAN_NAME
        proof = parent / f".cleanup-proof_{reserved.transaction_ref}.json"
        named_stream = Path(str(plan) + ":foreign")
        try:
            named_stream.write_bytes(b"foreign-abort-cleanup-plan-stream")
        except OSError as exc:
            self.skipTest(f"named stream creation unavailable: {exc}")
        plan_before = plan.read_bytes()
        names_before = tuple(sorted(item.name for item in tombstone.iterdir()))

        self.assert_code(
            "project_update_transaction_cleanup_refused",
            lambda: transaction_module
            .discover_exact_reservation_abort_cleanup_read_only(self.project),
        )
        self.assertFalse(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        self.assertTrue(tombstone.is_dir())
        self.assertFalse(proof.exists())
        self.assertEqual(plan.read_bytes(), plan_before)
        self.assertEqual(
            named_stream.read_bytes(),
            b"foreign-abort-cleanup-plan-stream",
        )
        self.assertEqual(
            tuple(sorted(item.name for item in tombstone.iterdir())),
            names_before,
        )

    @unittest.skipUnless(os.name == "nt", "NTFS named-stream contract")
    def test_reserved_abort_cleanup_refuses_named_stream_on_published_proof(
        self,
    ) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        authority = terminal["receipt_sha256"]
        real_delete_directory = transaction_module._delete_exact_cleanup_directory

        def stop_before_tombstone_delete(project: Path, path: Path, snapshot) -> None:
            if path.name == f".cleanup_{reserved.transaction_ref}":
                raise OSError("synthetic stop after proof publication")
            real_delete_directory(project, path, snapshot)

        with patch.object(
            transaction_module,
            "_delete_exact_cleanup_directory",
            side_effect=stop_before_tombstone_delete,
        ):
            self.assertFalse(
                reserved.exact_cleanup(cleanup_authority_sha256=authority)
            )

        parent = reserved.transaction_root.parent
        tombstone = parent / f".cleanup_{reserved.transaction_ref}"
        proof = parent / f".cleanup-proof_{reserved.transaction_ref}.json"
        named_stream = Path(str(proof) + ":foreign")
        try:
            named_stream.write_bytes(b"foreign-abort-cleanup-proof-stream")
        except OSError as exc:
            self.skipTest(f"named stream creation unavailable: {exc}")
        proof_before = proof.read_bytes()

        self.assert_code(
            "project_update_transaction_cleanup_refused",
            lambda: transaction_module
            .discover_exact_reservation_abort_cleanup_read_only(self.project),
        )
        self.assertFalse(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        self.assertTrue(tombstone.is_dir())
        self.assertEqual(list(tombstone.iterdir()), [])
        self.assertEqual(proof.read_bytes(), proof_before)
        self.assertEqual(
            named_stream.read_bytes(),
            b"foreign-abort-cleanup-proof-stream",
        )

    @unittest.skipUnless(
        os.name == "nt",
        "exact project-update cleanup mutation is Windows-only",
    )
    def test_reserved_abort_cleanup_actual_process_exit_resumes(self) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        authority = terminal["receipt_sha256"]
        worker = "\n".join(
            (
                "import os, sys",
                "from pathlib import Path",
                "from wom_kit import project_update_transaction as module",
                "reserved = module.ReservedProjectUpdateTransaction.open(Path(sys.argv[1]), sys.argv[2])",
                "real_delete = module._delete_exact_cleanup_file",
                "def crash(project, path, snapshot):",
                "    real_delete(project, path, snapshot)",
                "    os._exit(91)",
                "module._delete_exact_cleanup_file = crash",
                "reserved.exact_cleanup(cleanup_authority_sha256=sys.argv[3])",
                "raise SystemExit(99)",
            )
        )
        self.run_hard_exit_worker(
            worker,
            str(self.project),
            reserved.transaction_ref,
            authority,
            expected_returncode=91,
        )
        discovered = (
            transaction_module
            .discover_exact_reservation_abort_cleanup_read_only(self.project)
        )
        self.assertEqual(discovered[0].state, "cleanup_tombstone")
        self.assertTrue(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )

    def test_reserved_abort_cleanup_refuses_unknown_tampered_live_and_proof_collision(
        self,
    ) -> None:
        original_project = self.project
        cases = ("unknown", "tampered", "live_lock", "proof_collision")
        try:
            for index, case in enumerate(cases, start=1):
                with self.subTest(case=case):
                    self.project = Path(self.temporary.name) / f"abort-{index}"
                    self.project.mkdir()
                    reserved, terminal = self.prepare_terminal_reserved_abort()
                    authority = terminal["receipt_sha256"]
                    root = reserved.transaction_root
                    parent = root.parent
                    if case == "unknown":
                        changed = root / "unexpected-private.bin"
                        changed.write_bytes(b"must remain")
                    elif case == "tampered":
                        changed = root / "reservation-abort-receipt.json"
                        changed.write_bytes(b"tampered receipt\n")
                    elif case == "live_lock":
                        changed = (
                            self.project
                            / ".zettel-kasten"
                            / "version-update.lock"
                        )
                        changed.write_bytes(b"foreign live lock")
                    else:
                        changed = (
                            parent
                            / f".cleanup-proof_{reserved.transaction_ref}.json"
                        )
                        changed.write_bytes(b"preexisting proof collision\n")
                    changed_before = changed.read_bytes()
                    self.assertFalse(
                        reserved.exact_cleanup(
                            cleanup_authority_sha256=authority
                        )
                    )
                    self.assertTrue(root.is_dir())
                    self.assertEqual(changed.read_bytes(), changed_before)
                    self.assertFalse(
                        (
                            root
                            / transaction_module
                            .RESERVATION_ABORT_CLEANUP_PLAN_NAME
                        ).exists()
                    )
        finally:
            self.project = original_project

    def test_reserved_abort_cleanup_refuses_symlink_without_mutation(self) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        authority = terminal["receipt_sha256"]
        link = reserved.transaction_root / "unexpected-link"
        try:
            os.symlink(reserved.transaction_root / "marker.json", link)
        except OSError:
            link.write_bytes(b"synthetic reparse sentinel")
            link_info = link.lstat()
            link_identity = (int(link_info.st_dev), int(link_info.st_ino))
            real_is_reparse = transaction_module._is_reparse

            def identify_synthetic_reparse(info) -> bool:
                return (
                    (int(info.st_dev), int(info.st_ino)) == link_identity
                    or real_is_reparse(info)
                )

            with patch.object(
                transaction_module,
                "_is_reparse",
                side_effect=identify_synthetic_reparse,
            ):
                self.assertFalse(
                    reserved.exact_cleanup(
                        cleanup_authority_sha256=authority
                    )
                )
            self.assertEqual(link.read_bytes(), b"synthetic reparse sentinel")
            self.assertFalse(
                (
                    reserved.transaction_root
                    / transaction_module.RESERVATION_ABORT_CLEANUP_PLAN_NAME
                ).exists()
            )
            return
        self.assertFalse(
            reserved.exact_cleanup(cleanup_authority_sha256=authority)
        )
        self.assertTrue(link.is_symlink())
        self.assertFalse(
            (
                reserved.transaction_root
                / transaction_module.RESERVATION_ABORT_CLEANUP_PLAN_NAME
            ).exists()
        )

    @unittest.skipUnless(
        os.name == "nt",
        "exact project-update cleanup mutation is Windows-only",
    )
    def test_reserved_abort_cleanup_refuses_same_byte_file_identity_drift(self) -> None:
        reserved, terminal = self.prepare_terminal_reserved_abort()
        authority = terminal["receipt_sha256"]
        real_move = transaction_module._atomic_move_directory_no_replace

        def replace_marker_then_move(source: Path, destination: Path) -> None:
            marker = source / "marker.json"
            replacement = source / "marker.replacement"
            replacement.write_bytes(marker.read_bytes())
            os.replace(replacement, marker)
            real_move(source, destination)

        with patch.object(
            transaction_module,
            "_atomic_move_directory_no_replace",
            side_effect=replace_marker_then_move,
        ):
            self.assertFalse(
                reserved.exact_cleanup(cleanup_authority_sha256=authority)
            )
        parent = reserved.transaction_root.parent
        tombstone = parent / f".cleanup_{reserved.transaction_ref}"
        proof = parent / f".cleanup-proof_{reserved.transaction_ref}.json"
        self.assertTrue(tombstone.is_dir())
        self.assertFalse(proof.exists())
        self.assertEqual((tombstone / "marker.json").read_bytes(), (
            json.dumps(
                reserved.reservation.document(),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("ascii")
            + b"\n"
        ))
        self.assertFalse(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                reserved.transaction_ref,
                cleanup_authority_sha256=authority,
            )
        )
        self.assertTrue(tombstone.is_dir())

    @unittest.skipUnless(
        os.name == "nt",
        "exact project-update cleanup mutation is Windows-only",
    )
    def test_reserved_abort_cleanup_discovery_excludes_exact_abort_tombstone_from_generic(
        self,
    ) -> None:
        generic_ref = "update_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        generic = self.create_transaction(transaction_ref=generic_ref)
        self.finish_forward(generic)
        with patch.object(
            ProjectUpdateTransaction,
            "_resume_cleanup_paths",
            return_value=False,
        ):
            self.assertFalse(
                generic.exact_cleanup(
                    cleanup_authority_sha256=digest("generic-cleanup")
                )
            )
        abort_ref = "update_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        reserved, terminal = self.prepare_terminal_reserved_abort(
            transaction_ref=abort_ref
        )
        authority = terminal["receipt_sha256"]
        with patch.object(
            transaction_module.ReservedProjectUpdateTransaction,
            "_resume_abort_cleanup_paths",
            return_value=False,
        ):
            self.assertFalse(
                reserved.exact_cleanup(cleanup_authority_sha256=authority)
            )

        discovered = (
            transaction_module
            .discover_exact_reservation_abort_cleanup_read_only(self.project)
        )
        self.assertEqual(
            [(item.transaction_ref, item.state) for item in discovered],
            [(abort_ref, "cleanup_tombstone")],
        )
        generic_inspection = (
            ProjectUpdateTransaction
            .discover_complete_cleanup_tombstone_for_resume_read_only(self.project)
        )
        self.assertIsNotNone(generic_inspection)
        self.assertEqual(generic_inspection.transaction_ref, generic_ref)
        self.assertTrue(
            transaction_module.compact_exact_reservation_abort_history(
                self.project,
                abort_ref,
                cleanup_authority_sha256=authority,
            )
        )
        generic_after = (
            ProjectUpdateTransaction
            .discover_complete_cleanup_tombstone_for_resume_read_only(self.project)
        )
        self.assertEqual(generic_after.transaction_ref, generic_ref)

    @unittest.skipUnless(
        os.name == "nt",
        "exact project-update cleanup mutation is Windows-only",
    )
    def test_reserved_abort_cleanup_all_reports_exact_progress(self) -> None:
        first_ref = "update_cccccccccccccccccccccccccccccccc"
        second_ref = "update_dddddddddddddddddddddddddddddddd"
        self.prepare_terminal_reserved_abort(transaction_ref=first_ref)
        self.prepare_terminal_reserved_abort(transaction_ref=second_ref)
        result = transaction_module.compact_exact_reservation_abort_histories(
            self.project,
            cleanup_authority_sha256=digest("abort-cleanup-batch"),
        )
        self.assertEqual(
            result,
            {
                "completed_count": 2,
                "completed_refs": [first_ref, second_ref],
                "discovered_count": 2,
                "failed_ref": None,
                "ok": True,
                "remaining_refs": [],
                "schema": (
                    transaction_module.RESERVATION_ABORT_CLEANUP_RESULT_SCHEMA
                ),
            },
        )

    def test_reserved_partial_candidate_abort_refuses_and_preserves(self) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.3",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        reserved.runtime_candidate_path.mkdir()
        partial = reserved.runtime_candidate_path / "partial.bin"
        partial.write_bytes(b"partial-private-runtime")
        runtime_cleanup = self.runtime_cleanup_terminal_evidence(reserved)
        self.assert_code(
            "project_update_transaction_candidate_invalid",
            lambda: reserved.abort_before_intent_seal(
                expected_lock_bytes=lock_bytes,
                runtime_cleanup_terminal_evidence=runtime_cleanup,
                candidate_cleanup_evidence_sha256=digest("unknown-cleanup"),
            ),
        )
        self.assertEqual(partial.read_bytes(), b"partial-private-runtime")
        self.assertTrue(
            (self.project / ".zettel-kasten" / "version-update.lock").exists()
        )
        self.assertEqual(
            inspect_prelock_orphans(self.project)[0].classification,
            "manual_review_candidate_partial",
        )

    def test_reserved_abort_resumes_after_hard_exit_post_unlink(self) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.3",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        evidence = reserved.reservation_abort_plan_sha256()
        runtime_cleanup = self.runtime_cleanup_terminal_evidence(reserved)
        original_write = transaction_module._write_new

        def crash_before_receipt(path, value, *, within):
            if Path(path).name == "reservation-abort-receipt.json":
                raise RuntimeError("simulated process loss")
            return original_write(path, value, within=within)

        with patch.object(
            transaction_module, "_write_new", side_effect=crash_before_receipt
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated process loss"):
                reserved.abort_before_intent_seal(
                    expected_lock_bytes=lock_bytes,
                    runtime_cleanup_terminal_evidence=runtime_cleanup,
                    candidate_cleanup_evidence_sha256=evidence,
                )
        self.assertFalse(
            (self.project / ".zettel-kasten" / "version-update.lock").exists()
        )
        self.assertTrue(
            (reserved.transaction_root / "reservation-abort-intent.json").exists()
        )
        self.assertIsNone(
            transaction_module.load_runtime_cleanup_durable_ack(
                self.project,
                reserved.transaction_ref,
            )
        )
        reopened = transaction_module.ReservedProjectUpdateTransaction.open(
            self.project, reserved.transaction_ref
        )
        result = reopened.abort_before_intent_seal(
            expected_lock_bytes=lock_bytes,
            runtime_cleanup_terminal_evidence=runtime_cleanup,
            candidate_cleanup_evidence_sha256=evidence,
        )
        self.assertEqual(result["state"], "aborted_before_intent_seal")
        ack = transaction_module.load_runtime_cleanup_durable_ack(
            self.project,
            reserved.transaction_ref,
        )
        self.assertIsNotNone(ack)
        assert ack is not None
        self.assertTrue(
            transaction_module.revalidate_runtime_cleanup_durable_ack(ack)
        )

    def test_public_identifierless_resume_completes_reserved_abort_after_hard_exit(
        self,
    ) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.3",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        reserved.acquire_lock()
        runtime_cleanup = self.runtime_cleanup_terminal_evidence(reserved)
        worker = "\n".join(
            (
                "import json",
                "import os",
                "import sys",
                "from pathlib import Path",
                "from unittest.mock import patch",
                "from wom_kit import project_update_transaction as module",
                "reservation = module.ReservedProjectUpdateTransaction.open(Path(sys.argv[1]), sys.argv[2])",
                "runtime_cleanup = json.loads(sys.argv[3])",
                "lock_bytes = reservation.existing_lock_bytes_read_only()",
                "evidence = reservation.reservation_abort_plan_sha256()",
                "original_write = module._write_new",
                "def crash(path, value, *, within):",
                "    if Path(path).name == module.RESERVATION_ABORT_RECEIPT_NAME:",
                "        os._exit(86)",
                "    return original_write(path, value, within=within)",
                "with patch.object(module, '_write_new', side_effect=crash):",
                "    reservation.abort_before_intent_seal(expected_lock_bytes=lock_bytes, runtime_cleanup_terminal_evidence=runtime_cleanup, candidate_cleanup_evidence_sha256=evidence)",
                "raise SystemExit(99)",
            )
        )
        environment = dict(os.environ)
        environment.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(SRC_ROOT),
                "PYTHONUTF8": "1",
            }
        )
        crashed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                worker,
                str(self.project),
                reserved.transaction_ref,
                json.dumps(runtime_cleanup, separators=(",", ":")),
            ],
            cwd=KIT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(crashed.returncode, 86, crashed.stdout + crashed.stderr)
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        receipt_path = (
            reserved.transaction_root / "reservation-abort-receipt.json"
        )
        self.assertFalse(lock_path.exists())
        self.assertFalse(receipt_path.exists())

        reopened = transaction_module.ReservedProjectUpdateTransaction.open(
            self.project,
            reserved.transaction_ref,
        )
        before = {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in self.project.rglob("*")
            if path.is_file()
        }
        pending = reopened.inspect_abort_receipt_pending_read_only()
        self.assertIsNotNone(pending)
        self.assertEqual(
            inspect_prelock_orphans(self.project)[0].classification,
            "reserved_abort_receipt_pending",
        )
        self.assertEqual(
            {
                path.relative_to(self.project).as_posix(): path.read_bytes()
                for path in self.project.rglob("*")
                if path.is_file()
            },
            before,
        )

        with patch.object(
            archive_services,
            "_wom_kit_project_version_update_approval_authority_matches",
            return_value=True,
        ):
            recovered = (
                archive_services
                ._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=(
                        lambda *_args: self.fail(
                            "preapproval recovery called the approval executor"
                        )
                    ),
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive-identity",
                )
            )

        self.assertEqual(recovered["status"], "preapproval_scaffold_cancelled")
        self.assertEqual(
            recovered["preapproval_recovery"]["kind"],
            "empty_reservation_abort_receipt_completed",
        )
        self.assertFalse(recovered["operator_resume_identifiers_supplied"])
        self.assert_preapproval_cancel_effect_truth(
            recovered,
            live_lock_verified=False,
            reservation_abort_evidence=True,
            candidate_cleanup=False,
        )
        self.assertTrue(receipt_path.is_file())
        terminal = reopened.inspect_abort_receipt()
        self.assertIsNotNone(terminal)
        self.assertEqual(terminal["state"], "aborted_before_intent_seal")

    def test_public_resume_reports_cleanup_outcome_unknown_without_access_or_writes(
        self,
    ) -> None:
        original_project = self.project
        approval_root = Path(self.temporary.name) / "private-client-archive"
        approval_root.mkdir()
        (approval_root / "archive.yml").write_text(
            "archive_id: private-client-archive\n",
            encoding="utf-8",
        )
        (approval_root / "secret-sentinel.bin").write_bytes(
            b"private archive sentinel"
        )
        archive_before = self.tree_snapshot(approval_root)
        cases = (
            ("partial_tombstone", "proof_only")
            if os.name == "nt"
            else ("partial_tombstone",)
        )
        try:
            for index, case in enumerate(cases, start=1):
                with self.subTest(case=case):
                    self.project = (
                        Path(self.temporary.name) / f"cleanup-public-{index}"
                    )
                    self.project.mkdir()
                    transaction = self.create_transaction()
                    self.finish_forward(transaction)
                    authority = digest(f"cleanup-authority-{index}")
                    if case == "proof_only":
                        self.assertTrue(
                            transaction.exact_cleanup(
                                cleanup_authority_sha256=authority
                            )
                        )
                    else:
                        with patch.object(
                            ProjectUpdateTransaction,
                            "_resume_cleanup_paths",
                            return_value=False,
                        ):
                            self.assertFalse(
                                transaction.exact_cleanup(
                                    cleanup_authority_sha256=authority
                                )
                            )
                        tombstone = (
                            transaction.transaction_root.parent
                            / f".cleanup_{transaction.transaction_ref}"
                        )
                        self.assertTrue(tombstone.is_dir())
                        if case == "partial_tombstone":
                            victim = next(
                                path
                                for path in tombstone.rglob("*")
                                if path.is_file()
                                and path.name != CLEANUP_PLAN_NAME
                            )
                            victim.unlink()

                    project_before = self.tree_snapshot(self.project)
                    executor_calls: list[bool] = []

                    def approval_executor(*_args, **_kwargs):
                        executor_calls.append(True)
                        self.fail("cleanup-unknown entered approval executor")

                    with (
                        patch.object(
                            archive_services,
                            "_wom_kit_project_version_update_approval_authority_matches",
                            side_effect=AssertionError(
                                "cleanup-unknown accessed client archive authority"
                            ),
                        ) as authority_access,
                        patch.object(
                            archive_services,
                            "_project_update_resume_preapproval_transaction",
                            side_effect=AssertionError(
                                "cleanup-unknown reopened preapproval state"
                            ),
                        ) as preapproval_access,
                        patch.object(
                            archive_services,
                            "_project_update_reopen_durable_state",
                            side_effect=AssertionError(
                                "cleanup-unknown reopened durable state"
                            ),
                        ) as durable_access,
                        patch.object(
                            archive_services,
                            "_project_update_claim_store_absent_read_only",
                            side_effect=AssertionError(
                                "cleanup-unknown accessed approval claims"
                            ),
                        ) as claim_access,
                        patch.object(
                            ProjectUpdateTransaction,
                            "resume_cleanup",
                            side_effect=AssertionError(
                                "cleanup-unknown attempted cleanup"
                            ),
                        ) as cleanup_access,
                    ):
                        result = archive_services._wom_kit_project_version_update_resume_live_transaction(
                            self.project,
                            target=None,
                            reviewed_by=None,
                            transaction_ref=None,
                            approval_executor=approval_executor,
                            _expected_approval_root=approval_root,
                            _expected_archive_id=(
                                "private-client-archive-secret-id"
                            ),
                        )

                    if case == "proof_only":
                        self.assertEqual(
                            result["status"],
                            "no_resumable_project_update",
                        )
                        self.assertIsNone(result["update_completed"])
                        self.assertEqual(
                            result["effects_state"],
                            "canonical_cleanup_proof_shaped_artifact_only",
                        )
                        self.assertEqual(
                            result["cleanup_proof_artifacts_observed"],
                            1,
                        )
                        self.assertFalse(
                            result["past_update_success_attributed"]
                        )
                        self.assertFalse(
                            result["historical_detailed_result_available"]
                        )
                        self.assertTrue(
                            result["new_write_requires_fresh_approval"]
                        )
                    else:
                        self.assertEqual(
                            result,
                            {
                            "ok": False,
                            "status": "terminal_cleanup_outcome_unknown",
                            "reason_code": (
                                "project_version_update_terminal_cleanup_outcome_unknown"
                            ),
                            "reason_codes": [
                                "project_version_update_terminal_cleanup_outcome_unknown"
                            ],
                            "blocker_codes": [
                                "project_version_update_terminal_cleanup_outcome_unknown"
                            ],
                            "lifecycle_action": "project_version_update",
                            "error_class": "reconciliation",
                            "effects_state": "unknown",
                            "reconciliation_required": True,
                            "outcome_basis": (
                                "terminal_cleanup_residue_observed_or_could_not_be_ruled_out"
                            ),
                            "update_completed": None,
                            "observed_version_update_lock_present": False,
                            "automatic_resume_discovery": True,
                            "operator_resume_identifiers_supplied": False,
                            "automatic_retry_authorized": False,
                            "cleanup_authorized": False,
                            "fresh_approval_authorized": False,
                            "native_approval_redisplayed": False,
                            "domain_writer_reentered": False,
                            "approval_key_accessed": False,
                            "approval_claim_store_accessed": False,
                            "native_approval_ui_entered": False,
                            "domain_writer_entered": False,
                            "client_archive_accessed": False,
                            "archive_identity_metadata_read": False,
                            "client_archive_domain_content_accessed": False,
                            "project_domain_files_written": [],
                            "files_written": [],
                            "next_safe_actions": [
                                "Stop without deleting private update metadata, changing the project pin, or retrying approval.",
                                "Send the content-free result to the WOM maintainer for forensic review.",
                            ],
                            },
                        )
                    self.assertEqual(executor_calls, [])
                    self.assertEqual(authority_access.call_count, 0)
                    self.assertEqual(preapproval_access.call_count, 0)
                    self.assertEqual(durable_access.call_count, 0)
                    self.assertEqual(claim_access.call_count, 0)
                    self.assertEqual(cleanup_access.call_count, 0)
                    self.assertEqual(
                        self.tree_snapshot(self.project),
                        project_before,
                    )
                    self.assertEqual(
                        self.tree_snapshot(approval_root),
                        archive_before,
                    )
                    serialized = json.dumps(result, sort_keys=True)
                    self.assertNotIn(transaction.transaction_ref, serialized)
                    self.assertNotIn(str(approval_root), serialized)
                    self.assertNotIn(
                        "private-client-archive-secret-id",
                        serialized,
                    )
        finally:
            self.project = original_project

    def test_cleanup_unknown_after_archive_identity_boundary_reports_only_metadata_read(
        self,
    ) -> None:
        parent = (
            self.project
            / ".zettel-kasten"
            / "private"
            / "version-updates"
        )
        parent.mkdir(parents=True)
        (parent / ".cleanup_untrusted-race-residue").mkdir()

        result = archive_services._wom_kit_project_version_update_resume_live_transaction(
            self.project,
            target=None,
            reviewed_by=None,
            transaction_ref=None,
            approval_executor=lambda *_args, **_kwargs: self.fail(
                "cleanup unknown entered approval executor"
            ),
            _expected_approval_root=self.project,
            _expected_archive_id="archive-identity",
            _archive_identity_metadata_read=True,
        )

        self.assertEqual(
            result["status"],
            "terminal_cleanup_outcome_unknown",
        )
        self.assertTrue(result["client_archive_accessed"])
        self.assertTrue(result["archive_identity_metadata_read"])
        self.assertFalse(
            result["client_archive_domain_content_accessed"]
        )
        self.assertFalse(result["approval_key_accessed"])
        self.assertFalse(result["approval_claim_store_accessed"])

    def test_public_resume_cleanup_unknown_is_conservative_for_malformed_multiple_and_cap(
        self,
    ) -> None:
        original_project = self.project
        cases = ("malformed_multiple", "entry_cap", "scan_error")
        try:
            for index, case in enumerate(cases, start=1):
                with self.subTest(case=case):
                    self.project = (
                        Path(self.temporary.name) / f"cleanup-unsafe-{index}"
                    )
                    self.project.mkdir()
                    parent = (
                        self.project
                        / ".zettel-kasten"
                        / "private"
                        / "version-updates"
                    )
                    parent.mkdir(parents=True)
                    if case == "malformed_multiple":
                        (parent / ".cleanup_private-ref-one").mkdir()
                        (parent / ".cleanup-proof_private-ref-two").write_bytes(
                            b"untrusted"
                        )
                    else:
                        for entry_index in range(4):
                            (parent / f"benign-{entry_index}").write_bytes(b"")
                    before = self.tree_snapshot(self.project)
                    cap = (
                        patch.object(
                            transaction_module,
                            "MAX_TERMINAL_CLEANUP_SCAN_ENTRIES",
                            3,
                        )
                        if case == "entry_cap"
                        else patch.object(
                            transaction_module,
                            "MAX_TERMINAL_CLEANUP_SCAN_ENTRIES",
                            transaction_module.MAX_TERMINAL_CLEANUP_SCAN_ENTRIES,
                        )
                    )
                    def invoke_resume():
                        return archive_services._wom_kit_project_version_update_resume_live_transaction(
                            self.project,
                            target=None,
                            reviewed_by=None,
                            transaction_ref=None,
                            approval_executor=lambda *_args, **_kwargs: self.fail(
                                "unsafe cleanup residue entered approval"
                            ),
                            _expected_approval_root=self.project,
                            _expected_archive_id="private-archive-id",
                        )

                    with cap:
                        if case == "scan_error":
                            with patch.object(
                                transaction_module.os,
                                "scandir",
                                side_effect=OSError(
                                    "synthetic transaction-parent scan failure"
                                ),
                            ):
                                result = invoke_resume()
                        else:
                            result = invoke_resume()

                    self.assertFalse(result["ok"])
                    self.assertEqual(
                        result["status"],
                        "terminal_cleanup_outcome_unknown",
                    )
                    self.assertEqual(result["effects_state"], "unknown")
                    self.assertIsNone(result["update_completed"])
                    self.assertEqual(self.tree_snapshot(self.project), before)
                    serialized = json.dumps(result, sort_keys=True)
                    self.assertNotIn("private-ref-one", serialized)
                    self.assertNotIn("private-ref-two", serialized)
        finally:
            self.project = original_project

    def test_public_resume_without_lock_transaction_or_cleanup_artifact_stays_not_found(
        self,
    ) -> None:
        before = self.tree_snapshot(self.project)
        with self.assertRaises(ProjectUpdateTransactionError) as caught:
            archive_services._wom_kit_project_version_update_resume_live_transaction(
                self.project,
                target=None,
                reviewed_by=None,
                transaction_ref=None,
                approval_executor=lambda *_args, **_kwargs: self.fail(
                    "ordinary not-found entered approval"
                ),
                _expected_approval_root=self.project,
                _expected_archive_id="archive-identity",
            )
        self.assertEqual(
            caught.exception.code,
            "project_update_transaction_not_found",
        )
        self.assertEqual(self.tree_snapshot(self.project), before)

    def test_cleanup_unknown_identifier_audit_and_approval_id_assertion_are_exact(
        self,
    ) -> None:
        parent = (
            self.project
            / ".zettel-kasten"
            / "private"
            / "version-updates"
        )
        parent.mkdir(parents=True)
        (parent / ".cleanup_untrusted-private-name").mkdir()
        before = self.tree_snapshot(self.project)
        identifier_cases = (
            {"target": "v-private", "reviewed_by": None, "transaction_ref": None},
            {"target": None, "reviewed_by": "private-reviewer", "transaction_ref": None},
            {"target": None, "reviewed_by": None, "transaction_ref": "private-ref"},
        )

        for supplied in identifier_cases:
            with self.subTest(supplied=next(key for key, value in supplied.items() if value)):
                result = archive_services._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    approval_executor=lambda *_args, **_kwargs: self.fail(
                        "cleanup unknown entered approval executor"
                    ),
                    _expected_approval_root=self.project,
                    _expected_archive_id="private-archive-id",
                    **supplied,
                )
                self.assertTrue(
                    result["operator_resume_identifiers_supplied"]
                )
                serialized = json.dumps(result, sort_keys=True)
                for private_value in supplied.values():
                    if private_value:
                        self.assertNotIn(private_value, serialized)

        with self.assertRaisesRegex(
            archive_services.ArchiveServiceError,
            "exact_human_approval_resume_claim_invalid",
        ):
            archive_services._wom_kit_project_version_update_resume_live_transaction(
                self.project,
                target=None,
                reviewed_by=None,
                transaction_ref=None,
                approval_executor=lambda *_args, **_kwargs: self.fail(
                    "cleanup unknown entered approval executor"
                ),
                _expected_approval_root=self.project,
                _expected_archive_id="private-archive-id",
                _approval_identifier_supplied=True,
            )
        self.assertEqual(self.tree_snapshot(self.project), before)

    @unittest.skipUnless(
        os.name == "nt",
        "approved project-update mutation is Windows-only",
    )
    def test_abort_compaction_effect_is_preserved_on_mixed_normal_resume_result(
        self,
    ) -> None:
        normal = self.create_transaction(
            transaction_ref="update_11111111111111111111111111111111"
        )
        # v0.4.18: a fully ``completed`` original without handoff now routes to
        # terminal-original cleanup instead of the generic resume path, so the
        # "normal" resumable transaction here stops at the exact lockless
        # ``lock_released`` tail that the generic path still owns.
        normal_lock_bytes, normal_live = self.ready_forward(normal)
        normal_release = normal.release_lock_exact(
            expected_lock_bytes=normal_lock_bytes,
            live_component_sha256=normal_live,
        )
        self.assertTrue(normal_release.released)
        normal.append(
            phase="lock_released",
            stage="verified",
            live_component_sha256=normal_live,
            lock_release_result=normal_release,
        )
        abort_ref = "update_22222222222222222222222222222222"
        abort = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("abort-history-project"),
            requested_target_tag="v0.4.17",
            transaction_ref=abort_ref,
            ownership_nonce="1234567890abcdef1234567890abcdef",
            created_at=self.CREATED_AT,
        )
        abort_lock = abort.acquire_lock()
        abort_runtime_cleanup = self.runtime_cleanup_terminal_evidence(abort)
        abort.abort_before_intent_seal(
            expected_lock_bytes=abort_lock,
            runtime_cleanup_terminal_evidence=abort_runtime_cleanup,
        )
        recovered = {
            "ok": True,
            "status": "normal_resume_completed",
            "files_written": [
                ".zettel-kasten/installed-version.txt"
            ],
        }

        with (
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_approval_authority_matches",
                return_value=True,
            ),
            patch.object(
                archive_services,
                "_project_update_resume_preapproval_transaction",
                return_value=recovered,
            ) as normal_resume,
        ):
            result = (
                archive_services
                ._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=lambda *_args, **_kwargs: self.fail(
                        "mixed normal result entered approval executor"
                    ),
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive-identity",
                )
            )

        self.assertEqual(result["status"], "normal_resume_completed")
        self.assertEqual(
            result["files_written"],
            [".zettel-kasten/installed-version.txt"],
        )
        self.assertEqual(result["files_written_scope"], "project_domain_only")
        self.assertEqual(result["terminal_abort_histories_compacted"], 1)
        self.assertEqual(result["cleanup_proofs_written_or_verified"], 1)
        self.assertEqual(
            result["terminal_abort_history_compaction_state"],
            "complete",
        )
        self.assertFalse(
            result["terminal_abort_history_compaction_incomplete"]
        )
        self.assertTrue(
            result["effect_summary"]["project_domain_writes_performed"]
        )
        self.assertEqual(
            result["effect_summary"]["project_domain_files_written"],
            [".zettel-kasten/installed-version.txt"],
        )
        self.assertTrue(
            result["effect_summary"][
                "durable_control_evidence_written_or_verified"
            ]
        )
        self.assertTrue(
            result["effect_summary"][
                "terminal_abort_history_compaction_performed_or_verified"
            ]
        )
        self.assertTrue(
            result["effect_summary"][
                "private_control_mutation_performed_or_verified"
            ]
        )
        self.assertFalse(
            result["effect_summary"][
                "private_control_mutation_may_be_incomplete"
            ]
        )
        self.assertFalse(
            result["effect_summary"][
                "terminal_abort_history_cleanup_incomplete"
            ]
        )
        normal_resume.assert_called_once()
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(abort_ref, serialized)
        self.assertNotIn(digest("abort-history-project"), serialized)

    def test_public_resume_ambiguous_lockless_locator_returns_fixed_unknown_result(
        self,
    ) -> None:
        first = self.create_transaction(
            transaction_ref="update_33333333333333333333333333333333"
        )
        self.finish_forward(first)
        second = self.create_transaction(
            transaction_ref="update_44444444444444444444444444444444"
        )
        self.finish_forward(second)
        before = self.tree_snapshot(self.project)

        result = (
            archive_services
            ._wom_kit_project_version_update_resume_live_transaction(
                self.project,
                target=None,
                reviewed_by=None,
                transaction_ref=None,
                approval_executor=lambda *_args, **_kwargs: self.fail(
                    "ambiguous locator entered approval executor"
                ),
                _expected_approval_root=self.project,
                _expected_archive_id="archive-identity",
            )
        )

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["status"],
            "terminal_cleanup_outcome_unknown",
        )
        self.assertEqual(
            result["reason_code"],
            "project_version_update_terminal_cleanup_outcome_unknown",
        )
        self.assertFalse(result["domain_writer_entered"])
        self.assertEqual(result["project_domain_files_written"], [])
        self.assertEqual(result["files_written"], [])
        self.assertEqual(self.tree_snapshot(self.project), before)

    @unittest.skipUnless(os.name == "nt", "NTFS named-stream contract")
    def test_cleanup_proof_named_stream_blocks_fresh_preview_and_approval(
        self,
    ) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        cleanup_authority = digest("cleanup-proof-ads-authority")
        self.assertTrue(
            transaction.exact_cleanup(
                cleanup_authority_sha256=cleanup_authority,
            )
        )
        proof = (
            transaction.transaction_root.parent
            / f".cleanup-proof_{transaction.transaction_ref}.json"
        )
        self.assertTrue(proof.is_file())
        named_stream = Path(str(proof) + ":private-review-residue")
        private_stream_bytes = b"PRIVATE-NTFS-PROOF-STREAM"
        try:
            named_stream.write_bytes(private_stream_bytes)
        except OSError as failure:
            self.skipTest(f"named stream creation unavailable: {failure}")
        before = self.tree_snapshot(self.project)
        approval_calls: list[bool] = []

        with (
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_approval_authority_matches",
                return_value=True,
            ),
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_legacy_core",
                side_effect=AssertionError(
                    "ADS-tainted cleanup proof entered project writer"
                ),
            ) as legacy_core,
        ):
            dry_run_result = archive_services.wom_kit_project_version_update(
                self.project,
                target="v0.4.17",
                dry_run=True,
            )
            approval_result = (
                archive_services
                ._wom_kit_project_version_update_live_approval_transaction(
                    self.project,
                    target="v0.4.17",
                    reviewed_by="person:ads-proof-reviewer",
                    affirm_external_writers_quiescent=True,
                    approval_executor=lambda *_args, **_kwargs: (
                        approval_calls.append(True)
                    ),
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive-identity",
                )
            )

        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_artifact_classification_read_only(
                self.project
            ),
            ("unresolved", 0),
        )
        self.assertEqual(dry_run_result, approval_result)
        self.assertFalse(dry_run_result["ok"])
        self.assertEqual(
            dry_run_result["status"],
            "terminal_cleanup_outcome_unknown",
        )
        self.assertEqual(
            dry_run_result["reason_code"],
            "project_version_update_terminal_cleanup_outcome_unknown",
        )
        self.assertFalse(dry_run_result["domain_writer_entered"])
        self.assertEqual(dry_run_result["project_domain_files_written"], [])
        self.assertEqual(dry_run_result["files_written"], [])
        self.assertEqual(approval_calls, [])
        legacy_core.assert_not_called()
        self.assertEqual(self.tree_snapshot(self.project), before)
        self.assertEqual(named_stream.read_bytes(), private_stream_bytes)
        serialized = json.dumps(dry_run_result, sort_keys=True)
        self.assertNotIn(str(self.project), serialized)
        self.assertNotIn(private_stream_bytes.decode("ascii"), serialized)

    def test_public_resume_returns_unknown_when_mock_lock_has_no_namespace_entry(
        self,
    ) -> None:
        not_found = ProjectUpdateTransactionError(
            "project_update_transaction_not_found"
        )
        before = self.tree_snapshot(self.project)
        with (
            patch.object(
                transaction_module,
                "active_transaction_ref_for_resume_read_only",
                side_effect=[
                    not_found,
                    self.DEFAULT_TRANSACTION_REF,
                    self.DEFAULT_TRANSACTION_REF,
                ],
            ) as locator,
            patch.object(
                transaction_module,
                "inspect_terminal_cleanup_artifacts_for_resume_read_only",
                return_value="active_lock_changed",
            ) as cleanup_scan,
            patch.object(
                archive_services,
                "_project_update_resume_preapproval_transaction",
                side_effect=AssertionError(
                    "mock-only active locator entered a writer"
                ),
            ) as preapproval,
        ):
            result = archive_services._wom_kit_project_version_update_resume_live_transaction(
                self.project,
                target=None,
                reviewed_by=None,
                transaction_ref=None,
                approval_executor=lambda *_args, **_kwargs: self.fail(
                    "recovered new lock entered approval executor"
                ),
                _expected_approval_root=self.project,
                _expected_archive_id="archive-identity",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["status"],
            "terminal_cleanup_outcome_unknown",
        )
        self.assertEqual(
            result["reason_code"],
            "project_version_update_terminal_cleanup_outcome_unknown",
        )
        self.assertFalse(result["domain_writer_entered"])
        self.assertEqual(result["project_domain_files_written"], [])
        self.assertEqual(result["files_written"], [])
        self.assertEqual(locator.call_count, 2)
        self.assertEqual(cleanup_scan.call_count, 2)
        preapproval.assert_not_called()
        self.assertEqual(self.tree_snapshot(self.project), before)

    def test_untrusted_historical_cleanup_proof_blocks_exact_unlock_tail(
        self,
    ) -> None:
        transaction = self.create_transaction()
        lock_bytes, live = self.ready_forward(transaction)
        transaction.release_lock_exact(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
        )
        proof = (
            transaction.transaction_root.parent
            / ".cleanup-proof_update_ffffffffffffffffffffffffffffffff.json"
        )
        proof.write_bytes(b"untrusted historical proof")
        before = self.tree_snapshot(self.project)

        with (
            patch.object(
                archive_services,
                "_project_update_resume_preapproval_transaction",
                side_effect=AssertionError(
                    "untrusted cleanup proof entered a writer"
                ),
            ) as preapproval,
            patch.object(
                transaction_module,
                "_runtime_candidate_tree_inventory",
                side_effect=AssertionError(
                    "bounded regular locator materialized candidate inventory"
                ),
            ),
        ):
            result = archive_services._wom_kit_project_version_update_resume_live_transaction(
                self.project,
                target=None,
                reviewed_by=None,
                transaction_ref=None,
                approval_executor=lambda *_args, **_kwargs: self.fail(
                    "exact unlock tail entered approval executor"
                ),
                _expected_approval_root=self.project,
                _expected_archive_id="archive-identity",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["status"],
            "terminal_cleanup_outcome_unknown",
        )
        self.assertEqual(
            result["reason_code"],
            "project_version_update_terminal_cleanup_outcome_unknown",
        )
        self.assertFalse(result["domain_writer_entered"])
        self.assertEqual(result["project_domain_files_written"], [])
        self.assertEqual(result["files_written"], [])
        preapproval.assert_not_called()
        self.assertEqual(self.tree_snapshot(self.project), before)

    def test_hidden_approval_id_blocks_empty_reservation_recovery_without_writes(
        self,
    ) -> None:
        reserved = ProjectUpdateTransaction.reserve(
            self.project,
            project_identity_sha256=digest("project-identity"),
            requested_target_tag="v0.4.3",
            transaction_ref=self.DEFAULT_TRANSACTION_REF,
            ownership_nonce="abcdef0123456789abcdef0123456789",
            created_at=self.CREATED_AT,
        )
        lock_bytes = reserved.acquire_lock()
        self.assertEqual(
            inspect_prelock_orphans(self.project)[0].classification,
            "reserved_locked_unsealed",
        )
        before = self.tree_snapshot(self.project)
        executor_calls: list[bool] = []

        def approval_executor(*_args, **_kwargs):
            executor_calls.append(True)
            self.fail("hidden approval-id recovery entered approval executor")

        with patch.object(
            archive_services,
            "_wom_kit_project_version_update_approval_authority_matches",
            return_value=True,
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "exact_human_approval_resume_claim_invalid",
            ):
                archive_services._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=approval_executor,
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive-identity",
                    _approval_identifier_supplied=True,
                )

            self.assertEqual(self.tree_snapshot(self.project), before)
            self.assertEqual(
                (
                    self.project
                    / ".zettel-kasten"
                    / "version-update.lock"
                ).read_bytes(),
                lock_bytes,
            )
            self.assertEqual(executor_calls, [])

            recovered = archive_services._wom_kit_project_version_update_resume_live_transaction(
                self.project,
                target=None,
                reviewed_by=None,
                transaction_ref=None,
                approval_executor=approval_executor,
                _expected_approval_root=self.project,
                _expected_archive_id="archive-identity",
                _approval_identifier_supplied=False,
            )

        self.assertEqual(recovered["status"], "preapproval_scaffold_cancelled")
        self.assertEqual(
            recovered["preapproval_recovery"]["kind"],
            "empty_reservation_cancelled",
        )
        self.assertFalse(recovered["operator_resume_identifiers_supplied"])
        self.assert_preapproval_cancel_effect_truth(
            recovered,
            live_lock_verified=True,
            reservation_abort_evidence=True,
            candidate_cleanup=False,
        )
        self.assertEqual(executor_calls, [])

    def test_hidden_approval_id_blocks_sealed_preapproval_recovery_without_writes(
        self,
    ) -> None:
        reserved, _lock_bytes, tree = self.reserve_and_build_candidate()
        transaction = self.seal_reserved(reserved, tree)
        self.assertEqual(
            inspect_prelock_orphans(self.project)[0].classification,
            "intent_sealed_lock_binding_incomplete",
        )
        before = self.tree_snapshot(self.project)

        with patch.object(
            archive_services,
            "_wom_kit_project_version_update_approval_authority_matches",
            return_value=True,
        ):
            with self.assertRaisesRegex(
                archive_services.ArchiveServiceError,
                "exact_human_approval_resume_claim_invalid",
            ):
                archive_services._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=lambda *_args, **_kwargs: self.fail(
                        "hidden approval-id recovery entered approval executor"
                    ),
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive-identity",
                    _approval_identifier_supplied=True,
                )

        self.assertEqual(self.tree_snapshot(self.project), before)
        self.assertTrue(transaction.runtime_candidate_path.is_dir())
        self.assertEqual(
            inspect_prelock_orphans(self.project)[0].classification,
            "intent_sealed_lock_binding_incomplete",
        )

    def test_directory_fsync_reports_truth_and_false_result_is_not_success(self) -> None:
        result = transaction_module._fsync_directory(self.project)
        self.assertTrue(result.attempted)
        self.assertTrue(result.durable)
        self.assertIn(result.mechanism, {"posix_fsync", "windows_FlushFileBuffers"})
        transaction = self.create_transaction()
        self.activate(transaction)
        with patch.object(
            transaction_module,
            "_fsync_directory",
            return_value=DirectoryDurability(
                True, False, "synthetic", "directory_flush_failed"
            ),
        ):
            self.assert_code(
                "project_update_transaction_durability_unverified",
                lambda: transaction.append(
                    phase="lock_backlinked",
                    stage="verified",
                    live_component_sha256=self.live_pre(),
                ),
            )
        # The line may have reached the filesystem, but the API did not report
        # false durable success.  Reopen inspects the exact evidence as-is.
        reopened = ProjectUpdateTransaction.open(
            self.project, transaction.transaction_ref
        )
        self.assertEqual(len(reopened.inspect().journal.verified_prefix), 1)

    def test_claim_succeeded_handoff_correlates_same_ref_cleanup_tombstone(
        self,
    ) -> None:
        handoff_ref = "update_" + "a" * 32
        observation = (
            archive_services._ProjectUpdateTerminalHandoffObservation(
                state="claim_succeeded_pre_unlock",
                raw_sha256="sha256:" + "1" * 64,
                pending_record_sha256="sha256:" + "2" * 64,
                transaction_ref=handoff_ref,
            )
        )

        def observe_handoff(_root, *, _observation_out=None):
            if isinstance(_observation_out, list):
                _observation_out.append(observation)
            return "claim_succeeded_pre_unlock"

        not_found = ProjectUpdateTransactionError(
            "project_update_transaction_not_found"
        )
        for tombstone_ref, expected_status in (
            (handoff_ref, None),
            ("update_" + "b" * 32, "terminal_cleanup_outcome_unknown"),
        ):
            with self.subTest(tombstone_ref=tombstone_ref):
                tombstone = SimpleNamespace(transaction_ref=tombstone_ref)
                with (
                    patch.object(
                        archive_services,
                        "_project_update_terminal_handoff_state_read_only",
                        side_effect=observe_handoff,
                    ),
                    patch.object(
                        transaction_module,
                        "active_transaction_ref_for_resume_read_only",
                        side_effect=not_found,
                    ),
                    patch.object(
                        transaction_module,
                        "inspect_terminal_cleanup_artifacts_for_resume_read_only",
                        return_value="exact_cleanup_observed",
                    ),
                    patch.object(
                        archive_services,
                        "_project_update_terminal_cleanup_artifact_classification_read_only",
                        return_value=("recoverable_exact", 1),
                    ),
                    patch.object(
                        ProjectUpdateTransaction,
                        "discover_complete_cleanup_tombstone_for_resume_read_only",
                        return_value=tombstone,
                    ),
                ):
                    gate = (
                        archive_services
                        ._project_update_terminal_cleanup_unknown_gate_read_only(
                            self.project,
                            operator_resume_identifiers_supplied=False,
                        )
                    )
                    fresh = (
                        archive_services
                        ._project_update_fresh_update_cleanup_preflight_read_only(
                            self.project
                        )
                    )
                if expected_status is None:
                    self.assertIsNone(gate)
                    self.assertEqual(
                        fresh["status"],
                        "terminal_cleanup_required",
                    )
                else:
                    self.assertEqual(gate["status"], expected_status)
                    self.assertEqual(fresh["status"], expected_status)

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_fresh_approval_holds_one_exact_terminal_lease_through_callbacks(
        self,
    ) -> None:
        transaction_ref = "update_" + "7" * 32
        transaction_state = SimpleNamespace(
            transaction_ref=transaction_ref,
        )
        state = SimpleNamespace(
            inspection_root=self.project,
            project_root=self.project,
            transaction=transaction_state,
            prepared_preview={"status": "prepared"},
            reviewer="reviewer-a",
            terminal_update_verified=False,
        )
        prepared = archive_services._ProjectVersionUpdatePreparedApproval(
            preview={"status": "prepared"},
            state=state,
        )

        def prepared_generator():
            yield prepared

        guard_enters: list[str] = []
        actual_bound_guard = (
            archive_services._project_update_terminal_bound_guard
        )

        @contextmanager
        def counted_bound_guard(*args, **kwargs):
            guard_enters.append("entered")
            with actual_bound_guard(*args, **kwargs) as held:
                yield held

        terminal_checks: list[str] = []
        domain_result = {"ok": True, "status": "synthetic-complete"}

        def writer(observed_state, _claim):
            self.assertIs(observed_state, state)
            self.assertTrue(
                archive_services
                ._project_update_terminal_execution_lease_is_held(state)
            )
            terminal_checks.append("writer")
            return domain_result

        def finalizer(observed_state, _claim):
            self.assertIs(observed_state, state)
            self.assertTrue(
                archive_services
                ._project_update_terminal_execution_lease_is_held(state)
            )
            terminal_checks.append("finalizer")

        def checkpoint_guard(observed_state, _claim, *, succeeded):
            self.assertIs(observed_state, state)
            self.assertTrue(
                archive_services
                ._project_update_terminal_execution_lease_is_held(state)
            )
            terminal_checks.append(
                "succeeded-guard" if succeeded else "started-guard"
            )
            return True

        def approval_executor(
            _preview,
            continue_started,
            finalize_succeeded,
            started_guard,
            succeeded_guard,
            **_kwargs,
        ):
            self.assertTrue(
                archive_services
                ._project_update_terminal_execution_lease_is_held(state)
            )
            claim = object()
            self.assertTrue(started_guard(claim))
            result = continue_started(
                claim,
                "sha256:" + "1" * 64,
                "sha256:" + "2" * 64,
            )
            self.assertTrue(succeeded_guard(claim))
            finalize_succeeded(claim)
            return result

        binding = SimpleNamespace(
            plan_sha256="sha256:" + "1" * 64,
            target_binding_sha256="sha256:" + "2" * 64,
        )
        with (
            patch.object(
                archive_services,
                "_project_update_fresh_update_cleanup_preflight_read_only",
                return_value=None,
            ),
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_approval_authority_matches",
                return_value=True,
            ),
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_legacy_core_generator",
                side_effect=lambda *_args, **_kwargs: prepared_generator(),
            ),
            patch.object(
                archive_services,
                "_project_update_terminal_cleanup_unknown_gate_read_only",
                return_value=None,
            ),
            patch.object(
                archive_services,
                "_project_update_terminal_bound_guard",
                side_effect=counted_bound_guard,
            ),
            patch.object(
                archive_services,
                "project_version_update_approval_binding",
                return_value=binding,
            ),
            patch.object(
                archive_services,
                "assert_same_binding",
                return_value=None,
            ),
            patch.object(
                archive_services,
                "_project_update_durable_writer",
                side_effect=writer,
            ),
            patch.object(
                archive_services,
                "_project_update_succeeded_claim_finalizer",
                side_effect=finalizer,
            ),
            patch.object(
                archive_services,
                "_project_update_claim_checkpoint_guard",
                side_effect=checkpoint_guard,
            ),
        ):
            result = (
                archive_services
                ._wom_kit_project_version_update_live_approval_transaction(
                    self.project,
                    target="v0.4.17",
                    reviewed_by="reviewer-a",
                    affirm_external_writers_quiescent=True,
                    approval_executor=approval_executor,
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive:test",
                )
            )

        self.assertEqual(result, domain_result)
        self.assertEqual(guard_enters, ["entered"])
        self.assertEqual(
            terminal_checks,
            ["started-guard", "writer", "succeeded-guard", "finalizer"],
        )

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_execution_lease_is_owned_by_exact_state_identity(self) -> None:
        transaction = SimpleNamespace(
            transaction_ref="update_" + "8" * 32,
        )
        first = SimpleNamespace(
            inspection_root=self.project,
            project_root=self.project,
            transaction=transaction,
        )
        second = SimpleNamespace(
            inspection_root=self.project,
            project_root=self.project,
            transaction=transaction,
        )
        with patch.object(
            archive_services,
            "_project_update_terminal_cleanup_unknown_gate_read_only",
            return_value=None,
        ):
            with archive_services._project_update_terminal_execution_lease(
                first,
                expected_handoff_observation=None,
                fresh_absence=True,
            ):
                self.assertTrue(
                    archive_services
                    ._project_update_terminal_execution_lease_is_held(first)
                )
                self.assertFalse(
                    archive_services
                    ._project_update_terminal_execution_lease_is_held(second)
                )

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_ready_replay_holds_guard_through_native_and_cleanup(
        self,
    ) -> None:
        handoff_ref = "update_" + "c" * 32
        pending_record = {
            "payload": {
                "plan_sha256": "sha256:" + "1" * 64,
                "target_binding_sha256": "sha256:" + "2" * 64,
                "claim_succeeded_checkpoint_sha256": (
                    "sha256:" + "3" * 64
                ),
                "exact_postimage_sha256": "sha256:" + "4" * 64,
                "legacy_cleanup_authority_sha256": None,
                "reviewer": "reviewer-a",
                "transaction_ref": handoff_ref,
            }
        }
        ready_record = {
            "payload": {
                "plan_sha256": "sha256:" + "1" * 64,
                "target_binding_sha256": "sha256:" + "2" * 64,
                "pending_record_sha256": (
                    archive_services.project_update_transaction
                    .sha256_document(pending_record)
                ),
                "claim_succeeded_checkpoint_sha256": (
                    "sha256:" + "3" * 64
                ),
                "exact_postimage_sha256": "sha256:" + "4" * 64,
                "delivery_capability_sha256": (
                    archive_services.project_update_transaction.sha256_bytes(
                        b"capability"
                    )
                ),
                "legacy_cleanup_authority_sha256": None,
            }
        }
        active = {
            "schema": archive_services._PROJECT_UPDATE_TERMINAL_HANDOFF_SCHEMA,
            "state": "terminal_ready",
            "pending": pending_record,
            "ready": ready_record,
        }
        active_raw = archive_services._project_update_canonical_bytes(active)
        observation = (
            archive_services._ProjectUpdateTerminalHandoffObservation(
                state="terminal_ready",
                raw_sha256=(
                    archive_services.project_update_transaction.sha256_bytes(
                        active_raw
                    )
                ),
                pending_record_sha256=(
                    archive_services.project_update_transaction
                    .sha256_document(pending_record)
                ),
                transaction_ref=handoff_ref,
            )
        )
        binding = SimpleNamespace(
            plan_sha256="sha256:" + "1" * 64,
            target_binding_sha256="sha256:" + "2" * 64,
        )
        domain_result = {"ok": True, "status": "updated_restart_required"}
        cleanup_entered: list[bool] = []
        competing_acquired: list[bool] = []
        competing_finished = threading.Event()

        def competing_guard() -> None:
            try:
                with archive_services._project_update_terminal_control_boundary(
                    self.project
                ):
                    competing_acquired.append(True)
            except OSError:
                competing_acquired.append(False)
            finally:
                competing_finished.set()

        def approval_executor(
            _preview,
            _started_writer,
            finalizer,
            _started_guard,
            succeeded_guard,
            _reviewer,
            **_kwargs,
        ):
            competitor = threading.Thread(target=competing_guard)
            competitor.start()
            self.assertTrue(competing_finished.wait(timeout=5.0))
            competitor.join(timeout=5.0)
            self.assertFalse(competitor.is_alive())
            claim = SimpleNamespace(public_reference=lambda: {})
            self.assertTrue(succeeded_guard(claim))
            finalizer(claim)
            return {"ok": True}

        def authenticated_cleanup(*_args, **_kwargs):
            cleanup_entered.append(True)
            self.assertEqual(competing_acquired, [False])
            return True

        with (
            patch.object(
                archive_services,
                "_project_update_read_terminal_document",
                return_value=(active, active_raw),
            ),
            patch.object(
                archive_services,
                "_project_update_terminal_handoff_attachments",
                return_value=(
                    {"status": "prepared"},
                    domain_result,
                    {"target_tag": "v0.4.17"},
                    {},
                ),
            ),
            patch.object(
                archive_services,
                "project_version_update_approval_binding",
                return_value=binding,
            ),
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_approval_authority_matches",
                return_value=True,
            ),
            patch.object(
                archive_services,
                "_project_update_terminal_delivery_capability",
                return_value="capability",
            ),
            patch.object(
                archive_services,
                "_project_update_terminal_record_matches_claim",
                return_value=True,
            ),
            patch.object(
                archive_services,
                "_project_update_terminal_postimage_matches",
                return_value=True,
            ),
            patch.object(
                archive_services,
                "_project_update_register_terminal_delivery_capability",
            ),
            patch.object(
                archive_services,
                "_project_update_resume_authenticated_terminal_cleanup",
                side_effect=authenticated_cleanup,
            ),
        ):
            replayed = (
                archive_services
                ._project_update_replay_ready_terminal_handoff(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=approval_executor,
                    expected_approval_root=self.project,
                    expected_archive_id="archive:test",
                    _expected_handoff_observation=observation,
                )
            )

        self.assertTrue(replayed["ok"])
        self.assertEqual(competing_acquired, [False])
        self.assertEqual(cleanup_entered, [True])

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_mutation_resume_holds_one_exact_terminal_lease_through_callbacks(
        self,
    ) -> None:
        project_transaction = self.create_transaction(
            transaction_ref="update_" + "d" * 32
        )
        lock_bytes = self.activate(project_transaction)
        live = self.live_pre()
        project_transaction.append(
            phase="lock_backlinked",
            stage="verified",
            live_component_sha256=live,
        )
        closed: list[str] = []
        state = SimpleNamespace(
            inspection_root=self.project,
            project_root=self.project,
            transaction=project_transaction,
            expected_lock_bytes=lock_bytes,
            prepared_preview={"status": "prepared"},
            reviewer="reviewer-a",
            approved_plan_sha256=None,
            approved_target_binding_sha256=None,
            terminal_update_verified=False,
            transaction_cleanup_completed=None,
            directory_guard=SimpleNamespace(
                close=lambda: closed.append("directory")
            ),
        )
        lifetime = SimpleNamespace(
            close_after_service_transaction=lambda: closed.append("runner")
        )
        guard_enters: list[str] = []
        callback_checks: list[str] = []
        actual_bound_guard = (
            archive_services._project_update_terminal_bound_guard
        )

        @contextmanager
        def counted_bound_guard(*args, **kwargs):
            guard_enters.append("entered")
            with actual_bound_guard(*args, **kwargs) as held:
                yield held

        def assert_owned(label: str) -> None:
            self.assertTrue(
                archive_services
                ._project_update_terminal_execution_lease_is_held(state)
            )
            callback_checks.append(label)

        result_payload = {"ok": True, "status": "resume-complete"}

        def writer(observed_state, _claim):
            self.assertIs(observed_state, state)
            assert_owned("writer")
            return result_payload

        def finalizer(observed_state, _claim):
            self.assertIs(observed_state, state)
            assert_owned("finalizer")

        def checkpoint_guard(observed_state, _claim, *, succeeded):
            self.assertIs(observed_state, state)
            assert_owned(
                "succeeded-guard" if succeeded else "started-guard"
            )
            return True

        def approval_executor(
            _preview,
            continue_started,
            finalize_succeeded,
            started_guard,
            succeeded_guard,
            _reviewer,
            **_kwargs,
        ):
            assert_owned("executor")
            claim = object()
            self.assertTrue(started_guard(claim))
            result = continue_started(
                claim,
                "sha256:" + "1" * 64,
                "sha256:" + "2" * 64,
            )
            self.assertTrue(succeeded_guard(claim))
            finalize_succeeded(claim)
            return result

        binding = SimpleNamespace(
            plan_sha256="sha256:" + "1" * 64,
            target_binding_sha256="sha256:" + "2" * 64,
        )
        with (
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_approval_authority_matches",
                return_value=True,
            ),
            patch.object(
                archive_services,
                "_project_update_resume_preapproval_transaction",
                return_value=None,
            ),
            patch.object(
                archive_services,
                "_project_update_reopen_durable_state",
                return_value=(state, lifetime),
            ),
            patch.object(
                archive_services,
                "_project_update_terminal_bound_guard",
                side_effect=counted_bound_guard,
            ),
            patch.object(
                archive_services,
                "project_version_update_approval_binding",
                return_value=binding,
            ),
            patch.object(
                archive_services,
                "assert_same_binding",
                return_value=None,
            ),
            patch.object(
                archive_services,
                "_project_update_durable_writer",
                side_effect=writer,
            ),
            patch.object(
                archive_services,
                "_project_update_succeeded_claim_finalizer",
                side_effect=finalizer,
            ),
            patch.object(
                archive_services,
                "_project_update_claim_checkpoint_guard",
                side_effect=checkpoint_guard,
            ),
        ):
            result = (
                archive_services
                ._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=approval_executor,
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive:test",
                )
            )

        self.assertEqual(result, result_payload)
        self.assertEqual(guard_enters, ["entered"])
        self.assertEqual(
            callback_checks,
            [
                "executor",
                "started-guard",
                "writer",
                "succeeded-guard",
                "finalizer",
            ],
        )
        self.assertEqual(closed, ["directory", "runner"])

    def test_fresh_terminal_boundary_failure_cancels_preapproval_with_effect_truth(
        self,
    ) -> None:
        for cleanup_succeeds in (True, False):
            with self.subTest(cleanup_succeeds=cleanup_succeeds):
                state = SimpleNamespace(
                    inspection_root=self.project,
                    project_root=self.project,
                    transaction=SimpleNamespace(
                        transaction_ref="update_" + "9" * 32,
                    ),
                    prepared_preview={"status": "prepared"},
                    reviewer="reviewer-a",
                    terminal_update_verified=False,
                )
                prepared = (
                    archive_services._ProjectVersionUpdatePreparedApproval(
                        preview={"status": "prepared"},
                        state=state,
                    )
                )

                def prepared_generator():
                    yield prepared

                @contextmanager
                def failed_boundary(*_args, **_kwargs):
                    raise archive_services.ArchiveServiceError(
                        "project_version_update_terminal_execution_boundary_unknown"
                    )
                    yield

                cleanup_calls: list[str] = []

                def cancel_before_native(_state):
                    cleanup_calls.append("attempted")
                    if not cleanup_succeeds:
                        raise archive_services.ArchiveServiceError(
                            "private-cleanup-failure-must-not-escape"
                        )

                executor_calls: list[str] = []
                with (
                    patch.object(
                        archive_services,
                        "_project_update_fresh_update_cleanup_preflight_read_only",
                        return_value=None,
                    ),
                    patch.object(
                        archive_services,
                        "_wom_kit_project_version_update_approval_authority_matches",
                        return_value=True,
                    ),
                    patch.object(
                        archive_services,
                        "_wom_kit_project_version_update_legacy_core_generator",
                        side_effect=lambda *_args, **_kwargs: prepared_generator(),
                    ),
                    patch.object(
                        archive_services,
                        "_project_update_terminal_execution_lease",
                        side_effect=failed_boundary,
                    ),
                    patch.object(
                        archive_services,
                        "_project_update_cancel_before_native",
                        side_effect=cancel_before_native,
                    ),
                ):
                    result = (
                        archive_services
                        ._wom_kit_project_version_update_live_approval_transaction(
                            self.project,
                            target="v0.4.17",
                            reviewed_by="reviewer-a",
                            affirm_external_writers_quiescent=True,
                            approval_executor=lambda *_args, **_kwargs: (
                                executor_calls.append("entered")
                            ),
                            _expected_approval_root=self.project,
                            _expected_archive_id="archive:test",
                        )
                    )

                self.assertEqual(cleanup_calls, ["attempted"])
                self.assertEqual(executor_calls, [])
                self.assertEqual(
                    result["status"],
                    "terminal_cleanup_outcome_unknown",
                )
                self.assertFalse(
                    result["effect_summary"][
                        "project_domain_writes_performed"
                    ]
                )
                self.assertIs(
                    result["preapproval_cleanup"]["completed"],
                    cleanup_succeeds,
                )
                self.assertIs(
                    result["effect_summary"][
                        "private_control_mutation_may_be_incomplete"
                    ],
                    not cleanup_succeeds,
                )
                serialized = json.dumps(result, sort_keys=True)
                self.assertNotIn("private-cleanup-failure", serialized)
                self.assertNotIn("update_" + "9" * 32, serialized)

    # ------------------------------------------------------------------
    # v0.4.18: one completed original without handoff authority whose
    # project post-image was later superseded (the beta letter 153 shape).
    # ------------------------------------------------------------------

    TERMINAL_ORIGINAL_TEST_KEY = bytes(range(32))
    TERMINAL_ORIGINAL_ARCHIVE_ID = "terminal-original-archive"
    TERMINAL_ORIGINAL_APPROVAL_ID = "approval_" + "5" * 32

    def terminal_original_archive_root(self) -> Path:
        approval_root = Path(self.temporary.name) / "terminal-original-archive"
        if not approval_root.exists():
            approval_root.mkdir()
            (approval_root / "archive.yml").write_text(
                f"archive_id: {self.TERMINAL_ORIGINAL_ARCHIVE_ID}\n",
                encoding="utf-8",
            )
            (approval_root / "sentinel.bin").write_bytes(b"client archive")
        return approval_root

    def synthetic_claim_reference(
        self,
        archive_root: Path,
        *,
        status: str = "succeeded",
        approval_id: str | None = None,
        plan_label: str = "terminal-original-plan",
    ) -> str:
        """Write one MAC-authenticated claim; return its journal reference digest."""

        approval_id = approval_id or self.TERMINAL_ORIGINAL_APPROVAL_ID
        archive_id = self.TERMINAL_ORIGINAL_ARCHIVE_ID
        context = {
            "operation": "project_version_update",
            "archive_identity_sha256": (
                exact_human_approval.exact_human_approval_archive_identity_sha256(
                    archive_id
                )
            ),
            "plan_sha256": digest(plan_label),
            "target_binding_sha256": digest("terminal-original-target"),
            "reviewer_claim_sha256": digest("terminal-original-reviewer"),
            "review_binding_codes": ["plan_digest", "target_digest"],
            "warning_codes": [],
        }
        context_sha256 = exact_human_approval._sha256(
            exact_human_approval._AUTHORITY_DOMAIN
            + exact_human_approval._canonical_bytes(context)
        )
        approved_at = "2026-08-29T08:36:00.000000Z"
        authority = {
            "approval_id": approval_id,
            "archive_id": archive_id,
            "context_sha256": context_sha256,
            "reviewer_claim_sha256": context["reviewer_claim_sha256"],
            "approved_at": approved_at,
        }
        authority_sha256 = exact_human_approval._sha256(
            exact_human_approval._AUTHORITY_DOMAIN
            + exact_human_approval._canonical_bytes(authority)
        )
        document = {
            "schema_version": exact_human_approval.CLAIM_SCHEMA_VERSION,
            "approval_id": approval_id,
            "archive_id": archive_id,
            "context": context,
            "context_sha256": context_sha256,
            "approval_authority_sha256": authority_sha256,
            "reviewer_claim_sha256": context["reviewer_claim_sha256"],
            "reviewer_identity_authenticated": False,
            "interactive_intent": {
                "mechanism": CURRENT_INTERACTIVE_INTENT_MECHANISM,
                "confirmed": True,
            },
            "approved_at": approved_at,
            "started_at": approved_at,
            "status": status,
            "finished_at": (
                None if status == "started" else "2026-08-29T08:37:00.000000Z"
            ),
            "failure_code": "synthetic_failure" if status == "failed" else None,
        }
        authenticated = exact_human_approval._authenticated(
            document,
            self.TERMINAL_ORIGINAL_TEST_KEY,
        )
        claims_root = archive_root.joinpath(
            *Path(exact_human_approval.CLAIMS_RELATIVE_ROOT).parts
        )
        claims_root.mkdir(parents=True, exist_ok=True)
        (claims_root / f"{approval_id}.json").write_bytes(
            exact_human_approval._canonical_bytes(authenticated)
        )
        reference = {
            "schema_version": exact_human_approval.REFERENCE_SCHEMA_VERSION,
            "approval_id": approval_id,
            "context_sha256": context_sha256,
            "approval_authority_sha256": authority_sha256,
            "one_use": True,
        }
        return sha256_bytes(
            archive_services._project_update_canonical_bytes(reference)
        )

    class _TerminalOriginalKeyProvider:
        def __init__(self, key: bytes) -> None:
            self.key = key
            self.calls = 0
            self.create_if_missing: list[bool] = []

        def use_key(self, _root, consumer, *, create_if_missing=False):
            self.calls += 1
            self.create_if_missing.append(create_if_missing)
            buffer = bytearray(self.key)
            try:
                return consumer(memoryview(buffer))
            finally:
                buffer[:] = b"\0" * len(buffer)

    def build_terminal_original(
        self,
        *,
        approval_reference: str,
        transaction_ref: str = DEFAULT_TRANSACTION_REF,
        legacy_plan: bool = True,
    ) -> ProjectUpdateTransaction:
        """Leave exactly the predecessor 'plan written, rename lost' shape."""

        transaction = self.create_transaction(transaction_ref=transaction_ref)
        self.finish_forward(transaction, approval_reference=approval_reference)
        root = self.transaction_root(transaction)
        if legacy_plan:
            with patch.object(
                transaction_module,
                "_atomic_move_directory_no_replace",
                side_effect=OSError("synthetic tombstone rename failure"),
            ):
                self.assertFalse(
                    transaction.exact_cleanup(
                        cleanup_authority_sha256=approval_reference
                    )
                )
            self.assertTrue(root.is_dir())
            current_plan_path = root / CLEANUP_PLAN_NAME
            legacy_plan_path = root / LEGACY_CLEANUP_PLAN_NAME
            legacy = json.loads(current_plan_path.read_text(encoding="ascii"))
            legacy["schema"] = LEGACY_CLEANUP_PLAN_SCHEMA
            legacy.pop("transaction_root_identity")
            legacy_plan_path.write_bytes(transaction_module._document_bytes(legacy))
            current_plan_path.unlink()
        self.assertFalse((root.parent / f".cleanup_{transaction_ref}").exists())
        self.assertFalse(
            (root.parent / f".cleanup-proof_{transaction_ref}.json").exists()
        )
        self.assertFalse(
            (self.project / ".zettel-kasten" / "version-update.lock").exists()
        )
        return ProjectUpdateTransaction.open(self.project, transaction_ref)

    def run_terminal_original_resume(
        self,
        *,
        approval_root: Path,
        key_provider=None,
        extra_patches=(),
    ) -> dict:
        executor_calls: list[bool] = []

        def approval_executor(*_args, **_kwargs):
            executor_calls.append(True)
            self.fail("terminal original entered the approval executor")

        stack = ExitStack()
        with stack:
            stack.enter_context(
                patch.object(
                    archive_services,
                    "_wom_kit_project_version_update_approval_authority_matches",
                    return_value=True,
                )
            )
            stack.enter_context(
                patch.object(
                    archive_services,
                    "_project_update_reopen_durable_state",
                    side_effect=AssertionError(
                        "terminal original reopened durable approval state"
                    ),
                )
            )
            stack.enter_context(
                patch.object(
                    archive_services,
                    "_project_update_durable_writer",
                    side_effect=AssertionError(
                        "terminal original entered the domain writer"
                    ),
                )
            )
            if key_provider is not None:
                stack.enter_context(
                    patch.object(
                        archive_services,
                        "_project_update_terminal_original_key_provider",
                        return_value=key_provider,
                    )
                )
            for extra in extra_patches:
                stack.enter_context(extra)
            result = (
                archive_services
                ._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=approval_executor,
                    _expected_approval_root=approval_root,
                    _expected_archive_id=self.TERMINAL_ORIGINAL_ARCHIVE_ID,
                )
            )
        self.assertEqual(executor_calls, [])
        return result

    def test_terminal_original_inspection_accepts_exact_legacy_planned_original_only(
        self,
    ) -> None:
        reference = digest("terminal-original-approval-reference")
        transaction = self.build_terminal_original(approval_reference=reference)
        root = self.transaction_root(transaction)
        ref = transaction.transaction_ref

        inspection = (
            transaction_module.inspect_terminal_original_for_resume_read_only(
                self.project,
                ref,
            )
        )
        self.assertIsNotNone(inspection)
        assert inspection is not None
        self.assertEqual(inspection.transaction_ref, ref)
        self.assertEqual(inspection.approval_reference_sha256, reference)
        self.assertTrue(inspection.cleanup_plan_present)
        self.assertEqual(inspection.cleanup_plan_schema, LEGACY_CLEANUP_PLAN_SCHEMA)
        self.assertEqual(
            inspection.terminal_checkpoint_sha256,
            transaction.inspect().journal.head_sha256,
        )
        self.assertEqual(inspection.intent_sha256, transaction.intent.sha256)
        self.assertGreater(inspection.file_count, 0)
        pristine = self.tree_snapshot(self.project)

        legacy_plan_path = root / LEGACY_CLEANUP_PLAN_NAME
        original_plan_bytes = legacy_plan_path.read_bytes()
        lock_path = self.project / ".zettel-kasten" / "version-update.lock"
        tombstone = root.parent / f".cleanup_{ref}"
        proof = root.parent / f".cleanup-proof_{ref}.json"
        sidecar = root / CLEANUP_PLAN_NAME
        extra = root / "extra-member.bin"

        def rewrite_plan(**changes) -> None:
            plan = json.loads(original_plan_bytes.decode("ascii"))
            plan.update(changes)
            legacy_plan_path.write_bytes(transaction_module._document_bytes(plan))

        drift_cases = {
            "plan_authority_mismatch": (
                lambda: rewrite_plan(
                    cleanup_authority_sha256=digest("foreign-authority")
                ),
                lambda: legacy_plan_path.write_bytes(original_plan_bytes),
            ),
            "unexpected_member": (
                lambda: extra.write_bytes(b"unexpected"),
                lambda: extra.unlink(),
            ),
            "tombstone_present": (
                lambda: tombstone.mkdir(),
                lambda: tombstone.rmdir(),
            ),
            "proof_present": (
                lambda: proof.write_bytes(b"{}\n"),
                lambda: proof.unlink(),
            ),
            "live_lock_present": (
                lambda: lock_path.write_bytes(b"lock"),
                lambda: lock_path.unlink(),
            ),
            "current_schema_sidecar_present": (
                lambda: sidecar.write_bytes(b"{}\n"),
                lambda: sidecar.unlink(),
            ),
        }
        for case, (apply, revert) in drift_cases.items():
            with self.subTest(case=case):
                apply()
                try:
                    self.assertIsNone(
                        transaction_module
                        .inspect_terminal_original_for_resume_read_only(
                            self.project,
                            ref,
                        )
                    )
                finally:
                    revert()
                self.assertEqual(self.tree_snapshot(self.project), pristine)

    def test_terminal_original_plan_less_completed_original_keeps_generic_route(
        self,
    ) -> None:
        reference = digest("terminal-original-approval-reference")
        transaction = self.build_terminal_original(
            approval_reference=reference,
            legacy_plan=False,
        )
        ref = transaction.transaction_ref
        self.assertEqual(
            transaction_module.classify_terminal_original_for_resume_read_only(
                self.project,
                ref,
            ),
            ("not_applicable", None),
        )
        self.assertIsNone(
            transaction_module.inspect_terminal_original_for_resume_read_only(
                self.project,
                ref,
            )
        )
        # Today's label and generic routing are preserved for shapes this
        # contract does not own (v0.4.17 decision 18 stays intact).
        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_artifact_classification_read_only(
                self.project
            ),
            ("resume_required_exact", 1),
        )
        preflight = (
            archive_services
            ._project_update_fresh_update_cleanup_preflight_read_only(
                self.project
            )
        )
        assert preflight is not None
        self.assertEqual(
            preflight["outcome_basis"],
            "exact_terminal_control_history_requires_resume",
        )

    def test_terminal_original_current_schema_sidecar_is_exact_only_with_journal_authority(
        self,
    ) -> None:
        reference = digest("terminal-original-approval-reference")
        transaction = self.build_terminal_original(approval_reference=reference)
        root = self.transaction_root(transaction)
        ref = transaction.transaction_ref
        # v0.4.18's own crash window: the identity-bound sidecar is durable
        # beside the legacy plan but the tombstone rename never happened.
        with patch.object(
            transaction_module,
            "_atomic_move_directory_no_replace",
            side_effect=OSError("synthetic tombstone rename failure"),
        ):
            self.assertFalse(
                ProjectUpdateTransaction.open(self.project, ref).exact_cleanup(
                    cleanup_authority_sha256=reference
                )
            )
        sidecar = root / CLEANUP_PLAN_NAME
        self.assertTrue(sidecar.is_file())
        self.assertTrue((root / LEGACY_CLEANUP_PLAN_NAME).is_file())
        state, inspection = (
            transaction_module.classify_terminal_original_for_resume_read_only(
                self.project,
                ref,
            )
        )
        self.assertEqual(state, "exact")
        assert inspection is not None
        self.assertEqual(inspection.cleanup_plan_schema, CLEANUP_PLAN_SCHEMA)
        self.assertEqual(inspection.approval_reference_sha256, reference)
        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_artifact_classification_read_only(
                self.project
            ),
            ("terminal_original_exact", 1),
        )

        sidecar_bytes = sidecar.read_bytes()
        sidecar_document = json.loads(sidecar_bytes.decode("ascii"))
        handoff_authority = dict(sidecar_document)
        handoff_authority["cleanup_authority_sha256"] = digest("handoff-digest")
        sidecar.write_bytes(transaction_module._document_bytes(handoff_authority))
        try:
            self.assertEqual(
                transaction_module
                .classify_terminal_original_for_resume_read_only(
                    self.project,
                    ref,
                ),
                ("not_applicable", None),
            )
            self.assertEqual(
                archive_services
                ._project_update_terminal_cleanup_artifact_classification_read_only(
                    self.project
                ),
                ("resume_required_exact", 1),
            )
        finally:
            sidecar.write_bytes(sidecar_bytes)

        moved_identity = dict(sidecar_document)
        moved_identity["transaction_root_identity"] = {
            **sidecar_document["transaction_root_identity"],
            "inode": sidecar_document["transaction_root_identity"]["inode"] + 1,
        }
        sidecar.write_bytes(transaction_module._document_bytes(moved_identity))
        try:
            self.assertEqual(
                transaction_module
                .classify_terminal_original_for_resume_read_only(
                    self.project,
                    ref,
                )[0],
                "refused",
            )
            self.assertEqual(
                archive_services
                ._project_update_terminal_cleanup_artifact_classification_read_only(
                    self.project
                ),
                ("unresolved", 0),
            )
        finally:
            sidecar.write_bytes(sidecar_bytes)

    def test_terminal_original_is_classified_and_blocked_consistently_read_only(
        self,
    ) -> None:
        reference = digest("terminal-original-approval-reference")
        transaction = self.build_terminal_original(approval_reference=reference)
        root = self.transaction_root(transaction)
        pristine = self.tree_snapshot(self.project)

        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_artifact_classification_read_only(
                self.project
            ),
            ("terminal_original_exact", 1),
        )
        preflight = (
            archive_services
            ._project_update_fresh_update_cleanup_preflight_read_only(
                self.project
            )
        )
        self.assertIsNotNone(preflight)
        assert preflight is not None
        self.assertFalse(preflight["ok"])
        self.assertEqual(preflight["status"], "terminal_cleanup_required")
        self.assertEqual(
            preflight["reason_code"],
            "project_version_update_terminal_cleanup_required",
        )
        self.assertEqual(
            preflight["outcome_basis"],
            "exact_terminal_transaction_cleanup_requires_resume",
        )
        self.assertTrue(preflight["terminal_transaction_cleanup_required"])
        self.assertTrue(preflight["resumable_transaction_present"])
        self.assertFalse(preflight["past_update_success_attributed"])
        self.assertEqual(preflight["exact_terminal_history_count"], 1)
        self.assertFalse(preflight["cleanup_authorized"])
        self.assertFalse(preflight["fresh_approval_authorized"])
        self.assertIsNone(
            archive_services._project_update_terminal_cleanup_unknown_gate_read_only(
                self.project,
                operator_resume_identifiers_supplied=False,
            )
        )
        dry_run = archive_services.wom_kit_project_version_update(
            self.project,
            target="v0.4.18",
            dry_run=True,
        )
        self.assertEqual(dry_run, preflight)
        approval = (
            archive_services
            ._wom_kit_project_version_update_live_approval_transaction(
                self.project,
                target="v0.4.18",
                reviewed_by="reviewer",
                affirm_external_writers_quiescent=True,
                approval_executor=lambda *_args, **_kwargs: self.fail(
                    "terminal original entered native approval"
                ),
                _expected_approval_root=self.project,
                _expected_archive_id="archive:test",
            )
        )
        self.assertEqual(approval, preflight)
        serialized = json.dumps(preflight, sort_keys=True)
        self.assertNotIn(transaction.transaction_ref, serialized)
        self.assertNotIn(reference, serialized)
        self.assertNotIn(str(self.project), serialized)
        self.assertEqual(self.tree_snapshot(self.project), pristine)

        # Tampered plan authority is unresolved residue on every surface.
        legacy_plan_path = root / LEGACY_CLEANUP_PLAN_NAME
        original_plan_bytes = legacy_plan_path.read_bytes()
        tampered = json.loads(original_plan_bytes.decode("ascii"))
        tampered["cleanup_authority_sha256"] = digest("foreign-authority")
        legacy_plan_path.write_bytes(transaction_module._document_bytes(tampered))
        try:
            self.assertEqual(
                archive_services
                ._project_update_terminal_cleanup_artifact_classification_read_only(
                    self.project
                ),
                ("unresolved", 0),
            )
            unresolved_preflight = (
                archive_services
                ._project_update_fresh_update_cleanup_preflight_read_only(
                    self.project
                )
            )
            assert unresolved_preflight is not None
            self.assertEqual(
                unresolved_preflight["status"],
                "terminal_cleanup_outcome_unknown",
            )
            gate = archive_services._project_update_terminal_cleanup_unknown_gate_read_only(
                self.project,
                operator_resume_identifiers_supplied=False,
            )
            assert gate is not None
            self.assertEqual(gate["status"], "terminal_cleanup_outcome_unknown")
        finally:
            legacy_plan_path.write_bytes(original_plan_bytes)
        self.assertEqual(self.tree_snapshot(self.project), pristine)

    def test_terminal_original_with_pre_unlock_handoff_keeps_generic_resume_route(
        self,
    ) -> None:
        reference = digest("terminal-original-approval-reference")
        transaction = self.build_terminal_original(approval_reference=reference)
        observation = archive_services._ProjectUpdateTerminalHandoffObservation(
            state="claim_succeeded_pre_unlock",
            raw_sha256=digest("handoff-raw"),
            pending_record_sha256=digest("handoff-pending"),
            transaction_ref=transaction.transaction_ref,
        )

        def handoff_state(_inspection_root, *, _observation_out=None):
            if _observation_out is not None:
                _observation_out.append(observation)
            return "claim_succeeded_pre_unlock"

        class _GenericRouteReached(Exception):
            pass

        with (
            patch.object(
                archive_services,
                "_wom_kit_project_version_update_approval_authority_matches",
                return_value=True,
            ),
            patch.object(
                archive_services,
                "_project_update_terminal_handoff_state_read_only",
                side_effect=handoff_state,
            ),
            patch.object(
                archive_services,
                "_project_update_resume_preapproval_transaction",
                return_value=None,
            ),
            patch.object(
                archive_services,
                "_project_update_reopen_durable_state",
                side_effect=_GenericRouteReached("generic route"),
            ),
            patch.object(
                archive_services,
                "_project_update_resume_terminal_original_cleanup",
                side_effect=AssertionError(
                    "pre-unlock handoff entered terminal-original cleanup"
                ),
            ),
        ):
            with self.assertRaises(_GenericRouteReached):
                archive_services._wom_kit_project_version_update_resume_live_transaction(
                    self.project,
                    target=None,
                    reviewed_by=None,
                    transaction_ref=None,
                    approval_executor=lambda *_args, **_kwargs: self.fail(
                        "executor before reopen"
                    ),
                    _expected_approval_root=self.project,
                    _expected_archive_id="archive:test",
                )

    def test_terminal_original_with_intact_pin_keeps_replay_route_and_falls_back_on_candidate_missing(
        self,
    ) -> None:
        from wom_kit.exact_human_approval_workflow import (
            ExactHumanApprovalWorkflowError,
        )

        reference = digest("terminal-original-approval-reference")
        transaction = self.build_terminal_original(approval_reference=reference)
        ref = transaction.transaction_ref
        pin = next(
            component
            for component in transaction.intent.components
            if component.role == "active_pin"
        )
        pin_path = self.project.joinpath(*PurePosixPath(pin.logical_target).parts)
        pin_path.parent.mkdir(parents=True, exist_ok=True)
        pin_path.write_bytes(self.post_values["active-pin"])
        self.assertFalse(
            archive_services
            ._project_update_terminal_original_postimage_superseded_read_only(
                self.project,
                ref,
            )
        )
        pin_path.write_bytes(b"v9.9.9\n")
        self.assertTrue(
            archive_services
            ._project_update_terminal_original_postimage_superseded_read_only(
                self.project,
                ref,
            )
        )
        pin_path.write_bytes(self.post_values["active-pin"])

        closed: list[str] = []
        state = SimpleNamespace(
            inspection_root=self.project,
            project_root=self.project,
            transaction=transaction,
            expected_lock_bytes=b"",
            expected_approval_root=self.project,
            expected_archive_id="archive:test",
            prepared_preview={"status": "prepared"},
            reviewer="reviewer-a",
            runtime_candidate=object(),
            directory_guard=SimpleNamespace(
                close=lambda: closed.append("directory")
            ),
            terminal_update_verified=False,
        )
        lifetime = SimpleNamespace(
            close_after_service_transaction=lambda: closed.append("runner")
        )
        cleanup_routes: list[tuple[str, str]] = []

        def fake_terminal_cleanup(_inspection_root, **kwargs):
            cleanup_routes.append(
                (kwargs["transaction_ref"], kwargs.get("route", "direct"))
            )
            return {"ok": True, "status": "sentinel_terminal_cleanup"}

        cases = (
            (
                "candidate_missing_gate",
                ExactHumanApprovalWorkflowError(
                    "exact_human_approval_state_unknown",
                    cause_code=(
                        "project_version_update_preapproval_recovery_failed"
                    ),
                    cause_stage="candidate_missing_handler",
                ),
                True,
            ),
            (
                "other_workflow_failure",
                ExactHumanApprovalWorkflowError(
                    "exact_human_approval_state_unknown",
                ),
                False,
            ),
        )
        for case, failure, expect_fallback in cases:
            with self.subTest(case=case):
                cleanup_routes.clear()
                closed.clear()

                def approval_executor(*_args, failure=failure, **_kwargs):
                    raise failure

                with (
                    patch.object(
                        archive_services,
                        "_wom_kit_project_version_update_approval_authority_matches",
                        return_value=True,
                    ),
                    patch.object(
                        archive_services,
                        "_project_update_resume_preapproval_transaction",
                        return_value=None,
                    ),
                    patch.object(
                        archive_services,
                        "_project_update_reopen_durable_state",
                        return_value=(state, lifetime),
                    ),
                    patch.object(
                        archive_services,
                        "_project_update_terminal_execution_lease",
                        return_value=nullcontext(),
                    ),
                    patch.object(
                        archive_services,
                        "_project_update_resume_terminal_original_cleanup",
                        side_effect=fake_terminal_cleanup,
                    ),
                ):
                    if expect_fallback:
                        result = archive_services._wom_kit_project_version_update_resume_live_transaction(
                            self.project,
                            target=None,
                            reviewed_by=None,
                            transaction_ref=None,
                            approval_executor=approval_executor,
                            _expected_approval_root=self.project,
                            _expected_archive_id="archive:test",
                        )
                        self.assertEqual(
                            result["status"],
                            "sentinel_terminal_cleanup",
                        )
                        self.assertEqual(
                            cleanup_routes,
                            [(ref, "fallback_after_generic_resume_refusal")],
                        )
                    else:
                        with self.assertRaises(
                            ExactHumanApprovalWorkflowError
                        ):
                            archive_services._wom_kit_project_version_update_resume_live_transaction(
                                self.project,
                                target=None,
                                reviewed_by=None,
                                transaction_ref=None,
                                approval_executor=approval_executor,
                                _expected_approval_root=self.project,
                                _expected_archive_id="archive:test",
                            )
                        self.assertEqual(cleanup_routes, [])
                self.assertEqual(closed, ["directory", "runner"])

    @unittest.skipIf(
        os.name == "nt",
        "POSIX-only fail-closed mutation boundary",
    )
    def test_terminal_original_resume_refuses_off_windows_with_zero_writes(
        self,
    ) -> None:
        reference = digest("terminal-original-approval-reference")
        self.build_terminal_original(approval_reference=reference)
        approval_root = self.terminal_original_archive_root()
        pristine = self.tree_snapshot(self.project)
        archive_before = self.tree_snapshot(approval_root)

        result = self.run_terminal_original_resume(approval_root=approval_root)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "terminal_cleanup_platform_unsupported")
        self.assertEqual(
            result["reason_code"],
            "project_version_update_terminal_cleanup_platform_unsupported",
        )
        self.assertEqual(result["effects_state"], "none")
        self.assertFalse(result["cleanup_authorized"])
        self.assertFalse(result["approval_key_accessed"])
        self.assertFalse(result["approval_claim_store_accessed"])
        self.assertFalse(result["past_update_success_attributed"])
        self.assertEqual(result["files_written"], [])
        self.assertEqual(self.tree_snapshot(self.project), pristine)
        self.assertEqual(self.tree_snapshot(approval_root), archive_before)

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_original_resume_fails_closed_without_matching_succeeded_claim(
        self,
    ) -> None:
        approval_root = self.terminal_original_archive_root()
        claims_root = approval_root.joinpath(
            *Path(exact_human_approval.CLAIMS_RELATIVE_ROOT).parts
        )
        provider = self._TerminalOriginalKeyProvider(
            self.TERMINAL_ORIGINAL_TEST_KEY
        )
        cases = ("claim_store_absent", "reference_mismatch", "started_claim")
        for index, case in enumerate(cases, start=1):
            with self.subTest(case=case):
                self.project = Path(self.temporary.name) / f"terminal-{index}"
                self.project.mkdir()
                if claims_root.exists():
                    shutil.rmtree(claims_root)
                if case == "reference_mismatch":
                    self.synthetic_claim_reference(
                        approval_root,
                        plan_label="unrelated-plan",
                    )
                    reference = digest("terminal-original-approval-reference")
                elif case == "started_claim":
                    reference = self.synthetic_claim_reference(
                        approval_root,
                        status="started",
                    )
                else:
                    reference = digest("terminal-original-approval-reference")
                transaction = self.build_terminal_original(
                    approval_reference=reference
                )
                namespace = transaction.transaction_root.parent
                namespace_before = self.tree_snapshot(namespace)
                archive_before = self.tree_snapshot(approval_root)

                result = self.run_terminal_original_resume(
                    approval_root=approval_root,
                    key_provider=provider,
                )

                self.assertFalse(result["ok"])
                self.assertEqual(
                    result["status"],
                    "terminal_cleanup_outcome_unknown",
                )
                self.assertEqual(
                    result["outcome_basis"],
                    "terminal_transaction_cleanup_authority_unverified",
                )
                self.assertFalse(result["cleanup_authorized"])
                self.assertTrue(result["approval_key_accessed"])
                self.assertTrue(result["approval_claim_store_accessed"])
                self.assertEqual(self.tree_snapshot(namespace), namespace_before)
                self.assertEqual(self.tree_snapshot(approval_root), archive_before)
                serialized = json.dumps(result, sort_keys=True)
                self.assertNotIn(transaction.transaction_ref, serialized)
                self.assertNotIn(reference, serialized)
                self.assertNotIn(self.TERMINAL_ORIGINAL_APPROVAL_ID, serialized)
        self.assertNotIn(True, provider.create_if_missing)

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_original_resume_cleans_exact_original_after_claim_reauthentication(
        self,
    ) -> None:
        approval_root = self.terminal_original_archive_root()
        reference = self.synthetic_claim_reference(approval_root)
        transaction = self.build_terminal_original(approval_reference=reference)
        root = self.transaction_root(transaction)
        ref = transaction.transaction_ref
        provider = self._TerminalOriginalKeyProvider(
            self.TERMINAL_ORIGINAL_TEST_KEY
        )
        archive_before = self.tree_snapshot(approval_root)
        cleanup_calls: list[str] = []
        original_exact_cleanup = ProjectUpdateTransaction.exact_cleanup

        def observe_cleanup(transaction_object, *, cleanup_authority_sha256):
            self.assertEqual(cleanup_authority_sha256, reference)
            cleanup_calls.append(transaction_object.transaction_ref)
            return original_exact_cleanup(
                transaction_object,
                cleanup_authority_sha256=cleanup_authority_sha256,
            )

        result = self.run_terminal_original_resume(
            approval_root=approval_root,
            key_provider=provider,
            extra_patches=(
                patch.object(
                    ProjectUpdateTransaction,
                    "exact_cleanup",
                    new=observe_cleanup,
                ),
            ),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "terminal_transaction_cleanup_completed")
        self.assertFalse(result["update_completed"])
        self.assertFalse(result["past_update_success_attributed"])
        self.assertTrue(result["fresh_approval_required"])
        self.assertEqual(result["terminal_transactions_cleaned"], 1)
        self.assertEqual(result["cleanup_proofs_written_or_verified"], 1)
        self.assertEqual(result["namespace_cleanup_proof_count"], 1)
        self.assertTrue(result["approval_key_accessed"])
        self.assertTrue(result["approval_claim_store_accessed"])
        self.assertEqual(result["project_domain_effects"], "none")
        self.assertFalse(result["domain_writer_entered"])
        self.assertEqual(result["files_written"], [])
        self.assertEqual(result["files_written_scope"], "project_domain_only")
        self.assertTrue(
            result["effect_summary"][
                "private_control_mutation_performed_or_verified"
            ]
        )
        self.assertFalse(
            result["effect_summary"]["project_domain_writes_performed"]
        )
        self.assertEqual(cleanup_calls, [ref])
        self.assertEqual(provider.calls, 1)
        self.assertEqual(provider.create_if_missing, [False])
        self.assertFalse(root.exists())
        self.assertFalse((root.parent / f".cleanup_{ref}").exists())
        proof = root.parent / f".cleanup-proof_{ref}.json"
        self.assertTrue(proof.is_file())
        proof_document = json.loads(proof.read_text(encoding="ascii"))
        self.assertEqual(proof_document["schema"], CLEANUP_PLAN_SCHEMA)
        self.assertEqual(proof_document["cleanup_authority_sha256"], reference)
        self.assertEqual(self.tree_snapshot(approval_root), archive_before)
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(ref, serialized)
        self.assertNotIn(reference, serialized)
        self.assertNotIn(self.TERMINAL_ORIGINAL_APPROVAL_ID, serialized)
        self.assertNotIn(str(self.project), serialized)

        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_artifact_classification_read_only(
                self.project
            ),
            ("history_only_exact", 1),
        )
        self.assertIsNone(
            archive_services
            ._project_update_fresh_update_cleanup_preflight_read_only(
                self.project
            )
        )
        second = self.run_terminal_original_resume(
            approval_root=approval_root,
            key_provider=provider,
        )
        self.assertEqual(second["status"], "no_resumable_project_update")
        self.assertEqual(provider.calls, 1)

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_original_cleanup_is_reentrant_after_its_own_rename_failure(
        self,
    ) -> None:
        approval_root = self.terminal_original_archive_root()
        reference = self.synthetic_claim_reference(approval_root)
        transaction = self.build_terminal_original(approval_reference=reference)
        root = self.transaction_root(transaction)
        ref = transaction.transaction_ref
        provider = self._TerminalOriginalKeyProvider(
            self.TERMINAL_ORIGINAL_TEST_KEY
        )

        first = self.run_terminal_original_resume(
            approval_root=approval_root,
            key_provider=provider,
            extra_patches=(
                patch.object(
                    transaction_module,
                    "_atomic_move_directory_no_replace",
                    side_effect=OSError("synthetic tombstone rename failure"),
                ),
            ),
        )
        self.assertEqual(first["status"], "terminal_cleanup_outcome_unknown")
        self.assertEqual(
            first["outcome_basis"],
            "terminal_transaction_cleanup_incomplete",
        )
        self.assertTrue(first["approval_key_accessed"])
        self.assertTrue(root.is_dir())
        self.assertTrue((root / CLEANUP_PLAN_NAME).is_file())
        self.assertTrue((root / LEGACY_CLEANUP_PLAN_NAME).is_file())
        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_artifact_classification_read_only(
                self.project
            ),
            ("terminal_original_exact", 1),
        )
        preflight = (
            archive_services
            ._project_update_fresh_update_cleanup_preflight_read_only(
                self.project
            )
        )
        assert preflight is not None
        self.assertEqual(
            preflight["outcome_basis"],
            "exact_terminal_transaction_cleanup_requires_resume",
        )

        second = self.run_terminal_original_resume(
            approval_root=approval_root,
            key_provider=provider,
        )
        self.assertEqual(second["status"], "terminal_transaction_cleanup_completed")
        self.assertFalse(root.exists())
        self.assertTrue((root.parent / f".cleanup-proof_{ref}.json").is_file())
        self.assertEqual(provider.calls, 2)

    @unittest.skipUnless(os.name == "nt", "terminal mutation is Windows-only")
    def test_terminal_original_cleanup_finishes_restored_tombstone_without_claim_rediscovery(
        self,
    ) -> None:
        approval_root = self.terminal_original_archive_root()
        reference = self.synthetic_claim_reference(approval_root)
        transaction = self.build_terminal_original(approval_reference=reference)
        root = self.transaction_root(transaction)
        ref = transaction.transaction_ref
        provider = self._TerminalOriginalKeyProvider(
            self.TERMINAL_ORIGINAL_TEST_KEY
        )

        first = self.run_terminal_original_resume(
            approval_root=approval_root,
            key_provider=provider,
            extra_patches=(
                patch.object(
                    ProjectUpdateTransaction,
                    "_resume_cleanup_paths",
                    return_value=False,
                ),
            ),
        )
        self.assertEqual(first["status"], "terminal_cleanup_outcome_unknown")
        self.assertEqual(
            first["outcome_basis"],
            "terminal_transaction_cleanup_incomplete",
        )
        tombstone = root.parent / f".cleanup_{ref}"
        self.assertFalse(root.exists())
        self.assertTrue(tombstone.is_dir())
        self.assertEqual(
            archive_services
            ._project_update_terminal_cleanup_artifact_classification_read_only(
                self.project
            ),
            ("recoverable_exact", 1),
        )

        second = self.run_terminal_original_resume(
            approval_root=approval_root,
            key_provider=provider,
        )
        self.assertEqual(second["status"], "terminal_transaction_cleanup_completed")
        self.assertFalse(root.exists())
        self.assertFalse(tombstone.exists())
        self.assertTrue((root.parent / f".cleanup-proof_{ref}.json").is_file())
        self.assertEqual(provider.calls, 2)


if __name__ == "__main__":
    unittest.main()
