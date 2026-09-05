from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wom_kit import project_update_legacy_recovery as recovery
from wom_kit import project_update_transaction
from wom_kit import legacy_cleanup_bound_delete


class ProjectUpdateLegacyRecoveryPrimitiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.key = bytes(range(32))

    def project(self, root: Path) -> Path:
        project = root / "project"
        (project / ".zettel-kasten" / "private").mkdir(parents=True)
        return project

    def approval_seed(self, recovery_ref: str) -> dict[str, object]:
        return recovery.fresh_approval_seed_document(
            recovery_ref=recovery_ref,
            reviewer="private human reviewer",
            old_transaction_ref="update_" + "2" * 32,
            old_transaction_sha256="sha256:" + "1" * 64,
            archive_identity_sha256="sha256:" + "6" * 64,
            project_identity_sha256="sha256:" + "7" * 64,
            requested_target_tag="v0.4.19",
        )

    def intent(
        self,
        recovery_ref: str,
        fresh_approval_seed_document_sha256: str,
    ) -> dict[str, object]:
        digest = "sha256:" + "1" * 64
        return recovery.recovery_intent_document(
            recovery_ref=recovery_ref,
            old_transaction_ref="update_" + "2" * 32,
            old_transaction_sha256=digest,
            old_claim_sha256="sha256:" + "3" * 64,
            old_lock_sha256="sha256:" + "4" * 64,
            old_live_components_sha256="sha256:" + "5" * 64,
            archive_identity_sha256="sha256:" + "6" * 64,
            project_identity_sha256="sha256:" + "7" * 64,
            fresh_approval_seed_document_sha256=(
                fresh_approval_seed_document_sha256
            ),
        )

    def initialize(
        self,
        store: recovery.LegacyRecoveryStore,
        recovery_ref: str,
        *,
        failpoint=None,
    ) -> str:
        seed_sha256 = store.write_fresh_approval_seed(
            self.approval_seed(recovery_ref)
        )
        return store.initialize(
            self.intent(recovery_ref, seed_sha256),
            _failpoint=failpoint,
        )

    def cancellation_terminal_handoff(
        self,
        *,
        recovery_ref: str,
        intent_sha256: str,
        terminal_receipt_sha256: str,
        cancellation_result_document_sha256: str,
    ) -> tuple[dict[str, object], str]:
        result_sha256 = recovery._cancellation_delivery_payload_sha256(
            recovery.cancellation_result_document()
        )
        binding = {
            "archive_identity_sha256": "sha256:" + "6" * 64,
            "cancellation_result_document_sha256": (
                cancellation_result_document_sha256
            ),
            "intent_sha256": intent_sha256,
            "outcome": "unapproved_restored",
            "recovery_ref": recovery_ref,
            "result_payload_sha256": result_sha256,
            "terminal_receipt_sha256": terminal_receipt_sha256,
        }
        capability_document = recovery.authenticated_document(
            {
                "schema": (
                    recovery.CANCELLATION_TERMINAL_DELIVERY_CAPABILITY_SCHEMA
                ),
                **binding,
            },
            self.key,
        )
        capability = capability_document["authentication"]["mac"]
        capability_sha256 = recovery.sha256_bytes(
            capability.encode("ascii")
        )
        payload = {
            "schema": recovery.CANCELLATION_TERMINAL_PAYLOAD_SCHEMA,
            **binding,
            "delivery_capability_sha256": capability_sha256,
        }
        return (
            recovery.authenticated_document(
                {
                    "schema": recovery.CANCELLATION_TERMINAL_HANDOFF_SCHEMA,
                    "state": "terminal_ready_unapproved",
                    "payload": payload,
                },
                self.key,
            ),
            capability_sha256,
        )

    def test_fresh_approval_seed_is_private_exact_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "0" * 32
            raw_reviewer = "private human reviewer"
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                seed = self.approval_seed(ref)
                first = store.write_fresh_approval_seed(seed)
                second = store.write_fresh_approval_seed(seed)
                self.assertEqual(first, second)
                self.assertEqual(
                    store.read_fresh_approval_seed()["reviewer"], raw_reviewer
                )
                changed = dict(seed)
                changed["reviewer"] = "different private reviewer"
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_state_changed",
                ):
                    store.write_fresh_approval_seed(changed)

    @unittest.skipUnless(os.name == "nt", "exact locator publication is Windows-only")
    def test_initialized_locator_preserves_seed_privacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "0" * 32
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                intent_sha = self.initialize(store, ref)
                self.assertRegex(intent_sha, r"^sha256:[0-9a-f]{64}$")
                public_control = (
                    (store.paths.recovery_root / "intent.json").read_bytes()
                    + store.paths.locator_path.read_bytes()
                )
                self.assertNotIn(b"private human reviewer", public_control)
                self.assertNotIn("reviewer", store.read_intent()[0])

    def test_seed_and_allocation_reject_missing_extra_and_cross_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "1" * 32
            other_ref = "recovery_" + "2" * 32
            with recovery.LegacyRecoveryStore(
                project,
                other_ref,
                self.key,
            ) as missing_store:
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_path_unsafe",
                ):
                    missing_store.initialize(
                        self.intent(other_ref, "sha256:" + "0" * 64)
                    )
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                seed = self.approval_seed(ref)
                extra = dict(seed)
                extra["unexpected"] = "value"
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_binding_invalid",
                ):
                    store.write_fresh_approval_seed(extra)
                cross = dict(seed)
                cross["recovery_ref"] = other_ref
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_binding_invalid",
                ):
                    store.write_fresh_approval_seed(cross)
                seed_sha = store.write_fresh_approval_seed(seed)
                extra_intent = self.intent(ref, seed_sha)
                extra_intent["unexpected"] = "value"
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_binding_invalid",
                ):
                    store.initialize(extra_intent)
                self.assertFalse(store.paths.locator_path.exists())
                self.assertFalse(
                    (store.paths.recovery_root / "intent.json").exists()
                )
                wrong_intent = self.intent(
                    ref,
                    "sha256:" + "f" * 64,
                )
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_state_changed",
                ):
                    store.initialize(wrong_intent)
                self.assertFalse(store.paths.locator_path.exists())
                self.assertEqual(
                    store.read_fresh_approval_seed()["recovery_ref"], ref
                )
                prepared = (
                    project_update_transaction.ProjectUpdateTransaction.prepare_reservation(
                        project_identity_sha256="sha256:" + "7" * 64,
                        requested_target_tag="v0.4.19",
                        transaction_ref="update_" + "3" * 32,
                        ownership_nonce="4" * 32,
                        created_at="2026-09-05T00:00:00Z",
                    )
                )
                tampered_prepared = prepared.document()
                tampered_prepared["unexpected"] = True
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_binding_invalid",
                ):
                    recovery.fresh_allocation_document(
                        recovery_ref=ref,
                        prepared_reservation_document=tampered_prepared,
                        old_abandonment_sha256="sha256:" + "5" * 64,
                        pre_ref_snapshot_document_sha256="sha256:" + "6" * 64,
                        pre_ref_snapshot_sha256="sha256:" + "7" * 64,
                    )

    def test_authenticated_document_rejects_tamper(self) -> None:
        document = recovery.authenticated_document(
            {"schema": "fixed", "state": "eligible"},
            self.key,
        )
        self.assertEqual(
            recovery.verify_authenticated_document(document, self.key),
            {"schema": "fixed", "state": "eligible"},
        )
        tampered = dict(document)
        tampered["state"] = "changed"
        with self.assertRaisesRegex(
            recovery.LegacyProjectUpdateRecoveryError,
            "project_update_legacy_recovery_authentication_invalid",
        ):
            recovery.verify_authenticated_document(tampered, self.key)

    @unittest.skipUnless(os.name == "nt", "exact locator publication is Windows-only")
    def test_store_is_create_only_hash_chained_and_content_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "8" * 32
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                intent_sha = self.initialize(store, ref)
                first = store.append_checkpoint(
                    phase="legacy_eligibility_verified",
                    stage="verified",
                    intent_sha256=intent_sha,
                    evidence_sha256="sha256:" + "9" * 64,
                    expected_previous_checkpoint_sha256=None,
                )
                second = store.append_checkpoint(
                    phase="old_transaction_staged",
                    stage="verified",
                    intent_sha256=intent_sha,
                    evidence_sha256="sha256:" + "a" * 64,
                    expected_previous_checkpoint_sha256=first,
                )
                locator_before = recovery.sha256_bytes(
                    store.paths.locator_path.read_bytes()
                )
                locator_after = store.publish_locator(
                    state="old_transaction_staged",
                    intent_sha256=intent_sha,
                    journal_head_sha256=second,
                    previous_locator_sha256=locator_before,
                )
                self.assertNotEqual(locator_before, locator_after)
                self.assertEqual(
                    store.read_locator()["state"],
                    "old_transaction_staged",
                )
                lines = [
                    item.read_bytes()
                    for item in sorted(
                        (store.paths.recovery_root / "checkpoints").glob(
                            "*.json"
                        )
                    )
                ]
                self.assertEqual(len(lines), 2)
                first_doc = recovery.verify_authenticated_document(
                    json.loads(lines[0]), self.key
                )
                second_doc = recovery.verify_authenticated_document(
                    json.loads(lines[1]), self.key
                )
                self.assertIsNone(first_doc["previous_checkpoint_sha256"])
                self.assertEqual(
                    second_doc["previous_checkpoint_sha256"], first
                )
                serialized = b"".join(lines) + store.paths.locator_path.read_bytes()
                self.assertNotIn(str(project).encode(), serialized)

    @unittest.skipUnless(os.name == "nt", "exact locator publication is Windows-only")
    def test_locator_compare_and_swap_refuses_stale_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "b" * 32
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                intent_sha = self.initialize(store, ref)
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_state_changed",
                ):
                    store.publish_locator(
                        state="stale",
                        intent_sha256=intent_sha,
                        journal_head_sha256=None,
                        previous_locator_sha256="sha256:" + "c" * 64,
                    )

    @unittest.skipUnless(os.name == "nt", "exact locator publication is Windows-only")
    def test_locator_transition_crash_resumes_without_zero_or_two_active_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "b" * 32
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                intent_sha = self.initialize(store, ref)
                previous = recovery.sha256_bytes(
                    store.paths.locator_path.read_bytes()
                )
                head = store.append_checkpoint(
                    phase="legacy_eligibility_verified",
                    stage="verified",
                    intent_sha256=intent_sha,
                    evidence_sha256="sha256:" + "c" * 64,
                    expected_previous_checkpoint_sha256=None,
                )
                original = recovery._write_new

                def interrupt_active_publish(path, raw, **kwargs):
                    if Path(path) == store.paths.locator_path:
                        raise recovery.LegacyProjectUpdateRecoveryError(
                            "project_update_legacy_recovery_commit_failed"
                        )
                    return original(path, raw, **kwargs)

                with patch.object(
                    recovery,
                    "_write_new",
                    side_effect=interrupt_active_publish,
                ):
                    with self.assertRaisesRegex(
                        recovery.LegacyProjectUpdateRecoveryError,
                        "project_update_legacy_recovery_commit_failed",
                    ):
                        store.publish_locator(
                            state="legacy_eligible",
                            intent_sha256=intent_sha,
                            journal_head_sha256=head,
                            previous_locator_sha256=previous,
                        )
                transition = recovery._locator_transition_path(
                    store.paths.locator_path
                )
                self.assertFalse(store.paths.locator_path.exists())
                self.assertTrue(transition.exists())
                resumed = store.publish_locator(
                    state="legacy_eligible",
                    intent_sha256=intent_sha,
                    journal_head_sha256=head,
                    previous_locator_sha256=previous,
                )
                self.assertEqual(
                    resumed,
                    recovery.sha256_bytes(store.paths.locator_path.read_bytes()),
                )
                self.assertFalse(transition.exists())

    @unittest.skipUnless(os.name == "nt", "retained locator move is Windows-only")
    def test_locator_cas_preserves_raced_public_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "c" * 32
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                intent_sha = self.initialize(store, ref)
                previous = recovery.sha256_bytes(
                    store.paths.locator_path.read_bytes()
                )
                head = store.append_checkpoint(
                    phase="legacy_eligibility_verified",
                    stage="verified",
                    intent_sha256=intent_sha,
                    evidence_sha256="sha256:" + "d" * 64,
                    expected_previous_checkpoint_sha256=None,
                )
                displaced = store.paths.recovery_root / "displaced-locator.json"
                outsider = b"unrelated-concurrent-locator\n"
                original = recovery._move_exact_regular_no_replace
                raced = False

                def replace_then_move(project_root, source, destination, expected):
                    nonlocal raced
                    if Path(source) == store.paths.locator_path and not raced:
                        Path(source).rename(displaced)
                        Path(source).write_bytes(outsider)
                        raced = True
                    return original(project_root, source, destination, expected)

                with patch.object(
                    recovery,
                    "_move_exact_regular_no_replace",
                    side_effect=replace_then_move,
                ):
                    with self.assertRaisesRegex(
                        recovery.LegacyProjectUpdateRecoveryError,
                        "project_update_legacy_recovery_state_changed",
                    ):
                        store.publish_locator(
                            state="legacy_eligible",
                            intent_sha256=intent_sha,
                            journal_head_sha256=head,
                            previous_locator_sha256=previous,
                        )
                self.assertEqual(store.paths.locator_path.read_bytes(), outsider)
                self.assertTrue(displaced.exists())

    @unittest.skipUnless(os.name == "nt", "exact locator publication is Windows-only")
    def test_locator_first_initialize_resumes_every_durable_boundary(self) -> None:
        class Provider:
            def __init__(self, key: bytes) -> None:
                self.key = key

            def use_key(self, _root, consumer, *, create_if_missing=False):
                if create_if_missing:
                    raise AssertionError("must not create")
                return consumer(memoryview(self.key))

        stages = (
            "allocating_locator_durable",
            "recovery_root_durable",
            "intent_durable",
            "intent_locator_durable",
        )
        for index, selected_stage in enumerate(stages):
            with self.subTest(stage=selected_stage), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                project = self.project(base)
                archive = base / "archive"
                archive.mkdir()
                ref = "recovery_" + f"{index + 1:x}" * 32

                def stop(stage: str) -> None:
                    if stage == selected_stage:
                        raise RuntimeError("synthetic-hard-exit")

                with recovery.LegacyRecoveryStore(
                    project, ref, self.key
                ) as store:
                    with self.assertRaisesRegex(
                        recovery.LegacyProjectUpdateRecoveryError,
                        "project_update_legacy_recovery_commit_failed",
                    ):
                        self.initialize(store, ref, failpoint=stop)
                resolved = recovery.resolve_active_recovery(
                    project,
                    archive,
                    Provider(self.key),
                )
                self.assertEqual(resolved.locator["state"], "intent_sealed")
                recoveries = project.joinpath(
                    *recovery.RECOVERY_ROOT_LOGICAL.split("/")
                )
                self.assertEqual(
                    [item.name for item in recoveries.iterdir() if item.is_dir()],
                    [ref],
                )

    def test_directory_move_is_no_replace_and_identity_preserving(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            source = parent / "source"
            source.mkdir()
            identity = os.lstat(source)
            destination = parent / "destination"
            recovery.move_directory_no_replace(source, destination)
            moved = os.lstat(destination)
            self.assertFalse(source.exists())
            self.assertEqual(
                (identity.st_dev, identity.st_ino),
                (moved.st_dev, moved.st_ino),
            )
            source.mkdir()
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_state_changed",
            ):
                recovery.move_directory_no_replace(source, destination)

    def test_old_transaction_staging_is_reversible_and_tamper_evident(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "e" * 32
            paths = recovery.RecoveryPaths.build(project, ref)
            paths.recovery_root.mkdir(parents=True)
            transaction_ref = "update_" + "f" * 32
            transaction = project.joinpath(
                *recovery.TRANSACTION_ROOT_LOGICAL.split("/"),
                transaction_ref,
            )
            transaction.mkdir(parents=True)
            (transaction / "intent.json").write_bytes(b"sealed\n")
            expected = recovery.directory_tree_sha256(transaction)
            self.assertEqual(
                recovery.stage_old_transaction(
                    paths,
                    old_transaction_ref=transaction_ref,
                    expected_tree_sha256=expected,
                ),
                "staged",
            )
            self.assertFalse(transaction.exists())
            self.assertTrue(paths.old_transaction_vault.is_dir())
            self.assertEqual(
                recovery.stage_old_transaction(
                    paths,
                    old_transaction_ref=transaction_ref,
                    expected_tree_sha256=expected,
                ),
                "already_staged",
            )
            self.assertEqual(
                recovery.restore_old_transaction(
                    paths,
                    old_transaction_ref=transaction_ref,
                    expected_tree_sha256=expected,
                ),
                "restored",
            )
            self.assertEqual(transaction.joinpath("intent.json").read_bytes(), b"sealed\n")
            (transaction / "intent.json").write_bytes(b"tampered\n")
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_state_changed",
            ):
                recovery.stage_old_transaction(
                    paths,
                    old_transaction_ref=transaction_ref,
                    expected_tree_sha256=expected,
                )

    def test_active_locator_presence_never_parses_untrusted_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            self.assertEqual(
                recovery.active_locator_presence_read_only(project), "absent"
            )
            locator = project.joinpath(
                *recovery.ACTIVE_LOCATOR_LOGICAL.split("/")
            )
            locator.parent.mkdir(parents=True, exist_ok=True)
            locator.write_bytes(b"not-json and private")
            self.assertEqual(
                recovery.active_locator_presence_read_only(project),
                "present_unverified",
            )

    @unittest.skipUnless(os.name == "nt", "retained cancellation cleanup is Windows-only")
    def test_deny_or_ui_unavailable_restores_old_only_after_claim_absence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            paths = recovery.RecoveryPaths.build(
                project, "recovery_" + "1" * 32
            )
            paths.recovery_root.mkdir(parents=True)
            transaction_parent = project.joinpath(
                *recovery.TRANSACTION_ROOT_LOGICAL.split("/")
            )
            transaction_parent.mkdir(parents=True, exist_ok=True)
            old_ref = "update_" + "2" * 32
            fresh_ref = "update_" + "3" * 32
            old = transaction_parent / old_ref
            old.mkdir()
            (old / "intent.json").write_bytes(b"immutable-old\n")
            old_tree = recovery.directory_tree_sha256(old)
            lock = project.joinpath(*recovery.LOCK_LOGICAL.split("/"))
            old_lock = b"old-lock-exact\n"
            lock.write_bytes(old_lock)
            recovery.stage_old_transaction(
                paths,
                old_transaction_ref=old_ref,
                expected_tree_sha256=old_tree,
            )
            fresh = transaction_parent / fresh_ref
            fresh.mkdir()
            (fresh / "intent.json").write_bytes(b"prospective-fresh\n")
            fresh_inventory = recovery.directory_tree_inventory(fresh)

            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_state_ambiguous",
            ):
                recovery.restore_claimless_preapproval_state(
                    paths,
                    old_transaction_ref=old_ref,
                    old_transaction_tree_sha256=old_tree,
                    fresh_transaction_ref=fresh_ref,
                    fresh_transaction_inventory=fresh_inventory,
                    expected_old_lock_bytes=old_lock,
                    confirm_new_context_claim_absent=lambda: False,
                    cleanup_fresh_candidate=lambda: True,
                )
            self.assertFalse(old.exists())
            self.assertTrue(fresh.exists())
            self.assertEqual(lock.read_bytes(), old_lock)

            restored = recovery.restore_claimless_preapproval_state(
                paths,
                old_transaction_ref=old_ref,
                old_transaction_tree_sha256=old_tree,
                fresh_transaction_ref=fresh_ref,
                fresh_transaction_inventory=fresh_inventory,
                expected_old_lock_bytes=old_lock,
                confirm_new_context_claim_absent=lambda: True,
                cleanup_fresh_candidate=lambda: True,
            )
            self.assertEqual(restored["new_context_claim"], "absent_authenticated")
            self.assertEqual((old / "intent.json").read_bytes(), b"immutable-old\n")
            self.assertFalse(fresh.exists())
            self.assertFalse(paths.cancelled_fresh_transaction_vault.exists())
            self.assertEqual(restored["fresh_scaffold"], "deleted_exact")
            self.assertEqual(lock.read_bytes(), old_lock)

    def test_key_never_appears_in_error_or_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "d" * 32
            store = recovery.LegacyRecoveryStore(project, ref, self.key)
            try:
                with patch.object(os, "open", side_effect=PermissionError("private path")):
                    with self.assertRaises(
                        recovery.LegacyProjectUpdateRecoveryError
                    ) as caught:
                        self.initialize(store, ref)
                self.assertRegex(str(caught.exception), r"^[a-z][a-z0-9_]+$")
                self.assertNotIn("private path", str(caught.exception))
                self.assertNotIn(self.key.hex(), str(caught.exception))
            finally:
                store.close()

    def test_directory_barrier_is_hard_fail_not_best_effort(self) -> None:
        with patch.object(
            project_update_transaction,
            "_require_directory_durable",
            side_effect=project_update_transaction.ProjectUpdateTransactionError(
                "project_update_transaction_directory_fsync_failed"
            ),
        ):
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_commit_failed",
            ):
                recovery._fsync_directory(Path("unused-private-parent"))

    def test_write_new_never_leaves_partial_final_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            target = project / ".zettel-kasten" / "private" / "final.json"
            original_write = os.write
            calls = 0

            def short_then_fail(descriptor: int, raw: bytes) -> int:
                nonlocal calls
                calls += 1
                if calls == 1:
                    return original_write(descriptor, raw[:1])
                raise OSError("private-path-must-not-leak")

            with patch.object(os, "write", side_effect=short_then_fail):
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_commit_failed",
                ) as caught:
                    recovery._write_new(target, b"abcdef")
            self.assertFalse(target.exists())
            self.assertNotIn("private-path", str(caught.exception))

    def test_directory_inventory_progresses_for_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            tree = project / ".zettel-kasten" / "private" / "tree"
            (tree / "a" / "b").mkdir(parents=True)
            (tree / "c").mkdir()
            (tree / "a" / "b" / "value").write_bytes(b"value")
            progress: list[tuple[int, int]] = []
            inventory = recovery.directory_tree_inventory(
                tree,
                progress_callback=lambda count, size: progress.append(
                    (count, size)
                ),
            )
            self.assertEqual(len(progress), inventory["entry_count"])
            self.assertEqual(
                [item[0] for item in progress],
                list(range(1, inventory["entry_count"] + 1)),
            )
            self.assertTrue(
                recovery.directory_tree_matches_inventory(tree, inventory)
            )

    @unittest.skipUnless(os.name == "nt", "retained exact deletion is Windows-only")
    def test_exact_delete_removes_only_the_observed_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = self.project(Path(tmp)) / "tree"
            (tree / "nested").mkdir(parents=True)
            (tree / "nested" / "value").write_bytes(b"value")
            inventory = recovery.directory_tree_inventory(tree)
            self.assertEqual(recovery.delete_exact_inventory_tree(tree, inventory), "deleted_exact")
            self.assertFalse(tree.exists())

    def test_posix_exact_mutation_is_explicitly_unsupported_without_effects(self) -> None:
        # This selects the portable branch on Windows too, but does not mock
        # file reads, inventory, hashes, identities, or filesystem mutations.
        posix = SimpleNamespace(**(vars(os) | {"name": "posix"}))
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            tree = project / "tree"
            (tree / "nested").mkdir(parents=True)
            source = tree / "nested" / "value"
            source.write_bytes(b"approved bytes")
            destination = tree / "destination"
            inventory = recovery.directory_tree_inventory(tree)
            before = recovery.sha256_document(inventory)
            with patch.object(recovery, "os", posix):
                for action in (
                    lambda: recovery._move_exact_regular_no_replace(project, source, destination, b"approved bytes"),
                    lambda: recovery.delete_exact_inventory_tree(tree, inventory),
                ):
                    with self.assertRaisesRegex(recovery.LegacyProjectUpdateRecoveryError, "^project_update_legacy_recovery_platform_unsupported$"):
                        action()
                self.assertEqual(recovery.delete_exact_inventory_tree(project / "absent", inventory), "already_absent")
                with self.assertRaisesRegex(recovery.LegacyProjectUpdateRecoveryError, "binding_invalid"):
                    recovery.delete_exact_inventory_tree(tree, {})
                with self.assertRaisesRegex(recovery.LegacyProjectUpdateRecoveryError, "path_unsafe"):
                    recovery._move_exact_regular_no_replace(project, source, destination, "not bytes")
            self.assertFalse(destination.exists())
            self.assertEqual(source.read_bytes(), b"approved bytes")
            self.assertEqual(recovery.sha256_document(recovery.directory_tree_inventory(tree)), before)

    def test_process_guard_requires_terminal_first_and_serializes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            (project / ".zettel-kasten" / "private" / "version-update-terminal").mkdir(
                parents=True,
                exist_ok=True,
            )
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_state_ambiguous",
            ):
                with recovery.legacy_recovery_process_guard(
                    project,
                    terminal_control_lease_held=lambda: False,
                ):
                    pass
            with recovery.legacy_recovery_process_guard(
                project,
                terminal_control_lease_held=lambda: True,
            ):
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_guard_unavailable",
                ):
                    with recovery.legacy_recovery_process_guard(
                        project,
                        terminal_control_lease_held=lambda: True,
                    ):
                        pass
            with recovery.legacy_recovery_process_guard(
                project,
                terminal_control_lease_held=lambda: True,
            ):
                pass

    def test_terminal_receipts_have_disjoint_evidence(self) -> None:
        common = {
            "fresh_transaction_ref": "update_" + "1" * 32,
            "intent_sha256": "sha256:" + "2" * 64,
            "journal_head_sha256": "sha256:" + "3" * 64,
            "old_transaction_inventory_sha256": "sha256:" + "4" * 64,
            "recovery_ref": "recovery_" + "5" * 32,
        }
        success = recovery.terminal_receipt_document(
            **common,
            outcome="success",
            fresh_transaction_completed_sha256="sha256:" + "6" * 64,
            claim_evidence_sha256="sha256:" + "7" * 64,
            old_lock_backup_sha256="sha256:" + "8" * 64,
        )
        self.assertIn("claim_evidence_sha256", success)
        self.assertNotIn("claim_absence_evidence_sha256", success)
        restored = recovery.terminal_receipt_document(
            **common,
            outcome="unapproved_restored",
            claim_absence_evidence_sha256="sha256:" + "9" * 64,
            cancelled_fresh_staging_sha256="sha256:" + "a" * 64,
            cancelled_fresh_transaction_inventory_sha256=(
                "sha256:" + "b" * 64
            ),
            cancelled_fresh_transaction_inventory_document_sha256=(
                "sha256:" + "f" * 64
            ),
            cancelled_fresh_cleanup_evidence_sha256="sha256:" + "c" * 64,
            restored_old_transaction_sha256="sha256:" + "d" * 64,
            preserved_old_lock_sha256="sha256:" + "e" * 64,
            cancellation_plan_document_sha256="sha256:" + "1" * 64,
            cancellation_result_document_sha256="sha256:" + "2" * 64,
            cancellation_result_sha256="sha256:" + "3" * 64,
            cancelled_fresh_staging_document_sha256=(
                "sha256:" + "4" * 64
            ),
            cancelled_fresh_cleanup_evidence_document_sha256=(
                "sha256:" + "5" * 64
            ),
            restored_evidence_sha256="sha256:" + "6" * 64,
            restored_evidence_document_sha256="sha256:" + "7" * 64,
        )
        self.assertIn("claim_absence_evidence_sha256", restored)
        self.assertNotIn("claim_evidence_sha256", restored)

    def test_public_failure_code_export_is_the_exception_allowlist(self) -> None:
        self.assertEqual(
            recovery.PUBLIC_FAILURE_CODES,
            recovery.LegacyProjectUpdateRecoveryError._CODES,
        )
        for code in recovery.PUBLIC_FAILURE_CODES:
            self.assertEqual(str(recovery.LegacyProjectUpdateRecoveryError(code)), code)

    @unittest.skipUnless(os.name == "nt", "retained cleanup is Windows-only")
    def test_sharded_fresh_inventory_survives_partial_delete_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "6" * 32
            fresh_ref = "update_" + "7" * 32
            paths = recovery.RecoveryPaths.build(project, ref)
            fresh = project.joinpath(
                *recovery.TRANSACTION_ROOT_LOGICAL.split("/"),
                fresh_ref,
            )
            fresh.mkdir(parents=True)
            for name in ("a", "b", "c"):
                (fresh / name).write_bytes(name.encode("ascii"))
            inventory = recovery.directory_tree_inventory(fresh)
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                self.initialize(store, ref)
                pre_snapshot = store.write_pre_fetch_ref_snapshot(
                    {"head": "sha256:" + "0" * 64}
                )
                prepared = (
                    project_update_transaction.ProjectUpdateTransaction.prepare_reservation(
                        project_identity_sha256="sha256:" + "7" * 64,
                        requested_target_tag="v0.4.19",
                        transaction_ref=fresh_ref,
                        ownership_nonce="9" * 32,
                        created_at="2026-09-05T00:00:00Z",
                    )
                )
                allocation = recovery.fresh_allocation_document(
                    recovery_ref=ref,
                    prepared_reservation_document=prepared.document(),
                    old_abandonment_sha256="sha256:" + "8" * 64,
                    pre_ref_snapshot_document_sha256=pre_snapshot[
                        "pre_ref_snapshot_document_sha256"
                    ],
                    pre_ref_snapshot_sha256=pre_snapshot[
                        "pre_ref_snapshot_sha256"
                    ],
                )
                allocation_sha = store.write_fresh_allocation(allocation)
                self.assertRegex(allocation_sha, r"^sha256:[0-9a-f]{64}$")
                self.assertEqual(store.read_fresh_allocation(), allocation)
                with patch.object(
                    recovery, "_MAX_INVENTORY_CHUNK_RECORDS", 2
                ):
                    sealed = store.write_fresh_transaction_inventory(
                        fresh_transaction_ref=fresh_ref,
                        inventory=inventory,
                    )
                    reopened = store.read_fresh_transaction_inventory()
                self.assertEqual(
                    reopened["fresh_transaction_inventory"], inventory
                )
                self.assertEqual(
                    reopened["fresh_transaction_inventory_document_sha256"],
                    sealed["fresh_transaction_inventory_document_sha256"],
                )
                self.assertEqual(
                    len(
                        list(
                            (
                                paths.recovery_root
                                / "fresh-transaction-inventory"
                                / "chunks"
                            ).glob("*.json")
                        )
                    ),
                    2,
                )
                post_snapshot = store.write_post_fetch_ref_snapshot(
                    {"head": "sha256:" + "f" * 64},
                    pre_ref_snapshot_document_sha256=pre_snapshot[
                        "pre_ref_snapshot_document_sha256"
                    ],
                    pre_ref_snapshot_sha256=pre_snapshot[
                        "pre_ref_snapshot_sha256"
                    ],
                    requested_target_tag="v0.4.19",
                )
                plan = recovery.prospective_plan_document(
                    recovery_ref=ref,
                    fresh_allocation_document_sha256=allocation_sha,
                    fresh_transaction_ref=fresh_ref,
                    fresh_intent_sha256="sha256:" + "1" * 64,
                    fresh_transaction_inventory_sha256=sealed[
                        "fresh_transaction_inventory_sha256"
                    ],
                    fresh_transaction_inventory_document_sha256=sealed[
                        "fresh_transaction_inventory_document_sha256"
                    ],
                    fresh_approval_plan_sha256="sha256:" + "2" * 64,
                    fresh_approval_target_binding_sha256=(
                        "sha256:" + "3" * 64
                    ),
                    fresh_approval_context_sha256="sha256:" + "4" * 64,
                    fresh_recovery_binding_sha256="sha256:" + "5" * 64,
                    post_ref_snapshot_document_sha256=post_snapshot[
                        "post_ref_snapshot_document_sha256"
                    ],
                    post_ref_snapshot_sha256=post_snapshot[
                        "post_ref_snapshot_sha256"
                    ],
                    old_abandonment_sha256="sha256:" + "6" * 64,
                )
                self.assertEqual(
                    plan["fresh_transaction_inventory_document_sha256"],
                    sealed["fresh_transaction_inventory_document_sha256"],
                )
                recovery.stage_cancelled_fresh_transaction(
                    paths,
                    fresh_transaction_ref=fresh_ref,
                    fresh_transaction_inventory=inventory,
                )
                original_fsync = recovery._fsync_directory
                interrupted = False

                def interrupt_after_first_delete(path: Path) -> None:
                    nonlocal interrupted
                    if not interrupted:
                        interrupted = True
                        raise recovery.LegacyProjectUpdateRecoveryError(
                            "project_update_legacy_recovery_commit_failed"
                        )
                    original_fsync(path)

                with patch.object(
                    recovery,
                    "_fsync_directory",
                    side_effect=interrupt_after_first_delete,
                ):
                    with self.assertRaisesRegex(
                        recovery.LegacyProjectUpdateRecoveryError,
                        "project_update_legacy_recovery_commit_failed",
                    ):
                        recovery.delete_cancelled_fresh_transaction(
                            paths,
                            fresh_transaction_inventory=inventory,
                        )
                durable = store.read_fresh_transaction_inventory()
                self.assertEqual(
                    recovery.delete_cancelled_fresh_transaction(
                        paths,
                        fresh_transaction_inventory=durable[
                            "fresh_transaction_inventory"
                        ],
                    ),
                    "deleted_exact",
                )

    @unittest.skipUnless(os.name == "nt", "exact locator publication is Windows-only")
    def test_fresh_inventory_prepared_prefix_resumes_at_every_publish_boundary(
        self,
    ) -> None:
        class Provider:
            def __init__(self, key: bytes) -> None:
                self.key = key

            def use_key(self, _root, consumer, *, create_if_missing=False):
                if create_if_missing:
                    raise AssertionError("must not create")
                return consumer(memoryview(self.key))

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = self.project(base)
            archive = base / "archive"
            archive.mkdir()
            ref = "recovery_" + "6" * 32
            fresh_ref = "update_" + "7" * 32
            abandonment = "sha256:" + "8" * 64
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                intent_sha = self.initialize(store, ref)
                locator_sha = recovery.sha256_bytes(
                    store.paths.locator_path.read_bytes()
                )
                head = None

                def advance(phase: str, evidence: str) -> None:
                    nonlocal head, locator_sha
                    head = store.append_checkpoint(
                        phase=phase,
                        stage="verified",
                        intent_sha256=intent_sha,
                        evidence_sha256=evidence,
                        expected_previous_checkpoint_sha256=head,
                    )
                    locator_sha = store.publish_locator(
                        state=recovery._CHECKPOINT_LOCATOR_STATE[phase],
                        intent_sha256=intent_sha,
                        journal_head_sha256=head,
                        previous_locator_sha256=locator_sha,
                    )

                advance("legacy_eligibility_verified", abandonment)
                advance("old_transaction_staged", "sha256:" + "9" * 64)
                pre = store.write_pre_fetch_ref_snapshot(
                    {"state": "pre", "target": "v0.4.19"}
                )
                prepared = (
                    project_update_transaction.ProjectUpdateTransaction.prepare_reservation(
                        project_identity_sha256="sha256:" + "7" * 64,
                        requested_target_tag="v0.4.19",
                        transaction_ref=fresh_ref,
                        ownership_nonce="a" * 32,
                        created_at="2026-09-05T00:00:00Z",
                    )
                )
                allocation = recovery.fresh_allocation_document(
                    recovery_ref=ref,
                    prepared_reservation_document=prepared.document(),
                    old_abandonment_sha256=abandonment,
                    pre_ref_snapshot_document_sha256=pre[
                        "pre_ref_snapshot_document_sha256"
                    ],
                    pre_ref_snapshot_sha256=pre[
                        "pre_ref_snapshot_sha256"
                    ],
                )
                allocation_sha = store.write_fresh_allocation(allocation)
                advance("fresh_transaction_allocated", allocation_sha)
                reservation = recovery.fresh_reservation_document(
                    recovery_ref=ref,
                    fresh_transaction_ref=fresh_ref,
                    fresh_reservation_sha256=prepared.sha256,
                    fresh_allocation_document_sha256=allocation_sha,
                    old_abandonment_sha256=abandonment,
                )
                reservation_sha = store.write_fresh_reservation(reservation)
                advance("fresh_reservation_bound", reservation_sha)

            inventory = {
                "entry_count": 3,
                "records": [
                    {
                        "content_sha256": "sha256:" + f"{index + 1:x}" * 64,
                        "device": 1,
                        "inode": index + 10,
                        "kind": "file",
                        "logical": f"item-{index}.bin",
                        "modified_ns": 0,
                        "size": 0,
                    }
                    for index in range(3)
                ],
                "root_identity": [1, 2],
                "schema": "wom-kit/project-update-legacy-tree/v0.4.19",
                "total_bytes": 0,
            }
            paths = recovery.RecoveryPaths.build(project, ref)
            prepared_root = (
                paths.recovery_root / "fresh-transaction-inventory.prepared"
            )
            final_root = paths.recovery_root / "fresh-transaction-inventory"

            def resolve():
                return recovery.resolve_active_recovery(
                    project,
                    archive,
                    Provider(self.key),
                )

            boundaries = (
                "prepared_root_durable",
                "chunk_durable",
                "index_durable",
                "inventory_published",
            )
            with patch.object(recovery, "_MAX_INVENTORY_CHUNK_RECORDS", 1):
                for boundary in boundaries:
                    def stop(stage: str, *, selected=boundary) -> None:
                        if stage == selected:
                            raise RuntimeError("simulated_hard_exit")

                    with recovery.LegacyRecoveryStore(
                        project,
                        ref,
                        self.key,
                    ) as store:
                        with self.assertRaisesRegex(
                            RuntimeError,
                            "simulated_hard_exit",
                        ):
                            store.write_fresh_transaction_inventory(
                                fresh_transaction_ref=fresh_ref,
                                inventory=inventory,
                                _failpoint=stop,
                            )
                    reopened = resolve()
                    if boundary == "inventory_published":
                        self.assertFalse(prepared_root.exists())
                        self.assertTrue(final_root.exists())
                        self.assertEqual(
                            reopened.fresh_transaction_inventory,
                            inventory,
                        )
                    else:
                        self.assertTrue(prepared_root.exists())
                        self.assertFalse(final_root.exists())
                        self.assertIsNone(
                            reopened.fresh_transaction_inventory
                        )

                with recovery.LegacyRecoveryStore(
                    project,
                    ref,
                    self.key,
                ) as store:
                    sealed = store.write_fresh_transaction_inventory(
                        fresh_transaction_ref=fresh_ref,
                        inventory=inventory,
                    )
            self.assertEqual(
                sealed["fresh_transaction_inventory_sha256"],
                recovery.sha256_document(inventory),
            )

    @unittest.skipUnless(os.name == "nt", "exact locator publication is Windows-only")
    def test_checkpoint_chain_rejects_authenticated_invalid_grammar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "a" * 32
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                intent_sha = self.initialize(store, ref)
                head = None
                phases = (
                    "legacy_eligibility_verified",
                    "old_transaction_staged",
                    "fresh_transaction_allocated",
                    "fresh_reservation_bound",
                    "fresh_plan_sealed",
                )
                for index, phase in enumerate(phases, start=1):
                    head = store.append_checkpoint(
                        phase=phase,
                        stage="verified",
                        intent_sha256=intent_sha,
                        evidence_sha256="sha256:" + f"{index:x}" * 64,
                        expected_previous_checkpoint_sha256=head,
                    )
                invalid = {
                    "evidence_sha256": "sha256:" + "f" * 64,
                    "intent_sha256": intent_sha,
                    "phase": "fresh_reservation_bound",
                    "previous_checkpoint_sha256": head,
                    "recovery_ref": ref,
                    "schema": recovery.RECOVERY_CHECKPOINT_SCHEMA,
                    "sequence": 6,
                    "stage": "verified",
                }
                store._write_authenticated_create_only(
                    paths := store.paths.recovery_root
                    / "checkpoints"
                    / "00000006.json",
                    invalid,
                )
                self.assertTrue(paths.exists())
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_state_changed",
                ):
                    store.read_checkpoints(intent_sha256=intent_sha)

    def test_checkpoint_grammar_accepts_only_complete_branch_prefixes(self) -> None:
        common = [
            "legacy_eligibility_verified",
            "old_transaction_staged",
            "fresh_transaction_allocated",
            "fresh_reservation_bound",
            "fresh_plan_sealed",
        ]
        success = common + [
            "fresh_lock_backlinked",
            "fresh_transaction_completed",
        ]
        denied = common + [
            "cancelled_fresh_staged",
            "cancelled_fresh_cleaned",
            "unapproved_restored",
        ]

        def checkpoints(phases):
            return tuple(
                {"phase": phase, "stage": "verified"} for phase in phases
            )

        for phases in (success, denied):
            for length in range(len(phases) + 1):
                expected = (
                    "intent_sealed"
                    if length == 0
                    else recovery._CHECKPOINT_LOCATOR_STATE[
                        phases[length - 1]
                    ]
                )
                self.assertEqual(
                    recovery._checkpoint_chain_state(
                        checkpoints(phases[:length])
                    ),
                    expected,
                )
        invalid = (
            common + ["fresh_transaction_completed"],
            common
            + ["cancelled_fresh_staged", "fresh_lock_backlinked"],
            common + ["fresh_reservation_bound"],
        )
        for phases in invalid:
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_state_changed",
            ):
                recovery._checkpoint_chain_state(checkpoints(phases))

    @unittest.skipUnless(os.name == "nt", "exact locator publication is Windows-only")
    def test_cancellation_documents_reopen_each_durable_prefix_and_rebuild_receipt(
        self,
    ) -> None:
        class Provider:
            def __init__(self, key: bytes) -> None:
                self.key = key

            def use_key(self, _root, consumer, *, create_if_missing=False):
                if create_if_missing:
                    raise AssertionError("must not create")
                return consumer(memoryview(self.key))

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = self.project(base)
            archive = base / "archive"
            archive.mkdir()
            ref = "recovery_" + "a" * 32
            fresh_ref = "update_" + "b" * 32
            old_abandonment = "sha256:" + "c" * 64
            old_transaction_sha = "sha256:" + "1" * 64
            old_lock_sha = "sha256:" + "4" * 64
            approval_plan_sha = "sha256:" + "d" * 64
            approval_context_sha = "sha256:" + "e" * 64

            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                intent_sha = self.initialize(store, ref)
                locator_sha = recovery.sha256_bytes(
                    store.paths.locator_path.read_bytes()
                )
                head = None

                def advance(phase: str, evidence: str) -> None:
                    nonlocal head, locator_sha
                    head = store.append_checkpoint(
                        phase=phase,
                        stage="verified",
                        intent_sha256=intent_sha,
                        evidence_sha256=evidence,
                        expected_previous_checkpoint_sha256=head,
                    )
                    locator_sha = store.publish_locator(
                        state=recovery._CHECKPOINT_LOCATOR_STATE[phase],
                        intent_sha256=intent_sha,
                        journal_head_sha256=head,
                        previous_locator_sha256=locator_sha,
                    )

                advance("legacy_eligibility_verified", old_abandonment)
                advance(
                    "old_transaction_staged",
                    recovery.sha256_document(
                        {
                            "old_transaction_sha256": old_transaction_sha,
                            "schema": (
                                "wom-kit/project-update-legacy-stage-evidence/"
                                "v0.4.19"
                            ),
                            "state": "staged",
                        }
                    ),
                )
                pre = store.write_pre_fetch_ref_snapshot(
                    {"state": "pre", "target": "v0.4.19"}
                )
                prepared = (
                    project_update_transaction.ProjectUpdateTransaction.prepare_reservation(
                        project_identity_sha256="sha256:" + "7" * 64,
                        requested_target_tag="v0.4.19",
                        transaction_ref=fresh_ref,
                        ownership_nonce="3" * 32,
                        created_at="2026-09-05T00:00:00Z",
                    )
                )
                allocation = recovery.fresh_allocation_document(
                    recovery_ref=ref,
                    prepared_reservation_document=prepared.document(),
                    old_abandonment_sha256=old_abandonment,
                    pre_ref_snapshot_document_sha256=pre[
                        "pre_ref_snapshot_document_sha256"
                    ],
                    pre_ref_snapshot_sha256=pre[
                        "pre_ref_snapshot_sha256"
                    ],
                )
                allocation_doc_sha = store.write_fresh_allocation(allocation)
                advance("fresh_transaction_allocated", allocation_doc_sha)
                reservation = recovery.fresh_reservation_document(
                    recovery_ref=ref,
                    fresh_transaction_ref=fresh_ref,
                    fresh_reservation_sha256=prepared.sha256,
                    fresh_allocation_document_sha256=allocation_doc_sha,
                    old_abandonment_sha256=old_abandonment,
                )
                reservation_doc_sha = store.write_fresh_reservation(
                    reservation
                )
                advance("fresh_reservation_bound", reservation_doc_sha)
                inventory = {
                    "entry_count": 0,
                    "records": [],
                    "root_identity": [1, 2],
                    "schema": "wom-kit/project-update-legacy-tree/v0.4.19",
                    "total_bytes": 0,
                }
                sealed_inventory = store.write_fresh_transaction_inventory(
                    fresh_transaction_ref=fresh_ref,
                    inventory=inventory,
                )
                post = store.write_post_fetch_ref_snapshot(
                    {"state": "post", "target": "v0.4.19"},
                    pre_ref_snapshot_document_sha256=pre[
                        "pre_ref_snapshot_document_sha256"
                    ],
                    pre_ref_snapshot_sha256=pre[
                        "pre_ref_snapshot_sha256"
                    ],
                    requested_target_tag="v0.4.19",
                )
                prospective = recovery.prospective_plan_document(
                    recovery_ref=ref,
                    fresh_allocation_document_sha256=allocation_doc_sha,
                    fresh_transaction_ref=fresh_ref,
                    fresh_intent_sha256="sha256:" + "5" * 64,
                    fresh_transaction_inventory_sha256=sealed_inventory[
                        "fresh_transaction_inventory_sha256"
                    ],
                    fresh_transaction_inventory_document_sha256=(
                        sealed_inventory[
                            "fresh_transaction_inventory_document_sha256"
                        ]
                    ),
                    fresh_approval_plan_sha256=approval_plan_sha,
                    fresh_approval_target_binding_sha256=(
                        "sha256:" + "6" * 64
                    ),
                    fresh_approval_context_sha256=approval_context_sha,
                    fresh_recovery_binding_sha256="sha256:" + "7" * 64,
                    post_ref_snapshot_document_sha256=post[
                        "post_ref_snapshot_document_sha256"
                    ],
                    post_ref_snapshot_sha256=post[
                        "post_ref_snapshot_sha256"
                    ],
                    old_abandonment_sha256=old_abandonment,
                )
                invalid_prospective = dict(prospective)
                invalid_prospective["unexpected"] = True
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_binding_invalid",
                ):
                    store.write_prospective_plan(invalid_prospective)
                self.assertFalse(
                    (store.paths.recovery_root / "prospective-plan.json").exists()
                )
                prospective_doc_sha = store.write_prospective_plan(prospective)
                advance("fresh_plan_sealed", prospective_doc_sha)

            def resolve():
                return recovery.resolve_active_recovery(
                    project,
                    archive,
                    Provider(self.key),
                )

            # Result create-only document may durably lead the cancellation
            # plan by exactly one write.
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                result_record = store.write_cancellation_result(
                    recovery.cancellation_result_document()
                )
            resolved = resolve()
            self.assertIsNotNone(resolved.cancellation_result)
            self.assertIsNone(resolved.cancellation_plan)
            self.assertEqual(
                resolved.cancellation_result["files_written_scope"],
                "project_domain_only",
            )
            self.assertFalse(
                resolved.cancellation_result["project_domain_writes_performed"]
            )

            claim_absence_sha = "sha256:" + "8" * 64
            cancellation_plan = recovery.cancellation_plan_document(
                recovery_ref=ref,
                intent_sha256=intent_sha,
                fresh_transaction_ref=fresh_ref,
                prospective_plan_document_sha256=prospective_doc_sha,
                fresh_approval_plan_sha256=approval_plan_sha,
                fresh_approval_context_sha256=approval_context_sha,
                claim_absence_evidence_sha256=claim_absence_sha,
                old_transaction_ref="update_" + "2" * 32,
                old_transaction_sha256=old_transaction_sha,
                old_lock_sha256=old_lock_sha,
                old_abandonment_sha256=old_abandonment,
                fresh_transaction_inventory_sha256=sealed_inventory[
                    "fresh_transaction_inventory_sha256"
                ],
                fresh_transaction_inventory_document_sha256=(
                    sealed_inventory[
                        "fresh_transaction_inventory_document_sha256"
                    ]
                ),
                cancellation_result_sha256=result_record[
                    "cancellation_result_sha256"
                ],
                cancellation_result_document_sha256=result_record[
                    "cancellation_result_document_sha256"
                ],
            )
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                cancellation_plan_doc_sha = store.write_cancellation_plan(
                    cancellation_plan
                )
            resolved = resolve()
            self.assertEqual(
                resolved.cancellation_plan_document_sha256,
                cancellation_plan_doc_sha,
            )

            stage_document = recovery.cancellation_stage_evidence_document(
                recovery_ref=ref,
                intent_sha256=intent_sha,
                fresh_transaction_ref=fresh_ref,
                cancellation_plan_document_sha256=cancellation_plan_doc_sha,
                claim_absence_evidence_sha256=claim_absence_sha,
                fresh_transaction_inventory_sha256=sealed_inventory[
                    "fresh_transaction_inventory_sha256"
                ],
                fresh_transaction_inventory_document_sha256=(
                    sealed_inventory[
                        "fresh_transaction_inventory_document_sha256"
                    ]
                ),
                stage_state="staged",
            )
            cross_digest_stage = dict(stage_document)
            cross_digest_stage["cancellation_plan_document_sha256"] = (
                "sha256:" + "f" * 64
            )
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                store.write_cancellation_stage_evidence(cross_digest_stage)
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_state_changed",
            ):
                resolve()
            stage_path = (
                recovery.RecoveryPaths.build(project, ref).recovery_root
                / "cancellation-stage-evidence.json"
            )
            stage_path.unlink()
            recovery._fsync_directory(stage_path.parent)
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                stage_doc_sha = store.write_cancellation_stage_evidence(
                    stage_document
                )
            self.assertEqual(
                resolve().cancellation_stage_evidence_document_sha256,
                stage_doc_sha,
            )
            future_cleanup = recovery.cancellation_cleanup_evidence_document(
                recovery_ref=ref,
                intent_sha256=intent_sha,
                fresh_transaction_ref=fresh_ref,
                cancellation_plan_document_sha256=cancellation_plan_doc_sha,
                cancellation_stage_evidence_document_sha256=stage_doc_sha,
                fresh_transaction_inventory_sha256=sealed_inventory[
                    "fresh_transaction_inventory_sha256"
                ],
                fresh_transaction_inventory_document_sha256=(
                    sealed_inventory[
                        "fresh_transaction_inventory_document_sha256"
                    ]
                ),
                cleanup_state="deleted_exact",
            )
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                store.write_cancellation_cleanup_evidence(future_cleanup)
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_state_changed",
            ):
                resolve()
            cleanup_path = (
                recovery.RecoveryPaths.build(project, ref).recovery_root
                / "cancellation-cleanup-evidence.json"
            )
            cleanup_path.unlink()
            recovery._fsync_directory(cleanup_path.parent)
            # Checkpoint durable before locator publication is the other
            # permitted one-step lag; resolver repairs only that exact tail.
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                stage_head = store.append_checkpoint(
                    phase="cancelled_fresh_staged",
                    stage="verified",
                    intent_sha256=intent_sha,
                    evidence_sha256=stage_doc_sha,
                    expected_previous_checkpoint_sha256=head,
                )
            resolved = resolve()
            self.assertEqual(resolved.journal_head_sha256, stage_head)
            self.assertEqual(resolved.locator["state"], "cancelled_fresh_staged")

            cleanup_document = recovery.cancellation_cleanup_evidence_document(
                recovery_ref=ref,
                intent_sha256=intent_sha,
                fresh_transaction_ref=fresh_ref,
                cancellation_plan_document_sha256=cancellation_plan_doc_sha,
                cancellation_stage_evidence_document_sha256=stage_doc_sha,
                fresh_transaction_inventory_sha256=sealed_inventory[
                    "fresh_transaction_inventory_sha256"
                ],
                fresh_transaction_inventory_document_sha256=(
                    sealed_inventory[
                        "fresh_transaction_inventory_document_sha256"
                    ]
                ),
                cleanup_state="deleted_exact",
            )
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                cleanup_doc_sha = store.write_cancellation_cleanup_evidence(
                    cleanup_document
                )
            self.assertEqual(
                resolve().cancellation_cleanup_evidence_document_sha256,
                cleanup_doc_sha,
            )
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                cleanup_head = store.append_checkpoint(
                    phase="cancelled_fresh_cleaned",
                    stage="verified",
                    intent_sha256=intent_sha,
                    evidence_sha256=cleanup_doc_sha,
                    expected_previous_checkpoint_sha256=stage_head,
                )
            resolved = resolve()
            self.assertEqual(resolved.journal_head_sha256, cleanup_head)

            restore_document = recovery.cancellation_restore_evidence_document(
                recovery_ref=ref,
                intent_sha256=intent_sha,
                fresh_transaction_ref=fresh_ref,
                cancellation_plan_document_sha256=cancellation_plan_doc_sha,
                cancellation_cleanup_evidence_document_sha256=cleanup_doc_sha,
                old_transaction_ref="update_" + "2" * 32,
                old_transaction_sha256=old_transaction_sha,
                old_lock_sha256=old_lock_sha,
                restore_state="restored",
            )
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                restore_doc_sha = store.write_cancellation_restore_evidence(
                    restore_document
                )
            self.assertEqual(
                resolve().cancellation_restore_evidence_document_sha256,
                restore_doc_sha,
            )
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                restore_head = store.append_checkpoint(
                    phase="unapproved_restored",
                    stage="verified",
                    intent_sha256=intent_sha,
                    evidence_sha256=restore_doc_sha,
                    expected_previous_checkpoint_sha256=cleanup_head,
                )
            restored_without_receipt = resolve()
            self.assertEqual(
                restored_without_receipt.locator["state"],
                "unapproved_restored",
            )
            self.assertIsNone(restored_without_receipt.terminal_receipt)

            receipt = recovery.terminal_receipt_document(
                recovery_ref=ref,
                outcome="unapproved_restored",
                intent_sha256=intent_sha,
                journal_head_sha256=restore_head,
                fresh_transaction_ref=fresh_ref,
                old_transaction_inventory_sha256=old_transaction_sha,
                claim_absence_evidence_sha256=claim_absence_sha,
                cancelled_fresh_staging_sha256=(
                    recovery._transaction_semantic_sha256(stage_document)
                ),
                cancelled_fresh_transaction_inventory_sha256=(
                    sealed_inventory["fresh_transaction_inventory_sha256"]
                ),
                cancelled_fresh_transaction_inventory_document_sha256=(
                    sealed_inventory[
                        "fresh_transaction_inventory_document_sha256"
                    ]
                ),
                cancelled_fresh_cleanup_evidence_sha256=(
                    recovery._transaction_semantic_sha256(cleanup_document)
                ),
                restored_old_transaction_sha256=old_transaction_sha,
                preserved_old_lock_sha256=old_lock_sha,
                cancellation_plan_document_sha256=cancellation_plan_doc_sha,
                cancellation_result_document_sha256=result_record[
                    "cancellation_result_document_sha256"
                ],
                cancellation_result_sha256=result_record[
                    "cancellation_result_sha256"
                ],
                cancelled_fresh_staging_document_sha256=stage_doc_sha,
                cancelled_fresh_cleanup_evidence_document_sha256=(
                    cleanup_doc_sha
                ),
                restored_evidence_sha256=(
                    recovery._transaction_semantic_sha256(restore_document)
                ),
                restored_evidence_document_sha256=restore_doc_sha,
            )
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                receipt_path = store.paths.recovery_root / "terminal-receipt.json"
                for mutation in ("missing", "extra", "wrong_outcome"):
                    invalid_receipt = dict(receipt)
                    if mutation == "missing":
                        invalid_receipt.pop("restored_evidence_sha256")
                    elif mutation == "extra":
                        invalid_receipt["unexpected"] = True
                    else:
                        invalid_receipt["outcome"] = "unknown"
                    with self.subTest(terminal_receipt_mutation=mutation):
                        with self.assertRaisesRegex(
                            recovery.LegacyProjectUpdateRecoveryError,
                            "project_update_legacy_recovery_binding_invalid",
                        ):
                            store.write_terminal_receipt(invalid_receipt)
                        self.assertFalse(receipt_path.exists())
                receipt_sha = store.write_terminal_receipt(receipt)
            reconstructed = resolve()
            self.assertEqual(
                reconstructed.terminal_receipt_document_sha256,
                receipt_sha,
            )
            self.assertEqual(
                reconstructed.terminal_receipt["outcome"],
                "unapproved_restored",
            )
            self.assertIsNone(
                reconstructed.pending_cancellation_terminal
            )

            paths = recovery.RecoveryPaths.build(project, ref)
            handoff_path = project.joinpath(
                *recovery.PurePosixPath(
                    recovery.TERMINAL_HANDOFF_LOGICAL
                ).parts
            )
            handoff, capability_sha256 = self.cancellation_terminal_handoff(
                recovery_ref=ref,
                intent_sha256=intent_sha,
                terminal_receipt_sha256=receipt_sha,
                cancellation_result_document_sha256=result_record[
                    "cancellation_result_document_sha256"
                ],
            )
            exact_handoff_raw = recovery._canonical(handoff)
            handoff_path.write_bytes(exact_handoff_raw)
            recovery._fsync_directory(handoff_path.parent)

            pending_resolution = resolve()
            restarted_pending_resolution = resolve()
            pending = pending_resolution.pending_cancellation_terminal
            self.assertIsNotNone(pending)
            self.assertEqual(
                pending,
                restarted_pending_resolution.pending_cancellation_terminal,
            )
            self.assertEqual(pending.recovery_ref, ref)
            self.assertEqual(pending.outcome, "unapproved_restored")
            self.assertEqual(
                pending.active_locator_state,
                "unapproved_restored",
            )
            self.assertEqual(
                pending.active_locator_sha256,
                pending_resolution.locator_sha256,
            )
            self.assertEqual(
                pending.terminal_receipt_document_sha256,
                receipt_sha,
            )
            self.assertEqual(
                pending.cancellation_result_document_sha256,
                result_record["cancellation_result_document_sha256"],
            )
            self.assertEqual(
                pending.cancellation_result_sha256,
                result_record["cancellation_result_sha256"],
            )
            self.assertEqual(
                pending.result_payload_sha256,
                recovery._cancellation_delivery_payload_sha256(
                    recovery.cancellation_result_document()
                ),
            )
            self.assertNotEqual(
                pending.result_payload_sha256,
                pending.cancellation_result_sha256,
            )
            self.assertEqual(
                pending.terminal_handoff_document_sha256,
                recovery.sha256_bytes(exact_handoff_raw),
            )
            self.assertEqual(
                pending.delivery_capability_sha256,
                capability_sha256,
            )
            self.assertNotIn("reviewer", pending.__dataclass_fields__)
            self.assertNotIn("paths", pending.__dataclass_fields__)
            self.assertNotIn(
                "cancellation_result", pending.__dataclass_fields__
            )

            def control_bytes() -> dict[str, bytes]:
                candidates = [
                    item
                    for item in paths.recovery_root.rglob("*")
                    if item.is_file()
                ]
                candidates.extend(
                    item
                    for item in (paths.locator_path, handoff_path)
                    if item.is_file()
                )
                return {
                    str(item): item.read_bytes()
                    for item in sorted(candidates, key=str)
                }

            # A capsule cannot lead its receipt.  The receipt-only prefix is
            # valid, while capsule-without-receipt is preserved and blocked.
            held_receipt = receipt_path.with_suffix(".held")
            receipt_path.rename(held_receipt)
            capsule_without_receipt = control_bytes()
            try:
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_state_changed",
                ):
                    resolve()
                self.assertEqual(
                    control_bytes(), capsule_without_receipt
                )
            finally:
                held_receipt.rename(receipt_path)

            def rewrite_handoff(mutator) -> None:
                outer = recovery.verify_authenticated_document(
                    json.loads(exact_handoff_raw), self.key
                )
                mutator(outer)
                handoff_path.write_bytes(
                    recovery._canonical(
                        recovery.authenticated_document(outer, self.key)
                    )
                )

            capsule_mutations = (
                (
                    "missing",
                    lambda outer: outer["payload"].pop(
                        "delivery_capability_sha256"
                    ),
                    "project_update_legacy_recovery_binding_invalid",
                ),
                (
                    "extra",
                    lambda outer: outer.__setitem__("unexpected", True),
                    "project_update_legacy_recovery_binding_invalid",
                ),
                (
                    "cross_ref",
                    lambda outer: outer["payload"].__setitem__(
                        "recovery_ref", "recovery_" + "f" * 32
                    ),
                    "project_update_legacy_recovery_state_changed",
                ),
                (
                    "cross_receipt",
                    lambda outer: outer["payload"].__setitem__(
                        "terminal_receipt_sha256", "sha256:" + "f" * 64
                    ),
                    "project_update_legacy_recovery_state_changed",
                ),
                (
                    "cross_result",
                    lambda outer: outer["payload"].__setitem__(
                        "result_payload_sha256", "sha256:" + "f" * 64
                    ),
                    "project_update_legacy_recovery_state_changed",
                ),
                (
                    "storage_digest_is_not_delivery_digest",
                    lambda outer: outer["payload"].__setitem__(
                        "result_payload_sha256",
                        recovery.sha256_document(
                            recovery.cancellation_result_document()
                        ),
                    ),
                    "project_update_legacy_recovery_state_changed",
                ),
                (
                    "success_mismatch",
                    lambda outer: outer["payload"].__setitem__(
                        "outcome", "success"
                    ),
                    "project_update_legacy_recovery_binding_invalid",
                ),
            )
            for name, mutate, error in capsule_mutations:
                with self.subTest(cancellation_capsule_mutation=name):
                    rewrite_handoff(mutate)
                    preserved = control_bytes()
                    try:
                        with self.assertRaisesRegex(
                            recovery.LegacyProjectUpdateRecoveryError,
                            error,
                        ):
                            resolve()
                        self.assertEqual(control_bytes(), preserved)
                    finally:
                        handoff_path.write_bytes(exact_handoff_raw)

            unauthenticated = json.loads(exact_handoff_raw)
            mac = unauthenticated["authentication"]["mac"]
            unauthenticated["authentication"]["mac"] = (
                mac[:-1] + ("0" if mac[-1] != "0" else "1")
            )
            handoff_path.write_bytes(recovery._canonical(unauthenticated))
            preserved = control_bytes()
            try:
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_authentication_invalid",
                ):
                    resolve()
                self.assertEqual(control_bytes(), preserved)
            finally:
                handoff_path.write_bytes(exact_handoff_raw)

            terminal_locator_path = (
                paths.recovery_root / "terminal-locator.json"
            )
            terminal_locator_path.write_bytes(
                paths.locator_path.read_bytes()
            )
            collision = control_bytes()
            try:
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_state_ambiguous",
                ):
                    resolve()
                self.assertEqual(control_bytes(), collision)
            finally:
                terminal_locator_path.unlink()

            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_authentication_invalid",
            ):
                recovery.resolve_active_recovery(
                    project,
                    archive,
                    Provider(bytes(reversed(self.key))),
                )

            # A terminal_completed active locator is not the capsule-before-
            # retirement boundary.  It must be completed only through the
            # store's authenticated terminal publication primitive, never
            # reconstructed as pending cancellation authority.
            with recovery.LegacyRecoveryStore(
                project, ref, self.key
            ) as store:
                terminal_active_sha = store.publish_locator(
                    state="terminal_completed",
                    intent_sha256=intent_sha,
                    journal_head_sha256=restore_head,
                    previous_locator_sha256=pending.active_locator_sha256,
                    terminal_receipt_sha256=receipt_sha,
                )
            terminal_active_bytes = control_bytes()
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_state_changed",
            ):
                resolve()
            self.assertEqual(control_bytes(), terminal_active_bytes)
            with recovery.LegacyRecoveryStore(
                project, ref, self.key
            ) as store:
                retired = store.publish_terminal_locator_and_retire(
                    intent_sha256=intent_sha,
                    journal_head_sha256=restore_head,
                    previous_locator_sha256=terminal_active_sha,
                    terminal_receipt_sha256=receipt_sha,
                )
            self.assertFalse(
                recovery.RecoveryPaths.build(project, ref).locator_path.exists()
            )

            # A fresh process can authenticate the retired terminal without
            # recreating a key or exposing the private reviewer/result body.
            terminal = recovery.resolve_terminal_recovery(
                project,
                archive,
                ref,
                Provider(self.key),
            )
            restarted = recovery.resolve_terminal_recovery(
                project,
                archive,
                ref,
                Provider(self.key),
            )
            self.assertEqual(terminal, restarted)
            self.assertEqual(terminal.outcome, "unapproved_restored")
            self.assertEqual(
                terminal.terminal_locator_sha256,
                retired["terminal_locator_sha256"],
            )
            self.assertEqual(
                terminal.terminal_receipt_document_sha256,
                receipt_sha,
            )
            self.assertEqual(
                terminal.cancellation_result_document_sha256,
                result_record["cancellation_result_document_sha256"],
            )
            self.assertEqual(
                terminal.archive_identity_sha256,
                "sha256:" + "6" * 64,
            )
            self.assertNotIn("reviewer", terminal.__dataclass_fields__)
            self.assertNotIn(
                "cancellation_result", terminal.__dataclass_fields__
            )
            self.assertNotIn("paths", terminal.__dataclass_fields__)

            paths = recovery.RecoveryPaths.build(project, ref)
            terminal_locator_path = paths.recovery_root / "terminal-locator.json"
            terminal_receipt_path = paths.recovery_root / "terminal-receipt.json"
            cancellation_plan_path = paths.recovery_root / "cancellation-plan.json"
            restore_path = (
                paths.recovery_root / "cancellation-restore-evidence.json"
            )
            terminal_payload = recovery.verify_authenticated_document(
                json.loads(terminal_locator_path.read_bytes()), self.key
            )
            preterminal_path = (
                paths.recovery_root
                / "locator-history"
                / (
                    terminal_payload["previous_locator_sha256"].removeprefix(
                        "sha256:"
                    )
                    + ".json"
                )
            )

            def replace_authenticated(path, mutate):
                original = path.read_bytes()
                payload = recovery.verify_authenticated_document(
                    json.loads(original), self.key
                )
                mutate(payload)
                path.write_bytes(
                    recovery._canonical(
                        recovery.authenticated_document(payload, self.key)
                    )
                )
                return original

            # Missing exact evidence is not reconstructed from the terminal
            # receipt or guessed from neighboring documents.
            missing = terminal_receipt_path.with_suffix(".missing")
            terminal_receipt_path.rename(missing)
            try:
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_state_changed",
                ):
                    recovery.resolve_terminal_recovery(
                        project, archive, ref, Provider(self.key)
                    )
            finally:
                missing.rename(terminal_receipt_path)

            # Authenticated extra fields, a cross-ref, and a cross-digest are
            # independently rejected, then the exact original is restored.
            mutations = (
                (
                    "extra",
                    terminal_locator_path,
                    lambda payload: payload.__setitem__("unexpected", True),
                    "project_update_legacy_recovery_binding_invalid",
                ),
                (
                    "cross_ref",
                    cancellation_plan_path,
                    lambda payload: payload.__setitem__(
                        "recovery_ref", "recovery_" + "f" * 32
                    ),
                    "project_update_legacy_recovery_binding_invalid",
                ),
                (
                    "cross_preterminal_locator",
                    preterminal_path,
                    lambda payload: payload.__setitem__(
                        "state", "cancelled_fresh_cleaned"
                    ),
                    "project_update_legacy_recovery_state_changed",
                ),
                (
                    "cross_digest",
                    restore_path,
                    lambda payload: payload.__setitem__(
                        "cancellation_cleanup_evidence_document_sha256",
                        "sha256:" + "f" * 64,
                    ),
                    "project_update_legacy_recovery_state_changed",
                ),
            )
            for name, path, mutate, error in mutations:
                with self.subTest(terminal_mutation=name):
                    original = replace_authenticated(path, mutate)
                    try:
                        with self.assertRaisesRegex(
                            recovery.LegacyProjectUpdateRecoveryError,
                            error,
                        ):
                            recovery.resolve_terminal_recovery(
                                project, archive, ref, Provider(self.key)
                            )
                    finally:
                        path.write_bytes(original)

            # An unauthenticated edit cannot be confused with a state drift.
            original_terminal = terminal_locator_path.read_bytes()
            tampered_terminal = json.loads(original_terminal)
            original_mac = tampered_terminal["authentication"]["mac"]
            prefix = "hmac-sha256:"
            first = original_mac[len(prefix)]
            tampered_terminal["authentication"]["mac"] = (
                prefix
                + ("0" if first != "0" else "1")
                + original_mac[len(prefix) + 1 :]
            )
            terminal_locator_path.write_bytes(
                recovery._canonical(tampered_terminal)
            )
            try:
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_authentication_invalid",
                ):
                    recovery.resolve_terminal_recovery(
                        project, archive, ref, Provider(self.key)
                    )
            finally:
                terminal_locator_path.write_bytes(original_terminal)

            # A new active locator colliding with the retired terminal is an
            # ambiguous authority and is rejected before terminal delivery.
            paths.locator_path.write_bytes(original_terminal)
            try:
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_state_ambiguous",
                ):
                    recovery.resolve_terminal_recovery(
                        project, archive, ref, Provider(self.key)
                    )
            finally:
                paths.locator_path.unlink()

            # The exact HMAC child must not be accepted through a linked
            # locator-history parent.  Use a real directory symlink when the
            # host permits one; the deterministic fallback still proves that
            # this intermediate directory is passed through the safety gate.
            history_root = preterminal_path.parent
            history_backup = paths.recovery_root / "locator-history.original"
            outside_history = base / "outside-locator-history"
            outside_history.mkdir()
            (outside_history / preterminal_path.name).write_bytes(
                preterminal_path.read_bytes()
            )
            history_root.rename(history_backup)
            linked = False
            try:
                try:
                    history_root.symlink_to(
                        outside_history,
                        target_is_directory=True,
                    )
                    linked = True
                except OSError:
                    history_backup.rename(history_root)
                if linked:
                    with self.assertRaisesRegex(
                        recovery.LegacyProjectUpdateRecoveryError,
                        "project_update_legacy_recovery_path_unsafe",
                    ):
                        recovery.resolve_terminal_recovery(
                            project, archive, ref, Provider(self.key)
                        )
                else:
                    real_safe_directory = recovery._safe_directory

                    def reject_history_parent(path):
                        if Path(path) == history_root:
                            raise recovery.LegacyProjectUpdateRecoveryError(
                                "project_update_legacy_recovery_path_unsafe"
                            )
                        return real_safe_directory(path)

                    with patch.object(
                        recovery,
                        "_safe_directory",
                        side_effect=reject_history_parent,
                    ):
                        with self.assertRaisesRegex(
                            recovery.LegacyProjectUpdateRecoveryError,
                            "project_update_legacy_recovery_path_unsafe",
                        ):
                            recovery.resolve_terminal_recovery(
                                project, archive, ref, Provider(self.key)
                            )
            finally:
                if linked and os.path.lexists(history_root):
                    history_root.unlink()
                if not history_root.exists() and history_backup.exists():
                    history_backup.rename(history_root)

            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_authentication_invalid",
            ):
                recovery.resolve_terminal_recovery(
                    project,
                    archive,
                    ref,
                    Provider(bytes(reversed(self.key))),
                )

            class TrackingProvider(Provider):
                def __init__(self, key):
                    super().__init__(key)
                    self.calls = 0

                def use_key(self, _root, consumer, *, create_if_missing=False):
                    self.calls += 1
                    return super().use_key(
                        _root,
                        consumer,
                        create_if_missing=create_if_missing,
                    )

            unused = TrackingProvider(self.key)
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_binding_invalid",
            ):
                recovery.resolve_terminal_recovery(
                    project,
                    archive,
                    "not-a-recovery-ref",
                    unused,
                )
            self.assertEqual(unused.calls, 0)
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_binding_invalid",
            ):
                recovery.resolve_terminal_recovery(
                    project,
                    archive,
                    ref,
                    unused,
                    create_if_missing=True,
                )
            self.assertEqual(unused.calls, 0)

    @unittest.skipUnless(os.name == "nt", "exact locator publication is Windows-only")
    def test_terminal_locator_publish_and_retire_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "d" * 32
            fresh_ref = "update_" + "e" * 32
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                intent_sha = self.initialize(store, ref)
                locator_sha = recovery.sha256_bytes(
                    store.paths.locator_path.read_bytes()
                )
                head = None
                phases = (
                    "legacy_eligibility_verified",
                    "old_transaction_staged",
                    "fresh_transaction_allocated",
                    "fresh_reservation_bound",
                    "fresh_plan_sealed",
                    "fresh_lock_backlinked",
                    "fresh_transaction_completed",
                )
                for index, phase in enumerate(phases, start=1):
                    head = store.append_checkpoint(
                        phase=phase,
                        stage="verified",
                        intent_sha256=intent_sha,
                        evidence_sha256="sha256:" + f"{index:x}" * 64,
                        expected_previous_checkpoint_sha256=head,
                    )
                    locator_sha = store.publish_locator(
                        state=recovery._CHECKPOINT_LOCATOR_STATE[phase],
                        intent_sha256=intent_sha,
                        journal_head_sha256=head,
                        previous_locator_sha256=locator_sha,
                    )
                receipt = recovery.terminal_receipt_document(
                    recovery_ref=ref,
                    outcome="success",
                    intent_sha256=intent_sha,
                    journal_head_sha256=head,
                    fresh_transaction_ref=fresh_ref,
                    old_transaction_inventory_sha256="sha256:" + "8" * 64,
                    fresh_transaction_completed_sha256="sha256:" + "9" * 64,
                    claim_evidence_sha256="sha256:" + "a" * 64,
                    old_lock_backup_sha256="sha256:" + "b" * 64,
                )
                receipt_sha = store.write_terminal_receipt(receipt)
                first = store.publish_terminal_locator_and_retire(
                    intent_sha256=intent_sha,
                    journal_head_sha256=head,
                    previous_locator_sha256=locator_sha,
                    terminal_receipt_sha256=receipt_sha,
                )
                second = store.publish_terminal_locator_and_retire(
                    intent_sha256=intent_sha,
                    journal_head_sha256=head,
                    previous_locator_sha256=locator_sha,
                    terminal_receipt_sha256=receipt_sha,
                )
                self.assertEqual(first, second)
                self.assertFalse(store.paths.locator_path.exists())

            class Provider:
                def use_key(
                    self, _root, consumer, *, create_if_missing=False
                ):
                    if create_if_missing:
                        raise AssertionError("must not create")
                    return consumer(memoryview(self_key))

            self_key = self.key
            archive = Path(tmp) / "archive"
            archive.mkdir()
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_state_changed",
            ):
                recovery.resolve_terminal_recovery(
                    project,
                    archive,
                    ref,
                    Provider(),
                )

    @unittest.skipUnless(os.name == "nt", "exact locator publication is Windows-only")
    def test_resolver_reconciles_exactly_one_forward_checkpoint(self) -> None:
        class Provider:
            def __init__(self, key: bytes) -> None:
                self.key = key

            def use_key(self, _root, consumer, *, create_if_missing=False):
                if create_if_missing:
                    raise AssertionError("must not create")
                return consumer(memoryview(self.key))

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            project = self.project(base)
            archive = base / "archive"
            archive.mkdir()
            ref = "recovery_" + "8" * 32
            with recovery.LegacyRecoveryStore(project, ref, self.key) as store:
                intent_sha = self.initialize(store, ref)
                prior_locator = recovery.sha256_bytes(
                    store.paths.locator_path.read_bytes()
                )
                head = store.append_checkpoint(
                    phase="legacy_eligibility_verified",
                    stage="verified",
                    intent_sha256=intent_sha,
                    evidence_sha256="sha256:" + "9" * 64,
                    expected_previous_checkpoint_sha256=None,
                )
            resolved = recovery.resolve_active_recovery(
                project,
                archive,
                Provider(self.key),
            )
            self.assertEqual(resolved.locator_journal_head_sha256, None)
            self.assertEqual(resolved.journal_head_sha256, head)
            self.assertEqual(
                resolved.locator["state"],
                "legacy_eligible",
            )
            self.assertEqual(
                resolved.locator["journal_head_sha256"],
                head,
            )
            self.assertNotEqual(resolved.locator_sha256, prior_locator)
            self.assertEqual(
                resolved.pending_checkpoint["phase"],
                "legacy_eligibility_verified",
            )

    def test_wide_tree_retains_only_current_depth_and_caps_depth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            tree = project / ".zettel-kasten" / "private" / "wide"
            tree.mkdir()
            for index in range(64):
                (tree / f"d{index:03d}").mkdir()
            original = recovery._retained_directory
            active = 0
            peak = 0

            @contextmanager
            def counted(*args, **kwargs):
                nonlocal active, peak
                with original(*args, **kwargs) as value:
                    active += 1
                    peak = max(peak, active)
                    try:
                        yield value
                    finally:
                        active -= 1

            with patch.object(recovery, "_retained_directory", counted):
                inventory = recovery.directory_tree_inventory(tree)
            self.assertEqual(inventory["entry_count"], 64)
            self.assertLessEqual(peak, 2)

            deep = project / ".zettel-kasten" / "private" / "deep"
            (deep / "a" / "b").mkdir(parents=True)
            with patch.object(recovery, "_MAX_TREE_DEPTH", 1):
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_path_unsafe",
                ):
                    recovery.directory_tree_inventory(deep)

    def test_queued_child_replacement_is_not_enumerated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            tree = project / ".zettel-kasten" / "private" / "queued"
            child = tree / "child"
            child.mkdir(parents=True)
            (child / "approved").write_bytes(b"approved")
            replacement = tree.parent / "replacement"
            replacement.mkdir()
            (replacement / "must-not-enumerate").write_bytes(b"private")
            displaced = tree.parent / "displaced"
            original = recovery._retained_directory
            swapped = False

            @contextmanager
            def swap_before_child(path, *, expected_identity=None):
                nonlocal swapped
                if Path(path) == child and expected_identity is not None and not swapped:
                    child.rename(displaced)
                    replacement.rename(child)
                    swapped = True
                with original(path, expected_identity=expected_identity) as value:
                    yield value

            with patch.object(recovery, "_retained_directory", swap_before_child):
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_state_changed",
                ):
                    recovery.directory_tree_inventory(tree)
            self.assertTrue((child / "must-not-enumerate").exists())
            self.assertTrue((displaced / "approved").exists())

    @unittest.skipUnless(os.name == "nt", "retained delete is Windows-only")
    def test_exact_delete_preserves_raced_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            tree = project / ".zettel-kasten" / "private" / "delete-race"
            tree.mkdir()
            target = tree / "target"
            target.write_bytes(b"approved")
            inventory = recovery.directory_tree_inventory(tree)
            displaced = tree.parent / "approved-displaced"
            original = legacy_cleanup_bound_delete._delete_exact_approved_file
            raced = False

            def replace_then_delete(workspace_root, path, expected):
                nonlocal raced
                if Path(path) == target and not raced:
                    target.rename(displaced)
                    target.write_bytes(b"replacement")
                    raced = True
                return original(workspace_root, path, expected)

            with patch.object(
                legacy_cleanup_bound_delete,
                "_delete_exact_approved_file",
                side_effect=replace_then_delete,
            ):
                with self.assertRaisesRegex(
                    recovery.LegacyProjectUpdateRecoveryError,
                    "project_update_legacy_recovery_state_changed",
                ):
                    recovery.delete_exact_inventory_tree(tree, inventory)
            self.assertEqual(target.read_bytes(), b"replacement")
            self.assertEqual(displaced.read_bytes(), b"approved")

    @unittest.skipUnless(os.name == "nt", "NTFS alternate streams are Windows-only")
    def test_inventory_rejects_alternate_data_streams(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            tree = project / ".zettel-kasten" / "private" / "ads"
            tree.mkdir()
            target = tree / "target"
            target.write_bytes(b"approved")
            try:
                with open(str(target) + ":private", "wb") as stream:
                    stream.write(b"secret")
            except OSError:
                self.skipTest("filesystem does not support alternate streams")
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_path_unsafe",
            ):
                recovery.directory_tree_inventory(tree)
            self.assertEqual(target.read_bytes(), b"approved")
            with open(str(target) + ":private", "rb") as stream:
                self.assertEqual(stream.read(), b"secret")

    @unittest.skipUnless(os.name == "nt", "retained lock handoff is Windows-only")
    def test_lock_handoff_rejects_unowned_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            lock = parent / "version-update.lock"
            replacement = parent / ".fresh-lock"
            backup = parent / ".old-lock-backup"
            lock.write_bytes(b"old")
            replacement.write_bytes(b"fresh")
            backup.write_bytes(b"")
            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_lock_replace_ambiguous",
            ):
                recovery.atomic_replace_lock_with_backup_windows(
                    lock,
                    replacement,
                    backup,
                    expected_old_bytes=b"old",
                    expected_fresh_bytes=b"fresh",
                )
            self.assertEqual(lock.read_bytes(), b"old")
            self.assertEqual(replacement.read_bytes(), b"fresh")
            self.assertEqual(backup.read_bytes(), b"")

    @unittest.skipUnless(os.name == "nt", "retained vault move is Windows-only")
    def test_old_lock_vault_is_exact_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            paths = recovery.RecoveryPaths.build(
                project,
                "recovery_" + "a" * 32,
            )
            paths.recovery_root.mkdir(parents=True)
            source = project / ".zettel-kasten" / ".old-lock"
            source.write_bytes(b"old-lock")
            first = recovery.vault_old_lock_backup(
                paths,
                source,
                expected_old_lock_bytes=b"old-lock",
            )
            self.assertEqual(first["state"], "vaulted")
            self.assertFalse(source.exists())
            second = recovery.vault_old_lock_backup(
                paths,
                source,
                expected_old_lock_bytes=b"old-lock",
            )
            self.assertEqual(second["state"], "already_vaulted")
            self.assertEqual(
                second["old_lock_backup_sha256"],
                first["old_lock_backup_sha256"],
            )

    @unittest.skipUnless(os.name == "nt", "retained lock handoff is Windows-only")
    def test_replace_file_keeps_lock_name_and_exact_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            lock = parent / "version-update.lock"
            replacement = parent / ".fresh-lock"
            backup = parent / ".old-lock-backup"
            old = b"old-lock\n"
            fresh = b"fresh-lock\n"
            lock.write_bytes(old)
            replacement.write_bytes(fresh)
            outcome = recovery.atomic_replace_lock_with_backup_windows(
                lock,
                replacement,
                backup,
                expected_old_bytes=old,
                expected_fresh_bytes=fresh,
            )
            self.assertEqual(outcome, "replaced")
            self.assertEqual(lock.read_bytes(), fresh)
            self.assertEqual(backup.read_bytes(), old)
            self.assertFalse(replacement.exists())
            self.assertEqual(
                recovery.atomic_replace_lock_with_backup_windows(
                    lock,
                    replacement,
                    backup,
                    expected_old_bytes=old,
                    expected_fresh_bytes=fresh,
                ),
                "already_replaced",
            )

    @unittest.skipUnless(os.name == "nt", "retained lock handoff is Windows-only")
    def test_lock_handoff_hardlink_checkpoint_has_no_gap_and_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "c" * 32
            paths = recovery.RecoveryPaths.build(project, ref)
            paths.recovery_root.mkdir(parents=True)
            lock = project / ".zettel-kasten" / "version-update.lock"
            old = b"old-lock\n"
            fresh = b"fresh-lock\n"
            lock.write_bytes(old)
            replacement, backup = recovery.prepare_lock_handoff_files(
                paths,
                fresh_lock_bytes=fresh,
            )

            def stop_after_backup(stage: str) -> None:
                if stage == "old_backup_durable_before_atomic_replace":
                    self.assertTrue(lock.exists())
                    self.assertEqual(lock.read_bytes(), old)
                    raise RuntimeError("synthetic-hard-exit")

            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_lock_replace_ambiguous",
            ):
                recovery.atomic_replace_lock_with_backup_windows(
                    lock,
                    replacement,
                    backup,
                    expected_old_bytes=old,
                    expected_fresh_bytes=fresh,
                    _failpoint=stop_after_backup,
                )
            self.assertTrue(lock.exists())
            self.assertEqual(
                recovery.classify_lock_handoff(paths, old, fresh),
                "backup_linked",
            )
            self.assertEqual(
                recovery.prepare_lock_handoff_files(
                    paths,
                    fresh_lock_bytes=fresh,
                ),
                (replacement, backup),
            )
            self.assertEqual(
                recovery.atomic_replace_lock_with_backup_windows(
                    lock,
                    replacement,
                    backup,
                    expected_old_bytes=old,
                    expected_fresh_bytes=fresh,
                ),
                "replaced",
            )
            self.assertEqual(
                recovery.classify_lock_handoff(paths, old, fresh),
                "fresh",
            )
            self.assertEqual(lock.read_bytes(), fresh)
            self.assertEqual(backup.read_bytes(), old)

    @unittest.skipUnless(os.name == "nt", "retained lock handoff is Windows-only")
    def test_lock_handoff_preserves_raced_public_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.project(Path(tmp))
            ref = "recovery_" + "f" * 32
            paths = recovery.RecoveryPaths.build(project, ref)
            paths.recovery_root.mkdir(parents=True)
            lock = project / ".zettel-kasten" / "version-update.lock"
            old = b"old-lock\n"
            fresh = b"fresh-lock\n"
            outsider = b"unrelated-concurrent-lock\n"
            lock.write_bytes(old)
            replacement, backup = recovery.prepare_lock_handoff_files(
                paths,
                fresh_lock_bytes=fresh,
            )
            displaced = lock.parent / ".displaced-old-lock"

            def replace_public_name(stage: str) -> None:
                if stage == "lock_names_bound_before_atomic_replace":
                    lock.rename(displaced)
                    lock.write_bytes(outsider)

            with self.assertRaisesRegex(
                recovery.LegacyProjectUpdateRecoveryError,
                "project_update_legacy_recovery_lock_replace_ambiguous",
            ):
                recovery.atomic_replace_lock_with_backup_windows(
                    lock,
                    replacement,
                    backup,
                    expected_old_bytes=old,
                    expected_fresh_bytes=fresh,
                    _failpoint=replace_public_name,
                )
            self.assertEqual(lock.read_bytes(), outsider)
            self.assertEqual(displaced.read_bytes(), old)
            self.assertEqual(backup.read_bytes(), old)
            self.assertEqual(replacement.read_bytes(), fresh)


if __name__ == "__main__":
    unittest.main()
