from __future__ import annotations

import ctypes
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from typing import Any

from wom_kit.credential_visible_console_windows import (
    CP_UTF8,
    ENABLE_ECHO_INPUT,
    ENABLE_LINE_INPUT,
    ENABLE_PROCESSED_INPUT,
    VisibleConsolePromptContext,
    VisibleConsoleSecretPromptError,
    prompt_masked_secret_in_new_console,
)


REQUEST_ID = "intake_abcdef1234567890"
SYNTHETIC_SECRET = "synthetic-notion-token-never-from-os"
PROMPT_CONTEXT = VisibleConsolePromptContext(
    provider="notion",
    purpose="notion_page_recovery",
    account_label="검토된 연구 계정",
    workspace_label="복구 대상 작업공간",
    task_summary="검토한 Notion 페이지를 WOM 아카이브로 복구하고 있습니다.",
    connection_reason="이 작업을 계속하려면 해당 Notion 작업공간 연결을 확인해 주세요.",
)


class FakeFunction:
    def __init__(self, handler: Any) -> None:
        self.handler = handler
        self.argtypes = None
        self.restype = None

    def __call__(self, *args: Any) -> Any:
        return self.handler(*args)


@dataclass
class FakeConsoleKernel32:
    input_text: str = SYNTHETIC_SECRET
    interrupt_read: bool = False
    fail_close: bool = False
    no_inherited_console: bool = False
    append_line_ending: bool = True
    calls: list[tuple[str, Any]] = field(default_factory=list)
    safe_writes: list[str] = field(default_factory=list)
    modes: list[int] = field(default_factory=list)
    last_input_buffer: Any = field(default=None, repr=False)
    ctrl_wakeup_mask: int | None = None
    input_code_pages: list[int] = field(default_factory=list)
    output_code_pages: list[int] = field(default_factory=list)
    requested_write_lengths: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.FreeConsole = FakeFunction(self._free_console)
        self.AllocConsole = FakeFunction(self._alloc_console)
        self.SetConsoleTitleW = FakeFunction(self._set_title)
        self.GetConsoleCP = FakeFunction(lambda: 949)
        self.SetConsoleCP = FakeFunction(self._set_console_cp)
        self.GetConsoleOutputCP = FakeFunction(lambda: 949)
        self.SetConsoleOutputCP = FakeFunction(self._set_console_output_cp)
        self.CreateFileW = FakeFunction(self._create_file)
        self.GetConsoleMode = FakeFunction(self._get_mode)
        self.SetConsoleMode = FakeFunction(self._set_mode)
        self.ReadConsoleW = FakeFunction(self._read_console)
        self.WriteConsoleW = FakeFunction(self._write_console)
        self.CloseHandle = FakeFunction(self._close_handle)
        self.WideCharToMultiByte = FakeFunction(self._wide_to_utf8)

    def _free_console(self) -> int:
        first_detach = not any(name == "FreeConsole" for name, _ in self.calls)
        self.calls.append(("FreeConsole", None))
        if first_detach and self.no_inherited_console:
            return 0
        return 1

    def _alloc_console(self) -> int:
        self.calls.append(("AllocConsole", None))
        return 1

    def _set_title(self, title: str) -> int:
        self.calls.append(("SetConsoleTitleW", title))
        return 1

    def _set_console_cp(self, code_page: int) -> int:
        self.input_code_pages.append(int(code_page))
        return 1

    def _set_console_output_cp(self, code_page: int) -> int:
        self.output_code_pages.append(int(code_page))
        return 1

    def _create_file(
        self,
        name: str,
        _access: int,
        _share: int,
        _security: Any,
        _disposition: int,
        _flags: int,
        _template: Any,
    ) -> int:
        self.calls.append(("CreateFileW", name))
        return 101 if name == "CONIN$" else 102

    def _get_mode(self, handle: int, mode_pointer: Any) -> int:
        self.calls.append(("GetConsoleMode", handle))
        mode = ctypes.cast(
            mode_pointer, ctypes.POINTER(ctypes.c_ulong)
        )
        mode.contents.value = (
            ENABLE_PROCESSED_INPUT | ENABLE_LINE_INPUT | ENABLE_ECHO_INPUT
        )
        return 1

    def _set_mode(self, handle: int, mode: int) -> int:
        self.calls.append(("SetConsoleMode", handle))
        self.modes.append(int(mode))
        return 1

    def _read_console(
        self,
        handle: int,
        buffer: Any,
        capacity: int,
        count_pointer: Any,
        control: Any,
    ) -> int:
        self.calls.append(("ReadConsoleW", handle))
        self.last_input_buffer = buffer
        control_fields = ctypes.cast(
            control, ctypes.POINTER(ctypes.c_ulong * 4)
        ).contents
        self.ctrl_wakeup_mask = int(control_fields[2])
        if self.interrupt_read:
            raise KeyboardInterrupt
        entered = self.input_text + ("\r\n" if self.append_line_ending else "")
        self.assert_fits(entered, int(capacity))
        source = ctypes.create_unicode_buffer(entered)
        ctypes.memmove(
            buffer,
            source,
            len(entered) * ctypes.sizeof(ctypes.c_wchar),
        )
        count = ctypes.cast(
            count_pointer, ctypes.POINTER(ctypes.c_ulong)
        )
        count.contents.value = len(entered)
        return 1

    @staticmethod
    def assert_fits(value: str, capacity: int) -> None:
        if len(value) > capacity:
            raise AssertionError("synthetic input did not fit fake console buffer")

    def _write_console(
        self,
        handle: int,
        message: str,
        length: int,
        written_pointer: Any,
        _reserved: Any,
    ) -> int:
        self.calls.append(("WriteConsoleW", handle))
        self.safe_writes.append(message)
        self.requested_write_lengths.append(int(length))
        written = ctypes.cast(
            written_pointer, ctypes.POINTER(ctypes.c_ulong)
        )
        written.contents.value = int(length)
        return 1

    def _close_handle(self, handle: int) -> int:
        self.calls.append(("CloseHandle", handle))
        return 0 if self.fail_close else 1

    def _wide_to_utf8(
        self,
        _code_page: int,
        _flags: int,
        wide: Any,
        wide_length: int,
        output: Any,
        output_size: int,
        _default: Any,
        _used_default: Any,
    ) -> int:
        data = ctypes.wstring_at(wide, int(wide_length)).encode("utf-8")
        if output is None or int(output_size) == 0:
            return len(data)
        ctypes.memmove(output, data, len(data))
        return len(data)


class VisibleConsoleSecretPromptTests(unittest.TestCase):
    def test_success_uses_new_console_with_echo_disabled_and_no_public_output(self) -> None:
        kernel32 = FakeConsoleKernel32()
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            secret = prompt_masked_secret_in_new_console(
                request_id=REQUEST_ID,
                context=PROMPT_CONTEXT,
                kernel32=kernel32,
                platform_name="nt",
            )

        self.assertEqual(secret, bytearray(SYNTHETIC_SECRET.encode("utf-8")))
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(
            [value for name, value in kernel32.calls if name == "CreateFileW"],
            ["CONIN$", "CONOUT$"],
        )
        self.assertEqual(
            kernel32.modes,
            [ENABLE_LINE_INPUT, 0x0007],
        )
        self.assertEqual(kernel32.input_code_pages, [CP_UTF8, 949])
        self.assertEqual(kernel32.output_code_pages, [CP_UTF8, 949])
        self.assertEqual(
            [name for name, _value in kernel32.calls].count("FreeConsole"),
            2,
        )
        self.assertEqual(kernel32.ctrl_wakeup_mask, (1 << 0x03))
        rendered = "".join(kernel32.safe_writes)
        self.assertNotIn(SYNTHETIC_SECRET, rendered)
        self.assertIn("도우미 AI가 설명한 현재 작업", rendered)
        self.assertIn(PROMPT_CONTEXT.task_summary, rendered)
        self.assertIn(PROMPT_CONTEXT.connection_reason, rendered)
        self.assertIn(
            "입력한 자격 증명은 도우미 AI와 채팅에 전달되지 않습니다.",
            rendered,
        )
        self.assertIn("클립보드 내용을 직접 읽지 않습니다", rendered)
        self.assertIn("이 창에 붙여넣은 내용만 숨김 입력", rendered)
        self.assertIn("Windows 자격 증명 관리자", rendered)
        self.assertNotIn("???", rendered)
        self.assertNotIn(SYNTHETIC_SECRET, repr(kernel32.calls))
        self.assertIsNotNone(kernel32.last_input_buffer)
        self.assertEqual(
            ctypes.string_at(
                ctypes.addressof(kernel32.last_input_buffer),
                ctypes.sizeof(kernel32.last_input_buffer),
            ),
            b"\x00" * ctypes.sizeof(kernel32.last_input_buffer),
        )

    def test_non_bmp_task_context_is_written_as_complete_utf16(self) -> None:
        context = VisibleConsolePromptContext(
            provider="notion",
            purpose="notion_page_recovery",
            account_label="검토된 연구 계정",
            workspace_label="복구 대상 작업공간",
            task_summary="검토한 페이지를 복구하고 있습니다. 📘",
            connection_reason="해당 작업공간 연결이 필요합니다. 🔐",
        )
        kernel32 = FakeConsoleKernel32()

        secret = prompt_masked_secret_in_new_console(
            request_id=REQUEST_ID,
            context=context,
            kernel32=kernel32,
            platform_name="nt",
        )

        self.assertEqual(secret, bytearray(SYNTHETIC_SECRET.encode("utf-8")))
        rendered = "".join(kernel32.safe_writes)
        self.assertIn(context.task_summary, rendered)
        self.assertIn(context.connection_reason, rendered)
        self.assertNotIn("?", rendered)
        for message, requested in zip(
            kernel32.safe_writes,
            kernel32.requested_write_lengths,
            strict=True,
        ):
            self.assertEqual(
                requested,
                len(message.encode("utf-16-le")) // 2,
            )

    def test_empty_enter_and_ctrl_c_cancel_without_a_secret(self) -> None:
        for kernel32 in (
            FakeConsoleKernel32(input_text=""),
            FakeConsoleKernel32(input_text="\x03", append_line_ending=False),
            FakeConsoleKernel32(interrupt_read=True),
        ):
            with self.subTest(interrupt_read=kernel32.interrupt_read):
                self.assertIsNone(
                    prompt_masked_secret_in_new_console(
                        request_id=REQUEST_ID,
                        context=PROMPT_CONTEXT,
                        kernel32=kernel32,
                        platform_name="nt",
                    )
                )
                self.assertIn("입력을 취소했습니다", "".join(kernel32.safe_writes))

    def test_worker_without_inherited_console_still_allocates_visible_console(self) -> None:
        kernel32 = FakeConsoleKernel32(no_inherited_console=True)
        secret = prompt_masked_secret_in_new_console(
            request_id=REQUEST_ID,
            context=PROMPT_CONTEXT,
            kernel32=kernel32,
            platform_name="nt",
        )
        self.assertEqual(secret, bytearray(SYNTHETIC_SECRET.encode("utf-8")))
        self.assertEqual(
            [name for name, _value in kernel32.calls[:2]],
            ["FreeConsole", "AllocConsole"],
        )

    def test_invalid_request_fails_before_any_console_side_effect(self) -> None:
        kernel32 = FakeConsoleKernel32()
        with self.assertRaises(VisibleConsoleSecretPromptError) as error:
            prompt_masked_secret_in_new_console(
                request_id="not-valid",
                context=PROMPT_CONTEXT,
                kernel32=kernel32,
                platform_name="nt",
            )
        self.assertEqual(error.exception.code, "windows_visible_console_failed")
        self.assertEqual(kernel32.calls, [])

    def test_multiline_and_utf8_over_limit_fail_closed_without_echo(self) -> None:
        for entered in ("first\r\nsecond", "한" * 900):
            kernel32 = FakeConsoleKernel32(input_text=entered)
            with self.subTest(kind="multiline" if "\r" in entered else "oversize"):
                with self.assertRaises(VisibleConsoleSecretPromptError):
                    prompt_masked_secret_in_new_console(
                        request_id=REQUEST_ID,
                        context=PROMPT_CONTEXT,
                        kernel32=kernel32,
                        platform_name="nt",
                    )
                self.assertNotIn(entered, "".join(kernel32.safe_writes))

    def test_cleanup_failure_rejects_the_secret_instead_of_continuing_to_store(self) -> None:
        kernel32 = FakeConsoleKernel32(fail_close=True)
        with self.assertRaises(VisibleConsoleSecretPromptError):
            prompt_masked_secret_in_new_console(
                request_id=REQUEST_ID,
                context=PROMPT_CONTEXT,
                kernel32=kernel32,
                platform_name="nt",
            )
        self.assertNotIn(SYNTHETIC_SECRET, "".join(kernel32.safe_writes))


if __name__ == "__main__":
    unittest.main()
