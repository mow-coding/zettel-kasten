from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

from wom_kit.exact_human_approval import (
    CLAIMS_RELATIVE_ROOT,
    exact_human_approval_archive_identity_sha256,
)
from wom_kit.exact_human_approval_windows import (
    APPROVE_BUTTON_ID,
    ExactHumanApprovalContext,
    ExactHumanApprovalOperation,
)
from wom_kit import archive_services
from wom_kit import exact_human_approval_workflow as workflow_module
from wom_kit.exact_human_approval_workflow import (
    ExactHumanApprovalWorkflowError,
    _execute_exact_human_approved_write_core as execute_exact_human_approved_write,
    _resume_exact_human_approved_transaction_auto_core as resume_exact_human_approved_transaction_auto,
    _resume_exact_human_approved_transaction_core as resume_exact_human_approved_transaction,
    _resume_exact_human_approved_write_core as resume_exact_human_approved_write,
    _resume_succeeded_claim_finalizer_core as resume_succeeded_claim_finalizer,
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

    @contextmanager
    def _resume_boundary(self):
        canonical_root = self.root.resolve()
        claims_root = canonical_root / CLAIMS_RELATIVE_ROOT
        with archive_services._activity_group_bound_directory_chain(
            canonical_root,
            claims_root,
            create=False,
        ) as binding:
            yield canonical_root, binding

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

    def test_claim_publication_boundary_exits_before_writer_inside_key_consumer(
        self,
    ) -> None:
        events: list[str] = []
        boundary_active = False
        key_active = False

        class OrderedKeyProvider:
            def use_key(
                provider_self,
                _root: Path | str,
                consumer: Callable[[memoryview], Any],
                *,
                create_if_missing: bool = False,
            ) -> Any:
                nonlocal key_active
                self.assertTrue(create_if_missing)
                key_active = True
                events.append("key_enter")
                key = bytearray(range(32))
                try:
                    return consumer(memoryview(key))
                finally:
                    key[:] = b"\0" * len(key)
                    key_active = False
                    events.append("key_exit")

        @contextmanager
        def publication_boundary():
            nonlocal boundary_active
            self.assertTrue(key_active)
            boundary_active = True
            events.append("boundary_enter")
            try:
                yield
                claim_path = next(
                    (self.root / CLAIMS_RELATIVE_ROOT).glob("*.json")
                )
                self.assertIn(
                    '"status":"started"',
                    claim_path.read_text(encoding="utf-8"),
                )
                events.append("claim_publication")
            finally:
                boundary_active = False
                events.append("boundary_exit")

        def writer(_claim) -> dict[str, Any]:
            self.assertTrue(key_active)
            self.assertFalse(boundary_active)
            self.assertEqual(
                events,
                [
                    "key_enter",
                    "boundary_enter",
                    "claim_publication",
                    "boundary_exit",
                ],
            )
            events.append("writer")
            return {"ok": True, "lifecycle_action": "test_write"}

        result = execute_exact_human_approved_write(
            self.root,
            self.context,
            writer,
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=OrderedKeyProvider(),
            claim_publication_boundary=publication_boundary,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(
            events,
            [
                "key_enter",
                "boundary_enter",
                "claim_publication",
                "boundary_exit",
                "writer",
                "key_exit",
            ],
        )

    def test_success_finalizer_runs_only_after_claim_is_durably_succeeded(self) -> None:
        events: list[str] = []

        def writer(_claim):
            events.append("writer")
            return {"ok": True, "lifecycle_action": "test_write"}

        def finalizer(claim) -> None:
            events.append("finalizer")
            self.assertEqual(claim.status, "succeeded")
            evidence = claim.succeeded_evidence_digests(self.context)
            self.assertEqual(
                set(evidence),
                {
                    "approval_reference_sha256",
                    "claim_receipt_sha256",
                    "claim_mac_sha256",
                },
            )
            self.assertTrue(
                all(value.startswith("sha256:") for value in evidence.values())
            )
            claim_path = next(
                (self.root / CLAIMS_RELATIVE_ROOT).glob("*.json")
            )
            self.assertIn(
                '"status":"succeeded"',
                claim_path.read_text(encoding="utf-8"),
            )

        result = execute_exact_human_approved_write(
            self.root,
            self.context,
            writer,
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
            claim_succeeded_finalizer=finalizer,
        )

        self.assertEqual(events, ["writer", "finalizer"])
        self.assertEqual(result["exact_human_approval"]["status"], "succeeded")

    def test_success_finalizer_is_skipped_for_unsuccessful_writer(self) -> None:
        finalizer_calls = 0

        def finalizer(_claim) -> None:
            nonlocal finalizer_calls
            finalizer_calls += 1

        result = execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _claim: {"ok": False, "reason_code": "blocked"},
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
            claim_succeeded_finalizer=finalizer,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(finalizer_calls, 0)
        self.assertEqual(result["exact_human_approval"]["status"], "started")

    def test_success_finalizer_failure_is_unknown_after_claim_succeeded(self) -> None:
        def finalizer(_claim) -> None:
            raise RuntimeError("private finalizer detail")

        with self.assertRaises(ExactHumanApprovalWorkflowError) as captured:
            execute_exact_human_approved_write(
                self.root,
                self.context,
                lambda _claim: {"ok": True},
                native=_Native((APPROVE_BUTTON_ID, True)),
                key_provider=_KeyProvider(),
                claim_succeeded_finalizer=finalizer,
            )

        self.assertEqual(
            captured.exception.code, "exact_human_approval_state_unknown"
        )
        self.assertNotIn("private finalizer detail", str(captured.exception))
        claim_path = next((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))
        self.assertIn(
            '"status":"succeeded"', claim_path.read_text(encoding="utf-8")
        )

    def test_succeeded_claim_tail_resumes_without_writer_or_new_prompt(self) -> None:
        with self.assertRaises(ExactHumanApprovalWorkflowError) as interrupted:
            execute_exact_human_approved_write(
                self.root,
                self.context,
                lambda _claim: {"ok": True},
                native=_Native((APPROVE_BUTTON_ID, True)),
                key_provider=_KeyProvider(),
                claim_succeeded_finalizer=lambda _claim: (_ for _ in ()).throw(
                    RuntimeError("hard exit before transaction unlock")
                ),
            )
        self.assertEqual(
            interrupted.exception.code, "exact_human_approval_state_unknown"
        )
        claim_path = next((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))
        approval_id = claim_path.stem
        self.assertIn(
            '"status":"succeeded"', claim_path.read_text(encoding="utf-8")
        )

        events: list[str] = []
        provider = _KeyProvider()

        def guard(claim) -> bool:
            events.append("guard")
            reference = claim.assert_succeeded_for_context(self.context)
            self.assertEqual(reference["approval_id"], approval_id)
            self.assertTrue(
                all(
                    value.startswith("sha256:")
                    for value in claim.succeeded_evidence_digests(
                        self.context
                    ).values()
                )
            )
            return True

        def tail(claim) -> None:
            events.append("tail")
            self.assertEqual(claim.status, "succeeded")
            self.assertEqual(
                claim.assert_succeeded_for_context(self.context)["approval_id"],
                approval_id,
            )

        result = resume_succeeded_claim_finalizer(
            self.root,
            self.context,
            approval_id,
            guard,
            tail,
            key_provider=provider,
        )
        self.assertEqual(events, ["guard", "tail"])
        self.assertEqual(provider.create_if_missing, [False])
        self.assertTrue(result["ok"])
        self.assertEqual(result["exact_human_approval"]["status"], "succeeded")
        self.assertFalse(result["domain_writer_reentered"])
        self.assertFalse(result["native_approval_redisplayed"])

    def test_succeeded_claim_tail_requires_exact_checkpoint(self) -> None:
        with self.assertRaises(ExactHumanApprovalWorkflowError):
            execute_exact_human_approved_write(
                self.root,
                self.context,
                lambda _claim: {"ok": True},
                native=_Native((APPROVE_BUTTON_ID, True)),
                key_provider=_KeyProvider(),
                claim_succeeded_finalizer=lambda _claim: (_ for _ in ()).throw(
                    RuntimeError("leave succeeded claim for recovery")
                ),
            )
        approval_id = next(
            (self.root / CLAIMS_RELATIVE_ROOT).glob("*.json")
        ).stem
        tail_calls = 0

        def tail(_claim) -> None:
            nonlocal tail_calls
            tail_calls += 1

        with self.assertRaises(ExactHumanApprovalWorkflowError) as missing:
            resume_succeeded_claim_finalizer(
                self.root,
                self.context,
                approval_id,
                lambda _claim: False,
                tail,
                key_provider=_KeyProvider(),
            )
        self.assertEqual(
            missing.exception.code,
            "exact_human_approval_resume_checkpoint_invalid",
        )
        self.assertEqual(tail_calls, 0)

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

        guarded_claim = None

        def checkpoint_guard(claim) -> bool:
            nonlocal guard_calls
            nonlocal guarded_claim
            guard_calls += 1
            guarded_claim = claim
            self.assertEqual(
                claim.assert_ready_for_context(self.context)["approval_id"],
                approval_id,
            )
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
        self.assertIsNotNone(guarded_claim)
        self.assertEqual(resumed["exact_human_approval"]["status"], "succeeded")

        with self.assertRaises(ExactHumanApprovalWorkflowError) as terminal:
            resume_exact_human_approved_write(
                self.root,
                self.context,
                approval_id,
                lambda _claim: True,
                writer,
                key_provider=_KeyProvider(),
            )
        self.assertEqual(
            terminal.exception.code,
            "exact_human_approval_resume_claim_invalid",
        )
        self.assertEqual(writer_calls, 1)

    def test_transaction_resume_routes_authenticated_started_claim_to_writer(self) -> None:
        started = execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _claim: {"ok": False, "reason_code": "interrupted"},
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
        )
        approval_id = started["exact_human_approval"]["approval_id"]
        events: list[str] = []

        result = resume_exact_human_approved_transaction(
            self.root,
            self.context,
            approval_id,
            lambda claim: (
                events.append("started_guard") is None
                and claim.status == "started"
            ),
            lambda _claim: (
                events.append("writer") is None
                and {"ok": True, "lifecycle_action": "resume"}
            ),
            lambda _claim: False,
            lambda claim: events.append(
                "finalizer_" + claim.status
            ),
            key_provider=_KeyProvider(),
        )
        self.assertEqual(
            events, ["started_guard", "writer", "finalizer_succeeded"]
        )
        self.assertTrue(result["ok"])
        self.assertEqual(
            result["exact_human_approval_resume_branch"], "started_writer"
        )
        self.assertFalse(result["native_approval_redisplayed"])

    def test_transaction_auto_resume_discovers_only_authenticated_checkpoint_candidate(self) -> None:
        started = execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _claim: {"ok": False, "reason_code": "interrupted"},
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
        )
        approval_id = started["exact_human_approval"]["approval_id"]
        events: list[str] = []
        provider = _KeyProvider()

        result = resume_exact_human_approved_transaction_auto(
            self.root,
            self.context,
            lambda claim: (
                events.append("discover_or_resume_guard") is None
                and claim.status == "started"
            ),
            lambda _claim: (
                events.append("writer") is None
                and {"ok": True, "lifecycle_action": "resume"}
            ),
            lambda _claim: False,
            lambda claim: events.append("finalizer_" + claim.status),
            key_provider=provider,
            resume_boundary=self._resume_boundary,
        )

        self.assertEqual(
            events,
            [
                "discover_or_resume_guard",
                "discover_or_resume_guard",
                "writer",
                "finalizer_succeeded",
            ],
        )
        self.assertEqual(provider.create_if_missing, [False])
        self.assertEqual(provider.calls, 1)
        self.assertTrue(result["automatic_resume_discovery"])
        self.assertFalse(result["operator_resume_identifiers_supplied"])
        self.assertFalse(result["native_approval_redisplayed"])
        self.assertFalse(
            result["resume_discovery"]["writes_performed_by_discovery"]
        )
        self.assertFalse(
            result["resume_discovery"]["directories_created_by_discovery"]
        )
        self.assertFalse(result["resume_discovery"]["new_locks_created"])
        self.assertNotIn("writes_performed", result["resume_discovery"])
        self.assertNotIn("directories_created", result["resume_discovery"])
        self.assertNotIn(
            "locks_created_or_acquired",
            result["resume_discovery"],
        )
        discovery_text = repr(result["resume_discovery"])
        self.assertNotIn(approval_id, discovery_text)
        self.assertNotIn(str(self.root), discovery_text)
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(approval_id, serialized)
        self.assertFalse(result["approval_identifier_exposed"])
        self.assertFalse(result["transaction_identifier_exposed"])

    def test_transaction_auto_resume_recursively_projects_private_locators(
        self,
    ) -> None:
        started = execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _claim: {"ok": False, "reason_code": "interrupted"},
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
        )
        approval_id = started["exact_human_approval"]["approval_id"]
        transaction_ref = "update_" + "c" * 32
        transaction_logical_ref = (
            ".zettel-kasten/transactions/" + transaction_ref
        )
        safe_checkpoint_sha256 = "sha256:" + "d" * 64
        safe_claim_mac_sha256 = "sha256:" + "e" * 64

        result = resume_exact_human_approved_transaction_auto(
            self.root,
            self.context,
            lambda claim: claim.status == "started",
            lambda _claim: {
                "ok": True,
                "status": "updated_restart_required",
                "exact_human_approval_reference": {
                    "approval_id": approval_id,
                    "claim_mac_sha256": safe_claim_mac_sha256,
                },
                "operation_exact_human_approval": {
                    "operation": "project_version_update",
                    "exact_human_approval": {
                        "approval_id": approval_id,
                    },
                },
                "transaction": {
                    "transaction_ref": transaction_ref,
                    "transaction_logical_ref": transaction_logical_ref,
                    "checkpoint_head_sha256": safe_checkpoint_sha256,
                },
                "evidence": {
                    "claim_mac_sha256": safe_claim_mac_sha256,
                },
                "paths": [
                    f"private/{transaction_ref}/checkpoint.json",
                    "receipts/public-summary.json",
                ],
                "nested_echo": {
                    "value": f"selected={approval_id}",
                },
            },
            lambda _claim: False,
            lambda _claim: None,
            key_provider=_KeyProvider(),
            resume_boundary=self._resume_boundary,
        )

        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(approval_id, serialized)
        self.assertNotIn(transaction_ref, serialized)
        self.assertNotIn('"exact_human_approval":', serialized)
        self.assertNotIn('"exact_human_approval_reference":', serialized)
        self.assertNotIn('"operation_exact_human_approval":', serialized)
        self.assertNotIn('"approval_id"', serialized)
        self.assertNotIn('"transaction_ref"', serialized)
        self.assertNotIn('"transaction_logical_ref"', serialized)
        self.assertEqual(
            result["transaction"]["checkpoint_head_sha256"],
            safe_checkpoint_sha256,
        )
        self.assertEqual(
            result["evidence"]["claim_mac_sha256"],
            safe_claim_mac_sha256,
        )
        self.assertEqual(result["paths"], ["receipts/public-summary.json"])
        self.assertEqual(result["nested_echo"], {})
        self.assertFalse(result["approval_identifier_exposed"])
        self.assertFalse(result["transaction_identifier_exposed"])

    def test_transaction_auto_resume_holds_key_through_unique_selection_and_writer(
        self,
    ) -> None:
        started = execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _claim: {"ok": False, "reason_code": "interrupted"},
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
        )
        approval_id = started["exact_human_approval"]["approval_id"]
        events: list[str] = []

        @contextmanager
        def ordered_boundary():
            events.append("filesystem_enter")
            try:
                with self._resume_boundary() as boundary:
                    yield boundary
            finally:
                events.append("filesystem_exit")

        class NonReentrantKeyProvider:
            def __init__(self) -> None:
                self.active = False
                self.successful_acquisitions = 0
                self.blocked_acquisitions = 0

            def use_key(
                self,
                _root: Path | str,
                consumer: Callable[[memoryview], Any],
                *,
                create_if_missing: bool = False,
            ) -> Any:
                if self.active:
                    self.blocked_acquisitions += 1
                    events.append("publisher_key_blocked")
                    raise RuntimeError("credential_key_lock_busy")
                if create_if_missing:
                    raise AssertionError("resume must not create key material")
                self.active = True
                self.successful_acquisitions += 1
                events.append("key_enter")
                key = bytearray(range(32))
                try:
                    return consumer(memoryview(key))
                finally:
                    key[:] = b"\0" * len(key)
                    events.append("key_exit")
                    self.active = False

        provider = NonReentrantKeyProvider()
        original_selected_resume = (
            workflow_module
            ._resume_exact_human_approved_transaction_with_key_core
        )

        def old_gap_publisher_attempt(*args, **kwargs):
            events.append("selected_handler_enter")
            with self.assertRaises(
                ExactHumanApprovalWorkflowError
            ) as blocked:
                execute_exact_human_approved_write(
                    self.root,
                    self.context,
                    lambda _claim: {
                        "ok": False,
                        "reason_code": "competing_interrupted",
                    },
                    native=_Native((APPROVE_BUTTON_ID, True)),
                    key_provider=provider,
                )
            self.assertEqual(
                blocked.exception.code,
                "exact_human_approval_key_unavailable",
            )
            events.append("publisher_rejected")
            self.assertEqual(
                len(list((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))),
                1,
            )
            result = original_selected_resume(*args, **kwargs)
            events.append("selected_handler_exit")
            return result

        with patch.object(
            workflow_module,
            "_resume_exact_human_approved_transaction_with_key_core",
            side_effect=old_gap_publisher_attempt,
        ):
            result = resume_exact_human_approved_transaction_auto(
                self.root,
                self.context,
                lambda claim: (
                    events.append("checkpoint_guard") is None
                    and claim.status == "started"
                ),
                lambda _claim: (
                    events.append("writer") is None
                    and {"ok": True, "lifecycle_action": "resume"}
                ),
                lambda _claim: False,
                lambda claim: events.append(
                    "finalizer_" + claim.status
                ),
                key_provider=provider,
                resume_boundary=ordered_boundary,
            )

        self.assertEqual(
            events,
            [
                "filesystem_enter",
                "key_enter",
                "checkpoint_guard",
                "selected_handler_enter",
                "publisher_key_blocked",
                "publisher_rejected",
                "checkpoint_guard",
                "writer",
                "finalizer_succeeded",
                "selected_handler_exit",
                "key_exit",
                "filesystem_exit",
            ],
        )
        self.assertEqual(provider.successful_acquisitions, 1)
        self.assertEqual(provider.blocked_acquisitions, 1)
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(approval_id, serialized)
        self.assertNotIn("exact_human_approval", result)
        self.assertNotIn("exact_human_approval_reference", result)
        self.assertFalse(result["approval_identifier_exposed"])
        self.assertFalse(result["transaction_identifier_exposed"])
        self.assertEqual(
            len(list((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))),
            1,
        )

    def test_transaction_auto_resume_preserves_selected_result_identifier_flag(
        self,
    ) -> None:
        execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _claim: {"ok": False, "reason_code": "interrupted"},
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
        )
        provider = _KeyProvider()

        result = resume_exact_human_approved_transaction_auto(
            self.root,
            self.context,
            lambda claim: claim.status == "started",
            lambda _claim: {
                "ok": True,
                "operator_resume_identifiers_supplied": True,
            },
            lambda _claim: False,
            lambda _claim: None,
            key_provider=provider,
            resume_boundary=self._resume_boundary,
        )

        self.assertTrue(result["operator_resume_identifiers_supplied"])
        self.assertEqual(provider.create_if_missing, [False])

    def test_transaction_auto_resume_asserts_supplied_id_after_discovery(self) -> None:
        started = execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _claim: {"ok": False, "reason_code": "interrupted"},
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
        )
        approval_id = started["exact_human_approval"]["approval_id"]
        transaction_ref = "update_" + "f" * 32
        events: list[str] = []

        result = resume_exact_human_approved_transaction_auto(
            self.root,
            self.context,
            lambda claim: (
                events.append("discover_or_resume_guard") is None
                and claim.status == "started"
            ),
            lambda _claim: (
                events.append("writer") is None
                and {
                    "ok": True,
                    "lifecycle_action": "resume",
                    "transaction": {
                        "transaction_ref": transaction_ref,
                        "checkpoint_head_sha256": "sha256:" + "a" * 64,
                    },
                }
            ),
            lambda _claim: False,
            lambda claim: events.append("finalizer_" + claim.status),
            supplied_approval_id=approval_id,
            key_provider=_KeyProvider(),
            resume_boundary=self._resume_boundary,
        )

        self.assertEqual(
            events,
            [
                "discover_or_resume_guard",
                "discover_or_resume_guard",
                "writer",
                "finalizer_succeeded",
            ],
        )
        self.assertTrue(result["automatic_resume_discovery"])
        self.assertTrue(result["operator_resume_identifiers_supplied"])
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(approval_id, serialized)
        self.assertNotIn(transaction_ref, serialized)
        self.assertFalse(result["approval_identifier_exposed"])
        self.assertFalse(result["transaction_identifier_exposed"])

    def test_transaction_auto_resume_succeeded_tail_is_content_free(self) -> None:
        with self.assertRaises(ExactHumanApprovalWorkflowError):
            execute_exact_human_approved_write(
                self.root,
                self.context,
                lambda _claim: {"ok": True},
                native=_Native((APPROVE_BUTTON_ID, True)),
                key_provider=_KeyProvider(),
                claim_succeeded_finalizer=lambda _claim: (
                    _ for _ in ()
                ).throw(RuntimeError("hard exit")),
            )
        approval_id = next(
            (self.root / CLAIMS_RELATIVE_ROOT).glob("*.json")
        ).stem
        events: list[str] = []

        result = resume_exact_human_approved_transaction_auto(
            self.root,
            self.context,
            lambda _claim: False,
            lambda _claim: (_ for _ in ()).throw(
                AssertionError("succeeded resume re-entered writer")
            ),
            lambda claim: claim.status == "succeeded",
            lambda claim: events.append("tail_" + claim.status),
            key_provider=_KeyProvider(),
            resume_boundary=self._resume_boundary,
        )

        self.assertEqual(events, ["tail_succeeded"])
        self.assertEqual(
            result["exact_human_approval_resume_branch"],
            "succeeded_tail",
        )
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(approval_id, serialized)
        self.assertNotIn("exact_human_approval", result)
        self.assertNotIn("exact_human_approval_reference", result)
        self.assertFalse(result["approval_identifier_exposed"])
        self.assertFalse(result["transaction_identifier_exposed"])

    def test_transaction_auto_resume_rejects_supplied_id_mismatch_after_discovery(self) -> None:
        started = execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _claim: {"ok": False, "reason_code": "interrupted"},
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
        )
        approval_id = started["exact_human_approval"]["approval_id"]
        replacement = "0" if approval_id[-1] != "0" else "1"
        mismatched_approval_id = approval_id[:-1] + replacement
        guard_calls = 0
        writer_calls = 0
        provider = _KeyProvider()

        def guard(_claim) -> bool:
            nonlocal guard_calls
            guard_calls += 1
            return True

        def writer(_claim):
            nonlocal writer_calls
            writer_calls += 1
            return {"ok": True}

        with self.assertRaises(ExactHumanApprovalWorkflowError) as mismatch:
            resume_exact_human_approved_transaction_auto(
                self.root,
                self.context,
                guard,
                writer,
                lambda _claim: True,
                lambda _claim: None,
                supplied_approval_id=mismatched_approval_id,
                key_provider=provider,
                resume_boundary=self._resume_boundary,
            )

        self.assertEqual(
            mismatch.exception.code,
            "exact_human_approval_resume_claim_invalid",
        )
        self.assertEqual(guard_calls, 1)
        self.assertEqual(writer_calls, 0)
        self.assertEqual(provider.create_if_missing, [False])

    def test_transaction_auto_resume_supplied_id_cannot_select_one_ambiguous_candidate(self) -> None:
        approval_ids: list[str] = []
        for _index in range(2):
            started = execute_exact_human_approved_write(
                self.root,
                self.context,
                lambda _claim: {
                    "ok": False,
                    "reason_code": "interrupted",
                },
                native=_Native((APPROVE_BUTTON_ID, True)),
                key_provider=_KeyProvider(),
            )
            approval_ids.append(
                started["exact_human_approval"]["approval_id"]
            )
        guard_calls = 0
        writer_calls = 0

        def guard(_claim) -> bool:
            nonlocal guard_calls
            guard_calls += 1
            return True

        def writer(_claim):
            nonlocal writer_calls
            writer_calls += 1
            return {"ok": True}

        with self.assertRaises(ExactHumanApprovalWorkflowError) as ambiguous:
            resume_exact_human_approved_transaction_auto(
                self.root,
                self.context,
                guard,
                writer,
                lambda _claim: True,
                lambda _claim: None,
                supplied_approval_id=approval_ids[0],
                key_provider=_KeyProvider(),
                resume_boundary=self._resume_boundary,
            )

        self.assertEqual(
            ambiguous.exception.code,
            "exact_human_approval_resume_candidate_ambiguous",
        )
        self.assertEqual(guard_calls, 2)
        self.assertEqual(writer_calls, 0)

    def test_transaction_auto_resume_candidate_missing_handler_runs_inside_key_and_filesystem_boundaries(
        self,
    ) -> None:
        (self.root / CLAIMS_RELATIVE_ROOT).mkdir(parents=True)
        events: list[str] = []

        @contextmanager
        def ordered_boundary():
            events.append("filesystem_enter")
            try:
                with self._resume_boundary() as boundary:
                    yield boundary
            finally:
                events.append("filesystem_exit")

        class OrderedKeyProvider:
            def use_key(
                self,
                _root: Path | str,
                consumer: Callable[[memoryview], Any],
                *,
                create_if_missing: bool = False,
            ) -> Any:
                if create_if_missing:
                    raise AssertionError("resume must not create key material")
                events.append("key_enter")
                key = bytearray(range(32))
                try:
                    return consumer(memoryview(key))
                finally:
                    key[:] = b"\0" * len(key)
                    events.append("key_exit")

        def handle_missing(reason: str) -> dict[str, Any]:
            self.assertEqual(reason, "authenticated_candidate_missing")
            self.assertEqual(events, ["filesystem_enter", "key_enter"])
            events.append("handler")
            return {
                "ok": True,
                "status": "claimless_recovery_completed",
                "operator_resume_identifiers_supplied": True,
            }

        result = resume_exact_human_approved_transaction_auto(
            self.root,
            self.context,
            lambda _claim: True,
            lambda _claim: {"ok": True},
            lambda _claim: True,
            lambda _claim: None,
            candidate_missing_handler=handle_missing,
            key_provider=OrderedKeyProvider(),
            resume_boundary=ordered_boundary,
        )

        self.assertEqual(
            events,
            [
                "filesystem_enter",
                "key_enter",
                "handler",
                "key_exit",
                "filesystem_exit",
            ],
        )
        self.assertEqual(result["status"], "claimless_recovery_completed")
        self.assertTrue(result["operator_resume_identifiers_supplied"])
        self.assertTrue(result["automatic_resume_discovery"])
        self.assertEqual(
            result["resume_discovery"]["authenticated_candidate_count"],
            0,
        )
        self.assertTrue(
            result["resume_discovery"]
            ["checkpoint_chain_validated_read_only"]
        )

    def test_transaction_auto_resume_supplied_id_blocks_zero_candidate_handler_inside_boundaries(
        self,
    ) -> None:
        (self.root / CLAIMS_RELATIVE_ROOT).mkdir(parents=True)
        events: list[str] = []
        handler_calls = 0

        @contextmanager
        def ordered_boundary():
            events.append("filesystem_enter")
            try:
                with self._resume_boundary() as boundary:
                    yield boundary
            finally:
                events.append("filesystem_exit")

        class OrderedKeyProvider:
            def use_key(
                self,
                _root: Path | str,
                consumer: Callable[[memoryview], Any],
                *,
                create_if_missing: bool = False,
            ) -> Any:
                if create_if_missing:
                    raise AssertionError("resume must not create key material")
                events.append("key_enter")
                key = bytearray(range(32))
                try:
                    return consumer(memoryview(key))
                finally:
                    key[:] = b"\0" * len(key)
                    events.append("key_exit")

        def handle_missing(_reason: str) -> dict[str, Any]:
            nonlocal handler_calls
            handler_calls += 1
            events.append("handler")
            return {"ok": True, "status": "must_not_run"}

        with self.assertRaises(ExactHumanApprovalWorkflowError) as invalid:
            resume_exact_human_approved_transaction_auto(
                self.root,
                self.context,
                lambda _claim: True,
                lambda _claim: {"ok": True},
                lambda _claim: True,
                lambda _claim: None,
                supplied_approval_id="approval_" + "a" * 32,
                candidate_missing_handler=handle_missing,
                key_provider=OrderedKeyProvider(),
                resume_boundary=ordered_boundary,
            )

        self.assertEqual(
            invalid.exception.code,
            "exact_human_approval_resume_claim_invalid",
        )
        self.assertEqual(handler_calls, 0)
        self.assertEqual(
            events,
            [
                "filesystem_enter",
                "key_enter",
                "key_exit",
                "filesystem_exit",
            ],
        )
        self.assertEqual(
            list((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json")),
            [],
        )

    def test_transaction_auto_resume_candidate_missing_handler_supports_absent_claim_store(
        self,
    ) -> None:
        provider = _KeyProvider()
        reasons: list[str] = []

        result = resume_exact_human_approved_transaction_auto(
            self.root,
            self.context,
            lambda _claim: True,
            lambda _claim: {"ok": True},
            lambda _claim: True,
            lambda _claim: None,
            candidate_missing_handler=lambda reason: (
                reasons.append(reason) is None
                and {"ok": True, "status": "absent_store_handled"}
            ),
            key_provider=provider,
            resume_boundary=self._resume_boundary,
        )

        self.assertEqual(reasons, ["claim_store_absent"])
        self.assertEqual(provider.calls, 0)
        self.assertEqual(result["status"], "absent_store_handled")
        self.assertFalse(
            result["resume_discovery"]
            ["checkpoint_chain_validated_read_only"]
        )
        self.assertFalse((self.root / "profiles").exists())

    def test_transaction_auto_resume_candidate_missing_handler_requires_boolean_ok_mapping(
        self,
    ) -> None:
        (self.root / CLAIMS_RELATIVE_ROOT).mkdir(parents=True)
        invalid_results: tuple[Any, ...] = (
            [],
            {"ok": "true"},
        )

        for invalid_result in invalid_results:
            with self.subTest(invalid_result=invalid_result):
                with self.assertRaises(
                    ExactHumanApprovalWorkflowError
                ) as invalid:
                    resume_exact_human_approved_transaction_auto(
                        self.root,
                        self.context,
                        lambda _claim: True,
                        lambda _claim: {"ok": True},
                        lambda _claim: True,
                        lambda _claim: None,
                        candidate_missing_handler=(
                            lambda _reason, result=invalid_result: result
                        ),
                        key_provider=_KeyProvider(),
                        resume_boundary=self._resume_boundary,
                    )
                self.assertEqual(
                    invalid.exception.code,
                    "exact_human_approval_state_unknown",
                )

    def test_transaction_auto_resume_missing_claim_creates_nothing(self) -> None:
        provider = _KeyProvider()
        with self.assertRaises(ExactHumanApprovalWorkflowError) as missing:
            resume_exact_human_approved_transaction_auto(
                self.root,
                self.context,
                lambda _claim: True,
                lambda _claim: {"ok": True},
                lambda _claim: True,
                lambda _claim: None,
                key_provider=provider,
                resume_boundary=self._resume_boundary,
            )
        self.assertEqual(
            missing.exception.code,
            "exact_human_approval_resume_candidate_missing",
        )
        self.assertEqual(provider.create_if_missing, [])
        self.assertFalse((self.root / "profiles").exists())

    def test_transaction_auto_resume_rejects_ambiguous_candidates_without_writer(self) -> None:
        for _index in range(2):
            execute_exact_human_approved_write(
                self.root,
                self.context,
                lambda _claim: {
                    "ok": False,
                    "reason_code": "interrupted",
                },
                native=_Native((APPROVE_BUTTON_ID, True)),
                key_provider=_KeyProvider(),
            )
        writer_calls = 0

        def writer(_claim):
            nonlocal writer_calls
            writer_calls += 1
            return {"ok": True}

        with self.assertRaises(ExactHumanApprovalWorkflowError) as ambiguous:
            resume_exact_human_approved_transaction_auto(
                self.root,
                self.context,
                lambda _claim: True,
                writer,
                lambda _claim: True,
                lambda _claim: None,
                key_provider=_KeyProvider(),
                resume_boundary=self._resume_boundary,
            )
        self.assertEqual(
            ambiguous.exception.code,
            "exact_human_approval_resume_candidate_ambiguous",
        )
        self.assertEqual(writer_calls, 0)
        self.assertEqual(
            len(list((self.root / CLAIMS_RELATIVE_ROOT).glob("*.json"))),
            2,
        )

    def test_transaction_auto_resume_rejects_tampered_lookalike_as_invalid(self) -> None:
        execute_exact_human_approved_write(
            self.root,
            self.context,
            lambda _claim: {
                "ok": False,
                "reason_code": "interrupted",
            },
            native=_Native((APPROVE_BUTTON_ID, True)),
            key_provider=_KeyProvider(),
        )
        claim_path = next(
            (self.root / CLAIMS_RELATIVE_ROOT).glob("*.json")
        )
        raw = claim_path.read_bytes()
        claim_path.write_bytes(
            raw.replace(b'"status":"started"', b'"status":"failed"', 1)
        )
        writer_calls = 0

        def writer(_claim):
            nonlocal writer_calls
            writer_calls += 1
            return {"ok": True}

        with self.assertRaises(ExactHumanApprovalWorkflowError) as invalid:
            resume_exact_human_approved_transaction_auto(
                self.root,
                self.context,
                lambda _claim: True,
                writer,
                lambda _claim: True,
                lambda _claim: None,
                key_provider=_KeyProvider(),
                resume_boundary=self._resume_boundary,
            )
        self.assertEqual(
            invalid.exception.code,
            "exact_human_approval_resume_claim_invalid",
        )
        self.assertEqual(writer_calls, 0)

    def test_transaction_resume_routes_authenticated_succeeded_claim_to_tail(self) -> None:
        with self.assertRaises(ExactHumanApprovalWorkflowError):
            execute_exact_human_approved_write(
                self.root,
                self.context,
                lambda _claim: {"ok": True},
                native=_Native((APPROVE_BUTTON_ID, True)),
                key_provider=_KeyProvider(),
                claim_succeeded_finalizer=lambda _claim: (_ for _ in ()).throw(
                    RuntimeError("hard exit")
                ),
            )
        approval_id = next(
            (self.root / CLAIMS_RELATIVE_ROOT).glob("*.json")
        ).stem
        events: list[str] = []

        def writer(_claim):
            events.append("writer_must_not_run")
            return {"ok": True}

        result = resume_exact_human_approved_transaction(
            self.root,
            self.context,
            approval_id,
            lambda _claim: False,
            writer,
            lambda claim: (
                events.append("succeeded_guard") is None
                and claim.status == "succeeded"
            ),
            lambda claim: events.append("tail_" + claim.status),
            key_provider=_KeyProvider(),
        )
        self.assertEqual(events, ["succeeded_guard", "tail_succeeded"])
        self.assertEqual(
            result["exact_human_approval_resume_branch"], "succeeded_tail"
        )
        self.assertFalse(result["domain_writer_reentered"])
        self.assertFalse(result["native_approval_redisplayed"])

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
                lambda _claim: False,
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
                lambda _claim: True,
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
                lambda _claim: True,
                lambda _claim: {"ok": True},
                key_provider=_KeyProvider(),
            )
        self.assertEqual(
            tampered.exception.code,
            "exact_human_approval_resume_claim_invalid",
        )

    def test_workflow_error_carries_only_code_shaped_inner_cause(self) -> None:
        plain = ExactHumanApprovalWorkflowError("exact_human_approval_state_unknown")
        self.assertIsNone(plain.cause_code)
        self.assertIsNone(plain.cause_stage)
        self.assertEqual(plain.args, ("exact_human_approval_state_unknown",))

        carried = ExactHumanApprovalWorkflowError(
            "exact_human_approval_state_unknown",
            cause_code="project_version_update_preapproval_recovery_failed",
            cause_stage="candidate_missing_handler",
        )
        self.assertEqual(
            carried.cause_code,
            "project_version_update_preapproval_recovery_failed",
        )
        self.assertEqual(carried.cause_stage, "candidate_missing_handler")
        self.assertEqual(str(carried), "exact_human_approval_state_unknown")
        self.assertEqual(
            repr(carried),
            "ExactHumanApprovalWorkflowError('exact_human_approval_state_unknown')",
        )

        rejected = ExactHumanApprovalWorkflowError(
            "exact_human_approval_state_unknown",
            cause_code=r"C:\private\path secret",
            cause_stage="unknown_stage",
        )
        self.assertIsNone(rejected.cause_code)
        self.assertIsNone(rejected.cause_stage)

    def test_transaction_auto_resume_candidate_missing_handler_keeps_fixed_inner_cause(
        self,
    ) -> None:
        (self.root / CLAIMS_RELATIVE_ROOT).mkdir(parents=True)
        cases = (
            (
                "fixed_service_code",
                archive_services.ArchiveServiceError(
                    "project_version_update_preapproval_recovery_failed"
                ),
                "project_version_update_preapproval_recovery_failed",
            ),
            (
                "private_service_text",
                archive_services.ArchiveServiceError(
                    r"C:\private-owner\archive\secret.md PRIVATE-BODY"
                ),
                None,
            ),
            (
                "two_argument_service_error",
                archive_services.ArchiveServiceError(
                    "project_version_update_preapproval_recovery_failed",
                    "extra",
                ),
                None,
            ),
            (
                "other_exception_type",
                ValueError("project_version_update_preapproval_recovery_failed"),
                None,
            ),
        )

        def raising_handler(failure):
            def handle(_reason):
                raise failure

            return handle

        for case, failure, expected in cases:
            with self.subTest(case=case):
                with self.assertRaises(ExactHumanApprovalWorkflowError) as caught:
                    resume_exact_human_approved_transaction_auto(
                        self.root,
                        self.context,
                        lambda _claim: True,
                        lambda _claim: {"ok": True},
                        lambda _claim: True,
                        lambda _claim: None,
                        candidate_missing_handler=raising_handler(failure),
                        key_provider=_KeyProvider(),
                        resume_boundary=self._resume_boundary,
                    )
                self.assertEqual(
                    caught.exception.code,
                    "exact_human_approval_state_unknown",
                )
                self.assertEqual(caught.exception.cause_code, expected)
                self.assertEqual(
                    caught.exception.cause_stage,
                    "candidate_missing_handler",
                )
                self.assertIsNone(caught.exception.__cause__)
                self.assertNotIn("private-owner", str(caught.exception))
                self.assertNotIn("PRIVATE-BODY", repr(caught.exception))


if __name__ == "__main__":
    unittest.main()
