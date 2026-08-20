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
        self.calls: list[dict[str, str]] = []

    def show(self, **kwargs: str) -> tuple[int, bool]:
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

    def test_live_requires_button_and_checked_verification(self) -> None:
        for native_result, approved in (
            ((APPROVE_BUTTON_ID, True), True),
            ((APPROVE_BUTTON_ID, False), False),
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

    def test_dialog_contains_only_fixed_labels_codes_and_bindings(self) -> None:
        native = _FakeNative()
        request_exact_human_approval(
            self._context(),
            intent=ExactHumanApprovalIntent.live_write,
            native=native,
        )
        self.assertEqual(len(native.calls), 1)
        rendered = "\n".join(native.calls[0].values())
        for expected in (
            SHA_A,
            SHA_B,
            SHA_C,
            "body_digest",
            "frontmatter_digest",
            "unknown_facet_key",
            "person:local-operator",
            "실제 쓰기 1회를 검토하고 승인합니다",
        ):
            self.assertIn(expected, rendered)
        for forbidden in (
            "Bearer ",
            "https://",
            "C:\\",
            "profiles/local/",
            "secret_",
        ):
            self.assertNotIn(forbidden, rendered)

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
            def show(self, **_kwargs: str) -> tuple[int, bool]:
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
