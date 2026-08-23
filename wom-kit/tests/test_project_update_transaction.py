from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


KIT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = KIT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from wom_kit import project_update_transaction as transaction_module
from wom_kit.project_update_transaction import (
    ABSENT_COMPONENT_SHA256,
    CHECKPOINT_CHAIN_START_SHA256,
    ComponentExpectation,
    DirectoryDurability,
    LockObservation,
    ProjectUpdateBindings,
    ProjectUpdateComponent,
    ProjectUpdateTransaction,
    ProjectUpdateTransactionError,
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

    def seal_reserved(self, reserved, tree) -> ProjectUpdateTransaction:
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
            runtime_candidate_inventory_sha256=tree.recursive_tree_sha256,
            runtime_candidate_postimage_sha256=runtime_post,
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

    def begin(self, transaction: ProjectUpdateTransaction) -> tuple[bytes, dict[str, str]]:
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
            approval_reference_sha256=digest("main-approval-reference"),
            approval_mac_sha256=digest("main-approval-mac"),
        )
        return lock_bytes, live

    def ready_forward(
        self, transaction: ProjectUpdateTransaction
    ) -> tuple[bytes, dict[str, str]]:
        lock_bytes, live = self.begin(transaction)
        for component in transaction.intent.components:
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
                approval_reference=digest("main-approval-reference"),
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
        self, transaction: ProjectUpdateTransaction
    ) -> tuple[bytes, dict[str, str]]:
        lock_bytes, live = self.ready_forward(transaction)
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
            live[component.component_ref] = component.post_sha256
            reopened.append(
                phase=component.role,
                stage="verified",
                component_ref=component.component_ref,
                live_component_sha256=live,
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

    def test_partial_cleanup_hard_exit_is_resumable_from_exact_tombstone(self) -> None:
        transaction = self.create_transaction()
        self.finish_forward(transaction)
        root = self.transaction_root(transaction)
        authority = digest("cleanup-authority")
        original_unlink = Path.unlink
        deleted = {"count": 0}

        def fail_after_one(path: Path, *args, **kwargs):
            if ".cleanup_update_" in str(path):
                deleted["count"] += 1
                if deleted["count"] == 2:
                    raise OSError("simulated hard-exit boundary")
            return original_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", new=fail_after_one):
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
        )
        self.assertEqual(checkpoint.component_ref, "runtime")

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
            live[component.component_ref] = component.post_sha256
            transaction.append(
                phase=component.role,
                stage="verified",
                component_ref=component.component_ref,
                live_component_sha256=live,
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
        self.remove_sealed_candidate(transaction)
        receipt = transaction.candidate_cleanup_receipt_sha256()
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: transaction.cancel_before_approval(
                expected_lock_bytes=lock_bytes,
                live_component_sha256=live,
                candidate_cleanup_plan_sha256=plan,
                candidate_cleanup_receipt_sha256=digest("invented-receipt"),
            ),
        )
        completed = transaction.cancel_before_approval(
            expected_lock_bytes=lock_bytes,
            live_component_sha256=live,
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
            candidate_cleanup_plan_sha256=plan,
            candidate_cleanup_receipt_sha256=receipt,
        )
        self.assertEqual(repeated.checkpoint_sha256, completed.checkpoint_sha256)
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
        self.assertTrue(
            reopened.exact_cleanup(
                cleanup_authority_sha256=digest("cleanup-after-cancel")
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
        self.assert_code(
            "project_update_transaction_candidate_invalid",
            lambda: transaction.cancel_before_approval(
                expected_lock_bytes=lock_bytes,
                live_component_sha256=live,
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
            candidate_cleanup_plan_sha256=plan,
            candidate_cleanup_receipt_sha256=receipt,
        )
        self.assertEqual(completed.phase, "completed")

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
        result = reserved.abort_before_intent_seal(
            expected_lock_bytes=lock_bytes,
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
            candidate_cleanup_evidence_sha256=evidence,
        )
        self.assertEqual(repeated, result)
        root = reserved.transaction_root
        self.assertTrue((root / "reservation-abort-intent.json").is_file())
        self.assertTrue((root / "reservation-abort-receipt.json").is_file())
        self.assertEqual(
            inspect_prelock_orphans(self.project)[0].classification,
            "reserved_aborted_before_intent_seal",
        )
        self.assert_code(
            "project_update_transaction_state_transition_invalid",
            lambda: reopened.acquire_lock(),
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
        self.assert_code(
            "project_update_transaction_candidate_invalid",
            lambda: reserved.abort_before_intent_seal(
                expected_lock_bytes=lock_bytes,
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
                    candidate_cleanup_evidence_sha256=evidence,
                )
        self.assertFalse(
            (self.project / ".zettel-kasten" / "version-update.lock").exists()
        )
        self.assertTrue(
            (reserved.transaction_root / "reservation-abort-intent.json").exists()
        )
        reopened = transaction_module.ReservedProjectUpdateTransaction.open(
            self.project, reserved.transaction_ref
        )
        result = reopened.abort_before_intent_seal(
            expected_lock_bytes=lock_bytes,
            candidate_cleanup_evidence_sha256=evidence,
        )
        self.assertEqual(result["state"], "aborted_before_intent_seal")

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


if __name__ == "__main__":
    unittest.main()
