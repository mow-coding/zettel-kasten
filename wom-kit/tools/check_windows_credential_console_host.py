from __future__ import annotations

import argparse
import hmac
import json
import multiprocessing
import os
import platform
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from wom_kit.credential_visible_console_windows import (  # noqa: E402
    VisibleConsolePromptContext,
    prompt_masked_secret_in_new_console,
)


SCHEMA_VERSION = "wom-kit/windows-credential-console-host-acceptance/v0.1"
SYNTHETIC_LINE = "WOM-PASTE-ACCEPTANCE-0318"
HOST_FAMILIES = ("windows_terminal", "console_host", "conpty_parent")
HOST_LAUNCH_ROUTES = {
    "windows_terminal": "direct_terminal",
    "console_host": "console_host_child",
    "conpty_parent": "conpty_parent_allocconsole",
}
LAUNCH_ROUTES = tuple(HOST_LAUNCH_ROUTES.values())
GESTURES = (
    "ctrl_v",
    "ctrl_shift_v",
    "shift_insert",
    "right_click_menu_paste",
)

QuestionFunction = Callable[[str], bool]
PromptRunner = Callable[[], tuple[bool, bool]]


def _wipe(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0


def _ask_yes_no(prompt: str, *, input_stream: TextIO, output_stream: TextIO) -> bool:
    while True:
        output_stream.write(f"{prompt} [y/n]: ")
        output_stream.flush()
        answer = input_stream.readline()
        if answer == "":
            raise RuntimeError("manual_acceptance_input_closed")
        normalized = answer.strip().lower()
        if normalized in {"y", "yes"}:
            return True
        if normalized in {"n", "no"}:
            return False


def _result(
    *,
    host_family: str,
    launch_route: str,
    gesture: str,
    nonempty_line_received: bool,
    exact_synthetic_line_received: bool,
    echo_observed: bool,
    korean_rendered_without_question_marks: bool,
    receipt_status_observed: bool,
) -> dict[str, Any]:
    observations = (
        nonempty_line_received,
        exact_synthetic_line_received,
        echo_observed,
        korean_rendered_without_question_marks,
        receipt_status_observed,
    )
    if any(type(value) is not bool for value in observations):
        raise RuntimeError("manual_acceptance_observation_invalid")
    passed = all(
        (
            nonempty_line_received,
            exact_synthetic_line_received,
            not echo_observed,
            korean_rendered_without_question_marks,
            receipt_status_observed,
        )
    )
    return {
        "ok": passed,
        "schema_version": SCHEMA_VERSION,
        "host_family": host_family,
        "os_build": platform.version(),
        "launch_route": launch_route,
        "gesture": gesture,
        "automated_win32_boundary_status": "not_performed",
        "actual_host_acceptance_status": "passed" if passed else "failed",
        "nonempty_line_received": nonempty_line_received,
        "exact_synthetic_line_received": exact_synthetic_line_received,
        "echo_observed": echo_observed,
        "korean_rendered_without_question_marks": korean_rendered_without_question_marks,
        "receipt_status_observed": receipt_status_observed,
        "product_clipboard_read_performed": False,
        "credential_store_write_performed": False,
        "provider_request_performed": False,
        "result_contains_input_value": False,
    }


def _prompt_child(connection: Any) -> None:
    received: bytearray | None = None
    expected = bytearray(SYNTHETIC_LINE.encode("utf-8"))
    try:
        received = prompt_masked_secret_in_new_console(
            request_id="intake_manual_host_acceptance_0318",
            context=VisibleConsolePromptContext(
                provider="notion",
                purpose="source_recovery",
                account_label="합성 붙여넣기 확인용 계정",
                workspace_label="합성 붙여넣기 확인용 작업공간",
                task_summary="실제 Windows 붙여넣기 동작을 확인하고 있습니다.",
                connection_reason="합성 문자열 수신과 안전한 숨김 입력을 확인해야 합니다.",
            ),
        )
        nonempty = isinstance(received, bytearray) and bool(received)
        exact = isinstance(received, bytearray) and hmac.compare_digest(received, expected)
        connection.send((nonempty, exact))
    except BaseException:
        try:
            connection.send((False, False))
        except BaseException:
            pass
    finally:
        if isinstance(received, bytearray):
            _wipe(received)
        _wipe(expected)
        try:
            connection.close()
        except BaseException:
            pass


def _run_prompt_in_spawned_worker(*, timeout_seconds: float = 600.0) -> tuple[bool, bool]:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_prompt_child, args=(sender,))
    process.start()
    sender.close()
    deadline = time.monotonic() + timeout_seconds
    message: Any = None
    try:
        while time.monotonic() < deadline:
            if receiver.poll(0.25):
                message = receiver.recv()
                break
            if not process.is_alive():
                break
        if message is None and process.is_alive():
            process.terminate()
        process.join(timeout=10.0)
    finally:
        receiver.close()
    if (
        process.is_alive()
        or process.exitcode != 0
        or not isinstance(message, tuple)
        or len(message) != 2
        or any(type(value) is not bool for value in message)
    ):
        raise RuntimeError("manual_acceptance_worker_failed")
    return message


def run_manual_acceptance(
    *,
    host_family: str,
    launch_route: str,
    gesture: str,
    input_stream: TextIO,
    output_stream: TextIO,
    prompt_runner: PromptRunner = _run_prompt_in_spawned_worker,
    question_function: QuestionFunction | None = None,
) -> dict[str, Any]:
    if type(host_family) is not str or host_family not in HOST_FAMILIES:
        raise ValueError("unsupported_host_family")
    if type(launch_route) is not str or launch_route not in LAUNCH_ROUTES:
        raise ValueError("unsupported_launch_route")
    if launch_route != HOST_LAUNCH_ROUTES[host_family]:
        raise ValueError("host_launch_route_mismatch")
    if type(gesture) is not str or gesture not in GESTURES:
        raise ValueError("unsupported_gesture")

    if question_function is None:
        question_function = lambda text: _ask_yes_no(  # noqa: E731
            text,
            input_stream=input_stream,
            output_stream=output_stream,
        )

    output_stream.write(
        "실제 Windows 붙여넣기 수동 확인 절차입니다. 실제 PAT를 사용하지 마세요.\n"
        "아래 합성 문자열만 복사하세요. 제품은 클립보드를 직접 읽지 않습니다.\n\n"
        f"{SYNTHETIC_LINE}\n\n"
        f"검증 제스처: {gesture}\n"
        "문자열을 복사했으면 Enter를 눌러 별도 WOM 창을 여세요: "
    )
    output_stream.flush()
    if input_stream.readline() == "":
        raise RuntimeError("manual_acceptance_input_closed")

    prompt_result = prompt_runner()
    if (
        not isinstance(prompt_result, tuple)
        or len(prompt_result) != 2
        or any(type(value) is not bool for value in prompt_result)
    ):
        raise RuntimeError("manual_acceptance_worker_result_invalid")
    nonempty, exact = prompt_result
    echo_observed = question_function(
        "붙여넣은 합성 문자열의 글자나 길이가 화면에 보였습니까?"
    )
    korean_ok = question_function("WOM 창의 한국어가 ??? 없이 정상 표시됐습니까?")
    receipt_observed = question_function(
        "'입력값을 받았습니다. 검증 중입니다.' 문구를 확인했습니까?"
    )
    if any(
        type(value) is not bool
        for value in (echo_observed, korean_ok, receipt_observed)
    ):
        raise RuntimeError("manual_acceptance_observation_invalid")
    return _result(
        host_family=host_family,
        launch_route=launch_route,
        gesture=gesture,
        nonempty_line_received=nonempty,
        exact_synthetic_line_received=exact,
        echo_observed=echo_observed,
        korean_rendered_without_question_marks=korean_ok,
        receipt_status_observed=receipt_observed,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "실제 Windows 호스트에서 합성 문자열 붙여넣기를 사람이 확인합니다. "
            "실제 자격증명, Notion 요청, 자격증명 저장소를 사용하지 않습니다."
        )
    )
    parser.add_argument("--host-family", choices=HOST_FAMILIES, required=True)
    parser.add_argument("--launch-route", choices=LAUNCH_ROUTES, required=True)
    parser.add_argument("--gesture", choices=GESTURES, required=True)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if os.name != "nt":
        print(
            json.dumps(
                {
                    "ok": False,
                    "schema_version": SCHEMA_VERSION,
                    "actual_host_acceptance_status": "not_performed",
                    "reason_code": "windows_host_required",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(
            json.dumps(
                {
                    "ok": False,
                    "schema_version": SCHEMA_VERSION,
                    "actual_host_acceptance_status": "not_performed",
                    "reason_code": "interactive_terminal_required",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2

    try:
        result = run_manual_acceptance(
            host_family=args.host_family,
            launch_route=args.launch_route,
            gesture=args.gesture,
            input_stream=sys.stdin,
            output_stream=sys.stdout,
            prompt_runner=_run_prompt_in_spawned_worker,
        )
    except Exception:
        result = {
            "ok": False,
            "schema_version": SCHEMA_VERSION,
            "host_family": args.host_family,
            "launch_route": args.launch_route,
            "gesture": args.gesture,
            "actual_host_acceptance_status": "failed",
            "reason_code": "manual_acceptance_failed",
            "product_clipboard_read_performed": False,
            "credential_store_write_performed": False,
            "provider_request_performed": False,
            "result_contains_input_value": False,
        }

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print("PASS" if result.get("ok") is True else "FAIL")
        print(f"host_family: {args.host_family}")
        print(f"launch_route: {args.launch_route}")
        print(f"gesture: {args.gesture}")
        print(f"status: {result.get('actual_host_acceptance_status')}")
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
