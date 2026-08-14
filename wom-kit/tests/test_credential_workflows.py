from __future__ import annotations

import copy
import ctypes
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pickle
import tempfile
import threading
import unittest
from unittest.mock import patch
import uuid

import wom_kit.credential_workflows as credential_workflows
from wom_kit.credential_secure_intake import (
    AtomicJsonReceiptCommitter,
    HumanSecretInputResult,
    NOTION_PAT_SCOPE_FINGERPRINT_DOMAIN,
    NOTION_PAT_WORKSPACE_IDENTITY_BASIS,
)
from wom_kit.credential_secure_registry import (
    _receipt_mac,
    RECEIPT_AUTHENTICATION_SCHEMA,
    StableArchiveFingerprintKeyProvider,
)
from wom_kit.credential_workflows import (
    CredentialAdoptionWorkerInvocation,
    InjectedCredentialAdoptionWorkerSpawner,
    InjectedNotionRecoveryWorkerSpawner,
    approve_authenticated_credential_lifecycle,
    execute_authenticated_notion_page_recovery,
    execute_spawned_authenticated_notion_page_recovery,
    execute_windows_notion_credential_adoption,
    list_authenticated_secure_credentials,
    plan_authenticated_credential_lifecycle,
    plan_secure_credential_adoption,
)
from wom_kit.notion_http_adapter import NOTION_API_VERSION, NotionHttpAdapter
from wom_kit.notion_page_recovery import REQUEST_SCHEMA, plan_recovery


NOW = datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)
ARCHIVE_ID = "archive:test"
SID = "S-1-5-21-111111111-222222222-333333333-1001"
ANCHOR = str(uuid.UUID(int=101))
OTHER_ANCHOR = str(uuid.UUID(int=102))
USER_ID = str(uuid.UUID(int=202))
PAGE_ID = str(uuid.UUID(int=303))
WORKSPACE_ID = str(uuid.UUID(int=404))
REQUEST_ID = "intake_workflow1234567890"
CREDENTIAL_ID = "cred_workflow1234567890"
BACKEND_ID = "backend_workflow1234567890"
SECRET_TEXT = "synthetic_notion_pat_only_in_worker"
ARCHIVE_KEY = b"k" * 32
CAPABILITIES = (
    "read_content",
    "retrieve_page",
    "retrieve_page_as_markdown",
)


class SecretStr(str):
    """Pickle-safe hostile child string carrying secret-adjacent state."""

    def __new__(cls, value: str, secret: str | None = None):
        instance = super().__new__(cls, value)
        instance.secret = secret
        return instance

    def __repr__(self) -> str:
        return f"<SecretStr leaked={self.secret!r}>"

ZERO_LIVE_OPERATIONS = {
    "native_calls": 0,
    "provider_calls": 0,
    "credential_store_reads": 0,
    "credential_store_writes": 0,
    "archive_writes": 0,
}
APPROVED_WORKER_OPERATIONS_UNKNOWN = {
    "live_operation_boundary": "approved_worker_execution_entered",
    "count_status": "unknown_may_be_nonzero",
    "native_calls": None,
    "provider_calls": None,
    "credential_store_reads": None,
    "credential_store_writes": None,
    "archive_writes": None,
}
AUTHENTICATED_KEY_READ_OPERATIONS_UNKNOWN = {
    "live_operation_boundary": "authenticated_archive_key_access_entered",
    "count_status": "unknown_may_be_nonzero",
    "native_calls": None,
    "provider_calls": 0,
    "credential_store_reads": None,
    "credential_store_writes": 0,
    "archive_writes": 0,
}
AUTHENTICATED_KEY_WRITE_OPERATIONS_UNKNOWN = {
    **AUTHENTICATED_KEY_READ_OPERATIONS_UNKNOWN,
    "archive_writes": None,
}
RECOVERY_PRIVACY_GUARDS = {
    "token_echoed": False,
    "provider_body_echoed": False,
    "page_title_echoed": False,
    "email_echoed": False,
    "provider_url_echoed": False,
    "raw_cursor_echoed": False,
    "raw_cursor_persisted": False,
    "rate_limiter_clock_echoed": False,
}


class FakeResponse:
    def __init__(self, payload: dict[str, object], status: int = 200) -> None:
        self.status = status
        self.headers: dict[str, str] = {}
        self.raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def read(self, _size: int = -1) -> bytes:
        return self.raw

    def close(self) -> None:
        pass


class FakeTransport:
    def __init__(self, outcomes: list[FakeResponse]) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    def open(self, request, *, timeout: float):
        self.calls.append(request.full_url)
        if not self.outcomes:
            raise AssertionError("unexpected provider call")
        return self.outcomes.pop(0)


class FailIfRecoveryWorkerRuns:
    def run_worker(self, _invocation):
        raise AssertionError("verified replay must not spawn a live worker")


@dataclass
class StaticRecoveryWorkerSpawner:
    result: object
    calls: int = 0

    def run_worker(self, _invocation):
        self.calls += 1
        return self.result


class RaisingRecoveryWorkerSpawner:
    def run_worker(self, _invocation):
        raise RuntimeError("synthetic worker boundary failure")


class NotStartedRecoveryWorkerSpawner:
    def run_worker(self, _invocation):
        return credential_workflows._NotionRecoveryWorkerRunOutcome(
            worker_started=False
        )


@dataclass
class FakeWindowsNative:
    cancelled: bool = False
    secret_text: str = SECRET_TEXT
    delete_fails: bool = False
    probe_fails: bool = False
    secret_write_fails: bool = False
    probe_fail_targets: set[str] = field(default_factory=set, repr=False)
    read_fail_targets: set[str] = field(default_factory=set, repr=False)
    values: dict[str, bytearray] = field(default_factory=dict, repr=False)
    writes: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    probes: list[str] = field(default_factory=list)
    prompts: int = 0
    sid_reads: int = 0

    def prompt_masked_secret(
        self, *, request_id: str, context=None
    ) -> HumanSecretInputResult:
        self.prompts += 1
        if self.cancelled:
            return HumanSecretInputResult(
                secret=None,
                credential_input_received=True,
                complete_line_received=True,
                cancelled=True,
            )
        return HumanSecretInputResult(
            secret=bytearray(self.secret_text.encode("utf-8")),
            credential_input_received=True,
            complete_line_received=True,
            cancelled=False,
        )

    def write_generic(self, target_name: str, secret: memoryview) -> None:
        self.writes.append(target_name)
        if (
            self.secret_write_fails
            and "/backend_" in target_name
            and "backend_key_" not in target_name
        ):
            raise RuntimeError("synthetic secret write failure must not escape")
        self.values[target_name] = bytearray(secret)

    def generic_exists(self, target_name: str) -> bool:
        self.probes.append(target_name)
        if (
            self.probe_fails
            or target_name in self.probe_fail_targets
        ):
            raise RuntimeError("synthetic probe detail must not escape")
        return target_name in self.values

    def read_generic_secret_exact(self, target_name: str) -> bytearray:
        self.reads.append(target_name)
        if target_name in self.read_fail_targets:
            raise RuntimeError("synthetic read detail must not escape")
        return bytearray(self.values[target_name])

    def delete_generic(self, target_name: str) -> None:
        if self.delete_fails:
            raise RuntimeError("synthetic native detail must not escape")
        self.values.pop(target_name, None)

    def current_user_sid(self) -> str:
        self.sid_reads += 1
        return SID


@dataclass
class RecordingSpawner:
    result: dict[str, object] = field(default_factory=lambda: {"ok": True})
    calls: int = 0
    invocations: list[CredentialAdoptionWorkerInvocation] = field(default_factory=list)

    def run_worker(self, invocation: CredentialAdoptionWorkerInvocation):
        self.calls += 1
        self.invocations.append(invocation)
        return self.result


class NotStartedCredentialAdoptionSpawner:
    def run_worker(self, _invocation):
        return credential_workflows._CredentialAdoptionWorkerRunOutcome(
            worker_started=False
        )


@dataclass
class ArchiveIdentityMutatingKeyProvider:
    archive_root: Path

    def use_key(self, _archive_root, consumer, *, create_if_missing: bool = False):
        if create_if_missing is not True:
            raise AssertionError("adoption must request key initialization or reuse")
        (self.archive_root / "archive.yml").write_text(
            "archive_id: archive:changed-during-key-handoff\n",
            encoding="utf-8",
        )
        key = bytearray(ARCHIVE_KEY)
        try:
            return consumer(memoryview(key))
        finally:
            for index in range(len(key)):
                key[index] = 0


class NoOpPacer:
    def __init__(self) -> None:
        self.calls = 0

    def before_request(self) -> None:
        self.calls += 1


def make_archive(base: Path) -> Path:
    root = base / "archive"
    root.mkdir(parents=True)
    (root / ".gitignore").write_text("profiles/local/\n", encoding="utf-8")
    (root / "archive.yml").write_text("archive_id: archive:test\n", encoding="utf-8")
    return root


def intake_transport(
    *,
    include_recovery: bool = False,
    anchor: str = ANCHOR,
    person: bool = False,
) -> FakeTransport:
    identity = (
        {
            "object": "user",
            "id": USER_ID,
            "type": "person",
            "person": {},
        }
        if person
        else {
            "object": "user",
            "id": USER_ID,
            "type": "bot",
            "bot": {"workspace_id": WORKSPACE_ID},
        }
    )
    outcomes = [
        FakeResponse(identity),
        FakeResponse(
            {
                "object": "page",
                "id": anchor,
                "last_edited_time": "2026-08-10T00:00:00.000Z",
                "in_trash": False,
            }
        ),
    ]
    if include_recovery:
        metadata = {
            "object": "page",
            "id": PAGE_ID,
            "last_edited_time": "2026-08-10T01:00:00.000Z",
            "in_trash": False,
        }
        outcomes.extend(
            [
                FakeResponse(metadata),
                FakeResponse(
                    {
                        "object": "page_markdown",
                        "id": PAGE_ID,
                        "markdown": "# reviewed original\n\nexact body\n",
                        "truncated": False,
                        "unknown_block_ids": [],
                    }
                ),
                FakeResponse(metadata),
            ]
        )
    return FakeTransport(outcomes)


def make_plan(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "expected_archive_id": ARCHIVE_ID,
        "account_label": "organization account",
        "workspace_label": "reviewed workspace",
        "purpose": "source_recovery",
        "task_summary": "검토한 Notion 페이지를 WOM 아카이브로 복구하고 있습니다.",
        "connection_reason": "복구를 계속하려면 해당 Notion 작업공간 연결을 확인해야 합니다.",
        "reviewed_anchor_uuid": ANCHOR,
        "requested_capabilities": CAPABILITIES,
        "ttl_seconds": 300,
        "now": NOW,
        "request_id_factory": lambda: REQUEST_ID,
    }
    values.update(overrides)
    return plan_secure_credential_adoption(**values)


def make_manifest(scope_binding: dict[str, object]) -> dict[str, object]:
    return {
        "schema": REQUEST_SCHEMA,
        "batch_id": "letter118-reviewed-page-pilot",
        "archive_id": "archive:test",
        "expected_item_count": 1,
        "groups": [
            {
                "group_id": "group-org",
                "expected_count": 1,
                "scope_binding": scope_binding,
            }
        ],
        "items": [
            {"item_id": "reviewed-0001", "group_id": "group-org", "page_id": PAGE_ID}
        ],
    }


def make_valid_recovery_worker_result(preview: dict[str, object]) -> dict[str, object]:
    return {
        "ok": True,
        "dry_run": False,
        "lifecycle_action": "notion_page_recovery_execute",
        "status_class": "written",
        "reason_code": "notion_page_recovery_written",
        "request_sha256": preview["request_sha256"],
        "plan_sha256": preview["plan_sha256"],
        "counts": {
            "input_item_count": 1,
            "selected_item_count": 1,
            "processed_item_count": 1,
            "pending_item_count": 0,
            "unselected_item_count": 0,
            "replayed_recovered_count": 0,
            "outcomes": {
                "recovered": 1,
                "deleted": 0,
                "forbidden": 0,
                "not_found_or_not_shared": 0,
                "retryable_error": 0,
                "partial": 0,
            },
            "total_accounted_count": 1,
        },
        "operations": {
            "provider_calls": 3,
            "paced_request_count": 3,
            "credential_resolution_attempts": 1,
            "credential_reads": 1,
            "retry_count": 0,
            "sleep_seconds": 0.0,
            "objects_created": 1,
            "manifest_rows_created": 1,
            "projection_rows_created": 1,
            "resume_rows_created": 2,
        },
        "receipt_created": True,
        "privacy_guards": dict(RECOVERY_PRIVACY_GUARDS),
        "blockers": [],
    }


class CredentialWorkflowPlanningTests(unittest.TestCase):
    def test_plan_is_content_free_write_free_and_hides_exact_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            untouched = Path(temporary) / "must-not-exist"
            result = make_plan()

            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            self.assertFalse(untouched.exists())
            self.assertEqual(result["operations"], ZERO_LIVE_OPERATIONS)
            self.assertIn(
                "archive_scoped_authentication_key_initialize_or_reuse",
                result["approved_execution_steps"],
            )
            self.assertEqual(result["expected_archive_id"], ARCHIVE_ID)
            self.assertEqual(
                result["interaction_context"]["task_summary"],
                "검토한 Notion 페이지를 WOM 아카이브로 복구하고 있습니다.",
            )
            self.assertRegex(
                result["interaction_context_sha256"],
                r"^sha256:[0-9a-f]{64}$",
            )
            rendered = json.dumps(result, ensure_ascii=False, sort_keys=True)
            self.assertNotIn(ANCHOR, rendered)
            self.assertNotIn(SECRET_TEXT, rendered)
            self.assertNotIn("reviewed_anchor_uuid", rendered)
            self.assertTrue(result["intake_plan"]["reviewed_anchor_present"])

    def test_core_public_label_policy_rejects_secret_shapes_without_echo(self) -> None:
        unsafe = "token=synthetic-private-value"
        result = make_plan(account_label=unsafe)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], "credential_adoption_plan_invalid")
        self.assertNotIn(unsafe, json.dumps(result, ensure_ascii=False))

        for private_context in (
            "ntn_" + "A" * 32,
            "https://example.invalid/private-page",
            "C:\\private\\credential.txt",
        ):
            with self.subTest(private_context=private_context[:8]):
                context_result = make_plan(task_summary=private_context)
                rendered = json.dumps(context_result, ensure_ascii=False)
                self.assertFalse(context_result["ok"])
                self.assertEqual(
                    context_result["reason_code"],
                    "credential_adoption_plan_invalid",
                )
                self.assertNotIn(private_context, rendered)

    def test_not_approved_and_plan_drift_block_before_worker_spawn(self) -> None:
        plan = make_plan()
        spawner = RecordingSpawner()
        blocked = execute_windows_notion_credential_adoption(
            "not-even-inspected",
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=False,
            worker_spawner=spawner,
        )
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["reason_code"], "credential_adoption_approval_required")
        self.assertEqual(blocked["operations"], ZERO_LIVE_OPERATIONS)
        self.assertEqual(spawner.calls, 0)

        drifted = execute_windows_notion_credential_adoption(
            "not-even-inspected",
            plan,
            expected_plan_digest="0" * 64,
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=spawner,
        )
        self.assertFalse(drifted["ok"])
        self.assertEqual(drifted["reason_code"], "credential_adoption_plan_digest_mismatch")
        self.assertEqual(drifted["operations"], ZERO_LIVE_OPERATIONS)
        self.assertEqual(spawner.calls, 0)

        hidden_anchor_drift = execute_windows_notion_credential_adoption(
            "not-even-inspected",
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=str(uuid.UUID(int=999)),
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=spawner,
        )
        self.assertFalse(hidden_anchor_drift["ok"])
        self.assertEqual(hidden_anchor_drift["operations"], ZERO_LIVE_OPERATIONS)
        self.assertEqual(spawner.calls, 0)

        execution_contract_drift = dict(plan)
        execution_contract_drift["approved_execution_steps"] = [
            "masked_human_secret_intake"
        ]
        contract_blocked = execute_windows_notion_credential_adoption(
            "not-even-inspected",
            execution_contract_drift,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=spawner,
        )
        self.assertFalse(contract_blocked["ok"])
        self.assertEqual(
            contract_blocked["reason_code"],
            "credential_adoption_plan_digest_mismatch",
        )
        self.assertEqual(contract_blocked["operations"], ZERO_LIVE_OPERATIONS)
        self.assertEqual(spawner.calls, 0)

        archive_contract_drift = dict(plan)
        archive_contract_drift["expected_archive_id"] = "archive:unreviewed"
        archive_blocked = execute_windows_notion_credential_adoption(
            "not-even-inspected",
            archive_contract_drift,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=spawner,
        )
        self.assertFalse(archive_blocked["ok"])
        self.assertEqual(
            archive_blocked["reason_code"],
            "credential_adoption_plan_digest_mismatch",
        )
        self.assertEqual(archive_blocked["operations"], ZERO_LIVE_OPERATIONS)
        self.assertEqual(spawner.calls, 0)

        context_contract_drift = dict(plan)
        context_contract_drift["interaction_context"] = dict(
            plan["interaction_context"]
        )
        context_contract_drift["interaction_context"]["task_summary"] = (
            "승인되지 않은 다른 작업을 진행하고 있습니다."
        )
        context_blocked = execute_windows_notion_credential_adoption(
            "not-even-inspected",
            context_contract_drift,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=spawner,
        )
        self.assertFalse(context_blocked["ok"])
        self.assertEqual(
            context_blocked["reason_code"],
            "credential_adoption_plan_digest_mismatch",
        )
        self.assertEqual(spawner.calls, 0)

    def test_parent_rejects_arbitrary_or_nested_worker_output(self) -> None:
        plan = make_plan()
        malicious = RecordingSpawner(
            result={
                "ok": True,
                "credential": {"raw_secret": SECRET_TEXT},
            }
        )
        result = execute_windows_notion_credential_adoption(
            ".",
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=malicious,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(
            result["reason_code"], "credential_adoption_worker_state_unknown"
        )
        self.assertIsNone(result["accepted"])
        self.assertIsNone(result["persisted"])
        self.assertEqual(result["durable_state"], "unknown_may_have_changed")
        self.assertEqual(
            result["operator_action"],
            "reconcile_then_rerun_same_approved_command_and_plan",
        )
        self.assertEqual(result["operations"], APPROVED_WORKER_OPERATIONS_UNKNOWN)
        self.assertNotIn(SECRET_TEXT, json.dumps(result, ensure_ascii=False))

        forged_failure = credential_workflows._approved_adoption_worker_failure(
            "human_cancelled",
            accepted=True,
            persisted=True,
        )
        forged = execute_windows_notion_credential_adoption(
            ".",
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=RecordingSpawner(result=forged_failure),
        )
        self.assertEqual(
            forged["reason_code"], "credential_adoption_worker_state_unknown"
        )
        self.assertIsNone(forged["accepted"])
        self.assertIsNone(forged["persisted"])

    def test_adoption_projection_binds_reason_stage_and_rollback_exactly(self) -> None:
        def stage(bits: str) -> dict[str, bool]:
            return dict(
                zip(
                    (
                        "credential_input_received",
                        "complete_line_received",
                        "temporary_store_write_attempted",
                        "provider_request_attempted",
                    ),
                    (bit == "1" for bit in bits),
                    strict=True,
                )
            )

        valid_cases = (
            ("credential_input_not_received", "0000", "not_required", False),
            ("credential_input_not_received", "1000", "not_required", False),
            ("secret_input_unavailable", "0000", "not_required", False),
            ("credential_input_cancelled_or_empty", "0000", "not_required", False),
            ("credential_input_cancelled_or_empty", "1000", "not_required", False),
            ("credential_input_cancelled_or_empty", "1100", "not_required", False),
            ("credential_input_invalid_for_provider", "1100", "not_required", False),
            ("credential_input_boundary_failed", "1000", "not_required", False),
            ("credential_input_boundary_failed", "1100", "not_required", False),
            ("human_cancelled", "0000", "not_required", False),
            ("store_write_failed", "1110", "deleted", False),
            ("store_presence_not_verified", "1110", "delete_failed", False),
            ("provider_request_not_attempted", "1110", "deleted", False),
            ("provider_auth_rejected", "1111", "deleted", False),
            ("provider_identity_endpoint_unavailable", "1111", "delete_failed", False),
            ("reviewed_anchor_inaccessible", "1111", "deleted", False),
            ("provider_identity_unverified", "1111", "deleted", False),
            ("workspace_anchor_mismatch", "1111", "deleted", False),
            ("receipt_commit_failed", "1111", "deleted", False),
            ("request_expired", "0000", "not_required", False),
            ("request_replayed", "0000", "not_required", False),
            ("request_user_mismatch", "0000", "not_required", False),
            ("request_claim_failed", "0000", "not_required", False),
            ("plan_digest_mismatch", "0000", "not_required", False),
            ("credential_adoption_archive_identity_mismatch", "0000", "not_required", False),
            ("credential_adoption_existing_store_missing", "0000", "not_required", False),
            ("credential_adoption_existing_scope_revalidation_failed", "0001", "not_required", False),
            ("credential_adoption_archive_identity_changed", "1111", "not_required", True),
            ("credential_adoption_rediscovery_verification_failed", "1111", "not_required", True),
        )
        for reason, bits, rollback, persisted in valid_cases:
            with self.subTest(reason=reason, bits=bits, rollback=rollback):
                child = credential_workflows._approved_adoption_worker_failure(
                    reason,
                    accepted=persisted,
                    persisted=persisted,
                    rollback_status=rollback,
                    **stage(bits),
                )
                projected = credential_workflows._project_adoption_worker_result(
                    child
                )
                self.assertEqual(projected, child)
                self.assertEqual(
                    tuple(projected[field] for field in stage(bits)),
                    tuple(stage(bits).values()),
                )
                self.assertEqual(
                    projected["store_absence_verified"], rollback == "deleted"
                )
                self.assertIs(type(projected["reason_code"]), str)
                self.assertIs(type(projected["rollback_status"]), str)

        expected_new_actions = {
            "credential_input_invalid_for_provider": (
                "enter_a_complete_provider_credential_with_a_new_plan"
            ),
            "credential_input_boundary_failed": (
                "repair_secure_input_boundary_and_create_a_new_plan"
            ),
            "provider_request_not_attempted": (
                "stop_and_review_the_provider_adapter_before_retrying"
            ),
        }
        for reason, action in expected_new_actions.items():
            bits = (
                "1100"
                if reason
                in {
                    "credential_input_invalid_for_provider",
                    "credential_input_boundary_failed",
                }
                else "1110"
            )
            rollback = "not_required" if bits == "1100" else "deleted"
            projected = credential_workflows._project_adoption_worker_result(
                credential_workflows._approved_adoption_worker_failure(
                    reason,
                    rollback_status=rollback,
                    **stage(bits),
                )
            )
            self.assertEqual(projected["operator_action"], action)

        invalid_cases = (
            ("credential_input_invalid_for_provider", "1000", "not_required"),
            ("credential_input_invalid_for_provider", "1110", "deleted"),
            ("credential_input_boundary_failed", "0000", "not_required"),
            ("credential_input_boundary_failed", "1110", "deleted"),
            ("store_write_failed", "1100", "not_required"),
            ("provider_request_not_attempted", "1111", "deleted"),
            ("provider_auth_rejected", "1110", "deleted"),
            ("provider_auth_rejected", "1111", "not_required"),
            ("credential_adoption_existing_scope_revalidation_failed", "1110", "deleted"),
            ("credential_adoption_archive_identity_changed", "1111", "deleted"),
        )
        for reason, bits, rollback in invalid_cases:
            with self.subTest(forged_reason=reason, bits=bits, rollback=rollback):
                forged = credential_workflows._approved_adoption_worker_failure(
                    reason,
                    accepted=(
                        reason == "credential_adoption_archive_identity_changed"
                    ),
                    persisted=(
                        reason == "credential_adoption_archive_identity_changed"
                    ),
                    rollback_status=rollback,
                    **stage(bits),
                )
                projected = credential_workflows._project_adoption_worker_result(
                    forged
                )
                self.assertEqual(
                    projected["reason_code"],
                    "credential_adoption_worker_state_unknown",
                )
                self.assertIsNone(projected["accepted"])
                self.assertIsNone(projected["persisted"])

    def test_adoption_projection_rejects_untrusted_stage_evidence_as_unknown(self) -> None:
        stage_fields = (
            "credential_input_received",
            "complete_line_received",
            "temporary_store_write_attempted",
            "provider_request_attempted",
        )
        valid = credential_workflows._approved_adoption_worker_failure(
            "provider_auth_rejected",
            rollback_status="deleted",
            credential_input_received=True,
            complete_line_received=True,
            temporary_store_write_attempted=True,
            provider_request_attempted=True,
        )
        malformed: list[tuple[str, dict[str, object]]] = []
        for field in stage_fields:
            missing = dict(valid)
            missing.pop(field)
            malformed.append((f"missing_{field}", missing))
        extra = dict(valid)
        extra["untrusted_stage_detail"] = False
        malformed.append(("extra_field", extra))
        old_schema = dict(valid)
        old_schema["schema_version"] = "wom-credential-workflow-result/v0.2"
        malformed.append(("v0.2_child", old_schema))
        for field in stage_fields:
            for value in (0, 1, None, "false"):
                non_bool = dict(valid)
                non_bool[field] = value
                malformed.append((f"{field}_{value!r}", non_bool))

        for label, child in malformed:
            with self.subTest(case=label):
                projected = credential_workflows._project_adoption_worker_result(
                    child
                )
                self.assertEqual(
                    projected["reason_code"],
                    "credential_adoption_worker_state_unknown",
                )
                self.assertEqual(
                    [projected[field] for field in stage_fields],
                    [None, None, None, None],
                )

    def test_adoption_projection_rejects_pickle_roundtrip_secret_string_subclasses(
        self,
    ) -> None:
        stage_fields = (
            "credential_input_received",
            "complete_line_received",
            "temporary_store_write_attempted",
            "provider_request_attempted",
        )

        def assert_unknown_after_transport(
            child: dict[str, object],
            *,
            field: str,
            sentinel: str,
            nested_field: str | None = None,
        ) -> None:
            transported = pickle.loads(pickle.dumps(child))
            transported_value = transported[field]
            if nested_field is not None:
                self.assertIsInstance(transported_value, dict)
                transported_value = transported_value[nested_field]
            self.assertIs(type(transported_value), SecretStr)
            self.assertIn(sentinel, repr(transported))

            projected = credential_workflows._project_adoption_worker_result(
                transported
            )

            self.assertEqual(
                projected["reason_code"],
                "credential_adoption_worker_state_unknown",
            )
            self.assertEqual(
                [projected[stage_field] for stage_field in stage_fields],
                [None, None, None, None],
            )
            public_rendering = repr(projected) + json.dumps(
                projected,
                ensure_ascii=False,
                sort_keys=True,
            )
            self.assertNotIn(sentinel, public_rendering)

        valid_failure = credential_workflows._approved_adoption_worker_failure(
            "provider_auth_rejected",
            rollback_status="deleted",
            credential_input_received=True,
            complete_line_received=True,
            temporary_store_write_attempted=True,
            provider_request_attempted=True,
        )
        for field, value, sentinel in (
            (
                "schema_version",
                credential_workflows.WORKFLOW_RESULT_SCHEMA_VERSION,
                "PRIVATE_SCHEMA_SENTINEL",
            ),
            (
                "lifecycle_action",
                "secure_credential_adoption_execute",
                "PRIVATE_ACTION_SENTINEL",
            ),
            (
                "reason_code",
                "provider_auth_rejected",
                "PRIVATE_REASON_SENTINEL",
            ),
            ("rollback_status", "deleted", "PRIVATE_ROLLBACK_SENTINEL"),
            (
                "operator_action",
                "review_the_notion_credential_and_create_a_new_plan",
                "PRIVATE_OPERATOR_SENTINEL",
            ),
        ):
            with self.subTest(shape="failure", field=field):
                child = dict(valid_failure)
                child[field] = SecretStr(value, sentinel)
                assert_unknown_after_transport(
                    child,
                    field=field,
                    sentinel=sentinel,
                )

        for nested_field, value, sentinel in (
            (
                "live_operation_boundary",
                "approved_worker_execution_entered",
                "PRIVATE_OPERATIONS_BOUNDARY_SENTINEL",
            ),
            (
                "count_status",
                "unknown_may_be_nonzero",
                "PRIVATE_OPERATIONS_COUNT_SENTINEL",
            ),
        ):
            with self.subTest(shape="failure", field=f"operations.{nested_field}"):
                child = dict(valid_failure)
                operations = dict(APPROVED_WORKER_OPERATIONS_UNKNOWN)
                operations[nested_field] = SecretStr(value, sentinel)
                child["operations"] = operations
                assert_unknown_after_transport(
                    child,
                    field="operations",
                    nested_field=nested_field,
                    sentinel=sentinel,
                )

        valid_success: dict[str, object] = {
            "schema_version": credential_workflows.WORKFLOW_RESULT_SCHEMA_VERSION,
            "ok": True,
            "lifecycle_action": "secure_credential_adoption_execute",
            "accepted": True,
            "persisted": True,
            "reason_code": "credential_adoption_persisted_and_rediscoverable",
            "credential_id": CREDENTIAL_ID,
            "authenticated_rediscovery_verified": True,
            "human_default_decision_required": True,
            "secret_value_present": False,
            "reviewed_anchor_present_in_result": False,
            "backend_target_present": False,
            "crash_or_power_loss_rollback_guaranteed": False,
            "operations": dict(APPROVED_WORKER_OPERATIONS_UNKNOWN),
            "credential_input_received": True,
            "complete_line_received": True,
            "temporary_store_write_attempted": True,
            "provider_request_attempted": True,
        }
        projected_success = credential_workflows._project_adoption_worker_result(
            valid_success
        )
        self.assertTrue(projected_success["ok"])
        self.assertIs(type(projected_success["credential_id"]), str)
        for field, value, sentinel in (
            (
                "schema_version",
                credential_workflows.WORKFLOW_RESULT_SCHEMA_VERSION,
                "PRIVATE_SUCCESS_SCHEMA_SENTINEL",
            ),
            (
                "lifecycle_action",
                "secure_credential_adoption_execute",
                "PRIVATE_SUCCESS_ACTION_SENTINEL",
            ),
            (
                "reason_code",
                "credential_adoption_persisted_and_rediscoverable",
                "PRIVATE_SUCCESS_REASON_SENTINEL",
            ),
            ("credential_id", CREDENTIAL_ID, "PRIVATE_SUCCESS_ID_SENTINEL"),
        ):
            with self.subTest(shape="success", field=field):
                child = dict(valid_success)
                child[field] = SecretStr(value, sentinel)
                assert_unknown_after_transport(
                    child,
                    field=field,
                    sentinel=sentinel,
                )

        valid_reuse = {
            **valid_success,
            "accepted": False,
            "reason_code": (
                "credential_adoption_existing_registration_preserved_without_prompt"
            ),
            "secret_prompt_performed": False,
            "existing_registration_reused": True,
            "workspace_scope_migrated": False,
            "credential_input_received": False,
            "complete_line_received": False,
            "temporary_store_write_attempted": False,
            "provider_request_attempted": True,
        }
        projected_reuse = credential_workflows._project_adoption_worker_result(
            valid_reuse
        )
        self.assertTrue(projected_reuse["ok"])
        self.assertIs(type(projected_reuse["reason_code"]), str)
        self.assertIs(type(projected_reuse["credential_id"]), str)
        for field, value, sentinel in (
            (
                "reason_code",
                "credential_adoption_existing_registration_preserved_without_prompt",
                "PRIVATE_REUSE_REASON_SENTINEL",
            ),
            ("credential_id", CREDENTIAL_ID, "PRIVATE_REUSE_ID_SENTINEL"),
        ):
            with self.subTest(shape="reuse", field=field):
                child = dict(valid_reuse)
                child[field] = SecretStr(value, sentinel)
                assert_unknown_after_transport(
                    child,
                    field=field,
                    sentinel=sentinel,
                )

    def test_adoption_worker_start_evidence_controls_zero_vs_unknown(self) -> None:
        class FakeConnection:
            def __init__(self, messages=()) -> None:
                self.messages = list(messages)

            def recv(self):
                if not self.messages:
                    raise EOFError
                return self.messages.pop(0)

            def close(self) -> None:
                pass

        class FakeProcess:
            def __init__(self, *, fail_start: bool) -> None:
                self.fail_start = fail_start
                self.exitcode = 0

            def start(self) -> None:
                if self.fail_start:
                    raise RuntimeError("synthetic pre-start failure")

            def join(self) -> None:
                pass

            def is_alive(self) -> bool:
                return False

        class FakeSpawnContext:
            def __init__(self, *, fail_start: bool) -> None:
                self.process = FakeProcess(fail_start=fail_start)

            def Pipe(self, *, duplex: bool):
                if duplex is not False:
                    raise AssertionError("adoption pipe must be one-way")
                messages = (
                    ()
                    if self.process.fail_start
                    else (
                        {"worker_transport_status": "popup_child_detached"},
                    )
                )
                return FakeConnection(messages), FakeConnection()

            def Process(self, **_kwargs):
                return self.process

        plan = make_plan()
        call_kwargs = {
            "expected_plan_digest": str(plan["plan_digest"]),
            "expected_archive_id": ARCHIVE_ID,
            "reviewed_anchor_uuid": ANCHOR,
            "requested_capabilities": CAPABILITIES,
            "approved": True,
        }

        not_started = execute_windows_notion_credential_adoption(
            ".",
            plan,
            worker_spawner=NotStartedCredentialAdoptionSpawner(),
            **call_kwargs,
        )
        self.assertEqual(
            not_started["reason_code"],
            "credential_adoption_worker_launch_failed",
        )
        self.assertEqual(not_started["operations"], ZERO_LIVE_OPERATIONS)
        self.assertNotIn("durable_state", not_started)

        class InvalidStartEvidenceSpawner:
            def __init__(self, worker_started, result=None) -> None:
                self.worker_started = worker_started
                self.result = result

            def run_worker(self, _invocation):
                return credential_workflows._CredentialAdoptionWorkerRunOutcome(
                    worker_started=self.worker_started,
                    result=self.result,
                )

        invalid_start_cases = (
            (None, None),
            (1, None),
            ("false", None),
            (False, {"ok": False}),
        )
        for worker_started, child_result in invalid_start_cases:
            with self.subTest(
                worker_started=worker_started,
                child_result=child_result,
            ):
                invalid_start = execute_windows_notion_credential_adoption(
                    ".",
                    plan,
                    worker_spawner=InvalidStartEvidenceSpawner(
                        worker_started,
                        child_result,
                    ),
                    **call_kwargs,
                )
                self.assertEqual(
                    invalid_start["reason_code"],
                    "credential_adoption_worker_state_unknown",
                )
                self.assertIsNone(invalid_start["accepted"])
                self.assertIsNone(invalid_start["persisted"])
                self.assertEqual(
                    invalid_start["durable_state"],
                    "unknown_may_have_changed",
                )

        with patch.object(
            credential_workflows.multiprocessing,
            "get_context",
            return_value=FakeSpawnContext(fail_start=True),
        ):
            production_prestart = execute_windows_notion_credential_adoption(
                ".",
                plan,
                **call_kwargs,
            )
        self.assertEqual(
            production_prestart["reason_code"],
            "credential_adoption_worker_launch_failed",
        )
        self.assertEqual(production_prestart["operations"], ZERO_LIVE_OPERATIONS)

        with patch.object(
            credential_workflows.multiprocessing,
            "get_context",
            return_value=FakeSpawnContext(fail_start=False),
        ):
            production_eof = execute_windows_notion_credential_adoption(
                ".",
                plan,
                **call_kwargs,
            )
        self.assertEqual(
            production_eof["reason_code"],
            "credential_adoption_worker_state_unknown",
        )
        self.assertIsNone(production_eof["accepted"])
        self.assertIsNone(production_eof["persisted"])
        self.assertEqual(
            production_eof["durable_state"], "unknown_may_have_changed"
        )

    def test_spawned_popup_child_freeconsole_signature_and_strict_boolean(self) -> None:
        class FakeFreeConsole:
            def __init__(self, result) -> None:
                self.result = result
                self.calls = 0
                self.argtypes = None
                self.restype = None

            def __call__(self):
                self.calls += 1
                if isinstance(self.result, BaseException):
                    raise self.result
                return self.result

        class FakeKernel32:
            def __init__(self, result) -> None:
                self.FreeConsole = FakeFreeConsole(result)

        for raw_result, expected in (
            (True, True),
            (False, False),
            (1, False),
            (2, False),
            (0, False),
            (None, False),
            ("true", False),
        ):
            with self.subTest(raw_result=repr(raw_result)):
                kernel32 = FakeKernel32(raw_result)
                self.assertIs(
                    credential_workflows._detach_spawned_popup_child_console(
                        kernel32=kernel32,
                        platform_name="nt",
                    ),
                    expected,
                )
                self.assertEqual(kernel32.FreeConsole.calls, 1)
                self.assertEqual(kernel32.FreeConsole.argtypes, [])
                self.assertIs(
                    kernel32.FreeConsole.restype,
                    credential_workflows.wintypes.BOOL,
                )

        with self.assertRaises(RuntimeError):
            credential_workflows._detach_spawned_popup_child_console(
                kernel32=FakeKernel32(RuntimeError("synthetic detach failure")),
                platform_name="nt",
            )

        native_free_console = ctypes.CFUNCTYPE(
            credential_workflows.wintypes.BOOL
        )(lambda: 2)
        native_kernel32 = type(
            "NativeKernel32",
            (),
            {"FreeConsole": native_free_console},
        )()
        self.assertIs(
            credential_workflows._detach_spawned_popup_child_console(
                kernel32=native_kernel32,
                platform_name="nt",
            ),
            True,
        )
        native_zero = ctypes.CFUNCTYPE(
            credential_workflows.wintypes.BOOL
        )(lambda: 0)
        native_kernel32.FreeConsole = native_zero
        self.assertIs(
            credential_workflows._detach_spawned_popup_child_console(
                kernel32=native_kernel32,
                platform_name="nt",
            ),
            False,
        )

    def test_spawned_entry_detach_failure_returns_only_transport_marker(self) -> None:
        class ExplodingInvocation:
            def __getattribute__(self, name):
                raise AssertionError(f"invocation accessed before detach: {name}")

        class FakeConnection:
            def __init__(self) -> None:
                self.sent: list[object] = []
                self.closed = False

            def send(self, value) -> None:
                self.sent.append(value)

            def close(self) -> None:
                self.closed = True

        for detach_result in (
            False,
            1,
            None,
            RuntimeError("synthetic detach failure"),
            KeyboardInterrupt(),
        ):
            with self.subTest(detach=type(detach_result).__name__):
                connection = FakeConnection()
                detach_kwargs = (
                    {"side_effect": detach_result}
                    if isinstance(detach_result, BaseException)
                    else {"return_value": detach_result}
                )
                with patch.object(
                    credential_workflows,
                    "_detach_spawned_popup_child_console",
                    **detach_kwargs,
                ) as detach, patch.object(
                    credential_workflows,
                    "CtypesWindowsNativeFacade",
                ) as native, patch.object(
                    credential_workflows,
                    "ArchiveInterprocessRequestPacer",
                ) as pacer, patch.object(
                    credential_workflows,
                    "NotionHttpAdapter",
                ) as adapter, patch.object(
                    credential_workflows,
                    "StableArchiveFingerprintKeyProvider",
                ) as key_provider, patch.object(
                    credential_workflows,
                    "_execute_adoption_inside_worker",
                ) as execute:
                    credential_workflows._spawned_adoption_entry(
                        connection,
                        ExplodingInvocation(),  # type: ignore[arg-type]
                    )

                detach.assert_called_once_with()
                native.assert_not_called()
                pacer.assert_not_called()
                adapter.assert_not_called()
                key_provider.assert_not_called()
                execute.assert_not_called()
                self.assertEqual(connection.sent, [])
                self.assertTrue(connection.closed)

    def test_spawned_entry_ack_send_failure_blocks_all_live_work(self) -> None:
        events: list[str] = []

        class FakeConnection:
            def send(self, value) -> None:
                events.append("ack_send_attempt")
                self_outer.assertEqual(
                    value,
                    {"worker_transport_status": "popup_child_detached"},
                )
                raise KeyboardInterrupt("private ACK failure text")

            def close(self) -> None:
                events.append("close")

        self_outer = self
        with patch.object(
            credential_workflows,
            "_detach_spawned_popup_child_console",
            return_value=True,
        ) as detach, patch.object(
            credential_workflows,
            "CtypesWindowsNativeFacade",
        ) as native, patch.object(
            credential_workflows,
            "ArchiveInterprocessRequestPacer",
        ) as pacer, patch.object(
            credential_workflows,
            "NotionHttpAdapter",
        ) as adapter, patch.object(
            credential_workflows,
            "StableArchiveFingerprintKeyProvider",
        ) as key_provider, patch.object(
            credential_workflows,
            "_execute_adoption_inside_worker",
        ) as execute:
            credential_workflows._spawned_adoption_entry(
                FakeConnection(),
                object(),  # type: ignore[arg-type]
            )

        detach.assert_called_once_with()
        native.assert_not_called()
        pacer.assert_not_called()
        adapter.assert_not_called()
        key_provider.assert_not_called()
        execute.assert_not_called()
        self.assertEqual(events, ["ack_send_attempt", "close"])

    def test_spawned_entry_detaches_once_before_native_and_preserves_child_result(
        self,
    ) -> None:
        events: list[str] = []
        child_result = {"fixed": "sanitized_child_result"}
        native_object = object()
        pacer_object = object()
        adapter_object = object()
        key_object = object()

        class FakeConnection:
            def __init__(self) -> None:
                self.sent: list[object] = []

            def send(self, value) -> None:
                events.append(
                    "send_ack"
                    if value
                    == {"worker_transport_status": "popup_child_detached"}
                    else "send_final"
                )
                self.sent.append(value)

            def close(self) -> None:
                events.append("close")

        def detach() -> bool:
            events.append("detach")
            return True

        def make_native(*, cli_live_approved: bool):
            self.assertIs(cli_live_approved, True)
            events.append("native")
            return native_object

        def make_pacer(archive_root):
            self.assertEqual(archive_root, ".")
            events.append("pacer")
            return pacer_object

        def make_adapter(*, request_pacer, max_attempts):
            self.assertIs(request_pacer, pacer_object)
            self.assertEqual(max_attempts, 5)
            events.append("adapter")
            return adapter_object

        def make_key_provider(native):
            self.assertIs(native, native_object)
            events.append("key_provider")
            return key_object

        def execute(invocation, *, native, notion_adapter, key_provider):
            self.assertIs(native, native_object)
            self.assertIs(notion_adapter, adapter_object)
            self.assertIs(key_provider, key_object)
            events.append("execute")
            return child_result

        invocation = credential_workflows.CredentialAdoptionWorkerInvocation(
            archive_root=".",
            approval_plan={},
            expected_plan_digest="sha256:" + ("a" * 64),
            expected_interaction_context_sha256="sha256:" + ("b" * 64),
            replacement_approved=False,
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
        )
        connection = FakeConnection()
        with patch.object(
            credential_workflows,
            "_detach_spawned_popup_child_console",
            side_effect=detach,
        ) as detach_mock, patch.object(
            credential_workflows,
            "CtypesWindowsNativeFacade",
            side_effect=make_native,
        ), patch.object(
            credential_workflows,
            "ArchiveInterprocessRequestPacer",
            side_effect=make_pacer,
        ), patch.object(
            credential_workflows,
            "NotionHttpAdapter",
            side_effect=make_adapter,
        ), patch.object(
            credential_workflows,
            "StableArchiveFingerprintKeyProvider",
            side_effect=make_key_provider,
        ), patch.object(
            credential_workflows,
            "_execute_adoption_inside_worker",
            side_effect=execute,
        ):
            credential_workflows._spawned_adoption_entry(connection, invocation)

        detach_mock.assert_called_once_with()
        self.assertEqual(
            events,
            [
                "detach",
                "send_ack",
                "native",
                "pacer",
                "adapter",
                "key_provider",
                "execute",
                "send_final",
                "close",
            ],
        )
        self.assertEqual(
            connection.sent[0],
            {"worker_transport_status": "popup_child_detached"},
        )
        self.assertIs(connection.sent[1], child_result)

        source = Path(credential_workflows.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "CONIN$",
            "CONOUT$",
            "AllocConsole",
            "SetConsoleMode",
            "SetConsoleCtrlHandler",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        entry_source = source.split("def _spawned_adoption_entry", 1)[1].split(
            "def _join_started_credential_worker", 1
        )[0]
        self.assertLess(
            entry_source.index("_detach_spawned_popup_child_console"),
            entry_source.index("CtypesWindowsNativeFacade"),
        )
        parent_source = source.split(
            "class SpawnCredentialAdoptionWorkerSpawner", 1
        )[1].split("_ADOPTION_WORKER_SUCCESS_KEYS", 1)[0]
        self.assertNotIn("FreeConsole", parent_source)
        self.assertNotIn("_detach_spawned_popup_child_console", parent_source)

    def test_spawned_adoption_parent_waits_for_popup_child_with_atomic_signal_lease(
        self,
    ) -> None:
        events: list[str] = []
        child_result = {"fixed": "sanitized_child_result"}

        class FakeConnection:
            def __init__(self, *, receive: bool) -> None:
                self.receive = receive
                self.messages = [
                    {"worker_transport_status": "popup_child_detached"},
                    child_result,
                ]

            def recv(self):
                if not self.receive:
                    raise AssertionError("send connection cannot receive")
                if not self.messages:
                    events.append("receive_eof")
                    raise EOFError
                message = self.messages.pop(0)
                if message == {
                    "worker_transport_status": "popup_child_detached"
                }:
                    events.append("receive_ack")
                    return message
                events.append("receive_child_result")
                return message

            def close(self) -> None:
                events.append(
                    "receive_close" if self.receive else "send_close"
                )

        class FlakyJoinProcess:
            exitcode = 0

            def __init__(self) -> None:
                self.join_attempts = 0

            def start(self) -> None:
                events.append("process_start")

            def join(self) -> None:
                self.join_attempts += 1
                events.append(f"process_join_{self.join_attempts}")
                if self.join_attempts == 1:
                    raise RuntimeError("synthetic transient join failure")
                if self.join_attempts == 2:
                    raise KeyboardInterrupt

            def is_alive(self) -> bool:
                events.append("process_still_alive")
                return True

        class FakeSpawnContext:
            def __init__(self) -> None:
                self.process = FlakyJoinProcess()

            def Pipe(self, *, duplex: bool):
                if duplex is not False:
                    raise AssertionError("adoption pipe must be one-way")
                return FakeConnection(receive=True), FakeConnection(receive=False)

            def Process(self, **kwargs):
                self.process_kwargs = kwargs
                return self.process

        context = FakeSpawnContext()

        def interrupted_retry_wait(seconds: float) -> None:
            self.assertEqual(seconds, 0.05)
            events.append("join_retry_wait_interrupted")
            raise KeyboardInterrupt

        invocation = credential_workflows.CredentialAdoptionWorkerInvocation(
            archive_root=".",
            approval_plan={},
            expected_plan_digest="sha256:" + ("a" * 64),
            expected_interaction_context_sha256="sha256:" + ("b" * 64),
            replacement_approved=False,
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
        )
        with patch.object(
            credential_workflows.multiprocessing,
            "get_context",
            return_value=context,
        ), patch.object(
            credential_workflows.time,
            "sleep",
            side_effect=interrupted_retry_wait,
        ):
            outcome = (
                credential_workflows.SpawnCredentialAdoptionWorkerSpawner()
                .run_worker(invocation)
            )

        self.assertIs(outcome.worker_started, True)
        self.assertIs(outcome.result, child_result)
        self.assertLess(
            events.index("process_start"),
            events.index("receive_child_result"),
        )
        self.assertLess(
            events.index("receive_child_result"),
            events.index("process_join_1"),
        )
        self.assertEqual(
            events.count("process_still_alive"),
            2,
        )
        self.assertEqual(
            events.count("join_retry_wait_interrupted"),
            2,
        )
        self.assertIn("process_join_3", events)
        self.assertFalse(
            hasattr(
                credential_workflows,
                "_set_parent_console_ctrl_c_ignored",
            )
        )
        self.assertNotIn(
            "_ctrl_c_setter",
            credential_workflows.SpawnCredentialAdoptionWorkerSpawner.__dict__,
        )
        source = Path(credential_workflows.__file__).read_text(encoding="utf-8")
        self.assertNotIn("SetConsoleCtrlHandler", source)
        self.assertNotIn("_ctrl_c_setter", source)
        self.assertNotIn("threading.Thread", source)

    def test_spawned_adoption_signal_lease_orders_start_restore_recv_and_join(
        self,
    ) -> None:
        events: list[str] = []
        sigint = object()
        sigbreak = object()
        original_int = object()
        original_break = object()
        handlers = {
            sigint: original_int,
            sigbreak: original_break,
        }
        restore_attempts = {sigint: 0, sigbreak: 0}
        names = {sigint: "int", sigbreak: "break"}
        child_result = {"fixed": "content_free_child_result"}

        def get_handler(signal_number):
            events.append(f"get_{names[signal_number]}")
            return handlers[signal_number]

        def set_handler(signal_number, handler):
            label = (
                "ignore"
                if handler is credential_workflows.signal.SIG_IGN
                else "original"
            )
            events.append(f"set_{names[signal_number]}_{label}")
            if label == "original":
                restore_attempts[signal_number] += 1
                if signal_number is sigbreak and restore_attempts[signal_number] == 1:
                    events.append("restore_break_interrupted")
                    raise KeyboardInterrupt("private restore interruption text")
                if signal_number is sigint and restore_attempts[signal_number] == 1:
                    handlers[signal_number] = handler
                    events.append("restore_int_changed_then_interrupted")
                    raise SystemExit("private restore post-change text")
            handlers[signal_number] = handler

        class FakeConnection:
            def __init__(self, *, receive: bool) -> None:
                self.receive = receive
                self.messages = [
                    {"worker_transport_status": "popup_child_detached"},
                    child_result,
                ]

            def recv(self):
                if not self.messages:
                    events.append("eof")
                    raise EOFError
                message = self.messages.pop(0)
                if message == {
                    "worker_transport_status": "popup_child_detached"
                }:
                    events.append("ack")
                    return message
                self.assert_restored()
                events.append("recv")
                return message

            def assert_restored(self) -> None:
                self_outer.assertIs(handlers[sigint], original_int)
                self_outer.assertIs(handlers[sigbreak], original_break)

            def close(self) -> None:
                events.append("receive_close" if self.receive else "send_close")

        class FakeProcess:
            exitcode = 0

            def start(self) -> None:
                self_outer.assertIs(
                    handlers[sigint],
                    credential_workflows.signal.SIG_IGN,
                )
                self_outer.assertIs(
                    handlers[sigbreak],
                    credential_workflows.signal.SIG_IGN,
                )
                events.append("start")

            def join(self) -> None:
                events.append("join")

        class FakeContext:
            def __init__(self) -> None:
                self.process = FakeProcess()

            def Pipe(self, *, duplex: bool):
                self_outer.assertIs(duplex, False)
                return FakeConnection(receive=True), FakeConnection(receive=False)

            def Process(self, **_kwargs):
                return self.process

        self_outer = self
        context = FakeContext()
        invocation = credential_workflows.CredentialAdoptionWorkerInvocation(
            archive_root=".",
            approval_plan={},
            expected_plan_digest="sha256:" + ("a" * 64),
            expected_interaction_context_sha256="sha256:" + ("b" * 64),
            replacement_approved=False,
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
        )
        with patch.object(
            credential_workflows,
            "_credential_worker_start_signals",
            return_value=(sigint, sigbreak),
        ), patch.object(
            credential_workflows.multiprocessing,
            "get_context",
            return_value=context,
        ):
            outcome = credential_workflows.SpawnCredentialAdoptionWorkerSpawner(
                _signal_getter=get_handler,
                _signal_setter=set_handler,
            ).run_worker(invocation)

        self.assertIs(outcome.worker_started, True)
        self.assertIs(outcome.result, child_result)
        self.assertIs(handlers[sigint], original_int)
        self.assertIs(handlers[sigbreak], original_break)
        self.assertGreaterEqual(restore_attempts[sigint], 1)
        self.assertGreaterEqual(restore_attempts[sigbreak], 2)
        self.assertLess(events.index("set_int_ignore"), events.index("start"))
        self.assertLess(events.index("set_break_ignore"), events.index("start"))
        self.assertLess(events.index("start"), events.index("set_break_original"))
        self.assertLess(events.index("send_close"), events.index("ack"))
        self.assertLess(events.index("set_int_original"), events.index("recv"))
        self.assertLess(events.index("eof"), events.index("join"))
        self.assertLess(events.index("recv"), events.index("join"))
        self.assertNotIn("private restore interruption text", repr(outcome))
        self.assertNotIn("private restore post-change text", repr(outcome))

    def test_spawned_adoption_pipe_protocol_rejects_wrong_or_extra_messages(
        self,
    ) -> None:
        ack = {"worker_transport_status": "popup_child_detached"}
        final = {"fixed": "content_free_child_result"}

        class FakeConnection:
            def __init__(self, messages) -> None:
                self.messages = list(messages)

            def recv(self):
                if not self.messages:
                    raise EOFError
                message = self.messages.pop(0)
                if isinstance(message, BaseException):
                    raise message
                return message

        rows = (
            ((), False, None),
            ((ack, final), True, final),
            ((ack,), True, None),
            (({"worker_transport_status": "wrong"},), True, None),
            (({**ack, "extra": False}, final), True, None),
            ((ack, final, {"extra": "message"}), True, None),
            ((ack, "not_a_mapping"), True, None),
            ((KeyboardInterrupt("private interrupt text"), ack, final), True, final),
        )
        for messages, expected_started, expected_result in rows:
            with self.subTest(messages=len(messages), expected_started=expected_started):
                outcome = credential_workflows._drain_credential_worker_pipe(
                    FakeConnection(messages)
                )
                self.assertIs(outcome.worker_started, expected_started)
                self.assertIs(outcome.result, expected_result)
                self.assertNotIn("private interrupt text", repr(outcome))

    def test_spawned_adoption_pipe_never_returns_before_terminal_eof(self) -> None:
        ack = {"worker_transport_status": "popup_child_detached"}
        final = {"fixed": "content_free_child_result"}
        eof_release = threading.Event()
        eof_waiting = threading.Event()
        outcomes: list[object] = []

        class BlockingConnection:
            def __init__(self) -> None:
                self.messages = [ack, final]

            def recv(self):
                if self.messages:
                    return self.messages.pop(0)
                eof_waiting.set()
                eof_release.wait()
                raise EOFError

        worker = threading.Thread(
            target=lambda: outcomes.append(
                credential_workflows._drain_credential_worker_pipe(
                    BlockingConnection()
                )
            ),
            daemon=False,
        )
        worker.start()
        self.assertTrue(eof_waiting.wait(timeout=1.0))
        self.assertTrue(worker.is_alive())
        self.assertEqual(outcomes, [])
        eof_release.set()
        worker.join(timeout=1.0)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(outcomes), 1)
        outcome = outcomes[0]
        self.assertIs(outcome.worker_started, True)
        self.assertIs(outcome.result, final)

    def test_spawned_adoption_partial_signal_install_restores_and_never_starts(
        self,
    ) -> None:
        events: list[str] = []
        sigint = object()
        sigbreak = object()
        original_int = object()
        original_break = object()
        handlers = {sigint: original_int, sigbreak: original_break}
        originals = {sigint: original_int, sigbreak: original_break}
        names = {sigint: "int", sigbreak: "break"}
        restore_attempts = {sigint: 0, sigbreak: 0}
        state = {"partial_failure": False, "getter_interrupted": False}

        def get_handler(signal_number):
            if (
                state["partial_failure"]
                and signal_number is sigint
                and handlers[signal_number] is originals[signal_number]
                and not state["getter_interrupted"]
            ):
                state["getter_interrupted"] = True
                events.append("restore_get_interrupted")
                raise SystemExit("private synthetic getter text")
            events.append(f"get_{names[signal_number]}")
            return handlers[signal_number]

        def set_handler(signal_number, handler):
            if handler is credential_workflows.signal.SIG_IGN:
                handlers[signal_number] = handler
                events.append(f"set_{names[signal_number]}_ignore")
                if signal_number is sigbreak:
                    state["partial_failure"] = True
                    raise KeyboardInterrupt("private synthetic install text")
                return
            restore_attempts[signal_number] += 1
            events.append(f"restore_{names[signal_number]}")
            if signal_number is sigbreak and restore_attempts[signal_number] == 1:
                raise KeyboardInterrupt("private synthetic restore text")
            handlers[signal_number] = handler

        class FakeConnection:
            def recv(self):
                raise AssertionError("pre-start failure must not receive")

            def close(self) -> None:
                events.append("connection_close")

        class FakeProcess:
            exitcode = None
            pid = None

            def start(self) -> None:
                events.append("UNSAFE_process_start")
                raise AssertionError("process must not start")

            def join(self) -> None:
                events.append("UNSAFE_process_join")
                raise AssertionError("unstarted process must not join")

        class FakeContext:
            def Pipe(self, *, duplex: bool):
                self_outer.assertIs(duplex, False)
                return FakeConnection(), FakeConnection()

            def Process(self, **_kwargs):
                return FakeProcess()

        self_outer = self
        invocation = credential_workflows.CredentialAdoptionWorkerInvocation(
            archive_root=".",
            approval_plan={},
            expected_plan_digest="sha256:" + ("a" * 64),
            expected_interaction_context_sha256="sha256:" + ("b" * 64),
            replacement_approved=False,
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
        )
        with patch.object(
            credential_workflows,
            "_credential_worker_start_signals",
            return_value=(sigint, sigbreak),
        ), patch.object(
            credential_workflows.multiprocessing,
            "get_context",
            return_value=FakeContext(),
        ), patch.object(
            credential_workflows.time,
            "sleep",
            side_effect=KeyboardInterrupt("private synthetic delay text"),
        ):
            outcome = credential_workflows.SpawnCredentialAdoptionWorkerSpawner(
                _signal_getter=get_handler,
                _signal_setter=set_handler,
            ).run_worker(invocation)

        self.assertIs(outcome.worker_started, False)
        self.assertIsNone(outcome.result)
        self.assertIs(handlers[sigint], original_int)
        self.assertIs(handlers[sigbreak], original_break)
        self.assertGreaterEqual(restore_attempts[sigint], 2)
        self.assertGreaterEqual(restore_attempts[sigbreak], 2)
        self.assertNotIn("UNSAFE_process_start", events)
        self.assertNotIn("UNSAFE_process_join", events)
        for private_text in (
            "private synthetic getter text",
            "private synthetic install text",
            "private synthetic restore text",
            "private synthetic delay text",
        ):
            self.assertNotIn(private_text, repr(outcome))

    def test_spawned_adoption_start_exception_uses_ack_and_eof_containment(
        self,
    ) -> None:
        invocation = credential_workflows.CredentialAdoptionWorkerInvocation(
            archive_root=".",
            approval_plan={},
            expected_plan_digest="sha256:" + ("a" * 64),
            expected_interaction_context_sha256="sha256:" + ("b" * 64),
            replacement_approved=False,
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
        )

        for child_created in (False, True):
            with self.subTest(child_created=child_created):
                events: list[str] = []
                sigint = object()
                sigbreak = object()
                original_int = object()
                original_break = object()
                handlers = {sigint: original_int, sigbreak: original_break}
                child_result = {"fixed": "content_free_child_result"}

                def get_handler(signal_number):
                    return handlers[signal_number]

                def set_handler(signal_number, handler):
                    handlers[signal_number] = handler
                    events.append(
                        "restore"
                        if handler is not credential_workflows.signal.SIG_IGN
                        else "ignore"
                    )

                class FakeConnection:
                    def __init__(self, *, receive: bool) -> None:
                        self.receive = receive
                        self.interrupted = False
                        self.messages = (
                            [
                                {"worker_transport_status": "popup_child_detached"},
                                child_result,
                            ]
                            if child_created
                            else []
                        )

                    def recv(self):
                        if child_created and not self.interrupted:
                            self.interrupted = True
                            events.append("recv_interrupted")
                            raise KeyboardInterrupt("private drain interrupt text")
                        self_outer.assertIs(handlers[sigint], original_int)
                        self_outer.assertIs(handlers[sigbreak], original_break)
                        if not self.messages:
                            events.append("eof")
                            raise EOFError
                        message = self.messages.pop(0)
                        events.append("recv")
                        return message

                    def close(self) -> None:
                        events.append("close_receive" if self.receive else "close_send")

                class FakeProcess:
                    exitcode = 0 if child_created else None
                    pid = None

                    def __init__(self) -> None:
                        self.alive = False

                    def start(self) -> None:
                        events.append("start")
                        if child_created:
                            self.pid = 4242
                            self.alive = True
                            raise KeyboardInterrupt("private post-create text")
                        raise OSError("private pre-create text")

                    def is_alive(self) -> bool:
                        raise AssertionError(
                            "ambiguous start must not query public process state"
                        )

                    def join(self) -> None:
                        raise AssertionError("ambiguous start must not join")

                class FakeContext:
                    def __init__(self) -> None:
                        self.process = FakeProcess()

                    def Pipe(self, *, duplex: bool):
                        self_outer.assertIs(duplex, False)
                        return (
                            FakeConnection(receive=True),
                            FakeConnection(receive=False),
                        )

                    def Process(self, **_kwargs):
                        return self.process

                self_outer = self
                context = FakeContext()
                with patch.object(
                    credential_workflows,
                    "_credential_worker_start_signals",
                    return_value=(sigint, sigbreak),
                ), patch.object(
                    credential_workflows.multiprocessing,
                    "get_context",
                    return_value=context,
                ):
                    outcome = (
                        credential_workflows.SpawnCredentialAdoptionWorkerSpawner(
                            _signal_getter=get_handler,
                            _signal_setter=set_handler,
                        ).run_worker(invocation)
                    )

                self.assertIs(outcome.worker_started, child_created)
                self.assertIs(
                    outcome.result,
                    child_result if child_created else None,
                )
                self.assertIs(handlers[sigint], original_int)
                self.assertIs(handlers[sigbreak], original_break)
                if child_created:
                    self.assertLess(events.index("restore"), events.index("recv"))
                    self.assertIn("recv_interrupted", events)
                else:
                    self.assertNotIn("recv", events)
                self.assertNotIn("join", events)
                self.assertNotIn("private pre-create text", repr(outcome))
                self.assertNotIn("private post-create text", repr(outcome))
                self.assertNotIn("private drain interrupt text", repr(outcome))


class CredentialWorkflowEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = make_archive(Path(self.temporary.name))
        self.native = FakeWindowsNative()
        self.key_provider = StableArchiveFingerprintKeyProvider(
            self.native,
            random_bytes=lambda size: ARCHIVE_KEY if size == 32 else b"",
        )

    def assert_adoption_stage(self, result: dict, bits: str) -> None:
        self.assertEqual(
            tuple(
                result[field]
                for field in (
                    "credential_input_received",
                    "complete_line_received",
                    "temporary_store_write_attempted",
                    "provider_request_attempted",
                )
            ),
            tuple(bit == "1" for bit in bits),
        )

    def _adopt(self, *, transport: FakeTransport | None = None) -> tuple[dict, FakeTransport]:
        plan = make_plan()
        selected_transport = transport or intake_transport()
        spawner = InjectedCredentialAdoptionWorkerSpawner(
            native=self.native,
            notion_adapter=NotionHttpAdapter(transport=selected_transport),
            key_provider=self.key_provider,
            now_factory=lambda: NOW,
            credential_id_factory=lambda: CREDENTIAL_ID,
            backend_id_factory=lambda: BACKEND_ID,
        )
        result = execute_windows_notion_credential_adoption(
            self.root,
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=spawner,
        )
        return result, selected_transport

    def _replace_current_receipt_with_released_v01(
        self, *, anchor: str
    ) -> dict[str, object]:
        """Build an authenticated release-era artifact from an adopted fixture."""

        receipt_path = (
            self.root
            / "profiles"
            / "local"
            / "credential-intake"
            / "receipts"
            / f"{CREDENTIAL_ID}.json"
        )
        current = json.loads(receipt_path.read_text(encoding="utf-8"))
        current.pop("receipt_authentication")
        current.pop("workspace_identity_basis")
        current["schema_version"] = (
            "wom-credential-secure-intake-receipt/v0.1"
        )
        old_adapter_scope = "sha256:" + hashlib.sha256(
            (
                f"wom:notion:{NOTION_API_VERSION}:workspace-anchor:{anchor}"
            ).encode("utf-8")
        ).hexdigest()
        current["verified_workspace_fingerprint"] = (
            "sha256:"
            + hashlib.sha256(old_adapter_scope.encode("utf-8")).hexdigest()
        )
        receipt_path.unlink()
        authenticated = dict(current)
        authenticated["receipt_authentication"] = {
            "schema_version": RECEIPT_AUTHENTICATION_SCHEMA,
            "algorithm": "hmac-sha256",
            "mac": _receipt_mac(current, ARCHIVE_KEY),
        }
        AtomicJsonReceiptCommitter(receipt_path.parent).commit_atomic(
            authenticated
        )
        return current

    def test_success_is_authenticated_rediscoverable_and_failure_has_no_id(self) -> None:
        result, _transport = self._adopt()
        self.assertTrue(result["ok"])
        self.assertTrue(result["accepted"])
        self.assertTrue(result["persisted"])
        self.assertEqual(result["credential_id"], CREDENTIAL_ID)
        self.assertTrue(result["authenticated_rediscovery_verified"])
        self.assertTrue(result["human_default_decision_required"])
        self.assertEqual(result["operations"], APPROVED_WORKER_OPERATIONS_UNKNOWN)
        self.assert_adoption_stage(result, "1111")

        listed = list_authenticated_secure_credentials(
            self.root,
            native=self.native,
            key_provider=StableArchiveFingerprintKeyProvider(self.native),
        )
        self.assertTrue(listed["ok"])
        self.assertEqual(listed["credential_count"], 1)
        self.assertEqual(listed["credentials"][0]["credential_id"], CREDENTIAL_ID)
        self.assertFalse(listed["credentials"][0]["broker_authoritative"])
        rendered = json.dumps({"result": result, "listed": listed}, ensure_ascii=False)
        for private in (SECRET_TEXT, ANCHOR, BACKEND_ID, "WOM/credential-intake/"):
            self.assertNotIn(private, rendered)

        failed_root = make_archive(Path(self.temporary.name) / "cancelled")
        cancelled_native = FakeWindowsNative(cancelled=True)
        cancelled_key_provider = StableArchiveFingerprintKeyProvider(
            cancelled_native,
            random_bytes=lambda _size: ARCHIVE_KEY,
        )
        cancelled_transport = intake_transport()
        plan = make_plan(request_id_factory=lambda: "intake_cancelled123456789")
        failed = execute_windows_notion_credential_adoption(
            failed_root,
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                cancelled_native,
                NotionHttpAdapter(transport=cancelled_transport),
                cancelled_key_provider,
                now_factory=lambda: NOW,
            ),
        )
        self.assertFalse(failed["ok"])
        self.assertFalse(failed["persisted"])
        self.assertNotIn("credential_id", failed)
        self.assertEqual(failed["operations"], APPROVED_WORKER_OPERATIONS_UNKNOWN)
        self.assert_adoption_stage(failed, "1100")
        self.assertEqual(cancelled_native.sid_reads, 1)
        self.assertEqual(cancelled_native.prompts, 1)
        self.assertGreaterEqual(len(cancelled_native.probes), 2)
        self.assertEqual(len(cancelled_native.writes), 1)
        self.assertEqual(len(cancelled_native.reads), 1)
        self.assertEqual(cancelled_transport.calls, [])

    def test_repeat_adoption_preserves_authenticated_registration_without_prompt(self) -> None:
        first, _first_transport = self._adopt()
        self.assertTrue(first["ok"])
        self.assertEqual(self.native.prompts, 1)
        repeat_transport = intake_transport()

        repeat_plan = make_plan(
            request_id_factory=lambda: "intake_repeat_no_prompt123456"
        )
        repeat = execute_windows_notion_credential_adoption(
            self.root,
            repeat_plan,
            expected_plan_digest=str(repeat_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=repeat_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )

        self.assertTrue(repeat["ok"])
        self.assertFalse(repeat["accepted"])
        self.assertTrue(repeat["persisted"])
        self.assertEqual(
            repeat["reason_code"],
            "credential_adoption_existing_registration_preserved_without_prompt",
        )
        self.assertFalse(repeat["secret_prompt_performed"])
        self.assertTrue(repeat["existing_registration_reused"])
        self.assert_adoption_stage(repeat, "0001")
        self.assertEqual(self.native.prompts, 1)
        self.assertEqual(len(repeat_transport.calls), 2)

    def test_repeat_adoption_validates_saved_secret_before_provider_revalidation(
        self,
    ) -> None:
        first, _first_transport = self._adopt()
        self.assertTrue(first["ok"])
        prompts_before = self.native.prompts
        writes_before = len(self.native.writes)

        class LocallyInvalidSavedSecretVerifier:
            def __init__(self) -> None:
                self.validation_calls = 0
                self.verify_calls = 0

            def validate_secret_input(
                self, _secret: memoryview, _provider: str
            ) -> bool:
                self.validation_calls += 1
                return False

            def verify_identity(self, *_args, **_kwargs):
                self.verify_calls += 1
                raise AssertionError("provider revalidation must not start")

        verifier = LocallyInvalidSavedSecretVerifier()

        class LocallyInvalidSavedSecretAdapter:
            def secure_intake_verifier(self):
                return verifier

        repeat_plan = make_plan(
            request_id_factory=lambda: "intake_repeat_local_invalid123",
        )
        repeat = execute_windows_notion_credential_adoption(
            self.root,
            repeat_plan,
            expected_plan_digest=str(repeat_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=LocallyInvalidSavedSecretAdapter(),  # type: ignore[arg-type]
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )

        self.assertFalse(repeat["ok"])
        self.assertEqual(
            repeat["reason_code"],
            "credential_adoption_existing_scope_revalidation_failed",
        )
        self.assert_adoption_stage(repeat, "0000")
        self.assertEqual(repeat["rollback_status"], "not_required")
        self.assertFalse(repeat["store_absence_verified"])
        self.assertEqual(verifier.validation_calls, 1)
        self.assertEqual(verifier.verify_calls, 0)
        self.assertEqual(self.native.prompts, prompts_before)
        self.assertEqual(len(self.native.writes), writes_before)

    def test_repeat_adoption_reuses_saved_secret_for_another_anchor_in_same_workspace(self) -> None:
        first, _first_transport = self._adopt()
        self.assertTrue(first["ok"])
        prompts_before = self.native.prompts
        writes_before = len(self.native.writes)
        repeat_transport = intake_transport(anchor=OTHER_ANCHOR)
        repeat_plan = make_plan(
            reviewed_anchor_uuid=OTHER_ANCHOR,
            request_id_factory=lambda: "intake_repeat_other_anchor1234",
        )

        repeat = execute_windows_notion_credential_adoption(
            self.root,
            repeat_plan,
            expected_plan_digest=str(repeat_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=OTHER_ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=repeat_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )

        self.assertTrue(repeat["ok"])
        self.assertEqual(
            repeat["reason_code"],
            "credential_adoption_existing_registration_preserved_without_prompt",
        )
        self.assertTrue(repeat["existing_registration_reused"])
        self.assertFalse(repeat["secret_prompt_performed"])
        self.assertEqual(self.native.prompts, prompts_before)
        self.assertEqual(len(self.native.writes), writes_before)
        self.assertEqual(len(repeat_transport.calls), 2)
        rendered = json.dumps(repeat, ensure_ascii=False, sort_keys=True)
        for private in (ANCHOR, OTHER_ANCHOR, WORKSPACE_ID, USER_ID, SECRET_TEXT):
            self.assertNotIn(private, rendered)

    def test_person_pat_first_intake_reuses_same_pat_for_another_anchor_without_prompt(self) -> None:
        first, _ = self._adopt(transport=intake_transport(person=True))
        self.assertTrue(first["ok"])
        listed = list_authenticated_secure_credentials(
            self.root,
            native=self.native,
            key_provider=self.key_provider,
        )
        row = listed["credentials"][0]
        self.assertEqual(
            row["workspace_identity_basis"],
            NOTION_PAT_WORKSPACE_IDENTITY_BASIS,
        )
        expected_scope = "sha256:" + hashlib.sha256(
            NOTION_PAT_SCOPE_FINGERPRINT_DOMAIN
            + str(row["credential_fingerprint"]).encode("ascii")
        ).hexdigest()
        self.assertEqual(row["verified_workspace_fingerprint"], expected_scope)

        prompts_before = self.native.prompts
        writes_before = list(self.native.writes)
        repeat_transport = intake_transport(
            person=True,
            anchor=OTHER_ANCHOR,
        )
        repeat_plan = make_plan(
            reviewed_anchor_uuid=OTHER_ANCHOR,
            request_id_factory=lambda: "intake_person_pat_other_anchor1",
        )
        repeat = execute_windows_notion_credential_adoption(
            self.root,
            repeat_plan,
            expected_plan_digest=str(repeat_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=OTHER_ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=repeat_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )
        self.assertTrue(repeat["ok"])
        self.assertEqual(
            repeat["reason_code"],
            "credential_adoption_existing_registration_preserved_without_prompt",
        )
        self.assertFalse(repeat["secret_prompt_performed"])
        self.assertEqual(self.native.prompts, prompts_before)
        self.assertEqual(self.native.writes, writes_before)

        second_root = make_archive(Path(self.temporary.name) / "different-pat")
        second_secret = "synthetic_other_notion_pat_only_in_worker"
        second_native = FakeWindowsNative(secret_text=second_secret)
        second_key_provider = StableArchiveFingerprintKeyProvider(
            second_native,
            random_bytes=lambda size: ARCHIVE_KEY if size == 32 else b"",
        )
        second_plan = make_plan(
            request_id_factory=lambda: "intake_person_pat_separate_scope1"
        )
        second = execute_windows_notion_credential_adoption(
            second_root,
            second_plan,
            expected_plan_digest=str(second_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=second_native,
                notion_adapter=NotionHttpAdapter(
                    transport=intake_transport(person=True)
                ),
                key_provider=second_key_provider,
                now_factory=lambda: NOW,
                credential_id_factory=lambda: CREDENTIAL_ID,
                backend_id_factory=lambda: BACKEND_ID,
            ),
        )
        self.assertTrue(second["ok"])
        second_row = list_authenticated_secure_credentials(
            second_root,
            native=second_native,
            key_provider=second_key_provider,
        )["credentials"][0]
        self.assertNotEqual(
            row["verified_workspace_fingerprint"],
            second_row["verified_workspace_fingerprint"],
        )
        rendered = json.dumps(
            [first, listed, repeat, second, second_row],
            ensure_ascii=False,
            sort_keys=True,
        )
        for private in (
            SECRET_TEXT,
            second_secret,
            USER_ID,
            ANCHOR,
            OTHER_ANCHOR,
        ):
            self.assertNotIn(private, rendered)

    def test_released_v01_person_pat_evolves_without_prompt_and_preserves_singleton_lifecycle(self) -> None:
        first, _ = self._adopt(transport=intake_transport(person=True))
        self.assertTrue(first["ok"])
        legacy = self._replace_current_receipt_with_released_v01(anchor=ANCHOR)
        legacy_list = list_authenticated_secure_credentials(
            self.root,
            native=self.native,
            key_provider=self.key_provider,
        )
        legacy_row = legacy_list["credentials"][0]
        self.assertEqual(
            legacy_row["workspace_identity_basis"],
            "legacy_reviewed_anchor_v1",
        )
        lifecycle_plan = plan_authenticated_credential_lifecycle(
            self.root,
            provider="notion",
            workspace_fingerprint=str(
                legacy["verified_workspace_fingerprint"]
            ),
            selected_default_credential_id=CREDENTIAL_ID,
            revocation_pending_credential_ids=(),
            native=self.native,
            key_provider=self.key_provider,
        )
        lifecycle = approve_authenticated_credential_lifecycle(
            self.root,
            provider="notion",
            workspace_fingerprint=str(
                legacy["verified_workspace_fingerprint"]
            ),
            selected_default_credential_id=CREDENTIAL_ID,
            revocation_pending_credential_ids=(),
            expected_plan_sha256=str(lifecycle_plan["plan_sha256"]),
            reviewed_by="tester-legacy-pat",
            native=self.native,
            key_provider=self.key_provider,
        )
        self.assertTrue(lifecycle["ok"])

        prompts_before = self.native.prompts
        writes_before = list(self.native.writes)
        saved_targets_before = {
            target: bytes(value) for target, value in self.native.values.items()
        }
        repeat_transport = intake_transport(
            person=True,
            anchor=OTHER_ANCHOR,
        )
        repeat_plan = make_plan(
            reviewed_anchor_uuid=OTHER_ANCHOR,
            request_id_factory=lambda: "intake_legacy_pat_scope_evolve1",
        )
        repeat = execute_windows_notion_credential_adoption(
            self.root,
            repeat_plan,
            expected_plan_digest=str(repeat_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=OTHER_ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=repeat_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )
        self.assertTrue(repeat["ok"])
        self.assertEqual(
            repeat["reason_code"],
            "credential_adoption_legacy_scope_evolved_without_prompt",
        )
        self.assertTrue(repeat["workspace_scope_migrated"])
        self.assertFalse(repeat["secret_prompt_performed"])
        self.assertEqual(self.native.prompts, prompts_before)
        self.assertEqual(self.native.writes, writes_before)
        self.assertEqual(
            {target: bytes(value) for target, value in self.native.values.items()},
            saved_targets_before,
        )
        current = list_authenticated_secure_credentials(
            self.root,
            native=self.native,
            key_provider=self.key_provider,
        )["credentials"][0]
        self.assertEqual(
            current["workspace_identity_basis"],
            NOTION_PAT_WORKSPACE_IDENTITY_BASIS,
        )
        self.assertTrue(current["workspace_scope_evolved"])
        self.assertTrue(current["broker_authoritative"])
        self.assertFalse(repeat["human_default_decision_required"])
        evolution_files = list(
            (
                self.root
                / "profiles"
                / "local"
                / "credential-intake"
                / "evolutions"
            ).glob("*.workspace-scope-v1.json")
        )
        self.assertEqual(len(evolution_files), 1)
        rendered = json.dumps(
            [repeat, current], ensure_ascii=False, sort_keys=True
        )
        for private in (SECRET_TEXT, USER_ID, ANCHOR, OTHER_ANCHOR, BACKEND_ID):
            self.assertNotIn(private, rendered)

    def test_released_v01_migration_interruption_retries_pending_lifecycle_without_prompt(self) -> None:
        first, _ = self._adopt(transport=intake_transport(person=True))
        self.assertTrue(first["ok"])
        legacy = self._replace_current_receipt_with_released_v01(anchor=ANCHOR)
        lifecycle_plan = plan_authenticated_credential_lifecycle(
            self.root,
            provider="notion",
            workspace_fingerprint=str(
                legacy["verified_workspace_fingerprint"]
            ),
            selected_default_credential_id=CREDENTIAL_ID,
            revocation_pending_credential_ids=(),
            native=self.native,
            key_provider=self.key_provider,
        )
        approved_lifecycle = approve_authenticated_credential_lifecycle(
            self.root,
            provider="notion",
            workspace_fingerprint=str(
                legacy["verified_workspace_fingerprint"]
            ),
            selected_default_credential_id=CREDENTIAL_ID,
            revocation_pending_credential_ids=(),
            expected_plan_sha256=str(lifecycle_plan["plan_sha256"]),
            reviewed_by="tester-crash-retry",
            native=self.native,
            key_provider=self.key_provider,
        )
        self.assertTrue(approved_lifecycle["ok"])
        real_evolve = credential_workflows.evolve_legacy_authenticated_workspace_scope

        def interrupting_evolve(*args, **kwargs):
            def interrupt_after_publication() -> None:
                raise RuntimeError("private synthetic interruption")

            kwargs["after_evolution_commit"] = interrupt_after_publication
            return real_evolve(*args, **kwargs)

        prompts_before = self.native.prompts
        writes_before = list(self.native.writes)
        interrupted_plan = make_plan(
            reviewed_anchor_uuid=OTHER_ANCHOR,
            request_id_factory=lambda: "intake_legacy_scope_interrupted1",
        )
        with patch.object(
            credential_workflows,
            "evolve_legacy_authenticated_workspace_scope",
            side_effect=interrupting_evolve,
        ):
            interrupted = execute_windows_notion_credential_adoption(
                self.root,
                interrupted_plan,
                expected_plan_digest=str(interrupted_plan["plan_digest"]),
                expected_archive_id=ARCHIVE_ID,
                reviewed_anchor_uuid=OTHER_ANCHOR,
                requested_capabilities=CAPABILITIES,
                approved=True,
                worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                    native=self.native,
                    notion_adapter=NotionHttpAdapter(
                        transport=intake_transport(
                            person=True, anchor=OTHER_ANCHOR
                        )
                    ),
                    key_provider=self.key_provider,
                    now_factory=lambda: NOW,
                ),
            )
        self.assertFalse(interrupted["ok"])
        self.assertEqual(
            interrupted["reason_code"],
            "credential_adoption_existing_scope_migration_failed",
        )
        pending = list_authenticated_secure_credentials(
            self.root,
            native=self.native,
            key_provider=self.key_provider,
        )["credentials"][0]
        self.assertTrue(pending["workspace_scope_evolved"])
        self.assertTrue(pending["workspace_scope_transition_pending"])
        self.assertFalse(pending["broker_authoritative"])

        retry_plan = make_plan(
            reviewed_anchor_uuid=OTHER_ANCHOR,
            request_id_factory=lambda: "intake_legacy_scope_retry12345",
        )
        retry = execute_windows_notion_credential_adoption(
            self.root,
            retry_plan,
            expected_plan_digest=str(retry_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=OTHER_ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(
                    transport=intake_transport(
                        person=True, anchor=OTHER_ANCHOR
                    )
                ),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )
        self.assertTrue(retry["ok"])
        self.assertEqual(
            retry["reason_code"],
            "credential_adoption_legacy_scope_evolved_without_prompt",
        )
        self.assertTrue(retry["workspace_scope_migrated"])
        self.assertFalse(retry["human_default_decision_required"])
        current = list_authenticated_secure_credentials(
            self.root,
            native=self.native,
            key_provider=self.key_provider,
        )["credentials"][0]
        self.assertFalse(current["workspace_scope_transition_pending"])
        self.assertTrue(current["broker_authoritative"])
        self.assertEqual(self.native.prompts, prompts_before)
        self.assertEqual(self.native.writes, writes_before)
        rendered = json.dumps(
            [interrupted, pending, retry, current],
            ensure_ascii=False,
            sort_keys=True,
        )
        for private in (SECRET_TEXT, USER_ID, ANCHOR, OTHER_ANCHOR, BACKEND_ID):
            self.assertNotIn(private, rendered)

    def test_repeat_adoption_ignores_display_label_drift_and_reuses_exact_secret(self) -> None:
        first, _first_transport = self._adopt()
        self.assertTrue(first["ok"])
        prompts_before = self.native.prompts
        writes_before = len(self.native.writes)
        repeat_transport = intake_transport()

        repeat_plan = make_plan(
            account_label="renamed display account",
            workspace_label="renamed display workspace",
            request_id_factory=lambda: "intake_label_drift_no_prompt123",
        )
        repeat = execute_windows_notion_credential_adoption(
            self.root,
            repeat_plan,
            expected_plan_digest=str(repeat_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=repeat_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )
        self.assertTrue(repeat["ok"])
        self.assertTrue(repeat["existing_registration_reused"])
        self.assertFalse(repeat["secret_prompt_performed"])
        self.assertEqual(self.native.prompts, prompts_before)
        self.assertEqual(len(self.native.writes), writes_before)
        self.assertEqual(len(repeat_transport.calls), 2)

        listed = list_authenticated_secure_credentials(
            self.root,
            native=self.native,
            key_provider=StableArchiveFingerprintKeyProvider(self.native),
        )
        self.assertEqual(listed["credential_count"], 1)

    def test_multiple_provider_purpose_registrations_require_lifecycle_review(self) -> None:
        first, _first_transport = self._adopt()
        self.assertTrue(first["ok"])

        replacement_transport = intake_transport()
        replacement_plan = make_plan(
            replace_existing=True,
            account_label="second display account",
            workspace_label="second display workspace",
            request_id_factory=lambda: "intake_second_registration1234",
        )
        replacement = execute_windows_notion_credential_adoption(
            self.root,
            replacement_plan,
            expected_plan_digest=str(replacement_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=replacement_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
                credential_id_factory=lambda: "cred_secondregistration123456",
                backend_id_factory=lambda: "backend_secondregistration1234",
            ),
        )
        self.assertTrue(replacement["ok"])
        prompts_before = self.native.prompts
        reads_before = len(self.native.reads)
        writes_before = len(self.native.writes)
        blocked_transport = FakeTransport([])

        repeat_plan = make_plan(
            account_label="third display account",
            workspace_label="third display workspace",
            request_id_factory=lambda: "intake_multiple_requires_review1",
        )
        blocked = execute_windows_notion_credential_adoption(
            self.root,
            repeat_plan,
            expected_plan_digest=str(repeat_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=blocked_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )
        self.assertFalse(blocked["ok"])
        self.assertEqual(
            blocked["reason_code"],
            "credential_adoption_existing_registrations_require_lifecycle_review",
        )
        self.assertEqual(self.native.prompts, prompts_before)
        # One exact archive-key read happens before authenticated registry
        # inspection; no saved provider credential is read on this branch.
        self.assertEqual(len(self.native.reads), reads_before + 1)
        self.assertEqual(len(self.native.writes), writes_before)
        self.assertEqual(blocked_transport.calls, [])

    def test_repeat_adoption_requires_explicit_replacement_when_store_entry_is_missing(self) -> None:
        first, first_transport = self._adopt()
        self.assertTrue(first["ok"])
        secret_targets = [
            target
            for target in self.native.values
            if "/backend_" in target and "backend_key_" not in target
        ]
        self.assertEqual(len(secret_targets), 1)
        self.native.values.pop(secret_targets[0])
        prompts_before = self.native.prompts
        writes_before = len(self.native.writes)
        provider_calls_before = len(first_transport.calls)

        repeat_plan = make_plan(
            request_id_factory=lambda: "intake_missing_store_no_prompt12"
        )
        repeat = execute_windows_notion_credential_adoption(
            self.root,
            repeat_plan,
            expected_plan_digest=str(repeat_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=first_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )
        self.assertFalse(repeat["ok"])
        self.assertFalse(repeat["persisted"])
        self.assertEqual(
            repeat["reason_code"], "credential_adoption_existing_store_missing"
        )
        self.assertEqual(
            repeat["operator_action"],
            "create_and_review_fresh_replace_existing_plan",
        )
        self.assertFalse(repeat["credential_id_present"])
        self.assertEqual(self.native.prompts, prompts_before)
        self.assertEqual(len(self.native.writes), writes_before)
        self.assertEqual(len(first_transport.calls), provider_calls_before)

        replacement_transport = intake_transport()
        replacement_plan = make_plan(
            replace_existing=True,
            request_id_factory=lambda: "intake_explicit_replacement12345",
        )
        replacement = execute_windows_notion_credential_adoption(
            self.root,
            replacement_plan,
            expected_plan_digest=str(replacement_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=replacement_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
                credential_id_factory=lambda: "cred_replacement1234567890",
                backend_id_factory=lambda: "backend_replacement1234567890",
            ),
        )
        self.assertTrue(replacement["ok"])
        self.assertTrue(replacement["persisted"])
        self.assertEqual(self.native.prompts, prompts_before + 1)

    def test_repeat_adoption_store_probe_failure_never_prompts_or_calls_provider(self) -> None:
        first, first_transport = self._adopt()
        self.assertTrue(first["ok"])
        prompts_before = self.native.prompts
        writes_before = len(self.native.writes)
        provider_calls_before = len(first_transport.calls)
        secret_targets = [
            target
            for target in self.native.values
            if "/backend_" in target and "backend_key_" not in target
        ]
        self.assertEqual(len(secret_targets), 1)
        self.native.probe_fail_targets.add(secret_targets[0])

        repeat_plan = make_plan(
            request_id_factory=lambda: "intake_probe_failure_no_prompt123"
        )
        repeat = execute_windows_notion_credential_adoption(
            self.root,
            repeat_plan,
            expected_plan_digest=str(repeat_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=first_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )
        self.assertFalse(repeat["ok"])
        self.assertEqual(
            repeat["reason_code"],
            "credential_adoption_existing_store_probe_failed",
        )
        self.assertEqual(self.native.prompts, prompts_before)
        self.assertEqual(len(self.native.writes), writes_before)
        self.assertEqual(len(first_transport.calls), provider_calls_before)

    def test_repeat_adoption_rejects_replaced_secret_before_provider_or_prompt(self) -> None:
        first, _first_transport = self._adopt()
        self.assertTrue(first["ok"])
        secret_targets = [
            target
            for target in self.native.values
            if "/backend_" in target and "backend_key_" not in target
        ]
        self.assertEqual(len(secret_targets), 1)
        self.native.values[secret_targets[0]] = bytearray(b"different synthetic token")
        prompts_before = self.native.prompts
        writes_before = len(self.native.writes)
        repeat_transport = FakeTransport([])

        repeat_plan = make_plan(
            request_id_factory=lambda: "intake_replaced_store_no_prompt1"
        )
        repeat = execute_windows_notion_credential_adoption(
            self.root,
            repeat_plan,
            expected_plan_digest=str(repeat_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=repeat_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )
        self.assertFalse(repeat["ok"])
        self.assertEqual(
            repeat["reason_code"],
            "credential_adoption_existing_store_fingerprint_mismatch",
        )
        self.assertEqual(self.native.prompts, prompts_before)
        self.assertEqual(len(self.native.writes), writes_before)
        self.assertEqual(repeat_transport.calls, [])
        self.assertNotIn(SECRET_TEXT, json.dumps(repeat, ensure_ascii=False))

    def test_repeat_adoption_exact_secret_read_failure_never_prompts(self) -> None:
        first, _first_transport = self._adopt()
        self.assertTrue(first["ok"])
        secret_targets = [
            target
            for target in self.native.values
            if "/backend_" in target and "backend_key_" not in target
        ]
        self.assertEqual(len(secret_targets), 1)
        self.native.read_fail_targets.add(secret_targets[0])
        prompts_before = self.native.prompts
        repeat_transport = FakeTransport([])

        repeat_plan = make_plan(
            request_id_factory=lambda: "intake_store_read_failure12345"
        )
        repeat = execute_windows_notion_credential_adoption(
            self.root,
            repeat_plan,
            expected_plan_digest=str(repeat_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=repeat_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )
        self.assertFalse(repeat["ok"])
        self.assertEqual(
            repeat["reason_code"],
            "credential_adoption_existing_store_probe_failed",
        )
        self.assertEqual(self.native.prompts, prompts_before)
        self.assertEqual(repeat_transport.calls, [])

    def test_repeat_adoption_revalidates_the_current_reviewed_anchor(self) -> None:
        first, _first_transport = self._adopt()
        self.assertTrue(first["ok"])
        different_anchor = str(uuid.UUID(int=103))
        repeat_transport = FakeTransport(
            [
                FakeResponse(
                    {
                        "object": "user",
                        "id": USER_ID,
                        "type": "bot",
                        "bot": {"workspace_id": WORKSPACE_ID},
                    }
                ),
                FakeResponse({"object": "error"}, status=404),
            ]
        )
        prompts_before = self.native.prompts

        repeat_plan = make_plan(
            reviewed_anchor_uuid=different_anchor,
            request_id_factory=lambda: "intake_changed_anchor_no_prompt12",
        )
        repeat = execute_windows_notion_credential_adoption(
            self.root,
            repeat_plan,
            expected_plan_digest=str(repeat_plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=different_anchor,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=repeat_transport),
                key_provider=self.key_provider,
                now_factory=lambda: NOW,
            ),
        )
        self.assertFalse(repeat["ok"])
        self.assertEqual(
            repeat["reason_code"],
            "credential_adoption_existing_scope_revalidation_failed",
        )
        self.assertEqual(
            repeat["operator_action"],
            "review_current_notion_anchor_and_connection_before_retry",
        )
        self.assertEqual(self.native.prompts, prompts_before)
        self.assertEqual(len(repeat_transport.calls), 2)
        self.assertNotIn(different_anchor, json.dumps(repeat, ensure_ascii=False))

    def test_archive_identity_drift_blocks_before_sid_key_ui_or_provider(self) -> None:
        plan = make_plan()
        (self.root / "archive.yml").write_text(
            "archive_id: archive:changed-after-approval\n",
            encoding="utf-8",
        )
        transport = intake_transport()
        result = execute_windows_notion_credential_adoption(
            self.root,
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                self.native,
                NotionHttpAdapter(transport=transport),
                self.key_provider,
                now_factory=lambda: NOW,
            ),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["reason_code"],
            "credential_adoption_archive_identity_mismatch",
        )
        self.assertEqual(result["operations"], APPROVED_WORKER_OPERATIONS_UNKNOWN)
        self.assertEqual(self.native.sid_reads, 0)
        self.assertEqual(self.native.writes, [])
        self.assertEqual(self.native.reads, [])
        self.assertEqual(self.native.prompts, 0)
        self.assertEqual(transport.calls, [])

    def test_archive_identity_is_rechecked_at_archive_key_callback_boundary(self) -> None:
        plan = make_plan()
        transport = intake_transport()
        result = execute_windows_notion_credential_adoption(
            self.root,
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                self.native,
                NotionHttpAdapter(transport=transport),
                ArchiveIdentityMutatingKeyProvider(self.root),
                now_factory=lambda: NOW,
            ),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["reason_code"],
            "credential_adoption_archive_identity_mismatch",
        )
        self.assertEqual(result["operations"], APPROVED_WORKER_OPERATIONS_UNKNOWN)
        self.assertEqual(self.native.sid_reads, 1)
        self.assertEqual(self.native.prompts, 0)
        self.assertEqual(self.native.writes, [])
        self.assertEqual(transport.calls, [])

    def test_local_invalid_input_stops_before_store_and_provider_with_1100(self) -> None:
        native = FakeWindowsNative(secret_text=" ")
        key_provider = StableArchiveFingerprintKeyProvider(
            native,
            random_bytes=lambda _size: ARCHIVE_KEY,
        )
        transport = FakeTransport([])
        plan = make_plan(request_id_factory=lambda: "intake_local_invalid123456")
        result = execute_windows_notion_credential_adoption(
            self.root,
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native,
                NotionHttpAdapter(transport=transport),
                key_provider,
                now_factory=lambda: NOW,
                credential_id_factory=lambda: CREDENTIAL_ID,
                backend_id_factory=lambda: BACKEND_ID,
            ),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(
            result["reason_code"], "credential_input_invalid_for_provider"
        )
        self.assertEqual(result["rollback_status"], "not_required")
        self.assert_adoption_stage(result, "1100")
        self.assertEqual(transport.calls, [])
        self.assertFalse(
            any(
                "/backend_" in target and "backend_key_" not in target
                for target in native.values
            )
        )

    def test_store_write_failure_rolls_back_without_provider_and_reports_1110(self) -> None:
        native = FakeWindowsNative(secret_write_fails=True)
        key_provider = StableArchiveFingerprintKeyProvider(
            native,
            random_bytes=lambda _size: ARCHIVE_KEY,
        )
        transport = FakeTransport([])
        plan = make_plan(request_id_factory=lambda: "intake_store_failed1234567")
        result = execute_windows_notion_credential_adoption(
            self.root,
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native,
                NotionHttpAdapter(transport=transport),
                key_provider,
                now_factory=lambda: NOW,
                credential_id_factory=lambda: CREDENTIAL_ID,
                backend_id_factory=lambda: BACKEND_ID,
            ),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], "store_write_failed")
        self.assertEqual(result["rollback_status"], "deleted")
        self.assertTrue(result["store_absence_verified"])
        self.assert_adoption_stage(result, "1110")
        self.assertEqual(transport.calls, [])

    def test_provider_preflight_failure_is_not_auth_rejection_and_reports_1110(self) -> None:
        class NoProviderRequestVerifier:
            def validate_secret_input(
                self, _secret: memoryview, _provider: str
            ) -> bool:
                return True

            def verify_identity(
                self,
                _secret: memoryview,
                *,
                provider: str,
                reviewed_anchor_uuid: str,
                provider_request_observer,
            ):
                raise RuntimeError("synthetic pre-transport failure")

        class NoProviderRequestAdapter:
            def secure_intake_verifier(self):
                return NoProviderRequestVerifier()

        native = FakeWindowsNative()
        key_provider = StableArchiveFingerprintKeyProvider(
            native,
            random_bytes=lambda _size: ARCHIVE_KEY,
        )
        plan = make_plan(request_id_factory=lambda: "intake_no_provider_request123")
        result = execute_windows_notion_credential_adoption(
            self.root,
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native,
                NoProviderRequestAdapter(),  # type: ignore[arg-type]
                key_provider,
                now_factory=lambda: NOW,
                credential_id_factory=lambda: CREDENTIAL_ID,
                backend_id_factory=lambda: BACKEND_ID,
            ),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], "provider_request_not_attempted")
        self.assertNotEqual(result["reason_code"], "provider_auth_rejected")
        self.assertEqual(result["rollback_status"], "deleted")
        self.assertTrue(result["store_absence_verified"])
        self.assert_adoption_stage(result, "1110")

    def test_provider_failure_reports_unknown_live_counts_after_confirmed_delete(self) -> None:
        native = FakeWindowsNative()
        key_provider = StableArchiveFingerprintKeyProvider(
            native,
            random_bytes=lambda _size: ARCHIVE_KEY,
        )
        transport = FakeTransport([FakeResponse({}, status=401)])
        plan = make_plan(request_id_factory=lambda: "intake_provider_failed12345")
        result = execute_windows_notion_credential_adoption(
            self.root,
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native,
                NotionHttpAdapter(transport=transport),
                key_provider,
                now_factory=lambda: NOW,
                credential_id_factory=lambda: CREDENTIAL_ID,
                backend_id_factory=lambda: BACKEND_ID,
            ),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], "provider_auth_rejected")
        self.assertEqual(result["rollback_status"], "deleted")
        self.assertTrue(result["store_absence_verified"])
        self.assert_adoption_stage(result, "1111")
        self.assertEqual(result["operations"], APPROVED_WORKER_OPERATIONS_UNKNOWN)
        self.assertEqual(native.sid_reads, 1)
        self.assertEqual(native.prompts, 1)
        self.assertEqual(len(transport.calls), 1)

    def test_list_never_creates_a_missing_archive_key(self) -> None:
        empty_native = FakeWindowsNative()
        result = list_authenticated_secure_credentials(
            self.root,
            native=empty_native,
            key_provider=StableArchiveFingerprintKeyProvider(empty_native),
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], "credential_registry_key_not_found")
        self.assertEqual(empty_native.writes, [])
        self.assertEqual(empty_native.reads, [])
        self.assertEqual(
            result["operations"],
            AUTHENTICATED_KEY_READ_OPERATIONS_UNKNOWN,
        )

    def test_list_failure_after_exact_archive_key_read_never_reports_zero(self) -> None:
        native = FakeWindowsNative()
        key_provider = StableArchiveFingerprintKeyProvider(
            native,
            random_bytes=lambda _size: ARCHIVE_KEY,
        )
        key_provider.use_key(
            self.root,
            lambda _key: None,
            create_if_missing=True,
        )
        reads_before = len(native.reads)

        with patch.object(
            credential_workflows,
            "list_secure_credentials",
            side_effect=RuntimeError("PRIVATE REGISTRY FAILURE"),
        ):
            result = list_authenticated_secure_credentials(
                self.root,
                native=native,
                key_provider=key_provider,
            )

        self.assertFalse(result["ok"])
        self.assertGreater(len(native.reads), reads_before)
        self.assertEqual(
            result["operations"],
            AUTHENTICATED_KEY_READ_OPERATIONS_UNKNOWN,
        )
        self.assertNotIn("PRIVATE REGISTRY FAILURE", json.dumps(result))

    def test_post_key_non_mapping_results_keep_unknown_operation_envelope(self) -> None:
        class NonMappingKeyProvider:
            def use_key(self, *_args, **_kwargs):
                return "PRIVATE NON-MAPPING RESULT"

        provider = NonMappingKeyProvider()
        listed = list_authenticated_secure_credentials(
            self.root,
            native=FakeWindowsNative(),
            key_provider=provider,
        )
        planned = plan_authenticated_credential_lifecycle(
            self.root,
            provider="notion",
            workspace_fingerprint="sha256:" + "1" * 64,
            selected_default_credential_id=None,
            native=FakeWindowsNative(),
            key_provider=provider,
        )

        self.assertEqual(
            listed["operations"],
            AUTHENTICATED_KEY_READ_OPERATIONS_UNKNOWN,
        )
        self.assertEqual(
            planned["operations"],
            AUTHENTICATED_KEY_READ_OPERATIONS_UNKNOWN,
        )
        self.assertNotIn(
            "PRIVATE NON-MAPPING RESULT",
            json.dumps([listed, planned]),
        )

    def test_delete_failed_rollback_is_preserved_without_credential_id(self) -> None:
        native = FakeWindowsNative(delete_fails=True)
        key_provider = StableArchiveFingerprintKeyProvider(
            native,
            random_bytes=lambda _size: ARCHIVE_KEY,
        )
        transport = FakeTransport([FakeResponse({}, status=401)])
        plan = make_plan(request_id_factory=lambda: "intake_rollback1234567890")
        result = execute_windows_notion_credential_adoption(
            self.root,
            plan,
            expected_plan_digest=str(plan["plan_digest"]),
            expected_archive_id=ARCHIVE_ID,
            reviewed_anchor_uuid=ANCHOR,
            requested_capabilities=CAPABILITIES,
            approved=True,
            worker_spawner=InjectedCredentialAdoptionWorkerSpawner(
                native,
                NotionHttpAdapter(transport=transport),
                key_provider,
                now_factory=lambda: NOW,
                credential_id_factory=lambda: CREDENTIAL_ID,
                backend_id_factory=lambda: BACKEND_ID,
            ),
        )
        self.assertFalse(result["ok"])
        self.assertFalse(result["persisted"])
        self.assertEqual(result["rollback_status"], "delete_failed")
        self.assertFalse(result["store_absence_verified"])
        self.assert_adoption_stage(result, "1111")
        self.assertEqual(
            result["operator_action"],
            "stop_and_remove_the_exact_encrypted_store_entry",
        )
        self.assertEqual(result["operations"], APPROVED_WORKER_OPERATIONS_UNKNOWN)
        self.assertNotIn("credential_id", result)
        rendered = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(SECRET_TEXT, rendered)
        self.assertNotIn(BACKEND_ID, rendered)

    def test_lifecycle_then_recovery_replays_without_live_reads(self) -> None:
        transport = intake_transport(include_recovery=True)
        adopted, _ = self._adopt(transport=transport)
        self.assertTrue(adopted["ok"])
        self.assertEqual(self.native.prompts, 1)
        initial_list = list_authenticated_secure_credentials(
            self.root,
            native=self.native,
            key_provider=self.key_provider,
        )
        row = initial_list["credentials"][0]
        workspace = str(row["verified_workspace_fingerprint"])

        lifecycle_plan = plan_authenticated_credential_lifecycle(
            self.root,
            provider="notion",
            workspace_fingerprint=workspace,
            selected_default_credential_id=CREDENTIAL_ID,
            revocation_pending_credential_ids=(),
            native=self.native,
            key_provider=self.key_provider,
        )
        self.assertEqual(lifecycle_plan["status"], "human_decision_required")
        self.assertFalse(lifecycle_plan["persisted"])
        self.assertFalse(row["scope_binding"]["persisted"])
        self.assertEqual(
            lifecycle_plan["operations"],
            AUTHENTICATED_KEY_READ_OPERATIONS_UNKNOWN,
        )

        lifecycle = approve_authenticated_credential_lifecycle(
            self.root,
            provider="notion",
            workspace_fingerprint=workspace,
            selected_default_credential_id=CREDENTIAL_ID,
            revocation_pending_credential_ids=(),
            expected_plan_sha256=str(lifecycle_plan["plan_sha256"]),
            reviewed_by="tester-1",
            native=self.native,
            key_provider=self.key_provider,
        )
        self.assertTrue(lifecycle["ok"])
        self.assertEqual(self.native.prompts, 1)
        self.assertEqual(lifecycle["status"], "decision_recorded")
        self.assertFalse(lifecycle["delete_performed"])
        self.assertFalse(lifecycle["revoke_performed"])
        self.assertEqual(
            lifecycle["operations"],
            AUTHENTICATED_KEY_WRITE_OPERATIONS_UNKNOWN,
        )

        listed = list_authenticated_secure_credentials(
            self.root,
            native=self.native,
            key_provider=self.key_provider,
        )
        approved_row = listed["credentials"][0]
        self.assertTrue(approved_row["broker_authoritative"])
        self.assertTrue(approved_row["scope_binding"]["persisted"])
        self.assertEqual(
            listed["operations"],
            AUTHENTICATED_KEY_READ_OPERATIONS_UNKNOWN,
        )
        manifest = make_manifest(dict(approved_row["scope_binding"]))
        recovery_plan = plan_recovery(self.root, manifest, max_items=1)
        self.assertTrue(recovery_plan["ok"])

        derived_fingerprint_keys: list[bytearray] = []
        real_derive = credential_workflows.derive_windows_fingerprint_key

        def capture_derived_key(key_view, owner_binding):
            derived = real_derive(key_view, owner_binding)
            derived_fingerprint_keys.append(derived)
            return derived

        with patch.object(
            credential_workflows,
            "derive_windows_fingerprint_key",
            side_effect=capture_derived_key,
        ):
            recovery = execute_spawned_authenticated_notion_page_recovery(
                self.root,
                manifest,
                expected_plan_sha256=str(recovery_plan["plan_sha256"]),
                reviewed_by="tester-1",
                max_items=1,
                approved=True,
                worker_spawner=InjectedNotionRecoveryWorkerSpawner(
                    native=self.native,
                    notion_adapter=NotionHttpAdapter(transport=transport),
                    key_provider=self.key_provider,
                    request_pacer=NoOpPacer(),
                    sleep=lambda _seconds: None,
                    jitter=lambda: 0.0,
                    clock=lambda: NOW,
                ),
            )
        self.assertTrue(recovery["ok"])
        self.assertEqual(recovery["status_class"], "written")
        self.assertEqual(recovery["operations"]["credential_reads"], 1)
        self.assertEqual(recovery["operations"]["credential_resolution_attempts"], 1)
        self.assertEqual(len(derived_fingerprint_keys), 1)
        self.assertTrue(all(value == 0 for value in derived_fingerprint_keys[0]))
        self.assertEqual(len(transport.calls), 5)
        self.assertEqual(self.native.prompts, 1)

        native_reads_before = len(self.native.reads)
        provider_calls_before = len(transport.calls)
        replay = execute_spawned_authenticated_notion_page_recovery(
            self.root,
            manifest,
            expected_plan_sha256=str(recovery_plan["plan_sha256"]),
            reviewed_by="tester-1",
            max_items=1,
            approved=True,
            worker_spawner=FailIfRecoveryWorkerRuns(),
        )
        self.assertTrue(replay["ok"])
        self.assertEqual(replay["status_class"], "no_change")
        self.assertEqual(replay["operations"]["provider_calls"], 0)
        self.assertEqual(replay["operations"]["credential_reads"], 0)
        self.assertEqual(len(self.native.reads), native_reads_before)
        self.assertEqual(len(transport.calls), provider_calls_before)
        self.assertEqual(self.native.prompts, 1)

    def test_spawned_recovery_projection_rejects_child_covert_channels(self) -> None:
        manifest = make_manifest(
            {
                "credential_id": CREDENTIAL_ID,
                "workspace_fingerprint": "sha256:" + "1" * 64,
                "scope_receipt_sha256": "sha256:" + "2" * 64,
                "revision": "projection-test",
                "persisted": True,
                "workspace_evidence_verified": True,
            }
        )
        preview = plan_recovery(self.root, manifest, max_items=1)
        valid = make_valid_recovery_worker_result(preview)
        accepted = execute_spawned_authenticated_notion_page_recovery(
            self.root,
            manifest,
            expected_plan_sha256=str(preview["plan_sha256"]),
            reviewed_by="tester-1",
            max_items=1,
            worker_spawner=StaticRecoveryWorkerSpawner(valid),
        )
        self.assertTrue(accepted["ok"])
        self.assertEqual(accepted["request_sha256"], preview["request_sha256"])
        self.assertEqual(accepted["plan_sha256"], preview["plan_sha256"])

        lost_evidence_contract = credential_workflows._RecoveryProjectionContract(
            request_sha256=str(preview["request_sha256"]),
            plan_sha256=str(preview["plan_sha256"]),
            group_count=1,
            input_item_count=2,
            selected_item_count=2,
            unselected_item_count=0,
            recovered_verified_count=1,
            provider_pending_count=1,
        )
        refetched = copy.deepcopy(valid)
        refetched["counts"].update(
            {
                "input_item_count": 2,
                "selected_item_count": 2,
                "processed_item_count": 2,
                "replayed_recovered_count": 0,
                "outcomes": {
                    "recovered": 2,
                    "deleted": 0,
                    "forbidden": 0,
                    "not_found_or_not_shared": 0,
                    "retryable_error": 0,
                    "partial": 0,
                },
                "total_accounted_count": 2,
            }
        )
        refetched["operations"].update(
            {
                "provider_calls": 6,
                "paced_request_count": 6,
                "objects_created": 2,
                "manifest_rows_created": 2,
                "projection_rows_created": 2,
                "resume_rows_created": 4,
            }
        )
        lost_evidence_projection = (
            credential_workflows._project_recovery_worker_result(
                refetched,
                contract=lost_evidence_contract,
            )
        )
        self.assertTrue(lost_evidence_projection["ok"])
        self.assertEqual(
            lost_evidence_projection["counts"]["replayed_recovered_count"],
            0,
        )

        polluted: list[dict[str, object]] = []
        candidate = copy.deepcopy(valid)
        candidate["reason_code"] = "arbitrary_child_channel"
        polluted.append(candidate)
        candidate = copy.deepcopy(valid)
        candidate["blockers"] = ["arbitrary_child_channel"]
        polluted.append(candidate)
        candidate = copy.deepcopy(valid)
        candidate["privacy_guards"]["arbitrary_child_channel"] = False
        polluted.append(candidate)
        candidate = copy.deepcopy(valid)
        candidate["request_sha256"] = "sha256:" + "a" * 64
        polluted.append(candidate)
        candidate = copy.deepcopy(valid)
        candidate["plan_sha256"] = "sha256:" + "b" * 64
        polluted.append(candidate)
        candidate = copy.deepcopy(valid)
        candidate["counts"]["processed_item_count"] = 999
        polluted.append(candidate)
        candidate = copy.deepcopy(valid)
        candidate["operations"]["credential_resolution_attempts"] = 2
        polluted.append(candidate)
        candidate = copy.deepcopy(valid)
        candidate["operations"]["paced_request_count"] = 2
        polluted.append(candidate)

        for raw_result in polluted:
            with self.subTest(raw_result=raw_result):
                blocked = execute_spawned_authenticated_notion_page_recovery(
                    self.root,
                    manifest,
                    expected_plan_sha256=str(preview["plan_sha256"]),
                    reviewed_by="tester-1",
                    max_items=1,
                    worker_spawner=StaticRecoveryWorkerSpawner(raw_result),
                )
                self.assertFalse(blocked["ok"])
                self.assertEqual(
                    blocked["reason_code"],
                    "notion_page_recovery_worker_state_unknown",
                )
                self.assertEqual(
                    blocked["durable_state"], "unknown_may_have_changed"
                )
                self.assertEqual(
                    blocked["operator_action"],
                    "reconcile_and_rerun_same_approved_plan",
                )
                self.assertIsNone(blocked["counts"]["processed_item_count"])
                self.assertIsNone(blocked["operations"]["provider_calls"])
                self.assertIsNone(blocked["receipt_created"])
                self.assertEqual(
                    blocked["request_sha256"], preview["request_sha256"]
                )
                self.assertEqual(blocked["plan_sha256"], preview["plan_sha256"])
                self.assertNotIn(
                    "arbitrary_child_channel",
                    json.dumps(blocked, ensure_ascii=False),
                )

    def test_spawned_recovery_projection_accepts_fixed_authority_failures(self) -> None:
        manifest = make_manifest(
            {
                "credential_id": CREDENTIAL_ID,
                "workspace_fingerprint": "sha256:" + "1" * 64,
                "scope_receipt_sha256": "sha256:" + "2" * 64,
                "revision": "projection-authority-test",
                "persisted": True,
                "workspace_evidence_verified": True,
            }
        )
        preview = plan_recovery(self.root, manifest, max_items=1)

        def failed_candidate(
            blocker: str,
            *,
            status_class: str,
            operations: dict[str, int | float],
            receipt_created: bool,
        ) -> dict[str, object]:
            candidate = make_valid_recovery_worker_result(preview)
            candidate.update(
                {
                    "ok": False,
                    "status_class": status_class,
                    "reason_code": (
                        "notion_page_recovery_partial"
                        if status_class == "partial"
                        else "notion_page_recovery_blocked"
                    ),
                    "receipt_created": receipt_created,
                    "blockers": [blocker],
                }
            )
            candidate["counts"].update(
                {
                    "processed_item_count": 0,
                    "pending_item_count": 1,
                    "outcomes": {
                        "recovered": 0,
                        "deleted": 0,
                        "forbidden": 0,
                        "not_found_or_not_shared": 0,
                        "retryable_error": 0,
                        "partial": 0,
                    },
                }
            )
            candidate["operations"] = operations
            return candidate

        zero = {name: 0 for name in make_valid_recovery_worker_result(preview)["operations"]}
        provider_observed = dict(zero)
        provider_observed.update(
            {
                "provider_calls": 3,
                "paced_request_count": 3,
                "credential_resolution_attempts": 1,
                "credential_reads": 1,
            }
        )
        preprovider_authority = dict(zero)
        preprovider_authority.update(
            {
                "paced_request_count": 1,
                "credential_resolution_attempts": 1,
                "credential_reads": 1,
            }
        )
        cases = (
            (
                "notion_page_recovery_archive_identity_changed",
                "blocked",
                zero,
                False,
            ),
            ("durable_write_failed", "partial", provider_observed, False),
            (
                "durable_write_verification_failed",
                "partial",
                provider_observed,
                False,
            ),
            (
                "credential_authority_changed",
                "partial",
                preprovider_authority,
                True,
            ),
        )
        for blocker, status_class, operations, receipt_created in cases:
            with self.subTest(blocker=blocker):
                result = execute_spawned_authenticated_notion_page_recovery(
                    self.root,
                    manifest,
                    expected_plan_sha256=str(preview["plan_sha256"]),
                    reviewed_by="tester-1",
                    max_items=1,
                    approved=True,
                    worker_spawner=StaticRecoveryWorkerSpawner(
                        failed_candidate(
                            blocker,
                            status_class=status_class,
                            operations=operations,
                            receipt_created=receipt_created,
                        )
                    ),
                )
                self.assertEqual(result["status_class"], status_class, result)
                self.assertEqual(result["blockers"], [blocker])
                self.assertEqual(result["receipt_created"], receipt_created)

    def test_recovery_rejects_exact_vault_secret_that_no_longer_matches_receipt(self) -> None:
        transport = intake_transport(include_recovery=True)
        adopted, _ = self._adopt(transport=transport)
        self.assertTrue(adopted["ok"])
        listed = list_authenticated_secure_credentials(
            self.root,
            native=self.native,
            key_provider=self.key_provider,
        )
        row = listed["credentials"][0]
        workspace = str(row["verified_workspace_fingerprint"])
        lifecycle_plan = plan_authenticated_credential_lifecycle(
            self.root,
            provider="notion",
            workspace_fingerprint=workspace,
            selected_default_credential_id=CREDENTIAL_ID,
            revocation_pending_credential_ids=(),
            native=self.native,
            key_provider=self.key_provider,
        )
        lifecycle = approve_authenticated_credential_lifecycle(
            self.root,
            provider="notion",
            workspace_fingerprint=workspace,
            selected_default_credential_id=CREDENTIAL_ID,
            revocation_pending_credential_ids=(),
            expected_plan_sha256=str(lifecycle_plan["plan_sha256"]),
            reviewed_by="tester-1",
            native=self.native,
            key_provider=self.key_provider,
        )
        self.assertTrue(lifecycle["ok"])
        approved_row = list_authenticated_secure_credentials(
            self.root,
            native=self.native,
            key_provider=self.key_provider,
        )["credentials"][0]
        manifest = make_manifest(dict(approved_row["scope_binding"]))
        preview = plan_recovery(self.root, manifest, max_items=1)

        secret_targets = [
            target
            for target, value in self.native.values.items()
            if bytes(value) == SECRET_TEXT.encode("utf-8")
        ]
        self.assertEqual(len(secret_targets), 1)
        self.native.values[secret_targets[0]] = bytearray(
            b"different_exact_vault_secret"
        )
        provider_calls_before = len(transport.calls)
        blocked = execute_spawned_authenticated_notion_page_recovery(
            self.root,
            manifest,
            expected_plan_sha256=str(preview["plan_sha256"]),
            reviewed_by="tester-1",
            max_items=1,
            worker_spawner=InjectedNotionRecoveryWorkerSpawner(
                native=self.native,
                notion_adapter=NotionHttpAdapter(transport=transport),
                key_provider=self.key_provider,
                request_pacer=NoOpPacer(),
                sleep=lambda _seconds: None,
                jitter=lambda: 0.0,
                clock=lambda: NOW,
            ),
        )
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["status_class"], "partial")
        self.assertEqual(
            blocked["reason_code"],
            "notion_page_recovery_partial",
        )
        self.assertEqual(blocked["blockers"], ["credential_resolution_failed"])
        self.assertEqual(
            blocked["operations"]["credential_resolution_attempts"], 1
        )
        self.assertEqual(blocked["operations"]["credential_reads"], 0)
        self.assertEqual(blocked["operations"]["provider_calls"], 0)
        self.assertEqual(len(transport.calls), provider_calls_before)

    def test_recovery_worker_start_evidence_controls_zero_vs_unknown(self) -> None:
        class FakeConnection:
            def __init__(self, *, eof: bool = False) -> None:
                self.eof = eof

            def recv(self):
                if self.eof:
                    raise EOFError
                raise AssertionError("send side cannot receive")

            def close(self) -> None:
                pass

        class FakeProcess:
            def __init__(self, *, fail_start: bool) -> None:
                self.fail_start = fail_start
                self.exitcode = 0

            def start(self) -> None:
                if self.fail_start:
                    raise RuntimeError("synthetic pre-start failure")

            def join(self) -> None:
                pass

            def is_alive(self) -> bool:
                return False

        class FakeSpawnContext:
            def __init__(self, *, fail_start: bool) -> None:
                self.process = FakeProcess(fail_start=fail_start)

            def Pipe(self, *, duplex: bool):
                if duplex is not False:
                    raise AssertionError("recovery pipe must be one-way")
                return FakeConnection(eof=True), FakeConnection()

            def Process(self, **_kwargs):
                return self.process

        manifest = make_manifest(
            {
                "credential_id": CREDENTIAL_ID,
                "workspace_fingerprint": "sha256:" + "1" * 64,
                "scope_receipt_sha256": "sha256:" + "2" * 64,
                "revision": "worker-start-test",
                "persisted": True,
                "workspace_evidence_verified": True,
            }
        )
        preview = plan_recovery(self.root, manifest, max_items=1)

        not_started = execute_spawned_authenticated_notion_page_recovery(
            self.root,
            manifest,
            expected_plan_sha256=str(preview["plan_sha256"]),
            reviewed_by="tester-1",
            max_items=1,
            worker_spawner=NotStartedRecoveryWorkerSpawner(),
        )
        self.assertFalse(not_started["ok"])
        self.assertEqual(
            not_started["reason_code"],
            "notion_page_recovery_worker_launch_failed",
        )
        self.assertEqual(not_started["operations"], ZERO_LIVE_OPERATIONS)
        self.assertNotIn("durable_state", not_started)

        with patch.object(
            credential_workflows.multiprocessing,
            "get_context",
            return_value=FakeSpawnContext(fail_start=True),
        ):
            production_prestart = execute_spawned_authenticated_notion_page_recovery(
                self.root,
                manifest,
                expected_plan_sha256=str(preview["plan_sha256"]),
                reviewed_by="tester-1",
                max_items=1,
            )
        self.assertEqual(
            production_prestart["reason_code"],
            "notion_page_recovery_worker_launch_failed",
        )
        self.assertEqual(production_prestart["operations"], ZERO_LIVE_OPERATIONS)

        with patch.object(
            credential_workflows.multiprocessing,
            "get_context",
            return_value=FakeSpawnContext(fail_start=False),
        ):
            production_eof = execute_spawned_authenticated_notion_page_recovery(
                self.root,
                manifest,
                expected_plan_sha256=str(preview["plan_sha256"]),
                reviewed_by="tester-1",
                max_items=1,
            )
        self.assertEqual(
            production_eof["reason_code"],
            "notion_page_recovery_worker_state_unknown",
        )
        self.assertEqual(
            production_eof["durable_state"], "unknown_may_have_changed"
        )

        boundary_unknown = execute_spawned_authenticated_notion_page_recovery(
            self.root,
            manifest,
            expected_plan_sha256=str(preview["plan_sha256"]),
            reviewed_by="tester-1",
            max_items=1,
            worker_spawner=RaisingRecoveryWorkerSpawner(),
        )
        self.assertFalse(boundary_unknown["ok"])
        self.assertEqual(
            boundary_unknown["reason_code"],
            "notion_page_recovery_worker_state_unknown",
        )
        self.assertEqual(
            boundary_unknown["operations"]["count_status"],
            "unknown_may_be_nonzero",
        )
        self.assertIsNone(
            boundary_unknown["operations"]["credential_resolution_attempts"]
        )

        preapproval_spawner = StaticRecoveryWorkerSpawner({})
        preapproval = execute_spawned_authenticated_notion_page_recovery(
            self.root,
            manifest,
            expected_plan_sha256=str(preview["plan_sha256"]),
            reviewed_by="tester-1",
            max_items=1,
            approved=False,
            worker_spawner=preapproval_spawner,
        )
        digest_blocked = execute_spawned_authenticated_notion_page_recovery(
            self.root,
            manifest,
            expected_plan_sha256="sha256:" + "0" * 64,
            reviewed_by="tester-1",
            max_items=1,
            worker_spawner=preapproval_spawner,
        )
        self.assertEqual(preapproval["operations"], ZERO_LIVE_OPERATIONS)
        self.assertEqual(digest_blocked["operations"], ZERO_LIVE_OPERATIONS)
        self.assertEqual(preapproval_spawner.calls, 0)

    def test_recovery_approval_and_digest_drift_are_zero_native_and_zero_write(self) -> None:
        manifest = make_manifest(
            {
                "credential_id": CREDENTIAL_ID,
                "workspace_fingerprint": "sha256:" + "1" * 64,
                "scope_receipt_sha256": "sha256:" + "2" * 64,
                "revision": "lifecycle-test",
                "persisted": True,
                "workspace_evidence_verified": True,
            }
        )
        plan = plan_recovery(self.root, manifest, max_items=1)
        before = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))
        blocked = execute_authenticated_notion_page_recovery(
            self.root,
            manifest,
            expected_plan_sha256=str(plan["plan_sha256"]),
            reviewed_by="tester-1",
            max_items=1,
            approved=False,
            native=self.native,
            key_provider=self.key_provider,
        )
        drift = execute_authenticated_notion_page_recovery(
            self.root,
            manifest,
            expected_plan_sha256="sha256:" + "0" * 64,
            reviewed_by="tester-1",
            max_items=1,
            approved=True,
            native=self.native,
            key_provider=self.key_provider,
        )
        wrong_archive = dict(manifest)
        wrong_archive["archive_id"] = "archive:wrong"
        mismatched = execute_authenticated_notion_page_recovery(
            self.root,
            wrong_archive,
            expected_plan_sha256=str(plan["plan_sha256"]),
            reviewed_by="tester-1",
            max_items=1,
            approved=True,
            native=self.native,
            key_provider=self.key_provider,
        )
        after = sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*"))
        self.assertFalse(blocked["ok"])
        self.assertFalse(drift["ok"])
        self.assertEqual(drift["reason_code"], "expected_plan_sha256_mismatch")
        self.assertFalse(mismatched["ok"])
        self.assertEqual(
            mismatched["reason_code"],
            "notion_page_recovery_archive_identity_mismatch",
        )
        self.assertEqual(self.native.writes, [])
        self.assertEqual(self.native.reads, [])
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
