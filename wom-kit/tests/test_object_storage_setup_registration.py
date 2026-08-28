from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from wom_kit import archive_services
from wom_kit import object_storage_setup_registration as setup_registration_module
from wom_kit.archive_cli import main as cli_main
from wom_kit.exact_human_approval_windows import APPROVE_BUTTON_ID
from wom_kit.exact_human_approval_workflow import (
    ExactHumanApprovalWorkflowError,
    _execute_exact_human_approved_write_core,
)
from wom_kit.exact_operation_manifest import ExactOperationApprovalAuthority
from wom_kit.object_storage_setup_registration import (
    ObjectStorageSetupRegistrationError,
    _Writer,
    apply_object_storage_setup_registration,
    execute_object_storage_setup_registration,
    object_storage_setup_registration_context,
    plan_object_storage_setup_registration,
    revert_object_storage_setup_registration,
    validate_object_storage_setup_evidence,
)
from wom_kit.object_storage_preservation import (
    ObjectStoragePreservationError,
    _plan_core as plan_bytes_preservation,
)
from wom_kit.object_storage_adoption import (
    ObjectStorageAdoptionError,
    plan_object_storage_formal_adoption,
)


PROVIDER = "cloudflare-r2"
PROFILE_ID = "profile:personal:setup-test"
PROFILE_SLUG = "setup-test"
STORE_REF = "storage:account:setup-test"
BUCKET = "zettel-kasten-setup-test-objets"
ENDPOINT_REF = "provider:endpoint:cloudflare-r2"


class _Native:
    def __init__(self, approved: bool) -> None:
        self.result = (APPROVE_BUTTON_ID, True) if approved else (2, False)
        self.calls = 0

    def show(self, **_kwargs):
        self.calls += 1
        return self.result


class _KeyProvider:
    def __init__(self) -> None:
        self.calls = 0

    def use_key(self, _root, consumer, *, create_if_missing=False):
        self.calls += 1
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = b"\0" * len(key)


def _authority(seed: str = "a") -> ExactOperationApprovalAuthority:
    return ExactOperationApprovalAuthority.from_reference(
        {
            "schema_version": "wom-kit/exact-human-approval-reference/v0.1",
            "approval_id": "approval_" + seed * 32,
            "context_sha256": "sha256:" + "b" * 64,
            "approval_authority_sha256": "sha256:" + "c" * 64,
            "one_use": True,
        }
    )


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ObjectStorageSetupRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text(
            "archive_id: archive:test:object-storage-setup\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def kwargs(self) -> dict:
        return {
            "provider": PROVIDER,
            "profile_id": PROFILE_ID,
            "profile_slug": PROFILE_SLUG,
            "storage_account_ref": STORE_REF,
            "bucket_name": BUCKET,
            "endpoint_ref": ENDPOINT_REF,
        }

    def plan(self):
        return plan_object_storage_setup_registration(self.root, **self.kwargs())

    def run_cli(self, arguments: list[str]) -> tuple[int, str]:
        stream = io.StringIO()
        with redirect_stdout(stream), redirect_stderr(stream):
            code = cli_main(arguments)
        return code, stream.getvalue()

    def install_historical_bridge(self, *, mismatch: bool = False) -> None:
        archive_id = archive_services.read_archive_id(self.root)
        binding = archive_services.build_object_storage_provider_binding(
            archive_id=archive_id,
            profile_id=PROFILE_ID,
            profile_slug=PROFILE_SLUG,
            provider_kind=PROVIDER,
            storage_account_ref=STORE_REF,
            bucket_name=BUCKET,
            region="auto",
            endpoint_ref=ENDPOINT_REF,
            objet_prefix=f"archives/{archive_id}/objets/",
            visibility="private",
        )
        provider = {
            "version": "provider-bindings/v0.1",
            "archive_id": archive_id,
            "bindings": [binding],
        }
        (self.root / "provider-bindings.yml").write_text(
            archive_services.dump_yaml(provider), encoding="utf-8"
        )
        receipt_relative = archive_services.object_storage_provider_setup_receipt_path(
            BUCKET
        )
        receipt = archive_services.build_object_storage_provider_setup_receipt(
            archive_id=archive_id,
            profile_id=PROFILE_ID,
            profile_slug=PROFILE_SLUG,
            provider_kind=PROVIDER,
            storage_account_ref=STORE_REF,
            bucket_name=("wrong-bucket" if mismatch else BUCKET),
            region="auto",
            endpoint_ref=ENDPOINT_REF,
            objet_prefix=f"archives/{archive_id}/objets/",
            visibility="private",
            receipt_path=receipt_relative,
            reviewed_by="person:test-reviewer",
            timestamp="2026-08-25T00:00:00+09:00",
            dry_run=False,
            manual_steps=[],
        )
        path = self.root / receipt_relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(receipt, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def test_dry_run_is_stable_content_free_and_writes_nothing(self) -> None:
        before = _snapshot(self.root)
        first = self.plan().public_document()
        second = self.plan().public_document()
        self.assertEqual(first, second)
        self.assertEqual(_snapshot(self.root), before)
        rendered = json.dumps(first, sort_keys=True)
        for private in (BUCKET, STORE_REF, ENDPOINT_REF, str(self.root)):
            self.assertNotIn(private, rendered)
        self.assertFalse(first["closed_actions"]["provider_api_called"])
        self.assertFalse(first["closed_actions"]["bucket_created"])
        self.assertFalse(first["closed_actions"]["bucket_verified"])
        self.assertFalse(first["closed_actions"]["credential_value_read"])

    def test_cli_help_marks_profile_id_required_and_hides_legacy_local_profile(
        self,
    ) -> None:
        code, output = self.run_cli(["object-storage", "--help"])
        normalized = " ".join(output.split())

        self.assertEqual(code, 0, output)
        self.assertIn("--profile-id PROFILE_ID", output)
        self.assertNotIn("[--profile-id PROFILE_ID]", output)
        self.assertIn("profile-resolve", normalized)
        self.assertIn("profiles/wom-profiles.yml", normalized)
        self.assertIn("does not create a registry", normalized)
        self.assertNotIn("--write-local-profile", output)

    def test_cli_missing_profile_id_uses_standard_error_envelope(self) -> None:
        code, output = self.run_cli(
            [
                "object-storage",
                str(self.root),
                "--dry-run",
                "--provider",
                PROVIDER,
                "--storage-account-ref",
                STORE_REF,
                "--format",
                "json",
            ]
        )

        self.assertEqual(code, 2, output)
        result = json.loads(output)
        self.assertEqual(result["schema"], "wom-kit/cli-error/v0.1")
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["status_class"], "blocked")
        self.assertEqual(result["command"], "object-storage")
        self.assertEqual(result["lifecycle_action"], "cli_argument_validation")
        self.assertEqual(result["error_class"], "usage")
        self.assertEqual(result["reason_codes"], ["cli_required_arguments_missing"])
        self.assertEqual(result["exit_code"], 2)
        self.assertEqual(result["effects_state"], "none")
        self.assertEqual(result["files_written"], [])
        self.assertEqual(result["missing_arguments"], ["--profile-id"])
        self.assertFalse(result["private_values_echoed"])

    def test_hidden_local_profile_tombstone_rejects_dry_run_and_approve_before_plan(
        self,
    ) -> None:
        base = [
            "object-storage",
            str(self.root),
            "--provider",
            PROVIDER,
            "--profile-id",
            PROFILE_ID,
            "--profile-slug",
            PROFILE_SLUG,
            "--storage-account-ref",
            STORE_REF,
            "--write-local-profile",
            "--format",
            "json",
        ]
        before = _snapshot(self.root)

        for mode in (
            ["--dry-run"],
            ["--approve", "--reviewed-by", "person:test"],
        ):
            with self.subTest(mode=mode[0]), mock.patch.object(
                setup_registration_module,
                "plan_object_storage_setup_registration",
                side_effect=AssertionError("legacy flag must stop before planning"),
            ) as planner:
                code, output = self.run_cli(base + mode)

            self.assertEqual(code, 1, output)
            result = json.loads(output)
            self.assertEqual(result["schema"], "wom-kit/cli-error/v0.1")
            self.assertEqual(result["state"], "blocked")
            self.assertEqual(result["status_class"], "blocked")
            self.assertEqual(result["command"], "object-storage")
            self.assertEqual(result["error_class"], "policy")
            self.assertEqual(
                result["reason_codes"],
                ["object_storage_setup_registration_local_profile_unsupported"],
            )
            self.assertEqual(
                result["reason_code"],
                "object_storage_setup_registration_local_profile_unsupported",
            )
            self.assertEqual(result["exit_code"], 1)
            self.assertEqual(result["effects_state"], "none")
            self.assertEqual(result["files_written"], [])
            self.assertEqual(result["missing_arguments"], [])
            self.assertFalse(result["private_values_echoed"])
            self.assertEqual(planner.call_count, 0)
            self.assertEqual(_snapshot(self.root), before)

    def test_cli_hash_is_optional_expert_binding_and_local_profile_is_closed(self) -> None:
        base = [
            "object-storage",
            str(self.root),
            "--provider",
            PROVIDER,
            "--profile-id",
            PROFILE_ID,
            "--profile-slug",
            PROFILE_SLUG,
            "--storage-account-ref",
            STORE_REF,
            "--bucket-name",
            BUCKET,
            "--endpoint-ref",
            ENDPOINT_REF,
            "--format",
            "json",
        ]
        before = _snapshot(self.root)
        code, output = self.run_cli(base + ["--dry-run"])
        self.assertEqual(code, 0, output)
        dry = json.loads(output)
        self.assertEqual(dry["lifecycle_action"], "object_storage_setup_registration")
        self.assertEqual(_snapshot(self.root), before)

        code, output = self.run_cli(base + ["--approve"])
        self.assertEqual(code, 1, output)
        self.assertEqual(
            json.loads(output)["reason_code"],
            "object_storage_setup_registration_approval_required",
        )

        approved_stub = {
            "ok": True,
            "state": "setup_registration_completed",
            "plan_sha256": dry["plan_sha256"],
            "provider_api_called": False,
            "bucket_created": False,
            "bucket_verified": False,
            "credential_value_read": False,
            "private_values_echoed": False,
        }
        with mock.patch.object(
            setup_registration_module,
            "execute_object_storage_setup_registration",
            return_value=approved_stub,
        ) as execute:
            code, output = self.run_cli(
                base + ["--approve", "--reviewed-by", "person:test"]
            )
        self.assertEqual(code, 0, output)
        self.assertEqual(json.loads(output), approved_stub)
        self.assertEqual(execute.call_count, 1)

        code, output = self.run_cli(
            base
            + [
                "--approve",
                "--reviewed-by",
                "person:test",
                "--expected-plan-sha256",
                "not-a-digest",
            ]
        )
        self.assertEqual(code, 1, output)
        self.assertEqual(
            json.loads(output)["reason_code"],
            "object_storage_setup_registration_plan_invalid",
        )
        code, output = self.run_cli(
            base
            + [
                "--approve",
                "--reviewed-by",
                "person:test",
                "--expected-plan-sha256",
                "sha256:" + "f" * 64,
            ]
        )
        self.assertEqual(code, 1, output)
        self.assertEqual(
            json.loads(output)["reason_code"],
            "object_storage_setup_registration_plan_changed",
        )
        code, output = self.run_cli(
            base
            + [
                "--approve",
                "--reviewed-by",
                "person:test",
                "--expected-plan-sha256",
                dry["plan_sha256"],
                "--write-local-profile",
            ]
        )
        self.assertEqual(code, 1, output)
        self.assertEqual(
            json.loads(output)["reason_code"],
            "object_storage_setup_registration_local_profile_unsupported",
        )
        self.assertEqual(_snapshot(self.root), before)

    def test_native_cancel_has_zero_effects(self) -> None:
        plan = self.plan()
        context = object_storage_setup_registration_context(
            plan, reviewer_claim="person:test"
        )
        before = _snapshot(self.root)
        key_provider = _KeyProvider()
        writer_calls = 0

        def writer(_claim):
            nonlocal writer_calls
            writer_calls += 1
            return {"ok": True}

        with self.assertRaises(ExactHumanApprovalWorkflowError) as captured:
            _execute_exact_human_approved_write_core(
                self.root,
                context,
                writer,
                native=_Native(False),
                key_provider=key_provider,
            )
        self.assertEqual(captured.exception.code, "exact_human_approval_cancelled")
        self.assertEqual(key_provider.calls, 0)
        self.assertEqual(writer_calls, 0)
        self.assertEqual(_snapshot(self.root), before)

    def test_execute_uses_one_native_decision_then_exact_writer(self) -> None:
        plan = self.plan()
        native = _Native(True)
        key_provider = _KeyProvider()

        def injected(root, context, writer):
            return _execute_exact_human_approved_write_core(
                root,
                context,
                writer,
                native=native,
                key_provider=key_provider,
            )

        with mock.patch.object(
            setup_registration_module,
            "_execute_exact_human_approved_write",
            side_effect=injected,
        ), mock.patch.object(
            archive_services,
            "_object_storage_resolve_transport",
            side_effect=AssertionError("setup registration must not create a transport"),
        ) as transport_factory:
            result = execute_object_storage_setup_registration(
                plan, reviewer_claim="person:test"
            )
        self.assertTrue(result["ok"], result)
        self.assertEqual(
            result["counts"],
            {
                "provider_binding_field_change_count": 1,
                "setup_receipt_create_count": 1,
                "exact_manifest_item_count": 2,
            },
        )
        self.assertEqual(native.calls, 1)
        self.assertEqual(key_provider.calls, 1)
        self.assertEqual(transport_factory.call_count, 0)
        self.assertFalse(
            (
                self.root
                / "profiles"
                / "local"
                / "object-storage-accounts.local.yml"
            ).exists()
        )
        self.assertEqual(
            validate_object_storage_setup_evidence(
                self.root, provider_kind=PROVIDER, store_ref=STORE_REF
            ).mode,
            "exact_registration_v1",
        )

    def test_success_text_reports_actual_local_registration_counts(self) -> None:
        native = _Native(True)
        key_provider = _KeyProvider()

        def injected(root, context, writer):
            return _execute_exact_human_approved_write_core(
                root,
                context,
                writer,
                native=native,
                key_provider=key_provider,
            )

        with mock.patch.object(
            setup_registration_module,
            "_execute_exact_human_approved_write",
            side_effect=injected,
        ):
            code, output = self.run_cli(
                [
                    "object-storage",
                    str(self.root),
                    "--provider",
                    PROVIDER,
                    "--profile-id",
                    PROFILE_ID,
                    "--profile-slug",
                    PROFILE_SLUG,
                    "--storage-account-ref",
                    STORE_REF,
                    "--bucket-name",
                    BUCKET,
                    "--endpoint-ref",
                    ENDPOINT_REF,
                    "--approve",
                    "--reviewed-by",
                    "person:test",
                    "--format",
                    "text",
                ]
            )

        self.assertEqual(code, 0, output)
        self.assertIn("Provider binding changes: 1", output)
        self.assertIn("Setup receipts to create: 1", output)
        self.assertNotIn("Provider binding changes: 0", output)
        self.assertNotIn("Setup receipts to create: 0", output)

    def test_apply_preserves_unrelated_binding_and_revert_restores_exact_bytes(self) -> None:
        unrelated = {
            "binding_id": "github:test:unrelated",
            "provider": "github",
            "enabled": True,
            "resource": {"owner": "unrelated", "repo": "unrelated"},
        }
        provider_path = self.root / "provider-bindings.yml"
        provider_path.write_text(
            archive_services.dump_yaml(
                {
                    "version": "provider-bindings/v0.1",
                    "archive_id": archive_services.read_archive_id(self.root),
                    "bindings": [unrelated],
                }
            ),
            encoding="utf-8",
        )
        original = provider_path.read_bytes()
        plan = self.plan()
        result = apply_object_storage_setup_registration(
            plan, approval_authority=_authority()
        )
        self.assertTrue(result["ok"], result)
        document = archive_services.load_yaml(provider_path.read_text(encoding="utf-8"))
        self.assertEqual(document["bindings"][0], unrelated)
        self.assertEqual(len(document["bindings"]), 2)
        evidence = validate_object_storage_setup_evidence(
            self.root, provider_kind=PROVIDER, store_ref=STORE_REF
        )
        self.assertEqual(evidence.mode, "exact_registration_v1")
        rendered = json.dumps(result, sort_keys=True)
        for private in (BUCKET, STORE_REF, ENDPOINT_REF, str(self.root)):
            self.assertNotIn(private, rendered)

        reverted = revert_object_storage_setup_registration(
            plan, approval_authority=_authority("d")
        )
        self.assertEqual(reverted["status"], "completed")
        self.assertEqual(provider_path.read_bytes(), original)
        with self.assertRaises(ObjectStorageSetupRegistrationError) as captured:
            validate_object_storage_setup_evidence(
                self.root, provider_kind=PROVIDER, store_ref=STORE_REF
            )
        self.assertEqual(captured.exception.code, "object_storage_setup_evidence_missing")

    def test_registration_is_create_only_and_never_reconfigures_a_related_binding(self) -> None:
        archive_id = archive_services.read_archive_id(self.root)
        existing = archive_services.build_object_storage_provider_binding(
            archive_id=archive_id,
            profile_id=PROFILE_ID,
            profile_slug=PROFILE_SLUG,
            provider_kind=PROVIDER,
            storage_account_ref=STORE_REF,
            bucket_name="zettel-kasten-existing-setup-objets",
            region="auto",
            endpoint_ref=ENDPOINT_REF,
            objet_prefix=f"archives/{archive_id}/objets/",
            visibility="private",
        )
        provider_path = self.root / "provider-bindings.yml"
        provider_path.write_text(
            archive_services.dump_yaml(
                {
                    "version": "provider-bindings/v0.1",
                    "archive_id": archive_id,
                    "bindings": [existing],
                }
            ),
            encoding="utf-8",
        )
        before = _snapshot(self.root)

        with self.assertRaises(ObjectStorageSetupRegistrationError) as captured:
            self.plan()

        self.assertEqual(
            captured.exception.code,
            "object_storage_setup_registration_collision",
        )
        self.assertEqual(_snapshot(self.root), before)

    def test_exact_evidence_is_target_scoped_not_invalidated_by_unrelated_bindings(self) -> None:
        unrelated = {
            "binding_id": "github:test:unrelated",
            "provider": "github",
            "enabled": True,
            "resource": {"owner": "unrelated", "repo": "unrelated"},
        }
        provider_path = self.root / "provider-bindings.yml"
        provider_path.write_text(
            archive_services.dump_yaml(
                {
                    "version": "provider-bindings/v0.1",
                    "archive_id": archive_services.read_archive_id(self.root),
                    "bindings": [unrelated],
                }
            ),
            encoding="utf-8",
        )
        plan = self.plan()
        apply_object_storage_setup_registration(
            plan, approval_authority=_authority()
        )
        document = archive_services.load_yaml(
            provider_path.read_text(encoding="utf-8")
        )
        document["bindings"][0]["resource"]["repo"] = "unrelated-later-change"
        provider_path.write_text(
            archive_services.dump_yaml(document), encoding="utf-8"
        )

        evidence = validate_object_storage_setup_evidence(
            self.root, provider_kind=PROVIDER, store_ref=STORE_REF
        )

        self.assertEqual(evidence.mode, "exact_registration_v1")

    def test_drift_and_receipt_collision_fail_closed(self) -> None:
        plan = self.plan()
        (self.root / "provider-bindings.yml").write_text(
            "version: provider-bindings/v0.1\narchive_id: archive:test:object-storage-setup\nbindings: []\nextra: drift\n",
            encoding="utf-8",
        )
        with self.assertRaises(Exception):
            apply_object_storage_setup_registration(
                plan, approval_authority=_authority()
            )

        self.root.joinpath("provider-bindings.yml").unlink()
        plan = self.plan()
        receipt = self.root / plan.receipt_relative
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_bytes(b"{}\n")
        with self.assertRaises(ObjectStorageSetupRegistrationError) as captured:
            self.plan()
        self.assertEqual(
            captured.exception.code,
            "object_storage_setup_registration_receipt_collision",
        )

    def test_resume_after_provider_checkpoint_completes_receipt(self) -> None:
        plan = self.plan()
        original = _Writer.write_field
        interrupted = {"done": False}

        def fail_once(writer, **kwargs):
            if kwargs["field_ref"] == "receipt_bytes" and not interrupted["done"]:
                interrupted["done"] = True
                raise RuntimeError("synthetic interruption")
            return original(writer, **kwargs)

        with mock.patch.object(_Writer, "write_field", new=fail_once):
            with self.assertRaises(Exception):
                apply_object_storage_setup_registration(
                    plan, approval_authority=_authority()
                )
        result = apply_object_storage_setup_registration(
            plan, approval_authority=_authority(), resume=True
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(
            validate_object_storage_setup_evidence(
                self.root, provider_kind=PROVIDER, store_ref=STORE_REF
            ).mode,
            "exact_registration_v1",
        )

    def test_setup_gate_missing_mismatch_and_strict_historical_bridge(self) -> None:
        with self.assertRaises(ObjectStorageSetupRegistrationError) as missing:
            validate_object_storage_setup_evidence(
                self.root, provider_kind=PROVIDER, store_ref=STORE_REF
            )
        self.assertEqual(missing.exception.code, "object_storage_setup_evidence_missing")

        self.install_historical_bridge(mismatch=True)
        with self.assertRaises(ObjectStorageSetupRegistrationError) as mismatch:
            validate_object_storage_setup_evidence(
                self.root, provider_kind=PROVIDER, store_ref=STORE_REF
            )
        self.assertEqual(mismatch.exception.code, "object_storage_setup_evidence_mismatch")

        for path in (self.root / "receipts" / "providers").glob("*.json"):
            path.unlink()
        self.install_historical_bridge(mismatch=False)
        evidence = validate_object_storage_setup_evidence(
            self.root, provider_kind=PROVIDER, store_ref=STORE_REF
        )
        self.assertEqual(evidence.mode, "strict_historical_bridge")
        public = evidence.public_document()
        self.assertFalse(public["provider_api_called"])
        self.assertFalse(public["bucket_verified"])
        rendered = json.dumps(public, sort_keys=True)
        self.assertNotIn(BUCKET, rendered)
        self.assertNotIn(STORE_REF, rendered)

    def test_provider_status_and_readiness_use_exact_content_free_evidence(self) -> None:
        plan = self.plan()
        applied = apply_object_storage_setup_registration(
            plan, approval_authority=_authority()
        )
        self.assertTrue(applied["ok"], applied)
        before = _snapshot(self.root)

        status = archive_services.provider_setup_status(self.root)
        readiness = archive_services.object_storage_adapter_readiness_plan(
            self.root, dry_run=True
        )
        private_selector_readiness = (
            archive_services.object_storage_adapter_readiness_plan(
                self.root,
                provider_ref=str(plan.proposed_binding["binding_id"]),
                dry_run=True,
            )
        )

        self.assertEqual(_snapshot(self.root), before)
        self.assertTrue(status["ok"], status)
        self.assertEqual(status["status"], "ready")
        self.assertEqual(status["receipt_count"], 1)
        item = next(
            row
            for row in status["providers"]
            if row.get("provider") == "object_storage"
        )
        self.assertEqual(item["status"], "metadata_and_receipt_present")
        self.assertEqual(item["reason_code"], "object_storage_setup_evidence_valid")
        self.assertEqual(item["setup_evidence_mode"], "exact_registration_v1")
        self.assertTrue(item["setup_receipt_present"])
        self.assertRegex(item["provider_binding_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(item["receipt_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(item["binding_ref_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertIsNone(item["binding_id"])
        self.assertEqual(item["resource"], {})
        self.assertIsNone(item["expected_receipt_path"])
        self.assertIsNone(item["receipt_path"])
        self.assertFalse(item["private_values_echoed"])
        self.assertFalse(item["resource_details_echoed"])
        self.assertFalse(item["receipt_path_echoed"])

        self.assertTrue(readiness["ok"], readiness)
        self.assertEqual(readiness["readiness_state"], "ready_for_future_adapter")
        summary = readiness["provider_summary"]
        self.assertTrue(summary["selected_provider_setup_ready"])
        self.assertTrue(summary["selected_provider_setup_receipt_present"])
        self.assertFalse(readiness["closed_actions"]["provider_api_called"])
        self.assertFalse(readiness["closed_actions"]["credential_value_read"])
        self.assertEqual(readiness["would_change"], [])
        self.assertTrue(private_selector_readiness["ok"], private_selector_readiness)
        self.assertTrue(private_selector_readiness["provider_ref_supplied"])

        rendered = json.dumps(
            {
                "status": status,
                "readiness": readiness,
                "private_selector_readiness": private_selector_readiness,
            },
            sort_keys=True,
        )
        for private in (
            BUCKET,
            STORE_REF,
            ENDPOINT_REF,
            PROFILE_ID,
            PROFILE_SLUG,
            plan.receipt_relative,
            archive_services.OBJECT_STORAGE_PROVIDER_TOKEN_ENVS[PROVIDER],
            str(self.root),
        ):
            self.assertNotIn(private, rendered)

    def test_malformed_exact_receipt_never_falls_back_or_echoes_private_values(
        self,
    ) -> None:
        self.install_historical_bridge(mismatch=False)
        legacy_path = next(
            (self.root / "receipts" / "providers").glob(
                "*.object-storage-setup.json"
            )
        )
        plan = self.plan()
        applied = apply_object_storage_setup_registration(
            plan, approval_authority=_authority()
        )
        self.assertTrue(applied["ok"], applied)

        secret_sentinel = "provider-private-secret-sentinel"
        exact_path = self.root / plan.receipt_relative
        exact_path.write_text(
            json.dumps({"secret": secret_sentinel}) + "\n",
            encoding="utf-8",
        )
        nonstandard_legacy = legacy_path.with_name("nonstandard-private.json")
        nonstandard_document = json.loads(legacy_path.read_text(encoding="utf-8"))
        nonstandard_document["provider_private_scalar"] = secret_sentinel
        nonstandard_legacy.write_text(
            json.dumps(nonstandard_document, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        before = _snapshot(self.root)

        status = archive_services.provider_setup_status(self.root)
        readiness = archive_services.object_storage_adapter_readiness_plan(
            self.root, dry_run=True
        )

        self.assertEqual(_snapshot(self.root), before)
        self.assertFalse(status["ok"], status)
        self.assertEqual(status["status"], "blocked")
        item = next(
            row
            for row in status["providers"]
            if row.get("provider") == "object_storage"
        )
        self.assertEqual(item["status"], "metadata_receipt_mismatch")
        self.assertEqual(
            item["reason_code"], "object_storage_setup_evidence_mismatch"
        )
        self.assertEqual(
            item["blockers"], ["object_storage_setup_evidence_mismatch"]
        )
        self.assertIsNone(item["setup_evidence_mode"])
        self.assertFalse(item["setup_receipt_present"])
        self.assertIsNone(item["receipt_sha256"])
        self.assertFalse(readiness["ok"], readiness)
        self.assertIn(
            "object_storage_setup_evidence_mismatch", readiness["blockers"]
        )
        self.assertIn(
            "object_storage_provider_setup_not_ready", readiness["blockers"]
        )
        self.assertFalse(readiness["closed_actions"]["provider_api_called"])
        self.assertFalse(readiness["closed_actions"]["credential_value_read"])

        rendered = json.dumps(
            {"status": status, "readiness": readiness}, sort_keys=True
        )
        for private in (
            BUCKET,
            STORE_REF,
            ENDPOINT_REF,
            PROFILE_ID,
            PROFILE_SLUG,
            secret_sentinel,
            plan.receipt_relative,
            legacy_path.relative_to(self.root).as_posix(),
            nonstandard_legacy.relative_to(self.root).as_posix(),
            str(self.root),
        ):
            self.assertNotIn(private, rendered)
        self.assertNotIn("strict_historical_bridge", rendered)

    def test_historical_bridge_rejects_incomplete_or_extended_receipts(self) -> None:
        self.install_historical_bridge(mismatch=False)
        receipt_path = next(
            (self.root / "receipts" / "providers").glob(
                "*.object-storage-setup.json"
            )
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt.pop("receipt_path")
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(ObjectStorageSetupRegistrationError) as incomplete:
            validate_object_storage_setup_evidence(
                self.root, provider_kind=PROVIDER, store_ref=STORE_REF
            )
        self.assertEqual(
            incomplete.exception.code,
            "object_storage_setup_evidence_mismatch",
        )

        receipt["receipt_path"] = archive_services.object_storage_provider_setup_receipt_path(
            BUCKET
        )
        receipt["unreviewed_extension"] = True
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(ObjectStorageSetupRegistrationError) as extended:
            validate_object_storage_setup_evidence(
                self.root, provider_kind=PROVIDER, store_ref=STORE_REF
            )
        self.assertEqual(
            extended.exception.code,
            "object_storage_setup_evidence_mismatch",
        )

    def test_recovery_planners_stop_at_setup_gate_before_other_inputs(self) -> None:
        with self.assertRaises(ObjectStoragePreservationError) as preservation:
            plan_bytes_preservation(
                self.root, provider_kind=PROVIDER, store_ref=STORE_REF
            )
        self.assertEqual(
            preservation.exception.code,
            "object_storage_preservation_setup_evidence_missing",
        )
        deliberately_missing_map = self.root / "must-not-be-read-before-setup.jsonl"
        with self.assertRaises(ObjectStorageAdoptionError) as adoption:
            plan_object_storage_formal_adoption(
                self.root,
                key_map_path=deliberately_missing_map,
                provider_kind=PROVIDER,
                store_ref=STORE_REF,
            )
        self.assertEqual(
            adoption.exception.code,
            "object_storage_adoption_setup_evidence_missing",
        )

        self.install_historical_bridge(mismatch=False)
        manifest = self.root / "objects" / "manifests" / "files.jsonl"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        raw = b"historical-bridge-local-object"
        digest = hashlib.sha256(raw).hexdigest()
        relative = f"objects/by-sha256/{digest[:2]}/{digest}"
        object_path = self.root / relative
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(raw)
        manifest.write_text(
            json.dumps(
                {
                    "object_id": "sha256:" + digest,
                    "sha256": digest,
                    "logical_key": "test/historical-bridge",
                    "mime": "application/octet-stream",
                    "size_bytes": len(raw),
                    "locations": [
                        {
                            "provider": "local",
                            "availability": "available",
                            "path": relative,
                        }
                    ],
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        preservation_plan = plan_bytes_preservation(
            self.root, provider_kind=PROVIDER, store_ref=STORE_REF
        )
        self.assertEqual(preservation_plan.archive_id, archive_services.read_archive_id(self.root))


if __name__ == "__main__":
    unittest.main()
