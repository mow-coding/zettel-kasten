from __future__ import annotations

import importlib.util
import io
import json
import unittest
from pathlib import Path
from typing import Any
from unittest import mock


TOOL_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "check_windows_credential_console_host.py"
)
SPEC = importlib.util.spec_from_file_location("wom_popup_acceptance", TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("acceptance_tool_import_failed")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


class WindowsCredentialPopupAcceptanceTests(unittest.TestCase):
    PASS_HUMAN_ANSWERS = (True, True, True, True, False, True, True, True)
    PASS_MACHINE_EVIDENCE = (True, True, False, True, True)

    def run_row(
        self,
        *,
        machine_evidence: tuple[bool, bool, bool, bool, bool] | None = None,
        human_answers: tuple[bool, ...] | None = None,
        host_family: str = "codex_desktop",
        launch_route: str = "codex_desktop_native_popup",
        gesture: str = "direct_keyboard_typing",
    ) -> tuple[dict[str, Any], str, list[str]]:
        evidence = machine_evidence or self.PASS_MACHINE_EVIDENCE
        answers = iter(human_answers or self.PASS_HUMAN_ANSWERS)
        asked: list[str] = []
        output = io.StringIO()

        def answer(question: str) -> bool:
            asked.append(question)
            return next(answers)

        result = TOOL.run_manual_acceptance(
            host_family=host_family,
            launch_route=launch_route,
            gesture=gesture,
            input_stream=io.StringIO("\n"),
            output_stream=output,
            prompt_runner=lambda: evidence,
            question_function=answer,
        )
        return result, output.getvalue(), asked

    def test_exact_synthetic_popup_row_is_content_free(self) -> None:
        result, output, _asked = self.run_row()

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["schema_version"],
            "wom-kit/windows-credential-popup-acceptance/v0.1",
        )
        self.assertEqual(result["test_intent"], "synthetic_popup_acceptance_only")
        self.assertEqual(result["actual_host_acceptance_status"], "passed")
        self.assertEqual(
            result["machine_input_classification"],
            "exact_synthetic_input_received",
        )
        for key in (
            "synthetic_only_acknowledged",
            "popup_observed",
            "synthetic_test_copy_observed",
            "human_physical_gesture_attested",
            "credential_input_received",
            "complete_line_received",
            "nonempty_line_received",
            "exact_synthetic_line_received",
            "confirm_gate_observed",
            "popup_closed_after_confirmation",
            "korean_rendered_legibly",
        ):
            with self.subTest(key=key):
                self.assertIs(result[key], True)
        for key in (
            "cancelled",
            "value_mask_or_length_observed",
            "actual_credential_registration_performed",
            "actual_pat_requested",
            "product_clipboard_read_performed",
            "credential_store_write_performed",
            "provider_request_performed",
            "result_contains_input_value",
        ):
            with self.subTest(key=key):
                self.assertIs(result[key], False)
        serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(TOOL.SYNTHETIC_LINE, serialized)
        self.assertNotIn("ntn_", serialized.lower())
        self.assertIn(TOOL.SYNTHETIC_LINE, output)
        self.assertIn("실제 자격증명 등록이 아닙니다", output)
        self.assertIn("실제 PAT를 요구하지 않", output)

    def test_mismatch_and_cancel_rows_do_not_pass(self) -> None:
        rows = (
            (
                (True, True, False, True, False),
                "nonempty_input_mismatch",
            ),
            (
                (False, False, True, False, False),
                "no_input",
            ),
            (
                (True, False, True, False, False),
                "partial_input_cancelled",
            ),
        )
        for evidence, classification in rows:
            with self.subTest(evidence=evidence):
                result, _output, _asked = self.run_row(machine_evidence=evidence)
                self.assertFalse(result["ok"])
                self.assertEqual(result["actual_host_acceptance_status"], "failed")
                self.assertEqual(result["machine_input_classification"], classification)
                self.assertNotIn(TOOL.SYNTHETIC_LINE, repr(result))

    def test_questions_are_chronological_and_separate_attempt_from_perception(self) -> None:
        result, _output, asked = self.run_row(gesture="ctrl_v")
        self.assertTrue(result["ok"])
        self.assertEqual(len(asked), 8)
        self.assertIn("고정 합성 문자열만", asked[0])
        self.assertIn("별도 WOM native popup", asked[1])
        self.assertIn("합성 입력 테스트", asked[2])
        self.assertIn("성공한 것처럼 보였는지와 관계없이", asked[3])
        self.assertIn("Ctrl+V", asked[3])
        self.assertIn("길이를 알 수 있는 표시", asked[4])
        self.assertIn("빈 입력에서는 확인이 비활성화", asked[5])
        self.assertIn("popup이 정상적으로 닫혔", asked[6])
        self.assertIn("겹침·잘림", asked[7])

    def test_synthetic_acknowledgement_blocks_popup_before_launch(self) -> None:
        called: list[bool] = []
        with self.assertRaisesRegex(
            RuntimeError,
            "^manual_acceptance_synthetic_only_not_acknowledged$",
        ):
            TOOL.run_manual_acceptance(
                host_family="codex_desktop",
                launch_route="codex_desktop_native_popup",
                gesture="direct_keyboard_typing",
                input_stream=io.StringIO("\n"),
                output_stream=io.StringIO(),
                prompt_runner=lambda: called.append(True),
                question_function=lambda _text: False,
            )
        self.assertEqual(called, [])

    def test_each_post_popup_human_observation_fails_closed(self) -> None:
        for index in range(1, len(self.PASS_HUMAN_ANSWERS)):
            answers = list(self.PASS_HUMAN_ANSWERS)
            answers[index] = not answers[index]
            with self.subTest(index=index):
                result, _output, _asked = self.run_row(human_answers=tuple(answers))
                self.assertFalse(result["ok"])
                self.assertNotIn(TOOL.SYNTHETIC_LINE, repr(result))

    def test_routes_and_gestures_are_popup_only_and_closed(self) -> None:
        expected_routes = {
            "codex_desktop": "codex_desktop_native_popup",
            "windows_terminal": "windows_terminal_native_popup",
            "console_host": "console_host_native_popup",
            "conpty_parent": "conpty_parent_native_popup",
        }
        self.assertEqual(TOOL.HOST_LAUNCH_ROUTES, expected_routes)
        self.assertEqual(
            TOOL.GESTURES,
            (
                "direct_keyboard_typing",
                "ctrl_v",
                "shift_insert",
                "right_click_menu_paste",
            ),
        )
        for host, route, gesture in (
            ("unknown", "codex_desktop_native_popup", "ctrl_v"),
            ("codex_desktop", "windows_terminal_native_popup", "ctrl_v"),
            ("codex_desktop", "codex_desktop_native_popup", "ctrl_shift_v"),
            ("codex_desktop", "codex_desktop_attached_parent_console", "ctrl_v"),
        ):
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

    def test_machine_classification_is_strict_and_content_free(self) -> None:
        valid = {
            (False, False, False, False): "no_input",
            (True, False, False, False): "partial_input_cancelled",
            (True, True, False, False): "empty_confirmation",
            (True, True, True, False): "nonempty_input_mismatch",
            (True, True, True, True): "exact_synthetic_input_received",
        }
        for vector, classification in valid.items():
            with self.subTest(vector=vector):
                actual = TOOL._classify_machine_input(
                    credential_input_received=vector[0],
                    complete_line_received=vector[1],
                    nonempty_line_received=vector[2],
                    exact_synthetic_line_received=vector[3],
                )
                self.assertEqual(actual, classification)
                self.assertNotIn(TOOL.SYNTHETIC_LINE, actual)
        for vector in (
            (False, False, False, True),
            (False, False, True, False),
            (False, True, False, False),
            (True, False, True, False),
            (True, True, False, True),
        ):
            with self.subTest(vector=vector):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "^manual_acceptance_worker_result_invalid$",
                ):
                    TOOL._classify_machine_input(
                        credential_input_received=vector[0],
                        complete_line_received=vector[1],
                        nonempty_line_received=vector[2],
                        exact_synthetic_line_received=vector[3],
                    )
        with self.assertRaises(RuntimeError):
            TOOL._classify_machine_input(
                credential_input_received=1,
                complete_line_received=True,
                nonempty_line_received=True,
                exact_synthetic_line_received=True,
            )

    def test_non_boolean_machine_and_human_seams_fail_closed(self) -> None:
        for evidence in (
            (1, True, False, True, True),
            (True, True, False, True, "yes"),
            [True, True, False, True, True],
            (True, True),
            (True, True, True, True, True),
            (False, False, False, False, False),
        ):
            with self.subTest(evidence=evidence):
                with self.assertRaises(RuntimeError):
                    TOOL.run_manual_acceptance(
                        host_family="codex_desktop",
                        launch_route="codex_desktop_native_popup",
                        gesture="direct_keyboard_typing",
                        input_stream=io.StringIO("\n"),
                        output_stream=io.StringIO(),
                        prompt_runner=lambda evidence=evidence: evidence,
                        question_function=lambda _text: True,
                    )
        answers = iter((True, True, True, True, "yes", True, True, True))
        with self.assertRaisesRegex(
            RuntimeError,
            "^manual_acceptance_observation_invalid$",
        ):
            TOOL.run_manual_acceptance(
                host_family="codex_desktop",
                launch_route="codex_desktop_native_popup",
                gesture="direct_keyboard_typing",
                input_stream=io.StringIO("\n"),
                output_stream=io.StringIO(),
                prompt_runner=lambda: self.PASS_MACHINE_EVIDENCE,
                question_function=lambda _text: next(answers),
            )

    def test_child_detaches_then_uses_synthetic_popup_context_and_wipes(self) -> None:
        returned = bytearray(TOOL.SYNTHETIC_LINE.encode("utf-8"))
        input_result = TOOL.HumanSecretInputResult(
            secret=returned,
            credential_input_received=True,
            complete_line_received=True,
            cancelled=False,
        )

        class FakeConnection:
            def __init__(self) -> None:
                self.messages: list[Any] = []
                self.closed = False

            def send(self, value: Any) -> None:
                self.messages.append(value)

            def close(self) -> None:
                self.closed = True

        events: list[str] = []
        contexts: list[Any] = []
        input_intents: list[Any] = []
        wiped: list[bytearray] = []
        connection = FakeConnection()
        original_wipe = TOOL._wipe

        def fake_detach() -> bool:
            events.append("detach")
            return True

        def fake_prompt(**kwargs: Any) -> Any:
            events.append("popup")
            contexts.append(kwargs["context"])
            input_intents.append(kwargs["input_intent"])
            return input_result

        def observing_wipe(value: bytearray) -> None:
            wiped.append(value)
            original_wipe(value)

        with (
            mock.patch.object(
                TOOL,
                "_detach_spawned_popup_child_console",
                side_effect=fake_detach,
            ),
            mock.patch.object(
                TOOL,
                "prompt_secret_in_native_popup",
                side_effect=fake_prompt,
            ),
            mock.patch.object(TOOL, "_wipe", side_effect=observing_wipe),
        ):
            TOOL._prompt_child(connection)

        self.assertEqual(events, ["detach", "popup"])
        self.assertEqual(connection.messages[0], TOOL._ACK)
        self.assertEqual(connection.messages[1]["worker_transport_status"], "popup_result")
        self.assertTrue(connection.messages[1]["exact_synthetic_line_received"])
        self.assertTrue(connection.closed)
        self.assertEqual(len(contexts), 1)
        self.assertIs(
            input_intents[0],
            TOOL.CredentialPopupInputIntent.synthetic_acceptance,
        )
        self.assertIn(TOOL.SYNTHETIC_LINE, contexts[0].task_summary)
        self.assertIn("실제 PAT를 입력하지 말고", contexts[0].connection_reason)
        self.assertEqual(returned, bytearray(len(returned)))
        self.assertEqual(len(wiped), 2)
        self.assertTrue(all(value == bytearray(len(value)) for value in wiped))

    def test_detach_failure_never_opens_popup_or_sends_live_ack(self) -> None:
        class FakeConnection:
            def __init__(self) -> None:
                self.messages: list[Any] = []

            def send(self, value: Any) -> None:
                self.messages.append(value)

            def close(self) -> None:
                pass

        for outcome in (False, RuntimeError("synthetic")):
            connection = FakeConnection()
            popup_calls: list[bool] = []
            side_effect = outcome if isinstance(outcome, BaseException) else None
            with self.subTest(outcome=repr(outcome)), mock.patch.object(
                TOOL,
                "_detach_spawned_popup_child_console",
                return_value=None if side_effect else outcome,
                side_effect=side_effect,
            ), mock.patch.object(
                TOOL,
                "prompt_secret_in_native_popup",
                side_effect=lambda **_kwargs: popup_calls.append(True),
            ):
                TOOL._prompt_child(connection)
            self.assertEqual(popup_calls, [])
            self.assertEqual(
                connection.messages,
                []
                if outcome is False
                else [{"worker_transport_status": "popup_failed"}],
            )

    def test_spawned_runner_requires_ack_final_eof_then_join(self) -> None:
        events: list[str] = []
        final = {
            "worker_transport_status": "popup_result",
            "credential_input_received": True,
            "complete_line_received": True,
            "cancelled": False,
            "nonempty_line_received": True,
            "exact_synthetic_line_received": True,
        }

        class Receiver:
            def __init__(self) -> None:
                self.messages = iter((dict(TOOL._ACK), final))

            def recv(self) -> Any:
                try:
                    message = next(self.messages)
                except StopIteration:
                    events.append("eof")
                    raise EOFError
                events.append("recv")
                return message

            def close(self) -> None:
                events.append("receiver_close")

        class Sender:
            def close(self) -> None:
                events.append("sender_close")

        class Process:
            exitcode = 0

            def start(self) -> None:
                events.append("start")

            def join(self) -> None:
                events.append("join")

            def is_alive(self) -> bool:
                return False

        class Context:
            def Pipe(self, *, duplex: bool) -> tuple[Any, Any]:
                self.duplex = duplex
                events.append("pipe")
                return Receiver(), Sender()

            def Process(self, **kwargs: Any) -> Any:
                self.kwargs = kwargs
                self.testcase.assertIs(kwargs["target"], TOOL._prompt_child)
                self.testcase.assertFalse(kwargs["daemon"])
                return Process()

            testcase = self

        lease = object()
        with (
            mock.patch.object(
                TOOL.multiprocessing,
                "get_context",
                return_value=Context(),
            ),
            mock.patch.object(
                TOOL,
                "_capture_credential_worker_start_signal_lease",
                side_effect=lambda **_kwargs: events.append("capture") or lease,
            ),
            mock.patch.object(
                TOOL,
                "_install_credential_worker_start_signal_lease",
                side_effect=lambda *_args, **_kwargs: events.append("install") or True,
            ),
            mock.patch.object(
                TOOL,
                "_restore_credential_worker_start_signal_lease",
                side_effect=lambda *_args, **_kwargs: events.append("restore"),
            ),
        ):
            evidence = TOOL._run_prompt_in_spawned_worker()

        self.assertEqual(evidence, self.PASS_MACHINE_EVIDENCE)
        self.assertLess(events.index("capture"), events.index("install"))
        self.assertLess(events.index("install"), events.index("start"))
        self.assertLess(events.index("start"), events.index("restore"))
        self.assertLess(events.index("restore"), events.index("recv"))
        self.assertLess(events.index("start"), events.index("recv"))
        self.assertLess(events.index("eof"), events.index("join"))
        self.assertLess(events.index("join"), events.index("receiver_close"))

    def test_start_interrupt_after_possible_child_creation_drains_ack_final_eof(self) -> None:
        events: list[str] = []
        final = {
            "worker_transport_status": "popup_result",
            "credential_input_received": True,
            "complete_line_received": True,
            "cancelled": False,
            "nonempty_line_received": True,
            "exact_synthetic_line_received": True,
        }

        class Receiver:
            def __init__(self) -> None:
                self.messages = iter((dict(TOOL._ACK), final))

            def recv(self) -> Any:
                try:
                    value = next(self.messages)
                except StopIteration:
                    events.append("eof")
                    raise EOFError
                events.append("recv")
                return value

            def close(self) -> None:
                events.append("receiver_close")

        class Sender:
            def close(self) -> None:
                events.append("sender_close")

        class Process:
            exitcode = None

            def start(self) -> None:
                events.append("start_created_then_interrupt")
                raise KeyboardInterrupt

            def join(self) -> None:
                raise AssertionError("ambiguous public start must use EOF containment")

            def is_alive(self) -> bool:
                raise AssertionError("ambiguous public start has no joinability proof")

        class Context:
            def Pipe(self, *, duplex: bool) -> tuple[Any, Any]:
                self.duplex = duplex
                return Receiver(), Sender()

            def Process(self, **_kwargs: Any) -> Any:
                return Process()

        lease = object()
        with (
            mock.patch.object(TOOL.multiprocessing, "get_context", return_value=Context()),
            mock.patch.object(
                TOOL,
                "_capture_credential_worker_start_signal_lease",
                return_value=lease,
            ),
            mock.patch.object(
                TOOL,
                "_install_credential_worker_start_signal_lease",
                return_value=True,
            ),
            mock.patch.object(
                TOOL,
                "_restore_credential_worker_start_signal_lease",
                side_effect=lambda *_args, **_kwargs: events.append("restore"),
            ),
        ):
            evidence = TOOL._run_prompt_in_spawned_worker()

        self.assertEqual(evidence, self.PASS_MACHINE_EVIDENCE)
        self.assertLess(events.index("start_created_then_interrupt"), events.index("restore"))
        self.assertLess(events.index("restore"), events.index("recv"))
        self.assertIn("eof", events)

    def test_pre_start_lease_failure_restores_and_never_starts_or_receives(self) -> None:
        events: list[str] = []

        class Receiver:
            def recv(self) -> Any:
                events.append("recv")
                raise AssertionError("pre-start failure must not receive")

            def close(self) -> None:
                events.append("receiver_close")

        class Sender:
            def close(self) -> None:
                events.append("sender_close")

        class Process:
            exitcode = None

            def start(self) -> None:
                events.append("start")

        class Context:
            def Pipe(self, *, duplex: bool) -> tuple[Any, Any]:
                self.duplex = duplex
                return Receiver(), Sender()

            def Process(self, **_kwargs: Any) -> Any:
                return Process()

        lease = object()
        with (
            mock.patch.object(TOOL.multiprocessing, "get_context", return_value=Context()),
            mock.patch.object(
                TOOL,
                "_capture_credential_worker_start_signal_lease",
                return_value=lease,
            ),
            mock.patch.object(
                TOOL,
                "_install_credential_worker_start_signal_lease",
                return_value=False,
            ),
            mock.patch.object(
                TOOL,
                "_restore_credential_worker_start_signal_lease",
                side_effect=lambda *_args, **_kwargs: events.append("restore"),
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "^manual_acceptance_worker_failed$",
            ):
                TOOL._run_prompt_in_spawned_worker()

        self.assertEqual(events.count("restore"), 1)
        self.assertNotIn("start", events)
        self.assertNotIn("recv", events)
        self.assertIn("sender_close", events)

    def test_interrupt_during_post_start_pipe_wait_cannot_escape_or_skip_join(self) -> None:
        events: list[str] = []
        final = {
            "worker_transport_status": "popup_result",
            "credential_input_received": True,
            "complete_line_received": True,
            "cancelled": False,
            "nonempty_line_received": True,
            "exact_synthetic_line_received": True,
        }

        class Receiver:
            def __init__(self) -> None:
                self.calls = 0
                self.messages = iter((dict(TOOL._ACK), final))

            def recv(self) -> Any:
                self.calls += 1
                if self.calls == 1:
                    events.append("wait_interrupt")
                    raise KeyboardInterrupt
                try:
                    value = next(self.messages)
                except StopIteration:
                    events.append("eof")
                    raise EOFError
                events.append("recv")
                return value

            def close(self) -> None:
                pass

        class Sender:
            def close(self) -> None:
                pass

        class Process:
            exitcode = 0

            def start(self) -> None:
                events.append("start")

            def join(self) -> None:
                events.append("join")

            def is_alive(self) -> bool:
                return False

        class Context:
            def Pipe(self, *, duplex: bool) -> tuple[Any, Any]:
                self.duplex = duplex
                return Receiver(), Sender()

            def Process(self, **_kwargs: Any) -> Any:
                return Process()

        with (
            mock.patch.object(TOOL.multiprocessing, "get_context", return_value=Context()),
            mock.patch.object(
                TOOL,
                "_capture_credential_worker_start_signal_lease",
                return_value=object(),
            ),
            mock.patch.object(
                TOOL,
                "_install_credential_worker_start_signal_lease",
                return_value=True,
            ),
            mock.patch.object(
                TOOL,
                "_restore_credential_worker_start_signal_lease",
                return_value=None,
            ),
        ):
            evidence = TOOL._run_prompt_in_spawned_worker()

        self.assertEqual(evidence, self.PASS_MACHINE_EVIDENCE)
        self.assertEqual(events[:2], ["start", "wait_interrupt"])
        self.assertLess(events.index("eof"), events.index("join"))

    def test_failure_and_not_performed_json_are_safe_and_synthetic_only(self) -> None:
        class TTYStringIO(io.StringIO):
            def isatty(self) -> bool:
                return True

        arguments = [
            "--host-family",
            "codex_desktop",
            "--launch-route",
            "codex_desktop_native_popup",
            "--gesture",
            "direct_keyboard_typing",
        ]
        not_performed_output = TTYStringIO()
        with (
            mock.patch.object(TOOL.os, "name", "posix"),
            mock.patch.object(TOOL.sys, "stdout", not_performed_output),
        ):
            self.assertEqual(TOOL.main(arguments), 2)
        not_performed = json.loads(not_performed_output.getvalue())

        failure_output = TTYStringIO()
        with (
            mock.patch.object(TOOL.os, "name", "nt"),
            mock.patch.object(TOOL.sys, "stdin", TTYStringIO()),
            mock.patch.object(TOOL.sys, "stdout", failure_output),
            mock.patch.object(
                TOOL,
                "run_manual_acceptance",
                side_effect=RuntimeError("PRIVATE_SENTINEL"),
            ),
        ):
            self.assertEqual(TOOL.main(arguments), 1)
        failure = json.loads(failure_output.getvalue())

        for payload in (not_performed, failure):
            serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            self.assertEqual(payload["schema_version"], TOOL.SCHEMA_VERSION)
            self.assertEqual(payload["test_intent"], "synthetic_popup_acceptance_only")
            self.assertFalse(payload["actual_credential_registration_performed"])
            self.assertFalse(payload["actual_pat_requested"])
            self.assertFalse(payload["credential_store_write_performed"])
            self.assertFalse(payload["provider_request_performed"])
            self.assertNotIn(TOOL.SYNTHETIC_LINE, serialized)
            self.assertNotIn("PRIVATE_SENTINEL", serialized)
            self.assertNotIn("ntn_", serialized.lower())

    def test_source_contains_no_withdrawn_terminal_contract(self) -> None:
        source = TOOL_PATH.read_text(encoding="utf-8")
        for required in (
            'SCHEMA_VERSION = "wom-kit/windows-credential-popup-acceptance/v0.1"',
            "prompt_secret_in_native_popup",
            "CredentialPopupInputIntent.synthetic_acceptance",
            '"codex_desktop_native_popup"',
            '"synthetic_popup_acceptance_only"',
            '"actual_credential_registration_performed": False',
            '"actual_pat_requested": False',
            '"credential_store_write_performed": False',
            '"provider_request_performed": False',
            '"result_contains_input_value": False',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        for forbidden in (
            "prompt_masked_secret_in_attached_console",
            "codex_desktop_attached_parent_console",
            "conpty_parent_attached_console",
            "CONIN$",
            "CONOUT$",
            "ReadConsoleW",
            "windows-credential-console-host-acceptance/v0.4",
            "같은 현재 터미널",
            "no separate window",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
