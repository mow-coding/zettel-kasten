from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from wom_kit.exact_human_approval import (
    CLAIMS_RELATIVE_ROOT,
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import (
    APPROVE_BUTTON_ID,
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)
from wom_kit import exact_human_approval_workflow as workflow_module
from wom_kit.exact_human_approval_workflow import (
    ExactHumanApprovalWorkflowError,
    _execute_exact_human_approved_write_core as execute_exact_human_approved_write,
    _resume_exact_human_approved_write_core as resume_exact_human_approved_write,
)


class _Native:
    def __init__(self, result: tuple[int, bool]) -> None:
        self.result = result
        self.calls = 0

    def show(self, **_kwargs: str) -> tuple[int, bool]:
        self.calls += 1
        return self.result


class _KeyProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.create_if_missing: list[bool] = []

    def use_key(
        self,
        _root: Path | str,
        consumer: Callable[[memoryview], Any],
        *,
        create_if_missing: bool = False,
    ) -> Any:
        self.calls += 1
        self.create_if_missing.append(create_if_missing)
        buffer = bytearray(range(32))
        try:
            return consumer(memoryview(buffer))
        finally:
            buffer[:] = b"\0" * len(buffer)


class ExactHumanApprovalWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text(
            "archive_id: archive:test\n", encoding="utf-8"
        )
        self.context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.zettel_edge,
            archive_identity_sha256=exact_human_approval_archive_identity_sha256(
                "archive:test"
            ),
            plan_sha256="sha256:" + "a" * 64,
            target_binding_sha256="sha256:" + "b" * 64,
            reviewer_claim="person:local-operator",
            review_binding_codes=("edge_plan_digest", "target_digest"),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_generic_resume_writer_injection_is_not_public(self) -> None:
        self.assertNotIn(
            "resume_exact_human_approved_write",
            workflow_module.__all__,
        )
        self.assertFalse(
            hasattr(workflow_module, "resume_exact_human_approved_write")
        )

    def test_cancel_touches_no_key_claim_or_writer(self) -> None:
        native = _Native((2, False))
        key_provider = _KeyProvider()
        writer_calls = 0

        def writer(_reference):
            nonlocal writer_calls
            writer_calls += 1
            return {"ok": True}

        with self.assertRaises(ExactHumanApprovalWorkflowError) as captured:
            execute_exact_human_approved_write(
                self.root,
                self.context,
                writer,
                native=native,
                key_provider=key_provider,
            )
        self.assertEqual(captured.exception.code, "exact_human_approval_cancelled")
        self.assertEqual(key_provider.calls, 0)
        self.assertEqual(writer_calls, 0)
        self.assertFalse((self.root / "profiles").exists())

    def test_live_approval_claims_before_writer_and_finalizes_success(self) -> None:
        native = _Native((APPROVE_BUTTON_ID, True))
        key_provider = _KeyProvider()
        observed: list[dict[str, Any]] = []

        def writer(claim):
            paths = list((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))
            self.assertEqual(len(paths), 1)
            self.assertIn('"status":"started"', paths[0].read_text(encoding="utf-8"))
            observed.append(claim.assert_ready_for_context(self.context))
            return {"ok": True, "lifecycle_action": "test_write"}

        result = execute_exact_human_approved_write(
            self.root,
            self.context,
            writer,
            native=native,
            key_provider=key_provider,
        )
        self.assertEqual(len(observed), 1)
        self.assertEqual(key_provider.create_if_missing, [True])
        self.assertEqual(result["exact_human_approval"]["status"], "succeeded")
        self.assertEqual(result["exact_human_approval_reference"], observed[0])
        claim_path = next((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))
        self.assertIn('"status":"succeeded"', claim_path.read_text(encoding="utf-8"))

    def test_false_writer_result_keeps_claim_started_for_reconciliation(self) -> None:
        result = execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _reference: {"ok": False, "reason_code": "blocked"},
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["exact_human_approval"]["status"], "started")
        self.assertEqual(
            result["exact_human_approval_reconciliation"],
            {
                "required": True,
                "reason_code": "approval_claim_reconciliation_required",
                "automatic_retry_allowed": False,
            },
        )
        claim_path = next((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))
        claim_text = claim_path.read_text(encoding="utf-8")
        self.assertIn('"status":"started"', claim_text)
        self.assertNotIn('"status":"failed"', claim_text)

    def test_partial_durable_effect_shapes_never_finalize_claim_as_failed(self) -> None:
        cases = {
            "session_evidence_partial": {
                "ok": False,
                "state": "partial",
                "persistence": {
                    "files_written_count": 1,
                    "evidence_bytes_persisted": True,
                    "receipt_persisted": False,
                },
            },
            "promote_index_failure": {
                "ok": False,
                "state": "canonical_written_index_update_failed",
                "partial_result": {
                    "canonical_and_receipt_written": True,
                    "index_current": False,
                },
            },
            "mint_index_failure": {
                "ok": False,
                "state": "canonical_written_index_update_failed",
                "partial_result": {
                    "canonical_receipt_and_snapshot_written": True,
                    "index_current": False,
                },
            },
            "retire_index_failure": {
                "ok": False,
                "state": "draft_retired_index_update_failed",
                "partial_result": {
                    "draft_removed_and_receipt_written": True,
                    "index_current": False,
                },
            },
        }
        for name, writer_result in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "archive"
                root.mkdir()
                (root / "archive.yml").write_text(
                    "archive_id: archive:test\n", encoding="utf-8"
                )
                result = execute_exact_human_approved_write(
                    root,
                    self.context,
                    lambda _claim, value=writer_result: value,
                    native=_Native((APPROVE_BUTTON_ID, True)),
                    key_provider=_KeyProvider(),
                )
                self.assertFalse(result["ok"])
                self.assertEqual(
                    result["exact_human_approval"]["status"], "started"
                )
                self.assertTrue(
                    result["exact_human_approval_reconciliation"]["required"]
                )
                self.assertFalse(
                    result["exact_human_approval_reconciliation"]
                    ["automatic_retry_allowed"]
                )
                claim_path = next((root / CLAIMS_RELATIVE_ROOT).glob("*.json"))
                self.assertIn(
                    '"status":"started"', claim_path.read_text(encoding="utf-8")
                )

    def test_writer_exception_is_sanitized_and_claim_remains_started(self) -> None:
        def writer(_reference):
            raise RuntimeError("secret private path")

        with self.assertRaises(ExactHumanApprovalWorkflowError) as captured:
            execute_exact_human_approved_write(
                self.root,
                self.context,
                writer,
                native=_Native((APPROVE_BUTTON_ID, True)),
                key_provider=_KeyProvider(),
            )
        self.assertEqual(
            captured.exception.code, "exact_human_approval_state_unknown"
        )
        self.assertNotIn("secret private path", str(captured.exception))
        claim_path = next((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))
        self.assertIn('"status":"started"', claim_path.read_text(encoding="utf-8"))

    def test_malformed_writer_result_is_unknown_not_false_failure(self) -> None:
        with self.assertRaises(ExactHumanApprovalWorkflowError) as captured:
            execute_exact_human_approved_write(
                self.root,
                self.context,
                lambda _reference: {"unexpected": True},
                native=_Native((APPROVE_BUTTON_ID, True)),
                key_provider=_KeyProvider(),
            )
        self.assertEqual(captured.exception.code, "exact_human_approval_state_unknown")
        claim_path = next((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))
        self.assertIn('"status":"started"', claim_path.read_text(encoding="utf-8"))

    def test_resume_reauthenticates_same_started_claim_without_new_prompt(self) -> None:
        initial_provider = _KeyProvider()
        started = execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _claim: {"ok": False, "reason_code": "process_interrupted"},
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=initial_provider,
        )
        approval_id = started["exact_human_approval"]["approval_id"]
        resumed_provider = _KeyProvider()
        guard_calls = 0
        writer_calls = 0

        def checkpoint_guard() -> bool:
            nonlocal guard_calls
            guard_calls += 1
            return True

        def writer(claim):
            nonlocal writer_calls
            writer_calls += 1
            self.assertEqual(
                claim.assert_ready_for_context(self.context)["approval_id"],
                approval_id,
            )
            return {"ok": True, "lifecycle_action": "resumed_test_write"}

        resumed = resume_exact_human_approved_write(
            self.root,
            self.context,
            approval_id,
            checkpoint_guard,
            writer,
            key_provider=resumed_provider,
        )

        self.assertEqual(initial_provider.create_if_missing, [True])
        self.assertEqual(resumed_provider.create_if_missing, [False])
        self.assertEqual(guard_calls, 1)
        self.assertEqual(writer_calls, 1)
        self.assertEqual(resumed["exact_human_approval"]["status"], "succeeded")

        with self.assertRaises(ExactHumanApprovalWorkflowError) as terminal:
            resume_exact_human_approved_write(
                self.root,
                self.context,
                approval_id,
                lambda: True,
                writer,
                key_provider=_KeyProvider(),
            )
        self.assertEqual(
            terminal.exception.code,
            "exact_human_approval_resume_claim_invalid",
        )
        self.assertEqual(writer_calls, 1)

    def test_resume_blocks_missing_checkpoint_and_context_drift(self) -> None:
        started = execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _claim: {"ok": False, "reason_code": "process_interrupted"},
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
        )
        approval_id = started["exact_human_approval"]["approval_id"]
        writer_calls = 0

        def writer(_claim):
            nonlocal writer_calls
            writer_calls += 1
            return {"ok": True}

        with self.assertRaises(ExactHumanApprovalWorkflowError) as missing:
            resume_exact_human_approved_write(
                self.root,
                self.context,
                approval_id,
                lambda: False,
                writer,
                key_provider=_KeyProvider(),
            )
        self.assertEqual(
            missing.exception.code,
            "exact_human_approval_resume_checkpoint_invalid",
        )
        self.assertEqual(writer_calls, 0)
        claim_path = next((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))
        self.assertIn('"status":"started"', claim_path.read_text(encoding="utf-8"))

        drifted_context = replace(
            self.context,
            plan_sha256="sha256:" + "c" * 64,
        )
        with self.assertRaises(ExactHumanApprovalWorkflowError) as drifted:
            resume_exact_human_approved_write(
                self.root,
                drifted_context,
                approval_id,
                lambda: True,
                writer,
                key_provider=_KeyProvider(),
            )
        self.assertEqual(
            drifted.exception.code,
            "exact_human_approval_resume_claim_invalid",
        )
        self.assertEqual(writer_calls, 0)

    def test_resume_blocks_tampered_authenticated_claim(self) -> None:
        started = execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _claim: {"ok": False, "reason_code": "process_interrupted"},
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
        )
        approval_id = started["exact_human_approval"]["approval_id"]
        claim_path = next((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))
        raw = claim_path.read_bytes()
        claim_path.write_bytes(raw.replace(b'"started"', b'"failed"', 1))

        with self.assertRaises(ExactHumanApprovalWorkflowError) as tampered:
            resume_exact_human_approved_write(
                self.root,
                self.context,
                approval_id,
                lambda: True,
                lambda _claim: {"ok": True},
                key_provider=_KeyProvider(),
            )
        self.assertEqual(
            tampered.exception.code,
            "exact_human_approval_resume_claim_invalid",
        )


if __name__ == "__main__":
    unittest.main()
