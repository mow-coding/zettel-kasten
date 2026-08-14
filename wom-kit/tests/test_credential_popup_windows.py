from __future__ import annotations

import ctypes
import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from wom_kit import credential_popup_windows as popup
from wom_kit.credential_secure_intake import HumanSecretInputResult


REQUEST_ID = "intake_abcdef1234567890"
CONTEXT = popup.CredentialPopupContext(
    provider="notion",
    purpose="notion_page_recovery",
    account_label="개인 계정",
    workspace_label="자료 보관함",
    task_summary="검토한 Notion 페이지를 WOM 아카이브로 복구하고 있습니다.",
    connection_reason="복구를 계속하려면 Notion 작업공간 연결을 확인해야 합니다.",
)


class FakeKernel32:
    def __init__(self) -> None:
        self.convert_calls: list[tuple[int, int]] = []

    def GetModuleHandleW(self, _name):
        return 7001

    def WideCharToMultiByte(
        self,
        code_page,
        flags,
        source,
        source_length,
        destination,
        destination_size,
        _default_character,
        _used_default,
    ):
        self.convert_calls.append((int(code_page), int(flags)))
        text = "".join(source[index] for index in range(int(source_length)))
        encoded = text.encode("utf-8")
        if len(encoded) > int(destination_size):
            return 0
        ctypes.memmove(destination, encoded, len(encoded))
        return len(encoded)


class FakeImm32:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object]] = []
        self.get_calls: list[object] = []
        self.release_calls: list[tuple[object, object]] = []
        self.associate_return = 9001
        self.current_context = 0

    def ImmAssociateContext(self, hwnd, context):
        self.calls.append((hwnd, context))
        return self.associate_return

    def ImmGetContext(self, hwnd):
        self.get_calls.append(hwnd)
        return self.current_context

    def ImmReleaseContext(self, hwnd, context):
        self.release_calls.append((hwnd, context))
        return True


class FakeGdi32:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.created_fonts: list[dict[str, object]] = []
        self.created_brushes: list[int] = []
        self.deleted_fonts: list[object] = []
        self.deleted_brushes: list[object] = []
        self.text_colors: list[tuple[object, int]] = []
        self.background_colors: list[tuple[object, int]] = []
        self.selected_by_dc: dict[object, object] = {}
        self.delete_font_result = True
        self.delete_brush_result = True

    def CreateFontIndirectW(self, font_pointer):
        font = font_pointer._obj
        self.created_fonts.append(
            {"height": int(font.lfHeight), "face": str(font.lfFaceName)}
        )
        self.events.append("create_message_font")
        return 8001

    def DeleteObject(self, font):
        if font == 8001:
            self.deleted_fonts.append(font)
            self.events.append("delete_message_font")
            return self.delete_font_result
        self.deleted_brushes.append(font)
        self.events.append("delete_intent_banner_brush")
        return self.delete_brush_result

    def CreateSolidBrush(self, color):
        self.created_brushes.append(int(color))
        self.events.append("create_intent_banner_brush")
        return 8002

    def SetTextColor(self, device_context, color):
        self.text_colors.append((device_context, int(color)))
        return 0

    def SetBkColor(self, device_context, color):
        self.background_colors.append((device_context, int(color)))
        return 0

    def SelectObject(self, device_context, selected_object):
        previous = self.selected_by_dc.get(device_context, 7001)
        self.selected_by_dc[device_context] = selected_object
        return previous


class FakeComctl32:
    def __init__(self) -> None:
        self.subclasses: list[tuple[object, object, int, int]] = []
        self.removed: list[tuple[object, object, int]] = []
        self.default_messages: list[tuple[object, int, int, int]] = []
        self.events: list[tuple[str, object, int]] = []

    def SetWindowSubclass(self, hwnd, callback, subclass_id, reference):
        self.subclasses.append((hwnd, callback, int(subclass_id), int(reference)))
        return True

    def RemoveWindowSubclass(self, hwnd, callback, subclass_id):
        self.removed.append((hwnd, callback, int(subclass_id)))
        self.events.append(("remove", hwnd, int(subclass_id)))
        return True

    def DefSubclassProc(self, hwnd, message, wparam, lparam):
        self.default_messages.append(
            (hwnd, int(message), int(wparam), int(lparam))
        )
        self.events.append(("default", hwnd, int(message)))
        return 17


class FakeUser32:
    def __init__(self) -> None:
        self.next_handle = 100
        self.created: list[dict[str, object]] = []
        self.text_by_handle: dict[object, str] = {}
        self.messages: list[tuple[object, int, object, object]] = []
        self.enabled: list[tuple[object, bool]] = []
        self.focused: list[object] = []
        self.hidden_carets: list[object] = []
        self.destroyed: list[object] = []
        self.menu_items: list[tuple[int, str]] = []
        self.menu_command = 0
        self.paste_text = "붙여넣은-합성값"
        self.fail_clear = False
        self.fail_destroy = False
        self.raise_length = False
        self.owner_rect = (100, 200, 1100, 900)
        self.owner_handle = 3001
        self.events: list[str] = []
        self.registered_wndproc = None
        self.message_index = 0
        self.full_run_text = "synthetic-full-message-loop"
        self.dpi = 144
        self.dpi_calls: list[object] = []
        self.nonclient_metrics_calls: list[tuple[int, int]] = []
        self.measurements: list[dict[str, int | str]] = []
        self.dialog_message_calls = 0
        self.original_dpi_context = 4001
        self.current_dpi_context = self.original_dpi_context
        self.dpi_context_calls: list[int] = []
        self.fail_dpi_enter = False
        self.fail_dpi_restore = False
        self.fail_dpi_verify = False
        self.enter_current_override: int | None = None
        self.restore_return_override: int | None = None
        self.restore_current_override: int | None = None

    def _control_id(self, handle) -> int:
        for row in self.created:
            if row["handle"] == handle:
                return int(row["control_id"])
        return 0

    def CreateWindowExW(
        self,
        ex_style,
        class_name,
        text,
        style,
        x,
        y,
        width,
        height,
        parent,
        control_id,
        instance,
        _param,
    ):
        self.next_handle += 1
        handle = self.next_handle
        numeric_control_id = int(control_id.value) if control_id else 0
        row = {
            "handle": handle,
            "ex_style": int(ex_style),
            "class": class_name,
            "text": text,
            "style": int(style),
            "x": int(x),
            "y": int(y),
            "width": int(width),
            "height": int(height),
            "parent": parent,
            "control_id": numeric_control_id,
            "instance": instance,
        }
        self.created.append(row)
        self.text_by_handle[handle] = text
        self.events.append(f"create:{class_name}:{numeric_control_id}")
        if class_name.startswith("WOMCredentialPopup_"):
            if self.registered_wndproc is None:
                raise AssertionError("window class was not registered")
            self.registered_wndproc(handle, popup.WM_CREATE, 0, 0)
        return handle

    def SendMessageW(self, hwnd, message, wparam, lparam):
        self.messages.append((hwnd, int(message), wparam, lparam))
        if int(message) == popup.EM_EMPTYUNDOBUFFER:
            self.events.append("empty_undo")
        if int(message) == popup.WM_PASTE:
            self.text_by_handle[hwnd] = self.paste_text
        elif int(message) == popup.WM_CLEAR:
            self.text_by_handle[hwnd] = ""
        return 0

    def GetDpiForWindow(self, hwnd):
        self.dpi_calls.append(hwnd)
        self.events.append("get_window_dpi")
        return self.dpi

    @staticmethod
    def _dpi_context_value(context) -> int:
        raw = context.value if hasattr(context, "value") else context
        return int(raw)

    def SetThreadDpiAwarenessContext(self, context):
        target = self._dpi_context_value(context)
        pmv2 = ctypes.c_void_p(
            popup.DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        ).value
        if target == int(pmv2):
            self.events.append("enter_dpi_context")
            if self.fail_dpi_enter:
                return 0
        else:
            self.events.append("restore_dpi_context")
            if self.fail_dpi_restore:
                return 0
        previous = self.current_dpi_context
        if target == int(pmv2):
            self.current_dpi_context = (
                target
                if self.enter_current_override is None
                else self.enter_current_override
            )
        else:
            self.current_dpi_context = (
                target
                if self.restore_current_override is None
                else self.restore_current_override
            )
        self.dpi_context_calls.append(target)
        if target != int(pmv2) and self.restore_return_override is not None:
            return self.restore_return_override
        return previous

    def GetThreadDpiAwarenessContext(self):
        return self.current_dpi_context

    def AreDpiAwarenessContextsEqual(self, first, second):
        if self.fail_dpi_verify:
            return False
        return self._dpi_context_value(first) == self._dpi_context_value(second)

    def GetDpiForSystem(self):
        self.dpi_calls.append("system")
        return self.dpi

    def SystemParametersInfoForDpi(
        self,
        action,
        size,
        metrics_pointer,
        _flags,
        dpi,
    ):
        self.nonclient_metrics_calls.append((int(action), int(dpi)))
        metrics = metrics_pointer._obj
        if int(size) != ctypes.sizeof(popup._NONCLIENTMETRICSW):
            return False
        metrics.lfMessageFont.lfHeight = -max(
            1,
            (11 * int(dpi) + 48) // 96,
        )
        metrics.lfMessageFont.lfFaceName = "Segoe UI"
        return True

    def GetDC(self, _hwnd):
        return 6002

    def ReleaseDC(self, _hwnd, _device_context):
        return 1

    def DrawTextW(self, _device_context, text, _length, rect_pointer, flags):
        rect = rect_pointer._obj
        available_width = int(rect.right - rect.left)
        logical_text_width = sum(
            7 if ord(character) < 128 else 14 for character in text
        )
        text_width = (logical_text_width * self.dpi + 48) // 96
        line_count = max(1, (text_width + available_width - 1) // available_width)
        rect.right = rect.left + min(available_width, text_width)
        line_height = max(1, (20 * self.dpi + 48) // 96)
        rect.bottom = rect.top + (line_height * line_count)
        self.measurements.append(
            {
                "text": text,
                "width": int(rect.right - rect.left),
                "height": int(rect.bottom - rect.top),
                "flags": int(flags),
            }
        )
        return int(rect.bottom - rect.top)

    def SetWindowPos(self, *_args):
        return True

    def EnableWindow(self, hwnd, enabled):
        self.enabled.append((hwnd, bool(enabled)))
        self.events.append(f"enable:{hwnd}:{bool(enabled)}")
        return True

    def SetFocus(self, hwnd):
        self.focused.append(hwnd)
        return 0

    def HideCaret(self, hwnd):
        self.hidden_carets.append(hwnd)
        return True

    def GetWindowTextLengthW(self, hwnd):
        if self.raise_length:
            raise RuntimeError("native detail must not escape")
        return len(self.text_by_handle.get(hwnd, ""))

    def GetWindowTextW(self, hwnd, destination, capacity):
        text = self.text_by_handle.get(hwnd, "")
        if len(text) >= int(capacity):
            return 0
        for index, character in enumerate(text):
            destination[index] = character
        destination[len(text)] = "\0"
        return len(text)

    def SetWindowTextW(self, hwnd, text):
        self.messages.append((hwnd, -1, text, 0))
        if text == "" and self._control_id(hwnd) == popup.IDC_EDIT:
            self.events.append("clear_edit")
        if text == "" and self.fail_clear:
            return False
        self.text_by_handle[hwnd] = text
        return True

    def DestroyWindow(self, hwnd):
        self.destroyed.append(hwnd)
        self.events.append("destroy_window")
        if self.registered_wndproc is not None:
            self.registered_wndproc(hwnd, popup.WM_DESTROY, 0, 0)
        return not self.fail_destroy

    def RegisterClassExW(self, class_pointer):
        self.registered_wndproc = class_pointer._obj.lpfnWndProc
        self.events.append("register_class")
        return 1

    def UnregisterClassW(self, _class_name, _instance):
        self.events.append("unregister_class")
        return True

    def GetForegroundWindow(self):
        self.events.append("get_foreground_owner")
        return self.owner_handle

    def LoadCursorW(self, *_args):
        return 6001

    def ShowWindow(self, _hwnd, _show):
        self.events.append("show_window")
        return True

    def UpdateWindow(self, _hwnd):
        self.events.append("update_window")
        return True

    def SetForegroundWindow(self, hwnd):
        self.events.append(f"set_foreground:{hwnd}")
        return True

    def SetActiveWindow(self, _hwnd):
        self.events.append("set_active")
        return 0

    def GetMessageW(self, message_pointer, _hwnd, _minimum, _maximum):
        top = next(
            row["handle"]
            for row in self.created
            if str(row["class"]).startswith("WOMCredentialPopup_")
        )
        edit = next(
            row["handle"]
            for row in self.created
            if row["control_id"] == popup.IDC_EDIT
        )
        message = message_pointer._obj
        message.hwnd = top
        message.message = popup.WM_COMMAND
        message.lParam = edit
        if self.message_index == 0:
            self.text_by_handle[edit] = self.full_run_text
            message.wParam = popup.IDC_EDIT | (popup.EN_CHANGE << 16)
            self.events.append("queue_edit_change")
        elif self.message_index == 1:
            message.wParam = popup.IDOK
            self.events.append("queue_submit")
        else:
            return 0
        self.message_index += 1
        return 1

    def TranslateMessage(self, _message_pointer):
        return True

    def IsDialogMessageW(self, _hwnd, _message_pointer):
        self.dialog_message_calls += 1
        return False

    def DispatchMessageW(self, message_pointer):
        message = message_pointer._obj
        self.events.append(
            "dispatch_edit_change"
            if popup._hiword(message.wParam) == popup.EN_CHANGE
            else "dispatch_submit"
        )
        return self.registered_wndproc(
            message.hwnd,
            message.message,
            message.wParam,
            message.lParam,
        )

    def CreatePopupMenu(self):
        return 5001

    def AppendMenuW(self, _menu, _flags, item_id, text):
        self.menu_items.append((int(item_id), text))
        return True

    def TrackPopupMenuEx(self, *_args):
        return self.menu_command

    def DestroyMenu(self, _menu):
        return True

    def GetWindowRect(self, _hwnd, rect_pointer):
        rect = rect_pointer._obj
        rect.left, rect.top, rect.right, rect.bottom = self.owner_rect
        return True

    def GetSystemMetrics(self, index):
        return 1920 if int(index) == 0 else 1080

    def DefWindowProcW(self, *_args):
        return 19

    def PostQuitMessage(self, _code):
        self.events.append("post_quit")
        return None


def make_session(
    *,
    max_secret_bytes: int = 2560,
    context: popup.CredentialPopupContext = CONTEXT,
    input_intent: popup.CredentialPopupInputIntent = (
        popup.CredentialPopupInputIntent.synthetic_acceptance
    ),
    dpi: int = 96,
) -> tuple[
    popup._PopupSession,
    FakeUser32,
    FakeKernel32,
    FakeImm32,
    FakeGdi32,
    FakeComctl32,
]:
    user32 = FakeUser32()
    user32.dpi = dpi
    kernel32 = FakeKernel32()
    imm32 = FakeImm32()
    gdi32 = FakeGdi32(user32.events)
    comctl32 = FakeComctl32()
    session = popup._PopupSession(
        request_id=REQUEST_ID,
        context=context,
        input_intent=input_intent,
        user32=user32,
        kernel32=kernel32,
        imm32=imm32,
        gdi32=gdi32,
        comctl32=comctl32,
        max_secret_bytes=max_secret_bytes,
    )
    session.window = 91
    session._ui_font = 8001
    session._dpi = dpi
    session._window_width = session._scale(popup.WINDOW_WIDTH)
    session._window_height = session._scale(popup.WINDOW_HEIGHT)
    session._create_controls(7001)
    return session, user32, kernel32, imm32, gdi32, comctl32


class CredentialPopupWindowsTests(unittest.TestCase):
    def test_exact_unicode_copy_is_fixed_and_length_opaque(self) -> None:
        self.assertEqual(popup.POPUP_TITLE, "WOM · 안전한 자격 증명 입력")
        self.assertEqual(
            popup.OVERLAY_TEXT,
            "입력 내용과 길이는 화면에 표시되지 않습니다.",
        )
        self.assertEqual(popup.OK_TEXT, "확인")
        self.assertEqual(popup.CANCEL_TEXT, "취소")
        rendered = popup.popup_instruction_text(
            CONTEXT,
            input_intent=popup.CredentialPopupInputIntent.live_registration,
        )
        for token in (
            "도우미 AI와 채팅에는 자격 증명이 전달되지 않습니다.",
            "입력값의 글자·기호·길이는 화면에 표시되지 않습니다.",
            "Ctrl+V",
            "Shift+Insert",
            CONTEXT.task_summary,
            CONTEXT.connection_reason,
            CONTEXT.account_label,
            CONTEXT.workspace_label,
        ):
            with self.subTest(token=token):
                self.assertIn(token, rendered)
        unsafe = popup.CredentialPopupContext(
            provider="notion",
            purpose="notion_page_recovery",
            account_label="개인 계정",
            workspace_label="자료 보관함",
            task_summary="secret_abcdefghijklmnopqrstuvwxyz123456",
            connection_reason=CONTEXT.connection_reason,
        )
        with self.assertRaises(popup.CredentialPopupSecretPromptError) as error:
            popup.popup_instruction_text(
                unsafe,
                input_intent=(
                    popup.CredentialPopupInputIntent.live_registration
                ),
            )
        self.assertEqual(error.exception.reason_code, "credential_input_not_received")

    def test_exact_intent_enum_banners_and_synthetic_warning_copy_are_closed(self) -> None:
        live = popup.CredentialPopupInputIntent.live_registration
        synthetic = popup.CredentialPopupInputIntent.synthetic_acceptance
        self.assertEqual(live.value, "live_registration")
        self.assertEqual(synthetic.value, "synthetic_acceptance")
        self.assertEqual(
            popup.popup_intent_banner_text(live),
            "실제 자격 증명 등록",
        )
        self.assertEqual(
            popup.popup_intent_banner_text(synthetic),
            "합성 입력 테스트 · 실제 키 입력 금지",
        )
        live_copy = popup.popup_instruction_text(
            CONTEXT,
            input_intent=live,
        )
        synthetic_copy = popup.popup_instruction_text(
            CONTEXT,
            input_intent=synthetic,
        )
        self.assertIn("도우미 AI와 채팅에는", live_copy)
        self.assertNotIn("실제 자격 증명은 절대", live_copy)
        self.assertIn(
            "경고: 실제 자격 증명은 절대 입력하거나 붙여넣지 마세요.",
            synthetic_copy,
        )
        self.assertIn("고정 합성 문자열만 입력하세요.", synthetic_copy)
        self.assertNotIn("도우미 AI와 채팅에는", synthetic_copy)

    def test_standard_password_edit_is_fully_covered_and_all_controls_use_message_font(self) -> None:
        session, user32, _kernel32, imm32, _gdi32, comctl32 = make_session()
        self.assertIs(
            session.input_intent,
            popup.CredentialPopupInputIntent.synthetic_acceptance,
        )
        edit = next(row for row in user32.created if row["control_id"] == popup.IDC_EDIT)
        overlay = next(
            row for row in user32.created if row["control_id"] == popup.IDC_OVERLAY
        )
        self.assertEqual(edit["class"], "EDIT")
        self.assertTrue(int(edit["style"]) & popup.ES_PASSWORD)
        self.assertEqual(overlay["class"], "STATIC")
        self.assertEqual(overlay["text"], popup.OVERLAY_TEXT)
        self.assertEqual(
            (overlay["x"], overlay["y"], overlay["width"], overlay["height"]),
            (edit["x"], edit["y"], edit["width"], edit["height"]),
        )
        self.assertGreater(user32.created.index(overlay), user32.created.index(edit))
        font_messages = [
            row for row in user32.messages if row[1] == popup.WM_SETFONT
        ]
        self.assertEqual(len(font_messages), len(user32.created))
        self.assertTrue(all(row[2] == 8001 for row in font_messages))
        self.assertEqual(imm32.calls, [(session.edit, None)])
        self.assertEqual(
            [row[2] for row in comctl32.subclasses],
            [popup.IDC_EDIT, popup.IDC_OVERLAY],
        )
        self.assertIn(
            (session.edit, popup.EM_SETLIMITTEXT, session.max_secret_bytes, 0),
            user32.messages,
        )

    def test_intent_banner_is_topmost_exact_colored_row_at_common_dpis(self) -> None:
        modes = (
            (
                popup.CredentialPopupInputIntent.live_registration,
                "실제 자격 증명 등록",
                popup.LIVE_REGISTRATION_BANNER_BACKGROUND_COLOR,
                popup.LIVE_REGISTRATION_BANNER_TEXT_COLOR,
            ),
            (
                popup.CredentialPopupInputIntent.synthetic_acceptance,
                "합성 입력 테스트 · 실제 키 입력 금지",
                popup.SYNTHETIC_ACCEPTANCE_BANNER_BACKGROUND_COLOR,
                popup.SYNTHETIC_ACCEPTANCE_BANNER_TEXT_COLOR,
            ),
        )
        for input_intent, banner_text, background, foreground in modes:
            for dpi in (96, 120, 144, 168, 192):
                with self.subTest(input_intent=input_intent, dpi=dpi):
                    session, user32, _kernel32, _imm32, gdi32, _comctl32 = (
                        make_session(input_intent=input_intent, dpi=dpi)
                    )
                    banner = next(
                        row
                        for row in user32.created
                        if row["control_id"] == popup.IDC_INTENT_BANNER
                    )
                    visible_children = [
                        row
                        for row in user32.created
                        if row["parent"] == session.window
                        and int(row["style"]) & popup.WS_VISIBLE
                    ]
                    self.assertEqual(banner["text"], banner_text)
                    self.assertEqual(
                        int(banner["y"]),
                        min(int(row["y"]) for row in visible_children),
                    )
                    self.assertEqual(
                        gdi32.created_brushes,
                        [background],
                    )
                    self.assertEqual(
                        session._main_proc(
                            session.window,
                            popup.WM_CTLCOLORSTATIC,
                            6003,
                            int(banner["handle"]),
                        ),
                        8002,
                    )
                    self.assertEqual(gdi32.text_colors, [(6003, foreground)])
                    self.assertEqual(
                        gdi32.background_colors,
                        [(6003, background)],
                    )
                    instruction_rows = [
                        row
                        for row in user32.created
                        if row["class"] == "STATIC"
                        and row["control_id"] == 0
                    ]
                    self.assertTrue(instruction_rows)
                    self.assertLessEqual(
                        int(banner["y"]) + int(banner["height"]),
                        int(instruction_rows[0]["y"]),
                    )
                    ordered_rows = [
                        banner,
                        *instruction_rows,
                        next(
                            row
                            for row in user32.created
                            if row["control_id"] == popup.IDC_EDIT
                        ),
                        next(
                            row
                            for row in user32.created
                            if row["control_id"] == popup.IDC_STATUS
                        ),
                        next(
                            row
                            for row in user32.created
                            if row["control_id"] == popup.IDOK
                        ),
                    ]
                    for previous, current in zip(ordered_rows, ordered_rows[1:]):
                        self.assertLessEqual(
                            int(previous["y"]) + int(previous["height"]),
                            int(current["y"]),
                        )
                    self.assertLessEqual(
                        int(ordered_rows[-1]["y"])
                        + int(ordered_rows[-1]["height"]),
                        session._scale(popup.WINDOW_CLIENT_SAFE_BOTTOM),
                    )
        self.assertNotEqual(
            popup.LIVE_REGISTRATION_BANNER_BACKGROUND_COLOR,
            popup.SYNTHETIC_ACCEPTANCE_BANNER_BACKGROUND_COLOR,
        )

    def test_message_font_geometry_has_wrapped_nonoverlapping_rows(self) -> None:
        session, user32, _kernel32, _imm32, _gdi32, _comctl32 = make_session()
        instruction_rows = [
            row
            for row in user32.created
            if row["class"] == "STATIC" and row["control_id"] == 0
        ]
        self.assertEqual(
            [row["text"] for row in instruction_rows],
            [line for line in session._instruction.split("\r\n") if line],
        )
        for index, row in enumerate(instruction_rows):
            self.assertEqual(
                (row["x"], row["width"]),
                (popup.CONTENT_X, popup.CONTENT_WIDTH),
            )
            self.assertGreaterEqual(row["height"], popup.TEXT_ROW_MIN_HEIGHT)
            self.assertTrue(int(row["style"]) & popup.SS_NOPREFIX)
            self.assertTrue(int(row["style"]) & popup.SS_EDITCONTROL)
            if index:
                previous = instruction_rows[index - 1]
                self.assertGreaterEqual(
                    row["y"],
                    int(previous["y"]) + int(previous["height"]),
                )

        edit = next(
            row for row in user32.created if row["control_id"] == popup.IDC_EDIT
        )
        overlay = next(
            row for row in user32.created if row["control_id"] == popup.IDC_OVERLAY
        )
        status = next(
            row for row in user32.created if row["control_id"] == popup.IDC_STATUS
        )
        buttons = [
            row
            for row in user32.created
            if row["control_id"] in {popup.IDOK, popup.IDCANCEL}
        ]
        last_instruction = instruction_rows[-1]
        self.assertGreaterEqual(
            edit["y"],
            int(last_instruction["y"]) + int(last_instruction["height"]),
        )
        self.assertEqual(
            (overlay["x"], overlay["y"], overlay["width"], overlay["height"]),
            (edit["x"], edit["y"], edit["width"], edit["height"]),
        )
        self.assertGreaterEqual(
            status["y"],
            int(edit["y"]) + int(edit["height"]),
        )
        for button in buttons:
            self.assertGreaterEqual(
                button["y"],
                int(status["y"]) + int(status["height"]),
            )
            self.assertLessEqual(
                int(button["y"]) + int(button["height"]),
                popup.WINDOW_CLIENT_SAFE_BOTTOM,
            )
        expected_flags = (
            popup.DT_CALCRECT
            | popup.DT_WORDBREAK
            | popup.DT_EDITCONTROL
            | popup.DT_NOPREFIX
        )
        self.assertTrue(user32.measurements)
        self.assertTrue(
            all(row["flags"] == expected_flags for row in user32.measurements)
        )

    def test_all_logical_geometry_scales_together_at_common_windows_dpis(self) -> None:
        def scaled(value: int, dpi: int) -> int:
            return 0 if value == 0 else max(1, (value * dpi + 48) // 96)

        expected_geometry = {
            96: (660, 470, 52, 26, 184, 26, 28, 228, 590, 46, 290, 26, 418, 340, 92, 36),
            120: (825, 588, 65, 33, 232, 33, 35, 288, 738, 58, 366, 33, 523, 429, 115, 45),
            144: (990, 705, 78, 39, 276, 39, 42, 342, 885, 69, 435, 39, 627, 510, 138, 54),
            168: (1155, 823, 91, 46, 324, 46, 49, 402, 1033, 81, 511, 46, 732, 599, 161, 63),
            192: (1320, 940, 104, 52, 368, 52, 56, 456, 1180, 92, 580, 52, 836, 680, 184, 72),
        }
        for dpi in (96, 120, 144, 168, 192):
            with self.subTest(dpi=dpi):
                session, user32, *_rest = make_session(dpi=dpi)
                self.assertEqual(
                    (session._window_width, session._window_height),
                    (
                        scaled(popup.WINDOW_WIDTH, dpi),
                        scaled(popup.WINDOW_HEIGHT, dpi),
                    ),
                )
                instruction_rows = [
                    row
                    for row in user32.created
                    if row["class"] == "STATIC" and row["control_id"] == 0
                ]
                banner = next(
                    row
                    for row in user32.created
                    if row["control_id"] == popup.IDC_INTENT_BANNER
                )
                edit = next(
                    row
                    for row in user32.created
                    if row["control_id"] == popup.IDC_EDIT
                )
                overlay = next(
                    row
                    for row in user32.created
                    if row["control_id"] == popup.IDC_OVERLAY
                )
                status = next(
                    row
                    for row in user32.created
                    if row["control_id"] == popup.IDC_STATUS
                )
                buttons = [
                    row
                    for row in user32.created
                    if row["control_id"] in {popup.IDOK, popup.IDCANCEL}
                ]
                ok_button = next(
                    row for row in buttons if row["control_id"] == popup.IDOK
                )
                self.assertEqual(
                    (
                        session._window_width,
                        session._window_height,
                        instruction_rows[0]["y"],
                        instruction_rows[0]["height"],
                        instruction_rows[-1]["y"],
                        instruction_rows[-1]["height"],
                        edit["x"],
                        edit["y"],
                        edit["width"],
                        edit["height"],
                        status["y"],
                        status["height"],
                        ok_button["x"],
                        ok_button["y"],
                        ok_button["width"],
                        ok_button["height"],
                    ),
                    expected_geometry[dpi],
                )
                self.assertEqual(
                    banner["y"],
                    scaled(popup.INSTRUCTION_TOP, dpi),
                )
                self.assertEqual(
                    instruction_rows[0]["y"],
                    int(banner["y"])
                    + int(banner["height"])
                    + scaled(popup.INTENT_BANNER_GAP, dpi),
                )
                self.assertTrue(
                    all(
                        row["x"] == scaled(popup.CONTENT_X, dpi)
                        and row["width"] == scaled(popup.CONTENT_WIDTH, dpi)
                        for row in instruction_rows
                    )
                )
                for previous, current in zip(
                    instruction_rows,
                    instruction_rows[1:],
                ):
                    self.assertGreaterEqual(
                        int(current["y"])
                        - int(previous["y"])
                        - int(previous["height"]),
                        scaled(popup.TEXT_ROW_GAP, dpi),
                    )
                last_instruction = instruction_rows[-1]
                self.assertGreaterEqual(
                    int(edit["y"])
                    - int(last_instruction["y"])
                    - int(last_instruction["height"]),
                    scaled(popup.INPUT_SECTION_GAP, dpi),
                )
                self.assertEqual(
                    (edit["x"], edit["width"], edit["height"]),
                    (
                        scaled(popup.EDIT_X, dpi),
                        scaled(popup.EDIT_WIDTH, dpi),
                        scaled(popup.EDIT_HEIGHT, dpi),
                    ),
                )
                self.assertEqual(
                    (overlay["x"], overlay["y"], overlay["width"], overlay["height"]),
                    (edit["x"], edit["y"], edit["width"], edit["height"]),
                )
                self.assertGreaterEqual(
                    int(status["y"]) - int(edit["y"]) - int(edit["height"]),
                    scaled(popup.STATUS_GAP, dpi),
                )
                for button in buttons:
                    self.assertGreaterEqual(
                        int(button["y"])
                        - int(status["y"])
                        - int(status["height"]),
                        scaled(popup.BUTTON_GAP, dpi),
                    )
                    self.assertLessEqual(
                        int(button["y"]) + int(button["height"]),
                        scaled(popup.WINDOW_CLIENT_SAFE_BOTTOM, dpi),
                    )
                session.owner = user32.owner_handle
                user32.owner_rect = (100, 200, 2100, 1700)
                self.assertEqual(
                    session._center_position(),
                    (
                        100 + (2000 - session._window_width) // 2,
                        200 + (1500 - session._window_height) // 2,
                    ),
                )

    def test_acceptance_korean_ascii_context_wraps_within_layout_budget(self) -> None:
        long_task = (
            "수동 확인용 고정 합성 문자열은 "
            "WOM-INPUT-ACCEPTANCE-0319 입니다."
        )
        long_context = popup.CredentialPopupContext(
            provider="notion",
            purpose="source_recovery",
            account_label="합성 입력 확인용 계정",
            workspace_label="합성 입력 확인용 작업공간",
            task_summary=long_task,
            connection_reason=(
                "입력 대기 중 문구가 나타난 뒤 위 고정 합성 문자열 전체를 "
                "지정한 방식으로 입력하고 Enter를 눌러 주세요."
            ),
        )
        session, user32, *_rest = make_session(context=long_context)
        task_row = next(
            row
            for row in user32.created
            if row["control_id"] == 0
            and str(row["text"]).startswith("현재 작업:")
        )
        wrapped_rows = [
            row
            for row in user32.created
            if row["control_id"] == 0
            and int(row["height"]) > popup.TEXT_ROW_MIN_HEIGHT
        ]
        self.assertTrue(wrapped_rows)
        self.assertIn(long_task, session._instruction)
        edit = next(
            row for row in user32.created if row["control_id"] == popup.IDC_EDIT
        )
        self.assertLessEqual(
            int(task_row["y"]) + int(task_row["height"]),
            int(edit["y"]),
        )
        buttons = [
            row
            for row in user32.created
            if row["control_id"] in {popup.IDOK, popup.IDCANCEL}
        ]
        self.assertTrue(
            all(
                int(row["y"]) + int(row["height"])
                <= popup.WINDOW_CLIENT_SAFE_BOTTOM
                for row in buttons
            )
        )

    def test_edit_subclass_blocks_copy_cut_and_preserves_standard_paste_shortcuts(self) -> None:
        session, user32, _kernel32, _imm32, _gdi32, comctl32 = make_session()
        for message in (popup.WM_COPY, popup.WM_CUT):
            before = len(comctl32.default_messages)
            self.assertEqual(
                session._edit_proc(
                    session.edit, message, 0, 0, popup.IDC_EDIT, 0
                ),
                0,
            )
            self.assertEqual(len(comctl32.default_messages), before)

        for message, key in (
            (popup.WM_PASTE, 0),
            (popup.WM_KEYDOWN, ord("V")),
            (popup.WM_KEYDOWN, 0x2D),
        ):
            with self.subTest(message=message, key=key):
                self.assertEqual(
                    session._edit_proc(
                        session.edit,
                        message,
                        key,
                        0,
                        popup.IDC_EDIT,
                        0,
                    ),
                    17,
                )
                self.assertEqual(comctl32.default_messages[-1][1], message)

        session._edit_proc(
            session.edit, popup.WM_SETFOCUS, 0, 0, popup.IDC_EDIT, 0
        )
        self.assertIn(session.edit, user32.hidden_carets)

    def test_context_menu_contains_only_paste_and_clear_and_dispatches_standard_edit_messages(self) -> None:
        for command, expected_messages in (
            (popup.ID_POPUP_PASTE, (popup.WM_PASTE,)),
            (popup.ID_POPUP_CLEAR, (popup.EM_SETSEL, popup.WM_CLEAR)),
        ):
            with self.subTest(command=command):
                session, user32, *_rest = make_session()
                user32.menu_command = command
                session._edit_proc(
                    session.edit,
                    popup.WM_CONTEXTMENU,
                    0,
                    -1,
                    popup.IDC_EDIT,
                    0,
                )
                self.assertEqual(
                    user32.menu_items,
                    [
                        (popup.ID_POPUP_PASTE, popup.PASTE_MENU_TEXT),
                        (popup.ID_POPUP_CLEAR, popup.CLEAR_MENU_TEXT),
                    ],
                )
                sent = [row[1] for row in user32.messages]
                for message in expected_messages:
                    self.assertIn(message, sent)

    def test_overlay_is_mouse_transparent_and_refocuses_hidden_edit(self) -> None:
        session, user32, *_rest = make_session()
        self.assertEqual(
            session._overlay_proc(
                session.overlay,
                popup.WM_NCHITTEST,
                0,
                0,
                popup.IDC_OVERLAY,
                0,
            ),
            popup.HTTRANSPARENT,
        )
        self.assertEqual(
            session._overlay_proc(
                session.overlay,
                popup.WM_LBUTTONDOWN,
                0,
                0,
                popup.IDC_OVERLAY,
                0,
            ),
            0,
        )
        self.assertEqual(user32.focused[-1], session.edit)
        self.assertEqual(user32.hidden_carets[-1], session.edit)

    def test_subclasses_remove_before_forwarding_wm_ncdestroy(self) -> None:
        session, _user32, _kernel32, _imm32, _gdi32, comctl32 = make_session()
        session._edit_proc(
            session.edit,
            popup.WM_NCDESTROY,
            0,
            0,
            popup.IDC_EDIT,
            0,
        )
        session._overlay_proc(
            session.overlay,
            popup.WM_NCDESTROY,
            0,
            0,
            popup.IDC_OVERLAY,
            0,
        )
        self.assertEqual(
            comctl32.events,
            [
                ("remove", session.edit, popup.IDC_EDIT),
                ("default", session.edit, popup.WM_NCDESTROY),
                ("remove", session.overlay, popup.IDC_OVERLAY),
                ("default", session.overlay, popup.WM_NCDESTROY),
            ],
        )

    def test_nonempty_submit_returns_mutable_utf8_and_wipes_both_native_buffers(self) -> None:
        session, user32, kernel32, *_rest = make_session()
        synthetic = "synthetic-한글-token"
        user32.text_by_handle[session.edit] = synthetic
        session._note_edit_change()
        self.assertTrue(session.input_observed)
        self.assertIn((session.ok_button, True), user32.enabled)
        self.assertEqual(
            user32.text_by_handle[session.status],
            popup.SYNTHETIC_STATUS_READY_TEXT,
        )

        wiped: list[bytes] = []
        original_wipe = popup._wipe_ctypes_buffer

        def record_wipe(buffer):
            original_wipe(buffer)
            wiped.append(ctypes.string_at(ctypes.addressof(buffer), ctypes.sizeof(buffer)))

        with patch.object(popup, "_wipe_ctypes_buffer", side_effect=record_wipe):
            session._submit()

        self.assertIsNone(session.failure)
        self.assertIsInstance(session.result, HumanSecretInputResult)
        assert session.result is not None
        self.assertEqual(session.result.secret, bytearray(synthetic.encode("utf-8")))
        self.assertTrue(session.result.credential_input_received)
        self.assertTrue(session.result.complete_line_received)
        self.assertFalse(session.result.cancelled)
        self.assertEqual(kernel32.convert_calls, [(popup.CP_UTF8, popup.WC_ERR_INVALID_CHARS)])
        self.assertEqual(len(wiped), 2)
        self.assertTrue(all(set(snapshot) <= {0} for snapshot in wiped))
        self.assertIn((session.edit, popup.EM_EMPTYUNDOBUFFER, 0, 0), user32.messages)
        self.assertTrue(user32.destroyed)
        self.assertNotIn(synthetic, repr(session.result))
        assert session.result.secret is not None
        session.result.secret[:] = b"\x00" * len(session.result.secret)

    def test_enter_submits_only_nonempty_and_cancel_paths_preserve_truthful_input(self) -> None:
        empty, empty_user32, *_rest = make_session()
        empty._edit_proc(
            empty.edit, popup.WM_KEYDOWN, popup.VK_RETURN, 0, popup.IDC_EDIT, 0
        )
        self.assertFalse(empty.finished)
        self.assertIsNone(empty.result)

        submitted, submit_user32, *_rest = make_session()
        submit_user32.text_by_handle[submitted.edit] = "synthetic-direct-entry"
        submitted._edit_proc(
            submitted.edit,
            popup.WM_KEYDOWN,
            popup.VK_RETURN,
            0,
            popup.IDC_EDIT,
            0,
        )
        self.assertTrue(submitted.finished)
        assert submitted.result is not None
        self.assertTrue(submitted.result.complete_line_received)
        assert submitted.result.secret is not None
        submitted.result.secret[:] = b"\x00" * len(submitted.result.secret)

        for route in ("escape", "close", "cancel_button"):
            with self.subTest(route=route):
                session, user32, *_rest = make_session()
                user32.text_by_handle[session.edit] = "typed-then-cancelled"
                session._note_edit_change()
                if route == "escape":
                    session._edit_proc(
                        session.edit,
                        popup.WM_KEYDOWN,
                        popup.VK_ESCAPE,
                        0,
                        popup.IDC_EDIT,
                        0,
                    )
                elif route == "close":
                    session._main_proc(session.window, popup.WM_CLOSE, 0, 0)
                else:
                    session._main_proc(
                        session.window,
                        popup.WM_COMMAND,
                        popup.IDCANCEL,
                        0,
                    )
                assert session.result is not None
                self.assertIsNone(session.result.secret)
                self.assertTrue(session.result.credential_input_received)
                self.assertFalse(session.result.complete_line_received)
                self.assertTrue(session.result.cancelled)
                self.assertIn(
                    (session.edit, popup.EM_EMPTYUNDOBUFFER, 0, 0),
                    user32.messages,
                )

    def test_control_max_and_native_failures_map_only_to_0000_1000_or_1100(self) -> None:
        invalid, invalid_user32, *_rest = make_session()
        invalid_user32.text_by_handle[invalid.edit] = "abc\x01def"
        invalid._note_edit_change()
        invalid._submit()
        assert invalid.failure is not None
        self.assertEqual(invalid.failure.reason_code, "credential_input_invalid_for_provider")
        self.assertEqual(
            (
                invalid.failure.credential_input_received,
                invalid.failure.complete_line_received,
            ),
            (True, True),
        )

        oversized, oversized_user32, *_rest = make_session(max_secret_bytes=2)
        oversized_user32.text_by_handle[oversized.edit] = "한"
        oversized._note_edit_change()
        oversized._submit()
        assert oversized.failure is not None
        self.assertEqual(
            oversized.failure.reason_code, "credential_input_invalid_for_provider"
        )

        partial, partial_user32, *_rest = make_session()
        partial.input_observed = True
        partial_user32.raise_length = True
        partial._submit()
        assert partial.failure is not None
        self.assertEqual(partial.failure.reason_code, "credential_input_boundary_failed")
        self.assertEqual(
            (
                partial.failure.credential_input_received,
                partial.failure.complete_line_received,
            ),
            (True, False),
        )

        complete, complete_user32, *_rest = make_session()
        complete_user32.text_by_handle[complete.edit] = "synthetic-cleanup-failure"
        complete_user32.fail_clear = True
        complete._submit()
        assert complete.failure is not None
        self.assertEqual(complete.failure.reason_code, "credential_input_boundary_failed")
        self.assertEqual(
            (
                complete.failure.credential_input_received,
                complete.failure.complete_line_received,
            ),
            (True, True),
        )
        self.assertIsNone(complete.result)

        with self.assertRaises(popup.CredentialPopupSecretPromptError) as no_input:
            popup.prompt_secret_in_native_popup(
                request_id="bad",
                context=CONTEXT,
                input_intent=(
                    popup.CredentialPopupInputIntent.synthetic_acceptance
                ),
                platform_name="nt",
            )
        self.assertEqual(no_input.exception.reason_code, "credential_input_not_received")
        self.assertEqual(
            (
                no_input.exception.credential_input_received,
                no_input.exception.complete_line_received,
            ),
            (False, False),
        )
        rendered = str(no_input.exception) + repr(no_input.exception)
        self.assertNotIn("bad", rendered)

    def test_en_maxtext_is_sticky_until_empty_and_never_returns_truncated_text(self) -> None:
        session, user32, *_rest = make_session(max_secret_bytes=8)
        truncated = "12345678"
        user32.text_by_handle[session.edit] = truncated
        session._main_proc(
            session.window,
            popup.WM_COMMAND,
            popup.IDC_EDIT | (popup.EN_MAXTEXT << 16),
            session.edit,
        )
        self.assertTrue(session.input_observed)
        self.assertTrue(session.input_overlimit)
        self.assertEqual(
            user32.text_by_handle[session.status],
            popup.SYNTHETIC_STATUS_LIMIT_EXCEEDED_TEXT,
        )
        self.assertEqual(user32.enabled[-1], (session.ok_button, False))

        # EN_CHANGE may follow EN_MAXTEXT after the standard edit retained a
        # prefix. That non-empty prefix must not clear the overlimit state.
        session._main_proc(
            session.window,
            popup.WM_COMMAND,
            popup.IDC_EDIT | (popup.EN_CHANGE << 16),
            session.edit,
        )
        self.assertTrue(session.input_overlimit)
        self.assertEqual(user32.enabled[-1], (session.ok_button, False))
        session._submit()
        self.assertIsNone(session.result)
        assert session.failure is not None
        self.assertEqual(
            session.failure.reason_code,
            "credential_input_invalid_for_provider",
        )
        self.assertEqual(
            (
                session.failure.credential_input_received,
                session.failure.complete_line_received,
            ),
            (True, True),
        )
        self.assertNotIn(truncated, str(session.failure) + repr(session.failure))

        retry, retry_user32, *_rest = make_session(max_secret_bytes=8)
        retry_user32.text_by_handle[retry.edit] = truncated
        retry._note_edit_overlimit()
        retry_user32.text_by_handle[retry.edit] = "123"
        retry._note_edit_change()
        self.assertTrue(retry.input_overlimit)
        self.assertEqual(retry_user32.enabled[-1], (retry.ok_button, False))
        retry_user32.text_by_handle[retry.edit] = ""
        retry._note_edit_change()
        self.assertFalse(retry.input_overlimit)
        self.assertEqual(
            retry_user32.text_by_handle[retry.status],
            popup.SYNTHETIC_STATUS_EMPTY_TEXT,
        )

        exact_limit = "abcdefgh"
        retry_user32.text_by_handle[retry.edit] = exact_limit
        retry._note_edit_change()
        self.assertEqual(retry_user32.enabled[-1], (retry.ok_button, True))
        retry._submit()
        self.assertIsNone(retry.failure)
        assert retry.result is not None
        self.assertEqual(retry.result.secret, bytearray(exact_limit.encode("ascii")))
        assert retry.result.secret is not None
        retry.result.secret[:] = b"\x00" * len(retry.result.secret)

    def test_centering_uses_foreground_owner_without_disabling_it(self) -> None:
        session, user32, *_rest = make_session()
        session.owner = 3001
        self.assertEqual(
            session._center_position(),
            (
                100 + (1000 - popup.WINDOW_WIDTH) // 2,
                200 + (700 - popup.WINDOW_HEIGHT) // 2,
            ),
        )
        source = inspect.getsource(popup._PopupSession.run)
        self.assertIn("GetForegroundWindow", source)
        self.assertIn("SetForegroundWindow(self.window)", source)
        self.assertNotIn("EnableWindow(self.owner", source)
        self.assertNotIn("SetForegroundWindow(self.owner", source)

    def test_missing_or_non_enum_intent_fails_before_any_native_show(self) -> None:
        for label, supplied_intent in (
            ("missing", None),
            ("plain_live_string", "live_registration"),
            ("plain_synthetic_string", "synthetic_acceptance"),
            ("unknown", object()),
        ):
            with self.subTest(label=label):
                user32 = FakeUser32()
                kwargs: dict[str, object] = {
                    "request_id": REQUEST_ID,
                    "context": CONTEXT,
                    "user32": user32,
                    "kernel32": FakeKernel32(),
                    "imm32": FakeImm32(),
                    "gdi32": FakeGdi32(user32.events),
                    "comctl32": FakeComctl32(),
                    "platform_name": "nt",
                }
                if label != "missing":
                    kwargs["input_intent"] = supplied_intent
                with self.assertRaises(
                    popup.CredentialPopupSecretPromptError
                ) as error:
                    popup.prompt_secret_in_native_popup(**kwargs)
                self.assertEqual(
                    (
                        error.exception.reason_code,
                        error.exception.credential_input_received,
                        error.exception.complete_line_received,
                    ),
                    ("credential_input_not_received", False, False),
                )
                self.assertEqual(user32.events, [])
                self.assertEqual(user32.created, [])

        with self.assertRaises(popup.CredentialPopupSecretPromptError):
            popup._PopupSession(
                request_id=REQUEST_ID,
                context=CONTEXT,
                input_intent="synthetic_acceptance",
                user32=FakeUser32(),
                kernel32=FakeKernel32(),
                imm32=FakeImm32(),
                gdi32=FakeGdi32(),
                comctl32=FakeComctl32(),
                max_secret_bytes=2560,
            )

    def test_pmv2_lease_failure_or_ambiguous_install_never_shows_popup(self) -> None:
        for failure_kind in ("install_null", "current_proof_wrong"):
            with self.subTest(failure_kind=failure_kind):
                user32 = FakeUser32()
                if failure_kind == "install_null":
                    user32.fail_dpi_enter = True
                else:
                    user32.enter_current_override = 4999
                kernel32 = FakeKernel32()
                imm32 = FakeImm32()
                gdi32 = FakeGdi32(user32.events)
                comctl32 = FakeComctl32()
                with patch.object(popup, "_configure_native"), self.assertRaises(
                    popup.CredentialPopupSecretPromptError
                ) as error:
                    popup.prompt_secret_in_native_popup(
                        request_id=REQUEST_ID,
                        context=CONTEXT,
                        input_intent=(
                            popup.CredentialPopupInputIntent.synthetic_acceptance
                        ),
                        user32=user32,
                        kernel32=kernel32,
                        imm32=imm32,
                        gdi32=gdi32,
                        comctl32=comctl32,
                        platform_name="nt",
                    )

                self.assertEqual(
                    (
                        error.exception.reason_code,
                        error.exception.credential_input_received,
                        error.exception.complete_line_received,
                    ),
                    ("credential_input_not_received", False, False),
                )
                self.assertNotIn("show_window", user32.events)
                self.assertNotIn("get_foreground_owner", user32.events)
                self.assertNotIn("create_message_font", user32.events)
                self.assertFalse(user32.created)

    def test_full_fake_message_loop_orders_native_popup_lifecycle_without_owner_disable(self) -> None:
        user32 = FakeUser32()
        kernel32 = FakeKernel32()
        imm32 = FakeImm32()
        gdi32 = FakeGdi32(user32.events)
        comctl32 = FakeComctl32()
        with patch.object(popup, "_configure_native"):
            result = popup.prompt_secret_in_native_popup(
                request_id=REQUEST_ID,
                context=CONTEXT,
                input_intent=(
                    popup.CredentialPopupInputIntent.synthetic_acceptance
                ),
                user32=user32,
                kernel32=kernel32,
                imm32=imm32,
                gdi32=gdi32,
                comctl32=comctl32,
                platform_name="nt",
            )

        self.assertEqual(
            result.secret,
            bytearray(user32.full_run_text.encode("utf-8")),
        )
        self.assertTrue(result.credential_input_received)
        self.assertTrue(result.complete_line_received)
        self.assertFalse(result.cancelled)
        ordered = (
            "enter_dpi_context",
            "register_class",
            "get_foreground_owner",
            "get_window_dpi",
            "create_message_font",
            "create_intent_banner_brush",
            "show_window",
            "set_foreground:101",
            "queue_edit_change",
            "dispatch_edit_change",
            "queue_submit",
            "dispatch_submit",
            "clear_edit",
            "empty_undo",
            "destroy_window",
            "post_quit",
            "delete_intent_banner_brush",
            "delete_message_font",
            "unregister_class",
            "restore_dpi_context",
        )
        positions = [user32.events.index(event) for event in ordered]
        self.assertEqual(positions, sorted(positions))
        top_window_event = next(
            event
            for event in user32.events
            if event.startswith("create:WOMCredentialPopup_")
        )
        self.assertLess(
            user32.events.index("enter_dpi_context"),
            user32.events.index("get_foreground_owner"),
        )
        self.assertLess(
            user32.events.index("get_window_dpi"),
            user32.events.index(top_window_event),
        )
        self.assertEqual(
            [row for row in user32.enabled if row[0] == user32.owner_handle],
            [],
        )
        self.assertEqual(
            gdi32.created_fonts,
            [{"height": -17, "face": "Segoe UI"}],
        )
        self.assertEqual(gdi32.deleted_fonts, [8001])
        self.assertEqual(gdi32.deleted_brushes, [8002])
        self.assertEqual(user32.dpi_calls, [user32.owner_handle])
        self.assertEqual(
            user32.nonclient_metrics_calls,
            [(popup.SPI_GETNONCLIENTMETRICS, user32.dpi)],
        )
        source = Path(popup.__file__).read_text(encoding="utf-8")
        self.assertNotIn("DEFAULT_GUI_FONT", source)
        self.assertNotIn("GetStockObject", source)
        self.assertEqual(imm32.calls, [(imm32.get_calls[0], None)])
        self.assertEqual(imm32.release_calls, [])
        self.assertEqual(user32.dialog_message_calls, 2)
        self.assertEqual(
            user32.current_dpi_context,
            user32.original_dpi_context,
        )
        self.assertEqual(user32.events.count("restore_dpi_context"), 1)
        self.assertTrue(user32.destroyed)
        assert result.secret is not None
        result.secret[:] = b"\x00" * len(result.secret)

    def test_post_result_cleanup_failures_wipe_the_exact_result_bytearray(self) -> None:
        original_finish = popup._PopupSession._finish

        for failure_kind in (
            "native_edit",
            "destroy_window",
            "delete_banner_brush",
            "delete_font",
            "dpi_restore_null",
            "dpi_restore_wrong_return",
            "dpi_restore_wrong_current",
        ):
            with self.subTest(failure_kind=failure_kind):
                user32 = FakeUser32()
                kernel32 = FakeKernel32()
                imm32 = FakeImm32()
                gdi32 = FakeGdi32(user32.events)
                comctl32 = FakeComctl32()
                if failure_kind == "native_edit":
                    user32.fail_clear = True
                elif failure_kind == "destroy_window":
                    user32.fail_destroy = True
                elif failure_kind == "delete_banner_brush":
                    gdi32.delete_brush_result = False
                elif failure_kind == "delete_font":
                    gdi32.delete_font_result = False
                elif failure_kind == "dpi_restore_null":
                    user32.fail_dpi_restore = True
                elif failure_kind == "dpi_restore_wrong_return":
                    user32.restore_return_override = 4998
                elif failure_kind == "dpi_restore_wrong_current":
                    user32.restore_current_override = 4997
                captured_buffers: list[bytearray] = []

                def capturing_finish(session, result, failure=None):
                    if result is not None and result.secret is not None:
                        captured_buffers.append(result.secret)
                    return original_finish(session, result, failure)

                with patch.object(
                    popup,
                    "_configure_native",
                ), patch.object(
                    popup._PopupSession,
                    "_finish",
                    new=capturing_finish,
                ), self.assertRaises(
                    popup.CredentialPopupSecretPromptError
                ) as error:
                    popup.prompt_secret_in_native_popup(
                        request_id=REQUEST_ID,
                        context=CONTEXT,
                        input_intent=(
                            popup.CredentialPopupInputIntent.synthetic_acceptance
                        ),
                        user32=user32,
                        kernel32=kernel32,
                        imm32=imm32,
                        gdi32=gdi32,
                        comctl32=comctl32,
                        platform_name="nt",
                    )

                self.assertEqual(len(captured_buffers), 1)
                original_buffer = captured_buffers[0]
                self.assertGreater(len(original_buffer), 0)
                self.assertTrue(all(value == 0 for value in original_buffer))
                self.assertEqual(
                    (
                        error.exception.reason_code,
                        error.exception.credential_input_received,
                        error.exception.complete_line_received,
                    ),
                    ("credential_input_boundary_failed", True, True),
                )
                serialized_error = json.dumps(
                    error.exception.__dict__,
                    ensure_ascii=False,
                    default=str,
                    sort_keys=True,
                )
                self.assertNotIn(user32.full_run_text, repr(error.exception))
                self.assertNotIn(user32.full_run_text, serialized_error)
                if failure_kind == "delete_font":
                    self.assertLess(
                        user32.events.index("destroy_window"),
                        user32.events.index("delete_message_font"),
                    )
                if failure_kind == "delete_banner_brush":
                    self.assertLess(
                        user32.events.index("destroy_window"),
                        user32.events.index("delete_intent_banner_brush"),
                    )
                if failure_kind.startswith("dpi_restore"):
                    self.assertLess(
                        user32.events.index("delete_message_font"),
                        user32.events.index("restore_dpi_context"),
                    )

    def test_nonnull_ime_association_is_released_and_fails_before_show_or_focus(self) -> None:
        user32 = FakeUser32()
        kernel32 = FakeKernel32()
        imm32 = FakeImm32()
        imm32.current_context = 4444
        gdi32 = FakeGdi32(user32.events)
        comctl32 = FakeComctl32()
        with patch.object(popup, "_configure_native"), self.assertRaises(
            popup.CredentialPopupSecretPromptError
        ) as error:
            popup.prompt_secret_in_native_popup(
                request_id=REQUEST_ID,
                context=CONTEXT,
                input_intent=(
                    popup.CredentialPopupInputIntent.synthetic_acceptance
                ),
                user32=user32,
                kernel32=kernel32,
                imm32=imm32,
                gdi32=gdi32,
                comctl32=comctl32,
                platform_name="nt",
            )

        self.assertEqual(error.exception.reason_code, "credential_input_not_received")
        self.assertEqual(imm32.release_calls, [(imm32.get_calls[0], 4444)])
        self.assertNotIn("show_window", user32.events)
        self.assertFalse(
            any(event.startswith("set_foreground:") for event in user32.events)
        )
        edit_handle = imm32.get_calls[0]
        self.assertNotIn(edit_handle, user32.focused)
        self.assertIn("destroy_window", user32.events)
        self.assertIn("unregister_class", user32.events)
        self.assertEqual(imm32.calls, [(edit_handle, None)])

    def test_source_has_no_console_clipboard_reader_or_credui_fallback(self) -> None:
        source = Path(popup.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "GetClipboardData",
            "OpenClipboard",
            "CloseClipboard",
            "CredUIPrompt",
            "CONIN$",
            "CONOUT$",
            "AllocConsole",
            "FreeConsole",
            "sys.stdin",
            "sys.stdout",
            "sys.stderr",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn("WM_PASTE", source)
        self.assertIn("SetWindowSubclass", source)
        self.assertIn("DefSubclassProc", source)
        self.assertIn("WM_NCDESTROY", source)


if __name__ == "__main__":
    unittest.main()
