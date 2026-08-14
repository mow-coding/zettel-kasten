from __future__ import annotations

import argparse
import hmac
import json
import multiprocessing
import os
import platform
import signal
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from wom_kit.credential_secure_intake import HumanSecretInputResult  # noqa: E402
from wom_kit.credential_secure_intake_windows import (  # noqa: E402
    CredentialPopupPromptContext,
)
from wom_kit.credential_popup_windows import (  # noqa: E402
    CredentialPopupInputIntent,
    prompt_secret_in_native_popup,
)
from wom_kit.credential_workflows import (  # noqa: E402
    _capture_credential_worker_start_signal_lease,
    _close_credential_worker_send_connection,
    _detach_spawned_popup_child_console,
    _install_credential_worker_start_signal_lease,
    _join_started_credential_worker,
    _restore_credential_worker_start_signal_lease,
)


SCHEMA_VERSION = "wom-kit/windows-credential-popup-acceptance/v0.1"
SYNTHETIC_LINE = "WOM-INPUT-ACCEPTANCE-0319"
HOST_FAMILIES = (
    "codex_desktop",
    "windows_terminal",
    "console_host",
    "conpty_parent",
)
HOST_LAUNCH_ROUTES = {
    "codex_desktop": "codex_desktop_native_popup",
    "windows_terminal": "windows_terminal_native_popup",
    "console_host": "console_host_native_popup",
    "conpty_parent": "conpty_parent_native_popup",
}
LAUNCH_ROUTES = tuple(HOST_LAUNCH_ROUTES.values())
GESTURES = (
    "direct_keyboard_typing",
    "ctrl_v",
    "shift_insert",
    "right_click_menu_paste",
)
GESTURE_LABELS = {
    "direct_keyboard_typing": "키보드 직접 입력",
    "ctrl_v": "Ctrl+V 붙여넣기",
    "shift_insert": "Shift+Insert 붙여넣기",
    "right_click_menu_paste": "입력란 오른쪽 메뉴의 붙여넣기",
}

QuestionFunction = Callable[[str], bool]
PromptEvidence = tuple[bool, bool, bool, bool, bool]
PromptRunner = Callable[[], PromptEvidence]

_ACK = {"worker_transport_status": "popup_child_detached"}
_FINAL_KEYS = {
    "worker_transport_status",
    "credential_input_received",
    "complete_line_received",
    "cancelled",
    "nonempty_line_received",
    "exact_synthetic_line_received",
}


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


def _classify_machine_input(
    *,
    credential_input_received: bool,
    complete_line_received: bool,
    nonempty_line_received: bool,
    exact_synthetic_line_received: bool,
) -> str:
    evidence = (
        credential_input_received,
        complete_line_received,
        nonempty_line_received,
        exact_synthetic_line_received,
    )
    if any(type(value) is not bool for value in evidence):
        raise RuntimeError("manual_acceptance_observation_invalid")
    classifications = {
        (False, False, False, False): "no_input",
        (True, False, False, False): "partial_input_cancelled",
        (True, True, False, False): "empty_confirmation",
        (True, True, True, False): "nonempty_input_mismatch",
        (True, True, True, True): "exact_synthetic_input_received",
    }
    try:
        return classifications[evidence]
    except KeyError as error:
        raise RuntimeError("manual_acceptance_worker_result_invalid") from error


def _validate_prompt_evidence(value: Any) -> PromptEvidence:
    if (
        type(value) is not tuple
        or len(value) != 5
        or any(type(item) is not bool for item in value)
    ):
        raise RuntimeError("manual_acceptance_worker_result_invalid")
    input_received, complete, cancelled, nonempty, exact = value
    _classify_machine_input(
        credential_input_received=input_received,
        complete_line_received=complete,
        nonempty_line_received=nonempty,
        exact_synthetic_line_received=exact,
    )
    if cancelled and complete:
        raise RuntimeError("manual_acceptance_worker_result_invalid")
    if not cancelled and not complete:
        raise RuntimeError("manual_acceptance_worker_result_invalid")
    return value


def _result(
    *,
    host_family: str,
    launch_route: str,
    gesture: str,
    synthetic_only_acknowledged: bool,
    popup_observed: bool,
    synthetic_test_copy_observed: bool,
    human_physical_gesture_attested: bool,
    credential_input_received: bool,
    complete_line_received: bool,
    cancelled: bool,
    nonempty_line_received: bool,
    exact_synthetic_line_received: bool,
    value_mask_or_length_observed: bool,
    confirm_gate_observed: bool,
    popup_closed_after_confirmation: bool,
    korean_rendered_legibly: bool,
) -> dict[str, Any]:
    observations = (
        synthetic_only_acknowledged,
        popup_observed,
        synthetic_test_copy_observed,
        human_physical_gesture_attested,
        credential_input_received,
        complete_line_received,
        cancelled,
        nonempty_line_received,
        exact_synthetic_line_received,
        value_mask_or_length_observed,
        confirm_gate_observed,
        popup_closed_after_confirmation,
        korean_rendered_legibly,
    )
    if any(type(value) is not bool for value in observations):
        raise RuntimeError("manual_acceptance_observation_invalid")
    machine_input_classification = _classify_machine_input(
        credential_input_received=credential_input_received,
        complete_line_received=complete_line_received,
        nonempty_line_received=nonempty_line_received,
        exact_synthetic_line_received=exact_synthetic_line_received,
    )
    passed = all(
        (
            synthetic_only_acknowledged,
            popup_observed,
            synthetic_test_copy_observed,
            human_physical_gesture_attested,
            credential_input_received,
            complete_line_received,
            not cancelled,
            nonempty_line_received,
            exact_synthetic_line_received,
            not value_mask_or_length_observed,
            confirm_gate_observed,
            popup_closed_after_confirmation,
            korean_rendered_legibly,
        )
    )
    return {
        "ok": passed,
        "schema_version": SCHEMA_VERSION,
        "test_intent": "synthetic_popup_acceptance_only",
        "host_family": host_family,
        "os_build": platform.version(),
        "launch_route": launch_route,
        "gesture": gesture,
        "actual_host_acceptance_status": "passed" if passed else "failed",
        "synthetic_only_acknowledged": synthetic_only_acknowledged,
        "popup_observed": popup_observed,
        "synthetic_test_copy_observed": synthetic_test_copy_observed,
        "human_physical_gesture_attested": human_physical_gesture_attested,
        "credential_input_received": credential_input_received,
        "complete_line_received": complete_line_received,
        "cancelled": cancelled,
        "nonempty_line_received": nonempty_line_received,
        "exact_synthetic_line_received": exact_synthetic_line_received,
        "machine_input_classification": machine_input_classification,
        "value_mask_or_length_observed": value_mask_or_length_observed,
        "confirm_gate_observed": confirm_gate_observed,
        "popup_closed_after_confirmation": popup_closed_after_confirmation,
        "korean_rendered_legibly": korean_rendered_legibly,
        "actual_credential_registration_performed": False,
        "actual_pat_requested": False,
        "product_clipboard_read_performed": False,
        "credential_store_write_performed": False,
        "provider_request_performed": False,
        "result_contains_input_value": False,
    }


def _prompt_child(connection: Any) -> None:
    received: bytearray | None = None
    expected = bytearray(SYNTHETIC_LINE.encode("utf-8"))
    try:
        if _detach_spawned_popup_child_console() is not True:
            return
        connection.send(dict(_ACK))
        input_result = prompt_secret_in_native_popup(
            request_id="intake_manual_popup_acceptance_0319",
            input_intent=CredentialPopupInputIntent.synthetic_acceptance,
            context=CredentialPopupPromptContext(
                provider="notion",
                purpose="source_recovery",
                account_label="합성 입력 확인용 계정",
                workspace_label="합성 입력 확인용 작업공간",
                task_summary=(
                    f"합성 입력 테스트입니다. 고정 합성 문자열은 {SYNTHETIC_LINE} 입니다."
                ),
                connection_reason=(
                    "실제 PAT를 입력하지 말고 위 고정 합성 문자열 전체만 "
                    "지정한 방식으로 입력한 뒤 확인을 누르세요."
                ),
            ),
        )
        if not isinstance(input_result, HumanSecretInputResult):
            raise RuntimeError("manual_acceptance_worker_result_invalid")
        received = input_result.secret
        input_received = input_result.credential_input_received
        complete = input_result.complete_line_received
        cancelled = input_result.cancelled
        if any(type(value) is not bool for value in (input_received, complete, cancelled)):
            raise RuntimeError("manual_acceptance_worker_result_invalid")
        nonempty = isinstance(received, bytearray) and bool(received)
        exact = isinstance(received, bytearray) and hmac.compare_digest(received, expected)
        connection.send(
            {
                "worker_transport_status": "popup_result",
                "credential_input_received": input_received,
                "complete_line_received": complete,
                "cancelled": cancelled,
                "nonempty_line_received": nonempty,
                "exact_synthetic_line_received": exact,
            }
        )
    except BaseException:
        try:
            connection.send({"worker_transport_status": "popup_failed"})
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


def _drain_popup_worker_pipe(receiver: Any) -> list[Any]:
    """Drain fixed popup evidence through terminal EOF without interruption escape."""

    messages: list[Any] = []
    while True:
        try:
            messages.append(receiver.recv())
        except EOFError:
            return messages
        except BaseException:
            try:
                time.sleep(0.01)
            except BaseException:
                pass


def _run_prompt_in_spawned_worker() -> PromptEvidence:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_prompt_child, args=(sender,), daemon=False)
    messages: list[Any] = []
    start_lease: Any = None
    start_lease_restored = False
    start_invoked = False
    start_returned = False
    pipe_drained = False
    joined = False
    failed = False

    def restore_start_lease() -> None:
        nonlocal start_lease_restored
        if start_lease is not None and not start_lease_restored:
            _restore_credential_worker_start_signal_lease(
                start_lease,
                signal_getter=signal.getsignal,
                signal_setter=signal.signal,
            )
            start_lease_restored = True

    def drain_and_contain() -> None:
        nonlocal messages, pipe_drained, joined
        if not pipe_drained:
            _close_credential_worker_send_connection(sender)
            messages = _drain_popup_worker_pipe(receiver)
            pipe_drained = True
        if start_returned and not joined:
            _join_started_credential_worker(process)
            joined = True

    try:
        start_lease = _capture_credential_worker_start_signal_lease(
            signal_getter=signal.getsignal,
        )
        if start_lease is None:
            failed = True
        elif _install_credential_worker_start_signal_lease(
            start_lease,
            signal_getter=signal.getsignal,
            signal_setter=signal.signal,
        ):
            try:
                start_invoked = True
                process.start()
            except BaseException:
                # Windows child creation can precede Process' public start
                # proof. The fixed ACK/final/EOF pipe is the containment proof.
                pass
            else:
                start_returned = True
        else:
            failed = True
        restore_start_lease()
        if start_invoked:
            drain_and_contain()
    except BaseException:
        failed = True
        restore_start_lease()
        if start_invoked:
            drain_and_contain()
    finally:
        restore_start_lease()
        if start_invoked:
            drain_and_contain()
        else:
            _close_credential_worker_send_connection(sender)
        for connection in (receiver,):
            try:
                connection.close()
            except BaseException:
                failed = True
    if (
        failed
        or not start_invoked
        or not start_lease_restored
        or (start_returned and not joined)
        or (start_returned and process.is_alive())
        or (start_returned and process.exitcode != 0)
        or len(messages) != 2
        or type(messages[0]) is not dict
        or messages[0] != _ACK
        or type(messages[1]) is not dict
        or set(messages[1]) != _FINAL_KEYS
        or messages[1].get("worker_transport_status") != "popup_result"
    ):
        raise RuntimeError("manual_acceptance_worker_failed")
    return _validate_prompt_evidence(
        (
            messages[1]["credential_input_received"],
            messages[1]["complete_line_received"],
            messages[1]["cancelled"],
            messages[1]["nonempty_line_received"],
            messages[1]["exact_synthetic_line_received"],
        )
    )


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

    gesture_label = GESTURE_LABELS[gesture]
    output_stream.write(
        "Windows native popup 합성 입력 수동 확인입니다. 실제 자격증명 등록이 아닙니다.\n"
        "이 절차는 실제 PAT를 요구하지 않으며, 실제 PAT를 입력하면 안 됩니다.\n"
        "아래 공개 고정 합성 문자열만 사용하세요.\n\n"
        f"{SYNTHETIC_LINE}\n\n"
        f"검증 제스처: {gesture_label} ({gesture})\n"
        "확인 뒤 별도 native popup이 열립니다. popup 안에서도 합성 테스트임을 확인한 뒤\n"
        "고정 합성 문자열 전체만 입력하고 확인을 누르세요. 취소/X/Esc는 저장 없이 닫습니다.\n"
    )
    output_stream.flush()

    synthetic_only_acknowledged = question_function(
        "실제 PAT가 아니라 위 고정 합성 문자열만 입력하는 합성 테스트임을 확인했습니까?"
    )
    if synthetic_only_acknowledged is not True:
        raise RuntimeError("manual_acceptance_synthetic_only_not_acknowledged")

    prompt_result = _validate_prompt_evidence(prompt_runner())
    input_received, complete, cancelled, nonempty, exact = prompt_result

    popup_observed = question_function(
        "터미널 입력란이 아니라 별도 WOM native popup이 열렸습니까?"
    )
    synthetic_copy_observed = question_function(
        "popup이 실제 등록이 아닌 합성 입력 테스트이며 실제 PAT를 입력하지 말라고 명확히 표시했습니까?"
    )
    gesture_attested = question_function(
        "성공한 것처럼 보였는지와 관계없이, 고정 합성 문자열 전체를 "
        f"{gesture_label} 방식으로 입력하고 확인까지 실제로 눌렀습니까?"
    )
    value_or_length_observed = question_function(
        "입력한 글자, 점·별표 같은 mask, caret 이동, 개수 또는 길이를 알 수 있는 표시가 보였습니까?"
    )
    confirm_gate_observed = question_function(
        "빈 입력에서는 확인이 비활성화되고, 한 글자 이상 입력한 뒤에만 활성화됐습니까?"
    )
    popup_closed = question_function(
        "확인을 누른 뒤 popup이 정상적으로 닫혔습니까?"
    )
    korean_ok = question_function(
        "popup의 WOM 한국어가 겹침·잘림·깨진 물음표 없이 읽기 쉽게 표시됐습니까?"
    )
    if any(
        type(value) is not bool
        for value in (
            popup_observed,
            synthetic_copy_observed,
            gesture_attested,
            value_or_length_observed,
            confirm_gate_observed,
            popup_closed,
            korean_ok,
        )
    ):
        raise RuntimeError("manual_acceptance_observation_invalid")
    return _result(
        host_family=host_family,
        launch_route=launch_route,
        gesture=gesture,
        synthetic_only_acknowledged=synthetic_only_acknowledged,
        popup_observed=popup_observed,
        synthetic_test_copy_observed=synthetic_copy_observed,
        human_physical_gesture_attested=gesture_attested,
        credential_input_received=input_received,
        complete_line_received=complete,
        cancelled=cancelled,
        nonempty_line_received=nonempty,
        exact_synthetic_line_received=exact,
        value_mask_or_length_observed=value_or_length_observed,
        confirm_gate_observed=confirm_gate_observed,
        popup_closed_after_confirmation=popup_closed,
        korean_rendered_legibly=korean_ok,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "별도 Windows native popup에서 공개 합성 문자열 입력만 사람이 확인합니다. "
            "실제 PAT, 자격증명 등록, 저장소 쓰기, provider 요청은 하지 않습니다."
        )
    )
    parser.add_argument("--host-family", choices=HOST_FAMILIES, required=True)
    parser.add_argument("--launch-route", choices=LAUNCH_ROUTES, required=True)
    parser.add_argument("--gesture", choices=GESTURES, required=True)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser


def _not_performed(reason_code: str) -> dict[str, Any]:
    return {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "test_intent": "synthetic_popup_acceptance_only",
        "actual_host_acceptance_status": "not_performed",
        "reason_code": reason_code,
        "actual_credential_registration_performed": False,
        "actual_pat_requested": False,
        "credential_store_write_performed": False,
        "provider_request_performed": False,
        "result_contains_input_value": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if os.name != "nt":
        print(json.dumps(_not_performed("windows_host_required"), ensure_ascii=False, sort_keys=True))
        return 2
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(json.dumps(_not_performed("interactive_terminal_required"), ensure_ascii=False, sort_keys=True))
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
            **_not_performed("manual_acceptance_failed"),
            "host_family": args.host_family,
            "launch_route": args.launch_route,
            "gesture": args.gesture,
            "actual_host_acceptance_status": "failed",
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
