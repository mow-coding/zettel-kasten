"""Windows-native primitives for human-only credential intake.

This module is the live Windows boundary for :mod:`credential_secure_intake`.
It deliberately uses only these exact operations:

* one native Unicode modal popup whose length-opaque overlay covers a standard
  password-style ``EDIT`` control;
* ``CredWriteW`` for one exact Generic Credential target;
* ``CredReadW`` only as an existence probe, followed immediately by
  ``CredFree`` without dereferencing ``CredentialBlob`` in Python;
* a separate, post-approval broker read which copies one exact
  ``CredentialBlob`` into a mutable buffer and immediately calls ``CredFree``;
* ``CredDeleteW`` for the same exact target; and
* the current process token's ``TokenUser`` SID for owner binding.

There is no ordinary stdin, command argument, environment-variable,
stdout/stderr, clipboard-reading API, plaintext-file, enumeration, search,
fuzzy matching, or public ``get-secret`` API.  The isolated transaction worker
owns the popup while the parent blocks, so the raw secret never crosses a
process boundary.  The exact broker read returns no text or public result and
its mutable buffer must be wiped after the trusted consumer finishes.  Loading
the real DLL facade requires an explicit ``cli_live_approved`` flag and a
Windows platform. Unit tests inject fake native boundaries and never open a
real popup, credential store, provider, or real secret.

Microsoft contracts used here:

* the spawned worker opens one owned Unicode popup and a standard password edit
  whose entire visible rectangle is covered by fixed length-opaque text;
* A Generic Credential is identified exactly by ``TargetName`` and ``Type``.
* The buffer allocated by ``CredReadW`` must be released with ``CredFree``.
"""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import os
import re
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Protocol

from .credential_secure_intake import (
    AtomicJsonReceiptCommitter,
    FileOneTimeRequestClaims,
    HumanSecretInputResult,
    ProviderIdentityVerifier,
    SecureIntakeWorker,
    WindowsCredentialManagerExactStore,
    _HumanSecretInputEvidenceError,
)
from .credential_popup_windows import (
    CredentialPopupContext,
    CredentialPopupInputIntent,
    prompt_secret_in_native_popup,
)


# Compatibility name retained for callers that already construct this safe
# context through the Windows intake module. Production rendering is the popup.
CredentialPopupPromptContext = CredentialPopupContext
VisibleConsolePromptContext = CredentialPopupPromptContext


ERROR_NOT_FOUND = 1168

CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
CRED_MAX_CREDENTIAL_BLOB_SIZE = 5 * 512
TOKEN_QUERY = 0x0008
TOKEN_USER_INFORMATION_CLASS = 1

REQUEST_ID_RE = re.compile(r"^intake_[A-Za-z0-9_-]{16,96}$")
BACKEND_ID_RE = re.compile(r"^backend_[A-Za-z0-9_-]{16,96}$")
TARGET_RE = re.compile(
    r"^WOM/credential-intake/(?:[0-9a-f]{64}/)?backend_[A-Za-z0-9_-]{16,96}$"
)
SID_RE = re.compile(r"^S-\d+-\d+(?:-\d+)+$")
FINGERPRINT_DOMAIN = b"wom/credential-secure-intake/fingerprint/v0.1\x00windows\x00"
FIXED_CODES = {
    "windows_live_approval_required",
    "windows_platform_required",
    "windows_native_load_failed",
    "windows_credential_popup_failed",
    "windows_visible_console_failed",
    "windows_credential_write_failed",
    "windows_credential_probe_failed",
    "windows_credential_read_failed",
    "windows_credential_delete_failed",
    "windows_owner_query_failed",
    "windows_target_invalid",
    "windows_secret_buffer_invalid",
    "windows_fingerprint_key_invalid",
    "windows_claims_authority_invalid",
}


class WindowsSecureIntakeError(RuntimeError):
    """A fixed-code Windows boundary error with no native error text."""

    def __init__(self, code: str) -> None:
        self.code = code if code in FIXED_CODES else "windows_native_load_failed"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"WindowsSecureIntakeError({self.code!r})"


def _fail(code: str) -> WindowsSecureIntakeError:
    return WindowsSecureIntakeError(code)


def windows_credential_target_prefix(archive_scope_id: str) -> str:
    """Return a collision-resistant, non-secret archive-specific namespace."""

    scope = str(archive_scope_id or "").strip()
    if (
        not scope
        or len(scope) > 512
        or any(ord(character) < 32 or ord(character) == 127 for character in scope)
    ):
        raise _fail("windows_target_invalid")
    scope_digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()
    return f"WOM/credential-intake/{scope_digest}/"


def windows_credential_target(archive_scope_id: str, backend_id: str) -> str:
    """Build one exact private locator for a local continuity binding."""

    backend = str(backend_id or "")
    if BACKEND_ID_RE.fullmatch(backend) is None:
        raise _fail("windows_target_invalid")
    return windows_credential_target_prefix(archive_scope_id) + backend


class _FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", _FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Sid", ctypes.c_void_p),
        ("Attributes", wintypes.DWORD),
    ]


class _TOKEN_USER(ctypes.Structure):
    _fields_ = [("User", _SID_AND_ATTRIBUTES)]


@dataclass(frozen=True)
class WindowsDllBundle:
    """Injected DLL bundle; fields are hidden from repr and public results."""

    advapi32: Any = field(repr=False)
    kernel32: Any = field(repr=False)
    # Kept only so older injected test/embedding bundles remain constructible.
    # Production no longer loads or calls CredUI.
    credui: Any | None = field(default=None, repr=False)


class WindowsSecureIntakeNative(Protocol):
    """High-level native facade consumed by the core worker and factory."""

    def prompt_masked_secret(
        self,
        *,
        request_id: str,
        context: CredentialPopupPromptContext,
    ) -> HumanSecretInputResult: ...

    def write_generic(self, target_name: str, secret: memoryview) -> None: ...

    def generic_exists(self, target_name: str) -> bool: ...

    def read_generic_secret_exact(self, target_name: str) -> bytearray: ...

    def delete_generic(self, target_name: str) -> None: ...

    def current_user_sid(self) -> str: ...


def _configure(function: Any, argtypes: list[Any], restype: Any) -> None:
    try:
        function.argtypes = argtypes
        function.restype = restype
    except Exception:
        raise _fail("windows_native_load_failed") from None


class CtypesWindowsNativeFacade:
    """Explicitly approved ctypes implementation of the native facade."""

    def __init__(
        self,
        *,
        cli_live_approved: bool,
        dlls: WindowsDllBundle | None = None,
        platform_name: str | None = None,
        popup_prompt: Callable[..., HumanSecretInputResult] | None = None,
        attached_console_prompt: Callable[..., HumanSecretInputResult] | None = None,
        console_prompt: Callable[..., HumanSecretInputResult] | None = None,
    ) -> None:
        if cli_live_approved is not True:
            raise _fail("windows_live_approval_required")
        if (platform_name or os.name) != "nt":
            raise _fail("windows_platform_required")
        try:
            if dlls is None:
                loader = getattr(ctypes, "WinDLL", None)
                if loader is None:
                    raise OSError
                dlls = WindowsDllBundle(
                    advapi32=loader("advapi32", use_last_error=True),
                    kernel32=loader("kernel32", use_last_error=True),
                )
            self._advapi32 = dlls.advapi32
            self._kernel32 = dlls.kernel32
            prompt_overrides = tuple(
                value
                for value in (popup_prompt, attached_console_prompt, console_prompt)
                if value is not None
            )
            if len(prompt_overrides) > 1:
                raise ValueError
            self._popup_prompt = (
                prompt_overrides[0]
                if prompt_overrides
                else prompt_secret_in_native_popup
            )
            self._configure_signatures()
        except WindowsSecureIntakeError:
            raise
        except Exception:
            raise _fail("windows_native_load_failed") from None

    def __repr__(self) -> str:
        return "CtypesWindowsNativeFacade(live_approved=True, popup=True)"

    def _configure_signatures(self) -> None:
        _configure(
            self._advapi32.CredWriteW,
            [ctypes.POINTER(_CREDENTIALW), wintypes.DWORD],
            wintypes.BOOL,
        )
        _configure(
            self._advapi32.CredReadW,
            [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.POINTER(ctypes.c_void_p),
            ],
            wintypes.BOOL,
        )
        _configure(
            self._advapi32.CredDeleteW,
            [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD],
            wintypes.BOOL,
        )
        _configure(self._advapi32.CredFree, [ctypes.c_void_p], None)
        _configure(
            self._advapi32.OpenProcessToken,
            [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)],
            wintypes.BOOL,
        )
        _configure(
            self._advapi32.GetTokenInformation,
            [
                wintypes.HANDLE,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
            ],
            wintypes.BOOL,
        )
        _configure(
            self._advapi32.ConvertSidToStringSidW,
            [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)],
            wintypes.BOOL,
        )
        _configure(self._kernel32.GetCurrentProcess, [], wintypes.HANDLE)
        _configure(self._kernel32.CloseHandle, [wintypes.HANDLE], wintypes.BOOL)
        _configure(self._kernel32.LocalFree, [ctypes.c_void_p], ctypes.c_void_p)

    @staticmethod
    def _last_error() -> int:
        getter = getattr(ctypes, "get_last_error", None)
        try:
            return int(getter()) if getter is not None else 0
        except Exception:
            return 0

    def prompt_masked_secret(
        self,
        *,
        request_id: str,
        context: CredentialPopupPromptContext,
    ) -> HumanSecretInputResult:
        if REQUEST_ID_RE.fullmatch(str(request_id or "")) is None:
            raise _fail("windows_credential_popup_failed")
        try:
            result = self._popup_prompt(
                request_id=request_id,
                context=context,
                input_intent=CredentialPopupInputIntent.live_registration,
                kernel32=self._kernel32,
                platform_name="nt",
                max_secret_bytes=CRED_MAX_CREDENTIAL_BLOB_SIZE,
            )
            if not isinstance(result, HumanSecretInputResult):
                raise _fail("windows_credential_popup_failed")
            return result
        except _HumanSecretInputEvidenceError:
            raise
        except WindowsSecureIntakeError:
            raise
        except Exception:
            raise _fail("windows_credential_popup_failed") from None

    @staticmethod
    def _validated_target(target_name: str) -> str:
        target = str(target_name or "")
        if TARGET_RE.fullmatch(target) is None:
            raise _fail("windows_target_invalid")
        return target

    def write_generic(self, target_name: str, secret: memoryview) -> None:
        target = self._validated_target(target_name)
        try:
            view = secret.cast("B")
            if view.readonly or not view.contiguous or not 0 < view.nbytes <= CRED_MAX_CREDENTIAL_BLOB_SIZE:
                raise _fail("windows_secret_buffer_invalid")
            native_blob = (ctypes.c_ubyte * view.nbytes).from_buffer(view)
            credential = _CREDENTIALW()
            credential.Flags = 0
            credential.Type = CRED_TYPE_GENERIC
            credential.TargetName = target
            credential.Comment = "WOM secure credential intake"
            credential.CredentialBlobSize = view.nbytes
            credential.CredentialBlob = ctypes.cast(
                native_blob, ctypes.POINTER(ctypes.c_ubyte)
            )
            credential.Persist = CRED_PERSIST_LOCAL_MACHINE
            credential.AttributeCount = 0
            credential.Attributes = None
            credential.TargetAlias = None
            credential.UserName = "WOM"
            if not self._advapi32.CredWriteW(ctypes.byref(credential), 0):
                raise _fail("windows_credential_write_failed")
            # Clear the pointer-bearing structure.  The mutable secret buffer
            # remains owned by the core worker and is wiped there.
            ctypes.memset(
                ctypes.addressof(credential), 0, ctypes.sizeof(credential)
            )
        except WindowsSecureIntakeError:
            raise
        except Exception:
            raise _fail("windows_credential_write_failed") from None

    def generic_exists(self, target_name: str) -> bool:
        target = self._validated_target(target_name)
        credential_pointer = ctypes.c_void_p()
        try:
            found = bool(
                self._advapi32.CredReadW(
                    target,
                    CRED_TYPE_GENERIC,
                    0,
                    ctypes.byref(credential_pointer),
                )
            )
            if found:
                if credential_pointer.value:
                    # Do not cast or dereference the CREDENTIALW.  In
                    # particular CredentialBlob never becomes a Python value.
                    allocated_pointer = credential_pointer
                    credential_pointer = ctypes.c_void_p()
                    self._advapi32.CredFree(allocated_pointer)
                return True
            if credential_pointer.value:
                allocated_pointer = credential_pointer
                credential_pointer = ctypes.c_void_p()
                self._advapi32.CredFree(allocated_pointer)
            if self._last_error() == ERROR_NOT_FOUND:
                return False
            raise _fail("windows_credential_probe_failed")
        except WindowsSecureIntakeError:
            raise
        except Exception:
            if credential_pointer.value:
                try:
                    allocated_pointer = credential_pointer
                    credential_pointer = ctypes.c_void_p()
                    self._advapi32.CredFree(allocated_pointer)
                except Exception:
                    pass
            raise _fail("windows_credential_probe_failed") from None

    def read_generic_secret_exact(self, target_name: str) -> bytearray:
        """Copy one exact Generic Credential blob into a mutable buffer.

        Unlike ``generic_exists``, this method is the post-approval broker read
        path.  It dereferences only the exact ``CredReadW`` result, copies the
        blob directly into a ``bytearray``, and calls ``CredFree`` before
        returning.  It never enumerates, searches, decodes, prints, or returns
        the target name.  The caller must wipe the returned buffer in a
        ``finally`` block after its trusted provider callback completes.
        """

        target = self._validated_target(target_name)
        credential_pointer = ctypes.c_void_p()
        output = bytearray()
        try:
            found = bool(
                self._advapi32.CredReadW(
                    target,
                    CRED_TYPE_GENERIC,
                    0,
                    ctypes.byref(credential_pointer),
                )
            )
            if not found or not credential_pointer.value:
                raise _fail("windows_credential_read_failed")
            credential = ctypes.cast(
                credential_pointer, ctypes.POINTER(_CREDENTIALW)
            ).contents
            size = int(credential.CredentialBlobSize)
            if (
                size <= 0
                or size > CRED_MAX_CREDENTIAL_BLOB_SIZE
                or not credential.CredentialBlob
            ):
                raise _fail("windows_credential_read_failed")
            output = bytearray(size)
            native_output = (ctypes.c_ubyte * size).from_buffer(output)
            ctypes.memmove(
                ctypes.addressof(native_output),
                credential.CredentialBlob,
                size,
            )
            return output
        except WindowsSecureIntakeError:
            for index in range(len(output)):
                output[index] = 0
            raise
        except Exception:
            for index in range(len(output)):
                output[index] = 0
            raise _fail("windows_credential_read_failed") from None
        finally:
            if credential_pointer.value:
                try:
                    allocated_pointer = credential_pointer
                    credential_pointer = ctypes.c_void_p()
                    self._advapi32.CredFree(allocated_pointer)
                except Exception:
                    for index in range(len(output)):
                        output[index] = 0
                    raise _fail("windows_credential_read_failed") from None

    def delete_generic(self, target_name: str) -> None:
        target = self._validated_target(target_name)
        try:
            if self._advapi32.CredDeleteW(target, CRED_TYPE_GENERIC, 0):
                return
            if self._last_error() == ERROR_NOT_FOUND:
                return
            raise _fail("windows_credential_delete_failed")
        except WindowsSecureIntakeError:
            raise
        except Exception:
            raise _fail("windows_credential_delete_failed") from None

    def current_user_sid(self) -> str:
        token = wintypes.HANDLE()
        sid_text = wintypes.LPWSTR()
        try:
            process = self._kernel32.GetCurrentProcess()
            if not self._advapi32.OpenProcessToken(
                process, TOKEN_QUERY, ctypes.byref(token)
            ):
                raise _fail("windows_owner_query_failed")
            required = wintypes.DWORD(0)
            self._advapi32.GetTokenInformation(
                token,
                TOKEN_USER_INFORMATION_CLASS,
                None,
                0,
                ctypes.byref(required),
            )
            if required.value <= 0:
                raise _fail("windows_owner_query_failed")
            token_buffer = ctypes.create_string_buffer(required.value)
            if not self._advapi32.GetTokenInformation(
                token,
                TOKEN_USER_INFORMATION_CLASS,
                token_buffer,
                required.value,
                ctypes.byref(required),
            ):
                raise _fail("windows_owner_query_failed")
            token_user = ctypes.cast(
                token_buffer, ctypes.POINTER(_TOKEN_USER)
            ).contents
            if not token_user.User.Sid:
                raise _fail("windows_owner_query_failed")
            if not self._advapi32.ConvertSidToStringSidW(
                token_user.User.Sid, ctypes.byref(sid_text)
            ):
                raise _fail("windows_owner_query_failed")
            sid = str(sid_text.value or "")
            if SID_RE.fullmatch(sid) is None:
                raise _fail("windows_owner_query_failed")
            return sid
        except WindowsSecureIntakeError:
            raise
        except Exception:
            raise _fail("windows_owner_query_failed") from None
        finally:
            if sid_text:
                try:
                    self._kernel32.LocalFree(
                        ctypes.cast(sid_text, ctypes.c_void_p)
                    )
                except Exception:
                    pass
            if token:
                try:
                    self._kernel32.CloseHandle(token)
                except Exception:
                    pass


@dataclass
class WindowsCredentialPopupSecretUI:
    """Worker-only native-popup adapter with no fallback input channel."""

    native: WindowsSecureIntakeNative = field(repr=False)
    context: CredentialPopupPromptContext = field(repr=False)

    def request_secret(self, *, request_id: str) -> HumanSecretInputResult:
        try:
            value = self.native.prompt_masked_secret(
                request_id=request_id,
                context=self.context,
            )
            if not isinstance(value, HumanSecretInputResult):
                raise _fail("windows_credential_popup_failed")
            return value
        except _HumanSecretInputEvidenceError:
            raise
        except WindowsSecureIntakeError:
            raise
        except Exception:
            raise _fail("windows_credential_popup_failed") from None


# Source compatibility for integrations that imported the earlier names.
# All production aliases now resolve to the native popup class above.
WindowsAttachedConsoleSecretUI = WindowsCredentialPopupSecretUI
WindowsVisibleConsoleSecretUI = WindowsCredentialPopupSecretUI
WindowsNativeMaskedSecretUI = WindowsCredentialPopupSecretUI


def current_windows_owner_binding(native: WindowsSecureIntakeNative) -> str:
    """Return the current exact Windows SID as an internal owner binding."""

    try:
        sid = native.current_user_sid()
        if SID_RE.fullmatch(str(sid or "")) is None:
            raise _fail("windows_owner_query_failed")
        return f"windows-sid:{sid}"
    except WindowsSecureIntakeError:
        raise
    except Exception:
        raise _fail("windows_owner_query_failed") from None


def derive_windows_fingerprint_key(
    master_key: bytes | bytearray | memoryview, owner_binding: str
) -> bytearray:
    """Derive the intake-only fingerprint key from the archive master key.

    Keeping this derivation public lets high-level orchestration share the
    authenticated archive key without reusing that raw key for token
    fingerprints.
    """

    if isinstance(master_key, memoryview):
        if (
            master_key.readonly
            or not master_key.c_contiguous
            or master_key.itemsize != 1
            or not isinstance(master_key.obj, bytearray)
            or master_key.nbytes != len(master_key.obj)
        ):
            raise _fail("windows_fingerprint_key_invalid")
        material: bytes | bytearray = master_key.obj
    elif isinstance(master_key, (bytes, bytearray)):
        material = master_key
    else:
        raise _fail("windows_fingerprint_key_invalid")
    if len(material) < 32:
        raise _fail("windows_fingerprint_key_invalid")
    return bytearray(
        hmac.new(
            material,
            FINGERPRINT_DOMAIN + owner_binding.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )


def build_windows_secure_intake_worker(
    *,
    cli_live_approved: bool,
    claims_directory: Path | str,
    archive_root: Path | str | None = None,
    receipt_directory: Path | str,
    archive_scope_id: str,
    provider_verifier: ProviderIdentityVerifier,
    fingerprint_master_key: bytes | bytearray | memoryview,
    native: WindowsSecureIntakeNative | None = None,
    prompt_context: CredentialPopupPromptContext | None = None,
    credential_id_factory: Any | None = None,
    backend_id_factory: Any | None = None,
    now_factory: Any | None = None,
) -> SecureIntakeWorker:
    """Assemble the Windows-first worker after explicit CLI approval.

    Construction queries only the current SID and creates no claim/receipt
    directory. The native popup, exact Credential Manager operations, and
    provider verifier run later inside
    ``SecureIntakeWorker.execute``.
    ``claims_directory`` must be lexically contained by the explicit
    ``archive_root``; omission or an outside path fails before the SID query.
    The master key must come from an approved secure configuration channel; it
    must not be supplied in argv, environment variables, stdin, or a plaintext
    file.
    """

    if cli_live_approved is not True:
        raise _fail("windows_live_approval_required")
    try:
        if archive_root is None:
            raise ValueError
        canonical_archive_root = Path(os.path.abspath(os.fspath(archive_root)))
        canonical_claims_directory = Path(
            os.path.abspath(os.fspath(claims_directory))
        )
        claims_relative_directory = canonical_claims_directory.relative_to(
            canonical_archive_root
        )
        if not claims_relative_directory.parts:
            raise ValueError
    except (TypeError, ValueError, OSError):
        raise _fail("windows_claims_authority_invalid") from None
    selected_native = (
        native
        if native is not None
        else CtypesWindowsNativeFacade(cli_live_approved=True)
    )
    owner_binding = current_windows_owner_binding(selected_native)
    worker_kwargs: dict[str, Any] = {
        "claims": FileOneTimeRequestClaims(
            canonical_claims_directory,
            archive_root=canonical_archive_root,
            expected_relative_directory=claims_relative_directory,
        ),
        "ui": WindowsCredentialPopupSecretUI(
            selected_native,
            prompt_context
            if prompt_context is not None
            else CredentialPopupPromptContext(
                provider="notion",
                purpose="source_recovery",
                account_label="승인한 계정",
                workspace_label="승인한 작업공간",
                task_summary="승인한 Notion 자료 연결 작업을 진행하고 있습니다.",
                connection_reason="이 작업을 계속하려면 해당 Notion 작업공간 연결을 확인해 주세요.",
            ),
        ),
        "store": WindowsCredentialManagerExactStore(
            native=selected_native,
            target_prefix=windows_credential_target_prefix(archive_scope_id),
        ),
        "verifier": provider_verifier,
        "receipt_committer": AtomicJsonReceiptCommitter(receipt_directory),
        "fingerprint_key": derive_windows_fingerprint_key(
            fingerprint_master_key, owner_binding
        ),
    }
    if credential_id_factory is not None:
        worker_kwargs["credential_id_factory"] = credential_id_factory
    if backend_id_factory is not None:
        worker_kwargs["backend_id_factory"] = backend_id_factory
    if now_factory is not None:
        worker_kwargs["now_factory"] = now_factory
    return SecureIntakeWorker(**worker_kwargs)


__all__ = [
    "CtypesWindowsNativeFacade",
    "CredentialPopupPromptContext",
    "WindowsDllBundle",
    "WindowsAttachedConsoleSecretUI",
    "WindowsCredentialPopupSecretUI",
    "WindowsNativeMaskedSecretUI",
    "WindowsVisibleConsoleSecretUI",
    "WindowsSecureIntakeError",
    "WindowsSecureIntakeNative",
    "VisibleConsolePromptContext",
    "build_windows_secure_intake_worker",
    "current_windows_owner_binding",
    "derive_windows_fingerprint_key",
    "windows_credential_target",
    "windows_credential_target_prefix",
]
