"""Visible Windows-console intake for one human-entered secret.

This module is deliberately narrower than a terminal command runner.  It opens
one new console owned by the already-isolated credential transaction worker,
reads one line with console echo disabled, returns one mutable UTF-8 buffer,
and closes the console before any credential-store write can begin.

The secret is never accepted through argv, environment variables, ordinary
stdin, stdout/stderr, a direct clipboard API read, a file, or inter-process
communication.  A human may deliberately paste into this isolated console;
that paste is handled only as masked ``CONIN$`` input.  ``CONIN$`` and
``CONOUT$`` are opened directly so redirection in the launching AI process
cannot become an accidental secret channel.
"""

from __future__ import annotations

import ctypes
import math
import os
import re
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any, Callable


REQUEST_ID_RE = re.compile(r"^intake_[A-Za-z0-9_-]{16,96}$")

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

ENABLE_PROCESSED_INPUT = 0x0001
ENABLE_LINE_INPUT = 0x0002
ENABLE_ECHO_INPUT = 0x0004
ENABLE_INSERT_MODE = 0x0020
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080
ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200

CP_UTF8 = 65001
WC_ERR_INVALID_CHARS = 0x00000080
DEFAULT_MAX_SECRET_BYTES = 5 * 512

_CONSOLE_TITLE = "WOM · 안전한 연결 확인"
_SAFE_LABEL_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,128}$")
_SAFE_CONTEXT_TEXT_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,240}$")
_SECRET_SHAPE_RE = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:ntn_|secret_|github_pat_|sk-)[A-Za-z0-9_./+=-]{16,})"
)
_PRIVATE_LOCATOR_SHAPE_RE = re.compile(
    r"(?i)(?:https?://|\\\\|[A-Z]:\\|\b[0-9a-f]{8}-[0-9a-f-]{27,}\b|\b[0-9a-f]{32,}\b|\S+@\S+)"
)
_ACCEPTED_TEXT = (
    "\r\n입력값을 받았습니다. 검증 중입니다.\r\n"
    "이 창은 자동으로 닫힙니다.\r\n"
)
_CANCELLED_TEXT = "\r\n입력을 취소했습니다. 이 창은 자동으로 닫힙니다.\r\n"


@dataclass(frozen=True)
class VisibleConsolePromptContext:
    """Safe, already-reviewed task labels displayed only in the local console."""

    provider: str
    purpose: str
    account_label: str
    workspace_label: str
    task_summary: str
    connection_reason: str


def _safe_context_label(value: Any) -> str:
    text = str(value or "").strip()
    if _SAFE_LABEL_RE.fullmatch(text) is None:
        raise VisibleConsoleSecretPromptError()
    return text


def _safe_context_text(value: Any) -> str:
    text = str(value or "").strip()
    if (
        _SAFE_CONTEXT_TEXT_RE.fullmatch(text) is None
        or _SECRET_SHAPE_RE.search(text) is not None
        or _PRIVATE_LOCATOR_SHAPE_RE.search(text) is not None
    ):
        raise VisibleConsoleSecretPromptError()
    return text


def _prompt_copy(context: VisibleConsolePromptContext) -> str:
    if not isinstance(context, VisibleConsolePromptContext):
        raise VisibleConsoleSecretPromptError()
    provider = _safe_context_label(context.provider).lower()
    purpose = _safe_context_label(context.purpose).lower().replace("-", "_")
    account_label = _safe_context_label(context.account_label)
    workspace_label = _safe_context_label(context.workspace_label)
    task_summary = _safe_context_text(context.task_summary)
    connection_reason = _safe_context_text(context.connection_reason)
    if provider != "notion" or purpose not in {"notion_page_recovery", "source_recovery"}:
        raise VisibleConsoleSecretPromptError()
    return (
        "WOM · 안전한 연결 확인\r\n\r\n"
        "도우미 AI가 설명한 현재 작업\r\n"
        f"{task_summary}\r\n\r\n"
        "연결이 필요한 이유\r\n"
        f"{connection_reason}\r\n\r\n"
        "연결 대상\r\n"
        "- 서비스: Notion\r\n"
        f"- 계정: {account_label}\r\n"
        f"- 작업공간: {workspace_label}\r\n\r\n"
        "WOM 보안 안내\r\n"
        "입력한 자격 증명은 도우미 AI와 채팅에 전달되지 않습니다.\r\n"
        "WOM과 도우미 AI는 클립보드 내용을 직접 읽지 않습니다.\r\n"
        "사람이 이 창에 붙여넣은 내용만 숨김 입력으로 처리합니다.\r\n"
        "입력 내용은 화면, 명령줄, 로그에도 표시되지 않습니다.\r\n"
        "연결이 성공하면 Windows 자격 증명 관리자에 안전하게 보관됩니다.\r\n"
        "다음 승인된 WOM 작업에서는 저장된 자격 증명을 재사용하므로 다시 입력하지 않습니다.\r\n\r\n"
        "붙여넣기 안내\r\n"
        "- Ctrl+V 또는 Shift+Insert를 사용하세요.\r\n"
        "- Windows Terminal 기본 설정에서는 Ctrl+Shift+V도 사용할 수 있습니다.\r\n"
        "- 오른쪽 클릭은 터미널 설정에 따라 메뉴나 복사로 동작할 수 있습니다.\r\n"
        "  메뉴가 열리면 '붙여넣기'를 선택하세요.\r\n"
        "- 붙여넣은 글자는 화면에 나타나지 않습니다. 붙여넣은 뒤 Enter를 누르세요.\r\n"
        "취소하려면 아무것도 입력하지 않은 상태에서 Enter를 누르세요.\r\n\r\n"
        "Notion 연결 키 (입력 내용 숨김): "
    )


class _CONSOLE_READCONSOLE_CONTROL(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.ULONG),
        ("nInitialChars", wintypes.ULONG),
        ("dwCtrlWakeupMask", wintypes.ULONG),
        ("dwControlKeyState", wintypes.ULONG),
    ]


class VisibleConsoleSecretPromptError(RuntimeError):
    """One fixed, secret-free failure for the console boundary."""

    code = "windows_visible_console_failed"

    def __init__(self) -> None:
        super().__init__(self.code)

    def __repr__(self) -> str:
        return "VisibleConsoleSecretPromptError()"


def _configure(function: Any, argtypes: list[Any], restype: Any) -> None:
    try:
        function.argtypes = argtypes
        function.restype = restype
    except Exception:
        raise VisibleConsoleSecretPromptError() from None


def _configure_console_signatures(kernel32: Any) -> None:
    _configure(kernel32.FreeConsole, [], wintypes.BOOL)
    _configure(kernel32.AllocConsole, [], wintypes.BOOL)
    _configure(kernel32.SetConsoleTitleW, [wintypes.LPCWSTR], wintypes.BOOL)
    _configure(kernel32.GetConsoleCP, [], wintypes.UINT)
    _configure(kernel32.SetConsoleCP, [wintypes.UINT], wintypes.BOOL)
    _configure(kernel32.GetConsoleOutputCP, [], wintypes.UINT)
    _configure(kernel32.SetConsoleOutputCP, [wintypes.UINT], wintypes.BOOL)
    _configure(
        kernel32.CreateFileW,
        [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ],
        wintypes.HANDLE,
    )
    _configure(
        kernel32.GetConsoleMode,
        [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)],
        wintypes.BOOL,
    )
    _configure(
        kernel32.SetConsoleCtrlHandler,
        [wintypes.LPVOID, wintypes.BOOL],
        wintypes.BOOL,
    )
    _configure(
        kernel32.SetConsoleMode,
        [wintypes.HANDLE, wintypes.DWORD],
        wintypes.BOOL,
    )
    _configure(
        kernel32.ReadConsoleW,
        [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ],
        wintypes.BOOL,
    )
    _configure(
        kernel32.WriteConsoleW,
        [
            wintypes.HANDLE,
            wintypes.LPCVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ],
        wintypes.BOOL,
    )
    _configure(kernel32.CloseHandle, [wintypes.HANDLE], wintypes.BOOL)
    _configure(
        kernel32.WideCharToMultiByte,
        [
            wintypes.UINT,
            wintypes.DWORD,
            wintypes.LPCWSTR,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_int,
            wintypes.LPCSTR,
            ctypes.POINTER(wintypes.BOOL),
        ],
        ctypes.c_int,
    )


def _wipe_bytearray(value: bytearray | None) -> None:
    if value is None:
        return
    for index in range(len(value)):
        value[index] = 0


def _write_console(kernel32: Any, handle: Any, message: str) -> None:
    try:
        wchar_count = len(message.encode("utf-16-le", errors="strict")) // 2
    except UnicodeEncodeError:
        raise VisibleConsoleSecretPromptError() from None
    written = wintypes.DWORD(0)
    if not kernel32.WriteConsoleW(
        handle,
        message,
        wchar_count,
        ctypes.byref(written),
        None,
    ) or int(written.value) != wchar_count:
        raise VisibleConsoleSecretPromptError()


def _utf8_from_wchar_buffer(
    kernel32: Any,
    buffer: Any,
    wchar_length: int,
    *,
    max_secret_bytes: int,
) -> bytearray:
    output = bytearray()
    try:
        needed = int(
            kernel32.WideCharToMultiByte(
                CP_UTF8,
                WC_ERR_INVALID_CHARS,
                buffer,
                wchar_length,
                None,
                0,
                None,
                None,
            )
        )
        if needed <= 0 or needed > max_secret_bytes:
            raise VisibleConsoleSecretPromptError()
        output = bytearray(needed)
        native_output = (ctypes.c_char * needed).from_buffer(output)
        converted = int(
            kernel32.WideCharToMultiByte(
                CP_UTF8,
                WC_ERR_INVALID_CHARS,
                buffer,
                wchar_length,
                ctypes.cast(native_output, ctypes.c_void_p),
                needed,
                None,
                None,
            )
        )
        if converted != needed:
            raise VisibleConsoleSecretPromptError()
        return output
    except VisibleConsoleSecretPromptError:
        _wipe_bytearray(output)
        raise
    except Exception:
        _wipe_bytearray(output)
        raise VisibleConsoleSecretPromptError() from None


def prompt_masked_secret_in_new_console(
    *,
    request_id: str,
    context: VisibleConsolePromptContext,
    kernel32: Any | None = None,
    platform_name: str | None = None,
    max_secret_bytes: int = DEFAULT_MAX_SECRET_BYTES,
    status_dwell_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> bytearray | None:
    """Read one secret in a newly allocated console owned by this process.

    The caller must be the existing fresh credential transaction worker.  The
    console is detached before this function returns, so the raw secret never
    crosses a process boundary and the user cannot close a still-visible
    console after the later Credential Manager write has begun.
    """

    if (
        REQUEST_ID_RE.fullmatch(str(request_id or "")) is None
        or type(max_secret_bytes) is not int
        or max_secret_bytes <= 0
        or max_secret_bytes > DEFAULT_MAX_SECRET_BYTES
        or isinstance(status_dwell_seconds, bool)
        or not isinstance(status_dwell_seconds, (int, float))
        or not math.isfinite(float(status_dwell_seconds))
        or not 0 <= float(status_dwell_seconds) <= 5
        or not callable(sleep)
        or (platform_name or os.name) != "nt"
    ):
        raise VisibleConsoleSecretPromptError()
    prompt_text = _prompt_copy(context)
    try:
        selected_kernel32 = kernel32
        if selected_kernel32 is None:
            loader = getattr(ctypes, "WinDLL", None)
            if loader is None:
                raise VisibleConsoleSecretPromptError()
            selected_kernel32 = loader("kernel32", use_last_error=True)
        _configure_console_signatures(selected_kernel32)
    except VisibleConsoleSecretPromptError:
        raise
    except Exception:
        raise VisibleConsoleSecretPromptError() from None

    console_allocated = False
    input_handle: Any = None
    output_handle: Any = None
    original_mode: int | None = None
    original_input_code_page: int | None = None
    original_output_code_page: int | None = None
    ctrl_c_ignored = False
    secret: bytearray | None = None
    cancelled = False
    failed = False
    cleanup_failed = False
    # The largest accepted credential can be all ASCII, so reserve one WCHAR
    # per byte plus room for CR/LF.  UTF-8 width is checked after conversion.
    wchar_capacity = max_secret_bytes + 2
    input_buffer = ctypes.create_unicode_buffer(wchar_capacity)

    try:
        # The spawned worker may or may not have inherited a console from its
        # launcher. Detaching affects only this worker; failure can simply mean
        # that there was no console to detach. AllocConsole below is the
        # authoritative check that a separate visible console now exists.
        selected_kernel32.FreeConsole()
        if not selected_kernel32.AllocConsole():
            raise VisibleConsoleSecretPromptError()
        console_allocated = True
        if not selected_kernel32.SetConsoleTitleW(_CONSOLE_TITLE):
            raise VisibleConsoleSecretPromptError()
        original_input_code_page = int(selected_kernel32.GetConsoleCP())
        original_output_code_page = int(selected_kernel32.GetConsoleOutputCP())
        if (
            original_input_code_page <= 0
            or original_output_code_page <= 0
            or not selected_kernel32.SetConsoleCP(CP_UTF8)
            or not selected_kernel32.SetConsoleOutputCP(CP_UTF8)
        ):
            raise VisibleConsoleSecretPromptError()

        share_mode = FILE_SHARE_READ | FILE_SHARE_WRITE
        input_handle = selected_kernel32.CreateFileW(
            "CONIN$",
            GENERIC_READ | GENERIC_WRITE,
            share_mode,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        output_handle = selected_kernel32.CreateFileW(
            "CONOUT$",
            GENERIC_READ | GENERIC_WRITE,
            share_mode,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if input_handle in (None, INVALID_HANDLE_VALUE) or output_handle in (
            None,
            INVALID_HANDLE_VALUE,
        ):
            raise VisibleConsoleSecretPromptError()

        mode = wintypes.DWORD(0)
        if not selected_kernel32.GetConsoleMode(input_handle, ctypes.byref(mode)):
            raise VisibleConsoleSecretPromptError()
        original_mode = int(mode.value)
        # Processed input is required for the modern Console Host's Ctrl+V and
        # Shift+Insert edit shortcuts. AllocConsole resets the control-handler
        # table, whose default Ctrl+C handler exits the process, so ignore
        # Ctrl+C only for this short prompt and advertise empty Enter as the
        # deterministic cancellation gesture.
        if not selected_kernel32.SetConsoleCtrlHandler(None, True):
            raise VisibleConsoleSecretPromptError()
        ctrl_c_ignored = True
        masked_mode = (
            original_mode
            | ENABLE_PROCESSED_INPUT
            | ENABLE_LINE_INPUT
            | ENABLE_INSERT_MODE
            | ENABLE_QUICK_EDIT_MODE
            | ENABLE_EXTENDED_FLAGS
        ) & ~(
            ENABLE_ECHO_INPUT | ENABLE_VIRTUAL_TERMINAL_INPUT
        )
        if not selected_kernel32.SetConsoleMode(input_handle, masked_mode):
            raise VisibleConsoleSecretPromptError()

        _write_console(selected_kernel32, output_handle, prompt_text)
        count = wintypes.DWORD(0)
        input_control = _CONSOLE_READCONSOLE_CONTROL(
            nLength=ctypes.sizeof(_CONSOLE_READCONSOLE_CONTROL),
            nInitialChars=0,
            # ReadConsoleW remains in cooked line mode. Ctrl+C is temporarily
            # ignored at the process control-handler boundary, so only a
            # complete Enter-terminated line completes this read.
            dwCtrlWakeupMask=0,
            dwControlKeyState=0,
        )
        try:
            read_ok = selected_kernel32.ReadConsoleW(
                input_handle,
                input_buffer,
                wchar_capacity,
                ctypes.byref(count),
                ctypes.byref(input_control),
            )
        except KeyboardInterrupt:
            read_ok = True
            cancelled = True
        if not read_ok:
            raise VisibleConsoleSecretPromptError()

        if not cancelled:
            read_length = int(count.value)
            if read_length <= 0 or read_length > wchar_capacity:
                raise VisibleConsoleSecretPromptError()
            # Windows c_wchar is UTF-16.  The wider fallback keeps injected
            # fake-DLL tests portable without changing the live Windows path.
            unit_type = (
                ctypes.c_uint16
                if ctypes.sizeof(ctypes.c_wchar) == 2
                else ctypes.c_uint32
            )
            units = ctypes.cast(
                input_buffer,
                ctypes.POINTER(unit_type),
            )
            # Ctrl+C wakes ReadConsoleW before a trailing CR/LF and must be
            # classified before the complete-line check.
            if any(units[index] == 0x0003 for index in range(read_length)):
                cancelled = True
            else:
                # ENABLE_LINE_INPUT must return a complete line. A full buffer
                # without CR/LF is a truncated oversized input and must never
                # be accepted as a different credential.
                if units[read_length - 1] not in (0x000A, 0x000D):
                    raise VisibleConsoleSecretPromptError()
                wchar_length = read_length
                while wchar_length and units[wchar_length - 1] in (0x000A, 0x000D):
                    wchar_length -= 1
                if wchar_length == 0:
                    cancelled = True
                else:
                    # Embedded NUL/CR/LF indicates a pasted multiline or malformed
                    # value. Inspect UTF-16 code units without materializing a
                    # Python secret string.
                    for index in range(wchar_length):
                        if units[index] < 0x0020 or units[index] == 0x007F:
                            raise VisibleConsoleSecretPromptError()
                    secret = _utf8_from_wchar_buffer(
                        selected_kernel32,
                        input_buffer,
                        wchar_length,
                        max_secret_bytes=max_secret_bytes,
                    )
                    # Keep only the mutable UTF-8 buffer that crosses the
                    # secure-intake boundary.  The console's duplicate UTF-16
                    # copy is no longer needed and must not survive the safe
                    # receipt-status dwell below.
                    ctypes.memset(
                        ctypes.addressof(input_buffer),
                        0,
                        ctypes.sizeof(input_buffer),
                    )

        _write_console(
            selected_kernel32,
            output_handle,
            _CANCELLED_TEXT if cancelled else _ACCEPTED_TEXT,
        )
        if not cancelled and float(status_dwell_seconds) > 0:
            sleep(float(status_dwell_seconds))
    except KeyboardInterrupt:
        cancelled = True
    except BaseException:
        failed = True
    finally:
        ctypes.memset(
            ctypes.addressof(input_buffer),
            0,
            ctypes.sizeof(input_buffer),
        )
        if input_handle not in (None, INVALID_HANDLE_VALUE) and original_mode is not None:
            try:
                if not selected_kernel32.SetConsoleMode(input_handle, original_mode):
                    cleanup_failed = True
            except BaseException:
                cleanup_failed = True
        if console_allocated and original_input_code_page is not None:
            try:
                if not selected_kernel32.SetConsoleCP(original_input_code_page):
                    cleanup_failed = True
            except BaseException:
                cleanup_failed = True
        if console_allocated and original_output_code_page is not None:
            try:
                if not selected_kernel32.SetConsoleOutputCP(original_output_code_page):
                    cleanup_failed = True
            except BaseException:
                cleanup_failed = True
        for handle in (input_handle, output_handle):
            if handle in (None, INVALID_HANDLE_VALUE):
                continue
            try:
                if not selected_kernel32.CloseHandle(handle):
                    cleanup_failed = True
            except BaseException:
                cleanup_failed = True
        console_detached = False
        if console_allocated:
            try:
                console_detached = bool(selected_kernel32.FreeConsole())
                if not console_detached:
                    cleanup_failed = True
            except BaseException:
                cleanup_failed = True
        # Never re-enable the default process-terminating Ctrl+C handler while
        # this worker is still attached to the prompt console. FreeConsole
        # resets the handler table on success. This fallback is reached only
        # when allocation did not complete, so no prompt console exists.
        if ctrl_c_ignored and not console_detached and not console_allocated:
            try:
                if not selected_kernel32.SetConsoleCtrlHandler(None, False):
                    cleanup_failed = True
            except BaseException:
                cleanup_failed = True

    if failed or cleanup_failed:
        _wipe_bytearray(secret)
        raise VisibleConsoleSecretPromptError()
    if cancelled:
        _wipe_bytearray(secret)
        return None
    if not isinstance(secret, bytearray) or not secret:
        _wipe_bytearray(secret)
        raise VisibleConsoleSecretPromptError()
    return secret


__all__ = [
    "VisibleConsolePromptContext",
    "VisibleConsoleSecretPromptError",
    "prompt_masked_secret_in_new_console",
]
