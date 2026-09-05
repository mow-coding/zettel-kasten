"""Real claim files with fake native decisions; no popup or credential access."""

from dataclasses import fields, replace
from contextlib import nullcontext
import hashlib
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from wom_kit import exact_human_approval as authority
from wom_kit import exact_human_approval_windows as native_approval
from wom_kit import exact_human_approval_workflow as workflow
from wom_kit.target_collection_preview import TargetCollectionItem, TargetCollectionPreview


class KeyProvider:
    def __init__(self):
        self.creates = []

    def use_key(self, root, consumer, *, create_if_missing=False):
        self.creates.append(create_if_missing)
        key = bytearray(range(32))
        try:
            return consumer(memoryview(key))
        finally:
            key[:] = bytes(len(key))


class Native:
    def __init__(self, *, cancel=False, during_details=None, after_approve=None):
        self.cancel = cancel
        self.during_details = during_details
        self.after_approve = after_approve
        self.calls = []
        self.page_sizes = []

    def show(self, **kwargs):
        self.calls.append(kwargs)
        return (native_approval.IDCANCEL if self.cancel else native_approval.APPROVE_BUTTON_ID, False)

    def show_collection(self, *, session, **kwargs):
        self.calls.append(kwargs)
        assert session.button_clicked(native_approval.TARGET_DETAILS_BUTTON_ID) == "navigate"
        for index in range(session.preview.page_count):
            self.page_sizes.append(len(session.preview.native_page_text(index).splitlines()))
            if index + 1 < session.preview.page_count:
                assert session.button_clicked(native_approval.TARGET_NEXT_BUTTON_ID) == "navigate"
        # Even a spurious approve-button notification on details is powerless.
        assert session.button_clicked(native_approval.APPROVE_BUTTON_ID) == "ignore"
        if self.during_details is not None:
            self.during_details()
        if self.cancel:
            assert session.button_clicked(native_approval.IDCANCEL) == "close"
            return native_approval.IDCANCEL, False
        assert session.button_clicked(native_approval.TARGET_RETURN_BUTTON_ID) == "navigate"
        assert session.button_clicked(native_approval.APPROVE_BUTTON_ID) == "close"
        if self.after_approve is not None:
            self.after_approve()
        return native_approval.APPROVE_BUTTON_ID, False


class WorkflowPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wom-preview-workflow-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "archive"
        self.root.mkdir()
        (self.root / "archive.yml").write_text("archive_id: archive:test\n", encoding="utf-8")
        self.context = native_approval.ExactHumanApprovalContext(
            operation=native_approval.ExactHumanApprovalOperation.zettel_edge,
            archive_identity_sha256=authority.exact_human_approval_archive_identity_sha256("archive:test"),
            plan_sha256="sha256:" + "a" * 64,
            target_binding_sha256="sha256:" + "b" * 64,
            reviewer_claim="person:local-operator",
            review_binding_codes=("edge_plan_digest", "target_digest"),
        )
        self.provider = KeyProvider()
        self.writer = mock.Mock(return_value={"ok": True})

    def collection(self, count=1):
        return TargetCollectionPreview(items=tuple(
            TargetCollectionItem(
                identity_sha256="sha256:" + hashlib.sha256(f"synthetic-{index}".encode()).hexdigest(),
                kind="zet", title=f"합성 로컬 전용 제목 {index}",
            ) for index in range(count)
        ))

    def execute(self, **kwargs):
        return workflow._execute_exact_human_approved_write_core(
            self.root, self.context, self.writer, key_provider=self.provider, **kwargs,
        )

    def assert_untouched(self):
        self.assertEqual(self.provider.creates, [])
        self.writer.assert_not_called()
        self.assertFalse((self.root / "profiles").exists())

    def test_omitted_preview_preserves_legacy_request_kwargs_and_context_hash(self):
        # Historical schema independently reconstructed, not copied from a new
        # preview or session object. Adding either must not alter old authority.
        reviewer = "sha256:" + hashlib.sha256(
            b"wom-kit/exact-human-approval-reviewer-claim/v0.1\0person:local-operator"
        ).hexdigest()
        original_document = {
            "operation": "zettel_edge",
            "archive_identity_sha256": self.context.archive_identity_sha256,
            "plan_sha256": "sha256:" + "a" * 64,
            "target_binding_sha256": "sha256:" + "b" * 64,
            "reviewer_claim_sha256": reviewer,
            "review_binding_codes": ["edge_plan_digest", "target_digest"],
            "warning_codes": [],
        }
        original_hash = "sha256:" + hashlib.sha256(
            b"wom-kit/exact-human-approval-authority/v0.1\0"
            + json.dumps(original_document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            + b"\n"
        ).hexdigest()
        self.assertEqual(authority.exact_human_approval_context_sha256(self.context), original_hash)
        self.assertEqual([field.name for field in fields(self.context)], [
            "operation", "archive_identity_sha256", "plan_sha256", "target_binding_sha256",
            "reviewer_claim", "review_binding_codes", "warning_codes", "target_preview",
        ])
        native = Native()
        with mock.patch.object(workflow, "_request_exact_human_approval_core",
                               wraps=workflow._request_exact_human_approval_core) as request:
            result = self.execute(native=native)
        request.assert_called_once_with(
            self.context, intent=native_approval.ExactHumanApprovalIntent.live_write, native=native,
        )
        self.assertEqual(result["exact_human_approval"]["status"], "succeeded")
        self.assertEqual(authority.exact_human_approval_context_sha256(self.context), original_hash)

    def test_collection_reaches_native_only_and_preserves_exact_claim_context(self):
        for count in (1, 2, 5, 1000):
            with self.subTest(count=count):
                # A separate plan is required for each real one-use claim.
                self.context = replace(self.context, plan_sha256="sha256:" + hashlib.sha256(str(count).encode()).hexdigest())
                before_hash = authority.exact_human_approval_context_sha256(self.context)
                native = Native()
                preview = self.collection(count)
                result = self.execute(native=native, target_collection=preview,
                                      observe_target_binding=lambda: self.context.target_binding_sha256)
                self.assertEqual(sum(native.page_sizes), count)
                self.assertLessEqual(max(native.page_sizes), 20)
                self.assertIn(f"대상 {count:,}개", native.calls[0]["content"])
                self.assertNotIn("합성 로컬 전용 제목", native.calls[0]["content"])
                self.assertEqual(result["exact_human_approval"]["status"], "succeeded")
                self.assertEqual(authority.exact_human_approval_context_sha256(self.context), before_hash)
                public = json.dumps(result, ensure_ascii=False) + repr(self.context) + repr(preview)
                for path in (self.root / authority.CLAIMS_RELATIVE_ROOT).glob("*.json"):
                    public += path.read_text(encoding="utf-8")
                self.assertNotIn("합성 로컬 전용 제목", public)
                self.assertNotIn("target_collection", public)

    def test_collection_cancel_has_no_claim_key_or_writer(self):
        with self.assertRaisesRegex(workflow.ExactHumanApprovalWorkflowError, "^exact_human_approval_cancelled$"):
            self.execute(native=Native(cancel=True), target_collection=self.collection(1000),
                         observe_target_binding=lambda: self.context.target_binding_sha256)
        self.assert_untouched()

    def test_missing_or_invalid_preview_observation_has_no_side_effects(self):
        for options in (
            {"target_collection": self.collection()},
            {"observe_target_binding": lambda: self.context.target_binding_sha256},
            {"target_collection": object(), "observe_target_binding": lambda: self.context.target_binding_sha256},
        ):
            with self.subTest(keys=tuple(options)):
                native = Native()
                with self.assertRaisesRegex(workflow.ExactHumanApprovalWorkflowError, "^exact_human_approval_operation_failed$"):
                    self.execute(native=native, **options)
                self.assertEqual(native.calls, [])
                self.assert_untouched()

    def test_drift_before_during_or_after_native_confirmation_is_fail_closed(self):
        for stage in ("before", "details", "after"):
            with self.subTest(stage=stage):
                current = [self.context.target_binding_sha256]
                change = lambda: current.__setitem__(0, "sha256:" + "f" * 64)
                if stage == "before":
                    change()
                native = Native(during_details=change if stage == "details" else None,
                                after_approve=change if stage == "after" else None)
                observer = mock.Mock(side_effect=lambda: current[0])
                with self.assertRaisesRegex(workflow.ExactHumanApprovalWorkflowError, "^exact_human_approval_operation_failed$") as captured:
                    self.execute(native=native, target_collection=self.collection(), observe_target_binding=observer)
                self.assertEqual(captured.exception.__context__.code, "exact_human_approval_target_changed")
                self.assertEqual(observer.call_count, {"before": 1, "details": 2, "after": 3}[stage])
                self.assertEqual(len(native.calls), 0 if stage == "before" else 1)
                self.assert_untouched()

    def test_observation_exception_does_not_retain_private_failure_text(self):
        def fail_observation():
            raise RuntimeError("SYNTHETIC_PRIVATE_OBSERVATION_VALUE")

        with self.assertRaises(workflow.ExactHumanApprovalWorkflowError) as captured:
            self.execute(native=Native(), target_collection=self.collection(), observe_target_binding=fail_observation)
        error = captured.exception
        rendered = []
        while error is not None:
            rendered.append(str(error) + repr(error))
            error = error.__context__
        self.assertNotIn("SYNTHETIC_PRIVATE_OBSERVATION_VALUE", " ".join(rendered))
        self.assert_untouched()

    def test_legacy_started_claim_resumes_without_new_ui_or_session_binding(self):
        self.writer.return_value = {"ok": False, "reason_code": "synthetic_interruption"}
        started = self.execute(native=Native())
        approval_id = started["exact_human_approval"]["approval_id"]
        original_hash = authority.exact_human_approval_context_sha256(self.context)
        original_claim = next((self.root / authority.CLAIMS_RELATIVE_ROOT).glob("*.json"))
        before = original_claim.read_bytes()
        changed = replace(self.context, operation=native_approval.ExactHumanApprovalOperation.work_session,
                          warning_codes=("work_session_start",))
        writer = mock.Mock(return_value={"ok": True})
        with mock.patch.object(workflow, "_request_exact_human_approval_core", side_effect=AssertionError("no new prompt")) as prompt:
            with self.assertRaisesRegex(workflow.ExactHumanApprovalWorkflowError, "^exact_human_approval_resume_claim_invalid$"):
                workflow._resume_exact_human_approved_write_core(
                    self.root, changed, approval_id, lambda claim: True, writer, key_provider=self.provider,
                )
            self.assertEqual(original_claim.read_bytes(), before)
            writer.assert_not_called()
            resumed = workflow._resume_exact_human_approved_write_core(
                self.root, self.context, approval_id, lambda claim: claim.assert_ready_for_context(self.context) is not None,
                writer, key_provider=self.provider,
            )
            prompt.assert_not_called()
        self.assertEqual(resumed["exact_human_approval"]["status"], "succeeded")
        self.assertEqual(authority.exact_human_approval_context_sha256(self.context), original_hash)
        self.assertEqual(self.provider.creates, [True, False, False])
        signature = inspect.signature(workflow._resume_exact_human_approved_write_core)
        self.assertNotIn("target_collection", signature.parameters)
        self.assertNotIn("observe_target_binding", signature.parameters)

    def test_work_session_action_copy_is_fixed_and_bound_to_authority(self):
        hashes = set()
        for action, expected in (
            ("start", ("이 앱에서 새 작업을 시작할까요?", "작업 시작")),
            ("handoff", ("이 작업을 다른 앱으로 넘길까요?", "작업 넘기기")),
            ("accept", ("이 앱에서 넘겨받은 작업을 이어갈까요?", "작업 이어받기")),
            ("recover", ("중단된 작업을 이 앱에서 다시 맡을까요?", "중단 작업 맡기")),
        ):
            with self.subTest(action=action):
                context = replace(self.context, operation=native_approval.ExactHumanApprovalOperation.work_session,
                                  warning_codes=("work_session_" + action,))
                hashes.add(authority.exact_human_approval_context_sha256(context))
                native = Native(cancel=True)
                decision = native_approval._request_exact_human_approval_core(
                    context, intent=native_approval.ExactHumanApprovalIntent.live_write, native=native,
                )
                self.assertFalse(decision.approved)
                self.assertEqual(native.calls[0]["main_instruction"], expected[0])
                self.assertEqual(native.calls[0]["approve_button_text"], expected[1])
                primary = native.calls[0]["content"]
                for forbidden in ("work_session_", "workstream", "CAS", "digest", self.context.target_binding_sha256):
                    self.assertNotIn(forbidden, primary)
        self.assertEqual(len(hashes), 4)

    def test_work_session_native_callback_flow_publishes_same_action_claim(self):
        # Compose the production ctypes callback/navigation path with the real
        # claim store. Only the system DLL calls and secret provider are fake.
        from test_v0420_target_collection_preview import NativeDialogHarness

        for action in ("start", "handoff", "accept", "recover"):
            with self.subTest(action=action):
                self.context = replace(
                    self.context, operation=native_approval.ExactHumanApprovalOperation.work_session,
                    warning_codes=("work_session_" + action,),
                )
                harness = NativeDialogHarness([
                    native_approval.TARGET_DETAILS_BUTTON_ID,
                    native_approval.APPROVE_BUTTON_ID,
                    native_approval.TARGET_RETURN_BUTTON_ID,
                    native_approval.APPROVE_BUTTON_ID,
                ])
                with mock.patch.object(native_approval, "_activate_comctl32_v6",
                                       side_effect=lambda **kwargs: nullcontext()):
                    result = self.execute(
                        native=harness.native, target_collection=self.collection(),
                        observe_target_binding=lambda: self.context.target_binding_sha256,
                    )
                self.assertEqual(result["exact_human_approval"]["status"], "succeeded")
                self.assertEqual(len(harness.pages), 3)
                self.assertIn("합성 로컬 전용 제목", harness.pages[1]["content"])
                self.assertNotIn(native_approval.APPROVE_BUTTON_ID, harness.pages[1]["buttons"])
                claim_path = self.root / authority.CLAIMS_RELATIVE_ROOT / (
                    result["exact_human_approval"]["approval_id"] + ".json"
                )
                raw = claim_path.read_text(encoding="utf-8")
                self.assertIn('"operation":"work_session"', raw)
                self.assertIn('"warning_codes":["work_session_' + action + '"]', raw)
                self.assertNotIn("합성 로컬 전용 제목", raw)

    def test_missing_conflicting_or_unknown_session_action_is_rejected(self):
        for codes in ((), ("work_session_unknown",), ("work_session_handoff", "work_session_start"),
                      ("work_session_start", "work_session_unknown"), ("warning_set_other",)):
            with self.subTest(codes=codes):
                with self.assertRaisesRegex(native_approval.ExactHumanApprovalWindowsError, "^exact_human_approval_context_invalid$"):
                    replace(self.context, operation=native_approval.ExactHumanApprovalOperation.work_session, warning_codes=codes)


if __name__ == "__main__":
    unittest.main()
