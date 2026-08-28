from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest import mock

from wom_kit import archive_services, local_recovery_execution
from wom_kit.exact_human_approval import (
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID
from wom_kit.exact_human_approval_workflow import (
    ExactHumanApprovalWorkflowError,
    _execute_exact_human_approved_write_core,
)
from wom_kit.exact_operation_manifest import (
    ExactFieldEffect,
    ExactOperationItem,
    ExactOperationManifest,
    FileExactOperationCheckpointStore,
    exact_operation_writer_lock,
    hash_field_value,
)
from wom_kit.local_recovery_execution import (
    APPLY_OPERATION,
    LocalRecoveryError,
    LocalRecoveryFieldSpec,
    _run_with_store,
    build_observed_post_subset_revert_plan,
    build_local_recovery_plan,
    discover_local_recovery_plan,
    execute_local_recovery,
    load_local_recovery_plan,
    local_recovery_ledger_identity_sha256,
    local_recovery_ledger_relative,
    local_recovery_zettel_identity_sha256,
    persist_local_recovery_control,
    resume_local_recovery,
    verify_local_recovery_state,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = KIT_ROOT / "examples" / "fake-life-archive"
ZETTEL_ID = "zet_20240504_fake_lunch_thought"


class _ApproveNative:
    def __init__(self) -> None:
        self.calls = 0

    def show(self, **_kwargs: object) -> tuple[int, bool]:
        self.calls += 1
        return APPROVE_BUTTON_ID, True


class _StableKeyProvider:
    def __init__(self) -> None:
        self.create_if_missing: list[bool] = []

    def use_key(
        self,
        _root: Path | str,
        consumer: Callable[[memoryview], Any],
        *,
        create_if_missing: bool = False,
    ) -> Any:
        self.create_if_missing.append(create_if_missing)
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class LocalRecoveryExecutionTests(unittest.TestCase):
    def archive(self, parent: Path) -> Path:
        root = parent / "archive"
        shutil.copytree(FIXTURE, root)
        archive_services.index_archive(root)
        evidence = archive_services.require_current_zettel_index(root)
        self.assertTrue(evidence["ok"], evidence)
        return root

    def title_plan(self, root: Path):
        archive_id = archive_services.read_archive_id(root)
        relative = f"zettels/{ZETTEL_ID}.md"
        path = root.joinpath(*relative.split("/"))
        frontmatter, _body = archive_services.require_readable_zettel_content(path)
        before = frontmatter["title"].encode("utf-8")
        after = b"Recovered exact title"
        identity = local_recovery_zettel_identity_sha256(
            archive_id,
            ZETTEL_ID,
            relative,
        )
        source = b'{"source":"synthetic"}'
        item = ExactOperationItem(
            ordinal=0,
            item_id="item:000000",
            target_kind="zettel",
            target_ref=identity,
            target_identity_sha256=identity,
            fields=(
                ExactFieldEffect(
                    field_ref="frontmatter.title",
                    pre_sha256=hash_field_value(before),
                    post_sha256=hash_field_value(after),
                    source_sha256=hash_field_value(source),
                ),
            ),
        )
        manifest = ExactOperationManifest.build(
            operation=APPLY_OPERATION,
            archive_identity_sha256=(
                exact_human_approval_archive_identity_sha256(archive_id)
            ),
            items=(item,),
        )
        spec = LocalRecoveryFieldSpec(
            item_id=item.item_id,
            target_kind=item.target_kind,
            target_ref=item.target_ref,
            target_identity_sha256=item.target_identity_sha256,
            field_ref=item.fields[0].field_ref,
            target_relative=relative,
            zettel_id=ZETTEL_ID,
            pre_value=before,
            post_value=after,
            source_value=source,
        )
        return build_local_recovery_plan(
            root,
            domain="synthetic_title",
            manifest=manifest,
            specs=(spec,),
        )

    def ledger_plan(self, root: Path, *, count: int = 3):
        archive_id = archive_services.read_archive_id(root)
        items = []
        specs = []
        for ordinal in range(count):
            post = (f'{{"ordinal":{ordinal}}}\n').encode("ascii")
            source = (f'{{"source_ordinal":{ordinal}}}').encode("ascii")
            relative = local_recovery_ledger_relative("synthetic", post)
            identity = local_recovery_ledger_identity_sha256(
                archive_id,
                "synthetic",
                relative,
            )
            item = ExactOperationItem(
                ordinal=ordinal,
                item_id=f"item:{ordinal:06d}",
                target_kind="local_recovery_ledger",
                target_ref=identity,
                target_identity_sha256=identity,
                fields=(
                    ExactFieldEffect(
                        field_ref="classification.ledger",
                        pre_sha256=hash_field_value(None),
                        post_sha256=hash_field_value(post),
                        source_sha256=hash_field_value(source),
                    ),
                ),
            )
            items.append(item)
            specs.append(
                LocalRecoveryFieldSpec(
                    item_id=item.item_id,
                    target_kind=item.target_kind,
                    target_ref=item.target_ref,
                    target_identity_sha256=item.target_identity_sha256,
                    field_ref=item.fields[0].field_ref,
                    target_relative=relative,
                    zettel_id=None,
                    pre_value=None,
                    post_value=post,
                    source_value=source,
                )
            )
        manifest = ExactOperationManifest.build(
            operation=APPLY_OPERATION,
            archive_identity_sha256=(
                exact_human_approval_archive_identity_sha256(archive_id)
            ),
            items=items,
        )
        return build_local_recovery_plan(
            root,
            domain="synthetic_ledger",
            manifest=manifest,
            specs=specs,
        )

    def execute(self, plan, *, mode: str, resume: bool = False):
        with exact_operation_writer_lock(plan.archive_root) as lock:
            store = FileExactOperationCheckpointStore(
                plan.archive_root,
                writer_lock=lock,
            )
            return _run_with_store(
                plan,
                None,
                store,
                mode=mode,
                resume=resume,
                progress_hook=None,
            )

    def test_title_apply_and_field_scoped_revert_preserve_later_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.title_plan(root)
            applied = self.execute(plan, mode="apply")
            self.assertTrue(applied["ok"], applied)
            self.assertTrue(
                verify_local_recovery_state(plan, state="post")["all_match"]
            )

            path = root / "zettels" / f"{ZETTEL_ID}.md"
            text = path.read_text(encoding="utf-8")
            self.assertIn("Recovered exact title", text)
            path.write_text(
                text + "\nLater unrelated body edit.\n",
                encoding="utf-8",
                newline="",
            )
            archive_services.index_archive(root)
            self.assertTrue(
                archive_services.require_current_zettel_index(root)["ok"]
            )

            persist_local_recovery_control(plan)
            loaded = load_local_recovery_plan(
                root,
                manifest_sha256=plan.manifest.manifest_sha256,
            )
            reverted = self.execute(loaded, mode="revert")
            self.assertTrue(reverted["ok"], reverted)
            self.assertTrue(
                verify_local_recovery_state(loaded, state="pre")["all_match"]
            )
            final = path.read_text(encoding="utf-8")
            self.assertNotIn("Recovered exact title", final)
            self.assertIn("Later unrelated body edit.", final)

    def test_revert_control_is_auto_discovered_only_when_unambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.title_plan(root)
            self.assertTrue(self.execute(plan, mode="apply")["ok"])
            persist_local_recovery_control(plan)

            selected, discovery = discover_local_recovery_plan(
                root,
                allowed_domains={"synthetic_title"},
                mode="revert",
            )
            self.assertIsNotNone(selected)
            assert selected is not None
            self.assertEqual(
                selected.manifest.manifest_sha256,
                plan.manifest.manifest_sha256,
            )
            self.assertEqual(
                discovery["state"],
                "local_recovery_control_selected",
            )
            self.assertTrue(discovery["auto_discovered"])
            self.assertFalse(discovery["operator_counting_required"])

            second = self.ledger_plan(root, count=1)
            self.assertTrue(self.execute(second, mode="apply")["ok"])
            persist_local_recovery_control(second)
            selected, ambiguous = discover_local_recovery_plan(
                root,
                allowed_domains={"synthetic_title", "synthetic_ledger"},
                mode="revert",
            )
            self.assertIsNone(selected)
            self.assertEqual(
                ambiguous["state"],
                "local_recovery_control_ambiguous",
            )
            self.assertEqual(ambiguous["candidate_count"], 2)

    def test_resume_recovers_write_completed_before_field_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.title_plan(root)
            original = local_recovery_execution._Writer.write_field

            def crash_after_write(writer, **kwargs):
                original(writer, **kwargs)
                raise RuntimeError("synthetic interruption after canonical write")

            with mock.patch.object(
                local_recovery_execution._Writer,
                "write_field",
                new=crash_after_write,
            ):
                interrupted = self.execute(plan, mode="apply")
            self.assertFalse(interrupted["ok"], interrupted)
            self.assertEqual(interrupted["state"], "fully_applied_receipt_pending")
            self.assertEqual(interrupted["applied_field_count"], 1)
            self.assertEqual(interrupted["remaining_field_count"], 0)
            self.assertEqual(interrupted["checkpointed_field_count"], 0)
            self.assertEqual(
                interrupted["written_before_checkpoint_field_count"], 1
            )
            self.assertTrue(interrupted["resume_supported"])

            resumed = self.execute(plan, mode="apply", resume=True)
            self.assertTrue(resumed["ok"], resumed)
            self.assertEqual(resumed["written_field_count"], 0)
            self.assertEqual(resumed["resumed_field_count"], 1)
            self.assertTrue(
                verify_local_recovery_state(plan, state="post")["all_match"]
            )

    def test_revert_supersedes_unfinished_apply_and_blocks_old_resume(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.title_plan(root)
            native = _ApproveNative()
            keys = _StableKeyProvider()
            original_write = local_recovery_execution._Writer.write_field

            def approved_workflow(archive_root, context, writer):
                return _execute_exact_human_approved_write_core(
                    archive_root,
                    context,
                    writer,
                    native=native,
                    key_provider=keys,
                )

            def crash_after_write(writer, **kwargs):
                original_write(writer, **kwargs)
                raise RuntimeError("synthetic interruption after write")

            with mock.patch.object(
                local_recovery_execution,
                "_execute_exact_human_approved_write",
                new=approved_workflow,
            ), mock.patch.object(
                local_recovery_execution._Writer,
                "write_field",
                new=crash_after_write,
            ):
                interrupted = execute_local_recovery(plan)
            self.assertFalse(interrupted["ok"], interrupted)
            self.assertEqual(
                interrupted["written_before_checkpoint_field_count"],
                1,
            )

            loaded = load_local_recovery_plan(
                root,
                manifest_sha256=plan.manifest.manifest_sha256,
            )
            with mock.patch.object(
                local_recovery_execution,
                "_execute_exact_human_approved_write",
                new=approved_workflow,
            ):
                reverted = execute_local_recovery(loaded, mode="revert")
            self.assertTrue(reverted["ok"], reverted)
            self.assertTrue(
                reverted["superseded_parent_apply_execution"]
            )
            self.assertTrue(
                verify_local_recovery_state(loaded, state="pre")["all_match"]
            )

            selected, discovery = discover_local_recovery_plan(
                root,
                allowed_domains={"synthetic_title"},
                mode="apply",
                resume=True,
            )
            self.assertIsNone(selected)
            self.assertEqual(
                discovery["state"],
                "local_recovery_control_not_found",
            )
            with self.assertRaises(LocalRecoveryError) as raised:
                resume_local_recovery(loaded, key_provider=keys)
            self.assertEqual(raised.exception.code, "local_recovery_resume_invalid")
            self.assertEqual(native.calls, 2)
            supersessions = (
                root
                / "profiles"
                / "local"
                / "local-recovery"
                / "supersessions"
            )
            self.assertEqual(len(list(supersessions.glob("*.pending.json"))), 1)
            self.assertEqual(len(list(supersessions.glob("*.final.json"))), 1)

            # The final record is durable evidence in its own right.  Losing
            # the pending half must fail closed rather than resurrecting the
            # compensated parent apply.
            next(supersessions.glob("*.pending.json")).unlink()
            with self.assertRaises(LocalRecoveryError) as orphan_final:
                resume_local_recovery(loaded, key_provider=keys)
            self.assertEqual(
                orphan_final.exception.code,
                "local_recovery_resume_invalid",
            )
            self.assertTrue(
                verify_local_recovery_state(loaded, state="pre")["all_match"]
            )

    def test_interruption_reports_exact_partial_counts_and_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.ledger_plan(root, count=3)
            original = local_recovery_execution._Writer.write_field
            calls = 0

            def fail_before_third_write(writer, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise RuntimeError("synthetic third-field interruption")
                original(writer, **kwargs)

            with mock.patch.object(
                local_recovery_execution._Writer,
                "write_field",
                new=fail_before_third_write,
            ):
                interrupted = self.execute(plan, mode="apply")
            self.assertFalse(interrupted["ok"], interrupted)
            self.assertEqual(interrupted["state"], "partially_applied")
            self.assertEqual(interrupted["applied_field_count"], 2)
            self.assertEqual(interrupted["remaining_field_count"], 1)
            self.assertEqual(interrupted["checkpointed_field_count"], 2)
            self.assertEqual(
                interrupted["written_before_checkpoint_field_count"], 0
            )
            self.assertTrue(interrupted["resume_supported"])
            self.assertTrue(interrupted["subset_revert_supported"])
            self.assertEqual(
                interrupted["next_safe_actions"],
                ["resume_same_manifest", "revert_observed_applied_subset"],
            )

            resumed = self.execute(plan, mode="apply", resume=True)
            self.assertTrue(resumed["ok"], resumed)
            self.assertEqual(resumed["written_field_count"], 1)
            self.assertEqual(resumed["resumed_field_count"], 2)

    def test_partial_apply_builds_exact_observed_post_subset_revert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.ledger_plan(root, count=3)
            original = local_recovery_execution._Writer.write_field
            calls = 0

            def fail_before_third_write(writer, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise RuntimeError("synthetic third-field interruption")
                original(writer, **kwargs)

            with mock.patch.object(
                local_recovery_execution._Writer,
                "write_field",
                new=fail_before_third_write,
            ):
                interrupted = self.execute(plan, mode="apply")
            self.assertEqual(interrupted["applied_field_count"], 2)
            persist_local_recovery_control(plan)
            loaded = load_local_recovery_plan(
                root,
                manifest_sha256=plan.manifest.manifest_sha256,
            )
            subset, inspection = build_observed_post_subset_revert_plan(loaded)
            self.assertIsNotNone(subset)
            assert subset is not None
            self.assertEqual(inspection["selected_post_field_count"], 2)
            self.assertEqual(inspection["already_pre_field_count"], 1)
            self.assertEqual(len(subset.manifest.items), 2)
            self.assertNotEqual(
                subset.manifest.manifest_sha256,
                plan.manifest.manifest_sha256,
            )

            reverted = self.execute(subset, mode="revert")
            self.assertTrue(reverted["ok"], reverted)
            self.assertEqual(reverted["written_field_count"], 2)
            self.assertTrue(
                verify_local_recovery_state(loaded, state="pre")["all_match"]
            )

    def test_subset_revert_supersedes_the_parent_apply_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.ledger_plan(root, count=3)
            native = _ApproveNative()
            keys = _StableKeyProvider()
            original_write = local_recovery_execution._Writer.write_field
            calls = 0

            def approved_workflow(archive_root, context, writer):
                return _execute_exact_human_approved_write_core(
                    archive_root,
                    context,
                    writer,
                    native=native,
                    key_provider=keys,
                )

            def fail_before_third_write(writer, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise RuntimeError("synthetic third-field interruption")
                original_write(writer, **kwargs)

            with mock.patch.object(
                local_recovery_execution,
                "_execute_exact_human_approved_write",
                new=approved_workflow,
            ), mock.patch.object(
                local_recovery_execution._Writer,
                "write_field",
                new=fail_before_third_write,
            ):
                interrupted = execute_local_recovery(plan)
            self.assertEqual(interrupted["applied_field_count"], 2)
            parent = load_local_recovery_plan(
                root,
                manifest_sha256=plan.manifest.manifest_sha256,
            )
            subset, inspection = build_observed_post_subset_revert_plan(parent)
            self.assertIsNotNone(subset)
            assert subset is not None
            self.assertEqual(inspection["selected_post_field_count"], 2)

            with mock.patch.object(
                local_recovery_execution,
                "_execute_exact_human_approved_write",
                new=approved_workflow,
            ):
                reverted = execute_local_recovery(subset, mode="revert")
            self.assertTrue(reverted["ok"], reverted)
            self.assertTrue(
                reverted["superseded_parent_apply_execution"]
            )
            self.assertTrue(
                verify_local_recovery_state(parent, state="pre")["all_match"]
            )
            selected, discovery = discover_local_recovery_plan(
                root,
                allowed_domains={"synthetic_ledger"},
                mode="apply",
                resume=True,
            )
            self.assertIsNone(selected)
            self.assertEqual(
                discovery["state"],
                "local_recovery_control_not_found",
            )
            with self.assertRaises(LocalRecoveryError):
                resume_local_recovery(parent, key_provider=keys)
            self.assertEqual(native.calls, 2)

            final_path = next(
                (
                    root
                    / "profiles"
                    / "local"
                    / "local-recovery"
                    / "supersessions"
                ).glob("*.final.json")
            )
            final_document = json.loads(final_path.read_text(encoding="ascii"))
            final_document["parent_pre_verification_sha256"] = (
                "sha256:" + "0" * 64
            )
            basis = dict(final_document)
            basis.pop("supersession_final_sha256")
            final_document["supersession_final_sha256"] = (
                local_recovery_execution._sha(
                    local_recovery_execution._canonical_bytes(basis)
                )
            )
            final_path.write_bytes(
                local_recovery_execution._canonical_line(final_document)
            )
            with self.assertRaises(LocalRecoveryError) as tampered_final:
                resume_local_recovery(parent, key_provider=keys)
            self.assertEqual(
                tampered_final.exception.code,
                "local_recovery_resume_invalid",
            )
            self.assertTrue(
                verify_local_recovery_state(parent, state="pre")["all_match"]
            )

    def test_completed_subset_revert_finalizes_without_replaying_fields(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.ledger_plan(root, count=3)
            native = _ApproveNative()
            keys = _StableKeyProvider()
            original_write = local_recovery_execution._Writer.write_field
            calls = 0

            def approved_workflow(archive_root, context, writer):
                return _execute_exact_human_approved_write_core(
                    archive_root,
                    context,
                    writer,
                    native=native,
                    key_provider=keys,
                )

            def fail_before_third_write(writer, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise RuntimeError("synthetic third-field interruption")
                original_write(writer, **kwargs)

            with mock.patch.object(
                local_recovery_execution,
                "_execute_exact_human_approved_write",
                new=approved_workflow,
            ), mock.patch.object(
                local_recovery_execution._Writer,
                "write_field",
                new=fail_before_third_write,
            ):
                interrupted = execute_local_recovery(plan)
            self.assertEqual(interrupted["applied_field_count"], 2)

            parent = load_local_recovery_plan(
                root,
                manifest_sha256=plan.manifest.manifest_sha256,
            )
            subset, _inspection = build_observed_post_subset_revert_plan(parent)
            self.assertIsNotNone(subset)
            assert subset is not None

            with mock.patch.object(
                local_recovery_execution,
                "_execute_exact_human_approved_write",
                new=approved_workflow,
            ), mock.patch.object(
                local_recovery_execution,
                "_persist_subset_supersession_final",
                side_effect=RuntimeError("synthetic finalizer interruption"),
            ):
                with self.assertRaises(ExactHumanApprovalWorkflowError):
                    execute_local_recovery(subset, mode="revert")

            self.assertTrue(
                verify_local_recovery_state(parent, state="pre")["all_match"]
            )
            supersessions = (
                root
                / "profiles"
                / "local"
                / "local-recovery"
                / "supersessions"
            )
            self.assertEqual(len(list(supersessions.glob("*.pending.json"))), 1)
            self.assertEqual(len(list(supersessions.glob("*.final.json"))), 0)

            receipt_path = next(
                (root / "receipts" / "ops" / "exact-operations").glob(
                    "*.json"
                )
            )
            original_receipt = receipt_path.read_bytes()
            tampered_receipt = json.loads(original_receipt.decode("ascii"))
            tampered_receipt["result"]["field_count"] += 1
            result_basis = dict(tampered_receipt["result"])
            result_basis.pop("result_sha256")
            tampered_receipt["result"]["result_sha256"] = (
                local_recovery_execution._sha(
                    local_recovery_execution._canonical_bytes(result_basis)
                )
            )
            receipt_basis = dict(tampered_receipt)
            receipt_basis.pop("receipt_sha256")
            tampered_receipt["receipt_sha256"] = (
                local_recovery_execution._sha(
                    local_recovery_execution._canonical_bytes(receipt_basis)
                )
            )
            receipt_path.write_bytes(
                local_recovery_execution._canonical_line(tampered_receipt)
            )
            selected, blocked = discover_local_recovery_plan(
                root,
                allowed_domains={"synthetic_ledger"},
                mode="revert",
                resume=True,
            )
            self.assertIsNone(selected)
            self.assertEqual(
                blocked["state"],
                "local_recovery_control_requires_review",
            )
            receipt_path.write_bytes(original_receipt)

            selected, discovery = discover_local_recovery_plan(
                root,
                allowed_domains={"synthetic_ledger"},
                mode="revert",
                resume=True,
            )
            self.assertIsNotNone(selected, discovery)
            assert selected is not None
            write_calls_before_finalize = calls
            finalized = resume_local_recovery(
                selected,
                mode="revert",
                key_provider=keys,
            )
            self.assertTrue(finalized["ok"], finalized)
            self.assertTrue(finalized["finalized_existing_receipt"])
            self.assertTrue(finalized["superseded_parent_apply_execution"])
            self.assertEqual(
                finalized["exact_human_approval"]["status"],
                "succeeded",
            )
            self.assertEqual(calls, write_calls_before_finalize)
            self.assertEqual(native.calls, 2)
            self.assertEqual(len(list(supersessions.glob("*.final.json"))), 1)
            self.assertTrue(
                verify_local_recovery_state(parent, state="pre")["all_match"]
            )

    def test_legacy_whole_body_marker_bug_has_exact_compensation_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            archive_id = archive_services.read_archive_id(root)
            relative = f"zettels/{ZETTEL_ID}.md"
            path = root.joinpath(*relative.split("/"))
            text = path.read_text(encoding="utf-8")
            match = archive_services.FRONTMATTER_RE.match(text)
            self.assertIsNotNone(match)
            assert match is not None
            prefix = text[: match.end()]
            marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
            normalized_body = (
                "[Attached objet](wom-objet:sha256:" + "a" * 64 + ")\n"
            )
            bad_legacy_body = (
                '<span style="color:red"></span>\n'
                f'<file src="{marker}"></file>\n'
            )
            path.write_text(
                prefix + bad_legacy_body,
                encoding="utf-8",
                newline="",
            )
            archive_services.index_archive(root)
            self.assertTrue(
                archive_services.require_current_zettel_index(root)["ok"]
            )
            identity = local_recovery_zettel_identity_sha256(
                archive_id,
                ZETTEL_ID,
                relative,
            )
            pre_value = local_recovery_execution._marker_projection_v1(
                normalized_body
            )
            post_value = local_recovery_execution._marker_projection_v1(
                bad_legacy_body
            )
            source = b'{"legacy":"v0.4.7"}'
            item = ExactOperationItem(
                ordinal=0,
                item_id="item:000000",
                target_kind="zettel",
                target_ref=identity,
                target_identity_sha256=identity,
                fields=(
                    ExactFieldEffect(
                        field_ref="body.source_locator_omission_markers",
                        pre_sha256=hash_field_value(pre_value),
                        post_sha256=hash_field_value(post_value),
                        source_sha256=hash_field_value(source),
                    ),
                ),
            )
            manifest = ExactOperationManifest.build(
                operation=APPLY_OPERATION,
                archive_identity_sha256=(
                    exact_human_approval_archive_identity_sha256(archive_id)
                ),
                items=(item,),
            )
            plan = build_local_recovery_plan(
                root,
                domain="synthetic_legacy_marker",
                manifest=manifest,
                specs=(
                    LocalRecoveryFieldSpec(
                        item_id=item.item_id,
                        target_kind=item.target_kind,
                        target_ref=item.target_ref,
                        target_identity_sha256=item.target_identity_sha256,
                        field_ref=item.fields[0].field_ref,
                        target_relative=relative,
                        zettel_id=ZETTEL_ID,
                        pre_value=pre_value,
                        post_value=post_value,
                        source_value=source,
                        marker_pre_body=normalized_body,
                        marker_post_body=bad_legacy_body,
                    ),
                ),
            )
            persist_local_recovery_control(plan)
            loaded = load_local_recovery_plan(
                root,
                manifest_sha256=plan.manifest.manifest_sha256,
            )
            subset, inspection = build_observed_post_subset_revert_plan(loaded)
            self.assertEqual(inspection["selected_post_field_count"], 1)
            self.assertIsNotNone(subset)
            assert subset is not None
            reverted = self.execute(subset, mode="revert")
            self.assertTrue(reverted["ok"], reverted)
            _frontmatter, final_body = (
                archive_services.require_readable_zettel_content(path)
            )
            self.assertEqual(final_body, normalized_body)

    def test_marker_transform_changes_only_the_exact_marker_position_set(self) -> None:
        marker = archive_services.NOTION_IMPORT_LOCATOR_OMISSION_MARKER
        plain = "alpha\nbeta\ngamma\n"
        source = "alpha" + marker + "\nbeta\ngamma\n"
        destination = (
            "alpha"
            + marker
            + "\nbeta"
            + marker
            + "\ngamma\n"
        )

        applied = local_recovery_execution._marker_transform(
            source,
            source,
            destination,
        )
        self.assertEqual(applied, destination)
        self.assertEqual(applied.replace(marker, ""), plain)

        reverted = local_recovery_execution._marker_transform(
            applied,
            destination,
            source,
        )
        self.assertEqual(reverted, source)
        self.assertEqual(reverted.replace(marker, ""), plain)

    def test_native_approval_occurs_once_and_authenticated_resume_reuses_it(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.archive(Path(tmp))
            plan = self.title_plan(root)
            native = _ApproveNative()
            keys = _StableKeyProvider()
            original_write = local_recovery_execution._Writer.write_field

            def approved_workflow(archive_root, context, writer):
                return _execute_exact_human_approved_write_core(
                    archive_root,
                    context,
                    writer,
                    native=native,
                    key_provider=keys,
                )

            def crash_after_write(writer, **kwargs):
                original_write(writer, **kwargs)
                raise RuntimeError("synthetic power interruption")

            with mock.patch.object(
                local_recovery_execution,
                "_execute_exact_human_approved_write",
                new=approved_workflow,
            ), mock.patch.object(
                local_recovery_execution._Writer,
                "write_field",
                new=crash_after_write,
            ):
                interrupted = execute_local_recovery(plan)
            self.assertFalse(interrupted["ok"], interrupted)
            self.assertEqual(interrupted["applied_field_count"], 1)
            self.assertTrue(interrupted["resume_supported"])
            self.assertTrue(
                interrupted["exact_human_approval_reconciliation"]["required"]
            )
            self.assertEqual(native.calls, 1)

            loaded, discovery = discover_local_recovery_plan(
                root,
                allowed_domains={"synthetic_title"},
                mode="apply",
                resume=True,
            )
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(
                discovery["state"],
                "local_recovery_control_selected",
            )
            resumed = resume_local_recovery(loaded, key_provider=keys)
            self.assertTrue(resumed["ok"], resumed)
            self.assertEqual(resumed["resumed_field_count"], 1)
            self.assertFalse(resumed["native_approval_redisplayed"])
            self.assertEqual(native.calls, 1)
            self.assertEqual(keys.create_if_missing, [True, False])
            self.assertTrue(
                verify_local_recovery_state(loaded, state="post")["all_match"]
            )

    def test_control_rejects_archive_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            first = self.archive(parent / "first")
            second = self.archive(parent / "second")
            plan = self.title_plan(first)
            relative = persist_local_recovery_control(plan)
            target = second.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(first.joinpath(*relative.split("/")).read_bytes())
            marker = second / "archive.yml"
            marker.write_text(
                marker.read_text(encoding="utf-8").replace(
                    archive_services.read_archive_id(second),
                    "different-archive",
                    1,
                ),
                encoding="utf-8",
            )
            with self.assertRaises(Exception):
                load_local_recovery_plan(
                    second,
                    manifest_sha256=plan.manifest.manifest_sha256,
                )


if __name__ == "__main__":
    unittest.main()
