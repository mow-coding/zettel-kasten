from __future__ import annotations

import ctypes
import os
import unittest
from pathlib import Path

from wom_kit.exact_human_approval_windows import (
    APPROVE_BUTTON_ID,
    ExactHumanApprovalContext,
    ExactHumanApprovalIntent,
    ExactHumanApprovalOperation,
    ExactHumanApprovalTargetPreview,
    ExactHumanApprovalWindowsError,
    _ACTCTXW,
    _COMMON_CONTROLS_V6_MANIFEST,
    _DLLVERSIONINFO,
    _TASKDIALOGCONFIG,
    _TASKDIALOG_BUTTON,
    _activate_comctl32_v6,
    _require_comctl32_v6,
    _request_exact_human_approval_core as request_exact_human_approval,
    exact_human_approval_safe_content_preview,
)


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


class _FakeNative:
    def __init__(self, result: tuple[int, bool] = (APPROVE_BUTTON_ID, True)) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def show(self, **kwargs: object) -> tuple[int, bool]:
        self.calls.append(dict(kwargs))
        return self.result


class ExactHumanApprovalWindowsTests(unittest.TestCase):
    @staticmethod
    def _synthetic_private_preview_shapes() -> tuple[str, ...]:
        return (
            "Bearer " + ("A" * 24),
            "prefix_" + "nt" + "n_" + ("A" * 24),
            "prefix_" + "secret" + "_" + ("A" * 24),
            "prefix_" + "github" + "_pat_" + ("A" * 24),
            "gh" + "p_" + ("A" * 24),
            "gh" + "o_" + ("A" * 24),
            "gh" + "u_" + ("A" * 24),
            "gh" + "s_" + ("A" * 24),
            "gh" + "r_" + ("A" * 24),
            "gl" + "pat-" + ("A" * 20),
            "xo" + "xb-" + ("A" * 20),
            "xa" + "pp-" + ("A" * 20),
            "AI" + "za" + ("A" * 35),
            "AK" + "IA" + ("A" * 16),
            "AS" + "IA" + ("A" * 16),
            "ya" + "29." + ("A" * 24),
            "GOC" + "SPX-" + ("A" * 20),
            "s" + "k-" + ("A" * 24),
            "s" + "k-proj-" + ("A" * 24),
            "s" + "k_live_" + ("A" * 20),
            "r" + "k_live_" + ("A" * 20),
            "s" + "k_test_" + ("A" * 20),
            "r" + "k_test_" + ("A" * 20),
            "ey" + "J" + ("A" * 12) + "." + ("B" * 12) + "." + ("C" * 12),
            "-----BE" + "GIN PRIVATE KEY-----",
            "token=" + ("A" * 20),
            "credential=" + ("A" * 20),
            "client_secret=" + ("A" * 20),
            "aws_secret_access_key=" + ("A" * 20),
            "Authorization: Basic " + ("A" * 20),
        )

    def _context(self) -> ExactHumanApprovalContext:
        return ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.create_draft,
            archive_identity_sha256=SHA_A,
            plan_sha256=SHA_B,
            target_binding_sha256=SHA_C,
            reviewer_claim="person:local-operator",
            review_binding_codes=("body_digest", "frontmatter_digest"),
            warning_codes=("unknown_facet_key",),
        )

    def test_live_requires_explicit_action_button_not_checkbox(self) -> None:
        for native_result, approved in (
            ((APPROVE_BUTTON_ID, True), True),
            ((APPROVE_BUTTON_ID, False), True),
            ((2, True), False),
            ((2, False), False),
        ):
            with self.subTest(native_result=native_result):
                result = request_exact_human_approval(
                    self._context(),
                    intent=ExactHumanApprovalIntent.live_write,
                    native=_FakeNative(native_result),
                )
                self.assertIs(result.approved, approved)
                self.assertFalse(result.synthetic_acknowledged)
                self.assertEqual(result.plan_sha256, SHA_B)
                self.assertEqual(result.target_binding_sha256, SHA_C)

    def test_synthetic_acknowledgement_never_becomes_live_approval(self) -> None:
        result = request_exact_human_approval(
            self._context(),
            intent=ExactHumanApprovalIntent.synthetic_acceptance,
            native=_FakeNative(),
        )
        self.assertFalse(result.approved)
        self.assertTrue(result.synthetic_acknowledged)
        self.assertEqual(
            result.reason_code, "exact_human_approval_synthetic_acknowledged"
        )

    def test_dialog_keeps_human_decision_simple_and_machine_evidence_advanced(self) -> None:
        native = _FakeNative()
        request_exact_human_approval(
            self._context(),
            intent=ExactHumanApprovalIntent.live_write,
            native=native,
        )
        self.assertEqual(len(native.calls), 1)
        call = native.calls[0]
        primary = "\n".join(
            str(call[name])
            for name in ("title", "main_instruction", "content", "approve_button_text", "footer")
        )
        advanced = str(call["expanded_information"])
        self.assertIn("AI 초안을 만들까요?", primary)
        self.assertIn("초안 만들기", primary)
        self.assertIn("사람이 결정할 일은 이 작업을 지금 실행할지 여부", primary)
        self.assertIn("취소하면 아무 변경도 하지 않습니다", primary)
        for expected in (
            SHA_A,
            SHA_B,
            SHA_C,
            "body_digest",
            "frontmatter_digest",
            "unknown_facet_key",
            "person:local-operator",
            "사람이 직접 비교하거나 계산할 필요가 없습니다",
        ):
            self.assertIn(expected, advanced)
            self.assertNotIn(expected, primary)
        self.assertEqual(call["collapsed_control_text"], "기술 세부정보 보기")
        self.assertEqual(call["expanded_control_text"], "기술 세부정보 숨기기")
        rendered = primary + "\n" + advanced
        for forbidden in (
            "Bearer ",
            "https://",
            "C:\\",
            "profiles/local/",
            "secret_",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_every_operation_has_one_plain_question_summary_and_action(self) -> None:
        for operation in ExactHumanApprovalOperation:
            with self.subTest(operation=operation.value):
                context = ExactHumanApprovalContext(
                    operation=operation,
                    archive_identity_sha256=SHA_A,
                    plan_sha256=SHA_B,
                    target_binding_sha256=SHA_C,
                    reviewer_claim="person:local-operator",
                    review_binding_codes=("machine_verified",),
                )
                native = _FakeNative((2, False))
                request_exact_human_approval(
                    context,
                    intent=ExactHumanApprovalIntent.live_write,
                    native=native,
                )
                call = native.calls[0]
                self.assertTrue(str(call["main_instruction"]).endswith("까요?"))
                self.assertTrue(str(call["approve_button_text"]))
                primary = str(call["content"])
                self.assertIn("WOM이", primary)
                self.assertIn("사람이 결정할 일", primary)
                for machine_value in (SHA_A, SHA_B, SHA_C, "machine_verified"):
                    self.assertNotIn(machine_value, primary)

    def test_batch_dialogs_state_the_full_multiple_item_scope(self) -> None:
        cases = (
            (
                ExactHumanApprovalOperation.source_intake_batch,
                (
                    "원본 배치(최대 1,000개)",
                    "바이트를 다시 읽어 해시를 확인",
                    "바이트를 보관하거나 복사하지 않습니다",
                    "영수증(N개)",
                    "요청 1개",
                    "배치 반입 근거 기록",
                ),
                (
                    "메타데이터 계획 하나만",
                    "본문을 읽거나 복사하지 않고",
                    "단일 오브제",
                ),
            ),
            (
                ExactHumanApprovalOperation.objet_capture_batch,
                (
                    "원본 배치 전체",
                    "배치 전체의 원본 바이트를 보존",
                    "manifest와 영수증",
                    "외부 서비스(provider) 호출",
                    "원격 업로드",
                    "zet 연결",
                    "초안 생성",
                    "정본 발행",
                    "배치 전체 보존",
                ),
                (
                    "단일 오브제",
                    "원본 파일을 오브제로",
                    "선택 기록 하나만",
                ),
            ),
        )
        for operation, expected, forbidden in cases:
            with self.subTest(operation=operation.value):
                context = ExactHumanApprovalContext(
                    operation=operation,
                    archive_identity_sha256=SHA_A,
                    plan_sha256=SHA_B,
                    target_binding_sha256=SHA_C,
                    reviewer_claim="person:local-operator",
                    review_binding_codes=("complete_batch_item_set",),
                )
                native = _FakeNative((2, False))
                request_exact_human_approval(
                    context,
                    intent=ExactHumanApprovalIntent.live_write,
                    native=native,
                )
                call = native.calls[0]
                rendered = "\n".join(
                    str(call[name])
                    for name in (
                        "main_instruction",
                        "content",
                        "approve_button_text",
                        "expanded_information",
                    )
                )
                for value in expected:
                    self.assertIn(value, rendered)
                for value in forbidden:
                    self.assertNotIn(value, rendered)

    def test_notion_recovery_explains_scope_without_delegating_verification(self) -> None:
        context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.notion_property_backfill,
            archive_identity_sha256=SHA_A,
            plan_sha256=SHA_B,
            target_binding_sha256=SHA_C,
            reviewer_claim="person:local-operator",
            review_binding_codes=("source_properties",),
            warning_codes=("review_pages_present",),
        )
        native = _FakeNative((2, False))
        request_exact_human_approval(
            context,
            intent=ExactHumanApprovalIntent.live_write,
            native=native,
        )
        call = native.calls[0]
        self.assertEqual(
            call["main_instruction"],
            "검증된 Notion 원본 속성 복구를 실행할까요?",
        )
        self.assertEqual(call["approve_button_text"], "복구 실행")
        self.assertIn("source_properties 필드만 복구", str(call["content"]))
        self.assertIn("검토가 필요한 항목은 변경하지 않습니다", str(call["content"]))
        self.assertNotIn("review_pages_present", str(call["content"]))
        self.assertIn("review_pages_present", str(call["expanded_information"]))

    def test_dialog_uses_canonical_wom_product_language(self) -> None:
        expected_questions = {
            ExactHumanApprovalOperation.mint_zet: "이 zet를 정본으로 발행할까요?",
            ExactHumanApprovalOperation.zettel_edge: (
                "이 두 zet 사이에 엣지를 만들까요?"
            ),
            ExactHumanApprovalOperation.zettel_objet_link: (
                "이 zet와 오브제를 연결할까요?"
            ),
            ExactHumanApprovalOperation.retire_draft: (
                "발행을 마친 이 초안을 퇴역시킬까요?"
            ),
        }
        for operation, question in expected_questions.items():
            with self.subTest(operation=operation.value):
                context = ExactHumanApprovalContext(
                    operation=operation,
                    archive_identity_sha256=SHA_A,
                    plan_sha256=SHA_B,
                    target_binding_sha256=SHA_C,
                    reviewer_claim="person:local-operator",
                    review_binding_codes=("machine_verified",),
                )
                native = _FakeNative((2, False))
                request_exact_human_approval(
                    context,
                    intent=ExactHumanApprovalIntent.live_write,
                    native=native,
                )
                rendered = "\n".join(str(value) for value in native.calls[0].values())
                self.assertEqual(native.calls[0]["main_instruction"], question)
                for forbidden in ("제텔", "오브젝트", "중복 객체"):
                    self.assertNotIn(forbidden, rendered)
        self.assertIn("퇴역", expected_questions[ExactHumanApprovalOperation.retire_draft])
        self.assertNotIn("폐기", expected_questions[ExactHumanApprovalOperation.retire_draft])

    def test_dialog_shows_local_target_identity_without_putting_it_in_machine_details(self) -> None:
        preview = ExactHumanApprovalTargetPreview(
            kind="zet_edge",
            primary="출발-zet.md",
            secondary="도착-zet.md",
            relation="supports",
            primary_id="zet_source_01",
            secondary_id="zet_target_02",
            primary_label="출발 zet 제목",
            secondary_label="도착 zet 제목",
            source_preview="이 연결의 출발점이 되는 짧은 내용 단서입니다.",
        )
        context = ExactHumanApprovalContext(
            operation=ExactHumanApprovalOperation.zettel_edge,
            archive_identity_sha256=SHA_A,
            plan_sha256=SHA_B,
            target_binding_sha256=SHA_C,
            reviewer_claim="person:local-operator",
            review_binding_codes=("edge_contract",),
            target_preview=preview,
        )
        native = _FakeNative((2, False))

        request_exact_human_approval(
            context,
            intent=ExactHumanApprovalIntent.live_write,
            native=native,
        )

        call = native.calls[0]
        content = str(call["content"])
        self.assertIn("확인할 대상", content)
        self.assertIn("출발 zet: 출발 zet 제목", content)
        self.assertIn("도착 zet: 도착 zet 제목", content)
        self.assertIn("출발 파일: 출발-zet.md", content)
        self.assertIn("출발 ID: zet_source_01", content)
        self.assertIn("도착 식별자: 도착-zet.md", content)
        self.assertIn("도착 ID: zet_target_02", content)
        self.assertIn("엣지: supports", content)
        self.assertIn(
            "짧은 내용 미리보기: 이 연결의 출발점이 되는 짧은 내용 단서입니다.",
            content,
        )
        advanced = str(call["expanded_information"])
        self.assertNotIn("출발-zet.md", advanced)
        self.assertNotIn("도착-zet.md", advanced)
        self.assertNotIn("supports", advanced)
        self.assertNotIn("짧은 내용 단서", advanced)
        self.assertNotIn("출발-zet.md", repr(context))
        self.assertNotIn("출발-zet.md", repr(preview))
        self.assertNotIn("짧은 내용 단서", repr(context))
        self.assertNotIn("짧은 내용 단서", repr(preview))

    def test_content_preview_rejects_private_locators_and_secret_assignments(self) -> None:
        windows_path = r"C:" + r"\Users\private\note.md"
        escaped_windows_path = r"C:" + r"\\Users\\private\\note.md"
        for unsafe in (
            "원본은 " + escaped_windows_path + " 입니다.",
            r"원본은 \\\\server\\share\\note.md 입니다.",
            "원본은 /etc/private/note.md 입니다.",
            f'원본은 "{windows_path}" 입니다.',
            f"원본은 `{windows_path}` 입니다.",
            f"원본은 {{{windows_path}}} 입니다.",
            f"원본은 “{escaped_windows_path}” 입니다.",
            f"원본은 '{windows_path}' 입니다.",
            "https://private.example/note",
            "password=do-not-show",
            "owner@example.com",
        ):
            with self.subTest(unsafe=unsafe), self.assertRaises(
                ExactHumanApprovalWindowsError
            ):
                ExactHumanApprovalTargetPreview(
                    kind="zet",
                    primary="safe.md",
                    source_preview=unsafe,
                )

    def test_content_preview_omits_token_source_id_and_provider_locator_shapes(self) -> None:
        unsafe_values = self._synthetic_private_preview_shapes() + (
            "123e4567-e89b-12d3-a456-426614174000",
            "0123456789abcdef0123456789abcdef",
            "notion:private-page-reference",
            "wom-objet:private-object-reference",
            "s3://private-bucket/private-key",
        )
        for unsafe in unsafe_values:
            with self.subTest(unsafe=unsafe):
                self.assertIsNone(
                    exact_human_approval_safe_content_preview(unsafe)
                )
                with self.assertRaises(ExactHumanApprovalWindowsError):
                    ExactHumanApprovalTargetPreview(
                        kind="zet",
                        primary="safe.md",
                        source_preview=unsafe,
                    )

    def test_required_identity_rejects_private_shapes_but_accepts_safe_hash(self) -> None:
        unsafe_values = self._synthetic_private_preview_shapes() + (
            "123e4567-e89b-12d3-a456-426614174000",
            "0123456789abcdef0123456789abcdef",
            "notion:private-page-reference",
        )
        for unsafe in unsafe_values:
            with self.subTest(unsafe=unsafe), self.assertRaises(
                ExactHumanApprovalWindowsError
            ):
                ExactHumanApprovalTargetPreview(kind="zet", primary=unsafe)

        preview = ExactHumanApprovalTargetPreview(
            kind="zet_objet",
            primary="safe.md",
            secondary=SHA_A,
        )
        self.assertEqual(preview.secondary, SHA_A)

    def test_plain_colon_labels_and_noncredential_sk_filename_remain_available(self) -> None:
        safe_values = (
            "AI:assistant-assisted draft",
            "TODO:review-this-draft",
            "example:ordinary-label",
            "sk-project-roadmap.md",
        )
        for safe in safe_values:
            with self.subTest(safe=safe):
                self.assertEqual(
                    exact_human_approval_safe_content_preview(safe),
                    safe,
                )
                preview = ExactHumanApprovalTargetPreview(
                    kind="zet",
                    primary=safe,
                )
                self.assertEqual(preview.primary, safe)

    def test_target_preview_rejects_multiline_or_directional_spoofing(self) -> None:
        windows_path = r"C:" + r"\Users\private\draft.md"
        escaped_windows_path = r"C:" + r"\\Users\\private\\draft.md"
        for unsafe in (
            "first\nsecond",
            "safe\u2028fake label",
            "safe\u2029fake paragraph",
            "safe\u202eevil",
            escaped_windows_path,
            "/etc/private/draft.md",
            f'"{windows_path}"',
            f"`{windows_path}`",
            f"“{escaped_windows_path}”",
            "https://private.example/draft",
        ):
            with self.subTest(unsafe=unsafe), self.assertRaises(
                ExactHumanApprovalWindowsError
            ):
                ExactHumanApprovalTargetPreview(kind="zet", primary=unsafe)

    def test_invalid_context_or_plain_string_intent_fails_before_native(self) -> None:
        native = _FakeNative()
        for kwargs in (
            {"plan_sha256": "b" * 64},
            {"reviewer_claim": "person:C:\\private"},
            {"review_binding_codes": ("unsafe-value=private",)},
            {"warning_codes": ("duplicate", "duplicate")},
        ):
            values = {
                "operation": ExactHumanApprovalOperation.create_draft,
                "archive_identity_sha256": SHA_A,
                "plan_sha256": SHA_B,
                "target_binding_sha256": SHA_C,
                "reviewer_claim": "person:local-operator",
                "review_binding_codes": ("body_digest",),
                "warning_codes": (),
            }
            values.update(kwargs)
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ExactHumanApprovalWindowsError):
                    ExactHumanApprovalContext(**values)
        with self.assertRaises(ExactHumanApprovalWindowsError):
            request_exact_human_approval(
                self._context(),
                intent="live_write",  # type: ignore[arg-type]
                native=native,
            )
        self.assertEqual(native.calls, [])

    def test_native_exception_is_content_free(self) -> None:
        class _ExplodingNative:
            def show(self, **_kwargs: object) -> tuple[int, bool]:
                raise RuntimeError("secret_private_path")

        with self.assertRaises(ExactHumanApprovalWindowsError) as captured:
            request_exact_human_approval(
                self._context(),
                intent=ExactHumanApprovalIntent.live_write,
                native=_ExplodingNative(),
            )
        self.assertEqual(captured.exception.code, "exact_human_approval_native_call_failed")
        self.assertNotIn("secret_private_path", str(captured.exception))

    def test_native_boundary_requires_loaded_common_controls_v6(self) -> None:
        class _VersionFunction:
            argtypes: object = None
            restype: object = None

            def __init__(self, major: int, result: int = 0) -> None:
                self.major = major
                self.result = result

            def __call__(self, raw: object) -> int:
                info = ctypes.cast(
                    raw, ctypes.POINTER(_DLLVERSIONINFO)
                ).contents
                info.dwMajorVersion = self.major
                return self.result

        class _Library:
            def __init__(self, major: int, result: int = 0) -> None:
                self.DllGetVersion = _VersionFunction(major, result)

        _require_comctl32_v6(_Library(6))
        for library in (_Library(5), _Library(6, -1), object()):
            with self.subTest(library=type(library).__name__):
                with self.assertRaises(ExactHumanApprovalWindowsError) as captured:
                    _require_comctl32_v6(library)
                self.assertEqual(
                    captured.exception.code,
                    "exact_human_approval_activation_context_required",
                )

    def test_task_dialog_structures_use_commctrl_byte_packing(self) -> None:
        pointer_bytes = ctypes.sizeof(ctypes.c_void_p)
        self.assertEqual(
            ctypes.sizeof(_TASKDIALOG_BUTTON),
            12 if pointer_bytes == 8 else 8,
        )
        self.assertEqual(
            ctypes.sizeof(_TASKDIALOGCONFIG),
            160 if pointer_bytes == 8 else 96,
        )
        self.assertEqual(_TASKDIALOGCONFIG.hwndParent.offset, 4)
        self.assertEqual(
            _TASKDIALOGCONFIG.pszMainInstruction.offset,
            44 if pointer_bytes == 8 else 28,
        )

    def test_activation_context_parses_content_free_manifest_and_cleans_source(self) -> None:
        calls: list[tuple[object, ...]] = []
        observed: dict[str, object] = {}

        class _Function:
            argtypes: object = None
            restype: object = None

            def __init__(self, callback):
                self.callback = callback

            def __call__(self, *args):
                return self.callback(*args)

        def create(raw: object) -> int:
            descriptor = ctypes.cast(
                raw, ctypes.POINTER(_ACTCTXW)
            ).contents
            source = Path(descriptor.lpSource)
            observed["source"] = source
            observed["manifest"] = source.read_bytes()
            calls.append(("create",))
            return 123

        def activate(handle: object, raw_cookie: object) -> int:
            ctypes.cast(
                raw_cookie, ctypes.POINTER(ctypes.c_size_t)
            ).contents.value = 456
            calls.append(("activate", handle))
            return 1

        def deactivate(flags: object, cookie: object) -> int:
            calls.append(("deactivate", flags, cookie))
            return 1

        def release(handle: object) -> None:
            calls.append(("release", handle))

        class _Kernel32:
            CreateActCtxW = _Function(create)
            ActivateActCtx = _Function(activate)
            DeactivateActCtx = _Function(deactivate)
            ReleaseActCtx = _Function(release)

        class _Loader:
            def __call__(self, name: str, **kwargs: object) -> object:
                self_name = name.lower()
                self.assertEqual(self_name, "kernel32")
                self.assertTrue(kwargs.get("use_last_error"))
                return _Kernel32()

            def assertEqual(self, first: object, second: object) -> None:
                ExactHumanApprovalWindowsTests.assertEqual(
                    self_test, first, second
                )

            def assertTrue(self, value: object) -> None:
                ExactHumanApprovalWindowsTests.assertTrue(self_test, value)

        self_test = self
        with _activate_comctl32_v6(loader=_Loader()):
            source = observed["source"]
            self.assertIsInstance(source, Path)
            self.assertFalse(os.path.exists(source))
            self.assertEqual(observed["manifest"], _COMMON_CONTROLS_V6_MANIFEST)

        self.assertEqual(
            calls,
            [
                ("create",),
                ("activate", 123),
                ("deactivate", 0, 456),
                ("release", 123),
            ],
        )


if __name__ == "__main__":
    unittest.main()
