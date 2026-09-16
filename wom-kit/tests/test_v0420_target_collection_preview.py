from __future__ import annotations

import ctypes
import dataclasses
import hashlib
import json
import pickle
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import mock

from wom_kit import exact_human_approval_windows as approval
from wom_kit.target_collection_preview import TargetCollectionItem, TargetCollectionPreview


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64


def item(index: int, **kwargs: object) -> TargetCollectionItem:
    return TargetCollectionItem(
        identity_sha256="sha256:" + hashlib.sha256(f"synthetic-{index}".encode()).hexdigest(),
        kind="zet", **({"title": f"합성 제목 {index}"} | kwargs),
    )


def context() -> approval.ExactHumanApprovalContext:
    return approval.ExactHumanApprovalContext(
        operation=approval.ExactHumanApprovalOperation.local_recovery,
        archive_identity_sha256=SHA_A,
        plan_sha256=SHA_B,
        target_binding_sha256=SHA_C,
        reviewer_claim="person:synthetic-reviewer",
        review_binding_codes=("exact_targets",),
    )


class NativeFunction:
    def __init__(self, implementation):
        self.implementation = implementation

    def __call__(self, *args):
        return self.implementation(*args)


class NativeDialogHarness:
    """Exercise the production ctypes callback/config path without a window."""

    def __init__(self, actions, *, navigation_notified=True, reentrant_approval=False):
        self.actions = actions
        self.navigation_notified = navigation_notified
        self.reentrant_approval = reentrant_approval
        self.reentrant_results = []
        self.pages = []
        self.button_results = []
        self.config = None
        self.finished = False
        self.result = approval.IDCANCEL
        self.native = object.__new__(approval._CtypesTaskDialogNative)
        self.native._loader = self._loader
        self.user32 = SimpleNamespace(
            SendMessageW=NativeFunction(self._send),
            GetForegroundWindow=NativeFunction(lambda: 1),
        )
        self.comctl32 = SimpleNamespace(
            TaskDialogIndirect=NativeFunction(self._dialog),
            DllGetVersion=NativeFunction(self._version),
        )

    @staticmethod
    def _version(pointer):
        ctypes.cast(pointer, ctypes.POINTER(approval._DLLVERSIONINFO)).contents.dwMajorVersion = 6
        return 0

    def _loader(self, name, **kwargs):
        return {"user32": self.user32, "comctl32": self.comctl32}[name]

    def _notify(self, message, button=0):
        callback = ctypes.cast(self.config.pfCallback, approval._TASKDIALOG_CALLBACK)
        return callback(1, message, button, 0, 0)

    def _record(self):
        self.pages.append({
            "instruction": self.config.pszMainInstruction,
            "content": self.config.pszContent,
            "buttons": tuple(
                self.config.pButtons[i].nButtonID for i in range(self.config.cButtons)
            ),
            "default": self.config.nDefaultButton,
            "expanded": self.config.pszExpandedInformation,
            "flags": self.config.dwFlags,
        })

    def _send(self, hwnd, message, wparam, lparam):
        if message == approval.TDM_NAVIGATE_PAGE:
            self.config = ctypes.cast(lparam, ctypes.POINTER(approval._TASKDIALOGCONFIG)).contents
            self._record()
            if self.reentrant_approval:
                callback_result = self._notify(approval.TDN_BUTTON_CLICKED, approval.APPROVE_BUTTON_ID)
                self.reentrant_results.append(callback_result)
                if callback_result == 0:
                    self.result = approval.APPROVE_BUTTON_ID
                    self.finished = True
            if self.navigation_notified:
                self._notify(approval.TDN_NAVIGATED)
        elif message == approval.TDM_CLICK_BUTTON:
            if self._notify(approval.TDN_BUTTON_CLICKED, wparam) == 0:
                self.result = wparam
                self.finished = True
        return 0

    def _dialog(self, pointer, result, radio, checked):
        self.config = ctypes.cast(pointer, ctypes.POINTER(approval._TASKDIALOGCONFIG)).contents
        self._record()
        for action in self.actions:
            if self.finished:
                break
            if callable(action):
                action()
                continue
            callback_result = self._notify(approval.TDN_BUTTON_CLICKED, action)
            self.button_results.append((action, callback_result))
            if callback_result == 0:
                self.result = action
                self.finished = True
        if not self.finished:
            self._notify(approval.TDN_BUTTON_CLICKED, approval.IDCANCEL)
            self.result = approval.IDCANCEL
        self._notify(approval.TDN_DESTROYED)
        ctypes.cast(result, ctypes.POINTER(ctypes.c_int)).contents.value = self.result
        return 0

    def request(self, collection, *, observe=lambda: SHA_C, intent=approval.ExactHumanApprovalIntent.live_write):
        with mock.patch.object(approval, "_activate_comctl32_v6", side_effect=lambda **kwargs: nullcontext()):
            return approval._request_exact_human_approval_core(
                context(), intent=intent, native=self.native,
                target_collection=collection, observe_target_binding=observe,
            )


class TargetCollectionPreviewTests(unittest.TestCase):
    def test_count_profiles_are_complete_and_twenty_rows_per_page(self):
        for count in (1, 2, 5, 1000):
            with self.subTest(count=count):
                collection = TargetCollectionPreview(items=tuple(item(i) for i in range(count)))
                self.assertEqual(collection.native_main_text(), f"대상 {count:,}개")
                lines = []
                for page in range(collection.page_count):
                    rows = collection.native_page_text(page).splitlines()
                    self.assertLessEqual(len(rows), 20)
                    lines.extend(rows)
                self.assertEqual(len(lines), count)
                self.assertEqual(lines[-1], f"{count}. 합성 제목 {count - 1}")
                for invalid in (-1, collection.page_count, True):
                    with self.assertRaisesRegex(ValueError, "target_collection_preview_page_invalid"):
                        collection.native_page_text(invalid)

    def test_title_then_filename_and_short_identity_only_for_collisions(self):
        collection = TargetCollectionPreview(items=(
            item(0, title="같은 제목", filename="first.md"),
            item(1, title="같은 제목", filename="second.md"),
            item(2, title=None, filename="fallback.md"),
            item(3, title="고유 제목", filename="not-shown.md"),
        ))
        rows = collection.native_page_text(0).splitlines()
        self.assertIn(item(0).identity_sha256[7:15], rows[0])
        self.assertIn(item(1).identity_sha256[7:15], rows[1])
        self.assertEqual(rows[2], "3. fallback.md")
        self.assertEqual(rows[3], "4. 고유 제목")
        self.assertNotIn("first.md", rows[0])
        self.assertNotIn("sha256:", "\n".join(rows))

    def test_prefix_collision_lengthens_digest_until_unambiguous(self):
        collection = TargetCollectionPreview(items=tuple(
            TargetCollectionItem(identity_sha256="sha256:" + "a" * 8 + suffix * 56,
                                 kind="draft", title="같은 초안")
            for suffix in ("b", "c")
        ))
        rows = collection.native_page_text(0).splitlines()
        self.assertTrue(rows[0].endswith("a" * 8 + "b"))
        self.assertTrue(rows[1].endswith("a" * 8 + "c"))

    def test_sensitive_labels_omitted_without_losing_exact_identity(self):
        private_values = (
            "C:" + "\\" + "private" + "\\" + "note.md",
            "/private/note.md", "https://example.invalid/private",
            "synthetic@example.invalid", "token=" + "A" * 24,
            "nt" + "n_" + "A" * 24, "prefix " + "A" * 200 + " https://example.invalid/private",
        )
        for value in private_values:
            with self.subTest(shape=private_values.index(value)):
                target = item(0, title=value, filename=value)
                collection = TargetCollectionPreview(items=(target,))
                self.assertEqual(target.identity_sha256, item(0).identity_sha256)
                self.assertEqual(collection.native_page_text(0), "1. zet · 미리보기 생략")
                self.assertNotIn(value, repr(target) + repr(collection))
        long_relative_path = "x" * 200 + "/note.md"
        self.assertIsNone(item(0, title=None, filename=long_relative_path).filename)

    def test_local_views_do_not_serialize_or_enter_context_and_decision(self):
        target = item(0, title="로컬에만 있는 제목")
        collection = TargetCollectionPreview(items=(target,))
        for value in (target, collection):
            self.assertFalse(hasattr(value, "__dict__"))
            with self.assertRaises(TypeError):
                json.dumps(value)
            with self.assertRaisesRegex(TypeError, "target_collection_preview_local_only"):
                pickle.dumps(value)
        harness = NativeDialogHarness([approval.APPROVE_BUTTON_ID])
        decision = harness.request(collection)
        durable = json.dumps(dataclasses.asdict(context()), default=lambda value: value.value)
        durable += json.dumps(dataclasses.asdict(decision))
        self.assertNotIn("로컬에만 있는 제목", durable)
        self.assertNotIn("target_collection", {field.name for field in dataclasses.fields(context())})
        self.assertEqual(decision.plan_sha256, SHA_B)
        self.assertEqual(decision.target_binding_sha256, SHA_C)

    def test_invalid_and_mutable_collection_inputs_are_rejected_with_fixed_codes(self):
        for values in ((), [item(0)], (item(0), item(0))):
            with self.assertRaisesRegex(ValueError, "target_collection_preview_invalid"):
                TargetCollectionPreview(items=values)
        target = item(0)
        with self.assertRaisesRegex(TypeError, "target_collection_preview_immutable"):
            target.title = "changed"
        with self.assertRaisesRegex(TypeError, "target_collection_preview_immutable"):
            del target.title
        collection = TargetCollectionPreview(items=(target,))
        with self.assertRaisesRegex(TypeError, "target_collection_preview_immutable"):
            collection._items = ()
        with self.assertRaisesRegex(TypeError, "target_collection_preview_immutable"):
            del collection._items

    def test_single_edge_uses_both_names_human_meaning_and_filtered_reason(self):
        collection = TargetCollectionPreview(
            items=(item(0, title="출발 zet"), item(1, title="도착 zet")),
            relation_meaning="새 버전이 이전 내용을 대체함", reason="본문에서 수정 근거를 확인함",
        )
        self.assertEqual(collection.native_main_text(),
                         "출발 zet → 도착 zet\n관계 의미: 새 버전이 이전 내용을 대체함\n근거: 본문에서 수정 근거를 확인함")
        unsafe = TargetCollectionPreview(items=(item(0), item(1)), relation_meaning="의미",
                                         reason="https://example.invalid/private")
        self.assertIn("근거: 미리보기 생략", unsafe.native_main_text())

    def test_markdown_symbols_remain_literal_native_plain_text(self):
        title = "3 ~ 5 / A ~ B / **미완성 / ~~미완성"
        collection = TargetCollectionPreview(items=(item(0, title=title),))
        self.assertIn(title, collection.native_page_text(0))

    def test_native_paging_back_and_original_approval_only(self):
        collection = TargetCollectionPreview(items=tuple(item(i) for i in range(1000)))
        harness = NativeDialogHarness([
            approval.TARGET_DETAILS_BUTTON_ID, approval.APPROVE_BUTTON_ID,
            approval.TARGET_NEXT_BUTTON_ID, approval.TARGET_PREVIOUS_BUTTON_ID,
            approval.TARGET_RETURN_BUTTON_ID, approval.APPROVE_BUTTON_ID,
        ])
        observed = mock.Mock(return_value=SHA_C)
        decision = harness.request(collection, observe=observed)
        self.assertTrue(decision.approved)
        self.assertEqual(observed.call_count, 3)
        self.assertIn("대상 1,000개", harness.pages[0]["content"])
        self.assertNotIn("합성 제목", harness.pages[0]["content"])
        self.assertIn("1. 합성 제목 0", harness.pages[1]["content"])
        self.assertIn("21. 합성 제목 20", harness.pages[2]["content"])
        self.assertEqual(harness.pages[1]["content"], harness.pages[3]["content"])
        self.assertEqual(harness.pages[0]["content"], harness.pages[4]["content"])
        self.assertIn((approval.APPROVE_BUTTON_ID, 1), harness.button_results)
        for page in harness.pages[1:4]:
            self.assertNotIn(approval.APPROVE_BUTTON_ID, page["buttons"])
            self.assertIsNone(page["expanded"])
        for page in harness.pages:
            self.assertEqual(page["default"], approval.IDCANCEL)
            self.assertFalse(page["flags"] & 0x0001)  # no hyperlink/markup mode

    def test_native_cancel_and_synthetic_acknowledgement_never_grant_live_authority(self):
        collection = TargetCollectionPreview(items=(item(0),))
        for actions in ([approval.IDCANCEL], [approval.TARGET_DETAILS_BUTTON_ID, approval.IDCANCEL]):
            self.assertFalse(NativeDialogHarness(actions).request(collection).approved)
        synthetic = NativeDialogHarness([approval.APPROVE_BUTTON_ID]).request(
            collection, intent=approval.ExactHumanApprovalIntent.synthetic_acceptance,
        )
        self.assertFalse(synthetic.approved)
        self.assertTrue(synthetic.synthetic_acknowledged)

    def test_native_all_fifty_pages_reach_last_target_without_approval_button(self):
        collection = TargetCollectionPreview(items=tuple(item(i) for i in range(1000)))
        harness = NativeDialogHarness([
            approval.TARGET_DETAILS_BUTTON_ID,
            *([approval.TARGET_NEXT_BUTTON_ID] * 49),
            approval.TARGET_NEXT_BUTTON_ID,  # last-page out-of-range click is inert
            approval.TARGET_RETURN_BUTTON_ID, approval.APPROVE_BUTTON_ID,
        ])
        self.assertTrue(harness.request(collection).approved)
        details = harness.pages[1:-1]
        self.assertEqual(len(details), 50)
        self.assertEqual(sum(len(page["content"].splitlines()) for page in details), 1000)
        self.assertTrue(details[-1]["content"].endswith("1000. 합성 제목 999"))
        self.assertNotIn(approval.TARGET_NEXT_BUTTON_ID, details[-1]["buttons"])
        self.assertTrue(all(approval.APPROVE_BUTTON_ID not in page["buttons"] for page in details))

    def test_fresh_target_drift_before_and_after_detail_is_blocked(self):
        collection = TargetCollectionPreview(items=(item(0),))
        for observations in ((SHA_A,), (SHA_C, SHA_A), (SHA_C, SHA_C, SHA_A)):
            with self.subTest(observation_count=len(observations)):
                harness = NativeDialogHarness([
                    approval.TARGET_DETAILS_BUTTON_ID, approval.TARGET_RETURN_BUTTON_ID,
                    approval.APPROVE_BUTTON_ID,
                ])
                with self.assertRaisesRegex(approval.ExactHumanApprovalWindowsError,
                                            "exact_human_approval_target_changed"):
                    harness.request(collection, observe=mock.Mock(side_effect=observations))

    def test_observer_failure_does_not_reflect_private_exception(self):
        collection = TargetCollectionPreview(items=(item(0),))
        harness = NativeDialogHarness([approval.APPROVE_BUTTON_ID])
        with self.assertRaises(approval.ExactHumanApprovalWindowsError) as raised:
            harness.request(collection, observe=mock.Mock(side_effect=[SHA_C, RuntimeError("private-sentinel")]))
        self.assertEqual(str(raised.exception), "exact_human_approval_target_observation_failed")
        self.assertNotIn("private-sentinel", repr(raised.exception))
        self.assertIsNone(raised.exception.__context__)

    def test_unconfirmed_navigation_fails_closed(self):
        collection = TargetCollectionPreview(items=(item(0),))
        harness = NativeDialogHarness([approval.TARGET_DETAILS_BUTTON_ID, approval.APPROVE_BUTTON_ID],
                                      navigation_notified=False)
        with self.assertRaisesRegex(approval.ExactHumanApprovalWindowsError,
                                    "exact_human_approval_native_call_failed"):
            harness.request(collection)

    def test_reentrant_approval_during_navigation_cannot_replace_main_human_click(self):
        collection = TargetCollectionPreview(items=(item(0),))
        harness = NativeDialogHarness([
            approval.TARGET_DETAILS_BUTTON_ID, approval.TARGET_RETURN_BUTTON_ID, approval.IDCANCEL,
        ], reentrant_approval=True)
        observed = mock.Mock(return_value=SHA_C)
        result = harness.request(collection, observe=observed)
        self.assertFalse(result.approved)
        self.assertEqual(harness.reentrant_results, [1, 1])
        self.assertEqual(observed.call_count, 1)

    def test_no_observer_or_unapproved_native_return_cannot_authorize(self):
        collection = TargetCollectionPreview(items=(item(0),))
        fake = SimpleNamespace(show_collection=lambda **kwargs: (approval.APPROVE_BUTTON_ID, True))
        with self.assertRaisesRegex(approval.ExactHumanApprovalWindowsError,
                                    "exact_human_approval_context_invalid"):
            approval._request_exact_human_approval_core(context(), intent=approval.ExactHumanApprovalIntent.live_write,
                                                       native=fake, target_collection=collection)
        decision = approval._request_exact_human_approval_core(
            context(), intent=approval.ExactHumanApprovalIntent.live_write, native=fake,
            target_collection=collection, observe_target_binding=lambda: SHA_C,
        )
        self.assertFalse(decision.approved)


if __name__ == "__main__":
    unittest.main()
