"""Native Windows confirmation for one exact, content-free write plan.

This module establishes *interactive intent*, not human identity.  The live
boundary is one standard Windows task dialog.  It displays only fixed labels,
SHA-256 bindings, and machine-owned warning/review codes; private archive
paths, source text, facet values, and secrets are never accepted by the API.

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


TASK_DIALOG_TITLE = "WOM · 정확한 사람 검토"
LIVE_MAIN_INSTRUCTION = "실제 쓰기 1회를 검토하고 승인합니다"
SYNTHETIC_MAIN_INSTRUCTION = "합성 UI 테스트 · 실제 쓰기 권한이 아닙니다"
VERIFICATION_TEXT = "위 계획 식별자와 검토 항목을 확인했습니다."
APPROVE_BUTTON_TEXT = "이 계획을 1회 승인"
CANCEL_BUTTON_TEXT = "취소"

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
    """Content-free bindings shown to the person before one write attempt."""

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
        verification_text: str,
        approve_button_text: str,
        cancel_button_text: str,
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
        verification_text: str,
        approve_button_text: str,
        cancel_button_text: str,
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
                pszVerificationText=verification_text,
                pszExpandedInformation=None,
                pszExpandedControlText=None,
                pszCollapsedControlText=None,
                pszFooterIcon=None,
                pszFooter=cancel_button_text,
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
    review = ", ".join(context.review_binding_codes)
    warnings = ", ".join(context.warning_codes) if context.warning_codes else "없음"
    return (
        f"작업: {_OPERATION_LABELS[context.operation]}\n\n"
        f"아카이브 식별자: {context.archive_identity_sha256}\n"
        f"계획: {context.plan_sha256}\n"
        f"대상 결합: {context.target_binding_sha256}\n\n"
        f"검토자 표기: {context.reviewer_claim}\n"
        f"필수 검토 항목: {review}\n"
        f"경고 항목: {warnings}\n\n"
        "승인은 위 해시로 결합된 계획의 첫 실행 1회에만 사용됩니다. "
        "실패하거나 중단되어도 자동 재사용되지 않습니다."
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
        LIVE_MAIN_INSTRUCTION
        if intent is ExactHumanApprovalIntent.live_write
        else SYNTHETIC_MAIN_INSTRUCTION
    )
    try:
        button, checked = selected.show(
            title=TASK_DIALOG_TITLE,
            main_instruction=instruction,
            content=_dialog_content(context),
            verification_text=VERIFICATION_TEXT,
            approve_button_text=APPROVE_BUTTON_TEXT,
            cancel_button_text=CANCEL_BUTTON_TEXT,
        )
    except ExactHumanApprovalWindowsError:
        raise
    except BaseException:
        raise _fail("exact_human_approval_native_call_failed") from None

    acknowledged = button == APPROVE_BUTTON_ID and checked is True
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
