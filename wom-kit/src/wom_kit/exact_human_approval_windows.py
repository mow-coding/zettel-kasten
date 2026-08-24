"""Native Windows confirmation for one exact, content-free write plan.

This module establishes *interactive intent*, not human identity.  The live
boundary is one standard Windows task dialog.  Its primary surface asks one
human decision in ordinary language.  Machine-owned SHA-256 bindings and
warning/review codes remain available only through progressive disclosure;
private archive paths, source text, facet values, and secrets are never
accepted by the API.

The dialog alone is not write authority.  A caller must combine an approved
decision with the authenticated, one-use receipt/claim boundary in
``exact_human_approval`` before the first write.  Tests inject a fake native
boundary and never open a real window.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


TASK_DIALOG_TITLE = "WOM · 실행 확인"
SYNTHETIC_MAIN_INSTRUCTION = "합성 UI 테스트 · 실제 쓰기 권한이 아닙니다"
ADVANCED_DETAILS_COLLAPSED_TEXT = "기술 세부정보 보기"
ADVANCED_DETAILS_EXPANDED_TEXT = "기술 세부정보 숨기기"
SAFE_CANCEL_FOOTER = "취소하면 아무 변경도 하지 않습니다."
CURRENT_INTERACTIVE_INTENT_MECHANISM = (
    "windows_task_dialog_explicit_action_button"
)
LEGACY_INTERACTIVE_INTENT_MECHANISMS = frozenset(
    {"windows_task_dialog_checkbox_and_button"}
)

APPROVE_BUTTON_ID = 1001
IDCANCEL = 2

TDF_ALLOW_DIALOG_CANCELLATION = 0x0008
TDF_POSITION_RELATIVE_TO_WINDOW = 0x1000
TDF_SIZE_TO_CONTENT = 0x01000000
TDCBF_CANCEL_BUTTON = 0x0008

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_REVIEWER_CLAIM_RE = re.compile(
    r"^(?:person|human):[A-Za-z0-9][A-Za-z0-9._-]{0,95}$"
)
_MAX_WARNING_ITEMS = 256
_MAX_WARNING_BYTES = 256 * 1024


class ExactHumanApprovalIntent(Enum):
    """Strictly separate live authority from a harmless UI acceptance run."""

    live_write = "live_write"
    synthetic_acceptance = "synthetic_acceptance"


class ExactHumanApprovalOperation(Enum):
    """Initial v0.4 high-impact operations that require local intent."""

    create_draft = "create_draft"
    promote_zet = "promote_zet"
    mint_zet = "mint_zet"
    zettel_edge = "zettel_edge"
    zettel_objet_link = "zettel_objet_link"
    retire_draft = "retire_draft"
    warning_override = "warning_override"
    source_fidelity_session_evidence = "source_fidelity_session_evidence"
    human_artifact_lifecycle = "human_artifact_lifecycle"
    duplicate_object_reconcile = "duplicate_object_reconcile"
    integrity_repair = "integrity_repair"
    project_version_update = "project_version_update"
    git_backup = "git_backup"
    notion_property_backfill = "notion_property_backfill"
    notion_property_backfill_revert = "notion_property_backfill_revert"


def exact_human_approval_warning_codes(
    warnings: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    """Bind the exact warning set without reflecting warning text into UI.

    Warning prose may contain private archive context and is therefore never
    copied into the native dialog or durable public projection.  A
    deterministic 208-bit digest code still makes any warning-set change an
    approval-context change.  Order and duplicates are intentionally ignored:
    the human reviews the set of active warnings, not their presentation.
    """

    if type(warnings) not in {tuple, list} or len(warnings) > _MAX_WARNING_ITEMS:
        raise _fail("exact_human_approval_context_invalid")
    if any(type(item) is not str for item in warnings):
        raise _fail("exact_human_approval_context_invalid")
    normalized = sorted(set(warnings))
    if not normalized:
        return ()
    try:
        raw = json.dumps(
            normalized,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise _fail("exact_human_approval_context_invalid") from None
    if len(raw) > _MAX_WARNING_BYTES:
        raise _fail("exact_human_approval_context_invalid")
    digest = hashlib.sha256(raw).hexdigest()
    return ("warning_set_" + digest[:52],)


_OPERATION_LABELS = {
    ExactHumanApprovalOperation.create_draft: "AI 초안 생성",
    ExactHumanApprovalOperation.promote_zet: "제텔 승격",
    ExactHumanApprovalOperation.mint_zet: "제텔 발행",
    ExactHumanApprovalOperation.zettel_edge: "제텔 연결 생성",
    ExactHumanApprovalOperation.zettel_objet_link: "제텔-오브제 연결 생성",
    ExactHumanApprovalOperation.retire_draft: "초안 폐기",
    ExactHumanApprovalOperation.warning_override: "경고 예외 적용",
    ExactHumanApprovalOperation.source_fidelity_session_evidence: "세션 근거 보존",
    ExactHumanApprovalOperation.human_artifact_lifecycle: "사람 작업물 수명주기 변경",
    ExactHumanApprovalOperation.duplicate_object_reconcile: "중복 객체 정리",
    ExactHumanApprovalOperation.integrity_repair: "무결성 보충 또는 철회",
    ExactHumanApprovalOperation.project_version_update: "프로젝트 WOM-kit 버전 갱신",
    ExactHumanApprovalOperation.git_backup: "Git 원격 백업",
    ExactHumanApprovalOperation.notion_property_backfill: "Notion 원본 속성 복구",
    ExactHumanApprovalOperation.notion_property_backfill_revert: "Notion 원본 속성 복구 철회",
}

_OPERATION_QUESTIONS = {
    ExactHumanApprovalOperation.create_draft: "AI 초안을 만들까요?",
    ExactHumanApprovalOperation.promote_zet: "이 초안을 제텔로 승격할까요?",
    ExactHumanApprovalOperation.mint_zet: "이 제텔을 정본으로 발행할까요?",
    ExactHumanApprovalOperation.zettel_edge: "이 제텔 연결을 만들까요?",
    ExactHumanApprovalOperation.zettel_objet_link: "이 제텔과 오브제를 연결할까요?",
    ExactHumanApprovalOperation.retire_draft: "이 초안을 폐기할까요?",
    ExactHumanApprovalOperation.warning_override: "경고를 확인하고 계속할까요?",
    ExactHumanApprovalOperation.source_fidelity_session_evidence: (
        "이 세션 근거를 보존할까요?"
    ),
    ExactHumanApprovalOperation.human_artifact_lifecycle: (
        "이 사람 작업물의 상태를 변경할까요?"
    ),
    ExactHumanApprovalOperation.duplicate_object_reconcile: (
        "검증된 중복 객체 정리를 실행할까요?"
    ),
    ExactHumanApprovalOperation.integrity_repair: (
        "검증된 무결성 복구를 실행할까요?"
    ),
    ExactHumanApprovalOperation.project_version_update: (
        "현재 프로젝트의 WOM 버전을 업데이트할까요?"
    ),
    ExactHumanApprovalOperation.git_backup: (
        "현재 아카이브 변경을 원격 Git에 백업할까요?"
    ),
    ExactHumanApprovalOperation.notion_property_backfill: (
        "검증된 Notion 원본 속성 복구를 실행할까요?"
    ),
    ExactHumanApprovalOperation.notion_property_backfill_revert: (
        "Notion 원본 속성 복구를 되돌릴까요?"
    ),
}

_OPERATION_SUMMARIES = {
    ExactHumanApprovalOperation.create_draft: (
        "새 초안을 만들며 기존 정본은 변경하지 않습니다."
    ),
    ExactHumanApprovalOperation.promote_zet: (
        "검증된 초안을 제텔 단계로 옮깁니다."
    ),
    ExactHumanApprovalOperation.mint_zet: (
        "검증된 제텔을 정본으로 발행하고 영수증을 남깁니다."
    ),
    ExactHumanApprovalOperation.zettel_edge: (
        "검증된 두 제텔 사이에 선택한 관계만 추가합니다."
    ),
    ExactHumanApprovalOperation.zettel_objet_link: (
        "검증된 제텔과 오브제 사이에 선택한 연결만 추가합니다."
    ),
    ExactHumanApprovalOperation.retire_draft: (
        "검증된 초안만 폐기하며 정본은 변경하지 않습니다."
    ),
    ExactHumanApprovalOperation.warning_override: (
        "WOM이 표시한 경고가 있는 작업을 예외적으로 계속합니다."
    ),
    ExactHumanApprovalOperation.source_fidelity_session_evidence: (
        "현재 세션의 검증된 근거만 보존합니다."
    ),
    ExactHumanApprovalOperation.human_artifact_lifecycle: (
        "검증된 사람 작업물의 선택된 상태만 변경합니다."
    ),
    ExactHumanApprovalOperation.duplicate_object_reconcile: (
        "확실한 근거로 묶인 중복 객체만 정리하고 불명확한 항목은 건드리지 않습니다."
    ),
    ExactHumanApprovalOperation.integrity_repair: (
        "WOM이 검증한 대상과 필드만 복구합니다."
    ),
    ExactHumanApprovalOperation.project_version_update: (
        "프로젝트 전용 런타임과 버전 핀만 바꾸며 컴퓨터 공용 PATH 설치는 건드리지 않습니다."
    ),
    ExactHumanApprovalOperation.git_backup: (
        "검토된 변경만 커밋하고 force push 없이 원격 상태를 다시 검증합니다."
    ),
    ExactHumanApprovalOperation.notion_property_backfill: (
        "확실히 매핑된 제텔의 source_properties 필드만 복구합니다. "
        "매핑되지 않거나 검토가 필요한 항목은 변경하지 않습니다."
    ),
    ExactHumanApprovalOperation.notion_property_backfill_revert: (
        "이 복구가 추가한 source_properties 필드만 되돌립니다. "
        "제목과 본문 등 다른 필드는 변경하지 않습니다."
    ),
}

_OPERATION_APPROVE_BUTTONS = {
    ExactHumanApprovalOperation.create_draft: "초안 만들기",
    ExactHumanApprovalOperation.promote_zet: "제텔로 승격",
    ExactHumanApprovalOperation.mint_zet: "정본 발행",
    ExactHumanApprovalOperation.zettel_edge: "관계 만들기",
    ExactHumanApprovalOperation.zettel_objet_link: "연결 만들기",
    ExactHumanApprovalOperation.retire_draft: "초안 폐기",
    ExactHumanApprovalOperation.warning_override: "계속 실행",
    ExactHumanApprovalOperation.source_fidelity_session_evidence: "근거 보존",
    ExactHumanApprovalOperation.human_artifact_lifecycle: "상태 변경",
    ExactHumanApprovalOperation.duplicate_object_reconcile: "중복 정리",
    ExactHumanApprovalOperation.integrity_repair: "복구 실행",
    ExactHumanApprovalOperation.project_version_update: "업데이트 실행",
    ExactHumanApprovalOperation.git_backup: "백업 실행",
    ExactHumanApprovalOperation.notion_property_backfill: "복구 실행",
    ExactHumanApprovalOperation.notion_property_backfill_revert: "복구 되돌리기",
}


class ExactHumanApprovalWindowsError(RuntimeError):
    """Fixed-code error that never retains native text or private values."""

    _CODES = {
        "exact_human_approval_context_invalid",
        "exact_human_approval_platform_required",
        "exact_human_approval_activation_context_required",
        "exact_human_approval_native_load_failed",
        "exact_human_approval_native_call_failed",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "exact_human_approval_native_call_failed"
        super().__init__(self.code)

    def __repr__(self) -> str:
        return f"ExactHumanApprovalWindowsError({self.code!r})"


def _fail(code: str) -> ExactHumanApprovalWindowsError:
    return ExactHumanApprovalWindowsError(code)


def _validate_codes(value: tuple[str, ...]) -> tuple[str, ...]:
    if type(value) is not tuple or len(value) > 32:
        raise _fail("exact_human_approval_context_invalid")
    if any(type(item) is not str or _CODE_RE.fullmatch(item) is None for item in value):
        raise _fail("exact_human_approval_context_invalid")
    if tuple(sorted(set(value))) != value:
        raise _fail("exact_human_approval_context_invalid")
    return value


@dataclass(frozen=True)
class ExactHumanApprovalContext:
    """Content-free bindings kept behind one human decision surface."""

    operation: ExactHumanApprovalOperation
    archive_identity_sha256: str
    plan_sha256: str
    target_binding_sha256: str
    reviewer_claim: str
    review_binding_codes: tuple[str, ...]
    warning_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.operation) is not ExactHumanApprovalOperation:
            raise _fail("exact_human_approval_context_invalid")
        for value in (
            self.archive_identity_sha256,
            self.plan_sha256,
            self.target_binding_sha256,
        ):
            if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
                raise _fail("exact_human_approval_context_invalid")
        if (
            type(self.reviewer_claim) is not str
            or _REVIEWER_CLAIM_RE.fullmatch(self.reviewer_claim) is None
        ):
            raise _fail("exact_human_approval_context_invalid")
        if not self.review_binding_codes:
            raise _fail("exact_human_approval_context_invalid")
        _validate_codes(self.review_binding_codes)
        _validate_codes(self.warning_codes)

    def __repr__(self) -> str:
        return (
            "<ExactHumanApprovalContext operation="
            f"{self.operation.value} bindings=sha256 codes=content-free>"
        )


@dataclass(frozen=True)
class _ExactHumanApprovalDecision:
    """Interactive result; only ``approved`` live decisions may be claimed."""

    approved: bool
    synthetic_acknowledged: bool
    reason_code: str
    plan_sha256: str
    target_binding_sha256: str

    def __repr__(self) -> str:
        return (
            "<_ExactHumanApprovalDecision approved="
            f"{self.approved} synthetic={self.synthetic_acknowledged} bindings=sha256>"
        )


class _ExactHumanApprovalNative(Protocol):
    """Small fakeable boundary around ``TaskDialogIndirect``."""

    def show(
        self,
        *,
        title: str,
        main_instruction: str,
        content: str,
        expanded_information: str,
        expanded_control_text: str,
        collapsed_control_text: str,
        footer: str,
        approve_button_text: str,
    ) -> tuple[int, bool]: ...


class _TASKDIALOG_BUTTON(ctypes.Structure):
    _fields_ = [("nButtonID", ctypes.c_int), ("pszButtonText", wintypes.LPCWSTR)]


class _TASKDIALOGCONFIG(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("hwndParent", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("dwFlags", wintypes.UINT),
        ("dwCommonButtons", wintypes.UINT),
        ("pszWindowTitle", wintypes.LPCWSTR),
        ("pszMainIcon", ctypes.c_void_p),
        ("pszMainInstruction", wintypes.LPCWSTR),
        ("pszContent", wintypes.LPCWSTR),
        ("cButtons", wintypes.UINT),
        ("pButtons", ctypes.POINTER(_TASKDIALOG_BUTTON)),
        ("nDefaultButton", ctypes.c_int),
        ("cRadioButtons", wintypes.UINT),
        ("pRadioButtons", ctypes.POINTER(_TASKDIALOG_BUTTON)),
        ("nDefaultRadioButton", ctypes.c_int),
        ("pszVerificationText", wintypes.LPCWSTR),
        ("pszExpandedInformation", wintypes.LPCWSTR),
        ("pszExpandedControlText", wintypes.LPCWSTR),
        ("pszCollapsedControlText", wintypes.LPCWSTR),
        ("pszFooterIcon", ctypes.c_void_p),
        ("pszFooter", wintypes.LPCWSTR),
        ("pfCallback", ctypes.c_void_p),
        ("lpCallbackData", ctypes.c_ssize_t),
        ("cxWidth", wintypes.UINT),
    ]


class _DLLVERSIONINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("dwMajorVersion", wintypes.DWORD),
        ("dwMinorVersion", wintypes.DWORD),
        ("dwBuildNumber", wintypes.DWORD),
        ("dwPlatformID", wintypes.DWORD),
    ]


def _require_comctl32_v6(comctl32: object) -> None:
    """Verify the loaded common-controls assembly before showing live UI."""

    try:
        dll_get_version = getattr(comctl32, "DllGetVersion")
        dll_get_version.argtypes = [ctypes.POINTER(_DLLVERSIONINFO)]
        dll_get_version.restype = ctypes.c_long
        version = _DLLVERSIONINFO()
        version.cbSize = ctypes.sizeof(_DLLVERSIONINFO)
        result = int(dll_get_version(ctypes.byref(version)))
    except BaseException:
        raise _fail("exact_human_approval_activation_context_required") from None
    if result < 0 or int(version.dwMajorVersion) < 6:
        raise _fail("exact_human_approval_activation_context_required")


class _CtypesTaskDialogNative:
    """Pointer-size-correct Unicode task-dialog implementation."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise _fail("exact_human_approval_platform_required")
        loader = getattr(ctypes, "WinDLL", None)
        if loader is None:
            raise _fail("exact_human_approval_native_load_failed")
        try:
            self._comctl32 = loader("comctl32", use_last_error=True)
            self._user32 = loader("user32", use_last_error=True)
            _require_comctl32_v6(self._comctl32)
            self._task_dialog = self._comctl32.TaskDialogIndirect
            self._task_dialog.argtypes = [
                ctypes.POINTER(_TASKDIALOGCONFIG),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(wintypes.BOOL),
            ]
            self._task_dialog.restype = ctypes.c_long
            self._get_foreground_window = self._user32.GetForegroundWindow
            self._get_foreground_window.argtypes = []
            self._get_foreground_window.restype = wintypes.HWND
        except ExactHumanApprovalWindowsError:
            raise
        except BaseException:
            raise _fail("exact_human_approval_native_load_failed") from None

    def show(
        self,
        *,
        title: str,
        main_instruction: str,
        content: str,
        expanded_information: str,
        expanded_control_text: str,
        collapsed_control_text: str,
        footer: str,
        approve_button_text: str,
    ) -> tuple[int, bool]:
        buttons = (_TASKDIALOG_BUTTON * 1)(
            _TASKDIALOG_BUTTON(APPROVE_BUTTON_ID, approve_button_text)
        )
        button = ctypes.c_int(0)
        radio = ctypes.c_int(0)
        verified = wintypes.BOOL(0)
        try:
            owner = self._get_foreground_window()
            flags = TDF_ALLOW_DIALOG_CANCELLATION | TDF_SIZE_TO_CONTENT
            if owner:
                flags |= TDF_POSITION_RELATIVE_TO_WINDOW
            config = _TASKDIALOGCONFIG(
                cbSize=ctypes.sizeof(_TASKDIALOGCONFIG),
                hwndParent=owner,
                hInstance=None,
                dwFlags=flags,
                dwCommonButtons=TDCBF_CANCEL_BUTTON,
                pszWindowTitle=title,
                pszMainIcon=None,
                pszMainInstruction=main_instruction,
                pszContent=content,
                cButtons=1,
                pButtons=buttons,
                nDefaultButton=0,
                cRadioButtons=0,
                pRadioButtons=None,
                nDefaultRadioButton=0,
                pszVerificationText=None,
                pszExpandedInformation=expanded_information,
                pszExpandedControlText=expanded_control_text,
                pszCollapsedControlText=collapsed_control_text,
                pszFooterIcon=None,
                pszFooter=footer,
                pfCallback=None,
                lpCallbackData=0,
                cxWidth=0,
            )
            result = int(
                self._task_dialog(
                    ctypes.byref(config),
                    ctypes.byref(button),
                    ctypes.byref(radio),
                    ctypes.byref(verified),
                )
            )
        except BaseException:
            raise _fail("exact_human_approval_native_call_failed") from None
        if result < 0:
            raise _fail("exact_human_approval_native_call_failed")
        return int(button.value), bool(verified.value)


def _dialog_content(context: ExactHumanApprovalContext) -> str:
    return (
        "WOM이 대상, 현재 상태, 적용할 변경을 자동으로 검증했습니다.\n\n"
        f"{_OPERATION_SUMMARIES[context.operation]}\n\n"
        "사람이 결정할 일은 이 작업을 지금 실행할지 여부뿐입니다. "
        "대상이나 상태가 달라지면 WOM이 쓰기 전에 자동으로 중단합니다."
    )


def _dialog_advanced_information(context: ExactHumanApprovalContext) -> str:
    review = ", ".join(context.review_binding_codes)
    warnings = ", ".join(context.warning_codes) if context.warning_codes else "없음"
    return (
        "아래 값은 WOM이 자동 대조하는 기계 검증 근거입니다. "
        "사람이 직접 비교하거나 계산할 필요가 없습니다.\n\n"
        f"작업: {_OPERATION_LABELS[context.operation]}\n"
        f"아카이브 식별자: {context.archive_identity_sha256}\n"
        f"계획: {context.plan_sha256}\n"
        f"대상 결합: {context.target_binding_sha256}\n"
        f"검토자 표기: {context.reviewer_claim}\n"
        f"기계 검증 항목: {review}\n"
        f"기계 경고 항목: {warnings}\n\n"
        "이 식별자는 승인된 계획의 첫 실행 1회에만 결속됩니다."
    )


def _request_exact_human_approval_core(
    context: ExactHumanApprovalContext,
    *,
    intent: ExactHumanApprovalIntent,
    native: _ExactHumanApprovalNative | None = None,
) -> _ExactHumanApprovalDecision:
    """Internal fakeable review core; production callers never inject native."""

    if type(context) is not ExactHumanApprovalContext:
        raise _fail("exact_human_approval_context_invalid")
    if type(intent) is not ExactHumanApprovalIntent:
        raise _fail("exact_human_approval_context_invalid")
    selected = native if native is not None else _CtypesTaskDialogNative()
    instruction = (
        _OPERATION_QUESTIONS[context.operation]
        if intent is ExactHumanApprovalIntent.live_write
        else SYNTHETIC_MAIN_INSTRUCTION
    )
    try:
        button, checked = selected.show(
            title=TASK_DIALOG_TITLE,
            main_instruction=instruction,
            content=_dialog_content(context),
            expanded_information=_dialog_advanced_information(context),
            expanded_control_text=ADVANCED_DETAILS_EXPANDED_TEXT,
            collapsed_control_text=ADVANCED_DETAILS_COLLAPSED_TEXT,
            footer=SAFE_CANCEL_FOOTER,
            approve_button_text=_OPERATION_APPROVE_BUTTONS[context.operation],
        )
    except ExactHumanApprovalWindowsError:
        raise
    except BaseException:
        raise _fail("exact_human_approval_native_call_failed") from None

    # The explicit action button is the human decision.  Task-dialog
    # verification checkboxes are for optional secondary choices (for example,
    # "do not show again"), not a second oath that machine hashes were read.
    # ``checked`` is intentionally ignored for compatibility with the native
    # return shape and older injected test facades.
    acknowledged = button == APPROVE_BUTTON_ID
    if intent is ExactHumanApprovalIntent.synthetic_acceptance:
        return _ExactHumanApprovalDecision(
            approved=False,
            synthetic_acknowledged=acknowledged,
            reason_code=(
                "exact_human_approval_synthetic_acknowledged"
                if acknowledged
                else "exact_human_approval_cancelled"
            ),
            plan_sha256=context.plan_sha256,
            target_binding_sha256=context.target_binding_sha256,
        )
    return _ExactHumanApprovalDecision(
        approved=acknowledged,
        synthetic_acknowledged=False,
        reason_code=(
            "exact_human_approval_approved"
            if acknowledged
            else "exact_human_approval_cancelled"
        ),
        plan_sha256=context.plan_sha256,
        target_binding_sha256=context.target_binding_sha256,
    )


def _request_exact_human_approval(
    context: ExactHumanApprovalContext,
    *,
    intent: ExactHumanApprovalIntent,
) -> _ExactHumanApprovalDecision:
    """Run the production native boundary without an injectable facade."""

    return _request_exact_human_approval_core(
        context,
        intent=intent,
        native=None,
    )


__all__ = [
    "APPROVE_BUTTON_ID",
    "ExactHumanApprovalContext",
    "ExactHumanApprovalIntent",
    "ExactHumanApprovalOperation",
    "ExactHumanApprovalWindowsError",
]
