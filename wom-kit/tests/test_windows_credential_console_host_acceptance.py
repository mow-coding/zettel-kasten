from __future__ import annotations

import importlib.util
import io
import unittest
from pathlib import Path
from typing import Any


TOOL_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "check_windows_credential_console_host.py"
)
SPEC = importlib.util.spec_from_file_location("wom_console_host_acceptance", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("acceptance_tool_import_failed")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class WindowsCredentialConsoleHostAcceptanceTests(unittest.TestCase):
    def test_exact_manual_row_is_content_free(self) -> None:
        questions = iter((False, True, True))
        output = io.StringIO()
        result = TOOL.run_manual_acceptance(
            host_family="windows_terminal",
            launch_route="direct_terminal",
            gesture="ctrl_v",
            input_stream=io.StringIO("\n"),
            output_stream=output,
            prompt_runner=lambda: (True, True),
            question_function=lambda _text: next(questions),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["schema_version"],
            "wom-kit/windows-credential-console-host-acceptance/v0.1",
        )
        self.assertEqual(result["automated_win32_boundary_status"], "not_performed")
        self.assertEqual(result["actual_host_acceptance_status"], "passed")
        self.assertIsInstance(result["os_build"], str)
        self.assertTrue(result["os_build"])
        self.assertTrue(result["nonempty_line_received"])
        self.assertTrue(result["exact_synthetic_line_received"])
        self.assertFalse(result["echo_observed"])
        self.assertTrue(result["korean_rendered_without_question_marks"])
        self.assertTrue(result["receipt_status_observed"])
        self.assertFalse(result["product_clipboard_read_performed"])
        self.assertFalse(result["credential_store_write_performed"])
        self.assertFalse(result["provider_request_performed"])
        self.assertFalse(result["result_contains_input_value"])
        serialized = repr(result)
        self.assertNotIn(TOOL.SYNTHETIC_LINE, serialized)
        self.assertNotIn("ntn_", serialized.lower())
        self.assertIn(TOOL.SYNTHETIC_LINE, output.getvalue())

    def test_wrong_line_or_negative_visual_observation_fails_without_value(self) -> None:
        cases = (
            ((True, False), (False, True, True)),
            ((True, True), (True, True, True)),
            ((True, True), (False, False, True)),
            ((True, True), (False, True, False)),
        )
        for prompt_result, answers in cases:
            with self.subTest(answers=answers):
                questions = iter(answers)
                result = TOOL.run_manual_acceptance(
                    host_family="console_host",
                    launch_route="console_host_child",
                    gesture="shift_insert",
                    input_stream=io.StringIO("\n"),
                    output_stream=io.StringIO(),
                    prompt_runner=lambda: prompt_result,
                    question_function=lambda _text: next(questions),
                )
                self.assertFalse(result["ok"])
                self.assertEqual(result["actual_host_acceptance_status"], "failed")
                self.assertNotIn(TOOL.SYNTHETIC_LINE, repr(result))

    def test_spawn_runner_returns_only_two_booleans_to_the_parent_contract(self) -> None:
        questions = iter((False, True, True))
        result = TOOL.run_manual_acceptance(
            host_family="conpty_parent",
            launch_route="conpty_parent_allocconsole",
            gesture="ctrl_shift_v",
            input_stream=io.StringIO("\n"),
            output_stream=io.StringIO(),
            prompt_runner=lambda: (True, True),
            question_function=lambda _text: next(questions),
        )
        self.assertTrue(result["ok"])
        self.assertNotIn(TOOL.SYNTHETIC_LINE, repr(result))

    def test_enums_are_bounded_and_closed_before_prompt(self) -> None:
        invalid_rows = (
            ("unknown", "direct_terminal", "ctrl_v"),
            ("windows_terminal", "unknown", "ctrl_v"),
            ("windows_terminal", "direct_terminal", "unknown"),
            ("windows_terminal", "console_host_child", "ctrl_v"),
            (None, "direct_terminal", "ctrl_v"),
        )
        for host, route, gesture in invalid_rows:
            with self.subTest(host=host, route=route, gesture=gesture):
                called: list[bool] = []
                with self.assertRaises(ValueError):
                    TOOL.run_manual_acceptance(
                        host_family=host,
                        launch_route=route,
                        gesture=gesture,
                        input_stream=io.StringIO("\n"),
                        output_stream=io.StringIO(),
                        prompt_runner=lambda: called.append(True),
                        question_function=lambda _text: True,
                    )
                self.assertEqual(called, [])

    def test_non_boolean_seams_fail_without_public_projection(self) -> None:
        invalid_prompt_results = ((1, True), (True, "SAFE_NON_BOOL"), [True, True])
        for prompt_result in invalid_prompt_results:
            with self.subTest(prompt_result=prompt_result):
                with self.assertRaises(RuntimeError):
                    TOOL.run_manual_acceptance(
                        host_family="windows_terminal",
                        launch_route="direct_terminal",
                        gesture="ctrl_v",
                        input_stream=io.StringIO("\n"),
                        output_stream=io.StringIO(),
                        prompt_runner=lambda: prompt_result,
                        question_function=lambda _text: True,
                    )
        answers = iter(("SAFE_NON_BOOL", True, True))
        with self.assertRaises(RuntimeError):
            TOOL.run_manual_acceptance(
                host_family="windows_terminal",
                launch_route="direct_terminal",
                gesture="ctrl_v",
                input_stream=io.StringIO("\n"),
                output_stream=io.StringIO(),
                prompt_runner=lambda: (True, True),
                question_function=lambda _text: next(answers),
            )

    def test_child_returns_only_booleans_and_wipes_both_buffers(self) -> None:
        returned = bytearray(TOOL.SYNTHETIC_LINE.encode("utf-8"))

        class FakeConnection:
            def __init__(self) -> None:
                self.messages: list[Any] = []
                self.closed = False

            def send(self, value: Any) -> None:
                self.messages.append(value)

            def close(self) -> None:
                self.closed = True

        connection = FakeConnection()
        original = TOOL.prompt_masked_secret_in_new_console
        TOOL.prompt_masked_secret_in_new_console = lambda **_kwargs: returned
        try:
            TOOL._prompt_child(connection)
        finally:
            TOOL.prompt_masked_secret_in_new_console = original
        self.assertEqual(connection.messages, [(True, True)])
        self.assertTrue(connection.closed)
        self.assertEqual(returned, bytearray(len(returned)))


if __name__ == "__main__":
    unittest.main()
