from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

import yaml

from wom_kit.credential_continuity import (
    _AdapterProcessResult as AdapterProcessResult,
    CredentialContinuityError,
    _CredentialUseBroker as CredentialUseBroker,
    _KeePassXCExactEntryAdapter as KeePassXCExactEntryAdapter,
    _TrustedConsumerRegistry as TrustedConsumerRegistry,
    _WindowsCredentialManagerExactAdapter as WindowsCredentialManagerExactAdapter,
    _approve_credential_adoption as approve_credential_adoption,
    _discover_local_credential_candidates as discover_local_credential_candidates,
    lookup_credential_binding,
    _plan_credential_adoption as plan_credential_adoption,
    _verify_credential_provider_for_adoption as verify_credential_provider_for_adoption,
    _verify_credential_store_for_adoption as verify_credential_store_for_adoption,
)


PRIVATE_REF = "secret:개인 노션 토큰"
PRIVATE_LOCATOR = "개인 노션 토큰"
PRIVATE_VAULT = "C:\\private\\개인-비밀.kdbx"
PRIVATE_SECRET = "notion-private-token-value"


class CredentialContinuityTests(unittest.TestCase):
    def make_archive(self, temporary: str, credentials: list[object]) -> Path:
        root = Path(temporary) / "archive"
        (root / "profiles" / "local").mkdir(parents=True, exist_ok=True)
        (root / ".gitignore").write_text("profiles/local/\n", encoding="utf-8")
        (root / "archive.yml").write_text("archive_id: archive:test\n", encoding="utf-8")
        (root / "profiles" / "local" / "credential-refs.local.yml").write_text(
            yaml.safe_dump(
                {
                    "version": "wom-local-credential-ref-inventory/v0.1",
                    "credentials": credentials,
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return root

    def valid_row(self, *, exact_ref: str = PRIVATE_REF) -> dict[str, str]:
        return {
            "credential_id": "cred:notion-personal-readonly",
            "credential_kind": "provider_api_key",
            "provider": "notion",
            "purpose": "provider_api_access",
            "credential_ref": exact_ref,
        }

    def discover_one(self, root: Path):
        report = discover_local_credential_candidates(root)
        public = report.to_public_dict()
        self.assertEqual(public["candidate_count"], 1, public)
        return report, report.require_candidate(public["candidates"][0]["candidate_id"])

    def adopt_one(
        self,
        root: Path,
        *,
        adapter_kind: str = "windows_credential_manager",
        binding_id: str = "binding:opaque-001",
    ) -> tuple[dict[str, object], object]:
        _, candidate = self.discover_one(root)
        plan = plan_credential_adoption(
            root,
            candidate,
            adapter_kind=adapter_kind,
            account_label="account:notion-personal",
            workspace_label="workspace:notion-personal",
            vault_path=PRIVATE_VAULT,
            binding_id_factory=lambda: binding_id,
        )
        public_plan = plan.to_public_dict()
        store_evidence, provider_evidence = self.verify_plan(plan)
        result = approve_credential_adoption(
            root,
            plan,
            expected_plan_digest=str(public_plan["plan_digest"]),
            reviewed_by="human:tester",
            store_evidence=store_evidence,
            provider_evidence=provider_evidence,
        )
        return result, plan

    def verify_plan(self, plan):
        if plan.adapter_kind == "windows_credential_manager":
            adapter = WindowsCredentialManagerExactAdapter(
                metadata_reader=lambda locator: locator == PRIVATE_LOCATOR or locator == "다른 토큰",
                secret_reader=lambda _locator: self.fail("adoption verification must not read a secret"),
            )
        else:
            adapter = KeePassXCExactEntryAdapter(
                runner=lambda _argv: AdapterProcessResult(0, "exact-title-only", ""),
            )
        store_evidence = verify_credential_store_for_adoption(plan, adapter=adapter)

        def verifier(context):
            rendered = json.dumps(context, ensure_ascii=False, sort_keys=True)
            self.assert_private_absent(rendered)
            return {
                "verified": True,
                "provider": context["provider"],
                "account_label": context["account_label"],
                "workspace_label": context["workspace_label"],
                "credential_fingerprint": "fingerprint:notion-key-001",
                "rotation_status": "current",
                "default_selection": True,
            }

        provider_evidence = verify_credential_provider_for_adoption(
            plan,
            verifier=verifier,
            verifier_id="verifier:notion-test",
        )
        for rendered in (
            repr(store_evidence),
            json.dumps(store_evidence.to_public_dict(), ensure_ascii=False, sort_keys=True),
            repr(provider_evidence),
            json.dumps(provider_evidence.to_public_dict(), ensure_ascii=False, sort_keys=True),
        ):
            self.assert_private_absent(rendered)
        return store_evidence, provider_evidence

    def assert_private_absent(self, rendered: str, *extra: str) -> None:
        for private in (PRIVATE_REF, PRIVATE_LOCATOR, PRIVATE_VAULT, PRIVATE_SECRET, *extra):
            if private:
                self.assertNotIn(private, rendered)

    def test_unicode_legacy_discovery_is_content_free_and_row_tolerant(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            raw_secret = "synthetic_secret_value_must_not_echo"
            root = self.make_archive(
                temporary,
                [
                    self.valid_row(),
                    {"credential_id": "cred:broken", "credential_ref": raw_secret},
                    "not-an-object",
                ],
            )

            report = discover_local_credential_candidates(root)
            public = report.to_public_dict()
            rendered = json.dumps(public, ensure_ascii=False, sort_keys=True)

            self.assertTrue(public["ok"])
            self.assertEqual(public["status"], "ready_with_ignored_rows")
            self.assertEqual(public["candidate_count"], 1)
            self.assertEqual(public["ignored_row_count"], 2)
            self.assertEqual(public["candidates"][0]["presence"], "not_checked")
            self.assertEqual(public["candidates"][0]["provider"], "notion")
            self.assertFalse(public["closed_actions"]["secret_value_read"])
            self.assertFalse(public["closed_actions"]["credential_store_opened"])
            self.assert_private_absent(rendered, raw_secret)
            self.assert_private_absent(repr(report), raw_secret)

    def test_adoption_binds_exact_candidate_but_keeps_private_locator_local(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_archive(temporary, [self.valid_row()])
            result, plan = self.adopt_one(root)

            public_plan = json.dumps(plan.to_public_dict(), ensure_ascii=False, sort_keys=True)
            public_result = json.dumps(result, ensure_ascii=False, sort_keys=True)
            binding_path = root / "profiles" / "local" / "credential-bindings.local.json"
            receipt_path = root.joinpath(*str(result["receipt_path"]).split("/"))
            binding_text = binding_path.read_text(encoding="utf-8")
            binding_document = json.loads(binding_text)
            local_binding = binding_document["bindings"][0]
            receipt_text = receipt_path.read_text(encoding="utf-8")
            receipt_document = json.loads(receipt_text)
            lookup = lookup_credential_binding(
                root,
                binding_id=str(result["binding_id"]),
                binding_revision=int(result["binding_revision"]),
            )

            self.assertTrue(result["ok"])
            self.assertTrue(result["persisted"])
            self.assertEqual(result["reason_code"], "credential_binding_adopted_verified")
            self.assertEqual(result["binding_id"], "binding:opaque-001")
            self.assertEqual(result["binding_revision"], 1)
            self.assertIn(PRIVATE_REF, binding_text)
            self.assertIn(PRIVATE_LOCATOR, binding_text)
            self.assertEqual(local_binding["vault_path"], PRIVATE_VAULT)
            self.assertIn("account:notion-personal", binding_text)
            self.assertIn("workspace:notion-personal", binding_text)
            self.assertEqual(local_binding["presence"], "exact_match")
            self.assertTrue(local_binding["persisted"])
            self.assertEqual(local_binding["store_verification"]["status"], "verified")
            self.assertEqual(local_binding["provider_verification"]["status"], "verified")
            self.assertEqual(local_binding["credential_fingerprint"], "fingerprint:notion-key-001")
            self.assertEqual(local_binding["rotation_status"], "current")
            self.assertTrue(local_binding["default_selection"])
            self.assertTrue(lookup["binding"]["persisted"])
            self.assertEqual(lookup["binding"]["presence"], "exact_match")
            self.assertEqual(lookup["binding"]["credential_fingerprint"], "fingerprint:notion-key-001")
            self.assert_private_absent(public_plan)
            self.assert_private_absent(public_result)
            self.assert_private_absent(receipt_text)
            self.assert_private_absent(json.dumps(lookup, ensure_ascii=False, sort_keys=True))
            self.assertNotIn("exact_ref", receipt_document["binding"])
            self.assertNotIn("entry_locator", receipt_document["binding"])
            self.assertNotIn("vault_path", receipt_document["binding"])

    def test_unverified_adoption_is_no_write_and_confirms_no_binding_or_credential(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_archive(temporary, [self.valid_row()])
            _, candidate = self.discover_one(root)
            plan = plan_credential_adoption(
                root,
                candidate,
                adapter_kind="windows_credential_manager",
                account_label="account:notion-personal",
                workspace_label="workspace:notion-personal",
                binding_id_factory=lambda: "binding:unverified-001",
            )
            preview = plan.to_public_dict()

            self.assertFalse(preview["persisted"])
            self.assertEqual(preview["reason_code"], "credential_adoption_verification_required")
            self.assertIn("proposed_binding_id", preview)
            self.assertNotIn("binding_id", preview)

            no_store = approve_credential_adoption(
                root,
                plan,
                expected_plan_digest=str(preview["plan_digest"]),
                reviewed_by="human:tester",
            )
            self.assertFalse(no_store["ok"])
            self.assertFalse(no_store["persisted"])
            self.assertEqual(no_store["reason_code"], "credential_store_presence_not_verified")
            self.assertNotIn("binding_id", no_store)
            self.assertNotIn("credential_id", no_store)
            self.assertEqual(no_store["files_written"], [])

            store_evidence, _ = self.verify_plan(plan)
            no_provider = approve_credential_adoption(
                root,
                plan,
                expected_plan_digest=str(preview["plan_digest"]),
                reviewed_by="human:tester",
                store_evidence=store_evidence,
            )
            self.assertFalse(no_provider["persisted"])
            self.assertEqual(no_provider["reason_code"], "credential_provider_identity_not_verified")
            self.assertFalse((root / "profiles" / "local" / "credential-bindings.local.json").exists())
            self.assertFalse((root / "receipts" / "credentials" / "adoptions").exists())
            self.assert_private_absent(json.dumps(no_store, ensure_ascii=False, sort_keys=True))
            self.assert_private_absent(json.dumps(no_provider, ensure_ascii=False, sort_keys=True))

    def test_adoption_blocks_expected_digest_and_source_drift_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_archive(temporary, [self.valid_row()])
            report, candidate = self.discover_one(root)
            plan = plan_credential_adoption(
                root,
                candidate,
                adapter_kind="windows_credential_manager",
                binding_id_factory=lambda: "binding:drift-001",
            )

            with self.assertRaises(CredentialContinuityError) as digest_error:
                approve_credential_adoption(
                    root,
                    plan,
                    expected_plan_digest="0" * 64,
                    reviewed_by="human:tester",
                )
            self.assertEqual(digest_error.exception.code, "credential_adoption_plan_drift")

            catalog = root / "profiles" / "local" / "credential-refs.local.yml"
            catalog.write_text(catalog.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
            with self.assertRaises(CredentialContinuityError) as source_error:
                approve_credential_adoption(
                    root,
                    plan,
                    expected_plan_digest=str(plan.to_public_dict()["plan_digest"]),
                    reviewed_by="human:tester",
                )
            self.assertEqual(source_error.exception.code, "credential_adoption_source_drift")
            self.assertFalse((root / "profiles" / "local" / "credential-bindings.local.json").exists())
            self.assertFalse((root / "receipts" / "credentials" / "adoptions").exists())
            self.assert_private_absent(str(digest_error.exception))
            self.assert_private_absent(str(source_error.exception))
            self.assertEqual(report.to_public_dict()["candidate_count"], 1)

    def test_adoption_blocks_duplicate_and_rebinding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_archive(temporary, [self.valid_row()])
            self.adopt_one(root, binding_id="binding:fixed-001")

            duplicate_report, duplicate_candidate = self.discover_one(root)
            duplicate_plan = plan_credential_adoption(
                root,
                duplicate_candidate,
                adapter_kind="windows_credential_manager",
                binding_id_factory=lambda: "binding:different-002",
            )
            duplicate_store, duplicate_provider = self.verify_plan(duplicate_plan)
            with self.assertRaises(CredentialContinuityError) as duplicate_error:
                approve_credential_adoption(
                    root,
                    duplicate_plan,
                    expected_plan_digest=str(duplicate_plan.to_public_dict()["plan_digest"]),
                    reviewed_by="human:tester",
                    store_evidence=duplicate_store,
                    provider_evidence=duplicate_provider,
                )
            self.assertEqual(duplicate_error.exception.code, "credential_binding_duplicate")

            root = self.make_archive(temporary, [self.valid_row(exact_ref="secret:다른 토큰")])
            rebound_report, rebound_candidate = self.discover_one(root)
            rebound_plan = plan_credential_adoption(
                root,
                rebound_candidate,
                adapter_kind="windows_credential_manager",
                binding_id_factory=lambda: "binding:fixed-001",
            )
            rebound_store, rebound_provider = self.verify_plan(rebound_plan)
            with self.assertRaises(CredentialContinuityError) as rebound_error:
                approve_credential_adoption(
                    root,
                    rebound_plan,
                    expected_plan_digest=str(rebound_plan.to_public_dict()["plan_digest"]),
                    reviewed_by="human:tester",
                    store_evidence=rebound_store,
                    provider_evidence=rebound_provider,
                )
            self.assertEqual(rebound_error.exception.code, "credential_binding_rebind_blocked")
            self.assert_private_absent(str(duplicate_error.exception), "다른 토큰")
            self.assert_private_absent(str(rebound_error.exception), "다른 토큰")
            self.assertEqual(duplicate_report.to_public_dict()["candidate_count"], 1)
            self.assertEqual(rebound_report.to_public_dict()["candidate_count"], 1)

    def test_adoption_evidence_is_plan_bound_and_provider_tuple_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_archive(temporary, [self.valid_row()])
            _, candidate = self.discover_one(root)
            first = plan_credential_adoption(
                root,
                candidate,
                adapter_kind="windows_credential_manager",
                account_label="account:notion-personal",
                workspace_label="workspace:notion-personal",
                binding_id_factory=lambda: "binding:evidence-001",
            )
            store_evidence, provider_evidence = self.verify_plan(first)
            second = plan_credential_adoption(
                root,
                candidate,
                adapter_kind="windows_credential_manager",
                account_label="account:notion-personal",
                workspace_label="workspace:notion-personal",
                binding_id_factory=lambda: "binding:evidence-001",
            )

            with self.assertRaises(CredentialContinuityError) as evidence_error:
                approve_credential_adoption(
                    root,
                    second,
                    expected_plan_digest=second.plan_digest,
                    reviewed_by="human:tester",
                    store_evidence=store_evidence,
                    provider_evidence=provider_evidence,
                )
            self.assertEqual(
                evidence_error.exception.code,
                "credential_store_verification_evidence_invalid",
            )

            with self.assertRaises(CredentialContinuityError) as provider_error:
                verify_credential_provider_for_adoption(
                    first,
                    verifier=lambda context: {
                        "verified": True,
                        "provider": context["provider"],
                        "account_label": "account:someone-else",
                        "workspace_label": context["workspace_label"],
                    },
                    verifier_id="verifier:notion-test",
                )
            self.assertEqual(provider_error.exception.code, "credential_provider_identity_not_verified")
            self.assertFalse((root / "profiles" / "local" / "credential-bindings.local.json").exists())
            self.assert_private_absent(str(evidence_error.exception))
            self.assert_private_absent(str(provider_error.exception))

    def test_windows_adapter_is_exact_only_and_returns_no_locator_or_secret(self) -> None:
        metadata_calls: list[str] = []
        secret_calls: list[str] = []

        def metadata_reader(locator: str) -> bool:
            metadata_calls.append(locator)
            return True

        def secret_reader(locator: str) -> str:
            secret_calls.append(locator)
            return PRIVATE_SECRET

        adapter = WindowsCredentialManagerExactAdapter(
            metadata_reader=metadata_reader,
            secret_reader=secret_reader,
        )
        binding = {
            "entry_locator": PRIVATE_LOCATOR,
            "exact_ref": PRIVATE_REF,
            "vault_path": PRIVATE_VAULT,
        }

        probe = adapter.probe_exact(binding)
        result = adapter.with_secret(
            binding,
            lambda secret: {"status": "recovered", "secret_seen": secret == PRIVATE_SECRET},
        )

        self.assertEqual(metadata_calls, [PRIVATE_LOCATOR, PRIVATE_LOCATOR])
        self.assertEqual(secret_calls, [PRIVATE_LOCATOR])
        self.assertEqual(probe["presence"], "exact_match")
        self.assertTrue(result["consumer_result"]["secret_seen"])
        self.assert_private_absent(json.dumps(probe, ensure_ascii=False))
        self.assert_private_absent(json.dumps(result, ensure_ascii=False))

        missing = WindowsCredentialManagerExactAdapter(
            metadata_reader=lambda _locator: False,
            secret_reader=lambda _locator: self.fail("secret reader must not run after an exact miss"),
        )
        with self.assertRaises(CredentialContinuityError) as missing_error:
            missing.with_secret(binding, lambda _secret: {"status": "unexpected"})
        self.assertEqual(missing_error.exception.code, "credential_exact_entry_not_found")
        self.assert_private_absent(str(missing_error.exception))

    def test_keepassxc_stdout_reaches_callback_only_and_all_failures_are_redacted(self) -> None:
        commands: list[tuple[str, ...]] = []

        def runner(argv: tuple[str, ...]) -> AdapterProcessResult:
            commands.append(argv)
            return AdapterProcessResult(
                returncode=0,
                stdout=PRIVATE_SECRET,
                stderr="private stderr " + PRIVATE_SECRET,
            )

        adapter = KeePassXCExactEntryAdapter(runner=runner)
        binding = {
            "entry_locator": PRIVATE_LOCATOR,
            "exact_ref": PRIVATE_REF,
            "vault_path": PRIVATE_VAULT,
        }
        result = adapter.with_secret(
            binding,
            lambda secret: {"status": "used", "matched": secret == PRIVATE_SECRET},
        )

        self.assertEqual(len(commands), 1)
        self.assertIn(PRIVATE_VAULT, commands[0])
        self.assertIn(PRIVATE_LOCATOR, commands[0])
        self.assertTrue(result["consumer_result"]["matched"])
        self.assert_private_absent(json.dumps(result, ensure_ascii=False))
        self.assert_private_absent(repr(AdapterProcessResult(0, PRIVATE_SECRET, PRIVATE_SECRET)))

        leaking = KeePassXCExactEntryAdapter(runner=runner)
        with self.assertRaises(CredentialContinuityError) as callback_error:
            leaking.with_secret(binding, lambda secret: (_ for _ in ()).throw(RuntimeError(secret)))
        self.assertEqual(callback_error.exception.code, "credential_consumer_failed")
        self.assert_private_absent(str(callback_error.exception))

        failed = KeePassXCExactEntryAdapter(
            runner=lambda _argv: AdapterProcessResult(9, PRIVATE_SECRET, "failure " + PRIVATE_SECRET)
        )
        with self.assertRaises(CredentialContinuityError) as runner_error:
            failed.with_secret(binding, lambda _secret: {"status": "unexpected"})
        self.assertEqual(runner_error.exception.code, "credential_adapter_failed")
        self.assert_private_absent(str(runner_error.exception))

        missing = KeePassXCExactEntryAdapter(
            runner=lambda _argv: AdapterProcessResult(
                7,
                PRIVATE_SECRET,
                "missing " + PRIVATE_SECRET,
                outcome="not_found",
            )
        )
        missing_probe = missing.probe_exact(binding)
        self.assertEqual(missing_probe["presence"], "not_found")
        self.assert_private_absent(json.dumps(missing_probe, ensure_ascii=False))

        indeterminate = KeePassXCExactEntryAdapter(
            runner=lambda _argv: AdapterProcessResult(9, PRIVATE_SECRET, "failure " + PRIVATE_SECRET)
        )
        with self.assertRaises(CredentialContinuityError) as probe_error:
            indeterminate.probe_exact(binding)
        self.assertEqual(probe_error.exception.code, "credential_exact_probe_failed")
        self.assert_private_absent(str(probe_error.exception))

    def test_broker_claim_is_one_time_and_concurrent_replay_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_archive(temporary, [self.valid_row()])
            adoption, _ = self.adopt_one(root, adapter_kind="windows_credential_manager")
            entered = threading.Event()
            release = threading.Event()
            registry = TrustedConsumerRegistry()

            def consumer(secret: str, _context: dict[str, object]) -> dict[str, object]:
                self.assertEqual(secret, PRIVATE_SECRET)
                entered.set()
                self.assertTrue(release.wait(timeout=5))
                return {"status": "recovered", "recovered_count": 620}

            registry.register(
                "wom:adapter:notion-ancestor-fetch",
                consumer,
                allowed_result_fields={"status", "recovered_count"},
            )
            adapter = WindowsCredentialManagerExactAdapter(
                metadata_reader=lambda locator: locator == PRIVATE_LOCATOR,
                secret_reader=lambda _locator: PRIVATE_SECRET,
            )
            broker = CredentialUseBroker(
                root,
                registry=registry,
                adapters={"windows_credential_manager": adapter},
            )
            approval = {
                "receipt_id": "approval:notion-once",
                "decision": "approve_once",
                "binding_id": adoption["binding_id"],
                "binding_revision": adoption["binding_revision"],
                "action_kind": "cli_token_auth",
                "operation": "resolve_for_approved_action",
                "adapter_kind": "windows_credential_manager",
                "consumer": "wom:adapter:notion-ancestor-fetch",
            }
            first: dict[str, object] = {}

            def run_first() -> None:
                first.update(broker.use_once(approval))

            thread = threading.Thread(target=run_first)
            thread.start()
            self.assertTrue(entered.wait(timeout=5))
            with self.assertRaises(CredentialContinuityError) as replay_error:
                broker.use_once(approval)
            self.assertEqual(replay_error.exception.code, "credential_use_replay_blocked")
            release.set()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())

            self.assertTrue(first["ok"])
            self.assertEqual(first["consumer_result"]["recovered_count"], 620)
            receipt = root.joinpath(*str(first["audit_receipt_path"]).split("/"))
            rendered = json.dumps(first, ensure_ascii=False) + receipt.read_text(encoding="utf-8")
            self.assert_private_absent(rendered)
            self.assert_private_absent(str(replay_error.exception))

    def test_broker_redacts_consumer_exception_and_failed_claim_still_blocks_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_archive(temporary, [self.valid_row()])
            adoption, _ = self.adopt_one(root, adapter_kind="windows_credential_manager")
            registry = TrustedConsumerRegistry()

            def failing_consumer(secret: str, _context: dict[str, object]) -> dict[str, object]:
                raise RuntimeError("provider failure included " + secret)

            registry.register(
                "wom:adapter:notion-ancestor-fetch",
                failing_consumer,
                allowed_result_fields={"status"},
            )
            broker = CredentialUseBroker(
                root,
                registry=registry,
                adapters={
                    "windows_credential_manager": WindowsCredentialManagerExactAdapter(
                        metadata_reader=lambda _locator: True,
                        secret_reader=lambda _locator: PRIVATE_SECRET,
                    )
                },
            )
            approval = {
                "receipt_id": "approval:notion-failure-once",
                "decision": "approve_once",
                "binding_id": adoption["binding_id"],
                "binding_revision": adoption["binding_revision"],
                "action_kind": "cli_token_auth",
                "operation": "resolve_for_approved_action",
                "adapter_kind": "windows_credential_manager",
                "consumer": "wom:adapter:notion-ancestor-fetch",
            }

            with self.assertRaises(CredentialContinuityError) as first_error:
                broker.use_once(approval)
            self.assertEqual(first_error.exception.code, "credential_consumer_failed")
            self.assert_private_absent(str(first_error.exception), "provider failure included")

            claim_files = list((root / "receipts" / "credentials" / "uses").glob("*.json"))
            self.assertEqual(len(claim_files), 1)
            claim_text = claim_files[0].read_text(encoding="utf-8")
            self.assertIn('"status": "failed"', claim_text)
            self.assert_private_absent(claim_text, "provider failure included")

            with self.assertRaises(CredentialContinuityError) as replay_error:
                broker.use_once(approval)
            self.assertEqual(replay_error.exception.code, "credential_use_replay_blocked")

    def test_broker_ignores_untrusted_adapter_return_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_archive(temporary, [self.valid_row()])
            adoption, _ = self.adopt_one(root, adapter_kind="windows_credential_manager")
            registry = TrustedConsumerRegistry()
            registry.register(
                "wom:adapter:notion-ancestor-fetch",
                lambda secret, _context: {
                    "status": "recovered" if secret == PRIVATE_SECRET else "invalid",
                },
                allowed_result_fields={"status"},
            )

            class LeakyInjectedAdapter:
                def with_secret(self, _binding, callback):
                    callback(PRIVATE_SECRET)
                    return {
                        "ok": True,
                        "consumer_result": {"status": PRIVATE_SECRET},
                        "stderr": "leaked " + PRIVATE_SECRET,
                    }

            broker = CredentialUseBroker(
                root,
                registry=registry,
                adapters={"windows_credential_manager": LeakyInjectedAdapter()},
            )
            result = broker.use_once(
                {
                    "receipt_id": "approval:ignore-adapter-payload",
                    "decision": "approve_once",
                    "binding_id": adoption["binding_id"],
                    "binding_revision": adoption["binding_revision"],
                    "action_kind": "cli_token_auth",
                    "operation": "resolve_for_approved_action",
                    "adapter_kind": "windows_credential_manager",
                    "consumer": "wom:adapter:notion-ancestor-fetch",
                }
            )

            self.assertEqual(result["consumer_result"], {"status": "recovered"})
            receipt = root.joinpath(*str(result["audit_receipt_path"]).split("/"))
            self.assert_private_absent(
                json.dumps(result, ensure_ascii=False, sort_keys=True)
                + receipt.read_text(encoding="utf-8")
            )

    def test_broker_rejects_untrusted_consumer_and_binding_revision_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self.make_archive(temporary, [self.valid_row()])
            adoption, _ = self.adopt_one(root, adapter_kind="windows_credential_manager")
            registry = TrustedConsumerRegistry()
            broker = CredentialUseBroker(
                root,
                registry=registry,
                adapters={
                    "windows_credential_manager": WindowsCredentialManagerExactAdapter(
                        metadata_reader=lambda _locator: True,
                        secret_reader=lambda _locator: self.fail("secret must not be read"),
                    )
                },
            )
            approval = {
                "receipt_id": "approval:untrusted",
                "decision": "approve_once",
                "binding_id": adoption["binding_id"],
                "binding_revision": 2,
                "action_kind": "cli_token_auth",
                "operation": "resolve_for_approved_action",
                "adapter_kind": "windows_credential_manager",
                "consumer": "wom:adapter:arbitrary-command",
            }

            with self.assertRaises(CredentialContinuityError) as mismatch_error:
                broker.use_once(approval)
            self.assertEqual(mismatch_error.exception.code, "credential_use_binding_mismatch")
            self.assertFalse((root / "receipts" / "credentials" / "uses").exists())

            approval["binding_revision"] = 1
            with self.assertRaises(CredentialContinuityError) as untrusted_error:
                broker.use_once(approval)
            self.assertEqual(untrusted_error.exception.code, "credential_consumer_not_trusted")
            self.assertFalse((root / "receipts" / "credentials" / "uses").exists())


if __name__ == "__main__":
    unittest.main()
