from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

import wom_kit.credential_workflows as credential_workflows
from wom_kit.credential_secure_registry import StableArchiveFingerprintKeyProvider
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
from wom_kit.notion_http_adapter import NotionHttpAdapter
from wom_kit.notion_page_recovery import REQUEST_SCHEMA, plan_recovery


NOW = datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)
ARCHIVE_ID = "archive:test"
SID = "S-1-5-21-111111111-222222222-333333333-1001"
ANCHOR = str(uuid.UUID(int=101))
USER_ID = str(uuid.UUID(int=202))
PAGE_ID = str(uuid.UUID(int=303))
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
    delete_fails: bool = False
    values: dict[str, bytearray] = field(default_factory=dict, repr=False)
    writes: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    probes: list[str] = field(default_factory=list)
    prompts: int = 0
    sid_reads: int = 0

    def prompt_masked_secret(self, *, request_id: str) -> bytearray | None:
        self.prompts += 1
        if self.cancelled:
            return None
        return bytearray(SECRET_TEXT.encode("utf-8"))

    def write_generic(self, target_name: str, secret: memoryview) -> None:
        self.writes.append(target_name)
        self.values[target_name] = bytearray(secret)

    def generic_exists(self, target_name: str) -> bool:
        self.probes.append(target_name)
        return target_name in self.values

    def read_generic_secret_exact(self, target_name: str) -> bytearray:
        self.reads.append(target_name)
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


def intake_transport(*, include_recovery: bool = False) -> FakeTransport:
    outcomes = [
        FakeResponse({"object": "user", "id": USER_ID, "type": "bot"}),
        FakeResponse(
            {
                "object": "page",
                "id": ANCHOR,
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

    def test_adoption_worker_start_evidence_controls_zero_vs_unknown(self) -> None:
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
                    raise AssertionError("adoption pipe must be one-way")
                return FakeConnection(eof=True), FakeConnection()

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

    def test_success_is_authenticated_rediscoverable_and_failure_has_no_id(self) -> None:
        result, _transport = self._adopt()
        self.assertTrue(result["ok"])
        self.assertTrue(result["accepted"])
        self.assertTrue(result["persisted"])
        self.assertEqual(result["credential_id"], CREDENTIAL_ID)
        self.assertTrue(result["authenticated_rediscovery_verified"])
        self.assertTrue(result["human_default_decision_required"])
        self.assertEqual(result["operations"], APPROVED_WORKER_OPERATIONS_UNKNOWN)

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
        self.assertEqual(cancelled_native.sid_reads, 1)
        self.assertEqual(cancelled_native.prompts, 1)
        self.assertGreaterEqual(len(cancelled_native.probes), 2)
        self.assertEqual(len(cancelled_native.writes), 1)
        self.assertEqual(len(cancelled_native.reads), 1)
        self.assertEqual(cancelled_transport.calls, [])

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
        self.assertEqual(result["rollback_status"], "deleted")
        self.assertTrue(result["store_absence_verified"])
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
