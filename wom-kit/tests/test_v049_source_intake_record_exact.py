from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import contextmanager, nullcontext, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable
from unittest import mock

from wom_kit import (
    archive_cli,
    archive_services,
    objet_capture_selection_exact,
    source_intake_record_exact,
)
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID
from wom_kit.exact_human_approval_workflow import (
    _execute_exact_human_approved_write_core,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
REVIEWER = "person:v049-source-intake-reviewer"
PRIVATE_NAME = "private-letter147-source.md"
PRIVATE_BODY = "PRIVATE_LETTER147_BODY"


class _Native:
    def __init__(self, *, approved: bool) -> None:
        self.approved = approved
        self.calls = 0

    def show(self, **_kwargs: str) -> tuple[int, bool]:
        self.calls += 1
        return (
            (APPROVE_BUTTON_ID, True)
            if self.approved
            else (2, False)
        )


class _KeyProvider:
    def __init__(self) -> None:
        self.calls = 0

    def use_key(
        self,
        _root: Path | str,
        consumer: Callable[[memoryview], Any],
        *,
        create_if_missing: bool = False,
    ) -> Any:
        if create_if_missing is not True:
            raise AssertionError("exact approval must request one usable key")
        self.calls += 1
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class SourceIntakeRecordExactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.root = self.workspace / "archive"
        shutil.copytree(
            KIT_ROOT / "examples" / "fake-life-archive",
            self.root,
        )
        self.staged_relative = f"staging/incoming/{PRIVATE_NAME}"
        self.selected = self.root / Path(self.staged_relative)
        self.selected.parent.mkdir(parents=True, exist_ok=True)
        self.selected.write_text(PRIVATE_BODY, encoding="utf-8")
        self.source_document = archive_services.source_intake_plan(
            self.root,
            local_path=self.selected,
            redact_local_paths=True,
        )
        self.assertTrue(self.source_document["ok"], self.source_document)
        self.plan_path = self.workspace / "source-intake-plan.json"
        self._write_document(self.source_document, self.plan_path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _write_document(document: dict[str, Any], path: Path) -> None:
        path.write_text(
            json.dumps(document, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _snapshot(root: Path) -> dict[str, bytes]:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    @staticmethod
    def _run_cli(values: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = archive_cli.main(values)
        return int(code), stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def _workflow(native: _Native, key_provider: _KeyProvider):
        def execute(root, context, writer):
            return _execute_exact_human_approved_write_core(
                root,
                context,
                writer,
                native=native,
                key_provider=key_provider,
            )

        return execute

    def _plan(self):
        return source_intake_record_exact.plan_source_intake_record(
            self.root,
            self.plan_path,
        )

    def _cli_values(self, mode: str, *extra: str) -> list[str]:
        return [
            "source-intake-record",
            str(self.root),
            "--source-intake-plan",
            str(self.plan_path),
            mode,
            *extra,
            "--format",
            "json",
        ]

    def _assert_content_free(
        self,
        rendered: str,
        *,
        extra: tuple[str, ...] = (),
    ) -> None:
        forbidden = (
            str(self.root),
            str(self.plan_path),
            str(self.selected),
            self.staged_relative,
            PRIVATE_NAME,
            PRIVATE_BODY,
            *extra,
        )
        for value in forbidden:
            variants = {
                value,
                value.replace("\\", "/"),
                value.replace("\\", "\\\\"),
            }
            for variant in variants:
                self.assertNotIn(variant, rendered)

    def test_generated_local_path_plan_dry_run_is_stable_and_writes_nothing(
        self,
    ) -> None:
        before = self._snapshot(self.root)
        first = self._plan()
        second = self._plan()

        self.assertTrue(first.approveable, first.public_document())
        self.assertEqual(
            first.manifest.manifest_sha256,
            second.manifest.manifest_sha256,
        )
        self.assertEqual(first.receipt_bytes, second.receipt_bytes)
        self.assertEqual(first.manifest.operation, "source_intake_record")
        public = first.public_document()
        self.assertEqual(public["state"], "ready_for_exact_human_approval")
        self.assertEqual(public["receipt_create_count"], 1)
        self.assertTrue(public["general_intake_chain_complete_after_approval"])
        self.assertFalse(public["writes_performed"])
        self._assert_content_free(json.dumps(public, sort_keys=True))

        first_code, first_stdout, first_stderr = self._run_cli(
            self._cli_values("--dry-run")
        )
        second_code, second_stdout, second_stderr = self._run_cli(
            self._cli_values("--dry-run")
        )
        self.assertEqual((first_code, second_code), (0, 0))
        self.assertEqual(first_stderr + second_stderr, "")
        first_result = json.loads(first_stdout)
        second_result = json.loads(second_stdout)
        self.assertEqual(
            first_result["plan_sha256"],
            second_result["plan_sha256"],
        )
        self.assertEqual(
            first_result["plan_sha256"],
            first.manifest.manifest_sha256,
        )
        self._assert_content_free(first_stdout + second_stdout)
        self.assertEqual(self._snapshot(self.root), before)

    def test_unknown_body_duplicate_nonfinite_depth_and_oversize_are_blocked(
        self,
    ) -> None:
        canonical = json.dumps(
            self.source_document,
            ensure_ascii=False,
        ).encode("utf-8")

        unknown_body = json.loads(canonical)
        unknown_body["body"] = PRIVATE_BODY

        nonfinite = json.loads(canonical)
        nonfinite["profile_id"] = float("nan")

        nested: Any = "leaf"
        for _ in range(18):
            nested = [nested]
        excessive_depth = json.loads(canonical)
        excessive_depth["profile_id"] = nested

        cases = {
            "unknown-body": json.dumps(
                unknown_body,
                ensure_ascii=False,
            ).encode("utf-8"),
            "duplicate-member": b'{"ok":false,' + canonical[1:],
            "nonfinite-number": json.dumps(
                nonfinite,
                ensure_ascii=False,
            ).encode("utf-8"),
            "excessive-depth": json.dumps(
                excessive_depth,
                ensure_ascii=False,
            ).encode("utf-8"),
            "oversize": b" " * (8 * 1024 * 1024 + 1),
        }

        before = self._snapshot(self.root)
        for name, raw in cases.items():
            with self.subTest(name=name):
                path = self.workspace / f"{name}.json"
                path.write_bytes(raw)
                blocked = source_intake_record_exact.plan_source_intake_record(
                    self.root,
                    path,
                )
                self.assertFalse(blocked.approveable)
                self.assertEqual(
                    blocked.blockers,
                    ("source_intake_record_plan_invalid",),
                )
                self.assertIsNone(blocked.receipt_relative_path)
                self.assertIsNone(blocked.receipt_bytes)
                public = json.dumps(blocked.public_document(), sort_keys=True)
                self._assert_content_free(public, extra=(str(path),))

                code, stdout, stderr = self._run_cli(
                    [
                        "source-intake-record",
                        str(self.root),
                        "--source-intake-plan",
                        str(path),
                        "--dry-run",
                        "--format",
                        "json",
                    ]
                )
                self.assertEqual(code, 1, stderr)
                result = json.loads(stdout)
                self.assertEqual(
                    result["blockers"],
                    ["source_intake_record_plan_invalid"],
                )
                self._assert_content_free(stdout, extra=(str(path),))
                self.assertEqual(stderr, "")
        self.assertEqual(self._snapshot(self.root), before)

    def test_symlinked_plan_is_blocked_without_following_it(self) -> None:
        link = self.workspace / "linked-source-intake-plan.json"
        try:
            os.symlink(self.plan_path, link)
            link_guard = nullcontext()
        except OSError:
            # Some Windows hosts disable unprivileged symlink creation.  Keep
            # the reparse-point refusal covered there by making the platform
            # result deterministic at the guard boundary.
            link = self.plan_path
            link_guard = mock.patch.object(
                source_intake_record_exact,
                "_is_link_or_reparse",
                return_value=True,
            )

        before = self._snapshot(self.root)
        with link_guard:
            blocked = source_intake_record_exact.plan_source_intake_record(
                self.root,
                link,
            )
            self.assertFalse(blocked.approveable)
            self.assertEqual(
                blocked.blockers,
                ("source_intake_record_plan_invalid",),
            )
            code, stdout, stderr = self._run_cli(
                [
                    "source-intake-record",
                    str(self.root),
                    "--source-intake-plan",
                    str(link),
                    "--dry-run",
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 1, stderr)
        self.assertEqual(
            json.loads(stdout)["blockers"],
            ["source_intake_record_plan_invalid"],
        )
        self._assert_content_free(stdout, extra=(str(link),))
        self.assertEqual(self._snapshot(self.root), before)

    def test_native_approval_writes_once_and_unverified_replay_fails_closed(self) -> None:
        plan = self._plan()
        target = self.root / Path(plan.receipt_relative_path)
        native = _Native(approved=True)
        key_provider = _KeyProvider()
        context = source_intake_record_exact.approval_context(
            plan,
            reviewer_claim=REVIEWER,
        )
        self.assertEqual(context.operation.value, "source_intake_record")

        with mock.patch.object(
            source_intake_record_exact,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, key_provider),
        ):
            first_code, first_stdout, first_stderr = self._run_cli(
                self._cli_values(
                    "--approve",
                    "--reviewed-by",
                    REVIEWER,
                )
            )

            self.assertEqual(first_code, 0, first_stderr)
            first = json.loads(first_stdout)
            self.assertTrue(first["ok"], first)
            self.assertEqual(first["state"], "source_intake_recorded")
            self.assertEqual(first["receipt_create_count"], 1)
            self.assertTrue(first["general_intake_chain_complete"])
            self.assertTrue(first["writes_performed"])
            self.assertEqual(first["exact_human_approval"]["status"], "succeeded")
            self.assertEqual(native.calls, 1)
            self.assertEqual(key_provider.calls, 1)
            self.assertEqual(target.read_bytes(), plan.receipt_bytes)
            self.assertEqual(
                json.loads(target.read_text(encoding="utf-8")),
                self.source_document,
            )
            self.assertTrue(
                list(
                    (
                        self.root
                        / "profiles"
                        / "local"
                        / "exact-operations"
                        / "checkpoints"
                    ).glob("*.jsonl")
                )
            )
            self.assertTrue(
                list(
                    (
                        self.root
                        / "receipts"
                        / "ops"
                        / "exact-operations"
                    ).glob("*.json")
                )
            )

            after_first = self._snapshot(self.root)
            replay_code, replay_stdout, replay_stderr = self._run_cli(
                self._cli_values(
                    "--approve",
                    "--reviewed-by",
                    REVIEWER,
                )
            )

        self.assertEqual(replay_code, 1, replay_stderr)
        replay = json.loads(replay_stdout)
        self.assertEqual(replay["state"], "preexisting_unverified")
        self.assertEqual(
            replay["blockers"],
            ["source_intake_record_completion_evidence_required"],
        )
        self.assertFalse(replay["general_intake_chain_complete"])
        self.assertFalse(replay["writes_performed"])
        self.assertEqual(native.calls, 1)
        self.assertEqual(key_provider.calls, 1)
        self.assertEqual(self._snapshot(self.root), after_first)

        downstream = (
            objet_capture_selection_exact.plan_existing_intake_capture_selection(
                self.root,
                staged_path=self.staged_relative,
                source_intake_receipt=plan.receipt_relative_path,
            )
        )
        self.assertTrue(downstream.approveable, downstream.public_document())
        self._assert_content_free(first_stdout + replay_stdout)

    def test_semantically_equal_nonexact_target_bytes_are_a_collision(self) -> None:
        plan = self._plan()
        assert plan.receipt_relative_path is not None
        assert plan.receipt_bytes is not None
        target = self.root.joinpath(*plan.receipt_relative_path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        alternate = json.dumps(
            json.loads(plan.receipt_bytes),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertNotEqual(alternate, plan.receipt_bytes)
        target.write_bytes(alternate)

        replanned = self._plan()

        self.assertFalse(replanned.approveable)
        self.assertEqual(replanned.state, "target_collision")
        self.assertEqual(
            replanned.blockers,
            ("source_intake_record_target_collision",),
        )
        self.assertEqual(target.read_bytes(), alternate)

    def test_preexisting_exact_plan_requires_evidence_and_revalidates_target(self) -> None:
        ready = self._plan()
        assert ready.receipt_relative_path is not None
        assert ready.receipt_bytes is not None
        target = self.root.joinpath(*ready.receipt_relative_path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(ready.receipt_bytes)
        recorded = self._plan()
        self.assertTrue(recorded.preexisting_unverified)
        self.assertIsNotNone(recorded.manifest)

        wrong_digest = "sha256:" + "0" * 64
        with self.assertRaises(
            source_intake_record_exact.SourceIntakeRecordExactError
        ) as digest_error:
            source_intake_record_exact.execute_source_intake_record(
                recorded,
                expected_plan_sha256=wrong_digest,
                reviewer_claim=REVIEWER,
            )
        self.assertEqual(
            digest_error.exception.code,
            "source_intake_record_plan_digest_mismatch",
        )

        changed = b"changed-after-already-recorded-plan"
        target.write_bytes(changed)

        with self.assertRaises(
            source_intake_record_exact.SourceIntakeRecordExactError
        ) as raised:
            source_intake_record_exact.execute_source_intake_record(
                recorded,
                reviewer_claim=REVIEWER,
            )

        self.assertEqual(
            raised.exception.code,
            "source_intake_record_target_collision",
        )
        self.assertEqual(target.read_bytes(), changed)

    def test_exact_existing_receipt_under_linked_chain_is_not_replayed(self) -> None:
        plan = self._plan()
        assert plan.receipt_relative_path is not None
        assert plan.receipt_bytes is not None
        relative = Path(plan.receipt_relative_path)
        linked_parent = self.root / relative.parent
        linked_target = self.root / "receipt-link-target"
        linked_target.mkdir(parents=True, exist_ok=True)
        linked_receipt = linked_target / relative.name
        linked_receipt.write_bytes(plan.receipt_bytes)
        linked_parent.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(linked_target, linked_parent, target_is_directory=True)
            chain_guard = nullcontext()
        except OSError:
            linked_parent.mkdir(parents=True, exist_ok=True)
            (linked_parent / relative.name).write_bytes(plan.receipt_bytes)
            chain_guard = mock.patch.object(
                archive_services,
                "objet_capture_path_chain_blockers",
                return_value=["symlink_not_allowed"],
            )

        with chain_guard:
            blocked = self._plan()

        self.assertFalse(blocked.approveable)
        self.assertNotEqual(blocked.state, "already_recorded")
        self.assertEqual(
            blocked.blockers,
            ("source_intake_record_target_unsafe",),
        )

    def test_cancel_has_zero_filesystem_effects(self) -> None:
        plan = self._plan()
        before = self._snapshot(self.root)
        native = _Native(approved=False)
        key_provider = _KeyProvider()
        with mock.patch.object(
            source_intake_record_exact,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, key_provider),
        ):
            code, stdout, stderr = self._run_cli(
                self._cli_values(
                    "--approve",
                    "--reviewed-by",
                    REVIEWER,
                )
            )

        self.assertEqual(code, 1, stderr)
        result = json.loads(stdout)
        self.assertEqual(result["blockers"], ["exact_human_approval_cancelled"])
        self.assertEqual(native.calls, 1)
        self.assertEqual(key_provider.calls, 0)
        self.assertFalse((self.root / Path(plan.receipt_relative_path)).exists())
        self.assertEqual(self._snapshot(self.root), before)
        self._assert_content_free(stdout)

    def test_expected_digest_mismatch_fails_before_native_approval(self) -> None:
        plan = self._plan()
        before = self._snapshot(self.root)
        native = _Native(approved=True)
        key_provider = _KeyProvider()
        wrong_digest = "sha256:" + "0" * 64
        self.assertNotEqual(wrong_digest, plan.manifest.manifest_sha256)

        with mock.patch.object(
            source_intake_record_exact,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, key_provider),
        ):
            code, stdout, stderr = self._run_cli(
                self._cli_values(
                    "--approve",
                    "--expected-plan-sha256",
                    wrong_digest,
                    "--reviewed-by",
                    REVIEWER,
                )
            )

        self.assertEqual(code, 1, stderr)
        self.assertEqual(
            json.loads(stdout)["blockers"],
            ["source_intake_record_plan_digest_mismatch"],
        )
        self.assertEqual(native.calls, 0)
        self.assertEqual(key_provider.calls, 0)
        self.assertEqual(self._snapshot(self.root), before)
        self._assert_content_free(stdout, extra=(wrong_digest,))

    def test_post_approval_plan_drift_is_detected_before_receipt_write(self) -> None:
        plan = self._plan()
        native = _Native(approved=True)
        key_provider = _KeyProvider()
        observed_domain_errors: list[str] = []
        original_execute_core = source_intake_record_exact._execute_core

        drifted_document = json.loads(json.dumps(self.source_document))
        drifted_document["warnings"] = [
            *drifted_document["warnings"],
            "drifted-after-native-review",
        ]

        def observed_execute_core(*args, **kwargs):
            try:
                return original_execute_core(*args, **kwargs)
            except source_intake_record_exact.SourceIntakeRecordExactError as error:
                observed_domain_errors.append(error.code)
                raise

        def drifting_workflow(root, context, writer):
            @contextmanager
            def mutate_after_native_decision():
                self._write_document(drifted_document, self.plan_path)
                yield None

            return _execute_exact_human_approved_write_core(
                root,
                context,
                writer,
                native=native,
                key_provider=key_provider,
                post_decision_boundary=mutate_after_native_decision,
            )

        with (
            mock.patch.object(
                source_intake_record_exact,
                "_execute_exact_human_approved_write",
                side_effect=drifting_workflow,
            ),
            mock.patch.object(
                source_intake_record_exact,
                "_execute_core",
                side_effect=observed_execute_core,
            ),
        ):
            code, stdout, stderr = self._run_cli(
                self._cli_values(
                    "--approve",
                    "--reviewed-by",
                    REVIEWER,
                )
            )

        self.assertEqual(code, 1, stderr)
        self.assertEqual(
            observed_domain_errors,
            ["source_intake_record_state_drifted"],
        )
        self.assertEqual(
            json.loads(stdout)["blockers"],
            ["source_intake_record_write_failed"],
        )
        self.assertEqual(native.calls, 1)
        self.assertEqual(key_provider.calls, 1)
        self.assertFalse((self.root / Path(plan.receipt_relative_path)).exists())
        self._assert_content_free(stdout, extra=("drifted-after-native-review",))

    def test_collision_is_blocked_and_exact_postimage_is_reconciled(self) -> None:
        original = self._plan()
        target = self.root / Path(original.receipt_relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        collision_bytes = b"PRIVATE_UNRELATED_COLLISION_147"
        target.write_bytes(collision_bytes)

        collision = self._plan()
        self.assertFalse(collision.approveable)
        self.assertEqual(collision.state, "target_collision")
        self.assertEqual(
            collision.blockers,
            ("source_intake_record_target_collision",),
        )
        code, stdout, stderr = self._run_cli(self._cli_values("--dry-run"))
        self.assertEqual(code, 1, stderr)
        result = json.loads(stdout)
        self.assertEqual(result["state"], "target_collision")
        self.assertEqual(
            result["blockers"],
            ["source_intake_record_target_collision"],
        )
        self.assertEqual(target.read_bytes(), collision_bytes)
        self._assert_content_free(
            stdout,
            extra=(collision_bytes.decode("ascii"),),
        )

        target.write_bytes(original.receipt_bytes)
        reconciled = self._plan()
        self.assertTrue(reconciled.preexisting_unverified)
        self.assertFalse(reconciled.approveable)
        self.assertEqual(reconciled.state, "preexisting_unverified")
        self.assertIsNotNone(reconciled.manifest)
        self.assertEqual(
            reconciled.blockers,
            ("source_intake_record_completion_evidence_required",),
        )
        self.assertFalse(reconciled.public_document()["ok"])
        self._assert_content_free(
            json.dumps(reconciled.public_document(), sort_keys=True)
        )


if __name__ == "__main__":
    unittest.main()
