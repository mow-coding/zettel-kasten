from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

from wom_kit.credential_secure_intake import (
    _AtomicJsonReceiptCommitter as AtomicJsonReceiptCommitter,
    NOTION_PAT_SCOPE_FINGERPRINT_DOMAIN,
    NOTION_PAT_WORKSPACE_IDENTITY_BASIS,
    _WindowsCredentialManagerExactStore as WindowsCredentialManagerExactStore,
)
from wom_kit.credential_secure_intake_windows import (
    windows_credential_target,
    windows_credential_target_prefix,
)
from wom_kit.credential_capability import (
    _CredentialCapability as CredentialCapability,
    CredentialCapabilityScope,
)
from wom_kit.credential_secure_registry import (
    CAPABILITY_CLAIMS_RELATIVE,
    _capability_claim_mac,
    _receipt_mac,
    RECEIPT_AUTHENTICATION_SCHEMA,
    _ReceiptBackedNotionCredentialBroker as ReceiptBackedNotionCredentialBroker,
    SecureCredentialRegistryError,
    _StableArchiveFingerprintKeyProvider as StableArchiveFingerprintKeyProvider,
    _claim_credential_capability_use as claim_credential_capability_use,
    _create_archive_atomic_json_receipt_committer as create_archive_atomic_json_receipt_committer,
    list_secure_credentials,
    lookup_secure_credential,
    _evolve_legacy_authenticated_workspace_scope as evolve_legacy_authenticated_workspace_scope,
    _persist_duplicate_lifecycle_decision as persist_duplicate_lifecycle_decision,
)
from wom_kit.notion_http_adapter import _NotionBearerSecret as NotionBearerSecret
from wom_kit.notion_page_recovery import ScopeBinding


AUTH_KEY = b"registry-authentication-key-32!!"
FINGERPRINT_KEY = b"F" * 32
WORKSPACE_A = "sha256:" + ("1" * 64)
WORKSPACE_B = "sha256:" + ("2" * 64)
SECRET = b"ntn_test_value_that_must_never_be_public"
CAPABILITY_NOW = datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc)
CAPABILITY_REQUEST_SHA256 = "sha256:" + ("6" * 64)
CAPABILITY_PLAN_SHA256 = "sha256:" + ("7" * 64)


class FakeExactWindowsNative:
    def __init__(self) -> None:
        self.values: dict[str, bytearray] = {}
        self.read_targets: list[str] = []
        self.write_targets: list[str] = []
        self.returned_buffers: list[bytearray] = []

    def write_generic(self, target_name: str, secret: memoryview) -> None:
        self.write_targets.append(target_name)
        self.values[target_name] = bytearray(secret)

    def generic_exists(self, target_name: str) -> bool:
        return target_name in self.values

    def read_generic_secret_exact(self, target_name: str) -> bytearray:
        self.read_targets.append(target_name)
        if target_name not in self.values:
            raise KeyError("not found")
        value = bytearray(self.values[target_name])
        self.returned_buffers.append(value)
        return value


def make_archive(base: Path) -> Path:
    root = base / "archive"
    root.mkdir()
    (root / ".gitignore").write_text("profiles/local/\n", encoding="utf-8")
    (root / "archive.yml").write_text("archive_id: archive:test\n", encoding="utf-8")
    return root


def make_receipt(
    suffix: str = "a",
    *,
    workspace: str = WORKSPACE_A,
    fingerprint_digit: str = "3",
    legacy: bool = False,
) -> dict[str, object]:
    repeated = suffix * 16
    receipt = {
        "schema_version": (
            "wom-credential-secure-intake-receipt/v0.1"
            if legacy
            else "wom-credential-secure-intake-receipt/v0.2"
        ),
        "credential_id": "cred_" + repeated,
        "persisted": True,
        "provider": "notion",
        "account_label": "organization account",
        "workspace_label": "reviewed workspace",
        "purpose": "source_recovery",
        "verified_capabilities": [
            "read_content",
            "retrieve_page",
            "retrieve_page_as_markdown",
        ],
        "encrypted_backend_kind": "windows_credential_manager_generic",
        "encrypted_backend_id": "backend_" + repeated,
        "fingerprint_digest": "hmac-sha256:" + (fingerprint_digit * 64),
        "verified_account_fingerprint": "sha256:" + ("4" * 64),
        "verified_workspace_fingerprint": workspace,
        "adopted_at": "2026-08-10T01:02:03Z",
        "last_verified_at": "2026-08-10T01:02:03Z",
        "rotation_status": "current",
        "lifecycle_status": "active",
        "is_default": False,
        "request_id": "intake_" + repeated,
        "plan_digest": "5" * 64,
    }
    if not legacy:
        receipt["workspace_identity_basis"] = "notion_bot_workspace_id_v1"
    return receipt


def scope_from_public(row: dict[str, object]) -> ScopeBinding:
    binding = row["scope_binding"]
    assert isinstance(binding, dict)
    return ScopeBinding(**binding)


def commit_released_v01_receipt(
    root: Path, receipt: dict[str, object], *, key: bytes
) -> str:
    """Materialize exact release-era authenticated bytes without runtime writer access."""

    authenticated = dict(receipt)
    authenticated["receipt_authentication"] = {
        "schema_version": RECEIPT_AUTHENTICATION_SCHEMA,
        "algorithm": "hmac-sha256",
        "mac": _receipt_mac(receipt, key),
    }
    return AtomicJsonReceiptCommitter(
        root / "profiles" / "local" / "credential-intake" / "receipts"
    ).commit_atomic(authenticated)


class SecureCredentialRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = make_archive(Path(self.temporary.name))

    def _committer(self):
        return create_archive_atomic_json_receipt_committer(
            self.root,
            expected_archive_id="archive:test",
            receipt_authentication_key=AUTH_KEY,
        )

    @staticmethod
    def _capability_scope(scope: ScopeBinding) -> CredentialCapabilityScope:
        return CredentialCapabilityScope(
            credential_id=scope.credential_id,
            workspace_fingerprint=scope.workspace_fingerprint,
            scope_receipt_sha256=scope.scope_receipt_sha256,
            revision=scope.revision,
        )

    def _claim_for_scopes(
        self,
        *scopes: ScopeBinding,
        now: datetime = CAPABILITY_NOW,
        issued_at: datetime = CAPABILITY_NOW,
        ttl_seconds: int = 900,
        max_provider_requests: int = 32,
        capability: CredentialCapability | None = None,
    ):
        selected = capability or CredentialCapability.issue(
            request_sha256=CAPABILITY_REQUEST_SHA256,
            plan_sha256=CAPABILITY_PLAN_SHA256,
            scopes=[self._capability_scope(scope) for scope in scopes],
            reviewed_by="reviewer-1",
            max_provider_requests=max_provider_requests,
            issued_at=issued_at,
            ttl_seconds=ttl_seconds,
        )
        return claim_credential_capability_use(
            self.root,
            selected,
            AUTH_KEY,
            clock=lambda: now,
        )

    def _broker(
        self,
        native: FakeExactWindowsNative,
        *scopes: ScopeBinding,
        secret_fingerprint_key: bytes | None = None,
        claimed_use=None,
    ) -> ReceiptBackedNotionCredentialBroker:
        return ReceiptBackedNotionCredentialBroker(
            self.root,
            native,
            AUTH_KEY,
            secret_fingerprint_key,
            claimed_use=(claimed_use or self._claim_for_scopes(*scopes)),
        )

    def _approve_lifecycle(
        self,
        *,
        provider: str,
        workspace_fingerprint: str,
        selected_default_credential_id: str,
        revocation_pending_credential_ids: tuple[str, ...] = (),
    ) -> dict[str, object]:
        plan = persist_duplicate_lifecycle_decision(
            self.root,
            provider=provider,
            workspace_fingerprint=workspace_fingerprint,
            selected_default_credential_id=selected_default_credential_id,
            revocation_pending_credential_ids=revocation_pending_credential_ids,
            human_approved=False,
            receipt_authentication_key=AUTH_KEY,
        )
        return persist_duplicate_lifecycle_decision(
            self.root,
            provider=provider,
            workspace_fingerprint=workspace_fingerprint,
            selected_default_credential_id=selected_default_credential_id,
            revocation_pending_credential_ids=revocation_pending_credential_ids,
            human_approved=True,
            receipt_authentication_key=AUTH_KEY,
            expected_plan_sha256=str(plan["plan_sha256"]),
            reviewed_by="reviewer-1",
        )

    def _commit_and_authorize(
        self,
        receipt: dict[str, object] | None = None,
        *,
        secret: bytes = SECRET,
    ) -> tuple[dict[str, object], FakeExactWindowsNative, ScopeBinding]:
        receipt = receipt or make_receipt()
        receipt["fingerprint_digest"] = "hmac-sha256:" + hmac.new(
            FINGERPRINT_KEY,
            secret,
            hashlib.sha256,
        ).hexdigest()
        self._committer().commit_atomic(receipt)
        self._approve_lifecycle(
            provider="notion",
            workspace_fingerprint=str(receipt["verified_workspace_fingerprint"]),
            selected_default_credential_id=str(receipt["credential_id"]),
        )
        public = lookup_secure_credential(
            self.root,
            str(receipt["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        native = FakeExactWindowsNative()
        target = windows_credential_target(
            "archive:test", str(receipt["encrypted_backend_id"])
        )
        native.values[target] = bytearray(secret)
        return public, native, scope_from_public(public)

    def _legacy_receipt_with_secret(
        self,
        *,
        lifecycle: bool,
    ) -> tuple[dict[str, object], FakeExactWindowsNative, str]:
        receipt = make_receipt(legacy=True)
        receipt["fingerprint_digest"] = "hmac-sha256:" + hmac.new(
            FINGERPRINT_KEY,
            SECRET,
            hashlib.sha256,
        ).hexdigest()
        commit_released_v01_receipt(self.root, receipt, key=AUTH_KEY)
        if lifecycle:
            self._approve_lifecycle(
                provider="notion",
                workspace_fingerprint=str(
                    receipt["verified_workspace_fingerprint"]
                ),
                selected_default_credential_id=str(receipt["credential_id"]),
            )
        native = FakeExactWindowsNative()
        target = windows_credential_target(
            "archive:test", str(receipt["encrypted_backend_id"])
        )
        native.values[target] = bytearray(SECRET)
        return receipt, native, target

    def test_legacy_scope_evolution_preserves_exact_secret_and_singleton_lifecycle(self) -> None:
        receipt, native, target = self._legacy_receipt_with_secret(lifecycle=True)
        old = lookup_secure_credential(
            self.root,
            str(receipt["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        old_scope = scope_from_public(old)
        evolved = evolve_legacy_authenticated_workspace_scope(
            self.root,
            str(receipt["credential_id"]),
            evolved_workspace_fingerprint=WORKSPACE_B,
            workspace_identity_basis="notion_bot_workspace_id_v1",
            verified_account_fingerprint=str(
                receipt["verified_account_fingerprint"]
            ),
            verified_capabilities=tuple(receipt["verified_capabilities"]),
            receipt_authentication_key=AUTH_KEY,
            secret_fingerprint_key=FINGERPRINT_KEY,
            native=native,
            evolved_at="2026-08-13T01:02:03Z",
        )
        self.assertTrue(evolved["ok"])
        self.assertTrue(evolved["lifecycle_migrated"])
        self.assertEqual(native.write_targets, [])
        self.assertEqual(native.values[target], bytearray(SECRET))
        current = lookup_secure_credential(
            self.root,
            str(receipt["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertEqual(current["verified_workspace_fingerprint"], WORKSPACE_B)
        self.assertEqual(
            current["workspace_identity_basis"], "notion_bot_workspace_id_v1"
        )
        self.assertTrue(current["workspace_scope_evolved"])
        self.assertTrue(current["broker_authoritative"])
        self.assertNotEqual(
            current["scope_binding"]["scope_receipt_sha256"],
            old_scope.scope_receipt_sha256,
        )
        current_scope = scope_from_public(current)
        broker = self._broker(
            native,
            current_scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
        )
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_scope_receipt_mismatch|credential_registry_scope_workspace_mismatch",
        ):
            broker.resolve(old_scope)
        bearer = broker.resolve(current_scope)
        bearer.close()

    def test_legacy_scope_evolution_is_idempotent_and_no_lifecycle_stays_non_authoritative(self) -> None:
        receipt, native, _target = self._legacy_receipt_with_secret(lifecycle=False)
        common = {
            "evolved_workspace_fingerprint": WORKSPACE_B,
            "workspace_identity_basis": "notion_bot_workspace_id_v1",
            "verified_account_fingerprint": str(
                receipt["verified_account_fingerprint"]
            ),
            "verified_capabilities": tuple(receipt["verified_capabilities"]),
            "receipt_authentication_key": AUTH_KEY,
            "secret_fingerprint_key": FINGERPRINT_KEY,
            "native": native,
            "evolved_at": "2026-08-13T01:02:03Z",
        }
        first = evolve_legacy_authenticated_workspace_scope(
            self.root, str(receipt["credential_id"]), **common
        )
        second = evolve_legacy_authenticated_workspace_scope(
            self.root, str(receipt["credential_id"]), **common
        )
        self.assertEqual(first["status"], "workspace_scope_evolved")
        self.assertEqual(second["status"], "workspace_scope_evolution_replayed")
        self.assertEqual(first["authority_sha256"], second["authority_sha256"])
        self.assertFalse(first["broker_authoritative"])
        listed = lookup_secure_credential(
            self.root,
            str(receipt["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertFalse(listed["broker_authoritative"])

    def test_legacy_scope_evolution_complex_lifecycle_blocks_before_publication(self) -> None:
        first = make_receipt("a", legacy=True)
        second = make_receipt("b", legacy=True, fingerprint_digit="6")
        for receipt, secret in ((first, SECRET), (second, b"other secret")):
            receipt["fingerprint_digest"] = "hmac-sha256:" + hmac.new(
                FINGERPRINT_KEY, secret, hashlib.sha256
            ).hexdigest()
            commit_released_v01_receipt(self.root, receipt, key=AUTH_KEY)
        self._approve_lifecycle(
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(first["credential_id"]),
        )
        native = FakeExactWindowsNative()
        native.values[
            windows_credential_target(
                "archive:test", str(first["encrypted_backend_id"])
            )
        ] = bytearray(SECRET)
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_evolution_lifecycle_review_required",
        ):
            evolve_legacy_authenticated_workspace_scope(
                self.root,
                str(first["credential_id"]),
                evolved_workspace_fingerprint=WORKSPACE_B,
                workspace_identity_basis="notion_bot_workspace_id_v1",
                verified_account_fingerprint=str(
                    first["verified_account_fingerprint"]
                ),
                verified_capabilities=tuple(first["verified_capabilities"]),
                receipt_authentication_key=AUTH_KEY,
                secret_fingerprint_key=FINGERPRINT_KEY,
                native=native,
                evolved_at="2026-08-13T01:02:03Z",
            )
        evolutions = (
            self.root / "profiles" / "local" / "credential-intake" / "evolutions"
        )
        self.assertFalse(evolutions.exists())

    def test_legacy_scope_evolution_crash_after_authority_retries_singleton_lifecycle(self) -> None:
        receipt, native, target = self._legacy_receipt_with_secret(lifecycle=True)
        old = lookup_secure_credential(
            self.root,
            str(receipt["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        common = {
            "evolved_workspace_fingerprint": WORKSPACE_B,
            "workspace_identity_basis": "notion_bot_workspace_id_v1",
            "verified_account_fingerprint": str(
                receipt["verified_account_fingerprint"]
            ),
            "verified_capabilities": tuple(receipt["verified_capabilities"]),
            "receipt_authentication_key": AUTH_KEY,
            "secret_fingerprint_key": FINGERPRINT_KEY,
            "native": native,
            "evolved_at": "2026-08-13T01:02:03Z",
        }

        def interrupt_after_evolution() -> None:
            raise RuntimeError("synthetic private interruption")

        with self.assertRaisesRegex(RuntimeError, "synthetic private interruption"):
            evolve_legacy_authenticated_workspace_scope(
                self.root,
                str(receipt["credential_id"]),
                after_evolution_commit=interrupt_after_evolution,
                **common,
            )
        interrupted = lookup_secure_credential(
            self.root,
            str(receipt["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertTrue(interrupted["workspace_scope_evolved"])
        self.assertTrue(interrupted["workspace_scope_transition_pending"])
        self.assertFalse(interrupted["broker_authoritative"])
        self.assertEqual(native.values[target], bytearray(SECRET))

        replay = evolve_legacy_authenticated_workspace_scope(
            self.root, str(receipt["credential_id"]), **common
        )
        self.assertEqual(replay["status"], "workspace_scope_evolution_replayed")
        self.assertTrue(replay["lifecycle_migrated"])
        current = lookup_secure_credential(
            self.root,
            str(receipt["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertFalse(current["workspace_scope_transition_pending"])
        self.assertTrue(current["broker_authoritative"])
        self.assertNotEqual(
            current["scope_binding"]["scope_receipt_sha256"],
            old["scope_binding"]["scope_receipt_sha256"],
        )
        self.assertEqual(native.write_targets, [])
        self.assertEqual(native.values[target], bytearray(SECRET))

    def test_legacy_scope_evolution_requires_present_exact_saved_secret(self) -> None:
        receipt, native, target = self._legacy_receipt_with_secret(lifecycle=False)
        native.values.pop(target)
        common = {
            "evolved_workspace_fingerprint": WORKSPACE_B,
            "workspace_identity_basis": "notion_bot_workspace_id_v1",
            "verified_account_fingerprint": str(
                receipt["verified_account_fingerprint"]
            ),
            "verified_capabilities": tuple(receipt["verified_capabilities"]),
            "receipt_authentication_key": AUTH_KEY,
            "secret_fingerprint_key": FINGERPRINT_KEY,
            "native": native,
            "evolved_at": "2026-08-13T01:02:03Z",
        }
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_store_missing",
        ):
            evolve_legacy_authenticated_workspace_scope(
                self.root, str(receipt["credential_id"]), **common
            )
        native.values[target] = bytearray(b"different saved secret")
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_secret_fingerprint_mismatch",
        ):
            evolve_legacy_authenticated_workspace_scope(
                self.root, str(receipt["credential_id"]), **common
            )
        self.assertFalse(
            (
                self.root
                / "profiles"
                / "local"
                / "credential-intake"
                / "evolutions"
            ).exists()
        )
        self.assertEqual(native.write_targets, [])

    def test_pat_evolution_scope_is_derived_from_authenticated_secret_fingerprint(self) -> None:
        receipt, native, _target = self._legacy_receipt_with_secret(lifecycle=False)
        expected = "sha256:" + hashlib.sha256(
            NOTION_PAT_SCOPE_FINGERPRINT_DOMAIN
            + str(receipt["fingerprint_digest"]).encode("ascii")
        ).hexdigest()
        common = {
            "workspace_identity_basis": NOTION_PAT_WORKSPACE_IDENTITY_BASIS,
            "verified_account_fingerprint": str(
                receipt["verified_account_fingerprint"]
            ),
            "verified_capabilities": tuple(receipt["verified_capabilities"]),
            "receipt_authentication_key": AUTH_KEY,
            "secret_fingerprint_key": FINGERPRINT_KEY,
            "native": native,
            "evolved_at": "2026-08-13T01:02:03Z",
        }
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_evolution_identity_mismatch",
        ):
            evolve_legacy_authenticated_workspace_scope(
                self.root,
                str(receipt["credential_id"]),
                evolved_workspace_fingerprint=WORKSPACE_B,
                **common,
            )
        evolved = evolve_legacy_authenticated_workspace_scope(
            self.root,
            str(receipt["credential_id"]),
            evolved_workspace_fingerprint=expected,
            **common,
        )
        self.assertTrue(evolved["ok"])
        self.assertEqual(evolved["verified_workspace_fingerprint"], expected)

    def test_legacy_scope_evolution_conflict_does_not_publish_duplicate(self) -> None:
        receipt, native, _target = self._legacy_receipt_with_secret(lifecycle=False)
        common = {
            "workspace_identity_basis": "notion_bot_workspace_id_v1",
            "verified_account_fingerprint": str(
                receipt["verified_account_fingerprint"]
            ),
            "verified_capabilities": tuple(receipt["verified_capabilities"]),
            "receipt_authentication_key": AUTH_KEY,
            "secret_fingerprint_key": FINGERPRINT_KEY,
            "native": native,
            "evolved_at": "2026-08-13T01:02:03Z",
        }
        evolve_legacy_authenticated_workspace_scope(
            self.root,
            str(receipt["credential_id"]),
            evolved_workspace_fingerprint=WORKSPACE_B,
            **common,
        )
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_evolution_conflict",
        ):
            evolve_legacy_authenticated_workspace_scope(
                self.root,
                str(receipt["credential_id"]),
                evolved_workspace_fingerprint="sha256:" + "9" * 64,
                **common,
            )
        files = list(
            (
                self.root
                / "profiles"
                / "local"
                / "credential-intake"
                / "evolutions"
            ).glob("*.workspace-scope-v1.json")
        )
        self.assertEqual(len(files), 1)

    def test_legacy_scope_evolution_never_collapses_another_authenticated_registration(self) -> None:
        receipt, native, _target = self._legacy_receipt_with_secret(lifecycle=False)
        other = make_receipt("b", workspace=WORKSPACE_B, fingerprint_digit="7")
        self._committer().commit_atomic(other)
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_evolution_lifecycle_review_required",
        ):
            evolve_legacy_authenticated_workspace_scope(
                self.root,
                str(receipt["credential_id"]),
                evolved_workspace_fingerprint=WORKSPACE_B,
                workspace_identity_basis="notion_bot_workspace_id_v1",
                verified_account_fingerprint=str(
                    receipt["verified_account_fingerprint"]
                ),
                verified_capabilities=tuple(receipt["verified_capabilities"]),
                receipt_authentication_key=AUTH_KEY,
                secret_fingerprint_key=FINGERPRINT_KEY,
                native=native,
                evolved_at="2026-08-13T01:02:03Z",
            )
        self.assertFalse(
            (
                self.root
                / "profiles"
                / "local"
                / "credential-intake"
                / "evolutions"
            ).exists()
        )

    def test_production_committer_writes_v02_only_but_released_v01_remains_readable(self) -> None:
        legacy = make_receipt(legacy=True)
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_legacy_receipt_write_forbidden",
        ):
            self._committer().commit_atomic(legacy)
        commit_released_v01_receipt(self.root, legacy, key=AUTH_KEY)
        row = lookup_secure_credential(
            self.root,
            str(legacy["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertEqual(row["receipt_authentication_status"], "valid")
        self.assertEqual(
            row["workspace_identity_basis"], "legacy_reviewed_anchor_v1"
        )

    def test_evolution_tamper_or_orphan_fails_closed(self) -> None:
        receipt, native, _target = self._legacy_receipt_with_secret(lifecycle=False)
        evolve_legacy_authenticated_workspace_scope(
            self.root,
            str(receipt["credential_id"]),
            evolved_workspace_fingerprint=WORKSPACE_B,
            workspace_identity_basis="notion_bot_workspace_id_v1",
            verified_account_fingerprint=str(
                receipt["verified_account_fingerprint"]
            ),
            verified_capabilities=tuple(receipt["verified_capabilities"]),
            receipt_authentication_key=AUTH_KEY,
            secret_fingerprint_key=FINGERPRINT_KEY,
            native=native,
            evolved_at="2026-08-13T01:02:03Z",
        )
        evolution_path = next(
            (
                self.root
                / "profiles"
                / "local"
                / "credential-intake"
                / "evolutions"
            ).glob("*.workspace-scope-v1.json")
        )
        original = evolution_path.read_bytes()
        document = json.loads(original.decode("utf-8"))
        document["evolved_workspace_fingerprint"] = "sha256:" + "8" * 64
        evolution_path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        tampered = list_secure_credentials(
            self.root, receipt_authentication_key=AUTH_KEY
        )["credentials"][0]
        self.assertEqual(tampered["receipt_authentication_status"], "invalid")
        self.assertFalse(tampered["broker_authoritative"])
        self.assertIsNone(tampered["scope_binding"])
        evolution_path.write_bytes(original)
        receipt_path = (
            self.root
            / "profiles"
            / "local"
            / "credential-intake"
            / "receipts"
            / f"{receipt['credential_id']}.json"
        )
        receipt_path.unlink()
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_evolution_orphaned",
        ):
            list_secure_credentials(
                self.root, receipt_authentication_key=AUTH_KEY
            )

    def test_evolution_directory_rejects_unknown_and_oversized_entries(self) -> None:
        evolutions = (
            self.root
            / "profiles"
            / "local"
            / "credential-intake"
            / "evolutions"
        )
        evolutions.mkdir(parents=True)
        unknown = evolutions / "unexpected.json"
        unknown.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_evolution_entry_invalid",
        ):
            list_secure_credentials(
                self.root, receipt_authentication_key=AUTH_KEY
            )
        unknown.unlink()
        oversized = evolutions / (
            "cred_aaaaaaaaaaaaaaaa.workspace-scope-v1.json"
        )
        oversized.write_bytes(b"{" + (b" " * (64 * 1024)))
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_local_document_size_invalid",
        ):
            list_secure_credentials(
                self.root, receipt_authentication_key=AUTH_KEY
            )

    def test_concurrent_identical_evolution_is_one_append_only_authority(self) -> None:
        receipt, native, _target = self._legacy_receipt_with_secret(lifecycle=False)
        common = {
            "evolved_workspace_fingerprint": WORKSPACE_B,
            "workspace_identity_basis": "notion_bot_workspace_id_v1",
            "verified_account_fingerprint": str(
                receipt["verified_account_fingerprint"]
            ),
            "verified_capabilities": tuple(receipt["verified_capabilities"]),
            "receipt_authentication_key": AUTH_KEY,
            "secret_fingerprint_key": FINGERPRINT_KEY,
            "native": native,
            "evolved_at": "2026-08-13T01:02:03Z",
        }
        barrier = threading.Barrier(3)
        results: list[dict[str, object]] = []
        errors: list[BaseException] = []

        def run() -> None:
            try:
                barrier.wait()
                results.append(
                    evolve_legacy_authenticated_workspace_scope(
                        self.root, str(receipt["credential_id"]), **common
                    )
                )
            except BaseException as error:  # pragma: no cover - asserted below
                errors.append(error)

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(
            {result["status"] for result in results},
            {
                "workspace_scope_evolved",
                "workspace_scope_evolution_replayed",
            },
        )
        self.assertEqual(
            len(
                list(
                    (
                        self.root
                        / "profiles"
                        / "local"
                        / "credential-intake"
                        / "evolutions"
                    ).glob("*.workspace-scope-v1.json")
                )
            ),
            1,
        )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_reparse_evolution_directory_is_rejected_when_supported(self) -> None:
        outside = Path(self.temporary.name) / "outside-evolutions"
        outside.mkdir()
        parent = self.root / "profiles" / "local" / "credential-intake"
        parent.mkdir(parents=True)
        link = parent / "evolutions"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation not permitted")
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_evolution_directory_unsafe|credential_registry_path_reparse_forbidden",
        ):
            list_secure_credentials(
                self.root, receipt_authentication_key=AUTH_KEY
            )

    def test_authenticated_commit_is_rediscoverable_without_private_fields(self) -> None:
        receipt = make_receipt()
        reference = self._committer().commit_atomic(receipt)
        self.assertEqual(reference, str(receipt["credential_id"]) + ".json")

        report = list_secure_credentials(
            self.root,
            receipt_authentication_key=AUTH_KEY,
        )

        self.assertTrue(report["ok"])
        self.assertEqual(report["credential_count"], 1)
        row = report["credentials"][0]
        self.assertEqual(row["receipt_authentication_status"], "valid")
        self.assertEqual(row["verified_workspace_fingerprint"], WORKSPACE_A)
        self.assertEqual(row["credential_fingerprint"], receipt["fingerprint_digest"])
        self.assertEqual(
            row["verified_account_fingerprint"],
            receipt["verified_account_fingerprint"],
        )
        self.assertRegex(row["receipt_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertFalse(row["broker_authoritative"])
        self.assertFalse(row["scope_binding"]["persisted"])
        self.assertTrue(row["scope_binding"]["workspace_evidence_verified"])
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(str(receipt["encrypted_backend_id"]), serialized)
        self.assertNotIn(AUTH_KEY.decode("ascii"), serialized)
        self.assertNotIn("\"mac\"", serialized)
        self.assertNotIn("reviewed_anchor", serialized)

    def test_mutable_key_view_is_not_copied_to_immutable_bytes(self) -> None:
        mutable_key = bytearray(AUTH_KEY)
        committer = create_archive_atomic_json_receipt_committer(
            self.root,
            expected_archive_id="archive:test",
            receipt_authentication_key=memoryview(mutable_key),
        )
        mutable_key[:] = b"Z" * len(mutable_key)

        committer.commit_atomic(make_receipt())

        valid = list_secure_credentials(
            self.root,
            receipt_authentication_key=bytes(mutable_key),
        )["credentials"][0]
        stale = list_secure_credentials(
            self.root,
            receipt_authentication_key=AUTH_KEY,
        )["credentials"][0]
        self.assertEqual(valid["receipt_authentication_status"], "valid")
        self.assertEqual(stale["receipt_authentication_status"], "invalid")

    def test_discovery_without_key_marks_authentication_not_checked(self) -> None:
        self._committer().commit_atomic(make_receipt())
        row = list_secure_credentials(self.root)["credentials"][0]
        self.assertEqual(row["receipt_authentication_status"], "not_checked")
        self.assertIsNone(row["scope_binding"])
        self.assertFalse(row["broker_authoritative"])
        self.assertNotIn("provider", row)

    def test_empty_registry_discovery_is_filesystem_write_free(self) -> None:
        before = sorted(
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
        )

        report = list_secure_credentials(self.root)

        after = sorted(
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
        )
        self.assertEqual(report["credential_count"], 0)
        self.assertEqual(after, before)

    def test_authenticated_receipt_needs_human_default_before_executable_scope(self) -> None:
        receipt = make_receipt()
        self._committer().commit_atomic(receipt)
        row = lookup_secure_credential(
            self.root,
            str(receipt["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertEqual(row["receipt_authentication_status"], "valid")
        self.assertTrue(row["scope_binding"]["workspace_evidence_verified"])
        self.assertFalse(row["scope_binding"]["persisted"])
        native = FakeExactWindowsNative()
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_scope_binding_unverified",
        ):
            unapproved_scope = scope_from_public(row)
            self._broker(native, unapproved_scope).resolve(unapproved_scope)
        self.assertEqual(native.read_targets, [])

        self._approve_lifecycle(
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(receipt["credential_id"]),
        )
        approved = lookup_secure_credential(
            self.root,
            str(receipt["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertTrue(approved["scope_binding"]["persisted"])
        self.assertTrue(approved["scope_binding"]["workspace_evidence_verified"])

    def test_plain_atomic_receipt_is_not_broker_authoritative(self) -> None:
        receipt = make_receipt()
        receipt_root = self.root / "profiles" / "local" / "credential-intake" / "receipts"
        AtomicJsonReceiptCommitter(receipt_root).commit_atomic(receipt)
        row = lookup_secure_credential(
            self.root,
            str(receipt["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertEqual(row["receipt_authentication_status"], "missing")
        self.assertFalse(row["broker_authoritative"])
        native = FakeExactWindowsNative()
        raw = (receipt_root / (str(receipt["credential_id"]) + ".json")).read_bytes()
        scope = ScopeBinding(
            credential_id=str(receipt["credential_id"]),
            workspace_fingerprint=WORKSPACE_A,
            scope_receipt_sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
            revision="receipt-" + hashlib.sha256(raw).hexdigest(),
            persisted=True,
            workspace_evidence_verified=True,
        )
        broker = self._broker(native, scope)
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_receipt_authentication_invalid",
        ):
            broker.resolve(scope)
        self.assertEqual(native.read_targets, [])

    def test_same_command_receipt_lifecycle_and_exact_broker_read(self) -> None:
        public, native, scope = self._commit_and_authorize()
        self.assertTrue(public["broker_authoritative"])
        self.assertTrue(public["is_default"])
        self.assertEqual(public["lifecycle_status"], "active")
        self.assertEqual(public["rotation_status"], "current")

        credential = self._broker(
            native,
            scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
        ).resolve(scope)

        self.assertIsInstance(credential, NotionBearerSecret)
        self.assertEqual(str(credential), "[redacted]")
        self.assertEqual(
            native.read_targets,
            [windows_credential_target("archive:test", "backend_aaaaaaaaaaaaaaaa")],
        )
        self.assertEqual(native.returned_buffers[-1], bytearray(SECRET))
        credential.close()
        self.assertTrue(all(value == 0 for value in native.returned_buffers[-1]))
        credential.close()
        self.assertNotIn(SECRET.decode("ascii"), repr(credential))

    def test_cached_bearer_revalidates_without_another_secret_read(self) -> None:
        _public, native, scope = self._commit_and_authorize()
        credential = self._broker(
            native,
            scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
        ).resolve(scope)

        credential.revalidate_authority()
        credential.revalidate_authority()

        self.assertEqual(
            native.read_targets,
            [windows_credential_target("archive:test", "backend_aaaaaaaaaaaaaaaa")],
        )
        credential.close()
        self.assertTrue(all(value == 0 for value in native.returned_buffers[-1]))

    def test_cached_bearer_stops_after_authenticated_default_revision_drift(self) -> None:
        first = make_receipt("a")
        first["fingerprint_digest"] = "hmac-sha256:" + hmac.new(
            FINGERPRINT_KEY,
            SECRET,
            hashlib.sha256,
        ).hexdigest()
        second = make_receipt("b", fingerprint_digit="6")
        committer = self._committer()
        committer.commit_atomic(first)
        committer.commit_atomic(second)
        self._approve_lifecycle(
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(first["credential_id"]),
        )
        public = lookup_secure_credential(
            self.root,
            str(first["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        native = FakeExactWindowsNative()
        target = windows_credential_target(
            "archive:test", str(first["encrypted_backend_id"])
        )
        native.values[target] = bytearray(SECRET)
        current_scope = scope_from_public(public)
        credential = self._broker(
            native,
            current_scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
        ).resolve(current_scope)

        self._approve_lifecycle(
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(second["credential_id"]),
        )
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_scope_revision_mismatch",
        ):
            credential.revalidate_authority()

        self.assertEqual(native.read_targets, [target])
        credential.close()
        self.assertTrue(all(value == 0 for value in native.returned_buffers[-1]))

    def test_concurrent_lifecycle_drift_stops_every_remaining_authorized_attempt(self) -> None:
        first = make_receipt("a")
        first["fingerprint_digest"] = "hmac-sha256:" + hmac.new(
            FINGERPRINT_KEY,
            SECRET,
            hashlib.sha256,
        ).hexdigest()
        second = make_receipt("b", fingerprint_digit="6")
        committer = self._committer()
        committer.commit_atomic(first)
        committer.commit_atomic(second)
        self._approve_lifecycle(
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(first["credential_id"]),
        )
        public = lookup_secure_credential(
            self.root,
            str(first["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        native = FakeExactWindowsNative()
        target = windows_credential_target(
            "archive:test", str(first["encrypted_backend_id"])
        )
        native.values[target] = bytearray(SECRET)
        current_scope = scope_from_public(public)
        credential = self._broker(
            native,
            current_scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
        ).resolve(current_scope)
        first_attempt_finished = threading.Event()
        lifecycle_changed = threading.Event()
        provider_attempts: list[int] = []
        blocked_codes: list[str] = []

        def run_attempts() -> None:
            for attempt in range(3):
                if attempt == 1:
                    first_attempt_finished.set()
                    if not lifecycle_changed.wait(timeout=5):
                        blocked_codes.append("test_timeout")
                        return
                try:
                    credential.revalidate_authority()
                except SecureCredentialRegistryError as exc:
                    blocked_codes.append(exc.code)
                    return
                provider_attempts.append(attempt)

        worker = threading.Thread(target=run_attempts)
        worker.start()
        self.assertTrue(first_attempt_finished.wait(timeout=5))
        self._approve_lifecycle(
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(second["credential_id"]),
        )
        lifecycle_changed.set()
        worker.join(timeout=5)

        self.assertFalse(worker.is_alive())
        self.assertEqual(provider_attempts, [0])
        self.assertEqual(
            blocked_codes,
            ["credential_registry_scope_revision_mismatch"],
        )
        self.assertEqual(native.read_targets, [target])
        credential.close()
        self.assertTrue(all(value == 0 for value in native.returned_buffers[-1]))

    def test_cached_bearer_stops_on_receipt_set_drift_without_secret_reread(self) -> None:
        _public, native, scope = self._commit_and_authorize()
        credential = self._broker(
            native,
            scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
        ).resolve(scope)
        self._committer().commit_atomic(make_receipt("b", fingerprint_digit="6"))

        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_lifecycle_receipt_set_drift",
        ):
            credential.revalidate_authority()

        self.assertEqual(len(native.read_targets), 1)
        credential.close()
        self.assertTrue(all(value == 0 for value in native.returned_buffers[-1]))

    def test_exact_target_overwrite_fails_fingerprint_continuity_and_wipes_buffer(self) -> None:
        _public, native, scope = self._commit_and_authorize()
        target = next(iter(native.values))
        native.values[target] = bytearray(b"different-valid-looking-notion-token")
        broker = self._broker(
            native,
            scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
        )

        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_secret_fingerprint_mismatch",
        ):
            broker.resolve(scope)

        self.assertEqual(native.read_targets, [target])
        self.assertTrue(all(value == 0 for value in native.returned_buffers[-1]))

    def test_worker_store_and_later_broker_use_same_archive_scoped_target(self) -> None:
        receipt = make_receipt()
        receipt["fingerprint_digest"] = "hmac-sha256:" + hmac.new(
            FINGERPRINT_KEY,
            SECRET,
            hashlib.sha256,
        ).hexdigest()
        native = FakeExactWindowsNative()
        backend_id = str(receipt["encrypted_backend_id"])
        mutable_secret = bytearray(SECRET)
        store = WindowsCredentialManagerExactStore(
            native=native,
            target_prefix=windows_credential_target_prefix("archive:test"),
        )
        store.put_exact(backend_id, memoryview(mutable_secret))
        worker_target = native.write_targets[-1]
        self.assertEqual(worker_target, windows_credential_target("archive:test", backend_id))
        self.assertNotEqual(
            worker_target,
            windows_credential_target("archive:other", backend_id),
        )

        self._committer().commit_atomic(receipt)
        self._approve_lifecycle(
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(receipt["credential_id"]),
        )
        row = lookup_secure_credential(
            self.root,
            str(receipt["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        current_scope = scope_from_public(row)
        self._broker(
            native,
            current_scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
        ).resolve(current_scope)
        self.assertEqual(native.read_targets[-1], worker_target)

    def test_receipt_tampering_fails_authentication_before_native_read(self) -> None:
        receipt = make_receipt()
        public, native, original_scope = self._commit_and_authorize(receipt)
        del public
        path = (
            self.root
            / "profiles"
            / "local"
            / "credential-intake"
            / "receipts"
            / (str(receipt["credential_id"]) + ".json")
        )
        original = path.read_bytes()
        mutations = {
            "provider": lambda doc: doc.__setitem__("provider", "notion2"),
            "workspace": lambda doc: doc.__setitem__(
                "verified_workspace_fingerprint", WORKSPACE_B
            ),
            "backend": lambda doc: doc.__setitem__(
                "encrypted_backend_id", "backend_bbbbbbbbbbbbbbbb"
            ),
            "fingerprint": lambda doc: doc.__setitem__(
                "fingerprint_digest", "hmac-sha256:" + ("9" * 64)
            ),
            "mac": lambda doc: doc["receipt_authentication"].__setitem__("mac", "8" * 64),
        }
        broker = self._broker(native, original_scope)
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                document = json.loads(original.decode("utf-8"))
                mutate(document)
                changed = (
                    json.dumps(
                        document,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    + b"\n"
                )
                path.write_bytes(changed)
                workspace = str(document["verified_workspace_fingerprint"])
                tampered_scope = replace(
                    original_scope,
                    workspace_fingerprint=workspace,
                    scope_receipt_sha256="sha256:" + hashlib.sha256(changed).hexdigest(),
                )
                with self.assertRaisesRegex(
                    SecureCredentialRegistryError,
                    "credential_registry_receipt_authentication_invalid",
                ):
                    broker.resolve(tampered_scope)
                self.assertEqual(native.read_targets, [])
                path.write_bytes(original)

    def test_unauthenticated_tampered_label_is_never_projected(self) -> None:
        receipt = make_receipt()
        self._committer().commit_atomic(receipt)
        path = (
            self.root
            / "profiles"
            / "local"
            / "credential-intake"
            / "receipts"
            / (str(receipt["credential_id"]) + ".json")
        )
        document = json.loads(path.read_text(encoding="utf-8"))
        sentinel = "ntn_token_shaped_SENTINEL_MUST_NOT_ESCAPE"
        document["account_label"] = sentinel
        path.write_text(
            json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

        report = list_secure_credentials(
            self.root,
            receipt_authentication_key=AUTH_KEY,
        )
        row = report["credentials"][0]
        self.assertEqual(
            set(row),
            {
                "credential_id",
                "receipt_authentication_status",
                "lifecycle_authentication_status",
                "broker_authoritative",
                "scope_binding",
            },
        )
        self.assertEqual(row["receipt_authentication_status"], "invalid")
        self.assertIsNone(row["scope_binding"])
        self.assertNotIn(sentinel, json.dumps(report, ensure_ascii=False))
        self.assertNotIn(sentinel, repr(report))

    def test_scope_hash_workspace_and_revision_must_match_before_read(self) -> None:
        _, native, scope = self._commit_and_authorize()
        broker = self._broker(native, scope)
        cases = (
            replace(scope, scope_receipt_sha256="sha256:" + ("0" * 64)),
            replace(scope, workspace_fingerprint=WORKSPACE_B),
            replace(scope, revision="lifecycle-" + ("0" * 64)),
        )
        for changed in cases:
            with self.subTest(changed=changed):
                with self.assertRaises(SecureCredentialRegistryError):
                    broker.resolve(changed)
                self.assertEqual(native.read_targets, [])

    def test_broker_requires_claim_before_native_secret_read(self) -> None:
        _, native, scope = self._commit_and_authorize()
        broker = ReceiptBackedNotionCredentialBroker(
            self.root,
            native,
            AUTH_KEY,
            FINGERPRINT_KEY,
        )

        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_required",
        ):
            broker.resolve(scope)

        self.assertEqual(native.read_targets, [])

    def test_expired_capability_cannot_be_claimed_or_read_native_secret(self) -> None:
        _, native, scope = self._commit_and_authorize()
        capability = CredentialCapability.issue(
            request_sha256=CAPABILITY_REQUEST_SHA256,
            plan_sha256=CAPABILITY_PLAN_SHA256,
            scopes=[self._capability_scope(scope)],
            reviewed_by="reviewer-1",
            max_provider_requests=1,
            issued_at=CAPABILITY_NOW,
            ttl_seconds=30,
        )

        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_expired",
        ):
            self._claim_for_scopes(
                scope,
                capability=capability,
                now=CAPABILITY_NOW + timedelta(seconds=30),
            )

        self.assertEqual(native.read_targets, [])
        self.assertFalse(
            (
                self.root
                / CAPABILITY_CLAIMS_RELATIVE
                / f"{capability.capability_id}.json"
            ).exists()
        )

    def test_claim_scope_mismatch_blocks_before_native_secret_read(self) -> None:
        _, native, scope = self._commit_and_authorize()
        different_scope = replace(scope, workspace_fingerprint=WORKSPACE_B)
        claimed_use = self._claim_for_scopes(different_scope)
        broker = self._broker(
            native,
            scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
            claimed_use=claimed_use,
        )

        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_scope_not_allowed",
        ):
            broker.resolve(scope)

        self.assertEqual(native.read_targets, [])

    def test_receipt_purpose_is_enforced_before_native_secret_read(self) -> None:
        receipt = make_receipt()
        receipt["purpose"] = "diagnostic"
        _, native, scope = self._commit_and_authorize(receipt)
        broker = self._broker(
            native,
            scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
        )

        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_purpose_not_authorized",
        ):
            broker.resolve(scope)

        self.assertEqual(native.read_targets, [])

    def test_every_required_registered_capability_is_enforced_before_read(self) -> None:
        required = (
            "read_content",
            "retrieve_page",
            "retrieve_page_as_markdown",
        )
        workspaces = ("8", "9", "a")
        for index, missing in enumerate(required):
            with self.subTest(missing=missing):
                receipt = make_receipt(
                    chr(ord("b") + index),
                    workspace="sha256:" + (workspaces[index] * 64),
                )
                receipt["verified_capabilities"] = sorted(
                    capability
                    for capability in required
                    if capability != missing
                )
                _, native, scope = self._commit_and_authorize(receipt)
                broker = self._broker(
                    native,
                    scope,
                    secret_fingerprint_key=FINGERPRINT_KEY,
                )
                with self.assertRaisesRegex(
                    SecureCredentialRegistryError,
                    "credential_registry_registered_capabilities_insufficient",
                ):
                    broker.resolve(scope)
                self.assertEqual(native.read_targets, [])

    def test_any_existing_claim_leaf_blocks_reuse_even_when_malformed(self) -> None:
        _, native, scope = self._commit_and_authorize()
        capability = CredentialCapability.issue(
            request_sha256=CAPABILITY_REQUEST_SHA256,
            plan_sha256=CAPABILITY_PLAN_SHA256,
            scopes=[self._capability_scope(scope)],
            reviewed_by="reviewer-1",
            max_provider_requests=1,
            issued_at=CAPABILITY_NOW,
        )
        path = (
            self.root
            / CAPABILITY_CLAIMS_RELATIVE
            / f"{capability.capability_id}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"{malformed")

        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_claim_replayed",
        ):
            self._claim_for_scopes(scope, capability=capability)

        self.assertEqual(path.read_bytes(), b"{malformed")
        self.assertEqual(native.read_targets, [])

    def test_claim_ledger_requires_ignored_local_profile(self) -> None:
        _, native, scope = self._commit_and_authorize()
        (self.root / ".gitignore").write_text("objects/\n", encoding="utf-8")

        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_local_profile_not_ignored",
        ):
            self._claim_for_scopes(scope)

        self.assertEqual(native.read_targets, [])
        self.assertFalse((self.root / CAPABILITY_CLAIMS_RELATIVE).exists())

    def test_concurrent_claim_is_exclusive_and_loser_is_replay(self) -> None:
        _, native, scope = self._commit_and_authorize()
        capability = CredentialCapability.issue(
            request_sha256=CAPABILITY_REQUEST_SHA256,
            plan_sha256=CAPABILITY_PLAN_SHA256,
            scopes=[self._capability_scope(scope)],
            reviewed_by="reviewer-1",
            max_provider_requests=1,
            issued_at=CAPABILITY_NOW,
        )
        barrier = threading.Barrier(3)
        claimed = []
        errors: list[str] = []

        def attempt() -> None:
            barrier.wait()
            try:
                claimed.append(
                    self._claim_for_scopes(scope, capability=capability)
                )
            except SecureCredentialRegistryError as exc:
                errors.append(exc.code)

        workers = [threading.Thread(target=attempt) for _ in range(2)]
        for worker in workers:
            worker.start()
        barrier.wait()
        for worker in workers:
            worker.join(timeout=5)

        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(len(claimed), 1)
        self.assertEqual(errors, ["credential_capability_claim_replayed"])
        self.assertEqual(native.read_targets, [])

    def test_claim_tampering_blocks_provider_authorization(self) -> None:
        _, native, scope = self._commit_and_authorize()
        claimed_use = self._claim_for_scopes(scope)
        credential = self._broker(
            native,
            scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
            claimed_use=claimed_use,
        ).resolve(scope)
        path = (
            self.root
            / CAPABILITY_CLAIMS_RELATIVE
            / f"{claimed_use.capability_id}.json"
        )
        document = json.loads(path.read_text(encoding="utf-8"))
        document["authentication"]["mac"] = "0" * 64
        path.write_bytes(
            (
                json.dumps(
                    document,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
        )

        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_claim_authentication_invalid",
        ):
            credential.authorize_provider_request("retrieve_page")

        self.assertEqual(len(native.read_targets), 1)
        self.assertEqual(claimed_use.provider_request_authorizations, 0)
        credential.close()

    def test_claim_request_and_plan_digests_are_hmac_bound(self) -> None:
        _, native, scope = self._commit_and_authorize()
        claimed_use = self._claim_for_scopes(scope)
        path = (
            self.root
            / CAPABILITY_CLAIMS_RELATIVE
            / f"{claimed_use.capability_id}.json"
        )
        original = path.read_bytes()
        for field, replacement in (
            ("request_sha256", "sha256:" + ("8" * 64)),
            ("plan_sha256", "sha256:" + ("9" * 64)),
        ):
            with self.subTest(field=field):
                document = json.loads(original.decode("utf-8"))
                document[field] = replacement
                path.write_bytes(
                    (
                        json.dumps(
                            document,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    ).encode("utf-8")
                )
                with self.assertRaisesRegex(
                    SecureCredentialRegistryError,
                    "credential_capability_claim_authentication_invalid",
                ):
                    claimed_use.authorize_request("retrieve_page", scope=scope)
                path.write_bytes(original)

        self.assertEqual(claimed_use.provider_request_authorizations, 0)
        self.assertEqual(native.read_targets, [])

    def test_authenticated_digest_drift_still_fails_capability_binding(self) -> None:
        _, native, scope = self._commit_and_authorize()
        claimed_use = self._claim_for_scopes(scope)
        path = (
            self.root
            / CAPABILITY_CLAIMS_RELATIVE
            / f"{claimed_use.capability_id}.json"
        )
        document = json.loads(path.read_text(encoding="utf-8"))
        document["request_sha256"] = "sha256:" + ("8" * 64)
        document["authentication"]["mac"] = _capability_claim_mac(
            document,
            AUTH_KEY,
        )
        path.write_bytes(
            (
                json.dumps(document, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode("utf-8")
        )

        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_claim_binding_mismatch",
        ):
            claimed_use.authorize_request("retrieve_page", scope=scope)

        self.assertEqual(claimed_use.provider_request_authorizations, 0)
        self.assertEqual(native.read_targets, [])

    def test_endpoint_and_request_budget_are_bound_to_bearer(self) -> None:
        _, native, scope = self._commit_and_authorize()
        claimed_use = self._claim_for_scopes(scope, max_provider_requests=2)
        credential = self._broker(
            native,
            scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
            claimed_use=claimed_use,
        ).resolve(scope)

        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_endpoint_not_allowed",
        ):
            credential.authorize_provider_request("create_page")
        credential.authorize_provider_request("retrieve_page")
        credential.authorize_provider_request("retrieve_page_as_markdown")
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_request_budget_exhausted",
        ):
            credential.authorize_provider_request("retrieve_page")

        self.assertEqual(claimed_use.provider_request_authorizations, 2)
        self.assertEqual(claimed_use.provider_requests_remaining, 0)
        self.assertEqual(len(native.read_targets), 1)
        claimed_use.finalize_succeeded()
        credential.close()

    def test_concurrent_provider_authorization_cannot_overspend_budget(self) -> None:
        _, native, scope = self._commit_and_authorize()
        claimed_use = self._claim_for_scopes(scope, max_provider_requests=1)
        credential = self._broker(
            native,
            scope,
            secret_fingerprint_key=FINGERPRINT_KEY,
            claimed_use=claimed_use,
        ).resolve(scope)
        barrier = threading.Barrier(3)
        outcomes: list[str] = []

        def authorize() -> None:
            barrier.wait()
            try:
                credential.authorize_provider_request("retrieve_page")
                outcomes.append("authorized")
            except SecureCredentialRegistryError as exc:
                outcomes.append(exc.code)

        workers = [threading.Thread(target=authorize) for _ in range(2)]
        for worker in workers:
            worker.start()
        barrier.wait()
        for worker in workers:
            worker.join(timeout=5)

        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertCountEqual(
            outcomes,
            ["authorized", "credential_capability_request_budget_exhausted"],
        )
        self.assertEqual(claimed_use.provider_request_authorizations, 1)
        claimed_use.finalize_succeeded()
        credential.close()

    def test_successful_finalize_is_authenticated_single_shot_and_not_reusable(self) -> None:
        _, native, scope = self._commit_and_authorize()
        claimed_use = self._claim_for_scopes(scope, max_provider_requests=2)
        path = (
            self.root
            / CAPABILITY_CLAIMS_RELATIVE
            / f"{claimed_use.capability_id}.json"
        )
        self.assertTrue(path.is_file())
        self.assertEqual(native.read_targets, [])
        started = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(started["request_sha256"], CAPABILITY_REQUEST_SHA256)
        self.assertEqual(started["plan_sha256"], CAPABILITY_PLAN_SHA256)
        claimed_use.authorize_request("retrieve_page", scope=scope)
        claimed_use.finalize_succeeded()

        summary = claimed_use.public_summary()
        self.assertEqual(
            summary["schema_version"],
            "wom-credential-capability-use-summary/v0.1",
        )
        self.assertEqual(summary["status"], "succeeded")
        self.assertEqual(summary["provider_request_authorizations"], 1)
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["status"], "succeeded")
        self.assertEqual(document["provider_requests_authorized"], 1)
        self.assertEqual(document["request_sha256"], CAPABILITY_REQUEST_SHA256)
        self.assertEqual(document["plan_sha256"], CAPABILITY_PLAN_SHA256)
        self.assertIsNone(document["failure_code"])
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_claim_state_invalid",
        ):
            claimed_use.finalize_succeeded()
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_claim_state_invalid",
        ):
            claimed_use.authorize_request("retrieve_page", scope=scope)
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_claim_replayed",
        ):
            self._claim_for_scopes(
                scope,
                capability=claimed_use.capability,
            )

    def test_failed_finalize_is_permanent_and_replay_blocked(self) -> None:
        _, native, scope = self._commit_and_authorize()
        claimed_use = self._claim_for_scopes(scope)
        claimed_use.finalize_failed("recovery_cancelled")
        path = (
            self.root
            / CAPABILITY_CLAIMS_RELATIVE
            / f"{claimed_use.capability_id}.json"
        )
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["status"], "failed")
        self.assertEqual(document["failure_code"], "recovery_cancelled")
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_claim_replayed",
        ):
            self._claim_for_scopes(
                scope,
                capability=claimed_use.capability,
            )
        self.assertEqual(native.read_targets, [])

    def test_tampered_claim_cannot_be_finalized(self) -> None:
        _, native, scope = self._commit_and_authorize()
        claimed_use = self._claim_for_scopes(scope)
        path = (
            self.root
            / CAPABILITY_CLAIMS_RELATIVE
            / f"{claimed_use.capability_id}.json"
        )
        document = json.loads(path.read_text(encoding="utf-8"))
        document["authentication"]["mac"] = "f" * 64
        path.write_bytes(
            (
                json.dumps(document, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode("utf-8")
        )

        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_capability_claim_authentication_invalid",
        ):
            claimed_use.finalize_failed("recovery_cancelled")

        self.assertEqual(claimed_use.status, "started")
        self.assertEqual(native.read_targets, [])

    def test_claim_and_public_summary_are_secret_free(self) -> None:
        receipt = make_receipt()
        _, native, scope = self._commit_and_authorize(receipt)
        claimed_use = self._claim_for_scopes(scope)
        path = (
            self.root
            / CAPABILITY_CLAIMS_RELATIVE
            / f"{claimed_use.capability_id}.json"
        )
        summary = claimed_use.public_summary()
        self.assertNotIn("request_sha256", summary)
        self.assertNotIn("plan_sha256", summary)
        claim_document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            claim_document["request_sha256"],
            CAPABILITY_REQUEST_SHA256,
        )
        self.assertEqual(claim_document["plan_sha256"], CAPABILITY_PLAN_SHA256)
        serialized = "\n".join(
            (
                path.read_text(encoding="utf-8"),
                json.dumps(summary, sort_keys=True),
                repr(claimed_use),
                repr(self._broker(native, scope, claimed_use=claimed_use)),
            )
        )
        for forbidden in (
            SECRET.decode("ascii"),
            str(receipt["encrypted_backend_id"]),
            AUTH_KEY.decode("ascii"),
            FINGERPRINT_KEY.decode("ascii"),
            scope.credential_id,
            scope.workspace_fingerprint,
            "reviewer-1",
        ):
            self.assertNotIn(forbidden, serialized)
        with self.assertRaises(SecureCredentialRegistryError) as captured:
            self._claim_for_scopes(
                scope,
                capability=claimed_use.capability,
            )
        self.assertEqual(
            str(captured.exception),
            "credential_capability_claim_replayed",
        )

    def test_lifecycle_requires_human_approval_and_never_revokes(self) -> None:
        receipts = (
            make_receipt("a", fingerprint_digit="3"),
            make_receipt("b", fingerprint_digit="6"),
            make_receipt("c", fingerprint_digit="7"),
        )
        committer = self._committer()
        for receipt in receipts:
            committer.commit_atomic(receipt)
        lifecycle_path = self.root / "profiles" / "local" / "credential-intake" / "lifecycle.json"

        plan = persist_duplicate_lifecycle_decision(
            self.root,
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(receipts[0]["credential_id"]),
            revocation_pending_credential_ids=(str(receipts[2]["credential_id"]),),
            human_approved=False,
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertEqual(plan["status"], "human_decision_required")
        self.assertFalse(plan["persisted"])
        self.assertEqual(plan["distinct_fingerprint_count"], 3)
        self.assertFalse(lifecycle_path.exists())

        result = self._approve_lifecycle(
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(receipts[0]["credential_id"]),
            revocation_pending_credential_ids=(str(receipts[2]["credential_id"]),),
        )
        self.assertTrue(result["persisted"])
        self.assertFalse(result["delete_performed"])
        self.assertFalse(result["revoke_performed"])
        states = {row["credential_id"]: row for row in result["credentials"]}
        self.assertEqual(sum(row["is_default"] for row in states.values()), 1)
        self.assertEqual(states[str(receipts[0]["credential_id"])]["lifecycle_status"], "active")
        self.assertEqual(states[str(receipts[1]["credential_id"])]["lifecycle_status"], "legacy_valid")
        self.assertEqual(
            states[str(receipts[2]["credential_id"])]["lifecycle_status"],
            "revocation_pending",
        )
        report = list_secure_credentials(
            self.root,
            receipt_authentication_key=AUTH_KEY,
        )
        authoritative = [row for row in report["credentials"] if row["broker_authoritative"]]
        self.assertEqual(len(authoritative), 1)
        self.assertEqual(authoritative[0]["credential_id"], receipts[0]["credential_id"])
        fingerprint_values = {
            row["credential_fingerprint"] for row in report["credentials"]
        }
        self.assertEqual(len(fingerprint_values), 3)
        self.assertTrue(
            all(value.startswith("hmac-sha256:") and len(value) == 76 for value in fingerprint_values)
        )
        self.assertNotIn(SECRET.decode("ascii"), json.dumps(report, ensure_ascii=False))
        lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
        self.assertEqual(lifecycle["scopes"][0]["reviewed_by"], "reviewer-1")
        self.assertEqual(lifecycle["scopes"][0]["plan_sha256"], result["plan_sha256"])

    def test_same_secret_fingerprint_can_be_explicitly_selected_without_revocation(self) -> None:
        first = make_receipt("a", fingerprint_digit="3")
        second = make_receipt("b", fingerprint_digit="3")
        committer = self._committer()
        committer.commit_atomic(first)
        committer.commit_atomic(second)

        plan = persist_duplicate_lifecycle_decision(
            self.root,
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(first["credential_id"]),
            human_approved=False,
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertEqual(plan["credential_count"], 2)
        self.assertEqual(plan["distinct_fingerprint_count"], 1)
        result = persist_duplicate_lifecycle_decision(
            self.root,
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(first["credential_id"]),
            human_approved=True,
            receipt_authentication_key=AUTH_KEY,
            expected_plan_sha256=str(plan["plan_sha256"]),
            reviewed_by="reviewer-1",
        )

        states = {row["credential_id"]: row for row in result["credentials"]}
        self.assertTrue(states[str(first["credential_id"])]["is_default"])
        self.assertEqual(
            states[str(second["credential_id"])]["lifecycle_status"],
            "legacy_valid",
        )
        self.assertFalse(result["delete_performed"])
        self.assertFalse(result["revoke_performed"])

    def test_exact_committer_temp_is_ignored_but_arbitrary_entry_is_rejected(self) -> None:
        receipt = make_receipt("a")
        self._committer().commit_atomic(receipt)
        receipts_root = self.root / "profiles" / "local" / "credential-intake" / "receipts"
        leftover = receipts_root / (
            "." + str(receipt["credential_id"]) + ".0123456789abcdef.tmp"
        )
        leftover.write_bytes(b"interrupted temporary")

        report = list_secure_credentials(
            self.root,
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertEqual(report["credential_count"], 1)

        (receipts_root / ".unexpected.tmp").write_bytes(b"untrusted")
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_receipt_entry_invalid",
        ):
            list_secure_credentials(self.root, receipt_authentication_key=AUTH_KEY)

    def test_gitignore_negation_cannot_reinclude_private_registry(self) -> None:
        (self.root / ".gitignore").write_text(
            "profiles/local/\n!profiles/local/credential-intake/\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_local_profile_not_ignored",
        ):
            list_secure_credentials(self.root)

    def test_lifecycle_plan_is_deterministic_and_receipt_set_drift_blocks_write(self) -> None:
        first = make_receipt("a", fingerprint_digit="3")
        self._committer().commit_atomic(first)
        arguments = {
            "provider": "notion",
            "workspace_fingerprint": WORKSPACE_A,
            "selected_default_credential_id": str(first["credential_id"]),
            "human_approved": False,
            "receipt_authentication_key": AUTH_KEY,
        }
        plan_one = persist_duplicate_lifecycle_decision(self.root, **arguments)
        plan_two = persist_duplicate_lifecycle_decision(self.root, **arguments)
        self.assertEqual(plan_one["plan_sha256"], plan_two["plan_sha256"])
        self.assertEqual(plan_one["credential_count"], 1)
        self.assertEqual(plan_one["distinct_fingerprint_count"], 1)
        self.assertEqual(plan_one["revocation_pending_count"], 0)
        self.assertEqual(plan_one["legacy_valid_count"], 0)

        second = make_receipt("b", fingerprint_digit="6")
        self._committer().commit_atomic(second)
        lifecycle_path = self.root / "profiles" / "local" / "credential-intake" / "lifecycle.json"
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_lifecycle_plan_mismatch",
        ):
            persist_duplicate_lifecycle_decision(
                self.root,
                provider="notion",
                workspace_fingerprint=WORKSPACE_A,
                selected_default_credential_id=str(first["credential_id"]),
                human_approved=True,
                receipt_authentication_key=AUTH_KEY,
                expected_plan_sha256=str(plan_one["plan_sha256"]),
                reviewed_by="reviewer-1",
            )
        self.assertFalse(lifecycle_path.exists())

    def test_lifecycle_decision_drift_and_invalid_reviewer_block_write(self) -> None:
        first = make_receipt("a", fingerprint_digit="3")
        second = make_receipt("b", fingerprint_digit="6")
        committer = self._committer()
        committer.commit_atomic(first)
        committer.commit_atomic(second)
        plan = persist_duplicate_lifecycle_decision(
            self.root,
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(first["credential_id"]),
            human_approved=False,
            receipt_authentication_key=AUTH_KEY,
        )
        lifecycle_path = self.root / "profiles" / "local" / "credential-intake" / "lifecycle.json"
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_lifecycle_plan_mismatch",
        ):
            persist_duplicate_lifecycle_decision(
                self.root,
                provider="notion",
                workspace_fingerprint=WORKSPACE_A,
                selected_default_credential_id=str(second["credential_id"]),
                human_approved=True,
                receipt_authentication_key=AUTH_KEY,
                expected_plan_sha256=str(plan["plan_sha256"]),
                reviewed_by="reviewer-1",
            )
        self.assertFalse(lifecycle_path.exists())
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_lifecycle_reviewer_invalid",
        ):
            persist_duplicate_lifecycle_decision(
                self.root,
                provider="notion",
                workspace_fingerprint=WORKSPACE_A,
                selected_default_credential_id=str(first["credential_id"]),
                human_approved=True,
                receipt_authentication_key=AUTH_KEY,
                expected_plan_sha256=str(plan["plan_sha256"]),
                reviewed_by="unsafe reviewer with spaces",
            )
        self.assertFalse(lifecycle_path.exists())
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_lifecycle_reviewer_invalid",
        ):
            persist_duplicate_lifecycle_decision(
                self.root,
                provider="notion",
                workspace_fingerprint=WORKSPACE_A,
                selected_default_credential_id=str(first["credential_id"]),
                human_approved=True,
                receipt_authentication_key=AUTH_KEY,
                expected_plan_sha256=str(plan["plan_sha256"]),
                reviewed_by="ntn_abcdefghijklmnopqrstuvwxyz0123456789",
            )
        self.assertFalse(lifecycle_path.exists())

    def test_non_default_legacy_receipt_cannot_be_resolved(self) -> None:
        first = make_receipt("a", fingerprint_digit="3")
        second = make_receipt("b", fingerprint_digit="6")
        committer = self._committer()
        committer.commit_atomic(first)
        committer.commit_atomic(second)
        self._approve_lifecycle(
            provider="notion",
            workspace_fingerprint=WORKSPACE_A,
            selected_default_credential_id=str(first["credential_id"]),
        )
        row = lookup_secure_credential(
            self.root,
            str(second["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        native = FakeExactWindowsNative()
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_lifecycle_not_default",
        ):
            forged_scope = replace(
                scope_from_public(row),
                persisted=True,
                workspace_evidence_verified=True,
            )
            self._broker(native, forged_scope).resolve(forged_scope)
        self.assertEqual(native.read_targets, [])

    def test_lifecycle_tampering_blocks_before_native_read(self) -> None:
        _, native, scope = self._commit_and_authorize()
        path = self.root / "profiles" / "local" / "credential-intake" / "lifecycle.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        document["scopes"][0]["revision"] = "lifecycle-" + ("9" * 64)
        path.write_text(
            json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_lifecycle_authentication_invalid",
        ):
            self._broker(native, scope).resolve(scope)
        self.assertEqual(native.read_targets, [])

    def test_stable_archive_key_is_created_once_and_buffers_are_wiped(self) -> None:
        native = FakeExactWindowsNative()
        random_calls: list[int] = []

        def fixed_random(length: int) -> bytes:
            random_calls.append(length)
            return b"K" * length

        provider = StableArchiveFingerprintKeyProvider(native, fixed_random)
        digest_one = provider.use_key(
            self.root,
            lambda view: hashlib.sha256(view).hexdigest(),
            create_if_missing=True,
        )
        digest_two = provider.use_key(
            self.root,
            lambda view: hashlib.sha256(view).hexdigest(),
        )

        self.assertEqual(digest_one, digest_two)
        self.assertEqual(random_calls, [32])
        self.assertEqual(len(native.write_targets), 1)
        self.assertEqual(len(native.read_targets), 2)
        self.assertEqual(native.write_targets[0], native.read_targets[0])
        self.assertRegex(
            native.write_targets[0],
            r"^WOM/credential-intake/backend_key_[0-9a-f]{64}$",
        )
        self.assertTrue(all(all(value == 0 for value in buffer) for buffer in native.returned_buffers))
        self.assertNotIn("K" * 32, repr(provider))

    def test_read_only_key_lookup_never_creates_missing_key(self) -> None:
        native = FakeExactWindowsNative()
        random_calls: list[int] = []
        provider = StableArchiveFingerprintKeyProvider(
            native,
            lambda length: random_calls.append(length) or (b"K" * length),
        )
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_key_not_found",
        ):
            provider.use_key(self.root, lambda view: bytes(view))
        self.assertEqual(random_calls, [])
        self.assertEqual(native.write_targets, [])
        self.assertEqual(native.read_targets, [])
        self.assertFalse(
            (self.root / "profiles/local/credential-intake/.registry.lock").exists()
        )

    def test_new_authenticated_receipt_invalidates_old_default_until_reapproved(self) -> None:
        first = make_receipt("a", fingerprint_digit="3")
        second = make_receipt("b", fingerprint_digit="6")
        public, native, old_scope = self._commit_and_authorize(first)
        self.assertTrue(public["broker_authoritative"])
        self._committer().commit_atomic(second)

        after_drift = lookup_secure_credential(
            self.root,
            str(first["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertFalse(after_drift["broker_authoritative"])
        self.assertFalse(after_drift["scope_binding"]["persisted"])
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_lifecycle_receipt_set_drift",
        ):
            self._broker(native, old_scope).resolve(old_scope)
        self.assertEqual(native.read_targets, [])

    def test_lookup_is_exact_and_content_free(self) -> None:
        receipt = make_receipt()
        self._committer().commit_atomic(receipt)
        row = lookup_secure_credential(
            self.root,
            str(receipt["credential_id"]),
            receipt_authentication_key=AUTH_KEY,
        )
        self.assertEqual(row["credential_id"], receipt["credential_id"])
        self.assertNotIn("encrypted_backend_id", row)
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_credential_not_found",
        ):
            lookup_secure_credential(
                self.root,
                "cred_zzzzzzzzzzzzzzzz",
                receipt_authentication_key=AUTH_KEY,
            )

    def test_local_profile_must_be_ignored(self) -> None:
        (self.root / ".gitignore").write_text("objects/\n", encoding="utf-8")
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_local_profile_not_ignored",
        ):
            create_archive_atomic_json_receipt_committer(
                self.root,
                expected_archive_id="archive:test",
                receipt_authentication_key=AUTH_KEY,
            )

    def test_receipt_schema_and_size_are_strict(self) -> None:
        receipt = make_receipt()
        receipt["unexpected"] = True
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_receipt_schema_invalid",
        ):
            self._committer().commit_atomic(receipt)

        receipts_root = self.root / "profiles" / "local" / "credential-intake" / "receipts"
        receipts_root.mkdir(parents=True, exist_ok=True)
        path = receipts_root / "cred_aaaaaaaaaaaaaaaa.json"
        path.write_bytes(b"{" + (b" " * (64 * 1024)))
        with self.assertRaisesRegex(
            SecureCredentialRegistryError,
            "credential_registry_local_document_size_invalid",
        ):
            list_secure_credentials(self.root, receipt_authentication_key=AUTH_KEY)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_reparse_receipt_directory_is_rejected_when_supported(self) -> None:
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        parent = self.root / "profiles" / "local" / "credential-intake"
        parent.mkdir(parents=True)
        link = parent / "receipts"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation not permitted")
        with self.assertRaises(SecureCredentialRegistryError):
            list_secure_credentials(self.root, receipt_authentication_key=AUTH_KEY)


if __name__ == "__main__":
    unittest.main()
