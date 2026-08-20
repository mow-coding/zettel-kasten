from __future__ import annotations

import ctypes
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from wom_kit.credential_secure_intake import (
    HumanSecretInputResult,
    VerifiedCredentialIdentity,
    create_secure_intake_plan,
)
from wom_kit import credential_secure_intake_windows as windows_module
from wom_kit.credential_secure_intake_windows import (
    _CtypesWindowsNativeFacade as CtypesWindowsNativeFacade,
    CredentialPopupPromptContext,
    WindowsAttachedConsoleSecretUI,
    _WindowsCredentialPopupSecretUI as WindowsCredentialPopupSecretUI,
    WindowsDllBundle,
    WindowsNativeMaskedSecretUI,
    WindowsVisibleConsoleSecretUI,
    WindowsSecureIntakeError,
    _build_windows_secure_intake_worker as build_windows_secure_intake_worker,
    current_windows_owner_binding,
    windows_credential_target,
)
from wom_kit.credential_popup_windows import (
    CredentialPopupInputIntent,
    CredentialPopupSecretPromptError,
)


NOW = datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)
ANCHOR = "95452f0d-28ca-4911-892b-b369d6477443"
SID = "S-1-5-21-111111111-222222222-333333333-1001"
OWNER = f"windows-sid:{SID}"
SYNTHETIC_SECRET = b"synthetic-notion-value-never-from-os"
MASTER_KEY = b"synthetic-master-key-used-only-by-unit-tests-0001"
REQUEST_ID = "intake_abcdef1234567890"
CREDENTIAL_ID = "cred_abcdef1234567890"
BACKEND_ID = "backend_abcdef1234567890"
ARCHIVE_SCOPE_ID = "archive:test"
TARGET = windows_credential_target(ARCHIVE_SCOPE_ID, BACKEND_ID)


@dataclass
class FakeWindowsNative:
    prompt_error: bool = False
    probe_result: Any = True
    sid: str = SID
    calls: list[tuple[str, str]] = field(default_factory=list)
    stored: dict[str, bytes] = field(default_factory=dict, repr=False)
    last_prompt_buffer: bytearray | None = field(default=None, repr=False)

    def prompt_masked_secret(
        self, *, request_id: str, context=None
    ) -> HumanSecretInputResult:
        self.calls.append(("prompt_masked_secret", request_id))
        if self.prompt_error:
            raise RuntimeError(SYNTHETIC_SECRET.decode("ascii"))
        value = bytearray(SYNTHETIC_SECRET)
        self.last_prompt_buffer = value
        return HumanSecretInputResult(
            secret=value,
            credential_input_received=True,
            complete_line_received=True,
            cancelled=False,
        )

    def write_generic(self, target_name: str, secret: memoryview) -> None:
        self.calls.append(("write_generic", target_name))
        self.stored[target_name] = bytes(secret)

    def generic_exists(self, target_name: str) -> Any:
        self.calls.append(("generic_exists", target_name))
        return self.probe_result and target_name in self.stored

    def read_generic_secret_exact(self, target_name: str) -> bytearray:
        self.calls.append(("read_generic_secret_exact", target_name))
        return bytearray(self.stored[target_name])

    def delete_generic(self, target_name: str) -> None:
        self.calls.append(("delete_generic", target_name))
        self.stored.pop(target_name, None)

    def current_user_sid(self) -> str:
        self.calls.append(("current_user_sid", "exact"))
        return self.sid


@dataclass
class FakeVerifier:
    calls: int = 0

    def validate_secret_input(
        self, secret: memoryview, provider: str
    ) -> bool:
        return provider == "notion" and bytes(secret) == SYNTHETIC_SECRET

    def verify_identity(
        self,
        secret: memoryview,
        *,
        provider: str,
        reviewed_anchor_uuid: str,
        provider_request_observer=None,
    ) -> VerifiedCredentialIdentity:
        if provider_request_observer is not None:
            provider_request_observer()
        self.calls += 1
        if bytes(secret) != SYNTHETIC_SECRET:
            raise RuntimeError("unexpected synthetic input")
        return VerifiedCredentialIdentity(
            provider=provider,
            account_subject="provider-account-opaque",
            workspace_identity="provider-workspace-opaque",
            reviewed_anchor_uuid=reviewed_anchor_uuid,
            capabilities=("read_content",),
        )


class FakeFunction:
    def __init__(self, handler):
        self.handler = handler
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.handler(*args)


class FakeDllHarness:
    """Synthetic ctypes DLL surface; no Windows API is called."""

    def __init__(self) -> None:
        self.freed: list[int] = []
        self.written_target = ""
        self.written_blob = b""
        self.written_type: int | None = None
        self.written_persist: int | None = None
        self.deleted_target = ""
        self.blob = (ctypes.c_ubyte * len(SYNTHETIC_SECRET)).from_buffer_copy(
            SYNTHETIC_SECRET
        )
        self.credential = windows_module._CREDENTIALW()
        self.credential.CredentialBlobSize = len(SYNTHETIC_SECRET)
        self.credential.CredentialBlob = ctypes.cast(
            self.blob, ctypes.POINTER(ctypes.c_ubyte)
        )

        def cred_write(credential_pointer, _flags):
            credential = ctypes.cast(
                credential_pointer, ctypes.POINTER(windows_module._CREDENTIALW)
            ).contents
            self.written_target = credential.TargetName
            self.written_type = int(credential.Type)
            self.written_persist = int(credential.Persist)
            self.written_blob = ctypes.string_at(
                credential.CredentialBlob, credential.CredentialBlobSize
            )
            return 1

        def cred_read(_target, _kind, _flags, output_pointer):
            output = ctypes.cast(
                output_pointer, ctypes.POINTER(ctypes.c_void_p)
            )
            output.contents.value = ctypes.addressof(self.credential)
            return 1

        def cred_free(pointer):
            value = ctypes.cast(pointer, ctypes.c_void_p).value
            self.freed.append(int(value or 0))

        def cred_delete(target, _kind, _flags):
            self.deleted_target = target
            return 1

        self.advapi32 = SimpleNamespace(
            CredWriteW=FakeFunction(cred_write),
            CredReadW=FakeFunction(cred_read),
            CredDeleteW=FakeFunction(cred_delete),
            CredFree=FakeFunction(cred_free),
            OpenProcessToken=FakeFunction(lambda *_args: 0),
            GetTokenInformation=FakeFunction(lambda *_args: 0),
            ConvertSidToStringSidW=FakeFunction(lambda *_args: 0),
        )
        self.kernel32 = SimpleNamespace(
            GetCurrentProcess=FakeFunction(lambda: 1),
            CloseHandle=FakeFunction(lambda _handle: 1),
            LocalFree=FakeFunction(lambda _pointer: None),
        )

    def bundle(self) -> WindowsDllBundle:
        return WindowsDllBundle(
            advapi32=self.advapi32,
            kernel32=self.kernel32,
        )


class WindowsSecureIntakeTests(unittest.TestCase):
    def make_plan(self, *, request_id: str = REQUEST_ID):
        return create_secure_intake_plan(
            provider="notion",
            account_label="personal",
            workspace_label="backup",
            purpose="source-recovery",
            reviewed_anchor_uuid=ANCHOR,
            owner_binding=OWNER,
            requested_capabilities=("read-content",),
            ttl_seconds=300,
            now=NOW,
            request_id_factory=lambda: request_id,
        )

    def test_factory_runs_complete_fake_windows_transaction_without_real_os(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claims = root / "claims"
            receipts = root / "receipts"
            native = FakeWindowsNative()
            verifier = FakeVerifier()
            worker = build_windows_secure_intake_worker(
                cli_live_approved=True,
                claims_directory=claims,
                archive_root=root,
                receipt_directory=receipts,
                archive_scope_id=ARCHIVE_SCOPE_ID,
                provider_verifier=verifier,
                fingerprint_master_key=MASTER_KEY,
                native=native,
                credential_id_factory=lambda: CREDENTIAL_ID,
                backend_id_factory=lambda: BACKEND_ID,
                now_factory=lambda: NOW,
            )
            self.assertIsInstance(worker.fingerprint_key, bytearray)
            self.assertTrue(any(worker.fingerprint_key))

            # Construction queries the SID but performs no credential, provider,
            # request-file, or receipt-file operation.
            self.assertEqual(native.calls, [("current_user_sid", "exact")])
            self.assertFalse(claims.exists())
            self.assertFalse(receipts.exists())

            plan = self.make_plan()
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = worker.execute(
                    plan,
                    expected_plan_digest=plan.plan_digest,
                    current_owner_binding=OWNER,
                )

            self.assertTrue(result["ok"], result)
            self.assertTrue(all(value == 0 for value in worker.fingerprint_key))
            self.assertTrue(result["persisted"])
            self.assertEqual(result["credential_id"], CREDENTIAL_ID)
            self.assertEqual(result["encrypted_backend_kind"], "windows_credential_manager_generic")
            self.assertEqual(
                native.calls[1:],
                [
                    ("prompt_masked_secret", REQUEST_ID),
                    ("write_generic", TARGET),
                    ("generic_exists", TARGET),
                ],
            )
            self.assertEqual(verifier.calls, 1)
            self.assertEqual(native.last_prompt_buffer, bytearray(len(SYNTHETIC_SECRET)))
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            rendered = json.dumps(result, sort_keys=True)
            self.assertNotIn(SYNTHETIC_SECRET.decode("ascii"), rendered)
            self.assertNotIn(ANCHOR, rendered)
            self.assertTrue(list(receipts.glob(f"{CREDENTIAL_ID}.json")))

    def test_factory_rejects_non_boolean_presence_and_absence_evidence(self) -> None:
        class FalseyProbe:
            def __bool__(self) -> bool:
                return False

            def __repr__(self) -> str:
                return SYNTHETIC_SECRET.decode("ascii")

        cases = (
            (None, "delete_failed"),
            (0, "delete_failed"),
            (FalseyProbe(), "delete_failed"),
            (False, "deleted"),
        )
        for index, (raw_result, expected_rollback) in enumerate(cases, start=1):
            with self.subTest(
                raw_type=type(raw_result).__name__,
                expected_rollback=expected_rollback,
            ), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                native = FakeWindowsNative(probe_result=raw_result)
                verifier = FakeVerifier()
                worker = build_windows_secure_intake_worker(
                    cli_live_approved=True,
                    claims_directory=root / "claims",
                    archive_root=root,
                    receipt_directory=root / "receipts",
                    archive_scope_id=ARCHIVE_SCOPE_ID,
                    provider_verifier=verifier,
                    fingerprint_master_key=MASTER_KEY,
                    native=native,
                    credential_id_factory=lambda: CREDENTIAL_ID,
                    backend_id_factory=lambda: BACKEND_ID,
                    now_factory=lambda: NOW,
                )
                request_id = f"intake_{index:016d}"
                plan = self.make_plan(request_id=request_id)

                result = worker.execute(
                    plan,
                    expected_plan_digest=plan.plan_digest,
                    current_owner_binding=OWNER,
                )

                self.assertFalse(result["ok"])
                self.assertEqual(
                    result["reason_code"],
                    "store_presence_not_verified",
                )
                self.assertEqual(result["rollback_status"], expected_rollback)
                self.assertEqual(
                    (
                        result["credential_input_received"],
                        result["complete_line_received"],
                        result["temporary_store_write_attempted"],
                        result["provider_request_attempted"],
                    ),
                    (True, True, True, False),
                )
                self.assertEqual(verifier.calls, 0)
                self.assertEqual(
                    native.calls[1:],
                    [
                        ("prompt_masked_secret", request_id),
                        ("write_generic", TARGET),
                        ("generic_exists", TARGET),
                        ("delete_generic", TARGET),
                        ("generic_exists", TARGET),
                    ],
                )
                self.assertEqual(list((root / "receipts").glob("*.json")), [])
                self.assertNotIn(
                    SYNTHETIC_SECRET.decode("ascii"),
                    json.dumps(result, sort_keys=True),
                )

    def test_live_and_platform_guards_fire_before_dll_loading(self) -> None:
        with self.assertRaises(WindowsSecureIntakeError) as approval_error:
            CtypesWindowsNativeFacade(
                cli_live_approved=False,
                platform_name="nt",
                dlls=object(),  # type: ignore[arg-type]
            )
        self.assertEqual(
            approval_error.exception.code, "windows_live_approval_required"
        )

        with self.assertRaises(WindowsSecureIntakeError) as platform_error:
            CtypesWindowsNativeFacade(
                cli_live_approved=True,
                platform_name="posix",
                dlls=object(),  # type: ignore[arg-type]
            )
        self.assertEqual(platform_error.exception.code, "windows_platform_required")

        native = FakeWindowsNative()
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(WindowsSecureIntakeError) as factory_error:
                build_windows_secure_intake_worker(
                    cli_live_approved=False,
                    claims_directory=Path(temporary) / "claims",
                    archive_root=Path(temporary),
                    receipt_directory=Path(temporary) / "receipts",
                    archive_scope_id=ARCHIVE_SCOPE_ID,
                    provider_verifier=FakeVerifier(),
                    fingerprint_master_key=MASTER_KEY,
                    native=native,
                )
        self.assertEqual(factory_error.exception.code, "windows_live_approval_required")
        self.assertEqual(native.calls, [])

    def test_factory_requires_claims_to_be_bound_inside_archive_root(self) -> None:
        native = FakeWindowsNative()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "archive"
            outside = Path(temporary) / "outside"
            root.mkdir()
            outside.mkdir()
            for archive_root, claims_directory in (
                (None, root / "claims"),
                (root, outside / "claims"),
            ):
                with self.subTest(
                    archive_root_present=archive_root is not None
                ), self.assertRaises(WindowsSecureIntakeError) as error:
                    build_windows_secure_intake_worker(
                        cli_live_approved=True,
                        claims_directory=claims_directory,
                        archive_root=archive_root,
                        receipt_directory=root / "receipts",
                        archive_scope_id=ARCHIVE_SCOPE_ID,
                        provider_verifier=FakeVerifier(),
                        fingerprint_master_key=MASTER_KEY,
                        native=native,
                    )
                self.assertEqual(
                    error.exception.code,
                    "windows_claims_authority_invalid",
                )
            self.assertEqual(native.calls, [])
            self.assertEqual(list(outside.iterdir()), [])

    def test_ctypes_fake_dll_popup_write_probe_read_and_delete_are_exact(self) -> None:
        self.assertRegex(
            TARGET,
            r"^WOM/credential-intake/[0-9a-f]{64}/backend_[A-Za-z0-9_-]+$",
        )
        self.assertNotIn(ARCHIVE_SCOPE_ID, TARGET)
        harness = FakeDllHarness()
        prompted_request_ids: list[str] = []

        def fake_popup_prompt(
            *, request_id: str, input_intent: object, **_kwargs: object
        ) -> HumanSecretInputResult:
            prompted_request_ids.append(request_id)
            self.assertIs(
                input_intent,
                CredentialPopupInputIntent.live_registration,
            )
            return HumanSecretInputResult(
                secret=bytearray(SYNTHETIC_SECRET),
                credential_input_received=True,
                complete_line_received=True,
                cancelled=False,
            )

        native = CtypesWindowsNativeFacade(
            cli_live_approved=True,
            platform_name="nt",
            dlls=harness.bundle(),
            popup_prompt=fake_popup_prompt,
        )

        prompt_context = CredentialPopupPromptContext(
            provider="notion",
            purpose="notion_page_recovery",
            account_label="개인 계정",
            workspace_label="자료 보관함",
            task_summary="검토한 Notion 페이지를 WOM 아카이브로 복구하고 있습니다.",
            connection_reason="복구를 계속하려면 Notion 작업공간 연결을 확인해야 합니다.",
        )
        prompted = native.prompt_masked_secret(
            request_id=REQUEST_ID,
            context=prompt_context,
        )
        self.assertEqual(prompted.secret, bytearray(SYNTHETIC_SECRET))
        self.assertTrue(prompted.credential_input_received)
        self.assertTrue(prompted.complete_line_received)
        self.assertFalse(prompted.cancelled)
        self.assertEqual(prompted_request_ids, [REQUEST_ID])

        write_buffer = bytearray(SYNTHETIC_SECRET)
        native.write_generic(TARGET, memoryview(write_buffer))
        self.assertEqual(harness.written_target, TARGET)
        self.assertEqual(harness.written_blob, SYNTHETIC_SECRET)
        self.assertEqual(harness.written_type, windows_module.CRED_TYPE_GENERIC)
        self.assertEqual(
            harness.written_persist,
            windows_module.CRED_PERSIST_LOCAL_MACHINE,
        )

        self.assertTrue(native.generic_exists(TARGET))
        read_buffer = native.read_generic_secret_exact(TARGET)
        self.assertEqual(read_buffer, bytearray(SYNTHETIC_SECRET))
        self.assertEqual(len(harness.freed), 2)

        native.delete_generic(TARGET)
        self.assertEqual(harness.deleted_target, TARGET)
        self.assertFalse(hasattr(native, "enumerate"))
        self.assertFalse(hasattr(native, "search"))
        self.assertFalse(hasattr(native, "fuzzy_match"))
        self.assertIn("popup=True", repr(native))
        self.assertNotIn("attached_console=True", repr(native))
        self.assertNotIn("visible_console=True", repr(native))
        self.assertNotIn(SYNTHETIC_SECRET.decode("ascii"), repr(native))

        # A trusted broker/provider callback owns and wipes the mutable exact
        # read buffer.  No decoded immutable string is required by this module.
        for index in range(len(read_buffer)):
            read_buffer[index] = 0
        assert prompted.secret is not None
        for index in range(len(prompted.secret)):
            prompted.secret[index] = 0

    def test_production_facade_routes_input_to_native_popup_boundary(self) -> None:
        harness = FakeDllHarness()
        prompted = HumanSecretInputResult(
            secret=bytearray(SYNTHETIC_SECRET),
            credential_input_received=True,
            complete_line_received=True,
            cancelled=False,
        )
        with patch.object(
            windows_module,
            "_prompt_secret_in_native_popup",
            return_value=prompted,
        ) as popup_prompt:
            native = CtypesWindowsNativeFacade(
                cli_live_approved=True,
                platform_name="nt",
                dlls=harness.bundle(),
            )
            prompt_context = CredentialPopupPromptContext(
                provider="notion",
                purpose="notion_page_recovery",
                account_label="개인 계정",
                workspace_label="자료 보관함",
                task_summary="검토한 Notion 페이지를 WOM 아카이브로 복구하고 있습니다.",
                connection_reason="복구를 계속하려면 Notion 작업공간 연결을 확인해야 합니다.",
            )
            result = native.prompt_masked_secret(
                request_id=REQUEST_ID,
                context=prompt_context,
            )

        self.assertIs(result, prompted)
        popup_prompt.assert_called_once_with(
            request_id=REQUEST_ID,
            context=prompt_context,
            input_intent=CredentialPopupInputIntent.live_registration,
            kernel32=harness.kernel32,
            platform_name="nt",
            max_secret_bytes=windows_module.CRED_MAX_CREDENTIAL_BLOB_SIZE,
        )
        self.assertFalse(hasattr(harness, "credui"))
        self.assertFalse(
            hasattr(windows_module, "prompt_masked_secret_in_attached_console")
        )

    def test_all_production_ui_names_are_native_popup_aliases(
        self,
    ) -> None:
        self.assertIs(
            WindowsVisibleConsoleSecretUI,
            WindowsCredentialPopupSecretUI,
        )
        self.assertIs(
            WindowsNativeMaskedSecretUI,
            WindowsCredentialPopupSecretUI,
        )
        self.assertIs(
            WindowsAttachedConsoleSecretUI,
            WindowsCredentialPopupSecretUI,
        )
        self.assertIs(
            windows_module.VisibleConsolePromptContext,
            CredentialPopupPromptContext,
        )

    def test_popup_evidence_error_survives_facade_and_ui_boundaries(
        self,
    ) -> None:
        expected = (True, False)

        def fail_after_partial_input(**_kwargs: object) -> HumanSecretInputResult:
            raise CredentialPopupSecretPromptError(
                reason_code="credential_input_boundary_failed",
                credential_input_received=expected[0],
                complete_line_received=expected[1],
            )

        native = CtypesWindowsNativeFacade(
            cli_live_approved=True,
            platform_name="nt",
            dlls=FakeDllHarness().bundle(),
            popup_prompt=fail_after_partial_input,
        )
        context = CredentialPopupPromptContext(
            provider="notion",
            purpose="notion_page_recovery",
            account_label="개인 계정",
            workspace_label="자료 보관함",
            task_summary="검토한 Notion 페이지를 WOM 아카이브로 복구하고 있습니다.",
            connection_reason="복구를 계속하려면 Notion 작업공간 연결을 확인해야 합니다.",
        )
        ui = WindowsCredentialPopupSecretUI(native, context)

        with self.assertRaises(CredentialPopupSecretPromptError) as error:
            ui.request_secret(request_id=REQUEST_ID)

        self.assertEqual(
            (
                error.exception.credential_input_received,
                error.exception.complete_line_received,
            ),
            expected,
        )
        rendered = str(error.exception) + repr(error.exception) + repr(ui)
        self.assertNotIn(SYNTHETIC_SECRET.decode("ascii"), rendered)

    def test_overlimit_popup_projects_invalid_1100_before_store_or_provider(
        self,
    ) -> None:
        def fail_after_complete_input(**_kwargs: object) -> HumanSecretInputResult:
            raise CredentialPopupSecretPromptError(
                reason_code="credential_input_invalid_for_provider",
                credential_input_received=True,
                complete_line_received=True,
            )

        harness = FakeDllHarness()
        native = CtypesWindowsNativeFacade(
            cli_live_approved=True,
            platform_name="nt",
            dlls=harness.bundle(),
            popup_prompt=fail_after_complete_input,
        )
        native.current_user_sid = lambda: SID  # type: ignore[method-assign]
        verifier = FakeVerifier()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worker = build_windows_secure_intake_worker(
                cli_live_approved=True,
                claims_directory=root / "claims",
                archive_root=root,
                receipt_directory=root / "receipts",
                archive_scope_id=ARCHIVE_SCOPE_ID,
                provider_verifier=verifier,
                fingerprint_master_key=MASTER_KEY,
                native=native,
                credential_id_factory=lambda: CREDENTIAL_ID,
                backend_id_factory=lambda: BACKEND_ID,
                now_factory=lambda: NOW,
            )
            plan = self.make_plan()
            result = worker.execute(
                plan,
                expected_plan_digest=plan.plan_digest,
                current_owner_binding=OWNER,
            )

            self.assertFalse(result["ok"])
            self.assertEqual(
                result["reason_code"],
                "credential_input_invalid_for_provider",
            )
            self.assertEqual(
                (
                    result["credential_input_received"],
                    result["complete_line_received"],
                    result["temporary_store_write_attempted"],
                    result["provider_request_attempted"],
                ),
                (True, True, False, False),
            )
            self.assertEqual(result["rollback_status"], "not_required")
            self.assertEqual(verifier.calls, 0)
            self.assertEqual(harness.written_target, "")
            self.assertEqual(list((root / "receipts").glob("*.json")), [])
            self.assertNotIn(
                SYNTHETIC_SECRET.decode("ascii"),
                json.dumps(result, sort_keys=True),
            )

    def test_masked_ui_and_owner_errors_are_fixed_and_redacted(self) -> None:
        native = FakeWindowsNative(prompt_error=True)
        ui = WindowsCredentialPopupSecretUI(
            native,
            CredentialPopupPromptContext(
                provider="notion",
                purpose="notion_page_recovery",
                account_label="개인 계정",
                workspace_label="자료 보관함",
                task_summary="검토한 Notion 페이지를 WOM 아카이브로 복구하고 있습니다.",
                connection_reason="복구를 계속하려면 Notion 작업공간 연결을 확인해야 합니다.",
            ),
        )
        with self.assertRaises(WindowsSecureIntakeError) as dialog_error:
            ui.request_secret(request_id=REQUEST_ID)
        self.assertEqual(
            dialog_error.exception.code, "windows_credential_popup_failed"
        )
        self.assertNotIn(SYNTHETIC_SECRET.decode("ascii"), str(dialog_error.exception))
        self.assertNotIn(SYNTHETIC_SECRET.decode("ascii"), repr(ui))

        invalid_owner = FakeWindowsNative(sid="not-a-sid")
        with self.assertRaises(WindowsSecureIntakeError) as owner_error:
            current_windows_owner_binding(invalid_owner)
        self.assertEqual(owner_error.exception.code, "windows_owner_query_failed")
        self.assertEqual(current_windows_owner_binding(FakeWindowsNative()), OWNER)

    def test_exact_native_read_exception_is_fixed_and_never_echoes_blob(self) -> None:
        harness = FakeDllHarness()

        def explode(*_args):
            raise RuntimeError(SYNTHETIC_SECRET.decode("ascii"))

        harness.advapi32.CredReadW.handler = explode
        native = CtypesWindowsNativeFacade(
            cli_live_approved=True,
            platform_name="nt",
            dlls=harness.bundle(),
        )
        with self.assertRaises(WindowsSecureIntakeError) as read_error:
            native.read_generic_secret_exact(TARGET)
        self.assertEqual(
            read_error.exception.code, "windows_credential_read_failed"
        )
        self.assertNotIn(
            SYNTHETIC_SECRET.decode("ascii"), str(read_error.exception)
        )

    def test_domain_separated_fingerprint_is_stable_for_same_owner_and_key(self) -> None:
        fingerprints: list[str] = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index in range(2):
                native = FakeWindowsNative()
                worker = build_windows_secure_intake_worker(
                    cli_live_approved=True,
                    claims_directory=root / f"claims-{index}",
                    archive_root=root,
                    receipt_directory=root / f"receipts-{index}",
                    archive_scope_id=ARCHIVE_SCOPE_ID,
                    provider_verifier=FakeVerifier(),
                    fingerprint_master_key=MASTER_KEY,
                    native=native,
                    credential_id_factory=lambda i=index: f"cred_{i + 1:016d}",
                    backend_id_factory=lambda i=index: f"backend_{i + 1:016d}",
                    now_factory=lambda: NOW,
                )
                request_id = f"intake_{index + 1:016d}"
                plan = self.make_plan(request_id=request_id)
                result = worker.execute(
                    plan,
                    expected_plan_digest=plan.plan_digest,
                    current_owner_binding=OWNER,
                )
                self.assertTrue(result["ok"], result)
                fingerprints.append(str(result["fingerprint_digest"]))
            self.assertEqual(fingerprints[0], fingerprints[1])

            different_native = FakeWindowsNative()
            different_worker = build_windows_secure_intake_worker(
                cli_live_approved=True,
                claims_directory=root / "claims-different",
                archive_root=root,
                receipt_directory=root / "receipts-different",
                archive_scope_id=ARCHIVE_SCOPE_ID,
                provider_verifier=FakeVerifier(),
                fingerprint_master_key=b"different-master-key-used-only-for-test-0002",
                native=different_native,
                credential_id_factory=lambda: "cred_9999999999999999",
                backend_id_factory=lambda: "backend_9999999999999999",
                now_factory=lambda: NOW,
            )
            plan = self.make_plan(request_id="intake_9999999999999999")
            different = different_worker.execute(
                plan,
                expected_plan_digest=plan.plan_digest,
                current_owner_binding=OWNER,
            )
            self.assertNotEqual(fingerprints[0], different["fingerprint_digest"])


if __name__ == "__main__":
    unittest.main()
