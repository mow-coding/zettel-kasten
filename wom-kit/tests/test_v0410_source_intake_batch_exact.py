from __future__ import annotations

import hashlib
import json
import io
import shutil
import os
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable
from unittest import mock

from wom_kit import (
    archive_cli,
    archive_services,
    exact_human_approval,
    exact_operation_manifest,
    source_intake_batch_exact,
)
from wom_kit.exact_human_approval_windows import (
    APPROVE_BUTTON_ID,
    ExactHumanApprovalOperation,
)
from wom_kit.exact_human_approval_workflow import (
    ExactHumanApprovalWorkflowError,
    _execute_exact_human_approved_write_core,
)


KIT_ROOT = Path(__file__).resolve().parents[1]
REVIEWER = "person:v0410-batch-reviewer"


class _Native:
    def __init__(self) -> None:
        self.calls = 0

    def show(self, **_kwargs: str) -> tuple[int, bool]:
        self.calls += 1
        return APPROVE_BUTTON_ID, True


class _KeyProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.create_if_missing_calls: list[bool] = []

    def use_key(
        self,
        _root: Path | str,
        consumer: Callable[[memoryview], Any],
        *,
        create_if_missing: bool = False,
    ) -> Any:
        self.calls += 1
        self.create_if_missing_calls.append(create_if_missing)
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


class SourceIntakeBatchExactTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.root = self.workspace / "archive"
        shutil.copytree(KIT_ROOT / "examples" / "fake-life-archive", self.root)
        self.request_path = self.workspace / "batch-request.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_request(self, count: int) -> list[Path]:
        sources: list[Path] = []
        items: list[dict[str, Any]] = []
        for index in range(count):
            relative = f"staging/incoming/source-{index + 1}.bin"
            source = self.root / Path(relative)
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes((f"source-body-{index + 1}\n").encode("utf-8"))
            sources.append(source)
            items.append(
                {
                    "item_id": f"source-{index + 1}",
                    "local_path": relative,
                    "source_role": "primary_source",
                }
            )
        self.request_path.write_text(
            json.dumps(
                {
                    "schema": "wom-kit/source-intake-batch-request/v0.1",
                    "batch_id": f"batch-{count}",
                    "items": items,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return sources

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

    @staticmethod
    def _canonical_exact_bytes(value: Any) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")

    @classmethod
    def _exact_document_sha256(cls, value: Any) -> str:
        return "sha256:" + hashlib.sha256(
            cls._canonical_exact_bytes(value)
        ).hexdigest()

    def _final_receipt_path(self, execution_sha256: str) -> Path:
        return (
            self.root
            / "receipts"
            / "ops"
            / "exact-operations"
            / (execution_sha256.removeprefix("sha256:") + ".json")
        )

    def _checkpoint_path(self, execution_sha256: str) -> Path:
        return (
            self.root
            / "profiles"
            / "local"
            / "exact-operations"
            / "checkpoints"
            / (execution_sha256.removeprefix("sha256:") + ".jsonl")
        )

    def _claim_path(self, final: dict[str, Any]) -> Path:
        approval_id = final["result"]["completion_authentication"][
            "approval_reference"
        ]["approval_id"]
        return (
            self.root
            / "profiles"
            / "local"
            / "exact-human-approvals"
            / "claims"
            / f"{approval_id}.json"
        )

    def _execute_completed_batch(
        self,
        *,
        count: int = 1,
    ) -> tuple[Any, dict[str, Any], _KeyProvider]:
        self._write_request(count)
        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        native = _Native()
        key_provider = _KeyProvider()
        with mock.patch.object(
            source_intake_batch_exact,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, key_provider),
        ):
            result = source_intake_batch_exact.execute_source_intake_batch(
                plan,
                expected_plan_sha256=plan.manifest.manifest_sha256,
                reviewer_claim=REVIEWER,
            )
        self.assertTrue(result["ok"], result)
        replay = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        return replay, result, key_provider

    def _create_interrupted_batch(
        self,
        *,
        count: int = 3,
        fail_on_write: int = 2,
        key_provider: _KeyProvider | None = None,
    ) -> tuple[Any, _KeyProvider]:
        self._write_request(count)
        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        native = _Native()
        selected_key_provider = key_provider or _KeyProvider()
        original_write = source_intake_batch_exact._Writer.write_field
        calls = 0

        def interrupt(writer, **kwargs):
            nonlocal calls
            calls += 1
            if calls == fail_on_write:
                raise RuntimeError("bounded-test-interruption")
            return original_write(writer, **kwargs)

        with (
            mock.patch.object(
                source_intake_batch_exact,
                "_execute_exact_human_approved_write",
                side_effect=self._workflow(native, selected_key_provider),
            ),
            mock.patch.object(
                source_intake_batch_exact._Writer,
                "write_field",
                new=interrupt,
            ),
        ):
            with self.assertRaises(ExactHumanApprovalWorkflowError) as raised:
                source_intake_batch_exact.execute_source_intake_batch(
                    plan,
                    expected_plan_sha256=plan.manifest.manifest_sha256,
                    reviewer_claim=REVIEWER,
                )
        self.assertEqual(raised.exception.code, "exact_human_approval_state_unknown")
        return (
            source_intake_batch_exact.plan_source_intake_batch(
                self.root,
                self.request_path,
            ),
            selected_key_provider,
        )

    def test_one_and_three_item_plans_bind_every_exact_receipt(self) -> None:
        for count in (1, 3):
            with self.subTest(count=count):
                self._write_request(count)
                plan = source_intake_batch_exact.plan_source_intake_batch(
                    self.root,
                    self.request_path,
                )

                self.assertTrue(plan.approveable, plan.public_document())
                self.assertEqual(len(plan.items), count)
                self.assertEqual(len(plan.manifest.items), count + 1)
                self.assertEqual(plan.manifest.operation, "source_intake_batch")
                self.assertIs(
                    source_intake_batch_exact.approval_context(
                        plan,
                        reviewer_claim=REVIEWER,
                    ).operation,
                    ExactHumanApprovalOperation.source_intake_batch,
                )
                self.assertIsNotNone(plan.prepared_capture_request)
                self.assertEqual(
                    plan.public_document()["ready_to_create_count"],
                    count,
                )
                self.assertIs(
                    plan.public_document()[
                        "credential_material_used_for_local_authentication"
                    ],
                    False,
                )
                self.assertIs(
                    plan.public_document()["credential_values_echoed"],
                    False,
                )
                self.assertNotIn("credential_values_read", plan.public_document())
                self.assertTrue(
                    all(item.source_bytes_sha256.startswith("sha256:") for item in plan.items)
                )
                self.assertTrue(
                    all(item.target_state == "ready_to_create" for item in plan.items)
                )
                rendered = json.dumps(plan.public_document(), sort_keys=True)
                self.assertNotIn(str(self.root), rendered)
                self.assertNotIn("staging/incoming", rendered)
                for item in plan.items:
                    self.assertFalse(
                        self.root.joinpath(*item.receipt_relative_path.split("/")).exists()
                    )
                prepared = plan.prepared_capture_request
                self.assertFalse(
                    self.root.joinpath(*prepared.relative_path.split("/")).exists()
                )

                # Reset targets/sources between subtests without touching the
                # copied archive fixture.
                if count == 1:
                    shutil.rmtree(self.root / "staging")

    def test_external_source_without_generated_capture_request_is_blocked(self) -> None:
        external = self.workspace / "external-source.bin"
        external.write_bytes(b"external-source-body\n")
        self.request_path.write_text(
            json.dumps(
                {
                    "schema": "wom-kit/source-intake-batch-request/v0.1",
                    "batch_id": "external-source",
                    "items": [
                        {
                            "item_id": "external-source",
                            "local_path": str(external),
                            "source_role": "primary_source",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        public = plan.public_document()
        self.assertFalse(plan.approveable)
        self.assertIsNone(plan.manifest)
        self.assertIsNone(plan.prepared_capture_request)
        self.assertEqual(
            plan.blockers,
            ("source_intake_batch_capture_request_required",),
        )
        self.assertEqual(
            public["prepared_capture_request"],
            {
                "ready": False,
                "reason_code": "capture_sources_must_be_archive_relative",
            },
        )
        self.assertTrue(public["source_bytes_hashed"])
        self.assertFalse(public["source_bytes_retained"])
        self.assertFalse(any(self.root.glob("receipts/sources/*.json")))

    def test_source_drift_after_native_decision_fails_before_any_receipt(self) -> None:
        sources = self._write_request(1)
        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        native = _Native()
        key_provider = _KeyProvider()

        def workflow(root, context, writer):
            @contextmanager
            def mutate_after_decision():
                sources[0].write_bytes(b"source-swapped-after-review\n")
                yield None

            return _execute_exact_human_approved_write_core(
                root,
                context,
                writer,
                native=native,
                key_provider=key_provider,
                post_decision_boundary=mutate_after_decision,
            )

        with mock.patch.object(
            source_intake_batch_exact,
            "_execute_exact_human_approved_write",
            side_effect=workflow,
        ):
            with self.assertRaises(ExactHumanApprovalWorkflowError) as raised:
                source_intake_batch_exact.execute_source_intake_batch(
                    plan,
                    reviewer_claim=REVIEWER,
                )

        self.assertEqual(raised.exception.code, "exact_human_approval_state_unknown")
        self.assertEqual(native.calls, 1)
        self.assertFalse(
            self.root.joinpath(*plan.items[0].receipt_relative_path.split("/")).exists()
        )

    def test_bound_receipt_parent_cannot_be_swapped_into_an_attacker_directory(
        self,
    ) -> None:
        self._write_request(1)
        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        target = self.root.joinpath(
            *plan.items[0].receipt_relative_path.split("/")
        )
        moved_parent = target.parent.with_name(target.parent.name + "-moved")
        original_write = archive_services._write_activity_group_bytes_new_file_bound
        swap_attempted = False
        swap_blocked = False

        def attempt_parent_swap(binding, path, raw, *, heartbeat=None):
            nonlocal swap_attempted, swap_blocked
            if not swap_attempted:
                swap_attempted = True
                try:
                    path.parent.rename(moved_parent)
                except OSError:
                    # Windows holds every ancestor without delete sharing.
                    swap_blocked = True
                else:
                    # POSIX keeps writing through the already-bound directory
                    # descriptor; this new path is the attacker's replacement.
                    path.parent.mkdir()
            return original_write(
                binding,
                path,
                raw,
                heartbeat=heartbeat,
            )

        native = _Native()
        key_provider = _KeyProvider()
        with (
            mock.patch.object(
                source_intake_batch_exact,
                "_execute_exact_human_approved_write",
                side_effect=self._workflow(native, key_provider),
            ),
            mock.patch.object(
                archive_services,
                "_write_activity_group_bytes_new_file_bound",
                side_effect=attempt_parent_swap,
            ),
        ):
            if os.name == "nt":
                result = source_intake_batch_exact.execute_source_intake_batch(
                    plan,
                    expected_plan_sha256=plan.manifest.manifest_sha256,
                    reviewer_claim=REVIEWER,
                )
                self.assertTrue(result["ok"], result)
            else:
                with self.assertRaises(ExactHumanApprovalWorkflowError) as raised:
                    source_intake_batch_exact.execute_source_intake_batch(
                        plan,
                        expected_plan_sha256=plan.manifest.manifest_sha256,
                        reviewer_claim=REVIEWER,
                    )
                self.assertEqual(
                    raised.exception.code,
                    "exact_human_approval_state_unknown",
                )

        self.assertTrue(swap_attempted)
        if os.name == "nt":
            self.assertTrue(swap_blocked)
            self.assertEqual(target.read_bytes(), plan.items[0].receipt_bytes)
            self.assertFalse(moved_parent.exists())
        else:
            self.assertFalse(swap_blocked)
            self.assertFalse(target.exists())
            self.assertEqual(
                (moved_parent / target.name).read_bytes(),
                plan.items[0].receipt_bytes,
            )

    @unittest.skipIf(os.name == "nt", "directory symlink privilege is not portable")
    def test_prebind_receipt_parent_symlink_is_rejected(self) -> None:
        self._write_request(1)
        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        target = self.root.joinpath(*plan.items[0].receipt_relative_path.split("/"))
        attacker = self.root / "receipts" / "ops" / "attacker"
        attacker.mkdir(parents=True)
        target.parent.parent.mkdir(parents=True, exist_ok=True)
        self.assertFalse(target.parent.exists())
        os.symlink(attacker, target.parent, target_is_directory=True)

        writer = source_intake_batch_exact._Writer(
            plan,
            request_items=source_intake_batch_exact._request_items(plan),
        )
        with self.assertRaises(source_intake_batch_exact.SourceIntakeBatchExactError):
            writer.write_field(
                target_kind=source_intake_batch_exact.TARGET_KIND,
                target_ref=plan.items[0].receipt_relative_path,
                field_ref=source_intake_batch_exact.FIELD_REF,
                value=plan.items[0].receipt_bytes,
                heartbeat=lambda: None,
            )
        self.assertFalse((attacker / target.name).exists())

    def test_failure_document_is_truthful_about_uncertain_writes(self) -> None:
        uncertain = source_intake_batch_exact.failure_document(
            "exact_human_approval_state_unknown"
        )
        self.assertTrue(uncertain["writes_may_have_occurred"])
        self.assertTrue(uncertain["outcome_unverified"])
        self.assertEqual(uncertain["safe_recovery_actions"], ["reconcile", "resume"])
        self.assertEqual(
            uncertain["next_safe_actions"][0]["cli_flag"],
            "--resume",
        )
        self.assertFalse(
            uncertain["next_safe_actions"][0]["operator_identifiers_required"]
        )
        self.assertFalse(
            uncertain["next_safe_actions"][0][
                "private_folder_inspection_required"
            ]
        )
        blocked = source_intake_batch_exact.failure_document(
            "source_intake_batch_request_invalid"
        )
        self.assertFalse(blocked["writes_may_have_occurred"])
        self.assertFalse(blocked["outcome_unverified"])
        for pre_writer_code in (
            "exact_human_approval_operation_failed",
            "exact_human_approval_writer_result_invalid",
        ):
            with self.subTest(pre_writer_code=pre_writer_code):
                pre_writer = source_intake_batch_exact.failure_document(
                    pre_writer_code
                )
                self.assertFalse(pre_writer["writes_may_have_occurred"])
                self.assertFalse(pre_writer["outcome_unverified"])
                self.assertEqual(pre_writer["safe_recovery_actions"], [])
                self.assertEqual(pre_writer["next_safe_actions"], [])

    def test_bound_create_interruption_never_publishes_partial_final_file(
        self,
    ) -> None:
        root = self.root.resolve()
        target = (
            root
            / "receipts"
            / "ops"
            / "source-intake-batches"
            / "atomic-interruption-test.json"
        )
        raw = b"x" * (128 * 1024)
        heartbeat_calls = 0

        def interrupt_after_first_chunk() -> None:
            nonlocal heartbeat_calls
            heartbeat_calls += 1
            if heartbeat_calls == 2:
                raise RuntimeError("bounded-test-interruption")

        with archive_services._activity_group_bound_directory_chain(
            root,
            target.parent,
            create=True,
        ) as binding:
            with self.assertRaisesRegex(
                RuntimeError,
                "bounded-test-interruption",
            ):
                archive_services._write_activity_group_bytes_new_file_bound(
                    binding,
                    target,
                    raw,
                    heartbeat=interrupt_after_first_chunk,
                )

        self.assertFalse(target.exists())
        self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

        with archive_services._activity_group_bound_directory_chain(
            root,
            target.parent,
        ) as binding:
            archive_services._write_activity_group_bytes_new_file_bound(
                binding,
                target,
                raw,
            )
        self.assertEqual(target.read_bytes(), raw)

    def test_successful_batch_replay_reconciles_from_common_final_receipt(self) -> None:
        self._write_request(3)
        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        native = _Native()
        key_provider = _KeyProvider()
        with mock.patch.object(
            source_intake_batch_exact,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, key_provider),
        ):
            result = source_intake_batch_exact.execute_source_intake_batch(
                plan,
                expected_plan_sha256=plan.manifest.manifest_sha256,
                reviewer_claim=REVIEWER,
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["state"], "completed")
        self.assertEqual(result["receipt_create_count"], 3)
        self.assertIs(
            result["credential_material_used_for_local_authentication"],
            True,
        )
        self.assertIs(result["credential_values_echoed"], False)
        self.assertNotIn("credential_values_read", result)
        self.assertTrue(result["prepared_capture_request"]["ready"])
        self.assertTrue(
            self.root.joinpath(
                *plan.prepared_capture_request.relative_path.split("/")
            ).is_file()
        )
        self.assertEqual(native.calls, 1)
        replay = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        self.assertEqual(replay.state, "preexisting_unverified")
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        reconciled = source_intake_batch_exact.reconcile_source_intake_batch(
            replay,
            execution_sha256=result["execution_sha256"],
            key_provider=key_provider,
        )
        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        self.assertTrue(reconciled["ok"], reconciled)
        self.assertEqual(reconciled["completed_item_count"], 3)
        self.assertTrue(reconciled["independent_verification"])
        self.assertTrue(reconciled["completion_authentication_verified"])
        self.assertIs(
            reconciled["credential_material_used_for_local_authentication"],
            True,
        )
        self.assertIs(reconciled["credential_values_echoed"], False)
        self.assertNotIn("credential_values_read", reconciled)
        self.assertEqual(before, after)

    def test_reconcile_rejects_self_consistent_unkeyed_final_forgery(self) -> None:
        replay, result, key_provider = self._execute_completed_batch()
        checkpoint_path = self._checkpoint_path(result["execution_sha256"])
        checkpoint_rows = [
            json.loads(line)
            for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        item_verified = next(
            row for row in checkpoint_rows if row["stage"] == "item_verified"
        )
        item_verified["observed_sha256"] = "sha256:" + "2" * 64
        previous = None
        for sequence, row in enumerate(checkpoint_rows):
            row["sequence"] = sequence
            row["previous_checkpoint_sha256"] = previous
            checkpoint_basis = dict(row)
            checkpoint_basis.pop("checkpoint_sha256")
            row["checkpoint_sha256"] = self._exact_document_sha256(
                checkpoint_basis
            )
            previous = row["checkpoint_sha256"]
        checkpoint_path.write_bytes(
            b"".join(
                self._canonical_exact_bytes(row) + b"\n"
                for row in checkpoint_rows
            )
        )

        final_path = self._final_receipt_path(result["execution_sha256"])
        final = json.loads(final_path.read_text(encoding="utf-8"))
        stable_result = final["result"]
        stable_result["checkpoint_chain_sha256"] = previous
        stable_result["independent_verification_sha256"] = "sha256:" + "1" * 64
        authentication = stable_result["completion_authentication"]
        payload = exact_operation_manifest.exact_operation_completion_authentication_payload(
            stable_result
        )
        authentication["payload_sha256"] = "sha256:" + hashlib.sha256(
            payload
        ).hexdigest()
        result_basis = dict(stable_result)
        result_basis.pop("result_sha256")
        stable_result["result_sha256"] = self._exact_document_sha256(result_basis)
        receipt_basis = dict(final)
        receipt_basis.pop("receipt_sha256")
        final["receipt_sha256"] = self._exact_document_sha256(receipt_basis)
        final_path.write_bytes(self._canonical_exact_bytes(final) + b"\n")

        reconciled = source_intake_batch_exact.reconcile_source_intake_batch(
            replay,
            execution_sha256=result["execution_sha256"],
            key_provider=key_provider,
        )

        self.assertFalse(reconciled["ok"], reconciled)
        self.assertTrue(reconciled["independent_verification"])
        self.assertFalse(reconciled["completion_authentication_verified"])
        self.assertIsNone(
            reconciled["credential_material_used_for_local_authentication"]
        )

    def test_reconcile_rejects_non_succeeded_and_tampered_claims(self) -> None:
        replay, result, key_provider = self._execute_completed_batch()
        final_path = self._final_receipt_path(result["execution_sha256"])
        final = json.loads(final_path.read_text(encoding="utf-8"))
        claim_path = self._claim_path(final)
        original_claim_raw = claim_path.read_bytes()
        original_claim = json.loads(original_claim_raw.decode("utf-8"))

        started = dict(original_claim)
        started.pop("authentication")
        started.update(
            {
                "status": "started",
                "finished_at": None,
                "failure_code": None,
            }
        )
        started = exact_human_approval._authenticated(
            started,
            bytearray(range(32)),
        )
        claim_path.write_bytes(exact_human_approval._canonical_bytes(started))
        non_succeeded = source_intake_batch_exact.reconcile_source_intake_batch(
            replay,
            execution_sha256=result["execution_sha256"],
            key_provider=key_provider,
        )
        self.assertFalse(non_succeeded["ok"], non_succeeded)
        self.assertFalse(non_succeeded["completion_authentication_verified"])

        claim_path.write_bytes(original_claim_raw)
        tampered = json.loads(original_claim_raw.decode("utf-8"))
        supplied_mac = tampered["authentication"]["mac"]
        tampered["authentication"]["mac"] = supplied_mac[:-1] + (
            "0" if supplied_mac[-1] != "0" else "1"
        )
        claim_path.write_bytes(exact_human_approval._canonical_bytes(tampered))
        invalid_mac = source_intake_batch_exact.reconcile_source_intake_batch(
            replay,
            execution_sha256=result["execution_sha256"],
            key_provider=key_provider,
        )
        self.assertFalse(invalid_mac["ok"], invalid_mac)
        self.assertFalse(invalid_mac["completion_authentication_verified"])

    def test_reconcile_without_completion_is_strictly_read_only(self) -> None:
        self._write_request(1)
        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        key_provider = _KeyProvider()
        before_paths = {
            path.relative_to(self.root).as_posix(): (
                "directory" if path.is_dir() else path.read_bytes()
            )
            for path in self.root.rglob("*")
        }

        reconciled = source_intake_batch_exact.reconcile_source_intake_batch(
            plan,
            execution_sha256="sha256:" + "0" * 64,
            key_provider=key_provider,
        )
        after_paths = {
            path.relative_to(self.root).as_posix(): (
                "directory" if path.is_dir() else path.read_bytes()
            )
            for path in self.root.rglob("*")
        }

        self.assertFalse(reconciled["ok"], reconciled)
        self.assertFalse(reconciled["final_receipt_present"])
        self.assertFalse(reconciled["completion_authentication_verified"])
        self.assertIsNone(
            reconciled["credential_material_used_for_local_authentication"]
        )
        self.assertEqual(key_provider.calls, 0)
        self.assertEqual(before_paths, after_paths)

    def test_interrupted_batch_resumes_same_authenticated_claim_from_checkpoint(self) -> None:
        self._write_request(3)
        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        native = _Native()
        key_provider = _KeyProvider()
        original_write = source_intake_batch_exact._Writer.write_field
        calls = 0

        def fail_before_second_field(writer, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("bounded-test-interruption")
            return original_write(writer, **kwargs)

        with (
            mock.patch.object(
                source_intake_batch_exact,
                "_execute_exact_human_approved_write",
                side_effect=self._workflow(native, key_provider),
            ),
            mock.patch.object(
                source_intake_batch_exact._Writer,
                "write_field",
                new=fail_before_second_field,
            ),
        ):
            with self.assertRaises(ExactHumanApprovalWorkflowError) as raised:
                source_intake_batch_exact.execute_source_intake_batch(
                    plan,
                    expected_plan_sha256=plan.manifest.manifest_sha256,
                    reviewer_claim=REVIEWER,
                )

        self.assertEqual(raised.exception.code, "exact_human_approval_state_unknown")
        claim_paths = list(
            (
                self.root
                / "profiles"
                / "local"
                / "exact-human-approvals"
                / "claims"
            ).glob("approval_*.json")
        )
        checkpoint_paths = list(
            (
                self.root
                / "profiles"
                / "local"
                / "exact-operations"
                / "checkpoints"
            ).glob("*.jsonl")
        )
        self.assertEqual(len(claim_paths), 1)
        self.assertEqual(len(checkpoint_paths), 1)
        resumed_plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        self.assertTrue(resumed_plan.resume_candidate)

        resumed = source_intake_batch_exact.resume_source_intake_batch(
            resumed_plan,
            reviewer_claim=REVIEWER,
            approval_id=claim_paths[0].stem,
            execution_sha256="sha256:" + checkpoint_paths[0].stem,
            key_provider=key_provider,
        )

        self.assertTrue(resumed["ok"], resumed)
        self.assertEqual(resumed["state"], "completed")
        self.assertGreaterEqual(resumed["resumed_field_count"], 1)
        self.assertTrue(
            self.root.joinpath(
                *resumed_plan.prepared_capture_request.relative_path.split("/")
            ).is_file()
        )

    def test_public_auto_resume_discovers_read_only_then_completes_without_ids(
        self,
    ) -> None:
        resumed_plan, key_provider = self._create_interrupted_batch()
        before = {
            path.relative_to(self.root).as_posix(): (
                "directory" if path.is_dir() else path.read_bytes()
            )
            for path in self.root.rglob("*")
        }
        key_provider.create_if_missing_calls.clear()

        discovery = (
            source_intake_batch_exact.discover_source_intake_batch_resume_read_only(
                resumed_plan,
                reviewer_claim=REVIEWER,
                key_provider=key_provider,
            )
        )
        after_discovery = {
            path.relative_to(self.root).as_posix(): (
                "directory" if path.is_dir() else path.read_bytes()
            )
            for path in self.root.rglob("*")
        }

        self.assertEqual(before, after_discovery)
        self.assertEqual(key_provider.create_if_missing_calls, [False])
        public_discovery = discovery.public_document()
        self.assertEqual(public_discovery["candidate_count"], 1)
        self.assertFalse(public_discovery["operator_identifiers_required"])
        self.assertFalse(public_discovery["private_folder_inspection_required"])
        self.assertFalse(public_discovery["locks_created_or_acquired"])
        self.assertNotIn("approval_id", public_discovery)
        self.assertNotIn("execution_sha256", public_discovery)

        parser = archive_cli.build_parser()
        args = parser.parse_args(
            [
                "source-intake-batch",
                str(self.root),
                "--manifest",
                str(self.request_path),
                "--resume",
                "--reviewed-by",
                REVIEWER,
                "--no-progress",
                "--format",
                "json",
            ]
        )
        with (
            mock.patch.object(
                source_intake_batch_exact,
                "_production_key_provider",
                return_value=key_provider,
            ),
            mock.patch(
                "wom_kit.exact_human_approval_workflow._production_key_provider",
                return_value=key_provider,
            ),
            redirect_stdout(stdout := io.StringIO()),
            redirect_stderr(stderr := io.StringIO()),
        ):
            code = args.func(args)
        result = json.loads(stdout.getvalue())

        self.assertEqual(code, 0, result)
        self.assertEqual(stderr.getvalue(), "")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["automatic_resume_discovery"])
        self.assertFalse(result["operator_resume_identifiers_supplied"])
        self.assertFalse(result["native_approval_redisplayed"])
        self.assertEqual(result["resume_discovery"]["candidate_count"], 1)
        self.assertTrue(
            all(flag is False for flag in key_provider.create_if_missing_calls)
        )
        rendered = json.dumps(result, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(str(self.root), rendered)
        self.assertNotIn("staging/incoming", rendered)
        self.assertNotIn("profiles/local", rendered)

    def test_auto_resume_zero_candidates_is_read_only_and_creates_no_key_or_lock(
        self,
    ) -> None:
        self._write_request(1)
        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        key_provider = _KeyProvider()
        before = {
            path.relative_to(self.root).as_posix(): (
                "directory" if path.is_dir() else path.read_bytes()
            )
            for path in self.root.rglob("*")
        }

        with self.assertRaises(
            source_intake_batch_exact.SourceIntakeBatchExactError
        ) as raised:
            source_intake_batch_exact.discover_source_intake_batch_resume_read_only(
                plan,
                reviewer_claim=REVIEWER,
                key_provider=key_provider,
            )

        after = {
            path.relative_to(self.root).as_posix(): (
                "directory" if path.is_dir() else path.read_bytes()
            )
            for path in self.root.rglob("*")
        }
        self.assertEqual(raised.exception.code, "source_intake_batch_resume_required")
        self.assertEqual(before, after)
        self.assertTrue(
            all(flag is False for flag in key_provider.create_if_missing_calls)
        )
        self.assertFalse(
            (
                self.root
                / "profiles"
                / "local"
                / "exact-operations"
                / ".writer.lock"
            ).exists()
        )

    def test_auto_resume_rejects_two_authenticated_exact_candidates(self) -> None:
        self._write_request(1)
        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        key_provider = _KeyProvider()

        def interrupt_before_write(writer, **kwargs):
            raise RuntimeError("bounded-test-interruption")

        for _attempt in range(2):
            with (
                mock.patch.object(
                    source_intake_batch_exact,
                    "_execute_exact_human_approved_write",
                    side_effect=self._workflow(_Native(), key_provider),
                ),
                mock.patch.object(
                    source_intake_batch_exact._Writer,
                    "write_field",
                    new=interrupt_before_write,
                ),
            ):
                with self.assertRaises(ExactHumanApprovalWorkflowError):
                    source_intake_batch_exact.execute_source_intake_batch(
                        plan,
                        expected_plan_sha256=plan.manifest.manifest_sha256,
                        reviewer_claim=REVIEWER,
                    )
        replay = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        key_provider.create_if_missing_calls.clear()

        with self.assertRaises(
            source_intake_batch_exact.SourceIntakeBatchExactError
        ) as raised:
            source_intake_batch_exact.discover_source_intake_batch_resume_read_only(
                replay,
                reviewer_claim=REVIEWER,
                key_provider=key_provider,
            )

        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(
            raised.exception.code,
            "source_intake_batch_resume_ambiguous",
        )
        self.assertEqual(before, after)
        self.assertEqual(key_provider.create_if_missing_calls, [False])

    def test_auto_resume_rejects_forged_checkpoint_chain_without_writing(self) -> None:
        replay, key_provider = self._create_interrupted_batch()
        checkpoint_paths = list(
            (
                self.root
                / "profiles"
                / "local"
                / "exact-operations"
                / "checkpoints"
            ).glob("*.jsonl")
        )
        self.assertEqual(len(checkpoint_paths), 1)
        rows = checkpoint_paths[0].read_text(encoding="ascii").splitlines()
        forged = json.loads(rows[0])
        forged["checkpoint_sha256"] = "sha256:" + "0" * 64
        rows[0] = self._canonical_exact_bytes(forged).decode("ascii")
        checkpoint_paths[0].write_text("\n".join(rows) + "\n", encoding="ascii")
        before = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        key_provider.create_if_missing_calls.clear()

        with self.assertRaises(
            source_intake_batch_exact.SourceIntakeBatchExactError
        ) as raised:
            source_intake_batch_exact.discover_source_intake_batch_resume_read_only(
                replay,
                reviewer_claim=REVIEWER,
                key_provider=key_provider,
            )

        after = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(raised.exception.code, "source_intake_batch_resume_invalid")
        self.assertEqual(before, after)
        self.assertEqual(key_provider.create_if_missing_calls, [False])

    def test_approve_reads_request_once_and_rehashes_each_source_once_after_decision(self) -> None:
        self._write_request(3)
        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )
        native = _Native()
        key_provider = _KeyProvider()
        with (
            mock.patch.object(
                source_intake_batch_exact,
                "_execute_exact_human_approved_write",
                side_effect=self._workflow(native, key_provider),
            ),
            mock.patch.object(
                source_intake_batch_exact,
                "_stable_request_bytes",
                wraps=source_intake_batch_exact._stable_request_bytes,
            ) as request_reads,
            mock.patch.object(
                source_intake_batch_exact,
                "_stable_source_digest",
                wraps=source_intake_batch_exact._stable_source_digest,
            ) as source_reads,
        ):
            result = source_intake_batch_exact.execute_source_intake_batch(
                plan,
                expected_plan_sha256=plan.manifest.manifest_sha256,
                reviewer_claim=REVIEWER,
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual(request_reads.call_count, 1)
        self.assertEqual(source_reads.call_count, 3)

    def test_duplicate_json_member_is_rejected_without_source_or_target_write(self) -> None:
        source = self.root / "staging" / "incoming" / "source.bin"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"source\n")
        self.request_path.write_bytes(
            b'{"schema":"wom-kit/source-intake-batch-request/v0.1",'
            b'"batch_id":"first","batch_id":"second","items":[]}'
        )

        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )

        self.assertFalse(plan.approveable)
        self.assertEqual(plan.blockers, ("source_intake_batch_request_invalid",))
        self.assertFalse(list((self.root / "receipts" / "sources").glob("source-intake-*.json")))

    def test_duplicate_local_source_is_blocked_even_when_options_change_target(self) -> None:
        sources = self._write_request(1)
        request = json.loads(self.request_path.read_text(encoding="utf-8"))
        request["items"].append(
            {
                "item_id": "same-source-different-title",
                "local_path": sources[0].relative_to(self.root).as_posix(),
                "source_role": "primary_source",
                "title": "A second safe label",
            }
        )
        self.request_path.write_text(json.dumps(request), encoding="utf-8")

        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )

        self.assertFalse(plan.approveable)
        self.assertEqual(
            plan.blockers,
            ("source_intake_batch_duplicate_source",),
        )

    def test_hardlink_alias_of_same_physical_source_is_blocked(self) -> None:
        sources = self._write_request(1)
        alias = sources[0].with_name("hardlink-alias.bin")
        os.link(sources[0], alias)
        request = json.loads(self.request_path.read_text(encoding="utf-8"))
        request["items"].append(
            {
                "item_id": "hardlink-alias",
                "local_path": alias.relative_to(self.root).as_posix(),
                "source_role": "primary_source",
            }
        )
        self.request_path.write_text(json.dumps(request), encoding="utf-8")

        plan = source_intake_batch_exact.plan_source_intake_batch(
            self.root,
            self.request_path,
        )

        self.assertFalse(plan.approveable)
        self.assertEqual(
            plan.blockers,
            ("source_intake_batch_duplicate_source",),
        )

    def test_cli_dry_run_approve_and_reconcile_use_one_batch_approval(self) -> None:
        self._write_request(3)
        parser = archive_cli.build_parser()

        def run(values: list[str]) -> tuple[int, dict[str, Any], str]:
            args = parser.parse_args(values)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = args.func(args)
            return int(code), json.loads(stdout.getvalue()), stderr.getvalue()

        common = [
            "source-intake-batch",
            str(self.root),
            "--manifest",
            str(self.request_path),
            "--no-progress",
            "--format",
            "json",
        ]
        dry_code, dry, dry_stderr = run([*common, "--dry-run"])
        self.assertEqual(dry_code, 0, dry)
        self.assertEqual(dry_stderr, "")
        self.assertEqual(dry["item_count"], 3)

        native = _Native()
        key_provider = _KeyProvider()
        with mock.patch.object(
            source_intake_batch_exact,
            "_execute_exact_human_approved_write",
            side_effect=self._workflow(native, key_provider),
        ):
            apply_code, applied, apply_stderr = run(
                [
                    *common,
                    "--approve",
                    "--reviewed-by",
                    REVIEWER,
                    "--expected-plan-sha256",
                    dry["plan_sha256"],
                ]
            )
        self.assertEqual(apply_code, 0, applied)
        self.assertEqual(apply_stderr, "")
        self.assertEqual(native.calls, 1)
        self.assertEqual(applied["receipt_create_count"], 3)

        with mock.patch(
            "wom_kit.exact_human_approval_workflow._production_key_provider",
            return_value=key_provider,
        ):
            reconcile_code, reconciled, reconcile_stderr = run(
                [
                    *common,
                    "--reconcile",
                    "--execution-sha256",
                    applied["execution_sha256"],
                ]
            )
        self.assertEqual(reconcile_code, 0, reconciled)
        self.assertEqual(reconcile_stderr, "")
        self.assertEqual(reconciled["completed_item_count"], 3)

    def test_cli_help_exposes_identifier_free_automatic_resume(self) -> None:
        parser = archive_cli.build_parser()
        with (
            redirect_stdout(stdout := io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            parser.parse_args(["source-intake-batch", "--help"])
        rendered = stdout.getvalue()
        normalized = " ".join(rendered.split()).replace(
            "private- folder",
            "private-folder",
        )
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--resume", normalized)
        self.assertIn(
            "no private-folder inspection or copied IDs",
            normalized,
        )
        self.assertIn("Prefer --resume", normalized)

    def test_both_resume_paths_cannot_bypass_project_runtime_guard(self) -> None:
        metadata = self.root.parent / ".zettel-kasten"
        metadata.mkdir()
        (metadata / "installed-version.txt").write_text(
            "v0.0.1\n",
            encoding="utf-8",
        )
        self._write_request(1)
        parser = archive_cli.build_parser()
        common = [
            "source-intake-batch",
            str(self.root),
            "--manifest",
            str(self.request_path),
            "--reviewed-by",
            REVIEWER,
            "--format",
            "json",
        ]
        resume_modes = (
            [*common, "--resume"],
            [
                *common,
                "--resume-approval-id",
                "approval_" + "0" * 32,
                "--execution-sha256",
                "sha256:" + "0" * 64,
            ],
        )

        for raw_argv in resume_modes:
            with self.subTest(raw_argv=raw_argv):
                args = parser.parse_args(raw_argv)
                blocker = archive_cli._project_write_runtime_guard(
                    args,
                    raw_argv,
                )
                self.assertIsNotNone(blocker)
                self.assertEqual(
                    blocker["reason_codes"],
                    ["project_runtime_mismatch"],
                )
                self.assertEqual(blocker["files_written"], [])

        dry_argv = [
            "source-intake-batch",
            str(self.root),
            "--manifest",
            str(self.request_path),
            "--dry-run",
            "--format",
            "json",
        ]
        self.assertIsNone(
            archive_cli._project_write_runtime_guard(
                parser.parse_args(dry_argv),
                dry_argv,
            )
        )

    def test_cli_reports_state_unknown_as_possible_partial_write(self) -> None:
        self._write_request(1)
        parser = archive_cli.build_parser()
        args = parser.parse_args(
            [
                "source-intake-batch", str(self.root), "--manifest",
                str(self.request_path), "--approve", "--reviewed-by", REVIEWER,
                "--expected-plan-sha256", "a" * 64, "--no-progress", "--format", "json",
            ]
        )
        with (
            mock.patch.object(
                source_intake_batch_exact,
                "execute_source_intake_batch",
                side_effect=ExactHumanApprovalWorkflowError(
                    "exact_human_approval_state_unknown"
                ),
            ),
            redirect_stdout(stdout := io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(args.func(args), 1)
        result = json.loads(stdout.getvalue())
        self.assertTrue(result["writes_may_have_occurred"])
        self.assertTrue(result["outcome_unverified"])
        self.assertFalse(
            result["next_safe_actions"][0]["operator_identifiers_required"]
        )

        text_args = parser.parse_args(
            [
                "source-intake-batch",
                str(self.root),
                "--manifest",
                str(self.request_path),
                "--approve",
                "--reviewed-by",
                REVIEWER,
                "--expected-plan-sha256",
                "a" * 64,
                "--no-progress",
                "--format",
                "text",
            ]
        )
        with (
            mock.patch.object(
                source_intake_batch_exact,
                "execute_source_intake_batch",
                side_effect=ExactHumanApprovalWorkflowError(
                    "exact_human_approval_state_unknown"
                ),
            ),
            redirect_stdout(text_stdout := io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(text_args.func(text_args), 1)
        text_result = text_stdout.getvalue()
        self.assertIn("rerun this unchanged batch request with --resume", text_result)
        self.assertIn("do not inspect private folders", text_result)
        self.assertNotIn("approval_", text_result)

    def test_cli_reports_pre_writer_operation_failure_as_zero_write(self) -> None:
        self._write_request(1)
        parser = archive_cli.build_parser()
        args = parser.parse_args(
            [
                "source-intake-batch", str(self.root), "--manifest",
                str(self.request_path), "--approve", "--reviewed-by", REVIEWER,
                "--expected-plan-sha256", "a" * 64, "--no-progress", "--format", "json",
            ]
        )
        with (
            mock.patch.object(
                source_intake_batch_exact,
                "execute_source_intake_batch",
                side_effect=ExactHumanApprovalWorkflowError(
                    "exact_human_approval_operation_failed"
                ),
            ),
            redirect_stdout(stdout := io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(args.func(args), 1)
        result = json.loads(stdout.getvalue())
        self.assertFalse(result["writes_may_have_occurred"])
        self.assertFalse(result["outcome_unverified"])
        self.assertEqual(result["safe_recovery_actions"], [])
        self.assertEqual(result["next_safe_actions"], [])

        text_args = parser.parse_args(
            [
                "source-intake-batch", str(self.root), "--manifest",
                str(self.request_path), "--approve", "--reviewed-by", REVIEWER,
                "--expected-plan-sha256", "a" * 64, "--no-progress", "--format", "text",
            ]
        )
        with (
            mock.patch.object(
                source_intake_batch_exact,
                "execute_source_intake_batch",
                side_effect=ExactHumanApprovalWorkflowError(
                    "exact_human_approval_operation_failed"
                ),
            ),
            redirect_stdout(text_stdout := io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(text_args.func(text_args), 1)
        text_result = text_stdout.getvalue()
        self.assertIn("Writes performed: False", text_result)
        self.assertIn("source_intake_batch_write_failed", text_result)
        self.assertNotIn("--resume", text_result)


if __name__ == "__main__":
    unittest.main()
