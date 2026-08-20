"""Native Windows credential popup with a length-opaque input surface.

The popup owns one standard Unicode single-line ``EDIT`` control.  The edit is
created with ``ES_PASSWORD`` as a fail-safe, while a separate opaque sibling
``STATIC`` control covers the entire edit rectangle with fixed text so neither
characters nor password-mask count are visible.  The worker receives only one
mutable UTF-8 buffer after explicit confirmation.  No console, ordinary stream,
environment, argument, file, provider, store, or clipboard-reading API is used.
"""

from __future__ import annotations

import ctypes
import os
import re
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .credential_secure_intake import (
    HumanSecretInputResult,
    _HumanSecretInputEvidenceError,
)


CP_UTF8 = 65001
WC_ERR_INVALID_CHARS = 0x00000080

CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
COLOR_WINDOW = 5
CW_USEDEFAULT = 0x80000000

WS_OVERLAPPED = 0x00000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_TABSTOP = 0x00010000
WS_BORDER = 0x00800000
WS_CLIPSIBLINGS = 0x04000000

WS_EX_DLGMODALFRAME = 0x00000001
WS_EX_CONTROLPARENT = 0x00010000

ES_LEFT = 0x0000
ES_AUTOHSCROLL = 0x0080
ES_PASSWORD = 0x0020
SS_LEFT = 0x0000
SS_CENTER = 0x0001
SS_NOPREFIX = 0x0080
SS_CENTERIMAGE = 0x0200
SS_SUNKEN = 0x1000
SS_EDITCONTROL = 0x2000
BS_PUSHBUTTON = 0x00000000
BS_DEFPUSHBUTTON = 0x00000001

SW_SHOW = 5
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
HWND_TOP = 0
HTTRANSPARENT = -1

WM_CREATE = 0x0001
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_SETFONT = 0x0030
WM_COMMAND = 0x0111
WM_NCDESTROY = 0x0082
WM_KEYDOWN = 0x0100
WM_SETFOCUS = 0x0007
WM_LBUTTONDOWN = 0x0201
WM_NCHITTEST = 0x0084
WM_CONTEXTMENU = 0x007B
WM_CTLCOLORSTATIC = 0x0138
WM_COPY = 0x0301
WM_CUT = 0x0300
WM_CLEAR = 0x0303
WM_PASTE = 0x0302

EM_SETSEL = 0x00B1
EM_SETLIMITTEXT = 0x00C5
EM_EMPTYUNDOBUFFER = 0x00CD

EN_CHANGE = 0x0300
EN_MAXTEXT = 0x0501
BN_CLICKED = 0
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B

MF_STRING = 0x0000
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080

IDC_EDIT = 1001
IDC_OVERLAY = 1002
IDC_STATUS = 1003
IDC_INTENT_BANNER = 1004
IDOK = 1
IDCANCEL = 2
ID_POPUP_PASTE = 2001
ID_POPUP_CLEAR = 2002
SPI_GETNONCLIENTMETRICS = 0x0029
LF_FACESIZE = 32
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
DT_WORDBREAK = 0x0010
DT_EDITCONTROL = 0x2000
DT_CALCRECT = 0x0400
DT_NOPREFIX = 0x0800
CLR_INVALID = 0xFFFFFFFF

WINDOW_WIDTH = 660
WINDOW_HEIGHT = 470
CONTENT_X = 28
CONTENT_WIDTH = 590
INSTRUCTION_TOP = 24
INTENT_BANNER_HEIGHT = 24
INTENT_BANNER_GAP = 4
TEXT_ROW_MIN_HEIGHT = 24
TEXT_VERTICAL_PADDING = 6
TEXT_ROW_GAP = 4
TEXT_PARAGRAPH_GAP = 12
INPUT_SECTION_GAP = 18
INSTRUCTION_BUDGET_BOTTOM = 244
EDIT_X = CONTENT_X
EDIT_WIDTH = CONTENT_WIDTH
EDIT_HEIGHT = 46
STATUS_GAP = 16
BUTTON_GAP = 24
BUTTON_WIDTH = 92
BUTTON_HEIGHT = 36
BUTTON_OK_X = 418
BUTTON_CANCEL_X = 526
WINDOW_CLIENT_SAFE_BOTTOM = WINDOW_HEIGHT - 60

POPUP_TITLE = "WOM · 안전한 자격 증명 입력"
LIVE_REGISTRATION_BANNER_TEXT = "실제 자격 증명 등록"
SYNTHETIC_ACCEPTANCE_BANNER_TEXT = "합성 입력 테스트 · 실제 키 입력 금지"
LIVE_REGISTRATION_BANNER_BACKGROUND_COLOR = 0x00D47800
LIVE_REGISTRATION_BANNER_TEXT_COLOR = 0x00FFFFFF
SYNTHETIC_ACCEPTANCE_BANNER_BACKGROUND_COLOR = 0x003232C8
SYNTHETIC_ACCEPTANCE_BANNER_TEXT_COLOR = 0x00FFFFFF
OVERLAY_TEXT = "입력 내용과 길이는 화면에 표시되지 않습니다."
STATUS_EMPTY_TEXT = "자격 증명을 입력하면 확인 버튼이 활성화됩니다."
STATUS_READY_TEXT = "입력을 받았습니다. 확인을 누르면 연결 확인을 진행합니다."
STATUS_LIMIT_EXCEEDED_TEXT = "입력 한도를 초과했습니다. 지우고 다시 입력하세요."
SYNTHETIC_STATUS_EMPTY_TEXT = (
    "실제 키 입력 금지 · 안내받은 합성 문자열만 입력하세요."
)
SYNTHETIC_STATUS_READY_TEXT = (
    "합성 입력을 받았습니다. 실제 키가 아닌지 확인한 뒤 확인을 누르세요."
)
SYNTHETIC_STATUS_LIMIT_EXCEEDED_TEXT = (
    "합성 입력 한도를 초과했습니다. 지우고 다시 입력하세요."
)
PASTE_MENU_TEXT = "붙여넣기"
CLEAR_MENU_TEXT = "지우기"
OK_TEXT = "확인"
CANCEL_TEXT = "취소"

_REQUEST_ID_RE = re.compile(r"^intake_[A-Za-z0-9_-]{16,96}$")
_SAFE_LABEL_RE = re.compile(r"^[^\x00-\x1f\x7f\r\n]{1,120}$")
_SAFE_TEXT_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,500}$")
_SECRET_SHAPE_RE = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:ntn_|secret_|github_pat_|sk-)[A-Za-z0-9_./+=-]{16,})"
)
_PRIVATE_LOCATOR_SHAPE_RE = re.compile(
    r"(?i)(?:https?://|\\\\|[A-Z]:\\|\b[0-9a-f]{8}-[0-9a-f-]{27,}\b|"
    r"\b[0-9a-f]{32,}\b|\S+@\S+)"
)

_LRESULT = ctypes.c_ssize_t
_WPARAM = getattr(wintypes, "WPARAM", ctypes.c_size_t)
_LPARAM = getattr(wintypes, "LPARAM", ctypes.c_ssize_t)
_WNDPROC_TYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
    _LRESULT, wintypes.HWND, wintypes.UINT, _WPARAM, _LPARAM
)
_SUBCLASSPROC_TYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
    _LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    _WPARAM,
    _LPARAM,
    ctypes.c_size_t,
    ctypes.c_size_t,
)


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class _LOGFONTW(ctypes.Structure):
    _fields_ = [
        ("lfHeight", wintypes.LONG),
        ("lfWidth", wintypes.LONG),
        ("lfEscapement", wintypes.LONG),
        ("lfOrientation", wintypes.LONG),
        ("lfWeight", wintypes.LONG),
        ("lfItalic", wintypes.BYTE),
        ("lfUnderline", wintypes.BYTE),
        ("lfStrikeOut", wintypes.BYTE),
        ("lfCharSet", wintypes.BYTE),
        ("lfOutPrecision", wintypes.BYTE),
        ("lfClipPrecision", wintypes.BYTE),
        ("lfQuality", wintypes.BYTE),
        ("lfPitchAndFamily", wintypes.BYTE),
        ("lfFaceName", wintypes.WCHAR * LF_FACESIZE),
    ]


class _NONCLIENTMETRICSW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("iBorderWidth", ctypes.c_int),
        ("iScrollWidth", ctypes.c_int),
        ("iScrollHeight", ctypes.c_int),
        ("iCaptionWidth", ctypes.c_int),
        ("iCaptionHeight", ctypes.c_int),
        ("lfCaptionFont", _LOGFONTW),
        ("iSmCaptionWidth", ctypes.c_int),
        ("iSmCaptionHeight", ctypes.c_int),
        ("lfSmCaptionFont", _LOGFONTW),
        ("iMenuWidth", ctypes.c_int),
        ("iMenuHeight", ctypes.c_int),
        ("lfMenuFont", _LOGFONTW),
        ("lfStatusFont", _LOGFONTW),
        ("lfMessageFont", _LOGFONTW),
        ("iPaddedBorderWidth", ctypes.c_int),
    ]


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", _WPARAM),
        ("lParam", _LPARAM),
        ("time", wintypes.DWORD),
        ("pt", _POINT),
    ]


class _WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", _WNDPROC_TYPE),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


@dataclass(frozen=True)
class CredentialPopupContext:
    """Reviewed, non-secret labels rendered in the popup."""

    provider: str
    purpose: str
    account_label: str
    workspace_label: str
    task_summary: str
    connection_reason: str


class CredentialPopupInputIntent(Enum):
    """Closed operator intent set; plain strings are deliberately rejected."""

    live_registration = "live_registration"
    synthetic_acceptance = "synthetic_acceptance"


class CredentialPopupSecretPromptError(_HumanSecretInputEvidenceError):
    """Content-free popup failure with strict causal input evidence."""


def _error(
    *, input_observed: bool, complete: bool, invalid: bool = False
) -> CredentialPopupSecretPromptError:
    if invalid:
        return CredentialPopupSecretPromptError(
            reason_code="credential_input_invalid_for_provider",
            credential_input_received=True,
            complete_line_received=True,
        )
    if not input_observed:
        return CredentialPopupSecretPromptError(
            reason_code="credential_input_not_received",
            credential_input_received=False,
            complete_line_received=False,
        )
    return CredentialPopupSecretPromptError(
        reason_code="credential_input_boundary_failed",
        credential_input_received=True,
        complete_line_received=complete,
    )


def _safe_label(value: Any) -> str:
    if (
        type(value) is not str
        or _SAFE_LABEL_RE.fullmatch(value.strip()) is None
        or _SECRET_SHAPE_RE.search(value) is not None
        or _PRIVATE_LOCATOR_SHAPE_RE.search(value) is not None
    ):
        raise _error(input_observed=False, complete=False)
    return value.strip()


def _safe_text(value: Any) -> str:
    if (
        type(value) is not str
        or _SAFE_TEXT_RE.fullmatch(value.strip()) is None
        or _SECRET_SHAPE_RE.search(value) is not None
        or _PRIVATE_LOCATOR_SHAPE_RE.search(value) is not None
    ):
        raise _error(input_observed=False, complete=False)
    return value.strip()


def _require_input_intent(value: Any) -> CredentialPopupInputIntent:
    if type(value) is not CredentialPopupInputIntent:
        raise _error(input_observed=False, complete=False)
    return value


def popup_intent_banner_text(input_intent: Any) -> str:
    """Return the exact, non-secret banner for one validated operator intent."""

    intent = _require_input_intent(input_intent)
    if intent is CredentialPopupInputIntent.live_registration:
        return LIVE_REGISTRATION_BANNER_TEXT
    return SYNTHETIC_ACCEPTANCE_BANNER_TEXT


def popup_instruction_text(
    context: CredentialPopupContext,
    *,
    input_intent: CredentialPopupInputIntent | None = None,
) -> str:
    """Return the fixed Korean instruction layout with reviewed safe labels."""

    intent = _require_input_intent(input_intent)
    if not isinstance(context, CredentialPopupContext):
        raise _error(input_observed=False, complete=False)
    provider = _safe_label(context.provider).lower()
    purpose = _safe_label(context.purpose).lower().replace("-", "_")
    if provider != "notion" or purpose not in {
        "notion_page_recovery",
        "source_recovery",
    }:
        raise _error(input_observed=False, complete=False)
    account = _safe_label(context.account_label)
    workspace = _safe_label(context.workspace_label)
    task = _safe_text(context.task_summary)
    reason = _safe_text(context.connection_reason)
    if intent is CredentialPopupInputIntent.synthetic_acceptance:
        safety_copy = (
            "경고: 실제 자격 증명은 절대 입력하거나 붙여넣지 마세요.\r\n"
            "고정 합성 문자열만 입력하세요. 내용과 길이는 표시되지 않습니다."
        )
    else:
        safety_copy = (
            "도우미 AI와 채팅에는 자격 증명이 전달되지 않습니다.\r\n"
            "입력값의 글자·기호·길이는 화면에 표시되지 않습니다.\r\n"
            "붙여넣기는 Ctrl+V, Shift+Insert 또는 입력란의 오른쪽 메뉴를 사용하세요."
        )
    return (
        f"{safety_copy}\r\n\r\n"
        f"현재 작업: {task}\r\n"
        f"연결 이유: {reason}\r\n"
        f"연결 대상: Notion / {account} / {workspace}"
    )


def _configure(function: Any, argtypes: list[Any], restype: Any) -> None:
    try:
        function.argtypes = argtypes
        function.restype = restype
    except Exception:
        raise _error(input_observed=False, complete=False) from None


def _loword(value: int) -> int:
    return int(value) & 0xFFFF


def _hiword(value: int) -> int:
    return (int(value) >> 16) & 0xFFFF


def _signed_loword(value: int) -> int:
    result = _loword(value)
    return result - 0x10000 if result & 0x8000 else result


def _signed_hiword(value: int) -> int:
    result = _hiword(value)
    return result - 0x10000 if result & 0x8000 else result


def _wipe_ctypes_buffer(buffer: Any) -> None:
    try:
        ctypes.memset(ctypes.addressof(buffer), 0, ctypes.sizeof(buffer))
    except Exception:
        pass


class _PopupSession:
    def __init__(
        self,
        *,
        request_id: str,
        context: CredentialPopupContext,
        input_intent: CredentialPopupInputIntent,
        user32: Any,
        kernel32: Any,
        imm32: Any,
        gdi32: Any,
        comctl32: Any,
        max_secret_bytes: int,
    ) -> None:
        self.request_id = request_id
        self.context = context
        self.input_intent = _require_input_intent(input_intent)
        self.user32 = user32
        self.kernel32 = kernel32
        self.imm32 = imm32
        self.gdi32 = gdi32
        self.comctl32 = comctl32
        self.max_secret_bytes = max_secret_bytes
        self.owner = wintypes.HWND()
        self.window = wintypes.HWND()
        self.edit = wintypes.HWND()
        self.overlay = wintypes.HWND()
        self.status = wintypes.HWND()
        self.intent_banner = wintypes.HWND()
        self.ok_button = wintypes.HWND()
        self.input_observed = False
        self.input_overlimit = False
        self.complete = False
        self.finished = False
        self.result: HumanSecretInputResult | None = None
        self.failure: CredentialPopupSecretPromptError | None = None
        self._main_proc_callback = _WNDPROC_TYPE(self._main_proc)
        self._edit_proc_callback = _SUBCLASSPROC_TYPE(self._edit_proc)
        self._overlay_proc_callback = _SUBCLASSPROC_TYPE(self._overlay_proc)
        self._class_name = f"WOMCredentialPopup_{request_id}"
        self._intent_banner_text = popup_intent_banner_text(self.input_intent)
        self._instruction = popup_instruction_text(
            context,
            input_intent=self.input_intent,
        )
        if self.input_intent is CredentialPopupInputIntent.live_registration:
            self._banner_background_color = (
                LIVE_REGISTRATION_BANNER_BACKGROUND_COLOR
            )
            self._banner_text_color = LIVE_REGISTRATION_BANNER_TEXT_COLOR
            self._status_empty_text = STATUS_EMPTY_TEXT
            self._status_ready_text = STATUS_READY_TEXT
            self._status_limit_exceeded_text = STATUS_LIMIT_EXCEEDED_TEXT
        else:
            self._banner_background_color = (
                SYNTHETIC_ACCEPTANCE_BANNER_BACKGROUND_COLOR
            )
            self._banner_text_color = SYNTHETIC_ACCEPTANCE_BANNER_TEXT_COLOR
            self._status_empty_text = SYNTHETIC_STATUS_EMPTY_TEXT
            self._status_ready_text = SYNTHETIC_STATUS_READY_TEXT
            self._status_limit_exceeded_text = (
                SYNTHETIC_STATUS_LIMIT_EXCEEDED_TEXT
            )
        self._banner_brush = wintypes.HBRUSH()
        self._ui_font = wintypes.HANDLE()
        self._dpi = 96
        self._window_width = WINDOW_WIDTH
        self._window_height = WINDOW_HEIGHT
        self._previous_dpi_context = wintypes.HANDLE()
        self._dpi_context_active = False

    @staticmethod
    def _context_handle(value: int) -> Any:
        return ctypes.c_void_p(value)

    def _enter_per_monitor_v2_context(self) -> None:
        target = self._context_handle(
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        )
        previous = self.user32.SetThreadDpiAwarenessContext(target)
        if not previous:
            raise RuntimeError
        self._previous_dpi_context = previous
        self._dpi_context_active = True
        try:
            current = self.user32.GetThreadDpiAwarenessContext()
            verified = bool(
                current
                and self.user32.AreDpiAwarenessContextsEqual(
                    current,
                    target,
                )
            )
        except Exception:
            verified = False
        if not verified:
            self._restore_dpi_context()
            raise RuntimeError

    def _restore_dpi_context(self) -> bool:
        if not self._dpi_context_active:
            return True
        original = self._previous_dpi_context
        target = self._context_handle(
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        )
        try:
            replaced = self.user32.SetThreadDpiAwarenessContext(original)
            current = self.user32.GetThreadDpiAwarenessContext()
            restored = bool(
                replaced
                and current
                and self.user32.AreDpiAwarenessContextsEqual(
                    replaced,
                    target,
                )
                and self.user32.AreDpiAwarenessContextsEqual(
                    current,
                    original,
                )
            )
        except Exception:
            restored = False
        if restored:
            self._dpi_context_active = False
            self._previous_dpi_context = wintypes.HANDLE()
        return restored

    def _scale(self, logical_pixels: int) -> int:
        if type(logical_pixels) is not int or logical_pixels < 0:
            raise RuntimeError
        if logical_pixels == 0:
            return 0
        return max(1, (logical_pixels * self._dpi + 48) // 96)

    def _create_window(
        self,
        ex_style: int,
        class_name: str,
        text: str,
        style: int,
        x: int,
        y: int,
        width: int,
        height: int,
        parent: Any,
        control_id: int,
        instance: Any,
    ) -> Any:
        handle = self.user32.CreateWindowExW(
            ex_style,
            class_name,
            text,
            style,
            x,
            y,
            width,
            height,
            parent,
            ctypes.c_void_p(control_id) if control_id else None,
            instance,
            None,
        )
        if not handle:
            raise RuntimeError
        if parent and self.window and parent == self.window:
            self.user32.SendMessageW(
                handle, WM_SETFONT, self._ui_font, True
            )
        return handle

    def _subclass(self, handle: Any, callback: Any, subclass_id: int) -> None:
        if not self.comctl32.SetWindowSubclass(
            handle, callback, subclass_id, 0
        ):
            raise RuntimeError

    def _create_ui_message_font(self) -> None:
        """Own the current DPI-aware Windows message font for every control."""

        dpi = 0
        if self.owner:
            dpi = int(self.user32.GetDpiForWindow(self.owner))
        if dpi <= 0:
            dpi = int(self.user32.GetDpiForSystem())
        if dpi <= 0:
            raise RuntimeError
        self._dpi = dpi
        self._window_width = self._scale(WINDOW_WIDTH)
        self._window_height = self._scale(WINDOW_HEIGHT)
        metrics = _NONCLIENTMETRICSW()
        metrics.cbSize = ctypes.sizeof(_NONCLIENTMETRICSW)
        if not self.user32.SystemParametersInfoForDpi(
            SPI_GETNONCLIENTMETRICS,
            metrics.cbSize,
            ctypes.byref(metrics),
            0,
            dpi,
        ):
            raise RuntimeError
        font = self.gdi32.CreateFontIndirectW(
            ctypes.byref(metrics.lfMessageFont)
        )
        if not font:
            raise RuntimeError
        self._ui_font = font

    def _delete_ui_message_font(self) -> bool:
        if not self._ui_font:
            return True
        try:
            deleted = bool(self.gdi32.DeleteObject(self._ui_font))
        except Exception:
            return False
        if deleted:
            self._ui_font = wintypes.HANDLE()
        return deleted

    def _create_intent_banner_brush(self) -> None:
        brush = self.gdi32.CreateSolidBrush(self._banner_background_color)
        if not brush:
            raise RuntimeError
        self._banner_brush = brush

    def _delete_intent_banner_brush(self) -> bool:
        if not self._banner_brush:
            return True
        try:
            deleted = bool(self.gdi32.DeleteObject(self._banner_brush))
        except Exception:
            return False
        if deleted:
            self._banner_brush = wintypes.HBRUSH()
        return deleted

    def _measure_wrapped_text(self, text: str) -> tuple[int, int]:
        """Measure a message-font row with Win32's own wrapping algorithm."""

        if type(text) is not str or not text or "\r" in text or "\n" in text:
            raise RuntimeError
        device_context = self.user32.GetDC(self.window)
        if not device_context:
            raise RuntimeError
        previous_font: Any = None
        selected = False
        measured = False
        restored = False
        released = False
        content_width = self._scale(CONTENT_WIDTH)
        rect = _RECT(0, 0, content_width, 0)
        try:
            previous_font = self.gdi32.SelectObject(
                device_context,
                self._ui_font,
            )
            if not previous_font:
                raise RuntimeError
            selected = True
            drawn_height = int(
                self.user32.DrawTextW(
                    device_context,
                    text,
                    -1,
                    ctypes.byref(rect),
                    DT_CALCRECT
                    | DT_WORDBREAK
                    | DT_EDITCONTROL
                    | DT_NOPREFIX,
                )
            )
            measured = bool(
                drawn_height > 0
                and int(rect.right) >= int(rect.left)
                and int(rect.right - rect.left) <= content_width
                and int(rect.bottom) > int(rect.top)
            )
        finally:
            if selected:
                try:
                    restored = bool(
                        self.gdi32.SelectObject(
                            device_context,
                            previous_font,
                        )
                    )
                except Exception:
                    restored = False
            try:
                released = bool(
                    self.user32.ReleaseDC(self.window, device_context)
                )
            except Exception:
                released = False
        if not (measured and restored and released):
            raise RuntimeError
        return int(rect.right - rect.left), int(rect.bottom - rect.top)

    def _create_controls(self, instance: Any) -> None:
        content_x = self._scale(CONTENT_X)
        content_width = self._scale(CONTENT_WIDTH)
        text_row_min_height = self._scale(TEXT_ROW_MIN_HEIGHT)
        text_vertical_padding = self._scale(TEXT_VERTICAL_PADDING)
        text_row_gap = self._scale(TEXT_ROW_GAP)
        text_paragraph_gap = self._scale(TEXT_PARAGRAPH_GAP)
        cursor_y = self._scale(INSTRUCTION_TOP)
        banner_width, measured_banner_height = self._measure_wrapped_text(
            self._intent_banner_text
        )
        if banner_width > content_width:
            raise RuntimeError
        banner_height = max(
            self._scale(INTENT_BANNER_HEIGHT),
            measured_banner_height,
        )
        self._create_intent_banner_brush()
        self.intent_banner = self._create_window(
            0,
            "STATIC",
            self._intent_banner_text,
            WS_CHILD
            | WS_VISIBLE
            | SS_CENTER
            | SS_CENTERIMAGE
            | SS_NOPREFIX,
            content_x,
            cursor_y,
            content_width,
            banner_height,
            self.window,
            IDC_INTENT_BANNER,
            instance,
        )
        cursor_y += banner_height + self._scale(INTENT_BANNER_GAP)
        instruction_bottom = cursor_y
        for line in self._instruction.split("\r\n"):
            if not line:
                cursor_y += text_paragraph_gap
                continue
            measured_width, measured_height = self._measure_wrapped_text(
                line
            )
            if measured_width > content_width:
                raise RuntimeError
            row_height = max(
                text_row_min_height,
                measured_height + text_vertical_padding,
            )
            self._create_window(
                0,
                "STATIC",
                line,
                WS_CHILD
                | WS_VISIBLE
                | SS_LEFT
                | SS_NOPREFIX
                | SS_EDITCONTROL,
                content_x,
                cursor_y,
                content_width,
                row_height,
                self.window,
                0,
                instance,
            )
            instruction_bottom = cursor_y + row_height
            cursor_y = instruction_bottom + text_row_gap

        if instruction_bottom > self._scale(INSTRUCTION_BUDGET_BOTTOM):
            raise RuntimeError
        edit_x = self._scale(EDIT_X)
        edit_y = instruction_bottom + self._scale(INPUT_SECTION_GAP)
        edit_width = self._scale(EDIT_WIDTH)
        edit_height = self._scale(EDIT_HEIGHT)
        self.edit = self._create_window(
            0,
            "EDIT",
            "",
            WS_CHILD
            | WS_VISIBLE
            | WS_TABSTOP
            | WS_BORDER
            | WS_CLIPSIBLINGS
            | ES_LEFT
            | ES_AUTOHSCROLL
            | ES_PASSWORD,
            edit_x,
            edit_y,
            edit_width,
            edit_height,
            self.window,
            IDC_EDIT,
            instance,
        )
        self.user32.SendMessageW(
            self.edit, EM_SETLIMITTEXT, self.max_secret_bytes, 0
        )
        # The returned handle is the edit's former association, not proof that
        # detachment succeeded. This child-local edit is destroyed at popup
        # teardown, so that former association is deliberately not restored.
        self.imm32.ImmAssociateContext(self.edit, None)
        self._subclass(self.edit, self._edit_proc_callback, IDC_EDIT)
        self.overlay = self._create_window(
            0,
            "STATIC",
            OVERLAY_TEXT,
            WS_CHILD
            | WS_VISIBLE
            | WS_CLIPSIBLINGS
            | SS_CENTER
            | SS_CENTERIMAGE
            | SS_SUNKEN,
            edit_x,
            edit_y,
            edit_width,
            edit_height,
            self.window,
            IDC_OVERLAY,
            instance,
        )
        self._subclass(self.overlay, self._overlay_proc_callback, IDC_OVERLAY)
        self.user32.SetWindowPos(
            self.overlay,
            HWND_TOP,
            edit_x,
            edit_y,
            edit_width,
            edit_height,
            SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )

        status_measurements = [
            self._measure_wrapped_text(text)
            for text in (
                self._status_empty_text,
                self._status_ready_text,
                self._status_limit_exceeded_text,
            )
        ]
        if any(width > content_width for width, _height in status_measurements):
            raise RuntimeError
        status_height = max(
            text_row_min_height,
            max(height for _width, height in status_measurements)
            + text_vertical_padding,
        )
        status_y = edit_y + edit_height + self._scale(STATUS_GAP)
        self.status = self._create_window(
            0,
            "STATIC",
            self._status_empty_text,
            WS_CHILD | WS_VISIBLE | SS_LEFT | SS_NOPREFIX,
            content_x,
            status_y,
            content_width,
            status_height,
            self.window,
            IDC_STATUS,
            instance,
        )
        button_y = status_y + status_height + self._scale(BUTTON_GAP)
        button_height = self._scale(BUTTON_HEIGHT)
        if (
            button_y + button_height
            > self._scale(WINDOW_CLIENT_SAFE_BOTTOM)
        ):
            raise RuntimeError
        self.ok_button = self._create_window(
            0,
            "BUTTON",
            OK_TEXT,
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON,
            self._scale(BUTTON_OK_X),
            button_y,
            self._scale(BUTTON_WIDTH),
            button_height,
            self.window,
            IDOK,
            instance,
        )
        self._create_window(
            0,
            "BUTTON",
            CANCEL_TEXT,
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
            self._scale(BUTTON_CANCEL_X),
            button_y,
            self._scale(BUTTON_WIDTH),
            button_height,
            self.window,
            IDCANCEL,
            instance,
        )
        self.user32.EnableWindow(self.ok_button, False)

    def _verify_ime_detached_before_show(self) -> None:
        """Fail closed before ShowWindow if the token edit still owns an IME."""

        try:
            current_context = self.imm32.ImmGetContext(self.edit)
        except Exception:
            current_context = None
            failure = _error(input_observed=False, complete=False)
            self._finish(None, failure)
            raise failure
        if current_context:
            try:
                self.imm32.ImmReleaseContext(self.edit, current_context)
            except Exception:
                pass
            failure = _error(input_observed=False, complete=False)
            self._finish(None, failure)
            raise failure

    def _edit_nonempty(self) -> bool:
        length = int(self.user32.GetWindowTextLengthW(self.edit))
        if length < 0:
            raise RuntimeError
        return length > 0

    def _note_edit_change(self) -> None:
        nonempty = self._edit_nonempty()
        if nonempty:
            self.input_observed = True
        else:
            # A limit notification remains sticky through partial deletion.
            # Only a fully empty edit starts a clean retry.
            self.input_overlimit = False
        self.user32.EnableWindow(
            self.ok_button, nonempty and not self.input_overlimit
        )
        self.user32.SetWindowTextW(
            self.status,
            self._status_limit_exceeded_text
            if self.input_overlimit
            else self._status_ready_text
            if nonempty
            else self._status_empty_text,
        )
        self.user32.HideCaret(self.edit)

    def _note_edit_overlimit(self) -> None:
        self.input_observed = True
        self.input_overlimit = True
        self.user32.EnableWindow(self.ok_button, False)
        self.user32.SetWindowTextW(
            self.status, self._status_limit_exceeded_text
        )
        self.user32.HideCaret(self.edit)

    def _clear_native_edit(self) -> bool:
        if not self.edit:
            return True
        ok = bool(self.user32.SetWindowTextW(self.edit, ""))
        try:
            self.user32.SendMessageW(self.edit, EM_EMPTYUNDOBUFFER, 0, 0)
        except Exception:
            ok = False
        return ok

    def _destroy(self) -> bool:
        if not self.window:
            return True
        try:
            destroyed = bool(self.user32.DestroyWindow(self.window))
        except Exception:
            return False
        if destroyed:
            self.window = wintypes.HWND()
        return destroyed

    def _finish(
        self,
        result: HumanSecretInputResult | None,
        failure: CredentialPopupSecretPromptError | None = None,
    ) -> None:
        if self.finished:
            if result is not None and result.secret is not None:
                result.secret[:] = b"\x00" * len(result.secret)
            return
        cleanup_ok = self._clear_native_edit()
        destroy_ok = self._destroy()
        self.finished = True
        if not cleanup_ok or not destroy_ok:
            if result is not None and result.secret is not None:
                result.secret[:] = b"\x00" * len(result.secret)
            failure = _error(
                input_observed=self.input_observed,
                complete=self.complete,
            )
            result = None
        self.result = result
        self.failure = failure

    def _cancel(self) -> None:
        self._finish(
            HumanSecretInputResult(
                secret=None,
                credential_input_received=self.input_observed,
                complete_line_received=False,
                cancelled=True,
            )
        )

    def _submit(self) -> None:
        if self.finished:
            return
        try:
            if not self._edit_nonempty():
                return
            self.input_observed = True
            self.complete = True
            if self.input_overlimit:
                self._finish(
                    None,
                    _error(
                        input_observed=True,
                        complete=True,
                        invalid=True,
                    ),
                )
                return
            length = int(self.user32.GetWindowTextLengthW(self.edit))
            if length <= 0 or length > self.max_secret_bytes:
                self._finish(
                    None,
                    _error(
                        input_observed=True,
                        complete=True,
                        invalid=True,
                    ),
                )
                return
            utf16_buffer = (ctypes.c_wchar * (self.max_secret_bytes + 1))()
            utf8_buffer = (ctypes.c_ubyte * self.max_secret_bytes)()
            output = bytearray()
            try:
                copied = int(
                    self.user32.GetWindowTextW(
                        self.edit,
                        utf16_buffer,
                        self.max_secret_bytes + 1,
                    )
                )
                if copied != length:
                    raise RuntimeError
                for index in range(copied):
                    codepoint = ord(utf16_buffer[index])
                    if codepoint < 0x20 or codepoint == 0x7F:
                        self._finish(
                            None,
                            _error(
                                input_observed=True,
                                complete=True,
                                invalid=True,
                            ),
                        )
                        return
                encoded = int(
                    self.kernel32.WideCharToMultiByte(
                        CP_UTF8,
                        WC_ERR_INVALID_CHARS,
                        utf16_buffer,
                        copied,
                        utf8_buffer,
                        self.max_secret_bytes,
                        None,
                        None,
                    )
                )
                if encoded <= 0 or encoded > self.max_secret_bytes:
                    self._finish(
                        None,
                        _error(
                            input_observed=True,
                            complete=True,
                            invalid=True,
                        ),
                    )
                    return
                output = bytearray(encoded)
                output_view = (ctypes.c_ubyte * encoded).from_buffer(output)
                ctypes.memmove(
                    ctypes.addressof(output_view),
                    ctypes.addressof(utf8_buffer),
                    encoded,
                )
                result = HumanSecretInputResult(
                    secret=output,
                    credential_input_received=True,
                    complete_line_received=True,
                    cancelled=False,
                )
                self._finish(result)
                if self.failure is not None:
                    output[:] = b"\x00" * len(output)
            except CredentialPopupSecretPromptError:
                raise
            except Exception:
                output[:] = b"\x00" * len(output)
                self._finish(
                    None,
                    _error(input_observed=True, complete=True),
                )
            finally:
                _wipe_ctypes_buffer(utf16_buffer)
                _wipe_ctypes_buffer(utf8_buffer)
        except CredentialPopupSecretPromptError as error:
            self._finish(None, error)
        except Exception:
            self._finish(
                None,
                _error(
                    input_observed=self.input_observed,
                    complete=self.complete,
                ),
            )

    def _show_context_menu(self, lparam: int) -> None:
        menu = self.user32.CreatePopupMenu()
        if not menu:
            raise RuntimeError
        try:
            if not self.user32.AppendMenuW(
                menu, MF_STRING, ID_POPUP_PASTE, PASTE_MENU_TEXT
            ) or not self.user32.AppendMenuW(
                menu, MF_STRING, ID_POPUP_CLEAR, CLEAR_MENU_TEXT
            ):
                raise RuntimeError
            x = _signed_loword(lparam)
            y = _signed_hiword(lparam)
            if x == -1 and y == -1:
                rect = _RECT()
                if not self.user32.GetWindowRect(self.edit, ctypes.byref(rect)):
                    raise RuntimeError
                x, y = int(rect.left), int(rect.bottom)
            command = int(
                self.user32.TrackPopupMenuEx(
                    menu,
                    TPM_RETURNCMD | TPM_NONOTIFY,
                    x,
                    y,
                    self.edit,
                    None,
                )
            )
            if command == ID_POPUP_PASTE:
                self.user32.SendMessageW(self.edit, WM_PASTE, 0, 0)
            elif command == ID_POPUP_CLEAR:
                self.user32.SendMessageW(self.edit, EM_SETSEL, 0, -1)
                self.user32.SendMessageW(self.edit, WM_CLEAR, 0, 0)
        finally:
            self.user32.DestroyMenu(menu)

    def _main_proc(self, hwnd: Any, message: int, wparam: int, lparam: int) -> int:
        try:
            if message == WM_CREATE:
                self.window = hwnd
                self._create_controls(self.kernel32.GetModuleHandleW(None))
                return 0
            if (
                message == WM_CTLCOLORSTATIC
                and self.intent_banner
                and int(lparam) == int(self.intent_banner)
            ):
                text_result = int(
                    self.gdi32.SetTextColor(
                        wparam,
                        self._banner_text_color,
                    )
                )
                background_result = int(
                    self.gdi32.SetBkColor(
                        wparam,
                        self._banner_background_color,
                    )
                )
                if (
                    text_result == CLR_INVALID
                    or background_result == CLR_INVALID
                    or not self._banner_brush
                ):
                    raise RuntimeError
                return int(self._banner_brush)
            if message == WM_COMMAND:
                control_id = _loword(wparam)
                notification = _hiword(wparam)
                if control_id == IDC_EDIT and notification == EN_CHANGE:
                    self._note_edit_change()
                    return 0
                if control_id == IDC_EDIT and notification == EN_MAXTEXT:
                    self._note_edit_overlimit()
                    return 0
                if control_id == IDOK and notification == BN_CLICKED:
                    self._submit()
                    return 0
                if control_id == IDCANCEL and notification == BN_CLICKED:
                    self._cancel()
                    return 0
            if message == WM_CLOSE:
                self._cancel()
                return 0
            if message == WM_DESTROY:
                self.user32.PostQuitMessage(0)
                return 0
            return int(self.user32.DefWindowProcW(hwnd, message, wparam, lparam))
        except Exception:
            self._finish(
                None,
                _error(
                    input_observed=self.input_observed,
                    complete=self.complete,
                ),
            )
            return 0

    def _edit_proc(
        self,
        hwnd: Any,
        message: int,
        wparam: int,
        lparam: int,
        subclass_id: int,
        _reference: int,
    ) -> int:
        try:
            if message == WM_NCDESTROY:
                self.comctl32.RemoveWindowSubclass(
                    hwnd, self._edit_proc_callback, subclass_id
                )
                result = int(
                    self.comctl32.DefSubclassProc(
                        hwnd, message, wparam, lparam
                    )
                )
                return result
            if message in {WM_COPY, WM_CUT}:
                return 0
            if message == WM_CONTEXTMENU:
                self._show_context_menu(lparam)
                return 0
            if message == WM_KEYDOWN and int(wparam) == VK_RETURN:
                self._submit()
                return 0
            if message == WM_KEYDOWN and int(wparam) == VK_ESCAPE:
                self._cancel()
                return 0
            result = int(
                self.comctl32.DefSubclassProc(hwnd, message, wparam, lparam)
            )
            if message in {WM_SETFOCUS, WM_LBUTTONDOWN}:
                self.user32.HideCaret(hwnd)
            return result
        except Exception:
            self._finish(
                None,
                _error(
                    input_observed=self.input_observed,
                    complete=self.complete,
                ),
            )
            return 0

    def _overlay_proc(
        self,
        hwnd: Any,
        message: int,
        wparam: int,
        lparam: int,
        subclass_id: int,
        _reference: int,
    ) -> int:
        try:
            if message == WM_NCDESTROY:
                self.comctl32.RemoveWindowSubclass(
                    hwnd, self._overlay_proc_callback, subclass_id
                )
                result = int(
                    self.comctl32.DefSubclassProc(
                        hwnd, message, wparam, lparam
                    )
                )
                return result
            if message == WM_NCHITTEST:
                return HTTRANSPARENT
            if message in {WM_LBUTTONDOWN, WM_SETFOCUS}:
                self.user32.SetFocus(self.edit)
                self.user32.HideCaret(self.edit)
                return 0
            return int(
                self.comctl32.DefSubclassProc(hwnd, message, wparam, lparam)
            )
        except Exception:
            self._finish(
                None,
                _error(
                    input_observed=self.input_observed,
                    complete=self.complete,
                ),
            )
            return 0

    def _center_position(self) -> tuple[int, int]:
        rect = _RECT()
        if self.owner and self.user32.GetWindowRect(self.owner, ctypes.byref(rect)):
            width = int(rect.right - rect.left)
            height = int(rect.bottom - rect.top)
            return (
                int(rect.left + max(0, (width - self._window_width) // 2)),
                int(rect.top + max(0, (height - self._window_height) // 2)),
            )
        screen_width = int(self.user32.GetSystemMetrics(0))
        screen_height = int(self.user32.GetSystemMetrics(1))
        return (
            max(0, (screen_width - self._window_width) // 2),
            max(0, (screen_height - self._window_height) // 2),
        )

    def run(self) -> HumanSecretInputResult:
        instance = self.kernel32.GetModuleHandleW(None)
        class_registered = False
        try:
            # A fresh Python child is DPI-unaware unless this popup thread
            # establishes PMv2 before owner/DPI/window calls. Without this
            # lease Windows would scale our already-scaled geometry again.
            self._enter_per_monitor_v2_context()
            window_class = _WNDCLASSEXW()
            window_class.cbSize = ctypes.sizeof(_WNDCLASSEXW)
            window_class.style = CS_HREDRAW | CS_VREDRAW
            window_class.lpfnWndProc = self._main_proc_callback
            window_class.hInstance = instance
            window_class.hCursor = self.user32.LoadCursorW(
                None,
                ctypes.c_void_p(32512),
            )
            window_class.hbrBackground = ctypes.c_void_p(COLOR_WINDOW + 1)
            window_class.lpszClassName = self._class_name
            if not self.user32.RegisterClassExW(ctypes.byref(window_class)):
                raise RuntimeError
            class_registered = True
            self.owner = self.user32.GetForegroundWindow()
            self._create_ui_message_font()
            x, y = self._center_position()
            self.window = self._create_window(
                WS_EX_DLGMODALFRAME | WS_EX_CONTROLPARENT,
                self._class_name,
                POPUP_TITLE,
                WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
                x,
                y,
                self._window_width,
                self._window_height,
                self.owner,
                0,
                instance,
            )
            self._verify_ime_detached_before_show()
            self.user32.ShowWindow(self.window, SW_SHOW)
            self.user32.UpdateWindow(self.window)
            self.user32.SetForegroundWindow(self.window)
            self.user32.SetActiveWindow(self.window)
            self.user32.SetFocus(self.edit)
            self.user32.HideCaret(self.edit)
            message = _MSG()
            while not self.finished:
                status = int(self.user32.GetMessageW(ctypes.byref(message), None, 0, 0))
                if status == -1:
                    self._finish(
                        None,
                        _error(
                            input_observed=self.input_observed,
                            complete=self.complete,
                        ),
                    )
                    break
                if status == 0:
                    break
                if self.user32.IsDialogMessageW(
                    self.window,
                    ctypes.byref(message),
                ):
                    continue
                self.user32.TranslateMessage(ctypes.byref(message))
                self.user32.DispatchMessageW(ctypes.byref(message))
            if self.failure is not None:
                raise self.failure
            if not isinstance(self.result, HumanSecretInputResult):
                raise _error(
                    input_observed=self.input_observed,
                    complete=self.complete,
                )
            return self.result
        except CredentialPopupSecretPromptError:
            raise
        except Exception:
            raise _error(
                input_observed=self.input_observed,
                complete=self.complete,
            ) from None
        finally:
            cleanup_failed = False
            if self.window:
                cleanup_failed = not self._clear_native_edit()
                cleanup_failed = not self._destroy() or cleanup_failed
            # Every child control is gone before its owned GDI objects are
            # deleted.
            cleanup_failed = (
                not self._delete_intent_banner_brush() or cleanup_failed
            )
            cleanup_failed = not self._delete_ui_message_font() or cleanup_failed
            if class_registered:
                try:
                    if not self.user32.UnregisterClassW(
                        self._class_name,
                        instance,
                    ):
                        cleanup_failed = True
                except Exception:
                    cleanup_failed = True
            # Restore only after every PMv2 window/font object is gone.
            cleanup_failed = not self._restore_dpi_context() or cleanup_failed
            if cleanup_failed:
                if self.result is not None and self.result.secret is not None:
                    self.result.secret[:] = b"\x00" * len(self.result.secret)
                self.result = None
                raise _error(
                    input_observed=self.input_observed,
                    complete=self.complete,
                )


def _configure_native(
    user32: Any, kernel32: Any, imm32: Any, gdi32: Any, comctl32: Any
) -> None:
    pointer = ctypes.c_void_p
    _configure(kernel32.GetModuleHandleW, [wintypes.LPCWSTR], wintypes.HMODULE)
    _configure(
        kernel32.WideCharToMultiByte,
        [
            wintypes.UINT,
            wintypes.DWORD,
            wintypes.LPCWSTR,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ],
        ctypes.c_int,
    )
    _configure(user32.RegisterClassExW, [ctypes.POINTER(_WNDCLASSEXW)], wintypes.ATOM)
    _configure(user32.UnregisterClassW, [wintypes.LPCWSTR, wintypes.HINSTANCE], wintypes.BOOL)
    _configure(user32.CreateWindowExW, [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, pointer], wintypes.HWND)
    _configure(user32.DefWindowProcW, [wintypes.HWND, wintypes.UINT, _WPARAM, _LPARAM], _LRESULT)
    _configure(user32.GetForegroundWindow, [], wintypes.HWND)
    _configure(
        user32.SetThreadDpiAwarenessContext,
        [wintypes.HANDLE],
        wintypes.HANDLE,
    )
    _configure(
        user32.GetThreadDpiAwarenessContext,
        [],
        wintypes.HANDLE,
    )
    _configure(
        user32.AreDpiAwarenessContextsEqual,
        [wintypes.HANDLE, wintypes.HANDLE],
        wintypes.BOOL,
    )
    _configure(user32.GetDpiForWindow, [wintypes.HWND], wintypes.UINT)
    _configure(user32.GetDpiForSystem, [], wintypes.UINT)
    _configure(
        user32.SystemParametersInfoForDpi,
        [
            wintypes.UINT,
            wintypes.UINT,
            pointer,
            wintypes.UINT,
            wintypes.UINT,
        ],
        wintypes.BOOL,
    )
    _configure(user32.GetWindowRect, [wintypes.HWND, ctypes.POINTER(_RECT)], wintypes.BOOL)
    _configure(user32.GetSystemMetrics, [ctypes.c_int], ctypes.c_int)
    _configure(user32.SetWindowPos, [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.BOOL)
    _configure(user32.ShowWindow, [wintypes.HWND, ctypes.c_int], wintypes.BOOL)
    _configure(user32.UpdateWindow, [wintypes.HWND], wintypes.BOOL)
    _configure(user32.SetForegroundWindow, [wintypes.HWND], wintypes.BOOL)
    _configure(user32.SetActiveWindow, [wintypes.HWND], wintypes.HWND)
    _configure(user32.EnableWindow, [wintypes.HWND, wintypes.BOOL], wintypes.BOOL)
    _configure(user32.SetFocus, [wintypes.HWND], wintypes.HWND)
    _configure(user32.HideCaret, [wintypes.HWND], wintypes.BOOL)
    _configure(user32.GetWindowTextLengthW, [wintypes.HWND], ctypes.c_int)
    _configure(user32.GetWindowTextW, [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int)
    _configure(user32.SetWindowTextW, [wintypes.HWND, wintypes.LPCWSTR], wintypes.BOOL)
    _configure(user32.SendMessageW, [wintypes.HWND, wintypes.UINT, _WPARAM, _LPARAM], _LRESULT)
    _configure(user32.DestroyWindow, [wintypes.HWND], wintypes.BOOL)
    _configure(user32.PostQuitMessage, [ctypes.c_int], None)
    _configure(user32.GetMessageW, [ctypes.POINTER(_MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT], wintypes.BOOL)
    _configure(user32.IsDialogMessageW, [wintypes.HWND, ctypes.POINTER(_MSG)], wintypes.BOOL)
    _configure(user32.TranslateMessage, [ctypes.POINTER(_MSG)], wintypes.BOOL)
    _configure(user32.DispatchMessageW, [ctypes.POINTER(_MSG)], _LRESULT)
    _configure(user32.LoadCursorW, [wintypes.HINSTANCE, pointer], wintypes.HANDLE)
    _configure(user32.CreatePopupMenu, [], wintypes.HMENU)
    _configure(user32.AppendMenuW, [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR], wintypes.BOOL)
    _configure(user32.TrackPopupMenuEx, [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.HWND, pointer], wintypes.UINT)
    _configure(user32.DestroyMenu, [wintypes.HMENU], wintypes.BOOL)
    _configure(user32.GetDC, [wintypes.HWND], wintypes.HDC)
    _configure(user32.ReleaseDC, [wintypes.HWND, wintypes.HDC], ctypes.c_int)
    _configure(
        user32.DrawTextW,
        [
            wintypes.HDC,
            wintypes.LPCWSTR,
            ctypes.c_int,
            ctypes.POINTER(_RECT),
            wintypes.UINT,
        ],
        ctypes.c_int,
    )
    _configure(imm32.ImmAssociateContext, [wintypes.HWND, wintypes.HANDLE], wintypes.HANDLE)
    _configure(imm32.ImmGetContext, [wintypes.HWND], wintypes.HANDLE)
    _configure(
        imm32.ImmReleaseContext,
        [wintypes.HWND, wintypes.HANDLE],
        wintypes.BOOL,
    )
    _configure(
        gdi32.CreateFontIndirectW,
        [ctypes.POINTER(_LOGFONTW)],
        wintypes.HANDLE,
    )
    _configure(
        gdi32.CreateSolidBrush,
        [wintypes.DWORD],
        wintypes.HBRUSH,
    )
    _configure(
        gdi32.SetTextColor,
        [wintypes.HDC, wintypes.DWORD],
        wintypes.DWORD,
    )
    _configure(
        gdi32.SetBkColor,
        [wintypes.HDC, wintypes.DWORD],
        wintypes.DWORD,
    )
    _configure(gdi32.DeleteObject, [wintypes.HANDLE], wintypes.BOOL)
    _configure(
        gdi32.SelectObject,
        [wintypes.HDC, wintypes.HANDLE],
        wintypes.HANDLE,
    )
    _configure(
        comctl32.SetWindowSubclass,
        [wintypes.HWND, _SUBCLASSPROC_TYPE, ctypes.c_size_t, ctypes.c_size_t],
        wintypes.BOOL,
    )
    _configure(
        comctl32.RemoveWindowSubclass,
        [wintypes.HWND, _SUBCLASSPROC_TYPE, ctypes.c_size_t],
        wintypes.BOOL,
    )
    _configure(
        comctl32.DefSubclassProc,
        [wintypes.HWND, wintypes.UINT, _WPARAM, _LPARAM],
        _LRESULT,
    )


def _prompt_secret_in_native_popup(
    *,
    request_id: str,
    context: CredentialPopupContext,
    input_intent: CredentialPopupInputIntent | None = None,
    user32: Any | None = None,
    kernel32: Any | None = None,
    imm32: Any | None = None,
    gdi32: Any | None = None,
    comctl32: Any | None = None,
    platform_name: str | None = None,
    max_secret_bytes: int = 5 * 512,
) -> HumanSecretInputResult:
    """Run one modal Unicode popup and return a mutable UTF-8 secret buffer."""

    intent = _require_input_intent(input_intent)
    if (platform_name or os.name) != "nt":
        raise _error(input_observed=False, complete=False)
    if _REQUEST_ID_RE.fullmatch(str(request_id or "")) is None:
        raise _error(input_observed=False, complete=False)
    if type(max_secret_bytes) is not int or not 1 <= max_secret_bytes <= 65535:
        raise _error(input_observed=False, complete=False)
    popup_instruction_text(context, input_intent=intent)
    try:
        if (
            user32 is None
            or kernel32 is None
            or imm32 is None
            or gdi32 is None
            or comctl32 is None
        ):
            loader = getattr(ctypes, "WinDLL", None)
            if loader is None:
                raise OSError
            user32 = user32 or loader("user32", use_last_error=True)
            kernel32 = kernel32 or loader("kernel32", use_last_error=True)
            imm32 = imm32 or loader("imm32", use_last_error=True)
            gdi32 = gdi32 or loader("gdi32", use_last_error=True)
            comctl32 = comctl32 or loader("comctl32", use_last_error=True)
        _configure_native(user32, kernel32, imm32, gdi32, comctl32)
        return _PopupSession(
            request_id=request_id,
            context=context,
            input_intent=intent,
            user32=user32,
            kernel32=kernel32,
            imm32=imm32,
            gdi32=gdi32,
            comctl32=comctl32,
            max_secret_bytes=max_secret_bytes,
        ).run()
    except CredentialPopupSecretPromptError:
        raise
    except _HumanSecretInputEvidenceError:
        raise
    except Exception:
        raise _error(input_observed=False, complete=False) from None


__all__ = [
    "CANCEL_TEXT",
    "CLEAR_MENU_TEXT",
    "CredentialPopupContext",
    "CredentialPopupInputIntent",
    "CredentialPopupSecretPromptError",
    "LIVE_REGISTRATION_BANNER_BACKGROUND_COLOR",
    "LIVE_REGISTRATION_BANNER_TEXT",
    "LIVE_REGISTRATION_BANNER_TEXT_COLOR",
    "OK_TEXT",
    "OVERLAY_TEXT",
    "PASTE_MENU_TEXT",
    "POPUP_TITLE",
    "STATUS_EMPTY_TEXT",
    "STATUS_LIMIT_EXCEEDED_TEXT",
    "STATUS_READY_TEXT",
    "SYNTHETIC_ACCEPTANCE_BANNER_BACKGROUND_COLOR",
    "SYNTHETIC_ACCEPTANCE_BANNER_TEXT",
    "SYNTHETIC_ACCEPTANCE_BANNER_TEXT_COLOR",
    "SYNTHETIC_STATUS_EMPTY_TEXT",
    "SYNTHETIC_STATUS_LIMIT_EXCEEDED_TEXT",
    "SYNTHETIC_STATUS_READY_TEXT",
    "popup_intent_banner_text",
    "popup_instruction_text",
]
