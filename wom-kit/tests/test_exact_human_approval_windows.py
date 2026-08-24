from __future__ import annotations

import ctypes
import unittest

from wom_kit.exact_human_approval_windows import (
    APPROVE_BUTTON_ID,
    ExactHumanApprovalContext,
    ExactHumanApprovalIntent,
    ExactHumanApprovalOperation,
    ExactHumanApprovalWindowsError,
    _DLLVERSIONINFO,
    _require_comctl32_v6,
    _request_exact_human_approval_core as request_exact_human_approval,
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


if __name__ == "__main__":
    unittest.main()
