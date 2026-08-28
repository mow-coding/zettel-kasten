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
import tempfile
import unicodedata
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Protocol


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

_COMMON_CONTROLS_V6_MANIFEST = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity
      version="1.0.0.0"
      processorArchitecture="*"
      name="WOM.ExactHumanApproval"
      type="win32" />
  <dependency>
    <dependentAssembly>
      <assemblyIdentity
          type="win32"
          name="Microsoft.Windows.Common-Controls"
          version="6.0.0.0"
          processorArchitecture="*"
          publicKeyToken="6595b64144ccf1df"
          language="*" />
    </dependentAssembly>
  </dependency>
</assembly>
"""

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_REVIEWER_CLAIM_RE = re.compile(
    r"^(?:person|human):[A-Za-z0-9][A-Za-z0-9._-]{0,95}$"
)
_MAX_WARNING_ITEMS = 256
_MAX_WARNING_BYTES = 256 * 1024
_TARGET_PREVIEW_KINDS = frozenset({"draft", "zet", "zet_edge", "zet_objet"})
_MAX_TARGET_PREVIEW_CHARACTERS = 240
_MAX_TARGET_PREVIEW_UTF8_BYTES = 1024


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
    zettel_edge_revert = "zettel_edge_revert"
    zettel_objet_link = "zettel_objet_link"
    objet_capture = "objet_capture"
    objet_capture_batch = "objet_capture_batch"
    objet_capture_selection_record = "objet_capture_selection_record"
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
    object_storage_setup_registration = "object_storage_setup_registration"
    source_intake_record = "source_intake_record"
    source_intake_batch = "source_intake_batch"
    object_storage_bytes_preservation = "object_storage_bytes_preservation"
    object_storage_formal_adoption = "object_storage_formal_adoption"
    local_recovery = "local_recovery"
    local_recovery_revert = "local_recovery_revert"


def _validated_target_preview_text(value: str | None) -> str | None:
    if value is None:
        return None
    if type(value) is not str:
        raise _fail("exact_human_approval_context_invalid")
    normalized = unicodedata.normalize("NFC", value).strip()
    if (
        not normalized
        or len(normalized) > _MAX_TARGET_PREVIEW_CHARACTERS
        or len(normalized.encode("utf-8")) > _MAX_TARGET_PREVIEW_UTF8_BYTES
        or any(
            character in "\r\n\t"
            or unicodedata.category(character) in {
                "Cc",
                "Cf",
                "Cs",
                "Zl",
                "Zp",
            }
            for character in normalized
        )
    ):
        raise _fail("exact_human_approval_context_invalid")
    return normalized


@dataclass(frozen=True)
class ExactHumanApprovalTargetPreview:
    """Small local-only identity shown beside one exact approval question.

    Values come from the already validated operation plan. They are never
    written into the public binding document, approval receipt, log, or result.
    The preview intentionally accepts identity-sized labels only, not zet body
    text, source excerpts, provider locators, or absolute filesystem paths.
    """

    kind: str
    primary: str
    secondary: str | None = None
    relation: str | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not str or self.kind not in _TARGET_PREVIEW_KINDS:
            raise _fail("exact_human_approval_context_invalid")
        object.__setattr__(self, "primary", _validated_target_preview_text(self.primary))
        object.__setattr__(
            self,
            "secondary",
            _validated_target_preview_text(self.secondary),
        )
        object.__setattr__(
            self,
            "relation",
            _validated_target_preview_text(self.relation),
        )
        if self.kind in {"zet_edge", "zet_objet"} and self.secondary is None:
            raise _fail("exact_human_approval_context_invalid")

    def __repr__(self) -> str:
        return f"<ExactHumanApprovalTargetPreview kind={self.kind} values=local-only>"


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
    ExactHumanApprovalOperation.promote_zet: "zet 승격",
    ExactHumanApprovalOperation.mint_zet: "zet 발행",
    ExactHumanApprovalOperation.zettel_edge: "zet 엣지 생성",
    ExactHumanApprovalOperation.zettel_edge_revert: "zet 엣지 되돌리기",
    ExactHumanApprovalOperation.zettel_objet_link: "zet-오브제 연결 생성",
    ExactHumanApprovalOperation.objet_capture: "단일 오브제 보존",
    ExactHumanApprovalOperation.objet_capture_batch: "오브제 배치 전체 보존",
    ExactHumanApprovalOperation.objet_capture_selection_record: "오브제 선택 기록",
    ExactHumanApprovalOperation.retire_draft: "발행된 초안 퇴역",
    ExactHumanApprovalOperation.warning_override: "경고 예외 적용",
    ExactHumanApprovalOperation.source_fidelity_session_evidence: "세션 근거 보존",
    ExactHumanApprovalOperation.human_artifact_lifecycle: "사람 작업물 수명주기 변경",
    ExactHumanApprovalOperation.duplicate_object_reconcile: "중복 오브제 정리",
    ExactHumanApprovalOperation.integrity_repair: "무결성 보충 또는 철회",
    ExactHumanApprovalOperation.project_version_update: "프로젝트 WOM-kit 버전 갱신",
    ExactHumanApprovalOperation.git_backup: "Git 원격 백업",
    ExactHumanApprovalOperation.notion_property_backfill: "Notion 원본 속성 복구",
    ExactHumanApprovalOperation.notion_property_backfill_revert: "Notion 원본 속성 복구 철회",
    ExactHumanApprovalOperation.object_storage_setup_registration: (
        "오브제 저장소 로컬 설정 등록"
    ),
    ExactHumanApprovalOperation.source_intake_record: "새 원본 반입 근거 기록",
    ExactHumanApprovalOperation.source_intake_batch: "새 원본 배치 반입 근거 기록",
    ExactHumanApprovalOperation.object_storage_bytes_preservation: (
        "오브제 원격 바이트 긴급 보존"
    ),
    ExactHumanApprovalOperation.object_storage_formal_adoption: (
        "오브제 원격 정식 채택"
    ),
    ExactHumanApprovalOperation.local_recovery: "검증된 로컬 복구",
    ExactHumanApprovalOperation.local_recovery_revert: "로컬 복구 되돌리기",
}

_OPERATION_QUESTIONS = {
    ExactHumanApprovalOperation.create_draft: "AI 초안을 만들까요?",
    ExactHumanApprovalOperation.promote_zet: "이 초안을 zet로 승격할까요?",
    ExactHumanApprovalOperation.mint_zet: "이 zet를 정본으로 발행할까요?",
    ExactHumanApprovalOperation.zettel_edge: "이 두 zet 사이에 엣지를 만들까요?",
    ExactHumanApprovalOperation.zettel_edge_revert: "이 두 zet 사이의 엣지만 되돌릴까요?",
    ExactHumanApprovalOperation.zettel_objet_link: "이 zet와 오브제를 연결할까요?",
    ExactHumanApprovalOperation.objet_capture: "검증된 원본 파일을 오브제로 보존할까요?",
    ExactHumanApprovalOperation.objet_capture_batch: (
        "검증된 원본 배치 전체를 오브제로 보존할까요?"
    ),
    ExactHumanApprovalOperation.objet_capture_selection_record: (
        "검증된 원본 파일의 오브제 선택 기록을 만들까요?"
    ),
    ExactHumanApprovalOperation.retire_draft: "발행을 마친 이 초안을 퇴역시킬까요?",
    ExactHumanApprovalOperation.warning_override: "경고를 확인하고 계속할까요?",
    ExactHumanApprovalOperation.source_fidelity_session_evidence: (
        "이 세션 근거를 보존할까요?"
    ),
    ExactHumanApprovalOperation.human_artifact_lifecycle: (
        "이 사람 작업물의 상태를 변경할까요?"
    ),
    ExactHumanApprovalOperation.duplicate_object_reconcile: (
        "검증된 중복 오브제 정리를 실행할까요?"
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
    ExactHumanApprovalOperation.object_storage_setup_registration: (
        "검토한 오브제 저장소 설정을 이 아카이브에 등록할까요?"
    ),
    ExactHumanApprovalOperation.source_intake_record: (
        "검토한 새 원본의 반입 근거를 기록할까요?"
    ),
    ExactHumanApprovalOperation.source_intake_batch: (
        "검토한 새 원본 배치(최대 1,000개)의 반입 근거를 기록할까요?"
    ),
    ExactHumanApprovalOperation.object_storage_bytes_preservation: (
        "원격 사본이 확인되지 않은 오브제 바이트를 먼저 보존할까요?"
    ),
    ExactHumanApprovalOperation.object_storage_formal_adoption: (
        "보존·검증된 오브제를 정식 원격 연결로 채택할까요?"
    ),
    ExactHumanApprovalOperation.local_recovery: (
        "WOM이 검증한 로컬 복구를 실행할까요?"
    ),
    ExactHumanApprovalOperation.local_recovery_revert: (
        "이 로컬 복구가 바꾼 필드만 되돌릴까요?"
    ),
}

_OPERATION_SUMMARIES = {
    ExactHumanApprovalOperation.create_draft: (
        "새 초안을 만들며 기존 정본은 변경하지 않습니다."
    ),
    ExactHumanApprovalOperation.promote_zet: (
        "검증된 초안을 zet 단계로 옮깁니다."
    ),
    ExactHumanApprovalOperation.mint_zet: (
        "검증된 zet를 정본으로 발행하고 영수증을 남깁니다."
    ),
    ExactHumanApprovalOperation.zettel_edge: (
        "검증된 두 zet 사이에 선택한 엣지만 추가합니다."
    ),
    ExactHumanApprovalOperation.zettel_edge_revert: (
        "선택한 엣지 영수증과 현재 zet가 일치할 때 그 엣지만 제거합니다."
    ),
    ExactHumanApprovalOperation.zettel_objet_link: (
        "검증된 zet와 오브제 사이에 선택한 연결만 추가합니다."
    ),
    ExactHumanApprovalOperation.objet_capture: (
        "검증된 선택 manifest의 원본 바이트만 보존하고 manifest와 영수증을 남깁니다."
    ),
    ExactHumanApprovalOperation.objet_capture_batch: (
        "검증된 배치 전체의 원본 바이트를 보존하고 manifest와 영수증을 남깁니다. "
        "외부 서비스(provider) 호출, 원격 업로드, zet 연결, 초안 생성, "
        "정본 발행은 하지 않습니다."
    ),
    ExactHumanApprovalOperation.objet_capture_selection_record: (
        "기존 source-intake 근거와 원본 바이트에 결속된 선택 기록 하나만 만듭니다. "
        "오브제 보존 자체는 실행하지 않습니다."
    ),
    ExactHumanApprovalOperation.retire_draft: (
        "정본 발행이 확인된 원본 초안만 퇴역시키며 정본은 변경하지 않습니다."
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
        "확실한 근거로 묶인 중복 오브제만 정리하고 불명확한 항목은 건드리지 않습니다."
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
        "확실히 매핑된 zet의 source_properties 필드만 복구합니다. "
        "매핑되지 않거나 검토가 필요한 항목은 변경하지 않습니다."
    ),
    ExactHumanApprovalOperation.notion_property_backfill_revert: (
        "이 복구가 추가한 source_properties 필드만 되돌립니다. "
        "제목과 본문 등 다른 필드는 변경하지 않습니다."
    ),
    ExactHumanApprovalOperation.object_storage_setup_registration: (
        "검토한 로컬 설정과 설정 영수증만 기록합니다. "
        "버킷을 만들거나 확인하지 않고 자격증명도 읽지 않습니다."
    ),
    ExactHumanApprovalOperation.source_intake_record: (
        "본문을 읽거나 복사하지 않고, 검토한 메타데이터 계획 하나만 "
        "새 영수증으로 기록합니다."
    ),
    ExactHumanApprovalOperation.source_intake_batch: (
        "최대 1,000개 원본의 바이트를 다시 읽어 해시를 확인하지만, 이 반입 단계에서는 "
        "그 바이트를 보관하거나 복사하지 않습니다. 검토된 각 항목의 메타데이터 "
        "영수증(N개)과 이어지는 오브제 보존용 요청 1개만 기록합니다."
    ),
    ExactHumanApprovalOperation.object_storage_bytes_preservation: (
        "확인된 로컬 오브제 바이트만 content-addressed 원격 key에 보존하고 "
        "다시 내려받아 검증합니다. 정식 연결로 표시하지 않습니다."
    ),
    ExactHumanApprovalOperation.object_storage_formal_adoption: (
        "바이트와 원격 근거가 일치하는 항목만 정식 채택하고 "
        "충돌 항목은 검토 상태로 남깁니다."
    ),
    ExactHumanApprovalOperation.local_recovery: (
        "근거가 정확히 일치하는 필드와 로컬 기록만 바꾸고, "
        "불명확한 항목은 검토 상태로 남깁니다."
    ),
    ExactHumanApprovalOperation.local_recovery_revert: (
        "이 복구 manifest가 바꾼 필드만 원래 값으로 되돌리고 "
        "관계없는 필드와 본문은 유지합니다."
    ),
}

_OPERATION_APPROVE_BUTTONS = {
    ExactHumanApprovalOperation.create_draft: "초안 만들기",
    ExactHumanApprovalOperation.promote_zet: "zet로 승격",
    ExactHumanApprovalOperation.mint_zet: "정본 발행",
    ExactHumanApprovalOperation.zettel_edge: "엣지 만들기",
    ExactHumanApprovalOperation.zettel_edge_revert: "엣지 되돌리기",
    ExactHumanApprovalOperation.zettel_objet_link: "연결 만들기",
    ExactHumanApprovalOperation.objet_capture: "오브제 보존",
    ExactHumanApprovalOperation.objet_capture_batch: "배치 전체 보존",
    ExactHumanApprovalOperation.objet_capture_selection_record: "선택 기록 만들기",
    ExactHumanApprovalOperation.retire_draft: "초안 퇴역",
    ExactHumanApprovalOperation.warning_override: "계속 실행",
    ExactHumanApprovalOperation.source_fidelity_session_evidence: "근거 보존",
    ExactHumanApprovalOperation.human_artifact_lifecycle: "상태 변경",
    ExactHumanApprovalOperation.duplicate_object_reconcile: "중복 정리",
    ExactHumanApprovalOperation.integrity_repair: "복구 실행",
    ExactHumanApprovalOperation.project_version_update: "업데이트 실행",
    ExactHumanApprovalOperation.git_backup: "백업 실행",
    ExactHumanApprovalOperation.notion_property_backfill: "복구 실행",
    ExactHumanApprovalOperation.notion_property_backfill_revert: "복구 되돌리기",
    ExactHumanApprovalOperation.object_storage_setup_registration: "로컬 설정 등록",
    ExactHumanApprovalOperation.source_intake_record: "반입 근거 기록",
    ExactHumanApprovalOperation.source_intake_batch: "배치 반입 근거 기록",
    ExactHumanApprovalOperation.object_storage_bytes_preservation: "바이트 보존",
    ExactHumanApprovalOperation.object_storage_formal_adoption: "정식 채택",
    ExactHumanApprovalOperation.local_recovery: "복구 실행",
    ExactHumanApprovalOperation.local_recovery_revert: "복구 되돌리기",
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
    target_preview: ExactHumanApprovalTargetPreview | None = None

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
        if self.target_preview is not None and type(self.target_preview) is not ExactHumanApprovalTargetPreview:
            raise _fail("exact_human_approval_context_invalid")

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
    # CommCtrl.h surrounds the task-dialog declarations with pshpack1.h.
    _pack_ = 1
    _fields_ = [("nButtonID", ctypes.c_int), ("pszButtonText", wintypes.LPCWSTR)]


class _TASKDIALOGCONFIG(ctypes.Structure):
    # The native ABI is byte-packed even on 64-bit Windows.  Default ctypes
    # alignment produces a plausible-looking 176-byte structure that
    # TaskDialogIndirect rejects with E_INVALIDARG; the SDK layout is 160
    # bytes on 64-bit Windows.
    _pack_ = 1
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


class _ACTCTXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.ULONG),
        ("dwFlags", wintypes.DWORD),
        ("lpSource", wintypes.LPCWSTR),
        ("wProcessorArchitecture", wintypes.USHORT),
        ("wLangId", wintypes.LANGID),
        ("lpAssemblyDirectory", wintypes.LPCWSTR),
        ("lpResourceName", wintypes.LPCWSTR),
        ("lpApplicationName", wintypes.LPCWSTR),
        ("hModule", wintypes.HMODULE),
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


@contextmanager
def _activate_comctl32_v6(
    *,
    loader: object | None = None,
) -> Iterator[None]:
    """Activate the v6 side-by-side assembly for this calling thread.

    Python launchers do not reliably embed the Common Controls v6 dependency
    that ``TaskDialogIndirect`` requires.  A content-free, create-only
    temporary manifest supplies the exact side-by-side dependency.  The source
    file is removed immediately after ``CreateActCtxW`` parses it; the returned
    activation-context handle owns the parsed state until release.
    """

    selected_loader = loader if loader is not None else getattr(ctypes, "WinDLL", None)
    if selected_loader is None:
        raise _fail("exact_human_approval_native_load_failed")
    manifest_path: str | None = None
    activation_handle: object | None = None
    cookie = ctypes.c_size_t(0)
    activated = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix="wom-comctl32-v6-",
            suffix=".manifest",
            delete=False,
        ) as manifest_file:
            manifest_path = manifest_file.name
            manifest_file.write(_COMMON_CONTROLS_V6_MANIFEST)
            manifest_file.flush()
            os.fsync(manifest_file.fileno())

        kernel32 = selected_loader("kernel32", use_last_error=True)
        create = kernel32.CreateActCtxW
        create.argtypes = [ctypes.POINTER(_ACTCTXW)]
        create.restype = wintypes.HANDLE
        activate = kernel32.ActivateActCtx
        activate.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t)]
        activate.restype = wintypes.BOOL
        deactivate = kernel32.DeactivateActCtx
        deactivate.argtypes = [wintypes.DWORD, ctypes.c_size_t]
        deactivate.restype = wintypes.BOOL
        release = kernel32.ReleaseActCtx
        release.argtypes = [wintypes.HANDLE]
        release.restype = None

        descriptor = _ACTCTXW()
        descriptor.cbSize = ctypes.sizeof(_ACTCTXW)
        descriptor.lpSource = manifest_path
        activation_handle = create(ctypes.byref(descriptor))
        invalid_handle = ctypes.c_void_p(-1).value
        if activation_handle in {None, invalid_handle}:
            raise _fail("exact_human_approval_activation_context_required")

        try:
            os.unlink(manifest_path)
            manifest_path = None
        except OSError:
            # The file contains no private or machine-specific value.  Keep the
            # bounded fallback cleanup below rather than weakening the native
            # approval boundary after a valid context has been parsed.
            pass

        if not activate(activation_handle, ctypes.byref(cookie)):
            raise _fail("exact_human_approval_activation_context_required")
        activated = True
        yield
        if not deactivate(0, cookie.value):
            raise _fail("exact_human_approval_activation_context_required")
        activated = False
    except ExactHumanApprovalWindowsError:
        raise
    except BaseException:
        raise _fail("exact_human_approval_activation_context_required") from None
    finally:
        if activated and activation_handle not in {None, ctypes.c_void_p(-1).value}:
            try:
                deactivate(0, cookie.value)
            except BaseException:
                pass
        if activation_handle not in {None, ctypes.c_void_p(-1).value}:
            try:
                release(activation_handle)
            except BaseException:
                pass
        if manifest_path is not None:
            try:
                os.unlink(manifest_path)
            except OSError:
                pass


class _CtypesTaskDialogNative:
    """Pointer-size-correct Unicode task-dialog implementation."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise _fail("exact_human_approval_platform_required")
        loader = getattr(ctypes, "WinDLL", None)
        if loader is None:
            raise _fail("exact_human_approval_native_load_failed")
        self._loader = loader

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
        try:
            with _activate_comctl32_v6(loader=self._loader):
                comctl32 = self._loader("comctl32", use_last_error=True)
                user32 = self._loader("user32", use_last_error=True)
                _require_comctl32_v6(comctl32)
                task_dialog = comctl32.TaskDialogIndirect
                task_dialog.argtypes = [
                    ctypes.POINTER(_TASKDIALOGCONFIG),
                    ctypes.POINTER(ctypes.c_int),
                    ctypes.POINTER(ctypes.c_int),
                    ctypes.POINTER(wintypes.BOOL),
                ]
                task_dialog.restype = ctypes.c_long
                get_foreground_window = user32.GetForegroundWindow
                get_foreground_window.argtypes = []
                get_foreground_window.restype = wintypes.HWND

                buttons = (_TASKDIALOG_BUTTON * 1)(
                    _TASKDIALOG_BUTTON(APPROVE_BUTTON_ID, approve_button_text)
                )
                button = ctypes.c_int(0)
                owner = get_foreground_window()
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
                    task_dialog(
                        ctypes.byref(config),
                        ctypes.byref(button),
                        None,
                        None,
                    )
                )
        except BaseException:
            raise _fail("exact_human_approval_native_call_failed") from None
        if result < 0:
            raise _fail("exact_human_approval_native_call_failed")
        return int(button.value), False


def _dialog_content(context: ExactHumanApprovalContext) -> str:
    target_preview = ""
    preview = context.target_preview
    if preview is not None:
        if preview.kind == "draft":
            preview_lines = [f"초안: {preview.primary}"]
            if preview.secondary is not None:
                preview_lines.append(f"제목: {preview.secondary}")
        elif preview.kind == "zet":
            preview_lines = [f"zet: {preview.primary}"]
            if preview.secondary is not None:
                preview_lines.append(f"제목: {preview.secondary}")
        elif preview.kind == "zet_edge":
            preview_lines = [
                f"출발 zet: {preview.primary}",
                f"도착 zet: {preview.secondary}",
            ]
            if preview.relation is not None:
                preview_lines.append(f"엣지: {preview.relation}")
        else:
            preview_lines = [
                f"zet: {preview.primary}",
                f"오브제: {preview.secondary}",
            ]
            if preview.relation is not None:
                preview_lines.append(f"연결 역할: {preview.relation}")
        target_preview = "확인할 대상\n" + "\n".join(preview_lines) + "\n\n"
    return (
        "WOM이 대상, 현재 상태, 적용할 변경을 자동으로 검증했습니다.\n\n"
        f"{_OPERATION_SUMMARIES[context.operation]}\n\n"
        f"{target_preview}"
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
    "ExactHumanApprovalTargetPreview",
    "ExactHumanApprovalWindowsError",
]
