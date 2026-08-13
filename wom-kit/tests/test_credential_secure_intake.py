from __future__ import annotations

import hashlib
import io
import json
import os
import stat as stat_module
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from wom_kit import credential_secure_intake as secure_intake_module
from wom_kit.credential_secure_intake import (
    AtomicJsonReceiptCommitter,
    CredentialIntakeStageError,
    FileOneTimeRequestClaims,
    InMemoryOneTimeRequestClaims,
    NOTION_PAT_SCOPE_FINGERPRINT_DOMAIN,
    NOTION_PAT_WORKSPACE_IDENTITY_BASIS,
    NOTION_WORKSPACE_IDENTITY_BASIS,
    RECEIPT_SCHEMA_VERSION,
    SecureIntakeProcessLauncher,
    SecureIntakeWorker,
    VerifiedCredentialIdentity,
    WindowsCredentialManagerExactStore,
    WindowsMaskedDialog,
    apply_duplicate_lifecycle_decision,
    create_secure_intake_plan,
)


NOW = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
ANCHOR = "f73f965a-7897-4ea8-b936-30824284dc23"
OTHER_ANCHOR = "a728be3d-3dd2-438d-9640-2226aa65d123"
SECRET_TEXT = "notion-private-PAT-must-never-leave-worker"
SECRET_BYTES = SECRET_TEXT.encode("utf-8")
FINGERPRINT_KEY = b"stable-local-fingerprint-key-32-bytes-minimum"
REQUEST_ID = "intake_1234567890abcdef"
CREDENTIAL_ID = "cred_1234567890abcdef"
BACKEND_ID = "backend_1234567890abcdef"


@dataclass
class FakeUI:
    value_factory: Any = field(default=lambda: bytearray(SECRET_BYTES), repr=False)
    calls: int = 0
    last_buffer: bytearray | None = field(default=None, repr=False)

    def request_secret(self, *, request_id: str) -> bytearray | None:
        self.calls += 1
        value = self.value_factory()
        self.last_buffer = value
        return value


@dataclass
class FakeStore:
    backend_kind: str = "fake_encrypted_store"
    write_error: bool = False
    probe_result: bool = True
    probe_error: bool = False
    delete_error: bool = False
    calls: list[tuple[str, str]] = field(default_factory=list)
    received: list[bytes] = field(default_factory=list, repr=False)

    def put_exact(self, backend_id: str, secret: memoryview) -> None:
        self.calls.append(("put_exact", backend_id))
        self.received.append(bytes(secret))
        if self.write_error:
            raise RuntimeError(f"store exploded around {SECRET_TEXT}")

    def probe_exact(self, backend_id: str) -> bool:
        self.calls.append(("probe_exact", backend_id))
        if self.probe_error:
            raise RuntimeError(f"probe exploded around {SECRET_TEXT}")
        return self.probe_result

    def delete_exact(self, backend_id: str) -> None:
        self.calls.append(("delete_exact", backend_id))
        if self.delete_error:
            raise RuntimeError(f"delete exploded around {SECRET_TEXT}")


@dataclass
class FakeVerifier:
    provider: str = "notion"
    anchor: str = ANCHOR
    error: bool = False
    stage_error: str | None = None
    subject_verified: bool = True
    anchor_access_verified: bool = True
    received: list[bytes] = field(default_factory=list, repr=False)

    def verify_identity(
        self,
        secret: memoryview,
        *,
        provider: str,
        reviewed_anchor_uuid: str,
    ) -> VerifiedCredentialIdentity:
        self.received.append(bytes(secret))
        if self.error:
            raise RuntimeError(f"provider leaked {SECRET_TEXT}")
        if self.stage_error is not None:
            raise CredentialIntakeStageError(self.stage_error)
        return VerifiedCredentialIdentity(
            provider=self.provider,
            account_subject="provider-user-id-private",
            workspace_identity="provider-workspace-id-private",
            reviewed_anchor_uuid=self.anchor,
            capabilities=("read_content", "retrieve_user_identity"),
            subject_verified=self.subject_verified,
            anchor_access_verified=self.anchor_access_verified,
        )


@dataclass
class FakeCommitter:
    error: bool = False
    receipts: list[dict[str, Any]] = field(default_factory=list)

    def commit_atomic(self, receipt: dict[str, Any]) -> str:
        self.receipts.append(dict(receipt))
        if self.error:
            raise RuntimeError(f"receipt failed with {SECRET_TEXT}")
        return f"receipts/{receipt['credential_id']}.json"


class SecureCredentialIntakeTests(unittest.TestCase):
    def plan(self, *, ttl_seconds: int = 300):
        return create_secure_intake_plan(
            provider="notion",
            account_label="personal",
            workspace_label="backup",
            purpose="source-recovery",
            reviewed_anchor_uuid=ANCHOR,
            owner_binding="windows-sid:S-1-5-21-test-user",
            requested_capabilities=("read-content",),
            ttl_seconds=ttl_seconds,
            now=NOW,
            request_id_factory=lambda: REQUEST_ID,
        )

    def worker(
        self,
        *,
        claims=None,
        ui=None,
        store=None,
        verifier=None,
        committer=None,
        now: datetime = NOW + timedelta(seconds=1),
    ) -> tuple[SecureIntakeWorker, FakeUI, FakeStore, FakeVerifier, FakeCommitter]:
        ui = ui or FakeUI()
        store = store or FakeStore()
        verifier = verifier or FakeVerifier()
        committer = committer or FakeCommitter()
        worker = SecureIntakeWorker(
            claims=claims or InMemoryOneTimeRequestClaims(),
            ui=ui,
            store=store,
            verifier=verifier,
            receipt_committer=committer,
            fingerprint_key=FINGERPRINT_KEY,
            credential_id_factory=lambda: CREDENTIAL_ID,
            backend_id_factory=lambda: BACKEND_ID,
            now_factory=lambda: now,
        )
        return worker, ui, store, verifier, committer

    def execute(self, worker: SecureIntakeWorker, plan=None) -> dict[str, Any]:
        plan = plan or self.plan()
        return worker.execute(
            plan,
            expected_plan_digest=plan.plan_digest,
            current_owner_binding="windows-sid:S-1-5-21-test-user",
        )

    def assert_secret_absent(self, value: Any) -> None:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        self.assertNotIn(SECRET_TEXT, rendered)
        self.assertNotIn(hashlib.sha256(SECRET_BYTES).hexdigest(), rendered)

    def assert_failed_without_id(self, result: dict[str, Any], reason: str) -> None:
        self.assertFalse(result["ok"], result)
        self.assertFalse(result["accepted"], result)
        self.assertFalse(result["persisted"], result)
        self.assertEqual(result["reason_code"], reason)
        self.assertNotIn("credential_id", result)
        self.assert_secret_absent(result)

    def assert_unknown_worker_state(self, result: dict[str, Any]) -> None:
        self.assertFalse(result["ok"], result)
        self.assertIsNone(result["accepted"], result)
        self.assertIsNone(result["persisted"], result)
        self.assertEqual(result["reason_code"], "worker_state_unknown")
        self.assertEqual(result["durable_state"], "unknown_may_have_changed")
        self.assertEqual(
            result["operator_action"],
            "reconcile_then_rerun_same_approved_plan",
        )
        self.assertFalse(result["worker_result_accepted"])
        self.assertFalse(result["secret_value_present"])
        self.assertFalse(result["reviewed_anchor_present_in_result"])
        self.assertFalse(result["backend_target_present"])
        counts = result["operations"]
        self.assertEqual(counts["count_status"], "unknown_may_be_nonzero")
        self.assertTrue(
            all(value is None for key, value in counts.items() if key != "count_status")
        )
        self.assert_secret_absent(result)

    def test_plan_is_content_free_and_all_actions_remain_closed(self) -> None:
        plan = self.plan()
        public = plan.to_public_dict()

        self.assertEqual(public["provider"], "notion")
        self.assertEqual(public["purpose"], "source_recovery")
        self.assertTrue(public["reviewed_anchor_present"])
        self.assertNotIn("reviewed_anchor_uuid", public)
        self.assertNotIn(ANCHOR, json.dumps(public, ensure_ascii=False))
        self.assertNotIn(ANCHOR, repr(plan))
        self.assertEqual(public["request_id"], REQUEST_ID)
        self.assertEqual(len(public["plan_digest"]), 64)
        self.assertTrue(all(value is False for value in public["closed_actions"].values()))
        self.assertNotIn("credential_id", public)
        self.assertNotIn("encrypted_backend_id", public)
        self.assert_secret_absent(public)

        for unsafe_label in (
            "token=sk-private-value",
            "secret_abcdefghijklmnopqrstuvwxyz0123456789",
            "ntn_abcdefghijklmnopqrstuvwxyz0123456789",
            "person@example.com",
            "https://provider.example/workspace",
            "C:\\private\\credential.txt",
        ):
            with self.assertRaises(ValueError):
                create_secure_intake_plan(
                    provider="notion",
                    account_label=unsafe_label,
                    workspace_label="backup",
                    purpose="source_recovery",
                    reviewed_anchor_uuid=ANCHOR,
                    owner_binding="windows-sid:S-1-5-21-test-user",
                    now=NOW,
                    request_id_factory=lambda: REQUEST_ID,
                )

    def test_success_is_atomic_persisted_and_secret_buffer_is_wiped(self) -> None:
        worker, ui, store, verifier, committer = self.worker()
        result = self.execute(worker)

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["persisted"])
        self.assertEqual(result["credential_id"], CREDENTIAL_ID)
        self.assertEqual(result["encrypted_backend_id"], BACKEND_ID)
        self.assertEqual(result["lifecycle_status"], "active")
        self.assertEqual(result["rotation_status"], "current")
        self.assertFalse(result["is_default"])
        self.assertEqual(
            result["workspace_identity_basis"],
            NOTION_WORKSPACE_IDENTITY_BASIS,
        )
        self.assertFalse(result["secret_value_present"])
        self.assertRegex(
            result["verified_workspace_fingerprint"], r"^sha256:[0-9a-f]{64}$"
        )
        self.assertRegex(
            result["verified_account_fingerprint"], r"^sha256:[0-9a-f]{64}$"
        )
        self.assertEqual(
            store.calls,
            [("put_exact", BACKEND_ID), ("probe_exact", BACKEND_ID)],
        )
        self.assertEqual(store.received, [SECRET_BYTES])
        self.assertEqual(verifier.received, [SECRET_BYTES])
        self.assertEqual(len(committer.receipts), 1)
        self.assertEqual(
            committer.receipts[0]["schema_version"], RECEIPT_SCHEMA_VERSION
        )
        self.assertEqual(
            committer.receipts[0]["workspace_identity_basis"],
            NOTION_WORKSPACE_IDENTITY_BASIS,
        )
        self.assertEqual(ui.last_buffer, bytearray(len(SECRET_BYTES)))
        self.assertNotIn("provider-user-id-private", json.dumps(result))
        self.assertNotIn("provider-workspace-id-private", json.dumps(result))
        self.assert_secret_absent(result)
        self.assert_secret_absent(committer.receipts)

    def test_person_pat_scope_is_domain_separated_from_exact_secret_hmac(self) -> None:
        verifier = FakeVerifier()

        def verify_pat(
            secret: memoryview,
            *,
            provider: str,
            reviewed_anchor_uuid: str,
        ) -> VerifiedCredentialIdentity:
            verifier.received.append(bytes(secret))
            return VerifiedCredentialIdentity(
                provider=provider,
                account_subject="provider-person-id-private",
                workspace_identity="notion-pat-token-scope",
                workspace_identity_basis=NOTION_PAT_WORKSPACE_IDENTITY_BASIS,
                reviewed_anchor_uuid=reviewed_anchor_uuid,
                capabilities=("read_content", "retrieve_user_identity"),
            )

        verifier.verify_identity = verify_pat  # type: ignore[method-assign]
        worker, _, _, _, committer = self.worker(verifier=verifier)
        result = self.execute(worker)

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["workspace_identity_basis"],
            NOTION_PAT_WORKSPACE_IDENTITY_BASIS,
        )
        expected = "sha256:" + hashlib.sha256(
            NOTION_PAT_SCOPE_FINGERPRINT_DOMAIN
            + str(result["fingerprint_digest"]).encode("ascii")
        ).hexdigest()
        self.assertEqual(result["verified_workspace_fingerprint"], expected)
        self.assertEqual(
            committer.receipts[0]["verified_workspace_fingerprint"], expected
        )
        rendered = json.dumps([result, committer.receipts], ensure_ascii=False)
        for private in (
            SECRET_TEXT,
            "provider-person-id-private",
            "notion-pat-token-scope",
            ANCHOR,
        ):
            self.assertNotIn(private, rendered)

    def test_store_write_failure_attempts_exact_rollback_and_issues_no_id(self) -> None:
        worker, _, store, _, committer = self.worker(store=FakeStore(write_error=True))
        result = self.execute(worker)

        self.assert_failed_without_id(result, "store_write_failed")
        self.assertEqual(
            store.calls,
            [("put_exact", BACKEND_ID), ("delete_exact", BACKEND_ID)],
        )
        self.assertEqual(committer.receipts, [])

    def test_store_presence_failure_rolls_back_once_and_issues_no_id(self) -> None:
        worker, _, store, verifier, committer = self.worker(
            store=FakeStore(probe_result=False)
        )
        result = self.execute(worker)

        self.assert_failed_without_id(result, "store_presence_not_verified")
        self.assertEqual(
            store.calls,
            [
                ("put_exact", BACKEND_ID),
                ("probe_exact", BACKEND_ID),
                ("delete_exact", BACKEND_ID),
            ],
        )
        self.assertEqual(verifier.received, [])
        self.assertEqual(committer.receipts, [])

    def test_provider_exception_is_redacted_and_rolls_back(self) -> None:
        worker, _, store, _, committer = self.worker(verifier=FakeVerifier(error=True))
        result = self.execute(worker)

        self.assert_failed_without_id(result, "provider_identity_unverified")
        self.assertEqual(store.calls[-1], ("delete_exact", BACKEND_ID))
        self.assertEqual(committer.receipts, [])

    def test_provider_stage_failures_are_distinct_redacted_and_rolled_back(self) -> None:
        expected_actions = {
            "provider_auth_rejected": "review_the_notion_credential_and_create_a_new_plan",
            "provider_identity_endpoint_unavailable": "create_a_new_plan_after_provider_identity_service_recovers",
            "reviewed_anchor_inaccessible": "review_page_access_and_create_a_new_plan",
        }
        for reason, expected_action in expected_actions.items():
            with self.subTest(reason=reason):
                worker, _, store, _, committer = self.worker(
                    verifier=FakeVerifier(stage_error=reason)
                )
                result = self.execute(worker)

                self.assert_failed_without_id(result, reason)
                self.assertEqual(result["rollback_status"], "deleted")
                self.assertEqual(result["operator_action"], expected_action)
                self.assertEqual(
                    store.calls,
                    [
                        ("put_exact", BACKEND_ID),
                        ("probe_exact", BACKEND_ID),
                        ("delete_exact", BACKEND_ID),
                    ],
                )
                self.assertEqual(committer.receipts, [])
                self.assertNotIn(SECRET_TEXT, json.dumps(result, ensure_ascii=False))

    def test_provider_stage_delete_failure_remains_unresolved(self) -> None:
        worker, _, store, _, _ = self.worker(
            store=FakeStore(delete_error=True),
            verifier=FakeVerifier(stage_error="provider_auth_rejected"),
        )
        result = self.execute(worker)

        self.assert_failed_without_id(result, "provider_auth_rejected")
        self.assertEqual(result["rollback_status"], "delete_failed")
        self.assertEqual(
            result["operator_action"],
            "stop_and_remove_the_exact_encrypted_store_entry",
        )

    def test_reviewed_anchor_mismatch_is_distinct_and_rolls_back(self) -> None:
        worker, _, store, _, committer = self.worker(
            verifier=FakeVerifier(anchor=OTHER_ANCHOR)
        )
        result = self.execute(worker)

        self.assert_failed_without_id(result, "reviewed_anchor_inaccessible")
        self.assertEqual(store.calls[-1], ("delete_exact", BACKEND_ID))
        self.assertEqual(committer.receipts, [])

    def test_receipt_failure_is_redacted_rolls_back_and_issues_no_id(self) -> None:
        worker, _, store, _, committer = self.worker(committer=FakeCommitter(error=True))
        result = self.execute(worker)

        self.assert_failed_without_id(result, "receipt_commit_failed")
        self.assertEqual(store.calls[-1], ("delete_exact", BACKEND_ID))
        self.assertEqual(len(committer.receipts), 1)
        self.assert_secret_absent(committer.receipts)

    def test_committed_receipt_with_untrusted_reference_is_safely_opaque(self) -> None:
        class UntrustedReferenceCommitter(FakeCommitter):
            def commit_atomic(self, receipt: dict[str, Any]) -> str:
                self.receipts.append(dict(receipt))
                return SECRET_TEXT

        worker, _, store, _, _ = self.worker(
            committer=UntrustedReferenceCommitter()
        )
        result = self.execute(worker)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["receipt_ref"], f"receipt:{CREDENTIAL_ID}")
        self.assertNotIn(("delete_exact", BACKEND_ID), store.calls)
        self.assert_secret_absent(result)

    def test_human_cancel_and_ui_exception_never_open_store(self) -> None:
        cancelled_ui = FakeUI(value_factory=lambda: None)
        worker, _, store, _, _ = self.worker(ui=cancelled_ui)
        cancelled = self.execute(worker)
        self.assert_failed_without_id(cancelled, "credential_input_cancelled_or_empty")
        self.assertEqual(store.calls, [])

        class ExplodingUI:
            def request_secret(self, *, request_id: str):
                raise RuntimeError(f"dialog exploded with {SECRET_TEXT}")

        worker, _, store, _, _ = self.worker(ui=ExplodingUI())
        unavailable = self.execute(worker)
        self.assert_failed_without_id(unavailable, "credential_input_not_received")
        self.assertEqual(store.calls, [])

    def test_request_expiry_replay_and_owner_binding_close_before_ui(self) -> None:
        plan = self.plan(ttl_seconds=30)
        worker, ui, store, _, _ = self.worker(now=NOW + timedelta(seconds=30))
        expired = self.execute(worker, plan)
        self.assert_failed_without_id(expired, "request_expired")
        self.assertEqual(ui.calls, 0)
        self.assertEqual(store.calls, [])

        worker, ui, store, _, _ = self.worker()
        first = self.execute(worker)
        second = self.execute(worker)
        self.assertTrue(first["ok"])
        self.assert_failed_without_id(second, "request_replayed")
        self.assertEqual(ui.calls, 1)
        self.assertEqual(store.calls.count(("put_exact", BACKEND_ID)), 1)

        plan = self.plan()
        worker, ui, store, _, _ = self.worker()
        mismatch = worker.execute(
            plan,
            expected_plan_digest=plan.plan_digest,
            current_owner_binding="windows-sid:different-user",
        )
        self.assert_failed_without_id(mismatch, "request_user_mismatch")
        self.assertEqual(ui.calls, 0)
        self.assertEqual(store.calls, [])

    def test_plan_digest_drift_closes_before_human_ui(self) -> None:
        plan = self.plan()
        worker, ui, store, _, _ = self.worker()
        result = worker.execute(
            plan,
            expected_plan_digest="0" * 64,
            current_owner_binding="windows-sid:S-1-5-21-test-user",
        )

        self.assert_failed_without_id(result, "plan_digest_mismatch")
        self.assertEqual(ui.calls, 0)
        self.assertEqual(store.calls, [])

    def test_worker_writes_nothing_to_parent_stdout_or_stderr(self) -> None:
        worker, _, _, _, _ = self.worker(verifier=FakeVerifier(error=True))
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = self.execute(worker)

        self.assert_failed_without_id(result, "provider_identity_unverified")
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.assertNotIn(SECRET_TEXT, repr(worker))

    def test_file_claim_is_one_use_under_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            claims = FileOneTimeRequestClaims(Path(temporary) / "claims")
            plan = self.plan()
            barrier = threading.Barrier(3)
            outcomes: list[str | None] = []

            def claim() -> None:
                barrier.wait()
                outcomes.append(
                    claims.claim(
                        plan,
                        expected_plan_digest=plan.plan_digest,
                        current_owner_binding="windows-sid:S-1-5-21-test-user",
                        now=NOW + timedelta(seconds=1),
                    )
                )

            threads = [threading.Thread(target=claim) for _ in range(2)]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join()

            self.assertCountEqual(outcomes, [None, "request_replayed"])
            claim_text = next((Path(temporary) / "claims").iterdir()).read_text("utf-8")
            self.assert_secret_absent(claim_text)

    def test_file_claim_is_archive_bound_and_never_writes_outside_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            archive = parent / "archive"
            outside = parent / "outside"
            archive.mkdir()
            outside.mkdir()
            claims = FileOneTimeRequestClaims(
                outside,
                archive_root=archive,
                expected_relative_directory=Path("profiles") / "local" / "claims",
            )

            result = claims.claim(
                self.plan(),
                expected_plan_digest=self.plan().plan_digest,
                current_owner_binding="windows-sid:S-1-5-21-test-user",
                now=NOW + timedelta(seconds=1),
            )

            self.assertEqual(result, "request_claim_failed")
            self.assertEqual(list(outside.iterdir()), [])
            self.assertNotIn(str(parent), repr(claims))
            self.assertNotIn(str(parent), result)

    def test_file_claim_rejects_parent_reparse_flag_before_marker_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary)
            claims_path = archive / "profiles" / "local" / "claims"
            claims = FileOneTimeRequestClaims(
                claims_path,
                archive_root=archive,
                expected_relative_directory=Path("profiles") / "local" / "claims",
            )
            real_lstat = secure_intake_module.os.lstat

            def reparse_lstat(path):
                information = real_lstat(path)
                if os.path.normcase(str(Path(path))) == os.path.normcase(
                    str(archive / "profiles")
                ):
                    return SimpleNamespace(
                        st_mode=information.st_mode,
                        st_dev=information.st_dev,
                        st_ino=information.st_ino,
                        st_nlink=information.st_nlink,
                        st_size=information.st_size,
                        st_file_attributes=(
                            int(getattr(information, "st_file_attributes", 0))
                            | 0x00000400
                        ),
                    )
                return information

            with patch.object(secure_intake_module.os, "lstat", reparse_lstat):
                result = claims.claim(
                    self.plan(),
                    expected_plan_digest=self.plan().plan_digest,
                    current_owner_binding="windows-sid:S-1-5-21-test-user",
                    now=NOW + timedelta(seconds=1),
                )

            self.assertEqual(result, "request_claim_failed")
            self.assertEqual(list(archive.rglob("*.claim.json")), [])

    def test_file_claim_directory_swap_fails_before_any_outside_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "archive"
            outside = Path(temporary) / "outside"
            moved = Path(temporary) / "moved-claims"
            archive.mkdir()
            outside.mkdir()
            claims_path = archive / "profiles" / "local" / "claims"

            def swap_directory(stage: str) -> None:
                if stage != "directory_bound":
                    return
                claims_path.rename(moved)
                claims_path.symlink_to(outside, target_is_directory=True)

            claims = FileOneTimeRequestClaims(
                claims_path,
                archive_root=archive,
                expected_relative_directory=Path("profiles") / "local" / "claims",
                _failpoint=swap_directory,
            )
            plan = self.plan()
            result = claims.claim(
                plan,
                expected_plan_digest=plan.plan_digest,
                current_owner_binding="windows-sid:S-1-5-21-test-user",
                now=NOW + timedelta(seconds=1),
            )

            self.assertEqual(result, "request_claim_failed")
            self.assertEqual(list(outside.iterdir()), [])
            if moved.exists():
                self.assertEqual(list(moved.iterdir()), [])

    def test_file_claim_write_all_handles_short_writes_and_rejects_zero_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claims_path = root / "claims"
            claims = FileOneTimeRequestClaims(
                claims_path,
                archive_root=root,
                expected_relative_directory="claims",
            )
            plan = self.plan()
            real_write = secure_intake_module.os.write

            def short_write(descriptor, value):
                return real_write(descriptor, bytes(value[:7]))

            with patch.object(secure_intake_module.os, "write", short_write):
                result = claims.claim(
                    plan,
                    expected_plan_digest=plan.plan_digest,
                    current_owner_binding="windows-sid:S-1-5-21-test-user",
                    now=NOW + timedelta(seconds=1),
                )
            self.assertIsNone(result)
            self.assertEqual(
                FileOneTimeRequestClaims(
                    claims_path,
                    archive_root=root,
                    expected_relative_directory="claims",
                ).claim(
                    plan,
                    expected_plan_digest=plan.plan_digest,
                    current_owner_binding="windows-sid:S-1-5-21-test-user",
                    now=NOW + timedelta(seconds=2),
                ),
                "request_replayed",
            )
            self.assertEqual(list(claims_path.glob("*.claim.tmp")), [])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claims_path = root / "claims"
            claims = FileOneTimeRequestClaims(
                claims_path,
                archive_root=root,
                expected_relative_directory="claims",
            )
            plan = self.plan()
            with patch.object(secure_intake_module.os, "write", lambda *_args: 0):
                result = claims.claim(
                    plan,
                    expected_plan_digest=plan.plan_digest,
                    current_owner_binding="windows-sid:S-1-5-21-test-user",
                    now=NOW + timedelta(seconds=1),
                )
            self.assertEqual(result, "request_claim_failed")
            self.assertEqual(list(claims_path.iterdir()), [])

    def test_file_claim_fsync_and_close_fail_before_authority_publication(self) -> None:
        for failure_kind in ("fsync", "close"):
            with self.subTest(failure_kind=failure_kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                claims_path = root / "claims"
                claims = FileOneTimeRequestClaims(
                    claims_path,
                    archive_root=root,
                    expected_relative_directory="claims",
                )
                plan = self.plan()
                if failure_kind == "fsync":
                    selected_patch = patch.object(
                        secure_intake_module.os,
                        "fsync",
                        side_effect=OSError(SECRET_TEXT),
                    )
                else:
                    real_close = secure_intake_module.os.close
                    failed = False

                    def fail_first_regular_close(descriptor):
                        nonlocal failed
                        if not failed:
                            try:
                                information = os.fstat(descriptor)
                            except OSError:
                                return real_close(descriptor)
                            if stat_module.S_ISREG(information.st_mode):
                                failed = True
                                real_close(descriptor)
                                raise OSError(SECRET_TEXT)
                        return real_close(descriptor)

                    selected_patch = patch.object(
                        secure_intake_module.os,
                        "close",
                        fail_first_regular_close,
                    )
                with selected_patch:
                    result = claims.claim(
                        plan,
                        expected_plan_digest=plan.plan_digest,
                        current_owner_binding="windows-sid:S-1-5-21-test-user",
                        now=NOW + timedelta(seconds=1),
                    )
                self.assertEqual(result, "request_claim_failed")
                self.assertEqual(list(claims_path.glob("*.claim.json")), [])
                self.assertEqual(list(claims_path.glob("*.claim.tmp")), [])
                self.assertNotIn(SECRET_TEXT, result)

    def test_file_claim_detects_final_file_preemption_and_temp_file_swap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claims_path = root / "claims"
            claims_path.mkdir()
            plan = self.plan()
            final_path = claims_path / f"{plan.request_id}.claim.json"
            final_path.write_text("{}\n", encoding="utf-8")
            claims = FileOneTimeRequestClaims(
                claims_path,
                archive_root=root,
                expected_relative_directory="claims",
            )
            self.assertEqual(
                claims.claim(
                    plan,
                    expected_plan_digest=plan.plan_digest,
                    current_owner_binding="windows-sid:S-1-5-21-test-user",
                    now=NOW + timedelta(seconds=1),
                ),
                "request_claim_failed",
            )
            self.assertEqual(final_path.read_text("utf-8"), "{}\n")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claims_path = root / "claims"
            claims_path.mkdir()
            plan = self.plan()
            token = "a" * 32
            preempted_temp = (
                claims_path / f".{plan.request_id}.{token}.claim.tmp"
            )
            preempted_temp.write_bytes(b"attacker-owned")
            claims = FileOneTimeRequestClaims(
                claims_path,
                archive_root=root,
                expected_relative_directory="claims",
            )
            with patch.object(secure_intake_module.secrets, "token_hex", return_value=token):
                result = claims.claim(
                    plan,
                    expected_plan_digest=plan.plan_digest,
                    current_owner_binding="windows-sid:S-1-5-21-test-user",
                    now=NOW + timedelta(seconds=1),
                )
            self.assertEqual(result, "request_claim_failed")
            self.assertEqual(preempted_temp.read_bytes(), b"attacker-owned")
            self.assertEqual(list(claims_path.glob("*.claim.json")), [])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claims_path = root / "claims"

            def swap_temp(stage: str) -> None:
                if stage != "temp_closed":
                    return
                temporary_path = next(claims_path.glob("*.claim.tmp"))
                temporary_path.unlink()
                temporary_path.write_bytes(b"attacker-owned")

            claims = FileOneTimeRequestClaims(
                claims_path,
                archive_root=root,
                expected_relative_directory="claims",
                _failpoint=swap_temp,
            )
            plan = self.plan()
            result = claims.claim(
                plan,
                expected_plan_digest=plan.plan_digest,
                current_owner_binding="windows-sid:S-1-5-21-test-user",
                now=NOW + timedelta(seconds=1),
            )
            self.assertEqual(result, "request_claim_failed")
            self.assertEqual(list(claims_path.glob("*.claim.json")), [])

    def test_windows_store_uses_only_one_exact_generic_target(self) -> None:
        class FakeNative:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []
                self.received: list[bytes] = []

            def write_generic(self, target_name: str, secret: memoryview) -> None:
                self.calls.append(("write_generic", target_name))
                self.received.append(bytes(secret))

            def generic_exists(self, target_name: str) -> bool:
                self.calls.append(("generic_exists", target_name))
                return True

            def delete_generic(self, target_name: str) -> None:
                self.calls.append(("delete_generic", target_name))

        native = FakeNative()
        adapter = WindowsCredentialManagerExactStore(native=native)
        secret = bytearray(SECRET_BYTES)
        adapter.put_exact(BACKEND_ID, memoryview(secret))
        self.assertTrue(adapter.probe_exact(BACKEND_ID))
        adapter.delete_exact(BACKEND_ID)

        target = f"WOM/credential-intake/{BACKEND_ID}"
        self.assertEqual(
            native.calls,
            [
                ("write_generic", target),
                ("generic_exists", target),
                ("delete_generic", target),
            ],
        )
        self.assertFalse(hasattr(adapter, "enumerate"))
        self.assertFalse(hasattr(adapter, "search"))
        self.assertFalse(hasattr(adapter, "read_secret"))

    def test_masked_dialog_has_no_stdin_fallback_and_redacts_native_error(self) -> None:
        dialog = WindowsMaskedDialog(native_prompt=lambda request_id: bytearray(SECRET_BYTES))
        value = dialog.request_secret(request_id=REQUEST_ID)
        self.assertEqual(value, bytearray(SECRET_BYTES))

        def explode(request_id: str):
            raise RuntimeError(SECRET_TEXT)

        dialog = WindowsMaskedDialog(native_prompt=explode)
        with self.assertRaises(RuntimeError) as error:
            dialog.request_secret(request_id=REQUEST_ID)
        self.assertEqual(str(error.exception), "secure_intake_input_unavailable")
        self.assertNotIn(SECRET_TEXT, repr(dialog))

    def test_parent_launcher_exception_is_post_start_unknown_and_transport_is_secret_free(
        self,
    ) -> None:
        plan = self.plan()

        class CapturingSpawner:
            def __init__(self) -> None:
                self.invocation = None

            def run_worker(self, invocation):
                self.invocation = invocation
                raise RuntimeError(f"child failed with {SECRET_TEXT}")

        spawner = CapturingSpawner()
        launcher = SecureIntakeProcessLauncher(spawner=spawner)
        result = launcher.launch(plan, expected_plan_digest=plan.plan_digest)

        self.assert_unknown_worker_state(result)
        payload = spawner.invocation.to_public_dict()
        self.assertEqual(payload["stdin_mode"], "disabled")
        self.assertEqual(payload["secret_transport"], "human_only_worker_ui")
        self.assertTrue(payload["plan"]["reviewed_anchor_present"])
        self.assertNotIn("reviewed_anchor_uuid", payload["plan"])
        self.assertNotIn(ANCHOR, json.dumps(payload, ensure_ascii=False))
        self.assertNotIn("argv", payload)
        self.assertNotIn("env", payload)
        self.assert_secret_absent(payload)

    def test_parent_launcher_projects_exact_success_into_a_new_public_dict(self) -> None:
        plan = self.plan()
        worker, _, _, _, _ = self.worker(
            store=FakeStore(backend_kind="windows_credential_manager_generic")
        )
        child_result = self.execute(worker, plan)

        class SuccessfulSpawner:
            def run_worker(self, invocation):
                self.invocation = invocation
                return child_result

        launcher = SecureIntakeProcessLauncher(spawner=SuccessfulSpawner())
        projected = launcher.launch(plan, expected_plan_digest=plan.plan_digest)

        self.assertEqual(projected, child_result)
        self.assertIsNot(projected, child_result)
        self.assertIsNot(
            projected["verified_capabilities"],
            child_result["verified_capabilities"],
        )
        child_result["account_label"] = SECRET_TEXT
        child_result["verified_capabilities"].append("covert_value")
        self.assertEqual(projected["account_label"], "personal")
        self.assertNotIn("covert_value", projected["verified_capabilities"])
        self.assert_secret_absent(projected)

    def test_parent_launcher_projects_only_exact_fixed_failures(self) -> None:
        plan = self.plan()
        worker, _, _, _, _ = self.worker(
            ui=FakeUI(value_factory=lambda: None)
        )
        child_result = self.execute(worker, plan)

        class FailedSpawner:
            def run_worker(self, invocation):
                return child_result

        projected = SecureIntakeProcessLauncher(spawner=FailedSpawner()).launch(
            plan,
            expected_plan_digest=plan.plan_digest,
        )
        self.assertEqual(projected, child_result)
        self.assertIsNot(projected, child_result)
        self.assert_failed_without_id(projected, "credential_input_cancelled_or_empty")

        contaminated = dict(child_result)
        contaminated["error"] = SECRET_TEXT

        class ContaminatedFailureSpawner:
            def run_worker(self, invocation):
                return contaminated

        blocked = SecureIntakeProcessLauncher(
            spawner=ContaminatedFailureSpawner()
        ).launch(plan, expected_plan_digest=plan.plan_digest)
        self.assert_unknown_worker_state(blocked)

        provider_failure = secure_intake_module._fixed_failure(
            "provider_auth_rejected",
            rollback_status="deleted",
        )

        class ProviderFailureSpawner:
            def run_worker(self, invocation):
                return provider_failure

        projected_provider = SecureIntakeProcessLauncher(
            spawner=ProviderFailureSpawner()
        ).launch(plan, expected_plan_digest=plan.plan_digest)
        self.assertEqual(projected_provider, provider_failure)

        forged_provider_failure = secure_intake_module._fixed_failure(
            "provider_auth_rejected",
            rollback_status="not_required",
        )

        class ForgedProviderFailureSpawner:
            def run_worker(self, invocation):
                return forged_provider_failure

        blocked_provider = SecureIntakeProcessLauncher(
            spawner=ForgedProviderFailureSpawner()
        ).launch(plan, expected_plan_digest=plan.plan_digest)
        self.assert_unknown_worker_state(blocked_provider)

    def test_core_projection_binds_legacy_failure_stage_to_rollback_state(self) -> None:
        pre_store = {
            "human_cancelled",
            "secret_input_unavailable",
            "request_expired",
            "request_replayed",
            "request_user_mismatch",
            "request_claim_failed",
            "plan_digest_mismatch",
        }
        rollback_required = {
            "store_write_failed",
            "store_presence_not_verified",
            "provider_identity_unverified",
            "workspace_anchor_mismatch",
            "receipt_commit_failed",
        }
        for reason in sorted(pre_store):
            with self.subTest(reason=reason, rollback="not_required"):
                valid = secure_intake_module._fixed_failure(reason)
                self.assertEqual(
                    secure_intake_module._project_worker_failure(valid),
                    valid,
                )
                forged = secure_intake_module._fixed_failure(
                    reason,
                    rollback_status="deleted",
                )
                self.assertIsNone(
                    secure_intake_module._project_worker_failure(forged)
                )
        for reason in sorted(rollback_required):
            with self.subTest(reason=reason, rollback="deleted"):
                valid = secure_intake_module._fixed_failure(
                    reason,
                    rollback_status="deleted",
                )
                self.assertEqual(
                    secure_intake_module._project_worker_failure(valid),
                    valid,
                )
                forged = secure_intake_module._fixed_failure(reason)
                self.assertIsNone(
                    secure_intake_module._project_worker_failure(forged)
                )

    def test_parent_launcher_blocks_child_success_contamination_and_covert_fields(
        self,
    ) -> None:
        plan = self.plan()
        worker, _, _, _, _ = self.worker(
            store=FakeStore(backend_kind="windows_credential_manager_generic")
        )
        valid = self.execute(worker, plan)
        contaminations = {
            "extra_secret_field": {**valid, "child_debug": SECRET_TEXT},
            "secret_shaped_label": {**valid, "account_label": f"token={SECRET_TEXT}"},
            "provider_mismatch": {**valid, "provider": "other_provider"},
            "backend_not_allowlisted": {
                **valid,
                "encrypted_backend_kind": "child_selected_backend",
            },
            "backend_id_invalid": {
                **valid,
                "encrypted_backend_id": "backend_ntn_abcdefghijklmnopqrstuvwxyz0123456789",
            },
            "credential_id_secret_shaped": {
                **valid,
                "credential_id": "cred_ntn_abcdefghijklmnopqrstuvwxyz0123456789",
            },
            "capability_not_allowlisted": {
                **valid,
                "verified_capabilities": [
                    *valid["verified_capabilities"],
                    "covert_value",
                ],
            },
            "capability_count_unbounded": {
                **valid,
                "verified_capabilities": ["read_content"] * 17,
            },
            "receipt_ref_not_canonical": {
                **valid,
                "receipt_ref": f"private/{CREDENTIAL_ID}/{SECRET_TEXT}",
            },
            "privacy_flag_changed": {**valid, "secret_value_present": True},
            "timestamp_not_canonical": {
                **valid,
                "last_verified_at": "2026-08-10T03:00:02+00:00",
            },
        }

        for name, child_result in contaminations.items():
            with self.subTest(name=name):
                class ContaminatedSpawner:
                    def run_worker(self, invocation):
                        return child_result

                blocked = SecureIntakeProcessLauncher(
                    spawner=ContaminatedSpawner()
                ).launch(plan, expected_plan_digest=plan.plan_digest)
                self.assert_unknown_worker_state(blocked)

    def test_parent_launcher_requires_private_pre_start_marker_for_exact_launch_failure(
        self,
    ) -> None:
        plan = self.plan()

        class ProvenPreStartSpawner:
            def run_worker(self, invocation):
                return secure_intake_module._SecureIntakeWorkerRunOutcome(
                    worker_started=False
                )

        pre_start = SecureIntakeProcessLauncher(
            spawner=ProvenPreStartSpawner()
        ).launch(plan, expected_plan_digest=plan.plan_digest)
        self.assert_failed_without_id(pre_start, "worker_launch_failed")

        class ProvenPostStartSpawner:
            def run_worker(self, invocation):
                return secure_intake_module._SecureIntakeWorkerRunOutcome(
                    worker_started=True,
                    result=None,
                )

        post_start = SecureIntakeProcessLauncher(
            spawner=ProvenPostStartSpawner()
        ).launch(plan, expected_plan_digest=plan.plan_digest)
        self.assert_unknown_worker_state(post_start)

    def test_atomic_receipt_committer_never_overwrites_existing_receipt(self) -> None:
        worker, _, _, _, _ = self.worker()
        with tempfile.TemporaryDirectory() as temporary:
            committer = AtomicJsonReceiptCommitter(temporary)
            worker.receipt_committer = committer
            result = self.execute(worker)
            receipt_path = Path(temporary) / str(result["receipt_ref"])
            original = receipt_path.read_text("utf-8")
            self.assertIn(CREDENTIAL_ID, original)
            self.assert_secret_absent(original)

            second_worker, _, second_store, _, _ = self.worker(
                committer=committer,
            )
            second = self.execute(second_worker)
            self.assert_failed_without_id(second, "receipt_commit_failed")
            self.assertEqual(second_store.calls[-1], ("delete_exact", BACKEND_ID))
            self.assertEqual(receipt_path.read_text("utf-8"), original)

    def test_duplicate_lifecycle_requires_human_default_and_never_revokes(self) -> None:
        workspace = "sha256:" + "a" * 64
        receipts = [
            {
                "credential_id": "cred_1111111111111111",
                "provider": "notion",
                "verified_workspace_fingerprint": workspace,
                "fingerprint_digest": "hmac-sha256:" + "1" * 64,
            },
            {
                "credential_id": "cred_2222222222222222",
                "provider": "notion",
                "verified_workspace_fingerprint": workspace,
                "fingerprint_digest": "hmac-sha256:" + "2" * 64,
            },
            {
                "credential_id": "cred_3333333333333333",
                "provider": "notion",
                "verified_workspace_fingerprint": workspace,
                "fingerprint_digest": "hmac-sha256:" + "3" * 64,
            },
        ]

        preview = apply_duplicate_lifecycle_decision(receipts)
        self.assertEqual(preview["status"], "human_decision_required")
        self.assertFalse(preview["default_changed"])
        self.assertTrue(all(not row["is_default"] for row in preview["credentials"]))
        self.assertFalse(preview["delete_performed"])
        self.assertFalse(preview["revoke_performed"])

        decided = apply_duplicate_lifecycle_decision(
            receipts,
            selected_default_credential_id="cred_2222222222222222",
            revocation_pending_credential_ids=("cred_3333333333333333",),
            human_approved=True,
        )
        by_id = {row["credential_id"]: row for row in decided["credentials"]}
        self.assertTrue(by_id["cred_2222222222222222"]["is_default"])
        self.assertEqual(by_id["cred_1111111111111111"]["lifecycle_status"], "legacy_valid")
        self.assertEqual(
            by_id["cred_3333333333333333"]["lifecycle_status"],
            "revocation_pending",
        )
        self.assertFalse(decided["delete_performed"])
        self.assertFalse(decided["revoke_performed"])
        self.assert_secret_absent(decided)

    def test_same_secret_fingerprint_still_allows_explicit_human_default(self) -> None:
        workspace = "sha256:" + "a" * 64
        fingerprint = "hmac-sha256:" + "1" * 64
        receipts = [
            {
                "credential_id": "cred_1111111111111111",
                "provider": "notion",
                "verified_workspace_fingerprint": workspace,
                "fingerprint_digest": fingerprint,
            },
            {
                "credential_id": "cred_2222222222222222",
                "provider": "notion",
                "verified_workspace_fingerprint": workspace,
                "fingerprint_digest": fingerprint,
            },
        ]

        decided = apply_duplicate_lifecycle_decision(
            receipts,
            selected_default_credential_id="cred_1111111111111111",
            human_approved=True,
        )

        by_id = {row["credential_id"]: row for row in decided["credentials"]}
        self.assertTrue(by_id["cred_1111111111111111"]["is_default"])
        self.assertEqual(
            by_id["cred_2222222222222222"]["lifecycle_status"],
            "legacy_valid",
        )
        self.assertFalse(decided["delete_performed"])
        self.assertFalse(decided["revoke_performed"])


if __name__ == "__main__":
    unittest.main()
