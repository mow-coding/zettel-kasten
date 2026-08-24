from __future__ import annotations

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
    LocalRecoveryFieldSpec,
    _run_with_store,
    build_local_recovery_plan,
    execute_local_recovery,
    load_local_recovery_plan,
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
                with self.assertRaises(Exception):
                    self.execute(plan, mode="apply")

            resumed = self.execute(plan, mode="apply", resume=True)
            self.assertTrue(resumed["ok"], resumed)
            self.assertEqual(resumed["written_field_count"], 0)
            self.assertEqual(resumed["resumed_field_count"], 1)
            self.assertTrue(
                verify_local_recovery_state(plan, state="post")["all_match"]
            )

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
                with self.assertRaises(ExactHumanApprovalWorkflowError) as caught:
                    execute_local_recovery(plan)
            self.assertEqual(
                caught.exception.code,
                "exact_human_approval_state_unknown",
            )
            self.assertEqual(native.calls, 1)

            loaded = load_local_recovery_plan(
                root,
                manifest_sha256=plan.manifest.manifest_sha256,
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
